from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.builtins.stubs import STUBS


SOURCE_URL = (
    "https://wiki.secondlife.com/w/index.php"
    "?title=Template:LSL_All_Functions/Name&action=raw"
)

CSV_OUT = Path("data/lsl_functions_status.csv")
JSON_OUT = Path("data/lsl_functions_status.json")
MD_OUT = Path("docs/lsl-functions-status.md")

IMPLEMENTED = {
    "llCSV2List": "basic CSV split",
    "llDeleteSubList": "basic slice delete",
    "llGetListLength": "Python len over list",
    "llGetSubString": "basic inclusive substring",
    "llLinksetDataDelete": "in-memory linkset data",
    "llLinksetDataRead": "in-memory linkset data",
    "llLinksetDataReset": "in-memory linkset data",
    "llLinksetDataWrite": "in-memory linkset data",
    "llList2CSV": "basic join",
    "llList2Float": "basic indexed conversion",
    "llList2Integer": "basic indexed conversion",
    "llList2Key": "basic indexed conversion",
    "llList2Rot": "basic indexed conversion",
    "llList2String": "basic indexed conversion",
    "llList2Vector": "basic indexed conversion",
    "llListFindList": "basic contiguous search",
    "llListReplaceList": "basic slice replace",
    "llStringLength": "Python string length",
    "llSubStringIndex": "Python substring search",
    "llAbs": "absolute integer value",
    "llAcos": "arc cosine in radians",
    "llAsin": "arc sine in radians",
    "llAtan2": "arc tangent of y/x",
    "llCeil": "smallest integer value not less than arg",
    "llCos": "cosine of angle in radians",
    "llFabs": "absolute float value",
    "llFloor": "largest integer value not greater than arg",
    "llLog": "natural logarithm",
    "llLog10": "base 10 logarithm",
    "llModPow": "modulo power of positive integers",
    "llPow": "power function",
    "llRound": "rounded integer",
    "llSin": "sine of angle in radians",
    "llSqrt": "square root",
    "llTan": "tangent of angle in radians",
    "llVecDist": "vector distance",
    "llVecMag": "vector magnitude",
    "llVecNorm": "vector normalization",
    "llFrand": "random float",
    "llStringTrim": "string trimming",
    "llToLower": "convert to lowercase",
    "llToUpper": "convert to uppercase",
    "llEscapeURL": "URL escape string",
    "llUnescapeURL": "URL unescape string",
    "llMD5String": "MD5 hash",
    "llDumpList2String": "dump list to string",
    "llListRandomize": "randomize list elements",
    "llListSort": "sort list elements",
    "llListStatistics": "compute list statistics",
    "llParseString2List": "parse string to list",
    "llParseStringKeepNulls": "parse string to list keeping nulls",
    "llGetUnixTime": "current unix timestamp",
    "llLinksetDataAvailable": "linkset data storage available",
    "llLinksetDataFindKeys": "find keys in linkset data",
    "llGetNumberOfSides": "returns the face count of the prim running the script",
}

