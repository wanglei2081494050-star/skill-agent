---
name: data-pipeline
description: 搭建并检查 ETL 数据管道：从 CSV 落地到数仓表，包含清洗、分批写入、重跑幂等和行数对账。
metadata:
  version: 1.0.0
  tags: [data, etl]
depends-on:
  - csv-cleanup
  - sql-explain
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# ETL data pipeline

This skill declares dependencies, so loading it also loads `csv-cleanup` and
`sql-explain` (their bodies arrive in the same turn, once each, in dependency
order).

## Steps

1. Land the raw file, then run the `csv-cleanup` procedure on it.
2. Load in batches of 1000 rows inside one transaction per batch; record the
   batch boundary so a failed run can resume.
3. Make the load idempotent: upsert on the natural key, never plain insert.
4. Reconcile: source row count, cleaned row count, loaded row count, and
   duplicate count must be printed at the end.
5. If a load query is slow, hand the plan to the `sql-explain` procedure.
6. Deliver: pipeline script, the reconcile table, and the rerun command.
