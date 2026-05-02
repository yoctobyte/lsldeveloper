from core.types import LSLVector, NULL_KEY
from harness.runtime import build_runtime
from sim.prim import InventoryItem


INVENTORY_SCRIPT = """
integer script_count;
integer notecard_count;
string notecard_name;
integer notecard_type;
key notecard_key;
string notecard_desc;
key creator;
integer perm_mask;

default {
    state_entry() {
        script_count = llGetInventoryNumber(INVENTORY_SCRIPT);
        notecard_count = llGetInventoryNumber(INVENTORY_NOTECARD);
        notecard_name = llGetInventoryName(INVENTORY_NOTECARD, 0);
        notecard_type = llGetInventoryType("Config");
        notecard_key = llGetInventoryKey("Config");
        notecard_desc = llGetInventoryDesc("Config");
        creator = llGetInventoryCreator("Config");
        perm_mask = llGetInventoryPermMask("Config", MASK_OWNER);
    }
}
"""


PRIMITIVE_SCRIPT = """
string prim_name;
string prim_desc;
vector prim_size;
string link_name;
integer prim_count;
integer object_prim_count;
float mass;

default {
    state_entry() {
        llSetPrimitiveParams([PRIM_NAME, "Probe Prim", PRIM_DESC, "Root prim", PRIM_SIZE, <1.0, 2.0, 3.0>]);
        list params = llGetPrimitiveParams([PRIM_NAME, PRIM_DESC, PRIM_SIZE]);
        prim_name = llList2String(params, 0);
        prim_desc = llList2String(params, 1);
        prim_size = llList2Vector(params, 2);

        llSetLinkPrimitiveParamsFast(LINK_THIS, [PRIM_NAME, "Linked Probe"]);
        list link_params = llGetLinkPrimitiveParams(LINK_THIS, [PRIM_NAME]);
        link_name = llList2String(link_params, 0);

        prim_count = llGetNumberOfPrims();
        object_prim_count = llGetObjectPrimCount(llGetKey());
        mass = llGetMass();
    }
}
"""


def test_inventory_queries_read_current_prim_inventory():
    runtime = build_runtime(INVENTORY_SCRIPT)
    notecard = InventoryItem("Config", 7)
    notecard.description = "Demo config"
    notecard.creator_key = runtime.avatar.uuid
    notecard.perm_mask = 1234
    runtime.prim.add_item(notecard)

    runtime.tick()
    globals = runtime.script.ctx.globals

    assert globals["script_count"] == 1
    assert globals["notecard_count"] == 1
    assert globals["notecard_name"] == "Config"
    assert globals["notecard_type"] == 7
    assert globals["notecard_key"] == notecard.uuid
    assert globals["notecard_desc"] == "Demo config"
    assert globals["creator"] == runtime.avatar.uuid
    assert globals["perm_mask"] == 1234
    assert globals["notecard_key"] != NULL_KEY


def test_primitive_params_and_simple_object_mass_are_model_backed():
    runtime = build_runtime(PRIMITIVE_SCRIPT)
    runtime.tick()
    globals = runtime.script.ctx.globals

    assert globals["prim_name"] == "Probe Prim"
    assert globals["prim_desc"] == "Root prim"
    assert globals["prim_size"] == LSLVector(1.0, 2.0, 3.0)
    assert globals["link_name"] == "Linked Probe"
    assert globals["prim_count"] == 1
    assert globals["object_prim_count"] == 1
    assert globals["mass"] == 1.0
