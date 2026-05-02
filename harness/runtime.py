from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.ast_nodes import GlobalVar
from core.interpreter import Evaluator, ExecutionContext
from core.lexer import Lexer
from core.parser import Parser
from events.loop import SimulationLoop
from events.queue import LSLEvent
from sim.avatar import Avatar
from sim.demo import seed_demo_world
from sim.object import LSLObject
from sim.prim import Prim, ScriptItem
from sim.region import Region
from sim.world import World


@dataclass
class HarnessRuntime:
    world: World
    region: Region
    obj: LSLObject
    prim: Prim
    script: ScriptItem
    loop: SimulationLoop
    avatar: Avatar

    def tick(self, count: int = 1, dt: float = 0.1):
        for _ in range(count):
            self.loop.tick(dt)

    def say(self, message: str, channel: int = 0):
        self.avatar.say(channel, message)

    def touch(self, link_num: int = 0):
        self.avatar.touch(self.obj.uuid, link_num)


def parse_lsl(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def initialize_script(script_item: ScriptItem, queue_state_entry: bool = True) -> ScriptItem:
    script_ast = parse_lsl(script_item.source)
    script_item.ast = script_ast
    script_item.running = True
    script_item.current_state = "default"

    ctx = ExecutionContext()
    evaluator = Evaluator(ctx, script_item)
    for item in script_ast.globals:
        if isinstance(item, GlobalVar):
            ctx.globals[item.name] = (
                evaluator.evaluate(item.initial_value)
                if item.initial_value is not None
                else default_value_for_type(item.type)
            )

    script_item.ctx = ctx
    if queue_state_entry:
        script_item.event_queue.push(LSLEvent("state_entry", []))
    return script_item


def default_value_for_type(type_name: str):
    # Reuse local declaration semantics by evaluating a tiny declaration in spirit.
    from core.types import LSLList, LSLRotation, LSLVector, NULL_KEY

    if type_name == "integer":
        return 0
    if type_name == "float":
        return 0.0
    if type_name == "string":
        return ""
    if type_name == "key":
        return NULL_KEY
    if type_name == "vector":
        return LSLVector()
    if type_name == "rotation":
        return LSLRotation()
    if type_name == "list":
        return LSLList()
    return None


def build_runtime(
    source: str,
    *,
    script_name: str = "script.lsl",
    region_name: str = "Offline Region",
    object_name: str = "Offline Object",
    prim_name: str = "Root Prim",
    avatar_name: str = "Offline User",
    world: Optional[World] = None,
    seed_demo: bool = True,
) -> HarnessRuntime:
    world = world or World()
    if seed_demo:
        seeded = seed_demo_world(world)
        region = seeded["region"]
        default_avatar = seeded["owner"]
    else:
        world.reset()
        region = Region(region_name)
        world.add_region(region)
        default_avatar = None

    owner_key = default_avatar.uuid if default_avatar else None
    obj = LSLObject(
        object_name,
        owner_key=owner_key or "00000000-0000-0000-0000-000000000000",
        creator_key=owner_key or "00000000-0000-0000-0000-000000000000",
    )
    region.add_object(obj)

    prim = Prim(prim_name)
    obj.add_prim(prim)

    if default_avatar and avatar_name == default_avatar.name:
        avatar = default_avatar
    else:
        avatar = Avatar(avatar_name)
        region.add_avatar(avatar)

    script_item = initialize_script(ScriptItem(script_name, source))
    prim.add_item(script_item)

    return HarnessRuntime(
        world=world,
        region=region,
        obj=obj,
        prim=prim,
        script=script_item,
        loop=SimulationLoop(world),
        avatar=avatar,
    )
