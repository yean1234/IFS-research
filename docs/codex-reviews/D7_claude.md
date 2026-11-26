# D7 — Claude 하위 에이전트 독립 설계안 (멈춤 거리 다시 설계 · 눈높이 정규화)

프롬프트: `<repo>/docs/codex-reviews/prompts/D7_prompt.md`. 코드는 고치지 않았고, 다른 검토자의 답(D7.md)은 읽지 않았다.

## A. 멈춤 거리 과제

### A1. 지금 구현 (`PlacementSession.StepStop`, `StopDistanceSchedule.Build`, `PlacementConfig` X49 절)
- 경로: 정면(방위 0°) 직선, 물체 중심 높이 `stopHeightM` 1.2 m 고정. 가까워지는 시행은 3.0 m에서 출발해 0.2 m(`stopMinM`)까지, 멀어지는 시행은 0.5 m에서 출발해 4.0 m(`stopMaxM`)까지 간다.
- 속도는 0.25 m/s로 일정하다. 트리거(데스크톱은 Space)를 누르는 순간 시행이 끝나고, 경계에 닿으면 `timed_out`이 된다. 시행 사이 2 s 동안 물체를 숨긴다.
- 연습 2회 뒤 방향마다 4회 본시행을 하고, 두 방향을 번갈아 둔다. 첫 방향은 참여자 번호가 홀수면 approach다.
- `stopdistance.csv`: `trial,practice,direction,start_distance_m,speed_mps,stop_distance_m,rt_ms,timed_out`. 거리는 '나' 자리(원점)에서 물체 중심까지의 수평 거리다.
- 분석기(`eval/placement.py`)는 방향별 평균, `stop_mean_m`(두 방향 평균의 평균), `stop_sd_m`, `placeDistanceStopCorrelation`을 낸다.

### A2. 새 설계: 고정 왕복 경로 + 멈춤/재개 토글 + 따로 누르는 확정

| 항목 | 제안 | 이유 |
| --- | --- | --- |
| 경로 | 정면 직선 위 **왕복**(0.4 m ↔ 3.6 m). 양 끝에서 바로 되돌아간다 | 교수님이 말한 "정해진 루프". 3.6 m면 바닥(4 m) 안에 머물고, 0.4 m면 물체 반지름(최대 약 0.3 m)이 얼굴에 닿지 않는다 |
| 속도 | 0.25 m/s로 일정(X49 그대로). 끝에서 감속하지 않는다 | 감속 구간이 있으면 끝 근처에서 멈추기가 쉬워져 끝값 쪽으로 끌린다. 한쪽으로 12.8 s, 한 바퀴 25.6 s |
| 출발 | 라운드마다 출발 방향을 번갈아 둔다(첫 방향은 지금 `FirstDirectionFor` 그대로). 출발 거리는 [1.0, 3.0] m에서 **시드를 고정한 의사난수**로 뽑는다(시드 = 참여자 번호 × 라운드) | 조정법에서 시작값이 닻이 되는 문제를 줄인다. 같은 번호면 같은 순서가 나와 재현할 수 있다 |
| 버튼 | **트리거 = 멈춤/다시 움직임 토글**(누를 때마다 바뀜, 다시 움직이면 멈추기 전 방향 그대로). **A(왼손 X) = 확정**이고 멈춘 상태에서만 받는다. 움직이는 중에 누른 A는 무시하고 사건으로만 남긴다. 토글 사이 250 ms 안의 재입력은 버린다. 데스크톱은 Space가 토글, F가 확정 | 트리거와 A는 이미 `XrPlacementInputLogic`에 매핑되어 있다(StopDown, ConfirmDown). 확정 입력을 따로 두어야 "멈춤 = 고름"이 되지 않고 여러 번 고칠 수 있다 |
| 라운드 | 연습 1 + 본 4라운드 | 반복 측정 신뢰도를 볼 수 있는 최소치. 예전 10시행(약 1.5분)보다 길어 약 3–4분 |
| 시간 상한 | 라운드마다 움직이기 시작한 때부터 75 s(약 세 바퀴) | 왕복 한 번을 놓쳐도 두 번 더 기회가 있다 |
| 상한 도달 | 확정값은 **빈칸**으로 둔다. 그때 멈춰 있었으면 `end_reason=timeout_stopped`와 `last_stop_distance_m`을, 움직이고 있었으면 `timeout_moving`을 남긴다 | 원칙 2: 참여자가 확정하지 않은 값을 시스템이 대신 정하지 않는다 |
| 한 번도 안 누름 | 확정값·멈춤값 모두 빈칸, `n_stops=0`, `timeout_moving` | 위와 같음. 분석기는 결측으로 세고 결측 수를 보고한다 |

