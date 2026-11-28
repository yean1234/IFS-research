# G84 규칙 형태 사전 넓히기: shape_prompt_en 0.2.1 → 0.3.0 (2026-11-28)

출처: 2026-11-28 G84, 연구 책임자 결정: 원칙 2 유지 + 사전 넓히기. 문헌 조사(`docs/research/R2_llm_prompt_mediation.md`) 뒤 작업 원칙 2("말하지 않은 것을 추론하지 않는다")를 유지한다. LLM이 프롬프트를 자유롭게 쓰게 하지 않고, 참여자가 자주 쓸 형태 명사를 규칙 사전에 더해 LLM 없이 같은 한국어 낱말이 언제나 같은 영어 형태 이름을 내게 했다. 모든 문장은 합성이다.

## 무엇을 바꿨나

- 규칙 경로 구조: `tools/gen3d/prompts.shape_prompt()`가 확정 텍스트를 Kiwi로 나눈 뒤 `shared/lexicon/shape_prompt_en.v0.json`의 `entries`(ko = Kiwi 토큰 배열, en = 영어)와 맞춘다. 명사 항목은 붙여 쓴 명사 연속 전체와 같을 때만 맞는다(`_noun_run_bounds`). 맞은 형태 명사 가운데 처음 나온 것이 중심 명사다. 실험 설정에서는 세션 매퍼(v2) spec으로 한 번 더 거른다(매퍼가 버리거나 전혀 적지 않은 명사는 뺌). 낱말을 더할 자리는 이 파일의 `entries`이고, 기존 항목과 같은 꼴(`pos noun`, `slot shape_noun`, 필요하면 `thin`·`familiar`·`plural`)로 넣었다. 코드·틀·자리 규칙·차단 목록은 바꾸지 않았다. 매퍼 사전(layer1·base_shapes)은 건드리지 않았다(장면 슬롯이 바뀌지 않음).
- `shared/lexicon/shape_prompt_en.v0.json` 0.3.0: 형태 명사 **117낱말, 129항목**. Kiwi가 문맥에 따라 둘로 나누는 낱말(돌+덩어리, 눈+덩이, 유리+구슬 등)은 나뉜 꼴도 같은 영어로 따로 넣었다(기존 조개+껍데기와 같은 방식). 87낱말은 G81·G82 점검과 평가 세트(offline·eval2·eval3의 P 부류, G81·G82·G83 실제 흐름)에 나온 사전 밖 형태 명사, 30낱말은 같은 부류(덩어리·판·그릇·끈 꼴)의 일상 사물이다. `notIncluded`에 뺀 낱말과 이유를 더했다.
- `shared/lexicon/primitive_forms.v0.json` 0.1.1: `keyedTo.lexiconVersion`을 0.3.0으로. 더한 낱말은 모두 사물이라 단순 도형 목록은 그대로다.
- 영어: 모두 소문자 한 낱말이고 `english_shape_reasons`(G77 금지 목록)와 `llm_shape_english_reasons`(G82 꾸밈말 금지 목록)를 모두 통과한다. 이 검사로 바꾼 것: 궤짝 chest(몸 부위) → crate, 유리구슬 marble(재질) → bead, 깡통 tin(재질) → can(뒤에 깡통은 뺌), 스펀지 sponge(질감) → 뺌.
- 시험에서 "사전 밖 낱말" 예로 쓰던 조약돌·돌덩이·자갈·벽돌·방석·베개·주전자를 0.3.0에 없는 디딤돌·고구마·몽돌·차돌·쿠션·바가지로 바꿨다(`chatbot/tests/test_g82_llm_shape.py`, `test_g82_selection.py`, `test_g83_g82_on.py` 세션 시험, `test_g77_llm_fill.py` 1–600행). 매퍼가 그 낱말을 같은 방식(form.type 비움 + unlisted_noun, 또는 blob)으로 적는지 먼저 확인했다. 과거 점검 기록(G81–G83 README·results·스크립트)은 고치지 않았다. `tools/gen3d/tests/test_g62.py`의 사전 판 확인은 0.2.1부터 이미 어긋나 있어 0.3.0으로 고쳤다.

## 점검 (`check_g84.py` — 이 절의 수치는 규칙 0.4 이하 결과 `check_results.rules-0.4.json`)

같은 문장을 더하기 전 사전(git `8d0fa03`의 0.2.1)과 더한 뒤 사전(0.3.0)으로 규칙 그림 프롬프트에 넣었다. 매퍼 spec은 실험 설정(experiment.toml, 백엔드만 offline)의 scene_builder로 만들었다. "생성 시작" = 규칙 프롬프트 `status ok`([맞는 게 없어요] 뒤 LLM 없이 그림 생성이 시작됨).

