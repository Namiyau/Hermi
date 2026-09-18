import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.qq_context import load_recent_qq_context
from hermi_gateway.trusted_context import build_hermi_web_context, write_trusted_session_context
from hermi_gateway.qlos_client import QlosClient


class CaptureHermes:
    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append(messages)
        return "ok"


class StreamingCaptureHermes(CaptureHermes):
    def stream_events(self, messages, session_id, session_key):
        self.calls.append(messages)
        yield {"event": "final", "content": "stream ok"}


class TokenTransport:
    def __init__(self):
        self.tokens = []

    def __call__(self, url, payload, token, timeout):
        self.tokens.append(token)
        if token == "bad-token":
            raise PermissionError("401")
        return {"ok": True}


def test_owner_profile_is_injected_once_per_streamed_conversation_and_after_change(tmp_path: Path):
    hermes = StreamingCaptureHermes()
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config, hermes_adapter=hermes))
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:stream", "display_name": "Stream", "role": "friend", "token": "stream-token"},
    )
    client.put(
        "/admin/users/friend:stream/profile/relationship",
        headers=owner_headers,
        json={"value": "Owner 的协作朋友。"},
    )
    friend_headers = {"Authorization": "Bearer stream-token"}
    conversation_id = client.post("/conversations", headers=friend_headers, json={"title": "流式资料注入"}).json()["conversation_id"]

    def send_stream(content: str) -> str:
        with client.stream(
            "POST",
            f"/conversations/{conversation_id}/messages/stream",
            headers=friend_headers,
            json={"content": content},
        ) as response:
            assert response.status_code == 200
            return response.read().decode("utf-8")

    assert "event: final" in send_stream("你好")
    first_prompt = "\n".join(str(message["content"]) for message in hermes.calls[-1])
    assert "[Hermi owner-curated user private background]" in first_prompt
    assert "Owner 的协作朋友。" in first_prompt

    send_stream("再聊一次")
    second_prompt = "\n".join(str(message["content"]) for message in hermes.calls[-1])
    assert "[Hermi owner-curated user private background]" not in second_prompt

    client.put(
        "/admin/users/friend:stream/profile/recent_focus",
        headers=owner_headers,
        json={"value": "最近在准备演示。"},
    )
    send_stream("继续")
    deleted = client.delete(f"/conversations/{conversation_id}", headers=friend_headers)
    assert deleted.status_code == 200
    injected = client.app.state.db.execute(
        "select 1 from user_profile_injections where conversation_id = ? and user_id = ?",
        (conversation_id, "friend:stream"),
    ).fetchone()
    assert injected is None
    updated_prompt = "\n".join(str(message["content"]) for message in hermes.calls[-1])
    assert "[Hermi owner-curated user private background]" in updated_prompt
    assert "最近在准备演示。" in updated_prompt


def test_qlos_client_tries_fallback_tokens_on_401():
    transport = TokenTransport()
    config = HermiConfig(qlos_send_token="bad-token", qlos_send_tokens=["bad-token", "good-token"])

    result = QlosClient(config, transport=transport).send_qq(
        chat_type="private",
        user_id="1000000001",
        message="hi",
    )

    assert result["ok"] is True
    assert transport.tokens == ["bad-token", "good-token"]


def test_hermi_web_context_is_hash_only_and_bound_to_hermes_session(tmp_path: Path):
    context = build_hermi_web_context(
        "channel-token", user_id="testA", session_id="hermi-conv-1", session_key="hermi:conv-1", role="friend", now=1_000,
    )
    path = write_trusted_session_context(tmp_path, "hermi-conv-1", context)

    assert context["platform"] == "hermi_web"
    assert context["subject_id_hash"] != "testA"
    assert context["chat_type"] == "private"
    assert context["expires_at"] > 1_000
    text = path.read_text(encoding="utf-8")
    assert "testA" not in text
    assert "hermi-conv-1" not in text


