# 닫힌 사전을 넘어 시각화하기: 생성형 AI 없이 어디까지 되나 (조사, 2026-11-26)

**조사 질문 2.** 사전 없이(또는 닫힌 사전을 넘어) 자율적으로 시각화하는 일이 생성형 AI 없이 가능한가? 그렇게 하게 해 주는 오픈 소스·공개 자원이 있는가?

- 이 문서는 웹 조사 기록이다. 코드·사전·프로토콜은 바꾸지 않았다.
- 각 주장 옆에 출처 URL을 적었다. 열어서 확인하지 못한 것은 "확인 필요"로 적고 끝의 목록에 모았다.
- 판단 기준은 AGENTS.md 원칙 1(장면 속성은 사전·규칙만, 같은 확정 텍스트 → 같은 결과)과 원칙 2(말하지 않은 것을 추론하지 않음, 빈 슬롯은 비었다고 표시), 원칙 5(로컬 실행, 외부 전송 금지, 모델은 digest로 고정)다.
- 생성형 3D는 `docs/gen3d-feasibility.md`가 이미 다뤘으므로 E절에서 결론만 옮긴다.

## 0. 지금 방식 (저장소 기준)

| 항목 | 현재 상태 | 위치 |
| --- | --- | --- |
| 1층 사전 v0 | 379항목, 22범주(감정 49 · 사물 33 · 움직임 31 · 차원어 28 · 질감 27 · 모양 26 · 색 25 · 신체 부위 22 · 감각 20 …) | `shared/lexicon/layer1_lexicon.v0.json` |
| 1층 사전 v1 오버레이 | 174항목(움직임 66 · 질감 38 · 신체 부위 29 · 형태 10 …). 항목 구조는 `lemma`·`pos`·`category`·`value`·`ex`·`src` | `shared/lexicon/layer1_lexicon.v1.json` |
| 기본 형상 사전 | 낱말 34개 → 5개 기본 형상(container · line · sheet · flame · drop), 규칙 19개 | `shared/lexicon/base_shapes.v1.json` |
| 사전 밖 명사 기록 | 확정 텍스트의 명사 중 사전에 없는 것을 `_unmapped`에 남김. 형상 후보가 아닌 명사 6묶음은 `noun_stoplist.v2.json`으로 뺌 | `docs/scene-spec-mapping.md` |
| 퍼지 맞춤 | 자모 편집거리 ≤ 1인 사전 표제어를 찾되 **슬롯 값에 쓰지 않고** `_alternatives`(source `fuzzy_lexicon`, `needsConfirmation`)에만 남김 | `docs/scene-spec-mapping.md` 156행 |
| 3층 V/A/D | 감정어 49개에 붙인 초안 값. 값 자리가 아니라 `_inferred` 제안에만 씀. "검증된 한국어 감성사전으로 바꿔야 한다"고 적혀 있음 | `shared/lexicon/vad_ko.v0.json` |
| 참여자 조절 | 후보 고르기 + 일곱 항목(색·형태·밝기·투명도·크기·질감·움직임) 조절. 출처는 말함/고름/고침/기본값으로 `selection.json`에 따로 기록(G15) | `docs/validation/selection-flow/README.md` |

**실패의 모양**(`docs/mapping-failures.md` 4절, v0 dev 30개): 슬롯 실패 88건 중 사전 누락(LEX) 22, 비교 크기(CMPSZ) 13, 수치(NUM) 7, 복합어·형태소 분할(CMP) 7, 직유 원천 미등록(SIM) 3. 이와 별도로 무슬롯 속성(온도·무게·소리·냄새·모양) 19건이 사라졌다. 같은 문서 7절은 이미 "LLM 구조화 추출과 임베딩 유사도는 장면 속성 경로에 넣지 않는다"고 정해 두었다.

'코어'·'물먹은' 같은 말이 못 옮겨지는 이유는 두 가지로 갈린다.
- **'물먹은'**: Kiwi가 대개 물 + 먹다 + -은으로 자른다(이 문장으로 직접 돌려 보지는 않았다). 두 형태소 모두 사전의 속성어가 아니다. '젖음·무거움'이라는 뜻은 관용 결합에만 있다. 우리말샘·표준국어대사전에 '물먹다'가 표제어로 있는지는 확인 필요.
- **'코어'**: 외래어이고 뜻이 여러 갈래다(중심, 핵, 몸통 근육 등). 형태소 분석으로는 풀리지 않는다. 의미 자원(어휘망·임베딩)이 있어야 후보를 낼 수 있는데, 그 후보는 시스템의 추정이다.

## A. 규범(norm) 자료: 낱말 → 지각·정서 속성

규범은 사람들이 낱말마다 매긴 평정의 평균이다. 고정된 표이므로 조회는 결정적이다. 다만 **조회 결과를 슬롯 값으로 쓰면 원칙 2와 부딪힌다.** 참여자가 '불안'이라고만 했는데 표가 "각성 0.8"을 주면, 그것은 참여자가 한 말이 아니라 집단 평균에서 끌어온 추정이다. 지금 `vad_ko`를 `_inferred`에만 두는 이유가 이것이다.

