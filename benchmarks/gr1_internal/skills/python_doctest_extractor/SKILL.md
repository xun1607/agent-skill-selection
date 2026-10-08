---
name: python-doctest-extractor
description: Run and extract doctests embedded within python module docstrings.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- doctest
- docstring
- unittest
input:
  type: object
  required:
  - file_path
  properties:
    file_path:
      type: string
      description: Python source file containing doctests.
output:
  type: object
  properties:
    failures_count:
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

1. Run the python doctest module against `file_path` using `terminal_shell` (`python -m doctest -v file_path`).
2. Read and parse output results.
3. Return count of failures found inside docstrings.
