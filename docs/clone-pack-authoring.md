# Clone-pack authoring

This guide explains the `clone-pack/v2` file set, authority order, record graph, hashes, readiness profiles, evidence immutability, and gap dossiers. It does not replace the executable schemas or validator.

Tool `2.2.0` profiles are scoped proofs. Read [Runtime enforcement boundaries](runtime-enforcement-boundaries.md) before interpreting a pass beyond its governed records and retained evidence.

## Authority order

If the governed repository defines no different order, use:

1. explicit decisions in `clone_brief.md`;
2. frozen evidence in `evidence_ledger.md`;
3. normative behavior in `clone_specification.md`;
4. acceptance contracts in `acceptance_matrix.md`;
5. ordered changes in `mvp_build_plan.md` or `gap_implementation_plan.md`; and
6. status and deferred scope in `gaps_analysis.md`.

Resolve a contradiction before implementation. A lower item never silently overrides a higher item.

Markdown is normative for human-readable behavior. JSON is normative for pack identity, graph relationships, executable plan cases, lifecycle state, result pointers, and integrity values. Keep both representations semantically identical.

## Canonical pack paths

The manifest and executable operations require these exact paths:

| Path | Authority |
| --- | --- |
| `clone_pack.json` | Pack identity, baseline, repository state, document/plan locations, revision, state, lineage, and seal location |
| `clone_index.json` | Canonical records, attributes, locators, states, and graph links |
| `capture_plan.json` | Reference/clone acquisition cases and immutable result pointers |
| `parity_plan.json` | Reference-versus-clone comparator cases and result pointers |
| `scaffold_plan.json` | Exact audited scaffold or brownfield sentinel |
| `assurance_plan.json` | Risk profile, required checks, argv contracts, and result pointers |
| `full_stack_qa_plan.json` | Optional browser-to-persistence environment, declared-real owned-service topology, Playwright/CI contract, journeys, and canonical result path |
| `repository_inventory.json` | Optional brownfield repository kind, adopted state, protected dirty paths, and snapshot records |
| `enhancement_plan.json` | Optional brownfield request, affected surfaces, compatibility, preservation, scope, and lifecycle contract |
| `history/gap_events.jsonl` | Append-only, hash-chained gap transitions |
| `history/enhancement_events.jsonl` | Append-only, hash-chained enhancement transitions |
| `runs/` | Immutable automated and manual run records |
| `evidence/` | Immutable capture, parity, assurance, and retained source artifacts |
| `seal.json` | Derived unsigned integrity manifest for one passing sealable profile |

Executable commands reject remapped or symlinked canonical manifest, index, and plan files.

## Markdown documents

| Document | Required content |
| --- | --- |
| `clone_brief.md` | Authority, sources, prohibited actions, baseline, fidelity, MVP, unknowns, decisions, and stop rules |
| `evidence_ledger.md` | Baselines, environments, atomic evidence observations, conflicts, transformations, and artifact hashes |
| `clone_specification.md` | Actors, workflows, interfaces, state, data, security, time, errors, compatibility, deployment, and exact MVP contract |
| `acceptance_matrix.md` | Requirement-to-criterion-to-test-to-gate/run mappings and current factual result state |
| `mvp_build_plan.md` | Dependency-safe slices, path fences, stack/scaffold, ordered changes, gates, rollout, rollback, and HALTs |
| `architecture_decisions.md` | Resolved architecture, stack, interface, data, security, and operations decisions |
| `security_assurance.md` | Threats, controls, findings, exceptions, assurance checks, and exact result evidence |
| `provenance_ledger.md` | Origins, versions, digests, rights/licenses, components, SBOM, build provenance, and blockers |
| `gaps_analysis.md` | Capability dispositions, exact deltas, gap class/status/readiness, dependency order, and human dossiers |
| `gap_implementation_plan.md` | Cold implementation handoff for selected gaps, exact path/symbol changes, tests, gates, and stop conditions |

Each document starts with YAML frontmatter containing its exact `schema_version`, `pack_id`, `pack_revision`, and `document_state`. These values MUST equal the manifest entry and current pack revision.

## Language contract

Use factual present tense for observed/current behavior. Use imperative language or uppercase BCP 14 keywords for normative behavior.

Ready documents reject:

- `TBD`, `TODO`, `TBC`, `FIXME`, `TK`, or `???`;
- unresolved `[[REQUIRED: ...]]` or `[[MIGRATION_REQUIRED: ...]]` markers;
- lowercase “should,” “could,” “may,” “might,” “maybe,” “ideally,” or “eventually”;
- “as needed”;
- “support X” without the exact X operations and observable result;
- “handle errors” without conditions, output/status, effects, and recovery;
- “match the original” without baseline, metric, and tolerance; and
- invented paths, symbols, commands, or behavior.

Use `UNKNOWN_BLOCKER`, affected IDs, evidence checked, and one resolution question when exact truth is unavailable.

## Manifest identity

`clone_pack.json` has an exact schema. Use only schema-defined fields. Tool `2.2.0` permits optional `workstream`, `repository_inventory`, `enhancement`, and `full_stack_qa` plan paths; legacy v2 manifests remain valid without them.

Identity rules:

- Preserve `pack_id` only for the same governed evidence lineage.
- Increment `pack_revision` for a successor in that lineage.
- Use a new `pack_id` for a different reference baseline or independently governed clone.
- Bind `pack_id` and `pack_revision` across manifest, index, every plan, and every Markdown frontmatter block.
- Set `reference_baseline_id` to a defined immutable baseline record before `baseline-ready`.
- Record repository state as `git` with an exact revision, or `working-tree` with an exact revision plus lowercase SHA-256 of the complete diff/full-tree inventory.
- Leave document `sha256` values `null` while drafting unless intentionally binding current bytes. `seal` computes and writes final governed document hashes.
- Never edit an existing seal to match changed files. Advance the revision and create a valid successor.

`init --source-description` does not validate its text. Bind a local reference artifact with a separately executed digest command and retained `BASE`/`E` evidence.

## Index record contract

Every `clone_index.json.records` item contains exactly:

```json
{
  "id": "REQ-001",
  "kind": "REQ",
  "locator": {
    "path": "clone_specification.md",
    "anchor": "REQ-001",
    "sha256": "<sha256-of-the-one-matched-line>"
  },
  "links": {},
  "applicability": "MVP",
  "state": "PLANNED",
  "attributes": {}
}
```

The example digest marker MUST be replaced with the actual lowercase digest. Do not copy that object as a ready record.

Record IDs are stable, never reused, and have at least three decimal digits after their kind prefix. Controlled kinds are:

```text
BASE BLOCK ENV ART E CONFLICT DEC ADR ACT WF SURF REQ IF DATA SEC NFR
EXC AC TEST GATE RUN GAP INV CHANGE STEP CAP PAR ASSURE PROV ASSET
THREAT CTRL FIND GAPDEC COMP SBOM BUILD PROVBLOCK STACK SCF DEP SLICE
HALT MIG ENH PRES SNAP SCOPE
```

Gap-scoped requirements, acceptance criteria, tests, changes, and steps use the exact scoped patterns defined by `scripts/clonepack/constants.py`, such as `REQ-GAP-001-01` and `TEST-GAP-001-01`.

### Locator rules

- `path` is a safe POSIX relative path beneath the pack.
- `anchor` is a substring that occurs on exactly one UTF-8 line in that path.
- `sha256` is the SHA-256 of that entire matched line after Python UTF-8 text reading and universal-newline normalization.
- A non-scaffold profile requires a non-null current locator hash.
- When an anchored line changes, recompute the locator hash before validation.

The runtime algorithm is:

```text
text = UTF-8 text read with universal-newline translation (CRLF and CR become LF)
matches = text.splitlines(keepends=True) lines where anchor is a substring
require len(matches) == 1
sha256 = lowercase SHA-256 of matches[0] encoded as UTF-8
```

A terminated matched line therefore hashes with normalized `\n`; an unterminated final line has no line-ending byte.

### Link rules

Every target ID exists and has a kind permitted by the relation. Core reciprocal edges are:

```text
REQ.evidence <-> E.requirements
REQ.decisions <-> DEC/ADR/GAPDEC.requirements
REQ.acceptance <-> AC.requirements
REQ.tests <-> TEST.requirements
TEST.gates <-> GATE.tests
RUN.requirements <-> REQ.runs
RUN.acceptance <-> AC.runs
RUN.tests <-> TEST.runs
RUN.oracles <-> E/ART/CAP.runs
RUN.gates <-> GATE.runs
```

