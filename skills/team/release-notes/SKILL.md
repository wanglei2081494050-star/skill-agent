---
name: release-notes
description: 团队规范版发布说明：从 git 提交记录生成中文发布说明，按团队模板分组，并额外输出面向客服的「用户可感知变化」清单。
metadata:
  version: 2.0.0
  tags: [docs, release, team]
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# Release notes (team standard)

This is the team-owned variant. It overrides `builtin/release-notes` because the
`team` source has higher priority. Differences from the builtin copy:

1. Also produce a "customer support" section listing only user-perceivable
   changes, in the same order as the changelog.
2. Always include the affected config keys in the upgrade notes.
3. Reuse `builtin/release-notes`' script by path
   `../builtin/release-notes/scripts/collect_commits.py` — reading outside this
   skill directory is blocked by the file tool, so copy the command instead:
   run `python skills/builtin/release-notes/scripts/collect_commits.py <range>`
   from the repo root.

## Steps

1. Collect the commit list for the range.
2. Group: 新功能 / 改进 / 修复 / 破坏性变更.
3. Add the support section: one line per change a user can notice.
4. Add upgrade notes with the exact config keys and migration order.
