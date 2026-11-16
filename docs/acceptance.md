# 완료 기준 (acceptance)

야간 작업(2026-11-16 ~ 17)의 판정 기준입니다. 판정자는 이 문서의 기준과 실제 실행 결과입니다.

- **판정 규칙**: AC-1부터 AC-7까지 **모두 통과했을 때만 "완료"** 라고 씁니다. 하나라도 미달이면 미달 항목과 측정 수치를 그대로 보고합니다. 반올림·해석으로 통과시키지 않습니다.
- 수치 기준은 작업 지시에서 정한 값입니다. 바꾸려면 이유를 `docs/decisions.md`에 남깁니다.
- **AC 통과는 공학 목표 달성입니다. 연구 타당도 주장과 다릅니다.** 예를 들어 AC-3을 통과해도 "참여자의 심상을 더 잘 구현했다"는 증거가 되지 않습니다. AC-3의 지표는 AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스의 허용 구간에 대한 일치이고, 임계값(+0.15 등)은 사용자에게 의미 있는 차이로 정한 값이 아닙니다(`docs/research-design.md` 4.4절, 8절).
- 명령은 저장소 루트 기준이고 PowerShell 문법입니다. Python은 `chatbot\.venv\Scripts\python.exe`입니다.
- 경로에 "(구현 후 확정)"이 붙은 것은 작업 2·3·4·5의 실행자가 만든 파일 이름으로 오케스트레이터가 바꿔 적습니다.

## 요약표

| AC | 내용 | 핵심 수치 | 확인 방법 요약 |
| --- | --- | --- | --- |
| AC-1 | 연구 설계 문서 | 필수 절 7개, 지어낸 인용 0건 | 문서 절 확인 + 독립 검토자 인용 점검 |
| AC-2 | 심상 유지(표류) 판정 | 시나리오 ≥ 12, 정확도 ≥ 0.90, 덧붙임 오탐 0 | pytest |
| AC-3 | 매핑 고도화 | 실패 사례 ≥ 15, 반영률 ≥ 0.75 & v0 + 0.15, 왜곡률 ≤ 0.05 & ≤ v0, 미반영 원문 보존률 100% | pytest + 평가 스크립트 |
| AC-4 | Unity 현실감 | EditMode 전부 통과, 오류 0, p95 ≤ 13.9 ms(눈당 2064×2208 × 2눈), 드로콜 ≤ 100, 삼각형 ≤ 300k, 그림자 광원 ≤ 1 | batchmode 로그·결과 XML |
| AC-5 | 전 과정 실행 | 20–30개, 스키마 유효 100%, 로드 100%, 스크린샷 전부, \|Δ\| ≤ 1e-6 | 파이프라인 스크립트 + 로그 |
| AC-6 | Codex 감시 | CP1·CP2·CP3 원문 + 처리표 | `docs/codex-reviews/` |
| AC-7 | 아침 보고 | 파일 존재·필수 내용 | `docs/morning-report.md` |

---

## AC-1 연구 설계

**기준**

1. `docs/research-design.md`에 다음 절이 모두 있다: 가설 · 측정 행동(정의·수식) · 측정 도구 · 분석 방법 · 비교 조건 타당성 · 교란변수 · 한계.
2. 모든 인용은 URL 또는 DOI로 존재를 확인했거나 `[확인 필요]`로 표시되어 있다.
3. 독립 검토자(실행자와 컨텍스트가 분리된 에이전트 또는 Codex CP1)가 찾은 **지어낸 인용 0건**.

**연구 설계 품질 기준(추가)**

| ID | 기준 |
| --- | --- |
| RD-1 | 확증 가설마다 1차 지표·방향·검정·α가 적혀 있다 |
| RD-2 | 측정 행동(수정 요청 횟수, 만족까지 걸린 시간, 속성별 일치, 전체 일치도, Unity 조정량, 시스템 지표, 표류)에 계산식 또는 조작적 정의가 있다 |
| RD-3 | 표본 수 근거에 가정한 효과크기·α·검정력이 명시되어 있다 |
| RD-4 | 탐색 분석이 "탐색"으로 표시되어 확증과 구분된다 |
| RD-5 | 사전 등록 항목 목록이 있다 |
| RD-6 | 치료 효과·IFS 효과·일반화 주장이 없다. 정서 상황 오프닝과의 불일치를 지적하고 중립 문구 초안을 "팀 결정"으로 표시했다 |
| RD-7 | IRB 관련 내용은 리스크·확인 필요로만 적고 법적 단정을 하지 않는다 |
| RD-8 | 확인 질문 루프가 교란이 되는 이유와 분리 방법이 있다 |