거절한 대안: 다시 누르면 방향이 반대로 바뀌는 방식. 지나친 자리로 금방 돌아갈 수는 있지만 참여자가 경로 방향을 정하게 되어 "정해진 루프"가 아니고, 보기만 조건에도 능동 조정이 생긴다. 멈출 때 바닥 고리는 숨기는 쪽을 권한다(`stopLoopHideRings` 기본 true). 고리 눈금이 방금 놓은 거리를 맞추는 자로 쓰이지 않게 하려는 것이다(A4).

### A3. 기록과 주 값

| 값 | 정의 | 쓰임 |
| --- | --- | --- |
| **`final_distance_m`(주 값)** | 확정할 때 물체 중심의 수평 거리. 세션 값은 확정된 본 라운드의 평균(확정 라운드가 2개 미만이면 빈칸) | 물체가 멈춘 상태에서 참여자가 보고 받아들인 자리라 반응 시간만큼 지나치는 편향이 없다 |
| `first_stop_distance_m` | 라운드의 첫 멈춤 | 예전 단일 누름 지표와 같은 성격이다(RT 편향 포함). 예전 자료와 잇는 데 쓴다 |
| `n_stops`, `n_resumes` | 멈춘 횟수, 다시 움직인 횟수 | 망설임과 고친 정도 |
| `final_motion_dir` | 마지막 멈춤 직전에 움직이던 방향(approach / recede) | 히스테리시스 점검 |
| `passes_before_confirm` | 확정 전에 물체가 최종 거리를 지나간 횟수 | 탐색량 |
| `stop_spread_m` | 한 라운드 안 멈춤 거리들의 범위 | 라운드 안의 정밀도 |
| `at_bound` | 최종값이 끝(0.4 / 3.6)에서 5 cm 안 | 천장·바닥 효과 |
| 사건 행 | 라운드, t_ms, 사건(start, stop, resume, turn, confirm, confirm_ignored, timeout), distance_m, motion_dir | 위 값을 모두 다시 계산할 수 있다 |

히스테리시스: 예전 설계에서는 가까워지는 시행이 v×RT(0.25 m/s × 약 0.3 s ≈ 7.5 cm)만큼 더 가깝게, 멀어지는 시행은 그만큼 더 멀게 잡혔다. 새 설계에서는 최종값을 멈춘 물체로 판단하므로 이 성분이 빠진다. 남는 것은 지나친 자리를 "이 정도면 됐다"고 받아들이는 허용 편향인데, 이 편향은 마지막 방향을 따라간다. 그래서 다음을 미리 정한다. ① 주 분석은 방향을 가리지 않은 4라운드 평균이다. ② `final_motion_dir`로 나눈 평균을 함께 보고하고, 차이가 0.15 m를 넘으면 경고한다. ③ `first_stop − final`의 부호를 방향별로 보고해 RT 편향이 실제로 고쳐졌는지 확인한다.

### A4. 직접 배치에서 "방금 놓은 거리"에 끌리는 문제 (G59-11)
멈춤/재개를 여러 번 할 수 있으면 기억해 둔 거리를 더 정확히 맞출 수 있다. 그래서 배치 조건 안에서 놓은 거리와 멈춤 거리의 상관이 **커질** 가능성이 높다. 보기만 조건에도 닻이 있다는 점을 놓치면 안 된다. static은 시작 자리 1.5 m, system_move는 목표 2.5 m다. 따라서 두 조건 모두 `stop_minus_condition_final_m`(최종 멈춤 거리 − `placement.json`의 finalDistanceM)를 계산해 조건 간 "닻으로 끌린 정도"를 비교하자. 완화책은 세 가지다. 출발 거리를 무작위로 두고, 멈춤 단계에서 고리를 숨기고, 지시문에 '방금 자리'라는 말을 넣지 않는다. 직접 배치의 방위가 0°가 아니면 경로(0°)와 다른 곳이라 기억을 그대로 옮기기는 어렵다. 그래도 거리 기억은 남는다. 그러니 상관을 "같은 선호의 반복"으로 읽을지 "기억 맞추기"로 읽을지는 정할 수 없다고 논문에 적는다.

