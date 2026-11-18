// 보기 전 보고 과제 (문구 shared/protocol/prereport_task.v0.2.json, 기록 형식 shared/schemas/prereport.v0.2.json).
// 면담 밖의 고정 문구 과제다. LLM을 부르지 않는다. 외부 라이브러리 없음(연구실 오프라인 사용).
// 참여자에게 보이는 문구는 모두 과제 파일에서 가져온다(코드에 문구를 두지 않는다).
// 절차: 속성마다 ①②③을 먼저 [확인]으로 정하고, 색·크기는 ①②일 때만 값 고르기 화면이 나온다.
//   ③이면 값을 남기지 않는다. 값을 고른 뒤 [답 바꾸기]로 확정 여부를 바꾸면 commitmentChangedAfterPick = true.
//   첫 의도적 선택(firstValue)과 [확인] 때 값(value)을 함께 남긴다. 새로고침해도 sessionStorage로 이어 간다.
"use strict";

const $ = (sel) => document.querySelector(sel);
const sid = new URLSearchParams(location.search).get("session") || "";
const COMMITTED = ["from_start", "when_asked"];
const STORE_KEY = `ifs-prereport:${sid}`;
const r4 = (x) => Math.round(x * 10000) / 10000;

let task = null;
let st = null;            // {taskVersion, idx, phase, pending, answers, cur}
let dragging = false;

function freshCur() {
  return { commitment: null, value: null, firstValue: null, widthM: null, firstWidthM: null,
           nSelections: 0, changedAfterPick: false };
}

function save() {
  try { sessionStorage.setItem(STORE_KEY, JSON.stringify(st)); } catch (e) { /* 저장 불가면 이어 가기만 못 함 */ }
}

function restore() {
  try {
    const s = JSON.parse(sessionStorage.getItem(STORE_KEY) || "null");
    if (s && s.taskVersion === task.taskVersion && s.cur) return s;
  } catch (e) { /* 무시 */ }
  return { taskVersion: task.taskVersion, idx: 0, phase: "commit", pending: null, answers: {}, cur: freshCur() };
}

const phrase = (id, vars = {}) => task.fixedPhrases[id].text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || res.status));
    err.status = res.status;
    throw err;
  }
  return data;
}

function showMessage(text) {
  $("#pr-step").hidden = true;
  $("#pr-progress").hidden = true;
  const m = $("#pr-message");
  m.textContent = text;
  m.hidden = false;
}

function attr() { return task.attributeOrder[st.idx]; }
function info() { return task.attributes[attr()]; }
function needsPick(c) { return !!info().valuePick && COMMITTED.includes(c); }

// ── 색: 색상각 × 밝기 면(채도 고정) + 무채색 띠 ───────────────────────────────
function hslToRgb(h, s, l) {
  const a = s * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h * 12) % 12;
    return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [f(0), f(8), f(4)].map((x) => Math.round(x * 255));
}

function lOfY(fy) {
  const c = task.colorField;
  return c.lightnessTop - fy * (c.lightnessTop - c.lightnessBottom);
}
function yOfL(l, h) {
  const c = task.colorField;
  return ((c.lightnessTop - l) / (c.lightnessTop - c.lightnessBottom)) * (h - 1);
}

