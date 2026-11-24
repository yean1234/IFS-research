"""챗봇 웹 화면 사용성 확인(G44): 화면별 캡처 + DOM 측정 + 키보드만으로 끝까지 가기. 헤드리스 Chrome을 DevTools 프로토콜로 몬다.

합성 세션만 쓴다(ui_server.py가 chatbot/scenarios/selection/의 합성 시나리오로 단계별 세션을 만들어 둠). 서버는 127.0.0.1에만 연다.
출력은 --out(저장소 밖)에 둔다: png/<mode>_<view>_<width>_<screen>.png, metrics_<mode>.json, keyboard_<mode>.json.

  python ui_shots.py --out <저장소 밖 폴더> --mode webgl|image|none [--views participant researcher] [--widths 1440 1024 768]
       [--screens interview confirm ...] [--web-dir <이전 웹 파일 폴더>] [--keyboard] [--label after]
  이 스크립트는 websockets·Pillow가 있는 python으로 돌린다. 서버는 chatbot/.venv의 python으로 따로 띄운다(--venv).

측정(화면마다, 보이는 것만):
  - 가로 스크롤(문서 폭 > 창 폭)
  - 누를 수 있는 것(button·a·label에 싸인 input·textarea·[tabindex]≥0)의 크기: 가장 작은 높이·폭, 44px 미만 목록
  - 글자 크기: 참여자 영역 글자의 가장 작은 크기와 13px 미만·16px 미만 수
  - 대비: 글자가 있는 요소마다 글자색과 실제 배경색(조상 중 처음 불투명한 배경)으로 WCAG 대비비. 4.5:1(큰 글자 3:1) 미만 목록
  - 연구자 패널이 보이는가
키보드: 새 세션을 설정 화면부터 Tab·Enter·Space·방향키·글자 입력만으로 끝(사전 측정 제출)까지 진행하고, 단계마다
  누른 Tab 수, 초점이 간 요소, 초점 테두리가 보였는지(outline 또는 box-shadow), 화면 순서와 탭 순서가 어긋난 수를 적는다.
"""
import argparse
import asyncio
import base64
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

