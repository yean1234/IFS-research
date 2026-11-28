"""G76 이미지 모델 실측(측정 전용). 실험 경로 코드(chatbot/, 기존 tools/gen3d 함수)는 고치지 않고 불러 쓰기만 한다.

조사 research_notes/이미지 모델 교체 조사/report.md 3.2절의 실측 항목을 이 PC(RTX 5080 16 GB)에서 잰다.
모델 4개: SDXL base 1.0(G75 현행 설정), Z-Image(base), FLUX.2 klein 4B 증류판, klein 4B Base.
프롬프트는 G75 그대로(prompts.shape_prompt → image_pick_prompt, 무채색 화풍 고정 문구와 negative). 합성 대사만 쓴다.

  <venv>/python tools/gen3d/bench_image_models.py prompts
  <venv>/python tools/gen3d/bench_image_models.py gen --model sdxl|zimage|klein|klein-base
  <venv>/python tools/gen3d/bench_image_models.py det --model …       # 프로세스를 새로 띄워 같은 seed 재생성 → sha256 비교
  <venv>/python tools/gen3d/bench_image_models.py metrics [--models …]   # rembg(u2net) 마스크·채도·IoU·CLIP 관문
  <venv>/python tools/gen3d/bench_image_models.py mesh --model …         # 8 프롬프트 × seed 0 → TripoSG
  <venv>/python tools/gen3d/bench_image_models.py sheets                 # 시트 PNG → docs/validation/run-g76-image-model-bench/
  <venv>/python tools/gen3d/bench_image_models.py report                 # 원자료 JSON(bench.json) + 표

개별 그림·마스크·메시는 저장소 밖 OUT_ROOT/g76-image-bench/에 둔다(원칙 6). 프롬프트 고쳐 쓰기(PE·caption upsampling)는
어느 모델에서도 부르지 않는다(diffusers 파이프라인 인자에 없음을 기록). Generator는 CPU(diffusers 재현성 권고).
"""
from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_ROOT, REPO, assert_outside_repo, env_info, read_json, sha256_file, write_json  # noqa: E402

BENCH_VERSION = "g76-image-bench/0.1.0"
RUN = assert_outside_repo(OUT_ROOT / "g76-image-bench")
DOC = REPO / "docs" / "validation" / "run-g76-image-model-bench"
SEEDS = (0, 1, 2)                      # G75: on_none_seed(0) + 3r + 0·1·2, 첫 회차
SIZE = 1024

# 합성 대사(참여자 데이터 아님). A = 추상·드문 사물(11개), F = 익숙한 사물(9개). 문장은 형태 사전(shape_prompt_en.v0)의
# 낱말만 쓰고, 측정 전에 정했다.
SENTENCES = [
    ("A01", "엉킨 매듭이에요.", "abstract"),
    ("A02", "뾰족한 가시가 있어요.", "abstract"),
    ("A03", "울퉁불퉁한 덩어리예요.", "abstract"),
    ("A04", "둥근 고리예요.", "abstract"),
    ("A05", "뭉툭한 뭉치예요.", "abstract"),
    ("A06", "두툼한 혹이에요.", "abstract"),
    ("A07", "오돌토돌한 돌기가 있어요.", "abstract"),
    ("A08", "얇은 막이에요.", "abstract"),
    ("A09", "갈라진 껍데기예요.", "abstract"),
    ("A10", "꼬인 띠예요.", "abstract"),
    ("A11", "구불구불한 뿔이에요.", "abstract"),
    ("F01", "동그란 공이에요.", "familiar"),
    ("F02", "네모난 상자예요.", "familiar"),
    ("F03", "납작한 돌멩이예요.", "familiar"),
    ("F04", "찌그러진 컵이에요.", "familiar"),
    ("F05", "달걀이에요.", "familiar"),
    ("F06", "깃털이에요.", "familiar"),
    ("F07", "하트예요.", "familiar"),
    ("F08", "풍선이에요.", "familiar"),
    ("F09", "구겨진 종이예요.", "familiar"),
]
COMPARE_IDS = ["A01", "A02", "A03", "A07", "A10", "F01", "F04", "F06"]   # 비교 시트·3D 하류(측정 전에 정함)
DET_CASES = [("A01", 0), ("A03", 1), ("F01", 2)]                         # 결정성: 새 프로세스에서 다시 만들 것

