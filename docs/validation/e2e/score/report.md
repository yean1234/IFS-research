# 일치도 채점 — imagery-heldout · 매핑 v0

채점기 fidelity/0.3.0, 코퍼스 imagery-heldout@1.0.0, 빌더 scene-spec-builder/0.1.0

## 전체

| 지표 | 값 |
| --- | --- |
| attributes | 237 |
| slotAttributes | 212 |
| reflectRate | 0.500 |
| distortRate | 0.174 |
| lostRate | 0.160 |
| droppedRate | 0.108 |
| preserveRate | 0.532 |
| unreflectedVerbatimRate | 0.283 |
| unreflectedVerbatimRateWithClauseIndex | 0.283 |
| lostClauseIndexOnly | 0 |
| negated | 6 |
| negationErrors | 0 |
| contamination | 5 |
| contaminationDecisive | 5 |
| spuriousValues | 56 |
| unsupportedValues | 100 |
| fuzzyValues | 0 |
| valuesFilled | 203 |
| spuriousRate | 0.276 |
| unsupportedRate | 0.493 |

미반영 원문 보존률(unreflectedVerbatimRate)은 속성 단위 보존 필드만 인정한 값이다. 절 색인(_clauses)까지 인정한 값은 unreflectedVerbatimRateWithClauseIndex, 절 색인으로만 남은 손실은 lostClauseIndexOnly. fuzzyValues는 자모 퍼지 일치 근거로 슬롯에 들어간 값의 수(0이어야 한다).

슬롯 속성 상태: reflected 106, distorted 37, preserved 12, lost 34, dropped_by_controller 23
근거 없는 값(근거 기준) 사유: no_evidence 0, no_gold_span 67, outside_gold_span 33 · 그중 값은 정답 expect를 만족 20

## 신뢰구간(항목 단위 군집 부트스트랩, B = 10000, 시드 20261116, 항목 30개)

이 합성 코퍼스 안에서의 변동만 나타냅니다. 일반 성능의 증거가 아닙니다.

| 지표 | 추정 | 95% 구간 |
| --- | --- | --- |
| reflectRate | 0.500 | [0.434, 0.562] |
| distortRate | 0.174 | [0.123, 0.228] |
| lostRate | 0.160 | [0.114, 0.211] |
| droppedRate | 0.108 | [0.057, 0.166] |
| preserveRate | 0.532 | [0.473, 0.587] |
| unreflectedVerbatimRate | 0.283 | [0.212, 0.356] |
| unreflectedVerbatimRateWithClauseIndex | 0.283 | [0.212, 0.356] |
| spuriousRate | 0.276 | [0.244, 0.311] |
| unsupportedRate | 0.493 | [0.437, 0.551] |
| fuzzyValueRate | 0.000 | [0.000, 0.000] |

## 정답 구간 폭(kind = slot)

| expect 종류 | n | reflected | 반영률 |
| --- | --- | --- | --- |
| color_hue | 23 | 10 | 0.435 |
| color_sl | 6 | 2 | 0.333 |
| equals | 13 | 13 | 1.000 |
| equals_null | 1 | 0 | 0.000 |
| in | 57 | 38 | 0.667 |
| range | 112 | 43 | 0.384 |

| 폭 | n | 최소 | 중앙값 | 평균 | 최대 |
| --- | --- | --- | --- | --- | --- |
| range 폭 | 112 | 0.050 | 0.350 | 0.326 | 0.700 |
| hue 폭(도) | 23 | 17.000 | 35.000 | 39.217 | 90.000 |
| s 폭 | 8 | 0.200 | 0.275 | 0.331 | 0.500 |
| l 폭 | 22 | 0.150 | 0.335 | 0.322 | 0.500 |
| in 목록 길이 | 57 | 1.000 | 2.000 | 1.772 | 4.000 |

range 폭 중앙값 0.350 이하: 반영률 0.358 (n 67) · 초과: 반영률 0.422 (n 45)

layout.size 정답 구간 폭을 v1 크기 척도(1단위 = 6.000옥타브)로 환산: n 27 · 최소 0.900옥타브(×1.870) · 중앙값 2.100옥타브(×4.290) · 최대 2.700옥타브(×6.500). 구간 안이면 반영으로 세므로, 이 배율만큼 다른 크기도 반영될 수 있다.

## 속성 유형별

| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| body_layer | 15 | 15 | 14 | 1 | 0 | 0 | 0 | 0 | 0.933 |
| body_part | 7 | 7 | 0 | 7 | 0 | 0 | 0 | 0 | 0.000 |
| brightness | 16 | 15 | 2 | 3 | 1 | 1 | 9 | 0 | 0.133 |
| color | 31 | 30 | 12 | 6 | 4 | 1 | 8 | 0 | 0.400 |
| distance | 8 | 8 | 1 | 1 | 1 | 5 | 0 | 0 | 0.125 |
| erosion | 4 | 4 | 2 | 1 | 0 | 1 | 0 | 0 | 0.500 |
| form | 14 | 14 | 10 | 0 | 3 | 1 | 0 | 0 | 0.714 |
| height | 16 | 16 | 6 | 4 | 1 | 5 | 0 | 0 | 0.375 |
| motion_speed | 11 | 11 | 9 | 0 | 0 | 1 | 1 | 0 | 0.818 |
| motion_type | 29 | 29 | 24 | 2 | 0 | 2 | 1 | 0 | 0.828 |
| opacity | 8 | 8 | 4 | 1 | 0 | 3 | 0 | 0 | 0.500 |
| other | 4 | 0 | 0 | 0 | 1 | 3 | 0 | 0 | – |
| posture | 5 | 5 | 3 | 1 | 1 | 0 | 0 | 0 | 0.600 |
| saturation | 7 | 7 | 4 | 0 | 0 | 0 | 3 | 0 | 0.571 |
| shape | 9 | 0 | 0 | 0 | 3 | 6 | 0 | 0 | – |
| size | 27 | 27 | 5 | 10 | 0 | 9 | 3 | 0 | 0.185 |
| smell | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | – |
| sound | 2 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | – |
| temperature | 3 | 0 | 0 | 0 | 2 | 1 | 0 | 0 | – |
| texture_roughness | 16 | 16 | 10 | 0 | 1 | 5 | 0 | 0 | 0.625 |
| weight | 4 | 0 | 0 | 0 | 1 | 3 | 0 | 0 | – |

## 항목별

| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값(경로) | 근거 없는 값(근거) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H01 | 8 | 0.625 | 0.125 | 0.750 | 0 | 0 | 2 | 3 |
| H02 | 8 | 0.625 | 0.125 | 0.625 | 0 | 0 | 3 | 3 |
| H03 | 7 | 0.571 | 0.000 | 0.625 | 0 | 0 | 1 | 2 |
| H04 | 8 | 0.500 | 0.125 | 0.500 | 1 | 0 | 1 | 3 |
| H05 | 5 | 0.600 | 0.000 | 0.500 | 0 | 0 | 2 | 3 |
| H06 | 7 | 0.571 | 0.143 | 0.625 | 0 | 0 | 1 | 3 |
| H07 | 6 | 0.333 | 0.500 | 0.375 | 0 | 0 | 2 | 4 |
| H08 | 7 | 0.714 | 0.000 | 0.625 | 0 | 0 | 2 | 3 |
| H09 | 7 | 0.571 | 0.429 | 0.500 | 0 | 0 | 4 | 5 |
| H10 | 7 | 0.286 | 0.000 | 0.250 | 0 | 0 | 2 | 3 |
| H11 | 7 | 0.571 | 0.143 | 0.500 | 0 | 0 | 1 | 3 |
| H12 | 6 | 0.667 | 0.167 | 0.571 | 0 | 0 | 1 | 2 |
| H13 | 8 | 0.375 | 0.250 | 0.375 | 0 | 0 | 1 | 6 |
| H14 | 6 | 0.500 | 0.000 | 0.625 | 0 | 0 | 1 | 3 |
| H15 | 7 | 0.571 | 0.429 | 0.500 | 0 | 0 | 2 | 4 |
| H16 | 8 | 0.375 | 0.125 | 0.500 | 0 | 0 | 2 | 4 |
| H17 | 6 | 0.500 | 0.167 | 0.429 | 0 | 0 | 1 | 3 |
| H18 | 8 | 0.500 | 0.375 | 0.500 | 2 | 0 | 2 | 5 |
| H19 | 7 | 0.000 | 0.143 | 0.250 | 1 | 0 | 3 | 5 |
| H20 | 7 | 0.857 | 0.000 | 0.875 | 0 | 0 | 2 | 2 |
| H21 | 8 | 0.375 | 0.000 | 0.750 | 0 | 0 | 2 | 2 |
| H22 | 6 | 0.167 | 0.333 | 0.125 | 0 | 0 | 2 | 5 |
| H23 | 7 | 0.571 | 0.143 | 0.500 | 0 | 0 | 2 | 3 |
| H24 | 7 | 0.571 | 0.429 | 0.625 | 0 | 0 | 1 | 2 |
| H25 | 7 | 0.571 | 0.143 | 0.500 | 0 | 0 | 2 | 4 |
| H26 | 8 | 0.375 | 0.250 | 0.625 | 0 | 0 | 2 | 3 |
| H27 | 8 | 0.750 | 0.125 | 0.750 | 0 | 0 | 2 | 2 |
| H28 | 6 | 0.667 | 0.333 | 0.625 | 0 | 0 | 3 | 4 |
| H29 | 8 | 0.250 | 0.000 | 0.500 | 0 | 0 | 2 | 2 |
| H30 | 7 | 0.429 | 0.286 | 0.429 | 1 | 0 | 2 | 4 |

