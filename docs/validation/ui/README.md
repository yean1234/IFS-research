# 화면 사용성 개선 (G44) — 챗봇 웹 화면 · Unity 배치 실험 화면

> G57(2026-11-24): 참여자 문구를 다듬었습니다(`docs/decisions.md` G57). 이 문서의 단추 이름·문구 인용과 화면 캡처는 그 전 글입니다. 지금 글은 `shared/protocol/selection_protocol.v0.json`(0.4.0)·`elicitation_protocol.v1.2.json`과 웹 화면 코드에 있습니다(예: [다음 단계로] → [다음으로], [맞는 것이 없다] → [맞는 게 없어요], [제출] → [다 답했어요], [응답 폐기] → [내 답 지우기], [답하지 않기] → [답하지 않을게요]).

작성 2026-11-23, 브랜치 `claude/prototype-v4-build`. 방침은 `docs/decisions.md` G44(·G43), 정한 세부는 같은 파일 맨 끝 「G44 구현 세부」. 기준은 `ui-ux-pro-max` 스킬의 Quick Reference(§1 접근성, §2 상호작용, §5 배치, §6 글자·색, §8 폼·피드백)이고, 아래 괄호 안 영어 낱말이 그 규칙 이름입니다. 스킬이 권하는 외부 글꼴·CDN·아이콘 묶음은 쓰지 않았습니다(원칙 5). 체크 표시는 CSS로 그렸습니다(외부 그림·SVG 주소 없음).

**바꾸지 않은 것**: `shared/protocol/`의 고정 문구 글자(파일을 열지 않음), 문항 순서, 평정 방식(1–7·0–10 점 수, 앵커, 답하지 않기), 단계 순서, 후보 표시 순서(G20), `selection.json`·`premeasure.json`·세션 로그 형식과 내용, 면담 검증기·위기 판정·LLM 경로, 매퍼·후보 규칙·사전, Unity의 측정·기록·타이밍 로직. 새 참여자용 문구는 없습니다.

## 1. 챗봇 웹 화면 (`chatbot/ifs_chatbot/web/`)

전후 캡처는 `before/`·`after/`의 `web_<미리보기 방식>_<보기>_<창 폭>_<화면>.webp`(헤드리스 Chrome, 합성 세션, 70–85 % 축소). "전"의 참여자 보기는 이전 화면에서 [연구자 화면] 체크를 푼 모양입니다.