### A5. 기본값 호환과 문구 버전
- 새 설정 `stopMode`: `single`(기본, 지금 그대로) | `loop`. `loop` 관련 키는 `stopMode≠single`일 때만 config 맨 끝에 남긴다(G52·G59 관례).
- `loop`에서만 새 파일 `stoprounds.csv`(라운드 1행)와 `stopadjust.csv`(사건 행)를 만들고, manifest `stopDistance`에 `mode`·`loop{…}`를 더한다. `stopdistance.csv`는 헤더만 남긴다. `recordVersion`은 0.2를 유지한다(practice.json을 추가했을 때와 같은 판단).
- 문구: 새 키 `stop_distance_loop`(예: "이것이 앞뒤로 오갑니다. 알맞다고 느껴지는 자리에서 트리거를 눌러 멈추세요. 다시 누르면 다시 움직입니다. 그 자리로 정하셨으면 A 버튼을 눌러 주세요."), `stop_loop_hint`(멈춘 동안 아래에 "트리거: 다시 움직이기 · A: 이 자리로 정하기"). 둘 다 `status: draft`이고 출처를 적는다. `placement_task.v0.json` 0.5→0.6, scaleA 0.5-scaleA→0.6-scaleA로 올린다. `DraftKeysFor`·`CountFor`는 `single`일 때 loop 키를 빼야 한다(AssistKeys와 같은 방식). 그래야 기본값 기록에서 바뀌는 것이 `taskText.version` 한 값뿐이다.

### A6. 참고 문헌 (이름만)
- 대인 거리 stop-distance: Hayduk(1978, 1983 개관) — 확인 필요. Bailenson 외(2003, VR 대인 거리) — 확인 필요. Lee 외 2022, Tootell 외 2021(이미 X49에 있음). Iachini 외 2014(편안 거리 대 도달 거리).
- 정신물리 방법: method of adjustment, method of limits, 습관화·예상 오차(Guilford 1954 *Psychometric Methods*; Gescheider 1997 *Psychophysics: The Fundamentals*) — 확인 필요. 계단법: Cornsweet 1962, Levitt 1971(변환 상하법) — 확인 필요. 계단법은 "알맞다" 판단에 정답 문턱이 없어 이번 과제에는 맞지 않는다고 본다.

## B. 눈높이 정규화

### B1. 지금 코드
- **선 자세**다. `PlacementXrRig` 주석에 "참여자가 서는 곳"이라고 되어 있고, rq-v4-proposal 4.3도 "참여자가 선 자리"다.
- XR이 켜지면 추적 원점을 Floor로 요청한다(`RequestFloorOrigin`). 그래서 카메라 로컬 y가 실제 눈높이가 된다(사람마다 다름). Floor가 아니면 실험자 화면에 경고가 뜬다. 정면 재설정(R, `Recenter`)은 수평 위치와 yaw만 바꾸고 높이는 건드리지 않는다. 대신 `events.csv`의 recenter 상세에 `head_height_m`을 남긴다.
- 물체 높이는 모두 세계 절대값이다. `startHeightM` 1.2, `stopHeightM` 1.2, `systemMoveTargetHeightM` 1.2, `practiceTargetHeightM` 0.8이고, 허용 범위는 0.05–2.5다. 시작 위치는 정면 1.5 m다.
- 고정 1.6 m를 쓰는 곳: `PlacementRunner.anchorEyeHeightM`(SceneLoader 앵커와 문구 판 방향), `PlacementPanelMetrics.DefaultEyeHeightM`, 데스크톱 카메라(`PlacementExperimentMenu`), 자동 시행 머리(`ScriptedHead`), `sim_placement.HEAD_POS`.
- 기록: `headpose.csv`의 `head_y`(계속), `objpose.csv`의 `height_m`(절대값). 분석기에는 눈높이 열이 없고 `final_height_m`도 절대값이다. 점검표 2.4는 head_y가 실제 눈높이와 ±5 cm 안인지 확인한다.

결과: 눈높이가 1.50 m인 사람은 1.5 m 앞 물체를 약 11° 아래로 내려다보고, 1.75 m인 사람은 약 20° 아래로 본다. 제시 자극부터 사람마다 다르다.

### B2. 방식 비교

