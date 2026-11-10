# SceneSpec v2 — 확정 텍스트 → 장면 기술 → Unity

Holodeck(CVPR 2024)처럼 "자연어 → 구조화된 장면 JSON → Unity" 순서로 갑니다. 다른 점은 가운데 단계에 LLM이 없다는 것입니다(AGENTS.md 1). 장면 속성은 사전과 규칙만 정하고, 같은 확정 텍스트는 언제나 같은 JSON이 됩니다.

```text
챗봇 면담 ─ [이대로 맞아요] ─▶ 확정 텍스트 ─▶ scene_builder (0층 Kiwi → 1층 사전 → 2층 직유 → 3층 V/A/D)
                                                 └▶ chatbot/logs/scenes/{sessionId}.json  (SceneSpec v2)
                                                        └▶ Unity SceneLoader: 프리팹 4종 + Shader Graph 파라미터 + Transform
                                                               └▶ initialScene.json · finalScene.json · events.csv
```

- 형식: `shared/schemas/scene-spec.v2.json` (JSON Schema 2020-12)
- 정답 예시: `chatbot/tests/fixtures/scene_spec/EX01.json`, `EX02.json`
- 만드는 코드: `chatbot/ifs_chatbot/scene_builder.py` (형식 도우미는 `scene_spec.py`)
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
| `_unmatched` | 1층 사전에 없는 내용어. 참여자가 말했지만 시스템이 읽지 못한 말 |
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
