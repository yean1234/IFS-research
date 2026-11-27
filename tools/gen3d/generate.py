"""한국어 문장 → (영어 프롬프트) → 로컬 3D 생성 모델 → GLB + 메타데이터 JSON.

  <venv>/python tools/gen3d/generate.py --run <이름> --pipeline shap-e|sdxl-triposr|sdxl-triposg \
      [--prompt-mode rules|llm] [--seed 0] [--ids D01,D02] [--repeat 2]

입력: OUT_ROOT/<run>/inputs/sentences.json (inputs.py가 만든다).
출력: OUT_ROOT/<run>/<pipeline>-<prompt-mode>/  (저장소 밖, 원칙 6)
  specs/<id>.json        규칙 경로 SceneSpec(기존 SceneSpecBuilderV1, 코드 무수정 호출). Unity BatchCapture 입력과 같다.
  glb/<id>.glb           생성 메시(y-up, 정점 색). --repeat 2면 glb_rep1/에 같은 조건으로 한 번 더(결정성 확인).
  images/<id>.png        sdxl-triposr의 중간 이미지(text→image 결과)
  meta/<id>.json         입력 id, 프롬프트(+근거 슬롯), 모델 ID·리비전·파일 sha256, seed, 단계별 시간, VRAM 최대치,
                         GLB sha256·크기·정점/삼각형 수
  run.json               실행 환경·모델 출처·요약

모든 모델은 로컬에서 돈다. 가중치는 HF 캐시(저장소 밖)에서 local_files_only로 읽는다(원칙 5).
"""
from __future__ import annotations

import argparse
import gc
import sys
import time
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts  # noqa: E402
from common import (MODELS_ROOT, OUT_ROOT, VramPeak, assert_outside_repo, env_info, git_head,  # noqa: E402
                    hf_provenance, read_json, sha256_file, sha256_text, write_json)

# 생성 모델에 붙이는 시스템 꼬리말(심상 속성이 아님. meta에 따로 기록)
SUFFIX_SHAPE_E = ""                                                    # Shap-E는 물체 하나를 바로 만든다
SUFFIX_IMAGE = ", single object centered, full view, isolated on a plain white background, soft studio lighting, 3D render"
NEGATIVE_IMAGE = "text, watermark, multiple objects, cropped, person, hands, frame, scenery, floor, shadow"


def set_determinism(seed: int):
    import random

    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False


def mesh_stats(path: Path) -> dict:
    import trimesh

    scene = trimesh.load(path, force="scene")
    v = sum(len(g.vertices) for g in scene.geometry.values())
    f = sum(len(g.faces) for g in scene.geometry.values())
    ext = scene.extents.tolist() if scene.geometry else None
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size, "vertices": int(v), "triangles": int(f),
            "extents": [round(x, 4) for x in ext] if ext else None}


def to_y_up_glb(mesh, out: Path, rot_x_deg: float):
    """생성 메시를 glTF 좌표(y-up)로 돌리고 정점 색을 유지해 GLB로 쓴다."""
    import trimesh

    if rot_x_deg:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.radians(rot_x_deg), [1, 0, 0]))
    trimesh.repair.fix_normals(mesh)
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out, file_type="glb")
    _set_dielectric_material(out)


def _set_dielectric_material(path: Path):
    """trimesh는 정점 색만 있는 메시를 머티리얼 없이 쓴다. glTF 기본 머티리얼은 metallic 1이라 확산광이 없어
    Unity에서 거의 검게 보인다. 금속도 0·거칠기 0.8의 단일 머티리얼(색은 정점 색 그대로)을 붙인다.
    이 값도 생성 모델이 아니라 시스템이 정한 표면 값이다(meta의 exportMaterial에 기록)."""
    from pygltflib import GLTF2, Material, PbrMetallicRoughness

    g = GLTF2().load_binary(str(path))
    g.materials = [Material(name="gen3d_vertex_color", doubleSided=True,
                            pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=[1, 1, 1, 1],
                                                                      metallicFactor=0.0, roughnessFactor=0.8))]
    for m in g.meshes:
        for p in m.primitives:
            p.material = 0
    g.save_binary(str(path))


EXPORT_MATERIAL = {"metallicFactor": 0.0, "roughnessFactor": 0.8, "doubleSided": True, "color": "vertex COLOR_0"}


