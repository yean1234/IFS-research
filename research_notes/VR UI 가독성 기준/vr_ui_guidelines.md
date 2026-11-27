# VR UI 가독성·사용성 기준과 현재 헤드셋 화면 감사

> 작성 2026-11-27 · 조사·감사만 했고 코드는 고치지 않았다.
> 대상: 배치 러너(Quest 3 + Quest Link, OpenXR)의 참여자 판, 평정 표시, 컨트롤러 조작, 광선.
> 수치는 코드 기본값에서 계산했다. 헤드셋에서 잰 값은 없다(`docs/headset-checklist.md` 미실시).

## 0. 범위

- VR에서 참여자가 보는 UI는 배치 러너(`unity/Assets/IFS/Runtime/Placement/`) 하나다. 세계 공간 참여자 판(`PlacementTextPanel`), 그 아래 평정 기준점 줄, XR 광선과 손 표시(`XrPlacementInput`), 놓기 도움 표시(`PlacementSpace`)로 이루어진다.
- 과제에 적힌 "속성 조절 7항목 패널"은 VR에 없다. 헤드셋 전에 데스크톱 웹(`chatbot/ifs_chatbot/web/stage.js`)에서 두 집단이 똑같이 쓴다. VR 안에서 속성을 고치면 보기만 조건이 오염되기 때문이다(G11, `PlacementSelection.cs:30`). 그래서 이 감사에서는 뺐다.
- VR에는 슬라이더가 없다. 평정은 숫자 칸 줄이고, 실험자가 키보드로 넣는다. 설정 `participantRatesWithController`를 켜면 참여자가 썸스틱으로 고르고 트리거로 확정한다.
- 소유감 러너(`Ownership/`)에는 XR 리그와 컨트롤러 입력이 없고 헤드셋에서 확인한 적도 없다(`unity/README.md:305`). 글자 생성 코드(`ParticipantTextDisplay`)는 배치 러너와 같이 쓰므로 그 부분만 다룬다.

## 1. 기준 표

확인 수준 표기: **1차** = 원문 페이지나 논문 본문을 직접 열어 읽음. **2차** = 검색 요약이나 다른 논문의 인용으로만 확인함.

### 1.1 글자 크기

| 항목 | 기준 | 출처(확인 수준) |
| --- | --- | --- |
| 단위 | dmm = 1 m 거리에서 1 mm 높이(각도 단위, 거리와 무관). 1° ≈ 17.5 dmm | Kojić 외 2020 QoMEX, Google 정의 인용 (1차) |
| 최소 판독 | 2 m에서 0.35–0.4°(12.2–14.0 mm). 0.45 m에서 0.4–0.5° | Microsoft Typography (1차) |
| 편한 판독 | 2 m에서 0.6–0.75°(20.9–26.2 mm). 0.45 m에서 0.65–0.8° | Microsoft Typography, Text in Unity (1차) |
| 사용자가 고른 값 | Quest·Go, 22명. 21·51단어 본문은 평균 16.2–17.9 dmm(약 0.93–1.02°), 2단어 짧은 글은 27.5–32.1 dmm(약 1.6–1.8°). 글이 길수록 작은 크기를 고름 | Kojić 외 2020 (1차, 표 I) |
| 사용자가 고른 값 | Rift. 41 ± 14 dmm(약 2.3°). 흰 글/검은 바탕과 산세리프를 선호 | Dingler 외 2018 CHI EA, Kojić 2020의 인용 (2차) |
| 플랫폼 최소 | 14 px 이상, 편한 읽기는 18 px 이상. 굵은 굵기가 더 잘 읽힘(거리 가정은 적혀 있지 않음) | Meta Horizon Typography (1차) |
| 플랫폼 최소 | 14 dp 이상, normal 이상 굵기. 0.868 dmm/dp이므로 14 dp ≈ 12.2 dmm ≈ 0.70°(em 기준). SDF 글꼴 권장 | Android XR Visual design (1차) |
| 한자(복잡 문자) | OST HMD에서 0.32–1°를 시험함. 0.32°는 제외하고 0.84°가 최적이었으며, 피로는 약 0.95°까지 줄다가 다시 늘었다. 획이 많고 드물게 쓰는 글자일수록 큰 시각도가 필요함 | Gu·Bao 2024 *Ergonomics*, Hsiao 외 2024 *BIT* (2차) |
| 한글 | HMD에서 한글 시각도를 잰 연구는 찾지 못했다. 한글은 자모가 겹쳐 획 밀도가 높으므로 한자 결과를 근거로 본문 0.9–1.0° 이상, 기준점처럼 짧은 낱말은 1° 이상을 잠정 기준으로 둔다 | 추론(근거: 위 한자 연구) |
| 화소 | Quest 3는 25 PPD(눈당 2064×2208)이므로 1°는 화면 약 25 화소 | Meta Quest 3 사양 (2차) |
| 굵기 | 작은 크기에서 Light·Semilight를 쓰지 않는다(가는 세로획이 떨림) | Microsoft Typography (1차) |
| 렌더링 | 기본 UI Text·3D Text Mesh는 흐리다. TextMeshPro(SDF)는 거리와 상관없이 윤곽이 선명하다 | Microsoft Text in Unity (1차) |
| 렌더링 | 눈 버퍼에 한 번, 왜곡 단계에서 또 한 번 표본을 뜨면서 흐려진다. 컴포지터 레이어는 한 번을 건너뛰어 작은 글자도 또렷하다. 프레임당 최대 16개 | Meta OS compositor layers (1차) |

