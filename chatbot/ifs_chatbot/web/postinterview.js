// 사후 면담 기록 화면(G59, 연구자가 여는 화면) — 주소 /?view=postinterview&session=<세션 ID>.
// 모든 평정이 끝나고 헤드셋을 벗은 뒤, 실험자가 문항을 읽고 참여자 말을 받아 적는다(몇 문항은 참여자가 직접 적거나 고름).
// 문항·규칙·조건은 서버가 shared/protocol/post_interview.v0.json에서 준 것만 그린다(모두 초안). LLM을 부르지 않는다.
// 조건(place · view · point_select)을 고르면 그 조건의 문항만 보인다. 평정 묶음(PI6)과 뒤 문항은 자유 응답(PI1–PI5)을
// 저장(또는 건너뜀)한 뒤에만 보인다. 저장: POST /api/sessions/{id}/postinterview → 세션 폴더의 postinterview.json(git 밖).
// 외부 라이브러리·CDN 없음(원칙 5). app.js의 $ · el · api · toast · kv를 쓴다.
"use strict";

(function () {
  const P = { cfg: null, sid: null, view: null, condition: null, busy: false };

  async function open(sid) {
    document.body.dataset.view = "postinterview";
    for (const id of ["#setup", "#chat", "#composer", "#buttons", "#confirm-box", "#stage", "#researcher"]) { const n = $(id); if (n) n.hidden = true; }
    $("#layout").classList.add("solo");
    const box = $("#postinterview");
    box.hidden = false;
    if (!sid) { box.replaceChildren(el("p", { class: "warning" }, "주소에 세션 ID가 없습니다(?view=postinterview&session=<세션 ID>).")); return; }
    P.sid = sid;
    try {
      P.cfg = await api("GET", "/api/postinterview/config");
      P.view = await api("GET", `/api/sessions/${encodeURIComponent(sid)}/postinterview`);
    } catch (e) {
      box.replaceChildren(el("p", { class: "warning" }, `사후 면담 화면을 열지 못했습니다: ${e.message}`));
      return;
    }
    if (P.view.record) P.condition = P.view.record.condition;
    draw();
  }

  const itemsFor = (part) => P.cfg.items.filter((it) => it.part === part && (!it.conditions || it.conditions.includes(P.condition)));
  const KIND_NOTE = { oral: "구두 — 실험자가 읽고 그대로 받아 적음", oral_repeat: "구두 되묻기 — 참여자 낱말만, 최대 2회",
                      choice: "참여자가 고름", typed: "참여자가 직접 적음", rating_group: "참여자가 고름(1–7, 항목마다 건너뛸 수 있음)" };

  function draw() {
    const box = $("#postinterview");
    const rec = P.view.record;
    const parts = [
      el("h2", {}, "사후 면담 기록(연구자용)"),
      kv([["세션 ID", P.sid], ["문항 파일", `${P.cfg.protocol.file} (${P.cfg.protocol.protocolVersion})`],
          ["기록 파일", P.view.path || (rec ? "(메모리 — 기록 저장 꺼짐)" : "아직 없음")]]),
      el("p", { class: "notice draft-banner" },
        `초안 문구 사용 중 — 사후 면담 문구 ${P.cfg.protocol.draftCount}개가 status draft(IRB 검토 전)입니다.`),
      el("details", { class: "pi-rules", open: "" }, el("summary", {}, "실험자 규칙"),
        el("ul", {}, ...P.cfg.experimenterRules.map((r) => el("li", {}, r.text)))),
      conditionPicker(!!rec),
    ];
    if (!P.condition) parts.push(el("p", { class: "empty" }, "조건을 고르면 그 조건의 문항만 보입니다."));
    else if (!rec) parts.push(form("free"));
    else {
      parts.push(savedList(rec));
      if (!rec.completedAt) parts.push(form("after_free"));
      else parts.push(el("p", { class: "msg bot closing" }, "사후 면담을 다 저장했습니다."));
    }
    box.replaceChildren(...parts);
  }

  function conditionPicker(locked) {
    const fs = el("fieldset", { class: "conditions pi-conditions" }, el("legend", {}, locked ? "조건(저장한 기록의 조건)" : "조건"));
    for (const c of P.cfg.conditions) {
      const input = el("input", { type: "radio", name: "pi-condition", value: c.id });
      if (P.condition === c.id) input.checked = true;
      if (locked) input.disabled = true;
      input.addEventListener("change", () => { P.condition = c.id; draw(); });
      fs.append(el("label", { class: "choice" }, input, el("span", {}, c.label)));
    }
    return fs;
  }

  function prompt(text) { return el("blockquote", { class: "pi-prompt" }, text); }

  function skipBox(name, label) {
    const cb = el("input", { type: "checkbox", name });
    return [cb, el("label", { class: "pi-skip" }, cb, ` ${label}`)];
  }

  // ── 문항 그리기 · 응답 모으기 ────────────────────────────────────────────────
  function form(part) {
    const f = el("form", { class: "premeasure pi-form", novalidate: "" });
    const getters = [];
    for (const it of itemsFor(part)) {
      const fs = el("fieldset", { class: "pm-item pi-item", "data-item": it.id },
        el("legend", {}, `${it.id} · ${KIND_NOTE[it.kind] || it.kind}`));
      if (it.kind === "oral" || it.kind === "typed") {
        const ta = el("textarea", { rows: it.kind === "typed" ? "2" : "5", "aria-label": it.id });
        const [cb, lab] = skipBox(`${it.id}-skip`, it.kind === "typed" ? P.cfg.uiPhrases.typedSkip : "말하지 않음(건너뜀)");
        fs.append(prompt(it.text), ta, lab);
        getters.push(() => {
          if (cb.checked) return [{ id: it.id, skipped: true }];
          if (!ta.value.trim()) throw new Error(`${it.id}: 받아 적은 글이 없습니다(말하지 않았으면 건너뜀).`);
          return [{ id: it.id, text: ta.value }];
        });
      } else if (it.kind === "oral_repeat") {
        fs.append(el("p", { class: "hint" }, it.fillNote || ""));
        const rounds = [];
        for (let r = 1; r <= (it.maxRounds || 2); r++) {
          const word = el("input", { type: "text", maxlength: "40", "aria-label": `${it.id} ${r}회차 참여자 낱말` });
          const said = el("p", { class: "pi-prompt-live" }, "");
          const ta = el("textarea", { rows: "3", "aria-label": `${it.id} ${r}회차 받아 적기` });
          word.addEventListener("input", () => {
            const w = word.value.trim();
            said.textContent = w ? it.text.replace(it.placeholder, w) : "";
            said.classList.toggle("bad", !!w && !earlierText(f).includes(w));
          });
          fs.append(el("label", { class: "field" }, `${r}회차 — 참여자 낱말(X, 비우면 묻지 않음)`, word), said, ta);
          rounds.push({ word, ta });
        }
        getters.push(() => rounds.filter((x) => x.word.value.trim()).map((x) => ({ id: it.id, word: x.word.value, text: x.ta.value })));
      } else if (it.kind === "choice") {
        fs.append(prompt(it.text));
        const opts = el("div", { class: "pi-options" });
        for (const o of [...it.options, { id: "__skip", text: "답하지 않음" }]) {
          const id = `pi-${it.id}-${o.id}`;
          opts.append(el("label", { for: id, class: "choice" }, el("input", { type: "radio", name: `pi-${it.id}`, id, value: o.id }), ` ${o.text}`));
        }
        fs.append(opts);
        getters.push(() => {
          const c = f.querySelector(`input[name="pi-${CSS.escape(it.id)}"]:checked`);
          if (!c) throw new Error(`${it.id}: 아직 고르지 않았습니다.`);
          return [c.value === "__skip" ? { id: it.id, skipped: true } : { id: it.id, choice: c.value }];
        });
      } else if (it.kind === "rating_group") {
        fs.append(prompt(it.text));
        const sc = it.scale;
        const n = sc.max - sc.min + 1;
        for (const sub of it.items) {
          const pts = el("div", { class: "scale-points", style: `--n:${n}` });
          for (let k = sc.min; k <= sc.max; k++) {
            const id = `pi-${sub.id}-${k}`;
            pts.append(el("label", { for: id, class: "pt" }, el("input", { type: "radio", name: `pi-${sub.id}`, id, value: String(k) }),
              el("span", { class: "pt-num" }, String(k)), el("span", { class: "pt-anchor" }, sc.anchors[String(k)] || "")));
          }
          const sid = `pi-${sub.id}-skip`;
          fs.append(el("div", { class: "pi-sub", "data-item": sub.id }, el("p", { class: "pi-sub-text" }, sub.text),
            el("div", { class: "scale" }, pts, el("span", { class: "scale-gap", "aria-hidden": "true" }),
              el("label", { for: sid, class: "pt skip" }, el("input", { type: "radio", name: `pi-${sub.id}`, id: sid, value: "" }),
                el("span", { class: "pt-anchor" }, P.cfg.uiPhrases.ratingSkip)))));
          getters.push(() => {
            const c = f.querySelector(`input[name="pi-${CSS.escape(sub.id)}"]:checked`);
            if (!c) throw new Error(`${sub.id}: 아직 고르지 않았습니다.`);
            return [{ id: sub.id, value: c.value === "" ? null : Number(c.value) }];
          });
        }
      }
      f.append(fs);
    }
    const err = el("p", { class: "form-error", role: "alert", hidden: "" });
    const submit = el("button", { class: "primary", type: "submit" },
      part === "free" ? "자유 응답 저장(이 뒤에 평정 묶음이 보임)" : "저장(사후 면담 끝)");
    f.append(err, el("div", { class: "buttons stage-actions" }, submit));
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (P.busy) return;
      let responses;
      try { responses = getters.flatMap((g) => g()); } catch (x) { err.textContent = x.message; err.hidden = false; return; }
      err.hidden = true;
      P.busy = true;
      submit.classList.add("is-pending");
      try {
        P.view = await api("POST", `/api/sessions/${encodeURIComponent(P.sid)}/postinterview`, { condition: P.condition, part, responses });
        draw();
      } catch (x) {
        err.textContent = x.message; err.hidden = false;
      } finally {
        P.busy = false;
        submit.classList.remove("is-pending");
      }
    });
    return f;
  }

  // PI3의 X가 앞서 받아 적은 글(구두 문항 + 앞 회차)에 있는지 화면에서 미리 알림(빨간 글). 서버가 같은 것을 확인해 거부한다.
  function earlierText(f) {
    return [...f.querySelectorAll(".pi-item textarea")].map((t) => t.value).join("\n");
  }

  function savedList(rec) {
    const rows = rec.items.map((i) => {
      const v = i.skipped ? "(건너뜀)" : i.text != null ? i.text : i.choiceText != null ? i.choiceText : i.value;
      const head = i.round ? `${i.id} ${i.round}회차 ('${i.word}')` : i.id;
      return [head, v];
    });
    return el("section", { class: "pi-saved" }, el("h3", {}, "저장한 응답"), kv(rows));
  }

  window.ifsPostInterview = { open, _state: P };
})();
