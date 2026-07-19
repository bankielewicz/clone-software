# Desktop and mobile client playbook

Use this playbook when installed software, local files/state, OS lifecycle, device capabilities, permissions, notifications, or platform integration define the product.

## Capture evidence

- Freeze application build, OS/device/version, architecture, locale, theme, display scale, permissions, connectivity, account/role, feature flags, and seed state.
- Inventory install, first launch, onboarding, upgrade, normal launch, deep-link/file-open, background/foreground, suspend/resume, offline/reconnect, logout, and uninstall behavior.
- Capture screens and transitions with navigation stack, focus, keyboard/controller/touch behavior, window/orientation/resizing, accessibility tree, and transient states.
- Record local storage, files, caches, credentials, synchronization, conflict resolution, notifications, device/sensor access, clipboard/share, update, and crash recovery behavior.
- Record permission requested, denied, permanently denied, revoked, and restored states.
- Do not decompile, bypass signing/licensing, or extract protected assets unless explicit rights are documented.

## Specify the clone

- Pin the supported platform/version/device matrix and package format.
- Define each screen and journey as a state machine including navigation, lifecycle interruption, local persistence, permissions, offline behavior, errors, cancellation, and recovery.
- Define local file/database schema, storage location, encryption/credential store, migration, backup/export, cache eviction, and corruption recovery.
- Define sync direction, conflict policy, retry, idempotency, background restrictions, and user-visible status.
- Define OS integrations: file associations, URLs, notifications, background tasks, services, tray/menu, share targets, sensors, camera, microphone, location, and accessibility.
- Define update compatibility, downgrade behavior, signing/notarization boundary, installer privileges, uninstall data policy, logs/crash reports, and privacy choices.
- Use replacement branding/assets unless reuse rights are recorded.

## Minimum MVP

Include install/launch, one complete primary journey, durable local or remote state as required, permission and offline/failure behavior relevant to that journey, and a reproducible package or developer run path on the pinned platform matrix.

## Verify

| Contract | Required proof |
| --- | --- |
| Install/lifecycle | Clean install, first launch, normal launch, restart, suspend/resume, upgrade, and uninstall scenarios in scope |
| Journeys/state | UI automation or exact manual procedure plus persisted state assertions |
| Permissions | Grant, deny, permanent deny, revoke, restore, and no-access data behavior as applicable |
| Offline/sync | Offline operation, reconnect, duplicate, conflict, partial transfer, retry, and recovery |
| OS integration | Deep links/files, notifications, background work, window/orientation, and device capability scenarios |
| Accessibility/UI | Keyboard/controller/touch, focus, screen reader, scaling, contrast/theme, and named visual comparisons |
| Data/security | Credential-store use, local encryption decision, file permissions, migration, corruption, and privacy checks |
| Packaging | Supported platform/architecture artifacts, startup, signing boundary, update, and clean rollback checks |

Record unavailable device/OS coverage as an unverified gap; never generalize one emulator or operating system result to the whole matrix.

