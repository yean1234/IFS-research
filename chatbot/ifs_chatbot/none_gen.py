"""G73: 후보 화면에서 [맞는 게 없어요]를 누르면 확정 텍스트로 형태(메시)를 하나 만들어 새 후보로 보여 준다.

설정 [gen3d] on_none = true(experiment.toml만). G62 예외(AGENTS.md 원칙 1·2)의 조건을 그대로 지킨다:
- 프롬프트는 규칙만: tools/gen3d/prompts.shape_prompt(Kiwi + 한→영 고정 사전, 말한 형태 낱말만, 낱말마다 charSpan).
  LLM·번역 모델을 쓰지 않는다. 이 모듈은 그 함수를 같은 프로세스에서 불러 차단을 먼저 판정하고(모델 호출 없음),
  생성기 프로세스가 사이드카에 적은 프롬프트가 같은지 다시 본다(다르면 실패).
  (G73 후속) 세션의 매퍼 v2 spec을 함께 넘긴다(mapper_spec, 생성기 입력에는 promptRule mapper + mapperSpec).
  매퍼가 형태에서 버린 낱말(움직임 비유의 매개어 G71, 장소 용법 G74-c, 직접 진술에 밀린 형상 낱말 G71-b, 부정)은 프롬프트에
  넣지 않고 prompt.dropped에 사유와 함께 남긴다. G62 기본 후보 경로는 텍스트만 넘겨 예전 규칙 그대로다.
- (G73 후속) 생성기가 캐시로 끝날 것을 미리 알 수 있으면(같은 프롬프트·seed·모델의 자산이 이미 있음 — 생성기 --cache-probe,
  모델을 부르지 않음) 면담·가드 모델을 내리지 않는다(llmUnload.skipped = cache_hit_expected).
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

import copy
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
from .form_assets import NO_MESH_BASES, NO_MESH_FORM_TYPES, FormAssetStore, bare_sha, file_sha256, source_key
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
B_UNLOAD = "llm_unload_failed"                  # (CP13-1) 면담·가드 모델을 내리지 못함(요청 실패·제한 시간 뒤 /api/ps에 남음) — 만들지 않음
# 생성 뒤 차단: 사이드카 blockReason(person_like·gate_failed) 그대로. 같은 GLB가 이미 후보에 있으면 duplicate_of_offered
B_DUPLICATE = "duplicate_of_offered"
# (G75) 참고 이미지 고르기
IMAGE_PICK_VERSION = "ifs-image-pick/0.1.0"
IMAGES_PER_ROUND = 3
B_ALL_IMAGES_GATED = "all_images_gated"         # 이미지 관문을 통과한 이미지가 0장 — 보여 줄 것이 없음
B_IMAGE_MISSING = "image_missing"               # 고른 이미지 파일이 없거나 sha256이 기록과 다름(fail closed)
DECLINED = "declined"                           # afterNone.status: 이미지 회차를 모두 [이 중에는 없어요]

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


def shape_prompt(text: str, spec: dict | None = None, llm_items: list | None = None,
                 llm_shape_items: list | None = None) -> dict:
    """규칙 프롬프트(tools/gen3d/prompts.shape_prompt). 같은 (텍스트, spec) → 같은 결과. Kiwi 분석기를 함께 쓰므로 잠그고 부른다.
    spec을 주면 매퍼 규칙(그 spec이 형태에서 버린 낱말은 빼고 dropped에 사유).
    (G77) llm_items = 확정 직후 검증을 통과한 LLM 인용 형태 낱말(llm_fill.shape_items_from). 규칙이 형태를 못 만들 때만 쓰인다.
    (G82) llm_shape_items = 검증을 통과한 LLM 형태 이름(llm_shape.shape_items_from). 규칙에 중심 형태 명사가 없을 때만 쓰인다."""
    with _prompts_lock:
        if llm_shape_items:
            return _load_prompts().shape_prompt(text, mapper_spec=spec, llm_shape_items=llm_shape_items)
        if llm_items:
            return _load_prompts().shape_prompt(text, mapper_spec=spec, llm_items=llm_items)
        return _load_prompts().shape_prompt(text, mapper_spec=spec)


def image_pick_prompt(p: dict) -> dict:
    """(G75) 규칙 프롬프트에 이미지 고르기 화풍(무채색·흰 배경·물체 하나) 고정 문구를 더한다(tools/gen3d/prompts.image_pick_prompt)."""
    return _load_prompts().image_pick_prompt(p)


def prompt_record(p: dict) -> dict:
    """기록용 프롬프트: 낱말별 원문 근거(ko·charSpan = 정규화한 확정 텍스트 기준)와 사전·규칙 판.
    (G75) 이미지 고르기 화풍을 더한 프롬프트면 imageStyle·imageStyleVersion을 덧붙인다(G73 기록에는 키가 없다)."""
    extra = {k: p[k] for k in ("imageStyle", "imageStyleVersion", "shapeSource") if k in p}
    return {**_prompt_record(p), **extra}


def _prompt_record(p: dict) -> dict:
    return {"text": p.get("text") or None, "negativeText": p.get("negativeText"),
            "tokens": [{**{k: t.get(k) for k in ("en", "ko", "charSpan", "slot", "lexiconKey")},
                        **({"provenance": t["provenance"]} if "provenance" in t else {})} for t in p.get("tokens") or []],
            "dropped": list(p.get("dropped") or []),
            "status": p.get("status"), "blockReason": p.get("blockReason"), "blockDetail": p.get("blockDetail"),
            "lexiconVersion": p.get("lexiconVersion"), "builderVersion": p.get("builderVersion"),
            "templateVersion": p.get("templateVersion"), "sourceTextSha256": p.get("sourceTextSha256"),
            "promptRule": p.get("promptRule"), "mapperBuilder": p.get("mapperBuilder"),
            "pluralStated": p.get("pluralStated"), "thinRisk": p.get("thinRisk"),
            "familiarObjectStated": p.get("familiarObjectStated")}


def _resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else (CHATBOT_DIR / q).resolve()


class NoneGenJob:
    """생성 한 번. cancel()은 프로세스를 끈다(참여자가 기다리지 않고 넘어감·철회·서버 종료)."""

    def __init__(self, session_id: str, text: str, key: str, prompt_text: str, seed: int = 0, attempt: int = 0,
                 spec: dict | None = None, kind: str = "full", seeds: list[int] | None = None,
                 image: tuple[Path, str] | None = None, timeout_s: float | None = None, llm_items: list | None = None,
                 llm_shape_items: list | None = None):
        self.session_id, self.text, self.key, self.prompt_text = session_id, text, key, prompt_text
        self.llm_items = llm_items or None     # (G77) 생성기 입력 줄의 llmShapeItems(있을 때만 키를 적는다)
        self.llm_shape_items = llm_shape_items or None   # (G82) 생성기 입력 줄의 llmTranslatedShapeItems(있을 때만)
        self.spec = spec                    # 세션 매퍼 spec(있으면 생성기도 매퍼 규칙으로 프롬프트를 다시 만든다)
        self.seed, self.attempt = int(seed), int(attempt)
        # (G75) kind: full(G73 한 번에 이미지 → 형태) | image(이미지 여러 장 + 이미지 관문만) | mesh(고른 이미지로 형태만)
        self.kind = kind
        self.seeds = [int(s) for s in seeds] if seeds else [self.seed]
        self.image = image                  # mesh: (이미지 경로, sha256)
        self.timeout_s = timeout_s
        self.cancel_ev = threading.Event()
        self.cancel_reason: str | None = None
        self.proc: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.result: dict | None = None
        self.lock = threading.Lock()
        # (CP13-3) waiting(앞 작업의 모델 재적재를 기다림) → running(내림·생성) → reloading(모델 다시 올림) → done
        self.phase = "waiting"
        self.released = threading.Event()     # 재적재까지 끝남(다음 작업이 이것을 기다린다)

    def cancel(self, reason: str = "participant_skipped_wait") -> None:
        """취소 표시만 하고 곧 돌아온다. 프로세스 끄기(Windows taskkill, 최대 15초)는 백그라운드(CP13-4)."""
        with self.lock:
            if self.cancel_reason is None:
                self.cancel_reason = reason
            self.cancel_ev.set()
            proc = self.proc
        if proc is not None and proc.poll() is None:
            threading.Thread(target=_kill, args=(proc,), name=f"none-gen-kill-{self.session_id}", daemon=True).start()

    def wait(self, timeout: float | None = None) -> bool:
        """(시험용) 끝날 때까지 기다린다. 끝났으면 True."""
        if self.thread is None:
            return True
        self.thread.join(timeout)
        return not self.thread.is_alive()


class InterviewBlocked(RuntimeError):
    """(CP13-2) 생성 중이거나 가드 모델이 준비되지 않아 면담 요청을 받지 않음(서버는 409 + 이 사유)."""


class _InterviewSlot:
    def __init__(self, svc: "NoneGenService", crisis_ok: bool, creating: bool):
        self.svc, self.crisis_ok, self.creating = svc, crisis_ok, creating

    def __enter__(self):
        with self.svc.lock:
            why = self.svc._refusal_locked(self.creating)
            if why and not self.crisis_ok:
                raise InterviewBlocked(why)
            self.svc.inflight += 1
        return self

    def __exit__(self, *exc):
        with self.svc.lock:
            self.svc.inflight -= 1
        return False


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
        # (G75) 참고 이미지 고르기. 켜면 max_regenerations 대신 이미지 회차(image_rounds)로 다시 만든다
        self.image_pick = bool(getattr(g, "on_none_image_pick", False))
        self.image_rounds = max(1, int(getattr(g, "on_none_image_rounds", 2)))
        self.image_timeout_s = float(getattr(g, "on_none_image_timeout_s", 180.0))
        self.mesh_timeout_s = float(getattr(g, "on_none_mesh_timeout_s", 180.0))
        self.host = cfg.llm.host.rstrip("/")
        self.lock = threading.Lock()
        self.active: NoneGenJob | None = None      # 내림 ~ 재적재 완료까지 활성(CP13-3)
        self._closed = False
        # (CP13-2) 면담 LLM·가드 모델을 쓰는 요청 수(interview_slot). 생성은 이것이 0이고 면담 중 세션이 없을 때만 예약한다
        self.inflight = 0
        # 재적재 뒤 면담·가드 모델이 /api/ps에 없으면 False. guard.required면 돌아올 때까지 새 면담을 막고 백그라운드로 다시 올린다
        self.models_ready = True
        self.models_problem: str | None = None
        self._retrying = False
        self.retry_interval_s = 15.0

    # ── 정보 ────────────────────────────────────────────────────────────────
    def available(self) -> tuple[bool, str | None]:
        if not self.python.is_file():
            return False, f"생성기 python이 없습니다: {self.python}"
        if not self.script.is_file():
            return False, f"생성기 스크립트가 없습니다: {self.script}"
        return True, None

    def setting(self) -> dict:
        """기록용 설정(로컬 절대 경로는 넣지 않음 — 파일 이름만). (G75) 이미지 고르기를 켰을 때만 imagePick 키를 더한다."""
        out = {"version": NONE_GEN_VERSION, "timeoutS": self.timeout_s, "pipeline": self.pipeline, "seed": self.seed,
               "maxRegenerations": self.max_regenerations, "seedRule": "seed = on_none_seed + n (n = 0 첫 생성, 1… 다시 만들기)",
               "script": self.script.name, "python": self.python.name, "unloadModels": [m for _, m, _ in self._ollama_models()]}
        if self.image_pick:
            out["imagePick"] = {"version": IMAGE_PICK_VERSION, "rounds": self.image_rounds, "imagesPerRound": IMAGES_PER_ROUND,
                                "imageTimeoutS": self.image_timeout_s, "meshTimeoutS": self.mesh_timeout_s,
                                "seedRule": f"회차 r(0부터)의 이미지 seed = on_none_seed + {IMAGES_PER_ROUND}r + k "
                                            f"(k = 0…{IMAGES_PER_ROUND - 1}), 형태 seed = 고른 이미지의 seed",
                                "maxRegenerationsUsed": False}
        return out

    def seeds_for_round(self, r: int) -> list[int]:
        """(G75) 회차 r의 이미지 seed: 기준 + 3r, + 1, + 2."""
        return [self.seed + IMAGES_PER_ROUND * int(r) + k for k in range(IMAGES_PER_ROUND)]

    def info(self) -> dict:
        ok, why = self.available()
        with self.lock:
            busy = self.active.session_id if self.active is not None else None
            ready, problem = self.models_ready, self.models_problem
        return {"onNone": True, **self.setting(), "generatorAvailable": ok, "generatorProblem": why,
                "assetsDirExists": self.root.is_dir(),
                "generatingFor": busy, "modelsReady": ready, "modelsProblem": problem}   # CP13-2: 실험자 화면·health

    def prewarm(self) -> None:
        """첫 [맞는 게 없어요]의 규칙 프롬프트 판정이 Kiwi·매퍼 적재(수 초)를 기다리지 않게 미리 불러 둔다."""
        try:
            shape_prompt("준비")
        except Exception:  # noqa: BLE001
            pass

    # ── 생성 전 판정(모델 호출 없음) ─────────────────────────────────────────
    def precheck(self, spec: dict, confirmed_text: str | None, preview_mode: str, other_interviews: list[str],
                 llm_items: list | None = None, llm_shape_items: list | None = None) -> dict:
        """→ {prompt(기록용 | None), blockReason, blockDetail}. blockReason이 None이면 만들 수 있다. 같은 입력 → 같은 판정."""
        out = {"prompt": None, "blockReason": None, "blockDetail": None}

        def block(reason, detail=None):
            if out["blockReason"] is None:
                out["blockReason"], out["blockDetail"] = reason, detail
            return out

        if not isinstance(confirmed_text, str) or not confirmed_text.strip():
            return block(B_NO_TEXT)
        try:
            p = shape_prompt(confirmed_text, spec, llm_items, llm_shape_items)   # 세션 매퍼(v2) 판단을 따름(G73 후속). (G77) LLM 형태 낱말은 빈자리만
            if self.image_pick:
                p = image_pick_prompt(p)                     # (G75) 무채색 화풍 고정 문구(내용 토큰은 그대로)
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
            if self.active is not None and self.active.phase != "reloading":
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
        # (CP13-1) 내렸다고 볼 수 있는가: 요청이 모두 성공하고 /api/ps를 읽었고 우리 모델이 남지 않음
        left = sorted(names & set(loaded or []))
        rec["ok"] = all(x["ok"] for x in rec["models"]) and loaded is not None and not left
        if not rec["ok"]:
            rec["problem"] = ("unload_request_failed" if not all(x["ok"] for x in rec["models"]) else
                              "ps_unreadable" if loaded is None else "still_loaded:" + ",".join(left))
        return rec

    def models_loaded(self) -> tuple[bool, str | None]:
        """면담·가드 모델이 모두 /api/ps에 올라 있는가(Ollama를 쓰지 않으면 늘 True)."""
        models = self._ollama_models()
        if not models:
            return True, None
        loaded = self._loaded()
        if loaded is None:
            return False, "ps_unreadable"
        have = set(loaded)
        miss = [m for _, m, _ in models if m not in have and f"{m}:latest" not in have]
        return (not miss), ("not_loaded:" + ",".join(miss) if miss else None)

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
        ok, why = self.models_loaded()
        req_ok = all(x["ok"] for x in rec["models"])
        rec.update(ok=ok and req_ok, problem=None if ok and req_ok else (why or "reload_request_failed"))
        return rec

    def _after_reload(self, rec: dict) -> None:
        """(CP13-2) 재적재 결과로 준비 상태를 세운다. 실패면 백그라운드로 다시 올리기를 되풀이한다."""
        with self.lock:
            self.models_ready = bool(rec.get("ok"))
            self.models_problem = None if self.models_ready else rec.get("problem")
            start_retry = not self.models_ready and not self._retrying and not self._closed
            if start_retry:
                self._retrying = True
        if not self.models_ready:
            log.warning("none-gen: 면담·가드 모델을 다시 올리지 못함(%s) — 돌아올 때까지 새 면담을 막고 다시 올림",
                        self.models_problem)
        if start_retry:
            threading.Thread(target=self._retry_reload, name="none-gen-reload-retry", daemon=True).start()

    def _retry_reload(self) -> None:
        try:
            while True:
                with self.lock:
                    if self.models_ready or self._closed:
                        return
                    busy = self.active is not None
                if not busy:
                    ok, _ = self.models_loaded()            # 다른 경로(사람이 Ollama를 다시 켬 등)로 돌아왔으면 그대로 회복
                    rec = {"ok": True, "problem": None} if ok else self.reload_models()
                    with self.lock:
                        if self.active is None:
                            self.models_ready = bool(rec.get("ok"))
                            self.models_problem = None if self.models_ready else rec.get("problem")
                        ready = self.models_ready
                    if ready:
                        log.info("none-gen: 면담·가드 모델 다시 준비됨")
                        return
                time.sleep(self.retry_interval_s)
        finally:
            with self.lock:
                self._retrying = False

    # ── 면담과 생성의 상호 배제(CP13-2) ─────────────────────────────────────────
    def interview_refusal(self, creating: bool = False) -> str | None:
        """면담 요청을 지금 받으면 안 되는 이유(실험자 화면에 보일 짧은 문장). None이면 받아도 된다."""
        with self.lock:
            return self._refusal_locked(creating)

    def _refusal_locked(self, creating: bool) -> str | None:
        if self.active is not None:
            return (f"물체 생성 중이라 면담 모델을 내려 두었습니다(세션 {self.active.session_id}). "
                    "생성과 모델 다시 올리기가 끝난 뒤 다시 시도해 주세요.")
        if creating and not self.models_ready and self.cfg.guard.required:
            return (f"가드 모델이 준비되지 않았습니다({self.models_problem}). 다시 올리는 중입니다 — "
                    "서버 상태(/api/health)를 보고 잠시 뒤 다시 시도해 주세요.")
        return None

    def interview_slot(self, crisis_ok: bool = False, creating: bool = False) -> "_InterviewSlot":
        """면담 LLM·가드 모델을 쓸 수 있는 요청 구간. 생성이 예약돼 있으면 막는다(InterviewBlocked). crisis_ok면 통과 —
        키워드 위기는 모델 없이 고정 문구만 낸다(CP12). 들어가 있는 동안에는 새 생성을 예약하지 않는다(inflight)."""
        return _InterviewSlot(self, crisis_ok, creating)

    # ── 실행 ────────────────────────────────────────────────────────────────
    def seed_for(self, attempt: int) -> int:
        return self.seed + int(attempt)

    def start(self, session_id: str, text: str, key: str, prompt_text: str, on_done, attempt: int = 0,
              spec: dict | None = None, other_interviews=None, kind: str = "full", seeds: list[int] | None = None,
              image: tuple[Path, str] | None = None, seed: int | None = None,
              llm_items: list | None = None, llm_shape_items: list | None = None) -> "NoneGenJob | str":
        """백그라운드로 시작 → NoneGenJob, 못 하면 사유 문자열(B_BUSY·B_INTERVIEW). on_done(result)은 생성 스레드에서 한 번.
        (CP13-2) 면담 중 세션(other_interviews — 목록 또는 호출 가능)과 들어가 있는 면담 요청(inflight)을 같은 잠금 안에서 보고
        예약한다. (CP13-3) 앞 작업이 모델을 다시 올리는 중(reloading)이면 예약하고, 새 작업은 그 재적재가 끝난 뒤에 시작한다.
        (G75) kind = image(seeds의 이미지 + 이미지 관문) | mesh(image = (경로, sha256), seed = 고른 이미지의 seed).
        두 단계도 각각 이 작업 하나다: 모델 내림 → 생성기 → 모델 다시 올림(참여자가 고르는 동안 면담·가드 모델은 올라가 있다)."""
        with self.lock:
            prev = self.active
            if self._closed or (prev is not None and prev.phase != "reloading"):
                return B_BUSY
            others = list(other_interviews() if callable(other_interviews) else (other_interviews or []))
            if others or self.inflight:
                return B_INTERVIEW
            if kind == "full":
                job = NoneGenJob(session_id, text, key, prompt_text, self.seed_for(attempt), attempt, spec, llm_items=llm_items,
                                 llm_shape_items=llm_shape_items)
            else:
                job = NoneGenJob(session_id, text, key, prompt_text, seed if seed is not None else (seeds or [self.seed])[0],
                                 attempt, spec, kind=kind, seeds=seeds, image=image,
                                 timeout_s=self.image_timeout_s if kind == "image" else self.mesh_timeout_s,
                                 llm_items=llm_items, llm_shape_items=llm_shape_items)
            self.active = job

        def work():
            if prev is not None:
                prev.released.wait(600)                 # 앞 작업의 재적재가 끝날 때까지
            job.phase = "running"
            try:
                job.result = self._run(job) if job.kind == "full" else self._run_phase(job)
            except Exception as exc:  # noqa: BLE001 — 어떤 예외도 세션을 멈추게 하지 않는다(실패로 기록)
                job.result = {"status": FAILED, "error": f"{type(exc).__name__}: {exc}"[:300], "endedAt": now_iso()}
            job.phase = "reloading"
            try:
                on_done(job.result)
            except Exception:  # noqa: BLE001
                log.exception("none-gen on_done 실패")
            try:
                if job.result.get("llmUnload") and job.result["llmUnload"].get("models"):
                    rl = self.reload_models()
                    job.result["llmReload"] = rl
                    log.info("none-gen: 모델 다시 올림 %s", rl)
                    self._after_reload(rl)
            except Exception:  # noqa: BLE001
                log.exception("none-gen 재적재 실패")
                self._after_reload({"ok": False, "problem": "reload_exception"})
            finally:
                job.phase = "done"
                job.released.set()
                with self.lock:
                    if self.active is job:
                        self.active = None

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

        # 1) 입력(저장소 밖 assets_dir/<run>/inputs/sentences.json — tools/gen3d/inputs.py와 같은 형식).
        #    세션 매퍼 spec이 있으면 promptRule mapper + mapperSpec(생성기도 같은 매퍼 규칙으로 프롬프트를 만든다)
        run_dir = self.root / run
        inputs = run_dir / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        row = {"id": INPUT_ID, "text": job.text, "kind": "session_after_none", "source": None}
        if job.spec is not None:
            row.update(promptRule="mapper", mapperSpec=job.spec)
            if job.llm_items:
                row["llmShapeItems"] = job.llm_items
            if job.llm_shape_items:
                row["llmTranslatedShapeItems"] = job.llm_shape_items
        (inputs / "sentences.json").write_text(json.dumps([row], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cmd = [str(self.python), str(self.script), "--run", run, "--pipeline", self.pipeline, "--seed", str(job.seed)]
        env = {**os.environ, "GEN3D_OUT": str(self.root), "PYTHONIOENCODING": "utf-8"}
        # 2) 캐시로 끝날지 미리 본다(모델 호출 없음). 끝난다면 면담·가드 모델을 내리지 않는다(내렸다 올리는 시간·다음 세션 적재 대기 없음)
        probe = self._cache_probe(cmd, env, run_dir, job, t0)
        res["cacheProbe"] = probe
        res["timing"]["probeS"] = round(time.monotonic() - t0, 2)
        if job.cancel_ev.is_set():
            return finish(CANCELLED, error=job.cancel_reason)
        # 3) GPU 비우기(면담·가드 모델 내림) — 캐시 적중이 확실하지 않으면 늘 내린다
        if probe.get("modelCallsExpected") is False and probe.get("promptText") == job.prompt_text:
            res["llmUnload"] = {"at": now_iso(), "skipped": "cache_hit_expected", "models": [],
                                "loadedBefore": None, "loadedAfter": None}
        else:
            res["llmUnload"] = self.unload_models()
        res["timing"]["unloadS"] = round(time.monotonic() - t0, 2)
        if job.cancel_ev.is_set():
            return finish(CANCELLED, error=job.cancel_reason)
        u = res["llmUnload"]
        if u.get("models") and not u.get("ok"):            # (CP13-1) 남은 모델과 GPU를 나눠 쓰지 않는다
            return finish(BLOCKED, blockReason=B_UNLOAD, blockDetail=u.get("problem"))
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

    # ── (G75) 이미지 단계·형태 단계 ─────────────────────────────────────────────
    def _run_phase(self, job: NoneGenJob) -> dict:
        """image: --image-pick --seeds → <run>/image-pick.json(이미지마다 sha256·관문). mesh: --from-image → form-asset 사이드카.
        캐시 미리 보기는 하지 않는다(늘 모델을 내림). 대기 한도는 단계마다(job.timeout_s, 모델 내림 포함)."""
        t0 = time.monotonic()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tag = "img" if job.kind == "image" else "mesh"
        run = f"none-{job.session_id}-{stamp}-r{job.attempt}-{tag}"
        res = {"status": None, "kind": job.kind, "run": run, "seed": job.seed, "seeds": list(job.seeds), "attempt": job.attempt,
               "startedAt": now_iso(), "endedAt": None, "seconds": None, "exitCode": None, "error": None,
               "blockReason": None, "blockDetail": None, "asset": None, "images": None, "llmUnload": None,
               "cacheProbe": None, "timing": {}}
        limit = float(job.timeout_s if job.timeout_s is not None else self.timeout_s)

        def finish(status, **kw):
            res.update(status=status, endedAt=now_iso(), seconds=round(time.monotonic() - t0, 2), **kw)
            return res

        run_dir = self.root / run
        inputs = run_dir / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        row = {"id": INPUT_ID, "text": job.text, "kind": "session_after_none", "source": None,
               "imageStyle": _load_prompts().IMAGE_PICK_STYLE_ID}
        if job.spec is not None:
            row.update(promptRule="mapper", mapperSpec=job.spec)
            if job.llm_items:
                row["llmShapeItems"] = job.llm_items
            if job.llm_shape_items:
                row["llmTranslatedShapeItems"] = job.llm_shape_items
        (inputs / "sentences.json").write_text(json.dumps([row], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cmd = [str(self.python), str(self.script), "--run", run, "--pipeline", self.pipeline, "--seed", str(job.seed)]
        if job.kind == "image":
            cmd += ["--image-pick", "--seeds", ",".join(str(s) for s in job.seeds)]
        else:
            img, sha = job.image
            if not Path(img).is_file() or file_sha256(Path(img)) != sha:
                return finish(BLOCKED, blockReason=B_IMAGE_MISSING, blockDetail=Path(img).name)
            cmd += ["--from-image", str(img), "--image-sha256", sha]
        env = {**os.environ, "GEN3D_OUT": str(self.root), "PYTHONIOENCODING": "utf-8"}
        if job.cancel_ev.is_set():
            return finish(CANCELLED, error=job.cancel_reason)
        res["llmUnload"] = self.unload_models()
        res["timing"]["unloadS"] = round(time.monotonic() - t0, 2)
        if job.cancel_ev.is_set():
            return finish(CANCELLED, error=job.cancel_reason)
        u = res["llmUnload"]
        if u.get("models") and not u.get("ok"):            # (CP13-1) 남은 모델과 GPU를 나눠 쓰지 않는다
            return finish(BLOCKED, blockReason=B_UNLOAD, blockDetail=u.get("problem"))
        code, stop = self._spawn_wait(cmd, env, run_dir, job, t0, limit)
        res["exitCode"] = code
        if stop == CANCELLED:
            return finish(CANCELLED, error=job.cancel_reason)
        if stop == TIMEOUT:
            return finish(TIMEOUT, error=f"{limit:g}초를 넘김")
        res["timing"]["generatorS"] = round(time.monotonic() - t0 - res["timing"]["unloadS"], 2)
        if job.kind == "image":
            return self._image_result(run_dir, job, code, finish)
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

    def _image_result(self, run_dir: Path, job: NoneGenJob, code, finish) -> dict:
        """image-pick.json → 이미지 목록(seed 순서). 파일 sha256·프롬프트가 다르거나 관문을 못 돌린 이미지는 보이지 않는다(passed false)."""
        pf = run_dir / "image-pick.json"
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return finish(FAILED, error=f"exit {code}: no image-pick.json; {self._log_tail(run_dir)}"[:300])
        if d.get("status") == "blocked":
            return finish(BLOCKED, blockReason=d.get("blockReason") or "blocked", blockDetail=d.get("blockDetail"))
        if d.get("status") != "ok":
            return finish(FAILED, error=(d.get("error") or f"exit {code}: status {d.get('status')}")[:300])
        if (d.get("prompt") or {}).get("text") != job.prompt_text or bare_sha(d.get("sourceTextSha256")) != bare_sha(job.key):
            return finish(FAILED, error="prompt_mismatch: 생성기 프롬프트가 서버의 규칙 프롬프트와 다름")
        out = []
        for im in sorted(d.get("images") or [], key=lambda x: int(x.get("seed", 0))):
            rel = str(im.get("file") or "")
            path = (run_dir / rel).resolve()
            item = {"seed": int(im.get("seed", 0)), "file": rel, "sha256": im.get("sha256"), "seconds": im.get("seconds"),
                    "gate": copy.deepcopy(im.get("gate")) if isinstance(im.get("gate"), dict) else None,
                    "problem": None}
            if not rel or os.path.isabs(rel) or ".." in Path(rel).parts or run_dir.resolve() not in path.parents:
                # (CP14-2) 검증에 실패한 경로 문자열은 기록·로그에 남기지 않는다(로컬 절대 경로가 참여자 기록에 들어가지 않게)
                item["problem"] = "file_path_invalid"
                item["file"] = None
                path = None
            elif not path.is_file():
                item["problem"] = "file_missing"
            elif file_sha256(path) != im.get("sha256"):
                item["problem"] = "sha256_mismatch"
            elif item["gate"] is None or item["gate"].get("passed") is not True:
                item["problem"] = "gate_not_passed"
            item["passed"] = item["problem"] is None
            item["_path"] = path
            out.append(item)
        return finish(OK, images=out, models=copy.deepcopy(d.get("models")), generatorTiming=d.get("timing"))

    def _spawn_wait(self, cmd, env, run_dir: Path, job: NoneGenJob, t0: float, limit: float):
        """생성기 프로세스 하나를 띄우고 끝·취소·시간 초과까지 기다린다 → (exit code | None, None | CANCELLED | TIMEOUT)."""
        logf = open(run_dir / "generator.log", "wb")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            with job.lock:
                if job.cancel_ev.is_set():
                    return None, CANCELLED
                job.proc = subprocess.Popen(cmd, cwd=str(REPO_ROOT), env=env, stdout=logf, stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL, creationflags=flags)
            while True:
                try:
                    code = job.proc.wait(timeout=0.25)
                    # 취소의 백그라운드 끄기(cancel → _kill)가 먼저 끝냈으면 정상 종료가 아니라 취소다
                    return code, (CANCELLED if job.cancel_ev.is_set() else None)
                except subprocess.TimeoutExpired:
                    pass
                if job.cancel_ev.is_set() or time.monotonic() - t0 > limit:
                    stop = CANCELLED if job.cancel_ev.is_set() else TIMEOUT
                    _kill(job.proc)
                    job.proc.wait(timeout=30)
                    return job.proc.returncode, stop
        finally:
            logf.close()

    PROBE_TIMEOUT_S = 60.0

    def _cache_probe(self, cmd: list[str], env: dict, run_dir: Path, job: NoneGenJob, t0: float) -> dict:
        """생성기 --cache-probe(모델을 부르지 않음: 규칙 프롬프트 → 캐시 키 → 캐시 파일 유무) → run_dir/cache-probe.json.
        → {modelCallsExpected: bool | None, promptText, keys, seconds, error}. 알 수 없으면 modelCallsExpected None(모델을 내림)."""
        out = {"modelCallsExpected": None, "promptText": None, "seconds": None, "error": None}
        tp = time.monotonic()
        limit = min(self.PROBE_TIMEOUT_S, max(1.0, self.timeout_s - (tp - t0) - 5))
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            with open(run_dir / "cache-probe.log", "wb") as lf:
                with job.lock:
                    if job.cancel_ev.is_set():
                        out["error"] = "cancelled"
                        return out
                    job.proc = subprocess.Popen(cmd + ["--cache-probe"], cwd=str(REPO_ROOT), env=env, stdout=lf,
                                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags)
                proc = job.proc
                while True:
                    try:
                        proc.wait(timeout=0.25)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                    if job.cancel_ev.is_set() or time.monotonic() - tp > limit:
                        _kill(proc)
                        proc.wait(timeout=30)
                        out["error"] = "cancelled" if job.cancel_ev.is_set() else f"probe {limit:g}초를 넘김"
                        return out
            with job.lock:
                job.proc = None
            pf = run_dir / "cache-probe.json"
            if proc.returncode != 0 or not pf.is_file():
                out["error"] = f"exit {proc.returncode}: {self._log_tail(run_dir, name='cache-probe.log')}"[:300]
                return out
            d = json.loads(pf.read_text(encoding="utf-8"))
            row = (d.get("rows") or {}).get(INPUT_ID) or {}
            out.update(modelCallsExpected=d.get("modelCallsExpected"), promptText=row.get("promptText"),
                       cacheKey=row.get("cacheKey"), cached=row.get("cached"))
        except Exception as exc:  # noqa: BLE001 — 미리 보기를 못 하면 예전처럼 내린다
            out["error"] = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            out["seconds"] = round(time.monotonic() - tp, 2)
        return out

    @staticmethod
    def _sidecar(run_dir: Path) -> dict | None:
        for p in sorted(run_dir.rglob(f"{INPUT_ID}.form-asset.json")):
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        return None

    @staticmethod
    def _log_tail(run_dir: Path, n: int = 200, name: str = "generator.log") -> str:
        try:
            raw = (run_dir / name).read_bytes()[-n:]
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
