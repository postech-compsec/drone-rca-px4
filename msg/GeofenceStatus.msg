uint64 timestamp                        # time since system start (microseconds)

uint8 publisher_id
uint64 pub_timestamp

uint32 geofence_id 			# loaded geofence id
uint8 status 				# Current geofence status

uint8 GF_STATUS_LOADING = 0
uint8 GF_STATUS_READY = 1
