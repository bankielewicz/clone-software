# Changelog

This changelog begins with the repository state recorded on 2026-07-18. It does not assert that a Git tag, package publication, or public release exists. No earlier release history is inferred.

## Tool `2.3.0` implementation baseline — recorded 2026-07-20

This entry records behavior implemented in the repository. It does not assert a Git tag, publication, deployment, merge, hosted-CI result, product build, or GUI observation.

### Governed workspace boundaries

- Added exact pre-write classification of live workspace-root entries as `PRODUCT_INPUT`, `REPOSITORY_INSTRUCTION`, `TOOL_RUNTIME_EXCLUDED`, or `UNKNOWN_BLOCKER`. A tool-runtime exclusion requires an explicit user authority record, evidence that the path was absent before the session, an exact live identity, no allowed mutations, and repeated validation. It does not assert ownership. A dot-name, permission mode, inode, or mount state is not ownership evidence.
- Added optional `kind:"tool-runtime"` repository-inventory exclusions and matching repository-snapshot evidence. Existing scope-only exclusions may continue to omit `kind`; those records do not prune snapshot content and retain repository-authored nonempty reasons. A governed tool-runtime exclusion uses reason exactly `User-authorized empty tool-runtime directory excluded from product identity.`, must identify one empty, real, non-writable directory, and cannot overlap Git metadata, the clone pack, tracked content, repository instructions, scaffold or declared change paths, another exclusion, or an explicit include.
- Repository snapshots validate exclusions before and after Git or full-tree collection, keep product entries and `content_sha256` product-only, bind accepted exclusions separately, and require adopted and candidate snapshots to carry the same exclusion policy. Filesystem capture applies the same validation only when every exclusion authority is also declared by the selected case; the canonical exclusion set is retained in capture evidence.

### Isolated WSL trial

- Upgraded `scripts/install_clone_software_wsl.sh` receipts to canonical `clone-software-wsl-test-install/v2`. Each receipt binds the exact four-entry installed workspace inventory, including directory modes, prompt bytes, and the non-followed skill-symlink target, and the installer rechecks that inventory before atomic publication.
- Extended duplicate discovery to `$HOME/.codex/skills/clone-software` and a distinct configured `$CODEX_HOME/skills/clone-software`, in addition to the existing user, administrator, and repository-ancestor locations. A nonempty `CODEX_HOME` fails before clone when it is relative, control-bearing, lacks a searchable directory ancestor, or traverses a regular file or dangling symlink; the installer never moves or deletes the existing skill.
- Added read-only `scripts/check_wsl_trial_workspace.py`. Phase `pre-write` requires the exact v2 receipt/workspace binding and four-entry installed inventory. Phase `handoff` requires a canonical retained pre-write result, preserves every receipt-bound installer input, forbids added `.agents` content, reports product additions, and exact-matches any live runtime-exclusion identity with the baseline. It also exact-binds receipt `project_dir`, recomputes the complete receipt-bound checkout identity before and after workspace observation, and rejects a changed, symlinked-root, working-tree-symlinked, multiply linked, unsupported, unreadable, or concurrently mutated checkout. Both phases accept optional real `.git` metadata and only a requested literal `.codex` runtime path that is an empty real directory with no mode write bits. Accepted `.codex` evidence is `USER_PINNED`; it does not prove provider ownership. Missing, v1, noncanonical, live-binding-mismatched, populated, writable, symlinked, replaced, or unrelated initial workspace state returns a canonical blocking result. The unsigned receipt does not let the checker independently attest source-provenance fields that have no live workspace counterpart. The v1 `product_inventory` compatibility field includes `.agents` repository-scoped skill input and is not product-only identity.
- Made receipt `resolved_head` validation finite across Git object formats: exactly lowercase 40-hex SHA-1 and 64-hex SHA-256 values pass; unsupported lengths, uppercase, and non-hex values remain receipt schema exit `2`.
- Updated the voxel-sandbox request to execute `--phase pre-write` immediately before its first workspace write, retain exact canonical stdout at `docs/clone/evidence/raw/workspace-check/pre-write.json` as part of `E-002`, and execute `--phase handoff` against that baseline after the last authorized write. The request forbids `.codex` mutation or global ignore rules and preserves an active unsealed pack with stale RUN evidence byte-for-byte. Recovery uses exact absent path `docs/clone-recovery/` as a fresh independent revision-1 pack with a new `pack_id`, `supersedes: null`, and no copied RUN evidence while retaining the checker baseline in preserved `docs/clone/`. The terminal inventory contract subtracts the exact four receipt-bound inputs and compares the remaining typed records with fixed product paths plus manifest-derived governed pack paths. Root `changelog.md` is an authorized product document only for exact observed results; it cannot relabel a parity failure or claim an absent seal or delivery action.

