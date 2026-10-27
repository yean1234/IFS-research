# IFS 지식 → 시스템 반영

이 문서는 챗봇이 "단순 대화형"이 아니라 IFS 연구용 면담이 되도록 넣은 지식을 정리합니다.
어떤 개념이 코드·문구·사전 어디에 들어갔는지, 무엇을 일부러 하지 않는지를 함께 적습니다.

## 1. 핵심 개념과 쓰이는 곳

| IFS 개념 | 뜻 | 이 시스템에서 |
| --- | --- | --- |
| **Part(부분)** | 마음의 하위 인격. 생각·감정·신체감각·이미지·소리로 경험된다(IFS Institute, Model Outline). | 면담이 끌어내는 대상. Find 첫 답을 다섯 양식(신체감각·감정·생각·이미지·소리)으로 표시해 연구자에게만 보인다(`capture.findModality`). 이미지가 안 떠올라도 정상이며 '잘 모르겠어요'는 압박하지 않고 넘어간다. |
| **Self(참자기)** | part와 다른 층위의 중심. 호기심·연민 등 8C(calm, curiosity, compassion, confidence, courage, clarity, creativity, connectedness)를 지닌다. | 면담자는 판단 없는 호기심의 태도를 질문 틀로만 보인다(공감·해석·조언 금지). Self 상태 확인(Feel toward)은 VR 고정 문구로 하고 챗봇은 하지 않는다. |
| **보호자(관리자·소방관)** | 추방자의 고통이 올라오지 않게 미리 관리하거나(관리자) 터지면 급히 끄는(소방관) part. | 설문·면담이 잡는 것은 대개 보호자다. 6F는 추방자에 다가가기 전 보호자와 관계 맺는 준비 과정이라 연구 범위가 이 수준에 머문다. |
| **추방자** | 상처·수치·두려움을 지닌 어리고 취약한 part. | **범위 밖.** 기억·외상 서사 표지(어릴 때, 그때 …, 망신, 혼났 …)가 나오면 그 턴은 LLM 대신 고정 문구 `depth_present`로 지금 떠오른 것에 머물게 하고, 두 번째부터 확인 문구와 연구자 알림을 낸다(L5). 그 발화 속 말은 인용 후보에서 빼고 검증기 V9가 막는다. |
| **짐(burden)** | part가 떠안은 극단적 신념·감정. 내려놓기는 임상 영역. | 다루지 않는다. 세션 안에서 짐·역할이 바뀐다고 주장하지 않는다. |
| **Blending / Unblending** | part에 휩쓸려 "내가 그 감정이다" / 분리돼 "나에게 그런 part가 있다". | Flesh out의 목적은 정확한 그림이 아니라 part를 Self와 구별되는 대상으로 세우는 것이다(설계 노트 §2). '웅크린 작은 나'처럼 꾸밈을 받은 '나'는 자기지칭(`selfReference`)으로 기록한다(blending 단서). VR에서는 거리 d(t)가 이 축이 된다. |
| **나쁜 part는 없다** | 모든 part는 보호 의도를 가진다. | 면담자는 형상에 'part·보호자·추방자·내면아이' 같은 이름을 붙이지 않는다(V6 `ifs_label`). 면담 문구에 '제거'·'고치기'를 쓰지 않는다. |
| **트레일헤드** | 몸의 압박·막힘·통증처럼 part로 들어가는 입구. | Find의 위치 질문(몸 안·표면·주변)과 신체부위어 사전 → `bodyRelation`. 감정 이름에서 위치를 추론하지 않는다. |
| **컨테인먼트** | part를 용기에 담아 잠시 거리를 두는 안정화 기법. | VR 종료 문구(`vrStages.containment`). 안전장치이면서 IFS 이론과 맞는다. |
| **양극화** | 두 보호자가 상충하는 전략을 씀(통제하는 관리자 vs 폭식하는 소방관). | 한계로 기록한다. 프롬프트가 어느 보호자를 잡을지 통제하지 못한다. |

## 2. 6F와 이 연구의 범위