# ── Shap-E (text → 3D, MIT) ────────────────────────────────────────────────────
class ShapE:
    REPO = "openai/shap-e"
    LICENSE = "MIT"

    def __init__(self, steps=64, guidance=15.0, frame_size=256):
        import torch
        from diffusers import ShapEPipeline

        self.pipe = ShapEPipeline.from_pretrained(self.REPO, torch_dtype=torch.float16, variant="fp16",
                                                  local_files_only=True).to("cuda")
        self.pipe.set_progress_bar_config(disable=True)
        self.cfg = {"num_inference_steps": steps, "guidance_scale": guidance, "frame_size": frame_size}

    def provenance(self):
        return [hf_provenance(self.REPO)]

    def make(self, prompt: str, seed: int, out: Path, work: Path) -> dict:
        import torch
        import trimesh

        g = torch.Generator("cuda").manual_seed(seed)
        t0 = time.perf_counter()
        with VramPeak() as vp:
            res = self.pipe(prompt, generator=g, output_type="mesh", **self.cfg).images[0]
        t1 = time.perf_counter()
        verts = res.verts.detach().cpu().numpy()
        faces = res.faces.detach().cpu().numpy()
        rgb = np.stack([res.vertex_channels[c].detach().cpu().numpy() for c in "RGB"], axis=1)
        mesh = trimesh.Trimesh(vertices=verts, faces=faces,
                               vertex_colors=(np.clip(rgb, 0, 1) * 255).astype(np.uint8), process=False)
        to_y_up_glb(mesh, out, -90.0)                # Shap-E 메시는 z-up
        return {"seconds": {"generate": round(t1 - t0, 2), "export": round(time.perf_counter() - t1, 2)},
                "vram": {"maxAllocatedGiB": vp.allocated_gib, "maxReservedGiB": vp.reserved_gib},
                "config": self.cfg}


# ── SDXL (text → image) + TripoSR (image → 3D) ─────────────────────────────────
def _install_torchmcubes_shim():
    """TripoSR은 torchmcubes(CUDA 확장, Windows에서 빌드 필요)를 쓴다. 같은 계약의 skimage 구현으로 대신한다.

    torchmcubes.marching_cubes(vol, thr) → (verts[N,3] (dim2, dim1, dim0) 순서, faces[M,3]).
    skimage는 (dim0, dim1, dim2) 순서로 돌려주므로 뒤집는다. 면 감기 방향은 GLB로 쓸 때 fix_normals로 맞춘다.
    """
    if "torchmcubes" in sys.modules:
        return
    import torch
    from skimage import measure

    def marching_cubes(vol, thr):
        v = vol.detach().float().cpu().numpy()
        verts, faces, _, _ = measure.marching_cubes(v, level=float(thr))
        verts = np.ascontiguousarray(verts[:, ::-1])
        return torch.from_numpy(verts.astype(np.float32)), torch.from_numpy(faces.astype(np.int64))

    mod = types.ModuleType("torchmcubes")
    mod.marching_cubes = marching_cubes
    sys.modules["torchmcubes"] = mod


