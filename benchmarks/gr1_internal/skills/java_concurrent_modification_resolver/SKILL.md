---
name: java-concurrent-modification-resolver
description: Fix ConcurrentModificationException occurrences when modifying Java collections
  in parallel or within iterators.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- concurrency
- collections
- iterator
input:
  type: object
  required:
  - file_path
  - collection_name
  properties:
    file_path:
      type: string
      description: The Java file containing the collection operations.
    collection_name:
      type: string
      description: The name of the collection variable.
output:
  type: object
  properties:
    fixed_code:
      type: string
      description: Code replacement replacing iterator loop or using concurrent collections.
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

1. Read `file_path` content using `read_file`.
2. Locate the loop where the list/map is being traversed and modified simultaneously.
3. Replace standard collections with `CopyOnWriteArrayList` or `ConcurrentHashMap`, or modify the traversal to use iterator's explicit `remove()` method.
4. Write back modifications using `edit_file` and compile with `compile_project`.
