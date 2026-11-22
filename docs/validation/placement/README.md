# 배치 실험 러너 자동 시행 기록 (합성 자료 — 참여자 자료 아님)

`records/`는 합성 예시 spec `unity/Assets/StreamingAssets/IFS/examples/EX02.json`과 자동 시행 스크립트(`PlacementAutoScript`, 합성 입력)로 2026-11-22에 만든 기록입니다(외부 검토 CP7 반영 뒤 다시 만듦)(`events.csv`에 `auto_mode`, manifest `flags.autoMode: true`). `analysis/`는 그 기록을 `ifs_chatbot.eval.placement`에 넣은 결과입니다.

| 참여자 번호 | 조건 / 통제 방식 | 비고 |
| --- | --- | --- |
| P001 | place / none | 잡기 2번(다시 잡기), 확인 |
| P002 | view / static | |
| P003 | view / replay | 원본 = P001의 `trajectory.json` |
| P004 | view / system_move | 목표 2.5 m · 0° · 1.2 m |
| P005 | view / point_select | 2.4 m · 25° 지점을 가리킴 |

설정은 기본값(제시 30 s, 조건 90 s, dt 0.02 s, 20 Hz). 실행 방법은 `unity/README.md` 「배치 실험 러너」.

다시 만든 기록의 확인값(분석기 출력 `analysis/`):

| 참여자 번호 | 놓은 거리(m) · 방위(°) · 높이(m) | 멈춤 거리 approach / recede 평균(m) | flags |
| --- | --- | --- | --- |
| P001 place | 2.6 · −20 · 0.9 | 1.245 / 1.73 (timeout 1) | `runner_warning:1` |
| P002 view/static | 1.5 · 0 · 1.2 | 1.245 / 1.73 | `runner_warning:1` |
| P003 view/replay | 2.6 · −20 · 0.9 | 1.245 / 1.73 | `runner_warning:1` |
| P004 view/system_move | 2.5 · 0 · 1.2 | 1.245 / 1.73 | `runner_warning:1` |
| P005 view/point_select | 2.4 · 25 · 1.2 | 1.245 / 1.73 | `runner_warning:1` |

`runner_warning:1`은 draft 문구 경고(의도한 것)입니다. 5개 모두 `conditionCompleted: true`, manifest `object.boundingRadiusM` 0.1933, `flags.layoutIgnored` false(EX02의 `layout.distance`·`verticalOffset`이 null), 요약 `configMismatch` 없음. 멈춤 거리는 자동 스크립트가 같은 값을 누르므로 다섯 세션이 같습니다(조건 효과 검증용 자료가 아님). `chatbot/tests/test_placement_eval.py`의 계약 테스트가 이 폴더를 분석기에 넣어 봅니다.
