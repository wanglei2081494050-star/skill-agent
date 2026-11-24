"""End-to-end smoke check without the UI.

Run: py -m backend.app.smoke
Covers: scan + skip reporting + conflicts, prompt budget degradation with 200
simulated skills, tool path guards, dependency cycle detection, one offline chat
turn, and the routing eval.
"""

from __future__ import annotations

import json
import sys

from . import eval as eval_mod
from .agent import run_turn
from .bulk import BULK
from .inject import build_skill_section
from .skills import SkillRegistry
from .tools import ToolError, load_skill, read_skill_file

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok  " if condition else "FAIL"
    print(f"[{status}] {name}{(' - ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(name)


def main() -> int:
    registry = SkillRegistry()
    snapshot = registry.snapshot()

    check("scan finds >= 6 skills", len(snapshot.skills) >= 6, f"{len(snapshot.skills)} skills")
    check("broken skill skipped with reasons", len(snapshot.skipped) == 1, str([s.path for s in snapshot.skipped]))
    check("skipped entry carries a reason", bool(snapshot.skipped and snapshot.skipped[0].reasons))
    check("same-name conflict resolved", len(snapshot.conflicts) >= 1, str([c["name"] for c in snapshot.conflicts]))
    winners = {c["name"]: c["winner"]["source"] for c in snapshot.conflicts}
    check("personal overrides builtin", winners.get("commit-message") == "personal", str(winners))

    by_name = snapshot.by_name()
    drama = by_name.get("short-drama-script")
    check("attached files discovered", bool(drama and drama.attached), str(drama.attached if drama else []))

    body = load_skill(snapshot, "short-drama-script")["body"]
    check("load_skill returns body", "Steps" in body)

    try:
        read_skill_file(snapshot, "short-drama-script", "../../builtin/commit-message/SKILL.md")
        check("traversal blocked", False, "read succeeded")
    except ToolError as exc:
        check("traversal blocked", "rejected" in str(exc), str(exc))

    try:
        read_skill_file(snapshot, "short-drama-script", "C:/Windows/win.ini")
        check("absolute path blocked", False, "read succeeded")
    except ToolError as exc:
        check("absolute path blocked", "rejected" in str(exc), str(exc))

    try:
        load_skill(snapshot, "cycle-a")
        check("dependency cycle rejected", False, "load succeeded")
    except ToolError as exc:
        check("dependency cycle rejected", "circular" in str(exc), str(exc))

    chain = load_skill(snapshot, "weekly-report")["order"]
    check(
        "dependency chain in order",
        chain[:3] == ["csv-cleanup", "sql-explain", "data-pipeline"] or chain == [
            "csv-cleanup",
            "sql-explain",
            "data-pipeline",
            "weekly-report",
        ],
        str(chain),
    )

    small = build_skill_section(snapshot, budget=800)
    bulk = build_skill_section(snapshot, budget=800, extra_skills=BULK.skills(200))
    check("full prompt fits small catalogue", small.level == "full", small.level)
    check("200-skill prompt stays in budget", bulk.tokens <= 800, f"{bulk.tokens}/800 at level {bulk.level}")
    check("200-skill prompt degrades", bulk.level != "full", bulk.level)

    tiny = build_skill_section(snapshot, budget=200, extra_skills=BULK.skills(200))
    check("tiny budget still fits", tiny.tokens <= 200, f"{tiny.tokens}/200 level={tiny.level}")

    turn = run_turn(snapshot, "这段短剧台词太书面了，帮我改得口语一点，剧情一点都别动。")
    check("offline turn loads a skill", bool(turn["loaded"]), str(turn["loaded"]))
    check("offline turn mode labelled", turn["mode"] == "offline", turn["mode"])
    check("offline turn reads attached file", bool(turn["files"]), str([f["path"] for f in turn["files"]]))

    report = eval_mod.run_all(snapshot)
    for name, variant in report["variants"].items():
        check(f"eval {name} runs", variant["total"] >= 15, f"{variant['correct']}/{variant['total']}")
    delta = report.get("delta") or {}
    if delta:
        print(
            f"[info] routing accuracy {delta['before']:.2%} -> {delta['after']:.2%} "
            f"(fixed: {', '.join(delta['fixedCases']) or 'none'})"
        )

    reload_ok = registry.rescan().fingerprint == snapshot.fingerprint
    check("rescan is stable without edits", reload_ok)

    print(json.dumps({"failures": FAILURES}, ensure_ascii=False))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
