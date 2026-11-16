# 전 과정 실행 검증(E2E) 결과

> 입력은 전부 **합성 대사**다(AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스). 참여자 데이터가 아니다. 수치는 이 합성 코퍼스에서의 공학 회귀 지표이며 심상 구현의 타당도 증거가 아니다(docs/acceptance.md 머리말).

- 코퍼스: imagery-heldout@1.0.0 · chatbot/tests/fixtures/imagery_corpus/heldout.json · sha256 f8d38ef5877c09bd899ee7cbadd491be5f2dfb8ffaf97169c1163ad716350d55
- 형식 검사(--check-corpus): 오류 0 · 경고 0
- 입력 수: 30 · 매핑: v0, v1 · 조건: 정적(조건 1), LLM 없음
- LLM·네트워크 차단(AC-3.9): 켬 — 8개 함수(socket.connect, httpx.get, httpx.post, Client.send, urllib.request.urlopen, OllamaBackend.generate, OllamaBackend._post, OfflineTemplateBackend.generate)를 호출 즉시 예외로 바꾼 상태에서 재생·매핑, 시도된 호출 0건
- 도구: e2e/0.1.0 · 채점기 fidelity/0.3.0 · 빌더 v0 = scene-spec-builder/0.1.0, v1 = scene-spec-builder-v1/1.2.0 · drift drift/1.1.0

## 스키마·파일

| 매핑 | spec 파일 | 스키마 | 스키마 유효 | 원칙 검사 문제 | 파일 = 재생 spec | 매핑 대체(폴백) |
| --- | --- | --- | --- | --- | --- | --- |
| v0 | 30 | scene-spec.v2.json | 30/30 | 0 | 30/30 | 0 |
| v1 | 30 | scene-spec.v2.1.json | 30/30 | 0 | 30/30 | 0 |

## 채점 요약(속성 단위, phrase_missing 제외)

| 지표 | v0 | v1 | 차이(v1 − v0) | 차이 95% CI |
| --- | --- | --- | --- | --- |
| reflectRate | 0.500 | 0.698 | 0.198 | [0.137, 0.259] |
| distortRate | 0.174 | 0.094 | -0.080 | [-0.123, -0.038] |
| lostRate | 0.160 | 0.014 | -0.146 | [-0.201, -0.095] |
| droppedRate | 0.108 | 0.108 | 0.000 | [0.000, 0.000] |
| preserveRate | 0.532 | 0.797 | 0.266 | [0.209, 0.325] |
| unreflectedVerbatimRate | 0.283 | 0.859 | 0.576 | [0.466, 0.682] |
| unreflectedVerbatimRateWithClauseIndex | 0.283 | 1.000 | 0.717 | [0.644, 0.788] |
| spuriousRate | 0.276 | 0.220 | -0.056 | [-0.082, -0.031] |
| unsupportedRate | 0.493 | 0.363 | -0.129 | [-0.181, -0.081] |
| fuzzyValueRate | 0.000 | 0.000 | 0.000 | [0.000, 0.000] |

| 매핑 | 속성 | 슬롯 속성 | 슬롯 상태 | 미반영 | 절 색인으로만 남은 손실 | 퍼지 경로 값 | 근거 없는 값(근거/경로/값 있는 슬롯) | 근거 없는 값 사유 | 매핑 대체 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v0 | 237 | 212 | reflected 106, distorted 37, preserved 12, lost 34, dropped_by_controller 23 | 106 | 0 | 0 | 100/56/203 | no_evidence 0, no_gold_span 67, outside_gold_span 33 | 0 |
| v1 | 237 | 212 | reflected 148, distorted 20, preserved 18, lost 3, dropped_by_controller 23 | 64 | 3 | 0 | 81/49/223 | no_evidence 0, no_gold_span 60, outside_gold_span 21 | 0 |

## 매핑별 신뢰구간(항목 단위 군집 부트스트랩 95%)

| 지표 | v0 | v1 |
| --- | --- | --- |
| reflectRate | 0.500 [0.434, 0.562] | 0.698 [0.641, 0.753] |
| distortRate | 0.174 [0.123, 0.228] | 0.094 [0.057, 0.133] |
| lostRate | 0.160 [0.114, 0.211] | 0.014 [0.000, 0.030] |
| droppedRate | 0.108 [0.057, 0.166] | 0.108 [0.057, 0.166] |
| preserveRate | 0.532 [0.473, 0.587] | 0.797 [0.757, 0.837] |
| unreflectedVerbatimRate | 0.283 [0.212, 0.356] | 0.859 [0.766, 0.946] |
| unreflectedVerbatimRateWithClauseIndex | 0.283 [0.212, 0.356] | 1.000 [1.000, 1.000] |
| spuriousRate | 0.276 [0.244, 0.311] | 0.220 [0.189, 0.249] |
| unsupportedRate | 0.493 [0.437, 0.551] | 0.363 [0.317, 0.412] |
| fuzzyValueRate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |

## drift(세션 로그, 참고 수치 — AC-2 집계 아님)

| 매핑 | drift | no_drift | undecidable | 오류 |
| --- | --- | --- | --- | --- |
| v0 | 3 | 7 | 20 | 0 |
| v1 | 3 | 7 | 20 | 0 |

## Unity

- report.json: unity/report.json · ok = True · spec 파일 60 · 로드 60 · 캡처 실패 0
- Console 오류 0 · 예외 0 · 스크린샷(장면 PNG) 60/60 · 상세 PNG 59
- Unity 로그: 오류 패턴(error CS·Shader error·Exception) 0건 · '[SceneLoader] … 로드:' 줄 60개 · 읽기 실패 0 · 형식 경고 0 · 끝 표시 ['True']
- 적용값 대조: 원천 (나) · 수치 306개 · max |Δ| = 0.0 · 미달 0 · 반올림 경계 0 · 범주 불일치 0 · defaultsUsed 불일치 0
- 프레임 시간 p95 최댓값(데스크톱 대리 측정): 1.693 ms

## 실패·오류 목록

### v0

