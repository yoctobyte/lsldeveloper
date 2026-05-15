#!/usr/bin/env python3
"""
tools/memory_estimator.py — LSL Mono memory usage estimator

Estimates static (bytecode) and dynamic (heap) memory for an LSL script under
the Second Life Mono VM.  The hard limit is 65,536 bytes (64 KB) covering:

    base overhead  +  bytecode  +  string pool  +  global heap  +  active frame

─────────────────────── Reference values (Mono VM) ───────────────────────────
Sources:
  • wiki.secondlife.com/wiki/LSL_Script_Memory  (Jan 2013 Mono measurements)
  • wiki.secondlife.com/wiki/User:Becky_Pippen/Measure_Script_Memory_Usage
  • wiki.secondlife.com/wiki/User:Becky_Pippen/Memory_Limits_FAQ

BASE_OVERHEAD = 3,364 bytes
  Minimum memory consumed by an empty Mono script (Mono CLR runtime + LSL
  infrastructure + state machine scaffold + method descriptor tables).
  Source: Becky Pippen's measurements; referenced on LSL Script Memory wiki.

Global / state-scope variable heap costs (always allocated):
  integer     16
  float       16
  string      18 + 2 per character  (UTF-16; 18-byte object header)
  key         102                   (36-char UUID with Mono string header)
  vector      24                    (3 × float32 + CLR struct header)
  rotation    28                    (4 × float32 + CLR struct header)
  list        16 + per-element      (container header only)

Function / event-handler local variable costs (frame-allocated):
  integer     11
  float       11
  string       8 + 2 per character
  key         80   (8 + 36×2)
  vector      19
  rotation    23
  list        11 + per-element

List element costs (Mono, from LSL Script Memory wiki):
  integer     16
  float       16
  string      18 + 2 per character
  key         102
  vector      24
  rotation    28
  (interned string literals that repeat in a list may cost only 4 bytes;
   this estimator conservatively counts full cost for all elements)

Bytecode weights (CIL bytes per construct, from LSL Script Memory wiki):
  arithmetic / comparison op    1
  if statement                  6
  while / for loop             11
  function declaration         16 + 3 per parameter
  function call                21
  (remaining weights below are derived/estimated from CIL inspection)

─────────────────────── Model assumptions ─────────────────────────────────────
1. Only named variables (globals and active locals) consume heap. Intermediate
   expression results from nested ll* calls are transient — consistent with
   in-world llGetFreeMemory() behaviour.
2. String literals are deduplicated in the Mono metadata section; counted once
   in the "string pool" (static, part of the bytecode footprint).
3. LSL is single-threaded: only one event fires at a time. We report the
   largest single frame (worst-case active event/function). Nested user-function
   calls stack frames additively — noted as a caveat in the output.
4. All locals in a function body are counted simultaneously (conservative).
   The Mono compiler does not perform liveness analysis; all locals reserve
   slots for the full duration of the function call.
5. llGetFreeMemory() reports the historic low-water mark (worst-ever free),
   NOT current usage. Our estimate approximates current quiescent usage;
   dynamic string/list churn during heavy events can consume more.

Usage:
    python3 tools/memory_estimator.py script.lsl
    python3 tools/memory_estimator.py --json script.lsl
    python3 tools/memory_estimator.py file1.lsl file2.lsl ...
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.ast_nodes import (
    AssignmentStmt, BinOpExpr, BlockStmt, CastExpr, ComponentAccess,
    DoWhileStmt, EventHandler, ExprStmt, FloatLiteral, ForStmt,
    FuncCallExpr, FunctionDef, GlobalVar, IfStmt, IntegerLiteral,
    JumpStmt, LabelStmt, ListLiteral, ReturnStmt, RotationLiteral,
    Script, StateDef, StateChangeStmt, StringLiteral, UnaryOpExpr,
    VarDeclStmt, VariableExpr, VectorLiteral, WhileStmt,
)
from core.lexer import Lexer
from core.parser import Parser


# ── Hard limits ─────────────────────────────────────────────────────────────
SCRIPT_BUDGET = 65_536   # 64 KB hard limit

# ── Base overhead ────────────────────────────────────────────────────────────
# Minimum memory consumed by any Mono script regardless of content.
# Covers: CLR runtime, LSL infrastructure, state-machine scaffold,
# method descriptor tables for built-in ll* functions.
# Source: Becky Pippen / LSL Script Memory wiki.
BASE_OVERHEAD = 3_364

# ── Global / state-scope variable heap costs ─────────────────────────────────
# Variables declared at script top level; always resident in memory.
# Source: "State Variable Memory" table from LSL Script Memory wiki,
# string/key char costs doubled for Mono UTF-16 (wiki table was measured on LSO).
GLOBAL_TYPE_HEAP: dict[str, int] = {
    'integer':  15,
    'float':    15,
    'string':   12,   # header only; +STRING_CHAR_COST per character
    'key':      12,   # header only; UUID content (36 chars) added separately
    'vector':   31,
    'rotation': 39,
    'list':     16,   # container only; add per-element cost separately
}

# ── Function/event-handler local variable costs ───────────────────────────────
# Frame-allocated; only resident while the function/handler is active.
# Source: "Function-Level Variable Memory" table from LSL Script Memory wiki,
# char costs doubled for Mono UTF-16.
LOCAL_TYPE_HEAP: dict[str, int] = {
    'integer':  11,
    'float':    11,
    'string':    8,   # header only; +STRING_CHAR_COST per character
    'key':       8,   # header only; UUID content (36 chars) added separately
    'vector':   19,
    'rotation': 23,
    'list':     11,   # container only; add per-element cost separately
}

STRING_CHAR_COST = 2   # UTF-16: 2 bytes per code point in Mono

# ── List element costs (Mono) ─────────────────────────────────────────────────
# From LSL Script Memory wiki, "List Element Memory (Mono - Jan 2013)".
LIST_ELEM_COST: dict[str, int] = {
    'integer':  16,
    'float':    16,
    'string':   18,   # base; +STRING_CHAR_COST per character
    'key':      102,
    'vector':   24,
    'rotation': 28,
}

# ── Bytecode weights (bytes of CIL per AST construct) ────────────────────────
# Documented values from LSL Script Memory wiki:
BC_FUNC_PROLOGUE  = 16   # method header (wiki: 16 base)
BC_EVENT_PROLOGUE = 16   # event handlers use the same method prologue
BC_PARAM_COST     = 3    # per parameter (wiki: 3 per parameter)
BC_VAR_DECL       = 3    # local variable slot declaration
BC_ASSIGNMENT     = 3    # stloc / stfld
BC_BINARY_OP      = 1    # arithmetic / comparison instruction (wiki: 1 each)
BC_UNARY_OP       = 1
BC_FUNC_CALL      = 21   # call instruction + overhead (wiki: 21 base)
BC_IF_STMT        = 6    # brfalse/brtrue + jump (wiki: 6)
BC_LOOP_STMT      = 11   # back-edge branch + condition (wiki: 11)
BC_CAST           = 21   # LSL type casts compile to built-in function calls
BC_VAR_READ       = 2    # ldloc.s / ldarg.s
BC_COMPONENT      = 2    # ldfld on vector/rotation component
BC_LITERAL_INT    = 2    # ldc.i4.s (common small values; ldc.i4 = 5 bytes)
BC_LITERAL_FLOAT  = 5    # ldc.r4
BC_LITERAL_STR    = 5    # ldstr (5-byte metadata token; content in pool)
BC_LITERAL_VEC    = 16   # 3 × ldc.r4 + newobj
BC_LITERAL_ROT    = 21   # 4 × ldc.r4 + newobj
BC_LITERAL_LIST   = 5    # newarr
BC_LIST_ELEM      = 4    # box + stelem per element
BC_RETURN         = 2
BC_STATE_CHANGE   = 8
BC_JUMP           = 4
BC_LABEL          = 0    # labels produce no bytecode

# ── Assembly metadata overhead ────────────────────────────────────────────────
# Each unique external (ll*) function called requires a MemberRef table entry
# in the Mono assembly.  Each user-defined function/event handler gets a
# MethodDef entry.  These are part of the static binary, not the heap.
ASSEMBLY_MEMBERREF_COST = 12   # bytes per unique ll* function called
ASSEMBLY_METHODDEF_COST = 24   # bytes per user function or event handler


# ══════════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VarEntry:
    var_type: str
    name: str
    heap_bytes: int
    note: str = ""


@dataclass
class FrameReport:
    """Heap cost of a single function or event-handler call frame."""
    kind: str          # 'function' | 'event'
    state_name: str    # state name, or '' for top-level functions
    name: str
    params_bytes: int
    locals_bytes: int
    params: list[VarEntry] = field(default_factory=list)
    locals: list[VarEntry] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return self.params_bytes + self.locals_bytes

    @property
    def label(self) -> str:
        return f"{self.state_name}/{self.name}" if self.state_name else self.name


@dataclass
class MemoryReport:
    script_name: str
    bytecode_bytes: int
    string_pool_bytes: int
    string_pool_count: int
    assembly_bytes: int      # MemberRef + MethodDef metadata overhead
    ll_call_count: int       # unique ll* functions called
    global_vars: list[VarEntry]
    frames: list[FrameReport]
    warnings: list[str] = field(default_factory=list)

    @property
    def global_bytes(self) -> int:
        return sum(v.heap_bytes for v in self.global_vars)

    @property
    def static_bytes(self) -> int:
        return self.bytecode_bytes + self.string_pool_bytes + self.assembly_bytes

    @property
    def max_frame(self) -> Optional[FrameReport]:
        return max(self.frames, key=lambda f: f.total_bytes) if self.frames else None

    @property
    def conservative_total(self) -> int:
        """Base + static (bytecode+pool+assembly) + globals + worst-case frame."""
        mf = self.max_frame
        return (BASE_OVERHEAD + self.static_bytes + self.global_bytes
                + (mf.total_bytes if mf else 0))

    @property
    def budget(self) -> int:
        return SCRIPT_BUDGET

    @property
    def headroom(self) -> int:
        return self.budget - self.conservative_total

    @property
    def usage_pct(self) -> float:
        return 100.0 * self.conservative_total / self.budget


# ══════════════════════════════════════════════════════════════════════════════
# Heap-cost helpers
# ══════════════════════════════════════════════════════════════════════════════

def _string_content_cost(s: str) -> int:
    return len(s) * STRING_CHAR_COST


def _elem_cost(expr) -> int:
    """Heap cost of a single list element given its literal expression."""
    if isinstance(expr, IntegerLiteral):
        return LIST_ELEM_COST['integer']
    if isinstance(expr, FloatLiteral):
        return LIST_ELEM_COST['float']
    if isinstance(expr, StringLiteral):
        return LIST_ELEM_COST['string'] + _string_content_cost(expr.value)
    if isinstance(expr, VectorLiteral):
        return LIST_ELEM_COST['vector']
    if isinstance(expr, RotationLiteral):
        return LIST_ELEM_COST['rotation']
    # Variable / function call: unknown type — use string as conservative fallback
    return LIST_ELEM_COST['string']


def _var_heap_cost(var_type: str, init_expr=None,
                   is_global: bool = True) -> tuple[int, str]:
    """
    Return (heap_bytes, note) for a variable declaration.
    Uses GLOBAL_TYPE_HEAP for top-level globals, LOCAL_TYPE_HEAP for frame locals.
    When a literal initializer is present, content cost is computed exactly.
    """
    table = GLOBAL_TYPE_HEAP if is_global else LOCAL_TYPE_HEAP
    base = table.get(var_type, table['string'])
    note = ""

    if var_type == 'string':
        if isinstance(init_expr, StringLiteral):
            content = _string_content_cost(init_expr.value)
            note = f"{len(init_expr.value)} chars"
            return base + content, note
        return base, "empty"

    if var_type == 'key':
        # base is header-only (12 global / 8 local); content is always added.
        if isinstance(init_expr, StringLiteral):
            content = _string_content_cost(init_expr.value)
            note = f"{len(init_expr.value)} chars"
            return base + content, note
        # Default: NULL_KEY — 36-char UUID
        return base + 36 * STRING_CHAR_COST, "UUID (36 chars)"

    if var_type == 'list':
        if isinstance(init_expr, ListLiteral):
            elem_cost = sum(_elem_cost(e) for e in init_expr.elements)
            note = f"{len(init_expr.elements)} elems"
            return base + elem_cost, note
        return base, "empty"

    return base, ""


# ══════════════════════════════════════════════════════════════════════════════
# String-pool collector (unique literals → static metadata cost)
# ══════════════════════════════════════════════════════════════════════════════

def _collect_string_pool(node, pool: set[str]) -> None:
    """Walk any AST node and collect unique string literal values."""
    if node is None:
        return
    if isinstance(node, StringLiteral):
        pool.add(node.value)
        return
    if isinstance(node, (FunctionDef, EventHandler)):
        _collect_string_pool(node.body, pool)
        return
    if isinstance(node, StateDef):
        for h in node.handlers:
            _collect_string_pool(h, pool)
        return
    if isinstance(node, BlockStmt):
        for s in node.statements:
            _collect_string_pool(s, pool)
        return
    if isinstance(node, (GlobalVar, VarDeclStmt)):
        _collect_string_pool(node.initial_value, pool)
        return
    if isinstance(node, AssignmentStmt):
        _collect_string_pool(node.value, pool)
        return
    if isinstance(node, ExprStmt):
        _collect_string_pool(node.expr, pool)
        return
    if isinstance(node, BinOpExpr):
        _collect_string_pool(node.left, pool)
        _collect_string_pool(node.right, pool)
        return
    if isinstance(node, UnaryOpExpr):
        _collect_string_pool(node.right, pool)
        return
    if isinstance(node, CastExpr):
        _collect_string_pool(node.expr, pool)
        return
    if isinstance(node, ComponentAccess):
        _collect_string_pool(node.target, pool)
        return
    if isinstance(node, FuncCallExpr):
        for a in node.args:
            _collect_string_pool(a, pool)
        return
    if isinstance(node, ListLiteral):
        for e in node.elements:
            _collect_string_pool(e, pool)
        return
    if isinstance(node, VectorLiteral):
        for sub in (node.x, node.y, node.z):
            _collect_string_pool(sub, pool)
        return
    if isinstance(node, RotationLiteral):
        for sub in (node.x, node.y, node.z, node.s):
            _collect_string_pool(sub, pool)
        return
    if isinstance(node, IfStmt):
        _collect_string_pool(node.condition, pool)
        _collect_string_pool(node.then_branch, pool)
        _collect_string_pool(node.else_branch, pool)
        return
    if isinstance(node, WhileStmt):
        _collect_string_pool(node.condition, pool)
        _collect_string_pool(node.body, pool)
        return
    if isinstance(node, DoWhileStmt):
        _collect_string_pool(node.body, pool)
        _collect_string_pool(node.condition, pool)
        return
    if isinstance(node, ForStmt):
        for s in node.init:
            _collect_string_pool(s, pool)
        _collect_string_pool(node.condition, pool)
        for e in node.update:
            _collect_string_pool(e, pool)
        _collect_string_pool(node.body, pool)
        return
    if isinstance(node, ReturnStmt):
        _collect_string_pool(node.value, pool)
        return


def _collect_ll_calls(node, seen: set[str]) -> None:
    """Walk any AST node and collect unique ll* function names called."""
    if node is None:
        return
    if isinstance(node, FuncCallExpr):
        if node.name.startswith("ll"):
            seen.add(node.name)
        for a in node.args:
            _collect_ll_calls(a, seen)
        return
    # Recurse into children the same way as _collect_string_pool
    if isinstance(node, (FunctionDef, EventHandler)):
        _collect_ll_calls(node.body, seen); return
    if isinstance(node, StateDef):
        for h in node.handlers: _collect_ll_calls(h, seen)
        return
    if isinstance(node, BlockStmt):
        for s in node.statements: _collect_ll_calls(s, seen)
        return
    if isinstance(node, (GlobalVar, VarDeclStmt)):
        _collect_ll_calls(node.initial_value, seen); return
    if isinstance(node, AssignmentStmt):
        _collect_ll_calls(node.value, seen); return
    if isinstance(node, ExprStmt):
        _collect_ll_calls(node.expr, seen); return
    if isinstance(node, BinOpExpr):
        _collect_ll_calls(node.left, seen); _collect_ll_calls(node.right, seen); return
    if isinstance(node, UnaryOpExpr):
        _collect_ll_calls(node.right, seen); return
    if isinstance(node, CastExpr):
        _collect_ll_calls(node.expr, seen); return
    if isinstance(node, ComponentAccess):
        _collect_ll_calls(node.target, seen); return
    if isinstance(node, ListLiteral):
        for e in node.elements: _collect_ll_calls(e, seen)
        return
    if isinstance(node, VectorLiteral):
        for sub in (node.x, node.y, node.z): _collect_ll_calls(sub, seen)
        return
    if isinstance(node, RotationLiteral):
        for sub in (node.x, node.y, node.z, node.s): _collect_ll_calls(sub, seen)
        return
    if isinstance(node, IfStmt):
        _collect_ll_calls(node.condition, seen)
        _collect_ll_calls(node.then_branch, seen)
        _collect_ll_calls(node.else_branch, seen)
        return
    if isinstance(node, (WhileStmt,)):
        _collect_ll_calls(node.condition, seen); _collect_ll_calls(node.body, seen); return
    if isinstance(node, DoWhileStmt):
        _collect_ll_calls(node.body, seen); _collect_ll_calls(node.condition, seen); return
    if isinstance(node, ForStmt):
        for s in node.init: _collect_ll_calls(s, seen)
        _collect_ll_calls(node.condition, seen)
        for e in node.update: _collect_ll_calls(e, seen)
        _collect_ll_calls(node.body, seen)
        return
    if isinstance(node, ReturnStmt):
        _collect_ll_calls(node.value, seen)


def _string_pool_entry_cost(s: str) -> int:
    """
    Metadata cost for one unique string literal in the Mono assembly.
    Approx: 8-byte metadata table entry + 4-byte length + UTF-16 content.
    """
    return 12 + len(s) * STRING_CHAR_COST


# ══════════════════════════════════════════════════════════════════════════════
# Bytecode estimator
# ══════════════════════════════════════════════════════════════════════════════

def _bc(node) -> int:
    """Recursively estimate CIL bytecode bytes for an AST node."""
    if node is None:
        return 0

    if isinstance(node, FunctionDef):
        param_bc = len(node.parameters) * BC_PARAM_COST
        return BC_FUNC_PROLOGUE + param_bc + _bc(node.body)

    if isinstance(node, EventHandler):
        param_bc = len(node.parameters) * BC_PARAM_COST
        return BC_EVENT_PROLOGUE + param_bc + _bc(node.body)

    if isinstance(node, BlockStmt):
        return sum(_bc(s) for s in node.statements)

    if isinstance(node, VarDeclStmt):
        cost = BC_VAR_DECL
        if node.initial_value is not None:
            cost += _bc(node.initial_value) + BC_ASSIGNMENT
        return cost

    if isinstance(node, AssignmentStmt):
        return BC_ASSIGNMENT + _bc(node.value)

    if isinstance(node, ExprStmt):
        return _bc(node.expr)

    if isinstance(node, ReturnStmt):
        return BC_RETURN + _bc(node.value)

    if isinstance(node, IfStmt):
        cost = BC_IF_STMT + _bc(node.condition) + _bc(node.then_branch)
        if node.else_branch is not None:
            # else branch needs its own jump-over instruction
            cost += BC_IF_STMT // 2 + _bc(node.else_branch)
        return cost

    if isinstance(node, WhileStmt):
        return BC_LOOP_STMT + _bc(node.condition) + _bc(node.body)

    if isinstance(node, DoWhileStmt):
        return BC_LOOP_STMT + _bc(node.body) + _bc(node.condition)

    if isinstance(node, ForStmt):
        cost = BC_LOOP_STMT
        cost += sum(_bc(s) for s in node.init)
        cost += _bc(node.condition)
        cost += sum(_bc(e) for e in node.update)
        cost += _bc(node.body)
        return cost

    if isinstance(node, FuncCallExpr):
        arg_bc = sum(_bc(a) for a in node.args)
        return BC_FUNC_CALL + arg_bc

    if isinstance(node, BinOpExpr):
        return BC_BINARY_OP + _bc(node.left) + _bc(node.right)

    if isinstance(node, UnaryOpExpr):
        return BC_UNARY_OP + _bc(node.right)

    if isinstance(node, CastExpr):
        return BC_CAST + _bc(node.expr)

    if isinstance(node, VariableExpr):
        return BC_VAR_READ

    if isinstance(node, ComponentAccess):
        return BC_COMPONENT + _bc(node.target)

    if isinstance(node, IntegerLiteral):
        return BC_LITERAL_INT

    if isinstance(node, FloatLiteral):
        return BC_LITERAL_FLOAT

    if isinstance(node, StringLiteral):
        return BC_LITERAL_STR

    if isinstance(node, VectorLiteral):
        return BC_LITERAL_VEC + _bc(node.x) + _bc(node.y) + _bc(node.z)

    if isinstance(node, RotationLiteral):
        return BC_LITERAL_ROT + _bc(node.x) + _bc(node.y) + _bc(node.z) + _bc(node.s)

    if isinstance(node, ListLiteral):
        elem_bc = sum(_bc(e) + BC_LIST_ELEM for e in node.elements)
        return BC_LITERAL_LIST + elem_bc

    if isinstance(node, StateChangeStmt):
        return BC_STATE_CHANGE

    if isinstance(node, JumpStmt):
        return BC_JUMP

    if isinstance(node, LabelStmt):
        return BC_LABEL

    return 0


# ══════════════════════════════════════════════════════════════════════════════
# Local variable collector
# ══════════════════════════════════════════════════════════════════════════════

def _collect_locals(stmt) -> list[VarEntry]:
    """Collect all VarDeclStmt nodes in a statement tree (depth-first)."""
    result: list[VarEntry] = []
    if stmt is None:
        return result
    if isinstance(stmt, VarDeclStmt):
        cost, note = _var_heap_cost(stmt.type, stmt.initial_value, is_global=False)
        result.append(VarEntry(stmt.type, stmt.name, cost, note))
        return result
    if isinstance(stmt, BlockStmt):
        for s in stmt.statements:
            result.extend(_collect_locals(s))
        return result
    if isinstance(stmt, IfStmt):
        result.extend(_collect_locals(stmt.then_branch))
        result.extend(_collect_locals(stmt.else_branch))
        return result
    if isinstance(stmt, (WhileStmt,)):
        result.extend(_collect_locals(stmt.body))
        return result
    if isinstance(stmt, DoWhileStmt):
        result.extend(_collect_locals(stmt.body))
        return result
    if isinstance(stmt, ForStmt):
        for s in stmt.init:
            result.extend(_collect_locals(s))
        result.extend(_collect_locals(stmt.body))
        return result
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Main analysis
# ══════════════════════════════════════════════════════════════════════════════

def _make_frame(kind: str, state_name: str, name: str,
                parameters: list[tuple], body) -> FrameReport:
    params: list[VarEntry] = []
    for (ptype, pname) in parameters:
        cost, note = _var_heap_cost(ptype, is_global=False)
        params.append(VarEntry(ptype, pname, cost, note))

    locals_ = _collect_locals(body)
    return FrameReport(
        kind=kind,
        state_name=state_name,
        name=name,
        params_bytes=sum(v.heap_bytes for v in params),
        locals_bytes=sum(v.heap_bytes for v in locals_),
        params=params,
        locals=locals_,
    )


def estimate_memory(source: str, script_name: str = "<script>") -> MemoryReport:
    tokens = Lexer(source).tokenize()
    ast: Script = Parser(tokens).parse()

    global_vars: list[VarEntry] = []
    bytecode_total = 0
    warnings: list[str] = []

    for item in ast.globals:
        if isinstance(item, GlobalVar):
            cost, note = _var_heap_cost(item.type, item.initial_value, is_global=True)
            global_vars.append(VarEntry(item.type, item.name, cost, note))
        elif isinstance(item, FunctionDef):
            bytecode_total += _bc(item)

    # String pool — unique literals across the entire script
    pool: set[str] = set()
    for item in ast.globals:
        _collect_string_pool(item, pool)
    for state in ast.states:
        _collect_string_pool(state, pool)

    string_pool_bytes = sum(_string_pool_entry_cost(s) for s in pool)

    # Unique ll* function call sites → MemberRef assembly metadata
    ll_calls: set[str] = set()
    for item in ast.globals:
        _collect_ll_calls(item, ll_calls)
    for state in ast.states:
        _collect_ll_calls(state, ll_calls)

    # Frames: top-level functions + event handlers in all states
    frames: list[FrameReport] = []
    user_method_count = 0
    for item in ast.globals:
        if isinstance(item, FunctionDef):
            frames.append(_make_frame('function', '', item.name,
                                      item.parameters, item.body))
            user_method_count += 1
    for state in ast.states:
        bytecode_total += BC_EVENT_PROLOGUE
        for handler in state.handlers:
            bytecode_total += _bc(handler)
            frames.append(_make_frame('event', state.name, handler.name,
                                      handler.parameters, handler.body))
            user_method_count += 1

    assembly_bytes = (len(ll_calls) * ASSEMBLY_MEMBERREF_COST
                      + user_method_count * ASSEMBLY_METHODDEF_COST)

    # Warnings
    global_bytes = sum(v.heap_bytes for v in global_vars)
    total_est = (BASE_OVERHEAD + bytecode_total + string_pool_bytes
                 + global_bytes + (max(f.total_bytes for f in frames) if frames else 0))

    if global_bytes > 15_000:
        warnings.append(
            f"Global heap is {global_bytes:,} bytes — "
            "consider moving large lists/strings to Linkset Data."
        )

    large_lists = [v for v in global_vars
                   if v.var_type == 'list' and v.heap_bytes > 800]
    for v in large_lists:
        warnings.append(
            f"Global list '{v.name}' costs {v.heap_bytes:,} bytes. "
            "LSD can offload rarely-accessed data."
        )

    if frames:
        mf = max(frames, key=lambda f: f.total_bytes)
        if mf.total_bytes > 5_000:
            warnings.append(
                f"Frame '{mf.label}' uses {mf.total_bytes:,} bytes — "
                "large local strings/lists in hot paths increase peak usage."
            )

    if total_est > SCRIPT_BUDGET * 0.85:
        warnings.append(
            f"Estimated total {total_est:,} bytes exceeds 85% of the 64 KB "
            "budget — risk of 'Script run-time error: NRUNTIME' crash."
        )

    return MemoryReport(
        script_name=script_name,
        bytecode_bytes=bytecode_total,
        string_pool_bytes=string_pool_bytes,
        string_pool_count=len(pool),
        assembly_bytes=assembly_bytes,
        ll_call_count=len(ll_calls),
        global_vars=global_vars,
        frames=frames,
        warnings=warnings,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Formatters
# ══════════════════════════════════════════════════════════════════════════════

def _bar(used: int, total: int, width: int = 30) -> str:
    filled = int(width * used / total) if total else 0
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _kb(n: int) -> str:
    return f"{n / 1024:.1f} KB"


def format_report(r: MemoryReport) -> str:
    lines = []
    W = 64

    lines.append("═" * W)
    lines.append(f"  LSL Memory Estimate: {r.script_name}")
    lines.append("═" * W)

    lines.append("")
    lines.append("  STATIC (always present)")
    lines.append(f"  {'Mono base overhead':<38} {BASE_OVERHEAD:>7} bytes")
    lines.append(f"  {'Bytecode (CIL instructions)':<38} {r.bytecode_bytes:>7} bytes")
    lines.append(f"  {'String constant pool':<38} "
                 f"{r.string_pool_bytes:>7} bytes  "
                 f"({r.string_pool_count} unique literals)")
    lines.append(f"  {'Assembly metadata':<38} "
                 f"{r.assembly_bytes:>7} bytes  "
                 f"({r.ll_call_count} ll* refs + {len(r.frames)} methods)")
    lines.append(f"  {'Static subtotal':<38} "
                 f"{BASE_OVERHEAD + r.static_bytes:>7} bytes  "
                 f"{_kb(BASE_OVERHEAD + r.static_bytes)}")

    lines.append("")
    lines.append("  GLOBAL HEAP (always allocated)")
    if r.global_vars:
        for v in sorted(r.global_vars, key=lambda x: -x.heap_bytes):
            note = f"  [{v.note}]" if v.note else ""
            lines.append(f"    {v.var_type:<10} {v.name:<24} {v.heap_bytes:>6} bytes{note}")
    else:
        lines.append("    (none)")
    lines.append(f"  {'Global subtotal':<38} {r.global_bytes:>7} bytes  "
                 f"{_kb(r.global_bytes)}")

    lines.append("")
    lines.append("  CALL FRAMES (largest active frame counts toward total)")
    if r.frames:
        sorted_frames = sorted(r.frames, key=lambda f: -f.total_bytes)
        for fr in sorted_frames[:10]:
            tag = 'ev' if fr.kind == 'event' else 'fn'
            label = f"  {tag} {fr.label}"
            lines.append(f"  {label:<42} {fr.total_bytes:>5} bytes  "
                         f"({fr.params_bytes}p + {fr.locals_bytes}l)")
        if len(sorted_frames) > 10:
            lines.append(f"  ... ({len(sorted_frames) - 10} more frames)")
        mf = r.max_frame
        if mf:
            lines.append(f"  {'Largest frame':<38} {mf.total_bytes:>7} bytes  "
                         f"{_kb(mf.total_bytes)}")
    else:
        lines.append("    (none)")

    lines.append("")
    lines.append("─" * W)
    bar = _bar(r.conservative_total, r.budget)
    lines.append(f"  ESTIMATE  {r.conservative_total:>7} bytes  {_kb(r.conservative_total)}")
    lines.append(f"  BUDGET    {r.budget:>7} bytes  64.0 KB")
    lines.append(f"  HEADROOM  {r.headroom:>7} bytes  {_kb(r.headroom)}")
    lines.append(f"  {bar}  {r.usage_pct:.1f}%")

    if r.warnings:
        lines.append("")
        lines.append("  WARNINGS")
        for w in r.warnings:
            lines.append(f"  !  {w}")

    lines.append("")
    lines.append("  Calibration: compare with llGetUsedMemory() (current) or")
    lines.append("  llGetFreeMemory() (worst-ever free = most pessimistic).")
    lines.append("  Bytecode ±25%; type costs from LSL Script Memory wiki (Jan 2013).")
    lines.append("═" * W)
    return "\n".join(lines)


def format_json(r: MemoryReport) -> str:
    mf = r.max_frame
    return json.dumps({
        "script": r.script_name,
        "budget": r.budget,
        "estimate": r.conservative_total,
        "headroom": r.headroom,
        "usage_pct": round(r.usage_pct, 1),
        "breakdown": {
            "base_overhead": BASE_OVERHEAD,
            "bytecode": r.bytecode_bytes,
            "string_pool": r.string_pool_bytes,
            "string_pool_count": r.string_pool_count,
            "assembly_metadata": r.assembly_bytes,
            "ll_unique_calls": r.ll_call_count,
            "global_heap": r.global_bytes,
            "max_frame": mf.total_bytes if mf else 0,
        },
        "global_vars": [
            {"type": v.var_type, "name": v.name,
             "bytes": v.heap_bytes, "note": v.note}
            for v in r.global_vars
        ],
        "frames": [
            {"name": f.label, "kind": f.kind,
             "bytes": f.total_bytes,
             "params": f.params_bytes, "locals": f.locals_bytes}
            for f in sorted(r.frames, key=lambda f: -f.total_bytes)
        ],
        "warnings": r.warnings,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Estimate LSL Mono memory usage for one or more .lsl files."
    )
    ap.add_argument("files", nargs="+", metavar="FILE")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = ap.parse_args()

    results = []
    for path_str in args.files:
        path = Path(path_str)
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            continue
        try:
            report = estimate_memory(source, script_name=path.name)
        except Exception as e:
            print(f"ERROR parsing {path.name}: {e}", file=sys.stderr)
            continue

        results.append(report)
        if args.json:
            print(format_json(report))
        else:
            print(format_report(report))
            print()

    if not args.json and len(results) > 1:
        print("═" * 64)
        print("  SUMMARY")
        print(f"  {'Script':<36} {'Est.':>8}  {'%':>5}  {'Free':>8}")
        print("─" * 64)
        for r in sorted(results, key=lambda x: -x.conservative_total):
            flag = "!" if r.usage_pct > 85 else " "
            print(f"  {flag} {r.script_name:<34} "
                  f"{r.conservative_total:>7}b  "
                  f"{r.usage_pct:>4.1f}%  "
                  f"{r.headroom:>7}b free")
        total_est = sum(r.conservative_total for r in results)
        print("─" * 64)
        print(f"  {'Total across all scripts':<36} {total_est:>8}")
        print("═" * 64)


if __name__ == "__main__":
    main()
