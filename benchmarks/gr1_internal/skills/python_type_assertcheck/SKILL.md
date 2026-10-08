---
name: python-type-assertcheck
description: Add or fix runtime type assertions in python test suites.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- typing
- assertions
- test-sanity
input:
  type: object
  required:
  - test_file_path
  properties:
    test_file_path:
      type: string
      description: Target test file.
output:
  type: object
  properties:
    added_assertions:
      type: integer
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

1. Read test file using `read_file`.
2. Check test assertions for missing instance type checking (`assert isinstance(val, Type)`).
3. Enhance assertions using `edit_file` to ensure strict typing.
4. Run `run_tests` to verify no assertions fail.
