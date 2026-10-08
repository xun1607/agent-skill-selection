---
name: java-oom-analyzer
description: Analyze heap memory or garbage collection logs to solve Java OutOfMemoryErrors.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- oom
- outofmemory
- memory-leak
input:
  type: object
  required:
  - log_file_path
  properties:
    log_file_path:
      type: string
      description: Path to the log containing OOM or heap dump trace.
output:
  type: object
  properties:
    leak_candidate:
      type: string
      description: Suspected class or leak source.
    recommendation:
      type: string
      description: Recommendation to resolve the leak.
constraints:
  host:
    os:
    - linux
  resources:
    memory: 256MB
    timeout: 30s
  safety:
    fs_access: read-write
    requires_approval: false
---

## Instructions

1. Read the GC or error log using `read_file` on `log_file_path`.
2. Identify memory leak symptoms (e.g. progressive memory consumption or specific class instance counts).
3. Use `search_code` to search for resource leaks, unclosed streams, static collections, or infinite loops in the codebase.
4. Outline recommendations or edit classes to close resources properly.
