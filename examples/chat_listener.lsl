default {
    state_entry() {
        llListen(0, "", "", "");
        llSay(0, "Listening");
    }

    listen(integer channel, string name, key id, string message) {
        if (message == "ping") {
            llSay(channel, "pong " + name);
        }
    }
}
