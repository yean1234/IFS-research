# HANDOFF — 야간 작업 인수인계 (새 세션은 이 파일 하나만 읽고 이어서 진행)

> 마지막 갱신: 2026-11-16 (계정 전환 뒤 새 세션) · 갱신자: 오케스트레이터(Claude Fable 5.2, 세션 edd117bf)
> 모델 배정(decisions.md D09): 메인 세션(판단·검토 반영 분류·AC 판정·보고서)은 Fable, Workflow 서브에이전트(구현·테스트 실행·검토·수정)는 `model: 'opus'`로 지정.
> 이 파일은 단계가 끝날 때와 최소 30분마다 갱신하고, 갱신 때마다 WIP 커밋을 남깁니다.

## ★★ 실험 프로토타입 구현 (2026-11-23, 브랜치 `claude/prototype-v4-build`) — 가장 최근 작업은 이 절입니다

> 갱신: 2026-11-23, 하위 에이전트(Claude)가 단계 C·D10 문서 작업 끝에 적음. 같은 날 G31–G34 구현, 이어서 D6(기본 형상) 구현 뒤 바로 아래 소절을 더함. 지시문은 `docs/prompts/prototype-v4-build.md`(2026-11-22 클라우드 세션에서 연구 책임자와 정함). 결정은 `docs/decisions.md`의 「형상 표현 범위와 생성 모델」 절(G1–G28)과 X79–X85. 아래 ★ 절부터는 이전 작업의 기록이고 그대로 뒀습니다.

### G12 WebGL 미리보기 챗봇 연결 (2026-11-23, 하위 에이전트 Claude) — 이 절의 가장 최근 작업

챗봇 웹 화면의 형상 미리보기를 WebGL로 연결하고, 그림(image, G25) 방식은 예비로 남겼습니다. 상세 `docs/validation/webgl/README.md` 11절, 정한 세부 `docs/decisions.md` 맨 끝 「WebGL 연결 세부」(G25가 예비 경로가 된 것은 메인 세션이 G36으로 적을 예정).

- **빌드**: 저장소 밖 복사본(`<repo 밖>/webgl-build/proj`, robocopy, Library 재사용)에서 WebGL(`preview/`, 47.63 MB, 73.5 s, 오류 0)과 Windows 플레이어(`preview-win/` = v4 예비, `preview-win-cp/` = 비교용)를 같은 소스로 다시 빌드. 이전 `preview-win`은 D6 전 빌드였음.
- **설정**: `chatbot/config/v4.toml` `[preview] mode = "webgl"`(+ `webgl_ready_timeout_s` 30, `webgl_request_timeout_s` 15). 기본·pilot 프로필은 그대로.
- **코드**: `web/stage.js` WebGL 어댑터 다시 씀(iframe 고정·큐·응답 대조·실패 알림·미리 그리기·조절 화면 움직임 재생), `preview.py`(webgl일 때 image 예비, 세션별로 내림), `selection.py`(세션별 미리보기 방식·기록 `preview.shown/fallbacks/webgl`, image에서 움직임 끄기 `adjustUnavailable`, `previewWarmup`), `server.py`(`POST …/preview/client`, image PNG는 세션 방식 기준), 고정 문구 `adjust_item_unavailable`(protocolVersion 0.3.0, draft), WebGL 템플릿(시작 실패 때 ready 거부 등). Unity C#은 고치지 않음.
- **재현한 이전 문제**: 후보 화면에서 iframe이 문서에 없어 그림 0장(오류 없음), 조절 버튼마다 iframe 다시 로드, 두 번 조절 뒤 화면의 Unity에 형상이 없음.
- **확인(직접 돌림)**: pytest 파일별 `-m "not live"` **829 통과·6 xfail·실패 0**(+6). 헤드리스 Chrome으로 S1–S9 + 조절 모든 값 세션: 모두 webgl로 끝까지, iframe 재시작 0, 후보 그림 섞임 없음, 조절 54단계 모두 화면 바뀜, 움직임 재생, 기본 형상 5개·반투명 그릇 그려짐, 콘솔 오류 0, 면담 뒤 LLM 호출 0. 빌드 폴더를 막거나 브라우저 WebGL을 끄면 image로 내려가고 기록됨. WebGL ↔ 플레이어 평균 색 ΔE00 평균 0.112·최대 1.358(기본 형상 20개 최대 0.763). dotnet·Unity EditMode는 C#을 안 바꿔서 다시 돌리지 않음.
- 하지 않은 것: 창이 있는 브라우저·다른 PC, 끌어 돌리기, 시간 초과·컨텍스트 잃음 실제 발생, `selection-flow/runs/` 다시 만들기. 사람이 정할 것은 `docs/morning-todo.md` 「G12 WebGL 연결」.

