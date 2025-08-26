# Velocity and yaw rate limits for a multicopter position slow mode only

uint8 publisher_id
uint64 pub_timestamp

uint64 timestamp # time since system start (microseconds)

# absolute speeds, NAN means use default limit
float32 horizontal_velocity # [m/s]
float32 vertical_velocity # [m/s]
float32 yaw_rate # [rad/s]
