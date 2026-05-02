default {
    state_entry() {
        list items = ["alpha", 2, 3.0];
        items = llListReplaceList(items, ["beta"], 1, 1);
        integer found = llListFindList(items, ["beta"]);
        string joined = llList2CSV(items);
        llOwnerSay((string)found + ":" + joined);
    }
}
