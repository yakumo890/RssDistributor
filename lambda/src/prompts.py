"""チャットプロンプト生成ロジックをまとめたモジュール。"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .json_template import format_term_instruction

TERM_COLLECTION_SYSTEM_PROMPT = (
    "あなたは日本語のテックメディア編集者です。入力された記事本文から技術的な専門用語のみを抽出します。"
    "回答はJSONオブジェクト1つだけで、terms配列に用語（文字列）のみを含め、重複語や一般的すぎる語は含めません。"
)

TERM_COLLECTION_USER_PROMPT = (
    "以下の記事本文{chunk_notice}の中から、この記事で特に重要と思われる技術的な専門用語のみを抽出してください。"
    "terms配列には原文通りの表記で最大10件まで列挙し、JSON以外のテキストは出力しないでください。"
    "また、「コード」「フロントエンド」「Webアプリケーション」「タスク」のような、基本的な用語、一般的にも使われる用語は含めないでください。\n"
    "タイトル: {title}\n"
    "URL: {link}\n"
    "本文:\n"
    "{body}"
)

TERM_DESCRIPTION_SYSTEM_PROMPT = (
    "あなたは日本語のテックメディア編集者です。指定された技術用語について100字以内で分かりやすく説明します。"
    "説明文は敬体で記述し、必要に応じて参考URLをReferences配列に追加します（無ければ空配列）。"
    "出力はJSONオブジェクト1つだけで、terms配列に項目を格納してください。"
)

TERM_DESCRIPTION_USER_PROMPT = (
    "次の用語について説明してください。各項目には初出記事の情報と抜粋を付与しています。"
    "以下のJSON構造を用いて回答してください（discriptionキーの綴りに注意してください）。\n"
    "{template}\n\n"
    "{term_blocks}"
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


def build_term_description_messages(
    terms_info: Sequence[Dict[str, str]],
) -> List[dict]:
    """用語説明生成用メッセージを生成。"""
    template = format_term_instruction()
    blocks = []
    for item in terms_info:
        context = item.get("context", "").strip()
        if not context:
            context = "（参照できる本文がありません）"
        indented_context = "\n".join(f"    {line}" if line else "" for line in context.splitlines())
        blocks.append(
            "- 用語: {term}\n"
            "  タイトル: {title}\n"
            "  URL: {url}\n"
            "  抜粋:\n"
            "{context}\n".format(
                term=item["term"],
                title=item["title"],
                url=item["url"],
                context=indented_context,
            )
        )
    user_content = TERM_DESCRIPTION_USER_PROMPT.format(
        template=template,
        term_blocks="\n".join(blocks),
    )
    return [
        {"role": "system", "content": TERM_DESCRIPTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
