# LSL Developer Toolchain — Implementation Plan (Finalized)

## Background

LSL (Linden Scripting Language) is a C-ish scripting language used in Second Life / OpenSimulator. Existing tools are outdated. The goal is to build a modern, fully compliant LSL developer toolchain in Python that:

- Parses and executes LSL scripts with full language compliance
- Simulates the complete Second Life execution environment (World → Sim → Parcel → Object → Script)
- Supports multiple scripts in linked objects
- Emulates avatars (users) with chat on all channels
- Emulates dialogs, sensors, timers, and the dataserver
- Does **not** render objects visually, but preserves all attributes
- Provides a CLI/REPL test harness and scriptable scenario system

---

## Locked-In Decisions

| Decision | Choice | Notes |
|---|---|---|
| **Language** | Python | Fast iteration, rich stdlib, easy REPL. *Rust or TypeScript are suggested long-term alternatives if performance or a web frontend becomes a requirement.* |
| **LSL Dialect** | SL LSL (Mono) primary | OSSL extensions are a future optional plugin layer. Default run mode will be "flex" (permissive) to tolerate community script hacks. |
| **Parser strategy** | Hand-written recursive descent | See rationale below. No parser generators. |

### Why Hand-Written Recursive Descent?

LSL has two constructs that are genuinely ambiguous for standard parser generators:

1. **Vector/rotation literals vs. comparison operators**
   ```lsl
   <1.0, 2.0, 3.0>   // vector literal
   a < b > c          // two comparison operators — identical token stream
   ```
   Resolution requires semantic context. Parser generators can't handle this without ugly hacks.

2. **Type casts vs. parenthesized expressions**
   ```lsl
   (integer)somevar   // cast — token after ) is an identifier, not an operator
   (a + b) * c        // grouping — token after ) is an operator
   ```
   Solvable only with single-token lookahead after `)`. Not cleanly expressible in BNF.

3. **Typing overload / implicit coercions** are *semantic* rules anyway — a parser generator only helps with syntax; we write the semantic pass ourselves regardless.

A recursive descent parser in Python handles all of these naturally, produces precise error messages, has zero external dependencies, and is straightforwardly extensible for OSSL later. Estimated size: ~1500 lines of clean Python.

---

## Project Layout

```
lsldeveloper/
├── core/
│   ├── lexer.py         # Tokenizer
│   ├── parser.py        # Recursive descent parser → AST
│   ├── ast_nodes.py     # AST node definitions
│   ├── types.py         # LSL type system (vector, rotation, list, key, etc.)
│   ├── interpreter.py   # Tree-walk interpreter
│   └── builtins/        # ll* function implementations (one module per category)
│       ├── comms.py     # llSay, llListen, llDialog, etc.
│       ├── object.py    # llGetPos, llSetPos, llGetOwner, etc.
│       ├── inventory.py # llGetNotecardLine, llGetInventoryName, etc.
│       ├── math.py      # llSin, llSqrt, llFloor, etc.
│       ├── list_ops.py  # llList2*, llListSort, etc.
│       ├── string_ops.py
│       ├── sensor.py
│       ├── timer.py
│       └── http.py      # optional
├── sim/
│   ├── world.py         # World singleton
│   ├── region.py        # Sim / Region
│   ├── parcel.py        # Parcel
│   ├── object.py        # Object (Linkset)
│   ├── prim.py          # Prim (with inventory)
│   ├── inventory.py     # Prim inventory items
│   ├── avatar.py        # Avatar / user emulation
│   └── dataserver.py    # Notecard / dataserver async emulation
├── events/
│   ├── loop.py          # Central tick-based event loop
│   ├── dispatcher.py    # Event routing to script queues
│   └── queue.py         # Per-script event queue (max 64, per SL spec)
├── harness/
│   ├── repl.py          # Interactive CLI / REPL
│   ├── scenario.py      # YAML scenario loader
│   └── assertions.py    # Test assertion API
├── tests/
│   ├── lsl/             # Test LSL scripts
│   └── test_*.py        # Python test cases
└── docs/
    ├── quirks.md        # Documented LSL gotchas and hacks
    └── builtins.md      # ll* function implementation status
```

