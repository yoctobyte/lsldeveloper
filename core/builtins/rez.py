from __future__ import annotations

from events.queue import LSLEvent
from sim.prim import ObjectInventoryItem

from .common import current_object, current_region, emit_console
from .inventory import _item_by_name
from .registry import builtin


def _rez(evaluator, args, *, at_root: bool):
    script = evaluator.script
    obj = current_object(script)
    region = current_region(script)
    if not script or not obj or not region:
        return None

    item = _item_by_name(script, str(args[0]))
    if not isinstance(item, ObjectInventoryItem):
        emit_console(script, "error", f"rez failed: inventory object not found: {args[0]}")
        return None

    world = region.world
    if world.rezzed_object_count >= world.max_rezzed_objects:
        emit_console(script, "error", f"rez limit reached: {world.max_rezzed_objects}")
        return None

    position = args[1]
    rotation = args[3]
    rezzed = item.rez(region, world, position, rotation, obj.owner_key, obj.creator_key)
    if not rezzed:
        emit_console(script, "error", f"rez failed: {args[0]}")
        return None

    script.event_queue.push(LSLEvent("object_rez", [rezzed.uuid]))
    emit_console(script, "debug", f"rezzed {rezzed.name}", source_name=obj.name, source_key=obj.uuid)
    return None


@builtin("llRezObject")
def ll_rez_object(evaluator, args):
    return _rez(evaluator, args, at_root=False)


@builtin("llRezAtRoot")
def ll_rez_at_root(evaluator, args):
    return _rez(evaluator, args, at_root=True)
