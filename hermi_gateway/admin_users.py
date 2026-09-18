from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from .db import upsert_user
from .permissions import PermissionChecker, _upgrade_legacy_quota_permissions


PROFILE_FIELDS = ("relationship", "preferences", "recent_focus")


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    public = {key: value for key, value in user.items() if key != "token"}
    public["permissions"] = permissions_dict(public.get("permissions"))
    checker = PermissionChecker(public)
    public["effective_permissions"] = checker.to_dict()
    if public.get("role") in {"friend", "guest"}:
        public["permission_summary"] = {
            key: checker.check(key)
            for key in ("chat", "cron", "manage_scheduled")
        }
    elif public.get("role") == "channel":
        public["permission_summary"] = {
            key: checker.check(key)
            for key in ("chat", "media", "cron", "manage_scheduled")
        }
    return public


def permissions_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return _upgrade_legacy_quota_permissions(value)
    if not value:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return _upgrade_legacy_quota_permissions(parsed) if isinstance(parsed, dict) else {}
    return {}


def permissions_to_db(value: Any) -> str:
    permissions = permissions_dict(value)
    return json.dumps(permissions, ensure_ascii=False) if permissions else ""


def merge_permission_patch(current: Any, patch: Any) -> str:
    if patch is None:
        return permissions_to_db(current)
    merged = permissions_dict(current)
    incoming = permissions_dict(patch)
    if not incoming and patch in ("", {}):
        return ""
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    if "quota_token_limit" in incoming:
        merged.pop("daily_text_limit", None)
    return permissions_to_db(merged)


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("select * from users order by created_at asc").fetchall()
    return [public_user(dict(row)) for row in rows]


def get_user(conn: sqlite3.Connection, user_id: str) -> dict[str, Any] | None:
    row = conn.execute("select * from users where user_id = ?", (user_id,)).fetchone()
    return public_user(dict(row)) if row else None


def create_user(conn: sqlite3.Connection, body: Any) -> tuple[dict[str, Any], str | None]:
    token = str(body.token or "").strip() or f"hermi-{uuid.uuid4().hex}"
    role = str(body.role or "friend")
    upsert_user(
        conn,
        user_id=body.user_id,
        display_name=body.display_name,
        role=role,
        token=token,
        can_approve=body.can_approve if role == "owner" else False,
        can_remote_control=body.can_remote_control if role == "owner" else False,
        quota_policy=body.quota_policy or ("owner" if role == "owner" else "friend_free"),
        # Keep omitted permissions empty so deployment-level defaults (for example
        # token and file limits from HermiConfig) remain effective. Explicit panel
        # changes are still stored and take precedence later.
        permissions=permissions_to_db(body.permissions),
    )
    created = get_user(conn, body.user_id)
    if created is None:
        raise RuntimeError("created user could not be reloaded")
    generated_token = token if not str(body.token or "").strip() else None
    return created, generated_token


def update_user(conn: sqlite3.Connection, user_id: str, body: Any) -> dict[str, Any] | None:
    existing = conn.execute("select * from users where user_id = ?", (user_id,)).fetchone()
    if not existing:
        return None
    current = dict(existing)
    values = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body.dict(exclude_unset=True)
    role = str(values.get("role", current["role"]))
    permissions = (
        merge_permission_patch(current.get("permissions"), values["permissions"])
        if "permissions" in values
        else current.get("permissions", "")
    )
    upsert_user(
        conn,
        user_id=user_id,
        display_name=values.get("display_name", current["display_name"]),
        role=role,
        token=values.get("token") or current["token"],
        can_approve=bool(values.get("can_approve", current["can_approve"])) if role == "owner" else False,
        can_remote_control=bool(values.get("can_remote_control", current["can_remote_control"]))
        if role == "owner"
        else False,
        quota_policy=values.get("quota_policy", current["quota_policy"]),
        permissions=permissions,
    )
    return get_user(conn, user_id)


def delete_user(conn: sqlite3.Connection, user_id: str, current_user_id: str) -> dict[str, Any] | None:
    if user_id == current_user_id:
        raise ValueError("cannot_delete_current_user")
    existing = conn.execute("select * from users where user_id = ?", (user_id,)).fetchone()
    if not existing:
        return None
    if existing["role"] not in {"friend", "guest"}:
        raise ValueError("cannot_delete_system_user")
    conn.execute("delete from users where user_id = ?", (user_id,))
    return public_user(dict(existing))


def get_user_profile(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    row = conn.execute("select * from user_profiles where user_id = ?", (user_id,)).fetchone()
    if not row:
        return {"user_id": user_id, "relationship": "", "preferences": "", "recent_focus": "", "revision": 0, "updated_at": 0}
    return dict(row)


def update_user_profile_field(conn: sqlite3.Connection, user_id: str, field: str, value: str) -> dict[str, Any]:
    if field not in PROFILE_FIELDS:
        raise ValueError("invalid_profile_field")
    profile = get_user_profile(conn, user_id)
    clean_value = str(value or "").strip()
    if profile[field] == clean_value:
        return profile
    revision = int(profile["revision"]) + 1
    now = time.time()
    profile[field] = clean_value
    profile["revision"] = revision
    profile["updated_at"] = now
    conn.execute(
        """
        insert into user_profiles (user_id, relationship, preferences, recent_focus, revision, updated_at)
        values (?, ?, ?, ?, ?, ?)
        on conflict(user_id) do update set
          relationship = excluded.relationship,
          preferences = excluded.preferences,
          recent_focus = excluded.recent_focus,
          revision = excluded.revision,
          updated_at = excluded.updated_at
        """,
        (user_id, profile["relationship"], profile["preferences"], profile["recent_focus"], revision, now),
    )
    return profile


def pending_user_profile_context(conn: sqlite3.Connection, user_id: str, conversation_id: str) -> tuple[str, int]:
    profile = get_user_profile(conn, user_id)
    revision = int(profile["revision"])
    if revision <= 0 or not any(str(profile[field]).strip() for field in PROFILE_FIELDS):
        return "", 0
    injected = conn.execute(
        "select revision from user_profile_injections where conversation_id = ? and user_id = ?",
        (conversation_id, user_id),
    ).fetchone()
    if injected and int(injected["revision"]) >= revision:
        return "", 0
    labels = {"relationship": "relationship", "preferences": "preferences", "recent_focus": "recent focus"}
    details = [f"{labels[field]}: {profile[field]}" for field in PROFILE_FIELDS if str(profile[field]).strip()]
    return (
        "[Hermi owner-curated user private background]\n"
        "This is private background, not a script or a topic to introduce. "
        "Do not list, quote, or volunteer any of it. Do not say it came from the owner. "
        "Do not use it in the first reply unless the user clearly invites relaxed open-ended chat. "
        "Use at most one relevant detail only when the user independently raises that subject or invites relaxed open-ended chat. "
        "Never use it merely to sound familiar, and never turn an identity question or unrelated question into this profile's topic. "
        "Never use it to redirect an unrelated question, identity question, task, or concern.\n"
        + "\n".join(details),
        revision,
    )


def mark_user_profile_context_injected(conn: sqlite3.Connection, user_id: str, conversation_id: str, revision: int) -> None:
    if revision <= 0:
        return
    conn.execute(
        """
        insert into user_profile_injections (conversation_id, user_id, revision, injected_at)
        values (?, ?, ?, ?)
        on conflict(conversation_id, user_id) do update set
          revision = excluded.revision,
          injected_at = excluded.injected_at
        """,
        (conversation_id, user_id, revision, time.time()),
    )
