from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import _ensure_quota_window, _quota_window_bounds, create_app
from hermi_gateway.config import HermiConfig


class FakeHermesAdapter:
    last_usage = {"total_tokens": 1}

    def chat(self, messages, session_id, session_key):
        return "assistant reply"


class TokenMeteredHermesAdapter(FakeHermesAdapter):
    last_usage = {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}


class FiveTokenHermesAdapter(FakeHermesAdapter):
    last_usage = {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}


def _client(tmp_path: Path, *, friend_token_limit: int = 50_000, friend_file_size_limit: int = 1024) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        friend_token_limit=friend_token_limit,
        friend_file_size_limit=friend_file_size_limit,
    )
    return TestClient(create_app(config, hermes_adapter=FakeHermesAdapter()))


def test_owner_can_create_and_update_friend_user(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}

    created = client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:alice",
            "display_name": "Alice",
            "role": "friend",
            "token": "alice-token",
            "quota_policy": "friend_free",
        },
    )
    friend_me = client.get("/me", headers={"Authorization": "Bearer alice-token"})
    patched = client.patch(
        "/admin/users/friend:alice",
        headers=owner_headers,
        json={"display_name": "Alice Trusted", "quota_policy": "friend_trusted"},
    )
    listed = client.get("/admin/users", headers=owner_headers)

    assert created.status_code == 200
    assert created.json()["role"] == "friend"
    assert "token" not in created.json()
    assert friend_me.status_code == 200
    assert friend_me.json()["quota_policy"] == "friend_free"
    assert patched.status_code == 200
    assert patched.json()["display_name"] == "Alice Trusted"
    assert patched.json()["quota_policy"] == "friend_trusted"
    assert "friend:alice" in [item["user_id"] for item in listed.json()["users"]]


def test_owner_can_delete_friend_user_but_not_self(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:delete-me",
            "display_name": "Delete Me",
            "role": "friend",
            "token": "delete-token",
            "quota_policy": "friend_free",
        },
    )

    deleted = client.delete("/admin/users/friend:delete-me", headers=owner_headers)
    listed = client.get("/admin/users", headers=owner_headers)
    delete_self = client.delete("/admin/users/owner", headers=owner_headers)
    delete_channel = client.delete("/admin/users/channel:qlos", headers=owner_headers)

    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert "friend:delete-me" not in [item["user_id"] for item in listed.json()["users"]]
    assert delete_self.status_code == 400
    assert delete_self.json()["detail"] == "cannot_delete_current_user"
    assert delete_channel.status_code == 400
    assert delete_channel.json()["detail"] == "cannot_delete_system_user"


def test_owner_user_detail_route_accepts_colon_user_id(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:permission-detail",
            "display_name": "Permission Detail",
            "role": "friend",
            "token": "permission-detail-token",
        },
    )

    response = client.get("/admin/users/friend%3Apermission-detail", headers=owner_headers)

    assert response.status_code == 200
    assert response.json()["user_id"] == "friend:permission-detail"


def test_owner_can_store_and_read_friend_permissions_json(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    permissions = {
        "chat": "allow",
        "cron": "approval",
        "quota_token_limit": 42_000,
        "media": {"mode": "allow", "max_size_mb": 9, "daily_vision_count": 3},
    }

    created = client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:perms",
            "display_name": "Perms",
            "role": "friend",
            "token": "perms-token",
            "quota_policy": "friend_free",
            "permissions": permissions,
        },
    )
    detail = client.get("/admin/users/friend:perms", headers=owner_headers)
    patched = client.patch(
        "/admin/users/friend:perms",
        headers=owner_headers,
        json={"permissions": {"cron": "deny", "quota_token_limit": 7_000}},
    )
    patched_detail = client.get("/admin/users/friend:perms", headers=owner_headers)

    assert created.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["permissions"] == permissions
    assert patched.status_code == 200
    assert patched_detail.json()["permissions"]["chat"] == "allow"
    assert patched_detail.json()["permissions"]["cron"] == "deny"
    assert patched_detail.json()["permissions"]["quota_token_limit"] == 7_000
    assert patched_detail.json()["permissions"]["media"]["max_size_mb"] == 9