### 기본 형상 첫 묶음 D6 구현 (2026-11-23, 하위 에이전트 Claude)

연구 책임자 결정 G30(첫 묶음 5개 승인)에 따라 단계 D6을 끝냈습니다. 정한 세부는 `docs/decisions.md` 맨 끝 「D6 구현 세부」, 그림과 판정은 `docs/validation/base-forms/README.md`.

- 커밋(이 브랜치, 차례대로): `34ba7e2` compile-check 스텁 수리(`PlayerSettings.SplashScreen`) → `55e646d` 공통 경로 + 담는 것 → `8fead67` 선·끈 → `9711cc0` 얇은 판 → `792e411` 불꽃 → `cc8efb4` 물방울 → `2e05e4f` 로더·러너 통합 테스트, 시나리오 S8·S9 → `5065efa` 검증 자료 → 문서 커밋.
- **스키마 2.2.0**(`shared/schemas/scene-spec.v2.2.json`): `form.base`(container·line·sheet·flame·drop·null)·`form.baseVariant`, `_unmapped.reason` `excluded_shape`. 2.0·2.1 문서는 그대로 유효. Python `schema_errors()`·`check_principles()`, Unity `SceneSpecJson`·`SceneParams`(2.2 spec에만 기록에 `form.base`)·`SceneOverride`·`PlacementSelection` 갱신. **v0·v1 출력 sha 불변**(D6 전 HEAD에서 잰 5문장 고정).
- **매퍼 v2 builder 2.2.0**(언제나 specVersion 2.2.0) + 사전 `shared/lexicon/base_shapes.v1.json`(0.5.0, 명사 34개, 안전 제외 33개). 주어·이름·직유 원천, 본 장면, 부정 아님, 수량 단위·크기 비교 기준 아님. 같은 문장의 '엉키·가늘·굵·네모'가 변형값을 덮어씀.
- **Unity** `Runtime/Rendering/BaseShapeMesh.cs`(규칙 `container/1`·`line/1`·`sheet/1`·`flame/1`·`drop/1`), `FormRenderPlan`의 base 판정(blob·미지정만 그림), `BaseShapeRenderer`(렌더 경로 `base:<형상>`), 계획 JSON `base`.
- **후보·조절**: 후보 값 표 `candidate_values.v2.json`(2.0.0, v1·v0 파일은 그대로), 생성기 `ifs-candidates/0.3.0`. 기본 형상은 후보 값이 아님, 조절 "형태" 항목 9값(`valueOverrides`). 갈림 '막'과 `form_type_with_base`. `selection.v0.2.json`에 `form.base`를 하위 호환으로 더함. `web/stage.js`는 고치지 않음(범주 항목을 서버가 준 값 목록대로 번호 버튼으로 그려 9값이 그대로 나옴. WebGL 어댑터 부분은 손대지 않음).
- 확인한 수치(직접 돌림): pytest 파일별 `-m "not live"` 합계 **823 통과·6 xfail·실패 0**(기준선 750에서 +73), dotnet **383/383**, Unity EditMode **440/440**. 배치 캡처: 합성 20문장(형상 5개) + 목업 14개 전후, 콘솔 오류 0.
- 하지 않은 것: 헤드셋 확인, WebGL 빌드에서 돌려 보기(G35 대기), 팀원 그림 판정, held-out, Codex 검토, 채점기의 `form.base` 정답 기준. `docs/validation/selection-flow/runs/`(S1–S7 image 모드 결과)는 다시 돌리지 않음(S8·S9는 pytest로만 돌림).
- 사람이 정할 것은 `docs/morning-todo.md` 「D6」 항목.

### 연구 책임자 결정 G31–G34 구현 (2026-11-23, 하위 에이전트 Claude)

