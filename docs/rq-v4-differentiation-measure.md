# RQ V4 "구별하기(unblending)" 측정 조사와 지표 설계 초안 (2026-11-23)

> 이 문서는 팀이 확정하기 전의 초안입니다. 아래의 한국어 문항·지시문·고정 문구는 모두 `status: draft`이며 IRB 대상입니다(AGENTS.md 원칙 7). 확정하면 `shared/protocol/`로 옮기고 출처와 함께 프로토콜 버전을 올립니다.
> 함께 읽을 문서: docs/rq-v4-questionnaire-draft.md(이하 "설문 초안", 문항 ID A·B·M·S), docs/rq-v4-lit-check.md 부록 C·D, docs/ifs-knowledge.md.
> 확인 수준 표기: [전문] 본문을 직접 열어 해당 부분을 읽음 / [전문 일부] 본문 일부만 읽음 / [초록만] / [2차 자료] 다른 문헌이나 검색 요약으로만 확인 / [못 찾음]. "(이전 작업)"은 설문 초안·부록 C에서 이미 확인한 것이라 이번에 다시 열지 않았다는 뜻입니다.

---

## 0. 결론 요약

1. **지금 설계에 있는 것**: 주 척도 A(CFQ-7 상태판)는 Bernstein 외(2015)의 틀에서 보면 "사고 내용에 대한 반응성(휩쓸림)"을 잽니다. 그 밖에 거리감(S1·S2), 겹침 그림(S3), 접근·회피(S5·S6), 정서가(S8)가 있습니다.
2. **비어 있는 것**: "그것 ≠ 나 전체"를 바로 묻는 탈동일시 문항과, 그것을 너그럽게 대하는지 밀어내는지를 묻는 태도 문항(Feel toward)이 없습니다. 놓은 거리만으로는 회피와 "거리를 둔 관찰"을 가를 수 없습니다.
3. **그대로 쓸 IFS 고유 도구는 없습니다.** IFS Scale(57문항)·Self Scale(25문항)과 Self-Leadership Scale(50·20문항)은 모두 "얼마나 자주"를 묻는 특성 척도입니다. 특정 대상 하나를 향한 지금의 상태를 재지 않습니다. IFS Scale은 IFS 훈련을 받은 임상가만 회당 $9.99에 쓸 수 있습니다. unblending만 재는 검증된 도구는 찾지 못했고, 최근 IFS 기전 연구(Ally 외 2026)도 그런 도구가 없다고 적었습니다.
4. **뼈대**: Bernstein 외(2015)의 세 과정(메타 알아차림, 탈동일시, 반응성 감소)에 IFS의 태도(호기심·연민)를 더해 세 성분 지도를 만들었습니다. IFS 연구가 unblending을 탈중심화(EQ-D)와 자기자비(SCS-SF)로 대신 잰 선례가 있습니다(Ally 외 2025·2026).
5. **제안("구별 프로파일")**: 점수 하나로 묶지 않고 세 방법을 함께 씁니다. 자기보고 최소판 7문항(MPoD-s 고친 판 3 + 신규 2 + 기존 S5·S6), 이미 기록되는 자료로 계산하는 행동 지표(거리×머리 방향 2×2, 멈춤 거리 방향 차, 다시 잡기), Kiwi 규칙으로 세는 한국어 언어 표지(동일시 틀 "나는 X다" / 존재 틀 "나에게 X가 있다" / 지시어 / 명시 1인칭 / 과거시제, 그리고 기존 Feel toward 고정 문구 답의 태도 낱말)입니다.
6. **다른 연구자에게 쓸모 있으려면** IFS 용어 대신 "탈동일시·태도·반응성"이라는 이론 공통 성분으로 보고하고, 문항·번안 기록·계산 코드·언어 규칙·합성 예문을 함께 공개해야 합니다. 주장 수위는 "구성개념 지도에 맞춘 다방법 탐색 측정"까지이고 "unblending 척도"라고 부르면 안 됩니다.

---

## 1. 구성개념 지도

"구별하기"를 세 성분으로 나눕니다. 각 칸의 표시는 다음과 같습니다.
- **(문헌)**: 열어 본 문헌이 그 연결을 직접 말함
- **(해석)**: 이 문서가 연결한 것이며 문헌이 직접 말하지 않음

| 성분 | IFS 용어 | ACT·마음챙김·자기 거리두기 용어 | 재는 기존 도구 | 설문 초안의 현재 문항 | 빈칸 |
| --- | --- | --- | --- | --- | --- |
| **(가) 알아차림**: 그것이 있음을 앎 | Find·Focus. part를 찾아 주의를 둠(ifs-knowledge 2절). unblending 첫 단계가 메타 알아차림을 만든다는 서술이 있음(Ally 외 2025, (문헌)) | 메타 알아차림(meta-awareness): "awareness of subjective experience"(Bernstein 외 2015 (문헌)). 마음챙김은 이 과정만 담는다고 봄(같은 글, Table 1) | MPoD-s 1번(상태), TMS 탈중심화 4번 "events in my mind"(상태), EQ-D 일부(특성) | M1(B′안), B3(B안). **주 척도 A에는 없음** | A를 주 척도로 쓰면 알아차림 문항이 0개 |
| **(나) 탈동일시**: 그것 ≠ 나 전체 | Blending/Unblending: "내가 그 감정이다" → "나에게 그런 part가 있다"(ifs-knowledge 1절). 자기지칭 `selfReference` 기록 | 탈동일시(disidentification): "the experience of internal states as separate from one's self"(Bernstein 외 2015 (문헌)). Self-as-context와 자기 거리두기(self-distancing)도 Bernstein 표에서 이 과정에 놓임 (문헌). **unblending을 이 칸에 놓은 것은 (해석)**. Ally 외는 unblending을 메타 알아차림·탈중심화와 연결했지만 Bernstein의 "탈동일시" 과정으로 특정하지는 않음 | MPoD-s 2번, TMS 1·11번(상태), SACS·RISP·NAS·EQ-D(특성), IOS식 겹침(Ersner-Hershfield 2009 변형), Kross 관점 문항 | S3(겹침 그림), S1·S2(거리감·관점). B안이면 B1·B7, B′안이면 M2. A6 "깊이 얽혀 있다"는 (다)의 반응성에 가까움 | "그 느낌이 곧 나다" 대 "나에게 이것이 있다"를 직접 묻는 문항이 없음. S1–S3은 공간 은유라 실제 배치 거리와 섞임(설문 초안 4절) |
| **(다) 대하는 태도**: 열림·호기심·너그러움 대 밀어냄·휩쓸림 | Feel toward: Self-energy 확인. 호기심·연민이면 Self 쪽, 혐오·두려움·짜증이면 아직 blended(ifs-knowledge 2절). 8C. Steinhardt 외 2003은 Self를 비판단적 관찰자가 아니라 "active, compassionate leader"로 구별함 (문헌) | 반응성 감소(reduced reactivity, Bernstein (문헌). **CFQ는 이 과정을 반영한다**고 Bernstein 표가 적음). 수용·호기심(TMS 호기심 하위척도), 자기자비(SSCS). Ally 외 2026은 자기자비와 탈중심화가 한 요인("Compassionate Awareness")으로 묶였다고 보고함 (문헌). **Feel toward의 대상을 '자기'에서 '이것'으로 바꾼 자기자비 문항을 이 칸에 쓰는 것은 (해석)** | SSCS-L/S(상태), TMS 호기심 6문항(상태), CEAS(특성), MPoD-s 3번(반응성, 상태), SCFQ/CFQ(반응성) | A1–A7(반응성·휩쓸림), S5 더 알고 싶다(접근), S6 주의를 거두고 싶다(회피), S8 좋다–싫다(정서가) | **너그러움·연민 쪽을 묻는 문항이 없음.** S8은 대상이 좋은지 싫은지를 묻고, 내가 그것을 어떻게 대하는지는 묻지 않음 |

