# R2. LLM이 참여자 말로 그림 프롬프트를 쓰는 방식은 얼마나 흔한가

- 작성: 2026-11-28, 하위 에이전트(문헌 조사). 코드는 고치지 않았다.
- 맥락: G82/G83(`docs/decisions.md`)은 LLM이 형태 낱말 하나만 고르고 영어 문장은 규칙이 만든다. 연구 책임자는 LLM이 참여자 말 전체를 읽고 영어 프롬프트를 자유롭게 쓰는 방식으로 바꿀지 검토하고 있다.
- 검색어에 저장소·연구자·참여자 정보는 넣지 않았다. 모든 출처는 2026-11-28에 접속했다.
- "확인" 열의 뜻
  - **예**: 본문을 직접 열었다. PDF는 내려받아 텍스트를 뽑았다(DALL·E 3 논문, 시스템 카드, ArtTheraCat). HTML은 가져오기 도구로 열었다.
  - **초록만**: arXiv나 Semantic Scholar의 초록·서지만 봤다.
  - **검색 결과만**: 검색 요약만 봤다.
- HTML 본문에서 따온 인용은 가져오기 도구가 뽑아 준 것이다. 논문에 실을 때는 원문과 한 번 더 맞춰 봐야 한다.

> **교차 확인 뒤 정정 (2026-11-28, 메인 세션, `docs/codex-reviews/R2.md`)**
> 1. **MentalImager 해석이 틀렸다.** 관련성 평정이 높았던 것은 순수 키워드가 아니라 제목 주제어와 감정어를 함께 넣은 emo-keyword 조건이다. 순수 키워드 조건은 그보다 낮았다. "규칙 키워드가 전문 프롬프트보다 낫다"는 근거로 쓰지 않는다.
> 2. **Refugio가 LLM 재작성을 쓰지 않았다는 것은 확인되지 않았다.** 논문은 LLM을 물체 요청 검증에 쓴다. 그림 프롬프트를 LLM이 다시 쓰는지는 본문에서 가리지 못했다. "재작성 없는 대조 사례"로 쓰지 않는다.
> 3. **2.05배는 조건부 수치다.** AI가 편집한 이미지로 만든 AI 생성 영상 조건의 값이고, AI 편집 이미지 조건은 1.67배다. 이 연구의 위험 추정치로 쓰지 않는다.
> 4. **DALL·E 3 "끌 수 없음"은 API·Azure 배포 조건에 한한다.**
> 5. **빠진 문헌:** Jahani 외(2024, 온라인 실험 N=1,891)는 DALL·E 3의 자동 프롬프트 수정이 이미지 재현 과제에서 DALL·E 3의 성과 이점을 58% 줄였다고 보고한다(Codex가 제시, Microsoft Research 요약 기준. 메인은 원문을 직접 열지 않았다). 과제는 목표 이미지 재현이지 내적 경험의 표현이 아니다.
> 6. Metamorpheus의 DOI는 10.1145/3613904.3642410이다.
>
> 아래 본문에서 위와 어긋나는 서술(요약 7, "B. 방어 논리" 2·3·4)은 이 정정이 우선한다. **"규칙 경로가 참여자 심상에 더 충실하다"는 실증 근거는 없다. 원칙 2 유지는 설계 판단이다.**

## 요약

1. **생성 모델 쪽(흔하다, 확신 높음).** 상용 시스템은 LLM 재작성을 기본으로 켠다. DALL·E 3는 끌 수 없었고, Google Imagen은 `enhancePrompt=false`로 끌 수 있다. 부작용도 개발사가 스스로 적었다. OpenAI 시스템 카드는 재작성이 "뜻을 바꿀 수 있다", 편향을 실을 수 있다, 과잉 구체화(over-grounding)가 생긴다고 썼다.
2. **비영어 입력(갈린다, 확신 중간).** 실무 연구에서는 영어로 자동 번역해 넣는 일이 흔하다. 하지만 학술 문헌은 번역 후 입력(translate-test)이 다국어 인코더보다 못하다고 보고하고 번역 오류를 지적한다. 대안은 다국어 텍스트 인코더다(AltDiffusion은 한국어 포함 18개 언어).
3. **참여자 내면 경험을 그리는 HCI·심리 연구(LLM 쪽으로 기울지만 갈린다, 확신 중간).** 확인한 12편 가운데 LLM이 다시 쓰는 경우가 가장 많았다. ChatGPT·DALL·E 3·Bing을 거치면 재작성이 자동으로 들어간다. 규칙·키워드(MentalImager), 원문 그대로(전사 문장), 참여자나 연구자가 손으로 쓴 경우도 있다.
4. 생성물이 참여자 말을 반영하는지 **따로 잰 연구는 찾지 못했다.** 대부분 참여자 확인, 다시 만들기, 한계 서술로 처리했다.
5. **반대 근거(있다. 간접 근거는 강하고 직접 근거는 없다. 확신 중간).** 시스템 카드의 자기 보고, AI 편집 이미지가 거짓 기억을 늘린다는 실험(CHI 2025), 생성 이미지에 대한 고착(CHI 2024), 치료 맥락의 "왜곡된 거울" 지적이 있다.
6. LLM 재작성과 원문·규칙 프롬프트를 견주어 참여자 심상과 맞는 정도를 잰 실험은 찾지 못했다.
7. **소견: 절충.** 근거로 보면 LLM 매개는 흔하다. 다만 그런 연구는 거의 다 참여자 확인 단계와 여러 후보 안에서 고르기를 붙여서 썼다. 자유 재작성을 그대로 쓰면 원칙 2와 부딪히고, 개발사가 스스로 적은 부작용이 생긴다.

