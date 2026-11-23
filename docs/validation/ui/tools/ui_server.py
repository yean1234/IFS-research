"""ui_shots.py가 띄우는 챗봇 서버(127.0.0.1만). chatbot/.venv의 python으로 실행한다.

v4 설정(llm offline, 가드 모델 없음)으로 Runtime을 만들고, 합성 시나리오(chatbot/scenarios/selection/)로 화면별 세션을
서버 안에서 미리 그 단계까지 진행해 둔 뒤 세션 목록을 <log_dir>/ui_sessions.json에 적고 서버를 연다.
면담 대사는 모두 합성이다(AGENTS.md 6). LLM은 부르지 않는다(정적 조건).

  python ui_server.py --log-dir <폴더> --port 8795 --mode webgl|image|none [--webgl-dir <빌드>] [--player <exe>]
         [--queue-dir <폴더>] [--web-dir <이전 웹 파일 폴더>]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / "chatbot"))
import uvicorn  # noqa: E402

from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.selection_sim import choose, load  # noqa: E402
from ifs_chatbot.server import create_app  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--mode", choices=["webgl", "image", "none"], default="webgl")
    ap.add_argument("--webgl-dir", default="")
    ap.add_argument("--player", default="")
    ap.add_argument("--queue-dir", default="")
    ap.add_argument("--web-dir", default="")
    a = ap.parse_args()
    log_dir = Path(a.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    over = {"llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(log_dir),
            "preview.mode": a.mode}
    if a.mode == "webgl" and a.webgl_dir:
        over["preview.webgl_dir"] = str(Path(a.webgl_dir).resolve())
    if a.mode == "none":
        over["preview.image_player"] = ""
    elif a.player:
        over["preview.image_player"] = str(Path(a.player).resolve())
    if a.queue_dir:
        over["preview.queue_dir"] = str(Path(a.queue_dir).resolve())
    rt = Runtime(load_config("v4").with_overrides(**over))
    scs = {s["id"]: s for s in load()}
    m = a.mode.upper()
    out = {}

    # 면담 중(답 두 번 뒤, 다음 질문을 기다림)
    s = rt.new_session("static", f"SYN-UI-{m}-INT")
    s.start()
    for r in scs["S2_feeling_only"]["replies"][:2]:
        s.reply(r)
    out["interview"] = s.id
    # 확정 화면(면담을 다 했고 [이대로 맞아요]를 기다림)
    s = rt.new_session("static", f"SYN-UI-{m}-CONF")
    sc = dict(scs["S2_feeling_only"])
    sc.pop("confirm", None)
    s.start()
    for _ in range(40):
        if s.awaiting == "confirm":
            break
        if s.awaiting == "reply":
            s.reply(sc["replies"].pop(0) if sc["replies"] else "없어요")
        elif s.awaiting == "soft_check":
            s.act("continue")
        else:
            break
    out["confirm"] = s.id
    # 위기 고정 문구(합성 대사, 가드 키워드 사전으로 판정)
    s = rt.new_session("static", f"SYN-UI-{m}-CRISIS")
    s.start()
    s.reply("가슴이 답답해요")
    s.reply("죽고 싶어요")
    out["crisis"] = s.id
    # 확정 직후([다음 단계로])
    s = rt.new_session("static", f"SYN-UI-{m}-NEXT")
    drive(s, scs["S2_feeling_only"])
    out["next"] = s.id
    # 후보(2×2)
    s = rt.new_session("static", f"SYN-UI-{m}-CAND")
    drive(s, scs["S2_feeling_only"])
    s.selection().start()
    out["candidates"] = s.id
    # 조절(후보 고른 뒤 색 하나 바꿈)
    s = rt.new_session("static", f"SYN-UI-{m}-ADJ")
    drive(s, scs["S2_feeling_only"])
    f = s.selection()
    v = f.start()
    f.select(choose(v, "index:3"))
    f.adjust("color", "h07")
    out["adjust"] = s.id
    # 조절(선택 건너뜀, G34)
    s = rt.new_session("static", f"SYN-UI-{m}-SKIP")
    drive(s, scs["S3_all_said"])
    s.selection().start()
    out["adjust_skipped"] = s.id
    # 사전 측정
    s = rt.new_session("static", f"SYN-UI-{m}-PM")
    drive(s, scs["S4_none_fit"])
    f = s.selection()
    f.start()
    f.select("none")
    f.finish()
    out["premeasure"] = s.id
    # 끝
    s = rt.new_session("static", f"SYN-UI-{m}-DONE")
    drive(s, scs["S4_none_fit"])
    f = s.selection()
    f.start()
    f.select("none")
    f.finish()
    f.submit_premeasure({i["id"]: None for i in rt.selection_protocol.items()})
    out["done"] = s.id

    (log_dir / "ui_sessions.json").write_text(json.dumps({"sessions": out, "preview": rt.preview.info()},
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
    if a.web_dir:
        import ifs_chatbot.server as srv
        srv.WEB_DIR = Path(a.web_dir).resolve()
    try:
        uvicorn.run(create_app(runtime=rt, warmup=False), host="127.0.0.1", port=a.port, log_level="warning")
    finally:
        rt.preview.close()


if __name__ == "__main__":
    main()
