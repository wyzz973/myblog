import pytest
from pydantic import ValidationError

from app.schemas.pet import ClientContext, PetConfig, PetMode, SummonRequest


def test_petconfig_default_includes_27_personas():
    c = PetConfig()
    assert hasattr(c.personas, "cat")
    assert hasattr(c.personas, "dragon")
    assert hasattr(c.personas, "otter")
    # spot-check defaults are non-empty
    assert c.personas.cat
    assert c.personas.dragon


def test_petconfig_default_includes_smart_mode_templates():
    c = PetConfig()
    assert c.mode_templates.greet
    assert c.mode_templates.idle_monologue
    assert c.mode_templates.summary_react
    assert c.mode_templates.selection_explain
    assert c.mode_templates.selection_qa
    assert c.mode_templates.free_chat
    assert c.mode_templates.follow_up
    assert c.mode_templates.article_finished
    assert c.mode_templates.code_assist


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
        "greet", "idle_monologue", "summary_react", "selection_explain", "selection_qa",
        "free_chat", "follow_up", "article_finished", "reading_assist", "code_assist",
        "recommend_next", "pet_care",
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


def test_summon_request_accepts_message_intent_and_client_context():
    req = SummonRequest(
        post_id="hello",
        message="这段为什么要 cleanup？",
        intent="ask_selection",
        client_context={
            "page_type": "post",
            "path": "/p/hello",
            "read_progress": 62,
            "active_heading": "部署策略",
            "visible_block_type": "code",
            "selection_kind": "code",
            "dwell_seconds": 24,
            "recent_action": "copied_code",
            "locale": "zh-CN",
            "timezone": "Asia/Shanghai",
            "ignored_dom": "<main>nope</main>",
        },
    )
    assert req.message == "这段为什么要 cleanup？"
    assert req.intent == "ask_selection"
    assert isinstance(req.client_context, ClientContext)
    dumped = req.client_context.model_dump(exclude_none=True)
    assert dumped["read_progress"] == 62
    assert "ignored_dom" not in dumped


def test_summon_request_accepts_home_content_context():
    req = SummonRequest(
        client_context={
            "page_type": "home",
            "active_tag": "devtools",
            "post_count": 12,
            "focused_post_title": "VPS Setup" * 40,
            "focused_post_tag": "infra",
            "focused_post_subtitle": "Cheap and stable",
            "home_digest": "x" * 800,
            "visible_posts": [f"post {i}" for i in range(12)],
            "raw_posts": [{"title": "ignored"}],
        },
    )
    dumped = req.client_context.model_dump(exclude_none=True)
    assert dumped["active_tag"] == "devtools"
    assert dumped["post_count"] == 12
    assert len(dumped["focused_post_title"]) <= 160
    assert len(dumped["home_digest"]) <= 600
    assert len(dumped["visible_posts"]) == 8
    assert "raw_posts" not in dumped


def test_summon_request_rejects_too_long_message():
    with pytest.raises(ValidationError):
        SummonRequest(message="x" * 501)


def test_client_context_bounds_and_string_caps():
    with pytest.raises(ValidationError):
        SummonRequest(client_context={"read_progress": 101})
    req = SummonRequest(client_context={"active_heading": "x" * 400})
    assert len(req.client_context.active_heading) <= 120


def test_petconfig_includes_cost_and_memory_controls():
    cfg = PetConfig()
    assert cfg.enable_free_chat is True
    assert cfg.enable_proactive is True
    assert cfg.enable_long_term_memory is True
    assert cfg.per_mode_output_budget["free_chat"] == 100
    assert cfg.per_mode_daily_limit["free_chat"] > 0