# 단계·guidance: SDXL은 form_asset.CONFIG["image"](G75 현행), 나머지는 모델 카드의 diffusers 예제 값.
MODELS = {
    "sdxl": {"repo": "stabilityai/stable-diffusion-xl-base-1.0", "revision": "462165984030d82259a11f4367a4eed129e94a7b", "cls": "StableDiffusionXLPipeline", "dtype": "float16",
             "steps": 30, "guidance": 7.0, "extra": {}, "negative": "string",
             "source": "tools/gen3d/form_asset.py CONFIG['image'](G75 현행 30/7.0, fp16)", "license": "CreativeML Open RAIL++-M"},
    "zimage": {"repo": "Tongyi-MAI/Z-Image", "revision": "04cc4abb7c5069926f75c9bfde9ef43d49423021", "cls": "ZImagePipeline", "dtype": "bfloat16",
               "steps": 50, "guidance": 4.0, "extra": {"cfg_normalization": False}, "negative": "string",
               "source": "모델 카드 diffusers 예제(50단계, guidance 4, cfg_normalization False, bf16). 카드 권장 28–50 / 3.0–5.0",
               "license": "Apache-2.0"},
    "klein": {"repo": "black-forest-labs/FLUX.2-klein-4B", "revision": "e7b7dc27f91deacad38e78976d1f2b499d76a294", "cls": "Flux2KleinPipeline", "dtype": "bfloat16",
              "steps": 4, "guidance": 1.0, "extra": {}, "negative": "none",
              "source": "모델 카드 diffusers 예제(4단계, guidance 1.0, bf16). model_index is_distilled=true → CFG 꺼짐, negative 안 씀",
              "license": "Apache-2.0"},
    "klein-base": {"repo": "black-forest-labs/FLUX.2-klein-base-4B", "revision": "a3b4f4849157f664bdbc776fd7453c2783562f4d", "cls": "Flux2KleinPipeline", "dtype": "bfloat16",
                   "steps": 50, "guidance": 4.0, "extra": {}, "negative": "embeds",
                   "source": "모델 카드 diffusers 예제(50단계, guidance 4.0, bf16). negative는 encode_prompt로 만든 negative_prompt_embeds",
                   "license": "Apache-2.0"},
}
FULL_GPU_LIMIT_GIB = 14.0          # 가중치 합이 이보다 크면 전부 GPU에 올리지 않고 enable_model_cpu_offload(조사 3.2절 VRAM 기준)

# 자동 지표 정의(측정 전에 정함)
ALPHA_THRESHOLD = 128              # rembg 마스크(0–255) ≥ 128 → 전경
COMPONENT_MIN_FRACTION = 0.01      # 전경 넓이의 1% 이상인 8-연결 성분만 센다(점 잡티 제외). 원래 개수도 따로 적음
FG_RANGE = (0.10, 0.70)
BORDER_PX = 2                      # 바깥 2픽셀 띠에 전경이 있으면 테두리에 닿음
SAT_LOW = 0.15                     # 조사 3.2절 화풍 기준
IOU_HIGH = 0.90                    # 같은 프롬프트 3장 사이 최대 IoU < 0.9이면 다양함


# ── 프롬프트 ──────────────────────────────────────────────────────────────────
def cmd_prompts(_a):
    import prompts

    rows = []
    for pid, text, kind in SENTENCES:
        p = prompts.image_pick_prompt(prompts.shape_prompt(text))
        if p["status"] != "ok":
            raise SystemExit(f"{pid}: 프롬프트가 막힘 {p['blockReason']} {p['blockDetail']}")
        content = [t["en"] for t in p["tokens"] if t["slot"] != "template"]
        rows.append({"id": pid, "kind": kind, "text": text, "content": content, "prompt": p["text"],
                     "negative": p["negativeText"], "builderVersion": p["builderVersion"],
                     "lexiconVersion": p["lexiconVersion"], "imageStyleVersion": p["imageStyleVersion"],
                     "pluralStated": p["pluralStated"]})
        print(pid, "|", " ".join(content), "|", p["text"][:90], flush=True)
    write_json(RUN / "prompts.json", {"version": BENCH_VERSION, "rows": rows})


def load_prompts() -> list[dict]:
    return read_json(RUN / "prompts.json")["rows"]


