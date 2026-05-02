# API Status

This list reflects builtin handling exported by `core/builtins/runtime.py`.
The runtime is a registry over smaller modules in `core/builtins/`, grouped by
API family so individual handlers are easy to find.

For the full official wiki function list with local implementation flags, see
`docs/lsl-functions-status.md` or the machine-readable
`data/lsl_functions_status.csv`.

## Implemented or Stubbed APIs

Communication:
- `llSay`
- `llWhisper`
- `llShout`
- `llRegionSay`
- `llRegionSayTo`
- `llOwnerSay`
- `llListen`
- `llListenRemove`
- `llMessageLinked`

Object:
- `llGetOwner`
- `llGetKey`
- `llGetObjectName`
- `llSetObjectName`
- `llGetObjectDesc`
- `llSetObjectDesc`
- `llGetOwnerKey`
- `llGetCreator`
- `llGetPos`
- `llSetPos`
- `llGetRot`
- `llSetRot`
- `llGetVel`
- `llGetScale`
- `llSetScale`
- `llGetLinkNumber`
- `llGetNumberOfPrims`
- `llGetObjectPrimCount`
- `llGetLinkName`
- `llGetLinkKey`
- `llGetObjectDetails`
- `llGetMass`
- `llGetObjectMass`

Primitive Parameters:
- `llGetPrimitiveParams`
- `llSetPrimitiveParams`
- `llGetLinkPrimitiveParams`
- `llSetLinkPrimitiveParams`
- `llSetLinkPrimitiveParamsFast`

Region / Parcel / Avatar:
- `llGetRegionName`
- `llGetRegionCorner`
- `llGetRegionFPS`
- `llGetRegionTimeDilation`
- `llWater`
- `llWind`
- `llGetAgentList`
- `llKey2Name`
- `llGetDisplayName`
- `llRequestDisplayName`
- `llRequestUsername`
- `llGetAgentLanguage`
- `llGetParcelDetails`
- `llGetParcelMusicURL`
- `llSetParcelMusicURL`

Inventory:
- `llGetInventoryAcquireTime`
- `llGetInventoryCreator`
- `llGetInventoryDesc`
- `llGetInventoryKey`
- `llGetInventoryName`
- `llGetInventoryNumber`
- `llGetInventoryPermMask`
- `llGetInventoryType`

Dataserver:
- `llGetNotecardLine`
- `llGetNumberOfNotecardLines`

Sensors:
- `llSensor`
- `llSensorRepeat`
- `llSensorRemove`
- `llDetectedName`
- `llDetectedKey`
- `llDetectedOwner`
- `llDetectedPos`
- `llDetectedRot`
- `llDetectedVel`
- `llDetectedGroup`
- `llDetectedType`
- `llDetectedLinkNumber`

Stored Effects:
- `llSetText`
- `llParticleSystem`
- `llSetTextureAnim`
- `llPreloadSound`
- `llPlaySound`
- `llLoopSound`
- `llTriggerSound`
- `llStopSound`

Timer and Time:
- `llSetTimerEvent`
- `llGetTime` (stubbed)
- `llResetTime` (stubbed)

List:
- `llGetListLength`
- `llList2Float`
- `llList2Integer`
- `llList2Key`
- `llList2Rot`
- `llList2String`
- `llList2Vector`
- `llListFindList`
- `llListReplaceList`
- `llDeleteSubList`
- `llList2CSV`
- `llCSV2List`
- `llList2List`

String:
- `llStringLength`
- `llSubStringIndex`
- `llGetSubString`

Linkset Data:
- `llLinksetDataWrite`
- `llLinksetDataRead`
- `llLinksetDataDelete`
- `llLinksetDataReset`

Rez / Object Lifecycle:
- `llRezObject`
- `llRezAtRoot`

HTTP / JSON:
- `llHTTPRequest`
- `llJsonGetValue`

Stubbed APIs:
- Selected missing simulator APIs are registered in `core/builtins/stubs.py`.
- These handlers print `STUB <name>: not implemented` and return a typed default (`0`, `""`, `NULL_KEY`, empty vector/rotation/list, or `None`).
- Stubbed APIs are marked `partial` in `docs/lsl-functions-status.md`.

