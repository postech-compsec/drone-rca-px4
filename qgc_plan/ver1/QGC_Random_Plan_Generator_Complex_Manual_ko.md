
# QGC 랜덤 플랜 생성기 — 옵션 설명서
_작성일: 2025-08-30_

이 문서는 `qgc_plan_random_gen_complex.py`의 옵션 구성을 설명합니다.  
생성기는 QGroundControl에서 사용하는 `.plan` 파일을 무작위로 생성해 시뮬레이션/테스트에 활용할 수 있습니다.

---

## 빠른 시작 (Quick Start)
```bash
# 1) 서울 중심 반경 3km, 8각형 지오펜스 내부에서만 생성
python3 qgc_plan_random_gen_complex.py 5   --region 37.5665 126.9780 --radius-km 3   --fence-type polygon --fence-vertices 8

# 2) Survey/Corridor/Structure 활성화 + 파라미터를 범위로 난수화
python3 qgc_plan_random_gen_complex.py 8   --enable-survey --survey-prob 0.6 --survey-vertices-min 4 --survey-vertices-max 8   --enable-corridor --corridor-prob 0.5 --corridor-legs-min 2 --corridor-legs-max 6   --corridor-width-min-m 20 --corridor-width-max-m 80   --enable-structure --structure-prob 0.4 --structure-vertices-min 4 --structure-vertices-max 10   --max-complex 3 -o ./plans

# 3) 재현 가능한 결과(난수 시드 고정), 고도/속도 범위 제한
python3 qgc_plan_random_gen_complex.py 10   --seed 42 --alt-min 40 --alt-max 120   --cruise-min 8 --cruise-max 20 --hover-min 3 --hover-max 10
```

---

## 출력 결과
- 파일명: `1.plan`, `2.plan`, …, `N.plan`
- 위치: `--outdir`로 지정한 폴더(기본은 현재 작업 디렉터리)
- 형식: QGroundControl **Plan JSON** (`fileType: "Plan"`)

---

## 옵션 레퍼런스

### 1) 기본/입출력
| 옵션 | 형식/기본값 | 설명 |
|---|---|---|
| `count` *(위치 인자)* | 정수, 기본 `1` | 생성할 `.plan` 파일 개수 |
| `-o, --outdir` | 경로, 기본 `.` | 출력 폴더(없으면 생성) |
| `--seed` | 정수, 선택 | 난수 시드(같은 시드 → 같은 결과) |

### 2) 미션 길이(아이템 수)
| 옵션 | 기본값 | 제약/보정 | 설명 |
|---|---|---|---|
| `--min-items` / `--max-items` | `5` / `18` | `min ≥ 3`, `max ≥ min` | 미션 명령 수(이륙/웨이포인트/로이터/착륙 포함) |

### 3) 고도/속도 범위
| 옵션 | 기본값 | 제약/보정 | 설명 |
|---|---|---|---|
| `--alt-min` / `--alt-max` | `20` / `180` | `max ≥ min` | 각 아이템 고도 범위(m) |
| `--cruise-min` / `--cruise-max` | `5` / `25` | `max ≥ min` | 순항속도 범위(m/s) |
| `--hover-min` / `--hover-max` | `3` / `12` | `max ≥ min` | 호버속도 범위(m/s); 고정익은 내부적으로 `0.0` |

### 4) 지역 제약(원형)
| 옵션 | 기본값 | 제약/보정 | 설명 |
|---|---|---|---|
| `--region <LAT> <LON>` | 없음 | 위도 `[-85,85]`, 경도 `[-180,180)` 정규화 | 경로 생성 중심 좌표 |
| `--radius-km <R>` | 미지정 시 `2.0` | 최솟값 `0.05`km(=50m) | 중심 반경 R km 내부에서만 생성 |

