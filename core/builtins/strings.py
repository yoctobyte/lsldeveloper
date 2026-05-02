from __future__ import annotations

from .registry import builtin


@builtin("llStringLength")
def ll_string_length(evaluator, args):
    return len(str(args[0]))


@builtin("llSubStringIndex")
def ll_sub_string_index(evaluator, args):
    try:
        return str(args[0]).index(str(args[1]))
    except ValueError:
        return -1


@builtin("llGetSubString")
def ll_get_sub_string(evaluator, args):
    source = str(args[0])
    start = int(args[1])
    end = int(args[2])
    if end == -1:
        return source[start:]
    return source[start:end + 1]
