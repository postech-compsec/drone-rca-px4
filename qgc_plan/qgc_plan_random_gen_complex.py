#!/usr/bin/env python3
# qgc_plan_random_gen_complex.py — Random QGC .plan generator
# - Region constraint (--region / --radius-km)
# - Geofence shape constraint (--fence-type circle|polygon)
# - Altitude / speed ranges
# - ComplexItem randomization: Survey, CorridorScan, StructureScan
# Python 3.8+

import argparse, json, math, random, re
from pathlib import Path
from typing import List, Tuple, Optional

# --------------------------- MAVLink/QGC enums (subset) ----------------------
MAV_AUTOPILOT_CHOICES = [3, 12]  # 3: ArduPilot, 12: PX4
MAV_TYPE_CHOICES = [1, 2]        # 1: FIXED_WING, 2: QUADROTOR
MAV_FRAME_GLOBAL = 0
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

# Commands (navigation)
MAV_CMD_NAV_WAYPOINT    = 16
MAV_CMD_NAV_LOITER_TIME = 19
MAV_CMD_NAV_LAND        = 21
MAV_CMD_NAV_TAKEOFF     = 22

# --------------------------- Math / geo helpers ------------------------------
EARTH_M_PER_DEG_LAT = 111_320.0

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def meters_per_deg_lon(lat_deg: float) -> float:
    return EARTH_M_PER_DEG_LAT * max(1e-6, math.cos(math.radians(lat_deg)))

def offset_latlon(lat: float, lon: float, dx_m: float, dy_m: float) -> Tuple[float, float]:
    dlat = dy_m / EARTH_M_PER_DEG_LAT
    dlon = dx_m / meters_per_deg_lon(lat)
    return lat + dlat, lon + dlon

def approx_distance_m(center_lat: float, center_lon: float, lat: float, lon: float) -> float:
    dx = (lon - center_lon) * meters_per_deg_lon(center_lat)
    dy = (lat - center_lat) * EARTH_M_PER_DEG_LAT
    return math.hypot(dx, dy)

# --------------------------- Region (circle) utilities -----------------------

def random_point_in_circle(center_lat: float, center_lon: float, radius_m: float) -> Tuple[float, float]:
    r = radius_m * math.sqrt(random.random())
    theta = random.uniform(0.0, 2.0 * math.pi)
    dx, dy = r * math.cos(theta), r * math.sin(theta)
    return offset_latlon(center_lat, center_lon, dx, dy)

def confine_to_circle(center_lat: float, center_lon: float, cand_lat: float, cand_lon: float,
                      radius_m: float, margin: float = 1.0) -> Tuple[float, float]:
    dx = (cand_lon - center_lon) * meters_per_deg_lon(center_lat)
    dy = (cand_lat - center_lat) * EARTH_M_PER_DEG_LAT
    dist = math.hypot(dx, dy)
    if dist <= max(0.0, radius_m - margin):
        return cand_lat, cand_lon
    if dist < 1e-6:
        return offset_latlon(center_lat, center_lon, 0.0, 0.0)
    scale = (max(0.0, radius_m - margin)) / dist
    nx, ny = dx * scale, dy * scale
    return offset_latlon(center_lat, center_lon, nx, ny)

# --------------------------- Convex polygon utilities ------------------------

def regular_convex_polygon(center_lat: float, center_lon: float, radius_m: float, n: int,
                           jitter_ratio: float = 0.15) -> List[Tuple[float,float]]:
    """Generate a (roughly) regular n-gon around center with slight radius jitter."""
    pts = []
    for k in range(n):
        ang = 2.0 * math.pi * k / n
        r = radius_m * (1.0 - jitter_ratio/2 + jitter_ratio * random.random())
        dx, dy = r * math.cos(ang), r * math.sin(ang)
        pts.append(offset_latlon(center_lat, center_lon, dx, dy))
    return pts


def point_in_convex_polygon(pt: Tuple[float,float], poly: List[Tuple[float,float]]) -> bool:
    """Return True if point is inside (or on edge of) a convex polygon (lat,lon order)."""
    x0, y0 = pt[1], pt[0]  # use (lon, lat) for consistent math
    sign = None
    m = len(poly)
    for i in range(m):
        y1, x1 = poly[i][0], poly[i][1]
        y2, x2 = poly[(i+1)%m][0], poly[(i+1)%m][1]
        cross = (x2 - x1)*(y0 - y1) - (y2 - y1)*(x0 - x1)
        if cross == 0:
            continue
        s = cross > 0
        if sign is None:
            sign = s
        elif sign != s:
            return False
    return True


