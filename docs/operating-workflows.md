# Operating workflows

This document defines how a user selects a mode, what Codex may change, which validation profile controls each phase, and what constitutes a complete handoff.

The normative agent contract remains [SKILL.md](../SKILL.md). The evidence, document, capture, security, and evolution contracts remain the corresponding files under [`references/`](../references/).

## Mode decision

Use exactly one primary mode per invocation.

| Mode | Select when | May edit product code | Required stop |
| --- | --- | --- | --- |
| `mvp-build` | The user requests a working clone or MVP implementation | Yes, only after `build-ready` | Passing sealed `verified-mvp`, or `HOLD` |
| `spec-only` | The user requests capture, analysis, specification, or planning without implementation | No | Passing `spec-ready`, or exact blockers |
| `gap-plan` | A v2 pack already contains gaps that need cold-executable dossiers | No | Passing `gap-plan`, or exact blockers |
| `gap-implement` | A v2 pack contains selected, ready gap dossiers to implement | Only inside selected fences after preconditions pass | Passing closure evidence for selected gaps, or `HALT` |
| `pack-migrate` | The controlling artifact is a clone-pack/v1 directory | No product-code edits during migration | Non-overwriting v2 successor and report, or migration blocker |
| `enhancement-plan` | An existing repository needs a bounded executable change plan | No | Passing `enhancement-ready`, or exact blockers |
| `enhancement-build` | An existing repository needs one bounded change implemented | Only after `enhancement-ready` and inside its fence | Passing sealed `verified-enhancement`, or exact blockers |

Do not combine `spec-only` with product implementation. Do not use a gap dossier to defer an unfinished MVP behavior. Do not use migration as evidence that v1 prose satisfies v2 semantics.

Tool `2.1.0` profiles are scoped proofs. Read [Runtime enforcement boundaries](runtime-enforcement-boundaries.md), report the machine result and any dimension outside its profile separately, and never convert a narrow pass into a broader claim.

## Common phase gates

### Phase 0: establish authority

Record all of the following before non-public observation:

1. requester identity;
2. authorization basis;
3. permitted sources, accounts, endpoints, artifacts, and environments;
4. permitted target-side actions;
5. prohibited actions;
6. distribution target;
7. branding, content, model, dataset, and asset rights;
8. data policy; and
9. secret source and storage policy.

If one missing answer changes behavior, security, data ownership, compatibility, architecture, distribution, or the MVP boundary, create an `UNKNOWN_BLOCKER`, name the affected ID, list the evidence checked, and ask one resolution question.

### Phase 1: freeze current state

Inspect and record:

- repository instructions and exact absolute repository root;
- current revision or complete working-tree inventory/diff hash;
- unrelated dirty state and its ownership;
- reference release/build/commit/artifact digest;
- reference and clone environments;
- actors, roles, fixtures, locale, time zone, clocks, devices, flags, accounts, integrations, and dataset;
- product type and every applicable playbook; and
- intended pack directory.

Do not modify product code in this phase.

### Phase 2: initialize or adopt the pack

For a new v2 pack:

```bash
python3 "<skill-root>/scripts/clone_pack.py" init \
  --product-name "<exact product name>" \
  --product-type <controlled-type> \
  --playbook <applicable-playbook> \
  --source-description "<authorized immutable reference description>" \
  --repo-root "<absolute-repository-root>" \
  --output-dir "<absent-repository-relative-directory>"
```

Repeat `--playbook` for each hybrid contract. Initialization refuses an existing destination. It does not validate a source assertion.

For an existing v2 pack, validate its current structure before editing:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile scaffold --format json --max-problems 0
```

For v1, switch to `pack-migrate`; do not reinterpret it as v2.

### Phase 3: reach `baseline-ready`

Resolve authorization and baseline fields in `clone_brief.md`, bind primary evidence and environments in `evidence_ledger.md`, freeze `reference_baseline_id` in `clone_pack.json`, and create exact `BASE`, `ENV`, `E`, `DEC`, `CAP`, and related records in `clone_index.json`.

Every capture plan case has a same-ID `CAP` index counterpart. Its locator hash, environment link, decision links, and `attributes.case_sha256` MUST match the current plan case. Replace every required marker in the documents governed by this profile.

Validate:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile baseline-ready --format json --max-problems 0
```

Do not treat a passing baseline as an implementation or parity claim.

### Phase 4: reach `spec-ready`

Inventory every in-scope actor, surface, workflow, state, transition, input, output, validation error, permission, side effect, persistence rule, background operation, time/order rule, recovery path, and applicable nonfunctional dimension.

