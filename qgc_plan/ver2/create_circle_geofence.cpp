#pragma once
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
using namespace std;

namespace plan {

std::string make_circle_geofence(std::mt19937& rng, double cLat, double cLon){
  double lat = cLat + std::uniform_real_distribution<double>(-0.006, 0.006)(rng);
  double lon = cLon + std::uniform_real_distribution<double>(-0.006, 0.006)(rng);
  double rad = std::uniform_real_distribution<double>(150.0, 600.0)(rng);
  bool include = std::uniform_int_distribution<int>(0,1)(rng);

  // Per spec: circle item (inner version 1) inside geoFence.version=2 container. :contentReference[oaicite:20]{index=20}
  ostringstream ss;
  ss << "{ \"circle\": { \"center\": [" << setprecision(10) << lat << ", " << lon << "], \"radius\": " << fixed << setprecision(2) << rad
     << " }, \"inclusion\": " << (include?"true":"false") << ", \"version\": 1 }";
  return ss.str();
}

} // namespace plan
