# 일치도 채점 — imagery-heldout · 매핑 v1

채점기 fidelity/0.3.0, 코퍼스 imagery-heldout@1.0.0, 빌더 scene-spec-builder-v1/1.2.0

## 전체

| 지표 | 값 |
| --- | --- |
| attributes | 237 |
| slotAttributes | 212 |
| reflectRate | 0.698 |
| distortRate | 0.094 |
| lostRate | 0.014 |
| droppedRate | 0.108 |
| preserveRate | 0.797 |
| unreflectedVerbatimRate | 0.859 |
| unreflectedVerbatimRateWithClauseIndex | 1.000 |
| lostClauseIndexOnly | 3 |
| negated | 6 |
| negationErrors | 0 |
| contamination | 2 |
| contaminationDecisive | 2 |
| spuriousValues | 49 |
| unsupportedValues | 81 |
| fuzzyValues | 0 |
| valuesFilled | 223 |
| spuriousRate | 0.220 |
| unsupportedRate | 0.363 |

미반영 원문 보존률(unreflectedVerbatimRate)은 속성 단위 보존 필드만 인정한 값이다. 절 색인(_clauses)까지 인정한 값은 unreflectedVerbatimRateWithClauseIndex, 절 색인으로만 남은 손실은 lostClauseIndexOnly. fuzzyValues는 자모 퍼지 일치 근거로 슬롯에 들어간 값의 수(0이어야 한다).

슬롯 속성 상태: reflected 148, distorted 20, preserved 18, lost 3, dropped_by_controller 23
근거 없는 값(근거 기준) 사유: no_evidence 0, no_gold_span 60, outside_gold_span 21 · 그중 값은 정답 expect를 만족 21

## 신뢰구간(항목 단위 군집 부트스트랩, B = 10000, 시드 20261116, 항목 30개)

이 합성 코퍼스 안에서의 변동만 나타냅니다. 일반 성능의 증거가 아닙니다.

| 지표 | 추정 | 95% 구간 |
| --- | --- | --- |
| reflectRate | 0.698 | [0.641, 0.753] |
| distortRate | 0.094 | [0.057, 0.133] |
| lostRate | 0.014 | [0.000, 0.030] |
| droppedRate | 0.108 | [0.057, 0.166] |
| preserveRate | 0.797 | [0.757, 0.837] |
| unreflectedVerbatimRate | 0.859 | [0.766, 0.946] |
| unreflectedVerbatimRateWithClauseIndex | 1.000 | [1.000, 1.000] |
| spuriousRate | 0.220 | [0.189, 0.249] |
| unsupportedRate | 0.363 | [0.317, 0.412] |
| fuzzyValueRate | 0.000 | [0.000, 0.000] |

## 정답 구간 폭(kind = slot)

| expect 종류 | n | reflected | 반영률 |
| --- | --- | --- | --- |
| color_hue | 23 | 16 | 0.696 |
| color_sl | 6 | 4 | 0.667 |
| equals | 13 | 13 | 1.000 |
| equals_null | 1 | 0 | 0.000 |
| in | 57 | 48 | 0.842 |
| range | 112 | 67 | 0.598 |

| 폭 | n | 최소 | 중앙값 | 평균 | 최대 |
| --- | --- | --- | --- | --- | --- |
| range 폭 | 112 | 0.050 | 0.350 | 0.326 | 0.700 |
| hue 폭(도) | 23 | 17.000 | 35.000 | 39.217 | 90.000 |
| s 폭 | 8 | 0.200 | 0.275 | 0.331 | 0.500 |
| l 폭 | 22 | 0.150 | 0.335 | 0.322 | 0.500 |
| in 목록 길이 | 57 | 1.000 | 2.000 | 1.772 | 4.000 |

range 폭 중앙값 0.350 이하: 반영률 0.582 (n 67) · 초과: 반영률 0.622 (n 45)

layout.size 정답 구간 폭을 v1 크기 척도(1단위 = 6.000옥타브)로 환산: n 27 · 최소 0.900옥타브(×1.870) · 중앙값 2.100옥타브(×4.290) · 최대 2.700옥타브(×6.500). 구간 안이면 반영으로 세므로, 이 배율만큼 다른 크기도 반영될 수 있다.

## 속성 유형별

| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| body_layer | 15 | 15 | 14 | 1 | 0 | 0 | 0 | 0 | 0.933 |
| body_part | 7 | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| brightness | 16 | 15 | 5 | 2 | 0 | 0 | 9 | 0 | 0.333 |
| color | 31 | 30 | 20 | 1 | 2 | 0 | 8 | 0 | 0.667 |
| distance | 8 | 8 | 4 | 1 | 3 | 0 | 0 | 0 | 0.500 |
| erosion | 4 | 4 | 2 | 1 | 1 | 0 | 0 | 0 | 0.500 |
| form | 14 | 14 | 12 | 0 | 2 | 0 | 0 | 0 | 0.857 |
| height | 16 | 16 | 11 | 3 | 2 | 0 | 0 | 0 | 0.688 |
| motion_speed | 11 | 11 | 9 | 0 | 1 | 0 | 1 | 0 | 0.818 |
| motion_type | 29 | 29 | 25 | 2 | 0 | 1 | 1 | 0 | 0.862 |
| opacity | 8 | 8 | 6 | 1 | 0 | 1 | 0 | 0 | 0.750 |
| other | 4 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | – |
| posture | 5 | 5 | 3 | 1 | 1 | 0 | 0 | 0 | 0.600 |
| saturation | 7 | 7 | 4 | 0 | 0 | 0 | 3 | 0 | 0.571 |
| shape | 9 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | – |
| size | 27 | 27 | 13 | 7 | 3 | 1 | 3 | 0 | 0.481 |
| smell | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| sound | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | – |
| temperature | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| texture_roughness | 16 | 16 | 13 | 0 | 3 | 0 | 0 | 0 | 0.812 |
| weight | 4 | 0 | 0 | 0 | 4 | 0 | 0 | 0 | – |

## 항목별

| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값(경로) | 근거 없는 값(근거) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H01 | 8 | 0.625 | 0.125 | 0.750 | 0 | 0 | 1 | 3 |
| H02 | 8 | 0.750 | 0.125 | 0.750 | 0 | 0 | 3 | 3 |
| H03 | 7 | 0.571 | 0.000 | 0.625 | 0 | 0 | 1 | 1 |
| H04 | 8 | 1.000 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| H05 | 5 | 0.800 | 0.000 | 0.750 | 0 | 0 | 2 | 3 |
| H06 | 7 | 0.714 | 0.286 | 0.750 | 0 | 0 | 1 | 4 |
| H07 | 6 | 0.667 | 0.167 | 0.750 | 0 | 0 | 1 | 2 |
| H08 | 7 | 0.857 | 0.000 | 0.875 | 0 | 0 | 2 | 3 |
| H09 | 7 | 0.714 | 0.286 | 0.750 | 0 | 0 | 3 | 4 |
| H10 | 7 | 0.571 | 0.000 | 0.750 | 0 | 0 | 2 | 3 |
| H11 | 7 | 0.857 | 0.000 | 0.875 | 0 | 0 | 1 | 2 |
| H12 | 6 | 0.500 | 0.167 | 0.857 | 0 | 0 | 1 | 2 |
| H13 | 8 | 0.750 | 0.000 | 0.750 | 0 | 0 | 0 | 3 |
| H14 | 6 | 0.667 | 0.000 | 0.750 | 0 | 0 | 1 | 3 |
| H15 | 7 | 0.571 | 0.286 | 0.750 | 0 | 0 | 2 | 2 |
| H16 | 8 | 0.750 | 0.000 | 0.750 | 0 | 0 | 1 | 2 |
| H17 | 6 | 0.500 | 0.000 | 0.714 | 0 | 0 | 1 | 2 |
| H18 | 8 | 0.625 | 0.250 | 0.750 | 1 | 0 | 2 | 4 |
| H19 | 7 | 0.286 | 0.000 | 0.500 | 1 | 0 | 2 | 4 |
| H20 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 2 | 2 |
| H21 | 8 | 0.625 | 0.125 | 0.875 | 0 | 0 | 2 | 3 |
| H22 | 6 | 0.500 | 0.000 | 0.750 | 0 | 0 | 1 | 3 |
| H23 | 7 | 0.857 | 0.143 | 0.875 | 0 | 0 | 2 | 3 |
| H24 | 7 | 0.714 | 0.143 | 0.750 | 0 | 0 | 1 | 1 |
| H25 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 2 | 3 |
| H26 | 8 | 0.625 | 0.125 | 0.875 | 0 | 0 | 1 | 3 |
| H27 | 8 | 0.625 | 0.250 | 0.750 | 0 | 0 | 2 | 2 |
| H28 | 6 | 0.667 | 0.167 | 0.750 | 0 | 0 | 3 | 5 |
| H29 | 8 | 0.750 | 0.000 | 1.000 | 0 | 0 | 2 | 2 |
| H30 | 7 | 0.714 | 0.143 | 0.857 | 0 | 0 | 3 | 3 |

