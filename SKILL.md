---
name: clone-software
description: Specify, capture, scaffold, build, compare, secure, migrate, and verify authorized clean-room MVP reimplementations and evidence-grounded brownfield changes. Use when Codex is asked to clone, recreate, replicate, or reverse-specify software; enhance, extend, modernize, refactor, upgrade, migrate, or harden an existing repository; generate an AI-optimized clone or enhancement specification; produce or implement gaps_analysis.md; migrate a clone-pack/v1 pack; or prove target-versus-clone and before-versus-after behavior without guessing. Covers websites, SaaS products, APIs, services, servers, clients, libraries, SDKs, CLIs, browser extensions, AI/ML systems, data pipelines, storage systems, distributed or realtime systems, games, and embedded or IoT software.
---

# Clone Software

Create an evidence-grounded behavioral reimplementation. Produce the smallest complete authorized product slice, compare it with an immutable reference oracle, and record every excluded or divergent behavior as an implementation-ready gap.

## Enforce the boundary

- Reimplement authorized observable behavior and documented interfaces. Never claim source, binary, algorithmic, operational-scale, security, accessibility, or visual equivalence without evidence for that dimension.
- Record authorization before inspecting non-public surfaces or proprietary artifacts. Never bypass authentication, licensing, DRM, signing, rate limits, anti-bot controls, or access controls.
- Do not copy source, secrets, personal data, proprietary models, trademarks, trade dress, text, or media without recorded rights. Default to synthetic data and replacement branding.
- Never collect target credentials or impersonate the original product.
- Freeze the target build, environment, accounts, roles, data, locale, time zone, devices, integrations, and observation date. Create a successor baseline when any of them changes.
- Separate `VERIFIED`, `USER_PINNED`, `INFERRED`, and `UNKNOWN_BLOCKER` truth. Never promote inference into a requirement.
- Halt when a decision changes behavior, security, data ownership, compatibility, architecture, distribution, or the MVP boundary. Name the blocked ID and ask one answerable question.
- Use gaps only for evidenced work outside the pinned MVP, an existing MVP discrepancy, or missing evidence. Never hide an unfinished MVP requirement in a gap.

## Select the mode

| Intent | Mode | Terminal artifact |
| --- | --- | --- |
| Clone, recreate, or build an MVP | `mvp-build` | Verified MVP or `HOLD`, plus complete gaps |
| Analyze, capture, specify, or plan | `spec-only` | `spec-ready` or exact blockers; no product-code edits |
| Plan an existing gap register | `gap-plan` | Dependency-safe, cold-executable dossiers |
| Implement selected gaps | `gap-implement` | Evidenced legal transitions through closure or `HALT` |
| Refresh an old clone pack | `pack-migrate` | Non-overwriting v2 successor and migration report |
| Plan a bounded change to an existing repository | `enhancement-plan` | Passing `enhancement-ready` plan or exact blockers; no product-code edits |
| Implement a bounded existing-repository change | `enhancement-build` | Passing sealed `verified-enhancement` or exact blockers |

Default to `mvp-build` only when the user requests implementation. Do not widen a documentation-only request.

## Load the contracts

Always read [evidence-and-fidelity.md](references/evidence-and-fidelity.md) and [document-contracts.md](references/document-contracts.md).

Load operational references only when applicable:

- Capture or compare target behavior: [capture-and-parity.md](references/capture-and-parity.md).
- Bootstrap a repository: [greenfield.md](references/greenfield.md).
- Plan or run assurance and provenance: [security-and-provenance.md](references/security-and-provenance.md).
- Validate, migrate, supersede, seal, or close packs: [pack-evolution.md](references/pack-evolution.md).
- Plan or implement a change in an existing repository: [brownfield-enhancement.md](references/brownfield-enhancement.md).

Select every product playbook consumed by a hybrid product:

- Website: [website.md](references/website.md)
- Browser application or SaaS: [web-app-saas.md](references/web-app-saas.md)
- API, service, worker, protocol, or server: [api-service-server.md](references/api-service-server.md)
- Desktop or mobile client: [client-app.md](references/client-app.md)
- Library or SDK: [library-sdk.md](references/library-sdk.md)
- CLI: [cli.md](references/cli.md)
- Browser extension: [browser-extension.md](references/browser-extension.md)
- AI/ML system: [ai-ml-system.md](references/ai-ml-system.md)
- Data pipeline: [data-pipeline.md](references/data-pipeline.md)
- Database or storage engine: [database-storage.md](references/database-storage.md)
- Distributed or realtime system: [distributed-realtime.md](references/distributed-realtime.md)
- Game or simulation: [game-simulation.md](references/game-simulation.md)
- Embedded or IoT system: [embedded-iot.md](references/embedded-iot.md)