def random_point_in_convex_polygon(poly: List[Tuple[float,float]], center_hint: Optional[Tuple[float,float]] = None) -> Tuple[float,float]:
    """Sample a point inside a convex polygon via triangle fan (center ~ centroid)."""
    if center_hint is None:
        lat_c = sum(p[0] for p in poly)/len(poly)
        lon_c = sum(p[1] for p in poly)/len(poly)
        c = (lat_c, lon_c)
    else:
        c = center_hint
    i = random.randrange(0, len(poly))
    a = c
    b = poly[i]
    d = poly[(i+1) % len(poly)]
    r1, r2 = math.sqrt(random.random()), random.random()
    lat = (1-r1)*a[0] + r1*((1-r2)*b[0] + r2*d[0])
    lon = (1-r1)*a[1] + r1*((1-r2)*b[1] + r2*d[1])
    return (lat, lon)


def choose_step_within_polygon(last_lat: float, last_lon: float, step_min: float, step_max: float,
                               poly: List[Tuple[float,float]], center_hint: Tuple[float,float]) -> Tuple[float,float]:
    for _ in range(24):
        step_m = random.uniform(step_min, step_max)
        theta = random.uniform(0.0, 360.0)
        dx = step_m * math.cos(math.radians(theta))
        dy = step_m * math.sin(math.radians(theta))
        cand_lat, cand_lon = offset_latlon(last_lat, last_lon, dx, dy)
        if point_in_convex_polygon((cand_lat, cand_lon), poly):
            return cand_lat, cand_lon
    return random_point_in_convex_polygon(poly, center_hint)

# --------------------------- Mission field helpers ---------------------------

def random_altitude(vehicle_type: int, alt_min: float, alt_max: float) -> float:
    return random.uniform(alt_min, alt_max)


def random_speed(vehicle_type: int, cruise_min: float, cruise_max: float,
                 hover_min: float, hover_max: float) -> Tuple[float, float]:
    if vehicle_type == 1:  # FIXED_WING
        cruise = random.uniform(cruise_min, cruise_max)
        return cruise, 0.0
    else:  # QUADROTOR
        cruise = random.uniform(max(hover_min, cruise_min), cruise_max)
        hover = random.uniform(hover_min, hover_max)
        return cruise, hover


def waypoint_params(lat, lon, alt) -> List[float]:
    hold = random.uniform(0.0, 10.0)
    accept_radius = random.uniform(1.0, 20.0)
    pass_through = random.randint(0, 1)
    yaw = random.uniform(-180.0, 180.0)
    return [hold, accept_radius, pass_through, yaw, lat, lon, alt]


def takeoff_params(lat, lon, alt) -> List[float]:
    pitch = random.uniform(5.0, 15.0)
    yaw = random.uniform(-180.0, 180.0)
    return [pitch, 0.0, 0.0, yaw, lat, lon, alt]


def loiter_time_params(lat, lon, alt) -> List[float]:
    time_s = random.uniform(5.0, 120.0)
    radius = random.uniform(10.0, 80.0)
    return [time_s, radius, 0.0, 0.0, lat, lon, alt]


def land_params(lat, lon, alt) -> List[float]:
    abort_alt = random.uniform(10.0, 60.0)
    return [abort_alt, 0.0, 0.0, 0.0, lat, lon, alt]


def simple_item(cmd: int, did: int, frame: int, lat: float, lon: float, alt: float) -> dict:
    altitude_mode = random.randint(0, 1)
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

# --------------------------- ComplexItem builders ----------------------------

def camera_calc_random(alt_min: float, alt_max: float) -> dict:
    ground_res = random.uniform(2.0, 5.0)
    return {
        "CameraName": "Manual (no camera)",
        "Version": 1,
        "SensorWidth": 6.3,
        "SensorHeight": 4.7,
        "ImageWidth": 4000,
        "ImageHeight": 3000,
        "FocalLength": 4.5,
        "IsCustomCamera": True,
        "FixedValueIsAltitude": True,
        "Altitude": random.uniform(alt_min, alt_max),
        "GroundResolution": ground_res,
        "FrontalOverlap": random.uniform(65.0, 85.0),
        "SideOverlap": random.uniform(55.0, 80.0),
    }


