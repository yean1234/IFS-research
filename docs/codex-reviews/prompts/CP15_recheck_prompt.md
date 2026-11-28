너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`, 뼈대 `docs/design-backbone.md`. 앞선 검토 `docs/codex-reviews/CP15.md`(네 지적 원문)와 설계 `docs/chatbot-design.md` 7.11.1.
- 이번 범위: CP15 지적을 고친 **커밋 전 작업 트리 변경**만 본다. 아래 파일의 `git diff`와 새 파일을 읽어라.
  - `tools/gen3d/prompts.py`(`english_shape_reasons`, `_llm_head`), `shared/lexicon/shape_english_block.v0.json`(새 파일)
  - `chatbot/ifs_chatbot/llm_fill.py`, `chatbot/ifs_chatbot/selection.py`, `chatbot/ifs_chatbot/config.py`
  - `chatbot/prompts/llm_fill/llm_fill.v0.1.1.json`(새 파일), `chatbot/tests/test_g77_llm_fill.py`
- Unity 쪽(`unity/`)과 `docs/decisions.md`, `docs/validation/`, `tools/gen3d/bench_image_models.py`의 변경은 다른 작업이다. 보지 마라.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 실제 모델로는 아직 돌리지 않았다. 구분 표시가 모델 출력에 미치는 효과는 실측 예정.
- 금지 목록은 과차단을 허용한다(handle, surface, trombone, fireplace, mantle은 일부러 기각). 규칙 형태 사전이 쓰는 feather·horn은 일부러 뺐다.
- `LLM_FILL_VERSION`은 올리지 않았다(selection.v0.5 스키마가 const로 고정). 판 변화는 promptVersion과 목록 파일 해시로 남긴다.
- 확정 뒤 이미 화면에 낸 후보의 처음 값은 걷어 내지 않는다(확정 뒤 판정이 새로 서는 경로를 찾지 못함).
- 옛 v0.1.0 프롬프트 파일을 설정에서 읽으면 시작이 멈춘다.

## 확인할 것
1. CP15 지적 4건이 각각 고쳐졌는가. 지적마다 "고쳐짐 / 일부 / 안 고쳐짐"과 근거(`파일:줄`).
2. 새 정규화 규칙을 여전히 빠져나가는 영어 형태 낱말이 있는가(사람·얼굴·동물 형상, 안개·불꽃류). 재현 값으로 적어라. 유니코드 닮은꼴 문자, 숫자 섞기, 3낱말 구에서 가운데 낱말, 불규칙 복수형, 소유격을 포함해 본다.
3. 캐시·플래그 순서 수정이 만든 새 문제(플래그가 없는 정상 세션에서 캐시가 깨지는가, skipped 기록이 분석에 필요한 것을 지우는가).
4. 구분 표시 번호 올리기가 실패하는 입력, 구분 표시 때문에 인용 charSpan이 어긋나는 경로.
5. 플래그가 꺼진 설정의 출력·기록이 그대로인가. 캐시 키에 목록 해시를 넣은 것이 꺼진 설정에 영향을 주는가.
6. 새 시험이 위 수정을 실제로 고정하는가(통과만 하고 아무것도 확인하지 않는 시험이 있는가).

## 출력 형식
먼저 지적 4건의 상태 표. 그다음 새로 찾은 문제만 심각도(높음/중간/낮음), `파일:줄`, 재현 입력, 고칠 방향 한 줄. 새 문제가 없으면 없다고 적어라. 추측은 추측이라고 밝혀라.
