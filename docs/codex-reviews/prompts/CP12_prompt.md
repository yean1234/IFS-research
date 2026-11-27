너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`, 설계 뼈대 `docs/design-backbone.md`(실험은 이 뼈대를 따른다), 실행 순서 `docs/run-experiment.md`, 참여자 보호 `docs/participant-protection.md`(IRB 심의 없이 진행, G68).
- 검토 범위: `git diff 4d0304f HEAD`(브랜치 `claude/interview-mapper-fixes`). 결정은 `docs/decisions.md`의 G70(면담 앞부분, 구현 세부 포함), G71(매퍼: 움직임 비유 매개어와 직접 형태 진술), G72(축별 비율) 절.
  - G70: 프로토콜 1.6(`shared/protocol/elicitation_protocol.v1.6.json`), 프롬프트 v1.2.0, 안전 사전 0.3.0, `controller.py`·`validator.py`·`anchors.py`·`extract.py`·`prompts.py`·`simulate.py`, 시험 `test_g70.py`, 시나리오 `chatbot/scenarios/g70_*.json`. `experiment.toml`에서만 켜짐.
  - G71: `scene_builder_v2.py`(builder 2.6.0), `scene_params.v2.json` 2.1.0, 시험 `test_g69_shape_priority.py`.
  - G72: 스펙 `scene-spec.v2.4.json`, 매퍼(builder 2.8.0, proportions 표), `candidate_values.v3.json`, `selection_protocol.v0.7.json`, `selection.py`, Unity `SceneSpec/*`·`Rendering/FormRenderPlan.cs`·`ProportionsRender.cs`·`PlacementSelection.cs`, 분석기 `eval/placement.py`, 시험 `test_g72*.py`·`ProportionsTests.cs`.
- 시험(에이전트 보고): 관련 pytest 파일별 통과, Unity compile-check 600 통과. 열린 에디터 EditMode 시험은 못 돌림.

## 이미 알고 있는 것 (되풀이하지 말 것)
- `test_differentiation.py::test_committed_single_validation_outputs_are_byte_identical` 실패는 예전부터 있다.
- 헤드셋 빌드를 다시 만들어야 2.4.0 스펙을 읽는다. 생성 메시(G62)는 실험 설정에서 꺼져 있다(G67-b).
- 후속으로 적어 둔 것: LLM 인용 X에 '-하' 어근 제한이 없음, 첫 답(그 일에 대한 말)이 매퍼에 들어가 물체 값이 되는 문제, 알려진 형상 신호 오분류(G64-l), 안개·연기·먼지가 같은 mist로 그려짐.
- 새 문구는 모두 draft다.

## 할 일과 관점
1. **기존 설정 불변**: default/pilot/v4/v4-gen3d/bridge/mac8gb와 프로토콜 1.4·1.5, 매퍼를 끈 설정의 출력·기록·후보 id·해시가 바뀌는 경로. 플래그 기본값.
2. **원칙 2(말한 것만)**: G71·G72 규칙이 말하지 않은 값을 채우거나, 말한 값을 버리는 체계적 경우(부정·가정·회상·타인·비유·관형형/진행형 판정 오류, '구체적'류 동음이의, 방향 기본값). 직접 진술 대 형상 낱말 우선순위의 반례.
3. **원칙 3(면담)**: 1.6 고정 문구와 결정론 규칙(인용 X 선택, 조사 처리, referent, 프로브 판정, 같은 틀 금지)이 참여자가 쓰지 않은 말·예시·선택지를 내거나, 어색한 한국어를 내는 경우. V5 완화가 다리 고정 문장 밖으로 새는가.
4. **원칙 4(위기)와 참여자 보호**: 안전 사전 0.3.0과 흐름 변경(find 건너뛰기, LLM 단계 조기 종료, 프로브 건너뛰기)이 위기·확인 판정을 건너뛰는 경로. 「다 끝내고 싶어요」 등.
5. **흐름 결함**: 같은 틀 금지·like_what 1회·대체 문구 억제가 서로 얽혀 면담이 너무 일찍 끝나거나 아무 질문도 못 내는 경우, 무한 반복, 매퍼 예외 시 폴백.
6. **G72 거리 결과변수**: 가장 긴 변 = size가 모든 형태(메시·안개·조각·GLB)와 미리보기·헤드셋에서 실제로 지켜지는가. 비율 조절이 바닥 접지·피벗·시작 높이·멈춤 경로와 충돌하는가. 기록된 boundsM이 실제 렌더와 맞는가.
7. **스키마·호환**: 2.4.0 필수/선택 규칙, 2.0–2.3 읽기, selection 기록 하위 호환, 분석기 열이 기록 없을 때 깨지지 않는가.
8. **시험의 빈틈**: 항상 통과하는 시험, 구현을 그대로 베낀 기대값 가운데 결함을 가리는 것, 문서(decisions·chatbot-design §5-4·scene-spec-mapping 9·10절·run-experiment)와 코드 불일치.

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순. 끝에 "문제없다고 확인한 것"을 짧게. 추측은 추측이라고 밝혀라.
