"""Tests for the restricted script runner (timeout, network block, output cap)."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from backend.app.config import SCRIPT_MAX_OUTPUT_BYTES
from backend.app.sandbox import run_script
from backend.app.skills import SkillRegistry


class SandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._skill("runner", {
            "scripts/net.py": "import socket\nsocket.create_connection(('example.com', 80), 2)\n",
            "scripts/env.py": "import os\nprint(sorted(k for k in os.environ if 'KEY' in k or 'TOKEN' in k))\n",
            "scripts/noisy.py": "print('x' * 200000)\n",
            "scripts/slow.py": "import time\ntime.sleep(30)\n",
            "scripts/ok.py": "print('fine')\n",
        })
        self.registry = SkillRegistry(
            sources=[{"id": "t", "label": "T", "path": str(self.root), "priority": 1}]
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _skill(self, name: str, files: dict[str, str]) -> None:
        skill_dir = self.root / name
        (skill_dir / "scripts").mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: runner fixture\n---\nbody\n", encoding="utf-8"
        )
        for rel, content in files.items():
            path = skill_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_happy_path(self) -> None:
        result = run_script(self.registry.snapshot().by_name(), "runner", "scripts/ok.py", [])
        self.assertEqual(result["exitCode"], 0, result)
        self.assertIn("fine", result["stdout"])
        self.assertEqual(result["sandbox"]["network"], "blocked")

    def test_network_blocked(self) -> None:
        result = run_script(self.registry.snapshot().by_name(), "runner", "scripts/net.py", [])
        self.assertNotEqual(result["exitCode"], 0)
        self.assertIn("network access is disabled", result["stderr"])

    def test_environment_stripped(self) -> None:
        result = run_script(self.registry.snapshot().by_name(), "runner", "scripts/env.py", [])
        self.assertEqual(result["stdout"].strip(), "[]")

    def test_output_capped(self) -> None:
        result = run_script(self.registry.snapshot().by_name(), "runner", "scripts/noisy.py", [])
        self.assertLessEqual(len(result["stdout"]), SCRIPT_MAX_OUTPUT_BYTES)

    def test_timeout(self) -> None:
        original = __import__("backend.app.sandbox", fromlist=["SCRIPT_TIMEOUT_SECONDS"])
        old = original.SCRIPT_TIMEOUT_SECONDS
        original.SCRIPT_TIMEOUT_SECONDS = 0.5
        try:
            result = run_script(self.registry.snapshot().by_name(), "runner", "scripts/slow.py", [])
        finally:
            original.SCRIPT_TIMEOUT_SECONDS = old
        self.assertFalse(result["ok"])
        self.assertIn("timed out", result["error"])

    def test_non_python_script_rejected(self) -> None:
        snapshot = self.registry.snapshot()
        result = run_script(snapshot.by_name(), "runner", "SKILL.md", [])
        self.assertFalse(result["ok"])
        self.assertIn("only .py", result["error"])

    def test_traversal_rejected(self) -> None:
        result = run_script(self.registry.snapshot().by_name(), "runner", "../../etc/passwd", [])
        self.assertFalse(result["ok"])
        self.assertIn("rejected", result["error"])


if __name__ == "__main__":
    unittest.main()