The validator rejects a missing backlink even when the forward link exists.

Every `TEST` links to an independent oracle. Clone-produced expected values are not independent.

## Plan case hashes

Every indexed `CAP`, `PAR`, `ASSURE`, and `PRES` counterpart has `attributes.case_sha256` equal to the current plan case contract hash.

The hash algorithm is exact:

1. Copy every case key/value except the mutable top-level `result` member.
2. Serialize as JSON with two-space indentation, keys sorted at every object level, Unicode preserved, and one trailing newline.
3. Encode as UTF-8.
4. Compute lowercase SHA-256.

Any edit to an adapter, input, lifecycle, environment, authority, redaction, comparator, normalization, option, tolerance, or assurance command changes the case hash. Update the index counterpart before execution. A previously retained result becomes stale and cannot certify the edited case.

## Optional full-stack QA plan

Add `full_stack_qa_plan.json` only when one selected journey crosses all four required layers: browser UI, real request and response, an application-owned API or data postcondition, and persistence observed after reload, relogin, or restart. A static page, UI-only flow, screenshot comparison, or owned-service mock uses the ordinary capture/parity contracts instead.

Author and bind the plan in this order:

1. Copy `assets/templates-v2/full_stack_qa_plan.json` to the pack root and replace every marker from inspected repository facts.
2. Add `"full_stack_qa": "full_stack_qa_plan.json"` to `clone_pack.json.plans` without removing the four required base plan paths or any brownfield plan paths.
3. Keep every application-owned frontend, mid-tier, backend, and persistence role `REAL`. Two or more core roles may use the same `service_id` only when their complete service declarations are identical; conflicting declarations for a reused ID fail validation. Declare every application-owned queue, cache, or worker in `owned_stack.supporting_services` with `implementation: REAL`, readiness, one exact assertion, and one GATE artifact path, then reference its ID from every exercising journey through `supporting_service_ids`.
4. Classify only external dependencies as `SANDBOXED`, `STUBBED`, or `EXCLUDED`, each with an authority decision and at least one journey `external_dependency_ids` reference. Every non-`EXCLUDED` dependency declares exact `protocol`, `endpoint`, and `classification` in `interface`, where classification is `LOOPBACK` or `AUTHORIZED_SANDBOX`, plus readiness, assertion, and a GATE artifact path. A loopback-classified HTTP(S) endpoint resolves to loopback and an authorized-sandbox HTTP(S) endpoint has a matching authority-backed `allowed_origins` entry. Endpoint validation rejects malformed percent escapes and checks the percent-decoded UTF-8 query for secret-like names or values. An `EXCLUDED` dependency sets those four proof fields to `null`.
5. Pin repository file SHA-256 values, a controlled Playwright package (`@playwright/test`, `playwright`, or `playwright-core`) and declared version, the exact `playwright.project`, browser environment, `workers: 1`, `retries: 0`, the target CI workflow, one repository-owned GATE argv, and `ci.result_path`. `playwright.install_argv` remains `null`. The runtime hashes the declared lockfile but does not parse the lockfile or prove that the declared package/version is installed; the repository GATE wrapper performs that capability check.
6. Set `ci.blocked_exit_codes` to `[7]`, put `ci.result_path` in both `artifact_paths` and `fresh_artifact_paths`, and make the indexed GATE attributes contain those exact arrays. A non-blocked gate invocation must create or rewrite every fresh artifact during that invocation. An unchanged pre-existing file is rejected as `RUN_ARTIFACT_STALE` with exit `4`. Tool-2.2 automatic RUN evidence retains the complete effective GATE as `execution_contract`; the object is schema-validated before process execution, and changing any retained field later makes that RUN stale and requires a new `record-run` invocation.
7. Give each journey one primary wire exchange plus an ordered `additional_exchanges` array. Every trigger is unique within the journey. The canonical result must echo the primary exchange and every additional exchange in that order with exact trigger, method, path, status, and schema assertion values.
8. Add at least one `identity_bindings` entry. A `BIND-###` names the value captured from one declared exchange response by `response_json_pointer`, then uses JSON Pointers to bind that name into at least `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` contracts. Each pointed-to plan string contains the literal `{binding_name}` placeholder; the wire consumer points to a concrete additional-exchange path such as `/records/{captured_record_id}`. An optional supporting-service or external-dependency consumer must target an ID referenced by that same journey. The result repeats the source and consumers, reports `PASS`, and gives `captured_value_sha256` plus the same SHA-256 in every consumer's `observed_value_sha256` without retaining the raw identity.
9. Create one `ART-###` record for the plan. Every journey `oracle_ids` includes it plus at least one independent `E`, `ART`, or `CAP` oracle linked to all journey requirements. Link those IDs from the journey TEST; make their union exactly equal the GATE oracle links/attributes and make the REQ/AC/TEST union exactly equal GATE coverage.
10. Compute `contract_sha256` from canonical JSON excluding only that field, write the digest into the plan, use it as the ART locator anchor, and rehash that explicit record.

