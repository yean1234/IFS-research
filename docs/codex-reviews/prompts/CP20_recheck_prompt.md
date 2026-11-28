너는 이 연구 저장소의 외부 감시자다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

앞선 검토 `docs/codex-reviews/CP20.md`의 지적 3건이 고쳐졌는지 마지막 커밋(`git show --stat HEAD`, `git diff HEAD~1 HEAD`)에서 확인하라. 판정과 조치는 `docs/decisions.md` 맨 끝 "G83 구현 검토 CP20" 표에 있다.

1. `chatbot/ifs_chatbot/llm_shape.py`의 `basis_display`와 `selection.py`: 화면에 나가는 근거 낱말이 어떤 분기에서도 확정 텍스트의 부분 구간인가. 구간 불일치 때 LLM 없는 경로로 가는가.
2. `unity/Assets/IFS/Runtime/Placement/PlacementSession.cs`의 `StepStopLoop`: XR이 끊긴 동안 제한 시간·물체·입력이 멈추고 재연결 뒤 이어지는가. 이 수정이 만든 새 문제(끊긴 채 실험자가 단계를 넘길 때, 끊김이 라운드 사이 틈에 걸칠 때, 멈춤 상태에서 끊겼다 돌아올 때 방향·속도).
3. 추가된 시험이 위를 실제로 고정하는가.

이미 알고 있는 것(되풀이하지 말 것): 조건 단계 등 다른 단계의 타이머는 XR이 끊겨도 흐른다. 실제 흐름 재확인은 basis_display 0.1.0으로 돌렸고 다시 돌리지 않았다. 헤드셋에서는 확인하지 못했다.

출력: 지적 3건의 상태 표(고쳐짐/일부/안 고쳐짐, 근거 `파일:줄`), 새로 찾은 문제만 심각도와 함께. 로컬 경로는 `<repo>/`로 적어라.
