import pytest

from app.services.markdown_pipeline import parse_markdown, MarkdownError


def test_heading_paragraph():
    md = "## Hello\n\nWorld."
    blocks = parse_markdown(md)
    assert blocks == [
        {"t": "h2", "c": "Hello", "inline": [{"kind": "text", "s": "Hello"}]},
        {"t": "p", "c": "World.", "inline": [{"kind": "text", "s": "World."}]},
    ]


def test_h1_h3_h4():
    md = "# A\n\n### B\n\n#### C"
    blocks = parse_markdown(md)
    assert [b["t"] for b in blocks] == ["h1", "h3", "h4"]


def test_code_block_with_lang():
    md = "```bash\necho hi\n```"
    blocks = parse_markdown(md)
    assert blocks == [{"t": "code", "c": "echo hi", "lang": "bash"}]


def test_code_block_no_lang():
    md = "```\nplain\n```"
    blocks = parse_markdown(md)
    assert blocks == [{"t": "code", "c": "plain"}]


def test_unordered_list():
    md = "- one\n- two"
    blocks = parse_markdown(md)
    assert blocks == [
        {
            "t": "ul",
            "items": [
                {"c": "one", "inline": [{"kind": "text", "s": "one"}]},
                {"c": "two", "inline": [{"kind": "text", "s": "two"}]},
            ],
        }
    ]


def test_ordered_list():
    md = "1. a\n2. b"
    blocks = parse_markdown(md)
    assert blocks[0]["t"] == "ol"
    assert len(blocks[0]["items"]) == 2


def test_blockquote():
    md = "> quoted line"
    blocks = parse_markdown(md)
    assert blocks == [
        {"t": "quote", "c": "quoted line", "inline": [{"kind": "text", "s": "quoted line"}]}
    ]


def test_hr():
    md = "before\n\n---\n\nafter"
    blocks = parse_markdown(md)
    assert blocks[1] == {"t": "hr"}


def test_table_with_align():
    md = (
        "| h1 | h2 |\n"
        "|:---|---:|\n"
        "| a  | b  |\n"
        "| c  | d  |"
    )
    blocks = parse_markdown(md)
    assert blocks == [
        {
            "t": "table",
            "header": ["h1", "h2"],
            "align": ["left", "right"],
            "rows": [["a", "b"], ["c", "d"]],
        }
    ]


def test_image_block():
    md = "![alt](https://x.png)"
    blocks = parse_markdown(md)
    assert blocks == [{"t": "image", "src": "https://x.png", "alt": "alt"}]


def test_task_list_degrades_to_plain_list_item():
    # GFM task-list checkboxes are stripped to plain bullets so legacy posts
    # that use ``- [ ]`` as a decorative checklist still parse. -- Task 16.
    md = "- [ ] todo"
    blocks = parse_markdown(md)
    assert blocks == [
        {
            "t": "ul",
            "items": [{"c": "todo", "inline": [{"kind": "text", "s": "todo"}]}],
        }
    ]


def test_disallowed_strikethrough_rejected():
    md = "~~struck~~"
    with pytest.raises(MarkdownError):
        parse_markdown(md)


def test_disallowed_html_rejected():
    md = "<div>nope</div>"
    with pytest.raises(MarkdownError):
        parse_markdown(md)


from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "real_md"


@pytest.mark.parametrize("md_path", sorted(FIXTURES.glob("*.md")), ids=lambda p: p.name)
def test_real_fixture_parses_without_error(md_path):
    text = md_path.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    assert isinstance(blocks, list)
    assert len(blocks) > 0


@pytest.mark.parametrize("md_path", sorted(FIXTURES.glob("*.md")), ids=lambda p: p.name)
def test_real_fixture_block_types_known(md_path):
    text = md_path.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    allowed = {"h1", "h2", "h3", "h4", "p", "code", "ul", "ol", "quote", "hr", "table", "image"}
    for b in blocks:
        assert b["t"] in allowed, f"unknown block type {b['t']} in {md_path.name}"
