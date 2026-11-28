# 이미지 모델 교체 조사 — SDXL base 1.0을 바꿀 근거가 있는가 (2026-11-28)

범위: 웹 조사만 했다(모델 카드, 공식 저장소, 논문, 공개 벤치마크 원문). 내려받기·GPU 실행·코드 수정은 하지 않았다. 하위 에이전트가 조사했고 메인이 그 보고를 그대로 옮겨 적었다. 서지 교차 확인은 `docs/codex-reviews/R1.md`.
표시: [원문] = 직접 읽은 1차 자료, [요약] = 2차 자료나 검색 요약. 확인하지 못한 것은 맨 뒤 "확인 못 함"에 모았다.

앞선 조사와 겹치는 내용은 되풀이하지 않는다. 겹치는 것은 FLUX.2 klein 4B·Z-Image-Turbo·FLUX.1-schnell·Qwen-Image·Sana Sprint의 라이선스와 VRAM, 한국어 입력 표, `docs/gen3d-feasibility.md`의 후보 표다. 이 문서는 그 뒤로 바뀐 것, 빠졌던 후보, 그리고 "이미지 후보 3장 중 고르기"(G75)로 설계가 바뀌면서 새로 따져야 할 점만 다룬다.

## 0. 요약
- 공개 벤치마크에서 SDXL보다 낫다는 근거는 많다. 다만 **우리가 쓰는 '물체 하나' 프롬프트에서는 그 차이가 거의 드러나지 않는다.** GenEval 단일 물체 항목에서 SDXL은 이미 0.98이고 새 모델은 1.00이다. 격차는 두 물체·개수·위치·속성 결합에서 벌어지는데, 우리 프롬프트는 이런 항목을 쓰지 않는다.
- 우리 요구에 가까운 공개 지표는 두 가지다. PRISM-Bench의 Style·Entity **정합(Ali.)** 점수에서 Z-Image-Turbo와 SDXL의 차이는 약 5점이다. 큰 차이는 미적 점수(Aes.)에서 난다. DPG-Bench는 긴 묘사형 프롬프트로 잰 점수다. "흰 배경에 물체 하나만, 덧붙이지 않음", "무채색 점토 화풍", "추상·드문 사물"을 직접 잰 공개 벤치마크는 찾지 못했다.
- 설계가 바뀌면서 새로 중요해진 성질이 둘 있다.
  1. **seed 사이 다양성.** 후보 3장이 서로 달라야 고를 의미가 있다. Z-Image 공식 카드는 Turbo의 다양성을 "Low"로 적었다 [원문]. BFL도 klein Base가 증류판보다 다양하다고 적었다 [원문].
  2. **negative prompt.** 지금 파이프라인은 `negativeAccessories`(받침대·끈 등 덧붙임 억제)에 기댄다. Turbo는 negative를 지원하지 않는다 [원문]. klein 증류판은 guidance를 무시한다 [원문].
- 그래서 "빠른 증류 모델로 바꾸면 된다"는 결론은 근거가 약하다. 1순위 실측 후보는 **Z-Image(증류하지 않은 base)**, 2순위는 **FLUX.2 [klein] 4B(증류판과 Base 둘 다)**다. SDXL은 기준선으로 남긴다. 실측에서 통과 기준을 못 넘으면 SDXL을 그대로 쓴다.

## 1. SDXL보다 낫다는 공개 근거가 있는 로컬 후보

### 1.1 같은 표 안에서 SDXL과 비교한 수치
| 출처(표) | SDXL | 비교 대상 | 비고 |
|---|---|---|---|
| Z-Image 보고서 Table 10, DPG-Bench Overall [원문] | 74.65 | Z-Image 88.14 · Z-Image-Turbo 84.86 · Qwen-Image 88.32 · FLUX.1-dev 83.84 · SD3 Medium 84.08 · Lumina-Image 2.0 87.20 · HiDream-I1-Full 85.89 | 긴 묘사형 프롬프트 |
| Z-Image 보고서 Table 13, PRISM-Bench 영어 Overall [원문] | 57.0 | Z-Image-Turbo 77.4 · Z-Image 75.6 · Qwen-Image 74.1 · SD3.5-Large 70.6 · FLUX.1-dev 68.5 | |
| 같은 표, Style (Ali./Aes./Avg.) [원문] | 71.7/72.6/72.1 | Z-Image-Turbo 76.7/88.2/82.4 · Z-Image 78.0/89.0/83.5 | 정합 차이 약 5–6점, 미적 점수 차이 약 16점 |
| 같은 표, Entity (Ali./Aes./Avg.) [원문] | 71.1/65.0/68.0 | Z-Image-Turbo 75.7/82.3/79.0 · Z-Image 75.0/74.4/74.7 | 같은 경향 |
| Qwen-Image 보고서 Table 3, DPG [원문] | 74.65 | Qwen-Image 88.32 | SDXL은 Table 4(GenEval)에 없음 |
| LongCat-Image 보고서 Table 3, DPG [원문] | 74.65 | LongCat-Image 86.80 · FLUX.1-dev 83.84 | |
| HiDream-O1-Image 카드, DPG [원문] | 74.65 | HiDream-O1-Image 89.83 | 회사가 직접 낸 표 |
| SD3 논문 Table 5, GenEval [원문] | Overall 0.55, 단일 0.98, 두 물체 0.74, 개수 0.39, 색 0.85, 위치 0.15, 색 결합 0.23 | SDXL Turbo 0.55(단일 1.00) · SD3 최대 0.74 | 2024년 표 |

