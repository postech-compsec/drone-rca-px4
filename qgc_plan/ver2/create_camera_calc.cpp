#pragma once
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
using namespace std;

namespace plan {

std::string make_camera_calc(std::mt19937& rng){
  // Per spec: CameraCalc version:1 + fields. Use "Custom Camera" to allow full set. :contentReference[oaicite:18]{index=18}
  double f = std::uniform_real_distribution<double>(14.0, 28.0)(rng); // mm
  double sw = std::uniform_real_distribution<double>(13.0, 23.5)(rng);
  double sh = std::uniform_real_distribution<double>(8.0,  15.6)(rng);
  int iw = std::uniform_int_distribution<int>(4000, 6000)(rng);
  int ih = std::uniform_int_distribution<int>(3000, 4000)(rng);
  int fo = std::uniform_int_distribution<int>(65, 80)(rng); // %
  int so = std::uniform_int_distribution<int>(60, 75)(rng); // %
  double dist = std::uniform_real_distribution<double>(30.0, 120.0)(rng);
  bool landscape = true;

  // Adjusted footprints are informational here; QGC can recalc.
  double gsd = 25; // ImageDensity placeholder (doc shows this field), leave as 25
  double adjF = dist * 0.5; // rough stand-in
  double adjS = dist * 0.7;

  ostringstream ss;
  ss << "{\n";
  ss << "  \"AdjustedFootprintFrontal\": " << fixed << setprecision(1) << adjF << ",\n";
  ss << "  \"AdjustedFootprintSide\": "   << fixed << setprecision(1) << adjS << ",\n";
  ss << "  \"CameraName\": \"Custom Camera\",\n";
  ss << "  \"DistanceToSurface\": " << fixed << setprecision(1) << dist << ",\n";
  ss << "  \"DistanceToSurfaceRelative\": true,\n";
  ss << "  \"FixedOrientation\": false,\n";
  ss << "  \"FocalLength\": " << fixed << setprecision(1) << f << ",\n";
  ss << "  \"FrontalOverlap\": " << fo << ",\n";
  ss << "  \"ImageDensity\": " << gsd << ",\n";
  ss << "  \"ImageHeight\": " << ih << ",\n";
  ss << "  \"ImageWidth\": " << iw << ",\n";
  ss << "  \"Landscape\": " << (landscape?"true":"false") << ",\n";
  ss << "  \"MinTriggerInterval\": 0,\n";
  ss << "  \"SensorHeight\": " << fixed << setprecision(1) << sh << ",\n";
  ss << "  \"SensorWidth\": " << fixed << setprecision(1) << sw << ",\n";
  ss << "  \"SideOverlap\": " << so << ",\n";
  ss << "  \"ValueSetIsDistance\": true,\n";
  ss << "  \"version\": 1\n";
  ss << "}";
  return ss.str();
}

} // namespace plan