- 결정은 `docs/decisions.md` G30–G35, 구현 세부(새 출처 값, 구별 규칙 표, 형식 버전)는 바로 아래 소절 「G31–G34 구현 세부」. **G30(`form.base`, 스키마 2.2.0)은 하지 않았습니다**(다른 작업).
- **G31**: 조절 항목 순서가 색 → 형태 → 밝기 → 투명도 → 크기 → 질감 → 움직임. `selection.json`에 `colorChanged`(처음 색 ≠ 마지막 색).
- **G32**: 모형이 없는 모양어('길쭉'·'실')만 말했으면 형태 후보를 벌림(축 reason `said_unrendered`). 출처 `said_unrendered_chosen`(고름)·`said_unrendered_default`(맞는 것이 없다/건너뜀), 조절로 고치면 `edited`, 말한 낱말은 `sourceDetails.form.type.saidWords`. 모형이 있는 모양어는 말한 자리(출처 `said`).
- **G33**: 매퍼 v2 builder 2.1.0 — 거리 하한 꼬리표 `+floor(0.1;said=<말한 값>)`, `selection.json` `distanceFloor`. 스키마 2.1 그대로, v0·v1 출력 불변(sha 고정).
- **G34**: 값 표 `shared/lexicon/candidate_values.v1.json`(1.0.0, v0 파일은 그대로) — 밝기를 후보에서 뺌, 구별 규칙 `ifs-distinct/1.0.0`(최종 값이 같음 / 정지 미리보기의 움직임). 남은 후보가 하나면 선택 단계 없이 조절(`selection.skipped = true`). 생성기 `ifs-candidates/0.2.0`. 고정 문구 protocolVersion 0.2.0(후보 1개 화면 문구 2개 삭제, 27개 draft).
- 선택 기록 형식 **`ifs-selection/0.2`**(스키마 `selection.v0.2.json`, 0.1 스키마 유지). 러너는 0.1·0.2를 모두 읽음. 분석기 열 `selection_skipped`·`color_changed`·`form_source`.
- 합성 시나리오 S1–S7(S5를 "움직임만 빈 자리"로 바꾸고 S6·S7 추가)을 image 모드로 다시 돌림, 화면 캡처 다시 찍음(`1b`가 "후보 1개" → "건너뛰고 조절").
- 커밋: `ebe41d9` G33 → `0feba5f` G31·G32·G34 코드·테스트 → `e75efca` 시나리오 결과 → 이 문서를 담은 문서 커밋.
- 확인한 수치(직접 돌림): pytest 파일별(`-m "not live"`) 합계 750 통과·6 xfail·실패 0(live 14개 제외), dotnet 290/290, Unity EditMode 342/342(깨끗한 git worktree에서. 같은 때 다른 에이전트가 고친 커밋 안 된 `PreviewBuild.cs`가 dotnet 컴파일 검사 스텁에 없는 `PlayerSettings.SplashScreen`을 써서 이 저장소 작업 폴더에서는 dotnet 빌드가 실패함 — 그 변경은 이 작업 것이 아니라 건드리지 않음).
- 남은 것: 구별 규칙의 미확인 조합(안개·조각의 질감 등, 값 표 `distinctness.unverified`), 조절 쪽 반영 검사(G22 `adjustItems.availability`, image 미리보기에서 움직임 조절이 안 보임), 모양어 범주의 부분 낱말('가장자리' 등)도 형태 후보를 여는 문제(`docs/morning-todo.md`).

- **브랜치: `claude/prototype-v4-build`.** 로컬 `claude/gallant-galileo-u02gqf` 위에 만들고 `origin/claude/focused-lamport-auymxq`를 합쳤습니다(`acdfd28`). main은 건드리지 않았습니다.
- 커밋: `acdfd28` 병합 → `1985e17` G7–G13 → `235c3e7` G14–G24 → `7383abd` 조사·매퍼 v2(D1·D2) → `e999dbf` 에셋 계획 → `6719582` 미리보기(D4) → `c9d1eb2` 구름(D7)·러너(D8)·기록 → `1051d48` 후보·조절·사전 측정(D3·D5·D9) → `5d8bb1a` Codex CP9 판정(G26–G28).
- 커밋하지 않고 둔 것: `CLAUDE.md` 수정과 `refine-logs/`(사용자 것). 단계 C·D10 문서와 미리보기 캡처 2장(`docs/validation/selection-flow/screens/image_1_candidates_2x2.png`·`image_2_adjust.png`)은 이 문서를 쓴 시점에 커밋 전이었습니다(커밋은 메인 세션이 함).
- **IRB 승인을 받을 수 없어 사람을 모집하는 실험은 하지 않습니다(X79).** 헤드셋과 1–6단계 흐름은 연구팀 내부 시스템 점검에만 씁니다(X80).

