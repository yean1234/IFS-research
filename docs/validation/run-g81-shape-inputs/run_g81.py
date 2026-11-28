"""G81 점검: 참여자가 어떤 형태를 말해도 [맞는 게 없어요] 뒤 그림·형태가 잘 생성되는지(합성 대사만, 실제 로컬 파이프라인).

experiment 설정 서버(로그 폴더만 저장소 밖 임시 위치로 바꾼 사본 설정)를 따로 띄운 뒤 이 스크립트를 돌린다.
  1) HTTP로 면담: 세션 만들기(SYN-G81-<문장ID>) → 시작 → 첫 답 = 합성 문장 → [넘어가기]로 확인 화면까지 → [고칠게요]로 확정 텍스트 = 합성 문장
     (면담 LLM·가드는 실제 모델. 면담 질문은 점검 대상이 아니다)
  2) 헤드리스 Chrome(DevTools 프로토콜, 1280px 폭)으로 참여자 화면을 열고 단추를 눌러 진행하며 단계마다 찍는다:
     [다음으로] → (a) 후보 → [맞는 게 없어요] → 대기 → (b) 그림 3장 고르기 → 맨 앞(가장 작은 seed) 그림 [이걸로 할게요]
     → 대기 → (c) 만든 물체가 든 후보 → 만든 물체 [이걸로 할게요] → (d) 조절 화면 → [다 했어요]
     생성이 막히거나 시작되지 않으면 그때 참여자가 보는 화면을 찍는다.
  3) 세션마다 spec(scenes/<sid>.json)·selection.json·세션 로그에서 형태 슬롯·_unmapped·_negated·G77 기록·생성 기록을 모아 results.json에.
     로컬 절대 경로는 적지 않는다(<logs>/·<gen3d-out>/로 바꿈).

  python run_g81.py --base http://127.0.0.1:8031 --logs <서버 log_dir> --out <이 폴더> [--only A1,C1] [--chrome <chrome.exe>]
외부 패키지: websockets, Pillow. 외부로 나가는 요청 없음(127.0.0.1만).
"""
import argparse
import asyncio
import base64
import io
import json
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import websockets
from PIL import Image

CASES = [
    ("A1", "A 사전 형태 낱말+색·질감", "회색 매듭이에요. 단단해요."),
    ("A2", "A 사전 형태 낱말+색·질감", "얇은 띠가 꼬여 있어요."),
    ("B1", "B 사전 기본 형상", "동그란 공 같은 덩어리예요. 쑥색이에요."),
    ("C1", "C 사전에 없는 형태 낱말", "돌덩이예요."),
    ("C2", "C 사전에 없는 형태 낱말", "조약돌이 하나 있어요."),
    ("C3", "C 사전에 없는 형태 낱말", "판때기예요. 겨자색이고 반지르르해요."),
    ("D1", "D 직유·비유", "돌덩이 같은 게 있어요."),
    ("D2", "D 직유·비유", "깃털처럼 가벼운 거예요."),
    ("E1", "E 형태를 말하지 않음", "쑥색이고 차가워요."),
    ("F1", "F 생성 금지 범주", "사람 모양이에요."),
    ("F2", "F 생성 금지 범주", "고양이 같아요."),
    ("F3", "F 생성 금지 범주", "안개 같은 게 깔려 있어요."),
    ("F4", "F 생성 금지 범주", "불꽃이에요."),
    ("G1", "G 부정·과거", "매듭은 아니에요."),
    ("G2", "G 부정·과거", "예전에는 공이었어요."),
    ("H1", "H 긴 자유 서술", "가슴 한가운데가 꽉 막힌 느낌이에요. 회색 돌 같은 게 있는데 모서리가 뾰족해요. "
                           "크기는 주먹만 하고 무거워요. 가끔 조금씩 흔들려요."),
]

