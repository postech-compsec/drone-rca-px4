uint64 timestamp		# time since system start (microseconds)
uint64 timestamp_sample         # the timestamp of the raw data (microseconds)

uint8 publisher_id
uint64 pub_timestamp

float32[25] states		# Internal filter states
uint8 n_states		# Number of states effectively used

float32[24] covariances	# Diagonal Elements of Covariance Matrix
