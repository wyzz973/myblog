import json

import pytest

from myblog import output


def test_emit_record_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    output.set_format(json_mode=True)
    output.emit_record({"id": "p1", "title": "hi"})
    captured = capsys.readouterr().out.splitlines()
    assert json.loads(captured[0]) == {"id": "p1", "title": "hi"}


def test_emit_table_human_mode(capsys: pytest.CaptureFixture[str]) -> None:
    output.set_format(json_mode=False)
    output.emit_table(
        title="posts",
        columns=["id", "title", "status"],
        rows=[{"id": "p1", "title": "hi", "status": "published"}],
    )
    text = capsys.readouterr().out
    assert "p1" in text
    assert "hi" in text
    assert "published" in text


def test_emit_table_json_mode_yields_one_line_per_row(capsys: pytest.CaptureFixture[str]) -> None:
    output.set_format(json_mode=True)
    output.emit_table(
        title="posts",
        columns=["id"],
        rows=[{"id": "a"}, {"id": "b"}],
    )
    lines = capsys.readouterr().out.splitlines()
    assert [json.loads(l) for l in lines] == [{"id": "a"}, {"id": "b"}]


def test_emit_error_json_mode(capsys: pytest.CaptureFixture[str]) -> None:
    output.set_format(json_mode=True)
    output.emit_error("oops", code=42)
    line = capsys.readouterr().err
    assert json.loads(line) == {"error": "oops", "code": 42}
