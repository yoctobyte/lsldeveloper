from __future__ import annotations

from events.queue import LSLEvent
from sim.prim import ScriptItem

from .common import current_object
from .registry import builtin


@builtin("llLinksetDataWrite")
def ll_linkset_data_write(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.linkset_data[str(args[0])] = str(args[1])
    return None


@builtin("llLinksetDataRead")
def ll_linkset_data_read(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.linkset_data.get(str(args[0]), "") if obj else ""


@builtin("llLinksetDataDelete")
def ll_linkset_data_delete(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.linkset_data.pop(str(args[0]), None)
    return None


@builtin("llLinksetDataReset")
def ll_linkset_data_reset(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.linkset_data.clear()
    return None


@builtin("llMessageLinked")
def ll_message_linked(evaluator, args):
    script = evaluator.script
    obj = current_object(script)
    if not script or not script.container_prim or not obj:
        return None
    target_link = int(args[0])
    event = LSLEvent(
        "link_message",
        [script.container_prim.link_number, int(args[1]), str(args[2]), str(args[3])],
    )
    for prim in obj.prims:
        if target_link > 0 and prim.link_number != target_link:
            continue
        if target_link == -3 and prim.link_number == 1:
            continue
        if target_link == -4 and prim.link_number != script.container_prim.link_number:
            continue
        for item in prim.inventory:
            if isinstance(item, ScriptItem):
                item.event_queue.push(event)
    return None
