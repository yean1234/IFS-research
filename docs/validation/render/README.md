# 형상별 렌더 경로 전후 비교 (X64–X72)

`docs/decisions.md`의 "형상 종류별 렌더 경로"(X64–X72)를 구현하기 전(before)과 후(after)의 배치 캡처를 같은 spec 묶음으로 비교한다.

## spec 묶음

- `specs/` — **합성 spec 13개(참여자 데이터 아님).** `make_specs.py`가 손으로 고른 합성 값과 합성 트리거로 만들고 `shared/schemas/scene-spec.v2.1.json`으로 검사한다. 매퍼를 부르지 않는다.
  - 안개 3개(R01–R03): 색·크기가 같고 opacity만 1.0 / 0.6 / 0.15
  - 조각 2개(R04 작음 size 0.4, R05 큼 size 0.7 + 붉은색·거칠기 0.8·침식 0.3)
  - 껍질 1개(R06), 덩어리 2개(R07 기본, R08 초록·밝기 0.8), form null 1개(R09)
  - 모양 모형 4종(R10 round, R11 square, R12 flat, R13 pointed — `_unmapped` 모양어)
- held-out 60개 — `docs/validation/e2e/specs`(v0·v1)를 복사하지 않고 `-specDir`로 따로 지정해 캡처한다. 저장소에는 `report.json`과 형상이 mist·fragments인 spec의 PNG만 둔다(`before/heldout/`, `after/heldout/`).

## 캡처 명령

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity \
  -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run \
  -specDir ../docs/validation/render/specs -outDir ../docs/validation/render/before \
  -width 2064 -height 2208 -eyes 2 -warmup 30 -frames 300 -logFile <로그>
