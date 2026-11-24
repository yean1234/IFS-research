"""세션 컨트롤러 — 「앞으로 개발 방향」 > Focus > 컨트롤러(세션 진행 보조).

- 지금이 Find / Focus / Flesh out 중 어느 단계인지 기억한다.
- 다음 차례에 고정 문구를 낼지, LLM에게 질문을 만들게 할지 정한다.
- 단계별 횟수 제한(Find 1회, Flesh out 5회 …)을 세고 다음 단계로 넘긴다.

한 턴의 순서(「앞으로 개발 방향」 > 챗봇 구현 원리):
 1) 컨트롤러가 단계를 정함  2) 프롬프트 조립(공통 규칙 + 단계 블록)  3) 로컬 LLM이 JSON으로 답함
 4) 검증기 V1–V9 → 통과한 질문만 나감(최대 2회 재생성, 그다음 고정 대체 문구)
 5) 참여자 답마다 안전 분류(키워드 사전 + 가드 모델) → 위기면 LLM을 끄고 고정 문구 + 연구자 호출
 6) 끝나면 참여자 발화를 그대로 모은 요약을 보여 주고 [이대로 맞아요] → 그 텍스트만 추출로 넘어감
 7) 확정 직후 같은 텍스트로 SceneSpec v2를 만들어 scenes/{sessionId}.json에 저장(scene_builder, LLM 없음)
"""
from __future__ import annotations

import json
import logging
import re
import secrets
import threading
from collections import defaultdict
from datetime import datetime

from .anchors import anchor_candidates
from .clarify import clarify_targets, question_json
from .config import Config
from .drift import PARAMS as DRIFT_PARAMS
from .drift import DriftAssessor, participant_turns, summarize
from .extract import Extractor, find_modality, parse_body_relation
from .korean import Analyzer, normalize
from .lexicon import Lexicon
from .candidates import load_table as load_candidate_table
from .candidates import safety_flags
from .llm import GenerationRequest, OfflineTemplateBackend, OllamaBackend
from .paths import CHATBOT_DIR, shared
from .preview import PreviewService
from .prompts import PromptContext, PromptSet, TranscriptLine
from .protocol import Protocol, Step
from .safety import Guard, GuardVerdict, OllamaGuardModel, SafetyLexicon
from .scene_builder import SceneSpecBuilder, normalize_confirmed, write_spec
from .scene_builder_v1 import SceneSpecBuilderV1, fallback_spec
from .scene_builder_v2 import SceneSpecBuilderV2
from .scene_spec import check_principles
from .selection import SelectionError, SelectionFlow, SelectionProtocol, delete_selection_dir
from .session_log import SessionLog, now_iso
from .validator import TurnContext, Validator, describe

CONTROLLER_VERSION = "0.1.0"
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
alert_logger = logging.getLogger("ifs_chatbot.alerts")


class SessionError(Exception):
    """잘못된 순서의 요청 등. API는 409로 돌려준다."""


