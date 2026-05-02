from app.schemas.pet import PetConfig
from app.services.pet_prompt import (
    build_system,
    infer_mode,
    truncate_selection,
    _safe_format,
)


def test_safe_format_substitutes_known_variables():
    out = _safe_format("Title: {title}", title="Hi", summary="x")
    assert out == "Title: Hi"


def test_safe_format_leaves_unknown_placeholder_literal():
    """Admin-typed garbage placeholders must not raise."""
    out = _safe_format("Hello {garbage}", title="t")
    assert out == "Hello {garbage}"


def test_safe_format_handles_braces_in_selection():
    """A selection containing literal { or } must not be re-interpreted."""
    out = _safe_format("X: {selection}", selection="if (x) { return; }")
    assert out == "X: if (x) { return; }"


def test_truncate_selection_caps_at_max_chars():
    s = "a" * 1000
    assert truncate_selection(s, 500) == "a" * 500


def test_truncate_selection_returns_empty_for_none():
    assert truncate_selection(None, 500) == ""


def test_build_system_known_species_greet_mode():
    cfg = PetConfig()
    out = build_system(cfg, species="cat", mode="greet", title=None, tag=None,
                       summary=None, selection=None)
    assert "cat" in out
    assert cfg.personas.cat in out
    assert "tapped on you" in out  # from greet template


def test_build_system_unknown_species_falls_back_to_system_prompt():
    """Defensive: cookie/fingerprint produced a species not in the catalog."""
    cfg = PetConfig()
    out = build_system(cfg, species="nonexistent", mode="greet", title=None,
                       tag=None, summary=None, selection=None)
    assert cfg.system_prompt in out
    assert "Persona:" not in out  # didn't accidentally render BASE scaffold


def test_build_system_summary_react_injects_title_and_summary():
    cfg = PetConfig()
    out = build_system(cfg, species="cat", mode="summary_react",
                       title="Hello", tag="devtools", summary="A summary.",
                       selection=None)
    assert "Hello" in out
    assert "A summary." in out
    assert "devtools" in out


def test_build_system_selection_explain_truncates_selection():
    cfg = PetConfig()
    long_sel = "x" * 1000
    out = build_system(cfg, species="cat", mode="selection_explain",
                       title="T", tag="t", summary="s", selection=long_sel)
    # max_context_chars=500 by default
    assert "x" * 500 in out
    assert "x" * 501 not in out


def test_build_system_persona_placeholder_is_not_recursive():
    """If admin typed {persona} in a mode template, it must not recurse."""
    cfg = PetConfig()
    cfg.mode_templates.greet = "Hi {persona} {title}"
    out = build_system(cfg, species="cat", mode="greet", title="T", tag=None,
                       summary=None, selection=None)
    # {persona} should remain literal in the mode template's output (not
    # re-replaced by the persona text again — that's already in BASE).
    assert "{persona}" in out
    assert "T" in out


def test_infer_mode_no_post_no_selection_returns_greet():
    assert infer_mode(post_id=None, selection=None) == "greet"


def test_infer_mode_post_no_selection_returns_summary_react():
    assert infer_mode(post_id="hello", selection=None) == "summary_react"


def test_infer_mode_with_selection_returns_selection_qa():
    """Server-side default — frontend must explicitly pass
    'selection_explain' to opt into code mode."""
    assert infer_mode(post_id="hello", selection="some text") == "selection_qa"


def test_infer_mode_selection_without_post_still_returns_selection_qa():
    """Selection without post_id is unusual but should still produce qa."""
    assert infer_mode(post_id=None, selection="x") == "selection_qa"


def test_infer_mode_empty_string_selection_treated_as_no_selection():
    """selection='' (frontend may send empty string) routes by post_id."""
    assert infer_mode(post_id="hello", selection="") == "summary_react"
    assert infer_mode(post_id=None, selection="") == "greet"


def test_safe_format_blocks_attribute_traversal():
    """{title.__class__} must NOT leak Python internals."""
    out = _safe_format("X: {title.__class__}", title="hi")
    # The whole "{title.__class__}" stays literal because attribute access
    # is disabled and "title.__class__" is not a known key.
    assert "{title.__class__}" in out
    assert "<class" not in out


def test_safe_format_blocks_index_access():
    out = _safe_format("X: {title[0]}", title="hi")
    assert "{title[0]}" in out


def test_safe_format_returns_template_on_malformed():
    """Lone braces / numeric refs must not raise."""
    assert _safe_format("hello {", title="x") == "hello {"
    assert _safe_format("hello }", title="x") == "hello }"
    assert _safe_format("hello {0}", title="x") == "hello {0}"


def test_build_system_uses_summary_max_chars_from_config():
    cfg = PetConfig()
    cfg.summary_max_chars = 50
    long_summary = "a" * 300
    out = build_system(cfg, species="cat", mode="summary_react",
                       title="T", tag="t", summary=long_summary, selection=None)
    assert "a" * 50 in out
    assert "a" * 51 not in out


def test_safe_format_ignores_format_spec_width():
    """Defends against {title:>1000000000} memory amplification.
    Format specs (width / alignment / precision) are ignored entirely."""
    out = _safe_format("X: {title:>1000000}", title="hi")
    # Should NOT pad to 1M chars — should just substitute the value
    assert out == "X: hi"


def test_safe_format_ignores_format_spec_padding():
    out = _safe_format("[{title:^10}]", title="hi")
    # Center-pad to 10 chars would normally yield "[    hi    ]";
    # we ignore the spec and emit the value as-is.
    assert out == "[hi]"
