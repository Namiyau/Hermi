from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class FakeHermesAdapter:
    def __init__(self):
        self.calls = []
        self.last_usage = {}

    def chat(self, messages, session_id, session_key):
        self.calls.append((messages, session_id, session_key))
        return "image reply"


def test_qq_explicit_image_request_includes_stored_attachment_context(tmp_path: Path):
    adapter = FakeHermesAdapter()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=adapter))

    response = client.post(
        "/channels/qq/events",
        headers={"Authorization": "Bearer channel-token"},
        json={
            "message_id": "qq-image-followup",
            "chat_type": "private",
            "user_id": "1000000001",
            "text": "read this image",
            "sender_role": "owner",
            "session_id": "qlos-qq-dm-1000000001",
            "session_key": "qlos:qq:dm:1000000001",
            "attachments": ["image:https://example.com/pic.png"],
        },
    )

    assert response.status_code == 200
    content = adapter.calls[0][0][-1]["content"]
    assert "[Hermi server attachments]" in content
    assert "server_path=" in content

