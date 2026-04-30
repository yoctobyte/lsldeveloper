# LSL Developer Toolchain — Implementation Plan

## Background

LSL (Linden Scripting Language) is a C-ish scripting language used in Second Life / OpenSimulator. Existing tools are outdated. The goal is to build a modern, fully compliant LSL developer toolchain that:

- Parses and executes LSL scripts with full language compliance
- Simulates the complete Second Life execution environment (World → Sim → Parcel → Object → Script)
- Supports multiple scripts in linked objects
- Emulates avatars (users) with chat on all channels
- Emulates dialogs, sensors, timers, and the dataserver
- Does **not** render objects visually, but preserves all attributes
- Provides a CLI test harness and scriptable test framework

---

## User Review Required

> [!IMPORTANT]
> **Implementation Language**: No language has been chosen yet. Please confirm which to use:
> 1. **Python** — Fastest iteration, easiest for building the environment model and a REPL, best for scripting test cases.
> 2. **Rust** — Best performance and type safety for the AST/interpreter, can compile to a native binary or WebAssembly later.
> 3. **TypeScript/Node.js** — Best choice if you want a web-based IDE or graphical frontend later.
>
> My recommendation: **Python** to start fast and prove the design, then hot-swap the performance-critical core to Rust if needed.

> [!IMPORTANT]
> **LSL Dialect Target**: Should we target:
> 1. **Linden Second Life LSL (Mono)** — standard SL scripting
> 2. **OpenSimulator OSSL** — adds `os*` functions on top of LSL
> 3. **Both** — OSSL as an optional extension layer on top of SL LSL
>
> Recommended: SL LSL first, with OSSL as an optional plugin layer.

> [!WARNING]
> **Parser Strategy**: Write from scratch or use a parser generator?
> 1. **From scratch** — Maximum control over LSL quirks and error messages.
> 2. **Parser generator** (ANTLR, Lark/Python, pest/Rust) — Faster grammar iteration, proven tooling.
>
> Recommended: Use a parser generator with a hand-written grammar, since LSL has well-known quirks we need to encode precisely.

---

## Open Questions

1. Do you want a REPL (interactive shell) or only a batch script runner?
2. Should the test harness produce JUnit/TAP-compatible output for CI integration?
3. Do you want a scripted scenario format (YAML/TOML) for defining test environments?
4. Are HTTP-in / HTTP-out (`llHTTPRequest`, `llHTTPResponse`) in scope for emulation?

---

## Proposed Architecture

```
lsldeveloper/
├── core/               # Language: lexer, parser, AST, type system, interpreter/VM
├── sim/                # World model: World, Sim, Parcel, Object, Prim, Avatar, Inventory
├── builtins/           # All ll-function implementations (llSay, llListen, etc.)
├── events/             # Event loop, scheduler, event queue
├── harness/            # CLI, REPL, scenario loader, test assertions
├── tests/              # LSL test scripts and test suite
└── docs/               # Language quirks, design notes
```

---

## Component Breakdown

### 1. Core — LSL Language Engine

#### 1a. Lexer & Parser
- Tokenizes LSL source (keywords, types, operators, string literals, vector/rotation literals).
- Parses into an AST. Key LSL constructs:
  - States (`default`, `state foo`) and state transitions (`state foo;`)
  - Event handlers (`touch_start(integer num) { ... }`)
  - Data types: `integer`, `float`, `string`, `key`, `vector`, `rotation`, `list`
  - Control flow: `if/else`, `while`, `do/while`, `for`, `return`, `jump`, `@label`
  - Type casting: explicit `(type)value` casts with LSL semantics
  - String concatenation with `+`, list construction `[a, b, c]`
  - No unsigned integers; integer is 32-bit signed.

