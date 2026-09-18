import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class PermissionHermes:
    last_usage = {}

    def chat(self, messages, session_id, session_key):
        return "我需要权限才能重启 Hermi 服务，请在 Hermi 审批中心批准。"


class EchoHermes:
    last_usage = {}

    def chat(self, messages, session_id, session_key):
        return "ok"


def _client(tmp_path: Path, hermes=None) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
        default_operation_root=tmp_path,
    )
    return TestClient(create_app(config, hermes_adapter=hermes or EchoHermes()))


def test_upload_preserves_chinese_filename_in_media_store(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "新会话"}).json()

    uploaded = client.post(
        "/files",
        headers=headers,
        data={"conversation_id": conv["conversation_id"], "visibility": "private"},
        files={"upload": ("研究计划.docx", b"fake docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    ).json()

    assert uploaded["original_name"] == "研究计划.docx"
    assert uploaded["download_url"] == f"/files/{uploaded['file_id']}/content"


def test_hermes_permission_text_creates_unified_approval(tmp_path: Path):
    client = _client(tmp_path, PermissionHermes())
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", headers=headers, json={"title": "新会话"}).json()

    response = client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        headers=headers,
        json={"content": "请重启 Hermi"},
    ).json()
    approvals = client.get("/approvals", headers=headers).json()["approvals"]

    assert "已创建审批" in response["assistant"]["content"]
    assert approvals[0]["action_type"] == "hermes.permission.request"
    assert "重启 Hermi" in approvals[0]["summary"]
    assert json.loads(approvals[0]["payload_json"])["requested_capability"] == "service.restart"


def test_remote_node_can_register_poll_job_and_report_result(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}

    registered = client.post(
        "/nodes/register",
        headers=owner_headers,
        json={"node_id": "node-b", "name": "B电脑", "capabilities": ["deploy", "read_logs"]},
    ).json()
    node_headers = {"Authorization": f"Bearer {registered['node_token']}"}
    job = client.post(
        "/nodes/node-b/jobs",
        headers=owner_headers,
        json={"summary": "阶段11部署烟测", "payload": {"action": "echo"}},
    ).json()
    heartbeat = client.post("/nodes/node-b/heartbeat", headers=node_headers).json()
    next_job = client.get("/nodes/node-b/jobs/next", headers=node_headers).json()["job"]
    log = client.post(f"/jobs/{job['job_id']}/logs", headers=node_headers, json={"content": "started"}).json()
    result = client.post(f"/jobs/{job['job_id']}/result", headers=node_headers, json={"status": "completed", "result": {"ok": True}}).json()

    assert registered["node_id"] == "node-b"
    assert heartbeat["ok"] is True
    assert next_job["job_id"] == job["job_id"]
    assert log["event_type"] == "node.log"
    assert result["status"] == "completed"


def test_remote_node_can_upload_artifacts_and_owner_can_read_logs(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    registered = client.post(
        "/nodes/register",
        headers=owner_headers,
        json={
            "node_id": "node-artifact",
            "name": "Artifact Node",
            "capabilities": ["artifacts"],
            "policy": {"allowed_artifact_types": ["screenshot", "test_report"], "max_artifact_bytes": 1024},
        },
    ).json()
    node_headers = {"Authorization": f"Bearer {registered['node_token']}"}
    job = client.post(
        "/nodes/node-artifact/jobs",
        headers=owner_headers,
        json={"summary": "artifact smoke", "payload": {"action": "collect"}},
    ).json()
    client.get("/nodes/node-artifact/jobs/next", headers=node_headers)

    uploaded = client.post(
        f"/jobs/{job['job_id']}/artifacts",
        headers=node_headers,
        data={"artifact_type": "screenshot", "metadata_json": '{"viewport":"desktop"}'},
        files={"upload": ("screen.png", b"fake png", "image/png")},
    ).json()
    logs = client.get(f"/jobs/{job['job_id']}/logs", headers=owner_headers).json()["logs"]
    artifacts = client.get(f"/jobs/{job['job_id']}/artifacts", headers=owner_headers).json()["artifacts"]

    assert uploaded["artifact_type"] == "screenshot"
    assert uploaded["original_name"] == "screen.png"
    assert uploaded["metadata"]["viewport"] == "desktop"
    assert artifacts[0]["artifact_id"] == uploaded["artifact_id"]
    assert any(log["event_type"] == "node.artifact" for log in logs)
