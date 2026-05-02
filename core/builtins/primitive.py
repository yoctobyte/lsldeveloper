from __future__ import annotations

from core.types import LSLList, LSLRotation, LSLVector

from .common import current_object
from .registry import builtin


def _prim_by_link(obj, link: int, current_prim=None):
    if not obj:
        return None
    if link == -4:
        return current_prim
    for prim in obj.prims:
        if prim.link_number == link:
            return prim
    return None


def _get_param(prim, token: str):
    if token == "PRIM_NAME":
        return [prim.name]
    if token == "PRIM_DESC":
        return [prim.description]
    if token == "PRIM_SIZE":
        return [prim.scale]
    if token == "PRIM_POS_LOCAL":
        return [prim.local_pos]
    if token == "PRIM_ROT_LOCAL":
        return [prim.local_rot]
    if token == "PRIM_TEXT":
        text = prim.floating_text
        return [text["text"], text["color"], text["alpha"]]
    return []


def _set_param(prim, token: str, values: list):
    if token == "PRIM_NAME":
        prim.name = str(values[0])
        return 1
    if token == "PRIM_DESC":
        prim.description = str(values[0])
        return 1
    if token == "PRIM_SIZE":
        prim.scale = values[0]
        return 1
    if token == "PRIM_POS_LOCAL":
        prim.local_pos = values[0]
        return 1
    if token == "PRIM_ROT_LOCAL":
        prim.local_rot = values[0]
        return 1
    if token == "PRIM_TEXT":
        prim.floating_text = {"text": str(values[0]), "color": values[1], "alpha": float(values[2])}
        return 3
    return 0


def _get_params_for_prim(prim, params):
    result = LSLList()
    if not prim:
        return result
    for param in params:
        result.extend(_get_param(prim, str(param)))
    return result


def _set_params_for_prim(prim, params):
    if not prim:
        return None
    index = 0
    while index < len(params):
        token = str(params[index])
        consumed = _set_param(prim, token, params[index + 1:])
        index += 1 + consumed if consumed else 1
    return None


@builtin("llGetPrimitiveParams")
def ll_get_primitive_params(evaluator, args):
    script = evaluator.script
    return _get_params_for_prim(script.container_prim if script else None, args[0])


@builtin("llSetPrimitiveParams")
def ll_set_primitive_params(evaluator, args):
    script = evaluator.script
    _set_params_for_prim(script.container_prim if script else None, args[0])
    return None


@builtin("llGetLinkPrimitiveParams")
def ll_get_link_primitive_params(evaluator, args):
    script = evaluator.script
    obj = current_object(script)
    prim = _prim_by_link(obj, int(args[0]), script.container_prim if script else None)
    return _get_params_for_prim(prim, args[1])


@builtin("llSetLinkPrimitiveParamsFast")
def ll_set_link_primitive_params_fast(evaluator, args):
    script = evaluator.script
    obj = current_object(script)
    prim = _prim_by_link(obj, int(args[0]), script.container_prim if script else None)
    _set_params_for_prim(prim, args[1])
    return None


@builtin("llSetLinkPrimitiveParams")
def ll_set_link_primitive_params(evaluator, args):
    return ll_set_link_primitive_params_fast(evaluator, args)
