"""유도 면담 프로토콜(shared/protocol/elicitation_protocol.v1.4.json, 기본) 읽기.

단계 순서, 고정 문구, 질문 틀, 차원 프로브를 코드가 아니라 공용 JSON에서 가져온다.
Unity와 챗봇이 같은 문구를 쓰게 하려는 것이다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .korean import josa
from .paths import shared


@dataclass(frozen=True)
class Step:
    index: int
    type: str                 # fixed | llm | probes | bridge(1.5, D9) | confirm
    stage: str | None = None  # find | focus | flesh_out
    phrase: str | None = None
    max_turns: int = 0
    capture: str | None = None


class Protocol:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else shared("protocol", "elicitation_protocol.v1.4.json")
        if not self.path.is_absolute() and not self.path.exists():
            self.path = shared("protocol", str(path))
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.protocol_id: str = self.data["protocolId"]
        self.version: str = self.data["protocolVersion"]
        self.stages: dict = self.data["stages"]
        self.templates: dict = self.data["templates"]
        self.phrases: dict = self.data["fixedPhrases"]
        self.probes: list[dict] = self.data["dimensionProbes"]["order"]
        self._markers = {k: re.compile(v["marker"]) for k, v in self.templates.items()}

    # ── 조건·단계 ─────────────────────────────────────────────────────────────
    def conditions(self) -> list[str]:
        return list(self.data["conditions"])

    def condition(self, name: str) -> dict:
        if name not in self.data["conditions"]:
            raise ValueError(f"모르는 조건: {name} (가능: {self.conditions()})")
        return self.data["conditions"][name]

    def sequence(self, condition: str) -> list[Step]:
        steps = []
        for i, raw in enumerate(self.condition(condition)["sequence"]):
            steps.append(Step(
                index=i, type=raw["type"], stage=raw.get("stage"), phrase=raw.get("phrase"),
                max_turns=int(raw.get("maxTurns", 0)), capture=raw.get("capture"),
            ))
        return steps

    def max_llm_turns_total(self, condition: str) -> int | None:
        return self.condition(condition).get("maxLlmTurnsTotal")

    def allowed_templates(self, stage: str, image_present: bool = True) -> list[str]:
        """image_present=False이고 그 단계에 allowedTemplatesWhenNoImage가 있으면(1.5, D9: find) 그 목록."""
        info = self.stages[stage]
        if not image_present and "allowedTemplatesWhenNoImage" in info:
            return list(info["allowedTemplatesWhenNoImage"])
        return list(info["allowedTemplates"])

    def restricts_without_image(self, stage: str | None) -> bool:
        return "allowedTemplatesWhenNoImage" in self.stages.get(stage or "", {})

    # ── 다리 질문·형상 신호 (1.5, D9). 1.4 이하 파일에는 없다 ─────────────────
    @property
    def bridge(self) -> dict | None:
        """imageBridge 절. 없으면 None(다리 질문을 쓰지 않는 프로토콜)."""
        return self.data.get("imageBridge")

    @property
    def image_signal_spec(self) -> dict | None:
        return self.data.get("imageSignal")

    def uses_image_signal(self) -> bool:
        """형상 신호 판정을 흐름에 쓰는 프로토콜인지(다리 단계나 find 틀 제한이 있을 때)."""
        has_bridge_step = any(raw.get("type") == "bridge"
                              for c in self.data["conditions"].values() for raw in c["sequence"])
        return self.image_signal_spec is not None and (
            has_bridge_step or any("allowedTemplatesWhenNoImage" in v for v in self.stages.values()))

    def stage_info(self, stage: str | None) -> dict:
        return self.stages.get(stage or "", {})

    # ── 1.6 (G70 + 연구 책임자 시험 세션 결함 1–5). 1.5 이하 파일에는 없고, 없으면 빈 값이라 흐름이 예전 그대로다 ──
    @property
    def capture_defaults(self) -> dict:
        """세션 시작 때 capture에 둘 값(1.6: bodyRelation = not_asked). note 키는 뺀다."""
        return {k: v for k, v in (self.data.get("captureDefaults") or {}).items() if k != "note"}

    @property
    def template_rules(self) -> dict:
        """세션 안 질문 틀 규칙(1.6 templateRules): like_what 횟수·직전 틀 반복·형상 X 금지."""
        return self.data.get("templateRules") or {}

    @property
    def probe_coverage(self) -> dict | None:
        """차원 프로브의 '이미 말함' 판정 규칙(1.6 dimensionProbes.coverage). None이면 1.5 규칙(사전 범주)."""
        return self.data["dimensionProbes"].get("coverage")

    @property
    def referent(self) -> dict | None:
        """고정 문구의 호칭 규칙(1.6 referent). None이면 문구 text를 그대로 쓴다."""
        return self.data.get("referent")

    def find_signal_rule(self) -> dict | None:
        """find LLM을 묻는 조건(1.6 stages.find.askOnlyIfSignal, G70-e). None이면 예전처럼 늘 묻는다."""
        return self.stages.get("find", {}).get("askOnlyIfSignal")

    # ── 문구 ────────────────────────────────────────────────────────────────
    def phrase(self, key: str, **fmt: str) -> str:
        text = self.phrases[key]["text"]
        return text.format(**fmt) if fmt else text

    def has_ref_form(self, key: str) -> bool:
        """X를 인용하는 형(withX)이 있는 문구인지(1.6)."""
        return "withX" in self.phrases.get(key, {})

    def phrase_ref(self, key: str, x: str = "") -> str:
        """X가 있고 문구에 withX가 있으면 X를 넣고 조사를 맞춘 문장, 아니면 text('그 느낌' 형)."""
        p = self.phrases[key]
        if x and "withX" in p:
            return self.realize_text(p["withX"], x)
        return p["text"]

    def phrase_meta(self, key: str) -> dict:
        p = self.phrases[key]
        return {"id": key, "status": p.get("status"), "source": p.get("source") or p.get("note")}

    # ── 질문 틀 ─────────────────────────────────────────────────────────────
    def marker(self, template: str) -> re.Pattern | None:
        return self._markers.get(template)

    def template_slots(self, template: str) -> list[str]:
        return list(self.templates[template]["slots"])

    def realize(self, template: str, x: str = "", y: str = "") -> str:
        """조사까지 맞춘 질문 문장. 오프라인 대역 백엔드와 테스트에서 쓴다."""
        return self.realize_text(self.templates[template]["realize"], x, y)

    @staticmethod
    def realize_text(pattern: str, x: str = "", y: str = "") -> str:
        """'{X|이/가}'처럼 조사 자리를 X의 받침으로 맞추고 '{X}'를 X로 바꾼다(질문 틀과 1.6 withX 문구가 같이 쓴다)."""
        def sub(m: re.Match) -> str:
            slot, kind = m.group(1), m.group(2)
            word = x if slot == "X" else y
            return josa(word, kind)

        out = re.sub(r"\{([XY])\|([^}]+)\}", sub, pattern)
        return out.replace("{X}", x).replace("{Y}", y)

    def info(self) -> dict:
        return {"protocolId": self.protocol_id, "protocolVersion": self.version, "file": self.path.name}
