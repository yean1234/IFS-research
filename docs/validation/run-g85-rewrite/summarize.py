"""G85 합성 오프라인 점검 offline_results.json → summary.json + 화면 출력(사실만, 문턱 없음).

  python summarize.py
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = ("llm_word", "llm_rewrite", "rule")          # 참여자 말에서 온 형태로 생성을 시작하는 경로


def main():
    res = json.loads((HERE / "offline_results.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]}
    if (HERE / "holdout.json").is_file():
        cases.update({c["id"]: c for c in json.loads((HERE / "holdout.json").read_text(encoding="utf-8"))["cases"]})
    rows = res["results"]
    S = {"model": res.get("model"), "wordnet": res.get("wordnet"), "seconds": res.get("seconds"), "n": len(rows),
         "errors": [r["id"] for r in rows if r.get("error")]}
    by = collections.defaultdict(list)
    for r in rows:
        by[r["group"]].append(r)
    S["chainRoute"] = {g: dict(collections.Counter(r["chain"]["route"] for r in rs if r.get("chain"))) for g, rs in by.items()}
    S["forcedOutcome"] = {g: dict(collections.Counter((r["forced"][0].get("outcome") or r["forced"][0].get("skipReason")
                                                       or r["forced"][0].get("status")) for r in rs if r.get("forced")))
                          for g, rs in by.items()}
    S["forcedRoute"] = {g: dict(collections.Counter(r["forced"][0]["route"] for r in rs if r.get("forced"))) for g, rs in by.items()}

    added_acc, added_prop, grounded_acc, subj_pairs, sus = collections.Counter(), collections.Counter(), [], [], []
    span_total = span_exact = span_found = 0
    for r in rows:
        if not r.get("forced"):
            continue
        c = cases[r["id"]]
        norm = "\n".join(c["lines"])
        f = r["forced"][0]
        v = f.get("validation") or {}
        raw = f.get("rawItem") or None
        if isinstance(raw, dict) and isinstance(raw.get("subject"), dict):
            q, cs = raw["subject"].get("quote"), raw["subject"].get("charSpan")
            span_total += 1
            if isinstance(q, str) and q and q in norm:
                span_found += 1
            if isinstance(cs, list) and len(cs) == 2 and all(isinstance(x, int) for x in cs) and norm[cs[0]:cs[1]] == q:
                span_exact += 1
            for d in raw.get("details") or []:
                if isinstance(d, dict) and d.get("basis") == "none":
                    added_prop[d.get("en")] += 1
        for d in v.get("details") or []:
            if d.get("accepted") and d.get("origin") == "added" and f.get("status") == "ok":
                added_acc[d.get("en")] += 1
            if d.get("accepted") and d.get("origin") == "grounded" and f.get("status") == "ok":
                grounded_acc.append({"id": r["id"], "quote": d.get("quote"), "en": d.get("en")})
        if f.get("status") == "ok":
            sub = f["adopted"]["subject"]
            pair = {"id": r["id"], "group": r["group"], "line": c["lines"][2], "quote": sub["quote"], "en": sub["en"],
                    "details": [d["en"] + ("" if d["origin"] == "grounded" else "*") for d in f["adopted"]["details"]],
                    "prompt": (f.get("shapePromptText") or "").split(",")[0]}
            subj_pairs.append(pair)
            ok = c.get("enOk") or []
            if r["group"] == "OOV" and not any(o.replace(" ", "") in sub["en"].replace(" ", "") or
                                               sub["en"].replace(" ", "") in o.replace(" ", "") for o in ok):
                sus.append({**pair, "enOk": ok})
    S["spanMatch"] = {"subjectsProposed": span_total, "quoteInText": span_found, "charSpanExact": span_exact}
    S["addedAccepted"] = {"total": sum(added_acc.values()), "words": dict(added_acc)}
    S["addedProposed"] = {"total": sum(added_prop.values()), "words": dict(added_prop)}
    S["groundedAccepted"] = grounded_acc
    S["adoptedPairs"] = subj_pairs
    S["oovEnglishNotInEnOk"] = sus
    S["addedPerAdopted"] = dict(collections.Counter(
        sum(1 for d in r["forced"][0]["adopted"]["details"] if d["origin"] == "added")
        for r in rows if r.get("forced") and r["forced"][0].get("status") == "ok"))

    # 형태 없음 → 중립
    ns = by.get("NOSHAPE", [])
    S["noShapeNeutral"] = {"n": len(ns), "chainSystemDefault": sum(r["chain"]["route"] == "system_default" for r in ns),
                           "forcedSystemDefault": sum(r["forced"][0]["route"] == "system_default" for r in ns),
                           "notNeutral": [{"id": r["id"], "line": cases[r["id"]]["lines"][2], "chain": r["chain"]["route"],
                                           "forced": r["forced"][0]["route"], "adopted": r["forced"][0].get("adopted")}
                                          for r in ns if r["chain"]["route"] != "system_default" or r["forced"][0]["route"] != "system_default"]}
    # 오통과(생성하면 안 되는 갈래에서 말한 형태로 생성) · 오차단
    wrong = {}
    for g in ("NEG", "PAST", "OTHER", "HYPO", "SIMILE", "WORRY", "NOSHAPE"):
        lst = []
        for r in by.get(g, []):
            ch, fo = r["chain"]["route"], r["forced"][0]
            if ch in GEN or fo.get("status") == "ok":
                lst.append({"id": r["id"], "lines": cases[r["id"]]["lines"], "chain": ch,
                            "g82Adopted": (r["chain"]["g82"] or {}).get("adopted"),
                            "forcedAdopted": fo.get("adopted"), "forcedReasons": fo.get("rejectReasons")})
        wrong[g] = {"n": len(by.get(g, [])), "falsePass": len(lst), "rows": lst}
    S["falsePass"] = wrong
    S["oovFalseBlock"] = [{"id": r["id"], "line": cases[r["id"]]["lines"][2], "chain": r["chain"]["route"],
                           "reason": r["chain"]["reason"], "forced": r["forced"][0].get("outcome") or r["forced"][0].get("status"),
                           "forcedReasons": r["forced"][0].get("rejectReasons"),
                           "g82": (r["chain"]["g82"] or {}).get("rejectReasons"),
                           "raw": r["forced"][0].get("rawText")}
                          for r in by.get("OOV", []) if r["chain"]["route"] not in GEN]
    fb = by.get("FORBID", [])
    S["forbidden"] = {"n": len(fb), "chainRoute": dict(collections.Counter(r["chain"]["route"] for r in fb)),
                      "chainGenerating": [{"id": r["id"], "line": cases[r["id"]]["lines"][2], "what": cases[r["id"]]["what"],
                                           "route": r["chain"]["route"], "reason": r["chain"]["reason"],
                                           "g82Adopted": (r["chain"]["g82"] or {}).get("adopted"),
                                           "g85Adopted": (r["chain"]["g85"] or {}).get("adopted") if r["chain"]["g85"] else None}
                                          for r in fb if r["chain"]["route"] != "none"],
                      "forcedAdopted": [{"id": r["id"], "line": cases[r["id"]]["lines"][2], "adopted": r["forced"][0].get("adopted")}
                                        for r in fb if r["forced"][0].get("status") == "ok"]}
    # 2회 일치
    two = [r for r in rows if r.get("forced") and len(r["forced"]) == 2]
    S["repeat"] = {"n": len(two), "rawSame": sum(r["forced"][0].get("rawText") == r["forced"][1].get("rawText") for r in two),
                   "routeSame": sum(r["forced"][0]["route"] == r["forced"][1]["route"] for r in two),
                   "differ": [r["id"] for r in two if r["forced"][0].get("rawText") != r["forced"][1].get("rawText")]}
    # WordNet 과차단·미탐
    over, miss = [], []
    for r in rows:
        f = r["forced"][0] if r.get("forced") else {}
        v = f.get("validation") or {}
        s = v.get("subject") or {}
        reasons = s.get("rejectReasons") or []
        if r["group"] != "FORBID" and "wordnet_forbidden" in reasons:
            over.append({"id": r["id"], "group": r["group"], "en": s.get("en"), "wordnet": v.get("wordnet"),
                         "otherReasons": [x for x in reasons if x != "wordnet_forbidden"]})
        if r["group"] == "FORBID" and s.get("en") and "wordnet_forbidden" not in reasons:
            miss.append({"id": r["id"], "line": cases[r["id"]]["lines"][2], "en": s.get("en"), "otherReasons": reasons,
                         "wordnet": v.get("wordnet")})
    S["wordnet"] = {**(S["wordnet"] or {}), "overBlockNonForbidden": over, "missOnForbidden": miss}
    # (G85 판정 뒤) 몸 낱말 돌려 말하기 · 과차단 · 비유 꾸밈
    def body_row(r):
        c = cases[r["id"]]
        rr = (r["chain"]["g85"] or {}).get("ruleRoute") or (r["chain"]["g82"] or {}).get("ruleRoute") or {}
        return {"id": r["id"], "line": c["lines"][2], "route": r["chain"]["route"], "reason": r["chain"]["reason"],
                "blockReason": rr.get("blockReason")}
    bf, bo = by.get("BODYF", []), by.get("BODYOK", [])
    S["bodyForbid"] = {"n": len(bf), "chainRoute": dict(collections.Counter(r["chain"]["route"] for r in bf)),
                       "falsePass": [body_row(r) for r in bf if r["chain"]["route"] != "none"]}
    S["bodyOk"] = {"n": len(bo), "chainRoute": dict(collections.Counter(r["chain"]["route"] for r in bo)),
                   "blockedBodyAttachment": [body_row(r) for r in bo if "body_part_attachment" in str(r["chain"]["reason"])],
                   "notGenerating": [body_row(r) for r in bo if r["chain"]["route"] not in GEN]}
    hf, ho = by.get("HOLDF", []), by.get("HOLDOK", [])
    S["holdForbid"] = {"n": len(hf), "chainRoute": dict(collections.Counter(r["chain"]["route"] for r in hf)),
                       "falsePass": [body_row(r) for r in hf if r["chain"]["route"] != "none"]}
    S["holdOk"] = {"n": len(ho), "chainRoute": dict(collections.Counter(r["chain"]["route"] for r in ho)),
                   "blockedBodyAttachment": [body_row(r) for r in ho if "body_part_attachment" in str(r["chain"]["reason"])],
                   "notGenerating": [body_row(r) for r in ho if r["chain"]["route"] not in GEN]}
    S["bodyAttachmentByGroup"] = {g: sum("body_part_attachment" in str(r["chain"]["reason"]) for r in rs) for g, rs in by.items()}
    sim_rej = sim_acc = 0
    for r in rows:
        for d in ((r.get("forced") or [{}])[0].get("validation") or {}).get("details") or []:
            if d.get("origin") == "grounded":
                q = d.get("quote") or ""
                if "simile_detail" in (d.get("rejectReasons") or []):
                    sim_rej += 1
                elif d.get("accepted") and any(m in q for m in ("처럼", "같이", "같은", "마냥")):
                    sim_acc += 1
    S["simileDetail"] = {"rejected": sim_rej, "acceptedWithSimileQuote": sim_acc}
    S["groundedDetailReasons"] = dict(collections.Counter(
        x for r in rows for d in ((r.get("forced") or [{}])[0].get("validation") or {}).get("details") or []
        if d.get("origin") == "grounded" for x in (d.get("rejectReasons") or ["ACCEPTED"])))
    (HERE / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    for k in ("n", "errors", "seconds", "chainRoute", "forcedOutcome", "spanMatch", "addedAccepted", "addedProposed",
              "addedPerAdopted", "repeat"):
        print(k, json.dumps(S[k], ensure_ascii=False))
    print("noShapeNeutral", {k: v for k, v in S["noShapeNeutral"].items() if k != "notNeutral"})
    for x in S["noShapeNeutral"]["notNeutral"]:
        print("   ", x)
    for g, v in wrong.items():
        print("falsePass", g, v["n"], v["falsePass"])
        for x in v["rows"]:
            print("    ", x["id"], x["lines"][2], x["chain"], (x["forcedAdopted"] or {}).get("subject"))
    print("oovFalseBlock", len(S["oovFalseBlock"]))
    for x in S["oovFalseBlock"]:
        print("    ", x["id"], x["line"], x["chain"], x["reason"], x["forced"], x["forcedReasons"], (x["raw"] or "")[:160])
    print("forbidden", S["forbidden"]["chainRoute"])
    for x in S["forbidden"]["chainGenerating"]:
        print("    GEN", x)
    for x in S["forbidden"]["forcedAdopted"]:
        print("    FORCED", x)
    print("bodyForbid", S["bodyForbid"]["chainRoute"])
    for x in S["bodyForbid"]["falsePass"]:
        print("    PASS", x)
    print("bodyOk", S["bodyOk"]["chainRoute"], "blockedBPA", len(S["bodyOk"]["blockedBodyAttachment"]))
    for x in S["bodyOk"]["notGenerating"]:
        print("    NOGEN", x)
    print("holdForbid", S["holdForbid"]["chainRoute"])
    for x in S["holdForbid"]["falsePass"]:
        print("    PASS", x)
    print("holdOk", S["holdOk"]["chainRoute"], "blockedBPA", len(S["holdOk"]["blockedBodyAttachment"]))
    for x in S["holdOk"]["notGenerating"]:
        print("    NOGEN", x)
    print("bodyAttachmentByGroup", S["bodyAttachmentByGroup"])
    print("simileDetail", S["simileDetail"], "groundedDetailReasons", S["groundedDetailReasons"])
    print("wordnet over", [(x["id"], x["en"]) for x in over], "miss", [(x["id"], x["en"], x["otherReasons"]) for x in miss])
    print("grounded", [(x["quote"], x["en"]) for x in grounded_acc])
    print("susp", [(x["id"], x["quote"], x["en"]) for x in sus])
    for p in subj_pairs:
        print("  pair", p["id"], p["line"], "→", p["prompt"])


if __name__ == "__main__":
    main()
