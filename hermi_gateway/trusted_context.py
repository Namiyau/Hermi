"""Verification and local handoff for QLOS-authenticated memory context."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CONTEXT_VERSION = 1
DEFAULT_CONTEXT_TTL_SECONDS = 15 * 60


def build_hermi_web_context(
    channel_token: str,
    *,
    user_id: str,
    session_id: str,
    session_key: str,
    role: str,
    now: int | float | None = None,
) -> dict[str, Any]:
    """Build Hermi-originated, hash-only context for one authenticated Web user."""
    if not str(channel_token or "").strip() or not str(user_id or "").strip():
        raise ValueError("channel token and user id are required")
    issued_at = int(time.time() if now is None else now)
    key = str(channel_token).encode("utf-8")
    return {
        "version": CONTEXT_VERSION,
        "platform": "hermi_web",
        "chat_type": "private",
        "subject_id_hash": _bound_hash(key, f"hermi:web:user:{user_id}"),
        "group_id_hash": "",
        "is_owner": str(role or "") == "owner",
        "sender_role": str(role or "friend"),
        "expires_at": issued_at + DEFAULT_CONTEXT_TTL_SECONDS,
        "session_id_hash": _bound_hash(key, f"session:id:{session_id}"),
        "session_key_hash": _bound_hash(key, f"session:key:{session_key}"),
    }


def verify_qq_context(
    context: Any,
    channel_token: str,
    *,
    session_id: str,
    session_key: str,
    user_id: str,
    group_id: str | None,
    chat_type: str,
    sender_role: str,
    now: int | float | None = None,
) -> dict[str, Any] | None:
    """Verify QLOS context against its authenticated event payload."""
    if not isinstance(context, dict) or not str(channel_token or "").strip():
        return None
    key = str(channel_token).encode("utf-8")
    signature = str(context.get("signature") or "")
    payload = {name: value for name, value in context.items() if name != "signature"}
    if not signature or not hmac.compare_digest(signature, _sign(payload, key)):
        return None
    current = int(time.time() if now is None else now)
    if payload.get("version") != CONTEXT_VERSION or payload.get("platform") != "qq":
        return None
    if payload.get("chat_type") != chat_type or payload.get("sender_role") != sender_role:
        return None
    if not isinstance(payload.get("issued_at"), int) or not isinstance(payload.get("expires_at"), int):
        return None
    if payload["expires_at"] <= current or payload["issued_at"] > current + 60:
        return None
    expected = {
        "subject_id_hash": _bound_hash(key, f"qq:user:{user_id}"),
        "session_id_hash": _bound_hash(key, f"session:id:{session_id}"),
        "session_key_hash": _bound_hash(key, f"session:key:{session_key}"),
    }
    if chat_type == "group":
        if not group_id:
            return None
        expected["group_id_hash"] = _bound_hash(key, f"qq:group:{group_id}")
    elif str(payload.get("group_id_hash") or ""):
        return None
    for name, value in expected.items():
        if not hmac.compare_digest(str(payload.get(name) or ""), value):
            return None
    if bool(payload.get("is_owner")) != (sender_role == "owner"):
        return None
    return {
        "version": CONTEXT_VERSION,
        "platform": "qq",
        "chat_type": chat_type,
        "subject_id_hash": expected["subject_id_hash"],
        "group_id_hash": expected.get("group_id_hash", ""),
        "is_owner": bool(payload["is_owner"]),
        "sender_role": sender_role,
        "expires_at": payload["expires_at"],
    }


def write_trusted_session_context(directory: Path | str, session_id: str, context: dict[str, Any]) -> Path:
    """Atomically save the verified, hash-only context at a non-raw session locator."""
    root = Path(directory)
    locator = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    record = {**context, "session_locator": locator}
    path = root / f"{locator}.json"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=root, newline="\n") as handle:
        json.dump(record, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return path


def ensure_hermi_subject_page(
    directory: Path | str,
    profile: str,
    context: dict[str, Any],
    *,
    memory_source_root: Path | str | None = None,
) -> bool:
    """Idempotently create the Hermi caller's hash-only Chinese person page.

    Hermes Runs API sessions may replace a client session id internally, which
    prevents a plugin hook from finding its sidecar.  Hermi is the trusted
    server that created this context, so it provides a narrow fallback using
    the same MemoryVault implementation as the native plugin.
    """
    if context.get("platform") != "hermi_web" or context.get("chat_type") != "private":
        return False
    subject_hash = str(context.get("subject_id_hash") or "")
    if len(subject_hash) != 64 or any(char not in "0123456789abcdef" for char in subject_hash):
        return False
    vault_root = Path(directory).resolve().parent.parent
    source_root = Path(memory_source_root) if memory_source_root is not None else vault_root.parent / "src"
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    try:
        from hermes_memory.vault import MemoryVault
        vault = MemoryVault.initialize(vault_root)
        vault.cleanup_expired_hypotheses(profile=str(profile))
        vault.ensure_subject(
            profile=str(profile),
            subject_key=f"hermi_web:{subject_hash}",
            display_name=f"Hermi朋友-{subject_hash[-6:]}",
            source_platform="hermi_web",
        )
    except (ImportError, OSError, ValueError):
        return False
    return True


def _bound_hash(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _sign(payload: dict[str, Any], key: bytes) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(key, encoded, hashlib.sha256).hexdigest()