Constants currently available in the execution context:
- `TRUE`
- `FALSE`
- `NULL_KEY`
- `AGENT`
- `ACTIVE`
- `PASSIVE`
- `SCRIPTED`
- `LINK_SET`
- `LINK_ALL_OTHERS`
- `LINK_ALL_CHILDREN`
- `LINK_THIS`
- `LINK_ROOT`
- `HTTP_METHOD`
- `HTTP_BODY_MAXLENGTH`
- `JSON_INVALID`
- `INVENTORY_NONE`
- `INVENTORY_ALL`
- `INVENTORY_TEXTURE`
- `INVENTORY_SOUND`
- `INVENTORY_CALLINGCARD`
- `INVENTORY_LANDMARK`
- `INVENTORY_CLOTHING`
- `INVENTORY_OBJECT`
- `INVENTORY_NOTECARD`
- `INVENTORY_SCRIPT`
- `INVENTORY_BODYPART`
- `INVENTORY_ANIMATION`
- `INVENTORY_GESTURE`
- `MASK_BASE`
- `MASK_OWNER`
- `MASK_GROUP`
- `MASK_EVERYONE`
- `MASK_NEXT`
- `PRIM_NAME`
- `PRIM_DESC`
- `PRIM_SIZE`
- `PRIM_POS_LOCAL`
- `PRIM_ROT_LOCAL`
- `PRIM_TEXT`
- `AGENT_LIST_REGION`
- `AGENT_LIST_PARCEL`
- `OBJECT_NAME`
- `OBJECT_DESC`
- `OBJECT_POS`
- `OBJECT_ROT`
- `OBJECT_VELOCITY`
- `OBJECT_OWNER`
- `OBJECT_GROUP`
- `OBJECT_CREATOR`
- `OBJECT_RUNNING_SCRIPT_COUNT`
- `PARCEL_DETAILS_NAME`
- `PARCEL_DETAILS_DESC`
- `PARCEL_DETAILS_OWNER`
- `PARCEL_DETAILS_GROUP`
- `PARCEL_DETAILS_AREA`
- `PARCEL_DETAILS_ID`
- `PARCEL_DETAILS_SEE_AVATARS`

## Major Missing API Families

- Dialogs and controls: `llDialog` is simplified; `llTextBox`, `llTakeControls`, and `llReleaseControls` are still missing behavior.
- Dataserver and inventory: `llGetNotecardLine` and `llGetNumberOfNotecardLines` are simplified; inventory transfer and richer permission semantics are still missing.
- Object parameters: most `PRIM_*` constants beyond the small model-backed subset above.
- Avatar/agent: `llRequestAgentData`, attachments, animations, and many detailed `llDetected*` touch/collision APIs.
- Region/parcel: most detailed region/parcel/media/audio APIs beyond the simple model-backed subset above.
- Rez and object lifecycle: `llRezObject` / `llRezAtRoot` are simplified; `llDie`, `llResetScript`, `llGetScriptName`, and richer rez parameter handling are still missing.
- Physics/collision: volume detect, buoyancy, forces, impulses, collision events.
- Media, camera, pathfinding, experience, money, permissions, email/XML-RPC, and most environment APIs.

## Notes

- Several implemented APIs are pragmatic offline stubs, not bit-for-bit Second Life behavior.
- Notecard dataserver APIs live in `core/builtins/dataserver.py` and queue `dataserver` events from in-object notecard inventory.
- Rez APIs clone stored inventory objects from the current prim into the region and enforce `world.max_rezzed_objects` to prevent runaway spawning.
- Sensor APIs scan seeded region avatars/objects, support name/key/type/range filters, queue `sensor`/`no_sensor`, and expose simplified detected records.
- Unknown `ll*` functions are not compile-time errors yet; they fail when executed.
- Builtin signature/type validation is not centralized yet. That should be the next structural step before filling out the long API tail.
