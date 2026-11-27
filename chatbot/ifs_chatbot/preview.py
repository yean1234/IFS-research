"""형상 미리보기 어댑터 (D5, 결정 G12·G25). v4 설정은 "webgl"이고, 안 되면 "image"(G25 경로) → "none"(글 요약) 순으로 내려간다.

모드(config [preview] mode):
- "image": Unity Windows 미리보기 플레이어(IFSPreview.exe, PreviewQueue)를 상주시켜 spec JSON + 덮어쓰기 JSON을 넣고
           PNG를 받는다. 플레이어는 저장소 밖 빌드 폴더(설정값 image_player). 서버 시작 때(start_on_launch) 또는 첫 요청 때 띄운다.
           플레이어가 없거나, 뜨지 않거나, 요청 중에 죽으면 "none"으로 자동 대체하고 그 사실을 info()·세션 로그·화면에 남긴다.
           image_player = "fake"는 테스트용 가짜 렌더러(서버 안에서 그린 PNG — Unity 렌더가 아님)다.
- "webgl": 로컬에서 내보낸 Unity WebGL 빌드(webgl_dir/index.html)를 웹 화면 iframe에 띄운다(web/stage.js 어댑터,
           브리지: window.ifsPreview.load(spec) · applyOverrides(obj) · capture(...) · setFrozen(bool)).
           image_player가 있으면 그것을 예비로 준비해 둔다(띄우지는 않음). 서버 쪽에서 빌드 폴더가 없으면 처음부터 image
           (예비도 없으면 none). 브라우저 쪽에서 WebGL2가 없거나 Unity가 뜨지 않거나 요청이 실패하면 stage.js가 알리고
           그 세션만 image(예비가 없거나 실패했으면 none)로 내려간다(selection.SelectionFlow.client_preview).
- "none":  미리보기 없이 후보의 속성 요약 글만(테스트·시나리오용).
외부로 나가는 요청이 없다(원칙 5). PNG와 요청 폴더는 참여자 자료에서 나온 것이라 git 밖(<log_dir>/preview-queue).
"""
from __future__ import annotations

import colorsys
import json
import logging
import math
import os
import struct
import subprocess
import sys
import threading
import time
import zlib
from collections import OrderedDict
from pathlib import Path

from .candidates import canonical, effective_params, sha256_text

log = logging.getLogger("ifs_chatbot.preview")


def _asset_bytes(asset: dict) -> bytes:
    """asset의 GLB 바이트(sha256 다시 확인). 파일이 없거나 바뀌었으면 PreviewAssetError."""
    import hashlib
    try:
        raw = Path(asset["glbPath"]).read_bytes()
    except OSError as exc:
        raise PreviewAssetError(f"GLB 파일을 읽지 못함: {exc}") from exc
    if hashlib.sha256(raw).hexdigest() != asset["glbSha256"]:
        raise PreviewAssetError("GLB 파일이 제시한 뒤 바뀜(sha256 다름)")
    return raw
MODES = ("webgl", "image", "none")


class PreviewError(RuntimeError):
    """플레이어가 없거나 응답하지 않음 등. 서비스는 이것을 받으면 none으로 대체한다."""


class PreviewAssetError(PreviewError):
    """G62: 생성 형태 GLB 하나를 그리지 못함(플레이어 자체는 정상). 서비스는 image 경로를 닫지 않고 그대로 올린다 —
    부른 쪽(SelectionFlow)이 그 생성 후보를 후보에서 빼고 사유를 기록한다(절차 메시 모습으로 생성 후보를 보이지 않는다)."""


