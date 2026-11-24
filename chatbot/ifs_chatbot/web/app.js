// IFS 면담 데모 — 참여자 화면 + 연구자 화면. 외부 라이브러리 없음(연구실 오프라인 사용).
"use strict";

const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const c of children) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
};

const state = { health: null, sid: null, view: null, log: null, tab: "progress", editing: false, busy: false, crisisFocused: false };

// ── 보기: 연구자(기본) | 참여자 (G44) ────────────────────────────────────────
// 기본은 연구자 보기다(지금까지의 기본값, 내부 시행 안내 2절 8번이 연구자 화면을 보며 점검함).
// 참여자 보기는 가운데 한 단에 참여자가 보는 것만 둔다(연구자 패널·머리글 배지·문구 출처 꼬리표·미리보기 대체 사유 숨김).
// 주소 ?view=participant|researcher로 열 수 있고, 머리글 [연구자 화면] 체크를 풀면 참여자 보기가 된다.
// 참여자 보기에는 되돌리는 단추를 두지 않는다(참여자에게 보이는 글자를 늘리지 않음) → Ctrl+Alt+R 또는 주소로 되돌린다.
function isResearcherView() { return document.body.dataset.view !== "participant"; }

function setView(view, { updateUrl = true } = {}) {
  const v = view === "participant" ? "participant" : "researcher";
  document.body.dataset.view = v;
  $("#toggle-researcher").checked = v === "researcher";
  $("#researcher").hidden = v !== "researcher";
  $("#layout").classList.toggle("solo", v !== "researcher");
  if (updateUrl) {
    const u = new URL(location.href);
    u.searchParams.set("view", v);
    history.replaceState(null, "", u);
  }
  if (state.view) render(state.view);
}

