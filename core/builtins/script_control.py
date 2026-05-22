from __future__ import annotations

import time
from core.types import LSLList, LSLRotation, LSLVector, NULL_KEY
from core.exceptions import ScriptResetException
from sim.prim import ScriptItem
from .registry import builtin


def find_sibling_script(script, name: str) -> ScriptItem | None:
    if not script or not script.container_prim:
        return None
    target_name = name
    if target_name.endswith(".lsl"):
        target_name = target_name[:-4]
    for item in script.container_prim.inventory:
        if isinstance(item, ScriptItem):
            item_name = item.name
            if item_name.endswith(".lsl"):
                item_name = item_name[:-4]
            if item_name == target_name:
                return item
    return None


@builtin("llSleep")
def ll_sleep(evaluator, args):
    sec = float(args[0])
    # Sleep but limit to avoid blocking IDE thread indefinitely
    time.sleep(min(sec, 0.001))
    return None


@builtin("llSetScriptState")
def ll_set_script_state(evaluator, args):
    script = evaluator.script
    if not script:
        return None
    target_name = str(args[0])
    run = bool(args[1])
    sibling = find_sibling_script(script, target_name)
    if sibling:
        sibling.running = run
    return None


@builtin("llGetScriptState")
def ll_get_script_state(evaluator, args):
    script = evaluator.script
    if not script:
        return 0
    target_name = str(args[0])
    sibling = find_sibling_script(script, target_name)
    if sibling:
        return 1 if sibling.running else 0
    return 0


@builtin("llResetOtherScript")
def ll_reset_other_script(evaluator, args):
    script = evaluator.script
    if not script:
        return None
    target_name = str(args[0])
    sibling = find_sibling_script(script, target_name)
    if sibling:
        from harness.runtime import initialize_script
        initialize_script(sibling, queue_state_entry=True)
    return None


@builtin("llResetScript")
def ll_reset_script(evaluator, args):
    script = evaluator.script
    if script:
        from harness.runtime import initialize_script
        initialize_script(script, queue_state_entry=True)
        raise ScriptResetException()
    return None


@builtin("llSetTouchText")
def ll_set_touch_text(evaluator, args):
    return None