# ── 모델 ─────────────────────────────────────────────────────────────────────
def snapshot(repo: str, revision: str) -> Path:
    """HF 캐시의 고정 리비전(커밋 해시) 스냅숏. 내려받지 않는다."""
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(repo, revision=revision, local_files_only=True))


def module_gib(pipe) -> float:
    """올린 dtype 기준 가중치 크기(GiB): 파이프라인 구성 요소(nn.Module)의 매개변수·버퍼 바이트 합."""
    import torch

    tot = 0
    for _n, c in pipe.components.items():
        if isinstance(c, torch.nn.Module):
            tot += sum(t.numel() * t.element_size() for t in list(c.parameters()) + list(c.buffers()))
    return round(tot / 2**30, 2)


class Gen:
    def __init__(self, name: str, offload: str = "auto"):
        import diffusers
        import torch
        from form_asset import set_determinism  # noqa: F401  (기존 함수 그대로)

        self.name, self.m = name, MODELS[name]
        self.path = snapshot(self.m["repo"], self.m["revision"])
        self.revision = self.path.name
        cls = getattr(diffusers, self.m["cls"])
        dtype = getattr(torch, self.m["dtype"])
        kw = {"torch_dtype": dtype, "local_files_only": True}
        if name == "sdxl":
            kw["use_safetensors"] = True
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        self.pipe = cls.from_pretrained(str(self.path), **kw)
        self.weights_gib = module_gib(self.pipe)
        self.offload = self.weights_gib > FULL_GPU_LIMIT_GIB if offload == "auto" else offload == "on"
        if self.offload:
            self.pipe.enable_model_cpu_offload()
        else:
            self.pipe.to("cuda")
        torch.cuda.synchronize()
        self.load_s = round(time.perf_counter() - t0, 2)
        self.load_peak_gib = round(torch.cuda.max_memory_allocated() / 2**30, 3)
        self.pipe.set_progress_bar_config(disable=True)
        self._neg_cache: dict[str, object] = {}

    def config(self) -> dict:
        m = self.m
        return {"model": self.name, "repo": m["repo"], "revision": self.revision, "pipelineClass": m["cls"],
                "dtype": m["dtype"], "steps": m["steps"], "guidance": m["guidance"], "extra": m["extra"],
                "negative": m["negative"], "source": m["source"], "license": m["license"], "size": SIZE,
                "generator": "cpu", "offload": self.offload, "weightsGiB": self.weights_gib,
                "fullGpuLimitGiB": FULL_GPU_LIMIT_GIB, "attention": "SDPA(기본), flash·torch.compile 끔",
                "promptRewrite": "없음(파이프라인에 PE·caption upsampling 인자 없음, 부르지 않음)",
                "determinismFlags": "form_asset.set_determinism: cudnn deterministic, benchmark off, TF32 off"}

    def make(self, prompt: str, negative: str, seed: int, out_png: Path) -> dict:
        import torch
        from form_asset import set_determinism

        m = self.m
        set_determinism(seed)
        g = torch.Generator("cpu").manual_seed(seed)
        kw = {"prompt": prompt, "num_inference_steps": m["steps"], "guidance_scale": m["guidance"],
              "width": SIZE, "height": SIZE, "generator": g, **m["extra"]}
        t0 = time.perf_counter()
        if m["negative"] == "string":
            kw["negative_prompt"] = negative
        elif m["negative"] == "embeds":
            if negative not in self._neg_cache:
                with torch.no_grad():
                    emb, _ids = self.pipe.encode_prompt(prompt=negative, device=self.pipe._execution_device)
                self._neg_cache = {negative: emb}       # 프롬프트마다 다를 수 있어 하나만 둔다
            kw["negative_prompt_embeds"] = self._neg_cache[negative]
        im = self.pipe(**kw).images[0]
        torch.cuda.synchronize()
        sec = time.perf_counter() - t0
        out_png.parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png)
        return {"seconds": round(sec, 3), "sha256": sha256_file(out_png)}


def _free():
    import torch

    gc.collect()
    torch.cuda.empty_cache()


