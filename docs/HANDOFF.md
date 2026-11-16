# HANDOFF — 야간 작업 인수인계 (새 세션은 이 파일 하나만 읽고 이어서 진행)

> 마지막 갱신: 2026-11-16 (계정 전환 뒤 새 세션) · 갱신자: 오케스트레이터(Claude Fable 5.2, 세션 edd117bf)
> 모델 배정(decisions.md D09): 메인 세션(판단·검토 반영 분류·AC 판정·보고서)은 Fable, Workflow 서브에이전트(구현·테스트 실행·검토·수정)는 `model: 'opus'`로 지정.
> 이 파일은 단계가 끝날 때와 최소 30분마다 갱신하고, 갱신 때마다 WIP 커밋을 남깁니다.

## 0. 이어받으면 맨 처음 할 것 (확인 명령)

PowerShell 기준입니다(Git Bash도 가능). 모든 명령은 저장소 루트(이 파일이 있는 저장소의 최상위 폴더, 원본 PC의 D 드라이브 연구 폴더 아래 `IFS-research`)에서 실행합니다. 개인 경로가 공개 저장소에 남지 않도록 절대 경로는 적지 않습니다.

```powershell
git branch --show-current                     # overnight/2026-11-16-imagery-fidelity 여야 함
git log --oneline -8                          # 마지막 커밋 확인 (아래 2절과 비교)
git status --short                            # 커밋 안 된 변경 확인
# 보류(held-out) 코퍼스가 바뀌지 않았는지 (sha256이 아래 값이어야 함)
(Get-FileHash chatbot\tests\fixtures\imagery_corpus\heldout.json -Algorithm SHA256).Hash
#   → F8D38EF5877C09BD899EE7CBADD491BE5F2DFB8FFAF97169C1163AD716350D55
# 오프라인 테스트 (LLM·네트워크 없이)
cd chatbot; .\.venv\Scripts\python.exe -m pytest -q -m "not live"; cd ..
# 개인 정보·절대 경로가 들어가지 않았는지 (결과가 비어야 함; <사용자폴더명>은 원본 PC 경로의 개인 폴더 이름)
git grep -n -I "<사용자폴더명>"
```

- 이전 세션의 Workflow(백그라운드 서브에이전트 묶음)는 **다른 세션에서 재개할 수 없습니다.** 이전 세션이 끊겼다면 4절 "진행 중"의 작업은 git 상태를 보고 남은 부분만 새로 시키면 됩니다.
- 커밋은 오케스트레이터(이 파일을 읽은 당신)만 합니다. 병렬 서브에이전트에게는 커밋을 시키지 않습니다(decisions.md D05).
- **push 하지 않고 main에 합치지 않습니다.** 원격 저장소가 공개(public)라 외부 배포에 해당합니다. 아침에 사람이 검토 후 PR.

## 1. 사용자가 처음 준 지시 (원문 그대로)

~~~~text
ultracode

# 무인 실행 (중요)
- 나는 자는 중이라 질문에 답할 수 없어. 멈추지 말고, 모호한 건 가장 합리적인 쪽으로 결정한 다음 docs/decisions.md에 "결정 / 이유 / 다른 선택지"로 기록하고 계속 진행해.
- 되돌리기 어려운 작업(파일 대량 삭제, 외부로 배포, 유료 API 결제 등)만 하지 말고 docs/morning-todo.md에 남겨둬.
- 시작 전에 git 저장소인지 확인하고, 아니면 git init 해줘. 그리고 현재 상태를 "baseline" 커밋으로 남겨서 언제든 되돌릴 수 있게 해줘.

# 연구 맥락
- IFS 이론의 Find→Focus→Flesh out 단계를 따라가는 면담 챗봇과 VR(Unity)을 연결하는 연구야.
- 심리적 아픔은 다루지 않아. 대신 "사용자가 마음속에 떠올린 심상을 VR 공간에 얼마나 일치하게 구현하는가(심상-구현 일치도)"에 초점을 맞춰. IRB 없이 한국HCI학회에 투고하는 게 목표고, 마감은 12/2야.
- 현재 챗봇은 사용자 답변을 규칙 기반으로 JSON에 매핑해서 Unity로 넘겨. 시작 전에 저장소 구조부터 파악해.

