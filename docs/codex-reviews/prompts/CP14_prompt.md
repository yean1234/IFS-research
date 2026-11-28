너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 원칙 `AGENTS.md`, 설계 뼈대 `docs/design-backbone.md`, 참여자 보호 `docs/participant-protection.md`(IRB 없이 진행), 실행 순서 `docs/run-experiment.md` 6절.
- 검토 범위: `git diff fa5cc4c HEAD -- . ':!docs/codex-reviews' ':!research_notes'`(브랜치 `claude/g75-image-confirm`)의 G75. G75(2026-11-28 연구 책임자 결정): [맞는 게 없어요] 뒤 형태 낱말 프롬프트로 무채색 그림 3장 → 참여자가 가장 가까운 그림을 고름 → 고른 그림만 TripoSG → 메시 후보 맨 앞(그 뒤는 G73과 같음). [이 중에는 없어요]면 새 seed로 한 번 더, 그래도 없으면 기존 none 경로. 플래그 `[gen3d] on_none_image_pick`은 `experiment.toml`에서만 켠다.
- 구현: `tools/gen3d/{prompts,form_asset,generate}.py`, `chatbot/ifs_chatbot/{none_gen,selection,server,config}.py`, `web/{stage,app}.js`, `shared/protocol/selection_protocol.v0.9.json`, `shared/schemas/selection.v0.4.json`, Unity `PlacementSelection.cs`, 시험 `chatbot/tests/test_g75_image_pick.py`, 문서 `docs/chatbot-design.md` 7.11, 검증 `docs/validation/run-g75-image-pick/README.md`.
- 구현자가 정한 것: 그림 단계와 형태 단계를 각각 G73식 작업(모델 내림 → 생성기 → 다시 올림)으로 두 번 돌리고 고르는 동안은 면담·가드 모델을 올려 둔다. 고르는 사이 다른 세션이 면담을 시작하면 형태 단계는 `interview_active`로 기존 경로. 선택 기록은 켠 세션에서 처음 none 순간 `ifs-selection/0.4`. 그림 관문은 그림 한 장에 기존 CLIP 라벨·문턱. 캐시 미리 보기 없이 늘 모델을 내림.

## 이미 알고 있는 것 (되풀이하지 말 것)
- `test_differentiation.py::test_committed_single_validation_outputs_are_byte_identical` 실패는 예전부터 있다.
- 안내 문구 「색은 나중에 말씀하신 대로 칠하니」가 색을 말하지 않은 참여자에게 맞지 않는다(고칠 예정). 받침대가 붙은 그림이 관문을 지나 보일 수 있다. '돌덩이'가 형태 사전에 없다. 고른 그림과 메시가 같은 모양이라는 보장이 없다. 대기가 두 번 생긴다. G73 `_run`의 취소 경합은 손대지 않았다.
- 새 문구는 모두 draft다. 헤드셋 빌드는 다시 만들어야 한다.

## 할 일과 관점
1. **기존 설정 불변**: 플래그가 꺼진 모든 설정에서 출력·기록·판·생성기 인자가 바뀌는 경로.
2. **원칙 1·2(G62 예외)**: 그림 프롬프트에 LLM·원문·매퍼가 뺀 낱말이 들어가는 경로. 생성 후보가 참여자 확인 없이 장면에 쓰이는 경로. 그림에서 슬롯 값(색·크기 등)을 읽는 경로.
3. **원칙 4와 참여자 보호**: 두 단계 사이·고르는 동안·취소·시간 초과에서 가드 모델이 내려간 채 면담 입력을 받거나, 위기 문장이 고정 문구 없이 거절되는 경로. 사람·동물 그림이 참여자에게 보이는 경로(관문 실패·예외·파일 누락 시 fail closed인가).
4. **흐름 결함**: 상태 기계의 교착·중복 요청·새로고침·뒤로 가기·두 번 누르기·세션 종료, 회차 상한 계산, 메시 후보 뒤 다시 none, 넘어가기 경합, 고아 프로세스, 그림 파일 경로 노출(다른 세션의 그림을 URL로 볼 수 있는가, 경로 조작).
5. **기록·스키마**: 0.4 기록이 분석에 필요한 것(노출 여부, 회차, seed, sha256, 고른 번호, 관문 결과)을 빠짐없이 적는가. 0.3 읽기 호환. Unity가 0.4를 0.3과 같은 규칙으로 읽는 것이 안전한가. 참여자 원문이나 로컬 절대 경로가 기록·커밋에 들어가는가.
6. **시험의 빈틈**: 항상 통과하는 시험, 가짜 생성기가 실제 계약과 어긋나는 곳, 문서와 코드 불일치.

## 출력 형식
지적마다: 심각도(높음/중간/낮음), `파일:줄`, 재현 입력 또는 경로, 왜 문제인지, 고칠 방향 한 줄. 심각도 순. 끝에 "문제없다고 확인한 것"을 짧게. 추측은 추측이라고 밝혀라.
