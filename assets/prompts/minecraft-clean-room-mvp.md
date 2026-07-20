# Codex build request: clean-room voxel sandbox MVP

Use `$clone-software` in `mvp-build` mode. Read this file completely before running commands or writing files. Treat this file as the controlling request record. Execute the workflow through the installed skill and its deterministic CLI; do not replace the workflow with an informal implementation.

## 1. Authority, source, and claim boundary

- Requester: Local Codex skill evaluator.
- Authorization basis: the requester authorizes creation of new, original software implementing only the behavior pinned in this request.
- Reference baseline: the exact UTF-8 bytes of `MINECRAFT_CLONE_PROMPT.md` in the current workspace. Hash this file with SHA-256 before the first product-code edit and retain the command, digest, and file bytes as immutable `USER_PINNED` evidence.
- Reference-product wording: “Minecraft-inspired” identifies a broad voxel-sandbox genre. It is not evidence of target behavior and grants no copying authority.
- Permitted sources: this request; the installed `clone-software` contracts, schemas, templates, and scaffold catalog; and primary browser standards or MDN documentation needed to confirm WebGL 2, Pointer Lock, Web Storage, keyboard, mouse, and animation-frame APIs.
- Prohibited sources and actions: do not inspect, download, decompile, extract, capture, or reuse a Minecraft or Mojang executable, website, protocol, save, source, asset, data file, documentation page, screenshot, video, skin, map, server, or account. Do not bypass any access control. Do not send traffic to a third-party game or service.
- Rights boundary: No Mojang or Minecraft source code, binaries, assets, textures, audio, fonts, logos, names, or trade dress are authorized. Generate original geometry, solid colors, UI, prose, identifiers, and synthetic world data.
- Product-facing naming: use `Voxel Sandbox MVP` as the display name and `voxel-sandbox-mvp` as the package name. Product-facing code, UI, metadata, screenshots, and filenames MUST NOT contain `Minecraft` or `Mojang`. The immutable controlling request filename `MINECRAFT_CLONE_PROMPT.md` is the sole filename exception: retain that existing file unchanged as provenance, do not copy that name to another filename, and do not present it as a product artifact. Provenance evidence MAY retain this request verbatim inside governed evidence content and metadata.
- Distribution: local evaluation only.
- License: copy the canonical CC0 1.0 Universal text from `.agents/skills/clone-software/LICENSE` into product-root `LICENSE`; record `SPDX-License-Identifier: CC0-1.0` in the product README. The dedication applies only to newly generated original material.
- Data: synthetic procedural world state only.
- Secrets: none. Do not add environment variables, credentials, analytics identifiers, telemetry, cookies, or user tracking.
- Fidelity claim: every product requirement below is `USER_PINNED`. The build MAY claim conformance only to these requirements. It MUST NOT claim parity with Minecraft, target visual fidelity, target save compatibility, or behavior that was not observed and retained.

## 2. Workspace and execution boundary

The current working directory is the product repository root. Its permitted initial entries are:

```text
.agents/
MINECRAFT_CLONE_PROMPT.md
.git/                         optional
```

Before any write:

1. List the complete root inventory, including dotfiles.
2. If any other entry exists, HALT with blocker `REPO-001`, list the paths, and ask whether those paths belong to the new product. Do not overwrite or delete them.
3. Resolve the installed `clone-software` root from `.agents/skills/clone-software`; read the required greenfield, evidence, document, game-simulation, security/provenance, and pack-evolution contracts.
4. Record exact `git`, `node`, `npm`, and `python3` executable paths and versions. Require Python 3.10 or later and Node.js 18 or later. If a required executable or version is unavailable, HALT with `ENV-BLOCK-001`; do not install it.
5. Read `.agents/skills/clone-software/assets/scaffolds/catalog.json`. Select exactly `static-web-esm`. If that live profile differs from the required paths and commands below, HALT with `STACK-BLOCK-001`; do not substitute a stack.

Local Git initialization and local commits are authorized if `.git/` is absent. Add `.agents/` to `.gitignore`. Do not configure or add a remote. Do not fetch, push, open a pull request, publish, deploy, or bind a server beyond `127.0.0.1`.

No dependency installation is authorized. Do not change this boundary to unblock browser automation. The product has zero runtime dependencies and zero development dependencies.

## 3. Product and scaffold contract

- Product type: `game-simulation`.
- Playbook: `game-simulation`.
- Clone-pack output: `docs/clone`; it MUST be absent before initialization.
- Scaffold profile: exactly `static-web-esm`.
- Scaffold output root: `.`.
- Scaffold template, required paths, and commands: copy them exactly from the live `static-web-esm` catalog entry.
- Catalog setup command: `null`.
- Test command at scaffold time: `npm test`.
- Run command: `npm start`, which remains exactly `python3 -m http.server 8000 --bind 127.0.0.1`.
- The full-stack QA disposition: `NOT_APPLICABLE`. This MVP has no mid-tier, application-owned backend, service API, database, or server-side persistence layer. Do not create `full_stack_qa_plan.json` and do not label a browser-only or static-server check full-stack.

Apply the scaffold only after the pack passes `build-ready`. Preserve these catalog paths:

```text
README.md
package.json
index.html
styles.css
src/app.js
tests/smoke.test.mjs
```

Add only these product/test paths unless a generated clone-pack artifact requires its governed path:

```text
LICENSE
.gitignore
src/config.js
src/input.js
src/math.js
src/raycast.js
src/renderer.js
src/simulation.js
src/storage.js
src/world.js
tests/contract-probe.mjs
tests/fixtures/contract-oracle.json
tests/http_smoke.py
tests/mesh.test.mjs
tests/raycast.test.mjs
tests/renderer.test.mjs
tests/simulation.test.mjs
tests/static-contract.test.mjs
tests/storage.test.mjs
tests/world.test.mjs
docs/clone/
```

Update the catalog-created `package.json` so `scripts.test` is exactly `node --test tests/*.test.mjs`. Keep `scripts.start` unchanged. The file MUST contain neither `dependencies` nor `devDependencies`, and no lockfile is generated.

## 4. Deterministic world contract

Use right-handed world coordinates measured in blocks. `+Y` is up. Valid cell coordinates are integers:

```text
0 <= x <= 31
0 <= y <= 15
0 <= z <= 31
```

The only block values are `air`, `meadow`, `soil`, `rock`, and `timber`. `air` is non-solid; all other values are solid. The default seed is the integer `1337`.

Define positive modulo as a remainder in `[0, divisor - 1]`. The inclusive surface height is:

```text
h(x, z) = 4 + positive_mod(1337 + 13*x + 17*z, 5)
```

Freeze these independently computed oracle samples before implementing `world.js`:

| Coordinate | Required height |
| --- | ---: |
| `(0, 0)` | `6` |
| `(1, 0)` | `4` |
| `(0, 1)` | `8` |
| `(31, 31)` | `6` |
| `(16, 16)` | `6` |

For each `(x,z)` column:

- `y == h(x,z)` is `meadow`;
- `h(x,z)-2 <= y < h(x,z)` is `soil`;
- `0 <= y < h(x,z)-2` is `rock`;
- `y > h(x,z)` is `air`.

Cells outside the valid coordinate range return `air` for rendering and ray queries. For player collision only, `x < 0`, `x > 31`, `z < 0`, `z > 31`, and `y < 0` are solid world boundaries. `y >= 16` is open air.

Store only deviations from the generated baseline. Reverting a cell to its baseline value removes its deviation. Permit at most `4096` distinct deviations. Reject a mutation that would create deviation `4097` with exact visible status `World edit limit reached (4096).`; do not change the world, dirty flag, or stored bytes.

## 5. Player, clock, movement, and collision contract

Initial player feet position is `(16.5, 7, 16.5)`. Initial velocity is `(0, 0, 0)`, initial grounded is `true`, the fixed-step accumulator is `0`, all held-input flags and pending jump are false, and selected block is `meadow`. Initial yaw is `0` radians facing `-Z`; pitch is `0` radians.

After every mouse-look or keyboard-look update, normalize yaw with this exact operation, where positive modulo returns a value in `[0, divisor)`:

```text
yaw = positive_mod(yaw + 3.141592653589793, 6.283185307179586) - 3.141592653589793
```

The runtime yaw domain is therefore `[-3.141592653589793, 3.141592653589793)`, and an update landing on positive pi produces negative pi. Clamp pitch after applying each look update. Ignore a look delta containing a nonfinite number without changing yaw, pitch, application state, or visible status.

The player collision shape is an axis-aligned box with width `0.6`, depth `0.6`, and height `1.8` blocks. The eye is `1.62` blocks above the feet. A player box touching a block face without positive overlap is not intersecting.

Use these constants:

| Setting | Exact value |
| --- | ---: |
| fixed simulation step | `1/60` second |
| Maximum accepted render-frame delta | `0.25` second |
| Maximum fixed steps per render frame | `15` |
| Horizontal speed | `4.0` blocks/second |
| Gravity | `-20.0` blocks/second squared |
| Terminal downward speed | `-30.0` blocks/second |
| Jump velocity | `6.5` blocks/second |
| Mouse sensitivity | `0.002` radians/pixel |
| Keyboard-look speed | `1.5707963267948966` radians/second |
| Minimum/maximum pitch | `-1.5533430342749532` / `1.5533430342749532` radians |

Clamp each render-frame delta to `[0, 0.25]`, add it to an accumulator, and execute fixed steps while the accumulator is at least `1/60`, capped at 15 steps. Discard any residual whole steps beyond that cap and retain only the fractional remainder below `1/60`. Rendering reads state but does not mutate simulation state.

Derive raw movement axes as `forwardAxis = (W ? 1 : 0) - (S ? 1 : 0)` and `rightAxis = (D ? 1 : 0) - (A ? 1 : 0)`, so each opposite-key pair cancels exactly. Horizontal forward is `(sin(yaw), 0, -cos(yaw))` and horizontal right is `(cos(yaw), 0, sin(yaw))`; pitch never changes movement direction. Form `forwardAxis * forward + rightAxis * right`, normalize it only when its length exceeds `1`, then multiply by horizontal speed.

Every fixed step uses `dt = 1/60` and performs exactly this order:

1. Compute the normalized horizontal intent from the held-key snapshot and assign `velocity.x` and `velocity.z` to intent times `4.0`; absent/cancelled intent assigns both to `0`.
2. If `pendingJump` is true and `grounded` is true, assign `velocity.y = 6.5` and assign `grounded = false`. Otherwise leave `velocity.y` unchanged at this stage.
3. Assign `pendingJump = false` unconditionally, so an airborne or accepted jump request is consumed by this step and cannot fire later.
4. Apply gravity once as `velocity.y = velocity.y + (-20.0 * dt)`, then clamp once as `velocity.y = max(velocity.y, -30.0)`.
5. Assign `grounded = false` before integration.
6. Integrate and resolve `X` using displacement `velocity.x * dt`, then integrate and resolve `Z` using the possibly updated position and `velocity.z * dt`, then integrate and resolve `Y` using the possibly updated position and `velocity.y * dt`.
7. At each collision, move flush to the contacted face and zero only that axis velocity. Only a downward `Y` collision assigns `grounded = true`; upward and horizontal collisions leave it false.

