from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.types import LSLVector
from events.loop import SimulationLoop
from events.queue import LSLEvent
from harness.runtime import initialize_script
from sim.avatar import Avatar
from sim.demo import seed_demo_world
from sim.diagnostics import diagnostic_from_exception
from sim.object import LSLObject
from sim.prim import NotecardItem, ObjectInventoryItem, Prim, ScriptItem
from sim.world import World


DEFAULT_SCRIPT = """default {
    state_entry() {
        llOwnerSay("ready");
    }
}
"""

CONTROL_SCRIPT = """integer touches;
integer timer_seen;
integer radar_seen;
integer network_seen;
integer dialog_seen;
integer inter_object_seen;
integer dataserver_pass;
string note_value;
string link_ack;
key note_request;

default {
    state_entry() {
        llListen(0, "", NULL_KEY, "");
        llListen(-9000, "", NULL_KEY, "");
        llSetObjectDesc("storage:object");
        llSetPrimitiveParams([PRIM_DESC, "storage:prim"]);
        llLinksetDataWrite("mode", "boot");
        note_request = llGetNotecardLine("Config", 0);
        llMessageLinked(LINK_SET, 100, "within-object", "");
        llSetTimerEvent(0.2);
        llSensorRepeat("", NULL_KEY, AGENT | ACTIVE | PASSIVE | SCRIPTED, 96.0, 3.14, 0.2);
        llHTTPRequest("data:text/plain,offline-network-ok", [], "");
        llOwnerSay("control ready");
    }

    touch_start(integer total_number) {
        touches += total_number;
        llOwnerSay("touch " + (string)touches);
        llDialog(llGetOwner(), "Mode?", ["Start", "Stop", "Status"], -9000);
    }

    listen(integer channel, string name, key id, string message) {
        if (channel == -9000) {
            dialog_seen = TRUE;
            llOwnerSay("dialog " + message);
        }
        if (channel == 0 && message == "remote pong") {
            inter_object_seen = TRUE;
            llOwnerSay("remote reply");
        }
    }

    link_message(integer sender_num, integer num, string message, key id) {
        link_ack = message;
        llOwnerSay("link " + message);
    }

    dataserver(key queryid, string data) {
        if (queryid == note_request) {
            note_value = data;
            if (data == "mode=offline-demo") {
                dataserver_pass = TRUE;
                llOwnerSay("dataserver pass " + data);
            } else {
                llOwnerSay("dataserver fail " + data);
            }
        }
    }

    timer() {
        timer_seen = TRUE;
        llSetTimerEvent(0.0);
        llOwnerSay("timer");
    }

    sensor(integer total_number) {
        radar_seen = TRUE;
        llSensorRemove();
        llOwnerSay("radar " + llDetectedName(0));
    }

    http_response(key request_id, integer status, list metadata, string body) {
        network_seen = TRUE;
        llOwnerSay("network " + (string)status + " " + body);
    }
}
"""

ENVIRONMENT_PROBE_SCRIPT = """integer api_pass;
integer api_fail;
integer io_seen;
integer inventory_scripts;
integer agent_count;
integer running_scripts;
string env_region;
string env_parcel;
string object_desc_seen;
string prim_desc_seen;
string linkset_seen;
string parcel_music_seen;
string object_detail_name;
vector pos_seen;
string confirmation;

record(integer ok) {
    if (ok) {
        api_pass++;
    } else {
        api_fail++;
    }
}

default {
    state_entry() {
        llListen(5, "", NULL_KEY, "api ping");

        env_region = llGetRegionName();
        record(env_region == "Offline Sandbox");

        list parcel = llGetParcelDetails(llGetPos(), [PARCEL_DETAILS_NAME, PARCEL_DETAILS_AREA]);
        env_parcel = llList2String(parcel, 0);
        record(env_parcel == "Offline Parcel");
        record(llList2Integer(parcel, 1) == 65536);

        list agents = llGetAgentList(AGENT_LIST_REGION, []);
        agent_count = llGetListLength(agents);
        record(agent_count >= 2);

        inventory_scripts = llGetInventoryNumber(INVENTORY_SCRIPT);
        record(inventory_scripts >= 4);
        record(llGetInventoryType("Config") == INVENTORY_NOTECARD);

        llSetObjectDesc("api-probe-object");
        object_desc_seen = llGetObjectDesc();
        record(object_desc_seen == "api-probe-object");

        llSetPrimitiveParams([PRIM_DESC, "api-probe-prim", PRIM_SIZE, <1.0, 1.5, 2.0>]);
        list prim = llGetPrimitiveParams([PRIM_DESC, PRIM_SIZE]);
        prim_desc_seen = llList2String(prim, 0);
        record(prim_desc_seen == "api-probe-prim");
        record(llList2Vector(prim, 1) == <1.0, 1.5, 2.0>);

        llLinksetDataWrite("api", "persistent");
        linkset_seen = llLinksetDataRead("api");
        record(linkset_seen == "persistent");

        llSetParcelMusicURL("https://example.invalid/test-music");
        parcel_music_seen = llGetParcelMusicURL();
        record(parcel_music_seen == "https://example.invalid/test-music");

        llSetPos(<129.0, 129.0, 26.0>);
        pos_seen = llGetPos();
        record(pos_seen == <129.0, 129.0, 26.0>);

        list details = llGetObjectDetails(llGetKey(), [OBJECT_NAME, OBJECT_DESC, OBJECT_RUNNING_SCRIPT_COUNT]);
        object_detail_name = llList2String(details, 0);
        running_scripts = llList2Integer(details, 2);
        record(object_detail_name == "Control Panel");
        record(llList2String(details, 1) == "api-probe-object");
        record(running_scripts >= 4);

        confirmation = "api pass " + (string)api_pass + " fail " + (string)api_fail;
        llOwnerSay(confirmation);
    }

    listen(integer channel, string name, key id, string message) {
        io_seen = TRUE;
        record(message == "api ping");
        confirmation = "api pass " + (string)api_pass + " fail " + (string)api_fail;
        llOwnerSay("io pass " + name);
    }
}
"""

