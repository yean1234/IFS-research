"""G82 실제 흐름 점검: [맞는 게 없어요] 뒤 LLM 형태 이름(근거 인용 줄·[그 말이 아니에요])을 참여자 화면에서 끝까지(합성 대사만).

G81(run-g81-shape-inputs/run_g81.py)과 같은 방식이다. experiment-g82 설정 사본(로그 폴더만 저장소 밖 임시 위치)으로 서버를 따로 띄운 뒤 돌린다.
  1) HTTP로 면담: 세션 만들기(<sid-prefix>-<ID>-<tag>) → 시작 → 첫 답 = 합성 문장 → [넘어가기]로 확인 화면까지 → [고칠게요]로 확정 텍스트 = 합성 문장
     (면담 LLM·가드는 실제 모델. 면담 질문은 점검 대상이 아니다)
  2) 헤드리스 Chrome(DevTools 프로토콜, 1280px 폭)으로 참여자 화면을 열고 단추를 눌러 진행하며 단계마다 찍는다:
     [다음으로] → (a) 후보 → [맞는 게 없어요] → (LLM 대기·그림 대기) → (b) 그림 고르기(근거 인용 줄이 있으면 그 화면)
     → reject 표시 문장: [그 말이 아니에요] → (b2) 그 뒤 화면 → [다 했어요]
     → 그 밖: 맨 앞(가장 작은 seed) 그림 [이걸로 할게요] → 대기 → (c) 만든 물체가 든 후보 → 그 물체 [이걸로 할게요] → (d) 조절 → [다 했어요]
     막히면 그때 참여자가 보는 화면을 찍는다. 찍을 때마다 화면 글에 세션 ID·로컬 경로가 없는지 확인해 privacy에 적는다.
  3) 세션마다 spec·selection.json·세션 로그에서 매퍼 형태 슬롯·generation.shapeLlm·afterNone·관문·시간을 모아 results.json에.
     로컬 절대 경로는 적지 않는다(<logs>/·<gen3d-out>/·<repo>/로 바꿈).

  python run_g82_e2e.py --base http://127.0.0.1:8011 --logs <서버 log_dir> [--out <폴더>] [--raw <폴더>] [--cases cases.json]
                        [--sid-prefix SYN-G82] [--tag 1] [--only E1,E9] [--chrome <chrome.exe>]
  --cases: [{"id": "E1", "kind": "...", "text": "...", "reject": false}, ...] (없으면 아래 CASES)
외부 패키지: websockets, Pillow. 외부로 나가는 요청 없음(127.0.0.1만).
"""
import argparse
import asyncio
import base64
import json
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import websockets

REPO = Path(__file__).resolve().parents[3]

CASES = [
    {"id": "E1", "kind": "G81 실패 사전 밖 형태", "text": "조약돌이 하나 있어요.", "reject": False},
    {"id": "E2", "kind": "G81 실패 사전 밖 형태", "text": "판때기예요. 겨자색이고 반지르르해요.", "reject": False},
    {"id": "E3", "kind": "G81 실패 사전 밖 형태", "text": "돌덩이 같은 게 있어요.", "reject": False},
    {"id": "E4", "kind": "G81 실패 사전 밖 형태", "text": "돌덩이예요.", "reject": False},
    {"id": "E5", "kind": "새 사전 밖 형태", "text": "꼭 주전자 같아요. 회색이에요.", "reject": False},
    {"id": "E6", "kind": "새 사전 밖 형태", "text": "머릿속에 톱니바퀴가 있어요.", "reject": False},
    {"id": "E7", "kind": "형태 없음(막혀야 함)", "text": "쑥색이고 차가워요.", "reject": False},
    {"id": "E8", "kind": "속성 비유(막혀야 함)", "text": "돌덩이처럼 단단해요.", "reject": False},
    {"id": "E9", "kind": "[그 말이 아니에요]", "text": "조약돌이 하나 있어요.", "reject": True},
]

