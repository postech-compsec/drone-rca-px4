#!/usr/bin/env python3
# qgc_plan_random_gen_simple.py
# python3 qgc_plan_random_gen.py 25 --seed 42 --outdir ./plans --min-items 5 --max-items 20
# count : 만들 .plan 파일의 개수
# -o, --outdir <경로> : 출력 폴더. 없으면 생성. 기본값은 현재 작업 디렉터리(CWD).
# --seed <정수> : 난수 시드(재현성). 같은 시드로 실행하면 동일한 경로/좌표/속성의 계획 생성. 지정하지 않으면 매번 달라짐.
# --min-items <정수> / --max-items <정수> : 각 미션의 아이템(명령) 개수 범위를 지정. TAKEOFF/WAYPOINT/LOITER_TIME/LAND 같은 미션 단계 수의 하한·상한. 권장: 최소 3 이상(이륙·중간·착륙 구조 확보). 기본: min=5, max=18
import argparse, json, math, os, random
from pathlib import Path
from typing import List, Tuple

# ---- Enumerations (subset; QGC/MAVLink 호환 숫자) ---------------------------
MAV_AUTOPILOT_CHOICES = [3, 12]  # 3: ArduPilot, 12: PX4
MAV_TYPE_CHOICES = [1, 2]        # 1: FIXED_WING, 2: QUADROTOR (간단히 두 가지)
MAV_FRAME_GLOBAL = 0
MAV_FRAME_GLOBAL_RELATIVE_ALT = 3

# MAV_CMD (네비게이션 계열 위주: 좌표가 필요한 것만 사용해 호환성↑)
MAV_CMD_NAV_WAYPOINT   = 16
MAV_CMD_NAV_LOITER_TIME= 19
MAV_CMD_NAV_LAND       = 21
MAV_CMD_NAV_TAKEOFF    = 22

# ---- Helpers ----------------------------------------------------------------
def randf(a: float, b: float) -> float:
    return random.uniform(a, b)

def randint(a: int, b: int) -> int:
    return random.randint(a, b)

def choose(seq):
    return random.choice(seq)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def offset_latlon(lat: float, lon: float, dx_m: float, dy_m: float) -> Tuple[float, float]:
    """현재 위경도(lat, lon)에서 동쪽 dx_m, 북쪽 dy_m 만큼 이동시킨 위경도 반환."""
    dlat = dy_m / 111_320.0
    dlon = dx_m / (111_320.0 * math.cos(math.radians(lat)) or 1e-6)
    return lat + dlat, lon + dlon

def random_center() -> Tuple[float, float]:
    # 극 지역은 피해서 로드 지형 문제 최소화
    lat = randf(-60.0, 60.0)
    lon = randf(-180.0, 180.0)
    return lat, lon

def random_altitude(vehicle_type: int) -> float:
    if vehicle_type == 1:  # FIXED_WING: 보통 더 높이
        return randf(60.0, 250.0)
    else:                  # QUADROTOR
        return randf(20.0, 120.0)

def random_speed(vehicle_type: int) -> Tuple[float, float]:
    if vehicle_type == 1:  # FIXED_WING
        return randf(15.0, 40.0), None  # cruiseSpeed, hoverSpeed(None)
    else:                  # QUADROTOR
        return randf(5.0, 18.0), randf(3.0, 12.0)  # cruiseSpeed, hoverSpeed

def waypoint_params(lat, lon, alt) -> List[float]:
    hold = randf(0.0, 10.0)           # sec
    accept_radius = randf(1.0, 20.0)  # m
    pass_through = randint(0, 1)      # 0=stop,1=pass-through
    yaw = randf(-180.0, 180.0)        # deg
    return [hold, accept_radius, pass_through, yaw, lat, lon, alt]

def takeoff_params(lat, lon, alt) -> List[float]:
    pitch = randf(5.0, 15.0)          # deg (FW 기준), 멀티콥터는 무시됨
    _empty = 0.0
    yaw = randf(-180.0, 180.0)
    return [pitch, _empty, _empty, yaw, lat, lon, alt]

def loiter_time_params(lat, lon, alt) -> List[float]:
    time_s = randf(5.0, 120.0)
    radius = randf(10.0, 80.0)  # 일부 FW에 의미 있음, 멀티콥터는 무시 가능
    _zero = 0.0
    return [time_s, radius, _zero, _zero, lat, lon, alt]

def land_params(lat, lon, alt) -> List[float]:
    # alt는 최종 접근 고도(상대/절대는 프레임/모드에 따름)
    abort_alt = randf(10.0, 60.0)  # 일부 펌웨어에서 사용
    _zero = 0.0
    return [abort_alt, _zero, _zero, _zero, lat, lon, alt]

def simple_item(cmd: int, did: int, frame: int, lat: float, lon: float, alt: float) -> dict:
    # AltitudeMode: 0/1 정도로 랜덤 (Absolute/Relative 개념; QGC 내부 enum)
    altitude_mode = randint(0, 1)
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

