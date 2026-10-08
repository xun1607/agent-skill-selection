---
name: git-commit-linter
description: Analyze recent commit messages to verify alignment with Conventional
  Commits specifications.
version: 1.0.0
category: git/management
level: atomic
tags:
- git
- linter
- commit-message
- conventional-commits
input:
  type: object
  required:
  - max_commits
  properties:
    max_commits:
      type: integer
      description: Verify last N commit messages.
output:
  type: object
  properties:
    invalid_commits:
      type: array
      items:
        type: string
    all_valid:
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

1. Get recent commit messages using `terminal_shell` (`git log -n <max_commits> --pretty=format:%s`).
2. Verify each message against Conventional Commits regex (e.g. `^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?!?: .+$`).
3. Populate `invalid_commits` array if format misses.