HELPERS = r"""
window.__g82 = (() => {
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
    const basisEl = document.querySelector('[data-fkey="shape-basis"]');
    const wrongBtn = document.querySelector('button[data-fkey="img:basis-wrong"]');
    return { stage: v.stage, previewMode: v.preview && v.preview.mode, previewReason: v.preview && v.preview.reason,
             afterNone: v.afterNone || null, skipped: !!v.skipped,
             llmShapeBasis: v.llmShapeBasis || null,
             basisShown: basisEl ? basisEl.textContent : null, wrongButton: wrongBtn ? wrongBtn.textContent : null,
             candidates: (v.candidates || []).map((c) => ({ id: c.id, afterNone: !!c.afterNone, hasAsset: !!c.asset })),
             imagePick: v.imagePick ? { round: v.imagePick.round, images: v.imagePick.images.map((im) => ({ position: im.position })) } : null,
             msgs: [...document.querySelectorAll("#stage .msg")].map((m) => m.textContent).slice(0, 5),
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
    pageText() { return document.body.innerText; },
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


def scrub(obj, roots):
    s = json.dumps(obj, ensure_ascii=False)
    for root, tag in roots:
        for form in sorted({str(root), str(root).replace("\\", "/"), str(root).replace("\\", "\\\\")}, key=len, reverse=True):
            s = s.replace(form, tag)
    s = re.sub(r"[A-Za-z]:(\\\\|/)Users(\\\\|/)[^\"]*?(?=(\\\\|/)(AppData|Desktop))", "<home>", s)
    return json.loads(s)


def privacy_check(text, sid, roots):
    """화면 글에 세션 ID·로컬 경로가 보이는지(보이면 그 조각을 적음)."""
    hits = []
    for needle in [sid, "SYN-"] + [str(r) for r, _ in roots] + [str(r).replace("\\", "/") for r, _ in roots]:
        if needle and needle in text:
            hits.append(needle if needle.startswith("SYN") else "<local path>")
    if re.search(r"[A-Za-z]:\\|[A-Za-z]:/|/Users/|\\Users\\", text):
        hits.append("<drive path pattern>")
    return sorted(set(hits))


def _form_slots(spec):
    if not spec:
        return None
    prov = spec.get("_provenance", {})
    return {"form": spec.get("form"), "material": spec.get("material"),
            "formProvenance": {k: v for k, v in prov.items() if k.startswith("form")},
            "_unmapped": spec.get("_unmapped"), "_negated": spec.get("_negated"), "_context": spec.get("_context"),
            "_uncertain": spec.get("_uncertain"), "_needsConfirmation": spec.get("_needsConfirmation"),
            "metaMapping": (spec.get("meta") or {}).get("mapping")}


def compact(sel):
    """results.json 맨 위에 올릴 간추림: shapeLlm·그림 프롬프트·그림 관문·메시 관문·생성 시간·runnerReady."""
    if not sel:
        return None
    gen = sel.get("generation") or {}
    sl = gen.get("shapeLlm") or {}
    call = sl.get("call") or {}
    an = gen.get("afterNone") or {}
    earlier = gen.get("afterNoneEarlier") or []
    ip = an.get("imagePick") or {}
    asset = an.get("asset") or {}
    return {
        "shapeLlm": None if not sl else {
            "route": sl.get("route"), "routeReason": sl.get("routeReason"), "called": sl.get("called"),
            "candidate": sl.get("candidate"), "status": sl.get("status"), "skipReason": sl.get("skipReason"),
            "rawItem": call.get("rawItem"),
            "adopted": None if not sl.get("adopted") else {k: sl["adopted"].get(k) for k in ("quote", "charSpan", "en")},
            "rejectReasons": sl.get("rejectReasons"), "exposed": sl.get("exposed"), "imageChosen": sl.get("imageChosen"),
            "candidateChosen": sl.get("candidateChosen"), "rejected": sl.get("rejected"),
            "participantLeftBeforeResult": sl.get("participantLeftBeforeResult"),
            "llmSeconds": call.get("llmSeconds"), "seconds": call.get("seconds"), "cached": call.get("cached"),
            "promptVersion": sl.get("promptVersion"), "seed": sl.get("seed"),
            "model": sl.get("model"), "ruleRoute": call.get("ruleRoute")},
        "afterNone": None if not an else {
            "status": an.get("status"), "blockReason": an.get("blockReason"), "blockDetail": an.get("blockDetail"),
            "shapeLlmUsed": an.get("shapeLlmUsed"), "shapeLlmItems": an.get("shapeLlmItems"),
            "basisRejected": an.get("basisRejected"), "chosen": an.get("chosen"), "seconds": an.get("seconds"),
            "prompt": (an.get("prompt") or {}).get("text"), "shapeSource": (an.get("prompt") or {}).get("shapeSource"),
            "shapeNoun": (an.get("prompt") or {}).get("shapeNoun"),
            "imagePrompt": ip.get("promptText"),
            "imagePick": {"status": ip.get("status"), "outcome": ip.get("outcome"), "seconds": ip.get("seconds"),
                          "shownOrder": ip.get("shownOrder"), "pickedSeed": ip.get("pickedSeed"),
                          "images": [{"seed": x.get("seed"), "shown": x.get("shown"), "position": x.get("position"),
                                      "problem": x.get("problem"), "gate": x.get("gate")} for x in ip.get("images") or []]},
            "meshGate": asset.get("gate"), "meshCandidateId": an.get("candidateId")},
        "earlierRounds": len(earlier),
        "runnerReady": sel.get("runnerReady"), "runnerBlockers": sel.get("runnerBlockers"),
        "formTypeSource": (sel.get("sources") or {}).get("form.type"),
        "formAsset": (sel.get("form") or {}).get("asset"),
    }


def collect(sid, logs, roots):
    spec_p = logs / "scenes" / f"{sid}.json"
    spec = json.loads(spec_p.read_text(encoding="utf-8")) if spec_p.exists() else None
    selp = logs / "selection" / sid / "selection.json"
    sel = json.loads(selp.read_text(encoding="utf-8")) if selp.exists() else None
    slog_p = logs / f"{sid}.json"
    slog = json.loads(slog_p.read_text(encoding="utf-8")) if slog_p.exists() else {}
    out = {"spec": _form_slots(spec), "summary": compact(sel), "selection": None}
    ev = [e for e in slog.get("events", []) if e.get("type") == "scene:llm_fill"]
    out["llmFillEvent"] = ev[-1]["payload"] if ev else None
    out["shapeLlmEvents"] = [e.get("payload") for e in slog.get("events", []) if e.get("type") == "selection:shape_llm"]
    out["guardLabels"] = [t.get("guard") for t in slog.get("turns", []) if t.get("speaker") == "participant"]
    out["alerts"] = slog.get("alerts")
    if sel:
        out["llmFill"] = sel.get("llmFill")
        out["selection"] = {"runnerReady": sel.get("runnerReady"), "runnerBlockers": sel.get("runnerBlockers"),
                            "sources": sel.get("sources"), "form": sel.get("form"), "selection": sel.get("selection"),
                            "llmFillExposed": sel.get("llmFillExposed"), "generation": sel.get("generation")}
    return scrub(out, roots)


async def run(a):
    out = Path(a.out)
    shots = out / "shots"
    raw = Path(a.raw)
    shots.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    logs = Path(a.logs)
    roots = [(logs, "<logs>"), (Path(a.gen_out), "<gen3d-out>"), (raw, "<raw>"), (REPO, "<repo>")]
    cases = json.loads(Path(a.cases).read_text(encoding="utf-8")) if a.cases else CASES
    only = set(a.only.split(",")) if a.only else None
    prof = tempfile.mkdtemp(prefix="ifs-g82-cdp-")
    W, H = 1280, 1100
    proc = subprocess.Popen([a.chrome, "--headless=new", f"--remote-debugging-port={a.cdp_port}", f"--user-data-dir={prof}",
                             f"--window-size={W},{H}", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                             "--disable-background-networking", "--disable-component-update", "--disable-sync", "about:blank"])
    resp_path = out / "results.json"
    results = json.loads(resp_path.read_text(encoding="utf-8")) if (resp_path.exists() and a.resume) else {"cases": {}}
    results["run"] = {"sidPrefix": a.sid_prefix, "tag": a.tag, "base": a.base, "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S")}
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

            async def shot(name, r, sid):
                await ev("__g82.scrollTop()")
                h = await ev("document.documentElement.scrollHeight")
                hh = max(H, min(int(h), 3000))
                await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": hh, "deviceScaleFactor": 1, "mobile": False})
                await asyncio.sleep(1.2)          # WebGL 겹침 자리 다시 맞춤
                d = await call("Page.captureScreenshot", {"format": "png"})
                (shots / f"{name}.png").write_bytes(base64.b64decode(d["data"]))
                await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})
                r["privacy"][name] = privacy_check(await ev("__g82.pageText()"), sid, roots)
                return f"shots/{name}.png"

            async def clip(sel, path):
                r = await ev(f"__g82.rect({json.dumps(sel)})")
                if not r:
                    return None
                await asyncio.sleep(0.5)
                d = await call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
                                                          "clip": {"x": r["x"], "y": r["y"], "width": r["w"], "height": r["h"], "scale": 1}})
                Path(path).write_bytes(base64.b64decode(d["data"]))
                return True

            async def wait_generating(st, cid, tag, r, sid):
                """생성 대기 화면(있으면) 한 장 찍고 끝날 때까지 기다린다."""
                await asyncio.sleep(2.5)
                st = await ev("__g82.info()")
                if st["stage"] == "generating":
                    r["shots"][f"wait_{tag}"] = await shot(f"{cid}_wait_{tag}", r, sid)
                    st = await ev("__g82.waitLeave('generating', 600000)", 700)
                else:
                    st = await ev("__g82.settle()")
                return st

            task = asyncio.create_task(reader())
            await call("Runtime.enable")
            await call("Page.enable")
            await call("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})

            for case in cases:
                cid, kind, text, reject = case["id"], case.get("kind", ""), case["text"], bool(case.get("reject"))
                if only and cid not in only:
                    continue
                sid = f"{a.sid_prefix}-{cid}-{a.tag}"
                r = {"id": cid, "kind": kind, "text": text, "reject": reject, "sessionId": sid, "steps": [], "shots": {},
                     "timings": {}, "privacy": {}, "reachedEnd": False}
                console.clear()
                print(f"== {cid} {text}{' (reject)' if reject else ''}", flush=True)
                t_case = time.time()
                try:
                    r["interview"] = interview(a.base, sid, text)
                    r["timings"]["interviewS"] = r["interview"].get("seconds")
                    if not r["interview"].get("selectionAvailable"):
                        r["result"] = "interview_not_done"
                        raise RuntimeError(f"면담이 끝나지 않음: {r['interview']}")
                    await call("Page.navigate", {"url": f"{a.base}/?sid={sid}&view=participant"})
                    await ev("(async()=>{while(!window.ifsStage) await new Promise(r=>setTimeout(r,50)); return true;})()", 60)
                    await asyncio.sleep(1.0)
                    await ev(HELPERS)
                    t_next = time.time()
                    st = await ev("__g82.next()")
                    r["timings"]["nextToCandidatesS"] = round(time.time() - t_next, 1)
                    r["steps"].append({"at": "after_next", **st})
                    if st["stage"] != "selecting":
                        r["shots"]["a"] = await shot(f"{cid}_a_no_candidates", r, sid)
                        r["result"] = f"no_selecting_stage:{st['stage']}"
                    else:
                        r["shots"]["a"] = await shot(f"{cid}_a_candidates", r, sid)
                        t_none = time.time()
                        await ev("__g82.clickNone()")
                        st = await wait_generating(st, cid, "llm_image", r, sid)
                        r["timings"]["noneToNextScreenS"] = round(time.time() - t_none, 1)
                        r["steps"].append({"at": "after_none", **st})
                        if st["stage"] == "picking":
                            name = f"{cid}_b_images_basis" if st.get("basisShown") else f"{cid}_b_images"
                            r["shots"]["b"] = await shot(name, r, sid)
                            r["basisShown"] = st.get("basisShown")
                            imgs = st["imagePick"]["images"]
                            rnd = st["imagePick"]["round"] if st["imagePick"]["round"] is not None else 0
                            for im in imgs:
                                data = urllib.request.urlopen(f"{a.base}/api/sessions/{sid}/selection/image-pick/{rnd}/{im['position']}.png").read()
                                (raw / f"{cid}_img_r{rnd}_p{im['position']}.png").write_bytes(data)
                            if reject:
                                if not st.get("wrongButton"):
                                    r["result"] = "reject_button_missing"
                                else:
                                    t_rej = time.time()
                                    await ev("__g82.clickFkey('img:basis-wrong')")
                                    await asyncio.sleep(1.5)
                                    st = await ev("__g82.settle()")
                                    r["timings"]["rejectToNextScreenS"] = round(time.time() - t_rej, 1)
                                    r["steps"].append({"at": "after_reject", **st})
                                    r["shots"]["b2"] = await shot(f"{cid}_b2_after_reject_{st['stage']}", r, sid)
                                    r["result"] = f"basis_rejected:{st['stage']}"
                            else:
                                first = imgs[0]["position"]
                                r["pickedPosition"] = first
                                t_pick = time.time()
                                await ev(f"__g82.clickFkey('img:{first}')")
                                st = await wait_generating(st, cid, "mesh", r, sid)
                                r["timings"]["pickToNextScreenS"] = round(time.time() - t_pick, 1)
                                r["steps"].append({"at": "after_pick", **st})
                                gen = [c for c in st["candidates"] if c["afterNone"]]
                                if st["stage"] == "selecting" and gen:
                                    r["shots"]["c"] = await shot(f"{cid}_c_mesh", r, sid)
                                    await clip(f'.cand[data-id="{gen[0]["id"]}"] .preview', raw / f"{cid}_mesh_thumb.png")
                                    await ev(f"__g82.clickFkey('cand:{gen[0]['id']}')")
                                    st = await ev("__g82.waitStage(['adjusting'], 60000)", 90)
                                    st = await ev("__g82.settle()")
                                    r["steps"].append({"at": "after_choose_generated", **st})
                                    r["shots"]["d"] = await shot(f"{cid}_d_adjust", r, sid)
                                    r["result"] = "generated_and_chosen"
                                else:
                                    r["shots"]["c"] = await shot(f"{cid}_c_no_mesh_{st['stage']}", r, sid)
                                    r["result"] = f"mesh_not_shown:{st['stage']}"
                        elif st["stage"] == "adjusting":
                            r["shots"]["d"] = await shot(f"{cid}_d_adjust_blocked", r, sid)
                            r["result"] = "blocked_or_not_started"
                        else:
                            r["shots"]["b"] = await shot(f"{cid}_b_other_{st['stage']}", r, sid)
                            r["result"] = f"unexpected_stage:{st['stage']}"
                    # 조절 끝내기([다 했어요] — selection.json 마무리)
                    stg = await ev("__g82.stage()")
                    if stg == "adjusting":
                        await ev("(()=>{const b=document.querySelector('.stage .buttons button.primary'); if(b) b.click(); return !!b;})()")
                        try:
                            st = await ev("__g82.waitStage(['premeasure','done'], 30000)", 60)
                            r["reachedEnd"] = True
                            r["endStage"] = st["stage"]
                        except Exception as ex:  # noqa: BLE001
                            r["finishError"] = str(ex)
                except Exception as ex:  # noqa: BLE001
                    r["error"] = str(ex)[:800]
                    try:
                        r["shots"]["error"] = await shot(f"{cid}_x_error", r, sid)
                    except Exception:  # noqa: BLE001
                        pass
                r["timings"]["caseTotalS"] = round(time.time() - t_case, 1)
                r["console"] = list(console)
                r["collected"] = collect(sid, logs, roots)
                results["cases"][cid] = r
                resp_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"   -> {r.get('result')} {r.get('error', '')[:200]} {r['timings']} privacy={sum(map(len, r['privacy'].values()))}",
                      flush=True)
            task.cancel()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        results["run"]["endedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        resp_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8011")
    ap.add_argument("--logs", required=True, help="서버 설정의 log_dir(저장소 밖 임시 위치)")
    ap.add_argument("--gen-out", default=str(REPO.parent / "gen3d-out"),
                    help="생성기 산출물 폴더(설정 [gen3d] assets_dir, 기본 저장소 옆 gen3d-out) — results.json에서 경로를 가리는 데만 씀")
    ap.add_argument("--out", default=str(here), help="results.json·shots/를 쓸 폴더")
    ap.add_argument("--raw", default="", help="그림·메시 축소판 원본 폴더(저장소 밖, 기본 <logs>/../raw)")
    ap.add_argument("--cases", default="", help="문장 목록 JSON([{id, kind, text, reject}]). 없으면 기본 9개")
    ap.add_argument("--sid-prefix", default="SYN-G82", help="세션 ID 앞부분(<prefix>-<ID>-<tag>)")
    ap.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    ap.add_argument("--cdp-port", type=int, default=9342)
    ap.add_argument("--only", default="")
    ap.add_argument("--tag", default="1", help="같은 문장을 다시 돌릴 때 세션 ID 끝에 붙일 값")
    ap.add_argument("--resume", action="store_true", help="results.json에 이어 쓰기")
    a = ap.parse_args()
    if not a.raw:
        a.raw = str(Path(a.logs).resolve().parent / "raw")
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