MEASURE = r"""
(() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    if (e.closest(".topbar") && e.closest(".topbar").getBoundingClientRect().height < 4) return false;
    if (e.closest(".brand") && e.closest(".brand").getBoundingClientRect().width < 4) return false;   // 낭독기용으로만 남긴 제목
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && !e.closest("[hidden]") && !e.closest(".webgl-host") && !e.closest(".sr-only"); };
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lin = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
  const blend = (top, bot) => ({ r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1 });
  function bgOf(e) {
    const stack = [];
    for (let n = e; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; } }
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) base = blend(stack[i], base);
    return base;
  }
  const desc = (e) => (e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (e.className && typeof e.className === "string" ? "." + e.className.trim().split(/\s+/).join(".") : "")).slice(0, 80);
  const w = window.ifsStage && window.ifsStage._webgl;
  const out = { thumbJobs: w && w.dbg ? w.dbg.thumbJobs.slice() : null,
                thumbs: [...document.querySelectorAll(".opts .opt")].map((b) => b.classList.contains("has-thumb") ? "img" : b.classList.contains("thumb-failed") ? "num-failed" : b.classList.contains("thumb-wait") ? "wait" : "num"),
                width: innerWidth, docWidth: document.documentElement.scrollWidth, hScroll: document.documentElement.scrollWidth > innerWidth + 1,
                researcherVisible: !!(document.querySelector("#researcher") && vis(document.querySelector("#researcher"))) };
  // 누를 자리
  const targets = [];
  const seen = new Set();
  for (const e of document.querySelectorAll("button, a[href], textarea, input:not([type=radio]):not([type=checkbox]), label, [tabindex]:not([tabindex='-1'])")) {
    if (!vis(e)) continue;
    if (e.tagName === "LABEL" && !e.querySelector("input")) continue;
    if (e.closest("#researcher")) continue;
    const r = e.getBoundingClientRect();
    if (seen.has(e)) continue; seen.add(e);
    targets.push({ el: desc(e), text: (e.innerText || e.getAttribute("aria-label") || "").trim().slice(0, 24), w: Math.round(r.width), h: Math.round(r.height) });
  }
  out.targets = { n: targets.length, minH: Math.min(...targets.map((t) => t.h)), minW: Math.min(...targets.map((t) => t.w)),
                  under44: targets.filter((t) => t.h < 44 || t.w < 44), under24: targets.filter((t) => t.h < 24 || t.w < 24) };
  // 글자와 대비(참여자 영역)
  const texts = [];
  const root = document.querySelector(".participant") || document.body;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const els = new Set();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (n.textContent.trim() && n.parentElement && vis(n.parentElement)) els.add(n.parentElement);
  for (const b of document.querySelectorAll(".topbar *")) if (b.childNodes.length && [...b.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim()) && vis(b)) els.add(b);
  for (const e of els) {
    const cs = getComputedStyle(e);
    const fg0 = parse(cs.color); if (!fg0) continue;
    const bg = bgOf(e); const fg = blend(fg0, bg);
    const L1 = lum(fg), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700;
    const large = size >= 24 || (bold && size >= 18.66);
    const op = parseFloat(cs.opacity);
    texts.push({ el: desc(e), text: e.textContent.trim().slice(0, 30), size, lineHeight: cs.lineHeight, ratio: Math.round(ratio * 100) / 100,
                 need: large ? 3 : 4.5, disabled: !!e.closest("button:disabled, .off, [aria-disabled=true]") });
  }
  out.text = { n: texts.length, minSize: Math.min(...texts.map((t) => t.size)), under13: texts.filter((t) => t.size < 13),
               under16: texts.filter((t) => t.size < 16).length, minRatio: Math.min(...texts.filter((t) => !t.disabled).map((t) => t.ratio)),
               lowContrast: texts.filter((t) => !t.disabled && t.ratio < t.need) };
  return out;
})()
"""

KB_HELPERS = r"""
window.__kb = (() => {
  const desc = (e) => !e ? null : (e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (e.className && typeof e.className === "string" && e.className.trim() ? "." + e.className.trim().split(/\s+/).join(".") : "")
                       + (e.dataset && e.dataset.fkey ? "[" + e.dataset.fkey + "]" : "") + " '" + ((e.getAttribute("aria-label") || e.innerText || e.value || "").trim().slice(0, 20)) + "'");
  function focusInfo() {
    const e = document.activeElement;
    if (!e || e === document.body) return { el: null };
    const cs = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    const ring = (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) >= 2) || (cs.boxShadow && cs.boxShadow !== "none");
    // 라디오는 라벨 쪽에 테두리를 그린다(:has/:focus-within)
    let ringLabel = false;
    const lab = e.closest("label");
    if (lab) { const lc = getComputedStyle(lab); ringLabel = (lc.outlineStyle !== "none" && parseFloat(lc.outlineWidth) >= 2) || (lc.boxShadow && lc.boxShadow !== "none"); }
    return { el: desc(e), ring: ring || ringLabel, x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), visible: r.bottom > 0 && r.top < innerHeight };
  }
  return { focusInfo, desc,
    match(sel, text) { const e = document.activeElement; if (!e || e === document.body) return false;
      if (sel && !e.matches(sel)) return false; if (text && !((e.innerText || e.value || e.getAttribute("aria-label") || "").includes(text))) return false; return true; },
    stage() { const s = window.ifsStage && window.ifsStage._state; return { stage: s && s.view ? s.view.stage : null, busy: s ? s.busy : null,
      awaiting: state && state.view ? state.view.awaiting : null }; },
  };
})();
true
"""