| 자원 | 규모·내용 | 라이선스 | 한국어 | 로컬·결정론 | 원칙 1/2 | 도입 비용 | 출처 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Lancaster Sensorimotor Norms | 영어 39,707개, 지각 6(촉각·청각·후각·미각·시각·내수용) + 행위 5 차원 | 논문은 CC BY 4.0. OSF 데이터 자체의 라이선스는 확인 필요 | 없음(영어) | 파일 조회, 결정적 | 값으로 쓰면 원칙 2 충돌. "말한 감각어가 어느 감각인지" 분류 근거로는 쓸 만함 | 번역·검수 필요 | https://pmc.ncbi.nlm.nih.gov/articles/PMC7280349 , https://osf.io/7emr6/ |
| 한국어 지각 강도 규범(Lee & Shin 2023) | 한국어 1,000개(영어 목록의 번역 대응어), 시각·청각·촉각·미각·후각·내수용 6감각 | 데이터 라이선스 표기 없음 → 확인 필요 | **있음** | 결정적 | 위와 같음 | 작음. 1,000개라 면담 어휘와 겹치는 정도는 확인 필요 | https://pmc.ncbi.nlm.nih.gov/articles/PMC10395129/ , https://github.com/coolmintmild/materialrepository |
| Glasgow Norms | 영어 5,553개, 9차원(정서가·각성·지배·구체성·심상성·친숙도·습득 연령·**의미적 크기**·성별 연합) | 저장소 기록상 CC BY. 데이터 파일 조건은 확인 필요 | 없음 | 결정적 | 값으로 쓰면 충돌 | 번역 필요 | https://link.springer.com/article/10.3758/s13428-018-1099-3 |
| NRC VAD Lexicon v2.1 | 영어 55k 이상(v1은 2만 이상), V/A/D 각 0–1, Best-Worst Scaling | 비상업 연구·교육 무료, **재배포 금지**, 상업은 문의 | Google 번역(2022년 8월) 기계 번역본 있음. 잘못된 번역·음차가 섞일 수 있다고 명시 | 결정적 | 값으로 쓰면 충돌. 재배포 금지라 저장소에 파일을 넣을 수 없음 | 번역본 검수 비용 큼 | https://www.saifmohammad.com/WebPages/nrc-vad.html , https://arxiv.org/abs/2503.23547 |
| 한국어 감정 단어 목록(박인조·민경환) | 434개, 원형성·친숙도·정서가·각성. HF 미러는 868행 | HF 미러는 CC0 표기(원 논문 데이터 권리는 확인 필요) | 있음 | 결정적 | `vad_ko` 초안을 바꿀 후보. `_inferred`에만 쓰면 충돌 없음 | 작음 | https://huggingface.co/datasets/jonghwanhyeon/korean-emotion-lexicon |
| 한국어 정서단어 목록(홍 외 2016) | 450개, 정서가·각성가·구체성 | 내려받기·라이선스 확인 필요 | 있음 | 결정적 | 위와 같음 | 작음 | https://koreascience.kr/article/JAKO201630932329075.page |
| EVOKE(2026) | 한국어 1,427개·영어 1,399개 감정 어휘, 한국어 형용사·동사 819개 주석 | CC BY-NC 4.0(README 배지) | 있음 | 결정적 | V/A 평정이 있는지는 확인 필요 | 작음 | https://github.com/yoonwonj/EVOKE , https://arxiv.org/abs/2602.10414 |
| KNU 한국어 감성사전 | 긍·부정 극성 사전(Bi-LSTM으로 구축) | 원 저장소 라이선스 확인 필요(R 래퍼는 CC0) | 있음 | 결정적 | 극성만 있어 형상 속성과 거리가 멂 | 작음 | https://rdrr.io/github/mrchypark/KnuSentiLexR/ |
| Emotion Evaluator(Lee 외 2022) | 사전 뜻풀이로 한국어 낱말의 정서가·각성을 예측하는 신경망 | 논문 CC BY 4.0. 결과 사전 공개 여부 확인 필요 | 있음 | 학습 모델 | 학습 모델 출력이라 원칙 1 쪽에 가까움 | — | https://escholarship.org/uc/item/20s0r7c1 |
| 국제 색-감정 연합(Jonauskaite 외 2020) | 30개국 4,598명, 색 이름 12개 × 감정 20개 | FORS 데이터셋은 학술 연구·교육용 공개 | **한국 표본 포함 여부 확인 필요** | 결정적 | 감정 → 색을 정하면 원칙 2 정면 충돌(말하지 않은 색). 쓸 수 있다면 분석용 | 작음 | https://doi.org/10.1177/0956797620948810 , https://doi.org/10.23662/FORS-DS-888-2 |
| bouba/kiki 25개 언어(Ćwiek 외 2022) | 25개 언어·9개 어족·10개 문자 체계에서 효과 확인(중국어·루마니아어·터키어 등 일부 언어는 약함) | 논문 | 한국어 포함 여부 확인 필요 | — | 소리 → 모양 규칙의 근거 문헌. 낱말의 소리로 모양을 정하면 원칙 2 충돌 | — | https://pmc.ncbi.nlm.nih.gov/articles/PMC8591387 |
| 모양-정서 연합 | 곡선은 더 긍정·덜 각성, 각진 모양은 각성·위협과 연합(2D 도형·선 그림 연구) | 논문 | 한국어 아님 | — | 정서 → 모양 규칙의 근거. 값으로 쓰면 원칙 2 충돌 | — | Pacheco 외 2015: https://portalrecerca.uab.cat/ca/publications/two-dimensional-shapes-for-emotional-interfaces-assessing-the-inf/ ; "Negative triangles"(Emotion 2012): https://pubmed.ncbi.nlm.nih.gov/21787078/ ; Damiano 외 2021: https://www.nature.com/articles/s41598-021-99044-y ; Collier 1996: https://link.springer.com/doi/10.1007/BF02251005 |
| 한국어 의성·의태어 음상징 | 양성·음성 모음 대립(밝음·작음 대 어두움·큼)이 의태어에 가장 잘 남아 있음. 예사·거센·된소리 자음이 세기 차이를 냄 | 논문 | **있음** | 형태 규칙이라 결정적 | 사전 낱말의 **변이형**을 같은 값 + 정도 보정으로 받는 데 쓸 수 있음(아래 B절) | 규칙 몇십 줄 | Kwon 2018(Laboratory Phonology 9), Larsen & Heinz 2012(Phonology 29), "Iconicity in Korean consonantal symbolism": https://core.ac.uk/works/25126900 ; 모음조화 현황: https://mdpi.com/2226-471X/8/3/172 |
| 온도·무게·질감 은유 자료 | 한국어로 정리된 공개 표는 찾지 못함. Lancaster의 촉각 차원, Glasgow의 의미적 크기가 부분적으로 닿음 | — | 없음 | — | — | — | 확인 필요 |

**정리.** 한국어 규범은 수백~1,000개 규모라 면담의 자유 묘사를 덮기에 작다. 큰 규범은 영어이고 번역을 거쳐야 하며, NRC VAD는 재배포가 막혀 있다. 무엇보다 규범은 "그 낱말을 들은 사람들의 평균 연상"이라서 슬롯 값으로 쓰면 원칙 2를 깬다. 쓸 수 있는 곳은 세 군데다. (1) `vad_ko` 초안을 검증된 한국어 자료로 바꾸기(`_inferred` 전용), (2) 연구자가 사전 항목을 만들 때 참고하는 근거, (3) 의태어 변이형의 정도 보정 같은 형태 규칙.

## B. 닫힌 사전을 결정적으로 넓히기

### B-1. 형태 규칙(학습 모델 없음, 가장 안전)

