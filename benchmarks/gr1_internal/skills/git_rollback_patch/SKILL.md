---
name: git-rollback-patch
description: Revert a specific faulty commit and prepare a clean rollback patch.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- revert
- rollback
- patch
input:
  type: object
  required:
  - commit_sha
  properties:
    commit_sha:
      type: string
      description: SHA of commit to roll back.
output:
  type: object
  properties:
    patch_file:
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

1. Revert commit using `terminal_shell` (`git revert --no-commit <commit_sha>`).
2. Generate patch file using `git diff > rollback.patch`.
3. Reset revert changes (`git reset --hard HEAD`).
4. Output patch file name and content.
