---
name: csv-cleanup
description: 清洗 CSV 数据：统一编码、去重、补空值、纠正类型，并输出变更报告和可复现的清洗脚本。
metadata:
  version: 1.0.0
  tags: [data, csv]
allowed-tools:
  - read_skill_file
  - run_skill_script
---

# CSV cleanup

## Steps

1. Detect encoding (utf-8 / utf-8-sig / gbk) and delimiter; report both.
2. Profile every column: null count, distinct count, min/max, and the ratio of
   values that fail type parsing.
3. Apply the cleanup order: decode -> trim whitespace -> normalize header names
   to snake_case -> dedupe on the primary key -> fill or drop nulls -> cast types.
   Never silently drop rows: every dropped row must be counted.
4. Emit `clean.csv` plus `report.json` with counts per step and the sample rows
   that were removed.
5. Deliver the runnable script and the report summary table.
