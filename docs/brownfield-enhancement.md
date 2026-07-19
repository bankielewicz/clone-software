# Brownfield enhancement workflow

This guide describes the implemented tool `2.1.0` workflow for evidence-grounded changes to an existing repository. It covers additive features, behavior changes, refactors, dependency upgrades, data migrations, security hardening, and operations changes. The runtime remains Python standard-library only and works through Codex CLI or the direct `scripts/clone_pack.py` entry point.

The workflow adopts the repository as an immutable before-state, plans one bounded enhancement, proves preserved behavior and allowed scope against a candidate after-state, and seals only current evidence. It is not a deployer, package installer, merge bot, or substitute for authority over the repository and its systems.

## Select the operating mode

| Requested outcome | Mode | Product-code permission | Terminal result |
| --- | --- | --- | --- |
| Inspect an existing repository and produce an executable enhancement plan | `enhancement-plan` | Forbidden | Passing `enhancement-ready`, or exact blockers |
| Implement and verify the selected enhancement | `enhancement-build` | Allowed only after `enhancement-ready` | Passing sealed `verified-enhancement`, or exact blockers |

The `implementation` phase begins only after the exact plan passes `enhancement-ready`. Changing product code in `enhancement-plan` is a contract violation. Neither mode authorizes deployment, publication, production mutation, or merge.

## Inputs that must be pinned

Before initialization, record:

- requester and authority basis;
- repository root and intended base revision;
- one `ENH-###` identifier, exact title, and one or more controlled change types;
- a repository-contained UTF-8 request file;
- affected product surfaces and prohibited paths;
- public-interface, data, security, dependency, migration, flag, and telemetry constraints that apply;
- repository-native commands and expected outcomes;
- secret, personal-data, artifact-retention, and redaction policy;
- delivery target and actions outside authority.

The controlled change types are `feature`, `behavior-change`, `refactor`, `dependency-upgrade`, `data-migration`, `security-hardening`, and `operations`.

## Initialize without mutating the product

Use an absent repository-relative output directory:

```bash
python3 "<skill-root>/scripts/clone_pack.py" enhancement-init \
  --product-name "Authorized Inventory Service" \
  --product-type hybrid \
  --playbook web-app-saas \
  --playbook api-service-server \
  --enhancement-id ENH-001 \
  --title "Add an authorized export endpoint" \
  --change-type feature \
  --request-file docs/requests/ENH-001.md \
  --repo-root "<repository-root>" \
  --output-dir docs/enhancements/ENH-001 \
  --timestamp 2026-07-19T12:00:00Z
```

`--request-file` must resolve below the repository root to a non-empty UTF-8 regular file and must not be a symlink. The command retains the request under `evidence/requests/ENH-001/request.md` and records the source path and SHA-256 digest.

By default, any pre-existing Git worktree change stops with exit `4` and `REPOSITORY_DIRTY`; repository and pre-existing bytes remain unchanged. Use `--adopt-dirty` only when the requester explicitly adopts those exact changes as protected input. The inventory and scope then bind each protected dirty path so the later enhancement cannot absorb or overwrite it silently.

On success, stdout is canonical JSON containing only the stable result fields `enhancement_id`, absolute `pack_path`, and `status`. Initial status is `DRAFT`. The command creates the pack only; it does not edit product code, stage changes, commit, run a package manager, contact GitHub, or update evidence implicitly.

The new pack remains `clone-pack/v2`. Its optional workstream is `brownfield-enhancement`, its mode is `enhancement-plan` or `enhancement-build`, and its plans include:

- `repository_inventory.json` with schema `clone-repository-inventory/v2`;
- `enhancement_plan.json` with schema `clone-enhancement-plan/v2`.

Legacy v2 manifests without these optional fields remain valid for their original workflows.

## Adopt the repository oracle

Record and immediately check the before-state:

```bash
python3 "<skill-root>/scripts/clone_pack.py" repo-snapshot "<pack>" --role adopted --record
python3 "<skill-root>/scripts/clone_pack.py" repo-snapshot "<pack>" --role adopted --check
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile repository-adopted --format json --max-problems 0
```

`repo-snapshot` recognizes Git and filesystem repositories. It excludes `.git` and the pack directory. Repeat `--include <repository-relative-path>` only for an ignored runtime input already declared in the repository inventory; it does not narrow the ordinary tracked/full-tree inventory. `--record` creates an immutable `SNAP-###` record; `--check` compares current bytes with that record without replacing it. A mismatch reports `DRIFT`, expected and actual hashes, and exit `4`.

The `repository-adopted` profile requires a valid workstream, repository inventory, request binding, adopted snapshot, and reciprocal `ENH`, `SNAP`, and affected-record links. It does not authorize implementation.

After that profile passes, advance `DRAFT -> READY`. Baseline execution is state-gated to `READY`:

