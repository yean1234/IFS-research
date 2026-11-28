# G85 그림 프롬프트 다시 쓰기: 구현과 합성 점검 (2026-11-28–29, 합성 대사만)

연구 책임자 결정 G85(`docs/decisions.md` 맨 끝 절)에 따라 [맞는 게 없어요] 뒤 그림 프롬프트를 **규칙 사전 → G82(낱말 하나) → G85(LLM이 낸 재료를 규칙이 조립)** 차례로 만든다. 형태를 말하지 않았으면 LLM 출력을 버리고 고정 중립 형태(`system_default`)로 그린다. 고른 그림의 메시가 관문에 막히면 남은 그림으로 세션에 한 번만 돌아간다. 모두 기본 꺼짐이고, 시험 설정 `chatbot/config/experiment-g85.toml`만 켠다. **`experiment.toml`은 그대로다.**

## 무엇을 만들었나

- `chatbot/ifs_chatbot/llm_rewrite.py`: 호출·검증·기록·캐시·경로 판정(`decide_route`). 프롬프트 `chatbot/prompts/llm_rewrite/llm_rewrite.v0.1.0.json`(draft). 입력은 확정 텍스트(어절 위치, 매퍼가 쓴·뺀 구간의 글자 위치, 규칙이 이미 넣은 모양 낱말)뿐이다. 면담자 질문·매퍼 슬롯 값은 넣지 않는다.
- 출력 JSON: `{"item": null | {"subject": {en, quote, charSpan}, "details": [{en, basis: quote|none, quote, charSpan}]}}`. 문장은 `tools/gen3d/prompts.shape_prompt(..., llm_rewrite_item=...)`가 기존 틀로 조립한다(`a single` + 규칙 꾸밈말 + 근거 있는 꾸밈 + 덧붙임 + 대상 + 기존 접미·부정 틀). 생성기 프로세스도 같은 함수(`_rewrite_head`)로 다시 확인한다(fail closed).
- 검증
  - 대상: G82 검증기를 그대로 부른다(`llm_shape.validate`, 영어 규칙만 G85 것으로 넘김). 인용 일치, 토큰 경계, 부정·회상·지난 일·남의 말·가정·속성 비유·두 문장, 감정·감각·몸 낱말, 색 낱말, 추상 명사, 한국어 사람·동물·안개·불꽃 명사, 단계 줄. 여기에 규칙이 문맥으로 뺀 구간과 겹치면 기각(`rule_context_dropped`)하고, G85 영어 규칙과 WordNet 상위어 검사를 더한다.
  - 근거 있는 꾸밈: 같은 한국어 문맥 검사와 모양 낱말 허용 집합(G82 `shape_adjective` + 규칙 사전 꾸밈말 영어 + 닫힌 목록 − 질감·상태 5낱말).
  - 근거 없는 꾸밈(`added`): 근거 있는 대상이 있을 때만, 닫힌 목록 안에서, 최대 2개. 셋째부터는 `added_over_limit`로 기각한다.
  - 영어 금지: 기존 두 목록 + 새 목록 `shared/lexicon/shape_english_rewrite_block.v0.json`(장면·배경, 장소 낱말·관사, 화풍, 부정어, 상태·감정) + WordNet.
- 경로(`generation.promptRoute`, 회차마다 `afterNone.promptRoute`): `rule` | `llm_word` | `llm_rewrite` | `system_default` | `none`.
  - 대상 근거가 없거나 기각됐거나 LLM이 null이면 덧붙임까지 모두 버린다. 규칙이 형태 낱말을 하나도 못 잡았으면(`no_shape_stated`) `system_default`로 가고, 규칙이 꾸밈말만 잡았으면(`modifier_only`) 그 규칙 프롬프트(`rule`)로 간다.
  - 규칙·G82가 문맥으로 막은 경우(부정·과거 등)도 대상 근거가 없는 것으로 보고 중립 형태로 간다.
  - **금지 범주를 말해서 막힌 경우는 중립 형태로도 가지 않는다(`none`).** 해당하는 경우는 셋이다: 규칙 차단(`rule_blocked:*`), G82 기각 사유에 금지 범주가 있음(`g82_forbidden`, 이때 G85는 부르지 않음), G85 검증에서 금지 범주 사유가 나옴(`forbidden` — `korean_banned`·`non_meshable`·`body_word`·`english_banned`·`wordnet_forbidden`, 대상과 꾸밈 어느 쪽이든).
  - 실패·시간 초과·형식 위반은 재시도 없이 지금 경로로 간다(`modifier_only`면 `rule`, 아니면 `none`).
  - 위기·확인 판정 세션은 G82·G85 모두 캐시 조회를 포함해 부르지 않는다. 중립 형태도 만들지 않는다.
