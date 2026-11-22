# before/after report.json → 전후 비교표(마크다운, 표준 출력)와 형상별 전후 시트 이미지(sheet.png).
# 실행: python docs/validation/render/compare.py   (Pillow 필요. 참여자 데이터 없음: 합성 spec + held-out 합성 문장)
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load(p):
    return json.loads((HERE / p).read_text(encoding="utf-8"))


def row(e):
    s = e.get("silhouette", {})
    rs = e["renderStats"]["computed"]
    return {
        "path": e.get("renderPath"), "vis": e.get("visiblePixels"), "maxA": e.get("maxAlpha"),
        "circ": s.get("circularity"), "comp": s.get("components"), "fall": s.get("edgeFalloffPx"),
        "p95": e["performance"]["frameMsP95"], "draws": rs["drawCallsPerEyeEstimate"],
        "tris": rs["submittedTrianglesPerEyeEstimate"], "form": e["params"]["form.type"],
        "dE": (e["color"].get(e["color"].get("primary"), {}) or {}).get("deltaE2000VsSpec"),
    }


def table(before, after, only=None):
    out = ["| spec | 형상 | renderPath 전→후 | visiblePixels | maxAlpha | circularity | components | edgeFalloffPx | frameMsP95 | 드로콜/눈 | 삼각형/눈 | ΔE00(primary) |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b, a in zip(before["specs"], after["specs"]):
        assert b["spec"] == a["spec"]
        x, y = row(b), row(a)
        if only and x["form"] not in only:
            continue
        def ch(k):
            return f"{x[k]}" if x[k] == y[k] else f"{x[k]} → **{y[k]}**"
        path = x["path"] if x["path"] == y["path"] else f"{x['path']} → {y['path']}"
        out.append(f"| {b['spec'][:-5]} | {x['form']} | {path} | {ch('vis')} | {ch('maxA')} | {ch('circ')} | {ch('comp')} | {ch('fall')} | "
                   f"{x['p95']} → {y['p95']} | {ch('draws')} | {ch('tris')} | {ch('dE')} |")
    return "\n".join(out)


def by_form(before, after):
    out = ["| 형상 | spec 수 | visiblePixels 평균 | circularity 평균 | components 평균 | edgeFalloffPx 평균 | frameMsP95 최대 |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    forms = sorted({row(e)["form"] for e in before["specs"]})
    for f in forms:
        def agg(rep, k, fn):
            v = [row(e)[k] for e in rep["specs"] if row(e)["form"] == f and row(e)[k] is not None]
            return fn(v) if v else None
        mean = lambda v: round(sum(v) / len(v), 3)
        n = sum(1 for e in before["specs"] if row(e)["form"] == f)
        cells = [f"{agg(before, k, fn)} → {agg(after, k, fn)}" for k, fn in
                 (("vis", mean), ("circ", mean), ("comp", mean), ("fall", mean), ("p95", max))]
        out.append(f"| {f} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def summary(before, after):
    sb, sa = before["summary"], after["summary"]
    keys = ["frameMsP95Max", "drawCallsPerEyeMax", "submittedTrianglesPerEyeMax"]
    lines = [f"- {k}: {sb[k]} → {sa[k]}" for k in keys]
    ac = {k: v for k, v in sa["ac4"].items() if isinstance(v, bool)}
    lines.append("- AC-4(후): " + ", ".join(f"{k}={v}" for k, v in ac.items()))
    return "\n".join(lines)


def mist_color(after):
    """후(after) mist spec의 색 측정 경로(color.measuredWith)·바닥 잘림(mistFloor). 전(before) report에는 없는 키라 후만 본다."""
    out = ["| spec | measuredWith | primary | ΔE00 vs spec | ΔE00 vs 셰이더 목표(알베도 기준) | floorClipped | 잘린 높이 비율 |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for e in after["specs"]:
        if e["params"]["form.type"] != "mist":
            continue
        c = e["color"]
        p = c.get(c.get("primary"), {}) or {}
        mf = e.get("mistFloor") or {}
        out.append(f"| {e['spec'][:-5]} | {c.get('measuredWith')} | {c.get('primary')} | {p.get('deltaE2000VsSpec')} | "
                   f"{p.get('deltaE2000VsShaderTarget')} | {mf.get('floorClipped')} | {mf.get('clippedHeightFraction')} |")
    return "\n".join(out)


def sheet(pairs, out):
    from PIL import Image, ImageDraw
    cell = 260
    img = Image.new("RGB", (cell * 2 + 140, cell * len(pairs) + 30), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((140 + cell // 2 - 20, 8), "before", fill=(0, 0, 0))
    d.text((140 + cell + cell // 2 - 15, 8), "after", fill=(0, 0, 0))
    for i, (label, b, a) in enumerate(pairs):
        y = 30 + i * cell
        d.text((8, y + cell // 2 - 6), label, fill=(0, 0, 0))
        for j, p in enumerate((b, a)):
            path = HERE / p
            if path.exists():
                im = Image.open(path).convert("RGB")
                im.thumbnail((cell - 6, cell - 6))
                img.paste(im, (140 + j * cell + (cell - im.width) // 2, y + (cell - im.height) // 2))
            else:
                d.text((140 + j * cell + 20, y + cell // 2), "(PNG 없음)", fill=(200, 0, 0))
    img.save(HERE / out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    b, a = load("before/report.json"), load("after/report.json")
    hb, ha = load("before/heldout/report.json"), load("after/heldout/report.json")
    print("## 합성 13개\n")
    print(table(b, a))
    print("\n" + summary(b, a))
    print("\n## 합성 13개 — 형상별\n")
    print(by_form(b, a))
    print("\n## held-out 60개 — 형상별\n")
    print(by_form(hb, ha))
    print("\n" + summary(hb, ha))
    print("\n## held-out — mist·fragments spec\n")
    print(table(hb, ha, only={"mist", "fragments"}))
    print("\n## mist 색 측정 경로·바닥 잘림(후)\n")
    print(mist_color(a))
    print()
    print(mist_color(ha).split("\n", 2)[2])
    pairs = [(n, f"before/{n}_detail.png", f"after/{n}_detail.png") for n in
             ("R01_mist_op100", "R02_mist_op060", "R03_mist_op015", "R04_frag_small", "R05_frag_large",
              "R07_blob_default", "R11_shape_square", "R13_shape_pointed")]
    pairs += [(n, f"before/heldout/{n}_detail.png", f"after/heldout/{n}_detail.png") for n in ("H02.v0", "H23.v0")]
    sheet(pairs, "sheet.png")
    print("\n(sheet.png 저장)")
