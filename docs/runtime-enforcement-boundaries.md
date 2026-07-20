# Runtime enforcement boundaries

This document records the exact claim boundaries of tool `2.2.0`. These are current implementation facts. A machine profile `PASS` proves its governed structure, links, digests, retained results, and state; it does not prove unobserved behavior, authority, production readiness, or external delivery.

## Profiles are scoped proofs

`scaffold`, `baseline-ready`, `spec-ready`, `build-ready`, `verified-mvp`, `gap-plan`, `gap-closure`, `closed`, `repository-adopted`, `enhancement-ready`, `implementation`, and `verified-enhancement` each enforce a different contract. Passing a later branch does not make every other branch applicable.

- Clone profiles cover the reference-versus-clone graph and the cases selected by the pack.
- Gap profiles cover retained gaps, dossiers, lifecycle, and closure evidence.
- Enhancement profiles cover one adopted repository, one bounded enhancement, its candidate state, and selected preservation, scope, assurance, and lifecycle records.

The `implementation` profile validates retained enhancement planning and baseline evidence plus lifecycle state. It deliberately omits the live adopted-snapshot equality check so authorized product edits can exist, and it returns before candidate, preservation-regression, scope, assurance, and seal validation.

The runtime validates the records present and the minimum required by the named profile. The operator still identifies the complete applicable inventory. A missing, excluded, or unobserved external surface is not silently proven by a profile pass.

## Baseline evidence is bounded by its locator and environment

`baseline-ready` validates the governed baseline, environment, authorization, capture, and reciprocal-record contracts. It cannot authenticate a remote system, determine that a supplied artifact is legally observable, or infer that the recorded environment matches a system not exercised by a retained case.

Before a baseline claim, preserve the immutable locator or complete directory inventory, authorization basis, accounts and roles, fixtures, time/locale/device/network conditions, and required capture inventory. Report the exact baseline and environment IDs rather than calling an unnamed current system equivalent.

## Specification completeness starts with the operator's inventory

`spec-ready` validates governed requirements, acceptance, tests, oracles, evidence, parity, and bidirectional links. It cannot discover an actor, workflow, error, state transition, side effect, or compatibility consumer omitted from the pack.

Inventory applicable surfaces first. Every in-scope item then needs an evidence- or decision-backed disposition. A `spec-ready` pass supports only that recorded boundary.

## Gap closure is lifecycle proof, not deployment proof

Tool `2.2.0` requires selected closure gaps to be terminal, updates dossier closure evidence through the transition, and validates complete canonical hash-chained history. `VERIFIED` requires current run, parity, assurance, and closure evidence; `DECLINED` requires its recorded authority.

Multi-file lifecycle updates use recoverable transaction journals. After interruption, the next invocation completes an exact staged promotion only when current bytes match the journal's expected before/after state. Unexpected divergence stops the mutation. Do not edit the journal, index state, derived Markdown state, or history by hand.

A `gap-closure` or `closed` pass does not deploy code, validate a production rollout, or establish rights to distribute it.

## Successor seals prove governed bytes, not identity signing

Before editing a sealed revision, validate that predecessor while its governed files still exist. Successor sealing then requires the retained predecessor seal, validates its schema and internal manifest binding, checks its pinned seal SHA-256 and exact `supersedes` identity, enforces an increasing bound revision, and archives those exact predecessor seal bytes. It cannot revalidate predecessor file bytes after the caller has replaced them for the successor. A brownfield `verified-enhancement` seal binds the request, enhancement plan, adopted and candidate snapshots, scope, preservation baseline and regression results, assurance, and current run evidence required by that profile.

The built-in `seal.json` remains an unsigned integrity manifest. It is not a cryptographic identity signature, artifact attestation, release approval, license grant, or production approval. When signing is required, use a separately authorized and pinned repository process and retain its result as provenance outside the seal's self-referential file set.

## Assurance proves the selected case set

`assure <pack>` selects required cases. `--all` includes optional cases; repeatable `--case` selects an exact set. The runtime preflights the complete selected set, emits canonical JSON, and aggregates exits with precedence `7`, then `5`, then `0`.

The result proves only those cases under their recorded inputs, commands, environment, and artifacts. It does not install missing tools or turn an empty required set into coverage. Inspect retained per-case evidence when making a case-specific claim.

## Automated run evidence is output-bounded

`record-run` retains stdout, stderr, and declared artifacts after containment, regular-file, hash, and governed redaction checks. A GATE can declare `fresh_artifact_paths`; it must be a subset of `artifact_paths`. Immediately before process execution, the runtime captures each fresh path's device, inode, size, `mtime_ns`, `ctime_ns`, and SHA-256, or its absence. After a non-blocked execution it compares the same six-field tuple. A pre-existing unchanged tuple stops with `RUN_ARTIFACT_STALE` and integrity exit `4`; an absent-before artifact or a changed tuple passes this freshness check. This detects direct reuse of unchanged evidence, not whether the emitting process computed its content honestly.