## 질문 1. 생성 모델 쪽 관행: LLM 프롬프트 재작성·확장

| 출처 | 무엇을 했나 | 이 결정에 주는 함의 | 확인 |
|---|---|---|---|
| Betker, Goh, Jing 외 (2023). *Improving Image Generation with Better Captions*. OpenAI 기술 보고서. https://cdn.openai.com/papers/dall-e-3.pdf | GPT-4로 짧은 캡션을 자세한 캡션으로 "upsample"해서 DALL·E 3에 넣었다. 이유: LLM이 "coming up with plausible details in an image description"에 능하다. 업샘플 캡션을 쓰면 벤치마크 격차가 "widens significantly". | 재작성의 목적이 **그럴듯한 세부를 덧붙이는 것**임을 개발사가 밝혔다. 원칙 2("말하지 않은 것을 추론하지 않는다")와 정면으로 맞선다. | 예(PDF 본문) |
| OpenAI (2023-10-03). *DALL·E 3 System Card*. https://cdn.openai.com/papers/DALL_E_3_System_Card.pdf | ChatGPT가 제출 문장을 다시 쓴다("Prompt Transformations"). 정책 준수(사람에게 속성 붙이기 등)에도 쓴다. 부작용을 스스로 적었다: "they may alter the meaning of the prompt, potentially carry inherent biases, and may not always align with individual user preferences". 과잉 구체화(over-grounding)가 사용자 문장의 세부를 바꿨다(그림 7). 사람이 아닌 캐릭터에 인종·성별 속성을 더한 예도 있다(그림 19). | 부작용의 1차 근거로 가장 강하다. "뜻이 바뀐다"는 말을 개발사가 직접 했다. | 예(PDF 본문) |
| OpenAI Cookbook. *What's new with DALL·E 3*(보관된 글, 날짜 표기 없음). https://developers.openai.com/cookbook/articles/what_is_new_with_dalle_3 | API에서 GPT-4가 "all of your prompts"를 최적화한다고 적었다. "this feature isn't able to be disabled at the moment". | 끌 수 없는 재작성의 예. 지시문으로 덜 바꾸게 하는 정도만 안내한다. | 예 |
| Microsoft Learn. *Azure OpenAI prompt transformation concepts*(2026-07 갱신). https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/prompt-transformation | LLM이 안전·품질 시스템 메시지를 붙여 프롬프트를 "enriches"한다. "You can't disable or customize prompt transformation for DALL·E 3". 비결정적이라 한 프롬프트에서 여러 변형이 나온다. 결과는 `revised_prompt`로 돌려준다. dall-e-3는 2026-03-04에 퇴역했다. | 재작성한 프롬프트를 **기록으로 돌려주는** 관행이 있다. 비결정성을 개발사도 인정한다. | 예 |
| Google Cloud. *Use prompt rewriter*(Imagen on Vertex AI). https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/use-prompt-rewriter | "LLM-based prompt rewriting tool". `enhancePrompt`의 "default value is `true`"이고 `false`로 끌 수 있다. 끄면 품질과 프롬프트와 닮은 정도에 영향이 있을 수 있다고 적었다. 원 프롬프트가 30단어 미만일 때만 재작성 문장을 돌려준다. | **끄는 스위치가 있는** 사례다. 기본은 켜짐이다. 비교 조건(켬/끔)의 선례로 쓸 수 있다. | 예 |
| Datta, Ku, Ramachandran, Anderson (2024). *Prompt Expansion for Adaptive Text-to-Image Generation*. ACL 2024(long). https://aclanthology.org/2024.acl-long.189 | 질의 하나를 여러 확장 프롬프트로 바꿔 다양성·미감·정렬을 높였다. | 연구 쪽 목표는 "다양성"이다. 참여자 한 사람의 심상을 재현하는 목표와 다르다. | 초록만 |
| Raghavan, P. (2024-02-23). *Gemini image generation got it wrong. We'll do better.* Google 블로그. https://blog.google/products/gemini/gemini-image-generation-issue/ | "다양한 사람을 보여 주도록 한 조정"이 맞지 않는 경우까지 적용돼 "overcompensate"했다. | 사용자가 말하지 않은 속성을 시스템이 넣었을 때 생긴 실패 사례. 블로그는 그 조정이 프롬프트 재작성인지는 밝히지 않았다. | 예 |
| Liu, Ji, Lu 외 (2026). *Seeing is Believing: Aligning Prompt Rewriting with Visual Anchors for T2I Generation*. arXiv 2606.08492(심사 전). | "the rewriter may over-infer missing details, causing an intent-generation gap" | 최근 연구도 재작성기의 과잉 추론을 풀어야 할 문제로 본다. | 초록만 |