```bash
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 \
  --to READY --actor "<identity>" \
  --reason "Repository adopted and preservation contract frozen" \
  --evidence SNAP-001 --timestamp 2026-07-19T12:30:00Z
```

## Freeze preservation and scope

The enhancement plan names every affected surface and compatibility decision, maps each allowed path to exactly one controlled change record, and defines the behavior that must survive. Each `PRES-###` case uses a pinned argv array, working directory, environment indirection, expected result, timeout, and evidence pointers. Shell strings and implicit package installation are rejected.

Run required preservation cases against the adopted state:

```bash
python3 "<skill-root>/scripts/clone_pack.py" baseline-run "<pack>" --case PRES-001
python3 "<skill-root>/scripts/clone_pack.py" baseline-run "<pack>" --all
```

Both forms preflight the complete selected set before running any case. A recorded baseline is immutable; repeating it returns `BASELINE_IMMUTABLE`. If the adopted repository has a known failure, retain the exact observed failure and bind the authority decision that accepts it. Do not change the oracle to make a later result pass.

After all required immutable baselines exist, validate the complete plan:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile enhancement-ready --format json --max-problems 0
```

The `enhancement-ready` profile adds complete affected-surface, preservation, path-scope, implementation-location, compatibility, dependency, security, migration, and repository-gate contracts. A pass permits the bounded `implementation` phase only in `enhancement-build` mode.

## Implement within the fence

During `implementation`:

1. transition `READY -> IN_PROGRESS` through `enhancement-transition`;
2. write and run a discriminating failing test before product implementation;
3. make the smallest behavior change inside the authorized paths;
4. run focused tests, then repository-wide gates;
5. record and check the candidate snapshot while state is `IN_PROGRESS`;
6. retain candidate-bound command results and declared artifacts through `record-run`;
7. record any new affected surface or compatibility choice as a decision before changing it;
8. transition `IN_PROGRESS -> IMPLEMENTED` with the current candidate `SNAP-###` as evidence.

Codex CLI sandbox and approval decisions remain binding. The tool does not install missing compilers, scanners, browsers, package managers, or adapters. A missing executable, start failure, or timeout produces deterministic blocked evidence and infrastructure exit `7`; it does not become a skipped pass.

## Verify candidate behavior and scope

The exact candidate/state sequence is:

```bash
python3 "<skill-root>/scripts/clone_pack.py" repo-snapshot "<pack>" --role candidate --record
python3 "<skill-root>/scripts/clone_pack.py" repo-snapshot "<pack>" --role candidate --check
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 \
  --to IMPLEMENTED --actor "<identity>" --reason "Candidate implementation complete" \
  --evidence SNAP-002 --timestamp 2026-07-19T13:00:00Z
python3 "<skill-root>/scripts/clone_pack.py" regression "<pack>" --case PRES-001
python3 "<skill-root>/scripts/clone_pack.py" regression "<pack>" --all
python3 "<skill-root>/scripts/clone_pack.py" verify-scope "<pack>" --enhancement ENH-001
```

`regression` compares candidate results with immutable baseline results. A behavioral mismatch is a verification failure with exit `5` and retained comparison evidence. `verify-scope` compares adopted and candidate snapshots, emits canonical JSON with `changed_paths`, and returns `FAIL` plus `unauthorized_paths` when any delta lacks exactly one allowed change mapping. Adopted dirty paths remain protected: an unrelated pre-existing byte change is never counted as authorized enhancement work.

Run required assurance by default, or intentionally include optional cases:

```bash
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>"
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>" --all
```

The selected set is preflighted before execution. Canonical JSON reports results; aggregate exits use precedence `7`, then `5`, then `0`. Required assurance, preservation, scope, and lifecycle evidence are bound into the final profile and seal.

## Lifecycle and explicit digest repair

The forward lifecycle is:

```text
DRAFT -> READY -> IN_PROGRESS -> IMPLEMENTED -> VERIFIED
```

Change state only with `enhancement-transition`. `BLOCKED` stores its prior state for legal unblocking. `DECLINED` requires recorded authority. Reopen or backward edges require the exact governed reason, evidence, and decision. Events are canonical, sequence-numbered, and hash-chained in `history/enhancement_events.jsonl`; a manually edited plan status is not lifecycle proof.

Use `rehash` only when a governed record or existing result legitimately changed and the workflow authorizes rebinding:

```bash
python3 "<skill-root>/scripts/clone_pack.py" rehash "<pack>" --record <record-id>
python3 "<skill-root>/scripts/clone_pack.py" rehash "<pack>" --case PRES-001
```

Repeat `--record` and `--case` to select one or more explicit existing definitions. A case selector accepts `CAP`, `PAR`, `ASSURE`, or `PRES` definitions only while their retained result pointer is unfinalized. Finalized evidence is immutable and returns `FINALIZED_EVIDENCE_IMMUTABLE`. The command does not discover evidence, create a result, repair a failed command, or advance a lifecycle.

