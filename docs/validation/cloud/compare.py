# 구름 수정(D7) 전후 비교: before/after report.json → 마크다운 표(표준 출력)와 전후 시트(sheet.png).
# 실행: python docs/validation/cloud/compare.py   (Pillow 필요. 참여자 데이터 없음: 합성 spec과 목업(합성) 응답 spec)
# 밝기 대비(contrast.deltaL) = 형상 영역(윤곽 마스크) 평균 L* − 주변 배경 평균 L*. 배치 캡처가 report.json에 넣는다(SilhouetteMetrics.BackgroundContrast).
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def load(p):
    return json.loads((HERE / p).read_text(encoding="utf-8"))


def row(e):
    s, c = e.get("silhouette", {}), e.get("contrast", {})
    prim = e["color"].get("primary")
    return {
        "vis": e.get("visiblePixels"), "maxA": e.get("maxAlpha"), "circ": s.get("circularity"), "comp": s.get("components"),
        "dL": c.get("deltaL"), "std": c.get("shapeLStd"), "p95": e["performance"]["frameMsP95"],
        "op": e["params"].get("material.opacity"), "dE": (e["color"].get(prim) or {}).get("deltaE2000VsSpec"),
    }


def table(before, after):
    out = ["| spec | opacity | 대비 ΔL* 전 → 후 | 안쪽 L* 표준편차 전 → 후 | visiblePixels 전 → 후 | maxAlpha 전 → 후 | circularity 전 → 후 | components 전 → 후 | frameMsP95 전 → 후 (ms) | ΔE00(primary) 전 → 후 |",
           "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b, a in zip(before["specs"], after["specs"]):
        assert b["spec"] == a["spec"]
        x, y = row(b), row(a)
        out.append(f"| {b['spec'][:-5]} | {x['op']} | {x['dL']} → **{y['dL']}** | {x['std']} → {y['std']} | {x['vis']} → {y['vis']} | "
                   f"{x['maxA']} → **{y['maxA']}** | {x['circ']} → {y['circ']} | {x['comp']} → {y['comp']} | {x['p95']} → {y['p95']} | {x['dE']} → {y['dE']} |")
    return "\n".join(out)


def sheet(before, after, out):
    from PIL import Image, ImageDraw, ImageFont
    H = 260
    try:
        font = ImageFont.truetype("malgun.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    names = [e["spec"][:-5] for e in before["specs"]]
    rows = []
    for n in names:
        cells = []
        for d in ("before", "after"):
            for suffix in ("", "_detail"):
                im = Image.open(HERE / d / f"{n}{suffix}.png").convert("RGB")
                cells.append(im.resize((int(im.width * H / im.height), H)))
        rows.append(cells)
    label_w, gap, top = 170, 8, 30
    width = label_w + max(sum(c.width for c in r) + gap * 4 for r in rows)
    img = Image.new("RGB", (width, top + len(rows) * (H + gap)), "white")
    dr = ImageDraw.Draw(img)
    dr.text((label_w, 6), "전(이전 mist 셰이더): 장면 · 확대", fill="black", font=font)
    x_after = label_w + rows[0][0].width + rows[0][1].width + 2 * gap + gap
    dr.text((x_after, 6), "후(D7 덩어리 밀도장): 장면 · 확대", fill="black", font=font)
    for i, (n, cells) in enumerate(zip(names, rows)):
        y = top + i * (H + gap)
        dr.text((6, y + 6), n, fill="black", font=font)
        a = after["specs"][i]["contrast"]["deltaL"]
        b = before["specs"][i]["contrast"]["deltaL"]
        dr.text((6, y + 30), f"ΔL* {b} → {a}", fill="black", font=font)
        x = label_w
        for j, c in enumerate(cells):
            if j == 2:
                x += gap
            img.paste(c, (x, y))
            x += c.width + gap
    img.save(out)


if __name__ == "__main__":
    before, after = load("before/report.json"), load("after/report.json")
    print(table(before, after))
    bi, ai = load("before/inside/report.json"), load("after/inside/report.json")
    print()
    print("카메라가 안개 안(C03_cloud_inside): frameMsP95 "
          f"{bi['specs'][0]['performance']['frameMsP95']} → {ai['specs'][0]['performance']['frameMsP95']} ms, "
          f"maxAlpha {bi['specs'][0]['maxAlpha']} → {ai['specs'][0]['maxAlpha']}")
    sheet(before, after, HERE / "sheet.png")
    print("sheet.png 작성")
