너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
`docs/codex-reviews/CP11.md`(네 검토)의 지적을 `docs/decisions.md`의 「D9 구현 검토 CP11 판정」대로 처리했다. 고쳐졌는지만 확인한다. 새 전면 검토는 하지 않는다.

## 확인할 것
1. 지적 2(다리 뒤 like_what 재사용): `chatbot/ifs_chatbot/controller.py`의 `_llm_turn`에서 다리를 낸 세션의 허용 틀에서 like_what이 빠지고 검증기 V2가 같은 목록으로 막는가. 다리를 건너뛴 세션·기존 설정·프로토콜 1.4에 영향이 없는가. `chatbot/prompts/v1.1.0/stage_flesh_out.txt`의 바뀐 문장이 예시·선택지를 만들지 않는가. 시험은 `chatbot/tests/test_d9_bridge.py`.
2. 지적 3(부정 집계): `imageSignal.timeline[]`의 `negatedExcluded`·`negatedInEvidence`·`negated`가 `extract.py`의 evidence·excluded와 같은 뜻으로 남고 `shared/schemas/session_log.schema.json`·`docs/chatbot-design.md` §5-3과 맞는가.
3. 지적 4: `docs/handoff-D9.md`는 지웠다. 다른 문서가 이 파일을 가리키는 곳이 남아 있는가.
4. 지적 1은 반박했다(이전 형식 기록 파일 없음, 1.5 draft). 이 판단이 틀렸다는 근거(저장소 안에 이전 형식 `firstElicitedBy.kind` 값을 가진 기록·자료)가 있으면만 적어라.
5. 이번 수정으로 새로 생긴 문제(높음·중간만).

## 출력 형식
항목마다 "고쳐짐 / 안 고쳐짐 / 새 문제"와 `파일:줄`, 한두 줄 근거.