## 실패 사례

| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| H01 | preserved | form | 유리구슬 | {"in": ["blob"]} | – | [] |
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
| H04 | contamination | material.color | 파란 벽 | – | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | 파란 |
| H04 | spurious | body.part |  | – | body | ["몸"] |
| H04 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파란"] |
| H04 | unsupported/outside_gold_span | layout.distance |  | – | 0.600 | ["떨어져"] |
| H05 | dropped_by_controller | color | 회색이 섞인 검은색 | {"hue_deg": null, "s": [0.0, 0.2], "l": [0.05, 0.35]} | – | – |
| H05 | lost | weight | 묵직할 것 같아요 | – | – | – |
| H05 | lost | size | 주먹만 하고 | {"range": [0.05, 0.45]} | – | [] |
| H05 | spurious | body.part |  | – | body | ["몸"] |
| H05 | spurious | body.layer |  | – | around | ["밖"] |
| H05 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.08} | ["검은"] |
| H06 | preserved | color | 은빛 | {"hue_deg": null, "s": [0.0, 0.2], "l": [0.6, 0.92]} | – | [] |
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
| H16 | preserved | form | 껍데기 | {"in": ["shell"]} | – | [] |
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
| H18 | contamination | material.color | 하얀 방 | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | 하얀 |
| H18 | contamination | material.brightness | 깨끗하고 밝은데 | – | 0.800 | 밝은데 |
| H18 | spurious | body.part |  | – | head | ["머리"] |
| H18 | spurious | body.layer |  | – | around | ["밖"] |
| H18 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H18 | unsupported/outside_gold_span | material.brightness |  | – | 0.800 | ["밝은데"] |
| H18 | unsupported/outside_gold_span | motion.type |  | – | drifting | ["떠다녀요", "떠다녀요"] |
| H19 | preserved | color | 청록색 | {"hue_deg": [160, 195], "s": null, "l": null} | – | [] |
| H19 | dropped_by_controller | saturation | 아주 선명한 | {"range": [0.7, 1.0]} | – | – |
| H19 | dropped_by_controller | brightness | 환하게 빛나요 | {"range": [0.7, 1.0]} | – | – |
| H19 | lost | shape | 뾰족하게 솟아 | – | – | – |
| H19 | distorted/wrong_value | size | 제 손보다 조금 커요 | {"range": [0.2, 0.55]} | 0.621 | ["커요"] |
| H19 | preserved | distance | 바로 앞 | {"range": [0.0, 0.25]} | – | [] |
| H19 | dropped_by_controller | motion_type | 빙글 돌아요 | {"in": ["rotating", "circling"]} | – | – |
| H19 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| H19 | contamination | motion.type | 퍼져 나와요 | – | spreading | 퍼져 |
| H19 | spurious | layout.verticalOffset |  | – | 0.490 | ["손"] |
| H19 | spurious | body.part |  | – | body | ["몸"] |
| H19 | spurious | body.layer |  | – | around | ["밖"] |
| H19 | unsupported/no_gold_span | material.brightness |  | – | 0.700 | ["빛", "빛"] |
| H19 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| H20 | lost | height | 발밑이요 | {"range": [0.0, 0.1]} | – | [] |
| H20 | spurious | body.part |  | – | body | ["몸"] |
| H20 | spurious | body.layer |  | – | around | ["밖"] |
| H21 | preserved | color | 빨간색 | {"hue_deg": [345, 15], "s": null, "l": [0.3, 0.65]} | – | [] |
| H21 | lost | distance | 눈앞에 | {"range": [0.0, 0.3]} | – | [] |
| H21 | preserved | brightness | 반짝반짝 | {"range": [0.55, 1.0]} | – | [] |
| H21 | preserved | texture_roughness | 매끈매끈 | {"range": [0.0, 0.3]} | – | [] |
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
| H26 | preserved | height | 배꼽 앞쪽 | {"range": [0.5, 0.65]} | – | [] |
| H26 | preserved | posture | 돌돌 말려 | {"in": ["curled"]} | – | [] |
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
| H29 | preserved | color | 황토색 | {"hue_deg": [25, 50], "s": null, "l": [0.3, 0.6]} | – | [] |
| H29 | preserved | form | 흙덩이 | {"in": ["blob"]} | – | [] |
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
| H30 | contamination | material.color | 하얀 책상 | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | 하얀 |
| H30 | spurious | body.part |  | – | hand | ["손바닥"] |
| H30 | spurious | body.layer |  | – | surface_above | ["위"] |
| H30 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 0.0, "s": 0.0, "l": 0.95} | ["하얀"] |
| H30 | unsupported/outside_gold_span | layout.verticalOffset |  | – | 0.490 | ["손바닥"] |
