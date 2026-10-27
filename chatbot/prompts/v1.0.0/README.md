# 프롬프트 v1.0.0

| 파일 | 내용 | 출처 |
| --- | --- | --- |
| `common.txt` | 공통 시스템 프롬프트 v1.0 (역할, 절대 규칙 11개, 질문 틀 6개) | 노션 「IFS 이론이란?」 > 챗봇 도입 > 3. 시스템 프롬프트 제약. 글자 그대로 옮김 |
| `stage_find.txt` · `stage_focus.txt` · `stage_flesh_out.txt` | 단계별 블록. 컨트롤러가 현재 단계 하나만 붙인다 | 같은 절의 "단계별 블록". 글자 그대로 옮김 |
| `context.txt` | 매 턴 user 메시지 틀(면담 기록, 현재 단계, 참여자 원문, 이미 한 질문, 재생성 사유) | 이 저장소에서 새로 씀 (contextTemplate 0.1) |

- 시스템 프롬프트 = `common.txt` + 빈 줄 + 현재 단계 블록.
- 세션 로그 `protocol.promptVersion`에 이 폴더 버전이, `protocol.promptSha256`에 네 파일 해시가 남는다.
- 문구를 바꾸면 폴더를 복사해 새 버전(`v1.0.1/` 등)을 만들고 `config/*.toml`의 `prompt_version`을 바꾼다. 이미 수집한 로그와 비교할 수 있게 기존 폴더는 고치지 않는다.
