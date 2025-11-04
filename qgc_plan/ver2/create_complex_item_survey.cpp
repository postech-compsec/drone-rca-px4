#pragma once
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using namespace std;

namespace plan {
std::string make_transect_style(std::mt19937& rng, bool followTerrain);

// Polygon helper
static vector<pair<double,double>> random_polygon(std::mt19937& rng, double cLat, double cLon){
  // Make a simple convex quad around center
  std::uniform_real_distribution<double> dR(0.001, 0.004);
  double r = dR(rng);
  vector<pair<double,double>> poly = {
    {cLat + r, cLon - r},
    {cLat + r, cLon + r},
    {cLat - r, cLon + r},
    {cLat - r, cLon - r},
  };
  return poly; // clockwise order already
}

std::string make_complex_survey(std::mt19937& rng, int /*doJumpId*/, double centerLat, double centerLon){
  double angle = std::uniform_int_distribution<int>(0,179)(rng);
  bool followTerrain = false;
  auto poly = random_polygon(rng, centerLat, centerLon);

  // Per spec: type ComplexItem, complexItemType "survey", version (use 3 for compatibility), angle, entryLocation, flyAlternateTransects, polygon, TransectStyleComplexItem. :contentReference[oaicite:14]{index=14}
  ostringstream ss;
  ss << "    {\n";
  ss << "      \"TransectStyleComplexItem\": " << make_transect_style(rng, followTerrain) << ",\n";
  ss << "      \"angle\": " << angle << ",\n";
  ss << "      \"complexItemType\": \"survey\",\n";
  ss << "      \"entryLocation\": 0,\n";
  ss << "      \"flyAlternateTransects\": " << (std::uniform_int_distribution<int>(0,1)(rng) ? "true" : "false") << ",\n";
  ss << "      \"polygon\": [\n";
  for(size_t i=0;i<poly.size();++i){
    ss << "        [" << setprecision(10) << poly[i].first << ", " << poly[i].second << "]";
    if(i+1<poly.size()) ss << ",\n"; else ss << "\n";
  }
  ss << "      ],\n";
  ss << "      \"type\": \"ComplexItem\",\n";
  ss << "      \"version\": 3\n";
  ss << "    }";
  return ss.str();
}

} // namespace plan

#include "create_transect_style_complex_item.cpp"
