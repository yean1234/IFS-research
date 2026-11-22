# 일치도 채점 — imagery-mock-forms · 매핑 v0

채점기 fidelity/0.3.0, 코퍼스 imagery-mock-forms@0.1.0, 빌더 scene-spec-builder/0.1.0

## 전체

| 지표 | 값 |
| --- | --- |
| attributes | 258 |
| slotAttributes | 200 |
| reflectRate | 0.580 |
| distortRate | 0.125 |
| lostRate | 0.205 |
| droppedRate | 0.070 |
| preserveRate | 0.527 |
| unreflectedVerbatimRate | 0.127 |
| unreflectedVerbatimRateWithClauseIndex | 0.127 |
| lostClauseIndexOnly | 0 |
| negated | 1 |
| negationErrors | 0 |
| contamination | 0 |
| contaminationDecisive | 0 |
| spuriousValues | 53 |
| unsupportedValues | 85 |
| fuzzyValues | 0 |
| valuesFilled | 185 |
| spuriousRate | 0.286 |
| unsupportedRate | 0.460 |

미반영 원문 보존률(unreflectedVerbatimRate)은 속성 단위 보존 필드만 인정한 값이다. 절 색인(_clauses)까지 인정한 값은 unreflectedVerbatimRateWithClauseIndex, 절 색인으로만 남은 손실은 lostClauseIndexOnly. fuzzyValues는 자모 퍼지 일치 근거로 슬롯에 들어간 값의 수(0이어야 한다).

슬롯 속성 상태: reflected 116, distorted 25, preserved 4, lost 41, dropped_by_controller 14
근거 없는 값(근거 기준) 사유: no_evidence 0, no_gold_span 59, outside_gold_span 26 · 그중 값은 정답 expect를 만족 19

## 신뢰구간(항목 단위 군집 부트스트랩, B = 10000, 시드 20261116, 항목 36개)

이 합성 코퍼스 안에서의 변동만 나타냅니다. 일반 성능의 증거가 아닙니다.

| 지표 | 추정 | 95% 구간 |
| --- | --- | --- |
| reflectRate | 0.580 | [0.519, 0.640] |
| distortRate | 0.125 | [0.085, 0.167] |
| lostRate | 0.205 | [0.160, 0.251] |
| droppedRate | 0.070 | [0.030, 0.117] |
| preserveRate | 0.527 | [0.463, 0.591] |
| unreflectedVerbatimRate | 0.127 | [0.080, 0.174] |
| unreflectedVerbatimRateWithClauseIndex | 0.127 | [0.080, 0.174] |
| spuriousRate | 0.286 | [0.250, 0.327] |
| unsupportedRate | 0.460 | [0.416, 0.506] |
| fuzzyValueRate | 0.000 | [0.000, 0.000] |

## 정답 구간 폭(kind = slot)

| expect 종류 | n | reflected | 반영률 |
| --- | --- | --- | --- |
| color_hue | 15 | 11 | 0.733 |
| color_sl | 12 | 12 | 1.000 |
| equals | 42 | 32 | 0.762 |
| equals_null | 12 | 7 | 0.583 |
| in | 59 | 38 | 0.644 |
| range | 60 | 16 | 0.267 |

| 폭 | n | 최소 | 중앙값 | 평균 | 최대 |
| --- | --- | --- | --- | --- | --- |
| range 폭 | 60 | 0.080 | 0.350 | 0.350 | 0.550 |
| hue 폭(도) | 15 | 25.000 | 30.000 | 38.533 | 90.000 |
| s 폭 | 23 | 0.150 | 0.500 | 0.455 | 0.750 |
| l 폭 | 27 | 0.200 | 0.350 | 0.327 | 0.450 |
| in 목록 길이 | 59 | 1.000 | 2.000 | 2.000 | 5.000 |

range 폭 중앙값 0.350 이하: 반영률 0.333 (n 30) · 초과: 반영률 0.200 (n 30)

