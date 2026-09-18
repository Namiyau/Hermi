from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.db import init_db


class CaptureHermes:
    def __init__(self):
        self.calls = []
        self.last_usage = {}

    def chat(self, messages, session_id, session_key):
        self.calls.append(messages)
        return "ok"


def _client(tmp_path: Path, *, workspace: Path | None = None, hermes=None) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
        default_profile_name="妹妹",
        default_operation_root=workspace or tmp_path,
    )
    return TestClient(create_app(config, hermes_adapter=hermes or CaptureHermes()))


def test_phase9_operation_zone_tables_are_created(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    tables = {row["name"] for row in conn.execute("select name from sqlite_master where type = 'table'").fetchall()}

    assert "operation_zones" in tables
    assert "operation_logs" in tables


def test_owner_can_create_operation_zone_and_run_readonly_status(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "note.txt").write_text("hello", encoding="utf-8")
    client = _client(tmp_path, workspace=workspace)
    headers = {"Authorization": "Bearer owner-token"}

    zone = client.post(
        "/operation-zones",
        headers=headers,
        json={"workspace_path": str(workspace), "allowed_tools": ["list", "read", "git_status"]},
    ).json()
    listing = client.post(
        f"/operation-zones/{zone['zone_id']}/actions",
        headers=headers,
        json={"action": "list", "path": "."},
    )
    read = client.post(
        f"/operation-zones/{zone['zone_id']}/actions",
        headers=headers,
        json={"action": "read", "path": "note.txt"},
    )
    denied = client.post(
        f"/operation-zones/{zone['zone_id']}/actions",
        headers=headers,
        json={"action": "read", "path": "../outside.txt"},
    )

    assert listing.status_code == 200
    assert "note.txt" in listing.json()["output"]
    assert read.json()["output"] == "hello"
    assert denied.status_code == 403


def test_prompt_render_preview_uses_cards_without_replacing_profile(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/prompt-cards",
        headers=headers,
        json={"name": "Room rule", "card_type": "room", "content": "会议室只做补充规则。", "enabled": True},
    )

    rendered = client.post(
        "/prompt-renders/preview",
        headers=headers,
        json={"channel": "hermi", "room_id": "room-demo", "agent_name": "妹妹"},
    ).json()

    assert rendered["mode"] == "supplemental"
    assert "会议室只做补充规则。" in rendered["prompt"]
    assert "不覆盖 Hermes 原生 profile/soul" in rendered["prompt"]


def test_hermi_header_includes_default_profile_name(tmp_path: Path):
    hermes = CaptureHermes()
    client = _client(tmp_path, hermes=hermes)
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "profile"}).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
        json={"content": "hello"},
    )

    merged = "\n".join(str(message["content"]) for message in hermes.calls[0])
    assert "target_profile=薇拉(Vera)" in merged
