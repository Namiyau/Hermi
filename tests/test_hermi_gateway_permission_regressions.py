from pathlib import Path
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class TrackingAdapter:
    def __init__(self):
        self.calls = 0
        self.last_messages = []

    def chat(self, messages, session_id, session_key):
        self.calls += 1
        self.last_messages = messages
        return "should not run"


class SlowTrackingAdapter(TrackingAdapter):
    def chat(self, messages, session_id, session_key):
        self.calls += 1
        self.last_messages = messages
        time.sleep(0.15)
        return "approved once"


class NaturalReplyAdapter(TrackingAdapter):
    def chat(self, messages, session_id, session_key):
        self.calls += 1
        self.last_messages = messages
        return "当然记得你，小A。"


class OwnerScheduledActionAdapter(TrackingAdapter):
    def chat(self, messages, session_id, session_key):
        self.calls += 1
        self.last_messages = messages
        if session_id.startswith("hermi-scheduled-"):
            return "提醒时间到了，去做计划吧。"
        return (
            "好，我会在时间到时提醒你。\n"
            "<<<HERMI_ACTION\n"
            '{"type":"scheduled.create","kind":"once","schedule":"once:+0m",'
            '"summary":"提醒我去做计划","content":"提醒我去做计划"}\n'
            ">>>"
        )


class NativeCronAttemptAdapter(TrackingAdapter):
    def chat(self, messages, session_id, session_key):
        self.calls += 1
        self.last_messages = messages
        return ""


def _setup(tmp_path: Path, permissions: dict):
    adapter = TrackingAdapter()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    app = create_app(config, hermes_adapter=adapter)
    client = TestClient(app)
    owner = {"Authorization": "Bearer owner-token"}
    friend = {"Authorization": "Bearer friend-token"}
    client.post(
        "/admin/users",
        headers=owner,
        json={
            "user_id": "friend:test",
            "display_name": "Friend",
            "token": "friend-token",
            "permissions": {"chat": "allow"},
        },
    )
    conversation = client.post("/conversations", headers=friend, json={"title": "testA"}).json()
    client.patch(
        "/admin/users/friend:test",
        headers=owner,
        json={"permissions": permissions},
    )
    return config, client, adapter, owner, friend, conversation


def test_friend_chat_cron_approval_stops_before_hermes_and_creates_approval(tmp_path: Path):
    _, client, adapter, owner, friend, conversation = _setup(
        tmp_path,
        {"chat": "allow", "cron": "approval", "manage_scheduled": "deny"},
    )

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=friend,
        json={"content": "帮我定时1分钟后叫我！"},
    ) as response:
        body = response.read().decode("utf-8")

    approvals = client.get("/approvals", headers=owner).json()["approvals"]
    assert response.status_code == 200
    assert adapter.calls == 0
    assert len(approvals) == 1
    assert approvals[0]["action_type"] == "scheduled.create"
    assert approvals[0]["source"] == "permission"
    assert "审批" in body


