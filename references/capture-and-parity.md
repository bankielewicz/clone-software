# Capture and parity contract

Use this reference for every v2 pack. `capture_plan.json` defines authorized observations; `parity_plan.json` defines how those observations become independent comparison oracles.

## Contents

- Freeze the capture
- Capture adapter and lifecycle contracts
- Execute one case or a resumable batch
- Interpret capture status
- Define and execute parity
- Record outcomes and freshness

## Freeze the capture

- Record the reference release, environment, actor, data, state, locale, clock, viewport/device, feature flags, and authorization boundary before observing behavior.
- Give each capture a stable `CAP-###` ID. Human-authored artifact records use `ART-###`; runners use scoped IDs `ART-CAP-###-##`, `ART-RUN-###-##`, `ART-PAR-###-##`, and `ART-ASSURE-###-##`. Comparator-driver artifacts use `ART-PAR-DRIVER-##-##`. In these forms, `###` means at least three decimal digits and `##` means at least two. Every form has record kind `ART`. Store immutable paths and SHA-256 digests; redact secrets and private data without changing contract-bearing structure.
- Capture normal, boundary, negative, authorization, interruption, recovery, and repeated-operation states that apply to the workflow. Never run destructive, fuzz, or load probes against a reference unless that exact target and action are authorized.
- Keep raw evidence read-only. Derived crops, normalized traces, transcriptions, and summaries cite their raw artifact and record every transformation.
- A redaction is an object with exactly `pattern`, `replacement`, and `authority_ids`. The pattern is a UTF-8 regular expression; `authority_ids` is a non-empty unique array. A declared rule applies to every retained textual observation, lifecycle stream, invocation field, adapter metadata field, web summary, and web artifact. Every positive application records its location and count. If a declared rule encounters binary content, acquisition fails with `REDACTION_UNSUPPORTED` and the raw content is not promoted; pre-redact or exclude that artifact.

## Capture adapter and lifecycle contracts

Every case includes `id`, `adapter`, `side`, `environment_id`, `required`, `authorization_decision_ids`, `safe_test_environment`, `timeout_seconds`, `input`, `lifecycle`, `redactions`, and `result`; no other case fields are accepted. Adapter `input` objects are exact and accept no undocumented fields:

`verified-mvp` requires at least one required current `PASS` case for each of `reference` and `clone`, plus a required current `PASS` parity case that names those captures. An empty plan, optional-only plan, stale result, or prose `NOT_APPLICABLE` does not satisfy this gate.

At `baseline-ready`, every capture case has exactly one same-ID `CAP` index record whose `attributes.case_sha256` equals the current case contract hash. Its `environments` link exactly names the case environment. Its `decisions` links exactly name the union of case `authorization_decision_ids` and every redaction `authority_ids` entry; every target resolves to a `DEC`, `ADR`, or `GAPDEC` record before capture creates an output directory. At `spec-ready`, every parity case has one same-ID current `PAR` record whose `captures` links exactly name its reference and clone `CAP` cases/records and whose `decisions` links exactly name every normalization `authority_ids` entry. Every normalization authority also resolves to `DEC`, `ADR`, or `GAPDEC` before parity creates output. At `build-ready`, every assurance case has one same-ID current `ASSURE` record. Plan edits require counterpart hash updates before execution.

