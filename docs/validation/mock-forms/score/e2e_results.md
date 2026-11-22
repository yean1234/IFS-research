# 전 과정 실행 검증(E2E) 결과

> 입력은 전부 **합성 대사**다(AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스). 참여자 데이터가 아니다. 수치는 이 합성 코퍼스에서의 공학 회귀 지표이며 심상 구현의 타당도 증거가 아니다(docs/acceptance.md 머리말).

- 코퍼스: imagery-mock-forms@0.1.0 · docs/validation/mock-forms/mock_corpus.json · sha256 94df62030f6c6a9883cd7efec13ed7d05876cb5600e9fcafd49e685ec5f2c5a3
- 형식 검사(--check-corpus): 오류 0 · 경고 0
- 입력 수: 36 · 매핑: v0, v1 · 조건: 정적(조건 1), LLM 없음
- LLM·네트워크 차단(AC-3.9): 켬 — 8개 함수(socket.connect, httpx.get, httpx.post, Client.send, urllib.request.urlopen, OllamaBackend.generate, OllamaBackend._post, OfflineTemplateBackend.generate)를 호출 즉시 예외로 바꾼 상태에서 재생·매핑, 시도된 호출 0건
- 도구: e2e/0.2.0 · 채점기 fidelity/0.3.0 · 빌더 v0 = scene-spec-builder/0.1.0, v1 = scene-spec-builder-v1/1.2.0 · drift drift/1.1.0

## 스키마·파일

| 매핑 | spec 파일 | 스키마 | 스키마 유효 | 원칙 검사 문제 | 파일 = 재생 spec | 매핑 대체(폴백) |
| --- | --- | --- | --- | --- | --- | --- |
| v0 | 36 | scene-spec.v2.json | 36/36 | 0 | 36/36 | 0 |
| v1 | 36 | scene-spec.v2.1.json | 36/36 | 0 | 36/36 | 0 |

## 채점 요약(속성 단위, phrase_missing 제외)

| 지표 | v0 | v1 | 차이(v1 − v0) | 차이 95% CI |
| --- | --- | --- | --- | --- |
| reflectRate | 0.580 | 0.765 | 0.185 | [0.141, 0.230] |
| distortRate | 0.125 | 0.060 | -0.065 | [-0.105, -0.025] |
| lostRate | 0.205 | 0.010 | -0.195 | [-0.242, -0.149] |
| droppedRate | 0.070 | 0.070 | 0.000 | [0.000, 0.000] |
| preserveRate | 0.527 | 0.872 | 0.345 | [0.289, 0.401] |
| unreflectedVerbatimRate | 0.127 | 0.767 | 0.640 | [0.542, 0.737] |
| unreflectedVerbatimRateWithClauseIndex | 0.127 | 1.000 | 0.873 | [0.826, 0.920] |
| spuriousRate | 0.286 | 0.135 | -0.151 | [-0.186, -0.118] |
| unsupportedRate | 0.460 | 0.255 | -0.204 | [-0.257, -0.157] |
| fuzzyValueRate | 0.000 | 0.000 | 0.000 | [0.000, 0.000] |

| 매핑 | 속성 | 슬롯 속성 | 슬롯 상태 | 미반영 | 절 색인으로만 남은 손실 | 퍼지 경로 값 | 근거 없는 값(근거/경로/값 있는 슬롯) | 근거 없는 값 사유 | 매핑 대체 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v0 | 258 | 200 | reflected 116, distorted 25, preserved 4, lost 41, dropped_by_controller 14 | 126 | 0 | 0 | 85/53/185 | no_evidence 0, no_gold_span 59, outside_gold_span 26 | 0 |
| v1 | 258 | 200 | reflected 153, distorted 12, preserved 19, lost 2, dropped_by_controller 14 | 86 | 6 | 0 | 49/26/192 | no_evidence 0, no_gold_span 31, outside_gold_span 18 | 0 |

## 매핑별 신뢰구간(항목 단위 군집 부트스트랩 95%)

| 지표 | v0 | v1 |
| --- | --- | --- |
| reflectRate | 0.580 [0.519, 0.640] | 0.765 [0.714, 0.814] |
| distortRate | 0.125 [0.085, 0.167] | 0.060 [0.031, 0.092] |
| lostRate | 0.205 [0.160, 0.251] | 0.010 [0.000, 0.025] |
| droppedRate | 0.070 [0.030, 0.117] | 0.070 [0.030, 0.117] |
| preserveRate | 0.527 [0.463, 0.591] | 0.872 [0.818, 0.920] |
| unreflectedVerbatimRate | 0.127 [0.080, 0.174] | 0.767 [0.663, 0.863] |
| unreflectedVerbatimRateWithClauseIndex | 0.127 [0.080, 0.174] | 1.000 [1.000, 1.000] |
| spuriousRate | 0.286 [0.250, 0.327] | 0.135 [0.088, 0.182] |
| unsupportedRate | 0.460 [0.416, 0.506] | 0.255 [0.199, 0.310] |
| fuzzyValueRate | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |

## drift(세션 로그, 참고 수치 — AC-2 집계 아님)

| 매핑 | drift | no_drift | undecidable | 오류 |
| --- | --- | --- | --- | --- |
| v0 | 10 | 10 | 16 | 0 |
| v1 | 10 | 10 | 16 | 0 |

## 실패·오류 목록

### v0

