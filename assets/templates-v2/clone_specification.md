---
schema_version: clone-spec/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_slug: "{{PRODUCT_SLUG}}"
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_JSON}}
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
repository_root: "{{REPOSITORY_ROOT}}"
document_state: draft
---

# Clone specification — {{PRODUCT_NAME}}

## Authority and baseline

- Authority order: [[REQUIRED: ordered governing paths]]
- Reference baseline: [[REQUIRED: BASE-###, immutable version, and evidence IDs]]
- Repository baseline: [[REQUIRED: revision/diff hash or GREENFIELD-NO-COMMIT]]
- Applicable playbooks and decisions: [[REQUIRED: reference filenames and DEC/ADR IDs]]

## Product contract

- Purpose and intended users: [[REQUIRED: exact outcome and ACT-### list]]
- MVP terminal condition: [[REQUIRED: binary completion statement and REQ-### list]]
- Supported platforms/deployment boundary: [[REQUIRED: exact matrix/topology]]
- Explicit non-goals: [[REQUIRED: EXC-### and GAP-### list]]

## Actors, trust boundaries, and permissions

| Actor ID | Role/identity | Trust boundary | Allowed operations | Denied operations | Evidence/decision IDs |
| --- | --- | --- | --- | --- | --- |
| ACT-001 | [[REQUIRED: exact role]] | [[REQUIRED: boundary]] | [[REQUIRED: operations/resources]] | [[REQUIRED: negative contract]] | [[REQUIRED: E/DEC IDs]] |

## Workflows and state machines

| Workflow ID | Preconditions | Ordered actions/events | States/transitions | Success and side effects | Errors/cancel/retry/recovery | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| WF-001 | [[REQUIRED: exact state]] | [[REQUIRED: numbered sequence]] | [[REQUIRED: deterministic transitions]] | [[REQUIRED: output and persisted/external effects]] | [[REQUIRED: enumerated outcomes]] | [[REQUIRED: REQ-### list]] |

## Surface and interface contracts

| Interface ID | Surface/entry | Input and validation | Output/error | Ordering/time/precision | Auth/effects | Evidence/requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| IF-001 | [[REQUIRED: exact route, screen, command, endpoint, symbol, protocol, or device entry]] | [[REQUIRED: schema, defaults, validation order]] | [[REQUIRED: exact observable contract]] | [[REQUIRED: deterministic rules]] | [[REQUIRED: permissions and side effects]] | [[REQUIRED: E/REQ IDs]] |

## Behavioral requirements

| Requirement ID | Normative contract | Source | Workflow/interface | Acceptance IDs | Gap/exclusion |
| --- | --- | --- | --- | --- | --- |
| REQ-001 | [[REQUIRED: one testable MUST/MUST NOT statement]] | [[REQUIRED: E-### or DEC-###]] | [[REQUIRED: WF/IF IDs]] | [[REQUIRED: AC-### list]] | [[REQUIRED: GAP/EXC ID or `none`]] |

## Data and state contracts

| Data ID | Owner/lifecycle | Schema and constraints | Persistence/concurrency | Migration/retention/deletion | Requirements |
| --- | --- | --- | --- | --- | --- |
| DATA-001 | [[REQUIRED: owner and lifecycle]] | [[REQUIRED: types, units, null/missing/zero, constraints]] | [[REQUIRED: storage, transactions, conflicts]] | [[REQUIRED: exact procedures]] | [[REQUIRED: REQ-### list]] |

## Security, privacy, and provenance

- Threat/control contract: [[REQUIRED: THREAT/CTRL IDs or exact NOT_APPLICABLE decision]]
- Authentication, authorization, isolation, and audit: [[REQUIRED: exact contracts]]
- Secret, privacy, retention, and redaction rules: [[REQUIRED: exact contracts]]
- Dependency, artifact, license, SBOM, and build-provenance rules: [[REQUIRED: provenance IDs and gates]]

## Non-functional and operational contracts

| Area | Exact contract/budget | Measurement environment/procedure | Requirement/decision IDs |
| --- | --- | --- | --- |
| Accessibility | [[REQUIRED: standard/criteria or exact exclusion]] | [[REQUIRED: automated and manual proof]] | [[REQUIRED: IDs]] |
| Performance/capacity | [[REQUIRED: metric, percentile, load, and limit or exclusion]] | [[REQUIRED: fixed environment]] | [[REQUIRED: IDs]] |
| Reliability/recovery | [[REQUIRED: timeout, retry, idempotency, backup, restore, rollback]] | [[REQUIRED: exact failure exercises]] | [[REQUIRED: IDs]] |
| Observability/configuration | [[REQUIRED: logs, metrics, traces, health, config precedence]] | [[REQUIRED: exact checks]] | [[REQUIRED: IDs]] |
| Compatibility/deployment | [[REQUIRED: versions, packaging, migration window, topology]] | [[REQUIRED: exact matrix/checks]] | [[REQUIRED: IDs]] |

## Architecture and repository map

- Architecture decisions: [[REQUIRED: ADR-### list]]
- Components and dependency direction: [[REQUIRED: exact names and boundaries]]
- Repository paths and entry points: [[REQUIRED: verified existing paths or explicitly new paths]]
- Scaffold disposition: [[REQUIRED: one audited profile ID (static-web-esm, python-src, typescript-src, or rust-crate) plus STACK-###, or brownfield not-applicable]]

## Readiness result

| Gate | Result | Evidence/blocker |
| --- | --- | --- |
| Every MVP requirement has evidence or user pin | [[REQUIRED: PASS or HOLD]] | [[REQUIRED: IDs]] |
| Every MVP requirement maps to acceptance and test | [[REQUIRED: PASS or HOLD]] | [[REQUIRED: IDs]] |
| Architecture, security, data, dependency, and file contracts are pinned | [[REQUIRED: PASS or HOLD]] | [[REQUIRED: IDs]] |
| Capture, parity, scaffold, and assurance applicability is resolved | [[REQUIRED: PASS or HOLD]] | [[REQUIRED: IDs]] |
| Build readiness verdict | [[REQUIRED: READY or HOLD]] | [[REQUIRED: exact reason/IDs]] |
