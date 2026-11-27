# 프롬프트 v1.1.0 (D9, draft)

v1.0.0을 복사해 두 단계 블록만 고쳤다. `common.txt`·`stage_focus.txt`·`context.txt`는 v1.0.0과 같다.

| 파일 | 바뀐 곳 | 이유 |
| --- | --- | --- |
| `stage_find.txt` | 틀을 [이 단계에서 쓸 수 있는 질문 틀] 목록에서만 고르게 하고, 형상 묘사가 없으면 anything_else 하나뿐이라고 적음 | 프로토콜 1.5 `stages.find.allowedTemplatesWhenNoImage`(형상 신호 없으면 like_what을 focus_hold 뒤 다리 질문으로 미룬다) |
| `stage_flesh_out.txt` | 감정어·감각어만 있으면 그 말을 where·like_what 가운데 허용 목록에 있는 틀로 묻기(다리 질문을 낸 세션은 like_what이 목록에서 빠짐, CP11). 활용형('설레요')은 명사 자리 X에 쓰지 않기 | v1.0.0은 '이미 쓴 묘사어'만 펼치라고 해서 감정어만 있으면 바로 ready_to_advance로 넘어갔다(D9 진단). 검증기 V7 `predicate_as_noun`과 같은 규칙 |

- `config/bridge.toml`만 이 버전을 쓴다. 기존 설정(default·pilot·v4·mac8gb)은 v1.0.0 그대로다.
- 초안이며 연구팀 검토 전이다. 출처: `docs/codex-reviews/prompts/D9_rebuttal_prompt.md` 「메인의 판정」, `docs/codex-reviews/D9_claude.md` §2.
