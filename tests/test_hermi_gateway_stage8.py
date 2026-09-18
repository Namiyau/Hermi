from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.qlos_client import QlosClient


class CaptureHermes:
    def __init__(self, reply: str = "ok"):
        self.calls = []
        self.reply = reply
        self.last_usage = {}

    def chat(self, messages, session_id, session_key):
        self.calls.append(messages)
        return self.reply


class CaptureTransport:
    def __init__(self):
        self.payloads = []

    def __call__(self, url, payload, token, timeout):
        self.payloads.append(payload)
        return {"ok": True}


def _client(tmp_path: Path, hermes=None) -> TestClient:
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
    )
    return TestClient(create_app(config, hermes_adapter=hermes or CaptureHermes()))


def test_hermi_prompt_loads_soul_file_when_present(tmp_path: Path):
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text("Hermi soul: always keep owner context.", encoding="utf-8")
    hermes = CaptureHermes()
    config = HermiConfig(
        db_path=tmp_path / "hermi.db",
        owner_token="owner-token",
        channel_token="channel-token",
        media_dir=tmp_path / "media",
        soul_path=soul_path,
    )
    client = TestClient(create_app(config, hermes_adapter=hermes))
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", json={"title": "Soul"}, headers=headers).json()

    client.post(
        f"/conversations/{conv['conversation_id']}/messages",
        json={"content": "hello"},
        headers=headers,
    )

    merged = "\n".join(str(message["content"]) for message in hermes.calls[0])
    assert "[Hermi SOUL.md]" in merged
    assert "always keep owner context" in merged


def test_qlos_client_sends_standard_image_payload():
    transport = CaptureTransport()
    client = QlosClient(HermiConfig(qlos_send_token="token"), transport=transport)

    client.send_qq(
        chat_type="private",
        user_id="1000000001",
        message="see image",
        images=[{"file_id": "file-1", "url": "http://127.0.0.1/image.png"}],
    )

    assert transport.payloads[0]["images"] == [{"file_id": "file-1", "url": "http://127.0.0.1/image.png"}]
    assert transport.payloads[0]["attachments"] == [{"type": "image", "file_id": "file-1", "url": "http://127.0.0.1/image.png"}]


def test_stream_without_hermes_events_only_emits_final(tmp_path: Path):
    client = _client(tmp_path, CaptureHermes("plain reply"))
    headers = {"Authorization": "Bearer owner-token"}
    conv = client.post("/conversations", json={"title": "Stream"}, headers=headers).json()

    with client.stream(
        "POST",
        f"/conversations/{conv['conversation_id']}/messages/stream",
        headers=headers,
        json={"content": "hello"},
    ) as response:
        body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: final" in body
    assert "event: thought" not in body
    assert "Forwarding to Hermes" not in body


def test_scheduler_run_once_marks_due_once_job_and_records_event(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    created = client.post(
        "/scheduled-jobs",
        headers=headers,
        json={
            "kind": "once",
            "schedule": "once:+0m",
            "summary": "stage8 due job",
            "target": {"delivery": ["hermi"]},
            "payload": {"content": "report"},
        },
    ).json()

    result = client.post("/scheduler/run-once", headers=headers).json()
    job = client.get(f"/scheduled-jobs/{created['job_id']}", headers=headers).json()
    events = client.get(f"/tasks/{created['task_id']}/events", headers=headers).json()["events"]

    assert result["processed"] == 1
    assert job["status"] == "completed"
    assert any(event["event_type"] == "scheduled_job_due" for event in events)

