너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: 면담 챗봇 → 확정 텍스트 → 사전·규칙 매퍼 → SceneSpec JSON → Unity 형상. 저장소 원칙은 `AGENTS.md`.
- 이번 검토 대상은 D9(결정 G64): 첫 발화가 감정어·추상 서술뿐일 때 focus_hold 뒤에 결정론 "다리 질문"을 한 번 내는 구조. 결정과 판정은 `docs/decisions.md`의 「감정어·추상 서술에서 구체 심상으로 가는 다리 질문 D9」 절과 그 아래 「D9 판정 반박(Codex) 처리」「G64 구현 세부」. 설계 설명은 `docs/chatbot-design.md` §5-3.
- 변경 범위: 커밋 `06ae0ff..HEAD`와 그 뒤 미커밋 수정. 볼 파일:
  - `chatbot/ifs_chatbot/controller.py`(다리·imageSignal·firstElicitedBy 부분), `extract.py`(`image_signal`), `anchors.py`(`bridge_anchor`), `protocol.py`, `validator.py`(`require_quote`, `predicate_as_noun`), `safety.py`, `config.py`의 `[interview]`·`[guard]`·`[validator]` 플래그, `simulate.py`
  - `chatbot/config/bridge.toml`, `shared/protocol/elicitation_protocol.v1.5.json`, `shared/lexicon/safety_ko.v0.2.json`, `shared/lexicon/layer1_interview.v0.json`, `shared/schemas/session_log.schema.json`, `chatbot/prompts/v1.1.0/`
  - 시험·자료: `chatbot/tests/test_d9_bridge.py`, `chatbot/scenarios/emotion_bridge_*.json`, `chatbot/tests/test_scenarios.py`, `docs/research-design.md` 6.1절 7번
- **검토에서 뺄 것**: 작업 트리에는 무관한 미커밋 작업(생성 메시 gen3d·`form_assets.py`·`selection.py`·`preview.py`·`server.py`·`web/`·`unity/`·`tools/gen3d/`, 결정 G62·G63)이 섞여 있다. `controller.py`·`config.py`의 gen3d 줄도 대상이 아니다.
- 시험(에이전트 보고): `test_d9_bridge.py` 통과, chatbot/tests 파일별 실행에서 새 실패 없음.

## 이미 알고 있는 것 (되풀이하지 말 것)
- `docs/codex-reviews/D9_rebuttal.md`에서 네가 낸 지적 1–8과 그 판정(decisions.md 반박 처리 표).
- 알려진 오분류로 고정해 둔 것(G64-l): '돌 같지 않아요', '밝은 성격이에요', '시험 전날 같아요', '엄마 같아요', '벽에 막힌 느낌이에요', '머리가 하얘져요', '마음이 텅 빈 것 같아요'는 형상 신호 있음으로 판정돼 다리를 건너뛴다. 문맥 규칙은 넣지 않기로 했다.
- 몸 감각 질문(G64-b)은 보류이고 감각의 질을 묻는 단계가 없다는 점은 연구 책임자에게 올렸다. 다리 답의 응답 유형 자동 분류는 넣지 않는다.
- 새 고정 문구 `bridge_like_what_plain`과 프롬프트 v1.1.0은 draft다. 참여자 자료는 없다(합성 대사만).
- '가슴이 조이고 불안해요'는 다리를 묻고 X='불안'을 고르지만 X 문장이 `V5:leak:불안`에 걸려 X 없는 고정 문구로 나간다(분석기가 원문을 '불/안'으로 가름). 검증기를 약하게 하지 않고 이 동작으로 고정했다.
- v0부터 있던 noMore 패턴 `떠오르(지\s*않…)`는 부분 문자열로 찾아 "모양은 떠오르지 않고 차가워요"가 noMore로 잡힌다(v0·v0.2 공통, 이번에 고치지 않음).
- `test_differentiation.py::test_committed_single_validation_outputs_are_byte_identical` 실패는 이 작업 전부터 있었다.

## 할 일과 관점
1. **기존 설정 불변**: default/pilot/v4/v4-gen3d/mac8gb 설정과 프로토콜 1.4에서 면담 흐름·검증·세션 기록·안전 판정이 바뀌는 경로가 있는가. 플래그 기본값, 스키마 변경(`firstElicitedBy` enum 등)이 예전 기록 파일 검증을 깨는가.
2. **원칙 1·3 (LLM 한정, 참여자 말만 되돌림)**: 다리 문장의 X가 참여자 원문의 부분 문자열이 아닌 채로 나갈 수 있는 경로. 감정·감각 사전 표면 일치 대체 경로(G64-k)가 원문에 없는 표제어를 넣거나, 다른 낱말 안의 조각을 X로 고르는 경우. 조사 '은(는)' 처리. 다리가 두 번 나가거나 LLM이 like_what을 따로 내 중복되는 경로.
3. **원칙 2 (말한 것이 빠지지 않는가)**: noMore 판정(G64-d)이나 다리·건너뜀 흐름(G64-e) 때문에 참여자의 묘사 발화가 `participant_texts`·확정 초안에서 빠지는 경우. imageSignal이 흐름 밖(장면 값)으로 새는 경로.
4. **원칙 4 (위기 대응)**: 다리 턴과 그 답에서 위기·안전 판정이 건너뛰어지는 경로. V8 제외와 `require_quote=False` 경로가 안전 판정을 빼먹는가. v0.2 안전 사전이 v0보다 위기·은유 판정을 약하게 만든 곳.
5. **형상 신호 판정의 체계적 오류**: G64-k의 "사전 표제어 표면 일치 안의 적중은 뺀다" 규칙이 과하게 빼는 경우와 여전히 놓치는 흔한 감정어(형태소 분석기가 가르는 낱말). 부정 처리(4a)의 빈틈. 알려진 오분류 목록에 없는 새 유형만.
6. **기록**: `imageSignal`(근거·부정·판정 시점), `firstElicitedBy`, `capture.bridge`(basis·noXReason·fallbackReason·plainChecks)가 두 조건(LLM/정적)에서 같은 뜻으로 남는가. 다리 노출 층화(research-design 6.1-7)에 필요한 값이 기록만으로 복원되는가. 정적 조건과 LLM 조건의 다리 문장·자리 동일성.
7. **검증기**: `require_quote=False`가 고정 문구 밖에서 쓰일 수 있는가. `predicate_as_noun`의 오탐·누락. 검증기를 약하게 한 변경이 chatbot-design.md에 이유와 함께 적혀 있는가.
8. **원칙 5·6·7·8**: 새 문구·사전의 status/출처/버전, 프롬프트 v1.1.0의 금지 표현(예시·선택지·치료 표현), 절대 경로·개인 정보.
9. **시험의 빈틈과 문서 불일치**: 항상 통과하는 시험, 기대값이 구현을 그대로 베낀 시험 가운데 결함을 가리는 것, decisions.md·chatbot-design.md §5-3·`docs/handoff-D9.md`가 코드와 다른 곳.

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순으로. 끝에 "문제없다고 확인한 것"을 짧게 적어라. 추측은 추측이라고 밝혀라.
