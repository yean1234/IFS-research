# 자유 심상을 3D로: 생성형·절차형 대안 실현성 점검 (2026-11-22, 실험 경로)

**문제.** 지금 Unity는 형태 프리셋 4종(blob·mist·shell·fragments)과 모양 모형 4종(구·정육면체·납작 원기둥·원뿔)에 색·밝기·거칠기·투명도·침식·크기 같은 매개변수를 얹어서만 그립니다(`docs/shape-mapping.md`, `docs/mapping-audit.md`). 그래서 선이 엉킨 심상, 젖은 종이 같은 재질, 금속 손 같은 구체 사물처럼 이 틀 밖의 심상은 그리지 못합니다(실제 답변 원문은 이 문서에 옮기지 않고 유형만 적습니다). 이 문서는 그 한계를 풀 방법을 조사하고, 그중 생성형 두 경로를 로컬에서 끝까지 연결해 실제로 되는지 확인한 기록입니다.

- **이 작업은 실험용 별도 경로입니다.** 기존 SceneSpec 파이프라인·러너·테스트·사전은 바꾸지 않았습니다. 코드는 `tools/gen3d/`(Python)와 `unity/Assets/IFS/Runtime/Experimental/Gen3D/`(별도 asmdef `IFS.Gen3D`, `IFS.Gen3D.Editor`)에만 있습니다.
- **원칙과 충돌합니다(8절).** 생성 모델은 참여자가 말하지 않은 형상·재질·색을 반드시 채웁니다. 원칙 1(장면 속성은 사전·규칙만)과 원칙 2(말하지 않은 것을 추론하지 않음)에 정면으로 어긋납니다. 이 경로의 결과를 SceneSpec 물체와 같은 지위로 기록하거나 분석하지 않습니다. AGENTS.md는 고치지 않았습니다.
- 선행 연구의 시각화 방식과 공개 3D 모델의 1차 판단은 `docs/rq-v4-proposal.md` 5절에 있어 되풀이하지 않습니다. 이 문서는 그 표에 설치 가능성·속도·실측을 더합니다.

## 1. 결론 먼저

- **돌아가는 것.** 한국어 문장 → (규칙 또는 로컬 LLM) 영어 프롬프트 → 로컬 생성 모델 → GLB + 메타데이터 → Unity glTFast 런타임 로드 → 정면·사선 PNG까지 끝까지 연결했습니다. 경로 두 개: **Shap-E**(text→3D, 문장당 약 3초, VRAM 2.5 GiB), **SDXL → TripoSR**(text→image→3D, 약 7.6초, VRAM 최대 12.5 GiB). 모두 로컬, seed 고정 시 GLB가 바이트까지 같았습니다(120/120, 다른 프로세스 6/6).
- **질은 목적에 못 미칩니다.** 30문장 × 생성 4조합 = 120개 중 문장과 맞은 것은 4개였고, 모두 규칙 경로도 그리는 공·상자였습니다. 규칙 경로가 못 그리는 안개·선·종이·천·유리는 생성형도 고체 덩어리로 바꾸거나 실패했습니다. 외형 서술이 없는 답에도 반드시 형상을 지어냈습니다.
- **원칙 1·2와 정면으로 충돌**합니다(8절). 본 실험에는 쓰지 않는 것을 권합니다.
- **다음으로 권하는 것은 절차적 확장**(선·엉킴·판·처짐·입자 안개)입니다. 화이트박스를 지키면서 이번 실제 응답에서 가장 많이 놓친 유형을 덮습니다. 구체 사물은 검수 에셋 + 사전 선택으로 보완하고, 이번에 넣은 glTFast 로더를 그대로 쓸 수 있습니다(11절).
- **기존 테스트**: dotnet compile-check 168/168, Unity EditMode 192/192 통과(glTFast 6.21.0 추가 후).

## 2. 조사

### 2.1 Unity에서 런타임에 3D 파일 읽기

이 프로젝트는 **Built-in 렌더 파이프라인**입니다(`GraphicsSettings.currentRenderPipeline == null`, 캡처 report의 `renderPipeline`). IFS 셰이더도 Built-in 전용입니다(`unity/README.md`).

| 후보 | 확인한 것 | 출처(실제로 연 URL) |
| --- | --- | --- |
| **glTFast** `com.unity.cloud.gltfast` | 최신 6.21.0(2026-11-11), `unity: 6000.0`. 의존: burst 1.8.30, collections 2.6.8, mathematics 1.3.3, jsonserialize, unitywebrequest(UPM이 같이 설치함 — 이번 설치에서 `packages-lock.json`으로 확인). Apache-2.0. 런타임 API: `new GltfImport(downloadProvider, deferAgent)` → `Load(byte[] data, Uri uri, ImportSettings, ct)`(옛 `LoadGltfBinary`는 obsolete) → `InstantiateMainSceneAsync(Transform)`. `UninterruptedDeferAgent`는 가장 빠르지만 메인 스레드를 막을 수 있고, 실행 중에는 `TimeBudgetPerFrameDeferAgent`(기본)가 프레임을 지킴. `Load`가 true여도 "치명적 오류 없음"일 뿐이라 부분 로드일 수 있음 | https://packages.unity.com/com.unity.cloud.gltfast · https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/api/GLTFast.GltfImportBase.html · https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/manual/ImportRuntime.html · https://github.com/Unity-Technologies/com.unity.cloud.gltfast |
| glTFast — Built-in 빌드 셰이더 | **빌드(헤드셋)에서는** glTFast 셰이더 변형을 반드시 포함해야 함: *Always Included Shaders*(ProjectSettings ▸ Graphics) 또는 Resources에서 참조, 또는 Shader Variant Collection을 Preloaded Shaders에. 에디터·배치 캡처에서는 필요 없음(이번 캡처는 설정 변경 없이 `glTF/PbrMetallicRoughness`로 그려짐). **ProjectSettings는 이번에 바꾸지 않았음** — 헤드셋 빌드 전에 사람이 정할 것(11절) | https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/manual/ProjectSetup.html |
| glTFast — Android/Quest | 문서·README에 Android/Quest 지원 여부 언급을 찾지 못함. 순수 C# + Burst라 막을 이유는 없어 보이나 **기기에서 확인 안 함** | https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.21/manual/features.html |
| UnityGLTF (Khronos) | MIT, git URL로 설치(`org.khronos.unitygltf`), 런타임 `GLTFSceneImporter.LoadSceneAsync()`. Unity 2021.3+. 대안으로 충분하나 Unity 공식 레지스트리 패키지가 아님 | https://github.com/KhronosGroup/UnityGLTF |
| USD | `com.unity.formats.usd`는 legacy, 후속 `com.unity.importer.usd`는 에디터 전용·pre-release. 런타임 로드 용도로는 맞지 않음(검색 결과 요약만 봄, 공식 페이지 미확인) | — |

**고른 것: glTFast 6.21.0.** 공식 레지스트리, Unity 6 지원, 런타임·에디터 모두 같은 API, GLB(바이너리 glTF) 한 파일로 메시·정점 색·텍스처를 옮길 수 있습니다. 생성 모델 쪽(trimesh)도 GLB를 바로 씁니다.

### 2.2 16 GB VRAM·Windows에서 도는 무료 3D 생성 모델

라이선스는 저장소 LICENSE와 HF 모델 카드 원문으로 확인했습니다(조사 에이전트, 2026-11-22).

