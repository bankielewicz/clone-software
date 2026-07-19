---
schema_version: clone-brief/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_JSON}}
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
repository_root: "{{REPOSITORY_ROOT}}"
document_state: draft
---

# Clone brief — {{PRODUCT_NAME}}

## Authority and authorization

| Field | Pinned value |
| --- | --- |
| Requester/owner | [[REQUIRED: named authority]] |
| Authorization basis | [[REQUIRED: ownership, license, engagement, or explicit permission]] |
| Permitted evidence | [[REQUIRED: exact sources, accounts, endpoints, and artifacts]] |
| Prohibited operations | [[REQUIRED: exact actions and targets, or `none`]] |
| Distribution and production-use boundary | [[REQUIRED: exact audience and use]] |
| Branding, assets, and content rights | [[REQUIRED: reuse or replacement decision]] |
| Data and secrets policy | [[REQUIRED: classifications, synthetic/redacted rules, and secret source]] |

## Frozen reference baseline

- Baseline ID: [[REQUIRED: immutable BASE-### identifier]]
- Reference: {{SOURCE_DESCRIPTION}}
- Reference release/build and capture date: [[REQUIRED: immutable version and ISO-8601 date/time]]
- Baseline environment and artifact manifest: [[REQUIRED: ENV-### and artifact path/hash]]
- Repository starting state: [[REQUIRED: revision plus clean/dirty inventory or GREENFIELD-NO-COMMIT]]

## Product outcome and mode

- Operating mode: [[REQUIRED: mvp-build, spec-only, gap-plan, gap-implement, or pack-migrate]]
- Intended actors and outcome: [[REQUIRED: ACT-### list and observable value loop]]
- Selected playbooks: [[REQUIRED: exact reference filenames]]
- Required capabilities: [[REQUIRED: capture, parity, scaffold, assurance, signing, or explicit exclusions]]

## MVP boundary

| Workflow | In-scope terminal outcome | Evidence | Exclusions/gaps |
| --- | --- | --- | --- |
| WF-001 | [[REQUIRED: complete vertical journey]] | [[REQUIRED: E-### or DEC-###]] | [[REQUIRED: EXC-###, GAP-###, or `none`]] |

Dead controls, invented behavior, hard-coded success, mock persistence presented as durable, and unlabelled integrations are prohibited.

## Fidelity decisions

| Dimension | Disposition | Metric/tolerance | Oracle/comparison IDs |
| --- | --- | --- | --- |
| Behavior | [[REQUIRED: MUST_MATCH, MAY_DIFFER, or EXCLUDED]] | [[REQUIRED: exact metric/reason]] | [[REQUIRED: PAR-### list or `none`]] |
| Content/data | [[REQUIRED: disposition]] | [[REQUIRED: exact metric/reason]] | [[REQUIRED: IDs or `none`]] |
| Visual/accessibility | [[REQUIRED: disposition]] | [[REQUIRED: exact metric/reason]] | [[REQUIRED: IDs or `none`]] |
| Wire/platform | [[REQUIRED: disposition]] | [[REQUIRED: exact metric/reason]] | [[REQUIRED: IDs or `none`]] |
| Performance/operations/security | [[REQUIRED: disposition]] | [[REQUIRED: exact metric/reason]] | [[REQUIRED: IDs or `none`]] |

## Decisions and blockers

| ID | Kind | Exact decision or question | Authority/evidence | Impacted IDs | State |
| --- | --- | --- | --- | --- | --- |
| DEC-001 | [[REQUIRED: USER_PIN or ARCHITECTURE]] | [[REQUIRED: one exact ruling]] | [[REQUIRED: actor/artifact]] | [[REQUIRED: IDs]] | ACCEPTED |
| BLOCK-001 | [[REQUIRED: UNKNOWN_BLOCKER or `none`]] | [[REQUIRED: one answerable question or `none`]] | [[REQUIRED: evidence searched]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: OPEN or RESOLVED]] |

## Pack applicability

| Artifact | Applicability | Reason/authority |
| --- | --- | --- |
| `capture_plan.json` | [[REQUIRED: REQUIRED, OPTIONAL, or NOT_APPLICABLE]] | [[REQUIRED: exact reason]] |
| `parity_plan.json` | [[REQUIRED: REQUIRED, OPTIONAL, or NOT_APPLICABLE]] | [[REQUIRED: exact reason]] |
| `scaffold_plan.json` | [[REQUIRED: REQUIRED, OPTIONAL, or NOT_APPLICABLE]] | [[REQUIRED: exact reason]] |
| `assurance_plan.json` | [[REQUIRED: REQUIRED, OPTIONAL, or NOT_APPLICABLE]] | [[REQUIRED: exact reason]] |
