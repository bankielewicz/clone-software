# Getting started

This guide installs `clone-software`, verifies the installation, defines the complete request input, starts one authorized clone task through Codex, and explains the first generated result.

## 1. Choose the discovery scope

Use one location:

| Scope | Exact directory | Selection rule |
| --- | --- | --- |
| User | `$HOME/.agents/skills/clone-software` | Use when the skill applies across unrelated repositories for one user |
| Repository | `<repository>/.agents/skills/clone-software` | Use when the skill is governed with one repository |

Codex scans `.agents/skills` from its current working directory through the repository root and also scans `$HOME/.agents/skills`. The directory may be a symlink. These locations come from OpenAI's current [Build skills](https://learn.chatgpt.com/docs/build-skills.md) documentation.

Do not install two copies with the same `name: clone-software` in overlapping scopes. Codex can show both; it does not merge them.

## 2. Install without overwriting

For user scope, verify that the destination is absent:

```bash
test ! -e "$HOME/.agents/skills/clone-software"
```

Exit `0` means the path is absent. A nonzero result means stop and inspect the existing path.

Copy the checkout:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R "/absolute/path/to/clone-software" "$HOME/.agents/skills/clone-software"
```

For repository scope, use the same absence check and copy operation with `<repository>/.agents/skills/clone-software` as the destination, then run verification against that repository destination. PowerShell 7 installation commands are in [README installation](../README.md#install-the-skill-for-codex).

To develop from one checkout without copying, create a symlink at the selected discovery location whose target is the absolute `clone-software` checkout. Codex follows symlinked skill directories.

## 3. Verify the installed files

The installed directory MUST contain:

```text
SKILL.md
agents/openai.yaml
assets/schemas/
assets/scaffolds/
assets/templates-v2/
references/
references/full-stack-qa.md
docs/full-stack-qa.md
scripts/clone_pack.py
scripts/check_wsl_trial_workspace.py
scripts/clonepack/
```

Run:

```bash
python3 "/absolute/path/to/installed/clone-software/scripts/clone_pack.py" --help
```

The process MUST exit `0`. Its positional command list MUST contain these 19 names:

```text
init validate migrate capture parity scaffold
record-run record-manual gap-transition assure seal diff
enhancement-init repo-snapshot baseline-run regression verify-scope
enhancement-transition rehash
```

In Codex CLI or the IDE extension, type `$` or run `/skills` and confirm that `clone-software` appears. Codex detects changes automatically. If it remains absent, restart Codex once, confirm the discovery path, and check that `SKILL.md` has valid YAML frontmatter.

## 4. Run the isolated WSL trial

Use [the WSL installer](../scripts/install_clone_software_wsl.sh) when the objective is to clone the project into one new directory and test `$clone-software` against the checked-in [Minecraft-inspired clean-room request](../assets/prompts/minecraft-clean-room-mvp.md). It creates this exact layout:

```text
<destination>/
├── clone-software/                         cloned Git checkout
├── installation-receipt.json               canonical v2 source/head/workspace receipt
└── minecraft-clone/
    ├── .agents/skills/clone-software       symlink to ../../../clone-software
    └── MINECRAFT_CLONE_PROMPT.md            exact prompt copy
```

The destination MUST be absolute and absent. Its immediate parent MUST already exist as a directory; the installer does not create missing destination ancestry. The destination itself and every existing ancestor directory MUST NOT be a symlink. The installer also refuses an overlapping `clone-software` skill discovered at any of these paths:

- `$HOME/.agents/skills/clone-software`;
- `$HOME/.codex/skills/clone-software`;
- `$CODEX_HOME/skills/clone-software` when `CODEX_HOME` is nonempty and resolves somewhere other than the default above;
- `/etc/codex/skills/clone-software`; or
- `.agents/skills/clone-software` beneath an existing ancestor of the destination.

On `INSTALL_SKILL_DUPLICATE`, deliberately move the existing installation outside every Codex discovery location or use a clean WSL home/profile and destination ancestry. The installer does not move, overwrite, or delete the existing skill.

An unset or empty `CODEX_HOME` adds no candidate beyond `$HOME/.codex/skills/clone-software`. A nonempty value must be an absolute path without ASCII control characters. Its nearest existing lexical ancestor must be a searchable directory; a regular-file ancestor, dangling-symlink ancestor, or non-searchable directory returns exit `4` with `INSTALL_CODEX_HOME_INVALID` before cloning. Existing symlinks that resolve to searchable directories are resolved with `realpath -m` before the custom discovery candidate is checked.

Run from a clone-software checkout in WSL:

```bash
bash scripts/install_clone_software_wsl.sh \
  --destination "$HOME/clone-software-codex-test"
