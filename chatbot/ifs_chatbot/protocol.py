"""유도 면담 프로토콜(shared/protocol/elicitation_protocol.v1.json) 읽기.

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
    type: str                 # fixed | llm | probes | confirm
    stage: str | None = None  # find | focus | flesh_out
    phrase: str | None = None
    max_turns: int = 0
    capture: str | None = None


class Protocol:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else shared("protocol", "elicitation_protocol.v1.json")
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

    def allowed_templates(self, stage: str) -> list[str]:
        return list(self.stages[stage]["allowedTemplates"])

    def stage_info(self, stage: str | None) -> dict:
        return self.stages.get(stage or "", {})

    # ── 문구 ────────────────────────────────────────────────────────────────
    def phrase(self, key: str, **fmt: str) -> str:
        text = self.phrases[key]["text"]
        return text.format(**fmt) if fmt else text

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
        pattern = self.templates[template]["realize"]

        def sub(m: re.Match) -> str:
            slot, kind = m.group(1), m.group(2)
            word = x if slot == "X" else y
            return josa(word, kind)

        out = re.sub(r"\{([XY])\|([^}]+)\}", sub, pattern)
        return out.replace("{X}", x).replace("{Y}", y)

    def info(self) -> dict:
        return {"protocolId": self.protocol_id, "protocolVersion": self.version, "file": self.path.name}
