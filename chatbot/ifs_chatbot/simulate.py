"""시나리오 재생 · 모델 비교.

같은 참여자 답(스크립트)으로 면담을 돌려, 검증기 통과율·재생성·고정 대체·지연·안전 분기를 잰다.
「IFS 이론이란?」 2절의 권고 — "후보 3개를 같은 파일럿으로 비교해 고르고, 그 선정 절차를 논문에 쓴다" — 를
반복 가능하게 하려는 도구다. 참여자 답이 고정이므로 모델 사이의 차이는 면담자 쪽에서만 생긴다.

  python -m ifs_chatbot.simulate                                  scenarios/ 전부, config 기본 모델
  python -m ifs_chatbot.simulate scenarios/p07_storyboard.json --model gemma4:e4b --model qwen3.5:9b --runs 3
  python -m ifs_chatbot.simulate --backend offline                LLM 없이(파이프라인 점검용)
결과: reports/<시각>/summary.md, summary.json, sessions/*.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .config import Config, load_config
from .controller import Runtime, Session
from .paths import CHATBOT_DIR, SCENARIO_DIR


def load_scenarios(paths: list[str]) -> list[dict]:
    files: list[Path] = []
    for p in paths or [str(SCENARIO_DIR)]:
        path = Path(p)
        files += sorted(path.glob("*.json")) if path.is_dir() else [path]
    out = []
    for f in files:
        sc = json.loads(f.read_text(encoding="utf-8"))
        sc.setdefault("id", f.stem)
        out.append(sc)
    return out


def drive(session: Session, scenario: dict, max_steps: int = 80) -> None:
    replies = list(scenario.get("replies", []))
    soft = list(scenario.get("softCheck", ["continue"]))
    if isinstance(scenario.get("softCheck"), str):
        soft = [scenario["softCheck"]]
    confirm = scenario.get("confirm", "confirm")
    for _ in range(max_steps):
        a = session.awaiting
        if a == "none":
            return
        if a == "start":
            session.start()
        elif a == "reply":
            session.reply(replies.pop(0) if replies else scenario.get("defaultReply", "없어요"))
        elif a == "soft_check":
            session.act(soft.pop(0) if len(soft) > 1 else soft[0])
        elif a == "confirm":
            if isinstance(confirm, dict) and confirm.get("edit"):
                session.act("edit", confirm["edit"])
            else:
                session.act("confirm")
    raise RuntimeError(f"{scenario['id']}: {max_steps}단계 안에 끝나지 않았습니다")


def session_metrics(s: Session) -> dict:
    turns = s.log.data["turns"]
    attempts = [a for t in turns for a in t.get("attempts", [])]
    llm_turns = [t for t in turns if t.get("attempts")]
    reasons = Counter(r.split(":")[0] + ":" + (r.split(":")[1] if ":" in r else "") for a in attempts for r in a["reasons"])
    lat = [a["latencyMs"] for a in attempts if a.get("latencyMs")]
    questions = [t for t in turns if t.get("speaker") == "interviewer" and t.get("text")]
    return {
        "endedBy": s.log.data["endedBy"],
        "llmTurns": len(llm_turns),
        "attempts": len(attempts),
        "firstTryPass": sum(1 for t in llm_turns if t["attempts"] and t["attempts"][0]["passed"]),
        "blockedAttempts": sum(1 for a in attempts if not a["passed"]),
        "fallbacks": sum(1 for t in turns if (t.get("checks") or {}).get("fallback")),
        "regenerations": sum(max(0, len(t["attempts"]) - 1) for t in llm_turns),
        "reasons": dict(reasons),
        "latencyMsMean": round(statistics.mean(lat)) if lat else None,
        "latencyMsMax": max(lat) if lat else None,
        "interviewerQuestions": [t["text"] for t in questions],
        "softChecks": sum(1 for t in turns if t.get("source") == "fixed:soft_check"),
        "crisis": s.log.data["endedBy"] == "crisis",
        "alerts": [a["kind"] for a in s.log.data["alerts"]],
        "probes": s.log.data["capture"].get("probes"),
        "bodyRelation": (s.log.data["capture"].get("bodyRelation") or {}).get("ifsLocation"),
        "findModality": (s.log.data["capture"].get("findModality") or {}).get("labels"),
        "extracted": [a["_provenance"]["trigger"] for a in (s.log.data.get("extraction") or {}).get("attributes", [])],
    }


def check_expect(sc: dict, m: dict, s: Session) -> list[str]:
    """시나리오의 expect를 확인한다. 실패 사유 목록(비면 통과)."""
    exp, fails = sc.get("expect", {}), []
    if "endedBy" in exp and m["endedBy"] != exp["endedBy"]:
        fails.append(f"endedBy {m['endedBy']} != {exp['endedBy']}")
    if "softChecks" in exp and m["softChecks"] != exp["softChecks"]:
        fails.append(f"softChecks {m['softChecks']} != {exp['softChecks']}")
    if exp.get("noLlmAfterCrisis"):
        crisis_i = next((t["i"] for t in s.log.turns if t.get("source") == "fixed:crisis"), None)
        if crisis_i is None or any(t.get("attempts") for t in s.log.turns[crisis_i:]):
            fails.append("위기 대응 뒤에 LLM 호출이 있음")
    if "probesAsked" in exp and (m["probes"] or {}).get("asked") != exp["probesAsked"]:
        fails.append(f"probes {((m['probes'] or {}).get('asked'))} != {exp['probesAsked']}")
    if "bodyRelation" in exp and m["bodyRelation"] != exp["bodyRelation"]:
        fails.append(f"bodyRelation {m['bodyRelation']} != {exp['bodyRelation']}")
    for label in exp.get("findModalityIncludes", []):
        if label not in (m["findModality"] or []):
            fails.append(f"findModality에 {label} 없음")
    for src in exp.get("sourcesInclude", []):
        if not any(t.get("source") == src for t in s.log.turns):
            fails.append(f"{src} 문구가 나오지 않음")
    for src in exp.get("sourcesExclude", []):
        if any(t.get("source") == src for t in s.log.turns):
            fails.append(f"{src} 문구가 나옴")
    for w in exp.get("extractedIncludes", []):
        if w not in m["extracted"]:
            fails.append(f"추출에 '{w}' 없음")
    for k in exp.get("alertsInclude", []):
        if k not in m["alerts"]:
            fails.append(f"알림 {k} 없음")
    return fails


def run(cfg: Config, scenarios: list[dict], models: list[str | None], runs: int, out_dir: Path, quiet: bool = False) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sess_dir = out_dir / "sessions"
    results = []
    for model in models:
        mcfg = cfg.with_overrides(**{"llm.model": model}) if model else cfg
        mcfg = replace(mcfg, session=replace(mcfg.session, log_dir=str(sess_dir)))
        rt = Runtime(mcfg)
        label = rt.backend.info().get("name") if mcfg.llm.backend == "ollama" else f"{mcfg.llm.backend}"
        if not rt.backend_ok:
            print(f"! {label}: {rt.backend_msg}", file=sys.stderr)
        else:
            rt.backend.warmup()
        for sc in scenarios:
            for r in range(runs):
                cond = sc.get("condition", "chatbot")
                if cond == "chatbot" and not rt.backend_ok:
                    continue
                sid = f"{sc['id']}__{label.replace(':', '-').replace('/', '-')}__r{r + 1}"[:40]
                sid = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in sid)
                rt.sessions.pop(sid, None)
                s = rt.new_session(cond, sid)
                try:
                    drive(s, sc)
                    m = session_metrics(s)
                    fails = check_expect(sc, m, s)
                except Exception as exc:  # 한 시나리오가 죽어도 나머지는 돈다
                    m, fails = {"error": str(exc)}, [f"오류: {exc}"]
                results.append({"model": label, "scenario": sc["id"], "run": r + 1, "condition": cond,
                                "metrics": m, "expectFailures": fails, "log": str(s.log.path)})
                if not quiet:
                    q = " | ".join(m.get("interviewerQuestions", [])[:5]) if "interviewerQuestions" in m else ""
                    status = "OK " if not fails else "FAIL"
                    print(f"[{status}] {label:28} {sc['id']:24} r{r + 1}  {q[:110]}")
                    for f in fails:
                        print(f"        - {f}")
    summary = summarize(results)
    (out_dir / "summary.json").write_text(json.dumps({"results": results, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(to_markdown(summary, results), encoding="utf-8")
    return {"results": results, "summary": summary}


def summarize(results: list[dict]) -> dict:
    by_model: dict[str, dict] = {}
    for r in results:
        m = r["metrics"]
        if "error" in m:
            continue
        agg = by_model.setdefault(r["model"], Counter())
        agg["sessions"] += 1
        for k in ("llmTurns", "attempts", "firstTryPass", "blockedAttempts", "fallbacks", "regenerations", "softChecks"):
            agg[k] += m.get(k) or 0
        agg["expectFailures"] += len(r["expectFailures"])
        for code, n in m.get("reasons", {}).items():
            agg[f"reason {code}"] += n
        if m.get("latencyMsMean"):
            agg["latencySum"] += m["latencyMsMean"] * m["attempts"]
    out = {}
    for model, agg in by_model.items():
        llm = agg["llmTurns"] or 0
        out[model] = {
            **{k: v for k, v in agg.items() if not k.startswith("reason ") and k != "latencySum"},
            "firstTryPassRate": round(agg["firstTryPass"] / llm, 3) if llm else None,
            "fallbackRate": round(agg["fallbacks"] / llm, 3) if llm else None,
            "latencyMsMean": round(agg["latencySum"] / agg["attempts"]) if agg["attempts"] else None,
            "blockedByCheck": {k[7:]: v for k, v in sorted(agg.items()) if k.startswith("reason ")},
        }
    return out


def to_markdown(summary: dict, results: list[dict]) -> str:
    lines = ["# 시나리오 재생 결과", "", f"생성: {datetime.now().isoformat(timespec='seconds')}", "",
             "| 모델 | 세션 | LLM 턴 | 첫 시도 통과율 | 고정 대체 비율 | 차단된 시도 | 평균 지연(ms) | 기대 불일치 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for model, s in summary.items():
        lines.append(f"| {model} | {s.get('sessions', 0)} | {s.get('llmTurns', 0)} | {s.get('firstTryPassRate')} | "
                     f"{s.get('fallbackRate')} | {s.get('blockedAttempts', 0)} | {s.get('latencyMsMean')} | {s.get('expectFailures', 0)} |")
    lines += ["", "## 검사별 차단 횟수", ""]
    for model, s in summary.items():
        lines.append(f"- **{model}**: " + (", ".join(f"{k} {v}" for k, v in s["blockedByCheck"].items()) or "없음"))
    lines += ["", "## 세션별 면담자 질문", ""]
    for r in results:
        m = r["metrics"]
        mark = "✅" if not r["expectFailures"] else "❌"
        lines.append(f"### {mark} {r['scenario']} · {r['model']} · r{r['run']}")
        for q in m.get("interviewerQuestions", []):
            lines.append(f"- {q}")
        for f in r["expectFailures"]:
            lines.append(f"- ⚠ {f}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.simulate", description="시나리오 재생 · 모델 비교")
    ap.add_argument("scenarios", nargs="*", help="시나리오 JSON 파일 또는 폴더 (기본: chatbot/scenarios/)")
    ap.add_argument("--config")
    ap.add_argument("--model", action="append", help="비교할 Ollama 모델 (여러 번)")
    ap.add_argument("--backend", choices=["ollama", "offline"])
    ap.add_argument("--no-guard-model", action="store_true")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--out", default=None, help="결과 폴더 (기본: chatbot/reports/<시각>)")
    args = ap.parse_args(argv)
    cfg = load_config(args.config).with_overrides(**{
        "llm.backend": args.backend, "guard.model_backend": "none" if args.no_guard_model else None})
    out = Path(args.out) if args.out else CHATBOT_DIR / "reports" / datetime.now().strftime("%Y%m%d-%H%M%S")
    res = run(cfg, load_scenarios(args.scenarios), args.model or [None], args.runs, out)
    print(f"\n결과: {out / 'summary.md'}")
    for model, s in res["summary"].items():
        print(f"  {model}: 첫 시도 통과율 {s.get('firstTryPassRate')}, 고정 대체 비율 {s.get('fallbackRate')}, 기대 불일치 {s.get('expectFailures')}")


if __name__ == "__main__":
    main()
