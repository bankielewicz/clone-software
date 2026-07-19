---
schema_version: clone-spec/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_YAML}}
spec_version: 1
document_state: draft
---

# Clone specification — {{PRODUCT_NAME}}

## Authority and baseline

- Repository baseline: [[REQUIRED: full commit SHA or GREENFIELD-NO-COMMIT]]
- Reference baseline: [[REQUIRED: immutable version/build/snapshot and capture date]]
- Governing brief: `clone_brief.md`
- Evidence authority: `evidence_ledger.md`
- Authority precedence: [[REQUIRED: ordered controlling artifacts]]
- Runtime/dependency versions: [[REQUIRED: exact versions and lockfile policy]]

## Product contract

- Product outcome: [[REQUIRED: exact user-visible outcome]]
- Supported platforms: [[REQUIRED: exact browser/OS/device/runtime matrix]]
- Deployment topology: [[REQUIRED: processes, stores, integrations, and trust boundaries]]
- Startup entrypoint: [[REQUIRED: exact working directory and command]]
- MVP terminal condition: [[REQUIRED: binary completion statement referencing WF/REQ/AC IDs]]

## Actors and permissions

| Actor ID | Role | Authentication state | Permitted actions/data | Forbidden actions/data | Evidence/decision IDs |
| --- | --- | --- | --- | --- | --- |
| ACT-001 | [[REQUIRED: exact role]] | [[REQUIRED: auth/session state]] | [[REQUIRED: enumerated permissions]] | [[REQUIRED: enumerated denials]] | [[REQUIRED: E-### or DEC-###]] |

## MVP workflows

| Workflow ID | Actor IDs | Preconditions | Ordered transitions | Terminal state | Error/recovery requirements | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| WF-001 | [[REQUIRED: ACT-###]] | [[REQUIRED: exact starting state]] | [[REQUIRED: numbered state/action sequence]] | [[REQUIRED: observable and durable end state]] | [[REQUIRED: REQ-### list]] | [[REQUIRED: REQ-### list]] |

## Surface inventory

| Surface ID | Kind | Route/screen/command/endpoint/event | Actor IDs | Inputs | Outputs/state | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| SURF-001 | [[REQUIRED: UI, API, CLI, JOB, FILE, PROTOCOL, or PLATFORM]] | [[REQUIRED: exact locator/name]] | [[REQUIRED: ACT-###]] | [[REQUIRED: IF-### or exact input]] | [[REQUIRED: IF-###, DATA-###, or exact output]] | [[REQUIRED: REQ-### list]] |

## Behavioral requirements

<!-- Add one packet per requirement. Preserve IDs after publication. -->

### REQ-001 — [[REQUIRED: observable behavior title]]

- Truth basis: [[REQUIRED: VERIFIED or USER_PINNED]]
- Source IDs: [[REQUIRED: E-### and/or DEC-###]]
- Actor and preconditions: [[REQUIRED: ACT-### plus exact state]]
- Trigger/input: [[REQUIRED: event and IF-### or exact values]]
- Required behavior: [[REQUIRED: deterministic ordered behavior]]
- Output/state/side effects: [[REQUIRED: exact visible output, DATA-### transition, and external effects]]
- Validation and errors: [[REQUIRED: enumerated condition-to-outcome rules]]
- Authorization/privacy: [[REQUIRED: checks and prohibited disclosure/effects]]
- Concurrency/idempotency: [[REQUIRED: exact rule or EXCLUDED with reason and DEC-###]]
- Timing/retry/recovery: [[REQUIRED: units, limits, terminal behavior, or EXCLUDED with reason and DEC-###]]
- Compatibility/accessibility: [[REQUIRED: exact behavior or EXCLUDED with reason and DEC-###]]
- Acceptance IDs: [[REQUIRED: AC-### list]]
- Planned test IDs: [[REQUIRED: TEST-### list]]
- Implementation owners: [[REQUIRED: exact existing paths/symbols or exact new paths]]

## Interface contracts

| Interface ID | Consumer/provider | Input schema/encoding | Output schema/encoding | Errors/status/exits | Ordering/pagination/time/units | Version/compatibility | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| IF-001 | [[REQUIRED: actors/components]] | [[REQUIRED: exact schema]] | [[REQUIRED: exact schema]] | [[REQUIRED: exact error contract]] | [[REQUIRED: deterministic semantics]] | [[REQUIRED: exact version rule]] | [[REQUIRED: REQ-###]] |

## Data and state contracts

| Data ID | Owner | Fields/types/constraints | Lifecycle/transitions | Persistence/transaction | Migration/retention/deletion | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| DATA-001 | [[REQUIRED: owner and tenant scope]] | [[REQUIRED: exact schema and invariants]] | [[REQUIRED: states and allowed transitions]] | [[REQUIRED: store, transaction, and concurrency rules]] | [[REQUIRED: exact rules]] | [[REQUIRED: REQ-###]] |

## Security and privacy

| Boundary ID | Assets/trust boundary | Authentication | Authorization/isolation | Validation/secrets | Audit/privacy behavior | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-001 | [[REQUIRED: assets and boundary]] | [[REQUIRED: exact mechanism/session]] | [[REQUIRED: exact object/tenant rules]] | [[REQUIRED: validation and secret mechanism]] | [[REQUIRED: events, redaction, retention]] | [[REQUIRED: REQ-###]] |

## Non-functional contracts

| Contract ID | Dimension | Fixed environment/workload | Metric and limit | Verification method | Requirement IDs |
| --- | --- | --- | --- | --- | --- |
| NFR-001 | [[REQUIRED: accessibility, performance, reliability, compatibility, or operations]] | [[REQUIRED: exact environment and fixture]] | [[REQUIRED: numeric/binary limit]] | [[REQUIRED: command/procedure]] | [[REQUIRED: REQ-### or `cross-cutting`]] |

## Architecture and repository map

| Component | Exact path | Responsibility | Interfaces/data | Dependency/version | Requirement IDs |
| --- | --- | --- | --- | --- | --- |
| [[REQUIRED: component name]] | [[REQUIRED: verified existing path or exact new path]] | [[REQUIRED: bounded responsibility]] | [[REQUIRED: IF-### and DATA-###]] | [[REQUIRED: exact dependency/version or `none`]] | [[REQUIRED: REQ-###]] |

## Configuration and operations

- Configuration keys and precedence: [[REQUIRED: exact keys, types, defaults, source order, and invalid behavior]]
- Secret injection: [[REQUIRED: exact mechanism and redaction rule]]
- Schema migration and rollback: [[REQUIRED: exact commands and compatibility rule or EXCLUDED with DEC-###]]
- Health/readiness/shutdown: [[REQUIRED: exact signals/endpoints/timeouts or EXCLUDED with DEC-###]]
- Logs/metrics/traces: [[REQUIRED: exact events/fields/redaction or EXCLUDED with DEC-###]]
- Backup/recovery: [[REQUIRED: exact procedure and recovery objective or EXCLUDED with DEC-###]]

## MVP exclusions and gap mapping

| Exclusion ID | Exact excluded behavior | Reason/authority | Gap ID or permanent non-goal | Evidence/decision IDs |
| --- | --- | --- | --- | --- |
| EXC-001 | [[REQUIRED: exact behavior]] | [[REQUIRED: concrete reason and authority]] | [[REQUIRED: GAP-### or permanent non-goal]] | [[REQUIRED: E-### or DEC-###]] |

## Readiness result

- Unresolved MVP markers: [[REQUIRED: `none`]]
- UNKNOWN_BLOCKER items in MVP: [[REQUIRED: `none`]]
- Requirements without evidence/user pin: [[REQUIRED: `none`]]
- Requirements without AC and TEST mappings: [[REQUIRED: `none`]]
- Readiness decision: [[REQUIRED: READY or BLOCKED with exact IDs]]