**정리.** 상용 시스템에서 재작성은 기본값이다. 끌 수 있는지는 시스템마다 다르다(DALL·E 3는 못 끔, Imagen·Veo는 끌 수 있음). 개발사 스스로 뜻 변경, 편향, 비결정성을 적었다.

## 질문 2. 한국어 등 비영어 입력

| 출처 | 무엇을 했나 | 함의 | 확인 |
|---|---|---|---|
| Podell, English, Lacey, Blattmann 외 (2023). *SDXL*. arXiv 2307.01952 | 텍스트 인코더로 "OpenCLIP ViT-bigG … in combination with CLIP ViT-L"을 쓴다(2.1절). | 이 연구의 SDXL은 영어 CLIP 계열이다. 한국어를 그대로 넣는 길은 사실상 막혀 있다. | 예 |
| Li, Chang, Rawls, Vulić, Korhonen (2023). *Translation-Enhanced Multilingual Text-to-Image Generation*. ACL 2023, doi:10.18653/v1/2023.acl-long.510 | Translate Train / Translate Test / Zero-Shot을 비교하고 EnsAd를 제안했다. 검색 요약에 따르면 Translate Test가 Zero-Shot보다 낮고, 기계 번역문과 사람 영어 캡션 사이의 간격(번역투)을 원인으로 들었다. | 번역 후 입력은 표준 기준선이다. 하지만 학계에서 최선의 방법으로 보지 않는다. | 초록만(순위 결과는 검색 결과만) |
| Saxon, Wang (2023). *Multilingual Conceptual Coverage in Text-to-Image Models*. ACL 2023. arXiv 2306.01735 | CoCo-CroLa: 언어마다 같은 명사의 생성 결과가 얼마나 같은지 잰다. | 언어마다 개념 덮개가 다르다. 한국어 낱말을 영어로 옮길 때 생기는 뜻 차이는 측정 대상이다. | 초록만 |
| Saxon, Luo, Levy, Baral, Yang, Wang (2024). *Lost in Translation? …*. NAACL 2024(short), doi:10.18653/v1/2024.naacl-short.48 | 벤치마크의 개념 번역(스페인어·일본어·중국어)에서 오류를 찾아 고쳤다. | 사람이 만든 번역에도 오류가 있다. 번역 단계는 검증이 필요하다. | 검색 결과만 |
| Ye, Liu, Wu, Wu (2024). *AltDiffusion: A Multilingual Text-to-Image Diffusion Model*. AAAI 2024, 38(7):6648–6656. arXiv 2308.09991 | 증류한 다국어 텍스트 인코더를 영어 전용 확산 모델에 붙였다. 한국어를 포함한 18개 언어를 지원한다. | 번역 없는 대안의 예다. SDXL에 그대로 붙지는 않으므로 모델 교체 비용이 든다. | 초록만(AAAI 서지는 검색 결과) |
| Friedrich, Hämmerl, Schramowski 외 (2025). *Multilingual Text-to-Image Generation Magnifies Gender Stereotypes*. ACL 2025, 2025.acl-long.966 | 다국어 인코더(AltCLIP·mT5 등) 모델의 성별 편향을 쟀다. 우회 프롬프트로 편향을 줄이면 "the alignment with the specific prompt is compromised". | 다국어 인코더도 편향에서 자유롭지 않다. 프롬프트를 손대면 정렬이 깨지는 맞교환이 있다. | 예(본문 일부) |
| Pinzuti, Tüscher, Castro (2025). arXiv 2507.10861(심사 전) | 참여자 발화 전사를 그대로 프롬프트로 쓰고, 비영어 발화는 자동으로 영어 번역했다. | 실무 연구에서 "자동 번역 후 투입"이 흔하다는 사례. | 예 |
| Wan 외 (2024). Metamorpheus. CHI 2024 | 참여자 P10이 복잡한 장면이 안 나온 원인을 장면의 복잡도나 자신의 영어 프롬프트 실력으로 돌렸다. | 비영어 화자가 영어 프롬프트를 직접 쓰는 부담이 보고됐다. | 예 |

