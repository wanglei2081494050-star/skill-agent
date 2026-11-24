---
name: short-drama-rewrite
description: 只对已有成稿做台词润色：不新增情节、不改分集结构，逐句替换用词并给出改动理由。用户已贴出完整剧本并要求改台词、别动剧情时使用。
metadata:
  version: 1.0.0
  tags: [drama, rewrite]
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# Short-drama rewrite (dialogue polish on an existing script)

Use this skill when the user **already has a script** and wants the lines
rewritten. Creation from a logline or character sheet is a different skill
(`short-drama-script`).

## Steps

1. Ask for the script text if it was not pasted. Never invent scenes that are
   not in the input — rewriting changes wording, not story.
2. Read `templates/rewrite-rules.md` and apply every rule in order.
3. Rewrite scene by scene. Keep the scene order, the beat timing, and the
   character intents identical. Mark each changed line as `- old` / `+ new`.
4. For each change, give a one-line reason: information density, spoken rhythm,
   hook strength, or removing exposition.
5. Run `scripts/check_line_diff.py <old> <new>` when the user supplied two files;
   it verifies that no scene was lost and reports the changed-line ratio.
6. Deliver the rewritten script plus a change log table. Do not add new
   characters, do not add new plot beats.

## Rules

- One idea per line. Cut any line that only repeats what was already said.
- Replace written-Chinese connectives with spoken particles.
- Keep total episode length within +/- 10% of the original.
