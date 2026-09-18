from __future__ import annotations

import re
import uuid
from typing import Any


CHANNEL_ENVELOPE_FIELDS = [
    "channel",
    "source",
    "transport",
    "chat_type",
    "user_id",
    "group_id",
    "message_id",
    "sender_role",
    "permissions",
    "target_profile",
    "attachments",
    "trace_id",
]


def normalize_channel_envelope(payload: dict[str, Any], *, default_profile: str) -> dict[str, Any]:
    source = _clean_token(payload.get("source") or "qq")
    channel = _clean_token(payload.get("channel") or ("qq" if source == "qq" else source))
    message_id = str(payload.get("message_id") or "").strip()
    trace_id = str(payload.get("trace_id") or "").strip() or _default_trace_id(source, message_id)
    envelope = {
        "channel": channel,
        "source": source,
        "transport": _clean_token(payload.get("transport") or _default_transport(source)),
        "chat_type": _clean_token(payload.get("chat_type") or "private"),
        "user_id": str(payload.get("user_id") or "").strip(),
        "group_id": str(payload.get("group_id") or "").strip(),
        "message_id": message_id,
        "sender_role": _clean_token(payload.get("sender_role") or "friend"),
        "permissions": _string_list(payload.get("permissions")),
        "target_profile": str(payload.get("target_profile") or default_profile).strip() or default_profile,
        "attachments": _attachment_list(payload.get("attachments")),
        "trace_id": trace_id,
    }
    if source == "qq":
        envelope["channel"] = "qq"
        envelope["transport"] = envelope["transport"] or "napcat_onebot"
    return envelope


def _default_transport(source: str) -> str:
    return {
        "qq": "napcat_onebot",
        "hermi_web": "web",
        "hermi_pwa": "pwa",
        "api": "http_api",
        "remote_agent": "remote_agent",
    }.get(source, "")


def _default_trace_id(source: str, message_id: str) -> str:
    suffix = _clean_token(message_id) if message_id else uuid.uuid4().hex[:12]
    return f"{source}-{suffix}"


def _clean_token(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(value or "").strip()).strip("_")


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _attachment_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(dict(item))
        elif str(item).strip():
            result.append({"raw": str(item).strip()})
    return result
