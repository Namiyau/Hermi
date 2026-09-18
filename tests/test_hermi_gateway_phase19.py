from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def test_stage19_channel_envelope_normalizes_qq_source(tmp_path: Path):
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config))
    headers = {"Authorization": "Bearer owner-token"}

    response = client.post(
        "/qq-adapter/envelope/normalize",
        headers=headers,
        json={
            "source": "qq",
            "chat_type": "group",
            "user_id": "1000000001",
            "group_id": "2000000001",
            "message_id": "m-1",
            "sender_role": "owner",
            "permissions": ["qq.reply", "scheduled.create"],
            "attachments": [{"file_id": "file-1", "kind": "image"}],
        },
    )

    assert response.status_code == 200
    envelope = response.json()["envelope"]
    assert envelope["channel"] == "qq"
    assert envelope["source"] == "qq"
    assert envelope["transport"] == "napcat_onebot"
    assert envelope["chat_type"] == "group"
    assert envelope["target_profile"] == config.default_profile_name
    assert envelope["trace_id"].startswith("qq-m-1")
    assert envelope["attachments"][0]["file_id"] == "file-1"

