---
name: python-mock-patcher
description: Fix broken mocks and patches in unit tests by matching target imports.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- unittest
- mock
- patch
input:
  type: object
  required:
  - test_file_path
  - mock_target
  properties:
    test_file_path:
      type: string
      description: Path to test script.
    mock_target:
      type: string
      description: Import target that was mocked incorrectly.
output:
  type: object
  properties:
    corrected_target:
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

1. Read the test file content using `read_file`.
2. Review where the module under test imports `mock_target`.
3. Remap `patch('target')` to reference the module where it is imported, not where it is defined.
4. Modify using `edit_file` and check with `run_tests`.
