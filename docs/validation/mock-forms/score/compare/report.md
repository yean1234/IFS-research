# 일치도 채점 — imagery-mock-forms · 매핑 v1

채점기 fidelity/0.3.0, 코퍼스 imagery-mock-forms@0.1.0, 빌더 scene-spec-builder-v1/1.2.0

## 전체

| 지표 | 값 |
| --- | --- |
| attributes | 258 |
| slotAttributes | 200 |
| reflectRate | 0.765 |
| distortRate | 0.060 |
| lostRate | 0.010 |
| droppedRate | 0.070 |
| preserveRate | 0.872 |
| unreflectedVerbatimRate | 0.767 |
| unreflectedVerbatimRateWithClauseIndex | 1.000 |
| lostClauseIndexOnly | 6 |
| negated | 1 |
| negationErrors | 0 |
| contamination | 0 |
| contaminationDecisive | 0 |
| spuriousValues | 26 |
| unsupportedValues | 49 |
| fuzzyValues | 0 |
| valuesFilled | 192 |
| spuriousRate | 0.135 |
| unsupportedRate | 0.255 |

미반영 원문 보존률(unreflectedVerbatimRate)은 속성 단위 보존 필드만 인정한 값이다. 절 색인(_clauses)까지 인정한 값은 unreflectedVerbatimRateWithClauseIndex, 절 색인으로만 남은 손실은 lostClauseIndexOnly. fuzzyValues는 자모 퍼지 일치 근거로 슬롯에 들어간 값의 수(0이어야 한다).

슬롯 속성 상태: reflected 153, distorted 12, preserved 19, lost 2, dropped_by_controller 14
근거 없는 값(근거 기준) 사유: no_evidence 0, no_gold_span 31, outside_gold_span 18 · 그중 값은 정답 expect를 만족 14

## 신뢰구간(항목 단위 군집 부트스트랩, B = 10000, 시드 20261116, 항목 36개)

이 합성 코퍼스 안에서의 변동만 나타냅니다. 일반 성능의 증거가 아닙니다.

| 지표 | 추정 | 95% 구간 |
| --- | --- | --- |
| reflectRate | 0.765 | [0.714, 0.814] |
| distortRate | 0.060 | [0.031, 0.092] |
| lostRate | 0.010 | [0.000, 0.025] |
| droppedRate | 0.070 | [0.030, 0.117] |
| preserveRate | 0.872 | [0.818, 0.920] |
| unreflectedVerbatimRate | 0.767 | [0.663, 0.863] |
| unreflectedVerbatimRateWithClauseIndex | 1.000 | [1.000, 1.000] |
| spuriousRate | 0.135 | [0.088, 0.182] |
| unsupportedRate | 0.255 | [0.199, 0.310] |
| fuzzyValueRate | 0.000 | [0.000, 0.000] |

## 정답 구간 폭(kind = slot)

| expect 종류 | n | reflected | 반영률 |
| --- | --- | --- | --- |
| color_hue | 15 | 14 | 0.933 |
| color_sl | 12 | 12 | 1.000 |
| equals | 42 | 42 | 1.000 |
| equals_null | 12 | 7 | 0.583 |
| in | 59 | 44 | 0.746 |
| range | 60 | 34 | 0.567 |

| 폭 | n | 최소 | 중앙값 | 평균 | 최대 |
| --- | --- | --- | --- | --- | --- |
| range 폭 | 60 | 0.080 | 0.350 | 0.350 | 0.550 |
| hue 폭(도) | 15 | 25.000 | 30.000 | 38.533 | 90.000 |
| s 폭 | 23 | 0.150 | 0.500 | 0.455 | 0.750 |
| l 폭 | 27 | 0.200 | 0.350 | 0.327 | 0.450 |
| in 목록 길이 | 59 | 1.000 | 2.000 | 2.000 | 5.000 |

range 폭 중앙값 0.350 이하: 반영률 0.600 (n 30) · 초과: 반영률 0.533 (n 30)

