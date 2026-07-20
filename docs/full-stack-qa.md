# Full-stack QA with Playwright

This guide describes the implemented tool `2.2.0` contract for repository-specific browser-to-persistence verification. The clone-pack runtime stays Python standard-library only. Playwright and every application runtime remain target-repository capabilities.

## What the pipeline proves

A required journey connects four independent observations under one synthetic fixture and one environment:

| Layer | Required observation |
| --- | --- |
| UI | Playwright performs a named user action and observes the exact visible state |
| Wire | Each named trigger observes the real application request and response with pinned method, path, status, and schema assertion |
| Service | A repository-controlled API or integration probe observes the named server postcondition |
| Persistence | Reload, relogin, or restart observes the same persisted identity and state |

A passing full-stack gate proves only the declared browser action, observed request and response, named API or data postcondition, and retained environment. It does not prove unobserved mid-tier control flow, database constraints, background jobs, third-party provider behavior, or production deployment.

Playwright supplies the browser action, user-visible assertion, request/response observation, API request context, trace, screenshot, and browser matrix. Repository-native integration/data probes supply transaction, constraint, job, queue, migration, and persistence evidence that the browser cannot observe directly.

## Required inputs

Before authoring, record:

- pack path and selected `mvp-build` or `enhancement-build` mode;
- repository revision, governing instructions, package manager, lockfile, one supported Playwright package (`@playwright/test`, `playwright`, or `playwright-core`), its exact declared version, and browser source;
- exact frontend, mid-tier, backend, database, cache, queue, and worker commands; one implementation may fill multiple core roles only when the complete declaration is identical;
- migration, reset, seed, cleanup, readiness, and shutdown commands;
- synthetic actors, roles, tenants, records, and forbidden production origins;
- existing CI provider/workflow, required check, runner, permissions, and dependency restore command;
- `WF`, `ACT`, `REQ`, `AC`, `TEST`, `GATE`, `ENV`, `ART`, and decision IDs;
- exact test, workflow, Playwright configuration, lockfile, result, and log paths.

If a command, file, environment, service, or expected result is unknown, stop with its ID and one resolution question.

## Files and authority

Add `full_stack_qa_plan.json` only when a complete browser-to-persistence journey applies. Copy the reusable source from `assets/templates-v2/full_stack_qa_plan.json`, replace every marker, and add this optional canonical manifest path:

```json
{
  "plans": {
    "capture": "capture_plan.json",
    "parity": "parity_plan.json",
    "scaffold": "scaffold_plan.json",
    "assurance": "assurance_plan.json",
    "full_stack_qa": "full_stack_qa_plan.json"
  }
}
```

Brownfield manifests retain `repository_inventory` and `enhancement` in the same map. Old v2 packs omit `full_stack_qa` and remain valid.

The plan is governed by `assets/schemas/full-stack-qa-plan-v1.schema.json`. The target gate's canonical output is governed by `assets/schemas/full-stack-qa-result-v1.schema.json` and starts from `assets/templates-v2/full_stack_qa_result.json`. The plan is bound through one ART record and its `contract_sha256`. Each journey adds at least one independent `E`, `ART`, or `CAP` oracle; the TEST and GATE bind the exact oracle union and coverage union. The evidence oracle links to the requirements whose expected behavior it establishes. See [Full-stack QA contract](../references/full-stack-qa.md) for the exact hashing and link sequence.

`owned_stack.supporting_services` explicitly models every applicable application-owned `queue`, `cache`, and `worker`. Each entry is `REAL`, has a bounded readiness contract, exact assertion and proof artifact, and is referenced by `journeys[].supporting_service_ids`. A core service ID can appear in more than one of `frontend`, `mid_tier`, `backend`, and `persistence` only when those complete declarations are byte-for-byte equivalent after canonical JSON serialization; differing readiness or implementation fields are `QA_SERVICE_CONFLICT`.