```

The command requires WSL and executable `uname`, `realpath`, `dirname`, `basename`, `mktemp`, `git`, Python 3.10+ as `python3`, Node.js 18+ as `node`, `npm`, `mv`, `stat`, and Codex. The later prompt additionally requires executable `sha256sum` for its exact GUI-artifact digest command. Default source/ref are `https://github.com/bankielewicz/clone-software.git` and `main`; default verification is `smoke`. To test a not-yet-merged branch, pass its exact name with `--ref`; otherwise omit `--ref` and receive `main`.

The installer-authored steps do not install Codex, Node packages, Python packages, Playwright, browsers, or operating-system packages. Verification does execute `scripts/clone_pack.py` from the cloned source as the current WSL user, and `--verify full` also executes that source's `scripts/run_skill_tests.py`. Those programs can perform any action allowed to the current user. Use only a source and ref whose code you trust; the installer does not sandbox cloned code or constrain its effects.

Options:

| Option | Exact contract |
| --- | --- |
| `--destination <absolute-path>` | Required absent, non-root root whose immediate parent already exists; the path and every existing ancestor must not be a symlink; no overwrite or update mode exists |
| `--repo-url <url-or-path>` | Git URL or local Git repository; default is the public clone-software repository; URL/SCP user information is rejected, and any source value containing `?`, `#`, or an ASCII control character is rejected |
| `--trust-custom-source-code` | Required when `--repo-url` differs from the default; acknowledges current-user execution but does not sandbox or make the source trustworthy |
| `--ref <branch-or-tag>` | Exact clone branch or tag; default `main`; raw commit IDs are not accepted as branch names by this interface |
| `--verify smoke` | Validate the exact assets and metadata below, execute `clone_pack.py --help`, require all 19 commands, and require unchanged complete checkout identity before and after execution |
| `--verify full` | Perform smoke verification and run `PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_skill_tests.py` in the staged clone before the final identity check |
| `--codex-bin <command-or-absolute-path>` | Resolve an existing Codex executable to a path without running, version-checking, or installing it |
| `--allow-non-wsl` | Permit the same installer contract on non-WSL Linux for CI and installer testing |

The smoke asset contract requires these regular, non-symlink files:

```text
LICENSE
SKILL.md
agents/openai.yaml
scripts/clone_pack.py
scripts/check_wsl_trial_workspace.py
scripts/run_skill_tests.py
assets/prompts/minecraft-clean-room-mvp.md
assets/scaffolds/catalog.json
assets/scaffolds/static-web-esm/README.md
assets/scaffolds/static-web-esm/package.json
assets/scaffolds/static-web-esm/index.html
assets/scaffolds/static-web-esm/styles.css
assets/scaffolds/static-web-esm/src/app.js
assets/scaffolds/static-web-esm/tests/smoke.test.mjs
assets/scaffolds/static-web-esm-allowlist/README.md
assets/scaffolds/static-web-esm-allowlist/package.json
assets/scaffolds/static-web-esm-allowlist/index.html
assets/scaffolds/static-web-esm-allowlist/styles.css
assets/scaffolds/static-web-esm-allowlist/src/app.js
assets/scaffolds/static-web-esm-allowlist/tests/smoke.test.mjs
assets/scaffolds/static-web-esm-allowlist/tools/serve_static.py
assets/scaffolds/static-web-esm-allowlist/serve_manifest.json
references/evidence-and-fidelity.md
references/document-contracts.md
references/greenfield.md
references/game-simulation.md
references/security-and-provenance.md
references/pack-evolution.md
```

