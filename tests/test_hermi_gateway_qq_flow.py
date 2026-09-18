from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class FakeHermesAdapter:
    def __init__(self, reply: str = "Hermes says hi"):
        self.calls = []
        self.reply = reply

    def chat(self, messages, session_id, session_key):
        self.calls.append((messages, session_id, session_key))
        return self.reply


def _client(tmp_path: Path, adapter: FakeHermesAdapter) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=adapter))


def test_qq_event_creates_conversation_calls_hermes_and_returns_reply(tmp_path: Path):
    adapter = FakeHermesAdapter()
    client = _client(tmp_path, adapter)

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-1",
            "chat_type": "private",
            "user_id": "1000000001",
            "nickname": "Owner",
            "text": "hello from qq",
            "sender_role": "owner",
            "risk": {"risk": "L0", "blocked": False},
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
        },
    )

    data = response.json()

    assert response.status_code == 200
    assert data["ok"] is True
    assert data["reply"] == "Hermes says hi"
    assert data["session_id"] == "qlos-qq-dm-1000000001"
    merged = "\n".join(str(message["content"]) for message in adapter.calls[0][0])
    assert "hello from qq" in adapter.calls[0][0][-1]["content"]
    assert "<<<QLOS_SPLIT>>>" in merged
    assert "推荐 1~3 个" in merged
    assert "内部拆分标记" in merged

    messages = client.get(
        f"/conversations/{data['conversation_id']}/messages",
        headers={"Authorization": "Bearer owner-token"},
    ).json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]


def test_qq_event_ignores_a_duplicate_message_id_without_calling_hermes_again(tmp_path: Path):
    adapter = FakeHermesAdapter()
    client = _client(tmp_path, adapter)
    payload = {
        "message_id": "qq-duplicate-1",
        "chat_type": "private",
        "user_id": "1000000001",
        "text": "only answer this once",
        "sender_role": "owner",
        "session_id": "qlos-qq-dm-1000000001",
        "session_key": "qlos:qq:dm:1000000001",
    }
    headers = {"Authorization": "Bearer channel-token"}

    first = client.post("/channels/qq/events", headers=headers, json=payload)
    duplicate = client.post("/channels/qq/events", headers=headers, json=payload)

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json() == {
        "ok": True,
        "duplicate": True,
        "reply": "",
        "conversation_id": first.json()["conversation_id"],
    }
    assert len(adapter.calls) == 1
    messages = client.get(
        f"/conversations/{first.json()['conversation_id']}/messages",
        headers={"Authorization": "Bearer owner-token"},
    ).json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]


def test_qq_event_uses_qlos_prompt_when_qlos_routes_through_hermi(tmp_path: Path):
    adapter = FakeHermesAdapter()
    client = _client(tmp_path, adapter)
    qlos_prompt = "QLOS output contract: normal multi-unit QQ replies MUST use <<<QLOS_SPLIT>>>."

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-prompt-bridge-1",
            "chat_type": "private",
            "user_id": "1000000001",
            "text": "讲两件事",
            "sender_role": "owner",
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
            "qlos_prompt": qlos_prompt,
        },
    )

    assert response.status_code == 200
    system = adapter.calls[0][0][0]["content"]
    assert qlos_prompt in system
    assert system.count("<<<QLOS_SPLIT>>>") == 1


def test_qq_event_requires_channel_token(tmp_path: Path):
    adapter = FakeHermesAdapter()
    client = _client(tmp_path, adapter)

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer owner-token"},
        json={
            "message_id": "qq-2",
            "chat_type": "private",
            "user_id": "123",
            "text": "hello",
            "session_id": "qlos-qq-dm-123",
            "session_key": "qlos:qq:dm:123",
        },
    )

    assert response.status_code == 403


def test_qq_event_indexes_attachments_as_shared_media_without_auto_vision(tmp_path: Path):
    adapter = FakeHermesAdapter()
    client = _client(tmp_path, adapter)

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-file-1",
            "chat_type": "private",
            "user_id": "1000000001",
            "nickname": "Owner",
            "text": "这是一张图，先存着",
            "sender_role": "owner",
            "risk": {"risk": "L0", "blocked": False},
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
            "attachments": [
                "image:https://example.com/pic.png",
                "file:https://example.com/report.pdf",
            ],
        },
    )

    assert response.status_code == 200
    files = client.get("/files", headers={"Authorization": "Bearer owner-token"}).json()["files"]
    names = {item["original_name"] for item in files}
    image = next(item for item in files if item["original_name"] == "pic.png")

    assert names == {"pic.png", "report.pdf"}
    assert image["source_channel"] == "qq"
    assert image["visibility"] == "shared"
    assert image["metadata_json"]
    assert image["download_url"] == ""

    messages = client.get(
        f"/conversations/{response.json()['conversation_id']}/messages",
        headers={"Authorization": "Bearer owner-token"},
    ).json()["messages"]
    metadata = messages[0]["metadata_json"]
    assert "raw_attachments" in metadata
    assert "auto_vision" in metadata
    qq_content = adapter.calls[0][0][-1]["content"]
    assert "[QQ ChannelEnvelope]" in qq_content
    assert "source=qq" in qq_content
    assert "target_profile=薇达(Veda)" in qq_content
    assert "[user_message]\n这是一张图，先存着" in qq_content
    assert "[Hermi server attachments]" in qq_content


def test_qq_event_returns_split_marker_to_qlos_but_stores_readable_reply(tmp_path: Path):
    adapter = FakeHermesAdapter("第一段<<<QLOS_SPLIT>>>第二段")
    client = _client(tmp_path, adapter)

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-split-1",
            "chat_type": "private",
            "user_id": "1000000001",
            "nickname": "Owner",
            "text": "日常聊天，拆一下",
            "sender_role": "owner",
            "risk": {"risk": "L0", "blocked": False},
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
        },
    )
    data = response.json()
    messages = client.get(
        f"/conversations/{data['conversation_id']}/messages",
        headers={"Authorization": "Bearer owner-token"},
    ).json()["messages"]

    assert data["reply"] == "第一段<<<QLOS_SPLIT>>>第二段"
    assert messages[-1]["content"] == "第一段\n\n第二段"