| 항목 | 유형 | 속성/경로 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| M01 | lost | size | 방을 채울 만큼 | {"range": [0.75, 1.0]} | – | [] |
| M01 | lost | opacity | 뒤가 비쳐 보이긴 하는데 흐릿해요 | {"range": [0.2, 0.75]} | – | [] |
| M01 | dropped_by_controller | motion_type | 이리저리 떠다녀요 | {"in": ["floating", "drifting"]} | – | – |
| M01 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| M01 | spurious | material.brightness |  | – | 0.400 | ["뿌옇게"] |
| M01 | spurious | layout.verticalOffset |  | – | 0.930 | ["머리", "머리"] |
| M01 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| M02 | lost | opacity | 아주 진하진 않고 좀 비쳐요 | {"range": [0.3, 0.85]} | – | [] |
| M02 | spurious | layout.verticalOffset |  | – | 0.720 | ["가슴"] |
| M02 | unsupported/outside_gold_span | motion.type |  | – | rising | ["올라와요"] |
| M02 | unsupported/outside_gold_span | body.layer |  | – | inner | ["안쪽"] |
| M03 | lost | form | 구름이에요 | {"in": ["mist"]} | – | [] |
| M03 | lost | other | 커졌다 작아졌다 해요 | – | – | – |
| M03 | lost | body_layer | 주변이요 | {"in": ["around", "around_front", "around_behind", "around_side", "around_below"]} | – | [] |
| M03 | spurious | layout.verticalOffset |  | – | 0.930 | ["머리"] |
| M03 | spurious | body.part |  | – | head | ["머리"] |
| M04 | lost | form | 김 같은 게 | {"equals": "mist"} | – | [] |
| M04 | lost | size | 손바닥 두 개 정도요 | {"range": [0.25, 0.6]} | – | [] |
| M04 | spurious | layout.verticalOffset |  | – | 0.850 | ["목", "목"] |
| M04 | unsupported/outside_gold_span | motion.type |  | – | rising | ["올라와요"] |
| M05 | lost | size | 주먹만 해요 | {"range": [0.05, 0.5]} | – | [] |
| M05 | spurious | layout.verticalOffset |  | – | 0.600 | ["배"] |
| M05 | unsupported/outside_gold_span | body.part |  | – | belly | ["배"] |
| M06 | lost | lines | 실이 마구 엉켜서 | – | – | – |
| M06 | lost | size | 테니스공 정도요 | {"range": [0.1, 0.5]} | – | [] |
| M06 | distorted/wrong_value | body_part | 머리 안쪽 | {"equals": "head"} | body | ["몸"] |
| M06 | spurious | layout.verticalOffset |  | – | 0.930 | ["머리"] |
| M06 | unsupported/outside_gold_span | form.type |  | – | blob | ["뭉치"] |
| M06 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| M07 | lost | softness | 찰흙처럼 말랑말랑하고 | – | – | – |
| M07 | lost | motion_type | 부풀었다 줄었다 해요 | – | – | – |
| M07 | dropped_by_controller | size | 귤 하나 정도요 | {"range": [0.05, 0.45]} | – | – |
| M07 | spurious | layout.verticalOffset |  | – | 0.600 | ["배"] |
| M07 | unsupported/outside_gold_span | form.type |  | – | blob | ["뭉치"] |
| M07 | unsupported/outside_gold_span | body.part |  | – | belly | ["배"] |
| M08 | distorted/cross_slot | size | 가슴을 다 덮을 만큼 | {"range": [0.35, 0.8]} | – | [{"path": "layout.verticalOffset", "trigger": "가슴", "value": 0.72}] |
| M08 | distorted/wrong_value | body_layer | 몸 표면이요 | {"equals": "surface"} | around_front | ["앞", "앞"] |
| M08 | spurious | layout.verticalOffset |  | – | 0.720 | ["가슴", "가슴", "가슴", "가슴"] |
| M08 | unsupported/outside_gold_span | body.layer |  | – | around_front | ["앞", "앞"] |
| M09 | distorted/wrong_value | opacity | 반쯤 투명해서 | {"range": [0.25, 0.7]} | 0.100 | ["투명"] |
| M09 | distorted/wrong_value | size | 저를 통째로 감쌀 만큼 커요 | {"range": [0.75, 1.0]} | 0.621 | ["커요"] |
| M09 | dropped_by_controller | motion_type | 일렁여요 | {"in": ["rippling", "swaying"]} | – | – |
| M09 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M09 | spurious | body.part |  | – | body | ["몸", "몸"] |
| M09 | unsupported/outside_gold_span | form.type |  | – | shell | ["비눗방울 막처럼"] |
| M09 | unsupported/no_gold_span | motion.type |  | – | rotating | ["돌아요"] |
| M10 | lost | erosion | 군데군데 금이 가 있어요 | {"range": [0.15, 0.7]} | – | [] |
| M10 | lost | opacity | 금 간 데로만 빛이 비쳐요 | – | – | – |
| M10 | lost | hollow | 안은 비어 있고요 | – | – | – |
| M10 | distorted/wrong_value | size | 달걀보다 조금 커요 | {"range": [0.05, 0.45]} | 0.621 | ["커요"] |
| M10 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M10 | spurious | body.part |  | – | body | ["몸"] |
| M11 | lost | size | 엄지손톱만 하고 | {"range": [0.0, 0.35]} | – | [] |
| M11 | lost | shape | 모서리가 날카로워요 | – | – | – |
| M11 | dropped_by_controller | motion_type | 맴돌아요 | {"in": ["circling", "rotating", "drifting"]} | – | – |
| M11 | dropped_by_controller | motion_speed | 느릿느릿 | {"range": [0.0, 0.4]} | – | – |
| M11 | lost | body_layer | 몸 안이요 | {"equals": "inner"} | – | [] |
| M11 | spurious | material.erosion |  | – | 0.850 | ["부서진"] |
| M11 | spurious | layout.verticalOffset |  | – | 0.720 | ["가슴"] |
| M11 | unsupported/no_gold_span | motion.type |  | – | scattering | ["흩어져", "흩어져"] |
| M12 | distorted/cross_slot | distance | 팔 뻗으면 닿을 거리쯤에 | {"range": [0.05, 0.3]} | – | [{"path": "layout.verticalOffset", "trigger": "팔", "value": 0.63}] |
| M12 | lost | size | 다 모으면 베개만 해요 | {"range": [0.4, 0.75]} | – | [] |
| M12 | dropped_by_controller | motion_type | 거의 안 움직이고 떠 있기만 해요 | {"in": ["still", "floating"]} | – | – |
| M12 | spurious | material.erosion |  | – | 0.600 | ["깨진"] |
| M12 | spurious | layout.verticalOffset |  | – | 0.630 | ["팔"] |
| M12 | spurious | body.part |  | – | body | ["몸"] |
| M12 | unsupported/outside_gold_span | material.brightness |  | – | 0.850 | ["반짝이는"] |
| M12 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠", "떠"] |
| M13 | lost | form | 부스러기 같은 게 | {"equals": "fragments"} | – | [] |
| M13 | distorted/cross_slot | motion_type | 아래로 떨어져요 | {"in": ["sinking", "settling", "scattering", "collapsing"]} | – | [{"path": "layout.distance", "trigger": "떨어져요", "value": 0.6}] |
| M13 | lost | size | 깨알만 해요 | {"range": [0.0, 0.2]} | – | [] |
| M13 | spurious | layout.distance |  | – | 0.600 | ["떨어져요"] |
| M13 | spurious | layout.verticalOffset |  | – | 0.820 | ["어깨", "어깨", "어깨"] |
| M14 | lost | shape | 완전히 둥근 공 모양 | – | – | – |
| M14 | distorted/wrong_value | brightness | 은은하게 빛나요 | {"range": [0.5, 0.85]} | 0.900 | ["빛나요"] |
| M14 | lost | size | 배구공만 해요 | {"range": [0.4, 0.75]} | – | [] |
| M14 | lost | distance | 한두 걸음 앞에 | {"range": [0.2, 0.55]} | – | [] |
| M14 | distorted/cross_slot | motion_type | 제자리에서 천천히 굴러요 | {"in": ["rotating"]} | – | [{"path": "motion.speed", "trigger": "천천히", "value": 0.25}] |
| M14 | spurious | layout.verticalOffset |  | – | 0.600 | ["배"] |
| M14 | spurious | motion.speed |  | – | 0.250 | ["천천히"] |
| M14 | spurious | body.part |  | – | belly | ["배"] |
| M15 | lost | hardness | 모서리가 각지고 딱딱해요 | – | – | – |
| M15 | lost | size | 신발 상자만 해요 | {"range": [0.25, 0.65]} | – | [] |
| M15 | spurious | layout.distance |  | – | 0.000 | ["붙어"] |
| M15 | spurious | layout.verticalOffset |  | – | 0.720 | ["등", "등"] |
| M16 | lost | size | 9 cm쯤 | {"range": [0.03, 0.4]} | – | [] |
| M16 | lost | motion_type | 그대로 놓여 있어요 | {"in": ["still"]} | – | [] |
| M16 | lost | body_layer | 몸 안이요 | {"equals": "inner"} | – | [] |
| M16 | spurious | form.type |  | – | blob | ["돌처럼"] |
| M16 | spurious | layout.verticalOffset |  | – | 0.670 | ["명치"] |
| M17 | lost | shape | 끝이 뾰족해요 | – | – | – |
| M17 | lost | size | 새끼손가락 반만 해요 | {"range": [0.0, 0.3]} | – | [] |
| M17 | spurious | layout.verticalOffset |  | – | 0.850 | ["목", "목구멍"] |
| M17 | unsupported/outside_gold_span | body.part |  | – | throat_neck | ["목"] |
| M18 | lost | width | 머리카락만큼 가늘어요 | – | – | – |
| M18 | lost | motion_type | 조금씩 조여 와요 | – | – | – |
| M18 | spurious | layout.verticalOffset |  | – | 0.490 | ["손끝", "손"] |
| M18 | unsupported/outside_gold_span | body.part |  | – | hand | ["손끝", "손"] |
| M19 | lost | lines | 가느다란 선 하나 | – | – | – |
| M19 | distorted/wrong_value | brightness | 희미하게 빛나요 | {"range": [0.4, 0.75]} | 0.250 | ["희미하게"] |
| M19 | lost | size | 길이는 40센티쯤이요 | {"range": [0.3, 0.75]} | – | [] |
| M19 | lost | motion_type | 아래로 천천히 흘러내려요 | – | – | – |
| M19 | lost | body_layer | 몸 안이요 | {"equals": "inner"} | – | [] |
| M19 | spurious | layout.verticalOffset |  | – | 0.720 | ["등"] |
| M19 | unsupported/outside_gold_span | body.part |  | – | back | ["등"] |
| M20 | lost | sheet | 종이 한 장 | – | – | – |
| M20 | lost | size | A4 종이 한 장 | {"range": [0.25, 0.65]} | – | [] |
| M20 | lost | height | 눈높이쯤에 | {"range": [0.85, 1.0]} | – | [] |
| M20 | lost | wrinkle | 가장자리가 살짝 구겨져 있어요 | – | – | – |
| M20 | dropped_by_controller | motion_type | 팔랑거려요 | {"in": ["swaying", "rippling", "floating"]} | – | – |
| M20 | lost | body_layer | 주변이요 | {"in": ["around", "around_front", "around_behind", "around_side", "around_below"]} | – | [] |
| M20 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠"] |
| M21 | lost | color2 | 남색이 섞여 | – | – | – |
| M21 | distorted/wrong_value | opacity | 반투명해요 | {"range": [0.2, 0.7]} | 0.100 | ["투명"] |
| M21 | lost | softness | 부드러울 것 같아요 | – | – | – |
| M21 | lost | motion_type | 아래로 흘러내려요 | – | – | – |
| M21 | lost | size | 상체를 다 덮을 정도요 | {"range": [0.5, 0.85]} | – | [] |
| M21 | spurious | layout.verticalOffset |  | – | 0.820 | ["어깨", "어깨", "어깨"] |
| M22 | lost | liquid | 물방울 하나가 맺혀 | – | – | – |
| M22 | lost | opacity | 가운데는 맑게 비치는데 가장자리만 뿌예요 | – | – | – |
| M22 | lost | size | 콩알만 해요 | {"range": [0.0, 0.2]} | – | [] |
| M22 | dropped_by_controller | color | 색은 딱히 없어요 | {"equals": null} | – | – |
| M22 | lost | motion_type | 떨어질 듯 말 듯 매달려 있어요 | – | – | – |
| M22 | distorted/wrong_value | body_part | 눈 뒤쪽 | {"in": ["head", "face"]} | body | ["몸"] |
| M22 | distorted/cross_slot | body_layer | 몸 안이요 | {"equals": "inner"} | – | [{"path": "body.part", "trigger": "몸", "value": "body"}] |
| M22 | spurious | form.posture |  | – | hanging | ["매달려"] |
| M22 | spurious | material.brightness |  | – | 0.400 | ["뿌예요"] |
| M22 | spurious | layout.distance |  | – | 0.600 | ["떨어질"] |
| M22 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| M23 | lost | opacity | 바닥이 안 보여요 | {"range": [0.7, 1.0]} | – | [] |
| M23 | distorted/cross_slot | size | 서 있는 자리보다 조금 넓어요 | {"range": [0.35, 0.8]} | – | [{"path": "form.posture", "trigger": "서", "value": "standing"}] |
| M23 | spurious | form.posture |  | – | standing | ["서"] |
| M23 | spurious | material.saturation |  | – | 0.250 | ["탁한"] |
| M23 | spurious | body.part |  | – | foot | ["발", "발"] |
| M24 | lost | liquid | 진득한 노란 액체 | – | – | – |
| M24 | lost | motion_type | 천천히 흘러내리는데 | – | – | – |
| M24 | distorted/cross_slot | texture_roughness | 빛을 받으면 반짝여요 | {"range": [0.0, 0.35]} | – | [{"path": "material.brightness", "trigger": "빛", "value": 0.7}] |
| M24 | lost | size | 양은 한 컵쯤이요 | {"range": [0.05, 0.45]} | – | [] |
| M24 | lost | stickiness | 끈적끈적해요 | – | – | – |
| M24 | lost | body_layer | 몸 안이요 | {"equals": "inner"} | – | [] |
| M24 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M24 | spurious | layout.verticalOffset |  | – | 0.850 | ["목"] |
| M25 | lost | motion_type | 콩닥콩닥 뛰듯이 | {"in": ["pounding"]} | – | [] |
| M25 | distorted/wrong_value | size | 구슬만 해요 | {"range": [0.0, 0.25]} | 0.316 | ["작은"] |
| M25 | spurious | layout.verticalOffset |  | – | 0.720 | ["가슴", "가슴"] |
| M25 | unsupported/outside_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| M26 | lost | light | 불꽃 같은 게 | – | – | – |
| M26 | distorted/wrong_value | color | 주황색이에요 | {"hue_deg": [15, 45], "s": [0.5, 1.0], "l": [0.35, 0.7]} | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파랗고"] |
| M26 | lost | color2 | 아래는 파랗고 | – | – | – |
| M26 | lost | size | 손가락 한 마디만 해요 | {"range": [0.0, 0.25]} | – | [] |
| M26 | spurious | layout.verticalOffset |  | – | 0.600 | ["배", "배"] |
| M26 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파랗고"] |
| M26 | unsupported/outside_gold_span | body.layer |  | – | inner | ["안쪽"] |
| M27 | lost | light | 노란빛이 떠 있어요 | – | – | – |
| M27 | lost | size | 냄비 뚜껑만 하고 | {"range": [0.3, 0.65]} | – | [] |
| M27 | distorted/wrong_value | motion_type | 원을 그리며 돌아요 | {"in": ["circling", "rotating"]} | floating | ["떠", "떠"] |
| M27 | lost | motion_speed | 느긋하게 | {"range": [0.0, 0.4]} | – | [] |
| M27 | lost | opacity | 가장자리는 흐려서 뒤가 살짝 비쳐요 | – | – | – |
| M27 | distorted/wrong_value | body_layer | 몸 주변이요 | {"in": ["around", "around_front", "around_behind", "around_side", "around_below"]} | surface_above | ["위"] |
| M27 | spurious | body.part |  | – | head | ["머리"] |
| M27 | unsupported/outside_gold_span | motion.type |  | – | floating | ["떠", "떠"] |
| M27 | unsupported/outside_gold_span | body.layer |  | – | surface_above | ["위"] |
| M28 | lost | size | 도넛 하나 크기요 | {"range": [0.05, 0.45]} | – | [] |
| M28 | lost | motion_type | 그대로예요 | {"in": ["still"]} | – | [] |
| M28 | spurious | layout.verticalOffset |  | – | 0.720 | ["가슴", "가슴"] |
| M28 | unsupported/outside_gold_span | body.layer |  | – | inner | ["안"] |
| M29 | lost | hole | 텅 빈 공간이에요 | – | – | – |
| M29 | distorted/cross_slot | size | 배 전체만큼 넓어요 | {"range": [0.4, 0.8]} | – | [{"path": "layout.verticalOffset", "trigger": "배", "value": 0.6}] |
| M29 | lost | motion_type | 넓어졌다 좁아졌다 해요 | – | – | – |
| M29 | spurious | layout.verticalOffset |  | – | 0.600 | ["배", "배", "배"] |
| M29 | unsupported/outside_gold_span | body.layer |  | – | inner | ["속", "속"] |
| M30 | lost | figure | 작은 사람 모양 | – | – | – |
| M30 | distorted/cross_slot | motion_type | 살짝 몸을 흔들어요 | {"in": ["swaying"]} | – | [{"path": "body.part", "trigger": "몸", "value": "body"}] |
| M30 | spurious | layout.verticalOffset |  | – | 0.920 | ["얼굴"] |
| M30 | spurious | body.part |  | – | body | ["몸", "몸"] |
| M30 | unsupported/outside_gold_span | form.posture |  | – | crouched | ["쪼그려"] |
| M31 | lost | figure | 까만 고양이 한 마리 | – | – | – |
| M31 | distorted/wrong_value | posture | 동그랗게 말려 있어요 | {"in": ["curled"]} | lying | ["누웠을"] |
| M31 | lost | softness | 털이 보송보송해요 | – | – | – |
| M31 | lost | motion_type | 등이 오르락내리락해요 | – | – | – |
| M31 | lost | size | 보통 고양이만 해요 | {"range": [0.3, 0.6]} | – | [] |
| M31 | spurious | layout.verticalOffset |  | – | 0.280 | ["다리", "다리", "다리"] |
| M31 | unsupported/outside_gold_span | form.posture |  | – | lying | ["누웠을"] |
| M32 | distorted/wrong_value | size | 참새만 한 | {"range": [0.0, 0.3]} | 0.316 | ["작은"] |
| M32 | lost | color2 | 날개 끝은 노래요 | – | – | – |
| M32 | lost | motion_type | 날개를 파닥파닥해요 | – | – | – |
| M32 | spurious | form.posture |  | – | sitting | ["앉아"] |
| M32 | spurious | layout.verticalOffset |  | – | 0.820 | ["어깨", "어깨"] |
| M32 | unsupported/outside_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| M33 | dropped_by_controller | size | 그것도 모르겠어요 | {"equals": null} | – | – |
| M33 | dropped_by_controller | color | 색도 모르겠어요 | {"equals": null} | – | – |
| M33 | dropped_by_controller | motion_type | 움직임도 잘 모르겠어요 | {"equals": null} | – | – |
| M33 | dropped_by_controller | feeling | 멍해요 | – | – | – |
| M34 | lost | feeling | 꽉 막힌 느낌이에요 | – | – | – |
| M34 | dropped_by_controller | motion_type | 모르겠어요 | {"equals": null} | – | – |
| M34 | spurious | layout.verticalOffset |  | – | 0.720 | ["가슴"] |
| M35 | lost | feeling | 무겁게 가라앉는 느낌만 | – | – | – |
| M35 | lost | size | 몸 전체만큼이요 | {"range": [0.6, 1.0]} | – | [] |
| M35 | dropped_by_controller | motion_type | 아래로 가라앉아요 | {"in": ["sinking", "settling"]} | – | – |
| M35 | spurious | form.posture |  | – | drooping | ["처져요"] |
| M35 | unsupported/no_gold_span | motion.type |  | – | sinking | ["가라앉는"] |
| M36 | lost | feeling | 안절부절못하는 느낌 | – | – | – |
| M36 | lost | motion_type | 계속 들썩들썩해요 | {"in": ["vibrating", "trembling", "moving"]} | – | [] |
| M36 | distorted/wrong_value | body_part | 배 쪽이요 | {"in": ["belly"]} | body | ["몸"] |
| M36 | spurious | layout.verticalOffset |  | – | 0.600 | ["배"] |
| M36 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |

### v1

| 항목 | 유형 | 속성/경로 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| M01 | distorted/wrong_value | size | 방을 채울 만큼 | {"range": [0.75, 1.0]} | 0.621 | ["넓게"] |
| M01 | dropped_by_controller | motion_type | 이리저리 떠다녀요 | {"in": ["floating", "drifting"]} | – | – |
| M01 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| M01 | spurious | material.brightness |  | – | 0.400 | ["뿌옇게"] |
| M01 | unsupported/outside_gold_span | layout.size |  | – | 0.621 | ["넓게"] |
| M01 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| M04 | distorted/wrong_value | size | 손바닥 두 개 정도요 | {"range": [0.25, 0.6]} | 0.641 | ["손바닥 두 개 정도요"] |
| M05 | unsupported/outside_gold_span | body.part |  | – | belly | ["배"] |
| M06 | unsupported/outside_gold_span | form.type |  | – | blob | ["뭉치"] |
| M07 | dropped_by_controller | size | 귤 하나 정도요 | {"range": [0.05, 0.45]} | – | – |
| M07 | unsupported/outside_gold_span | form.type |  | – | blob | ["뭉치"] |
| M07 | unsupported/outside_gold_span | body.part |  | – | belly | ["배"] |
| M08 | distorted/wrong_value | size | 가슴을 다 덮을 만큼 | {"range": [0.35, 0.8]} | 1.000 | ["앞을 덮"] |
| M08 | unsupported/outside_gold_span | layout.size |  | – | 1.000 | ["앞을 덮"] |
| M09 | distorted/wrong_value | opacity | 반쯤 투명해서 | {"range": [0.25, 0.7]} | 0.100 | ["투명"] |
| M09 | distorted/wrong_value | size | 저를 통째로 감쌀 만큼 커요 | {"range": [0.75, 1.0]} | 0.621 | ["커요"] |
| M09 | dropped_by_controller | motion_type | 일렁여요 | {"in": ["rippling", "swaying"]} | – | – |
| M09 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M09 | spurious | body.part |  | – | body | ["몸", "몸"] |
| M09 | unsupported/outside_gold_span | form.type |  | – | shell | ["비눗방울 막처럼"] |
| M10 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M10 | spurious | body.part |  | – | body | ["몸"] |
| M11 | dropped_by_controller | motion_type | 맴돌아요 | {"in": ["circling", "rotating", "drifting"]} | – | – |
| M11 | dropped_by_controller | motion_speed | 느릿느릿 | {"range": [0.0, 0.4]} | – | – |
| M11 | spurious | material.erosion |  | – | 0.850 | ["부서진"] |
| M11 | unsupported/no_gold_span | motion.type |  | – | scattering | ["흩어져", "흩어져"] |
| M12 | distorted/cross_slot | distance | 팔 뻗으면 닿을 거리쯤에 | {"range": [0.05, 0.3]} | – | [{"path": "body.part", "trigger": "팔", "value": "arm"}] |
| M12 | dropped_by_controller | motion_type | 거의 안 움직이고 떠 있기만 해요 | {"in": ["still", "floating"]} | – | – |
| M12 | spurious | material.erosion |  | – | 0.600 | ["깨진"] |
| M12 | spurious | body.part |  | – | arm | ["팔"] |
| M12 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠", "떠"] |
| M13 | distorted/cross_slot | motion_type | 아래로 떨어져요 | {"in": ["sinking", "settling", "scattering", "collapsing"]} | – | [{"path": "layout.distance", "trigger": "떨어져요", "value": 0.6}] |
| M13 | spurious | layout.distance |  | – | 0.600 | ["떨어져요"] |
| M13 | unsupported/outside_gold_span | form.type |  | – | fragments | ["부스러기", "알갱이"] |
| M14 | spurious | form.type |  | – | blob | ["공"] |
| M14 | spurious | motion.speed |  | – | 0.250 | ["천천히"] |
| M14 | spurious | body.part |  | – | belly | ["배"] |
| M15 | spurious | layout.distance |  | – | 0.000 | ["붙어"] |
| M16 | spurious | form.type |  | – | blob | ["돌처럼"] |
| M17 | unsupported/outside_gold_span | body.part |  | – | throat_neck | ["목"] |
| M19 | distorted/wrong_value | brightness | 희미하게 빛나요 | {"range": [0.4, 0.75]} | 0.250 | ["희미하게"] |
| M19 | lost | motion_type | 아래로 천천히 흘러내려요 | – | – | – |
| M19 | unsupported/outside_gold_span | body.part |  | – | back | ["등"] |
| M20 | dropped_by_controller | motion_type | 팔랑거려요 | {"in": ["swaying", "rippling", "floating"]} | – | – |
| M20 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠"] |
| M22 | dropped_by_controller | color | 색은 딱히 없어요 | {"equals": null} | – | – |
| M22 | lost | motion_type | 떨어질 듯 말 듯 매달려 있어요 | – | – | – |
| M22 | distorted/wrong_value | body_part | 눈 뒤쪽 | {"in": ["head", "face"]} | body | ["몸"] |
| M22 | spurious | form.posture |  | – | hanging | ["매달려"] |
| M22 | spurious | layout.distance |  | – | 0.600 | ["떨어질"] |
| M22 | unsupported/outside_gold_span | layout.size |  | – | 0.000 | ["1센티쯤"] |
| M22 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| M23 | spurious | form.posture |  | – | standing | ["서"] |
| M23 | spurious | material.saturation |  | – | 0.250 | ["탁한"] |
| M23 | spurious | body.part |  | – | foot | ["발", "발"] |
| M24 | lost | motion_type | 천천히 흘러내리는데 | – | – | – |
| M24 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M24 | unsupported/outside_gold_span | material.roughness |  | – | 0.300 | ["끈적끈적해요"] |
| M24 | unsupported/outside_gold_span | motion.type |  | – | sinking | ["내려가요", "내려가고"] |
| M26 | distorted/wrong_value | color | 주황색이에요 | {"hue_deg": [15, 45], "s": [0.5, 1.0], "l": [0.35, 0.7]} | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파랗고"] |
| M26 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파랗고"] |
| M27 | lost | brightness | 눈이 부실 만큼 밝은 | {"range": [0.8, 1.0]} | – | [] |
| M27 | spurious | layout.distance |  | – | 0.000 | ["한 뼘쯤"] |
| M27 | spurious | body.part |  | – | head | ["머리"] |
| M29 | lost | motion_type | 넓어졌다 좁아졌다 해요 | – | – | – |
| M30 | spurious | layout.verticalOffset |  | – | 0.280 | ["무릎 높이"] |
| M30 | spurious | body.part |  | – | leg | ["무릎"] |
| M30 | unsupported/outside_gold_span | form.posture |  | – | crouched | ["쪼그려"] |
| M31 | distorted/wrong_value | posture | 동그랗게 말려 있어요 | {"in": ["curled"]} | lying | ["누웠을"] |
| M31 | unsupported/outside_gold_span | form.posture |  | – | lying | ["누웠을"] |
| M32 | distorted/wrong_value | size | 참새만 한 | {"range": [0.0, 0.3]} | 0.316 | ["작은"] |
| M32 | spurious | form.posture |  | – | sitting | ["앉아"] |
| M32 | unsupported/outside_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| M33 | dropped_by_controller | size | 그것도 모르겠어요 | {"equals": null} | – | – |
| M33 | dropped_by_controller | color | 색도 모르겠어요 | {"equals": null} | – | – |
| M33 | dropped_by_controller | motion_type | 움직임도 잘 모르겠어요 | {"equals": null} | – | – |
| M33 | dropped_by_controller | feeling | 멍해요 | – | – | – |
| M34 | dropped_by_controller | motion_type | 모르겠어요 | {"equals": null} | – | – |
| M35 | lost | size | 몸 전체만큼이요 | {"range": [0.6, 1.0]} | – | [] |
| M35 | dropped_by_controller | motion_type | 아래로 가라앉아요 | {"in": ["sinking", "settling"]} | – | – |
| M35 | spurious | form.posture |  | – | drooping | ["처져요"] |
| M35 | unsupported/no_gold_span | motion.type |  | – | sinking | ["가라앉는"] |

