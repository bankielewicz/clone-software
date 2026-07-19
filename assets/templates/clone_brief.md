---
schema_version: clone-brief/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_YAML}}
document_state: draft
---

# Clone brief — {{PRODUCT_NAME}}

## Authority and authorization

| Field | Pinned value | Evidence/decision ID |
| --- | --- | --- |
| Requester and product owner | [[REQUIRED: name the requesting authority and product owner]] | [[REQUIRED: E-### or DEC-###]] |
| Authorization basis | [[REQUIRED: ownership, license, engagement, or explicit permission]] | [[REQUIRED: E-### or DEC-###]] |
| Permitted reference sources | [[REQUIRED: exact URLs, artifacts, accounts, endpoints, and environments]] | [[REQUIRED: E-### or DEC-###]] |
| Prohibited operations | [[REQUIRED: exact access, probe, write, or distribution exclusions]] | [[REQUIRED: DEC-###]] |
| Distribution target | [[REQUIRED: local evaluation, internal deployment, customer deployment, or public distribution]] | [[REQUIRED: DEC-###]] |
| Branding and asset rights | [[REQUIRED: reuse authorization or replacement rule]] | [[REQUIRED: E-### or DEC-###]] |
| Data policy | [[REQUIRED: synthetic, redacted, or explicitly authorized data]] | [[REQUIRED: DEC-###]] |
| Secret handling | [[REQUIRED: source and storage mechanism without secret values]] | [[REQUIRED: DEC-###]] |

## Frozen reference baseline

| Field | Value |
| --- | --- |
| Product/release/build | [[REQUIRED: immutable version, build, commit, or dated snapshot]] |
| Captured at | [[REQUIRED: ISO-8601 timestamp with offset]] |
| Environment | [[REQUIRED: OS, browser/device/runtime, region, locale, role, tenant, flags, and dataset]] |
| Artifact manifest | [[REQUIRED: repository-relative path to evidence manifest or ledger]] |
| Change policy | [[REQUIRED: exact rule for refreshing or superseding this baseline]] |

## Product outcome

- Primary users: [[REQUIRED: ACT-### identifiers and exact user descriptions]]
- Problem solved: [[REQUIRED: one observable outcome statement]]
- Primary value loop: [[REQUIRED: WF-### sequence from precondition to durable completion]]
- Clone purpose: [[REQUIRED: evaluation, replacement, migration, interoperability, training, or other exact purpose]]
- Deployment boundary: [[REQUIRED: local, test, internal, or production environment and network exposure]]
- Acceptance authority: [[REQUIRED: person, test oracle, and artifacts that decide acceptance]]

## MVP boundary

| Workflow ID | Actor IDs | Included start state | Included terminal state | Requirement IDs | Evidence/decision IDs |
| --- | --- | --- | --- | --- | --- |
| WF-001 | [[REQUIRED: ACT-###]] | [[REQUIRED: exact state]] | [[REQUIRED: exact durable outcome]] | [[REQUIRED: REQ-### list]] | [[REQUIRED: E-### or DEC-### list]] |

## Fidelity decisions

<!-- Use MUST_MATCH, MAY_DIFFER with an exact tolerance, or EXCLUDED with a reason. -->

| Dimension | Disposition | Oracle and metric | Evidence/decision IDs |
| --- | --- | --- | --- |
| Behavioral | [[REQUIRED: disposition]] | [[REQUIRED: exact comparison and tolerance]] | [[REQUIRED: IDs]] |
| Wire/protocol | [[REQUIRED: disposition]] | [[REQUIRED: exact comparison and tolerance]] | [[REQUIRED: IDs]] |
| Visual | [[REQUIRED: disposition]] | [[REQUIRED: exact comparison and tolerance]] | [[REQUIRED: IDs]] |
| Content/data | [[REQUIRED: disposition]] | [[REQUIRED: exact comparison and tolerance]] | [[REQUIRED: IDs]] |
| Platform | [[REQUIRED: disposition]] | [[REQUIRED: exact comparison and tolerance]] | [[REQUIRED: IDs]] |
| Accessibility | [[REQUIRED: disposition]] | [[REQUIRED: exact standard and scenarios]] | [[REQUIRED: IDs]] |
| Performance | [[REQUIRED: disposition]] | [[REQUIRED: environment, workload, statistic, and limit]] | [[REQUIRED: IDs]] |
| Security/privacy | [[REQUIRED: disposition]] | [[REQUIRED: exact trust-boundary checks]] | [[REQUIRED: IDs]] |
| Operations | [[REQUIRED: disposition]] | [[REQUIRED: exact deploy/recovery checks]] | [[REQUIRED: IDs]] |

## Explicit exclusions

| Exclusion ID | Excluded behavior/surface | Reason | Disposition | Authority ID |
| --- | --- | --- | --- | --- |
| EXC-001 | [[REQUIRED: exact exclusion]] | [[REQUIRED: concrete reason]] | [[REQUIRED: GAP-### or permanent non-goal]] | [[REQUIRED: DEC-###]] |

## Decision ledger

| Decision ID | Question | Pinned answer | Authority | Date | Affected IDs |
| --- | --- | --- | --- | --- | --- |
| DEC-001 | [[REQUIRED: exact resolved decision]] | [[REQUIRED: one selected answer]] | [[REQUIRED: name or governing artifact]] | [[REQUIRED: ISO-8601 date]] | [[REQUIRED: IDs]] |

## Blockers

UNKNOWN_BLOCKERS: [[REQUIRED: `none` or a list of UNKNOWN_BLOCKER IDs and one exact resolution question for each]]