def test_load_recent_qq_context_reads_gateway_http_logs(tmp_path: Path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    payload = {
        "post_type": "message",
        "message_type": "group",
        "group_id": 2000000001,
        "user_id": 1000000001,
        "raw_message": "群里刚刚说了测试",
    }
    record = {"body_preview": json.dumps(payload, ensure_ascii=False)}
    (log_dir / "gateway_http.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    context = load_recent_qq_context(log_dir, limit=5)

    assert "group:2000000001" in context
    assert "群里刚刚说了测试" in context


def test_hermi_prompt_includes_rich_permission_and_recent_qq_context(tmp_path: Path):
    log_dir = tmp_path / "qlos_logs"
    log_dir.mkdir()
    payload = {
        "post_type": "message",
        "message_type": "group",
        "group_id": 2000000001,
        "user_id": 123,
        "raw_message": "群消息 A",
    }
    (log_dir / "gateway_http.jsonl").write_text(
        json.dumps({"body_preview": json.dumps(payload, ensure_ascii=False)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    hermes = CaptureHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        qlos_log_dir=log_dir,
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", json={"title": "Main"}, headers=headers).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        json={"content": "看看QQ群刚刚有啥消息"},
        headers=headers,
    )

    merged = "\n".join(str(message["content"]) for message in hermes.calls[0])
    assert "Hermi supports Markdown" in merged
    assert "permission=owner-high" in merged
    assert "[recent_qq_context]" in merged
    assert "群消息 A" in merged


def test_owner_profile_is_injected_once_per_conversation_and_after_change(tmp_path: Path):
    hermes = CaptureHermes()
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config, hermes_adapter=hermes))
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:alice", "display_name": "Alice", "role": "friend", "token": "alice-token"},
    )
    client.put(
        "/admin/users/friend:alice/profile/relationship",
        headers=owner_headers,
        json={"value": "Namiya 的朋友，使用 Hermi 协作。"},
    )
    friend_headers = {"Authorization": "Bearer alice-token"}
    conversation_id = client.post("/conversations", headers=friend_headers, json={"title": "资料注入"}).json()["conversation_id"]

    client.post(f"/conversations/{conversation_id}/messages", headers=friend_headers, json={"content": "你好"})
    first_prompt = "\n".join(str(message["content"]) for message in hermes.calls[-1])
    assert "[Hermi owner-curated user private background]" in first_prompt
    assert "Namiya 的朋友" in first_prompt

    client.post(f"/conversations/{conversation_id}/messages", headers=friend_headers, json={"content": "再聊一次"})
    second_prompt = "\n".join(str(message["content"]) for message in hermes.calls[-1])
    assert "[Hermi owner-curated user private background]" not in second_prompt

    client.put(
        "/admin/users/friend:alice/profile/recent_focus",
        headers=owner_headers,
        json={"value": "最近在准备日语学习计划。"},
    )
    client.post(f"/conversations/{conversation_id}/messages", headers=friend_headers, json={"content": "继续"})
    updated_prompt = "\n".join(str(message["content"]) for message in hermes.calls[-1])
    assert "[Hermi owner-curated user private background]" in updated_prompt
    assert "最近在准备日语学习计划" in updated_prompt


def test_owner_curated_user_profile_is_private_background_not_a_script(tmp_path: Path):
    hermes = CaptureHermes()
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    client = TestClient(create_app(config, hermes_adapter=hermes))
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:background", "display_name": "Background", "token": "background-token"},
    )
    client.put(
        "/admin/users/friend:background/profile/preferences",
        headers=owner_headers,
        json={"value": "likes a particular series"},
    )
    friend_headers = {"Authorization": "Bearer background-token"}
    conversation_id = client.post("/conversations", headers=friend_headers, json={"title": "Background"}).json()["conversation_id"]

    client.post(f"/conversations/{conversation_id}/messages", headers=friend_headers, json={"content": "hello"})
    profile_context = next(
        message["content"]
        for message in hermes.calls[-1]
        if "owner-curated user" in message["content"]
    )

    assert "private background" in profile_context
    assert "Do not list, quote, or volunteer" in profile_context
    assert "unrelated question" in profile_context
    assert "first reply" in profile_context
    assert "open-ended chat" in profile_context

