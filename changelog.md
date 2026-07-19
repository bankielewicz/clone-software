# Changelog

This changelog begins with the repository state recorded on 2026-07-18. It does not assert that a Git tag, package publication, or public release exists. No earlier release history is inferred.

## Tool `2.1.0` implementation baseline — recorded 2026-07-19

This entry records repository functionality and contracts. It does not assert a Git tag, publication, deployment, merge, or compatibility outside the retained tests and evidence.

### Brownfield enhancement

- Added `enhancement-plan` and `enhancement-build` modes for authorized feature, behavior-change, refactor, dependency-upgrade, data-migration, security-hardening, and operations work in existing repositories.
- Added `enhancement-init`, `repo-snapshot`, `baseline-run`, `regression`, `verify-scope`, `enhancement-transition`, and `rehash` with canonical JSON results and the existing stable exit taxonomy.
- Added optional backward-compatible `clone-pack/v2` workstream and plan paths, repository inventory and enhancement plan schemas, and reciprocal `ENH`, `PRES`, `SNAP`, and `SCOPE` records.
- Added `repository-adopted`, `enhancement-ready`, and `verified-enhancement` profiles with adopted/candidate snapshot, preservation, path-scope, lifecycle, assurance, and seal bindings.
- Added default-clean and explicit adopted-dirty repository handling without implicit product-code mutation.

### Runtime hardening

- Made selected gap closure require terminal lifecycle and current closure evidence with complete hash-chained history.
- Added recoverable multi-file transaction journals that stop on unexpected divergence.
- Added declared `record-run` artifact retention, governed redaction, and deterministic blocked evidence for missing executable, start failure, and timeout.
- Made `assure` execute required cases by default, added explicit `--all`, selected-set preflight, canonical JSON, and deterministic aggregate exit precedence `7`, `5`, then `0`.
- Added retained-predecessor seal schema/internal-binding checks, pinned seal-digest verification, and exact `supersedes` lineage checks before successor sealing.

### Repository governance and documentation

- Added root `AGENTS.md` with Red-Green-Refactor, feature-branch, push, pull-request, and no-merge requirements scoped to Codex CLI capabilities.
- Added read-only, concurrency-cancelled CI across Python 3.10 through 3.14 with full-SHA action pins and no dependency installation.
- Added a pull-request-only dependency review workflow and GitHub-Actions-only weekly Dependabot updates.
- Added [Brownfield enhancement workflow](docs/brownfield-enhancement.md) and the Codex-loaded [brownfield contract](references/brownfield-enhancement.md).

### Verification

- The complete offline suite passed 184 tests on Python 3.12.3 on 2026-07-19.
- The four cold forward trials reached their declared results: sealed web/API feature, sealed dependency upgrade with an authority-approved known baseline failure, valid deferred expand-contract migration plan, and sealed non-Git CLI enhancement.
- All 17 packaged JSON schemas passed Draft 2020-12 meta-validation.
- Skill Creator validation and Python compilation of `scripts` and `tests` passed.
- These are local repository results. This entry does not claim hosted CI, deployment, merge, publication, or production execution.

## Repository documentation baseline — 2026-07-18

### Added

- Added `README.md` as the GitHub-facing human entry point.
- Added exact Codex user/repository discovery locations and `$clone-software` invocation instructions based on the current Codex manual.
- Added a complete authorization and task-input contract.
- Added mode selection and terminal-result contracts for `mvp-build`, `spec-only`, `gap-plan`, `gap-implement`, and `pack-migrate`.
- Added direct v2 initialization, validation, readiness, verification, and limitation guidance.
- Added a prominent repository-rights boundary recording that no `LICENSE` or public-use grant exists.
- Added `docs/getting-started.md` for first installation and invocation.
- Added `docs/operating-workflows.md` for mode-specific execution and stop conditions.
- Added `docs/cli-reference.md` for all twelve commands, arguments, defaults, mutations, output channels, and exits.
- Added `docs/clone-pack-authoring.md` for pack authority, graph, hash, profile, evidence, gap, and seal contracts.
- Added `docs/runtime-enforcement-boundaries.md` to distinguish machine profile checks from stricter semantic skill requirements.
- Added `SKILL.md` routing that requires separate machine-validation and semantic-audit results for tool `2.0.0`.
- Added `docs/troubleshooting.md` for deterministic diagnostic recovery.
- Added `docs/contributing.md` for repository invariants and verification gates.

