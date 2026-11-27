# 프롬프트 v1.2.0 (프로토콜 1.6, G70 + 연구 책임자 시험 세션 결함 5, draft)

v1.1.0을 복사해 세 파일을 고쳤다. `stage_find.txt`·`stage_focus.txt`는 v1.1.0과 같다(focus 단계는 LLM 0회라 쓰이지 않는다).

| 파일 | 바뀐 곳 | 이유 |
| --- | --- | --- |
| `common.txt` | 허용 질문 틀 목록에서 `where` 줄을 뺐다 | 프로토콜 1.6 G70-a: flesh_out 허용 틀에서 where를 뺐다(공간어가 놓는 자리·거리 답을 미리 끌어당길 수 있음) |
| `stage_flesh_out.txt` | where를 언급하지 않음. 허용 목록에서만 고르기, 바로 앞 틀·이미 쓴 like_what은 목록에서 빠짐, 사물·모양 이름으로 말한 표현을 like_what의 X로 쓰지 않기, 이미 말한 차원을 다시 묻지 않기 | 결함 1·2·3·5. 같은 규칙을 컨트롤러가 허용 목록(templateRules)과 검증 V2(template_not_allowed·image_x)로 강제한다. 프롬프트는 그 목록을 모델에게 알리는 쪽이다 |
| `context.txt` | `[이미 쓴 질문 틀]`(틀 id·횟수·지금 쓸 수 없는 이유)과 `[참여자가 이미 말한 차원]`(차원 id와 참여자 원문 낱말) 두 블록을 더했다 | 결함 5. 차원 판정은 차원 프로브와 같은 출처(매퍼가 채운 슬롯 + 형상 신호, 프로토콜 1.6 `dimensionProbes.coverage`) |

- 예시 질문·선택지·참여자가 쓰지 않은 묘사어는 넣지 않았다. 새 블록의 차원은 영문 id(size·shape·color_brightness·movement)로만 적고, 괄호 안에는 참여자 원문 낱말만 넣는다. 틀도 id로만 적는다.
- LLM은 질문만 만든다. 차원 목록은 흐름(같은 질문 피하기)에만 쓰고 장면 값은 매퍼(규칙)가 확정 텍스트로만 정한다(원칙 1·2).
- `config/experiment.toml`만 이 버전을 쓴다. 다른 설정(default·pilot·v4·bridge·mac8gb)은 v1.0.0·v1.1.0 그대로다.
- 초안이며 연구팀 검토 전이다.