def test_friend_mixed_reminder_keeps_normal_chat_reply_and_creates_approval(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    adapter = NaturalReplyAdapter()
    client = TestClient(create_app(config, hermes_adapter=adapter))
    owner = {"Authorization": "Bearer owner-token"}
    friend = {"Authorization": "Bearer friend-token"}
    client.post(
        "/admin/users",
        headers=owner,
        json={
            "user_id": "friend:test",
            "display_name": "Friend",
            "token": "friend-token",
            "permissions": {"chat": "allow", "cron": "approval"},
        },
    )
    conversation = client.post("/conversations", headers=friend, json={"title": "testA"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "请问你还记得我吗！？能否5分钟后提醒我！？"},
    )

    approvals = client.get("/approvals", headers=owner).json()["approvals"]
    assert response.status_code == 200
    assert adapter.calls == 1
    assert "当然记得你" in response.json()["assistant"]["content"]
    assert len(approvals) == 1
    assert approvals[0]["action_type"] == "scheduled.create"
    assert "提醒" in approvals[0]["summary"]


def test_owner_scheduled_action_uses_hermi_scheduler_and_delivers_to_conversation(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
        scheduler_enabled=True,
    )
    adapter = OwnerScheduledActionAdapter()
    client = TestClient(create_app(config, hermes_adapter=adapter))
    owner = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=owner, json={"title": "Owner cron"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=owner,
        json={"content": "现在提醒我去做计划"},
    )

    jobs = client.get("/scheduled-jobs", headers=owner).json()["scheduled_jobs"]
    approvals = client.get("/approvals", headers=owner).json()["approvals"]
    assert response.status_code == 200
    assert len(jobs) == 1
    assert approvals == []

    run = client.post("/scheduler/run-once", headers=owner)
    messages = client.get(f"/conversations/{conversation['conversation_id']}/messages", headers=owner).json()["messages"]
    assert run.json()["processed"] == 1
    assert any("提醒时间到了" in message["content"] for message in messages)


def test_owner_plain_reminder_is_captured_before_hermes_native_cron(tmp_path: Path, monkeypatch):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    adapter = NativeCronAttemptAdapter()
    monkeypatch.setattr("hermi_gateway.app._maybe_create_native_hermes_cron", lambda *args: "native cron must not run")
    client = TestClient(create_app(config, hermes_adapter=adapter))
    owner = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=owner, json={"title": "Owner reminder"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=owner,
        json={"content": "1分钟后提醒我去做计划"},
    )

    jobs = client.get("/scheduled-jobs", headers=owner).json()["scheduled_jobs"]
    assert response.status_code == 200
    assert adapter.calls == 0
    assert len(jobs) == 1
    assert jobs[0]["schedule"] == "once:+1m"
    assert "安排好了" in response.json()["assistant"]["content"]


def test_friend_chat_cron_deny_stops_before_hermes(tmp_path: Path):
    _, client, adapter, owner, friend, conversation = _setup(
        tmp_path,
        {"chat": "allow", "cron": "deny"},
    )

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=friend,
        json={"content": "一分钟后提醒我"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert adapter.calls == 0
    assert client.get("/approvals", headers=owner).json()["approvals"] == []
    assert "禁止" in body


def test_chat_deny_blocks_message_endpoint(tmp_path: Path):
    _, client, adapter, _, friend, conversation = _setup(tmp_path, {"chat": "deny"})
    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "hello"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "permission_denied:chat"
    assert adapter.calls == 0


def test_cancel_active_run_marks_backend_cancelled(tmp_path: Path):
    config, client, _, _, friend, conversation = _setup(tmp_path, {"chat": "allow"})
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    run = conn.execute(
        "insert into message_runs (run_id, conversation_id, user_id, status, events_json, final_json, error, created_at, updated_at) "
        "values ('run-cancel', ?, 'friend:test', 'running', '[]', '{}', '', 1, 1) returning *",
        (conversation["conversation_id"],),
    ).fetchone()
    conn.commit()
    assert run is not None

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/runs/cancel",
        headers=friend,
    )
    status = conn.execute(
        "select status from message_runs where run_id = 'run-cancel'"
    ).fetchone()["status"]
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert status == "cancelled"


def test_friend_can_delete_own_conversation_but_not_owner_conversation(tmp_path: Path):
    _, client, _, owner, friend, conversation = _setup(tmp_path, {"chat": "allow"})
    owner_conversation = client.post("/conversations", headers=owner, json={"title": "owner"}).json()
    assert client.delete(f"/conversations/{conversation['conversation_id']}", headers=friend).status_code == 200
    assert client.delete(f"/conversations/{owner_conversation['conversation_id']}", headers=friend).status_code == 403


def test_chat_approval_logs_in_and_waits_for_owner_before_calling_hermes(tmp_path: Path):
    _, client, adapter, owner, friend, conversation = _setup(tmp_path, {"chat": "approval"})
    assert client.get("/me", headers=friend).status_code == 200

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "hello approval"},
    )
    approval = client.get("/approvals", headers=owner).json()["approvals"][0]
    assert response.status_code == 200
    assert adapter.calls == 0
    assert approval["action_type"] == "chat.message"

    decided = client.post(
        f"/approvals/{approval['approval_id']}/decision",
        headers=owner,
        json={"decision": "once"},
    )
    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=friend
    ).json()["messages"]
    assert decided.status_code == 200
    assert adapter.calls == 1
    assert adapter.last_messages[-1]["role"] == "user"
    assert "hello approval" in adapter.last_messages[-1]["content"]
    assert any("should not run" in message["content"] for message in messages)


def test_denied_approval_writes_friend_visible_message(tmp_path: Path):
    _, client, _, owner, friend, conversation = _setup(
        tmp_path, {"chat": "allow", "cron": "approval", "manage_scheduled": "deny"}
    )
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "1分钟后提醒我"},
    )
    approval = client.get("/approvals", headers=owner).json()["approvals"][0]
    client.post(
        f"/approvals/{approval['approval_id']}/decision",
        headers=owner,
        json={"decision": "deny"},
    )
    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=friend
    ).json()["messages"]
    assert any("拒绝" in message["content"] for message in messages)


