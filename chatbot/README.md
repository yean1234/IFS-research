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
| 본 실험(v4 흐름 + 다리 질문 + 설계 뼈대 3절 권고값) | `python -m ifs_chatbot.server --config experiment` — 세션 전체 순서는 `docs/run-experiment.md` |
| 다른 모델로 | `--model qwen3.5:9b` |
| 위기 안내에 연락처 넣기 | `--researcher-contact "연구자 OOO 010-…"` 또는 config의 `researcher_contact` |
| 테스트 | `python -m pytest` (오프라인), `$env:IFS_LIVE=1; python -m pytest -m live` (로컬 모델) |
| 모델 비교 | `python -m ifs_chatbot.simulate --model gemma4:e4b --model qwen3.5:9b --runs 3` |
| 소유감 실험 기록 요약 | `python -m ifs_chatbot.eval.ownership --records <기록 루트> --out <폴더>` (형상·세션 CSV + RQ1–RQ3 기술 통계, 기록 0.3이면 같은 말·다른 값 쌍과 세션 폴더의 `prereport.json`으로 shift_pairs.csv·가까운−먼 요약, 기록은 저장소 밖) |

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
                                                        └─▶ SceneSpec v2 → logs/scenes/{세션ID}.json ─▶ Unity SceneLoader
```

## 단계 순서

| 단계 | 조건 2 · AI 챗봇 면담 | 조건 1 · 정적 프롬프트 |
| --- | --- | --- |
| 안내 | AI 면담 보조자임을 알리고 중단 방법 안내 | 같음 |
| Find | 고정 오프닝 → 고정 위치 질문 → LLM 후속 최대 1회 (anything_else·like_what) | 고정 오프닝 → 고정 위치 질문 |
| Focus | 고정 "거기에 주의를 두고 잠시 머물러 보세요." (LLM 0회 — 스토리보드) | 같음 |
| Flesh out | LLM 최대 5회 (질문 틀 6개) | 고정 "지금 그것이 어떻게 있는지 떠오르는 대로 적어 주세요." |
| 차원 프로브 | 아직 안 나온 차원만 고정 순서로: 크기·모양 → 색·밝기 → 움직임 | 같음 |
| 확정 | 참여자 말을 그대로 모은 텍스트를 보여 주고 [이대로 맞아요] / [고칠게요] | 같음 |

단계 순서·횟수·문구는 코드가 아니라 `shared/protocol/elicitation_protocol.v1.4.json`(기본 설정, 1.4.0)에 있습니다. Focus에 LLM 질문을 넣으려면 그 파일의 `maxTurns`를 바꿉니다.

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
| `extract.py` | 확정 텍스트 → 속성 후보 + `_provenance`, 직유 원천 명사, 사전 밖 단어(소실 정보율), bodyRelation, Find 첫 반응 양식 (세션 로그의 추출 미리보기) |
| `scene_builder.py` · `scene_spec.py` | 확정 텍스트 → SceneSpec v2(0층 Kiwi · 1층 사전 · 2층 직유 · 3층 V/A/D 제안) → `logs/scenes/{sessionId}.json`. 형식 검사·원칙 검사 |
| `session_log.py` | elicit-log/0.1 세션 로그(턴마다 저장) |
| `server.py` · `web/` | FastAPI + 웹 데모(참여자 화면 / 연구자 화면) |
| `selection.py` · `web/stage.js` | 새 흐름(`--config v4`)의 면담 뒤 단계: 후보 선택 · 조절 · 사전 측정(문구 `shared/protocol/selection_protocol.v0.json` 0.6.0, 사전 측정 10문항, 모두 draft) |
| `postinterview.py` · `web/postinterview.js` | 사후 면담 기록 화면(G59, 연구자용, `/?view=postinterview&session=<세션 ID>`). 문항 `shared/protocol/post_interview.v0.json`, 대본 `docs/post-interview-guide.md`. LLM 없음 |
| `cli.py` · `simulate.py` | 터미널 데모, 시나리오 재생·모델 비교 |

## 로그

- `chatbot/logs/<세션ID>.json` — 형식은 `shared/schemas/session_log.schema.json`.
- `chatbot/logs/scenes/<세션ID>.json` — 확정 텍스트에서 만든 장면 기술(SceneSpec v2). Unity가 읽는다. 형식은 `shared/schemas/scene-spec.v2.json`.
- 참여자에게 나가지 않은 시도(보이지 않은 턴)와 걸린 이유, 재생성 횟수, 고정 대체 여부, 가드 판정, 연구자 알림, 확정 텍스트, 추출 미리보기까지 남깁니다.
- 세션 ID는 가명만 받습니다(영문·숫자·`_`·`-`). 로그 폴더는 git에 올리지 않습니다.
- 참여자가 끝난 뒤 [내 답 지우기]를 누르면 로그 파일을 지웁니다. 위기 대응으로 멈춘 세션은 안전 기록이라 연구자가 처리합니다.
- 암호화 저장(「IFS 이론이란?」 5절)은 아직 없습니다. 파일럿 전에 디스크 암호화나 별도 보관 절차가 필요합니다.

## 보기 전 보고 과제 (`/prereport?session=<id>`)

확정 텍스트 뒤, 형상을 보기 전에 속성마다 ①②③과 색·크기 값을 한 번 받습니다(문구 `shared/protocol/prereport_task.v0.3.json`,
형식 `shared/schemas/prereport.v0.2.json`, 면담·검증기 밖, LLM 없음). 기록은 `logs/<sessionId>/prereport.json`이고
장면 JSON에는 들어가지 않습니다. 장면 파일 sha256은 확정 때 고정한 값을 붙입니다.

**철회 절차.** [내 답 지우기](이전 이름 [응답 폐기])는 챗봇 쪽 세션 로그·장면 파일·`logs/<sessionId>/prereport.json`만 지웁니다. Unity 러너가
기록 폴더(`…/ownership/P###/<sessionId>/<UTC>/prereport.json`)에 복사한 사본과 그 기록 폴더, 그리고 분석 출력
(`stimuli.csv`·`sessions.csv`·`shift_pairs.csv`·`summary.json`)은 연구자가 직접 지우고 분석을 다시 돌려야 합니다.
분석을 다시 돌릴 때는 철회한 세션 ID를 한 줄에 하나씩 적은 파일을 넘깁니다:
`python -m ifs_chatbot.eval.ownership --records <기록 루트> --out <저장소 밖 폴더> --withdrawn <철회 목록.txt>`.
그 세션의 기록 폴더는 평정·보고를 읽기 전에 빠지고 summary에는 개수(`records.withdrawn`)만 남습니다. 출력 폴더가 git
저장소 안이고 무시 규칙에 걸리지 않으면 분석기가 경고합니다.
이 파일들은 저장소 밖에 두며, 저장소 안에 복사돼도 `.gitignore`가 막습니다(합성 fixture는 `tests/fixtures/` 아래
`*.synthetic.json` 또는 `manifest_*.json` 이름만 씁니다).