Compute and bind the contract with:

```bash
python3 -c 'import json,sys; sys.path.insert(0,sys.argv[1]); from scripts.clonepack.full_stack_qa import full_stack_qa_contract_sha256; value=json.load(open(sys.argv[2],encoding="utf-8")); print(full_stack_qa_contract_sha256(value))' "<skill-root>" "<pack>/full_stack_qa_plan.json"
python3 "<skill-root>/scripts/clone_pack.py" rehash "<pack>" --record ART-001
```

The plan's CI argv, cwd, expected exit, blocked-exit codes, artifact paths, and fresh-artifact paths MUST equal the indexed GATE attributes. Each journey declares separate UI, wire, service, persistence, and identity-binding outcomes and exact supporting-service and external-dependency references. The gate emits `clone-full-stack-qa-result/v1` at `ci.result_path` using `assets/templates-v2/full_stack_qa_result.json`; `record-run` retains that source mapping only when the current invocation produced a fresh file. The result binds the exact Playwright project, primary and ordered additional wire exchanges, every `BIND-###` identity flow, every declared external dependency, and every declared supporting service. The plan requires target CI to invoke the same GATE argv, but the runtime does not parse CI workflow semantics, parse the lockfile, prove package installation, or prove hosted execution. Plan validation checks readiness declarations and allowed origins; it does not execute readiness probes. The skill repository does not install or run Playwright.