## Use clone-pack/v2

Run the unified standard-library CLI:

```bash
python3 <skill-root>/scripts/clone_pack.py <command> ...
```

Before interpreting any profile or lifecycle result from tool version `2.1.0`, read [runtime-enforcement-boundaries.md](docs/runtime-enforcement-boundaries.md). Apply the semantic contracts in this skill to dimensions outside the selected machine profile. Report machine validation and any required semantic audit as separate results.

Initialize a non-overwriting v2 pack:

```bash
python3 <skill-root>/scripts/clone_pack.py init \
  --product-name "<exact name>" \
  --product-type <controlled-type> \
  --playbook <repeat-for-hybrid-contracts> \
  --source-description "<authorized immutable reference>" \
  --repo-root <repository-root> \
  --output-dir <repository-relative-pack-directory>
```

The pack contains human contracts in Markdown and canonical identity, relationship, execution, lifecycle, and integrity records in JSON. Treat Markdown as normative behavior and JSON as normative graph/execution state. Never edit a status string to manufacture verification.

Use these validation profiles in order:

1. `scaffold`: schema, manifest, safe paths, documents, and plans exist.
2. `baseline-ready`: authorization, target baseline, environments, and capture plan are frozen.
3. `spec-ready`: evidence, requirements, acceptance criteria, tests, and bidirectional traceability are complete.
4. `build-ready`: repository revision, architecture, implementation locations, gates, provenance, and risk-based assurance are pinned.
5. `verified-mvp`: at least one complete MVP `REQ -> AC -> TEST -> GATE -> PASS RUN` chain, current required reference and clone captures, required passing parity over those captures, assurance, no MVP blockers, and a valid seal exist.
6. `gap-plan`: every actionable gap has a selected dependency-safe order and cold-executable dossier.
7. `gap-closure`: selected gaps have legal lifecycle and current closure evidence.
8. `closed`: every retained gap is `VERIFIED` or `DECLINED` and the pack is sealed.

For a brownfield enhancement, use the branch-aware sequence:

1. `repository-adopted`: request, repository inventory, workstream, adopted snapshot, and reciprocal records are valid.
2. `enhancement-ready`: affected surfaces, compatibility decisions, preservation cases, allowed path scope, implementation locations, and gates are executable.
3. `implementation`: this is the human workflow phase after `enhancement-ready`, not a validation profile; it is forbidden in `enhancement-plan` mode.
4. `verified-enhancement`: current candidate snapshot, preservation, scope, assurance, lifecycle, and enhancement-seal evidence pass.

Validate with:

```bash
python3 <skill-root>/scripts/clone_pack.py validate <pack> --profile <profile>
```

Treat any nonzero result as blocking. Exit `5` means an honest verification `HOLD`; it is not tool success.

## Enhance an existing repository

Read [brownfield-enhancement.md](references/brownfield-enhancement.md) before inspecting or changing an existing implementation. Initialize only from a repository-contained, non-empty UTF-8 request and an absent pack path:

```bash
python3 <skill-root>/scripts/clone_pack.py enhancement-init \
  --product-name "<exact name>" \
  --product-type <controlled-type> \
  --playbook <repeatable-playbook> \
  --enhancement-id ENH-001 \
  --title "<exact title>" \
  --change-type <repeatable-controlled-change-type> \
  --request-file <repository-relative-request-file> \
  --repo-root <repository-root> \
  --output-dir <absent-repository-relative-pack-directory>
```

Reject a dirty repository by default. Use `--adopt-dirty` only when the requester explicitly adopts the exact existing paths and bytes as protected input. Initialization writes the pack only; it never edits product code.

Freeze the before-state and required preservation results before implementation:

```bash
python3 <skill-root>/scripts/clone_pack.py repo-snapshot <pack> --role adopted --record
python3 <skill-root>/scripts/clone_pack.py baseline-run <pack> --all
python3 <skill-root>/scripts/clone_pack.py validate <pack> --profile enhancement-ready
```

In `enhancement-build`, apply TDD inside the plan's exact path and behavior fence only after `enhancement-ready` passes. Then retain the candidate state and prove both behavior and scope:

```bash
python3 <skill-root>/scripts/clone_pack.py repo-snapshot <pack> --role candidate --record
python3 <skill-root>/scripts/clone_pack.py regression <pack> --all
python3 <skill-root>/scripts/clone_pack.py verify-scope <pack> --enhancement ENH-001
```

Change enhancement state only through `enhancement-transition`; never edit the plan status or hash-chained history. Use `rehash --record` or `rehash --case` only for an explicit existing target. Seal only a passing `verified-enhancement` state. The workflow does not install tools, deploy, mutate production, push, open or merge a pull request; those actions require separate repository workflow authority and Codex CLI capability.