**정리.** 비영어 입력을 영어로 옮겨 넣는 일은 실무에서 흔하다. 그러나 이것을 "표준"으로 못 박은 권위 있는 문헌은 찾지 못했다. 학술 쪽은 번역 오류·번역투를 문제로 보고, 다국어 인코더를 대안으로 연구한다. 이 연구에서 LLM이 쓰든 규칙이 쓰든 **한→영 변환 단계가 있다는 점은 같다.** 차이는 변환 범위다(낱말 하나 대 문장 전체).

## 질문 3. 참여자의 말(꿈·기억·심상·감정)을 생성 AI로 그린 연구

프롬프트 만드는 방식은 다섯 갈래로 나눴다: 원문 그대로 / 규칙·키워드 / LLM 재작성 / 참여자가 씀 / 연구자가 씀.

| 출처 | 프롬프트 만드는 방식 | 타당도를 어떻게 다뤘나 | 함의 | 확인 |
|---|---|---|---|---|
| Zhang, Zhang, Zhou, Louie, Kim, Guo, Li, Peng (2025). *MentalImager*. PACMHCI(CSCW1) 2025. arXiv 2409.14859 | **규칙·키워드.** RAKE로 키워드를 뽑고, BERT 감정 분류기로 감정어 1개를 정한다. 가중치를 붙여 SD에 넣는다. 프롬프트 생성에 LLM은 쓰지 않았다. 전문을 그대로 넣는 방식도 선택지로 있다. | 사용자가 키워드·가중치를 고치고 다시 만든다(한 번에 4장). 평정자 관련성 평균: 감정+키워드 3.09/3.52, 전문 2.69/3.04(주제/감정). | **규칙 키워드 프롬프트가 전문보다 관련성 평정이 높았다.** 유지 쪽 근거다. 다만 전문과 키워드 사이의 직접 검정은 보고되지 않았다. | 예 |
| Jin, Cai, Chen, Zhang, Doherty, Jiang (2024). *Exploring the Design of Generative AI in Supporting Music-based Reminiscence for Older Adults*. CHI 2024, doi:10.1145/3613904.3642800 | **연구자 고정 프롬프트 + 참여자 기억 → Bing Chat(GPT-4)이 이야기·그림을 만든다**(진행자가 대신 입력). | 참여자가 어긋남을 보고했다. AI가 "cannot accurately visualize what I thought unless I tell it all the details"(P1). 현지와 다른 배경·인물이 나왔다. | LLM이 매개한 그림은 어긋날 수 있다. 참여자는 맞는지를 중요하게 여긴다. | 예 |
| Wan, Feng, Bei, Gao, Lu (2024). *Metamorpheus*. CHI 2024. arXiv 2403.00632 | **참여자가 씀 + LLM 제안.** 참여자가 정서 요소·형용사·은유와 그림 프롬프트를 쓴다. ChatGPT는 은유를 제안하고 묘사문을 쓴다. 제안은 받거나 거절한다. | 프롬프트를 고치고 다시 만들 수 있다. 모델이 "was too random for correctly recreating an abstract visual scene during a dream". P9는 시스템이 적은 "무의식 감정"을 느끼지 않는다고 했다. | LLM이 해석을 덧붙이면 참여자가 거부할 수 있다. 참여자 통제권이 핵심 안전장치다. | 예 |
| Liu, Kitson, Picard-Deland, Carr 외 (2024). *Virtual Dream Reliving*. CHI EA 2024, doi:10.1145/3613905.3644054 | 속삭인 꿈 발화를 VR 속 3D 꿈 물체로 바꿨다(후속 논문의 설명). 전사를 그대로 넣었는지는 확인 못 함. | 1저자 자기민족지 2주. | **이 연구와 가장 비슷한 구성**(말 → 3D → VR). | 초록만 |
| Liu, Lee, Steinmaurer, Picard-Deland, Carr, Kitson (2024). *DreamLLM-3D*. NeurIPS 2024 Creative AI track. arXiv 2503.16439 | **LLM 추출.** 로컬 Mistral 7B(온도 0)가 꿈 보고를 "single dream entities" 프롬프트로 쪼개 Point-E에 넣는다. 감정·상호작용은 색·소리에 쓴다. | LLM 출력의 정확도나 충실도는 평가하지 않았다. 한계로 편향과 "overly reliant on AI-generated guidance or interpretation"을 들었다. | 로컬 LLM·온도 0 선례. 충실도 검증이 비어 있는 선례이기도 하다. | 예 |
| Wu, Lin, Chuang 외 (2025). *Dream Relay*. CHI EA 2025, doi:10.1145/3706599.3720238 | DALL·E 3로 꿈 그림을 만들었다(따라서 자동 재작성을 거친다). 프롬프트를 누가 썼는지는 확인 못 함. | 집단 자기민족지. 검색 요약에 따르면 "some inaccuracies"가 있어도 새로운 시각을 줬다. | 부정확함을 장점(상상 자극)으로 다룬 예. 우리처럼 반영 타당도가 목표인 연구와 목적이 다르다. | 초록만 |
| Zhai, Zhang, Jeung (2024). *Exploring Older Adults' Reminiscing with ChatGPT and Text-to-Image Technology*. ASSETS 2024, doi:10.1145/3663548.3688521 | **LLM 매개.** ChatGPT가 질문으로 이야기를 끌어내고, 그 이야기로 그림을 만든다. | 7명. 세부는 확인 못 함. | LLM 매개가 흔하다는 사례. | 초록만 |
| Wang, Tian, Zeng, Tu, Zhang, Yi, Li, Rau (2024). *The Synergy of Dialogue and Art: … ArtTheraCat*. CSCW Companion 2024, doi:10.1145/3678884.3681843 | **LLM 재작성.** GPT-4에 "interpreting users' emotional descriptions and converting them into suitable prompts for DALL-E 3"를 지시했다. 정서를 "tangible objects"로 떠올리게 한다. | 필요하면 함께 다듬는다(반복). P15: "my descriptions were sparse, leading to images that didn't quite match my feelings. However, viewing these mismatched images spurred more emotional associations…" | 정서를 사물로 떠올리게 한다는 점이 이 연구와 가깝다. 어긋난 그림이 참여자의 자기 이해를 바꾸었다는 보고는 질문 4의 암시 효과와 이어진다. | 예(PDF) |
| Haber, Hadar Shoval, Levkovich 외 (2025). *The externalization of internal experiences in psychotherapy through generative AI*. Frontiers in Digital Health 7:1512273 | **LLM 매개.** 맞춤 GPT(VIVI)가 내담 묘사를 요약하고 확인받은 뒤 DALL·E 3로 생성한다. | 요약을 확인받고, 반복해서 다듬는다(첫 그림은 "too young"이라 거부됨). 저자들이 GenAI를 "distorted mirrors"라고 했다. 환자가 AI 해석을 치료자보다 믿을 위험도 적었다. | 생성 전 확인 단계의 선례. 해석 권위가 옮겨 갈 위험을 적은 문헌. | 예 |
| Mora, Ivorra, Parra-Vargas, Soldevila-Matías, Alcañiz (2026). *Refugio*. Frontiers in Virtual Reality 7, doi:10.3389/frvir.2026.1760765 | **원문 그대로 + LLM 관문.** 음성을 전사하고 사용자가 확인한다. 로컬 Gemma 3는 내용 규칙 검사만 한다(본문에 재작성 서술은 없음). 그 뒤 Sana가 3장, Zero123++와 InstantMesh가 3D를 만든다. | 3장 가운데 고르고, 비슷한 것을 다시 만들거나 취소한다. 한계: "occasional mismatches between users' mental images and generated objects". 개발 중 LLM이 빨간 물체를 계속 거절한 편향이 있었다. | **말 → 3D → VR이 가장 가까운 동료 심사 사례.** LLM에 재작성을 맡기지 않고 원문과 후보 고르기를 썼다. | 예(본문 앞 2/3) |
| He, Qian (2025). *Human-Centred Evaluation of T2I Models for Self-expression of Mental Distress*. arXiv 2512.04087(심사 전) | **LLM 재작성.** GPT-4o가 네 가지 페르소나 틀로 묘사를 "elaborate"한다. '창의 예술가' 틀은 "unexpected or surreal" 요소를 일부러 넣는다. 주인공을 기본 여성으로 그리게 했다(남성 참여자 1명만 바꿈). | 참여자는 프롬프트를 보거나 고치지 않았다. 도움 평균 2.4. 한계로 "GPT-4o's inherent interpretive biases"를 들었다. | 재작성이 **말하지 않은 속성(성별, 초현실 요소)을 넣은** 구체적 사례. | 예 |
| Pinzuti, Tüscher, Castro (2025). arXiv 2507.10861(심사 전) | **원문 그대로.** 전사를 "without manual correction, preserving participants' spontaneous speech"로 넣었다(비영어는 자동 번역). | N=20. 재평가+그림이 부정 정서를 더 줄였다. 프롬프트–캡션 의미 일치가 평정과 상관(ρ=0.56). | 원문 투입도 쓰인다. 일치도를 효과 해석에 쓴 예. | 예 |
| Mihailidis, Garcia (2025-04-24). *Exploring AI's creative potential in dementia care*. Google 블로그(심사 없음) | **연구자와 참여자가 함께 씀.** 면담 묘사를 ImageFX/VideoFX에 넣고 "dream-like quality"를 더했다. | 참여자가 만족할 때까지 고르고 다듬었다. 그림은 "not intended to be perfect recreations of the past". | 일부러 정밀하지 않은 양식을 고른 선례. 다른 프로젝트 페이지의 '거짓 정밀' 설명은 검색 결과만 봤다. | 예(심사 없음) |

