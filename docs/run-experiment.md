# 실험 실행 순서서 (main 하나로 한 세션을 처음부터 끝까지)

작성 2026-11-27. 기준은 `docs/design-backbone.md` 2절(진행 순서)과 3절(본 실험 권고 설정)입니다. 이 문서는 순서와 명령만 적고, 자세한 설명은 이미 있는 문서를 가리킵니다.

> **이 실험은 지도교수의 결정으로 IRB 심의 없이 참여자를 모집해 진행합니다(결정 G68).** 그래서 세션마다 `docs/participant-protection.md`의 대상 확인·동의서·멈춤과 위기 대응·자료 다루기·디브리핑을 지킵니다. 화면·헤드셋의 고정 문구는 모두 초안(`status: draft`)입니다.

## 0. 한눈에 보기

| # | 뼈대 2절 단계 | 어디서 | 실행 | 앞 단계와 이어짐 |
| --- | --- | --- | --- | --- |
| 1 | 면담(떠올리기) | PC 브라우저 | 챗봇 서버 `--config experiment` | — |
| 2 | 물체 고르고 고치기 | 같은 화면 | 확정 → [다음 단계로] → 후보 → 조절 | **이어짐**(같은 세션, 매퍼 v2 spec이 세션 안에서 바로 만들어짐) |
| 3 | 사전 문항(컴퓨터) | 같은 화면 | 사전 측정 10문항 | **이어짐** |
| 4 | 헤드셋 → 직접 배치 / 보기만 | Unity 러너 | Setup에 spec·선택 파일 이름, 조건, [본 실험 권고 설정 켜기] | **손으로 이어야 함**: 세션 ID로 파일 이름을 적고 조건을 고름(배정표는 실험자가 가짐). 파일 복사는 필요 없음(에디터 Play 기준) |
| 5 | 사후 문항 | 헤드셋 | 러너 `post_items` | 이어짐(러너 안) |
| 6 | 자리 문항 | 헤드셋 | 러너 `check_items` | 이어짐 — 권고 설정이 멈춤 거리 **앞**으로 옮김 |
| 7 | 멈춤 거리 | 헤드셋 | 러너 `stop_distance`(반복 멈춤 loop) | 이어짐 |
| 8 | 헤드셋 벗고 짧은 면담 | PC 브라우저 | `/?view=postinterview&session=<세션ID>` | **손으로 이어야 함**: 주소를 열고 조건을 고름. 서버가 꺼졌으면 같은 설정으로 다시 띄우면 됨 |
| 9 | 분석 | PC | `python -m ifs_chatbot.eval.placement … --selection-dir …` | 이어짐: 세션 ID(= spec 파일 이름)로 사전 문항·사후 면담을 헤드셋 기록에 붙임 |

생성 메시 후보(G62)는 이 흐름에 **들어가 있지 않습니다**(6절).

## 1. 준비 (처음 한 번)

1. **파이썬 환경과 로컬 모델**: `chatbot/README.md` 「실행」의 venv·`ollama pull` 두 줄(면담 모델 `gemma4:e4b`, 가드 `kanana-safeguard-8b`). `experiment.toml`은 가드 모델이 **있어야** 시작합니다(`guard.required = true`). 세션 기록에 모델 digest가 남습니다.
2. **설정 확인**: `chatbot/config/experiment.toml`을 엽니다. 이것 하나가 v4 흐름 + 감정어 다리 질문(G64) + 면담 앞부분 G70(프로토콜 1.6: 위치 질문 없음, '그 느낌' 호칭, 질문 틀 규칙, 안전 사전 0.3.0 — docs/chatbot-design.md 5-4) + 뼈대 3절의 웹 쪽 권고값(초안 경고 줄을 참여자 보기에서 숨김)입니다. 어느 설정에서 무엇을 가져왔는지는 파일 머리말에 있습니다.
   - `researcher_contact`를 채웁니다(위기 고정 문구에 들어감). 파일을 고치지 않으려면 서버를 띄울 때 `--researcher-contact "…"`.
3. **미리보기 빌드**(후보·조절 화면의 형상 그림): `docs/internal-trial-guide.md` 1절의 robocopy + WebGL·Windows 미리보기 빌드 명령. 빌드가 없으면 정지 그림 → 글 요약으로 내려갑니다(기록에 남음).
4. **헤드셋 러너**: Unity 6000.0.85f2로 `<repo>/unity`를 열고 `Assets/IFS/Scenes/PlacementExperiment.unity`를 엽니다(없으면 메뉴 IFS ▸ Experiment ▸ Create Placement Experiment Scene). 헤드셋 연결은 `unity/README.md` 「헤드셋 연결 (Quest 3 + Quest Link, OpenXR)」, 처음 쓸 때 점검은 `docs/headset-checklist.md`.
   - **에디터 Play로 돌리는 것을 권합니다.** 에디터에서는 spec 목록 폴더가 `<repo>/chatbot/logs/scenes`라 챗봇이 쓴 파일을 그대로 읽습니다.
   - Windows 빌드(`unity/README.md` 같은 절 끝)를 쓰면 spec 목록 폴더가 `%USERPROFILE%\AppData\LocalLow\DefaultCompany\unity\IFS\scenes`로 바뀝니다. 파일을 옮기지 말고 Setup에 **절대 경로**(`<repo>\chatbot\logs\scenes\<세션ID>.json`, `<repo>\chatbot\logs\selection\<세션ID>\selection.json`)를 적습니다. 빌드에 실험 파일을 넣을 필요는 없습니다(러너가 실행 때 디스크에서 읽음).
5. **조건 배정표**: 직접 배치(`place`) / 보기만(`view` · `static`)을 참여자 번호별로 정해 둡니다. 멈춤 거리 첫 방향의 기본값(`by_participant`)은 번호 홀짝이라, 배정도 홀짝으로 하면 둘이 겹칩니다 — `unity/README.md` 「배치 실험 러너 ▸ 단계」의 "첫 방향과 조건 배정이 얽힐 수 있습니다" 문단대로 균형을 잡습니다.

## 2. 세션 한 번

세션 ID는 가명(영문·숫자·`_`·`-`, 예 `P01`)으로 정합니다. 이 ID가 spec 파일 이름이 되고, 분석기가 이 이름으로 세 곳의 기록을 잇습니다.

### 2.1 면담 → 물체 → 사전 문항 (PC)

```powershell
cd <repo>\chatbot
.venv\Scripts\python.exe -m ifs_chatbot.server --config experiment
```

1. 서버 창의 경고를 읽습니다: 다리 질문 문구 초안, `[selection] … 문구 29개가 초안`. 가드 모델이 없다는 오류로 멈추면 Ollama를 켭니다.
2. 브라우저에서 `http://127.0.0.1:8000`(처음은 연구자 보기). 이 설정은 면담 조건을 고정합니다(`[interview] lock_condition = true`): 시작 화면에 조건 고르기가 없고 "면담: 조건 2 · AI 챗봇 면담 (설정으로 고정)" 한 줄만 보입니다. 다른 조건으로 세션을 만들라는 요청은 서버가 거절합니다(409). 그 줄을 확인하고 세션 ID를 적어 [세션 만들기] → 참여자에게는 `http://127.0.0.1:8000/?sid=<세션ID>&view=participant`로 넘깁니다. 화면 조작과 각 단계의 모습은 `docs/internal-trial-guide.md` 2절 3–8번과 같습니다(그 문서의 `--config v4 --backend offline --condition static`만 이 명령으로 바뀝니다).
3. 면담 → 확정 → [다음 단계로] → 후보 고르기 → 조절 → 사전 측정 [제출]까지 한 화면에서 이어집니다. 생기는 파일은 `docs/internal-trial-guide.md` 3절의 표와 같습니다(`chatbot/logs/`, git 밖).

### 2.2 헤드셋 (Unity 러너)

1. Unity에서 Play. 참여자를 원판 가운데에 세우고 R(정면 재설정).
2. Setup:
   - 참여자 번호
   - spec: 목록에서 **`<세션ID>.json`** 단추(`.v0`·`.v1`·`.v2.json`은 비교용이라 고르면 해시가 달라 시작이 거부됩니다)
   - 선택 파일: `../selection/<세션ID>/selection.json`
   - 조건: 배정표대로 `place` 또는 `view`(통제 방식 `static`)
   - **[본 실험 권고 설정 켜기]** 단추를 누릅니다. 한 번에 켜는 것: 공간 B(`neutral`) + 놓기 도움, 두 조건 모두 배치 연습, 자리 문항을 멈춤 거리 앞으로, 평정 동안 물체 숨김, 헤드셋 UI 개선 묶음(G63), 멈춤 거리 반복 멈춤(`stopMode loop`, G60-2·G60-4), 눈높이 기준 배치(`eyeHeightMode relative`, G60-3), 문구 파일 scaleA(뼈대 3절·G59-8). 켜지면 단추 앞에 ●가 붙고 아래 낱개 체크도 따라 바뀝니다. 조건과 안내 판 숨기기는 이 단추가 건드리지 않습니다(7절).
   - 참여자 입력 `auto`, 주 사용 손
3. [확인] → 확인 화면의 선택 파일 요약(고른 후보, 덮어쓰기)과 경고를 읽습니다. 눈높이 기준 배치가 켜져 있으므로 [시작] 전에 눈높이를 잽니다: 참여자를 원판 가운데에 세움 → R → 말로 "편하게 똑바로 서서 앞을 봐 주세요" → H(또는 "눈높이 재기"). 실험자 화면에 `눈높이 E = … m`가 나오면 [시작]. 보정을 통과하지 못하면 시작이 거부되니 이유대로 고쳐 다시 H(`docs/internal-trial-guide.md` 4절 G60-3 항목). 초안 문구 경고는 PC의 실험자 화면에만 나오고 헤드셋에는 나오지 않습니다.
4. 단계: `intro → practice → baseline → pre_items → pre_wait → condition(90초) → post_items → check_items(자리 문항) → post_wait → stop_distance(반복 멈춤: 연습 1 + 본 4라운드, 트리거 = 멈춤/다시 움직임, A·X = 확정) → done`. 실험자 키는 `unity/README.md` 「데스크톱 조작 키」, 참여자 컨트롤러는 「컨트롤러 조작」.
5. 끝나면 실험자 화면에 기록 폴더가 나옵니다. 기본 기록 루트는 `%USERPROFILE%\AppData\LocalLow\DefaultCompany\unity\IFS\sessions`(git 밖)입니다.

### 2.3 사후 면담 (PC)

헤드셋을 벗은 뒤 `http://127.0.0.1:8000/?view=postinterview&session=<세션ID>`를 열고 조건을 고릅니다. 대본·실험자 규칙은 `docs/post-interview-guide.md`. 녹음하지 않고 받아 적습니다. 기록은 `chatbot/logs/selection/<세션ID>/postinterview.json`.

서버를 이미 껐다면 같은 명령(`--config experiment`)으로 다시 띄우면 됩니다(그 세션 폴더에 `selection.json`이 있으면 열림). 끝나면 서버 창에서 Ctrl+C.

## 3. 분석

```powershell
cd <repo>\chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.placement --records "$env:USERPROFILE\AppData\LocalLow\DefaultCompany\unity\IFS\sessions" --out <결과 폴더(저장소 밖)> --selection-dir logs\selection
```

- 결과: `placement_sessions.csv`(세션 1행: 놓은 자리, 반복 멈춤 확정 거리 `stop_final_*`, 눈높이 기준 열 `eye_height_m`·`final_height_rel_eye_m` 등, 헤드셋 평정 `rating_<문항>_<pre|post|check>`, 사전 측정 `pre_*`, 사후 면담 `pi_*`), `stop_loop_rounds.csv`(라운드 1행), `stop_trials.csv`, `placement_summary.json`.
- 주 분석의 사전 점수는 헤드셋 `pre_items`(`rating_A1_pre` 등), 컴퓨터 사전 측정(`pre_A1` 등)은 보조입니다(G67). 열의 뜻은 `chatbot/ifs_chatbot/eval/placement.py`와 `eval/self_report.py` 머리말.
- 미리 정한 분석 규칙(민감도 분석)은 뼈대 6절과 `docs/decisions.md` G59-11. 분석기는 기술 통계만 내고 유의성 판정은 하지 않습니다.

## 4. 시작 전 점검(합성 대사로, 실제 참여자 없이)

```powershell
cd <repo>\chatbot
.venv\Scripts\python.exe -m pytest tests\test_experiment_config.py              # 모의 LLM: 면담 → 후보 → 사전 측정 → 사후 면담 기록
$env:IFS_LIVE=1; .venv\Scripts\python.exe -m pytest tests\test_experiment_config.py -k live   # 실제 로컬 LLM 1개
```

헤드셋 없이 러너가 그 파일을 읽는지(Unity 에디터를 닫은 상태에서, 저장소 루트):

```powershell
& "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity `
  -executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.RunAutoTrialBatch `
  -recordRoot <저장소 밖 폴더> -specPath chatbot\logs\scenes\<세션ID>.json -selectionPath chatbot\logs\selection\<세션ID>\selection.json `
  -condition view -controlMode static -experimentPreset true -conditionSeconds 12 -baselineSeconds 1 -logFile <로그>
```

`-experimentPreset true`는 [본 실험 권고 설정 켜기]와 같고(문구 파일 scaleA 포함), 뒤에 적은 낱개 인자가 덮어씁니다. 자동 시행에는 헤드셋이 없어 눈높이를 재지 않고 기준값 1.60 m를 씁니다(`eye_height_source = desktop_fixed`, 러너의 기존 동작). 그 밖의 인자는 `unity/README.md` 「배치 실험 러너 ▸ 실행」.

2026-11-27 이 순서로 확인했습니다: 합성 시나리오 `emotion_bridge_x`로 만든 세션 파일 → 자동 시행(직접 배치, 권고 설정) 완료 → `stoprounds.csv`·`stopadjust.csv`가 생기고, 분석기가 반복 멈춤 열(`stop_mode = loop`, `stop_final_mean_m`)·눈높이 열(`eye_height_source = desktop_fixed`)·사전 측정·사후 면담 열을 붙임. 플래그는 `runner_warning:1`(초안 문구)과 `stop_unconfirmed:1`(자동 스크립트가 일부러 확정하지 않은 라운드).

## 5. 장애가 났을 때

| 증상 | 할 일 |
| --- | --- |
| 서버가 "가드 모델을 찾지 못했습니다 … guard.required = true"로 멈춤 | Ollama를 켜고 가드 모델을 받습니다. 점검만 할 때는 `--no-guard-model` |
| 러너가 "specSha256" 때문에 시작을 거부 | spec 파일을 고치거나 옮겨 저장하지 않았는지, `.v2.json`이 아니라 `<세션ID>.json`을 골랐는지 |
| 미리보기가 정지 그림·글 요약으로 내려감 | 1절 3번 빌드. 내려간 이유는 연구자 화면 "미리보기"와 `selection.json`의 `preview` |
| 그 밖 | `docs/internal-trial-guide.md` 7절(알려진 한계), `unity/README.md` 「문제 해결」 |

## 6. 생성 메시 후보(G62)는 왜 꺼져 있나

`experiment.toml`은 `[gen3d] enabled = false`입니다. 챗봇은 생성 모델을 부르지 않고, 확정 뒤 [다음 단계로]를 누르는 순간에 자산 폴더를 **한 번만** 찾습니다. 그 전에 누군가 확정 텍스트를 생성 도구 입력에 옮기고, 면담 모델을 내려 GPU 메모리를 비우고, `tools/gen3d/generate.py`를 별도 환경에서 돌려야 합니다(모델 적재 포함 약 2분, 생성만 약 30초). 이것을 자동으로 잇는 장치와 대기 화면이 없어 실제 세션에서는 손으로 맞추기 어렵습니다. 켜는 방법과 검증 결과는 `chatbot/config/v4-gen3d.toml`, `docs/gen3d-feasibility.md`, `docs/validation/run-g64-e2e/README.md` 「생성 메시 경로」.

## 7. 아직 사람이 정할 것 (이 문서가 켜지 않은 것)

- 조건·멈춤 거리 단계에서 안내 판 숨기기(G63 (7)): 꺼 둠.
- 면담 모델: `gemma4:e4b`(G64 검증에 쓴 모델). `pilot.toml`의 `gemma4:31b`는 16 GB GPU에 올라가지 않습니다.
- 주 척도 A1–A7은 컴퓨터 사전 측정과 헤드셋 `pre_items`(scaleA) 양쪽에서 묻습니다. 코드는 그대로 두고, 주 분석의 사전 점수는 헤드셋 쪽으로 정했습니다(G67, 3절).
