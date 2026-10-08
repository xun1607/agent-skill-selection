---
name: system-port-conflict-resolver
description: Locate processes binding to conflict port and terminate them.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- network
- ports
- kill
input:
  type: object
  required:
  - port
  properties:
    port:
      type: integer
output:
  type: object
  properties:
    killed_pid:
      type: integer
    success:
      type: boolean
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

1. Run `netstat -ano` or `lsof -i :<port>` in `terminal_shell`.
2. Parse the PID of the process using the target port.
3. Execute kill command (`taskkill /F /PID <pid>` or `kill -9 <pid>`).
4. Report success.