---

## Component Details

### 1. Lexer (`core/lexer.py`)

Tokenizes LSL source into a flat token stream. Token types:

| Token type | Examples |
|---|---|
| Keywords | `if`, `else`, `while`, `for`, `do`, `return`, `state`, `jump`, `default` |
| Type keywords | `integer`, `float`, `string`, `key`, `vector`, `rotation`, `list` |
| Identifiers | variable names, function names, state names |
| Integer literals | `42`, `-1`, `0xFF`, `0x80000000` |
| Float literals | `3.14`, `-1.0`, `1.e3` |
| String literals | `"hello\nworld"` (with escape handling) |
| Operators | `+`, `-`, `*`, `/`, `%`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `&&`, `\|\|`, `!`, `~`, `&`, `\|`, `^`, `<<`, `>>`, `=`, `+=`, etc. |
| Punctuation | `(`, `)`, `{`, `}`, `[`, `]`, `,`, `;`, `@`, `<`, `>` |
| Comments | `//` single-line, `/* */` block — stripped |

Key edge cases:
- `<` and `>` are both operators AND vector/rotation delimiters — emitted as the same token; the parser resolves context
- Integer `0x80000000` = `-2147483648` (32-bit signed wrap — LSL-specific)
- Negative literals: `-1` is tokenized as unary minus + integer; no negative token

---

### 2. Parser (`core/parser.py`)

Hand-written recursive descent. Produces an AST.

**Grammar highlights** (informal):

```
program         := (global_decl | function_def | state_def)*
global_decl     := type IDENTIFIER ['=' expr] ';'
function_def    := type IDENTIFIER '(' params ')' block
state_def       := ('default' | 'state' IDENTIFIER) '{' event_handler* '}'
event_handler   := IDENTIFIER '(' params ')' block
block           := '{' statement* '}'
statement       := var_decl | assignment | expr_stmt | if_stmt | while_stmt
                 | for_stmt | do_while_stmt | return_stmt | state_change
                 | jump_stmt | label_stmt
type_cast       := '(' type_keyword ')' expr      -- lookahead: if token after ')' is not an operator
vector_literal  := '<' expr ',' expr ',' expr '>'  -- context-sensitive (3 or 4 components)
list_literal    := '[' (expr (',' expr)*)? ']'
```

**Ambiguity resolution:**
- After `(`, peek next token: if it's a type keyword AND the token after `)` is not a binary operator → it's a cast. Otherwise → parenthesized expression.
- After `<`, if we're in an expression and the context allows a vector/rotation → attempt vector parse. If comma-separated float-able exprs followed by `>` → vector/rotation. Else → comparison operator.

---

### 3. AST Nodes (`core/ast_nodes.py`)

Python dataclasses for each AST node:

```python
@dataclass
class VectorLiteral:    x: Expr; y: Expr; z: Expr
@dataclass
class CastExpr:         target_type: str; expr: Expr
@dataclass
class BinOp:            op: str; left: Expr; right: Expr
@dataclass
class FuncCall:         name: str; args: list[Expr]
@dataclass
class StateChange:      state_name: str
@dataclass
class EventHandler:     name: str; params: list; body: Block
@dataclass
class StateDef:         name: str; handlers: list[EventHandler]
# ... etc.
```

---

### 4. Type System (`core/types.py`)

Exact LSL semantics:

| LSL type | Python representation | Key semantics |
|---|---|---|
| `integer` | `int` (masked to 32-bit signed) | Overflow wraps; `0x80000000` = `-2147483648` |
| `float` | `float` (IEEE 754 single, via `struct.pack`) | 32-bit precision, not 64-bit |
| `string` | `str` | UTF-8, `\n` `\t` `\"` `\\` escapes |
| `key` | `str` (UUID format) | `NULL_KEY = "00000000-0000-0000-0000-000000000000"` |
| `vector` | `Vector(x,y,z)` class | Component-wise ops, dot product, magnitude |
| `rotation` | `Rotation(x,y,z,s)` class | Quaternion math, `ZERO_ROTATION` |
| `list` | `LSLList([...])` class | Heterogeneous, negative indexing, typed extraction |

Implicit coercions per LSL spec:
- `integer → float` (widening)
- `integer/float → string` (explicit cast)
- `list + any` → appends element (NOT concatenation)

---

### 5. Interpreter (`core/interpreter.py`)

Tree-walk interpreter. Per-script execution context:

```python
class ScriptContext:
    globals: dict          # global variable table
    current_state: str     # active state name
    call_stack: list       # for user-defined function calls
    event_queue: deque     # max 64 events (SL spec)
    memory_used: int       # tracked for 64KB limit
    listeners: dict        # active llListen handles
    timers: dict           # active llSetTimerEvent handles
```

Execution model:
- `state_entry` fired on script start or state change
- One event handler runs to completion before the next is dequeued
- `llSleep` yields back to the event loop (simulated time advance)
- Infinite loops are detected by instruction count limit (configurable)

---

### 6. World Model (`sim/`)

```
World (singleton)
└── Region (one or more)
    ├── name, UUID, position (global coords)
    ├── Parcels (list)
    │   └── area, owner_key, group_key, flags, landing_point
    ├── Avatars (dict by UUID)
    │   ├── key, display_name, legacy_name, position, rotation
    │   ├── chat_history (by channel)
    │   └── pending_dialogs (queue)
    └── Objects (dict by UUID)
        └── Linkset
            ├── root_prim_key
            └── Prims (ordered list, index = link number - 1)
                ├── key (UUID), name, description
                ├── position (local + global), rotation, scale
                ├── owner_key, group_key, creator_key
                ├── permissions (mask)
                ├── Inventory
                │   ├── Scripts  → ScriptContext instances
                │   ├── Notecards → {name: [lines]}
                │   └── Other items (metadata only)
                └── physical, phantom, temp_on_rez flags
```

---

### 7. Event Loop (`events/loop.py`)

```python
class SimLoop:
    tick_rate: float = 0.1   # simulated seconds per tick
    
    def tick(self):
        advance_timers()
        dispatch_pending_sensor_results()
        dispatch_pending_dataserver_results()
        process_one_event_per_script()   # cooperative multitasking
```

Event routing:
- Chat → find all matching `llListen` registrations → queue `listen` event
- Touch → queue `touch_start` / `touch` / `touch_end` on target prim's scripts
- Timer → queue `timer` on script that registered it
- Link message → queue `link_message` on target prims' scripts
- Dataserver → queue `dataserver` on script that called `llGetNotecardLine`

---

### 8. Avatar / User Emulation

Interactive (REPL) and scripted (YAML) control:

```python
class Avatar:
    def say(self, channel: int, message: str)   # fires listen events
    def touch(self, object_key: str, link_num: int = 1)
    def answer_dialog(self, channel: int, button: str)
    def answer_textbox(self, channel: int, text: str)
    def walk_to(self, position: Vector)
```

---

### 9. Dataserver & Notecard Emulation

- Notecards stored as `list[str]` (one entry per line) in prim inventory
- `llGetNotecardLine(name, line)` returns a query UUID and schedules an async `dataserver` event after a configurable delay (default: 1 tick)
- Returns `EOF` constant when line index ≥ line count
- `llGetNumberOfNotecardLines` uses same async mechanism (per SL spec)

---

### 10. Dialog & Listen Emulation

- `llDialog(avatar_key, message, buttons, channel)` → pushed to `Avatar.pending_dialogs`
- REPL displays it; operator types a button label → delivered as chat on the specified channel → fires `listen` in the script
- `llListen(channel, name, key, message)` → registered in `ScriptContext.listeners`
- Listener matching: channel must match; name/key/message = "" means wildcard

