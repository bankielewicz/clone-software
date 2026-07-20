# Contributing

This repository contains a security-sensitive specification and evidence tool. A change is complete only when runtime behavior, schemas, templates, references, human documentation, and tests agree.

The repository contents are dedicated to the public domain under **CC0 1.0 Universal**. The canonical dedication and fallback terms are in [LICENSE](../LICENSE). By submitting material for inclusion, you agree that it may be distributed under CC0. Submit only material that you have authority to dedicate under CC0; do not submit third-party content, code, data, or other material without compatible documented terms.

## Development environment

The runtime imports only Python standard-library modules. The verified local environment for the current baseline is Python 3.12.3.

From the repository root, confirm the CLI:

```bash
python3 scripts/clone_pack.py --help
```

Do not run `scripts/run_skill_tests.py --help`; that script has no argument parser and executes the suite for any supplied arguments.

## Source map

| Path | Responsibility |
| --- | --- |
| `SKILL.md` | Compact Codex workflow and resource routing |
| `agents/openai.yaml` | Codex display name, description, and default prompt |
| `scripts/clonepack/cli.py` | Argument parser, dispatch, output channel, and exception boundary |
| `scripts/clonepack/constants.py` | Schemas, controlled vocabularies, ID patterns, profiles, gap states, and exits |
| `scripts/clonepack/common.py` | Canonical JSON, hashes, safe paths, atomic writes, and errors |
| `scripts/clonepack/pack.py` | v2 initialization, validation profiles, trace/proof checks, and seals |
| `scripts/clonepack/operations.py` | Capture, parity, run, manual attestation, and assurance execution |
| `scripts/clonepack/full_stack_qa.py` | Optional full-stack plan contract hashing, repository-file binding, authority/trace/GATE checks, and verified-journey run proof |
| `scripts/clonepack/lifecycle.py` | Gap transition prerequisites and append-only event history |
| `scripts/clonepack/dossier.py` | Machine gap-dossier validation against repository truth |
| `scripts/clonepack/evolution.py` | v1 migration, successor rules, and index-record diff |
| `scripts/clonepack/scaffold.py` | Audited scaffold catalog validation, preview, apply, and rollback |
| `scripts/clonepack/schema.py` | Packaged Draft 2020-12 schema evaluator |
| `assets/templates-v2/` | Source artifacts copied by v2 initialization |
| `assets/schemas/` | Exact machine schemas |
| `assets/scaffolds/` | Audited dependency-free skeletons and catalog |
| `assets/prompts/` | Checked-in cold-session evaluation requests copied by supported installers |
| `references/` | Normative operational and product contracts loaded by Codex |
| `docs/` | Human-facing repository usage documentation |
| `scripts/install_clone_software_wsl.sh` | Collision-refusing isolated WSL skill/trial installer |
| `scripts/check_wsl_trial_workspace.py` | Read-only v2 receipt, installed-input, Git-object-ID, checkout-identity, and optional runtime-directory checker |
| `tests/` | Offline regression, migration, lifecycle, freshness, path, and adversarial security proof |

## Change procedure

1. Identify the exact user-visible or validator contract that changes.
2. Add a failing discriminating test before changing runtime behavior when the change is executable.
3. Update the smallest implementation surface.
4. Update every affected schema and source template together.
5. Update `SKILL.md` only when the agent workflow or routing changes.
6. Update the relevant `references/` contract when normative behavior changes.
7. Update `README.md`, `docs/cli-reference.md`, workflow/authoring/troubleshooting documentation, and `changelog.md` when a public behavior or command changes.
8. Run focused tests for the touched boundary.
9. Run the full suite.
10. Remove generated `__pycache__` directories from the checkout and confirm the final file inventory.

Do not edit unrelated files, retained user evidence, or generated pack fixtures outside the test's temporary directory.

## Contract invariants

Preserve these rules unless a separately authorized versioned design replaces them:

- New v2 work uses `scripts/clone_pack.py`; `new_clone_pack.py` remains v1 compatibility only.
- Commands do not overwrite user-created destinations or finalized evidence.
- Paths remain pack/repository-contained POSIX relative paths where the schema requires them.
- Executables are invoked with argv arrays and no shell.
- External tools are never installed implicitly.
- The WSL installer refuses duplicate `clone-software` discovery in `.agents`, default/custom Codex-home, administrator, and destination-ancestor scopes; its checker accepts only lowercase 40-hex SHA-1 or 64-hex SHA-256 Git HEAD identities.
- The optional full-stack QA lane never installs Playwright, browsers, Node packages, application services, or operating-system dependencies; the target repository owns its pinned toolchain and CI gate.
- Application-owned frontend, mid-tier, backend, persistence, database, queue, cache, and worker components remain real in the required full-stack lane. Identical complete core-service declarations may share one `service_id`; conflicting declarations may not. Every queue, cache, or worker is an explicit `supporting_services` entry with readiness, assertion, artifact, journey binding, and result proof.
- Only external dependencies can be sandboxed, stubbed, or excluded with recorded authority, and every declared dependency is journey-bound. Every non-excluded dependency has exact protocol, endpoint, readiness, assertion, artifact, and result proof with its interface echoed; excluded dependencies have null proof fields and `NOT_APPLICABLE` results with a null interface.
- A full-stack verified profile requires a current linked `PASS` `RUN` for every declared journey, exact selected Playwright project, exact primary and ordered additional wire exchanges, and matching supporting/external results; screenshots, traces, capture status, and unlinked process exits are not substitutes.
- Full-stack plans and indexed GATE attributes use `blocked_exit_codes: [7]`. The repository wrapper performs capability/readiness preflight and exits `7` before behavioral work when blocked; ordinary behavioral mismatches remain `FAIL`/exit `5`.
- Automatic RUNs created by tool version `2.2.0` or `2.3.0` retain the complete effective GATE as `execution_contract`; the exact object is schema-validated before process execution, and validation rejects any later contract-field drift. Older v2 RUNs remain schema-compatible but do not attest fields they did not retain.
- Secret-like environment keys require `env:NAME`; resolved values are transient.
- `record-run` applies only explicitly governed textual redactions before promotion; gates still must not emit secrets outside that declared contract.
- Capture `PASS` remains acquisition status, not product outcome.
- Parity remains dimension-specific and oracle-independent.
- Plan case hashes exclude only mutable retained-result pointers: `result`, `baseline_result`, and `regression_result`.
- Traceability remains bidirectional.
- Gap status changes only through the legal lifecycle and append-only event chain.
- Seals are derived unsigned integrity manifests and never self-modified.
- Migration preserves exact v1 bytes and reports every semantic loss.
- `diff` remains an index-record comparison and returns data rather than a difference exit gate.

## Schema changes

All packaged JSON schemas declare Draft 2020-12 and reject additional properties at controlled object boundaries.

For a schema change:

1. Update the schema.
2. Update the corresponding template.
3. Update initialization or migration construction.
4. Update runtime parsing/validation.
5. Add one valid fixture and discriminating invalid fixtures.
6. Update human and agent documentation.
7. Decide whether the artifact's schema version changes. Do not overload `pack_revision` as a schema version.

The built-in schema evaluator supports only the vocabulary exercised by packaged schemas. Add evaluator behavior and meta-validation tests together if a schema introduces another keyword.

## Capture and path security changes

Any change touching capture input, staging, promotion, resume, redaction, secrets, lifecycle, web/comparator drivers, manual sources, or path resolution requires focused adversarial tests.

At minimum test:

- absolute, parent, empty-segment, dot-segment, backslash, drive-prefixed, and control-character paths;
- symlink components and final symlinks;
- non-regular and multiply linked files;
- undeclared outputs and runner metadata collisions;
- stale/malformed result pointers and ownership markers;
- missing/malformed secret indirection;
- credential resolution ordering and authorization;
- binary content under redaction rules;
- setup, adapter, teardown, interruption, and resume outcomes; and
- complete selected-set preflight before the first mutation.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.test_capture_adversarial_security \
  tests.test_capture_lifecycle_batch \
  tests.test_capture_parity_contract
