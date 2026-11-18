# shared — 챗봇과 VR이 같이 쓰는 약속

| 파일 | 내용 | 누가 읽나 | 버전 키 |
| --- | --- | --- | --- |
| `schemas/interviewer_turn.schema.json` | 면담 LLM의 턴 JSON. 키 순서(위험 판단 → 행동 → 질문 틀 → 근거 인용 → 질문)를 지킨다 | 챗봇(Ollama `format`), 검증기 V1 | `x-schemaVersion` |
| `schemas/session_log.schema.json` | 세션 로그 elicit-log/0.1 | 챗봇이 쓰고, 분석·Unity가 읽음 | `logVersion` |
| `schemas/scene-spec.v2.json` | 장면 기술 SceneSpec v2. 확정 텍스트에서 만든 0–1 파라미터 + `_provenance`. 말하지 않은 슬롯은 null(스키마가 강제) | 챗봇이 쓰고(`scenes/{sessionId}.json`), Unity `SceneLoader`가 읽음 | `x-schemaVersion`, `meta.specVersion` |
| `protocol/elicitation_protocol.v1.json` | 조건 1·2 단계 순서, 단계별 LLM 횟수, 고정 문구(IRB 대상), 질문 틀 6개, 차원 프로브, VR 단계 문구 | 챗봇 컨트롤러, Unity(VR 단계 문구) | `protocolVersion` |
| `lexicon/layer1_lexicon.v0.json` | 1층 사전: 참여자 말 → 장면 속성 (색채어·질감어·크기어·자세어·움직임어·신체부위어·감정어·차원어 …) | 검증기 V5(어휘 누출), 추출기 | `lexiconVersion` |
| `lexicon/scene_params.v0.json` | SceneSpec v2 대응표: 1층 사전 값 → 0–1 장면 파라미터, 2층 직유 원천 명사 → 형태 프로토타입, 3층 V/A/D → 빈 슬롯 제안 | 장면 빌더 | `lexiconVersion` |
| `lexicon/vad_ko.v0.json` | 3층 감성사전: 1층 감정어 → V/A/D(0–1). 초안 값 | 장면 빌더(`_inferred`만) | `lexiconVersion` |
| `lexicon/safety_ko.v0.json` | 위기 키워드 3층(위기·모호·은유), 중단·넘어가기·판단 맡김 표현, 깊이 표지(L5) | 챗봇 안전 계층, `/api/guard/check` | `lexiconVersion` |
| `schemas/prereport.v0.2.json` | 보기 전 보고 ifs-prereport/0.2: 0.1에 첫 선택(firstValue·firstWidthM)·최종 선택, 크기 물리 폭 widthM(m), 무채색 {h: null, s: 0, l}, commitmentChangedAfterPick, 확정 때 고정한 장면 sha256을 더함. 서버가 쓰는 판 | 챗봇이 쓰고, `eval.ownership`이 같은 스키마로 검사 | `schema` |
| `schemas/prereport.v0.json` | (이전 판, 읽기만) 보기 전 보고 ifs-prereport/0.1: 속성마다 확정 여부(①②③)와 색{h,l}·크기 값, 장면 파일 sha256. ③이면 값 null(스키마가 강제). 장면 JSON과 분리 | 챗봇이 쓰고(`<log_dir>/<sessionId>/prereport.json`), `eval.ownership`이 읽음 | `schema` |
| `protocol/prereport_task.v0.3.json` | 보기 전 보고 과제 고정 문구 0.3: 0.2에 크기 안내 '동그라미 지름 = 떠올린 모습의 가장 넓은 가로 폭'을 더함(모두 draft·출처) | 챗봇 웹 `/prereport`, 첫 화면 연결 버튼 | `taskVersion` |
| `protocol/prereport_task.v0.2.json` | (이전 판) 보기 전 보고 과제 고정 문구 0.2: 화면에 나오는 모든 문구(연결 버튼·이미 받음·열 수 없음·답 바꾸기·화면 읽기 이름 포함, 모두 draft·출처), 무채색 띠, 손잡이 없는 막대 | 챗봇 웹 `/prereport`, 첫 화면 연결 버튼 | `taskVersion` |
| `protocol/prereport_task.v0.json` | (이전 판, 0.1 기록이 가리킴) 보기 전 보고 과제 고정 문구(모두 draft, IRB 대상), 색 면·크기 막대 설정. 면담(질문 틀·V1–V9) 밖 | 챗봇 웹 `/prereport` | `taskVersion` |
| `api/README.md` | HTTP API 명세 | 웹 데모, Unity | — |

## 고칠 때

- 버전을 올립니다. 세션 로그 머리말에 각 파일의 버전이 남아서, 어떤 사전·문구로 수집한 데이터인지 나중에 가릴 수 있습니다.
- 고정 문구의 `status`: `spec`은 노션 설계 문서 문구 그대로, `draft`는 이 저장소에서 쓴 초안입니다. IRB 제출 전에 draft를 모두 검토해야 합니다.
- 1층 사전의 `lemma`는 Kiwi 분석형(무거워요 → 무겁, 답답해요 → 답답)입니다. 항목마다 예시(`ex`)를 적으면 `chatbot/tests/test_lexicon.py`가 Kiwi로 확인합니다.
- 사전의 색 값(hsl)은 회색(노션 예시 출력)만 근거가 있고 나머지는 초안입니다. 렌더러 기준으로 다시 정해야 합니다.
- 참여자의 실제 응답 문장을 이 폴더에 넣지 않습니다. 사전에는 낱말만 넣습니다.