class Cdp:
    def __init__(self, ws):
        self.ws, self.seq, self.waiting, self.console = ws, 0, {}, []

    async def reader(self):
        async for msg in self.ws:
            m = json.loads(msg)
            if "id" in m and m["id"] in self.waiting:
                self.waiting.pop(m["id"]).set_result(m)
            elif m.get("method") == "Runtime.exceptionThrown":
                d = m["params"]["exceptionDetails"]
                self.console.append({"type": "exception", "text": str((d.get("exception") or {}).get("description", d.get("text")))[:400]})
            elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] in ("error", "warning"):
                p = m["params"]
                self.console.append({"type": p["type"], "text": " ".join(str(x.get("value", x.get("description", ""))) for x in p.get("args", []))[:400]})

    async def call(self, method, params=None, timeout=120):
        self.seq += 1
        fut = asyncio.get_running_loop().create_future()
        self.waiting[self.seq] = fut
        await self.ws.send(json.dumps({"id": self.seq, "method": method, "params": params or {}}))
        r = await asyncio.wait_for(fut, timeout)
        if "error" in r:
            raise RuntimeError(f"{method}: {r['error']}")
        return r["result"]

    async def js(self, expr, timeout=120):
        r = await self.call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True}, timeout)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            raise RuntimeError(str((d.get("exception") or {}).get("description", d.get("text")))[:600])
        return r["result"].get("value")

    async def key(self, key, code=None, vk=None, text=None, shift=False):
        mods = 8 if shift else 0
        base = {"key": key, "code": code or key, "windowsVirtualKeyCode": vk or 0, "nativeVirtualKeyCode": vk or 0, "modifiers": mods}
        await self.call("Input.dispatchKeyEvent", {"type": "keyDown" if text is None else "keyDown", **base, **({"text": text} if text else {})})
        await self.call("Input.dispatchKeyEvent", {"type": "keyUp", **base})

    async def tab(self, shift=False):
        await self.key("Tab", "Tab", 9, shift=shift)

    async def enter(self):
        await self.key("Enter", "Enter", 13, text="\r")

    async def space(self):
        await self.key(" ", "Space", 32, text=" ")

    async def arrow(self, d="Right"):
        await self.key("Arrow" + d, "Arrow" + d, {"Left": 37, "Up": 38, "Right": 39, "Down": 40}[d])

    async def type(self, text):
        await self.call("Input.insertText", {"text": text})

    async def shot(self, full=True) -> bytes:
        p = {"format": "png", "captureBeyondViewport": full}
        return base64.b64decode((await self.call("Page.captureScreenshot", p))["data"])


WAIT_READY = r"""
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const t0 = performance.now();
  const until = async (fn, ms) => { for (;;) { let v = false; try { v = fn(); } catch (e) {} if (v) return true; if (performance.now() - t0 > ms) return false; await sleep(50); } };
  await until(() => document.readyState === "complete" && window.ifsStage, 15000);
  const S = window.ifsStage._state;
  const sid = new URLSearchParams(location.search).get("sid");
  if (sid) {
    await until(() => state.view, 15000);
    if (state.view.selection && state.view.selection.stage) await until(() => S.view && S.view.stage && !S.busy, 20000);
  }
  await sleep(400);
  const st = S.view && S.view.stage;
  let ok = true;
  if (st === "selecting") ok = await until(() => [...document.querySelectorAll(".cand .preview")].every((p) => { const i = p.querySelector("img"); return p.classList.contains("text") || (i && i.src && i.complete && i.naturalWidth > 0); }), 90000);
  if (st === "adjusting") {
    ok = await until(() => { const s = document.querySelector(".live-slot"); if (s) return s.dataset.applied === s.dataset.overrides;
                             const i = document.querySelector(".adjust .preview img"); if (i) return i.complete && i.naturalWidth > 0; return !!document.querySelector(".adjust .preview.text"); }, 60000);
    await until(() => ![...document.querySelectorAll(".opts img.thumb")].some((i) => !i.complete || !i.naturalWidth), 30000);
  }
  if (st === "premeasure") ok = await until(() => document.querySelector("form.premeasure"), 15000);
  await until(() => !S.busy, 15000);
  await sleep(600);
  return { stage: st, ok, ms: Math.round(performance.now() - t0) };
})()
"""


