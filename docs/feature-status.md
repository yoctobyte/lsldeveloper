# Feature Status

This is a working status snapshot for the Python-only offline LSL developer toolchain.

## Implemented Parser Coverage

- Global variable declarations with optional initializers.
- User functions with typed parameters and optional return type.
- `default` and named `state` blocks.
- Event handlers with typed parameters.
- Blocks, empty statements, local variable declarations, expression statements, and assignments.
- `if` / `else`, `for`, `while`, `do` / `while`, `return`, `state`, `jump`, and labels.
- Integer, float, string, vector, rotation, and list literals.
- Function calls, type casts, parenthesized expressions, component access, prefix/postfix `++` and `--`.
- Arithmetic, comparison, equality, logical, bitwise, shift, and compound-assignment operators.
- Line comments and block comments.
- Hex integer literals with 32-bit signed wrap.

## Implemented Runtime Coverage

- Global initialization and local variable scopes.
- User-defined function calls.
- Event queues with 64-event cap.
- `state_entry`, `state_exit`, `timer`, `touch_start`, `listen`, `link_message`, `sensor`, `no_sensor`, `dataserver`, and `http_response` dispatch when queued.
- State transitions clear queued events and enqueue the new state's `state_entry`.
- Basic avatar chat and touch simulation.
- Basic world/region/parcel/avatar/object/prim model with linkset data.
- Demo world seeding for offline scripts: one sandbox region, one parcel, selectable avatar density profiles, and a fixture object.
- Model-backed region, parcel, avatar, object detail, object transform, name lookup, chat/dialog, sensor, inventory/notecard dataserver, primitive params, and linkset data APIs.
- Stubbed API handlers for selected missing simulator functions. They print a console warning and return typed default values.
- Stored effect state for hover text, particles, texture animation, and basic sound calls.
- Vector, rotation, and list Python representations.
- Vector arithmetic, vector cross product, vector dot product, rotation multiplication, vector rotation.
- Casts between common scalar/string/vector/rotation/list forms.

## Known Missing Language Features

- `break` and `continue`.
- Full LSL compile-time validation for builtin signatures, event signatures, duplicate names, and type errors.
- Strict LSL assignment-expression restrictions.
- Full LSL integer overflow behavior across every arithmetic operation.
- Full 32-bit float precision semantics across every operation.
- Correct short-circuit evaluation for `&&` and `||`.
- Full string escape decoding.
- Full list slicing/index semantics for every list API.
- Full vector/rotation math parity with Second Life edge cases.
- Memory limits, script sleep/yield, and instruction limits.
- Include/preprocessor support, if any future dialect needs it.

## Known Missing Simulator Features

- Bounds-based multi-parcel routing. The current parcel model defaults to a single region parcel.
- Inventory transfer. Inventory query and notecard dataserver APIs have a basic current-prim model.
- Sensors are simplified: name/key/type/range filtering works against demo region entities, repeated scans can be removed, and detected accessors expose the simplified records; arc and true viewer/server detection semantics are not modeled yet.
- Dialogs are simplified: `llDialog` records the latest dialog and routes button clicks through normal chat listeners.
- Permissions and money/debit flows.
- Object rez, attach, detach, and inventory transfer.
- Physics, collisions, controls, camera, experience tools, pathfinding, media, and rendered particles/sound.
- Multi-script scheduling fairness beyond simple per-tick queue draining.
- Persistence for simulator state.

## Emulation Priority

- High: APIs that read/write simulator state, object metadata, parcels, avatars, inventory, dataserver, chat, HTTP, and inter-object communication.
- Medium: math/string/list APIs, because they unblock real scripts and are deterministic.
- Low: visual side effects such as particles, hover text, texture animation, sound, media, and camera effects. These can initially store requested parameters on the object/prim without rendering behavior.

## Example Corpus

Run parse-only checks:

```bash
python -m harness --examples --check
```

Run parser checks plus a short `state_entry` smoke test:

```bash
python -m harness --examples
```

`examples/unsupported_missing_api.lsl` is expected to parse and run through a stubbed `llTeleportAgent` handler. It keeps the report path visible for APIs that are still behaviorally missing.