| 항목 | 유형 | 속성/경로 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| H01 | dropped_by_controller | size | 구슬치기 구슬만 해요 | {"range": [0.0, 0.35]} | – | – |
| H01 | distorted/cross_slot | color | 연두빛이 살짝 | {"hue_deg": [65, 115], "s": null, "l": [0.4, 0.9]} | – | [{"path": "material.brightness", "trigger": "빛", "value": 0.7}] |
| H01 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| H01 | spurious | body.part |  | – | body | ["몸"] |
| H01 | unsupported/no_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| H02 | lost | opacity | 뒤가 다 비쳐 보여요 | {"range": [0.0, 0.35]} | – | [] |
| H02 | distorted/wrong_value | size | 방 하나를 채울 만큼 커요 | {"range": [0.75, 1.0]} | 0.621 | ["커요"] |
| H02 | dropped_by_controller | brightness | 좀 어두운 편 | {"range": [0.1, 0.45]} | – | – |
| H02 | spurious | material.saturation |  | – | 0.750 | ["짙어졌다"] |
| H02 | spurious | layout.verticalOffset |  | – | 0.040 | ["발"] |
| H02 | spurious | body.part |  | – | body | ["몸"] |
| H03 | dropped_by_controller | size | 제 머리만 해요 | {"range": [0.3, 0.6]} | – | – |
| H03 | dropped_by_controller | saturation | 선명한 | {"range": [0.6, 1.0]} | – | – |
| H03 | dropped_by_controller | brightness | 밝아요 | {"range": [0.6, 1.0]} | – | – |
| H03 | spurious | body.part |  | – | body | ["몸"] |
| H03 | unsupported/outside_gold_span | motion.type |  | – | floating | ["떠", "떠"] |
| H04 | distorted/wrong_value | color | 빨간 | {"hue_deg": [345, 15], "s": [0.5, 1.0], "l": [0.3, 0.65]} | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파란"] |
| H04 | lost | form | 공이 | {"in": ["blob"]} | – | [] |
| H04 | lost | height | 바닥에 | {"range": [0.0, 0.1]} | – | [] |
| H04 | lost | texture_roughness | 반들반들해요 | {"range": [0.0, 0.3]} | – | [] |
| H04 | spurious | body.part |  | – | body | ["몸"] |
| H04 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파란"] |
| H04 | unsupported/outside_gold_span | layout.distance |  | – | 0.600 | ["떨어져"] |
| H05 | dropped_by_controller | color | 회색이 섞인 검은색 | {"hue_deg": null, "s": [0.0, 0.2], "l": [0.05, 0.35]} | – | – |
| H05 | lost | weight | 묵직할 것 같아요 | – | – | – |
| H05 | lost | size | 주먹만 하고 | {"range": [0.05, 0.45]} | – | [] |
| H05 | spurious | body.part |  | – | body | ["몸"] |
| H05 | spurious | body.layer |  | – | around | ["밖"] |
| H05 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.08} | ["검은"] |
| H06 | distorted/wrong_value | posture | 매달려 있는 | {"in": ["hanging", "drooping"]} | sagging | ["늘어져서"] |
| H06 | lost | shape | 아주 가늘고 | – | – | – |
| H06 | lost | size | 길이는 1미터쯤 | {"range": [0.4, 0.8]} | – | [] |
| H06 | spurious | body.part |  | – | shoulder | ["어깨"] |
| H06 | unsupported/outside_gold_span | form.posture |  | – | sagging | ["늘어져서"] |
| H06 | unsupported/outside_gold_span | material.brightness |  | – | 0.700 | ["빛"] |
| H07 | distorted/wrong_value | body_part | 배 안쪽 | {"in": ["belly", "lower_belly"]} | body | ["몸"] |
| H07 | distorted/wrong_value | brightness | 은은하게 빛나고 | {"range": [0.4, 0.8]} | 0.900 | ["빛나고"] |
| H07 | lost | size | 귤 하나 정도 | {"range": [0.1, 0.45]} | – | [] |
| H07 | distorted/wrong_value | motion_type | 맥박 뛰듯이 | {"in": ["pounding", "vibrating", "trembling"]} | moving | ["움직여요"] |
| H07 | spurious | layout.verticalOffset |  | – | 0.600 | ["배"] |
| H07 | spurious | body.layer |  | – | inner | ["안쪽"] |
| H07 | unsupported/outside_gold_span | motion.type |  | – | moving | ["움직여요"] |
| H07 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H08 | dropped_by_controller | brightness | 밝아요 | {"range": [0.6, 1.0]} | – | – |
| H08 | lost | shape | 모서리가 날카롭고 | – | – | – |
| H08 | lost | size | 손톱만 해요 | {"range": [0.0, 0.25]} | – | [] |
| H08 | spurious | layout.distance |  | – | 0.850 | ["멀어져요"] |
| H08 | spurious | body.part |  | – | body | ["몸"] |
| H08 | unsupported/outside_gold_span | material.erosion |  | – | 0.600 | ["깨진"] |
| H09 | distorted/cross_slot | motion_type | 위로 피어올라요 | {"in": ["rising", "spreading"]} | – | [{"path": "body.layer", "trigger": "위", "value": "surface_above"}] |
| H09 | distorted/cross_slot | size | 제 허리쯤까지 | {"range": [0.45, 0.9]} | – | [{"path": "layout.verticalOffset", "trigger": "허리", "value": 0.6}, {"path": "body.part", "trigger": "허리", "value": "lower_back"}] |
| H09 | distorted/wrong_value | body_layer | 몸 앞쪽 | {"in": ["around_front", "around"]} | surface_above | ["위"] |
| H09 | spurious | material.brightness |  | – | 0.300 | ["흐려져서"] |
| H09 | spurious | material.saturation |  | – | 0.750 | ["짙고"] |
| H09 | spurious | layout.verticalOffset |  | – | 0.600 | ["허리"] |
| H09 | spurious | body.part |  | – | lower_back | ["허리"] |
| H09 | unsupported/outside_gold_span | body.layer |  | – | surface_above | ["위"] |
| H10 | dropped_by_controller | color | 짙은 갈색 | {"hue_deg": [10, 45], "s": null, "l": [0.1, 0.4]} | – | – |
| H10 | lost | distance | 1미터 앞 | {"range": [0.15, 0.4]} | – | [] |
| H10 | lost | height | 바닥에 | {"range": [0.0, 0.1]} | – | [] |
| H10 | lost | shape | 네모반듯한 | – | – | – |
| H10 | lost | size | 한 변이 30센티쯤 | {"range": [0.25, 0.65]} | – | [] |
| H10 | dropped_by_controller | brightness | 조금 어두워요 | {"range": [0.15, 0.45]} | – | – |
| H10 | spurious | body.part |  | – | body | ["몸"] |
| H10 | spurious | body.layer |  | – | around | ["밖"] |
| H10 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 24.8, "s": 0.45, "l": 0.3} | ["갈색"] |
| H11 | dropped_by_controller | color | 연한 분홍 | {"hue_deg": [300, 10], "s": null, "l": [0.65, 0.95]} | – | – |
| H11 | distorted/wrong_value | body_part | 손등 | {"in": ["hand"]} | body | ["몸"] |
| H11 | lost | other | 말랑말랑한 | – | – | – |
| H11 | lost | size | 탁구공만 해요 | {"range": [0.0, 0.35]} | – | [] |
| H11 | spurious | body.layer |  | – | surface | ["표면"] |
| H11 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 339.8, "s": 0.6, "l": 0.78} | ["분홍빛"] |
| H11 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H12 | lost | shape | 끝이 뾰족해요 | – | – | – |
| H12 | lost | brightness | 반짝반짝해요 | {"range": [0.6, 1.0]} | – | [] |
| H12 | distorted/wrong_value | height | 눈높이보다 조금 아래 | {"range": [0.75, 0.92]} | 0.490 | ["손바닥"] |
| H12 | spurious | body.part |  | – | hand | ["손바닥"] |
| H12 | unsupported/outside_gold_span | layout.verticalOffset |  | – | 0.490 | ["손바닥"] |
| H13 | dropped_by_controller | color | 짙은 남색 | {"hue_deg": [215, 250], "s": null, "l": [0.08, 0.4]} | – | – |
| H13 | distorted/wrong_value | body_part | 목 안쪽 | {"in": ["throat", "throat_neck"]} | body | ["몸"] |
| H13 | lost | motion_type | 아래로 내려가요 | {"in": ["sinking", "settling"]} | – | [] |
| H13 | distorted/wrong_value | size | 콩알만 해요 | {"range": [0.0, 0.25]} | 0.316 | ["작아요"] |
| H13 | dropped_by_controller | brightness | 어두운 편 | {"range": [0.05, 0.4]} | – | – |
| H13 | spurious | layout.verticalOffset |  | – | 0.850 | ["목"] |
| H13 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 230.0, "s": 0.55, "l": 0.25} | ["남색"] |
| H13 | unsupported/outside_gold_span | material.roughness |  | – | 0.250 | ["촉촉해요"] |
| H13 | unsupported/outside_gold_span | layout.size |  | – | 0.316 | ["작아요"] |
| H13 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H13 | unsupported/outside_gold_span | body.layer |  | – | inner | ["안쪽"] |
| H14 | lost | size | 농구공 정도요 | {"range": [0.35, 0.65]} | – | [] |
| H14 | dropped_by_controller | color | 어떤 색인지는 잘 모르겠어요 | {"equals": null} | – | – |
| H14 | dropped_by_controller | brightness | 밝지도 어둡지도 않아요 | {"range": [0.35, 0.65]} | – | – |
| H14 | spurious | body.part |  | – | body | ["몸"] |
| H14 | unsupported/no_gold_span | material.brightness |  | – | 0.300 | ["흐릿해서"] |
| H14 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| H15 | distorted/wrong_value | height | 눈높이 | {"range": [0.85, 1.0]} | 0.630 | ["팔"] |
| H15 | distorted/wrong_value | size | 팔찌보다 조금 큰 | {"range": [0.15, 0.5]} | 0.621 | ["큰"] |
| H15 | lost | shape | 가운데가 뻥 뚫려 | – | – | – |
| H15 | distorted/cross_slot | distance | 팔 뻗으면 닿을 거리 | {"range": [0.05, 0.3]} | – | [{"path": "layout.verticalOffset", "trigger": "팔", "value": 0.63}, {"path": "body.part", "trigger": "팔", "value": "arm"}] |
| H15 | spurious | body.part |  | – | arm | ["팔"] |
| H15 | spurious | body.layer |  | – | surface | ["겉"] |
| H15 | unsupported/outside_gold_span | layout.verticalOffset |  | – | 0.630 | ["팔"] |
| H15 | unsupported/outside_gold_span | motion.type |  | – | rotating | ["돌고", "돌아요"] |
| H16 | dropped_by_controller | color | 옅은 하늘색 | {"hue_deg": [185, 215], "s": null, "l": [0.6, 0.92]} | – | – |
| H16 | distorted/wrong_value | body_part | 등 쪽 | {"in": ["back"]} | body | ["몸"] |
| H16 | lost | opacity | 반쯤 비쳐요 | {"range": [0.25, 0.7]} | – | [] |
| H16 | dropped_by_controller | brightness | 은은하게 밝아요 | {"range": [0.5, 0.8]} | – | – |
| H16 | spurious | layout.distance |  | – | 0.000 | ["붙어"] |
| H16 | spurious | layout.verticalOffset |  | – | 0.720 | ["등", "등"] |
| H16 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 200.2, "s": 0.7, "l": 0.75} | ["하늘색"] |
| H16 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H17 | dropped_by_controller | size | 쌀알만 해요 | {"range": [0.0, 0.15]} | – | – |
| H17 | dropped_by_controller | saturation | 쨍한 | {"range": [0.7, 1.0]} | – | – |
| H17 | distorted/wrong_value | body_part | 손바닥 | {"in": ["hand"]} | body | ["몸"] |
| H17 | lost | other | 단단해 보여요 | – | – | – |
| H17 | spurious | layout.verticalOffset |  | – | 0.490 | ["손바닥"] |
| H17 | unsupported/no_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| H17 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H18 | distorted/wrong_value | color | 회색 | {"hue_deg": null, "s": [0.0, 0.2], "l": [0.3, 0.7]} | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H18 | distorted/wrong_value | brightness | 어두워요 | {"range": [0.0, 0.4]} | 0.800 | ["밝은데"] |
| H18 | lost | size | 소파만 하고 | {"range": [0.65, 1.0]} | – | [] |
| H18 | distorted/wrong_value | height | 제 머리보다 약간 높은 | {"range": [0.95, 1.0]} | 0.930 | ["머리"] |
| H18 | spurious | body.part |  | – | head | ["머리"] |
| H18 | spurious | body.layer |  | – | around | ["밖"] |
| H18 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H18 | unsupported/outside_gold_span | material.brightness |  | – | 0.800 | ["밝은데"] |
| H18 | unsupported/outside_gold_span | motion.type |  | – | drifting | ["떠다녀요", "떠다녀요"] |
| H19 | dropped_by_controller | saturation | 아주 선명한 | {"range": [0.7, 1.0]} | – | – |
| H19 | dropped_by_controller | brightness | 환하게 빛나요 | {"range": [0.7, 1.0]} | – | – |
| H19 | lost | shape | 뾰족하게 솟아 | – | – | – |
| H19 | distorted/wrong_value | size | 제 손보다 조금 커요 | {"range": [0.2, 0.55]} | 0.621 | ["커요"] |
| H19 | dropped_by_controller | motion_type | 빙글 돌아요 | {"in": ["rotating", "circling"]} | – | – |
| H19 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| H19 | spurious | layout.verticalOffset |  | – | 0.490 | ["손"] |
| H19 | spurious | body.part |  | – | body | ["몸"] |
| H19 | spurious | body.layer |  | – | around | ["밖"] |
| H19 | unsupported/no_gold_span | material.brightness |  | – | 0.700 | ["빛", "빛"] |
| H19 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| H20 | lost | height | 발밑이요 | {"range": [0.0, 0.1]} | – | [] |
| H20 | spurious | body.part |  | – | body | ["몸"] |
| H20 | spurious | body.layer |  | – | around | ["밖"] |
| H21 | lost | distance | 눈앞에 | {"range": [0.0, 0.3]} | – | [] |
| H21 | lost | motion_speed | 천천이 | {"range": [0.0, 0.4]} | – | [] |
| H21 | spurious | body.part |  | – | body | ["몸"] |
| H21 | spurious | body.layer |  | – | around | ["밖"] |
| H22 | dropped_by_controller | color | 눈처럼 하얘요 | {"hue_deg": null, "s": null, "l": [0.85, 1.0]} | – | – |
| H22 | distorted/wrong_value | body_part | 왼쪽 어깨 | {"in": ["shoulder"]} | body | ["몸"] |
| H22 | lost | motion_type | 천천히 내려오고 | {"in": ["sinking", "settling", "drifting", "floating"]} | – | [] |
| H22 | lost | weight | 아주 가볍고 | – | – | – |
| H22 | lost | other | 보송보송해요 | – | – | – |
| H22 | distorted/wrong_value | size | 새끼손가락 길이쯤 | {"range": [0.0, 0.3]} | 0.316 | ["작아요"] |
| H22 | lost | erosion | 가장자리가 살짝 흐트러져 | {"range": [0.05, 0.5]} | – | [] |
| H22 | spurious | layout.verticalOffset |  | – | 0.820 | ["어깨"] |
| H22 | spurious | body.layer |  | – | around | ["주변", "근처"] |
| H22 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H22 | unsupported/outside_gold_span | layout.size |  | – | 0.316 | ["작아요"] |
| H22 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H23 | lost | height | 발밑에 | {"range": [0.0, 0.1]} | – | [] |
| H23 | distorted/wrong_value | size | 아주 작고 | {"range": [0.0, 0.3]} | 0.316 | ["작은", "작고"] |
| H23 | lost | texture_roughness | 까슬까슬할 | {"range": [0.55, 1.0]} | – | [] |
| H23 | spurious | body.part |  | – | body | ["몸"] |
| H23 | spurious | body.layer |  | – | around | ["주변"] |
| H23 | unsupported/outside_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| H24 | distorted/wrong_value | body_part | 손등 | {"in": ["hand"]} | body | ["몸"] |
| H24 | distorted/wrong_value | color | 아주 살짝 푸른 기 | {"hue_deg": [180, 240], "s": [0.0, 0.35], "l": null} | {"hue_deg": 204.8, "s": 0.55, "l": 0.5} | ["푸른"] |
| H24 | distorted/cross_slot | size | 손 전체를 덮을 정도 | {"range": [0.2, 0.55]} | – | [{"path": "layout.verticalOffset", "trigger": "손", "value": 0.49}] |
| H24 | spurious | layout.verticalOffset |  | – | 0.490 | ["손"] |
| H24 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| H25 | distorted/wrong_value | size | 사람 키만 하고 | {"range": [0.7, 1.0]} | 0.646 | ["커다란"] |
| H25 | lost | distance | 2미터쯤 | {"range": [0.55, 0.75]} | – | [] |
| H25 | lost | texture_roughness | 약간 오돌토돌해요 | {"range": [0.45, 0.8]} | – | [] |
| H25 | spurious | body.part |  | – | body | ["몸"] |
| H25 | spurious | body.layer |  | – | around | ["밖"] |
| H25 | unsupported/outside_gold_span | form.posture |  | – | standing | ["서"] |
| H25 | unsupported/outside_gold_span | layout.size |  | – | 0.646 | ["커다란"] |
| H26 | distorted/cross_slot | color | 밝은 연두 | {"hue_deg": [70, 110], "s": null, "l": [0.5, 0.85]} | – | [{"path": "material.brightness", "trigger": "밝은", "value": 0.8}] |
| H26 | lost | texture_roughness | 보풀보풀해요 | {"range": [0.45, 1.0]} | – | [] |
| H26 | distorted/wrong_value | size | 야구공보다 조금 커요 | {"range": [0.2, 0.55]} | 0.621 | ["커요"] |
| H26 | spurious | material.brightness |  | – | 0.800 | ["밝은"] |
| H26 | spurious | body.part |  | – | body | ["몸"] |
| H26 | unsupported/outside_gold_span | body.layer |  | – | around | ["밖"] |
| H27 | lost | color | 검붉은 | {"hue_deg": [340, 20], "s": null, "l": [0.08, 0.35]} | – | [] |
| H27 | distorted/wrong_value | erosion | 조금씩 부서져 | {"range": [0.25, 0.7]} | 0.850 | ["부서져"] |
| H27 | spurious | body.part |  | – | body | ["몸"] |
| H27 | spurious | body.layer |  | – | around_side | ["옆", "옆"] |
| H28 | distorted/wrong_value | brightness | 밝기는 중간쯤 | {"range": [0.35, 0.65]} | 0.300 | ["흐릿한"] |
| H28 | distorted/cross_slot | opacity | 흐릿한 | {"range": [0.0, 0.7]} | – | [{"path": "material.brightness", "trigger": "흐릿한", "value": 0.3}] |
| H28 | spurious | layout.size |  | – | 0.316 | ["작았는데"] |
| H28 | spurious | motion.type |  | – | spreading | ["퍼진"] |
| H28 | spurious | body.part |  | – | head | ["머리"] |
| H28 | unsupported/outside_gold_span | material.brightness |  | – | 0.300 | ["흐릿한"] |
| H29 | lost | height | 무릎 높이쯤 | {"range": [0.2, 0.35]} | – | [] |
| H29 | lost | texture_roughness | 거칠거칠해요 | {"range": [0.6, 1.0]} | – | [] |
| H29 | lost | size | 수박만 한 | {"range": [0.45, 0.75]} | – | [] |
| H29 | lost | distance | 한 발짝 거리 | {"range": [0.05, 0.35]} | – | [] |
| H29 | spurious | body.part |  | – | body | ["몸"] |
| H29 | spurious | body.layer |  | – | around | ["밖"] |
| H30 | distorted/wrong_value | color | 파란 | {"hue_deg": [200, 250], "s": null, "l": null} | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H30 | lost | opacity | 속이 비쳐요 | {"range": [0.05, 0.6]} | – | [] |
| H30 | distorted/wrong_value | height | 가슴 높이쯤 | {"range": [0.6, 0.82]} | 0.490 | ["손바닥"] |
| H30 | lost | distance | 바로 앞이에요 | {"range": [0.0, 0.25]} | – | [] |
| H30 | spurious | body.part |  | – | hand | ["손바닥"] |
| H30 | spurious | body.layer |  | – | surface_above | ["위"] |
| H30 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H30 | unsupported/outside_gold_span | layout.verticalOffset |  | – | 0.490 | ["손바닥"] |

