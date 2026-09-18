import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config))


def test_owner_can_upload_list_download_and_delete_file(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    uploaded = client.post(
        "/files",
        headers=headers,
        files={"upload": ("notes.txt", b"hello media", "text/plain")},
        data={"visibility": "private"},
    )
    file_id = uploaded.json()["file_id"]
    listed = client.get("/files", headers=headers).json()["files"]
    downloaded = client.get(f"/files/{file_id}/content", headers=headers)
    deleted = client.delete(f"/files/{file_id}", headers=headers)
    missing = client.get(f"/files/{file_id}", headers=headers)

    assert uploaded.status_code == 200
    assert uploaded.json()["original_name"] == "notes.txt"
    assert uploaded.json()["size_bytes"] == len(b"hello media")
    assert "storage_path" not in uploaded.json()
    assert listed[0]["file_id"] == file_id
    assert downloaded.content == b"hello media"
    assert deleted.status_code == 200
    assert missing.status_code == 404


def test_upload_file_can_link_to_conversation_message(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "files"}).json()

    uploaded = client.post(
        "/files",
        headers=headers,
        files={"upload": ("image.png", b"fakepng", "image/png")},
        data={"conversation_id": conv["conversation_id"]},
    ).json()
    messages = client.get(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]

    assert uploaded["conversation_id"] == conv["conversation_id"]
    assert messages[-1]["role"] == "system"
    assert uploaded["file_id"] in messages[-1]["content"]
    assert json.loads(messages[-1]["metadata_json"])["file_id"] == uploaded["file_id"]