def complex_survey(polygon: List[Tuple[float,float]], alt_min: float, alt_max: float) -> dict:
    cam = camera_calc_random(alt_min, alt_max)
    return {
        "type": "ComplexItem",
        "complexItemType": "survey",
        "version": 4,
        "polygon": [[lat, lon] for (lat, lon) in polygon],
        "entryLocation": 0,
        "flyAlternateTransects": False,
        "TransectStyleComplexItem": {
            "CameraCalc": cam,
            "Angle": random.uniform(0.0, 180.0),
            "TurnAroundDistance": random.uniform(10.0, 25.0),
            "HoverAndCapture": False,
            "Refly90Degrees": False,
            "FollowTerrain": False,
        },
    }


def complex_corridor(polyline: List[Tuple[float,float]], alt_min: float, alt_max: float, width_m: float) -> dict:
    cam = camera_calc_random(alt_min, alt_max)
    return {
        "type": "ComplexItem",
        "complexItemType": "CorridorScan",
        "version": 1,
        "polyline": [[lat, lon] for (lat, lon) in polyline],
        "entryLocation": 0,
        "corridorWidth": width_m,
        "TransectStyleComplexItem": {
            "CameraCalc": cam,
            "Angle": 0.0,
            "TurnAroundDistance": random.uniform(10.0, 25.0),
            "HoverAndCapture": False,
            "FollowTerrain": False,
        },
    }


def complex_structure(polygon: List[Tuple[float,float]], alt_min: float, alt_max: float) -> dict:
    """Minimal StructureScan spec (QGC complexItemType "StructureScan", version 2)."""
    cam = camera_calc_random(alt_min, alt_max)
    return {
        "type": "ComplexItem",
        "complexItemType": "StructureScan",
        "version": 2,
        "polygon": [[lat, lon] for (lat, lon) in polygon],
        "Altitude": random.uniform(alt_min, alt_max),
        "CameraCalc": cam,
        "entryLocation": 0,
    }

# --------------------------- Mission assembly --------------------------------

