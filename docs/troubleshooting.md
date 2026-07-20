# Troubleshooting

Use the diagnostic code, path, record ID, and process exit together. Do not suppress a diagnostic by deleting evidence, weakening an oracle, increasing a tolerance without authority, or changing status prose.

For complete diagnostics, run:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile <intended-profile> \
  --format json \
  --max-problems 0
```

JSON validation output contains all diagnostics. `--max-problems` limits text rendering only.

## Skill is not visible in Codex

Checks:

1. Confirm the directory is exactly `$HOME/.agents/skills/clone-software` or `<repo>/.agents/skills/clone-software` beneath the current working directory's repository ancestry.
2. Confirm `SKILL.md` exists directly inside that directory.
3. Confirm the frontmatter starts with `name: clone-software` and has a nonempty `description`.
4. In CLI/IDE, type `$` or run `/skills`.
5. If an update remains absent, restart Codex once.
6. Check for another installed skill with the same name. Codex does not merge duplicates.

For a WSL trial installed by `scripts/install_clone_software_wsl.sh`, launch Codex from the receipt's `workspace_dir`, not from `clone-software/` or an unrelated directory. The repository-scoped link exists at `minecraft-clone/.agents/skills/clone-software`. If `/skills` still omits it, exit Codex, confirm the link resolves to the receipt's `project_dir`, and launch Codex once more from `workspace_dir`.

## WSL trial installer diagnostics

The installer writes diagnostics to stderr and publishes nothing until its staged clone, prompt, symlink, receipt, and selected verification pass. Its own steps do not install Codex, Node packages, Python packages, browsers, Playwright, or system packages. It does execute Python from the cloned repository as the current WSL user, and `--verify full` executes the cloned test runner. That code is not sandboxed by the installer and can perform any action allowed to the user. Use only a trusted source and ref.

| Diagnostic | Meaning | Exact recovery |
| --- | --- | --- |
| `INSTALL_USAGE` or `INSTALL_PATH_INVALID` | An option is missing/unknown, verification is not `smoke`/`full`, or destination is not an absolute non-root path | Run `bash scripts/install_clone_software_wsl.sh --help`; supply one absent absolute `--destination` |
| `INSTALL_SOURCE_TRUST_REQUIRED` | A non-default `--repo-url` was supplied without acknowledging cloned-code execution | Review the exact source and ref; rerun with `--trust-custom-source-code` only when you trust that code to execute as the current user |
| `INSTALL_SOURCE_UNSAFE` | The repository source contains user information in URL/SCP syntax, query text, a fragment, or a control character | Use a credential-free source URL or local path; keep authentication in existing Git credential/SSH configuration and never in an argument, diagnostic, or receipt |
| `INSTALL_PLATFORM_UNSUPPORTED` | The kernel is not WSL | Run inside WSL; use `--allow-non-wsl` only for an intentional Linux CI/test trial |
| `INSTALL_EXECUTABLE_MISSING`, `INSTALL_EXECUTABLE_FAILURE`, `INSTALL_PYTHON_UNSUPPORTED`, `INSTALL_NODE_UNSUPPORTED`, `INSTALL_NPM_UNAVAILABLE`, or `INSTALL_CODEX_UNAVAILABLE` | A required preinstalled capability is missing, failed its probe, or is below the pinned version | Install or select it outside this script, then rerun with the same absent destination; `--codex-bin` must resolve through `PATH` or an explicit path to an absolute regular executable file |
| `DESTINATION_EXISTS` | The requested destination existed before start or appeared before atomic publish | Do not delete it automatically. Inspect it and choose another absent path, or deliberately move it outside this workflow before rerunning |
| `DESTINATION_SYMLINK` | The destination or an existing ancestor resolves through a symlink | Choose an absent absolute path whose existing ancestors are real directories; the installer never follows the link for publication |
| `INSTALL_DESTINATION_PARENT_CHANGED` | The destination parent's current device/inode no longer matches the open directory binding | Stop concurrent mutation, inspect the named parent and any retained stage or already-bound published directory, then use a new absent destination; do not infer which pathname owns the bound inode |
| `INSTALL_SKILL_DUPLICATE` | `clone-software` already exists in user, administrator, or destination-ancestor repository discovery scope | Deliberately move the existing skill outside `$HOME/.agents/skills`, `/etc/codex/skills`, and applicable ancestor `.agents/skills` scopes, or use a clean WSL home/profile and destination ancestry; rerun without asking the installer to mutate it |
| `INSTALL_CLONE_BLOCKED` | Git could not clone the exact source/ref | Verify the URL/path, branch or tag, network, and Git authentication outside the script; raw commit IDs are not accepted as `--ref` branch names |
| `INSTALL_ASSET_MISSING`, `INSTALL_TREE_INVALID`, `INSTALL_GIT_INVALID`, `INSTALL_COMMAND_MISSING`, or `INSTALL_SMOKE_FAILED` | The cloned ref is incomplete, contains a forbidden worktree symlink/special path, has invalid skill/agent/catalog metadata, or does not expose the required CLI | Use a trusted ref satisfying the exact smoke asset and metadata contract in [Getting started](getting-started.md#4-run-the-isolated-wsl-trial); do not replace required files with links |
| `INSTALL_CHECKOUT_MUTATED` | Help/full verification changed any tracked, untracked, ignored, or Git-metadata path, mode, HEAD, or checkout state | Treat the source or test runner as mutation-capable; inspect it outside this installer, correct the mutation, commit the intended tree, and retry to a new absent destination |
| `INSTALL_HANDOFF_MUTATED` | The final staged root/workspace inventory, prompt bytes/digest, skill-link text/target, or canonical receipt bytes differ from the exact handoff contract | Treat the cloned verifier as still mutation-capable, inspect the durable retained stage when one is reported, correct the source, and retry to a new absent destination |
| `INSTALL_FULL_VERIFICATION_FAILED` | `--verify full` ran the cloned offline suite and it failed | Preserve stdout/stderr, fix or select a passing ref, and rerun to a new absent destination; do not relabel smoke as full |
| `STAGE_CLEANUP_REFUSED` | A staging pathname or its original parent no longer has the bound device/inode identity | The diagnostic reports the requested parent and stage basename but does not infer a durable current path. Do not delete a guessed path; identify the renamed/replaced directory and its owner first |
| `INSTALL_STAGE_RETAINED` | Another failure occurred and the original parent and stage identities remain at their lexical paths | Preserve it for diagnosis or deliberately remove it only after inspecting the exact durable path reported; the installer performs no recursive cleanup |
| `INSTALL_DESTINATION_FAILURE`, `INSTALL_RECEIPT_FAILURE`, or `INSTALL_INTERNAL_ERROR` | The immediate destination parent is absent, filesystem publication/receipt generation failed, or an unexpected command failed | Create or select the intended real non-symlink parent outside this script, confirm its permissions/free space, and inspect any reported `.clone-software-wsl-install.*`; the installer retains failed stages and never overwrites a requested destination |

After exit `0`, inspect `installation-receipt.json`. Compare `prompt_sha256` with `MINECRAFT_CLONE_PROMPT.md` before editing the prompt. `codex_executable` is path resolution only: the receipt does not attest that binary's version or identity. Launch it from `workspace_dir` and require `/skills` to display `clone-software`. A later workflow `HOLD` for missing GUI evidence is a clone-task result, not an installer failure; use the exact manual browser procedure in the prompt or provision a separately authorized existing observer without changing the product dependency boundary.

## CLI fails to import `clonepack`

Run the entry point by path:

```bash
python3 "/absolute/path/to/clone-software/scripts/clone_pack.py" --help
```

Do not copy only `clone_pack.py`; the sibling `scripts/clonepack/` package is required. Confirm the checkout is complete and readable.

## Skill-driven pack recovery

The CLI has no generic command to add index records, capture/parity cases, or gaps. To recover a pack without manually authoring its graph, invoke the skill with this request and replace every example field:

```text
Use $clone-software in <spec-only, mvp-build, gap-plan, or gap-implement> mode to reconcile an existing clone-pack/v2 pack.

