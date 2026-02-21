#!/usr/bin/env python3
"""
Run a QGroundControl .plan mission on PX4 SITL using MAVSDK-Python (no GUI).

Flow:
  1) Connect to PX4 SITL (default: udpin://0.0.0.0:14540)
  2) Import QGC .plan into MissionRaw (from string if available, otherwise from file path)
  3) Upload mission/geofence/rally (if present)
  4) Arm + Start mission
  5) Monitor mission progress until completion (or timeout)
  6) Optional end action (none/land/rtl)

Notes:
- PX4 SITL "external developer APIs" default to UDP remote port 14540. Multi-vehicle uses 14540..14549.
- QGC .plan complex items: importer supports Waypoints/Survey, not all complex items (e.g., Structure Scan).
"""

import argparse
import asyncio
import logging
import signal
from pathlib import Path
from typing import Optional
import sys

try:
    from mavsdk import System
except Exception as e:
    print("[fatal] Failed to import mavsdk properly.")
    print(f"python: {sys.executable}")
    print(f"error : {type(e).__name__}: {e}")
    print("traceback:")
    traceback.print_exc()
    sys.exit(1)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--plan",
        required=True,
        help="Path to QGroundControl .plan file (JSON).",
    )
    p.add_argument(
        "--system-address",
        default="udpin://0.0.0.0:14540",
        help='MAVSDK system_address (default: "udpin://0.0.0.0:14540").',
    )
    p.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip waiting for global/home position OK (useful if your SITL setup doesn't provide it).",
    )
    p.add_argument(
        "--health-timeout-s",
        type=float,
        default=60.0,
        help="Timeout seconds for health check (default: 60).",
    )
    p.add_argument(
        "--arm",
        action="store_true",
        default=True,
        help="Arm before starting mission (default: enabled).",
    )
    p.add_argument(
        "--no-arm",
        action="store_false",
        dest="arm",
        help="Do NOT arm (assume already armed).",
    )
    p.add_argument(
        "--start",
        action="store_true",
        default=True,
        help="Start mission after upload (default: enabled).",
    )
    p.add_argument(
        "--no-start",
        action="store_false",
        dest="start",
        help="Upload only; do NOT start mission.",
    )
    p.add_argument(
        "--clear-first",
        action="store_true",
        help="Try to clear existing mission/geofence/rally before upload (best-effort).",
    )
    p.add_argument(
        "--end-action",
        choices=["none", "land", "rtl"],
        default="none",
        help="Action to execute after mission completion (default: none).",
    )
    p.add_argument(
        "--mission-timeout-s",
        type=float,
        default=0.0,
        help="Timeout seconds waiting for mission completion (0 = no timeout, default: 0).",
    )
    p.add_argument(
        "--verbose-status",
        action="store_true",
        help="Print STATUSTEXT messages from the vehicle.",
    )
    p.add_argument(
        "--telemetry-interval",
        type=float,
        default=2.0,
        help="Print periodic telemetry every N seconds (0 to disable). default: 2.0",
    )
    p.add_argument("--skip-geofence", action="store_true", help="Do not upload geofence from .plan")
    p.add_argument("--skip-rally", action="store_true", help="Do not upload rally points from .plan")
    return p.parse_args()


async def _wait_connected(drone: System) -> None:
    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("-- Connected")
            return


async def _wait_health_ok(drone: System, timeout_s: float) -> None:
    print("Waiting for global position estimate (health) ...")
    async def _wait():
        async for health in drone.telemetry.health():
            if health.is_global_position_ok and health.is_home_position_ok:
                print("-- Global position & home position OK")
                return

    await asyncio.wait_for(_wait(), timeout=timeout_s)


async def _print_status_text(drone: System, stop_evt: asyncio.Event) -> None:
    try:
        async for st in drone.telemetry.status_text():
            print(f"STATUSTEXT: {st.type}: {st.text}")
            if stop_evt.is_set():
                return
    except asyncio.CancelledError:
        return


async def _import_plan_mission_raw(drone: System, plan_path: Path):
    """
    Prefer import_qgroundcontrol_mission_from_string (robust wrt backend cwd),
    fall back to import_qgroundcontrol_mission(path) if needed.
    """
    plan_text = plan_path.read_text(encoding="utf-8")

    mission_raw = drone.mission_raw

    # Prefer from_string if available
    if hasattr(mission_raw, "import_qgroundcontrol_mission_from_string"):
        return await mission_raw.import_qgroundcontrol_mission_from_string(plan_text)

    # Fallback: backend reads file itself
    return await mission_raw.import_qgroundcontrol_mission(str(plan_path))


async def _best_effort_clear(drone: System) -> None:
    """
    Clear mission/geofence/rally if APIs exist. Not all versions expose all clears.
    """
    mr = drone.mission_raw
    # MissionRaw clears
    for fn_name in ("clear_mission", "clear_geofence", "clear_rally_points", "clear_rallypoints"):
        if hasattr(mr, fn_name):
            try:
                await getattr(mr, fn_name)()
                print(f"-- Cleared via mission_raw.{fn_name}()")
            except Exception as e:
                print(f"-- (warn) mission_raw.{fn_name}() failed: {e}")

    # Mission plugin clear (if user later starts via mission plugin)
    if hasattr(drone.mission, "clear_mission"):
        try:
            await drone.mission.clear_mission()
            print("-- Cleared via mission.clear_mission()")
        except Exception as e:
            print(f"-- (warn) mission.clear_mission() failed: {e}")


