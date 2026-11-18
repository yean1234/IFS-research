// 보기 전 보고 과제 (shared/protocol/prereport_task.v0.json, 기록 형식 shared/schemas/prereport.v0.json).
// 면담 밖의 고정 문구 과제다. LLM을 부르지 않는다. 외부 라이브러리 없음(연구실 오프라인 사용).
// ③(지금도 정해진 것이 없다)을 고르면 값 고르기를 보이지 않고 값을 비워 둔다.
"use strict";

const $ = (sel) => document.querySelector(sel);
const sid = new URLSearchParams(location.search).get("session") || "";
const COMMITTED = ["from_start", "when_asked"];

const st = {
  task: null,
  order: [],
  idx: 0,
  answers: {},           // attr → {commitment, value, nSelections}
  cur: null,             // 지금 문항의 답(아직 [확인] 전)
  busy: false,
};

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = typeof d === "string" ? d : d && d.message ? `${d.message} ${(d.problems || []).join(" / ")}` : `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return data;
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 5000);
}

function showMessage(text) {
  $("#pr-step").hidden = true;
  const m = $("#pr-message");
  m.textContent = text;
  m.hidden = false;
}

// ── 색: 색상각 × 밝기 면(채도 고정) ───────────────────────────────────────────
function hslToRgb(h, s, l) {
  const a = s * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h * 12) % 12;
    return l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [f(0), f(8), f(4)].map((x) => Math.round(x * 255));
}

function colorCfg() {
  const c = st.task.colorField;
  return { s: c.saturation, top: c.lightnessTop, bottom: c.lightnessBottom };
}

function drawColorField() {
  const cv = $("#pr-color-field");
  const ctx = cv.getContext("2d");
  const { s, top, bottom } = colorCfg();
  const img = ctx.createImageData(cv.width, cv.height);
  for (let y = 0; y < cv.height; y++) {
    const l = top - (y / (cv.height - 1)) * (top - bottom);
    for (let x = 0; x < cv.width; x++) {
      const [r, g, b] = hslToRgb(x / cv.width, s, l);
      const i = (y * cv.width + x) * 4;
      img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const v = st.cur && st.cur.value;
  if (v && typeof v === "object") {
    const x = v.h * cv.width;
    const y = ((top - v.l) / (top - bottom)) * (cv.height - 1);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffffff";
    ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = "#000000";
    ctx.beginPath(); ctx.arc(x, y, 11, 0, Math.PI * 2); ctx.stroke();
  }
}

function onColorClick(ev) {
  const cv = $("#pr-color-field");
  const rect = cv.getBoundingClientRect();
  const fx = Math.min(Math.max((ev.clientX - rect.left) / rect.width, 0), 1);
  const fy = Math.min(Math.max((ev.clientY - rect.top) / rect.height, 0), 1);
  const { top, bottom } = colorCfg();
  const round = (x) => Math.round(x * 10000) / 10000;
  st.cur.value = { h: round(Math.min(fx, 0.9999)), l: round(top - fy * (top - bottom)) };
  st.cur.nSelections += 1;
  drawColorField();
  updateNext();
}

// ── 크기: 로그 척도 막대 + 서 있는 사람 윤곽 옆의 중립 원 ─────────────────────
function sizeDiameterM(s) {
  const c = st.task.sizeSlider;
  return c.baseDiameterM * Math.pow(2, (s - 0.5) * 4);
}

function drawSizeView() {
  const cv = $("#pr-size-view");
  const ctx = cv.getContext("2d");
  const ink = getComputedStyle(document.documentElement).getPropertyValue("--ink-soft").trim() || "#5b6b6e";
  ctx.clearRect(0, 0, cv.width, cv.height);
  const c = st.task.sizeSlider;
  const maxD = c.baseDiameterM * 4;
  const worldH = Math.max(c.figureHeightM, maxD) * 1.08;
  const ppm = (cv.height - 20) / worldH;
  const ground = cv.height - 10;
  ctx.strokeStyle = ink; ctx.fillStyle = ink; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(10, ground); ctx.lineTo(cv.width - 10, ground); ctx.stroke();

  // 서 있는 사람 윤곽(크기 가늠용, 고정)
  const H = c.figureHeightM * ppm;
  const fx = 90;
  const head = H * 0.065;
  ctx.globalAlpha = 0.55;
  ctx.beginPath(); ctx.arc(fx, ground - H + head, head, 0, Math.PI * 2); ctx.fill();
  const shoulder = ground - H + head * 2.3;
  const hip = ground - H * 0.47;
  const halfW = H * 0.13;
  ctx.beginPath();
  ctx.moveTo(fx - halfW, shoulder); ctx.lineTo(fx + halfW, shoulder);
  ctx.lineTo(fx + halfW * 0.8, hip); ctx.lineTo(fx + halfW * 0.55, ground);
  ctx.lineTo(fx + halfW * 0.12, ground); ctx.lineTo(fx, hip + H * 0.05);
  ctx.lineTo(fx - halfW * 0.12, ground); ctx.lineTo(fx - halfW * 0.55, ground);
  ctx.lineTo(fx - halfW * 0.8, hip); ctx.closePath(); ctx.fill();
  ctx.globalAlpha = 1;

  // 중립 원(윤곽만). 한 번 움직이기 전에는 그리지 않는다
  if (st.cur && typeof st.cur.value === "number") {
    const d = sizeDiameterM(st.cur.value) * ppm;
    const cx = Math.min(cv.width - 14 - d / 2, Math.max(fx + halfW + 30 + d / 2, (cv.width + fx) / 2));
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(cx, ground - d / 2, d / 2, 0, Math.PI * 2); ctx.stroke();
  }
}

function onSizeInput() {
  st.cur.value = Number($("#pr-size-slider").value);
  st.cur.touched = true;
  drawSizeView();
  updateNext();
}

function onSizeChange() {
  // 손을 뗄 때(또는 키 한 번) 고른 것으로 센다
  st.cur.value = Number($("#pr-size-slider").value);
  st.cur.nSelections += 1;
  drawSizeView();
  updateNext();
}

// ── 문항 진행 ──────────────────────────────────────────────────────────────
function attrInfo() {
  const a = st.order[st.idx];
  return { id: a, ...st.task.attributes[a] };
}

function needsValue() {
  const info = attrInfo();
  return info.valuePick && st.cur.commitment && COMMITTED.includes(st.cur.commitment);
}

function updateNext() {
  let ok = !!st.cur.commitment;
  if (ok && needsValue()) ok = st.cur.value !== null && st.cur.value !== undefined && st.cur.nSelections > 0;
  $("#pr-next").disabled = !ok || st.busy;
}

function choose(optId) {
  st.cur.commitment = optId;
  document.querySelectorAll("#pr-options button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.id === optId)));
  const info = attrInfo();
  const show = needsValue();
  if (!show) st.cur.value = null;     // ③: 값을 남기지 않는다(고른 횟수는 남김)
  $("#pr-color").hidden = !(show && info.valuePick === "color");
  $("#pr-size").hidden = !(show && info.valuePick === "size");
  if (show && info.valuePick === "color") drawColorField();
  if (show && info.valuePick === "size") {
    if (!st.cur.touched) $("#pr-size-slider").value = String(st.task.sizeSlider.start);
    drawSizeView();
  }
  updateNext();
}

function renderStep() {
  const info = attrInfo();
  const t = st.task;
  st.cur = { commitment: null, value: null, nSelections: 0, touched: false };
  $("#pr-intro").textContent = st.idx === 0 ? t.fixedPhrases.intro.text : "";
  $("#pr-intro").hidden = st.idx !== 0;
  $("#pr-question").textContent = info.question.text;
  const opts = $("#pr-options");
  opts.replaceChildren();
  for (const o of t.commitmentOptions) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pr-option";
    b.dataset.id = o.id;
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", "false");
    b.textContent = `${o.mark} ${o.label}`;
    b.addEventListener("click", () => choose(o.id));
    opts.append(b);
  }
  $("#pr-color").hidden = true;
  $("#pr-size").hidden = true;
  $("#pr-color-text").textContent = t.fixedPhrases.color_pick.text;
  $("#pr-size-text").textContent = t.fixedPhrases.size_pick.text;
  $("#pr-next").textContent = t.fixedPhrases.next_button.text;
  const prog = $("#pr-progress");
  prog.textContent = `${st.idx + 1} / ${st.order.length}`;
  prog.hidden = false;
  updateNext();
}

function answerFor(attr, cur) {
  const pick = st.task.attributes[attr].valuePick;
  if (!pick) return { commitment: cur.commitment };
  const committed = COMMITTED.includes(cur.commitment);
  return {
    commitment: cur.commitment,
    value: committed ? cur.value : null,
    method: pick === "color" ? st.task.colorField.method : st.task.sizeSlider.method,
    nSelections: cur.nSelections,
  };
}

async function next() {
  if ($("#pr-next").disabled) return;
  const attr = st.order[st.idx];
  st.answers[attr] = answerFor(attr, st.cur);
  if (st.idx + 1 < st.order.length) {
    st.idx += 1;
    renderStep();
    window.scrollTo(0, 0);
    return;
  }
  st.busy = true;
  updateNext();
  try {
    await api("POST", `/api/sessions/${encodeURIComponent(sid)}/prereport`, { attributes: st.answers });
    $("#pr-progress").hidden = true;
    showMessage(st.task.fixedPhrases.done.text);
  } catch (e) {
    toast(e.message);
    if (e.status === 409) showMessage(e.message);
  } finally {
    st.busy = false;
    if (!$("#pr-step").hidden) updateNext();
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  $("#pr-session").textContent = sid ? `세션 ${sid}` : "";
  try {
    st.task = await api("GET", "/api/prereport/task");
  } catch (e) {
    return showMessage(`과제 문구를 읽지 못했습니다: ${e.message}`);
  }
  if (!sid) return showMessage(st.task.fixedPhrases.not_ready.text);
  try {
    const s = await api("GET", `/api/sessions/${encodeURIComponent(sid)}/prereport`);
    if (s.submitted) return showMessage("이 세션의 보기 전 보고는 이미 받았습니다.");
    if (!s.available) return showMessage(`${st.task.fixedPhrases.not_ready.text}${s.reason ? ` (${s.reason})` : ""}`);
  } catch (e) {
    return showMessage(e.message);
  }
  st.order = st.task.attributeOrder;
  $("#pr-color-field").addEventListener("click", onColorClick);
  $("#pr-size-slider").addEventListener("input", onSizeInput);
  $("#pr-size-slider").addEventListener("change", onSizeChange);
  $("#pr-next").addEventListener("click", next);
  $("#pr-step").hidden = false;
  renderStep();
});