function paint(cv, sat, hueOf) {
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(cv.width, cv.height);
  for (let y = 0; y < cv.height; y++) {
    const l = lOfY(y / (cv.height - 1));
    for (let x = 0; x < cv.width; x++) {
      const [r, g, b] = hslToRgb(hueOf(x), sat, l);
      const i = (y * cv.width + x) * 4;
      img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return ctx;
}

function ring(ctx, x, y) {
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#ffffff"; ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.stroke();
  ctx.strokeStyle = "#000000"; ctx.beginPath(); ctx.arc(x, y, 11, 0, Math.PI * 2); ctx.stroke();
}

function drawColor() {
  const field = $("#pr-color-field"), strip = $("#pr-achromatic");
  const fctx = paint(field, task.colorField.saturation, (x) => x / field.width);
  const sctx = paint(strip, 0, () => 0);
  const v = st.cur.value;
  if (v && v.h === null) ring(sctx, strip.width / 2, yOfL(v.l, strip.height));
  else if (v) ring(fctx, v.h * field.width, yOfL(v.l, field.height));
}

function pickColor(ev, achromatic) {
  const cv = ev.currentTarget;
  const rect = cv.getBoundingClientRect();
  const fx = Math.min(Math.max((ev.clientX - rect.left) / rect.width, 0), 0.9999);
  const fy = Math.min(Math.max((ev.clientY - rect.top) / rect.height, 0), 1);
  const l = r4(lOfY(fy));
  const v = achromatic ? { h: null, s: 0, l } : { h: r4(fx), l };
  const c = st.cur;
  c.value = v;
  c.nSelections += 1;
  if (c.firstValue === null) c.firstValue = { ...v };
  save();
  drawColor();
  updateButtons();
}

// ── 크기: 손잡이 없는 막대 + 서 있는 사람 윤곽 옆의 중립 원 ─────────────────────
function widthOf(s) {
  const c = task.sizeSlider;
  return r4(c.baseDiameterM * Math.pow(2, (s - 0.5) * 4));
}

function drawSize() {
  const cv = $("#pr-size-view");
  const ctx = cv.getContext("2d");
  const ink = getComputedStyle(document.documentElement).getPropertyValue("--ink-soft").trim() || "#5b6b6e";
  ctx.clearRect(0, 0, cv.width, cv.height);
  const c = task.sizeSlider;
  const worldH = Math.max(c.figureHeightM, c.baseDiameterM * 4) * 1.08;
  const ppm = (cv.height - 20) / worldH;
  const ground = cv.height - 10;
  ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(10, ground); ctx.lineTo(cv.width - 10, ground); ctx.stroke();
  const H = c.figureHeightM * ppm, fx = 90, head = H * 0.065, halfW = H * 0.13;
  const shoulder = ground - H + head * 2.3, hip = ground - H * 0.47;
  ctx.globalAlpha = 0.55;
  ctx.beginPath(); ctx.arc(fx, ground - H + head, head, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath();
  ctx.moveTo(fx - halfW, shoulder); ctx.lineTo(fx + halfW, shoulder);
  ctx.lineTo(fx + halfW * 0.8, hip); ctx.lineTo(fx + halfW * 0.55, ground);
  ctx.lineTo(fx + halfW * 0.12, ground); ctx.lineTo(fx, hip + H * 0.05);
  ctx.lineTo(fx - halfW * 0.12, ground); ctx.lineTo(fx - halfW * 0.55, ground);
  ctx.lineTo(fx - halfW * 0.8, hip); ctx.closePath(); ctx.fill();
  ctx.globalAlpha = 1;
  const thumb = $("#pr-size-thumb");
  const v = st.cur.value;
  thumb.hidden = typeof v !== "number";
  if (typeof v === "number") {
    thumb.style.left = `${v * 100}%`;
    $("#pr-size-track").setAttribute("aria-valuenow", String(v));
    const d = c.baseDiameterM * Math.pow(2, (v - 0.5) * 4) * ppm;
    const cx = Math.min(cv.width - 14 - d / 2, Math.max(fx + halfW + 30 + d / 2, (cv.width + fx) / 2));
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(cx, ground - d / 2, d / 2, 0, Math.PI * 2); ctx.stroke();
  } else $("#pr-size-track").removeAttribute("aria-valuenow");
}

function setSize(v) {
  st.cur.value = r4(Math.min(Math.max(v, 0), 1));
  st.cur.widthM = widthOf(st.cur.value);
  drawSize();
}

function sizeFromEvent(ev) {
  const rect = $("#pr-size-track").getBoundingClientRect();
  return (ev.clientX - rect.left) / rect.width;
}

function commitSizeSelection() {
  const c = st.cur;
  c.nSelections += 1;
  if (c.firstValue === null) { c.firstValue = c.value; c.firstWidthM = c.widthM; }
  save();
  updateButtons();
}

// ── 화면 ───────────────────────────────────────────────────────────────────
function optionLabel(id) {
  const o = task.commitmentOptions.find((x) => x.id === id);
  return o ? `${o.mark} ${o.label}` : "";
}

function updateButtons() {
  const next = $("#pr-next");
  next.disabled = st.phase === "commit" ? !st.pending : st.cur.value === null;
}

function render() {
  const t = task, a = info();
  $("#pr-intro").textContent = t.fixedPhrases.intro.text;
  $("#pr-intro").hidden = st.idx !== 0 || st.phase !== "commit";
  $("#pr-question").textContent = a.question.text;
  const prog = $("#pr-progress");
  prog.textContent = `${st.idx + 1} / ${t.attributeOrder.length}`;
  prog.hidden = false;
  $("#pr-next").textContent = phrase("next_button");
  $("#pr-back").textContent = phrase("change_answer");

  const commit = st.phase === "commit";
  $("#pr-commit").hidden = !commit;
  $("#pr-pick").hidden = commit;
  $("#pr-back").hidden = commit;
  if (commit) {
    const opts = $("#pr-options");
    opts.replaceChildren();
    for (const o of t.commitmentOptions) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "pr-option";
      b.dataset.id = o.id;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(st.pending === o.id));
      b.textContent = `${o.mark} ${o.label}`;
      b.addEventListener("click", () => { st.pending = o.id; save(); render(); });
      opts.append(b);
    }
  } else {
    $("#pr-answer").textContent = phrase("your_answer", { answer: optionLabel(st.cur.commitment) });
    const kind = a.valuePick;
    $("#pr-color").hidden = kind !== "color";
    $("#pr-size").hidden = kind !== "size";
    $("#pr-color-text").textContent = phrase("color_pick");
    $("#pr-size-text").textContent = phrase("size_pick");
    if (kind === "color") drawColor();
    if (kind === "size") drawSize();
  }
  updateButtons();
}

function finalize() {
  const c = st.cur, a = info();
  let ans = { commitment: c.commitment };
  if (a.valuePick) {
    const keep = COMMITTED.includes(c.commitment);
    ans = {
      commitment: c.commitment,
      value: keep ? c.value : null,
      firstValue: keep ? c.firstValue : null,
      method: a.valuePick === "color" ? task.colorField.method : task.sizeSlider.method,
      nSelections: c.nSelections,
      commitmentChangedAfterPick: c.changedAfterPick,
    };
    if (a.valuePick === "size") {
      ans.widthM = keep ? c.widthM : null;
      ans.firstWidthM = keep ? c.firstWidthM : null;
    }
  }
  st.answers[attr()] = ans;
}

async function onNext() {
  if ($("#pr-next").disabled) return;
  if (st.phase === "commit") {
    const c = st.cur;
    if (c.nSelections > 0 && c.commitment && st.pending !== c.commitment) c.changedAfterPick = true;
    c.commitment = st.pending;
    if (needsPick(c.commitment)) {
      st.phase = "pick";
      save();
      return render();
    }
  }
  finalize();
  if (st.idx + 1 < task.attributeOrder.length) {
    st.idx += 1;
    st.phase = "commit";
    st.pending = null;
    st.cur = freshCur();
    save();
    render();
    window.scrollTo(0, 0);
    return;
  }
  $("#pr-next").disabled = true;
  try {
    await api("POST", `/api/sessions/${encodeURIComponent(sid)}/prereport`, { attributes: st.answers });
    sessionStorage.removeItem(STORE_KEY);
    showMessage(phrase("done"));
  } catch (e) {
    console.error(e);
    showMessage(e.status === 409 ? phrase("already_submitted") : phrase("submit_refused"));
  }
}

function onBack() {
  st.phase = "commit";
  st.pending = st.cur.commitment;
  save();
  render();
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    task = await api("GET", "/api/prereport/task");
  } catch (e) {
    console.error(e);
    return showMessage("—");
  }
  document.title = phrase("page_title");
  $("#pr-title").textContent = phrase("page_title");
  $("#pr-session").textContent = sid ? phrase("session_label", { sessionId: sid }) : "";
  const aria = task.ariaLabels;
  $("#pr-color-field").setAttribute("aria-label", aria.color_field);
  $("#pr-achromatic").setAttribute("aria-label", aria.achromatic_strip);
  $("#pr-size-view").setAttribute("aria-label", aria.size_view);
  $("#pr-size-track").setAttribute("aria-label", aria.size_slider);
  if (!sid) return showMessage(phrase("not_ready"));
  try {
    const s = await api("GET", `/api/sessions/${encodeURIComponent(sid)}/prereport`);
    if (s.submitted) return showMessage(phrase("already_submitted"));
    if (!s.available) { console.info(s.reason); return showMessage(phrase("not_ready")); }
  } catch (e) {
    console.error(e);
    return showMessage(phrase("not_ready"));
  }
  st = restore();
  $("#pr-color-field").addEventListener("click", (e) => pickColor(e, false));
  $("#pr-achromatic").addEventListener("click", (e) => pickColor(e, true));
  const track = $("#pr-size-track");
  track.addEventListener("pointerdown", (e) => {
    dragging = true;
    track.setPointerCapture(e.pointerId);
    setSize(sizeFromEvent(e));
  });
  track.addEventListener("pointermove", (e) => { if (dragging) setSize(sizeFromEvent(e)); });
  const release = () => { if (dragging) { dragging = false; commitSizeSelection(); } };
  track.addEventListener("pointerup", release);
  track.addEventListener("pointercancel", release);
  track.addEventListener("keydown", (e) => {
    if (typeof st.cur.value !== "number") return;      // 손잡이가 생기기 전에는 키로 값을 만들지 않는다
    const d = { ArrowLeft: -0.01, ArrowDown: -0.01, ArrowRight: 0.01, ArrowUp: 0.01 }[e.key];
    if (d === undefined) return;
    e.preventDefault();
    if (!e.repeat) setSize(st.cur.value + d);
  });
  track.addEventListener("keyup", (e) => {
    if (typeof st.cur.value === "number" && ["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"].includes(e.key)) commitSizeSelection();
  });
  $("#pr-next").addEventListener("click", onNext);
  $("#pr-back").addEventListener("click", onBack);
  $("#pr-step").hidden = false;
  render();
});
