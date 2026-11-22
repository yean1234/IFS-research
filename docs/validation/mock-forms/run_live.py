"""조건 2(AI 챗봇 면담) 라이브 재생 — mock_corpus.json에서 live 필드가 있는 항목을 실제 컨트롤러에 넣는다.

로컬 Ollama(config 기본 모델 gemma4:e4b)와 가드 모델을 config 그대로 쓴다. 외부 API 없음.
고정 문구 차례에는 corpus_run과 같은 키(opening·location·focus·프로브)의 합성 답을, LLM 질문 차례에는
live.find(Find 단계) / [replies.fleshout] + live.flesh_out_extra(Flesh out 단계)를 순서대로 넣는다.
목록이 떨어지면 "더 떠오르는 건 없어요."라고 답한다(합성). 안전 검사·soft check·건너뛰기·확정은 실제 경로 그대로.
세션 로그와 장면 파일은 임시 폴더(--work)에 쓴다. 결과(대화 기록·검증기·확정 텍스트·SceneSpec)는 --out에.

  cd chatbot
  .venv\\Scripts\\python.exe ..\\docs\\validation\\mock-forms\\run_live.py --work <임시 폴더> --out ..\\docs\\validation\\mock-forms\\live
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

CHATBOT = Path(__file__).resolve().parents[3] / "chatbot"
sys.path.insert(0, str(CHATBOT))

from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.eval.corpus_run import FIXED_REPLY_KEYS  # noqa: E402
from ifs_chatbot.korean import normalize  # noqa: E402
from ifs_chatbot.scene_builder_v1 import factory as v1_factory  # noqa: E402

NO_MORE = "더 떠오르는 건 없어요."
CORPUS = Path(__file__).resolve().parent / "mock_corpus.json"


def drive(s, item: dict, max_steps: int = 120) -> dict:
    rep = item["replies"]
    live = item["live"]
    queues = {"find": list(live.get("find") or []),
              "flesh_out": [rep["fleshout"]] + list(live.get("flesh_out_extra") or [])}
    used, soft = [], 0
    for _ in range(max_steps):
        a = s.awaiting
        if a == "none":
            break
        if a == "start":
            s.start()
        elif a == "reply":
            st = s.step
            if st.type == "fixed":
                key = FIXED_REPLY_KEYS.get(st.phrase, st.phrase)
                text = rep.get(key)
            elif st.type == "probes":
                cur = s.step_state[s.idx].get("current")
                key = f"probe_{cur}" if cur else None
                text = rep.get(key) if key else None
            elif st.type == "llm":
                key = f"llm:{st.stage}"
                q = queues.get(st.stage) or []
                text = q.pop(0) if q else NO_MORE
            else:
                key, text = st.type, None
            if text is None or not normalize(text):
                used.append({"key": key, "action": "skip"})
                s.act("skip")
            else:
                used.append({"key": key, "reply": text})
                s.reply(text)
        elif a == "soft_check":
            soft += 1
            s.act("continue")
        elif a == "confirm":
            s.act("confirm")
        else:
            raise RuntimeError(f"모르는 대기 상태: {a}")
    else:
        raise RuntimeError(f"{item['id']}: {max_steps}단계 안에 끝나지 않음")
    return {"inputs": used, "softChecks": soft}


def summarize_turns(turns: list[dict]) -> list[dict]:
    out = []
    for t in turns:
        row = {k: t.get(k) for k in ("i", "speaker", "source", "stage", "probe", "text", "note") if k in t}
        if isinstance(t.get("output"), dict) and t["output"].get("move"):
            row["move"] = t["output"]["move"]          # ready_to_advance면 text가 비고 참여자에게 나가지 않는다
        if t.get("attempts"):
            row["attempts"] = [{"attempt": a.get("attempt"), "passed": a.get("passed"),
                                "reasons": a.get("reasons"),
                                "utterance": (a.get("parsed") or {}).get("utterance"),
                                "template": (a.get("parsed") or {}).get("template"),
                                "anchor": (a.get("parsed") or {}).get("anchor"),
                                "latencyMs": a.get("latencyMs")} for a in t["attempts"]]
        if t.get("checks"):
            row["checks"] = t["checks"]
        out.append(row)
    return out


def main(argv=None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", help="쉼표 구분. 없으면 live 필드가 있는 항목 전부")
    args = ap.parse_args(argv)
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    items = [it for it in corpus["items"] if it.get("live")]
    if args.ids:
        want = set(args.ids.split(","))
        items = [it for it in items if it["id"] in want]
    work = Path(args.work)
    out = Path(args.out)
    (out / "specs").mkdir(parents=True, exist_ok=True)
    cfg = load_config().with_overrides(**{
        "interview.condition": "chatbot",
        "session.log_dir": str(work / "logs"), "session.scenes_dir": str(work / "scenes"),
        "mapping.mode": "v0", "mapping.save_both": False, "mapping.clarify_loop": False,
    })
    rt = Runtime(cfg, persist_logs=True)
    print("경고:", rt.warnings)
    v0_builder = rt.scene_builder
    rt.scene_builder = v1_factory(rt)
    header = rt.header("chatbot")
    summary = []
    for it in items:
        sid = f"{it['id']}-live"
        t0 = time.time()
        s = rt.new_session("chatbot", sid)
        d = drive(s, it)
        data = s.log.data
        turns = summarize_turns(data["turns"])
        llm_turns = [t for t in data["turns"] if t.get("attempts")]
        attempts = [a for t in llm_turns for a in t["attempts"]]
        confirmed = data.get("confirmedText")
        spec_v1 = s.scene_spec
        spec_v0 = None
        if confirmed:
            spec_v0 = v0_builder.build(confirmed, session_id=sid, participant_id=None, condition="chatbot")
        rec = {
            "id": it["id"], "synthetic": True, "condition": "chatbot",
            "elapsedSec": round(time.time() - t0, 1),
            "endedBy": data.get("endedBy"),
            "llmTurns": len(llm_turns),
            "attempts": len(attempts),
            "firstTryPass": sum(1 for t in llm_turns if t["attempts"][0].get("passed")),
            "blockedAttempts": sum(1 for a in attempts if not a.get("passed")),
            "fallbacks": sum(1 for t in data["turns"] if (t.get("checks") or {}).get("fallback")),
            "blockReasons": sorted({r for a in attempts if not a.get("passed") for r in a.get("reasons") or []}),
            "softChecks": d["softChecks"],
            "probes": (data.get("capture") or {}).get("probes"),
            "alerts": [{"kind": a["kind"], "detail": a["detail"]} for a in data.get("alerts", [])],
            "inputs": d["inputs"],
            "turns": turns,
            "confirmedText": confirmed,
        }
        (out / f"{it['id']}.live.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if spec_v1 is not None and s.scene_path and Path(s.scene_path).exists():
            (out / "specs" / f"{it['id']}.live.v1.json").write_bytes(Path(s.scene_path).read_bytes())
        if spec_v0 is not None:
            (out / "specs_v0_from_live_text").mkdir(exist_ok=True)
            (out / "specs_v0_from_live_text" / f"{it['id']}.live.v0.json").write_text(
                json.dumps(spec_v0, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary.append({k: rec[k] for k in ("id", "endedBy", "llmTurns", "attempts", "firstTryPass",
                                            "blockedAttempts", "fallbacks", "blockReasons", "softChecks",
                                            "elapsedSec")})
        print(json.dumps(summary[-1], ensure_ascii=False))
    meta = {"model": header.get("model") if isinstance(header, dict) else None, "header": header,
            "warnings": rt.warnings, "items": summary}
    (out / "summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