Thus an accepted jump from exact initial state finishes its first unobstructed step with `velocity.y = 6.166666666666667`, feet `y = 7.102777777777778`, `grounded = false`, and `pendingJump = false` before 12-decimal oracle normalization. Jump is accepted only on the first non-repeating Space keydown rising edge while grounded. Spawn recovery tests candidate feet `(x, min(originalY+n,16), z)` for integer `n = 1, 2, ...`, in order, stopping after candidate feet `y=16` is tested once; use the first nonintersecting candidate. If none exists, enter a fatal state with exact status `No safe spawn position is available.`

Pausing clears held inputs, pending jump, and the fixed-step accumulator. Simulation state MUST remain byte-equivalent across ticks while paused.

## 6. Inputs and interaction contract

Controls:

| Input | Action |
| --- | --- |
| `W`, `A`, `S`, `D` | Move forward, left, backward, right |
| Space | Jump when grounded |
| Mouse movement | Look while pointer lock is active |
| Arrow keys | Keyboard look while playing |
| Left mouse button or `F` | Break the first eligible hit block |
| Right mouse button or `G` | Place the selected block in the air cell immediately before the hit |
| `1`, `2`, `3`, `4` | Select `meadow`, `soil`, `rock`, `timber` respectively |
| Mouse wheel | Cycle the same four block types with wraparound |
| `P` | Pause |
| Escape or pointer-lock loss | Pause |

While `PLAYING`, apply one mouse event as `yaw += movementX * 0.002` and `pitch -= movementY * 0.002`, so positive `movementX` turns toward `+X` from initial view and positive `movementY` looks downward. During each fixed step, compute `yawLookAxis = (ArrowRight ? 1 : 0) - (ArrowLeft ? 1 : 0)` and `pitchLookAxis = (ArrowUp ? 1 : 0) - (ArrowDown ? 1 : 0)`; each opposite Arrow pair therefore cancels exactly. Add each axis times keyboard-look speed times `1/60`. A nonfinite mouse component invalidates the complete mouse event. Clamp pitch and normalize yaw after each applied mouse event or fixed-step Arrow update.

For `W`, `A`, `S`, `D`, and Arrow keys, keydown sets one held flag and repeated keydown is idempotent; keyup clears that flag. For Space, `F`, `G`, `P`, and `1` through `4`, ignore any keydown whose `repeat` is `true`. One non-repeating `F` or `G` keydown performs at most one edit attempt. One non-repeating number key selects exactly its table block and sets `status` to `Selected meadow.`, `Selected soil.`, `Selected rock.`, or `Selected timber.` respectively. Selecting the already-selected block sets the same exact status but does not change dirty state or stored bytes; changing selection sets dirty state but does not automatically save. On the canvas while `PLAYING`, one wheel event with finite `deltaY > 0` advances `meadow -> soil -> rock -> timber -> meadow`; finite `deltaY < 0` moves in the reverse order; zero or nonfinite `deltaY` is ignored byte-identically. Wheel magnitude never advances more than one slot. A successful wheel selection uses the same exact `Selected <block>.` status and dirty rule as a number key.

Use a grid DDA ray from the eye in the look direction with inclusive maximum reach `5.0` blocks. Validate and normalize the complete direction before inspecting the origin cell; a zero or nonfinite direction is invalid and produces no hit. The origin cell is `(floor(eye.x), floor(eye.y), floor(eye.z))`. If that origin cell is solid, return exactly `hitCell = originCell`, `precedingAirCell = null`, `distance = 0`, and `enteredFaceNormal = (0, 0, 0)` without advancing the DDA. Otherwise, when boundary crossing times tie, traverse axes in exact order `X`, then `Y`, then `Z`. On a later hit, return the hit cell, the immediately prior traversed air cell, hit distance, and entered face normal: stepping `+X/-X/+Y/-Y/+Z/-Z` yields normal `(-1,0,0)/(1,0,0)/(0,-1,0)/(0,1,0)/(0,0,-1)/(0,0,1)` respectively. A hit at distance exactly `5.0` is eligible; a hit beyond it is not.

The `status` element is the operational-status surface. Break and place set it to exactly one of these values:

| Outcome | Exact `status` text |
| --- | --- |
| eligible block successfully replaced with `air` | `Block removed.` |
| selected block successfully placed | `Block placed.` |
| ray has no hit within reach, including a zero or nonfinite direction | `No block is in reach.` |
| break hit has `y == 0` | `The foundation layer cannot be removed.` |
| placement cell is outside the valid cell bounds | `Cannot place outside the world.` |
| placement cell is in bounds but is not `air` | `Placement cell is occupied.` |
| placement cell positively overlaps the player box | `Cannot place a block inside the player.` |
| preceding air cell is absent because the ray starts in a solid cell | `No placement cell is available.` |

Breaking replaces the hit cell with `air`. Placing writes the selected solid type to the preceding air cell. Evaluate placement rejection precedence exactly in this order: missing preceding cell, outside bounds, non-`air`, then player intersection. A rejected action changes neither world state, mutation revision, dirty state, nor stored bytes. A successful action retains its exact operational status even when its automatic persistence attempt also runs; persistence reports only through `save-state`.

While application state is not `PLAYING`, ignore `W`, `A`, `S`, `D`, Space, mouse movement, Arrow keys, left/right mouse buttons, `F`, `G`, `1`, `2`, `3`, `4`, mouse wheel, and `P`. Each ignored input leaves world, player, selection, held-input state, mutation revision, persistence state, application state, and the exact `status` and `save-state` text byte-identical. This rule does not disable Start, Save, Reset, reset-dialog, or focus/navigation controls in the states where their UI contracts permit them.

Call `preventDefault()` only for a handled Space, Arrow, `F`, `G`, number-key, or `P` event while `PLAYING`, for a handled canvas wheel event while `PLAYING`, and for the render-canvas context menu. Do not prevent repeated/invalid/ignored events and do not disable browser keyboard shortcuts outside active game controls.

## 7. State machine and UI contract

The only application states are:

```text
BOOT -> READY -> PLAYING <-> PAUSED
BOOT -> FATAL_WEBGL
READY -> FATAL_WEBGL
BOOT -> FATAL_SPAWN
READY -> FATAL_SPAWN
PAUSED -> READY              confirmed reset
```

At `BOOT`, load and validate storage, create the renderer, then enter `READY`. Every successful transition from `BOOT` to `READY`, including default in-memory recovery after a storage read failure or invalid saved value, sets `status` to exactly `Ready. Select Start to play.` Storage warnings are shown separately in `save-state`. If `canvas.getContext("webgl2")` returns null, enter `FATAL_WEBGL`, expose a visible non-canvas element whose complete text is `WebGL 2 is required to run Voxel Sandbox MVP.` and whose text/background contrast is at least `4.5:1`, and do not start `requestAnimationFrame`.

Required DOM IDs:

```text
game-canvas
status
start-button
save-button
reset-button
reset-dialog
reset-confirm
reset-cancel
crosshair
hotbar
controls
save-state
```

The Start button is enabled only in `READY` or `PAUSED`. One activation stores that prior state in a pending-lock record, sets `status` to exactly `Requesting pointer lock.`, and calls `game-canvas.requestPointerLock()` exactly once. A second Start activation while that record is pending is ignored byte-identically. Promise resolution alone is not success. Only `pointerlockchange` with `document.pointerLockElement === game-canvas` clears the pending record, enters `PLAYING`, and sets `status` to exactly `Playing.`; it does not advance simulation until the next animation-frame delta is processed.

All pre-acquisition denial paths have one disposition: a synchronous exception from `requestPointerLock`, rejection of its returned promise, `pointerlockerror` while the pending record exists, or `pointerlockchange` while pending that reports an element other than `game-canvas` clears the record, retains its recorded `READY` or `PAUSED` state, sets `status` to exactly `Pointer lock was denied. Select Start to try again.`, and changes no world, player, input, accumulator, selection, dirty, or storage state. Handle only the first denial signal for a pending record; later promise/event signals from that completed request are ignored. Do not infer success or denial from elapsed time: while neither terminal event occurs, retain the prior state, pending record, and `Requesting pointer lock.` status; GUI-001 records `HOLD` if this prevents the procedure. If a late event nevertheless gives the canvas pointer lock with no pending record and state is not `PLAYING`, call `document.exitPointerLock()` once and retain application and simulation state; a synchronous cleanup exception sets `status` to `Pointer lock could not be released.` and otherwise changes nothing.

One non-repeating `P` keydown while `PLAYING` sets `status` to exactly `Pausing.`, calls `document.exitPointerLock()` exactly once, and does not directly change application or simulation state. Escape relies on the browser's pointer-lock release. A `pointerlockchange` from `PLAYING` with an owner other than `game-canvas`, whether caused by `P`, Escape, or external loss, enters `PAUSED`, clears held inputs, pending jump, and accumulator, and sets `status` to exactly `Paused.` If `exitPointerLock()` throws synchronously or `pointerlockerror` occurs after the `P` request while the canvas remains locked, retain `PLAYING` and all simulation/input state and set `status` to exactly `Pointer lock could not be released.` A later actual loss still follows the normal `PAUSED` transition. The Start button resumes from `PAUSED` through the same confirmed-lock sequence.

Save and Reset are operable only in `READY` or `PAUSED`. Reset opens the in-page `reset-dialog`; it MUST NOT use `window.confirm`. Cancel closes the dialog without state or storage changes. Confirm first clears the save key; only after that operation succeeds does it reconstruct the seed-1337 baseline and exact initial player state, clear dirty state, close the dialog, enter `READY`, and set `status` to exactly `World reset.`

Set the document title and visible heading to exactly `Voxel Sandbox MVP`. Button text is exactly `Start`, `Save`, and `Reset World`. The reset dialog has heading `Reset world?`, body `This removes the saved world and restores seed 1337.`, confirm text `Reset World`, and cancel text `Cancel`. Hotbar labels in order are exactly `Meadow`, `Soil`, `Rock`, `Timber`; each is a button with `aria-pressed="true"` only for the selected block and `aria-pressed="false"` for the other three. Persistent controls text contains these exact lines in order: `Move: W A S D`, `Jump: Space`, `Look: Mouse or Arrow keys`, `Break: Left click or F`, `Place: Right click or G`, `Select: 1 2 3 4 or wheel`, and `Pause: P or Escape`.

Show a crosshair at the exact canvas center only while `PLAYING`; hide it in every other state. Keep the four hotbar buttons in one ordered group centered along the bottom, `status` in a top-left region, and controls in a top-right region. Provide `status` and `save-state` as live `role="status"` regions, visible `:focus-visible` indicators, and at least 44-by-44 CSS-pixel targets for every button. Arrow-key look plus `F`/`G` provide a keyboard-only alternative to mouse look and edit buttons. Do not claim that 3-D play is screen-reader equivalent.

