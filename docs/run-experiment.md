# 실험 실행 순서서 (main 하나로 한 세션을 처음부터 끝까지)

작성 2026-11-27. 기준은 `docs/design-backbone.md` 2절(진행 순서)과 3절(본 실험 권고 설정)입니다. 이 문서는 순서와 명령만 적고, 자세한 설명은 이미 있는 문서를 가리킵니다.

> **이 실험은 지도교수의 결정으로 IRB 심의 없이 참여자를 모집해 진행합니다(결정 G68).** 그래서 세션마다 `docs/participant-protection.md`의 대상 확인·동의서·멈춤과 위기 대응·자료 다루기·디브리핑을 지킵니다. 화면·헤드셋의 고정 문구는 모두 초안(`status: draft`)입니다.

## 0. 한눈에 보기

| # | 뼈대 2절 단계 | 어디서 | 실행 | 앞 단계와 이어짐 |
| --- | --- | --- | --- | --- |
| 1 | 면담(떠올리기) | PC 브라우저 | 챗봇 서버 `--config experiment` | — |
| 2 | 물체 고르고 고치기 | 같은 화면 | 확정 → [다음 단계로] → 후보 → 조절 | **이어짐**(같은 세션, 매퍼 v2 spec이 세션 안에서 바로 만들어짐) |
| 3 | 사전 문항(컴퓨터) | 같은 화면 | 사전 측정 10문항 | **이어짐** |
| 4 | 헤드셋 → 직접 배치 / 보기만 | Unity 러너 | Setup: 자동으로 채운 최근 세션 확인, 참여자 번호, 조건 | **반쯤 이어짐**: spec·선택 파일은 챗봇이 가장 최근에 내보낸 세션으로 자동으로 채워지고(실험자가 세션 ID를 확인), 조건은 배정표대로 고름. 권고 설정은 실험 씬에서 고정. 파일 복사는 필요 없음(에디터 Play 기준) |
| 5 | 사후 문항 | 헤드셋 | 러너 `post_items` | 이어짐(러너 안) |
| 6 | 자리 문항 | 헤드셋 | 러너 `check_items` | 이어짐 — 권고 설정이 멈춤 거리 **앞**으로 옮김 |
| 7 | 멈춤 거리 | 헤드셋 | 러너 `stop_distance`(반복 멈춤 loop) | 이어짐 |
| 8 | 헤드셋 벗고 짧은 면담 | PC 브라우저 | `/?view=postinterview&session=<세션ID>` | **손으로 이어야 함**: 주소를 열고 조건을 고름. 서버가 꺼졌으면 같은 설정으로 다시 띄우면 됨 |
| 9 | 분석 | PC | `python -m ifs_chatbot.eval.placement … --selection-dir …` | 이어짐: 세션 ID(= spec 파일 이름)로 사전 문항·사후 면담을 헤드셋 기록에 붙임 |

생성 메시를 **기본 후보**로 두는 G62 경로는 이 흐름에 들어가 있지 않습니다(6절). 대신 참여자가 후보 화면에서 [맞는 게 없어요]를 누르면 그 자리에서 형태를 하나 만들어 새 후보로 보여 줍니다(G73, 6절).

## 1. 준비 (처음 한 번)

1. **파이썬 환경과 로컬 모델**: `chatbot/README.md` 「실행」의 venv·`ollama pull` 두 줄(면담 모델 `gemma4:e4b`, 가드 `kanana-safeguard-8b`). `experiment.toml`은 가드 모델이 **있어야** 시작합니다(`guard.required = true`). 세션 기록에 모델 digest가 남습니다.
2. **설정 확인**: `chatbot/config/experiment.toml`을 엽니다. 이것 하나가 v4 흐름 + 감정어 다리 질문(G64) + 면담 앞부분 G70(프로토콜 1.6: 위치 질문 없음, '그 느낌' 호칭, 질문 틀 규칙, 안전 사전 0.3.0 — docs/chatbot-design.md 5-4) + 뼈대 3절의 웹 쪽 권고값(초안 경고 줄을 참여자 보기에서 숨김)입니다. 어느 설정에서 무엇을 가져왔는지는 파일 머리말에 있습니다.
   - `researcher_contact`를 채웁니다(위기 고정 문구에 들어감). 파일을 고치지 않으려면 서버를 띄울 때 `--researcher-contact "…"`.
