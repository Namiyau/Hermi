import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class CaptureHermes:
    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append(messages)
        return "ok"


def test_owner_can_read_recent_qq_context_api(tmp_path: Path):
    log_dir = tmp_path / "qlos_logs"
    log_dir.mkdir()
    payload = {
        "post_type": "message",
        "message_type": "private",
        "user_id": 1000000001,
        "raw_message": "recent private qq",
    }
    (log_dir / "gateway_http.jsonl").write_text(
        json.dumps({"body_preview": json.dumps(payload, ensure_ascii=False)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        qlos_log_dir=log_dir,
    )
    client = TestClient(create_app(config))

    response = client.get("/qq/recent", headers={"Authorization": "Bearer owner-token"})

    assert response.status_code == 200
    assert "recent private qq" in response.json()["context"]


def test_hermi_prompt_says_recent_qq_context_is_visible_when_present(tmp_path: Path):
    log_dir = tmp_path / "qlos_logs"
    log_dir.mkdir()
    payload = {
        "post_type": "message",
        "message_type": "group",
        "group_id": 2000000001,
        "user_id": 123,
        "raw_message": "group synced message",
    }
    (log_dir / "gateway_http.jsonl").write_text(
        json.dumps({"body_preview": json.dumps(payload, ensure_ascii=False)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hermes = CaptureHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        qlos_log_dir=log_dir,
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", json={"title": "Main"}, headers=headers).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        json={"content": "看看 QQ 最近有什么"},
        headers=headers,
    )

    merged = "\n".join(str(message["content"]) for message in hermes.calls[0])
    assert "group synced message" in merged
    assert "synced recent QQ context" in merged
    assert "Do not say you cannot see QQ if context is provided" in merged


def test_friend_cannot_inject_owner_recent_qq_context_into_prompt(tmp_path: Path):
    log_dir = tmp_path / "qlos_logs"
    log_dir.mkdir()
    payload = {
        "post_type": "message",
        "message_type": "private",
        "user_id": 1000000001,
        "raw_message": "owner private secret",
    }
    (log_dir / "gateway_http.jsonl").write_text(
        json.dumps({"body_preview": json.dumps(payload, ensure_ascii=False)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hermes = CaptureHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        qlos_log_dir=log_dir,
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    owner = {"Authorization": "Bearer owner-token"}
    friend = {"Authorization": "Bearer friend-token"}
    client.post(
        "/admin/users",
        headers=owner,
        json={
            "user_id": "friend:qq-context",
            "display_name": "Friend",
            "token": "friend-token",
            "permissions": {"chat": "allow"},
        },
    )
    conversation = client.post("/conversations", headers=friend, json={"title": "Friend"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "看看 QQ 最近有什么消息"},
    )
    merged = "\n".join(str(message["content"]) for message in hermes.calls[0])

    assert response.status_code == 200
    assert "owner private secret" not in merged
    assert "[recent_qq_context]" not in merged

