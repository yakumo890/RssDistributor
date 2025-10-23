"""最終出力JSONとChatGPT指示用テンプレートを定義するモジュール。"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List

OUTPUT_TEMPLATE: Dict[str, Any] = {
    "articles": [
        {
            "title": "{記事のタイトル}",
            "url": "記事のURL",
            "media": "記事の掲載メディア",
            "terms": [
                {
                    "term": "記事の中で登場したターム1",
                    "discription": "タームの説明1",
                    "References": [
                        "参考文献URL1",
                        "参考文献URL2",
                    ],
                }
            ],
        }
    ]
}

TERM_TEMPLATE: Dict[str, Any] = {
    "term": "用語例",
    "discription": "用語の説明（100字以内）",
    "References": ["参考文献URL1"],
}


def build_payload(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """articles配列をはめ込んだ最終JSONを返す。"""
    template = copy.deepcopy(OUTPUT_TEMPLATE)
    template["articles"] = articles
    return template


def format_instruction() -> str:
    """OpenAIへ出力形式を指示するための整形済みJSON文字列を返す。"""
    example_article = OUTPUT_TEMPLATE["articles"][0]
    return json.dumps(example_article, ensure_ascii=False, indent=2)


def format_term_instruction() -> str:
    """用語説明JSONのテンプレート文字列を返す。"""
    return json.dumps(TERM_TEMPLATE, ensure_ascii=False, indent=2)