Each external dependency records `disposition`, authority, reason, and—unless `EXCLUDED`—an exact `protocol`, `endpoint`, `classification`, readiness contract, assertion, and proof artifact. `classification` is exactly `LOOPBACK` or `AUTHORIZED_SANDBOX`. `LOOPBACK` requires `localhost` or a loopback IP. `AUTHORIZED_SANDBOX` remains a non-production test endpoint under the dependency's authority decision; it does not override `production_access: false`. HTTP(S) endpoints are absolute URLs whose scheme equals `protocol`; they have a host, no credentials, no secret-like query, and an origin present in `environment.allowed_origins`. The validator rejects malformed percent escapes and percent-decodes the query before checking decoded secret-like names or values. A non-HTTP endpoint is interpreted under its declared protocol, must have a host, and follows the same credential and secret-like-query prohibitions. The journey names the dependency in `external_dependency_ids`. The canonical result repeats the exact disposition, interface including classification, and assertion and must report `PASS`; `EXCLUDED` instead uses null contract fields and reports `NOT_APPLICABLE`.

## CI lifecycle

The target repository's required job executes this order:

1. Check out the exact revision without persisting delivery credentials.
2. Restore only repository-declared dependencies from the pinned lockfile when an authority decision permits that command.
3. Run the repository wrapper's non-mutating preflight for the declared Playwright package/version, selected project/browser/configuration, service runtimes, and declared files. Exit `7` before behavioral work if one is unavailable or inconsistent.
4. Start ephemeral application-owned service containers or repository processes and declared external stubs/sandboxes.
5. Pass every bounded owned and external readiness check.
6. Apply the actual migrations used by the application.
7. Reset and seed deterministic synthetic fixtures.
8. Start the frontend, core services, persistence, and applicable queue/cache/worker components.
9. Run repository-native API, contract, migration, and data probes.
10. Run the Playwright journey with the pinned project, one worker, and zero retries.
11. Emit `clone-full-stack-qa-result/v1` at the exact `ci.result_path`, plus sanitized service logs and the test report.
12. Run cleanup and terminate services even after a mismatch.

GitHub Actions service containers provide a concrete way to run databases with health checks on Linux. A repository using another CI provider records its native equivalent and preserves the same lifecycle and evidence contract. The runtime hashes the declared workflow file but does not parse CI YAML or prove hosted required-check configuration; verify those separately from the retained local run.

The skill repository's own CI does not install Playwright. The generated target-repository workflow uses the existing repository setup or an explicitly authorized restore argv. The clone-pack runtime never installs Playwright or a browser. It verifies the current lockfile bytes against `lockfile_sha256`, but it does not parse the lockfile and therefore does not prove that the declared package or version occurs in dependency resolution. The repository wrapper performs that preflight and exits `7` when the declared capability is unavailable.

## Journey example

This abbreviated example shows the required cross-layer meaning; the schema requires all remaining identity, hash, environment, CI, and optional-dimension fields:

```json
{
  "id": "QA-001",
  "workflow_id": "WF-001",
  "actor_id": "ACT-001",
  "requirement_ids": ["REQ-001"],
  "acceptance_ids": ["AC-001"],
  "test_id": "TEST-001",
  "gate_id": "GATE-001",
  "environment_id": "ENV-001",
  "ui": {
    "action": "submit the order form through its accessible button",
    "assertion": "the submitted state is visible after reload",
    "artifact_path": "artifacts/QA-001.json"
  },
  "wire": {
    "trigger": "submit-order",
    "method": "POST",
    "path": "/api/orders",
    "expected_status": 201,
    "schema_assertion": "response matches OrderCreatedResponse v1",
    "artifact_path": "artifacts/QA-001.json",
    "additional_exchanges": [
      {
        "trigger": "reload-order",
        "method": "GET",
        "path": "/api/orders/{captured_order_id}",
        "expected_status": 200,
        "schema_assertion": "response matches OrderResponse v1"
      }
    ]
  },
  "service": {
    "probe": "GET /api/orders/{captured_order_id}",
    "postcondition": "status is submitted for the captured actor",
    "artifact_path": "artifacts/QA-001.json"
  },
  "persistence": {
    "verification_event": "reload",
    "postcondition": "order {captured_order_id} remains submitted after reload",
    "artifact_path": "artifacts/QA-001.json"
  },
  "identity_bindings": [
    {
      "id": "BIND-001",
      "name": "captured_order_id",
      "source": {
        "exchange_trigger": "submit-order",
        "response_json_pointer": "/order_id",
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
      "artifact_path": "artifacts/QA-001.json"
    }
  ],
  "external_dependency_ids": ["EXTERNAL-001"],
  "supporting_service_ids": ["SERVICE-005"]
}
```

