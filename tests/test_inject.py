"""Unit tests for prompt injection budgeting and the offline router."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.bulk import BULK
from backend.app.inject import build_skill_section
from backend.app.router import route, tokens
from backend.app.skills import SkillRegistry


class InjectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ["one", "two", "three"]:
            skill_dir = self.root / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: handles {name} requests end to end.\n---\nbody\n",
                encoding="utf-8",
            )
        self.snapshot = SkillRegistry(
            sources=[{"id": "t", "label": "T", "path": str(self.root), "priority": 1}]
        ).snapshot()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_full_level_when_budget_allows(self) -> None:
        build = build_skill_section(self.snapshot, budget=800)
        self.assertEqual(build.level, "full")
        self.assertEqual(len(build.included), 3)
        self.assertIn("one", build.text)

    def test_budget_respected_with_200_skills(self) -> None:
        build = build_skill_section(self.snapshot, budget=600, extra_skills=BULK.skills(200))
        self.assertLessEqual(build.tokens, 600)
        self.assertEqual(build.level, "truncated")
        self.assertTrue(build.omitted)
        self.assertIn("more skills exist", build.text)

    def test_tiny_budget_still_returns_text(self) -> None:
        build = build_skill_section(self.snapshot, budget=60, extra_skills=BULK.skills(200))
        self.assertLessEqual(build.tokens, 60)
        self.assertTrue(build.text)

    def test_bulk_catalog_is_deterministic(self) -> None:
        first = [s.name for s in BULK.skills(200)]
        second = [s.name for s in BULK.skills(200)]
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), 200)

    def test_descriptions_are_truncated_before_dropping(self) -> None:
        long_snapshot = self.snapshot
        for skill in long_snapshot.skills:
            skill.description = "x" * 900
        build = build_skill_section(long_snapshot, budget=260)
        self.assertLessEqual(build.tokens, 260)
        self.assertIn("…", build.text)


class RouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        specs = {
            "alpha": "清理 CSV 数据并输出变更报告。",
            "beta": "分析 SQL 执行计划并给出索引建议。",
        }
        for name, desc in specs.items():
            skill_dir = self.root / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {desc}\n---\nbody\n", encoding="utf-8"
            )
        self.snapshot = SkillRegistry(
            sources=[{"id": "t", "label": "T", "path": str(self.root), "priority": 1}]
        ).snapshot()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_tokens_split_cjk_and_latin(self) -> None:
        toks = tokens("清理 CSV 数据")
        self.assertIn("清理", toks)
        self.assertIn("csv", toks)

    def test_routes_to_matching_skill(self) -> None:
        outcome = route("帮我清洗这个 CSV 数据", self.snapshot.skills, threshold=1.0)
        self.assertEqual(outcome["skill"], "alpha")

    def test_no_skill_below_threshold(self) -> None:
        outcome = route("今天天气怎么样", self.snapshot.skills, threshold=1.6)
        self.assertIsNone(outcome["skill"])

    def test_description_override_changes_routing(self) -> None:
        override = {"beta": "清洗 CSV 数据并输出报告的特殊变体。"}
        outcome = route("清洗 CSV 数据", self.snapshot.skills, threshold=1.0, descriptions=override)
        self.assertIn(outcome["skill"], {"alpha", "beta"})
        self.assertGreater(len(outcome["top"]), 1)


if __name__ == "__main__":
    unittest.main()