| 단계 | 목적 | 표준 문구 (설계 노트 §2) | 이 시스템 |
| --- | --- | --- | --- |
| Find | part를 몸 안·위·주변에서 찾는다 | "그것이 몸 안에, 몸 표면에, 아니면 몸 주변에 있나요?" | 고정 오프닝 → 위 문구 그대로(고정) → 조건 2에서 LLM 후속 최대 1회 |
| Focus | 주의를 두고 머문다 | "거기에 주의를 두고 잠시 머물러 보세요." | 고정 문구. VR에서는 호흡에 맞춘 환경 맥동 |
| Flesh out | 모습을 구체화해 unblending을 돕는다 | "어떻게 보이나요? 몇 살쯤 되어 보이나요? 무엇을 하고 있나요?" | 조건 2: LLM clean 질문 최대 5회 + 고정 차원 프로브. 나이·행동 질문은 쓰지 않는다(사람 형상을 전제하고 추방자 쪽으로 이끈다). 조건 1: 비시각 경험도 받는 고정 질문 하나 |
| Feel toward | Self-energy를 잰다(“Self의 가이거 계수기”) | "지금 그 part에 대해 당신은 어떻게 느끼나요?" | VR 고정 문구. 혐오·두려움·짜증이면 아직 blended, 호기심·연민이면 Self 쪽(연구자 해석용) |
| beFriend | 역할·내력을 알아 간다 | "역할이 무엇인가요? 언제부터 그 일을 해왔나요?" | 범위 밖('언제부터'는 과거 질문) |
| Fears | 멈추면 무엇이 걱정되는지 | "그 일을 멈추면 무슨 일이 생길까 걱정되나요?" | 범위 밖 |

## 3. 왜 Clean Language 질문 틀인가

- 면담자가 자기 은유를 끼워 넣지 않고 참여자의 말만 써서 묻는 기법이다(Tosey, Lawley & Meese, 2014). IFS의 Flesh out(형상의 모습을 참여자 말로 펼치기)과 목적이 같다.
- 질문 틀 6개는 Clean Language 기본 질문의 한국어 판이다(`shared/protocol`의 `cleanLanguage` 필드).

| 틀 | 한국어 | Clean Language |
| --- | --- | --- |
| anything_else | '{X}'에 대해 더 있나요? | And is there anything else about X? |
| what_kind | 그 '{X}'은(는) 어떤 '{X}'인가요? | And what kind of X is that X? |
| where | 그 '{X}'은(는) 어디쯤 있나요? | And where is X? |
| like_what | 그 '{X}'은(는) 마치 무엇 같나요? | And that's X like what? |
| relationship | '{X}'와(과) '{Y}' 사이에는 어떤 관계가 있나요? | And what's the relationship between X and Y? |
| then_what | 그리고 그다음에는 어떻게 되나요? | And then what happens? |

- 고정 차원 프로브 "그것에 크기나 모양이 있나요?"는 Clean Language Level-1 지침의 "And does it have a size or a shape?"와 같은 꼴이다. 값을 주지 않는 속성 질문이지만 새 차원을 여는 것만으로 약한 유도가 되므로, LLM이 아니라 모든 참여자에게 같은 순서의 고정 문구로 묻는다(표준화 면담 원칙, Fowler & Mangione, 1990).
- 유도 질문의 효과: 동사 하나만 바꿔도 없던 기억이 생긴다(Loftus & Palmer, 1974). 그래서 질문이 나가기 전에 코드가 검사한다.
- 평가에 쓸 수 있는 틀: Cairns-Lee, Lawley & Tosey(2021)의 질문 깨끗함 등급(Classically Clean · Clean Repeat · Contextually Clean · Mildly Leading · Strongly Leading). 세션 로그의 질문을 이 등급으로 사람이 코딩하면 검증기의 자동 판정과 비교할 수 있다.

## 4. 「앞으로 개발 방향」의 질문 — 음성 오프닝에 참고할 IFS 임상 자료가 있나?

조사 결과(2026-10, 웹 원문 확인):

