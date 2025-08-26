uint64 timestamp		# time since system start (microseconds)

uint8 publisher_id
uint64 pub_timestamp

char[127] text
uint8 severity # log level (same as in the linux kernel, starting with 0)

uint8 ORB_QUEUE_LENGTH = 8
