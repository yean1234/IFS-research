너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`, 뼈대 `docs/design-backbone.md` 3절·5절, 참여자 보호 `docs/participant-protection.md`.
- 결정 `docs/decisions.md`의 G78 절(맨 끝). 관련 옛 결정 G59-8, G60, G63, G67.
- 검토 범위: **커밋 전 작업 트리**의 Unity 변경. `git status --short unity/ shared/ docs/`와 `git diff -- unity/ docs/headset-checklist.md docs/run-experiment.md`, 그리고 새 파일:
  - `unity/Assets/IFS/Runtime/Placement/`의 `PlacementSession.cs`, `PlacementConfig.cs`, `PlacementRunner.cs`, `PlacementExperimenterGui.cs`, `PlacementRecordWriter.cs`, `PlacementTaskText.cs`, 새 `PlacementExperimentLock.cs`, 새 `PlacementLatestSession.cs`
  - 문구 파일 `placement_task*.json`(판 0.8, 0.8-scaleA), `Editor/PlacementExperimentMenu.cs`, `PlacementUiCapture.cs`, 씬 `PlacementExperiment.unity`의 한 줄, 시험 `Tests/Editor/`의 바뀐 것과 새 `PlacementSetupAutoTests.cs`
- `chatbot/`, `tools/`, `shared/lexicon/`, `docs/validation/`의 변경은 다른 작업이다. 보지 마라.

## 이미 알고 있는 것 (되풀이하지 말 것)
- Unity 에디터 일괄 시험과 헤드셋 확인은 하지 못했다(dotnet 컴파일 시험만 통과).
- 확정은 물체가 멈춘 동안에만 받는다(G60-2). 버튼 안내는 반복 멈춤에서 멈춘 동안에만 붙는다(G78-d).
- 데스크톱 입력에서도 버튼 안내가 A/X로 나온다. Windows 빌드에서는 자동 채움이 보통 돌지 않는다.
- 참여자 번호·헤드셋 조건은 자동으로 채우지 않는다(G78-i). 잠그지 않은 설정 항목은 G78-g.
- 2초 간격 안에 문구 두 줄이 읽히는지는 사람이 본다.

## 관점
1. **측정 절차 불변**: 확정 조건, 본 라운드 수·상한 75초, 라운드 사이 간격, events.csv·stoprounds.csv에 적히는 시각과 값이 이번 변경으로 달라지는 경로가 있는가. 확정 알림·본 측정 시작 문구를 띄우는 코드가 타이머나 입력 수락 시점을 건드리는가. 연습 30초가 본 라운드에 새는 경로(라운드 번호 경계, single 모드, 연습 0라운드 설정).
2. **두 조건 동일**: 새 문구와 표시가 place·view 두 조건, 오른손·왼손에서 다르게 보이는 경로. 보기만 조건에 확인 버튼 안내가 붙는 경로.
3. **잠금**: 잠금이 켜진 채 틀린 설정으로 시작할 수 있는 경로(명령줄 인자, SetConfig, 문구 파일 바꾸기, 다음 참여자, 씬 다시 읽기). 잠금이 꺼진 기본 상태의 기록 바이트가 예전과 같은가. 잠금 요약에 적힌 값과 실제 적용 값이 어긋나는 경우.
4. **자동 채움**: 다른 참여자의 파일이 조용히 들어가는 경로(시계가 어긋난 파일, 쓰는 도중의 파일, 같은 세션 ID의 옛 spec 사본, sha 검사를 건너뛰는 분기, 폴더가 여럿일 때). 실험자가 손으로 고른 값을 자동 채움이 덮어쓰는 경로. 경로·세션 ID가 git에 들어가는 파일이나 캡처에 남는 경로(원칙 6).
5. **문구(원칙 7·8)**: 새 키 네 개의 status·출처·판, 판을 읽는 쪽이 0.8을 받는가, 옛 판 파일을 읽을 때 새 키가 없어 깨지는가. 문구에 평가·치료 표현이 있는가.
6. **시험의 빈틈**과 문서 불일치(`docs/run-experiment.md`, `docs/headset-checklist.md`, `unity/README.md`).

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순. 끝에 "문제없다고 확인한 것". 추측은 추측이라고 밝혀라. 경로는 저장소 기준 상대 경로로만 적어라.
