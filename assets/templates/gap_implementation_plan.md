---
schema_version: clone-gap-plan/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
plan_version: 1
document_state: draft
---

# Gap implementation plan — {{PRODUCT_NAME}}

## Execution contract

- Objective and selected gaps: [[REQUIRED: exact GAP-### dependency-safe slice and terminal state]]
- Repository root: `{{REPOSITORY_ROOT}}`
- Starting branch/revision: [[REQUIRED: branch and full commit SHA or exact working-tree identifier]]
- Reference baseline: [[REQUIRED: immutable version/build/snapshot]]
- Gap-analysis version/hash: [[REQUIRED: version and SHA-256]]
- Authority precedence: [[REQUIRED: ordered artifact paths]]
- Required tool/runtime versions: [[REQUIRED: exact versions]]
- Setup/verification commands: [[REQUIRED: exact commands and working directories]]
- Allowed change fence: [[REQUIRED: exhaustive paths/path prefixes from gap dossiers]]
- Forbidden changes: [[REQUIRED: explicit scope exclusions]]
- Completion boundary: [[REQUIRED: exact code, test, evidence, and status state]]
- Stop condition: [[REQUIRED: handoff, PR, commit, or working-tree boundary; no implied merge/deploy]]

Verify the starting revision and protected hashes once before the first edit. After editing begins, compare the complete repository change set with that baseline; do not require authorized mutable files to retain pre-edit hashes.

## Pinned invariants

| Invariant ID | Exact contract | Source IDs | Violation test |
| --- | --- | --- | --- |
| INV-001 | [[REQUIRED: public behavior/data/security/compatibility invariant]] | [[REQUIRED: REQ/GAP/E/DEC IDs]] | [[REQUIRED: TEST-###]] |

## Dependencies and prerequisites

| Dependency ID | Kind | Required status/version | Satisfaction proof | Blocking behavior |
| --- | --- | --- | --- | --- |
| DEP-001 | [[REQUIRED: hard, ordering, external, or decision]] | [[REQUIRED: exact status/version]] | [[REQUIRED: command/artifact/evidence]] | [[REQUIRED: HALT condition]] |

## Requirement and change trace

| Gap requirement ID | Exact target behavior | Change-map rows | Step IDs | Test IDs | AC IDs |
| --- | --- | --- | --- | --- | --- |
| REQ-GAP-001-01 | [[REQUIRED: exact contract copied from gaps_analysis.md]] | [[REQUIRED: CHANGE-### list]] | [[REQUIRED: STEP-### list]] | [[REQUIRED: TEST-### list]] | [[REQUIRED: AC-### list]] |

## File-level change map

| Change ID | Order | Operation | Exact path | Symbol/section | Required change | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| CHANGE-001 | 1 | [[REQUIRED: create, modify, delete, rename, or generate]] | [[REQUIRED: exact path]] | [[REQUIRED: exact symbol/section]] | [[REQUIRED: deterministic change]] | [[REQUIRED: REQ-GAP-### list]] |

## Test-first execution sequence

| Step ID | Preconditions | Exact action | Paths/symbols | Expected red/green state | Proof/checkpoint |
| --- | --- | --- | --- | --- | --- |
| STEP-001 | [[REQUIRED: dependency and baseline state]] | [[REQUIRED: exact test or implementation action]] | [[REQUIRED: exact locations]] | [[REQUIRED: exact failure before fix or pass after fix]] | [[REQUIRED: command/artifact]] |

## Verification commands

| Gate ID | Working directory | Exact command/procedure | Expected exit/result | Evidence path | Requirement/AC IDs |
| --- | --- | --- | --- | --- | --- |
| GATE-001 | [[REQUIRED: exact path]] | [[REQUIRED: exact command/procedure]] | [[REQUIRED: exact exit and summary/state]] | [[REQUIRED: stable artifact path]] | [[REQUIRED: IDs]] |

## Rollout and recovery

- Migration order and compatibility window: [[REQUIRED: exact procedure or N/A with reason]]
- Deployment/activation order: [[REQUIRED: exact procedure or local-only boundary]]
- Rollback trigger and commands: [[REQUIRED: exact trigger and commands]]
- Data recovery/repair: [[REQUIRED: exact procedure or N/A with reason]]
- Post-rollback verification: [[REQUIRED: exact command/procedure and result]]

## Non-goals and prohibited work

| Item | Source/reason |
| --- | --- |
| [[REQUIRED: exact behavior/path not to change]] | [[REQUIRED: governing ID or scope reason]] |

## HALT ledger

Stop without guessing when a new fact changes public behavior, data shape, security, dependency/version, file scope, destructive operations, expected tests, or acceptance. Record:

| HALT ID | Trigger | Evidence checked | Exact decision needed | Impacted IDs | Resume artifact |
| --- | --- | --- | --- | --- | --- |
| HALT-001 | [[REQUIRED: exact trigger or `none at plan time`]] | [[REQUIRED: artifacts/IDs]] | [[REQUIRED: exact question or `none`]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: expected DEC-### path or `not applicable`]] |

## Completion record

| Item | Evidence |
| --- | --- |
| Implemented revision/diff | [[REQUIRED: full SHA/diff ID]] |
| Focused and broad verification | [[REQUIRED: RUN-### records with commands/results]] |
| Acceptance evidence | [[REQUIRED: AC-### PASS records and artifact paths]] |
| Residual deviations | [[REQUIRED: GAP-### IDs or `none`]] |
| Final gap transitions | [[REQUIRED: each GAP-### from-state, to-state, and evidence]] |
| Stop boundary reached | [[REQUIRED: exact boundary and proof]] |

Set `NO-OPEN-GAPS` from the final lifecycle state: `true` only when every retained gap is `VERIFIED` or `DECLINED`; otherwise `false`.
