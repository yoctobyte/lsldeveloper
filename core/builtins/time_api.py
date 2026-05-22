from __future__ import annotations

import time

from .registry import builtin


@builtin("llSetTimerEvent")
def ll_set_timer_event(evaluator, args):
    script = evaluator.script
    if script:
        script.timer_interval = float(args[0])
        script.last_timer_fire = 0.0
    return None


@builtin("llGetTime")
def ll_get_time(evaluator, args):
    script = evaluator.script
    if not script:
        return 0.0
    if not hasattr(script, "time_reset_point"):
        script.time_reset_point = time.monotonic()
    return time.monotonic() - script.time_reset_point


@builtin("llResetTime")
def ll_reset_time(evaluator, args):
    script = evaluator.script
    if script:
        script.time_reset_point = time.monotonic()
    return None


@builtin("llGetAndResetTime")
def ll_get_and_reset_time(evaluator, args):
    script = evaluator.script
    if not script:
        return 0.0
    if not hasattr(script, "time_reset_point"):
        script.time_reset_point = time.monotonic()
        return 0.0
    now = time.monotonic()
    elapsed = now - script.time_reset_point
    script.time_reset_point = now
    return elapsed


@builtin("llGetUnixTime")
def ll_get_unix_time(evaluator, args):
    return int(time.time())


@builtin("llGetFreeMemory")
def ll_get_free_memory(evaluator, args):
    # Return a plausible value; real figure only available from the SL VM
    return 50000


@builtin("llGetScriptName")
def ll_get_script_name(evaluator, args):
    script = evaluator.script
    if script:
        name = script.name
        # Strip .lsl extension to match SL in-world naming convention
        if name.endswith(".lsl"):
            name = name[:-4]
        return name
    return ""