# 작업
1. 측정·평가 설계: 선행연구(심상 생생함 척도, VR 프레즌스, 심상-시각화 일치도 평가, 사용성 등)를 조사해서 가설, 측정할 사용자 행동(수정 요청 횟수, 만족까지 걸린 시간, 속성별 일치 평가 등), 측정 도구, 분석 방법을 정리해줘. "규칙 기반 vs 개선된 매핑"을 실험 비교 조건으로 쓸 수 있는지도 검토해줘. → docs/research-design.md, 완료 기준은 docs/acceptance.md
2. 심상 유지 판단: 사용자가 처음 떠올린 심상을 대화 내내 유지하는지 판단할 방법을 설계하고 구현해줘. 예를 들어 단계별 속성 스냅샷 비교로 심상 표류(drift)를 감지하거나, 회상 확인 질문을 넣거나, 자기보고를 받는 방법이 있어. 판단 기준은 수치로 정의해줘.
3. 매핑 고도화: 규칙 기반 매핑이 사용자 표현을 놓치거나 왜곡하는 사례를 먼저 찾아서 기록해줘. 그다음 자유 입력을 최대한 반영하도록 개선해줘. 예를 들어 LLM 구조화 추출과 스키마 검증, 임베딩 유사도 매칭, 매핑하지 못한 표현을 원문 그대로 보존하기, 확인 질문 루프 같은 방법이 있어. 기존 규칙 기반 방식은 비교 조건 겸 실패 시 대체 경로로 남겨둬.
4. Unity 현실감: 조명, PBR 재질, 스케일 기준, 환경과 스카이박스, 후처리를 개선하되 VR 프레임레이트(72fps 이상)를 유지해줘.
5. 실행 검증: 감정적 고통이 없는 중립적인 심상 설명(색, 모양, 크기, 위치, 재질, 움직임 등)으로 테스트 입력 20~30개를 만들어. 자유 서술형도 포함해줘. 이걸로 챗봇 → JSON → Unity 전 과정을 실제로 돌려보고 속성 반영률, 오류, 로그를 보고해줘. Unity는 batchmode나 PlayMode 테스트로 실행하고, 가능하면 스크린샷까지 확인해줘. 실행할 수 없는 부분은 docs/morning-todo.md에 체크리스트로 남겨줘.

# 역할 분리
- 실행자: 구현을 맡는 서브에이전트.
- 검토자: 실행자와 컨텍스트가 분리된 서브에이전트. 실제 코드와 실행 결과만 보고 판단해.
- 판정자: docs/acceptance.md의 기준과 테스트 결과. 이 기준을 통과했을 때만 "완료"라고 해.

# GPT(Codex) 감시자 — 팀 공용 계정이라 정확히 3번만 호출
- Codex 플러그인의 슬래시 명령이나 리뷰 게이트는 쓰지 마. 대신 터미널에서 codex exec을 직접 실행해. 먼저 `codex exec --help`로 옵션을 확인해.
- 매번 읽기 전용 샌드박스(--sandbox read-only)로, 추론 강도는 medium(-c model_reasoning_effort="medium")으로 실행해. 프롬프트가 길면 파일로 만들어서 넘겨.
- 각 호출 전에 해당 단계까지의 작업을 커밋하고, Codex에게는 "git diff <이전 체크포인트 커밋>..HEAD와 관련 문서를 읽고 검토하라"고 지시해.
- 호출 시점은 아래 3번뿐이야. 그 외에는 어떤 이유로도 호출하지 마. 실패해도 재시도는 1번까지만 해.
  - CP1 (작업 1 완료 후): 가설·측정 지표·평가 방법이 심상-VR 일치도를 타당하게 검증하는지, 빠진 교란변수와 과장된 주장 위주로 비판하게 해.
  - CP2 (작업 2·3 완료 후): 자유 입력→JSON 매핑이 원래 표현을 잃거나 왜곡하는 경우와 심상 유지 판단 기준의 허점 위주로 비판하게 해.
  - CP3 (작업 5 완료 후): 전체 코드 리뷰를 맡겨.
- Codex 출력은 docs/codex-reviews/CP1.md, CP2.md, CP3.md에 원문 그대로 저장해. 지적 사항은 "수용 / 반박(근거) / 보류" 표로 정리하고, 수용한 것만 반영해. 반영이 끝나면 커밋해.
- Codex 사용 한도 에러가 나면 더 시도하지 말고 그 체크포인트는 Claude 검토자로 대체해. 그 사실을 기록해줘.

