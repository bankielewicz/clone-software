# CLI reference

The unified entry point is:

```bash
python3 "<skill-root>/scripts/clone_pack.py" <command> [arguments]
```

Run the command from any directory. Resolve `<skill-root>` to the directory containing this repository's `SKILL.md`. Resolve `<pack>` to the directory containing `clone_pack.json`.

The CLI imports only Python standard-library modules. It does not install packages, drivers, scanners, compilers, or comparators.

## Command index

| Command | Read/write class | Primary result channel |
| --- | --- | --- |
| `init` | Creates one absent pack directory | Text stdout |
| `validate` | Read-only | JSON stdout for every validation result; text stdout on pass and text diagnostics on stderr for failure/hold |
| `migrate --check` | Read-only | JSON stdout |
| `migrate` | Creates one absent v2 successor | Text stdout |
| `capture` | Writes immutable evidence and updates capture plan | JSON stdout |
| `parity` | Writes immutable comparison evidence and updates parity plan | JSON stdout |
| `scaffold` | Preview is read-only; `--apply` writes an absent scaffold and updates plan | JSON stdout |
| `record-run` | Executes a gate, writes run/artifact evidence, updates index | JSON stdout |
| `record-manual` | Writes an attestation run and updates index | JSON stdout |
| `gap-transition` | Updates index, append-only history, and derived Markdown flag | JSON stdout |
| `assure` | Executes assurance, writes evidence, updates plan | No stdout result; exit status and files are authoritative |
| `seal` | Updates governed states/hashes and writes or archives a seal | JSON stdout |
| `diff` | Read-only index-record comparison | Text or JSON stdout |

Expected command errors print `DIAGNOSTIC_CODE: message` to stderr. They do not use a JSON error envelope.

## Common timestamp option

`--timestamp` is accepted only by:

```text
init migrate capture record-run record-manual gap-transition seal
```

The value MUST be an offset-bearing ISO-8601 timestamp. The runtime normalizes it to UTC.

The option exists for deterministic fixtures and pinned records; it does not freeze external processes or the wall clock. In particular, `record-run` uses the supplied timestamp for `started_at`, while `ended_at` and elapsed duration come from the live execution clock.

## `init`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" init \
  --product-name <single-line-name> \
  --product-type <controlled-type> \
  [--playbook <controlled-playbook>]... \
  --source-description <single-line-description> \
  [--repo-root "<existing-directory>"] \
  [--output-dir "<repository-relative-or-contained-absolute-path>"] \
  [--timestamp <offset-bearing-ISO-8601>]
```

Defaults:

- `--repo-root`: current working directory.
- `--output-dir`: `docs/clone` below the repository root.
- `--playbook`: empty user-supplied list. The runtime adds the matching playbook for a non-hybrid product.
- `--timestamp`: current UTC time.

`--product-type` accepts:

```text
ai-ml-system api-service-server browser-extension cli client-app
data-pipeline database-storage distributed-realtime embedded-iot
game-simulation hybrid library-sdk web-app-saas website
```

Every `--playbook` accepts the same set except `hybrid`. A hybrid requires at least two distinct playbooks.

Preconditions:

- repository root exists and is a directory;
- output is inside that root;
- output is not equal to the root;
- output does not exist; and
- name and description are nonempty single lines without control characters.

Mutation:

- creates the pack directory, ten Markdown documents, four JSON plans, manifest, index, run/evidence directories, and gap-event history;
- never overwrites an existing output;
- on initialization failure, removes only the destination it created.

`--source-description` is stored as descriptive input. It is not parsed, authenticated, hashed, or verified by `init`.

Exit `0` means creation completed. Invalid input or target normally exits `2`.

## `validate`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  [--profile <profile>] \
  [--format text|json] \
  [--max-problems <nonnegative-integer>]
```

Defaults:

- profile: `scaffold`;
- format: `text`;
- maximum text diagnostics: `100`.

`--max-problems 0` means unlimited. The option limits rendered text diagnostics only; JSON contains every diagnostic.

