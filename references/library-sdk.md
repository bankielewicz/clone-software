# Library and SDK playbook

Use this playbook when imported symbols, types, language/runtime behavior, package metadata, extension hooks, or an SDK client define the product. Add the API/service playbook when the library communicates with a stable wire interface.

## Capture evidence

- Freeze package name, exact version/build/commit, language/runtime/compiler, operating system/architecture, dependency versions, feature flags, and fixture data.
- Inventory public modules/namespaces, exports, types, constructors, functions, methods, properties, constants, generics, protocols/interfaces, decorators/annotations, and extension hooks.
- Record call signatures, defaults, overload resolution, accepted types/coercion, return types/shapes, mutation, iteration/ordering, serialization, warnings, exceptions, and side effects.
- Capture synchronous, asynchronous, streaming, cancellation, context-manager/resource, thread/process, reentrancy, and lifecycle behavior where exposed.
- Record numeric units/precision/rounding, time/zone behavior, missing/null/zero semantics, encoding, locale, random seeding, and deterministic ordering.
- Record packaging metadata, import paths, optional dependencies/extras, version reporting, deprecations, compatibility, and platform-specific behavior.
- Use official API documentation, type declarations, authorized source, and independently constructed black-box fixtures. Do not decompile or extract protected implementation details without recorded rights.

## Specify the clone

- Define the complete in-scope public surface with exact symbol paths, signatures, type constraints, defaults, return values, mutations, warnings, exceptions, and resource ownership.
- Define state, thread safety, async scheduling/cancellation, iterator exhaustion, caching, identity/equality/hash, copy/pickle/serialization, and cleanup behavior as applicable.
- Define algorithms by observable inputs and outputs, including boundary fixtures and numeric tolerances. Do not claim internal algorithm equivalence unless authorized evidence proves it.
- Define dependency/runtime/platform matrix, package/install metadata, import-time behavior, optional feature failure, semantic-version compatibility, and deprecation policy.
- Define network, filesystem, environment, credential, logging, telemetry, and privacy side effects explicitly.
- Preserve public compatibility only for surfaces inside the pinned scope. Put every evidenced excluded public surface in the gap register.

## Minimum MVP

Implement the smallest coherent consumer workflow through real public imports, inputs, state/effects, outputs, error behavior, and packaging. Include the types and negative paths needed by that workflow. A namespace of stubs, hard-coded fixtures, or type declarations without runtime behavior is not an MVP.

## Verify

| Contract | Required proof |
| --- | --- |
| Public surface | API inventory comparison for exports, symbol paths, signatures, defaults, and type metadata |
| Behavioral parity | Differential tests against independently defined inputs and captured reference outputs |
| Errors/boundaries | Exact warning/exception type, message tolerance, timing, mutation, and cleanup checks |
| State/resources | Lifecycle, context cleanup, iterator, cache, identity, copy, serialization, and leak checks as applicable |
| Async/concurrency | Await/cancel, scheduling-visible behavior, thread/process safety, reentrancy, and race fixtures |
| Numeric/data semantics | Hand-computed boundary fixtures for units, precision, rounding, time, ordering, null, and encoding behavior |
| Packaging/compatibility | Clean-environment install/import, metadata, extras, runtime/platform matrix, and downstream consumer tests |
| Side effects/security | Filesystem/network/environment/credential/logging effects, redaction, authorization, and no-effect negative cases |

Never generate expected outputs by invoking the clone implementation. Use captured reference results, hand-computed fixtures, standards, or an independent oracle.