# ── PNG (외부 라이브러리 없이) ─────────────────────────────────────────────────
def png_bytes(width: int, height: int, rgb_rows: list[bytes], text: dict | None = None) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + row for row in rgb_rows)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    for k, v in (text or {}).items():
        out += chunk(b"tEXt", k.encode("latin-1") + b"\x00" + v.encode("latin-1", "replace"))
    return out + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def fake_png(spec: dict, overrides: dict, defaults: dict, width: int = 160, height: int = 120) -> bytes:
    """테스트용 가짜 그림. 같은 입력 → 같은 바이트. 크기·색·밝기·투명도·형태가 그림에 드러나 덮어쓰기마다 달라진다.
    Unity 렌더가 아니다(PNG tEXt에 'fake'를 적는다). 연구 자료로 쓰지 않는다."""
    p = effective_params(spec, defaults, overrides)
    r, g, b = colorsys.hls_to_rgb(p["material.color.h"], p["material.color.l"], p["material.color.s"])
    gain = 0.4 + 1.2 * p["material.brightness"]
    col = [min(1.0, c * gain) for c in (r, g, b)]
    alpha = p["material.opacity"] * (0.5 if p["form.type"] == "mist" else 1.0)
    bg = 0.74
    radius = min(width, height) * 0.22 * (2.0 ** ((p["layout.size"] - 0.5) * 2.0))
    cx, cy = width / 2, height / 2
    form = p["form.type"]
    blobs = [(cx, cy, radius)]
    if form == "fragments":
        blobs = [(cx + radius * 0.9 * math.cos(a), cy + radius * 0.9 * math.sin(a), radius * 0.35)
                 for a in (0.3, 1.9, 3.4, 4.9)]
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            a = 0.0
            for bx, by, br in blobs:
                d = math.hypot(x - bx, y - by)
                if form == "shell":
                    hit = br * 0.7 <= d <= br
                elif form == "mist":
                    hit = d <= br * 1.2
                    a = max(a, alpha * max(0.0, 1 - d / (br * 1.2))) if hit else a
                    continue
                else:
                    hit = d <= br
                if hit:
                    a = max(a, alpha)
            if p["material.roughness"] < 0.3 and form != "mist" and math.hypot(x - cx + radius * 0.35, y - cy + radius * 0.35) < radius * 0.15:
                px = [1.0, 1.0, 1.0]
                a = max(a, 0.9)
            else:
                px = col
            row += bytes(int(255 * ((1 - a) * bg + a * c)) for c in px)
        rows.append(bytes(row))
    return png_bytes(width, height, rows, {"Software": "ifs-chatbot fake preview (NOT Unity)"})


def fake_asset_png(spec: dict, overrides: dict, defaults: dict, glb: bytes, width: int = 160, height: int = 120) -> bytes:
    """테스트용 가짜 그림(생성 형태): GLB 정점을 정면(x, y)으로 투영한 점들로 윤곽을 찍는다. 색·밝기·투명도는 스펙 값(fake_png와 같은 식),
    크기는 가장 긴 변을 절차 형상 지름에 맞춘다. 같은 입력 → 같은 바이트. Unity 렌더가 아니다."""
    from .form_assets import GlbError, read_glb_positions
    try:
        pos, _ = read_glb_positions(glb)
    except GlbError as exc:
        raise PreviewAssetError(f"GLB를 읽지 못함: {exc}") from exc
    p = effective_params(spec, defaults, overrides)
    r, g, b = colorsys.hls_to_rgb(p["material.color.h"], p["material.color.l"], p["material.color.s"])
    gain = 0.4 + 1.2 * p["material.brightness"]
    col = [min(1.0, c * gain) for c in (r, g, b)]
    alpha = p["material.opacity"]
    diameter = 2 * min(width, height) * 0.22 * (2.0 ** ((p["layout.size"] - 0.5) * 2.0))
    xs, ys, zs = [q[0] for q in pos], [q[1] for q in pos], [q[2] for q in pos]
    longest = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    k = diameter / longest
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    hit = set()
    for x, y, _z in pos:
        px, py = int(round(width / 2 + (x - cx) * k)), int(round(height / 2 - (y - cy) * k))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                hit.add((px + dx, py + dy))
    bg = 0.74
    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            a = alpha if (x, y) in hit else 0.0
            row += bytes(int(255 * ((1 - a) * bg + a * c)) for c in col)
        rows.append(bytes(row))
    return png_bytes(width, height, rows, {"Software": "ifs-chatbot fake preview (NOT Unity)", "Comment": "form asset"})


