"""Markdown -> structured body_json pipeline.

The frontend renders 8 block types and 4 inline types. We use mistune's AST
output ('renderer=None') and walk it; any unsupported AST node is a hard error.
"""
from typing import Any

import mistune

Block = dict[str, Any]
Inline = dict[str, Any]


class MarkdownError(ValueError):
    """Raised on disallowed GFM features or malformed input."""


_DISALLOWED = {
    "task_list_item": "task lists are not supported",
    "footnote_ref": "footnotes are not supported",
    "footnote_item": "footnotes are not supported",
    "strikethrough": "strikethrough is not supported",
    "block_html": "inline/block HTML is not supported",
    "inline_html": "inline/block HTML is not supported",
}


def _walk_inlines(children: list[dict]) -> list[Inline]:
    out: list[Inline] = []
    for c in children:
        t = c["type"]
        if t in _DISALLOWED:
            raise MarkdownError(_DISALLOWED[t])
        if t == "text":
            out.append({"kind": "text", "s": c["raw"]})
        elif t == "codespan":
            out.append({"kind": "code", "s": c["raw"]})
        elif t == "strong":
            out.append({"kind": "b", "children": _walk_inlines(c.get("children", []))})
        elif t == "emphasis":
            out.append({"kind": "i", "children": _walk_inlines(c.get("children", []))})
        elif t == "link":
            out.append({
                "kind": "a", "href": c["attrs"]["url"],
                "children": _walk_inlines(c.get("children", [])),
            })
        elif t == "softbreak" or t == "linebreak":
            out.append({"kind": "text", "s": "\n"})
        else:
            raise MarkdownError(f"unsupported inline node: {t}")
    return out


def _flatten_text(inlines: list[Inline]) -> str:
    parts: list[str] = []
    for i in inlines:
        if i["kind"] == "text":
            parts.append(i["s"])
        elif i["kind"] == "code":
            parts.append(i["s"])
        elif i["kind"] in ("b", "i"):
            parts.append(_flatten_text(i["children"]))
        elif i["kind"] == "a":
            parts.append(_flatten_text(i["children"]))
    return "".join(parts)


def _image_alt(img_node: dict) -> str:
    """Extract the alt text from an image node.

    Mistune stores the alt text as the children of the image node (a list of
    inline text nodes), not as an explicit ``alt`` attribute.
    """
    children = img_node.get("children", [])
    parts: list[str] = []
    for c in children:
        if c.get("type") == "text":
            parts.append(c.get("raw", ""))
    return "".join(parts)


_HEADING_TS = {1: "h1", 2: "h2", 3: "h3", 4: "h4"}


def _walk_blocks(nodes: list[dict]) -> list[Block]:
    out: list[Block] = []
    for node in nodes:
        t = node["type"]
        if t in _DISALLOWED:
            raise MarkdownError(_DISALLOWED[t])

        # Mistune emits "blank_line" tokens between blocks; ignore them.
        if t == "blank_line":
            continue

        if t == "heading":
            level = node["attrs"]["level"]
            if level not in _HEADING_TS:
                # Real fixtures occasionally use h5/h6; degrade silently to h4
                # rather than rejecting them. (Decision: degrade > reject so
                # legacy posts don't break the pipeline. -- Batch C, Task 16.)
                level = 4
            inline = _walk_inlines(node.get("children", []))
            out.append({"t": _HEADING_TS[level], "c": _flatten_text(inline), "inline": inline})

        elif t == "paragraph":
            children = node.get("children", [])
            # An image-only paragraph degrades to {t:"image", ...}
            if len(children) == 1 and children[0]["type"] == "image":
                img = children[0]
                out.append({
                    "t": "image",
                    "src": img["attrs"]["url"],
                    "alt": _image_alt(img),
                })
            else:
                inline = _walk_inlines(children)
                out.append({"t": "p", "c": _flatten_text(inline), "inline": inline})

        elif t == "block_code":
            block: Block = {"t": "code", "c": node["raw"].rstrip("\n")}
            info = node.get("attrs", {}).get("info")
            if info:
                block["lang"] = info.split()[0]
            out.append(block)

        elif t == "thematic_break":
            out.append({"t": "hr"})

        elif t == "block_quote":
            # Flatten children into a single paragraph-like block.
            inner = _walk_blocks(node.get("children", []))
            text = " ".join(b.get("c", "") for b in inner if b.get("c"))
            inlines: list[Inline] = []
            for b in inner:
                inlines.extend(b.get("inline", []))
            out.append({"t": "quote", "c": text, "inline": inlines})

        elif t == "list":
            ordered = node["attrs"]["ordered"]
            items: list[dict] = []
            for li in node.get("children", []):
                # li.type == 'list_item'; first child is block_text or paragraph
                paras = li.get("children", [])
                if not paras:
                    continue
                para = paras[0]
                if para["type"] not in ("block_text", "paragraph"):
                    raise MarkdownError("nested lists are not supported")
                inline = _walk_inlines(para.get("children", []))
                items.append({"c": _flatten_text(inline), "inline": inline})
            out.append({"t": "ol" if ordered else "ul", "items": items})

        elif t == "table":
            children = node.get("children", [])
            head = children[0]  # table_head
            body = children[1] if len(children) > 1 else None
            # In mistune's table plugin, table_head's direct children are the
            # header cells (not a row wrapper).
            header_cells = head.get("children", [])
            header: list[str] = []
            align: list[str] = []
            for cell in header_cells:
                header.append(_flatten_text(_walk_inlines(cell.get("children", []))))
                a = cell.get("attrs", {}).get("align")
                align.append(a if a in ("left", "center", "right") else "left")
            rows: list[list[str]] = []
            if body is not None:
                for row in body.get("children", []):
                    rows.append([
                        _flatten_text(_walk_inlines(c.get("children", [])))
                        for c in row.get("children", [])
                    ])
            out.append({"t": "table", "header": header, "align": align, "rows": rows})

        else:
            raise MarkdownError(f"unsupported block: {t}")

    return out