지도에서 나온 판단:
- 설문 초안 A는 (다)의 "휩쓸림" 쪽만 잽니다. Bernstein 외가 CFQ를 반응성 과정의 측정으로 분류하므로 (문헌), A 점수가 내려가도 "탈동일시가 일어났다"고 말할 근거는 약합니다.
- 우려 (1) "놓은 거리는 회피일 수 있다": 거리 자체는 (나)와 (다)의 어느 쪽인지 알려 주지 않습니다. 3.2절에서 머리 방향과 자기보고를 함께 써서 가르는 방법을 제안합니다.
- 우려 (2)·(3)은 지도의 빈칸과 같습니다. 3.1절의 P1(탈동일시)과 P2(태도)로 메웁니다.

---

## 2. 후보 도구 표

| 도구 | 재는 성분 | 문항 수 | 상태·특성 | 한국어판 | 원문 확보 | 사용 조건 | 출처 URL | 확인 수준 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **IFS Scale** (DeLand, Strongin & Schwartz. 학술지 Journal of Self Leadership 2권 1호. PDF에는 "© Lia DeLand, 2003"만 있고 권호 연도는 확인 못 함) | part 8종 + Self | 57(130문항에서 줄임), 10개 하위척도, 5점 | **특성**("how frequently") | [못 찾음] | 하위척도와 α만 확보. 부분 문항은 예시 1개 | IFS Institute 페이지: "trained IFS clinicians for a fee of $9.99 per use". 규준은 무선 표집이 아님. 페이지에 정식 논문 인용이 없음 | https://ifs-institute.com/resources/research/ifs-scale ; https://foundationifs.org/images/banners/pdf/Journal_for_Self_Leadership_DeLand.pdf | 페이지 [전문], 논문 [전문] |
| **Self Scale** (같은 논문) | Self(두 요인: Self-Qualities, Self-Leadership) | 25(짧은 판 9) | 특성(빈도 5점) | [못 찾음] | **25문항 [전문]**(논문 표 7, "© Lia DeLand, 2003") | 명시 없음. 저작권 표시가 있음 | 위 DeLand PDF | [전문]. α=.97, 짧은 판 α=.93, 두 판 r=.98. 호기심·연민·창의·연결 문항은 통계적으로 약해 빠졌다고 저자가 적음 |
| **Self-Leadership Scale (SLS)** (Steinhardt, Dolbier, Mallon & Adams 2003, Journal of Self Leadership 1권, 22쪽부터) | 8C에 맞춘 Self-leadership | 50(짧은 판 20) | 특성(빈도 5점). 저자가 상태 성격일 수 있다고 논의함 | [못 찾음] | **50문항 [전문]**(표 2, 짧은 판 표시 포함) | 명시 없음 | https://foundationifs.org/images/banners/pdf/Journal_for_Self_Leadership_Steinhardt.pdf | [전문]. 공무원 N=745. α .95/.93, 8주 재검사 r=.66/.65 |
| **Fitzgerald 2021**이 쓴 Self 척도 | Self-leadership | 25(검색 요약상 DeLand Self Scale) | 특성 | — | 미확인 | — | https://aquila.usm.edu/fac_pubs/18974 (DOI 10.1080/01926187.2020.1865218) | 서지·요지 [초록만], 쓴 척도는 [2차 자료](검색 요약) |
| **SSCS** (State Self-Compassion Scale; Neff, Tóth-Király, Knox, Kuchar & Davidson 2021, Mindfulness 12(1):121–140) | (다) 자기를 대하는 태도(친절·자기판단·과동일시 등 6성분) | 긴 판 18, 짧은 판 6, 1–5 | **상태**("right now as you think about this situation") | [못 찾음](특성 K-SCS는 있음) | **18·6문항과 지시문 [전문]**(저자 배포 문항지) | 검색 요약에 "Dr. Kristin Neff grants permission … for any purpose"가 있으나 그 문서는 열지 않음 | https://self-compassion.org/wp-content/uploads/2020/09/State-Self-Compassion-Scales.pdf ; 논문 https://self-compassion.org/wp-content/uploads/2021/03/Neff2021State.pdf(열지 않음) | 문항지 [전문], 논문 수치·허가 [2차 자료] |
| **TMS 호기심 하위척도** (Lau 외 2006) | (다) 경험을 향한 호기심 | 6, 0–4 | 상태(직전 명상 회기) | K-TMS(이우경 외 2010) 문항은 [미입수](이전 작업) | **영어 6문항 [전문]**(Navarrete 외 2023 부록 표, 3·5·6·10·12·13번. 예: "I was curious about each of the thoughts and feelings that I was having.") 이 표본 α=.85 | 확인 못 함 | https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2023.1212036/pdf | [전문] |
| **MPoD-s** (Hanley 외 2020) | (가)(나)(다) 하나씩 | 3, 0–10 | 상태 | 없음 | [전문](이전 작업, 설문 초안 2.4) | 확인 못 함 | https://pmc.ncbi.nlm.nih.gov/articles/PMC8647764/ | [전문](이전 작업) |
| **EQ-D** (Fresco 외 2007) / K-EQ | (가)(나) 탈중심화 | 11, 1–5 | 특성 | K-EQ(김빛나 외 2010) | 한국어 예시 2문항(이전 작업) | 번안 허가 기록 있음 | 부록 C-4 | IFS 연구가 unblending 대리 지표로 씀(Ally 외 2025·2026 [전문]) |
| **SCS-SF** (Raes 외 2011) | (다) 자기자비 | 12 | 특성 | 특성 SCS 한국판 있음(김경의·이금단 2008 등, 검색 요약) | 미확보 | 미확인 | Ally 외 2026 | [2차 자료] |
| **Nonattachment to Self Scale** (Whitehead, Bates, Elphinstone, Yang & Murray 2018, Front Psychol 9) | (나)(다) 자기 개념에 붙잡히지 않음 | 7, 1–7 | 시간 틀 없음, 36일 재검사 r=.80 → 특성에 가까움 | [못 찾음] | **7문항 [전문 일부]**(표 1) | 논문 라이선스 문구는 읽은 범위에 없었음 | https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.02544/full | [전문 일부]. 대상이 "thoughts about myself"라 우리 "이것"과 다름 |
| **SACS** (Zettle 외 2018) | (나) 관찰하는 자기 | 10(Centering, Transcending) | 특성 | K-SACS(2026, 서지만) | [미입수] | 미확인 | 부록 C 표 ; https://www.mdpi.com/2076-328X/15/7/910 (403) | [2차 자료] |
| **RISP** (Reno Inventory of Self-Perspective; Jeffcoat 2015 박사논문) | (나) 얽힘·중심·초월 | 13(3차원판) | 특성 | [못 찾음] | 미확보 | 미확인 | https://scholarwolf.unr.edu/entities/dissertation/ad5978c4-af5c-43fd-b158-f81e880ddce8 (열지 않음) | [2차 자료](검색 요약) |
| **CEAS** (Gilbert 외 2017, Journal of Compassionate Health Care) | (다) 자기·타인 연민의 관여와 행동 | 미확인 | 특성 | 미확인 | 미확보 | 논문은 CC BY 4.0이라는 검색 요약만 있음 | https://link.springer.com/article/10.1186/s40639-017-0033-3 (로그인 리디렉트로 못 엶) | [2차 자료] |
| **CEI-II 상태판** (Kashdan 외) | (다) 호기심 | 미확인 | 상태판이 있다고 함 | 미확인 | 미확보 | 미확인 | https://ppc.sas.upenn.edu/node/209 (열지 않음) | [2차 자료](검색 요약) |
| **Kross·Ayduk 관점 문항, IOS, CFQ-7, SCFQ, TMS 탈중심화** | 설문 초안 1절 참고 | — | — | — | — | — | 설문 초안 1절 | 이전 작업 |
| **Self-Assessment Manikin, 상태 수용 문항, Disidentification 척도** | — | — | — | — | — | — | SAM은 이번에 열지 않음. "disidentification scale"(정신통합 계열) 검색은 해리·정체성 척도만 나옴 | [못 찾음] |

