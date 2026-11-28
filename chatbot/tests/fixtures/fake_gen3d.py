"""G73 시험용 생성기 대역: tools/gen3d/generate.py와 같은 인자(--run --pipeline --seed)를 받아, 정해진 시간 뒤 작은 가짜 GLB와
form-asset.v0 사이드카를 GEN3D_OUT/<run>/g62-<pipeline>/assets/에 쓴다(실제 생성기와 같은 자리·같은 형식). 모델을 부르지 않는다.

프롬프트·sourceTextSha256은 실제 규칙(tools/gen3d/prompts.shape_prompt)으로 만든다(서버가 같은지 다시 본다).
환경 변수: FAKE_GEN3D_MODE = ok(기본) | gate(관문 차단 person_like) | failed(사이드카 status failed) | crash(사이드카 없이 exit 3)
           | hang(끝나지 않음 — 시간 초과·취소 시험) | mismatch(프롬프트를 바꿔 씀), FAKE_GEN3D_DELAY = 초(기본 0.5).
--cache-probe(G73 후속): FAKE_GEN3D_PROBE = miss(기본, 모델을 부를 것) | hit(캐시로 끝남) | fail(exit 4) — <run>/cache-probe.json.
(G75) --image-pick --seeds a,b,c: seed마다 작은 PNG + image-pick.json(실제 생성기와 같은 자리·형식).
  FAKE_GEN3D_IMAGE_MODE = ok(기본) | failed(status failed) | crash(exit 5) | hang | blocked(프롬프트 막힘처럼) | mismatch(프롬프트를 바꿔 씀)
  FAKE_GEN3D_IMAGE_GATE = 관문에 걸릴 이미지 순번(0부터, 쉼표) 또는 all. FAKE_GEN3D_IMAGE_TAMPER = 순번(파일을 적은 뒤 바꿈 — sha256 불일치)
--from-image <png> --image-sha256 <sha>: 그 이미지의 sha256을 확인하고(다르면 사이드카 failed) FAKE_GEN3D_MODE대로 사이드카.
  (G85) FAKE_GEN3D_MESH_GATE_SEEDS = 쉼표로 적은 seed — 그 seed의 그림으로 만든 메시만 관문 차단(person_like).
연구 자료가 아니다(합성 메시·합성 그림).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def tiny_glb(height: float) -> bytes:
    pos = [(-0.5, 0.0, -0.25), (0.5, 0.0, -0.25), (0.0, 0.0, 0.25), (0.0, height, 0.0)]
    idx = [0, 1, 2, 0, 3, 1, 1, 3, 2, 2, 3, 0]
    pb = b"".join(struct.pack("<3f", *p) for p in pos)
    ib = b"".join(struct.pack("<H", i) for i in idx)
    ib += b"\x00" * ((4 - len(ib) % 4) % 4)
    binary = pb + ib
    gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
            "buffers": [{"byteLength": len(binary)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pb)},
                            {"buffer": 0, "byteOffset": len(pb), "byteLength": len(idx) * 2}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 4, "type": "VEC3",
                           "min": [-0.5, 0.0, -0.25], "max": [0.5, height, 0.25]},
                          {"bufferView": 1, "componentType": 5123, "count": len(idx), "type": "SCALAR"}]}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


def tiny_png(seed: int) -> bytes:
    """seed마다 다른 회색 8×8 PNG."""
    w = h = 8
    v = 60 + (seed * 37) % 160
    rows = b"".join(b"\x00" + bytes([v, v, v]) * w for _ in range(h))

    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def image_pick(a, rows, gp, out_root, delay):
    mode = os.environ.get("FAKE_GEN3D_IMAGE_MODE", "ok")
    gate_env = os.environ.get("FAKE_GEN3D_IMAGE_GATE", "")
    tamper = {int(x) for x in os.environ.get("FAKE_GEN3D_IMAGE_TAMPER", "").split(",") if x.strip()}
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()] or [a.seed]
    gated = set(range(len(seeds))) if gate_env == "all" else {int(x) for x in gate_env.split(",") if x.strip()}
    if mode == "hang":
        time.sleep(3600)
    time.sleep(delay)
    if mode == "crash":
        sys.exit(5)
    run_dir = out_root / a.run
    r = rows[0]
    p = gp.shape_prompt_for_row(r)
    res = {"schema": "gen3d-image-pick.v0", "version": "fake", "id": r["id"], "pipeline": a.pipeline, "seeds": seeds,
           "status": "ok", "blockReason": None, "blockDetail": None, "error": None,
           "prompt": {"text": p["text"] + (" CHANGED" if mode == "mismatch" else ""), "builderVersion": p["builderVersion"],
                      "imageStyle": p.get("imageStyle")},
           "sourceTextSha256": p["sourceTextSha256"],
           "models": [{"name": "image", "repo": "none/fake-sdxl", "revision": "0" * 40}], "images": [], "timing": {"fake": delay}}
    if p["status"] != "ok" or mode == "blocked":
        res.update(status="blocked", blockReason=p["blockReason"] or "fake_blocked")
    elif mode == "failed":
        res.update(status="failed", error="RuntimeError: fake image failure")
    else:
        for k, s in enumerate(seeds):
            png = run_dir / "images" / f"{r['id']}-s{s}.png"
            png.parent.mkdir(parents=True, exist_ok=True)
            data = tiny_png(s)
            png.write_bytes(data)
            res["images"].append({"seed": s, "file": png.relative_to(run_dir).as_posix(),
                                  "sha256": hashlib.sha256(data).hexdigest(), "seconds": delay,
                                  "gate": {"personLikeScore": 0.9 if k in gated else 0.02, "passed": k not in gated,
                                           "threshold": 0.5}})
            if k in tamper:
                png.write_bytes(data + b"x")
            bad = os.environ.get("FAKE_GEN3D_IMAGE_BADPATH", "")      # (CP14-2) "0:abs,1:dotdot" — 그 순번의 file을 잘못 적음
            for spec_ in filter(None, bad.split(",")):
                idx, kind = spec_.split(":")
                if int(idx) == k:
                    res["images"][-1]["file"] = (str(png.resolve()) if kind == "abs"
                                                 else "../FAKE-SECRET-DIR/" + png.name)
    (run_dir / "image-pick.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print("fake image-pick", res["status"], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cache-probe", action="store_true")
    ap.add_argument("--image-pick", action="store_true")
    ap.add_argument("--seeds", default="")
    ap.add_argument("--from-image", default="")
    ap.add_argument("--image-sha256", default="")
    a = ap.parse_args()
    with open(Path(os.environ["GEN3D_OUT"]) / "fake-calls.log", "a", encoding="utf-8") as lf:   # 시험이 호출 인자를 본다
        lf.write(json.dumps({"run": a.run, "seed": a.seed, "imagePick": a.image_pick, "seeds": a.seeds,
                             "fromImage": Path(a.from_image).name if a.from_image else None,
                             "imageSha256": a.image_sha256 or None, "cacheProbe": a.cache_probe}) + "\n")
    mode = os.environ.get("FAKE_GEN3D_MODE", "ok")
    delay = float(os.environ.get("FAKE_GEN3D_DELAY", "0.5"))
    out_root = Path(os.environ["GEN3D_OUT"])
    rows = json.loads((out_root / a.run / "inputs" / "sentences.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("gp", REPO / "tools" / "gen3d" / "prompts.py")
    gp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gp)
    print("fake gen3d", a.run, mode, flush=True)
    if a.image_pick:
        image_pick(a, rows, gp, out_root, delay)
        return
    gate_seeds = {int(x) for x in os.environ.get("FAKE_GEN3D_MESH_GATE_SEEDS", "").split(",") if x.strip()}
    if a.from_image and a.seed in gate_seeds:
        mode = "gate"                         # (G85 시험) 이 seed의 그림으로 만든 메시만 관문 차단(person_like)
    if a.from_image and hashlib.sha256(Path(a.from_image).read_bytes()).hexdigest() != a.image_sha256:
        mode = "failed"                       # 고른 이미지가 바뀜 → 만들지 않음(실제 생성기와 같이 사이드카 failed)
    if a.cache_probe:
        pm = os.environ.get("FAKE_GEN3D_PROBE", "miss")
        if pm == "fail":
            sys.exit(4)
        out = {}
        for r in rows:
            p = gp.shape_prompt_for_row(r)
            out[r["id"]] = {"status": p["status"], "promptText": p["text"], "cacheKey": None,
                            "cached": (pm == "hit") if p["status"] == "ok" else None}
        (out_root / a.run / "cache-probe.json").write_text(json.dumps(
            {"pipeline": a.pipeline, "seed": a.seed, "rows": out,
             "modelCallsExpected": any(v["cached"] is False for v in out.values()), "seconds": 0.0},
            ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if mode == "hang":
        time.sleep(3600)
    time.sleep(delay)
    if mode == "crash":
        print("Traceback: fake crash", file=sys.stderr, flush=True)
        sys.exit(3)
    assets = out_root / a.run / f"g62-{a.pipeline}" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for r in rows:
        p = gp.shape_prompt_for_row(r)        # 서버와 같은 규칙(promptRule mapper면 세션 spec)
        key = hashlib.sha256(("fake|" + p["text"] + "|" + str(a.seed)).encode("utf-8")).hexdigest()
        aid = key[:16]
        status = {"ok": "ok", "mismatch": "ok", "gate": "blocked", "failed": "failed"}.get(mode, "ok")
        if p["status"] != "ok":
            status = "blocked"
        glb_name = sha = None
        if status == "ok":
            data = tiny_glb(0.4 + (int(key[:4], 16) % 50) / 100)
            glb_name = f"{aid}.glb"
            (assets / glb_name).write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
        side = {
            "schema": "form-asset.v0", "assetId": aid, "cacheKey": key, "status": status,
            "blockReason": p["blockReason"] if p["status"] != "ok" else ("person_like" if mode == "gate" else None),
            "blockDetail": None, "error": "RuntimeError: fake failure" if mode == "failed" else None,
            "glb": glb_name, "glbSha256": sha, "pipeline": a.pipeline, "postprocessVersion": "fake",
            "models": [{"name": "shape", "repo": "none/fake-gen3d", "revision": "0" * 40, "weightsSha256": {"fake.bin": "0" * 64}}],
            "seed": a.seed,
            "prompt": {"text": p["text"] + (" CHANGED" if mode == "mismatch" else ""), "negativeText": p["negativeText"],
                       "lexiconVersion": p["lexiconVersion"], "builderVersion": p["builderVersion"],
                       "tokens": p["tokens"], "dropped": p["dropped"]},
            "sourceTextSha256": p["sourceTextSha256"],
            "normalization": {"longestEdge": 1.0, "pivot": "bottom-center"} if status == "ok" else None,
            "covariates": {"axisRatios": [1.0, 0.6, 0.5], "thinRisk": False, "familiarObjectStated": False, "pluralStated": False},
            "gate": ({"personLikeScore": 0.9, "passed": False, "threshold": 0.5,           # 실제 관문과 같은 꼴(라벨 점수 포함)
                      "labelScores": {"a head with eyes and a mouth": 0.7, "a plain object": 0.1}} if mode == "gate" else
                     {"personLikeScore": 0.01, "passed": True}) if status != "failed" else
                    {"personLikeScore": None, "passed": None},
            "timing": {"fake": delay}, "cacheHit": False,
        }
        (assets / f"{r['id']}.form-asset.json").write_text(json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8")
    print("끝", flush=True)


if __name__ == "__main__":
    main()