SDXL이 없는 GenEval 표도 둘 있다. 서로 다른 논문의 수치는 옮겨 비교하지 않는다.
- Z-Image Table 9 [원문]: Z-Image 단일 1.00/Overall 0.84, Turbo 1.00/0.82, Qwen-Image 0.99/0.87, HiDream-I1-Full 1.00/0.83, SD3.5-Large 0.98/0.71, FLUX.1-dev 0.98/0.66.
- ERNIE-Image 카드 [원문]: ERNIE-Image(PE 없음) 1.0000/0.8856, FLUX.2-klein-9B 0.9313/0.8481, Z-Image-Turbo 1.0000/0.8233. klein 4B는 이 표에 없다.

**읽는 법.** 단일 물체 항목은 천장에 닿아 있다. 우리 프롬프트에 옮겨 쓸 수 있는 근거는 PRISM의 Style·Entity 정합 점수 정도이고, 거기서 차이는 약 5점이다. "덧붙이지 않음"이나 "프레임 안에 온전히"를 따로 잰 공개 수치는 없다.

### 1.2 후보별 사실
| 후보 | 가중치 라이선스 | 텍스트 인코더 | gated | 16 GB | diffusers | 단계/guidance | negative | seed 다양성 | SDXL과 같은 표 |
|---|---|---|---|---|---|---|---|---|---|
| **SDXL base 1.0**(현재) | CreativeML Open RAIL++-M | CLIP 2개 | 아니오 | 됨 | `StableDiffusionXLPipeline` | 30/7.0 | 됨 | 높음 | 기준선 |
| **Z-Image(base)** | Apache-2.0 [원문] | Qwen3-4B(보고서 4.1절) [원문] | 아니오 [원문] | VRAM 미기재. 같은 6B 구조인 Turbo가 "fits comfortably within 16G VRAM" [원문] | `ZImagePipeline` [원문] | 권장 28–50/3.0–5.0 [원문] | 지원 [원문] | "High" [원문] | DPG 88.14, PRISM 75.6 [원문] |
| Z-Image-Turbo | Apache-2.0 [원문] | 같음 | 아니오 | 16 GB 안 [원문] | 같음 | 8 NFE(`num_inference_steps=9`), guidance 0 [원문] | 지원 안 함 [원문] | "Low" [원문], 커뮤니티는 "diversity collapse" [요약] | DPG 84.86, PRISM 77.4 [원문] |
| **FLUX.2 [klein] 4B**(증류판) | Apache-2.0 [원문] | `Qwen3ForCausalLM` [원문], 크기 확인 못 함 | 아니오 [원문] | "~13GB VRAM (RTX 3090/4070 and above)" [원문] | `Flux2KleinPipeline`, main 브랜치 [원문] | 예제 4/1.0, 단계 증류판은 guidance 무시 [원문] | `negative_prompt_embeds`(미리 만든 텐서)만 받음. 안 주면 빈 문자열을 negative로 씀 [원문] | Base보다 낮음 [원문] | 없음. BFL Elo 차트에 "outperforms Z-Image" 주장만 [원문] |
| FLUX.2 [klein] Base 4B | Apache-2.0 [원문] | 같음 | 아니오 | "~13GB" [원문] | 같음 | 예제 50/4.0 [원문] | CFG는 동작, 문자열 인자 없음 [원문] | "Higher output diversity than the distilled models" [원문] | 없음 |
| FLUX 3 Image Klein(2026-10-15) | FLUX Kommunity License v1.0. 비상업·연구 허용, 연매출 500만 달러 미만 상업 예외 [원문] | Qwen3-VL-4B-Instruct(Apache-2.0) [원문] | **gated**: HF 정보 공유와 라이선스·AUP 동의 [원문] | 생성기 BF16 11.2 GB, FP8 5.6 GB. 참조 코드 최대 B200 31 GB(BF16). INT8 "8GB" [원문] | `ModularPipeline`(main) [원문] | 증류 16/guidance 없음, Base 50/3.5 [원문] | 증류판은 없음 | 확인 못 함 | 없음(BFL 내부 Elo, SDXL 없음) [원문] |
| HiDream-O1-Image(2026-05) | MIT [원문] | 별도 인코더 없는 픽셀 공간 통합 트랜스포머 [원문] | 아니오. Gemma 프롬프트 에이전트만 gated [원문] | 공식 수치 없음. 8B 표기, F32 9B [원문]. 커뮤니티 FP8 약 10 GB, BF16 17–20 GB [요약] | **없음**, 자체 스크립트 [원문] | Full 50/5.0, Dev 28/0.0 [원문] | 확인 못 함 | 확인 못 함 | DPG 89.83 [원문] |
| ERNIE-Image/Turbo(2026-04) | Apache-2.0 [원문] | 카드에 이름 없음 | 아니오 | "24G VRAM" [원문] | `ErnieImagePipeline` [원문] | 50/Turbo 8 [원문] | 확인 못 함 | 확인 못 함 | 없음 |
| LongCat-Image(2025-12) | 확인 못 함 | Qwen2.5-VL-7B [원문] | 확인 못 함 | 약 17 GB(오프로드) [요약] | `LongCatImagePipeline` [요약] | 확인 못 함 | — | — | DPG 86.80 [원문] |

