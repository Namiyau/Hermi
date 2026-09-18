from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def test_root_serves_hermi_app_shell(tmp_path: Path):
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config))

    response = client.get("/")

    assert response.status_code == 200
    assert "Hermi" in response.text
    assert "app.js" in response.text


def test_manifest_is_available(tmp_path: Path):
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config))

    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert response.json()["name"] == "Hermi"


def test_split_frontend_assets_are_served(tmp_path: Path):
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config))

    assert client.get("/admin_tools.js").status_code == 200
    assert client.get("/permissions_panel.js").status_code == 200
    assert client.get("/scheduled_jobs.js").status_code == 200


def test_meeting_ui_entry_and_panel_are_served(tmp_path: Path):
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config))

    html = client.get("/").text
    script = client.get("/app.js").text

    assert 'id="new-meeting"' in html
    assert 'id="meeting-tools-button"' in html
    assert 'id="meeting-tools-view"' in html
    assert 'id="room-list"' in html
    assert "`${role}+${titlePart}`" not in script


def test_start_script_uses_unicode_safe_media_path_and_broad_restart_cleanup():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "start_hermi_gateway.ps1").read_text(
        encoding="utf-8"
    )

    assert "Hermi璧勬枡" not in script
    assert "[char]0x8D44" in script
    assert "HERMI_RESTART_PARENT_PID" in script
    assert "Get-NetTCPConnection -LocalPort $Port" in script
    assert "function Stop-HermiProcess($proc)" in script
    assert "Stop-Process -Id $proc.ProcessId" in script
    assert "Stop-HermiProcess $proc" in script