class SdxlTripoSR:
    IMG_REPO = "stabilityai/stable-diffusion-xl-base-1.0"
    IMG_LICENSE = "CreativeML Open RAIL++-M"
    TSR_REPO = "stabilityai/TripoSR"
    TSR_LICENSE = "MIT"

    def __init__(self, steps=30, guidance=7.0, size=1024, mc_resolution=256):
        self.cfg = {"image": {"num_inference_steps": steps, "guidance_scale": guidance, "size": size,
                              "negative_prompt": NEGATIVE_IMAGE},
                    "triposr": {"mc_resolution": mc_resolution, "foreground_ratio": 0.85, "chunk_size": 8192,
                                "marching_cubes": "skimage shim (torchmcubes 대체)"}}
        self.img = None
        self.tsr = None
        self.rembg = None

    def provenance(self):
        tsr_code = MODELS_ROOT / "TripoSR"
        return [hf_provenance(self.IMG_REPO, (".safetensors",)), hf_provenance(self.TSR_REPO),
                hf_provenance("facebook/dino-vitb16"),
                {"repo": "github.com/VAST-AI-Research/TripoSR (code)", "revision": git_head(tsr_code)},
                {"repo": "github.com/danielgatis/rembg releases v0.0.0 u2net.onnx (배경 제거)",
                 "sha256": sha256_file(Path.home() / ".u2net" / "u2net.onnx")}]

    # 두 단계를 나눠 VRAM을 겹치지 않게 한다: 모든 문장 이미지 → SDXL 내림 → 모든 문장 3D.
    def load_image_model(self):
        import torch
        from diffusers import StableDiffusionXLPipeline

        self.img = StableDiffusionXLPipeline.from_pretrained(self.IMG_REPO, torch_dtype=torch.float16,
                                                             local_files_only=True, use_safetensors=True).to("cuda")
        self.img.set_progress_bar_config(disable=True)

    def unload_image_model(self):
        import torch

        self.img = None
        gc.collect()
        torch.cuda.empty_cache()

    def make_image(self, prompt: str, seed: int, out_png: Path) -> dict:
        import torch

        c = self.cfg["image"]
        g = torch.Generator("cuda").manual_seed(seed)
        t0 = time.perf_counter()
        with VramPeak() as vp:
            im = self.img(prompt=prompt, negative_prompt=c["negative_prompt"], num_inference_steps=c["num_inference_steps"],
                          guidance_scale=c["guidance_scale"], width=c["size"], height=c["size"], generator=g).images[0]
        out_png.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png)
        return {"seconds": round(time.perf_counter() - t0, 2),
                "vram": {"maxAllocatedGiB": vp.allocated_gib, "maxReservedGiB": vp.reserved_gib},
                "imageSha256": sha256_file(out_png)}

    def load_3d_model(self):
        import rembg

        _install_torchmcubes_shim()
        sys.path.insert(0, str(MODELS_ROOT / "TripoSR"))
        from tsr.system import TSR

        self.tsr = TSR.from_pretrained(self.TSR_REPO, config_name="config.yaml", weight_name="model.ckpt")
        self.tsr.renderer.set_chunk_size(self.cfg["triposr"]["chunk_size"])
        self.tsr.to("cuda")
        self.rembg = rembg.new_session()

    def make_3d(self, png: Path, seed: int, out: Path) -> dict:
        import torch
        from PIL import Image
        from tsr.utils import remove_background, resize_foreground

        set_determinism(seed)
        t0 = time.perf_counter()
        im = remove_background(Image.open(png).convert("RGB"), self.rembg)
        im = resize_foreground(im, self.cfg["triposr"]["foreground_ratio"])
        arr = np.array(im).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        im = Image.fromarray((arr * 255.0).astype(np.uint8))
        t1 = time.perf_counter()
        with VramPeak() as vp, torch.no_grad():
            codes = self.tsr([im], device="cuda")
            mesh = self.tsr.extract_mesh(codes, True, resolution=self.cfg["triposr"]["mc_resolution"])[0]
        t2 = time.perf_counter()
        to_y_up_glb(mesh, out, -90.0)                # TripoSR 메시는 z-up
        return {"seconds": {"removeBackground": round(t1 - t0, 2), "reconstruct": round(t2 - t1, 2),
                            "export": round(time.perf_counter() - t2, 2)},
                "vram": {"maxAllocatedGiB": vp.allocated_gib, "maxReservedGiB": vp.reserved_gib}}


