import hashlib
import hmac
import json
from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig


class FakeHermesAdapter:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, session_id, session_key):
        self.calls.append((messages, session_id, session_key))
        return "compatible reply"


def _hash(key: str, value: str) -> str:
    return hmac.new(key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def _signed_context(token: str, *, session_id: str, session_key: str, user_id: str = "1000000001") -> dict:
    payload = {
        "version": 1,
        "platform": "qq",
        "chat_type": "group",
        "subject_id_hash": _hash(token, f"qq:user:{user_id}"),
        "group_id_hash": _hash(token, "qq:group:9988"),
        "is_owner": True,
        "sender_role": "owner",
        "session_id_hash": _hash(token, f"session:id:{session_id}"),
        "session_key_hash": _hash(token, f"session:key:{session_key}"),
        "issued_at": 1_000_000_000,
        "expires_at": 4_000_000_000,
        "nonce": _hash(token, "nonce:qq-1:1000000000"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "signature": hmac.new(token.encode("utf-8"), encoded, hashlib.sha256).hexdigest()}


def _payload(context: dict | None = None) -> dict:
    result = {
        "message_id": "qq-1",
        "chat_type": "group",
        "user_id": "1000000001",
        "group_id": "9988",
        "text": "hello",
        "sender_role": "owner",
        "session_id": "qlos-qq-group-9988-user-1000000001",
        "session_key": "qlos:qq:group:9988:user:1000000001",
    }
    if context is not None:
        result["trusted_context"] = context
    return result


def test_verified_context_writes_hash_only_sidecar_and_keeps_existing_hermes_session(tmp_path: Path):
    adapter = FakeHermesAdapter()
    token = "channel-token"
    body = _payload()
    context = _signed_context(token, session_id=body["session_id"], session_key=body["session_key"])
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token=token,
        media_dir=tmp_path / "media",
        memory_context_dir=tmp_path / "trusted-sessions",
    )
    client = TestClient(create_app(config, hermes_adapter=adapter))

    response = client.post("/channels/qq/events", headers={"Authorization": f"Bearer {token}"}, json=_payload(context))

    assert response.status_code == 200
    assert adapter.calls[0][1:] == (body["session_id"], body["session_key"])
    files = list((tmp_path / "trusted-sessions").glob("*.json"))
    assert len(files) == 1
    stored = files[0].read_text(encoding="utf-8")
    assert "1000000001" not in stored
    assert "9988" not in stored
    assert json.loads(stored)["subject_id_hash"] == context["subject_id_hash"]


def test_tampered_context_keeps_existing_reply_and_creates_no_sidecar(tmp_path: Path):
    adapter = FakeHermesAdapter()
    token = "channel-token"
    body = _payload()
    context = _signed_context(token, session_id=body["session_id"], session_key=body["session_key"])
    context["is_owner"] = False
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token=token,
        media_dir=tmp_path / "media",
        memory_context_dir=tmp_path / "trusted-sessions",
    )
    client = TestClient(create_app(config, hermes_adapter=adapter))

    response = client.post("/channels/qq/events", headers={"Authorization": f"Bearer {token}"}, json=_payload(context))

    assert response.status_code == 200
    assert response.json()["reply"] == "compatible reply"
    assert not (tmp_path / "trusted-sessions").exists()

