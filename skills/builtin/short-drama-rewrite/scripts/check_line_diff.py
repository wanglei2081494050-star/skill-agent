#!/usr/bin/env python3
"""Compare an original script with a rewrite.

Usage: python check_line_diff.py old.md new.md
Reports preserved scene count and the changed-line ratio.
"""

from __future__ import annotations

import difflib
import sys


def lines(path: str) -> list[str]:
    return [l.strip() for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]


def main(old_path: str, new_path: str) -> int:
    old, new = lines(old_path), lines(new_path)
    if not old:
        print("old script is empty")
        return 2
    matcher = difflib.SequenceMatcher(a=old, b=new)
    changed = sum(
        max(i2 - i1, j2 - j1)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    )
    ratio = changed / len(old)
    old_scenes = [l for l in old if l.startswith(("INT.", "EXT."))]
    new_scenes = [l for l in new if l.startswith(("INT.", "EXT."))]
    print(f"old_lines={len(old)} new_lines={len(new)} changed={changed} ratio={ratio:.2%}")
    print(f"scenes old={len(old_scenes)} new={len(new_scenes)}")
    problems = []
    if len(new_scenes) < len(old_scenes):
        problems.append("a scene was dropped: rewriting must not delete scenes")
    if abs(len(new) - len(old)) / len(old) > 0.10:
        problems.append("length moved more than 10%")
    for p in problems:
        print(f"- {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: check_line_diff.py old.md new.md")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
