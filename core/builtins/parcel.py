from __future__ import annotations

from core.types import LSLList

from .common import current_object, current_region
from .registry import builtin


@builtin("llGetParcelDetails")
def ll_get_parcel_details(evaluator, args):
    region = current_region(evaluator.script)
    parcel = region.parcel_at(args[0]) if region else None
    details = LSLList()
    if not parcel:
        return details
    values = {
        "PARCEL_DETAILS_NAME": parcel.name,
        "PARCEL_DETAILS_DESC": parcel.description,
        "PARCEL_DETAILS_OWNER": parcel.owner_key,
        "PARCEL_DETAILS_GROUP": parcel.group_key,
        "PARCEL_DETAILS_AREA": parcel.area,
        "PARCEL_DETAILS_ID": parcel.uuid,
        "PARCEL_DETAILS_SEE_AVATARS": 1,
    }
    for detail in args[1]:
        details.append(values.get(str(detail), ""))
    return details


@builtin("llGetParcelMusicURL")
def ll_get_parcel_music_url(evaluator, args):
    obj = current_object(evaluator.script)
    region = current_region(evaluator.script)
    if obj and region:
        parcel = region.parcel_at(obj.position)
        return parcel.music_url if parcel else ""
    return ""


@builtin("llSetParcelMusicURL")
def ll_set_parcel_music_url(evaluator, args):
    obj = current_object(evaluator.script)
    region = current_region(evaluator.script)
    if obj and region:
        parcel = region.parcel_at(obj.position)
        if parcel:
            parcel.music_url = str(args[0])
    return None
