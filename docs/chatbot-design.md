# 챗봇 설계 노트 — 노션 설계 → 구현

이 문서는 노션 설계를 코드로 옮기면서 내린 결정을 남깁니다. 논문 Methods와 IRB 서류를 쓸 때 근거로 씁니다.

## 1. 노션 설계 → 구현 대응

| 노션 설계 | 구현 위치 |
| --- | --- |
| 컨트롤러: 단계 기억, 고정 문구 vs LLM 결정, 단계별 횟수 제한 (「앞으로 개발 방향」 Focus) | `controller.py` `Session._advance`, 순서·횟수는 `shared/protocol/elicitation_protocol.v1.json` |
| 공통 시스템 프롬프트 v1.0 + 단계별 블록 (「IFS 이론이란?」 3절) | `chatbot/prompts/v1.0.0/` 글자 그대로. 세션 로그에 `promptSha256` |
| 턴 JSON(stage → risk_signal → move → template → anchor_quote → utterance) | `shared/schemas/interviewer_turn.schema.json`, Ollama `format`으로 제약 디코딩 |
| 검증기 V1–V8, 재생성 최대 2회, 고정 대체 문구 | `validator.py`, `controller.py` `_llm_turn` |
| 고정 문구(오프닝, 차원 프로브, 대체, 범위 이탈) | `shared/protocol` `fixedPhrases` (`status: spec`) |
| 안전 L0–L5, Kanana Safeguard 8B, 109·1577-0199 | `safety.py`, `shared/lexicon/safety_ko.v0.json`, `fixedPhrases.crisis` |
| 확정 텍스트 [이대로 맞아요] → 그 문장만 추출로 | `controller.py` `_enter_confirm` / `_finish` |
| 세션 로그 elicit-log/0.1 (턴 JSON, 재생성, 가드, 확정 텍스트) | `session_log.py`, `shared/schemas/session_log.schema.json` |
| 0층 Kiwi → 1층 사전 → 2층 직유 표지, `_provenance {source, trigger, charSpan, rule}` | `lexicon.py`, `extract.py`, `shared/lexicon/layer1_lexicon.v0.json` |
| 조건 1 정적 프롬프트 / 조건 2 AI 챗봇 면담 (설계 노트 §6) | `protocol` `conditions.static` / `conditions.chatbot`, 웹 화면에서 선택 |
| 후보 모델 3개를 같은 파일럿으로 비교 (「IFS 이론이란?」 2절) | `simulate.py` + `scenarios/` |
| 버전 고정: 태그가 아니라 digest | 세션 로그 `model.digest`, `guard.digest` |

## 2. 문서끼리 다른 곳과 고른 것

| 항목 | 문서마다 | 고른 것 | 바꾸려면 |
| --- | --- | --- | --- |
| Focus의 LLM 질문 | 챗봇 설계(10-06): 최대 3회 / 스토리보드(10-26)·설계 노트: 호흡 단계, LLM 없음 | **0회** (최신 스토리보드) | `conditions.chatbot.sequence`의 focus `maxTurns` |
| LLM 질문 총량 | 설계 노트 §6: 조건 2 "최대 5턴" / 「앞으로 개발 방향」: Find 1회, Flesh out 5회 | **단계별 한도만** (Find 1, Flesh out 5) | `maxLlmTurnsTotal`에 숫자 |
| 위치 질문 문구 | 스토리보드 '몸 안, 표면, 주변 중 어디?' / 설계 노트 6F 표준 | **설계 노트 문구** "그것이 몸 안에, 몸 표면에, 아니면 몸 주변에 있나요?" ('아니면'은 고정 문구라 V6 대상 아님) | `fixedPhrases.location` |
| 크기 프로브를 건너뛰는 조건 | 스토리보드 P07은 '덩어리'(형태) 뒤에도 크기를 물음 | 크기어가 나왔을 때만 건너뜀 | `dimensionProbes` `coveredByCategories` |
| 조건 이름 | 유도 조건 1·2, VR 조건 A·B, 로드맵 트랙 A·B가 같은 글자를 씀 | 로그 키를 `elicitationCondition: static|chatbot`으로 분리 | — |
| Feel toward 문구 | 스토리보드 "지금 그것에 대해 어떻게 느끼나요?" / 설계 노트 "지금 그 part에 대해 당신은 어떻게 느끼나요?" | 스토리보드 문구를 `vrStages`에 두고 설계 노트 문구를 출처에 병기 | `vrStages.feel_toward` |

