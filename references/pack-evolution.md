# Pack evolution and sealing contract

Use this reference when creating, updating, migrating, indexing, or sealing a clone pack.

## Identity and versions

- Preserve `pack_id` for the same evidence lineage. A different reference baseline or independently governed clone receives a new pack ID.
- Dispatch validation by the exact `schema_version`; never reinterpret a v1 document as v2. Migration creates v2 artifacts beside or from an intact source and records the source hashes, tool version, transformations, and unresolved losses.
- Run `migrate <v1-pack> --check` before writing. If it reports `ambiguous_candidates`, create a JSON object that maps every reported occurrence key to one unique target ID of the same kind, for example `{"GATE-001@mvp_build_plan.md:52":"GATE-001","GATE-001@gap_implementation_plan.md:62":"GATE-002"}`, then pass that file with `--mapping`. Missing occurrences, unknown keys, wrong-kind targets, and duplicate target IDs block migration.
- Schema versions describe artifact shape. Document revisions and baseline identifiers describe content history; do not overload either field.

## Correct an abandoned initialization draft

`init` is non-overwriting. If any initialization input or manually entered draft fact is wrong, do not retry against the same existing directory and do not edit evidence to conceal the error. Choose exactly one correction path:

1. Preferred: run `init` with the corrected inputs and a new, absent `--output-dir`. Use a new creation timestamp or corrected identity input so the corrected pack receives a distinct `pack_id`; that directory is the new lineage. Preserve the prior directory until the authority explicitly records that it is abandoned.
2. Reuse the old path only after a human explicitly declares that exact pack directory abandoned, confirms `clone_pack.json.state` is `draft`, confirms `seal.json` is absent, and preserves any evidence or history that must survive. The human may then remove only that exact pack directory with an external filesystem operation and rerun `init` with corrected inputs.

Never remove an active, sealed, migrated, or non-abandoned pack to bypass `OUTPUT_EXISTS`. The clone-pack CLI has no abandon, delete, overwrite, or in-place reinitialize operation and never deletes or replaces a destination that existed before the invocation. Its refusal leaves every pre-existing byte unchanged.

## Human validation output

For text output, a passing `scaffold` profile prints `STRUCTURAL PASS` followed by an explicit `NON-CERTIFICATION` statement. It confirms only that the scaffold-profile structural contract passed. It does not establish source accuracy, evidence readiness, specification completeness, implementation, parity, assurance, security, or release readiness. JSON output retains the stable machine contract `{"profile":"scaffold","status":"PASS",...}`; automation must use the JSON `status`, not parse the human label.

## Migration report contract

Migration writes `history/migrations/MIG-001/migration_report.json` and validates it against `assets/schemas/migration-report-v2.schema.json` before committing the destination. The report is an exact object: missing or additional fields at any declared object level are invalid. Its top-level fields are exactly `schema_version`, `migration_id`, `tool_version`, `source`, `source_files`, `preserved_record_ids`, `resolved_record_ids`, `occurrence_mapping`, `transformations`, `status_downgrades`, `unresolved_losses`, and `required_reconciliation`.

- `tool_version` records the executing clone-pack tool version. `source.tool_version` must equal it.
- `source` is the complete `clone-migration-check/v2` preflight result. Its `source_files` starts with `clone_pack.json`, then follows the v1 manifest's canonical document order; each entry contains the relative `path` and SHA-256 of the exact preflight bytes.
- `source_files` binds every retained source file with exactly `source_path`, `archived_path`, and `sha256`. The ordered `source_path` and `sha256` pairs must equal `source.source_files`. Migration copies those bytes into `history/migrations/MIG-001/source/`; a hash change between preflight and archive aborts with `MIGRATION_SOURCE_CHANGED`.
- `transformations` has contiguous sequence values `1` through `6` and exactly this operation order: `initialize-v2-scaffold`, `archive-v1-source`, `preserve-pack-lineage`, `map-v1-definitions`, `downgrade-unverified-status`, `bind-v2-identity`. Every entry records exact `inputs`, `outputs`, and `effect`; reordering, omission, or addition is invalid.
- `status_downgrades` contains one exact object per explicit v1 `VERIFIED` claim that migration cannot substantiate. Each object records `record_id`, `kind`, `source_claim`, `migrated_status`, and `reason`. Every `record_id` must occur in `resolved_record_ids`.
- `unresolved_losses` contains structured, non-free-form accounting. Sequence `1` is `LOSS-001` with category `v2-document-semantic-reconciliation`; sequence `2` is `LOSS-002` with category `trace-link-reconstruction`; when `status_downgrades` is nonempty, sequence `3` is `LOSS-003` with category `verification-evidence-reconciliation`. Every loss records `affected_record_ids`, `source_paths`, `reason`, and an executable `required_action`. Loss sequences are contiguous and loss IDs are unique.
- `required_reconciliation` is always `true`. Archived bytes and occurrence mappings preserve provenance; they do not claim that v1 prose satisfies a v2 semantic contract, reconstruct missing trace links, or preserve a v1 verification claim.

