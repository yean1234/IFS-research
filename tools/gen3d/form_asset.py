"""G62 형태 메시 후보 생성기: 확정 텍스트 → 규칙 프롬프트 → (SDXL → 배경 제거 → TripoSG) → 결정적 후처리 → GLB +
form-asset.v0 사이드카(shared/schemas/form-asset.v0.json).

  <venv>/python tools/gen3d/generate.py --run <이름> --pipeline sdxl-triposg [--seed 0] [--ids …] [--repeat 2] [--no-cache]

- 프롬프트는 prompts.shape_prompt()(사전·규칙만, LLM 없음). 차단(no_shape_stated·excluded_category·untraceable_token)이면
  모델을 부르지 않는다(run.json의 modelCalls로 센다).
- 형태만 만든다: TripoSG는 정점 색·텍스처가 없다. GLB에는 회색 단일 머티리얼(금속도 0)만 붙인다(시스템 값).
- 결정적 후처리(POSTPROCESS_VERSION): 면 수 제한(quadric, FACE_LIMIT) → 경계 상자 중심을 x·z 원점 → 가장 긴 변 1.0 →
  바닥 y = 0(피벗 bottom-center). 주축 정렬은 하지 않는다(고유벡터 부호·순서가 결정적이지 않을 수 있어서).
- 캐시: 키 = sha256(프롬프트 텍스트 + 파이프라인 + 모델 리비전 + seed + 후처리 판). 같은 키면 다시 만들지 않는다.
  캐시와 산출물은 저장소 밖(OUT_ROOT, 기본 ../gen3d-out)에만 쓴다(원칙 6).
- 출력 관문: 6시점 무텍스처 렌더(점 찍기 렌더러, 결정적) → CLIP ViT-L/14 영점 분류(사람·얼굴·동물 대 물체).
  personLikeScore ≥ GATE_THRESHOLD면 person_like로 막는다. 문턱은 평가 전에 정한 값(0.5)이며 held-out으로 조정하지 않았다.
"""
from __future__ import annotations

import gc
import hashlib
import json
import shutil
import sys
import time
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (MODELS_ROOT, OUT_ROOT, VramPeak, assert_outside_repo, env_info, git_head,  # noqa: E402
                    read_json, sha256_file, write_json)

SCHEMA = "form-asset.v0"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "shared" / "schemas" / "form-asset.v0.json"
POSTPROCESS_VERSION = "g62-post/0.1.0"
FACE_LIMIT = 20000
GATE_THRESHOLD = 0.5
GATE_VIEWS = 6
GATE_VERSION = "g62-gate/0.2.0"        # 0.2.0: 여러 물체 검사(multi_object) 추가
# 여러 물체 검사: 후처리 뒤 연결 성분 중 전체 표면적의 MULTI_MIN_FRACTION 이상인 것이 2개 이상이면 막는다
# (gate_failed, blockDetail multi_object). 복수 명사를 말했으면(pluralStated) 적용하지 않는다.
# 문턱 0.05는 2차 실행 전에 정했고 그 결과를 보고 고치지 않는다.
MULTI_MIN_FRACTION = 0.05
CACHE_ROOT = OUT_ROOT / "form-assets"

IMG_REPO = "stabilityai/stable-diffusion-xl-base-1.0"
SHAPE_REPO = "VAST-AI/TripoSG"
SHAPE_REVISION = "2c1c516d22d58db486a058d98d31bb6177344e06"     # HF 커밋(2026-11-27 받음, MIT, 게이트 아님)
GATE_REPO = "openai/clip-vit-large-patch14"
U2NET = Path.home() / ".u2net" / "u2net.onnx"

