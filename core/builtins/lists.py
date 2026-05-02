from __future__ import annotations

from core.types import LSLList, LSLRotation, LSLVector, NULL_KEY

from .registry import builtin


@builtin("llGetListLength")
def ll_get_list_length(evaluator, args):
    return len(args[0])


@builtin("llList2Integer")
def ll_list_2_integer(evaluator, args):
    return int(args[0][int(args[1])])


@builtin("llList2Float")
def ll_list_2_float(evaluator, args):
    return float(args[0][int(args[1])])


@builtin("llList2String")
def ll_list_2_string(evaluator, args):
    return str(args[0][int(args[1])])


@builtin("llList2Key")
def ll_list_2_key(evaluator, args):
    try:
        return str(args[0][int(args[1])])
    except Exception:
        return NULL_KEY


@builtin("llList2Vector")
def ll_list_2_vector(evaluator, args):
    value = args[0][int(args[1])]
    return value if isinstance(value, LSLVector) else LSLVector()


@builtin("llList2Rot")
def ll_list_2_rot(evaluator, args):
    value = args[0][int(args[1])]
    return value if isinstance(value, LSLRotation) else LSLRotation()


@builtin("llListFindList")
def ll_list_find_list(evaluator, args):
    try:
        target = args[0]
        search = args[1]
        for index in range(len(target) - len(search) + 1):
            if target[index:index + len(search)] == search:
                return index
        return -1
    except Exception:
        return -1


@builtin("llListReplaceList")
def ll_list_replace_list(evaluator, args):
    dest = args[0]
    src = args[1]
    start = int(args[2])
    end = int(args[3])
    return LSLList(dest[:start]) + src + LSLList(dest[end + 1:])


@builtin("llDeleteSubList")
def ll_delete_sub_list(evaluator, args):
    dest = args[0]
    start = int(args[1])
    end = int(args[2])
    return LSLList(dest[:start]) + LSLList(dest[end + 1:])


@builtin("llList2CSV")
def ll_list_2_csv(evaluator, args):
    return ",".join(map(str, args[0]))


@builtin("llCSV2List")
def ll_csv_2_list(evaluator, args):
    if not args[0]:
        return LSLList()
    return LSLList(str(args[0]).split(","))


@builtin("llList2List")
def ll_list_2_list(evaluator, args):
    src = args[0]
    start = int(args[1])
    end = int(args[2])

    def lsl_idx(idx, length):
        if idx < 0:
            return length + idx
        return idx

    length = len(src)
    start_idx = lsl_idx(start, length)
    end_idx = lsl_idx(end, length)
    if start_idx > end_idx:
        return LSLList(src[start_idx:]) + LSLList(src[:end_idx + 1])
    return LSLList(src[start_idx:end_idx + 1])
