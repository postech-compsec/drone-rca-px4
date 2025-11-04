#pragma once
#include <iomanip>
#include <sstream>
#include <string>
using namespace std;

namespace plan {

// Per SimpleItem spec: type, AMSLAltAboveTerrain, Altitude, AltitudeMode, autoContinue,
// command (MAV_CMD), doJumpId, frame (MAV_FRAME), params[] (p1..p4,x,y,z). :contentReference[oaicite:13]{index=13}
static string simple_item_common_head(int doJumpId, double altRel){
  ostringstream ss;
  ss << "    {\n";
  ss << "      \"AMSLAltAboveTerrain\": null,\n";
  ss << "      \"Altitude\": " << fixed << setprecision(3) << altRel << ",\n";
  ss << "      \"AltitudeMode\": 0,\n"; // 0=Relative altitude
  ss << "      \"autoContinue\": true,\n";
  ss << "      \"doJumpId\": " << doJumpId << ",\n";
  ss << "      \"frame\": 3,\n";        // MAV_FRAME_GLOBAL_RELATIVE_ALT
  return ss.str();
}

std::string make_simple_takeoff(std::mt19937&, int doJumpId, double lat, double lon, double relAlt){
  // MAV_CMD_NAV_TAKEOFF = 22; params: pitch, empty, empty, yaw, lat, lon, alt
  ostringstream ss; ss << simple_item_common_head(doJumpId, relAlt);
  ss << "      \"command\": 22,\n";
  ss << "      \"params\": [15, 0, 0, null, " << setprecision(10) << lat << ", " << lon << ", " << fixed << setprecision(3) << relAlt << "],\n";
  ss << "      \"type\": \"SimpleItem\"\n";
  ss << "    }";
  return ss.str();
}

std::string make_simple_waypoint(std::mt19937&, int doJumpId, double lat, double lon, double relAlt){
  // MAV_CMD_NAV_WAYPOINT = 16; params: hold, acceptRadius, passRadius, yaw, lat, lon, alt
  ostringstream ss; ss << simple_item_common_head(doJumpId, relAlt);
  ss << "      \"command\": 16,\n";
  ss << "      \"params\": [0, 5, 0, null, " << setprecision(10) << lat << ", " << lon << ", " << fixed << setprecision(3) << relAlt << "],\n";
  ss << "      \"type\": \"SimpleItem\"\n";
  ss << "    }";
  return ss.str();
}

std::string make_simple_loiter_time(std::mt19937& rng, int doJumpId, double lat, double lon, double relAlt){
  // MAV_CMD_NAV_LOITER_TIME = 19; params: time, empty, empty, yaw, lat, lon, alt
  double t = std::uniform_real_distribution<double>(10,45)(rng);
  ostringstream ss; ss << simple_item_common_head(doJumpId, relAlt);
  ss << "      \"command\": 19,\n";
  ss << "      \"params\": [" << fixed << setprecision(1) << t << ", 0, 0, null, " << setprecision(10) << lat << ", " << lon << ", " << fixed << setprecision(3) << relAlt << "],\n";
  ss << "      \"type\": \"SimpleItem\"\n";
  ss << "    }";
  return ss.str();
}

std::string make_simple_land(std::mt19937&, int doJumpId, double lat, double lon){
  // MAV_CMD_NAV_LAND = 21; params: abortAlt, precisionLand?, empty, yaw, lat, lon, alt
  double alt = 0.0;
  ostringstream ss; ss << simple_item_common_head(doJumpId, alt);
  ss << "      \"command\": 21,\n";
  ss << "      \"params\": [0, 0, 0, null, " << setprecision(10) << lat << ", " << lon << ", " << fixed << setprecision(1) << alt << "],\n";
  ss << "      \"type\": \"SimpleItem\"\n";
  ss << "    }";
  return ss.str();
}

} // namespace plan