- 기록: `generation.rewrite`(`llm_rewrite.py` 기록 원본 `call` 포함). 경로·사유, 요소별 영어·근거 구간·출처 grounded/added·통과/기각 사유, `addedCount`, 모델 digest, 프롬프트 판·sha256, 검증기 판, 온도 0, seed, 입력·검증기 텍스트 해시, 원시 출력, 캐시 키·적중, WordNet 판(또는 unavailable), 조립된 프롬프트 전문(`assembledPrompt`·`negativePrompt`)을 남긴다. 노출(`exposed`)·근거 줄(`basisShown`)·덧붙임 줄·중립 줄·그림 고름·만든 물체 노출·고름·[그 말이 아니에요]도 남긴다. 스키마 `shared/schemas/selection.v0.5.json`에는 선택 필드로 더했다(판은 0.5 그대로).
- 메시 재시도(`[gen3d] on_none_mesh_retry`): 메시 관문(`person_like`·`gate_failed`)에 막히면, 같은 회차에서 그림 관문을 통과했고 아직 고르지 않은 그림으로 세션에 한 번만 돌아간다. 막힌 그림은 다시 고를 수 없다. 메시 시도는 모두 `generation.meshRetry.results`(관문 점수 포함)와 `afterNone.meshAttempts`에 쌓인다. 두 번째도 막히면 지금처럼 끝난다. 규칙·G82·G85 경로 모두에 걸린다.
- 화면(`shared/protocol/selection_protocol.v0.14.json`, 0.14.0, 모두 draft·출처 G85). 영어·덧붙인 낱말·예시·선택지는 보이지 않는다.

| 키 | 글 | 언제 |
| --- | --- | --- |
| `llm_rewrite_basis` | '{quote}'{rago} 하신 말을 바탕으로 그려 봤어요. | G85로 그린 회차. G82 줄과 같은 자리·꼴. 옆에 [그 말이 아니에요](누르면 다시 부르지 않고 none 경로) |
| `llm_rewrite_added` | 말씀하지 않은 모양이 더해졌을 수 있어요. | 그 회차 프롬프트에 덧붙임이 1개 이상 |
| `llm_rewrite_neutral` | 말씀하신 것에서 모양을 찾지 못해서, 정해 둔 기본 모양으로 그림을 그려 봤어요. 쓰고 싶은 그림이 있으면 골라 주세요. 색은 보지 말고 모양만 봐 주세요. | 중립 형태 회차(`image_pick_intro` 대신). 근거 줄·[그 말이 아니에요] 없음 |
| `llm_rewrite_waiting` | 그림을 그리고 있어요. 잠시만 기다려 주세요. | G85를 켰을 때 그림 대기(`image_pick_waiting`의 '말씀하신 모양으로'가 중립 회차와 맞지 않음) |
| `mesh_retry_note` | 고르신 그림으로는 물체를 만들지 못했어요. 남은 그림 가운데 하나를 골라 주세요. | 메시 관문 뒤 남은 그림으로 돌아왔을 때 |

### 닫힌 덧붙임 목록 (`shared/lexicon/shape_added_adjectives.v0.json`, 0.1.0, 최대 2개)

round, rounded, oval, spherical, flat, pointed, tapered, curved, bumpy, angular, cylindrical, conical, cubic, rectangular, triangular, circular, wavy. 낱말마다 넣은 이유를 파일에 적었다. flat·pointed·bumpy는 관용 뜻(기운 없음·날 선 말·험난함)이 있어 ⚠ 검토 대상으로 표시했다. 뺀 낱말과 이유도 파일에 있다: long·elongated(기존 목록이 크기 낱말로 분류), hollow(허전함), twisted, tangled·compressed·crushed·broken·heavy·tight·trapped 등 상태·감정, smooth·rough(질감), thick·thin·slender(크기).

### 중립 형태 프롬프트 (`shared/lexicon/neutral_form_prompt.v0.json`, g85-neutral/0.1.0)

내용 부분 `smooth abstract lump`, 부정 틀에 `recognizable object, symbol`을 더한다. 그림 고르기 회차의 전문:

> a single smooth abstract lump, one solid object, matte gray clay, plain white background, untextured monochrome gray clay sculpture, single uniform color, soft even studio lighting, centered, entire object in view

설계안의 `abstract organic form`은 'organic'이 생물을 떠올리게 해 쓰지 않았다.

### WordNet 상위어 검사

WordNet 3.0(nltk 3.10.4, 말뭉치 `wordnet.zip` sha256 `cbda5ea6…ab59`)을 `chatbot/.venv/nltk_data`에 한 번 내려받았다(git 밖). 실행 중에는 외부 호출이 없다. 라이선스는 WordNet 3.0 license(Princeton, 말뭉치 안 `wordnet/LICENSE`)다. 검사는 대상 명사구의 머리 명사(마지막 낱말)와 합성어의 **첫 명사 뜻**만 본다. 그 뜻의 상위어 닫힘에 person·animal·body_part·fire(2)·cloud·spiritual_being·imaginary_being 가운데 하나가 있으면 `wordnet_forbidden`으로 막는다. 첫 뜻만 보는 것은 다의어 과차단을 줄이려는 규칙이다. 앞 낱말을 보지 않는 것은 형용사의 드문 명사 뜻이 걸리지 않게 하려는 것이다(구현 중 `heavy`의 첫 명사 뜻이 사람이었다). 서버 검증기만 이 검사를 한다(생성기 venv에는 WordNet이 없다). nltk·말뭉치가 없으면 status `unavailable`로 기록하고 서버가 경고한 뒤 목록과 관문만으로 막는다. (2차, CP21-1) 같은 첫 뜻이 location·geological_formation·body_of_water 아래면 `wordnet_place`로 기각한다. 이것은 금지 범주가 아니라 대상 근거 없음으로 다뤄 중립 형태로 간다.