It also requires the non-symlink directories `scripts/clonepack/`, `assets/schemas/`, and `assets/templates-v2/`. Every required file in the list must decode as UTF-8. `SKILL.md` must have scalar string `name: clone-software` and a scalar, non-null, nonempty string description in its YAML frontmatter. A supported plain scalar matches `[A-Za-z$][A-Za-z0-9 $.,;/()_+\-!?@]*`; a double-quoted scalar must parse completely as one nonempty JSON string; a single-quoted scalar must end exactly and represent internal quotes only through doubled single quotes. Sequence, mapping, boolean, numeric, nonfinite, partially quoted, control-bearing, and trailing-token values are rejected. `agents/openai.yaml` uses the same scalar contract for its interface fields, and the parsed `default_prompt` scalar itself must invoke `$clone-software`. The catalog schema must be exactly `clone-scaffold-catalog/v2`; legacy `static-web-esm` retains its existing six paths and commands. `static-web-esm-allowlist` has the same six product paths plus `tools/serve_static.py` and `serve_manifest.json`; its start command remains `["npm","start"]`, whose package script is exactly `python3 tools/serve_static.py --manifest serve_manifest.json --bind 127.0.0.1 --port 8000`.

The clone uses `git clone --no-hardlinks`, so a local source and staged clone do not share Git-object inodes. Before executing cloned code, the installer records the complete checkout identity, including ordinary and ignored worktree entries, file modes, symlink text, and `.git` metadata. It revalidates status, HEAD/branch state, complete identity, and install-tree semantics after verification, after workspace staging and before receipt creation, and again immediately before bound publication. The receipt binds that last unchanged identity. Any observed byte, mode, path, Git HEAD, branch/detached state, or semantic metadata change refuses publication. No generated verifier output is excluded from this comparison.

After confirming that the operator-selected destination parent already exists, the installer records its lexical device/inode, opens that exact directory, and requires the bound and post-open lexical identities to match before running discovery checks. Staging and publication use `/proc/<installer-pid>/fd/<bound-fd>` rather than re-resolving the user-supplied parent. The lexical destination ancestry and bound identity are rechecked after discovery, after staging, and immediately before and after publication. A replacement or symlink produces `DESTINATION_SYMLINK` or `INSTALL_DESTINATION_PARENT_CHANGED`; it is not followed for staging or publication.

Exits and publication behavior:

| Exit | Meaning | Published destination |
| ---: | --- | --- |
| `0` | Clone, verification, prompt copy, symlink, receipt, and atomic publish succeeded | Complete |
| `2` | Invalid or missing argument/path contract | Absent |
| `3` | Non-WSL kernel without `--allow-non-wsl` | Absent |
| `4` | Destination/symlink/duplicate collision, invalid `CODEX_HOME`, parent-identity change, invalid tree, or cloned-content/checkout-identity mismatch | Existing paths preserved and requested destination absent unless the parent changed after the bound atomic publish; inspect the exact diagnostic and retained path in that concurrent case |
| `6` | Staging or destination write/publish failure | Absent unless an external concurrent filesystem event prevents the final rename contract |
| `7` | Required executable/version or Git clone source unavailable | Absent |
| `70` | Unexpected script failure | Absent; inspect the diagnostic and destination parent |

The installer never recursively deletes a failed-install staging directory. When the original parent and stage identities remain at their lexical paths, it emits `INSTALL_STAGE_RETAINED` with a durable `$destination_parent/.clone-software-wsl-install.<suffix>` path that still exists after process exit. If either pathname was replaced, it emits `STAGE_CLEANUP_REFUSED` with the requested parent and stage basename, explicitly without claiming a durable path; it does not delete the replacement. Inspect ownership and content before deliberately removing anything. The installer never deletes or replaces a pre-existing requested destination.