The primary wire object and ordered `additional_exchanges` cover submission, reload, relogin, or restart traffic separately. Triggers are unique within the journey. The result repeats each trigger and exact observed method, path, status, and schema assertion in the same order; missing, reordered, failing, or changed exchanges are rejected.

Every journey has at least one `identity_bindings` entry. Its ID is `BIND-###`; its unique lowercase `name` becomes the exact `{name}` placeholder. `source.exchange_trigger` names the primary or an additional exchange in that journey, `response_json_pointer` is the JSON Pointer used by the repository gate to extract the response value, and `value_type` is `string` or `integer`. Every binding includes at least one `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` consumer. Optional consumers are `SUPPORTING_SERVICE`, `EXTERNAL_DEPENDENCY`, `JOB`, and `UI`.

Each consumer's `contract_pointer` is a JSON Pointer to its controlled plan field. It must resolve to a string containing the exact placeholder once. A `WIRE_PATH` pointer targets a primary or additional wire `path`; the placeholder occupies one complete path segment, and that exchange occurs later than the source exchange. `SERVICE` targets `probe` or `postcondition`; `PERSISTENCE` targets `postcondition`; the other kinds target their controlled assertion field. A `SUPPORTING_SERVICE` or `EXTERNAL_DEPENDENCY` target must be referenced by the same journey through `supporting_service_ids` or `external_dependency_ids`. Consumer pointers are unique, and `artifact_path` equals `ci.result_path`.

The repository gate hashes the captured source value as canonical UTF-8: a string uses its exact decoded text, and an integer uses canonical decimal text (`0` or an optional minus followed by digits, without a plus sign or leading zero). The result reports the exact binding ID/source and the consumers in plan order, `status: PASS`, one `captured_value_sha256`, and the same value in every consumer's `observed_value_sha256`. The verifier additionally URL-decodes each concrete observed `WIRE_PATH` placeholder segment as UTF-8, enforces the declared value type, hashes it, and compares it with `captured_value_sha256`; a literal `{captured_order_id}` is not an observed path. The runtime validates the retained report and concrete wire path. It does not itself extract the source response value, execute the service probe, or query persistence, so the repository gate and discriminating independent probes remain responsible for those observations.

For an application-owned worker and an SMTP test boundary, the corresponding plan fragments are:

```json
{
  "owned_stack": {
    "supporting_services": [
      {
        "service_id": "SERVICE-005",
        "role": "worker",
        "implementation": "REAL",
        "readiness": {
          "kind": "COMMAND",
          "command": {
            "argv": ["python3", "qa/check-worker.py"],
            "cwd": ".",
            "environment": {},
            "expected_exit": 0,
            "timeout_seconds": 30
          }
        },
        "assertion": "the captured order is processed exactly once",
        "artifact_path": "artifacts/QA-001.json"
      }
    ]
  },
  "external_dependencies": [
    {
      "id": "EXTERNAL-001",
      "disposition": "STUBBED",
      "reason": "exercise the application email boundary without live delivery",
      "decision_ids": ["DEC-001"],
      "assertion": "one message is captured and live delivery is disabled",
      "interface": {
        "protocol": "smtp",
        "endpoint": "127.0.0.1:1025",
        "classification": "LOOPBACK"
      },
      "readiness": {
        "kind": "COMMAND",
        "command": {
          "argv": ["python3", "qa/check-email-stub.py"],
          "cwd": ".",
          "environment": {},
          "expected_exit": 0,
          "timeout_seconds": 30
        }
      },
      "artifact_path": "artifacts/QA-001.json"
    }
  ]
}
```

