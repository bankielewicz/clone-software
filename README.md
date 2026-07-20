# Clone Software

`clone-software` is a Codex skill and Python standard-library toolchain for authorized, evidence-grounded clean-room reimplementation and bounded enhancement of existing repositories. It converts an observed reference product into a versioned clone pack, or an adopted repository into a before-and-after enhancement contract with retained preservation and scope evidence. An optional full-stack QA plan binds a repository-owned Playwright journey to UI, wire, service, persistence, CI, and retained-run proof.

The repository does not contain a universal source-code copier. It does not bypass access controls, recover proprietary source, infer unobserved behavior, install capture tools, or certify parity that has not been measured.

## Implemented capabilities

- Operate in `mvp-build`, `spec-only`, `gap-plan`, `gap-implement`, `pack-migrate`, `enhancement-plan`, or `enhancement-build` mode.
- Model websites, browser applications, SaaS products, APIs, servers, clients, libraries, SDKs, CLIs, browser extensions, AI/ML systems, data pipelines, storage systems, distributed or realtime systems, games, simulations, embedded systems, IoT software, and hybrids of those types.
- Initialize and validate non-overwriting `clone-pack/v2` artifacts.
- Capture reference and clone behavior through HTTP, process/CLI, filesystem, manual artifact, custom process, or caller-supplied web-driver adapters.
- Compare retained evidence with exact, text, JSON, HTTP, filesystem, DOM, accessibility, performance, perceptual-image, or custom comparators.
- Preview or apply one of four audited dependency-free scaffolds: `static-web-esm`, `python-src`, `typescript-src`, or `rust-crate`.
- Execute pinned gates, record manual verification, run assurance cases, transition gaps through a controlled lifecycle, create integrity seals, migrate v1 packs, and compare pack index records.
- Adopt Git or filesystem repositories, retain immutable adopted and candidate snapshots, run preservation baselines and regression, enforce changed-path scope, and maintain a hash-chained enhancement lifecycle.
- Validate an optional `full_stack_qa_plan.json` against the packaged `clone-full-stack-qa-plan/v1` schema, require application-owned core and supporting services to be declared `REAL`, bind a Playwright project, primary/additional wire exchanges, and cross-layer `identity_bindings`, retain explicit external-boundary outcomes, require a current-invocation canonical result, and parse `clone-full-stack-qa-result/v1` through the existing indexed `GATE` and `RUN` model.
- Reject unresolved governed markers, unsafe paths, stale retained evidence, broken reciprocal links, illegal transition requests, unpinned credentials, and missing proof required by the selected profile; [Runtime enforcement boundaries](docs/runtime-enforcement-boundaries.md) identifies dimensions outside tool `2.2.0` profiles.

The tool version implemented in `scripts/clonepack/__init__.py` is `2.2.0`. It remains compatible with legacy `clone-pack/v2` manifests that omit the optional brownfield workstream fields and the optional `full_stack_qa` plan path.

## Non-negotiable boundary

Use this skill only when the requester has authority to observe and reimplement the named behavior.

The operator MUST record:

- the requester and authorization basis;
- the exact permitted sources, artifacts, accounts, and environments;
- prohibited actions and target-side mutation limits;
- the reference release, build, commit, artifact digest, or dated snapshot;
- branding, content, model, dataset, and redistribution rights;
- the data and secret-handling policy;
- the intended distribution target; and
- the reference and clone environments used for evidence.

The skill MUST NOT bypass authentication, licensing, DRM, signing, rate limits, anti-bot controls, paywalls, or other access controls. It MUST NOT collect target credentials, copy unauthorized source or assets, probe production destructively, or present inference as verified behavior.

Read [Evidence and fidelity](references/evidence-and-fidelity.md) before authorizing capture and [Security and provenance](references/security-and-provenance.md) before implementation or external delivery.

## Requirements

- Python 3.10 or later syntax. The CLI imports only Python standard-library modules.
- A local checkout of this repository.
- Codex for skill-driven operation. The deterministic CLI also runs directly without Codex.
- Any product-specific runtime, browser driver, comparator, scanner, compiler, or package manager already installed before the corresponding plan executes. The clone-pack runtime does not install external tools or dependencies. A target-owned CI workflow may execute only its explicitly authorized restore argv from its pinned lockfile.
- An existing clone repository root. `init` requires that root to exist and requires the selected pack output directory to be absent.
- Bash with `test`, `mkdir`, and `cp` for the Bash installation examples, or PowerShell 7 with `Test-Path`, `New-Item`, and `Copy-Item` for the PowerShell alternatives. The Python CLI itself does not require Bash.