| 단계 | 상태 | 산출물 |
| --- | --- | --- |
| 0 로컬 상태·병합·시트 대조 | 끝 | `docs/decisions.md` 「지시문이 쓰인 뒤 로컬에서 달라진 것」·「렌더 시트 3장과 구름 진단의 대조」 |
| 결정 기록 | 끝 | G7–G13(지시문 그대로), G14–G24(Codex `D5.md`·Claude `D5_claude.md` 독립안 비교), G25(미리보기 대안), G26–G28(Codex `CP9.md`). Codex 자문 `D4.md`(원래 D2) 대조 |
| A 조사 | 끝 | `reports/심상 외재화 형태 목록 조사.md`, `research_notes/심상 외재화 형태 목록 조사/` |
| B 에셋 계획 | 끝, **승인 대기** | `docs/asset-plan.md`(`status: draft`, 승인 결정 11개) |
| C 계획을 문서에 반영 | 끝 | `docs/rq-v4-proposal.md` 0·4.4·4.5·7절, `docs/chatbot-design.md` 7절(면담 밖, 유도 위험), `docs/scene-spec-mapping.md` 7절(매퍼 v2, 출처 네 가지, `form.base` 계획, 스키마 영향), `docs/shape-mapping.md` 「기본 형상 경로·후보 단계와의 관계」 |
| D1·D2 매퍼 v2 | 끝 | `chatbot/ifs_chatbot/scene_builder_v2.py`, `docs/validation/mapper-v2/`. v0·v1 출력 불변 |
| D3 후보 생성기 | 끝 | `chatbot/ifs_chatbot/candidates.py`, `shared/lexicon/candidate_values.v0.json` |
| D4 미리보기 | WebGL 못 함 → 대안(상주 Windows 플레이어 → PNG) 측정·채택(G25) | `docs/validation/webgl/` |
| D5 후보·조절·사전 측정 화면과 API | 끝 | `selection.py`·`server.py`·`web/stage.js`·`preview.py`, `shared/protocol/selection_protocol.v0.json`(문구 29개 draft → G34 뒤 27개, protocolVersion 0.2.0), `docs/validation/selection-flow/` |
| D6 기본 형상 경로 | **하지 않음**(에셋 계획 승인 대기) | — |
| D7 구름 | 끝(헤드셋 미확인) | `docs/validation/cloud/` |
| D8 러너 연결 | 끝 | `unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs`, 기록 `ifs-placement/0.2`, `docs/validation/runner-selection/` |
| D9 기록 | 끝 | `selection.json`(`ifs-selection/0.1` → G31–G34 뒤 `0.2`, 스키마 `shared/schemas/selection.v0.1.json`·`selection.v0.2.json`), `premeasure.json`, 러너 manifest `selection`·`appliedOverrides` |
| D10 내부 시행 준비 | 끝(문서) | `docs/internal-trial-guide.md`(실행 안내, 점검표, 중립 심상 예시 10개) |
| 미리보기 플레이어 재빌드 | 끝 | 저장소 밖 `../webgl-build/preview-win/`(D7 반영). image 모드 캡처 다시 만듦 — 안개 후보가 덩어리 구름으로 나옴 |

하지 않은 것·확인하지 못한 것:
- **D6**(기본 형상 경로, `form.base`, 스키마 2.2.0): 에셋 계획 승인 대기. 2.2.0으로 올릴 때의 영향은 `docs/scene-spec-mapping.md` 7.6절.
- **WebGL 빌드**: Web Build Support 모듈 설치가 관리자 확인(UAC) 때문에 두 번 실패. 사람이 Unity Hub ▸ Installs ▸ 6000.0.85f2 ▸ Add modules ▸ Web Build Support를 설치한 뒤 `docs/validation/webgl/README.md` 8절로 다시 판정.
- **헤드셋 실기**: 사람이 헤드셋을 쓰고 확인한 항목 없음(`docs/headset-checklist.md`).
- G26·G27(러너가 `sha256Basis`·출처 값을 검사)은 이후 구현됨(CP9 반영, 8686fb7). G22의 "조절 항목 × 렌더러 조합이 화면에 반영되는지" 검사 테스트와 Unity 쪽 후보 덮어쓰기 교차 테스트가 없음.
- `docs/validation/selection-flow/runs/`의 후보 PNG는 D7 전 플레이어로 찍은 것(S1·S4의 안개 후보가 옛 모양). 다시 만들지 않았음.
- 실제 브라우저로 화면을 눌러 보지는 않았음(헤드리스 캡처와 HTTP API로만 확인).