// ── 진행 표시: 글 없이 "n / N" + 칸 막대(G44). 단계 이름 문구를 새로 만들지 않는다 ──────────
// 참여자가 거치는 단계: 면담 · 확정 (기본 설정) + 후보 · 조절 · 사전 측정 (새 흐름 [selection]).
// 후보 단계를 건너뛴 세션(G34)은 그 칸을 지난 것으로 칠한다. 위기·그만·폐기에서는 숨긴다.
function updateProgress() {
  const box = $("#progress");
  const v = state.view;
  if (!v || ["crisis", "stopped", "withdrawn"].includes(v.state)) { box.hidden = true; return; }
  const total = v.selection ? 5 : 2;
  const sel = window.ifsStage ? window.ifsStage.current() : {};
  let pos, done;
  if (sel.stage === "selecting") { pos = 3; done = 2; }
  else if (sel.stage === "adjusting") { pos = 4; done = 3; }
  else if (sel.stage === "premeasure") { pos = 5; done = 4; }
  else if (sel.stage === "done") { pos = 5; done = 5; }
  else if (v.awaiting === "confirm") { pos = 2; done = 1; }
  else if (v.state === "done") { pos = 2; done = 2; }
  else { pos = 1; done = 0; }
  $("#progress-count").textContent = `${pos} / ${total}`;
  const bar = $("#progress-bar");
  bar.replaceChildren(...Array.from({ length: total }, (_, i) =>
    el("i", { class: i < done ? "done" : i === pos - 1 ? "current" : "" })));
  box.hidden = false;
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${res.status}`);
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 4000);
}

// 보내는 중: 중복 제출을 막고(단추 끔 + state.busy), 보내기 단추에 대기 표시, 상태 줄을 낭독기에 알림.
// 초점이 있던 단추는 끄지 않고 aria-disabled로 둔다(끈 단추는 초점을 잃어 키보드 사용자가 처음부터 다시 Tab해야 함).
function setBusy(on) {
  state.busy = on;
  $("#busy").hidden = !on;
  $("#composer").setAttribute("aria-busy", on ? "true" : "false");
  $("#btn-send").classList.toggle("is-pending", on);
  document.querySelectorAll("#buttons button, #composer button").forEach((b) => {
    if (b === document.activeElement) { b.setAttribute("aria-disabled", on ? "true" : "false"); b.classList.toggle("is-pending", on); }
    else b.disabled = on;
  });
  if (!on) document.querySelectorAll("#buttons button[aria-disabled], #composer button[aria-disabled]").forEach((b) => {
    b.removeAttribute("aria-disabled"); b.classList.remove("is-pending"); });
}

// ── 시작 ─────────────────────────────────────────────────────────────────────
async function loadHealth() {
  try {
    const h = await api("GET", "/api/health");
    state.health = h;
    const b = h.backend || {};
    const badge = $("#badge-model");
    badge.textContent = b.ok ? `모델 ${b.name}` : "LLM 사용 불가";
    if (!b.ok) badge.classList.add("bad");
    const warn = $("#setup-warning");
    const msgs = [...(h.warnings || [])];
    if (!b.ok) {
      document.querySelector('input[value="chatbot"]').disabled = true;
      document.querySelector('input[value="static"]').checked = true;
    }
    if (msgs.length) {
      warn.textContent = msgs.join(" / ");
      warn.hidden = false;
    }
    const def = h.defaultCondition;
    const radio = document.querySelector(`input[name="condition"][value="${def}"]`);
    if (radio && !radio.disabled) radio.checked = true;
  } catch (e) {
    toast(`서버 상태를 읽지 못했습니다: ${e.message}`);
  }
}

async function createSession() {
  const condition = document.querySelector('input[name="condition"]:checked').value;
  const sessionId = $("#session-id").value.trim() || undefined;
  try {
    setBusy(true);
    const v = await api("POST", "/api/sessions", { condition, sessionId });
    state.sid = v.sessionId;
    $("#setup").hidden = true;
    $("#chat").hidden = false;
    render(v);
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
  }
}

// ── 동작 ─────────────────────────────────────────────────────────────────────
async function send(text) {
  if (!state.sid) return toast("먼저 세션을 만들어 주세요.");
  if (!text.trim() || state.busy) return;
  setBusy(true);
  try {
    render(await api("POST", `/api/sessions/${state.sid}/reply`, { text }));
    $("#input").value = "";
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
  }
}

async function act(action, text) {
  if (state.busy) return;
  if (action === "withdraw" && !confirm("지금까지 적어 주신 내용을 저장하지 않고 지울까요? 지우면 되돌릴 수 없어요.")) return;
  setBusy(true);
  try {
    render(await api("POST", `/api/sessions/${state.sid}/action`, { action, text }));
  } catch (e) {
    toast(e.message);
  } finally {
    setBusy(false);
  }
}

// ── 참여자 화면 ───────────────────────────────────────────────────────────────
const KIND_CLASS = { question: "bot", info: "bot info", check: "bot check", crisis: "bot crisis", confirm: "bot confirm", closing: "bot closing" };

function render(v) {
  state.view = v;
  const chat = $("#chat");
  let crisisNode = null;
  chat.replaceChildren(
    ...v.messages.map((m) => {
      const cls = m.speaker === "participant" ? "msg me" : `msg ${KIND_CLASS[m.kind] || "bot"}`;
      const node = el("div", { class: cls }, m.text);
      if (m.speaker !== "participant" && m.source && isResearcherView()) {
        node.append(el("span", { class: "src", text: m.source }));
      }
      if (m.kind === "crisis") { node.setAttribute("tabindex", "-1"); crisisNode = node; }
      return node;
    })
  );
  chat.scrollTop = chat.scrollHeight;
  // 위기 고정 문구가 묻히지 않게(표시 방식만, 문구·판정은 그대로): 한 번만 그 문구로 초점을 옮겨 화면에 보이게 하고
  // 낭독기가 읽게 한다. 대화 칸 안에서 잘리지 않게 대화 칸 높이 제한도 푼다(.chat.has-crisis).
  chat.classList.toggle("has-crisis", !!crisisNode);
  if (crisisNode && !state.crisisFocused) {
    state.crisisFocused = true;
    crisisNode.focus({ preventScroll: true });
    crisisNode.scrollIntoView({ block: "nearest" });
  }

  const cond = $("#badge-condition");
  cond.textContent = v.condition.label;
  cond.hidden = false;
  const stage = $("#badge-stage");
  if (v.stageInfo && v.stageInfo.ifs) {
    stage.textContent = `IFS ${v.stageInfo.ifs} · ${v.stageInfo.labelKo}`;
    stage.title = v.stageInfo.purposeKo || "";
    stage.hidden = false;
  } else stage.hidden = true;

  // 확정 텍스트
  const box = $("#confirm-box");
  if (v.awaiting === "confirm") {
    box.hidden = false;
    const ta = $("#draft");
    if (!state.editing) ta.value = v.confirmDraft || "";
    ta.readOnly = !state.editing;
  } else {
    box.hidden = true;
    state.editing = false;
  }

  $("#composer").hidden = v.awaiting !== "reply";
  if (v.awaiting === "reply") $("#input").focus({ preventScroll: true });

  const btns = $("#buttons");
  btns.replaceChildren();
  const risky = [];   // 그만·응답 폐기는 다른 단추와 떨어뜨려 줄 끝에 둔다(화면 순서 = 탭 순서 유지)
  for (const b of v.buttons) {
    if (b.action === "edit") {
      if (state.editing) {
        btns.append(el("button", { class: "primary", onclick: () => act("edit", $("#draft").value) }, "고친 내용으로 할게요"));
        btns.append(el("button", { class: "ghost", onclick: () => { state.editing = false; render(state.view); } }, "취소"));
      } else {
        btns.append(el("button", { onclick: () => { state.editing = true; render(state.view); $("#draft").focus(); } }, b.label));
      }
      continue;
    }
    if (state.editing && b.action === "confirm") continue;
    const danger = b.action === "stop" || b.action === "withdraw";
    const cls = danger ? "danger" : ["start", "continue", "confirm"].includes(b.action) ? "primary" : "";
    const node = el("button", { class: cls, onclick: () => act(b.action) }, b.label);
    if (danger) risky.push(node); else btns.append(node);
  }
  if (risky.length) btns.append(el("span", { class: "spacer", "aria-hidden": "true" }), ...risky);
  if (["done", "stopped", "crisis", "withdrawn"].includes(v.state) && isResearcherView()) {
    // 새 세션은 연구자가 하는 일이라 연구자 보기에서만 보인다
    btns.append(el("button", { class: "ghost", onclick: () => { const u = new URL(location.href); u.searchParams.delete("sid"); location.href = u; } }, "새 세션"));
  }
  if (window.ifsStage) window.ifsStage.afterRender(v);   // 면담 뒤 단계(stage.js, 새 흐름에서만)
  updateProgress();
  refreshResearcher();
}

// ── 연구자 화면 ───────────────────────────────────────────────────────────────
async function refreshResearcher() {
  if (!state.sid || !$("#toggle-researcher").checked) return;
  try {
    const r = await api("GET", `/api/sessions/${state.sid}/log`);
    state.log = r.log;
    renderSafetyFlags(r.safetyFlags);
    renderProgress(r);
    if (window.ifsStage) window.ifsStage.researcherNote($("#tab-progress"));
    renderTurns(r.log);
    renderExtract(r.log);
    $("#json-view").textContent = JSON.stringify(r.log, null, 2);
  } catch (e) {
    /* 폐기된 세션 등 */
  }
}

// G50 (4): 넷째 제외 범주 표시(researcher_view().safetyFlags). refreshResearcher에서만 부른다 — 참여자 보기에서는 부르지 않고
// 자리도 연구자 패널 안이다. 글은 연구자용 로그 문자열(고정 문구 아님). 진행은 막지 않는다(VR 진행 여부는 연구자가 정함, 초안).
// 같은 내용이면 다시 그리지 않는다(role=alert가 매번 다시 읽히지 않게).
function describeSafetyFlag(f) {
  const parts = [];
  if (Number.isInteger(f.sentence)) parts.push(`${f.sentence + 1}번째 문장`);
  if (Array.isArray(f.charSpan) && f.charSpan.length === 2) parts.push(`글자 ${f.charSpan[0]}–${f.charSpan[1]}`);
  if (f.position) parts.push(`자리 ${f.position}`);
  if (f.scope && f.scope !== "main") parts.push(`범위 ${f.scope}${f.scope === "context" ? "(회상·상황 문장)" : ""}`);
  parts.push(f.formBlock ? "형태 막음" : "형태 막지 않음(색)");
  return `${f.lemma || "?"} — ${parts.join(", ")}`;
}

function renderSafetyFlags(flags) {
  const box = $("#safety-flags");
  const list = Array.isArray(flags) ? flags : [];
  const sig = JSON.stringify(list);
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  box.hidden = list.length === 0;
  if (!list.length) { box.replaceChildren(); return; }
  const cats = [...new Set(list.map((f) => f.category).filter(Boolean))].join(", ");
  box.replaceChildren(
    el("strong", {}, `[안전 표시] 넷째 제외 범주(죽음·자해·외상) 낱말: ${list.length}곳${cats ? ` [${cats}]` : ""}`),
    el("ul", {}, ...list.map((f) => el("li", {}, describeSafetyFlag(f)))),
    el("p", {}, "진행은 막지 않음 — VR 진행 여부는 연구자가 정함"));
}

function kv(pairs) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of pairs) dl.append(el("dt", {}, k), el("dd", {}, v == null || v === "" ? "—" : String(v)));
  return dl;
}

function renderProgress(r) {
  const v = r.session, log = r.log, h = state.health || {};
  const t = $("#tab-progress");
  const model = log.model || {};
  t.replaceChildren(
    el("h3", {}, "세션"),
    kv([
      ["세션 ID", v.sessionId], ["조건", v.condition.label], ["상태", `${v.state} (대기: ${v.awaiting})`],
      ["IFS 단계", v.stageInfo ? `${v.stageInfo.ifs} — ${v.stageInfo.purposeKo}` : null],
      ["진행", `단계 ${v.progress.step + 1}/${v.progress.steps} · LLM 질문 ${v.progress.llmTurns}회`],
    ]),
    el("h3", {}, `알림 (${log.alerts.length})`),
    ...(log.alerts.length ? log.alerts.map((a) => el("div", { class: `alert ${a.severity}` }, `[${a.kind}] ${a.detail}`, a.turn != null ? ` · 턴 ${a.turn}` : "")) : [el("p", { class: "empty" }, "없음")]),
    el("h3", {}, "모델·가드·버전"),
    kv([
      ["면담 모델", model.name ? `${model.name} ${model.quant || ""}` : "없음 (조건 1)"],
      ["digest", model.digest], ["runtime", model.runtime],
      ["샘플링", model.sampling ? JSON.stringify(model.sampling) : null],
      ["가드", log.guard && log.guard.name], ["가드 digest", log.guard && log.guard.digest],
      ["프롬프트", `${log.protocol.promptVersion} (ctx ${log.protocol.contextTemplateVersion})`],
      ["사전", `1층 ${log.protocol.lexiconVersion} · 안전 ${log.protocol.safetyLexiconVersion}`],
      ["컨트롤러", log.protocol.controllerVersion], ["형태소", `${log.analyzer.backend} ${log.analyzer.version || ""}`],
    ]),
    ...(r.runtimeWarnings && r.runtimeWarnings.length ? [el("h3", {}, "런타임 경고"), ...r.runtimeWarnings.map((w) => el("div", { class: "alert" }, w))] : [])
  );
}

function renderTurns(log) {
  const t = $("#tab-turns");
  const nodes = [];
  let blocked = 0, fallbacks = 0, llm = 0;
  for (const turn of log.turns) {
    if (turn.speaker === "participant") {
      if ((turn.source || "").startsWith("control")) continue;
      const g = turn.guard || "";
      const pills = [el("span", { class: `pill ${g === "SAFE" ? "" : g === "CRISIS" ? "red" : "amber"}` }, `가드 ${g}`)];
      const f = turn.flags || {};
      if (f.noMore) pills.push(el("span", { class: "pill" }, "더 없음"));
      if (f.delegation) pills.push(el("span", { class: "pill amber" }, "판단 맡김"));
      if (f.depthStrong && f.depthStrong.length) pills.push(el("span", { class: "pill red" }, `L5 ${f.depthStrong.join(",")}`));
      if (f.softCheckSuppressed) pills.push(el("span", { class: "pill" }, "확인 생략(이미 계속)"));
      const reasons = (turn.guardDetail && turn.guardDetail.reasons) || [];
      nodes.push(el("div", { class: "turn participant" },
        el("div", { class: "head" }, el("span", {}, `#${turn.i} 참여자 · ${turn.stage || ""}`), el("span", {}, "")),
        el("div", { class: "text" }, turn.text), el("div", {}, ...pills, reasons.length ? el("small", {}, " " + reasons.join(", ")) : null)));
      continue;
    }
    if (turn.speaker === "interviewer" || (turn.source || "").startsWith("fixed:")) {
      const isLLM = turn.source === "llm" || turn.source === "fixed:fallback" || turn.source === "fixed:redirect";
      const head = el("div", { class: "head" }, el("span", {}, `#${turn.i} ${turn.speaker === "interviewer" ? "면담자" : "시스템"} · ${turn.stage || ""}`), el("span", {}, turn.source));
      const box = el("div", { class: "turn" }, head, el("div", { class: "text" }, turn.text || "(참여자에게 나가지 않음)"));
      if (turn.output) box.append(el("div", {}, el("span", { class: "pill" }, `template ${turn.output.template}`), el("span", { class: "pill" }, `anchor ‘${turn.output.anchor_quote}’`), el("span", { class: "pill" }, `move ${turn.output.move}`)));
      if (turn.checks && turn.checks.fallback) { box.append(el("span", { class: "pill red" }, "고정 대체 문구")); fallbacks++; }
      if (turn.phraseStatus) box.append(el("span", { class: `pill ${turn.phraseStatus === "spec" ? "" : "amber"}` }, `문구 ${turn.phraseStatus}`));
      for (const a of turn.attempts || []) {
        llm++;
        if (!a.passed) blocked++;
        const utter = (a.parsed && a.parsed.utterance) || a.raw || "";
        box.append(el("div", { class: `attempt ${a.passed ? "pass" : "block"}` },
          el("strong", {}, `시도 ${a.attempt + 1} ${a.passed ? "통과" : "차단"} `), el("small", {}, `${a.latencyMs}ms · seed ${a.seed}`), el("br"),
          utter, ...(a.passed ? [] : [el("br"), el("span", { class: "why" }, (a.reasonsText || a.reasons).join(" / "))])));
      }
      if (isLLM || turn.attempts) nodes.push(box);
      else if (turn.source !== "fixed:intro") nodes.push(box);
    }
  }
  t.replaceChildren(
    el("p", {}, `LLM 시도 ${llm}회 · 차단 ${blocked}회(보이지 않은 턴) · 고정 대체 ${fallbacks}회`),
    ...(nodes.length ? nodes : [el("p", { class: "empty" }, "아직 턴이 없습니다.")])
  );
}

