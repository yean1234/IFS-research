# CP21 재검토 — G85 수정 확인

읽기 전용으로 확인한다. 파일을 고치지 않는다. 한국어로 답한다. 시험은 돌리지 않는다.

## 읽을 것
- `docs/codex-reviews/CP21.md` (앞선 지적)
- `AGENTS.md` 작업 원칙 1의 G85 예외
- `docs/validation/run-g85-rewrite/README.md`
- 커밋되지 않은 작업 트리(`git status --short`, `git diff`, 새 파일). 주로 `tools/gen3d/prompts.py`, `chatbot/ifs_chatbot/llm_rewrite.py`, `wordnet_check.py`, `llm.py`, `selection.py`, `shared/lexicon/body_part_attachment.v0.json`, `shape_english_rewrite_block.v0.json`, `shared/protocol/selection_protocol.v0.14.json`, `chatbot/tests/test_g85_rewrite.py`

`unity/Assets/XR/Settings/OpenXRPackageSettings.asset`과 `chatbot/logs/` 아래는 열지 않는다.

## 확인할 것 (항목마다 고쳐짐 / 일부 / 안 고쳐짐, 근거 파일:줄)
1. 대상 명사의 머리 낱말에 재질·장소 검사가 적용되는가(marble, cave).
2. 생성기 쪽 재검증이 서버 검증과 같은 문맥 검사(부정·과거·전언·가정·비유, 매퍼가 쓴·뺀 구간)를 하는가.
3. 원시 출력 전문과 sha256이 기록되는가.
4. 예열 요청이 본 호출과 구분돼 기록되고 참여자 글이 들어가지 않는가.
5. 빠졌던 시험(중복 인용 + 틀린 charSpan, 참여자 보기 응답에 영어 프롬프트·로컬 경로 없음)이 더해졌는가.
6. 새로 더한 것: 몸 낱말 차단(`body_part_attachments`)이 규칙 사전·G82·G85·생성기 재검증 네 곳에 모두 걸리는가. 걸렸을 때 중립 형태로 가지 않고 생성 안 함으로 가는가.
7. 새로 더한 것: 근거 꾸밈의 근거 구간 검사(용언 없음, 다른 주어, 대상에 안 붙음, 비유)가 서버와 생성기에서 같은 함수인가.
8. 수정 중 고쳤다는 버그: `_unmapped:shape` 표시 때문에 근거 꾸밈이 모두 `span_excluded`로 막히던 것. 이 수정이 매퍼가 실제로 쓴·뺀 구간 제외를 약하게 만들지 않았는가.

## 이미 알고 있는 것 (다시 지적하지 않는다)
- 보류 세트의 돌려 말하기 20문장 중 9문장이 몸 낱말 규칙을 지나간다(목적격·부사격, 목록 밖 낱말). 정상 문장 과차단도 있다.
- WordNet 첫 뜻 과차단(top, nail 등), 뜻이 다른 번역, LLM null로 중립 형태로 가는 금지 범주 낱말.
- 같은 입력의 원시 출력이 드물게 달라진다(원인 미확인).
- 「색은 보지 말고 모양만 봐 주세요」는 기존 문구(0.9.1부터)와 같은 문장이라 그대로 둔다.
- 덧붙임 줄은 실제 모델에서 나온 적이 없다.

## 답 형식
- 항목 1–8의 상태 표.
- 새로 찾은 문제(심각도, 파일:줄, 재현 입력, 수정 방향). 없으면 없다고 적는다.
