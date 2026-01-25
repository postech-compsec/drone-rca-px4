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

static vector<pair<double,double>> random_polyline(std::mt19937& rng, double cLat, double cLon){
  // Straight-ish line of 3–5 points
  int n = std::uniform_int_distribution<int>(3,5)(rng);
  std::uniform_real_distribution<double> dL(-0.009, 0.009);
  vector<pair<double,double>> pl;
  double baseLat = cLat + dL(rng), baseLon = cLon + dL(rng);
  double stepLat = std::uniform_real_distribution<double>(-0.002,0.002)(rng);
  double stepLon = std::uniform_real_distribution<double>(-0.003,0.003)(rng);
  for(int i=0;i<n;i++){
    pl.emplace_back(baseLat + i*stepLat, baseLon + i*stepLon);
  }
  return pl;
}

std::string make_complex_corridor(std::mt19937& rng, int /*doJumpId*/, double centerLat, double centerLon){
  double width = std::uniform_real_distribution<double>(20.0, 120.0)(rng);
  int entry = std::uniform_int_distribution<int>(0,1)(rng);
  bool followTerrain = false;
  auto polyline = random_polyline(rng, centerLat, centerLon);

  // Per spec: CorridorWidth, EntryPoint, polyline, TransectStyleComplexItem, type, complexItemType, version:3 (current). :contentReference[oaicite:15]{index=15}
  ostringstream ss;
  ss << "    {\n";
  ss << "      \"CorridorWidth\": " << fixed << setprecision(1) << width << ",\n";
  ss << "      \"EntryPoint\": " << entry << ",\n";
  ss << "      \"TransectStyleComplexItem\": " << make_transect_style(rng, followTerrain) << ",\n";
  ss << "      \"complexItemType\": \"CorridorScan\",\n";
  ss << "      \"polyline\": [\n";
  for(size_t i=0;i<polyline.size();++i){
    ss << "        [" << setprecision(10) << polyline[i].first << ", " << polyline[i].second << "]";
    if(i+1<polyline.size()) ss << ",\n"; else ss << "\n";
  }
  ss << "      ],\n";
  ss << "      \"type\": \"ComplexItem\",\n";
  ss << "      \"version\": 3\n";
  ss << "    }";
  return ss.str();
}

} // namespace plan

#include "create_transect_style_complex_item.cpp"
