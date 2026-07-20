# Web application and SaaS playbook

Use this playbook when the browser product is authenticated, stateful, role-based, multi-user, tenant-aware, or subscription-backed.

## Capture evidence

- Freeze reference build/date, browser, role, tenant, region, feature flags, account state, and seed dataset.
- Inventory actors, roles, tenant boundaries, invitations, onboarding, authentication, session expiry, recovery, and authorization failures.
- Capture complete stateful journeys, not isolated screens. Record preconditions, actions, requests, state mutations, visible results, refresh behavior, relogin behavior, and cross-user effects.
- Inventory routes, overlays, background jobs, notifications, exports/imports, search/filter/sort, pagination, bulk actions, audit events, and integrations.
- Observe loading, empty, invalid, forbidden, conflict, rate-limited, dependency-failure, partial-success, retry, cancellation, and recovery states.
- Use synthetic accounts and records. Do not capture other users' or tenants' data.

## Specify the clone

- Define the actor/permission matrix and object ownership rules. State tenant scoping on reads, writes, background work, logs, caches, exports, and notifications.
- Define each journey as a state machine with exact guards, transitions, persistence, concurrency outcome, errors, recovery, and audit behavior.
- Define UI route, component, form, accessibility, responsive, optimistic/pessimistic update, cache invalidation, and refresh/relogin behavior.
- Define API/service contracts using the API playbook when the browser consumes or exposes stable interfaces.
- Define data entities, constraints, indexes, transactions, migrations, retention, deletion, seed data, and import/export formats.
- Define session, CSRF, CORS, authorization, secret, upload, validation, rate-limit, and privacy contracts.
- Define background job delivery, idempotency, ordering, retry, dead-letter, and user-visible status behavior.
- Treat billing, email, identity providers, analytics, and other external services as real, sandboxed, explicitly stubbed, or excluded. Never present a stub as live behavior.

## Minimum MVP

Include one complete value loop per primary actor, real persistence, required authentication/authorization, validation, failure behavior, and a reproducible local or authorized test deployment. Multi-tenancy is inside the MVP only when the selected journey depends on it; if included, isolation tests are mandatory.

## Verify

| Contract | Required proof |
| --- | --- |
| Golden journeys | End-to-end tests from clean seed through persisted observable completion |
| State/persistence | Create, refresh, relogin, update, delete, conflict, and recovery assertions |
| Roles/tenants | Positive and negative permission matrix plus cross-tenant isolation probes against the clone |
| Validation/errors | Field, object, dependency, partial-failure, rate-limit, and retry states |
| Concurrency | Named simultaneous operations with deterministic conflict/idempotency outcomes |
| UI/accessibility | Route, focus, keyboard, responsive, loading, empty, error, and visual-state checks |
| Jobs/integrations | Delivery, duplicate, ordering, retry, terminal failure, and sandbox/stub labelling checks |
| Operations | Migration, health, structured logs, backup/recovery, and deployment smoke checks when in scope |

Do not use UI snapshots alone as proof of state, isolation, or backend behavior.

## Route browser-to-persistence QA

When a selected journey crosses browser UI, a real application request and response, an application-owned service postcondition, and persisted state after reload, relogin, or restart, load [Full-stack QA contract](full-stack-qa.md) and add the optional `full_stack_qa_plan.json`. Use ordinary web capture and dimension-specific parity when any of those four layers is absent.

The required lane declares application-owned frontend, mid-tier, backend, and persistence roles as `REAL`; identical complete core declarations may share a `service_id`. It MUST NOT intercept or replace an owned API or database. Declare every applicable queue, cache, or worker as a distinct `REAL` supporting service with readiness, assertion, artifact, and journey bindings; the canonical result reports the exact supporting-service set and each entry must pass.

Only an external dependency can be sandboxed, stubbed, or excluded, and every disposition has an authority decision. Each non-excluded boundary records protocol, endpoint, `LOOPBACK` or `AUTHORIZED_SANDBOX` classification, bounded readiness, assertion, proof artifact, and a journey reference, and its canonical-result entry must be `PASS`; an exclusion yields `NOT_APPLICABLE` and proves no provider behavior.

Pin the target repository's existing controlled Playwright package (`@playwright/test`, `playwright`, or `playwright-core`), declared version, browser, project, configuration, lockfile, test, CI workflow, indexed GATE, and canonical result path. The runtime hashes but does not parse the lockfile or prove the package is installed; the repository wrapper performs that preflight. The canonical result binds that project and every primary and `additional_exchanges` wire observation. Each journey also declares `identity_bindings`: a `BIND-###` source captures one response value, while concrete `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` pointers contain the same `{binding_name}`; the result's `captured_value_sha256` equals each consumer `observed_value_sha256`.

The plan and indexed GATE put `ci.result_path` in `artifact_paths` and `fresh_artifact_paths`. The repository GATE wrapper preflights capability, startup, and readiness before behavior: it exits declared code `7` for `record-run` to retain as `BLOCKED`, while a behavioral mismatch is `FAIL` with exit `5`. A non-blocked invocation that leaves a pre-existing result unchanged is rejected as `RUN_ARTIFACT_STALE` with exit `4`. The skill never installs Playwright or application services; its validator does not execute readiness probes, parse CI YAML, or query hosted checks. `build-ready` or `enhancement-ready` validates the contract before execution; `verified-mvp` or `verified-enhancement` requires the latest linked `PASS` `RUN` and matching parsed result for every journey.

A passing journey proves only the declared UI action, observed request and response, named API or data postcondition, persistence event, and retained environment. It does not prove unobserved mid-tier control flow, database constraints, jobs, external provider behavior, production deployment, or an undeclared browser environment.
