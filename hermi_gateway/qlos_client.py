from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .config import HermiConfig


class QlosClient:
    def __init__(self, config: HermiConfig, transport=None):
        self.base_url = config.qlos_base_url.rstrip("/")
        self.tokens = list(config.qlos_send_tokens or [])
        if config.qlos_send_token and config.qlos_send_token not in self.tokens:
            self.tokens.insert(0, config.qlos_send_token)
        self.transport = transport or _request_json

    def send_qq(
        self,
        *,
        chat_type: str,
        message: str,
        user_id: str | None = None,
        group_id: str | None = None,
        images: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        image_items = list(images or [])
        attachment_items = list(attachments or [])
        attachment_items.extend({"type": "image", **item} for item in image_items)
        payload = {
            "chat_type": chat_type,
            "message": message,
            "user_id": user_id,
            "group_id": group_id,
            "images": image_items,
            "attachments": attachment_items,
        }
        last_error: Exception | None = None
        for token in self.tokens or [""]:
            try:
                return self.transport(f"{self.base_url}/hermi/qq/send", payload, token, 30)
            except (PermissionError, urllib.error.HTTPError) as exc:
                status = getattr(exc, "code", None)
                if isinstance(exc, PermissionError) or status in {401, 403}:
                    last_error = exc
                    continue
                raise
        if last_error:
            raise last_error
        return self.transport(f"{self.base_url}/hermi/qq/send", payload, "", 30)


def _request_json(url: str, payload: dict[str, Any], token: str, timeout: int) -> dict[str, Any]:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace") or "{}")
