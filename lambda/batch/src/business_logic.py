"""バッチ処理用のビジネスロジックユーティリティ。"""

from __future__ import annotations

import json
from typing import Dict, List


def parse_term_descriptions(response_text: str) -> List[Dict[str, object]]:
    """ChatGPTのレスポンスから用語と説明文を抽出する。"""
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSONの解析に失敗しました: {exc}") from exc

    raw_terms = payload.get("terms", [])
    if not isinstance(raw_terms, list):
        raise ValueError("JSON中のtermsフィールドが配列ではありません。")

    normalized: List[Dict[str, object]] = []
    for item in raw_terms:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        if not term:
            continue
        description = str(
            item.get("discription") or item.get("description") or ""
        ).strip()
        if len(description) > 100:
            description = description[:100].rstrip()

        references = item.get("References") or item.get("references") or []
        if isinstance(references, list):
            refs = [str(ref).strip() for ref in references if str(ref).strip()]
        elif references:
            refs = [str(references).strip()]
        else:
            refs = []

        normalized.append(
            {
                "term": term,
                "discription": description,
                "References": refs,
            }
        )
    return normalized