CONFIG = {
    "image": {"num_inference_steps": 30, "guidance_scale": 7.0, "size": 1024},
    "rembg": {"model": "u2net", "note": "briaai/RMBG-1.4 대신(라이선스 조건, D8 3절). RGBA로 넘겨 TripoSG의 RMBG 경로를 건너뜀"},
    "shape": {"num_inference_steps": 50, "guidance_scale": 7.0, "use_flash_decoder": False,
              "dense_octree_depth": 8, "hierarchical_octree_depth": 8,
              "note": "flash 디코더는 diso(CUDA 확장, Windows 휠 없음)가 필요해 끔. 계층 옥트리 + skimage 마칭 큐브 경로"},
    "postprocess": {"version": POSTPROCESS_VERSION, "faceLimit": FACE_LIMIT, "longestEdge": 1.0,
                    "pivot": "bottom-center", "axisAlign": False,
                    "material": {"baseColorFactor": [0.75, 0.75, 0.75, 1.0], "metallicFactor": 0.0,
                                 "roughnessFactor": 0.8, "doubleSided": True}},
    "gate": {"version": GATE_VERSION, "views": GATE_VIEWS, "threshold": GATE_THRESHOLD, "renderSize": 224,
             "points": 200000, "multiObjectMinFraction": MULTI_MIN_FRACTION},
}

# CLIP 영점 분류 라벨(평가 전에 정함). person-like 쪽 확률 합 = personLikeScore.
GATE_PERSON = ["a person", "a human figure", "a human face", "a head with eyes and a mouth", "an animal",
               "an animal figurine", "a doll"]
GATE_OBJECT = ["an inanimate object", "an abstract shape", "a rock", "a geometric solid", "a household object",
               "a lump of clay", "a piece of cloth"]
GATE_TEMPLATE = "a gray clay 3D render of {}"


# ── 출처 ──────────────────────────────────────────────────────────────────────
def _hf_snapshot(repo: str, revision: str | None = None) -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(repo, revision=revision, local_files_only=True))


def _weights_sha(path: Path, exts=(".safetensors", ".onnx", ".bin", ".ckpt")) -> dict:
    """가중치 sha256. 큰 파일이라 (경로·크기·mtime) 기준으로 저장소 밖 캐시에 적어 두고 다시 쓴다."""
    memo_p = CACHE_ROOT / "provenance" / (hashlib.sha256(str(path).encode()).hexdigest()[:16] + ".json")
    memo = read_json(memo_p) if memo_p.exists() else {}
    out, changed = {}, False
    files = [path] if path.is_file() else sorted(f for f in path.rglob("*") if f.is_file() and f.suffix in exts)
    for f in files:
        rel = f.name if path.is_file() else f.relative_to(path).as_posix()
        st = f.stat()
        tag = f"{st.st_size}:{int(st.st_mtime)}"
        if memo.get(rel, {}).get("tag") != tag:
            memo[rel] = {"tag": tag, "sha256": sha256_file(f)}
            changed = True
        out[rel] = memo[rel]["sha256"]
    if changed:
        write_json(memo_p, memo)
    return out


def models_provenance() -> list[dict]:
    img = _hf_snapshot(IMG_REPO)
    shp = _hf_snapshot(SHAPE_REPO, SHAPE_REVISION)
    gate = _hf_snapshot(GATE_REPO)
    img_w = {k: v for k, v in _weights_sha(img).items()
             if not any(x in k for x in ("vae_1_0/", "fp16", "openvino", "flax", "onnx"))}
    return [
        {"name": "image", "repo": IMG_REPO, "revision": img.name, "weightsSha256": img_w,
         "license": "CreativeML Open RAIL++-M"},
        {"name": "rembg", "repo": "github.com/danielgatis/rembg u2net.onnx", "revision": None,
         "weightsSha256": _weights_sha(U2NET).get(U2NET.name), "license": "MIT (rembg) / Apache-2.0 (U^2-Net)"},
        {"name": "shape", "repo": SHAPE_REPO, "revision": shp.name, "weightsSha256": _weights_sha(shp),
         "codeCommit": git_head(MODELS_ROOT / "TripoSG"), "license": "MIT"},
        {"name": "gate", "repo": GATE_REPO, "revision": gate.name, "weightsSha256": _weights_sha(gate), "license": "MIT"},
    ]


