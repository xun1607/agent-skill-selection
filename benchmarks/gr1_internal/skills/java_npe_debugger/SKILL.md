---
name: java-npe-debugger
description: Pinpoint and resolve NullPointerExceptions in Java code by locating the
  exact null reference.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- npe
- nullpointerexception
- debug
input:
  type: object
  required:
  - file_path
  - line_number
  properties:
    file_path:
      type: string
      description: The path to the Java file relative to workspace.
    line_number:
      type: integer
      description: Line number where NPE occurred.
output:
  type: object
  properties:
    fixed_code:
      type: string
      description: The corrected code snippet.
    explanation:
      type: string
      description: Explanation of the null check added.
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

1. Read the code context using `read_file` around `line_number` in `file_path`.
2. Locate the reference that is causing the NullPointerException.
3. Wrap the statement with a null-safety check or initialize the reference appropriately.
4. Write the fix back to the file using `edit_file` or `write_file`.
5. Run `compile_project` to ensure the compilation succeeds.
