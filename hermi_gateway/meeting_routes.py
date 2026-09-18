from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def register_meeting_web_routes(app: FastAPI, web_path: Callable[[str], Path]) -> None:
    def frontend_file(filename: str) -> FileResponse:
        return FileResponse(
            web_path(filename),
            headers={"Cache-Control": "no-store, max-age=0, must-revalidate"},
        )

    @app.get("/meeting_state.js", include_in_schema=False)
    def meeting_state_js() -> FileResponse:
        return frontend_file("meeting_state.js")

    @app.get("/meeting_api.js", include_in_schema=False)
    def meeting_api_js() -> FileResponse:
        return frontend_file("meeting_api.js")

    @app.get("/meeting_ui.js", include_in_schema=False)
    def meeting_ui_js() -> FileResponse:
        return frontend_file("meeting_ui.js")
