# Evidence and fidelity contract

Use this reference for every clone task.

## Contents

1. Authorization record
2. Evidence ledger
3. Truth labels
4. Fidelity dimensions
5. MVP selection
6. Unknowns and stop rules
7. Safe observation rules

## Authorization record

Record the following before observing non-public behavior:

| Field | Required value |
| --- | --- |
| Product owner/requester | Named person or organization supplied by the user |
| Authorization basis | Ownership, license, engagement, or explicit permission |
| Permitted sources | Exact URLs, artifacts, accounts, environments, and documentation |
| Prohibited actions | Access-control bypass, destructive actions, production writes, or other exclusions |
| Distribution target | Local evaluation, internal use, customer deployment, or public distribution |
| Branding/assets rights | Reuse authorized, replacement required, or unresolved blocker |
| Data policy | Synthetic, redacted, or specifically authorized dataset |
| Secrets policy | Secret source and storage method; never place values in the pack |

Do not independently decide that public availability grants copying, branding, or redistribution rights. If rights are not recorded, reproduce generic behavior with replacement branding and synthetic content.

`init --source-description` stores descriptive input; it does not parse or verify a typed version or digest. A scaffold-profile result therefore makes no source-accuracy claim. For a local artifact, compute its digest with a pinned command, retain that command/output as evidence, and bind the resulting `BASE-###`/`E-###` locator before `baseline-ready`. For a directory, hash a complete sorted inventory with every governed file digest; a depth-limited listing is not a directory digest. If a description contains an incorrect assertion, abandon the unsealed draft under the exact correction rule in `pack-evolution.md` or advance the draft revision and correct every bound artifact before readiness; never preserve the assertion as verified truth.

## Evidence ledger

Assign one stable ID to each independently inspectable source or observation. Split a source into multiple entries when its version, preconditions, or confidence differ.

| Field | Rule |
| --- | --- |
| ID | `E-###`, never reused |
| Truth label | `VERIFIED`, `USER_PINNED`, `INFERRED`, or `UNKNOWN_BLOCKER` |
| Source | Exact artifact path, URL, command, capture, or user decision |
| Version | Release, commit, document version, capture date, or `not versioned` |
| Preconditions | Role, seed data, device, viewport, flags, locale, and state |
| Observation | One atomic fact; include units and ordering |
| Capture method | Reproducible steps or command |
| Confidence | `HIGH`, `MEDIUM`, or `LOW` with reason |
| Derived IDs | Requirements or decisions that consume the evidence |

Store screenshots, traces, exports, and recordings in a stable evidence directory when repository policy permits. Hash mutable artifacts. Redact secrets and personal data before storage.

## Truth labels

- `VERIFIED`: directly observed or proven by an inspectable primary artifact under recorded preconditions.
- `USER_PINNED`: explicitly selected by the authorized user where the target is silent or the clone intentionally differs.
- `INFERRED`: plausible interpretation that cannot authorize behavior. Convert it to a question, excluded note, or investigation task.
- `UNKNOWN_BLOCKER`: missing fact that prevents an exact product, security, data, or compatibility contract.

Never merge conflicting evidence silently. Record a decision with the conflict, authority order, and chosen resolution.

## Workspace-runtime evidence

Treat an installer receipt as evidence of installer output, not a signature or proof of provider ownership. A runtime exclusion is `USER_PINNED`: retain the pre-session inventory, live non-following identity, complete descendant inventory, authority ID, evidence ID, allowed operations, and both recheck results. The record does not prove provider ownership and must not describe a directory as Codex-owned, provider-authenticated, or trusted merely because its name is `.codex`, it is read-only, or it appears during a session.

Missing pre-session evidence, a legacy receipt without a complete installed inventory, an unsupported populated runtime path, or any live mismatch is `UNKNOWN_BLOCKER`. Do not inspect a blocked path for instructions, follow a symlink, suppress it from Git globally, or include it in product evidence while asking for a ruling.