def cmd_gen(a):
    import torch

    rows = load_prompts()
    if a.ids:
        rows = [r for r in rows if r["id"] in a.ids.split(",")]
    out = RUN / a.model
    g = Gen(a.model, a.offload)
    print(a.model, "load", g.load_s, "s offload", g.offload, "weights", g.weights_gib, flush=True)
    torch.cuda.reset_peak_memory_stats()
    images, triples = [], []
    t_all = time.perf_counter()
    for r in rows:
        tt = 0.0
        for s in SEEDS:
            info = g.make(r["prompt"], r["negative"], s, out / f"{r['id']}-s{s}.png")
            tt += info["seconds"]
            images.append({"id": r["id"], "seed": s, "file": f"{a.model}/{r['id']}-s{s}.png", **info})
        triples.append({"id": r["id"], "seconds": round(tt, 3)})
        print(a.model, r["id"], round(tt, 2), flush=True)
    peak = round(torch.cuda.max_memory_allocated() / 2**30, 3)
    peak_res = round(torch.cuda.max_memory_reserved() / 2**30, 3)
    ts = [t["seconds"] for t in triples]
    res = {"version": BENCH_VERSION, "config": g.config(), "loadSeconds": g.load_s, "loadPeakAllocGiB": g.load_peak_gib,
           "genPeakAllocGiB": peak, "genPeakReservedGiB": peak_res, "images": images, "triples": triples,
           "triple": {"firstSeconds": ts[0] if ts else None,
                      "medianAfterFirst": round(statistics.median(ts[1:]), 2) if len(ts) > 1 else None,
                      "median2to4": round(statistics.median(ts[1:4]), 2) if len(ts) > 3 else None,
                      "n": len(ts) - 1},
           "totalSeconds": round(time.perf_counter() - t_all, 1), "env": env_info()}
    write_json(out / "gen.json", res)
    print(a.model, "done peak", peak, "median3", res["triple"]["medianAfterFirst"], flush=True)


def cmd_det(a):
    """새 프로세스에서 gen과 같은 설정으로 DET_CASES를 다시 만들어 PNG sha256을 비교한다."""
    from PIL import Image

    rows = {r["id"]: r for r in load_prompts()}
    gen = read_json(RUN / a.model / "gen.json")
    ref = {(i["id"], i["seed"]): i for i in gen["images"]}
    g = Gen(a.model, "on" if gen["config"]["offload"] else "off")
    tag = a.tag or "det"
    out = []
    for pid, s in DET_CASES:
        r = rows[pid]
        p = RUN / a.model / tag / f"{pid}-s{s}.png"
        info = g.make(r["prompt"], r["negative"], s, p)
        same = info["sha256"] == ref[(pid, s)]["sha256"]
        maxdiff = 0
        if not same:
            x = np.asarray(Image.open(p).convert("RGB"), dtype=np.int16)
            y = np.asarray(Image.open(RUN / ref[(pid, s)]["file"]).convert("RGB"), dtype=np.int16)
            maxdiff = int(np.abs(x - y).max())
        out.append({"id": pid, "seed": s, "sha256": info["sha256"], "refSha256": ref[(pid, s)]["sha256"],
                    "identical": same, "maxPixelDiff": maxdiff})
        print(a.model, pid, s, "identical" if same else f"DIFF max {maxdiff}", flush=True)
    write_json(RUN / a.model / f"{tag}.json", {"version": BENCH_VERSION, "model": a.model, "offload": g.offload,
                                               "cases": out, "allIdentical": all(c["identical"] for c in out)})


# ── 자동 지표 ─────────────────────────────────────────────────────────────────
def mask_stats(img, mask: np.ndarray) -> dict:
    from scipy import ndimage

    fg = mask >= ALPHA_THRESHOLD
    n = fg.size
    area = int(fg.sum())
    lab, ncomp = ndimage.label(fg, structure=np.ones((3, 3), dtype=int))
    sizes = np.bincount(lab.ravel())[1:] if ncomp else np.array([], dtype=int)
    sig = int((sizes >= COMPONENT_MIN_FRACTION * max(area, 1)).sum()) if area else 0
    b = BORDER_PX
    border = bool(fg[:b].any() or fg[-b:].any() or fg[:, :b].any() or fg[:, -b:].any())
    frac = area / n
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
    sat = float(hsv[..., 1][fg].mean()) if area else None
    ok_comp, ok_frac = sig == 1, FG_RANGE[0] <= frac <= FG_RANGE[1]
    return {"components": sig, "componentsRaw": int(ncomp), "fgFraction": round(frac, 4), "touchesBorder": border,
            "maskPass": bool(ok_comp and ok_frac and not border), "satMean": None if sat is None else round(sat, 4)}


def iou(a: np.ndarray, b: np.ndarray) -> float:
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 1.0


