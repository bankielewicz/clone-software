# Distributed and realtime playbook

Use this playbook when long-lived connections, pub/sub, presence, coordination, replication, or multi-node timing defines observable behavior.

## Capture and specify

- Freeze topology, node/build versions, region, protocol, clocks, connection state, membership, partitions, retry configuration, and message fixtures.
- Define handshake/authentication, framing, channels, ordering scope, delivery semantics, acknowledgement, deduplication, backpressure, heartbeat, timeout, reconnect, resume, and terminal close behavior.
- Pin consistency, leader/ownership changes, split-brain prevention, conflict policy, capacity limits, fan-out, persistence, replay window, and observability.
- Use an authorized test deployment or local simulator for partition, clock, load, and failure injection.

## Minimum MVP and proof

Implement one authenticated producer-to-consumer journey across reconnect with real state. Verify duplicates, gaps, reordering, slow consumers, malformed frames, expired credentials, disconnect races, node loss, partition/heal, replay expiry, cancellation, and cleanup. Assert exact message/state outcomes; elapsed-time assertions require explicit bounds and controlled clocks.
