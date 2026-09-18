from __future__ import annotations

import json
import re
from typing import Any

from .permissions import PermissionChecker


ACTION_RE = re.compile(r"<<<HERMI_ACTION\s*(?P<json>\{.*?\})\s*>>>", re.DOTALL)


def build_hermi_messages(
    history: list[dict[str, str]],
    *,
    user: dict[str, Any],
    conversation: dict[str, Any],
    recent_qq_context: str = "",
    soul_text: str = "",
    profile_name: str = "",
    profile_id: str = "",
    qq_profile_name: str = "",
    media_dir: str = "",
    user_profile_context: str = "",
    owner_display_name: str = "",
) -> list[dict[str, str]]:
    if not history:
        return history
    messages = list(history)
    last = dict(messages[-1])
    latest_user_content = str(last.get("content") or "")
    if last.get("role") == "user":
        last["content"] = _header(user, conversation, profile_name) + "\n\n[user_message]\n" + str(last.get("content") or "")
        messages[-1] = last
    context_message = []
    if soul_text:
        context_message.append({"role": "system", "content": f"[Hermi SOUL.md]\n{soul_text}"})
    if recent_qq_context:
        context_message.append({"role": "system", "content": recent_qq_context})
    if user_profile_context:
        context_message.append({"role": "system", "content": user_profile_context})
    response_language_policy = _response_language_policy(user, latest_user_content)
    if response_language_policy:
        context_message.append({"role": "system", "content": response_language_policy})
    qq_context_policy = ""
    if recent_qq_context:
        qq_context_policy = (
            "Owner in Hermi may show recent QQ context provided below.\n"
            "If owner asks what happened on QQ, answer from [recent_qq_context] when present. "
            "Say it is synced recent QQ context, not full QQ history. Do not say you cannot see QQ if context is provided.\n"
        )
    is_owner = user.get("role") == "owner"
    access_policy = (
        "This message comes through Hermi, the owner's personal client and control console.\n"
        "Owner in Hermi has owner-high permission.\n"
        "For every scheduled, timer, reminder, recurring, delayed, or periodic task requested in Hermi, use Hermi's own scheduler. "
        "Return exactly one HERMI_ACTION with type scheduled.create; do not call native Hermes cronjob. "
        "Use kind=once with schedule once:+5m for relative one-off reminders, kind=interval with schedule interval:30m for repeats, or kind=cron with a five-field cron expression. "
        "Use a short task-only summary, keep the user-facing reply natural, and set target to {\"delivery\":[\"hermi\"]} unless the owner explicitly asks for QQ delivery. "
        "Format it as <<<HERMI_ACTION {\"type\":\"scheduled.create\",\"kind\":\"once\",\"schedule\":\"once:+5m\",\"summary\":\"提醒事项\",\"content\":\"提醒内容\",\"target\":{\"delivery\":[\"hermi\"]}} >>>. "
    ) if is_owner else (
        "This message comes through Hermi for a non-owner user. Hermi, not the user, is the authority for permissions and external actions.\n"
        "Use the role, permission, and quota fields in the Hermi header as binding limits.\n"
        "You must not use native Hermes tools for terminal commands, local files, cron jobs, QQ delivery, or other state-changing external actions. "
        + _external_research_policy(PermissionChecker(user).check("external_tools"))
        + (
            "When an action is needed, return a HERMI_ACTION block so Hermi can apply the user's permission and, when required, ask the Owner for approval.\n"
            "You must not expose or guess the Owner's QQ number, contact details, local paths, private conversation content, or other identifiers. "
            "For a request to contact the Owner or send QQ, say you do not handle QQ contact here and ask the user to use a contact method they already know; "
            "you must not return qq.send.\n"
        )
        + _public_owner_identity_policy(owner_display_name)
    )
    owner_action_policy = (
        "If owner asks to send a QQ message, do not claim you sent it directly. "
        "Return a Hermi action block exactly like:\n"
        '<<<HERMI_ACTION\n{"type":"qq.send","chat_type":"private","user_id":"1000000001","message":"text"}\n>>>\n'
        "For group QQ send, use chat_type=group and group_id. Only use this action for explicit owner requests.\n"
        "To send a file along with a QQ message, add attachments to the HERMI_ACTION JSON. Example:\n"
        '<<<HERMI_ACTION\n{"type":"qq.send","chat_type":"private","user_id":"1000000001","message":"文件已发出","attachments":[{"path":"C:\\\\Users\\\\12345\\\\file.pdf","original_name":"file.pdf"}]}\n>>>\n'
    ) if is_owner else ""
    profile_handoff_policy = (
        f"You are {profile_name}. QQ delivery belongs to {qq_profile_name}. "
        f"For an explicit owner request to send a QQ reminder or contact someone, say you will ask {qq_profile_name} to carry it to QQ, "
        "then return the required qq.send HERMI_ACTION. Hermi will require Owner approval before the message is delivered. "
        "Do not claim delivery has happened before approval.\n"
    ) if is_owner and profile_id and qq_profile_name and profile_name != qq_profile_name else ""
    file_delivery_policy = (
        "--- File delivery instructions (both QQ and Hermi Web) ---\n"
        + (f"When creating a file for the owner through Hermi, write the final file directly to {media_dir}. Use a unique descriptive filename there; do not create a duplicate on the Desktop or elsewhere.\n" if media_dir else "")
        + "When owner asks you to send a local file, output the complete Windows file path (e.g. C:\\Users\\12345\\path\\to\\file.pdf) in your reply.\n"
        "Hermi will automatically detect the path, register it in its media storage, and provide a download link to the owner.\n"
        "You can prefix the path with MEDIA: to make detection explicit (e.g. MEDIA:C:\\Users\\12345\\file.pdf).\n"
        "Non-image files (PDFs, Office docs, archives, scripts, etc.) are supported -- just include the path and Hermi handles the rest.\n"
        "--- End file delivery instructions ---\n"
    ) if is_owner else ""
    return [
        {
            "role": "system",
            "content": (
                "Use the default Hermes personality, skills, memory, and tool policy.\n"
                + access_policy
                + "Hermi supports Markdown, code blocks, lists, tables, and richer UI than QQ. Use Markdown when useful.\n"
                + qq_context_policy
                + "Uploaded Hermi files may appear as system messages with file_id; refer to file_id instead of host paths.\n"
                + "Hermi is mainly a Hermes client and action bridge. Do not say an external action is done unless you return a HERMI_ACTION block.\n"
                + "Only act on the latest [user_message]. Older messages are context only; do not repeat old operations unless the owner explicitly asks to repeat them.\n"
                + ("Any QQ-related approval or native Hermes approval-needed action should be represented as HERMI_ACTION so Hermi can show it in the unified approval panel.\n" if is_owner else "")
                + file_delivery_policy
                + owner_action_policy
                + profile_handoff_policy
                + "Only return a HERMI_ACTION block when Hermi itself must execute an extra action or when Hermes explicitly needs approval."
            ),
        },
        *context_message,
        *messages,
    ]