Every automatic RUN emitted by tool `2.2.0` retains `execution_contract`: exact argv, cwd, declared environment, timeout, expected and blocked exits, artifact and fresh-artifact paths, covered and oracle IDs, normalizations, and redactions. The runtime validates the complete object against the retained-run schema before process execution; invalid input exits `1` with `RUN_CONTRACT_INVALID`, executes no GATE, and writes no RUN. Validation exact-compares retained evidence with the current GATE and reports `RUN_CONTRACT_STALE` if any field changes. The run schema still accepts an earlier automatic `clone-run/v2` without this optional field for backward compatibility; such a legacy RUN is checked only against the fields it retained and does not attest the added execution dimensions. Record a new RUN before making those claims.

Missing executable, process-start failure, and timeout retain deterministic blocked evidence with infrastructure exit `7`. A declared blocked process exit, including the full-stack wrapper's fixed exit `7`, retains stdout/stderr, records `RUN_DECLARED_BLOCK`, skips declared artifact acquisition, and returns `7`.

The runtime can retain only output actually produced within its declared boundaries. It does not recover an external tool's hidden state, infer that an undeclared artifact exists, or make a binary artifact redactable under a textual rule.

## Full-stack QA proves declared vertical observations only

`plans.full_stack_qa` is an optional `clone-pack/v2` plan. When present, `build-ready` or `enhancement-ready` validates its repository file hashes, authority decisions, trace graph, CI/GATE contract, and declared artifacts. `verified-mvp` or `verified-enhancement` requires the latest linked gate/environment `RUN` to be `PASS`, then parses the retained `ci.result_path` under `clone-full-stack-qa-result/v1` and requires exact plan/GATE/environment/Playwright-project/journey identity, exact external-dependency and supporting-service sets, and passing applicable outcomes. An older v2 pack that omits this plan remains valid.

The plan requires application-owned services to be declared `REAL`: frontend, mid-tier, backend, persistence, and every declared queue, cache, or worker. Core roles may share a `service_id` only when their complete service declarations are identical. Each supporting service has readiness, assertion, artifact, journey-reference, and canonical-result contracts. It MUST NOT declare an application-owned UI, API, service, database, queue, cache, or worker as intercepted or replaced. Only an external dependency can be `SANDBOXED`, `STUBBED`, or `EXCLUDED`, and each disposition requires recorded authority. Every non-`EXCLUDED` dependency also has an exact protocol, endpoint, `LOOPBACK` or `AUTHORIZED_SANDBOX` classification, readiness, assertion, artifact, journey-reference, and result contract; the result echoes the exact interface. `LOOPBACK` requires `localhost` or a loopback IP. HTTP(S) requires an explicit matching-scheme, credential-free URL, rejects malformed percent escapes, percent-decodes the query before checking secret-like names or values, and uses an origin declared in `allowed_origins`; `AUTHORIZED_SANDBOX` remains non-production and authority-bound. An `EXCLUDED` dependency has null proof fields and a `NOT_APPLICABLE` result. The validator enforces declarations; it does not inspect service internals to detect a hidden mock or prove the external provider.

The clone-pack runtime never installs Playwright, Node packages, browser binaries, services, or operating-system dependencies. The plan's package is exactly `@playwright/test`, `playwright`, or `playwright-core`, with a declared version and pinned lockfile/configuration hashes. The validator compares lockfile bytes with the declared digest but does not parse the lockfile, so it does not prove that package or version was resolved. A target repository can run its authority-recorded restore argv from a pinned lockfile, but the skill does not execute or authorize that restore implicitly. Plan validation checks readiness shape, command environment references, and allowed HTTP origins but does not execute readiness probes. The repository-owned GATE wrapper performs executable, declared-package/version, selected-Playwright-project, browser, application, supporting-service, external-dependency, test-file, environment, and readiness preflight before behavioral work; an unavailable capability exits `7` before behavioral work.

Every journey has one or more `identity_bindings`. A `BIND-###` names a response value from `source.exchange_trigger`, its response JSON Pointer, and `string` or `integer` type. Its unique consumer JSON Pointers resolve only to controlled journey/global fields and contain the exact `{name}` placeholder once. `WIRE_PATH`, `SERVICE`, and `PERSISTENCE` consumers are mandatory; optional controlled consumers cover a supporting service, external dependency, job, or UI assertion. A global supporting-service or external-dependency consumer must target an ID referenced by the same journey. The wire placeholder occupies a complete path segment and its exchange occurs later than the source exchange. The artifact is the canonical `ci.result_path`.

The result echoes the exact source and ordered consumers, reports each as `PASS`, hashes the canonical UTF-8 captured value in `captured_value_sha256`, and repeats that hash in every consumer's `observed_value_sha256`. For each placeholder in a declared wire path, the validator URL-decodes the concrete observed path segment as UTF-8, enforces canonical integer text when applicable, and compares its SHA-256 with the captured hash. The runtime thereby rejects a changed consumer hash or unrelated concrete path ID. It validates retained evidence consistency; it does not itself extract the original JSON response, execute service/persistence checks, or prove undisclosed application control flow.

