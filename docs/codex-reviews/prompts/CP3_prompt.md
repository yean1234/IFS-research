너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: IFS Find→Focus→Flesh out 면담 챗봇 → 확정 텍스트 → 화이트박스 규칙 매핑(SceneSpec JSON, v0 규칙 / v1 개선) → Unity VR 렌더. 초점은 심상-구현 일치도. 저장소 원칙은 AGENTS.md.
- 이번 CP3는 작업 5(중립 테스트 입력으로 챗봇→JSON→Unity 전 과정 실행 검증) 완료 시점이며, **전체 코드 리뷰**를 맡긴다.

## 할 일
1. `git diff <CP2_COMMIT>..HEAD --stat` 와 `git diff <CP2_COMMIT>..HEAD` 를 읽어라(작업 5 변경). 그다음 전체 코드를 리뷰하라: `git diff a753289..HEAD --stat` 로 이번 야간 작업 전체 범위를 확인하고 핵심 파일을 직접 읽어라.
   - chatbot/ifs_chatbot/: controller.py, scene_builder.py(v0), scene_builder_v1.py, jamo.py, clarify.py, drift.py, scene_spec.py, lexicon.py, config.py, session_log.py, eval/*.py
   - shared/lexicon/*.json, shared/schemas/*.json, shared/protocol/*.json
   - unity/Assets/IFS/Runtime/SceneSpec/*.cs, unity/Assets/IFS/Editor/**/*.cs, unity/Assets/IFS/Shaders/*, unity/Assets/IFS/Tests/**
   - 검증 결과: docs/validation/ (E2E 보고서, report.json, 스크린샷 목록), docs/acceptance.md 판정
2. 관점:
   - 정확성 버그(예외 경로, 경계값, null 처리, 인코딩, 결정성 깨짐, v0 바이트 동일성·폴백 경로).
   - AGENTS.md 원칙 위반(장면 속성에 LLM 사용, 말하지 않은 값 추론, 기본값과 미지정 혼동, 위기 후 LLM 호출, 외부 전송, 참여자 데이터·개인 경로 커밋, 고정 문구 변경 시 status/출처/버전 누락, 치료 표현).
   - 검증 보고의 신뢰성: E2E 결과 숫자가 실제 산출물(spec JSON, report.json, 로그)에서 재현되는지, Unity 적용값=spec 값 비교가 실제로 무엇을 비교하는지, 테스트가 의미 있는 것을 검사하는지(항상 통과하는 테스트).
   - 성능·VR(72fps) 관련 위험, 셰이더·조명 설정 문제.
   - 유지보수성은 중대한 것만.
3. 출력 형식: 지적 사항 번호 목록. 각 항목 [심각도: 높음/중간/낮음], 위치(파일:줄), 문제, 근거(재현 입력 또는 코드 경로), 제안. 마지막에 총평 3줄. 칭찬은 생략.
