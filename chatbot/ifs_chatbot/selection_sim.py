"""합성 시나리오로 데스크톱 1–6단계(면담 → 확정 → 추출 → 후보 → 선택 → 조절 → 사전 측정)를 끝까지 돌린다.

  python -m ifs_chatbot.selection_sim --out ../docs/validation/selection-flow/runs
  python -m ifs_chatbot.selection_sim --preview image --player <IFSPreview.exe> --out <폴더>   (후보 그림도 저장)

- 설정은 config/v4.toml(매퍼 v2, [selection] enabled)에 LLM 오프라인·가드 모델 없음을 덮어쓴다. 시나리오는 조건 1(정적)이라
  면담에서도 LLM을 부르지 않는다. 후보·조절·측정 단계는 원래 LLM·검증기를 부르지 않는다.
- 시나리오: chatbot/scenarios/selection/*.json (합성 대사만, 원칙 6).
- 결과: <out>/<시나리오 id>/ confirmed_text.txt · spec.json · candidates.json · selection.json · premeasure.json
  (+ image 모드면 candidate_<n>.png·final.png), <out>/summary.json · summary.md.
  로컬 절대 경로는 <log_dir>로 바꿔 쓴다. selection.json의 시각은 실행 때마다 다르다(나머지는 같다).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from .config import load_config
from .controller import Runtime
from .paths import SCENARIO_DIR
from .simulate import drive

SCENARIO_SUBDIR = SCENARIO_DIR / "selection"


def load(paths: list[str] | None = None) -> list[dict]:
    files: list[Path] = []
    for p in paths or [str(SCENARIO_SUBDIR)]:
        q = Path(p)
        files += sorted(q.glob("*.json")) if q.is_dir() else [q]
    out = []
    for f in files:
        sc = json.loads(f.read_text(encoding="utf-8"))
        sc.setdefault("id", f.stem)
        out.append(sc)
    return out


def make_runtime(log_dir: Path, preview: str = "none", player: str = "", backend=None) -> Runtime:
    cfg = load_config("v4").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(log_dir),
        "preview.mode": preview, "preview.image_player": player})
    return Runtime(cfg, backend=backend)


def choose(view: dict, how: str) -> str:
    """시나리오의 selection: "none" | "display:<n>"(화면 n번째, 0부터) | "index:<n>"(격자 n번)."""
    if how == "none":
        return "none"
    kind, n = how.split(":")
    n = int(n)
    if kind == "display":
        return view["candidates"][n]["id"]
    return next(c["id"] for c in view["candidates"] if c["index"] == n)


def run_one(rt: Runtime, sc: dict) -> dict:
    """1–6단계. 결과 dict(세션·흐름 객체 포함)."""
    sid = sc.get("sessionId") or sc["id"]
    rt.sessions.pop(sid, None)
    s = rt.new_session(sc.get("condition", "static"), sid, sc.get("participantId"))
    drive(s, sc)
    f = s.selection()
    view = f.start()
    view = f.select(choose(view, sc.get("selection", "display:0")))
    for step in sc.get("adjust", []):
        f.adjust(step["item"], step["value"])
    f.finish()
    items = [i["id"] for i in rt.selection_protocol.items()]
    answers = {i: (sc.get("premeasure") or {}).get(i) for i in items}
    f.submit_premeasure(answers)
    return {"session": s, "flow": f}


def check(sc: dict, f) -> list[str]:
    exp, fails = sc.get("expect", {}), []
    c = f.cands
    if "candidateCount" in exp and len(c["candidates"]) != exp["candidateCount"]:
        fails.append(f"후보 {len(c['candidates'])}개 != {exp['candidateCount']}")
    if "axes" in exp and [a["slot"] for a in c["axes"]] != exp["axes"]:
        fails.append(f"축 {[a['slot'] for a in c['axes']]} != {exp['axes']}")
    if "axisReasons" in exp and [a["reason"] for a in c["axes"]] != exp["axisReasons"]:
        fails.append(f"축 이유 {[a['reason'] for a in c['axes']]} != {exp['axisReasons']}")
    if "none" in exp and f.data["selection"]["none"] != exp["none"]:
        fails.append(f"none {f.data['selection']['none']} != {exp['none']}")
    for slot, src in (exp.get("slotSources") or {}).items():
        got = f.data["sources"][slot]
        if got != src:
            fails.append(f"{slot} 출처 {got} != {src}")
    for k, v in (exp.get("finalOverrides") or {}).items():
        if f.data["finalOverrides"].get(k) != v:
            fails.append(f"finalOverrides[{k}] {f.data['finalOverrides'].get(k)} != {v}")
    return fails


def _scrub(text: str, log_dir: Path) -> str:
    for form in {str(log_dir), str(log_dir).replace("\\", "\\\\"), log_dir.as_posix()}:
        text = text.replace(form, "<log_dir>")
    return text


def run(scenarios: list[dict], out: Path, preview: str = "none", player: str = "", quiet: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    log_dir = Path(tempfile.mkdtemp(prefix="ifs-selection-sim-"))
    rt = make_runtime(log_dir, preview, player)
    results = []
    try:
        for sc in scenarios:
            r = run_one(rt, sc)
            s, f = r["session"], r["flow"]
            d = out / sc["id"]
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
            # 줄바꿈은 LF로 고정(Windows write_text의 CRLF 변환을 피함). spec.json은 저장된 파일 바이트 그대로라
            # sha256이 selection.json의 specSha256과 같다(G26).
            (d / "confirmed_text.txt").write_text(s.log.data["confirmedText"] + "\n", encoding="utf-8", newline="\n")
            (d / "spec.json").write_bytes(Path(s.log.data["sceneSpec"]["path"]).read_bytes())
            sel_dir = f.dir
            (d / "candidates.json").write_bytes((sel_dir / "candidates.json").read_bytes())
            for name in ("selection.json", "premeasure.json"):
                (d / name).write_text(_scrub((sel_dir / name).read_text(encoding="utf-8"), log_dir), encoding="utf-8",
                                      newline="\n")
            if rt.preview.mode == "image":
                for c in f.cands["candidates"]:
                    png = rt.preview.render(f.spec, c["overrides"])
                    if png:
                        (d / f"candidate_{c['index']}.png").write_bytes(png)
                png = rt.preview.render(f.spec, f.data["finalOverrides"])
                if png:
                    (d / "final.png").write_bytes(png)
            fails = check(sc, f)
            llm_turns = sum(1 for t in s.log.turns if t.get("attempts"))
            res = {
                "scenario": sc["id"], "title": sc.get("title"), "sessionId": s.id,
                "confirmedText": s.log.data["confirmedText"],
                "candidateCount": len(f.cands["candidates"]),
                "axes": [{"slot": a["slot"], "reason": a["reason"], "values": a["values"]} for a in f.cands["axes"]],
                "note": f.cands["note"], "displayOrder": f.cands["displayOrder"],
                "selection": {k: f.data["selection"][k] for k in ("selectedIndex", "none", "displayPosition", "operationalIndex")},
                "adjustCounts": {k: v["count"] for k, v in f.data["adjustments"]["items"].items()},
                "finalOverrides": f.data["finalOverrides"], "sourceCounts": f.data["sourceCounts"],
                "sources": dict(f.data["sources"]),
                "premeasure": {i["id"]: i["value"] for i in f.premeasure["items"]},
                "interviewLlmTurns": llm_turns, "previewMode": rt.preview.mode,
                "expectFailures": fails,
            }
            results.append(res)
            if not quiet:
                print(f"[{'OK ' if not fails else 'FAIL'}] {sc['id']:28} 후보 {res['candidateCount']} 축 "
                      f"{[a['slot'] for a in res['axes']]} 선택 {'none' if res['selection']['none'] else res['selection']['selectedIndex']} "
                      f"출처 {res['sourceCounts']}")
                for x in fails:
                    print("        - " + x)
    finally:
        rt.preview.close()
        shutil.rmtree(log_dir, ignore_errors=True)
    summary = {"results": results, "previewMode": preview,
               "sourceTotals": dict(sum((Counter(r["sourceCounts"]) for r in results), Counter())),
               "expectFailures": sum(len(r["expectFailures"]) for r in results)}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                      newline="\n")
    (out / "summary.md").write_text(to_markdown(summary), encoding="utf-8", newline="\n")
    return summary


def to_markdown(summary: dict) -> str:
    lines = ["# 1–6단계 합성 시나리오 결과", "", "> 합성 대사(AI가 쓴 문장)입니다. 실제 참여자 자료가 아닙니다.", "",
             "| 시나리오 | 후보 수 | 축(이유) | 선택 | 조절 | 출처 분포(said/chosen/edited/default) | 기대 불일치 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in summary["results"]:
        axes = ", ".join(f"{a['slot']}({a['reason']})" for a in r["axes"]) or "없음"
        sel = "맞는 것이 없다 → 0번" if r["selection"]["none"] else f"{r['selection']['selectedIndex']}번(화면 {r['selection']['displayPosition'] + 1}번째)"
        sc = r["sourceCounts"]
        adj = ", ".join(f"{k}×{v}" for k, v in r["adjustCounts"].items()) or "없음"
        lines.append(f"| {r['scenario']} | {r['candidateCount']} | {axes} | {sel} | {adj} | "
                     f"{sc['said']}/{sc['chosen']}/{sc['edited']}/{sc['default']} | {len(r['expectFailures'])} |")
    lines += ["", f"미리보기 모드: {summary['previewMode']}", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.selection_sim", description="1–6단계 합성 시나리오")
    ap.add_argument("scenarios", nargs="*", help="시나리오 JSON 또는 폴더(기본: chatbot/scenarios/selection/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview", choices=["none", "image"], default="none")
    ap.add_argument("--player", default="", help="image 모드의 미리보기 플레이어(IFSPreview.exe) 또는 fake")
    a = ap.parse_args(argv)
    s = run(load(a.scenarios), Path(a.out), a.preview, a.player)
    print(f"기대 불일치 {s['expectFailures']}")
    sys.exit(1 if s["expectFailures"] else 0)


if __name__ == "__main__":
    main()