**확인 방법**

```powershell
# 1) 필수 절 존재
Select-String -Path docs\research-design.md -Pattern '^## ' | ForEach-Object { $_.Line }
#   → "연구 질문과 가설", "과제 설계", "비교 조건 검토", "교란변수"(### 3.3), "측정할 사용자 행동", "측정 도구", "분석 방법", "한계"가 보여야 함

# 2) 인용 표기: 참고문헌 표의 각 행에 https:// 또는 doi.org 또는 [확인 필요]
Select-String -Path docs\research-design.md -Pattern '^\| [A-Z].*\(\d{4}\) \|' | Where-Object { $_.Line -notmatch 'https?://|\[확인 필요\]' }
#   → 출력 없음이어야 함
```

3) 독립 검토: 검토자가 참고문헌 표의 DOI/URL을 하나씩 열어 저자·연도·제목이 맞는지 확인하고, 결과를 `docs/codex-reviews/CP1.md`(또는 Claude 검토자 기록)에 남긴다. "지어낸 인용" 지적이 1건이라도 수용되면 미달.

---

## AC-2 심상 유지(표류) 판정

**기준**

1. 판단 기준이 수치로 정의되어 있다(모순 판정 임계값, 표류 지수 계산식, 세션 판정 규칙).
2. 구현 모듈과 테스트가 있다. 판정에 LLM 호출이 없다.
3. 정답 라벨이 있는 **합성 시나리오 ≥ 12개**: drift ≥ 5, no-drift ≥ 5. no-drift에는 **단순 덧붙임**과 **바꿔 말하기**가 포함된다. 대사는 합성(원칙 6).
4. 시나리오 전체 **정확도 ≥ 0.90**.
5. **덧붙임만 있는 사례 오탐 0건**.
6. 결정론: 같은 입력 → 같은 판정(두 번 실행해 출력이 바이트 동일).

**확인 방법**

```powershell
cd chatbot
.venv\Scripts\python.exe -m pytest -q -m "not live" tests\test_drift.py -s
# 시나리오 집계(정확도·혼동행렬·덧붙임-only 오탐·undecidable·acknowledged 일치)를 출력하고 결과 JSON을 남긴다
.venv\Scripts\python.exe -m ifs_chatbot.drift --cases tests\fixtures\drift\drift_cases.json --out <결과.json>
# 결정론: 위 명령을 두 번 실행해 두 결과 파일의 sha256이 같은지 본다(test_evaluation_is_deterministic도 같은 것을 확인)
```

- 시나리오 파일: `chatbot/tests/fixtures/drift/drift_cases.json`(독립 작성자 라벨). 라벨 개수를 직접 센다(drift ≥ 5, no-drift ≥ 5, 합계 ≥ 12). `test_cases_meet_label_counts`가 같은 것을 확인한다.
- 구현 모듈: `chatbot/ifs_chatbot/drift.py`(LLM 호출 없음, `test_drift_module_does_not_use_llm`). 평가는 `eval/corpus_run.py`로 실제 컨트롤러 정적 조건을 재생해 세션 로그 `drift.assessment`에서 읽는다.
- 수치 기준(τ·θ·가중치)과 근거는 `docs/drift-design.md` 3절, 같은 값이 `docs/research-design.md` 4.5절 표에 있다.
- 2026-11-16 결과: 18개(drift 9 · no-drift 9) 정확도 1.000, 덧붙임-only 오탐 0, 출력 sha256 두 번 동일. 설계자가 라벨을 읽은 뒤 규칙을 썼으므로 새 독립 라벨로 다시 재는 것이 남아 있다(`docs/drift-design.md` 8.4절).

---

## AC-3 매핑 고도화

**기준**

