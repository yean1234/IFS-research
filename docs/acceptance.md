# 완료 기준 (acceptance)

야간 작업(2026-11-16 ~ 17)의 판정 기준입니다. 판정자는 이 문서의 기준과 실제 실행 결과입니다.

- **판정 규칙**: AC-1부터 AC-7까지 **모두 통과했을 때만 "완료"** 라고 씁니다. 하나라도 미달이면 미달 항목과 측정 수치를 그대로 보고합니다. 반올림·해석으로 통과시키지 않습니다.
- 수치 기준은 작업 지시에서 정한 값입니다. 바꾸려면 이유를 `docs/decisions.md`에 남깁니다.
- **AC 통과는 공학 목표 달성입니다. 연구 타당도 주장과 다릅니다.** 예를 들어 AC-3을 통과해도 "참여자의 심상을 더 잘 구현했다"는 증거가 되지 않습니다. AC-3의 지표는 AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스의 허용 구간에 대한 일치이고, 임계값(+0.15 등)은 사용자에게 의미 있는 차이로 정한 값이 아닙니다(`docs/research-design.md` 4.4절, 8절).
- **AC는 구현이 준비됐는지 보는 공학적 회귀 기준입니다. 매핑·drift의 타당도 주장이 아닙니다.** AC-2·AC-3은 "규칙이 정해진 대로 돌고, 정한 합성 사례에서 정한 수치를 넘으며, 고친 뒤에도 그 수치가 떨어지지 않는다"를 확인합니다. AC-2의 라벨 18개는 규칙을 만든 쪽이 라벨을 읽은 뒤 규칙을 쓴 합성 사례이고, AC-3의 dev·held-out은 AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스입니다. 그래서 AC 통과를 "매핑이 심상을 옳게 옮긴다"·"drift 판정이 실제 심상 변화를 잡는다"는 근거로 쓰지 않습니다. 타당도는 규칙 버전을 동결한 뒤 독립 작성자의 held-out과 사람 라벨 평가(사례 수·불확실성 구간·속성별 오류 포함)로 따로 봅니다(Codex CP2 #1·#2·#5).
- 명령은 저장소 루트 기준이고 PowerShell 문법입니다. Python은 `chatbot\.venv\Scripts\python.exe`입니다.
- 경로에 "(구현 후 확정)"이 붙은 것은 작업 2·3·4·5의 실행자가 만든 파일 이름으로 오케스트레이터가 바꿔 적습니다.

## 요약표

| AC | 내용 | 핵심 수치 | 확인 방법 요약 |
| --- | --- | --- | --- |
| AC-1 | 연구 설계 문서 | 필수 절 7개, 지어낸 인용 0건 | 문서 절 확인 + 독립 검토자 인용 점검 |
| AC-2 | 심상 유지(표류) 판정 | 시나리오 ≥ 12, 정확도 ≥ 0.90, 덧붙임 오탐 0 | pytest |
| AC-3 | 매핑 고도화 | 실패 사례 ≥ 15, 반영률 ≥ 0.75 & v0 + 0.15, 왜곡률 ≤ 0.05 & ≤ v0, 미반영 원문 보존률(속성 단위) 100%, 퍼지 경로 슬롯 값 0건, 근거 없는 값 비율 ≤ v0 | pytest + 평가 스크립트 |
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
# 검토 회귀 대화(AC-2 집계 밖): 기대 일치 수와 알려진 한계를 출력한다
.venv\Scripts\python.exe -m pytest -q -m "not live" tests\test_drift_review.py -s
# 시나리오 집계(정확도·혼동행렬·덧붙임-only 오탐·undecidable·acknowledged 일치)를 출력하고 결과 JSON을 남긴다
.venv\Scripts\python.exe -m ifs_chatbot.drift --cases tests\fixtures\drift\drift_cases.json --out <결과.json>
# 결정론: 위 명령을 두 번 실행해 두 결과 파일의 sha256이 같은지 본다(test_evaluation_is_deterministic도 같은 것을 확인)
```

- 시나리오 파일: `chatbot/tests/fixtures/drift/drift_cases.json`(독립 작성자 라벨). 라벨 개수를 직접 센다(drift ≥ 5, no-drift ≥ 5, 합계 ≥ 12). `test_cases_meet_label_counts`가 같은 것을 확인한다.
- 구현 모듈: `chatbot/ifs_chatbot/drift.py`(LLM 호출 없음, `test_drift_module_does_not_use_llm`). 평가는 `eval/corpus_run.py`로 실제 컨트롤러 정적 조건을 재생해 세션 로그 `drift.assessment`에서 읽는다.
- 수치 기준(τ·θ·가중치)과 근거는 `docs/drift-design.md` 3절, 같은 값이 `docs/research-design.md` 4.5절 표에 있다.
- 2026-11-16 결과(`drift/1.1.0`, 2단계 검토 T2 반영 뒤): 18개(drift 9 · no-drift 9) 정확도 1.000(TP 9 · FP 0 · TN 9 · FN 0), 덧붙임-only 오탐 0, undecidable 0, acknowledged 일치 18/18, 출력 sha256 두 번 동일(`345c40714fe3c433bdfdc13440b320239a3270b561d07ee0ff38acf63f32dc1d`). 1.0.0 때 sha256은 `93687ebd…`였고, 18개 항목의 판정·DI는 1.0.0과 같다(결과 JSON의 판정 버전 문자열만 다름).
- **잠정 통과로 보고한다.** 설계자가 라벨을 읽은 뒤 규칙을 썼고, 라벨이 수치를 거의 구속하지 못하며(`docs/drift-design.md` 8.3절), 정확도가 라벨 사례에 나온 사전 낱말에 기댄다: 날개·보풀·돌멩이·뭉치 넷을 빼면 0.833(기준 미만, DR03·DR06·DR09 오탐, 8.4절). 새 독립 라벨로 다시 재는 것이 남아 있다.
- 검토 회귀 대화(`chatbot/tests/fixtures/drift/review_t2_regression.json`, 검토자 합성 41개)는 이 기준의 집계에 넣지 않는다. 규칙을 고친 뒤 확인한 것이라 독립 평가가 아니다. 기대가 있는 38개 중 33개가 기대와 같고, 5개는 알려진 한계다(`docs/drift-design.md` 9.3절, `tests\test_drift_review.py`).

---

## AC-3 매핑 고도화

**기준**

| # | 기준 | 수치 |
| --- | --- | --- |
| 3.1 | 규칙 기반 매핑의 실패 사례 기록(유형 분류 포함) | ≥ 15건 |
| 3.2 | held-out 코퍼스에서 개선 매핑의 슬롯 속성 반영률 | ≥ 0.75 |
| 3.3 | 같은 코퍼스에서 v0 대비 반영률 향상(절대) | ≥ +0.15 |
| 3.4 | 왜곡률(값은 있으나 틀림) | ≤ 0.05 이고 v0보다 높지 않음 |
| 3.5 | 무손실 보존: 반영되지 않은 정답 속성 표현이 원문 그대로(구간 포함) 결과 JSON의 **속성 단위 보존 필드**에 남음. 지표는 `fidelity.py`(채점기 0.3.0 이상)의 **미반영 원문 보존률**(`unreflectedVerbatimRate`: status ∉ {reflected, captured, dropped_by_controller}인 속성 중 phrase가 보존 필드에 원문 그대로 있는 비율). 보존 필드는 `_provenance`와 **`_clauses`(절 단위 원문 색인)를 뺀** '_' 최상위 키(`_unmatched`·`_unmapped`·`_negated`·`_alternatives`·`_inferred`·`_context`·`_parts`·`_uncertain`·`_measurements`·`_direction`·`_needsConfirmation`)다. `_clauses`는 확정 텍스트 전체를 담아 어떤 말이든 덮으므로 판정에 쓰지 않고, 그것까지 인정한 값(`unreflectedVerbatimRateWithClauseIndex`)과 절 색인으로만 남은 속성 수(`lostClauseIndexOnly`)는 따로 보고한다(v0·v1 같은 규칙). `dropped_by_controller`는 확정 텍스트에 없어 매핑이 원리적으로 보존할 수 없으므로 분모에서 빼고, **건수와 탈락률을 따로 보고**한다. `preserveRate`(전체 분모, dropped 포함)로는 판정하지 않는다. (2026-11-16 2단계 독립 검토 T3-G1 반영: held-out을 보기 전에 `_clauses`를 인정하던 기준을 이렇게 엄격하게 바꿈) | = 1.0 (100%) |
| 3.6 | 결정론: 같은 입력 → 바이트 동일 출력 | 테스트 통과 |
| 3.7 | 개선 매핑에서 예외가 나면 v0로 대체 | 테스트 통과 |
| 3.8 | v0 출력 불변: v0가 쓴 장면 파일이 `chatbot/tests/fixtures/scene_spec/EX01.json`, `EX02.json`과 **바이트 동일**(파일 바이트 비교 테스트). 기존 테스트 `test_scene_pipeline.py::test_confirm_writes_scene_file_equal_to_golden`, `test_scene_builder.py::test_matches_golden_including_provenance`는 JSON 값 비교라 이것만으로는 미달. 정답 파일 자체가 baseline 대비 바뀌지 않았어야 한다 | 테스트 통과 |
| 3.9 | 매핑 경로에 LLM 호출 없음: v0·개선 매핑을 실행하는 동안 LLM·HTTP 클라이언트(`ifs_chatbot.llm`의 호출 함수, `ollama`, `httpx`, `requests`, `urllib.request.urlopen`, `socket.socket.connect`)를 호출 즉시 예외를 내도록 바꿔 두고 held-out 코퍼스 전체를 매핑하는 테스트. 정적 grep은 보조 증거일 뿐 판정 기준이 아니다 | 테스트 통과 |
| 3.10 | 오프라인 테스트 전부 통과 | 실패 0 |
| 3.11 | 지어내기 ①: 퍼지 경로 슬롯 값. 개선 매핑 출력에서 슬롯 값의 `_provenance`에 자모 퍼지 일치(`source = fuzzy_lexicon` 또는 `needsConfirmation`)가 있는 슬롯 수. 지표는 `fidelity.py`의 `fuzzyValues`(요약)·`fuzzyValues`(항목별) | = 0건 |
| 3.12 | 지어내기 ②: 근거 없는 값 비율(근거 기준, `unsupportedRate` = 값이 있는 슬롯 중 `_provenance` 구간이 같은 경로 정답 phrase 구간과 겹치지 않는 것의 비율). 왜곡률(3.4)은 정답 phrase가 있는 슬롯만 보므로 정답 밖에서 지어낸 값을 못 본다. 그 빈틈을 이 기준이 막는다. 경로 기준 `spuriousRate`도 함께 보고한다 | 개선 매핑 ≤ v0 (같은 held-out 코퍼스) |

- 반영률·왜곡률·보존률의 정의는 `docs/research-design.md` 4.4절과 평가 스크립트 `chatbot/ifs_chatbot/eval/fidelity.py`가 같아야 한다. 다르면 스크립트가 정본이고 문서를 고친다. 반영률·왜곡률의 분모는 kind = slot인 정답 속성 수(dropped 포함), 왜곡은 `wrong_value` + `cross_slot`, 일치 판정은 정답 라벨마다의 `expect` 구간이다.
- held-out 코퍼스는 매핑을 고칠 때 보지 않은 문장이다(`docs/decisions.md` D04). dev 코퍼스 수치로는 판정하지 않는다. 채점 전에 정답 라벨 형식 검사(`--check-corpus`)에서 **오류 0**이어야 한다. 형식 오류가 있으면 채점기가 채점을 거부한다.
- **3.5의 뜻.** 미반영 원문 보존률 100%는 "반영하지 못한 표현을 잃지 않고 원문 그대로 남겼다"는 뜻일 뿐이다. 의미나 정보가 보존되었다는 증거가 아니다. 채점기는 phrase 구간이 보존 필드에 글자 그대로 있는지만 보며, 왜곡된 속성도 원문을 남기면 이 비율에 들어간다. 보고서에서 이 수치를 의미 일치의 증거로 쓰지 않는다. **미반영 원문 보존률은 정보가 결과 JSON에 남았는지 보는 보조 지표다.** 빌더 1.2.0의 어절 보존 규칙(아무 규칙도 소비하지 않은 내용어가 있거나 보존 필드가 어절의 일부만 덮은 어절은 어절 전체를 원문 그대로 `_unmatched`에 남김, `docs/mapping-v1.md` 6.2절) 때문에 거의 구조적으로 1.0이 된다. 매핑 품질 판정은 3.2–3.4(반영률·향상·왜곡률)와 3.11·3.12(지어내기)로 한다(Codex CP2 #1).
- **3.12의 한계.** 근거 없는 값 지표(`unsupportedRate`)는 값의 `_provenance` 구간이 **같은 경로의 정답 phrase 구간과 겹치기만 하면** 근거로 인정한다. 정답 구간이 넓으면(예: '파랗고 어둡다'를 phrase 하나로 라벨) 그 구간 안의 다른 낱말에서 만든 값도 근거 있는 것으로 세어 놓칠 수 있다. 값이 맞는지와 그 값이 실제로 어느 표현에서 나왔는지는 이 지표가 따로 보지 않는다(값의 맞고 틀림은 3.4가 정답 구간의 허용 범위로 본다). 반대로 코퍼스가 정답으로 두지 않은 값(라벨러가 속성으로 적지 않았지만 텍스트에 근거가 있는 값)도 근거 없는 값으로 센다. 그래서 절대 상한 없이 v0와의 상대 비교로만 판정하고, 절대값과 건별 목록을 함께 보고한다. 정답을 최소 의미 단위로 다시 라벨링하고 null 정답을 '미언급'과 '모호·부정·대상 불명'으로 나누는 일은 held-out 정답 고정(`docs/decisions.md` D04)과 사람 검토가 필요해 보류했다(Codex CP2 #2).
- **함께 보고할 것(판정 기준은 아님).** AC-3 수치를 적을 때 다음을 같이 싣는다: 지표별 분모와 `dropped_by_controller` 건수, 항목 단위 군집 부트스트랩 95% CI(`report.json`의 `summary.bootstrap`), v0 대비 차이의 항목 단위 쌍 CI(`--compare`로 만든 `paired.json`), 항목별 결과(`summary.byItem`, `paired.json`의 `items`), 정답 구간 폭 통계(`summary.expectWidths`. layout.size 구간 폭의 v1 크기 척도 옥타브·배율 환산 `sizeRangeOctavesV1` 포함 — dev 중앙값 2.1옥타브 ≈ ×4.3라 그만큼 다른 크기도 반영으로 센다), 근거 없는 값 두 가지(경로 기준 `spuriousRate`, 근거 기준 `unsupportedRate`). 사람 라벨이 생기면 라벨 신뢰도도 싣는다. 30개 안팎 코퍼스의 CI는 그 코퍼스 안의 변동이며 일반 성능의 증거가 아니다.

**확인 방법**

```powershell
cd chatbot
.venv\Scripts\python.exe -m pytest -q -m "not live"                         # 3.6–3.10, 실패 0
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --check-corpus tests\fixtures\imagery_corpus\heldout.json   # 형식 오류 0(종료 코드 0). phrase 원문은 출력하지 않음
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\heldout.json --mapper v0 --out <scratch>\v0
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\heldout.json --mapper v1 --out <scratch>\v1
#   report.json summary.overall 의 reflectRate(3.2·3.3), distortRate(3.4), unreflectedVerbatimRate(3.5 = 1.0, 속성 단위),
#   fuzzyValues(3.11 = 0), unsupportedRate(3.12), droppedRate·slotStatus.dropped_by_controller(따로 보고),
#   unreflectedVerbatimRateWithClauseIndex·lostClauseIndexOnly(따로 보고, 판정 아님)
#   summary.mappingFallback.count = 0 이어야 개선 매핑의 수치다(1 이상이면 report.md 머리에 경고, 그 항목은 v0 출력)
.venv\Scripts\python.exe -m ifs_chatbot.eval.fidelity --corpus tests\fixtures\imagery_corpus\heldout.json --mapper v0 --compare v1 --out <scratch>\pair
#   paired.json: 지표별 v0·개선 값, 차이(개선 − v0)와 항목 단위 쌍 군집 부트스트랩 95% CI, 항목별 결과(함께 보고, 판정 기준 아님)
#   3.12: paired.json metrics.unsupportedRate 의 b ≤ a. mappingFallback.a·b 의 count = 0
git diff --stat a753289 -- chatbot/tests/fixtures/scene_spec/               # 3.8 (1): 정답 파일 변경 없음(출력 없음)
.venv\Scripts\python.exe -m pytest -q -m "not live" -k "bytes or byte_identical"   # 3.8 (2): 6개 선택 — tests\test_scene_pipeline.py::test_v0_scene_file_byte_identical_to_golden[EX01·EX02](v0 장면 파일 == EX01/EX02 바이트 비교), ::test_default_v1_writes_main_and_both_variants_v0_byte_identical[EX01·EX02], tests\test_scene_builder_v1.py::test_v1_same_input_byte_identical, ::test_v0_output_byte_identical_to_baseline_hashes
.venv\Scripts\python.exe -m pytest -q -m "not live" -k "no_llm or no_network"    # 3.9 (dev 코퍼스): tests\test_scene_builder_v1.py::test_dev_corpus_maps_with_no_llm_no_network 1개 선택
.venv\Scripts\python.exe -m ifs_chatbot.eval.e2e --corpus tests\fixtures\imagery_corpus\heldout.json --out ..\docs\validation\e2e --no-network   # 3.9 (held-out 전체): 같은 대상(ifs_chatbot.llm 호출 함수·httpx·urlopen·socket.connect 등 8개)을 호출 즉시 예외로 바꾼 상태에서 재생·매핑. pipeline.log "[차단] … 시도된 호출 0건", summary.json network.calls = [] (차단 장치 테스트: tests\test_e2e.py::test_network_guard_blocks_and_restores)
Select-String -Path ifs_chatbot\scene_builder_v1.py, ifs_chatbot\jamo.py, ifs_chatbot\clarify.py -Pattern 'ollama|llm|requests|httpx'    # 3.9 보조 증거(판정 기준 아님)
```

- 3.1: 실패 사례 문서 `docs/mapping-failures.md`에서 사례 수와 유형 열을 센다.

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
Select-String -Path <scratch>\editmode.log, <scratch>\capture.log -Pattern 'error CS|Shader error|^[\w.]*Exception:|\[Exception\]'   # 0건. 네임스페이스가 붙은 예외(System.Exception: …)도 잡는다 (테스트 프레임워크 스택 프레임 'UnityLogCheckDelegatingCommand:CaptureException'은 오류가 아니므로 제외 — 이 패턴에는 걸리지 않는다)
# <scratch>\capture\report.json: frameMsP95Max ≤ 13.9, 드로콜·삼각형·그림자 광원 예산 항목, spec별 Console 오류 0
```

---

## AC-5 전 과정 실행

**기준**

1. held-out 입력 **20–30개**(감정적 고통 없는 중립 심상, 자유 서술형 포함, 합성 대사).
2. 실제 챗봇 컨트롤러(**정적 조건**, 조건 1)로 면담 → 확정 텍스트.
3. SceneSpec JSON **스키마 유효 100%**. spec마다 `meta.specVersion`에 맞는 스키마로 검사한다: v0 출력(2.0.0)은 `shared/schemas/scene-spec.v2.json`, v1 출력(2.1.0)은 `shared/schemas/scene-spec.v2.1.json`. (2026-11-16 문구 수정: 처음 문구는 v2.json만 적었는데, v1 출력 형식 2.1은 그 뒤 작업 3에서 정한 상위 집합이라 v2.json으로는 v1 spec이 모두 실패한다. 두 수치를 함께 보고한다. `docs/decisions.md` X9)
4. Unity batchmode 로드 **예외 0, 100%**.
5. **스크린샷 전부** 저장(입력 수 × 매핑 수).
6. 두 매핑(v0 / 개선)의 **속성 반영률·왜곡률·보존률** 보고.
7. Unity가 적용한 값과 spec 값 일치: 널이 아닌 수치 슬롯 **|Δ| ≤ 1e-6**. 비교 원천: (가) 캡처 메서드가 반올림 전 런타임 `SceneParams` 값을 따로 기록하면 그 값과 spec 원값을 비교한다. (나) 기록이 `SceneParams.ToRecord()`(소수 4자리 반올림, `initialScene.json`·캡처 `report.json`의 `params`)뿐이면 spec 값을 같은 규칙(소수 4자리, 짝수 반올림)으로 반올림한 뒤 비교한다. 어느 원천을 썼는지 결과 표에 적는다. (나)에서 반올림 경계 때문에 생기는 1e-4 차이는 미달로 세고 사례를 따로 적는다.
8. 로그 저장(파이프라인 로그, Unity 로그, 결과 표). 참여자 데이터 규칙에 따라 합성 입력만 쓰고, 로그 위치가 git 대상이면 합성임을 명시한다.

**확인 방법**

```powershell
cd chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.e2e --corpus tests\fixtures\imagery_corpus\heldout.json --out ..\docs\validation\e2e --no-network
#   입력 수, 스키마 유효 수(spec마다 meta.specVersion에 맞는 스키마: v0 → scene-spec.v2.json, v1 → scene-spec.v2.1.json), 반영률 표 출력
#   → ..\docs\validation\e2e\specs\<id>.v0.json·<id>.v1.json(컨트롤러가 쓴 장면 파일 그대로), schema.json, score\(fidelity --compare와 같은 파일), summary.json, results.md, pipeline.log
cd ..
& "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity `
     -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run -specDir ..\docs\validation\e2e\specs -outDir ..\docs\validation\e2e\unity `
     -width 2064 -height 2208 -eyes 2 -warmup 30 -frames 300 -logFile <scratch>\capture.log     # -specDir·-outDir의 상대 경로는 unity\ 기준
cd chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.e2e --corpus tests\fixtures\imagery_corpus\heldout.json --out ..\docs\validation\e2e --no-network `
     --unity-out ..\docs\validation\e2e\unity --unity-log <scratch>\capture.log
#   (캡처한 spec 파일과 다시 만든 spec이 다르거나 specs\에 이번 실행이 만들지 않는 *.json이 있으면 종료 코드 2로 멈춤)
#   unity\report.json summary.loaded = 입력 수 × 2, consoleExceptions = 0,
#   logs\capture.log(경로·계정 가림 사본)의 "[SceneLoader] … 로드:" 줄 = 입력 수 × 2, 오류 패턴 0
#   종료 코드 0 = 실행 검사 통과: report.json ok = true, spec별 결과가 specs\와 일대일(빠짐·남음·중복 없음), 모두 로드·캡처·PNG,
#   Console 오류·예외 0, 적용값 미달·범주·defaultsUsed 불일치 0, 로그 오류 패턴 0. 하나라도 어긋나면 종료 코드 1, 사유는
#   summary.json failures. 채점 지표의 AC 충족 여부는 종료 코드에 들어가지 않는다(판정은 사람이 한다)
# 스크린샷: ..\docs\validation\e2e\unity\<id>.<매핑>.png 수 = 입력 수 × 2 (summary.json unity.screenshots)
# 적용값 대조: ..\docs\validation\e2e\applied_values.json·.md 에서 max |Δ| ≤ 1e-6 (비교 원천 (나))
```

- 결과 문서: `docs/validation/e2e/README.md`(실행 명령·날짜·버전·결과 요약), `docs/validation/e2e/results.md`(결과 표·실패 목록).

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
| AC-1 | 통과(이전 세션 판정) | 필수 절 7개, CP1 지적 11건 반영. 인용 원문 대조 1건은 사람 몫으로 보류 | `docs/research-design.md`, `docs/codex-reviews/CP1.md`. 이 세션에서 다시 재지 않음 |
| AC-2 | 잠정 통과 | 라벨 18개(drift 9 · no-drift 9) 정확도 1.000, 덧붙임 오탐 0, 두 번 실행 sha256 동일(`345c4071…dc1d`), LLM 호출 0. **단서:** 라벨에 나온 사전 낱말 4개를 빼면 0.833(< 0.90). 설계자가 라벨을 읽은 뒤 규칙을 씀 | `pytest tests	est_drift.py`, `python -m ifs_chatbot.drift --cases …`, `docs/drift-design.md` 8절 |
| AC-3 | **미달** | held-out 30개: 3.2 반영률 0.698(기준 ≥ 0.75) **미달** · 3.3 향상 +0.198 충족(쌍 CI 하한 0.137) · 3.4 왜곡률 0.094(기준 ≤ 0.05) **미달** · 3.5 미반영 원문 보존률 0.859(기준 1.0) **미달** · 3.11 퍼지 경로 값 0 충족 · 3.12 근거 없는 값 0.363 ≤ v0 0.493 충족 · 3.1 실패 사례 45건 · 오프라인 테스트 394 통과(CP3 반영 뒤) | `docs/validation/e2e/README.md`·`results.md`·`score/` |
| AC-4 | **미달(4.5)** | 4.1 EditMode 28/28 · 4.2 오류·예외 0 · 4.3 p95 1.69–2.21 ms(≤ 13.9, 데스크톱 대리 측정) · 4.4 드로콜 추정 ≤ 24/눈, 삼각형 추정 ≤ 102,800/눈, 그림자 광원 1(기기 측정 아님) · **4.5 held-out 캡처 60장 중 H09.v1이 빈 화면, H09.v0도 사실상 빈 화면(매핑이 opacity 0.0·0.1을 냄). 60장 중 12장만 검토** · 4.6 기기 72 Hz는 morning-todo | `docs/validation/e2e/unity/report.json`, `logs/editmode.xml`, `docs/validation/unity/` |
| AC-5 | 통과(5.3 문구 수정 조건) | 입력 30 · 정적 조건 실제 컨트롤러 · 스키마 유효 60/60(버전별 스키마. 처음 문구대로 v2.json만 쓰면 v1 0/30) · Unity 로드 60/60 예외 0 · 스크린샷 60/60 · 적용값 수치 306개 max \|Δ\| = 0.0(원천 (나)) · 로그 저장 | `python -m ifs_chatbot.eval.e2e …`, `docs/validation/e2e/` |
| AC-6 | 통과 | CP1·CP2·CP3 원문과 수용/반박/보류 표, 수용 항목 반영 커밋. 호출 정확히 3번(재시도 0, 한도 에러 없음), 모두 `--sandbox read-only`·`model_reasoning_effort="medium"`. 원문에서 로컬 절대 경로만 `<repo>/`로 바꿈(CP2 16곳, CP3 5곳) | `docs/codex-reviews/CP1.md`·`CP2.md`·`CP3.md` |
| AC-7 | 통과 | 바뀐 파일, 검증 숫자, Codex 지적과 처리, 남은 리스크, 아침에 확인할 것 | `docs/morning-report.md` |

**종합(2026-11-16): "완료"가 아닙니다.** AC-3(3.2·3.4·3.5)과 AC-4.5가 미달입니다.