def make_random_mission(
    min_items: int,
    max_items: int,
    region_center: Optional[Tuple[float, float]],
    region_radius_km: Optional[float],
    # geofence influence
    fence_type: str,
    fence_poly: Optional[List[Tuple[float,float]]],
    fence_center: Optional[Tuple[float,float]],
    fence_radius_m: Optional[float],
    # ranges
    alt_min: float,
    alt_max: float,
    cruise_min: float,
    cruise_max: float,
    hover_min: float,
    hover_max: float,
    # complex items toggles & probs
    enable_survey: bool,
    survey_prob: float,
    enable_corridor: bool,
    corridor_prob: float,
    enable_structure: bool,
    structure_prob: float,
    max_complex: int,
    # unified ranges
    survey_vertices_rng: Tuple[int,int],
    structure_vertices_rng: Tuple[int,int],
    corridor_legs_rng: Tuple[int,int],
    corridor_width_rng_m: Tuple[float,float],
) -> Tuple[dict, dict]:



    firmware = random.choice(MAV_AUTOPILOT_CHOICES)
    vehicle  = random.choice(MAV_TYPE_CHOICES)
    cruise, hover = random_speed(vehicle, cruise_min, cruise_max, hover_min, hover_max)
    frame = random.choice([MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_FRAME_GLOBAL])
    global_alt_mode = random.randint(0, 3)

    # Determine spatial constraint priority: fence > region > global
    poly_constraint: Optional[List[Tuple[float,float]]] = None
    circle_constraint: Optional[Tuple[Tuple[float,float], float]] = None

    if fence_type == "polygon" and fence_poly:
        poly_constraint = fence_poly
    elif fence_type == "circle" and fence_center and fence_radius_m:
        circle_constraint = (fence_center, fence_radius_m)
    elif region_center and region_radius_km:
        circle_constraint = (region_center, region_radius_km * 1000.0)

    # Pick home/base
    if poly_constraint:
        lat_c = sum(p[0] for p in poly_constraint)/len(poly_constraint)
        lon_c = sum(p[1] for p in poly_constraint)/len(poly_constraint)
        base_lat, base_lon = random_point_in_convex_polygon(poly_constraint, (lat_c, lon_c))
    elif circle_constraint:
        (c_lat, c_lon), r_m = circle_constraint
        base_lat, base_lon = random_point_in_circle(c_lat, c_lon, r_m * 0.6)
    else:
        c_lat = random.uniform(-60.0, 60.0)
        c_lon = random.uniform(-180.0, 180.0)
        base_lat, base_lon = c_lat, c_lon

    home_alt = random_altitude(vehicle, alt_min, alt_max)
    home = [base_lat, base_lon, home_alt]

    # items count
    n_items = random.randint(min_items, max_items)
    items: List[dict] = []
    did = 1

    # helpers
    def step_within(lat0, lon0, smin, smax):
        nonlocal poly_constraint, circle_constraint
        if poly_constraint:
            lat, lon = choose_step_within_polygon(lat0, lon0, smin, smax, poly_constraint, (base_lat, base_lon))
            return lat, lon
        elif circle_constraint:
            (cc_lat, cc_lon), rr = circle_constraint
            for _ in range(20):
                step_m = random.uniform(smin, smax)
                theta = random.uniform(0.0, 360.0)
                dx = step_m * math.cos(math.radians(theta))
                dy = step_m * math.sin(math.radians(theta))
                cand_lat, cand_lon = offset_latlon(lat0, lon0, dx, dy)
                if approx_distance_m(cc_lat, cc_lon, cand_lat, cand_lon) <= rr:
                    return cand_lat, cand_lon
            return confine_to_circle(cc_lat, cc_lon, lat0, lon0, rr)
        else:
            step_m = random.uniform(smin, smax)
            theta = random.uniform(0.0, 360.0)
            dx = step_m * math.cos(math.radians(theta))
            dy = step_m * math.sin(math.radians(theta))
            return offset_latlon(lat0, lon0, dx, dy)

    def build_polygon_within(scale: float, verts: int) -> List[Tuple[float,float]]:
        if poly_constraint:
            # shrink polygon around its centroid
            lat_c = sum(p[0] for p in poly_constraint)/len(poly_constraint)
            lon_c = sum(p[1] for p in poly_constraint)/len(poly_constraint)
            # approximate radius from first vertex
            r0 = approx_distance_m(lat_c, lon_c, poly_constraint[0][0], poly_constraint[0][1])
            r = max(20.0, r0 * scale)
            return regular_convex_polygon(lat_c, lon_c, r, max(4, verts))
        elif circle_constraint:
            (cc_lat, cc_lon), rr = circle_constraint
            return regular_convex_polygon(cc_lat, cc_lon, rr * scale, max(4, verts))
        else:
            return regular_convex_polygon(base_lat, base_lon, 300.0 * scale, max(4, verts))

    # TAKEOFF
    t_alt = random_altitude(vehicle, alt_min, alt_max)
    t_lat, t_lon = step_within(base_lat, base_lon, 20.0, 200.0)
    items.append(simple_item(MAV_CMD_NAV_TAKEOFF, did, frame, t_lat, t_lon, t_alt)); did += 1

    # Insert up to N complex items at random positions
    def maybe_insert_complex_items(max_inserts: int):
        nonlocal items
        inserts = random.randint(0, max_inserts)
        for _ in range(inserts):
            didx = random.randint(1, max(1, len(items)))
            # decide candidates by enable flags and probs
            choices = []
            if enable_survey and random.random() < survey_prob:
                choices.append("survey")
            if enable_corridor and random.random() < corridor_prob:
                choices.append("corridor")
            if enable_structure and random.random() < structure_prob:
                choices.append("structure")
            if not choices:
                continue
            kind = random.choice(choices)

            # helpers to pick from ranges
            def pick_vertices_rng(rng: Tuple[int,int], min_allowed: int, max_allowed: int = 50) -> int:
                lo, hi = rng
                lo = int(clamp(lo, min_allowed, max_allowed))
                hi = int(clamp(hi, lo, max_allowed))
                return random.randint(lo, hi)

            def pick_legs_rng(rng: Tuple[int,int]) -> int:
                lo, hi = rng
                lo = max(2, int(lo))
                hi = max(lo, int(hi))
                return random.randint(lo, hi)

            def pick_width_rng(rng: Tuple[float,float]) -> float:
                lo, hi = rng
                lo = max(1.0, float(lo))
                hi = max(lo, float(hi))
                return random.uniform(lo, hi)

            if kind == "survey":
                local_vertices = pick_vertices_rng(survey_vertices_rng, 4)
                poly = build_polygon_within(scale=0.6, verts=local_vertices)
                items.insert(didx, complex_survey(poly, alt_min, alt_max))
            elif kind == "corridor":
                local_legs = pick_legs_rng(corridor_legs_rng)
                local_width = pick_width_rng(corridor_width_rng_m)
                # build polyline inside constraint
                if poly_constraint:
                    start = random_point_in_convex_polygon(poly_constraint, (base_lat, base_lon))
                elif circle_constraint:
                    (cc_lat, cc_lon), rr = circle_constraint
                    start = random_point_in_circle(cc_lat, cc_lon, rr*0.7)
                else:
                    start = (base_lat, base_lon)
                polyline: List[Tuple[float,float]] = [start]
                cur = start
                for _ in range(local_legs-1):
                    cur = step_within(cur[0], cur[1], 80.0, 400.0)
                    polyline.append(cur)
                items.insert(didx, complex_corridor(polyline, alt_min, alt_max, local_width))
            else:  # structure
                local_vertices = pick_vertices_rng(structure_vertices_rng, 4)
                poly = build_polygon_within(scale=0.3, verts=local_vertices)
                items.insert(didx, complex_structure(poly, alt_min, alt_max))

    maybe_insert_complex_items(max_complex)

    # middle path (simple items)
    last_lat, last_lon, last_alt = t_lat, t_lon, t_alt
    for _ in range(max(0, n_items - 2)):
        lat, lon = step_within(last_lat, last_lon, 50.0, 400.0)
        alt = clamp(last_alt + random.uniform(-15.0, 25.0), alt_min, alt_max)
        cmd = random.choice([MAV_CMD_NAV_WAYPOINT, MAV_CMD_NAV_WAYPOINT, MAV_CMD_NAV_LOITER_TIME])
        items.append(simple_item(cmd, did, frame, lat, lon, alt)); did += 1
        last_lat, last_lon, last_alt = lat, lon, alt

    # LAND
    l_lat, l_lon = step_within(last_lat, last_lon, 30.0, 200.0)
    l_alt = clamp(last_alt * 0.5, 0.0, min(100.0, alt_max))
    items.append(simple_item(MAV_CMD_NAV_LAND, did, frame, l_lat, l_lon, l_alt)); did += 1

    mission = {
        "version": 2,
        "firmwareType": firmware,
        "vehicleType": vehicle,
        "cruiseSpeed": cruise,
        "hoverSpeed": hover,
        "plannedHomePosition": home,
        "globalPlanAltitudeMode": global_alt_mode,
        "items": items,
    }

    # geoFence
    geoFence = {"circles": [], "polygons": [], "version": 2}
    if fence_type == "polygon" and fence_poly:
        geoFence["polygons"].append({"polygon": [[lat, lon] for (lat,lon) in fence_poly], "inclusion": True})
    elif fence_type == "circle" and fence_center and fence_radius_m:
        approx = regular_convex_polygon(fence_center[0], fence_center[1], fence_radius_m, 36, jitter_ratio=0.0)
        geoFence["polygons"].append({"polygon": [[lat, lon] for (lat,lon) in approx], "inclusion": True})

    return mission, geoFence


