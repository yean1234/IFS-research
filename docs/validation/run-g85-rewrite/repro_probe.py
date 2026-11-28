"""G85 재현성 원인 확인(합성 대사만): 같은 G85 호출을 앞 요청 상태만 바꿔 세 번 부르고 원시 출력과 Ollama의 prompt_eval_count를 견준다.

  A: G82 호출 바로 뒤(세션 흐름과 같음)   B: A 바로 뒤 같은 요청을 한 번 더(앞 요청과 프롬프트가 같음 → KV 캐시 재사용)
  C: 관계없는 짧은 요청('.') 바로 뒤
  D: (고친 뒤) backend.structured(..., fresh_context=True) — 매 호출 앞에 짧은 요청으로 KV 캐시를 비움

  chatbot/.venv/Scripts/python.exe repro_probe.py [--n 40]  → repro_probe.json
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_g85_check as rc  # noqa: E402
from ifs_chatbot import llm_rewrite as lr  # noqa: E402
from ifs_chatbot import llm_shape as ls  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    cases = [c for c in json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
             if c["group"] in ("OOV", "NOSHAPE", "PAST", "OTHER", "HYPO", "FORBID", "WORRY")]
    step = max(1, len(cases) // a.n)
    cases = cases[::step][:a.n]
    rt, cfg = rc.runtime(False)
    be = rt.backend
    log = []
    orig = be.structured

    def spy(system, user, schema, **kw):
        r = orig(system, user, schema, **kw)
        log.append({"kind": "g85" if "subject" in json.dumps(schema) else "g82", "raw": r.raw,
                    "promptEval": (r.meta or {}).get("prompt_eval_count")})
        return r
    be.structured = spy
    g = cfg.gen3d
    rows = []
    for c in cases:
        s, norm = rc.session(rt, f"SYN-G85R-{c['id']}", c["lines"])
        st = ls.line_stages(s, norm)

        def g85(fresh=False):
            n0 = len(log)
            lr.propose(rt.llm_rewrite_prompt, be, norm, s.scene_spec, seed=int(g.on_none_llm_rewrite_seed),
                       timeout_s=float(g.on_none_llm_rewrite_timeout_s), cache={}, flag=None, stages=st, g82=None,
                       fresh_context=fresh)
            x = [e for e in log[n0:] if e["kind"] == "g85"]
            return x[-1] if x else None
        ls.propose(rt.llm_shape_prompt, be, norm, s.scene_spec, seed=0, timeout_s=20, cache={}, flag=None, stages=st)
        A = g85()
        B = g85()
        be.prime_context()
        C = g85()
        D1 = g85(True)
        D2 = g85(True)
        rows.append({"id": c["id"], **{k: v for k, v in zip("ABCDE", (A, B, C, D1, D2))}})
        rt.sessions.pop(s.id, None)
    ok = [r for r in rows if all(r[k] for k in "ABCDE")]

    def same(x, y):
        return sum(r[x]["raw"] == r[y]["raw"] for r in ok)
    out = {"n": len(ok), "A==B": same("A", "B"), "A==C": same("A", "C"), "B==C": same("B", "C"),
           "D1==D2": same("D", "E"), "A==D1": same("A", "D"), "C==D1": same("C", "D"),
           "promptEval": {k: sorted({r[k]["promptEval"] for r in ok})[:6] for k in "ABCDE"},
           "promptEvalMedian": {k: sorted(r[k]["promptEval"] or 0 for r in ok)[len(ok) // 2] for k in "ABCDE"},
           "differAB": [r["id"] for r in ok if r["A"]["raw"] != r["B"]["raw"]],
           "differD": [r["id"] for r in ok if r["D"]["raw"] != r["E"]["raw"]]}
    (HERE / "repro_probe.json").write_text(json.dumps({"summary": out, "rows": rows}, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
