# 데스크톱 1–6단계 흐름: 후보 생성(D3) · 후보·조절 화면과 API(D5) · 기록(D9 데스크톱 쪽) · 사전 측정

> **합성 데이터입니다.** 모든 대사와 응답은 AI가 쓴 합성 문장이고, 실제 참여자 자료가 아닙니다(AGENTS.md 6).
> **문구는 모두 초안입니다.** 후보·조절·사전 측정 화면 문구 29개가 `status: draft`(IRB·연구팀 검토 전)입니다.

작업일 2026-11-23, 브랜치 `claude/prototype-v4-build`. 근거는 `docs/prompts/prototype-v4-build.md` 1절(흐름 표)·4절(D3·D5·D9)·6절(임시값)이고, 설계는 `docs/decisions.md` G14–G24를 따랐습니다. 미리보기는 메인 세션 판정 G25(WebGL을 쓸 수 없어 image 모드)를 따랐습니다.

## 1. 흐름

| 단계 | 하는 일 | 코드 |
| --- | --- | --- |
| 1 면담 · 2 확정 | 지금 챗봇 그대로 | `controller.py` |
| 3 규칙 추출 | 확정 텍스트 → SceneSpec. 새 흐름 설정(`config/v4.toml`)은 **매퍼 v2**를 씁니다. 기본 설정은 그대로 v1입니다 | `scene_builder_v2.py` |
| 4 후보 선택 | 규칙이 만든 후보(최대 4개)를 미리보기와 함께 보여 주고, 하나를 고르거나 "맞는 것이 없다" | `candidates.py`, `selection.py`, `web/stage.js` |
| 5 조절 | 정해 둔 일곱 항목(형태·색·밝기·투명도·크기·질감·움직임)을 표의 값으로만 고침. 위치·거리 항목은 없음 | `selection.py`, `web/stage.js` |
| 6 사전 측정 | 지시문, 주 척도안 A 7문항, G13 두 문항(모습 일치·대표성), 1–7 | `selection.py`, `shared/protocol/selection_protocol.v0.json` |

후보 단계는 면담 밖입니다. 4–6단계는 LLM도, 면담 검증기(V1–V9)도 부르지 않습니다. 테스트 `test_no_llm_or_validator_calls_in_stages`가 이를 확인합니다.

## 2. 후보 규칙(`chatbot/ifs_chatbot/candidates.py`, 값 표 `shared/lexicon/candidate_values.v0.json`)

- **입력**은 SceneSpec(dict)과 sessionId입니다. **출력**은 `{generatorVersion, tableVersion, tableSha256, specSha256(정규화), sessionId, axes, candidates, displayOrder, orderRule, splitSkipped, note}`입니다.
- 후보 하나는 "원본 spec + 덮어쓰기"입니다. 덮어쓰기는 Unity `SceneOverrideJson`이 받는 **평평한 객체**입니다(예: `{"form.type": "mist", "layout.size": 0.7}`). 색은 `material.color.h/s/l` 세 키로 나뉩니다(`SceneParams.NumericKeys`). 원본 spec과 `_provenance`는 바꾸지 않습니다(G14·G15).
- **빈 자리**는 값이 null인 슬롯입니다. 형태 자리는 모양어(`_unmapped` category shape)가 있어도 비지 않은 것으로 봅니다(아래 6절).
- **2×2**(G16)는 우선순위 형태 > 크기 > 투명도 > 밝기 > 질감 > 움직임에서 위 두 빈 차원으로 만듭니다. 각 차원의 두 값은 `pair`이고, `pair[0]`은 기본값입니다. 그래서 격자 0번(`a0·b0`)이 언제나 "후보 단계가 없었다면 그려졌을 형상"(덮어쓰기 없음)이 됩니다.
- **빈 차원이 하나뿐**이면 그 차원의 `levels`(최대 4개)를 씁니다. **빈 자리가 없으면** 후보는 1개입니다. 이때 화면은 "이 형상으로 진행 / 맞는 것이 없다"를 보여 줍니다(G19).
- **색상(hue)**은 후보에서 벌리지 않습니다(G17).
- **낱말 해석 갈림**(G18)은 닫힌 표에 등록된 것만 씁니다. spec당 한 축만 쓰고, 빈 차원보다 먼저 씁니다.
- **화면 순서**는 `sha256(sessionId)[:8] mod n`만큼 순환시킵니다(G20). 후보 id는 `"c-" + sha256(generatorVersion | 정규화 spec 해시 | index)[:12]`입니다.
- LLM·난수·시각을 쓰지 않습니다. 결정성은 두 가지로 나눠 테스트로 고정했습니다(G28).
  - **(a) 같은 확정 텍스트 → 같은 spec·같은 후보.** 정규화 spec 해시, 후보 id, 덮어쓰기, 축 값이 같습니다. 세션 ID가 달라도 성립합니다(`test_g28a_…`, `test_g28_determinism_has_two_meanings_through_the_flow`).
  - **(b) 같은 spec + 같은 세션 ID → 같은 표시 순서.** 표시 순서는 세션 ID 해시로 순환하므로(G20) 세션 ID가 다르면 달라질 수 있습니다(`test_g28b_…`). 출력 파일 전체 바이트에는 sessionId와 표시 순서가 들어 있어서, 세션 ID를 고정했을 때만 같습니다. 확정 텍스트 3개의 출력 sha256은 세션 ID `SYN-GOLD`로 고정했습니다.

