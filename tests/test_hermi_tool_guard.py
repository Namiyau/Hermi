import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


PLUGIN_PATH = Path.home() / ".hermes" / "plugins" / "qlos-tool-guard" / "__init__.py"


class ReplyingHermesAdapter:
    def chat(self, messages, session_id, session_key):
        return "safe reply"


def _load_tool_guard():
    spec = importlib.util.spec_from_file_location("qlos_tool_guard_for_test", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_hermi_friend_message_writes_short_lived_tool_guard_identity(tmp_path: Path, monkeypatch):
    identity_path = tmp_path / "hermi_tool_identity.jsonl"
    monkeypatch.setenv("HERMI_TOOL_GUARD_IDENTITY_FILE", str(identity_path))
    client = TestClient(
        create_app(
            HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token"),
            hermes_adapter=ReplyingHermesAdapter(),
        )
    )
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={"user_id": "friend:guard", "display_name": "Guard", "token": "guard-token"},
    )
    conversation = client.post(
        "/conversations",
        headers={"Authorization": "Bearer guard-token"},
        json={"title": "Guard"},
    ).json()

    response = client.post(
        f"/conversations/{conversation['conversation_id']}/messages",
        headers={"Authorization": "Bearer guard-token"},
        json={"content": "hello"},
    )

    assert response.status_code == 200
    record = json.loads(identity_path.read_text(encoding="utf-8").splitlines()[-1])
    assert record["session_id"] == conversation["session_id"]
    assert record["role"] == "friend"
    assert record["is_owner"] is False
    assert record["expires_at"] > record["ts"]


def test_tool_guard_blocks_high_risk_native_tools_for_hermi_friend(tmp_path: Path, monkeypatch):
    guard = _load_tool_guard()
    identity_path = tmp_path / "hermi_tool_identity.jsonl"
    identity_path.write_text(
        "\n".join(
            [
                json.dumps({"session_id": "hermi-friend", "role": "friend", "is_owner": False, "ts": 9_999_999_999, "expires_at": 9_999_999_999}),
                json.dumps({"session_id": "hermi-owner", "role": "owner", "is_owner": True, "ts": 9_999_999_999, "expires_at": 9_999_999_999}),
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMI_TOOL_GUARD_IDENTITY_FILE", str(identity_path))

    terminal = guard.pre_tool_call(tool_name="terminal", session_id="hermi-friend")
    cron = guard.pre_tool_call(tool_name="cronjob", session_id="hermi-friend")
    owner = guard.pre_tool_call(tool_name="terminal", session_id="hermi-owner")

    assert terminal and terminal["action"] == "block"
    assert cron and cron["action"] == "block"
    assert owner is None