Profiles:

```text
scaffold baseline-ready spec-ready build-ready verified-mvp
gap-plan gap-closure closed
```

The command is read-only. For v2 JSON output, the stable result fields are `schema_version`, `profile`, `status`, and `diagnostics`. Status is `PASS`, `FAIL`, or `HOLD`.

V1 input receives legacy structural validation. It does not receive v2 readiness certification. Requests for `verified-mvp`, `gap-closure`, or `closed` explicitly return `MIGRATION_REQUIRED`; migrate before making any v2 claim.

Typical exits are `0` pass, `1` contract/schema failure, `4` integrity failure, `5` hold, and `3` unsupported schema or migration required.

## `migrate`

### Preflight syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" migrate "<v1-source>" \
  --check [--mapping "<mapping.json>"]
```

`--check` takes precedence if `--output` is also supplied. It writes nothing, does not inspect a destination, and prints a `clone-migration-check/v2` JSON object. Exit `0` means the source is unambiguous under the supplied mapping; exit `6` means occurrence mapping is incomplete. Unsupported schema exits `3`.

### Migration syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" migrate "<v1-source>" \
  --output "<absent-v2-directory>" \
  [--mapping "<mapping.json>"] \
  [--timestamp <offset-bearing-ISO-8601>]
```

Without `--check`, `--output` is required. The destination parent must exist. The destination must be absent, must differ from the source, and must not be a child of the source.

When preflight reports `ambiguous_candidates`, the mapping is one JSON object from every reported occurrence key to one unique same-kind destination ID. Missing keys, additional unknown keys, wrong-kind IDs, or duplicate destination IDs block migration.

Migration:

- creates a non-overwriting v2 successor;
- archives exact source bytes and SHA-256 values;
- preserves pack lineage and resolved record IDs;
- records fixed ordered transformations and structured losses;
- downgrades unverifiable v1 status; and
- leaves the v1 source unchanged.

Migration always sets `required_reconciliation: true`.

## `capture`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" capture "<pack>" \
  (--case <CAP-ID> | --all) \
  [--resume] \
  [--timestamp <offset-bearing-ISO-8601>]
```

Exactly one selector is required. Unknown case ID is an invocation error.

Before executing any selected case, the runner preflights the complete selected set: case schema, same-ID index counterpart, authority traces, plan hashes, paths, destinations, executables, lifecycle commands, environment indirection, base64 fields, manual sources, and filesystem roots. Batch order is lexical by capture ID.

Each case writes to `evidence/captures/.<CAP-ID>.staging`, verifies the complete declared inventory, then atomically promotes to `evidence/captures/<CAP-ID>`. A final directory is never overwritten.

`--resume`:

- verifies pack identity, repository identity, case hash, result pointer, manifest hash, ownership marker, and artifact digests;
- skips any current finalized `PASS`, `FAIL`, or `BLOCKED` result;
- preserves the original nonzero state for skipped non-passing results;
- removes only a current runner-owned incomplete staging directory after full selected-set preflight; and
- never retries a finalized result at the same ID.

Use a new capture ID to acquire replacement evidence.

The output is a single capture result or `clone-capture-batch-result/v2` JSON object. A top-level capture `PASS` means evidence acquisition passed. It does not interpret HTTP status, process exit, response body, or business outcome. Read the adapter summary and retained artifacts.

Typical exits are `0` acquisition pass, `1` acquisition/contract failure, `7` infrastructure blocked, `4` integrity/path failure, and `2` unknown case or invalid selector.

Read [Capture and parity contract](../references/capture-and-parity.md) before authoring cases.

## `parity`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" parity "<pack>" --case <PAR-ID>
```

Prerequisites:

- same-ID current `PAR` index counterpart;
- required current reference and clone capture results with acquisition `PASS`;
- identical environment IDs;
- current case, baseline, repository revision/diff, artifact, and authority hashes;
- absent `evidence/parity/<PAR-ID>` destination; and
- installed local comparator driver for custom or perceptual-image comparison.