## Capture the target

1. Inventory every in-scope actor, surface, workflow, state, transition, input, output, error, permission, side effect, persistence rule, background operation, timing/order rule, and recovery path.
2. Give every environment, artifact, observation, surface, workflow, requirement, criterion, test, gate, capture, parity case, assurance case, and gap a stable controlled ID.
3. Populate `capture_plan.json`. Use HTTP, CLI/process, filesystem, manual/custom, or optional Playwright-compatible web capture.
4. Pin `lifecycle.setup` and `lifecycle.teardown` as `null` or exact no-shell commands with argv, cwd, environment, expected exit, and timeout. Use lifecycle commands to create and remove deterministic fixtures; do not prepare state through unrecorded shell steps.
5. Execute one authorized case or the complete plan in lexical capture-ID order. Use resume only for an interrupted selected capture set:

```bash
python3 <skill-root>/scripts/clone_pack.py capture <pack> --case CAP-001
python3 <skill-root>/scripts/clone_pack.py capture <pack> --case CAP-001 --resume
python3 <skill-root>/scripts/clone_pack.py capture <pack> --all
python3 <skill-root>/scripts/clone_pack.py capture <pack> --all --resume
```

6. Treat finalized evidence as immutable. The runner stages each case under a real non-symlink pack root, rejects undeclared/symlink/non-regular outputs and runner-name collisions, records observation start/completion timestamps, atomically promotes complete evidence, and permits resume to remove only runner-owned incomplete staging after exact result-pointer validation. Read [capture-and-parity.md](references/capture-and-parity.md) before using lifecycle or batch capture.
7. Hash and redact every retained textual artifact and structured observation field. A binary artifact under a declared redaction rule fails acquisition and is never promoted. Require an authorization decision for credentialed reference HTTP reads; require both a decision and `safe_test_environment: true` for mutating reference requests or reference-side processes.
8. Never put a raw secret in capture, comparator, web-driver, lifecycle, or gate environments. For a key containing `TOKEN`, `KEY`, `SECRET`, `PASSWORD`, `AUTH`, `COOKIE`, or `CREDENTIAL`, store only `env:NAME`; the runner resolves it transiently and rejects missing or invalid sources.
9. Mark unavailable adapters `BLOCKED`. Never substitute an inferred observation.

## Specify and plan the MVP

- Define fidelity as `MUST_MATCH`, `MAY_DIFFER` with an exact tolerance, or `EXCLUDED` with an authority and gap/non-goal disposition.
- Select complete vertical journeys with real persistence, authorization, validation, errors, recovery, and a reproducible run path. Reject screenshots, dead controls, fake persistence, and hard-coded success presented as implementation.
- Maintain `E/DEC -> REQ -> AC -> TEST/GATE -> RUN` bidirectionally in `clone_index.json`.
- Define actors, permissions, state machines, interfaces, data, security, time, ordering, concurrency, idempotency, retry, compatibility, accessibility, performance, deployment, telemetry, migration, backup, and recovery wherever applicable.
- Write exact repository paths only after inspection. For greenfield work, resolve one `STACK-###` decision and select exactly one audited profile: `static-web-esm`, `python-src`, `typescript-src`, or `rust-crate`. Copy that profile's `template`, `required_paths`, and `commands` from `assets/scaffolds/catalog.json` without alteration, then preview the neutral scaffold:

```bash
python3 <skill-root>/scripts/clone_pack.py scaffold <pack>
python3 <skill-root>/scripts/clone_pack.py scaffold <pack> --apply
```

- For a brownfield repository with an adopted implementation, record the scaffold plan as `profile_id: not-applicable`, `template: not-applicable`, `output_root: .`, empty `required_paths`, all-null `commands`, and `applied: false`. This disposition produces no files. There is no custom scaffold mode; halt if none of the four audited profiles fits a greenfield contract.
- Treat scaffolds as audited structure, never as product behavior. The scaffolder returns the pinned command argv but does not execute commands, install packages, or access the network. It refuses every existing destination and rolls back files and directories it created if apply does not complete.

Do not modify product code before `build-ready` passes.

## Implement and record proof

For each dependency-ordered vertical slice:

1. Reconfirm governing evidence, requirements, decisions, and the allowed path fence.
2. Add a discriminating failing test or record the repository-specific reason another order is required.
3. Implement the smallest complete behavior.
4. Exercise normal, boundary, negative, authorization, concurrency, interruption, and recovery cases that apply.
5. Run focused and broad gates from pinned argv arrays without a shell:

```bash
python3 <skill-root>/scripts/clone_pack.py record-run <pack> --gate GATE-001 --environment ENV-001
```

