from core.ast_nodes import GlobalVar
from core.interpreter import Evaluator, ExecutionContext
from core.lexer import Lexer
from core.parser import Parser
from events.loop import SimulationLoop
from sim.avatar import Avatar
from sim.object import LSLObject
from sim.prim import Prim, ScriptItem
from sim.region import Region
from sim.world import World


TOUCH_SCRIPT = """
integer touches = 0;

default {
    touch_start(integer num) {
        touches += num;
    }
}
"""


def test_avatar_touch_dispatches_touch_start():
    world = World()
    world.reset()
    region = Region("Test Region")
    world.add_region(region)

    obj = LSLObject("Touch Box")
    region.add_object(obj)
    prim = Prim("Root Prim")
    obj.add_prim(prim)

    avatar = Avatar("Test User")
    region.add_avatar(avatar)

    script_ast = Parser(Lexer(TOUCH_SCRIPT).tokenize()).parse()
    script_item = ScriptItem("touch.lsl", TOUCH_SCRIPT)
    script_item.ast = script_ast
    script_item.running = True

    ctx = ExecutionContext()
    evaluator = Evaluator(ctx, script_item)
    for item in script_ast.globals:
        if isinstance(item, GlobalVar):
            ctx.globals[item.name] = evaluator.evaluate(item.initial_value) if item.initial_value else None
    script_item.ctx = ctx
    prim.add_item(script_item)

    avatar.touch(obj.uuid)
    SimulationLoop(world).tick(0.1)

    assert ctx.globals["touches"] == 1