| 방법 | 무엇을 넓히나 | 원칙 1/2 | 자원 |
| --- | --- | --- | --- |
| 어간·활용(이미 씀) | 무거워요 → 무겁 | 충돌 없음 | Kiwi |
| 파생 접사 표 | -스럽다·-하다·-거리다·-대다·-이다(반짝거리다·반짝대다·반짝이다 → 반짝), 접두 연-·진-·반- | 충돌 없음. 접사 표도 사전처럼 버전 관리 | 직접 작성 |
| 의태어 모음·자음 교체 | 오돌토돌 ↔ 우둘투둘 ↔ 오톨도톨, 반짝 ↔ 번쩍 ↔ 빤짝. 사전에 뿌리가 하나 있으면 변이형을 같은 범주로 받고, 양성·음성, 예사·거센·된소리로 크기·세기를 조금 보정 | 뿌리가 사전에 있을 때만 쓰면 충돌 없음. 보정 폭은 연구자가 정함 | A절 음상징 문헌 |
| 반복·축약형 | 까끌까끌 ↔ 까끌, 울퉁불퉁 ↔ 울퉁 | 충돌 없음 | 직접 작성 |
| 관용 결합 표 | 물먹다(젖음·무거움), 속이 타다 같은 결합 | 연구자가 표를 만들면 충돌 없음. 뜻풀이를 사람이 정하는 것이 곧 사전 작업 | 우리말샘 뜻풀이를 참고 |

v1 오버레이에 이미 '오돌토돌·오톨도톨·우둘투둘'이 따로따로 들어가 있다. 변이 규칙이 있으면 이런 항목을 뿌리 하나로 줄일 수 있다.

### B-2. 공개 어휘 자원

| 자원 | 규모 | 라이선스 | 한국어 | 로컬 | 쓸 수 있는 곳 | 출처 |
| --- | --- | --- | --- | --- | --- | --- |
| Kiwi / kiwipiepy | 형태소 분석기. 간단한 오타 교정(0.13.0 이후), 분석 불능은 UN 태그 | **Apache 2.0**(0.23.2 이하 버전은 LGPL). 저장소 요구 버전(`kiwipiepy>=0.20`)에 따라 적용 라이선스가 다름 | 있음 | 로컬 | 이미 0층. 낱말 유사도 기능이 있는지는 확인 필요 | https://github.com/bab2min/Kiwi , https://github.com/bab2min/kiwipiepy |
| MeCab-ko-dic | 형태소 사전 | Apache 2.0 | 있음 | 로컬 | Kiwi 교차 확인용 | https://formulae.brew.sh/formula/mecab-ko-dic |
| Okt(open-korean-text) | 형태소 분석기 | 확인 필요 | 있음 | 로컬(JVM) | 이점 적음 | 확인 필요 |
| 우리말샘 | 표제어 1,229,827개. 비슷한말·반대말·상위어·하위어 관계가 구축돼 있음 | **CC BY-SA 2.0 KR**(상업 이용 가능, 출처 표시, 변경 시 같은 조건). 출처가 있는 용례는 원저작자 권리 | 있음 | Open API는 외부 전송이라 실행 경로에 불가. 공식 전체 내려받기 경로는 확인 필요(제3자 HF 미러 있음) | 오프라인 후보 생성: 사전 표제어의 비슷한말·하위어를 끌어와 연구자가 검토 | https://opendict.korean.go.kr/service/dicStat , https://opendict.korean.go.kr/service/copyrightPolicy |
| KorLex 1.5(부산대) | 명사·동사·형용사·부사·분류사. Princeton WordNet(PWN)을 참조 모델로 구축 | 확인 필요 | 있음 | 확인 필요 | 상위어로 "이 명사는 그릇류인가" 판정. PWN 연결로 영어 3D 자산 범주와 다리 | https://koreascience.kr/article/JAKO200906942467135.page |
| KAIST CoreNet | 약 73,000 의미, 일본 NTT Goidaikei 개념 체계에 연결 | 배포·라이선스 확인 필요(2005년 책 3권 출간 기록) | 있음 | 확인 필요 | 위와 같음 | https://aclanthology.org/L18-1165.pdf |
| KWN(한국어 워드넷) | PWN 3.0·일본어 워드넷 1.1 기반 반자동 구축, 117,659 동의어 집합의 약 54% 번역 | 배포 위치·라이선스 확인 필요 | 있음 | 확인 필요 | 위와 같음 | https://www.koreascience.kr/article/CFKO201408355727305.pdf |
| ConceptNet 5.7 / Numberbatch 19.08 | 다국어 상식 그래프. Numberbatch는 78개 언어 코드 | CC BY-SA 4.0 | 한국어 노드 있음. 한국어 간선 수·어휘 크기 확인 필요 | 덤프 내려받아 로컬 | "X는 Y처럼 생겼다" 같은 관계 후보. 한국어 품질 미확인 | https://github.com/commonsense/conceptnet-numberbatch , https://zenodo.org/records/1165009/latest |
| fastText cc.ko.300 | Common Crawl + 위키백과, 300차원, CBOW, 문자 5-gram. `.bin`은 미등록어도 부분 문자열로 벡터를 만듦 | CC BY-SA 3.0 | 있음 | 로컬. 파일 크기 확인 필요 | 미등록어 → 사전 표제어 최근접 후보 | https://fasttext.cc/docs/en/crawl-vectors |

### B-3. 정적 임베딩 최근접 대응은 '생성형 AI 없음 · 화이트박스 · 결정론'에 해당하는가

나누어 보면 이렇다.

| 요건 | 정적 임베딩(fastText 등) 최근접 | 판단 |
| --- | --- | --- |
| 생성형 AI가 아님 | 텍스트·형상을 만들어 내지 않는다. 고정된 벡터 표에서 코사인 최근접을 찾을 뿐이다 | **해당**. 생성 모델이 아니다 |
| 결정론 | 파일 hash를 고정하고, 동점일 때 사전순으로 고르고, 부동소수 합산 순서를 고정하면 같은 입력 → 같은 출력 | **해당**(구현 조건이 붙음). 학습은 비결정적이어도 배포 파일은 고정이다 |
| 로컬·digest 고정 | 파일을 내려받아 sha256으로 기록 | **해당** |
| 화이트박스(원칙 1의 "사전·규칙") | 300차원 벡터가 왜 '코어'를 '중심' 옆에 두는지 사람이 읽을 수 없다. 웹 말뭉치의 함께 쓰임 통계다 | **해당하지 않음**. 대응 결과 표는 검토할 수 있어도 대응 근거는 블랙박스다 |
| 원칙 2(말하지 않은 것을 추론하지 않음) | '코어' → '중심'은 참여자가 '중심'이라고 말한 것이 아니다. 거리 1의 자모 퍼지에서도 '설명' → '선명' 같은 오대응이 나왔는데, 임베딩은 반의어(뜨겁다·차갑다)를 가깝게 두는 성질이 알려져 있어 위험이 더 크다 | **충돌**. 값으로 쓰면 안 된다 |

