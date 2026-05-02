string inventory_name;
integer inventory_count;
string prim_name;
vector prim_size;

default {
    state_entry() {
        inventory_count = llGetInventoryNumber(INVENTORY_SCRIPT);
        inventory_name = llGetInventoryName(INVENTORY_SCRIPT, 0);

        llSetPrimitiveParams([PRIM_NAME, "Harness Probe", PRIM_SIZE, <1.0, 1.0, 0.25>]);
        list params = llGetPrimitiveParams([PRIM_NAME, PRIM_SIZE]);
        prim_name = llList2String(params, 0);
        prim_size = llList2Vector(params, 1);
    }
}