def summarize(per: list[dict], div: list[dict], rows: dict) -> dict:
    n = len(per)
    if not n:
        return {"n": 0}
    sats = [p["satMean"] for p in per if p["satMean"] is not None]
    abstract = [p for p in per if rows[p["id"]]["kind"] == "abstract"]
    return {
        "n": n,
        "maskPassRate": round(sum(p["maskPass"] for p in per) / n, 3),
        "maskPassAbstract": round(sum(p["maskPass"] for p in abstract) / max(len(abstract), 1), 3),
        "oneComponentRate": round(sum(p["components"] == 1 for p in per) / n, 3),
        "fgInRangeRate": round(sum(FG_RANGE[0] <= p["fgFraction"] <= FG_RANGE[1] for p in per) / n, 3),
        "borderTouchRate": round(sum(p["touchesBorder"] for p in per) / n, 3),
        "satMeanMean": round(float(np.mean(sats)), 4) if sats else None,
        "satMeanMedian": round(float(np.median(sats)), 4) if sats else None,
        "satLowRate": round(sum(x <= SAT_LOW for x in sats) / max(len(sats), 1), 3),
        "diverseRate": round(sum(d["maxIoU"] < IOU_HIGH for d in div) / max(len(div), 1), 3),
        "maxIoUMedian": round(float(np.median([d["maxIoU"] for d in div])), 4) if div else None,
        "gatePassRate": round(sum(bool(p["gatePassed"]) for p in per) / n, 3),
        "personLikeMax": round(max(p["personLikeScore"] for p in per), 4),
        "matchScoreMean": round(float(np.mean([p["matchScore"] for p in per])), 4)}


def cmd_metrics(a):
    import rembg
    from PIL import Image

    import form_asset

    models = a.models.split(",") if a.models else [m for m in MODELS if (RUN / m / "gen.json").exists()]
    rows = {r["id"]: r for r in load_prompts()}
    sess = rembg.new_session("u2net")
    gate = form_asset.GateStage()
    res = read_json(RUN / "metrics.json") if (RUN / "metrics.json").exists() else {}
    for m in models:
        gen = read_json(RUN / m / "gen.json")
        per, masks = [], {}
        mdir = RUN / m / "masks"
        mdir.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        for im in gen["images"]:
            img = Image.open(RUN / im["file"]).convert("RGB")
            mk = rembg.remove(img, session=sess, only_mask=True)
            mk.save(mdir / f"{im['id']}-s{im['seed']}.png")
            arr = np.asarray(mk.convert("L"))
            st = mask_stats(img, arr)
            gj = gate.judge([img], form_asset._phrase(rows[im["id"]]["prompt"]))
            st.update(id=im["id"], seed=im["seed"], personLikeScore=gj["personLikeScore"], gatePassed=gj["passed"],
                      matchScore=gj["matchScore"])
            per.append(st)
            masks[(im["id"], im["seed"])] = arr >= ALPHA_THRESHOLD
        div = []
        for pid in rows:
            ks = [k for k in masks if k[0] == pid]
            if len(ks) < 2:
                continue
            ious = [iou(masks[ks[i]], masks[ks[j]]) for i in range(len(ks)) for j in range(i + 1, len(ks))]
            div.append({"id": pid, "maxIoU": round(max(ious), 4), "ious": [round(x, 4) for x in ious]})
        sub = set(COMPARE_IDS)
        res[m] = {"perImage": per, "diversity": div, "seconds": round(time.perf_counter() - t0, 1),
                  "summary": summarize(per, div, rows),
                  "summaryCompare8": summarize([p for p in per if p["id"] in sub], [d for d in div if d["id"] in sub], rows)}
        print(m, json.dumps(res[m]["summary"], ensure_ascii=False), flush=True)
    res["_definitions"] = {"rembg": "u2net(form_asset.ShapeStage와 같은 세션 이름)", "alphaThreshold": ALPHA_THRESHOLD,
                           "componentMinFraction": COMPONENT_MIN_FRACTION, "fgRange": FG_RANGE, "borderPx": BORDER_PX,
                           "satLow": SAT_LOW, "iouHigh": IOU_HIGH,
                           "gate": "form_asset.GateStage.judge([이미지 1장]) — G75 pick_images와 같은 라벨·문턱 0.5"}
    write_json(RUN / "metrics.json", res)


