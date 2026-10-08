---
name: git-file-cherry-pick
description: Apply file state from a specific commit to the current branch without
  merging the whole commit.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- cherry-pick
- file-checkout
input:
  type: object
  required:
  - commit_sha
  - file_path
  properties:
    commit_sha:
      type: string
    file_path:
      type: string
output:
  type: object
  properties:
    status:
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

1. Execute checkout of file state from commit using `terminal_shell` (`git checkout <commit_sha> -- <file_path>`).
2. Stage the file with `git add <file_path>`.
3. Return success statement.