**IFS 효과 연구가 결과 변수로 쓴 것**

| 연구 | 결과 변수 | IFS 고유 도구 | 확인 수준 |
| --- | --- | --- | --- |
| Shadick 외 2013, J Rheumatol 40(11):1831–1841 (RCT, 류마티스 관절염) | RADAI 관절 통증, SF-12, 통증 VAS, BDI, STAI, 자기효능감(Lorig), **Neff SCS 26문항**. 1년 뒤 자기자비 개선 유지 [1.8 (2.8), p=.01] | 없음 | [전문] |
| Haddock 외 2017, J Marital Fam Ther 43:131–144 (우울, 여대생 37명) | 우울 증상(도구 이름은 확인 못 함) | 확인 못 함 | [2차 자료](IFS Institute 요약) |
| Hodgdon 외 2022, J Aggress Maltreat Trauma (DOI 10.1080/10926771.2021.2013375) | PTSD, 우울·해리·신체화, 정서 조절 곤란, 자기지각 혼란, 내수용 자각, 자기자비(도구 이름은 확인 못 함) | 확인 못 함 | [2차 자료](IFS Institute 요약) |
| Ally 외 2025, Front Psychiatry 16:1544435 (온라인 집단 IFS, PTSD+물질 사용) | PCL-5, 갈망, ITQ-DSO, PROMIS, MDI. 기전: **DERS, EQ-D(11), NADA(13)** | 없음. unblending은 논의에서만 다룸("An initial 'unblending,' stage generates meta-awareness…") | [전문] |
| Ally 외 2026, Front Psychol 17:1892071 (PARTS, 단일군 30명) | PCL-5, ITQ. 기전: **EQ-D, SCS-SF, TMS-Curiosity**, 자기비판 반추, DERS-16, OAS2, CES, CSE-T. 탐색적 요인분석에서 자기자비(.95)와 탈중심화(.69)가 "Compassionate Awareness"로 묶임 | 없음. 저자가 쓴 도구는 마음챙김 개입의 기전용이고 "rather than for the specific cognitive and affective processes hypothesized to operate in unblending"이라고 적음 | [전문 일부](앞 10만 자) |

---

## 3. 제안: "구별 프로파일" (초안)

세 방법(자기보고, 행동, 언어)을 성분별로 따로 보고합니다. 합산 점수는 만들지 않습니다. 성분 사이의 관계 자체가 아직 검증되지 않았기 때문입니다.

### 3.1 자기보고 단축 문항

번안 원칙은 설문 초안 3.0을 그대로 따릅니다. 대상은 "이것", 시간 틀은 "지금 이 순간", 두 조건에 같은 문장을 쓰고, 배치 동작과 겹치는 말(잡다·놓다·옮기다·물러서다·떨어지다)과 변화 방향을 묻는 말은 쓰지 않습니다. 이번에 하나를 더합니다. **"보다·지켜보다"는 보기만 조건의 동작과 겹치므로 문항에서 뺍니다.**