After readiness passes, run the indexed repository-owned gate without a shell:

```bash
python3 "<skill-root>/scripts/clone_pack.py" record-run "<pack>" \
  --gate GATE-001 --environment ENV-001
```

The full-stack plan fixes `ci.blocked_exit_codes` at `[7]`. Its `fresh_artifact_paths` is a nonempty subset of `artifact_paths`, contains `ci.result_path`, and exactly equals the indexed GATE attribute alongside argv, cwd, expected/blocked exits, and artifact paths. When the repository wrapper's preflight cannot run the declared lane, it exits `7`; `record-run` retains stdout, stderr, and `RUN_DECLARED_BLOCK` evidence as `BLOCKED`, skips declared artifacts, and exits `7`. A missing top-level executable, process-start failure, or timeout has the same infrastructure result. After behavioral work starts, a Playwright, product, wire, service, persistence, or assertion mismatch uses an ordinary nonzero exit; `record-run` retains it as `FAIL` and exits `5`. For non-blocked runs, unchanged fresh evidence stops with `RUN_ARTIFACT_STALE` and exit `4`; otherwise `record-run` retains declared artifacts after path, file-type, hash, and redaction checks and records each emitted artifact's repository `source_path`.

A passing full-stack gate proves only the declared UI action, the primary observed request/response and ordered additional exchanges, the reported identity-binding hashes plus concrete observed wire path segment, named API or data postcondition, persistence observation after reload, relogin, or restart, declared supporting-service assertions, declared non-excluded external-boundary assertions, the exact Playwright project, and retained environment. It does not prove unobserved mid-tier control flow, database constraints, undeclared background jobs, source-response extraction or service/persistence execution independently of the repository result, provider behavior behind a sandbox or stub, production deployment, or any undeclared browser or viewport. A screenshot, trace, capture `PASS`, or Playwright process exit alone is not full-stack proof.

The plan requires target CI to invoke the same indexed gate argv and pins the workflow bytes. The runtime does not parse CI YAML, query branch protection, or prove that a hosted check ran; verify those external facts separately. The skill repository's CI does not install or run Playwright. Neither the plan nor its run deploys, publishes, merges, or mutates production.

## Repository snapshots prove byte state, not behavior

`repo-snapshot` deterministically records or checks Git/filesystem state while excluding `.git` and the pack. An adopted/candidate hash match proves the included path inventory and bytes match the record. It does not prove those bytes compile, execute, preserve behavior, or are the version deployed elsewhere.

`baseline-run` and `regression` cover the selected `PRES` cases. `verify-scope` covers path deltas and exact allowed-change mappings. A passing preservation set does not prove an unlisted behavior; a passing scope result does not prove semantic correctness of an allowed change.

## Dirty adoption is explicit, not cleanup

`enhancement-init` rejects a dirty Git repository by default. `--adopt-dirty` binds the exact existing paths as protected input. It does not stage, commit, discard, normalize, or claim ownership of those changes. Later verification distinguishes them from the enhancement and fails on unauthorized alteration.

## Migration check does not inspect the destination

`migrate <v1-pack> --check` inventories the source and validates occurrence mapping. Destination existence, containment, source/destination relationship, and parent constraints are enforced by the write invocation. Read-only inspection can be used before the write, but only the exact write result proves the destination was accepted.

## Locator hashing normalizes line endings

The runtime reads a locator file as UTF-8 text using Python universal-newline translation, then uses normalized lines for locator hashing. Source CRLF and CR endings become `\n`; an unterminated final line has no ending byte. Raw CRLF hashes are not interchangeable with locator hashes.

## Direct authoring remains deliberate

The CLI has no generic mutation command for arbitrary requirements, decisions, gaps, capture cases, parity cases, preservation cases, or change records. Authors edit governed Markdown/JSON deliberately, then validate it. `rehash` accepts only an explicit existing record or `CAP`, `PAR`, `ASSURE`, or `PRES` result; it does not discover or create evidence.

For cold recovery, invoke `$clone-software` with the exact pack path, mode, failing command/profile, complete JSON diagnostics, authorized evidence/repository inputs, and a prohibition on deleting finalized evidence. The recovery prompt in [Troubleshooting](troubleshooting.md#skill-driven-pack-recovery) is the human entry point.

## Codex CLI and delivery boundary

The runtime imports only Python standard-library modules, executes declared no-shell argv, and performs no implicit dependency installation or network access. Codex CLI sandbox, network, and approval decisions remain authoritative for every surrounding action.

No clone-pack command deploys, publishes, mutates production, pushes Git, opens a pull request, rolls back production, or merges. Repository workflow automation and maintainers perform separately authorized delivery steps. A completed handoff is not deployed or merged.