뺀 후보:
- Qwen-Image(2512 포함): 20B에 7B 인코더라 16 GB에서는 양자화가 필요하다.
- HunyuanImage 3.0: 한국을 지역에서 뺀다 [요약, magichour].
- GLM-Image: 80 GB 이상 필요 [요약].
- klein 9B: FLUX NCL(비상업) [원문].

### 1.3 원칙과 부딪치는 기본 설정 (작업 원칙 1, G62)
LLM으로 프롬프트를 고쳐 쓰는 기능은 꺼야 한다.
- ERNIE-Image: 예제가 `use_pe=True`다. GenEval 1위 수치는 PE를 끈 상태에서 나왔다(0.8856) [원문].
- Z-Image: Prompt Enhancer는 선택 사항이다 [원문].
- FLUX.2: `caption_upsample_temperature`가 있다 [원문].
- FLUX 3 Klein: prompt upsampler가 있다 [원문].
- HiDream-O1: Gemma-4-31B 프롬프트 에이전트가 있다 [원문].

텍스트 인코더가 LLM(Qwen3 계열)인 것은 인코딩만 하므로 괜찮다. 다만 원문 문장은 넣지 않는다는 규칙은 그대로 지킨다.

### 1.4 결정성
- diffusers 공식 문서 [원문]: 재현성에는 **CPU `Generator`**를 권한다. `enable_full_determinism()`은 `CUBLAS_WORKSPACE_CONFIG=:16:8`, `torch.use_deterministic_algorithms(True)`, cudnn deterministic, benchmark off, TF32 off를 설정한다. 그래도 문서는 "not *guaranteed* even with an identical seed"라고 적는다.
- 후보 카드는 모두 `manual_seed` 예제만 싣고, 결정성 보증은 없다 [원문].
- Z-Image 보고서는 1초 미만 지연에 FlashAttention-3와 torch.compile이 필요하다고 적는다 [원문]. 실측할 때는 이런 가속을 켠 조건과 끈 조건을 나눠 잰다(추론).

### 1.5 속도 공식 수치
RTX 5080에서 잰 공식 수치는 어느 후보에도 없다.
- klein: "under 0.5s on modern hardware"(GB200, bf16). RTX 5080/5090에서 FP8 "up to 1.6x faster", NVFP4 "up to 2.7x faster" [원문].
- FLUX 3 Klein 증류판 1024²·16단계: RTX 4070에서 8.9 s, INT8로 RTX 5090에서 약 4 s [원문].
- Z-Image-Turbo: H800에서 1초 미만 [원문].

