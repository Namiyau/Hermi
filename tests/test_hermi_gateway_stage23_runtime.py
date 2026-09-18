from pathlib import Path
import threading
import time

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class ProfileAdapter:
    def __init__(self):
        self.calls = []
        self.last_usage = {}

    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        self.last_usage = {"total_tokens": 7}
        return f"{profile_id} reply {len(self.calls)}"


class SelectingProfileAdapter(ProfileAdapter):
    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        self.last_usage = {"total_tokens": 3}
        return "imouto" if profile_id == "maid" else f"{profile_id} selected reply"


class BlockingProfileAdapter(ProfileAdapter):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        self.started.set()
        self.release.wait(timeout=5)
        self.last_usage = {"total_tokens": 2}
        return f"{profile_id} resumed reply"


class OneMemberFailsAdapter(ProfileAdapter):
    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        if profile_id == "trainee":
            raise RuntimeError("trainee unavailable")
        self.last_usage = {"total_tokens": 5}
        return f"{profile_id} still replied"


class StreamingProfileAdapter(ProfileAdapter):
    def stream_profile_events(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        yield {"event": "thought", "content": f"{profile_id} thinking"}
        yield {"event": "tool", "content": f"{profile_id}: tool.completed"}
        yield {"event": "final", "content": f"{profile_id} streamed reply"}
        self.last_usage = {"total_tokens": 11}


class DirectedDiscussionAdapter(ProfileAdapter):
    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        self.last_usage = {"total_tokens": 4}
        if profile_id == "trainee":
            return "我先提出观点，请小墨接着分析。\nNEXT: imouto"
        if profile_id == "imouto":
            return "补充完成，可以结束讨论。\nNEXT: END"
        return "会议纪要"


class LongReplyAdapter(ProfileAdapter):
    def chat_profile(self, profile_id, messages, session_id, session_key):
        self.calls.append((profile_id, messages, session_id, session_key))
        self.last_usage = {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}
        return f"{profile_id}:" + ("长内容" * 5000)


def _client(tmp_path: Path, monkeypatch, adapter: ProfileAdapter) -> TestClient:
    local = tmp_path / "local"
    root = local / "hermes"
    for profile_id, model in (
        ("trainee", "mimo-v2.5-free"),
        ("imouto", "deepseek-v4-flash-free"),
        ("maid", "nemotron-3-ultra-free"),
    ):
        path = root / "profiles" / profile_id
        path.mkdir(parents=True, exist_ok=True)
        (path / "config.yaml").write_text(
            f"model:\n  default: {model}\n  provider: opencode-zen\n", encoding="utf-8"
        )
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
    )
    return TestClient(create_app(config, hermes_adapter=adapter))


def test_stage23_primary_profile_names_and_channel_routes(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}

    profiles = client.get("/profiles", headers=headers).json()["profiles"]
    status = client.get("/brain/status", headers=headers).json()

    assert {item["profile_id"]: item["display_name"] for item in profiles} == {
        "trainee": "薇达(Veda)",
        "imouto": "小墨(Ember)",
        "maid": "薇拉(Vera)",
    }
    assert status["channel_profiles"] == {"qq": "trainee", "hermi": "maid", "meeting_host": "maid"}


def test_pair_review_calls_two_real_profiles_for_two_rounds_and_records_metadata(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={
            "name": "review",
            "mode": "pair_review",
            "host_agent_id": "profile:maid",
            "permission_level": "smart",
            "max_turns": 2,
        },
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "检查权限设计", "max_turns": 2},
    )
    steps = client.get(f"/workflow-runs/{run.json()['run_id']}/steps", headers=headers).json()["steps"]

    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert [call[0] for call in adapter.calls] == ["trainee", "imouto", "trainee", "imouto"]
    assert len({call[2] for call in adapter.calls}) == 4
    member_steps = [step for step in steps if step["agent_id"] in {"profile:trainee", "profile:imouto"}]
    assert len(member_steps) == 4
    assert all(step["session_id"] and step["usage_json"] == '{"total_tokens": 7}' for step in member_steps)
    assert "写入、命令、外部发送必须审批" in adapter.calls[0][1][0]["content"]

    detail = client.get(f"/workflow-runs/{run.json()['run_id']}", headers=headers).json()
    assert detail["usage"] == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 28}


