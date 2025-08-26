uint64 timestamp			# time since system start (microseconds)

uint8 publisher_id
uint64 pub_timestamp

# Two wheels: 0 right, 1 left
float32[2] wheel_speed # [rad/s]
float32[2] wheel_angle # [rad]