| 점검 | 문장 수 | 더하기 전 생성 시작 | 더한 뒤 생성 시작 | 더한 뒤 G82 호출 |
| --- | --- | --- | --- | --- |
| 긍정 틀 3개(「X예요」「X 같은 게 있어요」「가슴 앞에 X이 있어요」) | 351 | 0 | **350** | 1 |
| 부정(「X은 아니에요」「X 같은 건 없어요」) | 234 | 0 | 0 | 234 |
| 과거(「예전에는 X였어요」「처음엔 X 같았어요」) | 234 | 0 | **228** | 6 |
| 타인(「친구가 X 같대요」「다들 그게 X라고 했어요」) | 234 | 0 | **226** | 8 |
| 가정(「X면 좋겠어요」「아마 X일 거예요」) | 234 | 0 | **229** | 5 |
| 속성 비유(「X처럼 단단해요」「X처럼 무거워요」) | 234 | 0 | **234** | 0 |
| 걱정 한 줄(「X 때문에 걱정이에요」「어제 X를 잃어버려서 속상해요」) | 234 | 0 | **230** | 4 |
| 걱정 줄 X + 형상 줄 「공 같은 게 있어요」 — 중심 명사가 공 | 117 | 117(공) | **3**(114는 X가 중심 명사) | — |

- 긍정: 실패 1건은 「양동이예요」다. Kiwi가 양동(NNP)+이(VCP)로 나눠 사전에 맞지 않는다. 이때는 예전처럼 G82 LLM이 불린다. 「그물을」(그+물)도 같은 종류다.
- G82·G77: 규칙이 중심 명사를 잡으면 `rule_route`가 `rule_has_shape`라 G82 LLM을 부르지 않는다(긍정 350/351). 규칙 프롬프트가 `no_shape_stated`가 아니므로 G77의 형태 낱말 칸(shape_noun)도 열리지 않는다(G82를 끈 설정에서도, 세션 시험으로 확인). G77의 다른 빈 칸(색·form.type 등)은 그대로다(실제 흐름 S1에서 G77이 form.type을 '돌덩이' 인용으로 제안했다).
- 지시한 세 문장: 「돌덩이는 아니에요」는 막힌다(규칙 `negated`). 「예전에는 돌덩이였어요」와 「돌덩이처럼 단단해요」는 **0.3.0에서 rock으로 생성이 시작된다**(0.2.1에서는 규칙이 시작하지 않았고 G82가 LLM을 불렀다. G82 점검 E8에서 「돌덩이처럼 단단해요」는 LLM null로 의도대로 막혔다).

### 미해결 문제를 넓히는가: 예 (이 절은 규칙 0.4 이하 기준 — 아래 "후속: 생성 경로 문맥 규칙"에서 막음)

`docs/decisions.md` "매퍼가 부정·과거·전언·가정 문장에서 색을 채운다"와 같은 뿌리가 형태 쪽 규칙 그림 프롬프트에도 있다. 생성 경로(`prompts.shape_prompt`, 세션 매퍼 판단 `_mapper_verdict`)에 있는 차단은 **부정·정정(`negated`·`mapper_negated`), 회상 문장(`context_sentence`: '~던 장면' 꼴만), 장소·크기 자리**뿐이다. 과거·전언·가정·속성 비유·걱정 문장을 막는 규칙은 없다. G82 LLM 경로는 검증기(past_or_former·reported_speech·hypothetical·simile_of_predicate·non_shape_stage_line)로 이 꼴을 막았는데, 낱말이 규칙 사전에 들어가면 G82가 불리지 않아 그 검증기를 거치지 않는다. 그래서 사전에 더한 낱말 수만큼 이 문제가 넓어진다. 기존 사전 낱말(공·상자 등)은 이미 같은 상태였다.

G82 평가 세트로 본 크기(규칙 경로만, 부류별 생성 시작 수 전 → 후):

| 세트:부류 | 문장 | 전 → 후 | 같은 세트의 G82 LLM 채택(검증기 0.4–0.5 당시) |
| --- | --- | --- | --- |
| eval2 PAST | 100 | 9 → 92 | 0 |
| eval2 HYPO | 100 | 9 → 91 | 0 |
| eval2 OTHER | 100 | 9 → 68 | 0 |
| eval2 SIMILE | 100 | 9 → 92 | 17(eval2 당시 검증기) |
| eval3 PAST | 50 | 0 → 24 | 0 |
| eval3 HYPO | 50 | 0 → 35 | 0 |
| eval3 OTHER | 50 | 0 → 29 | 0 |
| eval3 SIMILE | 200 | 0 → 200 | 0 |
| offline F(부정·과거·전언·가정 8) | 8 | 0 → 6 | — |
| eval2·eval3 NEG / WORRY / PERSON / ANIMAL / MIST / NONE | 50–100 | 변화 없음 | — |
| eval2 P · eval3 P · offline P(형태를 말함) | 48 · 50 · 19 | 4 → 39 · 0 → 29 · 3 → 18 | 24 · 30 · — |

평가 세트 WORRY 부류는 걱정 낱말(노트북·보고서 등)을 사전에 넣지 않아 바뀌지 않았다. 대신 위 표의 마지막 줄처럼, 걱정 줄에 더한 사물 낱말(가방·열쇠 등)이 있으면 형상 줄의 형태 명사를 밀어내고 중심 명사가 된다(처음 나온 형태 명사 규칙, 117 중 114). G82 검증기의 단계 규칙(non_shape_stage_line)에 해당하는 것이 규칙 경로에는 없다. (후속 규칙 0.5.0에서 이 다섯 꼴을 막았고 xfail을 풀었다.)

### 동음이의어·형태가 아닌 쓰임 (22문장)

