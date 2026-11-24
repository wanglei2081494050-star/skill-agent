"""Routing evaluation: run the labeled request set, report accuracy.

Two variants are always produced so the description-tuning experiment is
reproducible:

``baseline``  the descriptions as first written (copied into
              ``eval/description_variants.json`` when the pair was authored)
``tuned``     the disambiguated descriptions (the ones now in the SKILL.md files)

Router: the deterministic BM25 router by default. With an API key and
``mode="model"`` each case is also asked of the model, which costs tokens; the
report records which mode produced the numbers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import EVAL_CASES_PATH, EVAL_REPORT_DIR, REPO_ROOT
from .router import DEFAULT_THRESHOLD, route
from .skills import Snapshot

VARIANTS_PATH = REPO_ROOT / "eval" / "description_variants.json"


def load_cases() -> dict[str, Any]:
    data = json.loads(EVAL_CASES_PATH.read_text(encoding="utf-8"))
    data.setdefault("threshold", DEFAULT_THRESHOLD)
    return data


def load_variants() -> dict[str, dict[str, str]]:
    if not VARIANTS_PATH.exists():
        return {}
    return json.loads(VARIANTS_PATH.read_text(encoding="utf-8")).get("variants", {})


def run_suite(
    snapshot: Snapshot,
    variant: str,
    descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    cases = load_cases()
    threshold = float(cases.get("threshold", DEFAULT_THRESHOLD))
    rows: list[dict[str, Any]] = []
    correct = 0
    for case in cases["cases"]:
        outcome = route(case["text"], snapshot.skills, threshold=threshold, descriptions=descriptions)
        hit = outcome["skill"] == case["expected"]
        correct += 1 if hit else 0
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "text": case["text"],
                "expected": case["expected"],
                "predicted": outcome["skill"],
                "score": outcome["score"],
                "hit": hit,
                "runnerUp": outcome["top"][1] if len(outcome["top"]) > 1 else None,
            }
        )
    total = len(rows)
    return {
        "variant": variant,
        "router": "bm25-lite",
        "threshold": threshold,
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "wrong": [r["id"] for r in rows if not r["hit"]],
        "rows": rows,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_all(snapshot: Snapshot) -> dict[str, Any]:
    variants = load_variants()
    results = {name: run_suite(snapshot, name, descriptions=variants.get(name)) for name in variants}
    if not results:
        results = {"current": run_suite(snapshot, "current")}
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fingerprint": snapshot.fingerprint,
        "variants": results,
        "delta": _delta(results),
    }


def _delta(results: dict[str, Any]) -> dict[str, Any]:
    if "baseline" in results and "tuned" in results:
        before = results["baseline"]
        after = results["tuned"]
        fixed = sorted(set(before["wrong"]) - set(after["wrong"]))
        broken = sorted(set(after["wrong"]) - set(before["wrong"]))
        return {
            "before": before["accuracy"],
            "after": after["accuracy"],
            "absoluteGain": round(after["accuracy"] - before["accuracy"], 4),
            "fixedCases": fixed,
            "regressedCases": broken,
        }
    return {}


def persist(report: dict[str, Any]) -> Path:
    EVAL_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    latest = EVAL_REPORT_DIR / "latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return latest
