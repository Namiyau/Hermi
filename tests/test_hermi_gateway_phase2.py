from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class FakeQlosClient:
    def __init__(self):
        self.sent = []

    def send_qq(self, *, chat_type, message, user_id=None, group_id=None):
        self.sent.append(
            {"chat_type": chat_type, "message": message, "user_id": user_id, "group_id": group_id}
        )
        return {"ok": True}


class ProfileSessionHermes:
    last_usage = {}

    def __init__(self):
        self.deleted = []
        self.synced = []

    def delete_profile_session(self, profile_id, session_id, session_key):
        self.deleted.append((profile_id, session_id, session_key))
        return {"deleted": True, "profile_id": profile_id}

    def session_messages_profile(self, profile_id, session_id, session_key):
        self.synced.append((profile_id, session_id, session_key))
        return [
            {"id": "hermes-owner-1", "role": "user", "content": "Owner 从 Hermes 发来的消息", "timestamp": 20.0},
            {"id": "hermes-vera-1", "role": "assistant", "content": "薇拉在 Hermes 的回答", "timestamp": 21.0},
        ]


class InternalEnvelopeHermes(ProfileSessionHermes):
    def session_messages_profile(self, profile_id, session_id, session_key):
        self.synced.append((profile_id, session_id, session_key))
        return [
            {
                "id": "hermes-internal-user",
                "role": "user",
                "content": "user_id=owner\npermission=owner-high\n[user_message]\n不要显示这段完整上下文",
                "timestamp": 20.0,
            },
            {"id": "hermes-internal-ai", "role": "assistant", "content": "不要重复的回答", "timestamp": 21.0},
            {
                "id": "hermes-internal-ai-tool-progress",
                "role": "assistant",
                "content": "intermediate tool progress must stay hidden",
                "timestamp": 21.5,
            },
            {
                "id": "hermes-internal-ai-final",
                "role": "assistant",
                "content": "intermediate final must stay hidden too",
                "timestamp": 21.8,
            },
            {"id": "hermes-owner-direct", "role": "user", "content": "这才是 Owner 直发", "timestamp": 22.0},
            {"id": "hermes-ai-direct", "role": "assistant", "content": "这才是同步回答", "timestamp": 23.0},
        ]


def _client(tmp_path: Path, qlos: FakeQlosClient | None = None) -> TestClient:
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    return TestClient(create_app(config, qlos_client=qlos or FakeQlosClient()))


def test_proactive_qq_draft_waits_for_owner_approval(tmp_path: Path):
    qlos = FakeQlosClient()
    client = _client(tmp_path, qlos)
    headers = {"Authorization": "Bearer owner-token"}

    draft = client.post(
        "/proactive/drafts",
        headers=headers,
        json={
            "kind": "qq.send",
            "summary": "send reminder to owner QQ",
            "content": "phase2 reminder",
            "target": {"chat_type": "private", "user_id": "1000000001"},
        },
    )

    assert draft.status_code == 200
    assert draft.json()["status"] == "pending"
    assert draft.json()["source"] == "proactive"
    assert draft.json()["action_type"] == "qq.send"
    assert qlos.sent == []

    decided = client.post(
        f"/approvals/{draft.json()['approval_id']}/decision",
        headers=headers,
        json={"decision": "once"},
    )

    assert decided.status_code == 200
    assert qlos.sent == [
        {"chat_type": "private", "message": "phase2 reminder", "user_id": "1000000001", "group_id": None}
    ]


def test_frontend_assets_disable_browser_caching(tmp_path: Path):
    client = _client(tmp_path)

    for path in ("/", "/app.js", "/styles.css", "/trace_ui.js"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store, max-age=0, must-revalidate"

def test_proactive_summary_draft_approval_writes_conversation_message(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    draft = client.post(
        "/proactive/drafts",
        headers=headers,
        json={"kind": "summary", "summary": "daily summary", "content": "Hermi summary body"},
    ).json()
    decided = client.post(
        f"/approvals/{draft['approval_id']}/decision",
        headers=headers,
        json={"decision": "once"},
    )
    messages = client.get(
        f"/conversations/{draft['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]

    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert messages[-1]["role"] == "assistant"
    assert "Hermi summary body" in messages[-1]["content"]


def test_owner_can_delete_conversation_with_messages_and_approvals(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", headers=headers, json={"title": "delete me"}).json()
    draft = client.post(
        "/proactive/drafts",
        headers=headers,
        json={
            "conversation_id": created["conversation_id"],
            "kind": "summary",
            "summary": "temporary",
            "content": "delete this approval too",
        },
    ).json()

    deleted = client.delete(f"/conversations/{created['conversation_id']}", headers=headers)
    listed = client.get("/conversations", headers=headers).json()["conversations"]
    approvals = client.get("/approvals", headers=headers).json()["approvals"]

    assert deleted.status_code == 200
    assert created["conversation_id"] not in [item["conversation_id"] for item in listed]
    assert draft["approval_id"] not in [item["approval_id"] for item in approvals]


def test_conversation_delete_uses_its_profile_hermes_session(tmp_path: Path):
    hermes = ProfileSessionHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        hermi_profile_id="maid",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", headers=headers, json={"title": "delete remote too"}).json()

    deleted = client.delete(f"/conversations/{created['conversation_id']}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["hermes_session_delete"]["deleted"] is True
    assert hermes.deleted == [("maid", created["session_id"], created["session_key"])]


def test_message_list_syncs_owner_and_assistant_messages_from_hermes_once(tmp_path: Path):
    hermes = ProfileSessionHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        hermi_profile_id="maid",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", headers=headers, json={"title": "同步"}).json()

    first = client.get(f"/conversations/{created['conversation_id']}/messages", headers=headers).json()["messages"]
    second = client.get(f"/conversations/{created['conversation_id']}/messages", headers=headers).json()["messages"]

    assert [message["content"] for message in first] == ["Owner 从 Hermes 发来的消息", "薇拉在 Hermes 的回答"]
    assert [message["content"] for message in second] == ["Owner 从 Hermes 发来的消息", "薇拉在 Hermes 的回答"]
    assert first[0]["actor"]["display_name"] == "Owner"
    assert first[1]["actor"]["display_name"] == "薇拉(Vera)"
    assert hermes.synced[0][0] == "maid"


def test_message_list_does_not_sync_hermi_context_envelope_or_its_reply(tmp_path: Path):
    hermes = InternalEnvelopeHermes()
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", headers=headers, json={"title": "同步过滤"}).json()

    messages = client.get(f"/conversations/{created['conversation_id']}/messages", headers=headers).json()["messages"]

    assert [message["content"] for message in messages] == ["这才是 Owner 直发", "这才是同步回答"]


def test_owner_can_notify_qq_when_approval_overdue(tmp_path: Path):
    qlos = FakeQlosClient()
    client = _client(tmp_path, qlos)
    headers = {"Authorization": "Bearer owner-token"}
    draft = client.post(
        "/proactive/drafts",
        headers=headers,
        json={
            "kind": "qq.send",
            "summary": "approval waits too long",
            "content": "later",
            "target": {"chat_type": "private", "user_id": "1000000001"},
        },
    ).json()

    response = client.post(
        "/approvals/notify-overdue",
        headers=headers,
        json={"max_age_seconds": 0, "user_id": "1000000001"},
    )

    assert response.status_code == 200
    assert response.json()["notified"] >= 1
    assert qlos.sent[0]["chat_type"] == "private"
    assert qlos.sent[0]["user_id"] == "1000000001"
    assert "approval waits too long" in qlos.sent[0]["message"]
    assert draft["approval_id"]

