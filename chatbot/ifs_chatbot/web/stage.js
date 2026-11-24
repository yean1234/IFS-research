// 면담 뒤 데스크톱 단계 — 4 후보 선택 · 5 조절 · 6 사전 측정 (D5, 결정 G10·G13·G22·G23, G31·G34).
// G34: 구별되는 후보가 하나뿐이면 서버가 선택 단계를 건너뛰고 바로 adjusting으로 준다(후보 1개 화면은 없음).
// G31: 조절 항목은 서버가 준 순서(값 표 adjustItems.order, 색이 맨 앞) 그대로 그린다.
// 외부 라이브러리·CDN·글꼴 없음(원칙 5). 문구는 서버가 shared/protocol/selection_protocol.v0.json에서 준 것만 쓴다(모두 초안).
// 미리보기 어댑터: preview.mode = webgl(같은 출처 Unity WebGL 빌드, G12) | image(서버가 Unity 미리보기 플레이어로 그린 PNG, G25)
//                 | none(속성 요약 글). mode는 세션마다 서버가 정한다. webgl이 안 되면 이 화면이 서버에 알리고(POST …/preview/client)
//                 서버가 그 세션을 image(예비 플레이어가 없으면 none)로 내린 뷰를 돌려준다. 실제로 쓴 방식도 같은 곳에 알린다.
"use strict";

