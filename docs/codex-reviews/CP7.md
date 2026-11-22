# CP7 — 배치 실험 러너 프로토타입 검토 (Codex 독립 검토)

- 일시: 2026-11-22
- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium"` (RQ V4 무인 작업 2/3회, 사용량 한도 사용률 2%)
- 프롬프트: `docs/codex-reviews/prompts/CP7_prompt.md`
- 검토 대상 커밋: `5e0844f`
- 번호가 CP5·CP6을 건너뛴 것은 `claude/intelligent-cannon-2m4uu6` 브랜치가 그 번호를 쓰고 있어서입니다.
- 판정(수용/반박/보류)은 `docs/decisions.md` X55–X63에 적습니다.

---

1. **[심각도: 높음] 중단된 조건 시행이 완료 데이터처럼 분석됨** — [PlacementSession.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:674), [placement.py](<repo>/chatbot/ifs_chatbot/eval/placement.py:512)  
   중단 시 조건 단계가 끝나지 않았어도 `placement.json`과 `trajectory.json`을 쓰고, 요약에서는 중단 세션을 제외하지만 `placement_sessions.csv`에는 부분 조건의 최종 거리·경로가 포함됩니다. 중단 자료가 분석 출력에 완료 시행처럼 섞일 수 있습니다.  
   **근거:** 조건 단계 중 `Abort()` → `Finish(false, ...)` → `EndCondition(advance:false)` 경로. 분석기는 미완료 세션을 세션 표에 남기면서 요약 통계에서만 제외합니다.  
   **제안:** 완료 여부와 조건 단계 유효 여부를 별도 필드로 기록하고, 분석기가 부분 조건 측정치를 유효 세션 지표에서 제외하거나 명시적으로 표기하게 하세요.

2. **[심각도: 높음] stop-distance의 버튼 기록 거리가 입력 프레임에 따라 편향됨** — [PlacementSession.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:513)  
   버튼을 누른 프레임에는 현재 `_stopD`를 기록하고 그 프레임의 이동량은 반영하지 않습니다. 버튼 시점과 직전 프레임의 거리 차이가 최대 `speed × dt`가 되며, 프레임률·입력 갱신 순서에 따라 기록값이 달라집니다.  
   **근거:** 매 프레임 `StopDown` 검사 후에만 521행의 거리 갱신을 수행합니다.  
   **제안:** 입력 시각에 해당하는 이동 거리로 보간해 기록하거나, 거리 갱신과 입력 표본의 순서를 명시적으로 동기화하세요.

3. **[심각도: 높음] 멈춤 거리 정지 표본이 반경이 아닌 물체 중심 좌표 기준** — [PlacementSession.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:525), [PlacementConfig.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementConfig.cs:61)  
   제안된 측정은 물체 자극의 접근·후퇴인데, stop-distance 위치는 `FromPolar`로 정한 중심점이며 기록값도 그 중심 거리입니다. 물체 크기(잡기 반경의 하한 포함)에 따라 화면상 자극의 가장 가까운 지점은 달라집니다. 물체 크기별 비교에서는 중심 거리와 보이는 경계까지의 거리가 일치하지 않습니다.  
   **근거:** 정지 단계가 공통 `stopHeightM`·중심 거리만 사용하고, spec 형상 크기를 보정하지 않습니다.  
   **제안:** 중심 거리만 측정할 설계인지 문서에 못 박고, 크기별 시각 경계 차이를 통제하거나 분석 변수로 남기세요.

4. **[심각도: 중간] 참가자 번호가 방향 순서 배정의 대리변수** — [PlacementConfig.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementConfig.cs:114), [StopDistanceSchedule.cs](<repo>/unity/Assets/IFS/Runtime/Placement/StopDistanceSchedule.cs:24)  
   기본 `by_participant`는 홀수 번호에 approach, 짝수 번호에 recede를 먼저 배정합니다. 조건 배정이 참가자 번호와 연관되면 방향 순서와 조건이 얽힐 수 있고, 번호가 순차 배정되지 않거나 재사용될 때 균형도 보장되지 않습니다.  
   **근거:** 번호 parity만으로 첫 방향을 결정하며 조건 배정과 독립적인 무작위화·층화 정보는 없습니다.  
   **제안:** 방향 순서를 별도 배정·기록하고 조건 배정과 독립적으로 균형화하세요.

