---
name: system-disk-space-monitor
description: Verify remaining disk space and locate massive folder directories for
  cleanup.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- disk
- storage
- cleanup
input:
  type: object
  properties:
    target_dir:
      type: string
      default: .
output:
  type: object
  properties:
    disk_free_gb:
      type: number
    largest_directories:
      type: array
      items:
        type: string
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

1. Run system specific commands (`df -h` or disk inspection commands) via `terminal_shell`.
2. Recursively scan subfolders size inside `target_dir`.
3. Format the largest 5 directories.
