// 면담 뒤 데스크톱 단계 — 4 후보 선택 · 5 조절 · 6 사전 측정 (D5, 결정 G10·G13·G22·G23, G31·G34).
// G34: 구별되는 후보가 하나뿐이면 서버가 선택 단계를 건너뛰고 바로 adjusting으로 준다(후보 1개 화면은 없음).
// G31: 조절 항목은 서버가 준 순서(값 표 adjustItems.order, 색이 맨 앞) 그대로 그린다.
// 외부 라이브러리·CDN·글꼴 없음(원칙 5). 문구는 서버가 shared/protocol/selection_protocol.v0.json에서 준 것만 쓴다(모두 초안).
// 미리보기 어댑터: preview.mode = webgl(같은 출처 Unity WebGL 빌드, G12) | image(서버가 Unity 미리보기 플레이어로 그린 PNG, G25)
//                 | none(속성 요약 글). mode는 세션마다 서버가 정한다. webgl이 안 되면 이 화면이 서버에 알리고(POST …/preview/client)
//                 서버가 그 세션을 image(예비 플레이어가 없으면 none)로 내린 뷰를 돌려준다. 실제로 쓴 방식도 같은 곳에 알린다.
"use strict";

(function () {
  const S = { cfg: null, view: null, sid: null, imgSeq: 0, busy: false, answers: {}, reported: new Set() };

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
        img.addEventListener("load", () => reportShown("image", stage));
        img.addEventListener("error", () => refresh(true));   // 플레이어가 죽으면 서버가 이 세션을 none으로 내림 → 다시 그림
        return el("div", { class: "preview" }, img);
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
      this.frame = el("iframe", { class: "preview-frame", src: S.view.preview.webglUrl, title: "형상 미리보기", tabindex: "-1" });
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
      const holder = el("div", { class: "preview" }, img);
      const key = `${S.sid}|${target}|${canon(overrides)}`;
      const stage = S.view.stage;
      const shown = () => {
        if ([...document.querySelectorAll('.cand img[data-mode="webgl"]')].every((x) => x.src))
          reportShown("webgl", stage, this.info);
      };
      if (this.caps.has(key)) { img.src = this.caps.get(key); setTimeout(shown, 0); return holder; }
      this.start().then(() => this.enqueue(`후보 캡처 ${target}`, async () => {
        await this.setFrozen(true);
        await this.apply(overrides);
        const url = await this.capture(target);
        this.caps.set(key, url);
        img.src = url;
        img.dataset.captureSeq = String(this.seq);
        shown();
      })).catch(() => {});                        // 실패 처리는 enqueue·start의 fail이 한다(서버에 알리고 다시 그림)
      return holder;
    },

    // 조절 화면: 자리만 만들고, 고정된 iframe을 그 위에 겹쳐 놓는다. 움직임을 재생한다(setFrozen(false)).
    liveSlot(overrides) {
      const slot = el("div", { class: "preview live-slot", "data-mode": "webgl", "data-overrides": canon(overrides) });
      this.slot = slot;
      const stage = S.view.stage;
      this.start().then(() => this.enqueue("조절 화면 덮어쓰기", async () => {
        await this.setFrozen(false);
        await this.apply(overrides);
        slot.dataset.applied = canon(overrides);
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
      this.host.style.cssText = `left:${r.left + window.scrollX}px;top:${r.top + window.scrollY}px;width:${r.width}px;height:${r.height}px`;
      if (!this.ro) {
        this.ro = new ResizeObserver(() => this.place());
        window.addEventListener("resize", () => this.place());
      }
      this.ro.disconnect();
      this.ro.observe(slot);
      this.ro.observe(document.body);
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
      this.applied = null; this.frozen = null; this.caps.clear(); this.info = null; this.slot = null;
    },
  };

  // ── 서버 호출 ─────────────────────────────────────────────────────────────
  async function call(method, path, body) {
    if (S.busy) return;
    S.busy = true;
    try {
      S.view = await api(method, path, body);
      draw();
    } catch (e) {
      toast(e.message);
      await refresh(false);
    } finally {
      S.busy = false;
    }
  }

  async function refresh(redraw = true) {
    try {
      S.view = await api("GET", `/api/sessions/${S.sid}/selection`);
      if (redraw) draw();
    } catch (e) { /* 단계가 꺼져 있음 */ }
  }

  // ── 그리기 ────────────────────────────────────────────────────────────────
  function banners() {
    const out = [];
    const v = S.view;
    if (v.draftCount) {
      out.push(el("p", { class: "warning draft-banner" },
        `초안 문구 사용 중 — 이 화면의 문구 ${v.draftCount}개가 status draft(IRB·연구팀 검토 전)입니다.`));
    }
    const p = v.preview || {};
    if (p.requested && p.requested !== "none" && p.mode !== p.requested) {
      out.push(el("p", { class: "warning preview-fallback" },
        `미리보기를 ${p.mode === "image" ? "정지 그림" : "글 요약"}으로 보여 줍니다(${p.reason || "원인 미상"}).`));
    }
    return out;
  }

  function draw() {
    const box = $("#stage");
    const v = S.view;
    if (!v || !v.stage) { box.hidden = true; return; }
    box.hidden = false;
    for (const id of ["#chat", "#composer", "#buttons", "#confirm-box"]) $(id).hidden = true;
    box.dataset.stage = v.stage;
    box.dataset.previewMode = (v.preview && v.preview.mode) || "none";
    const parts = [...banners()];
    WebGL.slot = null;
    if (v.preview && v.preview.mode !== "webgl" && WebGL.host) WebGL.closeFrame();   // 내려간 뒤에는 iframe을 닫는다
    if (v.stage === "selecting") parts.push(...drawSelecting(v));
    else if (v.stage === "adjusting") parts.push(...drawAdjusting(v));
    else if (v.stage === "premeasure") { WebGL.teardown(); drawPremeasure(box, parts); return; }
    else if (v.stage === "done") { WebGL.teardown(); parts.push(el("p", { class: "msg bot closing" }, v.donePhrase || "")); }
    box.replaceChildren(...parts);
    WebGL.place();
    if (typeof refreshResearcher === "function") refreshResearcher();   // 연구자 화면에 단계 요약을 다시 그림
  }

  function drawSelecting(v) {
    const parts = [el("p", { class: "msg bot" }, phrase("figure_intro")),
                   el("p", { class: "msg bot" }, phrase("candidates_intro"))];
    const grid = el("div", { class: `cand-grid n${v.candidates.length}` });
    for (const c of v.candidates) {
      grid.append(el("div", { class: "cand", "data-id": c.id },
        Preview.node(c.id, c.summary, c.overrides),
        el("button", { class: "primary", onclick: () => call("POST", `/api/sessions/${S.sid}/selection`, { candidateId: c.id }) },
          phrase("choose_button"))));
    }
    parts.push(grid);
    parts.push(el("div", { class: "buttons" },
      el("button", { class: "none-fit", onclick: () => call("POST", `/api/sessions/${S.sid}/selection`, { candidateId: "none" }) },
        phrase("none_fit"))));
    return parts;
  }

  function drawAdjusting(v) {
    const cur = (v.current && v.current.items) || {};
    const off = v.unavailableItems || {};
    const panel = el("div", { class: "adjust-panel" });
    const send = (item, value) => call("POST", `/api/sessions/${S.sid}/adjust`, { item, value });
    for (const it of S.cfg.adjustItems) {
      const row = el("div", { class: `adjust-row${off[it.id] ? " off" : ""}`, "data-item": it.id }, el("span", { class: "adjust-label" }, it.label));
      const now = cur[it.id];
      const btns = [];
      if (it.kind === "swatch") {
        const chips = el("div", { class: "chips" });
        for (const sw of it.values) {
          const active = now && now.swatch === sw.id;
          const b = el("button", { class: `chip${active ? " active" : ""}`, style: `background:${sw.hex}`, "aria-label": `색 견본 ${sw.id}`,
                                   onclick: () => send(it.id, sw.id) });
          chips.append(b); btns.push(b);
        }
        row.append(chips);
      } else if (it.kind === "category") {
        const opts = el("div", { class: "opts" });
        // 참여자가 말한 값이 표의 목록에 없으면 서버가 adjustExtras로 알려 준다 → 목록 끝에 붙여 현재 값으로 보이게 함
        const extra = (v.adjustExtras || {})[it.id];
        const vals = extra !== undefined && !it.values.includes(extra) ? it.values.concat([extra]) : it.values;
        vals.forEach((val, k) => {
          const b = el("button", { class: now === val ? "active" : "", onclick: () => send(it.id, val) }, String(k + 1));
          opts.append(b); btns.push(b);
        });
        row.append(opts);
      } else {
        const vals = it.values;
        const idx = vals.findIndex((x) => Math.abs(x - now) < 1e-9);
        const lower = [...vals].reverse().find((x) => x < now - 1e-9);
        const upper = vals.find((x) => x > now + 1e-9);
        const minus = el("button", { onclick: () => send(it.id, lower) }, "−");
        const plus = el("button", { onclick: () => send(it.id, upper) }, "+");
        minus.disabled = lower === undefined;
        plus.disabled = upper === undefined;
        btns.push(minus, plus);
        row.append(el("div", { class: "stepper" }, minus,
          el("span", { class: "pos" }, idx >= 0 ? `${idx + 1} / ${vals.length}` : `– / ${vals.length}`), plus));
      }
      if (off[it.id]) {
        // G22: 이 미리보기 방식에서는 바꿔도 화면에 보이지 않는 항목(image = 정지 그림에서 움직임) → 끄고 이유 문구를 붙임
        for (const b of btns) b.disabled = true;
        row.append(el("small", { class: "adjust-off-note" }, phrase("adjust_item_unavailable")));
      }
      panel.append(row);
    }
    return [el("p", { class: "msg bot" }, phrase("figure_intro")), el("p", { class: "msg bot" }, phrase("adjust_intro")),
            el("div", { class: "adjust" }, Preview.node("current", v.current && v.current.summary, v.current && v.current.overrides), panel),
            el("div", { class: "buttons" }, el("button", { class: "primary", onclick: () => call("POST", `/api/sessions/${S.sid}/adjust/finish`) },
              phrase("adjust_finish_button")))];
  }

  async function drawPremeasure(box, parts) {
    let pm;
    try { pm = await api("GET", `/api/sessions/${S.sid}/premeasure`); } catch (e) { toast(e.message); return; }
    const sc = pm.scale;
    const form = el("form", { class: "premeasure" });
    form.append(el("p", { class: "msg bot" }, pm.instruction));
    for (const it of pm.items) {
      const opts = el("div", { class: "scale" });
      for (let k = sc.min; k <= sc.max; k++) {
        const id = `pm-${it.id}-${k}`;
        const input = el("input", { type: "radio", name: it.id, id, value: String(k) });
        if (S.answers[it.id] === k) input.checked = true;
        input.addEventListener("change", () => { S.answers[it.id] = k; });
        opts.append(el("label", { for: id, class: "pt" }, input, el("span", {}, `${k}`), el("small", {}, sc.anchors[String(k)] || "")));
      }
      const skip = el("input", { type: "radio", name: it.id, id: `pm-${it.id}-skip`, value: "" });
      if (S.answers[it.id] === null) skip.checked = true;
      skip.addEventListener("change", () => { S.answers[it.id] = null; });
      opts.append(el("label", { for: `pm-${it.id}-skip`, class: "pt skip" }, skip, el("small", {}, pm.skipLabel)));
      form.append(el("fieldset", { class: "pm-item", "data-item": it.id }, el("legend", {}, it.text), opts));
    }
    form.append(el("div", { class: "buttons" }, el("button", { class: "primary", type: "submit" }, phrase("premeasure_submit_button"))));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const missing = pm.items.filter((i) => !(i.id in S.answers));
      if (missing.length) { toast(`아직 고르지 않은 문항이 ${missing.length}개 있습니다.`); return; }
      call("POST", `/api/sessions/${S.sid}/premeasure`, { responses: S.answers });
    });
    box.replaceChildren(...parts, form);
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
      $("#buttons").prepend(el("button", { class: "primary", onclick: () => call("POST", `/api/sessions/${S.sid}/candidates`) },
        "다음 단계로"));
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

  window.ifsStage = { afterRender, researcherNote, _state: S, _webgl: WebGL };
})();
