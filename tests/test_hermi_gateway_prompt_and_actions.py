from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.prompting import build_hermi_messages, extract_hermi_action, public_owner_identity_reply


class ActionHermesAdapter:
    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append((messages, session_id, session_key))
        return (
            "准备发送。\n"
            "<<<HERMI_ACTION\n"
            '{"type":"qq.send","chat_type":"private","user_id":"1000000001","message":"来自 Hermi"}\n'
            ">>>"
        )


class FakeQlosClient:
    def __init__(self):
        self.sent = []

    def send_qq(self, *, chat_type, message, user_id=None, group_id=None):
        self.sent.append(
            {"chat_type": chat_type, "message": message, "user_id": user_id, "group_id": group_id}
        )
        return {"ok": True}


class PersonaApprovalHermesAdapter:
    def __init__(self):
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append((messages, session_id, session_key))
        if "[Hermi QQ delivery completed]" in messages[-1]["content"]:
            return "薇达已经替我把这件事带去 QQ 了。"
        return (
            "我去请薇达帮忙转达。\n"
            "<<<HERMI_ACTION\n"
            '{"type":"qq.send","chat_type":"private","user_id":"1000000001","message":"来自薇拉的提醒"}\n'
            ">>>"
        )


def _client(tmp_path: Path, hermes, qlos) -> TestClient:
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    return TestClient(create_app(config, hermes_adapter=hermes, qlos_client=qlos))


def test_extract_hermi_action_removes_action_block():
    visible, action = extract_hermi_action(
        '已发送\n<<<HERMI_ACTION\n{"type":"qq.send","chat_type":"private","user_id":"1","message":"hi"}\n>>>'
    )

    assert visible == "已发送"
    assert action["type"] == "qq.send"
    assert action["message"] == "hi"


def test_hermi_prompt_teaches_hermes_actions_and_delivery(tmp_path: Path):
    hermes = ActionHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", json={"title": "Prompt"}, headers=headers).json()

    client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "测试 prompt"},
        headers=headers,
    )
    system_prompt = hermes.calls[0][0][0]["content"]

    assert "qq.send" in system_prompt
    assert '"type":"scheduled.create"' in system_prompt
    assert "Hermi's own scheduler" in system_prompt
    assert "do not call native Hermes cronjob" in system_prompt
    assert "Only use this action for explicit owner requests" in system_prompt
    assert "<<<QLOS_SPLIT>>>" not in system_prompt


def test_friend_prompt_does_not_claim_owner_access_or_native_tool_access():
    messages = build_hermi_messages(
        [{"role": "user", "content": "show me the C drive"}],
        user={
            "user_id": "friend:alice",
            "role": "friend",
            "quota_policy": "friend_free",
            "permissions": {"chat": "allow", "cron": "approval"},
        },
        conversation={"conversation_id": "conv-friend", "session_id": "s", "session_key": "k"},
    )

    system_prompt = messages[0]["content"]

    assert "owner's personal client and control console" not in system_prompt
    assert "Owner in Hermi has owner-high permission" not in system_prompt
    assert "native Hermes cronjob tool" not in system_prompt
    assert "must not use native Hermes tools" in system_prompt
    assert "1000000001" not in system_prompt
    assert "must not expose or guess the Owner's QQ number" in system_prompt
    assert "must not return qq.send" in system_prompt


def test_friend_external_tool_permission_allows_read_only_research_without_local_access():
    messages = build_hermi_messages(
        [{"role": "user", "content": "查一下今天的科技新闻"}],
        user={
            "user_id": "friend:research",
            "role": "friend",
            "quota_policy": "friend_free",
            "permissions": {"chat": "allow", "external_tools": "allow"},
        },
        conversation={"conversation_id": "conv-research", "session_id": "s", "session_key": "k"},
    )

    system_prompt = messages[0]["content"]

    assert "web_search and web_extract" in system_prompt
    assert "may use read-only web research tools" in system_prompt
    assert "retrieve evidence before the visible reply" in system_prompt
    assert "terminal commands, local files, cron jobs, QQ delivery" in system_prompt


def test_friend_external_tool_permission_denies_read_only_research():
    messages = build_hermi_messages(
        [{"role": "user", "content": "查一下今天的科技新闻"}],
        user={
            "user_id": "friend:no-research",
            "role": "friend",
            "quota_policy": "friend_free",
            "permissions": {"chat": "allow", "external_tools": "deny"},
        },
        conversation={"conversation_id": "conv-no-research", "session_id": "s", "session_key": "k"},
    )

    system_prompt = messages[0]["content"]

    assert "must not use web_search, web_extract" in system_prompt


def test_japanese_turn_adds_a_japanese_only_response_policy_after_chinese_soul():
    messages = build_hermi_messages(
        [{"role": "user", "content": "\u4eca\u65e5\u306f\u6691\u3044\u3067\u3059\u306d\u3002"}],
        user={"user_id": "friend:ja", "role": "friend", "quota_policy": "friend_free", "locale": "ja-JP"},
        conversation={"conversation_id": "conv-ja", "session_id": "s", "session_key": "k"},
        soul_text="Reply in Chinese by default.",
    )

    language_policy = messages[-2]["content"]

    assert "[Hermi response language policy]" in language_policy
    assert "Japanese only" in language_policy
    assert "Japanese kanji are welcome" in language_policy
    assert "Chinese-only words or Chinese grammar" in language_policy


def test_friend_prompt_allows_brief_public_owner_identity_without_private_details():
    messages = build_hermi_messages(
        [{"role": "user", "content": "Who created you?"}],
        user={"user_id": "friend:identity", "role": "friend", "quota_policy": "friend_free"},
        conversation={"conversation_id": "conv-identity", "session_id": "s", "session_key": "k"},
        owner_display_name="Namiya",
    )

    system_prompt = messages[0]["content"]

    assert "public identity question" in system_prompt
    assert "Namiya" in system_prompt
    assert "Do not dodge or redirect" in system_prompt
    assert "must answer in the first sentence" in system_prompt