### Clarified

- `scripts/new_clone_pack.py` is a v1 compatibility generator; new work uses `scripts/clone_pack.py init`.
- `scripts/validate_clone_pack.py` is a compatibility dispatcher rather than the full v2 profile interface.
- Capture `PASS` reports evidence acquisition and does not interpret the observed product outcome.
- `record-manual` records a completed observation and does not execute its procedure.
- `record-run` retains raw stdout/stderr and does not apply plan redaction metadata to those bytes.
- `assure` reports through process exit and retained files, not a stdout result object.
- `diff` compares exact index record objects only and returns `0` when differences exist.
- The built-in seal is an unsigned integrity manifest.

### Verification

- The post-documentation suite passed 114 tests in 190.726 seconds on 2026-07-18.
- The total includes 15 adversarial capture-security tests and 7 GitHub-documentation contract tests.

## Tool `2.0.0` implementation baseline — recorded 2026-07-18

This entry records functionality present when the changelog was introduced. It does not assert the implementation date of each feature.

### Implemented

- Unified standard-library CLI commands: `init`, `validate`, `migrate`, `capture`, `parity`, `scaffold`, `record-run`, `record-manual`, `gap-transition`, `assure`, `seal`, and `diff`.
- `clone-pack/v2` manifest, index, plans, run, gap-event, migration, dossier, and seal schemas.
- Readiness profiles: `scaffold`, `baseline-ready`, `spec-ready`, `build-ready`, `verified-mvp`, `gap-plan`, `gap-closure`, and `closed`.
- Playbooks for thirteen product categories plus hybrid selection.
- Evidence-backed bidirectional traceability and current-result freshness validation.
- HTTP, process/CLI/custom, filesystem, manual, and caller-supplied web capture adapters.
- Setup/teardown lifecycle capture, full-set batch preflight, lexical execution, atomic promotion, and strict resume ownership/integrity validation.
- Exact, text, JSON, HTTP, filesystem, DOM, accessibility, performance, perceptual-image, and custom parity comparators.
- Four audited dependency-free scaffolds with collision refusal and rollback: static web ESM, Python src layout, TypeScript src layout, and Rust crate.
- Machine-executable gap dossiers, dependency-safe planning, legal evidenced lifecycle transitions, and derived no-open-gaps state.
- Non-overwriting v1-to-v2 migration with exact source archive, occurrence mapping, status downgrades, structured losses, and mandatory reconciliation.
- Derived integrity seals with higher-revision prior-seal archiving.

### Security enforcement

- Safe contained POSIX path validation.
- Symlink, non-regular file, multiply linked file, undeclared output, and runner-name collision rejection.
- Environment-variable-only indirection for secret-like keys.
- Authorization decisions before credential-bearing reference reads.
- `safe_test_environment` requirement for mutating reference operations.
- Redirect-disabled HTTP reference capture.
- Redaction coverage over retained textual observation and lifecycle fields, with binary-under-redaction rejection.
- Immutable finalized evidence and exact result-pointer/hash validation.

### Verification evidence

- The implementation passed 107 offline tests before the repository documentation baseline was added.
- The focused adversarial capture-security suite passed 15 tests in that baseline.
- All packaged JSON schemas passed Draft 2020-12 meta-validation in that baseline.
- `agents/openai.yaml`, Python compilation, Markdown local links existing at that time, and Skill Creator validation passed in that baseline.
- A cold forward trial reached `baseline-ready`, reproduced captures through resume without mutation, and correctly held at unresolved `spec-ready` requirements.
