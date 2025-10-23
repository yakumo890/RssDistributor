"""バッチ処理用のプロンプト定義。"""

from __future__ import annotations

from typing import Dict, List, Sequence

from .json_template import format_term_instruction

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


def build_term_description_messages(
    terms_info: Sequence[Dict[str, str]],
) -> List[dict]:
    template = format_term_instruction()
    blocks = []
    for item in terms_info:
        context = item.get("context", "").strip()
        if not context:
            context = "（参照できる本文がありません）"
        indented_context = "\n".join(
            f"    {line}" if line else "" for line in context.splitlines())
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