def test_friend_cron_approval_creates_scheduled_approval_then_owner_decision_creates_job(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    permissions = {"chat": "allow", "cron": "approval", "manage_scheduled": "allow"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:cron",
            "display_name": "Cron",
            "role": "friend",
            "token": "cron-token",
            "quota_policy": "friend_free",
            "permissions": permissions,
        },
    )
    friend_headers = {"Authorization": "Bearer cron-token"}

    requested = client.post(
        "/scheduled-jobs",
        headers=friend_headers,
        json={
            "kind": "once",
            "schedule": "once:+5m",
            "summary": "friend reminder",
            "target": {"delivery": ["hermi"]},
            "payload": {"content": "remind me to check permissions"},
        },
    )
    approvals = client.get("/approvals", headers=owner_headers).json()["approvals"]
    decided = client.post(
        f"/approvals/{approvals[0]['approval_id']}/decision",
        headers=owner_headers,
        json={"decision": "once"},
    )
    jobs = client.get("/scheduled-jobs", headers=owner_headers).json()["scheduled_jobs"]

    assert requested.status_code == 200
    assert requested.json()["status"] == "pending_approval"
    assert approvals[0]["action_type"] == "scheduled.create"
    assert approvals[0]["source"] == "permission"
    assert decided.status_code == 200
    assert jobs[0]["summary"] == "friend reminder"
    assert jobs[0]["created_by"] == "friend:cron"


def test_friend_cannot_admin_or_decide_approval_or_read_owner_qq_context(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:bob", "display_name": "Bob", "token": "bob-token"},
    )
    friend_headers = {"Authorization": "Bearer bob-token"}

    assert client.get("/admin/users", headers=friend_headers).status_code == 403
    assert client.get("/approvals", headers=friend_headers).status_code == 200
    assert client.post("/approvals/app-1/decision", headers=friend_headers, json={"decision": "once"}).status_code == 403
    assert client.get("/qq/recent", headers=friend_headers).status_code == 403


def test_friend_can_read_capabilities_but_cannot_validate_actions(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:capability", "display_name": "Capability", "token": "capability-token"},
    )
    friend_headers = {"Authorization": "Bearer capability-token"}

    capabilities = client.get("/capabilities", headers=friend_headers)
    validate = client.post("/actions/validate", headers=friend_headers, json={"type": "qq.send"})

    assert capabilities.status_code == 200
    assert capabilities.json()["capabilities"]
    assert validate.status_code == 403


def test_friend_sees_only_own_approval_records(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    permissions = {"chat": "allow", "cron": "approval", "manage_scheduled": "allow"}
    for user_id, token in (("friend:alice", "alice-token"), ("friend:bob", "bob-token")):
        client.post(
            "/admin/users",
            headers=owner_headers,
            json={
                "user_id": user_id,
                "display_name": user_id,
                "role": "friend",
                "token": token,
                "permissions": permissions,
            },
        )
        response = client.post(
            "/scheduled-jobs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "kind": "once",
                "schedule": "once:+5m",
                "summary": f"{user_id} reminder",
                "target": {"delivery": ["hermi"]},
                "payload": {"content": "approval visibility"},
            },
        )
        assert response.json()["status"] == "pending_approval"

    alice_approvals = client.get("/approvals", headers={"Authorization": "Bearer alice-token"})

    assert alice_approvals.status_code == 200
    assert len(alice_approvals.json()["approvals"]) == 1
    assert "friend:alice reminder" in alice_approvals.json()["approvals"][0]["summary"]


def test_friend_only_sees_own_conversations(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    owner_conv = client.post("/conversations", headers=owner_headers, json={"title": "owner private"}).json()
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:scope", "display_name": "Scope", "token": "scope-token"},
    )
    friend_headers = {"Authorization": "Bearer scope-token"}
    friend_conv = client.post("/conversations", headers=friend_headers, json={"title": "friend chat"}).json()

    friend_list = client.get("/conversations", headers=friend_headers).json()["conversations"]
    owner_message_read = client.get(
        f"/conversations/{owner_conv['conversation_id']}/messages",
        headers=friend_headers,
    )
    friend_message_read = client.get(
        f"/conversations/{friend_conv['conversation_id']}/messages",
        headers=friend_headers,
    )

    assert [item["conversation_id"] for item in friend_list] == [friend_conv["conversation_id"]]
    assert owner_message_read.status_code == 404
    assert friend_message_read.status_code == 200