**한계.**
- 웹 크기 막대의 원은 기본 지름 0.35 m(Unity 프리미티브 대체 크기) × 2^((s − 0.5) × 4)로 그립니다. 웹은 프리팹 실제 크기나
  자세 스케일(웅크림·납작·곧음)을 모르므로, 같은 s가 Unity 화면에서 다른 물리 크기일 수 있습니다. 그래서 보고에 원의 실제
  길이 `widthM`을 함께 남기고, 분석기는 manifest의 `wM`·`loM`·`hiM`(Unity가 그린 가장 넓은 가로 폭)이 있으면 log(미터)로
  비교합니다. 없으면 0–1 눈금으로 비교하고 `size_scale_fallback`을 표시합니다. Unity의 `wM`도 셰이더 굴곡과 프리팹 실제
  크기는 포함하지 않는 명목값입니다.
- 색 면은 채도 0.6 고정입니다. 회색은 오른쪽 무채색 띠로 고릅니다(`{h: null, s: 0, l}`).
- '보기 전'의 증거는 Unity 러너가 첫 제시 전에 보고를 기록 폴더로 복사하고 그 sha256을 `manifest.prereport`에 남긴
  사실입니다. 분석기는 이 해시가 없거나 맞지 않으면 `report_spec_mismatch`로 뺍니다. 보고 시각(`createdAtUtc`)과
  `events.csv`의 `first_viewing_utc` 비교는 두 기계의 시계가 다를 수 있어 경고(`report_clock_warning`)로만 씁니다.

## 노션 설계에 덧붙인 것

모두 `docs/chatbot-design.md`에 근거와 실험 결과를 적었습니다.

- **인용 후보 제공**: 작은 모델이 참여자 문장을 통째로 인용해서, 컨트롤러가 원문에서 낱말·짧은 명사구를 잘라 프롬프트에 넣습니다.
- **V3 확장**: 3어절을 넘는 인용, 여러 어절 문장 통째 인용을 막습니다.
- **V5 엄격 모드**: 사전에 없는 새 내용어(질문 틀 밖의 말)도 막습니다.
- **V8 차등 판정**: 가드가 참여자 말 때문에 대화 전체를 위험으로 볼 때 면담자를 탓하지 않습니다.
- **V9 깊이 제한(L5)**: 기억·외상 서사 속 말을 인용하지 못하게 하고, 그 턴은 고정 문구로 지금 떠오른 것에 머물게 합니다.
- **신호 없는 hold**: 다시 만들게 합니다.
- **조건 1(정적 프롬프트)**: 같은 파이프라인에서 돌립니다(설계 노트 §6).
