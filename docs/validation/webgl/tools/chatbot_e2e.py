"""챗봇 웹 화면 + WebGL 미리보기 끝에서 끝까지(G12 연결 확인). 헤드리스 Chrome을 DevTools 프로토콜로 눌러 본다.

합성 시나리오(chatbot/scenarios/selection/S1–S9)만 쓴다. 면담은 서버 안에서 정적 조건(LLM 없음)으로 끝내고(simulate.drive),
그 뒤 단계(후보 → 선택 → 조절 → 사전 측정 → selection.json)는 브라우저 화면의 버튼을 눌러서 진행한다.
서버는 127.0.0.1에만 열고, 외부로 나가는 요청이 없다. 출력(PNG·로그·selection.json)은 --out(저장소 밖)에 둔다.

  python chatbot_e2e.py --out <저장소 밖 폴더> --label webgl [--sweep] [--extra=--disable-webgl] [--venv <chatbot/.venv의 python.exe>]
       [--chrome <chrome.exe>] [--webgl-dir <빌드 폴더>] [--player <IFSPreview.exe>] [--ref-player <IFSPreview.exe>] [--scenarios S1_form_said ...]
  서버(chatbot_e2e_server.py)는 chatbot/.venv의 python으로 따로 띄운다(면담 형태소 분석이 그 환경과 같아야 시나리오 기대값이 맞음).
  이 스크립트는 websockets·numpy·Pillow가 있는 python으로 돌린다(ifs_chatbot에서는 순수 함수와 플레이어 클라이언트만 가져다 씀).

확인하는 것(결과 <out>/e2e_<label>.json):
  - 세션 방식(webgl/image/none)과 내려간 이유가 selection.json preview에 남는가
  - iframe이 다시 로드되지 않는가(첫 창에 표시를 심고 단계마다 같은 창인지 봄, iframe load 횟수)
  - 후보 칸 그림이 그 후보의 것인가(같은 spec·덮어쓰기를 예비 플레이어로 그린 PNG와 평균 ΔE00 행렬, 대각선이 행마다 최소인가)
  - 조절 값마다 화면(브라우저 스크린샷)이 바뀌는가, 움직임 값에서 시간에 따라 화면이 바뀌는가
  - 시나리오 기대값(selection_sim.check), 선택 단계 LLM 호출 0, 콘솔 오류
외부 패키지: websockets, numpy, Pillow.
"""
import argparse
import asyncio
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import websockets
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "chatbot"))
sys.path.insert(0, str(HERE))
from types import SimpleNamespace  # noqa: E402

from compare import ciede2000, linear_to_lab, srgb_to_linear  # noqa: E402
from ifs_chatbot.preview import UnityQueueRenderer  # noqa: E402
from ifs_chatbot.selection_sim import check, choose, load  # noqa: E402

