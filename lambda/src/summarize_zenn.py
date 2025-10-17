#!/usr/bin/env python3
"""エントリーポイント: RSSフィードから技術記事を収集し結果を生成する。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from zoneinfo import ZoneInfo

from .application_service import ArticleProcessingService, FeedSource, ProcessResult
from .config_loader import AppSettings, load_settings_from_dict
from .infrastructure import (
    ChatCompletionClient,
    CloudWatchLogger,
    DynamoDBArticleRepository,
    DynamoDBTermRepository,
    NotionDatabaseClient,
    RSSClient,
    S3FileLoader,
    SESClient,
    SecretsManagerClient,
)
from openai import OpenAI


@dataclass
class EnvConfig:
    bucket_name: str
    config_file_name: str
    feed_sources_file_name: str
    mail_template_file_name: str
    log_level: str = "INFO"


def _get_env_config() -> EnvConfig:
    try:
        return EnvConfig(
            bucket_name=os.environ["s3_bucket_name"],
            config_file_name=os.environ["config_file_name"],
            feed_sources_file_name=os.environ["feed_sources_file_name"],
            mail_template_file_name=os.environ["mail_body_template_file_name"],
            log_level=os.environ.get("log_level", "INFO"),
        )
    except KeyError as exc:  # pragma: no cover - 実行時に検知
        raise RuntimeError(f"環境変数 {exc.args[0]} が設定されていません。") from exc


def _load_settings_from_s3(env: EnvConfig, s3_loader: S3FileLoader) -> AppSettings:
    config_text = s3_loader.read_text(env.bucket_name, env.config_file_name)
    config_dict = json.loads(config_text)
    return load_settings_from_dict(config_dict)


def _load_feed_sources(env: EnvConfig, s3_loader: S3FileLoader) -> List[FeedSource]:
    feed_text = s3_loader.read_text(env.bucket_name, env.feed_sources_file_name)
    feed_payload = json.loads(feed_text)
    articles = feed_payload.get("articles", [])
    feed_sources: List[FeedSource] = []
    for item in articles:
        try:
            feed_sources.append(FeedSource(url=item["url"], media_name=item["media_name"]))
        except KeyError as exc:
            raise ValueError(f"feed_sources.json のレコードに必要なキーが不足しています: {exc}") from exc
    return feed_sources


def _load_mail_template(env: EnvConfig, s3_loader: S3FileLoader) -> str:
    return s3_loader.read_text(env.bucket_name, env.mail_template_file_name)


def _resolve_secret_values(settings: AppSettings, secrets_client: SecretsManagerClient) -> Dict[str, str]:
    if not settings.secrets_manager:
        return {}
    secrets_cfg = settings.secrets_manager
    return secrets_client.get_secret_dict(secrets_cfg.secret_id)


def _resolve_openai_key(settings: AppSettings, secret_values: Dict[str, str]) -> Optional[str]:
    if settings.openai and settings.openai.api_key:
        return settings.openai.api_key
    if settings.secrets_manager:
        key_name = settings.secrets_manager.openai_api_key_field
        if key_name in secret_values:
            return secret_values[key_name]
    return os.environ.get("OPENAI_API_KEY")


def _render_subject(template: str, current_time: datetime) -> str:
    pattern = re.compile(r"\{date:([^}]+)\}")

    def replace(match: re.Match[str]) -> str:
        fmt = match.group(1)
        return current_time.strftime(fmt)

    return pattern.sub(replace, template)


def _render_mail_body(template: str, articles: List[Dict[str, str]]) -> str:
    sections = []
    for article in articles:
        sections.append(
            template.format(
                url=article["url"],
                media=article.get("media", ""),
                title=article["title"],
            )
        )
    return "<body>" + "".join(sections) + "</body>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RSSフィードから技術記事を収集します。")
    return parser.parse_args()


def _log_success(logger: Optional[CloudWatchLogger], result: ProcessResult, collection_date: datetime.date) -> None:
    if not logger:
        return
    date_str = collection_date.isoformat()
    article_lines = [f"{item['title']} ({item['url']})" for item in result.article_summaries]
    if not article_lines:
        article_lines = ["(none)"]
    logger.info("[INFO][{0}] 収集した記事一覧\n".format(date_str) + "\n".join(article_lines))

    term_lines = result.unique_terms if result.unique_terms else ["(none)"]
    logger.info("[INFO][{0}] 収集した技術用語一覧\n".format(date_str) + "\n".join(term_lines))


def _log_failure(logger: Optional[CloudWatchLogger], collection_date: datetime.date, reason: str) -> None:
    if not logger:
        return
    date_str = collection_date.isoformat()
    logger.error(f"[ERROR][{date_str}] 収集に失敗\n{reason}")


def _create_openai_client(api_key: Optional[str]) -> OpenAI:
    if not api_key:
        raise RuntimeError("OpenAI APIキーが取得できませんでした。")
    return OpenAI(api_key=api_key)


def _prepare_notion_client(settings: AppSettings, notion_token: Optional[str]) -> NotionDatabaseClient:
    if not settings.notion:
        raise RuntimeError("configにNotion設定が存在しません。")
    if not notion_token:
        raise RuntimeError("Secrets ManagerからNotion APIトークンを取得できませんでした。")
    settings.notion.api_token = notion_token
    return NotionDatabaseClient(
        api_token=notion_token,
        database_id=settings.notion.database_id,
        term_property=settings.notion.term_property,
        description_property=settings.notion.description_property,
        api_version=settings.notion.api_version,
    )


def execute(push_to_notion_override: Optional[bool] = None) -> Dict[str, Any]:
    env_config = _get_env_config()
    s3_loader = S3FileLoader(region=os.environ.get("AWS_REGION"))
    settings = _load_settings_from_s3(env_config, s3_loader)

    if not settings.cloudwatch:
        raise RuntimeError("configにcloudwatch設定が存在しません。")
    cloudwatch_logger = CloudWatchLogger(
        region=settings.cloudwatch.region,
        log_group_name=settings.cloudwatch.log_group_name,
        log_level=env_config.log_level,
    )

    secret_client = (
        SecretsManagerClient(region=settings.secrets_manager.region)
        if settings.secrets_manager
        else None
    )
    secret_values: Dict[str, str] = {}
    if secret_client and settings.secrets_manager:
        secret_values = _resolve_secret_values(settings, secret_client)

    openai_key = _resolve_openai_key(settings, secret_values)
    openai_client = _create_openai_client(openai_key)

    rss_client = RSSClient()
    chat_client = ChatCompletionClient(openai_client)

    if not settings.dynamodb:
        raise RuntimeError("configにDynamoDB設定が存在しません。")

    dynamodb_cfg = settings.dynamodb
    article_repo = DynamoDBArticleRepository(
        region=dynamodb_cfg.region,
        table_name=dynamodb_cfg.articles_table_name,
        key_attr=dynamodb_cfg.article_attr,
        created_at_attr=dynamodb_cfg.created_at_attr,
    )
    term_repo = DynamoDBTermRepository(
        region=dynamodb_cfg.region,
        table_name=dynamodb_cfg.terms_table_name,
        key_attr=dynamodb_cfg.term_attr,
        created_at_attr=dynamodb_cfg.created_at_attr,
        original_attr=dynamodb_cfg.original_attr,
        article_url_attr=dynamodb_cfg.article_url_attr,
    )

    feed_sources = _load_feed_sources(env_config, s3_loader)
    if not feed_sources:
        raise RuntimeError("feed_sources.json にフィードが定義されていません。")

    if not settings.processing:
        raise RuntimeError("configにprocessing設定が存在しません。")
    processing = settings.processing
    collection_tz = ZoneInfo(processing.collection_timezone)
    collection_dt = datetime.now(collection_tz)
    collection_dates = [
        (collection_dt.date() - timedelta(days=offset))
        for offset in range(max(1, processing.collection_days))
    ]

    mail_template = _load_mail_template(env_config, s3_loader)

    notion_client = _prepare_notion_client(
        settings,
        secret_values.get(settings.secrets_manager.notion_api_token_key) if settings.secrets_manager else None,
    )

    source_email = secret_values.get(settings.secrets_manager.source_email_key)
    destination_email = secret_values.get(settings.secrets_manager.destination_email_key)
    if not source_email or not destination_email:
        raise RuntimeError("送信元/送信先メールアドレスがSecrets Managerに存在しません。")

    if not settings.ses:
        raise RuntimeError("configにSES設定が存在しません。")
    ses_client = SESClient(region=settings.ses.region)

    service = ArticleProcessingService(
        rss_client,
        chat_client,
        article_repository=article_repo,
        term_repository=term_repo,
        logger=cloudwatch_logger,
        feed_max_workers=processing.feed_max_workers,
        chatgpt_max_workers=processing.chatgpt_max_workers,
    )

    try:
        result = service.process(
            feed_sources=feed_sources,
            per_feed_limit=processing.per_feed_limit,
            model=processing.model,
            chunk_size=processing.chunk_size,
            temperature=processing.temperature,
            delay=processing.delay_seconds,
            collection_dates=collection_dates,
            collection_tz=collection_tz,
        )
    except Exception as exc:
        _log_failure(cloudwatch_logger, collection_dates[0], str(exc))
        raise

    subject = _render_subject(settings.ses.subject_template, collection_dt)
    body_html = _render_mail_body(mail_template, result.article_summaries)
    if cloudwatch_logger:
        cloudwatch_logger.debug(f"[SES] 送信メール本文:\n{body_html}")

    def chunk_list(seq: Sequence[Tuple[str, str]], size: int) -> List[Sequence[Tuple[str, str]]]:
        if size <= 0:
            size = 50
        return [seq[i : i + size] for i in range(0, len(seq), size)]

    def store_articles() -> None:
        if not result.article_records:
            return
        for url, created_at in result.article_records:
            article_repo.mark_processed(url, created_at)
        if cloudwatch_logger:
            cloudwatch_logger.debug(
                f"[DynamoDB] 記事URL {len(result.article_records)} 件登録完了"
            )

    def store_terms() -> None:
        if not result.term_store_payload:
            return
        term_repo.store_terms(result.term_store_payload)
        if cloudwatch_logger:
            cloudwatch_logger.debug(
                f"[DynamoDB] 技術用語 {len(result.term_store_payload)} 件登録完了"
            )

    def send_to_notion() -> None:
        if not result.notion_items:
            return
        batch_size = settings.notion.batch_size if settings.notion else 50
        batches = chunk_list(result.notion_items, batch_size)
        with ThreadPoolExecutor(max_workers=max(1, processing.notion_max_workers)) as notion_executor:
            future_to_index = {
                notion_executor.submit(notion_client.create_term_pages, batch): idx
                for idx, batch in enumerate(batches)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                response = future.result()
                if cloudwatch_logger:
                    cloudwatch_logger.debug(
                        f"[Notion] バッチ{idx + 1}/{len(batches)} レスポンス: {response}"
                    )

    def send_email() -> None:
        ses_client.send_email_html(source_email, destination_email, subject, body_html)
        if cloudwatch_logger:
            cloudwatch_logger.debug(f"[SES] メール送信完了: {destination_email}")

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            if result.article_records:
                futures.append(executor.submit(store_articles))
            if result.term_store_payload:
                futures.append(executor.submit(store_terms))
            if result.notion_items:
                futures.append(executor.submit(send_to_notion))
            futures.append(executor.submit(send_email))
            for future in futures:
                future.result()
    except Exception as exc:
        _log_failure(cloudwatch_logger, collection_dates[0], str(exc))
        raise

    _log_success(cloudwatch_logger, result, collection_dates[0])

    return result.payload


def run_cli(push_to_notion_override: Optional[bool]) -> int:
    try:
        payload = execute(push_to_notion_override)
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    return run_cli(args.push_to_notion)


if __name__ == "__main__":  # pragma: no cover - CLI 実行時のみ
    sys.exit(main())