**정리.** 2023년 이후로 LLM(ChatGPT·GPT-4·Bing·DALL·E 3)을 거치는 연구가 가장 많다. DALL·E 3를 쓰면 연구자가 의도하지 않아도 재작성이 들어간다. 그런데 본문에서 `revised_prompt`를 기록·보고했는지 밝힌 연구는 확인하지 못했다. 규칙 키워드(MentalImager), 원문(Refugio, Pinzuti), 참여자 작성(Metamorpheus)도 있다. 프롬프트 방식은 갈리지만, 타당도를 다루는 방식은 거의 같다. **참여자 확인, 여러 후보, 다시 만들기, 한계 서술**이다. 생성물이 참여자 말을 얼마나 반영했는지 독립 척도로 잰 연구는 찾지 못했다(가까운 것: MentalImager의 평정자 관련성, Pinzuti의 프롬프트–캡션 일치).

## 질문 4. 반대 근거: LLM 매개와 생성물의 암시 효과

| 출처 | 내용 | 함의 | 확인 |
|---|---|---|---|
| OpenAI (2023). DALL·E 3 System Card | 재작성이 "may alter the meaning of the prompt". 과잉 구체화. 사람이 아닌 대상에 인종 속성을 더함. 한 낱말("Japanese")을 더했더니 배경까지 바뀜. | 개발사의 자기 보고. 가장 인용하기 좋다. | 예 |
| Pataranutaporn, Archiwaranguprok, Chan, Loftus, Maes (2025). *Synthetic Human Memories: AI-Edited Images and Videos Can Implant False Memories and Distort Recollection*. CHI 2025, doi:10.1145/3706598.3713697 | N=200. AI가 편집한 이미지로 만든 AI 영상에서 거짓 기억이 가장 많았다("2.05x compared to control"). 확신도도 높았다. | 참여자가 본 생성물이 자기 기억이나 심상을 바꿀 수 있다. 말하지 않은 세부가 들어간 그림은 그 위험을 키운다. | 예(서지·초록) |
| Chan, Pataranutaporn, Suri, Zulfikar, Maes, Loftus (2024). *Conversational AI Powered by LLMs Amplifies False Memories in Witness Interviews*. arXiv 2408.04681(심사 여부 확인 못 함) | 생성형 챗봇 면담이 즉시 거짓 기억을 대조군의 3배 넘게 만들었다. | LLM 매개 면담의 암시 효과. 이 연구의 면담자 원칙 3과 같은 방향이다. | 검색 결과만 |
| Wadinambiarachchi, Kelly, Pareek, Zhou, Velloso (2024). *The Effects of Generative AI on Design Fixation and Divergent Thinking*. CHI 2024. arXiv 2403.11164 | N=60. AI 이미지 생성기를 쓴 쪽이 고착이 높았고, 고착이 AI 출력으로 옮겨 갔다("fixation displacement"). | 처음 보인 생성물에 참여자가 붙들릴 수 있다. 첫 후보의 영향이 크다. | 검색 결과만 |
| Jakesch, Bhat, Buschek, Zalmanson, Naaman (2023). *Co-Writing with Opinionated Language Models Affects Users' Views*. CHI 2023, doi:10.1145/3544548.3581196 | N=1,506. 의견이 치우친 LLM과 함께 쓰면 글과 이후 태도가 바뀐다("latent persuasion"). | LLM 매개가 사용자 표현을 옮긴다는 일반 근거. 맥락은 의견 글이다. | 검색 결과만 |
| Haber 외 (2025). Frontiers in Digital Health | "distorted mirrors". 해석 권위가 AI로 옮겨 갈 위험. 공감 실패. 문화·성별 편향. | 치료 인접 맥락의 이론·사례 분석. | 예 |
| Liu 외 (2024). DreamLLM-3D | AI 해석에 지나치게 기댈 위험을 한계로 적었다. | 같은 갈래(꿈 → LLM → 3D) 연구의 자기 경고. | 예 |
| Wang 외 (2024). ArtTheraCat(P15) | 어긋난 그림이 "true feelings"를 정리하게 했다. | 저자는 이로움으로 읽었다. 타당도 쪽에서 보면 생성물이 참여자 보고를 바꾼 예다. | 예 |
| He, Qian (2025) | 틀 기본값이 주인공 성별을 정했다. 초현실 요소를 일부러 넣었다. | 말하지 않은 속성이 들어간 구체적 사례. | 예 |