The full regression suite is currently executed under Python 3.12.3. This records the verified environment; it does not assert that every Python 3.10 or 3.11 patch release has been tested.

## Usage rights

The repository contents are dedicated to the public domain under **CC0 1.0 Universal** (`SPDX-License-Identifier: CC0-1.0`). The canonical dedication and fallback terms are in [LICENSE](LICENSE). CC0 does not waive patent or trademark rights and does not clear rights held by other people.

The CC0 dedication applies to this repository's contents. It does not authorize access to, observation of, or reimplementation of any third-party reference product. The authority and provenance requirements in [Non-negotiable boundary](#non-negotiable-boundary) remain mandatory for every clone or enhancement task.

## Install the skill for Codex

Current Codex skill discovery uses these locations:

| Scope | Location | Use |
| --- | --- | --- |
| User | `$HOME/.agents/skills/clone-software` | Make the skill available across repositories for one user |
| Repository | `<repository>/.agents/skills/clone-software` | Make the skill available while Codex works in that repository or its descendants |

Codex scans repository `.agents/skills` directories from the current working directory through the repository root. Symlinked skill directories are supported. See OpenAI's current [Build skills](https://learn.chatgpt.com/docs/build-skills.md) documentation for discovery behavior.

For a fresh user-level copy in Bash, set the selected destination and confirm it is absent:

```bash
INSTALLED_SKILL="$HOME/.agents/skills/clone-software"
test ! -e "$INSTALLED_SKILL"
```

Only after `test` exits `0`, run:

```bash
INSTALLED_SKILL="$HOME/.agents/skills/clone-software"
mkdir -p "$HOME/.agents/skills"
cp -R "/absolute/path/to/clone-software" "$INSTALLED_SKILL"
python3 "$INSTALLED_SKILL/scripts/clone_pack.py" --help
```

If `test` exits nonzero, do not run the second block. Inspect the existing installation and update it deliberately; do not copy a second tree into it.

For repository scope in Bash, first run only the absence check:

```bash
INSTALLED_SKILL="/absolute/path/to/repository/.agents/skills/clone-software"
test ! -e "$INSTALLED_SKILL"
```

Only after `test` exits `0`, run:

```bash
INSTALLED_SKILL="/absolute/path/to/repository/.agents/skills/clone-software"
mkdir -p "/absolute/path/to/repository/.agents/skills"
cp -R "/absolute/path/to/clone-software" "$INSTALLED_SKILL"
python3 "$INSTALLED_SKILL/scripts/clone_pack.py" --help
```

For PowerShell 7 user scope:

```powershell
$InstalledSkill = Join-Path $HOME ".agents/skills/clone-software"
if (Test-Path -LiteralPath $InstalledSkill) { throw "Destination already exists: $InstalledSkill" }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InstalledSkill) | Out-Null
Copy-Item -LiteralPath "C:\absolute\path\to\clone-software" -Destination $InstalledSkill -Recurse
python "$InstalledSkill/scripts/clone_pack.py" --help
```

For PowerShell repository scope, set `$InstalledSkill` to `C:\absolute\path\to\repository\.agents\skills\clone-software`. In every scope, the verification command MUST use the destination actually selected; do not verify `$HOME/.agents/skills` after a repository-only installation.

The help output MUST list `init`, `validate`, `migrate`, `capture`, `parity`, `scaffold`, `record-run`, `record-manual`, `gap-transition`, `assure`, `seal`, `diff`, `enhancement-init`, `repo-snapshot`, `baseline-run`, `regression`, `verify-scope`, `enhancement-transition`, and `rehash`.

Codex detects skill changes automatically. If `$clone-software` does not appear after installation or update, restart Codex once and check again.

## Invoke the skill through Codex

In Codex CLI or the IDE extension, type `$` or use `/skills`, then select `clone-software`. Explicit invocation is:

```text
Use $clone-software in spec-only mode.

Requester and authority: Acme Engineering owns the named internal application and authorizes behavioral reimplementation for internal evaluation.
Reference baseline: release 4.2.1, local artifact /absolute/path/reference-4.2.1.zip, SHA-256 supplied in evidence/reference.sha256.
Permitted observation: the local artifact, its bundled documentation, and ordinary interactions with the isolated test deployment at http://127.0.0.1:8080.
Prohibited actions: no production access, no third-party traffic, no credential extraction, no load testing, and no reuse of reference branding or media.
Reference evidence environment: ENV-001 on Ubuntu 24.04 x86_64, Chromium 1280x720, en-US, UTC, synthetic fixture set inventory-v1, reset before each case.
Clone evidence environment: the same ENV-001 host/settings/fixture contract, using the isolated clone endpoint.
Accounts and roles: reference account ref-member@example.invalid and clone account clone-member@example.invalid, both in the member role and isolated test tenant.
Data policy: synthetic fixtures only.
Secrets policy: values are supplied only through REFERENCE_TEST_AUTH and CLONE_TEST_AUTH environment variables and are never written into the request, plans, logs, screenshots, or fixtures.
Product type: hybrid. Playbooks: web-app-saas and api-service-server.
Clone repository root: /absolute/path/acme-clone.
Clone-pack output: docs/clone.
Distribution target: internal evaluation.
MVP boundary: actor signs in to the isolated clone, creates one record, observes validation failure for an invalid record, reloads, and retrieves the persisted valid record.
Stop condition: produce a spec-ready pack or return the exact blocked IDs and one resolution question for each behavior-changing unknown. Do not edit product code.
```

Every value above is an example. Replace it with the authorized task's actual facts. Do not retain a sample value when it is not true.

The operating mode is a Codex workflow boundary; it is not a `clone_pack.py init` option and is not stored as a manifest field.

| Requested intent | Mode | Product-code permission | Terminal result |
| --- | --- | --- | --- |
| Build or recreate an MVP | `mvp-build` | Allowed only after `build-ready` passes | Sealed verified MVP, or workflow `HOLD` with exact gaps/blockers |
| Capture, analyze, specify, or plan only | `spec-only` | Forbidden | `spec-ready`, or exact blockers |
| Turn existing gaps into executable plans | `gap-plan` | Forbidden | Dependency-safe, validator-passing gap dossiers |
| Implement selected existing gaps | `gap-implement` | Limited to the selected dossier fences | Evidenced legal transitions through verification, or `HALT` |
| Convert a v1 pack | `pack-migrate` | Forbidden unless separately requested after reconciliation | Non-overwriting v2 successor plus migration report |
| Plan a bounded change to an existing repository | `enhancement-plan` | Forbidden | `enhancement-ready`, or exact blockers |
| Implement a bounded existing-repository change | `enhancement-build` | Allowed only after `enhancement-ready` | Sealed `verified-enhancement`, or exact blockers |

A validator `HOLD` is the machine result `status: HOLD` with exit `5`. A workflow `HOLD` is the agent's terminal handoff when the requested outcome was not achieved; it can contain validator `FAIL`, validator `HOLD`, infrastructure exit `7`, or unresolved authority decisions. The handoff MUST retain the exact command, exit, status, and diagnostics rather than relabeling them.

See [Operating workflows](docs/operating-workflows.md) for the exact phase sequences and [Brownfield enhancement workflow](docs/brownfield-enhancement.md) for repository adoption, `implementation`, and before-and-after verification.

## Initialize a pack directly

Use the unified CLI for all v2 work:

```bash
SKILL_ROOT="/absolute/path/to/clone-software"
REPO_ROOT="/absolute/path/to/authorized-clone-repository"

python3 "$SKILL_ROOT/scripts/clone_pack.py" init \
  --product-name "Authorized Inventory CLI" \
  --product-type cli \
  --playbook cli \
  --source-description "Authorized local release 1.0 artifact; digest evidence is not yet bound" \
  --repo-root "$REPO_ROOT" \
  --output-dir docs/clone
```

Preconditions:

- `SKILL_ROOT` resolves to this checkout.
- `REPO_ROOT` is an existing directory.
- `REPO_ROOT/docs/clone` does not exist.
- `--output-dir` remains below `REPO_ROOT` and is not the repository root.
- A non-hybrid product includes its own product type as a playbook.
- A `hybrid` product supplies at least two distinct `--playbook` values.
- `--source-description` is descriptive input only; `init` does not verify the asserted version or digest.

