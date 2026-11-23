"""헤드리스 Chrome(DevTools 프로토콜)으로 WebGL 미리보기 페이지를 열고, 단계마다 브라우저 화면(캔버스 합성 결과)을 PNG로 찍는다(D4).

driver.html은 Unity 안의 렌더 텍스처(PreviewStage.RenderPng)를 받으므로 브라우저 합성·화면 AA를 보지 못한다.
이 스크립트는 사람이 볼 화면 그대로(Page.captureScreenshot)를 찍고, 첫 로딩 시간과 콘솔 오류를 모은다.

  python -I cdp_shot.py <chrome.exe> <페이지 URL> <출력 폴더> <steps.json> [--port 9333] [--size 800x600]
  steps.json = [{"name": "R07", "js": "<Promise를 돌려주는 식>", "settleFrames": 3}, …]
    js는 페이지 안에서 await 된다(예: fetch('/harness/spec/6').then(r=>r.text()).then(t=>ifsPreview.load(t)).then(r=>r.renderPath)).
    결과(JSON으로 바꿀 수 있는 값)는 shots.json에 남는다. 그 뒤 settleFrames 프레임을 기다렸다가 화면을 찍는다.
페이지 URL은 127.0.0.1(serve.py)이어야 한다. 외부로 나가는 요청이 없다. 별도 --user-data-dir(임시)로 띄우고 끝나면 그 프로세스만 닫는다.
외부 패키지: websockets.
"""
import argparse
import asyncio
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request

import websockets


async def run(a):
    os.makedirs(a.out, exist_ok=True)
    with open(a.steps, encoding="utf-8") as f:
        steps = json.load(f)
    w, h = (int(x) for x in a.size.split("x"))
    prof = tempfile.mkdtemp(prefix="ifs-cdp-")
    args = [a.chrome, "--headless=new", f"--remote-debugging-port={a.port}", f"--user-data-dir={prof}", f"--window-size={w},{h}",
            "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "about:blank"] + a.extra
    proc = subprocess.Popen(args)
    result = {"chromeArgs": args[1:], "url": a.url, "size": [w, h], "console": [], "shots": []}
    try:
        targets = None
        for _ in range(200):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{a.port}/json"))
                if any(t.get("type") == "page" for t in targets):
                    break
            except OSError:
                pass
            await asyncio.sleep(0.05)
        page = next(t for t in targets if t.get("type") == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=256 * 1024 * 1024) as ws:
            seq = [0]
            waiting = {}

            async def reader():
                async for msg in ws:
                    m = json.loads(msg)
                    if "id" in m and m["id"] in waiting:
                        waiting.pop(m["id"]).set_result(m)
                    elif m.get("method") == "Runtime.consoleAPICalled":
                        p = m["params"]
                        text = " ".join(str(x.get("value", x.get("description", ""))) for x in p.get("args", []))
                        result["console"].append({"type": p["type"], "text": text[:2000], "t": round(time.perf_counter() - t0, 3)})
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        result["console"].append({"type": "exception", "text": (d.get("exception") or {}).get("description", d.get("text"))[:2000],
                                                  "t": round(time.perf_counter() - t0, 3)})
                    elif m.get("method") == "Log.entryAdded":
                        e = m["params"]["entry"]
                        result["console"].append({"type": "log." + e["level"], "text": e["text"][:2000], "url": e.get("url"),
                                                  "t": round(time.perf_counter() - t0, 3)})

            async def call(method, params=None, timeout=300):
                seq[0] += 1
                fut = asyncio.get_running_loop().create_future()
                waiting[seq[0]] = fut
                await ws.send(json.dumps({"id": seq[0], "method": method, "params": params or {}}))
                r = await asyncio.wait_for(fut, timeout)
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error']}")
                return r["result"]

            async def evaluate(expr, timeout=300):
                r = await call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout)
                if "exceptionDetails" in r:
                    d = r["exceptionDetails"]
                    raise RuntimeError((d.get("exception") or {}).get("description") or d.get("text"))
                return r["result"].get("value")

            t0 = time.perf_counter()
            task = asyncio.create_task(reader())
            await call("Runtime.enable")
            await call("Log.enable")
            await call("Page.enable")
            await call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False})
            t_nav = time.perf_counter()
            await call("Page.navigate", {"url": a.url})
            ready = await evaluate("(async()=>{while(!window.ifsPreview) await new Promise(r=>setTimeout(r,20));"
                                   "await ifsPreview.ready; return ifsPreview.timings;})()")
            result["navigateToReadySeconds"] = round(time.perf_counter() - t_nav, 3)
            result["pageTimings"] = ready
            result["webgl"] = await evaluate("""(()=>{const c=document.getElementById('unity-canvas');
                const gl=c.getContext('webgl2'); if(!gl) return null; const d=gl.getExtension('WEBGL_debug_renderer_info');
                const a=gl.getContextAttributes();
                return {version: gl.getParameter(gl.VERSION), shading: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                        renderer: d? gl.getParameter(d.UNMASKED_RENDERER_WEBGL): gl.getParameter(gl.RENDERER),
                        maxSamples: gl.getParameter(gl.MAX_SAMPLES), contextAntialias: a && a.antialias,
                        canvas: [c.width, c.height]};})()""")
            for st in steps:
                e = {"name": st["name"]}
                try:
                    a0 = time.perf_counter()
                    e["value"] = await evaluate(st["js"])
                    e["jsSeconds"] = round(time.perf_counter() - a0, 3)
                    for _ in range(int(st.get("settleFrames", 3))):
                        await evaluate("new Promise(r=>requestAnimationFrame(()=>r(0)))")
                    shot = await call("Page.captureScreenshot", {"format": "png"})
                    path = os.path.join(a.out, st["name"] + ".png")
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(shot["data"]))
                    e["png"] = os.path.basename(path)
                except Exception as ex:  # 단계 하나가 실패해도 나머지를 찍는다
                    e["error"] = str(ex)
                result["shots"].append(e)
            task.cancel()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        with open(os.path.join(a.out, "shots.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: result.get(k) for k in ("navigateToReadySeconds", "pageTimings", "webgl")}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chrome")
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("steps")
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--size", default="800x600")
    ap.add_argument("--extra", action="append", default=[], help="Chrome에 더 넘길 인자 하나(여러 번 가능). 예: --extra=--use-angle=swiftshader")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