def http_json(url, timeout=30):
    return json.load(urllib.request.urlopen(url, timeout=timeout))


def small_png(data: bytes, path: Path, scale: float) -> None:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if scale != 1:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    im.quantize(colors=256, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE).save(path, optimize=True)


async def shots(c, a, base, sessions, out):
    metrics = []
    for view in a.views:
        for width in a.widths:
            await c.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
            for screen in a.screens:
                sid = sessions.get(screen)
                if not sid:
                    continue
                url = f"{base}/?sid={sid}&view={view}"
                await c.call("Page.navigate", {"url": url})
                await asyncio.sleep(0.4)
                # 이전 판(--web-dir)은 view 인자를 모름: 연구자 화면 체크를 풀어 '참여자만' 모양을 만든다
                if a.legacy_view and view == "participant":
                    await c.js("(async()=>{for(let i=0;i<100&&!document.querySelector('#toggle-researcher');i++) await new Promise(r=>setTimeout(r,50));"
                               "const t=document.querySelector('#toggle-researcher'); if(t&&t.checked){t.click();} return true;})()")
                rd = await c.js(WAIT_READY, timeout=180)
                if screen == "crisis":
                    await c.js("(()=>{const m=document.querySelector('.msg.crisis'); if(m) m.scrollIntoView({block:'center'}); return true})()")
                m = await c.js(MEASURE)
                m.update({"view": view, "width": width, "screen": screen, "ready": rd})
                metrics.append(m)
                # 전체 페이지: 창 높이를 문서 높이로 늘린 뒤 보이는 영역만 찍는다(captureBeyondViewport는 WebGL iframe을 빈 칸으로 찍음)
                h = await c.js("Math.min(4000, Math.max(900, document.documentElement.scrollHeight))")
                await c.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": h, "deviceScaleFactor": 1, "mobile": False})
                await asyncio.sleep(0.6)
                data = await c.shot(False)
                await c.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})
                small_png(data, out / "png" / f"{a.mode}_{view}_{width}_{screen}.png", 1.0)
                print(view, width, screen, rd, "hScroll" if m["hScroll"] else "", f"minH {m['targets']['minH']}", f"minFont {m['text']['minSize']}",
                      f"minRatio {m['text']['minRatio']}", flush=True)
    return metrics


async def tab_until(c, pred_js, max_tabs=80):
    visited = []
    for k in range(1, max_tabs + 1):
        await c.tab()
        fi = await c.js("__kb.focusInfo()")
        visited.append(fi)
        if await c.js(pred_js):
            return k, visited
    raise RuntimeError(f"Tab {max_tabs}번 안에 닿지 않음: {pred_js}; 마지막 {visited[-3:]}")


async def wait_js(c, expr, ms=60000):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < ms / 1000:
        try:
            if await c.js(expr):
                return True
        except RuntimeError:
            pass
        await asyncio.sleep(0.1)
    raise RuntimeError("시간 초과: " + expr)


def order_violations(visited):
    """연달아 초점이 간 두 요소에서 뒤 요소가 앞 요소보다 위(24px 넘게)에 있으면 어긋남으로 센다(줄바꿈된 같은 줄은 봐줌)."""
    v = [x for x in visited if x.get("el")]
    return sum(1 for p, q in zip(v, v[1:]) if q["y"] < p["y"] - 24)


