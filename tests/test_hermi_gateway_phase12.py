from pathlib import Path
import time

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.app import _scheduled_job_due
from hermi_gateway.config import HermiConfig


class ScheduledHermes:
    last_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append({"messages": messages, "session_id": session_id, "session_key": session_key})
        return "主动任务完成：已经检查并生成汇报。"


class CaptureQlos:
    def __init__(self):
        self.sent = []

    def send_qq(self, *, chat_type, message, user_id=None, group_id=None, images=None, attachments=None):
        self.sent.append(
            {
                "chat_type": chat_type,
                "message": message,
                "user_id": user_id,
                "group_id": group_id,
                "images": images or [],
                "attachments": attachments or [],
            }
        )
        return {"ok": True}


class FailingHermes:
    last_usage = {}

    def chat(self, messages, session_id, session_key):
        raise RuntimeError("boom")


class ProfileAwareScheduledHermes:
    def __init__(self):
        self.profile_calls = []
        self.last_usage = {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9}

    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.profile_calls.append((profile_id, messages, session_id, session_key))
        return "Vera: 该去做计划啦，我会在这里等你回来。"


def test_due_scheduled_job_runs_hermes_and_delivers_to_hermi_and_qq(tmp_path: Path):
    hermes = ScheduledHermes()
    qlos = CaptureQlos()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes, qlos_client=qlos))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "主动任务"}).json()
    job = client.post(
        "/scheduled-jobs",
        headers=headers,
        json={
            "kind": "once",
            "schedule": "once:+0m",
            "summary": "检查 QQ 并汇报",
            "target": {
                "delivery": ["hermi", "qq"],
                "conversation_id": conversation["conversation_id"],
                "qq": {"chat_type": "private", "user_id": "1000000001"},
            },
            "payload": {"content": "到时间后检查 QQ，有结果就汇报。", "report_to_qq": True},
        },
    ).json()

    result = client.post("/scheduler/run-once", headers=headers).json()
    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]
    events = client.get(f"/tasks/{job['task_id']}/events", headers=headers).json()["events"]

    assert result["processed"] == 1
    assert result["jobs"][0]["delivery"]["hermi"] is True
    assert result["jobs"][0]["delivery"]["qq"] is True
    assert hermes.calls[0]["session_id"].startswith("hermi-scheduled-")
    assert "到时间后检查 QQ" in "\n".join(item["content"] for item in hermes.calls[0]["messages"])
    assert messages[-1]["content"] == "主动任务完成：已经检查并生成汇报。"
    assert qlos.sent == [
        {
            "chat_type": "private",
            "message": "主动任务完成：已经检查并生成汇报。",
            "user_id": "1000000001",
            "group_id": None,
            "images": [],
            "attachments": [],
        }
    ]
    assert any(event["event_type"] == "scheduled_job_completed" for event in events)


def test_scheduled_job_uses_conversation_profile_finishes_task_and_delivers_to_qq(tmp_path: Path):
    hermes = ProfileAwareScheduledHermes()
    qlos = CaptureQlos()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes, qlos_client=qlos))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post(
        "/conversations", headers=headers, json={"title": "Vera reminder", "profile_id": "maid"}
    ).json()
    job = client.post(
        "/scheduled-jobs",
        headers=headers,
        json={
            "kind": "once",
            "schedule": "once:+0m",
            "summary": "Plan reminder",
            "target": {
                "delivery": ["hermi", "qq"],
                "conversation_id": conversation["conversation_id"],
                "qq": {"chat_type": "private", "user_id": "friend-qq"},
            },
            "payload": {"content": "请自然提醒我开始做计划"},
        },
    ).json()

    assert client.post("/scheduler/run-once", headers=headers).json()["processed"] == 1
    assert hermes.profile_calls[0][0] == "maid"
    assert qlos.sent[0]["user_id"] == "friend-qq"
    assert "该去做计划啦" in qlos.sent[0]["message"]
    task = next(
        task
        for task in client.get("/tasks", headers=headers).json()["tasks"]
        if task["task_id"] == job["task_id"]
    )
    assert task["status"] == "completed"


def test_cron_due_supports_ranges_lists_and_steps():
    baseline = time.mktime(time.strptime("2026-07-09 00:09:00", "%Y-%m-%d %H:%M:%S"))
    now = baseline + 90 * 60
    weekday_job = {
        "kind": "cron",
        "schedule": "*/15 0-2 * * 1-5",
        "created_at": baseline,
        "last_run_at": baseline,
    }
    listed_job = {
        "kind": "cron",
        "schedule": "30 1,3,5 * * *",
        "created_at": baseline,
        "last_run_at": baseline,
    }
    invalid_job = {
        "kind": "cron",
        "schedule": "not cron",
        "created_at": baseline,
        "last_run_at": baseline,
    }

    assert _scheduled_job_due(weekday_job, now) is True
    assert _scheduled_job_due(listed_job, now) is True
    assert _scheduled_job_due(invalid_job, now) is False


def test_scheduled_job_pause_resume_run_now_history_and_retry(tmp_path: Path):
    hermes = ScheduledHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=hermes, qlos_client=CaptureQlos()))
    headers = {"Authorization": "Bearer owner-token"}
    job = client.post(
        "/scheduled-jobs",
        headers=headers,
        json={
            "kind": "interval",
            "schedule": "interval:1h",
            "summary": "manual run smoke",
            "target": {"delivery": ["hermi", "qq"]},
            "payload": {"content": "manual"},
            "policy": {"allowed_delivery": ["hermi"]},
            "max_retries": 2,
        },
    ).json()

    paused = client.post(f"/scheduled-jobs/{job['job_id']}/pause", headers=headers).json()
    resumed = client.post(f"/scheduled-jobs/{job['job_id']}/resume", headers=headers).json()
    result = client.post(f"/scheduled-jobs/{job['job_id']}/run-now", headers=headers).json()
    runs = client.get(f"/scheduled-jobs/{job['job_id']}/runs", headers=headers).json()["runs"]

    assert paused["status"] == "paused"
    assert resumed["status"] == "active"
    assert result["delivery"]["hermi"] is True
    assert result["delivery"]["qq"] is False
    assert runs[0]["status"] == "active"
    assert "prompt_tokens" in runs[0]["token_json"]


def test_scheduled_job_failure_records_retry_history(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=FailingHermes(), qlos_client=CaptureQlos()))
    headers = {"Authorization": "Bearer owner-token"}
    job = client.post(
        "/scheduled-jobs",
        headers=headers,
        json={
            "kind": "once",
            "schedule": "once:+0m",
            "summary": "fail once",
            "target": {"delivery": ["hermi"]},
            "payload": {"content": "fail"},
            "policy": {"retry": {"backoff_seconds": 5}},
            "max_retries": 1,
        },
    ).json()

    result = client.post("/scheduler/run-once", headers=headers).json()["jobs"][0]
    detail = client.get(f"/scheduled-jobs/{job['job_id']}", headers=headers).json()
    runs = client.get(f"/scheduled-jobs/{job['job_id']}/runs", headers=headers).json()["runs"]

    assert result["will_retry"] is True
    assert detail["status"] == "active"
    assert detail["retry_count"] == 1
    assert detail["next_run_after"] is not None
    assert runs[0]["status"] == "failed"

