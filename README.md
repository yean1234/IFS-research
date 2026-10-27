# IFS 심상화 연구 (IFS-research)

노션 「IFS 심상화 연구」에서 쓰는 개발 환경 저장소입니다.
IFS(Internal Family Systems)의 6F 절차 가운데 **Find → Focus → Flesh out**을 따라 참여자가 떠올린 마음속 형상을 **참여자 자신의 말로** 끌어내고, 확정된 말만 화이트박스 규칙으로 장면 속성(IFSSceneSpec)으로 바꿔 VR에서 보여 주는 연구입니다.

## 폴더 구조

연구 레포 하나를 폴더로 나눕니다.

```text
ifs-research/
├─ chatbot/      # Python 면담 서버 (컨트롤러·프롬프트·검증기·가드·로그)
├─ unity/        # VR 앱
├─ shared/       # 둘이 같이 쓰는 약속: 턴 JSON 스키마, 세션 로그 형식, 1층 사전, API 명세
└─ docs/
```

지금 들어 있는 것:

```text
IFS-research/
├─ README.md                  이 문서
├─ AGENTS.md                  코드 작업(사람·AI 에이전트 공통) 때 지킬 연구 원칙
├─ chatbot/                   Python 면담 서버 — 데모 실행법은 chatbot/README.md
│  ├─ ifs_chatbot/            controller · prompts · llm · validator · safety · extract · server · web/
│  ├─ prompts/v1.0.0/         시스템 프롬프트 v1.0(노션 원문) + 단계 블록 + 턴 문맥 틀
│  ├─ config/                 default.toml(개발 PC) · pilot.toml(연구 파일럿)
│  ├─ scenarios/              합성 대사 시나리오 12개(P07 스토리보드, 위기, 은유, 기억 서사 …)
│  ├─ tests/                  pytest (오프라인 97개 + 로컬 모델 12개)
│  └─ logs/ · reports/        세션 로그 · 시나리오 결과 (git에 올리지 않음)
├─ unity/                     VR 앱 자리 (README에 쓸 계약 정리)
├─ shared/
│  ├─ schemas/                interviewer_turn.schema.json (턴 JSON) · session_log.schema.json (elicit-log/0.1)
│  ├─ protocol/               elicitation_protocol.v1.json — 조건 1·2 단계 순서, 고정 문구, 질문 틀, 차원 프로브
│  ├─ lexicon/                layer1_lexicon.v0.json (1층 사전) · safety_ko.v0.json (위기·중단·깊이 표지)
│  └─ api/README.md           HTTP API 명세 (웹 데모·Unity 공용)
└─ docs/
   ├─ chatbot-design.md       노션 설계 → 구현 대응표, 문서끼리 다른 곳에서 고른 것, 확장한 것, 실험 결과, 열린 질문
   └─ ifs-knowledge.md        IFS 개념이 시스템 어디에 들어갔는지(범위 안·밖), 6F 문구 출처, 안전 근거
```

## 브랜치 규칙

브랜치는 기능 단위로만 잠깐 팝니다. `feat/chatbot-validator`에서 검증기를 만들고 `main`에 합치는 식입니다.

| 접두어 | 예 | 쓰임 |
| --- | --- | --- |
| `feat/` | `feat/chatbot-validator`, `feat/unity-calibration` | 기능 하나 |
| `fix/` | `fix/chatbot-josa` | 버그 하나 |
| `exp/` | `exp/model-compare-qwen` | 파일럿 비교처럼 결과만 남기고 버릴 수 있는 실험 |
| `docs/` | `docs/irb-phrases` | 문서·문구 |

- 브랜치 이름에 폴더 이름(`chatbot`, `unity`, `shared`)을 넣어 어디를 건드리는지 보이게 합니다.
- `main`은 항상 돌아가는 상태로 둡니다. 합치기 전에 `chatbot/`에서 `python -m pytest`가 통과해야 합니다.
- `shared/`를 바꾸는 브랜치는 그 파일의 버전을 올리고(예: `lexiconVersion` 0.1.0 → 0.2.0), 챗봇과 Unity 양쪽이 같이 맞춰질 때 합칩니다.
- 참여자 데이터(세션 로그, 자유 기술 응답)는 어떤 브랜치에도 올리지 않습니다. `.gitignore`가 `chatbot/logs/`, `chatbot/reports/`를 막고 있습니다.

## 지키는 원칙

- **LLM은 유도 단계에만 씁니다.** 장면 속성(색·크기·형태 …)은 정하지 않습니다. 동일한 확정 텍스트는 언제나 동일한 추출 결과를 냅니다. (설계 노트 §6)
- **참여자 말만 되돌려 묻습니다.** 질문 틀 6개에 참여자 단어를 끼우는 것만 LLM이 하고, 나가기 전에 검증기가 막습니다. 새 차원은 사전 등록한 고정 문구가 묻습니다.
- **로컬에서만 돌립니다.** 상용 API를 쓰지 않고, 서버는 기본으로 `127.0.0.1`에만 엽니다.
- **위기 대응은 LLM에 맡기지 않습니다.** 고정 문구로 109·1577-0199·연구자 연락처를 안내하고 멈춥니다.
- **치료가 아니라 자기성찰 보조입니다.** 추방자 작업·짐 내려놓기는 범위 밖입니다.

## 빠른 시작 (챗봇 데모)

```powershell
cd chatbot
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
ollama pull gemma4:e4b                                            # 개발용 모델 (연구용은 gemma4:31b)
ollama pull hf.co/mradermacher/kanana-safeguard-8b-GGUF:Q4_K_M     # 안전 분류 모델 (선택)
.venv\Scripts\python -m ifs_chatbot.server                        # http://127.0.0.1:8000
```

LLM 없이 흐름만 보려면 `--backend offline`, 조건 1만 보려면 웹 화면에서 "조건 1 · 정적 프롬프트"를 고릅니다. 자세한 내용은 [chatbot/README.md](chatbot/README.md)에 있습니다.

## 노션 출처

- 「앞으로 개발 방향」(2026-10-26) + 첨부 「P07의 25분 — IFS VR 세션 파이프라인」
- 「IFS 이론이란?」 > 챗봇 도입 (시스템 프롬프트 v1.0, 턴 JSON, 검증기 V1–V8, 세션 로그, 안전 L0–L5)
- 「교수님 공유 자료」 > IFS 심상화 설계 노트(2026-10-06) §2 6F 표준 문구, §6 조건 1·2
- 「인터렉션 디벨롭 리서치 — JSON→3D · 화이트박스 NLP」, 「심상 텍스트 3D 시각화 프로젝트」, 「사용자 프롬포팅 연구」 등
