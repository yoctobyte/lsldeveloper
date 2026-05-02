string first_name;
key first_key;
integer first_type;

default {
    state_entry() {
        llSensor("", NULL_KEY, AGENT, 256.0, 3.14159);
    }

    sensor(integer total_number) {
        if (total_number > 0) {
            first_name = llDetectedName(0);
            first_key = llDetectedKey(0);
            first_type = llDetectedType(0);
        }
    }

    no_sensor() {
        first_name = "none";
    }
}