새 항목이 잡히지 않음 20: 붓다(붓고·부어), 모자(어머니와 아들), 나사(NASA), 유튜브, 먹이사슬, 블록체인, 모자라다, 동전만 해요·수박만 한(크기 비교), 의자에·이불 속·텐트 안·울타리 밖(장소), 눈이 와요, 양동작전, 판단 등.
잡힘 2: 「동전 세 개 크기 정도요」(수 표현이 끼면 크기 자리 규칙이 다음 토큰만 봐서 놓침 — 기존 낱말 '탁구공 두 개 크기'도 같음), 「주사위는 던져졌어요」(관용 표현). 첫 점검에서 「시계 방향으로 돌아요」「깡통 전세 때문에 걱정이에요」「첫 단추를 잘못 끼운 느낌이에요」가 잡혀 시계·깡통·단추는 사전에서 뺐다.

## 실제 흐름 (4문장, `run_g84_e2e.py` → `results.json`의 `cases`, `shots/`, `summary_1.png`)

`chatbot/config/experiment.toml` 사본(`[session] log_dir`만 저장소 밖 임시 폴더)으로 `chatbot/.venv` 파이썬 서버를 `--port 8011`에 띄우고, G83 점검 스크립트(`run-g83-g82-on/run_g83_e2e.py`)를 그대로 불러 돌렸다(드라이버는 websockets·Pillow가 있는 시스템 파이썬). 그림은 맨 앞(seed 0) 그림을 기계적으로 골랐다. 끝난 뒤 8011 서버만 내렸다. 8000 서버·Unity는 건드리지 않았고 `chatbot/logs/`는 읽지 않았다. 모델: 면담 `gemma4:e4b` `sha256:dc35e8d9…c9c`, 그림 SDXL base 1.0, 형태 TripoSG, 관문 CLIP ViT-L/14(문턱 0.5).

| ID | 문장 | G82 점검 때 | 0.3.0 규칙 프롬프트 | G82 | 결과 |
| --- | --- | --- | --- | --- | --- |
| S1 | 돌덩이예요. | E4: LLM null, 생성 안 함 | a single rock | 부르지 않음(rule_has_shape) | 그림 3장 통과 → 고름 → **메시가 관문에서 막힘**(person_like 0.776, 'a human face' 0.425). 조절 화면에 「물체를 더 만들지 못했어요」 |
| S2 | 돌덩이 같은 게 있어요. | E3: LLM null, 생성 안 함 | a single rock | 부르지 않음 | S1과 같은 프롬프트·seed라 같은 그림·메시(캐시) → 같은 관문 차단 |
| S3 | 조약돌이 하나 있어요. | E1: LLM이 pebble로 메움 | a single pebble | 부르지 않음 | 그림 고름 → 메시 → 고름(generated_chosen). 근거 줄·[그 말이 아니에요]는 나오지 않음(LLM 경로가 아님) |
| S4 | 쇳덩이가 있어요. | (점검 안 함) | a single lump | 부르지 않음 | 그림 2장(seed 2 관문 0.987로 막힘) → 고름 → 메시 → 고름 |

네 문장 모두 [다 고쳤어요]까지 갔고 화면에 세션 ID·로컬 경로는 없었다(`privacy` 0). 시간: [맞는 게 없어요] → 그림 38–47초, 그림 고름 → 다음 화면 11–50초.

찾은 문제: **'a single rock' seed 0 메시가 사람 얼굴로 판정돼 막힌다**(S1·S2). 그림 단계 관문은 0.001로 통과했다. 사전이 rock을 내게 된 뒤 「돌덩이」 문장은 이번 실행에서 매번 이 메시로 간다(같은 프롬프트·seed). 다음 seed나 [이 중에는 없어요] 2회차는 보지 않았다. boulder로 바꾸면 달라지는지도 보지 않았다.

## 시험

- 새 시험 `chatbot/tests/test_g84_shape_dictionary.py`: 384 통과(규칙 0.5.0 뒤, xfail 없음). 문맥 규칙 7꼴·형태 진술 4꼴 유지·단계 규칙·매퍼 spec 불변·G82가 되살리지 않음 7건을 더함. 낱말 117개 각각 두 틀에서 중심 명사·영어·G82 미호출·G77 칸 닫힘, 영어 금지 목록, 부정 117, 동음이의어 17문장, 세션에서 G82 호출 0, G77 형태 칸 닫힘.
- 파일 하나씩 돌림: test_g82_llm_shape 87, test_g82_selection 14, test_g83_g82_on 37, test_g77_llm_fill 219, test_g62_primitive_default 21, test_g73_none_gen 22, test_g73_prompt_rule 17, test_g73_cp13 9, test_g75_image_pick 28, test_g62_gen3d 35, test_g81_candidate_asset_order 2, test_g69_shape_priority 43, test_base_shapes 71, test_g45_exclusion 87, test_selection_flow 114 — 규칙 0.5.0 뒤 모두 통과(test_g73_prompt_rule의 '천' 확인 한 줄과 판 확인 세 곳을 고침). `tools/gen3d/tests/test_g62.py` 39 통과(trimesh가 있는 gen3d-venv 파이썬).

## 확인하지 못한 것

