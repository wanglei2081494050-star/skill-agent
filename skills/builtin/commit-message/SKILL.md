---
name: commit-message
description: 根据 git diff 写一条符合 Conventional Commits 的英文提交信息（含正文与影响范围），并检查现有提交是否是有意义的信息。
metadata:
  version: 1.0.0
  tags: [git, docs]
allowed-tools:
  - read_skill_file
---

# Commit message authoring

## Steps

1. Read the diff the user provides (`git diff --staged` output or a file list).
2. Pick exactly one type: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`,
   `build`, `chore`, `ci`. If a diff mixes types, propose splitting it into
   multiple commits and say which files belong together.
3. Write the subject as `type(scope): imperative summary`, <= 72 characters, no
   trailing period, no `update`/`fix`/`wip`-style filler.
4. Write the body in 2-5 lines: what changed, why, and the user-visible effect.
5. Read `templates/commit-examples.md` if the change touches a public API, so the
   breaking-change footer format matches the team convention.
6. Deliver the ready-to-run `git commit -m "..." -m "..."` command.
