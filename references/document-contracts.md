# Document contracts

Use these contracts when completing or reviewing the generated pack.

## Contents

1. Authority order
2. Language rules
3. Traceability model
4. Specification readiness
5. Gap dossier readiness
6. Status transitions
7. Cold implementation handoff
8. Workspace entry dispositions

## Authority order

Record a project-specific authority order. Use this default only when governing repository documents do not define one:

1. explicit decisions in `clone_brief.md`;
2. frozen evidence in `evidence_ledger.md`;
3. normative behavior in `clone_specification.md`;
4. acceptance contracts in `acceptance_matrix.md`;
5. ordered changes in `mvp_build_plan.md` or `gap_implementation_plan.md`;
6. status and deferred scope in `gaps_analysis.md`.

Resolve contradictions before implementation. Lower-authority documents cannot silently override higher-authority behavior.

## Language rules

The key words `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY`, when written in all capitals, carry the meanings defined by BCP 14 (RFC 2119 and RFC 8174). A `SHOULD` or `SHOULD NOT` deviation requires a recorded reason, authority, and affected IDs.

Use factual present tense for current behavior and imperative or `MUST`/`MUST NOT` for required behavior. Use exact values, units, time zones, encodings, ordering, defaults, error outcomes, and version pins.

Reject these patterns:

- `TBD`, `TODO`, `TBC`, `???`, or unresolved template markers;
- “should”, “could”, “may”, “might”, “ideally”, “eventually”, or “as needed”;
- “support X” without naming the X operations and observable contract;
- “handle errors” without enumerating conditions, status/output, side effects, and recovery;
- “match the original” without a named evidence baseline and metric;
- “production-ready”, “secure”, “scalable”, or “pixel-perfect” without acceptance evidence;
- invented file paths, symbols, commands, or target behavior.

Use `UNKNOWN_BLOCKER` plus one resolution question when evidence cannot supply an exact statement.

## Traceability model

Maintain these edges:

```text
E-### -> REQ-### -> AC-### -> TEST-### -> RUN-###
DEC-### -> REQ-###
REQ-### -> GAP-### when deliberately deferred
GAP-### -> AC-### and TEST-### for future closure
```

The index stores both directions of every governed edge. Require `E/DEC <-> REQ`, `REQ <-> AC/TEST`, `TEST <-> GATE`, and reciprocal `runs` links from every REQ, AC, TEST, GATE, E, ART, or CAP named by a RUN record. A run-writing command updates the RUN record and all reciprocal links in one index write.

Each acceptance criterion states preconditions, one action/event, observable output/state, prohibited side effects, and tolerance. Each test states its layer, fixture, command, and exact expected result. Each run record includes date, baseline revision, command, exit status, and artifact/log path.

Treat the starting revision and hashes as a pre-edit gate, not a post-edit acceptance precondition. Verify them once immediately before the first authorized edit. After edits begin, prove scope against the recorded baseline with a complete version-control diff or full-tree inventory; do not repeatedly require mutable files to retain their starting hashes, and do not use a depth-limited inventory as whole-repository proof.

When an error message or stream is exact, assert exact bytes or exception arguments. An unanchored substring or regular-expression match does not prove an exact contract.

## Specification readiness

A specification is build-ready only when it defines every applicable item:

- actors, roles, permissions, and trust boundaries;
- workflow preconditions, steps, state transitions, success, errors, cancellation, retry, and recovery;
- route/screen/command/endpoint inventory and navigation or call graph;
- input schemas, validation, output schemas, deterministic ordering, and missing-versus-zero semantics;
- persistence model, ownership, lifecycle, concurrency, transactions, migrations, and seed/fixture behavior;
- authentication, authorization, tenant isolation, secret handling, rate limits, and audit events;
- time, locale, units, precision, rounding, pagination, timeout, retry, idempotency, and compatibility rules;
- accessibility, performance, observability, deployment, backup/recovery, and platform constraints;
- exact MVP inclusion/exclusion and acceptance mappings.

Mark a non-applicable item `EXCLUDED` with a reason. Do not omit it silently.

## Gap dossier readiness

Every `OPEN` actionable gap contains:

1. identity, class, priority, status, dependencies, and source requirement/evidence;
2. current behavior with current repository evidence;
3. exact target behavior and observable delta;
4. user/consumer impact and reason for deferral;
5. repository change map with paths and symbols verified to exist, or explicitly named new paths;
6. interface, state, data, migration, algorithm, error, security, telemetry, and compatibility contracts;
7. ordered implementation steps with checkpoints;
8. fixtures and tests covering normal, boundary, negative, authorization, concurrency, and recovery behavior as applicable;
9. exact commands and expected results;
10. atomic acceptance criteria;
11. rollout, rollback, data repair, and backwards-compatibility rules;
12. non-goals and prohibited shortcuts;
13. risks with concrete mitigations;
14. closure evidence fields that remain empty until work is verified.

