"""Unit tests for the SKILL.md frontmatter parser."""

from __future__ import annotations

import unittest

from backend.app.frontmatter import parse_frontmatter

VALID = """---
name: demo-skill
description: A demo skill used by tests.
metadata:
  version: 1.0.0
  tags: [demo, test]
allowed-tools:
  - read_skill_file
---

# Demo

Body line.
"""


class FrontmatterTest(unittest.TestCase):
    def test_valid_frontmatter(self) -> None:
        parsed = parse_frontmatter(VALID)
        self.assertTrue(parsed.ok, parsed.errors)
        self.assertEqual(parsed.meta["name"], "demo-skill")
        self.assertEqual(parsed.meta["description"], "A demo skill used by tests.")
        self.assertEqual(parsed.meta["metadata"]["version"], "1.0.0")
        self.assertEqual(parsed.meta["metadata"]["tags"], ["demo", "test"])
        self.assertEqual(parsed.meta["allowed-tools"], ["read_skill_file"])
        self.assertIn("Body line.", parsed.body)

    def test_missing_frontmatter(self) -> None:
        parsed = parse_frontmatter("# no frontmatter\n")
        self.assertFalse(parsed.ok)
        self.assertIn("missing frontmatter", parsed.errors[0])

    def test_unterminated(self) -> None:
        parsed = parse_frontmatter("---\nname: x\ndescription: y\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("unterminated" in e for e in parsed.errors))

    def test_missing_description(self) -> None:
        parsed = parse_frontmatter("---\nname: x\n---\nbody\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("description" in e for e in parsed.errors))

    def test_missing_name(self) -> None:
        parsed = parse_frontmatter("---\ndescription: only a description\n---\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("name" in e for e in parsed.errors))

    def test_tab_indentation_rejected(self) -> None:
        parsed = parse_frontmatter("---\n\tname: x\n\tdescription: y\n---\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("tab indentation" in e for e in parsed.errors))

    def test_bad_name_shape(self) -> None:
        parsed = parse_frontmatter("---\nname: Not_Kebab\n---\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("does not match" in e or "kebab-case" in e for e in parsed.errors))

    def test_duplicate_key(self) -> None:
        parsed = parse_frontmatter("---\nname: a\ndescription: b\nname: c\n---\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("duplicate key" in e for e in parsed.errors))

    def test_overlong_description(self) -> None:
        long_desc = "d" * 1030
        parsed = parse_frontmatter(f"---\nname: a\ndescription: {long_desc}\n---\n")
        self.assertFalse(parsed.ok)
        self.assertTrue(any("1024" in e for e in parsed.errors))

    def test_comment_is_stripped(self) -> None:
        parsed = parse_frontmatter("---\nname: a\ndescription: b # trailing comment\n---\n")
        self.assertTrue(parsed.ok, parsed.errors)
        self.assertEqual(parsed.meta["description"], "b")

    def test_crlf_input(self) -> None:
        parsed = parse_frontmatter(VALID.replace("\n", "\r\n"))
        self.assertTrue(parsed.ok, parsed.errors)
        self.assertEqual(parsed.meta["name"], "demo-skill")


if __name__ == "__main__":
    unittest.main()
