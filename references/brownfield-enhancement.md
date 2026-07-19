# Brownfield enhancement contract

Load this reference when the user asks to enhance, extend, modernize, refactor, upgrade, migrate, or harden an existing repository. It governs both `enhancement-plan` and `enhancement-build` workstreams in tool `2.1.0`.

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
- `enhancement_plan.json`, schema `clone-enhancement-plan/v2`, for the request binding, change types, affected surfaces, compatibility dispositions, delivery strategy, preservation cases, scope, and enhancement state.

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
3. `implementation` is the human workflow phase after `enhancement-ready`; it is not a validation profile and is forbidden in `enhancement-plan` mode.
4. `verified-enhancement` requires a current candidate snapshot, passing scope and preservation results, required assurance, complete enhancement history ending in `VERIFIED`, current proof, and an enhancement seal binding the adopted and candidate state.

Run `validate <pack> --profile <profile> --format json --max-problems 0` and consume both canonical JSON and the process exit. Do not translate `FAIL`, `HOLD`, `BLOCKED`, or infrastructure exit `7` into success.

## Compatibility and migration decisions

For each affected public interface, persisted representation, dependency contract, configuration key, migration, flag, and telemetry signal, record either preservation or an authority-backed controlled disposition. A breaking change requires an explicit decision; silence is not compatibility evidence.

- Dependency upgrades bind the before/after dependency state, repository-native checks, dependency-review result, vulnerability and license deltas, rollback conditions, and any accepted finding authority.
- Data migrations use an expand-contract or other explicitly governed strategy. Validate before apply, make forward and rollback limits exact, never rewrite an applied migration, and retain compatibility evidence for mixed-version windows.
- Feature flags record default, targeting, ownership, expiry/removal condition, failure behavior, and behavior on flag-provider unavailability.
- Telemetry changes use stable semantic names and fields, redact sensitive values, and retain observable evidence rather than asserting operational coverage.

## Runtime and Codex CLI boundary

The clone-pack runtime imports only Python standard-library modules. It executes only pinned no-shell argv from the pack and never installs missing tools. Missing executable, process-start failure, and timeout produce deterministic blocked run evidence. Declared run artifacts are copied only after containment, regular-file, hash, and redaction checks.

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