3. **미리보기 빌드**(후보·조절 화면의 형상 그림): `docs/internal-trial-guide.md` 1절의 robocopy + WebGL·Windows 미리보기 빌드 명령. 빌드가 없으면 정지 그림 → 글 요약으로 내려갑니다(기록에 남음).
4. **헤드셋 러너**: Unity 6000.0.85f2로 `<repo>/unity`를 열고 `Assets/IFS/Scenes/PlacementExperiment.unity`를 엽니다(없으면 메뉴 IFS ▸ Experiment ▸ Create Placement Experiment Scene). 헤드셋 연결은 `unity/README.md` 「헤드셋 연결 (Quest 3 + Quest Link, OpenXR)」, 처음 쓸 때 점검은 `docs/headset-checklist.md`.
   - **에디터 Play로 돌리는 것을 권합니다.** 에디터에서는 spec 목록 폴더가 `<repo>/chatbot/logs/scenes`라 챗봇이 쓴 파일을 그대로 읽습니다.
   - 실험 씬의 `PlacementRunner`는 **본 실험 설정 잠금**(`lockExperimentPreset`)이 켜져 있습니다. 인스펙터의 「본 실험(2026-11-28)」 칸에서 확인합니다(씬을 메뉴로 다시 만들어도 켜짐). 코드 기본값과 자동 시행은 꺼짐입니다.
   - Windows 빌드(`unity/README.md` 같은 절 끝)를 쓰면 spec 목록 폴더가 `%USERPROFILE%\AppData\LocalLow\DefaultCompany\unity\IFS\scenes`로 바뀝니다. 파일을 옮기지 말고 Setup에 **절대 경로**(`<repo>\chatbot\logs\scenes\<세션ID>.json`, `<repo>\chatbot\logs\selection\<세션ID>\selection.json`)를 적습니다. 빌드에 실험 파일을 넣을 필요는 없습니다(러너가 실행 때 디스크에서 읽음).
5. **조건 배정표**: 직접 배치(`place`) / 보기만(`view` · `static`)을 참여자 번호별로 정해 둡니다. 멈춤 거리 첫 방향의 기본값(`by_participant`)은 번호 홀짝이라, 배정도 홀짝으로 하면 둘이 겹칩니다 — `unity/README.md` 「배치 실험 러너 ▸ 단계」의 "첫 방향과 조건 배정이 얽힐 수 있습니다" 문단대로 균형을 잡습니다.

## 2. 세션 한 번

세션 ID는 가명(영문·숫자·`_`·`-`, 예 `P01`)으로 정합니다. 이 ID가 spec 파일 이름이 되고, 분석기가 이 이름으로 세 곳의 기록을 잇습니다.

### 2.1 면담 → 물체 → 사전 문항 (PC)

```powershell
cd <repo>\chatbot
.venv\Scripts\python.exe -m ifs_chatbot.server --config experiment
```

1. 서버 창의 경고를 읽습니다: 다리 질문 문구 초안, `[selection] … 문구 36개가 초안`(G73 문구 4개 포함). 가드 모델이 없다는 오류로 멈추면 Ollama를 켭니다.
2. 브라우저에서 `http://127.0.0.1:8000`(처음은 연구자 보기). 이 설정은 면담 조건을 고정합니다(`[interview] lock_condition = true`): 시작 화면에 조건 고르기가 없고 "면담: 조건 2 · AI 챗봇 면담 (설정으로 고정)" 한 줄만 보입니다. 다른 조건으로 세션을 만들라는 요청은 서버가 거절합니다(409). 그 줄을 확인하고 세션 ID를 적어 [세션 만들기] → 참여자에게는 `http://127.0.0.1:8000/?sid=<세션ID>&view=participant`로 넘깁니다. 화면 조작과 각 단계의 모습은 `docs/internal-trial-guide.md` 2절 3–8번과 같습니다(그 문서의 `--config v4 --backend offline --condition static`만 이 명령으로 바뀝니다).
3. 면담 → 확정 → [다음 단계로] → 후보 고르기 → 조절 → 사전 측정 [제출]까지 한 화면에서 이어집니다. 생기는 파일은 `docs/internal-trial-guide.md` 3절의 표와 같습니다(`chatbot/logs/`, git 밖).

### 2.2 헤드셋 (Unity 러너)

1. **헤드셋 안에서 Link를 먼저 켠 뒤** Unity에서 Play. 실험자 화면 맨 위 XR 줄이 `XR: 헤드셋 켜짐(…) … 추적 원점: Floor`인지 봅니다. 빨간 줄 `XR: 헤드셋 없음 — 데스크톱으로 도는 중`이면 XR이 켜지지 않은 것이고(Link가 꺼져 있었거나 헤드셋이 잠들어 있었음 — 콘솔 `XR_ERROR_FORM_FACTOR_UNAVAILABLE`), 이때 참여자가 헤드셋의 Link 데스크톱 보기로 이 실험자 화면을 볼 수 있습니다. Link를 켜고 Play를 다시 누릅니다(실험 씬에서는 이 상태로 [확인]하면 시작이 거부됩니다. 헤드셋 없이 시험할 때만 참여자 입력을 `desktop`으로). XR이 켜져 있으면 실험자 화면(설정·세션 ID·참여자 번호·조건)은 PC 모니터에만 보이고, 헤드셋에는 빈 공간과 대기 안내 판("잠시 기다려 주세요. 다음 안내가 나올 거예요.", 문구 `wait`)만 보입니다(2026-11-28).
   참여자를 원판 가운데 의자에 앉히고(본 실험은 앉아서 합니다) R(정면 재설정). 실험자 화면의 `지금 머리 높이 … m` 줄로 바닥 높이를 먼저 봅니다: 앉은 자세에서 0.95–1.45 m 밖이면 노란 줄이 나오고, 그때는 Quest 바닥 높이(설정 ▸ 물리적 공간 ▸ 경계/바닥)를 다시 맞춥니다.