검증 명령(저장소 루트, PowerShell):
```powershell
git branch --show-current      # claude/prototype-v4-build
git status --short             # CLAUDE.md 수정과 refine-logs/ 는 원래 있던 것
cd chatbot; .\.venv\Scripts\python.exe -m pytest -q -m "not live"; cd ..             # 2026-11-23: 691 passed, 6 xfailed, 14 deselected
cd chatbot; .\.venv\Scripts\python.exe -m ifs_chatbot.selection_sim --out <임시 폴더>; cd ..   # 합성 시나리오 5개, "기대 불일치 0"(2026-11-23 확인)
cd chatbot; .\.venv\Scripts\python.exe -m ifs_chatbot.server --config v4 --backend offline --condition static   # 직접 해 보기 http://127.0.0.1:8000 (docs/internal-trial-guide.md)
cd unity/Tools/compile-check; dotnet test Tests/IFS.SceneSpec.CompileCheck.Tests.csproj; cd ../../..   # 283 통과(c9d1eb2 때 에이전트 보고, 이번에 다시 돌리지 않음)
& "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity -runTests -testPlatform EditMode -testResults <xml> -logFile <log>   # 335 통과(같음)
```
- Unity는 한 번에 하나만 띄웁니다. 배치 실행 뒤 `unity/Assets/XR/Settings/OpenXRPackageSettings.asset`이 줄바꿈만 바뀌어 있으면 `git checkout --`로 되돌립니다.

이어받을 때 볼 문서: `docs/prompts/prototype-v4-build.md`(1절 흐름 표, 6·7절), `docs/decisions.md` G1–G28·X79–X85, `docs/asset-plan.md`, `docs/internal-trial-guide.md`, `docs/validation/selection-flow/README.md`, `docs/validation/mapper-v2/README.md`, `docs/validation/webgl/README.md`, `docs/validation/cloud/README.md`, `docs/validation/runner-selection/README.md`, `docs/chatbot-design.md` 7절, `docs/scene-spec-mapping.md` 7절. 사람이 정할 것은 `docs/morning-todo.md` 맨 위 절.

후속 작업:
1. 에셋 계획 승인(결정 11개) → D6: 스키마 2.2.0(`form.base`), Python 검증, Unity 파서, 절차 모형, 사전 `base_shapes.v1.json`.
2. G26·G27 러너 구현, G28대로 "같은 후보"와 "같은 표시 순서" 테스트를 나눴는지 확인.
3. G22 반영 검사 테스트와 `adjustItems.availability` 채우기(어두운 색에서 밝기 등), Unity 교차 테스트.
4. 내부 시행(`docs/internal-trial-guide.md`) → 사람이 정할 것(후보 개수, 대표성 하한, 통과 기준 등) 결정.
5. WebGL 모듈 설치 뒤 재판정. 새 플레이어로 `selection-flow/runs/` 다시 만들기.
6. 분석기(`ifs_chatbot.eval.placement`) 아는 버전 목록에 `ifs-placement/0.2` 추가, `selection`·`appliedOverrides` 읽기.
7. 헤드셋 실기 점검.

## ★ RQ V4 무인 작업 (2026-11-22 밤)

> 갱신: 2026-11-22 밤, 메인 세션(Claude Fable 5.2). 아래 0절부터는 11/16–17 야간 작업의 기록이고 그대로 뒀습니다.

- **브랜치: `claude/gallant-galileo-u02gqf`** (main보다 앞. main은 건드리지 않음). 커밋·푸시는 이 브랜치에만. PR은 만들지 않음.
- 커밋하지 않고 둔 것: `CLAUDE.md`의 수정(사용자 것), `refine-logs/`(사용자 것).
- 지시 원문 요약: ① 선행 연구 검증 → ② 설계 결정(Codex·Claude 독립안 비교) → ③ 구현. 사용자·교수님이 정할 것(심상 종류와 심의, 통제 조건, 주 척도)은 확정하지 않고 "⚠ 팀 결정"으로 둠. `docs/research-design.md`와 노션은 고치지 않음. Codex는 이 작업 전체에서 최대 3회.