These are shape examples, not reusable facts. Replace every ID, command, endpoint, assertion, and path with inspected repository values. `SERVICE-005` occurs in `supporting_service_ids`; `EXTERNAL-001` occurs in `external_dependency_ids`. The result contains exact matching `supporting_services` and `external_dependencies` entries; the external result echoes the governed protocol, endpoint, and `classification`. For an excluded dependency, set `interface`, `readiness`, `assertion`, and `artifact_path` to `null`; its result status is `NOT_APPLICABLE` with null interface, assertion, and observation.

The CI plan and indexed GATE share these exact exit fields:

```json
{
  "expected_exit": 0,
  "blocked_exit_codes": [7],
  "artifact_paths": ["artifacts/QA-001.json"],
  "fresh_artifact_paths": ["artifacts/QA-001.json"],
  "result_path": "artifacts/QA-001.json"
}
```

`ci.fresh_artifact_paths` is a nonempty unique subset of `ci.artifact_paths`, and `ci.result_path` occurs in both. The indexed GATE's `argv`, `cwd`, `expected_exit`, `blocked_exit_codes`, `artifact_paths`, and `fresh_artifact_paths` exactly equal the CI plan fields. Before the process starts, `record-run` captures each fresh artifact's device, inode, size, `mtime_ns`, `ctime_ns`, and SHA-256, or records that it is absent. After a non-blocked process ends, it reads the regular, non-symlink, single-link file again. An absent-before file is fresh; a pre-existing file is fresh only when the six-field state tuple differs. An unchanged tuple stops with `RUN_ARTIFACT_STALE` and exit `4`, so a no-op wrapper cannot reuse an earlier canonical result.

An automatic RUN created by tool `2.2.0` retains `execution_contract` with the exact effective argv, cwd, declared environment, timeout, expected/blocked exits, artifact/fresh-artifact paths, coverage, oracles, normalizations, and redactions. The runtime validates the complete object against the retained-run schema before process execution; `RUN_CONTRACT_INVALID` exits `1`, executes no GATE, and writes no RUN. Validation compares retained evidence with the current GATE and reports `RUN_CONTRACT_STALE` after any change. An older automatic RUN may omit the field for backward compatibility and does not attest those added dimensions; record a current run before relying on them. `gap-plan` requires the QA plan to be ready but does not require verified QA output. `verified-mvp`, `gap-closure`, and `closed` require current passing QA evidence.

The repository wrapper reserves `7` for capability, startup, or bounded-readiness failure. `record-run` retains stdout/stderr, records `RUN_DECLARED_BLOCK` and `BLOCKED`, skips all declared artifact acquisition, and returns `7`. For an evidenced behavior mismatch the wrapper emits the current canonical failing result and returns a nonzero code other than `7`; `record-run` retains that exact `observed_exit`, records `FAIL`, and returns `5`.

The required result artifact contains a separate outcome for UI, wire, service, persistence, every applicable supporting service, and every external disposition. It repeats the current plan digest, GATE, environment, `playwright_project`, journey IDs, and exact contract-bearing assertions/probes/postconditions. One aggregate `PASS` without those results is rejected. Copy `assets/templates-v2/full_stack_qa_result.json`, emit it at `ci.result_path`, and validate its shape against `assets/schemas/full-stack-qa-result-v1.schema.json`.

## Playwright configuration

Pin these values in both the repository configuration and the QA plan:

- exactly one supported Playwright package value—`@playwright/test`, `playwright`, or `playwright-core`—plus its declared version and the exact browser version/source;
- lockfile and configuration SHA-256 values;
- operating system, `playwright.project`, viewport, locale, time zone, color scheme, reduced-motion setting, and fonts used by visual assertions; the driver argv must select that same project and the result repeats it as `playwright_project`;
- `workers: 1`, `retries: 0`, and fail-on-flaky behavior;
- trace, screenshot, and video retention policy;
- user-facing role/label/text/test-ID locators and web-first assertions;
- the network response awaited by each triggering action;
- allowed outbound origins.

The validator hashes the named lockfile and configuration and compares those bytes with the plan, but it does not parse the lockfile or prove package/version resolution. Make the repository-owned wrapper check the locally resolved package, version, browser binary, project, and configuration before setup; exit `7` on any absence or mismatch. Do not use arbitrary time delays as readiness or completion assertions. Do not intercept an application-owned endpoint in the required lane. External stubs remain explicit exclusions from provider-behavior proof.

## Local evidence recording

After `build-ready` or `enhancement-ready` passes, execute the indexed repository gate:

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
```

The plan declares that the GATE argv is identical to the command invoked by target CI. Its attributes exactly repeat `blocked_exit_codes: [7]`, `artifact_paths`, and `fresh_artifact_paths`; the canonical result path occurs in both artifact arrays. `record-run` executes the argv without a shell and, for a non-blocked run, rejects `RUN_ARTIFACT_STALE` before retaining declared artifacts after path, file-type, hash, and redaction checks. Each emitted artifact retains its original repository `source_path`. If the wrapper returns `7`, `record-run` retains stdout/stderr as `BLOCKED`, skips declared artifacts, and does not require the not-yet-produced result. Inspect the target workflow separately because the runtime does not parse its YAML.

Run the applicable terminal validation after the required journey passes:

```bash
python3 "<skill-root>/scripts/clone_pack.py" validate "<pack>" \
  --profile verified-mvp --format json --max-problems 0
```

Use `verified-enhancement` for a brownfield workstream. The latest linked RUN for the declared gate/environment controls; absence or a latest `FAIL`/`BLOCKED` produces `HOLD`. A latest `PASS` is accepted only when its retained `ci.result_path` validates and every required journey dimension is `PASS`.

## Failure and recovery

| Observation | Recorded outcome | Recovery |
| --- | --- | --- |
| Repository wrapper preflight finds a missing Playwright package/browser/project/config, service runtime, file, startup, or readiness capability | Wrapper exits `7`; retained `BLOCKED`, exit `7` | Provision the already-authorized capability and record a new run |
| Top-level GATE executable is missing, process start fails, or timeout expires | Retained `BLOCKED`, exit `7` | Fix the declared capability or timeout contract; record a new run |
| A `fresh_artifact_paths` file has the same pre/post device, inode, size, `mtime_ns`, `ctime_ns`, and SHA-256 | `RUN_ARTIFACT_STALE`, exit `4`; no accepted RUN | Make the current wrapper invocation create or rewrite the declared result, then record a new run; do not reuse the old bytes as current evidence |
| Behavioral assertion, primary/additional wire exchange, supporting service, or external-boundary assertion fails | Retained `FAIL`, exit `5` | Fix repository behavior and record a new run |
| Workflow/config/test hash differs | QA contract failure | Review the change, update the plan and authority, recalculate the plan digest, rehash ART, rerun |
| Application-owned service is stubbed | QA contract failure | Run the real owned service or remove the full-stack classification |
| Reused core `service_id` has a different readiness/implementation declaration | `QA_SERVICE_CONFLICT` | Make the alias declaration identical or use the correct distinct service ID |
| Supporting/external result is absent, unbound, changed, or non-passing | `QA_RESULT_*` or readiness contract failure | Bind the exact ID/assertion/artifact to a journey and emit the matching result |
| External interface classification, endpoint, origin, or result echo differs | `QA_EXTERNAL_INTERFACE_INVALID`, `QA_ORIGIN_UNAUTHORIZED`, or `QA_RESULT_CONTRACT_MISMATCH` | Use a loopback endpoint or record the authorized sandbox and allowed origin; emit the exact interface in the result |
| Identity source/consumer pointer is invalid, the placeholder is missing or misplaced, or the `WIRE_PATH` is not later than the source | `QA_IDENTITY_BINDING_INVALID` or `QA_IDENTITY_BINDING_INCOMPLETE` | Correct the `BIND-###` source and controlled pointers; retain the required three consumers and rerun |
| Identity binding or consumer is non-passing, a consumer hash differs, or a concrete wire segment does not hash to the captured value | `QA_RESULT_NOT_PASS` or `QA_RESULT_CONTRACT_MISMATCH` | Preserve the mismatch, fix the gate or product behavior, and emit a new canonical result from a new run |
| Required UI, request/response, service, or persistence artifact is absent | QA contract failure | Make the gate emit the declared sanitized result artifact |
| Canonical result is missing, malformed, stale, or has a non-passing dimension | Verification block (`QA_RESULT_*`) | Preserve the run, correct the gate/result contract, and record a new run |
| Retry is configured | QA schema failure | Set retries to zero and fix the flake before accepting the required lane |
| Visual output drifts | Behavioral `HOLD` | Reproduce under the pinned renderer; approve a new baseline only with evidence and authority |

