from __future__ import annotations

from core.types import NULL_KEY

from .common import inventory_matches_type
from .registry import builtin


def _inventory(script):
    if script and script.container_prim:
        return script.container_prim.inventory
    return []


def _items_of_type(script, item_type: int):
    return [item for item in _inventory(script) if inventory_matches_type(item, item_type)]


def _item_by_name(script, name: str):
    for item in _inventory(script):
        if item.name == name:
            return item
    return None


@builtin("llGetInventoryNumber")
def ll_get_inventory_number(evaluator, args):
    return len(_items_of_type(evaluator.script, int(args[0])))


@builtin("llGetInventoryName")
def ll_get_inventory_name(evaluator, args):
    items = _items_of_type(evaluator.script, int(args[0]))
    index = int(args[1])
    if 0 <= index < len(items):
        return items[index].name
    return ""


@builtin("llGetInventoryType")
def ll_get_inventory_type(evaluator, args):
    item = _item_by_name(evaluator.script, str(args[0]))
    return item.type if item else -1


@builtin("llGetInventoryKey")
def ll_get_inventory_key(evaluator, args):
    item = _item_by_name(evaluator.script, str(args[0]))
    return item.uuid if item else NULL_KEY


@builtin("llGetInventoryCreator")
def ll_get_inventory_creator(evaluator, args):
    item = _item_by_name(evaluator.script, str(args[0]))
    return getattr(item, "creator_key", NULL_KEY) if item else NULL_KEY


@builtin("llGetInventoryDesc")
def ll_get_inventory_desc(evaluator, args):
    item = _item_by_name(evaluator.script, str(args[0]))
    return getattr(item, "description", "") if item else ""


@builtin("llGetInventoryAcquireTime")
def ll_get_inventory_acquire_time(evaluator, args):
    item = _item_by_name(evaluator.script, str(args[0]))
    return getattr(item, "acquire_time", "") if item else ""


@builtin("llGetInventoryPermMask")
def ll_get_inventory_perm_mask(evaluator, args):
    item = _item_by_name(evaluator.script, str(args[0]))
    return getattr(item, "perm_mask", 0x7FFFFFFF) if item else 0