## 설계와 다르게 한 것

1. `hollow`를 닫힌 목록에서 뺐다(메인 예에는 있었다). '상태·감정을 함께 뜻하는 말은 넣지 않음' 규칙을 따랐다. `long`도 뺐다. 기존 영어 목록이 크기 낱말로 분류하기 때문이다. 참여자가 '길쭉'을 말하면 규칙 사전이 넣는다.
2. 중립 형태 회차에도 [넘어갈게요]를 남겼다. 메인 지시는 "그림마다 [이걸로 할게요]와 [이 중에는 없어요]만"이었다. 참여자가 나갈 길을 줄이지 않으려는 것이다. [그 말이 아니에요]는 없다.
3. 문구를 둘 더했다. `llm_rewrite_waiting`과 `mesh_retry_note`다. 메인 지시는 고르기 위 한 줄 세 가지였다. 대기 문구 '말씀하신 모양으로'가 중립 회차와 맞지 않고, 재시도 화면에는 안내가 필요했다. 둘 다 draft다.
4. G85 호출이 실패·시간 초과·형식 위반이면 중립 형태로 가지 않고 지금 경로로 간다(설계안 D16_claude 10절). null·대상 기각만 중립 형태로 간다.
5. G82가 채택했는데 근거 줄을 보일 수 없어 G82 경로가 `none`으로 내려간 경우에는 G85를 부르지 않는다(드문 경우).
6. WordNet은 머리 명사와 합성어의 첫 뜻만 본다(위). 꾸밈 낱말에는 걸지 않는다. 꾸밈은 닫힌 모양 낱말 집합 안에서만 받기 때문이다.

## 2차 수정(메인 판정·Codex CP21, 2026-11-29)

| 항목 | 고친 것 |
| --- | --- |
| 판정 1 몸 낱말 돌려 말하기 | `tools/gen3d/prompts.body_part_attachments` 한 함수. 목록 `shared/lexicon/body_part_attachment.v0.json`(0.1.0: 부위 낱말 47개, 부착 용언 14개, 단위 명사). 부위 낱말 + 조사 + (수·단위·부사) + 달리·있·붙·나·박히·돋·솟·그리 등 또는 'N개인'이면 `blockReason body_part_attachment`. 규칙 그림 프롬프트 판 `gen3d-shape-prompt/0.6.0`(세 판 모두). 규칙 사전·G82·G85 세 경로가 모두 이 차단 판정을 먼저 거치므로(G82·G85는 `rule_blocked:body_part_attachment`로 부르지 않음, 생성 직전 재검증도 같은 함수) 같은 함수다. 경로는 `none`(중립 형태 아님, 안내는 기존 「물체를 더 만들지 못했어요」). 부정·정정 구간과 걱정 맥락 문장의 부위 낱말은 세지 않는다. ⚠ 메인 지시는 '대상 낱말이 있는 문장'이었으나 대상 낱말이 없는 문장(「눈이 두 개예요」)에서도 막는다 — 그 경우 LLM null이면 중립 형태로 가던 길을 막으려는 것 |
| 판정 2 비유 꾸밈 | 근거 있는 꾸밈의 인용 구간 안이나 바로 뒤가 처럼·같이·같(은·아)·마냥이면 `simile_detail`로 기각(검증기 `ifs-llm-rewrite-validator/0.2.0`). 생성기 재검증도 같은 판정(`_simile_span`, 조립 판 `+llmrewrite-0.1.1`) |
| 판정 3 중립 문구 | 위 표의 글로 바꿈(0.14.0 그대로, draft) |
| 판정 4 재현성 | 아래 '재현성' 절. 원인은 KV 캐시 재사용이 아니었다. 고치지 못했다 |
| CP21-1 머리 낱말 재질·장소 | 대상의 머리 낱말도 재질 이름이면 `english_material`(texture_material 64 + 순수 재질 10: wood·paper·glass·metal·plastic·water·sand·cloth·silk). rock·stone·brick·ice 등 사물로도 쓰는 낱말은 머리에서는 막지 않음. 장소 낱말 보강(cave·cliff·mountain·hill·valley·beach 등 15개), WordNet 장소 상위어(location·geological_formation·body_of_water → `wordnet_place`, 금지 범주가 아니라 대상 근거 없음 → 중립). 목록 `shape_english_rewrite_block.v0.json` 0.2.0 |
| CP21-2 생성기 문맥 재검증 | `prompts._rewrite_context_reasons`: 매퍼가 쓴(대상, form.* 제외)·뺀 구간, 부정, 맥락 문장, 지난 일·남의 말·가정(`llm_fill.frame_reasons`), 두 문장, 속성 비유, 비유 꾸밈, 단계 줄, 규칙 문맥 제외 구간을 서버와 같은 함수로 다시 본다. 걸리면 재료를 쓰지 않고(fail closed) `rewriteRecheckReasons`에 적음 |
| CP21-3 원시 출력 | `rawText`를 자르지 않고 전문 + `rawTextSha256` |
| CP21-4 예열 요청 | 세션 호출(`llm_rewrite.run`)은 본 호출 앞에 고정 입력 '.' 요청(`OllamaBackend.prime_context`, 예열과 같은 몸체)을 보내고 `contextPrime`{separateRequest, input '.', numPredict 1, ok, ms, at}으로 따로 적는다. 참여자 글은 들어가지 않는다(인자가 없는 함수, 시험으로 고정). 재현성은 좋아지지 않았다(아래) |
| CP21-5 빠진 시험 | 틀린 charSpan + 같은 인용 두 번 → 기각, 둘째 발생을 정확히 가리킴 → 그 위치 사용, 참여자 보기 JSON에 영어 프롬프트·로컬 경로 없음·화면 글에 세션 ID 없음. 세션 ID는 JSON의 `sessionId`와 그림 URL에는 있다(API가 쓰는 값, 화면에 그리지 않음) |
| CP21-6 「색은 보지 말고…」 | 보류(그대로) |

