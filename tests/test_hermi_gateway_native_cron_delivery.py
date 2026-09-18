from hermi_gateway.app import (
    _parse_native_cron_request,
    _sanitize_native_cron_delivery_prompt,
)


def test_qq_native_cron_prompt_is_final_text_not_delivery_instruction():
    text = (
        "schedule=1m deliver=origin,qq:1000000001 "
        "prompt=\u7ed9\u8001\u54e5\u53d1\u4e00\u6761\u7b80\u77ed\u7684QQ\u79c1\u804a\u6d88\u606f\uff1a"
        "\u54e5\uff0c\u4e0b\u73ed\u65f6\u95f4\u5230\u5566\uff01\u522b\u62d6\u4e86\uff0c"
        "\u8d76\u7d27\u6536\u62fe\u8d70\u4eba\uff5e"
    )

    parsed = _parse_native_cron_request(text, {"session_id": "s1", "conversation_id": "c1"})

    assert parsed is not None
    assert "\u54e5\uff0c\u4e0b\u73ed\u65f6\u95f4\u5230\u5566\uff01\u522b\u62d6\u4e86\uff0c\u8d76\u7d27\u6536\u62fe\u8d70\u4eba\uff5e" in parsed["prompt"]
    assert "\u539f\u6837\u8f93\u51fa" in parsed["prompt"]
    assert "\u53d1" not in parsed["prompt"]
    assert "QQ" not in parsed["prompt"]
    assert "\u79c1\u804a" not in parsed["prompt"]


def test_qq_native_cron_sanitizer_removes_implicit_remind_qq_wording():
    prompt = _sanitize_native_cron_delivery_prompt(
        "\u518d\u8bd5\u8bd5\uff1f1\u5206\u949f\u540e\u63d0\u9192QQ\u8ba9\u6211\u4e0b\u73ed\uff01",
        "origin,qq:1000000001",
    )

    assert "\u4e0b\u73ed" in prompt
    assert "QQ" not in prompt
    assert "\u53d1" not in prompt
    assert "\u79c1\u804a" not in prompt

