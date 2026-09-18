from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class CaptureAdapter:
    def __init__(self):
        self.messages = []

    def chat(self, messages, session_id, session_key):
        self.messages = messages
        return "profile reply"


def _client(tmp_path: Path, monkeypatch, adapter=None) -> TestClient:
    local = tmp_path / "local"
    root = local / "hermes"
    (root / "profiles" / "trainee").mkdir(parents=True)
    (root / "profiles" / "imouto").mkdir(parents=True)
    (root / "profiles" / "maid").mkdir(parents=True)
    (root / "config.yaml").write_text(
        "model:\n  default: model-default\n  provider: provider-a\n", encoding="utf-8"
    )
    (root / "profiles" / "imouto" / "config.yaml").write_text(
        "model:\n  default: model-imouto\n  provider: provider-b\n", encoding="utf-8"
    )
    (root / "profiles" / "trainee" / "config.yaml").write_text(
        "model:\n  default: model-trainee\n  provider: provider-a\n", encoding="utf-8"
    )
    (root / "profiles" / "maid" / "SOUL.md").write_text("maid", encoding="utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("HERMI_PROFILE_NAMES", raising=False)
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
    )
    return TestClient(create_app(config, hermes_adapter=adapter))


def test_profiles_are_discovered_and_synced_to_agents(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer owner-token"}

    profiles = client.get("/profiles", headers=headers).json()["profiles"]
    agents = client.get("/agents", headers=headers).json()["agents"]

    assert [profile["profile_id"] for profile in profiles] == ["trainee", "imouto", "maid"]
    assert profiles[0]["model"] == "model-trainee"
    assert profiles[1]["status"] == "ready"
    assert profiles[2]["status"] == "setup_required"
    assert {agent["agent_id"] for agent in agents} == {
        "profile:trainee",
        "profile:imouto",
        "profile:maid",
    }


def test_meeting_mode_registry_exposes_versioned_dynamic_rules(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer owner-token"}

    modes = client.get("/meeting-presets", headers=headers).json()["modes"]

    assert all(item["mode"] and item["label"] for item in modes)
    assert all(item["rule_version"] for item in modes)
    assert all(item["orchestration"] for item in modes)
    assert next(item for item in modes if item["mode"] == "project_meeting")["orchestration"] == "directed_free"


def test_room_foundation_supports_host_permissions_history_and_live_changes(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer owner-token"}

    room = client.post(
        "/rooms",
        headers=headers,
        json={
            "name": "Local room",
            "mode": "auto_single",
            "host_agent_id": "profile:trainee",
            "permission_level": "general",
            "history_policy": "adaptive",
            "max_turns": 2,
        },
    ).json()
    member = client.post(
        f"/rooms/{room['room_id']}/members",
        headers=headers,
        json={"agent_id": "profile:imouto", "role": "participant"},
    )
    updated = client.patch(
        f"/rooms/{room['room_id']}",
        headers=headers,
        json={
            "mode": "pair_review",
            "permission_level": "smart",
            "history_policy": "summary",
            "max_turns": 4,
        },
    ).json()
    removed = client.delete(
        f"/rooms/{room['room_id']}/members/profile:imouto",
        headers=headers,
    )
    host_remove = client.delete(
        f"/rooms/{room['room_id']}/members/profile:trainee",
        headers=headers,
    )

    assert room["host_agent_id"] == "profile:trainee"
    assert member.status_code == 200
    assert updated["mode"] == "pair_review"
    assert updated["permission_level"] == "smart"
    assert updated["history_policy"] == "summary"
    assert updated["max_turns"] == 4
    assert removed.status_code == 200
    assert host_remove.status_code == 409


def test_owner_profile_name_flows_to_conversation_header_and_qq_envelope(tmp_path: Path, monkeypatch):
    adapter = CaptureAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}

    renamed = client.patch(
        "/profiles/trainee",
        headers=headers,
        json={"display_name": "总理"},
    )
    client.patch(
        "/profiles/maid",
        headers=headers,
        json={"display_name": "女仆长"},
    )
    conversation = client.post(
        "/conversations", headers=headers, json={"title": "New conversation"}
    ).json()
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "检查动态人格名称"},
    )
    listed = client.get("/conversations", headers=headers).json()["conversations"]
    envelope = client.post(
        "/qq-adapter/envelope/normalize",
        headers=headers,
        json={"source": "qq", "user_id": "1", "message_id": "m1"},
    ).json()["envelope"]
    profiles = client.get("/profiles", headers=headers).json()["profiles"]

    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "总理"
    assert next(item for item in profiles if item["profile_id"] == "trainee")["name"] == "总理"
    assert listed[0]["target_profile"] == "女仆长"
    assert listed[0]["title"].startswith("女仆长 · ")
    assert "target_profile=女仆长" in "\n".join(str(item["content"]) for item in adapter.messages)
    assert envelope["target_profile"] == "总理"


def test_conversation_profile_name_follows_source_channel(tmp_path: Path, monkeypatch):
    adapter = CaptureAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    owner_headers = {"Authorization": "Bearer owner-token"}

    client.post("/conversations", headers=owner_headers, json={"title": "Hermi chat"})
    qq = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-profile-1",
            "chat_type": "private",
            "user_id": "1000000001",
            "nickname": "Owner",
            "text": "检查人格",
            "sender_role": "owner",
            "risk": {"risk": "L0", "blocked": False},
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
        },
    )
    conversations = client.get("/conversations", headers=owner_headers).json()["conversations"]

    assert qq.status_code == 200
    assert next(item for item in conversations if item["channel"] == "qq")["target_profile"] == "薇达(Veda)"
    assert next(item for item in conversations if item["channel"] == "hermi-native")["target_profile"] == "薇拉(Vera)"


def test_qq_prompt_keeps_current_profile_identity_above_old_history(tmp_path: Path, monkeypatch):
    adapter = CaptureAdapter()
    client = _client(tmp_path, monkeypatch, adapter)

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-identity-1",
            "chat_type": "private",
            "user_id": "1000000001",
            "text": "老妹，你是谁？",
            "sender_role": "owner",
            "risk": {"risk": "L0", "blocked": False},
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
        },
    )
    system = str(adapter.messages[0]["content"])

    assert response.status_code == 200
    assert "当前启用人格：薇达(Veda)" in system
    assert "不得根据旧会话" in system
    assert "或用户称呼改写身份" in system


def test_private_messages_include_user_and_profile_actor_identity(tmp_path: Path, monkeypatch):
    adapter = CaptureAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "Identity"}).json()
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "显示身份"},
    )

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=headers
    ).json()["messages"]

    assert messages[0]["actor"]["actor_id"] == "owner"
    assert messages[0]["actor"]["actor_type"] == "user"
    assert messages[1]["actor"]["actor_id"] == "profile:maid"
    assert messages[1]["actor"]["display_name"] == "薇拉(Vera)"
    assert messages[1]["actor"]["actor_type"] == "ai"
    assert all("avatar" in item["actor"] for item in messages)