These fields are not satisfied by prose alone. Copy `assets/templates-v2/gap_dossier.json` into that gap's `clone_index.json` `attributes.dossier`, replace every generated marker, and keep the human dossier semantically identical. The `gap-plan` validator applies `assets/schemas/gap-dossier-v2.schema.json`, resolves every referenced record and decision, rejects duplicate or non-contiguous change/step IDs, verifies existing and new repository paths, requires an existing symbol anchor to occur exactly once, enforces the allowed path fence, checks test-dimension dispositions, and requires the GAP record to link back to every requirement, acceptance criterion, test, gate, change, step, and HALT in the dossier. A path, symbol, command, fixture, or test that has not been inspected cannot be represented as ready.

An `EVIDENCE_GAP` remains `BLOCKED` with `readiness: BLOCKED`. Its GAP attributes contain a `blocker` object with exactly `missing_evidence`, non-empty `investigations`, one `resolution_question`, and `authority`. Do not attach a fabricated change map or ready dossier.

## Status transitions

Use this state machine:

```text
OPEN -> IN_PROGRESS -> IMPLEMENTED -> VERIFIED
OPEN -> BLOCKED -> OPEN
OPEN -> DECLINED
BLOCKED -> DECLINED
IMPLEMENTED -> IN_PROGRESS when verification finds a defect
VERIFIED -> OPEN only with new contrary evidence and a supersession record
```

- `OPEN`: target and implementation contract are complete; code work has not started.
- `BLOCKED`: exact target or authorized execution prerequisite is missing.
- `IN_PROGRESS`: an authorized implementation slice is active.
- `IMPLEMENTED`: code exists and focused checks pass; full acceptance is pending.
- `VERIFIED`: every acceptance criterion passes on the recorded revision.
- `DECLINED`: an authority explicitly rejects the work; record decision and reason.

Never derive status from prose or commit presence alone. Record evidence for every transition.
When the last nonterminal gap becomes `VERIFIED` or `DECLINED`, set `NO-OPEN-GAPS: true`. Reopen it to `false` when new evidence creates a nonterminal gap.

## Cold implementation handoff

Make `gap_implementation_plan.md` sufficient for an agent with no chat history. Include:

- repository and exact baseline revision;
- controlling artifacts and authority order;
- selected gap IDs and explicit exclusions;
- allowed change fence and unrelated dirty-state handling;
- exact decisions, invariants, public interfaces, schemas, and versions;
- ordered file/symbol changes;
- test-first sequence and fixtures;
- required focused and broad gate commands with expected results;
- evidence-recording locations;
- blocking `HALT` conditions;
- completion and stop conditions.

Do not tell the implementer to “refer to prior discussion” or choose among unresolved alternatives.

Before implementation, record plan/status fields as `not implemented`, `none`, `NOT_RUN`, `NOT_STARTED`, or `HOLD`. These are current-state facts, not missing specification. `NOT_RUN` means no immutable run record exists. Once execution creates a `RUN-###` record, its result is exactly `PASS`, `FAIL`, `BLOCKED`, or `ERROR`; replace plan placeholders only with actual revision and run evidence.

In `spec-only` mode, absence of product code is not an `MVP_BLOCKER`. Track every planned MVP requirement as `NOT_STARTED` in the acceptance matrix and as ordered work in the MVP build plan. Add an `MVP_BLOCKER` only after inspecting an existing or attempted implementation that is contractually expected to meet the requirement and does not.

## Workspace entry dispositions

Record every pre-session/live root delta before product edits. Each disposition record has exactly these semantic fields:

| Field | Contract |
| --- | --- |
| `path` | One safe repository-relative path. |
| `observed_type` | Non-following type observed in the live workspace. |
| `content_inventory_or_hash` | Complete descendant inventory for a directory or SHA-256 for a regular file/link text; use `empty` only after an exact empty-directory check. |
| `pre_session_presence` | Boolean from immutable pre-session inventory evidence. |
| `owner_claim` | `USER_PINNED` for an authorized runtime exclusion; never a provider-ownership inference. |
| `lifetime` | Exact interval covered by the identity rechecks. |
| `authority_ids` | Non-empty decisions authorizing the disposition. |
| `evidence_ids` | Non-empty evidence records supporting pre-session and live facts. |
| `disposition` | `PRODUCT_INPUT`, `REPOSITORY_INSTRUCTION`, `TOOL_RUNTIME_EXCLUDED`, or `UNKNOWN_BLOCKER`. |
| `allowed_operations` | Exact allowed operations. It is empty for `TOOL_RUNTIME_EXCLUDED`. |

A `TOOL_RUNTIME_EXCLUDED` record does not prove provider ownership. Keep it outside product requirements and hashes, bind it separately into snapshots or filesystem captures that support the exclusion, and revalidate it before and after each operation. A missing field or mismatched recheck changes the disposition to `UNKNOWN_BLOCKER` and blocks the operation.
