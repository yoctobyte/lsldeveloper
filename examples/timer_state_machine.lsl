integer ticks;

default {
    state_entry() {
        llSetTimerEvent(0.2);
    }

    timer() {
        ticks++;
        if (ticks >= 2) {
            state done;
        }
    }

    state_exit() {
        llOwnerSay("leaving default");
    }
}

state done {
    state_entry() {
        llSetTimerEvent(0.0);
        llOwnerSay("done");
    }
}
