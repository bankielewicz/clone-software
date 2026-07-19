# Repository agent contract

This file governs every automated or human-assisted change in this repository. Work only through capabilities available in Codex CLI and commands present in this checkout. Do not claim a command, check, remote action, or product behavior ran unless its exit status or retained result was observed.

## Test-driven development

Use the Red, Green, Refactor cycle for every behavior change:

1. Red: write and run a failing test before changing implementation or production code. The failure must discriminate the missing behavior, not an unrelated setup error.
2. Green: make the smallest implementation change that passes the new test, then run the focused test again.
3. Refactor: improve structure without changing the pinned behavior, keeping the focused test green.
4. Run the repository's broader offline gates before handoff.

Documentation or workflow-only changes still require an executable contract check when one exists. Never weaken, skip, delete, or rewrite a test merely to make an implementation pass.

## Branch, push, and pull-request boundary

- Work on a feature branch or topic branch created from the intended base. Never commit, work, or push directly on the default branch (`main`).
- Keep each commit scoped and inspect the staged diff before committing. Do not include unrelated user changes.
- Run the required gates, push the current feature branch, and create a pull request against the intended base branch with the verified commands and results in its body.
- If GitHub authentication, network access, or repository permission prevents the push or pull request, stop and report the exact failing command and diagnostic. Do not report a PR as created unless the remote returns its URL or number.
- Never merge the pull request. A maintainer owns review and merge authority.

## Repository constraints

- The runtime is Python standard-library only. Do not add package installation to local or CI verification.
- Preserve non-overwriting pack behavior, canonical JSON, safe path handling, immutable finalized evidence, and honest `PASS`, `FAIL`, `HOLD`, or `BLOCKED` results.
- Use repository-relative, non-symlinked files where a command requires governed input. Do not bypass the CLI with manual state edits to manufacture readiness, lifecycle, or seal results.
- Treat deployment, publication, production mutation, and merging as outside this repository workflow unless a maintainer gives separate explicit authority.

## Required local handoff gates

Run from the repository root:

```bash
python3 scripts/clone_pack.py --help
PYTHONDONTWRITEBYTECODE=1 python3 scripts/run_skill_tests.py
python3 -m unittest -v tests.test_capture_adversarial_security tests.test_capture_lifecycle_batch tests.test_capture_parity_contract
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tests.test_documentation
PYTHONPYCACHEPREFIX=/tmp/clone-software-pycache python3 -m compileall -q scripts tests
```

Record the exact commands and exits. A skipped or unavailable gate is not green.
