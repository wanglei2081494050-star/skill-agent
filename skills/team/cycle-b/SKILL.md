---
name: cycle-b
description: 循环依赖演示技能 B：声明依赖 cycle-a，与 cycle-a 构成环，用于验证循环依赖检测。
metadata:
  version: 1.0.0
  tags: [demo, dependency]
depends-on:
  - cycle-a
allowed-tools:
  - read_skill_file
---

# Cycle B

Counterpart of `cycle-a`. Together they form a two-node cycle.