### v1

| 항목 | 유형 | 속성/경로 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| H01 | distorted/wrong_value | opacity | 투명한 | {"range": [0.0, 0.35]} | 0.500 | ["비치는"] |
| H01 | dropped_by_controller | size | 구슬치기 구슬만 해요 | {"range": [0.0, 0.35]} | – | – |
| H01 | spurious | body.part |  | – | body | ["몸"] |
| H01 | unsupported/outside_gold_span | material.opacity |  | – | 0.500 | ["비치는"] |
| H01 | unsupported/no_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| H02 | distorted/wrong_value | size | 방 하나를 채울 만큼 커요 | {"range": [0.75, 1.0]} | 0.621 | ["커요"] |
| H02 | dropped_by_controller | brightness | 좀 어두운 편 | {"range": [0.1, 0.45]} | – | – |
| H02 | spurious | material.saturation |  | – | 0.750 | ["짙어졌다"] |
| H02 | spurious | layout.verticalOffset |  | – | 0.020 | ["발밑"] |
| H02 | spurious | body.part |  | – | foot | ["발"] |
| H03 | dropped_by_controller | size | 제 머리만 해요 | {"range": [0.3, 0.6]} | – | – |
| H03 | dropped_by_controller | saturation | 선명한 | {"range": [0.6, 1.0]} | – | – |
| H03 | dropped_by_controller | brightness | 밝아요 | {"range": [0.6, 1.0]} | – | – |
| H03 | spurious | body.part |  | – | head | ["머리"] |
| H04 | spurious | body.part |  | – | body | ["몸"] |
| H05 | dropped_by_controller | color | 회색이 섞인 검은색 | {"hue_deg": null, "s": [0.0, 0.2], "l": [0.05, 0.35]} | – | – |
| H05 | spurious | body.part |  | – | foot | ["발"] |
| H05 | spurious | body.layer |  | – | around | ["밖"] |
| H05 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.08} | ["검은"] |
| H06 | distorted/wrong_value | posture | 매달려 있는 | {"in": ["hanging", "drooping"]} | sagging | ["늘어져서"] |
| H06 | distorted/wrong_value | size | 길이는 1미터쯤 | {"range": [0.4, 0.8]} | 0.887 | ["1미터쯤"] |
| H06 | spurious | body.part |  | – | body | ["몸"] |
| H06 | unsupported/outside_gold_span | form.posture |  | – | sagging | ["늘어져서"] |
| H06 | unsupported/outside_gold_span | material.brightness |  | – | 0.700 | ["빛"] |
| H06 | unsupported/outside_gold_span | body.layer |  | – | around_side | ["옆"] |
| H07 | distorted/wrong_value | motion_type | 맥박 뛰듯이 | {"in": ["pounding", "vibrating", "trembling"]} | moving | ["움직여요"] |
| H07 | spurious | body.layer |  | – | inner | ["안", "안쪽"] |
| H07 | unsupported/outside_gold_span | motion.type |  | – | moving | ["움직여요"] |
| H08 | dropped_by_controller | brightness | 밝아요 | {"range": [0.6, 1.0]} | – | – |
| H08 | spurious | layout.distance |  | – | 0.850 | ["멀어져요"] |
| H08 | spurious | body.part |  | – | body | ["몸"] |
| H08 | unsupported/outside_gold_span | material.erosion |  | – | 0.600 | ["깨진"] |
| H09 | distorted/cross_slot | size | 제 허리쯤까지 | {"range": [0.45, 0.9]} | – | [{"path": "body.part", "trigger": "허리", "value": "lower_back"}] |
| H09 | distorted/wrong_value | body_layer | 몸 앞쪽 | {"in": ["around_front", "around"]} | surface_above | ["위"] |
| H09 | spurious | material.saturation |  | – | 0.750 | ["짙고"] |
| H09 | spurious | layout.verticalOffset |  | – | 0.050 | ["바닥"] |
| H09 | spurious | body.part |  | – | lower_back | ["허리"] |
| H09 | unsupported/outside_gold_span | body.layer |  | – | surface_above | ["위"] |
| H10 | dropped_by_controller | color | 짙은 갈색 | {"hue_deg": [10, 45], "s": null, "l": [0.1, 0.4]} | – | – |
| H10 | dropped_by_controller | brightness | 조금 어두워요 | {"range": [0.15, 0.45]} | – | – |
| H10 | spurious | body.part |  | – | body | ["몸"] |
| H10 | spurious | body.layer |  | – | around | ["밖"] |
| H10 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 24.8, "s": 0.45, "l": 0.3} | ["갈색"] |
| H11 | dropped_by_controller | color | 연한 분홍 | {"hue_deg": [300, 10], "s": null, "l": [0.65, 0.95]} | – | – |
| H11 | spurious | body.layer |  | – | surface | ["표면"] |
| H11 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 339.8, "s": 0.6, "l": 0.78} | ["분홍빛"] |
| H12 | distorted/wrong_value | size | 손바닥만 한 | {"range": [0.1, 0.45]} | 0.475 | ["손바닥만 한"] |
| H12 | spurious | body.part |  | – | body | ["몸"] |
| H12 | unsupported/outside_gold_span | body.layer |  | – | around | ["밖"] |
| H13 | dropped_by_controller | color | 짙은 남색 | {"hue_deg": [215, 250], "s": null, "l": [0.08, 0.4]} | – | – |
| H13 | dropped_by_controller | brightness | 어두운 편 | {"range": [0.05, 0.4]} | – | – |
| H13 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 230.0, "s": 0.55, "l": 0.25} | ["남색"] |
| H13 | unsupported/outside_gold_span | material.roughness |  | – | 0.250 | ["촉촉해요"] |
| H13 | unsupported/outside_gold_span | layout.size |  | – | 0.224 | ["작아요"] |
| H14 | dropped_by_controller | color | 어떤 색인지는 잘 모르겠어요 | {"equals": null} | – | – |
| H14 | dropped_by_controller | brightness | 밝지도 어둡지도 않아요 | {"range": [0.35, 0.65]} | – | – |
| H14 | spurious | body.part |  | – | body | ["몸"] |
| H14 | unsupported/no_gold_span | material.brightness |  | – | 0.300 | ["흐릿해서"] |
| H14 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| H15 | distorted/wrong_value | size | 팔찌보다 조금 큰 | {"range": [0.15, 0.5]} | 0.573 | ["큰"] |
| H15 | distorted/cross_slot | distance | 팔 뻗으면 닿을 거리 | {"range": [0.05, 0.3]} | – | [{"path": "body.part", "trigger": "팔", "value": "arm"}] |
| H15 | spurious | body.part |  | – | arm | ["팔"] |
| H15 | spurious | body.layer |  | – | around_front | ["앞"] |
| H16 | dropped_by_controller | color | 옅은 하늘색 | {"hue_deg": [185, 215], "s": null, "l": [0.6, 0.92]} | – | – |
| H16 | dropped_by_controller | brightness | 은은하게 밝아요 | {"range": [0.5, 0.8]} | – | – |
| H16 | spurious | layout.distance |  | – | 0.000 | ["붙어"] |
| H16 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 200.2, "s": 0.7, "l": 0.75} | ["하늘색"] |
| H17 | dropped_by_controller | size | 쌀알만 해요 | {"range": [0.0, 0.15]} | – | – |
| H17 | dropped_by_controller | saturation | 쨍한 | {"range": [0.7, 1.0]} | – | – |
| H17 | spurious | form.type |  | – | fragments | ["알갱이"] |
| H17 | unsupported/no_gold_span | layout.size |  | – | 0.224 | ["작은"] |
| H18 | distorted/wrong_value | brightness | 어두워요 | {"range": [0.0, 0.4]} | 0.800 | ["밝은데"] |
| H18 | distorted/cross_slot | height | 제 머리보다 약간 높은 | {"range": [0.95, 1.0]} | – | [{"path": "body.part", "trigger": "머리", "value": "head"}] |
| H18 | spurious | body.part |  | – | head | ["머리"] |
| H18 | spurious | body.layer |  | – | around | ["밖"] |
| H18 | unsupported/outside_gold_span | material.brightness |  | – | 0.800 | ["밝은데"] |
| H18 | unsupported/outside_gold_span | motion.type |  | – | floating | ["둥둥"] |
| H19 | dropped_by_controller | saturation | 아주 선명한 | {"range": [0.7, 1.0]} | – | – |
| H19 | dropped_by_controller | brightness | 환하게 빛나요 | {"range": [0.7, 1.0]} | – | – |
| H19 | dropped_by_controller | motion_type | 빙글 돌아요 | {"in": ["rotating", "circling"]} | – | – |
| H19 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| H19 | spurious | body.part |  | – | body | ["몸"] |
| H19 | spurious | body.layer |  | – | around | ["밖"] |
| H19 | unsupported/no_gold_span | material.brightness |  | – | 0.700 | ["빛", "빛"] |
| H19 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| H20 | spurious | body.part |  | – | body | ["몸"] |
| H20 | spurious | body.layer |  | – | around | ["밖"] |
| H21 | distorted/wrong_value | motion_type | 둥둥 떠잇어요 | {"in": ["floating", "drifting"]} | moving | ["움직여여"] |
| H21 | spurious | body.part |  | – | body | ["몸"] |
| H21 | spurious | body.layer |  | – | around | ["밖"] |
| H21 | unsupported/outside_gold_span | motion.type |  | – | moving | ["움직여여"] |
| H22 | dropped_by_controller | color | 눈처럼 하얘요 | {"hue_deg": null, "s": null, "l": [0.85, 1.0]} | – | – |
| H22 | lost | motion_type | 천천히 내려오고 | {"in": ["sinking", "settling", "drifting", "floating"]} | – | [] |
| H22 | spurious | body.layer |  | – | around | ["주변", "근처"] |
| H22 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H22 | unsupported/outside_gold_span | layout.size |  | – | 0.224 | ["작아요"] |
| H23 | distorted/wrong_value | size | 아주 작고 | {"range": [0.0, 0.3]} | 0.316 | ["작은"] |
| H23 | spurious | body.part |  | – | body | ["몸"] |
| H23 | spurious | body.layer |  | – | around | ["주변"] |
| H23 | unsupported/outside_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| H24 | distorted/wrong_value | color | 아주 살짝 푸른 기 | {"hue_deg": [180, 240], "s": [0.0, 0.35], "l": null} | {"hue_deg": 204.8, "s": 0.55, "l": 0.5} | ["푸른"] |
| H24 | lost | size | 손 전체를 덮을 정도 | {"range": [0.2, 0.55]} | – | [] |
| H24 | spurious | motion.speed |  | – | 0.250 | ["잔잔하게"] |
| H25 | spurious | body.part |  | – | body | ["몸"] |
| H25 | spurious | body.layer |  | – | around | ["밖"] |
| H25 | unsupported/outside_gold_span | form.posture |  | – | standing | ["서"] |
| H26 | distorted/cross_slot | height | 배꼽 앞쪽 | {"range": [0.5, 0.65]} | – | [{"path": "body.part", "trigger": "배꼽", "value": "belly"}] |
| H26 | spurious | body.part |  | – | belly | ["배꼽"] |
| H26 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 90.0, "s": 0.55, "l": 0.55} | ["연두색"] |
| H26 | unsupported/outside_gold_span | body.layer |  | – | around | ["밖"] |
| H27 | distorted/cross_slot | height | 어깨 옆 | {"range": [0.72, 0.9]} | – | [{"path": "body.part", "trigger": "어깨", "value": "shoulder"}, {"path": "body.layer", "trigger": "옆", "value": "around_side"}] |
| H27 | distorted/wrong_value | erosion | 조금씩 부서져 | {"range": [0.25, 0.7]} | 0.850 | ["부서져"] |
| H27 | spurious | body.part |  | – | shoulder | ["어깨"] |
| H27 | spurious | body.layer |  | – | around_side | ["옆", "옆"] |
| H28 | distorted/wrong_value | brightness | 밝기는 중간쯤 | {"range": [0.35, 0.65]} | 0.700 | ["빛", "빛"] |
| H28 | lost | opacity | 흐릿한 | {"range": [0.0, 0.7]} | – | [] |
| H28 | spurious | layout.size |  | – | 0.316 | ["작았는데"] |
| H28 | spurious | motion.type |  | – | spreading | ["퍼진"] |
| H28 | spurious | body.part |  | – | head | ["머리"] |
| H28 | unsupported/outside_gold_span | material.brightness |  | – | 0.700 | ["빛", "빛"] |
| H28 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| H29 | spurious | body.part |  | – | body | ["몸"] |
| H29 | spurious | body.layer |  | – | around | ["밖"] |
| H30 | distorted/wrong_value | size | 손바닥만 하고 | {"range": [0.1, 0.45]} | 0.475 | ["손바닥만 하고"] |
| H30 | spurious | material.brightness |  | – | 0.850 | ["반짝반짝"] |
| H30 | spurious | body.part |  | – | body | ["몸"] |
| H30 | spurious | body.layer |  | – | around | ["밖"] |