The command creates ten Markdown contracts, four JSON plans, `clone_index.json`, `clone_pack.json`, and an empty append-only gap-event history. It does not create product code, inspect the reference, execute a scaffold, or establish source accuracy.

Validate only the structural result first:

```bash
python3 "$SKILL_ROOT/scripts/clone_pack.py" validate \
  "$REPO_ROOT/docs/clone" \
  --profile scaffold
```

`STRUCTURAL PASS` means the generated pack has the required v2 files and identities. The accompanying `NON-CERTIFICATION` statement is binding: it does not establish baseline, specification, implementation, parity, assurance, security, or release readiness.

The default generated pack intentionally fails `baseline-ready` until its authorization, baseline, environment, two default capture cases, index counterparts, hashes, and required Markdown fields are resolved. Deleting required cases does not satisfy the semantic baseline contract. Follow [Clone-pack authoring](docs/clone-pack-authoring.md) and [Runtime enforcement boundaries](docs/runtime-enforcement-boundaries.md) instead of deleting validation failures or inventing values.

## Readiness and proof

Foundation readiness proceeds in this order:

```text
scaffold -> baseline-ready -> spec-ready -> build-ready
```

After `build-ready`, select the profile matching the operation:

```text
verified-mvp   evidence-backed MVP proof and seal
gap-plan       cold-executable plans for actionable nonterminal gaps
gap-closure    machine profile and seal; selected terminal/closure evidence requires a separate semantic audit
closed         terminal status fields and seal; transition history/authority requires a separate semantic audit
```

Use `gap-closure` only after selected gaps have current lifecycle and closure evidence.

Brownfield enhancement readiness follows a separate branch:

```text
`repository-adopted` -> `enhancement-ready` -> `implementation` -> `verified-enhancement`
```

`implementation` validates the retained planning and baseline evidence required by `enhancement-ready` plus lifecycle state `IN_PROGRESS`, `IMPLEMENTED`, or `VERIFIED`. Unlike `enhancement-ready`, it does not require the live repository to equal the adopted snapshot because authorized edits may exist. A pass proves retained contract and lifecycle state only; edit authorization comes from a successful `READY -> IN_PROGRESS` transition and the resulting `enhancement-build` mode. It does not validate candidate, preservation-regression, scope, assurance, or seal evidence.

Always execute the validator. A checklist, document review, passing unit test, product screenshot, commit, or prose claim does not substitute for a passing profile.

Conversely, a profile pass proves only the named tool `2.2.0` contract. Apply [Runtime enforcement boundaries](docs/runtime-enforcement-boundaries.md) before a broader claim.

```bash
python3 "$SKILL_ROOT/scripts/clone_pack.py" validate \
  "$REPO_ROOT/docs/clone" \
  --profile spec-ready \
  --format json \
  --max-problems 0
```

For automation, read the JSON `status` and process exit code. Do not parse the human text label.

Do not modify product code before `build-ready` passes. Do not call the MVP verified until `verified-mvp` passes with a current seal. Do not call all gaps closed until `closed` passes.

## Full-stack QA with Playwright

Add the optional `full_stack_qa` plan only for a journey that crosses all four required layers: browser-visible UI, the real application request and response, an application-owned service postcondition, and persisted state observed after reload, relogin, or restart. Copy `assets/templates-v2/full_stack_qa_plan.json`, replace every marker with inspected repository facts, and add `"full_stack_qa": "full_stack_qa_plan.json"` to the manifest's `plans` object. Packs that omit this optional path retain their existing v2 behavior.

The target repository owns the Playwright configuration, browser, application services, CI workflow, dependency restore decision, and indexed gate command. The clone-pack runtime validates the plan and its hashes, files, trace links, declared real-service classifications, gate contract, and required proof artifacts. It executes the already-declared repository gate through the existing `record-run` command; it never installs Playwright, browsers, application dependencies, or services. `playwright.package` is exactly one of `@playwright/test`, `playwright`, or `playwright-core`. The plan pins its declared version, the lockfile bytes by SHA-256, and the exact Playwright `project`; the canonical result repeats the project as `playwright_project`. The runtime does not parse the lockfile or prove that the declared package, version, browser, or project is installed. The repository wrapper performs that capability preflight and exits `7` when it cannot execute the declared lane.