UI surface colors, panel opacity, borders, radii, shadows, spacing, font family/size/weight, control wrapping below `1280x720`, and crosshair stroke styling are classified `MAY_DIFFER`; they are not fidelity requirements, parity dimensions, or GUI pass criteria. Text contrast against its rendered background MUST be at least `4.5:1`, and the focus indicator MUST contrast at least `3:1` against adjacent colors. The pinned region placement, target sizes, labels, and clean-room naming remain exact. Sky, block colors, face shades, geometry, and visibility/state rules remain exact rendering requirements and are not `MAY_DIFFER`.

## 8. Rendering contract

Use raw WebGL 2 and ECMAScript modules. Do not use a framework, engine, texture, model, font file, image, CDN, data URL, blob URL, network API, worker, WebAssembly module, or generated dependency.

A solid cell `(x,y,z)` occupies the closed unit-cube coordinates `[x,x+1] x [y,y+1] x [z,z+1]`; shared faces are emitted by neither interior side. For `X=x+1`, `Y=y+1`, and `Z=z+1`, emit visible faces in exact orientation order `+Y, -Y, +X, -X, +Z, -Z`, skipping any non-visible orientation. Each emitted face uses these four vertices in order and local indices `[0,1,2, 0,2,3]`, offset by the prior vertex count:

| Face | Ordered positions |
| --- | --- |
| `+Y` | `(x,Y,Z), (X,Y,Z), (X,Y,z), (x,Y,z)` |
| `-Y` | `(x,y,z), (X,y,z), (X,y,Z), (x,y,Z)` |
| `+X` | `(X,y,z), (X,Y,z), (X,Y,Z), (X,y,Z)` |
| `-X` | `(x,y,Z), (x,Y,Z), (x,Y,z), (x,y,z)` |
| `+Z` | `(X,y,Z), (X,Y,Z), (x,Y,Z), (x,y,Z)` |
| `-Z` | `(x,y,z), (x,Y,z), (X,Y,z), (X,y,z)` |

Build one indexed mesh containing only faces adjacent to `air` or the outside render boundary. Each emitted face therefore has four distinct outward-counterclockwise vertices and six triangle indices. Store indices in `Uint32Array`. Iterate cells in numeric `x`, then `y`, then `z` order, then use the face order above, so mesh bytes are deterministic. Rebuild and upload the mesh only after initial load, a successful block mutation, a successful save load, or confirmed reset. Model those events with a monotonically increasing mesh revision; an unchanged frame and a rejected mutation retain the same revision and MUST NOT call the mesh builder or a buffer-upload method.

Use these RGB values in linear shader inputs:

| Surface | RGB |
| --- | --- |
| Sky clear color | `(0.56, 0.79, 1.00)` |
| Meadow | `(0.30, 0.64, 0.27)` |
| Soil | `(0.48, 0.30, 0.16)` |
| Rock | `(0.48, 0.50, 0.54)` |
| Timber | `(0.58, 0.39, 0.20)` |

Multiply block color by face shade `1.00` for `+Y`, `0.55` for `-Y`, `0.82` for `+X/-X`, `0.72` for `+Z`, and `0.66` for `-Z`. Store the resulting per-face RGB value on all four face vertices; compare computed components with tolerance `0.000001`.

Use this exact column-major perspective matrix, with `f = 1 / tan(verticalFieldOfViewRadians / 2)`:

```text
[f/aspect, 0, 0, 0,
 0, f, 0, 0,
 0, 0, (far+near)/(near-far), -1,
 0, 0, (2*far*near)/(near-far), 0]
```

The production values are a 75-degree vertical field of view converted to radians, near plane `0.05`, and far plane `96`; aspect is the post-resize drawing-buffer `width / height`. Matrix tests compare every component with tolerance `0.000001`.

The camera eye is `eye = (player.x, player.y + 1.62, player.z)`. Map normalized yaw and clamped pitch to exact unit forward vector `(sin(yaw)*cos(pitch), sin(pitch), -cos(yaw)*cos(pitch))`. Define right as `(cos(yaw), 0, sin(yaw))` and up as `cross(right, forward)`. At yaw `0`, pitch `0`, forward is `(0,0,-1)`, right is `(1,0,0)`, and up is `(0,1,0)`; positive yaw looks toward `+X`, and positive pitch looks toward `+Y`.

Use this exact column-major view matrix, where `r=right`, `u=up`, `f=forward`, `e=eye`, and `dot` is the three-component dot product:

```text
[r.x, u.x, -f.x, 0,
 r.y, u.y, -f.y, 0,
 r.z, u.z, -f.z, 0,
 -dot(r,e), -dot(u,e), dot(f,e), 1]
```

The vertex shader is GLSL ES `#version 300 es`, declares `layout(location=0) in vec3 aPosition`, `layout(location=1) in vec3 aColor`, `uniform mat4 uProjection`, `uniform mat4 uView`, and `out vec3 vColor`, and computes `vColor = aColor` then `gl_Position = uProjection * uView * vec4(aPosition, 1.0)`. The fragment shader is GLSL ES `#version 300 es`, declares `precision highp float`, `in vec3 vColor`, and `out vec4 outColor`, and computes `outColor = vec4(vColor, 1.0)`. Shader compile failure or program link failure enters `FATAL_WEBGL`, uses the exact visible fallback element and text/contrast contract in section 7, starts no animation frame, and performs no draw.

At renderer initialization, call `enable(DEPTH_TEST)`, `enable(CULL_FACE)`, `cullFace(BACK)`, and `frontFace(CCW)` in that order. For drawing-buffer sizing, use DPR `1` when `devicePixelRatio` is nonfinite or not positive; otherwise cap it at `2`. Set each buffer dimension to `max(1, Math.round(cssDimension * effectiveDpr))`. When either target dimension differs, assign width then height and call `viewport(0, 0, width, height)` once. When neither differs, assign neither dimension and do not call `viewport`.

For every nonfatal rendered frame, perform operations in this exact order: resize check; `clearColor(0.56, 0.79, 1.00, 1.00)`; `clear(COLOR_BUFFER_BIT | DEPTH_BUFFER_BIT)`; `useProgram(program)`; `bindVertexArray(meshVao)`; `uniformMatrix4fv(projectionLocation, false, projectionMatrix)` for `uProjection`; `uniformMatrix4fv(viewLocation, false, viewMatrix)` for `uView`; and, only when `indexCount > 0`, `drawElements(TRIANGLES, indexCount, UNSIGNED_INT, 0)`. Do not call `drawElements` for zero indices. Unbind operations after drawing are optional and have no acceptance meaning; no clear, program, uniform, or draw call may occur before the ordered operations above in that frame.

Keep the renderer testable without a browser or native graphics process: renderer construction accepts a canvas whose `getContext("webgl2")` result supplies the WebGL 2 interface, and production obtains the same interface through the real canvas. `tests/mesh.test.mjs` uses a synthetic cell accessor and `tests/renderer.test.mjs` uses a fake canvas and call-recording fake WebGL 2 context; neither test opens a browser.

`src/renderer.js` exposes these named contracts for both production and tests:

- `buildVisibleMesh(getCell, bounds)` requires a function and a non-null plain object whose own key set is exactly `minX, maxX, minY, maxY, minZ, maxZ`, all values are integers, and each minimum is no greater than its maximum. A nonfunction throws `TypeError` with exact message `getCell must be a function.`; an invalid bounds object throws `RangeError` with exact message `bounds must contain ordered integer min/max coordinates.`; an unsupported callback value throws `RangeError` with exact message `getCell returned an unsupported block value.`; a callback-thrown exception propagates unchanged. Success returns `{ vertices, indices, faceCount }`; `vertices` is a `Float32Array` with stride six in property order `x, y, z, r, g, b`, `indices` is a `Uint32Array`, and `faceCount` is the emitted-face integer.
- `createPerspectiveMatrix(aspect)` requires a finite positive number; invalid input throws `RangeError` with exact message `aspect must be a finite positive number.` Success returns a 16-element `Float32Array` containing the pinned 75-degree/`0.05`/`96` matrix.
- `createViewMatrix(x, y, z, yaw, pitch)` requires five finite numbers, normalized-domain yaw, and pinned-domain pitch; invalid input throws `RangeError` with exact message `camera values are outside the finite runtime domain.` Success returns the exact 16-element `Float32Array` view matrix above using eye height `1.62`.
- `computeDrawingBufferSize(cssWidth, cssHeight, dpr)` requires finite nonnegative CSS dimensions; invalid width or height throws `RangeError` with exact message `CSS dimensions must be finite nonnegative numbers.` Invalid/nonpositive DPR follows the pinned fallback and does not throw. Success returns an object with exactly integer properties `width, height` using the pinned DPR and rounding rules.
- `configureWebGL(gl)` requires an object with callable `enable`, `cullFace`, and `frontFace` plus finite numeric `DEPTH_TEST`, `CULL_FACE`, `BACK`, and `CCW`; invalid input throws `TypeError` with exact message `A WebGL 2 configuration interface is required.` before making a call. Success performs the exact calls above and returns `undefined`; a context-method exception propagates unchanged.
- `resizeDrawingBuffer(canvas, gl, dpr)` requires an object with finite nonnegative numeric `clientWidth` and `clientHeight` and finite nonnegative numeric `width` and `height`, plus an object with callable `viewport`; invalid canvas input throws `TypeError` with exact message `A canvas with finite nonnegative dimensions is required.`; invalid viewport input throws `TypeError` with exact message `A WebGL 2 viewport interface is required.`; these checks precede assignment or viewport calls. Success performs the exact assignment/viewport behavior above and returns `true` only when a resize occurred, otherwise `false`; setter or viewport exceptions propagate unchanged.
- `createMeshRevisionGate(rebuildAndUpload)` requires a function; invalid input throws `TypeError` with exact message `rebuildAndUpload must be a function.` It returns a `sync(revision, source)` method. The first nonnegative integer revision invokes `rebuildAndUpload(source, revision)` once, retains the revision only after that call returns, and returns `true`. The same revision returns `false` without invoking it. A greater revision follows the first-call rule. A lower, noninteger, negative, or nonfinite revision throws `RangeError` with exact message `revision must be a nondecreasing nonnegative integer.` without invoking the callback or changing the retained revision. A callback exception propagates unchanged and leaves the retained revision unchanged.

The required mesh and renderer oracles are:

- one isolated `meadow` cube emits exactly 6 faces, 24 vertices, and 36 indices;
- two face-adjacent `meadow` cubes emit exactly 10 faces, 40 vertices, and 60 indices, with no internal face;
- each orientation's four vertex colors equal `meadow` RGB multiplied by its pinned face shade within `0.000001`;
- the production perspective inputs produce the exact matrix formula above within `0.000001`;
- CSS size `320x180` at DPR `1`, `2`, and `3` produces `320x180`, `640x360`, and `640x360`; a repeated same-size call performs no assignment or viewport call;
- the fake context records the exact depth, culling, winding, indexed-draw, and viewport calls above; and
- two renders with the same mesh revision perform exactly one build and upload in total, while one subsequent increment performs exactly one additional build and upload.