def test_friend_token_quota_is_enforced(tmp_path: Path):
    client = _client(tmp_path, friend_token_limit=1)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:quota", "display_name": "Quota", "token": "quota-token"},
    )
    friend_headers = {"Authorization": "Bearer quota-token"}
    conv = client.post("/conversations", headers=friend_headers, json={"title": "quota"}).json()

    first = client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "first"},
    )
    second = client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "second"},
    )
    usage = client.get("/usage", headers=owner_headers).json()["usage"]

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "token_quota_exceeded"
    assert any(row["user_id"] == "friend:quota" and row["text_messages"] == 1 for row in usage)


def test_friend_quota_window_is_reported_and_enforced(tmp_path: Path):
    client = _client(tmp_path, friend_token_limit=99)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:window",
            "display_name": "Window",
            "token": "window-token",
            "permissions": {"quota_token_limit": 1, "quota_window_minutes": 60},
        },
    )
    friend_headers = {"Authorization": "Bearer window-token"}
    conv = client.post("/conversations", headers=friend_headers, json={"title": "window"}).json()

    first = client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "first"},
    )
    second = client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "second"},
    )
    usage = client.get("/usage/friend:window", headers=owner_headers).json()

    assert first.status_code == 200
    assert second.status_code == 429
    assert usage["quota_window"]["window_minutes"] == 60
    assert usage["quota_window"]["total_tokens"] == 1
    assert usage["quota_window"]["token_limit"] == 1
    assert usage["quota_window"]["remaining_seconds"] > 0


def test_friend_token_quota_is_enforced_and_exposed_in_personal_summary(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        friend_token_limit=12,
    )
    client = TestClient(create_app(config, hermes_adapter=TokenMeteredHermesAdapter()))
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:token-window", "display_name": "Token window", "token": "token-window-token"},
    )
    friend_headers = {"Authorization": "Bearer token-window-token"}
    conversation = client.post("/conversations", headers=friend_headers, json={"title": "token quota"}).json()

    first = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "first"},
    )
    second = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "second"},
    )
    usage = client.get("/usage/friend:token-window", headers=owner_headers).json()["quota_window"]
    summary = client.get("/my/summary", headers=friend_headers).json()

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"] == "token_quota_exceeded"
    assert usage["total_tokens"] == 12
    assert usage["token_limit"] == 12
    assert usage["remaining_tokens"] == 0
    assert summary["quota_window"]["usage_percent"] == 100


def test_token_quota_allows_the_started_turn_to_run_over_and_carries_only_the_debt(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        friend_token_limit=100,
    )
    client = TestClient(create_app(config, hermes_adapter=FiveTokenHermesAdapter()))
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:debt",
            "display_name": "Quota debt",
            "token": "quota-debt-token",
            "permissions": {"quota_token_limit": 100, "quota_window_minutes": 1},
        },
    )
    friend_headers = {"Authorization": "Bearer quota-debt-token"}
    conversation = client.post("/conversations", headers=friend_headers, json={"title": "quota debt"}).json()
    conn = client.app.state.db
    user = dict(conn.execute("select * from users where user_id = ?", ("friend:debt",)).fetchone())
    now = __import__("time").time()
    start, end, _ = _quota_window_bounds(user, now)
    conn.execute(
        """
        insert into usage_windows (
          window_key, user_id, window_start_at, window_end_at, text_messages, file_uploads, total_tokens
        ) values (?, ?, ?, ?, 0, 0, 99)
        """,
        (f"friend:debt:{int(start)}", "friend:debt", start, end),
    )
    conn.commit()

    completed = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "finish this turn"},
    )
    quota = client.get("/usage/friend:debt", headers=owner_headers).json()["quota_window"]
    blocked = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "do not start another turn"},
    )

    assert completed.status_code == 200
    assert quota["total_tokens"] == 104
    assert quota["remaining_tokens"] == -4
    assert quota["remaining_percent"] == -4
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "token_quota_exceeded"
    assert int(blocked.headers["Retry-After"]) > 0

    next_window = _ensure_quota_window(conn, user, config, now=end + 0.1)
    assert next_window["total_tokens"] == 4
    conn.execute("update usage_windows set total_tokens = 50 where window_key = ?", (next_window["window_key"],))
    conn.commit()
    later_start, later_end, _ = _quota_window_bounds(user, end + 60.1)
    reset_window = _ensure_quota_window(conn, user, config, now=later_start + 0.1)

    assert later_end > later_start
    assert reset_window["total_tokens"] == 0