HELPERS = r"""
window.__g81 = (() => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const until = async (fn, ms, what) => { const t0 = performance.now();
    for (;;) { let v; try { v = fn(); } catch (e) { v = false; } if (v) return v;
      if (performance.now() - t0 > ms) throw new Error("시간 초과: " + what); await sleep(50); } };
  const S = () => window.ifsStage._state;
  const frames = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(r))));
  const stage = () => (S().view && S().view.stage) || null;
  const idle = () => until(() => !S().busy && S().view, 30000, "busy");
  const candsReady = () => [...document.querySelectorAll(".cand .preview")].every((p) => {
      const i = p.querySelector("img"); return p.classList.contains("text") || (i && i.src && i.complete && i.naturalWidth > 0); });
  async function settle() {
    await idle();
    const st = stage();
    if (st === "selecting") await until(candsReady, 120000, "후보 그림");
    if (st === "picking") await until(() => [...document.querySelectorAll(".pick-img")].every((i) => i.complete && i.naturalWidth > 0), 30000, "그림");
    if (st === "adjusting" && S().view.preview.mode === "webgl")
      await until(() => { const s = document.querySelector(".live-slot"); return s && s.dataset.applied === s.dataset.overrides; }, 40000, "live");
    await frames(); await sleep(600); await frames();
    return info();
  }
  function info() {
    const v = S().view || {};
    return { stage: v.stage, previewMode: v.preview && v.preview.mode, previewReason: v.preview && v.preview.reason,
             afterNone: v.afterNone || null, skipped: !!v.skipped,
             candidates: (v.candidates || []).map((c) => ({ id: c.id, afterNone: !!c.afterNone, hasAsset: !!c.asset })),
             imagePick: v.imagePick ? { round: v.imagePick.round, images: v.imagePick.images.map((im) => ({ position: im.position, seed: im.seed })) } : null,
             msgs: [...document.querySelectorAll("#stage .msg")].map((m) => m.textContent).slice(0, 4),
             scrollH: document.documentElement.scrollHeight };
  }
  return {
    stage, info, settle,
    async next() { (await until(() => [...document.querySelectorAll("#buttons button")].find((b) => b.textContent === "다음으로"), 30000, "다음으로")).click();
                   await until(() => stage(), 60000, "stage"); return settle(); },
    clickNone() { const b = document.querySelector('button[data-fkey="none"]'); if (!b) return false; b.click(); return true; },
    clickFkey(k) { const b = document.querySelector(`button[data-fkey="${k}"]`); if (!b) return false; b.click(); return true; },
    async waitLeave(st, ms) { await until(() => stage() && stage() !== st && !S().busy, ms, "단계 " + st + " 끝"); return settle(); },
    async waitStage(sts, ms) { await until(() => sts.includes(stage()) && !S().busy, ms, "단계 " + sts.join("/")); return info(); },
    rect(sel) { const e = document.querySelector(sel); if (!e) return null; e.scrollIntoView({ block: "center" });
                const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height }; },
    scrollTop() { scrollTo(0, 0); return true; },
  };
})(); true
"""


def api(base, method, path, body=None, timeout=600):
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        return {"_httpError": e.code, "_body": e.read().decode("utf-8", "replace")[:2000]}


def wait_models_ready(base, limit_s=300):
    """앞 세션의 생성이 모델을 내렸다가 다시 올리는 동안은 서버가 새 세션을 받지 않는다(409, CP13). 끝날 때까지 기다린다."""
    t0 = time.time()
    while time.time() - t0 < limit_s:
        g = (api(base, "GET", "/api/health").get("gen3dOnNone") or {})
        if g.get("modelsReady") and not g.get("generatingFor"):
            return round(time.time() - t0, 1)
        time.sleep(2)
    return None


def interview(base, sid, text):
    waited = wait_models_ready(base)
    t0 = time.time()
    v = api(base, "POST", "/api/sessions", {"sessionId": sid})
    if "_httpError" in v:
        return {"error": v}
    api(base, "POST", f"/api/sessions/{sid}/start")
    v = api(base, "POST", f"/api/sessions/{sid}/reply", {"text": text})
    turns = 1
    while v.get("awaiting") not in ("confirm", "none") and turns < 20:
        act = "continue" if v.get("awaiting") == "soft_check" else "skip"
        v = api(base, "POST", f"/api/sessions/{sid}/action", {"action": act})
        turns += 1
    pre = {"awaiting": v.get("awaiting"), "state": v.get("state")}
    if v.get("awaiting") == "confirm":
        v = api(base, "POST", f"/api/sessions/{sid}/action", {"action": "edit", "text": text})
    return {"waitedForModelsS": waited, "turns": turns, "beforeConfirm": pre, "state": v.get("state"), "awaiting": v.get("awaiting"),
            "selectionAvailable": (v.get("selection") or {}).get("available"), "seconds": round(time.time() - t0, 1)}


