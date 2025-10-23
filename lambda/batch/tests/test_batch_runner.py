import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.batch_runner import _chunk_list


def test_chunk_list_returns_empty_for_non_positive_size():
    assert _chunk_list([{"key": "a"}], 0) == [[{"key": "a"}]]


def test_chunk_list_splits_sequence():
    seq = [{"key": str(i)} for i in range(5)]
    chunks = _chunk_list(seq, 2)
    assert len(chunks) == 3
    assert chunks[0] == seq[:2]
    assert chunks[-1] == seq[-1:]