# ── 렌더러 ──────────────────────────────────────────────────────────────────
class FakeRenderer:
    name = "fake"

    def __init__(self, defaults: dict, width: int = 160, height: int = 120):
        self.defaults, self.width, self.height = defaults, width, height
        self.calls = 0

    def render(self, spec_json: str, overrides: dict, asset: dict | None = None) -> bytes:
        self.calls += 1
        if asset is not None:
            return fake_asset_png(json.loads(spec_json), overrides, self.defaults, _asset_bytes(asset), self.width, self.height)
        return fake_png(json.loads(spec_json), overrides, self.defaults, self.width, self.height)

    def info(self) -> dict:
        return {"renderer": "fake", "note": "테스트용 가짜 렌더러 — Unity 렌더가 아님"}

    def close(self) -> None:
        pass


class UnityQueueRenderer:
    """상주 Unity 미리보기 플레이어(PreviewQueue, unity/Assets/IFS/Runtime/Preview/PreviewQueue.cs)에 폴더로 요청한다.
    요청: <queue>/<이름>.req.json = {"specJson", "overrides"(평평한 객체), "width", "height", "backgrounds":["scene"], "out"}
    응답: <out>_scene.png + <queue>/<이름>.done.json. 같은 플레이어에 한 번에 하나씩 보낸다(잠금)."""

    name = "unity-queue"

    def __init__(self, command: list[str], queue_dir: Path, width: int = 320, height: int = 240,
                 start_timeout_s: float = 60.0, request_timeout_s: float = 20.0):
        self.command = list(command)
        self.queue_dir = Path(queue_dir)
        self.width, self.height = width, height
        self.start_timeout_s, self.request_timeout_s = start_timeout_s, request_timeout_s
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.seq = 0
        self.started_at: float | None = None
        self.startup_s: float | None = None
        self.renders = 0
        self.last_rtt_ms: float | None = None

    def _alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> None:
        if self._alive():
            return
        if self.proc is not None:   # 띄운 적이 있는데 꺼졌다 → 몰래 다시 띄우지 않고 실패로 알린다(서비스가 none으로 대체)
            raise PreviewError(f"플레이어가 꺼져 있음(종료 코드 {self.proc.returncode})")
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        for f in self.queue_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                except OSError:
                    pass
        cmd = self.command + ["-batchmode", "-ifsPreviewQueue", str(self.queue_dir),
                              "-logFile", str(self.queue_dir / "player.log")]
        t0 = time.perf_counter()
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise PreviewError(f"플레이어를 실행하지 못함: {exc}") from exc
        ready = self.queue_dir / "ready.json"
        while not ready.exists():
            if self.proc.poll() is not None:
                raise PreviewError(f"플레이어가 시작 중에 끝남(종료 코드 {self.proc.returncode})")
            if time.perf_counter() - t0 > self.start_timeout_s:
                self.close()
                raise PreviewError(f"플레이어가 {self.start_timeout_s:.0f}초 안에 준비되지 않음")
            time.sleep(0.01)
        self.startup_s = round(time.perf_counter() - t0, 3)
        self.started_at = time.time()
        log.info("미리보기 플레이어 준비(%.2fs): %s", self.startup_s, self.queue_dir)

    def render(self, spec_json: str, overrides: dict, asset: dict | None = None) -> bytes:
        with self.lock:
            self.start()
            self.seq += 1
            name = f"r{os.getpid()}_{self.seq:06d}"
            out_prefix = self.queue_dir / name
            done = self.queue_dir / f"{name}.done.json"
            png = Path(f"{out_prefix}_scene.png")
            body = {"specJson": spec_json, "overrides": overrides or {}, "width": self.width, "height": self.height,
                    "backgrounds": ["scene"], "out": str(out_prefix)}
            if asset is not None:       # G62: 생성 형태 GLB(플레이어가 sha256을 다시 확인하고 GlbMeshReader로 읽음)
                body["formAsset"] = {"assetId": asset["assetId"], "glb": str(asset["glbPath"]), "glbSha256": asset["glbSha256"]}
            tmp = self.queue_dir / f"{name}.tmp"
            tmp.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
            t0 = time.perf_counter()
            os.replace(tmp, self.queue_dir / f"{name}.req.json")
            while not done.exists():
                if not self._alive():
                    raise PreviewError("플레이어가 요청 중에 끝남")
                if time.perf_counter() - t0 > self.request_timeout_s:
                    raise PreviewError(f"플레이어가 {self.request_timeout_s:.0f}초 안에 응답하지 않음")
                time.sleep(0.003)
            result = None
            for _ in range(200):
                try:
                    result = json.loads(done.read_text(encoding="utf-8"))
                    break
                except (PermissionError, json.JSONDecodeError):
                    time.sleep(0.005)
            self.last_rtt_ms = round((time.perf_counter() - t0) * 1000, 2)
            if result is None:
                raise PreviewError("플레이어 응답 파일을 읽지 못함")
            try:
                if result.get("formAssetError"):
                    raise PreviewAssetError("생성 형태 GLB를 그리지 못함: " + str(result.get("formAssetError"))[:300])
                if not result.get("ok"):
                    raise PreviewError("플레이어가 그리지 못함: " + str(result.get("error"))[:300])
                if asset is not None and (result.get("formAsset") or {}).get("status") != "applied":
                    # G62 전에 빌드한 플레이어는 formAsset을 모르고 절차 메시로 그린다 → 그 그림을 생성 후보로 쓰지 않는다
                    raise PreviewAssetError("플레이어가 생성 형태를 적용했다고 알리지 않음(G62 코드로 다시 빌드해야 함)")
                data = png.read_bytes()
            finally:
                for f in (done, png):
                    try:
                        f.unlink()
                    except OSError:
                        pass
            self.renders += 1
            return data

    def info(self) -> dict:
        return {"renderer": "unity-queue", "command": [Path(self.command[-1]).name], "queueDir": str(self.queue_dir),
                "running": self._alive(), "pid": self.proc.pid if self._alive() else None,
                "startupSeconds": self.startup_s, "renders": self.renders, "lastRttMs": self.last_rtt_ms,
                "size": [self.width, self.height]}

    def close(self) -> None:
        if self.proc is None:
            return
        if self._alive():
            try:
                (self.queue_dir / "quit.req.json").write_text("{}", encoding="utf-8")
                self.proc.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
        if self._alive():
            self.proc.kill()
        self.proc = None


