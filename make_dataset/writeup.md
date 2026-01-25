# run_plan_files.py
```bash
pip install mavsdk
python make_dataset/run_plan_files.py
```
### plan 경로 지정
```bash
python make_dataset/run_plan_files.py /path/to/plans
```
### 중간부터 재개
```bash
python make_dataset/run_plan_files.py --start-from plan_0005.plan
```
### 커맨드 직접 지정
```bash
python make_dataset/run_plan_files.py --command "python make_dataset/run_one_plan_mavsdk.py --plan {plan} --udp-port 14540"
```
## 옵션 요약
--command 또는 QGC_PLAN_CMD 필수
--retries (기본 3)
--log-root (기본 build/px4_sitl_default/rootfs/log)
--run-log-dir (stdout 저장 폴더)
--require-log/--no-require-log

# ulog_datasetify.py, make_per_module_csv.py
```bash
pip install -r make_dataset/requirements.txt
#python -m pip install -r make_dataset/requirements.txt
python make_dataset/ulog_datasetify.py --recursive
```
## log, dataset 경로 지정
```bash
python make_dataset/ulog_datasetify.py --ulog-dir /path/to/logs --recursive --out-dir /path/to/datasets
```
## log 파일 지정
```bash
python make_dataset/ulog_datasetify.py /path/to/a.ulg /path/to/b.ulog --out-dir ./datasets
```
## 자주 쓰는 옵션
--recursive 하위 폴더까지 스캔
--out-dir 출력 루트
--overwrite 기존 출력 삭제 후 재생성
--skip-module-summary 모듈 요약 스킵
--time-start, --time-end (초 단위 구간)