| ID | 성분 | 한국어 초안 | 응답 | 출처 | status |
| --- | --- | --- | --- | --- | --- |
| M1′ | (가) 알아차림 | 지금 나는 이것이 내 마음에서 일어나고 있다는 것을 알아차리고 있다. | 0 전혀 아니다 … 10 매우 그렇다 | MPoD-s 1번 수정. 설문 초안 M1의 "그대로 지켜볼 수 있다"를 "알아차리고 있다"로 바꿈(보기만 조건의 동작과 겹치기 때문) | draft |
| M2 | (나) 탈동일시 | 지금 나는 나 자신을 그 느낌과는 별개로 경험한다. | 0–10 | MPoD-s 2번 수정(설문 초안 그대로). G65·G66(2026-11-27): 대상을 "이것"에서 "그 느낌"으로 | draft |
| **P1** | (나) 탈동일시 | 지금 나와 그 느낌의 관계는 어느 쪽에 더 가깝나요? (G65·G66, 2026-11-27: 대상을 "이것"에서 "그 느낌"으로. P1 기준점도 같이 바꿈) | **1 그 느낌이 곧 나다 · 4 반반이다 · 7 그 느낌은 나에게 있는 것이지, 나 전체는 아니다** | 자작. IFS unblending 정의("내가 그 감정이다" → "나에게 그런 part가 있다", ifs-knowledge)와 Bernstein의 탈동일시 정의를 양극 문장으로 옮김. "부분·part"라는 낱말은 쓰지 않음(V6 `ifs_label`과 같은 이유) | draft |
| M3 | (다) 반응성 | 지금 나는 이것을 알아차리면서도 이것에 좌우되지 않을 수 있다. | 0–10 | MPoD-s 3번 수정(설문 초안 그대로) | draft |
| **P2** | (다) 태도 | 지금 나는 이것을 어떻게 대하고 있나요? | **1 엄하게 대하고 있다 · 4 반반이다 · 7 너그럽게 대하고 있다** | SSCS-L 4번("I'm being pretty tough on myself")과 7번("I'm being kind to myself")을 양극으로 묶고 대상을 "나 자신"에서 "이것"으로 바꿈. 대상 변경은 Feel toward에 맞춘 (해석) | draft |
| S5 | (다) 접근 | 지금 나는 이것에 대해 더 알고 싶다. | 1–7 | 기존(V3). TMS 호기심 6번과 내용이 가까움 | draft |
| S6 | (다) 회피 | 지금 나는 이것에서 주의를 거두고 싶다. | 1–7 | 기존(V3) | draft |

- **최소판은 위 7문항**입니다. 주 척도 A(7문항)와 문항 수가 같으므로, 팀이 "구별"을 주 결과로 삼는다면 A를 이것으로 바꾸고 A는 A-core 4문항을 보조로 남기는 안을 제안합니다. A와 이 7문항을 모두 쓰면 사전에만 20문항이 넘습니다(설문 초안의 시간 상한과 충돌).
- S5와 S6은 양극 하나로 합치지 않고 따로 둡니다. 둘 다 높으면 양가(끌리면서 밀어냄)이고, 이것은 IFS에서 양극화된 보호자 신호일 수 있습니다. 하나로 합치면 이 경우가 가운데 점수로 묻힙니다.
- 추가 후보(선택, 시간이 남으면): B3(TMS 4번, 알아차림), B7(TMS 11번, 탈동일시). S1–S3은 공간 은유라 보조로만 둡니다.

**감정어가 필요한 대안 (권하지 않음, ⚑ 원칙 3과 긴장)**

| ID | 안 | 긴장 |
| --- | --- | --- |
| P-alt1 ⚑ | 8C 낱말(호기심, 연민, 차분함 …)과 혐오·두려움·짜증을 목록으로 보여 주고 지금 해당하는 것을 고르게 함 | 참여자가 쓰지 않은 감정 이름을 시스템이 내밈. 목록이 "바람직한 답"을 알려 주는 사회적 바람직성 문제도 있음 |
| P-alt2 ⚑ | SSCS 짧은 판 6문항을 "이것"에 맞춰 통째로 고침 | 문항 2·3·6("obsessing", "others … feeling like I am", "struggling more than others")은 대상을 "이것"으로 바꾸면 뜻이 성립하지 않음. 비교 문항은 원칙 3의 "예시·비교" 금지와 맞지 않음 |

대신 태도의 감정 낱말은 **참여자가 스스로 말한 것만** 3.3절 언어 지표(L-B)로 셉니다.

### 3.2 행동 결합 지표

기록된 자료만 씁니다(제안서 4.5: 놓은 거리·방위·높이, 다시 잡은 횟수, 첫 잡기까지 시간, 궤적은 직접 배치 조건만. 머리–물체 거리와 응시 비율은 두 조건 모두, 20 Hz. 멈춤 거리는 사후만).

**정의**

| 기호 | 정의 | 조건 |
| --- | --- | --- |
| `D_place` | 90초가 끝날 때 물체 중심과 참여자 시작 자리 사이의 수평 거리(m). 시작 거리 1.5 m(잠정)와의 차 `ΔD = D_place − 1.5` | 직접 배치 |
| `D_head(t)` | 머리–물체 거리. 구간 평균 | 모두 |
| `G` | 머리 정면 벡터와 머리→물체 벡터 사이 각이 θ 이하인 표본의 비율. θ는 사전 등록(예: 15°)하고 10°·20°·30°로 민감도 분석. **눈 시선이 아니라 머리 방향**임 | 모두 |
| `G_early`, `G_late` | 처음 30초, 마지막 30초의 G | 모두 |
| `R`, `T_grab` | 다시 잡은 횟수, 첫 잡기까지 시간 | 직접 배치 |
| `SD_app`, `SD_rec` | 멈춤 거리: 다가오는 시행 평균, 멀어지는 시행 평균. `SD_asym = SD_app − SD_rec`, `SD_mean` | 모두(사후만) |

**거리 × 머리 방향 2×2 (직접 배치 조건)**: 거리 축은 `ΔD`의 부호(시작보다 가까이/멀리), 방향 축은 `G_late`가 사전 등록한 기준(예: 0.5)보다 높은지입니다. 칸 이름은 관찰 서술로만 붙입니다.

| 칸 | 이름 | 주장할 수 있는 것 | 주장할 수 없는 것 |
| --- | --- | --- | --- |
| 가까이·봄 | NL | 물체 가까이에서 주의를 둠 | "구별되지 않음(얽힘)"인지 "다가가 살핌"인지 행동만으로는 모름 |
| 멀리·봄 | FL | 거리를 두고도 머리가 물체를 향함 | **"거리 둔 관찰"이라고 단정할 수 없음.** VR 거미 공포 연구에서 공포증 집단은 거미와 최소 거리를 더 멀리 두면서도 거미를 더 자주 보고 몸을 더 향했음(Binder 외 2022 [전문 일부]). 경계 감시와 같은 행동 모양임 |
| 멀리·안 봄 | FA | 거리도 두고 주의도 거둠 | 회피와 가장 잘 맞지만, 과제를 끝냈다고 여겨 둘러보는 행동일 수도 있음 |
| 가까이·안 봄 | NA | 가까이 두고 주의는 다른 데 둠 | 해석이 가장 모호함(무관심, 가까운 것을 보기 부담스러움, 둘러보기) |

