from app.services.pet_usage import estimate_text_tokens, estimate_turn_tokens


def test_estimate_text_tokens_handles_english_and_cjk_conservatively():
    assert estimate_text_tokens("hello world " * 10) >= 25
    assert estimate_text_tokens("这是一段中文内容" * 10) >= 40
    assert estimate_text_tokens("cleanup 这段代码为什么需要 cleanup") >= 8


def test_estimate_turn_tokens_counts_system_messages_and_reply():
    usage = estimate_turn_tokens(
        system="system prompt",
        messages=[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "old"}],
        reply="new reply",
    )
    assert usage["estimated_input_tokens"] > 0
    assert usage["estimated_output_tokens"] > 0
    assert usage["estimated_total_tokens"] == (
        usage["estimated_input_tokens"] + usage["estimated_output_tokens"]
    )
