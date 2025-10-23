from __future__ import annotations

import json

from src.summarize_zenn import execute


def lambda_handler(event, context):  # pragma: no cover - AWS実行時に呼び出される
    try:
        payload = execute()
    except Exception as exc:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}, ensure_ascii=False),
        }
    return {
        "statusCode": 200,
        "body": json.dumps(payload, ensure_ascii=False),
    }
