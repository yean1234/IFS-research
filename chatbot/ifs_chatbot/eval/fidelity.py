"""심상-구현 일치도 채점 — 정답(gold) 대비 SceneSpec 슬롯 값을 판정한다. LLM 없음, 결정론적.

  python -m ifs_chatbot.eval.fidelity --corpus tests/fixtures/imagery_corpus/dev.json --mapper v0 --out <폴더>
  → <폴더>/runs.json(항목별 확정 텍스트·spec·컨트롤러 기록), report.json, report.md

## 정답 속성의 종류(kind)

| kind | 조건 | 쓰는 판정 |
| --- | --- | --- |
| slot | slot ≠ null, negated = false, expect ≠ null | reflected / distorted / preserved / lost / dropped_by_controller |
| slot_unscored | slot ≠ null, negated = false, expect = null | captured / preserved / lost / dropped_by_controller (반영률 분모에서 뺌) |
| negated | negated = true | preserved / lost / dropped_by_controller + negationError 표시 |
| no_slot | slot = null, negated = false | preserved / lost / dropped_by_controller |

## 판정(slot)

- 위치: phrase를 정규화해 확정 텍스트에서 찾은 모든 구간(occurrence). 확정 텍스트에 없고 replies에는 있으면
  **dropped_by_controller**(컨트롤러가 그 답을 쓰지 않음 — 묻지 않은 프로브 등). replies에도 없으면 phrase_missing(코퍼스 오류, 집계 제외).
- **reflected**: spec[slot]이 expect를 만족한다(equals / in / range / color의 hue_deg·s·l). {"equals": null}은 값이 null이어야 만족.
- **distorted**: 값이 있으나 expect를 만족하지 않음(wrong_value), 또는 값이 null인데 그 phrase가 다른 슬롯 값을 잘못
  만듦(cross_slot: phrase 구간과 겹치는 _provenance가 다른 경로 P에 있고, P를 가진 정답 phrase가 그 근거를 덮지 않으며,
  P의 값이 P의 정답을 만족하지도 않음).
- **preserved**: 값이 null이고, phrase 구간의 공백 아닌 글자가 모두 보존 필드(_provenance를 뺀 '_' 최상위 키:
  _unmatched, _unmapped, _negated, _alternatives, _inferred, 개선 매핑이 더하는 보존 필드)의 원문 근거(charSpan과
  그 구간의 원문과 같은 surface/trigger/text/phrase)로 덮임. 원문 그대로(구간 포함)만 인정한다.
- **lost**: 위 어디에도 해당하지 않음.

no_slot·negated·slot_unscored의 보존: no_slot은 보존 필드 ∪ _provenance(값의 근거로 남은 것도 원문 보존으로 봄),
negated는 보존 필드만(값으로 쓰인 것은 오류이므로 보존으로 치지 않음). slot_unscored는 phrase와 겹치는 근거로 그 슬롯에
값이 생겼으면 captured.

## 지표

- 반영률 = reflected / slot 수 · 왜곡률 = distorted / slot 수 · 손실률 = lost / slot 수 · 컨트롤러 탈락률 = dropped / slot 수
- 보존률 = (reflected + captured + preserved) / 전체 속성 수(모든 kind, dropped 포함)
- 미반영 원문 보존률 = 반영·포착되지 않은 속성(dropped 제외) 중 phrase가 보존 필드에 원문 그대로 있는 비율(상태와 무관한 verbatim 판정)
- 배경 오염 = distractor 구간과 겹치는 _provenance 근거가 들어간 (distractor, 경로) 쌍의 수(정답 phrase가 그 경로로
  덮으면 제외). 그 근거가 값을 정한 첫 근거이면 decisive(값 자체를 배경이 정함)
- 근거 없는 값(spurious) = 값이 있는 슬롯 중 그 항목 정답(부정 아님)에 그 경로가 없는 것의 수 / 값이 있는 슬롯 수
  (docs/research-design.md 4.4 Spurious_c와 같은 정의. 말하지 않은 것을 채움 — 원칙 2 감시)
- 부정 오류 = negated phrase 구간과 겹치는 _provenance 근거로 생긴 슬롯 값이 있는 negated 속성 수
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from ..korean import normalize
from ..scene_spec import SLOT_PATHS

SCORER_VERSION = "0.1.0"
STATUSES = ("reflected", "distorted", "preserved", "lost", "dropped_by_controller", "captured")
TEXT_KEYS = ("surface", "trigger", "text", "phrase")
VALUE_EVIDENCE_KEY = "_provenance"

Span = tuple[int, int]


# ── 기본 도우미 ──────────────────────────────────────────────────────────────
def find_spans(text: str, phrase: str) -> list[Span]:
    """정규화한 phrase가 text에 나타나는 모든 구간(겹치지 않게)."""
    p = normalize(phrase)
    out, i = [], 0
    if not p:
        return out
    while True:
        j = text.find(p, i)
        if j < 0:
            return out
        out.append((j, j + len(p)))
        i = j + len(p)


def overlaps(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def get_value(spec: dict | None, path: str):
    group, key = path.split(".")
    return ((spec or {}).get(group) or {}).get(key)


def satisfies(value, expect: dict) -> bool:
    """value가 expect를 만족하는가. expect 키: equals | in | range | hue_deg/s/l(색)."""
    if "equals" in expect:
        return value == expect["equals"]
    if value is None:
        return False
    if "in" in expect:
        return value in expect["in"]
    if "range" in expect:
        lo, hi = expect["range"]
        return isinstance(value, (int, float)) and not isinstance(value, bool) and lo <= value <= hi
    color_keys = {"hue_deg", "s", "l"}
    if set(expect) & color_keys:
        unknown = set(expect) - color_keys
        if unknown:
            raise ValueError(f"모르는 expect 키: {sorted(unknown)}")
        if not isinstance(value, dict) or not {"h", "s", "l"} <= set(value):
            return False
        if "hue_deg" in expect:
            hue = (float(value["h"]) * 360.0) % 360.0
            lo, hi = expect["hue_deg"]
            if not (lo <= hue <= hi if lo <= hi else (hue >= lo or hue <= hi)):
                return False
        for k in ("s", "l"):
            if k in expect and not (expect[k][0] <= float(value[k]) <= expect[k][1]):
                return False
        return True
    raise ValueError(f"모르는 expect 형식: {expect}")


def show_value(value):
    """리포트 표시용: 색은 hue를 도 단위로."""
    if isinstance(value, dict) and {"h", "s", "l"} <= set(value):
        return {"hue_deg": round(float(value["h"]) * 360, 1), "s": value["s"], "l": value["l"]}
    return value


def value_evidence(spec: dict | None) -> list[tuple[str, Span, str]]:
    """(경로, 구간, trigger) — 슬롯 값의 근거."""
    out = []
    for path, provs in ((spec or {}).get(VALUE_EVIDENCE_KEY) or {}).items():
        for p in provs or []:
            cs = p.get("charSpan")
            if isinstance(cs, (list, tuple)) and len(cs) == 2:
                out.append((path, (int(cs[0]), int(cs[1])), p.get("trigger", "")))
    return out


def _walk(node, found: list[tuple[Span, str]]):
    if isinstance(node, dict):
        cs = node.get("charSpan")
        txt = next((node[k] for k in TEXT_KEYS if isinstance(node.get(k), str)), None)
        if isinstance(cs, (list, tuple)) and len(cs) == 2 and txt is not None:
            found.append(((int(cs[0]), int(cs[1])), txt))
        for v in node.values():
            _walk(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found)


def preservation_spans(spec: dict | None, text: str) -> list[Span]:
    """보존 필드('_'로 시작하는 최상위 키 중 _provenance 제외)에 원문 그대로 남은 구간.
    근거 문자열이 확정 텍스트의 그 구간과 글자까지 같아야 인정한다."""
    found: list[tuple[Span, str]] = []
    for key, node in (spec or {}).items():
        if key.startswith("_") and key != VALUE_EVIDENCE_KEY:
            _walk(node, found)
    return sorted({sp for sp, txt in found if 0 <= sp[0] <= sp[1] <= len(text) and text[sp[0]:sp[1]] == txt})


def coverage(text: str, span: Span, spans: list[Span]) -> float:
    """span 안의 공백 아닌 글자 중 spans로 덮인 비율."""
    idx = [i for i in range(span[0], span[1]) if not text[i].isspace()]
    if not idx:
        return 1.0
    covered = sum(1 for i in idx if any(s <= i < e for s, e in spans))
    return covered / len(idx)


def kind_of(g: dict) -> str:
    if g.get("negated"):
        return "negated"
    if g.get("slot") is None:
        return "no_slot"
    return "slot" if g.get("expect") is not None else "slot_unscored"


# ── 한 항목 채점 ─────────────────────────────────────────────────────────────
def score_item(item: dict, run: dict) -> dict:
    """item: 코퍼스 항목(gold, distractors, replies). run: {confirmedText, spec, ...}."""
    text = run.get("confirmedText") or ""
    spec = run.get("spec") or {}
    replies_text = "\n".join(normalize(v) for v in (item.get("replies") or {}).values() if v)
    evidence = value_evidence(spec)
    keep = preservation_spans(spec, text)
    keep_and_values = sorted(set(keep) | {sp for _, sp, _ in evidence})
    gold = item.get("gold") or []
    occ = [find_spans(text, g["phrase"]) for g in gold]

    def licensed(path: str, span: Span) -> bool:
        """그 경로의 (부정 아닌) 정답 phrase가 이 근거 구간과 겹치는가."""
        return any(g.get("slot") == path and not g.get("negated") and any(overlaps(span, o) for o in occ[k])
                   for k, g in enumerate(gold))

    def benign(path: str) -> bool:
        """그 경로의 현재 값이 그 경로의 (부정 아닌) 정답 하나를 만족하는가."""
        v = get_value(spec, path)
        return v is not None and any(g.get("slot") == path and kind_of(g) == "slot" and satisfies(v, g["expect"])
                                     for g in gold)

    attrs = []
    for k, g in enumerate(gold):
        kind, spans = kind_of(g), occ[k]
        rec = {"attr": g["attr"], "phrase": g["phrase"], "slot": g.get("slot"), "kind": kind,
               "expect": g.get("expect"), "spans": [list(s) for s in spans]}
        if not spans:
            rec["status"] = "dropped_by_controller" if find_spans(replies_text, g["phrase"]) else "phrase_missing"
            attrs.append(rec)
            continue
        touching = [(p, sp, trig) for p, sp, trig in evidence if any(overlaps(sp, o) for o in spans)]
        verbatim = any(coverage(text, o, keep) >= 1.0 for o in spans)
        rec["verbatimPreserved"] = verbatim
        rec["coverageAny"] = round(max(coverage(text, o, keep_and_values) for o in spans), 3)
        rec["phraseEvidence"] = [{"path": p, "trigger": t} for p, _, t in touching]
        if kind in ("slot", "slot_unscored"):
            value = get_value(spec, g["slot"])
            rec["actual"] = show_value(value)
            rec["valueTriggers"] = [t for p, _, t in evidence if p == g["slot"]]
            cross = [{"path": p, "trigger": t, "value": show_value(get_value(spec, p))}
                     for p, sp, t in touching if p != g["slot"] and not licensed(p, sp) and not benign(p)]
            rec["crossSlot"] = cross
            if kind == "slot":
                ok = satisfies(value, g["expect"])
                rec["inAlternatives"] = any(a.get("path") == g["slot"] and satisfies(a.get("value"), g["expect"])
                                            for a in spec.get("_alternatives") or [])
                if ok:
                    rec["status"] = "reflected"
                elif value is not None:
                    rec["status"], rec["reason"] = "distorted", "wrong_value"
                elif cross:
                    rec["status"], rec["reason"] = "distorted", "cross_slot"
                else:
                    rec["status"] = "preserved" if verbatim else "lost"
            else:
                from_phrase = value is not None and any(p == g["slot"] for p, _, _ in touching)
                rec["status"] = "captured" if from_phrase else ("preserved" if verbatim else "lost")
        elif kind == "negated":
            errs = [{"path": p, "trigger": t, "value": show_value(get_value(spec, p))}
                    for p, sp, t in touching if not licensed(p, sp)]
            rec["negationError"] = errs
            rec["status"] = "preserved" if verbatim else "lost"
        else:  # no_slot
            full = any(coverage(text, o, keep_and_values) >= 1.0 for o in spans)
            rec["mappedTo"] = sorted({p for p, _, _ in touching})
            rec["status"] = "preserved" if full else "lost"
        attrs.append(rec)

    contamination, seen = [], set()
    for d in item.get("distractors") or []:
        for o in find_spans(text, d["phrase"]):
            for p, sp, t in evidence:
                if overlaps(sp, o) and not licensed(p, sp) and (d["phrase"], p) not in seen:
                    seen.add((d["phrase"], p))
                    first = ((spec.get(VALUE_EVIDENCE_KEY) or {}).get(p) or [{}])[0].get("charSpan")
                    contamination.append({"phrase": d["phrase"], "path": p, "trigger": t,
                                          "value": show_value(get_value(spec, p)),
                                          "decisive": list(sp) == list(first or [])})

    gold_slots = {g["slot"] for g in gold if g.get("slot") and not g.get("negated")}
    spurious = [{"path": path, "value": show_value(get_value(spec, path)),
                 "triggers": [t for p, _, t in evidence if p == path]}
                for path in SLOT_PATHS if get_value(spec, path) is not None and path not in gold_slots]
    n_values = sum(1 for p in SLOT_PATHS if get_value(spec, p) is not None)
    return {"id": item["id"], "style": item.get("style"), "attributes": attrs,
            "contamination": contamination, "spurious": spurious, "valuesFilled": n_values,
            "negationErrors": sum(1 for a in attrs if a.get("negationError"))}


# ── 집계 ────────────────────────────────────────────────────────────────────
def _rate(n: int, d: int):
    return round(n / d, 4) if d else None


def _summary(attrs: list[dict], items: list[dict]) -> dict:
    attrs = [a for a in attrs if a["status"] != "phrase_missing"]
    slot = [a for a in attrs if a["kind"] == "slot"]
    sc = Counter(a["status"] for a in slot)
    allc = Counter(a["status"] for a in attrs)
    unref = [a for a in attrs if a["status"] not in ("reflected", "captured", "dropped_by_controller")]
    negs = [a for a in attrs if a["kind"] == "negated"]
    values = sum(i["valuesFilled"] for i in items)
    spurious = sum(len(i["spurious"]) for i in items)
    return {
        "attributes": len(attrs),
        "slotAttributes": len(slot),
        "slotStatus": {s: sc.get(s, 0) for s in ("reflected", "distorted", "preserved", "lost", "dropped_by_controller")},
        "allStatus": {s: allc.get(s, 0) for s in STATUSES},
        "reflectRate": _rate(sc["reflected"], len(slot)),
        "distortRate": _rate(sc["distorted"], len(slot)),
        "lostRate": _rate(sc["lost"], len(slot)),
        "droppedRate": _rate(sc["dropped_by_controller"], len(slot)),
        "preserveRate": _rate(allc["reflected"] + allc["captured"] + allc["preserved"], len(attrs)),
        "unreflectedVerbatimRate": _rate(sum(1 for a in unref if a.get("verbatimPreserved")), len(unref)),
        "unreflected": len(unref),
        "negated": len(negs),
        "negationErrors": sum(1 for a in negs if a.get("negationError")),
        "contamination": sum(len(i["contamination"]) for i in items),
        "contaminationDecisive": sum(1 for i in items for c in i["contamination"] if c.get("decisive")),
        "spuriousValues": spurious,
        "valuesFilled": values,
        "spuriousRate": _rate(spurious, values),
        "crossSlotSideEffects": sum(len(a.get("crossSlot") or []) for a in attrs),
    }


def aggregate(scored: list[dict]) -> dict:
    attrs = [dict(a, id=i["id"], style=i.get("style")) for i in scored for a in i["attributes"]]
    by_attr: dict[str, dict] = {}
    groups = defaultdict(list)
    for a in attrs:
        if a["status"] != "phrase_missing":
            groups[a["attr"]].append(a)
    for name in sorted(groups):
        c = Counter(a["status"] for a in groups[name])
        slot_n = sum(1 for a in groups[name] if a["kind"] == "slot")
        by_attr[name] = {"n": len(groups[name]), "slotN": slot_n, **{s: c.get(s, 0) for s in STATUSES},
                         "reflectRate": _rate(sum(1 for a in groups[name] if a["kind"] == "slot" and a["status"] == "reflected"), slot_n)}
    by_style = {st: _summary([a for a in attrs if a["style"] == st], [i for i in scored if i.get("style") == st])
                for st in sorted({i["style"] for i in scored if i.get("style")})}
    by_item = {i["id"]: _summary(i["attributes"], [i]) for i in scored}
    return {"overall": _summary(attrs, scored), "byAttr": by_attr, "byStyle": by_style, "byItem": by_item,
            "phraseMissing": [{"id": a["id"], "phrase": a["phrase"]} for a in attrs if a["status"] == "phrase_missing"]}


def failures(scored: list[dict], runs: dict[str, dict]) -> list[dict]:
    """문서용 실패 사례 목록(결정론적 순서)."""
    out = []
    for i in scored:
        trace = (runs.get(i["id"]) or {}).get("controllerTrace") or {}
        for a in i["attributes"]:
            if a["kind"] == "slot" and a["status"] in ("distorted", "lost", "preserved", "dropped_by_controller"):
                out.append({"id": i["id"], "type": a["status"], "reason": a.get("reason"), "attr": a["attr"],
                            "phrase": a["phrase"], "slot": a["slot"], "expect": a["expect"], "actual": a.get("actual"),
                            "valueTriggers": a.get("valueTriggers"), "phraseEvidence": a.get("phraseEvidence"),
                            "crossSlot": a.get("crossSlot"), "inAlternatives": a.get("inAlternatives"),
                            "coverageAny": a.get("coverageAny"),
                            "unusedReplies": trace.get("unusedReplies") if a["status"] == "dropped_by_controller" else None})
            elif a["kind"] in ("no_slot", "slot_unscored") and a["status"] in ("lost", "dropped_by_controller"):
                out.append({"id": i["id"], "type": a["status"], "attr": a["attr"], "phrase": a["phrase"],
                            "slot": a["slot"], "kind": a["kind"], "coverageAny": a.get("coverageAny")})
            if a.get("negationError"):
                out.append({"id": i["id"], "type": "negation_error", "attr": a["attr"], "phrase": a["phrase"],
                            "slot": a["slot"], "negationError": a["negationError"]})
        for c in i["contamination"]:
            out.append({"id": i["id"], "type": "contamination", **c})
        for s in i["spurious"]:
            out.append({"id": i["id"], "type": "spurious", **s})
    return out


def score_runs(corpus: dict, runs: dict) -> dict:
    by_id = {r["id"]: r for r in runs["items"]}
    scored = [score_item(item, by_id.get(item["id"], {})) for item in corpus["items"]]
    return {"scorer": f"fidelity/{SCORER_VERSION}", "corpusId": corpus.get("corpusId"),
            "corpusVersion": corpus.get("version"), "mapper": runs.get("mapper"), "builder": runs.get("builder"),
            "analyzer": runs.get("analyzer"), "summary": aggregate(scored), "items": scored,
            "failures": failures(scored, by_id)}


# ── 출력 ────────────────────────────────────────────────────────────────────
def _fmt(v) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.3f}"
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)


def to_markdown(report: dict) -> str:
    s = report["summary"]["overall"]
    L = [f"# 일치도 채점 — {report.get('corpusId')} · 매핑 {report.get('mapper')}", "",
         f"채점기 {report['scorer']}, 코퍼스 {report.get('corpusId')}@{report.get('corpusVersion')}, "
         f"빌더 {(report.get('builder') or {}).get('builder')}", "",
         "## 전체", "", "| 지표 | 값 |", "| --- | --- |"]
    for k in ("attributes", "slotAttributes", "reflectRate", "distortRate", "lostRate", "droppedRate", "preserveRate",
              "unreflectedVerbatimRate", "negated", "negationErrors", "contamination", "contaminationDecisive",
              "spuriousValues", "valuesFilled",
              "spuriousRate"):
        L.append(f"| {k} | {_fmt(s[k])} |")
    L += ["", "슬롯 속성 상태: " + ", ".join(f"{k} {v}" for k, v in s["slotStatus"].items()), "",
          "## 속성 유형별", "", "| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, r in report["summary"]["byAttr"].items():
        L.append(f"| {name} | {r['n']} | {r['slotN']} | {r['reflected']} | {r['distorted']} | {r['preserved']} | "
                 f"{r['lost']} | {r['dropped_by_controller']} | {r['captured']} | {_fmt(r['reflectRate'])} |")
    L += ["", "## 항목별", "", "| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for iid, r in report["summary"]["byItem"].items():
        L.append(f"| {iid} | {r['slotAttributes']} | {_fmt(r['reflectRate'])} | {_fmt(r['distortRate'])} | "
                 f"{_fmt(r['preserveRate'])} | {r['contamination']} | {r['negationErrors']} | {r['spuriousValues']} |")
    L += ["", "## 실패 사례", "", "| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for f in report["failures"]:
        ev = f.get("valueTriggers") or f.get("triggers") or f.get("trigger") or f.get("negationError") or f.get("crossSlot")
        L.append(f"| {f['id']} | {f['type']}{'/' + f['reason'] if f.get('reason') else ''} | {f.get('attr') or f.get('path')} | "
                 f"{f.get('phrase', '')} | {_fmt(f.get('expect'))} | {_fmt(f.get('actual', f.get('value')))} | {_fmt(ev)} |")
    return "\n".join(L) + "\n"


def evaluate(corpus_path: str | Path, mapper="v0", out_dir: str | Path | None = None) -> dict:
    from .corpus_run import load_corpus, run_corpus
    corpus = load_corpus(corpus_path)
    runs = run_corpus(corpus, mapper)
    report = score_runs(corpus, runs)
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        dump = lambda o: json.dumps(o, ensure_ascii=False, indent=2) + "\n"  # noqa: E731
        (out / "runs.json").write_text(dump(runs), encoding="utf-8")
        (out / "report.json").write_text(dump(report), encoding="utf-8")
        (out / "report.md").write_text(to_markdown(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.fidelity", description="심상-구현 일치도 채점")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--mapper", default="v0", help="v0(기본) 또는 '모듈:factory'")
    ap.add_argument("--out", required=True, help="결과 폴더")
    args = ap.parse_args(argv)
    report = evaluate(args.corpus, args.mapper, args.out)
    s = report["summary"]["overall"]
    print(f"매핑 {report['mapper']} · 속성 {s['attributes']}개(슬롯 {s['slotAttributes']}개)")
    print(f"  반영률 {s['reflectRate']}  왜곡률 {s['distortRate']}  손실률 {s['lostRate']}  컨트롤러 탈락률 {s['droppedRate']}")
    print(f"  보존률 {s['preserveRate']}  미반영 원문 보존률 {s['unreflectedVerbatimRate']}")
    print(f"  배경 오염 {s['contamination']}(값 결정 {s['contaminationDecisive']})  부정 오류 {s['negationErrors']}/{s['negated']}  "
          f"근거 없는 값 {s['spuriousValues']}/{s['valuesFilled']}")
    print(f"결과: {Path(args.out) / 'report.md'}")


if __name__ == "__main__":
    main()
