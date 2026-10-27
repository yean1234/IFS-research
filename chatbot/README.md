# chatbot — IFS 유도 면담 서버

참여자가 떠올린 마음속 형상을 참여자 자신의 말로 조금 더 묘사하도록 묻는 면담 서버입니다.
노션 「앞으로 개발 방향」의 챗봇 구현 원리를 그대로 코드로 옮겼습니다.

> LLM은 "참여자 단어를 정해진 틀에 끼워 자연스러운 한국어 질문으로 만드는 일"만 합니다. 나머지는 전부 코드와 고정 문구가 맡습니다.

## 실행

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 로컬 모델 (Ollama)
ollama pull gemma4:e4b                                          # 개발 기본값. 연구 파일럿은 gemma4:31b (pilot.toml)
ollama pull hf.co/mradermacher/kanana-safeguard-8b-GGUF:Q4_K_M   # 안전 분류 모델. 없으면 키워드 사전만으로 검사

.venv\Scripts\python -m ifs_chatbot.server                      # 웹 데모 http://127.0.0.1:8000
.venv\Scripts\python -m ifs_chatbot.cli --debug                 # 터미널 (차단된 시도까지 보기)
```

| 하고 싶은 것 | 명령 |
| --- | --- |
| LLM 없이 흐름만 보기 | `python -m ifs_chatbot.server --backend offline` |
| 조건 1(정적 프롬프트) | 웹 화면에서 고르거나 `--condition static` |
| 연구 파일럿 설정 | `python -m ifs_chatbot.server --config pilot` (gemma4:31b, 가드 필수) |
| 다른 모델로 | `--model qwen3.5:9b` |
| 위기 안내에 연락처 넣기 | `--researcher-contact "연구자 OOO 010-…"` 또는 config의 `researcher_contact` |
| 테스트 | `python -m pytest` (오프라인), `$env:IFS_LIVE=1; python -m pytest -m live` (로컬 모델) |
| 모델 비교 | `python -m ifs_chatbot.simulate --model gemma4:e4b --model qwen3.5:9b --runs 3` |

## 한 턴이 도는 순서

```text
참여자 답 ─▶ L1 안전 검사(키워드 사전 + Kanana Safeguard) ─┬─ 위기 ─▶ 고정 문구(109·1577-0199·연구자) · 세션 중지 · LLM 끔
                                                          ├─ 은유·모호 ─▶ "지금 계속 이야기해도 괜찮으신가요?" [계속][그만]
                                                          └─ 안전 ─▶ 컨트롤러
컨트롤러: 지금 단계(Find/Focus/Flesh out)와 횟수를 보고 ─┬─ 고정 문구 차례 ─▶ 오프닝·위치·머물기·차원 프로브·확정
                                                        └─ LLM 차례 ─▶ ① 시스템 프롬프트 v1.0 + 단계 블록 + 인용 후보
                                                                       ② 로컬 LLM이 턴 JSON으로 답 (stage→risk→move→template→anchor→utterance)
                                                                       ③ 검증기 V1–V9 ─ 통과한 질문만 참여자에게
                                                                       ④ 걸리면 이유를 알려 주고 재생성(최대 2회) → 그래도 안 되면 고정 대체 문구
