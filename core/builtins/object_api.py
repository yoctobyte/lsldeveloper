from __future__ import annotations

from core.types import LSLList, LSLRotation, LSLVector, NULL_KEY
from sim.prim import ScriptItem

from .common import current_object, current_region
from .registry import builtin


def _prim_by_link(obj, link: int):
    for prim in obj.prims:
        if prim.link_number == link:
            return prim
    return None


@builtin("llGetOwner")
def ll_get_owner(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.owner_key if obj else NULL_KEY


@builtin("llGetKey")
def ll_get_key(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.uuid if obj else NULL_KEY


@builtin("llGetCreator")
def ll_get_creator(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.creator_key if obj else NULL_KEY


@builtin("llGetOwnerKey")
def ll_get_owner_key(evaluator, args):
    region = current_region(evaluator.script)
    if region:
        obj = region.find_object(str(args[0]))
        if obj:
            return obj.owner_key
        avatar = region.find_agent(str(args[0]))
        if avatar:
            return avatar.uuid
    return NULL_KEY


@builtin("llGetObjectName")
def ll_get_object_name(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.name if obj else ""


@builtin("llSetObjectName")
def ll_set_object_name(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.name = str(args[0])
    return None


@builtin("llGetObjectDesc")
def ll_get_object_desc(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.description if obj else ""


@builtin("llSetObjectDesc")
def ll_set_object_desc(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.description = str(args[0])
    return None


@builtin("llGetPos")
def ll_get_pos(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.position if obj else LSLVector()


@builtin("llSetPos")
def ll_set_pos(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.position = args[0]
    return None


@builtin("llGetRot")
def ll_get_rot(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.rotation if obj else LSLRotation()


@builtin("llSetRot")
def ll_set_rot(evaluator, args):
    obj = current_object(evaluator.script)
    if obj:
        obj.rotation = args[0]
    return None


@builtin("llGetVel")
def ll_get_vel(evaluator, args):
    obj = current_object(evaluator.script)
    return obj.velocity if obj else LSLVector()


@builtin("llGetScale")
def ll_get_scale(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        return script.container_prim.scale
    return LSLVector(0.5, 0.5, 0.5)


@builtin("llSetScale")
def ll_set_scale(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        script.container_prim.scale = args[0]
    return None


@builtin("llGetLinkNumber")
def ll_get_link_number(evaluator, args):
    script = evaluator.script
    if script and script.container_prim:
        return script.container_prim.link_number
    return 0


@builtin("llGetNumberOfPrims")
def ll_get_number_of_prims(evaluator, args):
    obj = current_object(evaluator.script)
    return len(obj.prims) if obj else 0


@builtin("llGetObjectPrimCount")
def ll_get_object_prim_count(evaluator, args):
    region = current_region(evaluator.script)
    target = region.find_object(str(args[0])) if region else None
    return len(target.prims) if target else 0


@builtin("llGetLinkName")
def ll_get_link_name(evaluator, args):
    obj = current_object(evaluator.script)
    prim = _prim_by_link(obj, int(args[0])) if obj else None
    return prim.name if prim else ""


@builtin("llGetLinkKey")
def ll_get_link_key(evaluator, args):
    obj = current_object(evaluator.script)
    prim = _prim_by_link(obj, int(args[0])) if obj else None
    return prim.uuid if prim else NULL_KEY


@builtin("llGetObjectDetails")
def ll_get_object_details(evaluator, args):
    region = current_region(evaluator.script)
    target = region.find_object(str(args[0])) if region else None
    details = LSLList()
    if not target:
        return details
    running_scripts = sum(
        1
        for prim in target.prims
        for item in prim.inventory
        if isinstance(item, ScriptItem) and item.running
    )
    values = {
        "OBJECT_NAME": target.name,
        "OBJECT_DESC": target.description,
        "OBJECT_POS": target.position,
        "OBJECT_ROT": target.rotation,
        "OBJECT_VELOCITY": target.velocity,
        "OBJECT_OWNER": target.owner_key,
        "OBJECT_GROUP": target.group_key,
        "OBJECT_CREATOR": target.creator_key,
        "OBJECT_RUNNING_SCRIPT_COUNT": running_scripts,
    }
    for detail in args[1]:
        details.append(values.get(str(detail), ""))
    return details


@builtin("llGetMass")
def ll_get_mass(evaluator, args):
    obj = current_object(evaluator.script)
    return float(len(obj.prims)) if obj else 0.0


@builtin("llGetObjectMass")
def ll_get_object_mass(evaluator, args):
    region = current_region(evaluator.script)
    target = region.find_object(str(args[0])) if region else None
    return float(len(target.prims)) if target else 0.0
