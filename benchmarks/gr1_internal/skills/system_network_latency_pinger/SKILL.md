---
name: system-network-latency-pinger
description: Test reachability and determine round-trip time latency to external host
  endpoints.
version: 1.0.0
category: system/monitoring
level: atomic
tags:
- system
- network
- ping
- latency
input:
  type: object
  required:
  - hostname
  properties:
    hostname:
      type: string
      description: Endpoint URL or server IP address.
output:
  type: object
  properties:
    rtt_avg_ms:
      type: number
    packet_loss_percent:
      type: number
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

1. Run command `ping -n 4 <hostname>` or `ping -c 4 <hostname>` using `terminal_shell`.
2. Parse standard output for average round trip time (RTT) and packet loss percentage.
3. Return extracted metrics.
