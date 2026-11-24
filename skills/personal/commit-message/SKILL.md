---
name: commit-message
description: 个人习惯版提交信息：写英文 Conventional Commits，额外要求带 issue 编号和影响面标签，并给出拆分建议。
metadata:
  version: 1.0.0
  tags: [git, personal]
allowed-tools:
  - read_skill_file
---

# Commit message (personal variant)

Overrides `builtin/commit-message` because the `personal` source has higher
priority in this demo.

## Steps

1. Read the staged diff.
2. Subject: `type(scope): imperative summary` <= 72 chars.
3. Append `(#ISSUE)` when the user gave an issue id; otherwise ask for it in one
   line and continue with a placeholder.
4. Body: 2-4 lines with "what / why / impact surface".
5. If the diff touches more than two top-level areas, propose a split plan with
   the exact file groups first, then one commit message per group.