# ── 실행 ──────────────────────────────────────────────────────────────────────
def make_prompts(rows, mode: str, seed: int, specs_dir: Path) -> dict:
    out = {}
    for r in rows:
        spec = prompts.build_spec(r["text"], r["id"])
        write_json(specs_dir / f"{r['id']}.json", spec)
        if mode == "rules":
            p = prompts.rules_prompt(spec)
        else:
            p = prompts.llm_prompt(r["text"], seed=seed)
        p["textSha256"] = sha256_text(r["text"])
        out[r["id"]] = p
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--pipeline", choices=["shap-e", "sdxl-triposr", "sdxl-triposg"], required=True,
                    help="sdxl-triposg = G62 형태 후보 생성기(form_asset.py, form-asset.v0 사이드카, 규칙 프롬프트만)")
    ap.add_argument("--prompt-mode", choices=["rules", "llm"], default="rules")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--repeat", type=int, default=1, help="2면 같은 조건으로 한 번 더 만들어 결정성을 본다")
    ap.add_argument("--no-cache", action="store_true",
                    help="(sdxl-triposg) 캐시가 있어도 다시 만들고, 앞 프로세스의 GLB sha256과 비교해 run.json에 적는다")
    a = ap.parse_args(argv)

    run_dir = assert_outside_repo(OUT_ROOT / a.run)
    rows = read_json(run_dir / "inputs" / "sentences.json")
    if a.ids:
        keep = set(a.ids.split(","))
        rows = [r for r in rows if r["id"] in keep]
    if a.pipeline == "sdxl-triposg":
        import form_asset

        if a.prompt_mode != "rules":
            raise SystemExit("sdxl-triposg는 규칙 프롬프트(shape_prompt)만 쓴다(원칙 1)")
        form_asset.run(rows, a.run, pipeline=a.pipeline, seed=a.seed, repeat=a.repeat, no_cache=a.no_cache)
        return
    out_dir = run_dir / f"{a.pipeline}-{a.prompt_mode}"
    t_start = time.perf_counter()

    pr = make_prompts(rows, a.prompt_mode, a.seed, out_dir / "specs")
    set_determinism(a.seed)
    metas = {r["id"]: {"id": r["id"], "kind": r.get("kind"), "seed": a.seed, "pipeline": a.pipeline,
                       "promptMode": a.prompt_mode, "prompt": pr[r["id"]], "runs": []} for r in rows}

    if a.pipeline == "shap-e":
        gen = ShapE()
        for rep in range(a.repeat):
            for r in rows:
                prompt = pr[r["id"]]["subject"] + SUFFIX_SHAPE_E
                glb = out_dir / ("glb" if rep == 0 else f"glb_rep{rep}") / f"{r['id']}.glb"
                set_determinism(a.seed)
                info = gen.make(prompt, a.seed, glb, out_dir)
                info.update(finalPrompt=prompt, glb=glb.name, mesh=mesh_stats(glb), repeat=rep)
                metas[r["id"]]["runs"].append(info)
                print(r["id"], rep, info["seconds"], info["mesh"]["triangles"], flush=True)
    else:
        gen = SdxlTripoSR()
        gen.load_image_model()
        imgs = {}
        for rep in range(a.repeat):
            for r in rows:
                prompt = pr[r["id"]]["subject"] + SUFFIX_IMAGE
                png = out_dir / ("images" if rep == 0 else f"images_rep{rep}") / f"{r['id']}.png"
                set_determinism(a.seed)
                imgs[(rep, r["id"])] = (prompt, png, gen.make_image(prompt, a.seed, png))
                print(r["id"], rep, "image", imgs[(rep, r["id"])][2]["seconds"], flush=True)
        gen.unload_image_model()
        gen.load_3d_model()
        for rep in range(a.repeat):
            for r in rows:
                prompt, png, iinfo = imgs[(rep, r["id"])]
                glb = out_dir / ("glb" if rep == 0 else f"glb_rep{rep}") / f"{r['id']}.glb"
                info = gen.make_3d(png, a.seed, glb)
                info["seconds"]["image"] = iinfo["seconds"]
                info["vram"] = {"image": iinfo["vram"], "reconstruct": info["vram"]}
                info.update(finalPrompt=prompt, negativePrompt=NEGATIVE_IMAGE, image=png.name,
                            imageSha256=iinfo["imageSha256"], glb=glb.name, mesh=mesh_stats(glb), repeat=rep)
                metas[r["id"]]["runs"].append(info)
                print(r["id"], rep, info["seconds"], info["mesh"]["triangles"], flush=True)

    prov = gen.provenance()
    det = {}
    for sid, m in metas.items():
        m["models"] = prov
        m["config"] = gen.cfg
        write_json(out_dir / "meta" / f"{sid}.json", m)
        if a.repeat > 1:
            hashes = [x["mesh"]["sha256"] for x in m["runs"]]
            same_img = None
            if a.pipeline == "sdxl-triposr":
                same_img = len({x["imageSha256"] for x in m["runs"]}) == 1
            det[sid] = {"glbIdentical": len(set(hashes)) == 1, "imageIdentical": same_img,
                        "triangles": [x["mesh"]["triangles"] for x in m["runs"]]}
    write_json(out_dir / "run.json", {"pipeline": a.pipeline, "promptMode": a.prompt_mode, "seed": a.seed,
                                      "repeat": a.repeat, "ids": [r["id"] for r in rows], "env": env_info(),
                                      "models": prov, "config": gen.cfg, "exportMaterial": EXPORT_MATERIAL,
                                      "suffix": SUFFIX_IMAGE if a.pipeline != "shap-e" else SUFFIX_SHAPE_E,
                                      "determinism": det, "totalSeconds": round(time.perf_counter() - t_start, 1)})
    print("끝:", out_dir)


if __name__ == "__main__":
    main()
