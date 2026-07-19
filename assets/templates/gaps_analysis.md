---
schema_version: clone-gaps/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
reference_baseline: {{SOURCE_DESCRIPTION_YAML}}
clone_baseline: "[[REQUIRED: full commit SHA or exact working-tree identifier]]"
analysis_version: 1
document_state: draft
---

# Gap analysis — {{PRODUCT_NAME}}

## Current-truth basis

- Reference snapshot/artifact manifest: [[REQUIRED: immutable ID and path]]
- Reference capture environment/date: [[REQUIRED: ENV-### and ISO-8601 timestamp]]
- Clone repository/revision: [[REQUIRED: repository and full SHA or exact working-tree identifier]]
- Governing MVP contract: `clone_specification.md` version [[REQUIRED: integer/hash]]
- Acceptance evidence: `acceptance_matrix.md` revision [[REQUIRED: integer/hash]]
- Authority precedence: [[REQUIRED: ordered controlling artifacts]]
- Comparison procedure: [[REQUIRED: exact reproducible procedure]]
- NO-OPEN-GAPS: false

## Gap classification and lifecycle

- Classes: `MVP_BLOCKER`, `PARITY_GAP`, `QUALITY_GAP`, `EVIDENCE_GAP`.
- Statuses: `OPEN`, `BLOCKED`, `IN_PROGRESS`, `IMPLEMENTED`, `VERIFIED`, `DECLINED`.
- An MVP blocker prevents a verified-MVP verdict.
- An evidence gap remains blocked until target behavior is observed or pinned.
- Intentional absence of product code in `spec-only` mode is not a gap; planned MVP requirements remain `NOT_STARTED` in the acceptance matrix and build plan.

## Capability coverage

| Surface/capability ID | Reference locator | Clone locator | Coverage | Gap/exclusion ID | Evidence IDs |
| --- | --- | --- | --- | --- | --- |
| SURF-001 | [[REQUIRED: immutable evidence locator]] | [[REQUIRED: exact clone path/symbol/route or `missing`]] | [[REQUIRED: EQUIVALENT, MISSING, PARTIAL, DIVERGENT, EXCLUDED, or UNVERIFIED]] | [[REQUIRED: GAP-###, EXC-###, or `none`]] | [[REQUIRED: E-### list]] |

## Gap register

| Gap ID | Title | Class | Priority | Status | Dependencies | Source IDs | Implementation readiness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-001 | [[REQUIRED: observable discrepancy]] | [[REQUIRED: gap class]] | [[REQUIRED: P0, P1, P2, or P3 with impact in dossier]] | OPEN | [[REQUIRED: GAP-### list or `none`]] | [[REQUIRED: E/REQ/DEC IDs]] | [[REQUIRED: READY or BLOCKED]] |

## Dependency order

| Order | Gap IDs | Why this order | Entry condition | Exit evidence |
| --- | --- | --- | --- | --- |
| 1 | [[REQUIRED: GAP-### dependency-safe slice]] | [[REQUIRED: exact dependency/risk reason]] | [[REQUIRED: status/dependency condition]] | [[REQUIRED: AC/TEST/RUN IDs]] |

## GAP-001 — [[REQUIRED: observable discrepancy]]

### Classification

- Class: [[REQUIRED: MVP_BLOCKER, PARITY_GAP, QUALITY_GAP, or EVIDENCE_GAP]]
- Priority and impact: [[REQUIRED: P0-P3 plus concrete affected actor/workflow/outcome]]
- Status: OPEN
- Implementation readiness: [[REQUIRED: READY or BLOCKED]]
- Capability/requirement IDs: [[REQUIRED: SURF-### and REQ-### list]]
- Evidence/decision IDs: [[REQUIRED: E-### and/or DEC-### list]]
- Dependencies: [[REQUIRED: GAP-### list or `none`]]
- Reason deferred: [[REQUIRED: exact MVP boundary, blocker, or authority decision]]

### Current-state evidence and discrepancy

| Side | Preconditions/input | Exact observed behavior/state/side effects | Immutable locator | Reproduction |
| --- | --- | --- | --- | --- |
| Reference | [[REQUIRED: environment, actor, data, and state]] | [[REQUIRED: exact behavior]] | [[REQUIRED: E-### and artifact locator]] | [[REQUIRED: exact safe steps]] |
| Clone | [[REQUIRED: matching environment, actor, data, and state]] | [[REQUIRED: exact behavior or absence]] | [[REQUIRED: path/test/run locator]] | [[REQUIRED: exact steps/command]] |

Delta: [[REQUIRED: one sentence naming the exact observable difference]]

### Target behavior

| Gap requirement ID | Preconditions | Trigger/input | Required result | State/side effects | Error/boundary behavior |
| --- | --- | --- | --- | --- | --- |
| REQ-GAP-001-01 | [[REQUIRED: exact state]] | [[REQUIRED: exact action/input]] | [[REQUIRED: exact output]] | [[REQUIRED: exact mutations/effects]] | [[REQUIRED: enumerated outcomes]] |

### Constraints and applicability

| Surface | Exact contract or N/A with reason | Requirement IDs |
| --- | --- | --- |
| Domain/state rules | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| Storage/migration/rollback | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| API/protocol | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| UI/interaction/accessibility | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| CLI | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| Jobs/retries/idempotency/concurrency | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| Authentication/authorization/privacy | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| Configuration/defaults | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| Logging/metrics/tracing | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |
| Compatibility/performance | [[REQUIRED: exact contract or N/A — reason]] | [[REQUIRED: IDs]] |

### Scope and non-goals

- In scope: [[REQUIRED: exhaustive behavior and paths]]
- Non-goals: [[REQUIRED: exact exclusions; do not hide required parity]]
- Prohibited shortcuts: [[REQUIRED: mocks, hard-coding, skipped checks, or other forbidden approaches]]

### File-level change map

| Order | Operation | Exact path | Symbol/section | Required change | Requirement IDs |
| --- | --- | --- | --- | --- | --- |
| 1 | [[REQUIRED: create, modify, delete, rename, or generate]] | [[REQUIRED: exact path]] | [[REQUIRED: exact symbol/section]] | [[REQUIRED: deterministic change contract]] | [[REQUIRED: REQ-GAP-### IDs]] |

### Implementation sequence

| Step ID | Preconditions | Exact action | Paths/symbols | Postcondition | Proof |
| --- | --- | --- | --- | --- | --- |
| STEP-GAP-001-01 | [[REQUIRED: dependencies and state]] | [[REQUIRED: one exact action]] | [[REQUIRED: exact locations]] | [[REQUIRED: observable result]] | [[REQUIRED: test/command/artifact]] |

### Test specification

| Test ID | Test path | Layer | Fixture/setup | Exact action/input | Exact assertions | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| TEST-GAP-001-01 | [[REQUIRED: exact path]] | [[REQUIRED: test layer]] | [[REQUIRED: independent fixture]] | [[REQUIRED: exact action/input]] | [[REQUIRED: normal/boundary/negative/state assertions]] | [[REQUIRED: REQ-GAP-### IDs]] |

### Acceptance criteria

| AC ID | Binary condition | Verification command/procedure | Expected result | Evidence artifact | Requirement/test IDs |
| --- | --- | --- | --- | --- | --- |
| AC-GAP-001-01 | [[REQUIRED: atomic observable condition]] | [[REQUIRED: exact command or procedure]] | [[REQUIRED: exact exit/output/state]] | [[REQUIRED: stable future evidence path]] | [[REQUIRED: REQ/TEST IDs]] |

### Rollout, compatibility, and recovery

- Migration/deployment: [[REQUIRED: ordered procedure or N/A with exact reason]]
- Backward compatibility: [[REQUIRED: exact rule or N/A with exact reason]]
- Rollback trigger/procedure: [[REQUIRED: exact trigger, commands, and data handling]]
- Data repair/recovery: [[REQUIRED: exact procedure or N/A with exact reason]]
- Risks/mitigations: [[REQUIRED: concrete failure modes and controls]]

### Uncertainty and HALT ledger

| Decision ID | Material unknown/conflict | Evidence searched | Exact question | Authority | Impact | Resolution artifact |
| --- | --- | --- | --- | --- | --- | --- |
| GAPDEC-001 | [[REQUIRED: `none` for READY or exact blocker]] | [[REQUIRED: evidence IDs/paths]] | [[REQUIRED: `none` or one answerable question]] | [[REQUIRED: authority]] | [[REQUIRED: affected contract]] | [[REQUIRED: DEC-### path or `pending`]] |

### Closure evidence

- Implemented revision: [[REQUIRED: `not implemented` until code exists, then full SHA/diff ID]]
- Verification runs: [[REQUIRED: `none` until run, then RUN-### IDs]]
- Acceptance result: [[REQUIRED: NOT_RUN only while no immutable run exists; after execution PASS, FAIL, BLOCKED, or ERROR with AC/run IDs]]
- Residual deviations/new gaps: [[REQUIRED: GAP-### list or `none`]]

### Status history

| Timestamp | From | To | Evidence/reason | Authority |
| --- | --- | --- | --- | --- |
| [[REQUIRED: ISO-8601 timestamp]] | `new` | `OPEN` | [[REQUIRED: discrepancy evidence IDs]] | [[REQUIRED: actor/artifact]] |
