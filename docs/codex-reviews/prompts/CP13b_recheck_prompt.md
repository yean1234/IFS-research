# CP13b 재검토: 지적 1–4와 주어 부정 처리가 고쳐졌는가

원 지적: docs/codex-reviews/CP13b.md. 판정: docs/decisions.md "CP13 재검토와 CP13b 구현 검토 판정"(1–4, '—' 항목). 고친 커밋: 2e36315 (`git show 2e36315`).
각 항목마다 [고쳐짐/덜 고쳐짐/새 문제]와 근거(파일:줄, 재현)만. 새 문제는 이 커밋이 만든 것만. 특히 resay=false에서 동작이 바뀌지 않았는지(simulate.py·selection_sim.py·drift.py·eval/corpus_run.py의 세션 종료 경로 교체 포함), 백그라운드 작업의 경쟁 상태. 40줄 이내, 한국어. 코드는 고치지 않는다.
이미 알고 있는 것: 「안개 같은 게 안 보여요」(비유)는 갈래 none, 「공이 둥글지 않아요」는 매핑은 solid인데 공유 G62 프롬프트가 공을 부정으로 봐 차단(안전 쪽, G62 출력 보존 때문에 그대로 둠), 서버 종료·end_session 뒤 회차 outcome null, cancel을 무시하는 생성기의 경쟁.
