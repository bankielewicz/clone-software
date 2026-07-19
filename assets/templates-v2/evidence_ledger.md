---
schema_version: clone-evidence/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_JSON}}
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
document_state: draft
---

# Evidence ledger — {{PRODUCT_NAME}}

## Capture environments

| Environment ID | Reference/build | Platform and configuration | Actor/data/state | Time/locale | Authorization |
| --- | --- | --- | --- | --- | --- |
| ENV-001 | [[REQUIRED: immutable baseline]] | [[REQUIRED: exact versions/settings]] | [[REQUIRED: exact preconditions]] | [[REQUIRED: clock, zone, and locale]] | [[REQUIRED: authority record]] |

## Evidence records

Truth labels are `VERIFIED`, `USER_PINNED`, `INFERRED`, and `UNKNOWN_BLOCKER`.

| Evidence ID | Truth | Source and retrieval | Preconditions/action | Exact observation | Artifact IDs | Captured at |
| --- | --- | --- | --- | --- | --- | --- |
| E-001 | [[REQUIRED: truth label]] | [[REQUIRED: immutable locator and method]] | [[REQUIRED: state plus safe steps]] | [[REQUIRED: observable fact only]] | [[REQUIRED: human ART-### or generated scoped ART IDs, or `none`]] | [[REQUIRED: ISO-8601]] |

## Surface and workflow observations

| ID | Kind | Actor/entry | Ordered behavior and side effects | Errors/recovery | Evidence IDs | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- |
| SURF-001 | [[REQUIRED: screen, route, command, endpoint, symbol, protocol, job, or device]] | [[REQUIRED: ACT-### and exact entry]] | [[REQUIRED: observed states/transitions]] | [[REQUIRED: observed failures or UNKNOWN_BLOCKER]] | [[REQUIRED: E-### list]] | [[REQUIRED: MVP, GAP-###, or EXC-###]] |
| WF-001 | workflow | [[REQUIRED: actor and preconditions]] | [[REQUIRED: ordered actions and result]] | [[REQUIRED: failures/recovery]] | [[REQUIRED: E-### list]] | [[REQUIRED: MVP, GAP-###, or EXC-###]] |

## Artifact integrity and derivation

| Artifact ID | Path | Media type/size | SHA-256 | Raw parent | Transformation/redaction | Evidence IDs |
| --- | --- | --- | --- | --- | --- | --- |
| ART-001 | [[REQUIRED: stable repository-relative path]] | [[REQUIRED: type and bytes]] | [[REQUIRED: lowercase SHA-256]] | [[REQUIRED: parent ART-### or generated scoped ART ID, or `none`]] | [[REQUIRED: exact operation or `none`]] | [[REQUIRED: E-### list]] |

## Conflicts and unknowns

| Record ID | Missing/conflicting fact | Evidence searched | Impacted IDs | State | Resolution question/decision |
| --- | --- | --- | --- | --- | --- |
| CONFLICT-001 | [[REQUIRED: exact issue or `none`]] | [[REQUIRED: IDs/paths]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: RESOLVED or UNKNOWN_BLOCKER]] | [[REQUIRED: DEC-### or one exact question]] |
