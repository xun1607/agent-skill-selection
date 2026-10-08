---
name: java-deadlock-detector
description: Analyze JVM thread dumps to detect thread deadlocks and propose locking
  sequence fixes.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- deadlock
- threads
- concurrency
input:
  type: object
  required:
  - thread_dump_path
  properties:
    thread_dump_path:
      type: string
      description: Path to the thread dump file.
output:
  type: object
  properties:
    deadlocked_threads:
      type: array
      items:
        type: string
      description: List of deadlocked thread names.
    locking_resolution:
      type: string
      description: Recommended lock ordering fix.
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

1. Read the thread dump at `thread_dump_path` using `read_file`.
2. Locate the section labeled 'Found one Java-level deadlock'.
3. Extract the locked monitors and the stack traces of the competing threads.
4. Search the files using `search_code` to identify the synchronized blocks or `ReentrantLock` instances.
5. Recommend reordering the lock acquisition to avoid cyclic dependency.