FL을 "거리 둔 관찰"과 "경계 감시"로 가르려면 자기보고를 함께 봐야 합니다. 사후에 S5↑·S6↓·P2 높음·M3 높음이면 관찰 쪽, S6↑·P2 낮음이면 감시·회피 쪽으로 읽습니다. 이 규칙도 사전 등록하고 탐색 결과로만 보고합니다.

**보기만 조건**에서는 거리를 참여자가 정하지 않으므로 2×2를 만들 수 없습니다. `G`, `G_late − G_early`, `D_head`만 두 조건에서 비교합니다. 조건 간 `D_place` 비교는 조작 자체의 결과라서 결과 변수로 쓰지 않습니다(부록 C 권고와 같음).

**그 밖의 지표와 주장 범위**

| 지표 | 주장할 수 있는 것 | 주장할 수 없는 것 |
| --- | --- | --- |
| `SD_mean` | 사후에 "이것"이 있기에 알맞다고 고른 거리. 두 조건이 같은 방식으로 측정됨 | 사전값이 없으므로 변화량이 아님. 물체·심상 자극에서 검증된 적이 없음(부록 D) |
| `SD_asym` | 방향에 따라 멈춘 거리가 다른지 | 방어 경계의 비대칭이라고 해석할 근거가 약함. 데스크톱 얼굴 과제에서 접근과 후퇴는 차이가 없었고(Lebert 외 2024, 부록 D B6), 정신물리 한계법의 반응 편향일 수도 있음 |
| `R`, `T_grab` | 자리 조정에 들인 행동량 | 탐색인지 안절부절못함인지 구별 못 함 |
| `G_late − G_early` | 시간에 따라 주의가 물체로 모이는지 흩어지는지 | 머리 방향만으로 주의를 확정할 수 없음. 시야각이 넓어 머리를 돌리지 않고 볼 수 있음 |

### 3.3 언어 지표 (LLM 없이 규칙으로 계산)

**받는 발화 (사전·사후 같은 문구)**

| ID | 고정 문구 | 상태 | 쓰는 곳 |
| --- | --- | --- | --- |
| L-A | 지금 이것에 대해 떠오르는 대로 한두 문장으로 말씀해 주세요. | `status: draft` · 출처: 자작. 묘사어·예시·방향어가 없음 | 동일시·대상 틀 표지 |
| L-B | 지금 그것에 대해 어떻게 느끼나요? | 기존 `feel_toward` 고정 문구(elicitation_protocol v1.1). 문구는 바꾸지 않고 **사전·사후 두 번 묻는 배치만 새로 정함**. 배치 변경도 IRB 대상 | 태도 낱말 |

- 음성 답을 전사합니다. 전사와 원문은 참여자 자료라서 git에 올리지 않습니다(원칙 6).
- 두 문구 모두 6개 질문 틀과 별개인 VR 고정 문구입니다. LLM은 끼지 않습니다(원칙 1·3).

**표지의 조작적 정의 (Kiwi 0.24.1 품사 태그 기준, `chatbot/.venv`에서 합성 문장으로 태그를 확인함)**

| 표지 | 규칙 | 근거 |
| --- | --- | --- |
| K1 명시 1인칭 | 형태 `나`·`저`이고 태그가 `NP`인 토큰 수. Kiwi는 "내"를 `나/NP 의/JKG`로, "제"를 `저/NP 의/JKG`로 풀어 냄 | 영어 1인칭 단수 감소(Nook 외 2017, 2차), Kross 외 2014 |
| K2 동일시 틀 "나 = X" | 한 절 안에서 (a) 1인칭 `NP` + `JX`/`JKS`가 주어이고 서술어가 `VCP`(이다)인 경우("나는 X다", "내가 X예요"), 또는 (b) 서술어 `VCP` 바로 앞이 1인칭 `NP`인 경우("X가 저예요") | IFS blending 서술의 한국어 대응. **(해석)** |
| K3 존재 틀 "나에게 X가 있다" | 서술어가 `있`이고 태그가 `VA` 또는 `VV`(조동사 `VX`는 제외)이며, 주어(`JKS`)가 1인칭이 아니고, 같은 절에 1인칭 `NP` + `JKB`(에게·한테·에) 또는 1인칭 `NP` + `JKG` + `안`/`속`이 있는 경우. 자기 위치어 없이 "X가 있다"만 있으면 K3b로 따로 셈 | IFS unblending 서술("나에게 그런 part가 있다")의 대응. **(해석)** |
| K4 지시어 대상 지칭 | `이것`·`그것`·`저것`/`NP`, 또는 `이`·`그`·`저`/`MM` 다음 명사가 주어(`JKS`/`JX`) 자리에 오는 경우 | 대상을 말하는 쪽에서 떼어 가리킴. **(해석)** |
| K5 지각 술어 | 서술어 `보이`/`VV`이고 바로 앞 토큰이 연결어미 `EC`가 아닌 경우("그게 보여요"). 앞이 `EC`면 "~아 보이다"(추정)라서 제외 | 관찰자 자리 서술. **(해석)** |
| K6 과거시제 | 절에 `EP`(었·았·였)가 있는 비율 | 현재시제 감소(Nook 외 2017, 2차) |
| K7 주어 미지정 | 서술어는 있는데 `JKS`/`JX`가 붙은 체언이 없는 절. **1인칭으로 채워 넣지 않고 "미지정"으로 둠** | 원칙 2. 스페인어 연구는 동사 활용형으로 1인칭을 복원했지만(Holmes 외 2024 [전문]) 한국어 동사에는 인칭 일치가 없어 그 방법을 쓸 수 없음 |
| L-B 태도 낱말 | 참여자 답에서 미리 등록한 사전의 표제어를 찾음. 범주: 열림(궁금·신기·알고 싶 …), 너그러움(안쓰럽·짠하·고맙 …), 차분(괜찮·편안·차분 …) / 밀어냄(싫·밉·역겹 …), 두려움(무섭·겁 …), 짜증(짜증·귀찮 …). 부정어(`안`/`MAG`, `못`, `-지 않`)가 두 토큰 안에 있으면 "부정된 X"로 따로 셈. 일치가 없으면 "미지정" | ifs-knowledge 2절의 Feel toward 해석 기준. 사전은 연구자 코딩용이며 참여자에게 보이지 않음. 사전 목록은 예시이고 확정 전임 |

