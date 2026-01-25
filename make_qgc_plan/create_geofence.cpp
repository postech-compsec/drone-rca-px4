#pragma once
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
using namespace std;

namespace plan {
std::string make_circle_geofence(std::mt19937& rng, double cLat, double cLon);
std::string make_polygon_geofence(std::mt19937& rng, double cLat, double cLon);

std::string create_geoFence(Ctx& ctx){
  int nCir = std::uniform_int_distribution<int>(0,2)(ctx.rng);
  int nPol = std::uniform_int_distribution<int>(0,2)(ctx.rng);
  vector<string> circles, polys;

  for(int i=0;i<nCir;i++) circles.push_back(make_circle_geofence(ctx.rng, ctx.centerLat, ctx.centerLon));
  for(int i=0;i<nPol;i++) polys.push_back(make_polygon_geofence(ctx.rng, ctx.centerLat, ctx.centerLon));

  ostringstream ss;
  ss << "{\n";
  ss << "  \"circles\": [\n";
  for(size_t i=0;i<circles.size();++i){
    ss << "    " << circles[i];
    if(i+1<circles.size()) ss << ",\n"; else ss << "\n";
  }
  ss << "  ],\n";
  ss << "  \"polygons\": [\n";
  for(size_t i=0;i<polys.size();++i){
    ss << "    " << polys[i];
    if(i+1<polys.size()) ss << ",\n"; else ss << "\n";
  }
  ss << "  ],\n";
  ss << "  \"version\": 2\n"; // container version per spec :contentReference[oaicite:19]{index=19}
  ss << "}";
  return ss.str();
}

} // namespace plan

#include "create_circle_geofence.cpp"
#include "create_polygon_geofence.cpp"
