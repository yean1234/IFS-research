# CP22 재검토 — G86 수정 확인

읽기 전용. 파일을 고치지 않는다. 한국어로 답한다. 시험은 돌리지 않는다.
`unity/Assets/XR/Settings/OpenXRPackageSettings.asset`과 `chatbot/logs/` 아래는 열지 않는다.

읽을 것: `docs/codex-reviews/CP22.md`(앞선 지적), 커밋되지 않은 작업 트리의 `unity/Assets/IFS/Runtime/Placement/PlacementSession.cs`, `unity/Assets/IFS/Tests/Editor/PlacementTests.cs`·`PlacementSetupAutoTests.cs`·`PlacementUiG63Tests.cs`, 문구 파일 `unity/Assets/StreamingAssets/IFS/placement_task*.json`.

확인할 것(고쳐짐 / 일부 / 안 고쳐짐, 근거 파일:줄):
1. 놓기와 확인이 같은 프레임일 때 켜진 설정에서 확인이 무시되고 `confirm_ignored`로 남는가. 다음 프레임의 확인은 받는가. 꺼진 설정의 동작은 예전 그대로인가.
2. 더한 시험이 경계를 실제로 고정하는가: 같은 프레임 놓기+확인, 상한 프레임의 확인(timeout), 알림 중 상한 경과(confirmed), 보기만 replay, 잠금에서 값을 끄면 거부, 조건 단계 중 XR 끊김(지금 동작 고정).
3. `condition_place` 문구가 「…확인 버튼을 누르면 정해지고 다음으로 넘어가요.」로 줄었고 `PlacementUiG63Tests`의 예외가 없어졌는가.
4. 이 수정이 새로 만든 문제가 있는가(심각도, 파일:줄, 재현 입력). 없으면 없다고 적는다.

이미 알고 있는 것(다시 지적하지 않는다): 두 조건의 조건 단계 길이가 달라짐, Unity EditMode·헤드셋 미확인, 조건 단계의 XR 끊김 중 타이머는 책임자에게 물어 둔 상태, 러너의 시작 거부 자체는 UnityOnly 범위라 시험 없음.
