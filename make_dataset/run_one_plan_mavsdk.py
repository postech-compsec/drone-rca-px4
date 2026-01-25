#!/usr/bin/env python3
"""
Run a single QGC .plan using MAVSDK (MissionRaw).

This script uploads mission items and starts the mission.
Complex items are not expanded; by default this is a hard error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

try:
    from mavsdk import System
    from mavsdk.mission_raw import MissionRawItem
except ImportError as exc:
    raise SystemExit("mavsdk is required (pip install mavsdk).") from exc


def _param(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def _coords_from_item(item: dict, params: List[Any]) -> Tuple[float, float, float]:
    if "coordinate" in item and item["coordinate"]:
        lat, lon, alt = item["coordinate"]
        return float(lat), float(lon), float(alt)
    if len(params) >= 7:
        return _param(params[4]), _param(params[5]), _param(params[6])
    return 0.0, 0.0, 0.0


@dataclass
class ParseResult:
    items: List[MissionRawItem]
    skipped_complex: int


def parse_plan(plan_path: Path, allow_skip_complex: bool) -> ParseResult:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    mission = data.get("mission", {})
    items = mission.get("items", [])

    out: List[MissionRawItem] = []
    skipped_complex = 0

    seq = 0
    for it in items:
        it_type = it.get("type")
        if it_type != "SimpleItem":
            if allow_skip_complex:
                skipped_complex += 1
                continue
            raise SystemExit(f"Complex item encountered in {plan_path}: {it_type}")

        params = it.get("params", [])
        lat, lon, alt = _coords_from_item(it, params)
        frame = int(it.get("frame", 3))
        command = int(it.get("command", 16))
        autocont = bool(it.get("autoContinue", True))

        out.append(
            MissionRawItem(
                seq=seq,
                frame=frame,
                command=command,
                current=1 if seq == 0 else 0,
                autocontinue=autocont,
                param1=_param(params[0]) if len(params) > 0 else 0.0,
                param2=_param(params[1]) if len(params) > 1 else 0.0,
                param3=_param(params[2]) if len(params) > 2 else 0.0,
                param4=_param(params[3]) if len(params) > 3 else 0.0,
                x=lat,
                y=lon,
                z=alt,
                mission_type=0,
            )
        )
        seq += 1

    if not out:
        raise SystemExit(f"No SimpleItem found in {plan_path}")

    return ParseResult(items=out, skipped_complex=skipped_complex)


async def _wait_for_connection(drone: System, timeout_s: float) -> None:
    async def _wait():
        async for state in drone.core.connection_state():
            if state.is_connected:
                return

    await asyncio.wait_for(_wait(), timeout=timeout_s)


async def _wait_for_mission(drone: System, timeout_s: float) -> None:
    async def _wait():
        async for progress in drone.mission_raw.mission_progress():
            if progress.current == progress.total and progress.total > 0:
                return

    await asyncio.wait_for(_wait(), timeout=timeout_s)


async def run_mission(args) -> int:
    parsed = parse_plan(args.plan, args.allow_skip_complex)
    if parsed.skipped_complex:
        print(f"[warn] skipped {parsed.skipped_complex} complex item(s)")

    drone = System()
    await drone.connect(system_address=f"udp://:{args.udp_port}")
    await _wait_for_connection(drone, args.connect_timeout)

    await drone.mission_raw.clear_mission()
    await drone.mission_raw.upload_mission(parsed.items)

    if not args.no_arm:
        await drone.action.arm()

    await drone.mission_raw.start_mission()
    await _wait_for_mission(drone, args.mission_timeout)
    return 0


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run a single QGC .plan using MAVSDK MissionRaw.")
    ap.add_argument("--plan", required=True, type=Path, help="Path to .plan file")
    ap.add_argument("--udp-port", type=int, default=14540, help="UDP port to connect to (default: 14540)")
    ap.add_argument("--allow-skip-complex", action="store_true", help="Skip ComplexItem entries instead of failing.")
    ap.add_argument("--no-arm", action="store_true", help="Do not arm before starting mission.")
    ap.add_argument("--connect-timeout", type=float, default=15.0, help="Seconds to wait for connection.")
    ap.add_argument("--mission-timeout", type=float, default=900.0, help="Seconds to wait for mission completion.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    try:
        rc = asyncio.run(run_mission(args))
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