def scrub(obj, logs, gen_out):
    s = json.dumps(obj, ensure_ascii=False)
    for root, tag in ((logs, "<logs>"), (gen_out, "<gen3d-out>"), (Path(__file__).resolve().parents[3], "<repo>")):
        for form in {str(root), str(root).replace("\\", "/"), str(root).replace("\\", "\\\\")}:
            s = s.replace(form, tag)
    s = re.sub(r"C:(\\\\|/)Users(\\\\|/)[^\"]*?(?=(\\\\|/)(AppData|Desktop))", "<home>", s)
    return json.loads(s)


def collect(sid, logs, gen_out):
    spec = json.loads((logs / "scenes" / f"{sid}.json").read_text(encoding="utf-8")) if (logs / "scenes" / f"{sid}.json").exists() else None
    selp = logs / "selection" / sid / "selection.json"
    sel = json.loads(selp.read_text(encoding="utf-8")) if selp.exists() else None
    slog = json.loads((logs / f"{sid}.json").read_text(encoding="utf-8")) if (logs / f"{sid}.json").exists() else {}
    out = {"spec": None, "llmFill": None, "selection": None}
    if spec:
        prov = spec.get("_provenance", {})
        out["spec"] = {"form": spec.get("form"), "material": spec.get("material"),
                       "formProvenance": {k: v for k, v in prov.items() if k.startswith("form")},
                       "_unmapped": spec.get("_unmapped"), "_negated": spec.get("_negated"), "_unmatched": spec.get("_unmatched"),
                       "_alternatives": spec.get("_alternatives"), "_context": spec.get("_context"), "_uncertain": spec.get("_uncertain"),
                       "_needsConfirmation": spec.get("_needsConfirmation"), "_clauses": spec.get("_clauses"),
                       "metaMapping": (spec.get("meta") or {}).get("mapping")}
    ev = [e for e in slog.get("events", []) if e.get("type") == "scene:llm_fill"]
    out["llmFillEvent"] = ev[-1]["payload"] if ev else None
    out["guardLabels"] = [t.get("guard") for t in slog.get("turns", []) if t.get("speaker") == "participant"]
    out["alerts"] = slog.get("alerts")
    if sel:
        gen = sel.get("generation") or {}
        out["llmFill"] = sel.get("llmFill")
        out["selection"] = {"schema": sel.get("schema") or sel.get("$schema") or sel.get("version"), "runnerReady": sel.get("runnerReady"),
                            "runnerBlockers": sel.get("runnerBlockers"), "sources": sel.get("sources"),
                            "sourceDetails": sel.get("sourceDetails"), "form": sel.get("form"), "selection": sel.get("selection"),
                            "llmFillExposed": sel.get("llmFillExposed"), "afterNoneGeneration": sel.get("afterNoneGeneration"),
                            "generation": gen, "colorRing": sel.get("colorRing"), "finalOverrides": sel.get("finalOverrides"),
                            "preview": sel.get("preview")}
    return scrub(out, logs, gen_out)


