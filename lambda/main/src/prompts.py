"""チャットプロンプト生成ロジックをまとめたモジュール。"""

from __future__ import annotations

from typing import List, Optional

TERM_COLLECTION_SYSTEM_PROMPT = (
    "あなたは日本語のテックメディア編集者です。入力された記事本文から技術的な専門用語のみを抽出します。"
    "回答はJSONオブジェクト1つだけで、terms配列に用語（文字列）のみを含てください。また、次に列挙する該当する単語は抽出しないでください。\n"
    "- ITの文脈以外でも使われる一般的な用語(例：タスク、データなど)\n"
    "- ITでも基礎的な用語(例：ループ、ファイルなど)\n"
    "- 言語の名前(例：C言語、JAVAなど)\n"
)

TERM_COLLECTION_USER_PROMPT = (
    "以下の記事本文{chunk_notice}の中から、この記事で特に重要と思われる技術的な専門用語のみを抽出してください。"
    "terms配列には原文通りの表記で最大10件まで列挙し、JSON以外のテキストは出力しないでください。\n"
    "タイトル: {title}\n"
    "URL: {link}\n"
    "本文:\n"
    "{body}"
)


def build_term_collection_messages(
    title: str,
    link: str,
    body: str,
    chunk_index: Optional[int] = None,
    chunk_total: Optional[int] = None,
) -> List[dict]:
    """テクニカルターム抽出用メッセージを生成。"""
    notice = ""
    if chunk_index is not None and chunk_total is not None and chunk_total > 1:
        notice = f"（{chunk_index}/{chunk_total}）"
    user_content = TERM_COLLECTION_USER_PROMPT.format(
        title=title,
        link=link,
        chunk_notice=notice,
        body=body,
    )
    return [
        {"role": "system", "content": TERM_COLLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
