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

