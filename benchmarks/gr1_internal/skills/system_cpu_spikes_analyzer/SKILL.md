---
name: system-cpu-spikes-analyzer
description: Analyze processes causing CPU usage spikes on host system.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- cpu
- load
- monitoring
input:
  type: object
  properties:
    threshold:
      type: number
      default: 80.0
      description: Trigger diagnostic if CPU exceeds this.
output:
  type: object
  properties:
    high_cpu_detected:
      type: boolean
    top_processes:
      type: array
      items:
        type: string
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

1. Collect tasklist or top output depending on OS from environment info.
2. Call `terminal_shell` executing `ps` or `tasklist` command.
3. Parse output sorting by CPU usage.
4. Return the list of top 3 heavy processes.