# held-out: -specDir ../docs/validation/e2e/specs -outDir <저장소 밖 폴더> → report.json과 mist·fragments PNG만 복사
```

프레임시간은 데스크톱 GPU 대리 측정값이다(Quest 3 실기 아님). 표는 `compare.py`가 두 report.json에서 만든다(`python docs/validation/render/compare.py`).

## 바뀐 것 (커밋 `b1ab311` → `ff3d483`)

| 형상 | 전 | 후 |
| --- | --- | --- |
| mist | 구(삼각형 5,120) + Fade 서피스 셰이더(가장자리 알파 감쇠) | 구 대리 메시(삼각형 1,280) + `SceneSpecMist` 부피 레이마칭 8걸음(밀도 = 흔든 반지름 감쇠 × 덩이 노이즈), 한 패스 |
| fragments | 구 5개(렌더러 5개, 정점 변위) | 각진 조각 5개를 합친 메시 하나(삼각형 100, 평면 음영, 정점 변위 0) |
| blob · shell · null · 모양 모형 | — | 그대로(구조만 `FormRenderPlan` + `IFormRenderer`로 옮김). 아래 표에서 값이 같다 |

## 요약

- **화면이 바뀌지 않아야 하는 형상**: 합성 blob 3·shell 1·모양 모형 4, held-out의 mist·fragments 밖 49개 모두 visiblePixels·silhouette·색(ΔE00)·드로콜·삼각형이 전과 같다(params·color·renderStats 비교 0건 차이).
- **fragments**: components 4 → 5(합성 2개, held-out 5개 중 4개. H23.v1은 3 → 3 — 작은 크기에서 조각이 겹쳐 보임). circularity 0.24 → 0.15. 드로콜/눈 24 → 8, 삼각형/눈 102,800 → 800. 보이는 화소는 약 35–40% 줄었다(납작한 조각이 구보다 화면을 덜 덮음, 바운즈·화면 상자 크기는 비슷). 색 ΔE00은 커졌다(5.1–5.5 → 9.4–11.1): 평면 음영이라 가운데 영역에 어두운 옆면이 섞인다.
- **mist**: circularity 0.58 → 0.39(합성 평균), 0.39 → 0.28(held-out). maxAlpha는 opacity × 0.5 정의를 그대로 따른다(1.0에서 0.554 → 0.567). opacity 0.15/0.6/1.0에서 visiblePixels 34,037 < 47,469 < 50,914(단조 증가). **edgeFalloffPx는 넓어지지 않고 줄었다**(63.6 → 48.9): 지표가 (10%→90% 띠 넓이) / 둘레라서, 윤곽이 울퉁불퉁해져 둘레가 길어지면 값이 작아진다. 화면에서 가장자리는 여전히 흐리다(sheet.png). X72의 "감쇠 폭이 넓어져야"는 이 지표로는 확인되지 않았다.
- **프레임시간**: mist frameMsP95 0.52–0.57 → 0.61–0.70 ms(spec별 +0.1–0.15 ms). frameMsP95Max 합성 1.826 → 2.186(첫 spec R01의 준비 효과, 전에도 1.8–2.0), held-out 1.966 → 2.020. 카메라가 안개 구 안에 있는 별도 확인(화면 전체가 안개)은 3.0–3.7 ms. 모두 13.9 ms 이하 → 걸음 수 8 유지.
- **AC-4(후, 합성·held-out 모두)**: 로드 오류 0, frameMsP95 ≤ 13.9, 드로콜/눈 ≤ 100(최대 8), 삼각형/눈 ≤ 300k(최대 20,880), 실시간 그림자 광원 ≤ 1 — 전부 true. 드로콜·삼각형은 추정치(ProfilerRecorder 교차 확인 안 됨).
- 바닥 문제: 처음 구현(안쪽 면만 그림)은 바닥 위 안개 H02에서 거의 사라졌다(41,834 → 763화소). 면 고르기 + 바닥 아래 밀도 0으로 고친 뒤 36,698(`ff3d483`).
- 대리 지표일 뿐이다. "더 안개답다·조각답다"는 사람 판정이 필요하다.

## 전후 시트

`sheet.png`: mist 3개, fragments 2개, 바뀌지 않아야 하는 blob·큐브·원뿔, held-out H02.v0(바닥 위 안개)·H23.v0(조각)의 전(왼쪽)·후(오른쪽) `_detail.png`.

## 전후 비교표

### 합성 13개

| spec | 형상 | renderPath 전→후 | visiblePixels | maxAlpha | circularity | components | edgeFalloffPx | frameMsP95 | 드로콜/눈 | 삼각형/눈 | ΔE00(primary) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01_mist_op100 | mist | mist | 53958 → **50914** | 0.554 → **0.567** | 0.641 → **0.48** | 1 | 66.91 → **51.99** | 1.826 → 2.186 | 5 | 5520 → **1680** | 5.29 → **6.19** |
| R02_mist_op060 | mist | mist | 53195 → **47469** | 0.334 → **0.351** | 0.594 → **0.38** | 1 | 64.53 → **47.92** | 0.521 → 0.679 | 5 | 5520 → **1680** | 5.27 → **6.65** |
| R03_mist_op015 | mist | mist | 45932 → **34037** | 0.08 → **0.091** | 0.513 → **0.308** | 1 | 59.32 → **46.68** | 0.527 → 0.69 | 5 | 5520 → **1680** | 5.22 → **7.7** |
| R04_frag_small | fragments | fragments | 21716 → **13849** | 1.0 | 0.239 → **0.152** | 4 → **5** | 0.68 | 0.895 → 0.817 | 24 → **8** | 102800 → **800** | 5.53 → **11.1** |
| R05_frag_large | fragments | fragments | 118967 → **78242** | 1.0 | 0.241 → **0.156** | 4 → **5** | 0.72 → **0.69** | 0.972 → 0.828 | 24 → **8** | 102800 → **800** | 5.11 → **9.36** |
| R06_shell | shell | shell | 48907 | 1.0 | 0.835 | 1 | 0.44 | 0.834 → 0.827 | 8 | 20880 | 8.25 |
| R07_blob_default | blob | blob | 62619 | 1.0 | 0.963 | 1 | 0.69 | 0.822 → 0.825 | 8 | 20880 | 3.55 |
| R08_blob_green_bright | blob | blob | 62619 | 1.0 | 0.968 | 1 | 0.69 | 0.832 → 0.829 | 8 | 20880 | 9.96 |
| R09_form_null | blob | blob | 62619 | 1.0 | 0.964 | 1 | 0.69 | 0.819 → 0.843 | 8 | 20880 | 3.54 |
| R10_shape_round | blob | shapePrefab(Sphere) | 63336 | 1.0 | 0.969 | 1 | 0.7 | 0.814 → 0.827 | 8 | 3472 | 7.77 |
| R11_shape_square | blob | shapePrefab(Cube) | 113605 | 1.0 | 0.825 | 1 | 0.41 | 0.822 → 0.823 | 8 | 448 | 5.77 |
| R12_shape_flat | blob | shapePrefab(FlatCylinder) | 47743 | 1.0 | 0.841 | 1 | 0.72 | 0.806 → 0.828 | 8 | 720 | 3.09 |
| R13_shape_pointed | blob | shapePrefab(Cone) | 50928 | 1.0 | 0.701 | 1 | 0.7 | 0.808 → 0.81 | 8 | 784 | 0.58 |

- frameMsP95Max: 1.826 → 2.186
- drawCallsPerEyeMax: 24 → 8
- submittedTrianglesPerEyeMax: 102800 → 20880
- AC-4(후): loadErrorsAndExceptionsZero=True, frameMsP95AtMost13_9=True, drawCallsPerEyeEstimateAtMost100=True, trianglesPerEyeEstimateAtMost300k=True, realtimeShadowLightsAtMost1=True, drawCallsTrianglesMeasuredByProfiler=False

### 합성 13개 — 형상별

| 형상 | spec 수 | visiblePixels 평균 | circularity 평균 | components 평균 | edgeFalloffPx 평균 | frameMsP95 최대 |
| --- | --- | --- | --- | --- | --- | --- |
| blob | 7 | 66209.857 → 66209.857 | 0.89 → 0.89 | 1.0 → 1.0 | 0.657 → 0.657 | 0.832 → 0.843 |
| fragments | 2 | 70341.5 → 46045.5 | 0.24 → 0.154 | 4.0 → 5.0 | 0.7 → 0.685 | 0.972 → 0.828 |
| mist | 3 | 51028.333 → 44140.0 | 0.583 → 0.389 | 1.0 → 1.0 | 63.587 → 48.863 | 1.826 → 2.186 |
| shell | 1 | 48907.0 → 48907.0 | 0.835 → 0.835 | 1.0 → 1.0 | 0.44 → 0.44 | 0.834 → 0.827 |

### held-out 60개 — 형상별

| 형상 | spec 수 | visiblePixels 평균 | circularity 평균 | components 평균 | edgeFalloffPx 평균 | frameMsP95 최대 |
| --- | --- | --- | --- | --- | --- | --- |
| blob | 48 | 92241.333 → 92241.333 | 0.886 → 0.886 | 1.146 → 1.146 | 8.11 → 8.11 | 1.966 → 2.02 |
| fragments | 5 | 7087.8 → 4308.8 | 0.211 → 0.15 | 3.8 → 4.6 | 0.65 → 0.628 | 0.912 → 0.826 |
| mist | 6 | 25409.5 → 20652.833 | 0.393 → 0.277 | 1.0 → 1.333 | 51.935 → 29.012 | 0.574 → 0.696 |
| shell | 1 | 148248.0 → 148248.0 | 0.142 → 0.142 | 1.0 → 1.0 | 41.06 → 41.06 | 0.576 → 0.616 |

- frameMsP95Max: 1.966 → 2.02
- drawCallsPerEyeMax: 24 → 8
- submittedTrianglesPerEyeMax: 102800 → 20880
- AC-4(후): loadErrorsAndExceptionsZero=True, frameMsP95AtMost13_9=True, drawCallsPerEyeEstimateAtMost100=True, trianglesPerEyeEstimateAtMost300k=True, realtimeShadowLightsAtMost1=True, drawCallsTrianglesMeasuredByProfiler=False

### held-out — mist·fragments spec

| spec | 형상 | renderPath 전→후 | visiblePixels | maxAlpha | circularity | components | edgeFalloffPx | frameMsP95 | 드로콜/눈 | 삼각형/눈 | ΔE00(primary) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H02.v0 | mist | mist | 41834 → **36698** | 0.49 → **0.53** | 0.437 → **0.185** | 1 | 45.59 → **30.66** | 0.568 → 0.696 | 5 | 5520 → **1680** | 4.31 → **3.94** |
| H02.v1 | mist | mist | 36958 → **23640** | 0.215 → **0.134** | 0.426 → **0.16** | 2 | 140.9 → **33.8** | 0.574 → 0.668 | 5 | 5520 → **1680** | 5.1 → **3.44** |
| H08.v0 | fragments | fragments | 8308 → **4870** | 1.0 | 0.108 → **0.098** | 4 → **5** | 0.52 → **0.49** | 0.874 → 0.8 | 24 → **8** | 102800 → **800** | 15.78 → **20.18** |
| H08.v1 | fragments | fragments | 556 → **344** | 1.0 | 0.169 → **0.131** | 4 → **5** | 0.62 → **0.6** | 0.853 → 0.801 | 24 → **8** | 102800 → **800** | 15.35 → **18.14** |
| H09.v0 | mist | mist | 31854 → **25536** | 0.053 → **0.065** | 0.447 → **0.23** | 1 → **3** | 52.81 → **40.83** | 0.522 → 0.672 | 5 | 5520 → **1680** | 7.17 → **10.24** |
| H09.v1 | mist | mist | 0 | 0.0 | 0.0 | 0 | 0.0 | 0.538 → 0.641 | 5 | 5520 → **1680** | None |
| H17.v1 | fragments | fragments | 8212 → **5217** | 1.0 | 0.238 → **0.153** | 4 → **5** | 0.71 → **0.68** | 0.874 → 0.792 | 24 → **8** | 102800 → **800** | 5.26 → **10.71** |
| H23.v0 | fragments | fragments | 13630 → **8674** | 1.0 | 0.238 → **0.152** | 4 → **5** | 0.72 → **0.69** | 0.882 → 0.802 | 24 → **8** | 102800 → **800** | 8.21 → **6.33** |
| H23.v1 | fragments | fragments | 4733 → **2439** | 1.0 | 0.301 → **0.217** | 3 | 0.68 | 0.912 → 0.826 | 24 → **8** | 102800 → **800** | 8.76 → **8.91** |
| H28.v0 | mist | mist | 20926 → **19160** | 0.581 → **0.575** | 0.458 → **0.509** | 1 | 34.47 → **33.3** | 0.495 → 0.61 | 5 | 5520 → **1680** | 16.83 → **12.11** |
| H28.v1 | mist | mist | 20885 → **18883** | 0.586 → **0.606** | 0.593 → **0.578** | 1 | 37.84 → **35.48** | 0.484 → 0.595 | 5 | 5520 → **1680** | 0.84 → **4.47** |

