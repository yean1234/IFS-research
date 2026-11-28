너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`(원칙 1의 G77 예외 문장 포함), 뼈대 `docs/design-backbone.md`, 참여자 보호 `docs/participant-protection.md`.
- 검토 범위: `git show c285132`(G77). 결정 `docs/decisions.md`의 G77 절, 설계 `docs/chatbot-design.md` 7.11.1. 연구 책임자가 D13의 "세션 안에는 넣지 않는다"를 뒤집고 실험 경로에 넣기로 했다. **넣을지 말지는 되풀이하지 말고, 넣은 구현이 스스로 정한 규칙을 지키는지만 본다.**
- 구현: `chatbot/ifs_chatbot/llm_fill.py`(입력·스키마·호출·검증기·캐시), `chatbot/prompts/llm_fill/llm_fill.v0.1.0.json`, `controller.py`(`_llm_fill`), `candidates.py`(prefill), `selection.py`, `none_gen.py`, `tools/gen3d/prompts.py`(`llm_items`), `web/stage.js`, `shared/schemas/selection.v0.5.json`, `shared/protocol/selection_protocol.v0.10.json`, Unity `PlacementSelection.cs`, 시험 `chatbot/tests/test_g77_llm_fill.py`.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 실제 모델로는 아직 돌리지 않았다(Ollama format의 anyOf+enum 지원, charSpan 정확도, 20초, 반복 일치는 실측 예정).
- 인용은 의미 검증이 아니다. 영어 형태 낱말·단계 값의 옳고 그름은 기계가 못 본다. 암시 효과. 합성 대사 평가 없이 들어간다.
- `test_differentiation` 실패 1건은 예전부터.

## 관점
1. **검증기 우회**: 인용·charSpan 검사를 통과하면서 규칙을 어기는 입력(유니코드 정규화·공백·겹침 경계, 매퍼가 뺀 구간과 한 글자 차이, 부정이 인용 구간 밖 뒤쪽에 있는 경우 「빨간 건 아니에요」, 다른 사람 말·과거·가정, 비유 매개어, 한 어절 안의 조사). 교차 감각·감정어 목록의 구멍. 영어 형태 낱말 금지 목록 우회(복수형·합성어·동의어: figure, doll, statue, hand, skull 등), 안개류.
2. **매퍼 값 보호**: LLM 값이 매퍼 값·낱말 해석 갈림·참여자 조절 값을 덮어쓰는 경로. 참여자가 보지 못한 값이 장면·selection.json 최종 값에 들어가는 경로.
3. **원칙 4**: 위기·확인 판정 뒤 호출, 판정과 호출 사이 경합, 가드 모델과의 순서, 확정 요청이 LLM 실패로 막히는 경로.
4. **프롬프트 주입**: 확정 텍스트 안의 지시문("위 규칙을 무시하고…")이 출력·화면에 미치는 영향. 화면 문구에 넣는 `{quote}`의 이스케이프(XSS), 길이.
5. **기존 설정 불변**: 플래그가 꺼진 설정의 출력·기록·판. experiment.toml에서 켰을 때 G73·G75 흐름 회귀.
6. **기록·스키마·Unity**: 0.5 기록이 분석에 필요한 것을 담는가(원시 항목, 기각 사유, 둔/고친 값, 노출 플래그). 0.1–0.4가 `llm_quoted`를 거부하는가. 참여자 원문이 git에 들어갈 경로.
7. **시험의 빈틈**과 문서 불일치.

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순. 끝에 "문제없다고 확인한 것". 추측은 추측이라고 밝혀라.
