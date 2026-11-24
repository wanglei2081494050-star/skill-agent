---
name: release-notes
description: 根据 git 提交记录生成面向用户的中文发布说明，按「新功能/改进/修复/破坏性变更」分组，并附升级注意事项。
metadata:
  version: 1.0.0
  tags: [docs, release]
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# Release notes (from commit history)

Base version: builtin. The team copy of this skill overrides it in the demo.

## Steps

1. Collect the commit range the user gives (`from..to`); if absent, use the last
   tag to `HEAD`.
2. Run `scripts/collect_commits.py <from>..<to>` to get a normalized list of
   subject lines, authors, and touched paths.
3. Classify each commit into Features / Improvements / Fixes / Breaking.
   A commit belongs to Breaking when it changes a public interface, a config
   key, or stored data.
4. Rewrite each item from the user's point of view: what changed for them, not
   which file changed.
5. Read `templates/section-order.md` for the exact section order and the
   "upgrade notes" block.
6. Deliver in Chinese, newest section first, one bullet per user-visible change.
