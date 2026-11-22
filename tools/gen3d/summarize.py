"""측정 요약: 생성 시간·VRAM·GLB 크기/삼각형·결정성(generate.py meta·run.json) + Unity 로드 시간(capture/report.json).

  python tools/gen3d/summarize.py --runs dev10,notion20 [--out <json>]

숫자만 모은다(문장 원문은 읽지 않음). 결과 JSON 기본 위치는 OUT_ROOT/compare/summary.json(저장소 밖).
"""
from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import OUT_ROOT, read_json, write_json  # noqa: E402

COMBOS = ("shap-e-rules", "shap-e-llm", "sdxl-triposr-rules", "sdxl-triposr-llm")


def q(xs):
    xs = sorted(xs)
    if not xs:
        return None
    return {"n": len(xs), "median": round(st.median(xs), 3), "min": round(xs[0], 3), "max": round(xs[-1], 3)}


def summarize(run_dir: Path, combo: str) -> dict | None:
    d = run_dir / combo
    if not (d / "run.json").exists():
        return None
    run = read_json(d / "run.json")
    gen, vram, tris, mb, prompts = [], [], [], [], []
    for m in sorted((d / "meta").glob("*.json")):
        meta = read_json(m)
        r0 = meta["runs"][0]
        s = r0["seconds"]
        gen.append(sum(v for v in s.values()))
        v = r0["vram"]
        vram.append(max(x["maxReservedGiB"] for x in v.values()) if "image" in v else v["maxReservedGiB"])
        tris.append(r0["mesh"]["triangles"])
        mb.append(r0["mesh"]["bytes"] / 2**20)
        prompts.append(meta["prompt"]["subject"])
    det = run.get("determinism") or {}
    out = {"perSentenceSeconds": q(gen), "vramReservedGiB": q(vram), "triangles": q(tris), "glbMiB": q(mb),
           "glbIdentical": f"{sum(x['glbIdentical'] for x in det.values())}/{len(det)}" if det else None,
           "imageIdentical": (f"{sum(bool(x['imageIdentical']) for x in det.values())}/{len(det)}"
                              if det and combo.startswith("sdxl") else None),
           "distinctPrompts": len(set(prompts)), "sentences": len(prompts),
           "runTotalSeconds(repeat 포함·모델 로드 포함)": run.get("totalSeconds")}
    cap = d / "capture" / "report.json"
    if cap.exists():
        rep = read_json(cap)
        loads = [i["loadMs"]["total"] for i in rep["items"] if i.get("ok")]
        out["unity"] = {"loaded": f"{len(loads)}/{rep['count']}", "loadMs": q(loads),
                        "consoleErrors": sum(i.get("consoleErrors", 0) for i in rep["items"]),
                        "shaders": sorted({s for i in rep["items"] for s in i.get("shaders", [])})}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="dev10,notion20")
    ap.add_argument("--out", type=Path, default=OUT_ROOT / "compare" / "summary.json")
    a = ap.parse_args(argv)
    res = {}
    for run in a.runs.split(","):
        res[run] = {c: summarize(OUT_ROOT / run, c) for c in COMBOS}
    write_json(a.out, res)
    import json

    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
