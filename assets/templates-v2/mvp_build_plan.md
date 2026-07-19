---
schema_version: clone-mvp-plan/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
repository_root: "{{REPOSITORY_ROOT}}"
document_state: draft
---

# MVP build plan — {{PRODUCT_NAME}}

## Execution contract

- Objective and requirement IDs: [[REQUIRED: exact terminal condition and REQ-### list]]
- Starting revision/state: [[REQUIRED: full SHA plus diff hash or GREENFIELD-NO-COMMIT]]
- Governing artifacts in authority order: [[REQUIRED: exact paths]]
- Tool/runtime versions: [[REQUIRED: exact versions]]
- Allowed change fence and dirty-state rule: [[REQUIRED: exhaustive paths and preserve/stop behavior]]
- Forbidden work: [[REQUIRED: exact behavior/paths/actions]]
- Stop boundary: [[REQUIRED: exact code, evidence, commit/PR, and no-merge boundary]]

## Scaffold and dependencies

| ID | Kind | Exact version/scaffold | Purpose | Integrity/license proof | Entry/stop condition |
| --- | --- | --- | --- | --- | --- |
| DEP-001 | [[REQUIRED: tool, package, service, decision, or scaffold]] | [[REQUIRED: pinned value]] | [[REQUIRED: one purpose]] | [[REQUIRED: locator/hash/license or N/A reason]] | [[REQUIRED: exact condition]] |

## Dependency-ordered slices

| Slice ID | Requirements | Dependencies | Deliverable | Gate to next slice |
| --- | --- | --- | --- | --- |
| SLICE-001 | [[REQUIRED: REQ-### list]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: one complete vertical behavior]] | [[REQUIRED: TEST/AC/GATE IDs and result]] |

## File-level change map

| Change ID | Order | Operation | Exact path | Symbol/section | Deterministic change | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| CHANGE-001 | 1 | [[REQUIRED: create, modify, delete, rename, or generate]] | [[REQUIRED: repository-relative path]] | [[REQUIRED: verified or explicitly new symbol]] | [[REQUIRED: exact contract]] | [[REQUIRED: REQ-### list]] |

## Test-first execution

| Step ID | Preconditions | Exact action | Paths/symbols | Expected red/green state | Proof |
| --- | --- | --- | --- | --- | --- |
| STEP-001 | [[REQUIRED: state/dependencies]] | [[REQUIRED: one action]] | [[REQUIRED: exact locations]] | [[REQUIRED: discriminating failure/pass]] | [[REQUIRED: command/artifact]] |

## Gate commands

| Gate ID | Working directory | Exact argv/command | Expected exit/result | Evidence path | Covered IDs |
| --- | --- | --- | --- | --- | --- |
| GATE-001 | [[REQUIRED: exact path]] | [[REQUIRED: executable and arguments]] | [[REQUIRED: integer and exact result]] | [[REQUIRED: stable path]] | [[REQUIRED: REQ/AC/SEC/PAR IDs]] |

## Rollout, rollback, and recovery

- Migration/activation order: [[REQUIRED: exact procedure or EXCLUDED with DEC-###]]
- Compatibility window: [[REQUIRED: exact versions/time or EXCLUDED with DEC-###]]
- Rollback trigger and procedure: [[REQUIRED: trigger, commands, and state handling]]
- Recovery and post-rollback proof: [[REQUIRED: exact procedure/result]]

## HALT conditions

Stop when evidence contradicts the contract, a pinned path/symbol/dependency is absent, a security/data/public-shape decision is missing, a required gate has an unexplained pre-existing failure, or work would cross the allowed fence. Record the exact blocked artifact and decision.

## Completion record

| Item | Current truth/evidence |
| --- | --- |
| Implemented revision/diff | [[REQUIRED: `not implemented` until code exists]] |
| Focused/broad runs | [[REQUIRED: `none` until run, then RUN-### list]] |
| Acceptance result | [[REQUIRED: NOT_RUN while no RUN exists; after execution PASS, FAIL, BLOCKED, or ERROR plus AC/RUN IDs]] |
| Assurance/parity result | [[REQUIRED: NOT_RUN or NOT_APPLICABLE before execution; after execution PASS, FAIL, BLOCKED, or ERROR plus IDs]] |
| Residual gaps | [[REQUIRED: GAP-### list or `none`]] |
| Stop boundary reached | [[REQUIRED: exact proof]] |
