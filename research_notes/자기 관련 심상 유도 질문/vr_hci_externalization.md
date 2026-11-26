# VR/HCI 외재화 연구의 내용 유도 방식과 윤리 처리 (비임상 참여자 중심)

조사일 2026-11-24. 각 항목에 읽은 범위를 붙였다.
- [full text read]: 본문을 직접 내려받아 해당 문장을 확인했다.
- [abstract only]: 초록이나 서지 정보만 확인했다.
- [secondary source]: 다른 논문이 그 연구를 설명한 내용이다.
- [not found]: 찾지 못했다.

영어 인용은 원문에서 직접 확인한 문장만 넣었다.

---

## 1. Shigyo, Cao, Takahira, Fan & Qu 2024, "VR-Mediated Cognitive Defusion" (ACM MM '24)

### Takeaway
본문을 열지 못했다. ACM DL은 자동 접근을 막고, HKUST 저장소 레코드에도 본문 파일이 없으며, OpenAlex와 Semantic Scholar는 모두 closed로 표시한다. 그래서 선택 지시문, 선별 기준, 윤리 문장은 확인하지 못했다. 초록으로 확인한 사실은 비임상 20명, VR군과 심상(mental imagery)군의 비교, 생각을 "tangible objects"로 만들어 표면에 옮겨 두는(transpose) 상호작용까지다. "Healy et al. (2008) 목록에서 골랐다"는 전제는 이번 조사에서 검증하지 못했다.

