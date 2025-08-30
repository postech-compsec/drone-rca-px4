#!/usr/bin/env python3
# qgc_plan_random_gen.py
import argparse, json, math, os, random
from pathlib import Path
from typing import List, Tuple, Optional

# ---- Enumerations (subset; QGC/MAVLink 호환 숫자) ---------------------------
MAV_AUTOPILOT_CHOICES = [3, 12]  # 3: ArduPilot, 12: PX4
MAV_TYPE_CHOICES = [1, 2]        # 1: FIXED_WING, 2: QUADROTOR
MAV_FRAME_GLOBAL = 0
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

# MAV_CMD (주요 네비게이션)
MAV_CMD_NAV_WAYPOINT    = 16
MAV_CMD_NAV_LOITER_TIME = 19
MAV_CMD_NAV_LAND        = 21
MAV_CMD_NAV_TAKEOFF     = 22

# ---- Helpers ----------------------------------------------------------------
def randf(a: float, b: float) -> float:
    return random.uniform(a, b)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def meters_per_deg_lon(lat_deg: float) -> float:
    # 위도에 따른 경도 1도의 길이(근사)
    return 111_320.0 * max(1e-6, math.cos(math.radians(lat_deg)))

def offset_latlon(lat: float, lon: float, dx_m: float, dy_m: float) -> Tuple[float, float]:
    """현재 위경도(lat, lon)에서 동쪽 dx_m, 북쪽 dy_m 만큼 이동시킨 위경도 반환."""
    dlat = dy_m / 111_320.0
    dlon = dx_m / meters_per_deg_lon(lat)
    return lat + dlat, lon + dlon

def approx_distance_m(center_lat: float, center_lon: float, lat: float, lon: float) -> float:
    """중심(lat,lon) 기준의 평면 근사 거리(m). 지역 반경이 수십 km 이내일 때 충분."""
    dx = (lon - center_lon) * meters_per_deg_lon(center_lat)
    dy = (lat - center_lat) * 111_320.0
    return math.hypot(dx, dy)

def random_point_in_circle(center_lat: float, center_lon: float, radius_m: float) -> Tuple[float, float]:
    """중심/반경 내 임의 점(원 내부 균일 분포)."""
    r = radius_m * math.sqrt(random.random())
    theta = randf(0.0, 2.0 * math.pi)
    dx, dy = r * math.cos(theta), r * math.sin(theta)
    return offset_latlon(center_lat, center_lon, dx, dy)

def confine_to_circle(center_lat: float, center_lon: float, cand_lat: float, cand_lon: float,
                      radius_m: float, margin: float = 1.0) -> Tuple[float, float]:
    """후보가 원 밖이면 원 둘레 안쪽(margin)으로 투영."""
    dx = (cand_lon - center_lon) * meters_per_deg_lon(center_lat)
    dy = (cand_lat - center_lat) * 111_320.0
    dist = math.hypot(dx, dy)
    if dist <= max(0.0, radius_m - margin):
        return cand_lat, cand_lon
    if dist < 1e-6:
        return offset_latlon(center_lat, center_lon, 0.0, 0.0)
    scale = (max(0.0, radius_m - margin)) / dist
    nx, ny = dx * scale, dy * scale
    return offset_latlon(center_lat, center_lon, nx, ny)

# ---- Mission builders --------------------------------------------------------
def random_altitude(vehicle_type: int) -> float:
    if vehicle_type == 1:  # FIXED_WING
        return randf(60.0, 250.0)
    else:                  # QUADROTOR
        return randf(20.0, 120.0)

def random_speed(vehicle_type: int) -> Tuple[float, float]:
    if vehicle_type == 1:  # FIXED_WING
        return randf(15.0, 40.0), 0.0
    else:                  # QUADROTOR
        return randf(5.0, 18.0), randf(3.0, 12.0)

def waypoint_params(lat, lon, alt) -> List[float]:
    hold = randf(0.0, 10.0)           # sec
    accept_radius = randf(1.0, 20.0)  # m
    pass_through = random.randint(0, 1)  # 0=stop,1=pass-through
    yaw = randf(-180.0, 180.0)        # deg
    return [hold, accept_radius, pass_through, yaw, lat, lon, alt]

