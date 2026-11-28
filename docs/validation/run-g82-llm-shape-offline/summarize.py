"""G82 오프라인 평가 결과 정리: results*.json에 문장별 뜻 판정과 갈래별 수치(metrics)를 적고, README용 표를 찍는다.

뜻 판정(영어 이름이 인용된 한국어 형태와 뜻이 맞는가):
  - run_g82.CASES의 enOk(결과를 보기 전에 적음)에 있으면 '맞음', 근거 '미리 정한 이름'.
  - 그 밖의 이름은 아래 POST_HOC에 결과를 본 뒤 사람이 적은 판정과 근거 한 마디(posthoc: true로 표시).
채움률은 사전 밖 형태(P) 문장 가운데 채택되었고 뜻이 맞는 것만 센다. 오통과 = N·F·B·W 문장에서 채택된 것.
통과 기준(docs/decisions.md G82, 결과를 보기 전에 고정): 오통과 0건 그리고 뜻 맞는 채움 70% 이상. 회차마다 따로 본다.

실행: python summarize.py results.json results.prompt-0.1.0.validator-0.1.0.json ...
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLOCK_GROUPS = ("N", "F", "B", "W")
FILL_MIN = 0.70

# (문장 id, 영어 이름) → (판정, 근거). 결과를 본 뒤 적음. 판정: 맞음 · 넓음(맞지만 덜 구체적, 맞음으로 셈) · 틀림 · 해당 없음
POST_HOC = {
    ("P04", "glass marble"): ("맞음", "유리구슬=유리 구슬. 다만 재료 낱말 포함"),
    ("P05", "wooden box"): ("맞음", "나무상자. 다만 재료 낱말 포함"),
    ("P10", "metal"): ("틀림", "쇳덩이는 쇠 덩어리. 재료 이름만 냄"),
    ("P16", "snowball"): ("맞음", "눈덩이=snowball"),
    ("F03", "stone"): ("넓음", "돌덩이→stone(막혀야 할 문장)"),
    ("F04", "brick"): ("맞음", "벽돌(막혀야 할 문장)"),
    ("F05", "pebble"): ("맞음", "조약돌(막혀야 할 문장)"),
    ("F06", "board"): ("맞음", "판때기(막혀야 할 문장)"),
    ("F07", "brick"): ("맞음", "벽돌(막혀야 할 문장)"),
    ("F08", "pebble"): ("넓음", "자갈→pebble(막혀야 할 문장)"),
    ("B01", "sparrow"): ("맞음", "참새. 번역은 맞고 금지 범주"),
    ("B01", "thing"): ("틀림", "형식 명사 '게'를 인용"),
    ("B02", "squirrel"): ("맞음", "다람쥐. 번역은 맞고 금지 범주"),
    ("B03", "scarecrow"): ("맞음", "허수아비. 번역은 맞고 사람 형상"),
    ("B06", "torch"): ("맞음", "횃불. 번역은 맞고 불꽃 범주"),
    ("W03", "desk"): ("맞음", "책상. 번역은 맞지만 걱정 이야기 속 사물"),
}


def meaning(case: dict, run: dict) -> dict | None:
    item = run.get("item") or (run.get("adopted"))
    raw = run.get("rawItem")
    en = (item or {}).get("en") if item else (raw or {}).get("en") if isinstance(raw, dict) else None
    if en is None:
        return None
    if en in (case.get("enOk") or []):
        v = "넓음" if (case["id"] in ("P03", "P19") and en == "stone") else "맞음"
        return {"en": en, "verdict": v, "reason": "미리 정한 이름", "posthoc": False}
    if (case["id"], en) in POST_HOC:
        v, r = POST_HOC[(case["id"], en)]
        return {"en": en, "verdict": v, "reason": r, "posthoc": True}
    return {"en": en, "verdict": "미판정", "reason": "판정 없음", "posthoc": True}


def metrics(d: dict) -> dict:
    out = {}
    nruns = max(len(c["runs"]) for c in d["cases"])
    for r in range(nruns):
        P = [c for c in d["cases"] if c["group"] == "P"]
        fill = sum(1 for c in P if c["runs"][r]["status"] == "ok"
                   and (meaning(c, c["runs"][r]) or {}).get("verdict") in ("맞음", "넓음"))
        adopted = sum(1 for c in P if c["runs"][r]["status"] == "ok")
        fp = [c["id"] for c in d["cases"] if c["group"] in BLOCK_GROUPS and c["runs"][r]["status"] == "ok"]
        by = {}
        for g in ("P", "N", "F", "B", "W", "R"):
            cs = [c for c in d["cases"] if c["group"] == g]
            st = {}
            for c in cs:
                k = c["runs"][r]["status"] if c["runs"][r]["status"] != "skipped" else "skipped:" + str(c["runs"][r]["skipReason"])
                st[k] = st.get(k, 0) + 1
            by[g] = {"n": len(cs), "statuses": st}
        out[f"run{r + 1}"] = {"pCases": len(P), "adopted": adopted, "meaningCorrectFill": fill,
                              "fillRate": round(fill / len(P), 3), "falsePass": fp, "falsePassCount": len(fp),
                              "criterionPass": len(fp) == 0 and fill / len(P) >= FILL_MIN, "byGroup": by}
    out["rawIdentical"] = sum(1 for c in d["cases"] if all(x.get("rawText") == c["runs"][0].get("rawText") for x in c["runs"]))
    out["decisionIdentical"] = sum(1 for c in d["cases"] if all(
        x.get("status") == c["runs"][0].get("status") and x.get("adopted") == c["runs"][0].get("adopted")
        and x.get("rejectReasons") == c["runs"][0].get("rejectReasons") for x in c["runs"]))
    out["cases"] = len(d["cases"])
    out["criterion"] = f"falsePass == 0 (groups {'/'.join(BLOCK_GROUPS)}) and meaningCorrectFill / P >= {FILL_MIN}"
    return out


def where(run: dict) -> str:
    st = run["status"]
    if st == "ok":
        return f"채택 `{run['adopted']['en']}`"
    if st == "rejected":
        en = (run.get("item") or {}).get("en")
        return f"검증기 기각 `{en}` ({', '.join(run['rejectReasons'])})"
    if st == "null":
        return "LLM null"
    if st == "skipped":
        return f"부르지 않음 ({run['skipReason']})"
    return f"{st}: {run.get('error')}"


def table(d: dict) -> str:
    rows = ["| ID | 갈래 | 입력 | 기대 | 1회 결과 | 2회 같음(원시/판정) | 뜻 일치 (근거) |", "|---|---|---|---|---|---|---|"]
    for c in d["cases"]:
        r0 = c["runs"][0]
        m = meaning(c, r0)
        raw_same = all(x.get("rawText") == r0.get("rawText") for x in c["runs"])
        dec_same = all(x.get("status") == r0.get("status") and x.get("adopted") == r0.get("adopted") for x in c["runs"])
        second = "" if dec_same else f" / 2회: {where(c['runs'][1])}"
        exp = {"fill": f"채움({c['expectKo']})", "none": "막힘", "rule": "규칙 경로(부르지 않음)"}[c["expect"]]
        mm = "—" if m is None else f"{m['verdict']}{' (사후)' if m['posthoc'] else ''}: {m['reason']}"
        text = c["text"].replace("\n", " / ")
        rows.append(f"| {c['id']} | {c['group']} | {text} | {exp} | {where(r0)}{second} | "
                    f"{'예' if raw_same else '아니오'}/{'예' if dec_same else '아니오'} | {mm} |")
    return "\n".join(rows)


def main():
    files = sys.argv[1:] or ["results.json"]
    for f in files:
        p = Path(f) if Path(f).is_absolute() else HERE / f
        d = json.loads(p.read_text(encoding="utf-8"))
        for c in d["cases"]:
            for r in c["runs"]:
                r["meaning"] = meaning(c, r)
        d["metrics"] = metrics(d)
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        m = d["metrics"]
        print(f"## {p.name} (prompt {d['prompt']['promptVersion']}, validator {d['validatorRules']})")
        for k in ("run1", "run2"):
            if k in m:
                x = m[k]
                print(f"- {k}: 뜻 맞는 채움 {x['meaningCorrectFill']}/{x['pCases']} ({x['fillRate']:.1%}), 채택 {x['adopted']}, "
                      f"오통과 {x['falsePassCount']} {x['falsePass']}, 기준 {'통과' if x['criterionPass'] else '미달'}")
                print("  ", {g: v["statuses"] for g, v in x["byGroup"].items()})
        print(f"- 2회 원시 출력 같음 {m['rawIdentical']}/{m['cases']}, 판정 같음 {m['decisionIdentical']}/{m['cases']}")
        print()
        print(table(d))
        print()


if __name__ == "__main__":
    main()