### 5) 지오펜스(경계 강제)
| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--fence-type {none,circle,polygon}` | `none` | 경계 형태. 설정 시 경로 생성도 해당 경계 **내부로 강제** |
| `--fence-radius-km <R>` | `--region` 반경 또는 `2.0` | 펜스 크기(원 또는 다각형 외접반경) |
| `--fence-vertices <N>` | `6` | 다각형 펜스 정점 수(내부 클램프: 3–24) |

> 원형 펜스는 `.plan` 저장 시 **36각형**으로 근사해 `geoFence.polygons`에 기록됩니다.  
> 공간 제약 우선순위: **지오펜스 > region > 전세계 랜덤**.

### 6) ComplexItem 활성/확률/개수
| 그룹 | 옵션 | 기본값 | 설명 |
|---|---|---|---|
| Survey | `--enable-survey` | 끔 | Survey 삽입 허용 |
|  | `--survey-prob` | `0.35` | 삽입 시도 때 Survey를 **후보**에 올릴 확률 |
| Corridor | `--enable-corridor` | 끔 | CorridorScan 삽입 허용 |
|  | `--corridor-prob` | `0.25` | 삽입 시도 때 Corridor를 후보에 올릴 확률 |
| Structure | `--enable-structure` | 끔 | StructureScan 삽입 허용 |
|  | `--structure-prob` | `0.25` | 삽입 시도 때 Structure를 후보에 올릴 확률 |
| 공통 | `--max-complex` | `2` | 한 미션에 추가할 ComplexItem **최대 개수** |

**삽입 로직**: 이륙 이후 **최대 `--max-complex`회** 삽입 시도 → 각 시도마다 enable+prob 통과 타입들 중 **하나**만 실제 삽입.  
(나머지 구간은 WAYPOINT/LOITER 등의 SimpleItem으로 채워짐.)

### 7) ComplexItem 파라미터 **범위(난수화 전용)**
| 타입 | 옵션 | 내부 기본값(미지정 시) | 제약/권장 | 설명 |
|---|---|---:|---|---|
| Survey | `--survey-vertices-min` / `--survey-vertices-max` | `5 / 5` | 최소 4 권장 | 영역 폴리곤 정점 수(삽입 시마다 범위에서 무작위 선택) |
| Structure | `--structure-vertices-min` / `--structure-vertices-max` | `5 / 5` | 최소 4 권장 | 구조물 폴리곤 정점 수 |
| Corridor | `--corridor-legs-min` / `--corridor-legs-max` | `3 / 3` | 최소 2 | 폴리라인 포인트 수(길이/복잡도) |
| Corridor | `--corridor-width-min-m` / `--corridor-width-max-m` | `40.0 / 40.0` | 최솟값 1.0m | 복도 폭(스캔 띠 넓이) |

**추천 시작 범위**: Survey=4–8, Structure=4–12, Corridor legs=2–6, Corridor width=20–80m

---

## 내부 동작 메모
- **기체 타입**: 고정익/멀티콥터를 랜덤 선택. 고정익은 `hoverSpeed=0.0`
- **좌표 생성**: 지오펜스/region 내부에서만 포인트를 선정. 벗어나려 하면 내부로 투영
- **홈/프레임**: 홈 좌표는 영역 내부에서 선택, `GLOBAL_RELATIVE_ALT`/`GLOBAL` 프레임 랜덤
- **클램프**: 모든 수치 옵션은 안전 범위로 보정(예: 최소/최대 뒤집힘 방지)

---

## 문제 해결 (Troubleshooting)
- **옵션이 충돌/뒤집힘**: 스크립트가 자동으로 `max ≥ min`으로 보정합니다.
- **펜스만 있고 region 없음**: 펜스 중심/반경을 기반으로 경로 생성. 원형 펜스는 36각형 근사.
- **ComplexItem이 안 들어옴**: `--enable-*`가 켜져 있는지, `--max-complex`가 0이 아닌지, `--*prob`이 충분히 큰지 확인.

---

## 변경 이력 (Changelog)
- **2025-08-30**: 단일값 옵션(`--survey-vertices`, `--structure-vertices`, `--corridor-legs`, `--corridor-width-m`) 제거.  
  → min/max 범위 옵션만 유지하여 난수화와 일관성 강화.

---

## 라이선스/주의
실제 비행 전에는 항상 **시뮬레이터/지상검증**을 통해 안전을 확인하세요. 지오펜스는 **기체 펌웨어 설정**에 따라 위반 시 동작(RTL/착륙/호버 등)이 달라집니다.
