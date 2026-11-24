---
name: sql-explain
description: 分析 PostgreSQL/MySQL 的 EXPLAIN 输出，找出全表扫描、错误的索引选择、隐式类型转换和 N+1 风险，并给出可执行的索引或改写建议。
metadata:
  version: 1.0.0
  tags: [database, performance]
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# SQL execution plan review

## Steps

1. Determine engine and version from the user's message; the plan format differs
   (`Seq Scan` vs `type: ALL`, `cost=` vs `rows=`).
2. Save the plan to a file and run `scripts/analyze_plan.py <file>`. It reports
   sequential scans, estimated/actual row misestimation ratios, and sort spills.
3. Read `templates/plan-checklist.md` and walk the checklist against the plan.
4. For every finding produce: the plan node, the cause, and a concrete fix
   (index DDL, predicate rewrite, or query split).
5. Deliver a table: node | problem | fix | expected effect. Never recommend an
   index without naming the exact column order.
6. If the plan shows a filter on a casted column (`WHERE created_at::date = ...`),
   flag it as non-sargable and rewrite with a range predicate.
