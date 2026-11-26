"""보기 전 보고 화면을 실제 브라우저(Playwright chromium)로 한 바퀴: 재선택·새로고침·값 고른 뒤 ③ 전환·손잡이 없는 막대.
node와 전역 playwright가 없으면 건너뛴다. 서버는 127.0.0.1의 빈 포트에서 offline 백엔드로 띄운다(외부 요청 없음)."""
import json
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

import pytest

from ifs_chatbot import prereport
from ifs_chatbot.server import create_app

SCRIPT = r"""
const { chromium } = require('playwright');
const base = process.argv[2], sid = process.argv[3];
(async () => {
  const out = { errors: [], external: [] };
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 900, height: 1200 } });
  p.on('pageerror', e => out.errors.push(String(e)));
  p.on('console', m => { if (m.type() === 'error') out.errors.push(m.text()); });
  p.on('request', r => { if (!r.url().startsWith(base)) out.external.push(r.url()); });
  await p.goto(`${base}/prereport?session=${sid}`);
  await p.waitForSelector('#pr-step:not([hidden])');
  // 색: ① 확인 전에는 값 고르기가 없다
  out.pickHiddenBeforeCommit = await p.isHidden('#pr-pick');
  await p.click('#pr-options button[data-id="from_start"]');
  await p.click('#pr-next');
  const box = await p.locator('#pr-color-field').boundingBox();
  await p.mouse.click(box.x + box.width * 0.25, box.y + box.height * 0.5);   // 첫 선택
  await p.mouse.click(box.x + box.width * 0.75, box.y + box.height * 0.5);   // 다시 고름
  // 새로고침해도 이어진다
  await p.reload();
  await p.waitForSelector('#pr-step:not([hidden])');
  out.afterReload = JSON.parse(await p.evaluate((k) => sessionStorage.getItem(k), `ifs-prereport:${sid}`));
  out.pickVisibleAfterReload = await p.isVisible('#pr-color');
  await p.click('#pr-next');
  // 크기: ① → 손잡이 없이 시작 → 막대를 눌러 고름 → 답 바꾸기 → ③
  await p.click('#pr-options button[data-id="from_start"]');
  await p.click('#pr-next');
  out.thumbHiddenAtStart = await p.isHidden('#pr-size-thumb');
  out.nextDisabledBeforePick = await p.isDisabled('#pr-next');
  const t = await p.locator('#pr-size-track').boundingBox();
  // 취소된 접촉(pointercancel)은 선택이 아니다: 손잡이도 확정값도 생기지 않는다
  await p.evaluate(({ x, y }) => {
    const tr = document.querySelector('#pr-size-track');
    tr.dispatchEvent(new PointerEvent('pointerdown', { clientX: x, clientY: y, pointerId: 7, bubbles: true }));
    tr.dispatchEvent(new PointerEvent('pointermove', { clientX: x + 20, clientY: y, pointerId: 7, bubbles: true }));
    tr.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 7, bubbles: true }));
  }, { x: t.x + t.width * 0.8, y: t.y + t.height / 2 });
  out.thumbHiddenAfterCancel = await p.isHidden('#pr-size-thumb');
  out.afterCancel = JSON.parse(await p.evaluate((k) => sessionStorage.getItem(k), `ifs-prereport:${sid}`)).cur;
  await p.mouse.click(t.x + t.width * 0.25, t.y + t.height / 2);
  out.thumbVisibleAfterPick = await p.isVisible('#pr-size-thumb');
  await p.click('#pr-back');
  await p.click('#pr-options button[data-id="not_set"]');
  await p.click('#pr-next');
  await p.click('#pr-options button[data-id="when_asked"]'); await p.click('#pr-next');
  await p.click('#pr-options button[data-id="not_set"]'); await p.click('#pr-next');
  await p.waitForSelector('#pr-message:not([hidden])');
  out.done = await p.textContent('#pr-message');
  out.storageCleared = (await p.evaluate((k) => sessionStorage.getItem(k), `ifs-prereport:${sid}`)) === null;
  await b.close();
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


def _playwright_ok() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
        ok = subprocess.run([node, "-e", "require('playwright')"], capture_output=True, timeout=30,
                            env={"NODE_PATH": root, "PATH": __import__("os").environ.get("PATH", "")}).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None
    return root if ok else None


NODE_PATH = _playwright_ok()
pytestmark = pytest.mark.skipif(NODE_PATH is None, reason="node + 전역 playwright 없음")


@pytest.fixture(scope="module")
def server(rt):
    import uvicorn
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(create_app(runtime=rt, warmup=False), host="127.0.0.1", port=port,
                                        log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(timeout=10)


def _call(base, method, path, body=None):
    req = urllib.request.Request(base + path, method=method, headers={"Content-Type": "application/json"},
                                 data=None if body is None else json.dumps(body).encode())
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def test_browser_reselect_reload_and_switch_to_not_set(server, rt, tmp_path):
    sid = "PR-BROWSER-1"
    v = _call(server, "POST", "/api/sessions", {"condition": "chatbot", "sessionId": sid})
    v = _call(server, "POST", f"/api/sessions/{sid}/start")
    for text in ["가슴이 좀 답답해요", "가슴 안쪽이요", "없어요", "회색 덩어리 같아요", "없어요", "작아요", "가라앉아요"]:
        if v["awaiting"] != "reply":
            break
        v = _call(server, "POST", f"/api/sessions/{sid}/reply", {"text": text})
    _call(server, "POST", f"/api/sessions/{sid}/action", {"action": "confirm"})
    script = tmp_path / "run.js"
    script.write_text(SCRIPT, encoding="utf-8")
    import os
    r = subprocess.run(["node", str(script), server, sid], capture_output=True, text=True, timeout=180,
                       env={**os.environ, "NODE_PATH": NODE_PATH})
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["errors"] == [] and out["external"] == []
    assert out["pickHiddenBeforeCommit"] and out["pickVisibleAfterReload"]
    assert out["afterReload"]["phase"] == "pick" and out["afterReload"]["cur"]["nSelections"] == 2
    assert out["thumbHiddenAtStart"] and out["nextDisabledBeforePick"] and out["thumbVisibleAfterPick"]
    assert out["thumbHiddenAfterCancel"] and out["afterCancel"]["nSelections"] == 0 and out["afterCancel"]["value"] is None
    assert out["done"] == prereport.task_text()["fixedPhrases"]["done"]["text"] and out["storageCleared"]

    rec = json.loads(prereport.record_path(rt.cfg.log_dir, sid).read_text(encoding="utf-8"))
    assert prereport.validate(rec) == []
    c, s = rec["attributes"]["color"], rec["attributes"]["size"]
    assert c["nSelections"] == 2 and c["firstValue"]["h"] == pytest.approx(0.25, abs=0.01)
    assert c["value"]["h"] == pytest.approx(0.75, abs=0.01) and c["commitmentChangedAfterPick"] is False
    assert c["commitmentAtPick"] == "from_start"
    assert s == {"commitment": "not_set", "value": None, "firstValue": None, "widthM": None, "firstWidthM": None,
                 "method": "size_slider", "nSelections": 1, "commitmentChangedAfterPick": True,
                 "commitmentAtPick": "from_start"}
    assert rec["attributes"]["form"] == {"commitment": "when_asked"}