The required journey records separate results for:

```text
browser action and visible UI result
  -> primary actual request and response
  -> every named additional_exchanges request and response
  -> API or data postcondition
  -> persistence after reload, relogin, or restart
  -> applicable supporting_services and external-boundary results
```

An application-owned frontend, mid-tier, backend, persistence service, queue, cache, or worker cannot be declared stubbed in the required full-stack lane. Core architecture roles may share the same `service_id` only when their complete declarations are identical. Applicable queues, caches, and workers are listed in `owned_stack.supporting_services`, bound to journeys, and require matching passing results. An authorized non-excluded external sandbox or stub records an exact interface containing `protocol`, `endpoint`, and `classification`, where classification is `LOOPBACK` or `AUTHORIZED_SANDBOX`, plus readiness, assertion, artifact, journey link, and passing result. A `LOOPBACK` endpoint must resolve to localhost or a loopback IP; an HTTP(S) interface must also match a declared allowed origin. Endpoint validation rejects malformed percent escapes and percent-decodes the query before checking for secret-like names or values. The canonical result echoes the complete interface exactly. `EXCLUDED` records null proof fields and `NOT_APPLICABLE`; no disposition proves the external provider. The validator rejects a non-`REAL` declaration but does not inspect service internals for a hidden mock.

Every journey has at least one `identity_bindings` entry. A `BIND-###` names the source exchange, response JSON pointer, and `string` or `integer` value type, then points to the exact plan strings that consume `{binding_name}`. `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` consumers are mandatory. An optional `SUPPORTING_SERVICE` or `EXTERNAL_DEPENDENCY` consumer must target an ID referenced by the same journey. The wire placeholder occupies one complete path segment in an exchange after the source; the result supplies the concrete observed segment. The gate hashes the canonical UTF-8 captured value into `captured_value_sha256`, repeats that digest as each consumer's `observed_value_sha256`, and marks the binding and every consumer `PASS`. The validator exact-matches the source and ordered consumer pointers, requires all hashes to agree, and percent-decodes and hashes the concrete wire segment. For service and persistence consumers it validates the emitted hashes and statuses; it does not inspect application internals or derive those values from the prose observation.

Each journey lists the plan-contract ART plus at least one independent `E`, `ART`, or `CAP` oracle. Their union must exactly equal the GATE oracle links/attributes; the journey REQ/AC/TEST union must exactly equal GATE coverage. Plan `ci.gate_argv`, `gate_cwd`, `expected_exit`, `blocked_exit_codes`, `artifact_paths`, and `fresh_artifact_paths` exactly equal the corresponding indexed GATE attributes. `ci.result_path` occurs in both artifact lists. For every non-blocked invocation, `record-run` compares each fresh artifact's pre-run and post-run device, inode, size, modification time, change time, and SHA-256; a path that is not created or rewritten by that invocation stops with `RUN_ARTIFACT_STALE` and exit `4`.

Every automatic RUN created by tool `2.2.0` retains an `execution_contract` containing the exact effective argv, cwd, declared environment, timeout, expected and blocked exits, artifact and fresh-artifact paths, coverage, oracles, normalizations, and redactions. The complete object is schema-validated before process execution; invalid input executes no GATE and writes no RUN. Validation compares retained evidence with the current GATE and reports `RUN_CONTRACT_STALE` after any change. Legacy automatic RUNs created by earlier tool versions may omit this backward-compatible field and therefore do not attest the added dimensions; record a new RUN before making those claims. `gap-plan` validates QA readiness but does not require a verified QA RUN; `verified-mvp`, `gap-closure`, and `closed` do.

The plan and GATE both declare `blocked_exit_codes: [7]`. The repository-owned wrapper performs capability/startup/readiness preflight and exits `7` on an infrastructure block; `record-run` retains stdout/stderr and `RUN_DECLARED_BLOCK` as `BLOCKED`, returns `7`, and skips all declared artifacts because the gate might not have produced them. For another nonzero observed exit, `record-run` retains the exact code and current emitted failing result as `FAIL`, then returns `5`. On success the gate writes `ci.result_path` using `clone-full-stack-qa-result/v1`; verified profiles require its exact plan/GATE/environment/project/journey/exchange/binding/supporting/external identity and passing applicable outcomes.

