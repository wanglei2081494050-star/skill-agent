"""Agent tools: ``load_skill`` and ``read_skill_file``.

Both tools are deliberately conservative about paths: a skill can only read files
inside its own directory, symlinks are resolved before the containment check, and
absolute paths / drive letters / ``..`` segments are rejected up front. A
traversal attempt returns an error object instead of a traceback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import MAX_ATTACHED_FILE_BYTES
from .skills import Skill, Snapshot


class ToolError(Exception):
    """A tool failed in a way the agent can report to the user."""


def _reject_reason(raw_path: str) -> str | None:
    if not raw_path or not raw_path.strip():
        return "path must not be empty"
    if "\x00" in raw_path:
        return "path must not contain NUL bytes"
    p = raw_path.replace("\\", "/").strip()
    if p.startswith("/"):
        return "absolute paths are not allowed"
    if len(p) > 1 and p[1] == ":":
        return "drive-qualified paths are not allowed"
    if any(part == ".." for part in Path(p).parts):
        return "'..' segments are not allowed"
    return None


def resolve_skill_file(skill: Skill, raw_path: str) -> Path:
    """Return the resolved path of an attached file, or raise ``ToolError``."""
    reason = _reject_reason(raw_path)
    if reason:
        raise ToolError(f"rejected path {raw_path!r}: {reason}")

    base = skill.dir.resolve()
    candidate = (base / raw_path.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ToolError(
            f"rejected path {raw_path!r}: resolves outside skill directory {base.name!r}"
        ) from None
    if candidate.is_dir():
        raise ToolError(f"rejected path {raw_path!r}: is a directory")
    if not candidate.is_file():
        raise ToolError(f"attached file not found: {raw_path}")
    return candidate


def read_skill_file(snapshot: Snapshot, name: str, raw_path: str) -> dict[str, Any]:
    skill = snapshot.get(name)
    if skill is None:
        raise ToolError(f"unknown skill: {name}")
    path = resolve_skill_file(skill, raw_path)
    size = path.stat().st_size
    if size > MAX_ATTACHED_FILE_BYTES:
        raise ToolError(
            f"attached file {raw_path!r} is {size} bytes, over the {MAX_ATTACHED_FILE_BYTES} byte limit"
        )
    data = path.read_bytes()
    if b"\x00" in data:
        raise ToolError(f"attached file {raw_path!r} is binary; only text files can be read")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"attached file {raw_path!r} is not valid UTF-8") from None
    return {
        "skill": name,
        "path": raw_path,
        "bytes": size,
        "text": text,
    }


def dependency_chain(snapshot: Snapshot, name: str) -> dict[str, Any]:
    """Resolve the dependency closure of ``name`` in load order.

    Returns ``{"order": [...], "cycle": [...], "missing": [...]}``. Missing
    dependencies are reported but do not abort the load; a cycle aborts it.
    """
    by_name = snapshot.by_name()
    order: list[str] = []
    cycle: list[str] = []
    missing: list[str] = []
    state: dict[str, str] = {}
    stack: list[str] = []

    def visit(current: str) -> bool:
        state[current] = "visiting"
        stack.append(current)
        skill = by_name.get(current)
        for dep in (skill.depends_on if skill else []):
            if dep not in by_name:
                missing.append(f"{current} -> {dep}")
                continue
            dep_state = state.get(dep)
            if dep_state == "visiting":
                start = stack.index(dep)
                cycle.extend(stack[start:] + [dep])
                return False
            if dep_state is None and not visit(dep):
                return False
        stack.pop()
        state[current] = "done"
        order.append(current)
        return True

    visit(name)
    if cycle:
        return {"order": [], "cycle": cycle, "missing": missing}
    return {"order": order, "cycle": [], "missing": missing}


def load_skill(snapshot: Snapshot, name: str) -> dict[str, Any]:
    skill = snapshot.get(name)
    if skill is None:
        known = ", ".join(sorted(snapshot.by_name())) or "none"
        raise ToolError(f"unknown skill: {name} (available: {known})")

    chain = dependency_chain(snapshot, name)
    if chain["cycle"]:
        raise ToolError(
            "circular skill dependency: " + " -> ".join(chain["cycle"])
        )

    by_name = snapshot.by_name()
    bodies = []
    for dep_name in chain["order"]:
        dep = by_name[dep_name]
        bodies.append(
            {
                "name": dep.name,
                "source": dep.source_id,
                "body": dep.body,
                "attached": dep.attached,
                "dependsOn": dep.depends_on,
            }
        )
    return {
        "name": skill.name,
        "source": skill.source_id,
        "body": skill.body,
        "attached": skill.attached,
        "dependsOn": skill.depends_on,
        "order": chain["order"],
        "missingDependencies": chain["missing"],
        "dependencies": bodies[1:],
        "bodyTokens": skill.body_tokens,
    }
