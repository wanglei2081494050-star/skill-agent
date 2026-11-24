---
name: weekly-report
description: 生成周报：汇总一周的提交、任务与数据指标，输出面向主管的进展、风险与下周计划。
metadata:
  version: 1.0.0
  tags: [reporting, team]
depends-on:
  - data-pipeline
allowed-tools:
  - read_skill_file
---

# Weekly report

Depends on `data-pipeline`, which itself depends on `csv-cleanup` and
`sql-explain`: loading this skill pulls the whole chain in order.

## Steps

1. Gather the week's commits and task list; ask for anything missing.
2. If metrics are involved, follow the `data-pipeline` procedure to get numbers
   that reconcile before you quote them.
3. Structure: 本周进展 (3-5 items, quantified) / 风险与阻塞 / 下周计划 / 需要决策.
4. Every risk line must name an owner and a date.
5. Keep it under 300 Chinese characters; a supervisor reads the first screen.