## Fidelity dimensions

Give every relevant dimension one disposition and metric.

Give every indexed `SURF-###` and `WF-###` exactly one typed `attributes.disposition`:

| Disposition | Required index contract |
| --- | --- |
| `EQUIVALENT` | Non-empty `requirements`; no `gaps` or `exclusions`; at least one linked `PAR` or `RUN` record whose state is `PASS` |
| `MISSING` | Non-empty `gaps`; no `requirements` or `exclusions`; linked evidence, parity, or run evidence |
| `PARTIAL` | Non-empty `gaps`; no `requirements` or `exclusions`; linked evidence, parity, or run evidence |
| `DIVERGENT` | Non-empty `gaps`; no `requirements` or `exclusions`; linked evidence, parity, or run evidence |
| `EXCLUDED` | Non-empty `exclusions`; no `requirements` or `gaps`; non-empty authority `decisions` |
| `UNVERIFIED` | Non-empty `gaps`; no `requirements` or `exclusions`; every linked gap is a `BLOCKED` `EVIDENCE_GAP` |

Do not infer a disposition from prose, MVP membership, or the presence of an implementation path.

| Dimension | Example measurable contract |
| --- | --- |
| Behavioral | Same state transition and user-visible outcome for named workflow |
| Wire/protocol | Same method, path, schema, status, headers, ordering, and error body |
| Visual | Approved screenshot-diff threshold at named viewport and state |
| Content/data | Same field meaning and transformation; synthetic values permitted |
| Platform | Same named OS integration, permission behavior, and lifecycle event |
| Performance | Named percentile under fixed dataset, hardware, concurrency, and duration |
| Accessibility | Named WCAG level plus keyboard and assistive-technology scenarios |
| Security | Named authentication, authorization, isolation, validation, and secret boundaries |
| Operations | Named deploy, migration, backup, health, telemetry, and recovery behavior |

Use `MUST_MATCH`, `MAY_DIFFER`, or `EXCLUDED`. A `MAY_DIFFER` decision requires an exact permitted difference. An `EXCLUDED` decision requires a reason and a gap or non-goal disposition.

## MVP selection

Select a coherent vertical product slice:

1. Name primary actors and the problem solved.
2. Choose at least one complete differentiating journey per primary actor.
3. Include prerequisites, persistence, authorization, validation, failure, retry/recovery, and observable completion.
4. Include the smallest deploy/run path that lets another person execute the journey.
5. Exclude secondary journeys explicitly and assign parity gaps when evidenced.

Do not accept these as MVP completion:

- screenshots without working interaction;
- dead buttons or navigation;
- hard-coded happy-path responses presented as real behavior;
- in-memory state when persistence is in scope;
- a mock integration presented as a live integration;
- missing authorization, validation, or failure paths for an in-scope workflow;
- a test suite that asserts implementation details without proving the user-visible contract.

## Unknowns and stop rules

Ask a blocking question when one answer changes any of these:

- actor permissions or tenant/data isolation;
- destructive side effects or money movement;
- external interface compatibility;
- schema ownership, retention, or migration;
- supported platform or version;
- branding, content, dataset, or distribution rights;
- which behavior belongs inside the MVP;
- a requirement's expected observable result.

Name the affected requirement or decision ID, list the evidence already checked, and ask for one pin. Do not fill the gap with a conventional default.

## Safe observation rules

- Use ordinary authorized product interactions only.
- Do not evade authentication, paywalls, licensing, rate limits, anti-bot controls, or code protection.
- Do not probe third-party or production targets with fuzzing, load, destructive, or security tests without explicit written scope.
- Capture the minimum data needed and prefer synthetic records.
- Keep credentials out of source, prompts, screenshots, logs, and generated fixtures.
- Mark the reimplementation clearly and use a local/test domain by default.
- Record when the reference could not be inspected; do not claim parity for that surface.