Repository: <absolute path and current revision/diff identity>.
Pack: <absolute path>.
Last passing profile: <exact profile or none>.
Failing command: <exact argv>.
Observed result: exit <integer>, validator status <PASS, FAIL, HOLD, or not-applicable>.
Diagnostics: <complete JSON diagnostics or exact stderr>.
Authorized evidence and decisions available: <exact IDs/paths/facts>.
Product-code authority: <forbidden, or exact selected build/gap fence>.
Evidence rule: preserve every finalized run/capture/parity/assurance result and allocate new stable IDs for replacement cases.
Required action: reconcile the named documents, records, reciprocal links, locators, case hashes, and blockers without guessing; do not weaken oracles/tolerances and do not edit lifecycle state directly.
Terminal condition: rerun the same failing command/profile and return its exact exit/status/diagnostics plus the highest passing profile. If an authority decision is missing, return workflow HOLD with the affected ID and one resolution question.
```

Use `spec-only` for marker, baseline, environment, record, trace, and specification recovery when product code is not authorized. Use `mvp-build` only when the current task already authorizes implementation. Use `gap-plan` or `gap-implement` only for existing governed gaps.

## Destination collision diagnostics

The runtime uses different collision codes:

- `OUTPUT_EXISTS`: initialization and finalized capture/parity/assurance/run output collisions;
- `MIGRATION_DESTINATION_EXISTS`: migration output already exists; and
- `SCAFFOLD_COLLISION`: an audited scaffold destination already exists.

Response by operation:

- `init`: choose a new absent output directory. Reuse the old path only after a human explicitly declares that exact unsealed draft abandoned and follows the correction rule in [Pack evolution](../references/pack-evolution.md).
- `migrate`: choose a new absent successor directory outside the source tree.
- `scaffold`: inspect the collision and reconcile the plan/destination; there is no overwrite mode.
- finalized capture/parity/assurance case: preserve it and assign a new stable plan case ID for replacement evidence.
- run collision: preserve the existing run/index state, reconcile any concurrent writer, and rerun the recording command; the runtime allocates the next available `RUN-###` ID.

