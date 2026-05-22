"""
TTChess Text Interface simulation tests.
Verifies compiling, move parsing, chat-based move execution, unicode board rendering,
and click-anywhere menu redirection in TextInterface.lsl.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from events.queue import LSLEvent
from core.types import LSLVector
from ide.project import IdeProject, ProjectObject, ProjectScript
from sim.world import World

TTCHESS = Path(__file__).parent.parent.parent / "ttchess"
TEXT_IFACE_SRC = (TTCHESS / "TextInterface.lsl").read_text()

# We'll use a thin observer script to intercept outbound link messages and write them to LSD
OBSERVER_SRC = """
default {
    link_message(integer sender, integer number, string message, key id) {
        llLinksetDataWrite("lm:" + (string)number + ":msg", message);
        llLinksetDataWrite("lm:" + (string)number + ":id", (string)id);
        llOwnerSay("LM:" + (string)number + " msg=" + message + " id=" + (string)id);
    }
}
"""

def _make_text_interface_project() -> IdeProject:
    World().reset()
    scripts = [
        ProjectScript("TextInterface.lsl", TEXT_IFACE_SRC),
        ProjectScript("Observer.lsl", OBSERVER_SRC),
    ]
    obj = ProjectObject(
        "Board A",
        position=LSLVector(120.0, 128.0, 25.0),
        scripts=scripts
    )
    return IdeProject(Path("/tmp/ttchess_text_iface_test"), [obj])

def _lsd_read(runtime, object_name: str, key: str) -> str:
    obj = runtime.objects[object_name]
    return obj.linkset_data.get(key, "")

def _inject_lm(runtime, object_name: str, num: int, msg: str, id_: str = ""):
    obj = runtime.objects[object_name]
    from sim.prim import ScriptItem
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running:
                item.event_queue.push(
                    LSLEvent("link_message", [prim.link_number, num, msg, id_])
                )

def test_text_interface_parses():
    """Verify that TextInterface.lsl compiles and has a default state."""
    from core.lexer import Lexer
    from core.parser import Parser
    ast = Parser(Lexer(TEXT_IFACE_SRC).tokenize()).parse()
    assert any(s.name == "default" for s in ast.states)

def test_text_interface_starts():
    """Verify that the script starts and outputs initial ready message."""
    proj = _make_text_interface_project()
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    messages = [m.text for m in runtime.world.console.messages if m.message_type == "say"]
    assert any("TTChess Chat/Text Interface Initialized." in m for m in messages)

def test_chat_move_validation_and_relay():
    """
    Simulate avatar saying chess moves in public chat.
    Valid moves in the validMoves list should be forwarded via LM 5002.
    Invalid moves should be rejected and not forwarded.
    """
    proj = _make_text_interface_project()
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    # 1. Feed a legal moves list on channel 20200351
    # We supply e2e4,g1f3 as valid moves
    _inject_lm(runtime, "Board A", 20200351, "e2e4,g1f3", "")
    runtime.tick(1, dt=0.1)

    # 2. Simulate avatar saying a valid move "e2e4" in chat
    # Clear observer LSD just in case
    runtime.objects["Board A"].linkset_data["lm:5002:msg"] = ""
    runtime.say("e2e4")
    runtime.tick(2, dt=0.5)

    # Observer should have recorded LM 5002
    msg = _lsd_read(runtime, "Board A", "lm:5002:msg")
    assert msg == "e2e4"

    # 3. Simulate avatar saying an invalid move "d2d4" in chat
    runtime.objects["Board A"].linkset_data["lm:5002:msg"] = ""
    runtime.say("d2d4")
    runtime.tick(2, dt=0.5)

    # Observer should NOT have recorded LM 5002 for d2d4
    msg = _lsd_read(runtime, "Board A", "lm:5002:msg")
    assert msg != "d2d4"

    # Verify rejecting message was whispered/said to player
    say_messages = [m.text for m in runtime.world.console.messages]
    assert any("d2d4 is not a valid move." in m for m in say_messages)

def test_chat_move_auto_promotion():
    """
    Simulate promotion check:
    When a promotion is possible (e.g. e7e8q is a legal move), saying "e7e8"
    should auto-promote to Queen (e7e8q) and forward LM 5002 with e7e8q.
    """
    proj = _make_text_interface_project()
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    # 1. Feed a legal moves list including a queen promotion
    _inject_lm(runtime, "Board A", 20200351, "e7e8q,a2a3", "")
    runtime.tick(1, dt=0.1)

    # 2. Say "e7e8" in chat
    runtime.objects["Board A"].linkset_data["lm:5002:msg"] = ""
    runtime.say("e7e8")
    runtime.tick(2, dt=0.5)

    # Observer should see LM 5002 with "e7e8q"
    msg = _lsd_read(runtime, "Board A", "lm:5002:msg")
    assert msg == "e7e8q"

def test_touch_redirection():
    """
    Verify that when CLICK_ANYWHERE is TRUE, touching the board
    sends a link message 90999 to open the main menu.
    """
    proj = _make_text_interface_project()
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    # Trigger touch
    runtime.objects["Board A"].linkset_data["lm:90999:msg"] = ""
    runtime.touch("Board A")
    runtime.tick(2, dt=0.5)

    # Observer should see LM 90999 with "mainmenu"
    msg = _lsd_read(runtime, "Board A", "lm:90999:msg")
    assert msg == "mainmenu"

def test_unicode_board_redraw():
    """
    Verify that receiving 777 board redraw instructions updates board history
    and outputs the premium unicode chess board.
    """
    proj = _make_text_interface_project()
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    # Send a new board event (clears board)
    _inject_lm(runtime, "Board A", 777, "new", "")
    runtime.tick(2, dt=0.5)

    say_messages = [m.text for m in runtime.world.console.messages]
    assert any("[TTChess Unicode Board]" in m for m in say_messages)
    assert any("♜" in m for m in say_messages)  # Should contain black rooks
    assert any("♙" in m for m in say_messages)  # Should contain white pawns
    assert any("a b c d e f g h" in m for m in say_messages)  # file labels
