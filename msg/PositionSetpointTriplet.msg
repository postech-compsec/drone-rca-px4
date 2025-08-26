# Global position setpoint triplet in WGS84 coordinates.
# This are the three next waypoints (or just the next two or one).

uint8 publisher_id
uint64 pub_timestamp

uint64 timestamp		# time since system start (microseconds)

PositionSetpoint previous
PositionSetpoint current
PositionSetpoint next