- 사전에 넣은 낱말이 실제 참여자 말에서 얼마나 나오는지(합성 문장만 봄). 낱말별 그림·메시 품질은 S1–S4 네 낱말만 봤다.
- 다른 문장 꼴(「X를 안고 있어요」 같은 목적어 자리, 여러 형태 명사가 섞인 문장)에서 중심 명사 선택.
- 매퍼(v2)의 form.type·base는 바꾸지 않아, 이 낱말들의 절차 후보(0번 후보)는 예전처럼 기본 덩어리 등이다.

## 파일

- `check_g84.py`, `check_results.json`(positive·shouldNotStart·worryThenShape·evalSets·homonym·specified): 사전 전후 비교
- `run_g84_e2e.py`, `make_summary.py`, `cases.json`, `results.json`(문장별 원시 결과, 로컬 경로는 가림), `shots/`, `summary_1.png`: 실제 흐름
- 원본 세션 기록·그림·메시 축소판·생성 산출물은 git 밖(임시 폴더)에 있다.

## 후속: 생성 경로 문맥 규칙 (규칙 판 gen3d-shape-prompt/0.5.0, 2026-11-28)

위 "미해결 문제를 넓히는가: 예" 보고 뒤 메인 지시로 생성 경로에서 막았다. 사전 0.3.0은 이 규칙과 함께 쓴다.

- 무엇: `tools/gen3d/prompts.shape_prompt`가 사전에 맞은 낱말마다 G77·G82 검증기와 **같은 함수**로 문맥을 본다(복사하지 않음).
  `llm_fill.frame_reasons`(과거·이전 / 타인·전언 / 가정), `llm_fill.simile_of_predicate`(속성 비유 — `_check_item`에서 함수로 떼어 냄,
  동작 같음) + `llm_shape._simile_of_shape_verb`('X처럼 생겼어요'는 형태 진술로 둠, G82와 같은 구분), `llm_shape.line_stage_reason`
  (G82 `non_shape_stage_line` — `validate`도 이 함수로 바꿈). 걸린 낱말은 쓰지 않고 `dropped`에 `reason`(첫 사유)·`frameReasons`를 남긴다.
  다른 유효한 형태 명사가 있으면 그것이 중심 명사, 없으면 `no_shape_stated`(G82를 켠 설정이면 LLM을 부르는 기존 경로).
  부정·회상 문장·장소·크기는 전과 같다. 꾸밈말(동그랗다 등)도 같은 문맥 규칙(과거·전언·가정·단계)을 받는다(형태 낱말이 든 문장이면 함께 막힘).
- 단계 규칙: 세션의 `llm_shape.line_stages`가 applied(확정 텍스트를 고치지 않았고 줄 = 면담 답 1:1)일 때만 건다. 허용 단계는 G82 프롬프트
  파일의 `lineStageRule.allowedStages`(focus·flesh_out) — G82를 끈 설정도 설정의 G82 프롬프트 파일 것을 읽는다. 서버(선택 단계 precheck·
  start·G82 경로 판정·G77 형태 칸 판정)와 생성기(입력 줄 `lineStageRule`)가 같은 값을 쓴다.
- 매퍼(IFSSceneSpec 확정 스펙)는 바꾸지 않았다. 설정 플래그 없이 항상 건다.
- 판·캐시: `SHAPE_BUILDER_VERSION` 0.2.0 → 0.5.0, `..._MAPPER` 0.3.0+mapper-v2 → 0.5.0+mapper-v2, `..._IMAGE_PICK` 0.4.0+imagepick
  → 0.5.0+imagepick. G82 캐시 키는 규칙 판(`rule.builderVersion`)을 이미 품는다. G77 캐시 키에 규칙 판과 단계 규칙을 더했다.
  생성기 캐시 키는 프롬프트 글이라 그대로다(같은 글이면 같은 산출물).
- G82가 되살리지 않는가: 규칙이 뺀 낱말을 가짜 LLM이 그대로 인용해도 G82 검증기가 같은 사유(past_or_former·reported_speech·
  hypothetical·simile_of_predicate·non_shape_stage_line)로 기각한다(`test_g84_shape_dictionary.py` 7건).

### 전후 수치 (사전 0.3.0, 같은 문장 세트 — 규칙 0.4 이하 → 규칙 0.5.0)

| 문장 세트 | 문장 | 생성 시작 전 | 생성 시작 후 |
| --- | --- | --- | --- |
| 긍정 틀 3개 | 351 | 350 | 350(새로 막힌 것 0) |
| 부정 | 234 | 0 | 0 |
| 과거 | 234 | 228 | **0** |
| 타인·전언 | 234 | 226 | **0** |
| 가정 | 234 | 229 | **0** |
| 속성 비유 | 234 | 234 | **0** |
| 걱정 한 줄(단계 표지 없음) | 234 | 230 | 230 (아래 참고) |
| 걱정 줄 X + 형상 줄 「공 같은 게」(단계 표지 있음) — 중심 명사가 공 | 117 | 3 | **117** |
| eval2 PAST · HYPO · OTHER · SIMILE | 각 100 | 92 · 91 · 68 · 92 | **0 · 0 · 0 · 0** |
| eval3 PAST · HYPO · OTHER · SIMILE | 50 · 50 · 50 · 200 | 24 · 35 · 29 · 200 | **0 · 0 · 0 · 0** |
| eval2 NEG · NONE(기존 낱말이 걱정 줄에 있던 9건) | 각 100 | 9 · 9 | 0 · 0 |
| offline F(부정·과거·전언·가정) | 8 | 6 | 0 |
| eval2 P · eval3 P · offline P(형태를 말함) | 48 · 50 · 19 | 39 · 29 · 18 | 32 · 27 · 18 |
| 형태를 말했지만 지난 시제(「가슴에 X가 있었어요」「X가 낡았어요」) | 234 | (재지 않음) | **0** — 233건 past_or_former로 막힘 |

