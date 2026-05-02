from app.services.pet_assignment import SPECIES_BY_RARITY
from app.services.pet_defaults import (
    BASE_INSTRUCTION,
    DEFAULT_PERSONAS,
    DEFAULT_TEMPLATES,
)


def test_every_species_has_persona():
    """SPECIES_BY_RARITY and DEFAULT_PERSONAS must stay in lock-step."""
    expected = {s for pool in SPECIES_BY_RARITY.values() for s in pool}
    assert set(DEFAULT_PERSONAS) == expected, (
        "personas drift: "
        f"missing={expected - set(DEFAULT_PERSONAS)} "
        f"extra={set(DEFAULT_PERSONAS) - expected}"
    )


def test_personas_non_empty_and_within_limit():
    for species, text in DEFAULT_PERSONAS.items():
        assert text.strip(), f"{species} persona is empty"
        assert len(text) <= 400, f"{species} persona exceeds 400 chars"


def test_default_templates_present():
    assert set(DEFAULT_TEMPLATES) == {
        "greet", "idle_monologue", "summary_react", "selection_explain", "selection_qa"
    }
    for mode, tpl in DEFAULT_TEMPLATES.items():
        assert tpl.strip(), f"{mode} template is empty"
        assert len(tpl) <= 800


def test_base_instruction_has_species_and_persona_placeholders():
    assert "{species}" in BASE_INSTRUCTION
    assert "{persona}" in BASE_INSTRUCTION
