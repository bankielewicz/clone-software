# Brownfield enhancement contract

Load this reference when the user asks to enhance, extend, modernize, refactor, upgrade, migrate, or harden an existing repository. It governs both `enhancement-plan` and `enhancement-build` workstreams in tool `2.3.0`.

## Authority and repository adoption

Record the requester, authority basis, repository root, intended base revision, allowed change types, path and product boundaries, prohibited actions, data and secret policy, required gates, delivery target, and the exact enhancement request before planning a change.

The accepted change types are:

- `feature`
- `behavior-change`
- `refactor`
- `dependency-upgrade`
- `data-migration`
- `security-hardening`
- `operations`

The request file MUST be a non-empty UTF-8 regular file inside the repository. It MUST NOT be a symlink. `enhancement-init` copies the request into governed pack evidence and binds its SHA-256 digest; it does not rewrite the source request.

The repository is clean by default. If `git status` reports pre-existing changes, initialization returns `REPOSITORY_DIRTY` and leaves repository bytes unchanged. Use `--adopt-dirty` only when the requester explicitly accepts those exact paths as protected input. Record the paths and their initial bytes in `repository_inventory.json` and the enhancement scope. Later scope verification MUST distinguish those protected bytes from enhancement changes.

`enhancement-init` creates only the absent pack directory under the repository root. It does not edit product code, stage files, commit, install tools, contact a remote, push, open a pull request, deploy, or merge.

## Workstream records

A brownfield manifest records:

```json
{
  "workstream": {
    "kind": "brownfield-enhancement",
    "mode": "enhancement-plan",
    "enhancement_id": "ENH-001"
  }
}
```

The mode is either `enhancement-plan` or `enhancement-build`. The optional `workstream` and brownfield plan paths preserve legacy `clone-pack/v2` validity: an existing v2 pack without them remains a legacy clone workstream.

The brownfield plans are:

- `repository_inventory.json`, schema `clone-repository-inventory/v2`, for repository kind, base identity, dirty adoption, governed paths, and snapshots;
- `enhancement_plan.json`, schema `clone-enhancement-plan/v2`, for the request binding, change types, affected surfaces, compatibility dispositions, delivery strategy, preservation cases, scope, and enhancement state; and
- optional `full_stack_qa_plan.json`, schema `clone-full-stack-qa-plan/v1`, for a selected journey that crosses browser UI, one or more real request/response exchanges, an application-owned service postcondition, and persistence after reload, relogin, or restart.

Use stable `ENH-###`, `PRES-###`, `SNAP-###`, and `SCOPE-###` records. Maintain reciprocal index links. A changed path belongs to exactly one controlled change record. Missing evidence becomes an `ENHANCEMENT_GAP`; it never becomes an inferred pass.

## Modes and product-code fence

| Mode | Product-code permission | Terminal state |
| --- | --- | --- |
| `enhancement-plan` | Forbidden | Passing `enhancement-ready`, or exact blockers |
| `enhancement-build` | Allowed only after `enhancement-ready` | Passing sealed `verified-enhancement`, or exact blockers |

The implementation phase remains inside the enhancement plan's path and behavior fences. Do not widen affected surfaces, compatibility dispositions, migrations, dependency changes, or security policy without an authority decision recorded in the pack.

## Deterministic command sequence

Initialize an absent pack:

```bash
python3 <skill-root>/scripts/clone_pack.py enhancement-init \
  --product-name "<name>" \
  --product-type <controlled-type> \
  --playbook <repeatable-playbook> \
  --enhancement-id ENH-001 \
  --title "<exact title>" \
  --change-type <repeatable-controlled-type> \
  --request-file <repository-relative-request-file> \
  --repo-root <repository-root> \
  --output-dir <absent-repository-relative-pack-path> \
  --timestamp <rfc3339-utc>
```

Add `--adopt-dirty` only for the explicit dirty-tree adoption described above.

Record the adopted repository oracle before implementation:

```bash
python3 <skill-root>/scripts/clone_pack.py repo-snapshot <pack> --role adopted --record
python3 <skill-root>/scripts/clone_pack.py repo-snapshot <pack> --role adopted --check
python3 <skill-root>/scripts/clone_pack.py validate <pack> \
  --profile repository-adopted --format json --max-problems 0
python3 <skill-root>/scripts/clone_pack.py enhancement-transition <pack> ENH-001 \
  --to READY --actor "<identity>" \
  --reason "Repository adopted and preservation contract frozen" \
  --evidence SNAP-001 --timestamp <rfc3339-utc>
```

Use repeatable `--include <repository-relative-path>` only for an ignored runtime input already declared in the repository inventory. It does not narrow the ordinary tracked/full-tree inventory. `.git` and the pack directory are excluded. Git repositories record a Git-aware snapshot; other repositories use a deterministic full-tree snapshot.

Before `enhancement-ready`, determine whether the selected enhancement contains a four-layer browser-to-persistence journey. If it does, load [Full-stack QA contract](full-stack-qa.md), copy the canonical template to `full_stack_qa_plan.json`, add `plans.full_stack_qa`, bind its canonical digest to one `ART` oracle and the indexed GATE, and pin the target-repository CI workflow. Pin `playwright.package` to `@playwright/test`, `playwright`, or `playwright-core` and its declared version. The runtime hashes but does not parse the lockfile or prove the package is installed; the repository wrapper owns that preflight. The required lane keeps every application-owned component `REAL`. Frontend, mid-tier, backend, and persistence are logical roles; two core roles may share a `service_id` only when their complete service declarations are identical. Declare each applicable queue, cache, or worker in `owned_stack.supporting_services` with its readiness contract, assertion, and proof artifact, reference its ID from at least one journey, and require the exact entry to pass in the canonical result.

Only external dependencies can be sandboxed, stubbed, or excluded, and every disposition requires recorded authority. Each non-excluded boundary records protocol, endpoint, a `LOOPBACK` or `AUTHORIZED_SANDBOX` classification, bounded readiness, assertion, proof artifact, and at least one journey reference; its exact canonical-result entry must be `PASS`. An excluded boundary uses the schema-defined null contracts and yields `NOT_APPLICABLE`, never provider proof. Pin the Playwright `project`, and bind the primary wire observation plus every declared `additional_exchanges` entry to the canonical result.

Each journey declares at least one `identity_bindings` entry. A `BIND-###` source identifies the exchange trigger and response JSON Pointer. Its consumers include a concrete additional-exchange path through `WIRE_PATH`, plus `SERVICE` and `PERSISTENCE` contract pointers; each pointed-to plan string contains the same `{binding_name}`. The result repeats that structure and requires `captured_value_sha256` to equal every consumer `observed_value_sha256`.

The plan CI argv, cwd, expected exit, `blocked_exit_codes: [7]`, artifact paths, and `fresh_artifact_paths` equal the indexed GATE, with `ci.result_path` in both artifact arrays. The target CI job and local evidence command execute that same no-shell argv. Tool versions `2.2.0` and `2.3.0` make `record-run` schema-validate the complete retained `execution_contract` before process execution. The repository-owned GATE wrapper preflights pinned capabilities before setup and browser behavior. Capability, startup, or readiness failure exits the declared `7`, which `record-run` retains as `BLOCKED` with exit `7`; a started behavioral assertion mismatch emits the failing canonical result and returns another nonzero code, which `record-run` retains as `FAIL` before returning `5`. A non-blocked invocation that leaves a required result unchanged is rejected as `RUN_ARTIFACT_STALE` with exit `4`. The clone-pack runtime never installs Playwright, Node packages, browser binaries, application services, or operating-system dependencies. Its validator checks readiness contracts and allowed HTTP origins but does not execute readiness probes, parse CI YAML, or query hosted checks.

Run each required preservation case against the adopted snapshot:

```bash
python3 <skill-root>/scripts/clone_pack.py baseline-run <pack> --case PRES-001
python3 <skill-root>/scripts/clone_pack.py baseline-run <pack> --all
python3 <skill-root>/scripts/clone_pack.py validate <pack> \
  --profile enhancement-ready --format json --max-problems 0
python3 <skill-root>/scripts/clone_pack.py enhancement-transition <pack> ENH-001 \
  --to IN_PROGRESS --actor "<identity>" \
  --reason "Enhancement-ready contract passed" --timestamp <rfc3339-utc>
```