def test_pair_review_requires_exactly_two_non_host_members(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "review", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    client.post(
        f"/rooms/{room['room_id']}/members",
        headers=headers,
        json={"agent_id": "profile:trainee", "role": "participant"},
    )

    response = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "不足成员", "max_turns": 2},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "pair_review_requires_two_participants"


def test_auto_single_asks_vera_host_to_select_one_member(tmp_path: Path, monkeypatch):
    adapter = SelectingProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "auto", "mode": "auto_single"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "auto_single", "topic": "挑选最适合的成员", "max_turns": 9},
    )

    assert run.status_code == 200
    assert [call[0] for call in adapter.calls] == ["maid", "imouto"]
    steps = client.get(
        f"/workflow-runs/{run.json()['run_id']}/steps", headers=headers
    ).json()["steps"]
    assert len(steps) == 1
    assert steps[0]["agent_id"] == "profile:imouto"


def test_conversation_can_be_renamed_and_room_can_be_deleted(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch, ProfileAdapter())
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post(
        "/conversations", headers=headers, json={"title": "旧名称"}
    ).json()
    renamed = client.patch(
        f"/conversations/{conversation['conversation_id']}",
        headers=headers,
        json={"title": "新名称"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "新名称"

    room = client.post("/rooms", headers=headers, json={"name": "待删除会议"}).json()
    deleted = client.delete(f"/rooms/{room['room_id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert client.get(f"/rooms/{room['room_id']}", headers=headers).status_code == 404


def test_running_room_requires_cancel_and_history_can_be_exported(tmp_path: Path, monkeypatch):
    client = _client(tmp_path, monkeypatch, ProfileAdapter())
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post("/rooms", headers=headers, json={"name": "阶段三会议"}).json()
    client.post(
        f"/rooms/{room['room_id']}/members",
        headers=headers,
        json={"agent_id": "profile:trainee", "role": "participant"},
    )
    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"topic": "导出测试", "background": False},
    ).json()
    exported = client.get(f"/rooms/{room['room_id']}/export", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["room"]["name"] == "阶段三会议"
    assert exported.json()["runs"][0]["topic"] == "导出测试"
    assert exported.json()["runs"][0]["steps"]

    client.app.state.db.execute(
        "update workflow_runs set status = 'paused' where run_id = ?", (run["run_id"],)
    )
    client.app.state.db.commit()
    assert client.delete(f"/rooms/{room['room_id']}", headers=headers).status_code == 409
    cancelled = client.post(f"/workflow-runs/{run['run_id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.delete(f"/rooms/{room['room_id']}", headers=headers).status_code == 200


def test_background_meeting_pauses_before_late_reply_is_saved_and_resumes(tmp_path: Path, monkeypatch):
    adapter = BlockingProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "pause", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "pause test", "max_turns": 1, "background": True},
    ).json()
    assert run["status"] == "running"
    assert adapter.started.wait(timeout=2)

    paused = client.post(f"/workflow-runs/{run['run_id']}/stop", headers=headers)
    adapter.release.set()
    time.sleep(0.2)
    steps_while_paused = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert steps_while_paused == []

    resumed = client.post(f"/workflow-runs/{run['run_id']}/resume", headers=headers)
    deadline = time.time() + 4
    current = resumed.json()
    while current["status"] != "completed" and time.time() < deadline:
        time.sleep(0.05)
        current = client.get(f"/workflow-runs/{run['run_id']}", headers=headers).json()

    assert current["status"] == "completed"
    assert len(client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]) == 2


def test_room_detail_and_run_list_support_meeting_ui(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post("/rooms", headers=headers, json={"name": "UI room"}).json()
    client.post(
        f"/rooms/{room['room_id']}/members",
        headers=headers,
        json={"agent_id": "profile:trainee", "role": "participant"},
    )
    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"topic": "UI topic", "max_turns": 1},
    ).json()

    detail = client.get(f"/rooms/{room['room_id']}", headers=headers)
    runs = client.get(f"/rooms/{room['room_id']}/workflows", headers=headers)

    assert detail.status_code == 200
    assert {item["agent_id"] for item in detail.json()["members"]} == {"profile:maid", "profile:trainee"}
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == run["run_id"]