- **발표된 IFS 임상시험은 참여자에게 읽어 준 오프닝 대본을 싣지 않는다.** 류마티스 관절염 RCT(Shadick et al., 2013)는 회기 주제만, 온라인 집단 IFS 연구(Comeau et al., 2024; Ally et al., 2025; PARTS RCT, Joss et al., 2026)는 커리큘럼 제목만 공개했다. Hodgdon et al.(2022)의 PTSD 연구는 대면 개인 회기 16회(90분)였다.
- **글자 그대로의 문구가 있는 곳은 치료자 지침과 Schwartz의 안내 명상이다.**
  - 치료자 지침: "FIND the part in, on, or around the body … FOCUS on it … FLESH it out. Can you see it? If so, how does it look? If not, how do you experience it?" (Anderson, IFS Skills Training Manual 계열의 6-step 글, PESI/therapist.com)
  - Schwartz의 안내 명상(Insight Timer, Huberman Lab 2025, Tim Ferriss Show #492): 숨 고르기 → 한 part를 떠올리기 → "where do you find it?" → 몸 안이나 주변에서 찾기, 그리고 "찾지 못해도 괜찮다"는 탈출구. 다만 모두 저작권 표시(All rights reserved)가 있어 그대로 옮겨 쓰면 안 된다. 구조만 참고해 우리 문구를 새로 써야 한다.
- **이 저장소의 선택**: 오프닝은 노션 고정 문구(“너무 힘들지 않은 정도로 …”)를 그대로 쓰고, 위치·머물기는 설계 노트의 6F 표준 한국어 문구를 쓴다. 비시각 경로("보이지 않는다면 어떻게 경험되나요")는 조건 1의 Flesh out 고정 질문에 반영했다.
- **IRB**: 생명윤리법 제15조는 사람 대상 연구에 사전 IRB 심의를 요구한다. 면제도 위험이 미미한 경우에 한해 심의 절차로 받는다. SCI 저널은 소급 승인을 받지 않는다(노션 로드맵). 고정 문구(`status: draft` 포함)와 위기 대응 절차는 IRB 제출물에 들어가야 한다.

## 5. 안전 근거

- **비임상·보호자 수준**: IFS 연구들은 정신증, 양극성 장애 I형·조증, 급성 자살 위험, 중증 우울, 최근 자해로 인한 입원, 중증 성격장애, 중등도 이상 물질 사용 장애를 제외했다. 파일럿 선별(L0)에 참고한다. PHQ-9는 선별 관문으로만 쓰고 결과 지표로 쓰지 않는다.
- **위기 대응을 LLM에 맡기지 않는다**: 최신 모델도 위기 상황에서 부적절하게 반응했다는 보고가 있다(Moore et al., FAccT 2025).
- **몸 은유 오탐**: 심상 묘사에는 "숨이 막힌다", "터질 것 같다"가 흔하다. 명확한 의도 표현만 위기 대응, 은유·모호 표현은 확인 문구로 나눈다. 같은 표현에는 확인 문구를 한 번만 낸다.
- **국내 상담 번호(2026년 기준)**: 자살예방상담전화 **109**(2024-01-01부터 1393을 통합·대체), 정신건강위기상담전화 **1577-0199**(24시간), 문자 상담 '마들랜', 청소년상담 1388, 긴급 119. 1393은 쓰지 않는다.
- **잘 반영된 형상이 꼭 편하지는 않다**: 2D 연구에서 Best 투표가 가장 많던 이미지가 편안함 점수는 가장 낮았다. 렌더 뒤 확인 문구와 컨테인먼트가 필요하다.

## 참고문헌

- Anderson, F. G., Sweezy, M., & Schwartz, R. C. (2017). *Internal Family Systems Skills Training Manual*. PESI.
- Anderson, F. G. 6 Step IFS Therapy Process to Jumpstart Healing. PESI / therapist.com.
- Cairns-Lee, H., Lawley, J., & Tosey, P. (2021). Enhancing researcher reflexivity about the influence of leading questions in interviews. *Journal of Applied Behavioral Science*.
- Fowler, F. J., & Mangione, T. W. (1990). *Standardized Survey Interviewing*. Sage.
- Geiecke, F., & Jaravel, X. (2024). Conversations at scale: Robust AI-led interviews with a simple open-source platform.
- Hodgdon, H. B., et al. (2022). Internal Family Systems (IFS) therapy for posttraumatic stress disorder among survivors of multiple childhood trauma. *Journal of Aggression, Maltreatment & Trauma*.
- IFS Institute. The Internal Family Systems Model Outline.
- Loftus, E. F., & Palmer, J. C. (1974). Reconstruction of automobile destruction. *Journal of Verbal Learning and Verbal Behavior*.
- Moore, J., et al. (2025). Expressing stigma and inappropriate responses prevents LLMs from safely replacing mental health providers. FAccT.
- Schwartz, R. C., & Sweezy, M. (2020). *Internal Family Systems Therapy* (2nd ed.). Guilford.
- Shadick, N. A., et al. (2013). A randomized controlled trial of an internal family systems-based psychotherapeutic intervention on outcomes in rheumatoid arthritis. *Journal of Rheumatology*, 40(11), 1831–1841.
- Tosey, P., Lawley, J., & Meese, R. (2014). Eliciting metaphor through Clean Language. *British Journal of Management*, 25(3), 629–646.
- 노션: 「IFS 이론이란?」, 「교수님 공유 자료」 설계 노트(2026-10-06), 「선행연구 정리」, 「학회 발표 준비」, 「인터렉션 디벨롭」.
