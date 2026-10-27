"""세션 컨트롤러 — 「앞으로 개발 방향」 > Focus > 컨트롤러(세션 진행 보조).

- 지금이 Find / Focus / Flesh out 중 어느 단계인지 기억한다.
- 다음 차례에 고정 문구를 낼지, LLM에게 질문을 만들게 할지 정한다.
- 단계별 횟수 제한(Find 1회, Flesh out 5회 …)을 세고 다음 단계로 넘긴다.

한 턴의 순서(「앞으로 개발 방향」 > 챗봇 구현 원리):
 1) 컨트롤러가 단계를 정함  2) 프롬프트 조립(공통 규칙 + 단계 블록)  3) 로컬 LLM이 JSON으로 답함
 4) 검증기 V1–V9 → 통과한 질문만 나감(최대 2회 재생성, 그다음 고정 대체 문구)
 5) 참여자 답마다 안전 분류(키워드 사전 + 가드 모델) → 위기면 LLM을 끄고 고정 문구 + 연구자 호출
 6) 끝나면 참여자 발화를 그대로 모은 요약을 보여 주고 [이대로 맞아요] → 그 텍스트만 추출로 넘어감
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
from .config import Config
from .extract import Extractor, find_modality, parse_body_relation
from .korean import Analyzer, normalize
from .lexicon import Lexicon
from .llm import GenerationRequest, OfflineTemplateBackend, OllamaBackend
from .paths import shared
from .prompts import PromptContext, PromptSet, TranscriptLine
from .protocol import Protocol, Step
from .safety import Guard, GuardVerdict, OllamaGuardModel, SafetyLexicon
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
        self.persist_logs = persist_logs
        self.sessions: dict[str, "Session"] = {}
        self._lock = threading.Lock()

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
            "warnings": self.warnings,
        }

    def new_session(self, condition: str | None = None, session_id: str | None = None) -> "Session":
        condition = condition or self.cfg.interview.condition
        if session_id is None:
            session_id = datetime.now().strftime("S%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        if not SESSION_ID_RE.match(session_id):
            raise SessionError("세션 ID는 영문·숫자·_·- 1–40자만 됩니다(가명 ID 사용).")
        with self._lock:
            if session_id in self.sessions:
                raise SessionError(f"이미 있는 세션 ID입니다: {session_id}")
            s = Session(self, condition, session_id)
            self.sessions[session_id] = s
        return s


# ── 세션 ────────────────────────────────────────────────────────────────────
class Session:
    def __init__(self, rt: Runtime, condition: str, session_id: str):
        self.rt, self.cfg, self.p = rt, rt.cfg, rt.protocol
        self.p.condition(condition)  # 모르는 조건이면 여기서 오류
        if condition == "chatbot" and not rt.backend_ok:
            raise SessionError(f"조건 2(챗봇)를 시작할 수 없습니다: {rt.backend_msg}")
        self.id, self.condition = session_id, condition
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
                raise SessionError("빈 답은 보낼 수 없습니다. 넘어가려면 [넘어가기]를 누르세요.")
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
                    self._finish(self.confirm_draft or "", edited=False)
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
                    self._finish(edited, edited=True)
                return self.view()
            raise SessionError(f"지금은 '{action}'을(를) 할 수 없습니다 (대기 중: {self.awaiting}).")

    def withdraw(self) -> dict:
        """참여자 철회 — 로그 파일을 지우고 메모리 내용도 비운다(2D 설문의 '응답 폐기' 선택지)."""
        with self.lock:
            if self.state not in ("done", "stopped"):
                raise SessionError("면담이 끝난 뒤에 폐기할 수 있습니다. 위기 대응으로 멈춘 세션은 안전 기록을 위해 연구자가 처리합니다.")
            self.log.delete()
            self.log.persist = False
            self.log.data.update(turns=[], alerts=[], capture={}, confirmedText=None, confirmation=None,
                                 extraction=None, events=[], endedBy="withdrawn")
            self.participant_texts, self.transcript, self.asked, self.confirm_draft = [], [], [], None
            self.messages = [{"speaker": "bot", "text": self.p.phrase("withdrawn"), "kind": "info", "source": "fixed:withdrawn"}]
            self.state, self.awaiting = "withdrawn", "none"
            return self.view()

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
        self._say_fixed("stopped", stage=self.stage, kind="info")
        self.state, self.awaiting = "stopped", "none"
        self.log.end(by)
        self._save()

    def _enter_confirm(self) -> None:
        self.confirm_draft = "\n".join(self.participant_texts)
        self._say_fixed("confirm_intro", stage=None, kind="confirm", draft=self.confirm_draft)
        self.state, self.awaiting = "confirm", "confirm"

    def _finish(self, text: str, edited: bool) -> None:
        self.log.data["confirmedText"] = text
        self.log.data["confirmation"] = {"edited": edited, "draft": self.confirm_draft, "at": now_iso()}
        self.log.data["extraction"] = self.rt.extractor.run(text, self.log.data["capture"].get("bodyRelation"))
        self._say_fixed("closing", stage=None, kind="closing")
        self.state, self.awaiting = "done", "none"
        self.log.end("completed")
        self._save()

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
        if self.state in ("done", "stopped"):
            return [{"action": "withdraw", "label": "응답 폐기"}]
        return []

    def view(self) -> dict:
        stage = self.stage if self.state in ("interview", "soft_check") else None
        info = self.p.stage_info(stage)
        return {
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

    def researcher_view(self) -> dict:
        return {"session": self.view(), "log": self.log.data, "runtimeWarnings": self.rt.warnings}
