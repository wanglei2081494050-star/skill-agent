---
name: short-drama-rewrite
description: 改短剧：把已有的短剧剧本改一改，让台词更顺，注意节奏和钩子。
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