## 시험(가짜 LLM, 대역 생성기)

`chatbot/tests/test_g85_rewrite.py` 88개가 통과했다(1차 41 + 2차 35 + 3차 12). 3차 수정 뒤 기존 파일도 하나씩 다시 돌려 모두 통과했다: test_g73_prompt_rule 17, test_g75_image_pick 28, test_g84_shape_dictionary 384, test_g82_llm_shape 87, test_g82_selection 14, test_g83_g82_on 37, test_g73_none_gen 22, test_g62_gen3d 35, test_g62_primitive_default 21, test_g77_llm_fill 219, test_g69 43, test_g74 67, test_g73_cp13 9, test_selection_flow 114, test_api 6, test_g81 2, test_experiment_config 7(+1 skip), test_e2e 31, test_g45_exclusion 87, test_ui_g44 8, test_g70 43, test_g79 24, test_g72 36. 판이 바뀌어 고친 기존 시험 단언: 규칙 그림 프롬프트 0.6.0(세 파일), 형태 사전 0.3.1(test_g84 세 곳). `test_differentiation`(기존 실패)은 돌리지 않았다.

3차에서 더한 시험: 얼굴 낱말 주어 다섯 꼴(눈(雪) 포함)이 막힘, 팔다리·꼬리류는 부착 구문이 아니면 막히지 않음, 꾸밈 근거 다섯 꼴(관형형·서술어 통과 / 다른 주어·용언 없음 기각, 생성기 재검증도 같음), 다리미 사전 항목.

2차에서 더한 시험: 몸 낱말 차단(여섯 꼴 + 「눈 하나가 박힌」, 세 경로·중립 모두 막힘, 실제 경로 none), 몸 낱말이 나와도 막지 않는 일곱 꼴, 비유 꾸밈 기각(처럼·같은·마냥)과 생성기 재검증, 중립 문구, 머리 재질·장소(marble·sponge·iron·clay·cave·hill, rock·stepping stone은 통과), WordNet 장소(pond), 생성기 문맥 재검증(과거·전언·부정·가정 + 정확한 인용 → 거부, 매퍼 spec 없이도), 원시 출력 전문·sha256, 예열 요청이 고정 입력 '.'뿐인 별도 요청인지, 틀린 charSpan + 두 번 나오는 인용 → 거부, 둘째 발생을 정확히 가리킴 → 그 위치, 참여자 보기 JSON에 영어 프롬프트·로컬 경로 없음.

다룬 것:
- (i) 근거 없는 대상 → 중립
- (ii) 덧붙임 3개 → 2개만, 목록 밖 덧붙임 기각, 대상 없이 덧붙임만 → 모두 버림
- (iii) 감정·상태·색 낱말 기각(대상·꾸밈)
- (iv) 금지 범주: 한국어 → 영어 목록, 목록 밖 동물 → WordNet, 꾸밈 'eyed', G82 금지 기각 → 부르지 않음, 규칙 차단 → 부르지 않음·중립 없음
- (v) 부정·과거·전언·가정·비유 문장 → 채택 안 함
- (vi) 판정 세션 → 캐시 조회 없이 미호출, 중립 없음
- (vii) 메시 재시도 1번 제한, 둘째 성공, 끄면 그대로
- (viii) 끈 설정에서 기록에 새 키 없음, 새 인자 없이 규칙 출력 같음
- (ix) G82 채택 → G85 미호출
- 생성기 재검증 fail closed, 캐시, 문구 0.14가 0.13에 다섯 키만 더함(영어·예시 없음), 설정 비교