| # | 기준 | 수치 |
| --- | --- | --- |
| 3.1 | 규칙 기반 매핑의 실패 사례 기록(유형 분류 포함) | ≥ 15건 |
| 3.2 | held-out 코퍼스에서 개선 매핑의 슬롯 속성 반영률 | ≥ 0.75 |
| 3.3 | 같은 코퍼스에서 v0 대비 반영률 향상(절대) | ≥ +0.15 |
| 3.4 | 왜곡률(값은 있으나 틀림) | ≤ 0.05 이고 v0보다 높지 않음 |
| 3.5 | 무손실 보존: 반영되지 않은 정답 속성 표현이 원문 그대로(구간 포함) 결과 JSON의 보존 필드에 남음. 지표는 `fidelity.py`의 **미반영 원문 보존률**(`unreflectedVerbatimRate`: status ∉ {reflected, captured, dropped_by_controller}인 속성 중 phrase가 보존 필드에 원문 그대로 있는 비율). `dropped_by_controller`는 확정 텍스트에 없어 매핑이 원리적으로 보존할 수 없으므로 분모에서 빼고, **건수와 탈락률을 따로 보고**한다. `preserveRate`(전체 분모, dropped 포함)로는 판정하지 않는다 | = 1.0 (100%) |
| 3.6 | 결정론: 같은 입력 → 바이트 동일 출력 | 테스트 통과 |
| 3.7 | 개선 매핑에서 예외가 나면 v0로 대체 | 테스트 통과 |
| 3.8 | v0 출력 불변: v0가 쓴 장면 파일이 `chatbot/tests/fixtures/scene_spec/EX01.json`, `EX02.json`과 **바이트 동일**(파일 바이트 비교 테스트). 기존 테스트 `test_scene_pipeline.py::test_confirm_writes_scene_file_equal_to_golden`, `test_scene_builder.py::test_matches_golden_including_provenance`는 JSON 값 비교라 이것만으로는 미달. 정답 파일 자체가 baseline 대비 바뀌지 않았어야 한다 | 테스트 통과 |
| 3.9 | 매핑 경로에 LLM 호출 없음: v0·개선 매핑을 실행하는 동안 LLM·HTTP 클라이언트(`ifs_chatbot.llm`의 호출 함수, `ollama`, `httpx`, `requests`, `urllib.request.urlopen`, `socket.socket.connect`)를 호출 즉시 예외를 내도록 바꿔 두고 held-out 코퍼스 전체를 매핑하는 테스트. 정적 grep은 보조 증거일 뿐 판정 기준이 아니다 | 테스트 통과 |
| 3.10 | 오프라인 테스트 전부 통과 | 실패 0 |

- 반영률·왜곡률·보존률의 정의는 `docs/research-design.md` 4.4절과 평가 스크립트 `chatbot/ifs_chatbot/eval/fidelity.py`가 같아야 한다. 다르면 스크립트가 정본이고 문서를 고친다. 반영률·왜곡률의 분모는 kind = slot인 정답 속성 수(dropped 포함), 왜곡은 `wrong_value` + `cross_slot`, 일치 판정은 정답 라벨마다의 `expect` 구간이다.
- held-out 코퍼스는 매핑을 고칠 때 보지 않은 문장이다(`docs/decisions.md` D04). dev 코퍼스 수치로는 판정하지 않는다. 채점 전에 정답 라벨 형식 검사(`--check-corpus`)에서 **오류 0**이어야 한다. 형식 오류가 있으면 채점기가 채점을 거부한다.
- **3.5의 뜻.** 미반영 원문 보존률 100%는 "반영하지 못한 표현을 잃지 않고 원문 그대로 남겼다"는 뜻일 뿐이다. 의미나 정보가 보존되었다는 증거가 아니다. 채점기는 phrase 구간이 보존 필드에 글자 그대로 있는지만 보며, 왜곡된 속성도 원문을 남기면 이 비율에 들어간다. 보고서에서 이 수치를 의미 일치의 증거로 쓰지 않는다.
- **함께 보고할 것(판정 기준은 아님).** AC-3 수치를 적을 때 다음을 같이 싣는다: 지표별 분모와 `dropped_by_controller` 건수, 항목 단위 군집 부트스트랩 95% CI(`report.json`의 `summary.bootstrap`), v0 대비 차이의 항목 단위 쌍 CI(`--compare`로 만든 `paired.json`), 항목별 결과(`summary.byItem`, `paired.json`의 `items`), 정답 구간 폭 통계(`summary.expectWidths`), 근거 없는 값 두 가지(경로 기준 `spuriousRate`, 근거 기준 `unsupportedRate`). 사람 라벨이 생기면 라벨 신뢰도도 싣는다. 30개 안팎 코퍼스의 CI는 그 코퍼스 안의 변동이며 일반 성능의 증거가 아니다.

**확인 방법**