### 1.2 패널 거리·크기·배치

| 항목 | 기준 | 출처(확인 수준) |
| --- | --- | --- |
| 거리 | 최적 1.25–5 m, 가능하면 2.0 m 근처. 몰입형 기기의 초점 거리는 1.25–2.5 m이고 대부분의 내용은 1 m 이상에 둔다. 깊이가 다른 두 곳을 번갈아 보는 일과 깊이 방향으로 움직이는 내용을 줄인다 | Microsoft Comfort (1차) |
| 거리 | 오래 보는 메뉴는 약 1 m, 시선보다 조금 아래 | Meta MR design guideline, Color management guide (2차) |
| 거리 | 패널을 1.75 m에 연다 | Android XR Visual design (1차) |
| 세로 시선 | 쉬는 시선은 수평 아래 10–20°, 최적 영역은 0–35° 아래. 10° 위나 60° 아래를 넘는 시선은 피한다 | Microsoft Comfort (1차) |
| 가로 | 목을 중심에서 45° 넘게 돌리지 않는다 | Microsoft Comfort (1차) |
| 가로 | 주 내용은 41° 시야 안에 둔다 | Android XR Visual design (1차) |
| 머리 회전 | 좌우 편한 범위 30°, 최대 55°. 위 20°(최대 60°), 아래 12°(최대 40°) | Alger 2015, Chu(Samsung) 인용 (2차) |
| 고정 방식 | 머리에 붙인 HUD는 불편을 일으킨다. 꼭 필요하면 몸에 붙이고, 일정 각도를 넘을 때만 따라오게 한다 | Microsoft Comfort (1차) |
| 고정 방식 | 내용을 머리에 붙이지 말고 공간에 고정한다 | Apple visionOS Spatial layout (1차), Meta Comfort (1차) |
| 깊이 | 글에 깊이를 주지 않는다(바탕 위에 뜬 글은 읽기 어렵고 눈이 불편하다) | Apple Spatial layout (1차), Meta Comfort (1차) |
| 양 | 창과 물체를 너무 많이 띄우지 않는다. 주 조작은 패널 하나에 모은다 | Apple (1차), Meta Comfort (1차) |
| 곡률 | 숫자 기준을 찾지 못했다. Meta는 휘어진 UI에 원기둥 컴포지터 레이어를 권한다 | Meta OS compositor layers (1차) |

### 1.3 대비·배경판·색

| 항목 | 기준 | 출처(확인 수준) |
| --- | --- | --- |
| 배경판 | 어둡거나 색이 있는 배경판 위의 흰 글을 권한다(가산 표시 기준) | Microsoft Typography (1차) |
| 사용자 선호 | 최적으로 고른 대비비는 평균 8.7–11.9:1(모든 조건에서 7:1 이상). 21:1은 '최악'으로 약 3분의 1이 골랐다. 밝은 바탕은 눈에 빛이 너무 많게 느껴질 수 있다 | Kojić 외 2020 (1차) |
| 사용자 선호 | 흰 글/검은 바탕을 선호 | Dingler 외 2018 (2차) |
| 배경판 | 흰 글 + 사각 배경판(billboard)이 여러 배경에서 잘 읽히고, 얇은 외곽선이 대비를 높인다 | Google Fonts Knowledge AR/VR, Jankowski 계열 인용 (2차) |
| 색 | 대비를 충분히 두고, 색각 이상에도 읽히는 조합을 쓰며, 눈을 피로하게 하는 조합을 피한다 | Android XR (1차) |
| 글꼴 수 | 한 맥락에서 글꼴 가족은 두 개까지 | Microsoft Typography (1차) |
| 주변부 | 주변부에 밝고 대비가 큰 물체나 움직임을 두지 않는다 | Apple Spatial layout (1차) |

### 1.4 조작·목표 크기·피드백

| 항목 | 기준 | 출처(확인 수준) |
| --- | --- | --- |
| 먼 목표(광선·시선) | 2 m에서 1° 이상(3.5 × 3.5 cm) | Microsoft Interactable object (1차) |
| 직접 터치 | 45 cm에서 2° 이상(1.6 × 1.6 cm) | Microsoft Interactable object (1차) |
| 목표 간격 | 버튼 중심 사이 60 pt 이상, 사이 빈틈 16 pt 이상. 겹치지 않게 | Apple Spatial layout (1차) |
| 목표 크기 | 56 dp 권장(아이콘 48 dp), 목표 사이 8 dp 이상, 포인터 목표가 겹치지 않게 | Android XR (1차) |
| 상태 피드백 | 기본·겨눔(hover)·누름 세 상태를 서로 다르게 보인다(강조·크기). 잡기 시작·끝은 소리로도 알린다 | Microsoft Interactable object (1차) |
| hover | hover·focus 상태를 둔다. 포인터 입력에서 특히 중요하다 | Android XR (1차) |
| 간접 조작 | 직접 손을 뻗는 조작보다 간접 조작을 우선한다. 시선 높이 이상에 놓인 물체를 직접 만지는 일은 피곤하다 | Apple Spatial layout (1차) |
| 거리 | 멀리서 조작하는 방법을 둔다. 먼 물체를 직접 다루거나 오래 조작하게 하지 않는다 | Meta Comfort (1차) |
| Unity 구현 | 세계 공간 Canvas + Tracked Device Graphic Raycaster + XR UI Input Module(다른 입력 모듈과 같이 쓰지 않음) | Unity XRI UI setup (2차, 매뉴얼 검색 요약) |

