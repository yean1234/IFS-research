"""G81 찾은 문제 1: 후보 화면에서 안개(mist) 후보를 마지막으로 그린 뒤 만든 물체(생성 GLB) 후보를 그리면 빠지던 문제.

원인: stage.js candidateNode가 setAsset(GLB)을 apply(overrides)보다 먼저 불렀다. Unity SetFormAssetJson은 지금 얹힌 덮어쓰기로
다시 로드하므로(PreviewBridge.SetFormAssetJson → _stage.Reapply(_stage.Overrides)) 직전 후보의 {"form.type":"mist"} 위에 GLB를
씌우려다 mist_form으로 거부했고(SceneLoader.ApplyFormAsset), 화면은 그 후보를 asset_failed로 뺐다.

실제 stage.js를 헤드리스 Chrome에서 돌린다(서버·LLM 없음, 같은 출처 정적 파일만, 외부 요청 없음). 대사·스펙은 합성이다.
- 가짜 Unity 다리: Unity의 순서 규칙(GLB는 지금 덮어쓰기 위에 씌움, 안개면 거부)을 흉내 낸다. Chrome이 없으면 건너뛴다.
- 실제 Unity WebGL 빌드: 저장소 밖 빌드(experiment.toml [preview] webgl_dir 또는 IFS_WEBGL_DIR)가 있을 때만.
"""
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import tomllib
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "chatbot" / "ifs_chatbot" / "web"
SID = "SYN-G81-ORDER"
MIST = {"form.type": "mist"}


def _chrome() -> str | None:
    cands = [os.environ.get("IFS_CHROME"), shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
    return next((c for c in cands if c and Path(c).is_file()), None)


def _webgl_dir() -> Path | None:
    env = os.environ.get("IFS_WEBGL_DIR")
    if env:
        p = Path(env)
    else:
        cfg = tomllib.loads((REPO_ROOT / "chatbot" / "config" / "experiment.toml").read_text(encoding="utf-8"))
        rel = (cfg.get("preview") or {}).get("webgl_dir") or ""
        if not rel:
            return None
        p = (REPO_ROOT / "chatbot" / rel).resolve()
    return p if (p / "index.html").is_file() and (p / "Build").is_dir() else None


CHROME = _chrome()
pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome 없음(IFS_CHROME으로 지정 가능)")


def cube_glb() -> bytes:
    """GlbMeshReader.Write와 같은 최소 GLB(합성 정육면체 하나)."""
    pos = [x for v in [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
                       (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)] for x in v]
    tri = [0, 2, 1, 0, 3, 2, 4, 5, 6, 4, 6, 7, 0, 1, 5, 0, 5, 4, 3, 7, 6, 3, 6, 2, 0, 4, 7, 0, 7, 3, 1, 2, 6, 1, 6, 5]
    binp = struct.pack(f"<{len(pos)}f", *pos)
    bini = struct.pack(f"<{len(tri)}I", *tri)
    js = json.dumps({
        "asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "buffers": [{"byteLength": len(binp) + len(bini)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(binp)},
                        {"buffer": 0, "byteOffset": len(binp), "byteLength": len(bini)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": [-.5] * 3, "max": [.5] * 3},
                      {"bufferView": 1, "componentType": 5125, "count": len(tri), "type": "SCALAR"}],
    }, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    body = binp + bini
    total = 12 + 8 + len(js) + 8 + len(body)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(body), 0x004E4942) + body)


