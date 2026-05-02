from __future__ import annotations

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
    return 0.05


@builtin("llResetTime")
def ll_reset_time(evaluator, args):
    return None
