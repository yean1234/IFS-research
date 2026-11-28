| CP17 지적 | 판정 | 근거 |
|---|---|---|
| 1. 세션 중 XR 연결 끊김 | **일부** | XR를 감시하는 세션은 프레임마다 헤드 상태를 보고하고, 끊김·복구를 이벤트와 manifest에 기록합니다. 단계와 타이머는 그대로 진행합니다. 다만 감시는 `XrHeadActive`에 의존하며 실제 헤드셋에서 끊김을 잡는지는 확인이 필요합니다. 데스크톱·자동 실행은 감시 대상에서 빠집니다. [PlacementRunner.cs:1044-1045](unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs), [PlacementSession.cs:477-496](unity/Assets/IFS/Runtime/Placement/PlacementSession.cs) |
| 2. 문구 판 변경으로 기록 바이트가 달라짐 | **반박대로** | 잠금 판은 `0.9-scaleA`이고, 새 시험은 실제 기본·scaleA 문구 파일의 버전과 필수 키를 읽어 확인합니다. 파일 변경에 따라 해당 manifest 값이 달라지는 것은 의도한 변경입니다. [PlacementExperimentLock.cs:23-28](unity/Assets/IFS/Runtime/Placement/PlacementExperimentLock.cs), [PlacementSetupAutoTests.cs](unity/Assets/IFS/Tests/Editor/PlacementSetupAutoTests.cs) |
| 3. 낮은 눈높이에서 물체·판이 바닥 아래로 감 | **고쳐짐** | relative 모드에서 시작·멈춤·system_move 목표와 연습 목표에 각각 바닥 하한을 적용하고, 참여자 판에도 별도 하한을 적용합니다. 적용 여부와 판 위치는 manifest에 남깁니다. [PlacementSession.cs:181-189](unity/Assets/IFS/Runtime/Placement/PlacementSession.cs), [PlacementTextPanel.cs:469-473](unity/Assets/IFS/Runtime/Placement/PlacementTextPanel.cs) |
| 4. XR 초기화 지연으로 설정 확인 때 세션이 거부됨 | **일부** | 설정 확인 뒤 XR 상태를 재검사해 XR이 켜지면 해당 거부를 지우고 입력을 다시 선택합니다. 재검사는 `Checked` 단계에만 적용됩니다. [PlacementRunner.cs:635-645](unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs) |

### 새로 찾은 문제

- **중간 — [PlacementExperimenterGui.cs:380-386](unity/Assets/IFS/Runtime/Placement/PlacementExperimenterGui.cs), [PlacementRunner.cs:1278](unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs)** — `[다음 참여자 준비]` 후에도 공간 단추가 앞 참여자의 `config.environment` 값을 유지합니다. nature/space를 고른 뒤 다음 참여자 화면으로 가면 해당 공간이 계속 선택된 상태입니다. 결정문대로라면 다음 참여자 때 neutral로 초기화하거나, 세션 간 유지가 의도라면 화면에 명시해야 합니다.
- **낮음 — [PlacementSession.cs:477-496](unity/Assets/IFS/Runtime/Placement/PlacementSession.cs), [PlacementRunner.cs:1044-1045](unity/Assets/IFS/Runtime/Placement/PlacementRunner.cs)** — `xr_lost`는 XR 감시 세션에만 기록되고, 매 감지 시 UTC 시각이 이벤트에 추가되며 manifest도 다시 씁니다. 따라서 **XR로 시작한 실험 세션**의 기록 바이트는 달라집니다. 데스크톱·일괄 실행은 `XrMonitored`가 꺼져 기록 변화가 없습니다. 시험은 XR 이벤트 행을 제외한 이벤트 비교만 해 이 경계를 고정합니다. XR 감시를 의도한 기록 변경으로 문서에 분명히 남기는 편이 좋습니다.

물체·연습 목표·system_move 목표에는 각각 하한이 적용되고 판에도 별도 하한이 있어, 코드상 한쪽만 바닥 아래로 남는 경로는 찾지 못했습니다. standing 기본 설정은 posture 기본값이 standing이고, 해당 설정의 판 하한도 적용되지 않는다는 시험이 있습니다. XR 재검사는 세션 시작 후 반복되지 않으며, 잠금 중 공간 단추의 유효한 값은 `Holds`와 `Refusals`를 깨지 않습니다. 세션 진행 중 설정 단추가 눌리는 경로도 확인하지 못했습니다.

### 새 시험의 고정 범위

새 시험은 XR 연결 이벤트와 타이머·단계 불변성, 실제 문구 파일의 버전·키, standing 판 위치 유지와 낮은 seated 눈높이에서의 하한, 일부 물체·연습 목표 사례를 확인합니다. 다만 XR 시험의 기록 비교는 `xr_` 행을 제외하므로 그 기록 차이를 고정하지 않고, system_move 목표의 하한도 직접 확인하지 않습니다. 공간의 다음 참여자 초기값 역시 시험하지 않습니다.