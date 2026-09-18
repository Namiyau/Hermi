from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class HermiConfig:
    host: str = "127.0.0.1"
    port: int = 8789
    db_path: Path = Path("./state/hermi_gateway.db")
    owner_token: str = "replace-with-owner-token"
    channel_token: str = "replace-with-channel-token"
    hermes_api_url: str = "http://127.0.0.1:8642/v1/chat/completions"
    hermes_api_key: str = ""
    hermes_model: str = "hermes-agent"
    hermes_reasoning_effort: str = ""
    hermes_max_tokens: int | None = None
    qlos_base_url: str = "http://127.0.0.1:8766"
    qlos_send_token: str = ""
    qlos_send_tokens: list[str] | None = None
    qlos_log_dir: Path = Path("./state/qlos_lite/logs")
    memory_context_dir: Path = Path("./state/memory")
    media_dir: Path = Path("~/Documents/Hermi资料/media").expanduser()
    soul_path: Path = Path("")
    default_profile_name: str = "薇达(Veda)"
    qq_profile_id: str = "trainee"
    hermi_profile_id: str = "maid"
    meeting_host_profile_id: str = "maid"
    profile_api_urls: str = "trainee=http://127.0.0.1:8642/v1/chat/completions,imouto=http://127.0.0.1:8643/v1/chat/completions,maid=http://127.0.0.1:8644/v1/chat/completions"
    default_operation_root: Path = Path(".")
    friend_token_limit: int = 50_000
    friend_trusted_token_limit: int = 250_000
    friend_file_size_limit: int = 5 * 1024 * 1024
    friend_trusted_file_size_limit: int = 25 * 1024 * 1024
    scheduler_enabled: bool = False
    scheduler_interval_seconds: int = 30
    permissions_enabled: bool = True

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "HermiConfig":
        source = dict(env) if env is not None else _apply_local_secrets(
            dict(os.environ),
            Path(__file__).resolve().parents[1] / "secrets.local.env",
        )
        return cls(
            host=str(source.get("HERMI_HOST", "127.0.0.1")).strip() or "127.0.0.1",
            port=int(source.get("HERMI_PORT", "8789")),
            db_path=Path(str(source.get("HERMI_DB_PATH", "./state/hermi_gateway.db"))),
            owner_token=str(source.get("HERMI_OWNER_TOKEN", "replace-with-owner-token")).strip() or "replace-with-owner-token",
            channel_token=str(source.get("HERMI_CHANNEL_TOKEN", "replace-with-channel-token")).strip()
            or "replace-with-channel-token",
            hermes_api_url=str(
                source.get("HERMI_HERMES_API_URL", "http://127.0.0.1:8642/v1/chat/completions")
            ).strip()
            or "http://127.0.0.1:8642/v1/chat/completions",
            hermes_api_key=str(
                source.get("HERMI_HERMES_API_KEY")
                or source.get("QLOS_HERMES_API_KEY")
                or source.get("API_SERVER_KEY")
                or ""
            ).strip(),
            hermes_model=str(source.get("HERMI_HERMES_MODEL", "hermes-agent")).strip() or "hermes-agent",
            hermes_reasoning_effort=str(source.get("HERMI_HERMES_REASONING_EFFORT", "")).strip(),
            hermes_max_tokens=_optional_int(source.get("HERMI_HERMES_MAX_TOKENS")),
            qlos_base_url=str(source.get("HERMI_QLOS_BASE_URL", "http://127.0.0.1:8766")).strip()
            or "http://127.0.0.1:8766",
            qlos_send_token=str(
                source.get("HERMI_QLOS_SEND_TOKEN")
                or source.get("QLOS_HERMI_GATEWAY_TOKEN")
                or source.get("QLOS_ONEBOT_INBOUND_TOKEN")
                or source.get("QILING_ONEBOT_INBOUND_TOKEN")
                or source.get("HERMI_CHANNEL_TOKEN")
                or ""
            ).strip(),
            qlos_send_tokens=_token_list(source),
            qlos_log_dir=Path(str(source.get("HERMI_QLOS_LOG_DIR", "./state/qlos_lite/logs"))),
            memory_context_dir=Path(str(source.get("HERMI_MEMORY_CONTEXT_DIR", "./state/memory"))),
            media_dir=Path(str(source.get("HERMI_MEDIA_DIR", "~/Documents/Hermi资料/media"))).expanduser(),
            soul_path=Path(str(source.get("HERMI_SOUL_PATH", ""))),
            default_profile_name=str(source.get("HERMI_DEFAULT_PROFILE_NAME", "薇达(Veda)")).strip() or "薇达(Veda)",
            qq_profile_id=str(source.get("HERMI_QQ_PROFILE_ID", "trainee")).strip() or "trainee",
            hermi_profile_id=str(source.get("HERMI_HERMI_PROFILE_ID", "maid")).strip() or "maid",
            meeting_host_profile_id=str(source.get("HERMI_MEETING_HOST_PROFILE_ID", "maid")).strip() or "maid",
            profile_api_urls=str(source.get("HERMI_PROFILE_API_URLS", cls.profile_api_urls)).strip() or cls.profile_api_urls,
            default_operation_root=Path(str(source.get("HERMI_DEFAULT_OPERATION_ROOT", "."))),
            friend_token_limit=int(source.get("HERMI_FRIEND_TOKEN_LIMIT", "50000")),
            friend_trusted_token_limit=int(source.get("HERMI_FRIEND_TRUSTED_TOKEN_LIMIT", "250000")),
            friend_file_size_limit=int(source.get("HERMI_FRIEND_FILE_SIZE_LIMIT", str(5 * 1024 * 1024))),
            friend_trusted_file_size_limit=int(
                source.get("HERMI_FRIEND_TRUSTED_FILE_SIZE_LIMIT", str(25 * 1024 * 1024))
            ),
            scheduler_enabled=_env_bool(source.get("HERMI_SCHEDULER_ENABLED", "0")),
            scheduler_interval_seconds=max(5, int(source.get("HERMI_SCHEDULER_INTERVAL_SECONDS", "30"))),
            permissions_enabled=_env_bool(source.get("HERMI_PERMISSIONS_ENABLED", "1")),
        )


def _apply_local_secrets(source: Mapping[str, str], path: Path) -> dict[str, str]:
    merged = dict(source)
    if not path.exists():
        return merged
    fallback_values = {
        "HERMI_OWNER_TOKEN": "replace-with-owner-token",
        "HERMI_CHANNEL_TOKEN": "replace-with-channel-token",
    }
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        if name in fallback_values and merged.get(name, "") in {"", fallback_values[name]}:
            merged[name] = value.strip('"\'')
    return merged


def _token_list(source: Mapping[str, str]) -> list[str]:
    tokens = []
    for name in (
        "HERMI_QLOS_SEND_TOKEN",
        "QLOS_HERMI_GATEWAY_TOKEN",
        "QLOS_ONEBOT_INBOUND_TOKEN",
        "QILING_ONEBOT_INBOUND_TOKEN",
        "QLOS_ONEBOT_ACCESS_TOKEN",
        "QILING_ONEBOT_ACCESS_TOKEN",
        "HERMI_CHANNEL_TOKEN",
    ):
        value = str(source.get(name) or "").strip()
        if value and value not in tokens:
            tokens.append(value)
    return tokens


def _env_bool(value: str | None) -> bool:
    return bool(value and value.lower() in ("1", "true", "yes", "on"))


def _optional_int(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


