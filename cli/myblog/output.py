"""Human (rich) + ndjson dual output mode.

Set the mode once via set_format(json_mode=...), then call emit_*.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.table import Table

_state = {"json": False}
_stdout = Console()
_stderr = Console(stderr=True)


def set_format(*, json_mode: bool) -> None:
    _state["json"] = bool(json_mode)


def is_json() -> bool:
    return _state["json"]


def emit_record(obj: dict) -> None:
    if _state["json"]:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return
    if not obj:
        _stdout.print("[dim]<empty>[/]")
        return
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(overflow="fold")
    for k, v in obj.items():
        table.add_row(str(k), _fmt(v))
    _stdout.print(table)


def emit_table(*, title: str, columns: list[str], rows: list[dict]) -> None:
    if _state["json"]:
        for r in rows:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return
    table = Table(title=title, show_lines=False)
    for c in columns:
        table.add_column(c)
    for r in rows:
        table.add_row(*[_fmt(r.get(c)) for c in columns])
    _stdout.print(table)


def emit_message(msg: str) -> None:
    if _state["json"]:
        sys.stdout.write(json.dumps({"message": msg}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return
    _stdout.print(msg)


def emit_error(msg: str, *, code: int = 1) -> None:
    if _state["json"]:
        sys.stderr.write(json.dumps({"error": msg, "code": code}, ensure_ascii=False) + "\n")
        sys.stderr.flush()
        return
    _stderr.print(f"[red]error:[/] {msg}")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)
