#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#if __has_include(<filesystem>)
  #include <filesystem>
  namespace fs = std::filesystem;
#elif __has_include(<experimental/filesystem>)
  #include <experimental/filesystem>
  namespace fs = std::experimental::filesystem;
#else
  #error "This compiler lacks <filesystem> support."
#endif

using namespace std;
namespace fs = std::filesystem;

// --- Forward declarations (implemented in included .cpps) ---
namespace plan {
  struct Ctx {
    std::mt19937 rng;
    double centerLat, centerLon; // home / planning center
    double homeAltAmsl;
  };

  std::string create_mission(Ctx& ctx, int vehicleType);
  std::string create_geoFence(Ctx& ctx);
  std::string create_rally_points(Ctx& ctx);
}

// Include submodules exactly as requested
#include "create_mission.cpp"
#include "create_geofence.cpp"
#include "create_rally_points.cpp"

static string make_top_level(const string& mission,
                             const string& geofence,
                             const string& rally) {
  // Top-level Plan object per spec (version 1)
  // docs: Plan container keys/version :contentReference[oaicite:7]{index=7}
  ostringstream ss;
  ss << "{\n";
  ss << "  \"fileType\": \"Plan\",\n";
  ss << "  \"geoFence\": " << geofence << ",\n";
  ss << "  \"groundStation\": \"QGroundControl\",\n";
  ss << "  \"mission\": " << mission << ",\n";
  ss << "  \"rallyPoints\": " << rally << ",\n";
  ss << "  \"version\": 1\n";
  ss << "}\n";
  return ss.str();
}

static double clamp_lat(double lat){ return std::max(-89.9, std::min(89.9, lat)); }
static double clamp_lon(double lon){
  while(lon < -180) lon += 360;
  while(lon >  180) lon -= 360;
  return lon;
}

int main(int argc, char** argv){
  if(argc < 3){
    cerr << "Usage: " << argv[0] << " <count> <output_dir> [vehicleType]\n"
         << "  vehicleType: 1=fixed-wing, 2=multirotor (default: random)\n";
    return 1;
  }
  int count = stoi(argv[1]);
  fs::path outDir = fs::path(argv[2]);
  int forcedVehicle = -1;
  if(argc >= 4) forcedVehicle = stoi(argv[3]);

  if(!fs::exists(outDir)) fs::create_directories(outDir);

  // Seed RNG
  std::random_device rd;
  plan::Ctx ctx;
  ctx.rng.seed(rd());
  // Choose a reasonable planning center (default to the Zurich sample area)
  // You can change these or randomize a rough world bbox if desired.
  ctx.centerLat = 47.3977419;
  ctx.centerLon = 8.545594;
  ctx.homeAltAmsl = 488.0;

  for(int i=0;i<count;i++){
    int vehicleType;
    if(forcedVehicle == 1 || forcedVehicle == 2) vehicleType = forcedVehicle;
    else {
      std::uniform_int_distribution<int> pick(0,1);
      vehicleType = pick(ctx.rng) ? 2 : 1; // 2=quad, 1=fixed
    }

    std::string mission   = plan::create_mission(ctx, vehicleType);
    std::string geofence  = plan::create_geoFence(ctx);
    std::string rally     = plan::create_rally_points(ctx);
    std::string json      = make_top_level(mission, geofence, rally);

    char name[64];
    std::snprintf(name, sizeof(name), "plan_%04d.plan", i+1);
    fs::path fp = outDir / name;

    std::ofstream ofs(fp);
    ofs << json;
    ofs.close();
    cout << "Wrote " << fp << "\n";
  }
  return 0;
}