## 2. 앞단 이미지 모델이 3D 결과에 주는 영향
- **TRELLIS** [원문]: "It is always recommended to do text to 3D generation by first generating images using text-to-image models". 이유는 "Text-conditioned models are less creative and detailed due to data limitations." 특정 모델은 권하지 않는다.
- **TripoSG** [원문]: RMBG-1.4로 배경을 지운다. "photorealistic images, cartoons, and sketches"를 다룬다고 적었다. 앞단 모델 권고는 없다.
- **Hunyuan3D-1 text→image 코드** [원문]: 프롬프트 뒤에 ",白色背景,3D风格,最佳质量"을 붙이고, negative에 "文本,特写,裁剪,出框" 등을 넣는다. HunyuanDiT 25단계, seed 기본값 0. 우리 방식과 같은 설계다. Hunyuan3D 자체는 한국 지역 제외 라이선스라 쓰지 않는다.
- **Hunyuan3D-2 README** [원문]: 앞단 모델 이름이 없다.
- 앞단 T2I를 바꿔 가며 3D를 비교한 논문은 찾지 못했다. 가까운 것은 다음과 같다.
  - ISS(arXiv 2209.04145): 저품질 영역 밖 이미지가 3D를 제한한다 [요약].
  - Turbo3D(arXiv 2412.04470): Flux를 앞단으로 고정 [요약].
  - ART-DECO(arXiv 2505.20431): SD와 MVDream을 SDS 계열에서 비교 [요약].
- 결론: 공식 권고는 "text→image, 흰 배경, 물체 하나, 배경 제거"까지다. **어느 T2I 모델이 3D에 더 좋은지에 대한 정량 근거는 없다.** 그래서 실측 판정에 TripoSG 출력을 넣는다.

## 3. 권고

### 3.1 순위
1. **1순위: Z-Image(base).** Apache-2.0이고 gated가 아니다. DPG 88.14 대 74.65, PRISM 75.6 대 57.0이다. 다양성 "High", negative 지원이다. 약점은 28–50단계로 느리다는 점과 16 GB 공식 수치가 없다는 점이다(오프로드나 인코더 양자화가 필요할 수 있음).
2. **2순위: FLUX.2 [klein] 4B 증류판과 Base.** Apache-2.0, gated 아님, "~13GB"다. 약점은 SDXL과 같은 표의 벤치마크가 없고, negative를 문자열로 줄 수 없고, 증류판 다양성이 낮을 수 있다는 점이다.
3. **보류**
   - Z-Image-Turbo: 다양성 Low, negative 없음.
   - FLUX 3 Klein: gated, Apache가 아님, 참조 메모리 31 GB.
   - HiDream-O1: diffusers 없음, VRAM 미기재.
   - ERNIE-Image: 24 GB, PE 기본.
   - LongCat-Image: 7B 인코더, 라이선스 미확인.
4. **SDXL은 기준선이자 후보다.** 1·2순위가 아래 기준에서 SDXL보다 낫지 않으면 SDXL을 유지한다.

### 3.2 이 PC에서 실측할 항목과 통과 기준(제안)
고정 조건:
- 1024²
- diffusers 버전·모델 리비전·가중치 해시 기록
- CPU Generator
- PE·upsampler 모두 끔
- 같은 프롬프트 표(`tools/gen3d/prompts.py`의 영어 프롬프트와 negative)
- 이미지 모델을 내린 뒤 TripoSG 실행

| 항목 | 재는 법 | 통과 기준(제안) |
|---|---|---|
| VRAM | `torch.cuda.max_memory_allocated`, 오프로드 여부 기록 | ≤ 14 GB |
| 속도 | 모델을 올린 뒤 seed 3개로 3장 생성. 처음 한 번은 버리고 5회 중앙값 | 3장 ≤ 20 s, SDXL(30단계) 실측값의 1.5배 이하 |
| 결정성 | 같은 seed 3회(프로세스 재시작 포함), PNG SHA-256 비교, 다르면 최대 픽셀 차이 기록 | 바이트 일치. 가속을 켜서 깨지면 끈 설정 채택 |
| 충실도 | 20 프롬프트 × 3 seed = 60장. 20개 중 8개 이상은 추상·드문 사물. 두 사람이 모델을 가리고 판정: ① 말한 물체 하나만 ② 다른 물체·사람·글자·받침대 없음 ③ 프레임 안에 온전히 | ①②③ 동시 만족 ≥ 90%이고 SDXL 이상. 사람 0장. 추상 부분집합도 SDXL 이상 |
| 배경·마스크 | RMBG-1.4: 연결 성분 1개, 전경 10–70%, 테두리에 닿지 않음 | ≥ 95%, SDXL 이상 |
| 화풍 | 전경 HSV 채도 평균 | ≤ 0.15인 비율 ≥ 90%(임계값은 SDXL을 보고 조정) |
| 후보 3장 다양성 | 3장 마스크 사이 쌍별 IoU | 프롬프트의 80% 이상에서 최대 IoU < 0.9 |
| 3D 하류 | 60장 모두 TripoSG: 성공 여부, 연결 성분 수, 수밀 여부 | SDXL 이상 |

