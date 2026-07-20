# Full-stack QA contract

Load this reference when a browser workflow requires GUI, Playwright, end-to-end, full-stack, or CI verification through application-owned frontend, transport, service, and persistence layers.

## Applicability

Use the optional `full_stack_qa_plan.json` only when all four required layers exist in the selected journey:

1. the browser-visible frontend;
2. the real request and response crossing the transport boundary;
3. an application-owned service postcondition; and
4. a persisted state verified after reload, relogin, or restart.

Use ordinary web capture and dimension-specific parity for a static page or a workflow without these four layers. Do not label a UI-only, mocked-service, or screenshot-only check full-stack.

## Inspect before authoring

Inspect and record these repository facts before adding the plan:

- governing `AGENTS.md` files and existing CI workflows;
- package manager, lockfile, Playwright package/version, browser source, and configuration;
- frontend, mid-tier, backend, persistence, cache, queue, worker, and external-service topology;
- repository-owned setup, migration, seed, reset, cleanup, start, readiness, test, and report commands;
- authentication roles, tenant boundaries, synthetic fixtures, and forbidden production origins;
- stable test files, result artifacts, logs, screenshots, trace policy, and redaction limits;
- the exact indexed `WF`, `ACT`, `REQ`, `AC`, `TEST`, `GATE`, `ENV`, `ART`, and authority records.

Missing information is `UNKNOWN_BLOCKER`. Do not invent a command, file, service, hash, assertion, or CI check name.

## Author the optional plan

Copy `assets/templates-v2/full_stack_qa_plan.json` to the pack root and replace every marker. Add only this canonical optional manifest entry:

```json
"full_stack_qa": "full_stack_qa_plan.json"
```

Legacy clone-pack/v2 manifests without this entry remain valid. Do not add the plan when full-stack QA is not applicable.

The plan schema is `clone-full-stack-qa-plan/v1`. It requires:

- `safe_test_environment: true`, `production_access: false`, synthetic data, lifecycle commands, and classified HTTP(S) allowed origins without credentials, non-root paths, queries, or fragments;
- real application-owned frontend, mid-tier, backend, and persistence services with readiness contracts; two core roles may use the same `service_id` only when their complete service declarations are identical;
- `owned_stack.supporting_services` as an explicit array of applicable real `queue`, `cache`, and `worker` components; each entry has a unique ID, bounded readiness, an exact assertion, a declared proof artifact, and at least one journey reference;
- every external sandbox, stub, or exclusion to have a recorded authority decision; a non-excluded dependency also has an exact interface containing `protocol`, `endpoint`, and `classification` of `LOOPBACK` or `AUTHORIZED_SANDBOX`, plus bounded readiness, assertion, proof artifact, journey reference, and result;
- `playwright.package` to be exactly `@playwright/test`, `playwright`, or `playwright-core`, with a declared version, project, lockfile/config hashes, browser, OS, viewport, locale, time zone, motion/color settings, one worker, zero retries, failure artifacts, and no install command;
- one pinned CI workflow and required check using read-only permissions, the indexed GATE contract, `blocked_exit_codes: [7]`, one canonical `ci.result_path` included in `artifact_paths`, and a nonempty `fresh_artifact_paths` that also contains that result;
- one or more journeys with exact UI, primary and `additional_exchanges` wire observations, service, and persistence assertions, required `identity_bindings`, plus governed authorization, job, accessibility, and visual dispositions.

Application-owned services MUST use `REAL`. Only an external dependency can be `SANDBOXED`, `STUBBED`, or `EXCLUDED`. `EXCLUDED` has null interface, readiness, assertion, and artifact fields and yields `NOT_APPLICABLE`; it is not proof of the external provider.

A non-excluded external result MUST echo the plan's complete interface exactly. `LOOPBACK` requires localhost or a loopback IP endpoint. An HTTP(S) interface's normalized scheme, host, and effective port must match one `environment.allowed_origins` entry; `AUTHORIZED_SANDBOX` origins carry authority decision IDs. Interface validation rejects malformed percent escapes and percent-decodes the query before applying the secret-like-name/value check. Interfaces cannot contain credentials or secret-like query parameters.

## Bind the plan to the index