async def _start_mission_best_effort(drone: System) -> None:
    """
    Prefer MissionRaw.start_mission(), fall back to Mission.start_mission()
    if MissionRaw doesn't exist in the installed version.
    """
    if hasattr(drone.mission_raw, "start_mission"):
        await drone.mission_raw.start_mission()
        return
    await drone.mission.start_mission()


async def _mission_progress_stream(drone: System):
    """
    Prefer MissionRaw.mission_progress(), else Mission.mission_progress()
    """
    if hasattr(drone.mission_raw, "mission_progress"):
        async for p in drone.mission_raw.mission_progress():
            yield p
        return
    async for p in drone.mission.mission_progress():
        yield p


async def _print_periodic_state(drone: System, stop_evt: asyncio.Event, interval_s: float) -> None:
    """
    Periodically print: armed, in_air, flight_mode, position/alt, ground speed.
    Uses async generators carefully (each stream consumed by a single task).
    """
    if interval_s <= 0:
        return

    armed = None
    in_air = None
    flight_mode = None
    lat = lon = rel_alt_m = abs_alt_m = None
    ground_speed_ms = None

    async def watch_armed():
        nonlocal armed
        async for a in drone.telemetry.armed():
            armed = a
            if stop_evt.is_set():
                return

    async def watch_in_air():
        nonlocal in_air
        async for ia in drone.telemetry.in_air():
            in_air = ia
            if stop_evt.is_set():
                return

    async def watch_flight_mode():
        nonlocal flight_mode
        async for fm in drone.telemetry.flight_mode():
            flight_mode = fm
            if stop_evt.is_set():
                return

    async def watch_position():
        nonlocal lat, lon, rel_alt_m, abs_alt_m
        async for pos in drone.telemetry.position():
            lat = pos.latitude_deg
            lon = pos.longitude_deg
            abs_alt_m = pos.absolute_altitude_m
            rel_alt_m = pos.relative_altitude_m
            if stop_evt.is_set():
                return

    async def watch_gs():
        nonlocal ground_speed_ms
        async for gs in drone.telemetry.ground_speed_ned():
            # gs has north_m_s/east_m_s/down_m_s; ground speed magnitude:
            ground_speed_ms = (gs.north_m_s**2 + gs.east_m_s**2) ** 0.5
            if stop_evt.is_set():
                return

    tasks = [
        asyncio.create_task(watch_armed()),
        asyncio.create_task(watch_in_air()),
        asyncio.create_task(watch_flight_mode()),
        asyncio.create_task(watch_position()),
        asyncio.create_task(watch_gs()),
    ]

    try:
        tick = 0
        while not stop_evt.is_set():
            tick += 1
            # 간단한 한 줄 heartbeat
            msg = (
                f"[hb {tick}] armed={armed} in_air={in_air} mode={flight_mode} "
                f"lat={lat:.6f} lon={lon:.6f} rel_alt={rel_alt_m:.1f}m "
                f"gs={ground_speed_ms:.1f}m/s"
                if (lat is not None and lon is not None and rel_alt_m is not None and ground_speed_ms is not None)
                else f"[hb {tick}] armed={armed} in_air={in_air} mode={flight_mode}"
            )
            #print(msg, flush=True)
            await asyncio.sleep(interval_s)
    finally:
        for t in tasks:
            t.cancel()


