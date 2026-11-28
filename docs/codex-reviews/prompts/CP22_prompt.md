# CP22 — G86(직접 배치는 확인 버튼으로 조건 단계를 끝냄) 구현 검토

읽기 전용으로 검토한다. 파일을 고치지 않는다. 한국어로 답한다. 시험은 돌리지 않는다.

## 결정 (연구 책임자, 2026-11-29)
직접 배치(place) 조건의 조건 단계에서 참여자가 확인 버튼(A/X)을 누르면 제한 시간(90초)이 남아 있어도 단계를 끝낸다. 시간 안에서는 몇 번이든 다시 놓을 수 있다. 확인하지 않으면 90초에 끝난다. 연습 1 + 본 1은 그대로. 보기만(view) 조건은 90초 고정으로 바꾸지 않는다.

## 읽을 것
- `AGENTS.md`, `docs/design-backbone.md`, `docs/participant-protection.md`
- 커밋되지 않은 작업 트리(`git status --short`, `git diff`). 주로
  - `unity/Assets/IFS/Runtime/Placement/PlacementSession.cs`, `PlacementConfig.cs`, `PlacementExperimentLock.cs`
  - `unity/Assets/IFS/Scenes/PlacementExperiment.unity`(conditionEndsOnConfirm 한 줄)
  - `unity/Assets/StreamingAssets/IFS/placement_task.v0.json`, `placement_task.scaleA.v0.json`
  - `unity/Assets/IFS/Tests/Editor/` 의 바뀐 시험
  - `chatbot/ifs_chatbot/eval/placement.py`, `chatbot/tests/test_placement_eval.py`
  - `docs/run-experiment.md`, `docs/headset-checklist.md`, `unity/README.md`

`unity/Assets/XR/Settings/OpenXRPackageSettings.asset`과 `chatbot/logs/` 아래는 열지 않는다.

## 찾을 것
1. 버그(재현 입력과 함께). 특히
   - 확인 → 「정했어요.」 2초 → 단계 끝. 그 2초 동안 잡기·옮기기·다시 확인이 정말 막히는가. 최종 자리(finalX/Y/Z)가 확인한 순간의 자리와 같은가.
   - 쥔 채 확인 무시(`confirm_ignored`)의 경계: 놓는 프레임과 확인이 같은 프레임일 때, 양손 입력, 왼손 설정.
   - 확인과 90초 상한이 거의 같은 때(같은 프레임, 알림 중 상한 경과)의 종료 사유와 길이 기록.
   - XR 연결이 끊긴 동안 확인 알림 타이머·조건 타이머가 어떻게 되는가(멈춤 거리 단계는 G83에서 멈추게 했다. 조건 단계는 정해진 바 없음. 새 코드가 이 경계에서 깨지는지만 본다).
   - 실험자가 단계를 넘기거나 중단할 때의 기록(`aborted`).
   - 보기만 조건(static·system_move·replay·point_select)이 어떤 입력으로도 일찍 끝나지 않는가.
   - 설정이 꺼져 있을 때 placement.json과 동작이 예전과 같은가.
2. 잠금: 실험 잠금이 이 값을 강제하고, 꺼져 있으면 시작을 거부하는가. 문구 판 `0.11-scaleA` 요구와 맞는가.
3. 분석기: 옛 기록(필드 없음)·새 기록·섞인 경우의 처리, 종료 사유 추정이 틀릴 수 있는 경우, `config_mismatch:conditionEndsOnConfirm` 경고.
4. 문구: 새 `condition_place`가 status·출처를 갖는가, 치료·유도 표현이 없는가.
5. 빠진 시험.

## 이미 알고 있는 것 (다시 지적하지 않는다)
- 두 조건의 조건 단계 길이(물체를 보는 시간)가 달라진다. 책임자 결정이며 한계로 기록한다.
- 처음 쓴 긴 문구가 35° 한계를 넘어 「확인 버튼을 누르면 정해지고 다음으로 넘어가요.」로 줄이는 중이다. `PlacementUiG63Tests`의 예외도 되돌리는 중이다.
- Unity EditMode 시험은 에디터가 열려 있어 돌리지 못했다(dotnet compile-check 시험만 통과). 헤드셋 확인 안 됨.
- 직접 배치 궤적을 replay 원본으로 쓰면 90초보다 짧다.
- 조건 단계의 XR 끊김 중 타이머 처리는 책임자에게 물어 둔 상태다.

## 답 형식
- 발견 사항: 심각도, 파일:줄, 재현 입력, 수정 방향.
- 문제를 찾지 못한 항목.
- 추측은 추측이라고 적는다.
