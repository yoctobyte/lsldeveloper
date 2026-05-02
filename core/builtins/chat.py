from __future__ import annotations

from sim.prim import Listener

from .common import current_object, current_region, emit_console
from .registry import builtin


@builtin("llSay")
def ll_say(evaluator, args):
    script = evaluator.script
    if script and script.container_prim and current_region(script):
        current_region(script).broadcast_chat(
            script.container_prim.uuid,
            script.container_prim.name,
            int(args[0]),
            str(args[1]),
        )
    else:
        emit_console(script, "say", str(args[1]), channel=int(args[0]), stdout_text=f"CHAT [Channel {args[0]}]: {args[1]}")
    return None


@builtin("llRegionSay", "llShout", "llWhisper")
def ll_region_say(evaluator, args):
    script = evaluator.script
    if script and script.container_prim and current_region(script):
        current_region(script).broadcast_chat(
            script.container_prim.uuid,
            script.container_prim.name,
            int(args[0]),
            str(args[1]),
        )
    return None


@builtin("llRegionSayTo")
def ll_region_say_to(evaluator, args):
    script = evaluator.script
    if script and script.container_prim and current_region(script):
        current_region(script).broadcast_chat(
            script.container_prim.uuid,
            script.container_prim.name,
            int(args[1]),
            str(args[2]),
        )
    return None


@builtin("llOwnerSay")
def ll_owner_say(evaluator, args):
    emit_console(evaluator.script, "ownersay", str(args[0]), stdout_text=f"OWNER_SAY: {args[0]}")
    return None


@builtin("llListen")
def ll_listen(evaluator, args):
    script = evaluator.script
    if not script:
        return 0
    handle = script.next_listener_handle
    script.listeners[handle] = Listener(int(args[0]), str(args[1]), str(args[2]), str(args[3]))
    script.next_listener_handle += 1
    return handle


@builtin("llListenRemove")
def ll_listen_remove(evaluator, args):
    script = evaluator.script
    if script:
        script.listeners.pop(int(args[0]), None)
    return None


@builtin("llDialog")
def ll_dialog(evaluator, args):
    script = evaluator.script
    region = current_region(script)
    obj = current_object(script)
    buttons = [str(button) for button in args[2]]
    dialog = {
        "avatar": str(args[0]),
        "message": str(args[1]),
        "buttons": buttons,
        "channel": int(args[3]),
        "source_name": obj.name if obj else "",
        "source_key": obj.uuid if obj else "",
    }
    if region and region.world:
        region.world.latest_dialog = dialog
    button_text = ", ".join(buttons)
    emit_console(
        script,
        "dialog",
        f"{dialog['message']} [{button_text}]",
        source_name=dialog["source_name"],
        source_key=dialog["source_key"],
        channel=dialog["channel"],
        stdout_text=f"DIALOG [{dialog['channel']}] {dialog['source_name']}: {dialog['message']} [{button_text}]",
    )
    return None
