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
    assert "summoned you out of nowhere" in out  # from greet template


def test_build_system_unknown_species_falls_back_to_system_prompt():
    """Defensive: cookie/fingerprint produced a species not in the catalog."""
    cfg = PetConfig()
    out = build_system(cfg, species="nonexistent", mode="greet", title=None,
                       tag=None, summary=None, selection=None)
    assert cfg.system_prompt in out


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