- `http`: `{"method": "GET", "url": "https://...", "headers": {"Authorization": "env:REFERENCE_AUTH"}}`, optionally with `body_base64`. The URL must be absolute HTTP(S). Userinfo is forbidden. Query names matching `token`, `access_token`, `api_key`, `key`, `secret`, `password`, `auth`, or `authorization`, case-insensitively, are rejected before network or output. Values for `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, and `X-API-Key` must be `env:NAME`; raw values and missing, empty, invalid, or control-bearing resolved values are rejected. A reference request carrying any of those credential headers requires at least one resolved `authorization_decision_ids` entry before credential resolution or network access. A reference method other than `GET`, `HEAD`, or `OPTIONS` additionally requires `safe_test_environment: true`. Resolution is transient. Sensitive headers are always retained as `[REDACTED]`; declared regex rules redact other retained fields and values. Redirect following is disabled: a 3xx response is captured as the terminal response with `redirect_policy: disabled`, so validation cannot be bypassed by a redirect target.
- `process`, `cli`, or capture adapter `custom`: `{"argv": ["executable", "arg"], "cwd": ".", "environment": {"API_TOKEN": "env:CLONE_API_TOKEN"}}`, optionally with `stdin_base64`. `argv` is invoked directly with no shell. `cwd` is `.` or a safe relative path beneath the pinned repository. Environment names use the portable `[A-Za-z_][A-Za-z0-9_]*` form; undeclared environment values are not inherited except the minimum launch variables added by the runner. If an environment key contains `TOKEN`, `KEY`, `SECRET`, `PASSWORD`, `AUTH`, `COOKIE`, or `CREDENTIAL` as a case-insensitive substring, its value must be `env:NAME`. All `env:NAME` values are resolved transiently; raw sensitive, missing, empty, malformed, or control-bearing values fail before output and are never written to the plan result or process metadata.
- `filesystem`: `{"path": "."}` or one safe relative path beneath the pinned repository. The result is a non-following, hashed filesystem snapshot; it does not copy file contents.
- `manual`: `{"source_path": "evidence/raw/authorized-file.bin"}` naming one direct, non-symlink, safe relative regular file beneath the pack. The runner copies it to the isolated `manual/` observation namespace and applies declared UTF-8 redactions. Source basenames therefore cannot overwrite runner metadata.
- `web`: `{"driver_argv": ["installed-driver", "arg"], "cwd": ".", "environment": {"SESSION_TOKEN": "env:WEB_SESSION_TOKEN"}}`. It uses the same local argv, cwd, environment-secret indirection, authorization, timeout, and no-install behavior as process capture. The runner adds `CLONE_CAPTURE_OUTPUT`, which names an isolated `web/` namespace. The driver must retain at least one declared regular observation artifact; its files cannot overwrite root runner metadata.

`body_base64` and `stdin_base64`, when present, are padded RFC 4648 base64. Safe relative paths reject absolute, drive-prefixed, backslash, empty-segment, `.`-segment, `..`-segment, and control-character forms. Schema and secret-input checks run before an evidence or parity output directory is created.

Every case also carries an exact lifecycle object:

```json
{
  "setup": {
    "argv": ["python3", "fixtures/reset.py", "ready"],
    "cwd": ".",
    "environment": {},
    "expected_exit": 0,
    "timeout_seconds": 30
  },
  "teardown": null
}
```

Both `setup` and `teardown` are required and each is either `null` or one command. A command contains exactly `argv`, `cwd`, `environment`, `expected_exit`, and `timeout_seconds`, plus optional `stdin_base64`. The runner invokes `argv` directly without a shell, applies the process capture path, environment, secret-indirection, and base64 rules, and inherits no undeclared environment other than minimum launch variables.

The runner starts setup before the adapter and runs the adapter only when setup exits exactly `expected_exit`. It attempts teardown after the adapter and after every setup failure, including an infrastructure failure. It retains each executed phase as `lifecycle/<phase>/invocation.json`, `stdout.bin`, and `stderr.bin`; `summary.lifecycle.setup` and `summary.lifecycle.teardown` carry the phase summaries. `summary.failure_phase` names `setup`, `adapter`, `teardown`, or the combined failed phases. If any failed lifecycle or adapter phase is an infrastructure failure with exit `7`, the capture status is `BLOCKED`; otherwise any phase failure makes it `FAIL`. Only a fully successful setup, acquisition, and teardown is `PASS`. Treat a reference-side lifecycle command as a reference-side process: mutating commands require a traced authorization decision and `safe_test_environment: true` on the case.

## Execute one case or a resumable batch

Use exactly one selector:

```bash
python3 <skill-root>/scripts/clone_pack.py capture <pack> --case CAP-001
python3 <skill-root>/scripts/clone_pack.py capture <pack> --case CAP-001 --resume
python3 <skill-root>/scripts/clone_pack.py capture <pack> --all
python3 <skill-root>/scripts/clone_pack.py capture <pack> --all --resume
```

`--case` and `--all` are mutually exclusive. `--resume` is valid with either selector and safely resumes that selected set. Batch execution sorts cases lexically by capture ID, preflights the entire selected set before starting any case, continues through acquisition `FAIL` and `BLOCKED` results, and emits one `clone-capture-batch-result/v2` object with offset-bearing UTC `started_at` and `completed_at` values plus results in that same lexical order. The batch exits zero only when every selected or resumed result is current and `PASS`.

Preflight resolves every declared adapter and lifecycle executable, working directory, manual source, filesystem root, base64 field, authorization trace, secret indirection, and destination before setup begins. Lifecycle commands may create or reset target state and fixtures inside roots that already exist at preflight. A lifecycle command may not create a selected case's declared executable, working directory, manual source, or filesystem root; declare those prerequisites before invoking capture.

For each case, the runner writes first to `evidence/captures/.<CASE>.staging` and creates `.clone-capture-staging.json` as runner-ownership provenance. The pack manifest paths are exact: `index_path` is `clone_index.json`; plans are `capture_plan.json`, `parity_plan.json`, `scaffold_plan.json`, and `assurance_plan.json`. Remapping or symlinking those files is rejected by executable commands. `evidence/` and `evidence/captures/` must be real in-pack directories with no symlink component. Before promotion, the runner rejects every symlink, multiply-linked or non-regular artifact, undeclared file or directory, missing declared file, and runner-name collision. A finalized capture contains offset-bearing UTC `started_at` and `completed_at`; the interval begins before setup and ends after teardown immediately before the terminal manifest is written. The runner atomically promotes a complete staging directory to `evidence/captures/<CASE>`. The ownership marker remains in the final directory and is validated by resume, but is excluded from comparison artifacts so runner provenance cannot create a reference-versus-clone mismatch. A staging directory is never evidence and a final directory is never overwritten.

`--resume` skips every final result whose manifest, case hash, pack identity, repository identity, and retained artifact digests are current, regardless of whether its status is `PASS`, `FAIL`, or `BLOCKED`; a skipped non-`PASS` result still returns nonzero. When the plan already has a result pointer, its object must exactly equal the canonical final manifest path, retained status, and current manifest SHA-256 before resume removes staging or writes the plan. After successful selected-set preflight, resume deletes only an incomplete real directory whose marker proves that the current runner owns that exact case staging path, and only on a platform with symlink-safe recursive removal. An invalid or stale final result, an absent or invalid marker, a symlink, or any unowned staging path blocks the selected execution before its first case. Assign a new capture ID to acquire replacement evidence and retain the prior final result; never delete or overwrite finalized evidence to manufacture a retry.

A web driver must write `web-driver-result.json` into `CLONE_CAPTURE_OUTPUT` with exactly this shape:

```json
{
  "schema_version": "clone-web-capture-result/v1",
  "artifacts": ["screenshot.png"],
  "summary": {}
}
```

`artifacts` is a non-empty unique array of safe relative regular-file paths beneath that output directory. It may not claim `web-driver-result.json`. The runner retains and hashes the root process metadata, stdout, stderr, sanitized web result, and every declared artifact. Undeclared files, symlinks, non-regular files, missing artifacts, and binary artifacts under an active redaction rule reject promotion. A missing executable is `CAPABILITY_MISSING`; missing or malformed output is `CAPTURE_DRIVER_INVALID`. The runner never installs the driver.

## Interpret capture status

The top-level capture `status` reports evidence acquisition, not whether the observed product behavior is successful or correct:

- `PASS`: the adapter completed and retained its declared observation artifacts. This does not interpret an HTTP status, process exit code, response body, stderr, or product state.
- `FAIL`: evidence acquisition began but violated a capture/redaction/adapter contract. The retained summary names the diagnostic; do not treat it as a product failure.
- `BLOCKED`: a required executable, authorized target, timeout boundary, or other acquisition infrastructure was unavailable. The retained summary names the blocking diagnostic.
- A schema, authorization-trace, secret, or other preflight rejection occurs before the output directory is created and therefore creates no capture result.

Read the observed product outcome from the adapter summary and retained artifacts. For `process`, `cli`, and capture `custom`, `summary.exit_code` is the observed process exit. For `http`, `summary.status` is the observed HTTP status. For `web`, `summary.exit_code` is the driver exit and `summary.web` is the driver's declared observation summary. Filesystem and manual captures describe acquisition metadata in `summary`; their observed state is in the retained artifact.

For example, this is a successful capture of a product's expected missing-record outcome, not a passing product exit:

```json
{
  "adapter": "cli",
  "status": "PASS",
  "summary": {
    "argv": ["inventory", "get", "missing"],
    "cwd": ".",
    "exit_code": 3
  }
}
```

Acceptance and parity logic may later establish that exit `3` is the required product behavior. Capture `PASS` establishes only that the exact exit and associated bytes were acquired and retained.

## Define parity before implementation

- Give each comparison a stable `PAR-###` ID and map it to evidence, requirements, acceptance criteria, and tests.
- Pin the comparator, inputs, preconditions, ignored fields, normalization rules, numeric or visual tolerance, expected result, and mismatch artifact before using it as a gate.
- Compare reference and clone under equivalent preconditions. A normalization may remove only named nondeterministic fields; it may not erase an unexplained mismatch.
- Generate expected values independently of the clone. Clone-produced snapshots, responses, or fixtures are not reference oracles.