# 가짜 Unity 다리: 실제 빌드의 window.ifsPreview와 같은 약속(Promise, 응답 kind)과 Unity가 지키는 순서 규칙만 흉내 낸다.
#   applyOverrides: 덮어쓰기를 바꿔 다시 로드(GLB가 얹혀 있고 안개면 Unity처럼 조용히 절차 모형으로 둠 — 오류 아님)
#   setFormAsset(a): 지금 덮어쓰기로 다시 로드하며 GLB를 씌움. 그때 형태가 안개면 GLB를 걷고 mist_form 오류(Unity SceneLoader와 같음)
FAKE_UNITY = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="icon" href="data:,"></head><body><script>
const st = { spec: null, ov: {}, asset: null }; window.__log = [];
const form = () => (st.ov["form.type"] !== undefined ? st.ov["form.type"] : (st.spec && st.spec.form && st.spec.form.type)) || "blob";
const PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
window.ifsPreview = {
  ready: Promise.resolve(), unityInfo: { graphicsDevice: "fake" },
  load(spec) { st.spec = typeof spec === "string" ? JSON.parse(spec) : spec; st.ov = {}; __log.push(["load"]); return Promise.resolve({ kind: "load" }); },
  applyOverrides(ov) { st.ov = ov || {}; __log.push(["overrides", JSON.stringify(st.ov)]); return Promise.resolve({ kind: "overrides", overrides: st.ov }); },
  setFormAsset(a) {
    __log.push(["formAsset", a ? a.glbSha256 : null, form()]);
    if (!a) { st.asset = null; return Promise.resolve({ kind: "formAsset", formAsset: null }); }
    if (form() === "mist") { st.asset = null; return Promise.reject({ kind: "formAsset", message: "생성 형태를 그리지 못했습니다: mist_form", details: [] }); }
    st.asset = a.glbSha256; return Promise.resolve({ kind: "formAsset", overrides: st.ov, formAsset: { status: "applied" } });
  },
  setFrozen() { return Promise.resolve(); },
  setAutoRotate() { return Promise.resolve(); },
  capture(o) { __log.push(["capture", o.id, form(), st.asset]); return Promise.resolve({ id: o.id, png: PNG }); },
};
</script></body></html>"""

# 하네스: app.js의 도우미($·el·api·toast·kv)만 최소로 두고 실제 stage.js를 읽어 WebGL 후보 칸을 차례로 그린다.
# 1회차 = 처음 후보 화면(0번 blob, 1번 mist), 2회차 = [맞는 게 없어요] 뒤 만든 물체가 맨 앞에 더해진 화면(나머지는 찍어 둔 그림 재사용),
# 3회차 = 생성 GLB 뒤 GLB 없는 안개 후보(바뀌지 않아야 하는 경로).
HARNESS = r"""<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="icon" href="data:,"></head><body>
<div id="stage"></div><ul id="grid"></ul><div id="toast" hidden></div>
<script>
const $ = (s) => document.querySelector(s);
const el = (tag, attrs = {}, ...children) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v; else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
  }
  for (const c of children) if (c != null) n.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return n;
};
const kv = () => el("dl");
function toast(m) { window.__toasts = (window.__toasts || []).concat([String(m)]); }
const posted = [];
async function api(method, path, body) {
  if (path.endsWith("/scene")) return { spec: await (await fetch("/h/spec.json")).json() };
  if (path.endsWith("/preview/client")) {
    posted.push(body);
    const S = window.ifsStage._state;
    return Object.assign({}, S.view, { candidates: [] });   // 서버가 그 후보를 뺀 뷰(여기서는 빈 화면)
  }
  return {};
}
</script>
<script src="/h/stage.js"></script>
<script>
(async () => {
  const P = JSON.parse(decodeURIComponent(location.hash.slice(1)));
  const W = window.ifsStage._webgl, S = window.ifsStage._state;
  S.sid = P.sid; S.cfg = { previewWarmup: [], phrases: {} };
  S.view = { stage: "selecting", candidates: [], preview: { mode: "webgl", webglUrl: P.webglUrl,
             webglRequestTimeoutMs: P.requestMs, webglReadyTimeoutMs: P.readyMs } };
  const asset = { assetId: "g-syn-cube", glbSha256: P.sha, glbUrl: "/h/asset.glb" };
  const out = { rounds: [], posted, errors: [] };
  window.addEventListener("error", (e) => out.errors.push(String(e.message)));
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function round(list) {
    const imgs = list.map(([id, ov, a]) => {
      const li = el("li", { class: "cand" }, W.candidateNode(id, ov, a ? asset : null));
      $("#grid").append(li);
      return [id, li.querySelector("img")];
    });
    const t0 = performance.now();
    const failedFor = (id) => posted.some((p) => p.event === "asset_failed" && p.webgl && p.webgl.candidateId === id);
    while (performance.now() - t0 < P.roundMs) {
      if (W.failed || imgs.every(([id, img]) => img.src || failedFor(id))) break;
      await sleep(100);
    }
    await W.q; await sleep(300);                   // 큐와 asset_failed 알림이 끝나기를 기다림
    out.rounds.push({ ms: Math.round(performance.now() - t0), drawn: Object.fromEntries(imgs.map(([id, img]) => [id, !!img.src])),
                      asset: W.asset, applied: W.applied, failed: W.failed });
  }
  try {
    await round([["c0", {}, false], ["c1", { "form.type": "mist" }, false]]);
    await round([["g0", {}, true], ["c0", {}, false], ["c1", { "form.type": "mist" }, false]]);
    await round([["c3", { "form.type": "mist" }, false]]);
  } catch (e) { out.errors.push(String(e && e.stack || e)); }
  const fw = W.frame && W.frame.contentWindow;
  out.bridgeLog = (fw && fw.__log) || null;
  await fetch("/result", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(out) });
})();
</script></body></html>"""


class _Site:
    """정적 파일만 내보내는 작은 서버(127.0.0.1, 빈 포트). /result로 하네스 결과를 받는다."""

    def __init__(self, spec: dict, glb: bytes, webgl_dir: Path | None):
        self.result = None
        self.got = threading.Event()
        site = self
        files = {
            "/h/index.html": (HARNESS.encode(), "text/html; charset=utf-8"),
            "/h/stage.js": ((WEB / "stage.js").read_bytes(), "text/javascript; charset=utf-8"),
            "/h/spec.json": (json.dumps(spec, ensure_ascii=False).encode(), "application/json"),
            "/h/asset.glb": (glb, "model/gltf-binary"),
            "/fake/index.html": (FAKE_UNITY.encode(), "text/html; charset=utf-8"),
        }
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".wasm": "application/wasm",
                 ".data": "application/octet-stream", ".json": "application/json"}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b"", ctype="text/plain"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = self.path.split("?", 1)[0].split("#", 1)[0]
                if path in files:
                    return self._send(200, *files[path])
                if webgl_dir is not None and path.startswith("/unity/"):
                    p = (webgl_dir / path[len("/unity/"):]).resolve()
                    if webgl_dir.resolve() in p.parents and p.is_file():
                        return self._send(200, p.read_bytes(), types.get(p.suffix, "application/octet-stream"))
                self._send(404)

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                data = self.rfile.read(n)
                if self.path == "/result":
                    site.result = json.loads(data)
                    site.got.set()
                self._send(200, b"{}", "application/json")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def run_harness(spec: dict, webgl_url: str, webgl_dir: Path | None = None, wait_s: float = 60, ready_ms: int = 30000,
                request_ms: int = 15000, round_ms: int = 20000) -> dict:
    glb = cube_glb()
    site = _Site(spec, glb, webgl_dir)
    prof = tempfile.mkdtemp(prefix="ifs-g81-order-")
    params = {"sid": SID, "webglUrl": webgl_url, "sha": sha256(glb).hexdigest(), "readyMs": ready_ms,
              "requestMs": request_ms, "roundMs": round_ms}
    url = f"{site.base}/h/index.html#" + json.dumps(params).replace(" ", "")
    proc = subprocess.Popen([CHROME, "--headless=new", f"--user-data-dir={prof}", "--no-first-run", "--no-default-browser-check",
                             "--disable-extensions", "--disable-background-networking", "--disable-component-update",
                             "--disable-sync", "--window-size=1024,768", url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert site.got.wait(wait_s), "하네스가 결과를 보내지 않음"
        return site.result
    finally:
        if os.name == "nt":       # 띄운 Chrome(과 그 자식)만 끈다
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        else:
            proc.kill()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        site.close()
        shutil.rmtree(prof, ignore_errors=True)


def synthetic_spec() -> dict:
    """합성 문장 '돌덩이예요'(형태를 말하지 않음 → form.type 비어 있음)를 실험 설정의 매퍼로 만든 스펙."""
    from ifs_chatbot.config import load_config
    from ifs_chatbot.controller import Runtime
    logs = tempfile.mkdtemp(prefix="ifs-g81-order-logs-")
    cfg = load_config("experiment").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none",
                                                       "session.log_dir": logs, "preview.mode": "none"})
    spec = Runtime(cfg).scene_builder.build("돌덩이예요", session_id=SID, participant_id="SYN")
    spec = spec if isinstance(spec, dict) else spec.to_dict()
    assert spec["form"]["type"] is None
    return spec


def canon(ov: dict) -> str:
    """stage.js canon()과 같은 정규형(키 정렬, 공백 없음)."""
    return json.dumps([list(kv) for kv in sorted(ov.items())], separators=(",", ":"), ensure_ascii=False)


def _check(r: dict):
    assert not r["errors"], r["errors"]
    r1, r2, r3 = r["rounds"]
    assert r1["failed"] is None and r1["drawn"] == {"c0": True, "c1": True} and r1["applied"] == canon(MIST)
    # 만든 물체 후보가 빠지지 않는다(asset_failed 없음)
    assert [p for p in r["posted"] if p.get("event") == "asset_failed"] == []
    assert r2["failed"] is None and r2["drawn"] == {"g0": True, "c0": True, "c1": True}
    assert r2["asset"] == sha256(cube_glb()).hexdigest() and r2["applied"] == canon({})
    # 생성 뒤 GLB 없는 안개 후보: 전과 같이 GLB를 걷고 안개로 그린다
    assert r3["failed"] is None and r3["drawn"] == {"c3": True} and r3["asset"] == ""
    assert r3["applied"] == canon(MIST)


def test_fake_bridge_asset_candidate_after_mist_candidate():
    r = run_harness({"meta": {"sessionId": SID}, "form": {"type": None}}, "/fake/index.html")
    _check(r)
    log = r["bridgeLog"]
    caps = {e[1].split("-", 1)[1]: (e[2], e[3]) for e in log if e[0] == "capture"}
    sha = sha256(cube_glb()).hexdigest()
    assert caps == {"c0": ("blob", None), "c1": ("mist", None), "g0": ("blob", sha), "c3": ("mist", None)}
    # GLB를 씌우는 순간 Unity의 형태는 안개가 아니다(덮어쓰기를 먼저 {}로 되돌림)
    assert [e for e in log if e[0] == "formAsset" and e[1]] == [["formAsset", sha, "blob"]]
    i_ov = max(i for i, e in enumerate(log) if e == ["overrides", "{}"] and i < log.index(["formAsset", sha, "blob"]))
    assert all(e[0] != "overrides" for e in log[i_ov + 1:log.index(["formAsset", sha, "blob"])])
    # GLB 없는 후보는 전과 같은 순서: GLB 걷기 → 덮어쓰기
    after = log[log.index(["formAsset", sha, "blob"]) + 1:]
    assert after[0][:2] == ["capture", "q3-g0"]
    assert after[1:3] == [["formAsset", None, "blob"], ["overrides", json.dumps({"form.type": "mist"}, separators=(",", ":"))]]


WEBGL_DIR = _webgl_dir()


@pytest.mark.skipif(WEBGL_DIR is None, reason="Unity WebGL 미리보기 빌드 없음(experiment.toml webgl_dir 또는 IFS_WEBGL_DIR)")
def test_real_webgl_asset_candidate_after_mist_candidate():
    r = run_harness(synthetic_spec(), "/unity/index.html", WEBGL_DIR, wait_s=240, ready_ms=120000, request_ms=60000,
                    round_ms=150000)
    _check(r)