The command writes `evidence/parity/<PAR-ID>/result.json`, hashes all retained artifacts, and updates the parity plan result pointer. A match exits `0`. A comparison mismatch is retained and exits `5`. Stale or corrupt evidence may exit `4` or `5`; unknown case exits `2`.

A driver failure can leave a diagnostic output directory that blocks reuse of the same ID. Preserve it, map the failure, and assign a new parity ID when replacement execution is required.

## `scaffold`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" scaffold "<pack>" [--apply]
```

Without `--apply`, the command previews the exact pinned catalog profile and returns JSON without creating files. Preview still checks for destination collisions.

With `--apply`, the command exclusively creates every catalog file and sets `scaffold_plan.json` `applied` to `true`. It does not execute the returned setup, test, build, or run argv and does not access the network.

Supported profile IDs are:

```text
static-web-esm python-src typescript-src rust-crate not-applicable
```

`not-applicable` is the exact brownfield sentinel and creates no files. There is no custom scaffold mode.

If apply fails, the command removes only files and directories it created. A collision or contract mismatch normally exits `1`; an unsafe path may exit `4`.

## `record-run`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate <GATE-ID> \
  --environment <ENV-ID> \
  [--timestamp <offset-bearing-ISO-8601>]
```

The indexed `GATE` supplies direct argv, cwd, environment map, expected exit, timeout, coverage, oracle IDs, normalizations, and redaction metadata. `--environment` selects the indexed environment identity. The runner uses no shell.

When the child process returns, the command retains its result, including expected-exit mismatch. It creates `runs/RUN-###.json`, stdout/stderr artifacts, a same-ID `RUN` index record, and reciprocal backlinks. It does not read or retain a gate `artifact_paths` field. A missing executable, start failure, or timeout exits `7` before run/artifact creation.

Gate stdout and stderr are raw. Redaction declarations copied into run metadata are not applied to those bytes. Gate commands MUST NOT emit secrets, credentials, personal data, or unauthorized content.

Exit `0` means the observed exit equals the gate's expected exit. Mismatch exits `5`. Missing executable or timeout exits `7`.

## `record-manual`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-manual "<pack>" \
  --test <TEST-ID> \
  --procedure "<procedure-file>" \
  --observer <identity> \
  --authority <authority> \
  --artifact <pack-relative-path> \
  [--artifact <additional-pack-relative-path>]... \
  [--timestamp <offset-bearing-ISO-8601>]
```

This command records an observation already performed. It does not execute the procedure.

The selected `TEST` MUST identify a manual procedure and pin `attributes.manual_procedure_sha256`. The supplied file MUST match that hash. At least one artifact is required.

The command copies the procedure into the run artifact directory. It hashes supplied pack-relative evidence artifacts in place and records references to them; it does not copy those artifacts into the run directory. The artifact paths therefore MUST already exist beneath the pack and remain immutable.

On acceptance, it creates a `PASS` manual run, index record, and backlinks, then exits `0`.

## `gap-transition`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" gap-transition "<pack>" <GAP-ID> \
  --to <status> \
  --actor <identity> \
  --reason <single-line-reason> \
  [--evidence <ID>]... \
  [--decision <DEC-ID>]... \
  [--timestamp <offset-bearing-ISO-8601>]
```

Legal edges are:

```text
OPEN -> IN_PROGRESS
OPEN -> BLOCKED
BLOCKED -> OPEN
OPEN -> DECLINED
BLOCKED -> DECLINED
IN_PROGRESS -> IMPLEMENTED
IMPLEMENTED -> VERIFIED
IMPLEMENTED -> IN_PROGRESS
VERIFIED -> OPEN
```

Each edge enforces its readiness, dependency, decision, run, parity, assurance, closure, or contrary-evidence prerequisites. The command stages `clone_index.json`, the hash-chained `history/gap_events.jsonl`, and derived `NO-OPEN-GAPS` in `gaps_analysis.md`, then replaces the files sequentially. The update is not transactional; interruption after a replacement can leave divergence.