REZ_PROBE_SCRIPT = """integer rez_seen;
integer rez_count_before;
integer rez_count_after;
key child_key;

default {
    state_entry() {
        rez_count_before = llGetInventoryNumber(INVENTORY_OBJECT);
        llRezObject("Seeded Child", llGetPos() + <2.0, 0.0, 0.0>, <0.0, 0.0, 0.0>, <0.0, 0.0, 0.0, 1.0>, 7);
    }

    object_rez(key id) {
        rez_seen = TRUE;
        child_key = id;
        rez_count_after = llGetInventoryNumber(INVENTORY_OBJECT);
        llOwnerSay("rez pass " + (string)id);
    }
}
"""

SENSOR_PROBE_SCRIPT = """integer phase;
integer agent_total;
integer object_total;
integer named_total;
integer no_sensor_seen;
integer repeat_events;
integer removed_count;
string first_agent_name;
key first_agent_key;
vector first_agent_pos;
integer first_agent_type;
string first_object_name;
integer first_object_type;

default {
    state_entry() {
        llSensor("", NULL_KEY, AGENT, 96.0, 3.14);
    }

    sensor(integer total_number) {
        if (phase == 0) {
            agent_total = total_number;
            first_agent_name = llDetectedName(0);
            first_agent_key = llDetectedKey(0);
            first_agent_pos = llDetectedPos(0);
            first_agent_type = llDetectedType(0);
            phase = 1;
            llSensor("Fixture Cube", NULL_KEY, ACTIVE | PASSIVE | SCRIPTED, 96.0, 3.14);
        } else if (phase == 1) {
            object_total = total_number;
            first_object_name = llDetectedName(0);
            first_object_type = llDetectedType(0);
            phase = 2;
            llSensor("External Visitor", NULL_KEY, AGENT, 96.0, 3.14);
        } else if (phase == 2) {
            named_total = total_number;
            phase = 3;
            llSensor("Nobody Here", NULL_KEY, AGENT, 5.0, 3.14);
        } else if (phase == 4) {
            repeat_events++;
            if (repeat_events >= 2) {
                llSensorRemove();
                removed_count = repeat_events;
                llOwnerSay("sensor pass agents " + (string)agent_total + " objects " + (string)object_total + " repeats " + (string)repeat_events);
            }
        }
    }

    no_sensor() {
        if (phase == 3) {
            no_sensor_seen = TRUE;
            phase = 4;
            llSensorRepeat("", NULL_KEY, AGENT, 96.0, 3.14, 0.2);
        }
    }
}
"""

CHILD_OBJECT_SCRIPT = """default {
    state_entry() {
        llSetObjectDesc("rezzed child active");
        llOwnerSay("child ready");
    }
}
"""

HELPER_SCRIPT = """default {
    link_message(integer sender_num, integer num, string message, key id) {
        if (message == "within-object") {
            llLinksetDataWrite("helper", "linked");
            llMessageLinked(LINK_SET, 101, "helper-ack", "");
        }
    }
}
"""

LANGUAGE_PROBE_SCRIPT = """integer for_sum;
integer while_count;
integer do_count;
integer condition_score;
integer state_seen;
integer list_score;
integer explicit_int;
float parsed_float;
vector parsed_vec;
rotation parsed_rot;
string type_summary;
string final_status;
list global_list;

integer add(integer left, integer right) {
    return left + right;
}

default {
    state_entry() {
        integer i;
        for (i = 0; i < 5; i++) {
            for_sum += i;
        }

        while (while_count < 3) {
            while_count++;
        }

        do {
            do_count++;
        } while (do_count < 2);

        if (for_sum == 10 && while_count == 3) {
            condition_score += add(1, 1);
        } else {
            condition_score = -100;
        }

        if (FALSE || do_count == 2) {
            condition_score += 3;
        }

        list local_list = ["alpha", 7, 2.5, <1.0, 2.0, 3.0>, <0.0, 0.0, 0.0, 1.0>];
        global_list = local_list + ["omega"];
        list_score = llGetListLength(global_list);
        if (llList2String(global_list, 0) == "alpha") {
            list_score += 10;
        }
        if (llList2Integer(global_list, 1) == 7) {
            list_score += 20;
        }
        if (llList2Float(global_list, 2) == 2.5) {
            list_score += 30;
        }
        if (llList2Vector(global_list, 3) == <1.0, 2.0, 3.0>) {
            list_score += 40;
        }
        if (llList2Rot(global_list, 4) == <0.0, 0.0, 0.0, 1.0>) {
            list_score += 50;
        }

        explicit_int = (integer)"42.9";
        parsed_float = (float)"3.5";
        parsed_vec = (vector)"<4.0, 5.0, 6.0>";
        parsed_rot = (rotation)"<0.0, 0.0, 0.0, 1.0>";
        type_summary = (string)explicit_int + "|" + (string)parsed_float + "|" + (string)parsed_vec;

        state ready;
    }
}

state ready {
    state_entry() {
        state_seen = TRUE;
        final_status = "language ok";
        llOwnerSay(final_status);
    }
}
"""

REMOTE_RELAY_SCRIPT = """default {
    state_entry() {
        llListen(0, "", NULL_KEY, "ping remote");
        llOwnerSay("relay ready");
    }

    listen(integer channel, string name, key id, string message) {
        llSay(0, "remote pong");
    }
}
"""


@dataclass
class ProjectScript:
    name: str
    source: str = DEFAULT_SCRIPT

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectScript":
        return cls(name=str(data.get("name", "script.lsl")), source=str(data.get("source", DEFAULT_SCRIPT)))

    def to_dict(self) -> dict:
        return {"name": self.name, "source": self.source}


@dataclass
class ProjectNotecard:
    name: str
    text: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectNotecard":
        return cls(name=str(data.get("name", "Config")), text=str(data.get("text", "")))

    def to_dict(self) -> dict:
        return {"name": self.name, "text": self.text}


@dataclass
class ProjectObject:
    name: str
    description: str = ""
    position: LSLVector = field(default_factory=lambda: LSLVector(128.0, 128.0, 25.0))
    scripts: list[ProjectScript] = field(default_factory=list)
    notecards: list[ProjectNotecard] = field(default_factory=list)
    child_objects: list["ProjectObject"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectObject":
        pos = data.get("position") or [128.0, 128.0, 25.0]
        return cls(
            name=str(data.get("name", "Object")),
            description=str(data.get("description", "")),
            position=LSLVector(float(pos[0]), float(pos[1]), float(pos[2])),
            scripts=[ProjectScript.from_dict(item) for item in data.get("scripts", [])],
            notecards=[ProjectNotecard.from_dict(item) for item in data.get("notecards", [])],
            child_objects=[ProjectObject.from_dict(item) for item in data.get("child_objects", [])],
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "position": [self.position.x, self.position.y, self.position.z],
            "scripts": [script.to_dict() for script in self.scripts],
            "notecards": [notecard.to_dict() for notecard in self.notecards],
            "child_objects": [obj.to_dict() for obj in self.child_objects],
        }


@dataclass
class ProjectRuntime:
    world: World
    region: object
    loop: SimulationLoop
    avatar: Avatar
    objects: dict[str, LSLObject]
    scripts: dict[tuple[str, str], ScriptItem]

    def tick(self, count: int = 1, dt: float = 0.1):
        for _ in range(count):
            self.loop.tick(dt)

    def say(self, text: str, channel: int = 0):
        self.avatar.say(channel, text)

    def dialog_response(self, button: str):
        dialog = getattr(self.world, "latest_dialog", None)
        if dialog:
            self.say(button, int(dialog["channel"]))

    def touch(self, object_name: str, link_num: int = 0):
        obj = self.objects.get(object_name)
        if obj:
            self.avatar.touch(obj.uuid, link_num)


class IdeProject:
    def __init__(self, folder: Path, objects: Optional[list[ProjectObject]] = None, world_profile: str = "couple"):
        self.folder = Path(folder)
        self.world_profile = world_profile
        self.objects = objects or [
            ProjectObject(
                "Control Panel",
                scripts=[
                    ProjectScript("control.lsl", CONTROL_SCRIPT),
                    ProjectScript("helper.lsl", HELPER_SCRIPT),
                    ProjectScript("language_probe.lsl", LANGUAGE_PROBE_SCRIPT),
                    ProjectScript("environment_probe.lsl", ENVIRONMENT_PROBE_SCRIPT),
                    ProjectScript("rez_probe.lsl", REZ_PROBE_SCRIPT),
                    ProjectScript("sensor_probe.lsl", SENSOR_PROBE_SCRIPT),
                ],
                notecards=[ProjectNotecard("Config", "mode=offline-demo\nnetwork=data-url\n")],
                child_objects=[
                    ProjectObject(
                        "Seeded Child",
                        description="Inventory object used by llRezObject tests",
                        scripts=[ProjectScript("child.lsl", CHILD_OBJECT_SCRIPT)],
                    )
                ],
            ),
            ProjectObject(
                "Remote Relay",
                position=LSLVector(132.0, 128.0, 25.0),
                scripts=[ProjectScript("relay.lsl", REMOTE_RELAY_SCRIPT)],
            ),
        ]

    @property
    def path(self) -> Path:
        return self.folder / "project.json"

    @classmethod
    def load(cls, folder: str | Path) -> "IdeProject":
        folder = Path(folder)
        path = folder / "project.json"
        if not path.exists():
            return cls(folder)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            folder,
            [ProjectObject.from_dict(item) for item in data.get("objects", [])],
            world_profile=str(data.get("world_profile", "couple")),
        )

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        data = {"world_profile": self.world_profile, "objects": [obj.to_dict() for obj in self.objects]}
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_object(self, name: Optional[str] = None) -> ProjectObject:
        existing = {obj.name for obj in self.objects}
        index = len(self.objects) + 1
        name = name or f"Object {index}"
        while name in existing:
            index += 1
            name = f"Object {index}"
        obj = ProjectObject(name, scripts=[ProjectScript("main.lsl")])
        self.objects.append(obj)
        return obj

    def add_script(self, object_index: int, name: Optional[str] = None) -> ProjectScript:
        obj = self.objects[object_index]
        existing = {script.name for script in obj.scripts}
        index = len(obj.scripts) + 1
        name = name or f"script{index}.lsl"
        while name in existing:
            index += 1
            name = f"script{index}.lsl"
        script = ProjectScript(name)
        obj.scripts.append(script)
        return script

    def build_runtime(self, *, echo_stdout: bool = True) -> ProjectRuntime:
        world = World()
        seeded = seed_demo_world(world, self.world_profile)
        world.console.echo_stdout = echo_stdout
        region = seeded["region"]
        avatar = seeded["owner"]
        objects = {}
        scripts = {}

        for project_object in self.objects:
            obj = LSLObject(
                project_object.name,
                project_object.position,
                description=project_object.description,
                owner_key=avatar.uuid,
                creator_key=avatar.uuid,
            )
            prim = Prim(f"{project_object.name} Root")
            obj.add_prim(prim)
            region.add_object(obj)
            objects[project_object.name] = obj

            for project_notecard in project_object.notecards:
                prim.add_item(NotecardItem(project_notecard.name, project_notecard.text))

            for child_object in project_object.child_objects:
                prim.add_item(ObjectInventoryItem(child_object.name, child_object.to_dict()))

            for project_script in project_object.scripts:
                item = ScriptItem(project_script.name, project_script.source)
                prim.add_item(item)
                try:
                    initialize_script(item)
                except Exception as exc:
                    item.running = False
                    world.add_diagnostic(
                        diagnostic_from_exception(
                            exc,
                            phase="compile",
                            object_name=project_object.name,
                            script_name=project_script.name,
                        )
                    )
                scripts[(project_object.name, project_script.name)] = item

        return ProjectRuntime(world, region, SimulationLoop(world), avatar, objects, scripts)

    def queue_state_entries(self, runtime: ProjectRuntime):
        for script in runtime.scripts.values():
            script.event_queue.push(LSLEvent("state_entry", []))