Do not delete an active, sealed, migrated, or non-abandoned pack to bypass this diagnostic.

## `MARKER_UNRESOLVED`

Meaning: a document governed by the requested profile still contains `[[REQUIRED: ...]]` or `[[MIGRATION_REQUIRED: ...]]`.

Response:

1. Open the named path.
2. Replace each marker with verified evidence, an exact authority decision, a factual current state such as `NOT_RUN`, an explicit `EXCLUDED`/`NOT_APPLICABLE` decision where permitted, or an `UNKNOWN_BLOCKER`.
3. Add or update the corresponding index record and links.
4. Recompute any affected locator/case hash.
5. Rerun the same profile.

Never replace a marker with invented behavior or a vague sentence.

## `AMBIGUOUS_LANGUAGE`

Meaning: ready prose contains a forbidden placeholder, lowercase modal, or unbounded timing phrase.

Replace it with one of:

- an observed current fact;
- an imperative or uppercase `MUST`/`MUST NOT` rule;
- an exact numeric/string/ordering/timing contract;
- an explicit exclusion with decision; or
- an exact blocker question.

## `BASELINE_UNRESOLVED` or `ENVIRONMENT_MISSING`

Meaning: the pack cannot reproduce the reference context.

Response:

1. Record an immutable reference release/build/commit/artifact digest in `evidence_ledger.md`.
2. Create its `BASE-###` record and set `clone_pack.json.reference_baseline_id` to that ID.
3. Create at least one `ENV-###` record with exact runtime/platform, actor/role, state, fixtures, clock/time zone, locale, flags, and authority.
4. Link capture cases and requirements to the correct records.

The descriptive `reference_source` field is not baseline proof.

## `PLAN_CASE_INDEX_MISSING`, `PLAN_CASE_INDEX_TRACE_INVALID`, or `PLAN_CASE_INDEX_STALE`

Meaning: an executable plan case and its same-ID index record are absent or inconsistent.

Response:

1. Create or inspect the same-ID `CAP`, `PAR`, or `ASSURE` record.
2. Point its locator to the exact plan definition and use an anchor occurring once.
3. Compute the current locator line hash.
4. Compute `attributes.case_sha256` from every case field except top-level `result` using canonical sorted two-space JSON plus one newline.
5. For `CAP`, make `environments` exactly the case environment and `decisions` exactly the union of authorization and redaction authorities.
6. For `PAR`, make `captures` exactly the reference/clone capture IDs and `decisions` exactly normalization authorities.
7. Rerun the same profile before executing the case.

Do not edit only the stored hash; reconcile the case and record semantics first.

## `LOCATOR_INVALID`, `HASH_ANCHOR_MISSING`, or `HASH_ANCHOR_MISMATCH`

Meaning: a record definition cannot be resolved to exactly one current line.

Response:

1. Confirm the locator path exists beneath the pack.
2. Choose an anchor substring that occurs on exactly one UTF-8 line.
3. Read as UTF-8 text with universal-newline translation, split with line endings retained, and hash the one matched line. CRLF and CR normalize to `\n`; an unterminated final line has no ending byte.
4. Update the locator.

