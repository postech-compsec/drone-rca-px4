#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PX4 module-level I/O map builder

- Inputs (required):  subscription_info*.csv  (timestamp, subscriber_id, topic_id)
- Outputs (optional): topic CSVs that have 'publisher_id' column
  (topic name is parsed from CSV filename: HH_MM_SS_<topic>_<idx>.csv)

Emits:
  <out>/modules_io_map.csv
  <out>/modules_edges.csv
  <out>/modules/module_<ID>.csv

Usage:
  python a.py --log-dir . --out-dir ./_by_module
  # (uORBTopics.hpp 자동 탐색 실패 시 topic_<id>로 표기)
"""

import argparse
import re
from pathlib import Path
from typing import List, Dict

import pandas as pd

# ---------- file patterns ----------
PATTERNS_IN  = ["*subscription_info*_*.csv", "*subscription_info*.csv"]
# 모든 topic CSV를 순회하되 subscription_info는 제외
CSV_INCLUDE  = ["*.csv"]
CSV_EXCLUDE  = ["*subscription_info*.csv"]

# ---------- helpers ----------
def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def find_log_dir(seed: Path) -> Path:
    seed = seed if seed.is_absolute() else (Path.cwd() / seed)
    if any(seed.glob(PATTERNS_IN[0])) or any(seed.glob(PATTERNS_IN[1])):
        return seed
    # 흔한 실수: 중복된 rootfs/log/<DATE> 경로 보정
    parts = list(seed.parts)
    for i in range(len(parts)-2):
        if parts[i] == "rootfs" and parts[i+1] == "log" and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[i+2]):
            for j in range(i+3, len(parts)-2):
                if parts[j] == "rootfs" and parts[j+1] == "log" and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[j+2]):
                    trimmed = Path(*parts[:j])
                    if any(trimmed.glob(PATTERNS_IN[0])) or any(trimmed.glob(PATTERNS_IN[1])):
                        print(f"[auto] fixed --log-dir: {seed} -> {trimmed}")
                        return trimmed
                    break
    # CWD에 있으면 CWD
    if any(Path.cwd().glob(PATTERNS_IN[0])) or any(Path.cwd().glob(PATTERNS_IN[1])):
        print(f"[auto] using CWD as log-dir: {Path.cwd()}")
        return Path.cwd()
    raise SystemExit(f"subscription_info CSV not found around: {seed}")

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
    m = re.search(r'enum\s+ORB_ID\s*\{(.*?)\};', text, flags=re.DOTALL)
    if not m:
        return {}
    names = []
    for line in m.group(1).splitlines():
        line = re.sub(r'//.*', '', line)
        line = re.sub(r'/\*.*?\*/', '', line)
        line = line.strip().rstrip(',')
        line = re.sub(r'\s*=\s*[^,]+$', '', line).strip()
        if re.match(r'^[A-Za-z_]\w*$', line):
            names.append(line)
    return {i: n for i, n in enumerate(names)}

TOPIC_STEM_RE = re.compile(r"^\d{2}_\d{2}_\d{2}_(?P<topic>.+)_(?P<idx>\d+)$")

def topic_name_from_filename(p: Path) -> str | None:
    m = TOPIC_STEM_RE.match(p.stem)
    if not m:
        return None
    return m.group("topic")

def list_topic_csvs(log_dir: Path) -> List[Path]:
    files = []
    for pat in CSV_INCLUDE:
        files += list(log_dir.glob(pat))
    # exclude subscription_info csvs
    ex = set()
    for pat in CSV_EXCLUDE:
        ex |= set(log_dir.glob(pat))
    files = [f for f in files if f not in ex and f.suffix == ".csv"]
    return sorted(files, key=lambda p: natural_key(p.name))

# ---------- loaders ----------
def load_inputs(log_dir: Path) -> pd.DataFrame:
    cand = []
    for pat in PATTERNS_IN:
        cand += list(log_dir.glob(pat))
    cand = sorted(set(cand), key=lambda p: natural_key(p.name))
    if not cand:
        raise SystemExit(f"subscription_info CSV not found in: {log_dir}")
    dfs = []
    for f in cand:
        df = pd.read_csv(f)
        need = {"timestamp", "subscriber_id", "topic_id"}
        miss = [c for c in need if c not in df.columns]
        if miss:
            raise SystemExit(f"{f} missing columns: {miss}")
        df["__srcfile"] = f.name
        dfs.append(df)
    ins = pd.concat(dfs, ignore_index=True).sort_values(["timestamp", "subscriber_id", "topic_id"])
    return ins

def load_outputs_from_topic_csvs(log_dir: Path) -> pd.DataFrame:
    """
    스캔한 각 토픽 CSV에서 publisher_id를 읽어 모듈 출력(edge)을 만든다.
    토픽 이름은 파일명에서 추출.
    timestamp는 pub_timestamp가 있으면 사용, 없으면 timestamp, 둘 다 없으면 None.
    """
    rows = []
    files = list_topic_csvs(log_dir)
    for f in files:
        tname = topic_name_from_filename(f)
        if not tname:
            continue
        # 최소 컬럼만 읽기 (없으면 있는 것만)
        try:
            df = pd.read_csv(f, usecols=lambda c: c in ("publisher_id","pub_timestamp","timestamp"))
        except Exception:
            # 스키마가 너무 다르면 스킵
            continue
        if "publisher_id" not in df.columns:
            # publisher 정보가 없다면 이 토픽은 출력측 추정 불가
            continue
        # 타임스탬프 선택
        ts_col = "pub_timestamp" if "pub_timestamp" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
        if ts_col is None:
            # 타임스탬프 없는 경우에도 edge는 기록하되 timestamp=None
            for pid in df["publisher_id"].dropna().astype(int).tolist():
                rows.append({"module_id": pid, "dir": "out", "topic_name": tname, "timestamp": None, "__srcfile": f.name})
            continue
        # 정상 케이스
        g = df[["publisher_id", ts_col]].dropna()
        if g.empty:
            continue
        g = g.rename(columns={ts_col: "timestamp"})
        g["module_id"]  = g["publisher_id"].astype(int)
        g["dir"]        = "out"
        g["topic_name"] = tname
        g["__srcfile"]  = f.name
        rows.append(g[["module_id","dir","topic_name","timestamp","__srcfile"]])
    if not rows:
        return pd.DataFrame(columns=["module_id","dir","topic_name","timestamp","__srcfile"])
    if isinstance(rows[0], dict):
        return pd.DataFrame(rows)
    return pd.concat(rows, ignore_index=True)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Build module-level INPUT/OUTPUT map from PX4 logs")
    ap.add_argument("--log-dir", type=Path, required=True, help="log folder (date dir)")
    ap.add_argument("--uorb-hpp", type=Path, default=None, help="optional uORBTopics.hpp for topic_id→name")
    ap.add_argument("--out-dir",  type=Path, default=Path("./_by_module"), help="output folder")
    args = ap.parse_args()

    log_dir = find_log_dir(args.log_dir)
    out_dir = args.out_dir.expanduser().resolve()
    (out_dir / "modules").mkdir(parents=True, exist_ok=True)

    # 1) Inputs (required)
    ins = load_inputs(log_dir)

    # 1-1) topic_id → name (best-effort)
    id2name = {}
    hpp = args.uorb_hpp or auto_find_uorb_topics_hpp(log_dir)
    if hpp:
        id2name = parse_topics_hpp(hpp)
        print(f"[info] topic id mapping: {hpp} ({len(id2name)} ids)")
    ins["topic_name"] = ins["topic_id"].map(lambda x: id2name.get(int(x), f"topic_{int(x)}"))
    ins_edges = ins.assign(
        module_id=ins["subscriber_id"].astype(int),
        dir="in",
        __srcfile=ins["__srcfile"]
    )[["module_id","dir","topic_name","timestamp","__srcfile"]]

    # 2) Outputs (optional from topic CSVs publisher_id)
    outs_edges = load_outputs_from_topic_csvs(log_dir)

    # 3) Edges union
    edges = pd.concat([ins_edges, outs_edges], ignore_index=True)
    # 모듈 타임라인 파일
    for mid, g in edges.groupby("module_id"):
        g.sort_values(["timestamp","topic_name","dir"]).to_csv(out_dir / "modules" / f"module_{mid}.csv", index=False)

    # 4) Aggregate edges (first/last/count)
    agg = (
        edges.groupby(["module_id","dir","topic_name"], dropna=False)
        .agg(first_seen=("timestamp","min"), last_seen=("timestamp","max"), rows=("timestamp","size"))
        .reset_index()
        .sort_values(["module_id","dir","topic_name"], key=lambda col: col.map(lambda x: "".join(map(str, natural_key(str(x))))))
    )
    agg.to_csv(out_dir / "modules_edges.csv", index=False)

    # 5) Per-module one-liner: inputs; outputs
    ins_list = (agg[agg["dir"]=="in"]
                .groupby("module_id")
                .apply(lambda df: " ".join(sorted(df["topic_name"].unique(), key=natural_key)))
                .rename("inputs"))
    if (agg["dir"]=="out").any():
        out_list = (agg[agg["dir"]=="out"]
                    .groupby("module_id")
                    .apply(lambda df: " ".join(sorted(df["topic_name"].unique(), key=natural_key)))
                    .rename("outputs"))
    else:
        out_list = pd.Series(dtype=str, name="outputs")

    modules = pd.DataFrame({"module_id": sorted(edges["module_id"].dropna().astype(int).unique())})
    modules = modules.merge(ins_list, left_on="module_id", right_index=True, how="left")
    modules = modules.merge(out_list, left_on="module_id", right_index=True, how="left")
    modules = modules.fillna({"inputs":"", "outputs":""}).sort_values("module_id")
    modules.to_csv(out_dir / "modules_io_map.csv", index=False)

    print(f"[+] wrote {out_dir/'modules_io_map.csv'}")
    print(f"[+] wrote {out_dir/'modules_edges.csv'}")
    print(f"[+] wrote {out_dir/'modules'}/module_<ID>.csv")

if __name__ == "__main__":
    main()

