---
schema_version: clone-gap-plan/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
repository_root: "{{REPOSITORY_ROOT}}"
document_state: draft
---

# Gap implementation plan — {{PRODUCT_NAME}}

## Execution contract

- Machine dossier authority: [[REQUIRED: `clone_index.json` GAP-### `attributes.dossier`, schema `clone-gap-dossier/v2`, and locator/hash evidence; every table below agrees exactly]]
- Selected dependency-safe gaps and terminal states: [[REQUIRED: GAP-### list and exact outcomes]]
- Starting branch/revision/diff hash: [[REQUIRED: exact identity]]
- Gap register revision/hash and latest event IDs: [[REQUIRED: exact values]]
- Governing artifacts and versions: [[REQUIRED: ordered paths]]
- Allowed fence, forbidden work, dirty-state rule: [[REQUIRED: exhaustive contract]]
- Tool/runtime versions and setup: [[REQUIRED: exact versions/commands]]
- Stop boundary: [[REQUIRED: code, evidence, event, commit/PR, and no-merge state]]

## Pinned invariants and dependencies

| ID | Kind | Exact contract/status | Source/proof | Violation/HALT condition |
| --- | --- | --- | --- | --- |
| INV-001 | invariant | [[REQUIRED: behavior/data/security/compatibility rule]] | [[REQUIRED: E/REQ/DEC/GAP IDs]] | [[REQUIRED: TEST-### or exact condition]] |
| DEP-001 | dependency | [[REQUIRED: exact state/version]] | [[REQUIRED: command/artifact]] | [[REQUIRED: stop rule]] |

## Requirement and file trace

| Gap requirement | Target behavior | Change IDs | Step IDs | Test IDs | AC IDs |
| --- | --- | --- | --- | --- | --- |
| REQ-GAP-001-01 | [[REQUIRED: exact contract copied from dossier]] | [[REQUIRED: CHANGE IDs]] | [[REQUIRED: STEP IDs]] | [[REQUIRED: TEST IDs]] | [[REQUIRED: AC IDs]] |

| Change ID | Order/operation | Exact path/symbol | Deterministic change | Requirement IDs |
| --- | --- | --- | --- | --- |
| CHANGE-001 | [[REQUIRED: integer and operation]] | [[REQUIRED: verified or explicitly new location]] | [[REQUIRED: exact contract]] | [[REQUIRED: IDs]] |

## Test-first execution sequence

| Step ID | Preconditions | Exact action | Expected red/green state | Proof/checkpoint |
| --- | --- | --- | --- | --- |
| STEP-001 | [[REQUIRED: dependencies/state]] | [[REQUIRED: command or edit at exact locations]] | [[REQUIRED: discriminating result]] | [[REQUIRED: artifact/command]] |

## Verification gates

| Gate ID | Working directory | Exact command/procedure | Expected exit/result | Evidence path | Covered IDs |
| --- | --- | --- | --- | --- | --- |
| GATE-001 | [[REQUIRED: exact path]] | [[REQUIRED: executable and arguments]] | [[REQUIRED: integer/result]] | [[REQUIRED: stable path]] | [[REQUIRED: REQ/AC/SEC/PAR IDs]] |

## Rollout, rollback, recovery, and non-goals

- Migration and activation order: [[REQUIRED: exact procedure or NOT_APPLICABLE decision]]
- Compatibility and rollback: [[REQUIRED: exact window, trigger, commands, and data handling]]
- Recovery proof: [[REQUIRED: exact command/procedure/result]]
- Non-goals and prohibited shortcuts: [[REQUIRED: exhaustive list]]

## HALT and completion records

| Record | Exact trigger/current truth | Evidence/decision |
| --- | --- | --- |
| HALT-001 | [[REQUIRED: `none at plan time` or exact trigger/question]] | [[REQUIRED: searched artifacts and expected decision path]] |
| Implemented revision | [[REQUIRED: `not implemented` until code exists]] | [[REQUIRED: exact diff/commit when implemented]] |
| Runs and acceptance | [[REQUIRED: `none` and NOT_RUN only while no immutable RUN exists]] | [[REQUIRED: RUN/AC IDs after execution; run result PASS, FAIL, BLOCKED, or ERROR]] |
| Gap transitions | [[REQUIRED: no event until verified transition]] | [[REQUIRED: event IDs/hash chain after transition]] |
| Stop boundary | [[REQUIRED: exact required state]] | [[REQUIRED: proof when reached]] |