그래서 결론은 지금의 자모 퍼지와 같은 지위다. **실행 시점에 쓰더라도 `_alternatives`(source `embedding_nn`, 점수, 모델 digest, 후보 표제어)까지만 남기고 슬롯 값·`_inferred`에는 넣지 않는다.** `docs/mapping-failures.md` 7절이 이미 임베딩 유사도를 장면 속성 경로에서 뺐으므로, 이 결론은 그 결정과도 맞는다.

확인 질문으로 되묻는 데에도 제약이 있다. 원칙 3은 면담자가 참여자가 쓰지 않은 묘사어를 내보내지 못하게 한다. 그래서 "'코어'가 '중심' 같은 건가요?"라고 물을 수 없고, 되물을 수 있는 것은 참여자의 말('코어')뿐이다. 임베딩 후보는 면담 문장이 아니라 **연구자 검토 자료**나 **화면의 닫힌 후보**(F절)로만 쓸 수 있다.

**선례(임계값·출처 표시).**
- 씨앗 낱말 + 임베딩 그래프 전파로 감성 사전을 넓히고, 부트스트랩 표준편차를 신뢰도로 붙인 SentProp(Hamilton 외 2016). 씨앗은 사람이 고른다. https://aclanthology.org/D16-1057 , https://nlp.stanford.edu/projects/socialsent/
- 임베딩으로 정서가·각성·구체성 규범을 외삽하면 정서가에서 r ≈ .89까지 나온다는 보고(Vankrunkelsven 외, 2차 인용이라 원문 확인 필요). 임베딩을 Lancaster 11차원에 사영한 SENSE(2026). https://arxiv.org/abs/2602.00469
- NRC VAD 번역본은 "기계 번역이며 틀릴 수 있다"고 자원 페이지에 출처를 밝힌다. 출처를 표시하는 최소 형태로 참고할 만하다. https://www.saifmohammad.com/WebPages/nrc-vad.html
- 저장소 안의 선례: 자모 퍼지(`_alternatives`, `needsConfirmation`)와 G15의 출처 네 가지(말함/고름/고침/기본값). 임베딩 후보도 같은 틀에 `source` 하나를 더하면 된다.

## C. 구체 명사 → 공개 3D 자산 검색(생성 아님)

명사 → 자산 ID 표를 사람이 만들면 같은 말 → 같은 자산이라 원칙 1을 지킨다. 다만 자산에 딸린 세부(손가락 모양, 병의 목 길이)는 참여자가 말하지 않은 것이다. `docs/gen3d-feasibility.md` 2.4절이 말한 대로 "자산 기본값"으로 기록해야 한다.

| 자원 | 규모 | 라이선스 | 이름표 | 로컬 | 원칙 1/2 | 도입 비용 | 출처 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Poly Haven | 모델·텍스처·HDRI(모델 수는 확인 필요) | **CC0**. 로고·렌더 이미지는 제외. API는 별도 약관, 긁어 오기는 허락 필요 | 영어 이름·태그 | 손으로 내려받아 저장소 밖 또는 검수 뒤 포함 | 표가 있으면 충돌 없음 | 사실적 스캔이 많아 중립 모형 원칙과 맞추는 데 손이 감 | https://polyhaven.com/license |
| Kenney | 게임용 자산 묶음 | **CC0**(로고 단독 사용만 제한) | 영어 파일명 | 로컬 | 충돌 없음 | 저폴리 양식이 통일돼 있어 Quest에 가벼움. 3D 형식은 묶음마다 확인 필요 | https://kenney.nl/support |
| Quaternius | 저폴리 묶음 | 묶음마다 **CC0 또는 QAL**(QAL은 직접 재판매 금지) | 영어 | 로컬. FBX·.blend 제공, glTF 여부 확인 필요 | 충돌 없음 | 묶음별 라이선스 파일 확인 | https://quaternius.com/faq.html |
| Google Scanned Objects | 가정용품 스캔 1,030개, 약 13 GB | CC BY 4.0 | 영어 | 로컬 | 충돌 없음(자산 기본값 기록 필요) | 제품 상표가 보이는 사실적 스캔이라 면담 심상과 결이 다름 | https://research.google/blog/scanned-objects-by-google-research-a-dataset-of-3d-scanned-common-household-items/ |
| Objaverse 1.0 | 80만 개 이상. 이름·설명·태그 메타데이터. **Objaverse-LVIS**: 4.7만 개를 1,156개 LVIS 범주에 사람이 검수해 배정 | 데이터셋 전체 ODC-By 1.0, 객체마다 CC(BY 721K · BY-NC 25K · BY-NC-SA 52K · BY-SA 16K · CC0 3.5K) | 영어. LVIS 범주는 WordNet 동의어 집합과 이어져 있어 KorLex·KWN으로 한국어 이름을 붙일 다리가 있음 | 미리 받아 로컬 | 표 + 검수가 있으면 충돌 없음 | 품질·양식이 제각각이라 검수 비용 큼. 객체별 라이선스 추적 필요 | https://huggingface.co/datasets/allenai/objaverse , https://arxiv.org/abs/2212.08051 |
| Objaverse-XL | 1,000만 개 이상으로 알려짐 | 출처별로 섞임 | — | — | — | 검수 불가능한 규모 | 확인 필요 |
| ShapeNetCore | 55범주, 약 51,300개. 모델마다 WordNet 3.0 동의어 집합 | **비상업 연구·교육 한정** 약관, 원저작권은 원작자, 접근 철회 가능 | WordNet 연결 | 로컬 | 충돌 없음 | 약관상 공개 배포물에 넣기 어려움 | https://shapenet.org/terms , https://huggingface.co/datasets/ShapeNet/ShapeNetCore |
| Sketchfab API | — | — | — | **실행 중 외부 전송이라 원칙 5 위반** | — | 쓰지 않음 | — |

**한국어 이름표 문제.** 어느 자원도 한국어 이름이 없다. 길은 둘이다. (1) 소규모 라이브러리(수십~수백 개)를 연구자가 직접 고르고 `base_shapes`처럼 한국어 표제어 표를 손으로 만든다. (2) WordNet 동의어 집합 → KorLex/KWN 대응으로 후보 이름을 뽑고 연구자가 고친다. KorLex·KWN의 라이선스가 확인되지 않아 지금은 (1)이 현실적이다.

## D. 절차적 형상 생성(AI 아님)

