# Runtime enforcement boundaries

This document records behavior of tool version `2.0.0` that is narrower than the semantic workflow required by `SKILL.md` and `references/`. These are current implementation facts, not a roadmap.

A machine profile `PASS` proves only checks implemented by `scripts/clonepack/`. A complete skill handoff MUST also apply the semantic contracts named below. Do not represent the stricter semantic contract as runtime enforcement.

## Baseline validation is not semantic baseline proof

At `baseline-ready`, the runtime:

- requires `clone_pack.json.reference_baseline_id` to be nonempty and not `UNRESOLVED`;
- requires at least one index record whose kind is `ENV`;
- validates `clone_brief.md` and `evidence_ledger.md` for governed markers/language;
- validates the capture plan schema; and
- validates same-ID `CAP` counterparts only for capture cases that exist in the plan.

The runtime does not resolve `reference_baseline_id` to a `BASE` record, validate semantic fields inside an `ENV` record, or require a nonempty capture case list.

Before claiming a frozen baseline, the skill/operator MUST independently confirm the immutable reference locator/digest, full environment preconditions, authority, and required capture inventory defined by [Evidence and fidelity](../references/evidence-and-fidelity.md). Report both the machine profile result and this semantic audit result.

## Specification validation is conditional on records present

At `spec-ready`, the runtime requires marker-free governed documents and a nonempty index. It applies requirement, acceptance, test, capability, trace, and parity-counterpart rules to relevant record kinds that are present.

The runtime does not require at least one record of every semantic kind, does not require a nonempty capture or parity case list, and can therefore pass a marker-free but substantively incomplete graph that avoids those record kinds.

Before claiming a complete specification, the skill/operator MUST inventory all applicable actors, surfaces, workflows, states, inputs, outputs, errors, permissions, side effects, persistence, timing/order, recovery, and fidelity dimensions; then confirm every in-scope capability has evidence/decision-backed requirements, acceptance, tests, independent oracles, and disposition. A bare machine `spec-ready` pass is insufficient.

## Gap profiles do not fully prove lifecycle closure

The `gap-plan` profile executes machine dossier validation. The `gap-closure` profile does not re-run dossier validation and does not require every selected gap to be terminal or to contain closure evidence. A selected ready gap can remain `OPEN` while other profile requirements pass.

The `closed` profile checks that every retained gap status is `VERIFIED` or `DECLINED`. If a gap has no history events, validation does not require one; a manually changed terminal status can therefore evade transition prerequisites.

For a closure claim:

1. require every selected gap to be `VERIFIED` or authority-backed `DECLINED` as applicable;
2. require a nonempty, valid, hash-chained event history ending in the current status;
3. require current run/parity/assurance and closure evidence for `VERIFIED`;
4. require the exact authority decision for `DECLINED`;
5. confirm dependencies and selected order; and
6. treat `gap-closure`/`closed` machine results as necessary but not sufficient.

## Gap transition writes are staged but not transactional

`gap-transition` stages the updated index, history, and `gaps_analysis.md` before replacing destinations. Replacement occurs sequentially. If interruption or an operating-system failure occurs after the first replacement, there is no rollback of already replaced files.

After any interrupted or failed transition:

1. stop further lifecycle work;
2. validate `clone_index.json`, `history/gap_events.jsonl`, and `gaps_analysis.md` together;
3. compare current gap status, latest event, event hash chain, sequence, and `NO-OPEN-GAPS`;
4. restore consistency from retained pre-transition bytes or an authority-approved successor revision; and
5. do not append another transition until the three surfaces agree.

Do not describe the current multi-file update as atomic or transactional.

## Successor seal lineage is partly operator-enforced

When `seal.json` already exists, `seal` requires a greater pack revision and archives the prior seal before writing the new one. It does not require `clone_pack.json.supersedes` to identify the prior seal and does not validate the prior seal's governed hashes before archiving it.

For trustworthy lineage, the skill/operator MUST:

1. validate the prior pack and seal before governed successor edits;
2. retain the prior manifest/seal identity and digest;
3. set `supersedes` to that exact prior identity/digest;
4. bind the higher revision across manifest, index, plans, and documents; and
5. verify the archived seal matches the recorded predecessor.

The CLI's higher-revision check and archive operation do not by themselves prove successor lineage.

## Assurance selection and aggregate exit require per-case inspection

`assure <pack>` with no `--case` selects every plan case, including cases whose `required` field is false. Repeat `--case` to select an exact subset.

The aggregate exit is updated in plan order. A blocked case sets exit `7`, while a later expected-exit mismatch can replace the aggregate with exit `5`; a later blocked case can replace `5` with `7`. The same set in another order can therefore produce a different aggregate exit.

Always inspect every selected case's retained `status` and diagnostic in `assurance_plan.json` and `evidence/assurance/<ASSURE-ID>/result.json`. Do not infer the complete result set from the final process exit alone.

## Automated gate recording has no declared-artifact retention

`record-run` reads gate argv, cwd, environment, expected exit, timeout, covered IDs, oracle IDs, normalizations, and redaction metadata. It retains stdout and stderr only. It does not consume a gate `artifact_paths` field or copy other declared gate artifacts.

If the child process returns, `record-run` writes the run and stdout/stderr even when the observed exit mismatches. Missing executable, start failure, or timeout raises exit `7` before a run record or output artifact directory is created.

Do not promise non-stdout/stderr gate artifact retention. When another artifact is necessary, retain it through an authorized capture, manual attestation, or assurance case whose implemented contract copies artifact paths.

## Migration check does not inspect the destination

`migrate <v1-pack> --check` inventories the source and validates occurrence mapping. It ignores `--output` when `--check` is present, accepts no destination internally, and emits no `required_occurrences` field.

Its output fields include `ambiguous_candidates`, `ambiguous_ids`, `resolved_by_mapping`, `unresolved_ids`, `mapping_format`, and `migratable`.

Destination existence, containment, source/destination relationship, and parent constraints are checked only by the write invocation. Validate them with read-only filesystem inspection before invoking migration, then preserve the write command's exact diagnostic if it refuses the destination.

## Locator hashing normalizes line endings

The runtime reads the locator file as UTF-8 text using Python universal-newline translation, then calls `splitlines(keepends=True)`. Source CRLF and CR line endings become `\n` before hashing. A terminated matched line is hashed with that normalized `\n`; an unterminated final line has no ending byte.

Do not hash raw CRLF bytes and expect the runtime locator digest to match.

## Direct pack authoring has no generic mutation command

The CLI has no generic `add-record`, `add-gap`, `add-capture-case`, `add-parity-case`, or `rehash-index` command. `init` creates templates; the skill or an informed pack author edits Markdown/JSON and computes the required locators/case hashes before validation.

For a cold recovery, invoke `$clone-software` with the exact pack path, mode, failing command/profile, full JSON diagnostics, authorized evidence/repository inputs, and a prohibition on deleting finalized evidence. The recovery prompt in [Troubleshooting](troubleshooting.md#skill-driven-pack-recovery) is the supported human entry point.