If the definition moved or materially changed, also reconcile every consumer and stale result; do not merely refresh the digest.

## `REF_UNDEFINED`, `REF_WRONG_KIND`, or `TRACE_NOT_BIDIRECTIONAL`

Meaning: the graph contains an absent target, an illegal relation-to-kind edge, or a missing reciprocal link.

Response:

1. Inspect the source and target records.
2. Add the missing governed record only if its definition exists.
3. Use a relation permitted for the target kind.
4. Add the exact reciprocal edge from [Clone-pack authoring](clone-pack-authoring.md).
5. Search Markdown for the same ID and reconcile every mention.

Do not remove a link solely to make validation pass if the governing document still asserts the relationship.

## `REPOSITORY_STATE_UNRESOLVED`

Meaning: `build-ready` cannot bind implementation evidence to one repository state.

For a clean Git state, record kind `git` and the exact full revision. For a working tree, record kind `working-tree`, the baseline revision, and lowercase SHA-256 of the complete diff or full-tree inventory. A depth-limited file listing is not a complete inventory.

## `RESULT_STALE`, case hash, revision, diff, baseline, or artifact freshness failure

Meaning: retained evidence no longer proves the current contract.

Response:

1. Identify which governing input changed.
2. Preserve the old final result.
3. Advance the pack revision if governed content changed.
4. Create a new capture, parity, assurance, or run ID as applicable.
5. Execute against the current baseline/repository state.
6. Update trace links and rerun validation.

Do not edit retained result JSON or its plan pointer.

## Full-stack QA contract diagnostics

These diagnostics apply only when `clone_pack.json.plans.full_stack_qa` names `full_stack_qa_plan.json`.

### `QA_CONTRACT_HASH_MISMATCH` or `QA_CONTRACT_ARTIFACT_INVALID`

Meaning: the canonical plan digest or its `ART` locator no longer binds the current plan.

Response:

1. Review the changed plan fields and confirm their evidence and authority; do not rehash an unexplained change.
2. Recalculate the digest from canonical JSON excluding only `contract_sha256`:

   ```bash
   python3 -c 'import json,sys; sys.path.insert(0,sys.argv[1]); from scripts.clonepack.full_stack_qa import full_stack_qa_contract_sha256; value=json.load(open(sys.argv[2],encoding="utf-8")); print(full_stack_qa_contract_sha256(value))' "<skill-root>" "<pack>/full_stack_qa_plan.json"
   ```

3. Write that lowercase digest to `contract_sha256`, make the plan `ART-###` locator path `full_stack_qa_plan.json` and anchor that digest, then rehash only the existing ART:

   ```bash
   python3 "<skill-root>/scripts/clone_pack.py" rehash "<pack>" --record ART-001
   ```

4. Rerun the same readiness profile. Any earlier run bound to the old oracle is stale; preserve it and record a new run after the contract passes.

### `QA_ARTIFACT_HASH_MISMATCH`

Meaning: a pinned lockfile, Playwright configuration, CI workflow, or journey test file no longer has the SHA-256 stored in the plan.

Inspect the repository diff and authority for that exact file. If the change is intended, update the plan's repository hash, recalculate `contract_sha256`, rehash its ART, and rerun readiness before recording another run. If the change is unintended, stop and restore it through the repository's authorized workflow. Do not update the digest merely to accept drift.

### `QA_GATE_CONTRACT_MISMATCH`, `QA_TRACE_INVALID`, or `QA_ARTIFACT_UNDECLARED`

Meaning: the plan, index graph, or indexed GATE disagree.

Reconcile all of these facts together:

- plan CI `gate_argv`, `gate_cwd`, `expected_exit`, `blocked_exit_codes`, `artifact_paths`, and `fresh_artifact_paths` exactly equal the indexed GATE attributes, with `blocked_exit_codes` exactly `[7]`;
- `ci.result_path` occurs in both `artifact_paths` and `fresh_artifact_paths`;
- every journey declares the plan-contract `ART` plus an independent `E`, `ART`, or `CAP` oracle, and the TEST includes them;
- the union of journey oracles exactly equals GATE oracle links/attributes;
- each journey TEST and GATE link reciprocally;
- GATE `covered_ids` exactly equals the union of journey `REQ`, `AC`, and `TEST` IDs;
- every required UI, wire, service, persistence, supporting-service, external-dependency, and applicable optional-dimension artifact appears in GATE `artifact_paths`; and
- journey environment/GATE IDs equal the plan environment and CI gate.