After current evidence supports the final transition, execute:

```bash
python3 "<skill-root>/scripts/clone_pack.py" enhancement-transition "<pack>" ENH-001 \
  --to VERIFIED --actor "<identity>" --reason "All declared verification passed" \
  --evidence SNAP-002 --evidence SCOPE-001 --evidence PRES-001 \
  --evidence RUN-001 --evidence ASSURE-001 \
  --timestamp 2026-07-19T13:30:00Z
python3 "<skill-root>/scripts/clone_pack.py" seal "<pack>" \
  --profile verified-enhancement --timestamp 2026-07-19T13:31:00Z
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile verified-enhancement --format json --max-problems 0
```

Use only evidence IDs that exist in the pack; omit `ASSURE-001` when the plan has no required assurance case. The seal binds the enhancement plan, request, adopted snapshot, candidate snapshot, scope result, preservation baseline and regression results, required assurance, current runs, lifecycle history, and governed pack files. For a higher revision, retain the predecessor seal and set `supersedes` to its schema, pack ID, revision, manifest SHA-256, and seal SHA-256 before sealing.

## Dependency, migration, flag, and telemetry cases

### Dependency upgrades

Bind the dependency source and before/after state, repository-native resolution and test commands, dependency-review output, vulnerability and license deltas, transitive changes, compatibility decision, rollback point, and accepted-finding authority. GitHub dependency review detects dependency-graph changes in pull requests; it does not replace runtime, license-authority, or exploitability analysis.

### Data migrations

Record schema and data invariants, forward and rollback boundaries, mixed-version compatibility, backup/restore prerequisites, idempotency, and validation commands. Prefer a governed expand-contract sequence when compatibility requires it. Never edit an applied migration or label production rollback as performed by this tool.

### Feature flags

Record flag key, default, targeting authority, degraded behavior when the provider is unavailable, telemetry, owner, and removal condition. A flag is a compatibility mechanism, not proof that both branches work; retain evidence for both required paths.

### Telemetry

Record stable event/metric/span names, semantic fields, units, cardinality limits, redaction, sampling, and observable fixtures. Telemetry evidence proves only the exercised environment and retained signal.

## Security and retained evidence

Gate commands execute as no-shell argv with an explicit working directory, timeout, and environment-variable indirection for secret-like values. `record-run` retains stdout, stderr, and declared artifacts only after containment and file-type checks. Textual retained evidence is redacted according to its governed rules. Missing executable, start failure, and timeout retain a blocked result rather than leaving an ambiguous absence.

SARIF is accepted only as an explicitly declared artifact with its producing tool, invocation, result policy, digest, and redaction contract. A SARIF file does not by itself establish that findings are resolved.

## Completion and handoff

The `verified-enhancement` profile requires a current candidate snapshot, passing scope result, passing required preservation and assurance cases, a complete hash-chained enhancement history ending in `VERIFIED`, and a current enhancement seal. Return the exact machine status and exit code; do not broaden it into production readiness.

The handoff contains these exact fields:

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

State which Codex CLI approvals were used and which external actions were unavailable. The result is a repository-level verified handoff only: it is not deployed or merged.

## Research basis

These sources informed the contract boundaries. They are references, not proof that a particular enhancement satisfies them.

- SEI, [Architecture Reconstruction Guidelines, Third Edition](https://www.sei.cmu.edu/library/architecture-reconstruction-guidelines-third-edition/): recover and verify architecture from repository evidence before assigning change locations.
- NISTIR 6407, [Information Technology Security Service](https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir6407.pdf): preserve explicit security requirements and validation evidence.
- Git, [`git status` documentation](https://git-scm.com/docs/git-status.html): define the Git worktree/index state used by clean and adopted-dirty handling.
- [Semantic Versioning 2.0.0](https://semver.org/): record compatibility decisions without treating a version label as compatibility proof.
- NIST SP 800-218, [Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final): connect change, security, provenance, and verification records.
- GitHub, [Dependency review](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review): review dependency-graph deltas in pull requests.
- OASIS, [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html): retain structured static-analysis results with explicit producer and policy.
- Flyway, [`validate`](https://documentation.red-gate.com/flyway/reference/commands/validate): distinguish migration validation from migration execution and production rollback.
- OpenFeature, [specification](https://openfeature.dev/specification/): pin feature-flag evaluation concepts and provider failure behavior.
- OpenTelemetry, [semantic conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/): use stable observable names and attributes.
- OpenAI, [Build skills](https://learn.chatgpt.com/docs/build-skills.md): install and route the skill through supported Codex discovery.
- OpenAI, [Sandbox and approvals](https://learn.chatgpt.com/docs/agent-approvals-security#sandbox-and-approvals): keep filesystem, network, and external-action claims within Codex CLI authority.
