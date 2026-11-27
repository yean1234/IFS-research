# CP13b 구현 검토: G73 다시 적기 화면·문구·기록·서버 연결

범위: `git diff 5d1ea64~1..b4f2f19`가 아니라 커밋 b4f2f19 자체(`git show b4f2f19`)와 1f9f21f의 문구 변경. 코드는 고치지 말고 지적만.
읽을 것: AGENTS.md, docs/design-backbone.md, docs/participant-protection.md, docs/decisions.md 끝의 G73 절 전체(G73~G73-r, D12 반박 판정, CP13·CP13b 판정).

찾을 것:
1. 작업 원칙 위반: 위기 판정 뒤 LLM·생성기 호출, 참여자에게 보이는 문구의 예시·선택지·차원어·치료 표현, 고정 문구 status·출처·판 누락, 원문이 git 추적 경로나 selection.json에 남음, 끈 설정(resay=false)에서 동작·기록 변화, experiment.toml이 켜짐.
2. 버그: 흐름 상태 전이(건너뛰기·시간 초과·회차 상한·전체 대기 상한·생성기 실패·세션 종료) 뒤 기준 후보 0번 복귀와 서버·화면 기록 불일치, 경쟁 상태(백그라운드 생성 중 건너뛰기·재요청), 두 조건(static·placement)에서 흐름 차이, selection.v0.4 스키마와 실제 기록 불일치, 출처(`generated_resaid_chosen`·`resaid`·`edited`) 오기록, mist.density가 Unity·미리보기로 가는 경로(SceneOverrideJson·FormRenderPlan), G73-m 조건(어떤 경우에만 처음 값을 쓰나) 위반.
3. 빠진 시험.

이미 알고 있는 것(다시 지적하지 말 것): 생성 큐 작업자 없음, 생성 전 Ollama 내리기 없음, renderVars.measuredDims null, 브라우저 확인 안 함, Kiwi 스레드 안전성 미확인, Unity를 이 Mac에서 컴파일 못 함, 설계 뼈대 2절과의 범위 차이(연구 책임자 판단 대기), 「안개가 안 보여요」 주어 부정 문제, test_differentiation 기존 실패, trimesh 없음, test_selection_flow 메모리 문제, CP13 지적 1–3(따로 재검토 중).

한국어, 지적마다 [높음/중간/낮음], 파일:줄, 재현 절차, 고칠 방법. 70줄 이내.