끝: 참여자 발화를 그대로 모은 확정 텍스트 [이대로 맞아요] ─▶ 추출 미리보기(1층 사전 + 직유 표지 + _provenance)
```

## 단계 순서

| 단계 | 조건 2 · AI 챗봇 면담 | 조건 1 · 정적 프롬프트 |
| --- | --- | --- |
| 안내 | AI 면담 보조자임을 알리고 중단 방법 안내 | 같음 |
| Find | 고정 오프닝 → 고정 위치 질문 → LLM 후속 최대 1회 (anything_else·like_what) | 고정 오프닝 → 고정 위치 질문 |
| Focus | 고정 "거기에 주의를 두고 잠시 머물러 보세요." (LLM 0회 — 스토리보드) | 같음 |
| Flesh out | LLM 최대 5회 (질문 틀 6개) | 고정 "지금 그것이 어떻게 있는지, 떠오르는 대로 적어 주세요." |
| 차원 프로브 | 아직 안 나온 차원만 고정 순서로: 크기·모양 → 색·밝기 → 움직임 | 같음 |
| 확정 | 참여자 말을 그대로 모은 텍스트를 보여 주고 [이대로 맞아요] / [고칠게요] | 같음 |

단계 순서·횟수·문구는 코드가 아니라 `shared/protocol/elicitation_protocol.v1.json`에 있습니다. Focus에 LLM 질문을 넣으려면 그 파일의 `maxTurns`를 바꿉니다.

## 모듈

| 파일 | 하는 일 |
| --- | --- |
| `controller.py` | 단계·횟수·고정 문구 vs LLM 결정, 안전 분기, 확정, 철회 |
| `prompts.py` · `prompts/v1.0.0/` | 공통 시스템 프롬프트 + 단계 블록 + 턴 문맥(면담 기록·참여자 원문·인용 후보·재생성 사유) |
| `anchors.py` | 참여자 원문에서 인용 후보(낱말·짧은 명사구)를 잘라 냄. 기억 서사 발화는 제외 |
| `llm.py` | Ollama 백엔드(JSON 스키마 강제, thinking 끔, digest 기록), 오프라인 대역, 테스트용 스크립트 |
| `validator.py` | V1 스키마 · V2 단계 · V3 인용 · V4 단일 질문 · V5 어휘 누출 · V6 금지 표현 · V7 질문 틀 · V8 출력 가드 · V9 깊이 제한 |
| `safety.py` | L1 키워드 사전 + 가드 모델(Kanana raw 프롬프트), 중단·넘어가기·판단 맡김·깊이 표지 |
| `lexicon.py` · `korean.py` | 1층 사전 매칭(Kiwi, 부정·변화 표시), 조사 선택, 인용 마스킹 |
| `extract.py` | 확정 텍스트 → 속성 후보 + `_provenance`, 직유 원천 명사, 사전 밖 단어(소실 정보율), bodyRelation, Find 첫 반응 양식 |
| `session_log.py` | elicit-log/0.1 세션 로그(턴마다 저장) |
| `server.py` · `web/` | FastAPI + 웹 데모(참여자 화면 / 연구자 화면) |
| `cli.py` · `simulate.py` | 터미널 데모, 시나리오 재생·모델 비교 |

## 로그

- `chatbot/logs/<세션ID>.json` — 형식은 `shared/schemas/session_log.schema.json`.
- 참여자에게 나가지 않은 시도(보이지 않은 턴)와 걸린 이유, 재생성 횟수, 고정 대체 여부, 가드 판정, 연구자 알림, 확정 텍스트, 추출 미리보기까지 남깁니다.
- 세션 ID는 가명만 받습니다(영문·숫자·`_`·`-`). 로그 폴더는 git에 올리지 않습니다.
- 참여자가 끝난 뒤 [응답 폐기]를 누르면 로그 파일을 지웁니다. 위기 대응으로 멈춘 세션은 안전 기록이라 연구자가 처리합니다.
- 암호화 저장(「IFS 이론이란?」 5절)은 아직 없습니다. 파일럿 전에 디스크 암호화나 별도 보관 절차가 필요합니다.

## 노션 설계에 덧붙인 것

모두 `docs/chatbot-design.md`에 근거와 실험 결과를 적었습니다.

- **인용 후보 제공**: 작은 모델이 참여자 문장을 통째로 인용해서, 컨트롤러가 원문에서 낱말·짧은 명사구를 잘라 프롬프트에 넣습니다.
- **V3 확장**: 3어절을 넘는 인용, 여러 어절 문장 통째 인용을 막습니다.
- **V5 엄격 모드**: 사전에 없는 새 내용어(질문 틀 밖의 말)도 막습니다.
- **V8 차등 판정**: 가드가 참여자 말 때문에 대화 전체를 위험으로 볼 때 면담자를 탓하지 않습니다.
- **V9 깊이 제한(L5)**: 기억·외상 서사 속 말을 인용하지 못하게 하고, 그 턴은 고정 문구로 지금 떠오른 것에 머물게 합니다.
- **신호 없는 hold**: 다시 만들게 합니다.
- **조건 1(정적 프롬프트)**: 같은 파이프라인에서 돌립니다(설계 노트 §6).
