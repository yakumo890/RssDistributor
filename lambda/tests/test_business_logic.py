import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zoneinfo import ZoneInfo

import src.business_logic as bl


def test_normalize_term_handles_case_and_space():
    assert bl.normalize_term("  Cloud Code ") == "cloudcode"
    assert bl.normalize_term("ＭＬ  ") == "ml"


def test_parse_entry_published_dc_date():
    entry = {
        "dc:date": "2025-10-13T09:30:00+09:00",
    }
    published = bl.parse_entry_published(entry)
    assert published is not None
    assert published.year == 2025
    assert published.tzinfo is not None
    assert published.utcoffset().total_seconds() == 9 * 3600


def test_parse_entry_published_pubdate():
    entry = {
        "pubDate": "Mon, 13 Oct 2025 00:00:00 GMT",
    }
    published = bl.parse_entry_published(entry)
    assert published is not None
    assert published.tzinfo is not None
    assert published.hour == 0
    assert published.minute == 0


def test_parse_entry_published_atom_iso():
    entry = {
        "published": "2025-10-13T12:34:56Z",
    }
    published = bl.parse_entry_published(entry)
    assert published is not None
    assert published.year == 2025
    assert published.month == 10
    assert published.day == 13
    assert published.hour == 12
    assert published.tzinfo is not None


def test_is_entry_on_date_true_for_same_day():
    entry = {
        "dc_date": "2025-10-13T08:00:00+09:00",
    }
    tz = ZoneInfo("Asia/Tokyo")
    assert bl.is_entry_on_date(entry, date(2025, 10, 13), tz)
    assert not bl.is_entry_on_date(entry, date(2025, 10, 12), tz)


def test_chunk_text_preserves_paragraphs():
    text = "paragraph one\n\nparagraph two"
    chunks = list(bl.chunk_text(text, max_chars=10))
    assert len(chunks) == 2