Workspace directories, the copied prompt, and the repository-scoped skill link are created through non-following directory descriptors. Receipt creation uses exclusive, non-following file creation. Immediately before publication, `INSTALL_HANDOFF_MUTATED` blocks any unexpected root/workspace entry, changed prompt byte/digest, changed skill-link text/target, or receipt byte that differs from the exact canonical expected object.

`installation-receipt.json` records schema `clone-software-wsl-test-install/v2`, source, requested ref, resolved full Git HEAD, checkout state, complete checkout-identity SHA-256, final project/workspace/link/prompt paths, prompt SHA-256, verification mode, absolute regular executable path selected for Codex, and `installed_workspace_inventory`. `resolved_head` is exactly a lowercase 40-hex SHA-1 or 64-hex SHA-256 Git object ID; every other length, case, or character is rejected by the workspace checker as receipt schema exit `2`. The inventory is sorted by relative path. Directory records contain integer mode; regular-file records contain integer mode, size, and SHA-256; the skill symlink record contains integer mode, non-followed target text, and the SHA-256 of that UTF-8 text. The receipt proves installer output and pre-Codex workspace contents. It is not signed and does not prove provider ownership, execute or attest Codex, prove discovery, or prove product behavior.

After exit `0`:

```bash
cd "$HOME/clone-software-codex-test/minecraft-clone"
codex
```

Inside Codex, first run `/skills`. Continue only when `clone-software` appears. This manual observation is the Codex discovery check; executable-path resolution and the receipt are not substitutes. Then paste:

```text
Use $clone-software. Read ./MINECRAFT_CLONE_PROMPT.md completely and execute it exactly.
```

The prompt first runs this exact read-only command before any product write:

```bash
python3 .agents/skills/clone-software/scripts/check_wsl_trial_workspace.py \
  --workspace . \
  --receipt ../installation-receipt.json \
  --allow-runtime-path .codex \
  --authority-id DEC-004 \
  --phase pre-write
```

Exit `0` emits one canonical `clone-software-wsl-workspace-check/v1` JSON result. The installed inventory may be unchanged, or it may have one additional `.codex` classified `TOOL_RUNTIME_EXCLUDED` only when the v2 receipt proves pre-session absence and the live entry is a real, empty directory with no write bits. The result retains device, inode, mode, emptiness, `USER_PINNED` owner claim, `DEC-004`, and `E-002`; it does not claim provider ownership. The result key `product_inventory` is a v1 compatibility field: it includes `.agents` repository-scoped skill input and the prompt, so it is not a product-only inventory or product hash. Missing or v1 evidence, content, symlink/type mismatch, write bits, replacement, disappearance, or recheck drift exits `4` with `RUNTIME-001`. Another undeclared initial root entry exits `4` with `REPO-001`. Never delete, rename, chmod, or globally ignore `.codex` to make this check pass.

The prompt reruns `--phase pre-write` immediately before the first workspace write and retains its exact canonical stdout at `docs/clone/evidence/raw/workspace-check/pre-write.json`. After all authorized writes, it runs `--phase handoff --baseline-result docs/clone/evidence/raw/workspace-check/pre-write.json`. Handoff mode permits reported product additions, requires receipt-bound installer inputs unchanged, and exact-compares the live runtime exclusion with the retained pre-write result; the prompt separately exact-compares the reported paths with its authorized product fence. It also exact-binds receipt `project_dir` to the installation root's `clone-software` directory and recomputes `checkout_identity_sha256` twice with descriptor-safe traversal. A symlinked checkout root, a working-tree symlink, a multiply linked regular file, an unsupported or unreadable object, concurrent mutation, or a digest mismatch is `RUNTIME-001`; `.git` symlink text is hashed without following its target. It then builds an original finite WebGL 2 voxel-sandbox MVP from its own `USER_PINNED` requirements and uses `static-web-esm-allowlist` so the local server cannot expose the prompt, evidence, tests, or repository/tool metadata. It forbids target code/assets/branding, network dependencies, and implicit installs. Node/Python checks can complete from the terminal. GUI proof requires an actually available authorized browser observer; otherwise the required terminal result is workflow `HOLD` with the exact browser-evidence gap, not an invented pass.