layout.size 정답 구간 폭을 v1 크기 척도(1단위 = 6.000옥타브)로 환산: n 31 · 최소 1.200옥타브(×2.300) · 중앙값 2.100옥타브(×4.290) · 최대 2.700옥타브(×6.500). 구간 안이면 반영으로 세므로, 이 배율만큼 다른 크기도 반영될 수 있다.

## 속성 유형별

| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| body_layer | 35 | 35 | 35 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| body_part | 26 | 26 | 25 | 1 | 0 | 0 | 0 | 0 | 0.962 |
| brightness | 7 | 6 | 4 | 1 | 0 | 1 | 0 | 1 | 0.667 |
| color | 33 | 33 | 30 | 1 | 0 | 0 | 2 | 0 | 0.909 |
| color2 | 5 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | – |
| distance | 2 | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0.000 |
| erosion | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0.000 |
| feeling | 4 | 0 | 0 | 0 | 3 | 0 | 1 | 0 | – |
| figure | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| form | 13 | 13 | 12 | 0 | 1 | 0 | 0 | 0 | 0.923 |
| hardness | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | – |
| height | 3 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| hole | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | – |
| hollow | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| light | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| lines | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| liquid | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| motion_speed | 5 | 5 | 3 | 0 | 0 | 0 | 2 | 0 | 0.600 |
| motion_type | 36 | 27 | 13 | 1 | 10 | 4 | 8 | 0 | 0.481 |
| opacity | 10 | 7 | 5 | 1 | 1 | 0 | 0 | 3 | 0.714 |
| other | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| posture | 2 | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0.500 |
| shape | 6 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | – |
| sheet | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | – |
| size | 35 | 35 | 17 | 5 | 10 | 1 | 2 | 0 | 0.486 |
| softness | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| stickiness | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| temperature | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | – |
| texture_roughness | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 1.000 |
| weight | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| width | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |
| wrinkle | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | – |

## 항목별

| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값(경로) | 근거 없는 값(근거) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M01 | 8 | 0.625 | 0.125 | 0.625 | 0 | 0 | 1 | 3 |
| M02 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| M03 | 5 | 0.800 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| M04 | 7 | 0.857 | 0.143 | 0.875 | 0 | 0 | 0 | 0 |
| M05 | 7 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| M06 | 6 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| M07 | 5 | 0.800 | 0.000 | 0.857 | 0 | 0 | 0 | 2 |
| M08 | 7 | 0.857 | 0.143 | 0.857 | 0 | 0 | 0 | 1 |
| M09 | 6 | 0.500 | 0.333 | 0.500 | 0 | 0 | 2 | 3 |
| M10 | 6 | 0.833 | 0.000 | 1.000 | 0 | 0 | 2 | 2 |
| M11 | 7 | 0.714 | 0.000 | 0.750 | 0 | 0 | 1 | 2 |
| M12 | 7 | 0.714 | 0.143 | 0.714 | 0 | 0 | 2 | 3 |
| M13 | 6 | 0.667 | 0.167 | 0.833 | 0 | 0 | 1 | 2 |
| M14 | 7 | 0.857 | 0.000 | 1.000 | 0 | 0 | 3 | 3 |
| M15 | 5 | 0.800 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| M16 | 6 | 0.667 | 0.000 | 1.000 | 0 | 0 | 1 | 1 |
| M17 | 5 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 1 |
| M18 | 3 | 1.000 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| M19 | 6 | 0.833 | 0.167 | 0.750 | 0 | 0 | 0 | 1 |
| M20 | 5 | 0.600 | 0.000 | 0.857 | 0 | 0 | 0 | 1 |
| M21 | 5 | 0.800 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| M22 | 4 | 0.500 | 0.250 | 0.571 | 0 | 0 | 2 | 4 |
| M23 | 6 | 0.833 | 0.000 | 1.000 | 0 | 0 | 3 | 3 |
| M24 | 6 | 0.833 | 0.000 | 0.889 | 0 | 0 | 1 | 3 |
| M25 | 5 | 0.800 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| M26 | 5 | 0.600 | 0.200 | 0.875 | 0 | 0 | 0 | 1 |
| M27 | 7 | 0.714 | 0.000 | 0.889 | 0 | 0 | 2 | 2 |
| M28 | 5 | 0.600 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |
| M29 | 4 | 1.000 | 0.000 | 0.833 | 0 | 0 | 0 | 0 |
| M30 | 5 | 0.800 | 0.000 | 1.000 | 0 | 0 | 2 | 3 |
| M31 | 5 | 0.600 | 0.200 | 0.875 | 0 | 0 | 0 | 1 |
| M32 | 4 | 0.750 | 0.250 | 0.857 | 0 | 0 | 1 | 2 |
| M33 | 3 | 0.000 | 0.000 | 0.000 | 0 | 0 | 0 | 0 |
| M34 | 5 | 0.800 | 0.000 | 0.833 | 0 | 0 | 0 | 0 |
| M35 | 5 | 0.600 | 0.000 | 0.714 | 0 | 0 | 1 | 2 |
| M36 | 5 | 0.800 | 0.000 | 1.000 | 0 | 0 | 0 | 0 |

