# Data pipeline playbook

Use this playbook when ingestion, validation, transformation, orchestration, delivery, or backfill is the externally consumed contract.

## Capture and specify

- Freeze source/sink schema versions, partitions, clocks/time zones, watermarks, ordering, batch or stream boundaries, checkpoint state, and representative fixtures.
- Define accepted encodings, missing/null/zero semantics, validation and quarantine, transformation formulas, keys, deduplication, late/corrected events, replay, and schema evolution.
- Pin delivery semantics, transaction boundaries, idempotency, retry/backoff, partial failure, checkpoint recovery, backfill windows, retention, lineage, and observability.
- Preserve raw inputs and independently computed expected outputs; do not use the clone transformation to author its own fixture.

## Minimum MVP and proof

Implement one source-to-sink slice with durable checkpointing and explicit bad-record handling. Verify empty, duplicate, out-of-order, late, corrected, malformed, boundary-time, dependency-failure, restart, replay, and backfill cases. Compare exact records, ordering, lineage, checkpoint state, and prohibited duplicate or partial effects.