**정리.** "LLM 재작성 프롬프트가 참여자 심상 보고의 해석 타당도를 떨어뜨린다"를 직접 실험한 연구는 찾지 못했다. 간접 근거는 여럿이고 일관된다. 개발사가 뜻 변경을 인정했고, 생성 시각물이 기억을 바꾸고 고착을 만든다는 실험이 있고, 치료 맥락에서도 같은 경고가 나왔다.

## 이 연구에 적용하면

### A. LLM 자유 프롬프트로 갈 때 선행 연구가 쓰는 안전장치

1. **생성 전 확인.** VIVI는 요약을 확인받고, Refugio는 전사를 확인받는다. 참여자에게 보이는 것은 영어 프롬프트가 아니라, 프롬프트가 기대는 **한국어 원문 구간**이어야 원칙 3과 맞는다.
2. **여러 후보와 고르기·다시 만들기·취소.** Refugio는 3장, MentalImager는 4장이다. 이 저장소의 G75 그림 고르기와 [이 중에는 없어요]가 같은 구실을 한다.
3. **편집 가능한 중간 표현.** MentalImager는 키워드와 가중치를, Metamorpheus는 프롬프트를 고칠 수 있다. 자유 문장보다 낱말 목록이 확인하기 쉽다.
4. **결정성과 기록.** DreamLLM-3D는 로컬 LLM을 온도 0으로 돌렸다. Azure·Vertex는 `revised_prompt`/`prompt`를 돌려준다. 재작성한 프롬프트 전문, 모델 digest, seed를 세션마다 남긴다(원칙 1 G77 예외와 같은 수준).
5. **덧붙이기 금지 지시와 검사.** 시스템 카드는 과잉 구체화를 실패 사례로 들었다. 색·질감·크기·사람 속성·배경을 넣지 말라고 지시하고, 출력의 각 명사·형용사가 원문 구간에 대응하는지 검사할 수 있다. 이것은 선행 연구에서 확인한 장치가 아니라 이 연구의 원칙에서 나온 제안이다.
6. **끄는 스위치와 비교 조건.** Imagen은 `enhancePrompt=false`로 끈다. 경로를 기록해 층으로 나눠 보는 G83 방식과 맞는다.
7. **일부러 덜 정밀한 양식.** Synthetic Memories 프로젝트는 "dream-like quality"를 골랐다(심사 없는 출처). 이 연구는 형태 메시 하나만 쓰고 색·질감은 조절 화면 값으로 정하므로 이미 일부가 덮여 있다.
8. **사후 면담에서 어긋남과 영향을 묻는다.** "그림을 보고 처음 떠올린 모습이 달라졌는가"를 묻는다. 거짓 기억·고착 문헌에 대응하는 장치다.

