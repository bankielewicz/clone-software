# Contributing

This repository contains a security-sensitive specification and evidence tool. A change is complete only when runtime behavior, schemas, templates, references, human documentation, and tests agree.

No `LICENSE` file exists in the current repository. This documentation does not grant redistribution or contribution rights. Obtain the repository owner's terms before publishing, redistributing, or accepting third-party contributions.

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
| `scripts/clonepack/lifecycle.py` | Gap transition prerequisites and append-only event history |
| `scripts/clonepack/dossier.py` | Machine gap-dossier validation against repository truth |
| `scripts/clonepack/evolution.py` | v1 migration, successor rules, and index-record diff |
| `scripts/clonepack/scaffold.py` | Audited scaffold catalog validation, preview, apply, and rollback |
| `scripts/clonepack/schema.py` | Packaged Draft 2020-12 schema evaluator |
| `assets/templates-v2/` | Source artifacts copied by v2 initialization |
| `assets/schemas/` | Exact machine schemas |
| `assets/scaffolds/` | Audited dependency-free skeletons and catalog |
| `references/` | Normative operational and product contracts loaded by Codex |
| `docs/` | Human-facing repository usage documentation |
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
- Distinguish tool version (`2.1.0` currently), artifact schema (`clone-pack/v2`), and pack revision.
- Keep examples synthetic and label every replaceable value as an example.
- Keep shell commands directly executable after documented placeholders are replaced.
- Document stdout/stderr, mutation behavior, defaults, and exits for every CLI change.
- Keep current Codex installation/invocation facts grounded in OpenAI's current documentation.

## Changelog rule

Add an entry only for behavior or documentation that exists in the same change. A baseline-record entry may state when it was recorded but MUST NOT fabricate a Git tag, publication, prior release date, or historical feature chronology.
