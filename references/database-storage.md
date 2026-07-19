# Database and storage playbook

Use this playbook when query, transaction, indexing, replication, object, file, cache, or persistence behavior is the product contract.

## Capture and specify

- Freeze engine/build, configuration, schema, collation, time zone, isolation level, topology, storage format, and dataset.
- Define query/command grammar, types, coercion, nulls, ordering, constraints, transactions, locking, consistency, conflicts, durability, quotas, and error codes.
- Pin backup/restore, migration, compaction, retention, deletion, corruption handling, replication/failover, authorization, encryption, and audit behavior.
- Never probe a reference with destructive, resource-exhausting, corruption, or failover tests without explicit environment and operation authorization.

## Minimum MVP and proof

Implement one durable create/read/update/delete or store/retrieve journey with its transaction and authorization boundary. Verify empty and maximum boundaries, invalid types, constraint conflicts, concurrent writers/readers, crash/restart, migration, backup/restore, permission denial, quota/disk failure, and deterministic query ordering. Record consistency and durability claims only for exercised configurations.
