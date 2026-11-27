"""run-g64-e2e: 질문 종류별 답(replyBy)으로 시나리오를 재생한다.

chatbot/ifs_chatbot/simulate.py의 run()·지표·기대 확인을 그대로 쓰고, drive()만 바꾼다.
이유: 실제 LLM은 flesh_out 질문 수가 모의 LLM과 다르고(ready_to_advance로 바로 넘어가기도 함),
그러면 답 목록(replies)을 차례대로 넣는 방식은 차원 프로브 답이 다른 프로브에 들어가는 어긋남이 생긴다.
여기서는 마지막 질문의 출처(source)·단계(stage)를 보고 그 종류의 답을 넣는다. 저장소 코드는 바꾸지 않는다.

  cd chatbot
  .venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/drive_by_question.py \
      ../docs/validation/run-g64-e2e/scenarios --config bridge --out <임시 폴더>/live
  (모의 LLM: --backend offline --no-guard-model)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "chatbot"))
from ifs_chatbot import simulate  # noqa: E402

PROBES = {"fixed:probe_size_shape": "probe_size_shape", "fixed:probe_color_brightness": "probe_color_brightness",
          "fixed:probe_movement": "probe_movement"}


def _last_question(session):
    for t in reversed(session.log.turns):
        if t.get("speaker") in ("system", "interviewer") and t.get("text"):
            return t
    return {}


def drive(session, scenario, max_steps=80):
    if "replyBy" not in scenario:
        return _orig_drive(session, scenario, max_steps)
    r = scenario["replyBy"]
    lists = {"find": list(r.get("find", [])), "flesh_out": list(r.get("flesh_out", []))}
    default = scenario.get("defaultReply", "없어요")
    for _ in range(max_steps):
        a = session.awaiting
        if a == "none":
            return
        if a == "start":
            session.start()
        elif a == "soft_check":
            session.act(scenario.get("softCheck", "continue"))
        elif a == "confirm":
            session.act("confirm")
        elif a == "reply":
            q = _last_question(session)
            src, stage = q.get("source", ""), q.get("stage")
            if src == "fixed:opening":
                ans = r["opening"]
            elif src == "fixed:location":
                ans = r["location"]
            elif src == "fixed:focus_hold":
                ans = r["focus_hold"]
            elif src in ("bridge:like_what", "fixed:bridge_like_what_plain"):
                ans = r.get("bridge", default)
            elif src in PROBES:
                ans = r.get(PROBES[src], default)
            elif stage in lists and src in ("llm", "fixed:fallback"):
                ans = lists[stage].pop(0) if lists[stage] else default
            else:
                ans = default
            session.reply(ans)
    raise RuntimeError(f"{scenario['id']}: {max_steps}단계 안에 끝나지 않았습니다")


_orig_drive = simulate.drive
simulate.drive = drive

if __name__ == "__main__":
    simulate.main()
