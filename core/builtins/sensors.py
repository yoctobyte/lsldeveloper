from __future__ import annotations

from typing import Any

from core.types import LSLRotation, LSLVector, NULL_KEY
from events.queue import LSLEvent
from sim.prim import ScriptItem

from .common import current_object, current_region
from .registry import builtin


def detected_at(script: ScriptItem | None, index: int) -> dict[str, Any]:
    if script and 0 <= index < len(script.detected):
        return script.detected[index]
    return {}


def _matches_sensor_filter(record: dict[str, Any], name: str, key: str, type_mask: int) -> bool:
    if name and record["name"] != name:
        return False
    if key and key != NULL_KEY and record["key"] != key:
        return False
    if type_mask and not (record["type"] & type_mask):
        return False
    return True


def queue_sensor_event(
    script: ScriptItem | None,
    *,
    name_filter: str,
    key_filter: str,
    type_mask: int,
    range_meters: float,
    arc: float,
) -> list[dict[str, Any]]:
    obj = current_object(script)
    region = current_region(script)
    if not script or not obj or not region:
        return []

    origin = obj.position
    detected = []
    for avatar in region.avatars.values():
        distance = (avatar.position - origin).magnitude()
        record = {
            "name": avatar.name,
            "key": avatar.uuid,
            "owner": avatar.uuid,
            "pos": avatar.position,
            "rot": avatar.rotation,
            "vel": LSLVector(),
            "group": avatar.group_key,
            "type": 1,
            "link_number": 0,
            "distance": distance,
        }
        if distance <= range_meters and _matches_sensor_filter(record, name_filter, key_filter, type_mask):
            detected.append(record)

    for target in region.objects.values():
        if target.uuid == obj.uuid:
            continue
        distance = (target.position - origin).magnitude()
        record = {
            "name": target.name,
            "key": target.uuid,
            "owner": target.owner_key,
            "pos": target.position,
            "rot": target.rotation,
            "vel": target.velocity,
            "group": target.group_key,
            "type": 2 | 4 | (8 if any(prim.inventory for prim in target.prims) else 0),
            "link_number": 1,
            "distance": distance,
        }
        if distance <= range_meters and _matches_sensor_filter(record, name_filter, key_filter, type_mask):
            detected.append(record)

    detected.sort(key=lambda item: item["distance"])
    event_name = "sensor" if detected else "no_sensor"
    script.event_queue.push(LSLEvent(event_name, [len(detected)], detected))
    return detected


@builtin("llSensor")
def ll_sensor(evaluator, args):
    queue_sensor_event(
        evaluator.script,
        name_filter=str(args[0]),
        key_filter=str(args[1]),
        type_mask=int(args[2]),
        range_meters=float(args[3]),
        arc=float(args[4]),
    )
    return None


@builtin("llSensorRepeat")
def ll_sensor_repeat(evaluator, args):
    script = evaluator.script
    if script:
        query = {
            "name_filter": str(args[0]),
            "key_filter": str(args[1]),
            "type_mask": int(args[2]),
            "range_meters": float(args[3]),
            "arc": float(args[4]),
        }
        script.sensor_repeat = {"query": query, "interval": float(args[5])}
        queue_sensor_event(script, **query)
    return None


@builtin("llSensorRemove")
def ll_sensor_remove(evaluator, args):
    if evaluator.script:
        evaluator.script.sensor_repeat = None
    return None


@builtin("llDetectedName")
def ll_detected_name(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("name", "")


@builtin("llDetectedKey")
def ll_detected_key(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("key", NULL_KEY)


@builtin("llDetectedOwner")
def ll_detected_owner(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("owner", NULL_KEY)


@builtin("llDetectedPos")
def ll_detected_pos(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("pos", LSLVector())


@builtin("llDetectedRot")
def ll_detected_rot(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("rot", LSLRotation())


@builtin("llDetectedVel")
def ll_detected_vel(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("vel", LSLVector())


@builtin("llDetectedGroup")
def ll_detected_group(evaluator, args):
    record = detected_at(evaluator.script, int(args[0]))
    obj = current_object(evaluator.script)
    return int(bool(record and obj and record.get("group") == obj.group_key and obj.group_key != NULL_KEY))


@builtin("llDetectedType")
def ll_detected_type(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("type", 0)


@builtin("llDetectedLinkNumber")
def ll_detected_link_number(evaluator, args):
    return detected_at(evaluator.script, int(args[0])).get("link_number", 0)