### 값 표(v0.1.0, 잠정값)

| 차원 | 슬롯 | levels(0번 = 기본값) | 2×2 pair |
| --- | --- | --- | --- |
| 형태 | form.type | blob, mist, shell, fragments | blob, mist |
| 크기 | layout.size | 0.5, 0.3, 0.7, 0.8 | 0.5, 0.7 |
| 투명도 | material.opacity | 1.0, 0.8, 0.6, 0.4 | 1.0, 0.4 |
| 밝기 | material.brightness | 0.5, 0.25, 0.75, 1.0 | 0.5, 0.75 |
| 질감 | material.roughness | 0.5, 0.1, 0.9 | 0.5, 0.1 |
| 움직임 | motion.type | still, floating, trembling, swaying | still, floating |

후보 값은 모두 조절 단계의 값 목록 위에 있습니다. 그래서 고른 후보에서 조절을 한 칸씩 이어 갈 수 있습니다(테스트로 고정). 기본값은 Unity `SceneParams.cs`의 `SceneDefaults`에서 옮겨 적었습니다. 파이썬 테스트가 그 C# 원문을 읽어 값을 대조합니다.

**표에 없는 말한 값.** 참여자가 말한 범주형 값(예: 움직임 `scattering`)이 조절 표의 목록에 없으면, 그 값을 이 세션의 목록 끝에 하나 더해 현재 값으로 보여 줍니다. 그래서 다른 값을 골랐다가 말한 값으로 돌아올 수도 있습니다. 더하는 것은 말한 값 하나뿐이고, 말하지 않은 표 밖 값은 계속 거부합니다. 더한 사실은 `selection.json`의 `adjustValueExtras`와 세션 로그 `selection:candidates`에 남습니다. 형태 등 다른 범주형 항목에도 같은 규칙을 씁니다(지금 형태 표에는 스키마의 네 값이 모두 있어 실제로는 움직임에서만 생깁니다).

**조절 값.** 형태는 form.type 네 값입니다. 색은 견본 17개(무채색 l 0.1/0.3/0.5/0.7/0.9, 유채색 색상 12칸 × s 0.6 × l 0.5)입니다. 밝기는 0–1을 0.125 간격으로, 투명도는 0.2–1.0을 0.2 간격으로, 크기는 0.2–0.8을 0.1 간격으로 나눴습니다. 질감은 0.1–0.9를 0.2 간격으로 나눴습니다. 움직임은 still·floating·swaying·trembling·pounding·sinking입니다. 값에는 이름을 붙이지 않습니다. 화면에는 형태 1–4, 색 견본, 단계 n/N으로만 보입니다.

**갈림 표**에는 `구름 → form.type {blob, mist}` 하나만 넣었습니다. 근거는 렌더 시트 M03입니다('구름이에요'가 기본 blob으로 그려짐). 껍질·막과 빛은 넣지 않았고, 넣지 않은 이유는 표 파일 `notIncluded`에 적었습니다.

## 3. 기록(D9 데스크톱 쪽, git 밖 `<log_dir>/selection/<sessionId>/`)

