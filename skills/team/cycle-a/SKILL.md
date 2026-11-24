---
name: cycle-a
description: 循环依赖演示技能 A：声明依赖 cycle-b，用于验证加载器能检测并报告循环依赖而不是栈溢出。
metadata:
  version: 1.0.0
  tags: [demo, dependency]
depends-on:
  - cycle-b
allowed-tools:
  - read_skill_file
---

# Cycle A

Loading this skill should fail with a cycle error mentioning `cycle-a -> cycle-b
-> cycle-a`. It exists only to exercise the dependency resolver.