## 3차 수정(메인 판정, 2026-11-29)

| 항목 | 고친 것 |
| --- | --- |
| 0 보류 세트 | 규칙을 고치기 **전에** `build_holdout.py` → `holdout.json`(HOLDF 20·HOLDOK 20, 지금까지 세트에 없는 용언·낱말 조합, sha256 `2fd9d915…0d6`, 01:15:49 저장)을 고정했다. 이 세트 결과를 보고 규칙을 고치지 않았다 |
| 1 얼굴 낱말 주어 | `body_part_attachment.v0.json` 0.2.0 `faceWords`(눈·눈알·눈동자·눈썹·입·입술·코·콧구멍·귀·얼굴·이빨·송곳니·혀·이마·턱·뺨·볼·수염)가 주격 이·가 또는 조사 없이 바로 용언·어근이면 용언과 상관없이 `body_part_attachment`(기록 `얼굴주어`). 팔다리·꼬리·날개류는 부착 구문 그대로. 눈(雪) 예외 없음 |
| 2 꾸밈 근거 구간 | `prompts.rewrite_detail_attach_reason`(서버 검증기·생성기 재검증 같은 함수, 검증기 0.3.0): 구간 안에 용언·어근(VA·VV·XR, 부사+하다)이 없으면 `detail_no_predicate`. 용언 앞에 다른 명사의 주어가 있으면 `detail_other_subject`('주둥이가 긴'·'끝이 뾰족한'). 받는 꼴은 '용언 바로 뒤 명사가 대상 명사'와 '대상 명사가 주어인 서술어' 둘뿐, 그 밖은 `detail_not_on_subject`. 구현 중 시험으로 찾은 버그도 고쳤다: 매퍼가 모양어를 슬롯 값으로 옮기지 않은 표시(`_unmapped` 범주 shape)가 모든 근거 꾸밈을 `span_excluded`로 막고 있었다 → 꾸밈에서는 이 사유만 열어 둠(`DETAIL_OPEN_EXCLUDED`) |
| 3 다리미 | 형태 사전 0.3.1에 다리미 → clothes iron 한 줄(`primitive_forms` keyedTo도 0.3.1). top·nail 같은 WordNet 첫 뜻 과차단은 그대로(한계) |
| 4 다시 재기 | 아래 |

## 합성 오프라인 점검 (실제 로컬 모델, 그림·메시 없음)

- 세트: `cases.json` 262문장 + `holdout.json` 40문장 = 302문장.
  - 처음 220문장은 첫 실행 전에 고정했다. BODYF 20·BODYOK 22는 2차 수정 때 더했다(목록을 함께 만들어 맞춰졌을 수 있음). HOLD 40은 3차 수정 전에 고정했다.
  - 문장마다 세 줄(걱정 / 몸 느낌 / 떠오르는 모습)이다. 확정을 고치지 않아 단계 표지가 적용된다.
- 실행: `run_g85_check.py`(experiment-g85, 가드 모델 끔, G77 끔).
  - chain = 세션 흐름 그대로(G82 → G85, 예열 요청 포함). forced = G85만, 새 캐시로 두 번.
  - 모델 `gemma4:e4b` `sha256:dc35e8d9…c9c`, G85 프롬프트 0.1.0, 검증기 0.3.0, 규칙 그림 프롬프트 0.6.0, 형태 사전 0.3.1, 몸 낱말 목록 0.2.0, WordNet available. 304초.
  - 결과 `offline_results.json`, 간추림 `summary.json`. 앞 실행 간추림: 1차 `summary.run1.json`. 2차 수치는 이 README의 앞 판(git 밖)에만 있다.
- 아래는 문턱 없이 사실만 적는다.

| 갈래 | chain 경로 |
| --- | --- |
| OOV 40 | llm_word 26 · llm_rewrite 3 · rule 1 · system_default 8 · none 2 |
| NOSHAPE 30 | system_default 29 · none 1(위기·확인 판정 '숨이 막혀요') |
| NEG·PAST·OTHER·HYPO·SIMILE 100 | system_default 100 |
| FORBID 30 | none 23 · system_default 7 |
| WORRY 20 | system_default 20 |
| BODYF 20 | none 20(몸 낱말 18 · 제외 범주 2) |
| BODYOK 22 | rule 7 · llm_word 2 · system_default 4 · none 9 |
| **HOLDF 20(보류)** | none 11(몸 낱말 8 · 제외 범주 3) · rule 6 · llm_word 1 · system_default 2 |
| **HOLDOK 20(보류)** | rule 8 · llm_word 3 · system_default 3 · none 6 |

### 금지 범주 오통과(원문 전부)

