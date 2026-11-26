"""배치 캡처 결과 → 이 폴더의 capture/(형상 주변 같은 배율 잘라 냄), summary.json(지표), sheets/contour.png·emission.png.
PIL 필요(시스템 Python). docs/validation/base-forms/collect.py를 바탕으로 했다.

  python docs\validation\scene-spec-2.3\collect.py <캡처 폴더> <make_specs 출력 폴더>

_detail.png는 형상마다 경계 상자로 확대해 크기·비율을 서로 견줄 수 없으므로, 장면 PNG(눈높이 카메라가 형상 중심을 봄)의
가운데를 모두 같은 크기로 잘라 쓴다(길쭉함·납작함 비율을 같은 배율로 본다). report.json 전체는 로컬 경로·기기 정보가 있어 넣지 않는다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "C:/Windows/Fonts/malgun.ttf"
CROP = 300      # 장면 PNG(폭 768)의 가운데 CROP × CROP


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cap")
    ap.add_argument("specs")
    a = ap.parse_args()
    cap, specs = Path(a.cap), Path(a.specs)
    rep = json.loads((cap / "report.json").read_text(encoding="utf-8"))
    index = {r["id"]: r for r in json.loads((specs / "_index.json").read_text(encoding="utf-8"))}
    out_cap = HERE / "capture"
    out_cap.mkdir(exist_ok=True)
    rows = []
    for e in rep["specs"]:
        sid = Path(e["spec"]).stem
        src = cap / f"{sid}.png"
        if src.exists():
            im = Image.open(src).convert("RGB")
            w, h = im.size
            im.crop(((w - CROP) // 2, (h - CROP) // 2, (w + CROP) // 2, (h + CROP) // 2)).save(out_cap / f"{sid}.png", optimize=True)
        plan = e.get("renderPlan") or {}
        sil = e.get("silhouette") or {}
        con = e.get("console") or {}
        rows.append({
            "id": sid, **{k: v for k, v in index.get(sid, {}).items() if k != "id"},
            "loaded": e.get("loaded"), "renderPath": e.get("renderPath"),
            "contour": e.get("contour"), "emission": e.get("emission"),
            "defaultsUsed": [k for k in e.get("defaultsUsed") or [] if k.startswith("form.")],
            "visiblePixels": e.get("visiblePixels"),
            "silhouette": {k: sil.get(k) for k in ("circularity", "components", "edgeFalloffPx", "maskPixels")},
            "contrastDeltaL": (e.get("contrast") or {}).get("deltaL"),
            # 1차 색 측정(primary 경로)의 화면 색 vs spec 색 ΔE00 — 발광이 바탕색을 얼마나 밝히는지 보는 참고값(발광은 셰이더 목표색에 없음)
            "colorPrimaryDeltaE00VsSpec": (((e.get("color") or {}).get((e.get("color") or {}).get("primary") or "") or {})
                                           .get("deltaE2000VsSpec")),
            "colorPrimaryMeanSrgb8": (((e.get("color") or {}).get((e.get("color") or {}).get("primary") or "") or {})
                                      .get("meanSrgb8")),
            "consoleErrors": con.get("errors"), "consoleWarnings": con.get("warnings"),
            "modelTriangles": next((x["triangles"] for x in ((e.get("renderStats") or {}).get("computed") or {}).get("renderers", [])
                                    if x["name"].startswith("model")), None),
            "frameP95Ms": (e.get("performance") or {}).get("frameMsP95"),
            "contourNotes": [n for n in e.get("notes") or [] if "form.roundness" in n or "form.aspect" in n or "material.emission" in n],
            "planPreset": plan.get("preset"), "zeroDisplacement": plan.get("zeroDisplacement"),
        })
    (HERE / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    def sheet(name: str, ids: list[list[str]], col_labels: list[str], row_labels: list[str]) -> None:
        T, LAB, HEAD = 200, 22, 26
        f = ImageFont.truetype(FONT, 14)
        cols, n_rows = len(col_labels), len(row_labels)
        left = 200
        img = Image.new("RGB", (left + cols * (T + 6) + 6, HEAD + n_rows * (T + LAB + 6) + 6), (255, 255, 255))
        d = ImageDraw.Draw(img)
        for c, lab in enumerate(col_labels):
            d.text((left + 6 + c * (T + 6), 4), lab, fill=(0, 0, 0), font=f)
        for r, lab in enumerate(row_labels):
            y = HEAD + r * (T + LAB + 6)
            d.text((6, y + T // 2 - 8), lab, fill=(0, 0, 0), font=f)
            for c in range(cols):
                sid = ids[r][c]
                x = left + 6 + c * (T + 6)
                p = out_cap / f"{sid}.png"
                if p.exists():
                    im = Image.open(p).convert("RGB")
                    im.thumbnail((T, T))
                    img.paste(im, (x, y))
                row = next((q for q in rows if q["id"] == sid), {})
                d.text((x, y + T + 2), f"{sid}  {row.get('renderPath')}", fill=(60, 60, 60), font=ImageFont.truetype(FONT, 11))
        (HERE / "sheets").mkdir(exist_ok=True)
        img.save(HERE / "sheets" / f"{name}.png", optimize=True)

    rnames = ["null(말 안 함)", "angular", "slightly_angular", "neutral", "slightly_rounded", "rounded"]
    rids = ["Rn", "R0", "R1", "R2", "R3", "R4"]
    sheet("contour", [[f"A_{r}_{k}" for k in ("E", "-", "F")] for r in rids],
          ["aspect = elongated", "aspect = null", "aspect = flattened"], [f"roundness = {n}" for n in rnames])
    ecols = [(e, r, c) for r in (0, 4) for c in ("blue", "gray") for e in ("none", "faint", "glowing")]
    sheet("emission", [[f"B_{e}_R{r}_{c}" for e in ("none", "faint", "glowing")] for r in (0, 4) for c in ("blue", "gray")],
          ["emission = none", "emission = faint", "emission = glowing"],
          ["angular · 파랑(말함)", "angular · 회색(기본색)", "rounded · 파랑(말함)", "rounded · 회색(기본색)"])
    print(json.dumps([{k: r[k] for k in ("id", "renderPath", "visiblePixels", "consoleErrors", "consoleWarnings")} for r in rows],
                     ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
