default {
    state_entry() {
        llLinksetDataWrite("mode", "offline");
        string mode = llLinksetDataRead("mode");
        llOwnerSay(mode);
        llLinksetDataDelete("mode");
    }
}
