---
schema_version: clone-spec/v1
pack_id: clone-fixture-product-2026-01-01
product_name: "Fixture Product"
product_type: "cli"
reference_source: "Fixture CLI 1.0"
document_state: validated
---

# Clone specification — Fixture Product

## Authority and baseline

DEC-001 and E-001 control this specification.

## Product contract

The fixture command emits one exact line and exits zero.

## Actors and permissions

ACT-001 is an authorized local user.

## MVP workflows

WF-001 invokes SURF-001 once.

## Surface inventory

SURF-001 is the fixture command.

## Behavioral requirements

### REQ-001 — Emit the fixture response

- Truth basis: VERIFIED
- Source IDs: E-001 and DEC-001
- Actor and preconditions: ACT-001 in ENV-001
- Trigger/input: Invoke SURF-001 with no arguments
- Required behavior: Write `fixture-ok\n` to standard output and write zero bytes to standard error
- Output/state/side effects: Exit zero with no persistent side effects
- Validation and errors: Additional arguments produce exit two
- Authorization/privacy: Process synthetic fixture data only
- Concurrency/idempotency: Repeated invocations produce identical output
- Timing/retry/recovery: Complete without retry
- Compatibility/accessibility: Operate under the pinned Python runtime
- Acceptance IDs: AC-001
- Planned test IDs: TEST-001
- Implementation owners: src/fixture.py:main

## Interface contracts

IF-001 is the command stream and exit-code contract for REQ-001.

## Data and state contracts

DATA-001 is immutable synthetic input.

## Security and privacy

SEC-001 prohibits credentials and external network effects.

## Non-functional contracts

NFR-001 requires deterministic bytes in ENV-001.

## Architecture and repository map

The implementation owner is src/fixture.py:main.

## Configuration and operations

No configuration, migration, service health, telemetry, or backup contract applies.

## MVP exclusions and gap mapping

EXC-001 records the permanent non-goal selected by DEC-001.

## Readiness result

The fixture specification is ready with no blockers.
