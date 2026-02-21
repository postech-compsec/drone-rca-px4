#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
using namespace std;

namespace plan {

// forward
std::string make_simple_takeoff(std::mt19937& rng, int doJumpId, double lat, double lon, double relAlt);
std::string make_simple_waypoint(std::mt19937& rng, int doJumpId, double lat, double lon, double relAlt);
std::string make_simple_loiter_time(std::mt19937& rng, int doJumpId, double lat, double lon, double relAlt);
std::string make_simple_land(std::mt19937& rng, int doJumpId, double lat, double lon);
std::string make_complex_survey(std::mt19937& rng, int doJumpId, double centerLat, double centerLon);
std::string make_complex_corridor(std::mt19937& rng, int doJumpId, double centerLat, double centerLon);
std::string make_complex_structure(std::mt19937& rng, int doJumpId, double centerLat, double centerLon);

static double urand(std::mt19937& r, double a, double b){
  std::uniform_real_distribution<double> d(a,b); return d(r);
}
static int irand(std::mt19937& r, int a, int b){
  std::uniform_int_distribution<int> d(a,b); return d(r);
}

std::string create_mission(Ctx& ctx, int vehicleType, bool simpleOnly, int maxMissionItems){
  // Mission per spec: required keys+versions :contentReference[oaicite:8]{index=8}
  // firmwareType: MAV_AUTOPILOT_PX4 (example uses 12). We'll set 12.
  double cruiseSpeed = (vehicleType==1) ? urand(ctx.rng, 15.0, 28.0) : urand(ctx.rng, 10.0, 18.0);
  double hoverSpeed  = (vehicleType==2) ? urand(ctx.rng, 3.0, 8.0) : 0.0;
  int globalAltMode  = irand(ctx.rng, 0, 1); // 0=Relative, 1=AMSL (kept simple)
  // Planned home position (AMSL)
  double homeLat = ctx.centerLat + urand(ctx.rng, -0.001, 0.001);
  double homeLon = ctx.centerLon + urand(ctx.rng, -0.001, 0.001);
  double homeAlt = ctx.homeAltAmsl;

  // Build items
  vector<string> items;
  int doJumpId=1;

  // Always start with TAKEOFF for aircraft (OK for copter & plane) :contentReference[oaicite:9]{index=9}
  {
    double tLat = homeLat + urand(ctx.rng, -0.0015, 0.0015);
    double tLon = homeLon + urand(ctx.rng, -0.0015, 0.0015);
    double tAlt = urand(ctx.rng, 25, (vehicleType==1?120.0:80.0));
    items.push_back(make_simple_takeoff(ctx.rng, doJumpId++, tLat, tLon, tAlt));
  }

  // Middle: random mix of Simple and (sometimes) Complex
  int midMin = 3;
  int midMax = 7;
  if(maxMissionItems > 0){
    int maxMid = maxMissionItems - 2; // reserve takeoff + land
    midMax = std::min(midMax, maxMid);
    midMin = std::min(midMin, midMax);
  }
  int midCount = (midMax <= 0) ? 0 : irand(ctx.rng, midMin, midMax);
  for(int k=0;k<midCount;k++){
    int pick = irand(ctx.rng, 0, simpleOnly ? 3 : 6);
    double lat = homeLat + urand(ctx.rng, -0.01, 0.01);
    double lon = homeLon + urand(ctx.rng, -0.01, 0.01);
    double alt = urand(ctx.rng, 25, (vehicleType==1?140.0:90.0));

    if(pick<=2){
      items.push_back(make_simple_waypoint(ctx.rng, doJumpId++, lat, lon, alt));
    }else if(pick==3){
      items.push_back(make_simple_loiter_time(ctx.rng, doJumpId++, lat, lon, alt));
    }else if(pick==4){
      items.push_back(make_complex_survey(ctx.rng, doJumpId++, ctx.centerLat, ctx.centerLon));
    }else if(pick==5){
      items.push_back(make_complex_corridor(ctx.rng, doJumpId++, ctx.centerLat, ctx.centerLon));
    }else{
      items.push_back(make_complex_structure(ctx.rng, doJumpId++, ctx.centerLat, ctx.centerLon));
    }
  }

  // Land near home
  {
    double lLat = homeLat + urand(ctx.rng, -0.002, 0.002);
    double lLon = homeLon + urand(ctx.rng, -0.002, 0.002);
    items.push_back(make_simple_land(ctx.rng, doJumpId++, lLat, lLon));
  }

  // Emit JSON
  ostringstream ss;
  ss << "{\n";
  ss << "  \"cruiseSpeed\": " << fixed << setprecision(3) << cruiseSpeed << ",\n";
  ss << "  \"firmwareType\": 12,\n";                  // MAV_AUTOPILOT_PX4 example value :contentReference[oaicite:10]{index=10}
  ss << "  \"globalPlanAltitudeMode\": " << globalAltMode << ",\n";
  ss << "  \"hoverSpeed\": " << fixed << setprecision(3) << hoverSpeed << ",\n";
  ss << "  \"items\": [\n";
  for(size_t i=0;i<items.size();++i){
    ss << items[i];
    if(i+1<items.size()) ss << ",\n";
    else ss << "\n";
  }
  ss << "  ],\n";
  ss << "  \"plannedHomePosition\": [\n";
  ss << "    " << setprecision(10) << homeLat << ",\n";
  ss << "    " << setprecision(10) << homeLon << ",\n";
  ss << "    " << fixed << setprecision(3) << homeAlt << "\n";
  ss << "  ],\n";
  ss << "  \"vehicleType\": " << vehicleType << ",\n"; // MAV_TYPE (1=fixed-wing, 2=quadrotor) :contentReference[oaicite:11]{index=11}
  ss << "  \"version\": 2\n";                           // Mission version per spec :contentReference[oaicite:12]{index=12}
  ss << "}";
  return ss.str();
}

} // namespace plan

// ---- bring in submodules ----
#include "create_simple_item.cpp"
#include "create_complex_item_survey.cpp"
#include "create_complex_item_corridor_scan.cpp"
#include "create_complex_item_structure_scan.cpp"
