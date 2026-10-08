---
name: java-class-not-found-fixer
description: Diagnose classpath problems leading to ClassNotFoundException or NoClassDefFoundError.
version: 1.0.0
category: java/debugging
level: atomic
tags:
- java
- classpath
- classnotfound
- dependency
input:
  type: object
  required:
  - classname
  - build_file
  properties:
    classname:
      type: string
      description: The fully qualified class name not found.
    build_file:
      type: string
      description: The build config file path (pom.xml or build.gradle).
output:
  type: object
  properties:
    missing_dependency:
      type: string
      description: The group:artifact:version coordinates missing.
    status:
      type: string
      description: Fix status.
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

1. Scan the `build_file` using `read_file` to see active dependencies.
2. Search for the library providing `classname` in online repositories or index listings.
3. Add the missing dependency element using `edit_file` to the build config.
4. Call `compile_project` to fetch the dependency and verify the build passes.
