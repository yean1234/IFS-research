너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`, 설계 뼈대 `docs/design-backbone.md`, 실행 순서 `docs/run-experiment.md`, 참여자 보호 `docs/participant-protection.md`.
- 검토 범위: `git diff 4368793 HEAD`(브랜치 `claude/interview-mapper-fixes`). 결정은 `docs/decisions.md`의 G73(「'맞는 게 없어요' 뒤 형태 생성」), G74(「안개·연기·먼지·구름 구분」), 「G73·G74 후속」 절.
  - G73: `chatbot/ifs_chatbot/none_gen.py`, `selection.py`, `server.py`, `controller.py`, `config.py`, `web/stage.js`·`app.js`, `tools/gen3d/prompts.py`(매퍼 결과를 받는 `shape_prompt`), `tools/gen3d/generate.py`(`--cache-probe`), `shared/protocol/selection_protocol.v0.8.json`, `shared/schemas/selection.v0.3.json`, Unity `ShapeMapping.Resolve`·`SceneLoader`·`PlacementSelection`, 시험 `test_g73_none_gen.py`·`test_g73_prompt_rule.py`.
  - G74: `scene_builder_v2.py`(mistKinds), `scene_params.v2.json`, 스펙 2.4.0의 `form.mistKind`, Unity mist 셰이더·`DustMesh`, 시험 `test_g74_mist_kinds.py`·`MistKindsTests`.
- 시험(에이전트 보고): 관련 pytest 파일별 통과, dotnet 618 통과. Unity EditMode는 못 돌림.

## 이미 알고 있는 것 (되풀이하지 말 것)
- CP12까지의 지적과 처리(`docs/codex-reviews/CP12.md`). `test_differentiation` 기존 실패 1건.
- 헤드셋 빌드를 다시 만들어야 한다. CLIP 사람·동물 관문 오탐('둥근 천'). 새 문구 draft. 조절 화면에서 안개 종류를 고르는 조절은 보류(G74-d). '구체'·'구형'은 형태 프롬프트 사전에 넣지 않음(G73-i).
- 러너 계약 `sources.form.type`은 `generated_chosen` 그대로, 세부 출처에 `generated_after_none`(G73-c).

## 할 일과 관점
1. **원칙 1·2**: 생성 프롬프트에 매퍼가 버린 낱말이나 참여자가 말하지 않은 내용이 들어가는 경로. 매퍼 spec과 확정 텍스트가 어긋나는 경우. 생성 후보가 고르지 않았는데 장면에 쓰이는 경로. 크기·색·위치를 모델이 바꾸는 경로.
2. **원칙 4·참여자 보호**: Ollama 모델을 내린 동안 위기 판정·가드가 필요한 입력이 들어올 수 있는가(다른 세션, 사후 면담, 철회). 모델을 다시 올리지 못하면 다음 세션이 어떻게 되는가. 생성 중 참여자 대기·건너뛰기에서 세션이 멈추는 경로.
3. **동시성·프로세스**: 백그라운드 스레드·자식 프로세스 종료(taskkill), 시간 초과, 늦게 온 결과 무시, 서버 재시작, 같은 세션 이중 요청, 캐시 판정 오류로 모델을 내리지 않았는데 실제 생성이 도는 경우(GPU 메모리 부족).
4. **기록·분석**: `afterNone` 필드가 분석 규칙(G73-d)을 복원하기에 충분한가, 스키마와 맞는가, 0.2 기록 하위 호환.
5. **G74 매퍼**: 연기·먼지 → mist 규칙과 장소 용법 규칙의 오탐·누락, '김'·'가루' 동음이의, 부정, G71·G72와의 우선순위 충돌.
6. **Unity**: `ShapeMapping.Resolve` 변경이 덮어쓰기가 없는 기존 spec 그림을 바꾸는가, 러너 검사와 미리보기 검사가 같은 판정을 하는가, dust 메시 결정성·가장 긴 변 규칙.
7. **기존 설정 불변**과 **시험의 빈틈**(항상 통과, 구현을 베낀 기대값), 문서와 코드 불일치.

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순. 끝에 "문제없다고 확인한 것"을 짧게. 추측은 추측이라고 밝혀라.
