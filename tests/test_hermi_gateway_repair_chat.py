import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class NamingHermes:
    last_usage = {}

    def chat(self, messages, session_id, session_key):
        return "assistant reply"


class EventHermes:
    last_usage = {}

    def stream_events(self, messages, session_id, session_key):
        yield {"event": "thought", "content": "正在调用 Hermes 工具"}
        yield {"event": "tool", "content": "工具调用：search"}
        yield {"event": "final", "content": "stream final reply"}

    def chat(self, messages, session_id, session_key):
        return "fallback reply"


class MediaActionHermes:
    last_usage = {}

    def __init__(self, image_path: Path):
        self.image_path = image_path

    def stream_events(self, messages, session_id, session_key):
        action = {
            "type": "qq.send",
            "chat_type": "private",
            "user_id": "1000000001",
            "message": f"截图路径：{self.image_path}",
            "images": [],
        }
        yield {
            "event": "final",
            "content": (
                f"截图好了。\n\nMEDIA:{self.image_path}\n\n"
                "<<<HERMI_ACTION\n"
                f"{json.dumps(action, ensure_ascii=False)}\n"
                ">>>"
            ),
        }

    def chat(self, messages, session_id, session_key):
        return ""


def _client(tmp_path: Path, hermes) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=hermes))


def test_default_conversation_auto_renames_after_first_round(tmp_path: Path):
    client = _client(tmp_path, NamingHermes())
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "新会话"}).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
        json={"content": "帮我整理今天的工作计划和提醒"},
    )
    conversations = client.get("/conversations", headers=headers).json()["conversations"]

    renamed = next(item for item in conversations if item["conversation_id"] == conv["conversation_id"])
    assert renamed["title"] == "薇拉(Vera) · 帮我整理今天的工作计划"


def test_my_summary_reports_basic_user_totals(tmp_path: Path):
    client = _client(tmp_path, NamingHermes())
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "Summary"}).json()
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "统计一下"},
    )

    summary = client.get("/my/summary", headers=headers).json()

    assert summary["display_name"] == "Owner"
    assert summary["role"] == "owner"
    assert summary["conversation_count"] == 1
    assert summary["message_count"] == 2
    assert summary["attachment_count"] == 0
    assert summary["total_tokens"] == 0


def test_user_can_change_display_name_without_changing_stable_identity(tmp_path: Path):
    client = _client(tmp_path, NamingHermes())
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:display-name",
            "display_name": "Before",
            "token": "display-name-token",
            "quota_policy": "friend_trusted",
        },
    )
    friend_headers = {"Authorization": "Bearer display-name-token"}

    changed = client.patch("/my/display-name", headers=friend_headers, json={"display_name": "After"})
    summary = client.get("/my/summary", headers=friend_headers).json()
    detail = client.get("/admin/users/friend:display-name", headers=owner_headers).json()

    assert changed.status_code == 200
    assert summary["display_name"] == "After"
    assert detail["user_id"] == "friend:display-name"
    assert detail["role"] == "friend"
    assert detail["quota_policy"] == "friend_trusted"


def test_stream_endpoint_forwards_real_hermes_thought_and_tool_events(tmp_path: Path):
    client = _client(tmp_path, EventHermes())
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "Stream"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conv['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "hello"},
    ) as response:
        body = response.read().decode("utf-8")

    messages = client.get(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]

    assert response.status_code == 200
    assert "event: thought" in body
    assert "正在调用 Hermes 工具" in body
    assert "event: tool" in body
    assert "event: final" in body
    assert messages[-1]["content"] == "stream final reply"
    metadata = json.loads(messages[-1]["metadata_json"])
    assert metadata["trace"][0] == {"event": "thought", "content": "正在调用 Hermes 工具"}
    assert metadata["trace"][1] == {"event": "tool", "content": "工具调用：search"}


def test_stream_imports_media_paths_as_message_attachments_and_qq_action_images(tmp_path: Path):
    image_path = tmp_path / "codex-screen.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    client = _client(tmp_path, MediaActionHermes(image_path))
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "Screen"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conv['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "截图发给 QQ 和聊天框"},
    ) as response:
        response.read()

    messages = client.get(f"/conversations/{conv['conversation_id']}/messages", headers=headers).json()["messages"]
    approvals = client.get("/approvals", headers=headers).json()["approvals"]
    metadata = json.loads(messages[-1]["metadata_json"])
    action = json.loads(approvals[0]["payload_json"])

    assert response.status_code == 200
    assert metadata["attachments"][0]["original_name"] == "codex-screen.png"
    assert metadata["attachments"][0]["mime"].startswith("image/")
    assert action["images"][0]["file_id"] == metadata["attachments"][0]["file_id"]
    assert action["images"][0]["path"].endswith(".png")
    assert "C:" not in action["message"]
    assert "图片已附上" in action["message"]


def test_stream_registers_files_already_in_hermi_media_without_copying_again(tmp_path: Path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    image_path = media_dir / "already-in-hermi-media.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    client = _client(tmp_path, MediaActionHermes(image_path))
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "Media root"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conv['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "把图发到这里"},
    ) as response:
        response.read()

    messages = client.get(f"/conversations/{conv['conversation_id']}/messages", headers=headers).json()["messages"]
    metadata = json.loads(messages[-1]["metadata_json"])
    assert response.status_code == 200
    assert len(list(media_dir.iterdir())) == 1
    assert metadata["attachments"][0]["original_name"] == image_path.name
def test_owner_cannot_rename_another_users_conversation(tmp_path: Path):
    client = _client(tmp_path, NamingHermes())
    owner_headers = {"Authorization": "Bearer owner-token"}
    created_user = client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:rename", "display_name": "Rename friend", "token": "friend-token"},
    )
    assert created_user.status_code == 200
    friend_headers = {"Authorization": "Bearer friend-token"}
    conversation = client.post("/conversations", headers=friend_headers, json={"title": "Friend title"}).json()

    response = client.patch(
        f"/conversations/{conversation['conversation_id']}",
        headers=owner_headers,
        json={"title": "Owner must not rename this"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "conversation_forbidden"


def test_owner_message_in_friend_conversation_keeps_owner_as_its_author(tmp_path: Path):
    client = _client(tmp_path, NamingHermes())
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.patch("/my/display-name", headers=owner_headers, json={"display_name": "Namiya"})
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:actor", "display_name": "testA", "token": "friend-actor-token"},
    )
    friend_headers = {"Authorization": "Bearer friend-actor-token"}
    conversation = client.post("/conversations", headers=friend_headers, json={"title": "Shared"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=owner_headers,
        json={"content": "owner joined this conversation"},
    ) as response:
        response.read()

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend_headers,
    ).json()["messages"]

    assert response.status_code == 200
    owner_message = next(message for message in messages if message["content"] == "owner joined this conversation")
    assert json.loads(owner_message["metadata_json"])["author_user_id"] == "owner"
    assert owner_message["actor"] == {
        "actor_id": "owner",
        "display_name": "Namiya",
        "actor_type": "user",
        "avatar": "",
    }