### 1.5 VR 안 설문·안내문

| 항목 | 기준 | 출처(확인 수준) |
| --- | --- | --- |
| VR 안 설문 | VR 밖 설문과 완료 시간이 비슷하다. 즐거움은 높고 사용성은 낮다. 참여자는 VR 안 설문을 선호한다. 가리키기와 세계 고정 제시가 쓸 만한 방식이다. 몸·정신 부담은 조금 높다 | Alexandrovsky 외 2020 CHI (1차, 연구실 요약 페이지) |
| 몰입 끊김 | VR 안 설문도 몰입을 끊지만, VR 밖보다 작고 짧다(EDA) | Putze 외 2020 CHI, 50명 (2차) |
| 글 양 | 줄 길이를 짧게, 글 주위에 여백을 충분히 둔다. 움직이는 물체에 글을 붙이지 않는다(멀미) | Android XR (1차) |
| 글 양 | 21·51단어 글은 2단어 글보다 작은 크기를 골랐다. 긴 글은 본문 크기(약 1°)로 충분하다 | Kojić 외 2020 (1차) |

### 1.6 멀미·피로

| 항목 | 기준 | 출처(확인 수준) |
| --- | --- | --- |
| 프레임 | 최소 60 FPS, 기기 최대 주사율 권장 | Microsoft Comfort (1차) |
| 깊이 이동 | 깊이 방향으로 움직이는 물체와 가까움·멂의 빠른 전환이 불편을 키운다. 1 m 안 깊이 이동은 전체 시간의 25% 이하로 둔다 | Microsoft Comfort (1차) |
| 자기 이동 | 사용자가 시작하지 않은 이동, 특히 세로 이동을 피한다 | Microsoft Comfort (1차) |
| HUD | 머리에 1:1로 붙인 HUD를 쓰지 않는다 | Microsoft Comfort (1차) |
| 팔 | 손을 계속 들고 있게 하거나 같은 동작을 오래 반복하게 하지 않는다 | Microsoft Comfort (1차) |

## 2. 현재 값 대 기준

계산 조건: 판 중심은 정면 2.0 m, 높이 0.6 m, 눈높이 1.6 m. 따라서 눈–판 거리는 2.236 m이고 판 중심은 수평 아래 26.6°다. 잉크 높이 비율(한글 0.94, 숫자 0.72)은 `PlacementPanelMetrics`의 실측값을 썼다. 판 크기와 줄 수는 `PlacementTextPanel.Layout`과 `ParticipantTextDisplay.Wrap`의 규칙을 그대로 따라 scaleA 문구 파일(`placement_task.scaleA.v0.json`)로 계산했다.

