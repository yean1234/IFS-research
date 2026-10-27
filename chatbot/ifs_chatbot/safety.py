"""안전 계층 (「IFS 이론이란?」 5절 L1–L5).

- L1 입력 검사: 한국어 위기 키워드 사전 OR 가드 모델. 하나라도 걸리면 발동(재현율 우선).
- L3 출력 검사(V8): 면담자 질문도 가드 모델과 키워드 사전으로 검사.
- L4 대응: 위기 수준이면 LLM을 부르지 않는다. 고정 문구는 controller가 낸다.
- L5 깊이 제한: 기억 서사·외상 표지(추방자 쪽)를 찾는다.

판정 규칙
  키워드 crisis 층                      → crisis (세션 중지, 연구자 호출)
  가드 S6(자살·자해) / controversial     → soft  (확인 문구 [계속][그만], S6이면 연구자 알림)
  키워드 ambiguous 층                   → soft  + 연구자 알림
  키워드 metaphor 층                    → soft
  그 밖의 가드 UNSAFE(S1 등)            → safe  (기록만, 연구자 화면에 표시)
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

from .korean import normalize
from .paths import shared

LEVEL_ORDER = {"safe": 0, "soft": 1, "crisis": 2}


# ── 키워드 사전 ──────────────────────────────────────────────────────────────
@dataclass
class KeywordHit:
    tier: str      # crisis | ambiguous | metaphor
    id: str
    match: str
    span: tuple[int, int]


class SafetyLexicon:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else shared("lexicon", "safety_ko.v0.json")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.version: str = data["lexiconVersion"]
        self.tiers: dict[str, dict] = {}
        for tier, spec in data["crisis"]["tiers"].items():
            self.tiers[tier] = {
                "action": spec["action"], "alert": bool(spec.get("alertResearcher")),
                "patterns": [(p["id"], re.compile(p["re"])) for p in spec["patterns"]],
            }
        ctrl = data["control"]
        self._stop = [re.compile(p) for p in ctrl["stop"]["wholeMessagePatterns"]]
        self._no_more = [re.compile(p) for p in ctrl["noMore"]["patterns"]]
        self._no_more_max = int(ctrl["noMore"].get("maxChars", 16))
        self._delegation = [re.compile(p) for p in ctrl["delegation"]["patterns"]]
        dep = data["depth"]
        self._depth = {
            "strong": [(p["id"], re.compile(p["re"])) for p in dep["strong"]["patterns"]],
            "weak": [(p["id"], re.compile(p["re"])) for p in dep["weak"]["patterns"]],
        }

    def crisis_hits(self, text: str) -> list[KeywordHit]:
        text = normalize(text)
        out = []
        for tier, spec in self.tiers.items():
            for pid, rx in spec["patterns"]:
                for m in rx.finditer(text):
                    out.append(KeywordHit(tier, pid, m.group(0), (m.start(), m.end())))
        return out

    @staticmethod
    def _clean(text: str) -> str:
        return normalize(text).strip(" .,!?~…'\"")

    def is_stop(self, text: str) -> bool:
        t = self._clean(text)
        return any(rx.fullmatch(t) for rx in self._stop)

    def is_no_more(self, text: str) -> bool:
        t = self._clean(text)
        if not t:
            return True
        if re.fullmatch(r"(아니요|아뇨|아니|아니에요|없음)", t):
            return True
        if len(t.replace(" ", "")) > self._no_more_max:
            return False
        return any(rx.search(t) for rx in self._no_more)

    def is_delegation(self, text: str) -> bool:
        t = normalize(text)
        return any(rx.search(t) for rx in self._delegation)

    def depth(self, text: str) -> dict[str, list[dict]]:
        t = normalize(text)
        out: dict[str, list[dict]] = {"strong": [], "weak": []}
        for level, pats in self._depth.items():
            for pid, rx in pats:
                for m in rx.finditer(t):
                    out[level].append({"id": pid, "match": m.group(0), "span": [m.start(), m.end()]})
        return out

    def has_depth_marker(self, text: str) -> bool:
        d = self.depth(text)
        return bool(d["strong"] or d["weak"])


# ── 가드 모델 ────────────────────────────────────────────────────────────────
KANANA_SYSTEM = (
    "Classify the conversation between a human and an AI. Respond only with the taxonomy code. "
    "(taxonomy codes : ['<SAFE>', '<UNSAFE-S1>', '<UNSAFE-S2>', '<UNSAFE-S3>', '<UNSAFE-S4>', "
    "'<UNSAFE-S5>', '<UNSAFE-S6>', '<UNSAFE-S7>'])"
)
KANANA_CATEGORIES = {
    "S1": "증오", "S2": "괴롭힘", "S3": "성적 콘텐츠", "S4": "범죄",
    "S5": "아동 성착취", "S6": "자살 및 자해", "S7": "잘못된 정보",
}


@dataclass
class ModelVerdict:
    name: str
    label: str                 # SAFE | UNSAFE | CONTROVERSIAL | ERROR
    category: str | None = None
    raw: str = ""
    latency_ms: int = 0
    note: str | None = None


class OllamaGuardModel:
    """Ollama로 띄운 가드 모델. Kanana Safeguard는 GGUF의 채팅 템플릿이 Ollama에서 깨져
    (메시지 내용이 빠짐) raw 모드로 원래 템플릿을 직접 조립한다. <SAFE>는 Ollama가 종료 토큰으로
    처리해 빈 응답(eval_count=1)으로 돌아온다."""

    def __init__(self, model: str, fmt: str = "kanana", host: str = "http://127.0.0.1:11434", timeout_s: float = 60):
        self.model, self.fmt, self.host, self.timeout_s = model, fmt, host.rstrip("/"), timeout_s
        self.digest: str | None = None

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.host}/api/tags", timeout=10)
            r.raise_for_status()
        except Exception:
            return False
        for m in r.json().get("models", []):
            if m.get("name") in (self.model, f"{self.model}:latest") or m.get("model") == self.model:
                self.digest = m.get("digest")
                return True
        return False

    def _kanana_prompt(self, human: str, ai: str) -> str:
        return (
            "<|start_header_id|>system<|end_header_id|>\n\n" + KANANA_SYSTEM + "<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n" + f"<human>{human}</human>\n<ai>{ai}</ai>"
            + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )

    def classify(self, human: str, ai: str = "") -> ModelVerdict:
        t0 = time.perf_counter()
        try:
            if self.fmt == "kanana":
                r = httpx.post(f"{self.host}/api/generate", timeout=self.timeout_s, json={
                    "model": self.model, "prompt": self._kanana_prompt(human, ai), "raw": True, "stream": False,
                    "options": {"temperature": 0, "num_predict": 8, "seed": 0}, "keep_alive": "30m",
                })
                r.raise_for_status()
                d = r.json()
                raw = d.get("response", "") or ""
                ms = int((time.perf_counter() - t0) * 1000)
                m = re.search(r"<UNSAFE-(S\d)>", raw)
                if m:
                    return ModelVerdict(self.model, "UNSAFE", m.group(1), raw, ms)
                if "<SAFE>" in raw:
                    return ModelVerdict(self.model, "SAFE", None, raw, ms)
                if raw.strip() == "" and d.get("done_reason") == "stop" and int(d.get("eval_count", 0)) == 1:
                    return ModelVerdict(self.model, "SAFE", None, raw, ms, note="<SAFE> 토큰이 종료 토큰으로 처리됨")
                return ModelVerdict(self.model, "ERROR", None, raw, ms, note="알 수 없는 가드 출력")
            # qwen3guard: 채팅 템플릿 사용 (이 저장소에서는 실제 모델로 시험하지 않았다)
            msgs = [{"role": "user", "content": human}]
            if ai:
                msgs.append({"role": "assistant", "content": ai})
            r = httpx.post(f"{self.host}/api/chat", timeout=self.timeout_s, json={
                "model": self.model, "messages": msgs, "stream": False, "think": False,
                "options": {"temperature": 0, "num_predict": 64, "seed": 0},
            })
            r.raise_for_status()
            raw = r.json().get("message", {}).get("content", "")
            ms = int((time.perf_counter() - t0) * 1000)
            m = re.search(r"Safety:\s*(Safe|Unsafe|Controversial)", raw, re.I)
            cat = re.search(r"Categories:\s*(.+)", raw)
            if not m:
                return ModelVerdict(self.model, "ERROR", None, raw, ms, note="Safety: 줄이 없음")
            label = m.group(1).upper()
            category = cat.group(1).strip() if cat else None
            if label == "UNSAFE" and category and re.search(r"Suicide|Self-Harm", category, re.I):
                category = "S6"
            return ModelVerdict(self.model, label, category, raw, ms)
        except Exception as exc:  # 가드가 죽어도 면담은 키워드 사전으로 계속 보호된다
            return ModelVerdict(self.model, "ERROR", None, "", int((time.perf_counter() - t0) * 1000), note=str(exc)[:200])

    def info(self) -> dict:
        return {"name": self.model, "format": self.fmt, "digest": self.digest, "runtime": "ollama"}


# ── 판정 ────────────────────────────────────────────────────────────────────
@dataclass
class GuardVerdict:
    level: str = "safe"                 # safe | soft | crisis
    alert: bool = False                 # 연구자 화면 알림
    reasons: list[str] = field(default_factory=list)
    keyword_hits: list[dict] = field(default_factory=list)
    model: dict | None = None

    @property
    def label(self) -> str:
        """세션 로그의 guard 값. 스토리보드 표기(SAFE, controversial)를 따른다."""
        if self.level == "crisis":
            return "CRISIS"
        if self.level == "soft":
            return "controversial"
        return "SAFE"

    def to_log(self) -> dict:
        return {"level": self.level, "label": self.label, "alert": self.alert, "reasons": self.reasons,
                "keywordHits": self.keyword_hits, "model": self.model}


class Guard:
    def __init__(self, lexicon: SafetyLexicon, model: OllamaGuardModel | None = None, use_keywords: bool = True):
        self.lexicon = lexicon
        self.model = model
        self.use_keywords = use_keywords

    def _keyword_part(self, text: str, v: GuardVerdict) -> None:
        if not self.use_keywords:
            return
        for h in self.lexicon.crisis_hits(text):
            v.keyword_hits.append(asdict(h))
            tier = self.lexicon.tiers[h.tier]
            level = "crisis" if tier["action"] == "crisis" else "soft"
            if LEVEL_ORDER[level] > LEVEL_ORDER[v.level]:
                v.level = level
            v.alert = v.alert or tier["alert"]
            v.reasons.append(f"kw:{h.tier}:{h.id}")

    def check_input(self, text: str) -> GuardVerdict:
        v = GuardVerdict()
        self._keyword_part(text, v)
        if self.model is not None:
            mv = self.model.classify(text)
            v.model = asdict(mv)
            if mv.label == "UNSAFE" and mv.category == "S6":
                v.reasons.append("model:S6")
                v.alert = True
                if v.level == "safe":
                    v.level = "soft"
            elif mv.label == "CONTROVERSIAL":
                v.reasons.append("model:controversial")
                if v.level == "safe":
                    v.level = "soft"
            elif mv.label == "UNSAFE":
                v.reasons.append(f"model:{mv.category}:note")  # 기록만
            elif mv.label == "ERROR":
                v.reasons.append("model:error")
        return v

    def check_output(self, participant_text: str, utterance: str, participant_model: dict | None = None) -> GuardVerdict:
        """V8. 면담자 질문이 '새로' 위험을 더하는지 본다.

        Kanana는 (사람, AI) 대화 전체를 분류한다. 실험해 보니 참여자 말만으로 S2가 나오는 문장
        ('젖은 종이처럼 축 처진 덩어리 같아요')이 있어, 그 대화의 판정을 면담자 탓으로 돌리면 무해한 질문이 막힌다.
        그래서 (1) 질문만 따로 분류해 위험하면 실패, (2) 대화 판정이 참여자 말만의 판정으로 설명되지 않으면 실패.
        """
        v = GuardVerdict()
        self._keyword_part(utterance, v)
        if v.level != "safe":
            return v
        if self.model is None:
            return v
        pair = self.model.classify(participant_text, utterance)
        v.model = asdict(pair)
        if pair.label not in ("UNSAFE", "CONTROVERSIAL"):
            return v
        alone = self.model.classify("", utterance)
        v.model["questionOnly"] = asdict(alone)
        if alone.label in ("UNSAFE", "CONTROVERSIAL"):
            v.level = "crisis" if alone.category == "S6" else "soft"
            v.reasons.append(f"model:question:{alone.label.lower()}:{alone.category}")
            return v
        if participant_model is None:
            participant_model = asdict(self.model.classify(participant_text))
            v.model["participantOnly"] = participant_model
        if participant_model.get("label") == pair.label and participant_model.get("category") == pair.category:
            v.reasons.append(f"model:pair:{pair.category}:inherited_from_participant")
            return v  # 참여자 말에서 온 판정 — 질문은 안전
        v.level = "crisis" if pair.category == "S6" else "soft"
        v.reasons.append(f"model:pair:{pair.label.lower()}:{pair.category}")
        return v

    def info(self) -> dict:
        return {
            "keywordLexicon": {"file": self.lexicon.path.name, "version": self.lexicon.version} if self.use_keywords else None,
            "model": self.model.info() if self.model else None,
            "name": (self.model.model if self.model else "keyword-only"),
            "digest": (self.model.digest if self.model else None),
        }