### Browser-serving scaffold

- Added the dependency-free `static-web-esm-allowlist` scaffold for new browser-served work. Its Python standard-library server exposes only regular non-symlink files named in `serve_manifest.json`, supports GET and HEAD, emits canonical port-zero readiness, and rejects queries, fragments, malformed or encoded ambiguity, dot/traversal paths, directories, symlinks, special files, undeclared files, and unsupported methods without returning denied resource bytes.
- Retained legacy `static-web-esm` byte-for-byte for existing packs that already select it. Selecting the allowlist for new browser-served work is a skill policy; the v2 schema and scaffolder accept both static profiles because they do not encode when a plan was authored. The three non-browser profiles and the brownfield `not-applicable` sentinel retain their existing contracts.

### Claim boundary

- The runtime exclusion contract verifies only inventoried local paths, identities, authority records, and the operations executed by the selected snapshot or capture. It does not establish provider ownership, authorize unobserved paths, or permit the skill to delete, rename, chmod, ignore, deploy, or merge runtime state.
- Runtime-exclusion traversal requires POSIX descriptor-safe `open`/`stat`/`scandir` capabilities. An unsupported host returns `RUNTIME_EXCLUSION_CAPABILITY_MISSING` with exit `3` and performs no pruning or collection.
- The allowlisted server is a local development capability. It fails before listening with exit `2` and `MANIFEST_INVALID` when its stricter descriptor-safe open capabilities are unavailable. It does not provide TLS, authentication, production caching, compression, deployment, or production hardening.
- Current local verification and pull-request check results are recorded in the implementation handoff after execution; this entry does not infer them.

## Isolated WSL trial and clean-room voxel prompt — recorded 2026-07-20

- Added `scripts/install_clone_software_wsl.sh`, a collision-refusing WSL Bash installer that stages and validates a requested Git branch/tag, publishes one new root containing the skill checkout and isolated repository-scoped test workspace, and records the resolved HEAD plus prompt SHA-256 in `installation-receipt.json`.
- Added `--verify smoke|full`, default-`main` or explicit branch/tag selection, absolute regular-file Codex path resolution without execution, Python/Node/runtime preflight, exact UTF-8 scalar frontmatter/agent and catalog-schema checks, repeated checkout identity including ignored paths and Git metadata, non-hardlinked local clones, descriptor-safe workspace creation, and exact pre-publication handoff validation.
- Non-default sources require `--trust-custom-source-code`; URL/SCP user information is rejected, and URL or local-path source values containing query, fragment, or control characters are rejected. Verification executes cloned Python, and full verification executes cloned tests, with the current WSL user's authority. The installer does not sandbox that code, so only trusted sources are valid inputs.
- The installer-authored steps do not install or update Codex, Node packages, Python packages, browsers, Playwright, or operating-system packages. This boundary does not claim that arbitrary cloned source code is effect-free.
- Added collision refusal for absent immediate parents, destination/ancestor symlinks, and an already discoverable `clone-software` skill in user, administrator, or ancestor repository scope. The installer never creates destination ancestry or moves an existing skill; the operator must select an existing real parent and deliberately move a duplicate skill outside discovery or use a clean home/profile.
- Bound staging and atomic publication to an open destination-parent descriptor whose pre-open, descriptor, and post-open device/inode identities must match. Revalidated checkout semantics and complete identity immediately before publication. Failed stages with unchanged lexical identities are reported by durable path through `INSTALL_STAGE_RETAINED`; a replaced parent/stage produces `STAGE_CLEANUP_REFUSED` without an inferred path, and no recursive cleanup command runs.
- Added `assets/prompts/minecraft-clean-room-mvp.md`, a cold-session `$clone-software` request for an original dependency-free WebGL 2 voxel-sandbox MVP with exact deterministic world, physics, controls, storage, security, TDD, evidence, exclusion, HALT, and handoff contracts.
- The prompt treats its own bytes as the `USER_PINNED` baseline, requires replacement branding and original content, prohibits Minecraft/Mojang code and assets, forbids a Minecraft-parity claim, and returns workflow `HOLD` instead of inventing GUI proof when no authorized installed browser observer exists.
- Updated README, getting-started, troubleshooting, and contributing documentation with the exact WSL command, published layout, trust boundary, required assets, arguments, exits/diagnostics, collision recovery, path-only Codex receipt field, `/skills` human discovery check, and machine-versus-GUI proof boundary.
- This entry does not claim a tag, release, hosted-CI result, game build result, GUI observation, publication, deployment, or merge.