Every parity case pins `options`. Use `{}` for `exact`, `text`, `json`, `filesystem`, `dom`, and `accessibility`. The other comparator contracts are exact:

- `http`: `{"json_artifact_names": [...]}`. `http.json` is always compared as semantic JSON. Each listed artifact name, including an extensionless `response.body`, is also compared as semantic JSON; every other body is compared byte-for-byte. A listed name must exist on both sides.
- `performance`: `{"absolute_tolerance": A, "relative_tolerance": R}` with finite non-negative numbers. Numbers match when `abs(reference - clone) <= max(A, R * max(abs(reference), abs(clone)))`; object keys, array lengths/order, booleans, strings, and nulls remain exact.
- `perceptual-image`: a local comparator driver plus a finite non-negative `threshold`. The driver reports `distance`; the runner decides pass/fail using `distance <= threshold`.
- `custom`: a local comparator driver that reports a boolean `equal` result. Use it only when none of the built-in comparator contracts expresses the oracle.

A normalization is never a string. It is either an authorized `json-pointer-remove` object with `artifact_names`, `path`, `reason`, and `authority_ids`, or an authorized `regex-replace` object with `artifact_names`, `pattern`, `replacement`, `reason`, and `authority_ids`. Artifact scoping is mandatory. Missing paths, invalid regular expressions, wrong rule shapes, and rules unsupported by the selected comparator fail deterministically; a rule does not silently become a no-op.