After the applicable readiness profile passes, retain the gate result through:

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
```

The runtime never installs Playwright, browsers, Node packages, application services, or operating-system dependencies. The repository-owned GATE wrapper performs capability and service-readiness preflight before behavioral work. When that preflight cannot run the declared lane, it exits `7`; because both the plan and indexed GATE declare `blocked_exit_codes: [7]`, `record-run` retains stdout, stderr, and `RUN_DECLARED_BLOCK` evidence as `BLOCKED` and returns exit `7`. A started gate's product or assertion mismatch uses an ordinary nonzero exit, which `record-run` retains as `FAIL` and returns exit `5`. Do not deploy, publish, merge, or mutate production through this plan. Use [Full-stack QA with Playwright](full-stack-qa.md) and the normative [full-stack QA contract](../references/full-stack-qa.md) for the complete schema, trace, evidence, and failure rules.

## Capability dispositions

Every indexed `SURF` and `WF` record sets exactly one `attributes.disposition`:

| Disposition | Exact link/proof contract |
| --- | --- |
| `EQUIVALENT` | Nonempty `requirements`, no gaps/exclusions, and linked `PASS` parity or run proof |
| `MISSING` | Nonempty `gaps`, no requirements/exclusions, and linked evidence/parity/run |
| `PARTIAL` | Nonempty `gaps`, no requirements/exclusions, and linked evidence/parity/run |
| `DIVERGENT` | Nonempty `gaps`, no requirements/exclusions, and linked evidence/parity/run |
| `EXCLUDED` | Nonempty `exclusions`, no requirements/gaps, and nonempty authority decisions |
| `UNVERIFIED` | Nonempty `gaps`, no requirements/exclusions, and every linked gap is a `BLOCKED` `EVIDENCE_GAP` |

Do not infer a disposition from prose or implementation presence.

## Validation profiles

### `scaffold`

Checks pack identity, required file presence, schemas available at the structural threshold, safe paths, frontmatter identity, index shape, plan identity, and any supplied hashes. It allows generated required markers and null record locator hashes.

This profile is structural only.

### `baseline-ready`

Machine enforcement additionally requires marker-free authorization/baseline documents, a nonempty/non-`UNRESOLVED` reference baseline ID, at least one `ENV` record, a valid capture plan schema, and exact same-ID capture index counterparts for every case that exists. It does not resolve the baseline ID to `BASE`, validate environment attributes, or require a nonempty case list. The skill/operator MUST perform those semantic checks separately before claiming a frozen baseline.

### `spec-ready`

Machine enforcement additionally requires marker-free specification and acceptance documents and a nonempty index. It validates controlled dispositions, evidence/decision-backed requirements, acceptance/tests/oracles, implementation locators, traceability, and parity counterparts only for relevant records/cases that exist. It does not require a substantively complete inventory or nonempty capture/parity cases. The skill/operator MUST audit complete semantic coverage separately.

In `spec-only`, planned implementation remains `NOT_STARTED` and planned test/run state remains `NOT_RUN` while no immutable run exists. Lack of code alone is not an MVP defect.

### `build-ready`

Additionally governs every Markdown document, requires pinned repository state, exact scaffold disposition, architecture/build plan, provenance records, a controlled assurance risk profile, every assurance kind required by that risk profile, same-ID assurance counterparts, and valid clean-room separation fields.

When `plans.full_stack_qa` is present, this profile also validates its schema, contract and repository hashes, authority records, real owned-service topology, trace links, GATE equivalence, and proof-artifact declarations.

Product-code editing begins only after this profile passes.

### `verified-mvp`

Additionally requires:

- at least one `attributes.mvp: true` requirement;
- current passing runs covering every MVP acceptance criterion;
- at least one complete passing `REQ -> AC -> TEST -> GATE -> RUN` chain with oracle and reciprocal links;
- at least one required current reference capture with acquisition `PASS`;
- at least one required current clone capture with acquisition `PASS`;
- a required current parity `PASS` over those captures;
- current assurance results;
- no non-verified `MVP_BLOCKER`; and
- a valid seal.

When `plans.full_stack_qa` is present, the latest linked GATE/environment `RUN` is `PASS`, its retained canonical result matches the current plan/GATE/environment/journey set, and every applicable dimension passes. A missing or latest non-passing run is a verification `HOLD`; a malformed result/plan, broken trace, non-`REAL` application declaration, stale repository file, or GATE mismatch blocks verification.

### `gap-plan`

Governs the gap analysis and implementation plan plus their prerequisite specification documents. It also applies the build-level repository, plan-schema, provenance, and assurance-profile prerequisites used by its validation rank. It validates every nonterminal gap's blocker or machine dossier, selected order, dependency topology, path/symbol fences, test dimensions, commands, acceptance, rollout/rollback, HALTs, and backlinks. It does not require verified-MVP proof or a seal and does not turn a gap plan into MVP proof.

### `gap-closure`

Requires current MVP-quality proof, selected-gap plan topology and dossier checks, terminal selected gaps, current closure evidence, complete hash-chained history, and a valid gap-closure seal.

### `closed`

Requires all retained gaps to be `VERIFIED` or authority-backed `DECLINED`, a matching derived `NO-OPEN-GAPS: true`, complete current history and closure evidence, current proof, and a valid closed seal.

### `repository-adopted`

Requires a `brownfield-enhancement` workstream, repository inventory, governed request binding, adopted `SNAP` record, protected dirty-path disposition when applicable, and reciprocal `ENH`, `SNAP`, affected-surface, and plan links. It does not authorize product-code edits.

### `enhancement-ready`

Adds a complete enhancement plan with controlled change types, affected surfaces, compatibility decisions, exact path/change mappings, immutable preservation baselines, implementation locations, repository-native gates, security/dependency/migration dispositions, and a legal lifecycle ending in `READY`. This is the implementation gate for `enhancement-build` only.

When `plans.full_stack_qa` is present, this profile applies the same full-stack readiness checks as `build-ready`.

### `implementation`

Validates the retained planning and baseline evidence required by `enhancement-ready` and requires lifecycle state `IN_PROGRESS`, `IMPLEMENTED`, or `VERIFIED`. It omits live adopted-snapshot equality so authorized product edits can exist. It does not validate candidate, preservation-regression, scope, assurance, or seal evidence. A pass does not authorize edits; the successful `READY -> IN_PROGRESS` transition and resulting `enhancement-build` mode do.

### `verified-enhancement`

Requires a current candidate `SNAP`, passing `SCOPE`, required `PRES` regression and assurance results, complete hash-chained enhancement history ending in `VERIFIED`, and an enhancement seal binding the request, plan, adopted/candidate state, scope, preservation, assurance, and governed pack bytes.

When `plans.full_stack_qa` is present, the latest linked run and its parsed canonical result additionally satisfy the full-stack contract, and the manifest-bound plan is included in the seal.

## Evidence immutability

- Final capture, parity, assurance, preservation baseline/regression, snapshot, scope, and run evidence is never overwritten.
- A plan result pointer contains retained status, canonical path, and current SHA-256.
- Reference results bind the reference baseline and use null clone revision/diff.
- Clone and parity results bind the current clone revision and diff hash.
- Case or governing contract edits stale existing results.
- Preserve failure and mismatch evidence.
- Assign a new stable ID for replacement acquisition or comparison.
- Never remove a finalized result to manufacture a retry.

Capture staging is not evidence. `--resume` removes only a marked runner-owned incomplete staging directory after exact selected-set preflight.

## Gap classes and lifecycle

Gap classes are:

```text
MVP_BLOCKER PARITY_GAP QUALITY_GAP EVIDENCE_GAP
```

Statuses are:

```text
OPEN BLOCKED IN_PROGRESS IMPLEMENTED VERIFIED DECLINED
```

Only `gap-transition` is an authorized gap status-changing interface. It promotes index, dossier closure, append-only hash-chained history, and derived `NO-OPEN-GAPS` state through a recoverable transaction journal. A later invocation completes an exact interrupted promotion or stops on unexpected byte divergence.

An `EVIDENCE_GAP` is `BLOCKED` and has exactly this blocker field set:

```text
missing_evidence
investigations (nonempty)
resolution_question (one answerable question)
authority
```

It has no ready implementation dossier.

## Actionable gap dossier

Copy `assets/templates-v2/gap_dossier.json` into `GAP-###.attributes.dossier` and replace every marker. The machine dossier and human section in `gaps_analysis.md` MUST agree.

