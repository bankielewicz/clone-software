# Greenfield and scaffold contract

Use this reference when the destination contains no adopted implementation, when the approved plan explicitly creates a new project root, or when a brownfield repository needs an explicit no-scaffold disposition.

## Pin the starting state

- Record the exact destination, complete pre-edit inventory, available runtimes/toolchains, platform constraints, license policy, and repository instructions.
- For greenfield work, select exactly one audited catalog profile in `scaffold_plan.json`: `static-web-esm`, `python-src`, `typescript-src`, or `rust-crate`.
- Copy the selected profile's `template`, ordered `required_paths`, and `commands` from `assets/scaffolds/catalog.json` exactly. The runtime rejects any mismatch instead of substituting catalog values or ignoring plan fields.
- For brownfield work with an adopted implementation, use only this sentinel: `profile_id: not-applicable`, `template: not-applicable`, `output_root: .`, empty `required_paths`, all-null `commands`, and `applied: false`. Preview and apply both return a no-file, non-applied disposition and do not write.
- Custom scaffolds are unsupported. If none of the four audited profiles satisfies a greenfield contract, halt on the stack decision rather than inventing a template or using the network.

## Materialize safely

- Require every scaffold destination to be absent. The runtime has no replacement mode, even when a separate authority record proposes one.
- Create each file exclusively. If a collision or any later failure occurs, preserve pre-existing and concurrently created paths and remove every file and directory created by the failed apply.
- Audited catalog templates contain UTF-8 text files only. Render only placeholders declared by the plan; reject unreadable template content and unresolved placeholders.
- Keep the catalog skeleton dependency-free. Add a dependency only after its version, source, license, security review, purpose, and removal or upgrade path are recorded.
- Preserve neutral names and replacement branding. Do not embed the reference product's marks, secrets, endpoints, analytics IDs, or proprietary content.

## Establish the first proof

The scaffolder returns but never executes the exact command argv pinned by the selected catalog profile. Run the applicable commands separately from the recorded working directory. Prove the declared entry point starts or compiles, the smoke test exercises real behavior, invalid input fails as specified, and no undeclared network or filesystem effects occur.

After materialization, replace scaffold assumptions with repository truth in `architecture_decisions.md`, `clone_specification.md`, and `mvp_build_plan.md`. A generated skeleton is a starting state, not evidence that an MVP requirement is implemented.
