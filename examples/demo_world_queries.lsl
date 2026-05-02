default {
    state_entry() {
        llSetObjectName("Probe");
        llSetObjectDesc("Object used for offline world queries");

        list object_details = llGetObjectDetails(llGetKey(), [OBJECT_NAME, OBJECT_DESC, OBJECT_POS]);
        list parcel_details = llGetParcelDetails(llGetPos(), [PARCEL_DETAILS_NAME, PARCEL_DETAILS_AREA]);
        list agents = llGetAgentList(AGENT_LIST_REGION, []);

        llOwnerSay(
            llList2String(object_details, 0)
            + " in "
            + llGetRegionName()
            + " / "
            + llList2String(parcel_details, 0)
            + " agents="
            + (string)llGetListLength(agents)
        );
    }
}
