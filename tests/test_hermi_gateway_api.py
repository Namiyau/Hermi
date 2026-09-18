from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class FakeHermesAdapter:
    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append((messages, session_id, session_key))
        return "assistant reply"


def _client(tmp_path: Path, adapter=None) -> TestClient:
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    return TestClient(create_app(config, hermes_adapter=adapter))


def test_health_is_public(tmp_path: Path):
    client = _client(tmp_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_me_requires_token_and_returns_owner(tmp_path: Path):
    client = _client(tmp_path)

    assert client.get("/me").status_code == 401

    response = client.get("/me", headers={"Authorization": "Bearer owner-token"})

    assert response.status_code == 200
    assert response.json()["role"] == "owner"


def test_user_can_store_interface_locale_without_changing_role_or_token(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    updated = client.patch("/my/locale", headers=headers, json={"locale": "ja-JP"})

    assert updated.status_code == 200
    assert updated.json() == {"user_id": "owner", "locale": "ja-JP"}
    assert client.get("/me", headers=headers).json()["locale"] == "ja-JP"


def test_i18n_frontend_module_is_served(tmp_path: Path):
    response = _client(tmp_path).get("/i18n.js")

    assert response.status_code == 200
    assert "HermiI18n" in response.text


def test_owner_can_create_conversation_and_messages(tmp_path: Path):
    adapter = FakeHermesAdapter()
    client = _client(tmp_path, adapter)
    headers = {"Authorization": "Bearer owner-token"}

    created = client.post("/conversations", json={"title": "Main"}, headers=headers)
    conversation_id = created.json()["conversation_id"]
    posted = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": "hello"},
        headers=headers,
    )
    listed = client.get(f"/conversations/{conversation_id}/messages", headers=headers)

    assert created.status_code == 200
    assert posted.status_code == 200
    assert posted.json()["assistant"]["content"] == "assistant reply"
    assert adapter.calls[0][0][-1]["content"].endswith("[user_message]\nhello")
    assert listed.status_code == 200
    assert [item["role"] for item in listed.json()["messages"]] == ["user", "assistant"]
    assert client.get("/conversations", headers=headers).json()["conversations"][0]["title"] == "Main"


def test_approval_decision_requires_owner(tmp_path: Path):
    client = _client(tmp_path)
    channel_headers = {"Authorization": "Bearer channel-token"}
    owner_headers = {"Authorization": "Bearer owner-token"}

    forbidden = client.post("/approvals/app-1/decision", json={"decision": "once"}, headers=channel_headers)
    allowed = client.post("/approvals/app-1/decision", json={"decision": "deny"}, headers=owner_headers)

    assert forbidden.status_code == 403
    assert allowed.status_code == 404


def test_remote_control_requires_owner(tmp_path: Path):
    client = _client(tmp_path)
    channel_headers = {"Authorization": "Bearer channel-token"}
    owner_headers = {"Authorization": "Bearer owner-token"}

    forbidden = client.post("/ops/services/hermes/action", json={"action": "status"}, headers=channel_headers)
    allowed = client.post("/ops/services/hermes/action", json={"action": "status"}, headers=owner_headers)

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["service"] == "hermes"
    assert allowed.json()["action"] == "status"