## 미반영 원문 보존 실패(AC-3.5 분자에서 빠진 속성)

반영·포착·컨트롤러 탈락이 아닌 속성 중 phrase가 속성 단위 보존 필드에 원문 그대로 없는 것. '절 색인만'은 _clauses로만 남은 것(판정에서 인정하지 않음).

| 매핑 | 항목 | 속성 | kind | 상태 | phrase | 절 색인만 |
| --- | --- | --- | --- | --- | --- | --- |
| v0 | H01 | color | slot | distorted/cross_slot | 연두빛이 살짝 | 아니오 |
| v0 | H02 | opacity | slot | lost | 뒤가 다 비쳐 보여요 | 아니오 |
| v0 | H02 | size | slot | distorted/wrong_value | 방 하나를 채울 만큼 커요 | 아니오 |
| v0 | H04 | form | slot | lost | 공이 | 아니오 |
| v0 | H04 | height | slot | lost | 바닥에 | 아니오 |
| v0 | H04 | texture_roughness | slot | lost | 반들반들해요 | 아니오 |
| v0 | H05 | weight | no_slot | lost | 묵직할 것 같아요 | 아니오 |
| v0 | H05 | size | slot | lost | 주먹만 하고 | 아니오 |
| v0 | H06 | posture | slot | distorted/wrong_value | 매달려 있는 | 아니오 |
| v0 | H06 | shape | no_slot | lost | 아주 가늘고 | 아니오 |
| v0 | H06 | size | slot | lost | 길이는 1미터쯤 | 아니오 |
| v0 | H07 | body_part | slot | distorted/wrong_value | 배 안쪽 | 아니오 |
| v0 | H07 | brightness | slot | distorted/wrong_value | 은은하게 빛나고 | 아니오 |
| v0 | H07 | size | slot | lost | 귤 하나 정도 | 아니오 |
| v0 | H07 | motion_type | slot | distorted/wrong_value | 맥박 뛰듯이 | 아니오 |
| v0 | H08 | shape | no_slot | lost | 모서리가 날카롭고 | 아니오 |
| v0 | H08 | size | slot | lost | 손톱만 해요 | 아니오 |
| v0 | H09 | motion_type | slot | distorted/cross_slot | 위로 피어올라요 | 아니오 |
| v0 | H09 | smell | negated | lost | 냄새는 안 나요 | 아니오 |
| v0 | H09 | size | slot | distorted/cross_slot | 제 허리쯤까지 | 아니오 |
| v0 | H10 | distance | slot | lost | 1미터 앞 | 아니오 |
| v0 | H10 | height | slot | lost | 바닥에 | 아니오 |
| v0 | H10 | shape | no_slot | lost | 네모반듯한 | 아니오 |
| v0 | H10 | size | slot | lost | 한 변이 30센티쯤 | 아니오 |
| v0 | H11 | other | no_slot | lost | 말랑말랑한 | 아니오 |
| v0 | H11 | size | slot | lost | 탁구공만 해요 | 아니오 |
| v0 | H12 | shape | no_slot | lost | 끝이 뾰족해요 | 아니오 |
| v0 | H12 | brightness | slot | lost | 반짝반짝해요 | 아니오 |
| v0 | H12 | height | slot | distorted/wrong_value | 눈높이보다 조금 아래 | 아니오 |
| v0 | H13 | body_part | slot | distorted/wrong_value | 목 안쪽 | 아니오 |
| v0 | H13 | motion_type | slot | lost | 아래로 내려가요 | 아니오 |
| v0 | H13 | size | slot | distorted/wrong_value | 콩알만 해요 | 아니오 |
| v0 | H14 | size | slot | lost | 농구공 정도요 | 아니오 |
| v0 | H15 | size | slot | distorted/wrong_value | 팔찌보다 조금 큰 | 아니오 |
| v0 | H15 | shape | no_slot | lost | 가운데가 뻥 뚫려 | 아니오 |
| v0 | H15 | distance | slot | distorted/cross_slot | 팔 뻗으면 닿을 거리 | 아니오 |
| v0 | H16 | body_part | slot | distorted/wrong_value | 등 쪽 | 아니오 |
| v0 | H16 | opacity | slot | lost | 반쯤 비쳐요 | 아니오 |
| v0 | H17 | other | no_slot | lost | 단단해 보여요 | 아니오 |
| v0 | H18 | size | slot | lost | 소파만 하고 | 아니오 |
| v0 | H18 | height | slot | distorted/wrong_value | 제 머리보다 약간 높은 | 아니오 |
| v0 | H19 | shape | no_slot | lost | 뾰족하게 솟아 | 아니오 |
| v0 | H19 | size | slot | distorted/wrong_value | 제 손보다 조금 커요 | 아니오 |
| v0 | H20 | height | slot | lost | 발밑이요 | 아니오 |
| v0 | H21 | distance | slot | lost | 눈앞에 | 아니오 |
| v0 | H21 | motion_speed | slot | lost | 천천이 | 아니오 |
| v0 | H22 | motion_type | slot | lost | 천천히 내려오고 | 아니오 |
| v0 | H22 | weight | no_slot | lost | 아주 가볍고 | 아니오 |
| v0 | H22 | other | no_slot | lost | 보송보송해요 | 아니오 |
| v0 | H22 | size | slot | distorted/wrong_value | 새끼손가락 길이쯤 | 아니오 |
| v0 | H22 | erosion | slot | lost | 가장자리가 살짝 흐트러져 | 아니오 |
| v0 | H23 | height | slot | lost | 발밑에 | 아니오 |
| v0 | H23 | size | slot | distorted/wrong_value | 아주 작고 | 아니오 |
| v0 | H23 | texture_roughness | slot | lost | 까슬까슬할 | 아니오 |
| v0 | H23 | temperature | negated | lost | 따뜻하진 않고 | 아니오 |
| v0 | H24 | color | slot | distorted/wrong_value | 아주 살짝 푸른 기 | 아니오 |
| v0 | H24 | size | slot | distorted/cross_slot | 손 전체를 덮을 정도 | 아니오 |
| v0 | H25 | size | slot | distorted/wrong_value | 사람 키만 하고 | 아니오 |
| v0 | H25 | distance | slot | lost | 2미터쯤 | 아니오 |
| v0 | H25 | weight | negated | lost | 무겁진 않고 | 아니오 |
| v0 | H25 | texture_roughness | slot | lost | 약간 오돌토돌해요 | 아니오 |
| v0 | H26 | color | slot | distorted/cross_slot | 밝은 연두 | 아니오 |
| v0 | H26 | texture_roughness | slot | lost | 보풀보풀해요 | 아니오 |
| v0 | H26 | size | slot | distorted/wrong_value | 야구공보다 조금 커요 | 아니오 |
| v0 | H27 | color | slot | lost | 검붉은 | 아니오 |
| v0 | H27 | erosion | slot | distorted/wrong_value | 조금씩 부서져 | 아니오 |
| v0 | H28 | sound | negated | lost | 소리는 전혀 없고 | 아니오 |
| v0 | H28 | brightness | slot | distorted/wrong_value | 밝기는 중간쯤 | 아니오 |
| v0 | H28 | opacity | slot | distorted/cross_slot | 흐릿한 | 아니오 |
| v0 | H29 | height | slot | lost | 무릎 높이쯤 | 아니오 |
| v0 | H29 | texture_roughness | slot | lost | 거칠거칠해요 | 아니오 |
| v0 | H29 | size | slot | lost | 수박만 한 | 아니오 |
| v0 | H29 | distance | slot | lost | 한 발짝 거리 | 아니오 |
| v0 | H30 | opacity | slot | lost | 속이 비쳐요 | 아니오 |
| v0 | H30 | height | slot | distorted/wrong_value | 가슴 높이쯤 | 아니오 |
| v0 | H30 | distance | slot | lost | 바로 앞이에요 | 아니오 |
| v1 | H02 | size | slot | distorted/wrong_value | 방 하나를 채울 만큼 커요 | 예 |
| v1 | H09 | size | slot | distorted/cross_slot | 제 허리쯤까지 | 예 |
| v1 | H15 | size | slot | distorted/wrong_value | 팔찌보다 조금 큰 | 예 |
| v1 | H22 | motion_type | slot | lost | 천천히 내려오고 | 예 |
| v1 | H24 | color | slot | distorted/wrong_value | 아주 살짝 푸른 기 | 예 |
| v1 | H24 | size | slot | lost | 손 전체를 덮을 정도 | 예 |
| v1 | H27 | height | slot | distorted/cross_slot | 어깨 옆 | 예 |
| v1 | H27 | erosion | slot | distorted/wrong_value | 조금씩 부서져 | 예 |
| v1 | H28 | opacity | slot | lost | 흐릿한 | 예 |

보존·손실의 상세(preserved 포함)와 배경 오염은 score/report.md·score/compare/report.md의 「실패 사례」에 있다.