def test_expired_pending_approval_is_automatically_denied(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=owner_headers, json={"title": "approval"}).json()
    created = client.post(
        "/proactive/drafts",
        headers=owner_headers,
        json={"conversation_id": conv["conversation_id"], "kind": "summary", "summary": "expire me"},
    ).json()
    client.app.state.db.execute(
        "update approvals set expires_at = ? where approval_id = ?",
        (0, created["approval_id"]),
    )
    client.app.state.db.commit()

    approvals = client.get("/approvals", headers=owner_headers).json()["approvals"]

    expired = next(item for item in approvals if item["approval_id"] == created["approval_id"])
    assert expired["status"] == "denied"
    assert expired["decision"] == "expired"


def test_admin_user_permission_summary_uses_allow_deny_and_approval(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:summary",
            "display_name": "Summary",
            "token": "summary-token",
            "permissions": {"chat": "allow", "cron": "approval", "manage_scheduled": "deny"},
        },
    )

    users = client.get("/admin/users", headers=owner_headers).json()["users"]
    summary = next(user for user in users if user["user_id"] == "friend:summary")["permission_summary"]

    assert summary == {"chat": "allow", "cron": "approval", "manage_scheduled": "deny"}


def test_owner_can_read_usage_for_one_user(tmp_path: Path):
    client = _client(tmp_path, friend_token_limit=5)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:usage", "display_name": "Usage", "token": "usage-token"},
    )
    friend_headers = {"Authorization": "Bearer usage-token"}
    conv = client.post("/conversations", headers=friend_headers, json={"title": "usage"}).json()
    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=friend_headers,
        json={"content": "hello usage"},
    )

    response = client.get("/usage/friend:usage", headers=owner_headers)
    own_usage = client.get("/usage/friend:usage", headers=friend_headers)
    other_usage = client.get("/usage/friend:someone-else", headers=friend_headers)

    assert response.status_code == 200
    assert response.json()["user_id"] == "friend:usage"
    assert response.json()["usage"][0]["text_messages"] == 1
    assert own_usage.status_code == 200
    assert other_usage.status_code == 403


def test_usage_period_filters_limit_owner_and_friend_history(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:period", "display_name": "Period", "token": "period-token"},
    )
    today = date.today()
    rows = [
        ((today - timedelta(days=0)).isoformat(), 1),
        ((today - timedelta(days=6)).isoformat(), 2),
        ((today - timedelta(days=7)).isoformat(), 3),
        ((today - timedelta(days=29)).isoformat(), 4),
        ((today - timedelta(days=30)).isoformat(), 5),
    ]
    client.app.state.db.executemany(
        "insert into usage_daily (day, user_id, text_messages, file_uploads, total_tokens) values (?, 'friend:period', ?, 0, 0)",
        rows,
    )
    client.app.state.db.commit()

    owner_seven = client.get("/usage?period=7d", headers=owner_headers)
    owner_thirty = client.get("/usage?period=30d", headers=owner_headers)
    friend_all = client.get("/usage/friend:period?period=all", headers={"Authorization": "Bearer period-token"})

    assert [item["text_messages"] for item in owner_seven.json()["usage"]] == [1, 2]
    assert [item["text_messages"] for item in owner_thirty.json()["usage"]] == [1, 2, 3, 4]
    assert [item["text_messages"] for item in friend_all.json()["usage"]] == [1, 2, 3, 4, 5]
    assert client.get("/usage?period=invalid", headers=owner_headers).status_code == 422


def test_friend_can_read_own_usage_even_when_legacy_view_stats_is_denied(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:own-usage",
            "display_name": "Own Usage",
            "token": "own-usage-token",
            "permissions": {"view_stats": "deny"},
        },
    )

    response = client.get(
        "/usage/friend:own-usage",
        headers={"Authorization": "Bearer own-usage-token"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "friend:own-usage"


def test_friend_file_upload_size_limit_is_enforced(tmp_path: Path):
    client = _client(tmp_path, friend_file_size_limit=4)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:file", "display_name": "File", "token": "file-token"},
    )
    friend_headers = {"Authorization": "Bearer file-token"}

    response = client.post(
        "/files",
        headers=friend_headers,
        files={"upload": ("big.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "file_quota_exceeded"
