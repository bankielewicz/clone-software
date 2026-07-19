# Game and simulation playbook

Use this playbook when an update loop, rules engine, physics, agents, save state, or interactive simulation defines the product.

## Capture and specify

- Freeze build, platform, input devices, tick/frame settings, random seed, difficulty, content/data version, save state, and network mode.
- Define rules, state machine, coordinate/physics units, update order, collision/tie rules, randomness, scoring, AI decisions, input mapping, pause, save/load, and failure behavior.
- Separate presentation fidelity from deterministic simulation fidelity. Record asset and branding rights; use neutral replacement content by default.
- Pin multiplayer authority, prediction/reconciliation, anti-cheat boundary, persistence, mod/plugin interface, accessibility, performance, and replay format when applicable.

## Minimum MVP and proof

Implement one complete playable or simulated loop with real state transition and restart/save behavior. Verify seeded replays, boundary and tie cases, invalid inputs, pause/resume, save/load compatibility, frame-rate independence, resource exhaustion, disconnect/reconnect, accessibility controls, and prohibited future-state or nondeterministic drift.