## 5. Prepare the request record

Supply every row whose value is known. Use `UNKNOWN_BLOCKER` only when the missing value changes behavior, rights, security, data ownership, compatibility, architecture, distribution, or the MVP boundary. An unknown is not permission for Codex to select a conventional default.

| Field | Required content |
| --- | --- |
| Intent/mode | One of `mvp-build`, `spec-only`, `gap-plan`, `gap-implement`, or `pack-migrate` |
| Requester | Named person or organization supplied by the user |
| Authorization basis | Ownership, license, engagement, or explicit permission |
| Reference | Exact URL, path, artifact, release, build, commit, digest, or dated snapshot |
| Reference evidence environment | Exact indexed environment identity, OS/runtime/browser/device, locale, time zone/clock, viewport, flags, fixtures, reset state, endpoint, and isolation boundary |
| Clone evidence environment | Exact environment identity and settings used to make comparison preconditions equivalent |
| Accounts/roles | Exact synthetic/authorized reference and clone account identities, tenant, role, permissions, and starting state |
| Permitted sources | Exact documentation, artifacts, accounts, endpoints, and environments |
| Permitted actions | Exact observation, capture, test, or mutation operations |
| Prohibited actions | Access-control bypass, production writes, destructive probes, load tests, or other exclusions |
| Distribution target | `local evaluation`, `internal`, `customer`, `public`, or `production` |
| Branding/assets rights | Exact reuse authority, replacement requirement, or blocker |
| Data policy | Synthetic, redacted, or specifically authorized dataset |
| Secrets policy | Exact environment-variable names and storage prohibition; never include values in the request or pack |
| Product type | One controlled type and every applicable playbook for a hybrid |
| Clone repository | Existing absolute repository root |
| Pack output | Absent repository-relative directory, normally `docs/clone` |
| MVP boundary | Named actors and complete vertical journeys, including validation, persistence, failure, and recovery |
| Full-stack QA applicability | `applicable` only when a selected journey crosses browser UI, real request and response, an application-owned API or data postcondition, and persistence after reload/relogin/restart; otherwise `not-applicable` with the exact missing layer |
| Full-stack QA repository capabilities | Existing package manager/lockfile, controlled Playwright package (`@playwright/test`, `playwright`, or `playwright-core`) and declared version, browser source, configuration/test/workflow paths, frontend/mid-tier/backend/persistence commands, reset/migration/seed/readiness/cleanup commands, indexed GATE argv, expected exit, `fresh_artifact_paths`, and declared artifacts; runtime does not parse the lockfile or prove installation |
| Full-stack QA identity binding | Each `identity_bindings` `BIND-###` source exchange/response JSON Pointer, binding name, concrete additional-exchange path containing `{binding_name}`, and `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` contract pointers |
| Full-stack QA external dependencies | Each external sandbox, stub, or exclusion plus its authority decision; each non-excluded interface has exact protocol, endpoint, and `LOOPBACK` or `AUTHORIZED_SANDBOX` classification; application-owned services remain real |
| Stop condition | Exact passing profile or exact `HOLD`/`HALT` handoff |

Controlled product types are:

```text
website web-app-saas api-service-server client-app library-sdk cli
browser-extension ai-ml-system data-pipeline database-storage
distributed-realtime game-simulation embedded-iot hybrid
```

Every non-hybrid product consumes its matching playbook. A hybrid consumes at least two playbooks.

## 6. Invoke Codex

Use this request shape and replace every value after a colon:

```text
Use $clone-software in mvp-build mode.

Requester: Example Product Team.
Authorization basis: Example Product Team owns the reference and authorizes a clean-room internal clone.
Reference: local release 2.7.0 artifact at /srv/reference/example-2.7.0.tar; SHA-256 recorded at /srv/reference/example-2.7.0.sha256.
Reference evidence environment: ENV-001 on Ubuntu 24.04 x86_64, Chromium at 1280x720, en-US, UTC, synthetic fixture set record-v1, reset before each case, isolated endpoint http://127.0.0.1:9100.
Clone evidence environment: the same ENV-001 host/settings/fixture contract, isolated endpoint http://127.0.0.1:9200.
Accounts/roles: reference account ref-member@example.invalid and clone account clone-member@example.invalid, both in the member role and isolated test tenant.
Permitted sources: that artifact, its bundled manual, and ordinary interactions with the isolated reference deployment at http://127.0.0.1:9100.
Permitted actions: GET requests and synthetic create/read/update/delete operations against the isolated resettable tenant.
Prohibited actions: no production access, no external traffic, no load or security testing, no reference credential collection, and no source extraction.
Distribution target: internal.
Branding/assets rights: replacement branding and synthetic content are required.
Data policy: synthetic fixture records only.
Secrets policy: REFERENCE_TEST_AUTH and CLONE_TEST_AUTH environment-variable indirection only; no values in the request, plans, commands, logs, screenshots, or fixtures.
Product type/playbooks: hybrid with web-app-saas and api-service-server.
Clone repository: /srv/work/example-clone.
Pack output: docs/clone.
MVP boundary: a member authenticates, creates a valid record, receives the exact invalid-input error for one invalid record, reloads the application, reads the persisted valid record, and signs out; an unauthenticated read is rejected with the observed outcome.
Full-stack QA applicability: applicable to the create-and-reload journey; capture `captured_record_id` from the POST response at `/id`, bind it to the concrete GET path `/records/{captured_record_id}`, the service probe, and the persistence postcondition, and require the result's captured and consumer SHA-256 values to match.
Full-stack QA repository capabilities: use only the repository's pinned `@playwright/test`, `playwright`, or `playwright-core` package/browser/configuration and its existing no-shell GATE argv; declare `ci.result_path` in both artifact paths and `fresh_artifact_paths`; do not install Playwright, browser binaries, Node packages, or application services through the skill. Runtime hashes but does not parse the lockfile or prove installation.
Full-stack QA external dependencies: none; the frontend, mid-tier, backend, and persistence services are application-owned and real.
Stop condition: return a sealed verified-mvp pack or workflow HOLD with exact command/status/exit diagnostics, blocked IDs, retained mismatch evidence, implementation-ready non-MVP gaps, and one resolution question for each behavior-changing unknown.
```

The names and paths above are examples. They are not defaults.

## 7. Expected Codex sequence

Codex performs these actions in order:

1. Reads `SKILL.md`, `references/evidence-and-fidelity.md`, and `references/document-contracts.md`.
2. Reads every product playbook named by the request.
3. Reads capture, greenfield, security, evolution, or full-stack QA contracts only when those operations apply.
4. Inspects repository instructions and current state without modifying product code.
5. Records authorization, prohibited actions, reference identity, environments, and data/secret policies.
6. Creates a non-overwriting v2 pack with `clone_pack.py init` or adopts the named existing pack.
7. Replaces required markers with evidence or an exact blocker, creates index records and reciprocal links, and validates `baseline-ready`.
8. Captures or binds enough authorized reference evidence to specify the selected MVP and validates `spec-ready`.
9. In `spec-only`, stops here without product-code edits.
10. In implementation modes, pins repository state, stack/scaffold disposition, architecture, provenance, gates, and assurance. When a selected journey crosses UI, wire, application-owned service, and persistence, it also copies and binds `full_stack_qa_plan.json`, including controlled package, external-interface classification, fresh-result, and `BIND-###` identity contracts, then validates `build-ready` or `enhancement-ready` before product-code edits.
11. Implements dependency-ordered vertical slices, records runs, captures reference and clone evidence, executes parity and assurance, and retains failures. A full-stack journey runs only through the indexed target-repository GATE and emits a newly created or rewritten `clone-full-stack-qa-result/v1` at `ci.result_path`; an unchanged pre-existing file is rejected as `RUN_ARTIFACT_STALE`. The result carries `captured_value_sha256` and matching `observed_value_sha256` values for every identity consumer. The skill never installs Playwright or declares an application-owned layer as stubbed.
12. Requires the latest linked run to be `PASS` and its retained canonical result to match every declared full-stack journey, identity binding, and governed dependency, seals only a passing sealable profile, and returns the highest passing profile plus gaps and blockers. It never deploys, publishes, merges, or mutates production.