async def run(a):
    out = Path(a.out)
    shots = out / "shots"
    raw = Path(a.raw)
    shots.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    logs = Path(a.logs)
    gen_out = Path(a.gen_out)
    only = set(a.only.split(",")) if a.only else None
    prof = tempfile.mkdtemp(prefix="ifs-g81-cdp-")
    W, H = 1280, 1100
    proc = subprocess.Popen([a.chrome, "--headless=new", f"--remote-debugging-port={a.cdp_port}", f"--user-data-dir={prof}",
                             f"--window-size={W},{H}", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                             "--disable-background-networking", "--disable-component-update", "--disable-sync", "about:blank"])
    resp_path = out / "results.json"
    results = json.loads(resp_path.read_text(encoding="utf-8")) if (resp_path.exists() and a.resume) else {"cases": {}}
    try:
        targets = None
        for _ in range(400):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{a.cdp_port}/json"))
                if any(t.get("type") == "page" for t in targets):
                    break
            except OSError:
                pass
            await asyncio.sleep(0.05)
        page = next(t for t in targets if t.get("type") == "page")
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=512 * 1024 * 1024) as ws:
            seq, waiting, console = [0], {}, []

            async def reader():
                async for msg in ws:
                    m = json.loads(msg)
                    if "id" in m and m["id"] in waiting:
                        waiting.pop(m["id"]).set_result(m)
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        console.append({"type": "exception", "text": str((d.get("exception") or {}).get("description", d.get("text")))[:500]})
                    elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] in ("error", "warning"):
                        p = m["params"]
                        console.append({"type": p["type"], "text": " ".join(str(x.get("value", x.get("description", ""))) for x in p.get("args", []))[:500]})

            async def call(method, params=None, timeout=900):
                seq[0] += 1
                fut = asyncio.get_running_loop().create_future()
                waiting[seq[0]] = fut
                await ws.send(json.dumps({"id": seq[0], "method": method, "params": params or {}}))
                r = await asyncio.wait_for(fut, timeout)
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error']}")
                return r["result"]

            async def ev(expr, timeout=900):
                r = await call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout)
                if "exceptionDetails" in r:
                    d = r["exceptionDetails"]
                    raise RuntimeError((d.get("exception") or {}).get("description") or d.get("text"))
                return r["result"].get("value")

            async def shot(name):
                await ev("__g81.scrollTop()")
                h = await ev("document.documentElement.scrollHeight")
                hh = max(H, min(int(h), 3000))
                await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": hh, "deviceScaleFactor": 1, "mobile": False})
                await asyncio.sleep(1.2)          # WebGL 겹침 자리 다시 맞춤
                d = await call("Page.captureScreenshot", {"format": "png"})
                (shots / f"{name}.png").write_bytes(base64.b64decode(d["data"]))
                await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})
                return f"shots/{name}.png"

            async def clip(sel, path):
                r = await ev(f"__g81.rect({json.dumps(sel)})")
                if not r:
                    return None
                await asyncio.sleep(0.5)
                d = await call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                                          "clip": {"x": r["x"], "y": r["y"], "width": r["w"], "height": r["h"], "scale": 1}})
                Path(path).write_bytes(base64.b64decode(d["data"]))
                return str(path)

            task = asyncio.create_task(reader())
            await call("Runtime.enable")
            await call("Page.enable")
            await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})

            for cid, kind, text in CASES:
                if only and cid not in only:
                    continue
                sid = f"SYN-G81-{cid}-{a.tag}"
                r = {"id": cid, "type": kind, "text": text, "sessionId": "SYN-G81-" + cid, "steps": [], "shots": {}, "timings": {}}
                console.clear()
                print(f"== {cid} {text}", flush=True)
                try:
                    r["interview"] = interview(a.base, sid, text)
                    if not r["interview"].get("selectionAvailable"):
                        r["result"] = "interview_not_done"
                        raise RuntimeError(f"면담이 끝나지 않음: {r['interview']}")
                    await call("Page.navigate", {"url": f"{a.base}/?sid={sid}&view=participant"})
                    await ev("(async()=>{while(!window.ifsStage) await new Promise(r=>setTimeout(r,50)); return true;})()", 60)
                    await asyncio.sleep(1.0)
                    await ev(HELPERS)
                    t_next = time.time()
                    st = await ev("__g81.next()")
                    r["timings"]["nextToCandidatesS"] = round(time.time() - t_next, 1)
                    r["steps"].append({"at": "after_next", **st})
                    if st["stage"] != "selecting":
                        r["shots"]["a"] = await shot(f"{cid}_a_no_candidates")
                        r["result"] = f"no_selecting_stage:{st['stage']}"
                    else:
                        r["shots"]["a"] = await shot(f"{cid}_a_candidates")
                        t_none = time.time()
                        await ev("__g81.clickNone()")
                        # 생성 대기 화면(있으면) 한 장
                        await asyncio.sleep(2.5)
                        st = await ev("__g81.info()")
                        if st["stage"] == "generating":
                            r["shots"]["wait_image"] = await shot(f"{cid}_wait_image")
                            st = await ev("__g81.waitLeave('generating', 600000)", 700)
                        else:
                            st = await ev("__g81.settle()")
                        r["timings"]["noneToNextScreenS"] = round(time.time() - t_none, 1)
                        r["steps"].append({"at": "after_none", **st})
                        if st["stage"] == "picking":
                            r["shots"]["b"] = await shot(f"{cid}_b_images")
                            imgs = st["imagePick"]["images"]
                            rnd = st["imagePick"]["round"] if st["imagePick"]["round"] is not None else 0
                            for im in imgs:
                                data = urllib.request.urlopen(f"{a.base}/api/sessions/{sid}/selection/image-pick/{rnd}/{im['position']}.png").read()
                                (raw / f"{cid}_img_r{rnd}_p{im['position']}.png").write_bytes(data)
                            first = imgs[0]["position"]
                            r["pickedPosition"] = first
                            t_pick = time.time()
                            await ev(f"__g81.clickFkey('img:{first}')")
                            await asyncio.sleep(2.5)
                            st = await ev("__g81.info()")
                            if st["stage"] == "generating":
                                r["shots"]["wait_mesh"] = await shot(f"{cid}_wait_mesh")
                                st = await ev("__g81.waitLeave('generating', 600000)", 700)
                            else:
                                st = await ev("__g81.settle()")
                            r["timings"]["pickToNextScreenS"] = round(time.time() - t_pick, 1)
                            r["steps"].append({"at": "after_pick", **st})
                            gen = [c for c in st["candidates"] if c["afterNone"]]
                            if st["stage"] == "selecting" and gen:
                                r["shots"]["c"] = await shot(f"{cid}_c_mesh")
                                await clip(f'.cand[data-id="{gen[0]["id"]}"] .preview', raw / f"{cid}_mesh_thumb.png")
                                await ev(f"__g81.clickFkey('cand:{gen[0]['id']}')")
                                st = await ev("__g81.waitStage(['adjusting'], 60000)", 90)
                                st = await ev("__g81.settle()")
                                r["steps"].append({"at": "after_choose_generated", **st})
                                r["shots"]["d"] = await shot(f"{cid}_d_adjust")
                                r["result"] = "generated_and_chosen"
                            else:
                                r["shots"]["c"] = await shot(f"{cid}_c_no_mesh_{st['stage']}")
                                r["result"] = f"mesh_not_shown:{st['stage']}"
                        elif st["stage"] == "adjusting":
                            r["shots"]["d"] = await shot(f"{cid}_d_adjust_blocked")
                            r["result"] = "blocked_or_not_started"
                        else:
                            r["shots"]["b"] = await shot(f"{cid}_b_other_{st['stage']}")
                            r["result"] = f"unexpected_stage:{st['stage']}"
                    # 조절 끝내기(selection.json 마무리)
                    stg = await ev("__g81.stage()")
                    if stg == "adjusting":
                        await ev("(()=>{const b=document.querySelector('.stage .buttons button.primary'); if(b) b.click(); return !!b;})()")
                        try:
                            await ev("__g81.waitStage(['premeasure','done'], 30000)", 60)
                        except Exception as ex:  # noqa: BLE001
                            r["finishError"] = str(ex)
                except Exception as ex:  # noqa: BLE001
                    r["error"] = str(ex)[:800]
                    try:
                        r["shots"]["error"] = await shot(f"{cid}_x_error")
                    except Exception:  # noqa: BLE001
                        pass
                r["console"] = list(console)
                r["collected"] = collect(sid, logs, gen_out)
                results["cases"][cid] = r
                resp_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"   -> {r.get('result')} {r.get('error', '')[:200]} {r['timings']}", flush=True)
            task.cancel()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8031")
    ap.add_argument("--logs", required=True, help="서버 설정의 log_dir(저장소 밖 임시 위치)")
    ap.add_argument("--gen-out", required=True, help="생성기 산출물 폴더(저장소 밖 gen3d-out) — results.json에서 경로를 가리는 데만 씀")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    ap.add_argument("--raw", required=True, help="그림·메시 축소판 원본을 둘 폴더(저장소 밖)")
    ap.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    ap.add_argument("--cdp-port", type=int, default=9341)
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="1", help="같은 문장을 다시 돌릴 때 세션 ID 끝에 붙일 값")
    ap.add_argument("--resume", action="store_true", help="results.json에 이어 쓰기")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
