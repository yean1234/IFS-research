너는 이 연구 저장소의 외부 감시자(비평가)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: IFS의 Find→Focus→Flesh out 단계를 따르는 면담 챗봇 → 확정 텍스트 → 화이트박스 규칙 매핑(SceneSpec JSON) → Unity VR 렌더. 초점은 "사용자가 떠올린 심상을 VR에 얼마나 일치하게 구현하는가(심상-구현 일치도)". 저장소 원칙은 AGENTS.md(특히 원칙 1: 장면 속성은 사전·규칙만, 같은 텍스트→같은 결과 / 원칙 2: 말하지 않은 것을 추론하지 않음, 기본값과 미지정을 섞지 않음 / 원칙 7: 고정 문구 변경 시 status·출처·버전).
- 지난 체크포인트(CP1, 커밋 d4e3e3a)에서는 연구 설계를 검토했다. 이번 CP2는 작업 2(심상 유지 drift 감지)와 작업 3(규칙 매핑 실패 사례 → 자유 입력 매핑 개선 v1, v0는 비교 조건·폴백으로 유지) 완료 시점이다.

## 이미 한 내부 검토
- 이 범위는 Claude 독립 검토자 2명이 먼저 검토했고, 그 지적과 수용/보류 분류·수정 결과가 docs/decisions.md 맨 끝 "2단계 독립 검토 분류"·"수정 결과와 수정 에이전트의 결정" 절에 있다(매핑 빌더 1.2.0, 채점기 0.3.0, drift 1.1.0). 같은 지적을 되풀이하지 말고, 그 수정이 실제로 문제를 없앴는지, 수정이 새로 만든 문제, 그 검토가 놓친 것을 찾아라. 보류로 둔 항목 중 보류가 부당한 것이 있으면 지적하라.

## 할 일
1. `git diff d4e3e3a..HEAD --stat` 로 범위를 보고, `git diff d4e3e3a..HEAD -- chatbot shared docs` 를 읽어라. unity/ 는 SceneSpec 파서(Runtime/SceneSpec/*.cs) 변경만 보면 된다.
2. 특히 다음을 읽어라:
   - 매핑: chatbot/ifs_chatbot/scene_builder_v1.py, jamo.py, clarify.py, scene_spec.py, lexicon.py, shared/lexicon/*.v1.json, shared/schemas/scene-spec.v2.1.json, docs/mapping-v1.md, docs/scene-spec-mapping.md, docs/mapping-failures.md
   - 채점: chatbot/ifs_chatbot/eval/fidelity.py, corpus_run.py, chatbot/tests/fixtures/imagery_corpus/dev.json (heldout.json은 형식만 확인. 아직 평가에 쓰지 않았다)
   - drift: chatbot/ifs_chatbot/drift.py, controller.py의 drift 부분, chatbot/tests/fixtures/drift/drift_cases.json, docs/drift-design.md, docs/research-design.md 4.5절, docs/acceptance.md AC-2·AC-3
   - 기록: docs/decisions.md
3. 다음 관점으로 **비판**하라:
   A. 자유 입력 → JSON 변환에서 **손실·왜곡**:
      - 사용자가 말한 속성이 JSON에서 사라지는 경로(컨트롤러 드롭, 사전 미등재, 수식 범위 오류, 부정·비교·수량 표현, 복합어, 여러 대상이 섞일 때 어느 대상에 붙는지).
      - 말하지 않은 값을 만들어 넣는 경로(퍼지 매칭 오탐, 기본값이 '말한 값'처럼 표시됨, 다른 대상·배경에서 속성이 새어 들어옴).
      - 원문 보존(verbatim) 필드가 정말 원문 그대로인지, charSpan이 맞는지.
      - v0 바이트 동일성·폴백 경로가 실제로 지켜지는지, v1이 결정적인지(같은 입력→같은 출력).
      - dev 코퍼스에 과적합된 규칙(특정 문장만 맞추는 하드코딩)이 있는지. held-out 일반화를 해칠 만한 것.
      - 채점기(fidelity.py)가 v1을 유리하게 만드는 허점(정답 구간이 넓어 왜곡을 놓침, null 정답 처리, 무슬롯 처리 등).
   B. **drift 기준의 구멍**:
      - 지표(DI 등)와 임계값(τ/θ)이 무엇을 재는지, 정교화(속성이 늘어남)와 대체(다른 심상으로 바뀜)를 구별하는지.
      - 라벨 세트(drift_cases.json)가 기준을 만든 쪽과 같은 관점으로 쓰여 순환적이지 않은지, 경계 사례가 충분한지, 정확도 0.90 기준이 18개 내외 사례에서 의미 있는지.
      - 거짓 양성/거짓 음성이 나올 실제 대화 패턴(동의어·대명사·부정·"아까 그거"·색 이름 바뀜·크기 표현 바뀜).
      - 자기보고·회상 확인 문구가 원칙 3·7(질문 틀, 고정 문구 IRB)을 어기지 않는지.
   C. acceptance 기준(AC-2, AC-3)이 쉽게 통과되도록 느슨하거나 확인 불가능한 곳.
4. 출력 형식: 지적 사항을 번호 목록으로. 각 항목에 [심각도: 높음/중간/낮음], 위치(파일:줄 또는 절), 문제, 근거(가능하면 구체적 입력 예와 예상 잘못된 출력), 제안. 마지막에 총평 3줄. 칭찬은 생략.
