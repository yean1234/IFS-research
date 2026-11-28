너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라. 경로는 저장소 기준 상대 경로로만 적어라.

## 맥락
- 앞선 검토 `docs/codex-reviews/CP17.md`(네 지적 4건)와 결정 `docs/decisions.md`의 G80 절(맨 끝).
- 이번 범위: CP17 지적을 고친 뒤의 **커밋 전 작업 트리** Unity 변경(`git diff -- unity/`와 새 파일). 볼 곳: `unity/Assets/IFS/Runtime/Placement/`의 `PlacementExperimentLock.cs`, `PlacementExperimenterGui.cs`, `PlacementRunner.cs`, `PlacementSession.cs`, `PlacementRecordWriter.cs`, `PlacementPanelMetrics.cs`, `PlacementTextPanel.cs`, `PlacementSpaceChoice.cs`, 시험 `PlacementSpaceChoiceTests.cs`, `PlacementSetupAutoTests.cs`.
- `chatbot/`, `shared/`, `tools/`, `docs/validation/`은 다른 작업이다. 보지 마라.

## 메인의 판정 (되풀이하지 말 것)
- 지적 1(세션 중 XR 끊김)은 일부 수용: 경고와 기록만 하고 타이머·단계는 건드리지 않는다(G80-e). 끊김 판정을 head 장치의 isValid로 하는 것이 실제로 잡히는지는 헤드셋에서 사람이 본다.
- 지적 2(문구 판이 달라짐)는 반박: 원칙 7에 따른 의도한 변경. 실제 문구 파일의 판·키를 읽는 시험만 더했다.
- 지적 3(판이 바닥 아래)은 수용: 높이 하한(G80-b). 하한이 걸리면 사람마다 같은 기하가 깨지는 것은 알고 있고 manifest에 남긴다.
- 공간은 실험자가 단추로 고른다(G80-f). 참여자 고르기 단계는 꺼 둔 기능이다. 뼈대와 어긋나는 것은 결정문에 적었다.
- [다음 참여자 준비] 뒤 공간이 앞 참여자 값으로 남는다.

## 확인할 것
1. 지적 4건 각각 "고쳐짐 / 일부 / 안 고쳐짐 / 반박대로"와 근거(`파일:줄`).
2. 수정이 만든 새 문제: 높이 하한이 standing 기본 설정의 값을 바꾸는 경로, 하한이 물체·연습 목표·system_move 목표·판에 일관되게 걸리는가(한쪽만 걸려 눈과 물체 사이 기하가 어긋나는 경우), `xr_lost` 기록이 데스크톱·일괄 실행 기록의 바이트를 바꾸는 경로, 매 프레임 XR 재검사가 이미 시작된 세션을 거부·중단시키는 경로, 잠금 중 공간 단추가 `Holds`/`Refusals`와 어긋나 정상 설정을 거부하는 경로, 세션이 도는 중에 공간 단추가 눌리는 경로.
3. 새 시험이 수정을 실제로 고정하는가.

## 출력 형식
먼저 4건의 상태 표. 그다음 새로 찾은 문제만 심각도, `파일:줄`, 재현 경로, 고칠 방향 한 줄. 없으면 없다고 적어라. 추측은 추측이라고 밝혀라.
