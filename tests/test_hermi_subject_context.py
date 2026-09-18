from __future__ import annotations

import pytest
from pathlib import Path

from hermi_gateway.trusted_context import (
    build_hermi_web_context,
    ensure_hermi_subject_page,
    write_trusted_session_context,
)


def test_hermi_web_context_is_hash_only_and_bound_to_hermes_session(tmp_path):
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


def test_ensure_hermi_subject_page_uses_chinese_hash_only_person_record(tmp_path):
    context = build_hermi_web_context(
        "channel-token", user_id="testA", session_id="hermi-conv-1", session_key="hermi:conv-1", role="friend", now=1_000,
    )
    context_dir = tmp_path / "HermesBrain" / "system" / "trusted-sessions"

    hermes_source = Path(__file__).resolve().parents[2] / "Hermes" / "src"
    if not hermes_source.exists():
        pytest.skip("Hermes source tree is an external runtime dependency")
    assert ensure_hermi_subject_page(context_dir, "maid", context, memory_source_root=hermes_source) is True

    person_pages = list((tmp_path / "HermesBrain" / "brains" / "maid" / "users").rglob("*.md"))
    assert len(person_pages) == 1
    content = person_pages[0].read_text(encoding="utf-8")
    assert "Hermi朋友-" in person_pages[0].name
    assert "source_platform: hermi_web" in content
    assert "testA" not in content
