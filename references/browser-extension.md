# Browser extension playbook

Use this playbook when the installable browser package, privileged APIs, content scripts, background lifecycle, or page integration defines the product.

## Capture and specify

- Freeze browser/version, extension build, manifest version, profile state, permissions, host grants, policy, locale, and target-site revisions.
- Inventory install/update/uninstall, toolbar and popup states, options, content-script injection, service-worker wake/suspend, messaging, storage, commands, notifications, and failure states.
- Pin manifest entries, least-privilege permissions, match patterns, CSP, message schemas, storage ownership/migration, incognito policy, network behavior, update compatibility, and store-package boundary.
- Treat inspected pages and account data as separate authorization scopes; never capture credentials or bypass site/browser controls.

## Minimum MVP and proof

Implement one complete page-to-extension journey plus permission denial and lifecycle restart. Verify package structure, install, message authorization, injection boundaries, storage persistence, worker restart, browser navigation, revoked host access, target-page change, offline behavior, accessibility, and clean uninstall. Use local fixtures for destructive or adversarial page cases.