Do not delete a finalized RUN to retry it. Fix the contract or implementation and create new run evidence.

The schema enforces the `REAL` declaration but cannot inspect service internals to prove that code did not substitute a mock. Repository review and discriminating probes remain required. Likewise, a pinned workflow hash does not prove that hosted CI executed the GATE.

## Security and artifact handling

- Use `LOOPBACK` targets or a specifically `AUTHORIZED_SANDBOX` test endpoint. `production_access` remains `false`; neither classification authorizes production.
- `allowed_origins` contains HTTP(S) origins only: no credentials, non-root path, query, or fragment. A `LOOPBACK` origin resolves by literal host classification to `localhost` or a loopback IP. An `AUTHORIZED_SANDBOX` origin has at least one decision ID.
- Each non-excluded external interface echoes `protocol`, `endpoint`, and classification in the result. HTTP(S) interface origins occur in `allowed_origins`; all interfaces reject credentials and secret-like queries. Non-HTTP protocols such as SMTP use a bounded `COMMAND` readiness check.
- Use synthetic identities and records. Do not retain another user or tenant's data.
- Store secret-like environment values only as `env:NAME` references.
- Do not upload storage state, cookies, tokens, or unredacted service logs.
- Binary traces and videos cannot receive textual redaction. Exclude them when their content is sensitive and retain sanitized JSON/JUnit evidence instead.
- Keep CI permissions read-only unless another repository workflow separately authorizes a narrowly scoped write; the QA gate itself does not deploy, publish, merge, or mutate production.

## Design sources

The implemented contract uses these primary references as design bases:

- Playwright, [Best Practices](https://playwright.dev/docs/best-practices): user-visible behavior, isolated tests, resilient locators, web-first assertions, controlled data, and pinned visual environments.
- Playwright, [API testing](https://playwright.dev/docs/api-testing): server setup and postcondition checks around browser actions.
- Playwright, [Network](https://playwright.dev/docs/network): request/response observation and bounded external stubbing.
- Playwright, [Web server](https://playwright.dev/docs/test-webserver): starting and waiting for local frontend and backend servers.
- Playwright, [Continuous Integration](https://playwright.dev/docs/ci): CI execution, stable workers, reports, and containerized environments.
- Playwright, [Trace viewer](https://playwright.dev/docs/trace-viewer-intro): retained action, DOM, console, and network diagnostics.
- Playwright, [Visual comparisons](https://playwright.dev/docs/test-snapshots): renderer-sensitive screenshot baselines.
- GitHub, [Creating PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers): Linux service containers and health checks.

These sources do not certify a generated pipeline. The pack's current hashes, trace graph, GATE contract, retained RUN, and explicit claim boundary determine the result.
