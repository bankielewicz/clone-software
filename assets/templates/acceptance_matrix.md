---
schema_version: clone-acceptance/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
document_state: draft
---

# Acceptance matrix — {{PRODUCT_NAME}}

## Acceptance criteria

| AC ID | Requirement IDs | Evidence/decision IDs | Preconditions | Action/event | Exact expected output/state | Prohibited side effects | Tolerance | Test IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-001 | [[REQUIRED: REQ-### list]] | [[REQUIRED: E-### or DEC-### list]] | [[REQUIRED: exact environment, actor, data, and state]] | [[REQUIRED: one action/event]] | [[REQUIRED: binary observable result]] | [[REQUIRED: exact forbidden effects or `none`]] | [[REQUIRED: numeric tolerance or `exact`]] | [[REQUIRED: TEST-### list]] |

## Requirement verification

<!-- Status: NOT_STARTED, IMPLEMENTED_UNVERIFIED, VERIFIED, or BLOCKED. -->

| Requirement ID | Implementation locator | AC IDs | Test IDs | Status | Run IDs | Deviation/gap IDs |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | [[REQUIRED: exact path:symbol/line or generated artifact]] | [[REQUIRED: AC-### list]] | [[REQUIRED: TEST-### list]] | [[REQUIRED: status]] | [[REQUIRED: RUN-### list or `none`]] | [[REQUIRED: GAP-### list or `none`]] |

## Verification runs

| Run ID | Baseline revision | Date/environment | Working directory | Exact command/procedure | Exit/result | Output/artifact path | Test/AC IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RUN-001 | [[REQUIRED: full commit SHA or exact working-tree identifier]] | [[REQUIRED: ISO-8601 timestamp and environment ID]] | [[REQUIRED: exact path]] | [[REQUIRED: exact command or numbered manual procedure]] | [[REQUIRED: exit code and exact result]] | [[REQUIRED: stable evidence path]] | [[REQUIRED: TEST-### and AC-### list]] |

## MVP verdict

- Reference baseline: [[REQUIRED: immutable version/build/snapshot]]
- Clone baseline: [[REQUIRED: full commit SHA or exact working-tree identifier]]
- Verified requirements: [[REQUIRED: REQ-### list]]
- Non-verified MVP requirements: [[REQUIRED: `none` or REQ-### list]]
- Skipped/unavailable checks: [[REQUIRED: `none` or exact check, reason, and impact]]
- Verdict: [[REQUIRED: VERIFIED_MVP or HOLD]]
