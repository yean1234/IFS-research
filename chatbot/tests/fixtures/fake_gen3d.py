"""G73 시험용 생성기 대역: tools/gen3d/generate.py와 같은 인자(--run --pipeline --seed)를 받아, 정해진 시간 뒤 작은 가짜 GLB와
form-asset.v0 사이드카를 GEN3D_OUT/<run>/g62-<pipeline>/assets/에 쓴다(실제 생성기와 같은 자리·같은 형식). 모델을 부르지 않는다.

프롬프트·sourceTextSha256은 실제 규칙(tools/gen3d/prompts.shape_prompt)으로 만든다(서버가 같은지 다시 본다).
환경 변수: FAKE_GEN3D_MODE = ok(기본) | gate(관문 차단 person_like) | failed(사이드카 status failed) | crash(사이드카 없이 exit 3)
           | hang(끝나지 않음 — 시간 초과·취소 시험) | mismatch(프롬프트를 바꿔 씀), FAKE_GEN3D_DELAY = 초(기본 0.5).
연구 자료가 아니다(합성 메시).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import time
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    mode = os.environ.get("FAKE_GEN3D_MODE", "ok")
    delay = float(os.environ.get("FAKE_GEN3D_DELAY", "0.5"))
    out_root = Path(os.environ["GEN3D_OUT"])
    rows = json.loads((out_root / a.run / "inputs" / "sentences.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("gp", REPO / "tools" / "gen3d" / "prompts.py")
    gp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gp)
    print("fake gen3d", a.run, mode, flush=True)
    if mode == "hang":
        time.sleep(3600)
    time.sleep(delay)
    if mode == "crash":
        print("Traceback: fake crash", file=sys.stderr, flush=True)
        sys.exit(3)
    assets = out_root / a.run / f"g62-{a.pipeline}" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for r in rows:
        p = gp.shape_prompt(r["text"])
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
            "gate": {"personLikeScore": 0.9 if mode == "gate" else 0.01, "passed": mode != "gate"} if status != "failed" else
                    {"personLikeScore": None, "passed": None},
            "timing": {"fake": delay}, "cacheHit": False,
        }
        (assets / f"{r['id']}.form-asset.json").write_text(json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8")
    print("끝", flush=True)


if __name__ == "__main__":
    main()