#### 1b. Type System
Implement exact LSL semantics including:
- `vector`: 3 floats, math operations, `<x,y,z>` literal syntax
- `rotation`: 4 floats (quaternion), `<x,y,z,s>` literal
- `list`: heterogeneous, negative indexing, `llList2*` extraction functions
- `key`: string alias representing UUIDs; `NULL_KEY` constant
- Integer overflow wraps at 32-bit signed
- Float precision matches IEEE 754 single precision (32-bit)
- String: UTF-8, supports escape sequences `\n`, `\t`, `\"`, `\\`

#### 1c. Interpreter / VM
- Tree-walk interpreter on the AST (for simplicity first; can be replaced with bytecode VM later).
- Per-script execution context:
  - Global variable table
  - Current `state`
  - Call stack (for user-defined functions)
  - Pending event queue (FIFO, max 64 events per LSL spec)
  - Mono memory limit tracking (64KB per script)

---

### 2. Simulator — World Model Hierarchy

```
World
└── Sim (Region)
    ├── Parcel(s)
    │   └── meta: area, owner, group, flags
    ├── Avatar(s)
    │   ├── UUID, name, position
    │   ├── Chat (all channels)
    │   └── Dialog answers
    └── Object (Linkset)
        ├── Root Prim + Linked Prims (1..N)
        │   ├── Attributes: UUID, position, rotation, scale, owner, group, name, desc, perms
        │   ├── Inventory
        │   │   ├── Scripts (LSL source + state)
        │   │   ├── Notecards (text files, line-addressable)
        │   │   └── Other items (textures, sounds, etc. — metadata only)
        │   └── Running Scripts (interpreter instance per script)
        └── Linkset-wide message bus (link messages)
```

Key behaviors to simulate:
- Each prim has its own inventory and can have multiple running scripts.
- Link numbers: root prim = 1, children = 2..N.
- Scripts in the same object can communicate via `llMessageLinked`.
- Objects can rez (spawn) child objects.

---

### 3. Event Loop & Scheduler

- A central tick-based event loop (configurable tick rate, default 100ms simulated time).
- An event dispatcher routes events to the correct script's event queue:

| Trigger | Event |
|---|---|
| Sim start / script reset | `state_entry` |
| Avatar touches prim | `touch_start`, `touch`, `touch_end` |
| Timer fires | `timer` |
| Sensor detects | `sensor` / `no_sensor` |
| Chat received on listened channel | `listen` |
| Link message sent | `link_message` |
| Notecard line read | `dataserver` |
| HTTP response received | `http_response` (optional) |
| Object collides | `collision_start`, `collision`, `collision_end` |
| Inventory changed | `changed` |

- Scripts process one event handler at a time (cooperative multitasking per SL spec).
- `llSleep` pauses the script; other scripts continue.

---

### 4. Built-in `ll*` Function Library

Organized by category:

| Category | Examples |
|---|---|
| Communication | `llSay`, `llWhisper`, `llShout`, `llRegionSay`, `llOwnerSay`, `llInstantMessage` |
| Listening | `llListen`, `llListenRemove`, `llListenControl` |
| Dialogs | `llDialog`, `llTextBox` |
| Timers | `llSetTimerEvent`, `llGetTime`, `llGetUnixTime` |
| Object properties | `llGetPos`, `llSetPos`, `llGetRot`, `llSetRot`, `llGetOwner`, `llGetKey`, `llGetObjectName` |
| Inventory | `llGetInventoryName`, `llGetInventoryType`, `llGetNotecardLine`, `llGetNumberOfNotecardLines` |
| Sensors | `llSensor`, `llSensorRepeat`, `llSensorRemove` |
| List manipulation | `llList2Integer`, `llList2String`, `llListSort`, `llDeleteSubList`, etc. |
| String ops | `llGetSubString`, `llStringLength`, `llStringTrim`, `llToUpper`, etc. |
| Math | `llSin`, `llCos`, `llSqrt`, `llFabs`, `llPow`, `llFloor`, `llRound`, etc. |
| Dataserver | `llGetNotecardLine` → fires `dataserver` event |
| Linking | `llMessageLinked`, `llGetLinkKey`, `llGetNumberOfPrims` |
| Permissions | `llRequestPermissions`, `run_time_permissions` event |
| Avatar | `llGetAgentInfo`, `llGetDisplayName` (mocked) |
| HTTP (optional) | `llHTTPRequest` → fires `http_response` event |