| 항목 | 현재 값 | 위치(파일:줄) | 기준 | 판정 |
| --- | --- | --- | --- | --- |
| 본문 글자 | 칸 5.44 cm, 한글 잉크 5.11 cm = **1.31°**(22.9 dmm) | `PlacementPanelMetrics.cs:22-25`, `PlacementTextPanel.cs:26-28` | 편한 판독 0.6–0.75°, 선호 0.93–1.02°, 한자 최적 0.84° | 충족(여유 있음) |
| 기준점 뜻 글자 | 잉크 4.51 cm = **1.16°** | `PlacementPanelMetrics.cs:27`, `PlacementTextPanel.cs:36` | 짧은 낱말 1° 이상(잠정) | 충족 |
| 평정 숫자 | "7" 잉크 4.61 cm = **1.18°** | `PlacementPanelMetrics.cs:31`, `PlacementTextPanel.cs:34` | 1° 이상 | 충족 |
| 화소 | 본문 약 33 px, 뜻 약 29 px(25 PPD) | — | 1° ≈ 25 px | 충족 |
| 글자 렌더링 | 레거시 `TextMesh` + OS 동적 비트맵 글꼴(fontSize 64), SDF 없음, 밉맵 없음, 컴포지터 레이어 없음 | `PlacementTextPanel.cs:2, 219-249`, `ParticipantTextDisplay.cs:16, 43` | TMP SDF(Microsoft, Android XR), 컴포지터 레이어(Meta) | **미충족**: 흐림과 깜빡임 위험이 있고 실기 미확인 |
| 글꼴 | 맑은 고딕 Regular(PC의 OS 글꼴). 없으면 `LegacyRuntime.ttf`로 대신하는데 이 글꼴에는 한글이 없다 | `ParticipantTextDisplay.cs:16, 46-51`, `PlacementTextPanel.cs:221` | 산세리프, 보통 이상 굵기 | 충족(Link 실행 한정). 단독 실행(Android)에서는 한글이 안 보일 수 있음 |
| 줄 간격 | 1.50 em(1.13 × 1.33) | `PlacementTextPanel.cs:31-32` | 여백 충분 | 충족 |
| 줄 길이 | 한글 20자 이하(판 너비 1.04–1.15 m = 26–29°) | `PlacementTextPanel.cs:30` | 짧은 줄 | 충족 |
| 글 양 | `items_instruction` 155자 **8줄**(판 높이 0.81 m), `stop_distance_loop` 115자 7줄 + 안내 2줄, `condition_place`+범위 안내 5–6줄 | `placement_task.scaleA.v0.json`, `PlacementSession.cs:389, 491, 947` | 줄과 양을 줄이고 여백 확보 | 부분 충족: 긴 판이 아래로 처짐(다음 줄) |
| 판 세로 위치 | 중심 26.6° 아래. 긴 판은 위 가장자리를 0.85 m로 묶어 아래로 내리므로 아래 가장자리가 **36.5–37.8°** 아래 | `PlacementRunner.cs:70-73, 841`, `PlacementTextPanel.cs:57-60, 369-379` | 최적 0–35°, 쉬는 시선 10–20° | **경계 초과**: 긴 판의 아랫줄이 최적 영역 밖 |
| 판 가로 폭(평정) | 7칸 × 0.22 m + 여백 = 1.70 m = **41.6°**(양 끝 ±20.8°) | `PlacementTextPanel.cs:40-42`, `PlacementPanelMetrics.cs:78` | 주 내용 41° 안, 목 45° 미만 | 경계: 끝 칸을 보려면 눈을 크게 돌려야 함 |
| 판 거리 | 2.24 m | `PlacementPanelMetrics.cs:39-43` | 최적 1.25–5 m, 2 m 근처 | 충족 |
| 물체와 판 | 물체는 1.5 m(15° 아래), 판은 2.24 m(27° 아래). 판이 물체보다 0.7 m 뒤 | `PlacementConfig.cs:42-43` | 깊이를 자주 오가지 않게 | 대체로 충족(같은 초점 영역) |
| 고정 방식 | 세계 고정. 판은 바닥 원점의 고정 눈 자리 `(0, 눈높이, 0)`을 본다. 머리를 따라다니지 않음 | `PlacementTextPanel.cs:1, 381-385`, `PlacementRunner.cs:842` | 세계 고정(Apple, Meta, Microsoft) | 충족. 단, 참여자가 걸어 나가면 비스듬히 보임 |
| 깊이 | 글과 배경 사이 1 cm, 글은 깊이 검사함(물체가 앞에 오면 글을 가림) | `PlacementTextPanel.cs:7-8, 53-54, 343` | 글에 깊이 주지 않기 | 충족 |
| 대비 | 짙은 글 #141419 / 옅은 회색 판 0.90 + 방출 0.6 → 렌더 화소는 **#16161C 대 #FFFFFF = 18.0:1** | `PlacementPanelMetrics.cs:14-15`, `PlacementTextPanel.cs:43-46, 162`, `unity/README.md:575` | 7:1 이상. 선호 평균 9–12:1, 21:1은 '최악'으로 자주 뽑힘. 흰 글/어두운 판 선호 | **과함**: 큰 흰 판(약 28° × 20°)이 눈부실 수 있음. 우주 공간(E)에서는 더 심함 |
| 고른 칸 | 짙은 파랑 굵게 + 테두리 1.2 cm + 옅은 파랑 바탕, 7.8:1 | `PlacementTextPanel.cs:44-50, 347-364` | 색만으로 구별하지 않기, hover·선택 상태 | 충족 |
| 색 수 | 글 2색(검정, 파랑), 판 회색 1, 고른 칸 2 | `PlacementPanelMetrics.cs:14-19` | 적게 | 충족 |
| 광선 | 굵기 4 mm(1 m에서 0.23°), 끝 구 3 cm, 파랑 #4D73B3, 최대 8 m | `XrPlacementInput.cs:83-88, 147-168` | 상태 피드백 | 광선 자체는 충분. hover 상태 없음(다음 줄) |
| 잡기 목표 | 판정 구 반지름 = max(0.15 m, 물체 반지름). 1.5 m에서 11° 이상 | `PlacementConfig.cs:62`, `PlacementRunner.cs:699` | 1° 이상 | 충족(넉넉함) |
| 겨눔(hover) 피드백 | 없음. 물체를 겨눠도 광선과 끝점이 바뀌지 않고, 잡히면 광선 끝이 물체 중심에 붙을 뿐 | `XrPlacementInputLogic.cs:169-182`, `unity/README.md:604` | 기본·hover·누름 세 상태(Microsoft, Android XR) | **미충족** |
| 누름·잡기 피드백 | 시각: 잡으면 광선 길이만 바뀜. 소리·햅틱 없음 | `XrPlacementInput.cs` 전체(햅틱 호출 없음) | 잡기 시작·끝 소리(Microsoft) | **미충족** |
| 버튼 배정 | 트리거·그립 = 잡기, 썸스틱 앞뒤 = 당기기·밀기, A·X = 확인, 트리거 = 멈춤, 썸스틱 좌우 + 트리거 = 평정 | `XrPlacementInputLogic.cs:3-10` | 일관된 조작 | 충족(단계마다 트리거 뜻이 바뀌는 점은 안내 필요) |
| 입력 이력 | 데드존 0.2, 트리거 누름 0.55·뗌 0.35, 평정 한 칸 0.6·복귀 0.3 | `XrPlacementInputLogic.cs:49-56` | 떨림 방지 | 충족 |
| 조작 안내 | 참여자 판에 버튼 안내가 없음(사람이 정할 일로 남김). 문구에는 "확인 버튼", "방아쇠"라고만 적힘 | `unity/README.md:598`, 문구 파일 `stop_loop_hint` | 처음 쓰는 사람의 학습 | **미충족**(실험자 구두 설명에 의존) |
| 참여자 평정 | 처음 젖히면 가운데 값부터 표시, 트리거를 누르면 바로 기록. 참여자가 되돌릴 방법은 없음(실험자 Backspace만) | `PlacementSession.cs:432-449` | 피드백, 실수 복구 | 부분 충족: 확정됐다는 표시가 없음 |
| 당기기·밀기 속도 | 1.0 m/s(깊이 방향 이동) | `PlacementConfig.cs:57` | 깊이 이동 줄이기 | 주의: 사용자가 시작한 이동이라 허용 범위. 실기에서 확인 |
| 멈춤 왕복 | 0.4–3.6 m 정면 직선, 0.25 m/s, 바닥 고리 숨김 | `PlacementConfig.cs:147-169` | 깊이 이동 | 과제상 필요. 느린 속도라 무난 |
| 판이 거리 단서가 됨 | 조건 단계와 멈춤 거리 단계 내내 정면 2.0 m에 밝은 판이 보인다. 멈춤 왕복에서는 거리 단서를 없애려고 바닥 고리를 숨기면서 판은 남겨 둔다 | `PlacementSession.cs:412, 491, 947`, `PlacementRunner.cs:841-849`, `PlacementConfig.cs:169` | (연구 설계) 거리 결과변수에 기준점을 주지 않기(G60-2, G62-e의 취지) | **연구 위험**(개선 1) |