**합성 예문과 Kiwi 출력** (모두 이 문서가 만든 합성 문장입니다. 원칙 6)

| 예문 | Kiwi 0.24.1 출력 | 표지 |
| --- | --- | --- |
| 나는 불안 덩어리다. | 나/NP 는/JX 불안/NNG 덩어리/NNG 이/VCP 다/EF | K1, K2 |
| 내가 그 돌이에요. | 나/NP 가/JKS 그/MM 돌/NNG 이/VCP 에요/EF | K1, K2 |
| 저 돌이 저예요. | 저/MM 돌/NNG 이/JKS 저/NP 이/VCP 예요/EF | K1, K2(b), K4 |
| 내 안에 불안한 게 있어요. | 나/NP 의/JKG 안/NNG 에/JKB 불안/NNG 하/XSA ᆫ/ETM 것/NNB 이/JKS 있/VA 어요/EF | K1, K3 |
| 나한테 그런 마음이 있네. | 나/NP 한테/JKB 그런/MM 마음/NNG 이/JKS 있/VA 네/EF | K1, K3 |
| 가슴에 돌 같은 게 있다. | 가슴/NNG 에/JKB 돌/NNG 같/VA 은/ETM 것/NNB 이/JKS 있/VV 다/EF | K3b (같은 "있"이 여기서는 `VV`) |
| 제 일부가 겁을 내고 있어요. | 저/NP 의/JKG 일부/NNG 가/JKS 겁/NNG 을/JKO 내/VV 고/EC 있/VX 어요/EF | K1. `있/VX`라 K3 아님 |
| 그게 저기 보여요. | 그것/NP 이/JKS 저기/IC 보이/VV 어요/EF | K4, K5 |
| 그 공이 아까보다 작아 보였다. | 그/MM 공/NNG 이/JKS 아까/NNG 보다/JKB 작/VA 어/EC 보이/VV 었/EP 다/EF | K4, K6. 앞이 `EC`라 K5 아님 |
| 무거워요. | 무겁/VA-I 어요/EF | K7 미지정 |
| 그냥 저 자체가 무거운 거예요. | 그냥/MAG 저/MM 자체/NNG 가/JKS 무겁/VA-I 은/ETM 거/NNB 이/VCP 예요/EF | **오분석 예**: 1인칭 "저"가 `MM`(지시 관형사)으로 태그됨 |

**한계**
- **짧은 발화**: 한두 문장이라 비율(%)이 불안정합니다. 표지마다 "있음/없음"과 개수만 쓰고, 사전→사후 변화는 참여자 수준의 이분 변화(예: K2 있음→없음)로 봅니다. Nook 외의 합성 지표는 30초 글쓰기를 여러 시행 평균했는데도 α가 .52(연구 1)와 .73(연구 2)이었습니다(Nook 외 2024 재분석 [전문 일부]). 한 번의 짧은 발화로 계산한 선례는 찾지 못했습니다 [못 찾음].
- **주어 생략**: 한국어 발화의 상당수는 K7이 됩니다. 이것을 1인칭으로 채우면 원칙 2에 어긋납니다. 그래서 K1·K2는 "명시적으로 말한 경우"만 셉니다.
- **"저"의 중의성**: 1인칭 겸양 "저"와 지시 "저"를 Kiwi가 틀릴 수 있습니다(위 마지막 예). 규칙 출력은 사람 코더 1명이 전수 확인하고, 20% 이중 코딩으로 일치도를 냅니다(Holmes 외는 1인칭 코딩 κ=.96을 보고함).
- **"있다" 태그 흔들림**: 같은 "있"이 `VA`와 `VV`로 나옵니다. 둘 다 받고 `VX`만 뺍니다.
- **과거시제의 혼입**: 사후 발화는 방금 겪은 VR 장면을 말하므로 과거형이 자연히 늘 수 있습니다. K6 변화는 거리두기보다 장면 회상일 수 있습니다.
- **틀 효과의 근거가 약함**: "I am X" 대 "I have X"를 직접 비교한 실험은 찾지 못했습니다. 가장 가까운 것은 명사형 대 소유형 자기 낙인 표현을 비교한 대학생 40명 상관 연구(Stroman, Bock 외, [2차 자료])입니다. "part of me" 틀을 조작한 실험도 [못 찾음]입니다. K2·K3은 IFS 서술을 한국어 구문으로 옮긴 (해석)입니다.
- **판본 고정**: Kiwi 버전과 모델 파일을 기록합니다(원칙 5와 같은 취지). 같은 전사본은 언제나 같은 결과를 내야 합니다(원칙 1).

### 3.4 세 방법의 수렴을 보는 법

**상관표**: 행과 열을 "성분 × 방법"으로 놓습니다. 예를 들어 (나) 탈동일시의 자기보고(P1·M2 변화), 언어(K2 감소·K3 증가), 행동(해당 없음)이 있고, (다) 태도의 자기보고(P2·S5·S6·M3), 언어(L-B 범주), 행동(2×2 칸·G)이 있습니다. 같은 성분을 다른 방법으로 잰 값끼리 상관이 다른 성분끼리보다 높아야 성분 구분이 쓸모 있다고 볼 수 있습니다. 이 기준은 다특성–다방법 행렬의 발상을 빌린 것이고, 이번에 원 문헌을 열지는 않았습니다.

**불일치 사례의 해석 (사전에 정해 둠)**

| 사례 | 읽는 법 |
| --- | --- |
| P1 높음(나에게 있음) + 발화에 K2("나는 X다") | 자기보고가 사회적 바람직성(IFS식 정답)에 끌렸을 가능성. 또는 말버릇. 사례 메모로 남김 |
| FL(멀리·봄) + S6 높음 + L-B "무섭" | 경계 감시. 구별이 아니라 섞임 쪽 |
| FL + S5 높음 + P2 높음 + L-B "궁금" | 거리 둔 관찰. 프로파일이 가장 잘 맞는 경우 |
| NL(가까이·봄) + P1 높음 + P2 높음 | 가까이 두고도 구별됨. **거리 = 구별이 아니라는 우려 (1)을 보여 주는 사례** |
| 자기보고는 변화가 없고 행동만 변함 | 조작이 행동을 바꿨으나 상태 보고에는 닿지 않음. 또는 문항 둔감 |