def takeoff_params(lat, lon, alt) -> List[float]:
    pitch = randf(5.0, 15.0)          # deg(FW), MC는 무시됨
    yaw = randf(-180.0, 180.0)
    return [pitch, 0.0, 0.0, yaw, lat, lon, alt]

def loiter_time_params(lat, lon, alt) -> List[float]:
    time_s = randf(5.0, 120.0)
    radius = randf(10.0, 80.0)        # 일부 FW 의미
    return [time_s, radius, 0.0, 0.0, lat, lon, alt]

def land_params(lat, lon, alt) -> List[float]:
    abort_alt = randf(10.0, 60.0)
    return [abort_alt, 0.0, 0.0, 0.0, lat, lon, alt]

def simple_item(cmd: int, did: int, frame: int, lat: float, lon: float, alt: float) -> dict:
    altitude_mode = random.randint(0, 1)  # Absolute/Relative 개념
    if cmd == MAV_CMD_NAV_TAKEOFF:
        params = takeoff_params(lat, lon, alt)
    elif cmd == MAV_CMD_NAV_LAND:
        params = land_params(lat, lon, alt)
    elif cmd == MAV_CMD_NAV_LOITER_TIME:
        params = loiter_time_params(lat, lon, alt)
    else:
        params = waypoint_params(lat, lon, alt)
    return {
        "type": "SimpleItem",
        "AMSLAltAboveTerrain": None,
        "Altitude": alt,
        "AltitudeMode": altitude_mode,
        "autoContinue": True,
        "command": cmd,
        "doJumpId": did,
        "frame": frame,
        "params": params,
    }

def choose_step_within_region(last_lat: float, last_lon: float, step_min: float, step_max: float,
                              center_lat: float, center_lon: float, radius_m: float) -> Tuple[float, float]:
    """지역 원 안을 유지하는 다음 점을 선택. 여러 번 시도 후 필요시 투영."""
    for _ in range(20):
        step_m = randf(step_min, step_max)
        theta = randf(0.0, 360.0)
        dx = step_m * math.cos(math.radians(theta))
        dy = step_m * math.sin(math.radians(theta))
        cand_lat, cand_lon = offset_latlon(last_lat, last_lon, dx, dy)
        if approx_distance_m(center_lat, center_lon, cand_lat, cand_lon) <= radius_m:
            return cand_lat, cand_lon
    # 반복 시도에도 실패하면 투영해 강제로 원 내부로
    cand_lat, cand_lon = confine_to_circle(center_lat, center_lon, last_lat, last_lon, radius_m)
    return cand_lat, cand_lon

def make_random_mission(min_items: int,
                        max_items: int,
                        region_center: Optional[Tuple[float, float]],
                        region_radius_km: Optional[float]) -> dict:
    firmware = random.choice(MAV_AUTOPILOT_CHOICES)
    vehicle  = random.choice(MAV_TYPE_CHOICES)
    cruise, hover = random_speed(vehicle)
    frame = random.choice([MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_FRAME_GLOBAL])
    global_alt_mode = random.randint(0, 3)

    # 중심/반경 설정
    if region_center is not None and region_radius_km is not None:
        c_lat, c_lon = region_center
        radius_m = max(5.0, region_radius_km * 1000.0)  # 5m 이상
        # 홈은 원 내부 임의 위치
        base_lat, base_lon = random_point_in_circle(c_lat, c_lon, radius_m * 0.6)
    else:
        # 전세계 랜덤(극지대 회피)
        c_lat = randf(-60.0, 60.0)
        c_lon = randf(-180.0, 180.0)
        radius_m = None
        base_lat, base_lon = c_lat, c_lon

    # 홈 고도
    home_alt = random_altitude(vehicle)
    home = [base_lat, base_lon, home_alt]

    # 아이템 개수
    n_items = random.randint(min_items, max_items)
    items = []
    did = 1

    # TAKEOFF
    t_alt = random_altitude(vehicle)
    if radius_m:
        # 홈 근처에서 조금 이동한 위치로 이륙
        t_lat, t_lon = choose_step_within_region(base_lat, base_lon, 20.0, 200.0, c_lat, c_lon, radius_m)
    else:
        t_lat, t_lon = offset_latlon(base_lat, base_lon, randf(-200, 200), randf(-200, 200))
    items.append(simple_item(MAV_CMD_NAV_TAKEOFF, did, frame, t_lat, t_lon, t_alt)); did += 1

    # 중간 경로
    last_lat, last_lon, last_alt = t_lat, t_lon, t_alt
    for _ in range(max(0, n_items - 2)):  # LAND 남김
        # 위치
        if radius_m:
            lat, lon = choose_step_within_region(last_lat, last_lon, 50.0, 400.0, c_lat, c_lon, radius_m)
        else:
            step_m = randf(50.0, 400.0)
            turn = randf(0, 360)
            dx = step_m * math.cos(math.radians(turn))
            dy = step_m * math.sin(math.radians(turn))
            lat, lon = offset_latlon(last_lat, last_lon, dx, dy)
        # 고도
        alt = clamp(last_alt + randf(-15.0, 25.0), 10.0, 400.0)
        # 명령
        cmd = random.choice([MAV_CMD_NAV_WAYPOINT, MAV_CMD_NAV_WAYPOINT, MAV_CMD_NAV_LOITER_TIME])
        items.append(simple_item(cmd, did, frame, lat, lon, alt)); did += 1
        last_lat, last_lon, last_alt = lat, lon, alt

    # LAND
    if radius_m:
        l_lat, l_lon = choose_step_within_region(last_lat, last_lon, 30.0, 200.0, c_lat, c_lon, radius_m)
    else:
        l_lat, l_lon = offset_latlon(last_lat, last_lon, randf(-150, 150), randf(-150, 150))
    l_alt = clamp(last_alt * 0.5, 0.0, 100.0)
    items.append(simple_item(MAV_CMD_NAV_LAND, did, frame, l_lat, l_lon, l_alt)); did += 1

    mission = {
        "version": 2,
        "firmwareType": firmware,
        "vehicleType": vehicle,
        "cruiseSpeed": cruise,
        "hoverSpeed": hover,
        "plannedHomePosition": home,               # [lat, lon, alt]
        "globalPlanAltitudeMode": global_alt_mode,
        "items": items,
    }
    return mission

