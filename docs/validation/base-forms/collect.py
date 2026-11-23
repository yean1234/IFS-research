"""배치 캡처 결과 → 이 폴더의 capture/(PNG), summary.<묶음>.json(지표 요약), sheets/<묶음>.png(시트). PIL 필요(시스템 Python).

  python docs\\validation\\base-forms\\collect.py <캡처 폴더> <make_specs 출력 폴더> <묶음 이름> [--suffix .after]

report.json 전체는 로컬 경로·기기 정보가 있어 넣지 않고, 형상 지표만 옮긴다(renderPath, renderPlan.base, visiblePixels,
silhouette, contrast, 콘솔 오류·경고 수, notes 가운데 기본 형상 줄).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "C:/Windows/Fonts/malgun.ttf"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cap")
    ap.add_argument("specs")
    ap.add_argument("group")
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()
    cap, specs = Path(a.cap), Path(a.specs)
    rep = json.loads((cap / "report.json").read_text(encoding="utf-8"))
    index = {r["id"]: r for r in json.loads((specs / "_index.json").read_text(encoding="utf-8"))}
    out_cap = HERE / "capture"
    out_cap.mkdir(exist_ok=True)
    rows = []
    for e in rep["specs"]:
        sid = Path(e.get("spec") or e.get("file") or e.get("specFile") or "").stem or e.get("id")
        name = sid + a.suffix
        for tail in ("_detail",):            # 장면 전체 PNG는 크기가 커서 넣지 않음(형상 주변 확대만)
            src = cap / f"{sid}{tail}.png"
            if src.exists():
                shutil.copyfile(src, out_cap / f"{name}{tail}.png")
        plan = e.get("renderPlan") or {}
        sil = e.get("silhouette") or {}
        con = e.get("console") or {}
        rows.append({
            "id": name, **{k: v for k, v in index.get(sid, {}).items() if k != "id"},
            "renderPath": e.get("renderPath"), "base": plan.get("base"),
            "visiblePixels": e.get("visiblePixels"),
            "silhouette": {k: sil.get(k) for k in ("circularity", "components", "edgeFalloffPx", "maskPixels")},
            "contrastDeltaL": (e.get("contrast") or {}).get("deltaL"),
            "consoleErrors": con.get("errors"), "consoleWarnings": con.get("warnings"),
            "modelTriangles": next((x["triangles"] for x in ((e.get("renderStats") or {}).get("computed") or {}).get("renderers", []) if x["name"].startswith("model")), None),
            "trianglesPerEyeEstimate": ((e.get("renderStats") or {}).get("computed") or {}).get("submittedTrianglesPerEyeEstimate"),
            "baseNotes": [n for n in e.get("notes") or [] if "form.base" in n or "기본 형상" in n],
        })
    (HERE / f"summary.{a.group}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                                  newline="\n")
    # 시트: 칸마다 형상 주변 확대(_detail) + 아래에 id·문장(또는 기본 형상)
    T, LAB = 240, 64
    cols = min(5, len(rows)) or 1
    n_rows = (len(rows) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (T + 8) + 8, n_rows * (T + LAB + 8) + 8), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 13)
    for i, r in enumerate(rows):
        x, y = 8 + (i % cols) * (T + 8), 8 + (i // cols) * (T + LAB + 8)
        p = out_cap / f"{r['id']}_detail.png"
        if p.exists():
            im = Image.open(p).convert("RGB")
            im.thumbnail((T, T))
            sheet.paste(im, (x, y))
        text = r.get("text") or ""
        b = r.get("base") or {}
        line1 = f"{r['id']}  {r.get('renderPath')}"
        line2 = (text[:18] + "…") if len(text) > 19 else text
        line3 = f"{b.get('status') or '-'} {json.dumps(b.get('variant') or {}, ensure_ascii=False)[:30]}"
        for k, t in enumerate((line1, line2, line3)):
            d.text((x, y + T + 2 + k * 19), t, fill=(0, 0, 0), font=f)
    (HERE / "sheets").mkdir(exist_ok=True)
    sheet.save(HERE / "sheets" / f"{a.group}.png", optimize=True)
    print(json.dumps(rows, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