HELPERS = r"""
window.__e2e = (() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const until = async (fn, ms, what) => {
    const t0 = performance.now();
    for (;;) { let v; try { v = fn(); } catch (e) { v = false; } if (v) return v;
      if (performance.now() - t0 > ms) throw new Error("시간 초과: " + what); await sleep(25); }
  };
  const S = () => window.ifsStage._state, W = () => window.ifsStage._webgl;
  const frames = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(r))));
  const idle = () => until(() => !S().busy && S().view, 20000, "busy");
  function frameInfo() {
    const w = W();
    if (!w.frame) return { frame: false };
    const cw = w.frame.contentWindow;
    if (!w.frame.__e2eLoads) { w.frame.__e2eLoads = 0; w.frame.addEventListener("load", () => { w.frame.__e2eLoads++; }); }
    if (cw && !cw.__e2eMark) cw.__e2eMark = "m" + Math.random().toString(36).slice(2);
    return { frame: true, mark: cw ? cw.__e2eMark : null, loadsAfterMark: w.frame.__e2eLoads, inBody: w.host && w.host.parentNode === document.body,
             hostClass: w.host ? w.host.className : null, contextLost: !!(cw && cw.ifsPreview && cw.ifsPreview.contextLost) };
  }
  function previewRect() {
    const el = document.querySelector(".adjust .preview");
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height };
  }
  async function settleAdjust(t0) {
    await idle();
    const mode = S().view.preview.mode;
    if (mode === "webgl") await until(() => { const s = document.querySelector(".live-slot"); return s && s.dataset.applied === s.dataset.overrides; }, 30000, "live applied");
    else if (mode === "image") await until(() => { const i = document.querySelector(".adjust .preview img"); return i && i.complete && i.naturalWidth > 0; }, 30000, "image");
    const ms = t0 ? performance.now() - t0 : null;     // 누름 → 새 그림이 얹힘(webgl: Unity 덮어쓰기 응답, image: PNG 받음)
    await frames(); await sleep(150); await frames();
    return { mode, ms, stage: S().view.stage, overrides: S().view.current && S().view.current.overrides, rect: previewRect(), frame: frameInfo(),
             unavailable: S().view.unavailableItems || {} };
  }
  return {
    async next() {
      const t0 = performance.now();
      (await until(() => [...document.querySelectorAll("#buttons button")].find((b) => b.textContent === "다음 단계로"), 20000, "다음 단계로")).click();
      await until(() => S().view && S().view.stage, 20000, "stage");
      return { stage: S().view.stage, mode: S().view.preview.mode, t0 };
    },
    async candidates(t0) {
      await until(() => S().view.stage !== "selecting" || [...document.querySelectorAll(".cand .preview")].every((p) => {
        const i = p.querySelector("img"); return p.classList.contains("text") || (i && i.src && i.complete && i.naturalWidth > 0); }), 90000, "후보 그림");
      const ms = performance.now() - t0;
      await frames();
      const v = S().view;
      return { ms, mode: v.preview.mode, stage: v.stage, frame: frameInfo(), webglInfo: W().info,
               cands: [...document.querySelectorAll(".cand")].map((c) => { const i = c.querySelector("img");
                 return { id: c.dataset.id, imgTarget: i && i.dataset.target, imgMode: i && i.dataset.mode, overrides: i && i.dataset.overrides,
                          captureSeq: i && i.dataset.captureSeq, src: i ? i.src : null }; }),
               view: { candidates: v.candidates.map((c) => ({ id: c.id, index: c.index, overrides: c.overrides })) } };
    },
    async select(id) {
      const b = id === "none" ? document.querySelector("button.none-fit") : document.querySelector(`.cand[data-id="${id}"] button`);
      b.click(); await idle(); return settleAdjust();
    },
    settleAdjust,
    items() { return S().cfg.adjustItems.map((i) => ({ id: i.id, kind: i.kind, values: i.kind === "swatch" ? i.values.map((v) => v.id) : i.values,
                                                       extra: (S().view.adjustExtras || {})[i.id] })); },
    current() { return S().view.current.items; },
    async adjust(item, value) {
      const t0 = performance.now();
      const it = S().cfg.adjustItems.find((x) => x.id === item);
      const row = () => document.querySelector(`.adjust-row[data-item="${item}"]`);
      if (it.kind === "swatch") { const b = row().querySelector(`[aria-label="색 견본 ${value}"]`); if (b.disabled) return { disabled: true }; b.click(); }
      else if (it.kind === "category") {
        const extra = (S().view.adjustExtras || {})[item];
        const vals = extra !== undefined && !it.values.includes(extra) ? it.values.concat([extra]) : it.values;
        const b = row().querySelectorAll(".opts button")[vals.indexOf(value)];
        if (b.disabled) return { disabled: true }; b.click();
      } else {
        for (let k = 0; k < 20; k++) {
          const now = S().view.current.items[item];
          if (Math.abs(now - value) < 1e-9) break;
          const [minus, plus] = row().querySelectorAll(".stepper button");
          const b = value > now ? plus : minus;
          if (b.disabled) return { disabled: true };
          b.click(); await idle();
        }
      }
      await idle();
      return settleAdjust(t0);
    },
    async captureNow(tag) {         // 지금 Unity 상태를 320×240으로(어댑터 큐를 거침)
      const w = W();
      return w.enqueue("e2e 캡처", () => w.capture("e2e-" + tag));
    },
    async finish(pm) {
      document.querySelector(".stage .buttons button.primary").click();
      await idle();
      await until(() => document.querySelector("form.premeasure"), 20000, "사전 측정");
      for (const fs of document.querySelectorAll("fieldset.pm-item")) {
        const id = fs.dataset.item, v = pm[id];
        (v === null || v === undefined ? fs.querySelector(`#pm-${id}-skip`) : fs.querySelector(`#pm-${id}-${v}`)).click();
      }
      document.querySelector("form.premeasure button[type=submit]").click();
      await until(() => S().view.stage === "done", 20000, "done");
      await idle();
      return { stage: S().view.stage, frame: frameInfo(), hostLeft: !!document.querySelector(".webgl-host") };
    },
  };
})();
true
"""