절차 생성은 **어휘를 넓히지 않는다.** 이미 슬롯에 들어간 값을 더 다양하게 그리는 표현력을 넓힐 뿐이다. 그래도 `docs/gen3d-feasibility.md`가 확인했듯 지금 규칙 경로가 가장 못 그리는 분위기·재질 유형(선·엉킴, 젖은 종이, 처짐, 안개)을 덮는 데는 이 길이 가장 싸다.

| 기법 | 무엇을 그리나 | 매개변수 | 출처 |
| --- | --- | --- | --- |
| superquadric(Barr 1981) | 구 ↔ 정육면체 ↔ 팔면체 사이, 납작·길쭉 | 지수 2개 + 축 비율 3개 | https://doi.org/10.1109/MCG.1981.1673799 |
| superformula(Gielis 2003) | 꽃잎·별·불가사리처럼 대칭 돌기 | m(대칭 수), n1–n3(뾰족함), a·b | American Journal of Botany 90(3):333–338, https://wwwuser.gwdg.de/~groimp/grogra.de/gallery/Technics/Supershape.html |
| 메타볼·SDF + 마칭 큐브(Blinn 1982; Lorensen & Cline 1987) | 덩어리 여러 개, 돌기, 구멍, 녹아 붙음 | 중심·반지름·혼합 정도 | https://doi.org/10.1145/357306.357310 , https://doi.org/10.1145/37402.37422 |
| 스플라인 튜브 | 선·실·끈·엉킴·매듭 | 경로, 두께, 꼬임 | Unity Splines 아래 |
| L-system | 가지·뻗음·자람 | 규칙, 반복 수, 각도 | https://algorithmicbotany.org/papers/#abop |
| 노이즈 변위 | 거칠기·울퉁불퉁·침식(지금 셰이더가 이미 씀) | 진폭·주파수 | `unity/README.md` |

**Unity 구현체.** 이 프로젝트는 Unity 6000.0.85f2이고 `Packages/manifest.json`에 URP 패키지가 없다(내장 렌더 파이프라인). 그래서 URP 지원 여부보다 Quest 빌드에서 도는지가 관건이다.

| 구현체 | 하는 일 | 라이선스 | 런타임·Quest | 출처 |
| --- | --- | --- | --- | --- |
| Unity Splines(`com.unity.splines`) | `SplineExtrude`가 런타임에 스플라인을 튜브 메시로 만듦. `SplineMesh`로 코드에서 압출 | Unity 패키지 약관(확인 필요) | 런타임 지원. Quest 성능 확인 필요 | https://docs.unity3d.com/Packages/com.unity.splines@2.8/api/UnityEngine.Splines.SplineExtrude.html |
| keijiro/Metamesh | 기본 도형(둥근 상자, 고리, 원판, 이코스피어 등) 생성 | Unlicense | 에셋 임포터 방식이라 에디터 시점 생성으로 보임(확인 필요) | https://github.com/keijiro/Metamesh |
| Syomus/ProceduralToolkit | `MeshDraft` 메시 빌더, 기본 도형, 노이즈, 마칭 스퀘어 | MIT | 요구 Unity 버전 확인 필요(가져온 요약에는 6.6 이상으로 나와 이 프로젝트와 안 맞을 수 있음) | https://github.com/Syomus/ProceduralToolkit |
| Scrawk/Marching-Cubes | 마칭 큐브·마칭 사면체 | MIT | CPU/GPU 여부 확인 필요 | https://github.com/Scrawk/Marching-Cubes |
| SebLague/Marching-Cubes | 마칭 큐브(지형 예제) | MIT | compute shader 여부·Quest 확인 필요 | https://github.com/SebLague/Marching-Cubes |
| SuperFormula3D-Unity(ondeowl) | compute shader로 superformula 3D 메시 | 확인 필요 | 확인 필요 | 저장소 원문 미확인(집계 사이트에서만 봄) |