## 3. 이 저장소에서 덧붙인 것과 이유

로컬 모델(gemma4:e4b)로 시나리오를 돌리며 실제로 나온 문제에 대응한 것입니다.

1. **인용 후보(`anchors.py`)** — e4b는 참여자 문장을 통째로 인용했다(“그 '젖은 종이처럼 축 처진 덩어리 같아요'는 마치 무엇 같나요?”). 컨트롤러가 원문에서 낱말·짧은 명사구('덩어리', '축 처진 덩어리', '조여요')를 잘라 프롬프트에 넣는다. 후보는 모두 원문의 부분 문자열이라 새 말을 주지 않는다. 사전 표제어 순위로 묘사어를 앞에, 신체 부위·비유 원천 명사를 뒤에 둔다.
2. **V3 확장** — 3어절을 넘는 인용과 여러 어절 문장 통째 인용을 막는다. '조여요'처럼 한 어절 용언은 허용한다.
3. **V5 엄격 모드** — 사전에 없는 새 내용어도 막는다. 질문 틀의 말(관계, 사이, 마치, 대하, 있 …)만 허용한다. 따옴표 구간은 지우지 않고 자리표시자(QQ)로 바꿔 분석한다. 지우면 '그 은 마치…'에서 '은'이 명사(銀)로 분석돼 정상 질문이 막혔다.
4. **V7 확장** — 질문 틀의 '은(는)'·'{X}'를 그대로 쓴 출력을 막는다(e4b에서 실제로 나옴).
5. **V8 차등 판정** — Kanana Safeguard는 참여자 문장 "젖은 종이처럼 축 처진 덩어리 같아요"만으로도 S2(괴롭힘)를 냈다. 대화 판정을 면담자 탓으로 돌리면 무해한 질문이 모두 막힌다. 그래서 (a) 질문만 따로 분류해 위험하면 실패, (b) 대화 판정이 참여자 말만의 판정과 같은 범주면 통과, 다르면 실패로 했다.
6. **V9 깊이 제한(L5)** — 기억·외상 서사 발화의 말을 인용 후보에서 빼고, 그런 말을 인용한 질문을 막는다. 그 턴에 질문이 다 막히면 일반 대체 문구("방금 말씀하신 것에 대해 더 있나요?")가 기억을 더 묻게 되므로 `depth_present` 고정 문구로 바꾼다.
7. **신호 없는 hold** — 규칙 11은 risk_signal과 hold를 같이 쓴다. e4b가 위험 신호 없이 hold를 내 확인 문구가 잘못 뜬 일이 있어, 신호 없는 hold는 잘못된 출력으로 보고 다시 만든다. 위험 신호가 있으면 move와 상관없이 확인 문구로 간다(L2).
8. **가드 판정 표** — 키워드 위기층 → 위기 대응(중지). 가드 S6, controversial, 키워드 모호층·은유층 → 확인 문구(S6·모호층은 연구자 알림). 그 밖의 가드 범주(S1 등) → 기록만. 같은 표현에 [계속]을 고른 뒤에는 다시 묻지 않는다(위기층은 예외 없음).
9. **Kanana를 Ollama에서 쓰는 법** — GGUF의 채팅 템플릿이 Ollama에서 깨져 메시지가 빠진다. raw 모드로 원래 템플릿을 조립하고, `<SAFE>`가 종료 토큰으로 처리돼 빈 응답(eval_count=1)으로 오는 것을 SAFE로 읽는다.
10. **압박하지 않기** — 직전 답이 '없어요·모르겠어요·넘어갈게요'면 그 단계의 LLM 질문을 건너뛴다. [넘어가기] 버튼도 같다. 위치를 모르면 `bodyRelation.status = unspecified`.
11. **철회** — 끝난 세션에서 [응답 폐기]를 누르면 로그 파일을 지운다(2D 평가 설문의 '응답을 제출하지 않고 폐기'). 위기 세션은 안전 기록이라 제외.