---

### 11. CLI / REPL Harness (`harness/repl.py`)

Commands:
```
spawn object "MyBox" at <128,128,25>
load script "door.lsl" into "MyBox"
start
tick [N]                        # advance N ticks (default 1)
as "Avatar Name" touch "MyBox"
as "Avatar Name" say 0 "Hello"
as "Avatar Name" answer dialog "OK"
expect chat 0 "Hello back!"
expect state "MyBox" "script.lsl" open
dump object "MyBox"             # print full prim + script state
```

YAML Scenario format:
```yaml
region: "Test Region"
objects:
  - name: MyBox
    position: [128, 128, 25]
    prims:
      - scripts: [door.lsl]
        notecards:
          config.txt: |
            line 1
            line 2
avatars:
  - name: Tester Resident
    position: [127, 128, 25]
steps:
  - touch: { avatar: Tester Resident, object: MyBox }
  - tick: 5
  - expect_chat: { channel: 0, message: "Door opened" }
  - expect_state: { object: MyBox, script: door.lsl, state: open }
```

---

## Phased Delivery

| Phase | Scope | Deliverable |
|---|---|---|
| **1** | Lexer + Parser + AST | Parse any valid LSL file; print AST |
| **2** | Type system + basic interpreter | Run expressions, global vars, functions (no events) |
| **3** | State machine + event loop | `state_entry`, `timer`, `listen` events; multi-state scripts |
| **4** | World model | Sim, Parcel, Object, Prim, Inventory, Avatar |
| **5** | `ll*` built-in library | All comms, object, math, list, string functions |
| **6** | Dataserver, dialogs, sensors, link messages | Full async event coverage |
| **7** | CLI/REPL + YAML scenarios + test assertions | Full test harness |
| **8** | OSSL extension layer | Optional, future |

---

## LSL Quirks Catalogue (to grow in `docs/quirks.md`)

- `<` and `>` are overloaded: vector/rotation delimiters AND comparison operators
- `(type)` cast syntax ambiguity with parenthesized expressions
- `list + value` appends, does NOT concatenate lists (use `list + list`)
- `integer` is strictly 32-bit signed; no unsigned arithmetic
- `float` is 32-bit IEEE 754 — LSL results differ from Python's 64-bit floats
- `0x80000000` is a valid integer literal = `-2147483648`
- Global variables may only be initialized with constant expressions (no function calls)
- `jump` / `@label` for intra-function goto (rare but valid)
- `state default;` vs `state foo;` — `default` is a reserved name
- `EOF` is a string constant `"\n\n"` not a keyword (dataserver quirk)
- `llList2String` on a list element that is already a string does NOT add quotes; on non-strings it serializes
- `TRUE` = `1`, `FALSE` = `0` — integer constants, not booleans
- `ZERO_VECTOR = <0,0,0>`, `ZERO_ROTATION = <0,0,0,1>`, `NULL_KEY = "00000000-..."`
- String + integer coercion: `"val: " + (string)42` required; `"val: " + 42` is a type error in strict mode

---

## Verification Plan

### Automated Tests
- **Phase 1**: Round-trip parse tests — parse LSL → serialize AST → compare
- **Phase 2–3**: Expression evaluation unit tests; state machine transition tests
- **Phase 5+**: Script integration tests — run a full script, assert event outputs
- Edge case scripts: list negative indexing, integer overflow, float precision, type coercion

### Manual Verification
- Load `door.lsl` (open/close door on touch), verify state transitions
- Load a vendor script (dialog-based purchase), emulate avatar interaction end-to-end
- Load a multi-prim linked object with scripts communicating via `llMessageLinked`

### Reference
- [LSL Portal](https://wiki.secondlife.com/wiki/LSL_Portal)
- [LSL Type article](https://wiki.secondlife.com/wiki/LSL_Type)
- Quirks catalogue maintained in `docs/quirks.md`