The runner retains stdout, stderr, and declared regular-file artifacts after containment, hash, and redaction checks. Missing executable, process-start failure, and timeout retain deterministic blocked evidence.

6. Record manual verification only with a versioned procedure, named observer and authority, and retained artifacts:

```bash
python3 <skill-root>/scripts/clone_pack.py record-manual <pack> \
  --test TEST-001 --procedure <procedure-file> \
  --observer "<identity>" --authority "<authority>" \
  --artifact <repeatable-pack-relative-path>
```

A run is stale when its target baseline, clone revision/diff, environment, gate, test, oracle, normalization, or artifact changes.

## Prove parity and assurance

- Capture reference and clone results independently under the same environment ID.
- Compare immutable reference evidence against clone evidence:

```bash
python3 <skill-root>/scripts/clone_pack.py parity <pack> --case PAR-001
```

- Use exact, text, JSON, HTTP, filesystem, DOM/accessibility, performance, or configured local perceptual/custom comparison. Pin comparator-specific options and tolerances. Authorize every normalization by artifact and field/region with decision/evidence IDs.
- Never derive expected results from clone code.
- Run the assurance plan without implicit installation:

```bash
python3 <skill-root>/scripts/clone_pack.py assure <pack>
python3 <skill-root>/scripts/clone_pack.py assure <pack> --all
```

The default selects required cases; `--all` explicitly includes optional cases. The runner preflights the complete selected set, emits canonical JSON, and aggregates exits with precedence `7`, then `5`, then `0`.

- Always require authority, data classification, threat/abuse modeling, origin/rights provenance, and secret handling. Add SAST, secret, dependency, license, and SPDX gates for internal delivery. Add applicable DAST, SLSA/in-toto provenance, independent attestation, rollback, and recovery gates for customer, public, or production delivery.
- Record `non-separated` when one context observes and implements. Claim `strict-separated` only with distinct observer/implementer identities and resolved contamination evidence.

Seal only a passing derived state:

```bash
python3 <skill-root>/scripts/clone_pack.py seal <pack> --profile verified-mvp
```

## Maintain gaps without ambiguity

Give every inventoried capability exactly one disposition: `EQUIVALENT`, `MISSING`, `PARTIAL`, `DIVERGENT`, `EXCLUDED`, or `UNVERIFIED`.

For every actionable gap, record current reference/clone evidence, exact delta, target contract, impact, dependencies, verified file/symbol map, ordered implementation steps, interface/data/security/operations rules, fixtures, tests, commands, expected results, atomic acceptance criteria, rollout, rollback, recovery, risks, non-goals, HALTs, and closure evidence. Reject `TBD`, lowercase “should”, “maybe”, “ideally”, and unbounded “support”.

Copy `assets/templates-v2/gap_dossier.json` into each ready `GAP-###.attributes.dossier` in `clone_index.json` and replace every marker. `gap-plan` machine-validates the dossier schema, current record graph, existing/new paths, exact symbol anchors, allowed fence, commands, test dimensions, decisions, closure placeholders, and GAP backlinks. Keep an `EVIDENCE_GAP` `BLOCKED` with the exact `attributes.blocker` contract from [document-contracts.md](references/document-contracts.md); never invent an implementation plan for missing evidence.

Change status only through:

```bash
python3 <skill-root>/scripts/clone_pack.py gap-transition <pack> GAP-001 \
  --to <status> --actor "<identity>" --reason "<exact reason>" \
  --evidence <repeatable-ID> --decision <repeatable-DEC-ID>
```

Enforce `OPEN -> IN_PROGRESS -> IMPLEMENTED -> VERIFIED`, blocking/unblocking, explicit decline, evidenced reopen, verified dependencies, current acceptance runs, parity, and assurance. Derive `NO-OPEN-GAPS`; never edit it as authority.

## Migrate and hand off

Inspect v1 migration without writing:

```bash
python3 <skill-root>/scripts/clone_pack.py migrate <v1-pack> --check
```

Create a non-overwriting successor:

```bash
python3 <skill-root>/scripts/clone_pack.py migrate <v1-pack> --output <new-v2-directory>
```

Preserve v1 bytes, hashes, IDs, and provenance. Downgrade unverifiable v1 `VERIFIED` claims. Require an explicit mapping for ambiguous IDs. Never mutate the v1 source.

Return the operating mode, frozen baseline or adopted snapshot, highest passing profile, exact commands/results, implemented and verified boundary, pack/seal paths, gap counts by class/status, blocked IDs and decisions, and the next dependency-safe work IDs. For brownfield work also return the enhancement ID, change types, candidate snapshot, affected surfaces, compatibility decisions, changed paths, preservation results, security and dependency deltas, and residual gaps. Never claim production readiness or complete parity beyond sealed evidence.