For each capability, select exactly one disposition:

```text
EQUIVALENT MISSING PARTIAL DIVERGENT EXCLUDED UNVERIFIED
```

Create evidence or authority-backed requirements. Maintain reciprocal traceability:

```text
E/DEC <-> REQ <-> AC/TEST
TEST <-> GATE
```

Each `TEST` has an independent oracle. Each surface/workflow disposition has its required requirement, gap, exclusion, decision, and proof links. Each parity case has a same-ID `PAR` record with the exact capture and normalization-authority links.

In `spec-only`, mark planned implementation and run states as `NOT_STARTED` or `NOT_RUN`. Absence of product code is not an `MVP_BLOCKER`. Add an `MVP_BLOCKER` only when an existing or attempted implementation is contractually expected to satisfy the requirement and does not.

Validate:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile spec-ready --format json --max-problems 0
```

`spec-only` stops after this command passes. Its handoff states that no product-code edits occurred.

### Phase 5: reach `build-ready`

Pin:

- repository revision and working-tree diff or inventory hash;
- exact implementation paths and symbol anchors;
- architecture decisions and interfaces;
- dependency/tool/runtime versions, origins, digests, licenses, and rights;
- greenfield scaffold profile or exact brownfield `not-applicable` disposition;
- gate argv arrays, cwd, environment identity, expected exit, timeout, coverage, and oracle links;
- risk profile and every required assurance kind; and
- allowed path fences, prohibited shortcuts, rollback, recovery, and halt conditions.

For greenfield work, copy one catalog profile exactly into `scaffold_plan.json`. For an adopted brownfield implementation, use the exact sentinel defined in [Greenfield and scaffold contract](../references/greenfield.md). No other scaffold disposition is supported.

Validate:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile build-ready --format json --max-problems 0
```

This passing result is the first authorization to modify product code in `mvp-build` or selected `gap-implement` work.

### Phase 6: implement one vertical slice

For each dependency-ordered slice:

1. Reconfirm governing evidence, decisions, requirements, and allowed paths.
2. Add a discriminating failing test, or record the repository-specific reason for another order.
3. Implement the smallest complete behavior.
4. Exercise the applicable normal, boundary, negative, authorization, concurrency, interruption, and recovery cases.
5. Execute indexed gates through `record-run`.
6. Preserve failures and update gaps; do not rewrite an oracle or tolerance to make the clone pass.

Example gate execution:

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
```

Gate stdout and stderr are retained raw. The gate MUST NOT print a secret, credential, personal record, or unauthorized content.

### Phase 7: capture and compare

Execute reference and clone captures independently under the same indexed environment:

```bash
python3 "<skill-root>/scripts/clone_pack.py" capture "<pack>" --case CAP-001
python3 "<skill-root>/scripts/clone_pack.py" capture "<pack>" --case CAP-002
python3 "<skill-root>/scripts/clone_pack.py" parity "<pack>" --case PAR-001
```

For a batch:

```bash
python3 "<skill-root>/scripts/clone_pack.py" capture "<pack>" --all
```

Batch capture preflights the complete selected set, executes in lexical capture-ID order, and continues through acquisition `FAIL` and `BLOCKED` results. Use `--resume` only to validate and skip current finalized results or recover runner-owned incomplete staging. Resume never retries a finalized `FAIL` or `BLOCKED`; assign a new capture ID for replacement evidence.

A capture `PASS` means the adapter acquired and retained the observation. Inspect `summary.exit_code`, `summary.status`, or retained artifacts for the product outcome.

Parity mismatch exits `5`, retains the mismatch, and requires a mapped gap or blocker.

### Phase 8: run assurance

Run required cases, all cases, or an explicitly selected case set:

```bash
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>"
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>" --all
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>" \
  --case ASSURE-001 --case ASSURE-002
```

Without a selector, `assure` selects required cases. `--all` adds optional cases. The complete selected set is preflighted before execution. The command atomically writes results into `evidence/assurance/`, updates `assurance_plan.json`, and, for a brownfield workstream, binds the executed IDs in `enhancement_plan.json`; it then emits canonical JSON. Aggregate exit precedence is infrastructure `7`, verification `5`, then success `0`. An empty required set does not satisfy a profile that requires assurance coverage.

### Phase 9: validate and seal

Validate before sealing:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile verified-mvp --format json --max-problems 0
```

Before `seal.json` exists, the validator returns a seal diagnostic even when every other proof passes. Create the seal only through:

```bash
python3 "<skill-root>/scripts/clone_pack.py" seal "<pack>" \
  --profile verified-mvp
```