# ── 서비스 ──────────────────────────────────────────────────────────────────
class PreviewService:
    """설정을 읽어 실제로 쓸 모드를 정하고, 렌더 실패 시 none으로 대체한다.
    mode = 서버가 처음 내보내는 모드(세션마다 실제로 쓴 모드는 SelectionFlow가 따로 든다). image_ok = image 경로를
    지금 쓸 수 있는가(webgl 모드에서는 예비 경로)."""

    def __init__(self, cfg, log_dir: Path, base_dir: Path, defaults: dict):
        self.cfg = cfg
        self.requested = cfg.mode
        if cfg.mode not in MODES:
            raise ValueError(f"모르는 preview.mode: {cfg.mode} (webgl | image | none)")
        self.mode = "none"
        self.reason: str | None = None
        self.renderer = None
        self.webgl_dir: Path | None = None
        self.image_failed = False
        self.last_image_error: str | None = None
        self.events: list[dict] = []
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

        def resolve(p: str) -> Path:
            q = Path(p)
            return q if q.is_absolute() else (base_dir / q).resolve()

        def image_renderer():
            """(렌더러 | None, 없을 때 이유). 띄우지는 않는다."""
            player = cfg.image_player
            if player == "fake":
                return FakeRenderer(defaults), None
            if player and resolve(player).exists():
                exe = resolve(player)
                cmd = [sys.executable, str(exe)] if exe.suffix == ".py" else [str(exe)]
                qdir = resolve(cfg.queue_dir) if cfg.queue_dir else Path(log_dir) / "preview-queue"
                return UnityQueueRenderer(cmd, qdir, cfg.width, cfg.height, cfg.start_timeout_s, cfg.request_timeout_s), None
            return None, f"미리보기 플레이어가 없음({player or '경로 미설정'})"

        if cfg.mode == "webgl":
            d = resolve(cfg.webgl_dir) if cfg.webgl_dir else None
            self.renderer, why_no_image = image_renderer()       # 예비(image) 경로. 없으면 브라우저 실패 때 none
            if d is not None and (d / "index.html").exists():
                self.mode, self.webgl_dir = "webgl", d
                if self.renderer is None:
                    self._event("no_image_fallback", f"{why_no_image} — WebGL이 안 되면 글 요약으로 내려감")
            else:
                to = "image" if self.renderer is not None else "none"
                self.mode = to
                self.reason = (f"WebGL 빌드가 없음({cfg.webgl_dir or '경로 미설정'}/index.html) → {to}"
                               + ("" if self.renderer is not None else f"; {why_no_image}"))
        elif cfg.mode == "image":
            self.renderer, why_no_image = image_renderer()
            if self.renderer is not None:
                self.mode = "image"
            else:
                self.reason = f"{why_no_image} → none"
        if self.mode == "image" and cfg.start_on_launch and isinstance(self.renderer, UnityQueueRenderer):
            try:
                self.renderer.start()
            except PreviewError as exc:
                self._fail(str(exc))
        if self.reason and not self.image_failed:
            self._event("fallback", self.reason)

    @property
    def image_ok(self) -> bool:
        """image 경로(상주 플레이어 PNG)를 지금 쓸 수 있는가. 한 번 실패하면 이 서버 프로세스에서는 다시 쓰지 않는다."""
        return self.renderer is not None and not self.image_failed

    def fallback_target(self, current: str) -> str:
        """세션이 current 모드에서 실패했을 때 내려갈 모드: webgl → image(쓸 수 있으면) → none."""
        if current == "webgl" and self.image_ok:
            return "image"
        return "none"

    def _event(self, kind: str, detail: str) -> None:
        self.events.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "detail": detail})
        log.warning("[preview] %s: %s", kind, detail)

    def _fail(self, detail: str) -> None:
        self.image_failed = True
        why = f"미리보기 플레이어 오류 → none: {detail}"
        self.last_image_error = why
        if self.mode == "image":           # webgl이 기본이면 기본은 그대로 두고 예비(image)만 닫힘
            self.mode, self.reason = "none", why
            self._event("fallback", why)
        else:
            self._event("image_fallback_lost", why)
        if self.renderer is not None:
            try:
                self.renderer.close()
            except Exception:  # noqa: BLE001
                pass

    def render(self, spec: dict, overrides: dict, asset: dict | None = None) -> bytes | None:
        """PNG 바이트. image 경로를 쓸 수 없거나 실패하면 None(실패하면 이후 image 경로는 닫힘).
        asset(G62) = {assetId, glbSha256, glbPath}: 생성 형태 메시로 그린다. 그 GLB만 그리지 못하면 PreviewAssetError를 올린다
        (image 경로는 닫지 않음). asset이 없으면 지금과 같은 호출·캐시 키다."""
        if not self.image_ok:
            return None
        spec_json = json.dumps(spec, ensure_ascii=False)
        key = sha256_text(spec_json + "|" + canonical(overrides or {})
                          + (("|asset:" + asset["glbSha256"]) if asset is not None else ""))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        try:
            data = (self.renderer.render(spec_json, dict(overrides or {}), asset) if asset is not None
                    else self.renderer.render(spec_json, dict(overrides or {})))
        except PreviewAssetError:
            raise
        except PreviewError as exc:
            self._fail(str(exc))
            return None
        with self._lock:
            self._cache[key] = data
            while len(self._cache) > 64:
                self._cache.popitem(last=False)
        return data

    def info(self) -> dict:
        return {"requested": self.requested, "mode": self.mode, "reason": self.reason,
                "webglUrl": "/preview/webgl/index.html" if self.mode == "webgl" else None,
                "fallback": self.fallback_target(self.mode) if self.mode == "webgl" else None,
                "webglReadyTimeoutMs": int(self.cfg.webgl_ready_timeout_s * 1000),
                "webglRequestTimeoutMs": int(self.cfg.webgl_request_timeout_s * 1000),
                "renderer": self.renderer.info() if self.renderer is not None and self.image_ok else None,
                "events": list(self.events[-10:])}

    def close(self) -> None:
        if self.renderer is not None:
            self.renderer.close()
