default {
    state_entry() {
        llSetText("Offline state is inspectable", <0.2, 0.7, 1.0>, 1.0);
        llParticleSystem([1, 2, "demo"]);
        llSetTextureAnim(3, -1, 4, 4, 0.0, 16.0, 6.0);
        llPreloadSound("ready");
        llPlaySound("ready", 0.4);
    }
}
