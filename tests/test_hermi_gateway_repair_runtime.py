import json
from pathlib import Path

from fastapi.testclient import TestClient

import hermi_gateway.app as app_module
from hermi_gateway.app import _bearer_token, create_app
from hermi_gateway.app import _friendly_hermes_failure_reply, _scheduled_request_missing_action_reply
from hermi_gateway.app import _create_message_run, _fail_message_run, _finish_message_run, _message_run_by_id
from hermi_gateway.config import HermiConfig
from hermi_gateway.db import create_seed_users, init_db, verify_token
from hermi_gateway.hermes import _session_turn_assistant_text
from hermi_gateway.hermes import _stream_event_from_chunk
from hermi_gateway.hermes import HermesAdapter


def test_config_uses_qlos_hermes_key_when_hermi_key_is_missing():
    config = HermiConfig.from_env({"QLOS_HERMES_API_KEY": "qlos-secret"})

    assert config.hermes_api_key == "qlos-secret"


def test_config_defaults_use_readable_documents_paths():
    config = HermiConfig.from_env({})

    assert "Hermi资料" in str(config.media_dir)
    assert "state" in str(config.qlos_log_dir)
    assert "璧勬枡" not in str(config.media_dir)
    assert "鑷" not in str(config.qlos_log_dir)


