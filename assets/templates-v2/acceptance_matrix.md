---
schema_version: clone-acceptance/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
document_state: draft
---

# Acceptance matrix — {{PRODUCT_NAME}}

## Acceptance criteria

| AC ID | Preconditions | One action/event | Required output/state | Prohibited effects | Tolerance | Requirement/evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| AC-001 | [[REQUIRED: exact actor/data/state/environment]] | [[REQUIRED: one reproducible action]] | [[REQUIRED: binary observable result]] | [[REQUIRED: exact prohibited effects or `none`]] | [[REQUIRED: exact value or `zero`]] | [[REQUIRED: REQ/E IDs]] |

## Test and oracle mapping

| Test ID | Layer/path | Independent fixture | Exact command/procedure | Exact assertions | AC IDs | Oracle/comparison IDs |
| --- | --- | --- | --- | --- | --- | --- |
| TEST-001 | [[REQUIRED: layer and exact path]] | [[REQUIRED: independently derived setup]] | [[REQUIRED: exact command/steps]] | [[REQUIRED: normal, boundary, and negative outcomes]] | [[REQUIRED: AC-### list]] | [[REQUIRED: E/ART/PAR IDs]] |

## Requirement verification

| Requirement ID | Evidence/pin | AC/test IDs | Implementation locator | Status | Run IDs | Residual gap |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | [[REQUIRED: E-### or DEC-###]] | [[REQUIRED: AC/TEST IDs]] | [[REQUIRED: path/symbol or `not implemented`]] | [[REQUIRED: NOT_STARTED, IMPLEMENTED_UNVERIFIED, VERIFIED, or BLOCKED]] | [[REQUIRED: RUN-### list or `none`]] | [[REQUIRED: GAP-### or `none`]] |

## Parity and assurance gates

| Gate ID | Kind | Covered IDs | Required result | Observed result | Run/evidence IDs | State |
| --- | --- | --- | --- | --- | --- | --- |
| GATE-001 | [[REQUIRED: parity, security, provenance, accessibility, build, or repository]] | [[REQUIRED: IDs]] | [[REQUIRED: exact threshold/result]] | [[REQUIRED: NOT_RUN while no RUN exists; otherwise PASS, FAIL, BLOCKED, or ERROR]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: NOT_RUN, PASS, FAIL, BLOCKED, ERROR, or NOT_APPLICABLE]] |

## Verification runs

| Run ID | Revision/environment | Exact command/procedure | Exit/result | Artifact IDs | Covered IDs | Timestamp |
| --- | --- | --- | --- | --- | --- | --- |
| RUN-001 | [[REQUIRED: revision and ENV-###]] | [[REQUIRED: exact command/steps]] | [[REQUIRED: integer and PASS, FAIL, BLOCKED, or ERROR]] | [[REQUIRED: ART-RUN-###-## or other governed ART IDs, or `none`]] | [[REQUIRED: REQ/AC/TEST/PAR/SEC IDs]] | [[REQUIRED: ISO-8601]] |

## MVP verdict

- Verdict: [[REQUIRED: HOLD or VERIFIED]]
- Verified requirement IDs: [[REQUIRED: list or `none`]]
- Blocking requirement/gap/finding IDs: [[REQUIRED: list or `none`]]
- Verdict revision and runs: [[REQUIRED: exact revision and RUN-### list or `none`]]