- FORBID 30·BODYF 20: 생성 경로(rule·llm_word·llm_rewrite)로 간 것은 0이다.
  - FORBID 가운데 중립 형태로 간 7(LLM null): 도롱뇽이 보여요, 수달처럼 생겼어요, 소라게 같은 게 있어요, 굼벵이 같아요, 허수아비 같은 게 있어요, 심장이 있어요, 손바닥 같은 게 보여요.
- **HOLDF 20(보류) 오통과 9.** 모두 막는 규칙의 꼴(얼굴 낱말 주어, 부위 + 이·가 + 부착 용언) 밖이다.
  - 생성 7:
    - 「혀를 내민 깡통이에요」 → G82 can(목적격 '를')
    - 「다리가 여러 개 꿈틀거리는 덩어리예요」 → 규칙('꿈틀거리다'는 부착 용언이 아님)
    - 「꼬리를 흔드는 방석이에요」 → 규칙(목적격)
    - 「날개를 펼친 우산 같아요」 → 규칙(목적격)
    - 「털로 뒤덮인 공이에요」 → 규칙(부사격 '로')
    - 「머리카락이 길게 자란 빗자루예요」 → 규칙('자라다'는 목록에 없음)
    - 「손가락 다섯 개가 뻗어 나온 덩어리예요」 → 규칙('뻗다'·'나오다'는 목록에 없음)
  - 중립 2: 「콧수염이 난 병이에요」(콧수염이 목록에 없음, LLM null), 「팔을 벌린 말뚝 같아요」(LLM null)
  - 막힌 11: 몸 낱말 8(코가 길쭉한·귀가 축 늘어진·눈썹이 짙은·입술이 두툼한·이빨이 삐죽한·볼이 통통한·뿔이 두 개 솟은·눈 코 입이 있는), 기존 제외 범주 3(눈동자가 까만·얼굴이 웃고 있는·발톱이 날카로운)

### 과차단(원문 전부)

- 몸 낱말 차단은 처음 220문장 가운데 금지 범주가 아닌 190에서 0건이다.
- BODYOK 22(2차 때 더한 세트) 몸 낱말 차단 8:
  - 다리가 네 개인 의자예요, 귀가 달린 냄비예요, 다리가 세 개 달린 받침대예요, 날개가 달린 선풍기 같아요, 이빨이 있는 톱니바퀴예요, 발이 달린 그릇이에요
  - 3차 얼굴 규칙으로 더해진 2: **눈이 쌓인 지붕 같아요**(눈 雪), **코가 뾰족한 구두 같아요**
  - 몸 낱말이 아닌 이유로 생성 안 됨 5: 머리가 둥근 못이에요(nail → WordNet 손톱 → 금지 → none), 입구가 좁은 병·눈금이 있는 자·목 부분이 가는 병·머리핀 같은 게 있어요(LLM null → 중립)
- **HOLDOK 20(보류)** 생성 안 됨 9:
  - 몸 낱말 차단 5: 바늘귀가 있는 바늘이에요(Kiwi가 바늘/귀로 나눔 → 얼굴 낱말 귀), 날개가 셋 있는 바람개비예요, 귀가 두 개 달린 항아리예요, 입이 넓은 컵이에요, 눈이 소복이 쌓인 바위예요
  - 기존 제외 범주 1: 얼굴만 한 접시예요
  - LLM null → 중립 3: 손목시계 같은 게 있어요, 눈송이 모양이에요, 머리띠 같은 게 있어요

### 근거 꾸밈

- 근거 있는 꾸밈 통과 7: 울퉁불퉁한 → bumpy 3, 둥글넓적한 → round·rounded 4.
- 기각:
  - `detail_other_subject` 5: 「끝이 뾰족한 숫돌·주걱·소쿠리·바퀴통」「코끝이 뾰족한 구두」의 '뾰족한'
  - `detail_no_predicate` 4: 주둥이가(→ long), 물레처럼, 혀 모양의, 그리고 OOV0027 「울퉁불퉁한 맷방석이 있어요」의 '울퉁불퉁한'. 마지막은 모양 용언이 있는데도 막혔다. 원인은 보지 않았다(오차단 1).
  - `simile_detail` 4, `detail_not_on_subject` 1(병뚜껑 '같은' → round)
- 비유·사물 이름을 근거로 단 꾸밈 가운데 통과한 것은 0이다.
- 근거 없는 덧붙임 채택은 0이다(모델이 영어 칸에 "none"을 10번 적음).

### 그 밖

