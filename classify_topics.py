#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classify topics as covered/uncovered based on topic CSVs and subscription_info CSVs.

Rules:
  - For each topic, scan all its topic CSV rows:
      if publisher_id == 0 OR pub_timestamp == 0 -> uncovered.
  - For each topic, scan all subscription_info CSV rows where topic_id matches:
      if subscriber_id == 0 OR sub_timestamp == 0 -> uncovered.
  - If both checks pass -> covered.

Output:
  classify_topics.json (default: <log_dir>/classify_topics.json)
"""

"""
```bash
python classify_topics.py make_dataset/datasets --uorb-hpp build/px4_sitl_default/uORB/topics/uORBTopics.hpp
# custom output
--out /path/to/classify_topics.json
```
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


PATTERNS_SUB = ["*subscription_info*_*.csv", "*subscription_info*.csv"]
CSV_EXCLUDE = ["*subscription_info*.csv"]

TOPIC_STEM_RE = re.compile(r"^\d{2}_\d{2}_\d{2}_(?P<topic>.+)_(?P<idx>\d+)$")
INSTANCE_SUFFIX_RE = re.compile(r"^(?P<base>.+)_\d+$")


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def topic_name_from_filename(p: Path) -> str | None:
    m = TOPIC_STEM_RE.match(p.stem)
    if not m:
        return None
    return m.group("topic")

def base_topic_name(topic_name: str) -> str:
    """
    subscription_info topic_id maps to the base topic name (no instance suffix).
    Example: actuator_controls_status_0 -> actuator_controls_status
    """
    m = INSTANCE_SUFFIX_RE.match(topic_name)
    return m.group("base") if m else topic_name


def list_topic_csvs(log_dir: Path) -> List[Path]:
    files = [p for p in log_dir.glob("*.csv") if p.is_file()]
    ex = set()
    for pat in CSV_EXCLUDE:
        ex |= set(log_dir.glob(pat))
    files = [f for f in files if f not in ex and f.suffix == ".csv"]
    return sorted(files, key=lambda p: natural_key(p.name))


def list_subscription_csvs(log_dir: Path) -> List[Path]:
    cand: List[Path] = []
    for pat in PATTERNS_SUB:
        cand += list(log_dir.glob(pat))
    return sorted(set(cand), key=lambda p: natural_key(p.name))

def find_log_dirs(root: Path) -> List[Path]:
    """
    Find subdirectories that contain subscription_info CSVs.
    If root itself has subscription_info CSVs, returns [root].
    """
    if list_subscription_csvs(root):
        return [root]
    dirs = []
    for p in root.rglob("*"):
        if not p.is_dir():
            continue
        if list_subscription_csvs(p):
            dirs.append(p)
    return sorted(dirs, key=lambda p: natural_key(str(p)))


def auto_find_uorb_topics_hpp(log_dir: Path) -> Path | None:
    try:
        build_root = log_dir.parents[2]  # .../build/px4_sitl_default
    except IndexError:
        build_root = log_dir
    for rel in [Path("uORB/topics/uORBTopics.hpp"), Path("uORB/uORBTopics.hpp")]:
        p = build_root / rel
        if p.exists():
            return p
    for p in build_root.rglob("uORBTopics.hpp"):
        return p
    return None


def parse_topics_hpp(path: Path | None) -> Dict[int, str]:
    if not path or not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"enum\s+(class\s+)?ORB_ID[^{]*\{(.*?)\};", text, flags=re.DOTALL)
    if not m:
        return {}
    names: List[str] = []
    for line in m.group(2).splitlines():
        line = re.sub(r"//.*", "", line)
        line = re.sub(r"/\*.*?\*/", "", line)
        line = line.strip().rstrip(",")
        line = re.sub(r"\s*=\s*[^,]+$", "", line).strip()
        if re.match(r"^[A-Za-z_]\w*$", line):
            names.append(line)
    return {i: n for i, n in enumerate(names)}


def to_int(val: str | None) -> int:
    if val is None:
        return 0
    val = val.strip()
    if val == "":
        return 0
    try:
        return int(float(val))
    except ValueError:
        return 0


