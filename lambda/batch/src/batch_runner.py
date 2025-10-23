from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from zoneinfo import ZoneInfo

from .config_loader import AppSettings, load_settings_from_dict
from .infrastructure import (
    ChatCompletionClient,
    CloudWatchLogger,
    DynamoDBTermRepository,
    NotionDatabaseClient,
    S3FileLoader,
    SecretsManagerClient,
)
from .prompts import build_term_description_messages
from .business_logic import parse_term_descriptions
from openai import OpenAI

JST = ZoneInfo("Asia/Tokyo")
JST_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class EnvConfig:
    bucket_name: str
    config_file_name: str
    log_level: str = "INFO"


def _get_env_config() -> EnvConfig:
    try:
        return EnvConfig(
            bucket_name=os.environ["s3_bucket_name"],
            config_file_name=os.environ["config_file_name"],
            log_level=os.environ.get("log_level", "INFO"),
        )
    except KeyError as exc:  # pragma: no cover
        raise RuntimeError(f"環境変数 {exc.args[0]} が設定されていません。") from exc


def _load_settings(env: EnvConfig, s3_loader: S3FileLoader) -> AppSettings:
    config_text = s3_loader.read_text(env.bucket_name, env.config_file_name)
    config_dict = json.loads(config_text)
    return load_settings_from_dict(config_dict)


def _current_jst_string() -> str:
    return datetime.now(JST).strftime(JST_FORMAT)


def _chunk_list(seq: Sequence[Dict[str, str]], size: int) -> List[Sequence[Dict[str, str]]]:
    if size <= 0:
        size = 20
    return [seq[i: i + size] for i in range(0, len(seq), size)]


def execute() -> Dict[str, int]:
    env_config = _get_env_config()
    s3_loader = S3FileLoader(region=os.environ.get("AWS_REGION"))
    settings = _load_settings(env_config, s3_loader)

    if not settings.cloudwatch:
        raise RuntimeError("configにcloudwatch設定が存在しません。")

    logger = CloudWatchLogger(
        region=settings.cloudwatch.region,
        log_group_name=settings.cloudwatch.log_group_name,
        log_level=env_config.log_level,
    )

    if not settings.secrets_manager:
        raise RuntimeError("configにSecrets Manager設定が存在しません。")

    secrets_client = SecretsManagerClient(
        region=settings.secrets_manager.region)
    secret_values = secrets_client.get_secret_dict(
        settings.secrets_manager.secret_id)

    try:
        if not settings.processing:
            raise RuntimeError("configにprocessing設定が存在しません。")
        processing = settings.processing

        openai_key = secret_values.get(settings.secrets_manager.openai_api_key_field)
        if not openai_key:
            raise RuntimeError("Secrets ManagerからOpenAI APIキーを取得できませんでした。")

        notion_token = secret_values.get(settings.secrets_manager.notion_api_token_key)
        if not notion_token:
            raise RuntimeError("Secrets ManagerからNotion APIトークンを取得できませんでした。")

        if not settings.dynamodb:
            raise RuntimeError("configにDynamoDB設定が存在しません。")

        term_repo = DynamoDBTermRepository(
            region=settings.dynamodb.region,
            table_name=settings.dynamodb.terms_table_name,
            key_attr=settings.dynamodb.term_attr,
            created_at_attr=settings.dynamodb.created_at_attr,
            original_attr=settings.dynamodb.original_attr,
            article_url_attr=settings.dynamodb.article_url_attr,
            updated_at_attr=settings.dynamodb.updated_at_attr,
            is_described_attr=settings.dynamodb.is_described_attr,
        )

        terms_to_process = term_repo.fetch_terms_for_description(
            processing.description_fetch_limit
        )
        if not terms_to_process:
            logger.info("[Batch] 説明生成対象の用語はありませんでした。")
            logger.info("[Batch] 用語説明バッチを正常終了しました (processed=0, failed=0)")
            return {"processed": 0, "failed": 0}

        openai_client = ChatCompletionClient(OpenAI(api_key=openai_key))
        notion_client = NotionDatabaseClient(
            api_token=notion_token,
            database_id=settings.notion.database_id,
            term_property=settings.notion.term_property,
            description_property=settings.notion.description_property,
            api_version=settings.notion.api_version,
            timeout=processing.notion_timeout_seconds,
        )

        descriptions: Dict[str, Dict[str, str]] = {}
        failures: List[str] = []

        batches = _chunk_list(terms_to_process, processing.description_batch_size)
        for idx, batch in enumerate(batches, start=1):
            terms_info = [
                {
                    "term": item["term"],
                    "title": "",
                    "url": item["article_url"],
                    "context": "",
                }
                for item in batch
            ]
            messages = build_term_description_messages(terms_info)
            try:
                response_text = openai_client.complete(
                    model=processing.model,
                    messages=messages,
                    temperature=processing.temperature,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:
                logger.error(f"[Batch] ChatGPT問い合わせ失敗: {exc}")
                failures.extend(item["key"] for item in batch)
                continue

            logger.debug(
                f"[Batch] ChatGPTレスポンス({idx}/{len(batches)}): {response_text}"
            )
            try:
                items = parse_term_descriptions(response_text)
            except Exception as exc:
                logger.error(f"[Batch] ChatGPTレスポンス解析失敗: {exc}")
                failures.extend(item["key"] for item in batch)
                continue

            if len(items) != len(batch):
                logger.debug(
                    f"[Batch] ChatGPTレスポンス件数が一致しません (expected {len(batch)}, got {len(items)})"
                )

            for original, parsed in zip(batch, items):
                descriptions[original["key"]] = parsed
            if len(items) < len(batch):
                for original in batch[len(items) :]:
                    failures.append(original["key"])

        if not descriptions:
            logger.error("[Batch] 説明を生成できた用語がありませんでした。")
            return {"processed": 0, "failed": len(failures)}

        notion_records = [
            {
                "key": key,
                "term": data.get("term", ""),
                "description": data.get("discription", ""),
            }
            for key, data in descriptions.items()
        ]

        notion_batch_size = max(1, processing.notion_batch_size)
        notion_batches = [
            notion_records[i: i + notion_batch_size]
            for i in range(0, len(notion_records), notion_batch_size)
        ]

        processed_total = 0
        failures_for_update: List[str] = []

        for idx, batch in enumerate(notion_batches, start=1):
            payload = [(record["term"], record["description"]) for record in batch]
            try:
                response = notion_client.create_term_pages(payload)
            except Exception as exc:
                logger.error(
                    f"[Batch] Notion書き込み失敗({idx}/{len(notion_batches)}): {exc}"
                )
                failures_for_update.extend(record["key"] for record in batch)
                continue

            logger.debug(
                f"[Batch] Notion書き込み({idx}/{len(notion_batches)}): {response}")

            timestamp = _current_jst_string()
            keys = [record["key"] for record in batch]
            term_repo.mark_terms_described(keys, timestamp)
            processed_total += len(keys)

        if failures_for_update:
            logger.error(f"[Batch] Notion登録に失敗したキー: {failures_for_update}")

        if failures:
            logger.error(f"[Batch] ChatGPTもしくはNotionで失敗したキー: {failures}")

        logger.info(
            f"[Batch] 用語説明バッチが完了しました (processed={processed_total}, failed={len(failures)})"
        )

        return {"processed": processed_total, "failed": len(failures)}

    except Exception as exc:
        logger.error(f"[Batch] バッチ処理中に未処理の例外が発生しました: {exc}")
        raise
