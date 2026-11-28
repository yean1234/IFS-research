너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`, 뼈대 `docs/design-backbone.md`, 결정 `docs/decisions.md` 맨 끝 G83 절(G83-a: G82를 실험 설정에서 켬, G83-b: 멈춤 거리 연습 1 + 본 측정 1).
- 이번 범위: 브랜치의 **커밋 전 작업 트리 변경**(`git status`, `git diff`).
  - 챗봇: `chatbot/ifs_chatbot/llm_shape.py`(`basis_display`), `selection.py`, `none_gen.py`, `web/stage.js`, `web/style.css`, `chatbot/config/experiment.toml`, `shared/protocol/selection_protocol.v0.13.json`, `shared/schemas/selection.v0.5.json`, `chatbot/tests/test_g83_g82_on.py`
  - Unity: `unity/Assets/IFS/Runtime/Placement/`의 `PlacementConfig.cs`·`PlacementExperimentLock.cs`·`PlacementSession.cs`·`StopLoopSchedule.cs`, 문구 `unity/Assets/StreamingAssets/IFS/placement_task*.json`, 시험 `unity/Assets/IFS/Tests/Editor/`
  - 분석기: `chatbot/ifs_chatbot/eval/placement.py`(`loop_min_confirmed`)
- `unity/Assets/XR/Settings/OpenXRPackageSettings.asset`은 보지 마라.

## 이미 알고 있는 것 (되풀이하지 말 것)
- G82 오프라인 평가는 채움 50% 안팎, 목록 밖 동물(도롱뇽) 오통과 2건이었다. 책임자가 알고 켰다.
- 본 측정을 1번으로 줄이면 세션 안 SD, 사람 안 방향 차이, 반복 신뢰도를 잃는다. 4라운드 세션과 섞으면 경고가 난다.
- 움직이는 동안의 지시문에는 A·X 표시가 없다(판 크기 제한).
- Unity 에디터 batch 시험과 헤드셋 동작은 확인하지 못했다. `sim_placement.py`와 `docs/rq-v4-proposal.md`는 4라운드 서술 그대로다.
- 그림 1장·좁은 화면에서의 단추 폭, [이 중에는 없어요] 2회차는 화면으로 확인하지 못했다.

## 확인할 것
1. `basis_display`: 화면에 보이는 낱말이 언제나 확정 텍스트의 부분 구간인가. 원문에 없는 글자가 나오는 입력, 명사를 못 찾을 때, 인용 안에 명사가 둘일 때, '라고/이라고' 선택이 틀리는 입력(받침, 숫자·영문·기호로 끝나는 낱말).
2. [그 말이 아니에요] 뒤: 다시 LLM을 부르는 경로가 남아 있는가(다음 회차, 새로 고침, 서버 재시작 뒤 세션 복구). 안내 문구가 다른 경우에 잘못 나오는가.
3. `experiment.toml`에서 켠 뒤: 위기·확인 판정 세션, 규칙이 형태를 잡은 세션, LLM 시간 초과(20초)·Ollama 장애 때 참여자 화면이 멈추지 않고 기존 경로로 가는가. G77의 형태 칸만 꺼지는가.
4. 기록: `candidateExposed`·`candidateChosen`(null/false 구분), `afterNone.gate`, `basisShown`이 스키마와 맞는가. Unity가 읽는 필드를 건드렸는가.
5. Unity 멈춤 거리: 라운드 1개에서 상태 기계가 빠지는 경로(마지막 라운드 확정/시간 초과 직후, 연습에서 시간 초과, 일시정지 중 시간 초과, XR 끊김 재개). 잠금이 옛 값 4를 1로 되돌리는가. 문구 판과 `ExpectedTaskTextVersion`이 맞는가.
6. 분석기: 1라운드 기록에서 주 값·결측 처리, 4라운드 기록의 결과가 전과 같은가, 섞였을 때 경고.
7. 시험이 위를 실제로 고정하는가.

## 출력 형식
심각도(높음/중간/낮음), `파일:줄`, 재현 입력, 고칠 방향 한 줄. 문제가 없는 항목은 없다고 적어라. 추측은 추측이라고 밝혀라.
