# Greenfield and scaffold contract

Use this reference when the destination contains no adopted implementation, when the approved plan explicitly creates a new project root, or when a brownfield repository needs an explicit no-scaffold disposition.

## Pin the starting state

- Record the exact destination, complete pre-edit inventory, available runtimes/toolchains, platform constraints, license policy, and repository instructions.
- For greenfield work, select exactly one audited catalog profile in `scaffold_plan.json`: `static-web-esm-allowlist`, `static-web-esm`, `python-src`, `typescript-src`, or `rust-crate`.
- Select `static-web-esm-allowlist` for every new browser-served project. This is a skill selection policy, not a schema or scaffolder distinction: both static profiles remain machine-valid because the v2 plan has no authored-before-2.3 discriminator. Its server exposes only manifest-listed product files. `static-web-esm` remains valid only for a previously authored pack that already pins it; do not select its repository-root server for new work.
- Copy the selected profile's `template`, ordered `required_paths`, and `commands` from `assets/scaffolds/catalog.json` exactly. The runtime rejects any mismatch instead of substituting catalog values or ignoring plan fields.
- For brownfield work with an adopted implementation, use only this sentinel: `profile_id: not-applicable`, `template: not-applicable`, `output_root: .`, empty `required_paths`, all-null `commands`, and `applied: false`. Preview and apply both return a no-file, non-applied disposition and do not write.
- Custom scaffolds are unsupported. If none of the five audited profiles satisfies a greenfield contract, halt on the stack decision rather than inventing a template or using the network.

## Classify session-created workspace entries

Retain two inventories: the authoritative pre-session inventory and a non-following live inventory taken before the first write. Classify every live root entry exactly once:

| Disposition | Meaning | Product treatment |
| --- | --- | --- |
| `PRODUCT_INPUT` | Authorized product or controlling request input | Include in the applicable product inventory and hashes. |
| `REPOSITORY_INSTRUCTION` | An applicable repository instruction such as `AGENTS.md` | Read as instruction and inventory separately from product behavior. |
| `TOOL_RUNTIME_EXCLUDED` | A user-authorized session entry whose pre-session absence and exact current identity are evidenced | Do not read as instructions or include in product baselines, hashes, diffs, staging, packaging, or publication. |
| `UNKNOWN_BLOCKER` | An entry without enough evidence for another disposition | Halt before writing and ask one authority question. |

Do not infer `TOOL_RUNTIME_EXCLUDED` from a path name, dot prefix, permissions, inode value, mountpoint, or enclosing read-only filesystem. Require all of the following:

1. immutable evidence of the complete pre-session inventory showing the path absent;
2. one explicit authority decision naming the exact relative path;
3. a non-following live identity and complete descendant inventory;
4. a tool-specific supported shape; tool `2.3.0` supports only an empty, real, non-writable directory;
5. an identity and emptiness recheck immediately before the first product write and at handoff.

Never delete, rename, chmod, or globally ignore a runtime entry to make a fence pass. Any appearance, disappearance, replacement, content, type, mode, or identity change is `UNKNOWN_BLOCKER`; report the evidence and stop. Product inventory and product content hashes remain separate from the retained runtime-exclusion record.

## Materialize safely

- Require every scaffold destination to be absent. The runtime has no replacement mode, even when a separate authority record proposes one.
- Create each file exclusively. If a collision or any later failure occurs, preserve pre-existing and concurrently created paths and remove every file and directory created by the failed apply.
- Audited catalog templates contain UTF-8 text files only. Render only placeholders declared by the plan; reject unreadable template content and unresolved placeholders.
- Keep the catalog skeleton dependency-free. Add a dependency only after its version, source, license, security review, purpose, and removal or upgrade path are recorded.
- Preserve neutral names and replacement branding. Do not embed the reference product's marks, secrets, endpoints, analytics IDs, or proprietary content.

## Establish the first proof

The scaffolder returns but never executes the exact command argv pinned by the selected catalog profile. Run the applicable commands separately from the recorded working directory. Prove the declared entry point starts or compiles, the smoke test exercises real behavior, invalid input fails as specified, and no undeclared network or filesystem effects occur. For `static-web-esm-allowlist`, verify that allowed GET and HEAD requests succeed and that dot paths, queries, malformed escapes, traversal, directories, symlinks, undeclared files, evidence, prompts, and repository instructions are denied without returning their bytes.

After materialization, replace scaffold assumptions with repository truth in `architecture_decisions.md`, `clone_specification.md`, and `mvp_build_plan.md`. A generated skeleton is a starting state, not evidence that an MVP requirement is implemented.