## 실패 사례

| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| H01 | preserved | form | 유리구슬 | {"in": ["blob"]} | – | [] |
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
| H07 | preserved | size | 귤 하나 정도 | {"range": [0.1, 0.45]} | – | [] |
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
| H10 | preserved | size | 한 변이 30센티쯤 | {"range": [0.25, 0.65]} | – | [] |
| H10 | dropped_by_controller | brightness | 조금 어두워요 | {"range": [0.15, 0.45]} | – | – |
| H10 | spurious | body.part |  | – | body | ["몸"] |
| H10 | spurious | body.layer |  | – | around | ["밖"] |
| H10 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 24.8, "s": 0.45, "l": 0.3} | ["갈색"] |
| H11 | dropped_by_controller | color | 연한 분홍 | {"hue_deg": [300, 10], "s": null, "l": [0.65, 0.95]} | – | – |
| H11 | spurious | body.layer |  | – | surface | ["표면"] |
| H11 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 339.8, "s": 0.6, "l": 0.78} | ["분홍빛"] |
| H12 | preserved | color | 초록색 | {"hue_deg": [90, 150], "s": null, "l": null} | – | [] |
| H12 | distorted/wrong_value | size | 손바닥만 한 | {"range": [0.1, 0.45]} | 0.475 | ["손바닥만 한"] |
| H12 | preserved | height | 눈높이보다 조금 아래 | {"range": [0.75, 0.92]} | – | [] |
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
| H15 | preserved | height | 눈높이 | {"range": [0.85, 1.0]} | – | [] |
| H15 | distorted/wrong_value | size | 팔찌보다 조금 큰 | {"range": [0.15, 0.5]} | 0.573 | ["큰"] |
| H15 | distorted/cross_slot | distance | 팔 뻗으면 닿을 거리 | {"range": [0.05, 0.3]} | – | [{"path": "body.part", "trigger": "팔", "value": "arm"}] |
| H15 | spurious | body.part |  | – | arm | ["팔"] |
| H15 | spurious | body.layer |  | – | around_front | ["앞"] |
| H16 | dropped_by_controller | color | 옅은 하늘색 | {"hue_deg": [185, 215], "s": null, "l": [0.6, 0.92]} | – | – |
| H16 | dropped_by_controller | brightness | 은은하게 밝아요 | {"range": [0.5, 0.8]} | – | – |
| H16 | spurious | layout.distance |  | – | 0.000 | ["붙어"] |
| H16 | unsupported/no_gold_span | material.color |  | – | {"hue_deg": 200.2, "s": 0.7, "l": 0.75} | ["하늘색"] |
| H17 | dropped_by_controller | size | 쌀알만 해요 | {"range": [0.0, 0.15]} | – | – |
| H17 | preserved | color | 빨간 | {"hue_deg": [345, 15], "s": null, "l": [0.3, 0.65]} | – | [] |
| H17 | dropped_by_controller | saturation | 쨍한 | {"range": [0.7, 1.0]} | – | – |
| H17 | spurious | form.type |  | – | fragments | ["알갱이"] |
| H17 | unsupported/no_gold_span | layout.size |  | – | 0.224 | ["작은"] |
| H18 | distorted/wrong_value | brightness | 어두워요 | {"range": [0.0, 0.4]} | 0.800 | ["밝은데"] |
| H18 | preserved | size | 소파만 하고 | {"range": [0.65, 1.0]} | – | [] |
| H18 | distorted/cross_slot | height | 제 머리보다 약간 높은 | {"range": [0.95, 1.0]} | – | [{"path": "body.part", "trigger": "머리", "value": "head"}] |
| H18 | contamination | material.brightness | 깨끗하고 밝은데 | – | 0.800 | 밝은데 |
| H18 | spurious | body.part |  | – | head | ["머리"] |
| H18 | spurious | body.layer |  | – | around | ["밖"] |
| H18 | unsupported/outside_gold_span | material.brightness |  | – | 0.800 | ["밝은데"] |
| H18 | unsupported/outside_gold_span | motion.type |  | – | floating | ["둥둥"] |
| H19 | dropped_by_controller | saturation | 아주 선명한 | {"range": [0.7, 1.0]} | – | – |
| H19 | dropped_by_controller | brightness | 환하게 빛나요 | {"range": [0.7, 1.0]} | – | – |
| H19 | preserved | distance | 바로 앞 | {"range": [0.0, 0.25]} | – | [] |
| H19 | dropped_by_controller | motion_type | 빙글 돌아요 | {"in": ["rotating", "circling"]} | – | – |
| H19 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| H19 | contamination | motion.type | 퍼져 나와요 | – | spreading | 퍼져 |
| H19 | spurious | body.part |  | – | body | ["몸"] |
| H19 | spurious | body.layer |  | – | around | ["밖"] |
| H19 | unsupported/no_gold_span | material.brightness |  | – | 0.700 | ["빛", "빛"] |
| H19 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| H20 | spurious | body.part |  | – | body | ["몸"] |
| H20 | spurious | body.layer |  | – | around | ["밖"] |
| H21 | preserved | distance | 눈앞에 | {"range": [0.0, 0.3]} | – | [] |
| H21 | distorted/wrong_value | motion_type | 둥둥 떠잇어요 | {"in": ["floating", "drifting"]} | moving | ["움직여여"] |
| H21 | preserved | motion_speed | 천천이 | {"range": [0.0, 0.4]} | – | [] |
| H21 | spurious | body.part |  | – | body | ["몸"] |
| H21 | spurious | body.layer |  | – | around | ["밖"] |
| H21 | unsupported/outside_gold_span | motion.type |  | – | moving | ["움직여여"] |
| H22 | dropped_by_controller | color | 눈처럼 하얘요 | {"hue_deg": null, "s": null, "l": [0.85, 1.0]} | – | – |
| H22 | lost | motion_type | 천천히 내려오고 | {"in": ["sinking", "settling", "drifting", "floating"]} | – | [] |
| H22 | preserved | erosion | 가장자리가 살짝 흐트러져 | {"range": [0.05, 0.5]} | – | [] |
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
| H26 | preserved | posture | 돌돌 말려 | {"in": ["curled"]} | – | [] |
| H26 | preserved | texture_roughness | 보풀보풀해요 | {"range": [0.45, 1.0]} | – | [] |
| H26 | spurious | body.part |  | – | belly | ["배꼽"] |
| H26 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 90.0, "s": 0.55, "l": 0.55} | ["연두색"] |
| H26 | unsupported/outside_gold_span | body.layer |  | – | around | ["밖"] |
| H27 | distorted/cross_slot | height | 어깨 옆 | {"range": [0.72, 0.9]} | – | [{"path": "body.part", "trigger": "어깨", "value": "shoulder"}, {"path": "body.layer", "trigger": "옆", "value": "around_side"}] |
| H27 | distorted/wrong_value | erosion | 조금씩 부서져 | {"range": [0.25, 0.7]} | 0.850 | ["부서져"] |
| H27 | preserved | texture_roughness | 녹슬어서 | {"range": [0.6, 1.0]} | – | [] |
| H27 | spurious | body.part |  | – | shoulder | ["어깨"] |
| H27 | spurious | body.layer |  | – | around_side | ["옆", "옆"] |
| H28 | distorted/wrong_value | brightness | 밝기는 중간쯤 | {"range": [0.35, 0.65]} | 0.700 | ["빛", "빛"] |
| H28 | lost | opacity | 흐릿한 | {"range": [0.0, 0.7]} | – | [] |
| H28 | spurious | layout.size |  | – | 0.316 | ["작았는데"] |
| H28 | spurious | motion.type |  | – | spreading | ["퍼진"] |
| H28 | spurious | body.part |  | – | head | ["머리"] |
| H28 | unsupported/outside_gold_span | material.brightness |  | – | 0.700 | ["빛", "빛"] |
| H28 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| H29 | preserved | form | 흙덩이 | {"in": ["blob"]} | – | [] |
| H29 | preserved | texture_roughness | 거칠거칠해요 | {"range": [0.6, 1.0]} | – | [] |
| H29 | spurious | body.part |  | – | body | ["몸"] |
| H29 | spurious | body.layer |  | – | around | ["밖"] |
| H30 | distorted/wrong_value | size | 손바닥만 하고 | {"range": [0.1, 0.45]} | 0.475 | ["손바닥만 하고"] |
| H30 | preserved | distance | 바로 앞이에요 | {"range": [0.0, 0.25]} | – | [] |
| H30 | spurious | material.brightness |  | – | 0.850 | ["반짝반짝"] |
| H30 | spurious | body.part |  | – | body | ["몸"] |
| H30 | spurious | body.layer |  | – | around | ["밖"] |
