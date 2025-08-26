uint64 timestamp # time since system start (microseconds)

uint8 publisher_id
uint64 pub_timestamp

int8 GEAR_UP = 1 # landing gear up
int8 GEAR_DOWN = -1 # landing gear down
int8 GEAR_KEEP = 0 # keep the current state

int8 landing_gear
