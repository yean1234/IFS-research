"""면담 LLM 백엔드.

- OllamaBackend: 로컬 Ollama. JSON 스키마를 format으로 넘겨 구조화 출력을 강제한다(제약 디코딩).
  Gemma 4는 thinking이 기본으로 켜져 있어 think=false를 명시한다.
- OfflineTemplateBackend: 개발용 대역. LLM 없이 '참여자 단어를 정해진 틀에 끼우는' 일을 규칙으로
  흉내 낸다. 연구 조건이 아니며, 세션 로그의 model.name이 offline-template로 남는다.
- ScriptedBackend: 테스트용. 미리 정한 출력을 차례로 돌려준다.

세 백엔드 모두 같은 검증기(V1–V9)를 통과해야 참여자에게 질문이 나간다.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Iterable

import httpx

from .config import LLMConfig
from .korean import Analyzer
from .lexicon import Lexicon
from .prompts import PromptContext
from .protocol import Protocol
from .safety import SafetyLexicon


@dataclass
class GenerationRequest:
    system: str
    user: str
    seed: int
    attempt: int
    context: PromptContext


@dataclass
class GenerationResult:
    raw: str
    latency_ms: int
    meta: dict = field(default_factory=dict)


class BackendError(RuntimeError):
    pass


def clean_schema(schema: dict) -> dict:
    """Ollama format으로 넘길 때 메타 키는 뺀다(키 순서는 그대로 둔다)."""
    return {k: v for k, v in schema.items() if not k.startswith("$") and not k.startswith("x-")
            and k not in ("title", "description")}


# ── Ollama ──────────────────────────────────────────────────────────────────
class OllamaBackend:
    name = "ollama"

    def __init__(self, cfg: LLMConfig, schema: dict):
        self.cfg = cfg
        self.schema = clean_schema(schema)
        self.host = cfg.host.rstrip("/")
        self.digest: str | None = None
        self.details: dict = {}
        self.runtime_version: str | None = None
        self._send_think = True

    def check(self) -> tuple[bool, str]:
        try:
            self.runtime_version = httpx.get(f"{self.host}/api/version", timeout=10).json().get("version")
            tags = httpx.get(f"{self.host}/api/tags", timeout=10).json().get("models", [])
        except Exception as exc:
            return False, f"Ollama 서버({self.host})에 연결할 수 없습니다. 'ollama serve'로 켜 주세요. ({exc.__class__.__name__})"
        names = {self.cfg.model, f"{self.cfg.model}:latest"}
        found = next((m for m in tags if m.get("name") in names or m.get("model") in names), None)
        if not found:
            return False, f"Ollama에 모델이 없습니다: {self.cfg.model}. 'ollama pull {self.cfg.model}' 후 다시 실행하거나 --backend offline으로 실행하세요."
        self.digest = found.get("digest")
        try:
            self.details = httpx.post(f"{self.host}/api/show", json={"model": self.cfg.model}, timeout=30).json().get("details", {})
        except Exception:
            self.details = {}
        return True, "ok"

    def info(self) -> dict:
        return {
            "name": self.cfg.model,
            "quant": self.details.get("quantization_level"),
            "parameterSize": self.details.get("parameter_size"),
            "digest": f"sha256:{self.digest}" if self.digest else None,
            "runtime": f"ollama {self.runtime_version}" if self.runtime_version else "ollama",
            "sampling": {"temperature": self.cfg.temperature, "top_p": self.cfg.top_p,
                         "seed": self.cfg.seed, "thinking": self.cfg.think},
            "numCtx": self.cfg.num_ctx,
        }

    def _post(self, body: dict) -> dict:
        r = httpx.post(f"{self.host}/api/chat", json=body, timeout=self.cfg.timeout_s)
        d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code >= 400 or d.get("error"):
            raise BackendError(d.get("error") or f"HTTP {r.status_code}")
        return d

    def generate(self, req: GenerationRequest) -> GenerationResult:
        body = {
            "model": self.cfg.model,
            "stream": False,
            "format": self.schema,
            "messages": [{"role": "system", "content": req.system}, {"role": "user", "content": req.user}],
            "options": {"temperature": self.cfg.temperature, "top_p": self.cfg.top_p,
                        "seed": req.seed, "num_ctx": self.cfg.num_ctx},
            "keep_alive": self.cfg.keep_alive,
        }
        if self._send_think:
            body["think"] = self.cfg.think
        t0 = time.perf_counter()
        try:
            d = self._post(body)
        except BackendError as exc:
            # thinking을 지원하지 않는 모델이면 think 키 없이 한 번 더
            if self._send_think and "think" in str(exc).lower():
                self._send_think = False
                body.pop("think", None)
                d = self._post(body)
            else:
                raise
        except httpx.HTTPError as exc:
            raise BackendError(f"{exc.__class__.__name__}: {exc}") from exc
        ms = int((time.perf_counter() - t0) * 1000)
        msg = d.get("message", {})
        return GenerationResult(
            raw=msg.get("content", ""),
            latency_ms=ms,
            meta={"eval_count": d.get("eval_count"), "prompt_eval_count": d.get("prompt_eval_count"),
                  "done_reason": d.get("done_reason"), "thinking_chars": len(msg.get("thinking") or "")},
        )

    def warmup(self) -> None:
        """첫 호출의 모델 적재 시간(수십 초)을 세션 밖에서 미리 쓴다."""
        try:
            httpx.post(f"{self.host}/api/chat", timeout=self.cfg.timeout_s, json={
                "model": self.cfg.model, "stream": False, "keep_alive": self.cfg.keep_alive,
                "messages": [{"role": "user", "content": "."}], "options": {"num_predict": 1}, "think": False,
            })
        except Exception:
            pass


# ── 오프라인 대역 ────────────────────────────────────────────────────────────
class OfflineTemplateBackend:
    name = "offline"

    def __init__(self, protocol: Protocol, lexicon: Lexicon, analyzer: Analyzer, safety: SafetyLexicon):
        self.protocol, self.lexicon, self.analyzer, self.safety = protocol, lexicon, analyzer, safety

    def check(self) -> tuple[bool, str]:
        return True, "ok"

    def info(self) -> dict:
        return {"name": "offline-template", "quant": None, "digest": None, "runtime": "rule (개발용 대역, 연구 조건 아님)",
                "sampling": None}

    def warmup(self) -> None:
        return None

    def generate(self, req: GenerationRequest) -> GenerationResult:
        ctx = req.context
        used_templates = [a.get("template") for a in ctx.asked]
        allowed = ctx.allowed_templates
        # 명사구보다 낱말을 먼저 쓴다(그 '덩어리'는 어떤 '덩어리'인가요?)
        candidates = [a for a in ctx.anchor_candidates if a.kind != "phrase"] or list(ctx.anchor_candidates)
        out = {"stage": ctx.stage, "risk_signal": "none", "move": "ready_to_advance",
               "template": "none", "anchor_quote": "", "utterance": ""}
        if candidates:
            a = candidates[req.attempt % len(candidates)]
            prefs = (["anything_else", "like_what"] if a.kind == "root"
                     else ["what_kind", "like_what", "anything_else", "where"])
            if ctx.stage == "focus":
                prefs = ["where"] + prefs
            if ctx.turn_no == 1 and "anything_else" in allowed:
                prefs = ["anything_else"] + prefs
            last = used_templates[-1] if used_templates else None
            template = next((t for t in prefs if t in allowed and t != last), next((t for t in prefs if t in allowed), None))
            if template:
                out.update(move="ask", template=template, anchor_quote=a.text,
                           utterance=self.protocol.realize(template, a.text))
        return GenerationResult(json.dumps(out, ensure_ascii=False), latency_ms=0, meta={"offline": True})


# ── 테스트용 ────────────────────────────────────────────────────────────────
class ScriptedBackend:
    name = "scripted"

    def __init__(self, outputs: Iterable[str | dict]):
        self.outputs = [o if isinstance(o, str) else json.dumps(o, ensure_ascii=False) for o in outputs]
        self.calls: list[GenerationRequest] = []

    def check(self) -> tuple[bool, str]:
        return True, "ok"

    def info(self) -> dict:
        return {"name": "scripted-test", "quant": None, "digest": None, "runtime": "test", "sampling": None}

    def warmup(self) -> None:
        return None

    def generate(self, req: GenerationRequest) -> GenerationResult:
        self.calls.append(req)
        if not self.outputs:
            raise BackendError("스크립트 출력이 더 없습니다")
        return GenerationResult(self.outputs.pop(0), latency_ms=1, meta={})
