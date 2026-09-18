"""
JSONL utility — practice module inspired by Hermi Gateway's JSONL logging patterns.

Features:
- Append-write with auto-flush
- Tail-read last N lines
- Search within records by key/value
- Streaming read (lazy generator)
- Rotate when file exceeds max_bytes

Design mimics the lightweight approach seen in hermi_gateway/ — no heavy deps,
pure stdlib, explicit is better than implicit.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any


class JsonlStore:
    """Append-only JSONL store with tail read and rotation."""

    def __init__(self, path: str | Path, max_bytes: int = 50 * 1024 * 1024):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # --- write ---

    def append(self, record: dict[str, Any]) -> None:
        """Append one JSON record as a newline-terminated line."""
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
        if self.path.stat().st_size > self.max_bytes:
            self._rotate()

    def append_batch(self, records: list[dict[str, Any]]) -> None:
        """Append multiple records in a single open/write cycle."""
        if not records:
            return
        lines = "".join(
            json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in records
        )
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(lines)
        if self.path.stat().st_size > self.max_bytes:
            self._rotate()

    # --- read ---

    def read_all(self) -> list[dict[str, Any]]:
        """Read all records into memory. Use tail() for large files."""
        return list(self._iter_records())

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        """Read the last N records efficiently by walking backwards."""
        if not self.path.exists():
            return []
        chunk_size = 4096
        file_size = self.path.stat().st_size
        records: list[dict[str, Any]] = []
        buffer = ""
        pos = file_size

        while pos > 0 and len(records) < n:
            read_size = min(chunk_size, pos)
            pos -= read_size
            with open(self.path, "rb") as f:
                f.seek(pos)
                chunk = f.read(read_size + len(buffer)).decode("utf-8", errors="replace")
            lines = chunk.splitlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(records) >= n:
                    break
            buffer = lines[0] if lines else ""

        records.reverse()
        return records[-n:]

    def search(self, key: str, value: Any, limit: int = 20) -> list[dict[str, Any]]:
        """Return records where record[key] == value."""
        results: list[dict[str, Any]] = []
        for record in self._iter_records():
            if record.get(key) == value:
                results.append(record)
                if len(results) >= limit:
                    break
        return results

    def stream(self) -> Generator[dict[str, Any], None, None]:
        """Lazy generator — yields records one by one without loading all."""
        yield from self._iter_records()

    # --- stats ---

    def count(self) -> int:
        """Count records (fast: count newlines in non-empty file)."""
        if not self.path.exists():
            return 0
        size = self.path.stat().st_size
        if size == 0:
            return 0
        with open(self.path, "rb") as f:
            raw = f.read(min(size, 4 * 1024 * 1024))
        return raw.count(b"\n")

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    # --- internal ---

    def _iter_records(self) -> Generator[dict[str, Any], None, None]:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def _rotate(self) -> None:
        """Rename current file with a timestamp + counter suffix, start fresh."""
        if not self.path.exists():
            return
        ts = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        counter = 0
        while True:
            suffix = f"{ts}.{counter:02d}" if counter else ts
            rotated = self.path.with_name(f"{self.path.stem}.{suffix}.jsonl")
            if not rotated.exists():
                break
            counter += 1
        os.rename(self.path, rotated)


# --- standalone helper (for CLI-style use) ---

def format_record(record: dict[str, Any], max_value_len: int = 160) -> str:
    """Format a JSONL record as a human-readable line."""
    ts = record.get("ts") or record.get("time") or record.get("timestamp") or ""
    label = record.get("event") or record.get("type") or record.get("action") or ""
    parts = []
    if ts:
        parts.append(f"[{str(ts)[:24]}]")
    if label:
        parts.append(f"{label}:")
    rest = {k: v for k, v in record.items() if k not in ("ts", "time", "timestamp", "event", "type", "action")}
    if rest:
        text = json.dumps(rest, ensure_ascii=False, default=str)
        if len(text) > max_value_len:
            text = text[:max_value_len] + "..."
        parts.append(text)
    return " ".join(parts)
