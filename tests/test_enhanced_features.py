import json
import pytest
from core.types import LSLVector
from ide.project import IdeProject, ProjectObject, ProjectScript, ProjectNotecard

# Test LSL source for verifying sides count
SIDES_SCRIPT_ROOT = """
integer root_sides;

default {
    state_entry() {
        root_sides = llGetNumberOfSides();
    }
}
"""

SIDES_SCRIPT_CHILD = """
integer child_sides;

default {
    state_entry() {
        child_sides = llGetNumberOfSides();
    }
}
"""

# Test LSL source for verifying advanced touch parameters
TOUCH_DETECT_SCRIPT = """
integer link_num;
integer touch_face;
vector touch_uv;

default {
    touch_start(integer total) {
        link_num = llDetectedLinkNumber(0);
        touch_face = llDetectedTouchFace(0);
        touch_uv = llDetectedTouchUV(0);
    }
}
"""

def test_ll_get_number_of_sides_and_linked_prims(tmp_path):
    # Setup project with custom root faces and child prims having custom face counts
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "MultiFaceObject",
                num_faces=8,
                linked_prims=[
                    {"name": "Child 1", "num_faces": 4},
                    {"name": "Child 2", "num_faces": 12},
                ],
                scripts=[
                    ProjectScript("root.lsl", SIDES_SCRIPT_ROOT),
                    # In our simulation, all scripts are associated with the prim inventory.
                    # Currently, scripts defined under obj.scripts are compiled in the root prim or prims
                    # based on how build_runtime instantiates them. Let's make sure it handles child prims inventory
                    # or registers scripts correctly.
                ],
            )
        ],
    )

    project.save()
    loaded = IdeProject.load(tmp_path)
    runtime = loaded.build_runtime(echo_stdout=False)
    runtime.tick()

    # Let's verify root prim face count
    obj = runtime.objects["MultiFaceObject"]
    assert obj.prims[0].num_faces == 8
    assert obj.prims[1].num_faces == 4
    assert obj.prims[2].num_faces == 12

    script = runtime.scripts[("MultiFaceObject", "root.lsl")]
    assert script.ctx.globals["root_sides"] == 8

def test_advanced_touch_parameters(tmp_path):
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "TouchObject",
                num_faces=6,
                linked_prims=[
                    {"name": "Link 2", "num_faces": 8},
                ],
                scripts=[
                    ProjectScript("touch_detect.lsl", TOUCH_DETECT_SCRIPT)
                ],
            )
        ],
    )

    runtime = project.build_runtime(echo_stdout=False)
    runtime.tick()

    # Perform advanced touch targeting Child Link 2 (link_num=2), face=5, UV = <0.25, 0.75, 0.0>
    runtime.touch("TouchObject", link_num=2, face=5, uv=LSLVector(0.25, 0.75, 0.0))
    runtime.tick()

    script = runtime.scripts[("TouchObject", "touch_detect.lsl")]
    assert script.ctx.globals["link_num"] == 2
    assert script.ctx.globals["touch_face"] == 5
    assert script.ctx.globals["touch_uv"] == LSLVector(0.25, 0.75, 0.0)

def test_notecard_serialization_and_sync(tmp_path):
    # Setup project with a script and a notecard
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "ObjectWithNotecard",
                scripts=[
                    ProjectScript("main.lsl", "default {}")
                ],
                notecards=[
                    ProjectNotecard("Config.nc", "key=value\nlimit=100\n")
                ]
            )
        ]
    )

    # 1. Save and verify files are created on disk under the correct directories
    project.save()

    notecard_file_path = tmp_path / "objects" / "ObjectWithNotecard" / "notecards" / "Config.nc"
    assert notecard_file_path.exists()
    assert notecard_file_path.read_text(encoding="utf-8") == "key=value\nlimit=100\n"

    # Verify project.json contains reference to the notecard file
    project_json_path = tmp_path / "project.json"
    project_data = json.loads(project_json_path.read_text(encoding="utf-8"))
    obj_data = project_data["objects"][0]
    assert "notecards" in obj_data
    assert obj_data["notecards"][0]["name"] == "Config.nc"
    assert obj_data["notecards"][0]["file"] == "objects/ObjectWithNotecard/notecards/Config.nc"

    # 2. Modify the file on disk and verify loading syncs it back
    notecard_file_path.write_text("key=new_value\nlimit=200\n", encoding="utf-8")
    loaded = IdeProject.load(tmp_path)

    assert len(loaded.objects[0].notecards) == 1
    assert loaded.objects[0].notecards[0].name == "Config.nc"
    assert loaded.objects[0].notecards[0].text == "key=new_value\nlimit=200\n"
