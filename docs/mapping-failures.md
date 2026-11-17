# 규칙 기반 매핑(v0)의 실패 사례 — dev 코퍼스

작업 3 전반부 기록입니다. 현 화이트박스 매핑(`scene-spec-builder/0.1.0`)이 참여자 표현을 놓치거나 왜곡하는 경우를 찾아 유형별로 셉니다. 개선 매핑은 이 문서의 유형과 수치를 기준선으로 삼습니다.

- 대상 코퍼스: `chatbot/tests/fixtures/imagery_corpus/dev.json` (합성 30개, 다회 응답 18 · 자유 서술 12). 정답 속성 240개, 그중 슬롯 속성 206개. 문장과 정답 라벨은 같은 AI 에이전트(`authoredBy: agent:dev-writer`)가 썼습니다. 사람 라벨이 아닙니다.
- held-out 코퍼스(`heldout.json`)는 열지 않았습니다. 매핑을 고칠 때 보지 않은 문장이어야 하기 때문입니다(AC-3). 이 문서의 수치는 **개선 방향을 정하는 데만** 씁니다. 논문 보고 수치가 아닙니다.
- 입력 경로: 코퍼스의 답을 **실제 컨트롤러의 정적 조건(조건 1)** 에 순서대로 넣었습니다. 안전 검사, 프로브 건너뛰기, 확정 텍스트 조립, 장면 파일 쓰기를 실제 코드 그대로 거칩니다.
- 사전 버전: `layer1_lexicon.v0.json`(379항목), `scene_params.v0.json`, `vad_ko.v0.json`. 형태소 분석기 Kiwi.

## 1. 실행 방법

저장소의 `chatbot` 폴더에서 PowerShell로 실행합니다.

```powershell
cd chatbot
# 재생 + 채점 + 리포트 (runs.json, report.json, report.md)
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\dev.json --mapper v0 --out <결과 폴더>
# 정답 라벨 형식 검사만 (phrase 원문은 출력하지 않음, 오류가 있으면 종료 코드 1)
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --check-corpus tests\fixtures\imagery_corpus\dev.json
# 두 매핑 비교 (A 결과는 <폴더>, B 결과는 <폴더>\compare, 항목 단위 쌍 비교는 <폴더>\paired.json · paired.md)
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\dev.json --mapper v0 --compare <모듈:factory> --out <결과 폴더>
# 재생만 (확정 텍스트 · SceneSpec · 컨트롤러 기록)
.venv\Scripts\python.exe -m ifs_chatbot.eval.corpus_run --corpus tests\fixtures\imagery_corpus\dev.json --out <파일>.json
# 채점 규칙 단위 테스트
.venv\Scripts\python.exe -m pytest -q tests\test_eval_fidelity.py
```

- 세션 로그와 장면 파일은 임시 폴더에 쓰고 끝나면 지웁니다. `chatbot/logs`는 건드리지 않습니다.
- 개선 매핑은 `--mapper 모듈:factory`로 바꿔 끼웁니다. `factory(rt)`는 `build(text, *, session_id, participant_id, condition)`를 가진 객체를 돌려줘야 합니다. 컨트롤러의 `rt.scene_builder` 자리에 들어가므로 v0와 같은 경로(`Session._write_scene`)를 지납니다.
- 같은 입력이면 `runs.json` · `report.json` · `report.md`가 바이트까지 같습니다(두 번 실행해 `cmp`로 확인).
- 소요 시간: 30개 항목 약 2초.

## 2. 채점 정의

정본은 `chatbot/ifs_chatbot/eval/fidelity.py`의 모듈 설명입니다. 이 절은 그 요약입니다.

### 2.1 정답 속성의 종류

| 종류 | 조건 | 가능한 상태 |
| --- | --- | --- |
| slot | slot ≠ null, negated = false, expect ≠ null | reflected / distorted / preserved / lost / dropped_by_controller |
| slot_unscored | slot ≠ null, negated = false, expect = null | captured / preserved / lost / dropped_by_controller |
| negated | negated = true | preserved / lost / dropped_by_controller, 그리고 부정 오류 표시 |
| no_slot | slot = null (온도·무게·소리·모양 등) | preserved / lost / dropped_by_controller |

### 2.2 상태

