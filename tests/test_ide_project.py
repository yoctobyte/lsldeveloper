import json

from core.types import LSLRotation, LSLVector, NULL_KEY
from ide.project import IdeProject, ProjectObject, ProjectScript


def test_ide_project_saves_loads_and_runs_multiple_objects(tmp_path):
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "Listener",
                scripts=[
                    ProjectScript(
                        "listener.lsl",
                        """
string heard;

default {
    state_entry() {
        llListen(7, "", NULL_KEY, "");
    }

    listen(integer channel, string name, key id, string message) {
        heard = message;
        llOwnerSay(name + ":" + message);
    }
}
""",
                    )
                ],
            ),
            ProjectObject(
                "Speaker",
                scripts=[
                    ProjectScript(
                        "speaker.lsl",
                        """
default {
    state_entry() {
        llSay(7, "ping");
    }
}
""",
                    )
                ],
            ),
        ],
    )

    project.save()
    loaded = IdeProject.load(tmp_path)
    runtime = loaded.build_runtime(echo_stdout=False)
    runtime.tick()
    runtime.tick()

    listener = runtime.scripts[("Listener", "listener.lsl")]
    messages = runtime.world.console.messages

    assert listener.ctx.globals["heard"] == "ping"
    assert [message.message_type for message in messages] == ["say", "ownersay"]
    assert messages[0].channel == 7
    assert messages[0].source_name == "Speaker Root"
    assert messages[1].text == "Speaker Root:ping"


def test_ide_project_stores_scripts_as_files(tmp_path):
    project = IdeProject(
        tmp_path,
        [ProjectObject("Box", scripts=[ProjectScript("main.lsl", "default {}\n")])],
    )

    project.save()

    script_path = tmp_path / "objects" / "Box" / "scripts" / "main.lsl"
    project_data = json.loads((tmp_path / "project.json").read_text(encoding="utf-8"))

    assert script_path.read_text(encoding="utf-8") == "default {}\n"
    assert project_data["objects"][0]["scripts"] == [
        {"name": "main.lsl", "file": "objects/Box/scripts/main.lsl"}
    ]


def test_ide_project_loads_external_script_file_edits(tmp_path):
    project = IdeProject(
        tmp_path,
        [ProjectObject("Box", scripts=[ProjectScript("main.lsl", "default {}\n")])],
    )
    project.save()
    script_path = tmp_path / "objects" / "Box" / "scripts" / "main.lsl"
    script_path.write_text('default { state_entry() { llOwnerSay("external"); } }\n', encoding="utf-8")

    loaded = IdeProject.load(tmp_path)

    assert 'llOwnerSay("external")' in loaded.objects[0].scripts[0].source


def test_ide_project_auto_detects_dropped_lsl_files(tmp_path):
    (tmp_path / "loose.lsl").write_text("default {}\n", encoding="utf-8")
    nested = tmp_path / "objects" / "Console" / "scripts"
    nested.mkdir(parents=True)
    (nested / "console.lsl").write_text("default { state_entry() {} }\n", encoding="utf-8")

    loaded = IdeProject.load(tmp_path)

    scripts_by_object = {obj.name: [script.name for script in obj.scripts] for obj in loaded.objects}

    assert scripts_by_object["Object 1"] == ["loose.lsl"]
    assert scripts_by_object["Console"] == ["console.lsl"]


def test_ide_project_text_input_routes_through_avatar_chat(tmp_path):
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "Listener",
                scripts=[
                    ProjectScript(
                        "listener.lsl",
                        """
string heard;

default {
    state_entry() {
        llListen(0, "Offline Owner", NULL_KEY, "");
    }

    listen(integer channel, string name, key id, string message) {
        heard = message;
    }
}
""",
                    )
                ],
            )
        ],
    )

    runtime = project.build_runtime(echo_stdout=False)
    runtime.tick()
    runtime.say("hello")
    runtime.tick()

    script = runtime.scripts[("Listener", "listener.lsl")]
    assert script.ctx.globals["heard"] == "hello"


