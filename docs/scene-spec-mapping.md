# SceneSpec v2 — 확정 텍스트 → 장면 기술 → Unity

Holodeck(CVPR 2024)처럼 "자연어 → 구조화된 장면 JSON → Unity" 순서로 갑니다. 다른 점은 가운데 단계에 LLM이 없다는 것입니다(AGENTS.md 1). 장면 속성은 사전과 규칙만 정하고, 같은 확정 텍스트는 언제나 같은 JSON이 됩니다.

```text
챗봇 면담 ─ [이대로 맞아요] ─▶ 확정 텍스트 ─▶ scene_builder (0층 Kiwi → 1층 사전 → 2층 직유 → 3층 V/A/D)
                                                 └▶ chatbot/logs/scenes/{sessionId}.json  (SceneSpec v2)
                                                        └▶ Unity SceneLoader: 프리팹 4종 + Shader Graph 파라미터 + Transform
                                                               └▶ initialScene.json · finalScene.json · events.csv
```

- 형식: `shared/schemas/scene-spec.v2.json` (JSON Schema 2020-12). 개선 매핑 v1의 출력은 상위 호환 `scene-spec.v2.1.json`(6절)
- 정답 예시: `chatbot/tests/fixtures/scene_spec/EX01.json`, `EX02.json`
- 만드는 코드: `chatbot/ifs_chatbot/scene_builder.py`(v0, 규칙 기반 기준선), `scene_builder_v1.py`(v1, 개선 매핑 — 6절), `scene_builder_v2.py`(v2, RQ V4 새 흐름 설정에서만 — 7절) (형식 도우미는 `scene_spec.py`)
- 읽는 코드: `unity/Assets/IFS/Runtime/` (`SceneSpecV2.cs`, `SceneLoader.cs`)
- 결정 기록: `docs/decision-log.md`

## 1. 형식

입력은 참여자가 [이대로 맞아요]를 누른 **확정 텍스트**뿐입니다. 면담 턴 JSON은 세션 로그에만 남고 장면에 쓰이지 않습니다.

| 경로 | 값 | 뜻 | Unity에서 |
| --- | --- | --- | --- |
| `form.type` | `blob`·`mist`·`shell`·`fragments`·null | 덩어리·안개·껍질·조각 | 프리팹 선택 |
| `form.posture` | `curled` 등 16종·null | 자세어(웅크리다, 처지다 …) | 변형 프리셋(납작·웅크림·곧음) |
| `material.color` | `{h, s, l}` 각 0–1 · null | HSL, h = 색상각/360 | `_BaseColor` |
| `material.brightness` | 0–1 · null | 0 어두움 – 1 눈부심 | `_Brightness` |
| `material.saturation` | 0–1 · null | 채도어(선명·탁하 …). 있으면 color.s 대신 씀 | 색 계산 |
| `material.roughness` | 0–1 · null | 0 젖은·매끈 – 1 거칠·녹슨 | `_Roughness` (URP Lit 대체 시 `_Smoothness = 1 − r`) |
| `material.opacity` | 0–1 · null | 0 투명 – 1 불투명 | `_Opacity` |
| `material.erosion` | 0–1 · null | 가장자리 침식·디졸브(삭다·갈라지다·깨지다) | `_Erosion` |
| `layout.size` | 0–1 · null | 로그 척도: 0.5 = ×1, 0 = ×0.25, 1 = ×4 | `localScale` |
| `layout.distance` | 0–1 · null | 0 = 0.3 m, 1 = 3.0 m (선형, 머리에서 수평) | 위치 |
| `layout.verticalOffset` | 0–1 · null | 참여자 키 대비 높이: 0 바닥, 1 정수리 | 위치 y |
| `motion.type` | `swaying` 등 22종·null | 움직임어 | 절차적 움직임 7종으로 묶어 재생 |
| `motion.speed` | 0–1 · null | 0 아주 느림 – 1 아주 빠름 | 움직임 주기 |
| `body.part` | `chest` 등 22종·null | 참여자가 말한 신체 부위 | 기록만(높이는 verticalOffset) |
| `body.layer` | `inner`·`surface`·`around` …·null | 몸 안·표면·주변 | 기록만 |

부가 필드:

| 필드 | 내용 |
| --- | --- |
| `_provenance` | 슬롯 경로 → 근거 목록 `{source, trigger, charSpan, rule}`. 값이 있는 슬롯에만 있고, null인 슬롯에는 없다(스키마가 강제) |
| `_unmatched` | 참여자가 말했지만 시스템이 값으로 읽지 못한 말. 1층 사전에 없는 내용어(낱말 항목)와, 값·다른 보존 필드가 다 덮지 못한 어절의 원문(`tag: EOJEOL`, 빌더 1.2.0부터. `docs/mapping-v1.md` 6절) |
| `_unmapped` | 사전에는 있지만 v2에 옮길 파라미터가 없는 말(형태어 '가장자리', 자기지칭 '나', 프로토타입이 정해지지 않은 직유 원천 '종이' …) |
| `_negated` | 부정된 말('무겁진 않아요'). 값에 넣지 않는다 |
| `_alternatives` | 같은 슬롯의 다른 근거. 우선순위에서 밀린 값(`lower_layer`, `later_mention`) |
| `_inferred` | 3층 V/A/D 제안. 값이 null인 슬롯에만 생기고 **값 자리에는 들어가지 않는다** |
| `meta` | `specVersion`, `participantId`, `sessionId`, `condition`, `sourceTextHash`, `pipeline`(빌더·분석기·사전 버전) |

- `source`: `explicit_lexicon`(1층), `simile_marker`(2층), `vad_lexicon`(3층). 2.2.0에는 `lexicon_implied`(형상 낱말의 사전 뜻에서 온 `form.baseVariant` 값, 7.5절)가 더해짐
- `rule`: `<근거 규칙>><슬롯 경로>:<대응 키>`. 예: `textureLexicon.눅눅>material.roughness:damp`, `simile.처럼>textureLexicon.젖>material.roughness:wet`
- `charSpan`·`sourceTextHash`의 기준은 정규화한 확정 텍스트(NFC, 따옴표 통일, 공백 정리, 줄바꿈 유지)입니다. 세션 로그의 `confirmedText`와 같은 문자열입니다.
- 장면 파일에는 시각이 없습니다. 같은 입력이면 파일이 바이트까지 같습니다.

## 2. 기존 형식과 달라진 점

이 저장소에 있던 형식은 추출 미리보기의 `sceneSpecDraft`(`IFSSceneSpec-draft/0.1`, `chatbot/ifs_chatbot/extract.py`)뿐입니다. 그 주석에 적힌 TS `IFSSceneSpec`의 묶음 이름(form / material / layout / motion)은 그대로 씁니다. TS 타입 원본과 `carrierFormMap.ts`는 이 저장소에 없어 필드 단위로 대조하지 못했습니다(decision-log 참고).

| 항목 | draft/0.1 (`sceneSpecDraft`) | v2 |
| --- | --- | --- |
| 구조 | 평평한 `slots["material.color"] = {value, _provenance}` | 묶음별 객체 `material.color = {h,s,l}` + 최상위 `_provenance["material.color"]` |
| 값 | 사전 라벨(`{"texture": "damp"}`, `{"size": "small", "scale": 0.6}`) | 0–1 수치(조정량 계산용). 범주형은 형태·자세·움직임·신체 부위만 |
| 빈 슬롯 | `unspecified` 목록 | 값 자리에 `null`(기본값과 섞지 않음) |
| 근거 | 슬롯마다 1개 | 슬롯마다 목록. 2층·3층도 같은 4개 키 |
| 질감 | `material.texture` 라벨 | `material.roughness`(젖음·거칠기)와 `material.erosion`(삭음·갈라짐)으로 나눔. 나머지 라벨(말랑·딱딱 …)은 `_unmapped` |
| 크기 | `layout.size {size, scale}` | `layout.size` = 0.5 + log2(scale)/4 |
| 거리 | `layout.distanceCue` 라벨(관찰값) | `layout.distance` 0–1 |
| 위치 | `bodyRelation`(Find 위치 질문의 답에서) | `body.part`·`body.layer`는 **확정 텍스트에서만**. 신체 부위는 `layout.verticalOffset`로도 옮김 |
| 자세 | `posture` unresolved | `form.posture` |
| 자기지칭 | `selfReference` unresolved | `_unmapped`(장면 파라미터 없음). blending 단서는 세션 로그에서 본다 |
| 무게·온도·소리·형태어 | `physical.weight`, `material.temperature`, `sound`, `form.shape` | 모두 `_unmapped`. 시각 파라미터로 옮길 근거가 아직 없다 |
| 직유 | `similes[]`, 프로토타입은 사전 형태어일 때만 | 2층 대응표로 `form.type`. 표에 없는 원천은 `_unmapped(simile_prototype_pending)` |
| 3층 | 없음 | `_inferred`(값 자리 아님) |
| 메타 | 없음 | `meta`(해시·버전·조건) |

세션 로그의 `extraction`(추출 미리보기)은 바꾸지 않았습니다. 장면 파일은 그와 별도로 저장되고, 세션 로그에는 `sceneSpec`에 파일 경로와 해시만 남습니다.

## 3. 층과 우선순위

| 층 | 하는 일 | 사전 |
| --- | --- | --- |
| 0층 | Kiwi 형태소 분석. 활용형 → 원형(무거워요 → 무겁) | — |
| 1층 | 확정 텍스트의 말 → 사전 항목 → 0–1 파라미터 | `shared/lexicon/layer1_lexicon.v0.json` + `scene_params.v0.json`의 `layer1` |
| 2층 | 직유 표지(~처럼, ~같은, ~듯한, ~마냥)의 원천 명사 → 형태 프로토타입. 직유 구 안의 수식어도 2층 근거 | `scene_params.v0.json`의 `layer2` |
| 3층 | 감정어 → V/A/D 평균 → 빈 슬롯 제안(밝기 ← V, 속도 ← A, 크기 ← D) | `shared/lexicon/vad_ko.v0.json` + `scene_params.v0.json`의 `layer3` |

- **1층 > 2층 > 3층.** 위층 값이 있으면 아래층 근거는 `_alternatives(lower_layer)`. 3층은 `_inferred`에만 들어갑니다.
- 같은 층에서는 **먼저 말한 것**이 값이고 나머지는 `_alternatives(later_mention)`입니다.
- **부정**("무겁진 않아요", "밝지 않아요")은 값에 넣지 않고 `_negated`에 남깁니다. 예외는 '움직임은 없어요'처럼 움직임 자체를 부정한 경우로, 참여자가 말한 상태라 `motion.type = still`입니다.
- `body.layer`는 같은 줄에 신체 부위어가 있을 때만 씁니다('벽 뒤에'의 '뒤'는 몸 기준 위치가 아님).
- '작아지다'처럼 변화형은 끝 상태 값으로 씁니다.

## 4. 예시

**① "가슴 안쪽에 젖은 종이처럼 눅눅하고 가장자리가 삭아가는 회색 덩어리가 있어요"**

| 말 | 층 | 결과 |
| --- | --- | --- |
| 가슴 | 1 | `body.part = chest`, `layout.verticalOffset = 0.72` |
| 안쪽 | 1 | `body.layer = inner` (같은 줄에 '가슴') |
| 젖은 | 2 (직유 구 '젖은 종이처럼' 안) | `material.roughness` 후보 0.15 → 1층 '눅눅'에 밀려 `_alternatives` |
| 종이(처럼) | 2 | 프로토타입 미정 → `_unmapped(simile_prototype_pending)` |
| 눅눅하고 | 1 | `material.roughness = 0.35` |
| 가장자리 | 1 | 형태어, 파라미터 없음 → `_unmapped` |
| 삭아가는 | 1 | `material.erosion = 0.6` |
| 회색 | 1 | `material.color = {h 0, s 0.05, l 0.45}` (노션 예시 값) |
| 덩어리 | 1 | `form.type = blob` |

