from app.schemas.pet import PetConfig
from app.services.pet_prompt import build_messages


def test_build_messages_with_empty_prior_yields_one_user_turn():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="greet",
        title=None, tag=None, summary=None, selection=None,
        prior=[],
    )
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "tapped on you" in msgs[0]["content"]


def test_build_messages_summary_react_scene_tag():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="summary_react",
        title="Hello", tag="devtools", summary="A summary.", selection=None,
        prior=[],
    )
    last = msgs[-1]
    assert last["role"] == "user"
    assert "Hello" in last["content"]
    assert "devtools" in last["content"]


def test_build_messages_selection_explain_includes_selection():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="selection_explain",
        title="T", tag="t", summary="s", selection="useEffect(() => {}, [])",
        prior=[],
    )
    last = msgs[-1]
    assert "code from" in last["content"]
    assert "useEffect" in last["content"]


def test_build_messages_selection_qa_includes_selection():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="selection_qa",
        title="T", tag=None, summary=None, selection="some prose",
        prior=[],
    )
    last = msgs[-1]
    assert "highlighted from" in last["content"]
    assert "some prose" in last["content"]


def test_build_messages_truncates_selection_to_max_context_chars():
    cfg = PetConfig()
    cfg.max_context_chars = 50
    long_sel = "x" * 1000
    msgs = build_messages(
        cfg, mode="selection_explain",
        title="T", tag="t", summary="s", selection=long_sel,
        prior=[],
    )
    last_content = msgs[-1]["content"]
    assert "x" * 50 in last_content
    assert "x" * 51 not in last_content


def test_build_messages_prepends_prior_unchanged():
    cfg = PetConfig()
    prior = [
        {"role": "user", "content": "prev_u"},
        {"role": "assistant", "content": "prev_a"},
    ]
    msgs = build_messages(
        cfg, mode="greet",
        title=None, tag=None, summary=None, selection=None,
        prior=prior,
    )
    assert msgs[0] == {"role": "user", "content": "prev_u"}
    assert msgs[1] == {"role": "assistant", "content": "prev_a"}
    assert msgs[2]["role"] == "user"
    assert "tapped on you" in msgs[2]["content"]


def test_build_messages_returns_only_role_content_pairs():
    """Ensure prior turns are stripped of any extra metadata before
    handing to LLM (the gateway/adapter layer expects clean messages)."""
    cfg = PetConfig()
    prior = [
        {"role": "user", "content": "u", "mode": "greet", "post_id": "x"},
        {"role": "assistant", "content": "a", "mode": "greet", "post_id": "x"},
    ]
    msgs = build_messages(
        cfg, mode="greet",
        title=None, tag=None, summary=None, selection=None,
        prior=prior,
    )
    for m in msgs:
        assert set(m.keys()) == {"role", "content"}
