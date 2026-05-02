from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .common import UNHANDLED


BuiltinHandler = Callable[[Any, list[Any]], Any]
REGISTRY: dict[str, BuiltinHandler] = {}


def builtin(*names: str):
    def decorator(func: BuiltinHandler) -> BuiltinHandler:
        for name in names:
            REGISTRY[name] = func
        return func

    return decorator


def call_builtin(evaluator: Any, name: str, args: list[Any]) -> Any:
    handler = REGISTRY.get(name)
    if handler is None:
        return UNHANDLED
    previous = getattr(evaluator, "current_builtin_name", None)
    evaluator.current_builtin_name = name
    try:
        return handler(evaluator, args)
    finally:
        if previous is None:
            del evaluator.current_builtin_name
        else:
            evaluator.current_builtin_name = previous