| 상태 | 정의 |
| --- | --- |
| reflected | 슬롯 값이 expect를 만족합니다(equals · in · range · 색의 hue_deg/s/l). `{"equals": null}`은 값이 null일 때만 만족합니다. |
| distorted | 값이 있으나 expect를 만족하지 않습니다(`wrong_value`). 또는 값이 null인데 그 phrase가 다른 슬롯 P에 값을 만들었습니다(`cross_slot`). 단, P를 가진 정답 phrase가 그 근거를 덮거나 P의 값이 P의 정답을 만족하면 왜곡으로 치지 않습니다. |
| preserved | 값이 null이고, phrase의 공백 아닌 글자가 모두 보존 필드의 원문 근거로 덮입니다. 보존 필드는 `_provenance`를 뺀 `_`로 시작하는 최상위 키입니다. 근거마다 `charSpan`과, 그 구간의 원문과 글자까지 같은 `surface`·`trigger`·`text`·`phrase`가 있어야 합니다. |
| lost | 위 어디에도 해당하지 않습니다. |
| dropped_by_controller | phrase가 replies에는 있는데 확정 텍스트에 없습니다. 컨트롤러가 그 답을 쓰지 않은 경우입니다. |
| captured | (slot_unscored) phrase와 겹치는 근거로 그 슬롯에 값이 생겼습니다. 값 자체는 검사하지 않습니다. |

- phrase 위치: 정규화한 phrase를 확정 텍스트에서 찾은 모든 구간입니다. replies에도 없는 phrase는 코퍼스 오류(`phrase_missing`)로 집계에서 뺍니다. dev 코퍼스에서는 0건입니다.
- no_slot 보존은 보존 필드에 더해 `_provenance`도 인정합니다. 값의 근거로 원문이 남았기 때문입니다. negated는 보존 필드만 인정합니다. 값으로 쓰인 것은 오류이기 때문입니다.

### 2.3 지표

| 지표 | 식 |
| --- | --- |
| 반영률 | reflected / slot 수 |
| 왜곡률 | distorted / slot 수 |
| 손실률 · 컨트롤러 탈락률 | lost / slot 수 · dropped_by_controller / slot 수 |
| 보존률 | (reflected + captured + preserved) / 전체 속성 수. 모든 종류를 넣고 dropped도 분모에 넣습니다. |
| 미반영 원문 보존률 | reflected·captured·dropped가 아닌 속성 중 phrase가 보존 필드에 원문 그대로 남은 비율입니다. 상태와 무관하게 판정하므로 distorted도 포함합니다. AC-3.5의 대상입니다. |
| 배경 오염 | distractor 구간과 겹치는 `_provenance` 근거가 들어간 (distractor, 경로) 쌍의 수입니다. 그 근거가 값을 정한 첫 근거이면 "값 결정"으로 따로 셉니다. |
| 부정 오류 | negated phrase 구간과 겹치는 근거로 슬롯 값이 생긴 negated 속성의 수입니다. |
| 근거 없는 값 — 경로 기준(spurious) | 값이 있는 슬롯 중 그 항목 정답(부정 제외)에 그 경로가 없는 것 / 값이 있는 슬롯 수입니다. `docs/research-design.md` 4.4의 Spurious_c와 같은 정의입니다. |
| 근거 없는 값 — 근거 기준(unsupported) | 값이 있는 슬롯 중, 그 슬롯의 `_provenance` 구간 어느 것도 같은 항목에서 같은 경로를 가진 부정 아닌 정답 phrase의 확정 텍스트 구간과 겹치지 않는 것 / 값이 있는 슬롯 수입니다. 사유는 `no_evidence` · `no_gold_span`(정답이 없거나 phrase가 확정 텍스트에 없음) · `outside_gold_span`입니다. 경로 기준으로 잡힌 값은 모두 여기에도 잡힙니다. `docs/research-design.md` 4.4의 Unsupported_c입니다. |

허용 구간(expect)은 항목마다 코퍼스를 쓴 AI 에이전트가 정했습니다(사람 라벨 아님). 색 expect에서 키가 없거나 값이 null인 구성요소는 검사하지 않습니다. 정의가 문서와 다르면 스크립트가 정본입니다(AC-3).

신뢰구간은 **항목 단위 군집 부트스트랩**(항목을 복원 추출, 10,000회, 시드 20261116, 백분위 95%)입니다. 한 항목 안의 속성들은 독립이 아니므로 속성 단위로 재표집하지 않습니다. 30개 코퍼스의 구간은 이 코퍼스 안의 변동만 나타냅니다.

## 3. 집계 수치 (v0, dev 30개)

채점기 `fidelity/0.2.0`. 0.1.0과 비교해 기존 지표 값은 바뀌지 않았고, 근거 기준 근거 없는 값과 신뢰구간이 더해졌습니다.

| 지표 | 값 | 95% 구간(항목 군집 부트스트랩) |
| --- | --- | --- |
| 정답 속성 / 슬롯 속성 | 240 / 206 | |
| 슬롯 상태 | reflected 118 · distorted 34 · preserved 1 · lost 40 · dropped 13 | |
| **반영률** | **0.573** | 0.491–0.649 |
| **왜곡률** | **0.165** | 0.112–0.224 |
| 손실률 | 0.194 | 0.148–0.244 |
| 컨트롤러 탈락률 | 0.063 | 0.020–0.112 |
| **보존률** | **0.529** | 0.454–0.604 |
| 미반영 원문 보존률 | 0.130 (108개 중) | 0.078–0.187 |
| 부정 오류 | 1 / 8 | |
| 배경 오염 | 8 (8건 모두 값 결정) | |
| 근거 없는 값 — 경로 기준 | 54 / 206 = 0.262 | 0.224–0.302 |
| 근거 없는 값 — 근거 기준 | 98 / 206 = 0.476 | 0.412–0.539 |