Do not edit any of those three lifecycle states by hand. After an interrupted transition, reconcile all three before another transition.

## `assure`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" assure "<pack>" \
  [--case <ASSURE-ID>]...
```

Omitting `--case` selects every plan case. Repeating it selects the named set. Unknown ID exits `2`.

The runner refuses all selected output collisions before execution, invokes direct argv without installation, retains raw stdout/stderr and configured artifacts under `evidence/assurance/<ASSURE-ID>`, and updates `assurance_plan.json`.

The command prints no result object. Inspect its process exit and retained plan/evidence.

Each retained case status is authoritative. A mismatch sets aggregate exit `5`; a blocked case sets aggregate exit `7`; later cases can overwrite that aggregate, so mixed blocked/failed sets are order-dependent. Inspect every selected result. An empty plan can exit `0`, but it provides no assurance evidence and does not satisfy readiness profiles requiring assurance kinds.

## `seal`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" seal "<pack>" \
  --profile verified-mvp|gap-closure|closed \
  [--timestamp <offset-bearing-ISO-8601>]
```

The command first validates the requested profile without requiring a pre-existing seal. It refuses to seal a failing or held derived state.

On success it:

- computes governed file hashes;
- updates every governed Markdown document state and manifest entry hash;
- updates manifest state;
- writes `seal.json`; and
- archives an existing prior seal when creating a valid higher-revision successor.

A successor seal requires a greater `pack_revision` bound consistently across manifest, index, plans, and document frontmatter. Tool `2.0.0` does not require `clone_pack.json.supersedes` and does not validate predecessor seal hashes before archiving; the operator performs those lineage checks separately.

The generated seal is an unsigned integrity manifest. It is not a cryptographic signature or release attestation.

## `diff`

### Syntax

```bash
python3 "<skill-root>/scripts/clone_pack.py" diff "<left-v2-pack>" "<right-v2-pack>" \
  [--format text|json]
```

Default format is text. The command is read-only.

It compares exact `clone_index.json` record objects by stable ID and reports added, removed, and changed IDs. It does not compare Markdown documents, manifests, plan objects outside indexed records, evidence bytes, history, runs, or seals.

Differences still exit `0`; the output is data, not a pass/fail verdict. Unsupported non-v2 input exits `3`.

## Exit status contract

| Exit | Meaning | Required response |
| --- | --- | --- |
| `0` | Requested command-level contract completed | Continue only to the next declared gate; inspect output semantics |
| `1` | Contract, schema, graph, or trace violation | Correct the named artifact; do not certify |
| `2` | Invalid argument, unknown selected ID, or unsafe requested target | Correct the invocation |
| `3` | Unsupported schema or capability mode | Select supported input or migrate |
| `4` | Integrity, hash, seal, artifact, or path violation | Treat affected retained state as untrusted until reconciled |
| `5` | Honest validation hold, expected-exit mismatch, or comparison failure | Preserve evidence and create, block, or update the mapped gap |
| `6` | Migration ambiguity or destination failure | Resolve occurrence mapping or destination contract |
| `7` | Required executable, adapter, timeout boundary, or infrastructure unavailable | Install or authorize outside the skill, or record a blocker |
| `70` | Unexpected internal exception | Preserve stderr and stop |
| `130` | User/process interruption | Inspect runner-owned staging before using capture resume |

An exit `0` never broadens the command's meaning. For example, capture exit `0` proves acquisition, diff exit `0` proves comparison execution, and assurance exit `0` proves only the selected nonempty executed set passed.

## Compatibility scripts

- `scripts/new_clone_pack.py` creates legacy clone-pack/v1. It is retained for compatibility and MUST NOT start new v2 work.
- `scripts/validate_clone_pack.py` dispatches v1 structural validation or v2 `scaffold`/`verified-mvp` compatibility checks. It does not expose the complete profile interface.
- `scripts/run_skill_tests.py` runs the full test suite and has no command-line parser. Passing `--help` still runs tests.