---

### 5. Avatar / User Emulation

- The harness lets the operator **be** an avatar:
  - Walk to a position
  - Touch a prim
  - Say text on a channel (`/channel message` syntax)
  - Answer a dialog (button choice)
  - Answer a text box
- Avatars can be scripted (YAML scenarios) or driven interactively via REPL.
- Multiple avatars can be emulated simultaneously.

---

### 6. Dataserver & Notecard Emulation

- Notecards are stored as plain text files in prim inventory.
- `llGetNotecardLine(name, line)` returns a `dataserver` query ID and schedules an async `dataserver` event.
- Simulates the async round-trip (configurable delay).
- `EOF` constant returned when line index exceeds notecard length (per SL spec).

---

### 7. Dialog & Chat Channel Emulation

- `llDialog(avatar_key, message, [buttons], channel)` — queued to a dialog inbox; the harness displays it and accepts a button response, which is delivered as a chat event on the specified channel.
- `llListen` / `llListenRemove` — a listener registry per script, matched against incoming chat events (channel, name, key, message pattern).
- Supports all channels including channel 0 (public), negative channels, and special channels.

---

### 8. CLI Test Harness

#### Interactive REPL mode:
```
> spawn object "MyBox" at <128,128,25>
> load script "door.lsl" into object "MyBox" prim 1
> start
> as avatar "Tester Resident" touch object "MyBox"
> chat /0 "Hello"
> expect chat "Hello back!"
```

#### Scripted scenario (YAML):
```yaml
world:
  region: "Test Region"
  objects:
    - name: MyBox
      position: [128, 128, 25]
      prims:
        - inventory:
            - type: script
              file: door.lsl
avatars:
  - name: Tester Resident
    position: [127, 128, 25]
steps:
  - action: touch
    avatar: Tester Resident
    object: MyBox
  - expect: chat
    channel: 0
    message: "Hello back!"
```

#### Test assertion API (for automated CI):
- `expect_chat(channel, message)` — assert that a chat event occurred
- `expect_dialog(avatar, buttons)` — assert that a dialog was sent
- `expect_state(script, state_name)` — assert current state of a script
- `expect_var(script, varname, value)` — assert global variable value

---

## Phased Delivery

| Phase | Scope |
|---|---|
| **Phase 1** | Lexer + Parser + AST, core types, basic interpreter (no events) |
| **Phase 2** | Event loop, state machine, `state_entry`/`timer`/`listen` events |
| **Phase 3** | World model: Sim, Parcel, Object, Prim, Inventory, Avatar |
| **Phase 4** | Full `ll*` built-in library (communications, object props, lists, math) |
| **Phase 5** | Dataserver, dialogs, link messages, sensors |
| **Phase 6** | CLI/REPL harness, scripted YAML scenarios, test assertions |
| **Phase 7** | OSSL extension layer (optional) |

---

## Verification Plan

### Automated Tests
- Collect trivial LSL examples from LSL wiki / community (e.g., Hello World, door open/close, vendor scripts).
- Run each through the interpreter and assert output events or state.
- Test edge cases: list negative indexing, integer overflow, float precision, type coercion.

### Manual Verification
- Load a multi-script linked object, send a chat command, verify that scripts communicate via `llMessageLinked` and respond correctly.
- Emulate a dialog interaction from avatar → script → dialog → button → chat response.

### LSL Reference
- Primary reference: [LSL Portal](https://wiki.secondlife.com/wiki/LSL_Portal)
- LSL quirks catalog to be maintained in `docs/quirks.md`