def cache_key(prompt_text: str, pipeline: str, models: list[dict], seed: int, negative: str = "") -> str:
    """키 = sha256(프롬프트 + 부정 틀 + 파이프라인 + 모델 리비전 + seed + 후처리 판 + 관문 판)."""
    revs = ";".join(f"{m['name']}={m['repo']}@{m['revision'] or m['weightsSha256']}" for m in models)
    payload = "\n".join([prompt_text, negative, pipeline, revs, str(int(seed)), POSTPROCESS_VERSION, GATE_VERSION])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def component_stats(mesh, min_fraction: float = MULTI_MIN_FRACTION) -> dict:
    """연결 성분(면 인접)별 표면적 비율. significant = 비율이 min_fraction 이상인 성분 수. 난수 없음."""
    parts = mesh.split(only_watertight=False)
    total = float(sum(p.area for p in parts)) or 1.0
    fr = sorted((float(p.area) / total for p in parts), reverse=True)
    return {"components": len(parts), "significant": sum(1 for f in fr if f >= min_fraction),
            "topFractions": [round(f, 4) for f in fr[:5]], "minFraction": min_fraction}


def decide_multi_object(stats: dict, plural_stated: bool) -> dict:
    """여러 물체 판정. 복수 명사를 말했으면 적용하지 않는다(말한 것이 덮어씀)."""
    applied = not plural_stated
    return {**stats, "applied": applied, "blocked": bool(applied and stats["significant"] >= 2)}


# ── 결정적 후처리 ───────────────────────────────────────────────────────────────
def postprocess(vertices: np.ndarray, faces: np.ndarray, face_limit: int = FACE_LIMIT):
    """면 수 제한 → 중심 맞춤 → 가장 긴 변 1.0 → 바닥 y = 0. 같은 입력 배열 → 같은 출력 배열(난수 없음).

    돌려주는 것: (trimesh.Trimesh, normalization dict). 주축 정렬은 하지 않는다.
    """
    import trimesh

    m = trimesh.Trimesh(np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int64), process=False)
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    faces_before = int(len(m.faces))
    if faces_before > face_limit:
        m = _decimate(m, face_limit)
    if m.is_watertight and m.volume < 0:          # 면 감기 방향만 맞춘다(결정적)
        m.invert()
    lo, hi = m.bounds
    ext = hi - lo
    longest = float(ext.max())
    if not np.isfinite(longest) or longest <= 0:
        raise ValueError("빈 메시 또는 퇴화한 경계 상자")
    scale = 1.0 / longest
    pivot = np.array([(lo[0] + hi[0]) / 2.0, lo[1], (lo[2] + hi[2]) / 2.0])
    v = ((m.vertices - pivot) * scale).astype(np.float32)
    out = trimesh.Trimesh(v, np.asarray(m.faces, dtype=np.int32), process=False)
    lo2, hi2 = out.bounds
    norm = {"longestEdge": 1.0, "pivot": "bottom-center",
            "bboxBefore": {"min": [round(float(x), 6) for x in lo], "max": [round(float(x), 6) for x in hi]},
            "bboxAfter": {"min": [round(float(x), 6) for x in lo2], "max": [round(float(x), 6) for x in hi2]},
            "scaleApplied": round(scale, 9), "axisAligned": False,
            "facesBefore": faces_before, "facesAfter": int(len(out.faces)), "faceLimit": int(face_limit)}
    return out, norm


def _decimate(m, face_limit: int):
    import pymeshlab
    import trimesh

    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=np.asarray(m.vertices, dtype=np.float64),
                               face_matrix=np.asarray(m.faces, dtype=np.int32)))
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=int(face_limit), preservenormal=True,
                                                 preserveboundary=True, optimalplacement=True)
    cm = ms.current_mesh()
    return trimesh.Trimesh(cm.vertex_matrix(), cm.face_matrix(), process=False)