2. Setup:
   - **자동으로 고른 세션**(Setup 맨 위, 2026-11-28): Play를 누를 때와 [다음 참여자 준비] 때 러너가 챗봇이 가장 최근에 저장한 `selection/<세션ID>/selection.json`과 짝 `scenes/<세션ID>.json`을 spec·선택 파일 칸에 채웁니다. 짝은 폴더 이름·`sessionId`·spec `meta.sessionId`(없어도 거부)·`specSha256`(spec 파일 바이트)이 모두 맞을 때만이고, 가장 최근 것이 맞지 않으면 더 오래된 세션으로 내려가지 않고 아무것도 채우지 않습니다(이유가 노란 줄로 나옴). 가장 최근 저장 시각이 지금보다 2분(`autoFillFutureToleranceMinutes`) 넘게 미래면 PC 시계 오류로 보고 채우지 않으며 큰 빨간 줄이 나옵니다 — 시계를 확인하고 손으로 고릅니다. 맨 위 줄의 **세션 ID와 저장 시각(몇 분 전)이 지금 참여자 것인지 확인**합니다. 30분보다 오래됐거나(`autoFillStaleMinutes`), 이 세션 ID의 기록 폴더가 이미 있거나, 더 늦게 저장된 spec에 선택 파일이 아직 없으면 노란 줄이 붙습니다. 챗봇 세션이 Play 뒤에 끝났으면 [최근 세션 다시 찾기]. 다른 파일을 쓰려면 아래 칸·목록 단추로 바꾸면 됩니다. 기록 manifest `sessionFiles.source`는 자동으로 채운 그대로면 `auto`, 채운 뒤 바꿨으면 `auto_overridden`이고, 자동 채움이 아무것도 채우지 않은 세션에는 이 키가 없습니다. 자동 채움은 칸만 채우고 시작하지 않습니다.
   - 참여자 번호: spec `meta.participantId`가 숫자(또는 P+숫자)일 때만 자동으로 채워집니다. 지금 챗봇 웹 화면은 이 값을 보내지 않아 보통 **손으로 넣습니다**. 조건도 챗봇 파일에 없어서 손으로 고릅니다.
   - spec: 손으로 고를 때는 목록에서 **`<세션ID>.json`** 단추(`.v0`·`.v1`·`.v2.json`은 비교용이라 고르면 해시가 달라 시작이 거부됩니다)
   - 선택 파일: 손으로 고를 때는 `../selection/<세션ID>/selection.json`
   - 조건: 배정표대로 `place` 또는 `view`(통제 방식 `static`)
   - **본 실험 설정 고정**: 실험 씬에서는 권고 설정, 멈춤 거리 절차 값(연습 1 × 상한 30초 + 본 1 × 상한 75초, 연습과 본 측정 사이 2초, 왕복 0.4–3.6 m · 0.25 m/s 등), 문구 파일 scaleA가 Play·[확인]·다음 참여자 때마다 자동으로 적용되고, 화면에는 낱개 토글 대신 "본 실험 설정 고정" 요약 다섯 줄만 보입니다(manifest `flags.experimentPresetLocked: true`). 2026-11-28 연구 책임자 결정으로 **공간은 실험자가 설정 화면에서 고릅니다**: 잠금 요약 위의 공간 단추 셋(기본 (neutral) · 자연 (nature) · 우주 (space), 처음 눌린 값 neutral)으로 세션마다 고르고, 잠금은 고른 공간을 바꾸지 않습니다(`environmentChoice experimenter`, 고른 공간은 manifest `config.environment`에). [다음 참여자 준비] 뒤에도 앞 참여자의 공간이 남으니 다시 확인합니다. 참여자가 헤드셋에서 고르는 단계(`space_choice`)는 꺼 둔 기능이라 실험 씬에서는 돌지 않습니다(설정 화면에 토글 없음). **눈높이 보정은 앉은 자세**(`eyeCalibPosture seated`, 범위 [0.95, 1.45] m)입니다 — 요약 첫 줄과 넷째 줄에 보입니다. 읽은 문구 파일의 판이 `0.10-scaleA`가 아니거나 G78 문구 네 개(`confirm_button_right/left`, `confirm_done`, `stop_main_start`)가 없으면, 또는 설정이 잠금 값과 다르면 [확인]·[시작]이 거부됩니다(빨간 줄). 고정하지 않고 화면에 남는 것: 공간, 안내 판 숨기기, 선택 단계 문항, 묻지 않을 문항 키, 참여자 컨트롤러 평정, 보기만 통제 방식, 참여자 입력·주 사용 손. 잠금을 끈 씬에서는 아래처럼 **[본 실험 권고 설정 켜기]** 단추를 누릅니다(설정은 저장되지 않아 Play마다 다시). 한 번에 켜는 것: 공간 B(`neutral`) + 놓기 도움, 두 조건 모두 배치 연습, 자리 문항을 멈춤 거리 앞으로, 평정 동안 물체 숨김, 헤드셋 UI 개선 묶음(G63), 멈춤 거리 반복 멈춤(`stopMode loop`, G60-2·G60-4), 눈높이 기준 배치(`eyeHeightMode relative`, G60-3), 문구 파일 scaleA(뼈대 3절·G59-8). 켜지면 단추 앞에 ●가 붙고 아래 낱개 체크도 따라 바뀝니다. 조건과 안내 판 숨기기는 이 단추가 건드리지 않습니다(7절).
   - 참여자 입력 `auto`, 주 사용 손
   - 멈춤 거리는 연습 1번(상한 30초, `stopLoopPracticeRoundSeconds`)과 본 측정 1번(상한 75초, `stopLoopRounds` 1 — 2026-11-28 연구 책임자 결정 G83, 이전 4번)입니다. 본 측정은 라운드를 되풀이하지 않고, 75초 안에 참여자가 언제든 트리거로 멈추고 다시 움직이다가 멈춘 자리에서 확인 버튼(오른손 A, 왼손 설정이면 X)으로 한 번 정합니다. 75초 전에 확정하면 그때 끝나고, 시간 안에 확정하지 않으면 확정값은 빈칸입니다(마지막 멈춤 거리는 따로 남음). 연습 뒤 2초 동안 「연습이 끝났어요. 이제 본 측정을 시작할게요.」(연습을 확정했으면 위에 「정했어요.」)가 보이고, 본 측정을 확정하면 「정했어요.」가 2초 보인 뒤, 시간 초과면 기다리지 않고 다음 단계로 갑니다. 본 측정의 출발 방향은 연습의 반대입니다(홀수 번호는 연습 가까워지며·본 멀어지며 출발, 짝수 번호는 그 반대).
