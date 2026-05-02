from __future__ import annotations

from typing import Any

from core.types import NULL_KEY
from sim.prim import ScriptItem


UNHANDLED = object()


def current_object(script: ScriptItem | None):
    if script and script.container_prim:
        return script.container_prim.parent_object
    return None


def current_region(script: ScriptItem | None):
    obj = current_object(script)
    return obj.region if obj else None


def console_for_script(script: ScriptItem | None):
    region = current_region(script)
    return getattr(region, "world_console", None) if region else None


def emit_console(
    script: ScriptItem | None,
    message_type: str,
    text: str,
    *,
    source_name: str = "",
    source_key: str = "",
    channel: int | None = None,
    stdout_text: str | None = None,
):
    console = console_for_script(script)
    if console:
        console.emit(
            message_type,
            text,
            source_name=source_name,
            source_key=source_key,
            channel=channel,
            stdout_text=stdout_text,
        )
    else:
        print(stdout_text if stdout_text is not None else text)


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def inventory_matches_type(item, item_type: int) -> bool:
    return item_type == -1 or item.type == item_type


def null_key_if_missing(value: str | None) -> str:
    return value or NULL_KEY
