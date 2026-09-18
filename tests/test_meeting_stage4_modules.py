from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backend_meeting_rules_are_split_from_app():
    from hermi_gateway.meeting_context import compact_meeting_context
    from hermi_gateway.meeting_events import trace_event
    from hermi_gateway.meeting_modes import normalize_meeting_mode
    from hermi_gateway.meeting_orchestrator import discussion_control
    from hermi_gateway.meeting_permissions import meeting_permission_prompt
    from hermi_gateway.meeting_repository import room_by_id
    from hermi_gateway.meeting_routes import register_meeting_web_routes
    from hermi_gateway.meeting_service import can_delete_room

    assert normalize_meeting_mode("自动单次模式") == "auto_single"
    assert trace_event("tool", "done") == {"event": "tool", "content": "done"}
    assert "压缩" in compact_meeting_context(["a" * 7000], max_chars=100)
    assert discussion_control("结论\nNEXT: end") == ("结论", "end")
    assert "只读" in meeting_permission_prompt("smart")
    assert callable(room_by_id)
    assert callable(register_meeting_web_routes)
    assert can_delete_room([]) is True
    assert can_delete_room([{"status": "paused"}]) is False

    app_source = (ROOT / "hermi_gateway" / "app.py").read_text(encoding="utf-8")
    assert "from .meeting_modes import" in app_source
    assert "def _normalize_meeting_mode" not in app_source
    assert "def _compact_meeting_context" not in app_source
    assert "def _meeting_permission_prompt" not in app_source
    assert "def _meeting_discussion_control" not in app_source
    assert "from .meeting_repository import" in app_source
    assert "from .meeting_service import" in app_source
    assert "from .meeting_routes import" in app_source


def test_frontend_meeting_api_state_and_ui_are_split():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    for name in ("meeting_state.js", "meeting_api.js", "meeting_ui.js"):
        assert (ROOT / "web" / name).exists()
        assert f'src="/{name}"' in html
    assert "window.HermiMeetingState" in app
    assert "window.HermiMeetingAPI" in app
    assert "window.HermiMeetingUI" in app