def test_bearer_token_and_verify_token_normalize_values(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    create_seed_users(conn, owner_token="owner-secret", channel_token="channel-secret")

    assert _bearer_token(" Bearer owner-secret ") == "owner-secret"
    assert verify_token(conn, " owner-secret ")["role"] == "owner"
    assert verify_token(conn, object()) is None


def test_health_endpoint_does_not_require_threadpool_dependency(tmp_path: Path):
    config = HermiConfig(db_path=tmp_path / "hermi.db")
    client = TestClient(create_app(config))

    assert client.get("/health").json() == {"status": "ok", "service": "hermi-gateway"}


def test_hermes_stream_parser_forwards_tool_progress_events():
    event = _stream_event_from_chunk(
        {"name": "terminal", "phase": "start"},
        event_name="hermes.tool.progress",
    )

    assert event["event"] == "tool"
    assert "terminal" in event["content"]
    assert "start" in event["content"]


def test_hermes_stream_parser_understands_runs_events():
    delta = _stream_event_from_chunk({"event": "message.delta", "delta": "OK"})
    assistant_delta = _stream_event_from_chunk({"event": "assistant.delta", "delta": "planning"})
    thought = _stream_event_from_chunk({"event": "reasoning.available", "text": "used memory"})
    named_thought = _stream_event_from_chunk({"text": "live reasoning"}, event_name="reasoning.delta")
    named_tool = _stream_event_from_chunk({"name": "terminal", "phase": "tool.started"}, event_name="tool.progress")
    final = _stream_event_from_chunk({"event": "run.completed", "output": "done"})

    assert delta == {"event": "final_delta", "content": "OK"}
    assert assistant_delta == {"event": "assistant_delta", "content": "planning"}
    assert thought == {"event": "thought", "content": "used memory"}
    assert named_thought == {"event": "thought", "content": "live reasoning"}
    assert named_tool["event"] == "tool"
    assert "terminal" in named_tool["content"]
    assert final == {"event": "final", "content": "done"}


def test_session_turn_separates_tool_progress_from_final_reply():
    before = [{"id": "previous", "role": "assistant", "content": "older reply"}]
    after = [
        *before,
        {"id": "step-1", "role": "assistant", "content": "I will inspect the folder first."},
        {"id": "tool-1", "role": "tool", "content": "{}"},
        {"id": "step-2", "role": "assistant", "content": "I found the target folder."},
        {"id": "final", "role": "assistant", "content": "The folder contains 494 files."},
    ]

    thought, final = _session_turn_assistant_text(after, {"previous"})

    assert thought == ["I will inspect the folder first.", "I found the target folder."]
    assert final == "The folder contains 494 files."


def test_runs_stream_uses_sse_event_names_for_live_trace(monkeypatch):
    config = HermiConfig(hermes_api_key="test-key")
    adapter = HermesAdapter(config)
    monkeypatch.setattr(adapter, "_start_run", lambda *args, **kwargs: "run-1")

    class FakeResponse:
        def __enter__(self):
            return iter(
                [
                    b"event: reasoning.delta\n",
                    b'data: {"text":"step 1"}\n\n',
                    b"event: tool.progress\n",
                    b'data: {"name":"terminal","phase":"tool.started"}\n\n',
                    b"event: run.completed\n",
                    b'data: {"output":"done"}\n\n',
                ]
            )

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    events = list(adapter._stream_run_events([{"role": "user", "content": "hi"}], "session", "key"))

    assert [event["event"] for event in events] == ["thought", "tool", "final"]
    assert events[0]["content"] == "step 1"
    assert "terminal" in events[1]["content"]
    assert events[2]["content"] == "done"


def test_runs_stream_uses_hermes_session_final_reply_and_progress(monkeypatch):
    config = HermiConfig(hermes_api_key="test-key")
    adapter = HermesAdapter(config)
    monkeypatch.setattr(adapter, "_start_run", lambda *args, **kwargs: "run-1")
    snapshots = iter(
        [
            [{"id": "old", "role": "assistant", "content": "older reply"}],
            [
                {"id": "old", "role": "assistant", "content": "older reply"},
                {"id": "progress", "role": "assistant", "content": "checking files"},
                {"id": "tool", "role": "tool", "content": "{}"},
                {"id": "final", "role": "assistant", "content": "files checked"},
            ],
        ]
    )
    monkeypatch.setattr(adapter, "session_messages", lambda *args, **kwargs: next(snapshots))

    class FakeResponse:
        def __enter__(self):
            return iter([b"event: run.completed\n", b'data: {"output":"checking files\\nfiles checked"}\n\n'])

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    events = list(adapter._stream_run_events([{"role": "user", "content": "hi"}], "session", "key"))

    assert events == [
        {"event": "thought", "content": "checking files"},
        {"event": "final", "content": "files checked"},
    ]


def test_runs_stream_forwards_live_assistant_progress_and_uses_authoritative_final(monkeypatch):
    config = HermiConfig(hermes_api_key="test-key")
    adapter = HermesAdapter(config)
    monkeypatch.setattr(adapter, "_start_run", lambda *args, **kwargs: "run-1")
    monkeypatch.setattr(adapter, "session_messages", lambda *args, **kwargs: [])

    class FakeResponse:
        def __enter__(self):
            return iter([
                b"event: assistant.delta\n",
                b'data: {"delta":"I will inspect the files."}\n\n',
                b"event: reasoning.available\n",
                b'data: {"text":"I will inspect the files."}\n\n',
                b"event: tool.started\n",
                b'data: {"tool":"terminal"}\n\n',
                b"event: assistant.delta\n",
                b'data: {"delta":"The files are ready."}\n\n',
                b"event: run.completed\n",
                b'data: {"output":"I will inspect the files.\\nThe files are ready.","messages":[{"role":"assistant","content":"I will inspect the files."},{"role":"tool","content":"{}"},{"role":"assistant","content":"The files are ready."}]}\n\n',
            ])

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    events = list(adapter._stream_run_events([{"role": "user", "content": "hi"}], "session", "key"))

    assert events == [
        {"event": "thought", "content": "I will inspect the files."},
        {"event": "tool", "content": "terminal: tool.started"},
        {"event": "final", "content": "The files are ready."},
    ]


def test_runs_stream_does_not_show_final_delta_as_thought_when_reasoning_echoes_it(monkeypatch):
    config = HermiConfig(hermes_api_key="test-key")
    adapter = HermesAdapter(config)
    monkeypatch.setattr(adapter, "_start_run", lambda *args, **kwargs: "run-1")
    monkeypatch.setattr(adapter, "session_messages", lambda *args, **kwargs: [])

    class FakeResponse:
        def __enter__(self):
            return iter([
                b"event: assistant.delta\n",
                b'data: {"delta":"# Final\\n\\n- done"}\n\n',
                b"event: reasoning.available\n",
                b'data: {"text":"# Final\\n\\n- done"}\n\n',
                b"event: run.completed\n",
                b'data: {"output":"# Final\\n\\n- done","messages":[{"role":"assistant","content":"# Final\\n\\n- done"}]}\n\n',
            ])

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse())

    assert list(adapter._stream_run_events([{"role": "user", "content": "hi"}], "session", "key")) == [
        {"event": "final", "content": "# Final\n\n- done"},
    ]


