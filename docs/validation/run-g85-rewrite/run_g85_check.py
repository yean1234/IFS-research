"""G85 합성 오프라인 점검: 고정한 cases.json을 실제 로컬 면담 모델로 돌린다(합성 대사만, 그림·메시 없음).

  - Runtime(시험 설정 experiment-g85 = experiment + G85 켬, 가드 모델 끔, 미리보기 끔, G77 끔, 조건 고정 끔, 기록 파일 안 씀)
    + static 세션 + simulate.drive(답 세 줄, 나머지 '없어요', 확정은 고치지 않음 → 단계 표지를 얻음)
  - 세션 흐름 그대로(chain): G82 llm_shape.run → 채택 못 하면 G85 llm_rewrite.run → decide_route. 실제로 탄 경로.
  - G85 단독(forced): 같은 세션에서 G82 결과를 주지 않고 G85를 부름(G85 출력의 질을 모든 갈래에서 보려고). 새 캐시로 두 번(run1·run2)
    — 같은 입력 반복 일치.
  - --probe: LLM을 부르지 않고 낱말 후보의 규칙 경로만 본다(사전 밖 낱말 고르기, words_ok.json).
결과: offline_results.json(로컬 절대 경로 없음).
실행(저장소 chatbot 폴더에서): .venv\\Scripts\\python ..\\docs\\validation\\run-g85-rewrite\\run_g85_check.py [--probe]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "chatbot"))
sys.path.insert(0, str(HERE.parent / "run-g82-llm-shape-eval3"))

from run_eval3 import nvsmi, ollama  # noqa: E402

from ifs_chatbot import llm_fill as lf  # noqa: E402
from ifs_chatbot import llm_rewrite as lr  # noqa: E402
from ifs_chatbot import llm_shape as ls  # noqa: E402
from ifs_chatbot import none_gen as ng  # noqa: E402
from ifs_chatbot import wordnet_check as wnc  # noqa: E402
from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402

G82_KEYS = ("status", "skipReason", "rawText", "rejectReasons", "adopted", "ruleRoute")
G85_KEYS = ("status", "skipReason", "outcome", "error", "called", "candidate", "rawText", "rawItem", "rejectReasons", "forbidden",
            "adopted", "shapePromptText", "addedCount", "groundedDetailCount", "llmSeconds", "validation", "ruleRoute",
            "ruleContextDropped", "lineStages", "cached", "contextPrime", "rawTextSha256")


def runtime(probe: bool):
    tmp = Path(tempfile.mkdtemp(prefix="g85-check-"))
    over = {"guard.model_backend": "none", "guard.required": False, "session.log_dir": str(tmp / "logs"),
            "preview.mode": "none", "interview.lock_condition": False, "mapping.llm_fill": False}
    if probe:
        over["llm.backend"] = "offline"
    cfg = load_config("experiment-g85").with_overrides(**over)
    rt = Runtime(cfg, persist_logs=False)
    assert rt.llm_rewrite_prompt is not None and rt.llm_shape_prompt is not None
    return rt, cfg


def session(rt, sid, lines):
    s = rt.new_session("static", sid)
    drive(s, {"id": sid, "replies": list(lines), "defaultReply": "없어요", "confirm": "confirm"})
    return s, s.log.data.get("confirmedText") or ""


def probe():
    sys.path.insert(0, str(HERE))
    import build_cases as bc
    rt, _ = runtime(True)
    ok, out = [], []
    for w, _en in bc.CANDIDATES:
        f = bc.forms(w)
        reasons = []
        for t in (f"{w}{f['ye']}", f"{w} 같은 게 있어요", f"{w}{f['ga']} 보여요"):
            s, norm = session(rt, f"SYN-G85P-{len(out)}", [bc.WORRY_L1[0], bc.BODY_L2[0], t])
            with ng._prompts_lock:
                sp = ng._load_prompts().shape_prompt(norm, mapper_spec=s.scene_spec, stage_rule=ls.session_stage_rule(s, norm))
                call, why = ls.rule_route(ng._load_prompts(), sp)
            reasons.append(why)
            rt.sessions.pop(s.id, None)
        out.append({"word": w, "ruleReasons": reasons})
        if all(r == "no_shape_stated" for r in reasons):
            ok.append(w)
    (HERE / "words_ok.json").write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(ok), "ok of", len(out))
    for r in out:
        if r["word"] not in ok:
            print("  drop", r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args()
    if a.probe:
        return probe()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    hold = HERE / "holdout.json"                       # (3차) 규칙을 고치기 전에 고정한 보류 세트 40문장도 함께
    if hold.is_file():
        cases["cases"] = cases["cases"] + json.loads(hold.read_text(encoding="utf-8"))["cases"]
    rt, cfg = runtime(False)
    host = cfg.llm.host
    out = {"what": "G85 synthetic offline check (synthetic only)", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "config": "experiment-g85 (= experiment + G85 on + mesh retry + selection protocol 0.14), guard model none, preview none, "
                     "mapping.llm_fill=false, lock_condition=false, persist_logs=false, static condition, unedited confirm",
           "model": rt.backend.info(), "ollamaVersion": (ollama(host, "/api/version") or {}).get("version"),
           "g82Prompt": rt.llm_shape_prompt.info(), "g85Prompt": rt.llm_rewrite_prompt.info(ng._load_prompts()),
           "validatorRules": {"g85": lr.VALIDATOR_RULES, "g82": ls.VALIDATOR_RULES, "g77": lf.VALIDATOR_RULES},
           "wordnet": wnc.info(), "seed": cfg.gen3d.on_none_llm_rewrite_seed,
           "casesSha256": ls.sha256_text((HERE / "cases.json").read_text(encoding="utf-8")),
           "holdoutSha256": ls.sha256_text(hold.read_text(encoding="utf-8")) if hold.is_file() else None,
           "gpuBefore": nvsmi(), "ollamaPsBefore": [m.get("name") for m in (ollama(host, "/api/ps") or {}).get("models", [])],
           "results": []}
    t0 = time.monotonic()
    g = cfg.gen3d
    for n, c in enumerate(cases["cases"]):
        s, norm = session(rt, f"SYN-G85C-{c['id']}", c["lines"])
        r = {"id": c["id"], "group": c["group"], "state": s.state, "linesMatch": norm == "\n".join(c["lines"]),
             "sessionFlag": lf.session_flag(s), "lineStages": ls.line_stages(s, norm)["status"]}
        try:
            g82 = ls.run(s, s.scene_spec, norm)
            g85 = None
            if not (g82.get("status") == "ok" and g82.get("adopted")):
                g85 = lr.run(s, s.scene_spec, norm, g82)
            rule_reason = ((g85 or {}).get("ruleRoute") or g82.get("ruleRoute") or {}).get("reason")
            if g82.get("status") == "ok" and g82.get("adopted"):
                chain = ("llm_word", "g82_adopted")
            elif (g82.get("ruleRoute") or {}).get("reason") == "rule_has_shape":
                chain = ("rule", "rule_has_shape")
            else:
                chain = lr.decide_route(g85, rule_reason)
            r["chain"] = {"route": chain[0], "reason": chain[1], "g82": {k: g82.get(k) for k in G82_KEYS},
                          "g85": {k: (g85 or {}).get(k) for k in G85_KEYS} if g85 else None}
            forced = []
            for _ in range(2):
                rec = lr.propose(rt.llm_rewrite_prompt, rt.backend, norm, s.scene_spec, seed=int(g.on_none_llm_rewrite_seed),
                                 timeout_s=float(g.on_none_llm_rewrite_timeout_s), cache={}, flag=lf.session_flag(s),
                                 stages=ls.line_stages(s, norm), g82=None)
                fr = {k: rec.get(k) for k in G85_KEYS}
                fr["route"] = lr.decide_route(rec, (rec.get("ruleRoute") or {}).get("reason"))[0]
                forced.append(fr)
            r["forced"] = forced
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
        out["results"].append(r)
        rt.sessions.pop(s.id, None)
        if n % 20 == 0:
            print(n, c["id"], (r.get("chain") or {}).get("route"), round(time.monotonic() - t0), flush=True)
    out["seconds"] = round(time.monotonic() - t0, 1)
    out["gpuAfter"] = nvsmi()
    out["ollamaPsAfter"] = [m.get("name") for m in (ollama(host, "/api/ps") or {}).get("models", [])]
    (HERE / "offline_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