3. [확인] → 확인 화면의 선택 파일 요약(고른 후보, 덮어쓰기)과 경고를 읽습니다. 눈높이 기준 배치가 켜져 있으므로 [시작] 전에 눈높이를 **과제를 하는 자세(앉은 자세)로** 잽니다: 참여자를 원판 가운데 의자에 앉힘 → R → 말로 "편하게 앉아서 앞을 봐 주세요"(대본 초안 — ⚠ 연구 책임자 확인) → H(또는 "눈높이 재기"). 실험자 화면에 `눈높이 E = … m`가 나오면 [시작]. 서서 재면 앉은 자세 범위를 넘어 실패합니다(서서 잰 값으로 앉아 과제를 하면 물체·안내 판이 그 차이만큼 눈보다 높게 놓입니다). 보정을 통과하지 못하면 시작이 거부되니 이유대로 고쳐 다시 H(`docs/internal-trial-guide.md` 4절 G60-3 항목). 실패 이유가 범위 밖이면 먼저 `지금 머리 높이` 줄과 Quest 바닥 높이를 봅니다(범위를 넓히는 우회 수단은 화면에 없습니다). 초안 문구 경고는 PC의 실험자 화면에만 나오고 헤드셋에는 나오지 않습니다.
4. (꺼 둔 기능 — 실험 씬에서는 돌지 않음) 잠금을 끄고 인스펙터·명령줄로 `environmentChoice participant`를 켰을 때만 [시작] 뒤 첫 단계가 **참여자 공간 고르기**(`space_choice`)입니다. 실험에서는 공간을 실험자가 2단계 Setup의 공간 단추로 고르고 [시작] 뒤 바로 intro입니다. 켰을 때의 동작: 헤드셋 판에 "과제를 할 공간을 골라 주세요. 방아쇠를 누르면 다음 공간이 보여요. 세 공간을 다 본 뒤 확인 버튼으로 정해 주세요. 확인 버튼은 오른손 A 버튼이에요. / 공간 1 / 3"이 보이고, 참여자는 방아쇠로 세 공간(기본·자연·우주, 순서는 참여자 번호로 돌림 — 1번은 기본부터, 2번은 자연부터, 3번은 우주부터)을 넘겨 보다가 세 공간을 다 본 뒤 A(왼손 X)로 정합니다. 다 보기 전 확인은 받지 않습니다. 실험자 화면에는 지금 공간 이름·본 공간 수·순서가 보이고(공간 이름은 헤드셋 판에 쓰지 않음), 참여자가 말로 고르면 실험자가 그 공간이 보일 때 Enter로 정할 수 있습니다(`chosenBy experimenter`). 정하면 "정했어요."가 2초 보인 뒤 intro. 기록: manifest `environmentChoice`{mode, orderRule, order, environmentBeforeChoice, chosen, chosenBy, durationMs, switches, seenAll, ignoredConfirms, viewMs}, `config.environmentChoice`, 고른 공간이 `config.environment`·`environment.name`, events `space_choice_start/show/confirm_ignored/end`. ⚠ 분석기는 세션 사이 공간이 다르면 `config_mismatch:environment` 플래그를 붙입니다(이 변경에서 분석기는 고치지 않음).
   - 세션 중 헤드셋 연결이 끊기면(헤드셋을 벗어 잠듦·Link 끊김) 실험자 화면 맨 위에 빨간 큰 경고가 뜹니다 — 그동안 참여자가 Link 데스크톱 보기로 PC 화면을 볼 수 있습니다. 세션 시간은 멈추지 않습니다. F1로 실험자 화면을 숨기거나, 진행할 수 없으면 [중단…](또는 Esc)으로 중단합니다. 기록: `events.csv` `xr_lost`·`xr_regained`, manifest `xrConnection.lostCount`(CP17-1). [확인] 때 XR이 늦게 켜져 "XR 없음" 오류가 났으면 XR이 잡히는 대로 오류가 저절로 사라지고 [시작]이 눌립니다(CP17-4).