| 화면 | 바꾼 것 | 규칙 | 전 → 후 |
| --- | --- | --- | --- |
| 공통 | **참여자 보기 / 연구자 보기**를 나눔. 참여자 보기는 가운데 한 단(최대 880 px), 연구자 패널·머리글 제목과 영문 부제·조건·모델 배지·체크·문구 출처 꼬리표·미리보기 대체 사유 줄·[새 세션]을 숨김. 기본은 연구자 보기(4절) | `visual-hierarchy`, `content-priority` | `webgl_researcher_1440_*` ↔ `webgl_participant_1440_*` |
| 공통 | **진행 표시** "n / N" + 칸 막대(지난 칸 채움, 지금 칸 속 빈 테두리, 남은 칸 회색 — 색만이 아니라 모양으로도). 단계 이름 글은 없음 | `progress-indicators`, `color-not-only` | 모든 `after/` 머리글 |
| 공통 | 색·간격·크기를 CSS 토큰으로(`--ink`·`--line-strong`·`--focus`·`--target 44px`·`--fs-body 16px`·`--space-*` …). 본문 16 px·줄 간격 1.6, 보조 글 14 px 이상. 대비 미달 색 둘을 고침(경고 글 #9a6a12 → #7a520a, 배지 글 청록 → 짙은 청록) | `color-contrast`, `readable-font-size`, `line-height`, `design-tokens` | 아래 2절 수치 |
| 공통 | 보이는 초점 테두리(3 px, 흰 바탕 8.0:1), 모든 누를 자리 높이 44 px 이상, 단추 눌림·대기 표시(0.2초 넘게 걸릴 때만 도는 표시), 기다리는 동안 다시 눌러도 다시 보내지 않음(기존 `busy`) | `focus-states`, `touch-target-size`, `loading-buttons`, `press-feedback` | `after/web_kb_webgl_*` |
| 공통 | `prefers-reduced-motion`이면 반짝임·도는 표시·전환을 멈춤(미리보기 형상의 움직임은 조절 대상이라 그대로). 768·1024·1440 폭에서 가로 스크롤 없음 | `reduced-motion`, `horizontal-scroll`, `breakpoint-consistency` | 2절 |
| 면담 | 입력칸에 이름(기존 자리표시 글 "떠오르는 대로 적어 주세요.")을 달고 "Enter 보내기 · Shift+Enter 줄바꿈"(기존 글)을 칸 아래로 뺌. 보내는 중 단추 대기 표시·상태 줄 낭독. 대화 칸 높이를 창에 맞춤. [그만]·[응답 폐기]는 다른 단추와 떨어뜨려 줄 오른쪽 끝 | `input-labels`, `input-helper-text`, `destructive-emphasis`, `touch-spacing` | `web_webgl_participant_1440_interview` |
| 면담 | **위기 고정 문구**: 대화 폭 전체·두꺼운 빨강 왼쪽 띠·굵게, 처음 나올 때 한 번 그 문구로 초점을 옮겨 화면에 보이게 하고 낭독기가 읽게 함, 대화 칸 높이 제한을 풀어 잘리지 않게. 문구·판정·LLM 경로는 그대로 | `error-placement`, `aria-live-errors` | `web_webgl_participant_1440_crisis` |
| 후보 | [맞는 것이 없다]를 후보 단추와 **같은 모양·크기**(테두리 청록 2 px, 높이 48 px)로, 후보 칸 아래 구분선 밑 가운데 **떨어진 자리**에. 후보 그림은 오기 전에도 4:3 자리를 차지(화면 안 밀림, 반짝이는 회색 칸). 고르면 그 칸을 표시하고 나머지를 흐리게, 단추에 대기 표시 | `primary-action`, `content-jumping`, `loading-states`, `state-clarity` | `web_webgl_participant_1440_candidates` |
| 조절 | 미리보기를 크게(왼쪽 반), 스크롤해도 따라옴(sticky). 항목은 한 열(이름 4.5 em + 조작) | `visual-hierarchy`, `fixed-element-offset` | `web_webgl_participant_1440_adjust` |
| 조절 | 단계 항목: "5 / 9" 글 대신 **칸 눈금 막대**(지나온 칸 옅은 청록, 지금 칸 진한 청록이고 더 높음) + 44 px −/+. 끝에서는 그쪽 단추를 끄고 점선·흐리게. 낭독기에는 `meter`(n / N) | `state-clarity`, `disabled-states`, `color-not-only` | 같은 캡처 |
| 조절 | **색 견본**: 44 px, 고른 것은 흰 틈 + 짙은 테두리 두 겹 + 오른쪽 위 체크(색만으로 구별하지 않음). 낭독기 이름 "색 1"–"색 17"(색 이름은 만들지 않음) | `color-not-only`, `aria-labels` | 같은 캡처 |
| 조절 | **형태 버튼**: 번호 대신 **Unity가 그린 견본 그림**(지금 상태에서 형태만 바꾼 정지 그림, 64×48, 가운데 1.6배). WebGL은 기존 큐로 캡처, image는 서버 예비 플레이어(새 읽기 전용 API). 글 요약(none)은 번호 그대로 | G44 지시 | `web_webgl_*_adjust`, `web_image_*_adjust`, `web_none_*_adjust` |
| 조절 | **움직임 버튼**: 번호를 두고, 초점이 가거나 마우스가 0.35초 머물면 본 미리보기에서 그 움직임을 재생, 떠나면 되돌림(WebGL만, reduced-motion이면 끔). 보는 중에는 미리보기·단추에 점선 테두리 | G44 지시, `hover-vs-tap` | — (움직임이라 정지 캡처 없음) |
| 조절 | 색·형태·움직임 묶음은 Tab 한 번에 들어가 방향키로 옮김(고르는 것은 Enter·Space). 다시 그린 뒤에도 같은 단추에 초점이 남음(−/+를 연달아 누를 수 있음) | `keyboard-nav`, `focus-management` | `web_kb_webgl_3_adjust` |
| 사전 측정 | 문항은 그대로 한 화면. 척도 점마다 **칸 전체가 눌리는 자리**(높이 64 px, 숫자 18 px 굵게 + 앵커 14 px), 고른 칸은 청록 채움 + 흰 글 + 체크, [답하지 않기]는 같은 줄 오른쪽에 점선으로 떨어뜨림. 고르지 않은 문항이 있으면 기존 문구 "아직 고르지 않은 문항이 N개 있습니다."를 제출 단추 위에 띄우고(토스트 대신) 그 문항 테두리를 표시하고 첫 문항으로 초점 | `touch-target-size`, `state-clarity`, `error-placement`, `focus-management` | `web_webgl_participant_1440_premeasure`, `web_kb_webgl_4_premeasure` |
| 초안 띠 | X35 안내 띠는 두 보기 모두에 남기고 모양만 차분한 띠(왼쪽 노랑 줄, 14 px, 6.2:1)로 | — | 모든 단계 화면 맨 위 |
| 끝 | 끝 문구를 가운데 카드로, 초점 이동 | — | `web_webgl_participant_1440_done` |

**고친 버그(재현됨)**: 조절 화면이 이 세션의 첫 WebGL 화면일 때(후보 단계를 건너뛴 세션 G34, `?sid=`로 다시 연 경우) `liveSlot`이 미리보기 자리를 정한 뒤 `start()`의 `teardown()`이 그 자리를 비워, 첫 조절을 누르기 전까지 미리보기가 회색 칸이었습니다(`before/web_webgl_participant_1440_adjust_skipped.webp`). `start()`를 먼저 부르게 고쳤습니다(`after/` 같은 이름). 테스트 `test_ui_g44.py::test_stage_js_g44_contract`. 이 때문에 `before/web_webgl_*_adjust*`의 미리보기 칸은 회색입니다 — 후보를 고르고 들어간 보통 경로의 이전 화면은 `docs/validation/selection-flow/screens/webgl_2_adjust.png`.

**WebGL 미리보기 자리**: iframe은 그대로 body 아래 하나이고(옮기면 Unity가 다시 시작), 겹쳐 놓는 방식만 `position: absolute`(문서 기준) → `fixed`(창 기준) + scroll 때 다시 맞춤으로 바꿨습니다. 미리보기 칸이 따라 내려오는(sticky) 동안 iframe 자리가 그대로입니다.

## 2. 수치 (직접 잼)

`tools/ui_shots.py`로 화면마다 DOM을 쟀습니다(보이는 요소만, 연구자 패널 안은 누를 자리에서 뺌). 세 미리보기 방식 × 두 보기 × 세 폭(1440·1024·768) × 9 화면(면담·확정·위기·확정 직후·후보·조절·조절(건너뜀)·사전 측정·끝) = 162 화면. 원자료 `after/web_metrics_<방식>.json`, 이전 화면은 `before/web_metrics_<방식>.json`(1440·768만, webgl은 셋).

| 항목 | 전 | 후 |
| --- | --- | --- |
| 가로 스크롤 | 0 화면 | 0 화면 |
| 누를 자리 가장 작은 높이 | 20 px(색 견본 24×24, 척도 라디오, 조건 라디오 등) | **44 px**(162 화면 모두 44 미만 0개) |
| 44 px 미만 누를 자리(webgl 54 화면 합) | 318 | **0** |
| 참여자 영역 가장 작은 글자 | 10.5 px(척도 앵커) | **14 px**(참여자 보기). 연구자 보기 12 px = 연구자용 문구 출처 꼬리표(고정폭) |
| 글자 대비 최소(합성 배경으로 계산, 끈 단추 제외) | 4.18:1(배지), 4.21:1(경고 글) — 4.5 미달 42곳(webgl 54 화면) | 참여자 보기 **4.92:1**, 연구자 보기 4.53:1. 미달 **0** |
| 연구자 패널이 보이는가 | 체크를 풀어야 숨음 | 참여자 보기 0/81 화면, 연구자 보기 81/81 |
| 형태 견본 | 번호 | WebGL·image 조절 화면 모두 9개 그림, 글 요약은 번호 |
| WebGL 견본 그리기 | — | 9장 33–53 ms(Unity 덮어쓰기·캡처 9번 + 되돌림), **그사이 iframe이 화면을 그린 횟수 0**(조절 화면 12개의 작업 12개 모두) → 보이는 미리보기가 다른 형태로 깜빡이지 않음 |
| 조절 누름 → 새 그림이 얹힘(e2e 조절 모든 값) | 중앙값 26 ms | 중앙값 50 ms, 최대 199 ms. 색·밝기 등을 바꾸면 형태 견본 9장을 다시 그리기 때문(형태·움직임만 바꾸면 다시 그리지 않음). 그사이 다음 값을 누르면 지난 견본 작업은 건너뜀 |

토큰 색의 대비(흰 바탕, WCAG 식으로 계산): 본문 #1f2a2c 14.2:1, 보조 #5b6b6e 5.6:1, 흰 글/청록 단추 #3f7a78 4.9:1, 짙은 청록 글 #2f6361/옅은 청록 5.8:1, 경고 글 #7a520a/옅은 노랑 6.2:1, 조작 테두리 #7f8f8d 3.4:1(비글자 3:1 기준), 초점 #22585a 8.0:1. 어두운 테마 토큰도 고쳤지만 캡처·측정은 밝은 테마만 했습니다.

**키보드만으로 끝까지**(마우스 이벤트 없이 Tab·Shift 없음·Enter·Space·방향키·글자 입력, 폭 1024, 세 방식 각 1회): 설정(가명 ID·조건·세션 만들기) → 시작 → 답 7번 → 확정 → [다음 단계로] → 후보 고르기 → 색 견본 묶음(Tab 1번 + →) → 밝기 + 두 번(두 번째는 Tab 없이, 다시 그린 뒤 초점 남음) → 형태 견본 묶음(Home →→) → [다 고쳤어요] → 9문항(문항마다 Tab 1번) → 제출 → 끝. **세 방식 모두 끝까지 감**, 지나간 모든 요소에서 초점 테두리가 보임(없음 0), 단계가 바뀌면 초점이 새 화면 첫 안내 글로 감. 탭 순서가 화면 순서보다 위로 거슬러 오른 것은 맨 끝에서 처음으로 돌아가는 경우뿐(예: 아래의 밝기에서 위의 형태로 가려면 한 바퀴 — 15 Tab). 전에는 색 견본 17개를 하나씩 지나야 했고(크기 +까지 30 Tab), 누를 때마다 화면을 다시 그려 초점이 문서 처음으로 돌아갔습니다. 결과 `after/web_metrics_<방식>.json`의 `keyboard`.

## 3. 다른 확인

| 테스트 | 결과(직접 돌림, 2026-11-23) |
| --- | --- |
| pytest 파일별 `-m "not live"` | **918 통과·6 xfail·실패 0**(기준선 910 + `test_ui_g44.py` 8) |
| dotnet(`unity/Tools/compile-check`) | **397/397**(기준선 389 + 8, Unity 쪽 새 테스트) |
| Unity EditMode | **457/457**(기준선 447 + 10) — 하위 에이전트가 돌림, 메인 작업자는 다시 돌리지 않음 |
| e2e webgl(S1–S9 + 조절 모든 값) | 10 세션 모두 webgl로 끝까지, iframe 재시작 0, 후보 그림 대조 일치, 조절 54/54 화면 바뀜, 움직임 재생, 기대값 불일치 0, 콘솔 오류 0, 면담 뒤 LLM 호출 0 — 이전 결과(`webgl/results/g12_chatbot_e2e_webgl.json`)와 같음 |
| e2e no-webgl2(`--disable-webgl`, S1·S3·S8 + 모든 값) | 4 세션 모두 webgl → image로 내려가 기록됨, 조절 48/48(움직임 6개는 꺼짐), 이전과 같음 |

- **기존 끝에서 끝까지(S1–S9 + 조절 모든 값, `docs/validation/webgl/tools/chatbot_e2e.py`)**: 위 표. 이 도구의 색 견본 찾기만 `aria-label="색 견본 …"` → `data-swatch`로 바꿨습니다(낭독기 이름이 바뀌어서). 직전 작업(CP10)에서 다시 만든 빌드로는 처음 돈 것입니다.
- pytest `chatbot/tests/test_ui_g44.py`(8개): 견본 API가 조절과 같은 규칙으로 덮어쓰기를 만들고 기록·`selection.json` 바이트·현재 상태를 바꾸지 않음, 표 밖 항목·조절 전 단계 거부, image 견본 PNG, 웹 화면 계약(진행 표시에 한글 문구 없음, 범주 버튼에 값 이름 없음, 사전 측정 한 화면, reduced-motion·초점·토큰).

## 4. 정한 것

`docs/decisions.md` 「G44 구현 세부」에 이유와 함께 적었습니다. 요점: 기본은 연구자 보기(지금까지의 기본, 내부 시행 안내가 연구자 화면을 보며 점검함, 설정 화면은 연구자가 씀), 참여자 보기는 `?view=participant` 또는 체크 해제, 되돌리기는 Ctrl+Alt+R 또는 주소(참여자 화면에 되돌리기 단추를 두지 않음). 새 문구 없음. 움직임은 머물러 보기.

## 5. Unity 배치 실험 화면 (`unity/Assets/IFS/Runtime/Placement/`)

하위 에이전트가 고치고 직접 쟀습니다. 상세·재현은 `unity/README.md` 「화면 사용성 점검」, 헤드셋 확인 항목은 `docs/headset-checklist.md` 1.3·1.7·3.8–3.12. 캡처 `before/`·`after/`의 `unity_*.png`(배치 모드 캡처 도구 `unity/Assets/IFS/Editor/PlacementUiCapture.cs`, 눈 시점은 약 25 px/°로 Quest 3 화소 밀도를 흉내 낸 근사), 수치 `unity_metrics.json`.

| 바꾼 것 | 규칙 | 전 → 후 |
| --- | --- | --- |
| 글 색이 지정값보다 옅게 보이던 버그(선형 색공간에서 TextMesh 정점 색이 변환되지 않음) → Inspector 색을 `Color.linear`로 | `color-contrast` | 본문 #4F4F5A로 그려짐 8.1:1 → 18.0:1. 고른 숫자 #5AA0ED 2.73:1 → 짙은 파랑 #0D389E 7.8:1 |
| 7점 앵커가 이웃 칸과 붙어 읽힘("전혀 그렇지 그렇지 않다 약간 그렇지") → 칸 0.2 → 0.22 m, 앵커를 칸 폭에 맞춰 줄바꿈, 이웃 앵커 틈 5 cm 이상(테스트) | `line-length-control`, `whitespace-balance` | `unity_panel_item7_cursor` |
| 고른 값이 색·굵기로만 구별 → 짙은 파랑 테두리 + 옅은 파랑 바탕 + 숫자·앵커 굵게 | `color-not-only` | 같은 캡처 |
| 글자 시야각(2·atan(h / 2d), 판 중심 정면 2.0 m·높이 0.6 m, 눈 1.6 m → d = 2.236 m, 글자 높이는 렌더한 잉크 높이) | `readable-font-size` | 본문 한글 1.31°(그대로), 앵커 0.85° → **1.17°**, 평정 숫자 1.00° → **1.18°** |
| 줄 간격 1.33 → 1.5 em, 여백 0.06 → 0.08 m. 판 위 가장자리가 0.85 m를 넘으면 판을 내림(긴 지시문이 시작 자리 형상 뒤로 올라가지 않게) | `line-height` | `unity_panel_instruction` |
| 실험자 GUI: 맨 위에 지금 단계를 크게, 그 아래 오류 → 초안 → 경고(초안 경고 두 번 → 한 번), 불투명 상자, Setup 가로 넘침 나눔, 참여자 조작 안내를 단추 위에 늘 보이게 | `visual-hierarchy`, `error-placement`, `horizontal-scroll` | `unity_gui_*`. GUI 글 대비 2.3–4.6(반투명) → 6.1–16.3(불투명 #1F2023) |
| [중단]: "다음" 옆 같은 크기 → 오른쪽 끝 빨간 "중단…" + 확인 줄("계속 진행(취소)"·"중단 확정"), 확정해야 기존 `runner.PressAbort()`. 단계가 바뀌면 확인 줄 닫힘 | `confirmation-dialogs`, `destructive-emphasis` | `after/unity_gui_run_abort_confirm` |

실험자 GUI가 헤드셋에 안 보이는 근거(코드): `PlacementExperimenterGui`는 `OnGUI`의 화면 좌표로만 그리고 세계 공간 물체·Canvas·렌더 텍스처를 만들지 않습니다. IMGUI는 주 디스플레이 백버퍼에 그려지고 XR 눈 영상은 카메라가 XR 텍스처로 렌더한 것이라 들어가지 않습니다. 기기에서는 확인하지 않았습니다(점검표 1.3).

## 6. 확인 못 한 것

- **헤드셋 안 가독성**(렌즈를 거친 글자 크기, 고른 칸, 흰 판의 눈부심, 판 양 끝을 읽을 때 고개 돌림)과 실험자 GUI가 헤드셋에 안 나오는지. 헤드셋을 연결하지 않았습니다 → `docs/headset-checklist.md`.
- **창이 있는 실제 브라우저**·다른 PC·Edge·실제 화면 낭독기(NVDA 등). 낭독기 이름·`role`은 코드로만 확인했습니다. 어두운 테마, 200 % 확대, 실제 마우스로 움직임 버튼에 머무는 것(헤드리스에서는 초점·마우스 이벤트를 보내지 않음).
- 움직임 머물러 보기를 화면에서 눈으로 본 것(코드 경로는 조절 재생과 같은 큐). 견본 그림이 거의 검은 색·거의 투명한 상태에서 구별되는지.
- Windows 빌드에서 Unity 판의 새 재질 색. Unity 쪽은 WebGL 미리보기(`Runtime/Preview/`)를 고치지 않아 저장소 밖 빌드를 다시 만들지 않았습니다(`docs/validation/webgl/README.md` 11.8).

## 7. 재현

```bash
# websockets·Pillow가 있는 python. 서버(ui_server.py)는 chatbot/.venv의 python으로 이 스크립트가 띄움. 출력은 저장소 밖
python docs/validation/ui/tools/ui_shots.py --out <저장소 밖>/ui-after-webgl --mode webgl --keyboard
python docs/validation/ui/tools/ui_shots.py --out <저장소 밖>/ui-after-image --mode image --keyboard
python docs/validation/ui/tools/ui_shots.py --out <저장소 밖>/ui-after-none --mode none --keyboard
# 이전 화면: 이전 커밋의 web/ 네 파일을 저장소 밖 폴더에 꺼내 --web-dir <그 폴더> --legacy-view --label before
```
