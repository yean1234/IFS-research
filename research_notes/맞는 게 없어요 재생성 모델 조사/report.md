# "맞는 게 없어요" 뒤 재생성: 로컬 3D 생성 모델 추가 조사 (2026-11-27)

> 조사: Claude 하위 에이전트(웹 검색·원문 열람). 메인이 받아 옮겼다. **서지·수치는 한 에이전트가 모은 것이고 다른 출처로 교차 확인하지 않았다.** 논문에 인용하기 전에 원문을 직접 확인한다(CLAUDE.md 조사 교차 확인 RN). [원문]은 페이지·파일을 직접 열어 본 것, [요약]은 검색 요약·스니펫만 본 것, [보조]는 블로그·커뮤니티·집계 사이트. 확인 날짜는 모두 2026-11-27.

범위: 기존 조사(`reports/심상 외부화 3D 생성 모델 검토.md`, `research_notes/심상 외부화 3D 생성 모델 검토/`, `docs/gen3d-feasibility.md` G62 절, `docs/decisions.md` G62–G62-i)에 이미 있는 내용은 빼고 새로 확인한 것만 적는다.

## 0. 요약
- **지금 경로(SDXL→TripoSG)는 유지해도 된다.** Windows·Python 3.11·VRAM 16 GB에서 돌아가고 한국에서 라이선스상 쓸 수 있으면서 TripoSG보다 낫다고 독립적으로 확인된 공개 모델은 없었다.
- **재생성 2순위는 Cube 3D v0.5.** 라이선스 원문: Research-Only RAIL-MS, 지역 제한 없음. 텍스트에서 형태로 바로 가며, 제3자 비교에서 공개 텍스트→3D 모델 가운데 텍스트-형태 정렬 점수가 가장 높았다.
- **한국어 직접 입력**: 텍스트→3D 모델은 모두 영어 CLIP 계열 인코더. 텍스트→이미지에서는 Qwen-Image가 한국어에서도 영어에 가까운 점수, SDXL은 크게 떨어짐. 문장을 직접 넣는 방식은 원칙 1·2(G62-f)와 맞지 않는다.
- **흐린 대상**: 볼류메트릭 결과를 만드는 로컬 생성 모델이 없다. 규칙 기반 파티클·셰이더 처리를 유지한다.

## 1. 2025–2026 로컬 후보: 새로 확인한 것

### 1.1 Cube 3D v0.5 (Roblox)
- 라이선스 [원문]: "CUBE3D RESEARCH-ONLY RAIL-MS LICENSE", "worldwide, non-exclusive, royalty-free", Permitted Purpose "for academic or research purposes only". 지역 제한 없음 → 한국 연구용 가능. Attachment A 관련 금지 조항: "to provide health or medical advice"(이 연구는 자기성찰 보조로 걸리지 않는다고 보나 연구 책임자 확인 필요), 동의 없이 사람의 생김새 합성(이미 사람 형상 차단). https://raw.githubusercontent.com/Roblox/cube/main/LICENSE
- 표기 불일치: HF 카드 태그는 "openrail" [원문] https://huggingface.co/Roblox/cube3d-v0.5 . v0.1 저장소에서 research-only RAIL-MS로 이름을 바꾼 토론 [요약] https://huggingface.co/Roblox/cube3d-v0.1/discussions/3/files . GitHub LICENSE 원문을 기준으로 삼는다.
- 텍스트 인코더 [원문]: "pre-trained CLIP text encoder"(변형 이름 없음), 학습 캡션은 GPT-4o가 렌더 이미지로 만듦 → 영어 입력 전용으로 본다. 다른 모델과 정량 비교 없음("approaching the visual quality"). arXiv 2503.15475v2 https://arxiv.org/html/2503.15475v2
- 제3자 비교 [원문]: Block3D(Cui et al., arXiv 2608.19567v4) https://arxiv.org/html/2608.19567 , TRELLIS-500K에서 떼어 둔 100개, CLIP은 8시점 평균, 시간은 A100 80GB.

| 모델 | CD-L1↓ | NC↑ | F@1%↑ | CLIP↑ | 시간 |
|---|---|---|---|---|---|
| ShapeLLM-Omni | 0.229 | 0.490 | 0.089 | 19.08 | 36.9 s |
| TRELLIS-text-xlarge | 0.222 | 0.496 | 0.090 | 20.41 | 11.7 s |
| AR3D-R1 | 0.145 | 0.583 | 0.162 | 21.92 | 79.8 s |
| Cube | 0.094 | 0.632 | 0.219 | 23.87 | 25.7 s |
| Block3D | 0.078 | 0.668 | 0.309 | 23.24 | 5.0 s |

텍스트→3D끼리의 비교이고 지금 경로(텍스트→이미지→3D)와 직접 비교한 것은 아니다. Block3D 가중치 공개·라이선스는 확인 못 함.

### 1.2 Pixal3D — 독립 검증 없음
- 저자 보고 [원문]: Li et al., SIGGRAPH 2026/TOG, arXiv 2605.10922 https://arxiv.org/html/2605.10922v1 . 실제 이미지 150장 사용자 연구(1–5점): Pixal3D 4.91/4.74, Direct3D-S2 3.21/3.64, Hunyuan3D-2.1 2.77/2.50, TripoSG 2.25/2.14, TRELLIS 1.86/1.99(Fidelity/Quality). Toys4K 법선 IoU Pixal3D 93.57, TripoSG 73.54. TRELLIS.2는 비교에 없음.
- HF 카드 [원문]: MIT, `--low_vram`(해상도 1536→1024, VRAM 수치 없음), 시험 OS 미기재, 출력 PBR GLB, TRELLIS.2 환경 + natten 0.21.0. https://huggingface.co/TencentARC/Pixal3D

### 1.3 TRELLIS.2 — 바뀐 것 없음 [원문]
"at least 24GB", "tested only on Linux", 이미지→3D만. https://github.com/microsoft/TRELLIS.2

### 1.4 TripoSG 쪽
- TripoSG-scribble(2025-04) [원문]: 낙서+프롬프트, CFG 증류, 512 토큰, "fast shape prototyping". 사용자 수정 경로 후보. https://github.com/VAST-AI-Research/TripoSG
- FlashVDM(ICCV 2025, arXiv 2503.16302) [원문]: VAE 디코딩 45배 이상, 확산 50→5단계. TripoSG는 "Community Supported Model". LICENSE 원문 확인 못 함(Tencent 저장소라 지역 조항 확인 필요), TripoSG 실측 속도 없음. https://github.com/Tencent-Hunyuan/FlashVDM

### 1.5 쓸 수 없거나 맞지 않는 후보
- SAM 3D Objects: SAM License worldwide [원문], 그러나 "at least 32 Gb of VRAM", "linux-64" [원문]. 16 GB 불가. https://raw.githubusercontent.com/facebookresearch/sam-3d-objects/main/LICENSE , https://raw.githubusercontent.com/facebookresearch/sam-3d-objects/main/doc/setup.md
- Hunyuan3D-Omni: 한국 제외는 2차 출처로만 [보조] https://deepwiki.com/Tencent-Hunyuan/Hunyuan3D-Omni/6.1-licensing-and-legal . 쓰지 않는다.
- UltraShape 1.0: 가중치 Apache-2.0 [요약]이나 거친 메시를 Hunyuan3D-2.1에서 받음 [요약] → 그대로는 못 씀. https://huggingface.co/infinith/UltraShape/blob/main/README.md
- LATTICE(CVPR 2026): Hunyuan3D 2.5/3.0 기반 [요약], 가중치 라이선스 확인 못 함. https://lattice3d.github.io

### 1.6 공개 벤치마크
- 3D Arena(Ebert, arXiv 2506.18787) [원문] https://arxiv.org/html/2506.18787v1 : 2025-05-30 기준 투표 123,243건. Elo TRELLIS-3DGS 1384, TRELLIS 메시 1306, Hunyuan3D-2 1298, Hi3DGen 1207, SF3D 1190, SPAR3D 1144, TripoSR 1089. TripoSG 없음. 텍스처 +144.1, 가우시안 +16.6(형태만 쓰는 이 연구에 바로 옮길 수 없음).
- T3Bench·GPTEval3D: 2025–2026 로컬 모델 점수를 찾지 못함.
- 논문 간 수치는 프로토콜이 달라 옮겨 비교할 수 없다(예: Hunyuan3D-2.1 논문 ULIP-T TripoSG 0.0767, Step1X-3D 0.0735, TRELLIS 0.0769, Direct3D-S2 0.0706 [요약]).

## 2. 한국어 직접 입력
- 텍스트→3D: 한국어·다국어 텍스트를 직접 받는 로컬 모델은 찾지 못함(Cube·TRELLIS-text는 CLIP 계열).
- 텍스트→이미지 [원문]: Zhang et al., ACM MM 2026, arXiv 2608.11002 https://arxiv.org/html/2608.11002 . 10개 언어 × 3,000 프롬프트, MetaCLIP2-worldwide-huge CLIPScore(자동 점수, 일반 프롬프트).

| 모델 | 영어 | 한국어 |
|---|---|---|
| Qwen-Image | 0.82 | 0.77 |
| MuLan | 0.73 | 0.65 |
| X2I | 0.72 | 0.63 |
| PEA | 0.64 | 0.59 |
| Z-Image | 0.64 | 0.57 |
| Sana 1.5 | 0.78 | 0.46 |
| SDXL | 0.78 | 0.31 |
| SD3.5 | 0.79 | 0.27 |
| FLUX.1-Krea | 0.77 | 0.26 |

- Qwen-Image [원문]: Apache-2.0, 약 20B, BF16, 언어 태그 영어·중국어, VRAM 미기재 https://huggingface.co/Qwen/Qwen-Image . 텍스트 인코더는 동결한 Qwen2.5-VL [요약, arXiv 2508.02324]. 16 GB에는 양자화 필요.
- Z-Image-Turbo·FLUX.2 klein 4B가 Qwen3-4B 인코더를 쓴다는 정보는 커뮤니티 출처뿐 [보조]. Motif-Image-6B-Preview [원문]: MIT, 언어 태그 영어·한국어, 한국어 평가·인코더·VRAM 정보 없음 https://huggingface.co/Motif-Technologies/Motif-Image-6B-Preview . KoDi(IEEE Access 13, 2025)는 서지만 확인 https://researchr.org/publication/JungLC25
- 원칙과의 관계: 문장을 직접 넣으면 LLM 계열 인코더가 감정어·색·비유까지 해석해 G62-f와 충돌. 규칙이 고른 한국어 형태 낱말만 넣는 방식은 가능하나 낱말 하나의 한국어 품질 근거는 없음.

## 3. 형태가 흐린 대상
- 텍스트·단일 이미지에서 볼류메트릭 결과를 만드는 로컬 생성 모델은 없다. 찾은 것은 동영상 기반 연기 복원 [요약]: SmokeSVD arXiv 2507.12156, WildSmoke arXiv 2509.11114. 구름 밀도 확산(arXiv 2501.05226)은 텍스트 조건이 아니며 공개 볼륨 데이터셋이 없다고 적음 [요약].
- 가우시안 출력: DiffSplat(ICLR 2025), MIT [요약] https://huggingface.co/chenguolin/DiffSplat . DiffSplat·TRELLIS v1은 물체 데이터로 학습, 안개 근거 없음.
- Unity: aras-p UnityGaussianSplatting [원문](MIT, DX12/Vulkan, PLY·SPZ 실행 중 로드, Quest 3 "reportedly", 2026-11 "not planning any significant further development") https://github.com/aras-p/UnityGaussianSplatting ; ninjamode Unity-VR-Gaussian-Splatting [원문](MIT, Unity 6000.3+, "desktop as well as Quest 3") https://github.com/ninjamode/Unity-VR-Gaussian-Splatting ; Meta Spatial SDK [원문](Unity 아님, Quest 3/3S, 스플랫 1개, 150k 이하 권장) https://developers.meta.com/vr/documentation/spatial-sdk/spatial-sdk-splats/ ; SplatXR Quest 3 단독 50k–200k 59–72 fps [보조] https://radiancefields.com/splatxr-brings-interactive-gaussian-splats-to-quest-3
- 판단: 흐린 대상은 생성하지 않는다(G62-e). 규칙이 정하는 파티클·볼륨 셰이더로 처리한다(G74).

## 4. 연구 근거: 재생성, 사용자 수정, 소유감
(이미 기록된 Metamorpheus, Wang 2026, Pataranutaporn 2025, Refugio, MentalImager, CyberSelf, Worry Gallery는 제외)
- **VRCopilot** (Zhang, Pan, Gettig, Oney & Guo, UIST 2024, arXiv 2408.09382) [원문] https://arxiv.org/html/2408.09382v1 : 연구 2 N=15, 피험자 내 수동·스캐폴드·자동. 행위주체감 수동 > 스캐폴드 > 자동, χ²(2)=20.11, p<.001, 모든 쌍 p<.001. CSI χ²(2)=17.63(스캐폴드–자동 차이 없음). NASA-TLX 차이 없음(p=.63). 소유감 척도 없음, 인터뷰 "it doesn't feel fully like I designed it"(P28). 재생성 횟수 미측정. 시사점: 사용자가 틀(비율·윤곽)을 정하는 스캐폴드가 자동보다 행위주체감이 높다 — Cube 경계상자 조건, TripoSG-scribble이 이 방식.
- **Memory Printer** (Fang & Huang, CHI 2026, arXiv 2603.13116) [원문] https://arxiv.org/html/2603.13116 : N=24, 조건 순서 고정, 정량 척도 없음. 19/24가 정확한 시각 일치보다 분위기를 원함, 23/24가 생성 인물이 닮지 않은 것을 받아들임. 다시 그린 횟수 미측정. 생성 이미지가 기억과 섞일 걱정(P14).
- **ClayFlect** (Sim, Nguyen, Han & Choo, arXiv 2610.08943, 동료 심사 전) [원문 초록] https://arxiv.org/abs/2610.08943 : N=50 혼합 방법. AI 출력을 "provisional"로 다룸. 사용자가 통제하는 공간을 남기라고 권함.
- **안전 필터의 비용** (Liu et al., arXiv 2605.09606, cs.CR) [원문 초록] https://arxiv.org/abs/2605.09606 : 입력 검열·모델 정렬·출력 필터를 겹치면 유해 형상 잔존 <1%, 오탐 11%. 사람·동물 관문의 오탐과 같은 종류의 비용.
- 찾지 못한 것: 내면 내용 외부화에서 "맞지 않음 → 재생성"을 정량으로 잰 연구.

## 5. 권고
전제: G62 규칙 그대로(형태를 말하지 않으면 생성 안 함, '생성' 출처 기록, 사용자가 확인해야 씀, 크기·위치는 모델이 정하지 않음). 재생성은 정해진 seed 순서(기준 seed + n)를 쓰고 기록한다.
- **1순위: SDXL→TripoSG 유지, 다음 seed로 재생성.** 결정성(같은·다른 프로세스 34/34), 후보당 약 27–30초, MIT, Windows·py3.11에서 동작, 더 낫다고 독립 확인된 대체 없음. 다음 단계 시험: 앞단만 Z-Image-Turbo나 FLUX.2 klein 4B(Apache-2.0)로 바꿔 보기(효과 근거 없음).
- **2순위: Cube 3D v0.5를 다른 계열 후보로 덧붙임.** (1) 이미지 단계에서 물체가 덧붙는 경로가 없음 (2) 경계상자 조건을 G72 비율(말한 것만)에 연결 가능, VRCopilot 스캐폴드 근거와 맞음 (3) 공개 텍스트→3D 중 CLIP 최고(23.87) (4) 연구용이면 한국 사용 가능 (5) 저자에 따르면 `top_p`를 설정하지 않으면 결정적 (6) seed만 바꾸면 같은 종류의 실패가 반복되는 것을 다른 계열로 피함. 남은 조건: 이 PC 실측(VRAM·시간·결정성), 연구 책임자의 라이선스 확인.
- **보류**: Pixal3D·TRELLIS.2(열린 표면이 필요해지면 별도 환경), Qwen-Image 한국어 직접 입력(원칙 충돌), 볼류메트릭·가우시안 생성.

## 6. 확인하지 못한 것
1. Cube의 RTX 5080·Windows 실측, CLIP 변형 이름. 2. FlashVDM LICENSE와 TripoSG 속도 효과. 3. Hunyuan3D-Omni LICENSE 원문. 4. LATTICE·Block3D 가중치 공개·라이선스. 5. Pixal3D·TRELLIS.2 독립 비교, Pixal3D low_vram 실제 VRAM, Windows 동작. 6. T3Bench·GPTEval3D 점수, 3D Arena 최신 순위. 7. 한국어 낱말 하나의 품질, Qwen-Image 양자화본의 품질·결정성, Z-Image·klein 공식 다국어 지원. 8. Motif-Image-6B 인코더·한국어 평가, KoDi 원문·가중치. 9. 볼류메트릭 로컬 모델. 10. DiffSplat 바탕 모델 라이선스. 11. 재생성과 소유감·일치감을 정량으로 잰 연구. 12. Regenerated Memories 본문(DOI 10.1145/3786995.3787031, 403 오류).