def test_default_ide_project_exercises_core_sim_features(tmp_path):
    project = IdeProject(tmp_path)
    project.save()
    loaded = IdeProject.load(tmp_path)

    runtime = loaded.build_runtime(echo_stdout=False)
    runtime.tick(8)

    control = runtime.scripts[("Control Panel", "control.lsl")]
    language = runtime.scripts[("Control Panel", "language_probe.lsl")]
    environment = runtime.scripts[("Control Panel", "environment_probe.lsl")]
    rez = runtime.scripts[("Control Panel", "rez_probe.lsl")]
    sensor = runtime.scripts[("Control Panel", "sensor_probe.lsl")]
    helper_object = runtime.objects["Control Panel"]
    globals_ = control.ctx.globals

    assert globals_["note_value"] == "mode=offline-demo"
    assert globals_["dataserver_pass"] == 1
    assert globals_["link_ack"] == "helper-ack"
    assert globals_["timer_seen"] == 1
    assert globals_["radar_seen"] == 1
    assert globals_["network_seen"] == 1
    assert helper_object.description == "api-probe-object"
    assert helper_object.root_prim.description == "api-probe-prim"
    assert helper_object.position == LSLVector(129.0, 129.0, 26.0)
    assert helper_object.linkset_data["mode"] == "boot"
    assert helper_object.linkset_data["helper"] == "linked"
    assert helper_object.linkset_data["api"] == "persistent"

    runtime.touch("Control Panel")
    runtime.tick()
    assert globals_["touches"] == 1
    assert runtime.world.latest_dialog["message"] == "Mode?"
    assert runtime.world.latest_dialog["buttons"] == ["Start", "Stop", "Status"]

    runtime.dialog_response("Status")
    runtime.tick()
    assert globals_["dialog_seen"] == 1

    runtime.say("ping remote")
    runtime.tick(2)
    assert globals_["inter_object_seen"] == 1

    messages = runtime.world.console.messages
    assert any(message.message_type == "dialog" for message in messages)
    assert any("dataserver pass mode=offline-demo" in message.text for message in messages)
    assert any("network 200 offline-network-ok" in message.text for message in messages)
    assert any(message.text == "remote pong" for message in messages)

    language_globals = language.ctx.globals
    assert language.current_state == "ready"
    assert language_globals["for_sum"] == 10
    assert language_globals["while_count"] == 3
    assert language_globals["do_count"] == 2
    assert language_globals["condition_score"] == 5
    assert language_globals["list_score"] == 156
    assert language_globals["explicit_int"] == 42
    assert language_globals["parsed_float"] == 3.5
    assert language_globals["parsed_vec"] == LSLVector(4.0, 5.0, 6.0)
    assert language_globals["parsed_rot"] == LSLRotation()
    assert language_globals["type_summary"] == "42|3.5|<4.000000, 5.000000, 6.000000>"
    assert language_globals["state_seen"] == 1
    assert language_globals["final_status"] == "language ok"

    environment_globals = environment.ctx.globals
    assert environment_globals["api_pass"] == 15
    assert environment_globals["api_fail"] == 0
    assert environment_globals["env_region"] == "Offline Sandbox"
    assert environment_globals["env_parcel"] == "Offline Parcel"
    assert environment_globals["inventory_scripts"] == 6
    assert environment_globals["agent_count"] >= 2
    assert environment_globals["running_scripts"] >= 4
    assert environment_globals["object_desc_seen"] == "api-probe-object"
    assert environment_globals["prim_desc_seen"] == "api-probe-prim"
    assert environment_globals["linkset_seen"] == "persistent"
    assert environment_globals["parcel_music_seen"] == "https://example.invalid/test-music"
    assert environment_globals["object_detail_name"] == "Control Panel"
    assert environment_globals["pos_seen"] == LSLVector(129.0, 129.0, 26.0)
    assert environment_globals["confirmation"] == "api pass 15 fail 0"

    runtime.say("api ping", 5)
    runtime.tick()
    assert environment_globals["io_seen"] == 1
    assert environment_globals["api_pass"] == 16
    assert environment_globals["api_fail"] == 0
    assert any("io pass Offline Owner" in message.text for message in runtime.world.console.messages)

    rez_globals = rez.ctx.globals
    child = next(obj for obj in runtime.region.objects.values() if obj.name == "Seeded Child")
    assert runtime.world.rezzed_object_count == 1
    assert rez_globals["rez_seen"] == 1
    assert rez_globals["rez_count_before"] == 1
    assert rez_globals["rez_count_after"] == 1
    assert rez_globals["child_key"] == child.uuid
    assert rez_globals["child_key"] != NULL_KEY
    assert child.description == "rezzed child active"
    assert child.position == LSLVector(131.0, 129.0, 26.0)
    assert any("rez pass " in message.text for message in runtime.world.console.messages)
    assert any(message.text == "child ready" for message in runtime.world.console.messages)

    sensor_globals = sensor.ctx.globals
    assert sensor_globals["phase"] == 4
    assert sensor_globals["agent_total"] == 2
    assert sensor_globals["object_total"] == 1
    assert sensor_globals["named_total"] == 1
    assert sensor_globals["no_sensor_seen"] == 1
    assert sensor_globals["repeat_events"] == 2
    assert sensor_globals["removed_count"] == 2
    assert sensor_globals["first_agent_name"] == "Offline Owner"
    assert sensor_globals["first_agent_key"] != NULL_KEY
    assert sensor_globals["first_agent_pos"] == LSLVector(128.0, 128.0, 25.0)
    assert sensor_globals["first_agent_type"] == 1
    assert sensor_globals["first_object_name"] == "Fixture Cube"
    assert sensor_globals["first_object_type"] & 2
    assert any("sensor pass agents 2 objects 1 repeats 2" in message.text for message in runtime.world.console.messages)


