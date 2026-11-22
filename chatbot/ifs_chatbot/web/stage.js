// 면담 뒤 데스크톱 단계 — 4 후보 선택 · 5 조절 · 6 사전 측정 (D5, 결정 G10·G13·G19·G22·G23).
// 외부 라이브러리·CDN·글꼴 없음(원칙 5). 문구는 서버가 shared/protocol/selection_protocol.v0.json에서 준 것만 쓴다(모두 초안).
// 미리보기 어댑터: preview.mode = image(서버가 Unity 미리보기 플레이어로 그린 PNG) | webgl(같은 출처 Unity WebGL 빌드, 인터페이스만) | none(속성 요약 글).
"use strict";

(function () {
  const S = { cfg: null, view: null, sid: null, imgSeq: 0, busy: false, answers: {} };

  async function ensureConfig() {
    if (S.cfg) return S.cfg;
    S.cfg = await api("GET", "/api/selection/config");
    return S.cfg;
  }

  function phrase(id) { return (S.cfg && S.cfg.phrases[id]) || ""; }

  // ── 미리보기 어댑터 ────────────────────────────────────────────────────────
  const Preview = {
    mode() { return (S.view && S.view.preview && S.view.preview.mode) || "none"; },

    // target = 후보 id 또는 "current". summary = 서버가 준 속성 요약(none 모드).
    node(target, summary) {
      const m = this.mode();
      if (m === "image") {
        const img = el("img", { class: "preview-img", alt: "", src: `/api/sessions/${S.sid}/preview/${target}.png?v=${++S.imgSeq}` });
        img.addEventListener("error", () => refresh(true));   // 플레이어가 죽으면 서버가 none으로 바꿈 → 다시 그림
        return el("div", { class: "preview" }, img);
      }
      if (m === "webgl") return WebGL.node(target);
      return el("div", { class: "preview text" }, el("ul", {}, ...(summary || []).map((s) => el("li", {}, s))));
    },
  };

  // WebGL: Unity WebGL 빌드(window.ifsPreview: load·applyOverrides·capture)를 같은 출처 iframe 하나로 띄운다.
  // 후보는 한 인스턴스에서 차례로 덮어쓰기를 얹어 capture한 그림을 칸에 넣고, 조절 화면은 iframe을 그대로 보여 준다.
  // ⚠ 2026-11-23 WebGL 빌드가 없어(G25) 실행해 보지 못한 인터페이스 코드다.
  const WebGL = {
    frame: null,
    loaded: null,
    api() {
      if (!this.frame) {
        this.frame = el("iframe", { class: "preview-frame", src: S.view.preview.webglUrl, title: "형상 미리보기" });
      }
      const ready = new Promise((resolve) => {
        const poll = () => {
          const w = this.frame.contentWindow;
          if (w && w.ifsPreview) w.ifsPreview.ready.then(() => resolve(w.ifsPreview)); else setTimeout(poll, 200);
        };
        poll();
      });
      // 원본 spec은 한 번만 넣는다(GET /scene). 그 뒤로는 덮어쓰기만 바꾼다(PreviewBridge.ApplyOverridesJson).
      if (!this.loaded) {
        this.loaded = ready.then(async (p) => {
          const sc = await api("GET", `/api/sessions/${S.sid}/scene`);
          await p.load(sc.spec);
          return p;
        });
      }
      return this.loaded;
    },
    node(target) {
      const holder = el("div", { class: "preview" });
      if (target === "current") {
        this.api();
        holder.append(this.frame);
        this.loaded.then((p) => p.applyOverrides((S.view.current && S.view.current.overrides) || {})).catch(() => {});
      } else {
        const img = el("img", { class: "preview-img", alt: "" });
        holder.append(img);
        const c = (S.view.candidates || []).find((x) => x.id === target);
        // 한 인스턴스를 같이 쓰므로 후보마다 차례로(덮어쓰기 → 캡처) 처리한다
        this.chain = (this.chain || this.api()).then(async () => {
          const p = await this.loaded;
          await p.applyOverrides(c ? c.overrides : {});
          const r = await p.capture({ id: target, width: 320, height: 240 });
          img.src = "data:image/png;base64," + r.png;
        }).catch(() => {});
      }
      return holder;
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
    if (p.requested && p.requested !== "none" && p.mode === "none") {
      out.push(el("p", { class: "warning" }, `미리보기를 쓸 수 없어 글 요약으로 보여 줍니다(${p.reason || "원인 미상"}).`));
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
    const parts = [...banners()];
    if (v.stage === "selecting") parts.push(...drawSelecting(v));
    else if (v.stage === "adjusting") parts.push(...drawAdjusting(v));
    else if (v.stage === "premeasure") { drawPremeasure(box, parts); return; }
    else if (v.stage === "done") parts.push(el("p", { class: "msg bot closing" }, v.donePhrase || ""));
    box.replaceChildren(...parts);
    if (typeof refreshResearcher === "function") refreshResearcher();   // 연구자 화면에 단계 요약을 다시 그림
  }

  function drawSelecting(v) {
    const parts = [el("p", { class: "msg bot" }, phrase("figure_intro")),
                   el("p", { class: "msg bot" }, v.single ? phrase("single_candidate_intro") : phrase("candidates_intro"))];
    const grid = el("div", { class: `cand-grid n${v.candidates.length}` });
    for (const c of v.candidates) {
      grid.append(el("div", { class: "cand", "data-id": c.id },
        Preview.node(c.id, c.summary),
        el("button", { class: "primary", onclick: () => call("POST", `/api/sessions/${S.sid}/selection`, { candidateId: c.id }) },
          v.single ? phrase("proceed_single_button") : phrase("choose_button"))));
    }
    parts.push(grid);
    parts.push(el("div", { class: "buttons" },
      el("button", { class: "none-fit", onclick: () => call("POST", `/api/sessions/${S.sid}/selection`, { candidateId: "none" }) },
        phrase("none_fit"))));
    return parts;
  }

  function sameColor(a, b) { return a && b && ["h", "s", "l"].every((k) => Math.abs(a[k] - b[k]) < 1e-6); }

  function drawAdjusting(v) {
    const cur = (v.current && v.current.items) || {};
    const panel = el("div", { class: "adjust-panel" });
    const send = (item, value) => call("POST", `/api/sessions/${S.sid}/adjust`, { item, value });
    for (const it of S.cfg.adjustItems) {
      const row = el("div", { class: "adjust-row", "data-item": it.id }, el("span", { class: "adjust-label" }, it.label));
      const now = cur[it.id];
      if (it.kind === "swatch") {
        const chips = el("div", { class: "chips" });
        for (const sw of it.values) {
          const active = now && now.swatch === sw.id;
          chips.append(el("button", { class: `chip${active ? " active" : ""}`, style: `background:${sw.hex}`, "aria-label": `색 견본 ${sw.id}`,
                                      onclick: () => send(it.id, sw.id) }));
        }
        row.append(chips);
      } else if (it.kind === "category") {
        const opts = el("div", { class: "opts" });
        // 참여자가 말한 값이 표의 목록에 없으면 서버가 adjustExtras로 알려 준다 → 목록 끝에 붙여 현재 값으로 보이게 함
        const extra = (v.adjustExtras || {})[it.id];
        const vals = extra !== undefined && !it.values.includes(extra) ? it.values.concat([extra]) : it.values;
        vals.forEach((val, k) => opts.append(el("button", { class: now === val ? "active" : "", onclick: () => send(it.id, val) }, String(k + 1))));
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
        row.append(el("div", { class: "stepper" }, minus,
          el("span", { class: "pos" }, idx >= 0 ? `${idx + 1} / ${vals.length}` : `– / ${vals.length}`), plus));
      }
      panel.append(row);
    }
    return [el("p", { class: "msg bot" }, phrase("figure_intro")), el("p", { class: "msg bot" }, phrase("adjust_intro")),
            el("div", { class: "adjust" }, Preview.node("current", v.current && v.current.summary), panel),
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
    tab.append(el("h3", {}, "후보·조절 단계(연구자용)"),
      kv([["단계", v.stage], ["후보 규칙", v.note], ["축", (v.axes || []).map((a) => `${a.slot}(${a.reason})`).join(", ")],
          ["미리보기", `${v.preview.mode}${v.preview.requested !== v.preview.mode ? ` (요청 ${v.preview.requested})` : ""}`],
          ["선택", v.selection ? (v.selection.none ? "맞는 것이 없다 → 0번으로 진행" : `${v.selection.selectedCandidateId} (화면 ${v.selection.displayPosition + 1}번째)`) : null],
          ["조절 횟수", v.adjustCounts ? JSON.stringify(v.adjustCounts) : null],
          ["finalOverrides", v.finalOverrides ? JSON.stringify(v.finalOverrides) : null],
          ["출처 분포", v.sourceCounts ? JSON.stringify(v.sourceCounts) : null]]));
  }

  window.ifsStage = { afterRender, researcherNote, _state: S };
})();