5. **[심각도: 중간] `gaze_ratio`가 시선 비율처럼 보이지만 머리 방향 비율** — [placement.py](<repo>/chatbot/ifs_chatbot/eval/placement.py:31)  
   계산은 `headpose.csv`의 `angle_deg` 중 임계값 이하 표본 비율입니다. 시선 추적값이 아닌 머리 정면과 물체 사이 각도이므로 결과 필드 `gaze_ratio`는 측정 의미를 과장합니다.  
   **근거:** 코드 설명이 angle 표본 비율임을 밝히지만 출력 컬럼·요약 지표는 `gaze_ratio`로 명명됩니다.  
   **제안:** `head_orientation_ratio`처럼 이름을 바꾸거나, README와 분석 산출물에서 머리 방향 기반 대리지표임을 명확히 하세요.

6. **[심각도: 중간] 효과크기 신뢰구간이 작은 표본에서 정규근사** — [placement.py](<repo>/chatbot/ifs_chatbot/eval/placement.py:159)  
   효과크기 구간을 `d ± 1.96 × SE`로 계산합니다. 제안된 표본 규모에서는 소표본 보정과 자유도를 반영하지 않아 구간이 부정확할 수 있습니다.  
   **근거:** `Z95`를 사용하는 정규근사이며 t 분포 또는 Hedges 보정이 없습니다.  
   **제안:** 분석 문서에 근사 구간임을 표시하고, 계획된 표본 크기에 맞는 소표본 구간·보정치를 사용하세요.

7. **[심각도: 중간] 참여자가 쓰지 않은 시작 위치를 설정값으로 채움** — [PlacementConfig.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementConfig.cs:41), [PlacementRunner.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs:251)  
   모든 spec 물체는 기본 `startDistanceM=1.5`, `startHeightM=1.2`, 정면 방향으로 시작합니다. 이는 참여자가 말한 속성이 아니라 실험 설정인데, `_provenance`와 구분되는 별도 시작 배치 provenance가 기록되지 않습니다.  
   **근거:** 시작 좌표는 spec 대신 설정값만으로 만들어지고, manifest 설정에는 값은 있으나 출처·역할 구분이 없습니다.  
   **제안:** 시작 배치를 실험자 설정으로 분명히 표시하고, 기록에서 참여자 서술 속성과 별도 provenance로 식별하세요.

8. **[심각도: 중간] 완료 평정 단계가 조건 시간 차이를 추가할 수 있음** — [PlacementSession.cs](<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:453)  
   조건 시간은 고정값이어도, 확인 버튼이 켜져 있으면 조기 종료하고 꺼져 있으면 전체 조건 시간을 채우도록 설정할 수 있습니다. 또한 place와 view의 안내 문구·표시 흐름이 다릅니다. 이를 설정으로 열어 둔 채 조건 비교를 진행하면 노출 시간이 달라질 수 있습니다.  
   **근거:** `conditionEndsOnConfirm` 기본값은 false지만 실험자 설정으로 true가 가능하고, `EndCondition` 호출 경로가 달라집니다.  
   **제안:** 비교 시행에서는 두 조건의 종료 규칙과 문구 노출 시간을 고정하고 manifest에서 설정 일치 여부를 분석 단계에서 검사하세요.

9. **[심각도: 낮음] 테스트 목록만으로는 시간·입력 경계 버그를 막기 어려움** — [PlacementTests.cs](<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:1), [PlacementRunnerTests.cs](<repo>/unity/Assets/IFS/Tests/Editor/UnityOnly/PlacementRunnerTests.cs:1)  
   문서상 테스트는 흐름·멈춤 순서·타임아웃·재생 등을 다루지만, 입력 버튼을 미리 누른 경우, 프레임률이 달라진 경우, timeout 경계와 같은 시각의 버튼 입력, 부분 조건 중단 뒤 분석 제외는 별도 경계 검증으로 확인되지 않습니다.  
   **근거:** 해당 동작은 세션의 `Tick(dt, input, ...)` 순서에 민감하지만 테스트 요약에는 경계별 검증이 없습니다.  
   **제안:** 이 경계 입력을 결정론적 단위 사례로 추가하고, Unity 기록을 Python 분석기에 직접 넣는 계약 픽스처도 유지하세요.

총평: 기록 계약의 큰 틀은 README와 코드에서 대체로 일치하지만, 부분 중단 자료 처리와 stop-distance의 시각·기록 시점은 결과 해석에 직접 영향을 줍니다.  
분석 지표 이름과 불확실성 계산은 연구 보고에서 측정 의미를 오해하게 만들 수 있습니다.  
위험 항목을 정리하기 전까지 이 러너의 산출물은 프로토타입 검증 자료로만 취급하는 것이 타당합니다.