근거 기준 98건의 사유: `no_gold_span` 62(그중 54건은 경로 기준과 같은 값, 8건은 정답 경로는 있으나 그 phrase가 확정 텍스트에 없음 — 컨트롤러가 버린 프로브 답 등), `outside_gold_span` 36, `no_evidence` 0. 98건 중 20건은 근거가 정답 구간 밖이지만 값은 그 경로의 정답 expect를 만족합니다. 예: D02 "안개 같은 게"가 정답 phrase인데 값의 근거는 뒤 문장의 "잿빛 안개가"의 '안개'입니다. 같은 속성을 두 번 말했는데 정답이 한 언급만 표시한 경우라, 라벨 누락인지 사람이 확인해야 합니다.

정답 구간 폭(kind = slot, 206개):

| expect 종류 | n | reflected | 반영률 |
| --- | --- | --- | --- |
| range | 91 | 41 | 0.451 |
| in | 54 | 40 | 0.741 |
| equals(값) | 29 | 23 | 0.793 |
| 색(hue 포함) | 20 | 8 | 0.400 |
| 색(s·l만, 무채색) | 8 | 6 | 0.750 |
| equals null('모르겠다') | 4 | 0 | 0.000 |

- range 폭: 중앙값 0.35(최소 0.08, 최대 0.60). 폭이 중앙값 이하인 53개의 반영률 0.453, 초과인 38개는 0.447로 차이가 거의 없습니다.
- hue 폭: 중앙값 30°(25–70°). s 폭 중앙값 0.55, l 폭 중앙값 0.30. `in` 목록 길이 중앙값 2(1–5).
- 범주형(`in`·`equals`)의 반영률이 수치·색보다 높습니다. `in` 목록이 길수록 쉽게 맞으므로 범주형 반영률은 목록 길이와 함께 읽습니다.

응답 방식별:

| 방식 | 슬롯 수 | 반영률 | 왜곡률 | 손실률 | 탈락률 | 배경 오염 |
| --- | --- | --- | --- | --- | --- | --- |
| 다회 응답(multi_turn) | 130 | 0.569 | 0.146 | 0.177 | 0.100 | 1 |
| 자유 서술(free_narrative) | 76 | 0.579 | 0.197 | 0.224 | 0.000 | 7 |

자유 서술은 한 답에 맥락 사물과 형상이 섞여 있어 배경 오염과 왜곡이 많습니다. 다회 응답은 프로브 생략으로 답이 버려지는 탈락이 생깁니다.

속성 유형별:

| 속성 | n | 슬롯 n | reflected | distorted | preserved | lost | dropped | 반영률 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| body_part | 19 | 19 | 16 | 3 | 0 | 0 | 0 | 0.842 |
| motion_speed | 14 | 14 | 12 | 0 | 0 | 1 | 1 | 0.857 |
| body_layer | 22 | 22 | 17 | 4 | 0 | 1 | 0 | 0.773 |
| form | 13 | 13 | 9 | 1 | 0 | 3 | 0 | 0.692 |
| motion_type | 30 | 28 | 19 | 3 | 0 | 6 | 2 | 0.679 |
| posture | 3 | 3 | 2 | 1 | 0 | 0 | 0 | 0.667 |
| saturation | 3 | 3 | 2 | 0 | 0 | 0 | 1 | 0.667 |
| brightness | 12 | 10 | 5 | 2 | 0 | 1 | 4 | 0.500 |
| erosion | 2 | 2 | 1 | 0 | 0 | 1 | 0 | 0.500 |
| height | 8 | 8 | 4 | 1 | 0 | 3 | 0 | 0.500 |
| texture_roughness | 14 | 14 | 7 | 2 | 0 | 5 | 0 | 0.500 |
| color | 30 | 29 | 14 | 10 | 1 | 4 | 1 | 0.483 |
| opacity | 7 | 7 | 2 | 2 | 0 | 3 | 0 | 0.286 |
| size | 29 | 28 | 7 | 4 | 0 | 13 | 5 | 0.250 |
| distance | 6 | 6 | 1 | 2 | 0 | 3 | 0 | 0.167 |
| shape · other · temperature · weight · sound · smell (무슬롯) | 28 | 0 | – | – | 8 | 19 | 0 | – |

크기(0.250)와 거리(0.167)가 가장 낮습니다. 참여자가 크기·거리를 "주먹만 해요", "1미터쯤"처럼 비교 대상이나 수치로 말하기 때문입니다. 색은 놓침보다 왜곡(10)이 많습니다.

## 4. 실패 유형과 건수

