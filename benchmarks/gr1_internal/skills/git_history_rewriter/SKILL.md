---
name: git-history-rewriter
description: Perform git commit squash or edit using rebasing mechanisms.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- rebase
- history
- squash
input:
  type: object
  required:
  - commit_count
  properties:
    commit_count:
      type: integer
      description: Number of recent commits to merge/squash.
output:
  type: object
  properties:
    new_commit_sha:
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

1. Execute dry-run rebase or check history using `terminal_shell` (`git log -n <commit_count>`).
2. Perform squash commits via environment flags or scripting git commands.
3. Stage and commit changes, outputting the resulting commit SHA.
