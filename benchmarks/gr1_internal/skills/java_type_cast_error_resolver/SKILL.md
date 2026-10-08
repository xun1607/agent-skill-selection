---
name: java-type-cast-error-resolver
description: Resolve ClassCastException by examining object inheritance hierarchy
  and inserting instanceof checks.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- classcastexception
- oop
- typecast
input:
  type: object
  required:
  - file_path
  - line_number
  properties:
    file_path:
      type: string
      description: The Java source file path.
    line_number:
      type: integer
      description: Line number of casting.
output:
  type: object
  properties:
    fixed_code:
      type: string
      description: Fixed typecast snippet.
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

1. Read `file_path` around `line_number` using `read_file`.
2. Determine the runtime class of the object and the target interface/class.
3. Add an `instanceof` check before casting or use generic parameters.
4. Write the change to the file using `edit_file`.