def png_rgb(data: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"), dtype=np.float64) / 255.0


def mean_de(a: np.ndarray, b: np.ndarray) -> float:
    """화면 전체 화소 ΔE00 평균(같은 크기)."""
    la, lb = linear_to_lab(srgb_to_linear(a).reshape(-1, 3)), linear_to_lab(srgb_to_linear(b).reshape(-1, 3))
    return float(np.mean(ciede2000(la, lb)))


def diff_px(a: bytes, b: bytes, thr: int = 8) -> tuple[int, int]:
    """(채널 차가 thr/255를 넘는 화소 수, 최대 채널 차). 크기가 다르면 (-1, -1)."""
    x = np.asarray(Image.open(io.BytesIO(a)).convert("RGB"), dtype=np.int16)
    y = np.asarray(Image.open(io.BytesIO(b)).convert("RGB"), dtype=np.int16)
    if x.shape != y.shape:
        return -1, -1
    d = np.abs(x - y).max(axis=2)
    return int((d > thr).sum()), int(d.max())


class Cdp:
    def __init__(self, ws):
        self.ws, self.seq, self.waiting, self.console = ws, 0, {}, []
        self.t0 = time.perf_counter()

    async def reader(self):
        async for msg in self.ws:
            m = json.loads(msg)
            if "id" in m and m["id"] in self.waiting:
                self.waiting.pop(m["id"]).set_result(m)
            elif m.get("method") == "Runtime.consoleAPICalled":
                p = m["params"]
                text = " ".join(str(x.get("value", x.get("description", ""))) for x in p.get("args", []))
                self.console.append({"type": p["type"], "text": text[:600], "t": round(time.perf_counter() - self.t0, 2)})
            elif m.get("method") == "Runtime.exceptionThrown":
                d = m["params"]["exceptionDetails"]
                self.console.append({"type": "exception", "text": str((d.get("exception") or {}).get("description", d.get("text")))[:600],
                                     "t": round(time.perf_counter() - self.t0, 2)})
            elif m.get("method") == "Log.entryAdded":
                e = m["params"]["entry"]
                self.console.append({"type": "log." + e["level"], "text": e["text"][:600], "url": e.get("url"),
                                     "t": round(time.perf_counter() - self.t0, 2)})

    async def call(self, method, params=None, timeout=180):
        self.seq += 1
        fut = asyncio.get_running_loop().create_future()
        self.waiting[self.seq] = fut
        await self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params or {}}))
        r = await asyncio.wait_for(fut, timeout)
        if "error" in r:
            raise RuntimeError(f"{method}: {r['error']}")
        return r["result"]

    async def js(self, expr, timeout=180):
        r = await self.call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            raise RuntimeError(str((d.get("exception") or {}).get("description", d.get("text")))[:800])
        return r["result"].get("value")

    async def shot(self, rect=None) -> bytes:
        p = {"format": "png", "captureBeyondViewport": True}
        if rect:
            p["clip"] = {"x": rect["x"], "y": rect["y"], "width": rect["w"], "height": rect["h"], "scale": 1}
        return base64.b64decode((await self.call("Page.captureScreenshot", p))["data"])


def stop_player(queue: Path) -> None:
    """서버를 강제로 끝내면(Windows terminate) 서버가 띄운 예비 플레이어가 남는다 → 큐 폴더에 끝내기 요청을 넣고 기다린다."""
    if not queue.exists():
        return
    (queue / "quit.req.json").write_text("{}", encoding="utf-8")
    for _ in range(100):
        try:
            with open(queue / "player.log", "a", encoding="utf-8"):
                pass
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq IFSPreview.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True)
            if "IFSPreview.exe" not in r.stdout:
                return
        except OSError:
            pass
        time.sleep(0.1)