layout.size 정답 구간 폭을 v1 크기 척도(1단위 = 6.000옥타브)로 환산: n 31 · 최소 1.200옥타브(×2.300) · 중앙값 2.100옥타브(×4.290) · 최대 2.700옥타브(×6.500). 구간 안이면 반영으로 세므로, 이 배율만큼 다른 크기도 반영될 수 있다.

## 속성 유형별

| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| body_layer | 35 | 35 | 26 | 3 | 0 | 6 | 0 | 0 | 0.743 |
| body_part | 26 | 26 | 23 | 3 | 0 | 0 | 0 | 0 | 0.885 |
| brightness | 7 | 6 | 4 | 2 | 0 | 0 | 0 | 1 | 0.667 |
| color | 33 | 33 | 27 | 1 | 3 | 0 | 2 | 0 | 0.818 |
| color2 | 5 | 0 | 0 | 0 | 2 | 3 | 0 | 0 | – |
| distance | 2 | 2 | 0 | 1 | 0 | 1 | 0 | 0 | 0.000 |
| erosion | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0.000 |
| feeling | 4 | 0 | 0 | 0 | 0 | 3 | 1 | 0 | – |
| figure | 3 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | – |
| form | 13 | 13 | 9 | 0 | 1 | 3 | 0 | 0 | 0.692 |
| hardness | 2 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | – |
| height | 3 | 3 | 2 | 0 | 0 | 1 | 0 | 0 | 0.667 |
| hole | 2 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | – |
| hollow | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | – |
| light | 3 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | – |
| lines | 3 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | – |
| liquid | 3 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | – |
| motion_speed | 5 | 5 | 2 | 0 | 0 | 1 | 2 | 0 | 0.400 |
| motion_type | 36 | 27 | 11 | 4 | 0 | 13 | 8 | 0 | 0.407 |
| opacity | 10 | 7 | 2 | 2 | 0 | 6 | 0 | 0 | 0.286 |
| other | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | – |
| posture | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0.500 |
| shape | 6 | 0 | 0 | 0 | 2 | 4 | 0 | 0 | – |
| sheet | 2 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | – |
| size | 35 | 35 | 5 | 7 | 0 | 21 | 2 | 0 | 0.143 |
| softness | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | – |
| stickiness | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | – |
| temperature | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| texture_roughness | 5 | 5 | 4 | 1 | 0 | 0 | 0 | 0 | 0.800 |
| weight | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| width | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | – |
| wrinkle | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | – |

## 항목별

| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값(경로) | 근거 없는 값(근거) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M01 | 8 | 0.500 | 0.000 | 0.500 | 0 | 0 | 2 | 3 |
| M02 | 7 | 0.857 | 0.000 | 0.857 | 0 | 0 | 1 | 3 |
| M03 | 5 | 0.600 | 0.000 | 0.500 | 0 | 0 | 2 | 2 |
| M04 | 7 | 0.714 | 0.000 | 0.750 | 0 | 0 | 1 | 2 |
| M05 | 7 | 0.857 | 0.000 | 0.889 | 0 | 0 | 1 | 2 |
| M06 | 6 | 0.667 | 0.167 | 0.625 | 0 | 0 | 1 | 3 |
| M07 | 5 | 0.600 | 0.000 | 0.571 | 0 | 0 | 1 | 3 |
| M08 | 7 | 0.714 | 0.286 | 0.714 | 0 | 0 | 1 | 2 |
| M09 | 6 | 0.333 | 0.333 | 0.500 | 0 | 0 | 2 | 4 |
| M10 | 6 | 0.500 | 0.167 | 0.500 | 0 | 0 | 2 | 2 |
| M11 | 7 | 0.429 | 0.000 | 0.375 | 0 | 0 | 2 | 3 |
| M12 | 7 | 0.571 | 0.143 | 0.571 | 0 | 0 | 3 | 5 |
| M13 | 6 | 0.500 | 0.167 | 0.500 | 0 | 0 | 2 | 2 |
| M14 | 7 | 0.429 | 0.286 | 0.375 | 0 | 0 | 3 | 3 |
| M15 | 5 | 0.800 | 0.000 | 0.714 | 0 | 0 | 2 | 2 |
| M16 | 6 | 0.500 | 0.000 | 0.667 | 0 | 0 | 2 | 2 |
| M17 | 5 | 0.800 | 0.000 | 0.667 | 0 | 0 | 1 | 2 |
| M18 | 3 | 1.000 | 0.000 | 0.667 | 0 | 0 | 1 | 2 |
| M19 | 6 | 0.333 | 0.167 | 0.375 | 0 | 0 | 1 | 2 |
| M20 | 5 | 0.200 | 0.000 | 0.143 | 0 | 0 | 0 | 1 |
| M21 | 5 | 0.600 | 0.200 | 0.444 | 0 | 0 | 1 | 1 |
| M22 | 4 | 0.000 | 0.500 | 0.000 | 0 | 0 | 3 | 4 |
| M23 | 6 | 0.667 | 0.167 | 0.714 | 0 | 0 | 3 | 3 |
| M24 | 6 | 0.500 | 0.167 | 0.333 | 0 | 0 | 2 | 2 |
| M25 | 5 | 0.600 | 0.200 | 0.714 | 0 | 0 | 1 | 2 |
| M26 | 5 | 0.600 | 0.200 | 0.500 | 0 | 0 | 1 | 3 |
| M27 | 7 | 0.429 | 0.286 | 0.333 | 0 | 0 | 1 | 3 |
| M28 | 5 | 0.600 | 0.000 | 0.667 | 0 | 0 | 1 | 2 |
| M29 | 4 | 0.750 | 0.250 | 0.500 | 0 | 0 | 1 | 2 |
| M30 | 5 | 0.800 | 0.200 | 0.667 | 0 | 0 | 2 | 3 |
| M31 | 5 | 0.600 | 0.200 | 0.375 | 0 | 0 | 1 | 2 |
| M32 | 4 | 0.750 | 0.250 | 0.571 | 0 | 0 | 2 | 3 |
| M33 | 3 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 0 |
| M34 | 5 | 0.800 | 0.000 | 0.667 | 0 | 0 | 1 | 1 |
| M35 | 5 | 0.600 | 0.000 | 0.429 | 0 | 0 | 1 | 2 |
| M36 | 5 | 0.600 | 0.200 | 0.500 | 0 | 0 | 1 | 2 |

## 실패 사례

| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |
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
| M07 | preserved | color | 살구색 | {"hue_deg": [12, 40], "s": [0.3, 0.95], "l": [0.55, 0.88]} | – | [] |
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
| M09 | preserved | color | 연두색 | {"hue_deg": [65, 110], "s": [0.3, 1.0], "l": [0.4, 0.82]} | – | [] |
| M09 | distorted/wrong_value | opacity | 반쯤 투명해서 | {"range": [0.25, 0.7]} | 0.100 | ["투명"] |
| M09 | distorted/wrong_value | size | 저를 통째로 감쌀 만큼 커요 | {"range": [0.75, 1.0]} | 0.621 | ["커요"] |
| M09 | dropped_by_controller | motion_type | 일렁여요 | {"in": ["rippling", "swaying"]} | – | – |
| M09 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M09 | spurious | body.part |  | – | body | ["몸", "몸"] |
| M09 | unsupported/outside_gold_span | form.type |  | – | shell | ["비눗방울 막처럼"] |
| M09 | unsupported/no_gold_span | motion.type |  | – | rotating | ["돌아요"] |
| M10 | preserved | form | 껍데기 | {"equals": "shell"} | – | [] |
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
| M19 | preserved | color | 금빛 | {"hue_deg": [35, 60], "s": [0.4, 1.0], "l": [0.35, 0.75]} | – | [] |
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
