from __future__ import annotations

from core.types import LSLList, LSLRotation, LSLVector, NULL_KEY

from .common import emit_console
from .registry import REGISTRY, builtin


RETURN_DEFAULTS = {
    "integer": 0,
    "float": 0.0,
    "string": "",
    "key": NULL_KEY,
    "vector": LSLVector(),
    "rotation": LSLRotation(),
    "list": LSLList(),
    "void": None,
}


STUBS = {
    "llAddToLandPassList": "void",
    "llAdjustSoundVolume": "void",
    "llAllowInventoryDrop": "void",
    "llApplyImpulse": "void",
    "llApplyRotationalImpulse": "void",
    "llAttachToAvatar": "void",
    "llAttachToAvatarTemp": "void",
    "llAvatarOnSitTarget": "key",
    "llClearCameraParams": "void",
    "llCollisionFilter": "void",
    "llCreateLink": "void",
    "llDeleteCharacter": "void",
    "llDetachFromAvatar": "void",
    "llDialog": "void",
    "llDie": "void",
    "llEjectFromLand": "void",
    "llEmail": "void",
    "llGetAndResetTime": "float",
    "llGetAnimation": "string",
    "llGetAnimationList": "list",
    "llGetAttached": "integer",
    "llGetBoundingBox": "list",
    "llGetCameraPos": "vector",
    "llGetCameraRot": "rotation",
    "llGetCenterOfMass": "vector",
    "llGetGeometricCenter": "vector",
    "llGetGMTclock": "float",
    "llGetNextEmail": "void",
    "llGetNotecardLine": "key",
    "llGetNumberOfNotecardLines": "key",
    "llGetObjectPermMask": "integer",
    "llGetPermissions": "integer",
    "llGetPermissionsKey": "key",
    "llGetRootPosition": "vector",
    "llGetRootRotation": "rotation",
    "llGetScriptState": "integer",
    "llGetStatus": "integer",
    "llGetSunDirection": "vector",
    "llGetTimeOfDay": "float",
    "llGetTimestamp": "string",
    "llGetUsedMemory": "integer",
    "llGiveInventory": "void",
    "llGiveInventoryList": "void",
    "llGround": "float",
    "llGroundContour": "vector",
    "llGroundNormal": "vector",
    "llGroundRepel": "void",
    "llGroundSlope": "vector",
    "llLoadURL": "void",
    "llMakeExplosion": "void",
    "llMakeFire": "void",
    "llMakeFountain": "void",
    "llMakeSmoke": "void",
    "llMapDestination": "void",
    "llMinEventDelay": "void",
    "llModifyLand": "void",
    "llOpenRemoteDataChannel": "void",
    "llOverMyLand": "integer",
    "llPassCollisions": "void",
    "llPassTouches": "void",
    "llPushObject": "void",
    "llRefreshPrimURL": "void",
    "llReleaseControls": "void",
    "llReleaseURL": "void",
    "llRemoteDataReply": "void",
    "llRemoteLoadScriptPin": "void",
    "llRemoveFromLandPassList": "void",
    "llRemoveInventory": "void",
    "llRequestAgentData": "key",
    "llRequestInventoryData": "key",
    "llRequestPermissions": "void",
    "llRequestSecureURL": "key",
    "llRequestSimulatorData": "key",
    "llRequestURL": "key",
    "llResetOtherScript": "void",
    "llResetScript": "void",
    "llRotLookAt": "void",
    "llSetAlpha": "void",
    "llSetAngularVelocity": "void",
    "llSetBuoyancy": "void",
    "llSetCameraAtOffset": "void",
    "llSetCameraEyeOffset": "void",
    "llSetCameraParams": "void",
    "llSetClickAction": "void",
    "llSetColor": "void",
    "llSetDamage": "void",
    "llSetForce": "void",
    "llSetForceAndTorque": "void",
    "llSetHoverHeight": "void",
    "llSetLinkAlpha": "void",
    "llSetLinkColor": "void",
    "llSetLinkTexture": "void",
    "llSetLocalRot": "void",
    "llSetPayPrice": "void",
    "llSetRemoteScriptAccessPin": "void",
    "llSetScriptState": "void",
    "llSetSitText": "void",
    "llSetSoundQueueing": "void",
    "llSetStatus": "void",
    "llSetTexture": "void",
    "llSetTorque": "void",
    "llSetTouchText": "void",
    "llSetVehicleFlags": "void",
    "llSitTarget": "void",
    "llSleep": "void",
    "llStopAnimation": "void",
    "llTakeControls": "void",
    "llTarget": "integer",
    "llTargetRemove": "void",
    "llTeleportAgent": "void",
    "llTeleportAgentGlobalCoords": "void",
    "llTeleportAgentHome": "void",
    "llTextBox": "void",
    "llTriggerSoundLimited": "void",
    "llUnSit": "void",
    "llVolumeDetect": "void",
    "llWanderWithin": "void",
}


REGISTERED_STUBS: dict[str, str] = {}


def make_stub(name: str, return_type: str):
    if name in REGISTRY:
        return None

    @builtin(name)
    def stub(evaluator, args):
        warning = f"STUB {name}: not implemented; returning default {return_type}"
        emit_console(evaluator.script, "stub", warning, stdout_text=warning)
        return RETURN_DEFAULTS[return_type]

    REGISTERED_STUBS[name] = return_type
    return stub


for _name, _return_type in STUBS.items():
    make_stub(_name, _return_type)
