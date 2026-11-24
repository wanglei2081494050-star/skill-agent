"""Skill discovery: scan source directories, parse frontmatter, resolve conflicts.

Design notes
------------
* A broken skill never aborts the scan: it lands in ``skipped`` with reasons.
* Same name in two sources: the source with the higher ``priority`` wins. The
  shadowed copy stays visible in the UI (with its source) so the reviewer can
  see that the conflict happened, but it is never injected nor loadable.
* Hot reload is implemented as a *fingerprint* over every SKILL.md and attached
  file (path, mtime_ns, size). Every request asks for the current snapshot; if
  the fingerprint changed the registry rescans, so an edited skill is used on
  the very next turn without a restart.
"""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_SOURCES,
    MAX_ATTACHED_FILES_PER_SKILL,
    REPO_ROOT,
    SKILL_ROOT,
)
from .frontmatter import parse_frontmatter
from .tokens import estimate_tokens

SKILL_FILE = "SKILL.md"


def rel_to_repo(path: Path) -> str:
    """Repo-relative POSIX path, or the absolute path for out-of-repo sources."""
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")
IGNORED_DIRS = {"__pycache__", ".git", "node_modules", ".venv"}


@dataclass
class Skill:
    name: str
    description: str
    source_id: str
    source_label: str
    priority: int
    dir: Path
    body: str
    meta: dict[str, Any]
    attached: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    line_tokens: int = 0
    body_tokens: int = 0
    mtime_ns: int = 0
    shadowed: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source_id,
            "sourceLabel": self.source_label,
            "priority": self.priority,
            "path": rel_to_repo(self.dir),
            "attached": self.attached,
            "dependsOn": self.depends_on,
            "lineTokens": self.line_tokens,
            "bodyTokens": self.body_tokens,
            "shadowed": self.shadowed,
            "mtimeNs": self.mtime_ns,
        }


@dataclass
class Skipped:
    path: str
    source_id: str
    reasons: list[str]

    def summary(self) -> dict[str, Any]:
        return {"path": self.path, "source": self.source_id, "reasons": self.reasons}


@dataclass
class Snapshot:
    skills: list[Skill]
    skipped: list[Skipped]
    conflicts: list[dict[str, Any]]
    fingerprint: str
    scanned_at: str
    source_stats: list[dict[str, Any]]

    def by_name(self) -> dict[str, Skill]:
        return {s.name: s for s in self.skills}

    def get(self, name: str) -> Skill | None:
        return self.by_name().get(name)

    def summary(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "scannedAt": self.scanned_at,
            "sources": self.source_stats,
            "skills": [s.summary() for s in self.skills],
            "skipped": [s.summary() for s in self.skipped],
            "conflicts": self.conflicts,
        }


def _iter_skill_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.is_dir() and entry.name not in IGNORED_DIRS and (entry / SKILL_FILE).is_file():
            out.append(entry)
    return out


def _collect_attached(skill_dir: Path) -> list[str]:
    files: list[str] = []
    for root, dirs, names in os.walk(skill_dir):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        for name in sorted(names):
            full = Path(root) / name
            rel = full.relative_to(skill_dir)
            if str(rel).replace("\\", "/") == SKILL_FILE:
                continue
            files.append(str(rel).replace("\\", "/"))
            if len(files) >= MAX_ATTACHED_FILES_PER_SKILL:
                return files
    return files


