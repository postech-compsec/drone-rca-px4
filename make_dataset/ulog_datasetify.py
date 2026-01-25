#!/usr/bin/env python3
"""
Convert multiple .ulog/.ulg logs into CSV datasets and per-module summaries.

Steps per log:
  1) pyulog.ulog2csv -> topic CSVs
  2) make_per_module_csv.py -> modules_io_map.csv + module_<ID>.csv
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Set

try:
    from pyulog import ulog2csv
except ImportError as exc:
    raise SystemExit("pyulog is required (pip install pyulog).") from exc

LOG_EXTS = {".ulg", ".ulog"}
HERE = Path(__file__).resolve().parent


def natural_key(s: str):
    import re

    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def collect_logs(inputs: Iterable[Path], recursive: bool) -> List[Path]:
    logs: Set[Path] = set()
    for p in inputs:
        if p.is_file() and p.suffix.lower() in LOG_EXTS:
            logs.add(p.resolve())
        elif p.is_dir():
            for ext in LOG_EXTS:
                globber = p.rglob(f"*{ext}") if recursive else p.glob(f"*{ext}")
                logs |= {f.resolve() for f in globber if f.is_file()}
    return sorted(logs, key=lambda p: natural_key(p.name))


def run_make_per_module(log_dir: Path, out_dir: Path) -> None:
    script = HERE / "make_per_module_csv.py"
    if not script.exists():
        print(f"[warn] make_per_module_csv.py not found at {script}, skipping per-module summary.")
        return
    import subprocess

    cmd = [sys.executable, str(script), "--log-dir", str(log_dir), "--out-dir", str(out_dir)]
    subprocess.run(cmd, check=True)


def convert_one(log_file: Path, out_root: Path, args) -> None:
    out_dir = out_root / log_file.stem
    if out_dir.exists() and args.overwrite:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ulog2csv.convert_ulog2csv(
        str(log_file),
        messages=None,
        output=str(out_dir),
        delimiter=args.delimiter,
        time_s=args.time_start,
        time_e=args.time_end,
        disable_str_exceptions=args.disable_str_exceptions,
    )

    if not args.skip_module_summary:
        run_make_per_module(out_dir, out_dir / "_by_module")

    print(f"[+] {log_file.name} -> {out_dir}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Batch convert .ulog/.ulg files to CSV datasets.")
    ap.add_argument(
        "ulog_files",
        nargs="*",
        type=Path,
        help="Explicit .ulog/.ulg files or directories. If empty, --ulog-dir is used.",
    )
    ap.add_argument("--ulog-dir", type=Path, default=Path("build/px4_sitl_default/rootfs/log"), help="Default log directory to scan.")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subdirectories when scanning for logs.")
    ap.add_argument("--out-dir", type=Path, default=Path("./datasets"), help="Output root (per-log subfolder will be created).")
    ap.add_argument("--delimiter", default=",", help="CSV delimiter passed to ulog2csv (default: ',').")
    ap.add_argument("--time-start", type=float, default=None, help="Start time offset (seconds) for conversion.")
    ap.add_argument("--time-end", type=float, default=None, help="End time limit (seconds) for conversion.")
    ap.add_argument("--overwrite", action="store_true", help="Delete existing output folders before converting.")
    ap.add_argument("--skip-module-summary", action="store_true", help="Skip make_per_module_csv step.")
    ap.add_argument("--disable-str-exceptions", action="store_true", help="Pass disable_str_exceptions=True to pyulog.")
    ap.add_argument("--limit", type=int, default=None, help="Process at most N logs.")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    targets = args.ulog_files or [args.ulog_dir]
    logs = collect_logs(targets, recursive=args.recursive)
    if not logs:
        raise SystemExit("No .ulog/.ulg files found.")

    if args.limit:
        logs = logs[: args.limit]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for log_file in logs:
        convert_one(log_file, args.out_dir, args)

    print(f"[done] processed {len(logs)} log(s) into {args.out_dir}")


if __name__ == "__main__":
    main()