## Optional comparator driver contract

`perceptual-image` and `custom` require `options` with exactly `driver_argv`, `artifact_pairs`, `cwd`, `environment`, and `timeout_seconds`; perceptual comparison additionally requires `threshold`. Each artifact pair has exactly `reference_name` and `clone_name`. `cwd` resolves inside the pinned repository. Comparator-driver `environment` uses the same portable names and secret-like-key `env:NAME` indirection contract as process capture; resolution is transient and the resolved value is not written into the parity result or invocation metadata. The runner invokes `driver_argv` directly with `shell=false`, passes only the resolved declared environment plus minimum process-launch variables, and never downloads or installs a driver.

For each pair, the runner sets `CLONE_PARITY_COMPARATOR`, `CLONE_PARITY_EXPECTED_PATH`, `CLONE_PARITY_ACTUAL_PATH`, `CLONE_PARITY_RESULT_PATH`, and `CLONE_PARITY_OPTIONS_JSON`. The driver writes this strict result to `CLONE_PARITY_RESULT_PATH`:

```json
{
  "schema_version": "clone-comparator-result/v1",
  "equal": true,
  "details": [],
  "artifacts": []
}
```

For `perceptual-image`, replace `equal` with a finite non-negative `distance`. `details` is a string array. `artifacts` contains relative paths beneath that pair's driver output directory. Stdout, stderr, invocation metadata, the result, and declared artifacts are retained and hashed. A missing executable is `CAPABILITY_MISSING`; a non-zero exit is `COMPARATOR_DRIVER_FAILED`; malformed or missing result data is `COMPARATOR_DRIVER_INVALID`.

## Record outcomes

Each immutable run records `RUN-###`, pack and baseline identity, implementation revision, tool version, exact command or procedure, timestamps, exit status, produced artifact digests, and comparison outcome. Its `result` is exactly `PASS`, `FAIL`, `BLOCKED`, or `ERROR`. `NOT_RUN` is only a plan case or index state meaning no immutable run exists. Retain mismatches as evidence and link them to a gap or blocker.

Executable `GATE` records use the same environment contract: `attributes.environment` is a string map, any secret-like key must contain an `env:NAME` reference, and `record-run` resolves it only for the child process. Raw sensitive, missing, empty, malformed, or control-bearing values reject the run before its output directory is created. Run evidence records the gate contract hash and command, never the resolved environment value.

Every capture and parity result records `case_sha256`, the SHA-256 of canonical JSON for that current plan case with only its mutable `result` member excluded. Reference captures store `clone_revision: null` and `clone_diff_sha256: null`. Clone captures and parity results store the manifest's exact current repository revision and working-tree diff SHA-256. Parity refuses capture evidence whose case hash, reference baseline, clone revision, or clone diff no longer matches. Pack validation applies the same freshness checks and rejects a retained `PASS` after any input, authorization, redaction, normalization, comparator, option, tolerance, repository, or other contract field changes; recapture and rerun instead of reusing stale evidence.

Parity is dimension-specific. Passing a behavior comparison does not establish visual, wire, performance, accessibility, security, or operational parity unless those dimensions have their own comparisons and tolerances.