**예비 시행에서 볼 것**: 문항별 끝점 비율(특히 P1·P2의 사회적 바람직성 천장), 인지 면담에서 P1의 두 끝 문장을 자기 말로 바꿔 말하게 하기, L-A 발화의 길이 분포와 K7 비율(대부분 미지정이면 K1·K2는 쓸 수 없음), 규칙 출력과 사람 코딩의 일치도, θ에 따라 2×2 칸 배정이 얼마나 바뀌는지, 응답 시간.

**표본 감각** (양측 α=.05, 검정력 .80, Fisher z 근사로 계산)

| 찾으려는 상관 | 필요한 n |
| --- | --- |
| r = .3 | 85 |
| r = .4 | 47 |
| r = .5 | 30 |
| r = .6 | 20 |

예비 시행 15–20명으로는 r이 약 .6–.67보다 큰 경우만 유의하게 잡힙니다(n=15에서 .67, n=20에서 .59). 따라서 예비 시행은 방법 간 수렴을 검정하는 단계가 아니라 **문항이 읽히는지, 표지가 나오는지**를 보는 단계로 둡니다. 집단 비교 표본(부록 D 4절)과는 별도로 판단합니다.

---

## 4. 다른 연구자에게 쓸모 있는 산출물이 되려면

**공개할 것**
1. **구성개념 지도**(1절): IFS 용어를 Bernstein 외의 세 과정 + 태도로 옮긴 표. 문헌이 뒷받침하는 연결과 (해석)을 나눈 그대로 공개합니다.
2. **문항과 번안 기록**: 원문 번호, 바꾼 것과 이유, 순·역번역, 인지 면담 요약(개인 정보 제외). 허가를 받은 범위 안에서만 공개합니다.
3. **행동 지표의 기록 형식과 계산 코드**: 20 Hz 로그의 열 정의(시각, 머리 위치, 머리 정면 벡터, 물체 위치, 잡힘 여부, 조건), `ΔD`·`G`·2×2·멈춤 거리 계산 스크립트, θ 민감도 분석. 합성 궤적으로 만든 시험 자료를 함께 둡니다.
4. **한국어 언어 표지 규칙**: K1–K7과 L-B 사전, Kiwi 버전, 합성 예문과 기대 출력(단위 시험), 오분석 사례 목록. 한국어 1인칭 생략과 "저"의 중의성을 다루는 방법은 다른 한국어 정서조절 연구에도 그대로 쓸 수 있습니다. KLIWC가 있다는 것은 확인했지만 거리두기 표지를 정의한 한국어 연구는 [못 찾음]입니다.

**주장 수위**: "IFS unblending을 잰다"가 아니라 "탈동일시·태도·반응성의 상태 변화를 세 방법으로 재는 탐색 측정"으로 씁니다. 타당화 연구가 아니라는 점을 제목과 초록에 밝힙니다.

**IFS 밖에서 쓰는 예**
- **ACT 탈융합 VR 연구**(Bell 외 2025, Shigyo 외 2024 계열): SCFQ만 쓰면 반응성만 잽니다. P1·M2(탈동일시)와 P2(태도)를 더하면 탈융합 연습이 어느 과정을 움직였는지 가를 수 있습니다.
- **자기 거리두기 연구**(Kross 계열): 한국어 참가자의 회상 발화에 K1·K2·K7을 적용하면 영어 1인칭 대명사 지표의 한국어판을 시험할 수 있습니다.
- **VR 노출·행동 접근 과제**: 거리만 보면 회피를 과대 추정하거나 경계 감시를 놓칩니다. 거리 × 머리 방향 2×2에 상태 자기보고를 붙이는 절차를 그대로 옮겨 쓸 수 있습니다.
- **PRISM류 배치 측정**: "거리가 무엇을 뜻하는가" 논쟁(부록 C-5(iv))에 대해, 거리와 함께 탈동일시·태도를 따로 재 두면 거리가 어느 성분과 같이 움직이는지 볼 수 있습니다.

---

## 5. 한계와 팀이 정할 것

- **미타당화**: 모든 문항은 고친 판이거나 자작입니다. 원판 요인 구조·신뢰도를 가져올 수 없습니다. P1·P2는 단일 문항이라 신뢰도를 추정할 수 없습니다.
- **사회적 바람직성**: P1·P2는 한쪽 끝이 IFS가 바라는 상태라 참여자가 "정답"을 짐작할 수 있습니다. 문항 배치에서 양 끝의 좌우를 참여자마다 바꾸는 방안을 인지 면담에서 함께 봅니다.
- **허가**: MPoD-s(Hanley), TMS·K-TMS(Lau, 이우경)는 조건을 확인하지 못했습니다. SSCS는 저자가 모든 용도에 허락한다는 문구를 검색 요약으로만 봤습니다. IFS Scale은 유료이고 IFS 훈련 임상가 전용이라 이 연구에 맞지 않습니다. Self Scale·SLS는 논문에 문항이 실려 있지만 사용 조건 문구는 없습니다. 특성 척도라 사전·사후 측정에는 쓰지 않습니다(기저선 공변량 후보로는 팀이 판단).
- **IRB**: P1, P2, M1′, L-A 문구, L-B를 사전·사후 두 번 묻는 배치, L-B 태도 사전이 모두 IRB 제출물에 들어가야 합니다.
- **원칙 3**: P2의 "엄하게/너그럽게"는 감정 이름은 아니지만 연구자가 정한 평가어입니다. 설문 초안 S8의 "좋다/싫다"와 같은 수준의 긴장으로 기록합니다. 감정 목록 대안(P-alt1)은 권하지 않습니다.
- **원칙 8**: Feel toward(지금 그것을 어떻게 대하는가)는 범위 안입니다. beFriend(역할·내력)와 Fears(멈추면 무엇이 걱정되나)는 범위 밖입니다. 그래서 "친해지다", "언제부터", "왜 그러는지"를 묻는 문항은 넣지 않았습니다. L-B 사전에 "고맙다"처럼 beFriend 이후에 흔한 낱말이 있어도 그것은 참여자 말을 세는 것이며 질문으로 유도하지 않습니다.
- **문항 수 부담**: A 7 + 프로파일 7 + S 문항을 모두 쓰면 사전 측정이 20문항을 넘습니다(설문 초안의 13문항 약 2–2.5분에서 비례로 어림하면 4분 안팎). 팀이 정할 것은 다음 넷입니다. (1) 주 결과를 A(반응성)로 할지 구별 프로파일로 할지 (2) L-B를 사전·사후 두 번 물을지 (3) 2×2 기준 θ와 G 절단값 (4) L-A를 넣을지(발화가 너무 짧으면 빼고 사후 인터뷰 전사에서만 셈).
- 정하면 docs/decisions.md에 남깁니다.