- 걱정 한 줄 230건: 단계 표지가 없는 경우(확정 텍스트를 고친 세션, 한 줄 확정)다. 「어제 X를 잃어버려서 속상해요」도 이 230에 든다 —
  frame_reasons의 과거 표지(선어말 어미 었·았·였, 예전·처음 등)가 이 문장에는 없다('어제'는 목록에 없음). 단계 표지가 applied인 세션에서는 걱정 줄(find)이
  막힌다(위 117/117, 평가 세트 WORRY 0).
- 과하게 막히는 것(알려진 한계, 고치지 않음): eval2 P에서 7건(「…좀 낡았어요」 4 → past_or_former, 「가만히 보면 X 모양이에요」 3 →
  hypothetical), eval3 P에서 2건(「잘 보면 X예요」 → hypothetical). 지난 시제로 본 것을 이야기한 문장(「가슴에 X가 있었어요」)도 모두 막힌다.
  G77·G82 검증기와 같은 규칙이라 그쪽에서도 같은 문장이 기각된다. 이때는 생성하지 않고 기존 none 경로(조절 화면)로 간다.
- offline R 「예전엔 공이었는데 지금은 조약돌 같아요」: 전에는 공(0.2.1)·조약돌(0.3.0) 가운데 처음 나온 공이 중심 명사였고, 이제 공이 과거로
  빠져 pebble이 된다.
- 동음이의어 22문장: 잡힘 2 → 1(「주사위는 던져졌어요」가 과거로 빠짐. 「동전 세 개 크기 정도요」는 그대로 잡힘).
- 점검 기록: `check_results.json`(규칙 0.5.0, 위 "후" 열 — 이 파일의 before는 사전 0.2.1 + 규칙 0.5.0), `check_results.rules-0.4.json`(규칙 0.4 이하,
  위 "전" 열). 평가 세트의 단계 표지는 그 평가 세션 기록(`results.json`의 `lineStages`)을 그대로 썼다.

### 바뀐 출력(꺼진 설정·기존 시험)

- 모든 규칙 프롬프트의 `builderVersion`(위 세 판). 시험 `test_g73_prompt_rule.py`(0.2.0)·`test_g75_image_pick.py`(0.4.0+imagepick·0.3.0+mapper-v2)의
  판 확인을 0.5.0으로 고쳤다.
- 과거·전언·가정·속성 비유·형태를 묻지 않은 단계 줄의 사전 낱말(기존 낱말 포함)로 만들던 프롬프트가 막히거나 다른 명사로 바뀐다
  (G62 기본 후보 경로·G73·G75·G82·G77 형태 칸 판정 모두 — 설정과 무관). 그 밖의 문장은 글자 그대로 같다.
- 실제 흐름(S1–S4)은 규칙 0.5.0 전에 돌렸다. 네 문장 모두 현재형이라 프롬프트는 같다(다시 돌리지 않음).

## 낱말별 영어와 근거 (117낱말)

