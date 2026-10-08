---
name: system-log-error-scanner
description: Scan server logs for critical error messages or tracebacks.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- log
- syslog
- tracebacks
input:
  type: object
  required:
  - log_path
  properties:
    log_path:
      type: string
      description: Absolute or relative path to log file.
output:
  type: object
  properties:
    errors_found:
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

1. Run search with `grep_search` or `search_code` in `log_path` looking for pattern `ERROR|CRITICAL|FATAL`.
2. Filter out duplicate trace entries.
3. Return unique error messages list.
