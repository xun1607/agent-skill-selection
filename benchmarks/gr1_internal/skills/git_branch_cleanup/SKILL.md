---
name: git-branch-cleanup
description: Analyze local git branches and prune those already merged to main.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- branch
- prune
- cleanup
input:
  type: object
  properties:
    target_branch:
      type: string
      default: main
      description: The main integration branch.
output:
  type: object
  properties:
    deleted_branches:
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

1. List merged branches using `terminal_shell` (`git branch --merged <target_branch>`).
2. Filter out master, main, and current branch.
3. For other branches, delete them using `git branch -d <branch_name>`.
4. Return the list of deleted branches.
