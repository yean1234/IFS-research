"""심상-구현 일치도 평가 도구(오프라인, LLM 없음).

- corpus_run: 코퍼스 항목의 답을 실제 컨트롤러(정적 조건)에 넣어 확정 텍스트와 SceneSpec v2를 얻는다.
- fidelity:   정답(gold) 대비 반영·왜곡·보존·손실을 채점하고 리포트를 쓴다.
- e2e:        코퍼스 → 재생 → v0·v1 spec 파일 → 스키마 검증 → 채점 → (선택) Unity 적용값 대조(docs/validation/e2e/README.md).
- ownership:  소유감 실험(Unity 러너) 기록 → stimuli.csv·sessions.csv·summary.json(RQ1–RQ3 기술 통계).
- placement:  배치 실험(RQ V4, ifs-placement/0.1) 기록 → placement_sessions.csv·stop_trials.csv·placement_summary.json
              (놓은 자리·고리 몰림·멈춤 거리·머리 행동·평정의 기술 통계와 효과크기 추정).
- language_markers: 한국어 발화의 언어 표지 K1–K7·태도 낱말(Kiwi 규칙, 근거 구간·판본 기록).
- differentiation: 구별 프로파일(자기보고·행동 2×2·언어를 성분별로 따로, 순위 상관·사례 목록, 합산 없음).
- sim_placement: ifs-placement/0.1 합성 세션 생성기(파이프라인 검증용, 효과의 근거가 아님).
  사용법과 합성 검증 결과: docs/validation/differentiation/README.md

정의와 실행 명령: docs/mapping-failures.md
"""
