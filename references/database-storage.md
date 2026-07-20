# Database and storage playbook

Use this playbook when query, transaction, indexing, replication, object, file, cache, or persistence behavior is the product contract.

## Capture and specify

- Freeze engine/build, configuration, schema, collation, time zone, isolation level, topology, storage format, and dataset.
- Define query/command grammar, types, coercion, nulls, ordering, constraints, transactions, locking, consistency, conflicts, durability, quotas, and error codes.
- Pin backup/restore, migration, compaction, retention, deletion, corruption handling, replication/failover, authorization, encryption, and audit behavior.
- Never probe a reference with destructive, resource-exhausting, corruption, or failover tests without explicit environment and operation authorization.

## Minimum MVP and proof

Implement one durable create/read/update/delete or store/retrieve journey with its transaction and authorization boundary. Verify empty and maximum boundaries, invalid types, constraint conflicts, concurrent writers/readers, crash/restart, migration, backup/restore, permission denial, quota/disk failure, and deterministic query ordering. Record consistency and durability claims only for exercised configurations.

## Full-stack persistence proof

When a browser journey includes this storage boundary, load [Full-stack QA contract](full-stack-qa.md). The required journey uses an `identity_bindings` `BIND-###` source to capture the created or changed identity, binds it through a concrete additional-exchange path and `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` contract pointers, verifies its application-owned API or data postcondition, then observes the same identity and state after the declared reload, relogin, or restart event. The canonical result reports one `captured_value_sha256` and the same `observed_value_sha256` for every consumer. Every application-owned component remains `REAL`; identical complete core declarations may share a `service_id`, while each applicable queue, cache, or worker is an explicit supporting service with readiness, assertion, proof artifact, and journey binding. An in-memory substitute or intercepted application endpoint cannot satisfy the required lane.

Pin the Playwright project and a controlled package value (`@playwright/test`, `playwright`, or `playwright-core`), the primary exchange, and every declared `additional_exchanges` observation to the canonical result. Each non-excluded external boundary records protocol, endpoint, `LOOPBACK` or `AUTHORIZED_SANDBOX` classification, bounded readiness, assertion, artifact, and journey reference and must report `PASS`; an excluded boundary reports `NOT_APPLICABLE`. The exact declared supporting-service set also appears in the result and every entry must pass.

The target repository owns the migration, reset, seed, readiness, probe, cleanup, and indexed no-shell GATE commands. Its GATE wrapper preflights capability, startup, and readiness before behavioral execution: declared exit `7` is retained by `record-run` as `BLOCKED`, while a behavioral mismatch is `FAIL` with exit `5`. The plan and GATE put `ci.result_path` in `fresh_artifact_paths`; an unchanged pre-existing result is rejected as `RUN_ARTIFACT_STALE` with exit `4`. The skill never installs or starts undeclared database tooling. Runtime validation checks the declared readiness contracts and allowed HTTP origins but does not execute probes, parse the lockfile, prove Playwright installation, parse CI YAML, or query hosted checks.

The latest linked `PASS` `RUN` and its matching canonical result prove only the declared persisted observation in the retained environment. They do not prove unexercised constraints, isolation levels, durability under crash, replication, backup/restore, migration safety, external provider behavior, or production state. Verify those separately with repository-native cases or record them as exclusions, gaps, or blockers.