### B. 지금 방식(형태 낱말 + 규칙 프롬프트)을 유지할 때 방어 논리

1. 개발사 스스로 재작성의 목적을 "plausible details" 덧붙이기로 밝혔다(Betker 외 2023). 뜻이 바뀌고 편향이 실릴 수 있다고도 적었다(System Card). "말하지 않은 것을 추론하지 않는다"는 연구 목적과 맞지 않는다.
2. 참여자 글에서 규칙으로 뽑은 키워드 프롬프트가 전문 프롬프트보다 주제·감정 관련성 평정이 높았다(MentalImager, CSCW 2025). 낱말 중심 프롬프트가 열등하다는 근거는 없다.
3. 가장 가까운 동료 심사 사례(Refugio, 말 → 3D → VR)도 LLM에게 재작성을 맡기지 않았다. 원문, 확인, 후보 고르기를 썼다.
4. 생성 시각물은 기억과 심상 보고를 바꿀 수 있다(CHI 2025 거짓 기억, CHI 2024 고착). 말하지 않은 세부가 적을수록 이 위험이 줄어든다.
5. 재작성은 비결정적이다(Azure 문서). "같은 텍스트는 같은 결과"를 캐시와 기록으로만 보장할 수 있다.
6. 약점도 적어야 한다. 낱말을 못 뽑으면 생성이 안 된다(G82 3차 평가에서 뜻 맞는 채움 50% 안팎). 선행 연구 다수는 LLM 매개를 받아들였다. "드문 방식"이라는 반론에는 "목적(반영 타당도)이 다르다"로 답해야 한다.

### C. 절충안의 모습(근거가 가리키는 곳)