def test_meeting_steps_include_actor_identity_for_message_ui(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "identity", "mode": "auto_single", "host_agent_id": "profile:maid"},
    ).json()
    client.post(
        f"/rooms/{room['room_id']}/members",
        headers=headers,
        json={"agent_id": "profile:trainee", "role": "participant"},
    )
    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "auto_single", "topic": "身份展示", "max_turns": 1},
    ).json()

    steps = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert all(step["actor"]["actor_id"].startswith("profile:") for step in steps)
    assert all(step["actor"]["display_name"] for step in steps)
    assert all(step["actor"]["actor_type"] == "ai" for step in steps)
    assert all("avatar" in step["actor"] for step in steps)


def test_project_meeting_records_member_turns_and_host_summary(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "project", "mode": "project_meeting", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "project_meeting", "topic": "形成计划", "max_turns": 1},
    ).json()
    steps = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert run["status"] == "completed"
    assert [call[0] for call in adapter.calls] == ["trainee", "imouto", "maid"]
    assert len(steps) == 3
    assert steps[-1]["agent_id"] == "profile:maid"
    assert "整理会议纪要" in adapter.calls[-1][1][-1]["content"]


def test_engineering_pipeline_runs_six_stages_for_every_member(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "pipeline", "mode": "engineering_pipeline", "host_agent_id": "profile:maid"},
    ).json()
    client.post(
        f"/rooms/{room['room_id']}/members",
        headers=headers,
        json={"agent_id": "profile:trainee", "role": "participant"},
    )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "engineering_pipeline", "topic": "交付功能", "max_turns": 1},
    ).json()
    steps = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert run["status"] == "completed"
    assert len(adapter.calls) == 12
    assert len(steps) == 12
    merged = "\n".join(call[1][-1]["content"] for call in adapter.calls)
    for stage in ("需求", "设计", "计划", "执行", "测试", "审查"):
        assert f"当前阶段：{stage}" in merged


def test_member_failure_is_recorded_and_other_member_continues(tmp_path: Path, monkeypatch):
    adapter = OneMemberFailsAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "failure", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "错误隔离", "max_turns": 1},
    ).json()
    steps = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert run["status"] == "completed"
    assert len(steps) == 2
    assert "RuntimeError: trainee unavailable" in steps[0]["error"]
    assert steps[1]["content"] == "imouto still replied"


def test_meeting_stream_trace_is_saved_with_each_member_step(tmp_path: Path, monkeypatch):
    adapter = StreamingProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "trace", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "trace", "max_turns": 1},
    ).json()
    steps = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert len(steps) == 2
    assert all(step["trace"] == [
        {"event": "thought", "content": f"{step['actor']['actor_id'].split(':', 1)[1]} thinking"},
        {"event": "tool", "content": f"{step['actor']['actor_id'].split(':', 1)[1]}: tool.completed"},
    ] for step in steps)
    assert all(step["content"].endswith("streamed reply") for step in steps)


def test_project_meeting_members_can_choose_next_speaker_and_end_early(tmp_path: Path, monkeypatch):
    adapter = DirectedDiscussionAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "free", "mode": "project_meeting", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "project_meeting", "topic": "自由讨论", "max_turns": 4},
    ).json()
    steps = client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]

    assert [call[0] for call in adapter.calls] == ["trainee", "imouto", "maid"]
    assert len(steps) == 3
    assert all("NEXT:" not in step["content"] for step in steps)
    assert steps[0]["metadata_json"].find('"next_speaker": "imouto"') >= 0
    assert steps[1]["metadata_json"].find('"discussion_end": true') >= 0


