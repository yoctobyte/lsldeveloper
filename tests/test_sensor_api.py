from harness.runtime import build_runtime


SCRIPT = """
string detected_name;
key detected_key;
integer detected_type;
integer detected_count;

default {
    state_entry() {
        llSensor("", NULL_KEY, AGENT, 256.0, 3.14159);
    }

    sensor(integer total_number) {
        detected_count = total_number;
        detected_name = llDetectedName(0);
        detected_key = llDetectedKey(0);
        detected_type = llDetectedType(0);
    }
}
"""


def test_sensor_finds_seeded_demo_avatar_and_exposes_detected_data():
    runtime = build_runtime(SCRIPT)
    runtime.tick()
    runtime.tick()

    globals = runtime.script.ctx.globals

    assert globals["detected_count"] >= 1
    assert globals["detected_name"] == "Offline User"
    assert globals["detected_key"] == runtime.region.avatars[globals["detected_key"]].uuid
    assert globals["detected_type"] & 1