def make_plan_dict(**kw) -> dict:
    mission, geoFence = make_random_mission(**kw)
    plan = {
        "fileType": "Plan",
        "groundStation": "QGroundControl",
        "version": 1,
        "mission": mission,
        "geoFence": geoFence,
        "rallyPoints": {"points": [], "version": 2},
    }
    return plan

# --------------------------- CLI --------------------------------------------

def parse_args():
    ap = argparse.ArgumentParser(description="Random QGC .plan generator with region/geofence and ComplexItems")
    ap.add_argument("count", type=int, nargs="?", default=1, help="생성할 .plan 개수 (기본 1)")
    ap.add_argument("--outdir", "-o", type=Path, default=Path("."), help="출력 폴더")
    ap.add_argument("--seed", type=int, default=None, help="난수 시드(재현성)")
    ap.add_argument("--min-items", type=int, default=5, help="미션 최소 아이템 수(>=3 권장)")
    ap.add_argument("--max-items", type=int, default=18, help="미션 최대 아이템 수")

    # Altitude/Speed ranges
    ap.add_argument("--alt-min", type=float, default=20.0, help="아이템 고도 최소(m)")
    ap.add_argument("--alt-max", type=float, default=180.0, help="아이템 고도 최대(m)")
    ap.add_argument("--cruise-min", type=float, default=5.0, help="크루즈 속도 최소(m/s)")
    ap.add_argument("--cruise-max", type=float, default=25.0, help="크루즈 속도 최대(m/s)")
    ap.add_argument("--hover-min", type=float, default=3.0, help="호버 속도 최소(m/s)")
    ap.add_argument("--hover-max", type=float, default=12.0, help="호버 속도 최대(m/s)")

    # Region constraint (circle)
    ap.add_argument("--region", nargs=2, type=float, metavar=("LAT", "LON"), help="경로 중심 위경도")
    ap.add_argument("--radius-km", type=float, default=None, help="--region 반경(km); 미지정시 2km")

    # Geofence constraint
    ap.add_argument("--fence-type", choices=["none", "circle", "polygon"], default="none",
                    help="지오펜스 형태 (경로 생성도 이 영역으로 강제)")
    ap.add_argument("--fence-radius-km", type=float, default=None, help="지오펜스 반경(km): circle 또는 polygon 외접 반경")
    ap.add_argument("--fence-vertices", type=int, default=6, help="polygon 정점 수(3~24)")

    # ComplexItems — enable/prob
    ap.add_argument("--enable-survey", action="store_true", help="Survey ComplexItem 랜덤 삽입 허용")
    ap.add_argument("--survey-prob", type=float, default=0.35, help="Survey 삽입 확률 (0~1)")

    ap.add_argument("--enable-corridor", action="store_true", help="CorridorScan ComplexItem 랜덤 삽입 허용")
    ap.add_argument("--corridor-prob", type=float, default=0.25, help="Corridor 삽입 확률 (0~1)")

    ap.add_argument("--enable-structure", action="store_true", help="StructureScan ComplexItem 랜덤 삽입 허용")
    ap.add_argument("--structure-prob", type=float, default=0.25, help="StructureScan 삽입 확률 (0~1)")

    ap.add_argument("--max-complex", type=int, default=2, help="한 미션에 삽입할 ComplexItem 최대 개수")

    # ComplexItems — 난수화 범위(최소/최대)
    ap.add_argument("--survey-vertices-min", type=int, default=None, help="Survey 정점 최소(>=4)")
    ap.add_argument("--survey-vertices-max", type=int, default=None, help="Survey 정점 최대")

    ap.add_argument("--structure-vertices-min", type=int, default=None, help="Structure 정점 최소(>=4)")
    ap.add_argument("--structure-vertices-max", type=int, default=None, help="Structure 정점 최대")

    ap.add_argument("--corridor-legs-min", type=int, default=None, help="Corridor 포인트 최소(>=2)")
    ap.add_argument("--corridor-legs-max", type=int, default=None, help="Corridor 포인트 최대")

    ap.add_argument("--corridor-width-min-m", type=float, default=None, help="Corridor 폭 최소(m)")
    ap.add_argument("--corridor-width-max-m", type=float, default=None, help="Corridor 폭 최대(m)")

    return ap.parse_args()