def http_json(url, timeout=30):
    return json.load(urllib.request.urlopen(url, timeout=timeout))


async def run(a):
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    (out / "png").mkdir(parents=True)
    log_dir = out / "logs"
    base = f"http://127.0.0.1:{a.port}"
    cmd = [a.venv, str(HERE / "chatbot_e2e_server.py"), "--log-dir", str(log_dir), "--port", str(a.port),
           "--queue-dir", str(out / "queue"), "--scenarios", *a.scenarios]
    if a.sweep:
        cmd.append("--sweep")
    if a.webgl_dir:
        cmd += ["--webgl-dir", a.webgl_dir]
    if a.player:
        cmd += ["--player", a.player]
    srv_log = open(out / "server.out", "w", encoding="utf-8")
    srv = subprocess.Popen(cmd, cwd=str(REPO / "chatbot"), stdout=srv_log, stderr=subprocess.STDOUT)
    ref = UnityQueueRenderer([a.ref_player], out / "ref-queue") if a.ref_player else None
    prof = tempfile.mkdtemp(prefix="ifs-e2e-")
    proc = None
    result = {"label": a.label, "chromeExtra": a.extra, "runs": [], "console": []}
    try:
        for _ in range(3000):
            if (log_dir / "e2e_sessions.json").exists():
                try:
                    http_json(base + "/api/health", 1)
                    break
                except OSError:
                    pass
            if srv.poll() is not None:
                raise RuntimeError("서버가 끝남: " + (out / "server.out").read_text(encoding="utf-8")[-2000:])
            time.sleep(0.1)
        sessions = json.loads((log_dir / "e2e_sessions.json").read_text(encoding="utf-8"))
        result["server"] = {"preview": sessions["preview"]}
        args = [a.chrome, "--headless=new", f"--remote-debugging-port={a.cdp_port}", f"--user-data-dir={prof}", "--window-size=1400,1100",
                "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "about:blank"] + a.extra
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        targets = None
        for _ in range(200):
            try:
                targets = http_json(f"http://127.0.0.1:{a.cdp_port}/json", 2)
                if any(t.get("type") == "page" for t in targets):
                    break
            except OSError:
                pass
            await asyncio.sleep(0.05)
        page = next(t for t in targets if t.get("type") == "page")
        scs = {s["id"]: s for s in load()}
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=512 * 1024 * 1024) as ws:
            c = Cdp(ws)
            rd = asyncio.create_task(c.reader())
            for m in ("Runtime.enable", "Log.enable", "Page.enable"):
                await c.call(m)
            for ses in sessions["sessions"]:
                sc = scs.get(ses["scenario"]) or {"id": ses["scenario"], "selection": "display:0", "adjust": []}
                result["runs"].append(await one(c, sc, ses, a, out, log_dir, base, ref))
            result["console"] = c.console
            rd.cancel()
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        srv.terminate()
        try:
            srv.wait(timeout=15)
        except subprocess.TimeoutExpired:
            srv.kill()
        srv_log.close()
        if ref is not None:
            ref.close()
        stop_player(out / "queue")
        shutil.rmtree(prof, ignore_errors=True)
    result["consoleErrors"] = [x for x in result["console"] if x["type"] in ("error", "exception", "log.error")]
    calls = log_dir / "e2e_llm_calls.txt"
    result["llmCalls"] = len(calls.read_text(encoding="utf-8").splitlines()) if calls.exists() else None
    (out / f"e2e_{a.label}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary(result), ensure_ascii=False, indent=1))


def summary(r):
    s = {"label": r["label"], "llmCalls": r["llmCalls"], "consoleErrors": len(r["consoleErrors"]), "runs": []}
    for x in r["runs"]:
        s["runs"].append({k: x.get(k) for k in ("scenario", "modeAtCandidates", "modeAtAdjust", "modeFinal", "candidatesMs",
                                                  "frameRestarts", "candidateMatch", "adjustChanged", "checkFails", "fallbacks", "error")})
    return s


async def one(c, sc, ses, a, out, log_dir, base, ref):
    sid, sweep = ses["sessionId"], ses["sweep"]
    run = {"scenario": sc["id"], "sessionId": sid, "steps": []}
    png = out / "png" / sc["id"]
    png.mkdir(parents=True, exist_ok=True)
    try:
        await c.call("Page.navigate", {"url": f"{base}/?sid={sid}"})
        await asyncio.sleep(0.3)
        for _ in range(200):
            if await c.js("!!(window.ifsStage && window.ifsStage._state && document.readyState === 'complete')"):
                break
            await asyncio.sleep(0.05)
        await c.js(HELPERS)
        n = await c.js("__e2e.next()")
        run["modeAtStart"] = n["mode"]
        spec_json = json.dumps(http_json(f"{base}/api/sessions/{sid}/scene")["spec"], ensure_ascii=False)
        marks = []
        if n["stage"] == "selecting":
            cd = await c.js(f"__e2e.candidates({n['t0']})", timeout=180)
            run["candidatesMs"] = round(cd["ms"], 1)
            run["modeAtCandidates"] = cd["mode"]
            run["webglInfo"] = cd["webglInfo"]
            if cd["frame"].get("frame"):
                marks.append(cd["frame"])
            (png / "candidates_page.png").write_bytes(await c.shot())
            imgs, refs = [], []
            for k, cand in enumerate(cd["cands"]):
                src = cand["src"]
                if src and src.startswith("data:image/png;base64,"):
                    data = base64.b64decode(src.split(",", 1)[1])
                elif src:
                    data = urllib.request.urlopen(src).read()
                else:
                    data = None
                if data:
                    (png / f"cand{k}_{cand['id']}.png").write_bytes(data)
                imgs.append(data)
                ov = next(v["overrides"] for v in cd["view"]["candidates"] if v["id"] == cand["id"])
                r = ref.render(spec_json, ov) if ref is not None else None
                if r:
                    (png / f"cand{k}_{cand['id']}_player.png").write_bytes(r)
                refs.append(r)
            run["candidates"] = [{k2: v for k2, v in x.items() if k2 != "src"} for x in cd["cands"]]
            if all(imgs) and all(refs) and cd["mode"] in ("webgl", "image"):
                m = [[round(mean_de(png_rgb(i), png_rgb(r)), 3) for r in refs] for i in imgs]
                run["candidateDeltaE"] = m
                run["candidateMatch"] = all(min(range(len(row)), key=lambda j: row[j]) == i for i, row in enumerate(m))
                run["candidateTargetsMatch"] = all(x["imgTarget"] == x["id"] for x in cd["cands"])
            choice = choose(cd["view"], sc.get("selection", "display:0"))
            st = await c.js(f"__e2e.select({json.dumps(choice)})", timeout=120)
            run["selected"] = choice
        else:
            st = await c.js("__e2e.settleAdjust()", timeout=120)
        run["modeAtAdjust"] = st["mode"]
        run["unavailableAtAdjust"] = st["unavailable"]
        if st["frame"].get("frame"):
            marks.append(st["frame"])
        (png / "adjust_page.png").write_bytes(await c.shot())
        prev = await c.shot(st["rect"])
        (png / "adjust_00_start.png").write_bytes(prev)
        run["adjustRect"] = st["rect"]
        steps = list(sc.get("adjust", []))
        if sweep:
            items = await c.js("__e2e.items()")
            cur = await c.js("__e2e.current()")
            for it in items:
                vals = it["values"] + ([it["extra"]] if it.get("extra") is not None and it["extra"] not in it["values"] else [])
                now = cur.get(it["id"])
                now = now.get("swatch") if isinstance(now, dict) else now
                for v in vals:
                    if v != now:
                        steps.append({"item": it["id"], "value": v})
                if it["id"] == "motion" and now is not None:
                    steps.append({"item": "motion", "value": now})
            # 반투명 그릇(기본 형상 container + 투명도 0.4)을 조절 화면에서 한 번 더 그림
            steps += [{"item": "form", "value": "container"}, {"item": "opacity", "value": 0.4}]
        changed = []
        for k, step in enumerate(steps, 1):
            r = await c.js(f"__e2e.adjust({json.dumps(step['item'])}, {json.dumps(step['value'])})", timeout=120)
            rec = {"i": k, **step}
            if r.get("disabled"):
                rec["disabled"] = True
                run["steps"].append(rec)
                continue
            if r["frame"].get("frame"):
                marks.append(r["frame"])
            img = await c.shot(r["rect"])
            (png / f"adjust_{k:02d}_{step['item']}_{step['value']}.png").write_bytes(img)
            rec["mode"] = r["mode"]
            rec["ms"] = round(r["ms"], 1) if r.get("ms") is not None else None
            rec["diffPxVsPrev"], rec["maxChannelDiffVsPrev"] = diff_px(prev, img)
            rec["changed"] = rec["maxChannelDiffVsPrev"] > 0
            if step["item"] == "motion" and r["mode"] == "webgl":
                await asyncio.sleep(0.7)
                img2 = await c.shot(r["rect"])
                (png / f"adjust_{k:02d}_{step['item']}_{step['value']}_t+0.7s.png").write_bytes(img2)
                rec["diffPxAfter0p7s"], rec["maxChannelDiffAfter0p7s"] = diff_px(img, img2)
                img = img2
            if sweep and step["item"] == "form" and r["mode"] == "webgl":
                cap = await c.js(f"__e2e.captureNow({json.dumps(str(step['value']))})")
                data = base64.b64decode(cap.split(",", 1)[1])
                (png / f"form_{step['value']}_webgl320.png").write_bytes(data)
                rr = ref.render(spec_json, r["overrides"]) if ref is not None else None
                if rr:
                    (png / f"form_{step['value']}_player320.png").write_bytes(rr)
                    rec["meanDeltaEVsPlayer"] = round(mean_de(png_rgb(data), png_rgb(rr)), 3)
            changed.append(rec["changed"])
            prev = img
            run["steps"].append(rec)
        run["adjustChanged"] = f"{sum(changed)}/{len(changed)}"
        fin = await c.js(f"__e2e.finish({json.dumps(sc.get('premeasure') or {})})", timeout=60)
        run["hostLeftAfterDone"] = fin["hostLeft"]
        data = json.loads((log_dir / "selection" / sid / "selection.json").read_text(encoding="utf-8"))
        run["preview"] = data["preview"]
        run["adjustUnavailable"] = data.get("adjustUnavailable")
        run["modeFinal"] = data["preview"]["mode"]
        run["fallbacks"] = [(x["from"], x["to"], x["source"], x["reason"][:160]) for x in data["preview"]["fallbacks"]]
        run["premeasureSaved"] = (log_dir / "selection" / sid / "premeasure.json").exists()
        run["runnerReady"] = data["runnerReady"]
        run["checkFails"] = [] if sweep else check(sc, SimpleNamespace(cands=data["candidates"], data=data))
        mk = {m["mark"] for m in marks if m.get("mark")}
        run["frameMarks"] = len(mk)
        run["frameRestarts"] = (len(mk) - 1 if mk else 0) + max([m.get("loadsAfterMark", 0) for m in marks] or [0])
        run["frameAlwaysInBody"] = all(m.get("inBody") for m in marks) if marks else None
        run["contextLost"] = any(m.get("contextLost") for m in marks)
    except Exception as e:  # noqa: BLE001
        run["error"] = f"{type(e).__name__}: {e}"[:800]
        try:
            (png / "error_page.png").write_bytes(await c.shot())
        except Exception:  # noqa: BLE001
            pass
    return run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="webgl")
    ap.add_argument("--webgl-dir", default="")
    ap.add_argument("--player", default="", help="서버의 예비(image) 플레이어. 비우면 v4.toml 값")
    ap.add_argument("--ref-player", default="", help="후보 그림 대조용으로 이 스크립트가 따로 띄우는 Windows 미리보기 플레이어")
    ap.add_argument("--venv", default=str(REPO / "chatbot" / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--cdp-port", type=int, default=9340)
    ap.add_argument("--sweep", action="store_true", help="합성 세션 하나를 더 만들어 조절 일곱 항목의 모든 값을 눌러 봄")
    ap.add_argument("--scenarios", nargs="*", default=[p.stem for p in sorted((REPO / "chatbot" / "scenarios" / "selection").glob("S*.json"))])
    ap.add_argument("--extra", action="append", default=[], help="Chrome 인자 더하기(예: --extra=--disable-webgl)")
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
