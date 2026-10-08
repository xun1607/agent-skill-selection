---
name: git-stash-manager
description: Stash local dirty modifications, execute operations, and pop back changes
  safely.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- stash
- workspace
- dirty
input:
  type: object
  required:
  - action
  properties:
    action:
      type: string
      description: 'Action: ''push'', ''pop'', ''list''.'
output:
  type: object
  properties:
    stdout:
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

1. Execute the git stash command based on `action` (e.g. `git stash push -u` or `git stash pop`) using `terminal_shell`.
2. Capture standard output and return it.
