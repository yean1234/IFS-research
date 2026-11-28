"""G85 요약 시트: G82 점검의 make_summary.py(docs/validation/run-g82-end-to-end/)를 불러 LLM 칸 글만 G82 + G85로 바꿔 돌린다.

  python make_summary.py --raw <run_g85_e2e.py의 --raw 폴더> [--per-sheet 4] [--title "G85 실제 흐름 점검"]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "run-g82-end-to-end" / "make_summary.py"
src = SRC.read_text(encoding="utf-8")
for a, b in (("experiment-g82 설정", "experiment-g85.toml 사본(G85 켬)"), ('("LLM 형태 이름 (G82)", 220)', '("LLM (G82 → G85)", 260)')):
    assert src.count(a) == 1, a
    src = src.replace(a, b)
assert src.count('"results.json"') == 2
src = src.replace('"results.json"', '"e2e_results.json"')     # 실제 흐름 결과(오프라인 점검 결과와 이름이 다름)
ns = {"__name__": "g85_summary", "__file__": str(HERE / "make_summary.py")}
exec(compile(src, str(SRC), "exec"), ns)
_g82_text = ns["llm_text"]


def llm_text(c):
    s = ((c.get("collected") or {}).get("summary") or {})
    lines = [f"경로 {s.get('promptRoute')}"]
    sl = s.get("shapeLlm") or {}
    raw = sl.get("rawItem")
    if sl.get("called"):
        lines.append("G82: " + (f"'{raw.get('quote')}' → {raw.get('en')}" if raw else "null") +
                     (f" · 기각 {','.join(sl.get('rejectReasons') or [])}" if sl.get("rejectReasons") else ""))
    rw = s.get("rewrite") or {}
    if rw.get("called"):
        els = rw.get("elements") or []
        lines.append("G85: " + ("; ".join(f"{e.get('en')}({'근거 ' + repr(e.get('quote')) if e.get('origin') == 'grounded' else '덧붙임'}"
                                          f"{'' if e.get('accepted') else ' 기각'})" for e in els) or "null"))
        if rw.get("rejectReasons"):
            lines.append("기각: " + ", ".join(rw["rejectReasons"])[:90])
    if rw.get("assembledPrompt"):
        lines.append("조립: " + rw["assembledPrompt"].split(",")[0])
    if c.get("basisShown"):
        lines.append("화면: " + c["basisShown"])
    for st in c.get("steps") or []:
        if st.get("addedLine"):
            lines.append("화면: " + st["addedLine"])
            break
    for st in c.get("steps") or []:
        if (st.get("llmRewriteNeutral") or {}).get("text"):
            lines.append("화면: 중립 형태 안내")
            break
    if c.get("meshRetryLine"):
        lines.append("화면: " + c["meshRetryLine"])
    mr = s.get("meshRetry") or {}
    if mr:
        lines.append(f"메시 시도 {mr.get('attemptsTotal')}번 · 돌아감 {'예' if mr.get('used') else '아니오'}")
    if rw.get("rejected"):
        lines.append("[그 말이 아니에요] 누름")
    return "\n".join(lines)


ns["llm_text"] = llm_text

if __name__ == "__main__":
    sys.argv[0] = str(HERE / "make_summary.py")
    ns["main"]()