**속성 → 형상 매개변수 규칙의 선례.** 정서·모양 연구는 대부분 2D 도형이다. 곡률·각도·대칭·움직임을 바꿔 정서가·각성 평정을 받은 연구(Pacheco 외 2015), 각진 모양은 흥분·놀람, 둥근 모양은 안도와 짝지어진 연구(Perception 2017, https://journals.sagepub.com/doi/abs/10.1177/0301006617731048), 단순 도형이 정서가를 전한다는 연구("Negative triangles", Emotion 2012), 선 그림의 방향·길이·각짐 통계가 정서가·위협 판단에 영향을 준다는 연구(Damiano 외 2021)가 있다. 사용자가 유연한 표면으로 감정을 표현할 때 형상 매개변수가 정서의 긍·부정을 따라가고, 시각 은유에 기댄 상징적 모양도 많이 나왔다는 CHI 2016 연구(Strohmeier 외, https://doi.org/10.1145/2858036.2858537)도 있다. VR 정서 시각화 개관으로는 Pinilla 외 2021(https://doi.org/10.3389/frvir.2021.630731)이 있다. **절차적으로 만든 3D 형상에 대한 정서 평정 연구는 이번 검색에서 찾지 못했다(확인 필요).**

원칙과의 관계는 분명하다. 이 문헌들은 "정서 → 모양"을 말하지만, 참여자가 모양을 말하지 않았는데 감정어로 모양을 정하면 원칙 2 위반이다. 규칙 대응은 **참여자가 직접 말한 모양어·정도어 → 매개변수**(예: '뾰족뾰족' → superformula n1을 낮게, '살짝' → 진폭 ×0.6)에만 쓰고, 문헌은 그 대응표를 짤 때의 근거로만 쓴다.

## E. 생성형이지만 로컬·고정 가능한 것(비교용)

`docs/gen3d-feasibility.md` 1절의 결론을 그대로 옮긴다.
- Shap-E(문장당 약 3초)와 SDXL → TripoSR(약 7.6초)를 로컬에서 끝까지 연결했고, seed를 고정하면 GLB가 바이트까지 같았다(120/120).
- 그러나 30문장 × 4조합 120개 중 문장과 맞은 것은 4개였고, 규칙 경로가 못 그리는 안개·선·종이·천·유리는 생성형도 실패했다. 외형 서술이 없는 답에도 형상을 지어냈다.
- 원칙 1·2와 정면으로 충돌하므로 본 실험에는 쓰지 않고, 절차적 확장 + 검수 자산을 권한다.

결정론(seed 고정)은 원칙 1의 "같은 텍스트 → 같은 결과"는 채우지만 "사전·규칙만"과 원칙 2는 채우지 못한다. 결정론과 화이트박스는 다른 요건이다. B-3절의 임베딩도 같은 이유로 값 경로에 못 들어간다.

## F. 참여자가 직접 고치는 방식(추론 없이 열린 표현)

시스템이 추론하지 않고 표현을 넓히는 유일한 길은 **참여자가 직접 정하게 하는 것**이다. 저장소에는 이미 후보 고르기와 일곱 항목 조절, 출처 네 가지(말함/고름/고침/기본값) 기록이 있다(G15·G31). 문제는 조절할 수 있는 값이 닫힌 표 안에 있다는 점이다.

| 선행 연구 | 무엇을 했나 | 이 연구에 주는 것 | 출처 |
| --- | --- | --- | --- |
| Mood Worlds(Wagener 외, CHI 2022) | 수정한 Open Brush로 참여자가 감정을 표현하는 가상 환경을 직접 만듦(N=16). 스스로 만드는 과정이 긍정 정서와 웰빙을 높였다고 보고 | 미리 정한 장면 대신 자율 창작. 다만 결과물은 환경이지 단일 물체가 아님 | https://doi.org/10.1145/3491102.3501861 |
| Painimation(JMIR 2018) | 단어·숫자 척도 대신 추상 애니메이션을 골라 통증을 표현(N=170). 80.2%가 의료진과 소통하는 데 쓰겠다고 답함. 고른 애니메이션이 McGill 통증 형용사와 맞았음 | **닫힌 시각 후보에서 고르기**도 말로 하기 어려운 감각을 옮기는 데 통한다는 근거 | https://jmir.org/2018/8/e10056 |
| Strohmeier 외(CHI 2016) | 사용자가 유연한 표면으로 감정 형상을 직접 만들고, 그 형상이 감정을 전달하는지 평가 | 사용자가 만든 형상 매개변수가 정서가를 따라감. 직접 조형 UI의 근거 | https://doi.org/10.1145/2858036.2858537 |
| 만성 요통 VR 임상시험 동의서(NCT04468074) | 연구 담당자와 함께 참여자가 통증의 3D 표상을 VR에서 만드는 개인화 단계 | 통증 외부화를 참여자 주도로 만든 예. 형상·색 조작 방식은 문서에 없음 | https://cdn.clinicaltrials.gov/large-docs/74/NCT04468074/ICF_000.pdf |
| Hacmun·Regev·Salomon(2018) | VR 미술치료의 원칙(현전·몰입·시점·관점) | 치료 맥락이라 원칙 8상 범위 밖. UI 설계 원칙만 참고 | https://doi.org/10.3389/fpsyg.2018.02082 |
| Pinilla 외(2021) | 추상 도형이 개인 연상을 줄인다는 이유로 VR 정서 시각화에 추상 형상을 씀 | 구체 자산(C절)보다 추상 매개변수 형상이 중립적일 수 있다는 근거 | https://doi.org/10.3389/frvir.2021.630731 |

원칙과 관련해 세 가지를 정해야 한다.
1. 참여자가 손으로 정한 값은 '말함'이 아니라 '고침'이다. G15대로 `_provenance`에 섞지 않으면 원칙 2와 충돌하지 않는다.
2. 화면에 닫힌 후보를 보여 주는 것은 면담자의 "예시·선택지 제시 금지"(원칙 3)와 다른 단계지만 같은 걱정, 곧 유도 편향을 낳는다. 지금 후보 단계가 이미 이 문제를 안고 있으므로 같은 기준으로 다룬다.
3. 조절할 수 있는 항목을 절차적 형상 매개변수(D절)로 넓히면 "참여자의 말이 얼마나 그대로 그려졌나"를 재는 측정과 "참여자가 고친 뒤의 모습"이 섞인다. 측정 시점(조절 전 spec)과 최종 모습을 따로 기록해야 한다. 지금 `selection.json` 구조가 이를 지원한다.

## 질문에 대한 답

**AI 없이 할 수 있는 것.**
- **사전 낱말의 변이형 받기.** 파생 접사, 의태어 모음·자음 교체, 반복·축약, 관용 결합 표는 모두 형태 규칙이라 결정적이고 화이트박스다. '오돌토돌'의 변이형이나 '반짝이다·반짝거리다'처럼 뿌리가 사전에 있는 말은 이것으로 대부분 덮인다.
- **사전을 오프라인에서 빨리 키우기.** 우리말샘 관계(비슷한말·하위어), 임베딩 최근접, 한국어 규범을 **연구자에게 후보를 보여 주는 도구**로 쓰고, 승인한 것만 사전 버전을 올린다. 실행 경로는 닫힌 표 그대로라 원칙 1·2가 유지된다.
- **구체 명사를 검수한 CC0 자산 표로 그리기.**
- **말한 값을 더 풍부하게 그리기.** 절차적 형상으로 선·엉킴·판·처짐·돌기·구멍을 매개변수로 그린다.
- **참여자가 직접 정하기.** 말하지 않은 속성을 시스템이 채우지 않고 참여자가 고르거나 고친다.

**AI 없이 할 수 없는 것(또는 원칙을 깨야 하는 것).**
- **처음 보는 말의 뜻을 실행 시점에 스스로 알아내 형상으로 옮기기.** 이것이 질문의 '자율적 시각화'이고, 학습된 통계 모델 없이는 안 된다. '코어'·'물먹은'이 그렇다.
- 정적 임베딩은 생성형이 아니고 결정적으로 만들 수 있다. 그러나 근거가 블랙박스이고 결과가 참여자가 하지 않은 말이라 원칙 1의 "사전·규칙"과 원칙 2를 채우지 못한다. 쓸 수 있는 자리는 `_alternatives`(확인 필요)와 연구자 검토 자료뿐이다.
- 감정어로 색·모양을 정하는 일(규범·색-감정 연합)은 AI 여부와 상관없이 원칙 2 위반이다.
- 추상 관계('자기와 바깥의 관계', '중심과 경계')는 어느 방법으로도 "말한 대로" 그리지 못한다(`docs/gen3d-feasibility.md` 2.4절과 같은 결론).

한 줄로 줄이면, **"닫힌 사전을 넘어선다"는 것은 실행 시점의 자율 해석이 아니라 (사람이 승인하는) 사전 확장 속도와 (참여자가 정하는) 표현 범위를 넓히는 일로 바꿔야 원칙 안에 들어온다.**

## 원칙을 깨지 않는 개발 방향 후보

### 1. 형태 변이 규칙층(0.5층) 추가

- **만드는 것**: Kiwi 다음, 1층 사전 앞에 결정적 변이 규칙을 둔다. 파생 접사 표(-거리다·-대다·-이다·-스럽다·-하다), 의태어 모음 교체(ㅗ↔ㅜ, ㅏ↔ㅓ)와 자음 교체(예사↔거센↔된소리), 반복형 축약을 다룬다. 뿌리가 사전에 있을 때만 그 값을 받고, 정도 보정(양성 = 작게·가볍게, 된소리 = 세게)은 연구자가 정한 표로 한다. provenance에 `+variant(<규칙>;root=<뿌리>)` 꼬리표를 붙인다.
- **자원**: Kiwi(Apache 2.0), 한국어 음상징 문헌(Kwon 2018 외).
- **위험**: 과잉 일치(우연히 같은 꼴인 다른 낱말). 자모 퍼지에서 나온 '설명' → '선명' 같은 오대응이 생길 수 있으니 허용 교체 쌍을 좁게 두고 반례 테스트로 고정해야 한다. 음상징 정도 보정은 관습이라는 반론이 있어(자음 상징 논문) 보정 폭을 작게 두거나 생략해야 한다.

### 2. 연구자 승인형 사전 확장 도구(오프라인)

- **만드는 것**: 세션·합성 코퍼스에서 쌓인 `_unmapped`·`_unmatched`·`_alternatives`를 모아, 미등록어마다 근거 후보를 뽑는 스크립트를 만든다. 근거는 우리말샘 비슷한말·상위어, fastText 최근접 상위 k개와 점수, 한국어 규범 값이다. 연구자가 받기/버리기/새 값을 고르면 사전 오버레이 파일(`src: "v3-review"`, 근거 자원·점수·검토자·날짜)을 만든다. 실행 경로는 바뀌지 않는다.
- **자원**: 우리말샘(CC BY-SA 2.0 KR), fastText cc.ko.300(CC BY-SA 3.0), 박인조·민경환 목록(HF 미러 CC0), Lee & Shin 2023 지각 강도 규범(라이선스 확인 필요).
- **위험**: (a) ShareAlike. 우리말샘 뜻풀이나 관계 데이터를 사전 파일에 옮겨 적으면 그 파일에 BY-SA 조건이 붙을 수 있다. 낱말 자체와 연구자가 정한 값만 넣고 원문 뜻풀이는 넣지 않는 편이 안전하다(법률 판단은 확인 필요). (b) 참여자 데이터를 쓰면 원칙 6에 따라 미등록어 목록 자체를 git 밖에 두어야 한다. (c) 확장은 사람 시간에 묶여 느리고, 참여자 고유의 은유는 여전히 못 옮긴다. (d) 실행 시점에 임베딩 후보를 `_alternatives`로 내는 선택지도 여기에 붙일 수 있으나, 값·`_inferred`·면담 문장에는 쓰지 않는다.

### 3. 절차적 형상 문법 + 검수 CC0 자산(말한 값의 표현력 확장)

- **만드는 것**: `docs/gen3d-feasibility.md` 11절 권고를 이어받는다. 스플라인 튜브(선·엉킴·매듭), 노이즈 판(천·종이·처짐), superquadric·superformula(납작·길쭉·뾰족·돌기), 메타볼(덩어리 여러 개·구멍)을 만들고, **말한 모양어·정도어 → 매개변수** 표를 화이트박스로 둔다. 말하지 않은 매개변수는 기본값으로 두고 `defaultsUsed`에 기록한다. 구체 명사는 수십 개 규모의 Kenney/Quaternius/Poly Haven CC0 자산을 손으로 고르고, 한국어 표제어 표 → 자산 ID로 잇는다(지금 glTFast 로더 재사용).
- **자원**: Unity Splines, ProceduralToolkit(MIT, 버전 확인 필요), Metamesh(Unlicense), Kenney·Poly Haven(CC0), Quaternius(CC0/QAL).
- **위험**: 어휘는 늘지 않는다(이미 사전에 있는 말만 더 잘 그림). Quest 프레임 비용(compute shader·메시 재생성)을 확인해야 한다. 자산의 세부는 말하지 않은 내용이므로 '자산 기본값' 기록이 빠지면 원칙 2가 깨진다. 정서 → 모양 문헌을 값 규칙으로 잘못 쓰지 않도록 대응표 검토가 필요하다.

### 4. 참여자 직접 조절의 확장(열린 표현은 참여자가)

- **만드는 것**: 지금의 일곱 항목 조절에 3번의 형상 매개변수(뾰족함·처짐·엉킴·덩어리 수 등)를 슬라이더로 더한다. 사전에 없는 말이 나온 슬롯은 비워 둔 채 "참여자가 쓴 말 그대로"를 이름표로 보여 주고(예: 「'코어'」), 참여자가 형태·질감 후보를 고르거나 슬라이더로 정하게 한다. 출처는 '고름/고침'으로 남는다.
- **자원**: 기존 selection 흐름(`chatbot/ifs_chatbot/selection.py`, `web/stage.js`), Painimation·Mood Worlds·Strohmeier 2016 같은 선행 설계.
- **위험**: 후보·슬라이더의 기본 위치가 유도 편향을 만든다(원칙 3의 정신). 측정이 섞이지 않게 조절 전 spec과 최종 모습을 나눠 기록해야 한다. VR에서 조작할 항목이 늘면 시간·피로가 커진다. 프로토콜 문구가 바뀌면 원칙 7에 따라 버전을 올려야 한다.

## 참고문헌

- Barr, A. H. (1981). Superquadrics and angle-preserving transformations. *IEEE CG&A*. https://doi.org/10.1109/MCG.1981.1673799
- Blinn, J. F. (1982). A generalization of algebraic surface drawing. *ACM TOG*. https://doi.org/10.1145/357306.357310
- Collier, G. L. (1996). Affective synesthesia. *Motivation and Emotion*, 20, 1–32. https://link.springer.com/doi/10.1007/BF02251005
- Ćwiek, A., et al. (2022). The bouba/kiki effect is robust across cultures and writing systems. *Phil. Trans. R. Soc. B*, 377. https://pmc.ncbi.nlm.nih.gov/articles/PMC8591387
- Damiano, C., Walther, D. B., & Cunningham, W. A. (2021). *Scientific Reports*. https://www.nature.com/articles/s41598-021-99044-y
- Deitke, M., et al. (2023). Objaverse: A universe of annotated 3D objects. *CVPR*. https://arxiv.org/abs/2212.08051
- Google Research (2022). Google Scanned Objects: A high-quality dataset of 3D scanned household items. *ICRA*. https://arxiv.org/abs/2204.11918
- Gielis, J. (2003). A generic geometric transformation that unifies a wide range of natural and abstract shapes. *American Journal of Botany*, 90(3), 333–338.
- Grave, E., et al. (2018). Learning word vectors for 157 languages. *LREC*. https://fasttext.cc/docs/en/crawl-vectors
- Hacmun, I., Regev, D., & Salomon, R. (2018). The principles of art therapy in virtual reality. *Frontiers in Psychology*, 9, 2082. https://doi.org/10.3389/fpsyg.2018.02082
- Hamilton, W. L., Clark, K., Leskovec, J., & Jurafsky, D. (2016). Inducing domain-specific sentiment lexicons from unlabeled corpora. *EMNLP*. https://aclanthology.org/D16-1057
- 홍 외(2016). 정서가, 각성가 및 구체성 평정을 통한 한국어 정서단어 목록 개발. *인지과학*, 27(3). https://koreascience.kr/article/JAKO201630932329075.page
- (2018). Abstract animations for the communication and assessment of pain in adults: Cross-sectional feasibility study (Painimation). *JMIR*, 20(8), e10056. https://jmir.org/2018/8/e10056 (저자 목록 미확인)
- Jonauskaite, D., et al. (2020). Universal patterns in color-emotion associations are further shaped by linguistic and geographic proximity. *Psychological Science*. https://doi.org/10.1177/0956797620948810 ; 데이터 https://doi.org/10.23662/FORS-DS-888-2
- Jung, Y., Shin, H., & Bergen, B. (2026). EVOKE: Emotion Vocabulary Of Korean and English. https://arxiv.org/abs/2602.10414
- (2012). Negative triangles: Simple geometric shapes convey emotional valence. *Emotion*. https://pubmed.ncbi.nlm.nih.gov/21787078/ (저자 목록 미확인)
- Lee, J., Lim, J., Park, J., et al. (2022). Emotion Evaluator. *CogSci*. https://escholarship.org/uc/item/20s0r7c1
- Lee & Shin (2023). The cross-linguistic comparison of perceptual strength norms for Korean, English and L2 English. *Frontiers in Psychology*. https://pmc.ncbi.nlm.nih.gov/articles/PMC10395129/
- Lorensen, W. E., & Cline, H. E. (1987). Marching cubes. *SIGGRAPH*. https://doi.org/10.1145/37402.37422
- Lynott, D., et al. (2020). The Lancaster Sensorimotor Norms. *Behavior Research Methods*. https://pmc.ncbi.nlm.nih.gov/articles/PMC7280349
- Mohammad, S. M. (2025). NRC VAD Lexicon v2. https://arxiv.org/abs/2503.23547
- Pacheco, D., Le Groux, S., & Verschure, P. (2015). Two dimensional shapes for emotional interfaces. *ACHI*. https://portalrecerca.uab.cat/ca/publications/two-dimensional-shapes-for-emotional-interfaces-assessing-the-inf/
- 박인조·민경환(2005). 한국어 감정단어의 목록 작성과 차원 탐색. *한국심리학회지: 사회 및 성격*. (HF 미러) https://huggingface.co/datasets/jonghwanhyeon/korean-emotion-lexicon
- Pinilla, A., et al. (2021). Affective visualization in virtual reality: An integrative review. *Frontiers in Virtual Reality*. https://doi.org/10.3389/frvir.2021.630731
- Prusinkiewicz, P., & Lindenmayer, A. (1990). *The Algorithmic Beauty of Plants*. https://algorithmicbotany.org/papers/#abop
- Scott, G. G., et al. (2019). The Glasgow Norms. *Behavior Research Methods*, 51(3), 1258–1270. https://link.springer.com/article/10.3758/s13428-018-1099-3
- Strohmeier, P., et al. (2016). An evaluation of shape changes for conveying emotions. *CHI*. https://doi.org/10.1145/2858036.2858537
- Wagener, N., Niess, J., Rogers, Y., & Schöning, J. (2022). Mood Worlds. *CHI*. https://doi.org/10.1145/3491102.3501861
- 한국어 음상징: Kwon (2018). Iconicity correlated with vowel harmony in Korean ideophones. *Laboratory Phonology*, 9 ; Larsen & Heinz (2012). Neutral vowels in sound symbolic vowel harmony in Korean. *Phonology*, 29 ; Iconicity in Korean consonantal symbolism, https://core.ac.uk/works/25126900 (서지는 검색 요약 기준, 원문 미열람)

## 확인 필요 목록

1. Lancaster Sensorimotor Norms의 OSF 데이터 라이선스(논문은 CC BY 4.0, 저장소마다 표기가 다름).
2. Lee & Shin 2023 한국어 지각 강도 규범의 데이터 라이선스와 파일 내용.
3. 홍 외 2016 한국어 정서단어 목록의 내려받기 경로·라이선스. 박인조·민경환 목록 원자료의 권리(HF 미러의 CC0 표기만 확인).
4. KNU 한국어 감성사전 원 저장소의 라이선스와 규모.
5. EVOKE에 V/A 평정이 있는지.
6. Jonauskaite 외 2020의 30개국에 한국이 있는지. 31개국 후속 연구(osf.io/873df)의 출판 연도·학술지.
7. Ćwiek 외 2022의 25개 언어에 한국어가 있는지.
8. 온도·무게·질감 은유를 낱말 단위로 정리한 한국어 공개 자원.
9. 우리말샘 전체 데이터의 공식 내려받기 경로. 관계 유형별 구축 수. '물먹다'의 표제어 여부.
10. KorLex·CoreNet·KWN의 배포 위치와 라이선스.
11. Okt 라이선스. kiwipiepy에 낱말 유사도 기능이 있는지. 저장소가 실제 설치한 kiwipiepy 버전이 0.23.2 이하(LGPL)인지 이후(Apache 2.0)인지.
12. ConceptNet 5.7·Numberbatch 19.08의 한국어 규모와 품질.
13. fastText cc.ko.300 파일 크기, 어휘 수.
14. Vankrunkelsven 외의 임베딩 외삽 상관(r ≈ .89 등)은 2차 인용이라 원문 확인 필요.
15. Poly Haven 모델 수. Kenney 3D 묶음의 형식. Quaternius의 glTF 제공 여부. Objaverse-XL 규모·라이선스 구성.
16. Unity Splines 패키지 약관. Metamesh 런타임 사용 가능 여부. ProceduralToolkit 요구 Unity 버전. 마칭 큐브 구현체들의 CPU/GPU 여부와 Quest 3 성능. SuperFormula3D-Unity 저장소 원문·라이선스.
17. 절차적으로 만든 3D 형상에 대한 정서 평정 연구(이번 검색에서는 2D 연구만 찾음).
18. 우리말샘 관계 데이터를 사전 파일에 옮길 때 CC BY-SA가 사전 파일에 미치는 범위(법률 판단).