### Cited Findings
- 저자와 소속: Kento Shigyo, Yifan Cao, Kentaro Takahira(HKUST), Mingming Fan(HKUST Guangzhou), Huamin Qu(HKUST). [abstract only] — [OpenAlex](https://api.openalex.org/works/doi:10.1145/3664647.3681504)
- 오픈 액세스 상태: "oa_status: closed", "any_repository_has_fulltext: False". HKUST 저장소 레코드(1783.1-147100)에는 DOI 링크만 있고 본문 파일은 없다. [abstract only] — [OpenAlex](https://api.openalex.org/works/doi:10.1145/3664647.3681504); [HKUST Repository](http://repository.hkust.edu.hk/ir/Record/1783.1-147100)
- 초록 원문 인용:
  - 설계 방법: "Using a co-design approach with clinicians and potential users of postgraduate students, we developed a VR system that materializes negative thoughts into tangible objects. This allows users to visually modify and transpose these objects onto a surface, facilitating mental detachment from negative thoughts."
  - 연구 설계: "In an evaluation study with 20 non-clinical participants, divided into VR and mental imagery groups, we assessed the impact of the cognitive defusion exercise on their perception of negative thoughts and psychological measures using standardized questionnaires."
  - 결과: "significant enhancements in negative thought perception and mental detachment from negative thoughts exclusively in the VR group, whereas the mental imagery group did not demonstrate significant changes."
  - 동기: "the challenge of maintaining vivid imagery diminishes their therapeutic effectiveness."

  [abstract only] — [HKUST Repository](http://repository.hkust.edu.hk/ir/Record/1783.1-147100); [Semantic Scholar API](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3664647.3681504)
- 참고: Healy et al. (2008)은 비임상 학부생 60명에게 사전 평정된 부정 자기진술 10개를 화면에 제시했다. 참여자가 고른 것이 아니라 연구자가 정해 보여 준 방식이다. 목록과 선정 근거는 6번에 정리했다. Shigyo 연구가 이 목록을 실제로 썼는지는 확인하지 못했다. [full text read: Healy 2008] — [Healy et al. 2008, Maynooth repository](https://mural.maynoothuniversity.ie/id/eprint/4954/1/YBH_experimental%20test.pdf)

### Inferences
- 초록에 "materializes negative thoughts into tangible objects"와 "transpose these objects onto a surface"가 함께 나온다. 우리 과제의 "형상화 → 나와의 거리에 배치" 흐름과 가장 가까운 선행 연구다. 결과 변수 이름도 "mental detachment"라서 거리·탈중심화 측정과 바로 이어진다.
- 대조군이 "mental imagery" 조건이므로, 같은 내용을 머릿속으로만 떠올리게 하는 조건을 우리 비교 조건으로 그대로 가져올 수 있다.

### Gaps
- 선택 지시문 원문, Healy 목록 사용 여부, 선별·제외 기준, 윤리 승인 문장, 쓴 척도 이름(SMQ? DDS? TMS?)을 확인하지 못했다. 본문 PDF가 필요하다. 기관 계정으로 ACM DL에 접근하거나 저자에게 요청해야 한다.
- 제1저자 Kento Shigyo의 HKUST 박사논문은 검색에서 나오지 않았다. arXiv에도 이 논문의 사본은 없다(arXiv API 저자 검색 결과에 없음).

---

## 2. Prudenzi et al. 2019 (Virtual Reality 23(2):179–185, doi:10.1007/s10055-018-0372-1)

### Takeaway
본문은 유료라 읽지 못했다. 초록으로 확인한 사실은 다음과 같다. 대상은 "negative self-referential thought (e.g., 'I am a failure')"이고, 30명을 defusion VR과 control VR에 무작위 배정했으며, state defusion과 생각 평정을 사전·사후에 쟀다. Bell et al. 2025에 따르면 표본은 비임상 젊은 성인이고, Negative Thought Assessment(NTA) 계열 절차로 참여자가 직접 부정적 생각을 만들어 냈다. 다만 이것은 2차 출처다.

### Cited Findings
- 초록 원문 인용:
  - 연구 대상: "The current study examined the impact of a VR task as a cognitive defusion technique on participants' relationship with a negative self-referential thought (e.g., 'I am a failure')."
  - 배정: "Thirty participants were randomly assigned to one of two conditions (i.e., defusion VR and control VR)."
  - 측정: "Participants were tested pre- and post-VR task on a state measure of cognitive defusion and ratings of their self-referential negative thought."
  - 결과: "a defusion VR task facilitates the management of negative thoughts and leads to an increase in state defusion."

  [abstract only] — [Springer](https://link.springer.com/article/10.1007/s10055-018-0372-1)
- 초록의 배경 문장에는 디퓨전이 "getting some distance from their thoughts"로 정의되어 있다(원문: "Cognitive defusion techniques undermine potential negative effects of thinking by teaching clients to get some distance from their thoughts."). [abstract only] — [Springer](https://link.springer.com/article/10.1007/s10055-018-0372-1)
- Bell et al.의 설명: "investigated a VR-based cognitive defusion task in a nonclinical sample of young adults and found that the task reduced the believability and discomfort associated with negative thoughts". 대조군은 "a nondefusion VR control"이다. [secondary source] — [Bell et al. 2025, Europe PMC full text](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12371279/fullTextXML)
- Bell et al.은 NTA를 Prudenzi[30] 등 선행 연구가 쓴 절차라고 소개한다. NTA는 "prompts respondents to generate and reflect on a particular negative thought that they identify as upsetting, find hard to stop thinking about, or bothers them a lot". Bell은 여기에 "One item used in the study by Prudenzi et al [30] was added to measure the degree of negativity of the thought ('How negative is the thought?')"라는 문항을 더했다. [secondary source] — [Bell et al. 2025](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12371279/fullTextXML)

### Inferences
- Prudenzi의 유도 대상은 "괴롭고 멈추기 어려운 부정적 자기 관련 생각"이었을 가능성이 높다. NTA 계열 절차이고 Masuda et al. 2004 패러다임을 따랐다는 점에서 그렇게 추정한다. 우리 과제의 "트라우마·증상·고통스러운 기억을 건드리지 않는다"는 조건보다 강도가 높은 범주다.

### Gaps
- 실제 지시문 원문, control VR의 내용, 윤리 승인 문장, 표본 연령과 성별은 본문을 열지 못해 확인하지 못했다. contextualscience.org 페이지와 iris.unikore.it 레코드에도 PDF 링크가 없었다.

---

## 3. Bell et al. 2025, JMIR Mental Health 12:e70160 (VR cognitive defusion app, 청소년·임상 표본)

**[임상·청소년 표본]** headspace(호주 청소년 정신건강 서비스)의 현재·과거 이용자 16–25세이고, PHQ-8 또는 GAD-7 점수가 10점 이상이다. 비임상 성인 연구가 아니다.

### Takeaway
[full text read]. Europe PMC 전문 XML로 읽었다. 지시는 "최근 자신을 괴롭힌 부정적 생각"을 고르게 하는 방식이었다(Masuda 프로토콜의 rumination induction). VR 안에서는 그 생각을 직접 입력하거나 미리 채워 둔 문장 중에서 고르게 했다. 20명 중 1명이 VR에서 고통을 겪어 중단을 요청했다. 저자들은 VR로 생각을 너무 직접 외재화하면 생각과 내적 표상의 연결이 끊길 수 있다는 해석을 내놓고, 다음 버전의 표적을 "decentering"으로 잡자고 제안한다.

### Cited Findings
- 생각 선택 지시:
  - "Following the protocol by Masuda et al [21], before each exercise, a brief rumination induction procedure took place in which participants were prompted to choose and reflect on a negative thought that had been distressing them recently and keep this in mind during the exercises."
  - NTA의 지시: "prompts respondents to generate and reflect on a particular negative thought that they identify as upsetting, find hard to stop thinking about, or bothers them a lot."

  [full text read] — [Bell et al. 2025 (Europe PMC)](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12371279/fullTextXML)
- VR 안에서의 외재화:
  - 장면 선택: "Participants were encouraged to choose the environment in which they felt that their negative thoughts were most likely to occur."
  - 객체 제시: "they were faced with an animated object and instructed to imagine this as representing the thought they had been struggling with. They were then guided to customize the thought by typing it in using a virtual keyboard presented to them within the scene or selecting from prefilled thought prompts (eg, 'I'm going to fail,' 'I am being judged,' or 'I am a bad person')."
  - 조작 방식: 모양과 색 바꾸기, 집어서 옮기기, 위로 띄우기, 터뜨리기와 던지기 게임.

  [full text read] — 같은 출처
- 대조 조건(audio): "The voice instructed the listener to identify a target negative thought and think about it in different ways, such as imagining their thought as having different colors, shapes, forms, and contexts." [full text read] — 같은 출처
- 표본과 선별:
  - 포함 기준: "(1) aged between 16 and 25 years, (2) normal or corrected-to-normal vision and hearing, (3) clinical levels of depression or anxiety (score of ≥10 on the 8-item Patient Health Questionnaire [PHQ-8] [36] or 7-item Generalized Anxiety Disorder scale [GAD-7] [37]), (4) high levels of repetitive negative thinking (RNT; score of ≥15 on the Brief Penn State Worry Questionnaire (Brief PSWQ) or ≥9 on the Brief Ruminative Response Scale (Brief RRS) [38]), and (5) sufficient command of the English language."
  - 제외 기준: "(1) inability to provide informed consent, (2) history of photosensitive epilepsy or previous experience of severe simulator sickness, and (3) being a psychiatric inpatient or under the care of a mental health crisis team."
  - 선별 절차: 전화로 적격성을 확인했다.
  - 표본: N=20, 평균 20.95세(SD 2.74).

  [full text read] — 같은 출처
- 윤리 문장 원문: "This project was approved by the University of Melbourne Human Research Ethics Committee (ID 2056403.1). Participants provided written informed consent. All participants received a full explanation of the study in lay terms related to the aims, study procedures, and potential risks and benefits in taking part before providing informed consent. The participants were reminded that they could withdraw from the study at any time without prejudice." 18세 미만은 "additional parent or guardian consent"를 받았다. [full text read] — 같은 출처
- 위험 관리:
  - 사전 고지: "Participants were informed at the start that they could stop the exercise at any time if they became distressed or uncomfortable." 오디오 조건에서는 연구자가 같은 방에 있었다("remaining in the room to monitor for any signs of distress").
  - 이상 사례: "One young person experienced some distress during the VR exercise and requested to stop. This participant found the experience of manifesting a distressing thought in VR confronting ... They were contacted the following day and reported no persisting discomfort or distress."
  - 다른 참여자 반응: "thinking about the thought was quite distressing, but it was also helpful with the interactive bit" (participant 94).

  [full text read] — 같은 출처
- 결과 척도:
  - NTA: discomfort, believability ("How accurate or true do you think the thought is?"), importance, negativity. 0–10 VAS.
  - State Cognitive Defusion Questionnaire(SCDQ, 7문항).
  - Toronto Mindfulness Scale–State: decentering과 curiosity 하위척도. 원문 정의는 "Decentering refers to psychological distance from thoughts".
  - 그 밖에 BSRI, POMS-A, SUDS, ITC-SOPI, 자체 14문항 UX 질문지.
  - VR 조건 결과: discomfort, cognitive defusion, state anger가 유의하게 개선됐다. 효과크기는 audio 조건이 더 컸다.

  [full text read] — 같은 출처
- "너무 직접적인 외재화"에 대한 저자 해석: "By externalizing the thought so directly, individuals may have lost the connection between the internal representation of their thought and, instead, related to the object as an external entity, thus losing the level of focus and mental manipulation required for successful cognitive defusion. Furthermore, the gamification element may have counterproductively enabled participants to experientially avoid their negative thoughts". [full text read] — 같은 출처
- 표적 재설정 제안: "the application may be better positioned as a treatment targeting decentering as a core underlying mechanism rather than an adaptation of cognitive defusion." [full text read] — 같은 출처
- 개인화 요구: 장면이 3개뿐이어서 "there might be like some people that like don't really resonate with any three of them" (participant 72)라는 응답이 있었다. [full text read] — 같은 출처

### Inferences
- 비임상 성인에게도 "a negative thought that had been distressing them recently"를 고르게 하면 강도가 높을 수 있다. 임상 청소년 20명 중 1명이 중단했다. 우리 과제의 "임의의 지금 떠오르는 것보다 명확하되 고통 기억은 아닌" 표적을 정할 때 피해야 할 예로 쓸 수 있다.
- Bell의 해석은 IFS "Flesh out" 단계에 직접 적용된다. 객체가 "external entity"가 되면 자기와의 연결이 끊기고 회피가 생길 수 있다. 그러니 거리를 두더라도 "이것은 내 안의 무엇"이라는 연결을 유지하는 문구가 필요하다. 예를 들어 배치 후에 "저것을 보면서 지금 어떤가"처럼 되묻는 것이다. 배치 거리와 연결감을 함께 재는 설계가 이 해석과 맞는다.
- 거리나 탈중심화를 측정하려면 TMS-State의 decentering 하위척도, SCDQ, NTA의 believability와 discomfort 문항을 후보로 쓸 수 있다.

### Gaps
- Multimedia Appendix 1(오디오 스크립트, 디퓨전 설명 스크립트)의 원문은 읽지 않았다.

---

## 4. Mind Mansion (Rasch, Zender, Sakel & Wagener, DIS '24, arXiv 2406.04871)

### Takeaway
[full text read]. 참여자가 생각을 직접 만들어 내지 않았다. Automatic Thoughts Questionnaire(ATQ)의 30개 부정적 생각을 미리 정해 두고 VR 아파트 안의 사물(웅덩이, 창문, 베개, 쓰레기봉투, 풍선 등)에 글자로 붙였다. 선별은 정신적 안정과 정신질환 병력이 없음을 자기 확인하는 수준이었다. 윤리는 기관 윤리위원회 지침을 준수했다는 한 문장뿐이다. 저자들은 공통 목록이라서 공감하지 못하는 생각이 있었다는 한계를 직접 적었다.

### Cited Findings
- 생각의 출처:
  - "participants were confronted with 30 prechosen negative thoughts and engaged with them through metaphorical interactions."
  - "The negative thoughts featured in the VR experience were drawn from the Automatic Thoughts Questionnaire (ATQ) [57], consisting of a total of 30".
  - 사전 절차: "participants were presented with the ATQ to get familiar with the negative thoughts by reading and rating the negative thoughts on the accompanying scale."

  [full text read] — [arXiv 2406.04871](https://arxiv.org/pdf/2406.04871)
- 표본과 선별: "We recruited n = 30 participants (male:12, female:18, diverse:0) via social networks and our institution's email distributor for user studies, with an average age of 26 years ranging from 22 to 62 years. ... All participants were required to confirm their current mental stability and health." 동의 절차 문장은 "participants were asked to fill out a consent form, confirm they were without a history of mental illnesses, and complete a demographic survey."이다. [full text read] — 같은 출처
- 윤리 문장 원문: "We designed and conducted the user study in compliance with our institution's ethics committee guidelines." 승인 번호는 없다. [full text read] — 같은 출처
- 저자가 밝힌 한계와 위험:
  - 관련성: "received the same set of negative thoughts based on related work, making it harder for participants who did not relate to some thoughts to experience a shift in their emotions. Future studies could further explore the effect of similar tools when using personalized thoughts in the experiment."
  - 위험: "These interactions present a risk, especially for vulnerable users, when not guided by professionals".

  [full text read] — 같은 출처
- 결과 측정: 조건마다 VR 안에서 7점 Likert 문항(예: "Through This Interaction I Felt Engaged With the Thought")을 받고, VR 후 질문지와 반구조화 인터뷰(평균 5분)를 했다. PANAS는 약어 목록에만 나오고 본문 결과에는 보이지 않았다. [full text read; 척도 세부는 WebFetch 요약으로 확인] — [arXiv HTML](https://arxiv.org/html/2406.04871)
- 참여자 반응: "your thoughts [become] a concrete image that you can work with or touch" (P28). [full text read] — [arXiv 2406.04871](https://arxiv.org/pdf/2406.04871)

### Inferences
- 목록 방식은 위험을 확실히 줄이지만 관련성이 떨어진다. 저자들이 이 대가를 직접 보고했다. 우리 과제는 참여자 자신의 심상을 쓰기 때문에 이 한계를 피하지만, 그만큼 경계를 정하는 일을 문구가 맡아야 한다.
- 선별 수준은 "정신적 안정과 병력 없음의 자기 확인"이다. 최소 위험 HCI 연구에서 자주 쓰는 수준으로 보인다. MoodShaper도 비슷하다.

### Gaps
- ATQ 30문항 원문은 이 논문에 표로 있는지 확인하지 않았다.

---

## 5. Wagener 계열: MoodShaper (DIS '24), Mood Worlds (CHI '22), SelVReflect (CHI '23)

### Takeaway
[full text read: 세 편 모두 UCL Discovery 사본]. 세 연구 모두 Autobiographical Emotional Memory Task(AEMT)로 내용을 유도했다. 표적 범주는 연구마다 달랐다.
- Mood Worlds: 최근의 행복한 기억(긍정)
- SelVReflect: 이미 극복한 감정적 도전
- MoodShaper: 강한 부정 감정을 느낀 최근 상황

MoodShaper는 St. Gallen 윤리 승인 번호를 밝혔고, SelVReflect는 "UCL 사전 승인" 한 문장을 적었다. Mood Worlds 본문에서는 윤리 승인 문장을 찾지 못했다. 동의서를 받았다는 언급만 있다.

### Cited Findings
**MoodShaper (Wagener, Kiesewetter, Reicherts, Woźniak, Schöning, Rogers & Niess 2024)**
- 유도 지시(원문 그대로의 참여자 지시문은 본문에 없고, 절차 서술만 있다):
  - "a negative affective state was induced using the autobiographical emotional memory task (AEMT)[42] ... This mood-congruent procedure prompts participants to recall and write about recent situations, thereby increasing the likelihood of re-experiencing strong emotions [4, 60]. Participants followed the AEMT guidelines by describing a situation where they felt strong negative emotions."
  - 이어서 "They then returned to VR to create a world reflecting the emotions expressed in the AEMT."

  [full text read] — [UCL Discovery PDF](https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf)
- 경계와 안전 장치:
  - 행복 세계로 감싸기: 먼저 "a world representing happiness"를 만들게 했다. 원문은 "serving both as an exploration phase to get used to the controls and a way to end positively after the intervention ... This step also serves as an additional safety measure". 중재가 끝나면 "automatically returned to their previously created positive world"로 돌아갔다.
  - 위험 성찰: "5.2.5 Ambivalent Experiences" 절에서 다뤘다.

  [full text read] — 같은 출처
- 표본과 선별: "A total of N = 60 participants evaluated MoodShaper quantitatively, and N = 62 participants provided qualitative feedback (14 females, 46 males, 2 non-binary; M = 28 years, min: 20 years, max: 44 years)". 선별 문장 원문은 "Participation was voluntary and unpaid, and participants self-assessed mental stability. While our intended user group includes those struggling with mental health, we restricted participation in testing this prototype as a precaution due to our ethical responsibility." 모집은 지인 네트워크와 눈덩이 표집이었다. [full text read] — 같은 출처
- 윤리 문장 원문: "The study received prior ethics approval from the University of St. Gallen (HSG-EC-20220503)." [full text read] — 같은 출처
- 측정: PANAS, S-DERS, UEQ-S, UES-SF와 반구조화 인터뷰. 거리나 탈중심화 척도는 없다. [full text read] — 같은 출처
- 시각화 난이도와 강도에 대한 저자 보고:
  - 난이도: "Initially, participants faced greater challenges when attempting to visualise negative emotions compared to positive emotions, resulting in more abstract and complex representations. Hence, their negative worlds often reveal a mix of negative emotions".
  - 강도: "The process of visualising and being immersed in complex negative emotions induced strong emotional responses among participants. ... This self-induced encapsulation triggered physical reactions in some participants, leading to reported unease, tingling sensations, and heightened heart rates."

  [full text read] — 같은 출처

**Mood Worlds (Wagener et al., CHI '22)**
- 사전 연구(N=12, 아날로그 무드보드)의 지시: "Participants were asked to write about a recent experience that made them, depending on the randomised condition, angry, sad or happy so that others might feel the same by reading their text." [full text read] — [UCL Discovery PDF](https://discovery.ucl.ac.uk/10150739/1/Wagener-2022_Mood-Worlds_CHI.pdf)
- 본 연구의 지시: "To make it more approachable for participants, they were asked to recall a happy memory from their recent past, but we also welcomed incidental emotions sharing the same valence, such as excitement, satisfaction or awe [15] as we were striving to create general mood states instead of specific emotions". [full text read] — 같은 출처
- 표본: "N = 16 (6 females, 10 males) participants took part in the Mood Worlds study (M = 27 years, min: 18, max: 33) without receiving remuneration." 지인 네트워크와 눈덩이 표집으로 모았고 원격으로 진행했다. [full text read] — 같은 출처
- 윤리: 본문에 "ethic"이라는 단어가 없다. Google Form 안에 "a consent form"이 있었다는 언급만 확인했다. [not found: 윤리 승인 문장] — 같은 출처
- 측정: PANAS, Oxford Happiness Questionnaire, 인터뷰. [full text read] — 같은 출처
- 참여자 소감: "I also think it's kind of nice when you recall such a happy experience and reflect on it and then meditate on it for half an hour and visualise it a bit. ... But at the same time it was also short-lived." (P10) [full text read] — 같은 출처

**SelVReflect (Wagener, Reicherts, Zargham et al., CHI '23)**
- 유도 지시: "participants were asked to recall and write about an emotionally loaded challenge they had successfully overcome. This approach is based on the Autobiographical Emotional Memory Task (AEMT) [42]. Then, they created a representation of the challenge, its stages and the emotions attached to each stage using SelVReflect." [full text read] — [UCL Discovery AAM](https://discovery.ucl.ac.uk/id/eprint/10169979/1/Reicherts_A%20Guided%20VR%20Experience%20Fostering%20Reflection%20on%20Personal%20Challenges_AAM.pdf)
- 음성 가이드 문장 예:
  - 단계 구분: "Now think about the main stages of the challenge from the start until the end, when you ultimately overcame it. How many different stages or steps were there?"
  - 극복 행동: "Now, focus again on the actions and ideas that helped you overcome the challenge."
  - 상담 계열 질문: "What does (thinking of) this situation trigger in you?", "How does it feel what you are creating here?"
  - 완성 후: 다른 관점에서 둘러보도록 유도했다. 원문은 "nudge them to physically move around to look at their drawing from different perspectives".

  [full text read] — 같은 출처
- 실제로 나온 도전의 맥락은 studies, work, relationship, friends & family, university였다(표의 "Challenge Context" 열). [full text read] — 같은 출처
- 표본: N=20(설계 단계 N=5는 별도). 대부분 학생, 박사과정생, 연구 보조원이고 나이는 23–53세다. [full text read] — 같은 출처
- 윤리 문장 원문: "The study received prior ethics approval from University College London." [full text read] — 같은 출처
- 측정: PANAS, GSE(일반 자기효능감), Technology-Supported Reflection Inventory(TSRI), DOE-20(REPCOG와 COMEMO로 HI-EMO/LO-EMO 집단 구분), 인터뷰. [full text read] — 같은 출처
- 반추 위험에 대한 언급:
  - 결과: "We also found no evidence of rumination."
  - 한계: "the effects of using systems similar to ours for self-care approaches - in particular for unfinished challenges - remain unclear and need to be carefully researched ... They are concerned that negative feelings might increase when exposed to and immersed in strong negative emotions without professional guidance [87]".

  [full text read] — 같은 출처

### Inferences
- 같은 연구진 안에서 위험 수준을 다르게 잡은 범주가 보인다. 긍정 기억과 "이미 극복한 도전"은 반추 위험을 줄이려고 고른 범주이고(SelVReflect는 "unfinished challenges"를 위험 요인으로 명시했다), "강한 부정 감정을 느낀 최근 상황"(MoodShaper)은 신체 반응까지 보고됐다.
- 우리 과제처럼 "고통 기억을 건드리지 않되 '아무거나'보다 분명한" 표적을 찾는다면 SelVReflect식 경계가 가장 가깝다. 완료되었고, 일상 맥락(학업·일·관계)에 있고, 자기가 관여한 것이라는 세 조건이다. 다만 이것은 "기억" 회상이라서 우리 면담 원칙의 "과거·기억 질문 금지"와 충돌한다. 그래서 과거 사건이 아니라 "지금 자신 안에서 느껴지는 어떤 부분/모습"으로 바꿔 적용해야 한다.
- MoodShaper가 보고한 "부정 정서는 긍정보다 시각화하기 어렵고 추상적으로 된다"는 결과는, 부정 정서를 표적으로 하면 형상화 단계에서 막힐 수 있다는 근거다.

### Gaps
- 세 논문 모두 참여자에게 준 AEMT 지시문 원문(Google Form 문구)을 본문에 싣지 않았다. 보충 자료에 있을 수 있으나 확인하지 않았다.
- TU Wien reposiTUm에 MoodShaper VoR 사본이 있다(OpenAlex 위치 정보). 내용은 UCL 사본과 같을 것으로 보고 따로 열지 않았다.

---

## 6. 기타 외재화 연구 (Grieger 2021, Healy 2008, Masuda 2004 등)

### Takeaway
시간 제약으로 일부만 확인했다. Grieger et al. CHI EA '21은 서지만 확인했다. Healy 2008은 원문을 읽어 부정 자기진술 목록과 선정 근거를 얻었다. Affective Diary VR, ConVRSelf, emotion sculpting/physicalisation, "Anima", 바이오피드백 객체화 연구는 이번에 조사하지 못했다.

### Cited Findings
- Grieger, Klapperich & Hassenzahl 2021, "Trash It, Punch It, Burn It - Using Virtual Reality to Support Coping with Negative Thoughts" (CHI EA '21). researchr 목록에는 "Abstract is missing"으로 나온다. [abstract only: 서지만] — [researchr](https://researchr.org/publication/GriegerKH21)
- MoodShaper가 Grieger 연구를 설명한 문장: "They empower users to physically engage with personal negative text messages, allowing them to release frustration and transform their thoughts through punching and trashing those messages." 비판은 "their approach requires technical knowledge and focuses on specific negative thoughts instead of general everyday negative emotions."이다. [secondary source] — [MoodShaper PDF](https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf)
- Healy et al. 2008(Psychological Record 58:623–640):
  - 표본: 비임상 학부생 n=60, 18–57세. 원문은 "All participants were undergraduate students and were recruited through Faculty announcements in the Department of Psychology."
  - 자기진술 선정: "The 10 negative statements used in the study were rated the most negative from a larger pool, rated from 0 (extremely negative) to 20 (extremely positive); none of the 32 independent raters was thereafter recruited as an experimental participant."
  - 부정 목록: "I am a failure. My life is pointless. I am stupid. I am a bad person. I make a mess of everything. I am broken. I am ugly. I am helpless. Sometimes I wish I wasn't me. No-one will ever love me". 긍정 10개도 함께 썼다(예: "I love life", "I am whole").
  - 측정: Comfort, Believability, Willingness를 7점 척도로 받았다.
  - 윤리 문장은 발췌한 범위에서 보지 못했다.

  [full text read] — [Healy et al. 2008](https://mural.maynoothuniversity.ie/id/eprint/4954/1/YBH_experimental%20test.pdf)
- Healy 논문이 Masuda et al. 2004를 설명한 문장: "undergraduate students were asked to generate two self-relevant negative thoughts that they found particularly disturbing (e.g., 'I am too fat') and then to restate each thought in a single word". [secondary source] — 같은 출처

### Inferences
- Healy 목록에는 "Sometimes I wish I wasn't me", "My life is pointless"처럼 자살 생각이나 우울 증상에 가까운 진술이 들어 있다. 비임상 표본에 썼더라도 우리 과제의 "증상을 건드리지 않음" 기준에는 맞지 않는다. Shigyo 연구가 이 목록을 썼다면 같은 문제가 있다.
- 디퓨전 계열(Masuda, Healy, Prudenzi, Bell)의 기본 지시는 "particularly disturbing" 또는 "distressing" 수준을 요구한다. HCI 계열(Wagener)은 기억이나 경험 단위로 표적을 잡고 긍정이나 극복한 일로 위험을 낮춘다. 두 계열이 갈린다.

### Gaps
- Affective Diary, ConVRSelf, emotion physicalisation, "Anima", 바이오피드백 객체화 연구의 지시문과 윤리 문장은 조사하지 못했다. 별도 조사가 필요하다.
- Grieger 2021의 "personal negative text messages"를 참여자가 어떻게 만들었는지, 윤리를 어떻게 처리했는지는 확인하지 못했다.

---

## 7. 연구 전반의 표적 범주와 "너무 강함·모호함·시각화 어려움" 보고

### Takeaway
연구들이 쓴 표적 범주는 다섯 가지다.
1. 사전 목록의 부정 자기진술: Healy 2008, Mind Mansion(ATQ), Bell의 미리 채운 문장. Shigyo는 확인하지 못했다.
2. 본인이 만든 괴로운 부정적 생각: Masuda 2004, Prudenzi 2019(추정), Bell 2025.
3. 강한 부정 감정을 느낀 최근 상황: MoodShaper, Mood Worlds 사전연구.
4. 이미 극복한 감정적 도전: SelVReflect.
5. 최근 행복한 기억: Mood Worlds 본 연구, MoodShaper의 감싸기 단계.

저자가 직접 문제를 보고한 경우는 세 가지다. 강도 문제는 Bell(1명 중단)과 MoodShaper(신체 반응)가, 관련성 문제는 Mind Mansion(목록이라 공감 못 함)이, 시각화 난이도 문제는 MoodShaper(부정 정서가 추상적이고 복합적으로 나옴)가 보고했다.

### Cited Findings
- 강도:
  - Bell: "This participant found the experience of manifesting a distressing thought in VR confronting". — [Bell 2025](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12371279/fullTextXML)
  - MoodShaper: "reported unease, tingling sensations, and heightened heart rates". — [MoodShaper](https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf)

  [full text read]
- 관련성: Mind Mansion은 "harder for participants who did not relate to some thoughts to experience a shift in their emotions"라고 썼다. [full text read] — [Mind Mansion](https://arxiv.org/pdf/2406.04871)
- 시각화 난이도: MoodShaper는 "participants faced greater challenges when attempting to visualise negative emotions compared to positive emotions, resulting in more abstract and complex representations"라고 썼다. [full text read] — [MoodShaper](https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf)
- 은유가 이해되지 않은 경우: Mind Mansion에 "some metaphors remained incomprehensible and, therefore, had no impact"라는 문장이 있다. [full text read, WebFetch 요약으로 확인] — [arXiv HTML](https://arxiv.org/html/2406.04871)
- 심상 유지의 어려움: Shigyo 초록에 "the challenge of maintaining vivid imagery diminishes their therapeutic effectiveness"가 있다. 순수 심상 조건의 약점으로 제시했다. [abstract only] — [HKUST Repository](http://repository.hkust.edu.hk/ir/Record/1783.1-147100)
- 외재화가 지나칠 때: Bell은 객체를 "external entity"로 대하면서 연결이 끊기고 경험 회피가 생길 수 있다고 해석했다. [full text read] — [Bell 2025](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12371279/fullTextXML)

### Inferences
- 범주를 위험 축(강도)과 명확성 축(구체성)으로 놓으면 이렇게 정리된다.
  - 목록형: 명확성은 높고 관련성은 낮다.
  - 괴로운 생각: 명확성도 높고 위험도 높다.
  - 최근 부정 상황: 위험이 높고 시각화가 어렵다.
  - 극복한 도전과 긍정 기억: 위험은 낮지만 "기억" 질문이다.

  IFS "Flesh out"에 맞추려면 "지금 내 안에서 느껴지는 한 부분(예: 자주 앞에 나서는 어떤 모습)"처럼 현재형이고, 자기 관련이며, 사건이 아닌 표적이 필요하다. 이런 표적을 직접 쓴 VR 선행연구는 이번 조사에서 찾지 못했다. 이 빈칸이 우리 연구의 기여 지점이 될 수 있다.
- 부정 정서는 시각화가 어렵다는 MoodShaper의 결과와 순수 심상은 생생함을 유지하기 어렵다는 Shigyo 초록을 합치면, 면담자가 모양·색·크기·위치를 참여자의 말로 하나씩 되물으며 구체화하는 단계가 필요하다는 근거가 된다.

### Gaps
- "too vague"(너무 모호함)를 직접 쓴 저자 보고는 찾지 못했다. MoodShaper의 "abstract and complex"가 가장 가까운 표현이다.

---

## 8. 윤리 면제(exempt)나 저위험 심사를 보고한 연구가 있는가

### Takeaway
확인한 논문 중 윤리 면제나 저위험 신속 심사를 명시한 곳은 없다. 윤리 처리는 세 수준으로 나뉜다.
- 번호가 있는 정식 승인: Bell(Melbourne HREC ID 2056403.1), MoodShaper(St. Gallen HSG-EC-20220503)
- 번호 없는 승인 언급: SelVReflect(UCL)
- 지침 준수 문장만 있음: Mind Mansion

Mood Worlds는 윤리 문장을 찾지 못했다. 위험을 낮춘 근거로는 비임상 자기 확인 선별, 긍정 세계로 감싸기, 극복한 도전으로 범주 제한, 중단 권리 고지가 쓰였다.

### Cited Findings
- Bell: "approved by the University of Melbourne Human Research Ethics Committee (ID 2056403.1)". [full text read] — [Bell 2025](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12371279/fullTextXML)
- MoodShaper: "prior ethics approval from the University of St. Gallen (HSG-EC-20220503)". 선별 근거로 "we restricted participation in testing this prototype as a precaution due to our ethical responsibility"라고 적었다. [full text read] — [MoodShaper](https://discovery.ucl.ac.uk/10194135/1/_DIS24__Mood_Shaper_Wagener.pdf)
- SelVReflect: "The study received prior ethics approval from University College London." [full text read] — [SelVReflect AAM](https://discovery.ucl.ac.uk/id/eprint/10169979/1/Reicherts_A%20Guided%20VR%20Experience%20Fostering%20Reflection%20on%20Personal%20Challenges_AAM.pdf)
- Mind Mansion: "We designed and conducted the user study in compliance with our institution's ethics committee guidelines." [full text read] — [Mind Mansion](https://arxiv.org/pdf/2406.04871)
- Mood Worlds: 윤리 문장 없음, 동의서만 언급. [not found] — [Mood Worlds](https://discovery.ucl.ac.uk/10150739/1/Wagener-2022_Mood-Worlds_CHI.pdf)
- Shigyo와 Prudenzi: 본문을 열지 못해 확인하지 못했다. [not found]

### Inferences
- VR 외재화 연구에서 "면제"를 근거로 든 선례는 이번 범위에서 없었다. 부정 정서나 부정 생각을 다루는 연구는 비임상 표본이어도 정식 승인을 받는 쪽이 관행으로 보인다. 저위험 주장을 하려면 다음 조합이 선행 연구에서 쓰인 근거와 겹친다.
  - 표적을 부정 정서나 괴로운 생각에서 떼어 낸다.
  - 사건·기억 회상을 쓰지 않는다.
  - 정신 안정과 병력 없음을 자기 확인한다.
  - 중단 권리를 고지한다.
  - 긍정적이거나 중립적인 마무리 단계를 둔다.
- 참고: 프로젝트 메모상 현재 방향은 IRB 없이 합성 데이터로 시스템과 측정 논문을 쓰는 것이다. 위 내용은 실제 참여자 연구로 넘어갈 때의 비교 근거로 쓴다.

### Gaps
- 기관별 면제 기준(예: 국내 생명윤리법상 심의 면제 요건)과 이 연구들을 대조하는 일은 이번 범위 밖이다.