```powershell
cd chatbot
.venv\Scripts\python.exe -m pytest -q -m "not live"                         # 3.6–3.10, 실패 0
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --check-corpus tests\fixtures\imagery_corpus\heldout.json   # 형식 오류 0(종료 코드 0). phrase 원문은 출력하지 않음
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\heldout.json --mapper v0 --out <scratch>\v0
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\heldout.json --mapper <개선 매핑 이름> --out <scratch>\v1   # (매퍼 이름은 구현 후 확정)
#   report.json 의 reflectRate(3.2·3.3), distortRate(3.4), unreflectedVerbatimRate(3.5 = 1.0), droppedRate·slotStatus.dropped_by_controller(따로 보고)
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\heldout.json --mapper v0 --compare <개선 매핑 모듈:factory> --out <scratch>\pair
#   paired.json: 지표별 v0·개선 값, 차이(개선 − v0)와 항목 단위 쌍 군집 부트스트랩 95% CI, 항목별 결과(함께 보고, 판정 기준 아님)
git diff --stat a753289 -- chatbot/tests/fixtures/scene_spec/               # 3.8 (1): 정답 파일 변경 없음(출력 없음)
.venv\Scripts\python.exe -m pytest -q -m "not live" -k "bytes or byte_identical"   # 3.8 (2): v0 출력 == EX01/EX02 바이트 비교 테스트(이름은 구현 후 확정, 1개 이상 실행·통과)
.venv\Scripts\python.exe -m pytest -q -m "not live" -k "no_llm or no_network"    # 3.9: LLM·HTTP 차단 상태 매핑 테스트(이름은 구현 후 확정, 1개 이상 실행·통과)
Select-String -Path <개선 매핑 모듈> -Pattern 'ollama|llm|requests|httpx'    # 3.9 보조 증거(판정 기준 아님)
```

- 3.1: 실패 사례 문서(구현 후 확정)에서 사례 수와 유형 열을 센다.

---

## AC-4 Unity 현실감

**기준**

1. batchmode **EditMode 테스트 전부 통과**(실패 0).
2. 씬 로드 시 **오류·예외 0**. 대상: EditMode 로그, **캡처·측정 실행 로그**(`BatchCapture.Run`의 `-logFile`), 그리고 캡처 `report.json`에 spec마다 기록된 Console 오류·예외(`Application.logMessageReceived`로 받은 Error/Exception/Assert). 세 곳 모두에서 `Exception`, `error CS`, `Shader error`, 오류 기록 0건.
3. 데스크톱 대리 측정에서 **Quest 3급 해상도** 렌더의 **프레임 시간 p95 ≤ 13.9 ms**(≥ 72 fps). 측정 조건을 고정한다: 눈당 **2064 × 2208** 렌더 타깃(Quest 3 눈당 해상도), 한 프레임 = 눈 **2개**를 따로 렌더(멀티패스, 가장 불리한 경우) + GPU 동기화까지의 시간, 준비 **30프레임 제외 후 300프레임** 측정, 그래픽 장치 사용(`-nographics` 금지), 화면 출력이 아닌 RenderTexture 렌더라 vSync의 영향을 받지 않음(`QualitySettings.vSyncCount`와 무관), 렌더 설정은 실험용 품질 단계. 판정 값은 캡처 `report.json`의 spec별 `frameMsP95` 중 **최댓값**(`frameMsP95Max`). 다른 조건으로 잰 값은 판정에 쓰지 않는다.
4. 프로젝트 자체 예산: **드로콜 ≤ 100, 삼각형 ≤ 300k, 실시간 그림자 광원 ≤ 1**. 이 예산은 보수적인 자체 기준이며 **기기 측정이 아님**을 보고서에 명시한다.
5. 스크린샷이 저장되고 검토되었다(검토자가 열어 보고 분홍 셰이더·빈 화면이 없음을 기록).
6. 실제 헤드셋 72 fps 확인은 `docs/morning-todo.md`에 남긴다(이번 판정에서는 대리 측정만).

**확인 방법**

```powershell
$U = "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe"
& $U -batchmode -projectPath unity -runTests -testPlatform EditMode `
     -testResults <scratch>\editmode.xml -logFile <scratch>\editmode.log
# editmode.xml 의 <test-run ... failed="0"> 확인, total 수 기록
& $U -batchmode -projectPath unity -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run `
     -specDir <spec 폴더> -outDir <scratch>\capture -width 2064 -height 2208 -eyes 2 -warmup 30 -frames 300 `
     -logFile <scratch>\capture.log          # -nographics 쓰지 않음