Codex halts rather than guesses when a missing decision changes the contract.

## 8. Recognize the first generated pack

A new pack contains:

```text
docs/clone/
├── clone_pack.json
├── clone_index.json
├── clone_brief.md
├── evidence_ledger.md
├── clone_specification.md
├── mvp_build_plan.md
├── acceptance_matrix.md
├── gaps_analysis.md
├── gap_implementation_plan.md
├── architecture_decisions.md
├── security_assurance.md
├── provenance_ledger.md
├── capture_plan.json
├── parity_plan.json
├── scaffold_plan.json
├── assurance_plan.json
├── evidence/
├── runs/
└── history/gap_events.jsonl
```

`init` does not create `full_stack_qa_plan.json`. When an applicable four-layer journey is established before `build-ready` or `enhancement-ready`, Codex copies `assets/templates-v2/full_stack_qa_plan.json` to that exact pack-root path and adds `plans.full_stack_qa` to the manifest. Packs without an applicable journey omit both the file and manifest entry.

Immediately after `init`, only the `scaffold` profile is expected to pass. The pack intentionally contains unresolved markers and unresolved baseline/repository state. `STRUCTURAL PASS` is not source, specification, implementation, parity, assurance, security, or release certification.

## 9. Run the first validator explicitly

Set local shell variables to actual absolute paths:

```bash
SKILL_ROOT="/absolute/path/to/clone-software"
PACK="/absolute/path/to/clone-repository/docs/clone"
```

Run:

```bash
python3 "$SKILL_ROOT/scripts/clone_pack.py" validate "$PACK" \
  --profile scaffold \
  --format json
```

Expected machine shape on success:

```json
{
  "diagnostics": [],
  "profile": "scaffold",
  "schema_version": "clone-pack/v2",
  "status": "PASS"
}
```

Then request the next actual profile. Do not skip directly to `verified-mvp` to suppress lower-level diagnostics.

## 10. Interpret the terminal response

A complete skill handoff includes:

- selected operating mode;
- frozen reference baseline and environment;
- highest passing profile;
- semantic-audit result for the current tool boundaries;
- exact commands and exit results;
- exact implemented and verified MVP boundary;
- full-stack plan, target CI/GATE, controlling `RUN` ID, retained canonical-result path/hash, separate UI/wire/service/persistence outcomes, `BIND-###` captured/consumer hashes, and external-interface classifications when the optional plan is present;
- pack and seal paths, when a seal exists;
- gap counts by class and status;
- blocked IDs and decisions; and
- next dependency-safe gap IDs.

If the handoff reports workflow `HOLD`, inspect the exact nested command result. Validator `status: HOLD`/exit `5` is one possible cause. Validator `FAIL`/exit `1` or `4`, infrastructure exit `7`, and unresolved authority decisions can also cause a workflow `HOLD`. Preserve the original status, exit, diagnostics, and evidence; do not relabel every blocking result as validator `HOLD`.

The CLI has no generic command to create an index record, capture/parity case, or gap. Use the exact recovery prompt in [Troubleshooting](troubleshooting.md#skill-driven-pack-recovery) or edit the governed pack directly according to [Clone-pack authoring](clone-pack-authoring.md), then rerun the same failing profile.

Next: [Operating workflows](operating-workflows.md), [Clone-pack authoring](clone-pack-authoring.md), [Full-stack QA with Playwright](full-stack-qa.md), and [Troubleshooting](troubleshooting.md).
