from __future__ import annotations

import json

from src import batch_runner


def lambda_handler(event, context):  # pragma: no cover
    result = batch_runner.execute()
    return {"statusCode": 200, "body": json.dumps(result, ensure_ascii=False)}