슬롯 속성의 실패 88건(distorted 34 + lost 40 + preserved 1 + dropped 13)을 **주된 원인 하나**로 분류했습니다. 분류는 사람이 `report.json`의 근거(`valueTriggers`, `phraseEvidence`, `_alternatives`, `_unmatched`, `_unmapped`)를 보고 했습니다.

| 코드 | 유형 | 건수 | 상태 내역 |
| --- | --- | --- | --- |
| LEX | 사전 누락(색 이름·의태어 질감·움직임 동사·투명도 표현·신체 부위) | 22 | lost 17 · distorted 4 · preserved 1 |
| CMPSZ | 비교 크기·거리("주먹만 해요", "팔 길이만큼", "몸을 다 덮을 만큼") | 13 | lost 9 · distorted 4 |
| CTRL | 컨트롤러 단계에서 버려짐(프로브 생략 12, "모르겠어요" 답 제외 1) | 13 | dropped 13 |
| NUM | 수치·단위("1미터쯤", "2센티", "한 뼘") | 7 | lost 6 · distorted 1 |
| CMP | 복합어·형태소 분할("반투명" → 반+투명, "연보라색", "하얀색", "눈높이", "몸 안이요"의 '안') | 7 | distorted 4 · lost 3 |
| SCOPE | 수식 범위·배경 오염(맥락 사물의 색·자세가 형상 값이 됨) | 6 | distorted 6 |
| DEG | 정도·수식어 무시("연한", "짙은", "살짝", "조금") | 5 | distorted 5 |
| FIRST | 같은 슬롯에서 먼저 말한 값 우선(일반어 '몸'이 '어깨'를, '떠 있다'가 '떨리다'를 이김) | 4 | distorted 4 |
| SIM | 직유 원천 미등록("껍데기처럼", "공기 같은", "솜사탕같아요") | 3 | lost 3 |
| POLY | 다의어 교차 슬롯('빛' → 밝기, '가까운' → 거리, '짙다' → 채도) | 3 | distorted 2 · lost 1 |
| PART | 부분-전체 대조("겉은 A, 안쪽은 B", "테두리는 A, 안쪽은 B") | 2 | distorted 2 |
| UNC | 불확실 표현("안인지 표면인지 모르겠어요")을 다른 말이 덮음 | 1 | distorted 1 |
| NEG | 부정 범위("빛이 안 나고"의 '빛'이 값이 됨) | 1 | distorted 1 |
| CTX | 문맥 요건(신체 부위가 다른 줄에 있어 '안에요'를 버림) | 1 | lost 1 |
| | **합계** | **88** | |

슬롯 밖의 오류는 따로 셉니다.

| 오류 | 건수 | 내용 |
| --- | --- | --- |
| 부정 오류 | 1 | D12 "빛이 안 나고" → 밝기 0.7 |
| 배경 오염 | 8 | 파란 벽, 하얀 책상, 초록 잎들, 주변 화분, 빵집 앞, 가운데는 하얗게, 안쪽은 매끈해요, 누웠던 |
| 근거 없는 값(경로 기준) | 54 | verticalOffset 18 · body.part 11 · body.layer 8 · brightness 4 · saturation 3 · distance 3 · posture 2 · form.type 2 · 기타 3 |
| 근거 없는 값(근거 기준) | 98 | 경로 기준 54 + 44. 더해진 44건은 body.layer 11 · body.part 6 · layout.size 6 · motion.type 7 · color 5 · brightness 4 · 기타 5. 36건은 같은 경로의 정답은 있으나 값의 근거가 정답 구간 밖의 말(예: D05 맥락 사물의 '파란', D02 일반어 '몸', 같은 말의 다른 언급)인 경우이고, 8건은 정답 phrase가 확정 텍스트에서 빠진 경우입니다 |
| 무슬롯 속성 lost | 19 | 온도·무게·소리·냄새·모양. 낱말은 대부분 `_unmatched`·`_unmapped`에 있으나 구 전체가 원문 그대로 남지 않음 |

근거 없는 값 54건 중 29건(verticalOffset 18 + body.part 11)은 설계와 코퍼스 규칙이 다른 데서 나옵니다. 6절에 적었습니다.

## 5. 사례 표

"실제 JSON 값"은 v0 SceneSpec의 슬롯 값과 근거(trigger)입니다. 색은 hue를 도 단위로 적었습니다. 코드 위치는 이 문서를 쓴 시점(브랜치 `overnight/2026-11-16-imagery-fidelity`)의 줄 번호입니다.

