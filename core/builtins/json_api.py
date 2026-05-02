from __future__ import annotations

import json

from .registry import builtin


@builtin("llJsonGetValue")
def ll_json_get_value(evaluator, args):
    try:
        data = json.loads(str(args[0]))
        value = data
        for specifier in args[1]:
            value = value[specifier]
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)
    except Exception:
        return "JSON_INVALID"
