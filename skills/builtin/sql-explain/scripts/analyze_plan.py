#!/usr/bin/env python3
"""Scan an EXPLAIN output for common red flags.

Usage: python analyze_plan.py plan.txt
"""

from __future__ import annotations

import re
import sys

RED_FLAGS = {
    "sequential scan": re.compile(r"Seq Scan|type:\s*ALL", re.I),
    "nested loop on large input": re.compile(r"Nested Loop.*rows=\d{5,}", re.I),
    "external merge sort": re.compile(r"external merge", re.I),
    "implicit cast": re.compile(r"::(?:date|text|timestamp)|CAST\(", re.I),
    "costly filter remove": re.compile(r"Rows Removed by Filter:\s*\d{4,}", re.I),
}


def main(path: str) -> int:
    text = open(path, encoding="utf-8").read()
    findings = []
    for name, pattern in RED_FLAGS.items():
        hits = len(pattern.findall(text))
        if hits:
            findings.append((name, hits))
    est = [int(m) for m in re.findall(r"rows=(\d+)", text)]
    print(f"bytes={len(text)} findings={len(findings)}")
    for name, hits in findings:
        print(f"- {name}: {hits} occurrence(s)")
    if len(est) >= 2:
        lo, hi = min(est), max(est)
        if lo and hi / lo > 10:
            print(f"- row estimate spread {lo}..{hi} (>10x): inspect statistics")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: analyze_plan.py plan.txt")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
