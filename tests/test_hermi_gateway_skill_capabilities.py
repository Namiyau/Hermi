from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class SkillCaptureHermes:
    last_usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}

    def __init__(self) -> None:
        self.calls = []

    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        return "我会按这个流程处理。"


class StreamingSkillCaptureHermes(SkillCaptureHermes):
    def stream_events(self, messages, session_id, session_key):
        return iter(())

    def stream_profile_events(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        yield {"event": "final", "content": "流式能力回复。"}


def _client(tmp_path: Path) -> tuple[TestClient, SkillCaptureHermes]:
    hermes = SkillCaptureHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=hermes)), hermes


def test_skill_capabilities_are_listed_and_add_a_scoped_skill_hint(tmp_path: Path):
    client, hermes = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    capabilities = client.get("/capabilities", headers=headers).json()["skill_capabilities"]
    presentation = next(item for item in capabilities if item["capability_id"] == "presentation.create")
    assert presentation["skills"] == ["powerpoint"]

    conversation = client.post("/conversations", headers=headers, json={"title": "PPT"}).json()
    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "做一份三页的项目汇报", "capability_id": "presentation.create"},
    )

    assert response.status_code == 200
    system_text = "\n".join(
        item["content"] for item in hermes.calls[0][1] if item["role"] == "system"
    )
    assert "Selected Hermi skill capability: presentation.create" in system_text
    assert "powerpoint" in system_text
    messages = client.get(f"/conversations/{conversation['conversation_id']}/messages", headers=headers).json()["messages"]
    assert messages[0]["content"] == "做一份三页的项目汇报"


def test_hermi_feature_capabilities_include_schedule_and_qq_with_the_same_permission_guard(tmp_path: Path):
    client, hermes = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    capabilities = client.get("/capabilities", headers=headers).json()["skill_capabilities"]
    schedule = next(item for item in capabilities if item["capability_id"] == "scheduled.create")
    qq = next(item for item in capabilities if item["capability_id"] == "qq.send")
    assert schedule["kind"] == "hermi_feature"
    assert qq["kind"] == "hermi_feature"

    conversation = client.post("/conversations", headers=headers, json={"title": "reminder"}).json()
    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "明天提醒我复盘", "capability_id": "scheduled.create"},
    )

    assert response.status_code == 200
    system_text = "\n".join(
        item["content"] for item in hermes.calls[0][1] if item["role"] == "system"
    )
    assert "Selected Hermi feature capability: scheduled.create" in system_text
    assert "permission and approval rules" in system_text


def test_unknown_skill_capability_falls_back_to_regular_conversation(tmp_path: Path):
    client, hermes = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "普通会话"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "随便聊聊", "capability_id": "stale.capability"},
    )

    assert response.status_code == 200
    system_text = "\n".join(
        item["content"] for item in hermes.calls[0][1] if item["role"] == "system"
    )
    assert "Selected Hermi skill capability" not in system_text


def test_stream_message_receives_the_same_skill_hint(tmp_path: Path):
    hermes = StreamingSkillCaptureHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "流程图"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "画出登录流程", "capability_id": "diagram.create"},
    ) as response:
        assert response.status_code == 200
        assert "流式能力回复" in response.read().decode("utf-8")

    system_text = "\n".join(
        item["content"] for item in hermes.calls[0][1] if item["role"] == "system"
    )
    assert "Selected Hermi skill capability: diagram.create" in system_text
    assert "excalidraw" in system_text
