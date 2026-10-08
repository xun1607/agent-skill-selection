---
name: python-coverage-analyzer
description: Assess code test coverage and identify untested lines using coverage
  package.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- coverage
- untested-lines
- pytest
input:
  type: object
  required:
  - module_name
  properties:
    module_name:
      type: string
      description: Python module name to check coverage.
output:
  type: object
  properties:
    coverage_percentage:
      type: number
    missing_lines:
      type: array
      items:
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

1. Run `coverage run -m pytest` and `coverage report -m` via `terminal_shell`.
2. Parse the report output specifically for `module_name`.
3. Extract the total coverage percentage and list of uncovered line numbers.
