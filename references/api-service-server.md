# API, service, and server playbook

Use this playbook when the primary contract is a protocol, API, webhook, daemon, worker, integration, network service, or server-side process.

## Capture evidence

- Freeze protocol/API version, reference deployment/build, base address, region, account/role, feature flags, clock, locale, and dataset.
- Prefer official versioned schemas and authorized request/response captures. Record method, path, query, headers, body bytes/encoding, status, response headers/body, latency context, and side effects.
- Inventory authentication, authorization, pagination, filtering, ordering, expansion, idempotency, concurrency, rate limits, retries, timeouts, redirects, webhooks, streaming, and version negotiation.
- Capture malformed, missing, duplicate, unauthorized, forbidden, not-found, conflict, rate-limited, dependency-failure, and server-failure behavior.
- Record persistence, transaction, cache, job, event, delivery, reconciliation, health, readiness, shutdown, configuration, and migration behavior when observable or documented.
- Never fuzz, load, or destructively probe the reference unless the exact environment and operation are authorized.

## Specify the clone

- Define every interface as bytes-on-the-wire where relevant: transport, method, path, encoding, schemas, required/optional fields, defaults, validation order, headers, status, and error envelope.
- Define missing-versus-null-versus-zero semantics, units, precision, rounding, time epoch/unit/time zone, deterministic ordering, cursor/offset semantics, and locale.
- Define identity, authorization scope, object ownership, tenant isolation, secret storage, rate limiting, and audit events.
- Define idempotency key scope/lifetime, duplicate behavior, transaction boundaries, concurrency control, retries, backoff, timeout, cancellation, and partial failure.
- Define persistence schema, indexes, constraints, migration/rollback, compatibility window, retention, deletion, cache invalidation, and repair behavior.
- Define event/webhook delivery, ordering, deduplication, signing, retry, terminal failure, and replay.
- Define configuration precedence, startup validation, health/readiness, logs, metrics, traces, graceful shutdown, resource limits, and deployment topology.

## Minimum MVP

Implement the smallest complete consumer workflow through real interface handling, business state, persistence, and response/error behavior. Include authorization and negative paths required by that workflow. Do not call a static mock server or hard-coded response table an MVP unless the requested product is explicitly a mock.

## Verify

| Contract | Required proof |
| --- | --- |
| Wire compatibility | Consumer/contract tests comparing exact schemas, statuses, headers, ordering, and error bodies |
| Validation/security | Missing/malformed/unauthorized/forbidden cases and ownership/tenant isolation |
| State and side effects | Transaction, persistence, duplicate, rollback, cache, job, and audit assertions |
| Pagination/order/time | Boundary fixtures proving cursors/offsets, stable ordering, units, zones, precision, and missing values |
| Concurrency/idempotency | Parallel and replay fixtures with exact final state and response behavior |
| Dependencies | Timeout, retry, partial failure, circuit/recovery, and terminal failure behavior |
| Lifecycle | Startup config rejection, health/readiness, shutdown/drain, migration, and restart recovery |
| Performance | Clone-only fixed workload, hardware, concurrency, duration, percentile, and resource budget |

Generate expected protocol values independently from the implementation under test. Use local or explicitly authorized test targets for negative, fuzz, and load exercises.

## Full-stack service proof

When a browser journey also exercises this API/service and persists state, load [Full-stack QA contract](full-stack-qa.md). The journey observes the real request and response at the transport boundary, then uses a repository-controlled API or integration probe to verify the named service/data postcondition independently of the UI. A `BIND-###` in `identity_bindings` captures the response value by JSON Pointer and binds a concrete additional-exchange path plus `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` contract pointers to the same `{binding_name}`. The canonical result's `captured_value_sha256` equals each consumer `observed_value_sha256`, proving the declared probes used the same captured identity without retaining it raw.

Keep every application-owned component `REAL` in the required lane. Identical complete core declarations may share a `service_id`; each applicable queue, cache, or worker instead has an explicit supporting-service declaration with readiness, assertion, proof artifact, and journey reference. The canonical result reports the exact supporting-service set and each entry must pass.

Only an external provider can be sandboxed, stubbed, or excluded with authority. Each non-excluded boundary records protocol, endpoint, `LOOPBACK` or `AUTHORIZED_SANDBOX` classification, bounded readiness, assertion, proof artifact, and a journey reference, and its result must be `PASS`; an exclusion is `NOT_APPLICABLE` and does not prove provider behavior. Pin the Playwright project and one controlled package value (`@playwright/test`, `playwright`, or `playwright-core`), then bind the primary exchange and every declared `additional_exchanges` wire observation to that same canonical result.

The indexed GATE and target CI job run the same repository-owned no-shell argv. The plan and GATE both put `ci.result_path` in `artifact_paths` and `fresh_artifact_paths`. Its repository wrapper preflights capability, startup, and readiness before behavioral execution: declared exit `7` is retained by `record-run` as `BLOCKED`, while a behavioral mismatch is `FAIL` with exit `5`. A non-blocked invocation that leaves a pre-existing required result unchanged is rejected as `RUN_ARTIFACT_STALE` with exit `4`. The skill never installs Playwright, server runtimes, or dependencies. Runtime validation checks contracts and allowed HTTP origins but does not execute readiness probes, parse the lockfile, prove package installation, parse CI YAML, or query hosted checks.

The latest linked `PASS` `RUN` and its matching canonical result prove the declared wire and service observations only. They do not prove unobserved handler branches, transaction constraints, background jobs, external providers, or production deployment. Retain those dimensions through repository-native tests or report them as exclusions, gaps, or blockers.