5. 단계: `intro → practice → baseline → pre_items → pre_wait → condition(90초) → post_items → check_items(자리 문항) → post_wait → stop_distance(반복 멈춤: 연습 1 + 본 1, 트리거 = 멈춤/다시 움직임, A·X = 확인(확정)) → done`. 실험자 키는 `unity/README.md` 「데스크톱 조작 키」, 참여자 컨트롤러는 「컨트롤러 조작」.
6. 끝나면 실험자 화면에 기록 폴더가 나옵니다. 기본 기록 루트는 `%USERPROFILE%\AppData\LocalLow\DefaultCompany\unity\IFS\sessions`(git 밖)입니다.

### 2.3 사후 면담 (PC)

헤드셋을 벗은 뒤 `http://127.0.0.1:8000/?view=postinterview&session=<세션ID>`를 열고 조건을 고릅니다. 대본·실험자 규칙은 `docs/post-interview-guide.md`. 녹음하지 않고 받아 적습니다. 기록은 `chatbot/logs/selection/<세션ID>/postinterview.json`.

서버를 이미 껐다면 같은 명령(`--config experiment`)으로 다시 띄우면 됩니다(그 세션 폴더에 `selection.json`이 있으면 열림). 끝나면 서버 창에서 Ctrl+C.

## 3. 분석

```powershell
cd <repo>\chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.placement --records "$env:USERPROFILE\AppData\LocalLow\DefaultCompany\unity\IFS\sessions" --out <결과 폴더(저장소 밖)> --selection-dir logs\selection
```

- 결과: `placement_sessions.csv`(세션 1행: 놓은 자리, 반복 멈춤 확정 거리 `stop_final_*`, 눈높이 기준 열 `eye_height_m`·`final_height_rel_eye_m` 등, 헤드셋 평정 `rating_<문항>_<pre|post|check>`, 사전 측정 `pre_*`, 사후 면담 `pi_*`), `stop_loop_rounds.csv`(라운드 1행), `stop_trials.csv`, `placement_summary.json`.
- 물체 크기·모양 공변량(G72, RQ2): `object_width_m`·`object_height_m`·`object_depth_m`(불러온 직후 물체 자기 축의 경계 상자, m — manifest `object.boundsM`)과 `proportions_x·y·z`(그리는 너비·높이·깊이 비율, 가장 큰 값 = 1)·`proportions_source`(said | edited | default)·`proportions_axis_said`(manifest `object.proportions`). 그런 기록이 하나도 없으면 열이 붙지 않습니다.
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

## 6. 생성 메시: [맞는 게 없어요] 뒤에만 (G73·G75)

`experiment.toml`은 `[gen3d] enabled = false`(생성 메시를 기본 후보로 두지 않음, G67-b)이고 `on_none = true`, `on_none_image_pick = true`(G75 — 아래 6.1)입니다. 아래 첫 항목들은 G73 흐름이고, G75를 켜면 그 가운데 생성 단계가 6.1처럼 '그림 고르기 → 고른 그림으로 형태'로 바뀝니다.

- 참여자가 후보 화면에서 처음 [맞는 게 없어요]를 누르면 서버가 확정 텍스트로 규칙 프롬프트를 만듭니다(`tools/gen3d/prompts.py`, 한→영 고정 사전, LLM 없음). 이 경로는 세션의 매퍼 spec을 함께 넘겨 매퍼 판단을 따릅니다(G73 후속): 매퍼가 형태에서 버린 낱말 — 움직임 비유의 매개어(「천이 펄럭이듯이 … 움직이는」의 '천'), 장소 용법(「안개 속에」), 직접 진술에 밀린 형상 낱말, 부정 — 은 프롬프트에 넣지 않고 `afterNone.prompt.dropped`에 사유(`mapper_action_simile` 등)와 함께 남깁니다(`promptRule: "mapper"`, builder `gen3d-shape-prompt/0.3.0+mapper-v2`). G62 기본 후보 경로와 오프라인 평가는 예전 규칙(0.2.0) 그대로입니다. 형태를 말하지 않았거나 사람·동물·안개처럼 메시로 만들지 않는 범주면 만들지 않고 "물체를 더 만들지 못했어요. 이어서 진행할게요."를 보인 뒤 예전처럼 조절로 갑니다.
- 만들 수 있으면 대기 화면(「말씀하신 내용으로 모양을 하나 더 만들고 있어요. …」)이 나오고, 서버가 Ollama의 면담·가드 모델을 내린 뒤 저장소 밖 `gen3d-venv`로 `tools/gen3d/generate.py --pipeline sdxl-triposg`를 돌립니다. 끝나면 만든 물체가 후보 맨 앞(점선 테두리)에 더해지고 다시 고릅니다. 이 후보도 아니라고 하면 같은 프롬프트·seed + 1로 한 번 더 만들고, 그다음 [맞는 게 없어요]는 예전 경로입니다. 끝나면 내렸던 모델을 다시 올립니다. 모델을 내리기 전에 생성기 `--cache-probe`(모델 호출 없음, 2초 안팎)로 같은 프롬프트·seed·모델의 자산이 이미 있는지 보고, 있으면 모델을 내리지 않습니다(`afterNone.llmUnload.skipped = "cache_hit_expected"`, `afterNone.cacheProbe`).
- 참여자는 [기다리지 않고 넘어갈게요]로 언제든 건너뛸 수 있습니다. 한도(`on_none_timeout_s`, 180초)를 넘거나 실패하면 생성을 끄고 예전 경로로 갑니다.
- 만든 후보를 고르면 GLB가 `logs/selection/<세션ID>/form-asset-*.glb`로 복사되고 `selection.json`(0.3)의 `form.asset`에 적혀 헤드셋 러너가 그 메시를 씁니다(G62 경로 그대로). 크기·색·재질은 매핑과 참여자 조절 값입니다.
- 기록: `selection.json`의 `generation.afterNone`(none 시각, 프롬프트와 낱말별 원문 위치, 모델 내림, 시작·끝·초, 결과와 사유, 모델·리비전·가중치 해시·seed, 골랐는지), `selection.afterNoneGeneration`. 생성기 입력·산출물·로그는 `gen3d-out/none-<세션ID>-…/`(저장소 밖).
- 미리보기가 글 요약(none)으로 내려간 세션에서는 만들지 않습니다(보일 수 없음). 같은 서버에서 다른 세션이 면담 중이면 GPU를 비울 수 없어 만들지 않습니다(`interview_active`).
- (CP13) 생성이 모델을 내린 때부터 다시 올리기가 끝날 때까지는 새 면담 세션 만들기·시작·답을 받지 않습니다(실험자 화면에 409와 「물체 생성 중이라 …」). 키워드 위기 문장은 막지 않습니다(모델 없이 고정 문구). 모델을 내리지 못하면 만들지 않습니다(`llm_unload_failed`). 다시 올리기에 실패하면 `/api/health`의 `gen3dOnNone.modelsReady`가 false가 되고, 가드 모델이 필수인 이 설정에서는 서버가 백그라운드로 다시 올려 돌아올 때까지 새 세션을 만들지 않습니다(「가드 모델이 준비되지 않았습니다 …」). 오래 이어지면 Ollama 상태를 확인합니다.

