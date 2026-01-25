#pragma once
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
using namespace std;

namespace plan {
std::string make_camera_calc(std::mt19937& rng);

std::string make_transect_style(std::mt19937& rng, bool followTerrain){
  // Per spec: TransectStyleComplexItem + CameraCalc + booleans + TurnAroundDistance + version:1. :contentReference[oaicite:17]{index=17}
  bool trigInTurn = std::uniform_int_distribution<int>(0,1)(rng);
  bool hoverCap   = std::uniform_int_distribution<int>(0,1)(rng);
  bool refly90    = std::uniform_int_distribution<int>(0,1)(rng);
  double turnDist = std::uniform_real_distribution<double>(5.0, 25.0)(rng);

  ostringstream ss;
  ss << "{\n";
  ss << "  \"CameraCalc\": " << make_camera_calc(rng) << ",\n";
  ss << "  \"CameraTriggerInTurnAround\": " << (trigInTurn? "true":"false") << ",\n";
  ss << "  \"FollowTerrain\": " << (followTerrain? "true":"false") << ",\n";
  ss << "  \"HoverAndCapture\": " << (hoverCap? "true":"false") << ",\n";
  ss << "  \"Items\": [],\n"; // optional; QGC fills after generation
  ss << "  \"Refly90Degrees\": " << (refly90? "true":"false") << ",\n";
  ss << "  \"TurnAroundDistance\": " << fixed << setprecision(1) << turnDist << ",\n";
  ss << "  \"VisualTransectPoints\": [],\n"; // optional visual cache
  ss << "  \"version\": 1\n";
  ss << "}";
  return ss.str();
}

} // namespace plan

#include "create_camera_calc.cpp"
