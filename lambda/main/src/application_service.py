"""アプリケーションサービス層: ビジネスロジックと外部依存を橋渡しする。"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from zoneinfo import ZoneInfo

from .business_logic import (
    ArticleTerms,
    TermCandidate,
    build_articles_output,
    build_unique_term_index,
    chunk_text,
    extract_entry_text,
    is_entry_on_date,
    normalize_term,
    parse_terms_list,
)
from .json_template import build_payload
from .prompts import build_term_collection_messages


@dataclass
class FeedSource:
    url: str
    media_name: str


@dataclass
class ProcessResult:
    """処理結果をカプセル化する。"""

    payload: Dict[str, Any]
    collected_terms: List[str]
    unique_terms: List[str]
    errors: List[str]
    skipped_articles: List[str]
    articles: List[Dict[str, Any]]
    article_summaries: List[Dict[str, str]]
    term_store_payload: List[Tuple[str, str, str, str]]
    article_records: List[Tuple[str, str]]


class ArticleProcessingService:
    """RSS取得とChatGPT問い合わせを統合するアプリケーションサービス。"""

    def __init__(
        self,
        rss_client,
        chat_client,
        article_repository=None,
        term_repository=None,
        logger=None,
        feed_max_workers: int = 1,
        chatgpt_max_workers: int = 1,
    ):
        self._rss_client = rss_client
        self._chat_client = chat_client
        self._article_repository = article_repository
        self._term_repository = term_repository
        self._logger = logger
        self._feed_max_workers = max(1, feed_max_workers)
        self._chatgpt_max_workers = max(1, chatgpt_max_workers)

    def process(
        self,
        *,
        feed_sources: Sequence[FeedSource],
        per_feed_limit: int,
        model: str,
        chunk_size: int,
        temperature: float,
        delay: float,
        collection_dates: Sequence[date],
        collection_tz: ZoneInfo,
    ) -> ProcessResult:
        all_articles: List[ArticleTerms] = []
        collected_article_meta: List[Dict[str, str]] = []
        collected_terms_debug: List[str] = []
        errors: List[str] = []
        skipped_articles: List[str] = []
        article_records: List[Tuple[str, str]] = []
        processed_in_run: set[str] = set()

        with ThreadPoolExecutor(max_workers=self._feed_max_workers) as executor:
            future_to_feed = {
                executor.submit(
                    self._collect_from_feed,
                    feed=feed,
                    per_feed_limit=per_feed_limit,
                    model=model,
                    chunk_size=chunk_size,
                    temperature=temperature,
                    delay=delay,
                    collection_dates=collection_dates,
                    collection_tz=collection_tz,
                ): feed
                for feed in feed_sources
            }

            for future in as_completed(future_to_feed):
                feed = future_to_feed[future]
                try:
                    (
                        feed_articles,
                        feed_article_meta,
                        feed_skipped,
                        feed_errors,
                        feed_article_records,
                    ) = future.result()
                except Exception as exc:
                    error_msg = f"[{feed.url}] フィード処理中にエラーが発生しました: {exc}"
                    errors.append(error_msg)
                    if self._logger:
                        self._logger.error(error_msg)
                    continue

                errors.extend(feed_errors)
                skipped_articles.extend(feed_skipped)

                for article, meta, record in zip(
                    feed_articles, feed_article_meta, feed_article_records
                ):
                    if article.url in processed_in_run:
                        skipped_articles.append(article.url)
                        continue
                    processed_in_run.add(article.url)
                    all_articles.append(article)
                    collected_article_meta.append(meta)
                    article_records.append(record)
                    collected_terms_debug.extend(
                        [term.original for term in article.candidates])

        if not all_articles:
            return ProcessResult(
                payload=build_payload([]),
                collected_terms=collected_terms_debug,
                unique_terms=[],
                errors=errors,
                skipped_articles=skipped_articles,
                articles=[],
                article_summaries=collected_article_meta,
                term_store_payload=[],
                article_records=[],
            )

        (
            unique_terms_info,
            articles_term_order,
            unique_terms_debug,
            original_term_lookup,
        ) = build_unique_term_index(all_articles)

        if self._term_repository and unique_terms_info:
            normalized_keys = [info["normalized"]
                               for info in unique_terms_info]
            try:
                existing_keys = self._term_repository.get_existing_keys(
                    normalized_keys)
            except Exception as exc:
                errors.append(f"DynamoDBからターム情報を取得中にエラーが発生しました: {exc}")
                existing_keys = set()

            if existing_keys:
                unique_terms_info = [
                    info for info in unique_terms_info if info["normalized"] not in existing_keys
                ]
                unique_terms_debug = [info["term"]
                                      for info in unique_terms_info]
                articles_term_order = [
                    [key for key in keys if key not in existing_keys] for keys in articles_term_order
                ]

        descriptions_map: Dict[str, Dict[str, object]] = {
            info["normalized"]: {
                "term": info["term"],
                "discription": "",
                "References": [],
            }
            for info in unique_terms_info
        }

        articles_output = build_articles_output(
            all_articles,
            articles_term_order,
            descriptions_map,
        )

        term_store_payload: List[Tuple[str, str, str, str]] = []
        jst_now = _current_jst_string()
        for term_info in unique_terms_info:
            key = term_info["normalized"]
            term_store_payload.append(
                (
                    key,
                    term_info["term"],
                    term_info["url"],
                    jst_now,
                )
            )

        payload = build_payload(articles_output)

        return ProcessResult(
            payload=payload,
            collected_terms=collected_terms_debug,
            unique_terms=unique_terms_debug,
            errors=errors,
            skipped_articles=skipped_articles,
            articles=articles_output,
            article_summaries=collected_article_meta,
            term_store_payload=term_store_payload,
            article_records=article_records,
        )

    def _collect_from_feed(
        self,
        *,
        feed: FeedSource,
        per_feed_limit: int,
        model: str,
        chunk_size: int,
        temperature: float,
        delay: float,
        collection_dates: Sequence[date],
        collection_tz: ZoneInfo,
    ) -> Tuple[
        List[ArticleTerms],
        List[Dict[str, str]],
        List[str],
        List[str],
        List[Tuple[str, str]],
    ]:
        articles: List[ArticleTerms] = []
        article_meta: List[Dict[str, str]] = []
        skipped_articles: List[str] = []
        errors: List[str] = []
        articles_to_mark: List[Tuple[str, str]] = []

        try:
            parsed = self._rss_client.fetch(feed.url)
        except Exception as exc:
            error_msg = f"[{feed.url}] RSS取得中にエラーが発生しました: {exc}"
            errors.append(error_msg)
            if self._logger:
                self._logger.error(error_msg)
            return articles, article_meta, skipped_articles, errors, articles_to_mark

        if getattr(parsed, "bozo", False):
            error_msg = f"[{feed.url}] RSSの解析に失敗しました: {parsed.bozo_exception}"
            errors.append(error_msg)
            if self._logger:
                self._logger.error(error_msg)
            return articles, article_meta, skipped_articles, errors, articles_to_mark

        entries = getattr(parsed, "entries", [])
        if self._logger:
            titles = [entry.get("title", "タイトル不明") for entry in entries]
            self._logger.debug(
                f"[Feed:{feed.media_name}] 取得記事数={len(entries)} / タイトル一覧={titles}"
            )

        processed_count = 0

        for entry in entries:
            if processed_count >= per_feed_limit:
                break

            if not any(is_entry_on_date(entry, d, collection_tz) for d in collection_dates):
                continue

            title = entry.get("title", "タイトル不明")
            url = entry.get("link", "リンク不明")

            if self._article_repository and self._article_repository.is_processed(url):
                skipped_articles.append(url)
                continue

            body = extract_entry_text(entry)
            article_terms = ArticleTerms(
                title=title, url=url, body=body, media=feed.media_name)

            chunks = list(chunk_text(body, chunk_size)) if body else []
            seen_terms_in_article = set()

            if chunks:
                try:
                    with ThreadPoolExecutor(max_workers=self._chatgpt_max_workers) as executor:
                        future_to_index = {}
                        total_chunks = len(chunks)
                        for chunk_index, chunk in enumerate(chunks, start=1):
                            messages = build_term_collection_messages(
                                title=title,
                                link=url,
                                body=chunk,
                                chunk_index=chunk_index if total_chunks > 1 else None,
                                chunk_total=total_chunks if total_chunks > 1 else None,
                            )
                            future = executor.submit(
                                self._chat_client.complete,
                                model=model,
                                messages=messages,
                                temperature=temperature,
                                response_format={"type": "json_object"},
                            )
                            future_to_index[future] = chunk_index

                        for future in as_completed(future_to_index):
                            chunk_index = future_to_index[future]
                            try:
                                response_text = future.result()
                            except Exception as exc:
                                error_msg = (
                                    f"[ChatGPT:{feed.media_name}] {title} チャンク{chunk_index}処理中にエラー: {exc}"
                                )
                                errors.append(error_msg)
                                if self._logger:
                                    self._logger.error(error_msg)
                                continue
                            if self._logger:
                                self._logger.debug(
                                    f"[ChatGPT:{feed.media_name}] {title} チャンク{chunk_index}/{total_chunks} 応答: {response_text}"
                                )
                            terms = parse_terms_list(response_text)
                            for term in terms:
                                normalized = normalize_term(term)
                                if not normalized or normalized in seen_terms_in_article:
                                    continue
                                seen_terms_in_article.add(normalized)
                                article_terms.candidates.append(
                                    TermCandidate(
                                        original=term, normalized=normalized)
                                )
                        if self._logger:
                            self._logger.debug(
                                f"[ChatGPT:{feed.media_name}] {title} 取得用語一覧: {[t.original for t in article_terms.candidates]}"
                            )
                except Exception as exc:
                    error_msg = f"[{feed.url}] {title} のチャット処理を実行中に例外: {exc}"
                    errors.append(error_msg)
                    if self._logger:
                        self._logger.error(error_msg)
                    article_terms.candidates.clear()

            articles.append(article_terms)
            article_meta.append(
                {"title": title, "url": url, "media": feed.media_name})
            articles_to_mark.append((url, _current_jst_string()))

            processed_count += 1
            if delay > 0 and processed_count < per_feed_limit:
                time.sleep(delay)

        return (
            articles,
            article_meta,
            skipped_articles,
            errors,
            articles_to_mark,
        )


_JST = ZoneInfo("Asia/Tokyo")


def _current_jst_string() -> str:
    return datetime.now(_JST).strftime("%Y-%m-%d %H:%M:%S")