function renderExtract(log) {
  const t = $("#tab-extract");
  const cap = log.capture || {};
  const parts = [];
  parts.push(el("h3", {}, "Find 단계 기록"));
  parts.push(kv([
    ["위치(bodyRelation)", cap.bodyRelation ? `${cap.bodyRelation.text} → ${cap.bodyRelation.part || "?"} · ${cap.bodyRelation.layer || "?"} (${cap.bodyRelation.ifsLocation || cap.bodyRelation.status})` : null],
    ["첫 반응 양식", cap.findModality ? `${cap.findModality.labels.join(", ")} (휴리스틱, 참여자에게 안 보임)` : null],
    ["차원 프로브", cap.probes ? `물음: ${cap.probes.asked.join(", ") || "없음"} / 이미 나와서 건너뜀: ${cap.probes.skippedAsCovered.join(", ") || "없음"}` : null],
  ]));
  if (!log.confirmedText) {
    parts.push(el("p", { class: "empty" }, "확정 텍스트가 아직 없습니다. 참여자가 [이대로 맞아요]를 누르면 그 텍스트만 추출로 넘어갑니다."));
    t.replaceChildren(...parts);
    return;
  }
  const ex = log.extraction;
  parts.push(el("h3", {}, `확정 텍스트 ${log.confirmation && log.confirmation.edited ? "(참여자가 고침)" : ""}`));
  parts.push(el("pre", { class: "json" }, log.confirmedText));
  parts.push(el("h3", {}, "1층 사전 매칭 (_provenance)"));
  const tb = el("table", {}, el("tr", {}, el("th", {}, "말"), el("th", {}, "범주"), el("th", {}, "값"), el("th", {}, "규칙 · 위치")));
  for (const a of ex.attributes) {
    tb.append(el("tr", {},
      el("td", {}, a._provenance.trigger, a.negated ? el("span", { class: "pill red" }, "부정") : null, a.change ? el("span", { class: "pill" }, a.change) : null),
      el("td", {}, a.category), el("td", {}, JSON.stringify(a.value)),
      el("td", {}, `${a._provenance.rule} [${a._provenance.charSpan}]`, a.valueSource === "draft" ? el("span", { class: "pill amber" }, "초안 값") : null)));
  }
  parts.push(tb);
  parts.push(el("h3", {}, "2층 직유 표지"));
  parts.push(ex.similes.length ? el("ul", {}, ...ex.similes.map((s) => el("li", {}, `‘${s.sourceNoun}’ + ${s.marker} → ${s.formPrototype || "형태 미정"} (${s.method})`))) : el("p", { class: "empty" }, "없음"));
  parts.push(el("h3", {}, `사전 밖 내용어 — 소실 정보율 근사 ${ex.lostInformation.rate ?? "—"}`));
  parts.push(ex.unmatched.length ? el("p", {}, ...ex.unmatched.map((u) => el("span", { class: "mark" }, u.surface), " ")) : el("p", { class: "empty" }, "없음"));
  const d = ex.sceneSpecDraft;
  parts.push(el("h3", {}, "IFSSceneSpec 초안 (말한 것만)"));
  parts.push(el("pre", { class: "json" }, JSON.stringify({ slots: d.slots, unspecified: d.unspecified, unresolved: d.unresolved, negated: d.negated }, null, 2)));
  t.replaceChildren(...parts);
}

