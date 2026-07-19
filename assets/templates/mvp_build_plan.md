---
schema_version: clone-mvp-plan/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
plan_version: 1
document_state: draft
---

# MVP build plan — {{PRODUCT_NAME}}

## Execution contract

- Objective: [[REQUIRED: exact MVP terminal condition and requirement IDs]]
- Repository root: `{{REPOSITORY_ROOT}}`
- Starting baseline: [[REQUIRED: full commit SHA or GREENFIELD-NO-COMMIT]]
- Governing artifacts: [[REQUIRED: ordered repository-relative paths]]
- Required tool/runtime versions: [[REQUIRED: exact versions]]
- Setup command: [[REQUIRED: exact command and working directory]]
- Allowed change fence: [[REQUIRED: exhaustive paths or precise path prefixes]]
- Forbidden changes: [[REQUIRED: exact exclusions]]
- Dirty-state policy: [[REQUIRED: preserve/stop rule]]
- Stop condition: [[REQUIRED: code/test/document state at handoff]]

## Dependency order

| Slice ID | Requirement IDs | Hard dependencies | Deliverable | Gate to next slice |
| --- | --- | --- | --- | --- |
| SLICE-001 | [[REQUIRED: REQ-### list]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: one complete vertical behavior]] | [[REQUIRED: exact test IDs/commands and result]] |

## File-level change map

| Order | Operation | Exact path | Symbol/section | Required change | Requirement IDs |
| --- | --- | --- | --- | --- | --- |
| 1 | [[REQUIRED: create, modify, delete, rename, or generate]] | [[REQUIRED: exact path]] | [[REQUIRED: exact existing symbol/section or new symbol]] | [[REQUIRED: deterministic change contract]] | [[REQUIRED: REQ-### list]] |

## Implementation sequence

| Step ID | Preconditions | Exact action | Paths/symbols | Postcondition | Proof |
| --- | --- | --- | --- | --- | --- |
| STEP-001 | [[REQUIRED: exact state and dependency IDs]] | [[REQUIRED: one implementable action]] | [[REQUIRED: exact paths/symbols]] | [[REQUIRED: observable code/data state]] | [[REQUIRED: test/command/artifact]] |

## Test specification

| Test ID | Test path | Layer | Fixture/setup | Exact action/input | Exact assertions | Requirement IDs |
| --- | --- | --- | --- | --- | --- | --- |
| TEST-001 | [[REQUIRED: exact path]] | [[REQUIRED: unit, integration, contract, e2e, visual, or manual]] | [[REQUIRED: independently constructed fixture]] | [[REQUIRED: exact action/input]] | [[REQUIRED: output, state, side effects, and prohibited effects]] | [[REQUIRED: REQ-### list]] |

## Gate commands

| Gate ID | Working directory | Exact command | Expected exit | Expected result/artifact | Blocking behavior |
| --- | --- | --- | --- | --- | --- |
| GATE-001 | [[REQUIRED: exact directory]] | [[REQUIRED: exact command]] | [[REQUIRED: integer]] | [[REQUIRED: exact summary/artifact]] | [[REQUIRED: stop rule]] |

## Migration, rollout, and rollback

- Data/schema migration: [[REQUIRED: ordered command/procedure or EXCLUDED with reason and DEC-###]]
- Backward compatibility: [[REQUIRED: exact compatibility window/rule or EXCLUDED with reason and DEC-###]]
- Deployment sequence: [[REQUIRED: ordered procedure or exact local-run boundary]]
- Rollback trigger and procedure: [[REQUIRED: exact trigger, command, and data handling]]
- Recovery validation: [[REQUIRED: exact command/procedure and result]]

## Non-goals and prohibited shortcuts

| Item | Reason/authority |
| --- | --- |
| [[REQUIRED: exact behavior or path not to change]] | [[REQUIRED: DEC-### or scope reason]] |

## HALT conditions

Stop and request a plan/spec revision when:

- a required path/symbol does not match the pinned baseline;
- implementation needs a public behavior, schema, dependency, security, or file-scope decision absent from governing artifacts;
- a hard dependency or required gate fails for a pre-existing reason;
- authorized evidence contradicts a requirement;
- the requested action crosses the allowed change fence or permitted target boundary.

## Completion record

| Item | Evidence |
| --- | --- |
| Implemented revision | [[REQUIRED: full commit SHA or exact working-tree diff identifier]] |
| Focused verification | [[REQUIRED: RUN-### IDs]] |
| Broad gates | [[REQUIRED: RUN-### IDs]] |
| MVP acceptance | [[REQUIRED: AC-### PASS list; every MVP AC required]] |
| Residual deviations | [[REQUIRED: GAP-### list or `none`]] |