Rerun `build-ready` or `enhancement-ready`. Do not record a behavioral run while this graph is invalid.

### `RUN_ARTIFACT_STALE`

Meaning: a non-blocked gate returned with a required `fresh_artifact_paths` file that existed before invocation and was not created or rewritten by that invocation. The runtime compares the pre-run and post-run file identity, metadata, and SHA-256; an unchanged canonical result cannot certify the current execution.

Preserve the diagnostic and inspect the repository GATE wrapper. Make the current invocation write `ci.result_path` only after it has built the current `clone-full-stack-qa-result/v1`. Do not touch, copy, or redate an old result to bypass freshness. Run the indexed GATE again through `record-run`. Exit `7` remains the declared capability/readiness block and does not require a result artifact.

### `RUN_CONTRACT_STALE`

Meaning: retained automatic RUN evidence no longer equals the selected indexed GATE. For an automatic RUN created by tool `2.2.0`, compare its `execution_contract` with the current GATE's argv, cwd, declared environment, timeout, expected exit, blocked exits, artifact paths, fresh-artifact paths, covered IDs, oracle IDs, normalizations, and redactions. Any difference is stale evidence, including a change that leaves the command argv unchanged. The runtime validates the complete object against the retained-run schema before process execution; `RUN_CONTRACT_INVALID` therefore produces no GATE side effect and no RUN evidence.

Preserve the prior RUN. Reconcile the GATE change with its requirements, tests, oracles, and authority; then execute `record-run` again to allocate new evidence. Do not edit the finalized RUN or copy the current GATE fields into it. A legacy automatic RUN created by an earlier tool version may omit `execution_contract`; it does not attest these added fields and must be replaced before claiming the tool-2.2 contract.

### `QA_AUTHORITY_MISSING`, `QA_EXTERNAL_DEPENDENCY_UNDEFINED`, or application-owned stub failure

Every external sandbox, stub, or exclusion needs a defined dependency and authority decision. Each non-`EXCLUDED` dependency also needs exact `interface.protocol`, `interface.endpoint`, and `interface.classification`, where classification is `LOOPBACK` or `AUTHORIZED_SANDBOX`, plus readiness, assertion, artifact path, a journey `external_dependency_ids` reference, and a matching canonical-result entry. An `EXCLUDED` dependency sets interface, readiness, assertion, and artifact path to `null`, remains authority-bound, and yields a `NOT_APPLICABLE` result. Application-owned frontend, mid-tier, backend, persistence, database, queue, cache, and worker services remain `REAL` in the required lane. Record the external decision or run the real owned service; do not relabel an owned component as external to pass validation.

Core roles may share one `service_id` only when their complete declarations are identical. If `QA_SERVICE_CONFLICT` reports a reused core service, make its readiness and implementation declaration identical at every mapped role or assign different IDs for actually distinct services. Declare each queue, cache, or worker once in `owned_stack.supporting_services`, bind it from at least one journey with `supporting_service_ids`, and give it an assertion, artifact path, and exact matching result entry. `QA_EXTERNAL_DEPENDENCY_UNBOUND` or `QA_SUPPORTING_SERVICE_UNBOUND` means a declared surface is absent from every journey; add its ID to each journey that exercises or excludes that boundary instead of leaving it global and untested.

### `QA_EXTERNAL_INTERFACE_INVALID`, `QA_ORIGIN_UNAUTHORIZED`, or `QA_ORIGIN_CLASSIFICATION_INVALID`

For `QA_EXTERNAL_INTERFACE_INVALID`, make protocol and endpoint syntactically agree, remove credentials and secret-like query names or values, and keep HTTP(S) endpoints as explicit URLs. The validator rejects malformed percent escapes and percent-decodes the query as UTF-8 before checking it; percent-encoding a credential key such as `token` does not authorize it. For a `LOOPBACK` interface, use a host that resolves to loopback. A non-loopback endpoint classified `LOOPBACK` is rejected.

For `QA_ORIGIN_UNAUTHORIZED`, add the exact HTTP(S) origin to `environment.allowed_origins` only after recording its authority decision; do not authorize a production origin for this lane. For `QA_ORIGIN_CLASSIFICATION_INVALID`, classify a loopback origin as `LOOPBACK`, or classify a specifically approved isolated test origin as `AUTHORIZED_SANDBOX` and include a nonempty `decision_ids` list. The canonical result echoes the exact protocol, endpoint, and classification.