`clone_pack.json.migration` pins `migration_id`, source schema/path/manifest hash, report path/hash, tool version, retained source files, the ordered transformations, structured unresolved losses, and the status-downgrade policy. Its `source_files`, `transformations`, and `unresolved_losses` values are byte-for-byte JSON-value mirrors of the validated report fields. Any reconciliation changes occur in a successor pack revision; never rewrite the archived source or migration report.

## Exit status contract

| Exit | Meaning | Required response |
| --- | --- | --- |
| `0` | Requested operation completed and its command-level contract passed | Continue only to the next declared gate |
| `1` | Contract/schema/trace violation | Correct the named artifact; do not implement or certify |
| `2` | Invalid command argument or unsafe requested target | Correct the invocation |
| `3` | Unsupported schema/capability mode | Select a supported mode or migrate |
| `4` | Integrity, hash, seal, artifact, or path violation | Treat retained state as untrusted until reconciled |
| `5` | Honest verification `HOLD` or comparison failure | Preserve evidence and create/block the mapped gap |
| `6` | Migration ambiguity or destination failure | Resolve the reported occurrence mapping/destination |
| `7` | Required local executable, adapter, or infrastructure unavailable | Install/authorize it outside this skill or record a blocker |
| `70` | Unexpected internal error | Preserve stderr and stop; do not reinterpret it as a product result |
| `130` | User/process interruption | Inspect partial evidence directories before retrying |

## Generated records

- `clone_pack.json` is the authoritative manifest of pack identity, baseline, product type, and governed files.
- `clone_index.json` is the canonical machine-validated index of IDs and trace edges. Update its records whenever a governed definition or edge changes; the indexed document remains the semantic authority, and the locator hash binds the record to that exact definition.
- Every `CAP`, `PAR`, and `ASSURE` plan case has one same-ID index record with `attributes.case_sha256` bound to the current case contract. `CAP.environments`/`CAP.decisions` and `PAR.captures` exactly mirror their plan references.
- Run records are immutable evidence. Gap events are append-only lifecycle facts; corrections append a superseding event rather than rewriting history.
- Canonical JSON uses UTF-8, LF, sorted object keys, no insignificant whitespace, and a trailing LF when stored as a file. Hashes are lowercase SHA-256 over exact bytes.

## Trace relation vocabulary

Use only these relation names, with targets of the stated kinds:

| Relation | Legal target kinds |
| --- | --- |
| `baselines` | `BASE` |
| `blockers` | `BLOCK`, `PROVBLOCK` |
| `environments` | `ENV` |
| `artifacts` | `ART` |
| `evidence` | `E` |
| `decisions` | `DEC`, `ADR`, `GAPDEC` |
| `actors` | `ACT` |
| `requirements` | `REQ` |
| `acceptance` | `AC` |
| `tests` | `TEST` |
| `runs` | `RUN` |
| `gaps` | `GAP` |
| `exclusions` | `EXC` |
| `surfaces` | `SURF` |
| `workflows` | `WF` |
| `interfaces` | `IF` |
| `data` | `DATA` |
| `security` | `SEC` |
| `nonfunctional` | `NFR` |
| `dependencies` | `GAP`, `DEP`, `COMP` |
| `oracles` | `E`, `ART`, `CAP` |
| `gates` | `GATE` |
| `captures` | `CAP` |
| `parity` | `PAR` |
| `assurance` | `ASSURE` |
| `assets` | `ASSET`, `ART` |
| `threats` | `THREAT` |
| `controls` | `CTRL` |
| `findings` | `FIND` |
| `components` | `COMP` |
| `sboms` | `SBOM` |
| `builds` | `BUILD` |
| `provenance` | `PROV` |
| `conflicts` | `CONFLICT` |
| `scaffolds` | `SCF` |
| `stacks` | `STACK` |
| `invariants` | `INV` |
| `changes` | `CHANGE` |
| `steps` | `STEP` |
| `slices` | `SLICE` |
| `halts` | `HALT` |
| `migrations` | `MIG` |

## Seal rules

Seal only a structurally valid pack with no unresolved generator marker. The seal lists each governed relative path and digest, the manifest digest, schema/tool versions, and timestamp. Exclude the seal's own bytes from its file set. The built-in seal is an unsigned integrity manifest. When signing is required, sign the completed `seal.json` with the repository's pinned signing process and record the detached signature path, digest, identity, and verification command as `PROV-###`/`BUILD-###` evidence; do not add the signature to the seal's self-referential file set.

Any governed-file change invalidates the prior seal. Before replacement, `seal` archives the exact prior bytes at `history/seals/revision-<pack_revision>-<digest-prefix>.json`; that archive enters the new governed file set. Increment `pack_revision` and every bound document/index/plan revision when semantic content changes, validate again, and issue the successor seal. A seal must never imply implementation verification, complete parity, production readiness, or authority to redistribute.