The layout is clean-room: the canvas fills the viewport; status, controls, crosshair, and hotbar occupy the pinned regions in section 7; and no logo or menu arrangement is copied from another product. Do not compare or score `MAY_DIFFER` styling during browser acceptance.

## 9. Persistence contract

Use only `localStorage` key `voxel-sandbox-mvp/v1`. The canonical document has this property order:

```text
version, seed, player, selectedBlock, changes
```

The `player` property order is `x, y, z, yaw, pitch`. Each `changes` entry has property order `x, y, z, type`; entries are sorted by numeric `x`, then `y`, then `z`. Coordinates are in-bounds integers and unique. Change type is exactly one of `air`, `meadow`, `soil`, `rock`, or `timber` and MUST differ from that cell's generated baseline.

Before serialization, round each player number with `Math.round(value * 1000000) / 1000000` and replace negative zero with positive zero. The exact empty-world fixture is:

```json
{"version":1,"seed":1337,"player":{"x":16.5,"y":7,"z":16.5,"yaw":0,"pitch":0},"selectedBlock":"meadow","changes":[]}
```

Load is all-or-nothing. Reject the complete saved value when any condition holds:

- the string exceeds `1048576` JavaScript code units;
- JSON parsing fails;
- the root or nested property set differs from the canonical schema;
- `version` is not integer `1` or `seed` is not integer `1337`;
- player `x` or `z` is outside inclusive `[0.3, 31.7]`, player `y` is outside inclusive `[0, 32]`, yaw is outside `[-3.141592653589793, 3.141592653589793)`, pitch is outside the pinned inclusive pitch range, or any player number is nonfinite;
- `selectedBlock` is not one of the four solid block types;
- a change coordinate is noninteger or out of bounds;
- a change type is invalid or equals its generated baseline;
- coordinates repeat, order is not canonical, or changes exceed `4096`.

At `BOOT`, call `localStorage.getItem("voxel-sandbox-mvp/v1")` once. When it returns `null`, load the default world, leave storage untouched, keep dirty state false, enter `READY`, set `status` to `Ready. Select Start to play.`, and set `save-state` to `No saved changes.`

When `getItem` returns schema-valid bytes, construct the complete saved world before testing the saved player box. A nonintersecting saved player loads exactly with velocity `(0,0,0)`, grounded recomputed by a downward collision probe of `0.000001` block, accumulator `0`, all held inputs/pending jump false, dirty false, stored bytes unchanged, `READY` status `Ready. Select Start to play.`, and `save-state` `Saved world loaded.` If the saved player intersects, test candidate feet heights `min(savedY+n, 16)` for integer `n=1,2,...`, in order, stopping after testing `16` once; retain saved `x`, `z`, yaw, pitch, world, and selection. On the first nonintersecting candidate, use that `y`, velocity `(0,0,0)`, grounded false, accumulator `0`, cleared held inputs/pending jump, dirty true, stored bytes unchanged, state `READY`, `status` exactly `Ready. Select Start to play.`, and `save-state` exactly `Saved position was obstructed; moved player upward. Save to retain it.` If no candidate through `16` is nonintersecting, retain the stored bytes, keep dirty false, enter `FATAL_SPAWN`, set `status` to `No safe spawn position is available.`, set `save-state` to `Saved data is valid, but no safe player position is available.`, and do not start `requestAnimationFrame`.

If the `BOOT` `getItem` call throws, do not call `setItem` or `removeItem` during `BOOT`. Load the default world into memory, keep dirty state false, leave any inaccessible stored bytes byte-identical, enter `READY`, set `status` to exactly `Ready. Select Start to play.`, and set `save-state` to exactly `Storage is unavailable; current changes remain in memory.` Do not permanently lock later writes; the first eligible write trigger in event-arrival order follows the retry contract below.

For invalid saved bytes, retain those exact bytes, load the default world into memory, lock storage writes, enter `READY` with `status` equal to `Ready. Select Start to play.`, and set `save-state` to `Saved data is invalid. Reset World to replace it.` Playing remains available in memory. Save leaves both storage and world unchanged and reports the same message through `save-state` until confirmed reset clears the invalid bytes.

Mark dirty whenever world deviations, player position/yaw/pitch, or selected block changes after the last successful write; held inputs, velocity, grounded, accumulator, application state, and UI status are not serialized and do not by themselves mark dirty. Process persistence triggers synchronously and without coalescing in exact event-arrival order. The only eligible triggers are: one automatic write after a successful block mutation in `PLAYING`; one explicit Save activation in `READY` or `PAUSED` while the reset dialog is closed; and one `visibilitychange` whose new `document.visibilityState` is `hidden` in `READY`, `PLAYING`, or `PAUSED`. Save activation in another state, Save while the reset dialog is open, visibility becoming a value other than `hidden`, and visibility changes during `BOOT`, `FATAL_WEBGL`, or `FATAL_SPAWN` are ignored byte-identically. A hidden-visibility event is eligible even when dirty is false and, if it is the first trigger after a `BOOT` `getItem` exception, it is the first retry and writes the complete current default state before any later event.

For each eligible trigger, the invalid-saved-bytes write lock has first precedence: perform no serialization or storage call and retain `save-state` as `Saved data is invalid. Reset World to replace it.` Otherwise serialize the complete current state and call `setItem` exactly once. If access or quota throws, keep in-memory state, set dirty true, leave prior stored bytes byte-identical, and set `save-state` to exactly `Save failed; current changes remain in memory.` The next eligible trigger retries the complete then-current state. A successful write replaces the key with exact canonical bytes, clears dirty state, and sets `save-state` to exactly `Saved.` Explicit Save and visibility persistence leave `status` byte-identical. Automatic mutation persistence retains the exact break/place status. No trigger calls `getItem` or `removeItem`.

Confirmed reset calls `localStorage.removeItem("voxel-sandbox-mvp/v1")` before changing in-memory state. If `removeItem` throws, leave the prior stored bytes byte-identical; leave world, player, selection, dirty flag, write-lock state, application state, and `save-state` byte-identical; leave `reset-dialog` open; and set `status` to exactly `Reset failed; saved data was not changed.` Do not call `setItem`, reconstruct the world, or close the dialog on that path. If `removeItem` succeeds, the save key is absent, reconstruction follows the successful reset contract in section 7, and `save-state` becomes exactly `No saved changes.`

## 10. Browser and security boundary

`index.html` MUST contain this exact effective Content Security Policy, expressed in a meta element without weakening directives:

```text
default-src 'self'; script-src 'self'; style-src 'self'; img-src 'none'; connect-src 'none'; media-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
```

The product performs no `fetch`, XMLHttpRequest, WebSocket, EventSource, beacon, service-worker registration, dynamic import from a URL, form submission, navigation, or external resource load. The local Python static server is the only process required to run the product. Bind it only to `127.0.0.1:8000`.

## 11. Test-first implementation order

Create immutable oracle fixtures before importing product modules. Expected values MUST be hand-computed from this request and MUST NOT be produced by the implementation under test.

### Fixed trace and evidence ID register

The current run authorizes only the following authored graph IDs. Replace scaffold markers with these IDs before `build-ready`; do not rename, duplicate, or allocate another current-run graph, capture, parity, assurance, or gap ID. Runtime-generated `RUN-###` and scoped `ART-CAP/RUN/PAR/ASSURE-###-##` IDs are allocated only by the clone-pack commands and MUST NOT be predicted or hand-authored. A need for another authored ID means the behavior exceeds this request: HALT with `SPEC-001` and request an authority revision.

| Kind | Exact IDs and meaning |
| --- | --- |
| baseline/evidence | `BASE-001` = SHA-256-pinned prompt baseline; `E-001` = immutable prompt bytes and hash; `ART-001` = the governed `USER_PINNED` prompt artifact |
| decisions | `DEC-001` = authorized original clean-room implementation; `DEC-002` = CC0 dedication and local-only delivery/no remote; `DEC-003` = full-stack QA `NOT_APPLICABLE` plus exact section 13 exclusions |
| context | `ENV-001` = recorded local executable/browser environment; `ACT-001` = local evaluator; `STACK-001` = exact `static-web-esm` profile |
| interfaces/data | `IF-001` = DOM/input/pointer-lock surface; `IF-002` = product module/renderer surface; `IF-003` = localStorage surface; `DATA-001` = generated world/player state; `DATA-002` = canonical save document. The workflow semantics remain normative in `REQ-004` through `REQ-010`; do not create a pre-build `WF` record because the live `build-ready` profile cannot accept an unevidenced `EQUIVALENT` workflow disposition. |
| security/exclusion | `SEC-001` = CSP, same-origin static loading, zero dependencies/secrets/network; `EXC-001` = exact section 13 exclusion set |
| provenance | `PROV-001` = immutable controlling-request provenance record described below; it is the only current-run `PROV` record |
| assurance/gap | assurance risk profile is `local-evaluation`; `ASSURE-001` is the required provenance case and `ASSURE-002` is the required threat-model case described below; `GAP-001` = conditional GUI evidence gap and is created only when GUI-001 cannot be completed |
| manual label | `GUI-001` = the section 12 manual evidence bundle label; it is not an index record kind, and its passing `RUN`/`ART` IDs come only from `record-manual` |

Author `PROV-001` as an exact clone-index record with `kind:"PROV"`, locator path `provenance_ledger.md`, locator anchor `| PROV-001 |`, the SHA-256 of that one finalized UTF-8 ledger row, `applicability:"MVP"`, and `state:"READY"`. Its links are exactly `artifacts:["ART-001"]`, `decisions:["DEC-001","DEC-002"]`, `evidence:["E-001"]`, and `requirements:["REQ-001","REQ-003","REQ-012"]`. Its attributes contain exactly these runtime-supported keys: `origin:"MINECRAFT_CLONE_PROMPT.md"`; `version:"sha256:<prompt-sha256>"`, substituting the lowercase digest recorded by `E-001`; `sha256:"<prompt-sha256>"` with the same substitution; `license:"CC0-1.0"`; `rights_basis:"DEC-001 requester authorization and DEC-002 dedication"`; `disposition:"retain as immutable USER_PINNED build input"`; and `separation_profile:"non-separated"`. The `PROV-001` ledger row records kind `source`, that same filename/version/origin, CC0/decision rights, actual recording actor/tool/time, the same digest, transform parent `none`, and usage `governing request and independent oracle authority`.

Add reciprocal `provenance:["PROV-001"]` links to `ART-001`, `E-001`, `DEC-001`, `DEC-002`, `REQ-001`, `REQ-003`, and `REQ-012`; no other record links to `PROV-001`. This relation is supported by the live index link-kind contract and introduces no new record ID.

Preserve the initialized assurance plan's schema, pack identity, and revision fields, set `risk_profile` to exactly `local-evaluation`, and replace `cases` with exactly these two case objects, in this order:

1. `id:"ASSURE-001"`, `kind:"provenance"`, `required:true`, `argv:["node","--test","tests/static-contract.test.mjs"]`, `cwd:"."`, `timeout_seconds:300`, `expected_exit:0`, `artifact_paths:[]`, `result:null`.
2. `id:"ASSURE-002"`, `kind:"threat-model"`, `required:true`, `argv:["npm","test"]`, `cwd:"."`, `timeout_seconds:300`, `expected_exit:0`, `artifact_paths:[]`, `result:null`.

Each same-ID `ASSURE` index record pins only its live case SHA-256 in `attributes.case_sha256`. `ASSURE-001` links `requirements:["REQ-001","REQ-003","REQ-011","REQ-012"]`; `ASSURE-002` links `requirements:["REQ-002","REQ-006","REQ-008","REQ-010","REQ-011","REQ-012"]`. Add the reciprocal `assurance` link to each named `REQ`. Before execution both assurance records use `applicability:"REQUIRED"` and `state:"NOT_RUN"`; do not fabricate PASS state or result pointers. The assurance runtime writes the two immutable result pointers and evidence directories.

The complete product trace is fixed below. An empty cell is forbidden in the authored acceptance matrix; use every listed reciprocal link exactly.

| Requirement | Exact normative scope | Acceptance IDs | Test IDs | Gate IDs | Oracle/evidence IDs |
| --- | --- | --- | --- | --- | --- |
| `REQ-001` | Sections 1 and 13 clean-room authority, naming, CC0, claim, distribution, and exclusion boundaries | `AC-009`, `AC-013` | `TEST-007` | `GATE-001`, `GATE-002`, `GATE-006`, `GATE-007` | `E-001`, `ART-001`, `DEC-001`, `DEC-002`, `DEC-003`, `EXC-001`, `PROV-001`, `ASSURE-001` |
| `REQ-002` | Section 2 workspace inventory, executable versions, local Git/network boundary, and no installation | `AC-009` | `TEST-007`, `TEST-010` | `GATE-001`, `GATE-002`, `GATE-004` | `E-001`, `ENV-001`, `DEC-002`, `ASSURE-002` |
| `REQ-003` | Section 3 exact scaffold, file fence, commands, zero dependencies, and full-stack QA disposition | `AC-008`, `AC-009` | `TEST-007`, `TEST-008`, `TEST-010` | `GATE-001`, `GATE-002`, `GATE-004` | `E-001`, `STACK-001`, `DEC-003`, `PROV-001`, `ASSURE-001` |
| `REQ-004` | Section 4 deterministic world, bounds, strata, deviations, edit limit, and reset baseline | `AC-001`, `AC-003`, `AC-004` | `TEST-001`, `TEST-003`, `TEST-004`, `TEST-009` | `GATE-002`, `GATE-003` | `E-001`, `CAP-001`, `CAP-002`, `PAR-001`, `DATA-001` |
| `REQ-005` | Section 5 initial player, fixed clock, movement, yaw, collision, jump, pause, and spawn recovery | `AC-002`, `AC-004` | `TEST-002`, `TEST-004`, `TEST-009` | `GATE-002`, `GATE-003` | `E-001`, `CAP-001`, `CAP-002`, `PAR-001`, `DATA-001` |
| `REQ-006` | Sections 6 and 7 keyboard/mouse/wheel signs, repeat rules, selection, pointer-lock lifecycle, state machine, and ignored-input behavior | `AC-002`, `AC-003`, `AC-005`, `AC-006` | `TEST-002`, `TEST-003`, `TEST-007`, `TEST-009`, `TEST-011` | `GATE-002`, `GATE-003`, `GATE-005` | `E-001`, `CAP-001`, `CAP-002`, `PAR-001`, `IF-001`, `ASSURE-002` |
| `REQ-007` | Section 6 DDA record, reach/tie/normal rules, edit precedence, statuses, and mutation immutability | `AC-003` | `TEST-003`, `TEST-009`, `TEST-011` | `GATE-002`, `GATE-003`, `GATE-005` | `E-001`, `CAP-001`, `CAP-002`, `PAR-001` |
| `REQ-008` | Section 7 exact UI labels/state/availability, accessibility, fatal states, and `MAY_DIFFER` boundary | `AC-001`, `AC-005`, `AC-006`, `AC-012` | `TEST-007`, `TEST-011` | `GATE-002`, `GATE-005` | `E-001`, `IF-001`, `ASSURE-002`; GUI-001 is a non-index reporting label only |
| `REQ-009` | Section 8 unit mesh, colors, camera, matrices, shader, WebGL sequence, resizing, revisions, and API failures | `AC-001`, `AC-010`, `AC-012` | `TEST-005`, `TEST-006`, `TEST-009`, `TEST-011` | `GATE-002`, `GATE-003`, `GATE-005` | `E-001`, `CAP-001`, `CAP-002`, `PAR-001`, `IF-002`; GUI-001 is a non-index reporting label only |
| `REQ-010` | Section 9 canonical storage, validation, obstructed-save recovery, retry precedence, invalid-byte lock, failure, and reset | `AC-004`, `AC-005`, `AC-012` | `TEST-004`, `TEST-009`, `TEST-011` | `GATE-002`, `GATE-003`, `GATE-005` | `E-001`, `CAP-001`, `CAP-002`, `PAR-001`, `DATA-002`, `IF-003`, `ASSURE-002`; GUI-001 is a non-index reporting label only |
| `REQ-011` | Section 10 CSP, no application network, static server, and local-origin boundary | `AC-007`, `AC-009`, `AC-012` | `TEST-007`, `TEST-010`, `TEST-011` | `GATE-002`, `GATE-004`, `GATE-005`, `GATE-006` | `E-001`, `SEC-001`, `ASSURE-001`, `ASSURE-002`; GUI-001 is a non-index reporting label only |
| `REQ-012` | Section 11 TDD order, immutable oracle, capture/parity, commands, trace, and retained run evidence | `AC-008`, `AC-011` | `TEST-001`, `TEST-002`, `TEST-003`, `TEST-004`, `TEST-005`, `TEST-006`, `TEST-007`, `TEST-008`, `TEST-009`, `TEST-010` | `GATE-001`, `GATE-002`, `GATE-003`, `GATE-004`, `GATE-006` | `E-001`, `BASE-001`, `PROV-001`, `CAP-001`, `CAP-002`, `PAR-001`, `ASSURE-001`, `ASSURE-002` |
| `REQ-013` | Section 12 exact browser procedure and truthful GUI-001 capture/HOLD boundary | `AC-012` | `TEST-011` | `GATE-005` | `E-001` plus runtime-generated manual RUN/ART evidence only; GUI-001 is a non-index reporting label; `GAP-001` only on capability block |
| `REQ-014` | Sections 13 and 14 exact exclusions, gap/interview rules, local handoff, seal boundary, and terminal claim | `AC-013` | `TEST-007` | `GATE-006`, `GATE-007` | `E-001`, `DEC-002`, `DEC-003`, `EXC-001`, optional `GAP-001` |

Use this exact test register:

| Test ID | Exact path/procedure |
| --- | --- |
| `TEST-001` | `tests/world.test.mjs` |
| `TEST-002` | `tests/simulation.test.mjs` |
| `TEST-003` | `tests/raycast.test.mjs` |
| `TEST-004` | `tests/storage.test.mjs` |
| `TEST-005` | `tests/mesh.test.mjs` |
| `TEST-006` | `tests/renderer.test.mjs` |
| `TEST-007` | `tests/static-contract.test.mjs` |
| `TEST-008` | preserved `tests/smoke.test.mjs` |
| `TEST-009` | `tests/contract-probe.mjs` plus exact `PAR-001` comparison |
| `TEST-010` | `tests/http_smoke.py` |
| `TEST-011` | manual procedure is the immutable complete `MINECRAFT_CLONE_PROMPT.md`; attributes are exactly `environment_id:"ENV-001"` and `manual_procedure_sha256:"<prompt-sha256>"`, substituting the lowercase digest recorded by `E-001`; links are exactly `requirements:["REQ-006","REQ-007","REQ-008","REQ-009","REQ-010","REQ-011","REQ-013"]`, `acceptance:["AC-001","AC-002","AC-003","AC-004","AC-005","AC-007","AC-012"]`, `oracles:["ART-001","E-001"]`, and `gates:["GATE-005"]`; the actual observation log is the later GUI-001 `procedure.md` artifact |

Every `REQ-001` through `REQ-014` has `evidence:["E-001"]` in addition to any decision and domain links listed above, and `E-001.links.requirements` is exactly `["REQ-001","REQ-002","REQ-003","REQ-004","REQ-005","REQ-006","REQ-007","REQ-008","REQ-009","REQ-010","REQ-011","REQ-012","REQ-013","REQ-014"]`. Every `TEST-001` through `TEST-011` has `oracles:["ART-001","E-001"]` exactly; add reciprocal test links required by the fixed trace table without adding another oracle. These source/oracle links are mandatory runtime coverage, not optional descriptive evidence.

Every test file starts with a comment naming its exact `TEST` ID and linked `REQ`/`AC` IDs from the table; every individual test name includes its `TEST` ID and at least one linked `AC` ID. Do not mint case-specific trace IDs.

After a successful `record-manual`, let `<RUN-ID>` denote the ID actually returned by the runtime; never predict it. That runtime-generated `RUN` record has exactly `tests:["TEST-011"]`, the seven sorted `acceptance` IDs, `oracles:["ART-001","E-001"]`, and the seven sorted `requirements` IDs pinned on `TEST-011`, with no `gates` relation because the runtime records `gate_id:"MANUAL"` rather than an indexed gate. The same transaction appends `<RUN-ID>` to `links.runs` on `TEST-011`, each linked `AC`, each linked `REQ`, `ART-001`, and `E-001`. The runtime artifact allocation follows the command's argument order exactly: `ART-<RUN-ID>-01` is the immutable prompt procedure copy; `ART-<RUN-ID>-02` through `ART-<RUN-ID>-08` correspond respectively to GUI-001 `procedure.md`, `ready.png`, `gameplay.png`, `persistence.png`, `console.log`, `network.json`, and `observation.json`. `GUI-001` remains a non-index reporting label and MUST NOT occur in any clone-index link array; these runtime-created backlinks are the only GUI manual proof and do not create `REF_UNDEFINED`.

Use this exact gate register, resolving `<skill-root>` once from the installed symlink and recording its absolute path in `ENV-001`:

| Gate ID | Exact command or procedure | Required result |
| --- | --- | --- |
| `GATE-001` | `python3 <skill-root>/scripts/clone_pack.py validate docs/clone --profile build-ready --format json` before product edits | exit `0` and profile `build-ready` |
| `GATE-002` | `npm test` | exit `0`; execute through `record-run` after the indexed gate is authored |
| `GATE-003` | `node tests/contract-probe.mjs --output docs/clone/evidence/raw/clone/contract.json`, then the fixed CAP/PAR commands below | probe exit `0`; both captures `PASS`; parity exit `0` and `PASS` |
| `GATE-004` | `python3 tests/http_smoke.py` | exit `0`; execute through `record-run` after the indexed gate is authored |
| `GATE-005` | section 12 browser procedure followed by `record-manual docs/clone --test TEST-011` with the actual observer/authority and every retained GUI-001 artifact | `PASS`, or `HOLD` with only `GAP-001` and no passing manual run |
| `GATE-006` | `python3 <skill-root>/scripts/clone_pack.py assure docs/clone --case ASSURE-001 --case ASSURE-002` | aggregate exit `0`, with current `PASS` results for both required cases |
| `GATE-007` | `python3 <skill-root>/scripts/clone_pack.py seal docs/clone --profile verified-mvp`, then `python3 <skill-root>/scripts/clone_pack.py validate docs/clone --profile verified-mvp --format json` | seal exit `0`, then authoritative post-seal validation exit `0` and profile `verified-mvp`; otherwise `HOLD` |

The indexed executable contracts are exact: `GATE-002` has `argv:["npm","test"]`, `cwd:"."`, `timeout_seconds:300`, `expected_exit:0`, and empty `blocked_exit_codes`, `environment`, `normalizations`, `artifact_paths`, `fresh_artifact_paths`, and `redactions`; `GATE-003` has `argv:["node","tests/contract-probe.mjs","--output","docs/clone/evidence/raw/clone/contract.json"]`, the same common fields, `timeout_seconds:60`, and both `artifact_paths` and `fresh_artifact_paths` equal to `["docs/clone/evidence/raw/clone/contract.json"]`; `GATE-004` has `argv:["python3","tests/http_smoke.py"]`, the same empty fields, and `timeout_seconds:60`. Their `covered_ids` and reciprocal test links equal the IDs in the fixed trace table; their `oracle_ids` contain only `E-001` and `ART-001`. Execute them without a shell and retain them in this order:

```text
python3 <skill-root>/scripts/clone_pack.py record-run docs/clone --gate GATE-002 --environment ENV-001
python3 <skill-root>/scripts/clone_pack.py record-run docs/clone --gate GATE-003 --environment ENV-001
python3 <skill-root>/scripts/clone_pack.py record-run docs/clone --gate GATE-004 --environment ENV-001
```

Do not run the standalone probe command in the GATE table in addition to `record-run`; `record-run` is that invocation and creates the fresh clone contract file. `GATE-001`, `GATE-005`, `GATE-006`, and `GATE-007` use their listed profile/manual/assurance/seal commands directly and are not passed to `record-run`.

Before product implementation, hand-author `tests/fixtures/contract-oracle.json` from this request, copy its exact bytes to `docs/clone/evidence/raw/reference/contract.json`, hash both, and make both paths immutable evidence. `contract-probe.mjs --output <path>` accepts only that exact option form, requires an absent output path beneath `docs/clone/evidence/raw/clone`, writes canonical JSON atomically, refuses overwrite, and emits no nondeterministic fields. Its observation keys cover the frozen world, clock/yaw/input math, ray/edit, mesh/matrix, and storage/recovery cases linked to `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-009`, and `REQ-010`; it does not claim DOM or live-browser proof for `REQ-008`.

The oracle file and probe output use the exact root property order `schema_version, request_sha256, number_normalization, cases`. Each case uses exact property order `name, input, expected`; every nested property order is the order shown in the literal below. No extra property is permitted. For every computed noninteger, normalize before serialization with `Math.round(value * 1000000000000) / 1000000000000`, then replace negative zero with numeric `0`; integers and strings remain unchanged. Encode UTF-8 without a BOM or insignificant whitespace and with exactly one trailing LF. Replace the single literal string `<prompt-sha256>` with the lowercase 64-character digest already recorded by `E-001`; make no other substitution. The reference is authored from this literal before product modules exist. The probe obtains actual values by calling product exports and emits the same schema and order; it MUST NOT read or import the reference fixture.

```json
{"schema_version":"voxel-sandbox-contract-oracle/v1","request_sha256":"<prompt-sha256>","number_normalization":{"decimal_places":12,"algorithm":"Math.round(value * 1000000000000) / 1000000000000","negative_zero":0},"cases":[{"name":"world-heights-strata","input":{"seed":1337,"height_coordinates":[[0,0],[1,0],[0,1],[31,31],[16,16]],"cell_coordinates":[[0,6,0],[0,5,0],[0,4,0],[0,3,0],[0,7,0],[-1,0,0]]},"expected":{"heights":[6,4,8,6,6],"cells":["meadow","soil","soil","rock","air","air"]}},{"name":"fixed-step-yaw-movement","input":{"fixed_step":{"dt":0.016666666666666666,"position":[16.5,7,16.5],"velocity":[0,0,0],"grounded":true,"pending_jump":true,"held":[]},"yaw_inputs":[3.141592653589793,-3.141592653589793,9.42477796076938,-9.42477796076938,3.391592653589793,-3.391592653589793],"movement_cases":[["W"],["D"],["W","S"],["A","D"],["W","D"]]},"expected":{"fixed_step":{"position":[16.5,7.102777777778,16.5],"velocity":[0,6.166666666667,0],"grounded":false,"pending_jump":false},"normalized_yaw":[-3.14159265359,-3.14159265359,-3.14159265359,-3.14159265359,-2.89159265359,2.89159265359],"movement_velocity":[[0,0,-4],[4,0,0],[0,0,0],[0,0,0],[2.828427124746,0,-2.828427124746]]}},{"name":"ray-and-edit-records","input":{"rays":{"start_solid":{"origin":[0.5,0.5,0.5],"direction":[1,0,0],"solid_cells":[[0,0,0]]},"tie":{"origin":[0.5,0.5,0.5],"direction":[1,1,1],"solid_cells":[[1,0,0]]},"inclusive":{"origin":[0,0.5,0.5],"direction":[1,0,0],"solid_cells":[[5,0,0]]},"beyond":{"origin":[0,0.5,0.5],"direction":[1,0,0],"solid_cells":[[6,0,0]]}},"fresh_world_each_edit":true,"selected_block":"timber","player_feet":[16.5,7,16.5],"edits":[{"name":"break_surface","action":"break","hit_cell":[0,6,0],"preceding_air_cell":[0,7,0]},{"name":"break_foundation","action":"break","hit_cell":[0,0,0],"preceding_air_cell":[-1,0,0]},{"name":"place_without_cell","action":"place","hit_cell":[0,0,0],"preceding_air_cell":null},{"name":"place_outside","action":"place","hit_cell":[0,0,0],"preceding_air_cell":[-1,0,0]},{"name":"place_occupied","action":"place","hit_cell":[0,5,0],"preceding_air_cell":[0,6,0]},{"name":"place_player_overlap","action":"place","hit_cell":[16,6,16],"preceding_air_cell":[16,7,16]}]},"expected":{"rays":{"start_solid":{"hit_cell":[0,0,0],"preceding_air_cell":null,"distance":0,"entered_face_normal":[0,0,0]},"tie":{"hit_cell":[1,0,0],"preceding_air_cell":[0,0,0],"distance":0.866025403784,"entered_face_normal":[-1,0,0]},"inclusive":{"hit_cell":[5,0,0],"preceding_air_cell":[4,0,0],"distance":5,"entered_face_normal":[-1,0,0]},"beyond":null},"edits":[{"name":"break_surface","status":"Block removed.","mutated":true,"mutation_revision_delta":1,"dirty":true,"target_cell":[0,6,0],"target_value":"air"},{"name":"break_foundation","status":"The foundation layer cannot be removed.","mutated":false,"mutation_revision_delta":0,"dirty":false,"target_cell":[0,0,0],"target_value":"rock"},{"name":"place_without_cell","status":"No placement cell is available.","mutated":false,"mutation_revision_delta":0,"dirty":false,"target_cell":null,"target_value":null},{"name":"place_outside","status":"Cannot place outside the world.","mutated":false,"mutation_revision_delta":0,"dirty":false,"target_cell":[-1,0,0],"target_value":"air"},{"name":"place_occupied","status":"Placement cell is occupied.","mutated":false,"mutation_revision_delta":0,"dirty":false,"target_cell":[0,6,0],"target_value":"meadow"},{"name":"place_player_overlap","status":"Cannot place a block inside the player.","mutated":false,"mutation_revision_delta":0,"dirty":false,"target_cell":[16,7,16],"target_value":"air"}]}},{"name":"mesh-and-camera-matrices","input":{"isolated":[{"x":0,"y":0,"z":0,"type":"meadow"}],"adjacent":[{"x":0,"y":0,"z":0,"type":"meadow"},{"x":1,"y":0,"z":0,"type":"meadow"}],"face_order":["+Y","-Y","+X","-X","+Z","-Z"],"camera":{"x":16.5,"y":7,"z":16.5,"yaw":0,"pitch":0,"aspect":1.7777777777777777}},"expected":{"isolated":{"faces":6,"vertices":24,"indices":36},"adjacent":{"faces":10,"vertices":40,"indices":60},"meadow_face_colors":[[0.3,0.64,0.27],[0.165,0.352,0.1485],[0.246,0.5248,0.2214],[0.246,0.5248,0.2214],[0.216,0.4608,0.1944],[0.198,0.4224,0.1782]],"projection_float32":[0.733064293861,0,0,0,0,1.303225398064,0,0,0,0,-1.001042246819,-1,0,0,-0.100052110851,0],"view_float32":[1,0,0,0,0,1,0,0,0,0,1,0,-16.5,-8.619999885559,-16.5,1]}},{"name":"storage-canonical-write","input":{"version":1,"seed":1337,"player":{"x":16.5,"y":7,"z":16.5,"yaw":0,"pitch":0},"selected_block":"meadow","changes":[]},"expected":{"stored_bytes":"{\"version\":1,\"seed\":1337,\"player\":{\"x\":16.5,\"y\":7,\"z\":16.5,\"yaw\":0,\"pitch\":0},\"selectedBlock\":\"meadow\",\"changes\":[]}","dirty":false,"save_state":"Saved."}},{"name":"storage-obstructed-position-recovery","input":{"stored_bytes":"{\"version\":1,\"seed\":1337,\"player\":{\"x\":16.5,\"y\":7,\"z\":16.5,\"yaw\":0,\"pitch\":0},\"selectedBlock\":\"meadow\",\"changes\":[{\"x\":16,\"y\":7,\"z\":16,\"type\":\"rock\"}]}","application_state":"BOOT"},"expected":{"application_state":"READY","player":[16.5,8,16.5,0,0],"velocity":[0,0,0],"grounded":false,"dirty":true,"status":"Ready. Select Start to play.","save_state":"Saved position was obstructed; moved player upward. Save to retain it.","stored_bytes_unchanged":true}},{"name":"storage-failure-retry-and-reset","input":{"read_failure_then_trigger":{"get_item":"throws","first_eligible_trigger":"visibility-hidden"},"reset_remove_failure":{"application_state":"READY","dialog_open":true,"dirty":false,"save_state":"Saved world loaded.","stored_bytes":"{\"version\":1,\"seed\":1337,\"player\":{\"x\":16.5,\"y\":7,\"z\":16.5,\"yaw\":0,\"pitch\":0},\"selectedBlock\":\"meadow\",\"changes\":[]}"}},"expected":{"read_failure_then_trigger":{"call_order":["getItem","setItem"],"written_bytes":"{\"version\":1,\"seed\":1337,\"player\":{\"x\":16.5,\"y\":7,\"z\":16.5,\"yaw\":0,\"pitch\":0},\"selectedBlock\":\"meadow\",\"changes\":[]}","application_state":"READY","dirty":false,"status":"Ready. Select Start to play.","save_state":"Saved."},"reset_remove_failure":{"call_order":["removeItem"],"application_state":"READY","dialog_open":true,"dirty":false,"status":"Reset failed; saved data was not changed.","save_state":"Saved world loaded.","stored_bytes_unchanged":true,"world_player_selection_unchanged":true}}}]}
```