### `QA_IDENTITY_BINDING_INVALID` or `QA_IDENTITY_BINDING_INCOMPLETE`

Each journey declares at least one unique `BIND-###`. Its source names an existing primary or additional `exchange_trigger`, an exact response `response_json_pointer`, and value type. Each consumer has a unique kind/pointer pair whose JSON Pointer resolves inside the current plan to a string containing the exact `{binding_name}` placeholder. Include at least `WIRE_PATH`, `SERVICE`, and `PERSISTENCE`; the wire pointer resolves to a concrete additional-exchange path such as `/records/{captured_record_id}`. A `SUPPORTING_SERVICE` or `EXTERNAL_DEPENDENCY` consumer points only to a global entry whose ID is referenced by the same journey; adding the ID to an unrelated journey does not satisfy the binding.

The canonical result repeats the exact source and ordered consumers. Set the binding and every consumer status to `PASS`, compute `captured_value_sha256` from the canonical UTF-8 captured value, and put the same digest in each `observed_value_sha256`. Do not include the raw identity in the result. `QA_IDENTITY_BINDING_INVALID` identifies a missing trigger, unresolved pointer, absent placeholder, duplicate identity, or changed source/consumer contract. `QA_IDENTITY_BINDING_INCOMPLETE` identifies missing required `WIRE_PATH`, `SERVICE`, or `PERSISTENCE` coverage.

### `QA_INSTALLER_SHIM_FORBIDDEN`

The Playwright driver starts repository-owned or preinstalled tooling. Set `playwright.package` to exactly `@playwright/test`, `playwright`, or `playwright-core`; remove downloader/installer shims from `driver_argv` and point it to the target repository's pinned executable. The clone-pack runtime never installs Playwright, browser binaries, Node packages, services, or operating-system dependencies. It hashes but does not parse the lockfile and does not prove that the declared package/version is installed. The repository wrapper performs that preflight. A target CI restore command is legal only when it is explicitly recorded in `ci.restore_argv`, sourced from the pinned lockfile, and backed by `restore_authority_decision_ids`.

### `QA_RUN_MISSING` or `QA_RUN_NOT_PASS`

Meaning: a verified profile has no linked run for the declared gate/environment, or the latest linked run is not `PASS`. A later failure or block controls; an earlier pass cannot mask it.

