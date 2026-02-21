# run_plan_files.py, run_one_plan_mavsdk.py
```bash
pip install mavsdk
make px4_sitl jmavsim
pxh> mavlink status
python make_dataset/run_plan_files.py --command "python make_dataset/run_one_plan_mavsdk.py  --skip-geofence --plan {plan} --system-address 'udpin://0.0.0.0:14540' "
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
python make_dataset/run_plan_files.py --command "python make_dataset/run_one_plan_mavsdk.py --plan {plan}"
python make_dataset/run_plan_files.py \
  --command "python make_dataset/run_one_plan_mavsdk.py --plan {plan} --verbose-status --telemetry-interval 2"
```

## 옵션
targets (옵션, 기본 ./make_qgc_plan/plans): .plan 파일 또는 디렉토리(여러 개 가능)
--command/-c 또는 QGC_PLAN_CMD 필수 (단, run_one_plan_mavsdk.py가 있으면 생략 가능)
  - {plan}, {plan_name}, {plan_stem} 치환 가능
--log-root (기본 build/px4_sitl_default/rootfs/log): .ulg/.ulog 생성 루트
--start-from (기본 없음): 재개할 plan 파일명 또는 경로(경로가 없으면 basename 매칭)
--retries (기본 3): 각 plan 최대 재시도 횟수
--post-sleep (기본 0): 각 run 이후 대기 초
--shell (기본 false): 커맨드를 shell로 실행
--require-log/--no-require-log (기본 require): 성공 판정에 새 로그 생성 여부 반영
--run-log-dir (기본 없음): stdout 저장 폴더(성공/실패 로그 저장)
--print-output/--no-print-output (기본 print): 실패 시 stdout 출력 여부
## run_one_plan_mavsdk.py 옵션
--plan (필수): QGC .plan 파일 경로
--system-address (기본 udpin://0.0.0.0:14540): MAVSDK system_address
--skip-health-check (기본 false): 글로벌/홈 위치 OK 대기 스킵
--health-timeout-s (기본 60): health check 타임아웃
--arm/--no-arm (기본 arm): 시동/Arm 여부
--start/--no-start (기본 start): 업로드 후 미션 시작 여부
--clear-first (기본 false): 업로드 전에 mission/geofence/rally 클리어 시도
--end-action (기본 none): 종료 후 행동 none/land/rtl
--mission-timeout-s (기본 0): 미션 완료 대기 타임아웃(0=무제한)
--verbose-status (기본 false): STATUSTEXT 출력
--telemetry-interval (기본 2.0): N초마다 텔레메트리 출력(0=끄기)
--skip-geofence (기본 false): geofence 업로드 스킵
--skip-rally (기본 false): rally points 업로드 스킵



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

## 옵션
ulog_files (옵션): .ulog/.ulg 파일 또는 디렉토리(여러 개 가능). 없으면 --ulog-dir 사용
--ulog-dir (기본 build/px4_sitl_default/rootfs/log): 스캔할 기본 로그 폴더
--recursive 하위 폴더까지 스캔
--out-dir 출력 루트(로그별 하위 폴더 생성, 기본 ./datasets)
--delimiter CSV 구분자(기본 ,)
--time-start, --time-end (초 단위 구간)
--overwrite 기존 출력 삭제 후 재생성
--skip-module-summary 모듈 요약 스킵(make_per_module_csv)
--disable-str-exceptions pyulog disable_str_exceptions 사용
--limit 최대 N개 로그만 처리
## make_per_module_csv.py 옵션
--log-dir (필수): subscription_info*.csv가 있는 로그 폴더(날짜 디렉토리)
--uorb-hpp (옵션): uORBTopics.hpp 경로(없으면 자동 탐색)
--out-dir (기본 ./_by_module): 출력 폴더