- `candidates.json`: 생성기 출력 그대로입니다.
- `selection.json`(`ifs-selection/0.1`, 스키마 `shared/schemas/selection.v0.1.json`)에는 다음을 적습니다.
  - **헤드셋 러너 계약 필드**(`PlacementSelection.cs`): `formatVersion`, `specSha256`(저장된 spec **파일 바이트**의 sha256), `finalOverrides`(평평한 객체, 위치·거리 키 없음), `selection{selectedCandidateId, none}`, `sources`(슬롯 → said / chosen / edited / default. 러너도 슬롯 이름과 값을 검사합니다, G27).
  - **러너에 넘길 수 있는지**(G26): `runnerReady`와 `runnerBlockers`(이유). `specSha256`에는 저장된 spec 파일 바이트의 해시만 적습니다. spec 파일이 없는 실행(`persist_logs = false` 등)이나 파일이 세션의 spec과 달라진 경우에는 `specSha256 = null`, `spec.sha256Basis = "none"`, `runnerReady = false`입니다. 조절을 마치기 전에도 `runnerReady = false`(이유: 조절을 마치지 않음)입니다. `/final` 응답 맨 위에도 `runnerReady`·`runnerBlockers`·`specPath`·`selectionPath`가 있습니다. 러너는 `spec.sha256Basis`가 `file`이 아니거나 `runnerReady = false`면 이유를 밝히고 시작을 거부합니다.
  - **줄바꿈**: spec 파일은 `dumps(spec)`의 UTF-8 바이트 그대로(LF) 씁니다. 전에는 Windows에서 `write_text`가 CRLF로 바꿔 써서, 같은 spec이 OS나 체크아웃 설정에 따라 다른 해시가 될 수 있었습니다. `runs/`는 `.gitattributes`로 LF를 고정했고, Unity 테스트(`PlacementSelectionTests.Chatbot_selection_files_match_their_saved_spec_files_byte_for_byte`)가 두 파일을 바이트로 대조합니다.
  - 챗봇이 더 적는 것:
    - 보여 준 후보 전체(`candidates`)와 표시 순서(`candidatesShown`)
    - `selection`의 `selectedIndex`·`displayPosition`·`operationalId`·`operationalIndex`
    - 조절 이력(`adjustments.events`, 항목별 횟수·처음 값·마지막 값·시각)
    - `sourceDetails`(슬롯별 값, 말한 값, 고른 값, 기본값)와 `sourceCounts`
    - 정규화 spec 해시, 초안 문구 수와 키(`protocol.draftCount`·`draftKeys`), 미리보기 모드
- `premeasure.json`(`ifs-premeasure/0.1`): 문항별 응답(1–7 또는 null = 답하지 않음), `selectionNone`(G23의 "고르지 않음" 표시), 초안 문구 수.
- 세션 로그(`elicit-log/0.1`)는 형식을 바꾸지 않았습니다. 기존 `events`에 `selection:candidates`·`selection:selected`·`selection:adjusted`·`selection:premeasure` 요약만 더합니다. 미리보기가 none으로 바뀌면 `alerts`에 `preview_fallback`을 남깁니다.
- 참여자가 응답을 폐기하면 이 폴더도 지웁니다.

**출처 계산.** 조절에서 만진 항목의 마지막 값이 처음 값과 다르면 `edited`입니다. 만졌다가 처음 값으로 되돌리면 원래 출처가 그대로 남고, 횟수는 조절 이력에 남습니다. 고른 후보의 축 슬롯은 `chosen`입니다("맞는 것이 없다"면 `chosen`이 없음). 값이 있던 슬롯은 `said`이고, 나머지는 `default`입니다. 말한 값을 고치면 `edited`가 되고, `sourceDetails.saidValue`에 원래 말한 값이 남습니다. 색 견본은 h·s·l을 함께 바꾸므로 `material.saturation`도 `edited`가 됩니다.

## 4. API(`chatbot/ifs_chatbot/server.py`, `[selection] enabled = true`일 때만 열림. 아니면 409)