| 모델 | 입력 | 라이선스(코드 / 가중치) | VRAM·속도(문서) | Windows·설치 | 이번 판단 |
| --- | --- | --- | --- | --- | --- |
| **Shap-E** (OpenAI) | 영어 텍스트 | MIT / MIT | 작음 | diffusers `ShapEPipeline`, 추가 설치 없음 | **경로 A로 구현** |
| **TripoSR** (VAST·Stability) | 이미지 | MIT / MIT | 약 6 GB, A100 0.5초 미만 | `torchmcubes`(CUDA 확장 빌드)가 걸림 → skimage 마칭 큐브로 대신(4.3절) | **경로 B의 image→3D로 구현** |
| Stable Fast 3D | 이미지 | Stability AI Community License(연 매출 100만 달러 미만이면 연구·상업 무료) / 같음, HF 약관 동의 필요 | 약 6 GB | Windows 실험적, VS2022로 C++ 확장 빌드 | 약관 동의가 사람 몫이라 시도 안 함 |
| InstantMesh | 이미지(다시점 확산 포함) | Apache-2.0 / Apache-2.0 | 문서에 없음 | xformers 0.0.22 고정, nvdiffrast | Blackwell(sm_120)·최신 torch와 버전 고정이 맞지 않아 시도 안 함 |
| TRELLIS | 이미지·**텍스트**(text-base 342M ~ xlarge 2.0B) | MIT / MIT(일부 서브모듈 별도) | **16 GB 이상** | Linux에서만 시험, spconv·flash-attn·nvdiffrast·kaolin | 16 GB 경계 + Windows 빌드 위험으로 시도 안 함 |
| TRELLIS.2 | 이미지만 | MIT / MIT | **24 GB 이상** | Linux 전용 | 맞지 않음 |
| TripoSG | 이미지 | MIT / MIT | 8 GB 이상 | 문서에 Windows 언급 없음 | 다음 후보(형상만, 색 없음) |
| Direct3D-S2 | 이미지 | MIT | 512 해상도 10 GB, 1024 약 24 GB | issue로만 Windows 논의 | 다음 후보 |
| Step1X-3D | 이미지 | Apache-2.0 | 27–29 GB | — | 맞지 않음 |
| SPAR3D | 이미지 | Stability Community | 미확인 | — | SF3D와 같은 조건 |
| Hunyuan3D-2.1 | 이미지 | Tencent 커뮤니티 — Territory 원문 "excluding … European Union, United Kingdom and **South Korea**" | — | — | **쓰지 않음** |

text→image(경로 B의 앞 단계):

| 모델 | 라이선스 | 비고 |
| --- | --- | --- |
| **SDXL base 1.0** | CreativeML Open RAIL++-M(이용 제한 조항 있음, 연구 가능) | **이 PC의 HF 캐시에 이미 있어 내려받기 없이 사용** |
| SDXL-Turbo | `sai-nc-community`(비상업·연구 허용) | 1–4 단계라 더 빠름. 이번에는 안 씀 |
| FLUX.1-schnell | Apache-2.0, 12B | bf16 트랜스포머만 약 24 GB(계산값) → 16 GB에서는 offload·양자화 필요, 내려받기 약 34 GB. 라이선스는 가장 깔끔해 다음 후보 |
| Sana 1600M | 메타데이터 apache-2.0이나 카드에 "research purposes only", 텍스트 인코더 Gemma 약관 추가 | 시도 안 함 |

출처: https://huggingface.co/openai/shap-e · https://github.com/VAST-AI-Research/TripoSR · https://huggingface.co/stabilityai/TripoSR · https://github.com/Stability-AI/stable-fast-3d · https://huggingface.co/stabilityai/stable-fast-3d · https://github.com/TencentARC/InstantMesh · https://github.com/microsoft/TRELLIS · https://github.com/microsoft/TRELLIS.2 · https://github.com/VAST-AI-Research/TripoSG · https://github.com/DreamTechAI/Direct3D-S2 · https://github.com/stepfun-ai/Step1X-3D · https://huggingface.co/stabilityai/stable-point-aware-3d · https://huggingface.co/tencent/Hunyuan3D-2.1/blob/main/LICENSE · https://huggingface.co/stabilityai/sdxl-turbo · https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 · https://huggingface.co/black-forest-labs/FLUX.1-schnell · https://huggingface.co/Efficient-Large-Model/Sana_1600M_1024px

### 2.3 한국어 서술 → 영어 프롬프트

| 방법 | 동작 | 원칙 | 이번 구현 |
| --- | --- | --- | --- |
| ① 로컬 LLM 번역 | Ollama `gemma4:e4b`(digest `dc35e8d9c606…`), temperature 0·seed 0, "말한 외형만, 덧붙이지 말 것" 지시 | **원칙 1 위반**(LLM을 유도 밖에 씀). 번역이 무엇을 남기고 버릴지 LLM이 정함 | `--prompt-mode llm`(비교용) |
| ② 화이트박스 조립 | 기존 규칙 추출기(`SceneSpecBuilderV1`, 코드 무수정 호출)가 만든 SceneSpec의 **말한 슬롯만** 고정 표로 영어 낱말에 옮김(`tools/gen3d/prompts.py`, `gen3d-prompt-rules/0.1.0`). 같은 spec → 같은 프롬프트 | 프롬프트 단계는 원칙 1·2와 맞음. 단 생성 모델이 빈칸을 채움 | `--prompt-mode rules`(기본) |
| ③ 한국어 직접 입력 모델 | 한국어를 직접 받는 text-to-3D는 찾지 못함. Kolors는 중국어·영어, Karlo는 영어 예시뿐. Motif-Image-6B-Preview(MIT)에 Korean 태그가 있으나 한국어 프롬프트 지원 명시는 없음 | — | 없음 |

②는 규칙 추출기가 놓친 낱말(엉킴·종이·금속 같은 재질어, 합성 예문 D03의 '나무로 된')을 프롬프트에 넣지 못합니다. 추출기가 아무 슬롯도 못 채우면 프롬프트는 "a single object"가 되고, 생성 모델이 형상을 통째로 지어냅니다(7절).

### 2.4 화이트박스를 유지하는 대안

이번에는 **구현하지 않고 평가만** 했습니다. 이 Unity 프로젝트에는 파티클(`com.unity.modules.particlesystem`)이 이미 있고, 형태 셰이더는 노이즈 변위·침식·안개 가장자리를 이미 씁니다(`unity/README.md`). 그래서 아래 대안은 새 패키지 없이 기존 구조(사전 → SceneSpec → 모형 선택)를 넓히는 방식으로 붙일 수 있습니다.

| 대안 | 무엇을 더 그릴 수 있나 | 사전 연결 | 못 하는 것 | 비용 |
| --- | --- | --- | --- | --- |
| **A. 절차적 형상 확장** — 스플라인 튜브(선·실·끈·엉킴·매듭), 노이즈 판(천·종이·막·얇은 판, 처짐은 정점 중력 변형), 메타볼/SDF 합(덩어리 여러 개·돌기·구멍), 길이 비율(길쭉·납작) | `docs/shape-mapping.md`「아직 모형이 없는 모양 값」 19개 중 thread·line·string·knot·thin·sheet·long·elongated·hole·hollow·bumpy·dot·thick·sharp·angular 등 대부분. 이번 실제 답변·연구자 예시 중 선·엉킴, 젖은 종이, 축 처짐 유형이 여기 해당 | 이미 1층 사전에 있는 모양 값에 모형만 붙이면 됨. 같은 spec → 같은 모형(원칙 1·2 유지) | 알아볼 수 있는 구체 사물(손, 아이, 병, 벽, 인형) | 모형 하나당 C# 수백 줄 + EditMode 테스트. 모형 매개변수(엉킴 정도 등)는 말한 값이 없으면 기본값 → `defaultsUsed` 기록 |
| **B. 입자·셰이더 효과** — 파티클(먼지·파편·빛 입자·연기·물방울), 발광(빛 덩어리), 젖음·광택, 볼륨 안개 | mist가 거의 안 보이는 문제(`unity/README.md` 한계)를 입자 안개로 대체 가능. 안개·빛 같은 분위기 심상(합성 예문 D09의 '주황색 빛 덩어리' 등) | form.type·material 슬롯의 새 표현으로 붙임 | 형상 그 자체(무엇인지)는 못 바꿈 | 입자는 VR 프레임 비용 확인 필요(Quest) |
| **C. 검수한 CC0 에셋 + 사전 선택** — 사람이 고르고 검수한 glTF 에셋(돌, 상자, 병, 공, 종이, 천, 손, 웅크린 사람 실루엣 …)을 명사 사전 → 에셋 ID로 고름. 로드는 이번에 넣은 glTFast 로더를 그대로 씀 | 지금 `_unmapped`에 category `object`(reason `no_scene_param`)로 남는 명사(구름·돌·막·상자 등, `docs/mapping-audit.md` 8절). 이번 노션 자료에 나온 손·웅크린 사람·벽 같은 구체 사물 | 명사 → 에셋 표(화이트박스). 같은 말 → 같은 에셋. 에셋이 가진 세부(손가락 모양 등)는 말하지 않은 세부이므로 "에셋 기본값"으로 기록해야 함 | 라이브러리에 없는 것. 추상 관계(자기와 바깥의 관계, 중심과 경계 등) | 에셋 수집·라이선스 확인·스타일 통일(검수) 시간. CC0 출처 후보(Poly Haven, Kenney, Quaternius 등)는 이번에 라이선스 원문을 열어 확인하지 않음 |
| D. 생성형(이번 구현) | 무엇이든 "무언가"는 나옴 | 프롬프트까지만 화이트박스 | 말하지 않은 세부를 반드시 지어냄, 결과 질이 들쭉날쭉(7절) | 문장당 3–8초, GPU PC 필요 |

