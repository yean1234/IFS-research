# 전 과정 실행 검증(E2E, 작업 5) — held-out 30개

> **입력은 전부 합성 대사입니다.** `chatbot/tests/fixtures/imagery_corpus/heldout.json`(AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스, `synthetic: true`)의 답을 컨트롤러에 넣었습니다. 참여자 데이터·실명·연락처는 없습니다. 이 폴더의 spec·로그·스크린샷도 모두 이 합성 입력에서 나왔습니다.
>
> 수치는 이 합성 코퍼스에서 잰 공학 회귀 지표입니다. "매핑이 심상을 옳게 옮긴다"는 근거가 아닙니다(`docs/acceptance.md` 머리말, `docs/research-design.md` 4.4·8절). 30개 코퍼스의 신뢰구간은 이 코퍼스 안의 변동만 나타냅니다.

- 실행 날짜: 2026-11-16 (UTC 05:16–05:20)
- 브랜치·기준 커밋: `overnight/2026-11-16-imagery-fidelity`, HEAD `4355d6c`(CP2 반영 `46199cc` 위 WIP). 매핑·채점·drift·컨트롤러·코퍼스는 이 커밋 그대로(동결, `docs/decisions.md` D04)
- held-out 채점은 아래 ①이 처음이자 유일한 채점이다. ②·④는 같은 계산의 재실행이며 결과 파일이 ①과 바이트 단위로 같다.

## 버전

| 구성 | 버전 |
| --- | --- |
| 코퍼스 | imagery-heldout@1.0.0, sha256 `f8d38ef5877c09bd899ee7cbadd491be5f2dfb8ffaf97169c1163ad716350d55`(형식 검사 오류 0·경고 0, 항목 30·정답 237) |
| 재생 | corpus-run/0.1.0, 정적 조건(조건 1), LLM 없음(`llm.backend = offline`, `guard.model_backend = none`) |
| 형태소 분석 | kiwi 0.24.1 |
| v0 매핑 | scene-spec-builder/0.1.0 (SceneSpec 2.0.0, layer1-attribute-lexicon@0.1.0, scene-params@0.1.0, vad-ko@0.1.0) |
| v1(개선) 매핑 | scene-spec-builder-v1/1.2.0 (SceneSpec 2.1.0, layer1-attribute-lexicon@1.0.0 ← 0.1.0, scene-params@1.0.0, vad-ko@0.1.0) |
| 채점기 | fidelity/0.3.0 (부트스트랩 B = 10000, 시드 20261116, 항목 단위 군집) |
| drift | drift/1.1.0, drift-params/1.1.0 (스냅샷 빌더 v1 = scene-spec-builder-v1/1.2.0) |
| 전 과정 스크립트 | e2e/0.1.0 (`chatbot/ifs_chatbot/eval/e2e.py`) |
| Unity | 6000.0.85f2, Built-in RP, Linear, 품질 단계 VR PC(MSAA 4), Direct3D11, 배치 캡처 ifs-batch-capture/0.1 |

## 실행 명령(그대로)

`<scratch>`는 저장소 밖 임시 폴더다. 저장소 루트에서 시작한다.

```bash
# ① held-out 형식 검사 + 채점(처음이자 유일한 채점)
cd chatbot
.venv/Scripts/python.exe -m ifs_chatbot.eval.fidelity --check-corpus tests/fixtures/imagery_corpus/heldout.json   # 종료 코드 0
sha256sum tests/fixtures/imagery_corpus/heldout.json
.venv/Scripts/python.exe -m ifs_chatbot.eval.fidelity --corpus tests/fixtures/imagery_corpus/heldout.json --mapper v0 --compare v1 --out <scratch>/heldout_fid
#   표준 출력 → logs/fidelity_cli.log

# ② 전 과정 스크립트(재생 → spec → 스키마 → 채점 → drift), LLM·HTTP·소켓 차단
.venv/Scripts/python.exe -m ifs_chatbot.eval.e2e --corpus tests/fixtures/imagery_corpus/heldout.json --out ../docs/validation/e2e --no-network
#   ①의 runs.json·report.json·report.md·compare/*·paired.json·paired.md와 score/의 같은 파일: 8개 모두 바이트 동일(cmp)
```

