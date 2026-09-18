from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.db import init_db


class ScheduledHermesAdapter:
    def chat(self, messages, session_id, session_key):
        return (
            "我会先生成一个待审批定时任务。\n"
            "<<<HERMI_ACTION\n"
            '{"type":"scheduled.create","kind":"cron","schedule":"*/5 * * * *",'
            '"summary":"每 5 分钟检查 QQ 并汇报","content":"检查 QQ 最近消息并汇报。"}'
            "\n>>>"
        )


class PromiseOnlyHermesAdapter:
    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append({"messages": messages, "session_id": session_id, "session_key": session_key})
        if session_id.endswith(":contract-repair"):
            return (
                "我已转成 Hermi 审批动作。\n"
                "<<<HERMI_ACTION\n"
                '{"type":"scheduled.create","kind":"once","schedule":"once:+5m",'
                '"summary":"5分钟后总结热点新闻","content":"上网看看新闻，然后总结五条热点新闻给 owner。",'
                '"target":{"delivery":["hermi","qq"],"qq":{"chat_type":"private","user_id":"1000000001"}},'
                '"payload":{"report_to_qq":true}}'
                "\n>>>"
            )
        return "安排上了。5分钟后我会去上网看新闻，然后总结给你发 QQ。"


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=ScheduledHermesAdapter()))


def test_phase5_tables_are_created(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    tables = {
        row["name"]
        for row in conn.execute("select name from sqlite_master where type = 'table'").fetchall()
    }

    assert {"tasks", "task_events", "task_artifacts", "scheduled_jobs"}.issubset(tables)


def test_owner_can_create_task_and_append_events(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    created = client.post(
        "/tasks",
        headers=headers,
        json={"title": "检查 QQ 消息", "task_type": "scheduled"},
    )
    task_id = created.json()["task_id"]
    event = client.post(
        f"/tasks/{task_id}/events",
        headers=headers,
        json={"event_type": "log", "content": "已开始检查"},
    )
    listed = client.get("/tasks", headers=headers)
    events = client.get(f"/tasks/{task_id}/events", headers=headers)

    assert created.status_code == 200
    assert created.json()["status"] == "pending"
    assert event.status_code == 200
    assert event.json()["content"] == "已开始检查"
    assert any(task["task_id"] == task_id for task in listed.json()["tasks"])
    assert events.json()["events"][0]["event_type"] == "log"


def test_owner_scheduled_action_creates_hermi_job_without_approval(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "cron"}).json()

    sent = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "开启一个每 5 分钟检查 QQ 并汇报的 cron 任务"},
    )
    approvals = client.get("/approvals", headers=headers).json()["approvals"]
    jobs = client.get("/scheduled-jobs", headers=headers).json()["scheduled_jobs"]
    tasks = client.get("/tasks", headers=headers).json()["tasks"]
    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]

    assert sent.status_code == 200
    assert approvals == []
    assert jobs[0]["kind"] == "interval"
    assert jobs[0]["schedule"] == "interval:5m"
    assert jobs[0]["status"] == "active"
    assert tasks[0]["task_type"] == "scheduled"
    assert any("安排好了" in message["content"] for message in messages)


def test_owner_can_read_and_delete_scheduled_job_detail(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post(
        "/scheduled-jobs",
        headers=headers,
        json={
            "kind": "cron",
            "schedule": "*/10 * * * *",
            "summary": "poll qq",
            "target": {"delivery": "qq", "qq": "1000000001"},
            "payload": {"prompt": "report"},
        },
    )
    job_id = created.json()["job_id"]

    detail = client.get(f"/scheduled-jobs/{job_id}", headers=headers)
    deleted = client.delete(f"/scheduled-jobs/{job_id}", headers=headers)
    missing = client.get(f"/scheduled-jobs/{job_id}", headers=headers)

    assert created.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["target_json"]
    assert deleted.status_code == 200
    assert deleted.json()["job_id"] == job_id
    assert missing.status_code == 404


def test_decided_approval_record_can_be_deleted_but_pending_cannot(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "delete approval"}).json()
    client.post(
        "/approvals/native",
        headers=headers,
        json={
            "conversation_id": conversation["conversation_id"],
            "capability_id": "hermes.permission.request",
            "summary": "删除审批测试",
        },
    )
    approval = client.get("/approvals", headers=headers).json()["approvals"][0]

    pending_delete = client.delete(f"/approvals/{approval['approval_id']}", headers=headers)
    client.post(
        f"/approvals/{approval['approval_id']}/decision",
        headers=headers,
        json={"decision": "deny"},
    )
    decided_delete = client.delete(f"/approvals/{approval['approval_id']}", headers=headers)
    approvals = client.get("/approvals", headers=headers).json()["approvals"]

    assert pending_delete.status_code == 409
    assert pending_delete.json()["detail"] == "approval_pending"
    assert decided_delete.status_code == 200
    assert not approvals


def test_owner_scheduled_request_uses_hermi_scheduler_without_approval(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    hermes = ScheduledHermesAdapter()
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "fallback cron"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "5分钟后去上网看看新闻，然后总结五条热点新闻给我发到QQ上"},
    )
    approvals = client.get("/approvals", headers=headers).json()["approvals"]
    jobs = client.get("/scheduled-jobs", headers=headers).json()["scheduled_jobs"]

    assert response.status_code == 200
    assert approvals == []
    assert len(jobs) == 1
    assert jobs[0]["kind"] == "once"
    assert jobs[0]["schedule"] == "once:+5m"

