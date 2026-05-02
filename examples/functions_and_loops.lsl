integer sum_to(integer n) {
    integer total = 0;
    integer i;
    for (i = 0; i <= n; i++) {
        total += i;
    }
    return total;
}

default {
    state_entry() {
        integer total = sum_to(5);
        do {
            total--;
        } while (total > 10);
        llOwnerSay((string)total);
    }
}