판정 규칙: 충실도·결정성·VRAM 가운데 하나라도 통과하지 못하면 탈락이다. 둘 다 통과하면 속도와 다양성을 보고 고른다. 바꾸면 docs/decisions.md에 기록하고 캐시 키의 모델 리비전을 갱신한다.

## 교차 확인(R1, Codex, 2026-11-28)에서 고친 것
- PRISM-Bench 영어 수치는 Table 12가 아니라 Table 13이다(Table 12는 중국어판). 수치는 맞다.
- FLUX.2 klein의 negative는 문자열 인자가 없는 것이 아니라 텐서(`negative_prompt_embeds`)로만 받는다.
- klein의 4단계/50단계 설정은 모델 카드에서 확인되지 않았다(실측 때 공식 예제를 다시 확인).
- 1·2순위는 공개 근거에서 따라 나오는 결론이 아니라 카드 정보(다양성·negative·VRAM)에 따른 실측 후보 선정이다.

## 확인 못 함
- FLUX.2 klein 4B의 GenEval·DPG·T2I-CompBench(찾지 못함). Artificial Analysis Elo 839는 SDXL이 같은 화면에 없어 쓰지 않았다.
- klein 4B 텍스트 인코더의 크기와 라이선스.
- Z-Image base의 공식 VRAM과 오프로드 없이 16 GB에서 도는지.
- SDXL을 포함한 사람 평가 아레나(Z-Image 보고서의 Alibaba AI Arena 표에는 SDXL이 없음).
- '덧붙이지 않음', 점토 화풍, 추상 사물을 따로 잰 벤치마크. arXiv 2611.16630(over-realization)은 부정·비유 문맥을 다루고, 평가 모델 이름을 확인하지 못했다.
- FLUX Kommunity License v1.0 전문(지역 제한 판단은 카드에 언급이 없다는 데에만 기댐).
- HiDream-O1의 공식 VRAM, LongCat 가중치 라이선스, ERNIE 텍스트 인코더.
- Point-E(arXiv 2212.08751) 본문의 GLIDE 미세조정 이유(초록만 확인).
- RTX 5080 실측 속도, 그리고 FlashAttention·compile을 켰을 때의 결정성.

## 결론을 떠받치는 서지·수치 목록
1. https://arxiv.org/html/2511.22699v2 (Z-Image Table 10·13) — DPG SDXL 74.65 대 Z-Image 88.14·Turbo 84.86. PRISM 영어 SDXL 57.0 대 Z-Image 75.6·Turbo 77.4. Style 정합 71.7 대 76.7.
2. https://arxiv.org/html/2403.03206 (SD3 Table 5) — GenEval SDXL 0.55, 단일 물체 0.98(천장 효과).
3. https://huggingface.co/Tongyi-MAI/Z-Image — Apache-2.0, 28–50단계, guidance 3–5, negative 지원, 다양성 base "High"·Turbo "Low".
4. https://huggingface.co/Tongyi-MAI/Z-Image-Turbo — Apache-2.0, 8 NFE, guidance 0, "fits comfortably within 16G VRAM".
5. https://huggingface.co/black-forest-labs/FLUX.2-klein-4B 및 https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B — Apache-2.0, "~13GB", 4단계 / 50단계, Base "Higher output diversity than the distilled models".
6. https://huggingface.co/docs/diffusers/main/en/api/pipelines/flux2 — `Flux2KleinPipeline` 인코더 `Qwen3ForCausalLM`, negative는 `negative_prompt_embeds`(텐서)로만, 단계 증류판은 guidance 무시.
7. https://github.com/microsoft/TRELLIS — "always recommended to do text to 3D generation by first generating images using text-to-image models".
8. https://huggingface.co/docs/diffusers/main/en/using-diffusers/reusing_seeds — CPU Generator 권장, `enable_full_determinism` 구성, 같은 seed라도 "not guaranteed".