```

## Gap and migration changes

For gap dossier or lifecycle changes, test valid and invalid status edges, dependencies, current run/parity/assurance evidence, path fences, symbol uniqueness, sequence continuity, atomic writes, hash-chain integrity, and derived `NO-OPEN-GAPS` behavior.

For migration changes, test read-only check, exact occurrence mappings, source hash changes between preflight and archive, output containment/non-overwrite, transformation ordering, source byte preservation, structured losses, status downgrades, and destination cleanup after failure.

## Full-stack QA changes

Changes to the optional full-stack contract MUST keep both full-stack plan/result schemas and templates, `scripts/clonepack/full_stack_qa.py`, emitted-artifact `source_path` retention, manifest parsing, profile enforcement, `references/full-stack-qa.md`, `docs/full-stack-qa.md`, and public documentation synchronized.

Add or preserve discriminating fixtures for:

- optional-plan backward compatibility for existing `clone-pack/v2` manifests;
- canonical contract hashing with only `contract_sha256` excluded;
- repository lockfile, Playwright configuration, CI workflow, and test-file hash drift;
- controlled `playwright.package` values (`@playwright/test`, `playwright`, `playwright-core`) and the boundary that runtime hashes but does not parse the lockfile or prove installation;
- exact Playwright project binding between plan and result;
- identical core-service reuse versus conflicting reused declarations;
- real, journey-bound supporting queue/cache/worker declarations with readiness, assertion, artifact, and result proof;
- authority-backed external dispositions, including exact protocol/endpoint/classification contracts, loopback rejection for a non-loopback `LOOPBACK` endpoint, authorized-origin checks for `AUTHORIZED_SANDBOX`, and `NOT_APPLICABLE` excluded results;
- installer-shim rejection and `install_argv: null`;
- plan-contract plus independent journey oracles, exact TEST/GATE oracle unions, reciprocal trace, and exact GATE coverage;
- exact GATE equality for argv, cwd, expected exit, `blocked_exit_codes: [7]`, artifact paths, and `fresh_artifact_paths`;
- exact tool-version `2.2.0` and `2.3.0` automatic RUN `execution_contract` retention and stale detection for every effective GATE field, plus earlier-run compatibility without overclaiming that evidence;
- a pre-existing unchanged required result rejected as `RUN_ARTIFACT_STALE`, while the current invocation's created or rewritten result is accepted;
- repository-wrapper preflight exit `7` mapping to retained `BLOCKED` evidence, while behavioral mismatches map to `FAIL`/exit `5`;
- primary and ordered `additional_exchanges` exact comparison, including duplicate-trigger rejection;
- `identity_bindings` with a `BIND-###` source and concrete `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` consumers, rejection of optional global consumers not referenced by the same journey, plus rejection when placeholders, pointers, required consumers, statuses, or `captured_value_sha256`/`observed_value_sha256` values differ;
- malformed percent escapes and percent-encoded secret-like external query names or values;
- canonical retained-result source mapping, schema/identity checks, and separate UI, request/response, service, persistence, supporting-service, and external-dependency outcomes; and
- latest-run precedence, verified-profile `HOLD` without a latest `PASS`, and rejection of a malformed or non-passing canonical result.

Run the focused offline contract and documentation tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.test_full_stack_qa_contract \
  tests.test_full_stack_qa_documentation