---

## 6. 조사 기록 (이번 작업)

**검색어와 검색한 곳** (모두 일반 웹 검색 도구)

| 검색어 | 결과 |
| --- | --- |
| Internal Family Systems Scale validation self-leadership measure psychometric | IFS Institute IFS Scale 페이지, Fitzgerald 2021 |
| "Self-Leadership" scale IFS "Self-energy" questionnaire validation 2023–2025 | 조직 리더십 척도(SLQ·RSLQ·ASLQ)만 나옴. IFS 상태 척도 없음 |
| Fitzgerald "Self-Leadership" … "Self-Leadership Scale" | DeLand 외, Steinhardt 외 Journal of Self Leadership PDF |
| "unblending" measure OR scale … | Ally 외 2026(PMC13771054), Comeau 외 PDF(열지 않음), 임상 워크시트(검증 도구 아님) |
| Hodgdon 2022 / Haddock 2017 / Shadick 2013 결과 변수 | IFS Institute 요약, Shadick PDF |
| Bernstein … "Decentering and Related Constructs" | PMC5103165 |
| Neff 2021 State Self-Compassion Scale | 저자 문항지 PDF |
| 한국판 상태 자기자비 척도 | 특성 SCS 한국판만 나옴 |
| Nonattachment to Self Scale | Frontiers 원문 |
| Reno Inventory of Self-Perspective | 박사논문 레코드, MDPI SACS 논문(403) |
| Compassionate Engagement and Action Scales | Springer(로그인 리디렉트) |
| state curiosity measure … | CEI-II 상태판 언급(열지 않음) |
| Nook 2017 linguistic distancing / PDF | Nook 2024 재분석(PMC11904052), Holmes 외 2024 |
| "I am anxious" vs "I feel anxious" 틀 실험 | 직접 실험 없음. Stroman 외 상관 연구(열지 않음), 블로그 |
| "part of me" language self-talk experiment | Kross 외 2014, Orvell 외 2021(열지 않음). "part of me" 조작 실험은 없음 |
| 한국어 언어적 거리두기 1인칭 생략 KLIWC | KLIWC 개발 논문 레코드(열지 않음). 거리두기 표지 연구 없음 |
| VR behavioral avoidance test distance gaze | Binder 외 2022, Mühlberger 외 2008(2차) |
| disidentification scale psychosynthesis | 해리·정체성 척도만 나옴 |
| 내면가족체계 IFS 척도 한국판 | IFS 프로그램 효과 연구만 나옴. 한국판 척도 없음 |

**연 곳 (확인 수준)**
- https://ifs-institute.com/resources/research/ifs-scale [전문]
- https://foundationifs.org/images/banners/pdf/Journal_for_Self_Leadership_DeLand.pdf [전문] (PDF를 내려받아 텍스트를 뽑음)
- https://foundationifs.org/images/banners/pdf/Journal_for_Self_Leadership_Steinhardt.pdf [전문] (같은 방법)
- https://aquila.usm.edu/fac_pubs/18974 [초록만]
- https://www.jrheum.org/content/jrheum/40/11/1831.full.pdf [전문] (텍스트 추출)
- https://Ifs-institute.com/resources/research/efficacy-internal-family-systems-therapy-treatment-depression-among-female [2차 자료]
- https://Ifs-institute.com/resources/research/internal-family-systems-ifs-therapy-posttraumatic-stress-disorder-ptsd-among [2차 자료]
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11983591/ (Ally 외 2025) [전문]
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13771054 (Ally 외 2026) [전문 일부, 앞 10만 자]
- https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2026.1892071/full (같은 논문) [전문 일부]
- https://pmc.ncbi.nlm.nih.gov/articles/PMC5103165 (Bernstein 외 2015) [전문 일부, 앞 10만 자]
- https://self-compassion.org/wp-content/uploads/2020/09/State-Self-Compassion-Scales.pdf [전문] (텍스트 추출)
- https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.02544/full (NAS) [전문 일부]
- https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2023.1212036/pdf (TMS 호기심 문항) [전문] (텍스트 추출)
- https://pmc.ncbi.nlm.nih.gov/articles/PMC11904052 (Nook 외 2024) [전문 일부]
- https://reed.edu/psychology/thought-lab/assets/publications/Holmes,-Kassin,-Buchillon-Almeida,-Canseco-Gonzalez-2024---Scientific-Reports.pdf (Sci Rep 14:22605) [전문] (텍스트 추출)
- https://sites.lsa.umich.edu/emotion-selfcontrol-psych/wp-content/uploads/sites/1322/2024/07/KrossJ_Pers_Soc_Psychol2014Self-talk_as_a_regulatory_mechanism_How_you_do_it_matters.pdf (JPSP 106(2):304–324) [전문 일부] (텍스트 추출, 초록·서론 확인)
- https://www.frontiersin.org/journals/behavioral-neuroscience/articles/10.3389/fnbeh.2022.827673/full (Binder 외 2022) [전문 일부]
- Kiwi 태그 확인: 저장소 `chatbot/.venv`의 kiwipiepy 0.24.1로 합성 문장 15개를 분석함(스크립트와 출력은 세션 임시 폴더에만 있고 저장소에는 넣지 않음)

**못 연 곳**
- https://www.tandfonline.com/doi/full/10.1080/13284207.2025.2533127 (IFS 범위 검토 2025): 403, 1회
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6300706 (NAS): reCAPTCHA, 1회 → Frontiers 원문으로 대신함
- https://pmc.ncbi.nlm.nih.gov/articles/PMC9094686/ (Binder 외 2022): reCAPTCHA, 1회 → Frontiers 원문으로 대신함
- https://pmc.ncbi.nlm.nih.gov/articles/PMC4808044/ : 다른 논문(오타 ID). Bernstein은 PMC5103165로 대신함
- https://link.springer.com/content/pdf/10.1186/s40639-017-0033-3.pdf 와 https://link.springer.com/article/10.1186/s40639-017-0033-3 (CEAS): 로그인 리디렉트, 각 1회
- https://www.mdpi.com/2076-328X/15/7/910 (SACS 2025): 403, 1회
- 열지 않은 것(검색 요약만 봄): Neff 2021 원 논문, SSCS 허가 안내 PDF, CEI-II 상태판, RISP 박사논문, Stroman 외, Orvell 외 2021, KLIWC 논문, Haddock 2017·Hodgdon 2022 원문, Mühlberger 2008, Comeau 외 PDF, Self-Assessment Manikin