- LLM이 참여자 확정 텍스트 전체를 읽는다. 하지만 출력은 "원문 인용 구간 + 그 구간의 영어 명사구"로 제한한다. 문장 조립은 지금처럼 규칙이 한다. G82를 형태 낱말 하나에서 "형태 명사구"로 넓히는 셈이다.
- 자유 문장 재작성은 끈 상태를 기본으로 두고, 켠 경로는 따로 기록해 비교한다.
- 어느 쪽이든 생성 전 원문 구간을 보여 주고, 여러 후보와 [이 중에는 없어요], 사후 면담의 어긋남 질문을 유지한다.

## Codex 교차 확인 대상 핵심 서지

1. Betker, J., Goh, G., Jing, L., et al. (2023). *Improving Image Generation with Better Captions.* OpenAI. https://cdn.openai.com/papers/dall-e-3.pdf — 3.5절 "upsample", "plausible details" 문구.
2. OpenAI (2023-10-03). *DALL·E 3 System Card.* https://cdn.openai.com/papers/DALL_E_3_System_Card.pdf — "may alter the meaning of the prompt", over-grounding(그림 7).
3. Google Cloud. *Use prompt rewriter* (Imagen on Vertex AI). https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/use-prompt-rewriter — `enhancePrompt` 기본 true, 끌 수 있음.
4. Zhang, H., Zhang, J., Zhou, Y., Louie, R., Kim, T., Guo, Q., Li, S., Peng, Z. (2025). *MentalImager: Exploring Generative Images for Assisting Support-Seekers' Self-Disclosure in Online Mental Health Communities.* PACMHCI (CSCW1). arXiv 2409.14859 — 규칙 키워드 대 전문의 평정 수치. DOI는 확인 못 함.
5. Mora, P., Ivorra, E., Parra-Vargas, E., Soldevila-Matías, P., Alcañiz, M. L. (2026). *Refugio: a voice-driven generative VR "safe place"…* Frontiers in Virtual Reality 7. doi:10.3389/frvir.2026.1760765 — LLM이 재작성하지 않는다는 점은 본문 앞 2/3에서만 확인.
6. Wan, Q., Feng, X., Bei, Y., Gao, Z., Lu, Z. (2024). *Metamorpheus: Interactive, Affective, and Creative Dream Narration Through Metaphorical Visual Storytelling.* CHI 2024. arXiv 2403.00632. DOI는 확인 못 함.
7. Pataranutaporn, P., Archiwaranguprok, C., Chan, S., Loftus, E., Maes, P. (2025). *Synthetic Human Memories: AI-Edited Images and Videos Can Implant False Memories and Distort Recollection.* CHI 2025. doi:10.1145/3706598.3713697 — 2.05배 수치.
8. Haber, Y., Hadar Shoval, D., Levkovich, I., et al. (2025). *The externalization of internal experiences in psychotherapy through generative artificial intelligence.* Frontiers in Digital Health 7:1512273. doi:10.3389/fdgth.2025.1512273

## 찾지 못했거나 확인하지 못한 것

- LLM 재작성 프롬프트와 원문·규칙 프롬프트를 견주어 **참여자가 떠올린 심상과의 일치**를 잰 실험. 찾지 못했다.
- 한국어 화자가 내면 심상을 말하고 생성 AI로 시각화한 연구. 찾지 못했다. IFS(부분)를 생성 AI로 시각화한 심사 거친 연구도 찾지 못했다.
- JMIR에 실린, 참여자 묘사로 그림을 만든 연구. 찾지 못했다(JMIR Formative 2024 e63038은 예술치료사 대상이라 뺐다).
- DALL·E 3·ChatGPT·Bing을 쓴 HCI 연구들(Jin, Zhai, Dream Relay, ArtTheraCat, Haber)이 자동 재작성(`revised_prompt`)을 기록·보고했는지. 확인 못 함.
- 본문을 열지 못한 것(초록만 또는 검색 결과만): Dream Relay·Zhai·Virtual Dream Reliving의 프롬프트 절차, Li 외 2023의 수치 표, Saxon 외 2024 본문, Jakesch 2023·Wadinambiarachchi 2024 본문, Chan 외 2024의 심사 게재 여부.
- 그 밖에 확인하지 못한 것:
  - HARMONEE(Geriatric Nursing 2025): 403으로 열리지 않았고 프롬프트 작성 방식을 확인 못 함.
  - Refugio: 본문 뒤 1/3과 참여자 언어.
  - Synthetic Memories: '흐릿한 양식으로 거짓 정밀을 피한다'는 설명은 검색 결과만 봤다.
- Imagen 3 기술 보고서(arXiv 2408.07009)에 재작성 서술이 있는지 확인 못 함.
- 문헌만으로는 정할 수 없는 것: 참여자 안내문이 로컬 LLM의 이 쓰임을 덮는지(D15 반박 3, 보류).