| 단계 | 상태 | 산출물 |
| --- | --- | --- |
| 1. 선행 연구 검증 | **끝** | `docs/rq-v4-lit-check.md`(요약 표 + 부록 A–F). Prudenzi 2019 전문은 두 번 시도하고도 못 엶 |
| 2. 설계 결정 | **끝** | `docs/codex-reviews/D2.md`(Codex, 1/3회), `docs/codex-reviews/D2_claude.md`, `docs/decisions.md` X42–X54, `docs/rq-v4-proposal.md` 0절(달라진 점 표)과 본문 갱신 |
| 3. 구현 | **끝**(데스크톱 모의 조작. 헤드셋 실기·XR 입력은 하지 않음) | `unity/Assets/IFS/Runtime/Placement/`, `chatbot/ifs_chatbot/eval/placement.py`, `docs/validation/placement/`, Codex 검토 `docs/codex-reviews/CP7.md`(2/3회)와 판정 X55–X63. dotnet 168/168, Unity EditMode 192/192, pytest 443 통과 |

이어받을 때:
```powershell
git branch --show-current      # claude/gallant-galileo-u02gqf 여야 함
git log --oneline -6
git status --short             # CLAUDE.md 수정과 refine-logs/ 는 원래 있던 것
cd chatbot; .\.venv\Scripts\python.exe -m pytest -q -m "not live"; cd ..
```
- 3단계의 기록 형식은 `unity/README.md`의 "배치 실험 러너" 절(구현되면)과 `docs/decisions.md` X54에 있습니다. 하위 에이전트는 다른 세션에서 재개할 수 없으니, 끊겼으면 git 상태를 보고 남은 부분만 새로 시킵니다.
- 사람이 정하거나 해야 할 일: `docs/morning-todo.md` 맨 위 절. 결과 요약: `docs/morning-report.md`.

## 헤드셋 프로토타입(2026-11-23)

> 하위 에이전트(Claude) 구현. 사용자가 Quest 3 헤드셋으로 배치 실험 러너를 돌릴 수 있게 해 달라고 지시. 1차 경로 = PC Unity(에디터 Play 또는 Windows 빌드) + Quest Link(OpenXR). 로컬 커밋 2개(푸시 없음).

한 일:
- **XR 기반**(커밋 ①, 되돌리기 쉽게 분리): 패키지 `com.unity.xr.management` 4.6.1 · `com.unity.xr.openxr` 1.16.1 · `com.unity.inputsystem` 1.20.0(Unity 6000.0.85 권장 버전). ProjectSettings `activeInputHandler` 0 → 2(Both), `EditorBuildSettings` config 객체 2개, `Assets/XR/`(Standalone: OpenXR 로더·Initialize XR on Startup, OpenXR 렌더 모드 Single Pass Instanced, Oculus Touch + Meta Quest Touch Plus 프로필). Android 설정 없음.
- **러너**(커밋 ②): XR 리그(`PlacementXrRig` — 바닥 원점 요청, 실험자 R = 정면 재설정), XR 컨트롤러 입력(`XrPlacementInput` + 규칙 `XrPlacementInputLogic`, 가짜 장치로 테스트), 입력 고르기(`inputMode` auto/desktop/xr), 헤드셋 안 참여자 판(`PlacementTextPanel`: 정면 2 m·중심 높이 0.6 m, 평정 문항 + 1–7 기준점, 글 깊이 검사), 평정 지시문·anchors 숫자 키(문구 형식 추가, 기존 파일 호환), 두 번째 문구 파일 `placement_task.scaleA.v0.json`(A 7문항 + S4–S8, 전부 draft), 설정 `participantRatesWithController`·`hideObjectDuringItems`(둘 다 기본 false), Setup 화면에서 입력·손·문구 파일 고르기, Windows 빌드 메뉴, `SceneSpecMist.shader`에 인스턴스 ID 전달(스테레오 인스턴싱), XR 설정 메뉴 `Editor/XR/XrProjectSetup.cs`.
- 기록 형식 `ifs-placement/0.1`은 추가만: manifest `config` 키 4개, `inputSource: xr`, events `items_instruction`·`xr_status`·`recenter`·`rating …;by=controller`. 분석기는 바꾸지 않음.

실행 방법: `unity/README.md` 「헤드셋 연결 (Quest 3 + Quest Link, OpenXR)」. 헤드셋 점검표: `docs/headset-checklist.md`.

확인한 것(헤드셋 없이): dotnet 234/234, Unity EditMode 278/278, pytest 443. 기존 자동 시행 5개(EX02, 기본 설정) 모두 완료·분석기 플래그 `runner_warning:1`(초안 문구)뿐. 배치 캡처(EX01·EX02) 콘솔 오류 0, 배치모드에서 XR 초기화 시도 없음. Windows 빌드 성공, 헤드셋 없이 실행하면 OpenXR이 `XR_ERROR_FORM_FACTOR_UNAVAILABLE`로 초기화에 실패하고 앱은 계속 돎(25초, 관리 코드 예외 없음).

