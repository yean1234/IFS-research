"""G81 요약 시트: results.json + 그림·메시 축소판(저장소 밖 raw 폴더) → summary_1.png, summary_2.png(폭 1600px).

한 줄 = 한 문장: ID·유형 | 입력 문장 | 매퍼가 잡은 형태 | G77 | 그림 3장(고른 그림 초록 테두리, 관문에 막힌 그림은 빨강 X) | 메시 축소판 | 결과
  python make_summary.py --raw <run_g81.py의 --raw 폴더> [--per-sheet 8]
외부 패키지: Pillow. 글꼴은 Windows 맑은 고딕.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
# 눈으로 본 판단(참고용, 점검자 한 사람이 화면을 보고 적음 — 측정이 아님). results.json에도 eyeJudgement로 넣는다
JUDGE = {
    "A1": "그림 3장 모두 매듭(굵은 끈 뭉치). 메시는 그림 0을 따른 매듭 뭉치. 받침·끈 없음",
    "A2": "'꼬인 띠'는 맞으나 '얇은'이 안 보임(굵은 고리). 그림 2는 세워진 고리. 메시는 꼬인 고리",
    "B1": "구·덩어리로 알아볼 만함. 그림 2에 받침(기둥) 붙음. 메시는 구 — 규칙 후보(구)와 거의 같음. 쑥색이 선명한 초록으로",
    "C1": "그림은 돌덩이로 알아볼 만함. 메시를 만들었지만 후보 화면에서 빠져(WebGL mist_form) 참여자는 설명 없이 조절로",
    "C1r2": "같은 문장·새 세션 ID: 이번엔 메시가 후보에 나와 고름(캐시). 메시는 둥근 돌",
    "C2": "LLM이 '조약돌'에 형태 낱말을 내지 않음 → 그림 단계 시작 안 함",
    "C3": "LLM이 색·질감만 채우고 '판때기' 형태 낱말은 안 냄 → 그림 단계 시작 안 함",
    "D1": "C1과 같은 낱말인데 '같은 게' 꼴에서는 LLM이 형태 낱말을 안 냄 → 시작 안 함",
    "D2": "깃털로 알아볼 만함(직유 원천을 형태로 씀). 메시는 얇은 깃털, '가벼운'은 반영 대상 아님",
    "E1": "형태를 말하지 않음 → 만들지 않음(의도대로)",
    "F1": "사람 → 막힘(의도대로)",
    "F2": "동물 → 막힘(의도대로)",
    "F3": "안개 → 메시 아님으로 막힘(의도대로)",
    "F4": "불꽃 → 메시 아님으로 막힘(의도대로)",
    "G1": "부정된 '매듭'을 빼고 막힘(의도대로)",
    "G2": "과거('예전에는')인데 막히지 않고 공을 그림 — 기대와 다름. 그림 2에 받침 붙음",
    "H1": "'뾰족한 돌'로 알아볼 만함(그림 0). 메시도 뾰족한 돌. 가드가 문장을 '확인'으로 판정해 G77은 건너뜀",
}
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"
W = 1600
COLS = [("문장", 260), ("매퍼 형태", 190), ("G77 (LLM 빈칸)", 200), ("그림 3장 (seed 0·1·2)", 3 * 132 + 8), ("메시", 150), ("결과", 0)]
ROW_H = 166
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


def g77_text(c):
    lf = (c.get("collected") or {}).get("llmFill") or {}
    if not lf:
        ev = (c.get("collected") or {}).get("llmFillEvent") or {}
        return f"기록 없음 ({ev.get('status', '-')})"
    st = lf.get("status")
    if st != "ok":
        return f"{st} {lf.get('skipReason') or lf.get('error') or ''}".strip()
    items = lf.get("items") or []
    if not items:
        return "호출됨, 제안 0"
    out = []
    for it in items:
        mark = "통과" if it.get("ok") else "기각:" + ",".join(it.get("reasons") or [])
        out.append(f"{it.get('slot')}={it.get('value')} '{it.get('quote')}' {mark}")
    return "\n".join(out)


def result_text(c):
    an = (((c.get("collected") or {}).get("selection") or {}).get("generation") or {}).get("afterNone") or {}
    ip = an.get("imagePick") or {}
    lines = []
    res = c.get("result") or c.get("error", "")[:60]
    if c.get("error"):
        lines.append("오류: " + c["error"][:80])
    if not an:
        lines.append(f"[맞는 게 없어요] 뒤 기록 없음 ({res})")
        return "\n".join(lines)
    prompt = (an.get("prompt") or {}).get("text") or ip.get("promptText") or ""
    head = prompt.split(",")[0] if prompt else "-"
    if an.get("status") == "ok" and an.get("chosen"):
        lines.append(f"생성 → 고름 (프롬프트: {head})")
    elif an.get("status") == "ok" and not an.get("chosen") and not c.get("pickedPosition") is None:
        lines.append(f"메시 만듦 → 후보 화면에서 빠짐(버그) (프롬프트: {head})")
    elif an.get("blockReason") or an.get("status") in ("blocked", "failed"):
        lines.append(f"생성 안 함: {an.get('status')} · {an.get('blockReason') or ip.get('blockReason') or an.get('error')}")
        if head != "-":
            lines.append(f"(프롬프트: {head})")
    else:
        lines.append(f"{an.get('status')} {an.get('blockReason') or ''} (프롬프트: {head})")
    t = c.get("timings") or {}
    if t.get("noneToNextScreenS") is not None:
        if t.get("pickToNextScreenS"):
            lines.append(f"누름→그림 {t['noneToNextScreenS']}초 · 고름→다음 화면 {t['pickToNextScreenS']}초")
        else:
            lines.append(f"누름→다음 화면 {t['noneToNextScreenS']}초")
    gate = (an.get("asset") or {}).get("gate") or {}
    if gate:
        mo = gate.get("multiObject") or {}
        lines.append(f"메시 관문 사람·동물 {gate.get('personLikeScore')} · 조각 {mo.get('significant')}")
    sel = ((c.get("collected") or {}).get("selection") or {})
    lines.append(f"runnerReady {sel.get('runnerReady')} · form.type {((sel.get('sources') or {}).get('form.type'))}")
    if JUDGE.get(c["id"]):
        lines.append("눈(참고): " + JUDGE[c["id"]])
    return "\n".join(lines)


def thumbs(c, raw):
    an = (((c.get("collected") or {}).get("selection") or {}).get("generation") or {}).get("afterNone") or {}
    ip = an.get("imagePick") or {}
    imgs = ip.get("images") or []
    rnd = ip.get("round") or 0
    out = []
    for im in imgs[:3]:
        p = raw / f"{c['id']}_img_r{rnd}_p{im.get('position')}.png" if im.get("shown") else None
        out.append({"path": p if p and p.exists() else None, "passed": (im.get("gate") or {}).get("passed"),
                    "score": (im.get("gate") or {}).get("personLikeScore"), "picked": im.get("shown") and im.get("position") == ip.get("pickedPosition")})
    return out


def sheet(cases, raw, path, title):
    h = 70 + 36 + ROW_H * len(cases) + 10
    img = Image.new("RGB", (W, h), "white")
    d = ImageDraw.Draw(img)
    d.text((16, 14), title, font=f(26, True), fill="#1d2b2a")
    d.text((16, 48), "합성 대사 · experiment 설정 · 실제 로컬 모델(gemma4:e4b, SDXL base 1.0, TripoSG, CLIP 관문) · 그림은 맨 앞(가장 작은 seed) 그림을 기계적으로 고름",
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
        d.text((x0 + 6, y + 6), f"{c['id']} · {c['type']}", font=f(14, True), fill="#2c6a63")
        yy = y + 28
        for ln in wrap(d, "「" + c["text"] + "」", f(15), w0 - 14)[:6]:
            d.text((x0 + 6, yy), ln, font=f(15), fill="#111")
            yy += 20
        for (xx, ww), txt in (((x1, w1), mapper_text(c)), ((x2, w2), g77_text(c))):
            yy = y + 6
            for ln in [l2 for l in txt.split("\n") for l2 in wrap(d, l, small, ww - 12)][:8]:
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
        for ln in [l2 for l in result_text(c).split("\n") for l2 in wrap(d, l, small, w5 - 12)][:8]:
            d.text((x5 + 6, yy), ln, font=small, fill="#222")
            yy += 18
        y += ROW_H
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--per-sheet", type=int, default=8)
    a = ap.parse_args()
    res = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    for cid, txt in JUDGE.items():
        if cid in res["cases"]:
            res["cases"][cid]["eyeJudgement"] = "(참고용, 점검자 눈) " + txt
    (HERE / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    order = [c for c in sorted(res["cases"].values(), key=lambda c: c["id"])]
    n = a.per_sheet
    for i in range(0, len(order), n):
        part = order[i:i + n]
        sheet(part, Path(a.raw), HERE / f"summary_{i // n + 1}.png",
              f"G81 형태 입력별 생성 점검 ({i // n + 1}/{(len(order) + n - 1) // n}) — {part[0]['id']}–{part[-1]['id']}")


if __name__ == "__main__":
    main()
