너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: 면담 챗봇 → 확정 텍스트 → 화이트박스 규칙 매핑(SceneSpec JSON) → Unity 형상. 저장소 원칙은 AGENTS.md.
- 2026-11-22에 "RQ V4" 제안(교수 확정 전)이 나왔다: 참여자의 말로 만든 VR 물체 하나를 '나'(원형 바닥의 중심) 기준 공간에 직접 배치하는 조건과 보기만 하는 조건을 비교하고, 놓은 거리와 멈춤 거리(stop-distance)를 기록한다. 제안은 docs/rq-v4-proposal.md, 결정은 docs/decisions.md 마지막 절(X42–X54).
- 이번 CP7은 그 프로토타입 구현 직후의 검토다. 번호가 CP5·CP6을 건너뛴 것은 다른 브랜치가 그 번호를 쓰고 있어서다. 변경은 최근 커밋에 있다: `git log --oneline -6`, `git diff main --stat` 로 확인하라.
  - unity/Assets/IFS/Runtime/Placement/*.cs (PlacementConfig, PlacementGeometry, PlacementSession, PlacementRunner, PlacementRecordWriter, PlacementTrajectory, StopDistanceSchedule, PlacementAutoScript, PlacementSpace, DesktopPlacementInput, PlacementInput, PlacementTaskText, PlacementExperimenterGui)
  - unity/Assets/IFS/Editor/PlacementExperimentMenu.cs, unity/Assets/IFS/Tests/Editor/PlacementTests.cs, UnityOnly/PlacementRunnerTests.cs
  - unity/Assets/StreamingAssets/IFS/placement_task.v0.json (문구, 전부 draft)
  - chatbot/ifs_chatbot/eval/placement.py, chatbot/tests/test_placement_eval.py
  - docs/validation/placement/ (합성 spec으로 돌린 자동 시행 기록 5개와 분석 결과), unity/README.md 의 "배치 실험 러너" 절
- 기록 형식(`ifs-placement/0.1`)은 unity/README.md 의 해당 절에 있다. Unity가 쓰고 Python이 읽는다. 두 쪽은 서로 다른 작업자가 같은 계약 문서를 보고 따로 만들었다.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 헤드셋 실기 미검증, XR 패키지 없음, XR 컨트롤러 입력 미구현(데스크톱 모의 조작과 자동 시행만 있음). 일부러 그렇게 했다.
- 통제 조건(static / system_move / replay / point_select), 주 척도, 심상의 종류는 팀 결정 전이라 설정값으로만 두었다. 어느 통제 조건이 옳은지에 대한 설계 논쟁은 D2에서 이미 받았으니 되풀이하지 마라.
- 정지 관찰은 "조작"과 "거리 변화 시각 자극"을 가르지 못한다. 놓은 거리는 "고른 거리"일 뿐 심리적 거리의 측정이 아니다. 멈춤 거리는 사람 아바타로만 검증됐고 물체 자극 검증은 없다. VR 원거리는 압축 지각된다. 고리가 놓는 자리의 닻이 될 수 있다(분석기가 몰림을 보고한다).
- 문구는 전부 status: draft 이고 IRB 검토 전이다. 주 척도는 러너에 넣지 않았고 pre_wait·post_wait 대기 단계만 있다.
- 자동 시행 기록은 합성 spec과 스크립트 입력으로 만든 것이라 수치에 의미가 없다.
- 기존 후보1 러너(Ownership*)는 고치지 않았다. 스텁 파일에 API 몇 개만 추가했다.

## 할 일과 관점
1. 정확성 버그: 거리·방위각·높이 계산(기준점, 부호, 범위), 바닥 경계 clamp, 잡기–놓기 상태 전이(잡은 채 단계가 끝남, 다시 잡기, 확인 뒤 이동), 경로 길이·heldMs·firstGrabMs·confirmMs 계산, 조건 단계 길이가 프레임률에 따라 달라지는지, system_move·replay·point_select의 이동(속도, 종료 시각, 재생 시간축, 재생 원본이 더 짧거나 길 때), 멈춤 거리(시행 순서·방향 교차·연습 구분, 버튼 시점과 기록 거리의 차이, timed_out 경계, 버튼을 미리 누르고 있을 때), 평정 입력 취소, 중단(abort) 때 기록 파일 상태.
2. Unity 기록과 Python 분석(placement.py)의 계약 불일치: 열 이름, 단계 이름, 빈칸·null 처리, state 값, 이벤트 detail 형식, 조건·통제 방식 문자열, 미완료 세션 처리. 분석 지표 정의의 계산 오류(방향별 멈춤 거리 평균, 고리 몰림, gaze_ratio, yaw 범위의 ±180° 경계, 효과크기와 신뢰구간, 경로 길이 교차 점검의 허용 오차).
3. 실험 타당성을 해치는 구현: 두 조건 사이에 조작 말고 달라지는 것(제시 시간, 안내 문구 길이·내용, 물체 시작 자리, 화면 글자, 로드 지연), 조건이 참여자에게 불필요하게 새는 경로, view 조건에서 물체를 움직일 수 있는 입력이 남아 있는지, 멈춤 거리 단계가 조건에 따라 다르게 시작하는지(직전 물체 위치), 지시문이 방향을 암시하는지("멀리", "치우다" 류), 참여자 번호에 따른 방향 순서 배정이 조건 배정과 얽히는지.
4. AGENTS.md 원칙 위반: 참여자 자료가 저장소 안에 쓰일 수 있는 기본 경로, 기록·문서에 로컬 절대 경로나 개인 이름, 치료·내담자·진단 표현, 문구의 status/출처 누락, 말하지 않은 속성을 시스템이 채우는 경로(물체 시작 자리를 spec의 layout 대신 설정값으로 둔 것이 `_provenance` 기록과 어긋나는지 포함), 외부 전송.
5. 문서와 구현의 불일치: docs/rq-v4-proposal.md 4절의 절차·측정, docs/decisions.md X45·X49의 매개변수, unity/README.md 의 실행 방법·기록 형식이 코드와 다른 곳.
6. 테스트가 의미 있는 것을 검사하는지(항상 통과하는 테스트, 빠진 경계 사례), 기존 테스트·기록 형식을 깨는 변경이 있는지.

## 출력 형식
지적 사항 번호 목록. 각 항목 [심각도: 높음/중간/낮음], 위치(파일:줄), 문제, 근거(재현 입력 또는 코드 경로), 제안. 심각도 높음부터. 최대 15개. 마지막에 총평 3줄. 칭찬은 생략.