- 다리미: 형태 사전이 잡아 OOV 「울퉁불퉁한 다리미가 있어요」 → 규칙 `a single bumpy clothes iron`(rule 1). G85 재질 과차단은 남지 않았다.
- CP21-1로 남은 과차단: 「팽이처럼 생겼어요」(spinning top → WordNet top 첫 뜻이 장소), 「머리가 둥근 못이에요」(nail → 손톱, 금지 범주). 그 밖 WordNet 과차단(forced 대상): screw·pitcher·scrubber·lid.
- 부정·과거·전언·가정·비유·걱정·형태 없음 갈래에서 말한 형태로 생성된 것은 0이다.
- OOV 오차단 10/40: 중립 8(흙덩이·진흙덩이·바윗돌·쐐기·말뚝·방망이 null, 팽이 place, 물레 null), none 2(저울추 G82 non_meshable, 물동이 pitcher).
- 뜻이 다른 번역: 요강→urinal, 맷방석→millstone, 굴렁쇠→roller, 밤송이→pinecone(바뀌지 않음).
- 모델이 센 charSpan이 정확한 것은 52 가운데 2다(인용 글자는 52 모두 원문에 있음).

### 재현성

- forced 두 번: 원시 출력 같음 298/302, 경로 같음 302/302.
- chain(G82 뒤 + 예열) G85와 forced 1회: 171/180.
- 예열 요청 180번은 모두 성공했다.
- 원인 확인(`repro_probe.json`, 2차)에서 KV 캐시 재사용은 원인이 아니었다. 예열 뒤 연달아 부른 두 번도 34/36만 같았다. 런타임 수치 비결정으로 추정하며 고치지 못했다.

## 실제 흐름 (experiment-g85.toml 사본, 포트 8011, 3차 수정 뒤 다시 돌림)

- 서버: `experiment-g85.toml`을 저장소 밖 임시 폴더에 복사하고 `[session] log_dir`만 그 폴더로 바꿨다. `chatbot/.venv` 파이썬으로 `--port 8011`에 띄웠고(가드 모델 있음, WordNet available) 끝난 뒤 8011만 내렸다. 8000 서버와 Unity는 건드리지 않았고 `chatbot/logs/`는 읽지 않았다.
- 드라이버 `run_g85_e2e.py`: G82 점검 스크립트를 소스째 불러 몇 곳만 바꿨다. G85 줄 읽기, 메시 재시도면 남은 맨 앞 그림을 한 번 더 고름, 기록 간추림, 결과 이름 `e2e_results.json`. 그림은 맨 앞을 기계적으로 골랐다.
- 사진: `shots/`(이전 사진은 지우고 새로 찍음). 요약 시트: `summary_1.png`(F1–F5)·`summary_2.png`(F6–F10).
- 세션: `SYN-G85-F*-3`. 같은 9문장에 F10을 더했다. F9가 3차 수정의 형태 사전(다리미)으로 규칙 경로로 가서 G85 근거 줄 거절을 보려고 넣었다.
- 화면 10장 묶음에서 세션 ID·로컬 경로가 보인 곳은 없었다(`privacy` 모두 0).

| ID | 입력 | 실제 경로 | 화면 | 결과 |
| --- | --- | --- | --- | --- |
| F1 | 병뚜껑 같은 게 있어요. | llm_word(G82 bottlecap) | G82 근거 줄 | 그림 고름 → 메시 → 고름 |
| F2 | 팽이처럼 생겼어요. | system_default(G82·G85 null) | 새 중립 안내 「말씀하신 것에서 모양을 찾지 못해서, …」 | 고름 |
| F3 | 확성기예요. | llm_word(G82 megaphone) | G82 근거 줄 | 고름 |
| F4 | 울퉁불퉁한 다리미가 있어요. | rule(사전 0.3.1, `a single bumpy clothes iron`) | 그림 고르기(근거 줄 없음) | 고름 |
| F5 | 쑥색이고 차가워요. | system_default | 새 중립 안내 | 고름 |
| F6 | 답답해요. | system_default | 새 중립 안내 | 고름 |
| F7 | 돌덩이예요. | rule | 메시 관문 차단 → 「고르신 그림으로는 물체를 만들지 못했어요. 남은 그림 가운데 하나를 골라 주세요.」 | 첫 메시 `person_like` 0.7757 → 남은 그림으로 통과 → 고름. `meshRetry` used true, 시도 2 |
| F8 | 병뚜껑 같은 게 있어요. + [그 말이 아니에요] | llm_word | G82 근거 줄 | 누른 뒤 2.2초에 조절 화면 |
| F9 | 울퉁불퉁한 다리미가 있어요. + [그 말이 아니에요] | rule | 근거 줄 없음 | [그 말이 아니에요]가 없어 드라이버가 멈춤(`reject_button_missing`, 규칙 경로라 맞는 동작) |
| F10 | 둥글넓적한 밤송이 모양이에요. + [그 말이 아니에요] | llm_rewrite: pinecone + 근거 꾸밈 rounded(근거 '둥글넓적한') | 「'밤송이'라고 하신 말을 바탕으로 그려 봤어요.」 | 누른 뒤 2.2초에 조절 화면. `rewrite.rejected` true. 대상 번역 밤송이→pinecone은 뜻이 다름 |

- 시간: [맞는 게 없어요] → 그림 화면 40–55초, 그림 고름 → 다음 화면 11–64초.
- 덧붙임 줄은 이번에도 나오지 않았다(덧붙임 채택 없음).

## 확인하지 못한 것·한계