Create one `ART-###` record for `full_stack_qa_plan.json`. Set its locator path to the canonical plan path and its anchor to the plan's `contract_sha256`. Every journey `oracle_ids` includes that ART plus at least one independent `E`, `ART`, or `CAP` oracle for the expected behavior. Add the same IDs to the journey TEST oracle links. The union of all journey oracle IDs exactly equals the GATE `oracle_ids` attributes and `oracles` links.

For each journey:

- `WF` links to every selected `REQ`;
- `TEST` links to every selected `REQ` and `AC`, the selected GATE, and the plan ART oracle;
- GATE links back to TEST;
- the union of journey REQ, AC, and TEST IDs exactly equals GATE `covered_ids`;
- each TEST includes its journey oracle IDs, and their union exactly equals GATE oracle links/attributes;
- plan CI argv, cwd, expected exit, blocked exit codes, artifact paths, and `fresh_artifact_paths` equal the GATE attributes exactly;
- every retained journey proof artifact occurs in GATE `artifact_paths`.
- `ci.result_path` names exactly one canonical repository output using `clone-full-stack-qa-result/v1` and occurs in both `artifact_paths` and `fresh_artifact_paths`.
- every supporting-service and non-excluded external-dependency proof artifact occurs in GATE `artifact_paths`, and every such ID is referenced by at least one journey.

Each independent `E-###` oracle links to the requirements whose expected behavior it establishes. A plan ART proves contract identity, not expected product behavior, so it cannot be the only journey oracle.

Calculate `contract_sha256` from canonical JSON with only the `contract_sha256` field excluded:

```bash
python3 -c 'import json,sys;sys.path.insert(0,sys.argv[1]);from scripts.clonepack.full_stack_qa import full_stack_qa_contract_sha256;value=json.load(open(sys.argv[2],encoding="utf-8"));print(full_stack_qa_contract_sha256(value))' "<skill-root>" "<pack>/full_stack_qa_plan.json"
```

Write the returned digest into the plan, set the ART locator anchor to that digest, set its locator SHA-256 to `null`, then run:

```bash
python3 "<skill-root>/scripts/clone_pack.py" rehash "<pack>" --record ART-001
```

Changing any plan contract field invalidates `contract_sha256`, its ART locator, and every run whose oracle hashes include that ART. Recalculate, rehash, and rerun; never preserve an earlier PASS as current evidence.

## Bind one captured identity through the journey

Every journey has a nonempty `identity_bindings` array. Each binding is an exact contract:

```json
{
  "id": "BIND-001",
  "name": "captured_entity_id",
  "source": {
    "exchange_trigger": "primary-action",
    "response_json_pointer": "/id",
    "value_type": "string"
  },
  "consumers": [
    {
      "kind": "WIRE_PATH",
      "contract_pointer": "/journeys/0/wire/additional_exchanges/0/path"
    },
    {
      "kind": "SERVICE",
      "contract_pointer": "/journeys/0/service/probe"
    },
    {
      "kind": "PERSISTENCE",
      "contract_pointer": "/journeys/0/persistence/postcondition"
    }
  ],
  "artifact_path": "artifacts/full-stack-qa-result.json"
}
```

The source `exchange_trigger` names the journey's primary exchange or one ordered additional exchange. `response_json_pointer` is an RFC 6901 JSON Pointer into that response body. `value_type` is `string` or `integer`. Binding IDs and names are unique within the journey, and `artifact_path` equals `ci.result_path`.

Every binding contains at least one consumer of each mandatory kind: `WIRE_PATH`, `SERVICE`, and `PERSISTENCE`. A consumer `contract_pointer` resolves inside the current plan to a controlled string for its kind and contains the exact `{captured_entity_id}` placeholder once. For `WIRE_PATH`, the placeholder occupies one complete path segment and the selected exchange occurs after the source response. Optional controlled consumer kinds are `SUPPORTING_SERVICE`, `EXTERNAL_DEPENDENCY`, `JOB`, and `UI`; a supporting-service or external-dependency target must be referenced by the same journey.

The repository gate extracts the source value and converts it to canonical text before hashing: preserve a JSON string's exact Unicode scalar sequence; render a JSON integer as its base-10 integer spelling with no leading zero. Encode that text as UTF-8 and compute lowercase SHA-256. The canonical result writes that digest as `captured_value_sha256` and as every consumer's `observed_value_sha256`; the binding and every consumer have `status: PASS`. The result repeats the plan source and ordered `{kind, contract_pointer}` consumer descriptors exactly.

