uint64 timestamp # time since system start (microseconds)

uint8 publisher_id
uint64 pub_timestamp

# rpm values of 0.0 mean within a timeout there is no movement measured
float32 rpm_estimate # filtered revolutions per minute
float32 rpm_raw
