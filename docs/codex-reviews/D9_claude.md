# D9 독립 설계안 (Claude 하위 에이전트): 감정어·추상 서술에서 구체 심상으로 가는 면담 구조

프롬프트: `docs/codex-reviews/prompts/D9_prompt.md`. Codex 응답(`D9.md`)을 보지 않고 쓴 안이다.

## 1. 진단 (단계별)

| 단계 | 원인 |
|---|---|
| 첫 질문 | "어떤 느낌이 드나요?"는 감정 이름을 답으로 불러온다. 그다음 location은 자리만 묻고 '질'을 묻지 않는다. |
| find | 틀 선택에 규칙이 없다. 그래서 LLM이 anything_else를 고르고, 감정어를 되묻는 질문("'불안'에 대해 더 있나요?")은 감정 서술만 더 끌어낸다. |
| flesh_out | 프롬프트가 "이미 쓴 묘사어"를 펼치라고 하므로, 감정어만 있으면 펼칠 말이 없다고 보고 바로 `ready_to_advance`로 넘어간다. |
| 프로브 | 지시어 '그것'이 감정이면 "크기나 모양"을 묻는 질문이 어색하고, 차원마다 한 번씩만 묻는다. 세 번 다 "없어요"면 슬롯이 빈다. |
| 인용 후보 | 감정어는 object 바로 앞 순위로 밀려 있다. '기대돼요'는 `기대되/VV`라서 '-하' 어근 규칙에 걸리지 않아 후보가 없다. 용언 '설레요'는 활용형 그대로 X에 들어간다. 은유 정규식 `숨이?\s*막히`는 '막힌'·'막혀'를 놓친다. |

## 2. 설계안: Clean 3단 다리 (자리 → 질 → 무엇 같은지 → 프로브)

**흐름을 가를지.** 모든 참여자에게 같은 순서를 주되, 다리 단계 하나만 dimensionProbes의 `coveredByCategories` 방식처럼 "이미 나왔으면 건너뛴다". 판정은 규칙으로 한다.

- **형상 신호 있음**: opening부터 직전 답까지의 참여자 발화에서 `categories_in` 결과에 {form, shape, object, size, color, brightness, texture, opacity, posture} 중 하나가 있거나, ANCHOR_STOP·emotion·sensation·body_part가 아닌 일반명사(NNG) 바로 뒤에 '같'·'처럼'·'마냥'이 붙은 비유 표지가 있을 때.
- **형상 신호 없음**: 위 둘이 모두 없을 때. 판정 결과와 근거 낱말은 `capture.imageSignal`에 남기되, 흐름을 정하는 데만 쓰고 값으로는 쓰지 않는다(원칙 2).

**순서와 그 이유.** Clean Language가 상징을 키울 때 쓰는 순서를 따른다. "And where do you feel strange?" → "And what kind of strange?" → "And that's strange like what?"(Lawley & Tompkins 2000, `research_notes/자기 관련 심상 유도 질문/metaphor_elicitation.md`) 다음에 크기·모양을 묻는다. Ikemi 2015의 "how is the whole thing felt in you?" → "A rock, a big rock."과 같은 방향이다.

| 순서 | 질문 (한국어 원문) | 형식 | status·출처 |
|---|---|---|---|
| ① 자리 | "그것이 몸 안에, 몸 표면에, 아니면 몸 주변에 있나요?" | 고정(그대로) | spec |
| ② find LLM | 형상 신호가 없으면 허용 틀을 anything_else 하나로 좁힌다. like_what은 질을 물은 뒤로 미룬다. | LLM | 프로토콜 규칙 추가(draft) |
| ③ 질 | "거기에 주의를 두고 잠시 머물러 보세요. 준비가 되면 지금 알아차려지는 것을 적어 주세요." | 고정(그대로) | Gendlin handle 단계의 "What is the quality…"와 같은 역할. 예시 목록은 넣지 않는다. |
| ④ 다리(새로 넣음) | X가 있으면 "그 '{X}'{은/는} 마치 무엇 같나요?", 없으면 "지금 그것은 마치 무엇 같나요?" | 결정론 realize, LLM 없음 | 틀은 spec(like_what). X 없는 문장은 새 고정 문구 `bridge_like_what_plain`(draft), Clean "that's X like what?" |
| ⑤ flesh_out LLM | 최대 5회(그대로). 프롬프트 v1.1.0에 "감정어·감각어만 있으면 그 말을 where나 like_what으로 묻는다"를 더한다. | LLM | 프롬프트 draft |
| ⑥ 프로브 | "그것에 크기나 모양이 있나요?" / "그것에 색이나 밝기가 있나요?" / "그것에 움직임이 있나요?" | 고정(그대로) | spec |

**④를 결정론 문장으로 둔 이유.** 작은 모델이 틀을 고르면 도달률이 흔들린다. 결정론 문장으로 두면 두 조건에 같은 문장이 나간다.

**X 고르기 규칙.** ③에 대한 답의 sensation 명사·어근을 먼저, 그다음 opening 답의 emotion 명사·어근을 쓴다. 참여자 원문의 부분 문자열만 쓰고 조사는 Kiwi로 뗀다. 활용형 용언 하나뿐이면('설레요', '조여요', '숨막혀요') X를 넣지 않고 '그것' 문장을 쓴다. 활용형을 명사형으로 바꾸면 참여자가 쓰지 않은 말이 되기 때문이다.