def make_plan_dict(min_items: int,
                   max_items: int,
                   region_center: Optional[Tuple[float, float]],
                   region_radius_km: Optional[float]) -> dict:
    mission = make_random_mission(min_items, max_items, region_center, region_radius_km)
    plan = {
        "fileType": "Plan",
        "groundStation": "QGroundControl",
        "version": 1,
        "mission": mission,
        "geoFence": {"circles": [], "polygons": [], "version": 2},
        "rallyPoints": {"points": [], "version": 2},
    }
    return plan

# ---- CLI --------------------------------------------------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Random QGC .plan generator with optional region constraint")
    ap.add_argument("count", type=int, nargs="?", default=1, help="생성할 .plan 개수 (기본 1)")
    ap.add_argument("--outdir", "-o", type=Path, default=Path("."), help="출력 폴더")
    ap.add_argument("--seed", type=int, default=None, help="난수 시드(재현성)")
    ap.add_argument("--min-items", type=int, default=5, help="미션 최소 아이템 수(>=3 권장)")
    ap.add_argument("--max-items", type=int, default=18, help="미션 최대 아이템 수")
    # 지역 옵션
    ap.add_argument("--region", nargs=2, type=float, metavar=("LAT", "LON"),
                    help="경로를 제한할 중심 위도/경도 (예: --region 36.019 129.342)")
    ap.add_argument("--radius-km", type=float, default=None,
                    help="--region과 함께 사용할 반경(km). 지정 없으면 기본 2km")
    return ap.parse_args()

def main():
    args = parse_args()

    n = max(1, int(args.count))
    min_items = max(3, int(args.min_items))
    max_items = max(min_items, int(args.max_items))

    if args.seed is not None:
        random.seed(args.seed)

    # 지역 파라미터 정리
    region_center = None
    region_radius_km = None
    if args.region:
        lat, lon = float(args.region[0]), float(args.region[1])
        lat = clamp(lat, -85.0, 85.0)  # 극지대 안정성
        lon = ((lon + 180.0) % 360.0) - 180.0
        region_center = (lat, lon)
        region_radius_km = float(args.radius_km) if args.radius_km is not None else 2.0
        region_radius_km = max(0.05, region_radius_km)  # 최소 50m

    args.outdir.mkdir(parents=True, exist_ok=True)

    for i in range(1, n + 1):
        plan = make_plan_dict(min_items, max_items, region_center, region_radius_km)
        outpath = args.outdir / f"{i}.plan"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()

