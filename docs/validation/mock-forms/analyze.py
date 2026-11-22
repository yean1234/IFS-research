"""목업 결과 집계 — 형태 판정(규칙) + fidelity 상태 + Unity 지표 + 화면 판정(AI, visual.json) → analysis.json · tables.md.

  py -3.11 docs/validation/mock-forms/analyze.py

입력(이 폴더): mock_corpus.json, specs/v0|v1/*.json, live/specs/*.json, score/report.json(v0), score/compare/report.json(v1),
capture/report.json(Unity BatchCapture), visual.json(AI 화면 판정, 없으면 빈칸).
형태 판정 규칙(속성 i — "말한 형태가 SceneSpec에 들어갔나"):
  form 정답(slot = form.type): fidelity 상태 reflected → 반영, distorted → 왜곡, 그 밖에 _unmapped에 그 구절 근거가 있으면 미반영, 없으면 기본값.
  shape 정답(둥근·네모·납작·뾰족): _unmapped에 같은 모양 값(round/square/flat/pointed) → 반영(모양 모형), 다른 모양 값 → 왜곡,
     그 구절이 form.type 값을 만들었으면 '반영+form'(모양과 형상이 함께 들어감 — 렌더 경로는 Unity가 정함), _unmapped에 다른 근거 → 미반영, 없으면 기본값.
  슬롯 없는 형태(실·선·종이·천·액체·빛·구멍·사람·동물): 그 구절이 form.type 값을 만들었으면 왜곡(다른 값), _unmapped 근거 → 미반영, 없으면 기본값.
  형상 없음(느낌만·모름): form.type이 비어 있으면 반영(비어 있음 유지), 값이 생겼으면 왜곡(지어냄).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAPPERS = ("v0", "v1")
FORM_ATTRS = ("form", "shape", "lines", "sheet", "liquid", "light", "hole", "hollow", "figure")
SHAPE_TAGS = ("round", "square", "flat", "pointed")
CAT_KO = {"mist": "안개·연기·구름·김", "lump": "덩어리·뭉치", "shell": "껍질·막·껍데기", "fragments": "조각·파편·부스러기",
          "round": "둥근", "square": "네모난", "flat": "납작한", "pointed": "뾰족한", "lines": "선·실·엉킨 것",
          "sheet": "얇은 판·종이·천", "liquid": "액체·물방울·웅덩이", "light": "빛·불꽃", "hole": "구멍·빈 것",
          "figure": "사람·동물", "none": "형상 없음(느낌·모름)"}
FORMTYPE_TO_CAT = {"mist": "mist", "blob": "lump", "shell": "shell", "fragments": "fragments"}
ATTR_GROUP = {"color": "색", "size": "크기", "opacity": "투명", "motion_type": "움직임", "motion_speed": "움직임",
              "brightness": "밝기", "texture_roughness": "질감", "height": "높이·거리", "distance": "높이·거리",
              "erosion": "질감", "posture": "자세", "body_part": "몸 위치", "body_layer": "몸 위치"}
STATUS_KO = {"reflected": "반영", "distorted": "왜곡", "preserved": "미반영(원문 보존)", "lost": "미반영(유실)",
             "dropped_by_controller": "컨트롤러 탈락", "captured": "반영(값 검사 없음)"}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def overlaps(span, spans) -> bool:
    return any(span[0] < b and a < span[1] for a, b in spans)


def prov_spans(prov) -> list:
    if prov is None:
        return []
    items = prov if isinstance(prov, list) else [prov]
    return [tuple(p["charSpan"]) for p in items if isinstance(p, dict) and p.get("charSpan")]


def form_category(item: dict, g: dict) -> str | None:
    a = g["attr"]
    if a == "form":
        exp = g.get("expect") or {}
        v = exp.get("equals") or (exp.get("in") or [None])[0]
        return FORMTYPE_TO_CAT.get(v)
    if a == "shape":
        if g.get("negated"):
            return None
        tags = [t for t in item["tags"]["form"] if t in SHAPE_TAGS]
        return tags[0] if tags else None
    if a in ("hole", "hollow"):
        return "hole"
    if a in FORM_ATTRS:
        return a
    return None


def judge_form(item: dict, g: dict, row: dict, spec: dict, cat: str) -> tuple[str, str]:
    """(판정, 근거) — row는 fidelity 속성 행."""
    spans = [tuple(s) for s in row.get("spans") or []]
    ft = spec["form"]["type"]
    ft_spans = prov_spans((spec.get("_provenance") or {}).get("form.type"))
    ft_from_phrase = ft is not None and any(overlaps(s, spans) for s in ft_spans)
    unm = [u for u in spec.get("_unmapped") or []
           if overlaps(tuple((u.get("_provenance") or {}).get("charSpan") or (0, 0)), spans)]
    unm_txt = ",".join(sorted({f"{u.get('lemma')}→{json.dumps(u.get('value'), ensure_ascii=False)}" for u in unm}))
    if g["attr"] == "form":
        st = row["status"]
        if st == "reflected":
            return "반영", f"form.type={ft}"
        if st == "distorted":
            return "왜곡", f"form.type={ft}"
        if unm:
            return "미반영", f"_unmapped {unm_txt}"
        return "기본값", "form.type=null"
    if cat in SHAPE_TAGS:
        shapes = [((u.get("value") or {}).get("shape")) for u in unm if u.get("category") == "shape"]
        if cat in shapes:
            return ("반영+form" if ft_from_phrase else "반영"), f"_unmapped shape={cat}" + (f", form.type={ft}" if ft_from_phrase else "")
        if any(s in SHAPE_TAGS for s in shapes):
            return "왜곡", f"_unmapped shape={shapes}"
        if ft_from_phrase:
            return "왜곡", f"form.type={ft}"
        if unm:
            return "미반영", f"_unmapped {unm_txt}"
        return "기본값", "근거 없음"
    if ft_from_phrase:
        return "왜곡", f"form.type={ft}"
    if unm:
        return "미반영", f"_unmapped {unm_txt}"
    return "기본값", "근거 없음(_unmatched만)"


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".") if v else "0"
    if isinstance(v, dict) and "h" in v:
        return f"h{round(v['h'] * 360)} s{v['s']:.2f} l{v['l']:.2f}"
    return str(v)


def main() -> None:
    corpus = load(HERE / "mock_corpus.json")
    reports = {"v0": load(HERE / "score" / "report.json"), "v1": load(HERE / "score" / "compare" / "report.json")}
    unity = load(HERE / "capture" / "report.json")
    visual = load(HERE / "visual.json") or {}
    u_by = {e["spec"]: e for e in (unity or {}).get("specs", [])}
    rows_by = {m: {it["id"]: it["attributes"] for it in reports[m]["items"]} for m in MAPPERS}

    items_out = []
    form_counts = {m: defaultdict(Counter) for m in MAPPERS}
    for item in corpus["items"]:
        iid = item["id"]
        rec = {"id": iid, "expected": item["expected"], "tags": item["tags"], "mappers": {}}
        for m in MAPPERS:
            spec = load(HERE / "specs" / m / f"{iid}.{m}.json")
            attrs = rows_by[m][iid]
            forms = []
            for g, row in zip(item["gold"], attrs):
                assert g["phrase"] == row["phrase"], (iid, g["phrase"], row["phrase"])
                cat = form_category(item, g)
                if cat is None:
                    continue
                verdict, why = judge_form(item, g, row, spec, cat)
                forms.append({"category": cat, "phrase": g["phrase"], "verdict": verdict, "why": why})
                form_counts[m][cat][verdict] += 1
            if not forms:          # 형상 없음
                ft = spec["form"]["type"]
                v = "반영(비어 있음)" if ft is None else "왜곡(지어냄)"
                forms.append({"category": "none", "phrase": "", "verdict": v, "why": f"form.type={ft}"})
                form_counts[m]["none"][v] += 1
            others = []
            for g, row in zip(item["gold"], attrs):
                if g["attr"] in ATTR_GROUP and row["kind"] in ("slot", "slot_unscored"):
                    others.append({"attr": g["attr"], "group": ATTR_GROUP[g["attr"]], "phrase": g["phrase"],
                                   "status": row["status"], "actual": row.get("actual")})
            ue = u_by.get(f"{iid}.{m}.json") or {}
            sil = ue.get("silhouette") or {}
            rec["mappers"][m] = {
                "slots": {"form.type": spec["form"]["type"], "form.posture": spec["form"]["posture"],
                          "color": spec["material"]["color"], "opacity": spec["material"]["opacity"],
                          "brightness": spec["material"]["brightness"], "roughness": spec["material"]["roughness"],
                          "size": spec["layout"]["size"], "distance": spec["layout"]["distance"],
                          "verticalOffset": spec["layout"]["verticalOffset"], "motion.type": spec["motion"]["type"],
                          "body.part": spec["body"]["part"], "body.layer": spec["body"]["layer"]},
                "forms": forms, "others": others,
                "unity": {"renderPath": ue.get("renderPath"), "visiblePixels": ue.get("visiblePixels"),
                          "maxAlpha": ue.get("maxAlpha"), "circularity": sil.get("circularity"),
                          "components": sil.get("components"), "edgeFalloffPx": sil.get("edgeFalloffPx"),
                          "defaultsUsed": ue.get("defaultsUsed"), "png": ue.get("png")} if ue else None,
                "visual": (visual.get(iid) or {}).get(m),
            }
        if item.get("live"):
            ue = u_by.get(f"{iid}.live.v1.json") or {}
            spec = load(HERE / "live" / "specs" / f"{iid}.live.v1.json")
            sil = ue.get("silhouette") or {}
            rec["live"] = {
                "slots": {"form.type": spec["form"]["type"], "form.posture": spec["form"]["posture"],
                          "color": spec["material"]["color"], "opacity": spec["material"]["opacity"],
                          "brightness": spec["material"]["brightness"], "roughness": spec["material"]["roughness"],
                          "size": spec["layout"]["size"], "distance": spec["layout"]["distance"],
                          "verticalOffset": spec["layout"]["verticalOffset"], "motion.type": spec["motion"]["type"],
                          "body.part": spec["body"]["part"], "body.layer": spec["body"]["layer"]} if spec else None,
                "unity": {"renderPath": ue.get("renderPath"), "visiblePixels": ue.get("visiblePixels"),
                          "circularity": sil.get("circularity"), "components": sil.get("components")} if ue else None,
                "visual": (visual.get(iid) or {}).get("live"),
            }
        items_out.append(rec)

    # 속성 묶음별 fidelity 집계(형태 제외)
    attr_counts = {}
    for m in MAPPERS:
        c = defaultdict(Counter)
        for rec in items_out:
            for o in rec["mappers"][m]["others"]:
                c[o["group"]][o["status"]] += 1
        attr_counts[m] = {k: dict(v) for k, v in c.items()}

    # 화면 판정(AI) 집계: 전체, 그리고 항목의 첫 형태 범주별
    vis_counts = {k: Counter() for k in ("v0", "v1", "live")}
    vis_by_cat = {m: defaultdict(Counter) for m in MAPPERS}
    for rec in items_out:
        cat = rec["mappers"]["v1"]["forms"][0]["category"]
        for m in MAPPERS:
            v = (rec["mappers"][m].get("visual") or {}).get("verdict")
            if v:
                vis_counts[m][v] += 1
                vis_by_cat[m][cat][v] += 1
        if "live" in rec and (rec["live"].get("visual") or {}).get("verdict"):
            vis_counts["live"][rec["live"]["visual"]["verdict"]] += 1

    out = {"note": "형태 판정은 analyze.py 규칙, 화면 판정은 AI(visual.json). 사람 판정 아님.",
           "visualCounts": {k: dict(v) for k, v in vis_counts.items()},
           "visualByCategory": {m: {k: dict(v) for k, v in vis_by_cat[m].items()} for m in MAPPERS},
           "formCounts": {m: {k: dict(v) for k, v in form_counts[m].items()} for m in MAPPERS},
           "attrCounts": attr_counts,
           "fidelityOverall": {m: {k: reports[m]["summary"]["overall"][k] for k in
                                   ("reflectRate", "distortRate", "lostRate", "droppedRate", "preserveRate",
                                    "slotStatus", "spuriousRate", "unsupportedRate")} for m in MAPPERS},
           "items": items_out}
    (HERE / "analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_tables(out)
    print("analysis.json · tables.md")


def write_tables(out: dict) -> None:
    L = []
    verdicts = ["반영", "반영+form", "미반영", "왜곡", "기본값", "반영(비어 있음)", "왜곡(지어냄)"]
    L.append("### 형태 범주 × 판정 (v0 → v1, 구절 단위)\n")
    L.append("| 형태 범주 | 구절 수 | " + " | ".join(verdicts) + " |")
    L.append("| --- | --- | " + " | ".join("---" for _ in verdicts) + " |")
    cats = list(CAT_KO)
    for cat in cats:
        c0 = out["formCounts"]["v0"].get(cat, {})
        c1 = out["formCounts"]["v1"].get(cat, {})
        n = sum(c1.values())
        if not n:
            continue
        cells = []
        for v in verdicts:
            a, b = c0.get(v, 0), c1.get(v, 0)
            cells.append("" if a == b == 0 else (f"{a}" if a == b else f"{a} → **{b}**"))
        L.append(f"| {CAT_KO[cat]} | {n} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("### 화면 판정(AI) — 항목의 첫 형태 범주별 (v0 → v1)\n")
    vv = ["그 형상답다", "부분적", "다른 것으로 보임", "거의 안 보임", "기본 덩어리(형상 없음)"]
    L.append("| 형태 범주 | 항목 수 | " + " | ".join(vv) + " |")
    L.append("| --- | --- | " + " | ".join("---" for _ in vv) + " |")
    for cat in CAT_KO:
        c0 = out["visualByCategory"]["v0"].get(cat, {})
        c1 = out["visualByCategory"]["v1"].get(cat, {})
        n = sum(c1.values())
        if not n:
            continue
        cells = []
        for v in vv:
            a, b = c0.get(v, 0), c1.get(v, 0)
            cells.append("" if a == b == 0 else (f"{a}" if a == b else f"{a} → **{b}**"))
        L.append(f"| {CAT_KO[cat]} | {n} | " + " | ".join(cells) + " |")
    tot = []
    for k in ("v0", "v1", "live"):
        c = out["visualCounts"][k]
        tot.append(f"{k}: " + ", ".join(f"{v} {c.get(v, 0)}" for v in vv if c.get(v)))
    L.append("\n합계 — " + " / ".join(tot) + "\n")
    L.append("### 형태 밖 속성 × fidelity 상태 (v0 → v1, 정답 속성 단위)\n")
    sts = ["reflected", "distorted", "preserved", "lost", "dropped_by_controller", "captured"]
    L.append("| 속성 | 수 | " + " | ".join(STATUS_KO[s] for s in sts) + " |")
    L.append("| --- | --- | " + " | ".join("---" for _ in sts) + " |")
    groups = sorted({g for m in MAPPERS for g in out["attrCounts"][m]})
    for gname in ["색", "크기", "투명", "밝기", "질감", "움직임", "높이·거리", "자세", "몸 위치"]:
        if gname not in groups:
            continue
        c0 = out["attrCounts"]["v0"].get(gname, {})
        c1 = out["attrCounts"]["v1"].get(gname, {})
        n = sum(c1.values())
        cells = []
        for s in sts:
            a, b = c0.get(s, 0), c1.get(s, 0)
            cells.append("" if a == b == 0 else (f"{a}" if a == b else f"{a} → **{b}**"))
        L.append(f"| {gname} | {n} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("### 항목별\n")
    L.append("열: 형태 판정(규칙, v0 / v1) · v1 슬롯 요약 · 형태 밖 속성 v1 반영 수/전체 · renderPath(v0 / v1) · visiblePixels(v0 / v1) · "
             "v1 circularity / components · 화면 판정(AI, v0 / v1).\n")
    L.append("| id | 기대(말한 것) | 형태 v0 | 형태 v1 | v1 슬롯 | 속성 반영 v1 | renderPath v0 / v1 | visiblePixels v0 / v1 | circ / comp v1 | 화면 v0 / v1 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for rec in out["items"]:
        m0, m1 = rec["mappers"]["v0"], rec["mappers"]["v1"]
        f0 = "; ".join(f"{CAT_KO.get(f['category'], f['category'])}: {f['verdict']}" for f in m0["forms"])
        f1 = "; ".join(f"{f['verdict']} ({f['why']})" for f in m1["forms"])
        s = m1["slots"]
        slots = (f"form {fmt(s['form.type'])}" + (f"/{s['form.posture']}" if s["form.posture"] else "") +
                 f", 색 {fmt(s['color'])}, 크기 {fmt(s['size'])}, 투명 {fmt(s['opacity'])}, 움직임 {fmt(s['motion.type'])}")
        ok = sum(1 for o in m1["others"] if o["status"] in ("reflected", "captured"))
        u0, u1 = m0["unity"] or {}, m1["unity"] or {}
        v0, v1 = m0.get("visual") or {}, m1.get("visual") or {}
        L.append(f"| {rec['id']} | {rec['expected']} | {f0} | {f1} | {slots} | {ok}/{len(m1['others'])} | "
                 f"{u0.get('renderPath', '—')} / {u1.get('renderPath', '—')} | {u0.get('visiblePixels', '—')} / {u1.get('visiblePixels', '—')} | "
                 f"{fmt(u1.get('circularity'))} / {u1.get('components', '—')} | {v0.get('verdict', '—')} / {v1.get('verdict', '—')} |")
    L.append("")
    L.append("### 조건 2(라이브) 대 조건 1 — v1\n")
    L.append("| id | 조건 1 v1 슬롯 | 조건 2 v1 슬롯 | renderPath 1 / 2 | visiblePixels 1 / 2 | 화면 2 |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    for rec in out["items"]:
        if "live" not in rec:
            continue
        a, b = rec["mappers"]["v1"]["slots"], rec["live"]["slots"] or {}
        diff = [k for k in a if a.get(k) != b.get(k)]
        sa = ", ".join(f"{k} {fmt(a[k])}" for k in diff) or "같음"
        sb = ", ".join(f"{k} {fmt(b.get(k))}" for k in diff) or "같음"
        ua, ub = rec["mappers"]["v1"]["unity"] or {}, rec["live"]["unity"] or {}
        vb = rec["live"].get("visual") or {}
        L.append(f"| {rec['id']} | {sa} | {sb} | {ua.get('renderPath', '—')} / {ub.get('renderPath', '—')} | "
                 f"{ua.get('visiblePixels', '—')} / {ub.get('visiblePixels', '—')} | {vb.get('verdict', '—')} |")
    (HERE / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