# 원칙
- 선행연구는 실제로 존재를 확인한 것만 인용해. 확인하지 못한 건 [확인 필요]로 표시하고, 저자·연도·제목을 지어내지 마.
- 12/2 마감을 고려해서 MVP를 먼저 만들고 개선은 그다음에 해.
- 끝나면 docs/morning-report.md에 정리해줘: 바뀐 파일, 검증 결과(숫자), Codex 지적과 처리 결과, 남은 리스크, 내가 아침에 확인할 것.
~~~~

추가 지시(2026-11-16 12:05, 원문 요지): 작업은 멈추지 말고 진행. 사용량 한도로 다른 계정 새 세션에서 이어갈 때를 대비해 이 HANDOFF.md를 만들고, 단계가 끝날 때마다·최소 30분마다 갱신하며, 진행 중 작업도 그때마다 WIP 커밋으로 남길 것.

## 2. 브랜치·커밋

- 브랜치: `overnight/2026-11-16-imagery-fidelity` (main에서 분기, main은 건드리지 않음)
- 체크포인트 커밋:
  - `a753289` baseline
  - `d4e3e3a` CP1 (작업 1 + 작업 3 전반 실패 사례·채점기 + 작업 4 Unity)
  - `46199cc` CP2 반영(Codex CP2 수용 항목. 오프라인 363 통과)
  - `58ba0dc` CP2 (작업 2 drift 1.1.0 + 작업 3 매핑 빌더 1.2.0·채점기 0.3.0, 독립 검토 반영)
- 마지막 커밋: `git log -1` 로 확인. 이 파일 갱신과 함께 WIP 커밋이 쌓입니다(메시지 접두어 `WIP:`).
  WIP 커밋은 체크포인트가 아니므로, Codex에게 줄 diff 기준점은 항상 위 체크포인트 커밋을 씁니다.

## 3. 진행 체크리스트

### 작업
- [x] 0. baseline 커밋, 저장소 구조 파악
- [x] 1. 측정·평가 설계 → `docs/research-design.md`, `docs/acceptance.md`(AC-1..AC-7, RD-1..8). CP1 지적 11건 반영 완료(커밋 전, WIP에 포함)
- [x] 2. 심상 유지(drift) 판단 — 구현·독립 검토·수정 끝(drift 1.1.0, AC-2 잠정 통과). CP2 대기
  - [x] 정답 라벨 18개 `chatbot/tests/fixtures/drift/drift_cases.json` (drift 9 / no_drift 9, 유형 a–k, 경계 3)
  - [x] 구현 `chatbot/ifs_chatbot/drift.py`, `tests/test_drift.py`, 컨트롤러 단계별 스냅샷, `shared/protocol/elicitation_protocol.v1.1.json`(회상 확인·자기보고 1–7 초안, status=draft), `docs/drift-design.md`, research-design 4.5절, acceptance AC-2
  - [x] 독립 검토 → 수정
- [x] 3. 매핑 고도화 (독립 검토·수정 끝, 빌더 1.2.0. dev: 반영률 0.937, 왜곡 0.000, 미반영 원문 보존 1.000(구조적), 퍼지 경로 값 0)
  - [x] 실패 사례 기록 `docs/mapping-failures.md`(45건), 채점기 `chatbot/ifs_chatbot/eval/fidelity.py`(v0.2.0), `eval/corpus_run.py`
  - [x] v1 매퍼 `chatbot/ifs_chatbot/scene_builder_v1.py` + `jamo.py` + `clarify.py`, 사전 `shared/lexicon/*.v1.json`, 스키마 `shared/schemas/scene-spec.v2.1.json`, Unity 파서 2.0/2.1, config `[mapping] mode=v1, save_both=true, clarify_loop=false`, v1 예외 시 v0 폴백. dev: 반영률 0.573→0.937, 왜곡 0.165→0.000, 미반영 원문 보존 0.130→1.000 (dev는 규칙 작성에 쓴 세트라 낙관적)
  - [x] 독립 검토 → 수정
