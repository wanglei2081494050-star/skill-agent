"""Unit tests for skill discovery, conflicts, and the file tool guards."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.skills import SkillRegistry
from backend.app.tools import ToolError, load_skill, read_skill_file


def write_skill(root: Path, name: str, body: str = "# steps\n\n1. do it\n", extra: dict[str, str] | None = None) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: description of {name}\n---\n{body}", encoding="utf-8"
    )
    for rel, content in (extra or {}).items():
        target = skill_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


class RegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.builtin = self.root / "builtin"
        self.personal = self.root / "personal"
        write_skill(self.builtin, "alpha")
        write_skill(self.builtin, "beta", extra={"templates/note.md": "hello\n", "scripts/run.py": "print(1)\n"})
        write_skill(self.builtin, "shared")
        write_skill(self.personal, "shared")
        (self.personal / "broken").mkdir(parents=True)
        (self.personal / "broken" / "SKILL.md").write_text("---\n\tname: broken\n---\n", encoding="utf-8")
        self.registry = SkillRegistry(
            sources=[
                {"id": "builtin", "label": "Built-in", "path": str(self.builtin), "priority": 10},
                {"id": "personal", "label": "Personal", "path": str(self.personal), "priority": 30},
            ]
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scan_loads_and_skips(self) -> None:
        snapshot = self.registry.snapshot()
        names = sorted(s.name for s in snapshot.skills)
        self.assertEqual(names, ["alpha", "beta", "shared"])
        self.assertEqual(len(snapshot.skipped), 1)
        self.assertTrue(snapshot.skipped[0].reasons)

    def test_higher_priority_source_wins(self) -> None:
        snapshot = self.registry.snapshot()
        shared = snapshot.get("shared")
        assert shared is not None
        self.assertEqual(shared.source_id, "personal")
        self.assertEqual(snapshot.conflicts[0]["name"], "shared")
        self.assertEqual(snapshot.conflicts[0]["shadowed"][0]["source"], "builtin")

    def test_attached_files_listed(self) -> None:
        snapshot = self.registry.snapshot()
        beta = snapshot.get("beta")
        assert beta is not None
        self.assertIn("templates/note.md", beta.attached)
        self.assertIn("scripts/run.py", beta.attached)
        self.assertNotIn("SKILL.md", beta.attached)

    def test_unknown_skill(self) -> None:
        snapshot = self.registry.snapshot()
        with self.assertRaises(ToolError):
            load_skill(snapshot, "nope")

    def test_read_attached_file(self) -> None:
        snapshot = self.registry.snapshot()
        data = read_skill_file(snapshot, "beta", "templates/note.md")
        self.assertEqual(data["text"].strip(), "hello")

    def test_traversal_rejected(self) -> None:
        snapshot = self.registry.snapshot()
        for bad in ["../alpha/SKILL.md", "..\\alpha\\SKILL.md", "./../../etc/passwd", "/etc/passwd"]:
            with self.assertRaises(ToolError):
                read_skill_file(snapshot, "beta", bad)

    def test_missing_file_rejected(self) -> None:
        snapshot = self.registry.snapshot()
        with self.assertRaises(ToolError):
            read_skill_file(snapshot, "beta", "templates/absent.md")

    def test_symlink_escape_rejected(self) -> None:
        snapshot = self.registry.snapshot()
        secret = self.root / "secret.txt"
        secret.write_text("outside", encoding="utf-8")
        link = self.builtin / "beta" / "templates" / "link.md"
        try:
            link.symlink_to(secret)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted on this platform")
        self.registry.rescan()
        with self.assertRaises(ToolError):
            read_skill_file(self.registry.snapshot(), "beta", "templates/link.md")

    def test_hot_reload_changes_body(self) -> None:
        before = self.registry.snapshot()
        body_before = load_skill(before, "alpha")["body"]
        path = self.builtin / "alpha" / "SKILL.md"
        path.write_text(
            "---\nname: alpha\ndescription: description of alpha\n---\n# steps\n\n1. changed step\n",
            encoding="utf-8",
        )
        after = self.registry.snapshot()
        self.assertNotEqual(before.fingerprint, after.fingerprint)
        body_after = load_skill(after, "alpha")["body"]
        self.assertIn("changed step", body_after)
        self.assertNotEqual(body_before, body_after)


class DependencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _registry(self, specs: dict[str, list[str]]) -> SkillRegistry:
        for name, deps in specs.items():
            skill_dir = self.root / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            dep_block = "".join(f"  - {d}\n" for d in deps)
            (skill_dir / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: desc {name}\n"
                + (f"depends-on:\n{dep_block}" if deps else "")
                + "---\nbody\n",
                encoding="utf-8",
            )
        return SkillRegistry(
            sources=[{"id": "t", "label": "T", "path": str(self.root), "priority": 1}]
        )

    def test_chain_order(self) -> None:
        registry = self._registry({"a": ["b"], "b": ["c"], "c": []})
        result = load_skill(registry.snapshot(), "a")
        self.assertEqual(result["order"], ["c", "b", "a"])

    def test_cycle_detected(self) -> None:
        registry = self._registry({"x": ["y"], "y": ["x"]})
        with self.assertRaises(ToolError) as ctx:
            load_skill(registry.snapshot(), "x")
        self.assertIn("circular", str(ctx.exception))

    def test_missing_dependency_reported(self) -> None:
        registry = self._registry({"m": ["ghost"]})
        result = load_skill(registry.snapshot(), "m")
        self.assertEqual(result["order"], ["m"])
        self.assertTrue(result["missingDependencies"])


if __name__ == "__main__":
    unittest.main()