### 6.1 참고 그림을 먼저 고르기 (G75, `on_none_image_pick = true`)

- 처음 [맞는 게 없어요]를 누르면 서버가 같은 규칙 프롬프트에 무채색 화풍 고정 문구(흰 배경, 회색 점토 조형 하나 — `tools/gen3d/prompts.image_pick_prompt`)를 붙이고, 면담·가드 모델을 내린 뒤 생성기를 `--image-pick --seeds 0,1,2`로 돌려 SDXL 그림 3장을 그립니다. 그림마다 CLIP 사람·동물 관문을 거쳐 통과한 그림만 seed 순서로 보입니다. 끝나면 모델을 다시 올립니다(대기 화면: 「말씀하신 모양으로 그림을 그리고 있어요. …」, [기다리지 않고 넘어갈게요]는 그대로).
- 고르기 화면(단계 `picking`): 「말씀하신 모양으로 그림을 그려 봤어요. 떠올리신 모양과 가장 가까운 그림을 골라 주세요. 색은 보지 말고 모양만 봐 주세요.」와 그림마다 [이걸로 할게요], 아래에 [이 중에는 없어요]·[넘어갈게요]. 고르는 동안 면담·가드 모델은 올라가 있고, 고르는 시간에는 한도가 없습니다.
- 그림을 고르면 모델을 다시 내리고 `--from-image <그 그림> --image-sha256 … --seed <그 그림의 seed>`로 TripoSG만 돌립니다(대기 문구는 G73 그대로). 만든 물체가 후보 맨 앞에 더해지고, 그 뒤는 위 G73과 같습니다(골라야만 장면에 씀).
- [이 중에는 없어요] 또는 만든 물체에 다시 [맞는 게 없어요] → 새 seed 3개(3, 4, 5)로 2회차(`on_none_image_rounds = 2`). 그다음은 예전 경로(조절)입니다. 이 설정에서는 G73의 'seed + 1로 다시 만들기'를 쓰지 않습니다.
- 관문을 통과한 그림이 없으면(`all_images_gated`)·형태를 말하지 않았으면·실패·시간 초과면 「물체를 더 만들지 못했어요. 이어서 진행할게요.」 뒤 예전 경로입니다. 한도는 그림 단계 `on_none_image_timeout_s`(180초)·형태 단계 `on_none_mesh_timeout_s`(180초), 각각 모델 내리기를 포함합니다.
- 기록: 이 설정에서 [맞는 게 없어요]를 누른 세션의 `selection.json`은 `ifs-selection/0.4`(`shared/schemas/selection.v0.4.json`)입니다. `generation.afterNone.imagePick`에 회차마다 seed, 그림 sha256, 관문 결과, 보여 준 순서, 고른 자리(또는 none·skipped), 시각, 프롬프트·builder·화풍 판이 남고, 앞 회차는 `afterNoneEarlier`에 있습니다. 그림 고르기 화면에 노출된 세션은 `generation.imagePickExposed = true`입니다. 세션 로그 사건은 `selection:image_pick`(running·shown·picked·none)입니다. 그림 파일은 `gen3d-out/none-<세션ID>-…-r<회차>-img/images/`(저장소 밖)에 있습니다. 헤드셋 러너는 0.4를 0.3과 같은 규칙으로 읽습니다.
- 실측(합성 대사 2개, 이 PC): `docs/validation/run-g75-image-pick/README.md`.

### 6.2 확정 직후 LLM 빈칸 채우기 (G77, `[mapping] llm_fill = true` — experiment.toml에서만 켬, 다른 설정은 기본 끔)