| # | 한국어 | 영어 | 사전 항목(Kiwi 꼴) | 표시 | 출처 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 돌덩이 | rock | 돌덩이 | familiar | 점검·평가 세트 | 돌의 덩어리. boulder는 큰 바위(바위가 이미 boulder)라 크기를 싣지 않는 rock을 고름 |
| 2 | 돌덩어리 | rock | 돌덩어리 · 돌+덩어리 | familiar | 같은 부류 | 돌덩이와 같은 말 |
| 3 | 바윗덩이 | boulder | 바윗덩이 | familiar | 같은 부류 | 바위(boulder)의 덩어리 |
| 4 | 바윗덩어리 | boulder | 바윗덩어리 | familiar | 점검·평가 세트 | 바윗덩이와 같은 말 |
| 5 | 쇳덩이 | lump | 쇳덩이 | — | 점검·평가 세트 | 쇠의 덩어리. 재질(쇠)은 프롬프트에 싣지 않으므로 덩이(lump)와 같은 형태 이름 |
| 6 | 흙덩이 | clod | 흙덩이 | — | 같은 부류 | 흙 덩어리를 뜻하는 영어 명사 하나 |
| 7 | 얼음덩어리 | lump | 얼음+덩어리 | — | 점검·평가 세트 | 얼음 재질은 싣지 않음. 덩어리 → lump |
| 8 | 얼음덩이 | lump | 얼음덩이 · 얼음+덩이 | — | 같은 부류 | 얼음덩어리와 같은 말 |
| 9 | 눈덩이 | snowball | 눈덩이 · 눈+덩이 | familiar | 점검·평가 세트 | 눈을 뭉친 덩어리. '눈'(눈·눈동자) 단독은 넣지 않고 붙은 낱말만 |
| 10 | 눈뭉치 | snowball | 눈+뭉치 | familiar | 같은 부류 | 눈덩이와 같은 말 |
| 11 | 조약돌 | pebble | 조약돌 | familiar | 점검·평가 세트 | 작고 둥근 돌 |
| 12 | 자갈 | gravel | 자갈 | familiar, plural | 점검·평가 세트 | 잔돌 여럿(복수 명사로 표시) |
| 13 | 벽돌 | brick | 벽돌 | familiar | 점검·평가 세트 | 벽돌 |
| 14 | 맷돌 | millstone | 맷돌 | familiar | 같은 부류 | 둥근 돌판 두 짝 |
| 15 | 블록 | block | 블록 | familiar | 같은 부류 | 네모난 덩이(장난감·건축 블록) |
| 16 | 타일 | tile | 타일 | familiar | 같은 부류 | 얇은 네모 판 |
| 17 | 통나무 | log | 통나무 | familiar | 같은 부류 | 베어 낸 나무 줄기 토막 |
| 18 | 고드름 | icicle | 고드름 | familiar | 점검·평가 세트 | 아래로 뾰족한 얼음 막대 |
| 19 | 판때기 | board | 판때기 | thin, familiar | 점검·평가 세트 | 넓적한 판의 낮춤말. 판(flat panel)보다 일상 사물에 가까운 board |
| 20 | 널빤지 | plank | 널빤지 | thin, familiar | 점검·평가 세트 | 넓고 긴 나무판 |
| 21 | 판자 | plank | 판자 | thin, familiar | 같은 부류 | 널빤지와 같은 뜻 |
| 22 | 방석 | cushion | 방석 | familiar | 점검·평가 세트 | 앉는 납작한 깔개 |
| 23 | 베개 | pillow | 베개 | familiar | 점검·평가 세트 | 베개 |
| 24 | 이불 | quilt | 이불 | thin, familiar | 점검·평가 세트 | 덮는 두툼한 천. blanket은 담요에 씀 |
| 25 | 담요 | blanket | 담요 | thin, familiar | 같은 부류 | 담요 |
| 26 | 수건 | towel | 수건 | thin, familiar | 점검·평가 세트 | 수건 |
| 27 | 매트 | mat | 매트 | thin, familiar | 같은 부류 | 바닥 깔개 |
| 28 | 원반 | disc | 원반 | — | 같은 부류 | 납작한 원판 |
| 29 | 동전 | coin | 동전 | familiar | 점검·평가 세트 | 동전 |
| 30 | 거울 | mirror | 거울 | familiar | 점검·평가 세트 | 거울 |
| 31 | 도마 | board | 도마 | thin, familiar | 점검·평가 세트 | 넓적한 판(판때기와 같은 board). cutting board는 두 낱말 |
| 32 | 바구니 | basket | 바구니 | familiar | 점검·평가 세트 | 바구니 |
| 33 | 양동이 | bucket | 양동이 | familiar | 점검·평가 세트 | 양동이 |
| 34 | 냄비 | pot | 냄비 | familiar | 점검·평가 세트 | 냄비 |
| 35 | 뚝배기 | pot | 뚝배기 | familiar | 점검·평가 세트 | 흙으로 빚은 냄비. 재질은 싣지 않음 |
| 36 | 주전자 | kettle | 주전자 | familiar | 점검·평가 세트 | 주전자 |
| 37 | 찻잔 | teacup | 찻잔 | familiar | 점검·평가 세트 | 찻잔 |
| 38 | 머그잔 | mug | 머그잔 | familiar | 같은 부류 | 머그잔 |
| 39 | 밥그릇 | bowl | 밥그릇 · 밥+그릇 | familiar | 점검·평가 세트 | 그릇(bowl)과 같은 형태 |
| 40 | 쟁반 | tray | 쟁반 | familiar | 같은 부류 | 쟁반 |
| 41 | 대야 | basin | 대야 | familiar | 같은 부류 | 넓은 물그릇 |
| 42 | 장독 | crock | 장독 | familiar | 점검·평가 세트 | 장을 담는 독. 항아리(jar)보다 큰 질그릇 crock |
| 43 | 드럼통 | barrel | 드럼통 | familiar | 같은 부류 | 원통 통. drum은 악기와 겹쳐 barrel |
| 44 | 궤짝 | crate | 궤짝 | familiar | 같은 부류 | 나무 상자. chest는 몸 부위(가슴)라 금지 목록에 걸려 crate |
| 45 | 나무상자 | box | 나무+상자 | familiar | 점검·평가 세트 | 상자(box)와 같은 형태. 재질(나무)은 싣지 않음 |
| 46 | 가방 | bag | 가방 | familiar | 같은 부류 | 가방 |
| 47 | 봉지 | bag | 봉지 | thin, familiar | 같은 부류 | 비닐·종이 봉지 |
| 48 | 보따리 | bundle | 보따리 | familiar | 같은 부류 | 천으로 싼 짐 |
| 49 | 봉투 | envelope | 봉투 | thin, familiar | 점검·평가 세트 | 봉투 |
| 50 | 모래주머니 | sandbag | 모래주머니 · 모래+주머니 | familiar | 점검·평가 세트 | 모래를 넣은 주머니 |
| 51 | 쌀자루 | sack | 쌀자루 · 쌀+자루 | familiar | 점검·평가 세트 | 자루(sack)와 같은 형태 |
| 52 | 화분 | flowerpot | 화분 | familiar | 점검·평가 세트 | 화분 |
| 53 | 깔때기 | funnel | 깔때기 | familiar | 점검·평가 세트 | 깔때기 |
| 54 | 프라이팬 | skillet | 프라이팬 · 프라이+팬 | familiar | 점검·평가 세트 | 프라이팬. pan은 넓은 뜻(냄비·쟁반)이라 뜻이 좁은 skillet |
| 55 | 쇠사슬 | chain | 쇠사슬 · 쇠+사슬 | thin, familiar | 점검·평가 세트 | 쇠사슬 |
| 56 | 사슬 | chain | 사슬 | thin, familiar | 같은 부류 | 사슬 |
| 57 | 철사 | wire | 철사 | thin, familiar | 같은 부류 | 철사 |
| 58 | 노끈 | twine | 노끈 | thin, familiar | 같은 부류 | 가는 끈 |
| 59 | 호스 | hose | 호스 | thin, familiar | 점검·평가 세트 | 호스 |
| 60 | 파이프 | pipe | 파이프 | familiar | 점검·평가 세트 | 관 |
| 61 | 튜브 | tube | 튜브 | familiar | 같은 부류 | 관·튜브 |
| 62 | 털실타래 | skein | 털+실타래 · 털실+타래 | thin, familiar | 점검·평가 세트 | 털실을 감은 타래. 영어 한 낱말이라 skein(실타래 0.2.1은 ball of yarn) |
| 63 | 그물 | net | 그물 | thin, familiar | 점검·평가 세트 | 그물 |
| 64 | 용수철 | coil | 용수철 | thin, familiar | 같은 부류 | 용수철. spring은 계절·샘과 겹쳐 coil |
| 65 | 유리구슬 | bead | 유리구슬 · 유리+구슬 | familiar | 점검·평가 세트 | 구슬(bead)과 같은 형태. marble은 재질 낱말(꾸밈말 금지 목록)에 걸림 |
| 66 | 야구공 | ball | 야구공 | familiar | 같은 부류 | 공(ball)과 같은 형태(축구공과 같은 꼴) |
| 67 | 골프공 | ball | 골프공 · 골프+공 | familiar | 같은 부류 | 공(ball)과 같은 형태 |
| 68 | 주사위 | dice | 주사위 | familiar | 점검·평가 세트 | 주사위. die는 '죽다'와 같은 꼴이라 dice |
| 69 | 톱니바퀴 | gear | 톱니바퀴 | familiar | 점검·평가 세트 | 톱니바퀴 |
| 70 | 타이어 | tire | 타이어 | familiar | 점검·평가 세트 | 타이어 |
| 71 | 반지 | ring | 반지 | familiar | 점검·평가 세트 | 반지. 고리(ring)와 같은 영어 |
| 72 | 목걸이 | necklace | 목걸이 | thin, familiar | 점검·평가 세트 | 목걸이 |
| 73 | 왕관 | crown | 왕관 | familiar | 점검·평가 세트 | 왕관 |
| 74 | 골무 | thimble | 골무 | familiar | 점검·평가 세트 | 골무 |
| 75 | 모자 | hat | 모자 | familiar | 점검·평가 세트 | 모자 |
| 76 | 신발 | shoe | 신발 | familiar | 점검·평가 세트 | 신발 |
| 77 | 열쇠 | key | 열쇠 | familiar | 점검·평가 세트 | 열쇠 |
| 78 | 자물쇠 | padlock | 자물쇠 | familiar | 점검·평가 세트 | 자물쇠. lock은 머리채 뜻이 있어 padlock |
| 79 | 나사 | screw | 나사 | familiar | 점검·평가 세트 | 나사 |
| 80 | 자석 | magnet | 자석 | familiar | 같은 부류 | 자석 |
| 81 | 닻 | anchor | 닻 | familiar | 점검·평가 세트 | 닻 |
| 82 | 깃발 | flag | 깃발 | thin, familiar | 점검·평가 세트 | 깃발 |
| 83 | 우산 | umbrella | 우산 | familiar | 점검·평가 세트 | 우산 |
| 84 | 의자 | chair | 의자 | familiar | 점검·평가 세트 | 의자 |
| 85 | 사다리 | ladder | 사다리 | familiar | 점검·평가 세트 | 사다리 |
| 86 | 숟가락 | spoon | 숟가락 | familiar | 점검·평가 세트 | 숟가락 |
| 87 | 국자 | ladle | 국자 | familiar | 점검·평가 세트 | 국자 |
| 88 | 연필 | pencil | 연필 | familiar | 점검·평가 세트 | 연필 |
| 89 | 빗자루 | broom | 빗자루 | familiar | 점검·평가 세트 | 빗자루 |
| 90 | 붓 | brush | 붓 | familiar | 점검·평가 세트 | 붓. 용언 '붓다'(VV)는 명사 태그가 아니라 맞지 않음 |
| 91 | 지우개 | eraser | 지우개 | familiar | 점검·평가 세트 | 지우개 |
| 92 | 비누 | soap | 비누 | familiar | 점검·평가 세트 | 비누 |
| 93 | 망원경 | telescope | 망원경 | familiar | 점검·평가 세트 | 망원경 |
| 94 | 돋보기 | magnifier | 돋보기 | familiar | 점검·평가 세트 | 돋보기 |
| 95 | 나침반 | compass | 나침반 | familiar | 점검·평가 세트 | 나침반 |
| 96 | 주판 | abacus | 주판 · 주+판 | familiar | 점검·평가 세트 | 주판 |
| 97 | 모래시계 | hourglass | 모래시계 | familiar | 같은 부류 | 모래시계 |
| 98 | 옷걸이 | hanger | 옷걸이 | familiar | 점검·평가 세트 | 옷걸이 |
| 99 | 지팡이 | cane | 지팡이 | familiar | 점검·평가 세트 | 지팡이 |
| 100 | 울타리 | fence | 울타리 | familiar | 점검·평가 세트 | 울타리 |
| 101 | 텐트 | tent | 텐트 | familiar | 점검·평가 세트 | 텐트 |
| 102 | 우체통 | mailbox | 우체통 | familiar | 점검·평가 세트 | 우체통 |
| 103 | 절구 | mortar | 절구 | familiar | 점검·평가 세트 | 절구 |
| 104 | 삽 | shovel | 삽 | familiar | 점검·평가 세트 | 삽 |
| 105 | 갈퀴 | rake | 갈퀴 | familiar | 점검·평가 세트 | 갈퀴 |
| 106 | 도토리 | acorn | 도토리 | familiar | 점검·평가 세트 | 도토리 |
| 107 | 호두 | walnut | 호두 | familiar | 점검·평가 세트 | 호두 |
| 108 | 솔방울 | pinecone | 솔방울 | familiar | 점검·평가 세트 | 솔방울(한 낱말 pinecone) |
| 109 | 감자 | potato | 감자 | familiar | 점검·평가 세트 | 감자 |
| 110 | 당근 | carrot | 당근 | familiar | 점검·평가 세트 | 당근 |
| 111 | 양파 | onion | 양파 | familiar | 점검·평가 세트 | 양파 |
| 112 | 수박 | watermelon | 수박 | familiar | 점검·평가 세트 | 수박 |
| 113 | 레몬 | lemon | 레몬 | familiar | 점검·평가 세트 | 레몬 |
| 114 | 귤 | tangerine | 귤 | familiar | 점검·평가 세트 | 귤 |
| 115 | 땅콩 | peanut | 땅콩 | familiar | 점검·평가 세트 | 땅콩 |
| 116 | 배추 | cabbage | 배추 | familiar | 점검·평가 세트 | 배추 |
| 117 | 만두 | dumpling | 만두 | familiar | 점검·평가 세트 | 만두 |