# ── 공유 의존성 ───────────────────────────────────────────────────────────────
class Runtime:
    """서버가 한 번 만들어 모든 세션이 같이 쓰는 것들."""

    def __init__(self, cfg: Config, backend=None, guard_model=None, persist_logs: bool = True):
        self.cfg = cfg
        self.warnings: list[str] = []
        self.analyzer = Analyzer()
        if not self.analyzer.available:
            self.warnings.append("kiwipiepy가 없어 정규식 대체 분석을 씁니다. V5·추출 정확도가 떨어집니다.")
        self.lexicon = Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), self.analyzer)
        self.safety = SafetyLexicon()
        self.protocol = Protocol(cfg.interview.protocol)
        self.prompts = PromptSet(cfg.interview.prompt_version)
        self.schema = json.loads(shared("schemas", "interviewer_turn.schema.json").read_text(encoding="utf-8"))

        if guard_model is None and cfg.guard.model_backend == "ollama":
            cand = OllamaGuardModel(cfg.guard.model, cfg.guard.format, cfg.llm.host)
            if cand.available():
                guard_model = cand
            else:
                msg = f"가드 모델을 찾지 못했습니다({cfg.guard.model}). 키워드 사전만으로 L1을 검사합니다."
                if cfg.guard.required:
                    raise RuntimeError(msg + " (guard.required = true)")
                self.warnings.append(msg)
        self.guard = Guard(self.safety, guard_model, use_keywords=cfg.guard.keyword)

        if backend is None:
            if cfg.llm.backend == "ollama":
                backend = OllamaBackend(cfg.llm, self.schema)
            elif cfg.llm.backend == "offline":
                backend = OfflineTemplateBackend(self.protocol, self.lexicon, self.analyzer, self.safety)
            else:
                raise ValueError(f"모르는 llm.backend: {cfg.llm.backend}")
        self.backend = backend
        self.backend_ok, self.backend_msg = backend.check()
        if not self.backend_ok:
            self.warnings.append(self.backend_msg)
        if cfg.llm.backend == "offline":
            self.warnings.append("오프라인 대역 백엔드: 규칙으로 질문 틀을 채웁니다. 연구 조건이 아닙니다.")

        self.validator = Validator(
            self.protocol, self.lexicon, self.safety, self.analyzer, self.schema,
            guard=self.guard if cfg.guard.check_output else None,
            strict_novel_content=cfg.validator.strict_novel_content,
            depth_anchor_block=cfg.validator.l5_depth != "off",
            max_anchor_eojeol=cfg.validator.max_anchor_eojeol,
        )
        self.extractor = Extractor(self.lexicon, self.analyzer)
        # 확정 텍스트 → SceneSpec 매핑. v0 = 규칙 기반 기준선(scene_builder.py, 출력 불변), v1 = 개선 매핑.
        # scene_builder는 주 매핑(config [mapping] mode). corpus_run이 이 자리에 다른 매핑을 끼울 수 있다.
        self.scene_builders: dict[str, object] = {"v0": SceneSpecBuilder(self.lexicon, self.analyzer)}
        self.mapping_load_error: str | None = None
        if cfg.mapping.mode not in ("v0", "v1", "v2"):
            raise ValueError(f"모르는 mapping.mode: {cfg.mapping.mode} (v0 | v1 | v2)")
        # [mapping] strict: 시작 시점(여기) 실패만 다룬다. strict이고 v1을 요청했으면 v0로 넘어가지 않고 시작을 멈춘다
        # (참여자 결과가 요청한 매핑과 달라지는 것을 막음, Codex CP2 #3). 세션 도중 확정 시점에 v1 build가 예외를
        # 내는 경우는 strict여도 Session._build_scene이 v0로 대체하고 meta.mapping·연구자 알림을 남긴다
        # (이미 진행 중인 참여자 세션을 끊지 않기 위함).
        try:
            self.scene_builders["v1"] = SceneSpecBuilderV1(self.analyzer)
        except Exception as exc:  # noqa: BLE001 — strict가 아니면 개선 매핑을 못 불러도 v0로 면담은 이어 간다
            self.mapping_load_error = f"{type(exc).__name__}: {exc}"
            if cfg.mapping.strict and cfg.mapping.mode == "v1":
                raise RuntimeError(
                    f"개선 매핑(v1)을 불러오지 못했습니다: {self.mapping_load_error}. "
                    "[mapping] strict = true라 v0로 대체하지 않고 시작을 멈춥니다. "
                    "원인을 고치거나, 개발·시연에서만 strict = false로 두세요.") from exc
            self.warnings.append(f"개선 매핑(v1)을 불러오지 못해 v0로 대체합니다: {self.mapping_load_error}")
        # 매핑 v2(scene_builder_v2.py, D1·D2 수정)는 mode = "v2"로 요청했을 때만 만든다(기본 v1 세션의 동작·기록은 그대로).
        # 실패 처리는 v1과 같다: strict면 시작을 멈추고, 아니면 v0로 대체하고 경고를 남긴다.
        if cfg.mapping.mode == "v2":
            try:
                self.scene_builders["v2"] = SceneSpecBuilderV2(self.analyzer)
            except Exception as exc:  # noqa: BLE001
                self.mapping_load_error = f"{type(exc).__name__}: {exc}"
                if cfg.mapping.strict:
                    raise RuntimeError(
                        f"매핑 v2를 불러오지 못했습니다: {self.mapping_load_error}. "
                        "[mapping] strict = true라 v0로 대체하지 않고 시작을 멈춥니다.") from exc
                self.warnings.append(f"매핑 v2를 불러오지 못해 v0로 대체합니다: {self.mapping_load_error}")
        self.scene_builder = self.scene_builders.get(cfg.mapping.mode) or self.scene_builders["v0"]
        self.clarify_validator = Validator(
            self.protocol, self.lexicon, self.safety, self.analyzer, self.schema, guard=None,
            strict_novel_content=cfg.validator.strict_novel_content,
            depth_anchor_block=cfg.validator.l5_depth != "off",
            max_anchor_eojeol=cfg.validator.max_anchor_eojeol,
        )
        # 심상 유지(표류) 판정 — 규칙만, LLM 없음(docs/drift-design.md). 회상 확인·자기보고는 고정 문구가 있을 때만 켠다.
        self.drift: DriftAssessor | None = None
        self.drift_recall = self.drift_self_report = False
        if cfg.drift.enabled:
            try:
                self.drift = DriftAssessor.from_runtime(self)
            except Exception as exc:  # noqa: BLE001 — 판정기를 못 만들어도 면담은 이어 간다
                self.warnings.append(f"표류 판정기를 만들지 못했습니다: {type(exc).__name__}: {exc}")
        # status = "draft"인 문구는 [drift] allow_draft_phrases = true일 때만 쓴다(원칙 7, Codex CP2 #12).
        for flag, phrase in (("recall_check", "recall_check"), ("self_report", "self_report_drift")):
            if not getattr(cfg.drift, flag):
                continue
            if phrase not in self.protocol.phrases:
                self.warnings.append(f"[drift] {flag}를 켰지만 프로토콜 {self.protocol.version}에 '{phrase}' 문구가 없어 "
                                     "끕니다(elicitation_protocol.v1.1.json 이상 필요).")
                continue
            if self.protocol.phrase_meta(phrase)["status"] == "draft" and not cfg.drift.allow_draft_phrases:
                self.warnings.append(f"[drift] {flag}를 켰지만 프로토콜 {self.protocol.version}의 '{phrase}' 문구가 "
                                     "status = draft(IRB·팀 검토 전)라 끕니다. 개발·시연에서만 쓰려면 "
                                     "[drift] allow_draft_phrases = true.")
                continue
            setattr(self, "drift_recall" if flag == "recall_check" else "drift_self_report", True)
        self.persist_logs = persist_logs
        self.sessions: dict[str, "Session"] = {}
        self._lock = threading.Lock()
        # 면담 뒤 데스크톱 단계(후보 선택·조절·사전 측정, selection.py). 면담 밖이라 LLM·검증기를 쓰지 않는다.
        # 문구·값 표는 언제나 읽어 두고(가벼움), 단계를 여는지는 [selection] enabled가 정한다.
        self.selection_protocol = SelectionProtocol(cfg.selection.protocol)
        self.candidate_table = load_candidate_table(shared("lexicon", cfg.selection.table))
        self.preview = PreviewService(cfg.preview, cfg.log_dir, CHATBOT_DIR, self.candidate_table["defaults"])
        if cfg.selection.enabled:
            n = self.selection_protocol.info()["draftCount"]
            if n:
                self.warnings.append(f"[selection] 후보·조절·사전 측정 문구 {n}개가 초안(status draft)입니다(X35: 화면·기록에 표시).")
            if self.preview.reason:
                self.warnings.append(f"[preview] {self.preview.reason}")

    def header(self, condition: str) -> dict:
        return {
            "protocol": {
                **self.prompts.info(),
                "lexiconVersion": self.lexicon.version,
                "safetyLexiconVersion": self.safety.version,
                "controllerVersion": CONTROLLER_VERSION,
                "protocolId": self.protocol.protocol_id,
                "protocolVersion": self.protocol.version,
            },
            "model": self.backend.info() if condition == "chatbot" else None,
            "guard": self.guard.info(),
            "analyzer": self.analyzer.info(),
            "validator": {"strictNovelContent": self.cfg.validator.strict_novel_content,
                          "l5Depth": self.cfg.validator.l5_depth, "maxAnchorEojeol": self.cfg.validator.max_anchor_eojeol,
                          "maxRegenerations": self.cfg.llm.max_regenerations},
        }

    def info(self) -> dict:
        return {
            "config": self.cfg.source,
            "conditions": {c: self.protocol.condition(c)["label"] for c in self.protocol.conditions()},
            "defaultCondition": self.cfg.interview.condition,
            "backend": {"type": self.cfg.llm.backend, "ok": self.backend_ok, "message": self.backend_msg,
                        **self.backend.info()},
            "guard": self.guard.info(),
            "analyzer": self.analyzer.info(),
            "lexicon": self.lexicon.info(),
            "protocol": self.protocol.info(),
            "prompts": self.prompts.info(),
            "mapping": {"mode": self.cfg.mapping.mode, "saveBoth": self.cfg.mapping.save_both,
                        "clarifyLoop": self.cfg.mapping.clarify_loop, "strict": self.cfg.mapping.strict,
                        "builders": {k: b.info() for k, b in self.scene_builders.items() if hasattr(b, "info")},
                        "loadError": self.mapping_load_error},
            "drift": {"enabled": self.drift is not None, "recallCheck": self.drift_recall,
                      "selfReport": self.drift_self_report, "allowDraftPhrases": self.cfg.drift.allow_draft_phrases,
                      **(self.drift.info() if self.drift else {})},
            "selection": {"enabled": self.cfg.selection.enabled, **self.selection_protocol.info(),
                          "tableVersion": self.candidate_table["tableVersion"]},
            "preview": self.preview.info(),
            "warnings": self.warnings,
        }

    def new_session(self, condition: str | None = None, session_id: str | None = None,
                    participant_id: str | None = None) -> "Session":
        condition = condition or self.cfg.interview.condition
        if session_id is None:
            session_id = datetime.now().strftime("S%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        if not SESSION_ID_RE.match(session_id):
            raise SessionError("세션 ID는 영문·숫자·_·- 1–40자만 됩니다(가명 ID 사용).")
        if participant_id is not None and not SESSION_ID_RE.match(participant_id):
            raise SessionError("참여자 ID는 영문·숫자·_·- 1–40자만 됩니다(가명 ID 사용).")
        with self._lock:
            if session_id in self.sessions:
                raise SessionError(f"이미 있는 세션 ID입니다: {session_id}")
            s = Session(self, condition, session_id, participant_id=participant_id)
            self.sessions[session_id] = s
        return s


# ── 세션 ────────────────────────────────────────────────────────────────────
class Session:
    def __init__(self, rt: Runtime, condition: str, session_id: str, participant_id: str | None = None):
        self.rt, self.cfg, self.p = rt, rt.cfg, rt.protocol
        self.p.condition(condition)  # 모르는 조건이면 여기서 오류
        if condition == "chatbot" and not rt.backend_ok:
            raise SessionError(f"조건 2(챗봇)를 시작할 수 없습니다: {rt.backend_msg}")
        self.id, self.condition = session_id, condition
        self.participant_id = participant_id   # 가명. 피험자 내 설계에서 한 사람의 여러 세션을 묶는다(장면 meta에만 씀)
        self.scene_spec: dict | None = None
        self.steps: list[Step] = self.p.sequence(condition)
        self.idx = 0
        self.step_state: dict[int, dict] = defaultdict(dict)
        self.llm_total = 0
        self.max_total = self.p.max_llm_turns_total(condition)
        self.state = "intro"            # intro | interview | soft_check | confirm | done | stopped | crisis | withdrawn
        self.awaiting = "start"         # start | reply | soft_check | confirm | none
        self.messages: list[dict] = []
        self.participant_texts: list[str] = []
        self.transcript: list[TranscriptLine] = []
        self.asked: list[dict] = []
        self.ack: set[str] = set()
        self.pending_soft: list[str] = []
        self.depth_strong_count = 0
        self.last_no_more = False
        self.last_depth_strong = False
        self.confirm_draft: str | None = None
        self.clarify: dict | None = None           # 확인 질문 루프 상태(config [mapping] clarify_loop)
        self.recall_asked = False                  # 회상 확인(config [drift] recall_check)을 이미 물었는지
        self.selection_flow: SelectionFlow | None = None   # 면담 뒤 후보·조절·사전 측정(config [selection])
        self.lock = threading.RLock()
        self.log = SessionLog(session_id, condition, rt.header(condition), self.cfg.log_dir, persist=rt.persist_logs)
        self._say_fixed("intro", stage=None, kind="info")
        self._save()

    # ── 출력 도우미 ─────────────────────────────────────────────────────────
    @property
    def step(self) -> Step | None:
        return self.steps[self.idx] if self.idx < len(self.steps) else None

    @property
    def stage(self) -> str | None:
        s = self.step
        return s.stage if s else None

    def _say(self, text: str, *, speaker: str, source: str, stage: str | None, kind: str = "question", **turn_fields) -> dict:
        turn = self.log.add_turn(speaker=speaker, source=source, stage=stage, text=text, **turn_fields)
        self.messages.append({"speaker": "bot", "text": text, "kind": kind, "source": source, "i": turn["i"]})
        if kind in ("question", "check") and stage:
            self.transcript.append(TranscriptLine("interviewer" if speaker == "interviewer" else "guide", text))
        return turn

    def _say_fixed(self, phrase_id: str, *, stage: str | None, kind: str = "question",
                   speaker: str = "system", **turn_fields) -> dict:
        fmt = {"researcher_contact": self.cfg.session.researcher_contact} if phrase_id == "crisis" else {}
        text = self.p.phrase(phrase_id, **fmt)
        return self._say(text, speaker=speaker, source=f"fixed:{phrase_id}", stage=stage, kind=kind,
                         phraseStatus=self.p.phrase_meta(phrase_id)["status"], **turn_fields)

    def _alert(self, kind: str, detail: str, turn: int | None, severity: str = "warning") -> None:
        self.log.add_alert(kind, detail, turn, severity)
        log_fn = alert_logger.critical if severity == "critical" else alert_logger.warning
        log_fn("[%s] %s: %s (turn %s)", self.id, kind, detail, turn)

    def _save(self) -> None:
        self.log.save()

    # ── 공개 동작 ───────────────────────────────────────────────────────────
    def start(self) -> dict:
        with self.lock:
            if self.awaiting != "start":
                raise SessionError("이미 시작한 세션입니다.")
            self.log.add_turn(speaker="participant", source="control:start", stage=None, text="[시작]")
            self.state = "interview"
            self._advance()
            self._save()
            return self.view()

    def reply(self, text: str, source: str = "typed") -> dict:
        with self.lock:
            if self.awaiting != "reply":
                raise SessionError("지금은 답을 받을 차례가 아닙니다.")
            text = normalize(text)
            if not text:
                raise SessionError("아직 적은 내용이 없어요. 넘어가려면 [넘어가기]를 눌러 주세요.")
            step, stage = self.step, self.stage
            verdict = self.rt.guard.check_input(text)
            safety = self.rt.safety
            no_more = safety.is_no_more(text)
            depth = safety.depth(text)
            flags = {"noMore": no_more, "delegation": safety.is_delegation(text),
                     "depthStrong": [d["match"] for d in depth["strong"]], "depthWeak": [d["match"] for d in depth["weak"]]}
            turn = self.log.add_turn(
                speaker="participant", source=source, stage=stage, text=text,
                guard=verdict.label, guardDetail=verdict.to_log(),
                crisisKeyword=any(h["tier"] == "crisis" for h in verdict.keyword_hits), flags=flags,
            )
            self.messages.append({"speaker": "participant", "text": text, "i": turn["i"]})
            self.transcript.append(TranscriptLine("participant", text))

            if verdict.level == "crisis":                       # L4: LLM 호출 없이 고정 문구
                self._crisis(verdict, turn["i"])
                return self.view()
            if safety.is_stop(text):
                self._stop("participant_stop")
                return self.view()
            if self.state == "clarify":                          # 확인 질문의 답(고정 틀, LLM 없음)
                if verdict.level == "soft":
                    self._alert("clarify_soft", "확인 질문의 답에 확인 필요 표현 — 답을 장면에 쓰지 않고 넘어감", turn["i"])
                self._on_clarify_reply(text, no_more or verdict.level == "soft", turn["i"])
                self._save()
                return self.view()
            if flags["delegation"]:
                self.log.add_alert("delegation", "참여자가 판단을 맡김(규칙 8) — 면담자는 답을 제안하지 않는다", turn["i"], "info")

            if not no_more:
                self.participant_texts.append(text)
            self.last_no_more = no_more
            self.last_depth_strong = bool(depth["strong"])
            self._on_reply(step, text, no_more)

            if verdict.level == "soft":
                soft = [r for r in verdict.reasons if r.startswith("kw:") or r in ("model:S6", "model:controversial")]
                new = [r for r in soft if r not in self.ack]
                if new:
                    if verdict.alert:
                        self._alert("soft_check", f"확인 문구 발동: {', '.join(new)}", turn["i"])
                    self._soft_check(new)
                    self._save()
                    return self.view()
                turn["flags"]["softCheckSuppressed"] = soft  # 이미 [계속]을 고른 표현
            self._advance()
            self._save()
            return self.view()

    def act(self, action: str, text: str | None = None) -> dict:
        """버튼 동작: start | skip | continue | stop | confirm | edit | withdraw"""
        with self.lock:
            if action == "start":
                return self.start()
            if action == "withdraw":
                return self.withdraw()
            if self.awaiting == "none":
                raise SessionError("이미 끝난 세션입니다.")
            if action == "stop":
                self.log.add_turn(speaker="participant", source="control:stop", stage=self.stage, text="[그만]")
                self._stop("participant_stop")
                return self.view()
            if self.awaiting == "recall":
                return self._on_recall(action)
            if self.awaiting == "self_report":
                return self._on_self_report(action)
            if action == "skip":
                return self.reply("넘어갈게요", source="control:skip")
            if action == "continue" and self.awaiting == "soft_check":
                self.log.add_turn(speaker="participant", source="control:continue", stage=self.stage, text="[계속]")
                self.ack.update(self.pending_soft)
                self.pending_soft = []
                self.state = "interview"
                self._advance()
                self._save()
                return self.view()
            if self.awaiting == "confirm" and action in ("confirm", "edit"):
                if action == "confirm":
                    self.log.add_turn(speaker="participant", source="control:confirm", stage=None, text="[이대로 맞아요]")
                    self._confirmed(self.confirm_draft or "", edited=False)
                else:
                    edited = normalize(text or "") if text and "\n" not in text else "\n".join(normalize(t) for t in (text or "").split("\n") if normalize(t))
                    if not edited:
                        raise SessionError("고친 텍스트가 비어 있습니다.")
                    verdict = self.rt.guard.check_input(edited)
                    turn = self.log.add_turn(speaker="participant", source="control:edit", stage=None, text=edited,
                                             guard=verdict.label, guardDetail=verdict.to_log())
                    if verdict.level == "crisis":
                        self._crisis(verdict, turn["i"])
                        return self.view()
                    self._confirmed(edited, edited=True)
                return self.view()
            raise SessionError(f"지금은 '{action}'을(를) 할 수 없습니다 (대기 중: {self.awaiting}).")

    def withdraw(self) -> dict:
        """참여자 철회 — 로그 파일을 지우고 메모리 내용도 비운다(2D 설문의 '응답 폐기' 선택지)."""
        with self.lock:
            if self.state not in ("done", "stopped"):
                raise SessionError("면담이 끝난 뒤에 폐기할 수 있습니다. 위기 대응으로 멈춘 세션은 안전 기록을 위해 연구자가 처리합니다.")
            self.log.delete()
            self.log.persist = False
            self._delete_scene()
            delete_selection_dir(self.cfg.log_dir, self.id)
            if self.selection_flow is not None:
                self.selection_flow.persist = False
            self.selection_flow = None
            self.log.data.update(turns=[], alerts=[], capture={}, confirmedText=None, confirmation=None,
                                 extraction=None, events=[], endedBy="withdrawn", sceneSpec=None, drift=None)
            self.participant_texts, self.transcript, self.asked, self.confirm_draft = [], [], [], None
            self.messages = [{"speaker": "bot", "text": self.p.phrase("withdrawn"), "kind": "info", "source": "fixed:withdrawn"}]
            self.state, self.awaiting = "withdrawn", "none"
            return self.view()

    def selection(self, create: bool = True) -> SelectionFlow | None:
        """면담 뒤 단계(selection.py). 확정까지 마친 세션(endedBy = completed)에서만 연다."""
        with self.lock:
            if self.selection_flow is not None or not create:
                return self.selection_flow
            if not self.cfg.selection.enabled:
                raise SelectionError("후보 단계가 꺼져 있습니다([selection] enabled = false). 새 흐름은 --config v4.")
            if self.state != "done" or self.log.data.get("endedBy") != "completed":
                raise SelectionError("면담을 끝내고 확정한 뒤에 후보 단계로 갑니다.")
            if self.scene_spec is None:
                raise SelectionError("장면 기술(SceneSpec)이 없어 후보를 만들 수 없습니다.")
            self.selection_flow = SelectionFlow(self, self.rt)
            return self.selection_flow

    def add_event(self, kind: str, payload: dict) -> dict:
        with self.lock:
            if self.state == "withdrawn":
                raise SessionError("폐기된 세션입니다.")
            ev = self.log.add_event(kind, payload)
            self._save()
            return ev

    # ── 진행 ────────────────────────────────────────────────────────────────
    def _on_reply(self, step: Step, text: str, no_more: bool) -> None:
        st = self.step_state[self.idx]
        if step.type == "fixed":
            if step.capture == "bodyRelation":
                self.log.data["capture"]["bodyRelation"] = parse_body_relation(text, self.rt.lexicon, no_more)
            if step.phrase == "opening":
                self.log.data["capture"]["findModality"] = find_modality(text, self.rt.lexicon)
            st["answered"] = True
            self.idx += 1
        elif step.type == "llm":
            if no_more:
                st["done"] = True
        elif step.type == "probes":
            st["current"] = None

    def _advance(self) -> None:
        while self.idx < len(self.steps):
            step, st = self.steps[self.idx], self.step_state[self.idx]
            if step.type == "fixed":
                if st.get("asked"):
                    self.idx += 1
                    continue
                self._say_fixed(step.phrase, stage=step.stage)
                st["asked"] = True
                self.awaiting = "reply"
                return
            if step.type == "llm":
                used = st.get("turns", 0)
                skip = (self.condition != "chatbot" or step.max_turns <= 0 or st.get("done") or used >= step.max_turns
                        or (self.max_total is not None and self.llm_total >= self.max_total)
                        or not self.participant_texts or self.last_no_more)
                if skip:
                    st["done"] = True
                    self.idx += 1
                    continue
                outcome = self._llm_turn(step, st)
                if outcome == "asked":
                    self.awaiting = "reply"
                    return
                if outcome == "soft_check":
                    return
                st["done"] = True          # ready_to_advance
                self.idx += 1
                continue
            if step.type == "probes":
                covered = self.rt.lexicon.categories_in("\n".join(self.participant_texts))
                asked = st.setdefault("asked", [])
                nxt = next((pr for pr in self.p.probes
                            if pr["id"] not in asked and not (set(pr["coveredByCategories"]) & covered)), None)
                if nxt is None:
                    st["skipped"] = [pr["id"] for pr in self.p.probes if pr["id"] not in asked]
                    self.log.data["capture"]["probes"] = {"asked": asked, "skippedAsCovered": st["skipped"]}
                    self.idx += 1
                    continue
                asked.append(nxt["id"])
                st["current"] = nxt["id"]
                self._say_fixed(nxt["phrase"], stage=step.stage, probe=nxt["id"])
                self.awaiting = "reply"
                return
            if step.type == "confirm":
                if self._ask_recall():
                    return
                self._enter_confirm()
                return
            raise RuntimeError(f"모르는 단계 종류: {step.type}")

    def _llm_turn(self, step: Step, st: dict) -> str:
        stage = step.stage
        turn_no = st.get("turns", 0) + 1
        cfg = self.cfg
        # L5: 기억 서사·외상 표지 → LLM 대신 고정 문구, 반복되면 확인 문구
        if cfg.validator.l5_depth == "present_focus" and self.last_depth_strong:
            self.depth_strong_count += 1
            self.last_depth_strong = False
            if self.depth_strong_count >= 2:
                self._alert("depth", "기억·과거 장면 서술이 반복됨(L5) — 확인 문구로 전환", len(self.log.turns) - 1)
                self._soft_check(["depth:repeated"])
                return "soft_check"
            self._say_fixed("depth_present", stage=stage, speaker="interviewer",
                            checks={"passed": True, "reasons": ["L5:present_focus"], "regenerations": 0, "fallback": False})
            self.asked.append({"template": "depth_present", "utterance": self.p.phrase("depth_present"), "anchor": ""})
            st["turns"] = turn_no
            self.llm_total += 1
            return "asked"

        allowed = self.p.allowed_templates(stage)
        cands = anchor_candidates(self.participant_texts, self.rt.lexicon, self.rt.analyzer, self.rt.safety,
                                  used={a.get("anchor", "") for a in self.asked})
        pctx = PromptContext(stage=stage, turn_no=turn_no, max_turns=step.max_turns, allowed_templates=allowed,
                             transcript=list(self.transcript), participant_texts=list(self.participant_texts),
                             asked=[dict(a) for a in self.asked], anchor_candidates=cands)
        last_p = next((t for t in reversed(self.log.turns) if t.get("speaker") == "participant" and t.get("guardDetail")), None)
        vctx = TurnContext(stage, allowed, list(self.participant_texts), self.participant_texts[-1],
                           ((last_p or {}).get("guardDetail") or {}).get("model"))
        attempts: list[dict] = []
        feedback: list[str] = []
        for attempt in range(cfg.llm.max_regenerations + 1):
            pctx.feedback = feedback if cfg.llm.retry_feedback else []
            req = GenerationRequest(system=self.rt.prompts.system(stage), user=self.rt.prompts.user(pctx),
                                    seed=cfg.llm.seed + attempt, attempt=attempt, context=pctx)
            try:
                res = self.rt.backend.generate(req)
            except Exception as exc:  # LLM이 죽어도 면담은 고정 문구로 이어 간다
                attempts.append({"attempt": attempt, "seed": req.seed, "raw": "", "parsed": None, "passed": False,
                                 "reasons": [f"LLM:error:{str(exc)[:160]}"], "reasonsText": [f"LLM 호출 오류: {str(exc)[:160]}"],
                                 "latencyMs": 0})
                self._alert("llm_error", str(exc)[:200], None)
                feedback = []
                continue
            r = self.rt.validator.check(res.raw, vctx)
            attempts.append({"attempt": attempt, "seed": req.seed, "raw": res.raw, "parsed": r.parsed,
                             "passed": r.passed, "reasons": r.reasons, "reasonsText": [describe(x) for x in r.reasons],
                             "latencyMs": res.latency_ms, "meta": res.meta, "guard": r.guard, "notes": r.notes})
            checks = {"passed": r.passed, "reasons": r.reasons, "regenerations": attempt, "fallback": False}
            if r.l2_signal:                                    # L2 보조 신호 → 확인 문구
                turn = self.log.add_turn(speaker="interviewer", source="llm", stage=stage, text="", output=r.parsed,
                                         checks={**checks, "l2Signal": True}, attempts=attempts)
                self._alert("risk_signal", f"LLM risk_signal={r.parsed['risk_signal']}, move={r.parsed['move']}", turn["i"])
                self._soft_check([f"llm:{r.parsed['risk_signal']}"])
                return "soft_check"
            if r.passed:
                move = r.parsed["move"]
                if move == "ask":
                    self._say(r.parsed["utterance"], speaker="interviewer", source="llm", stage=stage,
                              output=r.parsed, checks=checks, attempts=attempts)
                    self.asked.append({"template": r.parsed["template"], "utterance": r.parsed["utterance"],
                                       "anchor": r.parsed["anchor_quote"]})
                    st["turns"] = turn_no
                    self.llm_total += 1
                    return "asked"
                if move == "ready_to_advance":
                    self.log.add_turn(speaker="interviewer", source="llm", stage=stage, text="", output=r.parsed,
                                      checks=checks, attempts=attempts, note="ready_to_advance — 참여자에게 나가지 않음")
                    return "advance"
                if move == "redirect":
                    self._say_fixed("redirect", stage=stage, speaker="interviewer", output=r.parsed,
                                    checks=checks, attempts=attempts)
                    self.asked.append({"template": "redirect", "utterance": self.p.phrase("redirect"), "anchor": ""})
                    st["turns"] = turn_no
                    self.llm_total += 1
                    return "asked"
            if r.hard_fail:                                    # V8 → 재생성 없이 고정 문구
                break
            feedback = [describe(x) for x in r.reasons]
        last_reasons = attempts[-1]["reasons"] if attempts else []
        # '방금 말씀하신 것에 대해 더 있나요?'는 직전 발화가 기억 서사이면 그 장면으로 더 들어가게 한다.
        # 그럴 때는 L5 고정 문구로 지금 떠오른 것에 머물게 한다.
        depth_related = any(r.startswith("V9") for a in attempts for r in a["reasons"])             or bool(self.rt.safety.depth(self.participant_texts[-1])["strong"])
        phrase = "depth_present" if depth_related and cfg.validator.l5_depth != "off" else "fallback"
        self._say_fixed(phrase, stage=stage, speaker="interviewer", output=None, attempts=attempts,
                        checks={"passed": False, "reasons": last_reasons, "regenerations": max(0, len(attempts) - 1), "fallback": True})
        self.asked.append({"template": phrase, "utterance": self.p.phrase(phrase), "anchor": ""})
        st["turns"] = turn_no
        self.llm_total += 1
        return "asked"

    # ── 분기 ────────────────────────────────────────────────────────────────
    def _soft_check(self, reasons: list[str]) -> None:
        self.pending_soft = reasons
        self.state, self.awaiting = "soft_check", "soft_check"
        self._say_fixed("soft_check", stage=self.stage, kind="check", reasons=reasons)

    def _crisis(self, verdict: GuardVerdict, turn_i: int) -> None:
        self._say_fixed("crisis", stage=self.stage, kind="crisis")
        self._alert("crisis", f"위기 대응 발동 — LLM 호출 중지, 연구자 즉시 호출 ({', '.join(verdict.reasons)})", turn_i, "critical")
        self.state, self.awaiting = "crisis", "none"
        self.log.end("crisis")
        self._save()

    def _stop(self, by: str) -> None:
        if self.state == "clarify" and self.clarify:     # 이미 [이대로 맞아요]를 눌렀다 → 확정 텍스트로 장면은 남긴다
            self.clarify["stopped"] = True
            self._record_confirmation(self.clarify["baseText"], self.clarify["edited"])
            self._write_scene(self.clarify["baseText"])
            self._record_drift()
        if self.awaiting == "self_report":                # 확정은 끝났다 → 자기보고 값만 비운다(물은 기록은 남김)
            d = self._drift_log()
            sr = d.get("selfReport") if isinstance(d.get("selfReport"), dict) else {}
            sr.update(value=None, skipped="stop", selfReportDrift=None, at=now_iso())
            d["selfReport"] = sr
        if self.awaiting == "recall":                     # 회상 확인 대기 중 중단: 물은 기록에 중단 표시
            d = self._drift_log()
            rc = d.get("recallCheck") if isinstance(d.get("recallCheck"), dict) else {}
            rc.update(answer=None, skipped="stop", at=now_iso())
            d["recallCheck"] = rc
        self._say_fixed("stopped", stage=self.stage, kind="info")
        self.state, self.awaiting = "stopped", "none"
        self.log.end(by)
        self._save()

    def _enter_confirm(self) -> None:
        self.confirm_draft = "\n".join(self.participant_texts)
        self._say_fixed("confirm_intro", stage=None, kind="confirm", draft=self.confirm_draft)
        self.state, self.awaiting = "confirm", "confirm"

    def _record_confirmation(self, text: str, edited: bool) -> None:
        self.log.data["confirmedText"] = text
        self.log.data["confirmation"] = {"edited": edited, "draft": self.confirm_draft, "at": now_iso()}
        self.log.data["extraction"] = self.rt.extractor.run(text, self.log.data["capture"].get("bodyRelation"))

    def _confirmed(self, text: str, edited: bool) -> None:
        """[이대로 맞아요]/[고칠게요] 뒤. 확인 질문 루프가 켜져 있고 물을 말이 있으면 먼저 묻는다."""
        if self.cfg.mapping.clarify_loop and self._start_clarify(text, edited):
            return
        self._finish(text, edited)

    def _finish(self, text: str, edited: bool) -> None:
        self._record_confirmation(text, edited)
        self._write_scene(text)
        self._record_drift()
        if self._ask_self_report():
            self._save()
            return
        self._close()

    def _close(self) -> None:
        self._say_fixed("closing", stage=None, kind="closing")
        self.state, self.awaiting = "done", "none"
        self.log.end("completed")
        self._save()

    # ── 심상 유지(표류) 판정 · 회상 확인 · 자기보고 (docs/drift-design.md, LLM 없음) ─────────
    def _drift_log(self) -> dict:
        d = self.log.data.get("drift")
        if not isinstance(d, dict):
            d = {"enabled": self.rt.drift is not None, "assessment": None, "summary": None,
                 "recallCheck": None, "selfReport": None}
            self.log.data["drift"] = d
        return d

    def _record_drift(self) -> None:
        """확정 직후: 참여자 턴(단계 표시 포함)만으로 단계별 스냅샷 → 1차 쌍 판정. 실패해도 면담 종료를 막지 않는다."""
        if self.rt.drift is None:
            return
        d = self._drift_log()
        try:
            edited = bool((self.log.data.get("confirmation") or {}).get("edited"))
            a = self.rt.drift.assess(participant_turns(self.log.turns, self.log.data.get("clarify")),
                                     confirmation_edited=edited)
            d["assessment"], d["summary"] = a, summarize(a)
        except Exception as exc:  # noqa: BLE001
            d["assessment"], d["error"] = None, f"{type(exc).__name__}: {exc}"[:300]
            self._alert("drift_error", d["error"], None)

    def _ask_recall(self) -> bool:
        """Flesh out 뒤, 확정 요약 전에 한 번: 지금 떠오르는 것도 그 '{X}'인가요? (X = 참여자의 형상 명사 원문)"""
        if not self.rt.drift_recall or self.recall_asked or self.rt.drift is None:
            return False
        self.recall_asked = True
        d = self._drift_log()
        anchor = self.rt.drift.recall_anchor(participant_turns(self.log.turns),
                                             max_eojeol=self.cfg.validator.max_anchor_eojeol or 3)
        if anchor is None:
            d["recallCheck"] = {"asked": False, "reason": "첫 단계에 이름 붙인 형상 명사('X 같은 게'·'X예요')가 없음"}
            return False
        x = anchor["x"]
        safety = self.rt.safety
        if safety.crisis_hits(x) or safety.has_depth_marker(x):
            d["recallCheck"] = {"asked": False, "reason": "인용할 말에 안전·깊이 표지", "x": x}
            return False
        turn = self._say(self.p.phrase("recall_check", X=x), speaker="system", source="fixed:recall_check",
                         stage="recall_check", kind="check", phraseStatus=self.p.phrase_meta("recall_check")["status"],
                         anchor=x)
        d["recallCheck"] = {"asked": True, "x": x, "anchorTurn": anchor["i"], "anchorStage": anchor["stage"],
                            "questionTurn": turn["i"], "answer": None}
        self.state, self.awaiting = "recall", "recall"
        return True

    def _recall_options(self) -> list[dict]:
        return list(self.p.phrases["recall_check"].get("options") or [])

    def _on_recall(self, action: str) -> dict:
        opts = {f"recall:{o['id']}": o for o in self._recall_options()}
        if action not in opts:
            raise SessionError(f"지금은 '{action}'을(를) 할 수 없습니다 (대기 중: recall).")
        o = opts[action]
        turn = self.log.add_turn(speaker="participant", source=f"control:{action}", stage="recall_check", text=o["label"])
        rc = self._drift_log()["recallCheck"]
        rc.update(answer=None if o["id"] == "skip" else o["id"], skipped=o["id"] == "skip", turn=turn["i"], at=now_iso())
        self.messages.append({"speaker": "participant", "text": o["label"], "i": turn["i"]})
        self.state = "interview"
        self._enter_confirm()
        self._save()
        return self.view()

    def _ask_self_report(self) -> bool:
        if not self.rt.drift_self_report:
            return False
        turn = self._say_fixed("self_report_drift", stage=None, kind="check")
        self._drift_log()["selfReport"] = {"asked": True, "questionTurn": turn["i"], "value": None,
                                           "protocolVersion": self.p.version}
        self.state, self.awaiting = "self_report", "self_report"
        return True

    def _self_report_scale(self) -> dict:
        return self.p.phrases["self_report_drift"].get("scale") or {"min": 1, "max": 7, "anchors": {}}

    def _on_self_report(self, action: str) -> dict:
        sc = self._self_report_scale()
        valid = {f"self_report:{v}" for v in range(int(sc["min"]), int(sc["max"]) + 1)} | {"self_report:skip"}
        if action not in valid:
            raise SessionError(f"지금은 '{action}'을(를) 할 수 없습니다 (대기 중: self_report).")
        raw = action.split(":", 1)[1]
        value = None if raw == "skip" else int(raw)
        turn = self.log.add_turn(speaker="participant", source=f"control:{action}", stage=None,
                                 text="[넘어가기]" if value is None else str(value))
        self.messages.append({"speaker": "participant", "text": turn["text"], "i": turn["i"]})
        sr = self._drift_log()["selfReport"]
        cut = DRIFT_PARAMS["selfReportDriftMax"]
        sr.update(value=value, skipped=value is None, turn=turn["i"], at=now_iso(),
                  selfReportDrift=None if value is None else value <= cut, driftCutoff=cut)
        self._close()
        return self.view()

    # ── 확인 질문 루프 (선택, 고정 틀 what_kind만 · LLM 없음) ─────────────────
    def _start_clarify(self, text: str, edited: bool) -> bool:
        v1 = self.rt.scene_builders.get("v1")
        info: dict = {"enabled": True, "template": "what_kind", "baseText": text, "edited": edited, "targets": [],
                      "turns": [], "appended": [], "finalText": None}
        self.log.data["clarify"] = info
        if v1 is None:
            info["skipped"] = "v1 매핑 없음"
            return False
        try:
            spec = v1.build(text)
        except Exception as exc:  # noqa: BLE001
            info["skipped"] = f"v1 매핑 오류: {type(exc).__name__}: {exc}"
            return False
        info["targets"] = clarify_targets(spec, normalize_confirmed(text), max_n=max(0, self.cfg.mapping.clarify_max),
                                          analyzer=self.rt.analyzer)
        if not info["targets"]:
            return False
        self.clarify = info
        self.state = "clarify"
        return self._ask_clarify()

    def _ask_clarify(self) -> bool:
        """다음 대상 X로 what_kind 질문을 낸다. 검증기(V3·V4·V5·V7·V9)를 통과한 질문만 나간다."""
        info = self.clarify
        texts = [t for t in normalize_confirmed(info["baseText"]).split("\n") if t] + list(info["appended"])
        while info["targets"]:
            target = info["targets"].pop(0)
            utt, raw = question_json(self.p, target["x"])
            ctx = TurnContext("flesh_out", ["what_kind"], texts, texts[-1])
            r = self.rt.clarify_validator.check(raw, ctx)
            rec = {"x": target["x"], "why": target["why"], "question": utt, "passed": r.passed, "reasons": r.reasons}
            info["turns"].append(rec)
            if not r.passed:
                continue
            self._say(utt, speaker="interviewer", source="clarify:what_kind", stage="clarify",
                      checks={"passed": True, "reasons": [], "regenerations": 0, "fallback": False}, anchor=target["x"])
            self.awaiting = "reply"
            return True
        return False

    def _on_clarify_reply(self, text: str, skip: bool, turn_i: int) -> None:
        info = self.clarify
        asked = next((t for t in reversed(info["turns"]) if t["passed"] and "answer" not in t), None)
        if asked is not None:
            asked["answer"] = text
            asked["used"] = not skip
            asked["turn"] = turn_i
        if not skip:
            info["appended"].append(text)
        if self._ask_clarify():
            return
        final = info["baseText"] if not info["appended"] else "\n".join([info["baseText"], *info["appended"]])
        info["finalText"] = final
        self.clarify = None
        self._finish(final, info["edited"])

    # ── 장면 기술 (확정 텍스트 → SceneSpec v2 → Unity) ──────────────────────
    @property
    def scene_path(self):
        return self.cfg.scenes_dir / f"{self.id}.json"

    def variant_path(self, mapper: str):
        return self.cfg.scenes_dir / f"{self.id}.{mapper}.json"

    def _build_scene(self, text: str) -> tuple[dict, dict]:
        """주 매핑으로 만든다. v1(또는 끼운 매핑)이 예외를 내면 v0 결과에 대체 사실을 남겨 쓴다(AC-3.7).
        [mapping] strict와 상관없이 그렇다: strict는 시작 시점(Runtime)의 v1 생성 실패만 멈추고, 여기(세션 도중
        확정 시점)의 예외는 참여자 세션을 끊지 않도록 v0 대체 + meta.mapping + 연구자 알림으로 남긴다."""
        rt, kw = self.rt, {"session_id": self.id, "participant_id": self.participant_id, "condition": self.condition}
        v0 = rt.scene_builders["v0"]
        primary = rt.scene_builder
        requested = self.cfg.mapping.mode if primary is v0 else getattr(primary, "mapper_id", "custom")
        if primary is v0 and requested != "v0":            # v1을 불러오지 못한 경우
            reason = f"매핑 {requested}을(를) 불러오지 못함: {rt.mapping_load_error}"
            return fallback_spec(v0.build(text, **kw), requested, reason), {"requested": requested, "used": "v0",
                                                                            "fallbackReason": reason}
        try:
            spec = primary.build(text, **kw)
            return spec, {"requested": requested, "used": requested, "fallbackReason": None}
        except Exception as exc:  # noqa: BLE001
            if primary is v0:
                raise
            reason = f"{type(exc).__name__}: {exc}"
            self._alert("scene_mapping_fallback", f"매핑 {requested} 실패 → v0로 대체: {reason}"[:300], None)
            return fallback_spec(v0.build(text, **kw), requested, reason), {"requested": requested, "used": "v0",
                                                                            "fallbackReason": reason}

    def _write_scene(self, text: str) -> None:
        """확정 텍스트만 입력으로 장면 파일을 만든다. 턴 JSON·LLM 출력은 쓰지 않는다.
        save_both면 같은 텍스트를 v0·v1 두 매핑으로 만든 파일도 남긴다(비교 설계: research-design 3.1).
        실패해도 면담 종료는 막지 않고 연구자 알림으로 남긴다."""
        try:
            spec, mapping = self._build_scene(text)
            norm = normalize_confirmed(text)
            problems = check_principles(spec, norm)
            saved = None
            variants: dict = {}
            if self.rt.persist_logs:
                saved = str(write_spec(spec, self.scene_path))
            if self.cfg.mapping.save_both:
                variants = self._write_variants(text, spec, mapping, norm, problems)
            self.scene_spec = spec
            self.log.data["sceneSpec"] = {"path": saved, "specVersion": spec["meta"]["specVersion"],
                                          "builder": spec["meta"]["pipeline"]["builder"],
                                          "sourceTextHash": spec["meta"]["sourceTextHash"], "problems": problems,
                                          "mapping": mapping, "variants": variants}
            if mapping["fallbackReason"]:
                self.log.data["sceneSpec"]["fallback"] = True
            # G50 (4): 넷째 제외 범주(죽음·자해·외상) 낱말이 있으면 세션 기록에 남기고 연구자 알림으로 실험자 화면에 알린다.
            # 진행은 막지 않는다(VR 진행 여부는 연구자가 정함 — 초안, ⚠ 교수님·IRB 확인 필요). 참여자 화면(view)에는 내지 않는다
            flags = safety_flags(spec)
            if flags:
                self.log.data["sceneSpec"]["safetyFlags"] = flags
                self.log.add_event("scene:safety_flag", {"count": len(flags), "flags": flags})
                self._alert("scene_safety_flag", "넷째 제외 범주(죽음·자해·외상) 낱말: " + ", ".join(
                    f"{f['lemma']}[{f['charSpan'][0]}:{f['charSpan'][1]}]" for f in flags)[:300], None)
            if problems:
                self._alert("scene_spec_invalid", "; ".join(problems[:5]), None)
        except Exception as exc:  # noqa: BLE001 — 장면 생성 실패가 면담 종료를 막으면 안 된다
            self.log.data["sceneSpec"] = {"path": None, "error": f"{type(exc).__name__}: {exc}"}
            self._alert("scene_spec_error", f"{type(exc).__name__}: {exc}", None)

    def _write_variants(self, text: str, spec: dict, mapping: dict, norm: str, problems: list) -> dict:
        kw = {"session_id": self.id, "participant_id": self.participant_id, "condition": self.condition}
        out: dict = {}
        # v2는 mode = "v2"일 때만 만들어지므로 그때만 비교 파일({sid}.v2.json)도 남는다(v0·v1 세션 기록 형식은 그대로)
        for name in ("v0", "v1", *(("v2",) if "v2" in self.rt.scene_builders else ())):
            b = self.rt.scene_builders.get(name)
            if b is None:
                out[name] = None
                continue
            try:
                if mapping["used"] == name and spec["meta"].get("mapping", {}).get("fallbackReason") is None \
                        and (self.rt.scene_builder is b):
                    vs = spec
                else:
                    vs = b.build(text, **kw)
                for p in check_principles(vs, norm):
                    problems.append(f"[{name}] {p}")
                out[name] = str(write_spec(vs, self.variant_path(name))) if self.rt.persist_logs else None
            except Exception as exc:  # noqa: BLE001
                out[name] = None
                out[f"{name}Error"] = f"{type(exc).__name__}: {exc}"
        return out

    def _delete_scene(self) -> None:
        self.scene_spec = None
        for path in (self.scene_path, self.variant_path("v0"), self.variant_path("v1")):
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                alert_logger.warning("장면 파일을 지우지 못했습니다(%s): %s", path, exc)

    # ── 화면 ────────────────────────────────────────────────────────────────
    def buttons(self) -> list[dict]:
        if self.awaiting == "start":
            return [{"action": "start", "label": "시작"}]
        if self.awaiting == "reply":
            return [{"action": "skip", "label": "넘어가기"}, {"action": "stop", "label": "그만"}]
        if self.awaiting == "soft_check":
            return [{"action": "continue", "label": "계속"}, {"action": "stop", "label": "그만"}]
        if self.awaiting == "confirm":
            return [{"action": "confirm", "label": "이대로 맞아요"}, {"action": "edit", "label": "고칠게요"}]
        if self.awaiting == "recall":
            return [{"action": f"recall:{o['id']}", "label": o["label"]} for o in self._recall_options()] \
                + [{"action": "stop", "label": "그만"}]
        if self.awaiting == "self_report":
            sc = self._self_report_scale()
            anchors = sc.get("anchors") or {}
            skip = self.p.phrases["self_report_drift"].get("skipLabel", "넘어가기")
            return [{"action": f"self_report:{v}", "label": f"{v} {anchors[str(v)]}" if str(v) in anchors else str(v)}
                    for v in range(int(sc["min"]), int(sc["max"]) + 1)] + [{"action": "self_report:skip", "label": skip}]
        if self.state in ("done", "stopped"):
            return [{"action": "withdraw", "label": "내 답 지우기"}]
        return []

    def view(self) -> dict:
        stage = self.stage if self.state in ("interview", "soft_check") else None
        info = self.p.stage_info(stage)
        out = {
            "sessionId": self.id,
            "condition": {"id": self.condition, "label": self.p.condition(self.condition)["label"]},
            "state": self.state,
            "awaiting": self.awaiting,
            "stage": stage,
            "stageInfo": {"ifs": info.get("ifs"), "labelKo": info.get("labelKo"), "purposeKo": info.get("purposeKo")} if info else None,
            "messages": self.messages,
            "buttons": self.buttons(),
            "confirmDraft": self.confirm_draft if self.awaiting == "confirm" else None,
            "progress": {"step": self.idx, "steps": len(self.steps), "llmTurns": self.llm_total},
        }
        if self.cfg.selection.enabled:   # 새 흐름(v4)에서만 덧붙이는 키. 기본 설정의 화면 응답은 그대로
            out["selection"] = {
                "available": self.state == "done" and self.log.data.get("endedBy") == "completed"
                and self.scene_spec is not None,
                "stage": self.selection_flow.stage if self.selection_flow is not None else None}
        return out

    def researcher_view(self) -> dict:
        # safetyFlags(G50 (4)): 실험자 화면이 읽을 필드(연구자 응답에만. 참여자 화면 view에는 넣지 않음)
        return {"session": self.view(), "log": self.log.data, "runtimeWarnings": self.rt.warnings,
                "safetyFlags": list((self.log.data.get("sceneSpec") or {}).get("safetyFlags") or [])}