- 참여자가 [이대로 맞아요]로 확정하면 매퍼 v2가 스펙을 만든 직후, 면담 모델(같은 Ollama 모델)을 한 번 더 부릅니다(온도 0, seed 0, JSON 스키마, 한도 `llm_fill_timeout_s` 20초). 매퍼가 비운 슬롯(색·밝기·투명도·질감·크기·움직임·형태 종류)과 그림용 형태 낱말만, 참여자 원문 인용이 있어야 받습니다. 위치·거리는 대상이 아닙니다. 프롬프트 `chatbot/prompts/llm_fill/llm_fill.v0.1.1.json`(draft).
- 검증기를 통과한 값만 후보·조절의 처음 값이 됩니다(확정 스펙 파일은 그대로). 조절 화면에는 그 항목 아래 「'<인용>'라고 하셔서 이렇게 해 봤어요. 다르면 고쳐 주세요.」가 보입니다(문구 `selection_protocol.v0.10.json` `llm_fill_note`, draft). 형태 낱말은 [맞는 게 없어요] 뒤 규칙이 형태를 못 만들 때만 그림 프롬프트에 들어갑니다. G83부터는 G82(6.4)가 켜져 이 형태 낱말 칸이 꺼지고, 그 일은 G82가 맡습니다.
- 부르지 않음·버림: 세션에 위기·확인 판정이 있었음, 실패·시간 초과·JSON 깨짐(지금 경로 그대로). 서버 시작 때 Ollama가 없으면 면담도 시작하지 않으므로 별도 점검은 없습니다.
- 기록: 이 설정의 `selection.json`은 처음부터 `ifs-selection/0.5`(`shared/schemas/selection.v0.5.json`)입니다. `llmFill`(모델 digest·프롬프트 판·원시 항목·항목별 기각 사유·채택 값·`applied`·참여자가 그대로 뒀는지 `participant`), `llmFillExposed`, 출처 값 `llm_quoted`. 세션 로그 사건은 `scene:llm_fill`. 헤드셋 러너는 0.5를 0.3 규칙으로 읽고 `llm_quoted`를 받습니다(헤드셋 빌드를 다시 만들어야 함). 실제 모델로는 아직 돌려 보지 않았습니다(2026-11-28 구현 때 GPU를 다른 실측이 쓰고 있었음) — 본 실험 전에 합성 대사로 돌려 `docs/validation/run-g77-llm-fill/`에 결과를 남겨야 합니다.

### 6.3 조절 화면의 색 고리 (G79, experiment.toml에서만: 값 표 `candidate_values.v4.json`, 프로토콜 0.11)
- 조절 화면의 색은 고리(72칸)·채도 단추 4개·무채색 견본 5개로 고릅니다. 색을 말한 참여자는 손잡이가 말한 자리에서 시작하고 Home 키나 눈금으로 돌아올 수 있습니다. 색을 말하지 않은 참여자는 손잡이가 없고 회색 견본이 속 빈 테두리로 보입니다.
- 기록은 `selection.json`의 `colorRing`에서 봅니다(`final.origin`: 말함 / 고름 / `unspecified` = 말하지도 고르지도 않음). 선택 파일 형식은 `ifs-selection/0.5` 그대로라 헤드셋 빌드를 다시 만들지 않습니다.
- 값 표나 프로토콜을 바꾼 뒤에는 챗봇 서버를 다시 띄워야 합니다. 고리 값 표에 고리 문구가 없는 프로토콜을 묶으면 서버가 시작할 때 설정 오류로 멈춥니다.
- 사람이 볼 것: 웹 화면의 색과 헤드셋에서 그려진 색의 차이, 채도 단계 차이가 헤드셋에서 보이는지.
- G83부터 프로토콜은 0.13입니다(0.11의 고리 문구는 그대로, 6.4의 문구만 더함).

### 6.4 LLM이 고른 형태 낱말로 그림 그리기 (G82, `[gen3d] on_none_llm_shape = true` — G83부터 experiment.toml에서 켬, 프로토콜 0.13)

연구 책임자가 2026-11-28에 켜기로 정했습니다(G83). 오프라인 평가 세 번은 미리 정한 기준에 미달이었습니다(`docs/decisions.md` G82). 참여자가 그림을 직접 고르거나 거절하는 구조이므로 참여자 기록으로 판단합니다. 이 판 앞뒤 세션은 생성 경로가 다르니 분석에서 층으로 나눕니다.

