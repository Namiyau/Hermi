from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    return TestClient(create_app(config))


def test_owner_can_create_agent_and_room_skeleton(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    agent = client.post(
        "/agents",
        json={"name": "Hermes 主持", "agent_type": "hermes_profile", "description": "默认主持人"},
        headers=headers,
    )
    room = client.post(
        "/rooms",
        json={"name": "阶段1会议室", "room_type": "project", "mode": "single"},
        headers=headers,
    )

    assert agent.status_code == 200
    assert room.status_code == 200
    assert client.get("/agents", headers=headers).json()["agents"][0]["agent_type"] == "hermes_profile"
    assert client.get("/rooms", headers=headers).json()["rooms"][0]["mode"] == "single"


def test_owner_can_create_remote_deployment_job_skeleton(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    response = client.post(
        "/deployment-jobs",
        json={"target_node": "local", "summary": "部署会议室占位任务"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    jobs = client.get("/deployment-jobs", headers=headers).json()["deployment_jobs"]
    assert jobs[0]["summary"] == "部署会议室占位任务"