Then rerun the same `verified-mvp` validation. The built-in seal is an unsigned integrity manifest over governed files; it does not replace signing, rights, security, or artifact-attestation evidence.

## `mvp-build` mode

### Request contract

```text
Use $clone-software in mvp-build mode.
Authorization: <requester, basis, permitted sources/actions, prohibited actions>.
Reference: <immutable locator and digest/version>.
Clone repository: <absolute path>.
Pack: <repository-relative path>.
Product type/playbooks: <controlled values>.
Distribution/data/secrets/branding policies: <exact values>.
MVP: <actors and complete vertical journeys>.
Terminal condition: sealed verified-mvp or HOLD with exact blocked IDs and complete non-MVP gaps.
```

### Completion contract

Completion requires:

- a current required reference capture and clone capture with acquisition `PASS`;
- a current required parity `PASS` over those captures;
- at least one complete `REQ -> AC -> TEST -> GATE -> PASS RUN` chain with an independent oracle;
- passing required assurance;
- no non-verified `MVP_BLOCKER`;
- current repository and plan hashes; and
- a valid `verified-mvp` seal.

Anything less is a workflow `HOLD`. Preserve the actual nested validator status and exit; do not report validator `status: HOLD` unless the validator returned exit `5`.

## `spec-only` mode

### Request contract

```text
Use $clone-software in spec-only mode.
Authorization/reference/repository/product policies: <exact values>.
Specification boundary: <named surfaces, workflows, dimensions, and exclusions>.
Terminal condition: spec-ready or exact blockers. Do not edit product code.
```

### Completion contract

- `spec-ready` passes.
- Required observations and unknowns are distinguished.
- Planned MVP work is `NOT_STARTED`/`NOT_RUN` rather than misclassified as a defect.
- Every evidenced excluded or divergent behavior outside the MVP is represented in gaps or non-goals.
- The handoff explicitly states that product code was not changed.

## `gap-plan` mode

### Request contract

```text
Use $clone-software in gap-plan mode.
Repository: <absolute path and exact revision/diff>.
Pack: <absolute or repository-relative v2 pack path>.
Selection: <exact GAP IDs or all_actionable>.
Terminal condition: gap-plan passes for the selected dependency-safe order; do not edit product code.
```

### Planning rules

- An actionable gap is `OPEN`, `readiness: READY`, and contains the complete machine dossier from `assets/templates-v2/gap_dossier.json`.
- Every existing path and symbol anchor is inspected. Every new path is declared as new. The allowed fence contains every change.
- Steps, changes, fixtures, commands, expected results, test dimensions, rollout, rollback, recovery, non-goals, risks, HALTs, and empty closure fields are exact.
- Dependencies appear earlier in `plan_order` or are already `VERIFIED`.
- An `EVIDENCE_GAP` remains `BLOCKED`, has only the exact blocker object, and receives no fabricated implementation dossier.

Validate:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile gap-plan --format json --max-problems 0
```

## `gap-implement` mode

### Request contract

```text
Use $clone-software in gap-implement mode.
Repository and pack: <exact paths and revision/diff>.
Selected gaps: <dependency-safe GAP IDs>.
Authority: execute only the selected dossier steps and allowed path fences.
Terminal condition: selected gaps reach VERIFIED with current evidence, or HALT on a named dossier condition. Do not implement unselected gaps.
```

### Lifecycle

Change gap status only through `gap-transition`:

```text
OPEN -> IN_PROGRESS -> IMPLEMENTED -> VERIFIED
OPEN -> BLOCKED -> OPEN
OPEN -> DECLINED
BLOCKED -> DECLINED
IMPLEMENTED -> IN_PROGRESS
VERIFIED -> OPEN
```

The exceptional transitions require their specific decision or contrary-evidence contract. Never edit status prose or `NO-OPEN-GAPS` directly.

Example start:

```bash
python3 "<skill-root>/scripts/clone_pack.py" gap-transition "<pack>" GAP-001 \
  --to IN_PROGRESS \
  --actor "<authorized implementer identity>" \
  --reason "<exact selected-slice reason>" \
  --decision DEC-001
