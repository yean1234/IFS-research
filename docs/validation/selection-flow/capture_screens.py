"""1–6단계 화면 캡처(헤드리스 Edge). 합성 시나리오만(chatbot/scenarios/selection/).
사용(chatbot/ 폴더에서, 스크립트와 같은 폴더에 다른 .py가 없어야 함):
  .venv\\Scripts\\python.exe ..\\docs\\validation\\selection-flow\\capture_screens.py <out_dir> none
  .venv\\Scripts\\python.exe ..\\docs\\validation\\selection-flow\\capture_screens.py <out_dir> image <IFSPreview.exe>
Edge 경로는 이 PC의 기본 설치 위치다. 서버는 127.0.0.1에만 연다."""
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "chatbot"))   # <repo>/chatbot
import uvicorn  # noqa: E402

from ifs_chatbot.selection_sim import choose, load, make_runtime  # noqa: E402
from ifs_chatbot.server import create_app  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402

out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
mode = sys.argv[2]
player = sys.argv[3] if len(sys.argv) > 3 else ""
log_dir = Path(tempfile.mkdtemp(prefix="ifs-shots-"))
rt = make_runtime(log_dir, mode, player)
app = create_app(runtime=rt, warmup=False)
port = 8771 if mode == "none" else 8772
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
threading.Thread(target=server.run, daemon=True).start()
time.sleep(2)

scs = {s["id"]: s for s in load()}
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def session(sc, sid):
    sc = dict(sc, sessionId=sid)
    s = rt.new_session("static", sid)
    drive(s, sc)
    return s


def shot(sid, name):
    url = f"http://127.0.0.1:{port}/?sid={sid}"
    path = out / f"{name}.png"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--screenshot={path}",
                    "--window-size=1400,1150", "--virtual-time-budget=10000", "--no-first-run",
                    f"--user-data-dir={log_dir / 'edge'}", url], check=False, timeout=120)
    print(name, path.exists())


try:
    prefix = "none" if mode == "none" else "image"
    # 0) 확정 직후(다음 단계로 버튼)
    s = session(scs["S2_feeling_only"], f"SHOT-{prefix}-0")
    shot(s.id, f"{prefix}_0_after_confirm")
    # 1) 후보 화면(4개)
    s = session(scs["S2_feeling_only"], f"SHOT-{prefix}-1")
    s.selection().start()
    shot(s.id, f"{prefix}_1_candidates_2x2")
    # 1b) 구별되는 후보가 하나뿐 → 선택 단계 없이 바로 조절 화면(G34. 이전의 '후보 1개' 화면은 없어짐)
    s = session(scs["S3_all_said"], f"SHOT-{prefix}-1b")
    s.selection().start()
    shot(s.id, f"{prefix}_1b_skipped_to_adjust")
    if mode == "none":
        # 2) 조절 화면
        s = session(scs["S1_form_said"], f"SHOT-{prefix}-2")
        f = s.selection(); v = f.start(); f.select(choose(v, "index:2")); f.adjust("color", "h07"); f.adjust("size", 0.4)
        shot(s.id, f"{prefix}_2_adjust")
        # 3) 사전 측정 화면
        s = session(scs["S4_none_fit"], f"SHOT-{prefix}-3")
        f = s.selection(); f.start(); f.select("none"); f.finish()
        shot(s.id, f"{prefix}_3_premeasure")
        # 4) 끝
        f.submit_premeasure({i["id"]: 4 for i in rt.selection_protocol.items()})
        shot(s.id, f"{prefix}_4_done")
    else:
        s = session(scs["S2_feeling_only"], f"SHOT-{prefix}-2")
        f = s.selection(); v = f.start(); f.select(choose(v, "index:3")); f.adjust("color", "h07")
        shot(s.id, f"{prefix}_2_adjust")
finally:
    rt.preview.close()
    server.should_exit = True
    time.sleep(1)

