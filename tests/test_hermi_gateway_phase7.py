from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    return TestClient(create_app(config))


def test_owner_can_add_room_members_and_run_project_meeting(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    host = client.post(
        "/agents",
        json={"name": "Hermes Host", "agent_type": "hermes_profile", "description": "主持"},
        headers=headers,
    ).json()
    reviewer = client.post(
        "/agents",
        json={"name": "Mock Reviewer", "agent_type": "mock", "description": "审查"},
        headers=headers,
    ).json()
    room = client.post(
        "/rooms",
        json={"name": "阶段7项目会议", "room_type": "project", "mode": "project_meeting"},
        headers=headers,
    ).json()

    host_member = client.post(
        f"/rooms/{room['room_id']}/members",
        json={"agent_id": host["agent_id"], "role": "host"},
        headers=headers,
    )
    reviewer_member = client.post(
        f"/rooms/{room['room_id']}/members",
        json={"agent_id": reviewer["agent_id"], "role": "participant"},
        headers=headers,
    )
    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        json={"mode": "project_meeting", "topic": "Hermi 阶段7会议", "max_turns": 1},
        headers=headers,
    )
    steps = client.get(f"/workflow-runs/{run.json()['run_id']}/steps", headers=headers)

    assert host_member.status_code == 200
    assert reviewer_member.status_code == 200
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert run.json()["mode"] == "project_meeting"
    assert len(steps.json()["steps"]) >= 3
    assert any("会议纪要" in step["content"] for step in steps.json()["steps"])


def test_meeting_presets_support_open_roles_and_modes(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    presets = client.get("/meeting-presets", headers=headers)
    premier = client.post(
        "/agents",
        json={"name": "总理", "agent_type": "hermes_profile", "description": "暂定主持人"},
        headers=headers,
    ).json()
    challenger = client.post(
        "/agents",
        json={"name": "挑错者", "agent_type": "mock", "description": "负责挑错"},
        headers=headers,
    ).json()
    room = client.post(
        "/rooms",
        json={"name": "开放会议室", "room_type": "project", "mode": "auto_single"},
        headers=headers,
    ).json()
    client.post(
        f"/rooms/{room['room_id']}/members",
        json={"agent_id": premier["agent_id"], "role": "总理"},
        headers=headers,
    )
    client.post(
        f"/rooms/{room['room_id']}/members",
        json={"agent_id": challenger["agent_id"], "role": "participant"},
        headers=headers,
    )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        json={"mode": "pair_review", "topic": "检查 Hermi 会议模式", "max_turns": 2},
        headers=headers,
    )
    steps = client.get(f"/workflow-runs/{run.json()['run_id']}/steps", headers=headers).json()["steps"]

    assert presets.status_code == 200
    assert {"auto_single", "pair_review", "project_meeting", "engineering_pipeline"}.issubset(
        {item["mode"] for item in presets.json()["modes"]}
    )
    assert any(role["role"] == "总理" for role in presets.json()["roles"])
    assert run.json()["status"] == "completed"
    assert any(step["role"] == "总理" for step in steps)
    assert any("双人挑错模式" in step["content"] for step in steps)
