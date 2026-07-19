---
schema_version: clone-security-assurance/v2
pack_id: "{{PACK_ID}}"
pack_revision: 1
product_name: {{PRODUCT_NAME_JSON}}
product_type: "{{PRODUCT_TYPE}}"
reference_source: {{SOURCE_DESCRIPTION_JSON}}
baseline_date: "{{BASELINE_DATE}}"
created_at: "{{CREATED_AT}}"
document_state: draft
---

# Security assurance — {{PRODUCT_NAME}}

## Scope, data, and trust boundaries

| ID | Asset/data/actor/boundary | Classification/privilege | Entry and exit paths | Owner/lifecycle | Requirement IDs |
| --- | --- | --- | --- | --- | --- |
| ASSET-001 | [[REQUIRED: exact item/boundary]] | [[REQUIRED: class/privilege]] | [[REQUIRED: interfaces and flows]] | [[REQUIRED: owner, retention, deletion]] | [[REQUIRED: REQ-### list]] |

## Threats and controls

| Threat ID | Preconditions/attack | Impacted assets | Control IDs | Residual risk | Evidence |
| --- | --- | --- | --- | --- | --- |
| THREAT-001 | [[REQUIRED: concrete misuse/failure path]] | [[REQUIRED: ASSET/ACT/IF IDs]] | [[REQUIRED: CTRL-### list]] | [[REQUIRED: exact remaining exposure]] | [[REQUIRED: E/DEC IDs]] |

| Control ID | Prevent/detect/respond contract | Implementation locator | Negative check | Owner | State/evidence |
| --- | --- | --- | --- | --- | --- |
| CTRL-001 | [[REQUIRED: exact MUST/MUST NOT rule]] | [[REQUIRED: path/symbol/config or planned locator]] | [[REQUIRED: ASSURE-### and TEST-###]] | [[REQUIRED: actor]] | [[REQUIRED: PLANNED, IMPLEMENTED_UNVERIFIED, VERIFIED, or BLOCKED plus IDs]] |

## Assurance checks

| Check ID | Kind/scope | Tool/version or procedure | Required result | Observed result | Run/artifact IDs |
| --- | --- | --- | --- | --- | --- |
| ASSURE-001 | [[REQUIRED: threat-model, provenance, sast, secret, dependency, license, sbom, dast, slsa, independent-review, or rollback-recovery]] | [[REQUIRED: exact command/procedure]] | [[REQUIRED: binary threshold]] | [[REQUIRED: NOT_RUN while no RUN exists; otherwise PASS, FAIL, BLOCKED, or ERROR]] | [[REQUIRED: RUN/artifact IDs or `none`]] |

## Findings and exceptions

| ID | Kind/severity | Exact condition | Affected IDs | Disposition/authority | Closure or expiry evidence |
| --- | --- | --- | --- | --- | --- |
| FIND-001 | [[REQUIRED: finding and severity or `none`]] | [[REQUIRED: reproducible condition or `none`]] | [[REQUIRED: IDs or `none`]] | [[REQUIRED: OPEN, REMEDIATED, ACCEPTED_EXCEPTION, or `none` plus authority]] | [[REQUIRED: exact evidence/date or `none`]] |

## Assurance verdict

- Verdict: [[REQUIRED: HOLD, VERIFIED_FOR_PINNED_SCOPE, or NOT_APPLICABLE]]
- Revision, checks, and findings: [[REQUIRED: exact revision and ASSURE/FIND/EXC/RUN IDs]]
- Unverified platforms/configurations: [[REQUIRED: exact list or `none`]]
