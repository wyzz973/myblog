from app.services.pet_assignment import SPECIES_BY_RARITY
from app.services.pet_defaults import (
    BASE_INSTRUCTION,
    DEFAULT_PERSONAS,
    DEFAULT_TEMPLATES,
)

EXPECTED_TEMPLATES = {
    "greet", "idle_monologue", "summary_react", "selection_explain", "selection_qa",
    "free_chat", "follow_up", "article_finished", "reading_assist", "code_assist",
    "recommend_next", "pet_care",
}


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
    assert set(DEFAULT_TEMPLATES) == EXPECTED_TEMPLATES
    for mode, tpl in DEFAULT_TEMPLATES.items():
        assert tpl.strip(), f"{mode} template is empty"
        assert len(tpl) <= 800


def test_base_instruction_has_species_and_persona_placeholders():
    assert "{species}" in BASE_INSTRUCTION
    assert "{persona}" in BASE_INSTRUCTION
    assert "{behavior}" in BASE_INSTRUCTION
    assert "{visitor_background}" in BASE_INSTRUCTION
    assert "Persona catchphrases are optional seasoning" in BASE_INSTRUCTION
    assert "Most replies should express personality" in BASE_INSTRUCTION
    assert "avoid unrelated hunger" in BASE_INSTRUCTION
    assert "do not start every reply" in BASE_INSTRUCTION


def test_default_voice_rules_do_not_force_catchphrases():
    all_text = "\n".join([
        BASE_INSTRUCTION,
        *DEFAULT_PERSONAS.values(),
        *DEFAULT_TEMPLATES.values(),
    ])
    forbidden = [
        "Lean on your persona's catchphrase",
        "use its rhythm, catchphrases",
        "永远在抱怨",
        "挂嘴边",
        "每句话像拥抱",
        "频繁感叹",
        "永远在抱怨累或想吃",
        "想吃饭",
    ]
    for phrase in forbidden:
        assert phrase not in all_text