The result `wire.observed_path` contains a concrete segment instead of the placeholder. The validator percent-decodes that segment as UTF-8, applies the declared integer lexical rule when applicable, hashes the decoded bytes, and requires equality with `captured_value_sha256`. It exact-matches every other literal path segment. Service and persistence consumer hashes are emitted evidence: the validator checks their schema, equality, pointers, and `PASS` statuses but does not inspect application internals or independently derive their observed values. Do not describe a binding pass as code-path proof.

## Build the repository-owned gate

The indexed GATE argv owns orchestration. Its executable performs this sequence inside the authorized test environment:

```text
preflight pinned executable, Playwright package/browser/project/config, service runtimes, and files
  -> reset isolated services
  -> apply actual migrations
  -> load deterministic synthetic fixtures
  -> start application-owned frontend, core services, persistence, and declared queue/cache/worker components
  -> start declared external sandbox/stub boundaries
  -> pass every bounded owned and external readiness probe
  -> run repository-native contract/integration checks
  -> run Playwright journeys
       browser action and UI assertion
       -> observed primary and every declared additional request and response
       -> extract each BIND source with its response JSON pointer and hash the canonical UTF-8 value
       -> substitute the concrete value into each declared wire-path segment and observe every bound consumer
       -> API or service postcondition
       -> persistence proof after reload/relogin/restart
       -> supporting-service and external-boundary assertions
  -> emit the declared sanitized clone-full-stack-qa-result/v1 artifact and logs
  -> stop services and clean fixtures
```

The required lane MUST NOT intercept or replace an application-owned frontend, API, service, database, queue, cache, or worker. A separate component-test lane can use owned-service mocks, but it cannot satisfy this plan.

Playwright uses user-facing roles, labels, text, or explicit test IDs and web-first assertions. Do not use arbitrary sleeps as readiness or completion proof. Bind each request assertion to its unique `trigger`, then verify the named server/data postcondition independently. The configured driver selects the exact `playwright.project` recorded in the plan and result.

## Install and execution boundary

The clone-pack runtime never installs Playwright, Node packages, browsers, services, or operating-system dependencies. `playwright.install_argv` is always `null`. `playwright.package` is only `@playwright/test`, `playwright`, or `playwright-core`. Downloader shims such as `npx`, `pnpm dlx`, or `bunx` are forbidden as the declared Playwright driver.

A target repository CI workflow can execute a repository-owned, authority-recorded restore command from a pinned lockfile. Record that exact argv and decision in `ci.restore_argv` and `restore_authority_decision_ids`. The skill does not execute or authorize it implicitly.

The clone-pack runtime hashes the exact repository lockfile bytes and rejects a hash mismatch. It does not parse the lockfile, prove that the declared Playwright package/version occurs in it, or prove that any package or browser is installed. The repository-owned GATE wrapper performs non-mutating capability preflight before setup or browser behavior. It checks the declared executable, package/version, browser binary, selected project/configuration, service runtimes, test files, and environment. It then executes the bounded readiness commands/HTTP probes recorded in the plan. The clone-pack validator checks the contracts and allowed HTTP origins but does not execute those probes.

If capability, startup, or readiness is unavailable, the wrapper exits `7`. `ci.blocked_exit_codes` is exactly `[7]`, the indexed GATE has the same attribute, and `record-run` retains stdout/stderr plus `RUN_DECLARED_BLOCK` as `BLOCKED`, returns exit `7`, and skips all declared artifacts. For a behavioral mismatch the wrapper emits the canonical failing result and returns a nonzero code other than `7`; `record-run` retains its exact `observed_exit`, records `FAIL`, and returns `5`.

For every non-blocked run, each path in `fresh_artifact_paths` must be created or rewritten by that invocation. `record-run` snapshots its device, inode, size, modification time, change time, and SHA-256 before executing the GATE, then compares the post-run state before promotion. If every recorded field is unchanged, it retains no successful run and stops with `RUN_ARTIFACT_STALE` and exit `4`. Deleting or rewriting the prior canonical result inside the repository-owned wrapper is sufficient only when the current invocation then produces the declared regular file; never let a no-op gate reuse old result bytes.