| | (a) 리그 오프셋(가상 눈높이 1.6 고정) | (b) 물체·경로를 눈높이 기준으로 배치 | (c) 기록·분석만 정규화 | (d) b + c |
| --- | --- | --- | --- | --- |
| 거리 지각 | 바닥 내려다보는 각이 바뀌어 거리 지각이 눈높이 비율만큼 흔들린다(Ooi 외 2001; Leyrer 외 2011 — 확인 필요). **RQ2의 측정값 자체를 건드린다** | 물체와 눈의 기하가 모두 같아진다. 바닥은 실제 그대로 | 자극 차이가 그대로 남는다 | b와 같음 |
| 바닥 어긋남 | 키에 따라 ±15–20 cm. 선 자세에서 발밑을 보면 바로 드러난다 | 없음 | 없음 | 없음 |
| 멀미 | 정적 오프셋이라 작지만, 몸 감각과 시각 높이가 어긋난다 | 없음 | 없음 | 없음 |
| 안전 | 가상 바닥과 실제 바닥이 달라 몸을 숙이거나 걸을 때 위험 | 실제 바닥 그대로 | 그대로 | 그대로 |
| 구현 비용 | 낮음(리그 y 하나) | 중간(보정 단계, 높이 4곳, 판 앵커) | 낮음(분석기와 manifest) | 중간 |
| RQ2·RQ3 비교 | 세계 단위로는 같아 보이지만 지각이 달라져 비교 근거가 약하다 | 제시 조건이 같아지고, 놓은 높이도 눈 기준으로 바로 비교된다 | 공변량으로만 쓸 수 있다 | 가장 좋음 |

### B3. 권고: (d) 눈높이 상대 배치 + 분석 정규화
- 설정 `eyeHeightMode`: `none`(기본, 지금 그대로) | `relative`. 기준 `eyeHeightReferenceM = 1.60`(지금 앵커값). 실제 높이 = 설정 높이 + (E − 1.60). E = 1.60이면 지금과 같은 자리가 된다(시작·멈춤·system_move 1.2 = E − 0.4, 연습 0.8 = E − 0.8). 대상은 시작 높이, 멈춤 경로 높이, system_move 목표, 연습 목표, 문구 판 앵커(`anchorEyeHeightM` 대신 E)다. 수평 거리는 그대로 둔다. 참여자가 직접 놓은 높이도 정규화하지 않는다(참여자가 고른 값).
- 보정 시점: 세션 시작 전 Check 단계에서 정면 재설정(R) 바로 뒤에 한 번 하고, 세션 동안 고정한다. 도중에 다시 재면 물체가 움직이기 때문이다.
- 절차: 실험자 키 H(또는 GUI "눈높이 재기"). 참여자에게 "편하게 똑바로 서서 앞을 봐 주세요"라고 말로 안내한다(실험자 대본, 헤드셋 문구 아님). 20 Hz로 1.0 s 표본을 모아 중앙값을 E로 삼는다. 통과 조건: 추적 원점이 Floor, 표본 SD ≤ 2 cm, 머리 pitch |·| ≤ 15°, E ∈ [1.30, 1.95] m.
- 실패하면 `relative` 모드에서는 세션 시작을 거부하고 다시 재게 한다. 실험자가 명시적으로 `none`으로 바꾸면 그 사실이 manifest에 남는다. 데스크톱·자동 시행은 E = 1.60 고정이고 `source=desktop_fixed`다.
- 덤으로 얻는 점: Guardian 바닥이 몇 cm 틀려도 물체와 눈 사이 기하는 E 기준이라 틀어지지 않는다(바닥 고리만 어긋남).
- 기록(`relative`일 때만): manifest 맨 끝 `eyeHeight{mode, referenceM, measuredM, offsetM, sdM, pitchDeg, samples, trackingOrigin, source}`, config 끝 키 `eyeHeightMode`·`eyeHeightReferenceM`·보정 한계값, events `eye_height_calibrated`. 분석기에는 `eye_height_m`, `final_height_rel_eye_m`(= 최종 높이 − E), `final_height_ratio_eye`, `head_y_median_condition_m`, `head_y_drift_m`(조건 단계 중앙값 − E, 웅크리기·까치발 점검)을 둔다. 멈춤 과제에는 `eye_object_distance_m`(확정 순간 머리와 물체의 3D 거리)을 더한다.