async def keyboard(c, a, base, out):
    """설정 화면부터 끝까지 키보드만으로. 마우스 이벤트를 하나도 보내지 않는다."""
    log = {"steps": [], "mode": a.mode}
    await c.call("Emulation.setDeviceMetricsOverride", {"width": 1024, "height": 900, "deviceScaleFactor": 1, "mobile": False})
    await c.call("Page.navigate", {"url": f"{base}/?view=researcher"})
    await wait_js(c, "document.readyState === 'complete' && !!window.ifsStage")
    await asyncio.sleep(0.8)
    await c.js(KB_HELPERS)

    async def step(name, pred, action="enter", text=None):
        k, visited = await tab_until(c, pred)
        fi = visited[-1]
        if text is not None:
            await c.type(text)
        if action == "enter":
            await c.enter()
        elif action == "space":
            await c.space()
        log["steps"].append({"step": name, "tabs": k, "focus": fi["el"], "ring": fi["ring"], "inView": fi["visible"],
                             "noRing": [x["el"] for x in visited if x.get("el") and not x["ring"]],
                             "orderViolations": order_violations(visited)})
        await asyncio.sleep(0.25)

    sid = f"SYN-UI-KB-{a.mode.upper()}"
    await step("가명 ID 입력", "__kb.match('#session-id')", action=None, text=sid)
    # 조건 라디오: 정적(조건 1)으로 방향키
    await step("조건 고르기", "__kb.match('input[name=condition]')", action=None)
    for _ in range(4):
        if await c.js("document.querySelector('input[name=condition]:checked').value === 'static'"):
            break
        await c.arrow("Down")
    await step("세션 만들기", "__kb.match('#btn-create')")
    await wait_js(c, "!!(state && state.sid)")
    await c.js(KB_HELPERS)
    await step("시작", "__kb.match('#buttons button')")
    replies = ["가슴이 답답해요", "가슴 안쪽이요", "무거워요", "답답하고 무거운 느낌이에요", "모르겠어요", "모르겠어요", "없어요"]
    for n in range(40):
        await asyncio.sleep(0.3)
        await wait_js(c, "!state.busy")
        aw = await c.js("state.view.awaiting")
        if aw == "reply":
            # 답 입력칸이 이미 초점을 갖고 있으면 Tab 없이 입력(면담 화면은 질문 뒤 입력칸에 초점을 둔다)
            focused = await c.js("document.activeElement && document.activeElement.id === 'input'")
            if not focused:
                await step(f"답 입력칸 {n}", "__kb.match('#input')", action=None)
            await c.type(replies.pop(0) if replies else "없어요")
            await c.enter()
            log["steps"].append({"step": f"답 {n}", "tabs": 0 if focused else None, "focus": "textarea#input", "ring": True})
        elif aw == "soft_check":
            await step(f"계속 {n}", "__kb.match('#buttons button.primary')")
        elif aw == "confirm":
            await step("확정", "__kb.match('#buttons button.primary')")
            break
        else:
            break
    await wait_js(c, "state.view.state === 'done'")
    await asyncio.sleep(0.5)
    (out / "png" / f"kb_{a.mode}_1_next.png").write_bytes(await c.shot(False))
    await step("다음으로", "__kb.match('#buttons button', '다음으로')")
    await wait_js(c, "!!(window.ifsStage._state.view && window.ifsStage._state.view.stage)")
    st = await c.js("window.ifsStage._state.view.stage")
    if st == "selecting":
        await c.js(WAIT_READY, timeout=180)
        (out / "png" / f"kb_{a.mode}_2_candidates.png").write_bytes(await c.shot(False))
        # 맨 위로 초점이 옮겨졌는지(새 화면 제목)
        log["focusAfterStage"] = await c.js("__kb.focusInfo()")
        await step("후보 고르기(두 번째)", "__kb.match('.cand:nth-child(2) button')")
        await wait_js(c, "window.ifsStage._state.view.stage === 'adjusting' && !window.ifsStage._state.busy")
    await c.js(WAIT_READY, timeout=180)
    log["focusAfterAdjust"] = await c.js("__kb.focusInfo()")
    # 색 견본 묶음: Tab 한 번에 들어가(지금 고른 견본) 방향키로 옮긴 뒤 Enter
    await step("색 견본 묶음", "__kb.match('.adjust-row[data-item=color] .chip')", action=None)
    before = await c.js("document.activeElement.dataset.swatch")
    await c.arrow("Right")
    log["arrowMovedInSwatches"] = (await c.js("document.activeElement.dataset.swatch")) != before
    await c.enter()
    await c.js(WAIT_READY, timeout=60)
    log["focusAfterSwatch"] = await c.js("__kb.focusInfo()")
    # 밝기 +를 두 번(두 번째는 Tab 없이 — 다시 그린 뒤에도 초점이 같은 단추에 남아야 함)
    b0 = await c.js("window.ifsStage._state.view.current.items.brightness")
    await step("밝기 +", "__kb.match('.adjust-row[data-item=brightness] .stepper button:last-child')")
    await c.js(WAIT_READY, timeout=60)
    still = await c.js("__kb.match('.adjust-row[data-item=brightness] .stepper button:last-child')")
    log["focusKeptAfterRedraw"] = still
    if still:
        await c.enter()
        await c.js(WAIT_READY, timeout=60)
    log["brightness"] = [b0, await c.js("window.ifsStage._state.view.current.items.brightness")]
    if await c.js("!!document.querySelector('.adjust-row[data-item=form] .opts button:not(:disabled)')"):
        await step("형태 견본 묶음", "__kb.match('.adjust-row[data-item=form] .opts button')", action=None)
        await c.key("Home", "Home", 36)
        await c.arrow("Right")
        await c.arrow("Right")
        log["formThirdFocused"] = await c.js("__kb.match('.adjust-row[data-item=form] .opts button:nth-child(3)')")
        await c.enter()
        await c.js(WAIT_READY, timeout=60)
        log["formAfter"] = await c.js("window.ifsStage._state.view.current.items.form")
    (out / "png" / f"kb_{a.mode}_3_adjust.png").write_bytes(await c.shot(False))
    await step("다 고쳤어요", "__kb.match('.stage .buttons button.primary')")
    await wait_js(c, "!!document.querySelector('form.premeasure')")
    await asyncio.sleep(0.6)
    # 사전 측정: 문항마다 Tab으로 라디오 묶음에 들어가 방향키로 고름(A1–A7 답하지 않기, 평정 두 개 4)
    items = await c.js("[...document.querySelectorAll('fieldset.pm-item')].map((f) => f.dataset.item)")
    for it in items:
        k, visited = await tab_until(c, f"__kb.match('input[name=\"{it}\"]')")
        want = "skip" if it.startswith("A") else "4"
        for _ in range(10):
            cur = await c.js(f"(document.querySelector('input[name=\"{it}\"]:checked')||{{}}).id || ''")
            if cur.endswith("-" + want):
                break
            # 처음 들어가면 아무것도 고르지 않은 상태 → Space로 지금 초점을 고르고 방향키로 옮김
            if not cur:
                await c.space()
            else:
                await c.arrow("Right")
            await asyncio.sleep(0.05)
        fi = await c.js("__kb.focusInfo()")
        log["steps"].append({"step": f"문항 {it}", "tabs": k, "focus": fi["el"], "ring": fi["ring"], "chosen": want,
                             "noRing": [x["el"] for x in visited if x.get("el") and not x["ring"]], "orderViolations": order_violations(visited)})
    (out / "png" / f"kb_{a.mode}_4_premeasure.png").write_bytes(await c.shot(False))
    await step("제출", "__kb.match('form.premeasure button[type=submit]')")
    await wait_js(c, "window.ifsStage._state.view.stage === 'done'")
    await asyncio.sleep(0.5)
    (out / "png" / f"kb_{a.mode}_5_done.png").write_bytes(await c.shot(False))
    log["final"] = await c.js("window.ifsStage._state.view.stage")
    log["sessionId"] = sid
    return log


