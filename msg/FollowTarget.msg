uint64 timestamp  # time since system start (microseconds)

uint8 publisher_id
uint64 pub_timestamp

float64 lat       # target position (deg * 1e7)
float64 lon       # target position (deg * 1e7)
float32 alt       # target position

float32 vy        # target vel in y
float32 vx        # target vel in x
float32 vz        # target vel in z

uint8 est_cap     # target reporting capabilities
