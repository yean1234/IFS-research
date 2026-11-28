"""G82 2차 평가: 고정한 cases.json을 실제 로컬 면담 모델로 **한 번** 돌린다(합성 대사만). 결과를 본 뒤 문장·기대값·프롬프트·
검증기를 고치지 않는다.

  - Runtime(experiment 설정 + 이 프로세스 안에서만 [gen3d] on_none_llm_shape = true, 가드 모델 끔, 미리보기 끔, G77 끔, 조건 고정 끔,
    기록 파일 안 씀) + static 세션 + simulate.drive(답 세 줄, 나머지는 '없어요', 확정은 고치지 않음 → 단계 표지를 얻음)
  - llm_shape.run(세션, 매퍼 spec, 확정 텍스트) 한 번. 서버를 새로 띄우지 않고 모델을 내리지 않는다.
  - --probe: LLM을 부르지 않고 규칙 경로·위기 판정·단계 표지만 본다(문장 세트를 고정하기 전, 사전 밖 낱말이 정말 규칙 밖인지 확인용).
결과: results.json(로컬 절대 경로 없음).
실행(저장소 chatbot 폴더에서): .venv\\Scripts\\python ..\\docs\\validation\\run-g82-llm-shape-eval2\\run_eval2.py [--probe]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "chatbot"))

import httpx  # noqa: E402

from ifs_chatbot import llm_fill as lf  # noqa: E402
from ifs_chatbot import llm_shape as ls  # noqa: E402
from ifs_chatbot import none_gen as ng  # noqa: E402
from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402


def nvsmi():
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def ollama(host, path):
    try:
        return httpx.get(f"{host}{path}", timeout=10).json()
    except Exception:  # noqa: BLE001
        return None


KEYS = ("status", "skipReason", "error", "called", "candidate", "ruleRoute", "lineStages", "formSpansOpened", "rawText",
        "rawItem", "item", "rejectReasons", "adopted", "shapePromptText", "llmSeconds", "inputTextSha256",
        "validatorTextSha256", "validationInputSha256", "cacheKey")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="g82-eval2-"))
    over = {"guard.model_backend": "none", "guard.required": False, "session.log_dir": str(tmp / "logs"),
            "preview.mode": "none", "interview.lock_condition": False, "mapping.llm_fill": False,
            "gen3d.on_none_llm_shape": True}
    if a.probe:
        over["llm.backend"] = "offline"
    cfg = load_config("experiment").with_overrides(**over)
    host = cfg.llm.host
    rt = Runtime(cfg, persist_logs=False)
    assert rt.llm_shape_prompt is not None
    out = {"what": "G82 eval2 (synthetic only, single run)" + (" PROBE (no LLM)" if a.probe else ""),
           "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "config": "experiment + gen3d.on_none_llm_shape=true (in-process only), guard model none, preview none, "
                     "mapping.llm_fill=false, lock_condition=false, persist_logs=false, static condition, unedited confirm",
           "model": rt.backend.info(), "ollamaVersion": (ollama(host, "/api/version") or {}).get("version"),
           "prompt": rt.llm_shape_prompt.info(), "validatorRules": ls.VALIDATOR_RULES, "g77ValidatorRules": lf.VALIDATOR_RULES,
           "seed": cfg.gen3d.on_none_llm_shape_seed, "timeoutS": cfg.gen3d.on_none_llm_shape_timeout_s,
           "casesSha256": ls.sha256_text((HERE / "cases.json").read_text(encoding="utf-8")),
           "gpuBefore": nvsmi(), "ollamaPsBefore": [m.get("name") for m in (ollama(host, "/api/ps") or {}).get("models", [])],
           "results": []}
    t0 = time.monotonic()
    for n, c in enumerate(cases["cases"]):
        s = rt.new_session("static", f"SYN-G82E2-{c['id']}")
        drive(s, {"id": c["id"], "replies": list(c["lines"]), "defaultReply": "없어요", "confirm": "confirm"})
        norm = s.log.data.get("confirmedText") or ""
        r = {"id": c["id"], "group": c["group"], "state": s.state, "confirmedTextSha256": ls.sha256_text(norm),
             "linesMatch": norm == "\n".join(c["lines"]), "sessionFlag": lf.session_flag(s)}
        if a.probe:
            with ng._prompts_lock:
                sp = ng._load_prompts().shape_prompt(norm, mapper_spec=s.scene_spec)
                call, why = ls.rule_route(ng._load_prompts(), sp)
            r.update(ruleCall=call, ruleReason=why, lineStages=ls.line_stages(s, norm)["status"])
        else:
            try:
                rec = ls.run(s, s.scene_spec, norm)
            except Exception as exc:  # noqa: BLE001
                rec = {"status": "exception", "error": f"{type(exc).__name__}: {exc}"[:300]}
            r.update({k: rec.get(k) for k in KEYS})
        out["results"].append(r)
        rt.sessions.pop(s.id, None)
        if n % 50 == 0:
            print(n, c["id"], r.get("status") or r.get("ruleReason"), round(time.monotonic() - t0), flush=True)
    out["seconds"] = round(time.monotonic() - t0, 1)
    out["gpuAfter"] = nvsmi()
    out["ollamaPsAfter"] = [m.get("name") for m in (ollama(host, "/api/ps") or {}).get("models", [])]
    dest = Path(a.out) if a.out else HERE / ("probe.json" if a.probe else "results.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