말하지 않은 것(밝기·채도·투명도·크기·거리·움직임·자세)은 null입니다.

**② "웅크려진 작은 나"**

| 말 | 층 | 결과 |
| --- | --- | --- |
| 웅크려진 | 1 | `form.posture = curled` |
| 작은 | 1 | `layout.size = 0.316` (scale 0.6 → 0.5 + log2(0.6)/4) |
| 나 | 1 | 자기지칭, 파라미터 없음 → `_unmapped` |

형태(`form.type`)를 말하지 않았으므로 null입니다. Unity는 기본 형태를 쓰고 그 사실을 로그와 `initialScene.json`의 `defaultsUsed`에 남깁니다.

## 5. 대응 값의 출처

- 색 HSL: 1층 사전 값. '회색'만 노션 근거가 있고 나머지는 초안입니다.
- 질감·밝기·채도·투명도·거리·속도 수치, 신체 부위 높이, 2층 원천 명사 표, V/A/D 값: 모두 `status: draft`입니다(`scene_params.v0.json`, `vad_ko.v0.json`). 신체 부위 높이는 Drillis & Contini(1966)의 신체 비율을 근사했습니다.
- 수치를 바꾸면 사전의 `lexiconVersion`을 올립니다. 장면 파일의 `meta.pipeline.lexicons`에 버전이 남아서 어느 대응표로 만든 장면인지 가릴 수 있습니다.

## 6. 개선 매핑 v1 (SceneSpec v2.1)

v0(`scene_builder.py`)는 비교 기준선이라 그대로 두고, 개선 매핑을 `chatbot/ifs_chatbot/scene_builder_v1.py`에 따로 만들었습니다. 원칙은 v0와 같습니다. 장면 속성은 사전과 규칙만 정하고(LLM·임베딩 없음), 같은 확정 텍스트는 언제나 같은 파일 바이트가 됩니다. 실패 유형별 대응과 dev 수치는 `docs/mapping-v1.md`에 있습니다.

### 6.1 무엇을 쓰는가

| 파일 | 내용 |
| --- | --- |
| `shared/lexicon/layer1_lexicon.v1.json` | v0 1층 사전에 더하는 오버레이(174항목: 의태 질감어, 움직임 동사·의태 부사, 신체 부위, 투명도 '비치다', 형태 명사 …). v0 파일은 읽기만 한다 |
| `shared/lexicon/scene_params.v1.json` | v1 대응표. layer1·layer2·layer3은 v0 구조를 넓힌 것이고, `v1` 절에 표면형 규칙 표(색 이름·색 수식·정도 부사·단위·참조 사물 크기·높이어·배경 명사·부분 명사·모름·정정 표지·퍼지 임계값)가 있다 |
| `shared/schemas/scene-spec.v2.1.json` | 출력 형식. v2.0 문서도 그대로 유효(상위 호환). `meta.specVersion = "2.1.0"` |
| `chatbot/ifs_chatbot/jamo.py` | 자모 분해·편집거리(퍼지 매칭용) |
| `chatbot/ifs_chatbot/clarify.py` | 확인 질문 루프(6.6) |

### 6.2 층과 규칙

| 층 | 규칙 | 예 |
| --- | --- | --- |
| 0층 | Kiwi 형태소 + 어절(띄어쓰기·문장부호·이모지)·문장(종결어미·'요'·줄바꿈)·절(연결어미 '-고·-는데·-다가·-더니·-던데'·쉼표) | '떠있어요.크기는' → 두 문장 |
| 1층 사전 | v0 + 오버레이. 의태어 파생('까끌거리다' → 까끌까끌, '출렁출렁' → 출렁) | 오돌토돌 → roughness 0.75 |
| 1층 색 | 어절 표면형으로 색 이름을 찾는다(Kiwi가 '노란색'을 한 명사로 묶거나 '연보라색'을 '연/MM + 보라색'으로 나눠도 같게). 접두 '연-·진-·새-·검-', 앞 어절 수식어(연한·옅은 → 명도↑ 채도↓, 짙은·진한·어두운 → 명도↓, 탁한·칙칙한 → 채도↓, 선명한 → 채도↑), 띠는 색('누르스름' → 같은 문장의 색에 섞음), 'X에 가까운 Y'·'X빛이 도는 Y'(X를 30% 섞음). 무채색은 채도를 바꾸지 않는다. **품사 조건**: 색 어간이 시작하는 형태소가 형용사·어근(VA·XR)이거나, 명사(부사)이면 색 어간이 그 명사 안에 다 들어 있어야 하고, 동사(VV)는 원형이 색 어간 그대로일 때만('노래지다') 받는다 — '보라고'(보/VV + 라고), '제 노래요'(노래/NNG + 요)는 색이 아니다. 'N만 하다·N만큼/보다 + 크기 서술어'의 N은 비교 기준 사물이라 색으로 읽지 않는다. 표면형이 표에 없으면 첫 형태소 원형으로 찾는다('파랬다가' → 파랗, '노래졌어요' → 노래지) | '짙은 회색' → l 0.27 |
| 1층 정도 부사 | 앞 어절의 아주·매우·거의(×1.5) / 살짝·조금·좀·약간(×0.6)로 가운데(0.5, 침식 0, '떨어지다' 0)에서의 거리를 늘이고 줄인다 | '살짝 거칠어요' 0.71 |
| 1층 수치·단위 | 숫자·고유어 수 + 센티·미터·m·cm·뼘·걸음. 단위 뒤 '반'은 반 단위를 더한다('두 뼘 반' = 2.5뼘). 앞의 지름·크기·높이(는) → 크기, 뒤의 앞·떨어지다·처소 조사 → 거리, 폭·너비 → 크기 아님(보존), 정할 수 없으면 값 없이 `_measurements`에 `unknown` | '지름이 한 50센티' → size 0.68 |
| 1층 비교 크기 | 'N만 하다 / N만큼 / N보다 (조금·훨씬) 크다 / N 정도·크기 / N 두 개 / N을 다 덮을 만큼'과 참조 사물 크기표(m). 절반 'N (의) 반(만·쯤·정도)'·'N 크기의 반' → ×0.5('반투명'의 반은 아님). 'N 길이만큼 떨어져' → 거리. 참조 명사가 신체 부위여도 신체 부위 값이 아니다 | '주먹만 해요' → 0.33, '주먹 반만 해요' → 0.17 |
| 1층 높이어 | 눈높이·X 높이(가슴·무릎 …)·머리 위·발밑·바닥·천장 → `layout.verticalOffset` | '무릎 높이' 0.28 |
| 1층 투명·가림 | '비치다'(속이 비침: 1 − 0.5k), '뒤가 (거의) 안 보일 만큼' → 0.9, '반 투명' | '속이 살짝 비쳐요' 0.7 |
| 2층 직유 | v0 규칙 + 원천 명사표 확장. 합성어는 표에 있는 가장 긴 뒷부분('조개껍데기' → 껍데기) | '솜사탕같아요' → mist |
| 퍼지 | 사전에도 규칙에도 없는 내용어를 자모 편집거리 ≤ 1(표제어 자모 5개 이상, 가장 가까운 후보가 하나일 때만)로 사전 표제어에 맞춘다. Kiwi가 조각낸 어절은 어미를 떼고 어절 단위로. **결과는 슬롯 값에 쓰지 않는다**(원칙 2: 거리 1인 다른 낱말 '설명'→선명, '심정'→심장도 걸린다). `_alternatives`(reason `needs_confirmation`, `source = fuzzy_lexicon`, `needsConfirmation = true`)와 `_needsConfirmation`에 원문과 함께만 남고, `_inferred`도 만들지 않는다. 확인 질문 루프(6.6)가 켜져 있으면 이 말을 되묻는다 | '오돌도돌해요' → 오돌토돌(확인 필요, 값 없음) |
| 3층·제안 | V/A/D는 v0와 같다. 신체 부위 높이는 값이 아니라 `_inferred`(`source = body_part_height`) | '가슴' → 제안 0.72 |

### 6.3 범위 규칙 — 값에서 빼고 보존한다

| 규칙 | 판정 | 보존 위치 |
| --- | --- | --- |
| 회상 문장 | '장면'이 '-던' 관형절의 머리('걷던 장면')이거나 같은 문장에 떠오르다·생각나다·기억나다가 있음, 또는 관형형 '-던'이 있으면서 떠오르다 류가 있거나 '-던 + 상황 명사(오후·날·거 …)'로 문장이 끝남. '장면' 명사 하나만으로는 회상이 아니다('장면 속에 빨간 공이 …') | `_context`(recollection_sentence) |
| 배경 사물 | 관형어가 꾸미는 명사(명사구의 머리)가 배경 명사표(벽·책상·잎·화분·햇빛 …)에 있음. 형용사 + '-고' 관형 나열('크고 검은 돌')은 나열 끝 관형어와 같은 명사를 꾸민다 | `_context`(background_object) |
| 자리 표지 사물 | 관형어가 꾸미는 명사 바로 뒤가 위치 명사(앞·위·사이 …): '작은 상자 위에'의 '작은', '크고 검은 돌 옆의'의 '크고'·'검은' | `_context`(landmark_object) |
| 배경 주어 | 절의 주제·주어(은·는·도·이·가·만)가 배경 명사: '주변 화분들은 갈색이에요' | `_context`(background_subject) |
| 몸 위치어 | '위·앞·안 …' 바로 앞이 신체 부위가 아닌 명사이거나 뒤에 명사가 오면 몸 기준 위치가 아님 | `_context`(object_relative_position) |
| 부분 | 색·밝기·채도·거칠기에서 주제나 꾸미는 명사가 부분 명사: 겉·표면(전체와 같음) > 안쪽·가운데(전체 말이 없을 때만) > 테두리·가장자리·점·주변(값으로 쓰지 않음). 이·가 주어는 관형절('가장자리가 삭아가는 회색')에서 끊긴다. 침식·투명도는 부분 규칙을 쓰지 않는다 | `_parts` |
| 모름 | '모르겠다·헷갈리다·애매하다' 절. 그 절의 차원어('색은')나 'X인지 Y인지'·'움직이는지'가 가리키는 슬롯은 값을 비운다(말한 것: 모른다). 다른 언급도 `_alternatives(participant_uncertain)`. '-더니·-던데'도 절 경계라 '모르겠더니 지금은 분명히 빨개요'의 '빨개요'는 모름 절 밖이다 | `_uncertain` |
| 자기 정정 | '아(니) 아니다'·'아니'(뒤에 같은 슬롯이 다시 나옴), 'X이 아니고', 'X 말고', 'X보다는' | `_alternatives(self_corrected)` |
| 부정 | v0 규칙 + '빛이 (전혀) 안 나고'(체언 + 조사 + 안·못 + 용언), '안 빨개요', '빨갛지 않아요', '색은 없어요'(차원 부정), '크지도 작지도 않아요'('-지도'가 이어지고 뒤에 않·안·못이 오면 그 열의 모든 항) | `_negated` |
| 관용 | '윤기가 흐르다'·'초록빛이 돌다'의 흐르다·돌다는 움직임이 아님 | `_unmapped(idiom)` |
| 방향 | 왼쪽·오른쪽(+앞·뒤·위·아래). v2에 슬롯이 없다 | `_direction` |

