# Codex CP3 검토 원문 (전체 코드 리뷰)

- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium" -C . -o <임시>/cp3_last.md - < docs/codex-reviews/prompts/CP3_prompt.md` (Git Bash, 저장소 루트)
- 시각: 2026-11-16 14:40:18 – 14:41:53 KST, 종료 코드 0, 재시도 없음. **Codex 3번 중 3번째(마지막) 호출.** 이후 호출하지 않음
- 대상: `git diff 58ba0dc..HEAD`(작업 5)와 야간 작업 전체(`a753289..HEAD`). CP3 커밋 5326ca9
- 프롬프트: 아래 「프롬프트」 절
- 아래 「응답 원문」은 `-o`로 받은 마지막 메시지입니다. 고친 것은 한 가지뿐입니다: 파일 링크 5곳에 들어 있던 로컬 절대 경로(개인 폴더 이름 포함)를 `<repo>/`로 바꿨습니다(decisions.md D06·D08, 공개 저장소).

## 프롬프트

````text
너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: IFS Find→Focus→Flesh out 면담 챗봇 → 확정 텍스트 → 화이트박스 규칙 매핑(SceneSpec JSON, v0 규칙 / v1 개선) → Unity VR 렌더. 초점은 심상-구현 일치도. 저장소 원칙은 AGENTS.md.
- 이번 CP3는 작업 5(중립 테스트 입력으로 챗봇→JSON→Unity 전 과정 실행 검증) 완료 시점이며, **전체 코드 리뷰**를 맡긴다.

## 이미 알고 있는 것 (되풀이하지 말 것)
- held-out 판정은 docs/validation/e2e/README.md 「판정」과 docs/acceptance.md 맨 아래 판정 표에 있다: AC-3.2·3.4·3.5 와 AC-4.5 미달, 전체 "완료 아님". 이 미달 자체를 다시 지적하지 말고, 그 판정·숫자가 산출물과 어긋나는 곳이나 빠뜨린 미달을 찾아라.
- 이전 검토(Claude 독립 검토 2건, Codex CP2)의 지적과 수용/반박/보류는 docs/decisions.md 뒤쪽 절들과 docs/codex-reviews/CP2.md 에 있다. 보류로 기록된 한계를 그대로 되풀이하지 말라.

## 할 일
1. `git diff 58ba0dc..HEAD --stat` 와 `git diff 58ba0dc..HEAD` 를 읽어라(작업 5 변경). 그다음 전체 코드를 리뷰하라: `git diff a753289..HEAD --stat` 로 이번 야간 작업 전체 범위를 확인하고 핵심 파일을 직접 읽어라.
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
````

## 응답 원문

````markdown
1. [심각도: 중간] 위치: [e2e.py](<repo>/chatbot/ifs_chatbot/eval/e2e.py:504), [BatchCapture.cs](<repo>/unity/Assets/IFS/Editor/BatchCapture.cs:90)  
   문제: E2E 재실행 때 현재 코퍼스에 없는 spec 파일을 발견해도 경고만 남기고 계속합니다. Unity 캡처는 spec 폴더의 `*.json`을 전부 읽으므로, 이전 실행의 잔여 파일도 새 보고서에 포함될 수 있습니다. 그러면 입력 수와 Unity 캡처 수가 달라지고, 비교가 현재 실행의 입력만 대상으로 하는지 불분명해집니다.  
   근거: 같은 `--out` 경로에서 먼저 큰 코퍼스를 실행한 뒤 일부 입력만 든 코퍼스로 실행하면 이전 spec 파일은 삭제되지 않고, Unity는 둘 다 캡처합니다.  
   제안: 현재 실행의 기대 파일 목록과 spec 폴더 파일 목록이 다르면 캡처·판정을 실패 처리하거나, 실행별로 새 spec 출력 폴더를 사용하십시오.

2. [심각도: 중간] 위치: [e2e.py](<repo>/chatbot/ifs_chatbot/eval/e2e.py:591), [BatchCapture.cs](<repo>/unity/Assets/IFS/Editor/BatchCapture.cs:781)  
   문제: `unity_section`은 보고서의 `ok`, 로드 수, 캡처 실패 수를 요약에 기록하지만, 기대 spec 목록과 대조해 실패를 종료 코드나 판정 오류로 처리하지 않습니다. 따라서 캡처가 일부 실패해도 E2E 명령은 성공 반환할 수 있고, 후속 자동화가 종료 코드만 보면 성공으로 오인할 수 있습니다.  
   근거: `BatchCapture`는 `loaded == fileCount`, `captureFailures == 0` 등을 기준으로 `ok`를 계산하지만, Python 쪽은 그 값을 검증하지 않고 `summary.json`과 결과 문서를 씁니다.  
   제안: 현재 실행의 spec별 결과가 각각 정확히 한 번 있고 모두 로드·캡처됐는지 확인한 뒤, 실패 시 명령도 실패 반환하도록 하십시오.