A passing full-stack gate proves only the declared browser action, observed request and response, named API or data postcondition, and retained environment. It does not prove unobserved mid-tier control flow, database constraints, background jobs, third-party provider behavior, or production deployment.

See [Full-stack QA with Playwright](docs/full-stack-qa.md) for the exact plan, index, CI, evidence, failure, and recovery contracts.

## Direct CLI operations

| Command | Exact operation |
| --- | --- |
| `init` | Create a new non-overwriting v2 pack |
| `validate` | Validate a v1 or v2 pack against one named profile |
| `migrate` | Preflight or create a non-overwriting v1-to-v2 successor |
| `capture` | Execute one case or a preflighted, lexical-ID batch and atomically retain evidence |
| `parity` | Compare one pinned reference/clone capture pair |
| `scaffold` | Preview or apply the exact audited scaffold in `scaffold_plan.json` |
| `record-run` | Execute one indexed gate and retain its run evidence |
| `record-manual` | Record a completed manual observation with a pinned procedure, observer, authority, and artifacts |
| `gap-transition` | Apply one legal and evidenced lifecycle transition |
| `assure` | Execute required cases by default, all cases with `--all`, or an explicit case set without installing tools |
| `seal` | Derive and write an integrity seal only for a passing sealable profile |
| `diff` | Compare exact `clone_index.json` record objects by ID between two v2 packs |
| `enhancement-init` | Create a non-overwriting brownfield pack from an authorized repository request |
| `repo-snapshot` | Record or check the adopted or candidate repository state |
| `baseline-run` | Execute immutable adopted-state `PRES` results after selected-set preflight |
| `regression` | Execute candidate preservation cases and compare them with immutable baselines |
| `verify-scope` | Prove every changed path is inside exactly one authorized enhancement mapping |
| `enhancement-transition` | Append one legal, evidenced, hash-chained enhancement lifecycle event |
| `rehash` | Rebind one explicit existing record or case digest without creating evidence |

The complete argument, output, mutation, and exit-status contract is in [CLI reference](docs/cli-reference.md).

## Documentation

- [Getting started](docs/getting-started.md): installation verification and the first exact skill-driven run.
- [Operating workflows](docs/operating-workflows.md): mode selection, phase gates, handoffs, and stop conditions.
- [CLI reference](docs/cli-reference.md): every command, option, mutation, result, and exit code.
- [Clone-pack authoring](docs/clone-pack-authoring.md): file authority, identities, graph rules, profiles, hashes, and immutable evidence.
- [Brownfield enhancement workflow](docs/brownfield-enhancement.md): adopted repositories, preservation, scope, lifecycle, and verified handoff.
- [Full-stack QA with Playwright](docs/full-stack-qa.md): optional browser-to-persistence plan, target-owned CI gate, and exact claim boundary.
- [Runtime enforcement boundaries](docs/runtime-enforcement-boundaries.md): exact tool `2.2.0` proof and execution boundaries.
- [Troubleshooting](docs/troubleshooting.md): deterministic responses to common diagnostics and holds.
- [Contributing](docs/contributing.md): repository change rules and verification gates.
- [CC0 1.0 Universal dedication](LICENSE): canonical public-domain dedication and fallback terms.
- [Skill contract](SKILL.md): compact instructions loaded by Codex.
- [Product playbooks](references/): product-specific observation and MVP contracts loaded as needed.
- [Changelog](changelog.md): recorded implementation and documentation changes.

## Repository layout

```text
clone-software/
├── AGENTS.md                TDD, branch, push, PR, and no-merge contract
├── .github/                 read-only CI, dependency review, and Dependabot policy
├── LICENSE                  canonical CC0 1.0 Universal legal text
├── SKILL.md                 Codex runtime instructions
├── README.md                GitHub and human entry point
├── changelog.md             recorded changes
├── agents/openai.yaml       Codex UI metadata
├── docs/                    human operating documentation
├── references/              AI-loaded contracts and product playbooks
├── assets/templates-v2/     v2 pack source templates
├── assets/schemas/          executable JSON schemas
├── assets/scaffolds/        audited dependency-free project skeletons
├── scripts/clone_pack.py    unified v2 command entry point
├── scripts/clonepack/       v2 implementation
└── tests/                   offline regression and adversarial tests
```

