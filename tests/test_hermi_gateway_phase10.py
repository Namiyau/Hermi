from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class CaptureHermes:
    last_usage = {}

    def __init__(self):
        self.messages = []

    def chat(self, messages, session_id, session_key):
        self.messages = messages
        return "ok"

    def stream_events(self, messages, session_id, session_key):
        self.messages = messages
        yield {"event": "final", "content": "ok"}


def _client(tmp_path: Path, hermes: CaptureHermes) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
        default_profile_name="妹妹",
        default_operation_root=tmp_path,
    )
    return TestClient(create_app(config, hermes_adapter=hermes))


def test_uploaded_file_attachment_is_resolved_to_server_file_context(tmp_path: Path):
    hermes = CaptureHermes()
    client = _client(tmp_path, hermes)
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "新会话"}).json()
    uploaded = client.post(
        "/files",
        headers=headers,
        data={"conversation_id": conv["conversation_id"], "visibility": "private"},
        files={"upload": ("remote-device.txt", b"hello from phone", "text/plain")},
    ).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
        json={
            "content": "请阅读这个文件",
            "attachments": [{"file_id": uploaded["file_id"], "client_path": "C:/Users/phone/remote-device.txt"}],
        },
    )

    merged = "\n".join(message["content"] for message in hermes.messages)
    assert "请阅读这个文件" in merged
    assert "[Hermi server attachments]" in merged
    assert f"file_id={uploaded['file_id']}" in merged
    assert "remote-device.txt" in merged
    assert str(tmp_path / "media") in merged
    assert "C:/Users/phone/remote-device.txt" not in merged


def test_default_conversation_title_has_profile_prefix_after_first_round(tmp_path: Path):
    hermes = CaptureHermes()
    client = _client(tmp_path, hermes)
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


def test_garbled_default_conversation_title_can_still_auto_rename(tmp_path: Path):
    hermes = CaptureHermes()
    client = _client(tmp_path, hermes)
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "???"}).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
        json={"content": "阶段十标题修复验证"},
    )

    conversations = client.get("/conversations", headers=headers).json()["conversations"]
    renamed = next(item for item in conversations if item["conversation_id"] == conv["conversation_id"])
    assert renamed["title"] == "薇拉(Vera) · 阶段十标题修复验证"


def test_code_adapter_run_creates_approval_draft_task_bound_to_operation_zone(tmp_path: Path):
    hermes = CaptureHermes()
    client = _client(tmp_path, hermes)
    headers = {"Authorization": "Bearer owner-token"}
    zone = client.post(
        "/operation-zones",
        headers=headers,
        json={"workspace_path": str(tmp_path), "allowed_tools": ["list", "read"]},
    ).json()

    created = client.post(
        "/code-adapter-runs",
        headers=headers,
        json={
            "adapter": "codex",
            "operation_zone_id": zone["zone_id"],
            "summary": "检查 Hermi 上传文件通路",
            "mode": "repair",
            "instructions": "只读检查并给出 diff 草稿",
        },
    ).json()
    events = client.get(f"/tasks/{created['task_id']}/events", headers=headers).json()["events"]

    assert created["task_type"] == "code_adapter"
    assert created["status"] == "pending_approval"
    assert '"adapter": "codex"' in created["metadata_json"]
    assert zone["zone_id"] in created["metadata_json"]
    assert events[0]["event_type"] == "code_adapter.draft"
    assert "默认不执行写入" in events[0]["content"]
