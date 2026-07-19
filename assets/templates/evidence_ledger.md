---
schema_version: clone-evidence/v1
pack_id: clone-{{PRODUCT_SLUG}}-{{BASELINE_DATE}}
product_name: {{PRODUCT_NAME_YAML}}
reference_source: {{SOURCE_DESCRIPTION_YAML}}
document_state: draft
---

# Evidence ledger — {{PRODUCT_NAME}}

## Capture environment

| Environment ID | Reference version | Role/tenant | Platform/runtime | Locale/time zone | Flags/state | Dataset |
| --- | --- | --- | --- | --- | --- | --- |
| ENV-001 | [[REQUIRED: exact version/build/snapshot]] | [[REQUIRED: role and tenant]] | [[REQUIRED: OS/browser/device/runtime versions]] | [[REQUIRED: locale and IANA time zone]] | [[REQUIRED: flags, consent, permission, and prior state]] | [[REQUIRED: synthetic fixture or authorized dataset ID]] |

## Evidence records

<!-- Truth labels: VERIFIED, USER_PINNED, INFERRED, UNKNOWN_BLOCKER. Confidence: HIGH, MEDIUM, LOW. -->

| Evidence ID | Truth label | Source and immutable locator | Version/date | Environment ID and preconditions | Atomic observation | Capture/reproduction | Confidence and reason | Derived IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E-001 | [[REQUIRED: truth label]] | [[REQUIRED: path, hash, URL plus capture artifact, command output, or decision]] | [[REQUIRED: exact version and ISO-8601 date]] | [[REQUIRED: ENV-### plus state]] | [[REQUIRED: one exact observable fact]] | [[REQUIRED: reproducible steps or command]] | [[REQUIRED: level and reason]] | [[REQUIRED: REQ-###, DEC-###, or GAP-###]] |

## Surface inventory

| Surface ID | Product surface | Actor/role | Entry point | States observed | Evidence IDs | MVP disposition |
| --- | --- | --- | --- | --- | --- | --- |
| SURF-001 | [[REQUIRED: route, screen, command, endpoint, job, protocol, or integration]] | [[REQUIRED: ACT-### and role]] | [[REQUIRED: exact entry]] | [[REQUIRED: default plus observed alternate/error states]] | [[REQUIRED: E-### list]] | [[REQUIRED: MVP, GAP-###, or EXC-###]] |

## Workflow observations

| Workflow ID | Preconditions | Ordered actions/events | Observable result and side effects | Failure/recovery states | Evidence IDs |
| --- | --- | --- | --- | --- | --- |
| WF-001 | [[REQUIRED: exact actor, data, and state]] | [[REQUIRED: numbered actions/events]] | [[REQUIRED: output, persisted state, and external effects]] | [[REQUIRED: named failures and recovery or EXCLUDED with decision ID]] | [[REQUIRED: E-### list]] |

## Conflicts and unknowns

| Record ID | Conflicting/missing fact | Evidence searched | Impacted IDs | Resolution state | Exact question or decision ID |
| --- | --- | --- | --- | --- | --- |
| CONFLICT-001 | [[REQUIRED: exact conflict/unknown or `none`]] | [[REQUIRED: E-### list or `not applicable`]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: RESOLVED or UNKNOWN_BLOCKER]] | [[REQUIRED: DEC-### or one exact question]] |

## Artifact integrity

| Artifact ID | Repository-relative path | SHA-256 | Redaction applied | Captured at | Evidence IDs |
| --- | --- | --- | --- | --- | --- |
| ART-001 | [[REQUIRED: stable artifact path]] | [[REQUIRED: lowercase SHA-256]] | [[REQUIRED: exact redaction or `none`]] | [[REQUIRED: ISO-8601 timestamp]] | [[REQUIRED: E-### list]] |