PARTIAL = {
    "llDetectedGroup": "reads current simplified sensor detection record",
    "llDetectedKey": "reads current simplified sensor detection record",
    "llDetectedLinkNumber": "reads current simplified sensor detection record",
    "llDetectedName": "reads current simplified sensor detection record",
    "llDetectedOwner": "reads current simplified sensor detection record",
    "llDetectedPos": "reads current simplified sensor detection record",
    "llDetectedRot": "reads current simplified sensor detection record",
    "llDetectedTouchBinormal": "reads current simplified touch detection record",
    "llDetectedTouchFace": "reads current simplified touch detection record",
    "llDetectedTouchNormal": "reads current simplified touch detection record",
    "llDetectedTouchPos": "reads current simplified touch detection record",
    "llDetectedTouchST": "reads current simplified touch detection record",
    "llDetectedTouchUV": "reads current simplified touch detection record",
    "llDetectedType": "reads current simplified sensor detection record",
    "llDetectedVel": "reads current simplified sensor detection record",
    "llGetEnv": "reads current simplified simulator environment attributes",
    "llGetFreeMemory": "returns fixed simulated free memory",
    "llGetScriptName": "returns current script filename",
    "llHTTPResponse": "sends simplified HTTP response",
    "llInstantMessage": "emits diagnostic console instant message",
    "llSetRegionPos": "updates harness object region position within limits",
    "llDialog": "records latest dialog and emits button responses through chat",
    "llGetKey": "returns current harness object UUID",
    "llGetAgentLanguage": "reads demo avatar language",
    "llGetAgentList": "returns avatars in the current harness region",
    "llGetCreator": "reads harness object creator key",
    "llGetDisplayName": "reads demo avatar display name",
    "llGetInventoryAcquireTime": "reads stored inventory metadata when present",
    "llGetInventoryCreator": "reads stored inventory metadata when present",
    "llGetInventoryDesc": "reads stored inventory metadata when present",
    "llGetInventoryKey": "returns inventory item UUID by name",
    "llGetInventoryName": "returns inventory item names by type/index",
    "llGetInventoryNumber": "counts current prim inventory by type",
    "llGetInventoryPermMask": "returns stored inventory permissions or permissive default",
    "llGetInventoryType": "returns inventory item type by name",
    "llGetLinkPrimitiveParams": "supports a small model-backed PRIM_* subset",
    "llGetLinkKey": "reads prim UUID by link number",
    "llGetLinkName": "reads prim name by link number",
    "llGetLinkNumber": "reads current prim link number",
    "llGetMass": "returns simplified object mass from prim count",
    "llGetNumberOfPrims": "counts prims in current linkset",
    "llGetObjectMass": "returns simplified object mass from prim count",
    "llGetObjectDesc": "reads harness object description",
    "llGetObjectDetails": "supports a subset of OBJECT_* constants",
    "llGetObjectName": "returns harness object name",
    "llGetObjectPrimCount": "counts prims for a known object",
    "llGetNotecardLine": "queues dataserver event from stored notecard lines",
    "llGetNumberOfNotecardLines": "queues dataserver event with stored notecard line count",
    "llGetOwner": "returns harness owner key",
    "llGetOwnerKey": "resolves owner for known objects/agents",
    "llGetParcelDetails": "supports a subset of PARCEL_DETAILS_* constants",
    "llGetParcelMusicURL": "reads current demo parcel music URL",
    "llGetPos": "returns harness object position",
    "llGetRegionCorner": "reads demo region corner",
    "llGetRegionFPS": "reads demo region FPS",
    "llGetRegionName": "reads demo region name",
    "llGetRegionTimeDilation": "reads demo region time dilation",
    "llGetRot": "reads harness object rotation",
    "llGetScale": "reads current prim scale",
    "llGetTime": "stubbed constant",
    "llGetVel": "reads harness object velocity",
    "llHTTPRequest": "stdlib HTTP request; simplified options/headers/events",
    "llJsonGetValue": "basic JSON path lookup",
    "llKey2Name": "resolves known avatar/object names",
    "llListen": "basic chat listener registration",
    "llListenRemove": "basic listener removal",
    "llList2List": "basic and wrap slice handling only",
    "llLoopSound": "stores looping sound state and history without audio playback",
    "llMessageLinked": "queues link_message in linkset; ignores target details",
    "llOwnerSay": "prints to stdout",
    "llParticleSystem": "stores particle parameters on the current prim without rendering",
    "llPlaySound": "stores current sound state and history without audio playback",
    "llPreloadSound": "records preloaded sound names on the current prim",
    "llRegionSay": "routes through harness chat without range semantics",
    "llRegionSayTo": "routes through harness chat without private delivery semantics",
    "llRequestDisplayName": "synchronous name lookup instead of dataserver event",
    "llRequestUsername": "synchronous name lookup instead of dataserver event",
    "llResetTime": "stubbed no-op",
    "llRezAtRoot": "clones stored object inventory into the current region with a runtime cap",
    "llRezObject": "clones stored object inventory into the current region with a runtime cap",
    "llSay": "routes chat in harness or prints to stdout",
    "llSensor": "queues simplified sensor/no_sensor events from demo region entities",
    "llSensorRemove": "clears simplified repeated sensor registration",
    "llSensorRepeat": "stores and queues simplified repeated sensor scans",
    "llSetLinkPrimitiveParams": "supports a small model-backed PRIM_* subset",
    "llSetLinkPrimitiveParamsFast": "supports a small model-backed PRIM_* subset",
    "llSetObjectDesc": "writes harness object description",
    "llSetObjectName": "writes harness object name",
    "llSetParcelMusicURL": "writes current demo parcel music URL",
    "llSetPos": "sets harness object position",
    "llGetPrimitiveParams": "supports a small model-backed PRIM_* subset",
    "llSetPrimitiveParams": "supports a small model-backed PRIM_* subset",
    "llSetRot": "sets harness object rotation",
    "llSetScale": "sets current prim scale",
    "llSetText": "stores floating text state on the current prim",
    "llSetTextureAnim": "stores texture animation parameters on the current prim",
    "llSetTimerEvent": "queues timer events in tick loop",
    "llShout": "routes through harness chat without range semantics",
    "llStopSound": "clears current stored sound state",
    "llWater": "reads demo region water height",
    "llWhisper": "routes through harness chat without range semantics",
    "llWind": "reads demo region wind vector",
    "llTriggerSound": "stores triggered sound state and history without audio playback",
}

PARTIAL.update(
    {
        name: f"stub: prints not implemented and returns default {return_type}"
        for name, return_type in STUBS.items()
        if name not in IMPLEMENTED and name not in PARTIAL
    }
)

FLAG_NAMES = {
    "LSL New": "NEW",
    "LSL EXP": "X",
    "LSL I": "I",
    "LSL D": "D",
    "LSL_D": "D",
    "LSL R": "R",
    "LSL_R": "R",
    "LSL UPD": "U",
    "LSL B": "B",
    "LSL GM": "G",
    "LSL_GM": "G",
    "LSL LX": "LX",
    "LSL RQ": "RQ",
}


def fetch_raw() -> str:
    with urlopen(SOURCE_URL, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_functions(raw: str) -> list[dict[str, str]]:
    rows = []
    seen = set()
    for line in raw.splitlines():
        if "<li>" not in line:
            continue

        match = re.search(r"\[\[ll[^\]|{}]+(?:\{\{#var:lang\}\})?\|+\s*(?P<name>ll[A-Za-z0-9]+)\]\]", line)
        if not match:
            continue

        name = match.group("name")
        if name in seen:
            continue
        seen.add(name)

        flags = []
        for template, label in FLAG_NAMES.items():
            if "{{" + template + "}}" in line:
                flags.append(label)

        if name in IMPLEMENTED:
            status = "implemented"
            note = IMPLEMENTED[name]
        elif name in PARTIAL:
            status = "partial"
            note = PARTIAL[name]
        else:
            status = "missing"
            note = ""

        rows.append(
            {
                "name": name,
                "status": status,
                "wiki_flags": " ".join(flags),
                "note": note,
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]]):
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "status", "wiki_flags", "note"])
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows: list[dict[str, str]]):
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    with JSON_OUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": SOURCE_URL,
                "count": len(rows),
                "functions": rows,
            },
            f,
            indent=2,
        )
        f.write("\n")


def write_markdown(rows: list[dict[str, str]]):
    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    counts = {status: sum(1 for row in rows if row["status"] == status) for status in ("implemented", "partial", "missing")}
    lines = [
        "# LSL Function Status",
        "",
        f"Source: {SOURCE_URL}",
        "",
        f"Total functions copied: {len(rows)}",
        "",
        "| Status | Count |",
        "|---|---:|",
        f"| Implemented | {counts['implemented']} |",
        f"| Partial | {counts['partial']} |",
        f"| Missing | {counts['missing']} |",
        "",
        "Wiki flags are copied from the official template where present. Local status means:",
        "",
        "- `implemented`: usable local behavior exists for the common offline case.",
        "- `partial`: a handler exists, but behavior is stubbed, simplified, or simulator-limited.",
        "- `missing`: no local builtin handler exists yet.",
        "",
        "| Function | Local status | Wiki flags | Notes |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['name']}` | {row['status']} | {row['wiki_flags']} | {row['note']} |"
        )
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_offline_functions() -> list[dict[str, str]]:
    if not JSON_OUT.exists():
        return []
    with JSON_OUT.open("r", encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for func in data.get("functions", []):
        name = func["name"]
        wiki_flags = func.get("wiki_flags", "")
        if name in IMPLEMENTED:
            status = "implemented"
            note = IMPLEMENTED[name]
        elif name in PARTIAL:
            status = "partial"
            note = PARTIAL[name]
        else:
            status = "missing"
            note = ""
        rows.append({
            "name": name,
            "status": status,
            "wiki_flags": wiki_flags,
            "note": note
        })
    return rows


def main() -> int:
    try:
        rows = parse_functions(fetch_raw())
        print("Fetched functions online successfully.")
    except Exception as e:
        print(f"Online fetch failed ({e}), falling back to offline update using existing JSON.")
        rows = load_offline_functions()
    write_csv(rows)
    write_json(rows)
    write_markdown(rows)
    counts = {status: sum(1 for row in rows if row["status"] == status) for status in ("implemented", "partial", "missing")}
    print(
        f"Copied {len(rows)} functions: "
        f"{counts['implemented']} implemented, {counts['partial']} partial, {counts['missing']} missing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
