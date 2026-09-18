"""Tests for jsonl_util.py — following patterns from Hermi Gateway tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

from practice.jsonl_util import JsonlStore, format_record


def test_append_and_tail(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")

    store.append({"msg": "hello", "ts": "1"})
    store.append({"msg": "world", "ts": "2"})

    records = store.tail()
    assert len(records) == 2
    assert records[-1]["msg"] == "world"
    assert records[0]["msg"] == "hello"


def test_tail_returns_last_n(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    for i in range(10):
        store.append({"idx": i})

    records = store.tail(n=3)
    assert len(records) == 3
    assert [r["idx"] for r in records] == [7, 8, 9]


def test_search_by_key(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    store.append({"type": "inbound", "from": "qq"})
    store.append({"type": "outbound", "to": "qq"})
    store.append({"type": "inbound", "from": "web"})

    results = store.search("type", "inbound")
    assert len(results) == 2
    assert all(r["type"] == "inbound" for r in results)


def test_count_empty_file(tmp_path: Path):
    store = JsonlStore(tmp_path / "empty.jsonl")
    assert store.count() == 0


def test_count_after_writes(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    for i in range(5):
        store.append({"i": i})
    assert store.count() == 5


def test_append_batch(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    store.append_batch([
        {"a": 1},
        {"a": 2},
        {"a": 3},
    ])
    assert store.count() == 3


def test_read_all(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    store.append({"id": "x"})
    store.append({"id": "y"})
    store.append({"id": "z"})

    all_records = store.read_all()
    assert len(all_records) == 3
    assert [r["id"] for r in all_records] == ["x", "y", "z"]


def test_skip_empty_lines(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    store.append({"valid": True})
    with open(store.path, "a", encoding="utf-8") as f:
        f.write("\n\n")
    store.append({"valid": False})

    records = store.read_all()
    assert len(records) == 2


def test_rotation(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl", max_bytes=200)
    for i in range(50):
        store.append({"data": "x" * 20})

    rotated_files = sorted(tmp_path.glob("test.*.jsonl"))
    assert len(rotated_files) >= 1
    # rotated file exists and is non-empty
    assert any(f.stat().st_size > 0 for f in rotated_files)
    # new main file exists and is smaller than max_bytes
    assert store.path.exists()
    assert store.path.stat().st_size <= store.max_bytes + 500


def test_search_returns_early_on_limit(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    for i in range(100):
        store.append({"kind": "a"})

    results = store.search("kind", "a", limit=10)
    assert len(results) == 10


def test_tail_on_nonexistent_file(tmp_path: Path):
    store = JsonlStore(tmp_path / "nonexistent.jsonl")
    assert store.tail(10) == []


def test_stream(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    for i in range(3):
        store.append({"n": i})

    streamed = list(store.stream())
    assert len(streamed) == 3
    assert streamed[-1]["n"] == 2


def test_format_record():
    record = {"ts": "2026-07-10T12:00:00", "event": "ping", "status": "ok"}
    output = format_record(record)
    assert "2026-07-10T12:00:00" in output
    assert "ping" in output
    assert "ok" in output


def test_format_record_without_timestamp():
    record = {"action": "test", "result": "pass"}
    output = format_record(record)
    assert "test" in output
    assert "pass" in output


def test_handles_invalid_json_lines_gracefully(tmp_path: Path):
    store = JsonlStore(tmp_path / "test.jsonl")
    store.append({"valid": True})
    with open(store.path, "a", encoding="utf-8") as f:
        f.write("not valid json\n")
    store.append({"valid": True})

    records = store.read_all()
    assert len(records) == 2
