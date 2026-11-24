#!/usr/bin/env python3
"""Normalize a git commit range into JSON lines for release notes.

Usage: python collect_commits.py "v1.2.0..HEAD"
Requires git on PATH; prints one JSON object per commit.
"""

from __future__ import annotations

import json
import subprocess
import sys

SEP = "\x1f"


def main(rev_range: str) -> int:
    out = subprocess.run(
        ["git", "log", f"--pretty=format:%h{SEP}%s{SEP}%an{SEP}%cd", "--date=short", rev_range],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        print(out.stderr.strip() or "git log failed", file=sys.stderr)
        return out.returncode
    for line in out.stdout.splitlines():
        parts = line.split(SEP)
        if len(parts) != 4:
            continue
        sha, subject, author, date = parts
        print(json.dumps({"sha": sha, "subject": subject, "author": author, "date": date}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: collect_commits.py FROM..TO")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
