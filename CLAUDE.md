@AGENTS.md

# 작업 방식 (Claude Code)

## 역할
- 메인(Fable): 계획, 설계 판단, 하위 에이전트·Codex 결과 판정, 최종 결정을 docs/decisions.md에 기록.
  큰 파일 읽기, 테스트·Unity 반복 실행, 로그 분석은 직접 하지 않고 하위 에이전트에 맡긴다.
- 하위 에이전트(Opus): 구현, 테스트 실행, 파일 탐색, 로그·report.json 분석.
  결과는 요약(바뀐 파일, 핵심 수치, 실패 내용)만 돌려준다. 원문 전체를 붙이지 않는다.

## GPT vs Claude 경쟁
- 설계가 갈리는 결정: Claude 하위 에이전트와 Codex에게 서로의 답을 보여 주지 않고 따로 안을 받는다.
  메인이 비교해서 하나를 고르고, 수용/반박/보류와 이유를 docs/decisions.md에 남긴다.
- 체크포인트마다 Codex 독립 검토:
  codex exec --sandbox read-only -c model_reasoning_effort="medium" -C . -o <임시>/cpN_last.md - < docs/codex-reviews/prompts/CPN_prompt.md
  프롬프트는 docs/codex-reviews/prompts/, 응답 원문은 docs/codex-reviews/CPN.md에 저장한다(로컬 절대 경로는 <repo>/로 바꾼다).
- Codex 호출은 작업 하나당 최대 3회.

## 토큰 절약
- 하위 에이전트에게는 목표, 관련 파일 경로, 완료 기준만 넘긴다.
- 이미 검토되고 기록된 지적은 Codex·하위 에이전트에 다시 보내지 않는다("이미 알고 있는 것" 절에 적는다).
- 같은 파일을 여러 번 읽지 말고, 필요한 부분만 grep으로 찾는다.
