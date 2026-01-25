#pragma once
#include <iomanip>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using namespace std;

namespace plan {

std::string make_polygon_geofence(std::mt19937& rng, double cLat, double cLon){
  // CW winding quad
  double r = std::uniform_real_distribution<double>(0.003,0.009)(rng);
  vector<pair<double,double>> pts = {
    {cLat + r, cLon - r},
    {cLat + r, cLon + r},
    {cLat - r, cLon + r},
    {cLat - r, cLon - r}
  };
  bool include = std::uniform_int_distribution<int>(0,1)(rng);

  // Per spec: polygon item (doc example shows item version 1), container geoFence.version=2. :contentReference[oaicite:21]{index=21}
  ostringstream ss;
  ss << "{ \"inclusion\": " << (include?"true":"false") << ", \"polygon\": [";
  for(size_t i=0;i<pts.size();++i){
    ss << "[" << setprecision(10) << pts[i].first << ", " << pts[i].second << "]";
    if(i+1<pts.size()) ss << ", ";
  }
  ss << "], \"version\": 1 }";
  return ss.str();
}

} // namespace plan
