from pathlib import Path

from fastapi.testclient import TestClient

from hermi_gateway.app import create_app
from hermi_gateway.config import HermiConfig
from hermi_gateway.db import init_db


def _client(tmp_path: Path) -> TestClient:
    config = HermiConfig(db_path=tmp_path / "hermi.db", owner_token="owner-token", channel_token="channel-token")
    return TestClient(create_app(config))


def test_phase6_tables_are_created(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    tables = {
        row["name"]
        for row in conn.execute("select name from sqlite_master where type = 'table'").fetchall()
    }

    assert {"prompt_cards", "prompt_bindings", "prompt_renders", "channel_events"}.issubset(tables)


def test_owner_can_create_prompt_card(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    created = client.post(
        "/prompt-cards",
        headers=headers,
        json={
            "name": "QQ 输出卡",
            "card_type": "channel",
            "content": "QQ 输出要短，必要时拆分。",
            "enabled": True,
            "metadata": {"channel": "qq"},
        },
    )
    cards = client.get("/prompt-cards", headers=headers).json()["prompt_cards"]

    assert created.status_code == 200
    assert created.json()["card_type"] == "channel"
    assert cards[0]["name"] == "QQ 输出卡"


def test_prompt_cards_are_owner_only_even_when_friend_permission_allows_them(tmp_path: Path):
    client = _client(tmp_path)
    owner_headers = {"Authorization": "Bearer owner-token"}
    client.post(
        "/admin/users",
        headers=owner_headers,
        json={
            "user_id": "friend:cards",
            "display_name": "Cards Friend",
            "token": "cards-token",
            "permissions": {"prompt_cards": {"mode": "allow", "max_count": 99}},
        },
    )
    friend_headers = {"Authorization": "Bearer cards-token"}

    listed = client.get("/prompt-cards", headers=friend_headers)
    created = client.post(
        "/prompt-cards",
        headers=friend_headers,
        json={"name": "Friend card", "card_type": "channel", "content": "not allowed"},
    )

    assert listed.status_code == 403
    assert created.status_code == 403


def test_owner_can_bind_prompt_card_to_channel(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}
    card = client.post(
        "/prompt-cards",
        headers=headers,
        json={"name": "QQ split", "card_type": "channel", "content": "QQ 使用内部拆分标记。"},
    ).json()

    created = client.post(
        "/prompt-bindings",
        headers=headers,
        json={"card_id": card["card_id"], "scope_type": "channel", "scope_id": "qq", "priority": 10},
    )
    bindings = client.get("/prompt-bindings", headers=headers).json()["prompt_bindings"]

    assert created.status_code == 200
    assert created.json()["scope_type"] == "channel"
    assert created.json()["scope_id"] == "qq"
    assert bindings[0]["card_id"] == card["card_id"]


def test_channel_event_records_envelope(tmp_path: Path):
    client = _client(tmp_path)
    headers = {"Authorization": "Bearer owner-token"}

    created = client.post(
        "/channel-events",
        headers=headers,
        json={
            "channel": "qq",
            "source_id": "qq:dm:1000000001",
            "direction": "inbound",
            "envelope": {
                "source": "qq",
                "sender": {"user_id": "1000000001", "role": "owner"},
                "permissions": ["owner-high"],
            },
        },
    )
    events = client.get("/channel-events", headers=headers).json()["channel_events"]

    assert created.status_code == 200
    assert created.json()["channel"] == "qq"
    assert "owner-high" in created.json()["envelope_json"]
    assert events[0]["direction"] == "inbound"

