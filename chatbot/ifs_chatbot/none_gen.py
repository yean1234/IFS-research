"""G73: 후보 화면에서 [맞는 게 없어요]를 누르면 확정 텍스트로 형태(메시)를 하나 만들어 새 후보로 보여 준다.

설정 [gen3d] on_none = true(experiment.toml만). G62 예외(AGENTS.md 원칙 1·2)의 조건을 그대로 지킨다:
- 프롬프트는 규칙만: tools/gen3d/prompts.shape_prompt(Kiwi + 한→영 고정 사전, 말한 형태 낱말만, 낱말마다 charSpan).
  LLM·번역 모델을 쓰지 않는다. 이 모듈은 그 함수를 같은 프로세스에서 불러 차단을 먼저 판정하고(모델 호출 없음),
  생성기 프로세스가 사이드카에 적은 프롬프트가 같은지 다시 본다(다르면 실패).
- 형태를 말하지 않았거나(no_shape_stated) 사람·얼굴·동물·메시로 그릴 수 없는 범주면(excluded_category, G50 형태 막음,
  안개·불꽃) 만들지 않는다. 사유를 기록하고 기존 none 경로(0번 후보로 조절)로 간다.
- 생성 결과는 '생성' 출처(generated_after_none)의 후보일 뿐이다. 참여자가 고른 경우에만 장면에 쓰고(selection.py),
  스펙 슬롯 값(색·질감·크기·위치)을 채우지 않는다. 크기는 가장 긴 변 정규화(사이드카 normalization) + 사용자 값.

실행: 생성은 별도 프로세스(gen3d 환경)로 한다 — <on_none_python> <script> --run <이름> --pipeline <p> --seed <s>.
입력·출력은 assets_dir(저장소 밖) 아래 <run>/에만 쓴다(원칙 6). 만들기 전에 Ollama 모델(면담·가드)을 내려 GPU를 비우고,
끝나면 다시 올린다. 이 시점 뒤 그 세션은 면담 LLM을 부르지 않는다(후보 단계는 면담이 끝나 확정된 세션에서만 열림,
selection.py는 LLM·검증기를 부르지 않음). 다른 세션이 면담 중이면 내리지 않고 만들지도 않는다(interview_active).
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx

from .candidates import form_blocks, slot_value
from .form_assets import NO_MESH_BASES, NO_MESH_FORM_TYPES, FormAssetStore, source_key
from .paths import CHATBOT_DIR, REPO_ROOT
from .session_log import now_iso

log = logging.getLogger("ifs_chatbot.none_gen")

NONE_GEN_VERSION = "ifs-none-gen/0.1.0"
ORIGIN = "generated_after_none"                 # 후보 origin·sources form.type, form.asset.origin(G62의 generated와 구분)
GEN_SCRIPT = REPO_ROOT / "tools" / "gen3d" / "generate.py"
PROMPTS_FILE = REPO_ROOT / "tools" / "gen3d" / "prompts.py"
INPUT_ID = "after-none"                         # 생성기 입력 sentences.json의 문장 id(사이드카 파일 이름)
# 면담 LLM을 부를 수 있는 세션 상태(controller.Session.state). 이런 세션이 있으면 GPU를 비우지 않는다
INTERVIEW_STATES = ("interview", "soft_check", "clarify", "confirm")

# 결과(afterNone.status)
RUNNING, OK, BLOCKED, FAILED, TIMEOUT, CANCELLED = "running", "ok", "blocked", "failed", "timeout", "cancelled"
STATUSES = (RUNNING, OK, BLOCKED, FAILED, TIMEOUT, CANCELLED)
# 생성 전 차단 사유(모델 호출 없음). shape_prompt의 no_shape_stated·excluded_category·untraceable_token도 이 자리에 온다
B_NO_TEXT = "no_confirmed_text"
B_HASH = "source_hash_mismatch"                 # 확정 텍스트 해시가 spec meta.sourceTextHash와 다름(fail closed)
B_PREVIEW_NONE = "no_shape_preview"             # 미리보기가 글 요약뿐이라 생성 형태를 보일 수 없음
B_FORM_BLOCKED = "form_blocked_G50"
B_NO_MESH = "no_mesh_form"                      # 안개·불꽃(메시로 만들지 않음)
B_BUSY = "generator_busy"                       # 다른 세션의 생성이 돌고 있음
B_INTERVIEW = "interview_active"                # 다른 세션이 면담 중 — 면담 모델을 내릴 수 없음
B_NO_GENERATOR = "generator_unavailable"        # 생성기 python·스크립트가 없음
B_PROMPT_ERROR = "prompt_error"                 # 규칙 프롬프트를 만들지 못함(Kiwi 없음 등)
# 생성 뒤 차단: 사이드카 blockReason(person_like·gate_failed) 그대로. 같은 GLB가 이미 후보에 있으면 duplicate_of_offered
B_DUPLICATE = "duplicate_of_offered"

_prompts_mod = None
_prompts_lock = threading.Lock()


def _load_prompts():
    """tools/gen3d/prompts.py를 고유 이름으로 불러온다(저장소 안 코드, 모델 의존 없음 — Kiwi·매퍼만). sys.path는 되돌린다."""
    global _prompts_mod
    if _prompts_mod is None:
        saved, had_common = list(sys.path), "common" in sys.modules
        try:
            spec = importlib.util.spec_from_file_location("ifs_gen3d_prompts", PROMPTS_FILE)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = saved
            if not had_common:
                sys.modules.pop("common", None)     # tools/gen3d/common.py가 다른 'common'을 가리지 않게
        _prompts_mod = mod
    return _prompts_mod


def shape_prompt(text: str) -> dict:
    """규칙 프롬프트(tools/gen3d/prompts.shape_prompt). 같은 텍스트 → 같은 결과. Kiwi 분석기를 함께 쓰므로 잠그고 부른다."""
    with _prompts_lock:
        return _load_prompts().shape_prompt(text)


def prompt_record(p: dict) -> dict:
    """기록용 프롬프트: 낱말별 원문 근거(ko·charSpan = 정규화한 확정 텍스트 기준)와 사전·규칙 판."""
    return {"text": p.get("text") or None, "negativeText": p.get("negativeText"),
            "tokens": [{k: t.get(k) for k in ("en", "ko", "charSpan", "slot", "lexiconKey")} for t in p.get("tokens") or []],
            "dropped": list(p.get("dropped") or []),
            "status": p.get("status"), "blockReason": p.get("blockReason"), "blockDetail": p.get("blockDetail"),
            "lexiconVersion": p.get("lexiconVersion"), "builderVersion": p.get("builderVersion"),
            "templateVersion": p.get("templateVersion"), "sourceTextSha256": p.get("sourceTextSha256"),
            "pluralStated": p.get("pluralStated"), "thinRisk": p.get("thinRisk"),
            "familiarObjectStated": p.get("familiarObjectStated")}


def _resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else (CHATBOT_DIR / q).resolve()


class NoneGenJob:
    """생성 한 번. cancel()은 프로세스를 끈다(참여자가 기다리지 않고 넘어감·철회·서버 종료)."""

    def __init__(self, session_id: str, text: str, key: str, prompt_text: str, seed: int = 0, attempt: int = 0):
        self.session_id, self.text, self.key, self.prompt_text = session_id, text, key, prompt_text
        self.seed, self.attempt = int(seed), int(attempt)
        self.cancel_ev = threading.Event()
        self.cancel_reason: str | None = None
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.result: dict | None = None
        self.lock = threading.Lock()

    def cancel(self, reason: str = "participant_skipped_wait") -> None:
        with self.lock:
            if self.cancel_reason is None:
                self.cancel_reason = reason
            self.cancel_ev.set()
            _kill(self.proc)

    def wait(self, timeout: float | None = None) -> bool:
        """(시험용) 끝날 때까지 기다린다. 끝났으면 True."""
        if self.thread is None:
            return True
        self.thread.join(timeout)
        return not self.thread.is_alive()


def _kill(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        # 자식까지(Windows): taskkill /T. 실패해도 아래 kill로 본 프로세스는 끈다
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=15)
        except Exception:  # noqa: BLE001
            pass
    try:
        proc.kill()
    except Exception:  # noqa: BLE001
        pass


class NoneGenService:
    """Runtime 하나에 하나. 동시에 하나의 생성만 돌린다(GPU 하나)."""

    def __init__(self, cfg, assets_root: Path):
        g = cfg.gen3d
        self.cfg = cfg
        self.root = Path(assets_root)
        self.timeout_s = float(g.on_none_timeout_s)
        self.python = _resolve(g.on_none_python)
        self.script = _resolve(g.on_none_script) if g.on_none_script else GEN_SCRIPT
        self.pipeline, self.seed = g.on_none_pipeline, int(g.on_none_seed)
        # 다시 만들기: 만든 후보도 맞지 않다고 하면 같은 프롬프트로 seed = 기준 seed + n(n = 1, 2, …)까지 이 횟수만큼 더
        self.max_regenerations = max(0, int(g.on_none_max_regenerations))
        self.host = cfg.llm.host.rstrip("/")
        self.lock = threading.Lock()
        self.active: NoneGenJob | None = None
        self._closed = False

    # ── 정보 ────────────────────────────────────────────────────────────────
    def available(self) -> tuple[bool, str | None]:
        if not self.python.is_file():
            return False, f"생성기 python이 없습니다: {self.python}"
        if not self.script.is_file():
            return False, f"생성기 스크립트가 없습니다: {self.script}"
        return True, None

    def setting(self) -> dict:
        """기록용 설정(로컬 절대 경로는 넣지 않음 — 파일 이름만)."""
        return {"version": NONE_GEN_VERSION, "timeoutS": self.timeout_s, "pipeline": self.pipeline, "seed": self.seed,
                "maxRegenerations": self.max_regenerations, "seedRule": "seed = on_none_seed + n (n = 0 첫 생성, 1… 다시 만들기)",
                "script": self.script.name, "python": self.python.name, "unloadModels": [m for _, m, _ in self._ollama_models()]}

    def info(self) -> dict:
        ok, why = self.available()
        return {"onNone": True, **self.setting(), "generatorAvailable": ok, "generatorProblem": why,
                "assetsDirExists": self.root.is_dir()}

    def prewarm(self) -> None:
        """첫 [맞는 게 없어요]의 규칙 프롬프트 판정이 Kiwi·매퍼 적재(수 초)를 기다리지 않게 미리 불러 둔다."""
        try:
            shape_prompt("준비")
        except Exception:  # noqa: BLE001
            pass

    # ── 생성 전 판정(모델 호출 없음) ─────────────────────────────────────────
    def precheck(self, spec: dict, confirmed_text: str | None, preview_mode: str, other_interviews: list[str]) -> dict:
        """→ {prompt(기록용 | None), blockReason, blockDetail}. blockReason이 None이면 만들 수 있다. 같은 입력 → 같은 판정."""
        out = {"prompt": None, "blockReason": None, "blockDetail": None}

        def block(reason, detail=None):
            if out["blockReason"] is None:
                out["blockReason"], out["blockDetail"] = reason, detail
            return out

        if not isinstance(confirmed_text, str) or not confirmed_text.strip():
            return block(B_NO_TEXT)
        try:
            p = shape_prompt(confirmed_text)
        except (Exception, SystemExit) as exc:  # noqa: BLE001 — 프롬프트를 못 만들면 만들지 않는다(fail closed)
            return block(B_PROMPT_ERROR, f"{type(exc).__name__}: {exc}"[:300])
        out["prompt"] = prompt_record(p)
        if p.get("sourceTextSha256") != source_key(spec):
            block(B_HASH)
        if preview_mode == "none":
            block(B_PREVIEW_NONE, "preview mode none")
        if form_blocks(spec):
            block(B_FORM_BLOCKED, ",".join(sorted({u.get("lemma") or "" for u in form_blocks(spec)})))
        if slot_value(spec, "form.type") in NO_MESH_FORM_TYPES or slot_value(spec, "form.base") in NO_MESH_BASES:
            block(B_NO_MESH, f"form.type={slot_value(spec, 'form.type')} form.base={slot_value(spec, 'form.base')}")
        if p.get("status") != "ok":
            block(p.get("blockReason") or "blocked", p.get("blockDetail"))
        ok, why = self.available()
        if not ok:
            block(B_NO_GENERATOR, why)
        if other_interviews:
            block(B_INTERVIEW, ",".join(other_interviews))
        with self.lock:
            if self.active is not None:
                block(B_BUSY, self.active.session_id)
        return out

    # ── Ollama(면담·가드 모델) 내리기·올리기 ─────────────────────────────────
    def _ollama_models(self) -> list[tuple[str, str, str]]:
        """(역할, 모델, 다시 올릴 때 keep_alive). Ollama를 쓰는 것만."""
        out = []
        if self.cfg.llm.backend == "ollama":
            out.append(("interview", self.cfg.llm.model, self.cfg.llm.keep_alive))
        if self.cfg.guard.model_backend == "ollama":
            out.append(("guard", self.cfg.guard.model, "30m"))       # safety.OllamaGuardModel과 같은 keep_alive
        return out

    def _loaded(self) -> list[str] | None:
        try:
            r = httpx.get(f"{self.host}/api/ps", timeout=10)
            return sorted({m.get("name") or m.get("model") for m in r.json().get("models", [])})
        except Exception:  # noqa: BLE001
            return None

    def unload_models(self) -> dict:
        """keep_alive 0으로 내리고 /api/ps에서 빠졌는지 확인한다(최대 10초). Ollama를 쓰지 않으면 건너뜀."""
        models = self._ollama_models()
        rec = {"at": now_iso(), "models": [], "loadedBefore": None, "loadedAfter": None}
        if not models:
            rec["skipped"] = "no_ollama_models"
            return rec
        rec["loadedBefore"] = self._loaded()
        for role, m, _ in models:
            item = {"role": role, "model": m, "ok": False, "detail": None}
            try:
                r = httpx.post(f"{self.host}/api/generate", json={"model": m, "keep_alive": 0}, timeout=60)
                item["ok"] = r.status_code < 400
                if not item["ok"]:
                    item["detail"] = f"HTTP {r.status_code}"
            except Exception as exc:  # noqa: BLE001
                item["detail"] = f"{type(exc).__name__}: {exc}"[:200]
            rec["models"].append(item)
        names = {m for _, m, _ in models} | {f"{m}:latest" for _, m, _ in models}
        t_end = time.monotonic() + 10
        loaded = self._loaded()
        while loaded is not None and names & set(loaded) and time.monotonic() < t_end:
            time.sleep(0.5)
            loaded = self._loaded()
        rec["loadedAfter"] = loaded
        return rec

    def reload_models(self) -> dict:
        """생성이 끝난 뒤(결과와 상관없이) 내린 모델을 다시 올린다(다음 세션의 첫 질문이 적재를 기다리지 않게)."""
        rec = {"at": now_iso(), "models": []}
        for role, m, keep in self._ollama_models():
            item = {"role": role, "model": m, "ok": False}
            try:
                r = httpx.post(f"{self.host}/api/generate", json={"model": m, "keep_alive": keep}, timeout=300)
                item["ok"] = r.status_code < 400
            except Exception as exc:  # noqa: BLE001
                item["detail"] = f"{type(exc).__name__}: {exc}"[:200]
            rec["models"].append(item)
        return rec

    # ── 실행 ────────────────────────────────────────────────────────────────
    def seed_for(self, attempt: int) -> int:
        return self.seed + int(attempt)

    def start(self, session_id: str, text: str, key: str, prompt_text: str, on_done, attempt: int = 0) -> NoneGenJob | None:
        """백그라운드로 시작. 이미 돌고 있으면 None. on_done(result)은 생성 스레드에서 한 번 불린다."""
        with self.lock:
            if self.active is not None or self._closed:
                return None
            job = NoneGenJob(session_id, text, key, prompt_text, self.seed_for(attempt), attempt)
            self.active = job

        def work():
            try:
                job.result = self._run(job)
            except Exception as exc:  # noqa: BLE001 — 어떤 예외도 세션을 멈추게 하지 않는다(실패로 기록)
                job.result = {"status": FAILED, "error": f"{type(exc).__name__}: {exc}"[:300], "endedAt": now_iso()}
            finally:
                with self.lock:
                    if self.active is job:
                        self.active = None
            try:
                on_done(job.result)
            except Exception:  # noqa: BLE001
                log.exception("none-gen on_done 실패")
            if job.result.get("llmUnload") and job.result["llmUnload"].get("models"):
                rl = self.reload_models()
                log.info("none-gen: 모델 다시 올림 %s", rl)

        job.thread = threading.Thread(target=work, name=f"none-gen-{session_id}", daemon=True)
        job.thread.start()
        return job

    def _run(self, job: NoneGenJob) -> dict:
        t0 = time.monotonic()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run = f"none-{job.session_id}-{stamp}-n{job.attempt}"
        res = {"status": None, "run": run, "seed": job.seed, "attempt": job.attempt, "startedAt": now_iso(), "endedAt": None, "seconds": None, "exitCode": None,
               "error": None, "blockReason": None, "blockDetail": None, "asset": None, "llmUnload": None,
               "timing": {}}

        def finish(status, **kw):
            res.update(status=status, endedAt=now_iso(), seconds=round(time.monotonic() - t0, 2), **kw)
            return res

        # 1) GPU 비우기(면담·가드 모델 내림)
        res["llmUnload"] = self.unload_models()
        res["timing"]["unloadS"] = round(time.monotonic() - t0, 2)
        if job.cancel_ev.is_set():
            return finish(CANCELLED, error=job.cancel_reason)
        # 2) 입력(저장소 밖 assets_dir/<run>/inputs/sentences.json — tools/gen3d/inputs.py와 같은 형식)
        run_dir = self.root / run
        inputs = run_dir / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        (inputs / "sentences.json").write_text(json.dumps([{"id": INPUT_ID, "text": job.text, "kind": "session_after_none",
                                                            "source": None}], ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
        cmd = [str(self.python), str(self.script), "--run", run, "--pipeline", self.pipeline, "--seed", str(job.seed)]
        env = {**os.environ, "GEN3D_OUT": str(self.root), "PYTHONIOENCODING": "utf-8"}
        logf = open(run_dir / "generator.log", "wb")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            with job.lock:
                if job.cancel_ev.is_set():
                    return finish(CANCELLED, error=job.cancel_reason)
                job.proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL, creationflags=flags)
            t_proc = time.monotonic()
            while True:
                try:
                    code = job.proc.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if job.cancel_ev.is_set():
                    _kill(job.proc)
                    job.proc.wait(timeout=30)
                    res["exitCode"] = job.proc.returncode
                    return finish(CANCELLED, error=job.cancel_reason)
                if time.monotonic() - t0 > self.timeout_s:
                    _kill(job.proc)
                    job.proc.wait(timeout=30)
                    res["exitCode"] = job.proc.returncode
                    return finish(TIMEOUT, error=f"{self.timeout_s:g}초를 넘김")
            res["exitCode"] = code
            res["timing"]["generatorS"] = round(time.monotonic() - t_proc, 2)
        finally:
            logf.close()
        # 3) 결과 찾기(확정 텍스트 키로, 이 실행 폴더만) — form_assets와 같은 검사(status ok·관문 통과·GLB sha256·읽을 수 있는 GLB)
        store = FormAssetStore(run_dir, max_candidates=1)
        lk = store.lookup(job.key)
        if lk["offered"]:
            a = lk["offered"][0]
            if a.get("promptText") != job.prompt_text:
                return finish(FAILED, error="prompt_mismatch: 생성기 프롬프트가 서버의 규칙 프롬프트와 다름")
            return finish(OK, asset=a)
        side = self._sidecar(run_dir)
        if side is not None and side.get("status") == "blocked":
            return finish(BLOCKED, blockReason=side.get("blockReason") or "blocked", blockDetail=side.get("blockDetail"))
        if side is not None and side.get("status") == "failed":
            return finish(FAILED, error=(side.get("error") or "failed")[:300])
        why = "; ".join(f"{r['reason']}" for r in lk["rejected"]) or "no_sidecar"
        return finish(FAILED, error=f"exit {code}: {why}; {self._log_tail(run_dir)}"[:300])

    @staticmethod
    def _sidecar(run_dir: Path) -> dict | None:
        for p in sorted(run_dir.rglob(f"{INPUT_ID}.form-asset.json")):
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        return None

    @staticmethod
    def _log_tail(run_dir: Path, n: int = 200) -> str:
        try:
            raw = (run_dir / "generator.log").read_bytes()[-n:]
            return raw.decode("utf-8", "replace").replace("\r", " ").replace("\n", " ").strip()
        except OSError:
            return ""

    def close(self) -> None:
        """서버 종료: 돌고 있는 생성을 끈다."""
        with self.lock:
            self._closed = True
            job = self.active
        if job is not None:
            job.cancel("server_shutdown")
