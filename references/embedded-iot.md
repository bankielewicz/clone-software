# Embedded and IoT playbook

Use this playbook when firmware, hardware interfaces, constrained devices, telemetry, control, provisioning, or over-the-air lifecycle defines the product.

## Capture and specify

- Freeze hardware revision, firmware/build, bootloader, peripherals, power/network state, calibration, clock, region, and test-fixture wiring.
- Define boot/provisioning, protocols, byte order, units, sampling, debounce, command/state transitions, offline buffering, watchdog, safe state, reset, update, and rollback.
- Pin identity, key provisioning, secure boot/update, authorization, physical-debug boundary, privacy, retention, resource budgets, and supported hardware matrix.
- Perform fault, power, radio, update, and destructive hardware tests only on owned or explicitly authorized fixtures with a recovery method.

## Minimum MVP and proof

Implement one sensor/control-to-observable-output journey on a simulator or pinned device plus safe failure behavior. Verify malformed frames, unit and clock boundaries, disconnect, buffer overflow, power loss at named points, restart recovery, denied commands, update interruption/rollback, watchdog, resource limits, and safe-state output. Do not generalize one board or simulator result to untested hardware.
