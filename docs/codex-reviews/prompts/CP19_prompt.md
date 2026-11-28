너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`(G82 예외가 새로 들어감), 뼈대 `docs/design-backbone.md`, 결정 `docs/decisions.md` 맨 끝 G82 절(판정과 미리 고정한 평가 기준), 설계 `docs/codex-reviews/D15.md`·`D15_claude.md`·`D15_rebuttal.md`.
- 이번 범위: G82 첫 단계(실험 경로에 잇지 않은 오프라인 구현)의 **커밋 전 작업 트리 변경**. `git status`와 `git diff`로 보라.
  - 새 파일: `chatbot/ifs_chatbot/llm_shape.py`, `chatbot/prompts/llm_shape/llm_shape.v0.1.0.json`·`v0.1.1.json`, `shared/lexicon/shape_english_modifier_block.v0.json`, `chatbot/tests/test_g82_llm_shape.py`, `docs/validation/run-g82-llm-shape-offline/`
  - 고친 파일: `tools/gen3d/prompts.py`, `chatbot/ifs_chatbot/config.py`, `controller.py`, `llm_fill.py`
- `unity/` 변경은 보지 마라.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 같은 45문장으로 프롬프트·검증기 판을 세 번 고쳐 기준을 넘었다(과적합 위험). 새 문장으로 2차 평가를 할 예정이다.
- 검증기 0.2.0은 인용 글자가 텍스트에 한 번만 나오면 LLM이 틀리게 센 charSpan을 고친다.
- 걱정 이야기 속 사물(보고서, 휴대폰, 통장)을 막는 규칙은 아직 없다.
- 매퍼가 form.*에 쓴 구간은 `span_covered`로 기각된다(벽돌, 눈덩이). 풀 예정이다.
- 한국어 금지 목록에 참새·다람쥐가 없고 영어 보충 목록에서만 걸린다.
- 노출·채택·거절 기록은 자리만 있다. 실험 설정에서는 꺼져 있다.

## 확인할 것
1. 원칙 위반: LLM이 프롬프트 문장을 쓰게 되는 경로, 규칙 값을 덮어쓰는 경로, 위기·확인 판정 세션에서 호출되거나 캐시를 읽는 경로, 형태를 말하지 않았는데 생성으로 이어지는 경로.
2. 검증기를 빠져나가는 입력(재현 값으로): charSpan 고치기를 악용하는 경우, 인용이 여러 번 나오는 경우, 부정·과거·타인·가정·비유, 사람·몸·동물·안개·불꽃(한·영, 복합어·복수형·유니코드 닮은꼴), 꾸밈말이 붙은 영어 이름, 색·추상 명사.
3. 꺼진 설정에서 기존 출력·기록·캐시 키가 그대로인가. G82가 켜졌을 때 G77의 형태 칸만 꺼지는가.
4. 기록·캐시: 입력 해시와 검증기 텍스트 해시, 판 변화가 캐시 키에 들어가는가. 재현에 필요한 것이 빠졌는가.
5. 시험이 위를 실제로 고정하는가. 통과만 하고 아무것도 확인하지 않는 시험.
6. 오프라인 평가(`docs/validation/run-g82-llm-shape-offline/`)의 집계가 README 수치와 맞는가. 뜻 일치 판정이 후하게 매겨진 문장.

## 출력 형식
심각도(높음/중간/낮음), `파일:줄`, 재현 입력, 고칠 방향 한 줄. 문제가 없는 항목은 없다고 적어라. 추측은 추측이라고 밝혀라.
