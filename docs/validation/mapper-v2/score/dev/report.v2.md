# 일치도 채점 — imagery-dev · 매핑 v2

채점기 fidelity/0.3.0, 코퍼스 imagery-dev@1.0.0, 빌더 scene-spec-builder-v2/2.0.0

## 전체

| 지표 | 값 |
| --- | --- |
| attributes | 240 |
| slotAttributes | 206 |
| reflectRate | 0.937 |
| distortRate | 0.000 |
| lostRate | 0.000 |
| droppedRate | 0.063 |
| preserveRate | 0.942 |
| unreflectedVerbatimRate | 1.000 |
| unreflectedVerbatimRateWithClauseIndex | 1.000 |
| lostClauseIndexOnly | 0 |
| negated | 8 |
| negationErrors | 0 |
| contamination | 0 |
| contaminationDecisive | 0 |
| spuriousValues | 29 |
| unsupportedValues | 45 |
| fuzzyValues | 0 |
| valuesFilled | 226 |
| spuriousRate | 0.128 |
| unsupportedRate | 0.199 |

미반영 원문 보존률(unreflectedVerbatimRate)은 속성 단위 보존 필드만 인정한 값이다. 절 색인(_clauses)까지 인정한 값은 unreflectedVerbatimRateWithClauseIndex, 절 색인으로만 남은 손실은 lostClauseIndexOnly. fuzzyValues는 자모 퍼지 일치 근거로 슬롯에 들어간 값의 수(0이어야 한다).

슬롯 속성 상태: reflected 193, distorted 0, preserved 0, lost 0, dropped_by_controller 13
근거 없는 값(근거 기준) 사유: no_evidence 0, no_gold_span 35, outside_gold_span 10 · 그중 값은 정답 expect를 만족 12

## 신뢰구간(항목 단위 군집 부트스트랩, B = 10000, 시드 20261116, 항목 30개)

이 합성 코퍼스 안에서의 변동만 나타냅니다. 일반 성능의 증거가 아닙니다.

| 지표 | 추정 | 95% 구간 |
| --- | --- | --- |
| reflectRate | 0.937 | [0.888, 0.980] |
| distortRate | 0.000 | [0.000, 0.000] |
| lostRate | 0.000 | [0.000, 0.000] |
| droppedRate | 0.063 | [0.020, 0.112] |
| preserveRate | 0.942 | [0.896, 0.979] |
| unreflectedVerbatimRate | 1.000 | [1.000, 1.000] |
| unreflectedVerbatimRateWithClauseIndex | 1.000 | [1.000, 1.000] |
| spuriousRate | 0.128 | [0.084, 0.172] |
| unsupportedRate | 0.199 | [0.150, 0.247] |
| fuzzyValueRate | 0.000 | [0.000, 0.000] |

## 정답 구간 폭(kind = slot)

| expect 종류 | n | reflected | 반영률 |
| --- | --- | --- | --- |
| color_hue | 20 | 20 | 1.000 |
| color_sl | 8 | 8 | 1.000 |
| equals | 29 | 29 | 1.000 |
| equals_null | 4 | 1 | 0.250 |
| in | 54 | 53 | 0.982 |
| range | 91 | 82 | 0.901 |

| 폭 | n | 최소 | 중앙값 | 평균 | 최대 |
| --- | --- | --- | --- | --- | --- |
| range 폭 | 91 | 0.080 | 0.350 | 0.331 | 0.600 |
| hue 폭(도) | 20 | 25.000 | 30.000 | 37.750 | 70.000 |
| s 폭 | 28 | 0.200 | 0.550 | 0.504 | 0.800 |
| l 폭 | 28 | 0.170 | 0.300 | 0.311 | 0.400 |
| in 목록 길이 | 54 | 1.000 | 2.000 | 2.111 | 5.000 |

range 폭 중앙값 0.350 이하: 반영률 0.924 (n 53) · 초과: 반영률 0.868 (n 38)

layout.size 정답 구간 폭을 v1 크기 척도(1단위 = 6.000옥타브)로 환산: n 27 · 최소 1.500옥타브(×2.830) · 중앙값 2.100옥타브(×4.290) · 최대 2.700옥타브(×6.500). 구간 안이면 반영으로 세므로, 이 배율만큼 다른 크기도 반영될 수 있다.

## 속성 유형별

| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| body_layer | 22 | 22 | 22 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| body_part | 19 | 19 | 19 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| brightness | 12 | 10 | 7 | 0 | 1 | 0 | 4 | 0 | 0.700 |
| color | 30 | 29 | 28 | 0 | 1 | 0 | 1 | 0 | 0.966 |
| distance | 6 | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| erosion | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| form | 13 | 13 | 13 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| height | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| motion_speed | 14 | 14 | 13 | 0 | 0 | 0 | 1 | 0 | 0.929 |
| motion_type | 30 | 28 | 26 | 0 | 1 | 0 | 2 | 1 | 0.929 |
| opacity | 7 | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| other | 7 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | – |
| posture | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| saturation | 3 | 3 | 2 | 0 | 0 | 0 | 1 | 0 | 0.667 |
| shape | 10 | 0 | 0 | 0 | 10 | 0 | 0 | 0 | – |
| size | 29 | 28 | 23 | 0 | 1 | 0 | 5 | 0 | 0.821 |
| smell | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| sound | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | – |
| temperature | 5 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | – |
| texture_roughness | 14 | 14 | 14 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| weight | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |

## 항목별

| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값(경로) | 근거 없는 값(근거) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D01 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| D02 | 8 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 2 |
| D03 | 8 | 0.625 | 0.000 | 0.625 | 0 | 0 | 2 | 4 |
| D04 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| D05 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 3 | 3 |
| D06 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| D07 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| D08 | 8 | 0.625 | 0.000 | 0.625 | 0 | 0 | 0 | 1 |
| D09 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| D10 | 8 | 1.000 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| D11 | 8 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| D12 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| D13 | 8 | 0.875 | 0.000 | 0.875 | 0 | 0 | 0 | 1 |
| D14 | 3 | 1.000 | 0.000 | 1.000 | 0 | 0 | 2 | 3 |
| D15 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| D16 | 8 | 1.000 | 0.000 | 1.000 | 0 | 0 | 2 | 3 |
| D17 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| D18 | 8 | 0.750 | 0.000 | 0.750 | 0 | 0 | 2 | 3 |
| D19 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| D20 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| D21 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 3 | 3 |
| D22 | 7 | 0.857 | 0.000 | 0.875 | 0 | 0 | 0 | 1 |
| D23 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 2 | 3 |
| D24 | 8 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| D25 | 7 | 0.857 | 0.000 | 0.750 | 0 | 0 | 1 | 1 |
| D26 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 2 | 2 |
| D27 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| D28 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 3 | 3 |
| D29 | 5 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| D30 | 6 | 0.667 | 0.000 | 0.750 | 0 | 0 | 2 | 3 |

## 실패 사례

| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| D02 | unsupported/outside_gold_span | form.type |  | – | mist | ["안개"] |
| D02 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변", "주변"] |
| D03 | dropped_by_controller | size | 한 30센티 정도요 | {"range": [0.25, 0.7]} | – | – |
| D03 | dropped_by_controller | motion_type | 아주 천천히 돌아요 | {"in": ["rotating", "circling"]} | – | – |
| D03 | dropped_by_controller | motion_speed | 아주 천천히 | {"range": [0.0, 0.25]} | – | – |
| D03 | spurious | body.part |  | – | body | ["몸"] |
| D03 | spurious | body.layer |  | – | around | ["주변"] |
| D03 | unsupported/no_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| D03 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠"] |
| D05 | spurious | form.type |  | – | blob | ["공"] |
| D05 | spurious | material.brightness |  | – | 0.850 | ["반짝반짝"] |
| D05 | spurious | body.part |  | – | body | ["몸"] |
| D06 | spurious | body.part |  | – | head | ["머리"] |
| D07 | spurious | form.type |  | – | blob | ["돌멩이 같"] |
| D08 | dropped_by_controller | size | 하나하나는 손톱만 해요 | {"range": [0.0, 0.4]} | – | – |
| D08 | dropped_by_controller | color | 어떤 색인지 모르겠어요 | {"equals": null} | – | – |
| D08 | dropped_by_controller | brightness | 빛이 좀 나요 | {"range": [0.5, 0.9]} | – | – |
| D08 | unsupported/no_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| D09 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| D10 | spurious | material.opacity |  | – | 0.500 | ["비쳐요"] |
| D11 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| D12 | spurious | body.part |  | – | body | ["몸"] |
| D13 | dropped_by_controller | size | 모래알처럼 아주 작아요 | {"range": [0.0, 0.25]} | – | – |
| D13 | unsupported/no_gold_span | layout.size |  | – | 0.316 | ["작은"] |
| D14 | spurious | motion.type |  | – | spreading | ["퍼져"] |
| D14 | spurious | body.part |  | – | body | ["몸", "몸"] |
| D14 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변", "주변"] |
| D16 | spurious | form.type |  | – | blob | ["보라색 구슬 같"] |
| D16 | spurious | motion.speed |  | – | 0.250 | ["천천히"] |
| D16 | unsupported/outside_gold_span | body.part |  | – | head | ["머리"] |
| D17 | spurious | form.type |  | – | blob | ["보라색 풍선같"] |
| D18 | dropped_by_controller | size | 제 키보다 커요 | {"range": [0.75, 1.0]} | – | – |
| D18 | dropped_by_controller | brightness | 어두운 편이에요 | {"range": [0.1, 0.4]} | – | – |
| D18 | spurious | body.part |  | – | body | ["몸", "몸"] |
| D18 | spurious | body.layer |  | – | around | ["주변", "주변"] |
| D18 | unsupported/no_gold_span | layout.size |  | – | 0.646 | ["커다란"] |
| D20 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| D21 | spurious | material.brightness |  | – | 0.400 | ["뿌연", "뿌연"] |
| D21 | spurious | body.part |  | – | body | ["몸", "몸"] |
| D21 | spurious | body.layer |  | – | around | ["주변"] |
| D22 | dropped_by_controller | size | 크기는 잘 모르겠어요 | {"equals": null} | – | – |
| D22 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| D23 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| D23 | spurious | body.part |  | – | body | ["몸"] |
| D23 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| D24 | unsupported/outside_gold_span | body.layer |  | – | around | ["주변"] |
| D25 | dropped_by_controller | saturation | 칙칙해요 | {"range": [0.0, 0.4]} | – | – |
| D25 | spurious | body.layer |  | – | surface | ["표면"] |
| D26 | spurious | form.type |  | – | blob | ["공"] |
| D26 | spurious | body.layer |  | – | surface | ["표면"] |
| D28 | spurious | material.roughness |  | – | 0.250 | ["촉촉하고"] |
| D28 | spurious | body.part |  | – | body | ["몸"] |
| D28 | spurious | body.layer |  | – | around | ["주변"] |
| D30 | dropped_by_controller | brightness | 은은한 정도 | {"range": [0.3, 0.65]} | – | – |
| D30 | dropped_by_controller | motion_type | 움직이는지는 잘 모르겠어요 | {"equals": null} | – | – |
| D30 | spurious | body.part |  | – | body | ["몸"] |
| D30 | spurious | body.layer |  | – | around | ["주변"] |
| D30 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠"] |
