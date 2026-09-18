from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class QuietAdapter:
    last_usage = {}

    def chat(self, messages, session_id, session_key):
        return "unused"

    def stream_events(self, messages, session_id, session_key):
        yield {"event": "final", "content": "unused"}


def _client(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=QuietAdapter()))
    owner = {"Authorization": "Bearer owner-token"}
    friend = {"Authorization": "Bearer friend-token"}
    created = client.post(
        "/admin/users",
        headers=owner,
        json={
            "user_id": "friend:quota",
            "display_name": "Quota friend",
            "token": "friend-token",
            "permissions": {"quota_token_limit": 1000, "quota_window_minutes": 60},
        },
    )
    assert created.status_code == 200
    return client, owner, friend


def test_temporary_quota_request_requires_owner_approval_and_raises_current_window_limit(tmp_path: Path):
    client, owner, friend = _client(tmp_path)

    initial = client.get("/my/summary", headers=friend).json()["quota_window"]
    requested = client.post("/my/quota-requests", headers=friend)
    duplicate = client.post("/my/quota-requests", headers=friend)
    mine = client.get("/approvals", headers=friend).json()["approvals"]

    assert initial["token_limit"] == 1000
    assert requested.status_code == 201
    assert requested.json()["action_type"] == "quota.temporary.grant"
    assert requested.json()["status"] == "pending"
    assert duplicate.status_code == 409
    assert [approval["approval_id"] for approval in mine] == [requested.json()["approval_id"]]

    decided = client.post(
        f"/approvals/{requested.json()['approval_id']}/decision",
        headers=owner,
        json={"decision": "once"},
    )
    summary = client.get("/my/summary", headers=friend).json()["quota_window"]
    approval = next(
        item for item in client.get("/approvals", headers=friend).json()["approvals"]
        if item["approval_id"] == requested.json()["approval_id"]
    )
    notification = client.app.state.db.execute(
        "select kind, title, message from user_notices where user_id = ? order by created_at desc limit 1",
        ("friend:quota",),
    ).fetchone()
    reminder = client.app.state.db.execute(
        "select 1 from messages where conversation_id = ? and content like '临时额度申请已批准%'",
        (requested.json()["conversation_id"],),
    ).fetchone()

    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert summary["token_limit"] == 101000
    assert summary["temporary_granted_tokens"] == 100000
    assert approval["status"] == "approved"
    assert notification["kind"] == "quota.temporary.grant.approved"
    assert "100,000 Token" in notification["message"]
    assert reminder is None


def test_owner_cannot_request_temporary_quota(tmp_path: Path):
    client, owner, _ = _client(tmp_path)

    response = client.post("/my/quota-requests", headers=owner)

    assert response.status_code == 403
    assert response.json()["detail"] == "temporary_quota_not_available"


def test_temporary_quota_denial_is_visible_to_the_requesting_user(tmp_path: Path):
    client, owner, friend = _client(tmp_path)

    requested = client.post("/my/quota-requests", headers=friend).json()
    denied = client.post(
        f"/approvals/{requested['approval_id']}/decision",
        headers=owner,
        json={"decision": "deny"},
    )
    approval = next(
        item for item in client.get("/approvals", headers=friend).json()["approvals"]
        if item["approval_id"] == requested["approval_id"]
    )
    notification = client.app.state.db.execute(
        "select kind from user_notices where user_id = ? order by created_at desc limit 1",
        ("friend:quota",),
    ).fetchone()

    assert denied.status_code == 200
    assert approval["status"] == "denied"
    assert notification["kind"] == "quota.temporary.grant.denied"
