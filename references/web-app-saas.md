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