async def _run(args: argparse.Namespace) -> int:
    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.exists():
        print(f"[ERROR] plan file not found: {plan_path}")
        return 1

    # Enable INFO logs if you want (matches MAVSDK examples style)
    logging.basicConfig(level=logging.INFO)

    drone = System()
    await drone.connect(system_address=args.system_address)

    await _wait_connected(drone)

    stop_evt = asyncio.Event()
    status_task: Optional[asyncio.Task] = None
    if args.verbose_status:
        status_task = asyncio.create_task(_print_status_text(drone, stop_evt))
    telemetry_task: Optional[asyncio.Task] = None
    if args.telemetry_interval and args.telemetry_interval > 0:
        telemetry_task = asyncio.create_task(
            _print_periodic_state(drone, stop_evt, args.telemetry_interval)
        )

    # Health check (for SITL this usually becomes OK)
    if not args.skip_health_check:
        try:
            await _wait_health_ok(drone, timeout_s=args.health_timeout_s)
        except asyncio.TimeoutError:
            print(f"[WARN] Health check timed out after {args.health_timeout_s}s. "
                  f"Continue anyway (or use --skip-health-check).")

    if args.clear_first:
        await _best_effort_clear(drone)

    # Import .plan
    print(f"-- Importing .plan: {plan_path.name}")
    try:
        import_data = await _import_plan_mission_raw(drone, plan_path)
    except Exception as e:
        print(f"[ERROR] Failed to import .plan: {e}")
        stop_evt.set()
        if status_task:
            status_task.cancel()
        if telemetry_task:
            telemetry_task.cancel()
        return 1

    mission_items = getattr(import_data, "mission_items", []) or []
    geofence_items = getattr(import_data, "geofence_items", []) or []
    rally_items = getattr(import_data, "rally_items", []) or []

    print(f"-- Import result: mission_items={len(mission_items)}, "
          f"geofence_items={len(geofence_items)}, rally_items={len(rally_items)}")

    # Upload
    try:
        if geofence_items and hasattr(drone.mission_raw, "upload_geofence") and not args.skip_geofence:
            print("-- Uploading geofence items (MissionRaw)...")
            await drone.mission_raw.upload_geofence(geofence_items)

        if rally_items and not args.skip_rally:
            # Some versions name it upload_rally_points
            if hasattr(drone.mission_raw, "upload_rally_points"):
                print("-- Uploading rally points (MissionRaw.upload_rally_points)...")
                await drone.mission_raw.upload_rally_points(rally_items)
            elif hasattr(drone.mission_raw, "upload_rallypoints"):
                print("-- Uploading rally points (MissionRaw.upload_rallypoints)...")
                await drone.mission_raw.upload_rallypoints(rally_items)

        print("-- Uploading mission items (MissionRaw)...")
        await drone.mission_raw.upload_mission(mission_items)
    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        stop_evt.set()
        if status_task:
            status_task.cancel()
        return 1

    # Arm
    if args.arm:
        try:
            print("-- Arming")
            await drone.action.arm()
        except Exception as e:
            print(f"[ERROR] Arming failed: {e}")
            stop_evt.set()
            if status_task:
                status_task.cancel()
            return 1

    # Start mission
    if args.start:
        try:
            print("-- Starting mission")
            await _start_mission_best_effort(drone)
        except Exception as e:
            print(f"[ERROR] Start mission failed: {e}")
            stop_evt.set()
            if status_task:
                status_task.cancel()
            return 1
    else:
        print("-- Upload only (no start). Done.")
        stop_evt.set()
        if status_task:
            status_task.cancel()
        return 0

    # Monitor mission progress
    print("-- Monitoring mission progress")
    done_evt = asyncio.Event()

    async def _monitor():
        last = None
        async for prog in _mission_progress_stream(drone):
            # prog has fields: current, total
            cur = getattr(prog, "current", None)
            tot = getattr(prog, "total", None)
            if (cur, tot) != last:
                print(f"   progress: {cur}/{tot}")
                last = (cur, tot)

            # Heuristic: finished when current == total and total > 0
            if tot is not None and tot > 0 and cur == tot:
                done_evt.set()
                return

    monitor_task = asyncio.create_task(_monitor())

    try:
        if args.mission_timeout_s and args.mission_timeout_s > 0:
            await asyncio.wait_for(done_evt.wait(), timeout=args.mission_timeout_s)
        else:
            await done_evt.wait()
        print("-- Mission completed (progress reached end)")
    except asyncio.TimeoutError:
        print(f"[ERROR] Mission timeout after {args.mission_timeout_s}s")
        monitor_task.cancel()
        stop_evt.set()
        if status_task:
            status_task.cancel()
        return 2
    finally:
        if not monitor_task.done():
            monitor_task.cancel()

    # Optional end action
    try:
        if args.end_action == "land":
            print("-- Landing")
            await drone.action.land()
        elif args.end_action == "rtl":
            if hasattr(drone.action, "return_to_launch"):
                print("-- Return to launch")
                await drone.action.return_to_launch()
            else:
                print("[WARN] return_to_launch() not available in this MAVSDK version")
    except Exception as e:
        print(f"[WARN] End action '{args.end_action}' failed: {e}")

    stop_evt.set()

    if status_task:
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass

    if telemetry_task:
        telemetry_task.cancel()
        try:
            await telemetry_task
        except asyncio.CancelledError:
            pass

    return 0


def main() -> None:
    args = _parse_args()

    stop_now = asyncio.Event()

    def _sig_handler(*_):
        stop_now.set()

    async def _entry():
        runner = asyncio.create_task(_run(args))
        stopper = asyncio.create_task(stop_now.wait())

        # signal handler는 Unix에서만 잘 됨. 실패해도 진행.
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, _sig_handler)
            loop.add_signal_handler(signal.SIGTERM, _sig_handler)
        except Exception:
            pass

        done, pending = await asyncio.wait({runner, stopper}, return_when=asyncio.FIRST_COMPLETED)

        if stopper in done and not runner.done():
            print("\n[INFO] Interrupted. Best-effort land...")
            try:
                # 여기서 drone 재연결/land는 선택사항. 필요 없으면 제거해도 됨.
                d = System()
                await d.connect(system_address=args.system_address)
                async for st in d.core.connection_state():
                    if st.is_connected:
                        break
                await d.action.land()
            except Exception:
                pass
            for t in pending:
                t.cancel()
            return 130

        for t in pending:
            t.cancel()
        return await runner

    raise SystemExit(asyncio.run(_entry()))


if __name__ == "__main__":
    main()
