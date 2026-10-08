---
name: git-merge-validator
description: Simulate branch merge dry-run to identify conflicts before actual merge.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- merge
- dry-run
- validation
input:
  type: object
  required:
  - source_branch
  - target_branch
  properties:
    source_branch:
      type: string
    target_branch:
      type: string
output:
  type: object
  properties:
    mergeable:
      type: boolean
    conflicted_files:
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

1. Checkout to `target_branch`.
2. Run dry-run merge `git merge --no-commit --no-ff <source_branch>` in `terminal_shell`.
3. Scan exit code. If conflict occurs, parse conflicted files list.
4. Clean dry run via `git merge --abort`.