```

These tests use Python standard-library fixtures. Do not add Playwright, Node, browser, service-container, or network installation to this skill repository's CI. A target-repository fixture can describe and hash its own gate files; this repository does not execute that target gate. The validator checks readiness contracts but does not run their HTTP or command probes, and it hashes but does not parse CI YAML or inspect branch protection.

## WSL trial installer changes

Changes to `scripts/install_clone_software_wsl.sh` MUST keep the installer, `assets/prompts/minecraft-clean-room-mvp.md`, `README.md`, `docs/getting-started.md`, `docs/troubleshooting.md`, `changelog.md`, and `tests/test_wsl_minecraft_trial.py` synchronized.

Preserve these installer boundaries:

- the destination is absolute and absent, its immediate parent already exists, no existing destination component is a symlink, and there is no overwrite/update mode or ancestor-creation behavior;
- an existing `clone-software` skill in user, administrator, or applicable ancestor repository discovery scope blocks publication;
- non-default sources require `--trust-custom-source-code`, credential/userinfo/query/fragment URLs are rejected, and the trust flag is never described as a sandbox;
- required assets are regular non-symlink files, worktree symlinks and special files are rejected, and skill frontmatter, agent metadata, the WSL workspace checker, and both exact static-web catalog contracts are validated before cloned code executes;
- smoke and full verification are enclosed by a complete pre/post checkout identity that includes ignored entries and Git metadata, and any cloned-code mutation blocks publication;
- failed stages are retained with `INSTALL_STAGE_RETAINED`, no recursive cleanup command exists, and a replacement produces `STAGE_CLEANUP_REFUSED` without deleting either identity;
- the destination parent is descriptor-bound, checked by device/inode before and after publication, and local clones use `--no-hardlinks`;
- parent identity is sampled before open and matched to the descriptor and post-open path before discovery, while unchanged checkout semantics and identity are rechecked immediately before publication;
- descriptor-safe workspace creation and exclusive receipt creation are followed by exact staged-inventory, prompt, skill-link, and canonical-receipt validation; and
- `--codex-bin` provides path resolution only, while `/skills` from the published workspace remains the human discovery check.

The installer-authored command sequence MUST NOT install or update dependencies. Tests and documentation MUST separately state that cloned Python/help/full-suite code runs with the current user's authority and may have arbitrary effects. Add hostile fixtures for final and ancestor symlinks, duplicate discovery scopes, malformed metadata/catalog entries, ignored-file creation, HEAD/Git-metadata changes, help/full-runner mutation, source URL credential material, missing custom-source trust, staging-path replacement, and publication collision. A test fixture that merely returns a successful exit without proving the negative path is insufficient.

## Full verification

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_skill_tests.py
```

The command MUST exit `0`. Record the exact test count and elapsed result from the current execution.

Compile Python without writing bytecode into the repository:

```bash
PYTHONPYCACHEPREFIX=/tmp/clone-software-pycache \
  python3 -m compileall -q scripts tests
```

When the Codex `skill-creator` package is available, run its validator using the installed package's actual path:

```bash
python3 "<skill-creator-root>/scripts/quick_validate.py" \
  "/absolute/path/to/clone-software"
```

That validator checks skill packaging/frontmatter. It does not replace the repository tests.

Validate documentation structure and local links with:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.test_documentation
```

Do not rely only on visual rendering.

## Documentation rules

- Link to normative `references/` instead of redefining a second conflicting contract.
- State exact implemented behavior and exact limitations.
- Do not add roadmaps, promised features, unsupported platform matrices, release dates, licenses, repository URLs, or security claims without evidence.
- Distinguish tool version (`2.3.0` currently), artifact schema (`clone-pack/v2`), optional full-stack plan/result schemas (`clone-full-stack-qa-plan/v1` and `clone-full-stack-qa-result/v1`), and pack revision.
- Keep examples synthetic and label every replaceable value as an example.
- Keep shell commands directly executable after documented placeholders are replaced.
- Document stdout/stderr, mutation behavior, defaults, and exits for every CLI change.
- Keep current Codex installation/invocation facts grounded in OpenAI's current documentation.

## Changelog rule

Add an entry only for behavior or documentation that exists in the same change. A baseline-record entry may state when it was recorded but MUST NOT fabricate a Git tag, publication, prior release date, or historical feature chronology.
