"""G82 요약 시트: results.json + 그림·메시 축소판(저장소 밖 raw 폴더) → summary_1.png …(폭 1600px). G81 make_summary.py와 같은 꼴.

한 줄 = 한 문장: ID·유형 | 입력 문장 | 매퍼가 잡은 형태 | LLM 형태 이름(근거 인용 → 영어, 기각 사유) | 그림 3장(고른 그림 초록 테두리,
관문에 막힌 그림은 빨강) | 메시 축소판 | 결과(그림 프롬프트 앞부분·관문·시간·화면 끝까지 갔는지)
  python make_summary.py --raw <run_g82_e2e.py의 --raw 폴더> [--out <results.json 폴더>] [--judge judge.json] [--per-sheet 5] [--title G82]
외부 패키지: Pillow. 글꼴은 Windows 맑은 고딕.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
# 눈으로 본 판단(참고용, 점검자 한 사람이 화면을 보고 적음 — 측정이 아님). --judge <json {ID: 글}>로 받아 results.json에도 eyeJudgement로 넣는다
JUDGE = {}
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"
W = 1600
COLS = [("문장", 250), ("매퍼 형태", 170), ("LLM 형태 이름 (G82)", 220), ("그림 3장 (seed 0·1·2)", 3 * 132 + 8), ("메시", 150), ("결과", 0)]
ROW_H = 176
THUMB = 124


def f(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=font) > width:
            lines.append(cur)
            cur = ch.lstrip() if ch == " " else ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def mapper_text(c):
    sp = (c.get("collected") or {}).get("spec") or {}
    form = sp.get("form") or {}
    parts = []
    if form.get("type"):
        parts.append(f"type={form['type']}" + (f"({form['mistKind']})" if form.get("mistKind") else ""))
    if form.get("base"):
        bv = form.get("baseVariant") or {}
        parts.append(f"base={form['base']}" + (f"/{bv.get('form')}" if isinstance(bv, dict) and bv.get("form") else ""))
    trig = sorted({p.get("trigger") for v in (sp.get("formProvenance") or {}).values() for p in v if p.get("trigger")})
    if trig:
        parts.append("낱말: " + ", ".join(trig))
    neg = [n.get("lemma") or n.get("trigger") or str(n)[:20] for n in (sp.get("_negated") or [])]
    if neg:
        parts.append("부정: " + ", ".join(map(str, neg)))
    um = [u.get("lemma") for u in (sp.get("_unmapped") or []) if u.get("lemma")]
    if um:
        parts.append("못 씀: " + ", ".join(um))
    return "\n".join(parts) if parts else "(형태 없음)"


def llm_text(c):
    s = ((c.get("collected") or {}).get("summary") or {})
    sl = s.get("shapeLlm")
    if not sl:
        an = s.get("afterNone")
        return "기록 없음" + ("" if an else " ([맞는 게 없어요] 뒤 기록 없음)")
    lines = [f"경로 {sl.get('route')} ({sl.get('routeReason')})", f"부름 {'예' if sl.get('called') else '아니오'}"
             + (f" · {sl.get('llmSeconds')}초" if sl.get("llmSeconds") is not None else "")]
    raw = sl.get("rawItem")
    if sl.get("called"):
        lines.append("LLM 출력: " + (f"'{raw.get('quote')}' → {raw.get('en')}" if raw else "null(없음)"))
    if sl.get("adopted"):
        lines.append(f"채택: '{sl['adopted']['quote']}' → {sl['adopted']['en']}")
    if sl.get("rejectReasons"):
        lines.append("기각: " + ", ".join(sl["rejectReasons"]))
    flags = [k for k in ("exposed", "imageChosen", "candidateChosen", "rejected") if sl.get(k)]
    if flags:
        lines.append("기록: " + ", ".join(flags))
    if c.get("basisShown"):
        lines.append("화면: " + c["basisShown"])
    return "\n".join(lines)


def result_text(c):
    s = ((c.get("collected") or {}).get("summary") or {})
    an = s.get("afterNone") or {}
    ip = an.get("imagePick") or {}
    lines = []
    if c.get("error"):
        lines.append("오류: " + c["error"][:80])
    if not an:
        lines.append(f"[맞는 게 없어요] 뒤 기록 없음 ({c.get('result')})")
        return "\n".join(lines)
    head = (an.get("prompt") or "-").split(",")[0]
    res = c.get("result") or ""
    if res == "generated_and_chosen":
        lines.append(f"생성 → 고름 (프롬프트: {head})")
    elif res.startswith("basis_rejected"):
        lines.append(f"[그 말이 아니에요] → {res.split(':')[-1]} (프롬프트: {head})")
    elif an.get("blockReason") or an.get("status") in ("blocked", "failed"):
        lines.append(f"생성 안 함: {an.get('status')} · {an.get('blockReason')}")
    else:
        lines.append(f"{res} · {an.get('status')} (프롬프트: {head})")
    t = c.get("timings") or {}
    tl = []
    if t.get("noneToNextScreenS") is not None:
        tl.append(f"누름→다음 {t['noneToNextScreenS']}초")
    if t.get("pickToNextScreenS") is not None:
        tl.append(f"고름→메시 {t['pickToNextScreenS']}초")
    if t.get("rejectToNextScreenS") is not None:
        tl.append(f"아니에요→다음 {t['rejectToNextScreenS']}초")
    if tl:
        lines.append(" · ".join(tl))
    gate = an.get("meshGate") or {}
    if gate:
        mo = gate.get("multiObject") or {}
        lines.append(f"메시 관문 사람·동물 {gate.get('personLikeScore')} · 조각 {mo.get('significant')}")
    lines.append(f"runnerReady {s.get('runnerReady')} · form.type {s.get('formTypeSource')} · 끝까지 {'예' if c.get('reachedEnd') else '아니오'}")
    if JUDGE.get(c["id"]):
        lines.append("눈(참고): " + JUDGE[c["id"]])
    return "\n".join(lines)


def thumbs(c, raw):
    an = (((c.get("collected") or {}).get("summary") or {}).get("afterNone") or {})
    ip = an.get("imagePick") or {}
    imgs = ip.get("images") or []
    out = []
    for im in imgs[:3]:
        p = raw / f"{c['id']}_img_r0_p{im.get('position')}.png" if im.get("shown") else None
        out.append({"path": p if p and p.exists() else None, "passed": (im.get("gate") or {}).get("passed"),
                    "score": (im.get("gate") or {}).get("personLikeScore"),
                    "picked": im.get("shown") and im.get("seed") == ip.get("pickedSeed")})
    return out


def sheet(cases, raw, path, title):
    h = 70 + 36 + ROW_H * len(cases) + 10
    img = Image.new("RGB", (W, h), "white")
    d = ImageDraw.Draw(img)
    d.text((16, 14), title, font=f(26, True), fill="#1d2b2a")
    d.text((16, 48), "합성 대사 · experiment-g82 설정 · 실제 로컬 모델(gemma4:e4b, SDXL base 1.0, TripoSG, CLIP 관문) · 그림은 맨 앞(가장 작은 seed) 그림을 기계적으로 고름",
           font=f(14), fill="#555")
    y = 76
    x = 10
    xs = []
    rest = W - 20 - sum(w for _, w in COLS)
    for name, w in COLS:
        w = w or rest
        xs.append((x, w))
        d.rectangle([x, y, x + w - 2, y + 32], fill="#e6efed")
        d.text((x + 8, y + 6), name, font=f(16, True), fill="#1d2b2a")
        x += w
    y += 36
    small = f(13)
    for c in cases:
        d.line([10, y, W - 10, y], fill="#ccc")
        (x0, w0), (x1, w1), (x2, w2), (x3, w3), (x4, w4), (x5, w5) = xs
        d.text((x0 + 6, y + 6), f"{c['id']} · {c.get('kind', '')}", font=f(14, True), fill="#2c6a63")
        yy = y + 28
        for ln in wrap(d, "「" + c["text"] + "」" + (" + [그 말이 아니에요]" if c.get("reject") else ""), f(15), w0 - 14)[:6]:
            d.text((x0 + 6, yy), ln, font=f(15), fill="#111")
            yy += 20
        for (xx, ww), txt in (((x1, w1), mapper_text(c)), ((x2, w2), llm_text(c))):
            yy = y + 6
            for ln in [l2 for l in txt.split("\n") for l2 in wrap(d, l, small, ww - 12)][:9]:
                d.text((xx + 6, yy), ln, font=small, fill="#222")
                yy += 18
        th = thumbs(c, raw)
        for k in range(3):
            bx, by = x3 + 4 + k * 132, y + 8
            if k < len(th) and th[k]["path"]:
                t = Image.open(th[k]["path"]).convert("RGB").resize((THUMB, THUMB))
                img.paste(t, (bx, by))
                if th[k]["picked"]:
                    d.rectangle([bx - 3, by - 3, bx + THUMB + 2, by + THUMB + 2], outline="#1b9e4b", width=4)
            elif k < len(th):
                d.rectangle([bx, by, bx + THUMB, by + THUMB], fill="#f3e3e3", outline="#c33")
                d.text((bx + 8, by + 46), f"관문에 막힘\n{th[k]['score']}", font=small, fill="#a00")
            else:
                d.rectangle([bx, by, bx + THUMB, by + THUMB], outline="#ddd")
                if k == 0:
                    d.text((bx + 8, by + 52), "그림 단계\n시작 안 함", font=small, fill="#888")
        mp = raw / f"{c['id']}_mesh_thumb.png"
        if mp.exists():
            t = Image.open(mp).convert("RGB")
            t = t.crop((int(t.width * 0.25), int(t.height * 0.3), int(t.width * 0.75), int(t.height * 0.8)))   # 물체 둘레를 크게
            r = min((w4 - 10) / t.width, (ROW_H - 16) / t.height)
            t = t.resize((int(t.width * r), int(t.height * r)))
            img.paste(t, (x4 + 4, y + 8))
        else:
            d.text((x4 + 8, y + 60), "메시 없음", font=small, fill="#888")
        yy = y + 6
        for ln in [l2 for l in result_text(c).split("\n") for l2 in wrap(d, l, small, w5 - 12)][:9]:
            d.text((x5 + 6, yy), ln, font=small, fill="#222")
            yy += 18
        y += ROW_H
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", default=str(HERE), help="results.json이 있는 폴더(요약 시트도 여기에)")
    ap.add_argument("--per-sheet", type=int, default=5)
    ap.add_argument("--title", default="G82 실제 흐름 점검")
    ap.add_argument("--judge", default="", help="눈으로 본 판단 JSON {문장 ID: 글}(참고용)")
    a = ap.parse_args()
    if a.judge:
        JUDGE.update(json.loads(Path(a.judge).read_text(encoding="utf-8")))
    out = Path(a.out)
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    for cid, txt in JUDGE.items():
        if cid in res["cases"]:
            res["cases"][cid]["eyeJudgement"] = "(참고용, 점검자 눈) " + txt
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    order = sorted(res["cases"].values(), key=lambda c: c["id"])
    n = a.per_sheet
    for i in range(0, len(order), n):
        part = order[i:i + n]
        sheet(part, Path(a.raw), out / f"summary_{i // n + 1}.png",
              f"{a.title} ({i // n + 1}/{(len(order) + n - 1) // n}) — {part[0]['id']}–{part[-1]['id']}")


if __name__ == "__main__":
    main()
