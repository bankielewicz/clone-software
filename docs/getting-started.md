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
scripts/clonepack/
```

Run:

```bash
python3 "/absolute/path/to/installed/clone-software/scripts/clone_pack.py" --help
```

The process MUST exit `0`. Its positional command list MUST contain these twelve names:

```text
init validate migrate capture parity scaffold
record-run record-manual gap-transition assure seal diff
```

In Codex CLI or the IDE extension, type `$` or run `/skills` and confirm that `clone-software` appears. Codex detects changes automatically. If it remains absent, restart Codex once, confirm the discovery path, and check that `SKILL.md` has valid YAML frontmatter.

## 4. Prepare the request record

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

## 5. Invoke Codex

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

## 6. Expected Codex sequence

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

## 7. Recognize the first generated pack

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

## 8. Run the first validator explicitly

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

## 9. Interpret the terminal response

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