## Tool `2.2.0` implementation baseline — recorded 2026-07-19

This entry records repository functionality and contracts. It does not assert a Git tag, publication, deployment, merge, hosted-CI result, or compatibility outside the implemented schemas, validators, and retained evidence.

### Full-stack QA

- Added optional `plans.full_stack_qa` support to `clone-pack/v2`, strict `clone-full-stack-qa-plan/v1` and `clone-full-stack-qa-result/v1` schemas, and reusable plan/result templates. Existing v2 manifests that omit the optional path remain valid.
- Added readiness validation for plan identity, canonical contract digest, repository file hashes, plan-contract plus independent journey oracles, reciprocal `WF`/`REQ`/`AC`/`TEST`/`GATE` trace links, exact gate coverage/command/artifacts/fresh artifacts, declared-real application-owned services, pinned Playwright project/CI configuration, synthetic fixtures, and authorized external dispositions.
- Allowed one identically declared application service to fill multiple frontend, mid-tier, backend, or persistence roles while rejecting conflicting declarations for a reused `service_id`. Added explicit `REAL` queue/cache/worker declarations with readiness, assertion, artifact, journey binding, and canonical supporting-service results.
- Required every external dependency to be journey-bound. Non-excluded dependencies declare an exact `protocol`, `endpoint`, and `classification` of `LOOPBACK` or `AUTHORIZED_SANDBOX`, plus readiness, assertion, artifact, and matching result evidence with the complete interface echoed. Excluded dependencies retain authority while using null proof fields and a `NOT_APPLICABLE` result with a null interface.
- Added exact primary-wire plus ordered `additional_exchanges` result comparison and duplicate-trigger rejection. The selected Playwright project is also bound from plan to canonical result.
- Added required journey `identity_bindings`: each `BIND-###` names a source exchange/response JSON pointer/value type, uses exact placeholders at mandatory `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` consumer pointers, and binds the concrete decoded wire segment plus every emitted consumer to one canonical UTF-8 `captured_value_sha256`. Verified results require the binding and every consumer to be `PASS`. The validator checks the emitted service/persistence hashes; it does not inspect their implementation internals.
- Fixed the full-stack blocked contract at `ci.blocked_exit_codes: [7]` and required an identical indexed GATE attribute. A repository wrapper preflights capabilities/readiness and exits `7` before behavioral work; `record-run` retains that as `BLOCKED`/exit `7` and skips declared artifacts, while ordinary behavioral mismatches remain `FAIL`/exit `5`.
- Added exact plan-to-GATE equality for `fresh_artifact_paths`, required `ci.result_path` in that set, and made non-blocked `record-run` invocations reject a required artifact whose pre/post identity, metadata, and SHA-256 are all unchanged with `RUN_ARTIFACT_STALE` and exit `4`.
- Added `execution_contract` to tool-2.2 automatic RUN evidence and freshness validation. It retains the effective argv, cwd, declared environment, timeout, exits, artifact/fresh-artifact paths, coverage, oracles, normalizations, and redactions; the complete object is schema-validated before process execution, and any later GATE-field change produces `RUN_CONTRACT_STALE`. Earlier v2 RUNs may omit the object for backward compatibility and do not attest those added fields.
- Kept optional QA verification out of `gap-plan`; current passing QA output is required at `verified-mvp`, `gap-closure`, and `closed`, while `gap-plan` performs readiness checks only.
- Hardened external endpoints by rejecting malformed percent escapes and checking the percent-decoded query for secret-like content. Optional identity consumers for supporting services and external dependencies now must target an ID referenced by that same journey.
- Added verification `HOLD` behavior when the latest linked gate/environment `RUN` is absent or not `PASS`. The workflow reuses the existing indexed `GATE` and `record-run` execution path; no new Playwright executor or installer was added to the clone-pack runtime.
- Made `record-run` retain each emitted artifact's repository `source_path`. Verified full-stack profiles parse the exact retained `ci.result_path`, bind it to the current plan digest/GATE/environment/journey set, and require separate passing UI, actual request/response, application-owned service, and persistence outcomes.
- Required application-owned services to be declared `REAL`; authorized external stubs remain explicit exclusions from provider proof. The validator checks readiness declarations but does not execute probes, inspect service internals, parse CI workflow semantics, query branch protection, or prove a hosted run, so those limitations remain explicit.