## 미반영 원문 보존 실패(AC-3.5 분자에서 빠진 속성)

반영·포착·컨트롤러 탈락이 아닌 속성 중 phrase가 속성 단위 보존 필드에 원문 그대로 없는 것. '절 색인만'은 _clauses로만 남은 것(판정에서 인정하지 않음).

| 매핑 | 항목 | 속성 | kind | 상태 | phrase | 절 색인만 |
| --- | --- | --- | --- | --- | --- | --- |
| v0 | M01 | size | slot | lost | 방을 채울 만큼 | 아니오 |
| v0 | M01 | opacity | slot | lost | 뒤가 비쳐 보이긴 하는데 흐릿해요 | 아니오 |
| v0 | M02 | opacity | slot | lost | 아주 진하진 않고 좀 비쳐요 | 아니오 |
| v0 | M03 | form | slot | lost | 구름이에요 | 아니오 |
| v0 | M03 | other | no_slot | lost | 커졌다 작아졌다 해요 | 아니오 |
| v0 | M03 | body_layer | slot | lost | 주변이요 | 아니오 |
| v0 | M04 | form | slot | lost | 김 같은 게 | 아니오 |
| v0 | M04 | size | slot | lost | 손바닥 두 개 정도요 | 아니오 |
| v0 | M05 | hardness | no_slot | preserved | 딱딱한 덩어리 | 아니오 |
| v0 | M05 | size | slot | lost | 주먹만 해요 | 아니오 |
| v0 | M06 | lines | no_slot | lost | 실이 마구 엉켜서 | 아니오 |
| v0 | M06 | size | slot | lost | 테니스공 정도요 | 아니오 |
| v0 | M06 | body_part | slot | distorted/wrong_value | 머리 안쪽 | 아니오 |
| v0 | M07 | softness | no_slot | lost | 찰흙처럼 말랑말랑하고 | 아니오 |
| v0 | M07 | motion_type | slot_unscored | lost | 부풀었다 줄었다 해요 | 아니오 |
| v0 | M08 | size | slot | distorted/cross_slot | 가슴을 다 덮을 만큼 | 아니오 |
| v0 | M08 | body_layer | slot | distorted/wrong_value | 몸 표면이요 | 아니오 |
| v0 | M09 | opacity | slot | distorted/wrong_value | 반쯤 투명해서 | 아니오 |
| v0 | M09 | size | slot | distorted/wrong_value | 저를 통째로 감쌀 만큼 커요 | 아니오 |
| v0 | M10 | erosion | slot | lost | 군데군데 금이 가 있어요 | 아니오 |
| v0 | M10 | opacity | slot_unscored | lost | 금 간 데로만 빛이 비쳐요 | 아니오 |
| v0 | M10 | hollow | no_slot | lost | 안은 비어 있고요 | 아니오 |
| v0 | M10 | size | slot | distorted/wrong_value | 달걀보다 조금 커요 | 아니오 |
| v0 | M11 | size | slot | lost | 엄지손톱만 하고 | 아니오 |
| v0 | M11 | shape | no_slot | lost | 모서리가 날카로워요 | 아니오 |
| v0 | M11 | body_layer | slot | lost | 몸 안이요 | 아니오 |
| v0 | M12 | distance | slot | distorted/cross_slot | 팔 뻗으면 닿을 거리쯤에 | 아니오 |
| v0 | M12 | size | slot | lost | 다 모으면 베개만 해요 | 아니오 |
| v0 | M13 | form | slot | lost | 부스러기 같은 게 | 아니오 |
| v0 | M13 | motion_type | slot | distorted/cross_slot | 아래로 떨어져요 | 아니오 |
| v0 | M13 | size | slot | lost | 깨알만 해요 | 아니오 |
| v0 | M14 | shape | no_slot | lost | 완전히 둥근 공 모양 | 아니오 |
| v0 | M14 | brightness | slot | distorted/wrong_value | 은은하게 빛나요 | 아니오 |
| v0 | M14 | size | slot | lost | 배구공만 해요 | 아니오 |
| v0 | M14 | distance | slot | lost | 한두 걸음 앞에 | 아니오 |
| v0 | M14 | motion_type | slot | distorted/cross_slot | 제자리에서 천천히 굴러요 | 아니오 |
| v0 | M15 | hardness | no_slot | lost | 모서리가 각지고 딱딱해요 | 아니오 |
| v0 | M15 | size | slot | lost | 신발 상자만 해요 | 아니오 |
| v0 | M16 | shape | no_slot | preserved | 납작한 돌처럼 | 아니오 |
| v0 | M16 | size | slot | lost | 9 cm쯤 | 아니오 |
| v0 | M16 | motion_type | slot | lost | 그대로 놓여 있어요 | 아니오 |
| v0 | M16 | body_layer | slot | lost | 몸 안이요 | 아니오 |
| v0 | M17 | shape | no_slot | lost | 끝이 뾰족해요 | 아니오 |
| v0 | M17 | size | slot | lost | 새끼손가락 반만 해요 | 아니오 |
| v0 | M18 | lines | no_slot | preserved | 가느다란 검은 실 | 아니오 |
| v0 | M18 | width | no_slot | lost | 머리카락만큼 가늘어요 | 아니오 |
| v0 | M18 | motion_type | slot_unscored | lost | 조금씩 조여 와요 | 아니오 |
| v0 | M19 | lines | no_slot | lost | 가느다란 선 하나 | 아니오 |
| v0 | M19 | brightness | slot | distorted/wrong_value | 희미하게 빛나요 | 아니오 |
| v0 | M19 | size | slot | lost | 길이는 40센티쯤이요 | 아니오 |
| v0 | M19 | motion_type | slot_unscored | lost | 아래로 천천히 흘러내려요 | 아니오 |
| v0 | M19 | body_layer | slot | lost | 몸 안이요 | 아니오 |
| v0 | M20 | sheet | no_slot | lost | 종이 한 장 | 아니오 |
| v0 | M20 | size | slot | lost | A4 종이 한 장 | 아니오 |
| v0 | M20 | height | slot | lost | 눈높이쯤에 | 아니오 |
| v0 | M20 | wrinkle | no_slot | lost | 가장자리가 살짝 구겨져 있어요 | 아니오 |
| v0 | M20 | body_layer | slot | lost | 주변이요 | 아니오 |
| v0 | M21 | color2 | no_slot | lost | 남색이 섞여 | 아니오 |
| v0 | M21 | opacity | slot | distorted/wrong_value | 반투명해요 | 아니오 |
| v0 | M21 | softness | no_slot | lost | 부드러울 것 같아요 | 아니오 |
| v0 | M21 | motion_type | slot_unscored | lost | 아래로 흘러내려요 | 아니오 |
| v0 | M21 | size | slot | lost | 상체를 다 덮을 정도요 | 아니오 |
| v0 | M22 | liquid | no_slot | lost | 물방울 하나가 맺혀 | 아니오 |
| v0 | M22 | opacity | slot_unscored | lost | 가운데는 맑게 비치는데 가장자리만 뿌예요 | 아니오 |
| v0 | M22 | size | slot | lost | 콩알만 해요 | 아니오 |
| v0 | M22 | motion_type | slot_unscored | lost | 떨어질 듯 말 듯 매달려 있어요 | 아니오 |
| v0 | M22 | body_layer | slot | distorted/cross_slot | 몸 안이요 | 아니오 |
| v0 | M23 | opacity | slot | lost | 바닥이 안 보여요 | 아니오 |
| v0 | M23 | size | slot | distorted/cross_slot | 서 있는 자리보다 조금 넓어요 | 아니오 |
| v0 | M24 | liquid | no_slot | lost | 진득한 노란 액체 | 아니오 |
| v0 | M24 | motion_type | slot_unscored | lost | 천천히 흘러내리는데 | 아니오 |
| v0 | M24 | texture_roughness | slot | distorted/cross_slot | 빛을 받으면 반짝여요 | 아니오 |
| v0 | M24 | size | slot | lost | 양은 한 컵쯤이요 | 아니오 |
| v0 | M24 | stickiness | no_slot | lost | 끈적끈적해요 | 아니오 |
| v0 | M24 | body_layer | slot | lost | 몸 안이요 | 아니오 |
| v0 | M25 | light | no_slot | preserved | 작은 빛 | 아니오 |
| v0 | M25 | motion_type | slot | lost | 콩닥콩닥 뛰듯이 | 아니오 |
| v0 | M25 | size | slot | distorted/wrong_value | 구슬만 해요 | 아니오 |
| v0 | M26 | light | no_slot | lost | 불꽃 같은 게 | 아니오 |
| v0 | M26 | color | slot | distorted/wrong_value | 주황색이에요 | 아니오 |
| v0 | M26 | color2 | no_slot | lost | 아래는 파랗고 | 아니오 |
| v0 | M26 | size | slot | lost | 손가락 한 마디만 해요 | 아니오 |
| v0 | M27 | light | no_slot | lost | 노란빛이 떠 있어요 | 아니오 |
| v0 | M27 | size | slot | lost | 냄비 뚜껑만 하고 | 아니오 |
| v0 | M27 | motion_type | slot | distorted/wrong_value | 원을 그리며 돌아요 | 아니오 |
| v0 | M27 | motion_speed | slot | lost | 느긋하게 | 아니오 |
| v0 | M27 | opacity | slot_unscored | lost | 가장자리는 흐려서 뒤가 살짝 비쳐요 | 아니오 |
| v0 | M27 | body_layer | slot | distorted/wrong_value | 몸 주변이요 | 아니오 |
| v0 | M28 | size | slot | lost | 도넛 하나 크기요 | 아니오 |
| v0 | M28 | motion_type | slot | lost | 그대로예요 | 아니오 |
| v0 | M29 | hole | no_slot | lost | 텅 빈 공간이에요 | 아니오 |
| v0 | M29 | size | slot | distorted/cross_slot | 배 전체만큼 넓어요 | 아니오 |
| v0 | M29 | motion_type | slot_unscored | lost | 넓어졌다 좁아졌다 해요 | 아니오 |
| v0 | M30 | figure | no_slot | lost | 작은 사람 모양 | 아니오 |
| v0 | M30 | motion_type | slot | distorted/cross_slot | 살짝 몸을 흔들어요 | 아니오 |
| v0 | M31 | figure | no_slot | lost | 까만 고양이 한 마리 | 아니오 |
| v0 | M31 | posture | slot | distorted/wrong_value | 동그랗게 말려 있어요 | 아니오 |
| v0 | M31 | softness | no_slot | lost | 털이 보송보송해요 | 아니오 |
| v0 | M31 | motion_type | slot_unscored | lost | 등이 오르락내리락해요 | 아니오 |
| v0 | M31 | size | slot | lost | 보통 고양이만 해요 | 아니오 |
| v0 | M32 | size | slot | distorted/wrong_value | 참새만 한 | 아니오 |
| v0 | M32 | color2 | no_slot | lost | 날개 끝은 노래요 | 아니오 |
| v0 | M32 | motion_type | slot_unscored | lost | 날개를 파닥파닥해요 | 아니오 |
| v0 | M34 | feeling | no_slot | lost | 꽉 막힌 느낌이에요 | 아니오 |
| v0 | M35 | feeling | no_slot | lost | 무겁게 가라앉는 느낌만 | 아니오 |
| v0 | M35 | shape | negated | lost | 모양은 없고 | 아니오 |
| v0 | M35 | size | slot | lost | 몸 전체만큼이요 | 아니오 |
| v0 | M36 | feeling | no_slot | lost | 안절부절못하는 느낌 | 아니오 |
| v0 | M36 | motion_type | slot | lost | 계속 들썩들썩해요 | 아니오 |
| v0 | M36 | body_part | slot | distorted/wrong_value | 배 쪽이요 | 아니오 |
| v1 | M05 | hardness | no_slot | preserved | 딱딱한 덩어리 | 예 |
| v1 | M09 | opacity | slot | distorted/wrong_value | 반쯤 투명해서 | 예 |
| v1 | M09 | size | slot | distorted/wrong_value | 저를 통째로 감쌀 만큼 커요 | 예 |
| v1 | M13 | motion_type | slot | distorted/cross_slot | 아래로 떨어져요 | 예 |
| v1 | M16 | shape | no_slot | preserved | 납작한 돌처럼 | 예 |
| v1 | M18 | lines | no_slot | preserved | 가느다란 검은 실 | 예 |
| v1 | M19 | brightness | slot | distorted/wrong_value | 희미하게 빛나요 | 예 |
| v1 | M19 | motion_type | slot_unscored | lost | 아래로 천천히 흘러내려요 | 예 |
| v1 | M22 | motion_type | slot_unscored | lost | 떨어질 듯 말 듯 매달려 있어요 | 예 |
| v1 | M24 | liquid | no_slot | preserved | 진득한 노란 액체 | 예 |
| v1 | M24 | motion_type | slot_unscored | lost | 천천히 흘러내리는데 | 예 |
| v1 | M24 | stickiness | no_slot | preserved | 끈적끈적해요 | 예 |
| v1 | M26 | color2 | no_slot | preserved | 아래는 파랗고 | 예 |
| v1 | M27 | light | no_slot | preserved | 노란빛이 떠 있어요 | 예 |
| v1 | M27 | brightness | slot | lost | 눈이 부실 만큼 밝은 | 예 |
| v1 | M29 | motion_type | slot_unscored | lost | 넓어졌다 좁아졌다 해요 | 예 |
| v1 | M30 | figure | no_slot | preserved | 작은 사람 모양 | 예 |
| v1 | M31 | figure | no_slot | preserved | 까만 고양이 한 마리 | 예 |
| v1 | M35 | feeling | no_slot | preserved | 무겁게 가라앉는 느낌만 | 예 |
| v1 | M35 | size | slot | lost | 몸 전체만큼이요 | 예 |

보존·손실의 상세(preserved 포함)와 배경 오염은 score/report.md·score/compare/report.md의 「실패 사례」에 있다.
