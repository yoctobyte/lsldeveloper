# LSL Language & Environment Quirks Inventory

This document tracks the specific behaviors, limitations, and "gotchas" of the Linden Scripting Language (LSL) and the Second Life / OpenSimulator environment.

## 1. Language Syntax & Ambiguities

### Vector/Rotation Literals vs. Comparison Operators
The tokens `<` and `>` are used for both vector/rotation literals and comparison operators.
- `<1.0, 2.0, 3.0>` (Vector)
- `a < b > c` (Comparison: `(a < b) > c`)
- **Resolution**: Context-sensitive parsing. If a comma-separated list of 3 or 4 floats/expressions is found after `<`, it's a literal.

### Type Casts vs. Parenthesized Expressions
- `(integer)var` (Cast)
- `(a + b) * c` (Grouping)
- **Resolution**: Single-token lookahead after `)`. If the token is an identifier or another cast, it's likely a cast. If it's an operator, it's grouping.

### Integer Literals & Overflow
- LSL integers are 32-bit signed (`-2,147,483,648` to `2,147,483,647`).
- `0x80000000` is parsed as `-2147483648`.
- Overflow/Underflow wraps around (standard 2's complement).

## 2. Type System & Typecasting

### Implicit vs. Explicit Coercion
- **Implicit**: Only `integer` to `float` is implicit (e.g., `float f = 1;`).
- **Explicit**: Required for almost everything else: `(string)1`, `(integer)"123"`.
- **Strict String Typing**: Unlike many scripting languages, LSL does **not** implicitly convert numbers to strings during concatenation.
  - `string s = "Score: " + 10;` **(ERROR)**
  - `string s = "Score: " + (string)10;` **(CORRECT)**
- **List Overloading**: The `+` operator is overloaded for lists. Adding a non-list to a list implicitly appends it as an element.
  - `list l = ["a"] + 1;` -> `["a", 1]`

### String Serialization
- `(string)float`: Results in 6 decimal places (e.g., `"1.000000"`).
- `(string)vector`: Results in `"<1.00000, 2.00000, 3.00000>"` (6 decimal places).
- `(string)rotation`: Results in `"<0.00000, 0.00000, 0.00000, 1.00000>"` (6 decimal places).
- **Key vs String**: A `key` can be used as a `string` without casting in many function calls, but variables are distinct types.

## 3. Script & Object Memory

### Script Limits
- **Mono**: 64KB (standard for modern scripts).
- **LSO**: 16KB (legacy).
- Memory includes bytecode, stack, and heap.

### Linkset Data (LSD) — Shared Object Storage

Introduced ~2022 and the preferred alternative to link-message-based state sharing. Think of it as a per-linkset key-value store that all scripts in the object can read and write.

**Limits**
- **128 KB** total per linkset (stored on the root prim)
- Max **4096** key-value pairs
- Keys and values are both `string`; cast other types before storing

**Persistence** — survives script resets, `llResetScript()`, object rezzing, and region restarts. Does **not** survive `llLinksetDataReset()` or the object being deleted.

**Core API**

| Function | Returns | Notes |
|---|---|---|
| `llLinksetDataWrite(name, value)` | `integer` 0=OK | Create or overwrite a key |
| `llLinksetDataRead(name)` | `string` | Returns `""` if key absent |
| `llLinksetDataDelete(name)` | `integer` 0=OK | Remove a single key |
| `llLinksetDataReset()` | `integer` | Remove **all** keys |
| `llLinksetDataCountKeys()` | `integer` | Number of keys currently stored |
| `llLinksetDataFindKeys(pattern, start, count)` | `list` | Regex search on key names; paginates with start+count |

**Protected writes** (cross-script locking)

Scripts can lock individual keys so only code that knows the token can touch them:
```lsl
llLinksetDataWriteProtected(string name, string value, string token)
llLinksetDataReadProtected(string name, string token)
llLinksetDataDeleteProtected(string name, string token)
```

**`linkset_data` event**

Fires in every script in the linkset when any key changes:
```lsl
linkset_data(integer action, string name, string value) { ... }
```
`action` constants:
- `LINKSETDATA_UPDATE` — key was written or overwritten
- `LINKSETDATA_DELETE` — key was deleted
- `LINKSETDATA_RESET` — all data was cleared
- `LINKSETDATA_PROTECTED_UNSET` — a protected key was accessed with the wrong token

**Patterns used in this project**
- Engine writes board geometry at start (`BOARD_POS`, `BOARD_SCALE`, `BOARD_ROT`, `SPAWN_POS`, `FINISH_POS`) so rezzed walkers/towers read them without any chat protocol.
- `REZZ_POS_<seq>` written before `llRezObject`; the spawned object reads it, calls `llSetRegionPos`, then deletes the key — zero-overhead sim-wide transport.
- `WALKER_HP` / `WALKER_SPEED` written after each level-notecard load so every walker in the wave shares the same stats.
- `ROAD_x_y` / `WALL_x_y` used as a 2-D boolean grid burned into LSD at game start for fast O(1) occupancy checks.
- `llLinksetDataReset()` called on new game to guarantee a clean slate.

### SLua (Luau) Integration (2026 Beta)
- As of early 2026, **SLua** (based on Luau) is in open beta.
- Offers native tables, better memory management (~50% reduction), and significantly higher performance than Mono.
- *Note: We are currently targeting standard LSL (Mono), but architecture should be modular to allow SLua migration.*

## 4. Execution Model & Events

### Event-Driven
- Scripts are state machines.
- One event handler runs to completion before the next starts (no true threading).
- Max event queue size: **64 events**. New events are dropped if the queue is full.

### Common Events & Quirks
- `state_entry`: Fired on script start or state transition.
- `changed`: Fired for many reasons (inventory change, link change, owner change, etc.).
- `timer`: Registered via `llSetTimerEvent(float)`. Only one timer per script.
- `listen`: Registered via `llListen(channel, name, id, msg)`.

### Delays (Built-in)
- Many `ll*` functions have hard-coded delays (e.g., `llInstantMessage` = 2.0s, `llRezObject` = 0.1s).
- `llSleep(float)` yields the script for the duration.

## 5. Multi-Script Interaction

- **Link Messages**: `llMessageLinked(link, num, str, id)` is the classic way to communicate between scripts.
- **LSD as Shared Memory**: Modern scripts use LSD to avoid complex `link_message` protocols for simple state sharing.
- **Root vs Child**: Scripts in different prims can communicate just as easily as scripts in the same prim if they are in the same linkset.

## 6. Environment & Simulator Quirks

### Coordinates
- Regions are 256x256m.
- Global coordinates vs. Local coordinates (within linkset).
- Floating point precision issues at high altitudes or far from region center.

### Physics
- `llSetStatus(STATUS_PHYSICS, TRUE)`.
- Physical objects have strict limits (mass, complexity).

### Permissions
- Some actions require user permission (e.g., `llRequestPermissions(id, PERMISSION_DEBIT | PERMISSION_TAKE_CONTROLS)`).
- Permissions are granted per-script.

## 7. Constants & Special Values

- **TRUE / FALSE**: Integer constants `1` and `0`. There is no boolean type.
- **NULL_KEY**: `"00000000-0000-0000-0000-000000000000"`.
- **EOF**: The string `"\n\n"` (double newline). Returned by dataserver functions when the end of a notecard is reached.
- **ZERO_VECTOR**: `<0.0, 0.0, 0.0>`.
- **ZERO_ROTATION**: `<0.0, 0.0, 0.0, 1.0>`.

## 8. Math & Logic

- **Integer Division**: Standard C-style. `5 / 2` results in `2`.
- **Float Precision**: LSL uses 32-bit single-precision IEEE 754 floats. Calculations may differ slightly from Python's 64-bit floats.
- **Bitwise Operators**: `&`, `|`, `^`, `~`, `<<`, `>>` only work on `integer` types.
- **Logical Operators**: `&&`, `||`, `!` are "short-circuiting" but only work on `integer` (0 is false, non-zero is true).

## 9. Application Development & Optimization

Developing complex applications in LSL requires working within tight resource constraints (64KB per script).

### Memory-Saving Hacks
- **List-to-string casting for formatted output**: Casting a mixed list to `(string)` concatenates all elements without explicit typecasts or `+` operators. This is shorter to write and compiles to fewer bytes than chained string concatenation:
  ```lsl
  // Verbose — each variable needs an explicit cast and + operator:
  llOwnerSay("varA=" + (string)varA + "; vecB=" + (string)vecB + "; floatC=" + (string)floatC);

  // Compact — one cast, no operators between elements:
  llOwnerSay((string)["varA=", varA, "; vecB=", vecB, "; floatC=", floatC]);
  ```
  Works with any mix of `integer`, `float`, `vector`, `rotation`, `key`, and `string` elements. The list literal is only used as a conversion vehicle — it is not assigned to a variable.

- **Bitfields**: Store up to 32 boolean flags in a single `integer` using bitwise operators (`&`, `|`).
- **LSD as "Virtual Heap"**: Move large datasets, configuration, or non-immediate state into **Linkset Data**. This frees up the script's 64KB Mono heap for active processing.
- **String Packing**: Instead of long lists of strings (which have high overhead in Mono), store data as a single CSV or delimited string and unpack as needed using `llParseString2List`.
- **JSON Support**: `llJsonGetValue` and `llJsonSetValue` allow for structured data storage in strings, though parsing has a CPU cost.
- **List Reuse**: Avoid creating many temporary lists. Reassigning to an existing list variable can sometimes help with fragmentation.
- **Clearing Variables**: Set large strings or lists to `""` or `[]` as soon as they are no longer needed to trigger garbage collection.

### Inter-Script Communication Strategies
- **Link Messages (`llMessageLinked`)**: 
  - **Pros**: Fast, event-driven, supports a `key` (id) and `integer` (num) parameter for metadata.
  - **Cons**: Can "flood" the event queue if too many scripts are listening; limited payload size (one string).
- **Linkset Data (`llLinksetDataWrite`)**:
  - **Pros**: Shared state persistency; avoids "lost" messages (state is always there); multiple scripts can poll or react to `linkset_data` events.
  - **Cons**: Slightly higher overhead than a direct message; **128 KB** total limit for the whole linkset (not per-script).
- **Global Storage**: For data that must persist even if the object is deleted and re-rezzed, use **Experience KVP** (requires Experience permissions).

### Scaling beyond 64KB
- **Modular Scripts**: Split the application into "Core", "UI", "Comms", and "Data" scripts.
- **Memory Tracking**: Use `llGetUsedMemory()` and `llGetFreeMemory()` to monitor headroom.
- **Script Reset**: Design scripts to be "stateless" by storing critical data in LSD, allowing them to be reset (clearing fragmentation) without losing application state.
