---
name: python-flaky-test-detector
description: Identify flaky (intermittent) test cases by executing them repeatedly.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- flaky
- pytest
- ci
input:
  type: object
  required:
  - test_case_name
  properties:
    test_case_name:
      type: string
      description: The test function name to stress test.
output:
  type: object
  properties:
    is_flaky:
      type: boolean
    fail_rate:
      type: number
constraints:
  host:
    os:
    - linux
    - darwin
    - windows
  resources:
    memory: 256MB
    timeout: 30s
  safety:
    fs_access: read-write
    requires_approval: false
---

## Instructions

1. Execute the specific test in a loop (e.g. 10 iterations) using `terminal_shell` with `pytest -k <test_case_name>`.
2. Track exit codes of each iteration.
3. Compute failure rate. If it fails sometimes but passes other times, mark `is_flaky` as true.
