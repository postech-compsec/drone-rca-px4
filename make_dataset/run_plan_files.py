#!/usr/bin/env python3
"""
Batch-run QGroundControl plan files in deterministic order with retry & log handling.

- Runs plans sorted by directory then filename so you can resume from a failed plan.
- On failure: deletes the newest logs created by that run, then retries.
- After retries are exhausted: prints the failing plan path and exits non-zero.

Usage examples:
  python run_plan_files.py --command "./run_one_plan.sh {plan}"            # default ./plans
  python run_plan_files.py ./plans_extra --command "qgc_cli --plan {plan}"
  python run_plan_files.py --start-from plan_0005.plan --retries 2

Required:
  --command (or env QGC_PLAN_CMD) must be a shell snippet with {plan} placeholder.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Set

LOG_EXTS = {".ulg", ".ulog"}


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def sort_key(path: Path):
    return (path.parent.as_posix(), natural_key(path.name))


def list_plan_files(inputs: Sequence[Path]) -> List[Path]:
    files: Set[Path] = set()
    for p in inputs:
        if p.is_dir():
            files |= {f.resolve() for f in p.glob("*.plan")}
        elif p.suffix == ".plan":
            files.add(p.resolve())
    return sorted(files, key=sort_key)


def snapshot_logs(log_root: Path) -> Set[Path]:
    if not log_root.exists():
        return set()
    return {
        p.resolve()
        for p in log_root.rglob("*")
        if p.is_file() and p.suffix.lower() in LOG_EXTS
    }


def delete_logs(paths: Iterable[Path], log_root: Path) -> None:
    for p in paths:
        try:
            p.unlink()
        except FileNotFoundError:
            continue
        # Clean up empty date/time directories if possible
        parent = p.parent
        while parent != log_root and parent != parent.parent:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


@dataclass
class RunResult:
    success: bool
    new_logs: List[Path]
    returncode: int
    output: str


def run_single_plan(plan: Path, args) -> RunResult:
    cmd_template = args.command or os.environ.get("QGC_PLAN_CMD")
    if not cmd_template:
        raise SystemExit("No command provided. Use --command or set QGC_PLAN_CMD.")

    cmd = cmd_template.format(plan=str(plan), plan_name=plan.name, plan_stem=plan.stem)
    before = snapshot_logs(args.log_root)

    proc = subprocess.run(
        cmd if args.shell else shlex.split(cmd),
        shell=args.shell,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if args.post_sleep > 0:
        time.sleep(args.post_sleep)

    after = snapshot_logs(args.log_root)
    new_logs = sorted(after - before, key=sort_key)
    success = (proc.returncode == 0) and (new_logs or not args.require_log)

    return RunResult(success=success, new_logs=new_logs, returncode=proc.returncode, output=proc.stdout or "")


def parse_args() -> argparse.Namespace:
    default_plans = Path(__file__).resolve().parents[1] / "make_qgc_plan" / "ver2" / "plans"
    ap = argparse.ArgumentParser(description="Run multiple QGC .plan files with retries and log clean-up.")
    ap.add_argument(
        "targets",
        nargs="*",
        type=Path,
        default=[default_plans],
        help="Plan files or directories (default: ./plans)",
    )
    ap.add_argument(
        "--command",
        "-c",
        help="Command template to run a single plan. Use {plan}, {plan_name}, {plan_stem}.",
    )
    ap.add_argument("--log-root", type=Path, default=Path("build/px4_sitl_default/rootfs/log"), help="Root directory where .ulg/.ulog are written.")
    ap.add_argument("--start-from", type=str, default=None, help="Plan filename or path to resume from (matches basename if path not found).")
    ap.add_argument("--retries", type=int, default=3, help="Max attempts per plan (default: 3).")
    ap.add_argument("--post-sleep", type=float, default=0.0, help="Seconds to sleep after each run (default: 0).")
    ap.add_argument("--shell", action="store_true", help="Run command template through the shell.")
    ap.add_argument("--require-log", action=argparse.BooleanOptionalAction, default=True, help="Require new log file(s) for success (default: True).")
    ap.add_argument("--run-log-dir", type=Path, default=None, help="Optional dir to store stdout per plan.")
    return ap.parse_args()


def find_start_index(plans: List[Path], start_from: str | None) -> int:
    if not start_from:
        return 0
    target = Path(start_from)
    for idx, p in enumerate(plans):
        if p.resolve() == target.resolve() or p.name == target.name:
            return idx
    raise SystemExit(f"--start-from '{start_from}' not found in plan list.")


def main() -> None:
    args = parse_args()
    plans = list_plan_files(args.targets)
    if not plans:
        raise SystemExit("No .plan files found.")

    if args.run_log_dir:
        args.run_log_dir.mkdir(parents=True, exist_ok=True)

    start_idx = find_start_index(plans, args.start_from)
    for plan in plans[start_idx:]:
        attempt = 0
        while attempt < args.retries:
            attempt += 1
            res = run_single_plan(plan, args)

            if res.success:
                print(f"[ok] {plan} (attempt {attempt}, logs: {len(res.new_logs)})")
                if args.run_log_dir:
                    log_path = args.run_log_dir / f"{plan.stem}.log"
                    log_path.write_text(res.output, encoding="utf-8")
                break

            # failure path
            if args.run_log_dir:
                log_path = args.run_log_dir / f"{plan.stem}.fail.{attempt}.log"
                log_path.write_text(res.output, encoding="utf-8")

            if res.new_logs:
                delete_logs(res.new_logs, args.log_root)
            print(f"[warn] failed {plan} attempt {attempt}/{args.retries} (rc={res.returncode}, logs={len(res.new_logs)})")

            if attempt >= args.retries:
                print(f"[fatal] plan failed repeatedly: {plan}")
                sys.exit(1)

    print("[done] all plans processed.")


if __name__ == "__main__":
    main()