**멈추는 조건.** 다리 질문은 1회다. ③이나 ④에 짧은 "없어요·모르겠어요·안 보여요·안 떠올라요"가 오면 기존 규칙대로 flesh_out LLM을 건너뛴다('안 보여'·'안 떠올라'를 no_more 표현에 더한다). 선택 규칙 `probe_stop_after_no = 2`(기본 꺼짐): 연속 두 번 그런 답이 오면 남은 프로브를 건너뛴다.

**끝까지 형상이 없을 때.** `imageSignal`을 시점별로 남기고 `imageless = true`로 표시한다. 장면은 기존 G19 경로를 따른다. 분석에서는 이 사례를 RQ 닮음 문항과 따로 보고한다.

**조사·어간·사전 밖 감정어.**
- '-되/VV' 어근 규칙을 더한다('기대되' → '기대').
- 사전 emotion 범주에 '기대'를 더하고 사전 버전을 올린다. emotion 범주는 슬롯을 정하지 않으므로 값 추론은 생기지 않는다.
- 은유 정규식을 `숨이?\s*막(히|힌|힐|혀|혔)`으로 고친다.
- V7에 `predicate_as_noun` 검사를 더한다. what_kind·where·like_what 틀의 X가 종결어미(EF)로 끝나면 막는다.

## 3. 원칙과의 충돌 점검

- **원칙 2.** `imageSignal`은 흐름만 정하고 슬롯에 들어가지 않는다.
- **원칙 3.** like_what은 질문 틀 6개 안에 있다. "마치"는 비유를 요청할 뿐 비유 내용을 주지 않는다. 그래도 은유 양식을 여는 약한 유도이므로 사전 등록한 결정론 문장에만 맡긴다.
- **원칙 8.** 몸에 머물게 하는 새 문구는 만들지 않고 기존 focus_hold만 쓴다. L1–L5와 확인 문구 경로를 그대로 둔다.
- **시각 양식 오염.** 다리 질문에는 '모양·보이다·모습·이미지'가 없다. 시각 차원을 처음 꺼내는 것은 지금처럼 spec 프로브이고 맨 뒤에 온다.
- **RQ 위험.** 다리 질문이 만든 형상은 함께 만든 것에 가깝다. 형상 낱말마다 처음 나온 턴(opening, focus, bridge, LLM, probe)을 `elicitedBy`에 적고 RQ 분석을 출처별로 나눈다. like_what이 기존 형상을 새 사물로 바꾸는 표류는 recall_check와 drift 기록으로 본다.
- **검증기.** 다리 문장에는 V8을 걸지 않는다(틀 + 원문 인용뿐이고, 가드 모델을 부르면 결정론이 깨진다). V1–V7·V9는 그대로 걸고, 하나라도 걸리면 X 없는 고정 문장으로 바꾼다. find 틀 제한과 V7 추가는 강화다.

## 4. 조건 1(static)과의 형평

④를 정적 조건에도 같은 규칙·같은 문장으로 넣는다(focus_hold 뒤, fleshout_open 앞). X를 넣는 것이 정적 조건의 "고정 질문" 성격을 흐린다고 보면 두 조건 모두 X 없는 문장만 쓰는 쪽이 더 엄격하다. 이 선택은 결정 기록에 남긴다.

## 5. 시험 계획

- 주 시험은 정해 둔 답 재생(결정론). 시나리오: `emo_anxious`, `emo_expect`, `emo_breathless`, `emo_stuffy`, `emo_dontknow`, `emo_scene`(장면·기억 쪽으로 가는 경우), `shape_first`(다리를 건너뛰어야 함). 오프라인 대역과 gemma4:e4b 양쪽.
- 로컬 LLM 가상 참여자는 보조 스트레스 시험으로만 쓴다(은유를 너무 쉽게 내서 성공률을 부풀린다).
- 성공 기준: 다리 도달률(목표 100%), imageSignal 오판 수, 형상 슬롯 채움 비율(v1.4와 비교), 검증기 위반률·fallback률, 어색한 질문 수, 압박 지수(첫 "없어요" 뒤 질문 수), 기본 설정에서 기존 기록과의 차이 0.
- 선행 연구 응답 자료: 축어록은 선택 편향이 있고 번역은 초안이다. 합성 대사로 다시 쓰고 출처를 적는다. 그 낱말에 맞춰 사전을 손보지 않는다. 보류 세트를 따로 둔다.

## 6. 구현 순서

1. `docs/decisions.md` 새 G 항목, `docs/chatbot-design.md` 새 절.
2. `shared/protocol/elicitation_protocol.v1.5.json` 새로 만듦(v1.4 보존): bridge 단계, `bridge_like_what_plain`(draft), `imageSignal` 절, find의 `allowedTemplatesWhenNoImage`.
3. 사전에 '기대', 안전 사전 정규식 수정.
4. `extract.py`에 `image_signal()`, `anchors.py`에 '-되' 어근 규칙과 다리 X 선택기.
5. `protocol.py` bridge 파싱, `controller.py` `_advance`에 bridge 분기, no_more 표현 확장.
6. `validator.py`에 V7 `predicate_as_noun`(설정 플래그).
7. `chatbot/prompts/v1.1.0/`(v1.0.0 보존).
8. 설정: `[interview] bridge = false` 등 기본 꺼짐. 기본 프로토콜은 v1.4.
9. 테스트: 기본 설정 golden, 두 조건의 다리 문장 동일, 형상이 있으면 건너뜀, 정규식·조사·활용형 인용.

**위험.** 규칙 판정이 사전 범위에 묶인다(사전 밖 명사만 답하면 다리를 다시 묻지만 한 번뿐). like_what이 장면·기억을 불러올 수 있다(L5로 처리). v1.5로 모은 기록은 이전 파일럿과 따로 분석해야 한다.
