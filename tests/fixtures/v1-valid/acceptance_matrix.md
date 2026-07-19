---
schema_version: clone-acceptance/v1
pack_id: clone-fixture-product-2026-01-01
product_name: "Fixture Product"
document_state: validated
---

# Acceptance matrix — Fixture Product

## Acceptance criteria

| AC ID | Requirement IDs | Evidence IDs | Preconditions | Action | Expected result | Prohibited effects | Tolerance | Test IDs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-001 | REQ-001 | E-001 | ENV-001 clean state | Invoke SURF-001 | Exact fixture output and exit zero | Persistent writes and network calls | exact | TEST-001 |

## Requirement verification

| Requirement ID | Implementation locator | AC IDs | Test IDs | Status | Run IDs | Deviation IDs |
| --- | --- | --- | --- | --- | --- | --- |
| REQ-001 | src/fixture.py:main | AC-001 | TEST-001 | VERIFIED | RUN-001 | none |

## Verification runs

| Run ID | Baseline | Environment | Directory | Command | Result | Artifact | IDs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RUN-001 | fixture-revision | ENV-001 | repository root | python -m unittest | exit 0 and pass | tests/fixtures/run.txt | TEST-001 and AC-001 |

## MVP verdict

- Reference baseline: Fixture CLI 1.0
- Clone baseline: fixture-revision
- Verified requirements: REQ-001
- Non-verified MVP requirements: none
- Skipped/unavailable checks: none
- Verdict: VERIFIED_MVP
