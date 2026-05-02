from harness.runtime import build_runtime


SCRIPT = """
default {
    state_entry() {
        llSetText("Ready", <0.25, 0.5, 1.0>, 0.75);
        llParticleSystem([1, 2, "burst"]);
        llSetTextureAnim(3, -1, 4, 4, 0.0, 16.0, 8.0);
        llPreloadSound("ding");
        llPlaySound("ding", 0.5);
        llLoopSound("hum", 0.2);
        llTriggerSound("click", 1.0);
        llStopSound();
    }
}
"""


def test_visual_and_sound_apis_store_prim_state():
    runtime = build_runtime(SCRIPT)
    runtime.tick()

    assert runtime.prim.floating_text["text"] == "Ready"
    assert runtime.prim.floating_text["color"].z == 1.0
    assert runtime.prim.floating_text["alpha"] == 0.75
    assert runtime.prim.particle_system == [1, 2, "burst"]
    assert runtime.prim.texture_animation == {
        "mode": 3,
        "face": -1,
        "size_x": 4,
        "size_y": 4,
        "start": 0.0,
        "length": 16.0,
        "rate": 8.0,
    }
    assert runtime.prim.preloaded_sounds == {"ding"}
    assert [entry["mode"] for entry in runtime.prim.sound_history] == ["play", "loop", "trigger"]
    assert runtime.prim.sound_state["mode"] == "stopped"
