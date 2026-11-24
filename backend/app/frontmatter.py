"""Minimal YAML-subset frontmatter parser used for SKILL.md files.

Only the shapes a SKILL.md frontmatter actually needs are supported:

    ---
    name: short-drama-script
    description: Write a vertical short-drama episode script.
    metadata:
      version: 1.0.0
      tags: [drama, script]
    allowed-tools:
      - read_skill_file
    ---

Anything outside that subset is reported as a parse error instead of being
silently ignored, because a silently mis-parsed description poisons routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_KEY_RE = re.compile(r"^([A-Za-z0-9_.-]+):(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")


@dataclass
class FrontmatterResult:
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _strip_comment(value: str) -> str:
    """Drop a trailing ``# comment`` that is not inside quotes."""
    out = []
    quote = ""
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = ""
            out.append(ch)
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or value[i - 1].isspace()):
            break
        out.append(ch)
    return "".join(out).strip()


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
        return inner.replace("''", "'")
    return value


def _scalar(raw: str) -> Any:
    value = _unquote(_strip_comment(raw).strip())
    if value in ("", "~", "null"):
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _inline_list(raw: str) -> list[Any]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    items, buf, quote = [], "", ""
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf += ch
            continue
        if ch == ",":
            items.append(_scalar(buf))
            buf = ""
            continue
        buf += ch
    if buf.strip():
        items.append(_scalar(buf))
    return items


def parse_frontmatter(text: str) -> FrontmatterResult:
    """Parse frontmatter + body, collecting human-readable error strings."""
    result = FrontmatterResult()
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---"):
        result.errors.append("missing frontmatter: file must start with '---'")
        result.body = normalized
        return result

    lines = normalized.split("\n")
    if lines[0].strip() != "---":
        result.errors.append("invalid frontmatter opener: first line must be exactly '---'")
        result.body = normalized
        return result

    closing = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing = idx
            break
    if closing is None:
        result.errors.append("unterminated frontmatter: no closing '---'")
        result.body = normalized
        return result

    fm_lines = lines[1:closing]
    result.body = "\n".join(lines[closing + 1 :]).strip("\n")

    meta: dict[str, Any] = {}
    current_key: str | None = None
    current_indent = 0
    for offset, raw in enumerate(fm_lines, start=2):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            result.errors.append(f"line {offset}: tab indentation is not allowed in frontmatter")
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()

        item_match = _LIST_ITEM_RE.match(raw)
        if item_match:
            if current_key is None:
                result.errors.append(f"line {offset}: list item without a parent key")
                continue
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(_scalar(item_match.group(1)))
            continue

        key_match = _KEY_RE.match(stripped)
        if not key_match:
            result.errors.append(f"line {offset}: expected 'key: value', got {stripped!r}")
            continue

        key, raw_value = key_match.group(1), key_match.group(2).strip()
        if key in meta and indent == 0:
            result.errors.append(f"line {offset}: duplicate key {key!r}")
            continue

        if indent == 0:
            current_key, current_indent = key, 0
            if raw_value.startswith("[") and raw_value.endswith("]"):
                meta[key] = _inline_list(raw_value)
            elif raw_value in ("|", ">", "|-", ">-"):
                meta[key] = ""
            else:
                meta[key] = _scalar(raw_value)
        else:
            if current_key is None:
                result.errors.append(f"line {offset}: indented key without a parent")
                continue
            parent = meta.get(current_key)
            if parent is None:
                # `metadata:` followed by an indented block: start the mapping.
                meta[current_key] = {}
            elif not isinstance(parent, dict):
                result.errors.append(
                    f"line {offset}: nested key under {current_key!r}, which is not a mapping"
                )
                continue
            container = meta[current_key]
            if raw_value.startswith("[") and raw_value.endswith("]"):
                container[key] = _inline_list(raw_value)
            else:
                container[key] = _scalar(raw_value)

    if "name" not in meta:
        result.errors.append("missing required field: name")
    elif not isinstance(meta.get("name"), str) or not str(meta.get("name")).strip():
        result.errors.append("field 'name' must be a non-empty string")
    elif not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(meta["name"]).strip()):
        result.errors.append(
            "field 'name' must be kebab-case (lowercase letters, digits, dashes, max 64 chars)"
        )

    if "description" not in meta:
        result.errors.append("missing required field: description")
    elif not isinstance(meta.get("description"), str) or not str(meta.get("description")).strip():
        result.errors.append("field 'description' must be a non-empty string")
    elif len(str(meta["description"]).strip()) > 1024:
        result.errors.append("field 'description' must be at most 1024 characters")

    result.meta = meta
    return result
