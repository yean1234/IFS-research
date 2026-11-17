너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: IFS Find→Focus→Flesh out 면담 챗봇 → 확정 텍스트 → 화이트박스 규칙 매핑(SceneSpec JSON) → Unity 형상. 저장소 원칙은 AGENTS.md.
- 2026-11-17에 연구 설계가 바뀌었다: 원본 형상 1개 + 속성 하나만 바꾼 변형본 4개(형태·색·크기·움직임)를 균형 순서로 하나씩 보여 주고, "내 것 같다" 7점 평정, 최종 선택, 머리 자세를 기록한다. 설계는 docs/research-design.md, 결정은 docs/decisions.md 마지막 절(X17–X30).
- 이번 CP4는 그 프로토타입 구현 직후의 검토다. 변경은 커밋되지 않은 작업 트리에 있다: `git status --short` 와 `git diff HEAD` 로 확인하고, 새 파일(untracked)은 직접 읽어라.
  - unity/Assets/IFS/Runtime/Ownership/*.cs (생성기 OwnershipVariantGenerator, WilliamsDesign, OwnershipConfig, OwnershipManifest, OwnershipRecordWriter, OwnershipRunner, HeadPoseProvider, OwnershipGeometry 등)
  - unity/Assets/IFS/Runtime/SceneSpec/SceneOverride.cs, MotionGroups.cs, 수정된 SceneLoader.cs·SpecMotion.cs·ShapeMapping.cs
  - unity/Assets/IFS/Editor/OwnershipExperimentMenu.cs, unity/Assets/IFS/Tests/Editor/Ownership*.cs, UnityOnly/*
  - unity/Assets/StreamingAssets/IFS/ownership_task.v0.json
  - chatbot/ifs_chatbot/eval/ownership.py, chatbot/tests/test_ownership_eval.py
  - docs/research-design.md, docs/mapping-audit.md, docs/morning-todo.md

## 이미 알고 있는 것 (되풀이하지 말 것)
- 헤드셋 실기 미검증, XR 패키지 없음, PC 실행·실험자 키보드 진행·평정 구두 응답(X27). 눈 추적이 없어 응시는 머리 방향 대리 지표.
- 속성 간 변화 크기가 지각적으로 같지 않을 수 있고 sizeStep 0.25·colorDeltaE 30은 잠정값이며 내부 시행으로 보정한다(X21, X25).
- 생성기를 Python이 아니라 Unity에 둔 것(X19), 형태·움직임 변형 규칙(X22, X23)은 네가 D1에서 낸 안과 다르다는 것을 안다. 같은 반론을 되풀이하지 말고, 채택된 규칙의 **구현이 규칙과 어긋나는 곳**을 찾아라.
- 규칙 매핑의 왜곡·근거 없는 값 사례는 docs/mapping-audit.md 에 있다. 매퍼(scene_builder*.py)는 이번에 고치지 않았다.
- 참여자 수집 가능 여부(기관 확인)는 미결이다.

## 할 일과 관점
1. 정확성 버그: 변형 생성(경계값, 범위 끝 강제 방향, 색상 순환, ΔE 목표 미달, 무채색 판정, 보이지 않는 움직임 조합, 원본과 같아지는 경우), Williams 표, 결정성(같은 입력 → 같은 manifest), 러너 상태 기계(취소·중단·재시작, 시간 측정 rt_ms·view_ms, 제시 시간이 프레임률에 따라 달라지는지), 기록 파일(헤더, 로케일, 인코딩, 중단 시 손실, 같은 초에 두 번 시작하면 폴더 충돌), 머리 자세 표본 간격.
2. Unity 기록 형식과 Python 분석(ownership.py)의 계약 불일치: 열 이름, 취소 행 순서, phase 값, 빈칸 처리, position/variant 대응, final·difference 단계 표본 처리. 분석 지표 정의(응시 시간, 방위각 원형 범위, first_look)의 계산 오류.
3. 실험 타당성을 해치는 구현: 원본 여부가 참여자에게 새는 경로(화면 글자, 제시 시간 차이, 로드 지연 차이, 형상 위치 차이, 소리·로그), 순서 균형이 깨지는 경로, 변형이 한 속성만 바꾸지 않는 경우(예: 모형 교체로 크기·표면이 같이 바뀜), 말한 값/기본값 라벨이 틀리는 경우.
4. AGENTS.md 원칙 위반: 말하지 않은 값이 spec에 들어감, 참여자 자료가 저장소 안에 쓰일 수 있는 기본 경로, 로컬 절대 경로·개인 이름, 치료 표현, 문구의 status/출처 누락.
5. 문서와 구현의 불일치: docs/research-design.md 의 절차·지표·기록 형식 서술, unity/README.md 실행 방법이 코드와 다른 곳. 지어낸 것으로 보이는 인용.
6. 테스트가 의미 있는 것을 검사하는지(항상 통과하는 테스트, 빠진 경계 사례).

## 출력 형식
지적 사항 번호 목록. 각 항목 [심각도: 높음/중간/낮음], 위치(파일:줄), 문제, 근거(재현 입력 또는 코드 경로), 제안. 심각도 높음부터. 최대 20개. 마지막에 총평 3줄. 칭찬은 생략.
