---
name: system-docker-container-inspector
description: Assess health state and fetch failure logs from failing Docker containers.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- docker
- containers
- healthcheck
input:
  type: object
  required:
  - container_name
  properties:
    container_name:
      type: string
output:
  type: object
  properties:
    status:
      type: string
    health_status:
      type: string
    recent_stderr:
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

1. Run `docker inspect <container_name>` via `terminal_shell` to fetch health config.
2. Run `docker logs --tail 20 <container_name>` to capture stderr outputs.
3. Return JSON containing status, health state, and logs snippet.
