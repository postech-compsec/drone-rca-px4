# Rover Attitude Setpoint

uint8 publisher_id
uint64 pub_timestamp

uint64 timestamp # [us] Time since system start
float32 yaw_setpoint # [rad] [@range -inf, inf] [@frame NED] Yaw setpoint
