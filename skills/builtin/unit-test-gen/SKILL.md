---
name: unit-test-gen
description: 为已有函数或模块补单元测试，优先覆盖边界值、错误分支和并发/幂等场景，输出可直接运行的测试文件。
metadata:
  version: 1.0.0
  tags: [testing]
allowed-tools:
  - read_skill_file
---

# Unit test generation

## Steps

1. List the function's contract: inputs, outputs, thrown errors, and side
   effects. If the contract is ambiguous, state the assumption you test against.
2. Choose the branch set in this order: empty input, boundary value, happy path,
   error path, idempotency (same call twice), and concurrency when shared state
   exists.
3. Prefer table-driven tests for pure functions; prefer fakes over mocks for I/O.
4. One assertion concept per test; assert on observable behavior, not internals.
5. Make the test fail first (wrong expectation) and confirm the failure message
   is readable, then fix the expectation.
6. Deliver the test file plus a coverage summary table: branch | covered | why
   it matters.
