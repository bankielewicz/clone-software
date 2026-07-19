# Runtime enforcement boundaries

This document records the exact claim boundaries of tool `2.1.0`. These are current implementation facts. A machine profile `PASS` proves its governed structure, links, digests, retained results, and state; it does not prove unobserved behavior, authority, production readiness, or external delivery.

## Profiles are scoped proofs

`scaffold`, `baseline-ready`, `spec-ready`, `build-ready`, `verified-mvp`, `gap-plan`, `gap-closure`, `closed`, `repository-adopted`, `enhancement-ready`, and `verified-enhancement` each enforce a different contract. Passing a later branch does not make every other branch applicable.

- Clone profiles cover the reference-versus-clone graph and the cases selected by the pack.
- Gap profiles cover retained gaps, dossiers, lifecycle, and closure evidence.
- Enhancement profiles cover one adopted repository, one bounded enhancement, its candidate state, and selected preservation, scope, assurance, and lifecycle records.

The runtime validates the records present and the minimum required by the named profile. The operator still identifies the complete applicable inventory. A missing, excluded, or unobserved external surface is not silently proven by a profile pass.

## Baseline evidence is bounded by its locator and environment

`baseline-ready` validates the governed baseline, environment, authorization, capture, and reciprocal-record contracts. It cannot authenticate a remote system, determine that a supplied artifact is legally observable, or infer that the recorded environment matches a system not exercised by a retained case.

Before a baseline claim, preserve the immutable locator or complete directory inventory, authorization basis, accounts and roles, fixtures, time/locale/device/network conditions, and required capture inventory. Report the exact baseline and environment IDs rather than calling an unnamed current system equivalent.

## Specification completeness starts with the operator's inventory

`spec-ready` validates governed requirements, acceptance, tests, oracles, evidence, parity, and bidirectional links. It cannot discover an actor, workflow, error, state transition, side effect, or compatibility consumer omitted from the pack.

Inventory applicable surfaces first. Every in-scope item then needs an evidence- or decision-backed disposition. A `spec-ready` pass supports only that recorded boundary.

## Gap closure is lifecycle proof, not deployment proof

Tool `2.1.0` requires selected closure gaps to be terminal, updates dossier closure evidence through the transition, and validates complete canonical hash-chained history. `VERIFIED` requires current run, parity, assurance, and closure evidence; `DECLINED` requires its recorded authority.

Multi-file lifecycle updates use recoverable transaction journals. After interruption, the next invocation completes an exact staged promotion only when current bytes match the journal's expected before/after state. Unexpected divergence stops the mutation. Do not edit the journal, index state, derived Markdown state, or history by hand.

A `gap-closure` or `closed` pass does not deploy code, validate a production rollout, or establish rights to distribute it.

## Successor seals prove governed bytes, not identity signing

Before editing a sealed revision, validate that predecessor while its governed files still exist. Successor sealing then requires the retained predecessor seal, validates its schema and internal manifest binding, checks its pinned seal SHA-256 and exact `supersedes` identity, enforces an increasing bound revision, and archives those exact predecessor seal bytes. It cannot revalidate predecessor file bytes after the caller has replaced them for the successor. A brownfield `verified-enhancement` seal binds the request, enhancement plan, adopted and candidate snapshots, scope, preservation baseline and regression results, assurance, and current run evidence required by that profile.

The built-in `seal.json` remains an unsigned integrity manifest. It is not a cryptographic identity signature, artifact attestation, release approval, license grant, or production approval. When signing is required, use a separately authorized and pinned repository process and retain its result as provenance outside the seal's self-referential file set.

## Assurance proves the selected case set

`assure <pack>` selects required cases. `--all` includes optional cases; repeatable `--case` selects an exact set. The runtime preflights the complete selected set, emits canonical JSON, and aggregates exits with precedence `7`, then `5`, then `0`.

The result proves only those cases under their recorded inputs, commands, environment, and artifacts. It does not install missing tools or turn an empty required set into coverage. Inspect retained per-case evidence when making a case-specific claim.

## Automated run evidence is output-bounded

`record-run` retains stdout, stderr, and declared artifacts after containment, regular-file, hash, and governed redaction checks. Missing executable, process-start failure, and timeout retain deterministic blocked evidence with infrastructure exit `7`.

The runtime can retain only output actually produced within its declared boundaries. It does not recover an external tool's hidden state, infer that an undeclared artifact exists, or make a binary artifact redactable under a textual rule.

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
