from pathlib import Path

from hermi_gateway.config import HermiConfig, _apply_local_secrets
from hermi_gateway.db import create_seed_users, init_db, upsert_user, verify_token


def test_config_defaults_keep_private_ports():
    config = HermiConfig.from_env({})

    assert config.host == "127.0.0.1"
    assert config.port == 8789
    assert config.hermes_api_url == "http://127.0.0.1:8642/v1/chat/completions"
    assert config.qq_profile_id == "trainee"
    assert "trainee=http://127.0.0.1:8642/v1/chat/completions" in config.profile_api_urls
    assert "default=" not in config.profile_api_urls
    assert config.qlos_base_url == "http://127.0.0.1:8766"


def test_local_secret_replaces_fallback_owner_and_channel_tokens(tmp_path: Path):
    env_file = tmp_path / "secrets.local.env"
    env_file.write_text("HERMI_OWNER_TOKEN=real-owner\nHERMI_CHANNEL_TOKEN=real-channel\n", encoding="utf-8")

    source = _apply_local_secrets(
        {"HERMI_OWNER_TOKEN": "replace-with-owner-token", "HERMI_CHANNEL_TOKEN": "replace-with-channel-token"},
        env_file,
    )

    assert source["HERMI_OWNER_TOKEN"] == "real-owner"
    assert source["HERMI_CHANNEL_TOKEN"] == "real-channel"


def test_init_db_creates_core_tables(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")

    table_names = {
        row["name"]
        for row in conn.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    }

    assert {
        "users",
        "devices",
        "conversations",
        "messages",
        "approvals",
        "usage_daily",
        "audit_log",
        "media_files",
        "agents",
        "rooms",
        "room_members",
        "workflow_runs",
        "workflow_steps",
        "nodes",
        "deployment_jobs",
    } <= table_names


def test_seed_users_and_verify_token(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    create_seed_users(conn, owner_token="owner-secret", channel_token="channel-secret")

    owner = verify_token(conn, "owner-secret")
    channel = verify_token(conn, "channel-secret")

    assert owner["role"] == "owner"
    assert owner["can_approve"] == 1
    assert owner["can_remote_control"] == 1
    assert channel["role"] == "channel"
    assert channel["can_approve"] == 0


def test_seed_users_preserves_custom_owner_display_name(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    create_seed_users(conn, owner_token="owner-secret", channel_token="channel-secret")
    conn.execute("update users set display_name = ? where user_id = ?", ("Namiya", "owner"))
    conn.commit()

    create_seed_users(conn, owner_token="owner-secret", channel_token="channel-secret")

    owner = verify_token(conn, "owner-secret")
    assert owner["display_name"] == "Namiya"


def test_friend_user_is_present_but_cannot_approve(tmp_path: Path):
    conn = init_db(tmp_path / "hermi.db")
    upsert_user(
        conn,
        user_id="friend:alice",
        display_name="Alice",
        role="friend",
        token="friend-token",
        can_approve=False,
        can_remote_control=False,
        quota_policy="friend_free",
    )

    friend = verify_token(conn, "friend-token")

    assert friend["role"] == "friend"
    assert friend["quota_policy"] == "friend_free"
    assert friend["can_approve"] == 0
    assert friend["can_remote_control"] == 0