## 4. 로컬 모델 실험 (gemma4:e4b, RTX 5080 16GB)

시나리오 12개(합성 대사)를 1회씩 돌린 결과입니다. `python -m ifs_chatbot.simulate`로 다시 만들 수 있습니다.

| 지표 | 값 |
| --- | --- |
| 시나리오 기대(안전 분기·확정·추출) 충족 | 12 / 12 |
| LLM 질문 턴 | 20 |
| 첫 시도에 검증 통과 | 50% |
| 재생성 뒤에도 실패해 고정 대체 문구 | 25% |
| 시도당 평균 지연 | 약 0.7초 (첫 호출은 모델 적재 약 10초) |

- 참여자에게 나간 LLM 질문 예: "'답답'한 것에 대해 더 있나요?", "그 '젖은 종이'는 마치 무엇 같나요?", "그 '덩어리'는 어떤 '덩어리'인가요?", "'무거워요'에 대해 더 있나요?", "'웅크린 작은 나'에 대해 더 있나요?"
- 막힌 시도 예(보이지 않은 턴): "'답답'한 느낌에 대해 더 있나요?"(참여자가 쓰지 않은 '느낌', V5), 문장 통째 인용(V3), "그 '덩어리'은(는) …"(V7), 기억 문장 인용(V9).
- 검증기의 오탐은 찾지 못했다. 막힌 시도는 모두 실제 규칙 위반이었다.
- e4b는 개발용이다. 노션 권고(Gemma 4 31B, Qwen3.5 27B, EXAONE 4.0 32B 비교)대로 파일럿 전에 같은 시나리오로 비교해 모델을 고르고 이 표를 논문에 쓴다. 31B(약 20GB)는 이 PC의 16GB GPU에 다 올라가지 않아 일부가 CPU로 간다.

## 5. 열린 질문 (연구팀·교수님)

1. LLM 질문 총량: 단계별(Find 1 + Flesh out 5)인가, 설계 노트의 "최대 5턴"인가.
2. Focus 단계 LLM 질문: 0회(스토리보드)로 확정하는가.
3. `status: draft` 고정 문구(안내, 머물기 뒷문장, 조건 1 Flesh out, depth_present, 위기 안내, 확정·종료·철회)를 IRB 제출 전에 확정.
4. 가드 판정 표(2절 8): '사라지고 싶다'처럼 가드 S6 + 모호 표현을 위기 대응으로 올릴지, 지금처럼 확인 문구 + 연구자 알림으로 둘지.
5. IFSSceneSpec에 자세(`posture`)·자기지칭(`selfReference`) 슬롯을 만들지(설계 노트 §7 질문 4). 지금은 `unresolved`로만 남긴다.
6. 확정 텍스트를 참여자 발화 그대로 모으는 방식으로 충분한지. LLM 요약을 쓰면 V3·V5 같은 검사를 똑같이 걸어야 한다.
7. 세션 로그 암호화 저장 방식(디스크 암호화 / 별도 보관).

## 6. 다음 작업

- 2D 연구 자유 기술 응답으로 1층 사전 v1 만들기(「앞으로 개발 방향」 권고). 미등록어 목록(`extraction.unmatched`)이 출발점.
- 2층 직유 → 형태 프로토타입 선택(FastText 유사도), 3층 V/A/D 보충, 우선순위 병합.
- 정식 IFSSceneSpec 스키마와 필드 정렬, `serializeIFSSceneSpec` → `initialScene.json` 연결.
- 후보 모델 3개 비교(`simulate --model … --runs 3`)와 사람 코딩(Clean Language 깨끗함 등급)으로 검증기 판정 검증.
