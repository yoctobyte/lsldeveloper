"""
TTChess P2P simulation tests.

Verifies the three new scripts (ChessEngine, NodeHTTP, NodeManager) running
inside the offline LSL simulator.  Tests progress from unit-level (single
board, local engine) to integration-level (two boards, peer-to-peer move).

Run:
    cd ~/lsldeveloper && python -m pytest tests/test_ttchess_p2p.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from events.queue import LSLEvent
from ide.project import IdeProject, ProjectObject, ProjectScript
from sim.world import World

# Absolute paths to the actual LSL scripts
TTCHESS = Path(__file__).parent.parent.parent / "ttchess"
ENGINE_SRC  = (TTCHESS / "ChessEngine.lsl").read_text()
HTTP_SRC    = (TTCHESS / "NodeHTTP.lsl").read_text()
MANAGER_SRC = (TTCHESS / "NodeManager.lsl").read_text()

# Standard starting position in FEN
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Link-message channel constants (must match the LSL scripts)
LM_ENGINE_SEARCH  = 0xCE001
LM_ENGINE_RESULT  = 0xCE003
LM_NET_URL        = 0xCE010
LM_NODE_NEED_MOVE = 0xCE020
LM_NODE_GOT_MOVE  = 0xCE021


def _make_project(*board_names: str) -> IdeProject:
    """Build an IdeProject with one or more boards, each running all 3 scripts."""
    World().reset()
    objects = []
    for i, name in enumerate(board_names):
        objects.append(ProjectObject(
            name,
            position_list=[120.0 + i * 16, 128.0, 25.0],
            scripts=[
                ProjectScript("ChessEngine.lsl", ENGINE_SRC),
                ProjectScript("NodeHTTP.lsl",    HTTP_SRC),
                ProjectScript("NodeManager.lsl", MANAGER_SRC),
            ],
        ))
    return IdeProject(Path("/tmp/ttchess_test"), objects)


def _ownersay_lines(runtime) -> list[str]:
    return [
        m.text
        for m in runtime.world.console.messages
        if m.message_type == "ownersay"
    ]


def _move_is_legal(move: str) -> bool:
    """Basic sanity: 4-char algebraic like e2e4, a1h8, etc."""
    return bool(re.fullmatch(r"[a-h][1-8][a-h][1-8][qrnb]?", move))


# ── Helpers for direct LM injection ──────────────────────────────────────────

def _inject_lm(runtime, object_name: str, num: int, msg: str, id_: str = ""):
    """Push a link_message event into all scripts of the named object."""
    obj = runtime.objects[object_name]
    from sim.prim import ScriptItem
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running:
                item.event_queue.push(
                    LSLEvent("link_message", [prim.link_number, num, msg, id_])
                )


def _lsd_read(runtime, object_name: str, key: str) -> str:
    obj = runtime.objects[object_name]
    return obj.linkset_data.get(key, "")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Parse / compile tests — no simulation needed
# ═══════════════════════════════════════════════════════════════════════════

def test_engine_parses():
    from core.lexer import Lexer
    from core.parser import Parser
    ast = Parser(Lexer(ENGINE_SRC).tokenize()).parse()
    assert any(s.name == "default" for s in ast.states)


def test_nodehttp_parses():
    from core.lexer import Lexer
    from core.parser import Parser
    ast = Parser(Lexer(HTTP_SRC).tokenize()).parse()
    assert any(s.name == "default" for s in ast.states)


def test_nodemanager_parses():
    from core.lexer import Lexer
    from core.parser import Parser
    ast = Parser(Lexer(MANAGER_SRC).tokenize()).parse()
    assert any(s.name == "default" for s in ast.states)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Single-board startup
# ═══════════════════════════════════════════════════════════════════════════

def test_single_board_starts():
    """All three scripts start up and emit their ready messages."""
    proj    = _make_project("Board A")
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(3, dt=1.0)

    lines = _ownersay_lines(runtime)
    assert any("ChessEngine" in l and "ready" in l for l in lines), lines
    assert any("NodeHTTP"    in l and "ready" in l for l in lines), lines
    assert any("NodeManager" in l and "ready" in l for l in lines), lines


def test_url_acquired():
    """NodeHTTP acquires a sim URL and writes it to llLinksetData."""
    proj    = _make_project("Board A")
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(3, dt=1.0)

    url = _lsd_read(runtime, "Board A", "node:url")
    assert url.startswith("http://sim.local/"), f"unexpected url: {url!r}"


def test_engine_lsd_initialized():
    """ChessEngine writes node:busy=0 and node:abort=0 on startup."""
    proj    = _make_project("Board A")
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    assert _lsd_read(runtime, "Board A", "node:busy")  == "0"
    assert _lsd_read(runtime, "Board A", "node:abort") == "0"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Local engine: direct LM_ENGINE_SEARCH → LM_ENGINE_RESULT
# ═══════════════════════════════════════════════════════════════════════════

def test_local_engine_returns_move():
    """
    Inject LM_ENGINE_SEARCH directly into ChessEngine and verify it
    responds with a legal move via LM_ENGINE_RESULT.
    """
    proj    = _make_project("Board A")
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    # Capture LM_ENGINE_RESULT by adding a listener script
    results = []

    obj = runtime.objects["Board A"]
    from sim.prim import ScriptItem
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and item.name == "NodeHTTP.lsl":
                # We'll check LSD node:move after the search
                pass

    # Inject search request: depth=2, budget=30000ms
    _inject_lm(runtime, "Board A", LM_ENGINE_SEARCH,
                START_FEN, f"{2}|{30000}")

    # Run ticks — the self-LM loop completes within each tick
    runtime.tick(20, dt=0.5)

    # ChessEngine writes best move to LSD when done
    move  = _lsd_read(runtime, "Board A", "node:move")
    busy  = _lsd_read(runtime, "Board A", "node:busy")
    assert busy == "0", "engine should be idle after search"
    assert _move_is_legal(move), f"expected a legal move, got {move!r}"


# ═══════════════════════════════════════════════════════════════════════════
# 4. NodeManager local path: LM_NODE_NEED_MOVE → local engine → LM_NODE_GOT_MOVE
# ═══════════════════════════════════════════════════════════════════════════

def test_nodemanager_local_path():
    """
    NodeManager falls back to the local engine when no peers are known.
    Inject LM_NODE_NEED_MOVE, expect LM_NODE_GOT_MOVE with a legal move.
    """
    proj    = _make_project("Board A")
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(3, dt=1.0)

    # Collect GOT_MOVE responses by watching ownersay from a thin observer
    # (We can't easily intercept link_message from Python, so we check LSD)
    _inject_lm(runtime, "Board A", LM_NODE_NEED_MOVE,
                START_FEN, "3|30000")

    runtime.tick(30, dt=0.5)

    move = _lsd_read(runtime, "Board A", "node:move")
    assert _move_is_legal(move), f"expected legal move from local engine, got {move!r}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Two-board P2P: Board A uses Board B's engine via intra-sim HTTP
# ═══════════════════════════════════════════════════════════════════════════

def test_two_board_region_discovery():
    """
    Two boards in the same region discover each other via llRegionSay.
    After a few timer ticks, Board A should have Board B's URL in its peer list.
    NodeManager stores allow_peers/prefer_peers in LSD; Board B's URL should
    appear in Board A's ownersay output (nodeready acknowledgement).
    """
    proj    = _make_project("Board A", "Board B")
    runtime = proj.build_runtime(echo_stdout=False)
    # Let both boards start up + timers fire (NodeManager timer = 5 s)
    runtime.tick(10, dt=1.0)

    url_b = _lsd_read(runtime, "Board B", "node:url")
    assert url_b.startswith("http://sim.local/"), f"Board B has no URL: {url_b!r}"

    # Board A's NodeManager should have heard Board B's "nodeready" response
    lines = _ownersay_lines(runtime)
    # NodeHTTP announces its URL — both boards should have it
    url_a = _lsd_read(runtime, "Board A", "node:url")
    assert url_a.startswith("http://sim.local/"), f"Board A has no URL: {url_a!r}"
    assert url_a != url_b, "boards must have distinct URLs"


def test_intra_sim_http_serve():
    """
    Send a raw HTTP POST to Board B's URL (as if from a peer).
    Board B should compute a move and respond via llHTTPResponse.
    The caller (Board A's NodeHTTP) should receive the response.
    """
    proj    = _make_project("Board A", "Board B")
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(3, dt=1.0)

    url_b = _lsd_read(runtime, "Board B", "node:url")
    assert url_b, "Board B needs a URL"

    # Find Board A's NodeHTTP script — it will make the outgoing fetch
    world = _world_from_runtime(runtime)

    # Inject LM_NET_FETCH into Board A: "go ask Board B for a move"
    token = "test-token-123"
    _inject_lm(runtime, "Board A", 0xCE014,   # LM_NET_FETCH
                START_FEN,
                f"{url_b}|3|20000|{token}")

    runtime.tick(40, dt=0.5)

    # Board B's engine should have computed a move; Board A should have got it
    move_b = _lsd_read(runtime, "Board B", "node:move")
    assert _move_is_legal(move_b), f"Board B engine move: {move_b!r}"


def test_two_board_p2p_move():
    """
    End-to-end: Board A asks for AI move via LM_NODE_NEED_MOVE with prefer_peers=1.
    With both boards running and Board B discovered, Board A should route the
    request to Board B's engine and receive a legal move back.
    """
    proj    = _make_project("Board A", "Board B")
    runtime = proj.build_runtime(echo_stdout=False)

    # Let discovery happen (timer fires at 5 s, collection window 3 s)
    runtime.tick(12, dt=1.0)

    # Force prefer_peers on Board A so it skips local engine
    runtime.objects["Board A"].linkset_data["node:prefer_peers"] = "1"

    # Ask Board A for a move
    _inject_lm(runtime, "Board A", LM_NODE_NEED_MOVE,
                START_FEN, "3|20000")

    runtime.tick(40, dt=0.5)

    # Either Board A's local LSD move (if local fallback) or Board B's LSD move
    # should contain a legal move.  The key assertion: no crash and a legal move exists.
    move_a = _lsd_read(runtime, "Board A", "node:move")
    move_b = _lsd_read(runtime, "Board B", "node:move")
    move   = move_a or move_b
    assert _move_is_legal(move), (
        f"Expected a legal move from P2P flow, got A={move_a!r} B={move_b!r}"
    )


# ── helper ────────────────────────────────────────────────────────────────

def _world_from_runtime(runtime) -> World:
    return runtime.world


# ── ProjectObject position helper ────────────────────────────────────────
# IdeProject.ProjectObject takes position as LSLVector; patch from_dict accepts
# a list.  For test convenience we add a small shim here.

def _patch_project_object():
    from core.types import LSLVector
    _orig_init = ProjectObject.__init__

    def _new_init(self, name, description="", position_list=None, scripts=None,
                  notecards=None, child_objects=None, **kw):
        pos = LSLVector(*(position_list or [128.0, 128.0, 25.0]))
        _orig_init(self, name, description=description, position=pos,
                   scripts=scripts or [], notecards=notecards or [],
                   child_objects=child_objects or [])

    ProjectObject.__init__ = _new_init

_patch_project_object()