def test_friend_can_list_and_delete_own_approved_job_without_manage_permission(tmp_path: Path):
    _, client, _, owner, friend, conversation = _setup(
        tmp_path, {"chat": "allow", "cron": "approval", "manage_scheduled": "deny"}
    )
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "1分钟后提醒我"},
    )
    approval = client.get("/approvals", headers=owner).json()["approvals"][0]
    client.post(
        f"/approvals/{approval['approval_id']}/decision",
        headers=owner,
        json={"decision": "once"},
    )
    jobs = client.get("/scheduled-jobs", headers=friend)
    assert jobs.status_code == 200
    assert len(jobs.json()["scheduled_jobs"]) == 1
    assert jobs.json()["scheduled_jobs"][0]["created_by_display_name"] == "Friend"
    assert client.delete(
        f"/scheduled-jobs/{jobs.json()['scheduled_jobs'][0]['job_id']}", headers=friend
    ).status_code == 200


def test_plain_reminder_complaint_is_not_misclassified_as_new_cron(tmp_path: Path):
    _, client, adapter, owner, friend, conversation = _setup(
        tmp_path, {"chat": "allow", "cron": "approval"}
    )
    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "你也没提醒我！"},
    )
    assert response.status_code == 200
    assert adapter.calls == 1
    assert client.get("/approvals", headers=owner).json()["approvals"] == []


def test_repeated_approval_clicks_execute_chat_message_only_once(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    adapter = SlowTrackingAdapter()
    client = TestClient(create_app(config, hermes_adapter=adapter))
    owner = {"Authorization": "Bearer owner-token"}
    friend = {"Authorization": "Bearer friend-token"}
    client.post(
        "/admin/users",
        headers=owner,
        json={
            "user_id": "friend:test",
            "display_name": "Friend",
            "token": "friend-token",
            "permissions": {"chat": "approval"},
        },
    )
    conversation = client.post("/conversations", headers=friend, json={"title": "repeat"}).json()
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "hello once"},
    )
    approval = client.get("/approvals", headers=owner).json()["approvals"][0]

    def decide():
        return client.post(
            f"/approvals/{approval['approval_id']}/decision",
            headers=owner,
            json={"decision": "once"},
        ).status_code

    with ThreadPoolExecutor(max_workers=3) as executor:
        statuses = list(executor.map(lambda _: decide(), range(3)))

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=friend
    ).json()["messages"]
    assert sorted(statuses) == [200, 409, 409]
    assert adapter.calls == 1
    assert sum(message["content"] == "approved once" for message in messages) == 1


def test_friend_cannot_manage_owner_scheduled_job_even_with_manage_permission(tmp_path: Path):
    _, client, _, owner, friend, _ = _setup(
        tmp_path, {"chat": "allow", "manage_scheduled": "allow"}
    )
    job = client.post(
        "/scheduled-jobs",
        headers=owner,
        json={
            "kind": "once",
            "schedule": "once:+10m",
            "summary": "owner private job",
            "payload": {"content": "owner only"},
        },
    ).json()

    assert client.get(f"/scheduled-jobs/{job['job_id']}", headers=friend).status_code == 403
    assert client.delete(f"/scheduled-jobs/{job['job_id']}", headers=friend).status_code == 403
    assert client.post(f"/scheduled-jobs/{job['job_id']}/pause", headers=friend).status_code == 403
    assert client.post(f"/scheduled-jobs/{job['job_id']}/resume", headers=friend).status_code == 403
    assert client.post(f"/scheduled-jobs/{job['job_id']}/run-now", headers=friend).status_code == 403
    assert client.get(f"/scheduled-jobs/{job['job_id']}/runs", headers=friend).status_code == 403
    assert client.post("/scheduler/run-once", headers=friend).status_code == 403


def test_friend_media_permission_does_not_expose_or_delete_owner_private_files(tmp_path: Path):
    _, client, _, owner, friend, conversation = _setup(
        tmp_path, {"chat": "allow", "media": {"mode": "allow", "max_size_mb": 5}}
    )
    owner_conversation = client.post("/conversations", headers=owner, json={"title": "owner files"}).json()
    owner_file = client.post(
        "/files",
        headers=owner,
        data={"conversation_id": owner_conversation["conversation_id"], "visibility": "private"},
        files={"upload": ("owner.txt", b"owner secret", "text/plain")},
    ).json()

    listed = client.get("/files", headers=friend).json()["files"]
    assert owner_file["file_id"] not in {item["file_id"] for item in listed}
    assert client.get(f"/files/{owner_file['file_id']}", headers=friend).status_code == 404
    assert client.delete(f"/files/{owner_file['file_id']}", headers=friend).status_code == 403

    own_file = client.post(
        "/files",
        headers=friend,
        data={"conversation_id": conversation["conversation_id"], "visibility": "private"},
        files={"upload": ("friend.txt", b"friend data", "text/plain")},
    ).json()
    assert client.delete(f"/files/{own_file['file_id']}", headers=friend).status_code == 200