_md = mistune.create_markdown(
    renderer=None,
    plugins=["table", "url"],
)


_TASK_PREFIXES = ("- [ ]", "- [x]", "- [X]", "* [ ]", "* [x]", "* [X]",
                  "+ [ ]", "+ [x]", "+ [X]")


def _has_unrendered_task_list(md: str) -> bool:
    # Currently we always degrade. Reserved for future strict-mode use.
    return False


def _strip_task_list_markers(md: str) -> str:
    """Rewrite GFM task-list items as plain bullet items.

    Converts ``- [ ] foo`` / ``- [x] foo`` to ``- foo`` so mistune's default
    list parser treats them as regular bullets. The semantic checkbox is
    dropped; this is a one-way degrade. Real legacy posts (Task 16 fixtures)
    use task-list syntax as decoration only, so this is acceptable.
    """
    lines = md.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        for prefix in _TASK_PREFIXES:
            if stripped.startswith(prefix):
                # `- [ ] foo` -> `- foo`
                bullet = prefix[0]
                rest = stripped[len(prefix):].lstrip()
                line = f"{indent}{bullet} {rest}"
                break
        out.append(line)
    return "".join(out)


def parse_markdown(md: str) -> list[Block]:
    """Parse a Markdown body into a list of structured blocks.

    Returns: list of Block dicts.
    Raises:  MarkdownError on disallowed features or malformed AST.
    """
    if "<" in md and (">" in md):
        # Quick reject for obvious HTML before mistune normalizes anything.
        # (mistune by default escapes; we still want explicit 422.)
        for token in ("<div", "<span", "<p ", "<p>", "<br", "<img", "<script"):
            if token in md:
                raise MarkdownError("inline/block HTML is not supported")
    if "~~" in md:
        raise MarkdownError("strikethrough is not supported")
    if _has_unrendered_task_list(md):
        raise MarkdownError("task lists are not supported")
    # Strip GFM task-list markers so they degrade to plain list items. Real
    # legacy posts (e.g. PageHelper troubleshooting checklists) use these and
    # we don't want to reject them. -- Batch C, Task 16.
    md = _strip_task_list_markers(md)
    ast = _md(md)
    return _walk_blocks(ast)


import math
import re

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_CJK_RE = re.compile(r"[一-鿿]")


def _plaintext(blocks: list[Block]) -> str:
    parts: list[str] = []
    for b in blocks:
        if "c" in b:
            parts.append(b["c"])
        elif b.get("t") in ("ul", "ol"):
            for it in b["items"]:
                parts.append(it["c"])
        elif b.get("t") == "table":
            parts.extend(b["header"])
            for row in b["rows"]:
                parts.extend(row)
    return " ".join(parts)


def compute_derived(blocks: list[Block]) -> dict:
    text = _plaintext(blocks)
    words = len(_WORD_RE.findall(text))
    cjk = len(_CJK_RE.findall(text))
    word_count = words + cjk
    read_min = max(1, math.ceil(word_count / 240))
    first_p = next((b for b in blocks if b.get("t") == "p"), None)
    summary = (
        (first_p["c"][:140] + "…") if first_p and len(first_p["c"]) > 140
        else (first_p["c"] if first_p else "")
    )
    return {"word_count": word_count, "read": f"{read_min} min", "summary": summary}
