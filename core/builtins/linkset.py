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


LSD_LIMIT = 131072  # 128 KB, matches SL


@builtin("llLinksetDataAvailable")
def ll_linkset_data_available(evaluator, args):
    obj = current_object(evaluator.script)
    if not obj:
        return LSD_LIMIT
    used = sum(len(k.encode()) + len(v.encode()) for k, v in obj.linkset_data.items())
    return max(0, LSD_LIMIT - used)


@builtin("llLinksetDataFindKeys")
def ll_linkset_data_find_keys(evaluator, args):
    from core.types import LSLList
    obj = current_object(evaluator.script)
    if not obj:
        return LSLList()
    pattern = str(args[0])
    start   = int(args[1])
    count   = int(args[2])
    matches = [k for k in obj.linkset_data if pattern in k]
    if start:
        matches = matches[start:]
    if count:
        matches = matches[:count]
    result = LSLList()
    result.extend(matches)
    return result


@builtin("llMessageLinked")
def ll_message_linked(evaluator, args):
    script = evaluator.script
    obj = current_object(script)
    if not script or not script.container_prim or not obj:
        return None
    target_link = int(args[0])
    link_num = script.container_prim.link_number
    num = int(args[1])
    str_msg = str(args[2])
    id_key = str(args[3])

    event = LSLEvent(
        "link_message",
        [link_num, num, str_msg, id_key],
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

    # Emit console message for the Linked Messages inspector
    from .common import emit_console
    emit_console(
        script,
        "link_message",
        f"Sender: {link_num} | Target: {target_link} | Num: {num} | Msg: '{str_msg}' | Key: '{id_key}'",
        source_name=obj.name,
        source_key=obj.uuid,
    )
    return None