def axis_ratios(mesh) -> list[float]:
    ext = mesh.bounds[1] - mesh.bounds[0]
    return [round(float(x / ext.max()), 4) for x in ext]


def export_glb(mesh, out: Path) -> str:
    """무텍스처 GLB(y-up). 회색 단일 머티리얼(금속도 0)을 붙인다. 바이트가 결정적이도록 trimesh 기본 내보내기만 쓴다."""
    from pygltflib import GLTF2, Material, PbrMetallicRoughness

    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out, file_type="glb")
    mat = CONFIG["postprocess"]["material"]
    g = GLTF2().load_binary(str(out))
    g.materials = [Material(name="g62_shape_only", doubleSided=mat["doubleSided"],
                            pbrMetallicRoughness=PbrMetallicRoughness(baseColorFactor=mat["baseColorFactor"],
                                                                      metallicFactor=mat["metallicFactor"],
                                                                      roughnessFactor=mat["roughnessFactor"]))]
    for mm in g.meshes:
        for p in mm.primitives:
            p.material = 0
    g.save_binary(str(out))
    return sha256_file(out)


# ── 6시점 무텍스처 렌더(점 찍기, 결정적) ─────────────────────────────────────────────
VIEWS = [(0, 15), (60, 15), (120, 15), (180, 15), (270, 15), (30, 70)]     # (방위각, 고도) 도


def render_views(mesh, size: int = 224, n_points: int = 200000, views=VIEWS) -> list:
    """표면 점(seed 0 고정 표본)을 정사영해 z-버퍼로 찍고 법선으로 양면 램버트 음영. 흰 배경 회색 물체."""
    import trimesh
    from PIL import Image

    pts, fidx = trimesh.sample.sample_surface(mesh, n_points, seed=0)
    nrm = mesh.face_normals[fidx]
    center = (mesh.bounds[0] + mesh.bounds[1]) / 2.0
    pts = pts - center
    radius = float(np.linalg.norm(pts, axis=1).max()) or 1.0
    light = np.array([0.4, 0.6, 1.0])
    light /= np.linalg.norm(light)
    out = []
    for az, el in views:
        a, e = np.radians(az), np.radians(el)
        ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
        r = rx @ ry
        p = pts @ r.T
        n = nrm @ r.T
        px = np.clip(((p[:, 0] / radius) * 0.48 + 0.5) * size, 0, size - 1).astype(np.int64)
        py = np.clip((0.5 - (p[:, 1] / radius) * 0.48) * size, 0, size - 1).astype(np.int64)
        pix = py * size + px
        order = np.lexsort((-p[:, 2], pix))               # 픽셀마다 카메라에 가장 가까운 점
        pix_s = pix[order]
        first = np.ones(len(pix_s), dtype=bool)
        first[1:] = pix_s[1:] != pix_s[:-1]
        sel = order[first]
        shade = 0.25 + 0.75 * np.abs(n[sel] @ light)
        img = np.full(size * size, 255.0)
        img[pix[sel]] = 40 + 200 * shade
        im = img.reshape(size, size)
        # 점 사이 빈칸 메우기: 3×3 최소값(물체가 배경보다 어두움)
        pad = np.pad(im, 1, mode="edge")
        stack = np.stack([pad[dy:dy + size, dx:dx + size] for dy in range(3) for dx in range(3)])
        im = np.where(im >= 255.0, stack.min(axis=0), im)
        out.append(Image.fromarray(np.clip(im, 0, 255).astype(np.uint8)).convert("RGB"))
    return out


# ── 모델 래퍼 ──────────────────────────────────────────────────────────────────
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


def _free():
    import torch

    gc.collect()
    torch.cuda.empty_cache()