# ── 3D 하류 ──────────────────────────────────────────────────────────────────
def cmd_mesh(a):
    import form_asset

    out = RUN / a.model / "mesh"
    out.mkdir(parents=True, exist_ok=True)
    rows = {r["id"]: r for r in load_prompts()}
    st = form_asset.ShapeStage()
    res = []
    for pid in COMPARE_IDS:
        png = RUN / a.model / f"{pid}-s0.png"
        rec = {"id": pid, "seed": 0}
        try:
            v, f, tm = st.make(png, 0, out)
            mesh, norm = form_asset.postprocess(v, f)
            cs = form_asset.component_stats(mesh)
            multi = form_asset.decide_multi_object(cs, bool(rows[pid]["pluralStated"]))
            mesh.export(out / f"{pid}-s0.glb")
            rec.update(ok=True, faces=norm["facesAfter"], components=cs["components"], significant=cs["significant"],
                       topFractions=cs["topFractions"], multiObjectBlocked=multi["blocked"],
                       watertight=bool(mesh.is_watertight), seconds=tm["shape"], vramReservedGiB=tm["vramReservedGiB"])
        except Exception as ex:  # noqa: BLE001 — 실패도 기록
            rec.update(ok=False, error=f"{type(ex).__name__}: {ex}"[:300])
        res.append(rec)
        print(a.model, pid, {k: rec.get(k) for k in ("ok", "components", "significant", "watertight", "seconds")}, flush=True)
    write_json(RUN / a.model / "mesh.json", {"version": BENCH_VERSION, "model": a.model, "rows": res,
                                             "config": form_asset.CONFIG["shape"], "shapeRevision": form_asset.SHAPE_REVISION})


# ── 시트 ─────────────────────────────────────────────────────────────────────
def _font(size: int):
    from PIL import ImageFont

    for f in ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def _save_small(im, p: Path, limit=2_000_000):
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p, optimize=True)
    if p.stat().st_size > limit:                      # 2 MB를 넘으면 회색조 아닌 팔레트로 줄인다
        im.convert("P", palette=1, colors=128).save(p, optimize=True)
    return p.stat().st_size