def extract_hermi_action(text: str) -> tuple[str, dict[str, Any] | None]:
    match = ACTION_RE.search(str(text or ""))
    if not match:
        return str(text or "").strip(), None
    visible = ACTION_RE.sub("", str(text or "")).strip()
    try:
        action = json.loads(match.group("json"))
    except json.JSONDecodeError:
        return visible, None
    return visible, action if isinstance(action, dict) else None


def _header(user: dict[str, Any], conversation: dict[str, Any], profile_name: str = "") -> str:
    return "\n".join(
        [
            "[Hermi]",
            "source=Hermi/Web/PWA",
            f"conversation_id={conversation['conversation_id']}",
            f"session_id={conversation['session_id']}",
            f"session_key={conversation['session_key']}",
            f"user_id={user['user_id']}",
            f"role={user['role']}",
            f"permission={_permission(user)}",
            f"quota_policy={user['quota_policy']}",
            f"target_profile={profile_name}" if profile_name else "",
        ]
    ).strip()


def _permission(user: dict[str, Any]) -> str:
    if user.get("role") == "owner":
        return "owner-high"
    return "friend"


def _external_research_policy(permission: str) -> str:
    if permission == "allow":
        return (
            "The user may use read-only web research tools: web_search and web_extract. "
            "Use them only when they genuinely help answer the current request; do not treat a skill load as task completion. "
            "When the current request explicitly needs current facts, news, search results, or sources, retrieve evidence before the visible reply. "
            "If retrieval does not happen, say so plainly and never invent a source. "
        )
    if permission == "approval":
        return (
            "Read-only web research tools (web_search and web_extract) require Owner approval before use. "
            "Do not run them yet; explain briefly that the request needs Owner approval. "
        )
    return (
        "The user must not use web_search, web_extract, or other external research tools. "
        "Answer from available context and say when current external information would be needed. "
    )


