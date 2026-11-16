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
- 만드는 코드: `chatbot/ifs_chatbot/scene_builder.py`(v0, 규칙 기반 기준선), `scene_builder_v1.py`(v1, 개선 매핑 — 6절) (형식 도우미는 `scene_spec.py`)
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

- `source`: `explicit_lexicon`(1층), `simile_marker`(2층), `vad_lexicon`(3층)
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
| `mode` | `"v1"` | 주 매핑. `scenes/{sessionId}.json`을 만든다. `"v0"`이면 규칙 기반 기준선 |
| `save_both` | `true` | 같은 확정 텍스트로 `scenes/{sessionId}.v0.json`(순수 v0, specVersion 2.0.0)과 `.v1.json`도 만든다 — 비교 설계(`docs/research-design.md` 3.1). 철회하면 셋 다 지운다 |
| `clarify_loop` | `false` | 확인 질문 루프(`docs/chatbot-design.md` 5-1). 확증 비교에서는 끈다 |
| `clarify_max` | `2` | 확인 질문 최대 횟수 |

- **대체 경로.** v1이 예외를 내거나 불러오지 못하면 v0 결과를 씁니다. 파일의 `meta.mapping = {requested: "v1", used: "v0", fallbackReason}`(specVersion 2.1.0), 세션 로그 `sceneSpec.fallback = true`·`sceneSpec.mapping`, 연구자 알림 `scene_mapping_fallback`이 남습니다. 면담 종료는 막지 않습니다.
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
