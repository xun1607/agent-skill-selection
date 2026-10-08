---
name: java-array-index-bounds-fixer
description: Locate and fix ArrayIndexOutOfBoundsException in loop indices or array
  bounds declarations.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- array
- bounds
- index-out-of-bounds
input:
  type: object
  required:
  - file_path
  - line_number
  properties:
    file_path:
      type: string
      description: Path to the Java source file.
    line_number:
      type: integer
      description: Line number of the bounds exception.
output:
  type: object
  properties:
    fixed_code:
      type: string
      description: Corrected loop or array accessor.
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

1. Read `file_path` at `line_number` using `read_file`.
2. Verify the array length and check loop termination conditions (e.g. change `<` instead of `<=`).
3. Apply the correction to code using `edit_file`.
4. Compile with `compile_project` and run tests via `run_tests` to verify.