| 메서드·경로 | 내용 |
| --- | --- |
| `GET /api/selection/config` | 화면 문구(초안 표시 포함), 조절 항목과 값 목록, 미리보기 모드 |
| `GET /api/sessions/{sid}/selection` | 지금 단계와 후보·조절 상태 |
| `POST /api/sessions/{sid}/candidates` | 확정이 끝난 세션에서 후보를 만들고 기록함. 다시 부르면 같은 후보를 돌려줌 |
| `POST /api/sessions/{sid}/selection` `{candidateId}` | 후보 id 또는 `"none"`. none이면 기준 후보 0번으로 진행 |
| `POST /api/sessions/{sid}/adjust` `{item, value}` | 조절 한 번. 항목·값이 표 밖이면 422, 순서가 틀리면 409 |
| `POST /api/sessions/{sid}/adjust/finish` | 조절을 끝내고 `finalOverrides`·`sources`를 확정함 |
| `GET /api/sessions/{sid}/final` | 헤드셋 러너용: 원본 spec(바꾸지 않음)과 selection.json. 맨 위 `runnerReady`·`runnerBlockers`·`specPath`·`selectionPath`. 러너에는 이 응답의 spec이 아니라 `specPath`의 파일을 넘깁니다 |
| `GET·POST /api/sessions/{sid}/premeasure` | 문항 조회와 응답 제출(`{responses: {id: 1–7 또는 null}}`) |
| `GET /api/sessions/{sid}/preview/{후보 id 또는 current}.png` | image 모드의 미리보기 PNG. 플레이어가 실패하면 503을 내고 none으로 바뀜 |

기존 엔드포인트와 기본 설정의 화면 응답은 바꾸지 않았습니다. `/api/health`에는 `selection`·`preview` 키만 더했습니다. 새 흐름 설정에서만 세션 응답에 `selection{available, stage}`가 붙습니다.

## 5. 미리보기 어댑터(`chatbot/ifs_chatbot/preview.py`, `[preview] mode`)

- **image**(새 흐름 기본값, G25): Unity Windows 미리보기 플레이어(`PreviewQueue`)를 띄워 두고, 폴더로 spec JSON과 덮어쓰기를 보내 PNG를 받습니다. 플레이어 경로는 설정값입니다(`image_player`, 저장소 밖 `../../webgl-build/preview-win/IFSPreview.exe`). 첫 요청 때 띄우며, `start_on_launch = true`로 두면 서버 시작 때 띄웁니다.
  - 플레이어가 없거나, 뜨지 않거나, 요청 중에 죽거나, 오류를 돌려주면 none으로 자동 대체합니다. 대체 사실은 `/selection`·`/health`의 `preview.reason`, 세션 로그의 `preview_fallback`, 화면 경고 줄로 알립니다.
  - **이 PC에서 이미 빌드된 플레이어로 실제 연결을 확인했습니다.** 320×240에서 시작 0.71초(첫 장 461 ms), 이후 한 장 12–16 ms였습니다. 시나리오의 `candidate_*.png`·`final.png`와 `screens/image_*.png`가 그 결과입니다.
  - 테스트는 가짜 플레이어(`chatbot/tests/fixtures/fake_preview_player.py`)로 연결·정리·실패 대체(요청 중 종료, 준비 안 됨, 오류 응답)를 확인합니다.
- **webgl**: 인터페이스만 있습니다. 같은 출처의 `/preview/webgl/`(설정값 `webgl_dir`)를 iframe으로 띄우고 `window.ifsPreview.load(spec)`·`applyOverrides(obj)`·`capture()`를 부릅니다. 빌드가 없으면 none으로 대체합니다. **실행해 보지 못했습니다.**
- **none**: 후보의 속성 요약 글(`키 = 값`, 덮어쓴 키에 `*`)만 보여 줍니다(테스트·시나리오용).
- 외부 CDN·글꼴·스크립트는 쓰지 않습니다. 테스트가 웹 파일에 `http(s)://`가 없는지 확인합니다.

## 6. 합성 시나리오 결과(`runs/`, image 모드 · 실제 Unity 플레이어)

시나리오 파일은 `chatbot/scenarios/selection/*.json`입니다. 모두 정적 조건 1이라 면담에서도 LLM을 부르지 않습니다(면담 LLM 턴 0).