def test_runs_start_payload_can_include_session_history(monkeypatch):
    config = HermiConfig(
        hermes_api_key="test-key",
        hermes_model="profile-model",
        hermes_reasoning_effort="high",
        hermes_max_tokens=4096,
    )
    adapter = HermesAdapter(config)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"run_id":"run-1"}'

    def fake_urlopen(request, timeout=0):
        captured["payload"] = request.data.decode("utf-8")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    run_id = adapter._start_run(
        "当前问题",
        "系统指令",
        "session-1",
        "key-1",
        conversation_history=[
            {"role": "user", "content": "上一条"},
            {"role": "assistant", "content": "上一条回答"},
        ],
    )

    payload = __import__("json").loads(captured["payload"])
    assert run_id == "run-1"
    assert payload["conversation_history"] == [
        {"role": "user", "content": "上一条"},
        {"role": "assistant", "content": "上一条回答"},
    ]
    assert payload["model"] == "profile-model"
    assert payload["reasoning_effort"] == "high"
    assert payload["max_tokens"] == 4096


def test_runs_omit_hermes_agent_placeholder_model(monkeypatch):
    config = HermiConfig(hermes_api_key="test-key", hermes_model="hermes-agent")
    adapter = HermesAdapter(config)
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"run_id":"run-1"}'

    def fake_urlopen(request, timeout=0):
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert adapter._start_run("hello", "", "session", "key") == "run-1"
    assert "model" not in captured["payload"]


def test_finished_message_run_clears_stale_stream_timeout(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    lock = __import__("threading").RLock()
    run = _create_message_run(conn, "conv", "owner", lock)

    _fail_message_run(conn, run["run_id"], "message_run_stream_timeout", lock)
    _finish_message_run(conn, run["run_id"], {"assistant": {"content": "ok"}}, lock)

    row = _message_run_by_id(conn, run["run_id"])
    assert row["status"] == "done"
    assert row["error"] == ""


def test_scheduled_request_without_action_is_not_reported_as_success():
    reply = _scheduled_request_missing_action_reply("五分钟后QQ提醒我工作", "设好了，五分钟后提醒你")

    assert "没有真正创建定时任务" in reply
    assert "HERMI_ACTION" in reply
    assert _scheduled_request_missing_action_reply("你好", "设好了") == ""


def test_traceback_reply_becomes_friendly_failure():
    reply = _friendly_hermes_failure_reply("Traceback (most recent call last):\nUnicodeEncodeError: bad")

    assert "Hermes 工具执行报错" in reply
    assert "UnicodeEncodeError" in reply


class RestartPermissionHermes:
    last_usage = {}

    def chat(self, messages, session_id, session_key):
        return (
            "restart approval requested\n"
            '<<<HERMI_ACTION\n{"type":"hermes.permission.request","requested_capability":"service.restart","summary":"restart Hermi"}\n>>>'
        )


def test_service_restart_permission_approval_schedules_restart(tmp_path: Path, monkeypatch):
    scheduled = []

    monkeypatch.setattr(app_module, "_schedule_hermi_gateway_restart", lambda: scheduled.append(True) or True)
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
    )
    client = TestClient(create_app(config, hermes_adapter=RestartPermissionHermes()))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "restart"}).json()
    client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={"content": "restart yourself"},
    )
    approval = client.get("/approvals", headers=headers).json()["approvals"][0]

    response = client.post(
        f"/approvals/{approval['approval_id']}/decision",
        headers=headers,
        json={"decision": "once"},
    )

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
    ).json()["messages"]
    assert response.json()["status"] == "approved"
    assert scheduled == [True]
    assert "后台重启" in messages[-1]["content"]


class EmptyFinalHermes:
    last_usage = {}

    def stream_events(self, messages, session_id, session_key):
        yield {"event": "tool", "content": "web_search: completed"}
        yield {"event": "final", "content": ""}

    def chat(self, messages, session_id, session_key):
        return "fallback after empty stream"


def test_stream_empty_final_uses_fallback_instead_of_persisting_blank_reply(tmp_path: Path):
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    client = TestClient(create_app(config, hermes_adapter=EmptyFinalHermes()))
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/conversations", headers=headers, json={"title": "empty stream"}).json()

    with client.stream(
        "POST",
        f"/conversations/{conversation['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "please answer"},
    ) as response:
        body = response.read().decode("utf-8")

    messages = client.get(
        f"/conversations/{conversation['conversation_id']}/messages", headers=headers
    ).json()["messages"]
    assert response.status_code == 200
    assert "fallback after empty stream" in body
    assert messages[-1]["content"] == "fallback after empty stream"