def test_world_profiles_seed_selectable_avatar_counts(tmp_path):
    expected = {
        "none": 0,
        "one": 1,
        "couple": 2,
        "dozens": 24,
        "sixty_plus": 64,
    }

    for profile, avatar_count in expected.items():
        project = IdeProject(tmp_path / profile, [ProjectObject("Probe", scripts=[])], world_profile=profile)
        project.save()
        loaded = IdeProject.load(tmp_path / profile)
        runtime = loaded.build_runtime(echo_stdout=False)

        assert loaded.world_profile == profile
        assert len(runtime.region.avatars) == avatar_count


def test_rez_limit_prevents_runaway_spawn(tmp_path):
    child_script = """
default {
    state_entry() {
        llOwnerSay("spawned");
    }
}
"""
    rezzer_script = """
integer seen;

default {
    state_entry() {
        llRezObject("Child", llGetPos(), <0.0, 0.0, 0.0>, <0.0, 0.0, 0.0, 1.0>, 1);
        llRezObject("Child", llGetPos(), <0.0, 0.0, 0.0>, <0.0, 0.0, 0.0, 1.0>, 2);
    }

    object_rez(key id) {
        seen++;
    }
}
"""
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "Rezzer",
                scripts=[ProjectScript("rezzer.lsl", rezzer_script)],
                child_objects=[ProjectObject("Child", scripts=[ProjectScript("child.lsl", child_script)])],
            )
        ],
    )

    runtime = project.build_runtime(echo_stdout=False)
    runtime.world.max_rezzed_objects = 1
    runtime.tick(2)

    script = runtime.scripts[("Rezzer", "rezzer.lsl")]
    children = [obj for obj in runtime.region.objects.values() if obj.name == "Child"]

    assert len(children) == 1
    assert runtime.world.rezzed_object_count == 1
    assert script.ctx.globals["seen"] == 1
    assert any("rez limit reached: 1" in message.text for message in runtime.world.console.messages)


def test_ide_project_collects_compile_diagnostics_and_runs_other_scripts(tmp_path):
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "Broken",
                scripts=[ProjectScript("broken.lsl", "default { state_entry() { llOwnerSay(\"oops\") } }\n")],
            ),
            ProjectObject(
                "Healthy",
                scripts=[
                    ProjectScript(
                        "healthy.lsl",
                        """
integer ran;

default {
    state_entry() {
        ran = TRUE;
    }
}
""",
                    )
                ],
            ),
        ],
    )

    runtime = project.build_runtime(echo_stdout=False)
    runtime.tick()

    broken = runtime.scripts[("Broken", "broken.lsl")]
    healthy = runtime.scripts[("Healthy", "healthy.lsl")]
    diagnostic = runtime.world.diagnostics[0]

    assert broken.running is False
    assert healthy.ctx.globals["ran"] == 1
    assert diagnostic.object_name == "Broken"
    assert diagnostic.script_name == "broken.lsl"
    assert diagnostic.phase == "compile"
    assert diagnostic.line == 1
    assert "Expected ';'" in diagnostic.message
    assert runtime.world.console.messages[0].message_type == "error"


def test_ide_project_collects_runtime_diagnostics_and_disables_bad_script(tmp_path):
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "Runtime Broken",
                scripts=[
                    ProjectScript(
                        "runtime_broken.lsl",
                        """
default {
    state_entry() {
        llFunctionThatDoesNotExist();
    }
}
""",
                    )
                ],
            )
        ],
    )

    runtime = project.build_runtime(echo_stdout=False)
    runtime.tick()

    script = runtime.scripts[("Runtime Broken", "runtime_broken.lsl")]
    diagnostic = runtime.world.diagnostics[0]

    assert script.running is False
    assert diagnostic.object_name == "Runtime Broken"
    assert diagnostic.script_name == "runtime_broken.lsl"
    assert diagnostic.phase == "runtime:state_entry"
    assert "Unknown function: llFunctionThatDoesNotExist" in diagnostic.message
