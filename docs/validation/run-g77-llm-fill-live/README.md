# G77 실측: 확정 직후 LLM 빈 슬롯 제안을 실제 로컬 모델로 (2026-11-28)

합성 확정 텍스트 19개(참여자 자료 아님)로 `chatbot/ifs_chatbot/llm_fill.py`를 실제 Ollama 모델에 돌린 기술 실측이다. 제품 코드·프롬프트·시험은 고치지 않았다.

- 모델: `gemma4:e4b` `sha256:dc35e8d9c6061baa6f0fa870975ab6932e2542b579b13ea0f199fa4bb7300c9c` (Q4_K_M, 7.5B), Ollama 0.40.17, RTX 5080 16 GB. 프롬프트 `llm_fill.v0.1.1.json`(draft), 온도 0, seed 0(`llm_fill_seed` 코드 기본값. experiment.toml에는 이 값이 없다), 한도 20초.
- 설정: experiment에 가드 모델 없음, 미리보기 none, `gen3d.on_none` 끔, `lock_condition` 끔(static 세션에 확정 텍스트를 바로 넣으려고), 기록은 남기지 않음(`persist_logs=False`, 임시 폴더).
- 실행(`chatbot/`에서): `.venv\Scripts\python ..\docs\validation\run-g77-llm-fill-live\live_llm_fill.py --repeats 5 --cold 3`
- 단계: ① 모델을 내린 뒤 제품 경로로 부름(cold, 3문장). 같은 사용자 메시지를 한도 120초로 한 번 더 불러 실제 걸린 시간을 잰다. ② 모델이 올라와 있을 때(warm) 문장마다 세션 캐시를 비우고 5번 부른 뒤, 캐시 확인을 1번 한다. ③ 가드 모델도 함께 올린 상태에서 문장마다 2번 부르고, ②의 원시 출력과 같은지 본다.
- 결과: `results.json`. `summary`는 ② 기준이고 `summary.guardPhase`가 ③이다. 문장마다 원시 출력(`rawText`), 항목별 검증기 사유, charSpan 분류(`span.kind`), Ollama meta를 담았다.

요약(②, 95회): 스키마 오류 0, 반복 일치 19/19, 걸린 시간 0.16–0.86초. 항목 45개(서로 다른 것 9개) 가운데 charSpan이 정확한 것이 45개, 통과한 것이 40개다. ③(38회)에서는 1회가 ②와 다른 원시 출력을 냈고, 그 출력의 인용 끝이 1글자 어긋나 `quote_mismatch`로 버려졌다. cold는 3.9–4.6초였다.
해석과 지적은 메인 세션 보고에 있다. 사람 눈으로 가린 "과한 해석"은 참고용이다.
