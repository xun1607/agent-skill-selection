---
name: system-memory-leak-tracer
description: Track system memory growth rate to identify slow leak trends.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- memory
- leak-trace
- ram
input:
  type: object
  properties:
    interval_seconds:
      type: integer
      default: 5
output:
  type: object
  properties:
    memory_growth_rate_kb_sec:
      type: number
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

1. Read memory stats at start using system telemetry inside `terminal_shell`.
2. Sleep/wait for `interval_seconds`.
3. Read memory stats again.
4. Return growth delta rate per second.