- [x] 4. Unity 현실감 (Linear, VR PC/VR Quest 품질 단계, 무채색 하늘·바닥 1 m 격자·그림자 1개, 후처리 없음, 배치 캡처). EX01/EX02 p95 ≤ 2.01 ms(데스크톱 대리 측정). 기기 72 Hz 측정은 morning-todo
- [ ] 5. 실행 검증(E2E) — **남음** (5절 참고)
- [ ] docs/morning-report.md — **남음**

### Codex 체크포인트 (정확히 3번, 실패 시 재시도 1번)
- [x] CP1 — 1회 사용. 원문+분류표 `docs/codex-reviews/CP1.md`. 수용 11 / 보류 1(#12 인용 원문 대조, 사람)
- [x] CP2 — 1회 사용(2026-11-16 13:55, 종료 코드 0). 원문+분류표 `docs/codex-reviews/CP2.md`. 수용 6 · 일부 수용 2 · 반박 1 · 일부 반박·보류 1 · 보류 2. 지시문 `docs/codex-reviews/prompts/CP2_prompt.md`
- [ ] CP3 — 미사용. 지시문 `docs/codex-reviews/prompts/CP3_prompt.md` (`<CP2_COMMIT>` = `58ba0dc`)

**Codex 사용 현황: 3번 중 2번 사용(CP1, CP2), 남은 1번(CP3).** 다른 계정으로 넘어가도 이 횟수는 이어집니다. 이 외 용도로 절대 호출하지 마세요.

Codex 실행 명령(Git Bash, 저장소 루트에서. CP1 때 쓴 것과 같은 형식):
```bash
codex exec --sandbox read-only -c model_reasoning_effort="medium" -C . -o /tmp/cpN_last.md - < docs/codex-reviews/prompts/CPN_prompt.md
```
- 출력 원문을 `docs/codex-reviews/CPN.md`에 저장(맨 위에 실행 명령·시각·종료 코드, 그 아래 지시문, 그 아래 원문). 그 뒤에 "수용 / 반박(근거) / 보류" 표를 붙이고, 수용한 것만 반영 후 커밋.
- 사용 한도 에러면 재시도하지 말고 Claude 검토자(별도 서브에이전트, 같은 지시문)로 대체하고 그 사실을 CPN.md와 decisions.md에 기록.

## 4. 지금 진행 중인 것 (계정 전환 뒤 세션 edd117bf 기준)

- 끝: 2단계, Codex CP2와 반영(커밋 `46199cc`). 오프라인 363 통과, drift 라벨 정확도 1.000, held-out sha 그대로.
- **진행 중: 3단계 Workflow(이 세션 내부, opus, 순차)**: ① E2E 실행자 — held-out 30개 재생 → v0·v1 spec → 스키마 검증 → 채점 → Unity 배치 캡처 60개 → 적용값 대조 → `docs/validation/e2e/`, 전 과정 스크립트(`chatbot/ifs_chatbot/eval/` 아래), acceptance.md의 "(구현 후 확정)" 채움. ② 독립 재현 검토자(읽기 전용).
- **동결:** 매핑 규칙·채점 판정·drift·코퍼스는 CP2 반영 커밋 뒤로 고치지 않음. held-out 결과를 본 뒤에는 어떤 것도 조정하지 않고 미달이면 숫자 그대로 보고(D04).
- 끊겼다면: `git status`로 `docs/validation/e2e/`와 새 스크립트가 어디까지 됐는지 보고, 남은 것만 새 서브에이전트(opus)에 맡김(5절 4번). held-out 채점이 이미 한 번 됐으면 같은 명령의 재실행(재현)만 함. 그다음 메인 세션이 AC를 하나씩 판정 → CP3 커밋 → Codex CP3(마지막 1번, `<CP2_COMMIT>` = `58ba0dc`) → 반영 → morning-report.
- 모델 배정(D09): 판단·분류·판정·보고서는 메인 세션(Fable), 구현·테스트 실행·검토·수정 서브에이전트는 opus.

## 5. 다음에 할 일 (순서대로)

1. **2단계 결과 정리**: 결과 확인 → 결정 사항을 `docs/decisions.md`에, 사람이 할 일을 `docs/morning-todo.md`에 병합 → 개인 폴더명 `git grep` 결과 0 → 오프라인 테스트 전체 통과 → held-out sha 그대로인지 확인.
2. **CP2 커밋** (`CP2: 심상 유지 판단·개선 매핑 v1 …`). 이 해시를 이 파일 2절에 기록.
3. **Codex CP2** (2번째 호출): `docs/codex-reviews/prompts/CP2_prompt.md` 사용 → `docs/codex-reviews/CP2.md` 저장 → 분류표 → 수용 항목 반영(서브에이전트) → 테스트 → 커밋.
4. **3단계(작업 5, E2E)**:
   - held-out 30개(`chatbot/tests/fixtures/imagery_corpus/heldout.json`)를 실제 컨트롤러(조건 1 정적, LLM 없음)로 재생 → 확정 텍스트 → v0·v1 SceneSpec JSON. 도구: `python -m ifs_chatbot.eval.corpus_run`, 채점 `python -m ifs_chatbot.eval.fidelity --compare <module:factory>` (먼저 `--check-corpus heldout.json`).
   - 스키마 검증 100%, Unity 배치 캡처로 모든 spec 로드·스크린샷, Unity 적용값 = spec 값(|Δ| ≤ 1e-6) 확인, 로그 수집.
   - Unity 명령(`-nographics`·`-quit` 쓰지 않음, 경로는 상대 경로로):
     `"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run -specDir <dir> -outDir <dir> -logFile <log>`
   - 결과 문서는 `docs/validation/` 아래, 독립 검토자가 숫자 재현 확인. 그다음 acceptance.md의 AC를 하나씩 판정하고 "(구현 후 확정)" 자리를 실제 경로로 채움.
   - 주의: held-out 반영률은 v1 ≥ 0.75 그리고 ≥ v0 + 0.15, 왜곡 ≤ 0.05 그리고 ≤ v0(AC-3). 미달이면 숫자 그대로 보고하고 held-out 보고 고치지 않음(과적합 금지, D04).
5. **CP3 커밋** → **Codex CP3**(3번째, 마지막) → CP3.md·분류표 → 반영 → 커밋.
6. **`docs/morning-report.md`** 작성: 바뀐 파일, 검증 숫자, Codex 지적과 처리, 남은 리스크, 아침에 확인할 것 → 최종 커밋. 모든 AC 통과 시에만 "완료", 아니면 실패 항목과 숫자를 보고.

## 6. 참고

- **주요 결정은 `docs/decisions.md`** (D01–D07, C1–C6, R1–R9, F1–F4, U1–U9, 이후 추가분). 사람이 할 일·결정은 `docs/morning-todo.md`.
- 완료 기준(판정자): `docs/acceptance.md`. 연구 설계: `docs/research-design.md`. 매핑: `docs/mapping-failures.md`, `docs/mapping-v1.md`, `docs/scene-spec-mapping.md`. Unity: `docs/validation/unity/`.
- 원칙(AGENTS.md) 중 이번 작업에서 자주 걸리는 것: 장면 속성 추출에 LLM·임베딩 금지(원칙 1, D03), 말하지 않은 값 추론 금지·기본값과 미지정 구분(원칙 2), 고정 문구는 `shared/protocol`에 status·출처·버전(원칙 7), 참여자 데이터·개인 경로 커밋 금지(원칙 6), 외부 API·CDN 금지(원칙 5).
- 환경 메모:
  - Python venv: `chatbot\.venv\Scripts\python.exe`. 오프라인 테스트: `cd chatbot; .venv\Scripts\python.exe -m pytest -q -m "not live"` (baseline 136 → CP1 156 → CP1 반영 후 171, 이후 증가).
  - Unity 6000.0.85f2(Built-in RP), 라이선스 있음. `unity/Library` 존재.
  - Codex CLI 0.169.0, ChatGPT 로그인(기본 모델 설정 그대로, effort만 medium으로 덮어씀).
  - Ollama 로컬 모델(gemma4:e4b, kanana-safeguard)은 면담 질문 생성(조건 2)용. 이번 E2E는 조건 1(정적)이라 필요 없음.
  - Git Bash heredoc에서 백슬래시가 반으로 줄어드는 문제가 있음. 백슬래시가 든 스크립트는 파일로 써서 실행.
  - Unity report.json에 로컬 절대 경로가 남으면 `<repo>\…`로 바꾼 뒤 커밋(D06).
