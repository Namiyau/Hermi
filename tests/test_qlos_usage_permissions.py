import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class QlosUsageAdapter:
    def __init__(self) -> None:
        self.last_usage = {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12}

    def chat_profile(self, profile_id, messages, session_id, session_key):
        return "QLOS reply"


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=QlosUsageAdapter()))


def _qq_event(*, attachments=None) -> dict:
    return {
        "message_id": "qq-usage-1",
        "chat_type": "private",
        "user_id": "qq-user",
        "text": "hello from QQ",
        "attachments": attachments or [],
        "sender_role": "friend",
        "session_id": "qlos-usage-session",
        "session_key": "qlos:usage:session",
    }


def test_qlos_permissions_are_visible_enforced_and_usage_is_recorded(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    channel_headers = {"Authorization": "Bearer channel-token"}

    listed = client.get("/admin/users", headers=owner_headers).json()["users"]
    qlos = next(user for user in listed if user["user_id"] == "channel:qlos")
    assert qlos["permission_summary"]["chat"] == "allow"
    assert qlos["permission_summary"]["media"] == "allow"

    accepted = client.post("/channels/qq/events", headers=channel_headers, json=_qq_event())
    assert accepted.status_code == 200
    usage = client.get("/usage/channel:qlos?period=all", headers=owner_headers).json()["usage"]
    assert usage[0]["text_messages"] == 1
    assert usage[0]["total_tokens"] == 12

    client.patch("/admin/users/channel:qlos", headers=owner_headers, json={"permissions": {"chat": "deny"}})
    denied_chat = client.post("/channels/qq/events", headers=channel_headers, json={**_qq_event(), "message_id": "qq-usage-2"})
    assert denied_chat.status_code == 403
    assert denied_chat.json()["detail"] == "permission_denied:chat"

    client.patch(
        "/admin/users/channel:qlos",
        headers=owner_headers,
        json={"permissions": {"chat": "allow", "media": {"mode": "deny"}}},
    )
    denied_media = client.post(
        "/channels/qq/events",
        headers=channel_headers,
        json=_qq_event(attachments=["image:C:/temp/example.png"]),
    )
    assert denied_media.status_code == 403
    assert denied_media.json()["detail"] == "permission_denied:media"

    oversized = tmp_path / "oversized.png"
    oversized.write_bytes(b"x" * (1024 * 1024 + 1))
    client.patch(
        "/admin/users/channel:qlos",
        headers=owner_headers,
        json={"permissions": {"media": {"mode": "allow", "max_size_mb": 1}}},
    )
    denied_size = client.post(
        "/channels/qq/events",
        headers=channel_headers,
        json={**_qq_event(attachments=[f"image:{oversized}"],), "message_id": "qq-usage-3"},
    )
    assert denied_size.status_code == 413
    assert denied_size.json()["detail"] == "media_file_too_large"


def test_owner_qq_reminder_creates_hermi_job_that_returns_to_same_qq(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    channel_headers = {"Authorization": "Bearer channel-token"}

    created = client.post(
        "/channels/qq/events",
        headers=channel_headers,
        json={
            **_qq_event(),
            "message_id": "qq-owner-reminder",
            "user_id": "owner-qq",
            "sender_role": "owner",
            "text": "1分钟后提醒我开始做计划",
        },
    )

    assert created.status_code == 200
    jobs = client.get("/scheduled-jobs", headers=owner_headers).json()["scheduled_jobs"]
    assert len(jobs) == 1
    target = json.loads(jobs[0]["target_json"])
    assert target["delivery"] == ["hermi", "qq"]
    assert target["qq"] == {"chat_type": "private", "user_id": "owner-qq"}
