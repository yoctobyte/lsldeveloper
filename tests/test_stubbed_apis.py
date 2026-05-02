from core.types import LSLRotation, LSLVector, NULL_KEY
from harness.runtime import build_runtime


SCRIPT = """
integer permissions;
key permissions_key;
key notecard_request;
vector ground_normal;
rotation root_rotation;
list animations;
string timestamp;

default {
    state_entry() {
        llTeleportAgent(NULL_KEY, "", <128.0, 128.0, 25.0>, <0.0, 0.0, 0.0>);
        permissions = llGetPermissions();
        permissions_key = llGetPermissionsKey();
        notecard_request = llGetInventoryKey("Config");
        ground_normal = llGroundNormal(<0.0, 0.0, 0.0>);
        root_rotation = llGetRootRotation();
        animations = llGetAnimationList(NULL_KEY);
        timestamp = llGetTimestamp();
    }
}
"""


def test_stubbed_apis_warn_and_return_typed_defaults(capsys):
    runtime = build_runtime(SCRIPT)
    runtime.tick()

    globals = runtime.script.ctx.globals
    out = capsys.readouterr().out

    assert "STUB llTeleportAgent: not implemented; returning default void" in out
    assert "STUB llGetPermissions: not implemented; returning default integer" in out
    assert globals["permissions"] == 0
    assert globals["permissions_key"] == NULL_KEY
    assert globals["notecard_request"] == NULL_KEY
    assert globals["ground_normal"] == LSLVector()
    assert globals["root_rotation"] == LSLRotation()
    assert globals["animations"] == []
    assert globals["timestamp"] == ""