3. [심각도: 낮음] 위치: [e2e.py](<repo>/chatbot/ifs_chatbot/eval/e2e.py:57)  
   문제: Unity 로그 예외 탐지 정규식은 `System.Exception:`처럼 네임스페이스가 붙은 형식을 놓칠 수 있습니다. `^\w*Exception:`은 점(`.`)을 통과하지 못하므로, 로그 스캔의 “오류 패턴 0건”이 예외 부재를 보증하지 않습니다.  
   근거: `System.Exception: failure`는 `^\w*Exception:`에 매치되지 않습니다. 개별 spec의 Console 예외 집계가 이를 잡더라도, 로그 검사 결과는 별도로 거짓 음성이 될 수 있습니다.  
   제안: 예외 타입의 네임스페이스를 허용하는 패턴으로 바꾸고, 네임스페이스가 붙은 예외 로그 사례도 판별 대상에 포함하십시오.

총평: v0/v1 매핑과 Unity 적용값 수치 비교는 코드 경로상 명시적으로 연결되어 있습니다.  
E2E 산출물은 보고 중심이며, 오래된 spec과 캡처 실패를 자동으로 차단하지 않아 재실행·자동화 판정에 주의가 필요합니다.  
AGENTS.md의 LLM·위기 대응·참여자 데이터 원칙 위반은 이번에 확인한 변경 경로에서 발견하지 못했습니다.
````

## 분류 (수용 / 반박 / 보류) — 메인 세션 판정

| # | 지적 요지 | 판단 | 근거·처리 |
| --- | --- | --- | --- |
| 1 | e2e를 같은 출력 폴더에 다시 돌리면 이전 실행의 spec이 남아 Unity 캡처·보고서에 섞일 수 있음 | 수용 | 기대 spec 목록과 폴더의 실제 목록이 다르면 실패로 끝냄. 자동 삭제는 하지 않고 명시적 옵션을 줬을 때만 정리. **이번 held-out 실행은 해당 없음**: 새 폴더에 한 번 돌렸고 spec 60개 = 입력 30 × 매핑 2, Unity 로드 60, 독립 재실행에서도 같은 60개 |
| 2 | Unity report의 ok·로드 수·캡처 실패를 요약에 적기만 하고 검증하지 않아, 캡처가 실패해도 명령이 성공으로 끝남 | 수용 | report의 spec별 결과가 기대 목록과 일대일이고 모두 로드·캡처됐는지 확인해, 아니면 0이 아닌 종료 코드. 이번 실행의 report는 `ok=True`, 60/60, 캡처 실패 0(검토자가 직접 셈) |
| 3 | 로그 예외 탐지 정규식 `^\w*Exception:`이 `System.Exception:` 같은 네임스페이스 형식을 놓침 | 수용 | 패턴을 고치고 저장소의 캡처·EditMode 로그를 다시 스캔. AC-4.2의 확인 명령 정규식도 같이 고침 |

수용 3 · 반박 0 · 보류 0. 세 건 모두 검증 도구(e2e.py)의 견고성 문제이고 매핑·채점 결과를 바꾸지 않으므로 held-out 수치는 그대로입니다(decisions X13). Codex는 AGENTS.md 원칙 위반(LLM 사용, 위기 대응, 참여자 데이터)을 확인한 변경 경로에서 찾지 못했다고 적었습니다.

## 반영 결과 (2026-11-16)

| # | 바뀐 파일 | 무엇을 바꿨나 |
| --- | --- | --- |
| 1 | `chatbot/ifs_chatbot/eval/e2e.py`(0.2.0), `tests/test_e2e.py` | specs 폴더에 이번 실행이 만들지 않는 `*.json`이 있으면 아무것도 쓰지 않고 종료 코드 2로 멈춤. `--clean-specs`를 줬을 때만 이 스크립트 형식의 잔여 파일을 지움(`--unity-out`과 함께 쓸 수 없음) |
| 2 | 같은 파일 | Unity report를 기대 spec 목록과 일대일로 대조(빠짐·남음·중복·미로드·캡처 실패·PNG 없음·Console 오류), 적용값 미달·로그 문제까지 확인. 어긋나면 `summary.json`에 사유를 적고 종료 코드 1. 채점 지표의 AC 미달은 종료 코드에 넣지 않음(판정은 사람) |
| 3 | 같은 파일, `docs/acceptance.md` AC-4 확인 방법 | 예외 패턴 `^\w*Exception:` → `^[\w.]*Exception:`. 저장소 로그 재스캔: `capture.log` 0줄, `editmode.log` 0줄(`Exception`이 든 36줄은 모두 테스트 프레임워크의 `CaptureException` 스택 프레임) |

- 고친 e2e로 held-out을 임시 폴더에서 다시 돌려 `score/`·`specs/`·`schema.json`·`drift.json`·`applied_values.*`가 저장소 산출물과 바이트 동일함을 확인했습니다(종료 코드 0). 저장소의 결과 산출물은 0.1.0으로 만든 그대로 두었습니다.
- 메인 세션이 다시 잰 값: 오프라인 테스트 394 통과, held-out sha 그대로.