## 3. 개선 목록(우선순위)

"예상 값"은 제안값이다. 모든 항목은 헤드셋에서 확인한 뒤에 정한다. 코드 기본값을 바꾸면 기존 골든·검증 자료가 깨진다(G52, G59-8). 그래서 새 동작은 설정 플래그로 넣고 기본은 꺼 둔 채, 본 실험 권고 설정(G59-8 표)에서만 켜는 방식을 권한다.

| 순위 | 문제 | 바꿀 파일 | 예상 값 | 연구 설계에 주는 위험 |
| --- | --- | --- | --- | --- |
| 1 | **안내 판이 거리 기준점이 된다.** 조건 단계(직접 배치)와 멈춤 거리 단계에서 정면 2.0 m의 밝은 판(폭 1.1 m)이 계속 보인다. 바닥 고리는 숨기면서 판을 남기면, 놓은 거리와 멈춘 거리가 2 m 근처에 몰릴 수 있다 | `PlacementSession.cs:412, 491, 947`, `PlacementRunner.cs:841-849`, `PlacementConfig.cs`(새 플래그) | 판을 읽을 시간을 준 뒤(첫 입력 때나 실험자 키, 또는 N초 뒤) 판을 숨긴다. 또는 이 두 단계에서만 판을 정면 밖(방위 ±35°, 같은 거리)으로 옮긴다. 기본 꺼짐, manifest `config`에 기록 | 절차가 바뀌므로 RQ2 결과변수(놓은 거리·멈춘 거리)에 직접 영향이 있다. 두 조건에 똑같이 적용하고, 본 자료를 모으기 전에 정해야 한다. ⚠ 사람이 정할 것 |
| 2 | **실기 가독성을 확인한 적이 없다.** 모든 값이 캡처 근사치(25 px/°)다 | `docs/headset-checklist.md`(항목 추가, 코드 변경 없음) | 참여자 자리에서 판 글 소리 내어 읽기(오독 수), 평정 줄 양 끝 칸 읽기, 우주(E) 공간에서 눈부심 5점 평정, 긴 지시문의 마지막 줄 읽기, 고개를 숙인 각도 기록 | 없음(점검만) |
| 3 | **글 렌더링 품질.** 레거시 TextMesh 비트맵 글꼴은 흐리고, 축소할 때 밉맵이 없어 깜빡일 수 있다. 판 글이 두 번 표본을 거친다 | `PlacementTextPanel.cs:219-249`, `ParticipantTextDisplay.cs:34-54`, 새 TMP 글꼴 에셋 | TextMeshPro SDF(Unity 6 내장 uGUI 2.0). 한글 글꼴은 OFL 라이선스(Noto Sans KR 또는 Pretendard)를 저장소에 넣는다(맑은 고딕은 재배포할 수 없음). 정적 아틀라스 4096², 표본 크기 64–90, 패딩 9 이상. 각도 크기는 지금 값(1.31°/1.16°/1.18°)을 유지한다. 선택: 판을 RenderTexture로 그려 OpenXR 컴포지터 레이어(Unity XR Composition Layers)로 낸다 | 화면 표현만 바뀌고 두 조건에 같다. 다만 G44의 "외부 글꼴 쓰지 않는다"와 부딪치므로(로컬 파일이라도 새 글꼴) ⚠ 사람이 정할 것. `docs/validation/ui` 실측(잉크 비율 0.94/0.72, 대비)을 다시 재야 한다. 단독(Android) 실행의 한글 대체 문제도 함께 풀린다 |
| 4 | **판이 너무 밝고 대비가 최대다(18:1, 흰 판).** 큰 흰 면이 시야의 약 28° × 20°를 차지한다. 사용자 연구에서는 21:1이 자주 '최악'으로 뽑혔고 어두운 판이 선호됐다. 우주 공간(E)에서는 휘도 차가 더 크다 | `PlacementPanelMetrics.cs:14-19`, `PlacementTextPanel.cs:43-48, 162` | 안 A(어두운 판): 판 #2A2B30, 글 #E6E6E8, 고른 칸은 글 #9EC3FF + 테두리(판 대비 약 7.9:1), 본문 대비 약 11:1. 안 B(밝기만 낮춤): 방출 0.6 → 0, 판 0.80(#CCCCD0), 대비 약 11:1. 대비 테스트의 하한 4.5:1은 그대로 두고 상한(예: 15:1)을 더한다 | 판 휘도가 눈의 순응과 물체의 겉보기 밝기·대비 지각에 영향을 줄 수 있다. 조건 간에는 같지만 G56의 형상 대비 측정 조건과는 달라진다. 본 자료 전에 정해야 한다. 고른 칸 색은 다시 검증해야 한다 |
| 5 | **조작 안내가 없다.** "확인 버튼", "방아쇠"가 어느 버튼인지 헤드셋 안에서 알 수 없다. 트리거 뜻이 단계마다 바뀐다(잡기, 멈춤, 평정 확정) | 문구 파일 `placement_task*.json`(새 키), `XrPlacementInput.cs`(손 자리에 컨트롤러 모양과 버튼 이름표) | 컨트롤러 모형 위 버튼 옆에 짧은 이름표(예: A/X "확인", 트리거 "잡기"/"멈춤")를 그 단계에서 쓰는 버튼에만 띄운다. 글자 1° 이상, 손 거리 0.45 m 기준 높이 8 mm 이상. 또는 실험자 대본에 버튼 설명을 고정한다 | 참여자가 보는 새 고정 문구이므로 원칙 7에 따라 `status: draft`, 출처, 문구 파일 버전 올림이 필요하다. 원칙 3에 따라 묘사어나 예시를 넣지 않는다. 직접 배치 조건에서 쓰는 버튼이 더 많아, 이름표 수가 조건마다 다르다는 점을 기록한다. ⚠ 사람이 정할 것(README:598) |
| 6 | **긴 판이 아래로 처진다.** `items_instruction`이 8줄이라 아래 가장자리가 37.8° 아래로, 최적 영역 35°를 넘는다. 판을 위로 올리면 시작 자리의 물체(반지름 0.3 m의 아래 가장자리 시선이 판 자리에서 y = 0.67 m)를 가린다 | `PlacementTextPanel.cs:30`(`wrapChars`) 또는 `PlacementSession.cs:389`(지시문 쪽 나누기) | 안 A: `wrapChars` 20 → 24. `items_instruction` 8 → 7줄(아래 36.5°), `stop_distance_loop` 7 → 5줄(아래 33.4°). 판 폭은 1.32 m = 33°. 안 B: 지시문만 문장 경계에서 두 쪽으로 나누고 실험자 Enter로 넘긴다(글자는 그대로) | 안 A는 표현만 바뀐다. 안 B는 제시 방식과 지시문 읽는 시간이 바뀌므로 ⚠ 사람이 정할 것(G44는 웹 사전 측정을 한 화면에 두기로 했다). 두 조건에 같다 |
| 7 | **겨눔(hover) 상태가 없다.** 광선이 물체나 연습 상자에 닿아도 아무것도 바뀌지 않아, 잡을 수 있는지 미리 알 수 없다 | `XrPlacementInput.cs:83-88, 147-168`, `PlacementRunner.cs:883-897` | 광선이 잡기 판정 구에 닿으면 광선과 끝점 색을 바꾸고(예: #4D73B3 → #F2B233) 끝 구를 3 → 4.5 cm로 키운다. 잡는 동안에는 또 다른 상태(굵기 4 → 6 mm). 물체 자체의 색과 재질은 건드리지 않는다 | 낮음. 광선은 직접 배치·가리켜 지정 조건에만 보인다. 물체의 겉모습이 바뀌지 않으므로 자극물은 같다 |
| 8 | **햅틱·소리 피드백이 없다.** 잡기·놓기·확인·평정 한 칸·확정이 손에 전달되지 않는다 | `XrPlacementInput.cs`(`InputDevice.SendHapticImpulse`), `XrPlacementInputLogic.cs`(사건 플래그) | 잡기·놓기 0.3 진폭 20 ms, 확인·평정 확정 0.5 진폭 40 ms, 평정 한 칸 0.2 진폭 10 ms. `events.csv`에 `haptic` 사건(추가만) | 낮음~중간. 두 조건이 함께 쓰는 사건(멈춤, 평정)에는 똑같이 준다. 잡기·놓기 햅틱은 직접 배치에만 있어 조건 차이가 조금 커지므로 기록해 둔다 |
| 9 | **참여자 평정 확정이 보이지 않는다.** 트리거를 누르면 바로 기록되고 다음 문항으로 넘어가며, 무엇이 기록됐는지 표시가 없다 | `PlacementSession.cs:444-449`, `PlacementTextPanel.cs:347-364` | 확정된 칸을 0.4 s 동안 굵은 테두리(0.012 → 0.02 m)로 깜빡인 뒤 넘긴다. 이 0.4 s는 `rt_ms`에 넣지 않는다. 확정 방식(트리거 한 번)은 그대로 | 확정 방식은 바꾸지 않는다(G44). 문항 사이 간격이 0.4 s 늘어난다. 지금 기본값(`participantRatesWithController = false`, 구두 응답 + 실험자 입력)에서는 영향이 없다 |
| 10 | **평정 줄이 넓다(41.6°).** 7칸 양 끝의 기준점 뜻을 읽으려면 눈을 ±21° 돌려야 한다 | `PlacementTextPanel.cs:40`(`columnWidthM`) | 0.22 → 0.20 m(폭 1.56 m = 38.4°). 기준점 뜻 줄바꿈이 한 칸에 3–4자로 늘어나는지 캡처로 확인 | 표현만 바뀌고 두 조건에 같다. 앵커 글자는 그대로 |
| 11 | 판이 바닥 원점의 고정 눈 자리를 본다. 직접 배치 중 걸어 나간 참여자는 사후 문항을 비스듬히 본다 | `PlacementRunner.cs:841-842` | 평정 단계를 시작할 때 한 번만 지금 머리 위치 쪽으로 판의 방위를 돌린다(따라다니지 않음). 또는 실험자 대본에 "가운데 표식으로 돌아오기"를 넣는다 | 판 자리가 참여자 위치에 따라 달라지면 조건 간 기하가 달라진다. 대본 안이 더 안전하다. ⚠ 사람이 정할 것 |
| 12 | 광선 굵기 4 mm는 1 m에서 0.23°로 가늘어 계단 현상이 생길 수 있다 | `XrPlacementInput.cs:83` | 6 mm, 끝으로 갈수록 옅게 | 없음 |
| 13 | 단독 실행에서 한글 글꼴이 없다(내장 대체 글꼴에 한글 없음) | `ParticipantTextDisplay.cs:46-51` | 3번을 하면 해결된다. 하지 않는다면 단독 빌드에서 글꼴 경고를 시작 거부로 바꾼다 | 없음(지금은 Link 실행) |
| 14 | 당기기·밀기 1.0 m/s는 빠른 깊이 이동이다 | `PlacementConfig.cs:57` | 실기에서 0.6–0.8 m/s와 비교 | 놓기 행동(경로 길이, 시간)에 영향을 준다. ⚠ 사람이 정할 것 |

## 4. 바꾸면 안 되는 것

| 대상 | 근거 |
| --- | --- |
| 물체 시작 자리 정면 1.5 m, 높이 1.2 m(`startDistanceM`, `startHeightM`). spec의 `layout.distance`·`verticalOffset`은 무시하고, 선택 파일의 위치·거리 키는 거부한다 | G10, G33, `unity/README.md:367, 491`, `PlacementSelection.cs:12-13` |
| VR 안에서 속성(7항목)을 고치는 입력을 넣지 않는다. 조절은 데스크톱에서 두 집단이 똑같이 한다 | G11, `PlacementSelection.cs:30` |
| 참여자가 보는 고정 문구의 글자(`shared/protocol/`, `unity/Assets/StreamingAssets/IFS/placement_task*.json`). 고치거나 더하면 `status`(draft)와 출처를 적고 버전을 올린다 | AGENTS 원칙 7, X35, G57 |
| 문구에 참여자가 쓰지 않은 묘사어·예시·선택지를 넣지 않는다. 형태 견본에 이름을 붙이지 않는다 | AGENTS 원칙 3, G44 |
| 문항 순서, 평정 방식(점 수, 앵커, 확정 방식), 단계 순서 | G44, `unity/README.md:566` |
| 두 조건(직접 배치 대 보기만)이 공유하는 화면 요소는 같아야 한다: 판 자리·크기·색·글꼴, 공간, 평정 UI, 평정 중 물체 숨김, 눈높이 정규화 | G1(형상은 두 조건이 같이 쓰는 자극물), G59-8, G60-3 |
| 눈높이 정규화(`eyeHeightMode = relative`): 판 높이도 "설정 높이 + (잰 눈높이 − 1.60 m)"를 따른다 | G60-3, `PlacementRunner.cs:839-841` |
| 거리 단서 통제: 멈춤 왕복의 바닥 고리 숨김, 0.4–3.6 m 왕복, 0.25 m/s 일정 속도 | G60-2, `PlacementConfig.cs:147-169` |
| 공간 후보(B/E/F)의 하늘·바닥·조명. 바꾸면 형상 대비(G56)를 다시 재야 한다 | G52–G56 |
| 기록 형식은 추가만 한다(`recordVersion` 그대로, 기존 열·키를 지우지 않음). 기본 설정의 기록은 바이트 단위로 같아야 한다 | `unity/README.md:431, 534`, G52 |
| 코드 기본값(기존 골든·검증 자료 보존). 새 동작은 플래그로 넣고 기본은 꺼 둔다 | G52, G59-8 |
| 안전 표시(`safetyFlags`)는 실험자 화면에만 보인다. 헤드셋 판에는 내보내지 않는다 | G50, `unity/README.md:482` |
| 상용 API, 외부 CDN, 외부 글꼴을 쓰지 않는다(로컬 실행) | AGENTS 원칙 5, G44 |
| 참여자 판에 입력 안내를 넣을지는 사람이 정한다(넣으면 draft 문구) | `unity/README.md:598` |
| 초안 경고 줄은 실험자 화면과 기록에 남긴다 | X35, G59-8 |

## 5. Claude Code용 Unity·XR 스킬과 플러그인(설치하지 않음)

| 이름 | 출처 | 한 줄 평가 |
| --- | --- | --- |
| Unity Plugin for Claude Code(공식, 2026-09-09) | https://unity.com/blog/unity-plugin-for-claude-code · https://claude.com/plugins/unity | 스킬 29개. `/ui-ugui`·`/ui-uitk`·`/optimize-text-mesh-pro`는 3번(TMP 전환)에 바로 쓸 만하다. XR 전용 스킬은 없다. 계정과 클라우드가 필요한지는 페이지에 적혀 있지 않아, 원칙 5에 맞는지 확인해야 한다 |
| IvanMurzak/Unity-MCP("AI Game Developer") | https://github.com/IvanMurzak/Unity-MCP | 로컬 MCP 서버와 `.claude/skills` 묶음. EditMode·PlayMode 테스트 실행, 장면 질의. 실험 중인 에디터를 조작하므로 기록과 기본값을 보존하려면 주의가 필요하다 |
| CoplayDev/unity-mcp | https://github.com/CoplayDev/unity-mcp | 널리 쓰이는 MCP 서버. newtro/UnityPlugin이 Claude Code용 설치 플러그인으로 감싼다. 쓸 만하지만 이 저장소는 이미 배치 모드 CLI 검증 경로가 있어 꼭 필요하지는 않다 |
| ArkTarusov/unity-cli-plugin | https://github.com/ArkTarusov/unity-cli-plugin | MCP 없이 Unity CLI만 쓰는 SKILL.md 묶음. 이 저장소의 배치 모드 작업 방식과 가장 가깝다 |
| unity-xr(nice-wolf-studio/unity-claude-skills) | https://skills.sh/nice-wolf-studio/unity-claude-skills/unity-xr | Unity 6.3 LTS 문서 기반 OpenXR·Quest 설정 스킬. 리그와 입력 프로필을 점검할 때 참고할 만하다(내용 미검증) |
| xr-interface-architect(OpenRoster-ai/awesome-agents) | https://tessl.io/registry/skills/github/OpenRoster-ai/awesome-agents/xr-interface-architect | 공간 UI 배치와 편안 영역 임계값, XRI 예제. 이 문서의 기준 표와 겹친다. 수치의 출처는 확인하지 않았다 |
| vr-ar(davila7/claude-code-templates) | https://vibehackers.io/claude-code/skills/vr-ar-davila7 | 짧은 원칙 모음(편안함, 프레임). 이 문서보다 얕다 |

이미 쓰는 `ui-ux-pro-max`(G44)는 웹 규칙을 VR 각도로 옮겨 썼다. VR 고유 기준(시선 각도, 컴포지터 레이어, hover 상태)은 이 문서로 보완한다.

## 6. 출처

1차(직접 열어 확인):
- Microsoft, Typography — https://learn.microsoft.com/en-us/windows/mixed-reality/design/typography
- Microsoft, Text in Unity — https://learn.microsoft.com/en-us/windows/mixed-reality/develop/unity/text-in-unity
- Microsoft, Comfort — https://learn.microsoft.com/en-us/windows/mixed-reality/design/comfort
- Microsoft, Interactable object — https://learn.microsoft.com/en-us/windows/mixed-reality/design/interactable-object
- Apple, HIG Spatial layout — https://developer.apple.com/design/human-interface-guidelines/spatial-layout
- Android XR, Scale, sizes, and visual design — https://developer.android.com/design/ui/xr/guides/visual-design
- Meta, Horizon Typography — https://developers.meta.com/horizon/design/styles_typography/
- Meta, Comfort — https://developers.meta.com/horizon/design/comfort/
- Meta, OS compositor layers(Unity) — https://developers.meta.com/horizon/documentation/unity/os-compositor-layers
- Meta, Panels·Layouts — https://developers.meta.com/horizon/design/panels/ , https://developers.meta.com/horizon/design/styles_layouts/ (dp 크기만 있고 거리와 각도 수치는 없음)
- Kojić, T. 외(2020). User Experience of Reading in Virtual Reality — Finding Values for Text Distance, Size and Contrast. QoMEX 2020. https://arxiv.org/abs/2004.01545
- Alexandrovsky, D. 외(2020). Examining Design Choices of Questionnaires in VR User Studies. CHI '20. doi:10.1145/3313831.3376260 — 연구실 요약 https://openlab.ncl.ac.uk/research/examining-design-choices-for-questionnaires-in-vr-user-studies
- Unity, Official Unity Plugin for Claude Code — https://unity.com/blog/unity-plugin-for-claude-code

2차(검색 요약이나 다른 논문의 인용으로만 확인):
- Dingler, T., Kunze, K., Outram, B.(2018). VR Reading UIs: Assessing Text Parameters for Reading in VR. CHI EA '18. doi:10.1145/3170427.3188695 (Kojić 2020의 인용)
- Putze, S. 외(2020). Breaking The Experience: Effects of Questionnaires in VR User Studies. CHI '20. doi:10.1145/3313831.3376144 — https://openlab.ncl.ac.uk/research/breaking-the-experience-effects-of-questionnaires-in-vr-user-studies
- Gu, Bao(2024). OST-HMD 한자 글자 크기(가독성·시각 피로). *Ergonomics*. doi:10.1080/00140139.2024.2369205 (원문 접근 403)
- Hsiao 외(2024). 광학 HMD 한자 인식 시각도 임계값. *Behaviour & Information Technology* 43(4) 749–763
- Alger, M.(2015). Visual Design Methods for Virtual Reality — https://www.scribd.com/document/353031068/VisualDesignMethodsforVR-MikeAlger (원문 미열람)
- Meta, Quest 3 디스플레이 25 PPD — https://www.meta.com/blog/vr-display-optics-pancake-lenses-ppd/
- Meta, MR design guideline(약 1 m, 시선보다 조금 아래) — https://developers.meta.com/horizon/design/mr-design-guideline/
- Google Fonts Knowledge, Introducing AR/VR — https://fonts.google.com/knowledge/using_type_in_ar_and_vr/introducing_ar_vr
- Unity XR Interaction Toolkit, UI interaction setup — https://docs.unity3d.com/Packages/com.unity.xr.interaction.toolkit@3.0/manual/ui-setup.html
- Safikhani, S. 외(2021). The Influence of in-VR Questionnaire Design on the User Experience. VRST '21 (본문 미열람)

찾지 못한 것: Google "Designing Screen Interfaces for VR"(I/O 2017)의 본문별 dmm 권장값(Kojić 2020은 제목 32 dmm, 머리글 40 dmm만 인용함), HMD 한글 가독성 실험, Meta가 공개한 패널 거리·각도 수치.