async def run(a):
    out = Path(a.out).resolve()
    if out.exists() and not a.keep:
        shutil.rmtree(out)
    (out / "png").mkdir(parents=True, exist_ok=True)
    log_dir = out / "logs"
    base = f"http://127.0.0.1:{a.port}"
    cmd = [a.venv, str(HERE / "ui_server.py"), "--log-dir", str(log_dir), "--port", str(a.port), "--mode", a.mode,
           "--queue-dir", str(out / "queue")]
    if a.webgl_dir:
        cmd += ["--webgl-dir", a.webgl_dir]
    if a.player:
        cmd += ["--player", a.player]
    if a.web_dir:
        cmd += ["--web-dir", a.web_dir]
    srv_log = open(out / f"server_{a.mode}.out", "w", encoding="utf-8")
    srv = subprocess.Popen(cmd, cwd=str(REPO / "chatbot"), stdout=srv_log, stderr=subprocess.STDOUT)
    prof = tempfile.mkdtemp(prefix="ifs-ui-")
    proc = None
    try:
        for _ in range(3000):
            if (log_dir / "ui_sessions.json").exists():
                try:
                    http_json(base + "/api/health", 1)
                    break
                except OSError:
                    pass
            if srv.poll() is not None:
                raise RuntimeError("서버가 끝남: " + (out / f"server_{a.mode}.out").read_text(encoding="utf-8")[-2000:])
            time.sleep(0.1)
        sessions = json.loads((log_dir / "ui_sessions.json").read_text(encoding="utf-8"))
        print("preview", sessions["preview"].get("mode"), flush=True)
        args = [a.chrome, "--headless=new", f"--remote-debugging-port={a.cdp_port}", f"--user-data-dir={prof}", "--window-size=1440,900",
                "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
                "--disable-component-update", "--disable-sync", "--hide-scrollbars", "about:blank"]
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
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=512 * 1024 * 1024) as ws:
            c = Cdp(ws)
            rd = asyncio.create_task(c.reader())
            for m in ("Runtime.enable", "Page.enable"):
                await c.call(m)
            result = {"label": a.label, "mode": a.mode, "preview": sessions["preview"]}
            if a.screens:
                result["metrics"] = await shots(c, a, base, sessions["sessions"], out)
            if a.keyboard:
                try:
                    result["keyboard"] = await keyboard(c, a, base, out)
                except Exception as e:  # noqa: BLE001
                    result["keyboard"] = {"error": f"{type(e).__name__}: {e}"[:800]}
                    (out / "png" / f"kb_{a.mode}_error.png").write_bytes(await c.shot(False))
            result["console"] = c.console
            rd.cancel()
        (out / f"ui_{a.label}_{a.mode}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
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
        q = out / "queue"
        if q.exists():
            (q / "quit.req.json").write_text("{}", encoding="utf-8")
        shutil.rmtree(prof, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="after")
    ap.add_argument("--mode", choices=["webgl", "image", "none"], default="webgl")
    ap.add_argument("--views", nargs="*", default=["participant", "researcher"])
    ap.add_argument("--widths", nargs="*", type=int, default=[1440, 1024, 768])
    ap.add_argument("--screens", nargs="*", default=["interview", "confirm", "crisis", "next", "candidates", "adjust", "adjust_skipped",
                                                      "premeasure", "done"])
    ap.add_argument("--webgl-dir", default=str(REPO.parent / "webgl-build" / "preview"))
    ap.add_argument("--player", default=str(REPO.parent / "webgl-build" / "preview-win" / "IFSPreview.exe"))
    ap.add_argument("--web-dir", default="")
    ap.add_argument("--legacy-view", action="store_true", help="이전 판 화면: 참여자 보기를 '연구자 화면' 체크를 풀어 만든다")
    ap.add_argument("--keyboard", action="store_true")
    ap.add_argument("--keep", action="store_true", help="--out 폴더를 지우지 않음")
    ap.add_argument("--venv", default=str(REPO / "chatbot" / ".venv" / "Scripts" / "python.exe"))
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--cdp-port", type=int, default=9345)
    a = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
