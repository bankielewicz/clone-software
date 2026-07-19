---
schema_version: clone-gaps/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_JSON}}
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
document_state: draft
---

# Gap analysis — {{PRODUCT_NAME}}

## Current-truth basis

- Reference baseline and capture plan: [[REQUIRED: BASE-### plus file revision/hash]]
- Clone repository/revision/diff: [[REQUIRED: exact identity]]
- Specification and acceptance revisions: [[REQUIRED: paths/revisions/hashes]]
- Comparison procedure and runs: [[REQUIRED: PAR/RUN IDs, or NOT_RUN only while no immutable RUN exists]]
- `NO-OPEN-GAPS`: false

## Classification and lifecycle

Classes are `MVP_BLOCKER`, `PARITY_GAP`, `QUALITY_GAP`, and `EVIDENCE_GAP`. States are `OPEN`, `BLOCKED`, `IN_PROGRESS`, `IMPLEMENTED`, `VERIFIED`, and `DECLINED`. Lifecycle changes are append-only events; current state is the highest valid sequence for the gap.

## Capability coverage

Every `SURF-###` and `WF-###` index record sets exactly one `attributes.disposition` value. `EQUIVALENT` links only to requirements and has a linked `PASS` parity or run record. `MISSING`, `PARTIAL`, and `DIVERGENT` link only to gaps and include evidence, parity, or run evidence. `EXCLUDED` links only to exclusions and an authority decision. `UNVERIFIED` links only to gaps whose class/state is `EVIDENCE_GAP`/`BLOCKED`.

| Surface/capability | Reference locator | Clone locator | Coverage | Gap/exclusion | Evidence/run IDs |
| --- | --- | --- | --- | --- | --- |
| SURF-001 | [[REQUIRED: E/ART locator]] | [[REQUIRED: path/symbol/route or `missing`]] | [[REQUIRED: EQUIVALENT, MISSING, PARTIAL, DIVERGENT, EXCLUDED, or UNVERIFIED]] | [[REQUIRED: GAP/EXC ID or `none`]] | [[REQUIRED: IDs]] |

## Gap register

| Gap ID | Observable delta | Class/priority | State/sequence | Dependencies | Source IDs | Readiness |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-001 | [[REQUIRED: exact reference-versus-clone difference]] | [[REQUIRED: class and P0-P3 impact]] | OPEN / 1 | [[REQUIRED: GAP-### list or `none`]] | [[REQUIRED: E/REQ/PAR/DEC IDs]] | [[REQUIRED: READY or BLOCKED]] |

## Dependency order

| Order | Gap IDs | Entry condition | Exit evidence | Reason |
| --- | --- | --- | --- | --- |
| 1 | [[REQUIRED: dependency-safe slice]] | [[REQUIRED: exact state]] | [[REQUIRED: AC/TEST/RUN IDs]] | [[REQUIRED: dependency/risk rule]] |

## GAP-001 dossier — [[REQUIRED: observable delta]]

The tables below are the human-readable contract. The same gap MUST embed a marker-free object copied from `assets/templates-v2/gap_dossier.json` at `clone_index.json` `GAP-001.attributes.dossier`. Every ID, path, symbol, command, disposition, and closure field MUST agree. `gap-plan` fails when the machine dossier is absent, ambiguous, untraced, outside its path fence, or inconsistent with repository state.

### Classification and evidence

- Class, priority, impact: [[REQUIRED: exact values and affected actor/workflow]]
- Current state and latest event: [[REQUIRED: state, sequence, and event ID]]
- Evidence/requirements/comparisons: [[REQUIRED: E/REQ/PAR/DEC IDs]]
- Dependencies and deferral authority: [[REQUIRED: IDs and exact reason]]

### Current and target behavior

| Side | Preconditions/input | Exact behavior/state/effects | Locator/reproduction |
| --- | --- | --- | --- |
| Reference | [[REQUIRED: exact setup]] | [[REQUIRED: observed contract]] | [[REQUIRED: immutable evidence and safe steps]] |
| Clone | [[REQUIRED: matching setup]] | [[REQUIRED: behavior or absence]] | [[REQUIRED: path/run and command]] |
| Target | [[REQUIRED: exact setup]] | [[REQUIRED: normative output, errors, state, and prohibited effects]] | [[REQUIRED: REQ-GAP-### IDs]] |

### Change, test, and acceptance contract

| ID | Exact path/action | Deterministic contract | Proof/expected result |
| --- | --- | --- | --- |
| CHANGE-GAP-001-01 | [[REQUIRED: operation, path, symbol]] | [[REQUIRED: exact change]] | [[REQUIRED: requirement IDs]] |
| TEST-GAP-001-01 | [[REQUIRED: test path and fixture]] | [[REQUIRED: normal/boundary/negative assertions]] | [[REQUIRED: command and red/green result]] |
| AC-GAP-001-01 | [[REQUIRED: one binary condition]] | [[REQUIRED: tolerance and prohibited effects]] | [[REQUIRED: procedure and artifact]] |

### Security, rollout, and non-goals

- Security/data/interface/compatibility effects: [[REQUIRED: exact contracts or NOT_APPLICABLE with decision]]
- Migration, activation, rollback, and recovery: [[REQUIRED: exact procedure or NOT_APPLICABLE with decision]]
- Non-goals and prohibited shortcuts: [[REQUIRED: exhaustive list]]
- Risks and mitigations: [[REQUIRED: concrete failure/control pairs]]

### Blocker or closure

- Exact unresolved question: [[REQUIRED: `none` for READY or one answerable question]]
- Implemented revision and runs: [[REQUIRED: `not implemented`; after work, exact revision/RUN IDs]]
- Acceptance and residual deviations: [[REQUIRED: NOT_RUN while no immutable RUN exists; after work, PASS/FAIL/BLOCKED/ERROR and GAP IDs]]

For an `EVIDENCE_GAP`, omit the ready dossier, set status/readiness to `BLOCKED`, and put exactly `missing_evidence`, non-empty `investigations`, one `resolution_question`, and `authority` in `GAP-###.attributes.blocker`.
