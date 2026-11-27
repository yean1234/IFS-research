# D9 이어받기 메모 (2026-11-27)

브랜치 `claude/emotion-to-imagery-bridge`. 감정어·추상 서술로 시작한 면담에서 구체 심상으로 가는 다리 질문(G62)을 구현하는 중이다. 이 메모는 남은 일을 다 하면 지운다.

## 지금 상태
- 결정과 Codex 반박 처리: `docs/decisions.md`의 「감정어·추상 서술에서 구체 심상으로 가는 다리 질문 D9」 절(G62, 반박 처리 표 1–8).
- 설계 원문: `docs/codex-reviews/D9.md`(Codex), `D9_claude.md`(Claude), `D9_rebuttal.md`(Codex 반박).
- 구현: 판정 표(`docs/codex-reviews/prompts/D9_rebuttal_prompt.md`)의 모든 행이 들어가 있다. 설계 설명은 `docs/chatbot-design.md` §5-3.
- 켜는 방법: `cd chatbot && python -m ifs_chatbot.server --config bridge` (프로토콜 1.5, 프롬프트 v1.1.0). 기존 설정(default/pilot/v4/mac8gb)과 프로토콜 1.4에서는 켜지지 않는다.
- 시험: `chatbot/tests/test_d9_bridge.py` 62개 통과. 전체는 통과 1233, 실패 1, 건너뜀 15, xfail 6.
  - 실패 1건 `test_differentiation.py::test_committed_single_validation_outputs_are_byte_identical`은 이 작업 전 커밋(06ae0ff)에서도 실패한다. 원인은 아직 보지 않았다.
  - 전체를 한 번에 돌리면 79% 근처에서 exit 137로 죽는다(메모리로 추정, 작업 전에도 같음). 파일마다 따로 돌린다.

## 남은 일 (순서대로)
1. **반박 수용분 가운데 아직 구현에 없는 것** (`docs/decisions.md` 반박 처리 표 번호)
   - 1·2: `docs/chatbot-design.md` §5-3에 성공 기준("다리 뒤 참여자가 스스로 형상 표현을 낸 비율")과 focus_hold=주의 유지, bridge=은유 질문 구분을 적는다. focus_hold가 감각의 질 단계라는 서술이 있으면 지운다.
   - 3: X 선택 근거와 X 없음 사유를 기록에 남긴다. X가 감정·감각 사전에 든 참여자 원문 부분 문자열일 때만 쓰이는지 시험으로 확인한다('시험이 걱정돼요'에서 '시험'이 뽑히지 않아야 한다).
   - 4b: `imageSignal`에 근거 표현·부정 여부·판정 시점이 남는지 확인하고 빠진 것을 더한다. "밝은 성격이에요", "시험 전날 같아요", "엄마 같아요", "벽에 막힌 느낌이에요"를 알려진 오분류 사례로 시험에 고정한다(지금 구현은 '시험 전날 같아요'·'엄마 같아요'를 신호 있음으로 쳐서 다리를 건너뛴다).
   - 6: `firstElicitedBy`의 종류를 opening / focus_hold / bridge / llm / probe 로 맞추고 스키마에 열거한다. 분석 계획 문서에 다리 노출 사례를 따로 층화한다고 적는다.
   - 7: X 없는 고정 문구는 지금 검증기를 거치지 않는다. 고정 문구 전용 검증 경로(인용 요구 제외)와 대체 사유 기록을 넣는다. §5-3의 V8 제외 이유를 "틀과 인용만으로 된 문장이라서"로 적는다.
   - 8: `D9_rebuttal.md`의 합성 첫 발화 15개를 시험 자료로 넣는다. Codex가 X 선택 실패 예로 든 줄은 X 없는 고정 문구를 기대값으로 한다.
   - 4a(부정 표현)는 이미 구현돼 있다.
2. **하위 에이전트가 스스로 정한 것 가운데 메인 판정이 필요한 것**
   - v0.2 안전 사전의 noMore에 '안 보여요·안 떠올라요'를 넣었다(판정 표에 없음).
   - focus_hold나 다리 질문에 '없어요'류 답이 오면 flesh_out LLM을 건너뛴다.
   - 다리 단계의 stage 값이 `flesh_out`, speaker가 `system`이다.
   - 부수 수정(-되 규칙, '기대', 은유 정규식, V7 추가 검사)을 모두 새 설정에서만 켜지게 했다.
   판정을 `docs/decisions.md`에 「G62 구현 세부」로 남긴다.
3. **Codex 구현 검토(CP)**: 위를 고친 뒤 diff(06ae0ff..HEAD)를 Codex에 넘기고, 지적을 고친 뒤 재검토한다. 방법은 `CLAUDE.md`.
4. **연구 책임자에게 물을 것**: 지금 구조에는 감각의 질을 묻는 단계가 없다. Codex의 몸 감각 질문 「'{X}'은 지금 몸에서 어떻게 느껴지나요?」(G62-b, 보류)를 넣을지.
5. 감정어로 시작하는 시나리오 파일(`chatbot/scenarios`)은 아직 없다. 새 고정 문구 `bridge_like_what_plain`과 프롬프트 v1.1.0은 draft다.

## 클론한 뒤 준비
- 파이썬 환경과 모델 준비는 `chatbot/README.md`를 따른다. 8GB 맥은 `--config mac8gb`(점검용, 연구 조건 아님).
- Codex CLI가 없으면 CP 단계는 Claude 하위 에이전트만으로 한다(`CLAUDE.md`).
