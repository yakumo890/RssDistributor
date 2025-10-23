"""設定ファイルを読み込み、外部サービスの資格情報を提供するモジュール。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = Path("config.json")


@dataclass
class NotionSettings:
    api_token: str
    database_id: str
    term_property: str = "term"
    description_property: str = "Description"
    api_version: str = "2025-09-03"
    notion_batch_size: int = 50


@dataclass
class OpenAISettings:
    api_key: Optional[str] = None


@dataclass
class SecretsManagerSettings:
    secret_id: str
    region: str
    openai_api_key_field: str
    notion_api_token_key: str
    source_email_key: str
    destination_email_key: str


@dataclass
class DynamoDBSettings:
    region: str
    articles_table_name: str
    terms_table_name: str
    article_attr: str
    term_attr: str
    created_at_attr: str
    original_attr: str
    article_url_attr: str
    updated_at_attr: str
    is_described_attr: str


@dataclass
class ProcessingSettings:
    model: str
    per_feed_limit: int
    chunk_size: int
    temperature: float
    collection_timezone: str = "UTC"
    delay_seconds: float = 0.0
    collection_days: int = 1
    notion_batch_size: int = 50
    description_batch_size: int = 20
    description_fetch_limit: int = 200
    feed_max_workers: int = 1
    chatgpt_max_workers: int = 1
    notion_max_workers: int = 1
    notion_timeout_seconds: float = 10.0


@dataclass
class OutputSettings:
    push_to_notion: bool = False


@dataclass
class AppSettings:
    notion: NotionSettings | None = None
    openai: OpenAISettings | None = None
    secrets_manager: SecretsManagerSettings | None = None
    dynamodb: DynamoDBSettings | None = None
    processing: ProcessingSettings | None = None
    output: OutputSettings | None = None
    ses: Optional["SESSettings"] = None
    cloudwatch: Optional["CloudWatchSettings"] = None


@dataclass
class SESSettings:
    region: str
    subject_template: str


@dataclass
class CloudWatchSettings:
    region: str
    log_group_name: str


def _read_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"設定ファイルが見つかりません: {path}. config.json を作成してください。"
        )

    with path.open("r", encoding="utf-8") as fp:
        try:
            return json.load(fp)
        except json.JSONDecodeError as exc:
            raise ValueError(f"設定ファイルのJSON解析に失敗しました: {exc}") from exc


def load_settings(path: Path = DEFAULT_CONFIG_PATH) -> AppSettings:
    raw = _read_config_file(path)
    return load_settings_from_dict(raw)


def load_settings_from_dict(raw: Dict[str, Any]) -> AppSettings:
    default_region = "ap-northeast-1"

    notion_settings = None
    notion_raw = raw.get("notion")
    if notion_raw:
        try:
            notion_settings = NotionSettings(
                api_token=notion_raw.get("api_token", ""),
                database_id=notion_raw["database_id"],
                term_property=notion_raw.get("term_property", "Term"),
                description_property=notion_raw.get(
                    "description_property", "Description"),
                api_version=notion_raw.get("api_version", "2025-09-03"),
            )
        except KeyError as exc:
            raise KeyError(f"Notion設定に必要なキーが不足しています: {exc}") from exc

    openai_raw = raw.get("openai", {})
    openai_settings = None
    if openai_raw or "openai_api_key" in raw:
        if not openai_raw:
            openai_raw = {"api_key": raw.get("openai_api_key")}
        openai_settings = OpenAISettings(api_key=openai_raw.get("api_key"))

    aws_raw = raw.get("aws", {})

    secrets_settings = None
    secrets_raw = aws_raw.get("secrets_manager") or raw.get("secrets_manager")
    if secrets_raw:
        try:
            secrets_settings = SecretsManagerSettings(
                secret_id=secrets_raw["secret_id"],
                region=secrets_raw.get("region", default_region),
                openai_api_key_field=secrets_raw["OpenAI_api_key"],
                notion_api_token_key=secrets_raw["Notion_api_token_key"],
                source_email_key=secrets_raw["source_email_address_key"],
                destination_email_key=secrets_raw["destination_email_address_key"],
            )
        except KeyError as exc:
            raise KeyError(f"Secrets Manager設定に必要なキーが不足しています: {exc}") from exc

    dynamodb_settings = None
    dynamodb_raw = aws_raw.get("dynamodb") or raw.get("dynamodb")
    if dynamodb_raw:
        try:
            dynamodb_settings = DynamoDBSettings(
                region=dynamodb_raw.get("region", default_region),
                articles_table_name=dynamodb_raw["articles_table_name"],
                terms_table_name=dynamodb_raw["terms_table_name"],
                article_attr=dynamodb_raw["article_attr"],
                term_attr=dynamodb_raw["term_attr"],
                created_at_attr=dynamodb_raw["created_at_attr"],
                original_attr=dynamodb_raw["original_attr"],
                article_url_attr=dynamodb_raw["article_url_attr"],
                updated_at_attr=dynamodb_raw["updated_at_attr"],
                is_described_attr=dynamodb_raw["is_described_attr"],
            )
        except KeyError as exc:
            raise KeyError(f"DynamoDB設定に必要なキーが不足しています: {exc}") from exc

    processing_settings = None
    processing_raw = raw.get("processing")
    if processing_raw:
        try:
            processing_settings = ProcessingSettings(
                model=processing_raw["model"],
                per_feed_limit=int(processing_raw["per_feed_limit"]),
                chunk_size=int(processing_raw["chunk_size"]),
                temperature=float(processing_raw["temperature"]),
                collection_timezone=processing_raw.get(
                    "collection_timezone", "UTC"),
                delay_seconds=float(processing_raw.get("delay_seconds", 0.0)),
                collection_days=int(processing_raw.get("collection_days", 1)),
                notion_batch_size=int(
                    processing_raw.get("notion_batch_size", 50)),
                description_batch_size=int(
                    processing_raw.get("description_batch_size", 20)),
                description_fetch_limit=int(
                    processing_raw.get("description_fetch_limit", 200)),
                feed_max_workers=int(
                    processing_raw.get("feed_max_workers", 1)),
                chatgpt_max_workers=int(
                    processing_raw.get("chatgpt_max_workers", 1)),
                notion_max_workers=int(
                    processing_raw.get("notion_max_workers", 1)),
                notion_timeout_seconds=float(
                    processing_raw.get("notion_timeout_seconds", 10.0)
                ),
            )
        except KeyError as exc:
            raise KeyError(f"Processing設定に必要なキーが不足しています: {exc}") from exc

    output_raw = raw.get("output", {})
    output_settings = OutputSettings(
        push_to_notion=bool(output_raw.get("push_to_notion", False))
    )

    ses_settings = None
    ses_raw = aws_raw.get("ses") or raw.get("ses")
    if ses_raw:
        try:
            ses_settings = SESSettings(
                region=ses_raw.get("region", default_region),
                subject_template=ses_raw["subject_template"],
            )
        except KeyError as exc:
            raise KeyError(f"SES設定に必要なキーが不足しています: {exc}") from exc

    cloudwatch_settings = None
    cloudwatch_raw = aws_raw.get("cloudwatch") or raw.get("cloudwatch")
    if cloudwatch_raw:
        try:
            cloudwatch_settings = CloudWatchSettings(
                region=cloudwatch_raw.get("region", default_region),
                log_group_name=cloudwatch_raw["log_group_name"],
            )
        except KeyError as exc:
            raise KeyError(f"CloudWatch設定に必要なキーが不足しています: {exc}") from exc

    return AppSettings(
        notion=notion_settings,
        openai=openai_settings,
        secrets_manager=secrets_settings,
        dynamodb=dynamodb_settings,
        processing=processing_settings,
        output=output_settings,
        ses=ses_settings,
        cloudwatch=cloudwatch_settings,
    )