### 6.4 병합 우선순위

슬롯마다 다음 순서로 고르고, 진 후보는 `_alternatives`(이유 포함)나 `_parts`에 남깁니다.

1. 차원 주제: '색은 X', '크기는 X'처럼 그 차원을 주제로 말한 값
2. 부분: 전체·겉 > 안쪽(6.3)
3. 때: '지금은' > 표지 없음 > '처음엔'·'~했다가'·'~있다가'(`superseded`). 절 표지와 별개로 '-던' 관형절 안의 말('빨갛던 게', '반짝이던 게')은 후보 단위로 지난 상태다
4. 층: 1층 > 2층(`lower_layer`)
5. 근거 종류: 수치 단위 > 비교·구 규칙 > 사전(`lower_priority`). 퍼지 일치는 병합에 들어가지 않는다(값 아님, `needs_confirmation`)
6. 슬롯별: 움직임은 움직임 동사 > 상태어('떠 있다'·'-어 있다'·가만히), 신체 부위는 구체어 > 온몸 > 몸, 몸 위치는 안·겉·주변 > 앞·뒤·위·아래(`lower_priority`)
7. 먼저 말한 것(`later_mention`)

### 6.5 원문 보존(무손실)

- 값이 되지 못한 말은 `_unmatched`·`_unmapped`·`_negated`·`_alternatives`·`_context`·`_parts`·`_uncertain`·`_measurements`·`_direction`·`_needsConfirmation`에 확정 텍스트의 `charSpan`과 원문(`text`·`trigger`·`surface`)으로 남습니다(**속성 단위 보존 필드**). 색 규칙이 읽지 못한 색 사전 낱말('빨깐')도 `_unmatched`에 남습니다.
- `_clauses`는 확정 텍스트 전체를 절로 나눈 색인입니다. 공백이 아닌 모든 글자가 어느 절엔가 들어가고, 절마다 `usedFor`(그 절이 근거가 된 슬롯)와 `status`(used·partly_used·unused·context)를 적습니다. 그래서 시스템이 읽지 못한 말도, 잘못 읽은 말도 결과 JSON에서 사라지지 않습니다.
- 다만 이 색인은 어떤 말이든 덮으므로 **보존의 증거로 세지 않습니다.** 채점기(채점기 0.3.0)는 미반영 원문 보존률(AC-3.5)을 속성 단위 보존 필드만으로 재고, `_clauses`까지 인정한 값은 `unreflectedVerbatimRateWithClauseIndex`, 절 색인으로만 남은 속성 수는 `lostClauseIndexOnly`로 따로 보고합니다(v0·v1 같은 규칙). 보존률은 "잃지 않았다"는 뜻이지 "옳게 읽었다"는 뜻이 아닙니다. 매핑 품질은 반영률·왜곡률·근거 없는 값으로 봅니다.

### 6.6 매핑 선택·대체·확인 질문 (`config/*.toml [mapping]`)

