from __future__ import annotations

from core.types import LSLList

from .registry import builtin


@builtin("llSetText")
def ll_set_text(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        script.container_prim.floating_text = {
            "text": str(args[0]),
            "color": args[1],
            "alpha": float(args[2]),
        }
    return None


@builtin("llParticleSystem")
def ll_particle_system(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        script.container_prim.particle_system = LSLList(args[0])
    return None


@builtin("llSetTextureAnim")
def ll_set_texture_anim(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        script.container_prim.texture_animation = {
            "mode": int(args[0]),
            "face": int(args[1]),
            "size_x": int(args[2]),
            "size_y": int(args[3]),
            "start": float(args[4]),
            "length": float(args[5]),
            "rate": float(args[6]),
        }
    return None


@builtin("llPlaySound", "llLoopSound", "llTriggerSound")
def ll_sound(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        sound_state = {
            "mode": {
                "llPlaySound": "play",
                "llLoopSound": "loop",
                "llTriggerSound": "trigger",
            }[evaluator.current_builtin_name],
            "sound": str(args[0]),
            "volume": float(args[1]),
        }
        script.container_prim.sound_state = sound_state
        script.container_prim.sound_history.append(sound_state)
    return None


@builtin("llPreloadSound")
def ll_preload_sound(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        script.container_prim.preloaded_sounds.add(str(args[0]))
    return None


@builtin("llStopSound")
def ll_stop_sound(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        script.container_prim.sound_state = {"mode": "stopped", "sound": "", "volume": 0.0}
    return None