def test_repeated_stop_resume_is_stable_and_finished_thread_is_removed(tmp_path: Path, monkeypatch):
    adapter = BlockingProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "repeat", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )
    run = client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "重复操作", "max_turns": 1, "background": True},
    ).json()
    assert adapter.started.wait(timeout=2)

    first_stop = client.post(f"/workflow-runs/{run['run_id']}/stop", headers=headers).json()
    second_stop = client.post(f"/workflow-runs/{run['run_id']}/stop", headers=headers).json()
    first_resume = client.post(f"/workflow-runs/{run['run_id']}/resume", headers=headers).json()
    second_resume = client.post(f"/workflow-runs/{run['run_id']}/resume", headers=headers).json()
    adapter.release.set()

    deadline = time.time() + 4
    current = second_resume
    while current["status"] != "completed" and time.time() < deadline:
        time.sleep(0.05)
        current = client.get(f"/workflow-runs/{run['run_id']}", headers=headers).json()

    assert first_stop["status"] == second_stop["status"] == "paused"
    assert first_resume["status"] == second_resume["status"] == "running"
    assert current["status"] == "completed"
    assert len(client.get(f"/workflow-runs/{run['run_id']}/steps", headers=headers).json()["steps"]) == 2
    assert run["run_id"] not in client.app.state.workflow_threads


def test_meeting_context_is_compacted_before_later_member_calls(tmp_path: Path, monkeypatch):
    adapter = LongReplyAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = client.post(
        "/rooms",
        headers=headers,
        json={"name": "budget", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )

    client.post(
        f"/rooms/{room['room_id']}/workflows",
        headers=headers,
        json={"mode": "pair_review", "topic": "上下文预算", "max_turns": 2},
    )

    later_prompts = [call[1][-1]["content"] for call in adapter.calls[1:]]
    assert all(len(prompt) < 9000 for prompt in later_prompts)
    assert any("[会议上下文已压缩]" in prompt for prompt in later_prompts)


def test_restart_marks_running_meeting_recoverable_and_resume_skips_saved_steps(tmp_path: Path, monkeypatch):
    first_adapter = ProfileAdapter()
    first_client = _client(tmp_path, monkeypatch, first_adapter)
    headers = {"Authorization": "Bearer owner-token"}
    room = first_client.post(
        "/rooms",
        headers=headers,
        json={"name": "restart", "mode": "pair_review", "host_agent_id": "profile:maid"},
    ).json()
    for profile_id in ("trainee", "imouto"):
        first_client.post(
            f"/rooms/{room['room_id']}/members",
            headers=headers,
            json={"agent_id": f"profile:{profile_id}", "role": "participant"},
        )
    conn = first_client.app.state.db
    now = time.time()
    conn.execute(
        "insert into workflow_runs (run_id, room_id, mode, status, max_turns, topic, state_json, created_at, updated_at) values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("run-restart", room["room_id"], "pair_review", "running", 1, "恢复测试", "{}", now, now),
    )
    conn.execute(
        "insert into workflow_steps (step_id, run_id, step_index, agent_id, role, content, created_at, session_id, usage_json, error, metadata_json) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("step-existing", "run-restart", 0, "profile:trainee", "participant", "saved reply", now, "saved-session", "{}", "", "{}"),
    )
    conn.commit()

    second_adapter = ProfileAdapter()
    second_client = _client(tmp_path, monkeypatch, second_adapter)
    paused = second_client.get("/workflow-runs/run-restart", headers=headers).json()
    resumed = second_client.post("/workflow-runs/run-restart/resume", headers=headers).json()
    deadline = time.time() + 4
    current = resumed
    while current["status"] != "completed" and time.time() < deadline:
        time.sleep(0.05)
        current = second_client.get("/workflow-runs/run-restart", headers=headers).json()
    steps = second_client.get("/workflow-runs/run-restart/steps", headers=headers).json()["steps"]

    assert paused["status"] == "paused"
    assert "service_restart" in paused["state_json"]
    assert current["status"] == "completed"
    assert [call[0] for call in second_adapter.calls] == ["imouto"]
    assert [step["step_index"] for step in steps] == [0, 1]


def test_empty_approval_expiry_scan_does_not_leave_database_locked(tmp_path: Path, monkeypatch):
    adapter = ProfileAdapter()
    client = _client(tmp_path, monkeypatch, adapter)
    headers = {"Authorization": "Bearer owner-token"}

    assert client.get("/approvals", headers=headers).status_code == 200

    conn = client.app.state.db
    assert conn.in_transaction is False