First rerun `build-ready` or `enhancement-ready`. Plan validation checks the structure and allowed origin of readiness declarations; it does not execute HTTP or command readiness probes. The repository-owned GATE wrapper must preflight the declared executable, Playwright package and selected project, browser, application services, supporting services, non-excluded external dependencies, test files, and authorized test environment before behavioral work. If any capability or readiness check fails, the wrapper exits `7`. Otherwise it proceeds with the behavioral gate. Execute that indexed wrapper through:

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
```

Rerun `verified-mvp` or `verified-enhancement` after a new `PASS`. Do not delete or rewrite an earlier finalized `RUN`.

The full-stack plan and indexed GATE both declare `blocked_exit_codes: [7]`. When the wrapper exits `7`, `record-run` retains stdout, stderr, and a `RUN_DECLARED_BLOCK` diagnostic as `BLOCKED` and returns exit `7`; the same outcome applies when the top-level executable is missing, process start fails, or timeout expires. The wrapper must reserve exit `7` for capability or infrastructure preflight. After behavioral work begins, Playwright, product, contract, or assertion mismatches use an ordinary nonzero exit; `record-run` retains them as `FAIL` and returns exit `5`. Fix the repository capability or behavior, preserve that result, and record a new run.

The full-stack run does not deploy, publish, merge, or mutate production. A screenshot, trace, capture `PASS`, or process exit without separate UI, request/response, API or data postcondition, and persistence evidence does not resolve `QA_RUN_MISSING`.

### `QA_RESULT_MISSING`, `QA_RESULT_INVALID`, `QA_RESULT_CONTRACT_MISMATCH`, or `QA_RESULT_NOT_PASS`

Meaning: the controlling `PASS` RUN does not retain exactly one artifact whose `source_path` equals `ci.result_path`; the artifact is not valid `clone-full-stack-qa-result/v1`; its plan digest, GATE, environment, Playwright project, journey set, external-dependency set, supporting-service set, or echoed contracts differ; or an applicable outcome is not `PASS`.

Response:

1. Preserve the finalized RUN and its artifacts.
2. Compare the plan's `ci.result_path` with the indexed GATE `artifact_paths`.
3. Start the gate's output shape from `assets/templates-v2/full_stack_qa_result.json` and validate it against `assets/schemas/full-stack-qa-result-v1.schema.json`.
4. Emit the current `contract_sha256`, exact GATE/environment/journey IDs, exact `playwright_project`, exact assertion/probe/postcondition strings, the primary observed wire exchange plus every ordered `additional_exchanges` item, each exact `identity_bindings` source and consumer with one matching captured/observed SHA-256, and separate journey, supporting-service, and external-dependency outcomes. A non-`EXCLUDED` external dependency must echo its exact protocol, endpoint, and classification and be `PASS`; every supporting service must be `PASS`; an `EXCLUDED` dependency must echo a null interface and be `NOT_APPLICABLE`.
5. Keep the canonical result sanitized before emission; a redaction that changes a contract-bearing field makes it mismatch.
6. Correct the gate or product behavior, record a new RUN, and rerun the same verified profile.

Do not edit the retained artifact or RUN metadata. `implementation: REAL` remains a governed declaration: the validator cannot inspect service internals for a hidden mock. The pinned workflow hash likewise does not prove hosted CI invocation because the runtime does not parse CI YAML or query branch protection.

## Capture preflight creates no output

Schema, authorization, secret, executable, path, base64, or destination failures occur before evidence acquisition and create no final capture result.

Correct the named input. For secret-like environment keys, store only `env:VARIABLE_NAME`; set the variable outside the pack before running. Credential-bearing reference HTTP reads require a resolved authorization decision. Mutating reference HTTP/process/lifecycle operations additionally require `safe_test_environment: true`.

The runner does not inherit arbitrary parent environment variables.

## Capture returns `PASS` but the product returned an error

This is valid when the error was successfully observed.

- HTTP product outcome: `summary.status` and retained body/headers.
- Process/CLI/custom product outcome: `summary.exit_code`, stdout, and stderr.
- Web outcome: driver `summary.exit_code`, `summary.web`, and declared artifacts.
- Filesystem/manual outcome: retained snapshot/artifact.

Acceptance and parity determine whether the observed product error is expected. Capture status determines only acquisition integrity.

## Capture resume refuses staging

Resume requires all of these:

- real, non-symlink pack/evidence/captures directories;
- exact canonical plan and index paths;
- a runner-owned staging marker for the same pack/case/path;
- no symlink, non-regular, multiply linked, or undeclared staged item;
- a current exact final result pointer when one exists; and
- successful preflight of the full selected set.

If staging is unowned, has an invalid marker, or contains unsafe entries, stop and inspect it. Do not manually relabel it as runner-owned.

## Capture resume skips `FAIL` or `BLOCKED`

Resume verifies and skips any current finalized result, including `FAIL` and `BLOCKED`; it preserves the nonzero outcome. It does not retry a finalized case. Assign a new `CAP-###` ID for replacement acquisition.

## `REDACTION_UNSUPPORTED`

Meaning: a declared regex redaction applies to retained binary content.

Pre-redact the authorized source through a recorded transformation or exclude that binary artifact with authority. Raw binary content under an active redaction rule is not promoted.

## Parity exits `5`

Meaning: the selected comparator found a retained mismatch or a required proof remains held.

Response:

1. Preserve `evidence/parity/<PAR-ID>`.
2. Inspect mismatch details and both immutable capture artifacts.
3. Confirm the comparator and normalization were pinned before implementation.
4. Create/update a `PARITY_GAP`, `MVP_BLOCKER`, or `EVIDENCE_GAP` according to scope and evidence.
5. Implement only through an authorized build/gap plan.
6. Use new capture/parity IDs for the next attempt.

Never broaden a tolerance or normalization merely to erase the mismatch.

## `record-run` retained sensitive stdout/stderr

Governed redaction is applied to textual stdout, stderr, and declared artifacts before promotion when the indexed gate declares redaction rules. If retained output still contains sensitive data because no applicable rule was declared, stop distribution, follow the repository incident/data policy, rotate any exposed credential outside this skill, and record the finding. Do not rewrite the immutable run in place. Correct the gate contract, advance governed state, and rerun recording; the runtime allocates a new `RUN-###` ID. A binary artifact that requires textual redaction is rejected with `REDACTION_UNSUPPORTED` rather than retained.

## `record-manual` does not run the procedure

