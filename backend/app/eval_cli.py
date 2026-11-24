"""CLI entry point for the routing evaluation (same code path as the UI button)."""

from __future__ import annotations

import json

from . import eval as eval_mod
from .skills import SkillRegistry


def main() -> int:
    snapshot = SkillRegistry().snapshot()
    report = eval_mod.run_all(snapshot)
    path = eval_mod.persist(report)
    for name, variant in report["variants"].items():
        print(f"{name}: {variant['correct']}/{variant['total']} = {variant['accuracy']:.2%} "
              f"(router {variant['router']}, wrong: {', '.join(variant['wrong']) or 'none'})")
    delta = report.get("delta") or {}
    if delta:
        print(f"delta: {delta['before']:.2%} -> {delta['after']:.2%} "
              f"fixed={delta['fixedCases']} regressed={delta['regressedCases']}")
    print(f"report: {path}")
    print(json.dumps({"ok": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