| 시나리오 | 확정 텍스트 | 후보 | 축(이유) | 선택 | 조절 | 출처 said/chosen/edited/default |
| --- | --- | --- | --- | --- | --- | --- |
| S1 형태를 말함 | 가슴 앞에 연기 같은 게 있어요. 작아요. | 4 | 투명도·밝기(빈 자리) | 2번(화면 3번째) | 색·크기·밝기 각 1 | 3/1/4/7 |
| S2 느낌만 | 가슴 안쪽이 답답하고 무거운 느낌이에요. | 4 | 형태·크기(빈 자리) | 3번(화면 1번째) | 없음 | 2/2/0/11 |
| S3 모두 말함 | 까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 안 움직여요. 불투명해요. 어두워요. | 1 | 없음 | 0번(진행) | 움직임 2회(되돌림) | 8/0/0/7 |
| S4 맞는 것이 없다 | 배 안쪽에 구름이 있어요. 하얀색이에요. | 4 | 형태(낱말 갈림 '구름')·크기 | none → 0번 | 형태·크기·투명도 각 1 | 3/0/3/9 |
| S5 빈 자리 하나 | (S3에서 '어두워요'를 뺌) | 4 | 밝기(빈 자리) | 1번(화면 3번째) | 없음 | 7/1/0/7 |

시나리오 폴더마다 `confirmed_text.txt`, `spec.json`(바이트 그대로이며 sha256 = selection.json `specSha256`), `candidates.json`, `selection.json`, `premeasure.json`, `candidate_<n>.png`, `final.png`가 있습니다. `selection.json`·`premeasure.json`의 시각은 실행할 때마다 다르고 나머지는 같습니다. 로컬 경로는 `<log_dir>`로 바꿔 적었습니다. 다섯 시나리오 모두 `runnerReady: true`입니다.

**2026-11-23 다시 돌림(CP9 반영 뒤).** 구름 수정(D7) 뒤에 다시 빌드한 미리보기 플레이어(04:12 빌드)로 찍었습니다. 앞의 그림은 D7 전 플레이어로 찍은 것이었습니다. PNG 말고 달라진 것은 다음과 같습니다.
- `specSha256`: spec 파일을 LF로 쓰게 되어(위 3절 "줄바꿈") 다섯 개 모두 값이 바뀌었습니다. spec 내용은 같습니다.
- `selection.json`에 `runnerReady`·`runnerBlockers`·`adjustValueExtras`가 더해졌습니다(다섯 시나리오에는 표에 없는 말한 값이 없어 `{}`).
- 후보, 축, 선택, 조절, 출처 분포, `finalOverrides`, 사전 측정 응답은 같습니다(시각만 다름).
- 그림이 바뀐 것은 mist가 들어간 장면뿐입니다(S1 전부, S2 후보 2·3과 최종, S4 후보 2·3과 최종). 덩어리 공(blob)만 있는 장면은 바이트까지 같습니다.

**그림을 보고 확인한 것(⚠).**
- **S5**: 거의 검은 색(l 0.06)에서는 밝기 후보 4개가 화면에서 거의 구별되지 않습니다. 규칙은 "같은 넷"을 피했지만 렌더에서는 같아 보입니다. G22의 "반영되지 않는 조합" 표(`adjustItems.availability`, 지금 비어 있음)와 후보 차원 쪽 같은 점검이 필요합니다.
- **S1·S4**: D7 뒤 mist 후보는 둥근 덩어리가 겹친 구름 모양으로 보이고, 전보다 배경과 잘 구분됩니다. S1은 크기를 작게 말해서 여전히 작습니다.
- **S2**: 형태(blob/mist) × 크기 차이는 잘 보입니다.

### 챗봇 → 배치 러너 끝에서 끝까지(2026-11-23, CP9 반영 뒤)

