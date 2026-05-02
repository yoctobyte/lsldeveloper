vector start = <1.0, 2.0, 3.0>;
rotation rot = <0.0, 0.0, 0.0, 1.0>;

default {
    state_entry() {
        vector pos = llGetPos();
        pos += start;
        pos.z = pos.z + 1.0;
        llSetPos(pos);
        llOwnerSay((string)rot);
    }
}