```powershell
# ③ Unity 배치 캡처(-nographics·-quit 없음. -specDir·-outDir 상대 경로는 unity\ 기준)
$U = "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe"
& $U -batchmode -projectPath unity -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run `
     -specDir ..\docs\validation\e2e\specs -outDir ..\docs\validation\e2e\unity `
     -width 2064 -height 2208 -eyes 2 -warmup 30 -frames 300 -logFile <scratch>\capture.log      # 종료 코드 0, 30 s
# ⑤ Unity EditMode 테스트
& $U -batchmode -projectPath unity -runTests -testPlatform EditMode -testResults <scratch>\editmode.xml -logFile <scratch>\editmode.log   # 종료 코드 0
```

```bash
# ④ 적용값 대조·Unity 로그 확인(②를 다시 돌리며 Unity 결과를 붙인다. 캡처한 spec과 다시 만든 spec이 다르면 멈춘다)
cd chatbot
.venv/Scripts/python.exe -m ifs_chatbot.eval.e2e --corpus tests/fixtures/imagery_corpus/heldout.json --out ../docs/validation/e2e --no-network \
    --unity-out ../docs/validation/e2e/unity --unity-log <scratch>/capture.log
# 재현 확인: 이 폴더 전체를 <scratch>/e2e_repro에 복사해 ④를 다시 돌린 뒤 diff -rq → 모든 파일 동일
```