**덮는 범위(실제 답변 20개를 유형으로 나눈 결과, 판정은 AI 에이전트).** 20개 중 7개는 규칙 추출기가 외형 슬롯을 하나도 못 채웠습니다(7절). 내용으로 보면(실제 응답 12 + 연구자 예시 8):

| 유형 | 개수 | 지금 규칙 기반 | A·B(절차·효과) | C(에셋) | 생성형 |
| --- | --- | --- | --- | --- | --- |
| 분위기·재질(선·엉킴, 안개, 젖은 종이, 축 처짐) | 8 | 안개만 mist로(거의 안 보임), 나머지 못 그림 | 대부분 덮음(튜브·노이즈 판·입자 안개) | 일부(종이·천 에셋) | "무언가"는 나오나 7절처럼 자주 어긋남 |
| 구체 덩어리·공·껍질 | 3 | 그림 | — | 더 나은 모형 | 그림(세부를 지어냄) |
| 색·무게 속성만 | 2 | 색은 그림, 무게는 못 그림 | — | — | 형상을 지어냄 |
| 이미지에 대한 평가·수정 요구(채도·따뜻함·색 계열) | 3 | 형상 대상이 아님(색 조정 입력으로 써야 함) | — | — | 해당 없음 |
| 추상 관계(자기와 바깥의 관계, 중심과 경계) | 2 | 못 그림 | 못 그림 | 못 그림 | 말하지 않은 형상을 지어낼 뿐 |
| 영어 답 | 2 | 한국어 분석기라 못 읽음 | — | — | LLM 번역 경로로만 |

A·B만으로 분위기·재질 8개 대부분을 덮을 수 있고, 이 8개는 지금 규칙 기반이 가장 못 그리는 유형입니다. 추상 관계는 어느 방법도 "말한 대로" 그리지 못합니다.

## 3. 고른 경로

```text
한국어 문장 ─► SceneSpecBuilderV1(기존, 무수정) ─► SceneSpec ─┬─► Unity BatchCapture(기존) ─► 규칙 경로 PNG
                                                             │
                     [rules] 말한 슬롯 → 영어 낱말 표 ──┐      │
  (비교) [llm] Ollama gemma4:e4b 번역 ─────────────────┴─► 영어 프롬프트
                                                             ├─ 경로 A: Shap-E(text→3D) ─────────────┐
                                                             └─ 경로 B: SDXL(text→image) → rembg → TripoSR(image→3D)
                                                                                                     ▼
                                     GLB(y-up, 정점 색, 금속도 0) + meta.json ─► Unity glTFast(Gen3DCapture) ─► 생성 경로 PNG
```

- **경로 A — Shap-E(MIT).** 추가 설치가 없고(diffusers에 있음) 텍스트를 바로 받습니다. 품질이 낮다는 것은 알고 고른 하한선입니다.
- **경로 B — SDXL base 1.0 → TripoSR(MIT).** 16 GB·Windows에서 C++/CUDA 확장 빌드 없이 돌릴 수 있는 image→3D 중 가장 단순했습니다(`torchmcubes`만 skimage로 대체). SF3D·TRELLIS·InstantMesh보다 품질은 낮다고 알려져 있지만, 이들은 약관 동의(SF3D)나 Linux 전용 의존성(TRELLIS·InstantMesh)이 걸립니다.
- **프롬프트는 rules를 기본으로**, llm은 비교용으로 같은 문장에 같이 돌렸습니다.

## 4. 설치와 실행

경로는 이 PC 기준입니다. 저장소 밖 폴더 세 개를 씁니다: `gen3d-venv/`(Python), `gen3d-models/`(외부 코드 클론), `gen3d-out/`(산출물). 가중치는 HF 캐시(`%USERPROFILE%\.cache\huggingface`)와 `%USERPROFILE%\.u2net`에 있습니다.

```bash
# 0) 환경: 시스템 Python 3.11.7(torch 2.11.0+cu128, diffusers 0.40.0.dev0, transformers 4.57.6)을 재사용하는 venv
cd "D:/Seoyeon/IFS -HCI Korea"
python -m venv --system-site-packages gen3d-venv
gen3d-venv/Scripts/python -m pip install "trimesh==4.*" pygltflib kiwipiepy==0.24.1 kiwipiepy_model==0.24.0 jsonschema
#    (rembg 2.0.57·onnxruntime 1.18.1·scikit-image 0.26.0·omegaconf·einops는 시스템에 이미 있음)

# 1) 외부 코드와 가중치(한 번만, 저장소 밖)
git clone --depth 1 https://github.com/VAST-AI-Research/TripoSR.git gen3d-models/TripoSR   # 107cefdc244c…
gen3d-venv/Scripts/python -c "from huggingface_hub import snapshot_download as s; [s(r) for r in ('openai/shap-e','stabilityai/TripoSR','facebook/dino-vitb16')]"
#    SDXL base 1.0은 이 PC 캐시에 이미 있었음. rembg의 u2net.onnx는 첫 실행 때 GitHub에서 받음.

# 2) 입력 → 저장소 밖 sentences.json + id↔원문 대응표
cd IFS-research
../gen3d-venv/Scripts/python tools/gen3d/inputs.py --dev 10 --run dev10                       # 합성 dev.json 앞 10개
../gen3d-venv/Scripts/python tools/gen3d/inputs.py --answers <answers.json> --max 20 --run notion20

# 3) 생성(문장마다 SceneSpec → 프롬프트 → GLB + meta). --repeat 2 = 결정성 확인
for p in shap-e sdxl-triposr; do for m in rules llm; do
  ../gen3d-venv/Scripts/python tools/gen3d/generate.py --run dev10 --pipeline $p --prompt-mode $m --repeat 2
done; done
#    llm 모드는 Ollama(127.0.0.1:11434)에 gemma4:e4b가 있어야 함

# 4) 규칙 경로 캡처(기존 BatchCapture, 코드 무수정): specs 폴더는 generate.py가 쓴 것과 같음
"C:/Program Files/Unity/Hub/Editor/6000.0.85f2/Editor/Unity.exe" -batchmode -projectPath unity \
  -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run -specDir <out>/dev10/rule_specs \
  -outDir <out>/dev10/rule_capture -frames 5 -warmup 1 -logFile <로그>

# 5) 생성 경로 캡처(새 Gen3DCapture): GLB 폴더 → 정면·사선 PNG + report.json
"C:/Program Files/Unity/Hub/Editor/6000.0.85f2/Editor/Unity.exe" -batchmode -projectPath unity \
  -executeMethod IFS.Gen3D.EditorTools.Gen3DCapture.Run -glbDir <out>/dev10/shap-e-rules/glb \
  -outDir <out>/dev10/shap-e-rules/capture [-size 1024 -objectSize 0.5] -logFile <로그>

# 6) 비교 시트·측정 요약
../gen3d-venv/Scripts/python tools/gen3d/compare_sheet.py --run dev10 --rows-per-sheet 5
../gen3d-venv/Scripts/python tools/gen3d/summarize.py --runs dev10,notion20
```

| 파일 | 역할 |
| --- | --- |
| `tools/gen3d/common.py` | 경로(저장소 밖 강제), sha256, HF 리비전·파일 해시, VRAM 최대치 |
| `tools/gen3d/inputs.py` | answers.json(실제 응답 우선) 또는 dev.json → sentences.json·대응표 |
| `tools/gen3d/prompts.py` | 기존 `SceneSpecBuilderV1` 호출(무수정), 규칙 프롬프트 표, Ollama 번역 |
| `tools/gen3d/generate.py` | Shap-E / SDXL + TripoSR, GLB(y-up, 정점 색, 금속도 0 머티리얼), meta·run.json |
| `tools/gen3d/compare_sheet.py` · `summarize.py` | 비교 시트(id만), 측정 요약 |
| `unity/Assets/IFS/Runtime/Experimental/Gen3D/Gen3DGlb.cs` | glTFast 로드(`Load(byte[])` → `InstantiateMainSceneAsync`), 통계, 크기 정규화 |
| `…/Gen3D/Gen3DGlbLoader.cs` | 씬 컴포넌트(경로 → 정규화된 물체). 실행 중에는 프레임 예산 방식 |
| `…/Gen3D/Editor/Gen3DCapture.cs` | 배치 캡처 진입점. 비동기 로드를 `EditorApplication.update`에서 기다린 뒤 `Exit` |
| `unity/Packages/manifest.json` | `com.unity.cloud.gltfast` 6.21.0 추가(burst·collections·mathematics가 따라 들어옴) |
| `unity/Tools/compile-check/IFS.SceneSpec.CompileCheck.csproj` | `Runtime/Experimental/**` 제외(glTFast 스텁이 없음) |

- **Built-in·ProjectSettings.** 에디터 캡처는 ProjectSettings를 바꾸지 않고 glTFast의 Built-in 셰이더(`glTF/PbrMetallicRoughness`)로 그려졌습니다. XR 패키지도 건드리지 않았습니다.
- **asmdef.** `IFS.Gen3D`(런타임, glTFast 참조)와 `IFS.Gen3D.Editor`(에디터 전용, `IFS.SceneSpec`의 `EnvironmentBuilder`를 씀)는 `autoReferenced: false`라 기존 어셈블리·테스트가 이 코드를 참조하지 않습니다.

## 5. 측정

RTX 5080 16 GB, Windows 11, Unity 6000.0.85f2(에디터 배치모드). 문장 30개(합성 10 + 노션 20) × 4조합, 조합마다 2번씩 만든 것 중 첫 번째 값입니다. `tools/gen3d/summarize.py` 결과(저장소 밖 `gen3d-out/compare/summary.json`)에서 옮겼습니다.

| | Shap-E | SDXL → TripoSR |
| --- | --- | --- |
| 문장당 생성 시간(중앙값 / 최대) | **2.9 / 3.4 s** | **7.6 / 8.4 s** (이미지 약 6.2 s + 배경 제거 0.15 s + 재구성 약 1.2 s + 내보내기) |
| 모델 적재(한 번) | 수 초(실행 전체 72 s = 20회 생성 + 적재) | SDXL·TripoSR 각각 수 초, 단계 사이에 SDXL을 내림 |
| 프롬프트(llm 모드만) | Ollama 호출당 약 7–10 s(`keep_alive 0`이라 매번 적재) | 같음 |
| VRAM 최대(torch reserved) | **2.5 GiB** | 이미지 **12.5 GiB**(allocated 9.7) · 재구성 **3.0 GiB** |
| GLB 크기(중앙값 / 최대) | 2.0–2.7 / 8.3 MiB | 2.4–2.9 / 11.7 MiB |
| 삼각형(중앙값, 범위) | 10.6만–14.4만 (2,112 – 434,040) | 12.7만–15.1만 (488 – 614,214) |
| Unity 로드(glTFast `Load` + `InstantiateMainSceneAsync`) | 세션 첫 파일 175–212 ms(준비 포함), 이후 중앙값 2–3 ms, 90백분위 약 55 ms, 최대 105 ms | 같음 |
| Unity 로드 성공 · 콘솔 오류 | 60/60 · 0 | 60/60 · 0 |
| 셰이더 | `glTF/PbrMetallicRoughness`(glTFast Built-in) | 같음 |

- 생성 시간에 Ollama 번역은 들어 있지 않습니다. Unity 로드 시간은 데스크톱 에디터 값이라 헤드셋에서는 더 깁니다.
- 삼각형 488(dev D10, llm)과 2,112(노션 답변 1건, llm)는 사실상 **생성 실패**(거의 빈 메시)입니다. 로드는 성공으로 셉니다.
- GLB 머티리얼: trimesh는 정점 색만 있는 메시를 머티리얼 없이 씁니다. glTF 기본 머티리얼은 금속도 1이라 Unity에서 거의 검게 보였습니다(첫 시험). 그래서 내보낼 때 금속도 0·거칠기 0.8·양면 머티리얼을 붙입니다(`exportMaterial`로 기록).

## 6. 결정성

| 확인 | 결과 |
| --- | --- |
| 같은 프로세스에서 같은 입력·seed 0으로 두 번 | GLB sha256 **120/120 같음**(30문장 × 4조합), SDXL 중간 이미지 **60/60 같음** |
| 다른 프로세스에서 다시(dev D01–D03, Shap-E·TripoSR 규칙 경로) | GLB·이미지 sha256 **6/6 같음** |
| 같은 문장, seed만 1·2로 | 다른 메시(Shap-E D01 삼각형 149,196 → 284,440 → 260,056) |
| 규칙 프롬프트 | 같은 spec → 같은 문자열(코드상 결정적), spec 파일도 실행마다 바이트까지 같음 |
| llm 프롬프트 | temperature 0·seed 0에서 같은 문장 30개 모두 두 번의 호출(Shap-E 실행, SDXL 실행)이 같은 문자열 |

`set_determinism`(cuDNN deterministic, TF32 끔, 모든 난수 seed)을 쓰고 생성기를 seed로 만듭니다. **같은 PC·같은 소프트웨어 판**에서만 확인했습니다. GPU·드라이버·torch 판이 바뀌면 같은 바이트가 나온다는 보장은 없습니다. 그리고 seed는 연구자가 정한 값일 뿐 참여자 말과 관계가 없어, seed를 바꾸면 같은 말에서 다른 형상이 나옵니다. **"결정적"이지만 "말한 것만 그린다"는 뜻은 아닙니다.**

## 7. 실제 답변으로 확인한 결과

**입력.** 합성 dev.json 앞 10개(D01–D10, held-out은 열지 않음)와, 노션에서 모은 답변 중 "실제 응답" 12개 + "연구자 예시" 8개. 노션 원문은 이 문서에 넣지 않았습니다. 비교 시트(문장 id만)와 판정표, id↔원문 대응표는 저장소 밖에 있습니다:

- 비교 시트: `D:\Seoyeon\IFS -HCI Korea\gen3d-out\compare\dev10_sheet_{1,2}.png`, `notion20_sheet_{1..4}.png` — 열: 규칙 경로(BatchCapture 상세 크롭) · Shap-E[rules] · SDXL 이미지[rules] · TripoSR[rules] · Shap-E[llm] · SDXL 이미지[llm] · TripoSR[llm](Unity 사선 보기)
- 판정표: `D:\Seoyeon\IFS -HCI Korea\gen3d-out\compare\judgments.md`
- 대응표: `D:\Seoyeon\IFS -HCI Korea\gen3d-out\<run>\inputs\id_text_table.md`

**판정 방법.** AI 에이전트가 시트를 보고 결과마다 하나를 붙였습니다(사람 판정 아님. 합성 10개는 문장 작성도 AI 에이전트). 맞음 = 말한 외형 대부분 반영, 큰 지어냄 없음. 부분 = 일부 반영. 어긋남 = 말한 것과 다름. 지어냄 = 문장에 외형 서술이 없는데 형상이 나옴(생성형은 이 경우에도 반드시 무언가를 만듦). 규칙 경로는 '기본값만'(읽은 슬롯 없음)과 '왜곡'을 따로 셌습니다.

| 열 | 맞음 | 부분 | 어긋남 | 지어냄 | 비고 |
| --- | --- | --- | --- | --- | --- |
| 규칙 경로(SceneSpec) | **8** | 13 | 0 | — | 기본값만 8, 왜곡 1 |
| Shap-E [rules] | 0 | 15 | 8 | 7 | |
| TripoSR [rules] | 0 | 10 | 13 | 7 | |
| Shap-E [llm] | 4 | 10 | 8 | 8 | |
| TripoSR [llm] | 0 | 11 | 11 | 8 | |

(30문장. 묶음별: 합성 10에서 규칙 경로 맞음 3·부분 7, Shap-E[llm] 맞음 3. 실제 응답 12에서 생성형 네 열 모두 맞음 0, 지어냄 6–7. 연구자 예시 8에서 규칙 경로 맞음 4.)

**문장과 맞은 생성 결과는 120개 중 4개(Shap-E[llm]: 노란 공, 나무 상자, 빨간 공, 파란 공)** 였고, 모두 "공·상자"처럼 프리팹으로도 그릴 수 있는 것이었습니다. 규칙 경로가 못 그리는 유형(엉킨 선, 선들, 안개, 젖은 종이, 축 처짐, 얇은 천, 유리 조각)에서 생성형이 "맞음"을 낸 경우는 없었습니다. 젖은 종이 → 구겨진 판(부분), 엉망인 원 → 원판(부분) 정도가 가장 가까웠습니다.

**대표 실패 유형.**

1. **비고체가 고체가 됨.** 안개·구름·빛·반투명·유리는 SDXL 이미지에서는 그럴듯해도(구름, 유리 조각, 비단 천) 3D로 바꾸면 회색 덩어리·납작한 판이 되거나 메시가 거의 비었습니다. Shap-E·TripoSR 메시는 정점 색만 있고 투명도·발광이 없습니다.
2. **TripoSR이 색을 바램.** 노랑 → 베이지, 주황 상자 → 흰 상자, 파랑 → 회청색. 30문장 대부분에서 채도가 크게 떨어졌습니다. 정점 색 품질 한계로 보입니다(원인은 따로 확인 안 함).
3. **말하지 않은 정체를 지어냄.** "회색 안개" → 검은 망토 인물(Shap-E), "껍질" → 조개껍데기, "파란 덩어리" → 파란 구슬 수십 개, LLM 번역이 "blue crystal"을 덧붙여 결정체. 규칙 프롬프트가 "a single object"뿐인 7문장은 7개가 모두 **같은 청록색 구멍 난 덩어리**(Shap-E)와 같은 회색 구(TripoSR)가 됐습니다 — 모델의 기본 형상입니다.
4. **정보를 잃는 번역.** 규칙 프롬프트는 추출기가 놓친 낱말(엉킨, 젖은 종이, 나무)을 못 넣습니다. LLM 번역은 반대로 안개를 '느낌'으로 말한 답 2건에서 안개를 버리고 "an object"로 옮기기도 했고(규칙 경로는 mist로 읽음), 결정체처럼 없는 것을 더하기도 했습니다.
5. **색 이름 표의 거칠기.** 규칙 프롬프트의 HSL → 영어 색 이름 표가 '연한 갈색'을 orange로 옮겼습니다(D03). 표를 고칠 수 있지만 고친 뒤 생성 모델이 그 색을 지키는지는 별개입니다(2번).
6. **규칙 경로 자체의 왜곡 1건.** 밝기를 부정하는 이미지 평가 답 1건에서 추출기가 밝음 값을 만들었습니다. 생성형은 이 왜곡까지 그대로 물려받습니다.

**요약하면** 생성형은 "무언가 다른 모양"을 늘 내놓지만, 이번 30문장에서 그 모양이 문장과 맞은 것은 규칙 경로가 이미 그리는 단순 형상뿐이었습니다. 자유 심상을 덮는다는 목적에는 지금 모델(Shap-E·TripoSR)로는 미치지 못했습니다.

## 8. 원칙과의 관계

| 원칙 | 이 경로에서 | 어떻게 다뤘나 |
| --- | --- | --- |
| 1. LLM은 유도 단계에만, 장면 속성은 사전·규칙만, 같은 텍스트 → 같은 추출 | **위반.** 형상·색·재질을 생성 모델(확산 모델)이 정합니다. `--prompt-mode llm`은 번역에도 LLM을 씁니다 | 실험 경로로 격리(별도 폴더·asmdef). 기본 프롬프트는 규칙(`rules`)이라 프롬프트까지는 결정적. seed 고정으로 **같은 입력 → 같은 GLB 바이트**는 확인(6절). 결정적이라고 화이트박스가 되지는 않음 — 왜 그 모양인지 설명할 수 없음 |
| 2. 말하지 않은 것을 추론하지 않음, 기본값과 미지정을 섞지 않음 | **위반.** 생성 모델은 빈칸을 반드시 채웁니다. 규칙 프롬프트가 "a single object"뿐이어도 특정 형상·색이 나옵니다(7절). 프롬프트 꼬리말(흰 배경·스튜디오 조명)과 GLB 머티리얼(금속도 0·거칠기 0.8)도 시스템이 정한 값입니다 | meta에 프롬프트에 쓴 슬롯(`usedSlots`)·시스템 꼬리말·`exportMaterial`을 따로 남김. 생성 결과의 어떤 세부가 지어낸 것인지 슬롯 단위로 표시할 방법은 없음(메시 전체가 모델 출력) |
| 5. 로컬 실행, digest 기록 | 지킴. 가중치는 HF·GitHub에서 한 번 내려받아 로컬에서만 추론. 상용 API·외부 추론 없음 | 모델마다 저장소 ID + 리비전(커밋 해시) + 파일 sha256을 `run.json`·`meta/*.json`에 기록. Ollama 모델은 digest로 기록 |
| 6. 참여자 데이터는 git 밖 | 지킴 | 입력 문장·대응표·GLB·PNG·meta는 모두 저장소 밖 `gen3d-out/`. `common.assert_outside_repo`가 저장소 안 출력을 막음. 이 문서에는 합성 예문(dev.json)만 인용 |

**결론적으로**, 생성형은 지금 연구 설계("말한 것만 그리고, 그린 것의 근거를 슬롯별로 남긴다")의 측정 논리와 맞지 않습니다. 쓰려면 원칙 1·2의 예외를 팀이 명시적으로 정해야 합니다(11절).

## 9. Quest 3 단독 실행

- **생성은 헤드셋에서 못 합니다.** Shap-E는 VRAM 약 2.5 GB, SDXL + TripoSR은 약 7–8 GB(5절)이고 CUDA가 필요합니다. Quest 3(모바일 GPU)에서는 돌지 않습니다.
- **구조: PC에서 생성 → GLB 파일만 헤드셋으로.** 면담이 끝나면 PC가 GLB를 만들고(문장당 3–8초, 모델 적재 시간 별도), 헤드셋 앱은 `Gen3DGlbLoader`로 GLB를 읽습니다. 전달은 SceneSpec과 같은 두 방법: adb push로 `Application.persistentDataPath` 아래에 두기, 또는 로컬 HTTP(`adb reverse`)로 받기(`unity/README.md`「Quest에서 주의」). 외부 서버는 쓰지 않습니다.
- **헤드셋 쪽에서 확인 안 한 것.** (1) glTFast의 Android 동작(문서에 언급 없음), (2) Built-in 빌드에 glTFast 셰이더 포함(Always Included Shaders 또는 변형 모음 — ProjectSettings 변경이 필요해 이번에 안 함), (3) 메시 크기: 생성 메시는 삼각형 6만–43만 개(5절)라 SceneSpec 형상(눈당 약 2만)보다 크고, 지금 AC-4 기준(눈당 30만)을 한 물체가 넘을 수 있습니다. 헤드셋용이면 PC에서 메시 단순화(decimation)를 거쳐 보내야 합니다(이번에 안 함). (4) 로드 시간은 데스크톱 에디터 측정값이라 헤드셋 CPU에서는 더 깁니다.

## 10. 실패한 시도와 하지 않은 것

| 무엇 | 결과 |
| --- | --- |
| 첫 GLB(머티리얼 없음) | Unity에서 거의 검게 나옴 → glTF 기본 금속도 1 때문. 금속도 0 머티리얼을 붙여 해결(5절) |
| TripoSR의 `torchmcubes` | 설치하지 않음(CUDA 확장 빌드). 같은 계약의 skimage 마칭 큐브 함수로 대신해 문제없이 돎(`generate.py` `_install_torchmcubes_shim`) |
| 비고체(안개·유리·천)의 3D 재구성 | 반복 실패(7절 1번). 모델 한계라 재시도하지 않음 |
| SF3D·TRELLIS·InstantMesh·TripoSG·FLUX.1-schnell | 시도 안 함(2.2절 이유). 시간이 더 있으면 다음 후보는 TripoSG(MIT, 8 GB, 형상만) + 색 별도, 또는 FLUX.1-schnell(Apache-2.0) 이미지 |
| 헤드셋 빌드, 메시 단순화, glTFast 셰이더 포함 설정 | 안 함(9절) |
| 규칙 프롬프트 색 이름 표 수정 | 안 함(실행 중 같은 표로 비교하려고). 7절 5번 |

## 11. 권고와 사람이 정할 것

| 선택지 | 쓸 조건 | 이번 결과로 본 판단 |
| --- | --- | --- |
| **규칙 기반 유지**(지금) | 측정 논리("말한 것만, 근거 슬롯별로")를 지켜야 하는 본 실험 | 단순 형상에서는 생성형보다 낫습니다(맞음 8 대 최대 4) |
| **절차적 확장(A·B)** — 추천 1순위 | 규칙 기반이 못 그리는 분위기·재질(선·엉킴·천·종이·안개·빛)을 원칙 1·2 안에서 늘리고 싶을 때 | 이번 실제 응답에서 가장 많이 놓친 유형(8/20)이 여기 해당. 이미 사전에 있는 모양 값(thread·sheet·thin·line·knot…)에 모형만 붙이면 됨 |
| **검수 에셋 선택(C)** | 구체 사물(손·사람 실루엣·벽·병)이 자주 나올 때. 에셋 라이선스·스타일 검수 인력이 있을 때 | 로더(glTFast)는 이번에 준비됨. 에셋이 가진 세부는 "에셋 기본값"으로 기록해야 함 |
| **생성형** | (a) 본 실험이 아닌 탐색·예비 면담의 보조 자극, (b) 연구자가 미리 생성·검수해 에셋 라이브러리(C)를 채우는 도구, (c) 원칙 1·2 예외를 팀이 명시하고 "생성 조건"을 별도 조건으로 비교하는 연구 | 실시간 참여자용으로는 이번 모델로 부적합(맞음 4/120, 지어냄 7–8/30). 쓰려면 더 나은 image→3D(SF3D·TRELLIS 등)와 투명·발광 처리가 먼저 |

**사람이 정할 것.**

1. 생성형을 연구에 쓸지, 쓴다면 위 (a)–(c) 중 어떤 용도인지. (c)라면 원칙 1·2의 예외 범위를 `docs/decisions.md`에 적어야 합니다(AGENTS.md는 이번에 고치지 않음).
2. 절차적 확장(A·B)을 다음 구현으로 할지, 한다면 어떤 모양 값부터(이번 실제 응답 기준 선·엉킴, 종이·천, 안개 입자).
3. glTFast 패키지를 그대로 둘지. 헤드셋 빌드에 쓰려면 ProjectSettings(Always Included Shaders 또는 Preloaded Shaders)를 바꿔야 합니다. 쓰지 않는다면 `manifest.json`에서 빼고 `Runtime/Experimental/`을 지우면 됩니다.
4. SF3D를 쓰려면 HF에서 Stability Community License 약관 동의(계정 소유자)가 필요합니다.
5. 판정은 AI 에이전트 한 명이 했습니다. 연구 근거로 쓰려면 사람 2명 이상의 독립 판정이 필요합니다.

## 2026-11-27 추가: G62 형태 후보 생성기

결정 G62(형태 메시 후보를 로컬 생성 모델로 만든다)의 **생성기 쪽**입니다. 설계 바탕은 `docs/codex-reviews/D8_claude.md`. 위 1–11절의 실험 경로와 달리 **형태만** 만들고(색·재질은 매핑이 정함), 프롬프트는 규칙만 씁니다(LLM 없음). 생성 결과는 SceneSpec 슬롯 값이 아니라 '생성' 출처의 후보입니다.

### 무엇을 만들었나

```text
확정 텍스트 ─► shape_prompt()(Kiwi + 고정 사전, 차단 판정) ─┬─ 차단: 사이드카만(모델 호출 없음)
                                                         └─ ok: SDXL base 1.0 → rembg(u2net) → TripoSG(형태만)
                                                                 → 후처리(면 ≤ 2만 → 중심 → 가장 긴 변 1.0 → 바닥 y=0)
                                                                 → GLB(회색 단일 머티리얼) → 6시점 렌더 → CLIP 관문
                                                                 → <assetId>.glb + <id>.form-asset.json
```

| 파일 | 내용 |
| --- | --- |
| `shared/schemas/form-asset.v0.json` | 사이드카 계약(`schema`·`assetId`·`status`·`blockReason`·`glb`·`glbSha256`·`pipeline`·`models[]`·`seed`·`prompt{text, lexiconVersion, tokens[{en, ko, charSpan, slot}]}`·`sourceTextSha256`·`normalization`·`covariates`·`gate`). `sourceTextSha256`는 `normalize_confirmed(text)`의 sha256이라 SceneSpec `meta.sourceTextHash`(접두어 `sha256:` 뺀 값)와 같음(확인함) |
| `shared/lexicon/shape_prompt_en.v0.json` | 한→영 고정 사전 0.1.0: 형태 명사 90·형태 꾸밈말 49(명사 꼴 '구멍' 포함), 틀 문구, 자리 규칙(장소·크기 비교·비유·부정), 보충 차단 목록(메시 불가·사람/얼굴·동물). dev.json과 일반 어휘로만 만듦 |
| `tools/gen3d/prompts.py` `shape_prompt()` | 사전 맞춤(명사 연속 전체), 회상 문장 제외(기존 `_context_sentences`), 부정 제외(기존 `_negated` + 아니·않·없·못), 크기 비교·장소 제외, 차단 판정, charSpan 감사(fail closed) |
| `tools/gen3d/form_asset.py` | 모델 단계·결정적 후처리·캐시·렌더러·CLIP 관문·사이드카 쓰기(jsonschema 검증) |
| `tools/gen3d/generate.py` | `--pipeline sdxl-triposg`, `--no-cache` 추가(기존 shap-e·sdxl-triposr 경로는 그대로) |
| `tools/gen3d/eval_g62.py` | 합성 60문장 입력·수치·비교 시트 |
| `tools/gen3d/tests/test_g62.py` | 모델 없는 단위 테스트 30개(프롬프트·차단·후처리 결정성·스키마) |

**차단 규칙(모델을 부르지 않음).** ① 기존 제외 판정을 코드 수정 없이 호출(`SceneSpecBuilderV2`, G45–G51: `_unmapped` reason excluded_shape·no_asset 중 `formSaid` 또는 `formBlock`), ② 기존 빌더가 `form.type = mist`·`form.base = flame`으로 읽음, ③ 보충 목록: 안개·연기·구름·빛·불꽃 등은 명사 꾸밈('빛 덩어리')·비유 원천이면 막고, 주어 자리면 텍스트에 형태 명사가 따로 없을 때만 막음(배경 햇빛·'빛이 나요'는 통과). 얼굴·인형·동물 보충 낱말은 G45처럼 중심 명사일 때만. → `excluded_category`. 형태 낱말이 없으면 `no_shape_stated`, 근거 없는 내용 토큰이면 `untraceable_token`. 얇은 것(선·종이·천·잎·깃털 등)은 생성하되 `thinRisk: true`.

**틀 문구**(slot `template`, 분석에서 뺌): `a single {꾸밈말} {…-like} {명사|object}, one solid object, matte gray clay, plain white background`. 부정 틀(안전 제약): `person, human, face, eyes, figure, animal, hands, …`.

**결정적 후처리**(`g62-post/0.1.0`): 정점 병합 → 면 > 20,000이면 pymeshlab quadric 축소 → (닫힌 메시면) 감기 방향만 맞춤 → 경계 상자 x·z 중심과 바닥을 원점 → 가장 긴 변 1.0. **주축 정렬은 하지 않음**(고유벡터 부호·순서가 결정적이라는 보장이 없음). 모델의 y-up 그대로.

**캐시**: 키 = sha256(프롬프트 텍스트 + 파이프라인 + 네 모델의 repo@리비전 + seed + 후처리 판), `assetId` = 앞 16자. 저장소 밖 `gen3d-out/form-assets/sdxl-triposg/`(GLB·`.gen.json`·중간 이미지·렌더). 같은 키면 다시 만들지 않음. 실행 폴더 `gen3d-out/<run>/g62-sdxl-triposg/assets/`에 `<assetId>.glb`와 문장마다 `<id>.form-asset.json`. 관문 차단 GLB는 실행 폴더로 복사하지 않음.

**출력 관문**: 자체 점 찍기 렌더러(표면 점 20만 개, seed 0 표본, 정사영 z-버퍼, 6시점) → CLIP ViT-L/14 영점 분류. 라벨 14개(사람 쪽 7: person·human figure·human face·head with eyes and a mouth·animal·animal figurine·doll / 물체 쪽 7), 사람 쪽 확률 합의 시점 최댓값 = `personLikeScore`, **문턱 0.5(평가 전에 정함, 고치지 않음)**. `matchScore` = 'a single …' 문구 대 렌더 CLIP 코사인(6시점 평균).

### 설치(저장소 밖, 한 번만)

```bash
cd "D:/Seoyeon/IFS -HCI Korea"
git clone https://github.com/VAST-AI-Research/TripoSG.git gen3d-models/TripoSG        # fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c
gen3d-venv/Scripts/python -m pip install jaxtyping typeguard pymeshlab               # 0.3.11 · 4.6.1 · 2025.7.post1
gen3d-venv/Scripts/python -c "from huggingface_hub import snapshot_download as s; \
  s('VAST-AI/TripoSG', revision='2c1c516d22d58db486a058d98d31bb6177344e06'); \
  s('openai/clip-vit-large-patch14', revision='32bd64288804d66eefd0ccbe215aa642df71cc41', allow_patterns=['*.json','*.txt','model.safetensors'])"
```

- **diso는 설치하지 않음**: PyPI에 소스(sdist, CUDA 확장 빌드)만 있음. TripoSG의 flash 디코더만 쓰므로 빈 모듈로 막고 `use_flash_decoder=False`(계층 옥트리 + skimage 마칭 큐브)로 돌림. 그 밖에 Windows에서 막힌 곳 없음(설치·첫 GLB까지 약 30분).
- **briaai/RMBG-1.4는 받지 않음**(라이선스 조건, D8 3절). 이미 쓰던 rembg u2net으로 RGBA를 만들어 넘기면 TripoSG `prepare_image`가 RMBG 경로를 건너뜀.
- 게이트(약관 동의) 모델 없음. 상용 API·외부 추론 없음.

| 역할 | 저장소 | 리비전 | 가중치 sha256(앞 12자) | 라이선스 |
| --- | --- | --- | --- | --- |
| 이미지 | stabilityai/stable-diffusion-xl-base-1.0 | 462165984030… | unet 357650fbfb3c · vae 1598f3d24932 · te 5c3d6454dd2d · te2 3a6032f63d37 | CreativeML Open RAIL++-M |
| 배경 제거 | rembg u2net.onnx | — | 8d10d2f3bb75 | MIT / Apache-2.0 |
| 형태 | VAST-AI/TripoSG | 2c1c516d22d5… (코드 fc5c40990181) | transformer 9192b5923f7b · vae a2e667c24927 · dinov2 399fba97a95f | MIT |
| 관문 | openai/clip-vit-large-patch14 | 32bd64288804… | a2bf730a0c7d | MIT |

설정: SDXL 30단계·cfg 7·1024², TripoSG 50단계·cfg 7·dense/hierarchical 옥트리 8·fp16, seed 0. 환경: Python 3.11.7, torch 2.11.0+cu128, diffusers 0.40.0.dev0, transformers 4.57.6, trimesh 4.12.2, kiwipiepy 0.24.1, 드라이버 610.88, RTX 5080 16 GB.

### 실행

```bash
cd IFS-research
../gen3d-venv/Scripts/python tools/gen3d/eval_g62.py prepare --run g62eval
../gen3d-venv/Scripts/python tools/gen3d/generate.py --run g62eval --pipeline sdxl-triposg --repeat 2
../gen3d-venv/Scripts/python tools/gen3d/eval_g62.py prepare --run g62eval_rerun
../gen3d-venv/Scripts/python tools/gen3d/generate.py --run g62eval_rerun --pipeline sdxl-triposg --no-cache   # 다른 프로세스
../gen3d-venv/Scripts/python tools/gen3d/eval_g62.py report --run g62eval --rerun g62eval_rerun
../gen3d-venv/Scripts/python -m pytest tools/gen3d/tests -q
```

### 합성 60문장 평가(2026-11-27)

**입력.** dev.json 30 + heldout.json 30 + chatbot 테스트의 합성 예문 8. 라벨은 사전·규칙을 얼린 뒤(사전 sha256 `695390a9…`) AI 에이전트가 기준(`eval_g62.py` `LABEL_RULE`)대로 붙였습니다. **should_block 20** = 메시 불가 범주가 주된 것인 말뭉치 12(D02·D06·D09·D14·D20·D21·H02·H07·H09·H18·H24·H28) + 제외 범주 6(사람·고양이·뱀·귀신·칼·올가미) + 형태 서술 없음 2. **shape 40** = 나머지 말뭉치에서 id 순 40(dev 24 + H01–H20 중 16). held-out으로 규칙을 고치지 않았습니다.

| 항목 | 결과 |
| --- | --- |
| (a) 차단 대상 20개의 모델 호출 | **0** (20/20 규칙 단계에서 차단: excluded_category 17, no_shape_stated 3) |
| (b) 형태 40개 중 GLB 저장 | **34/40**. 규칙 단계 오차단 2(D19 '솜사탕' — 기존 빌더가 mist로 읽음, H19 '크리스탈' — 사전에 없는 명사 + '빛이 퍼져 나와요' 주어), 관문 차단 4, 생성 실패 0 |
| (c) GLB sha256 일치 | 같은 프로세스 **34/34**, 다른 프로세스(`--no-cache` 재실행) **34/34** (38개 프롬프트 → 고유 키 34; '공' 문장 3개 등 같은 문구는 키 하나) |
| (d) 후보당 시간(모델 적재 제외) | 중앙값 **29.8 s**, 범위 25.2–39.9 s = 이미지 6.4 + 배경 제거 0.3 + TripoSG 17.7(확산 약 9 + 표면 추출 약 9) + 후처리 0.4–13.8(면 수 축소, 원본 5만–89만 면) + 관문 0.3. **30 s 기준을 넘는 것이 절반 가까이** |
| (d) VRAM 최대(torch reserved) | 이미지 **12.5 GiB**, TripoSG **5.8 GiB**(단계를 나눠 동시에 올리지 않음) |
| (e) 관문 차단(person_like) | **4**: D23(꽃), D29(깃털), H01(구슬), H06(실). 모두 사람·동물 명사 없는 문장. 차단 점수 0.61–0.66, 통과 중 최고 0.43(D25 나뭇잎). 오탐인지는 사람이 시트로 볼 것 |
| (f) 일치 점수(CLIP 코사인) | TripoSG 38개 중앙값 **0.244**(0.187–0.305). 같은 7문장(D01·D03·D04·D05·D07·D08·D10, 같은 문구·같은 렌더러): TripoSG 0.235 · Shap-E(11-22) 0.227 · TripoSR(11-22) 0.210(중앙값). 차이가 작고 자동 지표일 뿐이라 질 판단 근거로 쓰지 않음 |
| 공변량 | thinRisk 11/40, familiarObjectStated 26/40 |
| 스키마 | 사이드카 60개 모두 `form-asset.v0` 검증 통과 |

- 비교 시트(문장 id·프롬프트 문구·상태 | SDXL 이미지 | TripoSG 렌더 3시점 | D01–D10만 11-22 Shap-E·TripoSR): `D:\Seoyeon\IFS -HCI Korea\gen3d-out\g62eval\compare\g62_sheet_{1..4}.png`. **사람 판정은 하지 않았습니다**(연구팀 몫).
- 수치 원본: `gen3d-out\g62eval\g62_report.json`, `g62-sdxl-triposg\run.json`(모델 호출 수·결정성·스키마 문제), 사이드카 `assets\*.form-asset.json`.

### 실패·한계

1. **오차단 2건(b)**: 기존 빌더의 mist 판정을 그대로 따르므로 '몽실몽실한 솜사탕'도 막힘. 사전에 없는 명사(크리스탈)를 말하고 빛을 주어로 말하면 형태 명사가 없다고 보고 막음. 막는 쪽 오차라 안전하지만 생성 후보가 없어짐.
2. **관문 오탐 의심 4건(e)**: 얇거나 작은 사물(꽃·깃털·구슬·실)이 'animal figurine'·'doll' 라벨로 넘어감. 문턱·라벨은 평가 전에 정한 값이라 고치지 않았음. 바꾸려면 dev 렌더로만 다시 정하고 기록할 것.
3. **시간(d)**: 30 s 기준을 자주 넘음. 주된 원인은 dense 옥트리 질의(256³)와 큰 메시의 quadric 축소. flash 디코더(diso 빌드)나 옥트리 깊이 7, 추출 단계 축소 순서 변경이 후보이나 시도하지 않음.
4. **얇은 것**: SDF 계열이라 천·종이·잎은 두께 있는 판이 됨(thinRisk로만 표시).
5. **SDXL 이미지가 프롬프트에 없는 것을 더함**: 'a single ball' → 구멍 난 공(D05), 'a single bottle' → 병 두 개(D12), 'a single square box' → 열린 틀(D03). 틀 문구 'one solid object'로 막지 못함 — 원칙 2의 '생성' 출처 표시 근거.
6. **sdxl-triposr 대체 경로**는 TripoSG가 돌아서 이 계약으로 감싸지 않음(스키마 enum에만 남김).
7. 결정성은 이 PC·이 소프트웨어 판에서만 확인(6절과 같은 한계).

### 조정 0.2.0: 지어냄 줄이기(같은 60문장의 1차 비교 시트를 본 뒤)

**위 수치는 모두 조정 전(사전 0.1.0·틀 0.1.0·관문 0.1)입니다.** 1차 비교 시트에서 TripoSG는 SDXL 이미지를 충실히 옮기지만 SDXL이 말하지 않은 것을 더하는 것이 보였습니다(병 2개 D12, 구슬 2개 D16, 고리 2개 D24, 풍선의 줄과 추 D17, 꽃병 D23, 구멍 난 공 D05·D26). 그래서 아래를 바꿨습니다. **같은 문장을 보고 조정했으므로, 이 문장들로 다시 잰 수치는 조정 뒤 수치이며 독립 검증이 아닙니다.**

| 바꾼 것 | 내용 |
| --- | --- |
| 출력 관문 `g62-gate/0.2.0` — 여러 물체 검사 | 후처리 뒤 메시의 연결 성분(면 인접) 중 표면적 비율 **5% 이상**인 것이 2개 이상이면 `status blocked`, `blockReason gate_failed`, `blockDetail multi_object`(사이드카 `gate.multiObject`에 성분 수·상위 비율). 문턱 5%는 2차 실행 전에 정했고 결과를 보고 고치지 않는다. 복수 명사(사전 `plural`: 조각·파편·알갱이, 또는 형태 명사 + '-들')를 말했으면 적용하지 않음(`covariates.pluralStated`) |
| 틀 `g62-template/0.2.0`·사전 0.2.0 | 일반 부속물 부정 틀 `negativeAccessories`: two objects, pair, duplicate, group of objects, stand, pedestal, base plate, plinth, string, rope, chain, strap, holder, container, bowl, vase, tray, plate. 프롬프트 내용 토큰의 영어 낱말과 겹치는 항목은 뺌(말한 끈·그릇·접시를 부정하지 않음). 개별 문장에 맞춘 항목 없음. 형태 낱말 항목·차단 목록은 그대로 |
| 캐시 키 | 부정 틀 문자열과 관문 판을 키에 넣음 → 0.1.0 결과와 키가 모두 달라져 다시 만듦 |
| 그대로 둔 것 | 사람·동물 관문의 문턱 0.5·라벨(오탐 의심 4건 — 꽃·깃털·구슬·실 — 그대로), 후처리 `g62-post/0.1.0` |

**2차 실행 상태(2026-11-27): 끝내지 못함.** 같은 60문장을 새 실행 이름 `g62eval_v2`(`--repeat 2`)로 돌리던 중, 이미지 단계(34개)를 마치고 TripoSG를 올리는 사이에 시스템 메모리 부족으로 작업 관리자(Claude Code)가 프로세스를 멈췄습니다. GLB·사이드카·수치는 나오지 않았고, 조정 뒤 수치는 아직 없습니다. 다시 돌리는 명령:

```bash
../gen3d-venv/Scripts/python tools/gen3d/eval_g62.py prepare --run g62eval_v2
../gen3d-venv/Scripts/python tools/gen3d/generate.py --run g62eval_v2 --pipeline sdxl-triposg --repeat 2
../gen3d-venv/Scripts/python tools/gen3d/eval_g62.py prepare --run g62eval_v2_rerun
../gen3d-venv/Scripts/python tools/gen3d/generate.py --run g62eval_v2_rerun --pipeline sdxl-triposg --no-cache
../gen3d-venv/Scripts/python tools/gen3d/eval_g62.py report --run g62eval_v2 --rerun g62eval_v2_rerun --prev g62eval
```

(`report --prev`가 1차 수치를 `g62_report.json`의 `previous`에 나란히 넣고, 새 비교 시트를 `gen3d-out\g62eval_v2\compare\`에 만듭니다. 이미 만든 SDXL 이미지는 캐시 폴더에 남아 있으나 생성기는 키마다 이미지부터 다시 만듭니다.)