def cmd_sheets(a):
    from PIL import Image, ImageDraw

    rows = load_prompts()
    models = [m for m in MODELS if (RUN / m / "gen.json").exists()]
    fnt, fnt_s = _font(16), _font(13)
    th, lab_h, gap = a.thumb, 22, 6
    per_row = 2                                     # 한 줄에 프롬프트 2개 × seed 3장 = 6장
    for m in models:
        mrows = [r for r in rows if any((RUN / m / f"{r['id']}-s{s}.png").exists() for s in SEEDS)]   # 일부만 만든 모델은 만든 줄만
        nrow = (len(mrows) + per_row - 1) // per_row
        W = per_row * (3 * th + gap * 3) + gap
        H = 30 + nrow * (th + lab_h + gap)
        sheet = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(sheet)
        d.text((gap, 6), f"{m} — {len(mrows)} prompts x seed 0,1,2 ({MODELS[m]['repo']})", fill="black", font=fnt)
        for k, r in enumerate(mrows):
            x0 = gap + (k % per_row) * (3 * th + gap * 3)
            y0 = 30 + (k // per_row) * (th + lab_h + gap)
            d.text((x0, y0 + 2), f"{r['id']} {' '.join(r['content'])}", fill="black", font=fnt_s)
            for j, s in enumerate(SEEDS):
                f = RUN / m / f"{r['id']}-s{s}.png"
                if not f.exists():                      # 일부만 만든 모델(Z-Image)은 빈 칸
                    d.text((x0 + j * (th + 2) + th // 2 - 20, y0 + lab_h + th // 2), "(no run)", fill="gray", font=fnt_s)
                    continue
                im = Image.open(f).convert("RGB").resize((th, th), Image.LANCZOS)
                sheet.paste(im, (x0 + j * (th + 2), y0 + lab_h))
        sz = _save_small(sheet, DOC / f"sheet-{m}.png")
        print("sheet", m, sheet.size, sz, flush=True)
    # 비교 시트: 8 프롬프트 × 4 모델 × seed 3장
    th2 = a.thumb2
    W = 150 + len(models) * (3 * th2 + 12)
    H = 30 + len(COMPARE_IDS) * (th2 + 4)
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    for mi, m in enumerate(models):
        d.text((150 + mi * (3 * th2 + 12), 6), m, fill="black", font=fnt)
    byid = {r["id"]: r for r in rows}
    for ri, pid in enumerate(COMPARE_IDS):
        y0 = 30 + ri * (th2 + 4)
        d.text((4, y0 + th2 // 2 - 16), pid, fill="black", font=fnt)
        d.text((4, y0 + th2 // 2 + 4), " ".join(byid[pid]["content"])[:22], fill="black", font=fnt_s)
        for mi, m in enumerate(models):
            for j, s in enumerate(SEEDS):
                im = Image.open(RUN / m / f"{pid}-s{s}.png").convert("RGB").resize((th2, th2), Image.LANCZOS)
                sheet.paste(im, (150 + mi * (3 * th2 + 12) + j * (th2 + 2), y0))
    sz = _save_small(sheet, DOC / "compare-8x4.png")
    print("compare", sheet.size, sz, flush=True)


# ── 보고 ─────────────────────────────────────────────────────────────────────
def cmd_report(a):
    from form_asset import _weights_sha

    out = {"version": BENCH_VERSION, "seeds": SEEDS, "size": SIZE, "compareIds": COMPARE_IDS, "detCases": DET_CASES,
           "prompts": load_prompts(), "env": env_info(), "models": {}}
    metrics = read_json(RUN / "metrics.json") if (RUN / "metrics.json").exists() else {}
    out["metricDefinitions"] = metrics.get("_definitions")
    for m in MODELS:
        if not (RUN / m / "gen.json").exists():
            continue
        gen = read_json(RUN / m / "gen.json")
        e = {"config": gen["config"], "loadSeconds": gen["loadSeconds"], "loadPeakAllocGiB": gen["loadPeakAllocGiB"],
             "genPeakAllocGiB": gen["genPeakAllocGiB"], "genPeakReservedGiB": gen["genPeakReservedGiB"],
             "triple": gen["triple"], "triples": gen["triples"],
             "images": [{k: i[k] for k in ("id", "seed", "seconds", "sha256")} for i in gen["images"]]}
        if not a.no_hash:
            e["weightsSha256"] = {k: v for k, v in _weights_sha(snapshot(MODELS[m]["repo"], MODELS[m]["revision"])).items()
                                  if not any(x in k for x in ("vae_1_0/", "fp16", "openvino", "flax", "onnx"))}
        for tag in ("det", "det2"):
            if (RUN / m / f"{tag}.json").exists():
                e[tag] = read_json(RUN / m / f"{tag}.json")
        if m in metrics:
            e["metrics"] = metrics[m]
        if (RUN / m / "mesh.json").exists():
            e["mesh"] = read_json(RUN / m / "mesh.json")["rows"]
        if (RUN / m / "visual.json").exists():
            e["visual"] = read_json(RUN / m / "visual.json")
        out["models"][m] = e
    write_json(DOC / "bench.json", out)
    for m, e in out["models"].items():
        s = (e.get("metrics") or {}).get("summary") or {}
        print(m, e["config"]["revision"][:12], "off" if not e["config"]["offload"] else "OFFLOAD",
              e["genPeakAllocGiB"], e["loadSeconds"], e["triple"]["medianAfterFirst"],
              (e.get("det") or {}).get("allIdentical"), s.get("maskPassRate"), s.get("satMeanMean"),
              s.get("diverseRate"), s.get("gatePassRate"), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompts")
    p = sub.add_parser("gen")
    p.add_argument("--model", required=True, choices=list(MODELS))
    p.add_argument("--offload", default="auto", choices=["auto", "on", "off"])
    p.add_argument("--ids", default="")
    p = sub.add_parser("det")
    p.add_argument("--model", required=True, choices=list(MODELS))
    p.add_argument("--tag", default="det")
    p = sub.add_parser("metrics")
    p.add_argument("--models", default="")
    p = sub.add_parser("mesh")
    p.add_argument("--model", required=True, choices=list(MODELS))
    p = sub.add_parser("sheets")
    p.add_argument("--thumb", type=int, default=150)
    p.add_argument("--thumb2", type=int, default=96)
    p = sub.add_parser("report")
    p.add_argument("--no-hash", action="store_true")
    a = ap.parse_args(argv)
    {"prompts": cmd_prompts, "gen": cmd_gen, "det": cmd_det, "metrics": cmd_metrics, "mesh": cmd_mesh,
     "sheets": cmd_sheets, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