| 키 | 기본 | 뜻 |
| --- | --- | --- |
| `mode` | `"v1"` | 주 매핑. `scenes/{sessionId}.json`을 만든다. `"v0"`이면 규칙 기반 기준선. `"v2"`는 RQ V4 새 흐름 설정(`config/v4.toml`)에서만 쓴다(7절) |
| `save_both` | `true` | 같은 확정 텍스트로 `scenes/{sessionId}.v0.json`(순수 v0, specVersion 2.0.0)과 `.v1.json`도 만든다 — 비교 설계(`docs/research-design.md` 3.1). 철회하면 셋 다 지운다 |
| `clarify_loop` | `false` | 확인 질문 루프(`docs/chatbot-design.md` 5-1). 확증 비교에서는 끈다 |
| `clarify_max` | `2` | 확인 질문 최대 횟수 |
| `strict` | `false` (pilot `true`) | `true`이고 `mode = "v1"`인데 **시작 시점**에 v1 빌더를 만들지 못하면 v0로 넘어가지 않고 서버 시작(`Runtime` 생성)을 예외로 멈춘다. 요청한 매핑과 다른 매핑으로 참여자 세션을 돌리지 않기 위함(Codex CP2 #3). `mode = "v0"`이면 v1 생성 실패는 경고뿐. `false`면 아래 대체 경로 그대로 |

- **대체 경로.** v1이 예외를 내거나 불러오지 못하면 v0 결과를 씁니다. 파일의 `meta.mapping = {requested: "v1", used: "v0", fallbackReason}`(specVersion 2.1.0), 세션 로그 `sceneSpec.fallback = true`·`sceneSpec.mapping`, 연구자 알림 `scene_mapping_fallback`이 남습니다. 면담 종료는 막지 않습니다.
- **`strict`가 다루는 것과 다루지 않는 것.** `strict`는 시작 시점의 v1 **생성** 실패만 멈춥니다. 세션 도중 확정 시점에 v1 `build`가 예외를 내면 `strict = true`여도 위 대체 경로(v0 결과 + `meta.mapping` + 연구자 알림)로 갑니다. 이미 진행 중인 참여자 세션을 도중에 끊지 않기 위해서입니다. 그런 세션은 `sceneSpec.fallback = true`로 찾아 분석에서 따로 다룹니다.
- **코퍼스 재생.** `corpus_run`·`fidelity`의 매핑은 `--mapper`로만 고릅니다(설정의 `mode`와 무관). `--mapper v1`은 `ifs_chatbot.scene_builder_v1:factory`와 같습니다. 요청한 매핑이 예외로 v0에 대체된 항목은 `corpus_run` 결과의 `mappingFallback`과 채점 요약 `summary.mappingFallback`(건수·id)에 남고, 1건이라도 있으면 `report.md`·`paired.md` 머리와 콘솔에 경고가 나옵니다(그 항목은 v0 출력으로 채점된 것).

```powershell
cd chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\dev.json --mapper v1 --out <결과 폴더>
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\dev.json --mapper v0 --compare v1 --out <결과 폴더>
```

### 6.7 Unity

`SceneSpecV2.cs`·`SceneSpecJson.cs`는 2.0.0과 2.1.0을 같은 엄격 파서로 읽습니다. 2.1 필드는 선택 필드라 2.0.0 문서의 왕복 직렬화가 그대로이고, 2.0.0 문서에 2.1 필드가 있으면 `Validate`가 문제로 알립니다. 렌더 파라미터(`SceneParams`)는 v2.0과 같은 슬롯만 씁니다. 퍼지 일치 후보는 슬롯 값이 아니라 `_alternatives`(`needs_confirmation`)에만 있으므로 렌더에 들어가지 않습니다(2.1 스키마에서 `_alternatives.reason`에 `needs_confirmation`을 더했고, C#은 reason을 문자열로 읽어 파서는 그대로입니다). `_uncertain`·확인 필요를 기본값과 구분해 기록하는 일은 아직 하지 않았습니다(T3-H1, 보류). 예시는 `unity/Assets/StreamingAssets/IFS/examples/v1/`(배치 캡처 테스트가 세는 `examples/*.json`과 분리).

### 6.8 수치의 출처와 가정

- 참조 사물 크기표(m)·색 이름 HSL·색 수식 비율·정도 부사 배율·높이어 값은 모두 초안입니다(`status: draft`). 출처 문헌이 없고 연구팀 확인이 필요합니다.
- ⚠ **크기 가정.** 말한 물리 크기 m(가장 긴 변)를 `size = 0.5 + log2(m / 0.2 m) / 6`로 옮깁니다. size 0.5 = 20 cm, 0 = 2.5 cm, 1 = 1.6 m입니다. 렌더 배율(×0.25–×4, 16배)에 사람이 말하는 크기 범위(손톱–사람 키, 약 64배)를 압축해 넣은 것이라, Unity에서 보이는 크기는 말한 크기와 1:1이 아닙니다(Unity 기본 크기 0.35 m 기준 30 cm → 약 0.46 m). 물리 크기를 그대로 쓰려면 `_measurements.meters`를 씁니다.
- 거리는 v2 정의(0.3–3.0 m 선형) 그대로입니다.

## 7. RQ V4 실험 프로토타입(2026-11-23): 매퍼 v2, 속성 출처, 기본 형상 경로(D6), 스키마 영향

근거: `docs/prompts/prototype-v4-build.md` 단계 C·D, `docs/decisions.md` G14–G28과 연구 책임자 결정 G31–G34(구현 세부는 decisions.md 「G31–G34 구현 세부」). 구현 결과는 `docs/validation/mapper-v2/README.md`(D1·D2), `docs/validation/selection-flow/README.md`(D3·D5·D9), `docs/validation/runner-selection/README.md`(D8)에 있습니다.

### 7.1 매퍼 v2와 v0·v1의 관계 (G24)

- 매퍼 수정(D1 사전에 없는 명사 기록, D2 형상이 사라지거나 눈앞을 가리는 오류)은 **새 빌더 `scene_builder_v2.py`**에만 넣었습니다. `SceneSpecBuilderV1`을 상속하고 바뀌는 메서드만 다시 씁니다. 규칙과 수치는 `shared/lexicon/scene_params.v2.json`, 불용 명사는 `noun_stoplist.v2.json`입니다.
- **v0·v1 출력은 바뀌지 않습니다.** v0·v1의 코드와 사전 파일은 고치지 않았습니다. v0 sha256 고정 테스트(`chatbot/tests/test_scene_builder_v1.py::test_v0_output_byte_identical_to_baseline_hashes`, 고정값 `fixtures/v0_output_sha256.json`), 목업 v1 spec 36개 바이트 비교(`test_scene_builder_v2.py::test_v1_mock_specs_unchanged`), Unity v1 예시 비교(`test_unity_v1_examples_are_current_v1_output`)가 그대로 통과합니다. held-out v1 수치(반영률 0.698 등)도 그대로 유효합니다.
- **v2는 새 흐름 설정에서만 씁니다.** `chatbot/config/v4.toml`의 `[mapping] mode = "v2"`입니다. 기본 설정(`default.toml`·`pilot.toml`)과 `MappingConfig.mode` 기본값은 v1 그대로이고, v2 빌더는 v2를 요청할 때만 만듭니다(`test_default_mode_is_unchanged_and_v2_not_built`). v4 설정은 `save_both = true`라 같은 확정 텍스트로 `scenes/{sessionId}.v0.json`·`.v1.json`·`.v2.json` 비교 파일도 남깁니다.
- v2는 dev 코퍼스와 목업 36개만 보고 고쳤습니다. 목업 v1 → v2는 반영률 0.765 → 0.775, 왜곡률 0.060 → 0.045입니다(개발 자료 수치). held-out은 열지 않았고, v2를 주 매핑으로 보고하려면 규칙을 보지 않은 사람이 쓴 새 평가 문장이 필요합니다(X13).
- **거리 하한(G33, builder 2.1.0).** v2는 `layout.distance`가 하한 0.1보다 작으면 0.1로 올립니다(유지). 올릴 때 말한 값과 그려진 값을 둘 다 남깁니다: 슬롯 값 = 그려진 값(0.1), `_provenance.layout.distance[0].rule` 끝 꼬리표 `+floor(0.1;said=<말한 값>)` = 말한 값(하한 전, 0–1). 예: '얼굴 앞에 붙어 있어요' → `distanceLexicon.붙>layout.distance:attached+floor(0.1;said=0.0)`. 스키마 2.1에는 두 값을 구조로 담을 자리가 없어(`_measurements`는 수치 측정에만, `_alternatives`·`_context`·`_parts`의 `reason`은 닫힌 enum이라 뜻이 맞는 값이 없음) 자유 문자열인 `rule`에 적었습니다. `scene_builder_v2.floor_record(spec)`이 이 꼬리표를 읽고, 선택 기록 `selection.json`의 `distanceFloor`(말한 값·그려진 값·하한·rule·trigger·charSpan)와 `sourceDetails.layout.distance.saidValue`(말한 값)에 구조로 옮깁니다. builder 2.0.0 출력(`+floor(0.1)`, 말한 값 없음)은 `said = null`로 읽습니다. 배치 러너의 시작 자리는 spec 거리와 무관합니다(실험 설정 `startDistanceM`, G33 확인). v0·v1에는 하한이 없고 출력이 바뀌지 않습니다(`test_scene_builder_v2.py::test_v0_v1_outputs_unchanged_by_g33`, sha256 고정).
- 스키마를 바꾸지 않았기 때문에 v2 출력은 `specVersion` 2.1.0입니다. `meta.mapping = {requested: "v2", used: "v1", fallbackReason: null}`(2.1 스키마의 `used`가 v0·v1만 받음)과 `meta.pipeline.builder = "scene-spec-builder-v2/…"`로 v2임을 남기고, 대체 판정은 `scene_spec.is_mapping_fallback()`이 합니다.

### 7.2 사전에 없는 명사 (`_unmapped`, category `unlisted_noun`)

v1까지는 사전에 없는 명사(화분, 물병, 인형)가 기록 없이 사라졌습니다. v2는 확정 텍스트의 명사(Kiwi NNG·NNP) 가운데 다음을 모두 만족하는 것을 `_unmapped`에 남깁니다. 규칙은 결정적입니다(같은 텍스트 → 같은 목록).

1. 1층 사전(v0 + v1 오버레이, 표제어·이형 562개)에 없음
2. 값 근거(`_provenance`)와 다른 보존 기록(`_unmapped`·`_negated`·`_alternatives`·`_context`·`_parts`·`_measurements`·`_direction`·`_needsConfirmation`)이 이미 덮지 않음
3. 불용 명사(326개: 신체 부위·시간·장소 일반어·기능·차원·감정 명사 등)가 아님
4. 바로 뒤에 -하다가 붙지 않음('퇴근하고'의 퇴근은 빠짐)

```json
{"lemma": "화분", "category": "unlisted_noun", "reason": "no_scene_param",
 "value": {"noun": "화분", "role": "subject", "scope": "main"},
 "_provenance": {"source": "phrase_rule", "trigger": "화분", "charSpan": [9, 11], "rule": "unlistedNoun.화분"}}
```

- `role`은 뒤에 붙은 조사로 정합니다(subject·named·location·object·modifier·other). `scope`는 맥락 명사(회상 문장, 상황 명사, '생각나다' 류 문장 등)면 `context`, 아니면 `main`입니다. 둘 다 조사·문장 규칙이라 사람이 판단한 "형상 명사"와 같지 않습니다(예: '창가에 작은 화분이 있어요'에서는 '창가'도 `main`으로 남습니다).
- `reason`과 `_provenance.source`는 2.1 스키마 enum에 "사전에 없음"이 없어 가장 가까운 값(`no_scene_param`, `phrase_rule`)을 썼습니다. 2.2.0에서 값을 더할지는 정하지 않았습니다.
- 사전에 없는 명사는 **기록만** 합니다. 대신할 형상을 고르지 않고 값도 만들지 않습니다(원칙 2). 화면에는 기본 모형이 그려지고, 후보 단계에서 형태 자리는 비어 있는 것으로 봅니다.

### 7.3 속성 출처는 spec이 아니라 `selection.json`에 (G15, G32)

| 출처 | 뜻 | 어디에 |
| --- | --- | --- |
| 말함(`said`) | 확정 텍스트에서 규칙이 읽은 값 | spec의 `_provenance`(지금과 같음). `selection.json`의 `sources`에도 `said` |
| 고름(`chosen`) | 고른 후보가 정한 값(후보의 축 슬롯) | `selection.json`에만 |
| 고침(`edited`) | 조절에서 마지막 값이 처음 값과 다른 슬롯. 말한 값을 고치면 `edited`가 되고 `sourceDetails.saidValue`에 원래 값이 남음 | `selection.json`에만 |
| 기본값(`default`) | 아무도 정하지 않아 기본값으로 그려지는 슬롯 | `selection.json`에만(Unity 기록의 `defaultsUsed`와 같은 뜻) |
| 말했지만 모형 없음 → 고름(`said_unrendered_chosen`) | `form.type`만. 모형이 없는 모양어(Unity `ShapeMapping`에 모형이 없는 `_unmapped` category shape, 예: '길쭉'·'실')만 말해 형태 후보를 벌렸고, 참여자가 후보를 고름(0번 기준 후보를 골라도 같음) | `selection.json`에만. 말한 낱말은 `sourceDetails.form.type.saidWords` |
| 말했지만 모형 없음 → 기본 형태(`said_unrendered_default`) | `form.type`만. 같은 경우에 고르지 않음([맞는 것이 없다], 또는 선택 단계를 건너뜀) — 기본 형태(blob)로 그려짐 | `selection.json`에만. `saidWords` 같음 |

- **모양어와 형태 자리(G32, G29 대체).** 모형이 있는 모양어(round·square·flat·pointed → Sphere·Cube·FlatCylinder·Cone)를 말했으면 형태 자리는 말한 자리로 고정하고 후보에서 벌리지 않습니다. 출처는 `said`이고 `saidWords`에 모양어가 남습니다(G32 전에는 `form.type` 값이 null이라 `default`로 적혔습니다). 모형이 있는 모양어와 없는 모양어를 함께 말했으면 Unity가 모형을 그리므로 역시 `said`입니다. 모형이 없는 모양어만 말했으면 위 두 값 가운데 하나이고, 조절로 형태를 고치면 다른 슬롯처럼 `edited`입니다(말한 낱말은 그대로 남음). 모형 목록은 값 표 `candidate_values.v1.json`의 `shapeModels`이고 Unity 원문과 같은지 pytest가 대조합니다.
- **`_provenance`는 "말함"만 뜻하게 그대로 둡니다.** `_provenance`에 고름·기본값을 넣으면 참여자가 말한 것처럼 보이기 때문입니다. 원본 spec은 후보·조절 단계에서 바뀌지 않습니다(G14).
- `selection.json`(형식 `ifs-selection/0.2`, 스키마 `shared/schemas/selection.v0.2.json`. 0.1 스키마는 이전 기록용으로 그대로)은 세션 기록 폴더(`<log_dir>/selection/<sessionId>/`, git 밖)에 생깁니다. 헤드셋 러너는 원본 spec과 이 파일을 함께 읽고, `specSha256`(원본 spec 파일 바이트의 sha256)이 다르면 시작을 거부합니다.
- 헤드셋 러너는 `sources`를 해석하지 않고 기록에 옮기되, 슬롯 이름과 출처 값을 검사합니다(G27: 0.2는 여섯 값, 0.1은 네 값). `spec.sha256Basis`가 파일 기준이 아니거나 `runnerReady = false`면 거부합니다(G26). 0.2에서는 `selection.skipped`(선택 단계를 건너뜀, G34)와 `colorChanged`(색을 바꿨는지, G31)도 필수로 읽어 manifest에 옮깁니다.

### 7.4 덮어쓰기 키 형식

후보 하나와 최종 형상은 "원본 spec + 덮어쓰기"입니다. 덮어쓰기는 Unity `SceneOverrideJson`이 받는 **평평한 객체**입니다.

```json
{"form.type": "mist", "layout.size": 0.7, "material.color.h": 0.583, "material.color.s": 0.6, "material.color.l": 0.5}
```

- 수치 키는 0–1 숫자, 범주 키는 문자열입니다. 쓰는 키는 `form.type`, `motion.type`, `material.color.h`·`.s`·`.l`(색은 세 키로 나뉨, `SceneParams.NumericKeys`), `material.brightness`, `material.opacity`, `material.roughness`, `layout.size`입니다(선택 기록 스키마의 `flatOverrides`).
- 위치·거리 키(`layout.distance`·`layout.verticalOffset`)는 들어갈 수 없습니다(G10). 선택 기록 스키마와 헤드셋 러너가 둘 다 거부합니다.
- Unity `SceneOverrideJson`은 모양 모형을 강제하는 `shapeModel` 키도 받지만, 챗봇은 이 키를 쓰지 않습니다.

### 7.5 낱말 → 범주 → 기본 형상(`form.base`) 경로 — 구현(D6, 2026-11-23, 결정 G21·G30)

첫 묶음 5개(`container`·`line`·`sheet`·`flame`·`drop`)를 연구 책임자가 승인했고(G30) 매퍼 v2 builder 2.2.0과 스키마 2.2.0으로 구현했습니다. 형상별 그림과 판정은 `docs/validation/base-forms/README.md`, 정한 세부는 `docs/decisions.md` 「D6 구현 세부」입니다.

- **표현(G21):** `form.base`(5값 + null)와 `form.baseVariant`(낱말 뜻·같은 문장의 말이 정한 변형값, 정한 키만. 없으면 null). `form.type`(blob·mist·shell·fragments)은 표면·밀도 방식으로 그대로입니다. 두 슬롯의 `_provenance` 규칙은 다른 슬롯과 같습니다(값 ⇔ 근거, `_inferred` 없음).
- **사전:** `shared/lexicon/base_shapes.v1.json`(초안, `lexiconVersion` 0.6.0 — CP10 G37에서 0.5.0에 `excludedCompounds`·`rules.excludedMatch`를 더함). 형상을 이름 붙이는 명사 34개(담는 것 10·선 9·판 7·불꽃 5·물방울 3), 낱말마다 출처 표기(`lit:`[문] / `tr:`[번] / `added`[보]). 넣지 않은 낱말과 이유는 `notIncluded`, 그리지 않는 안전 제외 낱말은 `excluded`(0.6.0까지 사유 코드 human_figure·attacking_being·weapon·death_trauma·blood_noose, 0.7.0부터 범주 person·threat·weapon·death_self_harm_trauma와 `noAsset.animal`).
- **어떤 명사가 base가 되는가:** 명사 연속 전체 글자가 표제어와 같고(뒷부분만 맞추지 않음: '종이컵'·'비눗방울'), 본 장면 문장이며(회상·상황 문장 = 7.2의 `scope` context 판정), 부정되지 않았고, 문장 성분이 주어·이름이거나(‘종이 한 장이’처럼 수량 표현 뒤의 성분 포함) 직유 원천('불꽃 같은', 근거 `source` = `simile_marker`)일 때. 수량 단위('한 컵쯤'), 크기 비교 기준('신발 상자만 해요'·'컵 정도'), 다른 슬롯 값(form.type 제외)·`_measurements`·`_parts`·`_context`의 근거로 쓴 말은 base가 아닙니다.
- **여럿이면:** charSpan이 가장 앞선 명사의 형상을 쓰고, 같은 형상의 다른 명사는 근거에 더하며, 다른 형상은 `_alternatives`(reason `later_mention`)에 남깁니다. 변형값은 이긴 명사의 사전 값에서 시작해 같은 형상 근거가 있는 문장의 참여자 말('엉키·꼬이' → tangle, '가늘·굵' → 굵기, 모양어 '네모' → 단면 square)이 덮어씁니다.
- **다른 기록과의 관계:** base의 근거가 된 명사는 `_unmapped`의 같은 낱말 기록(object·shape·unlisted_noun, 직유 원형 대기 포함)에서 빠집니다. 그래서 builder 2.1.0까지 모형 없는 모양어(G32)였던 '실'·'선'·'끈'·'매듭'·'판'과 unlisted_noun이던 '화분'·'물병' 등은 이제 말한 형태입니다(후보에서 형태 자리를 벌리지 않음. `chatbot/tests/test_base_shapes.py`가 고정). 안전 제외 낱말은 `_unmapped`에 reason `excluded_shape`, `value.excluded`로 남기고 대신할 형상을 그리지 않습니다.
- **안전 제외 판정(CP10 G37, builder 2.3.0):** 형태소 단위입니다. 명사 연속을 바로 앞의 띄어 쓴 맨 명사 어절까지 넓히고('해골 그릇'·'아이 장난감 상자'·'사람 형상') 그 안의 Kiwi 명사 토큰 하나라도 제외 낱말이거나, Kiwi가 한 토큰으로 내는 제외 합성어 목록(`excludedCompounds`: '칼날'·'칼집'·'핏물' …)에 있으면 넓힌 연속 전체를 그리지 않습니다. 글자 부분 일치는 쓰지 않습니다('칼슘'·'피부'·'아이스크림'은 제외되지 않음). 부정된 것(`value.negated`)·직유 원천(`value.simile`)도 기록하고, 제외 낱말이 직유 원천이면('뱀 같은 끈') **같은 문장의 형상 낱말도 그리지 않고** 그 기록에 `value.excludedBy`를 남깁니다. 기록을 바꿀 때 원래 사유는 `value.priorReason`에 둡니다. 이 기록(reason `excluded_shape`)은 모양어로 세지 않습니다(챗봇 후보·Unity `ShapeMapping` 모두). 세부와 ⚠ 항목은 `docs/decisions.md` 「CP10 반영 세부」.
- **제외 판정 개정(G45–G51, builder 2.4.0, 사전 0.7.0 — 위 G37 판정을 대체):** 범주는 person·threat·weapon·death_self_harm_trauma(`value.excluded`), 동물은 reason `no_asset`(`value.noAsset` animal). 판정은 명사구의 **중심 명사**로 합니다 — 꾸미는 말·빗댄 낱말이면 중심 명사를 그리고('뱀 같은 끈' → line, '아기 그릇' → container), 중심 명사가 목록 낱말이면 그리지 않고 `value.formSaid` = true(후보가 형태 자리를 벌림, `saidWords[].unrenderedBy`). 넷째 범주는 어디에 나와도 형태 에셋·형태 후보를 막습니다(`value.formBlock`, 색 비교·색 표현 예외). 목록 낱말이 나온 자리마다 하나씩 기록하고 `value`에 position·role·scope·sentence(0부터)·usedForShape(false)·head·negated·simile을 둡니다. 목록 낱말 때문에 그리지 않은 형상 낱말·모양어에는 `value.blockedBy`{lemma, charSpan, category, rule(simile_target | modifier_of_listed_head | copula | unresolved_reference | strict_category)}. 1층 직유 원형이 목록 낱말의 뒷부분으로 낸 form.type('핏방울 같은' → blob)은 지우고 `value.blockedValue`에 남깁니다. reason `excluded_shape`·`no_asset`은 모양어로 세지 않습니다(챗봇 `candidates.UNRENDERED_REASONS`, Unity `ShapeMapping.UnrenderedReasons`). 문형 표: `docs/validation/mapper-v2/head-noun-patterns.md`.
- **낱말 뜻에서 온 변형값(CP10 G38, builder 2.3.0):** 형상 낱말의 사전 항목이 정한 변형값('그릇' → opening wide)은 그리되 `_provenance["form.baseVariant"]`의 `source`를 `lexicon_implied`로 적습니다. 같은 문장에서 참여자가 직접 한 말('엉켜'·'가는'·'네모난')로 정한 값만 `explicit_lexicon`입니다. 선택 기록은 `sourceDetails["form.baseVariant"].keyBasis`(키마다 lexicon_implied | said)로 가릅니다.
- **렌더(Unity):** `form.type`이 비었거나 blob일 때만 기본 형상을 그리고, mist·shell·fragments면 그 형태를 그리며 base는 `not_applied_form`으로 기록합니다. base가 모양 모형(Sphere 등)보다 앞서고 모양어는 `not_applied_base`. 자세한 것은 `docs/shape-mapping.md`, `unity/README.md` 「형상별 렌더 경로」.
- **후보·조절:** 기본 형상은 후보 값으로 내밀지 않습니다(말하지 않은 구체 사물을 보이지 않음, 에셋 계획 결정 8 제안대로). 말했으면 형태 자리는 말한 자리. 등록된 갈림 두 가지만 예외로 다른 읽기를 하나 더 보입니다: '막'(form.type이 비었을 때 blob = 얇은 판 | shell), 형태어 mist·shell·fragments와 기본 형상을 둘 다 말한 경우(`form_type_with_base`: 말한 형태 | blob = 기본 형상 — 두 읽기 모두 참여자 말이라 말한 form.type을 후보에서 바꾸는 유일한 경우). 조절의 "형태" 항목은 form.type 4값 + 기본 형상 5값이고 값 하나가 `form.type`·`form.base`를 함께 정합니다(후보 값 표 `candidate_values.v2.json`의 `valueOverrides`). 출처는 `selection.json`의 `sources["form.base"]`(said/chosen/edited/default)와 `sources["form.baseVariant"]`(CP10 G39: 변형값이 있으면 said, 없으면 default, 형태 조절로 base가 바뀌어 변형값이 쓰이지 않게 되면 edited·값 null. 형태 조작 한 번이 세 슬롯을 정했다는 기록은 `sourceDetails`의 `formItem`, 조절 사건의 `formSlots`).

### 7.6 스키마 영향

`shared/schemas/scene-spec.v2.2.json`(2.2.0, D6)을 새로 만들었습니다. 2.0·2.1 문서는 그 스키마로 계속 검사합니다(파이썬 `schema_errors()`가 specVersion에 맞는 파일을 고름). 2.2 스키마도 2.0·2.1 문서를 받습니다(상위 호환). 2.2.0 문서는 `form.base`·`form.baseVariant`를 반드시 가집니다(값이 null이어도 — 매퍼 v2는 기본 형상을 말하지 않았어도 2.2.0으로 적음. 같은 매퍼가 문서마다 다른 버전을 내지 않게 하고, '평가했지만 말하지 않음'(null)과 '이 판에는 슬롯 없음'(2.1)을 가르기 위해).

| 어디 | 영향 |
| --- | --- |
| v0·v1 출력 | **바뀌지 않음.** 기본 형상 낱말이 든 합성 5문장의 v0·v1 출력 sha256을 D6 전 커밋의 깨끗한 작업 폴더에서 재 고정(`test_base_shapes.py::test_v0_v1_outputs_unchanged_by_d6`). G33 때의 3문장 고정도 그대로 통과 |
| v2 출력 | builder 2.1.0 → 2.2.0, specVersion 2.2.0. 후보 출력 고정 해시 5개와 후보 id가 바뀜(생성기 `ifs-candidates/0.3.0`, 표 2.0.0) |
| Python 검사 | `scene_spec.SPEC_VERSION_V22`, `BASE_SLOT_PATHS`. `SLOT_PATHS`(2.0 슬롯)는 그대로 — 그 목록을 쓰는 v0·v1·평가 코드의 출력이 바뀌지 않게. `check_principles()`가 두 슬롯의 값 ⇔ 근거와 2.0·2.1 문서에 2.2 키가 있는지도 봄 |
| Unity 파서 | `SupportedSpecVersions`에 2.2.0, `FormSpec.Base`·`BaseVariant`(모르는 변형 키는 파싱 오류), 원문에 키가 있었는지(`BaseKeysPresent`)를 따로 봐 2.0·2.1 왕복 직렬화와 golden 지문이 그대로. `Validate()`가 버전·근거·모르는 기본 형상·다른 형상의 변형 키를 경고 |
| 해석값·기록 | `SceneParams`가 `form.base`를 범주 값으로 들지만 `CategoricalKeys`에는 넣지 않음 — 2.2 spec이거나 덮어쓰기로 기본 형상을 정했을 때만 `initialScene.json`·`ToRecord`에 나옴 |
| 덮어쓰기·선택 기록 | `SceneOverride`가 `form.base`(5값 + none)를 받음. `selection.v0.2.json`의 `slotName`·`flatOverrides`에 `form.base`를 하위 호환으로 더함(형식 버전 0.2 그대로), 러너 `PlacementSelection.SlotNames`도 같음 |
| 소유감 러너 | 형태 변형은 `form.base`를 건드리지 않음(G21, `BaseShapeTests.Ownership_variants_do_not_touch_form_base`) |
| 사전 버전 | `meta.pipeline.lexicons.baseShapes` = `base-shapes-v1@0.5.0` |
| 남은 것 | `meta.mapping.used`는 여전히 v0 | v1(v2는 v1으로 적음, 2.2 스키마에서도 그대로). 채점기(`eval/fidelity.py`)에는 `form.base` 정답 기준이 없어 v2의 기본 형상 반영은 채점하지 않음 |

## 8. 스펙 2.3: 윤곽·발광과 형태 변이 규칙층 (G61, 2026-11-26)

근거: `docs/decisions.md` G61(① 그릴 수 있는 형상 ② 받아들이는 말), 조사 `docs/viz-research-json-unity.md` 4.2절(E1 슈퍼쿼드릭 윤곽, E4 발광), `docs/viz-research-open-vocabulary.md` B-1절. 방향 전체와 하지 않은 것은 `docs/viz-pipeline-direction.md`에 있습니다. **Unity 구현자는 8.2·8.4·8.5절만 보고 구현할 수 있게 썼습니다.**

### 8.1 무엇이 바뀌었나, 켜는 법

| 파일 | 내용 |
| --- | --- |
| `shared/schemas/scene-spec.v2.3.json` | 2.3.0 형식. 2.2 스키마에 슬롯 3개(`form.roundness`, `form.aspect`, `material.emission`)와 선택 필드 `provenance.variant`를 더함. 2.0–2.2 문서도 그대로 받음 |
| `shared/lexicon/layer1_lexicon.v2.json` | 1층 사전 v2 오버레이(v0 + v1 위). 새 범주 `contour`(윤곽어 16개)·`emission`(발광어 8개)만 더함 |
| `shared/lexicon/scene_params.v3.json` | 새 범주 → 슬롯(`layer1`), 서수 단계(`ordinal`), 정도 부사(`degree`), 부정(`negation`), 명사 + 용언 구(`phrases`), **Unity 수치 대응표(`render`)** |
| `shared/lexicon/variant_rules.v0.json` | 형태 변이 규칙층의 닫힌 표(어미·파생 접사·겹친 꼴·의태어 모음·자음 교체, 불용 표) |
| `chatbot/ifs_chatbot/variants.py` | 변이 규칙 해석기 |
| `chatbot/ifs_chatbot/scene_builder_v2.py` | 매퍼 v2에 두 기능을 선택으로 더함(builder 2.5.0) |

설정은 `config/*.toml`의 `[mapping]`이고 `mode = "v2"`일 때만 씁니다.

| 키 | 기본 | 뜻 |
| --- | --- | --- |
| `ext_lexicon` | `""`(끔) | `"layer1_lexicon.v2.json"`이면 스펙 2.3.0을 냅니다 |
| `ext_params` | `"scene_params.v3.json"` | `ext_lexicon`을 켰을 때 읽는 대응표 |
| `variant_rules` | `""`(끔) | `"variant_rules.v0.json"`이면 형태 변이 규칙층을 켭니다. 스펙 버전은 바꾸지 않습니다(2.2.0 그대로, 근거는 `rule` 꼬리표) |

- **둘 다 꺼져 있으면(기본) 매퍼 v2 출력은 builder 2.4.0·스펙 2.2.0과 바이트 단위로 같습니다.** dev.json 30개, `mock_corpus.json` 36개, G61 합성 30개에서 G61 전 HEAD(`d21f984`)의 빌더 출력과 바이트 비교해 모두 같았고, 6문장을 sha256으로 고정했습니다(`chatbot/tests/test_g61_viz_pipeline.py::test_default_v2_output_unchanged_by_g61`). 하나라도 켜면 `meta.pipeline.builder`가 `scene-spec-builder-v2/2.5.0`이 되고, 켠 기능만 `meta.pipeline.lexicons`에 키(`layer1Chain`·`sceneParamsV3`·`variantRules`)가 생깁니다(G52와 같은 관례: 기본값이 아닐 때만 새 표기).
- `config/v4.toml`에도 두 키를 꺼진 채로 적었습니다. **Unity는 2.3.0을 읽고 그립니다**(2026-11-26): 파서(`SceneSpecJson`)·`SceneLoader`를 같이 쓰는 헤드셋 러너·WebGL 미리보기·배치 캡처가 8.4절대로 윤곽·발광을 그리고, 세 값이 모두 null인 2.3 문서는 2.2와 같은 메시·머티리얼·화소입니다(`unity/README.md`, 화면 `docs/validation/scene-spec-2.3/`). 명세와 다른 점은 셰이더 발광 프로퍼티 이름 하나(`_EmissionColor` 대신 `_IfsEmission` — Built-in Standard 예약 이름이고 2.0–2.2 golden 지문이 그 이름의 유무를 읽기 때문)입니다. `ext_lexicon`을 켤지는 아직 정하지 않았습니다(헤드셋 확인 전). `variant_rules`는 스펙을 바꾸지 않아 Unity와 무관하게 켤 수 있습니다(권고는 `docs/viz-pipeline-direction.md`).

### 8.2 최종 스키마 2.3.0 (Unity 구현자용)

```json
"form": {"type": "blob", "posture": null, "base": null, "baseVariant": null,
         "roundness": "angular", "aspect": null},
"material": {"color": {"h": 0.0, "s": 0.05, "l": 0.45}, "brightness": null, "saturation": null,
             "roughness": null, "opacity": null, "erosion": null, "emission": "glowing"}
```

| 슬롯 | 값(서수, 왼쪽부터 순서) | null | 사전 낱말(1층 사전 v2) |
| --- | --- | --- | --- |
| `form.roundness` | `angular` · `slightly_angular` · `neutral` · `slightly_rounded` · `rounded` | 둥긂을 말하지 않음 | 각지·모나·네모나 → angular, 둥글·동그랗·둥그렇·동글동글·둥글둥글 → rounded, 둥그스름·동그스름 → slightly_rounded. 구 '각이 지다'·'모가 나다' → angular |
| `form.aspect` | `elongated` · `slightly_elongated` · `neutral` · `slightly_flattened` · `flattened` | 길쭉함·납작함을 말하지 않음 | 길쭉·기다랗 → elongated, 갸름 → slightly_elongated, 납작·평평·넓적 → flattened |
| `material.emission` | `none` · `faint` · `glowing` | 발광을 말하지 않음 | 빛나·번쩍이·번쩍거리·환하·눈부시 → glowing, 반짝이·반짝거리·반짝반짝 → faint, 구 '빛이 나다' → glowing. 부정('빛나지 않아요'·'빛이 안 나요') → none |

- 2.3.0 문서는 세 키를 **반드시 가집니다**(값이 null이어도). 2.2 키(`form.base`·`form.baseVariant`)도 그대로 반드시 있습니다. 2.0·2.1·2.2 문서에 세 키가 있으면 스키마와 `check_principles()`가 거부합니다.
- 값 규칙은 다른 슬롯과 같습니다. 값이 있으면 `_provenance["form.roundness"]` 같은 근거가 있고, null이면 근거가 없습니다. `_inferred`에는 나오지 않습니다(추론 제안을 만들지 않음).
- `neutral`(둥긂·길쭉함)은 사전이 내지 않습니다. 나중에 참여자 조절(④)과 렌더러 기본값을 위한 단계입니다.
- `_alternatives`·`_context`·`_parts`·`_uncertain`·`_clauses`의 `path`에 세 경로가 올 수 있습니다. 윤곽어 부정은 `_negated`(category `contour`)에 남습니다.
- `provenance.variant`(선택): 형태 변이 규칙층 근거의 구조 기록. `{"rules": [...], "surface": "빤짝빤짝", "root": "반짝반짝", "grade": ["stronger"]}`. 같은 내용이 `rule` 앞머리 `variant(…)`에도 있습니다(2.2 문서에는 구조 필드가 없어 꼬리표만). Unity는 이 필드를 읽지 않아도 되지만 엄격 파서라면 키를 알아야 합니다.
- 렌더러가 새로 받을 수 있는 덮어쓰기 키(아직 챗봇이 쓰지 않음, ④ 설계용): `form.roundness`·`form.aspect`·`material.emission`(범주 문자열, `"none"`은 발광 끔).

### 8.3 매퍼 규칙 (사전 → 값)

1. **직접 묘사어만.** 참여자가 모양·빛을 직접 말했을 때만 값이 생깁니다. 감정어·온도어로 윤곽·발광을 정하지 않습니다(`'불안하고 답답해요'` → 세 슬롯 모두 null). '밝은 색'의 '밝다'는 명도(`material.brightness`)라 발광이 아닙니다. 넣지 않은 낱말과 이유는 `layer1_lexicon.v2.json`의 `notIncluded`.
2. **정도 부사.** 앞 어절이 약한 정도 부사(살짝·조금·약간 …)면 한 단계 중립 쪽으로 옮깁니다(rounded → slightly_rounded, glowing → faint). 중립·none까지는 가지 않습니다. 센 정도 부사는 바꾸지 않습니다. 옮기면 `rule` 끝에 `+degree(살짝)`. 구('빛이 좀 나요')는 용언 앞 부사를 봅니다.
3. **부정.** 발광어 부정 → `none`(말한 값: 빛이 없다, `rule` 끝 `(negated)`). 윤곽어 부정('둥글지 않아요') → 값 없음, `_negated`에만(반대 값 '각짐'을 만들지 않음).
4. **범위 규칙**은 v1과 같습니다. 회상 문장 → `_context`, 배경 사물·자리 표지 사물을 꾸미는 윤곽어('둥근 탁자 위에') → `_context`(background_object·landmark_object), 부분 명사(안쪽·가장자리 …)를 주제로 하거나 꾸미는 말('가장자리가 빛나요') → `_parts`(전체 값으로 올리지 않음, 겉·표면은 전체), 모름 절 → `_alternatives`(participant_uncertain), 자기 정정·'처음엔 …했다가' → `_alternatives`(self_corrected·superseded). 병합 순위도 v1과 같습니다(차원 주제 > 때 > 층 > 근거 종류 > 먼저 말한 것). 직유 원천의 꾸밈말('둥근 돌 같은')은 2층(`source = simile_marker`)입니다.
5. **구 규칙**(`scene_params.v3.json` `phrases`): 명사 + (이·가·은·는·도) + (부사 둘까지) + 용언이 같은 절에 있으면 '각+지'·'모+나'·'빛+나'를 사전 항목 각지·모나·빛나로 읽습니다. Kiwi가 문맥에 따라 '각진'을 `각/NNG + 지/VV`로 나누는 경우도 이것으로 받습니다. 근거 `source = phrase_rule`, 구간은 명사부터 용언 어절 끝까지. 그 명사가 D1에서 사전에 없는 명사(`unlisted_noun`)로 기록됐으면 지웁니다(D6 기본 형상과 같은 처리).
6. **2.2 슬롯과의 관계.** 윤곽·발광은 다른 슬롯과 기록을 다 정한 뒤 따로 읽으므로 2.2 슬롯 값은 바뀌지 않습니다. 같은 낱말이 다른 범주에도 있으면 둘 다 걸립니다(v1 오버레이 규칙과 같음): '둥근'은 v0 모양어(`_unmapped` category shape round — Unity 구 모형이 읽음)로 **그대로 남고** `form.roundness = rounded`의 근거도 됩니다. '빛나요'는 `material.brightness = 0.9`와 `material.emission = glowing`을 함께 냅니다(밝기 슬롯은 2.2와 같음).
7. `_unmatched`는 새 근거가 덮은 토큰을 빼고 어절 항목을 다시 계산합니다. `_clauses`는 근거가 든 절의 `usedFor`에 새 경로를 더합니다(읽기용 색인).

### 8.4 Unity 해석 규칙 (구현자용)

1. **파서.** `SupportedSpecVersions`에 2.3.0. `FormSpec.Roundness`·`FormSpec.Aspect`·`MaterialSpec.Emission`(문자열, null 허용). 표에 없는 값은 파싱 오류(기본 형상 변형 키와 같게). 2.0–2.2 문서의 왕복 직렬화와 golden 지문이 바뀌지 않게, 2.2 때처럼 원문에 키가 있었는지 따로 봅니다. `provenance.variant`는 선택 키로 받습니다.
2. **어느 형상을 그리나(윤곽 적용 순서).** 위에서부터 처음 맞는 것:
   1. `form.type`이 mist·shell·fragments → 그 형태. 윤곽은 `not_applied_form`.
   2. `form.base`가 승인된 기본 형상이고 `form.type`이 null·blob → 기본 형상. 윤곽은 `not_applied_base`.
   3. 모양 모형이 적용됨(`docs/shape-mapping.md` 규칙: `_unmapped` category shape의 round·square·flat·pointed) → 그 모형 그대로. 윤곽(둥긂·길쭉함 둘 다)은 `not_applied_model`. **충돌 규칙:** 둥글·동그랗·네모나·납작·평평은 모양 모형 낱말이면서 윤곽어라, 모형이 있으면 2.2와 같은 그림을 지키고 같은 말을 두 번 적용하지 않습니다(예: 납작 원기둥을 또 납작하게 만들지 않음).
   4. 그 밖(기본 덩어리 경로):
      - `form.roundness`가 있으면 **슈퍼쿼드릭 메시**(8.5 표의 e1·e2)로 기본 덩어리 메시를 대신합니다. 모양 모형처럼 정점 변위 `_Displacement`·굴곡 `_Lumpiness`를 0으로 둡니다(각진 윤곽이 노이즈로 흐려지지 않게). 색·밝기·거칠기·불투명도·침식은 같은 IFS 셰이더로 그대로.
      - `form.roundness`가 null이고 `form.aspect`만 있으면 **기본 덩어리 메시를 그대로** 쓰고 축 배율만 곱합니다(말하지 않은 둥긂을 바꾸지 않음).
      - `form.aspect`가 있으면 8.5 표의 축 비율 (x, y, z)를 형상의 국소 배율에 곱합니다. 긴 축 = 1이라 `layout.size`(가장 긴 변)의 뜻이 그대로입니다. 그 위에 지금처럼 `layout.size` 배율과 `form.posture` 크기 변형을 곱합니다.
      - 두 슬롯이 모두 null이면 **2.2와 완전히 같은 경로**(같은 메시·같은 셰이더 값·같은 기록)입니다.
3. **슈퍼쿼드릭 메시(`superquadric/1`).** 지름 1(반축 0.5)인 단위 형상을 만들고 모양 모형과 같은 기본 크기(`SceneLoader ▸ Placement ▸ Primitive Base Size`, 0.35 m)로 줄입니다. Unity 국소 축(y가 위)으로:
   - η ∈ [−π/2, π/2](위도), ω ∈ [−π, π)(경도), f(c, e) = sign(c)·|c|^e
   - x = 0.5·f(cos η, e1)·f(cos ω, e2), y = 0.5·f(sin η, e1), z = 0.5·f(cos η, e1)·f(sin ω, e2)
   - 경도 48칸 × 위도 24칸(원뿔 모형과 같은 48조각), 극점은 한 점으로 모읍니다. e가 작으면(angular 0.1) 정점이 모서리 근처에 몰려 `RecalculateNormals`의 음영이 얼룩질 수 있습니다. 같은 매개변수 격자에서 이웃 정점 차의 외적으로 법선을 구하거나(이음매·극점은 평균), 해석 법선(Barr 1981의 법선 식: 지수 e를 2 − e로 바꾼 같은 꼴)을 쓰고, 모서리 음영을 화면으로 확인합니다. 난수가 없어 같은 값이면 같은 메시입니다.
   - 확인 기준: e1 = e2 = 1이면 지름 1인 구(정점 오차 1e-5 이내), 0.1이면 한 변 1인 정육면체에 가까운 둥근 상자.
4. **발광.** 형상 경로와 상관없이(1–4 모두) 적용합니다.
   - 발광 색 = 그 물체를 그리는 **바탕색 그대로**(말한 `material.color`에 밝기·채도 슬롯과 덮어쓰기까지 반영한 최종 바탕색. 색을 말하지 않았으면 지금 쓰는 기본색 — 그 기본색은 지금처럼 `defaultsUsed`에 `material.color`로 남음). **새 색을 만들지 않습니다.**
   - 셰이더 발광 항 = 바탕색(선형) × 세기(8.5 표). IFS 셰이더에 `_EmissionColor`(기본 검정 = 0, 그래서 null·none이면 2.2와 같은 화소) 항 하나를 더합니다. 블룸 후처리는 넣지 않습니다(Quest 비용).
   - 반투명 형태(mist 등)도 같은 규칙입니다.
5. **기록(`initialScene.json`, 배치 캡처 `report.json`).** 2.3 문서일 때만 새 키:
   - `contour`: `{"status": "applied" | "not_applied_form" | "not_applied_base" | "not_applied_model" | "none", "roundness", "aspect", "mesh": "superquadric/1" | "default", "e1", "e2", "axisRatios": [x, y, z]}` — 적용하지 않았으면 수치는 null(기본값과 미지정을 섞지 않음).
   - `emission`: `{"level", "intensity", "colorSource": "said" | "default"}`.
   - `defaultsUsed`에 더할 것: 길쭉함·납작함을 그렸으면 `form.aspect.axis`(긴 축 방향 = 세로 y는 말하지 않은 기본값), 슈퍼쿼드릭을 그렸는데 `form.aspect`가 null이면 `form.aspect`, 축 배율만 곱했는데 `form.roundness`가 null이면 `form.roundness`.
6. **덮어쓰기.** `SceneOverride`가 `form.roundness`·`form.aspect`·`material.emission` 범주 키를 받을 수 있게 둡니다(챗봇은 아직 보내지 않음. 선택 기록 `selection.v0.2.json`은 바꾸지 않았음).
7. **테스트.** 2.0–2.2 golden 지문 불변, 세 슬롯이 모두 null인 2.3 문서는 2.2 문서와 렌더·기록이 같음(specVersion 빼고), e = 1 구 대조, 적용 순서 1–4, 발광 null·none일 때 화소 불변.

### 8.5 수치 대응표 (`scene_params.v3.json` `render`, 초안 — 화면 확인 전)

| `form.roundness` | e1 | e2 | 모양 |
| --- | --- | --- | --- |
| `angular` | 0.1 | 0.1 | 모서리가 살짝 둥근 정육면체 |
| `slightly_angular` | 0.3 | 0.3 | 둥근 상자 |
| `neutral` | 0.5 | 0.5 | 쿠션 꼴 |
| `slightly_rounded` | 0.75 | 0.75 | 덜 둥근 구 |
| `rounded` | 1.0 | 1.0 | 구 |

| `form.aspect` | (x, y, z) 배율 |
| --- | --- |
| `elongated` | (0.5, 1.0, 0.5) |
| `slightly_elongated` | (0.75, 1.0, 0.75) |
| `neutral` | (1.0, 1.0, 1.0) |
| `slightly_flattened` | (1.0, 0.7, 1.0) |
| `flattened` | (1.0, 0.4, 1.0) — FlatCylinder 모형의 두께 비 0.4와 같음 |

| `material.emission` | 세기 |
| --- | --- |
| `none` | 0.0 |
| `faint` | 0.35 |
| `glowing` | 1.0 |

- 두 지수를 같게 둡니다(참여자가 말한 것은 '둥긂 정도' 하나). e > 1(팔면체·별꼴)은 쓰지 않습니다.
- 길쭉함의 긴 축은 세로(y)입니다. 참여자가 방향을 말하지 않았으므로 기본값이고 `defaultsUsed`에 남깁니다.
- 수치를 바꾸면 `scene_params.v3.json`의 `lexiconVersion`을 올립니다. 정서 → 모양 문헌(곡선 = 긍정 등)은 이 표의 근거가 아닙니다(원칙 2). 표는 직접 말한 모양어를 어떻게 그릴지만 정합니다.

### 8.6 형태 변이 규칙층 (`variant_rules.v0.json`)

**순서**: ① 1층 사전 직접 일치 → ② 기존 의태어 파생(v1 `mimeticDerivation`: -거리다·-대다·-이다·겹친 꼴) → ③ 변이 규칙층 → ④ 자모 퍼지(`_alternatives`, 값 아님). ③은 ①②가 아무것도 내지 않은 토큰에만, 뿌리가 사전에 있을 때만 그 항목의 값(정도 부사 포함 v1과 같은 대응)을 냅니다. ③이 다룬 토큰은 ④로 가지 않습니다. 퍼지는 '다른 낱말일 수도 있는' 거리 1 후보이고 변이는 닫힌 표의 규칙 일치라 변이가 앞섭니다.

| 규칙(이름) | 하는 일 | 예(합성) |
| --- | --- | --- |
| `ending` | Kiwi가 어미까지 한 토큰(NNG·UN)으로 묶거나 어절을 조각낸 경우 어미를 뗌(안에 든 파생 접사도 기록) | 빤짝여요 → 빤짝 (+suffix:이) |
| `suffix:<접사>` | -스럽·-스름·-스레·-거리·-대·-이·-하를 뗌. -스름·-스레는 grade `attenuated`만 남김 | 탄탄하 → 탄탄 |
| `reduplication` | ABAB → AB | 빤짝빤짝 → 빤짝 |
| `ideophone_vowel` | 양성 ↔ 음성 모음 쌍(ㅏ↔ㅓ, ㅗ↔ㅜ, ㅏ↔ㅜ, ㅐ↔ㅔ, ㅐ↔ㅣ, ㅑ↔ㅕ, ㅛ↔ㅠ, ㅘ↔ㅝ, ㅚ↔ㅟ), 한 낱말 안에서 같은 방향 | 꺼칠 → 까칠(larger), 번질번질 → 반질반질(larger), 꼼틀 → 꿈틀거리(smaller) |
| `ideophone_consonant` | 초성 예사 ↔ 거센 ↔ 된소리(ㄱㅋㄲ, ㄷㅌㄸ, ㅂㅍㅃ, ㅈㅊㅉ, ㅅㅆ), 같은 방향 | 빤짝 → 반짝(stronger), 탄탄 → 단단(stronger) |

- **과잉 일치 막기**: (a) 교체는 의태어 꼴에만 — 말한 쪽이 XR·MAG이거나 겹친 꼴·접사·어미를 뗀 꼴일 때만(용언 원형 '말려' → '멀리' 오대응을 dev에서 보고 막음), 사전 쪽은 XR·MAG이나 -거리·-이·-대 동사이고 감각 의태어 범주(질감·움직임·밝기·소리·모양·온도·무게·윤곽·발광)일 때만. (b) 모음과 자음을 한꺼번에 바꾸지 않음('통통' → '둥둥' 오대응을 dev에서 보고 끔). (c) 같은 단계에서 서로 다른 값이 걸리면 대응하지 않음. (d) 불용 표: 부들부들·철렁·촐랑·설렁·탁탁·털털·동동·감감·벌벌·펄펄·콩콩·쿵쿵·뻥뻥·번번·반반. (e) 보통 명사에는 걸지 않음. 규칙마다 양·음 테스트가 있습니다(`test_g61_viz_pipeline.py`).
- **강도는 기록만**: 큰말·작은말(`larger`·`smaller`), 센·여린 소리(`stronger`·`weaker`), -스름(`attenuated`)은 값을 바꾸지 않습니다. '꺼칠꺼칠'과 '까칠까칠'은 같은 `material.roughness`입니다.
- **부정**이면 값을 만들지 않고 `_negated`에(규칙 꼬리표 그대로). 뿌리가 사전에 있으나 장면 값이 없으면('탄탄' → 단단 firm) 직접 일치와 같게 `_unmapped`에.
- **근거 형식**: `rule = "variant(suffix:하>ideophone_vowel;surface=꺼칠;root=까칠;grade=larger)>textureLexicon.까칠>material.roughness:rough"`. 스펙 2.3 문서에서는 `provenance.variant`에도 구조로 남습니다.
- **dev 수치**(held-out 미사용, 확정 텍스트 근사 = 코퍼스 replies를 줄바꿈으로 이음): dev.json + mock_corpus 66개에서 변이 규칙이 값을 낸 것 0건(두 오대응을 막은 뒤), 토큰 단위 `_unmatched` 460 → 460. G61 합성 30문장(규칙을 보고 지은 문장이라 평가 아님)에서 값 5개·기록 3개, `_unmatched` 37 → 31, 퍼지 대안 3 → 1. 스펙 2.3을 함께 켜면 66개에서 윤곽 값 15(둥긂 12·길쭉함 3), 발광 값 10, `_unmatched` 460 → 453.

### 8.7 입자 형태(`form.type = particles`)는 자리를 예약하지 않았다

- 지금 1층 사전 v1은 '알갱이'·'가루'·'입자'·'부스러기'를 `fragments`로 대응합니다. 입자 형태를 만들면 이 낱말들의 대응을 다시 정해야 하고(어느 것이 파편이고 어느 것이 입자인가), 그것은 사전 결정이지 스키마 자리 문제가 아닙니다.
- 해석기가 없는 enum 값을 스키마에 먼저 넣으면 엄격 파서·후보 값 표(`candidate_values.v2.json`의 형태 항목)·러너 덮어쓰기 검사가 '받지만 그리지 못하는 값'을 갖게 됩니다. 기본값과 미지정을 섞지 않는다는 원칙과도 맞지 않습니다.
- 권고: 입자 렌더(Shuriken, 고정 시드)와 사전 재대응을 함께 정할 때 2.4에서 `form.type` 값으로 더합니다. 밀도(빽빽·촘촘)는 그때의 매개변수 후보입니다(`docs/validation/lexicon-proposals/priority-imagery.proposals.json`).

### 8.8 남은 문제

- **기존 결함(이번에 고치지 않음, 기본 출력을 바꾸게 되므로):** builder 2.2.0 이후 D6 기본 형상 경로가 `_unmatched`의 어절 항목을 다시 계산할 때 옛 어절 항목을 지우지 않은 채 계산해, 기본 형상(또는 제외 낱말)이 나온 spec에서는 **어절 단위 `_unmatched`가 모두 사라집니다**(dev + mock 66개 중 20개. 어절 항목이 66개 합계 636개인데, 옛 항목을 빼고 다시 계산하면 956개). 무손실 보존(6.5절) 결함입니다. 스펙 2.3 경로는 다시 계산할 때 옛 항목을 먼저 빼므로 이 결함이 없습니다 — 그래서 2.2와 2.3 출력의 어절 항목 수를 그대로 견주면 안 됩니다. 고칠지와 golden 재고정은 메인이 정할 일입니다.
- 윤곽은 형상 전체에만 적용합니다. '끝이 뾰족'처럼 부분 형상, 구멍·고리(위상), 시간에 따른 형태 변화는 범위 밖입니다(`docs/viz-research-json-unity.md` E2·E5).
- 모양 모형이 있는 말과 윤곽어를 같이 말하면('둥글고 길쭉한') 모형이 이기고 길쭉함은 그려지지 않습니다(8.4 규칙 3, 기록에는 남음).
- 검증기 V5는 계속 v0 사전만 봅니다. 면담자가 새 윤곽어('갸름한')를 먼저 꺼내는 경우는 V5 사전 검사가 아니라 `strict_novel_content`에만 걸립니다.
- 변이 규칙층은 dev에서 값을 하나도 내지 않았습니다. 이득은 변이형이 실제로 얼마나 나오는지에 달렸고, 새 평가 문장(X13)으로 재야 합니다.
- 연구자 승인형 사전 확장으로 더한 항목은 `ext_lexicon` 사슬(v0 + v1 + 새 파일)로만 쓰입니다. 스펙 2.3 없이 1층 사전만 넓히는 설정은 아직 없습니다.

## 9. 매퍼 v2 builder 2.6.0: 형태 슬롯 우선순위 (2026-11-27)

계기는 연구 책임자의 `--config experiment` 시험 세션이다. 「기본 모형은 구형」·「동그란 원?」·「모양은 구체」라고 말했는데 물체가 직사각형 천으로 나왔다. '천'은 「바람이 불면 천이 펄럭이듯이 물체가 계속 꾸물꾸물 움직이는 느낌」의 움직임 비유 안 낱말이었다. 규칙과 수치는 `shared/lexicon/scene_params.v2.json` 2.1.0(`shapePriority`·`neutralSize`·`surfaceTerms`·`speedWish`), 시험은 `chatbot/tests/test_g69_shape_priority.py`다. v0·v1 출력은 그대로이고 스펙 판도 2.2.0 그대로다(스키마에 있는 값·사유만 씀).

| 고친 것 | 규칙 | 기록 |
| --- | --- | --- |
| 움직임 비유 매개어가 형태를 채움 | (A) '-듯이'·'-는 것처럼' 절의 명사는 같은 문장 뒤에 따로 주어가 있을 때 매개어. (B) 'N처럼 V'에서 V가 움직임 사전 낱말이면(결과 상태 '퍼진'·'퍼져 있어요'는 빼고) N이 매개어. 매개어는 `form.base`·`form.type`을 채우지 않는다 | `_alternatives`(lower_priority, rule `+actionSimile(…)`), 움직임 값 근거에 `actionSimile.<낱말>>motion.type:<값>` |
| 직접 형태 진술이 형상 낱말에 짐 | 모양어(round·square·flat·pointed)가 형상 낱말·매개어를 꾸미거나 서술하지 않으면 직접 진술. 맞지 않는 형상 낱말(`compatibleBase` 밖)과 비유에서 온 mist·shell·fragments를 내린다. 형태 틀 안 형상 낱말끼리('모양은 그릇 같아요')는 기존 규칙 | `_alternatives`(lower_priority, rule `+directShape(…)`) |
| '구형'·'구체'가 형태로 안 잡힘 | 모양 명사 → 모양어 round(Unity Sphere). 다른 명사를 꾸미면('구형 핸드폰') 안 씀, '구체적'·'구체화'도 안 씀(사전 '구체' blob도 v2에서 막음) | `_unmapped` category shape, rule `shapeNoun.<낱말>>shape:round` |
| 줄 끝 명사가 다음 줄 명사를 꾸민 것으로 읽힘 | `_noun_role`: 줄이 바뀌면 이름만 말한 것(named) | — |
| '보통 크기'가 비어 있음 | 크기 주제 명사와 함께 쓴 '보통·중간·적당' → `layout.size` 0.5(말함) | `neutralSize.보통>layout.size:0.5` |
| '무광' | 어절 표면형 → `material.roughness` 0.7(초안), '유광' 0.1 | `surfaceTerm.무광>material.roughness:matte` |
| '빨리 끝내고 싶다' → 빠르기 0.8 | 빠르기 부사가 '-고 싶-'을 꾸미면 쓰지 않음 | `_alternatives`(lower_priority, rule `+wish(…)`) |

- '-듯이' 절 안의 색·크기·질감 값은 층 2(비유)로 내려 직접 진술에 진다(「빨간 천이 펄럭이듯이 파란 물체가」 → 파랑). 비유 절의 움직임 동사는 물체가 움직이는 모양새라 그대로 둔다.
- 「천이 펄럭이듯이 움직여요」처럼 비유 절 뒤에 주어가 없으면 천이 물체일 수도 있어 지금처럼 그린다(보수적).
- `actionSimile.demoteFormType`(기본 true)을 false로 하면 form.type은 2.4.0처럼 둔다(「구름처럼 떠다녀요」 → mist). 기본 true에서는 형태가 빈 자리가 되어 후보 단계가 형태 축(blob·mist)을 벌린다.
- 물음표·'것 같아'(「역동적인 형체?」, 「동그란 원?」)는 '모른다'(`_uncertain`)가 아니라 말한 것으로 둔다(지금과 같음).

## 10. 스펙 2.4: 너비·높이·깊이 비율 `layout.proportions` (G72, 2026-11-27)

계기는 연구 책임자 시험 세션 test03이다. 「넓게 펼쳐진 안개가 떠오른다」가 뭉친 구름으로 그려졌다('펼쳐지'가 움직임 spreading으로만 읽혔고, 크기는 `layout.size` 하나뿐이었다). 켜는 법: `[mapping] proportions = "scene_params.v2.json"`(그 파일의 `proportions` 표, tableVersion 0.1.0). 실험 설정(`experiment.toml`)만 켜고, 다른 설정은 출력·builder 표기(2.6.0/2.7.0)·스펙 판(2.2.0/2.3.0)이 그대로다. 켜면 builder `scene-spec-builder-v2/2.8.0`, 스펙 2.4.0, `meta.pipeline.lexicons.proportionsTable`.

- **스키마 2.4.0**(`shared/schemas/scene-spec.v2.4.json`): `layout.proportions`는 반드시 있고(null 허용) 값은 `{x 너비, y 높이, z 깊이, axisSaid}`, 각 0.2–1, 가장 큰 값 = 1(이 규칙은 `scene_spec.proportion_problems`·Unity `Validate`). 2.0–2.3 문서에는 없어야 한다. 2.3 윤곽·발광 슬롯은 2.4.0에서 선택이다(ext를 켠 매핑만 셋을 함께 적음 — 읽지 않은 것을 '말하지 않음'으로 적지 않으려고). `layout.size`의 뜻은 그대로 '가장 긴 변'이다(G62-e).
- **매퍼 규칙**(참여자가 축을 말했을 때만, `phrase_rule`, rule `proportions.<profile>(<규칙>)>layout.proportions:<profile>`):

| 말 | profile (x, y, z) | axisSaid |
| --- | --- | --- |
| 넓게·옆으로 + 펼쳐진/퍼진/깔린(결과 상태), 펼쳐진(꾸미는 말 없이도), 넓적한 | spread (1, 0.3, 1) | 예 |
| 납작·평평 | flat (1, 0.3, 1) | 아니오(기본: 세로가 짧음) |
| 길쭉·기다란, 길게 늘어진 | elongated (0.4, 1, 0.4) | 아니오(기본: 세로가 김) |
| 높이·높게·우뚝 + 솟은, 키가 큰, 높다란 | tall (0.5, 1, 0.5) | 예 |
| 세로로·위아래로 / 가로로·옆으로 / 앞뒤로 + 긴·길쭉한 | vertical / wide / deep | 예 |

- **결과 상태 대 진행**: 용언 + 완료 관형형('펼쳐진')이나 '-어 있-'('펼쳐져 있어요')이면 퍼진 모양(비율)이고 그 용언은 움직임 값을 만들지 않는다. 진행·현재 꼴('펼쳐져요'·'펼쳐지고 있어요'·'퍼지는')은 지금처럼 움직임이다. 어미만 보는 결정론 규칙이고, builder 2.6.0이 비유에 이미 쓰는 구분(`actionSimile.resultativeETM`)과 같다.
- **범위**: 회상 문장, 움직임 비유의 절·매개어(G71) 안, 배경 낱말·신체 부위·자기 지칭을 꾸미거나 서술하는 말('넓게 펼쳐진 들판 위에 …')은 채우지 않는다. 부정은 `_negated`(category proportions). 처음 말한 것이 값, 다른 profile은 `_alternatives` later_mention. '납작·평평'이 모양 모형(납작 원기둥)으로 그려지는 자리면 비율로 한 번 더 납작하게 하지 않고 `_alternatives` lower_priority(`+shapeModel(flat)`). 방향을 말하지 않은 길쭉함은 같은 글의 자세가 방향을 정한다(lying·prone → wide, standing·hanging → vertical, `+posture(…)`).
- **2.3 `form.aspect`와의 관계**: ext와 함께 켜면 aspect는 그대로 기록되지만, 비율이 있으면(spec 값이나 조절) Unity는 aspect 축 배율을 쓰지 않고 비율만 쓴다(계획 JSON `aspectSupersededBy`).
- **Unity 해석**: 그리는 비율 p = clamp(원값 / 최대, 0.2, 1). 메시 형상과 안개(물체 좌표 레이마칭)는 비균일 배율, 조각은 조각 중심 분포만 늘림, 생성 메시(GLB)도 같은 비율 뒤 가장 긴 변 맞춤. 어느 경우든 가장 긴 변 = `layout.size`가 정한 길이(L0/L1 정규화). 비율이 null이면 2.2와 같은 그림·기록이고 2.4 문서면 defaultsUsed에 `layout.proportions`, axisSaid = false면 `layout.proportions.axis`.
- **조절 화면**(값 표 `candidate_values.v3.json`, 문구 `selection_protocol.v0.7.json`): 너비·높이·깊이 단계 [0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0](원값, 덮어쓰기 키 `layout.proportions.x·y·z`). 한 축을 올리면 그 축이 가장 길어지고 나머지가 상대적으로 줄어 보인다. 기록: `selection.json` 맨 위 `proportions`(축별 처음·최종 원값, 고쳤는지, 처음·최종 그리는 비율), `sources`·`sourceDetails`의 `layout.proportions`.
- **전후 비교**: 저장소의 합성 자료(시나리오·코퍼스·테스트 문자열) 4,640개를 켬/끔으로 돌려, 새 슬롯과 2.4 표기를 빼고 비교했다. 비율이 채워진 것 23개(길쭉 14, 넓게 퍼진·펼쳐진 8, 납작 1), 그 밖에 바뀐 것 20개는 모두 새 근거가 덮은 말의 기록 정리(`_clauses` usedFor·`_unmatched`·옛 움직임 대안)와 결과 상태 '넓게 퍼져 있어요'류 5개의 motion spreading → null뿐이다. 그림: `docs/validation/run-g72-proportions/`.
