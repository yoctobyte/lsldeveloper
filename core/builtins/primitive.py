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


_PRIM_NAME     = 27
_PRIM_DESC     = 28
_PRIM_SIZE     = 23
_PRIM_POSITION = 2
_PRIM_POS_LOCAL = 33
_PRIM_ROT_LOCAL = 29
_PRIM_TEXT     = 26
_PRIM_LINK_TARGET = 34


def _token_int(token) -> int:
    try:
        return int(token)
    except (ValueError, TypeError):
        return -1


def _get_param(prim, token_int: int) -> list:
    if token_int == _PRIM_NAME:
        return [prim.name]
    if token_int == _PRIM_DESC:
        return [prim.description]
    if token_int == _PRIM_SIZE:
        return [prim.scale]
    if token_int in (_PRIM_POSITION, _PRIM_POS_LOCAL):
        return [prim.local_pos]
    if token_int == _PRIM_ROT_LOCAL:
        return [prim.local_rot]
    if token_int == _PRIM_TEXT:
        text = prim.floating_text
        return [text["text"], text["color"], text["alpha"]]
    return []


def _set_param(prim, token_int: int, values: list) -> int:
    if token_int == _PRIM_NAME:
        prim.name = str(values[0])
        return 1
    if token_int == _PRIM_DESC:
        prim.description = str(values[0])
        return 1
    if token_int == _PRIM_SIZE:
        prim.scale = values[0]
        return 1
    if token_int in (_PRIM_POSITION, _PRIM_POS_LOCAL):
        prim.local_pos = values[0]
        return 1
    if token_int == _PRIM_ROT_LOCAL:
        prim.local_rot = values[0]
        return 1
    if token_int == _PRIM_TEXT:
        prim.floating_text = {"text": str(values[0]), "color": values[1], "alpha": float(values[2])}
        return 3
    return 0


def _get_params_for_prim(prim, params):
    result = LSLList()
    if not prim:
        return result
    for param in params:
        result.extend(_get_param(prim, _token_int(param)))
    return result


def _set_params_for_prim(prim, params, obj=None):
    if not prim:
        return None
    index = 0
    while index < len(params):
        token_int = _token_int(params[index])
        if token_int == _PRIM_LINK_TARGET and obj is not None:
            link = int(params[index + 1]) if index + 1 < len(params) else 0
            prim = _prim_by_link(obj, link, prim)
            index += 2
            continue
        consumed = _set_param(prim, token_int, params[index + 1:])
        index += 1 + consumed if consumed else 1
    return None


@builtin("llGetPrimitiveParams")
def ll_get_primitive_params(evaluator, args):
    script = evaluator.script
    return _get_params_for_prim(script.container_prim if script else None, args[0])


@builtin("llSetPrimitiveParams")
def ll_set_primitive_params(evaluator, args):
    script = evaluator.script
    obj = current_object(script)
    _set_params_for_prim(script.container_prim if script else None, args[0], obj)
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
    _set_params_for_prim(prim, args[1], obj)
    return None


@builtin("llSetLinkPrimitiveParams")
def ll_set_link_primitive_params(evaluator, args):
    return ll_set_link_primitive_params_fast(evaluator, args)