| # | 항목 | 입력 원문 구간 | 기대 | 실제 JSON 값 | 유형 | 원인 코드 위치 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | D05 | "파란 벽 앞에 빨간 공이 하나 있는데" | color 빨강(hue 345–15°) | color = 파랑(214.9°, '파란'). '빨간'은 `_alternatives` | SCOPE | `scene_builder.py:264` `_merge`(같은 층은 먼저 말한 값). 관형어가 꾸미는 명사를 보지 않음 |
| 2 | D12 | "하얀 책상 위에 초록색 유리병이 하나 서 있어요" | color 초록(90–160°) | color = 흰색(l 0.95, '하얀'). body.layer = surface_above('책상 위'의 '위') | SCOPE | 같음 + `scene_params.v0.json` body_layer |
| 3 | D23 | "초록 잎들 사이에 하얀 꽃 한 송이가" | color 흰색(s ≤ 0.25, l ≥ 0.8) | color = 초록(119.9°, '초록') | SCOPE | `scene_builder.py:264` |
| 4 | D14 | "빵집 앞을 지나가던 게 … 저를 둥글게 감싸고" | body.layer around | around_front('빵집 앞'의 '앞') | SCOPE | `scene_builder.py:264`, 회상 문장과 형상 문장을 구분하지 않음(`scene_builder.py:91`) |
| 5 | D12 | "회의실에 앉아 있던 장면이요 … 하나 서 있어요" | posture standing | posture = sitting('앉아'). standing은 `_alternatives` | SCOPE | `scene_builder.py:91–128`(문장 역할 구분 없음) |
| 6 | D26 | "집에 와서 누웠던 장면이요" | 값 없음(맥락) | posture = lying('누웠던') | 배경 오염 | 같음 |
| 7 | D30 | "금색 테두리가 있고 안쪽은 어두운 초록이에요" | color 어두운 초록(l ≤ 0.35) | color = 금색(45°). 초록은 `_alternatives`. brightness = 0.15('어두운') | PART | `scene_builder.py:264`. 부분 표지('테두리', '안쪽') 규칙 없음 |
| 8 | D15 | "겉은 울퉁불퉁한데 안쪽은 매끈해요" | roughness ≥ 0.6 | roughness = 0.1('매끈해요'). '울퉁불퉁'은 `_unmapped`(shape, no_scene_param) | PART | `layer1_lexicon.v0.json` '울퉁불퉁' 범주가 shape. `scene_params.v0.json` layer1에 shape 없음 |
| 9 | D20 | "색은 따뜻한 귤색이고, 가운데는 하얗게 밝고" | color 주황(20–45°) | color = 흰색('하얗게'). '귤'은 `_unmatched` | LEX | `layer1_lexicon.v0.json`에 귤색 없음 |
| 10 | D14 · D15 · D21 | "크림색", "베이지색", "청록색" | 각 색 구간 | color null. 낱말은 `_unmatched` | LEX | `layer1_lexicon.v0.json` 색 이름 부족 |
| 11 | D07 · D18 · D17 · D25 | "오돌토돌해요", "까끌까끌해요", "반질반질해요", "바삭바삭해요" | roughness 구간 | null. `_unmatched` | LEX | `layer1_lexicon.v0.json` 의태어 질감 없음 |
| 12 | D21 · D22 · D29 · D23 | "소용돌이쳐요", "펄럭여요", "살랑거려요", "피어나듯 벌어지고" | motion.type 구간 | null. `_unmatched` | LEX | `layer1_lexicon.v0.json` 움직임 동사 부족 |
| 13 | D02 · D16 | "속이 살짝 비치는 정도로 옅고", "속이 조금 비쳐요" | opacity 0.2–0.85 | null. '비치'·'옅'은 `_unmatched` | LEX | `layer1_lexicon.v0.json` 투명도 표현 부족 |
| 14 | D25 | "왼손 손등이요" | body.part hand | body('몸'). '손등'은 `_unmatched` | LEX | `layer1_lexicon.v0.json`에 손등 없음 |
| 15 | D01 | "주먹만 해요" | size 0.05–0.5 | null. '주먹'은 `_unmatched` | CMPSZ | `scene_builder.py:174` `_map`. 크기어만 logScale로 바꾸고 'N만 하다' 규칙이 없음 |
| 16 | D05 · D06 · D07 · D26 · D30 | "농구공만 하고", "수박만한데", "달걀만 하고", "볼링공만 한", "접시만 해요" | size 구간 | null | CMPSZ | 같음. 참조 사물 크기표 없음 |
| 17 | D02 | "제 몸을 다 덮을 만큼 커요" | size 0.65–1.0 | 0.621('커요', logScale(1.4)) | CMPSZ | `scene_builder.py:174` `_map`. 크기어마다 고정값 |
| 18 | D17 | "크기는 사람 머리만하고" | size 0.35–0.65 | size null. body.part = head, verticalOffset = 0.93('머리') | CMPSZ + 교차 슬롯 | `scene_params.v0.json` body_part → body.part · layout.verticalOffset |
| 19 | D12 | "제 팔 길이만큼 떨어져" | distance 0.05–0.3 | 0.6('떨어져' = apart 고정) | CMPSZ | `scene_params.v0.json` distance.values.apart |
| 20 | D16 | "구슬만큼 작아요. 한 2센티쯤?" | size 0–0.3 | 0.316('작아요') | NUM | 단위 파서 없음. '쯤'은 `_unmatched` |
| 21 | D03 · D20 · D28 | "1미터쯤 앞에", "30센티쯤에", "2미터쯤" | distance 구간 | null. '미터'는 `_unmatched` | NUM | 같음 |
| 22 | D11 · D24 | "지름이 한 1미터쯤", "지름이 한 50센티 정도" | size 구간 | null | NUM | 같음 |
| 23 | D04 | "반투명한 덩어리" | opacity 0.2–0.7 | 0.1('투명'). '반'은 `_unmatched` | CMP | `lexicon.py:129–135` 접두사 결합이 부정 접두사(불·무·비·미)만 처리. '반투명' 항목은 있으나 닿지 않음 |
| 24 | D17 | "연보라색 풍선같은게" | color l 0.6–0.9 | 보라(275°, l 0.45) | CMP | 같음. 접두사 '연-'(밝게) 규칙 없음 |
| 25 | D04 | "연두빛이 도는" | color 연두(70–120°) | color null. brightness = 0.7('빛') | CMP + 교차 슬롯 | '연두' 사전 없음. '빛'이 brightness 항목 |
| 26 | D22 | "하얀색인데 약간 누르스름해요" | color 흰~크림 | null. '하얀색'·'누르스름'이 `_unmatched` | CMP | Kiwi가 '하얀색'을 한 명사로 냄. 사전 alt에 없음(`lexicon.py:100` `_candidates`). '노란색'도 문장 첫머리에서 같은 현상(단위 테스트 작성 중 확인) |
| 27 | D03 · D30 | "눈높이에 있어요" | verticalOffset 0.85–1.0 | null. '눈'·'높이'가 `_unmatched` | CMP | 사전 없음, 합성어 분할 |
| 28 | D04 | "몸 안이요. 배꼽 바로 아래쯤이요." | body.layer inner | around_below('아래'). '안'은 `_unmatched` | CMP | Kiwi가 '안이요'의 '안'을 부사로 분석. 위치어 '안'이 매칭되지 않음 |
| 29 | D03 | "연한 갈색이고 조금 어두워요" | color l 0.4–0.75, brightness 0.2–0.48 | color l 0.3(갈색 기본값). '연한'은 saturation 0.25. brightness 0.15 | DEG | `scene_params.v0.json` saturation.pale, brightness.dark 고정값. 명도 보정 규칙 없음 |
| 30 | D18 | "짙은 회색이고" | color l 0.1–0.4 | 회색 l 0.45. '짙은'은 saturation 0.75 | DEG | 같음 |
| 31 | D30 | "표면은 살짝 거칠어요" | roughness 0.5–0.8 | 0.85(rough 고정) | DEG | `scene_params.v0.json` texture.rough. 정도 부사 무시 |
| 32 | D12 | "병 자체는 빛이 안 나고 좀 어둑해요" | brightness 0.15–0.45. '빛'은 부정 | brightness = 0.7('빛'). '어둑해요'(0.3)는 `_alternatives` | NEG | `lexicon.py:156–169` `_negated`. 앞 부정어 '안'은 바로 앞 토큰일 때만 봄. 주어+안+서술어 구조를 놓침 |
| 33 | D24 | "흰빛에 가까운 노란색" | color 연노랑(40–65°, l ≥ 0.65) | color null. distance = 0.25('가까운') | POLY | '가깝'이 distance 항목. '흰'·'노란색'은 `_unmatched` |
| 34 | D23 | "빛이 살짝 비쳐요" | opacity 0.4–0.9 | opacity null. brightness = 0.7('빛') | POLY | '빛' brightness, '비치' 사전 없음 |
| 35 | D21 | "뒤가 거의 안 보일 만큼 짙어요" | opacity 0.7–1.0 | opacity null. '짙어요'는 saturation(`_alternatives`) | POLY | '짙'이 saturation 항목만 있음 |
| 36 | D02 | "몸 주변에 안개 … 어깨 뒤쪽을 감싸고" | body.part shoulder | body('몸'). shoulder는 `_alternatives` | FIRST | `scene_builder.py:264`. 일반어가 구체어보다 먼저 나오면 이김 |
| 37 | D20 · D24 | "떠 있어요 … 미세하게 떨리고", "떠 있어요 … 빙빙 돌아요" | motion.type trembling / rotating | floating('떠'). 정답 값은 `_alternatives` | FIRST | 같음. 상태어('떠 있다')와 움직임 동사를 같은 층으로 봄 |
| 38 | D15 · D14 · D19 | "껍데기처럼", "공기 같은 게", "솜사탕같아요" | form shell / mist / blob·mist | null | SIM | `scene_params.v0.json` layer2.prototypes에 껍질은 있으나 껍데기·공기·솜사탕 없음 |
| 39 | D19 | "배에 뭐가 있어요" / "안에요" | body.layer inner | null. '안'은 `_unmapped`(no_body_part_context) | CTX | `scene_builder.py:112` bodyPartSameLine. 신체 부위가 앞 줄에 있음 |
| 40 | D08 | "몸 안인지 표면인지 잘 모르겠어요. 목 앞쪽이요." | body.layer null(모름) | around('목 근처'의 '근처') | UNC | '모르겠다' 표지 규칙 없음. 다른 줄의 위치어가 값을 채움 |
| 41 | D22 · D30 | "크기는 잘 모르겠어요.", "움직이는지는 잘 모르겠어요." | 값 null + 모름 기록 | 확정 텍스트에서 빠짐(D30은 프로브 생략) | CTRL | `controller.py:258–259` 짧은 '모르겠어요'를 `no_more`로 보고 확정 텍스트에서 뺌(`safety.py:79–87`) |
| 42 | D03 | (크기 프로브 답) "한 30센티 정도요." | size 0.25–0.7 | 프로브를 묻지 않아 확정 텍스트에 없음 | CTRL | `controller.py:387–401`. 첫 답의 '작은'이 size 범주를 덮어 프로브 생략 |
| 43 | D03 · D08 · D18 · D25 · D30 | 움직임·색 프로브 답("아주 천천히 돌아요", "빛이 좀 나요", "어두운 편이에요", "칙칙해요", "은은한 정도예요") | 각 슬롯 구간 | 묻지 않아 확정 텍스트에 없음 | CTRL | 같음. '떠 있어요'(movement)·'갈색'(color)처럼 범주 낱말 하나로 그 차원 전체를 생략 |
| 44 | D17 | "하나 떠있어요.크기는 사람 머리만하고" | 근거 구간은 한 어절 | motion.type 근거 trigger가 '떠있어요.크기는'(문장 경계를 넘음) | 어절 경계 | `lexicon.py:144` → `korean.py:211` `eojeol_at`이 공백만 경계로 봄 |
| 45 | D01 외 17개 | "가슴 쪽에", "어깨 뒤쪽", "머리 위" 등 신체 부위어 | 공간 높이어가 없으면 verticalOffset null(코퍼스 규칙 5) | 예: D01 verticalOffset 0.72('가슴') | 기준 불일치 | `scene_params.v0.json` body_part → layout.verticalOffset(설계 결정, 6절) |

