integer touches;

default {
    touch_start(integer total_number) {
        touches += total_number;
        llOwnerSay("touches=" + (string)touches);
    }
}