Each automatic RUN emitted by tool `2.2.0` also retains `execution_contract`, an exact object containing argv, cwd, the declared environment map, timeout, expected/blocked exits, artifact/fresh-artifact paths, covered IDs, oracle IDs, normalizations, and redactions. The runtime validates the complete object against the retained-run schema before process execution; an invalid contract exits `1` with `RUN_CONTRACT_INVALID`, executes no GATE, and writes no RUN. Pack validation compares retained evidence with the current indexed GATE and reports `RUN_CONTRACT_STALE` if any field differs. Legacy automatic RUNs from an earlier tool can omit the field for v2 compatibility; they do not attest these added fields, so replace them with a current run before claiming this contract. `gap-plan` performs readiness validation only; current passing result evidence starts at `verified-mvp` and is also required by `gap-closure` and `closed`.

Execute and retain proof with the existing command:

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
```

The plan requires the target CI workflow to invoke the exact same repository GATE argv. The runtime pins the workflow bytes by SHA-256 but does not parse CI YAML or query hosted check configuration; inspect the workflow and hosted check separately. The target job does not need access to clone-pack unless that repository explicitly vendors or installs this skill.

## Evidence and redaction

Copy `assets/templates-v2/full_stack_qa_result.json` into the target gate implementation and emit it at `ci.result_path` using schema `clone-full-stack-qa-result/v1`. Replace every marker at runtime. The result binds the current plan digest, GATE, environment, `playwright_project`, exact journey set, every primary/additional wire exchange, every `identity_bindings` source and ordered consumer set, supporting-service results, external-dependency disposition/protocol/endpoint/classification/assertion results, and separate UI, service, persistence, and optional-dimension outcomes. Each applicable result and identity consumer is `PASS`; each excluded external dependency is `NOT_APPLICABLE`. Every non-excluded external result echoes the complete plan interface exactly. `record-run` retains the result's original repository path and immutable copied bytes. Retain sanitized frontend/backend/service logs and the CI test report required to reproduce a mismatch.

Trace, video, screenshot, storage-state, cookie, and service-log artifacts can contain secrets or personal data. Use synthetic non-sensitive fixtures and minimize retention. Text redaction rules do not make binary traces or videos redactable; exclude binary evidence that requires redaction and retain sanitized textual results instead.

Capture `PASS` remains acquisition status. A screenshot, trace, navigation, HTTP response, or Playwright process exit alone does not prove full-stack behavior.

## Profile effects

When the manifest includes the optional plan:

- `build-ready` validates its schema, repository file hashes, authority records, trace links, GATE contract, and proof-artifact declarations;
- `enhancement-ready` applies the same readiness checks to a brownfield workstream;
- `verified-mvp` and `verified-enhancement` additionally require a current linked `PASS` RUN for every declared journey;
- the latest linked RUN for the declared GATE/environment controls; a later `FAIL` or `BLOCKED` is not masked by an earlier `PASS`;
- verified profiles parse the retained `ci.result_path`, validate `clone-full-stack-qa-result/v1`, require exact plan/GATE/environment/Playwright-project/journey identity, exact primary/additional exchange contracts, exact binding IDs/sources/ordered consumers and matching hashes, exact supporting/external result sets and interfaces, and every applicable dimension to pass;
- sealing includes `full_stack_qa_plan.json` because it is a manifest plan path.

A missing current journey run or latest non-passing run is a verification `HOLD`. A missing/malformed canonical result, malformed plan, broken trace, non-`REAL` application-owned declaration, stale repository file, stale current-invocation result, or GATE mismatch blocks verification.

`implementation: REAL` is a governed declaration, not code introspection. The validator rejects any other plan value but cannot prove that repository code does not hide a mock, proxy, or alternate store. The gate and independent repository probes must expose that behavior; undiscoverable internals remain outside the machine claim.

## Claim boundary

A passing full-stack gate proves only the declared browser action, observed request and response, named API or data postcondition, canonical result evidence, and retained environment. `identity_bindings` prove that the emitted captured and consumer hashes agree and that a concrete observed wire-path segment hashes to the captured digest. The validator checks emitted evidence, not application internals; service and persistence hashes can be false if the repository-owned gate emits false evidence.

It does not prove unobserved mid-tier control flow, database constraints, background jobs, third-party provider behavior, package installation, hosted CI execution, or production deployment.

Report each required dimension separately. Record unobserved jobs, constraints, consumers, integrations, browsers, viewports, and production conditions as exclusions, gaps, or blockers.