class ImageStage:
    def __init__(self):
        import torch
        from diffusers import StableDiffusionXLPipeline

        self.pipe = StableDiffusionXLPipeline.from_pretrained(IMG_REPO, torch_dtype=torch.float16, local_files_only=True,
                                                              use_safetensors=True).to("cuda")
        self.pipe.set_progress_bar_config(disable=True)

    def make(self, prompt: str, negative: str, seed: int, out_png: Path) -> dict:
        import torch

        c = CONFIG["image"]
        set_determinism(seed)
        g = torch.Generator("cuda").manual_seed(seed)
        t0 = time.perf_counter()
        with VramPeak() as vp:
            im = self.pipe(prompt=prompt, negative_prompt=negative, num_inference_steps=c["num_inference_steps"],
                           guidance_scale=c["guidance_scale"], width=c["size"], height=c["size"], generator=g).images[0]
        out_png.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png)
        return {"seconds": round(time.perf_counter() - t0, 2), "vramReservedGiB": vp.reserved_gib,
                "imageSha256": sha256_file(out_png)}


def _install_diso_stub():
    """TripoSG inference_utils는 맨 위에서 diso(CUDA 확장)를 import한다. flash 디코더를 끄면 쓰지 않으므로 빈 모듈로 막는다."""
    if "diso" in sys.modules:
        return
    mod = types.ModuleType("diso")

    class DiffDMC:  # noqa: D401
        def __init__(self, *a, **k):
            raise RuntimeError("diso가 설치되지 않음 — use_flash_decoder=False로만 돈다")

    mod.DiffDMC = DiffDMC
    sys.modules["diso"] = mod


class ShapeStage:
    def __init__(self):
        import rembg
        import torch

        _install_diso_stub()
        code = MODELS_ROOT / "TripoSG"
        for p in (code, code / "scripts"):
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
        from triposg.pipelines.pipeline_triposg import TripoSGPipeline

        self.pipe = TripoSGPipeline.from_pretrained(str(_hf_snapshot(SHAPE_REPO, SHAPE_REVISION))).to("cuda", torch.float16)
        self.pipe.set_progress_bar_config(disable=True)
        self.rembg = rembg.new_session("u2net")

    def make(self, png: Path, seed: int, work: Path) -> tuple[np.ndarray, np.ndarray, dict]:
        import rembg
        import torch
        from image_process import prepare_image
        from PIL import Image

        c = CONFIG["shape"]
        t0 = time.perf_counter()
        rgba = rembg.remove(Image.open(png).convert("RGB"), session=self.rembg)
        rgba_p = work / (png.stem + "_rgba.png")
        rgba_p.parent.mkdir(parents=True, exist_ok=True)
        rgba.save(rgba_p)
        img = prepare_image(str(rgba_p), bg_color=np.array([1.0, 1.0, 1.0]), rmbg_net=None)
        t1 = time.perf_counter()
        set_determinism(seed)
        with VramPeak() as vp, torch.no_grad():
            out = self.pipe(image=img, generator=torch.Generator(device="cuda").manual_seed(seed),
                            num_inference_steps=c["num_inference_steps"], guidance_scale=c["guidance_scale"],
                            use_flash_decoder=c["use_flash_decoder"], dense_octree_depth=c["dense_octree_depth"],
                            hierarchical_octree_depth=c["hierarchical_octree_depth"]).samples[0]
        t2 = time.perf_counter()
        v, f = np.asarray(out[0], dtype=np.float32), np.ascontiguousarray(out[1])
        return v, f, {"removeBackground": round(t1 - t0, 2), "shape": round(t2 - t1, 2),
                      "vramReservedGiB": vp.reserved_gib}