(function () {
  const S = { cfg: null, view: null, sid: null, imgSeq: 0, busy: false, answers: {}, reported: new Set(),
              drawnStage: null, focusKey: null, samples: new Map(), lastThumb: {} };

  // G44 화면 표현 설정(기록과 무관).
  // 형태 버튼: 낱말·번호 대신 Unity가 그린 견본(지금 상태에서 형태만 바꾼 정지 그림). 글 요약(none)에서는 번호 그대로.
  // 움직임 버튼: 정지 그림으로는 구별되지 않으므로, 버튼에 초점이 가거나 마우스가 머물면(DWELL_MS) 본 미리보기에서 그 움직임을
  //   재생하고 떠나면 되돌린다(WebGL만). 이렇게 본 것은 조절 기록에 남지 않는다(누른 것만 기록) → ⚠ 사람이 정할 것. 끄려면 false.
  //   화살표·물결 같은 기호는 방향·성질을 시스템이 해석해 내미는 것이라 쓰지 않았다(docs/validation/ui/README.md).
  const MOTION_PREVIEW_ON_DWELL = true;
  const DWELL_MS = 350;
  const THUMB_W = 128, THUMB_H = 96;      // 견본 캡처 크기(화면에는 64×48로, 고해상도 화면 대비 2배)
  const reducedMotion = () => !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  async function ensureConfig() {
    if (S.cfg) return S.cfg;
    S.cfg = await api("GET", "/api/selection/config");
    return S.cfg;
  }

  function phrase(id) { return (S.cfg && S.cfg.phrases[id]) || ""; }

  // 덮어쓰기 비교용 정규형(키 정렬, 수치는 소수 6자리). Unity가 돌려준 overrides와 요청한 것을 대조한다.
  function canon(ov) {
    const o = ov || {};
    return JSON.stringify(Object.keys(o).sort().map((k) => [k, typeof o[k] === "number" ? Math.round(o[k] * 1e6) / 1e6 : o[k]]));
  }

  // ── 서버에 미리보기 결과 알리기 ─────────────────────────────────────────────
  // shown: 이 단계에서 이 방식으로 실제로 그렸음(단계·방식마다 한 번). fallback: 이 방식으로 그리지 못함 → 서버가 내린 뷰로 다시 그림.
  function reportShown(mode, stage, webgl) {
    const key = `${S.sid}:${stage}:${mode}`;
    if (!S.sid || S.reported.has(key)) return;
    S.reported.add(key);
    api("POST", `/api/sessions/${S.sid}/preview/client`, { event: "shown", mode, stage, webgl: webgl || null })
      .catch((e) => console.warn("[preview] shown 알림 실패", e));
  }

  async function reportFallback(mode, reason) {
    console.warn(`[preview] ${mode} 실패 → 서버에 알림: ${reason}`);
    try {
      S.view = await api("POST", `/api/sessions/${S.sid}/preview/client`,
        { event: "fallback", mode, stage: S.view && S.view.stage, reason: String(reason).slice(0, 300) });
    } catch (e) {
      // 서버에도 못 알리면 이 화면에서만 글 요약으로 그린다(서버 기록은 남지 않음 → 화면에 경고)
      console.error("[preview] fallback 알림 실패", e);
      if (S.view && S.view.preview) S.view.preview = { ...S.view.preview, mode: "none", reason: `${mode} 실패, 서버 알림 실패: ${reason}` };
    }
    draw();
  }

  // ── 미리보기 어댑터 ────────────────────────────────────────────────────────
  const Preview = {
    mode() { return (S.view && S.view.preview && S.view.preview.mode) || "none"; },

    // target = 후보 id 또는 "current". summary = 서버가 준 속성 요약(none 모드). overrides = 그 그림의 덮어쓰기.
    node(target, summary, overrides) {
      const m = this.mode();
      const stage = S.view.stage;
      if (m === "webgl") return target === "current" ? WebGL.liveSlot(overrides) : WebGL.candidateNode(target, overrides);
      if (m === "image") {
        const img = el("img", { class: "preview-img", alt: "", "data-target": target, "data-mode": "image",
                                src: `/api/sessions/${S.sid}/preview/${target}.png?v=${++S.imgSeq}` });
        const box = el("div", { class: `preview is-loading${target === "current" ? " live-slot-image" : ""}`, "aria-busy": "true" }, img);
        img.addEventListener("load", () => { box.classList.remove("is-loading"); box.removeAttribute("aria-busy"); reportShown("image", stage); });
        img.addEventListener("error", () => refresh(true));   // 플레이어가 죽으면 서버가 이 세션을 none으로 내림 → 다시 그림
        return box;
      }
      reportShown("none", stage);
      return el("div", { class: "preview text", "data-mode": "none" }, el("ul", {}, ...(summary || []).map((s) => el("li", {}, s))));
    },
  };

  // WebGL: Unity WebGL 빌드(window.ifsPreview)를 같은 출처 iframe 하나로 띄운다.
  // - iframe은 세션마다 한 번 만들어 document.body 아래 host에 고정한다. 화면을 다시 그려도(#stage.replaceChildren) 옮기지 않는다
  //   (문서에서 빠졌다 들어온 iframe은 브라우저가 새로 로드해 Unity가 처음부터 다시 시작된다).
  //   후보 화면에서는 화면 밖에 두고, 조절 화면에서는 자리(.live-slot) 위에 겹쳐 놓는다.
  // - 모든 Unity 호출은 큐 하나로 차례로 보낸다(SendMessage 응답을 요청과 짝짓는 템플릿 규칙이 겹친 호출에서 엇갈리지 않게).
  //   덮어쓰기 응답은 Unity가 돌려준 overrides를, 캡처 응답은 요청 id를 대조한다. 어긋나거나 시간을 넘기면 실패로 본다.
  // - 실패하면(WebGL2 없음, Unity 시작 실패·시간 초과, 로드·덮어쓰기·캡처 오류, 컨텍스트 잃음) iframe을 닫고 서버에 알린다
  //   → 서버가 이 세션을 image(없으면 none)로 내리고 기록한다.
  // - 후보 칸은 정지 그림이다(setFrozen(true) 뒤 capture, 값 표 구별 규칙 still_preview_motion의 전제). 조절 화면은 움직임을 재생한다.
  // - 준비 단계에서 형태 값마다 한 번씩 작게 그려 셰이더 컴파일 지연을 후보를 보이기 전에 치른다(서버 previewWarmup).
  const WebGL = {
    sid: null, host: null, frame: null, p: null, started: null, failed: null,
    q: Promise.resolve(), seq: 0, applied: null, frozen: null, caps: new Map(), info: null, slot: null, ro: null,
    thumbCache: new Map(), dbg: { thumbJobs: [] },     // dbg: 검증용(서버로 보내지 않음)

    probe() {
      // 이 브라우저가 WebGL2를 만들 수 있는가. 렌더러 문자열(GPU 이름)은 기록용(참여자 식별 정보 아님)
      try {
        const c = document.createElement("canvas");
        const gl = c.getContext("webgl2");
        if (!gl) return { ok: false, reason: "이 브라우저에서 WebGL2를 쓸 수 없음" };
        const dbg = gl.getExtension("WEBGL_debug_renderer_info");
        const out = { ok: true, version: gl.getParameter(gl.VERSION),
                      renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
                      vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR) };
        const lose = gl.getExtension("WEBGL_lose_context");
        if (lose) lose.loseContext();
        return out;
      } catch (e) {
        return { ok: false, reason: `WebGL2 확인 중 오류: ${e}` };
      }
    },

    timeout(promise, ms, what) {
      let t;
      return Promise.race([promise, new Promise((_, j) => { t = setTimeout(() => j(new Error(`${what}: ${ms} ms 안에 응답 없음`)), ms); })])
        .finally(() => clearTimeout(t));
    },

    // 큐: 앞 요청이 끝나야 다음 요청을 보낸다. 실패해도 큐는 이어지고(다음 요청은 failed를 보고 바로 거부), 실패 처리는 한 번만.
    enqueue(what, fn) {
      const run = this.q.then(() => {
        if (this.failed) throw new Error(this.failed);
        return this.timeout(fn(), (S.view.preview.webglRequestTimeoutMs || 15000), what);
      });
      this.q = run.catch(() => {});
      return run.catch((e) => { this.fail(`${what}: ${e && e.message ? e.message : JSON.stringify(e)}`); throw e; });
    },

    start() {
      if (this.sid !== S.sid) this.teardown();
      if (this.started) return this.started;
      this.sid = S.sid;
      const pr = this.probe();
      if (!pr.ok) { this.started = Promise.reject(new Error(pr.reason)); this.started.catch(() => {}); this.fail(pr.reason); return this.started; }
      this.info = { renderer: pr.renderer, vendor: pr.vendor, version: pr.version };
      this.host = el("div", { class: "webgl-host parked", "aria-hidden": "true" });
      this.frame = el("iframe", { class: "preview-frame", src: S.view.preview.webglUrl, title: "물체 미리보기", tabindex: "-1" });
      this.host.append(this.frame);
      document.body.append(this.host);
      const t0 = performance.now();
      const ready = new Promise((resolve, reject) => {
        const poll = () => {
          if (this.failed) { reject(new Error(this.failed)); return; }
          const w = this.frame && this.frame.contentWindow;
          if (w && w.ifsPreview) w.ifsPreview.ready.then(() => resolve(w.ifsPreview), reject);
          else setTimeout(poll, 100);
        };
        poll();
      });
      this.started = (async () => {
        const p = await this.timeout(ready, S.view.preview.webglReadyTimeoutMs || 30000, "Unity 준비");
        this.p = p;
        this.info.readyMs = Math.round(performance.now() - t0);
        this.info.graphicsDevice = (p.unityInfo && p.unityInfo.graphicsDevice) || null;
        const sc = await api("GET", `/api/sessions/${S.sid}/scene`);
        await this.enqueue("spec 로드", async () => {
          const r = await p.load(sc.spec);
          if (!r || r.kind !== "load") throw new Error("spec 로드 응답이 아님");
          this.applied = canon({});
        });
        const w0 = performance.now();
        await this.enqueue("멈춤", () => this.setFrozen(true));
        for (const ov of (S.cfg.previewWarmup || [])) {   // 셰이더 미리 컴파일(화면 밖, 기록 안 함)
          await this.enqueue("준비 그리기", async () => { await this.apply(ov); await this.capture("warmup", 64, 48); });
        }
        this.info.warmupMs = Math.round(performance.now() - w0);
        return p;
      })();
      this.started.catch((e) => this.fail(`준비: ${e && e.message ? e.message : e}`));
      return this.started;
    },

    async apply(ov) {
      const want = canon(ov);
      if (this.applied === want) return;
      this.applied = null;                       // 응답을 확인하기 전까지는 무엇이 얹혔는지 모름
      const r = await this.p.applyOverrides(ov || {});
      if (!r || r.kind !== "overrides") throw new Error("덮어쓰기 응답이 아님");
      const got = canon(r.overrides || {});
      if (got !== want) throw new Error(`덮어쓰기 응답이 요청과 다름(요청 ${want}, 응답 ${got})`);
      this.applied = want;
    },

    async setFrozen(on) {
      if (this.frozen === on) return;
      await this.p.setFrozen(on);
      this.frozen = on;
    },

    async capture(target, w = 320, h = 240) {
      const id = `q${++this.seq}-${target}`;
      const r = await this.p.capture({ id, width: w, height: h, background: "scene" });
      if (!r || r.id !== id || !r.png) throw new Error(`캡처 응답 id가 다름(요청 ${id}, 응답 ${r && r.id})`);
      return "data:image/png;base64," + r.png;
    },

    // 후보 칸: 정지 그림. 같은 후보·덮어쓰기는 다시 찍지 않는다(화면을 다시 그려도 Unity를 부르지 않음).
    candidateNode(target, overrides) {
      const img = el("img", { class: "preview-img", alt: "", "data-target": target, "data-mode": "webgl", "data-overrides": canon(overrides) });
      // 그림이 오기 전에도 같은 크기의 자리를 차지한다(4:3, 화면이 밀리지 않음)
      const holder = el("div", { class: "preview is-loading", "aria-busy": "true" }, img);
      const loaded = () => { holder.classList.remove("is-loading"); holder.removeAttribute("aria-busy"); };
      const key = `${S.sid}|${target}|${canon(overrides)}`;
      const stage = S.view.stage;
      const shown = () => {
        if ([...document.querySelectorAll('.cand img[data-mode="webgl"]')].every((x) => x.src))
          reportShown("webgl", stage, this.info);
      };
      if (this.caps.has(key)) { img.src = this.caps.get(key); loaded(); setTimeout(shown, 0); return holder; }
      this.start().then(() => this.enqueue(`후보 캡처 ${target}`, async () => {
        await this.setFrozen(true);
        await this.apply(overrides);
        const url = await this.capture(target);
        this.caps.set(key, url);
        img.src = url;
        loaded();
        img.dataset.captureSeq = String(this.seq);
        shown();
      })).catch(() => {});                        // 실패 처리는 enqueue·start의 fail이 한다(서버에 알리고 다시 그림)
      return holder;
    },

    // 조절 화면: 자리만 만들고, 고정된 iframe을 그 위에 겹쳐 놓는다. 움직임을 재생한다(setFrozen(false)).
    liveSlot(overrides) {
      const slot = el("div", { class: "preview live-slot is-loading", "data-mode": "webgl", "data-overrides": canon(overrides), "aria-busy": "true" });
      const stage = S.view.stage;
      // start()를 먼저 부른다: 이 세션의 첫 시작이면 start()가 teardown()으로 slot을 비우므로 slot은 그 뒤에 정한다.
      // (G44에서 고침. 전에는 조절 화면이 첫 화면일 때 — 후보 단계를 건너뛴 세션(G34)이나 ?sid=로 다시 연 경우 — iframe이
      //  화면 밖에 남아 첫 조절을 누르기 전까지 미리보기 자리가 회색 칸이었다.)
      const started = this.start();
      this.slot = slot;
      started.then(() => this.enqueue("조절 화면 덮어쓰기", async () => {
        await this.setFrozen(false);
        await this.apply(overrides);
        slot.dataset.applied = canon(overrides);
        slot.classList.remove("is-loading");
        slot.removeAttribute("aria-busy");
        reportShown("webgl", stage, this.info);
      })).catch(() => {});
      return slot;
    },

    place() {
      if (!this.host) return;
      const slot = this.slot && this.slot.isConnected ? this.slot : null;
      if (!slot || this.failed) { this.host.className = "webgl-host parked"; this.host.style.cssText = ""; return; }
      const r = slot.getBoundingClientRect();
      this.host.className = "webgl-host live";
      // 창 기준 고정(position: fixed). 미리보기 칸이 스크롤을 따라 붙어 있는(sticky) 동안에는 자리가 그대로이고,
      // 칸이 움직일 때만 scroll 이벤트에서 다시 맞춘다(iframe은 옮기지 않음 — 옮기면 Unity가 다시 시작됨).
      this.host.style.cssText = `left:${r.left}px;top:${r.top}px;width:${r.width}px;height:${r.height}px`;
      if (!this.ro) {
        this.ro = new ResizeObserver(() => this.place());
        window.addEventListener("resize", () => this.place());
        window.addEventListener("scroll", () => this.place(), { passive: true });
      }
      this.ro.disconnect();
      this.ro.observe(slot);
      this.ro.observe(document.body);
    },

    // 조절 화면 견본(G44): 지금 상태에서 한 항목만 바꾼 정지 그림을 작게 찍는다. 보이는 미리보기가 다른 형태로 깜빡이지 않게
    // 한 작업 안에서 멈춤 → 값마다 덮어쓰기·캡처 → 지금 상태로 되돌림 → 다시 움직임을 쉬지 않고 이어 한다. Unity 호출(SendMessage)과
    // 응답(dispatchEvent)이 모두 동기라 그 사이에 브라우저가 화면을 그리지 않는다(검증: dbg.thumbJobs[].framesBetween = 0).
    // 찍은 견본은 덮어쓰기별로 기억해 같은 상태에서는 다시 찍지 않는다(형태만 바꾸면 견본 덮어쓰기가 같아 다시 찍지 않음).
    thumbs(samples, w, h) {
      const want = samples.filter((s) => !this.thumbCache.has(canon(s.overrides)));
      if (!want.length) return Promise.resolve();
      const curNow = () => (S.view && S.view.current && S.view.current.overrides) || {};
      const forState = canon(curNow());
      return this.start().then(() => this.enqueue("견본 그리기", async () => {
        // 그사이 다른 값을 눌러 상태가 바뀌었으면 이 견본은 건너뜀(다음 그리기가 새 상태로 다시 부름 — 조절 응답을 늦추지 않게)
        if (canon(curNow()) !== forState) return;
        const cur = curNow();
        const wasFrozen = this.frozen;
        const win = this.frame && this.frame.contentWindow;
        let frames = 0, rafId = 0;
        const tick = () => { frames++; rafId = win.requestAnimationFrame(tick); };
        if (win) rafId = win.requestAnimationFrame(tick);
        const t0 = performance.now();
        await this.setFrozen(true);
        for (const s of want) {
          await this.apply(s.overrides);
          this.thumbCache.set(canon(s.overrides), await this.capture("thumb", w, h));
        }
        await this.apply(cur);
        if (wasFrozen === false) await this.setFrozen(false);
        if (win) win.cancelAnimationFrame(rafId);
        this.dbg.thumbJobs.push({ n: want.length, ms: Math.round(performance.now() - t0), framesBetween: frames });
      }));
    },

    // 움직임 버튼에 머무는 동안 본 미리보기에서 그 값을 재생(overrides), 떠나면 지금 상태로(null). 기록하지 않는다.
    preview(overrides) {
      if (!this.p || this.failed || !this.slot || !this.slot.isConnected) return;
      const target = overrides || (S.view && S.view.current && S.view.current.overrides) || {};
      this.enqueue("미리 보기", async () => { await this.setFrozen(false); await this.apply(target); }).catch(() => {});
    },

    fail(reason) {
      if (this.failed) return;
      this.failed = reason;
      this.closeFrame();
      reportFallback("webgl", reason);
    },

    closeFrame() {
      if (this.ro) this.ro.disconnect();
      if (this.frame) { try { this.frame.src = "about:blank"; } catch (e) { /* 무시 */ } }
      if (this.host) this.host.remove();
      this.host = this.frame = this.p = null;
    },

    teardown() {
      this.closeFrame();
      this.sid = null; this.started = null; this.failed = null; this.q = Promise.resolve();
      this.applied = null; this.frozen = null; this.caps.clear(); this.thumbCache.clear(); this.info = null; this.slot = null;
    },
  };

  // ── 서버 호출 ─────────────────────────────────────────────────────────────
  // srcBtn: 누른 단추. 기다리는 동안 대기 표시(.is-pending, 0.2초 뒤에만 보임)와 aria-disabled를 붙이고, 다시 그린 뒤에는
  // 같은 자리(data-fkey)로 초점을 돌려준다(키보드로 +를 여러 번 누를 때 매번 처음부터 Tab하지 않게).
  async function call(method, path, body, srcBtn) {
    if (S.busy) return;
    S.busy = true;
    const box = $("#stage");
    box.setAttribute("aria-busy", "true");
    if (srcBtn) {
      srcBtn.classList.add("is-pending");
      srcBtn.setAttribute("aria-disabled", "true");
      if (srcBtn.dataset.fkey) S.focusKey = srcBtn.dataset.fkey;
    }
    try {
      S.view = await api(method, path, body);
      draw();
    } catch (e) {
      toast(e.message);
      if (srcBtn) { srcBtn.classList.remove("is-pending"); srcBtn.removeAttribute("aria-disabled"); }
      box.classList.remove("choosing");
      await refresh(false);
    } finally {
      S.busy = false;
      box.removeAttribute("aria-busy");
    }
  }

  async function refresh(redraw = true) {
    try {
      S.view = await api("GET", `/api/sessions/${S.sid}/selection`);
      if (redraw) draw();
    } catch (e) { /* 단계가 꺼져 있음 */ }
  }

  // 조절 견본용 덮어쓰기(서버 GET …/adjust/samples/{item}, 기록하지 않음). 지금 상태별로 기억한다.
  async function samplesFor(item) {
    const key = `${S.sid}|${item}|${canon(S.view && S.view.current && S.view.current.overrides)}`;
    if (!S.samples.has(key)) {
      const r = await api("GET", `/api/sessions/${S.sid}/adjust/samples/${item}`);
      S.samples.set(key, r.samples);
    }
    return S.samples.get(key);
  }

  // image 모드 견본: 서버가 예비 플레이어로 그린 PNG(GET …/preview/sample/{item}/{k}.png). 덮어쓰기별로 기억한다.
  const ImageThumbs = {
    cache: new Map(),
    async get(item, k, overrides) {
      const key = `${S.sid}|${canon(overrides)}`;
      if (!this.cache.has(key)) {
        const res = await fetch(`/api/sessions/${S.sid}/preview/sample/${item}/${k}.png`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.cache.set(key, URL.createObjectURL(await res.blob()));
      }
      return this.cache.get(key);
    },
  };

  // ── 그리기 ────────────────────────────────────────────────────────────────
  function banners() {
    const out = [];
    const v = S.view;
    if (v.draftCount) {
      // X35: 초안 문구 안내 띠(두 보기 모두). 글은 그대로, 모양만 차분한 띠로
      out.push(el("p", { class: "notice draft-banner" },
        `초안 문구 사용 중 — 이 화면의 문구 ${v.draftCount}개가 status draft(IRB·연구팀 검토 전)입니다.`));
    }
    const p = v.preview || {};
    if (p.requested && p.requested !== "none" && p.mode !== p.requested) {
      // 대체 사유는 기술 정보라 연구자 보기에서만(연구자 패널 "미리보기 대체 이유"에도 있음)
      out.push(el("p", { class: "warning preview-fallback researcher-only" },
        `미리보기를 ${p.mode === "image" ? "정지 그림" : "글 요약"}으로 보여 줍니다(${p.reason || "원인 미상"}).`));
    }
    return out;
  }

  // 단계가 바뀌면 그 화면의 첫 안내 글로 초점을 옮긴다(키보드·낭독기 사용자가 새 화면의 처음부터 읽게).
  function intro(text) { return el("p", { class: "msg bot stage-top", tabindex: "-1" }, text); }

  function focusTop(box) {
    const t = box.querySelector(".stage-top");
    if (t) { t.focus({ preventScroll: true }); window.scrollTo(0, 0); }
  }

  function restoreFocus(box, fkey) {
    const sel = (k) => box.querySelector(`[data-fkey="${CSS.escape(k)}"]`);
    let n = sel(fkey);
    if (n && n.disabled && fkey.startsWith("step:")) n = sel(fkey.endsWith(":+") ? fkey.replace(/:\+$/, ":-") : fkey.replace(/:-$/, ":+"));
    if (n && !n.disabled) n.focus({ preventScroll: true });
  }

  function draw() {
    const box = $("#stage");
    const v = S.view;
    if (!v || !v.stage) { box.hidden = true; return; }
    box.hidden = false;
    for (const id of ["#chat", "#composer", "#buttons", "#confirm-box"]) $(id).hidden = true;
    const ae = document.activeElement;
    const fkey = S.focusKey || (ae && box.contains(ae) && ae.dataset ? ae.dataset.fkey : null) || null;
    S.focusKey = null;
    const stageChanged = S.drawnStage !== v.stage;
    S.drawnStage = v.stage;
    box.dataset.stage = v.stage;
    box.dataset.previewMode = (v.preview && v.preview.mode) || "none";
    box.classList.remove("choosing");
    const parts = [...banners()];
    WebGL.slot = null;
    if (v.preview && v.preview.mode !== "webgl" && WebGL.host) WebGL.closeFrame();   // 내려간 뒤에는 iframe을 닫는다
    if (v.stage === "selecting") parts.push(...drawSelecting(v));
    else if (v.stage === "adjusting") parts.push(...drawAdjusting(v));
    else if (v.stage === "premeasure") { WebGL.teardown(); drawPremeasure(box, parts); progress(); return; }
    else if (v.stage === "done") { WebGL.teardown(); parts.push(el("p", { class: "msg bot closing stage-top done-card", tabindex: "-1" }, v.donePhrase || "")); }
    box.replaceChildren(...parts);
    WebGL.place();
    if (stageChanged) focusTop(box);
    else if (fkey) restoreFocus(box, fkey);
    progress();
    if (typeof refreshResearcher === "function") refreshResearcher();   // 연구자 화면에 단계 요약을 다시 그림
  }

  function progress() { if (typeof updateProgress === "function") updateProgress(); }

  // 후보를 고르면: 고른 칸을 표시하고 나머지는 흐리게, 단추는 대기(중복 제출 방지는 S.busy)
  function choose(id, btn) {
    if (S.busy) return;
    const card = btn.closest(".cand");
    if (card) card.classList.add("chosen");
    btn.setAttribute("aria-pressed", "true");
    $("#stage").classList.add("choosing");
    call("POST", `/api/sessions/${S.sid}/selection`, { candidateId: id }, btn);
  }

  function drawSelecting(v) {
    const parts = [intro(phrase("figure_intro")), el("p", { class: "msg bot" }, phrase("candidates_intro"))];
    const grid = el("ul", { class: `cand-grid n${v.candidates.length}` });
    v.candidates.forEach((c, i) => {
      grid.append(el("li", { class: "cand", "data-id": c.id },
        Preview.node(c.id, c.summary, c.overrides),
        el("button", { type: "button", class: "pick", "aria-label": `${phrase("choose_button")} ${i + 1}`, "data-fkey": `cand:${c.id}`,
                       onclick: (e) => choose(c.id, e.currentTarget) }, phrase("choose_button"))));
    });
    parts.push(grid);
    // [맞는 것이 없다]: 후보 단추와 같은 무게(같은 모양·크기), 후보 칸과 떨어진 자리(구분선 아래)
    parts.push(el("div", { class: "none-fit-row" },
      el("button", { type: "button", class: "pick none-fit", "data-fkey": "none", onclick: (e) => choose("none", e.currentTarget) },
        phrase("none_fit"))));
    return parts;
  }

  // 범주 항목(형태·움직임). 화면에 값 이름을 쓰지 않는다. 형태는 견본 그림, 견본이 없으면(글 요약) 번호.
  function categoryOpts(it, v, now, off, lid, send) {
    const extra = (v.adjustExtras || {})[it.id];   // 참여자가 말한 값이 표의 목록에 없으면 목록 끝에 붙여 현재 값으로 보이게 함
    const vals = extra !== undefined && !it.values.includes(extra) ? it.values.concat([extra]) : it.values;
    const mode = Preview.mode();
    const thumbs = it.id === "form" && (mode === "webgl" || mode === "image") && !off;
    const dwell = it.id === "motion" && mode === "webgl" && MOTION_PREVIEW_ON_DWELL && !off && !reducedMotion();
    const opts = el("div", { class: `opts${thumbs ? " thumbs" : ""}`, role: "toolbar", "aria-labelledby": lid });
    const imgs = [];
    const last = S.lastThumb[it.id] || [];
    vals.forEach((val, k) => {
      const active = now === val;
      const b = el("button", { type: "button", class: `opt${active ? " active" : ""}`, "aria-pressed": active ? "true" : "false",
                               "aria-label": `${it.label} ${k + 1}`, "data-fkey": `cat:${it.id}:${k}`, onclick: (e) => send(it.id, val, e.currentTarget) },
                   el("span", { class: "opt-num", "aria-hidden": "true" }, String(k + 1)));
      if (thumbs) {
        // 그림이 올 때까지는 직전 견본(같은 자리)을 보여 주고, 처음이면 빈 회색 칸(번호는 견본이 끝내 없을 때만 보임)
        const img = el("img", { class: "thumb", alt: "", "aria-hidden": "true" });
        b.classList.add("thumb-wait");
        if (last[k]) { img.src = last[k]; b.classList.replace("thumb-wait", "has-thumb"); }
        b.prepend(el("span", { class: "thumb-box", "aria-hidden": "true" }, img));   // 가운데를 키워 보여 줌(모든 값에 같은 배율)
        imgs.push(img);
      }
      if (dwell) attachDwell(b, it.id, k);
      opts.append(b);
    });
    if (thumbs) fillThumbs(it.id, opts, imgs);
    return opts;
  }

  async function fillThumbs(item, opts, imgs) {
    const giveUp = () => imgs.forEach((img) => { const b = img.closest("button"); if (b && !b.classList.contains("has-thumb")) b.classList.replace("thumb-wait", "thumb-failed"); });
    const set = (k, url) => {
      if (!url) return;
      (S.lastThumb[item] = S.lastThumb[item] || [])[k] = url;
      const img = imgs[k];
      if (!img || !img.isConnected) return;
      if (img.src !== url) img.src = url;
      const b = img.closest("button");
      b.classList.remove("thumb-wait", "thumb-failed");
      b.classList.add("has-thumb");
    };
    let samples;
    try { samples = await samplesFor(item); } catch (e) { giveUp(); return; }
    const mode = Preview.mode();
    try {
      if (mode === "webgl") {
        await WebGL.thumbs(samples, THUMB_W, THUMB_H);
        samples.forEach((s, k) => set(k, WebGL.thumbCache.get(canon(s.overrides))));
      } else if (mode === "image") {
        for (let k = 0; k < samples.length; k++) set(k, await ImageThumbs.get(item, k, samples[k].overrides));
      }
    } catch (e) {
      console.warn("[견본] 그리지 못함 → 번호로 표시", e);
    }
    giveUp();
  }

  // 움직임: 머물면 본 미리보기에서 재생, 떠나면 되돌림(WebGL). 누르면 그 값으로 고침(기록됨).
  function attachDwell(b, item, k) {
    let t = 0;
    const slot = () => document.querySelector(".live-slot");
    const startP = () => {
      clearTimeout(t);
      t = setTimeout(async () => {
        let samples;
        try { samples = await samplesFor(item); } catch (e) { return; }
        if (!b.isConnected || S.busy) return;
        b.classList.add("is-previewing");
        if (slot()) slot().classList.add("is-previewing");
        WebGL.preview(samples[k].overrides);
      }, DWELL_MS);
    };
    const stopP = () => {
      clearTimeout(t);
      if (!b.classList.contains("is-previewing")) return;
      b.classList.remove("is-previewing");
      if (slot()) slot().classList.remove("is-previewing");
      if (!S.busy) WebGL.preview(null);
    };
    b.addEventListener("mouseenter", startP);
    b.addEventListener("focus", startP);
    b.addEventListener("mouseleave", stopP);
    b.addEventListener("blur", stopP);
    b.addEventListener("click", () => { clearTimeout(t); b.classList.remove("is-previewing"); });
  }

  // 견본 묶음(색·형태·움직임)은 Tab 한 번에 들어가고 방향키(←→↑↓, Home·End)로 옮긴다(도구 막대 방식, 초점만 옮기고
  // 고르지 않음 — 고르는 것은 Enter·Space). 색 17개를 Tab으로 하나씩 지나지 않게. 들어갈 때의 자리는 지금 고른 것.
  function roving(group) {
    const items = () => [...group.querySelectorAll("button")].filter((b) => !b.disabled);
    const list0 = items();
    const cur = list0.find((b) => b.getAttribute("aria-pressed") === "true") || list0[0];
    group.querySelectorAll("button").forEach((b) => b.setAttribute("tabindex", b === cur ? "0" : "-1"));
    group.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (step === undefined && e.key !== "Home" && e.key !== "End") return;
      const list = items();
      const i = list.indexOf(document.activeElement);
      if (i < 0) return;
      e.preventDefault();
      const j = e.key === "Home" ? 0 : e.key === "End" ? list.length - 1 : (i + step + list.length) % list.length;
      list.forEach((b) => b.setAttribute("tabindex", b === list[j] ? "0" : "-1"));
      list[j].focus();
    });
    return group;
  }

  function drawAdjusting(v) {
    const cur = (v.current && v.current.items) || {};
    const off = v.unavailableItems || {};
    const panel = el("div", { class: "adjust-panel" });
    const send = (item, value, btn) => call("POST", `/api/sessions/${S.sid}/adjust`, { item, value }, btn);
    for (const it of S.cfg.adjustItems) {
      const lid = `adj-label-${it.id}`;
      const row = el("div", { class: `adjust-row${off[it.id] ? " off" : ""}`, "data-item": it.id },
        el("span", { class: "adjust-label", id: lid }, it.label));
      const now = cur[it.id];
      const btns = [];
      if (it.kind === "swatch") {
        // 색 견본: 이름 없이 색만. 고른 것은 색만이 아니라 두꺼운 테두리 + 체크 표시로. 낭독기 이름은 "색 n"(색 이름을 만들지 않음)
        const chips = el("div", { class: "chips", role: "toolbar", "aria-labelledby": lid });
        it.values.forEach((sw, k) => {
          const active = !!(now && now.swatch === sw.id);
          const b = el("button", { type: "button", class: `chip${active ? " active" : ""}`, style: `--swatch:${sw.hex}`,
                                   "aria-pressed": active ? "true" : "false", "aria-label": `${it.label} ${k + 1}`,
                                   "data-swatch": sw.id, "data-fkey": `sw:${sw.id}`, onclick: (e) => send(it.id, sw.id, e.currentTarget) });
          chips.append(b); btns.push(b);
        });
        row.append(roving(chips));
      } else if (it.kind === "category") {
        const opts = categoryOpts(it, v, now, !!off[it.id], lid, send);
        btns.push(...opts.querySelectorAll("button"));
        row.append(off[it.id] ? opts : roving(opts));
      } else {
        // 단계: "n / N" 글 대신 칸 눈금 막대(지금 자리까지 채움, 지금 칸은 진하게) + −/+. 끝에서는 그쪽 단추를 끔.
        const vals = it.values;
        const idx = vals.findIndex((x) => Math.abs(x - now) < 1e-9);
        const below = vals.filter((x) => x < now - 1e-9).length;   // 말한 값이 단계 사이일 때: 그보다 작은 단계 수
        const lower = [...vals].reverse().find((x) => x < now - 1e-9);
        const upper = vals.find((x) => x > now + 1e-9);
        const minus = el("button", { type: "button", class: "step-btn", "aria-label": `${it.label} −`, "data-fkey": `step:${it.id}:-`,
                                     onclick: (e) => send(it.id, lower, e.currentTarget) }, "−");
        const plus = el("button", { type: "button", class: "step-btn", "aria-label": `${it.label} +`, "data-fkey": `step:${it.id}:+`,
                                    onclick: (e) => send(it.id, upper, e.currentTarget) }, "+");
        minus.disabled = lower === undefined;
        plus.disabled = upper === undefined;
        btns.push(minus, plus);
        const pos = idx >= 0 ? idx + 1 : below + 0.5;
        const meter = el("div", { class: "meter", role: "meter", "aria-labelledby": lid, "aria-valuemin": "1", "aria-valuemax": String(vals.length),
                                  "aria-valuenow": String(pos), "aria-valuetext": idx >= 0 ? `${idx + 1} / ${vals.length}` : `– / ${vals.length}` },
          ...vals.map((_, k) => el("i", { class: idx >= 0 ? (k === idx ? "cur" : k < idx ? "on" : "") : (k < below ? "on" : "") })));
        row.append(el("div", { class: "stepper" }, minus, meter, plus));
      }
      if (off[it.id]) {
        // G22: 이 미리보기 방식에서는 바꿔도 화면에 보이지 않는 항목(image = 정지 그림에서 움직임) → 끄고 이유 문구를 붙임
        for (const b of btns) b.disabled = true;
        row.append(el("small", { class: "adjust-off-note" }, phrase("adjust_item_unavailable")));
      }
      panel.append(row);
    }
    return [intro(phrase("figure_intro")), el("p", { class: "msg bot" }, phrase("adjust_intro")),
            el("div", { class: "adjust" },
              el("div", { class: "adjust-preview" }, Preview.node("current", v.current && v.current.summary, v.current && v.current.overrides)),
              panel),
            el("div", { class: "buttons stage-actions" },
              el("button", { type: "button", class: "primary", "data-fkey": "finish",
                             onclick: (e) => call("POST", `/api/sessions/${S.sid}/adjust/finish`, undefined, e.currentTarget) },
                phrase("adjust_finish_button")))];
  }

  // 사전 측정: 문항을 모두 한 화면에(하나씩 넘기지 않음, G44). 척도 점마다 칸 전체가 눌리는 큰 자리(높이 44px 이상),
  // [답하지 않기]는 같은 줄에서 떨어뜨려 둔다. 고르지 않은 문항이 있으면 기존 문구를 제출 단추 위에 띄우고 그 문항을 표시·초점.
  async function drawPremeasure(box, parts) {
    let pm;
    try { pm = await api("GET", `/api/sessions/${S.sid}/premeasure`); } catch (e) { toast(e.message); return; }
    const sc = pm.scale;
    const n = sc.max - sc.min + 1;
    const form = el("form", { class: "premeasure", novalidate: "" });
    form.append(el("p", { class: "msg bot stage-top pm-instruction", tabindex: "-1" }, pm.instruction));
    for (const it of pm.items) {
      const fs = el("fieldset", { class: "pm-item", "data-item": it.id });
      const pts = el("div", { class: "scale-points", style: `--n:${n}` });
      const pick = () => fs.classList.remove("missing");
      for (let k = sc.min; k <= sc.max; k++) {
        const id = `pm-${it.id}-${k}`;
        const input = el("input", { type: "radio", name: it.id, id, value: String(k) });
        if (S.answers[it.id] === k) input.checked = true;
        input.addEventListener("change", () => { S.answers[it.id] = k; pick(); });
        pts.append(el("label", { for: id, class: "pt" }, input, el("span", { class: "pt-num" }, `${k}`),
          el("span", { class: "pt-anchor" }, sc.anchors[String(k)] || "")));
      }
      const skip = el("input", { type: "radio", name: it.id, id: `pm-${it.id}-skip`, value: "" });
      if (S.answers[it.id] === null) skip.checked = true;
      skip.addEventListener("change", () => { S.answers[it.id] = null; pick(); });
      fs.append(el("legend", {}, it.text),
        el("div", { class: "scale" }, pts, el("span", { class: "scale-gap", "aria-hidden": "true" }),
          el("label", { for: `pm-${it.id}-skip`, class: "pt skip" }, skip, el("span", { class: "pt-anchor" }, pm.skipLabel))));
      form.append(fs);
    }
    const err = el("p", { class: "form-error", role: "alert", hidden: "" });
    const submit = el("button", { class: "primary", type: "submit", "data-fkey": "pm-submit" }, phrase("premeasure_submit_button"));
    form.append(err, el("div", { class: "buttons stage-actions" }, submit));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const missing = pm.items.filter((i) => !(i.id in S.answers));
      form.querySelectorAll(".pm-item").forEach((f) => f.classList.toggle("missing", missing.some((m) => m.id === f.dataset.item)));
      if (missing.length) {
        err.textContent = `아직 고르지 않은 문장이 ${missing.length}개 있어요.`;
        err.hidden = false;
        const first = form.querySelector(`.pm-item[data-item="${CSS.escape(missing[0].id)}"] input`);
        if (first) first.focus();
        return;
      }
      err.hidden = true;
      call("POST", `/api/sessions/${S.sid}/premeasure`, { responses: S.answers }, submit);
    });
    box.replaceChildren(...parts, form);
    focusTop(box);
  }

  // ── app.js에서 부르는 곳 ───────────────────────────────────────────────────
  async function afterRender(v) {
    if (!v.selection) return;                       // 기본 설정: 새 단계 없음
    S.sid = v.sessionId;
    await ensureConfig();
    if (v.selection.stage) {                        // 이미 진행 중(?sid= 로 다시 연 경우)
      if (!S.view) await refresh(true);
      return;
    }
    if (v.selection.available) {
      $("#buttons").prepend(el("button", { class: "primary", "data-fkey": "next",
                                         onclick: (e) => call("POST", `/api/sessions/${S.sid}/candidates`, undefined, e.currentTarget) },
        "다음으로"));
    }
  }

  function researcherNote(tab) {
    if (!S.view || !S.view.stage) return;
    const v = S.view;
    const w = WebGL.info;
    tab.append(el("h3", {}, "후보·조절 단계(연구자용)"),
      kv([["단계", v.stage], ["후보 규칙", v.note], ["축", (v.axes || []).map((a) => `${a.slot}(${a.reason})`).join(", ")],
          ["미리보기", `${v.preview.mode}${v.preview.requested !== v.preview.mode ? ` (요청 ${v.preview.requested})` : ""}`],
          ["미리보기 대체 이유", v.preview.mode !== v.preview.requested ? v.preview.reason : null],
          ["WebGL 렌더러", v.preview.mode === "webgl" && w ? `${w.renderer || "?"} · ${w.graphicsDevice || "?"}` : null],
          ["꺼 둔 조절 항목", Object.keys(v.unavailableItems || {}).length ? JSON.stringify(v.unavailableItems) : null],
          ["선택", v.selection ? (v.selection.skipped ? "구별되는 후보가 하나뿐 → 선택 단계 건너뜀(G34)"
                                 : v.selection.none ? "맞는 것이 없다 → 0번으로 진행"
                                 : `${v.selection.selectedCandidateId} (화면 ${v.selection.displayPosition + 1}번째)`) : null],
          ["조절 횟수", v.adjustCounts ? JSON.stringify(v.adjustCounts) : null],
          ["색 바꿈", v.colorChanged === undefined ? null : (v.colorChanged ? "예" : "아니오")],
          ["finalOverrides", v.finalOverrides ? JSON.stringify(v.finalOverrides) : null],
          ["출처 분포", v.sourceCounts ? JSON.stringify(v.sourceCounts) : null]]));
  }

  // 진행 표시(app.js updateProgress)가 읽는 지금 단계
  function current() { return { stage: S.view ? S.view.stage : null, skipped: !!(S.view && S.view.skipped) }; }

  window.ifsStage = { afterRender, researcherNote, current, _state: S, _webgl: WebGL };
})();
