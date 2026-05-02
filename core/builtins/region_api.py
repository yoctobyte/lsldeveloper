from __future__ import annotations

from core.types import LSLList, LSLVector

from .common import current_region
from .registry import builtin


@builtin("llGetRegionName")
def ll_get_region_name(evaluator, args):
    region = current_region(evaluator.script)
    return region.name if region else ""


@builtin("llGetRegionCorner")
def ll_get_region_corner(evaluator, args):
    region = current_region(evaluator.script)
    return region.corner if region else LSLVector()


@builtin("llGetRegionFPS")
def ll_get_region_fps(evaluator, args):
    region = current_region(evaluator.script)
    return region.fps if region else 0.0


@builtin("llGetRegionTimeDilation")
def ll_get_region_time_dilation(evaluator, args):
    region = current_region(evaluator.script)
    return region.time_dilation if region else 0.0


@builtin("llWater")
def ll_water(evaluator, args):
    region = current_region(evaluator.script)
    return region.water_height if region else 0.0


@builtin("llWind")
def ll_wind(evaluator, args):
    region = current_region(evaluator.script)
    return region.wind if region else LSLVector()


@builtin("llGetAgentList")
def ll_get_agent_list(evaluator, args):
    region = current_region(evaluator.script)
    return LSLList(list(region.avatars.keys())) if region else LSLList()


@builtin("llKey2Name", "llRequestUsername", "llRequestDisplayName")
def ll_key_2_name(evaluator, args):
    region = current_region(evaluator.script)
    return region.entity_name(str(args[0])) if region else ""


@builtin("llGetDisplayName")
def ll_get_display_name(evaluator, args):
    region = current_region(evaluator.script)
    avatar = region.find_agent(str(args[0])) if region else None
    return avatar.display_name if avatar else ""


@builtin("llGetAgentLanguage")
def ll_get_agent_language(evaluator, args):
    region = current_region(evaluator.script)
    avatar = region.find_agent(str(args[0])) if region else None
    return avatar.language if avatar else ""