class GateStage:
    def __init__(self):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        p = str(_hf_snapshot(GATE_REPO))
        self.model = CLIPModel.from_pretrained(p, torch_dtype=torch.float32).to("cuda").eval()
        self.proc = CLIPProcessor.from_pretrained(p)
        labels = [GATE_TEMPLATE.format(x) for x in GATE_PERSON + GATE_OBJECT]
        self.labels = GATE_PERSON + GATE_OBJECT
        self.label_emb = self._text(labels)

    def _text(self, texts):
        import torch

        with torch.no_grad():
            t = self.proc(text=texts, return_tensors="pt", padding=True, truncation=True).to("cuda")
            e = self.model.get_text_features(**t)
        return e / e.norm(dim=-1, keepdim=True)

    def judge(self, images, prompt_phrase: str | None) -> dict:
        import torch

        with torch.no_grad():
            px = self.proc(images=images, return_tensors="pt").to("cuda")
            ie = self.model.get_image_features(**px)
            ie = ie / ie.norm(dim=-1, keepdim=True)
            logits = self.model.logit_scale.exp() * ie @ self.label_emb.T
            prob = logits.softmax(dim=-1).cpu().numpy()
        n_p = len(GATE_PERSON)
        person = prob[:, :n_p].sum(axis=1)
        score = float(person.max())
        res = {"personLikeScore": round(score, 4), "passed": bool(score < GATE_THRESHOLD),
               "threshold": GATE_THRESHOLD, "views": len(images),
               "labelScores": {lab: round(float(prob[:, k].max()), 4) for k, lab in enumerate(self.labels)},
               "matchScore": None}
        if prompt_phrase:
            te = self._text([prompt_phrase])
            res["matchScore"] = round(float((ie @ te.T).mean().item()), 4)
        return res


# ── 실행 ──────────────────────────────────────────────────────────────────────
def _phrase(prompt_text: str) -> str:
    """일치 점수용: 틀 꼬리말을 뺀 'a single …' 부분."""
    return prompt_text.split(",")[0] if prompt_text else ""


def _sidecar(row_prompt: dict, *, asset_id: str, key: str, status: str, block: str | None, block_detail,
             glb_name, glb_sha, pipeline: str, models, seed: int, norm, ratios, gate, timing, cache_hit, error=None):
    return {
        "schema": SCHEMA, "assetId": asset_id, "cacheKey": key, "status": status, "blockReason": block,
        "blockDetail": block_detail, "error": error, "glb": glb_name, "glbSha256": glb_sha, "pipeline": pipeline,
        "postprocessVersion": POSTPROCESS_VERSION, "models": models, "seed": seed,
        "prompt": {"text": row_prompt["text"], "negativeText": row_prompt["negativeText"],
                   "lexiconVersion": row_prompt["lexiconVersion"], "builderVersion": row_prompt["builderVersion"],
                   "tokens": row_prompt["tokens"], "dropped": row_prompt["dropped"]},
        "sourceTextSha256": row_prompt["sourceTextSha256"],
        "normalization": norm,
        "covariates": {"axisRatios": ratios, "thinRisk": bool(row_prompt["thinRisk"]),
                       "familiarObjectStated": bool(row_prompt["familiarObjectStated"]),
                       "pluralStated": bool(row_prompt.get("pluralStated"))},
        "gate": gate or {"personLikeScore": None, "passed": None},
        "timing": timing, "cacheHit": cache_hit,
    }


