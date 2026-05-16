from __future__ import annotations

import hashlib
import random
import urllib.parse

from core.types import LSLList

from .common import emit_console
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


@builtin("llToLower")
def ll_to_lower(evaluator, args):
    return str(args[0]).lower()


@builtin("llToUpper")
def ll_to_upper(evaluator, args):
    return str(args[0]).upper()


@builtin("llFrand")
def ll_frand(evaluator, args):
    mag = float(args[0])
    return random.uniform(0.0, mag) if mag >= 0.0 else random.uniform(mag, 0.0)


@builtin("llMD5String")
def ll_md5_string(evaluator, args):
    text = str(args[0])
    nonce = int(args[1])
    data = f"{text}:{nonce}"
    return hashlib.md5(data.encode()).hexdigest()


@builtin("llGetEnv")
def ll_get_env(evaluator, args):
    name = str(args[0])
    from .common import current_region
    region = current_region(evaluator.script)
    env_map = {
        "region_product_name": "Second Life Server",
        "region_product_sku": "",
        "sim_channel": "Second Life Server",
        "sim_version": "2024.0",
        "frame_number": "0",
        "region_max_prims": "15000",
        "region_object_bonus": "1.0",
        "script_limit": "100",
        "region_cpu_ratio": "1",
        "region_start": "0",
        "region_idle": "0",
        "region_fps": "45.0",
        "physics_engine": "Havok",
        "dynamic_pathfinding": "disabled",
    }
    if name == "region_hostname" and region:
        return region.name.lower().replace(" ", "-") + ".lindenlab.com"
    return env_map.get(name, "")


@builtin("llEscapeURL")
def ll_escape_url(evaluator, args):
    return urllib.parse.quote(str(args[0]), safe="")


@builtin("llUnescapeURL")
def ll_unescape_url(evaluator, args):
    return urllib.parse.unquote(str(args[0]))


@builtin("llStringTrim")
def ll_string_trim(evaluator, args):
    text  = str(args[0])
    flags = int(args[1])
    if flags == 1:   # STRING_TRIM_HEAD
        return text.lstrip()
    if flags == 2:   # STRING_TRIM_TAIL
        return text.rstrip()
    return text.strip()  # STRING_TRIM = 3


@builtin("llAbs")
def ll_abs(evaluator, args):
    return abs(int(args[0]))


@builtin("llInstantMessage")
def ll_instant_message(evaluator, args):
    target = str(args[0])
    message = str(args[1])
    emit_console(
        evaluator.script,
        "im",
        message,
        source_key=target,
        stdout_text=f"IM -> {target}: {message}",
    )
    return None
