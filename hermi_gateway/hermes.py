from __future__ import annotations

import json
from dataclasses import replace
import urllib.error
import urllib.request
from urllib.parse import quote, urlsplit, urlunsplit
from typing import Any

from .config import HermiConfig


class HermesAdapter:
    def __init__(self, config: HermiConfig):
        self.config = config
        self.last_usage: dict[str, Any] = {}
        self._profile_adapters: dict[str, HermesAdapter] = {}

    def chat_profile(
        self,
        profile_id: str,
        messages: list[dict[str, Any]],
        session_id: str,
        session_key: str,
    ) -> str:
        endpoints = _profile_api_urls(self.config.profile_api_urls)
        endpoint = endpoints.get(profile_id)
        if not endpoint:
            raise RuntimeError(f"profile_api_not_configured:{profile_id}")
        if endpoint == self.config.hermes_api_url:
            reply = self.chat(messages, session_id, session_key)
        else:
            adapter = self._profile_adapters.get(profile_id)
            if adapter is None:
                adapter = HermesAdapter(replace(self.config, hermes_api_url=endpoint))
                self._profile_adapters[profile_id] = adapter
            reply = adapter.chat(messages, session_id, session_key)
            self.last_usage = dict(adapter.last_usage)
        return reply

    def _profile_adapter(self, profile_id: str) -> "HermesAdapter":
        endpoint = _profile_api_urls(self.config.profile_api_urls).get(profile_id)
        if not endpoint:
            raise RuntimeError(f"profile_api_not_configured:{profile_id}")
        if endpoint == self.config.hermes_api_url:
            return self
        adapter = self._profile_adapters.get(profile_id)
        if adapter is None:
            adapter = HermesAdapter(replace(self.config, hermes_api_url=endpoint))
            self._profile_adapters[profile_id] = adapter
        return adapter

    def stream_profile_events(
        self,
        profile_id: str,
        messages: list[dict[str, Any]],
        session_id: str,
        session_key: str,
    ):
        endpoints = _profile_api_urls(self.config.profile_api_urls)
        endpoint = endpoints.get(profile_id)
        if not endpoint:
            raise RuntimeError(f"profile_api_not_configured:{profile_id}")
        adapter = self
        if endpoint != self.config.hermes_api_url:
            adapter = self._profile_adapters.get(profile_id)
            if adapter is None:
                adapter = HermesAdapter(replace(self.config, hermes_api_url=endpoint))
                self._profile_adapters[profile_id] = adapter
        yield from adapter.stream_events(messages, session_id, session_key)
        self.last_usage = dict(adapter.last_usage)

    def chat(self, messages: list[dict[str, Any]], session_id: str, session_key: str) -> str:
        if self.config.hermes_api_key:
            try:
                return self._chat_via_run(messages, session_id, session_key).strip()
            except Exception:
                pass
        return self._chat_completion(messages, session_id, session_key)

    def _chat_completion(self, messages: list[dict[str, Any]], session_id: str, session_key: str) -> str:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Hermes-Session-Id": session_id,
            "X-Hermes-Session-Key": session_key,
        }
        if self.config.hermes_api_key:
            headers["Authorization"] = f"Bearer {self.config.hermes_api_key}"
        payload = {
            "model": self.config.hermes_model,
            "messages": messages,
            "stream": False,
        }
        payload.update(_model_options_payload(self.config))
        request = urllib.request.Request(
            self.config.hermes_api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
        usage = data.get("usage")
        self.last_usage = usage if isinstance(usage, dict) else {}
        return _extract_reply(data)

    def _chat_via_run(self, messages: list[dict[str, Any]], session_id: str, session_key: str) -> str:
        final_text = ""
        for event in self._stream_run_events(messages, session_id, session_key):
            if event.get("event") == "final":
                final_text = str(event.get("content") or "")
        return final_text

    def stream_events(self, messages: list[dict[str, Any]], session_id: str, session_key: str):
        if self.config.hermes_api_key:
            try:
                yield from self._stream_run_events(messages, session_id, session_key)
                return
            except Exception:
                pass
        yield from self._stream_chat_completion_events(messages, session_id, session_key)

    def _stream_chat_completion_events(self, messages: list[dict[str, Any]], session_id: str, session_key: str):
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "text/event-stream",
            "X-Hermes-Session-Id": session_id,
            "X-Hermes-Session-Key": session_key,
        }
        if self.config.hermes_api_key:
            headers["Authorization"] = f"Bearer {self.config.hermes_api_key}"
        payload = {
            "model": self.config.hermes_model,
            "messages": messages,
            "stream": True,
        }
        payload.update(_model_options_payload(self.config))
        request = urllib.request.Request(
            self.config.hermes_api_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        final_parts: list[str] = []
        event_name = ""
        with urllib.request.urlopen(request, timeout=180) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    event_name = ""
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue
                payload_text = line[5:].strip()
                if payload_text == "[DONE]":
                    break
                try:
                    data = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue
                event = _stream_event_from_chunk(data, event_name=event_name)
                if event["event"] in {"final_delta", "assistant_delta"}:
                    final_parts.append(event["content"])
                    continue
                if event["event"] in {"thought", "tool"}:
                    yield event
                usage = data.get("usage")
                if isinstance(usage, dict):
                    self.last_usage = usage
        yield {"event": "final", "content": "".join(final_parts)}

    def _stream_run_events(self, messages: list[dict[str, Any]], session_id: str, session_key: str):
        instructions, run_input = _messages_to_run_parts(messages)
        session_snapshot = self.session_messages(session_id, session_key)
        known_message_ids = {
            str(item.get("id") or item.get("message_id") or "").strip()
            for item in session_snapshot
            if isinstance(item, dict) and str(item.get("id") or item.get("message_id") or "").strip()
        }
        conversation_history = _conversation_history_from_session_messages(session_snapshot)
        run_id = self._start_run(run_input, instructions, session_id, session_key, conversation_history=conversation_history)
        final_parts: list[str] = []
        pending_assistant_text: list[str] = []
        emitted_thoughts: set[str] = set()

        def flush_assistant_progress():
            text = "".join(pending_assistant_text).strip()
            pending_assistant_text.clear()
            if text and text not in emitted_thoughts:
                emitted_thoughts.add(text)
                return {"event": "thought", "content": text}
            return None
        request = urllib.request.Request(
            f"{_derive_v1_url(self.config.hermes_api_url)}/runs/{run_id}/events",
            headers=self._headers(session_key=session_key, accept="text/event-stream"),
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            data_lines: list[str] = []
            event_name = ""
            for raw_chunk in response:
                for raw_line in raw_chunk.splitlines(keepends=True):
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line:
                        event = _decode_sse_data(data_lines)
                        data_lines = []
                        if event is not None:
                            result = _stream_event_from_chunk(event, event_name=event_name)
                            if result["event"] in {"assistant_delta", "final_delta"}:
                                pending_assistant_text.append(result["content"])
                            elif result["event"] == "final":
                                usage = event.get("usage")
                                if isinstance(usage, dict):
                                    self.last_usage = usage
                                # Newer Hermes gateways attach this turn's authoritative
                                # transcript.  ``output`` is an aggregate, so it must never
                                # be used as Hermi's final reply when a transcript exists.
                                thought, final = _run_transcript_assistant_text(event.get("messages"))
                                if not final:
                                    thought, final = _session_turn_assistant_text(
                                        self.session_messages(session_id, session_key),
                                        known_message_ids,
                                    )
                                for content in thought:
                                    if content not in emitted_thoughts:
                                        emitted_thoughts.add(content)
                                        yield {"event": "thought", "content": content}
                                if final:
                                    result = {"event": "final", "content": final}
                                elif pending_assistant_text:
                                    result = {"event": "final", "content": "".join(pending_assistant_text).strip()}
                                yield result
                                return
                            elif result["event"] == "tool" and result["content"]:
                                # Hermes emits message/assistant deltas before a tool starts.
                                # This boundary proves that text is process narration, not final.
                                progress = flush_assistant_progress()
                                if progress:
                                    yield progress
                                yield result
                            elif result["event"] == "thought" and result["content"]:
                                text = result["content"].strip()
                                pending_text = "".join(pending_assistant_text).strip()
                                # Some Hermes models mirror visible assistant text through
                                # reasoning.available.  Keep its authoritative final delta
                                # pending until run.completed instead of showing it twice.
                                if pending_text and text == pending_text:
                                    continue
                                if text and text not in emitted_thoughts:
                                    emitted_thoughts.add(text)
                                    yield {"event": "thought", "content": text}
                        event_name = ""
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line[5:].strip())
        if final_parts:
            yield {"event": "final", "content": "".join(final_parts).strip()}

    def _start_run(
        self,
        run_input: Any,
        instructions: str,
        session_id: str,
        session_key: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "input": run_input,
            "session_id": session_id,
        }
        # ``hermes-agent`` is Hermi's compatibility placeholder, not a model
        # accepted by profile gateways.  Omit it so each Hermes profile uses
        # its configured model (maid, trainee, or imouto) for native runs.
        if self.config.hermes_model and self.config.hermes_model != "hermes-agent":
            payload["model"] = self.config.hermes_model
        payload.update(_model_options_payload(self.config))
        if instructions:
            payload["instructions"] = instructions
        if conversation_history:
            payload["conversation_history"] = conversation_history
        request = urllib.request.Request(
            f"{_derive_v1_url(self.config.hermes_api_url)}/runs",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(session_key=session_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Hermes runs API HTTP {exc.code}: {body[:500]}") from exc
        data = json.loads(body or "{}")
        run_id = str(data.get("run_id") or data.get("id") or "")
        if not run_id:
            raise RuntimeError("Hermes runs API did not return run_id")
        return run_id

    def session_history(self, session_id: str, session_key: str | None = None) -> list[dict[str, str]]:
        return _conversation_history_from_session_messages(self.session_messages(session_id, session_key))

    def session_messages(self, session_id: str, session_key: str | None = None) -> list[dict[str, Any]]:
        if not session_id:
            return []
        request = urllib.request.Request(
            f"{_derive_origin_url(self.config.hermes_api_url)}/api/sessions/{quote(session_id, safe='')}/messages",
            headers=self._headers(session_key=session_key),
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            return []
        except Exception:
            return []
        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError:
            return []
        raw_messages = data.get("data") or data.get("messages") or []
        if not isinstance(raw_messages, list):
            return []
        return [item for item in raw_messages if isinstance(item, dict)]

    def session_messages_profile(
        self,
        profile_id: str,
        session_id: str,
        session_key: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._profile_adapter(profile_id).session_messages(session_id, session_key)

    def _headers(self, session_key: str | None = None, accept: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if accept:
            headers["Accept"] = accept
        if self.config.hermes_api_key:
            headers["Authorization"] = f"Bearer {self.config.hermes_api_key}"
        if session_key:
            headers["X-Hermes-Session-Key"] = session_key
        return headers

    def delete_session(self, session_id: str, session_key: str | None = None) -> dict[str, Any]:
        if not session_id:
            return {"deleted": False, "skipped": "empty_session_id"}
        request = urllib.request.Request(
            f"{_derive_origin_url(self.config.hermes_api_url)}/api/sessions/{quote(session_id, safe='')}",
            headers=self._headers(session_key=session_key),
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"deleted": False, "missing": True}
            body = exc.read().decode("utf-8", errors="replace")
            return {"deleted": False, "error": f"HTTP {exc.code}: {body[:300]}"}
        except Exception as exc:
            return {"deleted": False, "error": f"{type(exc).__name__}: {exc}"}
        try:
            data = json.loads(body or "{}")
        except json.JSONDecodeError:
            data = {"raw": body}
        data["deleted"] = bool(data.get("deleted"))
        return data

    def delete_profile_session(
        self,
        profile_id: str,
        session_id: str,
        session_key: str | None = None,
    ) -> dict[str, Any]:
        result = self._profile_adapter(profile_id).delete_session(session_id, session_key)
        result.setdefault("profile_id", profile_id)
        return result


def _extract_reply(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content") if isinstance(message, dict) else message
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(item.get("text") or item.get("content") or "") for item in content if isinstance(item, dict))
    return str(content or "")


def _model_options_payload(config: HermiConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    effort = str(config.hermes_reasoning_effort or "").strip()
    if effort:
        payload["reasoning_effort"] = effort
    if config.hermes_max_tokens:
        payload["max_tokens"] = int(config.hermes_max_tokens)
    return payload


def _stream_event_from_chunk(data: dict[str, Any], event_name: str = "") -> dict[str, str]:
    event_type = str(event_name or data.get("event") or data.get("type") or "")
    if event_type == "assistant.delta":
        return {"event": "assistant_delta", "content": str(data.get("delta") or data.get("text") or "")}
    if event_type == "message.delta":
        return {"event": "final_delta", "content": str(data.get("delta") or data.get("text") or "")}
    if event_type == "run.completed":
        return {"event": "final", "content": str(data.get("output") or data.get("content") or "")}
    if event_type == "run.failed":
        raise RuntimeError(str(data.get("error") or "Hermes run failed"))
    if event_type in {"thought", "reasoning", "reasoning.delta", "reasoning.available"}:
        return {"event": "thought", "content": str(data.get("content") or data.get("text") or "")}
    if (
        event_type in {"tool", "tool_call", "tool_result", "tool_progress", "approval.request"}
        or event_type.startswith("tool.")
        or event_type.startswith("hermes.tool.")
    ):
        return {"event": "tool", "content": _format_tool_event(event_type, data)}
    if event_type in {"thought", "tool"}:
        return {"event": event_type, "content": str(data.get("content") or data.get("text") or "")}
    choices = data.get("choices") or []
    if choices:
        delta = choices[0].get("delta") or {}
        if isinstance(delta, dict):
            for key in ("reasoning", "reasoning_content", "thought"):
                if delta.get(key):
                    return {"event": "thought", "content": str(delta[key])}
            if delta.get("tool_calls"):
                return {"event": "tool", "content": json.dumps(delta["tool_calls"], ensure_ascii=False)}
            content = delta.get("content")
            if content:
                return {"event": "final_delta", "content": str(content)}
    return {"event": "", "content": ""}


def _format_tool_event(event_type: str, data: dict[str, Any]) -> str:
    name = data.get("name") or data.get("tool") or data.get("tool_name") or data.get("id") or "tool"
    phase = data.get("phase") or data.get("status") or data.get("state") or event_type
    detail = data.get("content") or data.get("text") or data.get("message") or data.get("summary")
    if detail:
        return f"{name}: {phase} - {detail}"
    payload = data.get("payload")
    if isinstance(payload, dict):
        payload_name = payload.get("name") or payload.get("tool") or payload.get("id")
        payload_phase = payload.get("phase") or payload.get("status") or payload.get("state")
        if payload_name or payload_phase:
            return f"{payload_name or name}: {payload_phase or phase}"
    return f"{name}: {phase}"


def _derive_v1_url(api_url: str) -> str:
    url = str(api_url).strip().rstrip("/")
    if url.endswith("/v1/chat/completions"):
        return url[: -len("/chat/completions")]
    if url.endswith("/chat/completions"):
        return url[: -len("/chat/completions")]
    if url.endswith("/v1"):
        return url
    return url


def _profile_api_urls(raw: str) -> dict[str, str]:
    endpoints: dict[str, str] = {}
    for item in str(raw or "").split(","):
        profile_id, separator, endpoint = item.partition("=")
        if separator and profile_id.strip() and endpoint.strip():
            endpoints[profile_id.strip()] = endpoint.strip()
    return endpoints


def _derive_origin_url(api_url: str) -> str:
    parts = urlsplit(str(api_url).strip())
    if not parts.scheme or not parts.netloc:
        return str(api_url).strip().rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")


def _conversation_history_from_session_messages(raw_messages: list[Any]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("author") or "").strip()
        if role not in {"user", "assistant", "system"}:
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or part.get("content") or "")
                for part in content
                if isinstance(part, dict)
            )
        text = str(content or "").strip()
        if text:
            history.append({"role": role, "content": text})
    return history


def _session_turn_assistant_text(
    raw_messages: list[Any], known_message_ids: set[str],
) -> tuple[list[str], str]:
    """Split newly persisted Hermes assistant segments into progress and final text."""
    assistant_text: list[str] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        message_id = str(item.get("id") or item.get("message_id") or "").strip()
        if not message_id or message_id in known_message_ids:
            continue
        if str(item.get("role") or item.get("author") or "").strip().lower() != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or part.get("content") or "")
                for part in content
                if isinstance(part, dict)
            )
        text = str(content or "").strip()
        if text:
            assistant_text.append(text)
    if not assistant_text:
        return [], ""
    return assistant_text[:-1], assistant_text[-1]


def _run_transcript_assistant_text(raw_messages: Any) -> tuple[list[str], str]:
    """Split Hermes ``run.completed.messages`` into process and final text."""
    if not isinstance(raw_messages, list):
        return [], ""
    assistant_text: list[str] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        if str(item.get("role") or item.get("author") or "").strip().lower() != "assistant":
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "".join(
                str(part.get("text") or part.get("content") or "")
                for part in content
                if isinstance(part, dict)
            )
        text = str(content or "").strip()
        if text:
            assistant_text.append(text)
    if not assistant_text:
        return [], ""
    return assistant_text[:-1], assistant_text[-1]


def _messages_to_run_parts(messages: list[dict[str, Any]]) -> tuple[str, Any]:
    instructions: list[str] = []
    user_inputs: list[str] = []
    structured_inputs: list[dict[str, Any]] = []
    has_structured = False
    for message in messages:
        role = str(message.get("role") or "")
        content = message.get("content") or ""
        if role == "system":
            instructions.append(str(content))
        elif role == "user":
            structured_inputs.append({"role": "user", "content": content})
            if isinstance(content, str):
                user_inputs.append(content)
            else:
                has_structured = True
    run_input: Any = structured_inputs if has_structured else "\n\n".join(part for part in user_inputs if part).strip()
    return "\n\n".join(part for part in instructions if part).strip(), run_input


def _decode_sse_data(data_lines: list[str]) -> dict[str, Any] | None:
    if not data_lines:
        return None
    data = "\n".join(data_lines).strip()
    if not data or data == "[DONE]":
        return None
    return json.loads(data)