- ③의 첫 시도는 `-specDir docs\validation\e2e\specs`(저장소 루트 기준)로 줘서 `DirectoryNotFoundException: …\unity\docs\validation\e2e\specs`로 끝났다(종료 코드 1, 캡처 0건). Unity가 상대 경로를 프로젝트 폴더(`unity\`) 기준으로 푼다. `..\`를 붙여 다시 돌린 것이 위 ③이다.
- ⑤의 로그·xml과 ①의 표준 출력은 경로·계정 이름을 가린 사본을 `logs/`에 두었다(`<repo>`·`<home>`·`<user>`·`<host>`, 라이선스 Machine Id·사설 IP는 `<masked>`·`<ip>`).

## 결과 요약

### 채점(AC-3·AC-5.6) — 속성 단위, held-out 30개(정답 237, 슬롯 속성 212)

| 지표 | v0 [95% CI] | v1 [95% CI] | 차이 v1 − v0 [쌍 95% CI] |
| --- | --- | --- | --- |
| 반영률 reflectRate | 0.500 [0.434, 0.562] | **0.698** [0.641, 0.753] | **+0.198** [0.137, 0.259] |
| 왜곡률 distortRate | 0.174 [0.123, 0.228] | **0.094** [0.057, 0.133] | −0.080 [−0.123, −0.038] |
| 손실률 lostRate | 0.160 [0.114, 0.211] | 0.014 [0.000, 0.030] | −0.146 [−0.201, −0.095] |
| 컨트롤러 탈락률 droppedRate | 0.108 [0.057, 0.166] | 0.108 [0.057, 0.166] | 0.000 |
| 보존률 preserveRate(전체 분모) | 0.532 [0.473, 0.587] | 0.797 [0.757, 0.837] | +0.266 [0.209, 0.325] |
| 미반영 원문 보존률 unreflectedVerbatimRate(속성 단위, 판정용) | 0.283 [0.212, 0.356] | **0.859** [0.766, 0.946] | +0.576 [0.466, 0.682] |
| 미반영 원문 보존률(절 색인 포함, 참고) | 0.283 | 1.000 | +0.717 |
| 근거 없는 값 비율 unsupportedRate(근거 기준) | 0.493 (100/203) [0.437, 0.551] | **0.363** (81/223) [0.317, 0.412] | −0.129 [−0.181, −0.081] |
| 근거 없는 값 비율 spuriousRate(경로 기준) | 0.276 (56/203) | 0.220 (49/223) | −0.056 [−0.082, −0.031] |
| 퍼지 경로 값 fuzzyValues | 0 | **0** | 0 |
| 매핑 대체(폴백) | 0 | 0 | |

- 슬롯 상태 — v0: 반영 106 · 왜곡 37 · 보존 12 · 손실 34 · 탈락 23. v1: 반영 148 · 왜곡 20(wrong_value 15, cross_slot 5) · 보존 18 · 손실 3 · 탈락 23.
- 미반영 원문 보존률 분모(반영·포착·탈락이 아닌 속성): v0 106, v1 64. v1에서 원문이 속성 단위 보존 필드에 없는 속성 9개는 모두 절 색인(`_clauses`)에만 남았다(`lostClauseIndexOnly` = 3은 status = lost 중 절 색인으로만 남은 수, 나머지 6개는 왜곡 속성). 목록은 `results.md` 「미반영 원문 보존 실패」.
- 근거 없는 값 사유 — v0: no_gold_span 67 · outside_gold_span 33. v1: no_gold_span 60 · outside_gold_span 21. no_evidence 0.
- 부정 오류 0/6(두 매핑), 배경 오염 v0 5건·v1 2건(모두 값 결정).
- `dropped_by_controller` 23건(밝기 8, 색 7, 크기 3, 채도 3, 움직임 종류 1, 속도 1): 컨트롤러가 묻지 않은 프로브의 답이라 확정 텍스트에 없다. 두 매핑 같다.

### 전 과정(AC-5)

| 항목 | 값 |
| --- | --- |
| 입력 수 | 30(합성, free_narrative 12·multi_turn 18. "모든 항목은 감정적 고통이 없는 중립 심상"은 코퍼스 `note`의 작성자 진술이며 이번 실행에서 따로 검토하지 않음) |
| 매핑 수 | 2(v0, v1) → spec 60개(`specs/<id>.v0.json`·`<id>.v1.json`, 컨트롤러가 장면 폴더에 쓴 바이트 그대로) |
| 스키마 유효 | v0 30/30(`shared/schemas/scene-spec.v2.json`), v1 30/30(`shared/schemas/scene-spec.v2.1.json`). spec마다 `meta.specVersion`에 맞는 스키마로 검사. 원칙 검사(`check_principles`) 문제 0 |
| LLM·네트워크 차단 | 8개 함수(`socket.connect`, `httpx.get/post`, `httpx.Client.send`, `urllib.request.urlopen`, `OllamaBackend.generate/_post`, `OfflineTemplateBackend.generate`) 차단 상태에서 60개 재생·매핑, 시도된 호출 0건(`ollama`·`requests`는 설치돼 있지 않음) |
| Unity 로드 | 60/60, 캡처 실패 0, Console 오류 0·예외 0·경고 0. 로그의 `[SceneLoader] … 로드:` 줄 60개, 오류 패턴(`error CS`·`Shader error`·`Exception`) 0건, `[BatchCapture] 끝: ok=True` |
| 스크린샷 | 장면 PNG 60/60(`unity/<id>.<매핑>.png`), 형상 확대 PNG 59(`_detail`, H09.v1은 형상이 화면에 안 보여 만들지 않음) |
| 적용값 대조 | 비교 원천 **(나)**(report.json `params` = `SceneParams.ToRecord()` 소수 4자리 짝수 반올림). 널이 아닌 수치 306개 **max \|Δ\| = 0.0**, 미달 0, 반올림 경계 0, 0–1 밖 0. 범주 87개 불일치 0. null 슬롯의 `defaultsUsed` 표시 불일치 0. `applied_values.md` |
| 프레임 시간 p95 최댓값 | 1.693 ms(데스크톱 대리 측정, 눈당 2064×2208 × 2눈, 준비 30 + 300프레임). 드로콜 추정 최대 24/눈, 삼각형 추정 최대 102,800/눈, 그림자 광원 1 |
| EditMode 테스트 | 28개 중 통과 28·실패 0(`logs/editmode.xml`). `SceneSpecDeserializationTests` 14개(EX01·EX03.v1 왕복 포함) 통과 |
| drift(참고, AC-2 집계 아님) | 두 매핑 같음: drift 3(H05 DI 1.0, H24 0.5, H26 0.5) · no_drift 7 · undecidable 20(no_later_snapshot 7, 비교 후 판정 불가 13) · 오류 0 |

## 판정 (오케스트레이터, 2026-11-16) — AC-3 미달

독립 검토자가 README의 명령을 다시 돌려 아래 숫자를 모두 재현했습니다(spec 60개·채점 파일·PNG 119장 바이트 동일). held-out은 이 실행에서 처음 채점했고, 결과를 본 뒤 매핑·채점·drift·컨트롤러·코퍼스는 고치지 않았습니다.

| 기준 | held-out 값 | 판정 |
| --- | --- | --- |
| AC-3.2 v1 반영률 ≥ 0.75 | 0.698 [0.641, 0.753] | **미달** |
| AC-3.3 v0 대비 향상 ≥ +0.15 | +0.198 [0.137, 0.259] | 충족(점추정). 쌍 신뢰구간 하한 0.137은 0.15 아래 |
| AC-3.4 왜곡률 ≤ 0.05, 그리고 ≤ v0 | 0.094 [0.057, 0.133] (v0 0.174) | **미달**(0.05 초과). v0 이하는 충족 |
| AC-3.5 미반영 원문 보존률(속성 단위) = 1.0 | 0.859 (55/64) | **미달** |
| AC-3.11 퍼지 경로 슬롯 값 0건 | 0 | 충족 |
| AC-3.12 근거 없는 값 비율 v1 ≤ v0 | 0.363 ≤ 0.493 | 충족 |
| AC-5.1–5.8 | 아래 「전 과정」 표 | 충족. 단 5.3은 spec 버전에 맞는 스키마 기준(v1 spec을 `scene-spec.v2.json`으로 검사하면 0/30) |
| AC-4.5 빈 화면 없음 | H09.v1 빈 화면, H09.v0 사실상 빈 화면. 60장 중 12장만 사람이 아닌 검토자가 열어 봄 | **미달** |

- dev(규칙을 쓸 때 본 세트)에서는 v1 반영률 0.937·왜곡률 0.000이었습니다. held-out에서 0.698·0.094로 떨어진 만큼이 dev 과적합입니다. v1은 v0보다 낫지만(반영률 +0.198, 왜곡률 −0.080) 정한 절대 기준에는 못 미칩니다.
- 표의 「절 색인 포함 1.000」은 참고값이고 판정에 쓰지 않습니다.

## 확인할 점

- **H09.v1 화면에 형상이 없다.** v1이 `material.opacity = 0.0`(mist)을 냈다. 렌더는 정상이고(셰이더 오류 없음) 바닥·하늘만 보인다. H09.v0도 opacity 0.1이라 형상 덮인 화소가 21개뿐이다. H08.v1(fragments, 작고 멀리)은 437화소. 매핑 결과를 그대로 렌더한 것이며 고치지 않았다(동결).
- 분홍(셰이더 오류) 화면은 `report.json` 셰이더 상태(4개 모두 `hasErrors: false`)와 Console 오류 0으로만 확인했다. 60장을 사람이 다 열어 보지는 않았다(H01.v1·H08.v1·H09.v1만 열어 봄).
- Unity 에디터 자체는 실행 중 라이선스 서버와 `public-cdn.cloud.unity3d.com`에 접속을 시도한다(EditMode 로그에 시간 초과 1줄). 파이프라인(Python)은 네트워크를 쓰지 않았다.
- 같은 항목의 v0·v1 spec이 같은 매개변수를 낸 경우는 0건이라(60장 모두 바이트가 다름) 중복 이미지를 줄이지 않았다.

## 파일

| 경로 | 내용 | 크기 |
| --- | --- | --- |
| `results.md` | 결과 표, 실패·오류 목록(왜곡·손실·탈락·근거 없는 값 건별, 미반영 원문 보존 실패) | |
| `summary.json` | 위 수치 전부(기계 판독용) | |
| `specs/` | spec 60개 | 0.5 MB |
| `schema.json` | spec별 스키마 파일·오류·원칙 검사·폴백 | |
| `score/` | `fidelity --compare`와 같은 배치: `runs.json`·`report.*`(v0), `compare/`(v1), `paired.*` | 1.8 MB |
| `drift.json` | 항목별 drift 판정·DI(세션 로그 drift) | |
| `applied_values.json`·`.md` | Unity 적용값 대조 | |
| `unity/` | `report.json`(경로 없음 확인), PNG 60 + 상세 59 | 17.9 MB(장면 PNG 11.6 MB, 상세 5.6 MB) |
| `logs/` | `capture.log`(Unity 캡처), `editmode.log`·`editmode.xml`, `fidelity_cli.log`(①) — 모두 경로·계정 가림 | 1.1 MB |
| `pipeline.log` | ④의 표준 출력 | |
