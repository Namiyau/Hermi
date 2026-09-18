from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class StreamingShellHermesAdapter:
    def __init__(self):
        self.last_usage = {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}

    def chat(self, messages, session_id, session_key):
        return "streamed reply"

    def stream_events(self, messages, session_id, session_key):
        yield {"event": "final", "content": "streamed reply"}


def test_message_stream_emits_final_without_fake_thoughts(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=StreamingShellHermesAdapter()))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "stream"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "hello"},
    ) as response:
        body = response.read().decode("utf-8")

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]

    assert response.status_code == 200
    assert "trace_started_at" in body
    assert "event: final" in body
    assert "event: thought" not in body
    assert "streamed reply" in body
    assert [message["role"] for message in messages] == ["user", "assistant"]
