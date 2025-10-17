"""プロセス外依存へのアクセスを提供するインフラ層モジュール。"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import feedparser
import requests
from openai import OpenAI

try:
    import boto3  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
except ImportError:  # pragma: no cover - boto3はAWS利用時にのみ必要
    boto3 = None
    ClientError = None


class RSSClient:
    """RSSフィード取得クライアント。"""

    def fetch(self, feed_url: str):
        return feedparser.parse(feed_url)


class ChatCompletionClient:
    """OpenAI Chat Completions APIをラップするクライアント。"""

    def __init__(self, client: OpenAI):
        self._client = client

    def complete(
        self,
        *,
        model: str,
        messages: List[dict],
        temperature: float,
        response_format: Optional[dict] = None,
    ) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format=response_format,
        )
        return response.choices[0].message.content.strip()


class NotionDatabaseClient:
    """Notionデータベースへページを追加するクライアント。"""

    def __init__(
        self,
        *,
        api_token: str,
        database_id: str,
        term_property: str,
        description_property: str,
        api_version: str,
        timeout: float = 10.0,
    ):
        self._database_id = database_id
        self._term_property = term_property
        self._description_property = description_property
        self._api_version = api_version
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
                "Notion-Version": api_version,
            }
        )
        self._timeout = timeout

    def create_term_page(self, term: str, description: str) -> dict:
        """単一のタームをNotionデータベースへ登録する。"""
        payload = self._build_payload(term, description)
        response = self._session.post(
            "https://api.notion.com/v1/pages",
            json=payload,
            timeout=self._timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Notion APIリクエストに失敗しました (status={response.status_code}): {response.text}"
            )
        return response.json()

    def create_term_pages(self, items: Sequence[tuple[str, str]]) -> List[dict]:
        """ターム一覧を順次登録する。レスポンスのリストを返す。"""
        results: List[dict] = []
        for term, description in items:
            results.append(self.create_term_page(term, description))
        return results

    def _build_payload(self, term: str, description: str) -> dict:
        properties = {
            self._term_property: {
                "title": [
                    {
                        "text": {
                            "content": term,
                        }
                    }
                ]
            }
        }
        if description:
            properties[self._description_property] = {
                "rich_text": [
                    {
                        "text": {
                            "content": description,
                        }
                    }
                ]
            }
        else:
            properties[self._description_property] = {"rich_text": []}

        return {
            "parent": {"database_id": self._database_id},
            "properties": properties,
        }


def _require_boto3() -> None:
    if boto3 is None:  # pragma: no cover - boto3未導入時のガード
        raise RuntimeError(
            "この機能を利用するには boto3 と botocore が必要です。"
            "uv add boto3 botocore 等でインストールしてください。"
        )


class SecretsManagerClient:
    """AWS Secrets Managerからシークレットを取得するクライアント。"""

    def __init__(self, *, region: str):
        _require_boto3()
        self._client = boto3.client("secretsmanager", region_name=region)

    def get_secret_string(self, secret_id: str) -> str:
        response = self._client.get_secret_value(SecretId=secret_id)
        if "SecretString" in response:
            return response["SecretString"]
        secret_binary = response.get("SecretBinary")
        if secret_binary is None:
            raise RuntimeError("Secrets ManagerレスポンスにSecretString/Binaryが含まれていません。")
        return base64.b64decode(secret_binary).decode("utf-8")

    def get_secret_dict(self, secret_id: str) -> Dict[str, str]:
        secret_string = self.get_secret_string(secret_id)
        try:
            payload = json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Secrets ManagerのシークレットをJSONとして解析できません: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Secrets ManagerのシークレットはJSONオブジェクトである必要があります。")
        return {str(key): str(value) for key, value in payload.items()}

    def get_secret_field(self, secret_id: str, field: str) -> str:
        payload = self.get_secret_dict(secret_id)
        if field not in payload:
            raise KeyError(f"Secrets Managerシークレットに'{field}'が存在しません。")
        return payload[field]


class DynamoDBArticleRepository:
    """記事URLの重複を管理するDynamoDBリポジトリ。"""

    def __init__(
        self,
        *,
        region: str,
        table_name: str,
        key_attr: str,
        created_at_attr: str,
        client=None,
    ):
        _require_boto3()
        self._client = client or boto3.client("dynamodb", region_name=region)
        self._table = table_name
        self._key_attr = key_attr
        self._created_at_attr = created_at_attr

    def is_processed(self, url: str) -> bool:
        response = self._client.get_item(
            TableName=self._table,
            Key={self._key_attr: {"S": url}},
            ProjectionExpression=self._key_attr,
        )
        return "Item" in response

    def mark_processed(self, url: str, created_at_iso: str) -> None:
        self._client.put_item(
            TableName=self._table,
            Item={
                self._key_attr: {"S": url},
                self._created_at_attr: {"S": created_at_iso},
            },
            ConditionExpression=f"attribute_not_exists({self._key_attr})",
        )


class DynamoDBTermRepository:
    """テクニカルタームの重複を管理するDynamoDBリポジトリ。"""

    def __init__(
        self,
        *,
        region: str,
        table_name: str,
        key_attr: str,
        created_at_attr: str,
        original_attr: str,
        article_url_attr: str,
        client=None,
    ):
        _require_boto3()
        self._client = client or boto3.client("dynamodb", region_name=region)
        self._table = table_name
        self._key_attr = key_attr
        self._created_at_attr = created_at_attr
        self._original_attr = original_attr
        self._article_url_attr = article_url_attr

    def get_existing_keys(self, normalized_terms: Sequence[str]) -> set[str]:
        if not normalized_terms:
            return set()

        unique_keys = list(dict.fromkeys(normalized_terms))
        existing: set[str] = set()

        for chunk in _chunk(unique_keys, 100):
            request_items = {
                self._table: {
                    "Keys": [{self._key_attr: {"S": key}} for key in chunk],
                    "ProjectionExpression": self._key_attr,
                }
            }
            response = self._client.batch_get_item(RequestItems=request_items)
            for item in response.get("Responses", {}).get(self._table, []):
                existing.add(item[self._key_attr]["S"])

            unprocessed = response.get("UnprocessedKeys", {})
            while unprocessed:
                response = self._client.batch_get_item(RequestItems=unprocessed)
                for item in response.get("Responses", {}).get(self._table, []):
                    existing.add(item[self._key_attr]["S"])
                unprocessed = response.get("UnprocessedKeys", {})

        return existing

    def store_terms(self, items: Iterable[Tuple[str, str, str, str]]) -> None:
        """
        DynamoDBへタームを保存する。
        items: (normalized_key, original_term, article_url, created_at_iso)
        """
        put_requests = []
        for normalized, original, article_url, created_at_iso in items:
            put_requests.append(
                {
                    "PutRequest": {
                        "Item": {
                            self._key_attr: {"S": normalized},
                            self._original_attr: {"S": original},
                            self._article_url_attr: {"S": article_url},
                            self._created_at_attr: {"S": created_at_iso},
                        }
                    }
                }
            )
            if len(put_requests) == 25:
                self._write_batch(put_requests)
                put_requests = []

        if put_requests:
            self._write_batch(put_requests)

    def _write_batch(self, put_requests: List[dict]) -> None:
        request_items = {self._table: put_requests}
        response = self._client.batch_write_item(RequestItems=request_items)
        unprocessed = response.get("UnprocessedItems", {})
        while unprocessed:  # pragma: no cover - 正常系では発生しにくい
            response = self._client.batch_write_item(RequestItems=unprocessed)
            unprocessed = response.get("UnprocessedItems", {})


def _chunk(seq: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    for idx in range(0, len(seq), size):
        yield seq[idx : idx + size]


class S3FileLoader:
    """S3から設定ファイルを取得するクライアント。"""

    def __init__(self, *, region: Optional[str] = None):
        _require_boto3()
        self._client = boto3.client("s3", region_name=region)

    def read_text(self, bucket: str, key: str, encoding: str = "utf-8") -> str:
        response = self._client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        return body.decode(encoding)


class SESClient:
    """SESを用いてメール送信を行うクライアント。"""

    def __init__(self, *, region: str):
        _require_boto3()
        self._client = boto3.client("ses", region_name=region)

    def send_email_html(self, source: str, destination: str, subject: str, body_html: str) -> None:
        self._client.send_email(
            Source=source,
            Destination={"ToAddresses": [destination]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": body_html, "Charset": "UTF-8"}},
            },
        )


class CloudWatchLogger:
    """CloudWatch Logsへイベントを記録するロガー。"""

    _LEVEL_PRIORITY = {"DEBUG": 0, "INFO": 1, "ERROR": 2}

    def __init__(self, *, region: str, log_group_name: str, log_level: str = "INFO"):
        _require_boto3()
        self._client = boto3.client("logs", region_name=region)
        self._log_group = log_group_name
        self._level = log_level.upper()
        if self._level not in self._LEVEL_PRIORITY:
            self._level = "INFO"

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        self._info_stream = f"run-{timestamp}"
        self._info_token: Optional[str] = None
        self._debug_stream: Optional[str] = None
        self._debug_token: Optional[str] = None

        self._create_stream(self._info_stream)
        if self._level == "DEBUG":
            self._debug_stream = f"debug-{timestamp}"
            self._create_stream(self._debug_stream)

    def _create_stream(self, stream_name: str) -> None:
        try:
            self._client.create_log_stream(
                logGroupName=self._log_group,
                logStreamName=stream_name,
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code != "ResourceAlreadyExistsException":
                raise

    def _should_log(self, level: str) -> bool:
        level = level.upper()
        if level not in self._LEVEL_PRIORITY:
            level = "INFO"
        return self._LEVEL_PRIORITY[level] >= self._LEVEL_PRIORITY[self._level]

    def _put_event(self, stream: str, token: Optional[str], message: str) -> Optional[str]:
        event = {
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "message": message,
        }
        kwargs = {
            "logGroupName": self._log_group,
            "logStreamName": stream,
            "logEvents": [event],
        }
        if token:
            kwargs["sequenceToken"] = token
        try:
            response = self._client.put_log_events(**kwargs)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code == "InvalidSequenceTokenException":
                expected = exc.response.get("expectedSequenceToken")
                if not expected:
                    raise
                kwargs["sequenceToken"] = expected
                response = self._client.put_log_events(**kwargs)
            else:
                raise
        return response.get("nextSequenceToken", token)

    def log(self, message: str, level: str = "INFO") -> None:
        level = level.upper()
        if not self._should_log(level):
            return
        if level == "DEBUG" and self._debug_stream:
            self._debug_token = self._put_event(self._debug_stream, self._debug_token, message)
        else:
            self._info_token = self._put_event(self._info_stream, self._info_token, message)

    def info(self, message: str) -> None:
        self.log(message, "INFO")

    def debug(self, message: str) -> None:
        self.log(message, "DEBUG")

    def error(self, message: str) -> None:
        self.log(message, "ERROR")