합성 시나리오 S1으로 챗봇이 만든 `spec.json`과 `selection.json`(`runnerReady: true`)을 그대로 배치 러너 자동 시행(place 조건, 참여자 21)에 넣었습니다. 기록은 저장소 밖 임시 폴더에 두었습니다.
- 끝까지 돌았습니다(`summary.json` `completed: true`, `recordVersion` `ifs-placement/0.2`, `inputSource: auto`).
- manifest `specSha256`이 selection.json의 `specSha256`과 같았습니다. 줄바꿈 변환 없이 바이트가 맞았다는 뜻입니다.
- manifest `selection`에 `none: false`, 고른 후보 id, `finalOverrides` 6키, `sources` 15슬롯이 남았습니다. `appliedOverrides`는 6키 모두 그려진 값과 같았습니다. `events.csv`에는 `selection` 한 줄(`applied=6`)이 있었습니다. manifest에 로컬 경로는 없었습니다.
- 분석기(`python -m ifs_chatbot.eval.placement`)가 이 기록을 읽었습니다: `selection_none 0`, 후보 id, `n_final_overrides 6`, 플래그 `runner_warning:1`(초안 문구 경고).

## 7. 화면 캡처(`screens/`, 헤드리스 Edge)

| 파일 | 내용 |
| --- | --- |
| `none_0_after_confirm.png` | 확정 직후 [다음 단계로] |
| `none_1_candidates_2x2.png` · `image_1_candidates_2x2.png` | 후보 4개 + "맞는 것이 없다"(none은 글 요약, image는 실제 Unity 렌더) |
| `none_1b_single_candidate.png` · `image_1b_single_candidate.png` | 빈 자리가 없어 후보 1개 |
| `none_2_adjust.png` · `image_2_adjust.png` | 조절 화면(항목 패널 + 미리보기) |
| `none_3_premeasure.png` | 사전 측정(지시문, 9문항, 1–7, 답하지 않기) |
| `none_4_done.png` | 끝 |

모든 화면 맨 위에 "초안 문구 사용 중" 경고 줄이 있습니다(X35 방식).

## 8. 재현

```powershell
cd chatbot
.venv\Scripts\python.exe -m pytest -q tests\test_candidates.py tests\test_selection_flow.py
.venv\Scripts\python.exe -m ifs_chatbot.selection_sim --out <폴더>                                    # none 모드
.venv\Scripts\python.exe -m ifs_chatbot.selection_sim --preview image --player <IFSPreview.exe> --out ..\docs\validation\selection-flow\runs
.venv\Scripts\python.exe ..\docs\validation\selection-flow\capture_screens.py ..\docs\validation\selection-flow\screens none
.venv\Scripts\python.exe -m ifs_chatbot.server --config v4 --backend offline --condition static   # 직접 해 보기(http://127.0.0.1:8000)
```

## 9. 이 구현에서 정한 것(결정 문서에 없던 것)

- 2×2의 0번이 기준 후보가 되도록 각 차원의 `pair[0]`을 기본값으로 두었습니다. 그래서 2단계의 다른 한 값은 방향을 하나 골라야 했습니다(크기 0.7, 투명도 0.4, 밝기 0.75, 질감 0.1, 움직임 floating). D5_claude 안의 값을 조절 단계 위로 옮겼고, 밝기 값은 근거 없이 정한 잠정값입니다.
- 모양어를 말했으면 형태 자리를 비지 않은 것으로 봅니다.
- 갈림 축은 대상 슬롯이 비어 있을 때만 씁니다. 말한 슬롯을 덮지 않으므로 G9를 예외 없이 지킵니다.
- `edited`는 "만짐"이 아니라 "처음 값과 다른 마지막 값"으로 정했습니다.
- 사전 측정에서는 문항마다 "답하지 않기"(null)를 허용했습니다. G13 두 문항에는 A 척도의 7점 기준점을 썼습니다.
- 움직임 조절 값 6개를 골랐습니다. 회전·다가옴·퍼짐은 뺐습니다.
- 정규화 spec 해시는 sessionId·participantId·condition을 빼고 계산합니다.

## 10. 하지 않은 것 · 확인하지 못한 것

- WebGL 모드는 실행하지 않았습니다(빌드 없음).
- Unity 쪽 교차 테스트를 하지 않았습니다. 후보 덮어쓰기를 `SceneOverride.Validate`·`FormRenderPlan`에 넣는 테스트와, 조절 항목 × 형태별 반영 여부 표(G22)가 남아 있습니다.
- `form.base`(G21)는 스키마에 없어 형태 값은 `form.type` 네 개뿐입니다.
- `docs/chatbot-design.md`에 후보 단계의 유도 위험을 적는 일은 이번 범위(chatbot/·shared 새 파일·이 폴더) 밖이라 하지 않았습니다.