**미검증(헤드셋을 쓰고 봐야 함)**: 작업 시점에 헤드셋이 연결돼 있지 않았습니다(OVRService 중지, Quest USB 장치 없음). XR 초기화 성공·`headSource = xr`, 바닥 높이·'나' 자리, 컨트롤러 조준 pose 이름(`PointerPosition` — 못 읽으면 grip pose + 30° 기울임으로 대체), 광선 잡기·밀기 체감, 판 글 가독성·자리, 스테레오 인스턴싱에서 안개 셰이더가 두 눈에 맞게 보이는지, Unity 자동 카메라 추적과 `HeadPoseProvider`의 이중 적용 여부, 72 Hz 유지, 멀미.

후속: Quest 단독(Android) 빌드(Android 로더·Meta Quest 기능·`adb`), IOS 그림 문항(S3)과 S1, 눈 추적 없음(Quest 3에는 장치가 없음 — 시선 각은 머리 방향), 소유감 러너의 헤드셋 경로(리그·입력), 헤드셋 성능 측정.

## 렌더 경로 개선(2026-11-23)

> 하위 에이전트(Claude) 구현, 설계는 `docs/decisions.md` X64–X72. 단계마다 로컬 커밋(푸시 없음).

한 일:
- 0단계 `ba36db1`: 합성 spec 13개(`docs/validation/render/specs/`, `make_specs.py`)와 기준선 캡처(`before/`, held-out은 `before/heldout/`).
- 1단계 `b1ab311`: `SceneLoader`의 형상 생성부를 `Runtime/Rendering/`의 `FormRenderPlan`(슬롯 값 → 렌더러 입력, meta.mapping을 받지 않음) + `IFormRenderer`로 옮김. 화면 변화 없음(golden 그대로, 캡처 params·color·renderStats 같음). BatchCapture의 Fade 판정 중복을 `RenderedColor.UsesFadeShader`로 합침.
- 2단계 `5dc9d91`: report.json에 `renderPath`·`renderPlan`·`visiblePixels`·`maxAlpha`·`silhouette{circularity, components, edgeFalloffPx …}`, `summary.renderPaths` (X72).
- 3단계 `dd3b815`: fragments = 각진 조각 5개를 합친 메시 하나(X67). 드로콜/눈 24 → 8, 삼각형 102,800 → 800, components 4 → 5.
- 4단계 `b81b801` + 보완 `ff3d483`: mist = 대리 구 + 부피 레이마칭 셰이더 `SceneSpecMist`(8걸음, X66). 처음 안(안쪽 면만)은 바닥 위 안개(H02)가 깊이 테스트로 사라져, 카메라 위치로 면을 고르는 한 패스(Cull Off) + 바닥 아래 밀도 0으로 바꿈. golden은 GOLD-mist 항목만 바뀜.
- 5단계: `after/`·`after/heldout/` 캡처, `docs/validation/render/README.md`(전후 표·요약), `sheet.png`, `unity/README.md` 렌더 절.

검증 명령:
```powershell
cd unity/Tools/compile-check; dotnet test Tests/IFS.SceneSpec.CompileCheck.Tests.csproj; cd ../../..   # 201 통과
& "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity -runTests -testPlatform EditMode -testResults <xml> -logFile <log>   # 237 통과
cd chatbot; .\.venv\Scripts\python.exe -m pytest -q -m "not live"; cd ..   # 443 통과
python docs/validation/render/compare.py   # 전후 표 다시 만들기(캡처 명령은 docs/validation/render/README.md)
```

