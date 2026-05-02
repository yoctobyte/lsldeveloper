from harness.runtime import build_runtime


SCRIPT = """
string region_name;
string parcel_name;
string object_name;
string object_desc;
integer agent_count;
vector region_corner;

default {
    state_entry() {
        llSetObjectName("Probe");
        llSetObjectDesc("Probe object");
        region_name = llGetRegionName();
        region_corner = llGetRegionCorner();

        list parcel = llGetParcelDetails(llGetPos(), [PARCEL_DETAILS_NAME]);
        parcel_name = llList2String(parcel, 0);

        list details = llGetObjectDetails(llGetKey(), [OBJECT_NAME, OBJECT_DESC]);
        object_name = llList2String(details, 0);
        object_desc = llList2String(details, 1);

        agent_count = llGetListLength(llGetAgentList(AGENT_LIST_REGION, []));
        llSetParcelMusicURL("https://example.invalid/new-stream");
    }
}
"""


def test_demo_world_prefill_and_model_backed_apis():
    runtime = build_runtime(SCRIPT)
    runtime.tick()

    globals = runtime.script.ctx.globals

    assert globals["region_name"] == "Offline Sandbox"
    assert globals["parcel_name"] == "Offline Parcel"
    assert globals["object_name"] == "Probe"
    assert globals["object_desc"] == "Probe object"
    assert globals["agent_count"] >= 2
    assert globals["region_corner"].x == 1000.0
    assert runtime.region.default_parcel.music_url == "https://example.invalid/new-stream"
