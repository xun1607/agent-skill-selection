---
name: python-fixture-resolver
description: Locate and correct missing or misconfigured pytest fixtures.
version: 1.0.0
category: python/testing
level: atomic
tags:
- python
- pytest
- fixture
- conftest
input:
  type: object
  required:
  - test_file_path
  - fixture_name
  properties:
    test_file_path:
      type: string
      description: Path to the test file.
    fixture_name:
      type: string
      description: Name of missing fixture.
output:
  type: object
  properties:
    resolution:
      type: string
      description: Where the fixture was found or created.
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

1. Search for `fixture_name` across `conftest.py` files using `search_code`.
2. If not found, inspect the imports or parent directories.
3. Write a new fixture or import in `conftest.py` or the test file using `edit_file`.
4. Run tests to check if fixture resolving works.
