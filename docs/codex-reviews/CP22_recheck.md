## CP22 재검토

시험은 실행하지 않았습니다. 요청한 파일만 읽었고, `OpenXRPackageSettings.asset`과 `chatbot/logs/`는 열지 않았습니다.

1. **같은 프레임 놓기+확인: 고쳐짐.** 설정이 켜진 직접 배치에서는 프레임 시작 때 잡고 있었다면 같은 프레임에 놓아도 확인을 무시하고 `confirm_ignored;reason=held`를 기록합니다. 놓기 이벤트도 그대로 남깁니다. 다음 프레임의 확인은 받습니다. 꺼진 설정은 기존처럼 확인 시 잡기를 놓고, 조건 시간은 끝까지 채웁니다. 근거: [PlacementSession.cs](</<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:830>), [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:683>), [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:795>).

2. **시험 경계: 고쳐짐.** 추가된 시험이 같은 프레임 놓기+확인 및 다음 프레임 확인, 상한 프레임 확인(timeout), 알림 중 상한 경과(confirmed), 보기만 replay, 잠금 값을 끄면 거부, 조건 중 XR 끊김 때 타이머 지속을 각각 확인합니다. 조건 중 XR 끊김 시험은 기존 동작을 고정합니다. 근거: [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:683>), [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:720>), [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:739>), [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:750>), [PlacementTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementTests.cs:772>), [PlacementSetupAutoTests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementSetupAutoTests.cs:288>).

3. **문구와 예외: 고쳐짐.** 두 `placement_task*.json` 모두 `condition_place`를 “확인 버튼을 누르면 정해지고 다음으로 넘어가요.”로 바꿨습니다. `PlacementUiG63Tests`에는 해당 안내 조합이 일반 경계 검사에 포함되고, `condition_place` 예외 분기는 없습니다. 근거: `placement_task.v0.json:17`, `placement_task.scaleA.v0.json:17`, [PlacementUiG63Tests.cs](</<repo>/unity/Assets/IFS/Tests/Editor/PlacementUiG63Tests.cs:156>).

4. **새 문제: 확인한 범위에서 발견하지 못했습니다.** 확인 후 알림이 끝날 때까지 입력을 받지 않고, 그동안 상한 시간이 지나도 확인 종료를 유지하는 흐름은 코드와 추가 시험에 반영돼 있습니다([PlacementSession.cs](</<repo>/unity/Assets/IFS/Runtime/Placement/PlacementSession.cs:1701>)).