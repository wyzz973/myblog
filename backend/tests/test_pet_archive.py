from app.services import pet_archive


def test_sanitize_text_redacts_common_secret_shapes_and_truncates():
    raw = "prefix sk-abcdefghijklmnopqrstuvwxyz0123456789 bearer token=abc123456789"

    out = pet_archive.sanitize_text(raw, max_chars=24)

    assert "sk-" not in out
    assert "abc123456789" not in out
    assert len(out) <= 24
    assert "[redacted]" in out


def test_sanitize_turns_redacts_content_without_mutating_input():
    turns = [{"role": "user", "content": "api_key=abc123456789"}]

    out = pet_archive.sanitize_turns(turns, max_chars=80)

    assert out == [{"role": "user", "content": "api_key=[redacted]"}]
    assert turns[0]["content"] == "api_key=abc123456789"