The `mesh-and-camera-matrices` values are the 12-decimal normalization of the actual `Float32Array` results required by section 8, not the unrounded double-precision formula. The `ray-and-edit-records` edit subcases each start from a new seed-1337 world, so earlier mutations cannot influence later expected values. `storage-canonical-write` starts dirty and observes the post-write state shown; its input omits transient dirty state because dirty is not serialized.

`CAP-001` has exactly `id:"CAP-001"`, `adapter:"manual"`, `side:"reference"`, `environment_id:"ENV-001"`, `required:true`, `authorization_decision_ids:["DEC-001"]`, `safe_test_environment:true`, `timeout_seconds:300`, `input:{"source_path":"evidence/raw/reference/contract.json"}`, `lifecycle:{"setup":null,"teardown":null}`, `redactions:[]`, and `result:null`. `CAP-002` has the same exact keys/order and values except `id:"CAP-002"`, `side:"clone"`, and `input.source_path:"evidence/raw/clone/contract.json"`. No other capture case or field is authored. Each same-ID `CAP` index counterpart has `attributes:{"case_sha256":"<current-case-sha256>"}`, where the value is the runtime's lowercase hash of that exact case with only `result` excluded; it has `environments:["ENV-001"]` and `decisions:["DEC-001"]` exactly, plus the requirements, acceptance, and tests mapped by the fixed trace table. Before capture it uses `applicability:"REQUIRED"` and `state:"NOT_RUN"`; only runtime evidence changes that state.

`PAR-001` has exactly `id:"PAR-001"`, `comparator:"json"`, `required:true`, `reference_capture_id:"CAP-001"`, `clone_capture_id:"CAP-002"`, `normalizations:[]`, `options:{}`, and `result:null`. Its same-ID `PAR` index counterpart has `attributes:{"case_sha256":"<current-case-sha256>"}`, `captures:["CAP-001","CAP-002"]`, and `decisions:[]` exactly, plus links to `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-009`, `REQ-010`, `AC-001`, `AC-002`, `AC-003`, `AC-004`, `AC-010`, `AC-011`, `TEST-001`, `TEST-002`, `TEST-003`, `TEST-004`, `TEST-005`, `TEST-006`, and `TEST-009`. Before parity it uses `applicability:"REQUIRED"` and `state:"NOT_RUN"`; only runtime evidence changes that state. Exact JSON equality has no tolerance. `PAR-001` is not GUI, accessibility, or live-browser evidence and cannot independently pass a criterion containing those dimensions. Execute exactly:

```text
python3 <skill-root>/scripts/clone_pack.py capture docs/clone --case CAP-001
python3 <skill-root>/scripts/clone_pack.py capture docs/clone --case CAP-002
python3 <skill-root>/scripts/clone_pack.py parity docs/clone --case PAR-001
```

Use this exact Red-Green-Refactor order:

1. Preserve the scaffold smoke tests and first add failing `world.test.mjs` cases for height samples, strata, bounds, deviations, deterministic reset, and the 4096/4097 boundary.
2. Implement only world/config behavior; rerun the focused test.
3. Add failing `simulation.test.mjs` cases for exact initial position/velocity/grounded/input/accumulator state, fixed-step equivalence, delta cap, opposite-key cancellation, diagonal normalization, yaw-relative forward/right signs, mouse/Arrow signs, repeat behavior, X/Z/Y collision ordering, grounding, jump rising edge, spawn recovery, pause input clearing, and paused immutability. The yaw oracle MUST cover `pi -> -pi`, `-pi -> -pi`, `3*pi -> -pi`, `-3*pi -> -pi`, `pi + 0.25 -> -pi + 0.25`, `-pi - 0.25 -> pi - 0.25`, and a nonfinite look delta leaving the complete prior state and visible status unchanged; use tolerance `0.000000000001` for finite comparisons.
4. Implement only math/simulation behavior; rerun the focused test.
5. Add failing `raycast.test.mjs` cases for normalized rays, direction validation before origin inspection, the exact start-inside-solid distance-zero/null-preceding/zero-normal record, inclusive reach, X/Y/Z ties, every entered-normal sign, successful break/place statuses, every exact rejection status, placement-rejection precedence, forbidden y=0 break, preceding-air placement, player overlap, bounds, and rejected-action immutability.
6. Implement only ray/action behavior; rerun the focused test.
7. Add failing `storage.test.mjs` cases for the exact empty fixture, six-decimal rounding, negative zero, sorting, round trip, every invalid-load class, valid nonintersecting saved player, valid obstructed-player upward recovery, no-safe-position fatal disposition, corrupt-byte retention/write-lock precedence, storage unavailable/quota errors, dirty retry, trigger-state permissions, visibility-first retry, synchronous event-order writes, and reset. Include a throwing `getItem` fixture that asserts the exact READY state, default in-memory world, false dirty flag, untouched stored bytes, no `setItem`/`removeItem` call, both exact status strings, and each possible first eligible retry trigger. Include a throwing `removeItem` fixture that asserts retained stored bytes, unchanged in-memory state/dirty flag/write lock/application state/`save-state`, open dialog, exact failure `status`, and no reconstruction or `setItem` call.
8. Implement only storage behavior; rerun the focused test.
9. Add failing `mesh.test.mjs` cases for the isolated-cube and adjacent-cube face/vertex/index counts, internal-face removal, `Uint32Array` indices, outward counterclockwise winding, and every pinned meadow face color/shade oracle.
10. Add failing `renderer.test.mjs` cases for unit-cube coordinates and deterministic face/cell order, every perspective- and view-matrix component, yaw/pitch direction oracles, shader interface/source contracts, DPR fallback/cap/rounding and resize behavior, exact initialize/clear/uniform/draw sequence through a call-recording fake WebGL 2 context, build/upload call counts across unchanged/incremented revisions and callback failure, and every named renderer API's exact invalid-input exception type/message with no forbidden side effect.
11. Implement only mesh and renderer behavior; rerun both focused tests.
12. Add failing `static-contract.test.mjs` cases for required DOM IDs, exact labels/control text, exact CSP, package scripts, absent dependency fields/lockfile/external URLs, state-transition functions, initial READY/PLAYING/Pausing/PAUSED text, every request/release pointer-lock denial path, every interaction/selection status, actions ignored outside `PLAYING`, P release behavior, fatal WebGL/shader behavior, mesh revision triggers, accessibility/contrast contracts, `MAY_DIFFER` exclusions, and product-facing forbidden names with only the controlling prompt filename exception.
13. Implement app/input/UI/CSS behavior; rerun the focused test.
14. Implement `contract-probe.mjs` to import product modules and emit canonical observations for the frozen height, empty-save, clock, yaw, ray, mutation, mesh, and persistence-failure cases. Compare that output with the independent pre-code oracle through the clone-pack parity workflow.
15. Implement `http_smoke.py` with Python standard-library `ThreadingHTTPServer` bound to `127.0.0.1` on an operating-system-selected port. It MUST serve the repository root, request `index.html` and every local module, reject missing paths, shut down in `finally`, and exit nonzero on mismatch. It is not browser or GUI evidence.
16. Run `npm test`, then `python3 tests/http_smoke.py`. Both MUST exit `0` before browser observation.

Every test uses only the fixed trace register above. Retain exact commands, exits, and artifacts in the clone pack. A process exit without the linked evidence is not proof.

## 12. Acceptance criteria

- `AC-001`: On BOOT with WebGL 2 and no saved value, one load enters `READY` with the exact initial player/world/selection, labels, statuses, visibility rules, and deterministic seed-1337 render; no `MAY_DIFFER` style is scored.
- `AC-002`: After one confirmed pointer-lock acquisition, held/cancelled/repeated inputs produce the pinned movement and look signs, collision, fall, grounded jump, and fixed-step results; one actual lock loss enters `PAUSED` and later ticks leave simulation byte-identical.
- `AC-003`: For each pinned ray normal/start/reach case, one break/place event returns the exact record, mutation, selection/status, persistence effect, or rejection precedence with every forbidden state/storage effect absent.
- `AC-004`: One write produces canonical bytes; each valid, obstructed-valid, invalid, unavailable, failed-write, visibility-first, retry, and reset fixture produces its exact world/player/dirty/storage/status outcome.
- `AC-005`: One keyboard-only sequence performs look, break, place, selection, pause, confirmed resume, Save, Reset Cancel, and Reset Confirm using the exact repeat/state rules, visible focus, labels, and live statuses.
- `AC-006`: Each null-context, shader/program failure, pointer-lock request denial, pointer-lock release denial, and fatal-spawn case produces its exact state/status and prohibited simulation/frame/draw effects.
- `AC-007`: One clean browser load requests only the same-origin static files needed for initial document/module loading and the application initiates no later network request.
- `AC-008`: From a clean checkout, `npm test`, the contract probe, and `python3 tests/http_smoke.py` each exit `0` using only the recorded installed Git/Node/npm/Python capabilities.
- `AC-009`: The final tree exactly satisfies the authority, initial-inventory decision, CC0/naming, path fence, `static-web-esm`, zero dependency/install/remote, CSP, and local-only contracts.
- `AC-010`: Independent mesh/renderer fixtures produce the exact unit-cube bytes/counts/colors, camera matrices, shader interface, DPR behavior, ordered WebGL calls, revision calls, and invalid-input results.
- `AC-011`: The authored pack uses only the fixed IDs and reciprocal mapping; `CAP-001` and `CAP-002` are current `PASS`, `PAR-001` is current exact-JSON `PASS`, and required machine/assurance gates are current for the final revision.
- `AC-012`: One actual GUI-001 procedure at the pinned environment passes every numbered observable and retains every exact real artifact; absent capability yields only truthful `GAP-001`, workflow `HOLD`, and no GUI or verified seal artifact.
- `AC-013`: The final handoff states exact implemented/evidenced IDs, exclusions/gaps, local revision, commands/results, seal truth, optional-interview boundary, and the pinned not-parity/not-delivered sentence without claiming excluded or unobserved behavior.

Browser acceptance procedure, at Chromium viewport `1280x720`, locale `en-US`, keyboard layout US, device-pixel ratio `1`, default seed, and empty storage:

1. Run `npm start` and confirm the server reports `127.0.0.1:8000`.
2. Open `http://127.0.0.1:8000/` in the named browser and record browser name/version and observer identity.
3. Confirm exact heading/button/hotbar/control labels, `Ready. Select Start to play.`, `No saved changes.`, Meadow selected, crosshair hidden, the pinned region/target/focus behavior, deterministic terrain, and absence of console errors. Do not score any `MAY_DIFFER` style.
4. Select Start; observe `Requesting pointer lock.`, then confirm canvas pointer ownership, `PLAYING`, `Playing.`, and visible crosshair.
5. Exercise forward/diagonal/opposite-key movement, collision with a block, one grounded jump, positive/negative mouse look, positive/negative keyboard look, non-repeating P pause, and confirmed Start resume.
6. Break one non-foundation block, select `timber`, place one `timber` block, select another block once in each wheel direction and by a number key, and confirm every exact status and hotbar state.
7. Press non-repeating `P`, wait for `pointerlockchange`, and confirm `PAUSED` with status `Paused.` before activating Save. Confirm `save-state` is `Saved.`, reload, and confirm the edit, player state, and selection persist in `READY`.
8. Open Reset, select Cancel and prove no change; reopen Reset, select Confirm and prove the seed-1337 baseline returns.
9. Inspect the browser network log and confirm only same-origin static files were requested and no application-initiated request occurred after module load.
10. Retain the exact GUI-001 artifacts below only when each artifact was actually captured from this running build.

GUI evidence authority is rooted at `docs/clone/evidence/manual/GUI-001/` and uses exactly these paths:

```text
docs/clone/evidence/manual/GUI-001/procedure.md
docs/clone/evidence/manual/GUI-001/ready.png
docs/clone/evidence/manual/GUI-001/gameplay.png
docs/clone/evidence/manual/GUI-001/persistence.png
docs/clone/evidence/manual/GUI-001/console.log
docs/clone/evidence/manual/GUI-001/network.json
docs/clone/evidence/manual/GUI-001/observation.json
```

- `ready.png` captures the state after procedure step 3; `gameplay.png` captures the PLAYING world and hotbar after step 6; `persistence.png` captures the restored edit, player state, and selection after step 7 and before reset.
- `console.log` is the UTF-8 console capture for the complete procedure. When the captured console contains no messages, its entire content is exactly `NO CONSOLE MESSAGES` followed by one LF; an empty placeholder is forbidden.
- `network.json` is canonical JSON with root property order `browser, captureStart, captureEnd, requests`. `browser` has string properties `name, version`; capture times are UTC RFC 3339 strings. Each request uses property order `sequence, method, url, status, initiator, observedAt`, where `sequence` is a one-based integer, `method`, absolute `url`, and `initiator` are strings, `status` is the observed integer HTTP status, and `observedAt` is a UTC RFC 3339 string; order requests by `sequence`. It contains actual captured requests, not a source-code-derived prediction.
- `observation.json` is canonical JSON with root property order `evidenceId, result, observer, browser, environment, steps, artifacts`. `evidenceId` is `GUI-001`; `result` is `PASS` only when all ten procedure steps pass and otherwise `HOLD`; `observer` is the nonempty human or authorized-agent identity; `browser` has exact `name, version`; `environment` records the exact viewport width/height, locale, keyboard layout, DPR, seed, and initial-storage state; `steps` has one ordered entry per procedure step with one-based `step`, `result` of `PASS` or `HOLD`, and nonempty exact `observed` text; `artifacts` maps each other retained GUI-001 repository-relative path to its lowercase 64-character SHA-256.
- `procedure.md` records the exact `npm start` command and exit, the exact installed observer/browser commands or UI operations used, UTC start/end timestamps, observer identity, browser name/version, each numbered expected-versus-observed result, and the output and exit from this exact hash command run after capture:

```text
sha256sum docs/clone/evidence/manual/GUI-001/ready.png docs/clone/evidence/manual/GUI-001/gameplay.png docs/clone/evidence/manual/GUI-001/persistence.png docs/clone/evidence/manual/GUI-001/console.log docs/clone/evidence/manual/GUI-001/network.json
```

After all seven GUI-001 files are finalized, invoke exactly the following command with `<skill-root>` already resolved and `<actual-observer-identity>` replaced only by the same nonempty identity recorded in both JSON and procedure; do not invoke it for a partial capture:

```text
python3 <skill-root>/scripts/clone_pack.py record-manual docs/clone --test TEST-011 --procedure MINECRAFT_CLONE_PROMPT.md --observer "<actual-observer-identity>" --authority DEC-001 --artifact evidence/manual/GUI-001/procedure.md --artifact evidence/manual/GUI-001/ready.png --artifact evidence/manual/GUI-001/gameplay.png --artifact evidence/manual/GUI-001/persistence.png --artifact evidence/manual/GUI-001/console.log --artifact evidence/manual/GUI-001/network.json --artifact evidence/manual/GUI-001/observation.json
```

Do not create the `GUI-001` directory, any named GUI-001 file, a blank file, or synthetic browser output before an actual browser observation begins. For a partial real capture, retain only files containing actual observations, set any created `observation.json` result to `HOLD`, enumerate missing artifacts, do not invoke `record-manual`, and do not use GUI-001 as passing evidence. If installed observer capability became unavailable, record those facts in `GAP-001`; if a product observation mismatched the contract, retain it as a current verification blocker and do not create a gap.

If an already-installed, repository-authorized browser observer can execute this exact procedure without downloads or dependency changes, use it and retain its version and artifacts. Otherwise do not install Playwright or a browser, do not create any `GUI-001` path, complete machine-verifiable code, record browser proof as `UNKNOWN_BLOCKER`, create exactly `GAP-001` with class `EVIDENCE_GAP`, state `BLOCKED`, and the exact procedure above, return workflow `HOLD`, and do not create a `verified-mvp` seal.

## 13. Explicit exclusions and post-MVP handling

The following are outside this MVP by authority decision: crafting, recipes, inventory quantities, durability, item drops, mobs, NPCs, combat, health, hunger, fluids, weather, day/night, sound, music, multiplayer, networking, accounts, backend services, cloud saves, infinite chunks, biomes, caves, structures, modding, target-compatible saves or protocols, mobile, touch, gamepad, VR, localization, production hosting, target content, and target visual parity.

Do not describe an excluded item as implemented, planned, or implementation-ready. In `gaps_analysis.md`, retain the exact MVP/browser evidence state and the authority exclusions. The only current-run gap ID is conditional `GAP-001` for unavailable GUI evidence. A missing required product behavior remains a verification blocker and MUST NOT be converted into a deferred gap. Any other gap requires a later explicit authority revision and is not authored during this run. `GAP-001` contains one resolution question—`Can an already-installed, repository-authorized Chromium observer execute GUI-001 without downloads or dependency changes?`—and no fabricated change map.

After the MVP handoff, offer one optional next action: a separate human interview for post-MVP scope. Do not start it without an affirmative response. In that later session, interview one feature group at a time, obtain exact observable behavior and acceptance decisions, inspect current repository truth, use web research only against primary technical sources needed for the selected implementation, and run `gap-plan`.

An affirmative interview produces these exact conditional-session records under the existing clone pack:

```text
docs/clone/post-mvp/interview_record.md
docs/clone/post-mvp/usability_critique.md
docs/clone/post-mvp/adoption_sprints.md
```

- `interview_record.md` records each question, the human's answer without semantic rewriting, the resulting authority decision, affected gap/requirement IDs, and unresolved question. It contains no inferred answer.
- `usability_critique.md` contains only evidence-backed findings. Each finding has a `USE-###` ID, cited interview/run/GUI evidence ID, exact observed friction, affected user and workflow, severity, acceptance impact, and a measurable correction criterion. An unevaluated surface is labeled `NOT_OBSERVED` and is not assigned a usability conclusion.
- `adoption_sprints.md` labels every adoption statement either `OBSERVED` with retained evidence or `HYPOTHESIS_UNVALIDATED`. Each hypothesis states target user, adoption trigger, expected observable behavior, measurement method, pass/falsification threshold, and evidence required; it is never phrased as a prediction or fact. The file then lists dependency-ordered sprint slices. Every slice has an ID, linked authorized gap and requirements, exact included/excluded behavior, predecessor IDs, affected paths or an explicit path-discovery gate, discriminating tests, entry gate, exit gate, rollback/recovery boundary, and terminal handoff. A slice cannot enter implementation until every entry gate is evidenced.
- Every researched technical claim records primary-source title, URL, access time, exact supported decision, and affected requirement. If primary support or repository evidence is unavailable, label the claim `NOT_VERIFIED`, create the corresponding blocked evidence gap, and exclude it from a sprint entry gate.

Update `gaps_analysis.md` with reciprocal links to these records and the gap-plan result. No post-MVP item becomes implementation-ready until its exact behavior is authority-approved, research claims are verified or explicitly excluded, affected repository paths are evidenced, acceptance tests and rollback boundaries are pinned, and its dossier passes the skill's gap-plan semantic and machine contracts.

## 14. HALT and terminal handoff

The codes below are terminal diagnostic codes, not clone-index graph IDs; do not create index records whose IDs use these codes.

HALT rather than guess when any of these occurs:

- `RIGHTS-001`: requested distribution, branding, content, or target-specific fidelity exceeds the authority above;
- `REPO-001`: the initial workspace contains an undeclared entry or a path collision occurs;
- `ENV-BLOCK-001`: Git, Node 18+, npm, Python 3.10+, or the local server capability is unavailable;
- `STACK-BLOCK-001`: the live `static-web-esm` catalog contract differs, a dependency appears necessary, or an implementation would require network installation;
- `SPEC-001`: a requested change alters world dimensions, terrain, physics, controls, persistence, security, MVP scope, or an acceptance outcome without a new authority decision;
- `EVIDENCE-001`: required reference, clone, browser, or parity evidence cannot be obtained with installed authorized capabilities;
- `INSTRUCTION-001`: a repository instruction conflicts with this request.

For one blocker, report the ID, evidence checked, affected requirement/criterion, current safe state, and one decision question. Preserve prior evidence and product files; do not weaken tests, remove the blocker, or substitute an inferred value.

Stop at a local verified-or-`HOLD` handoff. Do not deploy, publish, push, open or merge a pull request, or claim production readiness. The final handoff MUST state:

- mode and product type/playbook;
- prompt SHA-256 and `USER_PINNED` authority boundary;
- exact repository revision or full-tree diff identity;
- pack path and highest passing profile;
- every command, exit, and retained evidence path;
- implemented and machine-verified requirement/acceptance IDs;
- actual browser/GUI evidence state and observer/browser version, or the exact blocked evidence gap;
- `gaps_analysis.md` counts, IDs, status, exclusions, and next dependency-safe action;
- seal path only if a valid `verified-mvp` seal exists; and
- the exact boundary: `Not Minecraft parity. Not deployed, published, pushed, or merged.`
