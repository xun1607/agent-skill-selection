---
name: python-pytest-runner
description: Run pytest suites and parse output reports to determine failure summaries.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- pytest
- testrunner
- failures
input:
  type: object
  required:
  - test_path
  properties:
    test_path:
      type: string
      description: The file or directory of tests to run.
output:
  type: object
  properties:
    passed_count:
      type: integer
    failed_count:
      type: integer
    failures_details:
      type: string
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

1. Execute the command `pytest --tb=short <test_path>` using `terminal_shell` or `run_tests`.
2. Parse stdout to extract passed/failed counts.
3. Extract stack traces and test names for failed test cases and format them as JSON.