후속 작업:
- shell 렌더러(X69): 이번에 바꾸지 않음(구 + 껍질 열림 프리셋 그대로).
- 정반사 남기기(X70 보류분): 넣지 않음. opacity 바닥값·윤곽선 보정도 없음 — 낮은 opacity는 거의 안 보이는 그대로(R03·H09).
- 헤드셋 실기에서 mist 채움 비용 측정: 데스크톱 대리 측정만 함(mist frameMsP95 +0.1–0.15 ms, 카메라가 안개 속이면 약 3–3.7 ms). Quest 모바일 GPU의 레이마칭 비용·셰이더 컴파일(GLES3/Vulkan)은 확인 안 함.
- 소유감 러너(X71): 규칙·기록·테스트는 그대로지만, 형태 변형 자극 중 mist·fragments의 화면이 달라졌다. 이전 내부 보정 시행 값을 다시 볼 것.
- 지표 한계: mist의 edgeFalloffPx는 넓어지지 않고 줄었다(둘레로 나누는 정의 때문). 사람 판정 필요. fragments 색 ΔE00은 평면 음영 때문에 커졌다(약 5 → 9–11).
- 매퍼 쪽 문제(H09의 부분 투명 → 전체 opacity 등)는 이번 범위 밖.

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
  - `5326ca9` CP3 (작업 5 E2E + AC 판정. 오프라인 374 통과)
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
- [x] 5. 실행 검증(E2E) — 끝. `docs/validation/e2e/`. **held-out에서 AC-3.2(0.698)·3.4(0.094)·3.5(0.859), AC-4.5(H09 빈 화면) 미달 → 전체 "완료 아님"**. 규칙은 고치지 않음(decisions X10)
- [x] docs/morning-report.md — 작성 끝

### Codex 체크포인트 (정확히 3번, 실패 시 재시도 1번)
- [x] CP1 — 1회 사용. 원문+분류표 `docs/codex-reviews/CP1.md`. 수용 11 / 보류 1(#12 인용 원문 대조, 사람)
- [x] CP2 — 1회 사용(2026-11-16 13:55, 종료 코드 0). 원문+분류표 `docs/codex-reviews/CP2.md`. 수용 6 · 일부 수용 2 · 반박 1 · 일부 반박·보류 1 · 보류 2. 지시문 `docs/codex-reviews/prompts/CP2_prompt.md`
- [x] CP3 — 1회 사용(2026-11-16 14:40, 종료 코드 0). 원문+분류표 `docs/codex-reviews/CP3.md`. 수용 3(모두 e2e.py 견고성), 반영 끝. 지시문 `docs/codex-reviews/prompts/CP3_prompt.md` (`<CP2_COMMIT>` = `58ba0dc`)

**Codex 사용 현황: 3번 모두 사용(CP1, CP2, CP3), 재시도 0. 어떤 이유로도 더 호출하지 않습니다.** 다른 계정으로 넘어가도 이 횟수는 이어집니다. 이 외 용도로 절대 호출하지 마세요.

Codex 실행 명령(Git Bash, 저장소 루트에서. CP1 때 쓴 것과 같은 형식):
```bash
codex exec --sandbox read-only -c model_reasoning_effort="medium" -C . -o /tmp/cpN_last.md - < docs/codex-reviews/prompts/CPN_prompt.md
```
- 출력 원문을 `docs/codex-reviews/CPN.md`에 저장(맨 위에 실행 명령·시각·종료 코드, 그 아래 지시문, 그 아래 원문). 그 뒤에 "수용 / 반박(근거) / 보류" 표를 붙이고, 수용한 것만 반영 후 커밋.
- 사용 한도 에러면 재시도하지 말고 Claude 검토자(별도 서브에이전트, 같은 지시문)로 대체하고 그 사실을 CPN.md와 decisions.md에 기록.

## 4. 지금 상태 (세션 edd117bf, 2026-11-16) — 야간 작업 끝, 진행 중인 것 없음

- 다섯 작업의 구현·실행·검토, Codex 3번, `docs/morning-report.md`까지 끝났습니다. **판정은 "완료 아님"**: AC-3(held-out 반영률 0.698·왜곡률 0.094·미반영 원문 보존률 0.859)과 AC-4.5(H09 빈 화면)가 미달입니다. 판정 표는 `docs/acceptance.md` 맨 아래.
- 마지막으로 잰 값: 오프라인 테스트 394 통과, drift 라벨 정확도 1.000, Unity EditMode 28/28, held-out sha 그대로.
- **이어서 할 일은 사람의 결정이 먼저입니다**(`docs/morning-todo.md` 맨 위 세 항목): AC-3 미달을 어떻게 이어갈지, AC-5.3 문구 수정을 인정할지, 스크린샷 60장 확인.
- **하지 말 것:** 지금 held-out(`heldout.json`)을 보고 매핑 규칙을 고치는 일(평가 무효, D04·X10), Codex 추가 호출, push·main 병합(사람이 검토 후 PR).
- 모델 배정(D09): 판단·분류·판정·보고서는 메인 세션(Fable), 구현·테스트 실행·검토·수정 서브에이전트는 opus.

## 5. 야간 작업의 순서 (모두 끝남. 기록용)

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