- **무엇이 켜졌나.** 처음 [맞는 게 없어요]를 누르면 서버가 먼저 규칙 그림 프롬프트를 만듭니다(6절). 그 프롬프트에 중심 형태 명사가 없을 때(`no_shape_stated`)만 면담 모델을 한 번 부릅니다. 모델은 확정 텍스트에서 형태 낱말 하나를 인용하고 영어 이름(소문자 한 낱말)을 냅니다. 같은 Ollama 모델·digest이고 온도 0, seed 0, JSON 스키마, 한도 20초입니다(`chatbot/ifs_chatbot/llm_shape.py`, 프롬프트 `llm_shape.v0.3.0`, draft). 검증기(G77 형태 낱말 검증 + 영어 금지 목록)를 통과한 것만 규칙 프롬프트의 빈 중심 명사 자리에 넣습니다. 프롬프트 문장·꾸밈말·부정 틀은 규칙이 붙입니다. 그 뒤는 6.1과 같습니다(그림 3장 → 고르기 → 메시).
- **부르지 않는 경우.** 규칙이 형태를 잡았을 때, 다른 사유로 막혔을 때(사람·동물·안개 등), 형태를 전혀 말하지 않았을 때('쑥색이고 차가워요'), 세션에 위기·확인 판정이 있었을 때입니다. LLM이 null을 내거나 검증기가 버리거나 실패·시간 초과가 나면 지금 경로(「물체를 더 만들지 못했어요. 이어서 진행할게요.」 뒤 조절)로 갑니다. 다시 부르지 않습니다.
- **G77과의 관계.** 이 플래그가 켜지면 G77(6.2)의 그림용 형태 낱말 칸(`shape_noun`)은 코드가 자동으로 끕니다. 다른 빈 슬롯 제안(색·질감 등)은 그대로입니다. 서버를 띄우면 경고 줄에 그 사실이 나옵니다.
- **참여자 화면.** LLM 이름으로 그린 회차의 그림 고르기 화면 맨 위에 「'<낱말>'이라고 하신 말을 바탕으로 모양을 만들어 볼게요.」 한 줄과 [그 말이 아니에요]가 있습니다(`selection_protocol.v0.13.json` `llm_shape_basis`·`llm_shape_basis_wrong_button`, draft). 낱말은 LLM 인용 구간 안의 명사 부분을 원문 글자 그대로 씁니다. 예를 들어 인용이 '판때기예요'면 '판때기'가 보입니다. 조사는 받침에 맞춰 '이라고'/'라고'를 붙입니다. 영어 이름은 보이지 않습니다. 단추는 그림마다 붙은 [이걸로 할게요]와 같은 크기입니다. [그 말이 아니에요]를 누르면 LLM을 다시 부르지 않고 조절 화면으로 가고, 맨 위에 「물체를 더 만들지 못했어요. 이어서 진행할게요.」가 나옵니다. [이 중에는 없어요]로 가는 2회차도 같은 낱말을 씁니다.
- **기록(`selection.json`, `ifs-selection/0.5`).** 칸은 `generation.shapeLlm`에 있습니다.
  - 경로: `route`(rule·llm·none), `routeReason`, `called`, `candidate`, `adopted`(인용·charSpan·영어), `rejectReasons`, `rawText`(원시 출력), 입력·검증 입력 해시, `model`(digest), `promptVersion`, `validatorRules`, `seed`
  - 화면 노출과 선택: `exposed`(그림이 나옴), `imageChosen`, `candidateExposed`(만든 물체가 후보에 나옴), `candidateChosen`(만든 물체가 나온 적이 없으면 null), `rejected`·`rejectedAt`
  - `basisShown`: LLM 인용(`llmQuote`·`llmCharSpan`), 화면 낱말(`shownText`·`shownSpan`), 조사, 보인 문장
  - `generation.afterNone`의 칸: `shapeLlmUsed`, `shapeLlmItems`, `shapeLlmBasisShown`, `basisRejected`. 메시가 관문에서 막혔으면 `gate`(personLikeScore·labelScores 등)
  - 세션 로그 사건은 `selection:shape_llm`입니다. 원시 출력은 참여자 말에서 온 것이라 git 밖 로그에만 있습니다.
- **알려진 한계.**
  - 채움은 약 50%입니다. 사전 밖 형태 낱말에서 뜻이 맞는 이름을 낸 비율이 2차 24/48, 3차 25/50이었습니다. 나머지는 LLM null, 목록 밖 이름, 가정 표지로 막힘 등입니다.
  - 목록 밖 동물은 LLM 단계를 지납니다(3차 '도롱뇽' → newt 2건). 그 뒤의 그림 관문과 메시 관문(CLIP 사람·동물)에 기댑니다.
  - '돌덩이'는 되지 않습니다. 「돌덩이예요.」와 「돌덩이 같은 게 있어요.」 모두 LLM이 null을 냅니다(실제 흐름 점검 `docs/validation/run-g82-end-to-end/`).
  - 그림은 통과해도 메시가 관문에서 막힐 수 있습니다(주전자 `person_like` 0.793). 이때 참여자는 그림을 고른 뒤 40초쯤 기다렸다가 조절 화면으로 갑니다.
- 실측: `docs/validation/run-g82-end-to-end/`(G82 첫 점검, 시험 설정), `docs/validation/run-g83-g82-on/`(G83 고친 뒤, experiment.toml 사본).

## 7. 아직 사람이 정할 것 (이 문서가 켜지 않은 것)

- 조건·멈춤 거리 단계에서 안내 판 숨기기(G63 (7)): 꺼 둠.
- 면담 모델: `gemma4:e4b`(G64 검증에 쓴 모델). `pilot.toml`의 `gemma4:31b`는 16 GB GPU에 올라가지 않습니다.
- 주 척도 A1–A7은 컴퓨터 사전 측정과 헤드셋 `pre_items`(scaleA) 양쪽에서 묻습니다. 코드는 그대로 두고, 주 분석의 사전 점수는 헤드셋 쪽으로 정했습니다(G67, 3절).
