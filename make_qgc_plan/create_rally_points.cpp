#pragma once
#include <array>
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
#include <vector>
using namespace std;

namespace plan {

std::string create_rally_points(Ctx& ctx){
  int n = std::uniform_int_distribution<int>(0,3)(ctx.rng);
  vector<array<double,3>> pts;
  for(int i=0;i<n;i++){
    double lat = ctx.centerLat + std::uniform_real_distribution<double>(-0.008,0.008)(ctx.rng);
    double lon = ctx.centerLon + std::uniform_real_distribution<double>(-0.008,0.008)(ctx.rng);
    double alt = std::uniform_real_distribution<double>(30.0, 80.0)(ctx.rng);
    pts.push_back({lat,lon,alt});
  }
  // Per spec: points array and version 2. :contentReference[oaicite:22]{index=22}
  ostringstream ss;
  ss << "{\n";
  ss << "  \"points\": [\n";
  for(size_t i=0;i<pts.size();++i){
    ss << "    [" << setprecision(10) << pts[i][0] << ", " << pts[i][1] << ", " << fixed << setprecision(1) << pts[i][2] << "]";
    if(i+1<pts.size()) ss << ",\n"; else ss << "\n";
  }
  ss << "  ],\n";
  ss << "  \"version\": 2\n";
  ss << "}";
  return ss.str();
}

} // namespace plan
