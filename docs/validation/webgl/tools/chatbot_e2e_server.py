"""chatbot_e2e.py가 띄우는 챗봇 서버(127.0.0.1만). chatbot/.venv의 python으로 실행한다.

v4 설정(llm offline, 가드 모델 없음)으로 Runtime을 만들고, 합성 시나리오의 면담을 정적 조건으로 서버 안에서 끝낸 뒤
(simulate.drive — LLM 없음) 세션 목록을 <log_dir>/e2e_sessions.json에 적고 서버를 연다. 그 뒤 단계는 브라우저가 진행한다.
LLM 백엔드의 generate 호출은 <log_dir>/e2e_llm_calls.txt에 한 줄씩 남긴다(0이어야 함).

  python chatbot_e2e_server.py --log-dir <폴더> --port 8790 [--webgl-dir <빌드>] [--player <exe>] [--queue-dir <폴더>]
         [--sweep] --scenarios S1_form_said ...
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
from ifs_chatbot.selection_sim import load  # noqa: E402
from ifs_chatbot.server import create_app  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402

SWEEP_SID = "SYN-E2E-SWEEP"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--webgl-dir", default="")
    ap.add_argument("--player", default="")
    ap.add_argument("--queue-dir", default="")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--scenarios", nargs="*", default=[])
    ap.add_argument("--web-dir", default="", help="재현용: 웹 화면 파일(index.html·app.js·stage.js·style.css)을 이 폴더에서 내보냄(예: 이전 커밋의 stage.js)")
    a = ap.parse_args()
    log_dir = Path(a.log_dir).resolve()
    over = {"llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(log_dir)}
    if a.webgl_dir:
        over["preview.webgl_dir"] = str(Path(a.webgl_dir).resolve())
    if a.player:
        over["preview.image_player"] = str(Path(a.player).resolve())
    if a.queue_dir:
        over["preview.queue_dir"] = str(Path(a.queue_dir).resolve())
    rt = Runtime(load_config("v4").with_overrides(**over))
    calls = log_dir / "e2e_llm_calls.txt"
    log_dir.mkdir(parents=True, exist_ok=True)
    calls.write_text("", encoding="utf-8")
    orig = rt.backend.generate

    def counted(req):
        with calls.open("a", encoding="utf-8") as f:
            f.write("generate\n")
        return orig(req)
    rt.backend.generate = counted

    scs = {s["id"]: s for s in load()}
    sessions = []
    for sid in a.scenarios:
        sc = scs[sid]
        s = rt.new_session(sc.get("condition", "static"), sc.get("sessionId") or sc["id"])
        drive(s, sc)
        sessions.append({"scenario": sid, "sessionId": s.id, "state": s.state, "sweep": False})
    if a.sweep:
        sc = dict(scs["S2_feeling_only"], id="SWEEP_all_items", sessionId=SWEEP_SID)
        s = rt.new_session("static", SWEEP_SID)
        drive(s, sc)
        sessions.append({"scenario": "SWEEP_all_items", "sessionId": s.id, "state": s.state, "sweep": True})
    (log_dir / "e2e_sessions.json").write_text(json.dumps({"sessions": sessions, "preview": rt.preview.info()},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
    if a.web_dir:
        import ifs_chatbot.server as srv
        srv.WEB_DIR = Path(a.web_dir).resolve()
    uvicorn.run(create_app(runtime=rt, warmup=False), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
