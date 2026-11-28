# CP21 — G85(생성 프롬프트 다시 쓰기) 구현 검토

읽기 전용으로 검토한다. 파일을 고치지 않는다. 한국어로 답한다.

## 읽을 것
- `AGENTS.md` (작업 원칙 1의 G85 예외, 원칙 2의 "G85에서 바뀐 것")
- `docs/design-backbone.md`
- `docs/decisions.md`의 G85 절
- `docs/participant-protection.md`
- `docs/validation/run-g85-rewrite/README.md`

## 검토 대상
커밋되지 않은 작업 트리 변경이다. `git status --short`와 `git diff`로 본다. 새 파일도 포함한다.
- `chatbot/ifs_chatbot/llm_rewrite.py`, `wordnet_check.py`, `selection.py`, `none_gen.py`, `controller.py`, `config.py`, `llm_shape.py`, `web/stage.js`
- `tools/gen3d/prompts.py`
- `chatbot/prompts/llm_rewrite/`, `shared/lexicon/shape_added_adjectives.v0.json`, `shape_english_rewrite_block.v0.json`, `neutral_form_prompt.v0.json`
- `shared/protocol/selection_protocol.v0.14.json`, `shared/schemas/selection.v0.5.json`
- `chatbot/tests/test_g85_rewrite.py`, `chatbot/config/experiment-g85.toml`

`unity/Assets/XR/Settings/OpenXRPackageSettings.asset`은 열지 않는다(일부러 커밋하지 않는 파일).
`chatbot/logs/` 아래는 열지 않는다(참여자 데이터).

## 찾을 것
1. 작업 원칙 위반. 특히
   - LLM 출력이 검증 없이 프롬프트에 들어가는 경로(대상 명사, 근거 꾸밈, 덧붙임 각각).
   - 형태를 말하지 않은 경우에 LLM 출력(덧붙임 포함)이 남는 경로.
   - 색·재질·크기·위치·배경·화풍·감정·상태 낱말이 조립 프롬프트에 들어갈 수 있는 경로.
   - 위기·확인 판정 세션에서 호출 또는 캐시 조회가 일어나는 경로.
   - 규칙 값이나 G82 값을 G85가 덮어쓰는 경로.
   - 확정 스펙(IFSSceneSpec)의 슬롯 값에 G85 출력이 닿는 경로.
   - 영어 프롬프트나 세션 ID·파일 경로가 참여자 화면에 나가는 경로.
   - 외부 전송(nltk 내려받기 포함: 실행 중 네트워크 접근이 일어나는가).
2. 버그. 재현 입력을 적는다. 특히 인용 구간 바로잡기(모델이 센 charSpan이 틀릴 때 같은 인용이 원문에 두 번 나오면 어느 것을 쓰는가), 캐시 키, 메시 관문 뒤 남은 그림으로 돌아가기(세션당 한 번인가, 누적 시도 수가 기록되는가), [그 말이 아니에요] 뒤 재호출 금지.
3. 기록. 실제로 탄 경로(rule | llm_word | llm_rewrite | system_default), 조립된 프롬프트 전문, 모델 digest, 프롬프트 판, 온도, seed, 입력 해시, 원시 출력, 기각 사유, 호출·노출·선택·거절이 모두 남는가. 빠진 것을 적는다.
4. 고정 문구. `selection_protocol.v0.14.json`의 새 문구가 status·출처를 갖는가, 치료 표현이나 유도 표현이 있는가, 사실과 다른 말을 하는 경우가 있는가.
5. 빠진 시험.

## 이미 알고 있는 것 (다시 지적하지 않는다)
- 몸 낱말로 돌려 말한 문장 4건이 생성으로 간다(「눈 두 개가 달린 바윗돌이에요」 등). 고치는 중이다.
- 비유 꾸밈 2건이 근거 꾸밈으로 통과했다(팽이처럼→conical, 물레처럼→circular). 고치는 중이다.
- 중립 형태 문구 「모양은 말씀하지 않으셔서」가, 형태를 말했는데 시스템이 잡지 못한 경우에는 사실과 다르다. 고치는 중이다.
- 뜻이 다른 번역 4/28, WordNet 과차단 4건, 사전 밖 형태 40 중 9가 생성 경로로 못 감.
- 덧붙임 채택은 실제 모델에서 0건이라 화면 줄은 단위 시험으로만 확인됐다.
- CLIP 토큰 77 단언 없음. 헤드셋 러너 확인 안 됨.
- `experiment.toml`에는 아직 켜지 않았다.

## 답 형식
- 발견 사항: 심각도(높음/중간/낮음), 파일:줄, 재현 입력, 수정 방향.
- 문제를 찾지 못한 항목.
- 확인하지 못한 것은 추측이라고 적는다.
