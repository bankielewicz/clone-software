# Security and provenance contract

Use this reference before implementation and again before any release or external handoff.

## Security assurance

- Inventory data classes, trust boundaries, identities, privileges, secrets, entry points, outbound integrations, build inputs, and administrative operations in `security_assurance.md` and `assurance_plan.json`.
- Give threats `THREAT-###`, controls `CTRL-###`, executable assurance checks `ASSURE-###`, security requirements `SEC-###`, exceptions `EXC-###`, and findings `FIND-###` identifiers. Link each control to a threat, owner, implementation locator, negative test, and evidence.
- Never reproduce an observed vulnerability, weak default, leaked credential, unsafe cryptography, or missing authorization merely for fidelity. Record the intentional security deviation and its effect on parity.
- Run static, dependency, secret, authorization, validation, and executable negative-path checks that fit the product and language. Security claims remain `UNVERIFIED` until evidence is attached.

## Supply-chain provenance

- Record every source artifact, generated artifact, dependency, toolchain, model, font, image, and fixture with origin, version, license or rights basis, digest, and transformation in `provenance_ledger.md`.
- Prefer immutable source revisions and verified downloads. Unknown origin, integrity, license, or redistribution rights blocks reuse.
- Produce an SBOM when the clone contains third-party or generated components. Record direct and transitive coverage, known omissions, generator/version, timestamp, and artifact digest.
- For a releasable artifact, bind the source revision, pack ID, external build parameters, resolved dependencies, builder identity, commands, and subject digests in verifiable build provenance.

## Release gate

`assurance_plan.json` names exact checks and required outcomes. Open findings and approved exceptions remain visible. A seal proves only the listed files and hashes; it does not replace security review, license authority, parity evidence, or artifact-signature verification.