def _validator():
    try:
        import jsonschema
    except ImportError:
        return None
    return jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def run(rows: list[dict], run_name: str, pipeline: str = "sdxl-triposg", seed: int = 0, repeat: int = 1,
        no_cache: bool = False) -> Path:
    import prompts

    if pipeline != "sdxl-triposg":
        raise SystemExit("form-asset 계약은 지금 sdxl-triposg만 구현함")
    out_dir = assert_outside_repo(OUT_ROOT / run_name / f"g62-{pipeline}")
    cache = assert_outside_repo(CACHE_ROOT / pipeline)
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()
    validator = _validator()

    # 1) 규칙 프롬프트(모델 없음)
    t0 = time.perf_counter()
    pr = {r["id"]: prompts.shape_prompt(r["text"]) for r in rows}
    prompt_seconds = round(time.perf_counter() - t0, 2)
    models = models_provenance()
    keys = {sid: cache_key(p["text"], pipeline, models, seed, p["negativeText"])
            for sid, p in pr.items() if p["status"] == "ok"}
    todo = sorted({k for k in keys.values() if no_cache or not (cache / f"{k[:16]}.gen.json").exists()})
    calls = {"image": 0, "shape": 0, "gate": 0}
    called_ids = sorted(sid for sid, k in keys.items() if k in todo)
    prev_sha = {k: read_json(cache / f"{k[:16]}.gen.json").get("glbSha256")
                for k in todo if (cache / f"{k[:16]}.gen.json").exists()}
    key_prompt = {k: pr[sid] for sid, k in keys.items()}
    rep_sha: dict[str, list] = {k: [] for k in todo}
    gens: dict[str, dict] = {}

    for rep in range(max(1, repeat)):
        tag = "" if rep == 0 else f"_rep{rep}"
        # 2) 이미지 단계(모든 키) → SDXL 내림
        img_info = {}
        if todo:
            st = ImageStage()
            for k in todo:
                p = key_prompt[k]
                img_info[k] = st.make(p["text"], p["negativeText"], seed, cache / "images" / f"{k[:16]}{tag}.png")
                calls["image"] += 1
                print("image", k[:16], rep, img_info[k]["seconds"], flush=True)
            del st
            _free()
        # 3) 형태 단계 → 후처리 → GLB
        meshes = {}
        if todo:
            st = ShapeStage()
            for k in todo:
                info = {"image": img_info[k]["seconds"]}
                try:
                    v, f, sinfo = st.make(cache / "images" / f"{k[:16]}{tag}.png", seed, cache / "work")
                    calls["shape"] += 1
                    tp = time.perf_counter()
                    mesh, norm = postprocess(v, f)
                    glb = cache / f"{k[:16]}{tag}.glb"
                    sha = export_glb(mesh, glb)
                    info.update(removeBackground=sinfo["removeBackground"], shape=sinfo["shape"],
                                postprocess=round(time.perf_counter() - tp, 2))
                    meshes[k] = mesh
                    rep_sha[k].append(sha)
                    gens.setdefault(k, {}).update(
                        {f"glbSha256{tag}": sha, "imageSha256" + tag: img_info[k]["imageSha256"]})
                    if rep == 0:
                        gens[k].update(status="ok", glbSha256=sha, normalization=norm, axisRatios=axis_ratios(mesh),
                                       timing={**info, "vramImageGiB": img_info[k]["vramReservedGiB"],
                                               "vramShapeGiB": sinfo["vramReservedGiB"]})
                    print("shape", k[:16], rep, info, norm["facesBefore"], "->", norm["facesAfter"], flush=True)
                except Exception as ex:  # noqa: BLE001 — 실패도 기록하고 다음으로
                    rep_sha[k].append(None)
                    if rep == 0:
                        gens[k] = {"status": "failed", "error": f"{type(ex).__name__}: {ex}"[:300], "glbSha256": None,
                                   "normalization": None, "axisRatios": None, "timing": info}
                    print("FAILED", k[:16], ex, flush=True)
            del st
            _free()
        # 4) 출력 관문(첫 회만; 반복은 결정성 확인용)
        if rep == 0 and meshes:
            gs = GateStage()
            rdir = cache / "renders"
            rdir.mkdir(parents=True, exist_ok=True)
            for k, mesh in meshes.items():
                tg = time.perf_counter()
                try:
                    views = render_views(mesh, size=CONFIG["gate"]["renderSize"], n_points=CONFIG["gate"]["points"])
                    for vi, im in enumerate(views):
                        im.save(rdir / f"{k[:16]}_v{vi}.png")
                    g = gs.judge(views, _phrase(key_prompt[k]["text"]))
                    g["model"] = f"{GATE_REPO}@{models[3]['revision']}"
                    gens[k]["gate"] = g
                    gens[k]["components"] = component_stats(mesh)
                except Exception as ex:  # noqa: BLE001 — 관문을 못 돌리면 막는다(gate_failed, fail closed)
                    gens[k]["gate"] = None
                    gens[k]["gateError"] = f"{type(ex).__name__}: {ex}"[:300]
                calls["gate"] += 1
                gens[k]["timing"]["gate"] = round(time.perf_counter() - tg, 2)
            del gs
            _free()
        for k in todo:
            if rep == 0:
                gens[k]["cacheKey"] = k
                write_json(cache / f"{k[:16]}.gen.json", gens[k])

    # 5) 사이드카(문장마다). 같은 키는 GLB 하나를 함께 쓴다.
    index, problems = {}, []
    for r in rows:
        sid, p = r["id"], pr[r["id"]]
        if p["status"] != "ok":
            key = cache_key(p["text"] + "\n" + p["sourceTextSha256"], pipeline, models, seed, p["negativeText"])
            sc = _sidecar(p, asset_id=key[:16], key=key, status="blocked", block=p["blockReason"],
                          block_detail=p["blockDetail"], glb_name=None, glb_sha=None, pipeline=pipeline, models=models,
                          seed=seed, norm=None, ratios=None, gate=None, timing=None, cache_hit=False)
        else:
            key = keys[sid]
            g = read_json(cache / f"{key[:16]}.gen.json")
            gate = dict(g["gate"]) if g.get("gate") else None
            status, block, detail, glb_name = g["status"], None, None, None
            if status == "ok" and (gate is None or g.get("components") is None):
                status, block, detail = "blocked", "gate_failed", "gate_not_evaluated"
            elif status == "ok" and not gate["passed"]:
                status, block = "blocked", "person_like"
            if gate is not None and g.get("components") is not None:
                multi = decide_multi_object(g["components"], bool(p.get("pluralStated")))
                gate["multiObject"] = multi
                if status == "ok" and multi["blocked"]:
                    gate["passed"] = False
                    status, block, detail = "blocked", "gate_failed", "multi_object"
            if status == "ok":
                glb_name = f"{key[:16]}.glb"
                shutil.copyfile(cache / glb_name, out_dir / "assets" / glb_name)
            sc = _sidecar(p, asset_id=key[:16], key=key, status=status, block=block, block_detail=detail,
                          glb_name=glb_name, glb_sha=g.get("glbSha256") if status == "ok" else None, pipeline=pipeline,
                          models=models, seed=seed, norm=g.get("normalization"), ratios=g.get("axisRatios"),
                          gate=gate, timing=g.get("timing"), cache_hit=key not in todo, error=g.get("error"))
        if validator is not None:
            errs = [e.message for e in validator.iter_errors(sc)]
            if errs:
                problems.append({"id": sid, "errors": errs[:3]})
        write_json(out_dir / "assets" / f"{sid}.form-asset.json", sc)
        index[sid] = {"assetId": sc["assetId"], "status": sc["status"], "blockReason": sc["blockReason"],
                      "glb": sc["glb"], "glbSha256": sc["glbSha256"], "prompt": p["text"],
                      "modelCalled": sid in called_ids}

    det = {}
    for k, shas in rep_sha.items():
        det[k[:16]] = {"sameProcessIdentical": (len(set(shas)) == 1 and shas[0] is not None) if len(shas) > 1 else None,
                       "previousProcessSha": prev_sha.get(k), "thisSha": shas[0] if shas else None,
                       "crossProcessIdentical": (prev_sha[k] == shas[0]) if k in prev_sha else None}
    write_json(out_dir / "run.json", {
        "pipeline": pipeline, "seed": seed, "repeat": repeat, "noCache": no_cache, "ids": [r["id"] for r in rows],
        "env": env_info(), "models": models, "config": CONFIG, "gateLabels": {"person": GATE_PERSON, "object": GATE_OBJECT,
                                                                              "template": GATE_TEMPLATE},
        "promptSeconds": prompt_seconds, "modelCalls": calls, "idsWithModelCall": called_ids,
        "generatedKeys": [k[:16] for k in todo], "determinism": det, "schemaProblems": problems,
        "index": index, "totalSeconds": round(time.perf_counter() - t_start, 1)})
    print("끝:", out_dir, "모델 호출", calls, "스키마 문제", len(problems))
    return out_dir