Select-String -Path <scratch>\editmode.log, <scratch>\capture.log -Pattern 'error CS|Shader error|^\w*Exception:|\[Exception\]'   # 0건 (테스트 프레임워크 스택 프레임 'UnityLogCheckDelegatingCommand:CaptureException'은 오류가 아니므로 제외)
# <scratch>\capture\report.json: frameMsP95Max ≤ 13.9, 드로콜·삼각형·그림자 광원 예산 항목, spec별 Console 오류 0
```

---

## AC-5 전 과정 실행

**기준**

1. held-out 입력 **20–30개**(감정적 고통 없는 중립 심상, 자유 서술형 포함, 합성 대사).
2. 실제 챗봇 컨트롤러(**정적 조건**, 조건 1)로 면담 → 확정 텍스트.
3. SceneSpec JSON **스키마 유효 100%**(`shared/schemas/scene-spec.v2.json`).
4. Unity batchmode 로드 **예외 0, 100%**.
5. **스크린샷 전부** 저장(입력 수 × 매핑 수).
6. 두 매핑(v0 / 개선)의 **속성 반영률·왜곡률·보존률** 보고.
7. Unity가 적용한 값과 spec 값 일치: 널이 아닌 수치 슬롯 **|Δ| ≤ 1e-6**. 비교 원천: (가) 캡처 메서드가 반올림 전 런타임 `SceneParams` 값을 따로 기록하면 그 값과 spec 원값을 비교한다. (나) 기록이 `SceneParams.ToRecord()`(소수 4자리 반올림, `initialScene.json`·캡처 `report.json`의 `params`)뿐이면 spec 값을 같은 규칙(소수 4자리, 짝수 반올림)으로 반올림한 뒤 비교한다. 어느 원천을 썼는지 결과 표에 적는다. (나)에서 반올림 경계 때문에 생기는 1e-4 차이는 미달로 세고 사례를 따로 적는다.
8. 로그 저장(파이프라인 로그, Unity 로그, 결과 표). 참여자 데이터 규칙에 따라 합성 입력만 쓰고, 로그 위치가 git 대상이면 합성임을 명시한다.

**확인 방법**

```powershell
cd chatbot
.venv\Scripts\python.exe -m <전 과정 스크립트>                       # (구현 후 확정) 입력 수, 스키마 유효 수, 반영률 표 출력
# Unity 쪽: -executeMethod <일괄 로드 메서드> 로그에서 로드 성공 수 = 입력 수 × 2, 예외 0
# 스크린샷 폴더 파일 수 = 입력 수 × 2
# 적용값 대조 결과 파일에서 max |Δ| ≤ 1e-6
```

---

## AC-6 Codex 감시

**기준**

1. `docs/codex-reviews/CP1.md`, `CP2.md`, `CP3.md`에 Codex 출력 **원문**이 있다.
2. 각 파일(또는 짝 문서)에 지적 사항이 **수용 / 반박(근거) / 보류** 표로 정리되어 있고, 수용한 것은 반영 후 커밋되었다.
3. Codex 사용 한도 에러가 난 체크포인트는 Claude 검토자로 대체했다는 기록이 있다.
4. 호출 횟수는 정확히 3번(실패 시 재시도 1번까지)이다. 호출 명령에 `--sandbox read-only`와 `model_reasoning_effort="medium"`이 있다.

**확인 방법**

```powershell
Get-ChildItem docs\codex-reviews\                       # CP1.md, CP2.md, CP3.md
Select-String -Path docs\codex-reviews\*.md -Pattern '수용|반박|보류'
git log --oneline                                        # 체크포인트 커밋과 반영 커밋
```

---

## AC-7 아침 보고

**기준**: `docs/morning-report.md`가 있고 다음을 모두 담는다.

1. 바뀐 파일 목록
2. 검증 결과(숫자: 테스트 수, 반영률·왜곡률·보존률, 표류 정확도, 프레임 시간 등)
3. Codex 지적과 처리 결과
4. 남은 리스크
5. 사용자가 아침에 확인할 것

**확인 방법**

```powershell
Select-String -Path docs\morning-report.md -Pattern '바뀐 파일|검증|Codex|리스크|아침'
```

---

## 판정 기록 양식

| AC | 판정(통과/미달) | 측정 수치 | 근거 파일·명령 |
| --- | --- | --- | --- |
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |
