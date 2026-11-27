# Local open-weight text/image-to-3D for shape-only abstract objects (RTX 5080 16 GB, Windows 11, cu128) — status as of 2026-11-26

Scope note: this covers only what is new or changed relative to the 2026-11-22 local run (Shap-E, SDXL→TripoSR; 4/120 sentence matches; mist, line, paper and cloth failed). Labels used below: **[authors]** = claim by the model authors; **[3rd-party]** = community or independent report; **[unverified]** = could not confirm from a primary source. "Allowed in KR" means the licence text I read contains no clause excluding South Korea or academic research use. It is not legal advice.

## Q1. Candidate models: licence, VRAM, speed, Windows/Blackwell blockers, output, determinism, weight hosting

### Takeaway
On licence and install grounds, **TripoSG (MIT, ≥8 GB, GLB, geometry only)** is the easiest new image→shape model to try on this PC. **TRELLIS.2 and its MIT derivative Pixal3D** are the only open models that explicitly claim **open surfaces** (cloth, leaves), which is the failure class we saw. Upstream says they need 24 GB and Linux, but there are 3rd-party RTX 5080 Windows reports at about 8–14 GB. **Roblox Cube 3D v0.5** is the one current *native text→shape* open model that outputs geometry only and takes a bounding-box condition. Its "openrail" licence terms need reading. **Every Tencent Hunyuan3D open release checked (2.0, 2mini, 2.1, and Omni via the same licence family) excludes South Korea**, so all are out.

### Proposed ranked shortlist (my synthesis of the evidence below)
1. **TripoSG** (MIT): low VRAM, simple install, geometry-only GLB. It is SDF-based, so sheets come out as closed or thickened shells.
2. **TRELLIS.2-4B / Pixal3D** (MIT): the only open-surface claim. Windows on Blackwell needs community wheels and patches, and depends on gated DINOv3 and RMBG-2.0.
3. **Cube 3D v0.5** (openrail, terms to verify): native text→shape with bbox conditioning, deterministic when `top_p` is unset, 16 GB without fast inference.
4. **TRELLIS (v1)** (MIT): includes *text-conditioned* models (342M–2.0B) and Gaussian/radiance-field outputs. Needs 16 GB and spconv/xformers/flash-attn.
5. **Direct3D-S2** (MIT): 10 GB at 512³ (authors don't recommend 512), 24 GB at 1024³. Its TorchSparse dependency is a Windows pain point.
6. **Step1X-3D geometry stage** (Apache-2.0): 27 GB with texture per authors. Geometry-only VRAM is not stated.
7. **SF3D / SPAR3D** (Stability AI Community License, gated): very fast. Low-poly textured output.
8. Others (CraftsMan3D, Hi3DGen/Stable3DGen, PartCrafter, PartPacker, InstantMesh, SAM 3D Objects): see the table. Each has licence or install caveats, or a less suitable output type.

### Cited Findings

**TripoSG (VAST-AI)**
- Licence MIT. 1.5B rectified-flow model and VAE released March 2025. TripoSG-scribble (scribble + text prompt, "CFG-distilled, 512 token model") released April 2025. No newer version is listed — [GitHub VAST-AI-Research/TripoSG](https://github.com/VAST-AI-Research/TripoSG)
- Requirement: "CUDA-enabled GPU with at least 8GB VRAM" [authors]. Output `.glb` with an optional `--faces` cap. No texture. Weights at HF `VAST-AI/TripoSG` and `VAST-AI/TripoSG-scribble`, plus `briaai/RMBG-1.4` for background removal. The README gives no OS statement and no timing — [GitHub](https://github.com/VAST-AI-Research/TripoSG)
- The README does not mention `diso` or `flash-attn`. `torch-cluster` is needed only for the full VAE encoder — [GitHub](https://github.com/VAST-AI-Research/TripoSG)

**TRELLIS.2 (Microsoft)**
- MIT ("model and code"). nvdiffrast and nvdiffrec have their own terms. 4B parameters. arXiv 2512.14692. Initial repo release 2025-12-16 — [GitHub microsoft/TRELLIS.2](https://github.com/microsoft/TRELLIS.2); date from [cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)
- "An NVIDIA GPU with at least 24GB of memory is necessary" [authors]. "Tested only on Linux". Default env is PyTorch 2.6.0 + CUDA 12.4 with flash-attn (xformers as an alternative). Native extensions: nvdiffrast, nvdiffrec, cumesh, o-voxel, flexgemm — [GitHub](https://github.com/microsoft/TRELLIS.2)
- Times on H100 [authors]: ~3 s at 512³, ~17 s at 1024³, ~60 s at 1536³. Output is GLB plus MP4 preview. Handles "Open Surfaces (e.g., clothing, leaves)", non-manifold geometry and internal structures. Image-to-3D only. Weights at `microsoft/TRELLIS.2-4B` — [GitHub](https://github.com/microsoft/TRELLIS.2)
- Windows, from issue #4 [3rd-party]:
  - SoftologyPro's install.bat uses `torch==2.7.0+cu128`, `triton-windows==3.5.0.post21`, a prebuilt flash_attn 2.7.4.post1 cp310 wheel, and prebuilt cp310 wheels for nvdiffrast, nvdiffrec, cumesh, FlexGEMM and o-voxel from "Deathdadev's TRELLIS.2-Windows test-wheels". All wheels are **Python 3.10**, which does not match this PC's 3.11.
  - DINOv3 and RMBG-2.0 are gated on HF.
  - mr-lab built for RTX 5090 (sm_120) with `TORCH_CUDA_ARCH_LIST=9.0+PTX` after "5 hours" of MSVC patching.
  - Source: [TRELLIS.2 issue #4](https://github.com/microsoft/TRELLIS.2/issues/4)
- Self-reported figures from scjww in the same thread [3rd-party, method not stated]: RTX 5080 marked "TESTED" at 1024–1536 resolution, ~30–40 s, ~8–12 GB. Peak VRAM 14.2→12.8 GB with an "optimized" app on a 5090. Tested env "PyTorch 2.9.1, CUDA 13.1" — [issue #4](https://github.com/microsoft/TRELLIS.2/issues/4)
- Determinism and stability concerns [3rd-party]: memory "can even depend on the seed". OOM appears with randomized seeds. Unresolved "decoding issues causing artifacts". Some meshes have "small holes". One user left for Hunyuan because "The meshes prodcued here are a mess" — [issue #4](https://github.com/microsoft/TRELLIS.2/issues/4)
- ComfyUI guides [3rd-party, of uneven quality]: 16 GB minimum with 24 GB recommended, *or* 8 GB at 512³ in low-VRAM mode. On Windows the fix is to swap triton for windows-triton. The visualbruno ComfyUI-Trellis2 node is recommended for RTX 50 cards — [trellis2.app low-VRAM guide](https://trellis2.app/blog/trellis-2-low-vram), [trify3d RTX50 guide](https://trify3d.com/blog/install-trellis-2-comfyui-windows-rtx50/)

**Pixal3D (TencentARC, 2026)**
- Released May 2026. Multiview inference added September 2026 — [cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)
- The HF README says "released under the MIT License", with third-party components under their own terms (NOTICE). The `main` branch uses the TRELLIS.2 backbone and the `paper` branch uses Direct3D-S2. It needs `natten==0.21.0` built for the local arch. flash_attn is optional (`ATTN_BACKEND=sdpa`). `--low_vram` loads models on demand, with default resolution 1024 (1536 in standard mode). Output is GLB. HF metadata has `extra_gated_eu_disallowed: true` (EU only, not Korea) — [HF TencentARC/Pixal3D README](https://huggingface.co/TencentARC/Pixal3D/blob/main/README.md)
- Licence history conflicts: earlier versions used a custom "pixal3d-license" with academic or non-commercial terms, and MIT came later — [search summary incl. startupfortune Jul 2026](https://startupfortune.com/pixal3d-goes-mit-open-source-for-3d-asset-creation/). **Pin the HF revision whose LICENSE is MIT.**
- VRAM of ~12 GB in low-VRAM mode at 1024 is only from a 3rd-party blog **[unverified]** — [aifilms blog](https://studio.aifilms.ai/blog/pixal3d-image-to-3d-asset-generation)

**TRELLIS v1 (Microsoft)**
- MIT. Two submodules (diffoctreerast, modified Flexicubes) have their own licences. Models: image-large 1.2B, **text-base 342M, text-large 1.1B, text-xlarge 2.0B**. Needs at least 16 GB. Tested on Linux only, with Windows covered in issue #3. Default env is PyTorch 2.4.0 + CUDA 11.8. Dependencies: xformers, flash-attn, spconv, kaolin, nvdiffrast, diffoctreerast, mip-splatting — [GitHub microsoft/TRELLIS](https://github.com/microsoft/TRELLIS)
- Outputs: 3D Gaussians (PLY), radiance fields, GLB mesh. The README itself recommends text→image→image-to-3D over its text models, because text-conditioned models are "less creative and detailed" — [GitHub](https://github.com/microsoft/TRELLIS)
- `SPCONV_ALGO` defaults to `auto`, which benchmarks at startup; `native` is recommended for single runs. `ATTN_BACKEND` defaults to flash-attn — [GitHub](https://github.com/microsoft/TRELLIS)

**Roblox Cube 3D (native text→shape)**
- v0.1 March 2025. v0.5 July 2025 added bounding-box conditioning and a VQ-VAE latent of 512→1024. CubePart (part-controllable, mesh + parts schema) came in May 2026. Texture is listed as "upcoming" — [GitHub Roblox/cube](https://github.com/Roblox/cube)
- VRAM: 24 GB recommended with `--fast-inference`, 16 GB otherwise [authors]. Windows is mentioned, with a note to install a CUDA-enabled PyTorch. Tested on L40S, H100, A100 and Apple M2–M4. Output `.obj`. `--bounding-box-xyz` (e.g. `1.0 2.0 1.5`). Decoding can be slow; lowering `--resolution-base` (4.0–9.0) speeds it up. Weights `Roblox/cube3d-v0.5` and `Roblox/cubepart` — [GitHub](https://github.com/Roblox/cube)
- Determinism: generation is deterministic when `top_p` is unset. No seed parameter is documented — [GitHub](https://github.com/Roblox/cube)
- HF licence tag is "openrail", with no further terms shown on the card — [HF Roblox/cube3d-v0.5](https://huggingface.co/Roblox/cube3d-v0.5). **[unverified]: exact LICENSE text and use restrictions.**

**Direct3D-S2 (DreamTech, NeurIPS 2025)**
- MIT. Code and models v1.0/v1.1 released 2025-05-30. v1.2 was "in preparation" as of June 2025. Needs ≥10 GB at 512 (not recommended for quality) and ~24 GB at 1024 [authors]. Tested on Ubuntu 22.04, CUDA 12.1, PyTorch 2.5.1. Requires **TorchSparse**. Windows is covered only in community issues #11/#12. Output OBJ with `remove_interior` and `remesh` options. Weights `wushuang98/Direct3D-S2` (subfolder `direct3d-s2-v-1-1`). Image-only — [GitHub DreamTechAI/Direct3D-S2](https://github.com/DreamTechAI/Direct3D-S2)

**Step1X-3D (StepFun)**
- Apache-2.0. Released 2025-05-13. Geometry + texture needs 27 GB (29 GB for the Label variant). ~152 s for 50 steps. No low-VRAM option is listed. Env is CUDA 12.4, PyTorch 2.5.1, pytorch3d, kaolin 0.17.0, torch-cluster, plus two rasterizers built from source and taken from Hunyuan3D 2.0. Output GLB. The geometry stage uses "watertight TSDF". Stage 1 produces an untextured mesh. Weights `stepfun-ai/Step1X-3D`. Image-only — [GitHub stepfun-ai/Step1X-3D](https://github.com/stepfun-ai/Step1X-3D)
- [unverified] VRAM for the geometry stage alone.

**SF3D / SPAR3D (Stability AI)**
- Both use the "Stability AI Community License": free for research, non-commercial and commercial use under US$1M annual revenue. No territorial restriction is stated. HF access is gated (share contact info, accept the licence). SF3D: 1B params, 512×512 input, "under one second", textured UV-unwrapped low-poly mesh — [HF stable-fast-3d](https://huggingface.co/stabilityai/stable-fast-3d)
- SPAR3D: about 2B params, point-cloud diffusion + mesh stage, "under one second", textured mesh with delighting — [HF stable-point-aware-3d](https://huggingface.co/stabilityai/stable-point-aware-3d)

**Hunyuan3D family (Tencent) — excluded for South Korea**
- 2.1: "TENCENT HUNYUAN 3D 2.1 COMMUNITY LICENSE AGREEMENT"; "'Territory' shall mean the worldwide territory, excluding the territory of the European Union, United Kingdom and South Korea"; "THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA"; §5(c) "Any such use outside the Territory is unlicensed and unauthorized" — [HF Hunyuan3D-2.1 LICENSE](https://huggingface.co/tencent/Hunyuan3D-2.1/blob/main/LICENSE)
- 2mini (and 2.0): "TENCENT HUNYUAN 3D 2.0 COMMUNITY LICENSE AGREEMENT", with the same Territory definition excluding EU, UK and South Korea — [HF Hunyuan3D-2mini LICENSE](https://huggingface.co/tencent/Hunyuan3D-2mini/blob/main/LICENSE)
- Hunyuan3D-Omni (built on 2.1, adds point cloud, voxel, **bounding box** and skeleton conditioning): HF licence tag `tencent-hunyuan-community` — [HF tencent/Hunyuan3D-Omni](https://huggingface.co/tencent/Hunyuan3D-Omni/tree/main); [arXiv 2509.21245](https://arxiv.org/abs/2509.21245v1). The Omni LICENSE text was not read **[unverified]**. Same family, so the KR exclusion presumably applies.
- 2.5 / 3.x: no open weights found. The cinevva timeline lists only a 2.5 API endpoint shutdown on 2026-10-20 and a pointer to "HY-3D-3.1 on TokenHub" (a hosted service). "Hunyuan3D-Buffalo 1.0" was announced in August 2026 with no weights verified — [cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)

**Others**
- **CraftsMan3D**: MIT. Image-conditioned only; text conditioning is "planned". Coarse mesh ~5 s + refinement ~20 s [authors]. Ubuntu 22.04, PyTorch 2.5.1, CUDA 12.4, torch-cluster. Output OBJ, geometry only. Weights `craftsman3d/craftsman` and `craftsman3d/craftsman-doravae` — [GitHub CraftsMan3D](https://github.com/wyysf-98/CraftsMan)
- **Hi3DGen / Stable3DGen**: MIT. Adapted from TRELLIS. torch 2.4.0, spconv-cu 2.3.6, xformers 0.0.27.post2. kaolin, nvdiffrast and flexicubes removed. VRAM and output not stated — [GitHub Stable-X/Hi3DGen](https://github.com/Stable-X/Hi3DGen)
- **Hi3D v1.0** (announced 2026-10-23): reference image + coarse mesh → refined geometry, no textures, under a "Hi3D Open License Agreement" — [cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026). Licence text was not read **[unverified]**.
- **PartCrafter**: MIT. Fine-tuned from TripoSG's DiT. ≥8 GB. Python 3.11, PyTorch 2.5.1 + CUDA 12.4. Windows through a community PR or fork. An optional Gemini API key (part suggestion) must stay off under our no-cloud rule. Weights `wgsxm/PartCrafter` — [GitHub wgsxm/PartCrafter](https://github.com/wgsxm/PartCrafter)
- **PartPacker (NVIDIA)**: ~10 GB in fp16 [authors]. Has a Windows section (Python 3.10, CUDA 12.4, Torch 2.5.1, tested on 3090/4090). Weights `nvidia/PartPacker`. The licence is in `license.md`, which I did not read — [GitHub NVlabs/PartPacker](https://github.com/NVlabs/PartPacker). **[unverified]: licence terms. NVlabs repos often use non-commercial research licences; check before use.**
- **InstantMesh**: Apache-2.0. Install pins torch 2.1.0 + cu121 and xformers 0.0.22.post7. Output OBJ with vertex colours. Weights `TencentARC/InstantMesh` — [GitHub TencentARC/InstantMesh](https://github.com/TencentARC/InstantMesh)
- **SAM 3D Objects (Meta, 2025-11-19)**: "SAM License", worldwide royalty-free grant with trade-control compliance and no military use. Publications must acknowledge SAM. No country exclusion, and no research/commercial split — [LICENSE](https://github.com/facebookresearch/sam-3d-objects/blob/main/LICENSE). Input is an image plus an object mask. The README example saves a Gaussian splat PLY — [GitHub](https://github.com/facebookresearch/sam-3d-objects). The timeline says it produces mesh and Gaussian outputs — [cinevva](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)

### Inferences
- **Python 3.11 vs community wheels.** TRELLIS.2's Windows wheels are cp310. Either a separate Python 3.10 venv with its own torch cu128 build, or a source build, is needed. The 2026-11-22 setup (torch 2.11.0+cu128, py3.11) probably cannot be reused as-is for TRELLIS.2, Direct3D-S2 or InstantMesh. TripoSG, Cube and CraftsMan3D have pure-PyTorch-leaning dependency lists and are the likeliest to run in the existing env, but that is unconfirmed.
- **Sources of non-determinism to control.** These come from the docs above plus general CUDA knowledge, not from a source that tested them:
  - spconv `SPCONV_ALGO=auto` (startup benchmarking can pick different kernels). Set `native`.
  - flash-attn vs SDPA/xformers backend choice.
  - Seed-dependent token counts (TRELLIS.2 OOM by seed).
  - Cube's `top_p`.
  - Re-verify byte-identity per model as was done on 2026-11-22. Do not assume it.
- **Pinning.** Every candidate's weights are on Hugging Face, so revision commit hashes can be pinned: `VAST-AI/TripoSG`, `microsoft/TRELLIS.2-4B`, `TencentARC/Pixal3D`, `Roblox/cube3d-v0.5`, `wushuang98/Direct3D-S2`, `stepfun-ai/Step1X-3D`, `stabilityai/stable-fast-3d`, `stabilityai/stable-point-aware-3d`, `craftsman3d/craftsman`, `wgsxm/PartCrafter`, `nvidia/PartPacker`, `TencentARC/InstantMesh`. The gated DINOv3 and RMBG-2.0 dependencies of TRELLIS.2 must be pinned too.

### Gaps
- Measured generation time on a 16 GB-class GPU for TripoSG, Cube, Direct3D-S2, CraftsMan3D and Step1X-3D geometry. Not found; only authors' requirement statements exist.
- Exact licence texts for Cube 3D ("openrail" variant), PartPacker, Hi3D v1.0 and Hunyuan3D-Omni were not read.
- Any notable fully-open 2026 shape model besides Pixal3D, CubePart and Hi3D v1.0. The only 2026 timeline found is a 3rd-party aggregator, and it does not cover UltraShape, Sparc3D, LATTICE etc. These were not researched.
- Reported fixed-seed reproducibility for TripoSG, Cube or TRELLIS.2 on Windows. No reports were found.

## Q2. Thin structures, sheets and amorphous/volumetric objects (mist, smoke, flame, cloth, paper, lines)

### Takeaway
The literature treats this as a **known failure class** for SDF/watertight-occupancy 3D generators: open sheets get closed into double-layered shells, and training data are dominated by closed surfaces. Among open models, only TRELLIS.2 (and Pixal3D on top of it) claims open-surface support. No source shows any image-to-3D *mesh* model handling mist, smoke or flame. Volumetric phenomena fit Gaussian or radiance-field outputs (TRELLIS v1, SAM 3D), which glTFast mesh import does not cover.

### Cited Findings
- "Neural Signed Distance Functions (SDFs) excel at reconstructing watertight manifolds but fail on thin structures and open boundaries due to strict inside–outside constraints" — [Metric–Phase Fields, arXiv 2605.25503](https://arxiv.org/html/2605.25503)
- The sign assumption "becomes ambiguous for open surfaces … including clothing and cloth folds, thin sheets" — [arXiv 2610.13088](https://arxiv.org/html/2610.13088)
- Sparc3D's VAE converts open surfaces into double-layered watertight meshes — [Sparc3D, arXiv 2505.14521](https://arxiv.org/html/2505.14521v2)
- UltraShape: when the fill is applied to non-watertight inputs it "often leaks into the interior, yielding unintended double-layered thin shells" — [UltraShape 1.0, arXiv 2512.21185](https://arxiv.org/html/2512.21185v2)
- LoG3D: SDF pipelines depend on watertight preprocessing that "fundamentally fails on open or non-manifold topologies". It proposes a UDF VAE — [LoG3D, arXiv 2511.10040](https://arxiv.org/pdf/2511.10040). SparseFlex also targets arbitrary topology — [SparseFlex ICCV 2025](https://openaccess.thecvf.com/content/ICCV2025/papers/He_SparseFlex_High-Resolution_and_Arbitrary-Topology_3D_Shape_Modeling_ICCV_2025_paper.pdf)
- TRELLIS.2 claims "Open Surfaces (e.g., clothing, leaves)" and non-manifold geometry via O-Voxel — [GitHub TRELLIS.2](https://github.com/microsoft/TRELLIS.2)
- Step1X-3D's geometry uses "watertight TSDF" — [GitHub Step1X-3D](https://github.com/stepfun-ai/Step1X-3D). TripoSG is built on 3DShape2VecSet-style SDF VAE lineage per its acknowledgements — [GitHub TripoSG](https://github.com/VAST-AI-Research/TripoSG)
- TRELLIS v1 can decode to 3D Gaussians and radiance fields as well as meshes — [GitHub TRELLIS](https://github.com/microsoft/TRELLIS). SAM 3D Objects saves Gaussian splat PLY — [GitHub sam-3d-objects](https://github.com/facebookresearch/sam-3d-objects)

### Inferences
- "Paper" and "cloth" are the cases a model like TRELLIS.2 could plausibly fix. "Thin line" at 512–1536³ voxel resolution will still be at or below the resolution limit. "Mist" and "flame" are not surfaces at all, so a mesh-only pipeline cannot represent them faithfully whatever the model. A rule-based procedural fallback for these classes (a particle system or volumetric shader in Unity, set by the existing rule layer) is the realistic route, with ML generation reserved for solid-ish nouns (lump, ball, animal, crumpled paper).
- TripoSG and other SDF models will likely render "a piece of cloth" or "paper" as a slab with thickness. For a shape-only scene this may be acceptable, but it should be scored separately.

### Gaps
- No benchmark specifically evaluates image-to-3D on thin sheets, lines or volumetric phenomena, so I found no quantitative failure rates.
- No independent test was found of TRELLIS.2's open-surface claim on cloth or paper inputs.

## Q3. Local text-to-image front end (single object, plain background, readable shape) on 16 GB

### Takeaway
The cleanest licence picks are **FLUX.2 [klein] 4B (Apache-2.0, ~13 GB per BFL)**, **Z-Image-Turbo (Apache-2.0, 6B, 8 steps, "fits … 16G VRAM")** and **FLUX.1-schnell (Apache-2.0)**. Qwen-Image (Apache-2.0, 20B) needs quantization to fit. Sana Sprint carries a contradictory "research purposes only" note plus Gemma terms. FLUX.2 dev and klein 9B are under the FLUX Non-Commercial License. I found no source comparing prompt adherence on abstract or amorphous objects.

### Cited Findings
- FLUX.2 [klein] 4B is Apache 2.0 and the 9B klein models use the FLUX Non-Commercial License. The 4B "fits in ~13GB VRAM (RTX 3090/4070 and above)" [authors]. One model handles T2I, editing and multi-reference — [BFL blog](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence); 9B/dev non-commercial per [VentureBeat](https://venturebeat.com/technology/black-forest-labs-launches-open-source-flux-2-klein-to-generate-ai-images-in)
- BFL claims klein outperforms Z-Image (vendor claim) — [BFL blog](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence)
- Licence matrix (Aug 2026, 3rd-party): FLUX.1-schnell Apache 2.0; FLUX.2 dev 32B FLUX Non-Commercial; Z-Image Turbo/base Apache 2.0, 6B, runs on 16 GB; Qwen-Image line Apache 2.0, "20B checkpoints want 40GB+ in BF16" — [invideo.io](https://invideo.io/blog/open-source-image-models-licenses/)
- Z-Image-Turbo HF card: Apache-2.0, 6B, 8 DiT forwards (`num_inference_steps=9`), `guidance_scale=0.0`, "fits comfortably within 16G VRAM consumer devices", sub-second on H800 [authors]. The example uses `manual_seed(42)` and makes no explicit determinism claim. Paper dated 2025-11-27 — [HF Tongyi-MAI/Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
- Sana Sprint 1.6B: Apache-2.0 tag, but the card says "intended for research purposes only", and Gemma Terms apply to its Gemma-2-2B-IT encoder. 1–4 steps. 0.31 s on RTX 4090 [authors] — [HF Sana_Sprint_1.6B](https://huggingface.co/Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers)

### Inferences
- For this project (non-commercial academic), even FLUX Non-Commercial and Stability Community licences would probably be acceptable. Apache-2.0 models avoid the question entirely.
- The 2026-11-22 pipeline used SDXL. Replacing it with Z-Image-Turbo or FLUX.2 klein 4B fits the 16 GB budget only if the T2I model is unloaded before the 3D stage, because TRELLIS.2 or Cube alone want most of 16 GB.
- Diffusers pipelines with a fixed `torch.Generator` seed are usually reproducible on the same GPU/driver/library versions. Byte-identity must be re-checked, as was done for SDXL.

### Gaps
- SD3.5 Medium licence and VRAM were not re-verified (assumed Stability Community License **[unverified]**).
- No evaluation of prompt adherence for abstract or amorphous prompts ("mist", "a thin line") was found for any of these models.
- No verified VRAM figure for FLUX.1-schnell or Sana on 16 GB.

## Q4. Automatic text↔3D shape agreement metrics runnable locally

### Takeaway
Local options are: **CLIP score on multi-view renders**; a **Uni3D text–point-cloud cosine similarity**, used as the text-alignment score in GT23D-Bench; and **VLM-judge methods with open VLMs**. Eval3D reports LLaVA at about 88.7% human agreement vs 91.5% for GPT-4o on text-3D alignment. GPTEval3D defaults to closed GPT-4V, and Hi3DEval swaps in GPT-4o, so both need adaptation to a local VLM.

### Cited Findings
- GPTEval3D (CVPR 2024): pairwise comparisons → Elo, with GPT-4V as the default judge — [GitHub 3DTopia/GPTEval3D](https://github.com/3DTopia/GPTEval3D)
- GT23D-Bench computes text alignment as cosine similarity between Uni3D point-cloud features and prompt text features — [arXiv 2412.09997](https://arxiv.org/pdf/2412.09997)
- Uni3D authors planned a "Uni3D-score" for text-to-3D semantic coherence (details via GeoDream). It is unclear whether it has shipped — [GitHub baaivision/Uni3D](https://github.com/baaivision/Uni3D)
- Eval3D is fully open-source and replaces GPT-4o with LLaVA for text-3D alignment, at ~88.7% vs 91.5% agreement with humans — [Eval3D, arXiv 2504.18509](https://arxiv.org/pdf/2504.18509)
- Hi3DEval evaluates both text- and image-to-3D and uses GPT-4o in its GPTEval3D baseline — [arXiv 2508.05609](https://arxiv.org/pdf/2508.05609)
- A 2025 fine-grained T23D quality benchmark re-implements criteria-based evaluation with open-source LLM evaluators — [arXiv 2509.23841](https://arxiv.org/html/2509.23841v1)

### Inferences
- For a shape-only, colour-free setting, render untextured shaded multi-views (fixed lighting and camera ring) and score with: (a) CLIP/SigLIP text–image similarity averaged over views; (b) Uni3D or OpenShape point-cloud–text similarity, which needs no rendering and ignores colour if points are uncoloured; (c) a local VLM yes/no judge as a secondary check. All three can run offline. The prior "4/120 matched" figure was presumably human-judged and could serve as a small calibration set.

### Gaps
- T3Bench, ULIP-2 and OpenShape were not checked for licence or local runnability in this pass.
- No source validates these metrics on abstract or amorphous concepts such as mist or line. CLIP-type scores on untextured renders of such concepts are likely unreliable, but that is untested.

## Q5. Geometry-only generation and scale/orientation normalization

### Takeaway
Several candidates are geometry-only by design: TripoSG, CraftsMan3D, Cube 3D, Step1X-3D stage 1, and Hi3D v1.0's refinement. Cube 3D v0.5 is the only open, KR-usable model found with explicit **bounding-box (aspect) conditioning** from text. Hunyuan3D-Omni also has bbox conditioning but is licence-excluded. I found no open model that guarantees a canonical *orientation*, so pose normalization has to be a deterministic post-process.

### Cited Findings
- TripoSG outputs a mesh with no texture mentioned. `--faces` caps the face count — [GitHub TripoSG](https://github.com/VAST-AI-Research/TripoSG)
- Cube 3D v0.5 has `--bounding-box-xyz` conditioning and outputs OBJ. Texture is "upcoming", so output is geometry only — [GitHub Roblox/cube](https://github.com/Roblox/cube)
- Step1X-3D stage 1 produces an untextured mesh, with texture as a separate stage — [GitHub Step1X-3D](https://github.com/stepfun-ai/Step1X-3D)
- CraftsMan3D outputs a geometry-only OBJ — [GitHub CraftsMan](https://github.com/wyysf-98/CraftsMan)
- Hi3D v1.0 does reference image + coarse mesh → refined geometry with no textures — [cinevva timeline](https://app.cinevva.com/guides/ai-3d-model-generation-timeline-2026)
- Hunyuan3D-Omni accepts bounding-box and other conditioning, but uses the Tencent Hunyuan community licence — [arXiv 2509.21245](https://arxiv.org/abs/2509.21245v1); [HF](https://huggingface.co/tencent/Hunyuan3D-Omni/tree/main)
- TRELLIS.2 exports textured PBR GLB by default, and shape and material are separate stages in its timing breakdown (e.g. 1024³: 10 s shape + 7 s material) — [GitHub TRELLIS.2](https://github.com/microsoft/TRELLIS.2)

### Inferences
- For TRELLIS.2, running only the shape stage (skipping material) should cut both time and VRAM, judging from the stage split. Whether the public API exposes this cleanly is **[unverified]**.
- Deterministic post-processing (outside ML, consistent with AGENTS.md principle 1) can produce a canonical pose: centre at the bbox centre, scale to unit max-extent, align to principal axes by PCA with a fixed sign convention, place the lowest point at y=0, decimate to a fixed face budget, then export GLB via trimesh. The rule layer then sets size and colour in Unity. Image-to-3D outputs are aligned to the input camera, so a fixed front-view T2I prompt template ("centered, front view, plain white background") also helps orientation consistency.

### Gaps
- No open model was found that outputs canonically oriented shapes (an "upright/front" guarantee). No canonical-pose tool (e.g. orientation estimators) was researched in this pass.
