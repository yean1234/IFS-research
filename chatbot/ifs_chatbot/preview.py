"""형상 미리보기 어댑터 (D5, 결정 G12 → 메인 세션 판정 G25: WebGL 모듈을 설치하지 못해 지금은 "image" 모드).

모드(config [preview] mode):
- "image": Unity Windows 미리보기 플레이어(IFSPreview.exe, PreviewQueue)를 상주시켜 spec JSON + 덮어쓰기 JSON을 넣고
           PNG를 받는다. 플레이어는 저장소 밖 빌드 폴더(설정값 image_player). 서버 시작 때(start_on_launch) 또는 첫 요청 때 띄운다.
           플레이어가 없거나, 뜨지 않거나, 요청 중에 죽으면 "none"으로 자동 대체하고 그 사실을 info()·세션 로그·화면에 남긴다.
           image_player = "fake"는 테스트용 가짜 렌더러(서버 안에서 그린 PNG — Unity 렌더가 아님)다.
- "webgl": 로컬에서 내보낸 Unity WebGL 빌드(webgl_dir/index.html)를 웹 화면 iframe에 띄운다. 인터페이스만 있다
           (브리지: window.ifsPreview.load(spec) · applyOverrides(obj) · capture(...)). 폴더가 없으면 "none".
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
MODES = ("webgl", "image", "none")


class PreviewError(RuntimeError):
    """플레이어가 없거나 응답하지 않음 등. 서비스는 이것을 받으면 none으로 대체한다."""


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


# ── 렌더러 ──────────────────────────────────────────────────────────────────
class FakeRenderer:
    name = "fake"

    def __init__(self, defaults: dict, width: int = 160, height: int = 120):
        self.defaults, self.width, self.height = defaults, width, height
        self.calls = 0

    def render(self, spec_json: str, overrides: dict) -> bytes:
        self.calls += 1
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

    def render(self, spec_json: str, overrides: dict) -> bytes:
        with self.lock:
            self.start()
            self.seq += 1
            name = f"r{os.getpid()}_{self.seq:06d}"
            out_prefix = self.queue_dir / name
            done = self.queue_dir / f"{name}.done.json"
            png = Path(f"{out_prefix}_scene.png")
            body = {"specJson": spec_json, "overrides": overrides or {}, "width": self.width, "height": self.height,
                    "backgrounds": ["scene"], "out": str(out_prefix)}
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
                if not result.get("ok"):
                    raise PreviewError("플레이어가 그리지 못함: " + str(result.get("error"))[:300])
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
    """설정을 읽어 실제로 쓸 모드를 정하고, 렌더 실패 시 none으로 대체한다."""

    def __init__(self, cfg, log_dir: Path, base_dir: Path, defaults: dict):
        self.cfg = cfg
        self.requested = cfg.mode
        if cfg.mode not in MODES:
            raise ValueError(f"모르는 preview.mode: {cfg.mode} (webgl | image | none)")
        self.mode = "none"
        self.reason: str | None = None
        self.renderer = None
        self.webgl_dir: Path | None = None
        self.events: list[dict] = []
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

        def resolve(p: str) -> Path:
            q = Path(p)
            return q if q.is_absolute() else (base_dir / q).resolve()

        if cfg.mode == "webgl":
            d = resolve(cfg.webgl_dir) if cfg.webgl_dir else None
            if d is not None and (d / "index.html").exists():
                self.mode, self.webgl_dir = "webgl", d
            else:
                self.reason = f"WebGL 빌드가 없음({d or '경로 미설정'}) → none"
        elif cfg.mode == "image":
            player = cfg.image_player
            if player == "fake":
                self.mode, self.renderer = "image", FakeRenderer(defaults)
            elif player and resolve(player).exists():
                exe = resolve(player)
                cmd = [sys.executable, str(exe)] if exe.suffix == ".py" else [str(exe)]
                qdir = resolve(cfg.queue_dir) if cfg.queue_dir else Path(log_dir) / "preview-queue"
                self.mode = "image"
                self.renderer = UnityQueueRenderer(cmd, qdir, cfg.width, cfg.height,
                                                   cfg.start_timeout_s, cfg.request_timeout_s)
                if cfg.start_on_launch:
                    try:
                        self.renderer.start()
                    except PreviewError as exc:
                        self._fail(str(exc))
            else:
                self.reason = f"미리보기 플레이어가 없음({player or '경로 미설정'}) → none"
        if self.reason:
            self._event("fallback", self.reason)

    def _event(self, kind: str, detail: str) -> None:
        self.events.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind, "detail": detail})
        log.warning("[preview] %s: %s", kind, detail)

    def _fail(self, detail: str) -> None:
        self.mode = "none"
        self.reason = f"미리보기 플레이어 오류 → none: {detail}"
        self._event("fallback", self.reason)
        if self.renderer is not None:
            try:
                self.renderer.close()
            except Exception:  # noqa: BLE001
                pass

    def render(self, spec: dict, overrides: dict) -> bytes | None:
        """PNG 바이트. image 모드가 아니거나 실패하면 None(실패하면 이후 none으로 고정)."""
        if self.mode != "image" or self.renderer is None:
            return None
        spec_json = json.dumps(spec, ensure_ascii=False)
        key = sha256_text(spec_json + "|" + canonical(overrides or {}))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        try:
            data = self.renderer.render(spec_json, dict(overrides or {}))
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
                "renderer": self.renderer.info() if self.renderer is not None and self.mode == "image" else None,
                "events": list(self.events[-10:])}

    def close(self) -> None:
        if self.renderer is not None:
            self.renderer.close()
