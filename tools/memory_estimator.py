#!/usr/bin/env python3
"""
tools/memory_estimator.py — LSL Mono memory usage estimator

Estimates static (bytecode) and dynamic (heap) memory for an LSL script under
the Second Life Mono VM.  The hard limit is 65,536 bytes (64 KB) covering:

    bytecode  +  string-constant pool  +  global heap  +  active call-frame

─────────────────────────── Reference values ──────────────────────────────────
Type sizes (Mono CLR, empirically measured in-world):
  Source: SLUniverse scripting forums, Linden Lab memory-usage experiments
  (2010-2022), and Mono CLR object layout specifications.

  Type        Heap cost (bytes)
  ─────────── ───────────────────────────────────────────────────────────────
  integer     4    — 32-bit value stored directly (no boxing for globals)
  float       4    — 32-bit IEEE 754 float
  string      36   — 16-byte CLR String header + 8-byte char[] header
                     + 2 bytes per character (UTF-16 in Mono)
  key         108  — string of exactly 36 UUID characters: 36 + 36×2
  vector      12   — 3 × float32
  rotation    16   — 4 × float32
  list        16   — list-object header (empty); +per-element below

  List element boxing (Mono boxes primitive value types stored in lists):
  integer     8    — boxed: 4-byte value + 4-byte CLR object header
  float       8    — same
  string      36 + 2×len
  key         108
  vector      12   (structs not boxed in the SL Mono runtime patch)
  rotation    16

Bytecode weights (bytes of CIL per AST construct) — rough estimates derived
from inspecting disassembled Mono CIL for typical LSL patterns (±25%):
  Calibrate against llGetUsedMemory() from in-world measurements.

─────────────────────── Model assumptions ─────────────────────────────────────
1. Only *named variables* (globals and locals while active) consume heap.
   Intermediate expression results from nested ll* calls are transient and
   released before the next event fires — consistent with in-world behaviour.
2. String literals are deduplicated in the metadata section and counted once
   in the "string pool" (static, part of bytecode footprint).
3. LSL is single-threaded: at most one event handler runs at a time.
   Frames from nested user-function calls are stacked and reported separately.
4. Local variables in branches (if/else, loops) are all assumed alive at peak —
   the LSL Mono compiler does not perform liveness analysis at the bytecode
   level, so all locals in a function body reserve stack space simultaneously.

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


# ── Hard limits ────────────────────────────────────────────────────────────
SCRIPT_BUDGET = 65_536   # 64 KB

# ── Heap cost per variable type (bytes) ────────────────────────────────────
TYPE_HEAP: dict[str, int] = {
    'integer':  4,
    'float':    4,
    'string':   36,
    'key':      108,
    'vector':   12,
    'rotation': 16,
    'list':     16,
}
STRING_CHAR_COST = 2   # UTF-16

# Heap cost for a list element of each type (boxed in Mono)
LIST_ELEM_COST: dict[str, int] = {
    'integer':  8,
    'float':    8,
    'string':   36,
    'key':      108,
    'vector':   12,
    'rotation': 16,
}

# ── Bytecode weights (bytes of CIL per AST construct) ──────────────────────
BC_FUNC_PROLOGUE  = 32   # method header, local-var table, return instruction
BC_EVENT_PROLOGUE = 24
BC_VAR_DECL       = 6    # local variable slot + optional ldloc init
BC_ASSIGNMENT     = 8    # stloc / stfld
BC_BINARY_OP      = 4    # add / sub / mul / div / and / or / clt …
BC_UNARY_OP       = 3
BC_FUNC_CALL      = 18   # call instruction (5 bytes) + argument push overhead
BC_IF_STMT        = 10   # brfalse/brtrue + nop overhead
BC_LOOP_STMT      = 14   # branch + back-edge + condition
BC_CAST           = 6
BC_VAR_READ       = 4    # ldloc / ldfld
BC_COMPONENT      = 6    # ldfld on a struct field
BC_LITERAL_INT    = 5    # ldc.i4
BC_LITERAL_FLOAT  = 5    # ldc.r4
BC_LITERAL_STR    = 5    # ldstr (pointer into metadata; content counted in pool)
BC_LITERAL_VEC    = 15   # 3 × ldc.r4 + newobj
BC_LITERAL_ROT    = 20   # 4 × ldc.r4 + newobj
BC_LITERAL_LIST   = 8    # newarr + stelem per element (rough)
BC_RETURN         = 4
BC_STATE_CHANGE   = 8
BC_JUMP           = 4
BC_LABEL          = 0    # labels generate no bytecode
# Each list-element push during a list-literal: ~6 bytes (box + stelem)
BC_LIST_ELEM      = 6


# ══════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════

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
    state_name: str    # state or '' for top-level functions
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
        if self.state_name:
            return f"{self.state_name}/{self.name}"
        return self.name


@dataclass
class MemoryReport:
    script_name: str
    bytecode_bytes: int
    string_pool_bytes: int
    string_pool_count: int
    global_vars: list[VarEntry]
    frames: list[FrameReport]
    warnings: list[str] = field(default_factory=list)

    @property
    def global_bytes(self) -> int:
        return sum(v.heap_bytes for v in self.global_vars)

    @property
    def static_bytes(self) -> int:
        return self.bytecode_bytes + self.string_pool_bytes

    @property
    def max_frame(self) -> Optional[FrameReport]:
        return max(self.frames, key=lambda f: f.total_bytes) if self.frames else None

    @property
    def conservative_total(self) -> int:
        """Static + globals + single worst-case frame (most common scenario)."""
        mf = self.max_frame
        return self.static_bytes + self.global_bytes + (mf.total_bytes if mf else 0)

    @property
    def budget(self) -> int:
        return SCRIPT_BUDGET

    @property
    def headroom(self) -> int:
        return self.budget - self.conservative_total

    @property
    def usage_pct(self) -> float:
        return 100.0 * self.conservative_total / self.budget


# ══════════════════════════════════════════════════════════════════════════
# Heap-cost helpers
# ══════════════════════════════════════════════════════════════════════════

def _type_cost(var_type: str) -> int:
    return TYPE_HEAP.get(var_type, TYPE_HEAP['string'])


def _string_content_cost(s: str) -> int:
    return len(s) * STRING_CHAR_COST


def _elem_cost(expr) -> int:
    """Heap cost of a single list element, given its literal expression."""
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
    # Variable / function call: unknown type — conservative: string cost
    return LIST_ELEM_COST['string']


def _var_heap_cost(var_type: str, init_expr=None) -> tuple[int, str]:
    """
    Return (heap_bytes, note) for a variable of var_type with optional initializer.
    When we have a literal initializer, we compute the exact content cost.
    Otherwise we use the type default (empty string, empty list, etc.)
    """
    base = _type_cost(var_type)
    note = ""

    if var_type == 'string':
        if isinstance(init_expr, StringLiteral):
            content = _string_content_cost(init_expr.value)
            note = f"{len(init_expr.value)} chars"
            return base + content, note
        return base, "empty"

    if var_type == 'key':
        # key is always a 36-char UUID; the initial value may be NULL_KEY or similar
        if isinstance(init_expr, StringLiteral):
            content = _string_content_cost(init_expr.value)
            note = f"{len(init_expr.value)} chars"
            return TYPE_HEAP['string'] + content, note
        return base, "UUID (36 chars)"

    if var_type == 'list':
        if isinstance(init_expr, ListLiteral):
            elem_cost = sum(_elem_cost(e) for e in init_expr.elements)
            note = f"{len(init_expr.elements)} elems"
            return base + elem_cost, note
        return base, "empty"

    return base, ""


# ══════════════════════════════════════════════════════════════════════════
# String-pool collector (unique literals, static metadata cost)
# ══════════════════════════════════════════════════════════════════════════

def _collect_string_pool(node, pool: set[str]) -> None:
    """Walk any AST node and collect unique string literal values."""
    if node is None:
        return
    if isinstance(node, StringLiteral):
        pool.add(node.value)
        return

    # Dispatch to children
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

    if isinstance(node, (BinOpExpr,)):
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


def _string_pool_cost(s: str) -> int:
    """
    Metadata cost for one unique string literal.
    8 bytes token-table entry + 4-byte length prefix + UTF-16 content.
    """
    return 12 + len(s) * STRING_CHAR_COST


# ══════════════════════════════════════════════════════════════════════════
# Bytecode estimator
# ══════════════════════════════════════════════════════════════════════════

def _bc(node) -> int:
    """Recursively estimate CIL bytecode bytes for an AST node."""
    if node is None:
        return 0

    if isinstance(node, FunctionDef):
        param_bc = len(node.parameters) * BC_VAR_DECL
        return BC_FUNC_PROLOGUE + param_bc + _bc(node.body)

    if isinstance(node, EventHandler):
        param_bc = len(node.parameters) * BC_VAR_DECL
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
        return BC_FUNC_CALL + sum(_bc(a) for a in node.args)

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
        return BC_LITERAL_STR   # content is counted in string pool, not here

    if isinstance(node, VectorLiteral):
        return BC_LITERAL_VEC + _bc(node.x) + _bc(node.y) + _bc(node.z)

    if isinstance(node, RotationLiteral):
        return BC_LITERAL_ROT + _bc(node.x) + _bc(node.y) + _bc(node.z) + _bc(node.s)

    if isinstance(node, ListLiteral):
        elem_bc = sum(_bc(e) + BC_LIST_ELEM for e in node.elements)
        return BC_LITERAL_LIST + elem_bc

    if isinstance(node, StateChangeStmt):
        return BC_STATE_CHANGE

    if isinstance(node, (JumpStmt,)):
        return BC_JUMP

    if isinstance(node, LabelStmt):
        return BC_LABEL

    return 0


# ══════════════════════════════════════════════════════════════════════════
# Local variable collector
# ══════════════════════════════════════════════════════════════════════════

def _collect_locals(stmt) -> list[VarEntry]:
    """Collect all VarDeclStmt nodes in a statement tree (depth-first)."""
    result: list[VarEntry] = []
    if stmt is None:
        return result

    if isinstance(stmt, VarDeclStmt):
        cost, note = _var_heap_cost(stmt.type, stmt.initial_value)
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


# ══════════════════════════════════════════════════════════════════════════
# Main analysis
# ══════════════════════════════════════════════════════════════════════════

def _make_frame(kind: str, state_name: str, name: str,
                parameters: list[tuple], body) -> FrameReport:
    params: list[VarEntry] = []
    for (ptype, pname) in parameters:
        cost, note = _var_heap_cost(ptype)
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

    # ── global variables ──────────────────────────────────────────────────
    global_vars: list[VarEntry] = []
    bytecode_total = 0
    warnings: list[str] = []

    for item in ast.globals:
        if isinstance(item, GlobalVar):
            cost, note = _var_heap_cost(item.type, item.initial_value)
            global_vars.append(VarEntry(item.type, item.name, cost, note))
        elif isinstance(item, FunctionDef):
            bytecode_total += _bc(item)

    # ── string pool (unique literals across entire script) ────────────────
    pool: set[str] = set()
    for item in ast.globals:
        _collect_string_pool(item, pool)
    for state in ast.states:
        _collect_string_pool(state, pool)

    string_pool_bytes = sum(_string_pool_cost(s) for s in pool)

    # ── frames: top-level functions + event handlers in all states ────────
    frames: list[FrameReport] = []

    for item in ast.globals:
        if isinstance(item, FunctionDef):
            frames.append(_make_frame('function', '', item.name,
                                      item.parameters, item.body))

    for state in ast.states:
        bytecode_total += BC_EVENT_PROLOGUE  # state-machine dispatch overhead
        for handler in state.handlers:
            bytecode_total += _bc(handler)
            frames.append(_make_frame('event', state.name, handler.name,
                                      handler.parameters, handler.body))

    # ── warnings ──────────────────────────────────────────────────────────
    global_bytes = sum(v.heap_bytes for v in global_vars)
    if global_bytes > 20_000:
        warnings.append(
            f"Global heap is {global_bytes:,} bytes — "
            "consider moving large lists/strings to Linkset Data."
        )

    large_lists = [v for v in global_vars
                   if v.var_type == 'list' and v.heap_bytes > 1_000]
    for v in large_lists:
        warnings.append(
            f"Global list '{v.name}' costs {v.heap_bytes:,} bytes. "
            "LSD can offload rarely-accessed data."
        )

    if frames:
        max_f = max(frames, key=lambda f: f.total_bytes)
        if max_f.total_bytes > 8_000:
            warnings.append(
                f"Frame '{max_f.label}' uses {max_f.total_bytes:,} bytes — "
                "large local strings/lists in hot paths increase peak usage."
            )

    estimated_total = bytecode_total + string_pool_bytes + global_bytes
    if frames:
        estimated_total += max(f.total_bytes for f in frames)
    if estimated_total > SCRIPT_BUDGET * 0.85:
        warnings.append(
            f"Estimated total {estimated_total:,} bytes is above 85% of the "
            "64 KB budget — risk of 'Script run-time error: NRUNTIME' crash."
        )

    return MemoryReport(
        script_name=script_name,
        bytecode_bytes=bytecode_total,
        string_pool_bytes=string_pool_bytes,
        string_pool_count=len(pool),
        global_vars=global_vars,
        frames=frames,
        warnings=warnings,
    )


# ══════════════════════════════════════════════════════════════════════════
# Formatters
# ══════════════════════════════════════════════════════════════════════════

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
    lines.append(f"  {'Bytecode (CIL instructions)':<38} {r.bytecode_bytes:>7} bytes")
    lines.append(f"  {'String constant pool':<38} "
                 f"{r.string_pool_bytes:>7} bytes  "
                 f"({r.string_pool_count} unique literals)")
    lines.append(f"  {'Static subtotal':<38} {r.static_bytes:>7} bytes  "
                 f"{_kb(r.static_bytes)}")

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
    lines.append("  CALL FRAMES (active while running)")
    if r.frames:
        sorted_frames = sorted(r.frames, key=lambda f: -f.total_bytes)
        for fr in sorted_frames[:10]:
            label = f"  {'event' if fr.kind == 'event' else 'func'} {fr.label}"
            lines.append(f"  {label:<40} {fr.total_bytes:>6} bytes  "
                         f"({fr.params_bytes}p + {fr.locals_bytes}l)")
        if len(sorted_frames) > 10:
            lines.append(f"  ... ({len(sorted_frames) - 10} more frames)")
        mf = r.max_frame
        if mf:
            lines.append(f"  {'Largest single frame':<38} {mf.total_bytes:>7} bytes  "
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
            lines.append(f"  ⚠  {w}")

    lines.append("")
    lines.append(
        "  Note: bytecode estimate ±25%; calibrate with llGetUsedMemory() in-world."
    )
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
        "static": {
            "bytecode": r.bytecode_bytes,
            "string_pool": r.string_pool_bytes,
            "string_pool_count": r.string_pool_count,
        },
        "global_heap": {
            "total": r.global_bytes,
            "vars": [
                {"type": v.var_type, "name": v.name,
                 "bytes": v.heap_bytes, "note": v.note}
                for v in r.global_vars
            ],
        },
        "frames": {
            "largest": {
                "name": mf.label,
                "bytes": mf.total_bytes,
            } if mf else None,
            "count": len(r.frames),
            "all": [
                {"name": f.label, "kind": f.kind,
                 "bytes": f.total_bytes,
                 "params": f.params_bytes, "locals": f.locals_bytes}
                for f in sorted(r.frames, key=lambda f: -f.total_bytes)
            ],
        },
        "warnings": r.warnings,
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Estimate LSL Mono memory usage for one or more .lsl files."
    )
    ap.add_argument("files", nargs="+", metavar="FILE")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of text")
    ap.add_argument(
        "--top-frames", type=int, default=10,
        metavar="N", help="Show top-N frames (default 10)"
    )
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

    # Summary line when multiple files
    if not args.json and len(results) > 1:
        print("═" * 64)
        print("  SUMMARY")
        print(f"  {'Script':<36} {'Est.':>8}  {'%':>5}  {'Free':>8}")
        print("─" * 64)
        for r in sorted(results, key=lambda x: -x.conservative_total):
            status = "⚠" if r.usage_pct > 85 else " "
            print(f"  {status} {r.script_name:<34} "
                  f"{r.conservative_total:>7}b  "
                  f"{r.usage_pct:>4.1f}%  "
                  f"{r.headroom:>7}b free")
        total_est = sum(r.conservative_total for r in results)
        print("─" * 64)
        print(f"  {'Total across all scripts':<36} {total_est:>8}")
        print("═" * 64)


if __name__ == "__main__":
    main()
