너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라. 경로는 저장소 기준 상대 경로로만 적어라.

## 맥락
- 앞선 검토 `docs/codex-reviews/CP16.md`(네 지적 6건)와 결정 `docs/decisions.md`의 G78 절.
- 이번 범위: CP16 지적을 고친 뒤의 **커밋 전 작업 트리**. `unity/Assets/IFS/Runtime/Placement/`의 `PlacementExperimentLock.cs`, `PlacementLatestSession.cs`, `PlacementRunner.cs`, `PlacementRecordWriter.cs`, `PlacementExperimenterGui.cs`, 시험 `unity/Assets/IFS/Tests/Editor/PlacementSetupAutoTests.cs`, `PlacementStopLoopTests.cs`.
- `chatbot/`, `tools/`, `shared/lexicon/`, `docs/validation/`은 다른 작업이다. 보지 마라.

## 메인의 판정 (되풀이하지 말 것)
- 지적 2(`view` + `point_select`에 버튼 안내)는 보류다. 코드를 바꾸지 않고 지금 동작을 시험으로만 고정했다(X42 미결).
- 지적 4에서 문구 파일 digest는 고정하지 않는다. 판과 새 키 네 개만 검사한다.
- 지적 1은 지시보다 넓게 잡았다: 반복 멈춤의 왕복 범위·속도·첫 방향 등도 코드 기본값으로 잠근다.
- `sessionFiles`는 자동 채움이 그 세션의 칸을 채웠을 때만 쓴다(auto / auto_overridden).

## 확인할 것
1. 지적 6건 각각 "고쳐짐 / 일부 / 안 고쳐짐 / 보류대로"와 근거(`파일:줄`).
2. 수정이 만든 새 문제: 잠금이 정상 설정을 거부하는 경로(부동소수 비교, 명령줄 일괄 실행, 다음 참여자), 잠금이 꺼진 씬·자동 시행에 영향, 미래 시각 허용 오차의 경계, `auto_overridden` 판정이 틀리는 경로(실험자가 같은 파일을 다시 고른 경우, spec만 바꾼 경우), manifest 바이트가 예전과 달라지는 남은 경로.
3. 새 시험이 수정을 실제로 고정하는가.

## 출력 형식
먼저 6건의 상태 표. 그다음 새로 찾은 문제만 심각도, `파일:줄`, 재현 경로, 고칠 방향 한 줄. 없으면 없다고 적어라. 추측은 추측이라고 밝혀라.
