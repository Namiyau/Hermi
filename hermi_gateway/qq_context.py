from __future__ import annotations

import json
from pathlib import Path


def load_recent_qq_context(log_dir: str | Path, limit: int = 20) -> str:
    path = Path(log_dir) / "gateway_http.jsonl"
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
    items: list[str] = []
    for line in reversed(lines):
        payload = _payload_from_gateway_record(line)
        if not payload:
            continue
        if str(payload.get("post_type") or "") != "message":
            continue
        text = str(payload.get("raw_message") or _text_from_message(payload.get("message")) or "").strip()
        if not text:
            continue
        message_type = str(payload.get("message_type") or "")
        user_id = str(payload.get("user_id") or "")
        if message_type == "group":
            source = f"group:{payload.get('group_id')} user:{user_id}"
        else:
            source = f"private user:{user_id}"
        items.append(f"- {source}: {text[:300]}")
        if len(items) >= limit:
            break
    if not items:
        return ""
    return "[recent_qq_context]\n" + "\n".join(reversed(items))


def _payload_from_gateway_record(line: str) -> dict | None:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    body = record.get("body_preview")
    if not isinstance(body, str) or not body.strip().startswith("{"):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _text_from_message(message) -> str:
    if isinstance(message, str):
        return message
    if not isinstance(message, list):
        return ""
    parts = []
    for item in message:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text":
            parts.append(str((item.get("data") or {}).get("text") or ""))
    return "".join(parts)

