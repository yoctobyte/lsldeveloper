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


@builtin("llDumpList2String")
def ll_dump_list_2_string(evaluator, args):
    src = args[0]
    sep = str(args[1])
    return sep.join(str(e) for e in src)


def _parse_string(source: str, separators: list, spacers: list, keep_nulls: bool) -> LSLList:
    # LSL llParseString2List / llParseStringKeepNulls:
    # Split source on any separator or spacer token. Separators are discarded;
    # spacers are kept as elements. Empty elements are dropped unless keep_nulls.
    seps = [str(s) for s in separators]
    spcs = [str(s) for s in spacers]
    all_tokens = seps + spcs
    # Sort longest first so multi-char tokens match before their prefixes.
    all_tokens.sort(key=len, reverse=True)

    result = []
    current = ""
    i = 0
    while i < len(source):
        matched = False
        for token in all_tokens:
            if source[i:i + len(token)] == token:
                if keep_nulls or current:
                    result.append(current)
                current = ""
                if token in spcs:
                    result.append(token)
                i += len(token)
                matched = True
                break
        if not matched:
            current += source[i]
            i += 1
    if keep_nulls or current:
        result.append(current)
    return LSLList(result)


@builtin("llParseString2List")
def ll_parse_string_2_list(evaluator, args):
    return _parse_string(str(args[0]), list(args[1]), list(args[2]), keep_nulls=False)


@builtin("llParseStringKeepNulls")
def ll_parse_string_keep_nulls(evaluator, args):
    return _parse_string(str(args[0]), list(args[1]), list(args[2]), keep_nulls=True)


@builtin("llListSort")
def ll_list_sort(evaluator, args):
    src    = list(args[0]) if args[0] else []
    stride = max(1, int(args[1]))
    asc    = bool(args[2])
    chunks = [src[i:i + stride] for i in range(0, len(src), stride)]
    # Sort by first element of each chunk; mixed-type comparison falls back to str
    def _key(c):
        v = c[0]
        # LSL sorts integers/floats numerically, strings lexicographically
        if isinstance(v, (int, float)):
            return (0, float(v), "")
        return (1, 0.0, str(v))
    chunks.sort(key=_key, reverse=not asc)
    result = LSLList()
    for chunk in chunks:
        result.extend(chunk)
    return result


@builtin("llListRandomize")
def ll_list_randomize(evaluator, args):
    import random
    src    = list(args[0]) if args[0] else []
    stride = max(1, int(args[1]))
    chunks = [src[i:i + stride] for i in range(0, len(src), stride)]
    random.shuffle(chunks)
    result = LSLList()
    for chunk in chunks:
        result.extend(chunk)
    return result


@builtin("llListStatistics")
def ll_list_statistics(evaluator, args):
    # operation, list → commonly used for LIST_STAT_MAX/MIN/MEAN etc.
    # Return 0.0 as a safe default for unsupported ops
    return 0.0


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
