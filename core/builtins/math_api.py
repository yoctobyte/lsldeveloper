from __future__ import annotations

import math

from .registry import builtin


@builtin("llPow")
def ll_pow(evaluator, args):
    return float(args[0]) ** float(args[1])


@builtin("llSqrt")
def ll_sqrt(evaluator, args):
    v = float(args[0])
    if v < 0.0:
        return 0.0
    return math.sqrt(v)


@builtin("llLog")
def ll_log(evaluator, args):
    v = float(args[0])
    if v <= 0.0:
        return 0.0
    return math.log(v)


@builtin("llLog10")
def ll_log10(evaluator, args):
    v = float(args[0])
    if v <= 0.0:
        return 0.0
    return math.log10(v)


@builtin("llSin")
def ll_sin(evaluator, args):
    return math.sin(float(args[0]))


@builtin("llCos")
def ll_cos(evaluator, args):
    return math.cos(float(args[0]))


@builtin("llTan")
def ll_tan(evaluator, args):
    return math.tan(float(args[0]))


@builtin("llAsin")
def ll_asin(evaluator, args):
    v = float(args[0])
    v = max(-1.0, min(1.0, v))
    return math.asin(v)


@builtin("llAcos")
def ll_acos(evaluator, args):
    v = float(args[0])
    v = max(-1.0, min(1.0, v))
    return math.acos(v)


@builtin("llAtan2")
def ll_atan2(evaluator, args):
    return math.atan2(float(args[0]), float(args[1]))


@builtin("llFabs")
def ll_fabs(evaluator, args):
    return abs(float(args[0]))


@builtin("llFloor")
def ll_floor(evaluator, args):
    return int(math.floor(float(args[0])))


@builtin("llCeil")
def ll_ceil(evaluator, args):
    return int(math.ceil(float(args[0])))


@builtin("llRound")
def ll_round(evaluator, args):
    return int(round(float(args[0])))


@builtin("llModPow")
def ll_mod_pow(evaluator, args):
    return int(pow(int(args[0]), int(args[1]), int(args[2])))


@builtin("llVecMag")
def ll_vec_mag(evaluator, args):
    from core.types import LSLVector
    v = args[0]
    if isinstance(v, LSLVector):
        return math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z)
    return 0.0


@builtin("llVecNorm")
def ll_vec_norm(evaluator, args):
    from core.types import LSLVector
    v = args[0]
    if isinstance(v, LSLVector):
        mag = math.sqrt(v.x*v.x + v.y*v.y + v.z*v.z)
        if mag == 0.0:
            return LSLVector(0.0, 0.0, 0.0)
        return LSLVector(v.x/mag, v.y/mag, v.z/mag)
    return args[0]


@builtin("llVecDist")
def ll_vec_dist(evaluator, args):
    from core.types import LSLVector
    a, b = args[0], args[1]
    if isinstance(a, LSLVector) and isinstance(b, LSLVector):
        return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)
    return 0.0
