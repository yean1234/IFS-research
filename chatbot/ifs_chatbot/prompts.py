"""프롬프트 조립 (「IFS 이론이란?」 3절).

system = 공통 시스템 프롬프트 v1.0 + 현재 단계 블록 하나 (MindfulDiary·ChaCha처럼 단계마다 짧은 블록을 바꿔 끼움)
user   = context.txt 틀에 면담 기록·참여자 원문·이미 한 질문·재생성 사유를 채운 것
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .paths import PROMPTS_DIR

CONTEXT_TEMPLATE_VERSION = "0.2.0"
STAGES = ("find", "focus", "flesh_out")


@dataclass
class TranscriptLine:
    role: str   # guide(고정 안내) | interviewer | participant
    text: str


@dataclass
class PromptContext:
    stage: str
    turn_no: int
    max_turns: int
    allowed_templates: list[str]
    transcript: list[TranscriptLine]
    participant_texts: list[str]
    asked: list[dict] = field(default_factory=list)       # [{"template":..., "utterance":...}]
    feedback: list[str] = field(default_factory=list)     # 사람이 읽을 수 있는 재생성 사유
    anchor_candidates: list = field(default_factory=list) # anchors.Anchor — 참여자 원문의 낱말·짧은 구


_ROLE_LABEL = {"guide": "안내(고정)", "interviewer": "면담자", "participant": "참여자"}


class PromptSet:
    def __init__(self, version: str = "1.0.0", base_dir: Path | None = None):
        self.version = version
        self.dir = (base_dir or PROMPTS_DIR) / f"v{version}"
        if not self.dir.exists():
            raise FileNotFoundError(f"프롬프트 폴더가 없습니다: {self.dir}")
        self.common = self._read("common.txt")
        self.stage_blocks = {s: self._read(f"stage_{s}.txt") for s in STAGES}
        self.context_template = self._read("context.txt")
        h = hashlib.sha256()
        for name in ("common.txt", "stage_find.txt", "stage_focus.txt", "stage_flesh_out.txt", "context.txt"):
            h.update((self.dir / name).read_bytes())
        self.sha256 = "sha256:" + h.hexdigest()

    def _read(self, name: str) -> str:
        return (self.dir / name).read_text(encoding="utf-8").strip()

    def system(self, stage: str) -> str:
        return f"{self.common}\n\n{self.stage_blocks[stage]}"

    def user(self, ctx: PromptContext) -> str:
        transcript = "\n".join(f"{_ROLE_LABEL.get(l.role, l.role)}: {l.text}" for l in ctx.transcript) or "(없음)"
        participant_lines = "\n".join(f'- "{t}"' for t in ctx.participant_texts) or "(없음)"
        asked_lines = "\n".join(f"- {a['utterance']} ({a['template']})" for a in ctx.asked) or "(없음)"
        candidate_lines = "\n".join(f"- {a.text}" for a in ctx.anchor_candidates) \
            or "(없음 — 더 펼칠 표현이 없으면 move를 ready_to_advance로)"
        feedback_block = ""
        if ctx.feedback:
            feedback_block = (
                "\n[다시 쓰기] 바로 앞 시도는 아래 검사에 걸려 참여자에게 보내지 않았습니다. 같은 문제를 피해 다시 쓰세요.\n"
                + "\n".join(f"- {f}" for f in ctx.feedback) + "\n"
            )
        return self.context_template.format(
            transcript=transcript,
            stage=ctx.stage,
            turn_no=ctx.turn_no,
            max_turns=ctx.max_turns,
            allowed_templates=", ".join(ctx.allowed_templates),
            participant_lines=participant_lines,
            asked_lines=asked_lines,
            candidate_lines=candidate_lines,
            feedback_block=feedback_block,
        )

    def info(self) -> dict:
        return {"promptVersion": self.version, "promptSha256": self.sha256,
                "contextTemplateVersion": CONTEXT_TEMPLATE_VERSION}