## 실패 사례

| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |
| --- | --- | --- | --- | --- | --- | --- |
| M01 | distorted/wrong_value | size | 방을 채울 만큼 | {"range": [0.75, 1.0]} | 0.621 | ["넓게"] |
| M01 | dropped_by_controller | motion_type | 이리저리 떠다녀요 | {"in": ["floating", "drifting"]} | – | – |
| M01 | dropped_by_controller | motion_speed | 천천히 | {"range": [0.0, 0.4]} | – | – |
| M01 | spurious | material.brightness |  | – | 0.400 | ["뿌옇게"] |
| M01 | unsupported/outside_gold_span | layout.size |  | – | 0.621 | ["넓게"] |
| M01 | unsupported/no_gold_span | motion.type |  | – | spreading | ["퍼져"] |
| M03 | preserved | form | 구름이에요 | {"in": ["mist"]} | – | [] |
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
| M10 | preserved | erosion | 군데군데 금이 가 있어요 | {"range": [0.15, 0.7]} | – | [] |
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
| M13 | preserved | size | 깨알만 해요 | {"range": [0.0, 0.2]} | – | [] |
| M13 | spurious | layout.distance |  | – | 0.600 | ["떨어져요"] |
| M13 | unsupported/outside_gold_span | form.type |  | – | fragments | ["부스러기", "알갱이"] |
| M14 | preserved | distance | 한두 걸음 앞에 | {"range": [0.2, 0.55]} | – | [] |
| M14 | spurious | form.type |  | – | blob | ["공"] |
| M14 | spurious | motion.speed |  | – | 0.250 | ["천천히"] |
| M14 | spurious | body.part |  | – | belly | ["배"] |
| M15 | preserved | size | 신발 상자만 해요 | {"range": [0.25, 0.65]} | – | [] |
| M15 | spurious | layout.distance |  | – | 0.000 | ["붙어"] |
| M16 | preserved | size | 9 cm쯤 | {"range": [0.03, 0.4]} | – | [] |
| M16 | preserved | motion_type | 그대로 놓여 있어요 | {"in": ["still"]} | – | [] |
| M16 | spurious | form.type |  | – | blob | ["돌처럼"] |
| M17 | unsupported/outside_gold_span | body.part |  | – | throat_neck | ["목"] |
| M19 | distorted/wrong_value | brightness | 희미하게 빛나요 | {"range": [0.4, 0.75]} | 0.250 | ["희미하게"] |
| M19 | lost | motion_type | 아래로 천천히 흘러내려요 | – | – | – |
| M19 | unsupported/outside_gold_span | body.part |  | – | back | ["등"] |
| M20 | preserved | size | A4 종이 한 장 | {"range": [0.25, 0.65]} | – | [] |
| M20 | dropped_by_controller | motion_type | 팔랑거려요 | {"in": ["swaying", "rippling", "floating"]} | – | – |
| M20 | unsupported/no_gold_span | motion.type |  | – | floating | ["떠"] |
| M21 | preserved | size | 상체를 다 덮을 정도요 | {"range": [0.5, 0.85]} | – | [] |
| M22 | dropped_by_controller | color | 색은 딱히 없어요 | {"equals": null} | – | – |
| M22 | lost | motion_type | 떨어질 듯 말 듯 매달려 있어요 | – | – | – |
| M22 | distorted/wrong_value | body_part | 눈 뒤쪽 | {"in": ["head", "face"]} | body | ["몸"] |
| M22 | spurious | form.posture |  | – | hanging | ["매달려"] |
| M22 | spurious | layout.distance |  | – | 0.600 | ["떨어질"] |
| M22 | unsupported/outside_gold_span | layout.size |  | – | 0.000 | ["1센티쯤"] |
| M22 | unsupported/outside_gold_span | body.part |  | – | body | ["몸"] |
| M23 | preserved | opacity | 바닥이 안 보여요 | {"range": [0.7, 1.0]} | – | [] |
| M23 | spurious | form.posture |  | – | standing | ["서"] |
| M23 | spurious | material.saturation |  | – | 0.250 | ["탁한"] |
| M23 | spurious | body.part |  | – | foot | ["발", "발"] |
| M24 | lost | motion_type | 천천히 흘러내리는데 | – | – | – |
| M24 | preserved | size | 양은 한 컵쯤이요 | {"range": [0.05, 0.45]} | – | [] |
| M24 | spurious | material.brightness |  | – | 0.700 | ["빛"] |
| M24 | unsupported/outside_gold_span | material.roughness |  | – | 0.300 | ["끈적끈적해요"] |
| M24 | unsupported/outside_gold_span | motion.type |  | – | sinking | ["내려가요", "내려가고"] |
| M25 | preserved | motion_type | 콩닥콩닥 뛰듯이 | {"in": ["pounding"]} | – | [] |
| M26 | distorted/wrong_value | color | 주황색이에요 | {"hue_deg": [15, 45], "s": [0.5, 1.0], "l": [0.35, 0.7]} | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파랗고"] |
| M26 | preserved | size | 손가락 한 마디만 해요 | {"range": [0.0, 0.25]} | – | [] |
| M26 | unsupported/outside_gold_span | material.color |  | – | {"hue_deg": 214.9, "s": 0.7, "l": 0.5} | ["파랗고"] |
| M27 | lost | brightness | 눈이 부실 만큼 밝은 | {"range": [0.8, 1.0]} | – | [] |
| M27 | preserved | size | 냄비 뚜껑만 하고 | {"range": [0.3, 0.65]} | – | [] |
| M27 | spurious | layout.distance |  | – | 0.000 | ["한 뼘쯤"] |
| M27 | spurious | body.part |  | – | head | ["머리"] |
| M28 | preserved | size | 도넛 하나 크기요 | {"range": [0.05, 0.45]} | – | [] |
| M28 | preserved | motion_type | 그대로예요 | {"in": ["still"]} | – | [] |
| M29 | lost | motion_type | 넓어졌다 좁아졌다 해요 | – | – | – |
| M30 | preserved | motion_type | 살짝 몸을 흔들어요 | {"in": ["swaying"]} | – | [] |
| M30 | spurious | layout.verticalOffset |  | – | 0.280 | ["무릎 높이"] |
| M30 | spurious | body.part |  | – | leg | ["무릎"] |
| M30 | unsupported/outside_gold_span | form.posture |  | – | crouched | ["쪼그려"] |
| M31 | distorted/wrong_value | posture | 동그랗게 말려 있어요 | {"in": ["curled"]} | lying | ["누웠을"] |
| M31 | preserved | size | 보통 고양이만 해요 | {"range": [0.3, 0.6]} | – | [] |
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
| M36 | preserved | motion_type | 계속 들썩들썩해요 | {"in": ["vibrating", "trembling", "moving"]} | – | [] |
