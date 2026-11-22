# 배치 실험 러너 자동 시행 기록 (합성 자료 — 참여자 자료 아님)

`records/`는 합성 예시 spec `unity/Assets/StreamingAssets/IFS/examples/EX02.json`과 자동 시행 스크립트(`PlacementAutoScript`, 합성 입력)로 2026-11-22에 만든 기록입니다(`events.csv`에 `auto_mode`, manifest `flags.autoMode: true`). `analysis/`는 그 기록을 `ifs_chatbot.eval.placement`에 넣은 결과입니다.

| 참여자 번호 | 조건 / 통제 방식 | 비고 |
| --- | --- | --- |
| P001 | place / none | 잡기 2번(다시 잡기), 확인 |
| P002 | view / static | |
| P003 | view / replay | 원본 = P001의 `trajectory.json` |
| P004 | view / system_move | 목표 2.5 m · 0° · 1.2 m |
| P005 | view / point_select | 2.4 m · 25° 지점을 가리킴 |

설정은 기본값(제시 30 s, 조건 90 s, dt 0.02 s, 20 Hz). 실행 방법은 `unity/README.md` 「배치 실험 러너」.
