"""G82 2차 평가 정리: results.json에 문장별 뜻 판정(meaning)과 갈래별 수치(metrics)를 적고 README용 표를 찍는다.

채점(CP19-3, 실행 전에 고정): P 문장은 cases.json의 enOk(허용 번역 목록) 안이면 '맞음'. 목록 밖이면 사람이 결과를 보고 '넓음'(상위어)
또는 '틀림'으로 적는다(POST_HOC — 이번 실행에는 목록 밖 이름이 없어 비어 있다). 채움률(기준 70%)에는 '맞음'만 넣고, 넓음 포함 수치는 참고로 병기.
오통과 = P가 아닌 갈래에서 채택(status ok)된 문장.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
POST_HOC: dict = {}            # (id, en) → (판정, 근거). 결과를 본 뒤 적음
FILL_MIN = 0.70
GROUP_KO = {"P": "사전 밖 형태", "NEG": "부정", "PAST": "과거", "OTHER": "타인의 말", "HYPO": "가정", "SIMILE": "속성 비유",
            "PERSON": "사람·몸", "ANIMAL": "동물", "MIST": "안개·불꽃류", "NONE": "형태 없음", "WORRY": "걱정 이야기 속 사물"}


def en_of(r):
    for k in ("adopted", "item"):
        if isinstance(r.get(k), dict) and isinstance(r[k].get("en"), str):
            return r[k]["en"]
    return None


def meaning(case, r):
    en = en_of(r)
    if en is None:
        return None
    if case["group"] == "P":
        if en in case["enOk"]:
            return {"en": en, "verdict": "맞음", "reason": f"허용 목록 안({case['word']})", "posthoc": False}
        v = POST_HOC.get((case["id"], en))
        return {"en": en, "verdict": v[0] if v else "미판정", "reason": v[1] if v else "목록 밖", "posthoc": True}
    return {"en": en, "verdict": "해당 없음", "reason": f"막혀야 할 갈래({GROUP_KO[case['group']]})", "posthoc": False}


def main():
    d = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]}
    by = {}
    for r in d["results"]:
        c = cases[r["id"]]
        r["meaning"] = meaning(c, r)
        g = by.setdefault(r["group"], {"n": 0, "statuses": Counter(), "candidates": 0, "reasons": Counter(), "falsePass": []})
        g["n"] += 1
        g["statuses"][r["status"] if r["status"] != "skipped" else f"skipped:{r['skipReason']}"] += 1
        g["candidates"] += bool(r.get("candidate"))
        g["reasons"].update(r.get("rejectReasons") or [])
        if r["group"] != "P" and r["status"] == "ok":
            g["falsePass"].append(r["id"])
    P = [r for r in d["results"] if r["group"] == "P"]
    right = sum(1 for r in P if r["status"] == "ok" and (r["meaning"] or {}).get("verdict") == "맞음")
    broad = sum(1 for r in P if r["status"] == "ok" and (r["meaning"] or {}).get("verdict") == "넓음")
    fp = sum(len(g["falsePass"]) for k, g in by.items() if k != "P")
    m = {"pCases": len(P), "fillRight": right, "fillRate": round(right / len(P), 3), "fillWithBroad": right + broad,
         "falsePassCount": fp, "fillPass": right / len(P) >= FILL_MIN, "blockPass": fp == 0,
         "criterionPass": fp == 0 and right / len(P) >= FILL_MIN,
         "byGroup": {k: {"n": g["n"], "statuses": dict(g["statuses"]), "candidates": g["candidates"],
                         "reasons": dict(g["reasons"]), "falsePass": g["falsePass"]} for k, g in by.items()}}
    d["metrics"] = m
    (HERE / "results.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in m.items() if k != "byGroup"}, ensure_ascii=False))
    print("| 갈래 | 문장 | 틀 | 규칙이 막음 | 부르지 않음(그 밖) | LLM null | LLM 후보 | 검증기 기각 | 채택 | 오통과 | 주된 기각 사유 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    frames = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["framesPerGroup"]
    for k, g in by.items():
        st = g["statuses"]
        rb = sum(v for s, v in st.items() if s.startswith("skipped:rule_blocked"))
        other = sum(v for s, v in st.items() if s.startswith("skipped:") and not s.startswith("skipped:rule_blocked"))
        top = ", ".join(f"{a} {b}" for a, b in g["reasons"].most_common(3)) or "—"
        print(f"| {k} {GROUP_KO[k]} | {g['n']} | {frames[k]} | {rb} | {other} | {st.get('null', 0)} | {g['candidates']} | "
              f"{st.get('rejected', 0)} | {st.get('ok', 0)} | {'—' if k == 'P' else len(g['falsePass'])} | {top} |")
    print()
    print("| ID | 낱말 | 모습 줄(셋째 줄) | 결과 | 영어 | 뜻 일치(근거) |")
    print("|---|---|---|---|---|---|")
    for r in P:
        c = cases[r["id"]]
        res = {"ok": "채택", "null": "LLM null", "rejected": "기각 " + ", ".join(r.get("rejectReasons") or [])}.get(
            r["status"], f"{r['status']} {r.get('skipReason')}")
        mm = r["meaning"]
        print(f"| {r['id']} | {c['word']} | {c['lines'][2]} | {res} | {en_of(r) or '—'} | "
              f"{'—' if mm is None else mm['verdict'] + ': ' + mm['reason']} |")
    print()
    for k, g in by.items():
        for i in g["falsePass"]:
            r = next(x for x in d["results"] if x["id"] == i)
            print(f"| {i} | {' / '.join(cases[i]['lines'])} | `{r['adopted']['quote']}` → `{r['adopted']['en']}` |")


if __name__ == "__main__":
    main()