def make_random_mission() -> dict:
    firmware = choose(MAV_AUTOPILOT_CHOICES)
    vehicle  = choose(MAV_TYPE_CHOICES)
    cruise, hover = random_speed(vehicle)
    frame = choose([MAV_FRAME_GLOBAL_RELATIVE_ALT, MAV_FRAME_GLOBAL])
    global_alt_mode = randint(0, 3)  # QGC가 사용하는 전역 고도 모드(대략적)

    # 지리적 중심 및 홈
    base_lat, base_lon = random_center()
    home_alt = random_altitude(vehicle)
    home = [base_lat, base_lon, home_alt]

    # 아이템 개수
    n_items = randint(5, 18)
    items = []
    did = 1

    # TAKEOFF (첫 아이템로 넣되, 고정익/멀티콥터 모두 허용)
    t_alt = random_altitude(vehicle)
    t_lat, t_lon = offset_latlon(base_lat, base_lon, randf(-200, 200), randf(-200, 200))
    items.append(simple_item(MAV_CMD_NAV_TAKEOFF, did, frame, t_lat, t_lon, t_alt)); did += 1

    # 중간 경로: WAYPOINT/LOITER_TIME 섞기
    last_lat, last_lon, last_alt = t_lat, t_lon, t_alt
    for _ in range(n_items - 2):  # 마지막 LAND를 남겨두기 위해 -2
        # 이동 벡터 (50~400m 랜덤 워크)
        step_m = randf(50.0, 400.0)
        turn = randf(0, 360)
        dx = step_m * math.cos(math.radians(turn))
        dy = step_m * math.sin(math.radians(turn))
        lat, lon = offset_latlon(last_lat, last_lon, dx, dy)

        # 고도 살짝 변동
        alt = clamp(last_alt + randf(-15.0, 25.0), 10.0, 400.0)

        cmd = choose([MAV_CMD_NAV_WAYPOINT, MAV_CMD_NAV_WAYPOINT,
                      MAV_CMD_NAV_LOITER_TIME])  # WP 비중↑
        items.append(simple_item(cmd, did, frame, lat, lon, alt)); did += 1

        last_lat, last_lon, last_alt = lat, lon, alt

    # LAND (경로 끝 근처)
    l_lat, l_lon = offset_latlon(last_lat, last_lon, randf(-150, 150), randf(-150, 150))
    l_alt = clamp(last_alt * 0.5, 0.0, 100.0)
    items.append(simple_item(MAV_CMD_NAV_LAND, did, frame, l_lat, l_lon, l_alt)); did += 1

    mission = {
        "version": 2,
        "firmwareType": firmware,
        "vehicleType": vehicle,
        "cruiseSpeed": cruise,
        "hoverSpeed": hover if hover is not None else 0.0,
        "plannedHomePosition": home,               # [lat, lon, alt]
        "globalPlanAltitudeMode": global_alt_mode,
        "items": items,
    }
    return mission

def make_plan_dict() -> dict:
    mission = make_random_mission()
    plan = {
        "fileType": "Plan",
        "groundStation": "QGroundControl",
        "version": 1,
        "mission": mission,
        # 지오펜스/랠리포인트는 스펙상 선택. 빈 컨테이너로 두되 version 포함.
        "geoFence": {"circles": [], "polygons": [], "version": 2},
        "rallyPoints": {"points": [], "version": 2},
    }
    return plan

# ---- CLI --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Random QGC .plan generator")
    ap.add_argument("count", nargs="?", type=int, help="생성할 .plan 개수 (기본 1)")
    # ap.add_argument("--count", "-c", type=int, help="생성할 .plan 개수")
    ap.add_argument("--outdir", "-o", type=Path, default=Path("."), help="출력 폴더")
    ap.add_argument("--seed", type=int, default=None, help="난수 시드 (선택)")
    ap.add_argument("--min-items", type=int, default=5, help="미션 최소 아이템 수(>=3)")
    ap.add_argument("--max-items", type=int, default=18, help="미션 최대 아이템 수")
    args = ap.parse_args()

    n = args.count if args.count is not None else (args.count if args.count else 1)
    if isinstance(args.count, int):
        n = args.count
    elif isinstance(args.count, type(None)) and args.count is None:
        # positional
        n = args.count if args.count else (args.count or 1)
    n = args.count or n  # normalize
    if not isinstance(n, int) or n <= 0:
        n = 1

    if args.seed is not None:
        random.seed(args.seed)

    # bounds sanity (미션 길이 전역 설정; 파일별 다양성을 원하면 여기 로직 확장)
    global randint
    original_randint = randint
    def bounded_randint(a, b):
        lo = max(a, args.min_items)
        hi = min(b, args.max_items)
        if lo > hi: lo, hi = hi, lo
        return random.randint(lo, hi)
    # monkey patch 로 n_items 범위를 조절
    globals()['randint'] = bounded_randint

    args.outdir.mkdir(parents=True, exist_ok=True)

    for i in range(1, n + 1):
        plan = make_plan_dict()
        outpath = args.outdir / f"{i}.plan"
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
    # 복구
    globals()['randint'] = original_randint

if __name__ == "__main__":
    main()