## 넣지 않은 낱말

| 넣지 않은 낱말 | 이유 |
| --- | --- |
| 가위·바늘 | 날붙이·찌르는 물건(무기 기준과 같은 쪽으로 보수적으로) |
| 장갑 | 손 모양 — 몸 부위 형상 |
| 트로피 | 사람 형상 장식이 흔함 |
| 저금통 | 영어 이름이 piggy bank(동물)로 흔히 그려짐 |
| 북·문·빗·사과·바퀴·실패·추·독·솔·못·초·단지 | 동음이의어(방위·질문/물다·빚/비·사죄·한 바퀴·실패하다·추석/성·독약·소나무·못하다·시간 단위·그저) — 문맥 제한 장치가 없음 |
| 리모컨·팽이·액자·집게·물통·바가지·밤송이·옥수수 | 뜻이 좁게 맞는 영어 명사 한 낱말이 없음(remote·top·frame·clip/tongs 등 다른 뜻과 겹침, '바가지 쓰다' 관용) |
| 고구마·물뿌리개·단풍잎 | 영어가 두 낱말(sweet potato·watering can·maple leaf) |
| 전구·램프·전등·손전등·양초·촛대·호롱·등잔 | 빛·불을 내는 물건 — 막는 범주(빛·불꽃)와 닿음. lightbulb·flashlight는 light를 품음 |
| 계단·책·공책·휴대폰·지갑·노트북 | 걱정·상황 문장에 흔히 나오는 장소·물건 낱말(평가 세트 WORRY 부류). 규칙 경로의 상황 문장 판정이 좁아 넣지 않음 |
| 스펀지 | sponge가 꾸밈말 금지 목록(질감·재질)에 걸림 |
| 붕대 | 다침을 떠올리게 하는 물건 |
| 소라 | 바다 생물(동물) |
| 전선·술병 | 동음이의어(전선 = 싸움터, 술병 = 숙취) |
| 빵 | 의성어('빵 터지다')와 같은 꼴 |
| 시계·깡통·단추 | 형태가 아닌 흔한 쓰임이 명사 꾸밈 자리로 잡힘('시계 방향으로', '깡통 전세', '첫 단추를 끼우다') — 점검 문장에서 오탐. 문맥 제한 장치가 없음 |
| 몽돌·캔·체인·원통·크레파스·테니스공·고무공·걸레·스프링·톱니·차돌·공깃돌·쿠션·쇳덩어리 | 60–120개 상한 안에서 같은 영어를 가진 말(조약돌·깡통·사슬·원기둥·공)과 겹치거나 덜 흔해 이번 판에서 뺌 |

시험의 사전 밖 낱말 예(디딤돌·고구마·몽돌·차돌·쿠션·바가지)는 0.3.0에 없다. 이 낱말을 사전에 넣으면 그 시험의 예도 함께 바꾼다.
