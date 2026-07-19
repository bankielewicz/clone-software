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

Gate output is not automatically redacted. Stop distribution, treat the artifact according to the repository incident/data policy, rotate any exposed credential outside this skill, and record the finding. Do not rewrite the immutable run in place. Correct the gate to emit safe output, advance governed state, and rerun recording; the runtime allocates a new `RUN-###` ID.

## `record-manual` does not run the procedure

This is intentional. Perform the versioned procedure under its recorded preconditions first. Retain the observation artifacts beneath the pack. Then call `record-manual` with the same procedure file, observer, authority, and every artifact path. The procedure hash MUST match the selected `TEST` record.

## `assure` prints nothing

This is intentional. Read the updated `assurance_plan.json` and every `evidence/assurance/<ASSURE-ID>/result.json`. Omitting `--case` selects optional and required cases. Mixed `FAIL` and `BLOCKED` results make the aggregate exit order-dependent, so the per-case statuses are authoritative. Confirm the selected set is nonempty before interpreting exit `0` as executed assurance.

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
- After a governed change: validate the predecessor first; record its exact identity/digest in `supersedes`; advance and bind the pack revision; regenerate stale evidence; then create a successor seal. Tool `2.0.0` archives the prior seal but does not validate predecessor hashes or require `supersedes`.
- On unexpected hash mismatch: treat the affected pack as untrusted until the changed bytes and authority are reconciled.

## `diff` exits `0` with changed IDs

This is intentional. `diff` is a report, not a gate. Parse `added_ids`, `removed_ids`, and `changed_ids`. It compares index record objects only; use separate governed comparisons for documents, plans, evidence, history, runs, and seals.

## Exit `70`

Preserve stderr, exact invocation, Python version, pack path, and current file hashes. Stop rather than converting the exception into `PASS`, `FAIL`, or `HOLD`. Reproduce with the smallest non-sensitive fixture before changing implementation.
