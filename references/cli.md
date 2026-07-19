# CLI playbook

Use this playbook when command grammar, streams, exit behavior, shell composition, and filesystem/network effects define the product.

## Capture evidence

- Freeze reference version/build, operating system, shell, terminal/TTY state, locale, color settings, environment, config files, working directory, permissions, and fixture tree.
- Capture global and subcommand help, version output, completion if in scope, positional/flag grammar, aliases, defaults, required combinations, mutual exclusions, and parse-error ordering.
- Capture stdout and stderr separately as raw bytes when exact compatibility matters. Record exit code, file changes, network calls, elapsed-context only when controlled, and cleanup state.
- Exercise stdin/pipes, non-TTY and TTY behavior, redirection, Unicode, quoting, spaces, empty input, invalid input, missing config, permission failure, dependency failure, interruption, and repeated invocation.
- Record config/flag/environment precedence and platform-specific paths.

## Specify the clone

- Define the complete in-scope command tree and grammar, including `--`, short-flag grouping, repeated flags, defaults, ordering, and unknown-option behavior.
- Define config discovery, formats, merge/precedence, environment variables, secret handling, and path expansion.
- Define stdout/stderr ownership, encoding, newline, color/progress/interactive rules, machine-readable formats, diagnostic wording tolerance, and exit-code table.
- Define stdin consumption, buffering/streaming, TTY prompts, confirmation, non-interactive behavior, signal handling, timeout/cancellation, and cleanup.
- Define filesystem effects, atomicity, permissions, overwrite rules, symlink behavior, temp files, idempotency, and rollback.
- Define network behavior, retries, authentication, proxy/TLS configuration, rate limits, offline mode, and partial downloads when applicable.
- Define supported OS/shell/runtime matrix, packaging/install, updates, and compatibility.

## Minimum MVP

Implement one complete useful command journey with real parsing, effects, output/error streams, exit codes, configuration needed by the journey, invalid-input behavior, interruption cleanup, and a documented install/run path. A help-only shell or hard-coded output is not an MVP.

## Verify

| Contract | Required proof |
| --- | --- |
| Grammar/help | Golden and semantic tests for command tree, flags, defaults, invalid combinations, and help/version output |
| Streams/exits | Separate raw stdout/stderr captures and exact exit assertions for success and every named failure |
| Composition | stdin pipe, stdout redirection, non-TTY, TTY, quiet/color/JSON modes, and broken-pipe behavior as applicable |
| Configuration | flag/environment/project/user/system precedence, missing/invalid config, and secret redaction |
| Filesystem | Fixture-tree diffs for create/update/overwrite, atomicity, permissions, symlinks, idempotency, and cleanup |
| Signals/recovery | Interrupt/terminate at named points with expected exit, final state, and temp/resource cleanup |
| Network | Local fake-server fixtures for requests, auth, retry, timeout, partial response, offline, and TLS/proxy rules |
| Platforms | Recorded OS/shell matrix with path, quoting, newline, packaging, and install checks |

Normalize dynamic values only when the specification names each field and normalization rule. Do not replace the whole output with a loose substring assertion.