### Skill and documentation

- Added the Codex-loaded [full-stack QA contract](references/full-stack-qa.md) and the human [Full-stack QA with Playwright](docs/full-stack-qa.md) guide with exact authoring, CI, evidence, failure, and recovery contracts.
- Limited `playwright.package` to `@playwright/test`, `playwright`, or `playwright-core`. The runtime hashes the declared lockfile bytes but does not parse the lockfile or prove package/version installation; capability preflight remains repository-wrapper-owned and reports an unavailable lane with exit `7`.
- Kept Playwright, browser binaries, application services, dependency restore, and CI execution target-owned. The Python standard-library clone-pack runtime validates and records declared evidence but never installs those capabilities.

### Claim boundary

- A passing full-stack gate proves only the declared browser action, primary request/response, ordered additional exchanges, named API or data postcondition, declared supporting-service and external-boundary assertions, exact Playwright project, and retained environment. It does not prove unobserved mid-tier control flow, database constraints, undeclared background jobs, provider behavior behind a sandbox or stub, or production deployment.
- No 2.2.0 test count, hosted-CI result, release, publication, deployment, or merge is claimed in this entry.

## CC0 1.0 Universal public-domain dedication — 2026-07-19

- Added the canonical Creative Commons CC0 1.0 Universal legal text as `LICENSE`.
- Replaced the current no-license distribution boundary with the CC0 public-domain dedication and fallback terms.
- Kept third-party reference authorization and provenance separate: CC0 applies to this repository's contents and does not authorize access to or reimplementation of another product.
- This entry records repository terms only. It does not assert a Git tag, GitHub release, package publication, or deployment.

## Tool `2.1.0` implementation baseline — recorded 2026-07-19

This entry records repository functionality and contracts. It does not assert a Git tag, publication, deployment, merge, or compatibility outside the retained tests and evidence.

### Brownfield enhancement

- Added `enhancement-plan` and `enhancement-build` modes for authorized feature, behavior-change, refactor, dependency-upgrade, data-migration, security-hardening, and operations work in existing repositories.
- Added `enhancement-init`, `repo-snapshot`, `baseline-run`, `regression`, `verify-scope`, `enhancement-transition`, and `rehash` with canonical JSON results and the existing stable exit taxonomy.
- Added optional backward-compatible `clone-pack/v2` workstream and plan paths, repository inventory and enhancement plan schemas, and reciprocal `ENH`, `PRES`, `SNAP`, and `SCOPE` records.
- Added `repository-adopted`, `enhancement-ready`, `implementation`, and `verified-enhancement` profiles with adopted/candidate snapshot, preservation, path-scope, lifecycle, assurance, and seal bindings.
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

- The complete offline suite passed 194 tests on Python 3.12.3 on 2026-07-19.
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
- Added a prominent repository-rights boundary recording that no `LICENSE` or public-use grant existed in that baseline; the CC0 dedication above supersedes that boundary.
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