`scripts/new_clone_pack.py` is retained only for clone-pack/v1 compatibility. Do not use it for new work. `scripts/validate_clone_pack.py` is a compatibility dispatcher; new automation uses `scripts/clone_pack.py validate` with an explicit profile.

## Verification

Run the full offline suite from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_skill_tests.py
```

Run the security-focused capture suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests.test_capture_adversarial_security
```

For the tool `2.1.0` tree recorded on 2026-07-19, the complete offline suite passed 194 tests on Python 3.12.3. The same tree passed all four brownfield cold trials, Skill Creator validation, compilation of `scripts` and `tests`, and Draft 2020-12 meta-validation of all 17 packaged schemas. These are local results; hosted CI status belongs to the pull request.

The recorded tool `2.0.0` documentation baseline passed 114 tests on 2026-07-18 in 190.726 seconds, including 15 adversarial capture-security cases and 7 GitHub-documentation contract tests. That historical result is not a claim about the current tree; current results belong in the pull request handoff.

## Exact limitations

- The four audited scaffolds are the only greenfield scaffold profiles. There is no custom scaffold mode.
- The scaffolder never runs the returned setup, test, build, or run commands.
- Capture and comparator drivers must already be installed. The runner never downloads them.
- The optional full-stack QA plan validates a target-owned Playwright and CI contract; the clone-pack runtime does not generate or install the target's Playwright package, browser, services, or dependency graph, execute readiness probes during validation, parse CI YAML, parse the lockfile, or prove that a declared package/version is installed.
- A Playwright process, trace, screenshot, navigation, or web-capture `PASS` alone is not full-stack proof. The required journey also needs current request/response, service, persistence, identity-binding, trace-link, gate, and retained `PASS` run evidence.
- Full-stack validation covers only the declared browser, renderer, viewport, environment, services, fixtures, journeys, wire exchanges, supporting-service assertions, and external-boundary assertions. A sandbox/stub proves only the application interaction with that boundary; unobserved provider behavior, constraints, jobs, browsers, and production conditions remain unproved.
- The full-stack identity validator checks the plan and canonical result evidence. It recomputes the concrete wire-path segment hash, but it does not introspect service or persistence internals; their matching `captured_value_sha256` and consumer hashes remain assertions emitted by the repository-owned gate.
- The runtime hashes the target CI workflow but does not parse CI YAML or prove that a hosted job invoked the indexed GATE. Confirm the required-check configuration and hosted run separately; a local retained RUN proves only the local declared environment.
- `init` does not inspect or authenticate the reference and does not compute a baseline digest.
- A capture `PASS` means evidence acquisition succeeded; it does not mean the observed product returned a successful business result.
- `record-manual` records an observation already performed; it does not execute the procedure.
- `record-run` retains stdout, stderr, and declared regular-file artifacts after containment and governed redaction checks. It cannot recover output that an external process never produced.
- Parity is dimension-specific. Behavioral parity does not imply visual, performance, accessibility, wire, security, or operational parity.
- `diff` compares index record objects only, returns exit `0` when differences exist, and does not compare documents, manifests, evidence bytes, or seals.
- The built-in `seal.json` is an unsigned integrity manifest. Signing requires a separately pinned repository process and recorded provenance.
- A v1 pack cannot receive v2 evidence-backed certification. Migrate it, reconcile every reported loss, and validate the successor.
- Profiles prove only their governed records and retained evidence; they do not infer behavior, environments, consumers, or external systems that were not exercised.
- `assure` executes required cases by default. `--all` includes optional cases; neither form installs a missing tool.
- Missing executables, process-start failures, timeouts, and repository wrappers returning a declared infrastructure exit `7` produce blocked run evidence, not a successful gate.
- Successor seals require retained predecessor seal bytes and exact schema/pack/revision/manifest/seal-digest `supersedes` lineage; predecessor governed files must be validated before successor edits. The built-in seal remains unsigned.
- No profile proves legal rights, production readiness, external security review, or correctness outside the retained artifacts and exact profile contract.
