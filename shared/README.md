# shared — 챗봇과 VR이 같이 쓰는 약속

| 파일 | 내용 | 누가 읽나 | 버전 키 |
| --- | --- | --- | --- |
| `schemas/interviewer_turn.schema.json` | 면담 LLM의 턴 JSON. 키 순서(위험 판단 → 행동 → 질문 틀 → 근거 인용 → 질문)를 지킨다 | 챗봇(Ollama `format`), 검증기 V1 | `x-schemaVersion` |
| `schemas/session_log.schema.json` | 세션 로그 elicit-log/0.1 | 챗봇이 쓰고, 분석·Unity가 읽음 | `logVersion` |
| `protocol/elicitation_protocol.v1.json` | 조건 1·2 단계 순서, 단계별 LLM 횟수, 고정 문구(IRB 대상), 질문 틀 6개, 차원 프로브, VR 단계 문구 | 챗봇 컨트롤러, Unity(VR 단계 문구) | `protocolVersion` |
| `lexicon/layer1_lexicon.v0.json` | 1층 사전: 참여자 말 → 장면 속성 (색채어·질감어·크기어·자세어·움직임어·신체부위어·감정어·차원어 …) | 검증기 V5(어휘 누출), 추출기 | `lexiconVersion` |
| `lexicon/safety_ko.v0.json` | 위기 키워드 3층(위기·모호·은유), 중단·넘어가기·판단 맡김 표현, 깊이 표지(L5) | 챗봇 안전 계층, `/api/guard/check` | `lexiconVersion` |
| `api/README.md` | HTTP API 명세 | 웹 데모, Unity | — |

## 고칠 때

- 버전을 올립니다. 세션 로그 머리말에 각 파일의 버전이 남아서, 어떤 사전·문구로 수집한 데이터인지 나중에 가릴 수 있습니다.
- 고정 문구의 `status`: `spec`은 노션 설계 문서 문구 그대로, `draft`는 이 저장소에서 쓴 초안입니다. IRB 제출 전에 draft를 모두 검토해야 합니다.
- 1층 사전의 `lemma`는 Kiwi 분석형(무거워요 → 무겁, 답답해요 → 답답)입니다. 항목마다 예시(`ex`)를 적으면 `chatbot/tests/test_lexicon.py`가 Kiwi로 확인합니다.
- 사전의 색 값(hsl)은 회색(노션 예시 출력)만 근거가 있고 나머지는 초안입니다. 렌더러 기준으로 다시 정해야 합니다.
- 참여자의 실제 응답 문장을 이 폴더에 넣지 않습니다. 사전에는 낱말만 넣습니다.
