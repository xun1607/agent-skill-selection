---
name: git-conflict-resolver
description: Locate conflict markers in the workspace, resolve them, and stage the
  files.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- merge-conflict
- resolve
- git-add
input:
  type: object
  required:
  - file_path
  properties:
    file_path:
      type: string
      description: File containing git merge conflicts.
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

1. Read the conflicted file content using `read_file`.
2. Parse conflict blocks starting with `<<<<<<<` and ending with `>>>>>>>`.
3. Decide on conflict resolution strategy (keep HEAD, incoming, or combine).
4. Rewrite the file using `edit_file` removing conflict markers.
5. Stage the file using `terminal_shell` (`git add <file_path>`).
