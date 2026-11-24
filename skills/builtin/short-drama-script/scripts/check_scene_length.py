#!/usr/bin/env python3
"""Check a short-drama draft for per-scene length and hook placement.

Usage: python check_scene_length.py draft.md
Exit code 1 when at least one violation is found.
"""

from __future__ import annotations

import re
import sys

SCENE_RE = re.compile(r"^(INT\.|EXT\.)\s", re.MULTILINE)
MAX_CHARS_PER_SCENE = 260
MAX_FIRST_LINE_CHARS = 20


def main(path: str) -> int:
    text = open(path, encoding="utf-8").read()
    blocks = [b.strip() for b in SCENE_RE.split(text) if b and b.strip()]
    scenes = [s for s in text.splitlines() if SCENE_RE.match(s)]
    violations: list[str] = []

    if not scenes:
        violations.append("no scene heading found (expected INT./EXT. lines)")
    for idx, line in enumerate(text.splitlines(), start=1):
        if len(line) > MAX_CHARS_PER_SCENE:
            violations.append(f"line {idx}: {len(line)} chars in a single speech block")
    first_dialogue = next(
        (l for l in text.splitlines() if l.strip() and not SCENE_RE.match(l)), ""
    )
    if len(first_dialogue) > MAX_FIRST_LINE_CHARS:
        violations.append(
            f"opening line is {len(first_dialogue)} chars; hook must stay <= {MAX_FIRST_LINE_CHARS}"
        )
    if "反转" not in text and "reversal" not in text.lower():
        violations.append("no reversal marker found between the obstacle and the cliff hanger")

    print(f"scenes={len(scenes)} blocks={len(blocks)} violations={len(violations)}")
    for v in violations:
        print(f"- {v}")
    return 1 if violations else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: check_scene_length.py draft.md")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