## 6. 해석할 때 주의할 점

1. **verticalOffset과 body.part 'body'.** v0는 신체 부위어에서 높이를 만듭니다(`scene_params.v0.json`의 신체 비율 근사). 코퍼스 작성 규칙 5는 공간 높이어가 있을 때만 height를 정답으로 넣었습니다. 그래서 근거 없는 값 18건이 이 차이에서 나옵니다. "몸 주변이요"의 '몸'이 만드는 body.part = body 11건도 코퍼스가 정답으로 달지 않은 값입니다. 이 29건은 버그가 아니라 기준 차이일 수 있습니다. 어느 쪽을 따를지는 팀이 정합니다. 그 전까지 근거 없는 값은 "전체 54 / 기준 차이 제외 25"로 함께 보고합니다.
2. **컨트롤러 탈락은 재생 조건의 산물입니다.** 실제 면담에서 묻지 않은 프로브에는 참여자가 답하지 않습니다. 그래도 탈락 13건은 의미가 있습니다. 범주 낱말 하나("작은", "떠 있어요", "갈색")로 그 차원의 프로브를 통째로 생략하면 더 정밀한 정보를 받을 기회가 사라집니다. 매핑을 고쳐도 이 13건은 돌아오지 않습니다. 프로토콜(`shared/protocol/`)을 바꿔야 하므로 IRB 문구 규칙(AGENTS.md 7)과 팀 결정이 필요합니다.
3. **"모르겠어요"가 사라집니다.** 짧은 '모르겠어요' 답은 `no_more`로 분류되어 확정 텍스트에 들어가지 않습니다. 그 결과 SceneSpec에서 "말하지 않음"과 "모른다고 말함"이 둘 다 null이 됩니다. 채점은 `{"equals": null}`을 만족하지만, 원칙 2("비어 있는 슬롯은 비어 있다고 표시")의 취지와는 맞지 않습니다.
4. **cross_slot 판정은 정답 주석에 기댑니다.** 정답에 없는 슬롯(예: D16 "천천히 굴러요"의 speed)에 값을 만들면 왜곡으로 셉니다. 정답이 그 속성을 빠뜨린 경우도 왜곡으로 잡힐 수 있습니다. 해당 사례는 `report.json`의 `crossSlot`에 근거가 남으니 보고 전에 확인합니다.
5. **보존 판정은 엄격합니다.** 낱말 단위 `_unmatched`는 조사·어미를 남기지 않으므로 구 전체를 덮지 못합니다. 그래서 v0의 미반영 원문 보존률은 0.130입니다. 낱말 수준 포함률은 `coverageAny`로 따로 남겼습니다. 예: "크림색"은 0.667입니다('크림'은 남고 '색'은 빠짐).
6. dev 코퍼스는 30개입니다. 유형별 건수는 방향을 정하는 데만 씁니다.