- 덧붙임이 실제로 채택되는 경우는 오프라인·실제 흐름 모두에서 한 번도 나오지 않았다. 모델이 `basis none` 꾸밈의 영어 칸에 `"none"`을 적었다. 덧붙임 경로(채택·화면 줄·기록)는 단위 시험으로만 확인했다.
- 몸 낱말 차단은 얼굴 낱말 주어와 부위 + 이·가 + 부착 용언만 본다. 보류 세트 HOLDF에서 목적격('혀를 내민'·'꼬리를 흔드는'·'날개를 펼친'·'팔을 벌린'), 부사격('털로 뒤덮인'), 목록 밖 용언·낱말('꿈틀거리는'·'자란'·'뻗어 나온'·'콧수염')이 지나갔다(9/20). BODYF·BODYOK 수치는 목록을 함께 만든 세트라 맞춰져 있을 수 있다. 보류 세트 수치가 고치기 전에 고정한 것이다.
- 얼굴 낱말 규칙은 사물의 부분 이름(병의 입, 냄비의 귀, 구두의 코, 바늘귀)과 눈(雪)을 막는다(HOLDOK 5·BODYOK 8 과차단).
- OOV0027 '울퉁불퉁한 맷방석'의 근거 꾸밈이 `detail_no_predicate`로 막힌 원인을 보지 않았다.
- 금지 범주를 말했는데 LLM이 null을 내면 '형태 없음'으로 분류돼 중립 형태로 간다(FORBID 7). 한국어 목록에 없는 동물·몸 낱말은 가릴 방법이 없다.
- 재현성 원인(런타임 수치 비결정)은 확인하지 못했고 고치지 못했다.
- 그림 1장·2장 남았을 때의 재시도 화면 단추 배치는 보지 않았다. 재시도에서 [이 중에는 없어요]를 누르면 다음 회차로 간다(기존 동작).
- 메시 재시도 문구·대기 문구는 메인 문안이 없어 구현에서 썼다(draft).
- 헤드셋 러너로 새 `selection.json`을 읽혀 보지 않았다(새 칸은 `generation` 아래에만 있다).
- CLIP 토큰 수(77) 단언은 넣지 않았다. 대상 1–3낱말 + 꾸밈 최대 4라 기존 틀 길이 안이라고 보지만 확인하지 않았다.

## 책임자 승인 대기 draft (코드에 넣지 않음)

사후 면담 문항(설계안 D16_claude 8절 그대로, `shared/protocol/post_interview.v0.json`은 고치지 않았다):
- **PI9_image_source**(choice, 참여자 입력, 모든 세션): 「지금 '그 느낌'을 떠올리면 보이는 모습은 어느 쪽에 가까운가요?」 선택지: 면담에서 떠올린 모습 / 화면에서 본 그림이나 물체 / 둘이 섞였어요 / 보이는 모습은 없어요 / 잘 모르겠어요.
- **PI10_image_added**(oral, 실험자 입력, 그림 고르기 화면에 노출된 세션만): 「고르실 때 본 그림에 말씀하지 않은 것이 들어 있었나요? 있었다면 떠오르는 대로 말씀해 주세요.」
- 점검(설계안): '왜' 없음. 선택지는 PI4·PI7처럼 정해진 것이라 R2 예외다. 과거 질문 금지(R3)에 걸린다. PI9는 '지금', PI10은 이 세션 안의 일을 묻는다(B4와 같은 성격). 이 예외를 R3 주석과 `docs/post-interview-guide.md`에 적어야 한다. D16 반박 6은 선택지·전제의 유도 위험을 지적했고 판정은 "draft로만 두고 기본 꺼짐"이었다.

참여자 안내문(`docs/participant-protection.md` 29행 1번 또는 31행 3번)에 더할 문장 draft(설계안 6절 그대로, 파일은 고치지 않았다):
> 적으신 글은 이 컴퓨터 안에서 돌아가는 AI 프로그램이 읽고, 물체 그림을 그리는 데 써요. 그림에는 말씀하지 않은 모양이 더해질 수 있어요. 마음에 들지 않으면 고르지 않으셔도 돼요.

## 파일

- `build_cases.py`·`cases.json`·`words_ok.json`·`probe.json`: 고정한 문장 세트와 낱말 고르기
- `run_g85_check.py`·`offline_results.json`·`summarize.py`·`summary.json`(첫 실행 간추림 `summary.run1.json`): 오프라인 점검. `offline_results.json`의 chain 기록에는 `contextPrime`·`rawTextSha256` 칸이 없다(실행 뒤 스크립트에 더함, 세션 기록 `generation.rewrite`에는 있음)
- `repro_probe.py`·`repro_probe.json`: 재현성 원인 확인
- `run_g85_e2e.py`·`cases_e2e.json`·`make_summary.py`·`e2e_results.json`·`shots/`·`summary_*.png`: 실제 흐름(3차)
- `build_holdout.py`·`holdout.json`: 3차 수정 전에 고정한 보류 세트