This is intentional. Perform the versioned procedure under its recorded preconditions first. Retain the observation artifacts beneath the pack. Then call `record-manual` with the same procedure file, observer, authority, and every artifact path. The procedure hash MUST match the selected `TEST` record.

## `assure` returns `CASE_SELECTION_EMPTY`

Omitting both `--case` and `--all` selects required cases only. If none are required, the command exits `1` with `CASE_SELECTION_EMPTY` and executes nothing. Repeating `--case` selects exactly those cases; `--all` selects required and optional cases. Every nonempty execution emits one canonical JSON result on stdout. Aggregate precedence is order-independent: any infrastructure block exits `7`, otherwise any verification mismatch exits `5`, otherwise all selected cases passed and the command exits `0`. Inspect the aggregate and each immutable `evidence/assurance/<ASSURE-ID>/result.json`.

## `ASSURANCE_INCOMPLETE`

Meaning: the selected risk profile lacks one or more required assurance kinds.

Required sets are:

- `local-evaluation`: threat model and provenance;
- `internal`: local-evaluation plus SAST, secret, dependency, license, and SBOM;
- `customer`, `public`, or `production`: internal plus DAST, SLSA, independent review, and rollback/recovery.

Add exact installed-tool or versioned-procedure cases and same-ID `ASSURE` records. Do not add a placeholder or an empty optional case.

## Scaffold collision

Preview and apply both refuse a pre-existing required destination. Inspect `scaffold_plan.json`, `assets/scaffolds/catalog.json`, and the repository tree. Use the exact brownfield `not-applicable` sentinel for an adopted implementation. There is no custom or overwrite mode.

## Gap dossier failure

Common causes:

- marker or vague modal remains;
- existing path does not exist;
- new path is not declared new;
- symbol anchor occurs zero or multiple times;
- change lies outside the allowed fence;
- change/step sequence is duplicated or non-contiguous;
- dependency is not earlier or verified;
- required test dimension lacks a case or exact non-applicable decision;
- command or expected result is vague;
- closure fields falsely claim unexecuted work; or
- GAP backlinks omit dossier records.

Reinspect repository truth, update the human and machine dossiers identically, and rerun `gap-plan`.

## Illegal gap transition

Use only `gap-transition`. Inspect current status, latest event, dependencies, readiness, decisions, current runs, parity, and assurance. Satisfy the exact edge prerequisite. Do not append history manually or edit `NO-OPEN-GAPS`.

If a transition is interrupted or errors during file replacement, stop and compare `clone_index.json`, `history/gap_events.jsonl`, and `gaps_analysis.md`. The staged multi-file write is not transactional and has no rollback after a destination is replaced. Reconcile status, event sequence/hash, and `NO-OPEN-GAPS` before another transition.

## Migration exits `6`

Run `migrate <source> --check` and inspect:

- `ambiguous_candidates`;
- `ambiguous_ids`, `resolved_by_mapping`, and `unresolved_ids`;
- `mapping_format` and `migratable`; and
- source file/hash validity.

`--check` does not inspect `--output`. Create a complete occurrence mapping only for reported candidate keys and rerun check. Separately inspect that the output parent exists, the output is absent, and the output is outside the source tree before the write invocation.

## Seal failure or `SEAL_TAMPERED`

A seal is derived state. Do not edit its hashes.

- Before first seal: resolve every non-seal validation diagnostic, then call `seal`.
- After a governed change: the predecessor must have been validated before its governed files were edited. Retain `seal.json`; record its schema, pack ID, revision, manifest SHA-256, and seal SHA-256 in `supersedes`; advance and bind the pack revision; regenerate stale evidence; then create a successor seal. A missing retained predecessor stops with `SEAL_PREDECESSOR_MISSING`; changed predecessor seal bytes stop with `SEAL_SUPERSEDES_MISMATCH`.
- On unexpected hash mismatch: treat the affected pack as untrusted until the changed bytes and authority are reconciled.

## `diff` exits `0` with changed IDs

This is intentional. `diff` is a report, not a gate. Parse `added_ids`, `removed_ids`, and `changed_ids`. It compares index record objects only; use separate governed comparisons for documents, plans, evidence, history, runs, and seals.

## Exit `70`

Preserve stderr, exact invocation, Python version, pack path, and current file hashes. Stop rather than converting the exception into `PASS`, `FAIL`, or `HOLD`. Reproduce with the smallest non-sensitive fixture before changing implementation.
