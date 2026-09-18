from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.db import init_db


class UsageHermes:
    last_usage = {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18, "cache_read_tokens": 3}

    def chat(self, messages, session_id, session_key):
        return "OK"


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
    )
    return TestClient(create_app(config, hermes_adapter=UsageHermes()))


def test_phase13_owner_can_read_conversation_context_summary(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "context"}).json()
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "hello context"},
    )

    response = client.get(f"/conversations/{conversation['conversation_id']}/context", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == conversation["conversation_id"]
    assert data["message_count"] == 2
    assert data["attachment_count"] == 0
    assert data["usage"]["total_tokens"] == 18
    assert data["conversation_usage"]["total_tokens"] == 18
    assert data["conversation_usage"]["cache_read_tokens"] == 3
    assert data["conversation_usage"]["cache_hit_rate"] == 43
    assert data["usage_scope"] == "user_last_7_days"
    assert data["context_window"]["status"] == "ok"


def test_new_hermi_conversation_accepts_current_vera_profile_only(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    created = client.post("/conversations", headers=headers, json={"title": "vera", "profile_id": "maid"})
    rejected = client.post("/conversations", headers=headers, json={"title": "other", "profile_id": "trainee"})

    assert created.status_code == 200
    assert created.json()["profile_id"] == "maid"
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "profile_not_available"


def test_phase14_capabilities_have_schema_and_validate_actions(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    capabilities = client.get("/capabilities", headers=headers).json()["capabilities"]
    qq_send = next(item for item in capabilities if item["capability_id"] == "qq.send")
    valid = client.post(
        "/actions/validate",
        headers=headers,
        json={"type": "qq.send", "message": "hello", "target": {"chat_type": "private", "user_id": "1000000001"}},
    )
    invalid = client.post(
        "/actions/validate",
        headers=headers,
        json={"type": "qq.send", "target": {"chat_type": "private"}},
    )

    assert qq_send["risk_level"] == "medium"
    assert "message" in qq_send["schema"]["required"]
    assert valid.json()["ok"] is True
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["missing"] == ["message"]


def test_phase14_approval_callback_records_native_run_status(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "approval callback"}).json()
    approval = client.post(
        "/approvals/native",
        headers=headers,
        json={
            "conversation_id": conversation["conversation_id"],
            "run_id": "run-1",
            "request_id": "approval-request-1",
            "capability_id": "service.action",
            "summary": "重启 Hermi",
            "payload": {"service": "hermi", "action": "restart"},
        },
    ).json()

    decision = client.post(
        f"/approvals/{approval['approval_id']}/decision",
        headers=headers,
        json={"decision": "deny"},
    )
    callbacks = client.get(f"/approvals/{approval['approval_id']}/callbacks", headers=headers)

    assert decision.json()["status"] == "denied"
    assert callbacks.json()["callbacks"][0]["external_run_id"] == "run-1"
    assert callbacks.json()["callbacks"][0]["status"] == "denied"


def test_phase14_db_contains_registry_and_callback_tables(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    tables = {row["name"] for row in conn.execute("select name from sqlite_master where type='table'").fetchall()}

    assert {"capability_registry", "approval_callbacks"}.issubset(tables)


def test_phase14_local_slash_commands_do_not_call_hermes(tmp_path: Path):
    class CountingHermes:
        last_usage = {}
        calls = 0

        def chat(self, messages, session_id, session_key):
            self.calls += 1
            return "should not be called"

    hermes = CountingHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "commands"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "/capabilities"},
    )

    assert response.status_code == 200
    assert "Hermi 当前能力" in response.json()["assistant"]["content"]
    assert hermes.calls == 0

