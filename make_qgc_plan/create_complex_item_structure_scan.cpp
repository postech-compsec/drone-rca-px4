#pragma once
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using namespace std;

namespace plan {
std::string make_camera_calc(std::mt19937& rng);

static vector<pair<double,double>> random_structure_poly(std::mt19937& rng, double cLat, double cLon){
  // Small rectangle
  std::uniform_real_distribution<double> d(0.0004, 0.001);
  double r = d(rng);
  return {
    {cLat + r, cLon - r},
    {cLat + r, cLon + r},
    {cLat - r, cLon + r},
    {cLat - r, cLon - r}
  };
}

std::string make_complex_structure(std::mt19937& rng, int /*doJumpId*/, double centerLat, double centerLon){
  auto poly = random_structure_poly(rng, centerLat, centerLon);
  double elev = std::uniform_real_distribution<double>(25.0, 80.0)(rng); // Altitude
  int layers = std::uniform_int_distribution<int>(1,4)(rng);
  double height = std::uniform_real_distribution<double>(10.0, 40.0)(rng);

  // Per spec: StructureScan keys, version:2; CameraCalc version:1. :contentReference[oaicite:16]{index=16}
  ostringstream ss;
  ss << "    {\n";
  ss << "      \"Altitude\": " << fixed << setprecision(1) << elev << ",\n";
  ss << "      \"CameraCalc\": " << make_camera_calc(rng) << ",\n";
  ss << "      \"Layers\": " << layers << ",\n";
  ss << "      \"StructureHeight\": " << fixed << setprecision(1) << height << ",\n";
  ss << "      \"altitudeRelative\": true,\n";
  ss << "      \"complexItemType\": \"StructureScan\",\n";
  ss << "      \"polygon\": [\n";
  for(size_t i=0;i<poly.size();++i){
    ss << "        [" << setprecision(10) << poly[i].first << ", " << poly[i].second << "]";
    if(i+1<poly.size()) ss << ",\n"; else ss << "\n";
  }
  ss << "      ],\n";
  ss << "      \"type\": \"ComplexItem\",\n";
  ss << "      \"version\": 2\n";
  ss << "    }";
  return ss.str();
}

} // namespace plan

#include "create_camera_calc.cpp"