The command preflights the selected set before execution and runs pinned argv arrays without a shell. A baseline result is immutable. An already-recorded case returns `BASELINE_IMMUTABLE`; do not replace it. An accepted existing failure requires the exact observed result plus a governed decision, rather than a changed expected exit.

After test-first implementation inside the declared fence, record the candidate while state is `IN_PROGRESS`, bind candidate gate results, then advance to `IMPLEMENTED` before regression and scope verification:

```bash
python3 <skill-root>/scripts/clone_pack.py repo-snapshot <pack> --role candidate --record
python3 <skill-root>/scripts/clone_pack.py repo-snapshot <pack> --role candidate --check
python3 <skill-root>/scripts/clone_pack.py record-run <pack> \
  --gate GATE-001 --environment ENV-001
python3 <skill-root>/scripts/clone_pack.py enhancement-transition <pack> ENH-001 \
  --to IMPLEMENTED --actor "<identity>" --reason "Candidate implementation complete" \
  --evidence SNAP-002 --timestamp <rfc3339-utc>
python3 <skill-root>/scripts/clone_pack.py regression <pack> --case PRES-001
python3 <skill-root>/scripts/clone_pack.py regression <pack> --all
python3 <skill-root>/scripts/clone_pack.py verify-scope <pack> --enhancement ENH-001
python3 <skill-root>/scripts/clone_pack.py assure <pack>
python3 <skill-root>/scripts/clone_pack.py enhancement-transition <pack> ENH-001 \
  --to VERIFIED --actor "<identity>" --reason "All declared verification passed" \
  --evidence SNAP-002 --evidence SCOPE-001 --evidence PRES-001 \
  --evidence RUN-001 --evidence ASSURE-001 --timestamp <rfc3339-utc>
python3 <skill-root>/scripts/clone_pack.py seal <pack> \
  --profile verified-enhancement --timestamp <rfc3339-utc>
python3 <skill-root>/scripts/clone_pack.py validate <pack> \
  --profile verified-enhancement --format json --max-problems 0
```

Use only evidence IDs present in the pack; omit `ASSURE-001` when no required assurance case exists. No command in this sequence deploys or merges.

`regression` compares candidate results with the immutable baseline and returns verification exit `5` on a preservation mismatch. `verify-scope` compares adopted and candidate state, reports `changed_paths`, rejects unauthorized paths, and preserves unrelated adopted dirty bytes.

Change enhancement state only through:

```bash
python3 <skill-root>/scripts/clone_pack.py enhancement-transition <pack> ENH-001 \
  --to <state> --actor "<identity>" --reason "<exact reason>" \
  --evidence <repeatable-record-id> --decision <repeatable-decision-id> \
  --timestamp <rfc3339-utc>
```

The forward lifecycle is `DRAFT -> READY -> IN_PROGRESS -> IMPLEMENTED -> VERIFIED`. `BLOCKED` retains its prior state for a legal unblock. `DECLINED` requires recorded authority. A backward transition requires the governed reason and evidence defined by the transition contract. The CLI appends canonical hash-chained events to `history/enhancement_events.jsonl`; never edit the current state or history by hand.

Recompute a digest only through an explicit target:

```bash
python3 <skill-root>/scripts/clone_pack.py rehash <pack> --record <record-id>
python3 <skill-root>/scripts/clone_pack.py rehash <pack> --case PRES-001
```

`--case` accepts an existing `CAP`, `PAR`, `ASSURE`, or `PRES` result. `rehash` does not create evidence, discover implicit targets, or convert a stale or failing result into proof.

## Profiles

Use the branch-aware profiles in order:

1. `repository-adopted` validates the brownfield workstream, repository inventory, request binding, adopted state, and required reciprocal records.
2. `enhancement-ready` adds an executable enhancement plan, affected-surface mapping, compatibility decisions, scope fence, preservation contract, implementation locations, and pinned gates.
3. `implementation` validates the retained planning and baseline evidence required by `enhancement-ready` plus lifecycle state `IN_PROGRESS`, `IMPLEMENTED`, or `VERIFIED`. Unlike `enhancement-ready`, it does not require the live repository to equal the adopted snapshot because authorized edits may exist. A pass proves retained contract and lifecycle state only; edit authorization comes from a successful `READY -> IN_PROGRESS` transition and the resulting `enhancement-build` mode. It does not validate candidate, preservation-regression, scope, assurance, or seal evidence.
4. `verified-enhancement` requires a current candidate snapshot, passing scope and preservation results, required assurance, complete enhancement history ending in `VERIFIED`, current proof, and an enhancement seal binding the adopted and candidate state.

When `plans.full_stack_qa` is present, `enhancement-ready` additionally validates the plan schema, repository file hashes, authority, trace, GATE/fresh-artifact equality, declared-real owned-service topology, identity bindings, supporting/external journey bindings, and proof artifacts. `verified-enhancement` additionally requires the latest linked `PASS` `RUN`; parses its canonical result for the pinned Playwright project, exact journey set, primary and additional wire exchanges, `BIND-###` captured/consumer hashes, supporting services, and external dependencies; and seals the manifest-bound plan. A missing or latest non-passing run is `HOLD`; result, contract, hash, trace, non-`REAL` declaration, and GATE errors block verification.

Run `validate <pack> --profile <profile> --format json --max-problems 0` and consume both canonical JSON and the process exit. Do not translate `FAIL`, `HOLD`, `BLOCKED`, or infrastructure exit `7` into success.

## Compatibility and migration decisions

For each affected public interface, persisted representation, dependency contract, configuration key, migration, flag, and telemetry signal, record either preservation or an authority-backed controlled disposition. A breaking change requires an explicit decision; silence is not compatibility evidence.

- Dependency upgrades bind the before/after dependency state, repository-native checks, dependency-review result, vulnerability and license deltas, rollback conditions, and any accepted finding authority.
- Data migrations use an expand-contract or other explicitly governed strategy. Validate before apply, make forward and rollback limits exact, never rewrite an applied migration, and retain compatibility evidence for mixed-version windows.
- Feature flags record default, targeting, ownership, expiry/removal condition, failure behavior, and behavior on flag-provider unavailability.
- Telemetry changes use stable semantic names and fields, redact sensitive values, and retain observable evidence rather than asserting operational coverage.

## Runtime and Codex CLI boundary

The clone-pack runtime imports only Python standard-library modules. It executes only pinned no-shell argv from the pack and never installs missing tools. Missing top-level executable, process-start failure, and timeout produce deterministic blocked run evidence and exit `7`. For the optional QA gate, the repository wrapper also exits its declared blocked code `7` when preflight, startup, or readiness cannot complete; `record-run` retains that started process as `BLOCKED` and returns `7`. A started behavioral mismatch is `FAIL` with exit `5`. Declared run artifacts are copied only after containment, regular-file, hash, redaction, and required-freshness checks; unchanged `fresh_artifact_paths` yield `RUN_ARTIFACT_STALE` and exit `4`. Runtime validation does not execute readiness probes, parse the lockfile, prove package installation, parse CI YAML, or inspect hosted branch-protection checks.

A passing optional full-stack GATE proves only the declared UI action, observed request and response, named API or data postcondition, persistence observation, and retained environment. It does not prove unobserved mid-tier control flow, database constraints, background jobs, external provider behavior, production deployment, or undeclared browser environments.

Codex CLI filesystem, network, and approval limits remain authoritative. Do not evade a sandbox or approval by changing command shape, writing outside the authorized repository, or substituting an unrecorded external tool. If a required action is unavailable, retain the exact blocker and stop at the highest honestly passing profile.

The workflow ends at a verified repository handoff. It does not deploy, publish, mutate production, roll back production, or merge.

## Handoff

Return these exact fields:

- mode
- enhancement ID
- change types
- adopted snapshot
- candidate snapshot
- affected surfaces
- compatibility decisions
- changed paths
- command results
- preservation results
- security and dependency deltas
- residual gaps
- seal path
- blockers

State explicitly whether implementation was permitted and performed. A passing handoff means repository evidence is current; it does not expand the recorded authority or delivery boundary.
