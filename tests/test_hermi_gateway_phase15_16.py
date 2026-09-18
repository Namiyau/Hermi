from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HERMI_PROFILE_NAMES", "妹妹,总理,工程师")
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        default_profile_name="妹妹",
        hermes_api_key="",
    )
    return TestClient(create_app(config))


def test_stage15_profile_registry_exposes_local_profiles(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer owner-token"}

    response = client.get("/profiles", headers=headers)

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert [profile["name"] for profile in profiles] == ["妹妹", "总理", "工程师"]
    assert profiles[0]["is_default"] is True
    assert all(profile["adapter"] == "hermes_profile" for profile in profiles)


def test_stage16_brain_status_keeps_hermi_usable_without_api_key(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    headers = {"Authorization": "Bearer owner-token"}

    response = client.get("/brain/status", headers=headers)

    assert response.status_code == 200
    data = response.json()
    adapters = {adapter["adapter_id"]: adapter for adapter in data["adapters"]}
    assert data["active_brain"] == "hermes_api"
    assert adapters["hermes_api"]["requires_setup"] is True
    assert adapters["local_profiles"]["available"] is True
    assert "opencode" in adapters
