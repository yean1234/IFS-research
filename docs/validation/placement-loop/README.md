# 반복 멈춤·눈높이 합성 기록 (G60-2·G60-3, 2026-11-26 — 합성 자료, 참여자 자료 아님)

> **합성 자료: 파이프라인 검증용이며 효과의 근거가 아님.** 세션 24개는 모두 `ifs_chatbot.eval.sim_placement`가 만든 가짜 기록입니다(AGENTS.md 원칙 6).

`records/`는 멈춤 거리 반복 멈춤(`stopMode loop`)과 눈높이 기준 배치(`eyeHeightMode relative`)를 켠 형식의 합성 세션이고, `analysis/placement/`는 그 기록을 `ifs_chatbot.eval.placement`에 넣은 결과입니다(`placement_sessions.csv`의 반복 멈춤·눈높이 열, `stop_loop_rounds.csv`, 요약 `stopLoop`·`eyeHeight`). `analysis/differentiation/`(고정 기준)·`analysis/differentiation_median/`(중앙값 분할)은 같은 기록의 구별 프로파일이고 `analysis/sim_check.json`은 가정 유형 대조표입니다(기본 방식 `../differentiation`과 같은 파이프라인). 기존 검증 폴더(`../differentiation`, `../placement`)는 건드리지 않았습니다.

- 출발 계획(`manifest.json`의 `stopDistance.loop.plan`)은 Unity 러너와 같은 규칙(참여자 번호 시드 xorshift64*)으로 만들었습니다. 같은 값을 `PlacementStopLoopTests`(C#)와 `test_placement_eval.py`(Python)가 고정값으로 대조합니다.
- 라운드 안의 움직임은 러너 규칙(왕복·끝에서 반사·멈춤/재개 같은 방향·멈춘 상태에서 확정)을 해석적으로 푼 값이고, 멈출 거리·확정 여부·눈높이는 생성기가 정한 가정입니다(`sim_truth.json`). 본 라운드의 약 8%는 일부러 확정하지 않아(`timeout_stopped`) 결측 처리를 봅니다.
- 구별 프로파일(`differentiation`, 2026-11-26 추가): loop 세션의 멈춤 성분 `sd_mean_m`은 placement 분석기의 주 값 `stop_final_mean_m`(본 라운드 중 확정된 라운드의 확정 거리 평균, 확정 라운드 2개 이상일 때만)입니다. 한계법의 방향별 값(`sd_approach_m`·`sd_recede_m`·`sd_asym_m`)은 loop에서 정의되지 않아 빈칸이고, 프로파일 표에 `stop_mode`·`sd_final_n` 열, 요약에 `behavior.stopMode`가 붙습니다(single 기록만 넣으면 이 열·키가 없고 출력은 전과 바이트까지 같음 — `test_committed_single_validation_outputs_are_byte_identical`). single과 loop 세션을 함께 넣으면 `warnings`에 `config_mismatch:stop_mode`가 붙습니다.
- 결과(합성, 효과 근거 아님): 24세션 모두 loop, 확정 라운드 2개 미만으로 `sd_mean_m`이 빈칸인 세션 1개(`far_look`). 유형별 `sd_mean_m` 평균은 생성기 가정 구간 안에 있습니다 — near_look 0.79 m(가정 0.7–0.9), far_look 1.60(1.5–1.8), far_away 1.93(1.7–2.1), view_only 1.20(1.1–1.3)(`sim_check.json`의 `stop_assumed_range_m`·`sd_mean_mean`). 코드가 정의대로 계산한다는 확인일 뿐입니다.
- 다시 만들 때 `records/`와 `analysis/placement/`는 이전과 바이트까지 같았습니다(새로 생긴 것은 `analysis/differentiation*/`·`sim_check.json`뿐).

재현(결과가 바이트 단위로 같음):

```bash
cd chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.sim_placement --out ../docs/validation/placement-loop --analyze --stop-mode loop --eye-mode relative
```
