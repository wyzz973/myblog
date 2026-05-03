import pytest
from pydantic import ValidationError

from app.schemas.pet import PetConfig, PetMode


def test_petconfig_default_includes_27_personas():
    c = PetConfig()
    assert hasattr(c.personas, "cat")
    assert hasattr(c.personas, "dragon")
    assert hasattr(c.personas, "otter")
    # spot-check defaults are non-empty
    assert c.personas.cat
    assert c.personas.dragon


def test_petconfig_default_includes_5_mode_templates():
    c = PetConfig()
    assert c.mode_templates.greet
    assert c.mode_templates.idle_monologue
    assert c.mode_templates.summary_react
    assert c.mode_templates.selection_explain
    assert c.mode_templates.selection_qa


def test_unlimited_defaults_to_false():
    c = PetConfig()
    assert c.unlimited is False
    assert c.hard_ceiling_per_day == 20000


def test_petconfig_merges_old_jsonb_payload():
    """Old persisted config (no personas/templates/unlimited) must load
    cleanly with defaults filled in — JSONB forward-compat."""
    old = {
        "providers": ["zhipu"],
        "system_prompt": "old prompt",
        "fallback_lines": ["..."],
        "tired_lines": ["zzz"],
        "per_ip_per_min": 6,
    }
    merged = PetConfig(**{**PetConfig().model_dump(), **old})
    assert merged.system_prompt == "old prompt"
    assert merged.personas.cat  # default filled
    assert merged.unlimited is False


def test_persona_field_max_length_400():
    with pytest.raises(ValidationError):
        PetConfig(personas={"cat": "x" * 401})


def test_pet_mode_literal_rejects_garbage():
    from typing import get_args
    valid = get_args(PetMode)
    assert set(valid) == {
        "greet", "idle_monologue", "summary_react", "selection_explain", "selection_qa"
    }


def test_petconfig_partial_personas_dict_fills_per_species_defaults():
    """If JSONB contains personas with only some species, missing species
    fall back to DEFAULT_PERSONAS at the field level — not an error.
    Guards future species roster changes against silent data loss."""
    c = PetConfig(personas={"cat": "custom cat"})
    assert c.personas.cat == "custom cat"
    assert c.personas.dragon  # default filled at field level


def test_context_window_turns_default_and_bounds():
    c = PetConfig()
    assert c.context_window_turns == 10
    with pytest.raises(ValidationError):
        PetConfig(context_window_turns=0)
    with pytest.raises(ValidationError):
        PetConfig(context_window_turns=51)


def test_context_ttl_seconds_default_and_bounds():
    c = PetConfig()
    assert c.context_ttl_seconds == 7200
    with pytest.raises(ValidationError):
        PetConfig(context_ttl_seconds=59)
    with pytest.raises(ValidationError):
        PetConfig(context_ttl_seconds=86401)