def main():
    args = parse_args()

    n = max(1, int(args.count))
    outdir: Path = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    if args.seed is not None:
        random.seed(args.seed)

    min_items = max(3, int(args.min_items))
    max_items = max(min_items, int(args.max_items))

    alt_min = float(args.alt_min)
    alt_max = max(alt_min, float(args.alt_max))

    cruise_min = float(args.cruise_min)
    cruise_max = max(cruise_min, float(args.cruise_max))
    hover_min = float(args.hover_min)
    hover_max = max(hover_min, float(args.hover_max))

    # Region normalize
    region_center = None
    region_radius_km = None
    if args.region:
        lat, lon = float(args.region[0]), float(args.region[1])
        lat = clamp(lat, -85.0, 85.0)
        lon = ((lon + 180.0) % 360.0) - 180.0
        region_center = (lat, lon)
        region_radius_km = float(args.radius_km) if args.radius_km is not None else 2.0
        region_radius_km = max(0.05, region_radius_km)  # >=50m

    # Geofence build (also used to constrain path)
    fence_type = args.fence_type
    fence_poly = None
    fence_center = None
    fence_radius_m = None

    if fence_type != "none":
        if region_center:
            c_lat, c_lon = region_center
            r_km = args.fence_radius_km if args.fence_radius_km is not None else (region_radius_km or 2.0)
        else:
            c_lat = random.uniform(-60.0, 60.0)
            c_lon = random.uniform(-180.0, 180.0)
            r_km = args.fence_radius_km if args.fence_radius_km is not None else 2.0
        r_km = max(0.05, float(r_km))
        fence_center = (c_lat, c_lon)
        fence_radius_m = r_km * 1000.0

        if fence_type == "polygon":
            verts = clamp(int(args.fence_vertices), 3, 24)
            fence_poly = regular_convex_polygon(c_lat, c_lon, fence_radius_m, verts)

    # ---- Ranges for ComplexItems (per-insert randomization) ----
    SURVEY_VERTICES_DEF = 5
    STRUCTURE_VERTICES_DEF = 5
    CORRIDOR_LEGS_DEF = 3
    CORRIDOR_WIDTH_DEF = 40.0

    def mk_int_rng(base: int, mn_opt: Optional[int], mx_opt: Optional[int], lo: int, hi: int) -> Tuple[int,int]:
        if mn_opt is None and mx_opt is None:
            b = int(clamp(base, lo, hi))
            return (b, b)
        mn = int(clamp(mn_opt if mn_opt is not None else base, lo, hi))
        mx = int(clamp(mx_opt if mx_opt is not None else base, mn, hi))
        return (mn, mx)

    def mk_float_rng(base: float, mn_opt: Optional[float], mx_opt: Optional[float], lo: float, hi: float) -> Tuple[float,float]:
        if mn_opt is None and mx_opt is None:
            b = float(clamp(base, lo, hi))
            return (b, b)
        mn = float(clamp(mn_opt if mn_opt is not None else base, lo, hi))
        mx = float(clamp(mx_opt if mx_opt is not None else base, mn, hi))
        return (mn, mx)

    survey_vertices_rng = mk_int_rng(SURVEY_VERTICES_DEF, args.survey_vertices_min, args.survey_vertices_max, 4, 50)
    structure_vertices_rng = mk_int_rng(STRUCTURE_VERTICES_DEF, args.structure_vertices_min, args.structure_vertices_max, 4, 50)
    corridor_legs_rng = mk_int_rng(CORRIDOR_LEGS_DEF, args.corridor_legs_min, args.corridor_legs_max, 2, 50)
    corridor_width_rng_m = mk_float_rng(CORRIDOR_WIDTH_DEF, args.corridor_width_min_m, args.corridor_width_max_m, 1.0, 500.0)

    for i in range(1, n + 1):
        plan = make_plan_dict(
            min_items=min_items,
            max_items=max_items,
            region_center=region_center,
            region_radius_km=region_radius_km,
            fence_type=fence_type,
            fence_poly=fence_poly,
            fence_center=fence_center,
            fence_radius_m=fence_radius_m,
            alt_min=alt_min,
            alt_max=alt_max,
            cruise_min=cruise_min,
            cruise_max=cruise_max,
            hover_min=hover_min,
            hover_max=hover_max,
            enable_survey=bool(args.enable_survey),
            survey_prob=float(args.survey_prob),
            enable_corridor=bool(args.enable_corridor),
            corridor_prob=float(args.corridor_prob),
            enable_structure=bool(args.enable_structure),
            structure_prob=float(args.structure_prob),
            max_complex=int(args.max_complex),
            survey_vertices_rng=survey_vertices_rng,
            structure_vertices_rng=structure_vertices_rng,
            corridor_legs_rng=corridor_legs_rng,
            corridor_width_rng_m=corridor_width_rng_m,
        )
        outpath = outdir / f"{i}.plan"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