def scan_topic_csvs(topic_files: Iterable[Path]) -> bool:
    """
    Returns True if covered by topic CSVs; False if uncovered.
    Uncovered when publisher_id==0 OR pub_timestamp==0 in any row.
    """
    for f in topic_files:
        with f.open("r", newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            cols = set(reader.fieldnames or [])
            if "publisher_id" not in cols or "pub_timestamp" not in cols:
                return False
            for row in reader:
                if to_int(row.get("publisher_id")) == 0 or to_int(row.get("pub_timestamp")) == 0:
                    return False
    return True


def scan_subscription_csvs(
    sub_files: Iterable[Path],
    topic_id: int | None,
) -> Tuple[bool, bool]:
    """
    Returns (covered, used_mapping).
    Uncovered when subscriber_id==0 OR sub_timestamp==0 for matching topic_id.
    If topic_id is None, returns (False, False).
    """
    if topic_id is None:
        return False, False
    used_mapping = True
    for f in sub_files:
        with f.open("r", newline="", encoding="utf-8", errors="ignore") as fh:
            reader = csv.DictReader(fh)
            cols = set(reader.fieldnames or [])
            if "topic_id" not in cols or "subscriber_id" not in cols:
                return False, used_mapping
            ts_col = "sub_timestamp" if "sub_timestamp" in cols else ("timestamp" if "timestamp" in cols else None)
            if ts_col is None:
                return False, used_mapping
            for row in reader:
                if to_int(row.get("topic_id")) != topic_id:
                    continue
                if to_int(row.get("subscriber_id")) == 0 or to_int(row.get(ts_col)) == 0:
                    return False, used_mapping
    return True, used_mapping


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify topics as covered/uncovered from PX4 log CSVs")
    ap.add_argument("log_dir", type=Path, help="log folder (date dir) containing CSVs")
    ap.add_argument("--uorb-hpp", type=Path, default=None, help="optional uORBTopics.hpp for topic_id mapping")
    ap.add_argument("--out", type=Path, default=None, help="output JSON path (default: <log_dir>/classify_topics.json)")
    args = ap.parse_args()

    root_dir = args.log_dir.expanduser().resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        print(f"[error] invalid log_dir: {root_dir}", file=sys.stderr)
        return 2

    log_dirs = find_log_dirs(root_dir)
    if not log_dirs:
        print(f"[error] subscription_info CSV not found under: {root_dir}", file=sys.stderr)
        return 2

    sub_files: List[Path] = []
    topic_files: List[Path] = []
    for d in log_dirs:
        sub_files.extend(list_subscription_csvs(d))
        topic_files.extend(list_topic_csvs(d))

    topics: Dict[str, List[Path]] = {}
    for f in topic_files:
        tname = topic_name_from_filename(f)
        if not tname:
            continue
        topics.setdefault(tname, []).append(f)

    if not topics:
        print(f"[error] no topic CSVs found in: {log_dir}", file=sys.stderr)
        return 2

    hpp = args.uorb_hpp or auto_find_uorb_topics_hpp(log_dirs[0])
    id2name = parse_topics_hpp(hpp)
    name2id = {v: k for k, v in id2name.items()}

    covered: List[str] = []
    uncovered: List[str] = []
    missing_mapping: List[str] = []

    for tname in sorted(topics.keys(), key=natural_key):
        ok_topic = scan_topic_csvs(topics[tname])
        topic_id = name2id.get(tname)
        if topic_id is None:
            topic_id = name2id.get(base_topic_name(tname))
        ok_sub, used_mapping = scan_subscription_csvs(sub_files, topic_id)
        if not used_mapping:
            missing_mapping.append(tname)
        if ok_topic and ok_sub:
            covered.append(tname)
        else:
            uncovered.append(tname)

    out_path = args.out or (root_dir / "classify_topics.json")
    payload = {"uncovered": uncovered, "covered": covered}
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    if missing_mapping:
        print(
            "[warn] topic_id mapping missing for topics: "
            + ", ".join(sorted(missing_mapping, key=natural_key)),
            file=sys.stderr,
        )

    print(f"[ok] wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
