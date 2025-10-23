"""ビジネスロジック層: RSS記事処理とターム正規化・整形などの純粋な処理を提供する。"""

from __future__ import annotations

import calendar
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


@dataclass
class TermCandidate:
    """記事から抽出されたテクニカルターム候補。"""

    original: str
    normalized: str


@dataclass
class ArticleTerms:
    """記事情報と抽出済みターム候補の集合。"""

    title: str
    url: str
    body: str
    media: str
    candidates: List[TermCandidate] = field(default_factory=list)


def _parse_iso8601(value: str) -> Optional[datetime]:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt_obj = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj


def _parse_rfc822(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt_obj = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc)
    return dt_obj


def _struct_time_to_datetime(struct_time) -> Optional[datetime]:
    if not struct_time:
        return None
    try:
        timestamp = calendar.timegm(struct_time)
    except (OverflowError, TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def parse_entry_published(entry) -> Optional[datetime]:
    """RSSエントリから公開日時を抽出する。"""
    iso_keys = ("published", "updated", "dc_date",
                "dc:date", "date", "issued", "created")
    for key in iso_keys:
        value = entry.get(key)
        if value:
            if isinstance(value, list):
                value = value[0]
            dt_obj = _parse_iso8601(str(value))
            if dt_obj:
                return dt_obj

    rfc_keys = ("pubDate", "published", "updated")
    for key in rfc_keys:
        value = entry.get(key) or entry.get(key.lower())
        if value:
            if isinstance(value, list):
                value = value[0]
            dt_obj = _parse_rfc822(str(value))
            if dt_obj:
                return dt_obj

    for attr in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, attr, None) or entry.get(attr)
        dt_obj = _struct_time_to_datetime(struct)
        if dt_obj:
            return dt_obj

    return None


def is_entry_on_date(entry, target_date: date, tz: ZoneInfo) -> bool:
    published_at = parse_entry_published(entry)
    if not published_at:
        return False
    return published_at.astimezone(tz).date() == target_date


def strip_html(raw_html: str) -> str:
    """簡易的にHTMLタグを除去して段落改行を復元する。"""
    if not raw_html:
        return ""
    text = re.sub(
        r"</?(p|div|br|li|ul|ol|h[1-6]|tr|td|th)>",
        "\n",
        raw_html,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\r?\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_entry_text(entry: Dict) -> str:
    """feedparserエントリーから本文テキストを抽出する。"""
    candidates: List[str] = []
    if "summary" in entry:
        candidates.append(entry.summary)
    if "content" in entry:
        for content in entry.content:
            value = content.get("value")
            if value:
                candidates.append(value)
    if not candidates and "description" in entry:
        candidates.append(entry.description)
    merged = "\n\n".join(strip_html(part) for part in candidates if part)
    return merged.strip()


def chunk_text(text: str, max_chars: int) -> Iterable[str]:
    """本文を段落単位で分割し、max_chars以内のチャンクに分ける。"""
    if len(text) <= max_chars:
        yield text
        return
    current: List[str] = []
    current_len = 0
    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        paragraph_len = len(paragraph) + 1
        if current and current_len + paragraph_len > max_chars:
            yield "\n".join(current)
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += paragraph_len
    if current:
        yield "\n".join(current)


def normalize_term(term: str) -> str:
    """重複判定用に用語を正規化したキーへ変換する。"""
    normalized = unicodedata.normalize("NFKC", term)
    normalized = normalized.casefold()
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def parse_terms_list(response_text: str) -> List[str]:
    """ターム抽出応答からterms配列を取り出す。"""
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSONの解析に失敗しました: {exc}") from exc

    raw_terms = payload.get("terms", [])
    if not isinstance(raw_terms, list):
        raise ValueError("JSON中のtermsフィールドが配列ではありません。")

    normalized: List[str] = []
    for item in raw_terms:
        term = str(item).strip()
        if term:
            normalized.append(term)
    return normalized


def truncate_context(text: str, limit: int = 1200) -> str:
    """ChatGPTに渡す文脈を指定文字数に丸める。"""
    if len(text) <= limit:
        return text
    truncated = text[:limit].rstrip()
    return truncated + "..."


def build_unique_term_index(
    articles: List[ArticleTerms],
    context_limit: int = 1200,
) -> Tuple[
    List[Dict[str, str]],
    List[List[str]],
    List[str],
    Dict[str, str],
]:
    """記事群からユニークターム情報と記事ごとの割り当てを構築する。"""
    unique_terms_info: List[Dict[str, str]] = []
    articles_term_order: List[List[str]] = [[] for _ in articles]
    unique_terms_debug: List[str] = []
    original_term_lookup: Dict[str, str] = {}
    seen_global: Dict[str, int] = {}

    for index, article in enumerate(articles):
        for candidate in article.candidates:
            key = candidate.normalized
            if key in seen_global:
                continue
            seen_global[key] = index
            unique_terms_info.append(
                {
                    "term": candidate.original,
                    "normalized": key,
                    "title": article.title,
                    "url": article.url,
                    "context": truncate_context(article.body, context_limit),
                }
            )
            articles_term_order[index].append(key)
            unique_terms_debug.append(candidate.original)
            original_term_lookup[key] = candidate.original

    return unique_terms_info, articles_term_order, unique_terms_debug, original_term_lookup


def build_description_map(
    unique_terms_info: List[Dict[str, str]],
    description_items: List[Dict[str, object]],
    original_term_lookup: Dict[str, str],
) -> Dict[str, Dict[str, object]]:
    """説明レスポンスとユニークターム情報から正規化キーを基準としたマップを生成する。"""
    descriptions_map: Dict[str, Dict[str, object]] = {}

    for item in description_items:
        normalized_key = normalize_term(item["term"])
        if not normalized_key:
            continue
        item["term"] = original_term_lookup.get(normalized_key, item["term"])
        descriptions_map[normalized_key] = item

    for term_info in unique_terms_info:
        key = term_info["normalized"]
        if key not in descriptions_map:
            descriptions_map[key] = {
                "term": original_term_lookup.get(key, term_info["term"]),
                "discription": "説明を生成できませんでした。",
                "References": [],
            }

    return descriptions_map


def build_articles_output(
    articles: List[ArticleTerms],
    articles_term_order: List[List[str]],
    descriptions_map: Dict[str, Dict[str, object]],
) -> List[Dict[str, object]]:
    """記事ごとのターム出力配列を組み立てる。"""
    result: List[Dict[str, object]] = []
    for article, term_keys in zip(articles, articles_term_order):
        term_entries: List[Dict[str, object]] = []
        for key in term_keys:
            detail = descriptions_map.get(key)
            if detail:
                term_entries.append(detail)
        result.append(
            {
                "title": article.title,
                "url": article.url,
                "media": article.media,
                "terms": term_entries,
            }
        )
    return result