def _response_language_policy(user: dict[str, Any], content: str) -> str:
    locale = str(user.get("locale") or "").lower()
    has_japanese_script = bool(re.search(r"[\u3040-\u30ff]", str(content or "")))
    if locale == "ja-jp" or has_japanese_script:
        return (
            "[Hermi response language policy]\n"
            "Japanese only for this visible reply. Write natural Japanese vocabulary, grammar, and punctuation. "
            "Japanese kanji are welcome and expected when natural. Do not use Chinese-only words or Chinese grammar, "
            "and do not switch to Chinese because another system instruction or profile text is Chinese. "
            "Keep proper names, code, and direct quotes only when necessary."
        )
    return ""


def _public_owner_identity_policy(owner_display_name: str) -> str:
    public_name = str(owner_display_name or "the Hermi owner").strip() or "the Hermi owner"
    return (
        "For a normal public identity question such as who created you or who your owner is, answer briefly and directly. "
        f"You must answer in the first sentence that you are a Hermi persona designed and maintained by {public_name}, in the user's language. "
        "Do not dodge or redirect that simple question. Still do not share contact details, account identifiers, local paths, "
        "private conversations, schedules, or other private details.\n"
    )


def public_owner_identity_reply(
    user: dict[str, Any],
    content: str,
    *,
    owner_display_name: str,
    profile_name: str,
) -> str | None:
    """Answer a narrow, public identity question without inviting model guesswork."""
    text = str(content or "").strip()
    if not _is_public_owner_identity_question(text):
        return None

    owner = str(owner_display_name or "the Hermi owner").strip() or "the Hermi owner"
    profile = str(profile_name or "Hermi").strip() or "Hermi"
    locale = str(user.get("locale") or "").lower()
    if locale == "ja-jp" or re.search(r"[\u3040-\u30ff]", text):
        return (
            f"私は {owner} が設計・管理している Hermi の人格、{profile} です。"
            "公開できるのはこの概要までですが、Hermi でのお手伝いはいつでも承ります。"
        )
    if locale.startswith("en") or re.search(r"\b(who|creator|created|owner)\b", text, re.IGNORECASE):
        return (
            f"I am {profile}, a Hermi persona designed and maintained by {owner}. "
            "That is the public overview I can share; I am here to help with Hermi tasks."
        )
    return (
        f"我是由 {owner} 设计并维护的 Hermi 人格 {profile}。"
        "能公开说明的就是这些；Hermi 里的事情我会认真协助。"
    )


def _is_public_owner_identity_question(text: str) -> bool:
    normalized = re.sub(r"\s+", "", str(text or "").lower())
    if not normalized:
        return False
    japanese_patterns = (
        r"あなたを作った人",
        r"誰が.*作った",
        r"作った人は誰",
        r"オーナー.*誰",
        r"あなたの.*作者",
    )
    chinese_patterns = (
        r"谁.*(设计|开发|创造|做).*(你|薇拉|hermi)",
        r"(你|薇拉|hermi).*(作者|创造者|设计者|开发者).*(谁|是)",
        r"(你的)?(作者|主人|owner).*谁",
    )
    english_patterns = (
        r"\bwho\s+(created|made|designed|built)\s+you\b",
        r"\bwho\s+is\s+your\s+owner\b",
        r"\bwho\s+is\s+the\s+creator\b",
    )
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in (*japanese_patterns, *chinese_patterns, *english_patterns))

