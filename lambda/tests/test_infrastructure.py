import json
import random
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.infrastructure import NotionDatabaseClient


class DummyResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.text = "OK"

    def json(self):
        return {
            "object": "page",
            "properties": self._payload.get("properties", {}),
        }


class DummySession:
    def __init__(self):
        self.headers = {}
        self.requests: List[Tuple[str, dict, float]] = []

    def post(self, url, *, json=None, timeout=None):
        self.requests.append((url, json, timeout))
        return DummyResponse(json)


@pytest.fixture()
def sample_terms():
    rng = random.Random(42)
    terms = [
        ("Codex", "Codexは、AIを活用したコーディング支援ツールです。"),
        ("ClaudeCode", "ClaudeCodeは、AIを用いたコーディング支援ツールです。"),
        ("AIコーディングツール", "AIによるコード生成を支援するツールです。"),
        ("制御", "制御とは、システムを意図通りに動作させることです。"),
        ("運用", "実際の環境でツールを活用することです。"),
    ]
    sample_size = min(5, len(terms))
    return rng.sample(terms, sample_size)


def test_create_term_pages(monkeypatch, sample_terms):
    dummy_session = DummySession()

    def dummy_session_factory():
        return dummy_session

    monkeypatch.setattr("src.infrastructure.requests.Session", dummy_session_factory)

    client = NotionDatabaseClient(
        api_token="secret_dummy",
        database_id="1234567890abcdef1234567890abcdef",
        term_property="term",
        description_property="Description",
        api_version="2025-09-03",
    )

    responses = client.create_term_pages(sample_terms)

    assert len(responses) == len(sample_terms)
    assert len(dummy_session.requests) == len(sample_terms)

    for (url, payload, timeout), (term, description), response in zip(
        dummy_session.requests, sample_terms, responses
    ):
        assert url == "https://api.notion.com/v1/pages"
        assert timeout == pytest.approx(client._timeout)
        properties = payload["properties"]
        assert properties["term"]["title"][0]["text"]["content"] == term
        rich_text = properties["Description"]["rich_text"]
        if description:
            assert rich_text[0]["text"]["content"] == description
        else:
            assert rich_text == []
        assert response["properties"] == properties

    expected_headers = {
        "Authorization": "Bearer secret_dummy",
        "Content-Type": "application/json",
        "Notion-Version": "2025-09-03",
    }
    for key, value in expected_headers.items():
        assert dummy_session.headers[key] == value