```

Verify with current runs, parity, assurance, and transition history before the final transition. Tool `2.1.0` requires terminal selected gaps, current dossier closure evidence, and complete hash-chained history. Lifecycle surfaces are promoted through a recoverable transaction journal; unexpected byte divergence stops the transition.

## `pack-migrate` mode

### Request contract

```text
Use $clone-software in pack-migrate mode.
V1 source pack: <absolute path>.
V2 output: <absolute absent path outside the source tree>.
Occurrence mapping: <path or none before preflight>.
Terminal condition: create a non-overwriting v2 successor and migration report, or return the exact ambiguity/loss blockers. Do not modify source or product code.
```

Preflight:

```bash
python3 "<skill-root>/scripts/clone_pack.py" migrate "<v1-pack>" --check
```

If `ambiguous_candidates` is nonempty, create one mapping object covering every reported occurrence key with a unique same-kind destination ID, then rerun preflight:

```bash
python3 "<skill-root>/scripts/clone_pack.py" migrate "<v1-pack>" \
  --check --mapping "<mapping.json>"
```

Create the successor:

```bash
python3 "<skill-root>/scripts/clone_pack.py" migrate "<v1-pack>" \
  --output "<absent-v2-directory>" \
  --mapping "<mapping.json>"
```

The migration archives exact v1 bytes and hashes, preserves lineage and resolved IDs, downgrades unverifiable status, and writes structured reconciliation losses. It always requires semantic reconciliation. The source remains unchanged.

## `enhancement-plan` and `enhancement-build` modes

Use [Brownfield enhancement workflow](brownfield-enhancement.md) and load [the brownfield skill contract](../references/brownfield-enhancement.md).

### Request contract

```text
Use $clone-software in enhancement-plan|enhancement-build mode.
Authority: <requester, repository authority, permitted changes, prohibited actions>.
Repository: <absolute root and intended base revision>.
Enhancement: <ENH ID, exact title, controlled change types, repository-relative request file>.
Affected surfaces: <interfaces, data, security, dependencies, migrations, flags, telemetry>.
Path boundary: <allowed paths and protected existing dirty paths>.
Repository gates: <exact no-shell commands and expected outcomes>.
Terminal condition: enhancement-ready plan without product edits, or sealed verified-enhancement after implementation; otherwise return exact blockers. Do not deploy or merge.
```

### Profile and command sequence

```text
repository-adopted -> enhancement-ready -> implementation -> verified-enhancement
```

`implementation` is allowed only in `enhancement-build`; it is not a validation profile.

```bash
python3 "<skill-root>/scripts/clone_pack.py" enhancement-init <required-options>
python3 "<skill-root>/scripts/clone_pack.py" repo-snapshot "<pack>" --role adopted --record
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" --profile repository-adopted
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 --to READY <required-options>
python3 "<skill-root>/scripts/clone_pack.py" baseline-run "<pack>" --all
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" --profile enhancement-ready
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 --to IN_PROGRESS <required-options>
# Write a discriminating failing test, then implement only declared changes.
python3 "<skill-root>/scripts/clone_pack.py" repo-snapshot "<pack>" --role candidate --record
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" --gate GATE-001 --environment ENV-001
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 --to IMPLEMENTED --evidence SNAP-002 <required-options>
python3 "<skill-root>/scripts/clone_pack.py" regression "<pack>" --all
python3 "<skill-root>/scripts/clone_pack.py" verify-scope "<pack>" --enhancement ENH-001
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>"
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 --to VERIFIED <required-options>
python3 "<skill-root>/scripts/clone_pack.py" seal "<pack>" --profile verified-enhancement
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" --profile verified-enhancement
python3 "<skill-root>/scripts/clone_pack.py" rehash "<pack>" --record <explicit-existing-record>
```

Default-clean initialization rejects pre-existing Git changes. `--adopt-dirty` records explicitly accepted paths as protected input; it does not clean or claim them. Adopted baselines are immutable. Candidate regression and scope verification retain mismatches instead of replacing the oracle.

The `verified-enhancement` seal binds the request, enhancement plan, adopted and candidate snapshots, preservation, scope, assurance, and lifecycle evidence. It remains an unsigned integrity manifest and no delivery action is implied.

## Required handoff format

Every mode returns these fields:

1. mode;
2. reference baseline and environment;
3. repository revision/diff state;
4. highest passing validation profile;
5. exact commands and exit results;
6. product-code paths changed, or `none`;
7. verified MVP boundary, or `not implemented` in non-build modes;
8. pack and seal paths;
9. gaps by class/status;
10. blocked IDs and one resolution question per behavior-changing blocker; and
11. next dependency-safe action.

Brownfield modes additionally return enhancement ID, change types, adopted snapshot, candidate snapshot, affected surfaces, compatibility decisions, changed paths, preservation results, security and dependency deltas, residual gaps, and blockers.

Never state “complete parity,” “production-ready,” “secure,” or equivalent language beyond the exact retained dimensions and passing profiles.