// ── 이벤트 ───────────────────────────────────────────────────────────────────
function switchTab(name) {
  state.tab = name;
  document.querySelectorAll(".tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
    b.setAttribute("aria-selected", b.dataset.tab === name ? "true" : "false");
  });
  for (const id of ["progress", "turns", "extract", "json"]) $(`#tab-${id}`).hidden = id !== name;
}

// 주소에 ?sid=<세션 ID>가 있으면 그 세션 화면을 다시 연다(연구자가 이어서 진행하거나 화면을 확인할 때).
async function resumeFromUrl() {
  const sid = new URLSearchParams(location.search).get("sid");
  if (!sid) return;
  try {
    const v = await api("GET", `/api/sessions/${encodeURIComponent(sid)}`);
    state.sid = v.sessionId;
    $("#setup").hidden = true;
    $("#chat").hidden = false;
    render(v);
  } catch (e) {
    toast(`세션을 열지 못했습니다: ${e.message}`);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setView(new URLSearchParams(location.search).get("view") || "researcher", { updateUrl: false });
  // 머리글 실제 높이(줄바꿈되면 커짐) → 조절 미리보기가 따라 내려올 위치(--topbar-h)
  const topbar = document.querySelector(".topbar");
  new ResizeObserver(() => document.documentElement.style.setProperty("--topbar-h", `${topbar.offsetHeight}px`)).observe(topbar);
  document.addEventListener("keydown", (e) => {
    // 참여자 보기에서 연구자 보기로 돌아가기(화면에 단추를 두지 않음). 연구자 보기에서는 참여자 보기로.
    if (e.ctrlKey && e.altKey && !e.shiftKey && (e.key === "r" || e.key === "R" || e.code === "KeyR")) {
      e.preventDefault();
      setView(isResearcherView() ? "participant" : "researcher");
    }
  });
  loadHealth().then(resumeFromUrl);
  $("#btn-create").addEventListener("click", createSession);
  $("#composer").addEventListener("submit", (e) => { e.preventDefault(); send($("#input").value); });
  $("#input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send($("#input").value); }
  });
  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  $("#toggle-researcher").addEventListener("change", (e) => setView(e.target.checked ? "researcher" : "participant"));
  $("#btn-download").addEventListener("click", () => {
    if (!state.log) return;
    const blob = new Blob([JSON.stringify(state.log, null, 2)], { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: `${state.sid}.json` });
    document.body.append(a); a.click(); a.remove();
  });
});
