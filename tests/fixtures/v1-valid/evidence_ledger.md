---
schema_version: clone-evidence/v1
pack_id: clone-fixture-product-2026-01-01
product_name: "Fixture Product"
reference_source: "Fixture CLI 1.0"
document_state: validated
---

# Evidence ledger — Fixture Product

## Capture environment

ENV-001 is Python 3 on a local test host with synthetic data.

## Evidence records

| Evidence ID | Truth label | Source | Version | Preconditions | Observation | Reproduction | Confidence | Derived IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E-001 | VERIFIED | tests/fixtures/reference.txt | 1.0 | ENV-001 clean state | The command prints fixture-ok and exits zero. | Run the frozen fixture command. | HIGH with exact bytes | REQ-001 |

## Surface inventory

SURF-001 is the fixture command and belongs to REQ-001.

## Workflow observations

WF-001 invokes SURF-001 and observes fixture-ok.

## Conflicts and unknowns

There are no conflicts or unknowns.

## Artifact integrity

ART-001 identifies the frozen reference transcript.