A ready dossier specifies:

1. identity, class, priority, status, dependencies, and source records;
2. current reference and clone evidence;
3. exact target contract and observable delta;
4. impact and deferral authority;
5. verified existing/new paths, unique symbols, and allowed fence;
6. interface, state, data, migration, algorithm, error, security, telemetry, and compatibility rules;
7. ordered changes and steps;
8. fixtures and applicable test-dimension dispositions;
9. exact argv commands and expected results;
10. atomic acceptance criteria;
11. activation, migration, rollback, recovery, and data repair;
12. non-goals and prohibited shortcuts;
13. concrete risks and mitigations;
14. explicit HALTs; and
15. empty closure fields until verified execution supplies evidence.

The `gap-plan` profile resolves every ID, validates the dossier schema, verifies path and symbol truth, checks sequence continuity and dependency order, and rejects a command or acceptance claim not grounded in the current repository.

## Seals and successors

Seal only through `clone_pack.py seal`. The command derives the profile result, binds governed paths and digests, updates document and manifest state, and writes `seal.json`.

For a trustworthy successor after any governed change:

1. advance `pack_revision`;
2. bind that revision across manifest, index, plans, and documents;
3. validate the predecessor before editing, retain its `seal.json`, and set `supersedes` to its schema, pack ID, revision, manifest SHA-256, and seal SHA-256;
4. regenerate affected evidence/runs under new IDs when contracts changed;
5. satisfy the selected profile; and
6. create a successor seal.

Tool `2.2.0` requires the retained predecessor seal, validates its schema/internal manifest binding and pinned seal digest, and checks the exact `supersedes` identity before archiving it. The predecessor's governed files must be validated before successor edits because their old bytes are no longer available afterward. Do not edit archived evidence, migration reports, transaction journals, history events, runs, snapshots, or the prior seal.
