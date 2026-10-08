---
name: java-database-connection-leak-detector
description: Identify JDBC connection leaks by checking for unclosed Connection, Statement,
  or ResultSet objects.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- jdbc
- resource-leak
- connection-leak
input:
  type: object
  required:
  - source_dir
  properties:
    source_dir:
      type: string
      description: Relative directory containing Java repository or DAO classes.
output:
  type: object
  properties:
    leaky_files:
      type: array
      items:
        type: string
      description: Java files with connection leaks.
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

1. Use `search_code` in `source_dir` looking for `.getConnection(` or `.prepareStatement(`.
2. For each hit, check if the resource is closed in a `finally` block or instantiated in a `try-with-resources` statement.
3. If a leak is found, refactor the code to try-with-resources using `edit_file`.
4. Compile and test the project.