### B4. 깨질 수 있는 테스트·golden과 피하는 법
- `PlacementTests`의 manifest 최상위 키 목록(`EquivalentTo`), `space`·`stopDistance` 키 목록, config 기본 키 → 새 키는 기본값이 아닐 때만 넣는다.
- `stopdistance.csv`·`headpose.csv`·`objpose.csv` 헤더 대조 → 헤더를 바꾸지 않고 새 파일로 낸다. `PlacementRecordWriter.AllFiles`는 그대로 두고 `LoopFiles`를 따로 만든다.
- `docs/validation/{placement,differentiation,runner-selection}/analysis/*.csv`와 `test_placement_eval` → 분석기 새 열은 그 블록이 있는 세션이 하나라도 있을 때만 붙인다(G59 self_report와 같은 관례). 라운드 자료는 별도 `stop_loop_rounds.csv`로 낸다.
- `PlacementPanelMetrics`·`PlacementTextPanelTests`·`PlacementUiCapture`의 1.6 고정 → `none`에서는 그대로, `relative`에서는 E를 넘기는 경로만 새로 테스트한다.
- 문구 파일 version 변경 → `taskText.version`을 고정값으로 대조하는 테스트가 있으면 함께 갱신한다(G52 선례).

## C. 구현 순서 (파일 단위)
1. `PlacementConfig.cs`: `stopMode`, `stopLoopMinM` 0.4, `stopLoopMaxM` 3.6, `stopLoopStartMinM` 1.0, `stopLoopStartMaxM` 3.0, `stopLoopRounds` 4, `stopLoopPracticeRounds` 1, `stopLoopRoundSeconds` 75, `stopLoopToggleDebounceMs` 250, `stopLoopHideRings` true, `eyeHeightMode`, `eyeHeightReferenceM` 1.6, `eyeHeightMinM` 1.30, `eyeHeightMaxM` 1.95, `eyeCalibSeconds` 1.0, `eyeCalibMaxSdM` 0.02, `eyeCalibMaxPitchDeg` 15. 검증(min < start 범위 < max ≤ floorRadiusM, E 범위 안에서 모든 높이가 [minHeightM, maxHeightM] 안)과 조건부 ToJson.
2. `StopLoopSchedule.cs`(새 파일): 라운드 계획. 의사난수는 **`System.Random`을 쓰지 말고** 직접 쓴 xorshift나 해시로 만든다(Mono와 dotnet의 출력이 같아야 결정적이다).
3. `PlacementSession.cs`: `StepStopLoop` 상태 기계(moving / stopped / done), 사건 `stop_loop_*`, `Next()` 분기는 그대로. 높이에는 `EffectiveHeight(h)`를 적용한다.
4. `PlacementRecordWriter.cs`: `stoprounds.csv`·`stopadjust.csv`, manifest `stopDistance.mode/loop`, `eyeHeight` 블록.
5. `EyeHeightCalibration.cs`(새 파일, UnityEngine 없음): 중앙값·SD·pitch 판정. `PlacementRunner.cs`: 키 H, Check 거부, `anchorEyeHeightM` 대신 E. `PlacementExperimenterGui.cs`: E와 상태 표시.
6. `PlacementTaskText.cs` + 두 JSON: loop 키, `DraftKeysFor`를 설정 기반으로 일반화, version 올리기.
7. `PlacementAutoScript.cs`: loop용 자동 참여자(멈춤 → 재개 → 멈춤 → 확정, 확정 없음, 상한 도달).
8. `chatbot/ifs_chatbot/eval/placement.py`(loop 분기, 조건부 열, 닻 지표), `sim_placement.py`(loop·눈높이 합성. 기존 검증 폴더는 건드리지 않고 새 폴더에 둔다).
9. 테스트: `PlacementTests`(기본값 바이트 불변 유지, 토글·디바운스·이동 중 확정 무시·상한 빈칸·끝값 플래그·같은 번호 같은 계획), `PlacementXrTests`(트리거 토글과 A), 눈높이 판정 테스트(E = 1.6이면 위치가 예전과 같음, Device 원점 거부), pytest 새 사례.
10. 문서: `docs/decisions.md`, `docs/headset-checklist.md`(2.5 눈높이 재기, 5.5 왕복 멈춤), `docs/rq-v4-proposal.md` 4.5, `unity/README.md`.

위험: ① 과제 시간이 늘어 피로가 쌓인다(라운드 수를 설정으로 줄일 수 있게 둔다). ② 보기만 조건 참여자는 A 버튼이 처음일 수 있다(연습 라운드로 해결. practiceInAllConditions를 켜면 이미 익숙함). ③ 보정 순간의 자세가 평소와 다를 수 있다(드리프트 열로 점검). ④ 거리 기억 맞추기 때문에 G59-11 상관이 커질 수 있다. 해석 한계로 미리 적어 둔다. ⑤ 보정 실패로 시작을 거부하는 일이 현장에서 생길 수 있으니 실험자 대본에 절차를 넣는다.
