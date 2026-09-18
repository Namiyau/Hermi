import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class CaptureAdapter:
    last_usage = {}

    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append(messages)
        return "Hermes reply"


class ActionThoughtAdapter(CaptureAdapter):
    def stream_events(self, messages, session_id, session_key):
        self.calls.append(messages)
        yield {"event": "thought", "content": "preparing action"}
        yield {"event": "thought", "content": '<<<HERMI_ACTION\n{"type":"qq.send"}\n>>>'}
        yield {"event": "final", "content": "approval created"}


class EchoedFinalThoughtAdapter(CaptureAdapter):
    def stream_events(self, messages, session_id, session_key):
        self.calls.append(messages)
        yield {"event": "thought", "content": "This is the final reply."}
        yield {"event": "final", "content": "This is the final reply."}


def _client(tmp_path: Path, adapter: CaptureAdapter) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=adapter))


def test_qq_qlos_attachment_metadata_is_parsed_and_single_file_waits(tmp_path: Path):
    adapter = CaptureAdapter()
    client = _client(tmp_path, adapter)
    source = tmp_path / "qq-screen.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nimage-bytes")

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-image-only",
            "chat_type": "private",
            "user_id": "1000000001",
            "nickname": "Owner",
            "text": "[image]",
            "sender_role": "owner",
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
            "attachments": [
                f"image:{source} | relative=Hermi资料/1000000001/qq-screen.png | original=https://example.test/qq-screen.png"
            ],
        },
    )

    assert response.status_code == 200
    assert "告诉我希望我做什么" in response.json()["reply"]
    assert adapter.calls == []
    files = client.get("/files", headers={"Authorization": "Bearer owner-token"}).json()["files"]
    assert len(files) == 1
    assert files[0]["mime"] == "image/png"
    assert files[0]["size_bytes"] == len(source.read_bytes())
    assert files[0]["download_url"]


def test_hermi_attachment_only_waits_for_instruction_without_calling_hermes(tmp_path: Path):
    adapter = CaptureAdapter()
    client = _client(tmp_path, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "files"}).json()
    uploaded = client.post(
        "/files",
        headers=headers,
        data={"conversation_id": conversation["conversation_id"]},
        files={"upload": ("note.txt", b"private file contents", "text/plain")},
    ).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "", "attachments": [{"file_id": uploaded["file_id"]}]},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "告诉我希望我做什么" in body
    assert adapter.calls == []


def test_stream_never_exposes_raw_hermi_action_as_thought(tmp_path: Path):
    adapter = ActionThoughtAdapter()
    client = _client(tmp_path, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "trace"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "hello"},
    ) as response:
        body = response.read().decode("utf-8")

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=headers
    ).json()["messages"]
    assert "preparing action" in body
    assert "<<<HERMI_ACTION" not in body
    assert "<<<HERMI_ACTION" not in messages[-1]["metadata_json"]


def test_stream_does_not_persist_a_thought_that_repeats_the_final_reply(tmp_path: Path):
    adapter = EchoedFinalThoughtAdapter()
    client = _client(tmp_path, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "echo"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "hello"},
    ) as response:
        body = response.read().decode("utf-8")

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=headers
    ).json()["messages"]
    assert "This is the final reply." in body
    assert '"trace"' not in messages[-1]["metadata_json"]


def test_explicit_image_question_returns_clear_unavailable_message_without_guessing(tmp_path: Path):
    adapter = CaptureAdapter()
    client = _client(tmp_path, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "image"}).json()
    uploaded = client.post(
        "/files",
        headers=headers,
        data={"conversation_id": conversation["conversation_id"]},
        files={"upload": ("screen.png", b"\x89PNG\r\n\x1a\nimage-bytes", "image/png")},
    ).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={
            "content": "请识别这张图片是什么。",
            "attachments": [{"file_id": uploaded["file_id"]}],
        },
    )

    assert response.status_code == 200
    assert "识图服务不可用" in response.json()["assistant"]["content"]
    assert adapter.calls == []


def test_frontend_has_logout_and_internal_trace_filter():
    root = Path(__file__).resolve().parents[1]
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    script = (root / "web" / "app.js").read_text(encoding="utf-8")

    assert 'id="account-logout-button"' in html
    assert "function logout" in script
    assert 'localStorage.removeItem("hermi_owner_token")' in script
    assert "function isInternalActionTrace" in script

