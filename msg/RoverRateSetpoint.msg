# Rover Rate setpoint

uint8 publisher_id
uint64 pub_timestamp

uint64 timestamp # [us] Time since system start
float32 yaw_rate_setpoint # [rad/s] [@range -inf, inf] [@frame NED] Yaw rate setpoint