## 7. 개선 방향 (화이트박스 한정)

AGENTS.md 원칙 1에 따라 장면 속성은 사전과 규칙으로만 정합니다. LLM 구조화 추출과 임베딩 유사도는 장면 속성 경로에 넣지 않습니다. 아래는 기대 효과(위 건수)가 큰 순서입니다. 모두 같은 확정 텍스트에 같은 결과를 냅니다.

| 순서 | 개선 | 겨냥 유형(건수) | 방법 |
| --- | --- | --- | --- |
| 1 | 원문 보존 필드 | AC-3.5, 미반영 전부 | 슬롯에 들어가지 못한 정답 후보 구간(내용어를 포함한 어절 묶음)을 `charSpan`과 함께 원문 그대로 남깁니다. 반영률은 그대로여도 보존률을 100%로 올리는 최소 조건입니다. |
| 2 | 비교 크기 · 수치 단위 | CMPSZ 13, NUM 7 | "N만 하다 / N만큼 / N 정도 / N보다 크다"를 잡는 규칙과 참조 사물 크기표(주먹, 달걀, 축구공, 수박, 접시, 손바닥, 새끼손가락 …)를 둡니다. "숫자 + 미터·센티·뼘 + 쯤·정도"를 파싱해 size·distance 구간으로 바꿉니다. 표는 출처와 함께 `shared/lexicon/`에 둡니다. |
| 3 | 사전 보강 | LEX 22, SIM 3 | 색 이름(귤·크림·베이지·청록·연두·누르스름), 의태어 질감(오돌토돌·까끌까끌·반질반질·바삭바삭·울퉁불퉁 → texture), 움직임(소용돌이치다·펄럭이다·살랑거리다·구르다·피어나다), 투명도(비치다·옅다), 신체 부위(손등), 높이(눈높이·바닥), 직유 원천(껍데기·공기·솜사탕·가루·알갱이)을 넣습니다. 각 항목에 출처(`src`)를 적습니다. |
| 4 | 복합어 · 접두사 | CMP 7, DEG 5 | 'X색' 단일 명사(하얀색·노란색)를 alt로 받습니다. 접두사 연-(명도↑·채도↓), 반-(반투명), 진-/짙은(명도↓)을 색 값 보정 규칙으로 처리합니다. 정도 부사(살짝·조금·아주)는 구간 안 보정표로 씁니다. 위치어 '안'의 품사 중의성은 '몸/배/가슴 + 안' 패턴으로 받습니다. |
| 5 | 수식 범위 | SCOPE 6, 배경 오염 8 | 관형어가 꾸미는 명사가 형상 지시어(그것·덩어리·공 …)가 아니라 맥락 사물(벽·책상·잎·화분·빵집)이면 값으로 쓰지 않습니다. 대신 `_context` 같은 보존 필드에 원문으로 남깁니다. 첫 답의 회상 문장("~하던 장면/게 떠올라요")에서 나온 자세·위치어는 형상 값으로 쓰지 않습니다. |
| 6 | 같은 슬롯 경쟁 규칙 | FIRST 4, PART 2, UNC 1 | 먼저 말한 값보다 구체어(어깨 > 몸), 상태어보다 움직임 동사(돌다 > 떠 있다)를 앞세웁니다. "겉은/안쪽은/테두리는/가운데는" 부분 표지가 있으면 부분별 값을 따로 보존하고, 대표 값은 전체를 가리키는 말에서만 고릅니다. '모르겠다'가 붙은 차원은 값 대신 '모름'으로 표시합니다. |
| 7 | 부정 범위 · 다의어 | NEG 1, POLY 3 | "명사 + 이/가 + 안 + 서술어"에서 명사의 속성도 부정으로 봅니다. '빛'이 '연두빛·흰빛'처럼 색 이름에 붙으면 brightness로 보내지 않습니다. '가깝다' 앞에 색·빛 명사가 오면 거리로 보내지 않습니다. |
| 8 | 컨트롤러 · 프로토콜(팀 결정) | CTRL 13 | 매핑 밖입니다. 프로브 생략 기준과 '모르겠어요' 처리는 프로토콜 변경이라 이번 작업에서 고치지 않습니다. 아침 확인 목록에 올립니다. |

비교 조건을 유지하려면 v0(`scene_builder.py`)는 그대로 두고, 개선 매핑을 별도 모듈로 만들어 `--mapper`로 바꿔 끼웁니다. 개선 매핑에서 예외가 나면 v0 결과를 냅니다(AC-3.7). 최종 수치는 held-out 코퍼스로만 보고합니다.