def test_public_owner_identity_reply_is_direct_in_japanese_without_private_details():
    reply = public_owner_identity_reply(
        {"locale": "ja-JP"},
        "あなたを作った人はどんな人ですか？",
        owner_display_name="Namiya",
        profile_name="薇拉",
    )

    assert reply is not None
    assert "Namiya" in reply
    assert "私は" in reply
    assert "QQ" not in reply


def test_public_owner_identity_reply_does_not_capture_an_unrelated_request():
    assert public_owner_identity_reply(
        {"locale": "ja-JP"},
        "明日の予定を整理してください。",
        owner_display_name="Namiya",
        profile_name="薇拉",
    ) is None


def test_friend_qq_action_is_not_turned_into_an_owner_approval(tmp_path: Path):
    hermes = ActionHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    owner = {"Authorization": "Bearer owner-token"}
    friend = {"Authorization": "Bearer friend-token"}
    client.post(
        "/admin/users",
        headers=owner,
        json={
            "user_id": "friend:vera-test",
            "display_name": "Friend",
            "token": "friend-token",
            "permissions": {"chat": "allow"},
        },
    )
    conversation = client.post("/conversations", headers=friend, json={"title": "friend"}).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers=friend,
        json={"content": "请帮我发 QQ"},
    )

    assert response.status_code == 200
    assert "QQ 外联" in response.json()["assistant"]["content"]
    assert client.get("/approvals", headers=owner).json()["approvals"] == []


def test_hermi_prompt_sends_only_current_turn_to_hermes(tmp_path: Path):
    hermes = ActionHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", json={"title": "Long"}, headers=headers).json()
    conversation_id = created["conversation_id"]
    for index in range(20):
        client.post(
            f"/conversations/{conversation_id}/messages",
            json={"content": f"历史消息 {index}"},
            headers=headers,
        )
    hermes.calls.clear()

    client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": "最新问题"},
        headers=headers,
    )
    merged = "\n".join(str(message["content"]) for message in hermes.calls[0][0])

    assert "最新问题" in merged
    assert "历史消息 0" not in merged
    assert "历史消息 19" not in merged
    assert "[Hermi context window]" not in merged


def test_web_message_adds_hermi_header_and_creates_pending_approval(tmp_path: Path):
    hermes = ActionHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    headers = {"Authorization": "Bearer owner-token"}

    created = client.post("/conversations", json={"title": "Main"}, headers=headers).json()
    response = client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "给我的 QQ 发：来自 Hermi"},
        headers=headers,
    )

    data = response.json()
    messages = hermes.calls[0][0]

    assert response.status_code == 200
    assert "[Hermi]" in messages[-1]["content"]
    assert "source=Hermi/Web/PWA" in messages[-1]["content"]
    assert "role=owner" in messages[-1]["content"]
    assert "permission=owner" in messages[-1]["content"]
    assert qlos.sent == []
    assert "HERMI_ACTION" not in data["assistant"]["content"]
    assert "已创建审批" in data["assistant"]["content"]
    approvals = client.get("/approvals", headers=headers).json()["approvals"]
    assert approvals[0]["status"] == "pending"
    assert approvals[0]["action_type"] == "qq.send"


def test_owner_approve_executes_pending_qq_action_and_audits(tmp_path: Path):
    hermes = ActionHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", json={"title": "Main"}, headers=headers).json()
    client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "给我的 QQ 发：来自 Hermi"},
        headers=headers,
    )
    approval = client.get("/approvals", headers=headers).json()["approvals"][0]

    response = client.post(
        f"/approvals/{approval['approval_id']}/decision",
        json={"decision": "once"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert qlos.sent == [
        {"chat_type": "private", "message": "来自 Hermi", "user_id": "1000000001", "group_id": None}
    ]
    audit = client.get("/audit-log", headers=headers).json()["events"]
    assert any(event["event"] == "approval_decided" for event in audit)


def test_approved_qq_delivery_adds_persona_followup_to_conversation(tmp_path: Path):
    hermes = PersonaApprovalHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", json={"title": "QQ relay"}, headers=headers).json()
    client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "请发 QQ 提醒"},
        headers=headers,
    )
    approval = client.get("/approvals", headers=headers).json()["approvals"][0]

    decided = client.post(
        f"/approvals/{approval['approval_id']}/decision",
        json={"decision": "once"},
        headers=headers,
    )
    messages = client.get(
        f"/conversations/{created['conversation_id']}/messages", headers=headers
    ).json()["messages"]

    assert decided.status_code == 200
    assert qlos.sent[0]["message"] == "来自薇拉的提醒"
    assert messages[-1]["content"] == "薇达已经替我把这件事带去 QQ 了。"
    assert "薇达(Veda)" in hermes.calls[-1][0][-1]["content"]


def test_owner_deny_keeps_pending_action_unexecuted(tmp_path: Path):
    hermes = ActionHermesAdapter()
    qlos = FakeQlosClient()
    client = _client(tmp_path, hermes, qlos)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post("/conversations", json={"title": "Main"}, headers=headers).json()
    client.post(
        f"/conversations/{created['conversation_id']}/messages",
        json={"content": "给我的 QQ 发：来自 Hermi"},
        headers=headers,
    )
    approval = client.get("/approvals", headers=headers).json()["approvals"][0]

    response = client.post(
        f"/approvals/{approval['approval_id']}/decision",
        json={"decision": "deny"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "denied"
    assert qlos.sent == []