def _fingerprint(sources: list[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for src in sources:
        root = SKILL_ROOT.parent / src["path"] if not Path(src["path"]).is_absolute() else Path(src["path"])
        if not root.is_dir():
            h.update(f"{src['id']}:missing\n".encode())
            continue
        for path in sorted(root.rglob("*")):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            rel = path.relative_to(root)
            h.update(f"{src['id']}/{rel}:{st.st_mtime_ns}:{st.st_size}\n".encode())
    return h.hexdigest()[:16]


class SkillRegistry:
    """Holds the latest snapshot and rescans when files change."""

    def __init__(self, sources: list[dict[str, Any]] | None = None) -> None:
        self.sources = sources if sources is not None else list(DEFAULT_SOURCES)
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._fingerprint: str = ""
        self.rescan_count = 0

    # -- public API -----------------------------------------------------
    def snapshot(self) -> Snapshot:
        """Return a snapshot, rescanned if any skill file changed on disk."""
        current = _fingerprint(self.sources)
        with self._lock:
            if self._snapshot is not None and current == self._fingerprint:
                return self._snapshot
            snap = self._scan(current)
            self._snapshot = snap
            self._fingerprint = current
            self.rescan_count += 1
            return snap

    def rescan(self) -> Snapshot:
        with self._lock:
            self._snapshot = None
            self._fingerprint = ""
        return self.snapshot()

    def _source_root(self, src: dict[str, Any]) -> Path:
        p = Path(src["path"])
        return p if p.is_absolute() else REPO_ROOT / p

    # -- internals ------------------------------------------------------
    def _scan(self, fingerprint: str) -> Snapshot:
        from datetime import datetime, timezone

        found: list[Skill] = []
        skipped: list[Skipped] = []
        stats: list[dict[str, Any]] = []

        for src in self.sources:
            root = self._source_root(src)
            dirs = _iter_skill_dirs(root)
            ok_count = 0
            for skill_dir in dirs:
                skill_path = skill_dir / SKILL_FILE
                try:
                    text = skill_path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as exc:
                    skipped.append(
                        Skipped(
                            path=rel_to_repo(skill_path),
                            source_id=src["id"],
                            reasons=[f"unreadable SKILL.md: {exc.__class__.__name__}: {exc}"],
                        )
                    )
                    continue

                parsed = parse_frontmatter(text)
                if not parsed.ok:
                    skipped.append(
                        Skipped(
                            path=rel_to_repo(skill_path),
                            source_id=src["id"],
                            reasons=parsed.errors,
                        )
                    )
                    continue

                name = str(parsed.meta["name"]).strip()
                description = " ".join(str(parsed.meta["description"]).split())
                depends = parsed.meta.get("depends-on") or []
                if isinstance(depends, str):
                    depends = [depends]
                depends = [str(d) for d in depends]

                mtime = skill_path.stat().st_mtime_ns
                skill = Skill(
                    name=name,
                    description=description,
                    source_id=src["id"],
                    source_label=src["label"],
                    priority=int(src["priority"]),
                    dir=skill_dir,
                    body=parsed.body,
                    meta=parsed.meta,
                    attached=_collect_attached(skill_dir),
                    depends_on=depends,
                    line_tokens=estimate_tokens(f"{name}: {description}"),
                    body_tokens=estimate_tokens(parsed.body),
                    mtime_ns=mtime,
                )
                found.append(skill)
                ok_count += 1

            stats.append(
                {
                    "id": src["id"],
                    "label": src["label"],
                    "path": src["path"],
                    "priority": src["priority"],
                    "dirs": len(dirs),
                    "loaded": ok_count,
                }
            )

        found.sort(key=lambda s: (-s.priority, s.name))
        winners: dict[str, Skill] = {}
        conflicts: list[dict[str, Any]] = []
        for skill in found:
            held = winners.get(skill.name)
            if held is None:
                winners[skill.name] = skill
                continue
            held.shadowed.append(
                {
                    "source": skill.source_id,
                    "path": rel_to_repo(skill.dir),
                }
            )
            conflicts.append(
                {
                    "name": skill.name,
                    "winner": {"source": held.source_id, "priority": held.priority},
                    "shadowed": [
                        {"source": skill.source_id, "priority": skill.priority}
                    ],
                    "rule": "highest source priority wins; personal > team > builtin",
                }
            )

        skills = sorted(winners.values(), key=lambda s: (-s.priority, s.name))
        return Snapshot(
            skills=skills,
            skipped=skipped,
            conflicts=conflicts,
            fingerprint=fingerprint,
            scanned_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            source_stats=stats,
        )
