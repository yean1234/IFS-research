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

import contextlib
import json
import logging
import re
import secrets
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .anchors import anchor_candidates, bridge_anchor
from .clarify import clarify_targets, question_json
from .config import Config
from .drift import PARAMS as DRIFT_PARAMS
from .drift import DriftAssessor, participant_turns, summarize
from .extract import Extractor, find_modality, image_signal, parse_body_relation
from .form_assets import FormAssetStore
from .none_gen import InterviewBlocked, NoneGenService
from .korean import Analyzer, normalize
from .lexicon import Lexicon
from .candidates import load_table as load_candidate_table
from .candidates import safety_flags
from .llm import GenerationRequest, OfflineTemplateBackend, OllamaBackend
from . import llm_fill as llm_fill_mod
from . import prereport as prereport_mod
from .paths import CHATBOT_DIR, shared
from .preview import PreviewService
from .prompts import PromptContext, PromptSet, TranscriptLine
from .protocol import Protocol, Step
from .safety import Guard, GuardVerdict, OllamaGuardModel, SafetyLexicon
from .scene_builder import SceneSpecBuilder, normalize_confirmed, write_spec
from .scene_builder_v1 import SceneSpecBuilderV1, fallback_spec
from .scene_builder_v2 import SceneSpecBuilderV2, load_lexicon_chain
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
        if cfg.interview.lexicon_overlay:
            # D9: 면담용 오버레이(감정어 '기대' 등). v0 파일은 읽기만 하고, 기록의 lexiconVersion에 두 파일을 모두 적는다
            self.lexicon = load_lexicon_chain(self.analyzer, [shared("lexicon", "layer1_lexicon.v0.json"),
                                                              shared("lexicon", cfg.interview.lexicon_overlay)])
            self.lexicon.version = self.lexicon.chain_info   # type: ignore[attr-defined]
        else:
            self.lexicon = Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), self.analyzer)
        self.safety = SafetyLexicon(shared("lexicon", cfg.guard.safety_lexicon))
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
            predicate_as_noun=cfg.validator.predicate_as_noun,
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
        if cfg.mapping.mode != "v2" and (cfg.mapping.ext_lexicon or cfg.mapping.variant_rules):
            self.warnings.append("[mapping] ext_lexicon·variant_rules는 mode = \"v2\"에서만 씁니다. 지금 설정에서는 쓰지 않습니다.")
        if cfg.mapping.mode == "v2":
            try:
                m = cfg.mapping
                self.scene_builders["v2"] = SceneSpecBuilderV2(
                    self.analyzer,
                    ext_lexicon_path=shared("lexicon", m.ext_lexicon) if m.ext_lexicon else None,
                    ext_params_path=shared("lexicon", m.ext_params) if m.ext_lexicon else None,
                    variant_rules_path=shared("lexicon", m.variant_rules) if m.variant_rules else None,
                    proportions_path=shared("lexicon", m.proportions) if m.proportions else None,   # G72(기본 끔)
                    mist_kinds_path=shared("lexicon", m.mist_kinds) if m.mist_kinds else None)      # G74(기본 끔)
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
            predicate_as_noun=cfg.validator.predicate_as_noun,
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
        # D9 다리 질문(프로토콜 1.5 imageBridge). 고정 문구가 draft면 경고만 남긴다(opening처럼 IRB·팀 검토 전 초안)
        br = self.protocol.bridge
        if br and br.get("plainPhrase") in self.protocol.phrases \
                and self.protocol.phrase_meta(br["plainPhrase"])["status"] == "draft":
            self.warnings.append(f"[D9] 다리 질문 고정 문구 '{br['plainPhrase']}'가 status = draft입니다(IRB·팀 검토 전).")
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
        # G62: 생성 형태 메시 후보([gen3d] enabled일 때만). 꺼져 있으면 None — 후보·기록·화면 출력이 G62 전과 같다
        self.form_assets: FormAssetStore | None = None
        if cfg.gen3d.enabled:
            root = Path(cfg.gen3d.assets_dir)
            self.form_assets = FormAssetStore(root if root.is_absolute() else (CHATBOT_DIR / root).resolve(),
                                              cfg.gen3d.max_candidates, cfg.gen3d.default_form_source)
            if not self.form_assets.root.is_dir():
                self.warnings.append("[gen3d] 자산 폴더가 없어 생성 형태 후보를 내지 않습니다(절차 메시 후보만): "
                                     f"assets_dir = {cfg.gen3d.assets_dir}")
        # G73: [맞는 게 없어요] 뒤 형태 생성([gen3d] on_none, 후보 단계를 켰을 때만). 꺼져 있으면 None — none은 예전처럼 바로 조절
        # G77: 확정 직후 매퍼가 비운 슬롯을 면담 LLM이 인용과 함께 채움([mapping] llm_fill). 꺼져 있으면 None — 출력 그대로
        self.llm_fill_prompt = None
        if cfg.mapping.llm_fill:
            self.llm_fill_prompt = llm_fill_mod.FillPrompt(cfg.mapping.llm_fill_prompt)   # 파일이 없으면 시작을 멈춤
            if cfg.selection.enabled and "llm_fill_note" not in self.selection_protocol.data["phrases"]:
                raise RuntimeError("[mapping] llm_fill을 켰는데 선택 단계 문구에 llm_fill_note가 없습니다 — 참여자가 LLM이 채운 값의 "
                                   "근거를 볼 수 없어 시작을 멈춥니다(selection_protocol.v0.10.json 이상을 쓰세요).")
            if cfg.mapping.mode != "v2":
                self.warnings.append("[mapping] llm_fill은 매퍼 v2 spec을 전제로 만든 것입니다(mode = \"v2\"가 아님).")
            if not hasattr(self.backend, "structured"):
                self.warnings.append(f"[mapping] llm_fill: 백엔드 {getattr(self.backend, 'name', '?')}는 JSON 호출을 못 해 "
                                     "부르지 않습니다(사유 backend_unsupported로 기록).")
        self.none_gen: NoneGenService | None = None
        if cfg.gen3d.on_none and cfg.selection.enabled:
            root = Path(cfg.gen3d.assets_dir)
            self.none_gen = NoneGenService(cfg, root if root.is_absolute() else (CHATBOT_DIR / root).resolve())
            ok, why = self.none_gen.available()
            if not ok:
                self.warnings.append(f"[gen3d] on_none: {why} — [맞는 게 없어요] 뒤 생성을 하지 못하고 기존 경로로 갑니다(사유 기록).")

    def header(self, condition: str) -> dict:
        h = {
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
        # D9 설정을 켰을 때만 키를 더한다(기존 설정의 기록은 그대로)
        if self.cfg.validator.predicate_as_noun:
            h["validator"]["predicateAsNoun"] = True
        if self.cfg.interview.anchor_doe_root:
            h["protocol"]["anchorDoeRoot"] = True
        # 면담 조건 고정([interview] lock_condition)을 켰을 때만 키를 더한다(기존 설정의 기록은 그대로)
        if self.cfg.interview.lock_condition:
            h["conditionLocked"] = True
        return h

    def info(self) -> dict:
        return {
            "config": self.cfg.source,
            "conditions": {c: self.protocol.condition(c)["label"] for c in self.protocol.conditions()},
            "defaultCondition": self.cfg.interview.condition,
            **({"conditionLocked": True} if self.cfg.interview.lock_condition else {}),   # 켰을 때만(꺼지면 출력 그대로)
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
            **({"gen3d": self.form_assets.info()} if self.form_assets is not None else {}),   # G62: 켰을 때만(꺼지면 출력 그대로)
            **({"gen3dOnNone": self.none_gen.info()} if self.none_gen is not None else {}),   # G73: 켰을 때만
            "warnings": self.warnings,
        }

    def new_session(self, condition: str | None = None, session_id: str | None = None,
                    participant_id: str | None = None) -> "Session":
        locked = self.cfg.interview.condition
        if self.cfg.interview.lock_condition and condition and condition != locked:
            # 실험 설정: 면담 조건은 설정값으로 고정. 다른 조건 요청은 덮어쓰지 않고 거절한다(실험자가 바로 알 수 있게)
            raise SessionError(f"면담 조건이 설정으로 '{locked}'에 고정되어 있어 '{condition}' 조건으로는 세션을 만들 수 없습니다"
                               "([interview] lock_condition).")
        condition = condition or self.cfg.interview.condition
        if session_id is None:
            session_id = datetime.now().strftime("S%Y%m%d-%H%M%S-") + secrets.token_hex(2)
        if not SESSION_ID_RE.match(session_id):
            raise SessionError("세션 ID는 영문·숫자·_·- 1–40자만 됩니다(가명 ID 사용).")
        if participant_id is not None and not SESSION_ID_RE.match(participant_id):
            raise SessionError("참여자 ID는 영문·숫자·_·- 1–40자만 됩니다(가명 ID 사용).")
        self.check_interview_allowed(creating=True)
        with self._lock:
            if session_id in self.sessions:
                raise SessionError(f"이미 있는 세션 ID입니다: {session_id}")
            s = Session(self, condition, session_id, participant_id=participant_id)
            self.sessions[session_id] = s
        return s

    # ── (CP13-2) 면담과 [맞는 게 없어요] 생성의 상호 배제. on_none을 켠 설정에서만(none_gen 없으면 아무것도 안 함) ──
    def check_interview_allowed(self, creating: bool = False) -> None:
        if self.none_gen is not None:
            why = self.none_gen.interview_refusal(creating=creating)
            if why:
                raise SessionError(why)

    def interview_slot(self, text: str | None = None, creating: bool = False):
        """면담 LLM·가드 모델을 쓰는 요청 구간. 생성이 모델을 내려 둔 동안에는 막는다(SessionError → 409).
        키워드 위기 문장은 막지 않는다 — 가드 모델 없이 고정 문구만 낸다(CP12)."""
        if self.none_gen is None:
            return contextlib.nullcontext()
        crisis = bool(text) and self.guard.use_keywords and any(
            self.guard.lexicon.tiers[h.tier]["action"] == "crisis" for h in self.guard.lexicon.crisis_hits(text))
        slot = self.none_gen.interview_slot(crisis_ok=crisis, creating=creating)

        class _Wrap:
            def __enter__(self_):
                try:
                    slot.__enter__()
                except InterviewBlocked as exc:
                    raise SessionError(str(exc)) from exc
                return self_

            def __exit__(self_, *exc):
                return slot.__exit__(*exc)
        return _Wrap()


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
        self.scene_hashes: dict | None = None      # 확정 시점에 고정한 장면 파일별 sha256(보기 전 보고가 쓴다)
        self.llm_fill: dict | None = None          # (G77) 확정 직후 LLM 빈칸 채우기 기록([mapping] llm_fill일 때만)
        self.llm_fill_cache: dict = {}             # (확정 텍스트 해시, 모델 digest, 프롬프트 판·해시) → 기록(다시 부르지 않음)
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
        # D9 형상 신호(프로토콜 1.5). 흐름(다리 질문·find 틀 제한)에만 쓰고 장면 값에는 쓰지 않는다(원칙 2)
        self.image_on = self.p.uses_image_signal()
        self.answers: dict[str, str] = {}          # 고정 문구 id → 참여자 답(없어요 제외). 다리 X 고르기에 쓴다
        self._img_cache: dict[str, dict] = {}
        # 나간 질문마다 질문 틀(LLM·다리 = 고른 틀, 고정 문구 = 1.6 templateRules.fixedPhraseTemplates에 있으면 그 틀, 아니면 None).
        # 1.6 templateRules(like_what 세션 1회·직전 틀 반복 금지)가 쓴다. 1.5 이하에서는 세기만 하고 흐름·기록에 쓰지 않는다
        self.tpl_history: list[str | None] = []
        self.lock = threading.RLock()
        self.log = SessionLog(session_id, condition, rt.header(condition), self.cfg.log_dir, persist=rt.persist_logs)
        for key, val in self.p.capture_defaults.items():   # 1.6(G70): bodyRelation = {"status": "not_asked"}
            self.log.data["capture"][key] = json.loads(json.dumps(val))
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
        if kind == "question" and stage:
            out = turn_fields.get("output") or {}
            tpl = out.get("template") if out.get("move") == "ask" and out.get("template") in self.p.templates else None
            if tpl is None and source.startswith("fixed:"):
                tpl = (self.p.template_rules.get("fixedPhraseTemplates") or {}).get(source[len("fixed:"):])
            self.tpl_history.append(tpl)
        return turn

    def _say_fixed(self, phrase_id: str, *, stage: str | None, kind: str = "question",
                   speaker: str = "system", ref_x: str | None = None, **turn_fields) -> dict:
        """ref_x: X를 인용하는 형(1.6 withX)이 있는 문구에서 None이면 호칭 규칙(_referent)으로 X를 고르고, ""면 '그 느낌' 형."""
        fmt = {"researcher_contact": self.cfg.session.researcher_contact} if phrase_id == "crisis" else {}
        if self.p.has_ref_form(phrase_id):
            ref = self._referent() if ref_x is None else {"x": ref_x, "rule": "given"}
            text = self.p.phrase_ref(phrase_id, ref["x"])
            turn_fields["referent"] = ref
        else:
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
        with self.lock, self.rt.interview_slot(creating=True):
            if self.awaiting != "start":
                raise SessionError("이미 시작한 세션입니다.")
            self.log.add_turn(speaker="participant", source="control:start", stage=None, text="[시작]")
            self.state = "interview"
            self._advance()
            self._save()
            return self.view()

    def reply(self, text: str, source: str = "typed") -> dict:
        with self.lock, self.rt.interview_slot(text):
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
        # (CP13-2) 면담 모델·가드 모델을 부를 수 있는 동작은 생성 중에 받지 않는다(그만·철회·시작은 각자 처리)
        gated = action in ("continue", "confirm", "edit") or action.startswith(("recall:", "self_report:"))
        with self.lock, (self.rt.interview_slot(text) if gated else contextlib.nullcontext()):
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
                self.selection_flow.cancel_generation("withdrawn")     # G73: 돌고 있는 생성이 있으면 끈다
            self.selection_flow = None
            prereport_mod.delete_record(self.cfg.log_dir, self.id)
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

    # ── 보기 전 보고 과제 (면담 밖, 고정 문구, LLM 없음 — ifs_chatbot/prereport.py) ──────────
    @property
    def prereport_path(self):
        return prereport_mod.record_path(self.cfg.log_dir, self.id)

    def prereport_status(self) -> dict:
        """과제를 열 수 있는지(확정 텍스트와 장면 파일이 있어야 함)와 이미 냈는지. 고른 값은 돌려주지 않는다."""
        with self.lock:
            reason = None
            if self.state == "withdrawn":
                reason = "폐기된 세션입니다."
            elif not self.log.data.get("confirmedText"):
                reason = "확정 텍스트가 아직 없습니다([이대로 맞아요] 뒤에 열립니다)."
            elif not self.scene_hashes:
                reason = "확정 때 만든 장면 파일이 없습니다(장면 파일의 sha256을 남겨야 하므로 과제를 열 수 없습니다)."
            submitted = self.prereport_path.is_file()
            return {"sessionId": self.id, "available": reason is None and not submitted,
                    "submitted": submitted, "reason": reason}

    def submit_prereport(self, attributes: dict) -> dict:
        """참여자 답(attributes)에 ID·장면 sha256·문구 판을 붙여 스키마 검사 뒤 한 번만 쓴다.
        → {"ok": True, ...} / 스키마 위반이면 ValueError(위반 목록), 순서가 틀리면 SessionError."""
        with self.lock:
            st = self.prereport_status()
            if st["submitted"]:
                raise SessionError("보기 전 보고는 이미 냈습니다(한 번만 받습니다).")
            if st["reason"]:
                raise SessionError(st["reason"])
            # 장면 sha256·대체 매핑 파일 목록은 확정 때 고정한 값(지금 파일을 다시 읽지 않는다)
            rec = prereport_mod.build_record(session_id=self.id, participant=self.participant_id,
                                             frozen=self.scene_hashes, attributes=attributes)
            problems = prereport_mod.validate(rec)
            if problems:
                raise ValueError(problems)
            prereport_mod.write_record(rec, self.prereport_path)
            # 세션 로그에는 낸 사실과 파일 짝만 남긴다(고른 값·①②③은 별도 파일에만)
            self.log.add_event("prereport", {"file": f"{self.id}/{prereport_mod.RECORD_NAME}",
                                             "specSha256": rec["specSha256"], "taskTextVersion": rec["taskTextVersion"]})
            self._save()
            return {"ok": True, "sessionId": self.id, "specSha256": rec["specSha256"], "createdAtUtc": rec["createdAtUtc"]}

    # ── 진행 ────────────────────────────────────────────────────────────────
    def _on_reply(self, step: Step, text: str, no_more: bool) -> None:
        st = self.step_state[self.idx]
        if self.image_on:
            self._record_image_signal(step, st, text, no_more)
        if step.type == "fixed":
            if step.capture == "bodyRelation":
                self.log.data["capture"]["bodyRelation"] = parse_body_relation(text, self.rt.lexicon, no_more)
            if step.phrase == "opening":
                self.log.data["capture"]["findModality"] = find_modality(text, self.rt.lexicon)
            if not no_more and step.phrase:
                self.answers[step.phrase] = text
            st["answered"] = True
            self.idx += 1
        elif step.type == "bridge":
            # 압박하지 않기: 다리 답이 '없어요'류면 다음 LLM 질문(flesh_out)을 건너뛴다. 다리 답에 내용이 있으면
            # focus_hold 답이 '없어요'였어도 flesh_out LLM을 그대로 묻는다(직전 noMore를 물려받지 않음)
            self.last_no_more = no_more
            st["answered"] = True
            self.idx += 1
        elif step.type == "llm":
            if no_more:
                st["done"] = True
        elif step.type == "probes":
            st["current"] = None

    # ── 형상 신호 · 다리 질문 (D9, 프로토콜 1.5) ─────────────────────────────
    def _img(self, text: str) -> dict:
        if text not in self._img_cache:
            self._img_cache[text] = image_signal(text, self.rt.lexicon, self.rt.analyzer, self.p.image_signal_spec)
        return self._img_cache[text]

    def _image_signal_all(self) -> dict:
        """opening부터 직전 답까지 참여자 발화 전체('없어요' 제외)의 형상 신호. excluded = 부정·중복 범주로 뺀 후보."""
        ev = [{**e, "text": t} for t in self.participant_texts for e in self._img(t)["evidence"]]
        ex = [{**e, "text": t} for t in self.participant_texts for e in self._img(t)["excluded"]]
        return {"present": bool(ev), "evidence": ev, "excluded": ex}

    # ── 1.6: 호칭(referent) · 차원 판정(coverage) · find 조건(G70-e) · 틀 규칙(templateRules) ──────────
    def _referent(self) -> dict:
        """고정 문구의 호칭 X(1.6 referent). 형상 신호의 일반명사(사전 form·object 항목이거나 비유 표지 앞 명사)를
        가장 최근 답부터 찾는다(한 답 안에서는 앞에 나온 것). 'N 모양'의 N, 인용 금지어, 깊이 표지어, 기억 서사 답의 말은 뺀다.
        없으면 x = ""('그 느낌'). X는 늘 참여자 원문의 부분 문자열이다."""
        from .anchors import ANCHOR_STOP
        rule = self.p.referent or {}
        if not rule:
            return {"x": "", "rule": "none"}
        name = rule.get("rule", "image_noun_or_feeling")
        cats = set(rule.get("imageNounCategories", ["form", "object"]))
        tags = set(rule.get("nounTags", ["NNG"]))
        skip_next = set(rule.get("skipIfFollowedBy", []))
        safety = self.rt.safety
        skipped: list[dict] = []
        for age, text in enumerate(reversed(self.participant_texts)):
            if safety.depth(text)["strong"]:
                skipped.append({"age": age, "why": "depth_strong"})
                continue
            sig = self._img(text)
            spans = [tuple(e["charSpan"]) for e in sig["evidence"]
                     if (e["kind"] == "lexicon" and e.get("category") in cats)
                     or (e["kind"] == "simile" and rule.get("simileNoun", True))]
            if not spans:
                continue
            toks = self.rt.analyzer.tokens(text)
            for k, tok in enumerate(toks):
                if tok.base_tag not in tags or text[tok.start:tok.end] != tok.form:
                    continue
                if not any(a <= tok.start and tok.end <= b for a, b in spans):
                    continue
                nxt = toks[k + 1] if k + 1 < len(toks) else None
                if nxt is not None and nxt.form in skip_next:
                    skipped.append({"age": age, "noun": tok.form, "why": "followed_by:" + nxt.form})
                    continue
                if tok.form in ANCHOR_STOP or safety.has_depth_marker(tok.form):
                    skipped.append({"age": age, "noun": tok.form, "why": "stop_or_depth"})
                    continue
                out = {"x": tok.form, "rule": name, "fromText": len(self.participant_texts) - 1 - age,
                       "charSpan": [tok.start, tok.end]}
                if skipped:
                    out["skipped"] = skipped
                return out
        out = {"x": "", "rule": name, "why": "no_image_noun"}
        if skipped:
            out["skipped"] = skipped
        return out

    @staticmethod
    def _slot(spec, path: str):
        cur = spec
        for part in path.split("."):
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        return cur

    def _coverage(self) -> dict:
        """참여자가 이미 말한 차원(1.6 dimensionProbes.coverage). 지금까지의 참여자 발화로 매퍼가 실제로 채운 슬롯 +
        모양은 형상 신호(사전 form·shape·object·posture, 비유 표지, 'N 모양'). 매퍼가 예외를 내면 1.5 규칙(사전 범주).
        흐름(프로브·프롬프트 맥락)에만 쓰고 장면 값에는 쓰지 않는다(원칙 2)."""
        cov = self.p.probe_coverage or {}
        text = "\n".join(self.participant_texts)
        lex_cats = self.rt.lexicon.categories_in(text) if text else set()
        builder = self.rt.scene_builder
        bid = getattr(builder, "builder_id", None)
        rec: dict = {"rule": cov.get("rule", "lexicon_categories"), "turn": len(self.log.turns),
                     "builder": bid if isinstance(bid, str) else type(builder).__name__,
                     "mappingMode": self.cfg.mapping.mode}
        spec = None
        if text:
            try:
                spec = builder.build(text)
            except Exception as exc:  # noqa: BLE001 — 매퍼가 죽어도 면담은 1.5 규칙으로 이어 간다
                rec["mapperError"] = type(exc).__name__ + ": " + str(exc)[:160]
        shape_cats = set(cov.get("imageShapeCategories", ["form", "shape", "object", "posture"]))
        before = cov.get("shapeNounBefore")
        shape_ev = []
        for t in self.participant_texts:
            for e in self._img(t)["evidence"]:
                if (e["kind"] == "lexicon" and e.get("category") in shape_cats) or \
                        (e["kind"] == "simile" and cov.get("imageShapeSimile", True)):
                    shape_ev.append({"kind": e["kind"], "category": e.get("category"), "trigger": e["trigger"]})
            if before:
                toks = self.rt.analyzer.tokens(t)
                for k in range(len(toks) - 1):
                    if toks[k].base_tag in ("NNG", "NNP") and toks[k + 1].form == before and toks[k + 1].base_tag == "NNG":
                        shape_ev.append({"kind": "noun_before_shape", "trigger": t[toks[k].start:toks[k + 1].end]})
        filled: dict = {}
        dims: dict = {}

        def judge(dim_id: str, entry: dict) -> None:
            hit = []
            for path in entry.get("slots", []):
                v = self._slot(spec, path)
                if v is not None:
                    prov = ((spec or {}).get("_provenance") or {}).get(path) or []
                    prov = prov if isinstance(prov, list) else [prov]
                    trig = [pv.get("trigger") for pv in prov if isinstance(pv, dict) and pv.get("trigger")]
                    filled[path] = {"value": v, "triggers": trig}
                    hit.append(path)
            img = bool(shape_ev) if entry.get("imageShape") else False
            if spec is None:      # 매퍼 없음(예외·빈 발화) → 1.5 규칙: 사전 범주
                by_lex = sorted(set(entry.get("coveredByCategories", [])) & lex_cats)
                dims[dim_id] = {"covered": bool(by_lex) or img, "byLexicon": by_lex, "byImageSignal": img}
            else:
                dims[dim_id] = {"covered": bool(hit) or img, "bySlots": hit, "byImageSignal": img}

        for pr in self.p.probes:
            if pr.get("parts"):
                for part in pr["parts"]:
                    lex = pr.get("coveredByCategories", []) if part["id"] == "size" else []
                    judge(part["id"], {**part, "coveredByCategories": lex})
            else:
                judge(pr["id"], pr)
        rec["dims"] = dims
        rec["filledSlots"] = filled
        rec["imageShape"] = shape_ev
        rec["fallback"] = spec is None
        return rec

    def _covered_dims_for_prompt(self, cov: dict) -> list[dict]:
        """프롬프트 맥락용: 이미 말한 차원 id와 참여자 원문 낱말(원문에 그대로 있는 것만)."""
        out = []
        for dim, d in cov.get("dims", {}).items():
            if not d.get("covered"):
                continue
            words: list[str] = []
            for path in d.get("bySlots", []):
                words += cov["filledSlots"].get(path, {}).get("triggers", [])
            if d.get("byImageSignal"):
                words += [e["trigger"] for e in cov.get("imageShape", [])]
            words = [w for w in dict.fromkeys(words) if w and any(w in t for t in self.participant_texts)]
            out.append({"dim": dim, "words": words[:4]})
        return out

    def _find_signal(self) -> tuple[bool, dict]:
        """G70-e: 첫 답(opening)에 감정·감각 사전어(부정 아님)나 형상 신호가 있는가."""
        rule = self.p.find_signal_rule() or {}
        src = rule.get("from", "opening")
        text = self.answers.get(src) or ""
        cats = set(rule.get("lexiconCategories", ["emotion", "sensation"]))
        lex = [{"lemma": h.entry.lemma, "category": h.entry.category, "trigger": h.trigger}
               for h in (self.rt.lexicon.hits(text) if text else []) if h.entry.category in cats and not h.negated]
        img = self._img(text) if text and rule.get("orImageSignal", True) else {"present": False, "evidence": []}
        ok = bool(lex) or bool(img["present"])
        return ok, {"from": src, "hasAnswer": bool(text), "lexicon": lex,
                    "imageSignal": [{"kind": e["kind"], "trigger": e["trigger"]} for e in img.get("evidence", [])]}

    def _template_rules(self, allowed: list[str], cands: list) -> tuple[list[str], dict]:
        """1.6 templateRules: 허용 목록에서 뺄 틀과 이유. 검증(V2)이 같은 목록을 쓰므로 둘 다 막힌다."""
        rules = self.p.template_rules
        blocked: dict = {}
        if not rules:
            return allowed, blocked
        used = [t for t in self.tpl_history if t]
        for tpl, n in (rules.get("maxPerSession") or {}).items():
            if tpl in allowed and used.count(tpl) >= n:
                blocked[tpl] = "max_per_session:" + str(n)
        last = self.tpl_history[-1] if self.tpl_history else None
        if rules.get("noImmediateRepeat") and last in allowed and last not in blocked:
            blocked[last] = "immediate_repeat"
        for tpl in rules.get("notOnImageX") or []:
            if tpl in allowed and tpl not in blocked and cands and all(self._img(a.text)["present"] for a in cands):
                blocked[tpl] = "all_anchor_candidates_are_image"
        return [t for t in allowed if t not in blocked], blocked

    def _probe_v16(self, step: Step, st: dict) -> bool:
        """1.6 차원 프로브: '이미 말함' = 매퍼가 채운 슬롯 + 형상 신호(_coverage). 크기·모양은 둘 다 아직이면 합친 문구,
        하나만 아직이면 그 하나(probe_size·probe_shape). 물었으면 True. 판정 근거는 프로브 턴의 coverage와 capture.probes."""
        done = st.setdefault("doneEntries", [])
        asked = st.setdefault("asked", [])
        log = st.setdefault("coverage", [])
        cov = self._coverage()
        dims = cov["dims"]
        for pr in self.p.probes:
            if pr["id"] in done:
                continue
            done.append(pr["id"])
            if pr.get("parts"):
                open_parts = [pt for pt in pr["parts"] if not dims[pt["id"]]["covered"]]
                if not open_parts:
                    continue
                pick = pr if len(open_parts) == len(pr["parts"]) else open_parts[0]
            else:
                if dims[pr["id"]]["covered"]:
                    continue
                pick = pr
            decision = {"entry": pr["id"], "asked": pick["id"], "phrase": pick["phrase"]}
            log.append({**cov, "decision": decision})
            asked.append(pick["id"])
            st["current"] = pick["id"]
            self._say_fixed(pick["phrase"], stage=step.stage, probe=pick["id"], coverage={**cov, "decision": decision})
            self._write_probe_capture(st)
            return True
        log.append({**cov, "decision": {"asked": None}})
        st["skipped"] = [pr["id"] for pr in self.p.probes if pr["id"] not in asked
                         and not any(pt["id"] in asked for pt in pr.get("parts", []))]
        self._write_probe_capture(st)
        return False

    def _write_probe_capture(self, st: dict) -> None:
        self.log.data["capture"]["probes"] = {
            "asked": list(st.get("asked", [])), "skippedAsCovered": list(st.get("skipped", [])),
            "rule": (self.p.probe_coverage or {}).get("rule"), "coverage": list(st.get("coverage", []))}

    def _image_capture(self) -> dict:
        cap = self.log.data["capture"]
        if "imageSignal" not in cap:
            cap["imageSignal"] = {
                "use": "flow_only", "protocolVersion": self.p.version,
                "note": "규칙 판정(사전 범주·비유 표지). 다리 질문·find 틀 제한에만 쓰고 장면 값에는 쓰지 않는다(원칙 2).",
                "timeline": [], "atFind": None, "atBridge": None, "confirmed": None,
            }
            cap["firstElicitedBy"] = None
            cap["imageless"] = None
        return cap["imageSignal"]

    def _reply_kind(self, step: Step, st: dict) -> str:
        if step.type == "fixed":
            return step.phrase or "fixed"
        if step.type == "probes":
            return f"probe:{st.get('current')}"
        if step.type == "llm":
            return f"llm:{step.stage}"
        return step.type

    @staticmethod
    def _elicited_by(step: Step) -> str:
        """firstElicitedBy.kind(반박 처리 표 6): opening | focus_hold | bridge | llm | probe.
        고정 문구는 단계로 나눈다 — find 단계(opening·location) = opening, focus 단계(focus_hold) = focus_hold,
        flesh_out 단계(조건 1 fleshout_open) = probe. 자세한 턴 종류는 detail에 남긴다."""
        if step.type == "bridge":
            return "bridge"
        if step.type == "llm":
            return "llm"
        if step.type == "probes":
            return "probe"
        return {"find": "opening", "focus": "focus_hold"}.get(step.stage or "", "probe")

    def _record_image_signal(self, step: Step, st: dict, text: str, no_more: bool) -> None:
        sig = self._image_capture()
        turn_i = len(self.log.turns) - 1
        asked_by = next((t.get("source") for t in reversed(self.log.turns[:-1])
                         if t.get("speaker") in ("system", "interviewer") and t.get("text")), None)
        kind = self._reply_kind(step, st)
        by = self._elicited_by(step)
        own = {"present": False, "evidence": [], "excluded": []} if no_more else self._img(text)
        cum = self._image_signal_all()
        neg_ex = any(e.get("why") == "negated" for e in own["excluded"])
        neg_ev = any(e.get("negated") for e in own["evidence"])
        # 판정 시점 = 이 답(turn i, 단계). evidence의 trigger가 근거 표현, excluded의 why = negated가 부정으로 뺀 것
        sig["timeline"].append({"i": turn_i, "judgedAt": "reply", "kind": kind, "elicitedBy": by, "askedBy": asked_by,
                                "stage": step.stage, "noMore": no_more, "present": own["present"],
                                "cumulative": cum["present"], "evidence": own["evidence"], "excluded": own["excluded"],
                                # negated = 이 답에 부정 표지가 있었는지(양쪽). 판정과 무관한 기록이다(CP11):
                                # negatedExcluded = 부정으로 신호에서 뺀 사전 적중, negatedInEvidence = 부정이 기록만 된 비유 적중
                                "negatedExcluded": neg_ex, "negatedInEvidence": neg_ev, "negated": neg_ex or neg_ev})
        cap = self.log.data["capture"]
        if own["present"] and cap.get("firstElicitedBy") is None:
            cap["firstElicitedBy"] = {"kind": by, "detail": kind, "i": turn_i, "askedBy": asked_by,
                                      "evidence": list(dict.fromkeys(e.get("lemma") or e.get("noun") for e in own["evidence"]))}

    def _bridge(self, step: Step, st: dict) -> bool:
        """다리 질문을 낼지 정하고 내면 True. 형상 신호가 이미 있으면 건너뛴다(1회만, LLM 없음)."""
        br = self.p.bridge or {}
        sig_all = self._image_signal_all()
        cap = self.log.data["capture"]
        self._image_capture()["atBridge"] = {"judgedAt": "bridge", "present": sig_all["present"],
                                             "evidence": sig_all["evidence"], "excluded": sig_all["excluded"],
                                             "turn": len(self.log.turns)}
        if sig_all["present"]:
            cap["bridge"] = {"asked": False, "skipped": "image_signal_present", "stage": step.stage}
            st["skipped"] = True
            return False
        doe = self.cfg.interview.anchor_doe_root
        xs = br.get("xSelection") or {}
        # 1.6(G70-c): kinds = noun(일반명사만), surfaceFallbackPos = NNG. 1.5 파일의 값은 코드 기본값과 같다
        xkw = {}
        if xs.get("order"):
            xkw["order"] = tuple((o["from"], o["category"]) for o in xs["order"])
        if xs.get("kinds"):
            xkw["kinds"] = tuple(xs["kinds"])
        if xs.get("surfaceFallbackPos"):
            xkw["surface_pos"] = set(xs["surfaceFallbackPos"])
        x, xinfo = bridge_anchor(self.answers, self.rt.lexicon, self.rt.analyzer, self.rt.safety, doe_root=doe, **xkw)
        template = br.get("template", "like_what")
        plain = br.get("plainPhrase", "bridge_like_what_plain")
        x_form = br.get("xForm")                       # 1.6: X 문장도 고정 문구의 withX 형(「그 '{X}'이/가 눈에 보이는 무언가라면…」)
        v5_allow = frozenset((br.get("validation") or {}).get("v5Allow") or ())   # 1.6: 틀 말 '눈·보이·무언가·느낌'
        rec = {"asked": True, "stage": step.stage, "x": x or None, "xSelection": xinfo, "template": template,
               "validation": "V1–V7·V9 (V8 가드 모델은 걸지 않음: 틀 + 참여자 원문 인용뿐인 결정론 문장)"}
        vkw = {"extra_allow": v5_allow} if v5_allow else {}   # 1.5 이하는 예전 호출 그대로
        if v5_allow:
            rec["v5Allow"] = sorted(v5_allow)
        last = self.participant_texts[-1] if self.participant_texts else ""
        vctx = TurnContext(step.stage, [template], list(self.participant_texts), last, None)
        if x:
            utt = self.p.phrase_ref(plain, x) if x_form and self.p.has_ref_form(plain) else self.p.realize(template, x)
            out = {"stage": step.stage, "risk_signal": "none", "move": "ask", "template": template,
                   "anchor_quote": x, "utterance": utt}
            r = self.rt.clarify_validator.check(json.dumps(out, ensure_ascii=False), vctx, **vkw)
            rec["checks"] = {"passed": r.passed, "reasons": r.reasons}
            if r.passed:
                rec["phrase"] = "template:" + template
                cap["bridge"] = rec
                self._say(utt, speaker="system", source=f"bridge:{template}", stage=step.stage, output=out,
                          checks={"passed": True, "reasons": [], "regenerations": 0, "fallback": False, "v8": "not_applied"})
                self.asked.append({"template": template, "utterance": utt, "anchor": x})
                st["asked"] = True
                return True
        # X 없는 고정 문장. 대체 사유: no_x(X를 고르지 못함, 사유는 xSelection.noXReason) | x_sentence_failed_validation
        rec["phrase"] = plain
        rec["fallback"] = bool(x)            # X가 있었는데 검증에 걸려 X 없는 문장으로 바꿈
        rec["fallbackReason"] = "x_sentence_failed_validation" if x else "no_x"
        # 고정 문구 전용 검증 경로(반박 처리 표 7): V1·V2·V4–V7·V9. 인용이 없게 만든 문장이라 인용 요구(V1 anchor_required·V3)만
        # 빼고, V8 가드 모델은 X 문장과 같은 이유로 걸지 않는다(docs/chatbot-design.md 5-3)
        plain_text = self.p.phrase(plain)
        pout = {"stage": step.stage, "risk_signal": "none", "move": "ask", "template": template,
                "anchor_quote": "", "utterance": plain_text}
        pr = self.rt.clarify_validator.check(json.dumps(pout, ensure_ascii=False), vctx, require_quote=False, **vkw)
        rec["plainChecks"] = {"path": "fixed_phrase", "applied": "V1·V2·V4·V5·V6·V7·V9",
                              "notApplied": ["V1:anchor_required", "V3", "V8"], "passed": pr.passed, "reasons": pr.reasons}
        if not pr.passed:
            # 고정 문장마저 걸리면 내지 않는다(검증기를 거치지 않은 문장을 내보내지 않음). 다리 1회는 쓴 것으로 친다
            rec["asked"] = False
            rec["skipped"] = "plain_phrase_failed_validation"
            cap["bridge"] = rec
            st["skipped"] = True
            self._alert("bridge_plain_blocked", f"다리 고정 문장이 검증기에 걸려 내지 않음: {', '.join(pr.reasons)}",
                        len(self.log.turns) - 1)
            return False
        cap["bridge"] = rec
        self._say_fixed(plain, stage=step.stage, output=pout, ref_x="",
                        checks={"passed": True, "reasons": [], "regenerations": 0, "fallback": bool(x),
                                "fallbackReason": rec["fallbackReason"],
                                "xSentenceReasons": rec.get("checks", {}).get("reasons", []),
                                "path": "fixed_phrase", "v8": "not_applied"})
        self.asked.append({"template": plain, "utterance": plain_text, "anchor": ""})
        st["asked"] = True
        return True

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
                if not skip and step.stage == "find" and self.p.find_signal_rule() and not st.get("signalChecked"):
                    # G70-e(1.6): 첫 답에 감정·감각 사전어나 형상 신호가 없으면(상황·생각·바람) find LLM을 건너뛴다
                    ok, basis = self._find_signal()
                    st["signalChecked"] = True
                    self.log.data["capture"]["findLlm"] = {"asked": ok, "rule": "askOnlyIfSignal", **basis,
                                                           **({} if ok else {"skipped": "no_emotion_sensation_or_image"})}
                    skip = not ok
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
            if step.type == "bridge":
                if st.get("asked") or st.get("skipped") or not self._bridge(step, st):
                    self.idx += 1
                    continue
                self.awaiting = "reply"
                return
            if step.type == "probes":
                if self.p.probe_coverage:
                    if self._probe_v16(step, st):
                        self.awaiting = "reply"
                        return
                    self.idx += 1
                    continue
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
            said = self._say_fixed("depth_present", stage=stage, speaker="interviewer",
                                   checks={"passed": True, "reasons": ["L5:present_focus"], "regenerations": 0, "fallback": False})
            self.asked.append({"template": "depth_present", "utterance": said["text"], "anchor": ""})
            st["turns"] = turn_no
            self.llm_total += 1
            return "asked"

        allowed = self.p.allowed_templates(stage)
        if self.image_on and self.p.restricts_without_image(stage):
            # D9: 형상 신호가 아직 없으면 find LLM은 anything_else만(like_what은 focus_hold 뒤 다리 질문으로 미룬다)
            sig_all = self._image_signal_all()
            allowed = self.p.allowed_templates(stage, image_present=sig_all["present"])
            self._image_capture()["atFind"] = {"judgedAt": "find_llm", "present": sig_all["present"],
                                               "evidence": sig_all["evidence"], "excluded": sig_all["excluded"],
                                               "allowedTemplates": allowed, "turn": len(self.log.turns)}
        if self.image_on and (self.log.data["capture"].get("bridge") or {}).get("asked"):
            # D9(CP11): 다리 질문(like_what)을 이미 낸 세션에서는 그 뒤 LLM이 같은 틀을 다시 고르지 못한다(다리 1회).
            # 프롬프트의 허용 목록과 검증(V2 template_not_allowed)이 같은 목록을 쓰므로 둘 다 막힌다
            bt = (self.p.bridge or {}).get("template", "like_what")
            if bt in allowed:
                allowed = [t for t in allowed if t != bt]
                self.log.data["capture"]["bridge"].setdefault("blockedTemplateAfter", bt)
        cands = anchor_candidates(self.participant_texts, self.rt.lexicon, self.rt.analyzer, self.rt.safety,
                                  used={a.get("anchor", "") for a in self.asked},
                                  doe_root=self.cfg.interview.anchor_doe_root)
        rules = self.p.template_rules
        covered_dims: list[dict] = []
        used_templates: list[dict] = []
        if rules:
            # 1.6 결함 1·2: like_what 세션 1회(다리 포함)·직전 틀 반복 금지·형상 X에 like_what 금지 → 허용 목록에서 빼고 V2도 같은 목록
            before = list(allowed)
            allowed, blocked = self._template_rules(allowed, cands)
            hist = [t for t in self.tpl_history if t]
            used_templates = [{"template": t, "count": hist.count(t), "blocked": blocked.get(t)}
                              for t in dict.fromkeys(hist + list(blocked))]
            # 결함 3·5: 이미 말한 차원(프로브와 같은 출처)을 프롬프트 맥락으로
            cov = self._coverage() if self.p.probe_coverage else None
            covered_dims = self._covered_dims_for_prompt(cov) if cov else []
            self.log.data["capture"].setdefault("templateRules", []).append({
                "turn": len(self.log.turns), "stage": stage, "allowedBefore": before, "allowed": allowed,
                "blocked": blocked, "history": list(self.tpl_history), "coveredDims": covered_dims,
                **({"mapperError": cov["mapperError"]} if cov and cov.get("mapperError") else {})})
            if not allowed:      # 쓸 틀이 없으면 LLM을 부르지 않고 다음 단계로
                return "advance"
        pctx = PromptContext(stage=stage, turn_no=turn_no, max_turns=step.max_turns, allowed_templates=allowed,
                             transcript=list(self.transcript), participant_texts=list(self.participant_texts),
                             asked=[dict(a) for a in self.asked], anchor_candidates=cands,
                             covered_dims=covered_dims, used_templates=used_templates)
        last_p = next((t for t in reversed(self.log.turns) if t.get("speaker") == "participant" and t.get("guardDetail")), None)
        vctx = TurnContext(stage, allowed, list(self.participant_texts), self.participant_texts[-1],
                           ((last_p or {}).get("guardDetail") or {}).get("model"),
                           image_x_templates=tuple(rules.get("notOnImageX") or ()))
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
        fb_tpl = (rules.get("fixedPhraseTemplates") or {}).get("fallback") if rules else None
        if rules.get("noImmediateRepeat") and fb_tpl and self.tpl_history and self.tpl_history[-1] == fb_tpl \
                and not any(r.startswith("V9") for a in attempts for r in a["reasons"]) \
                and not self.rt.safety.depth(self.participant_texts[-1])["strong"]:
            # 1.6 결함 1: 대체 문구(= anything_else 꼴)가 바로 앞 질문과 같은 틀이 되면 내지 않고 이 LLM 단계를 끝낸다
            self.log.add_turn(speaker="interviewer", source="llm", stage=stage, text="", output=None, attempts=attempts,
                              checks={"passed": False, "reasons": last_reasons,
                                      "regenerations": max(0, len(attempts) - 1), "fallback": False,
                                      "fallbackSuppressed": "immediate_repeat:" + fb_tpl},
                              note="대체 문구가 직전 질문과 같은 틀이라 내지 않고 다음 단계로 — 참여자에게 나가지 않음")
            self.log.data["capture"]["templateRules"][-1]["fallbackSuppressed"] = "immediate_repeat:" + fb_tpl
            return "advance"
        # '방금 말씀하신 것에 대해 더 있나요?'는 직전 발화가 기억 서사이면 그 장면으로 더 들어가게 한다.
        # 그럴 때는 L5 고정 문구로 지금 떠오른 것에 머물게 한다.
        depth_related = any(r.startswith("V9") for a in attempts for r in a["reasons"])             or bool(self.rt.safety.depth(self.participant_texts[-1])["strong"])
        phrase = "depth_present" if depth_related and cfg.validator.l5_depth != "off" else "fallback"
        said = self._say_fixed(phrase, stage=stage, speaker="interviewer", output=None, attempts=attempts,
                               checks={"passed": False, "reasons": last_reasons, "regenerations": max(0, len(attempts) - 1), "fallback": True})
        self.asked.append({"template": phrase, "utterance": said["text"], "anchor": ""})
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
        if self.image_on:
            self._image_capture()
            self.log.data["capture"]["imageless"] = not self._image_signal_all()["present"]
        self.confirm_draft = "\n".join(self.participant_texts)
        self._say_fixed("confirm_intro", stage=None, kind="confirm", draft=self.confirm_draft)
        self.state, self.awaiting = "confirm", "confirm"

    def _record_confirmation(self, text: str, edited: bool) -> None:
        self.log.data["confirmedText"] = text
        self.log.data["confirmation"] = {"edited": edited, "draft": self.confirm_draft, "at": now_iso()}
        self.log.data["extraction"] = self.rt.extractor.run(text, self.log.data["capture"].get("bodyRelation"))
        if self.image_on:
            sig = self._img(text)
            self._image_capture()["confirmed"] = {"judgedAt": "confirmed", "present": sig["present"],
                                                  "evidence": sig["evidence"], "excluded": sig["excluded"],
                                                  "edited": edited, "turn": len(self.log.turns) - 1}

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
            self.scene_hashes = None
            if saved:
                others = [Path(v) for k, v in variants.items() if k in ("v0", "v1") and v]
                self.scene_hashes = prereport_mod.freeze_hashes(Path(saved), others)
            self.log.data["sceneSpec"] = {"path": saved, "specVersion": spec["meta"]["specVersion"],
                                          "builder": spec["meta"]["pipeline"]["builder"],
                                          "sourceTextHash": spec["meta"]["sourceTextHash"], "problems": problems,
                                          "mapping": mapping, "variants": variants,
                                          # 시각(frozenAtUtc)은 빼고 남긴다: 같은 확정 텍스트 → 같은 로그 내용(재현 검사)
                                          "sha256": None if self.scene_hashes is None else
                                          {k: v for k, v in self.scene_hashes.items() if k != "frozenAtUtc"}}
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
            if self.rt.llm_fill_prompt is not None:
                self._llm_fill(spec, norm)
        except Exception as exc:  # noqa: BLE001 — 장면 생성 실패가 면담 종료를 막으면 안 된다
            self.log.data["sceneSpec"] = {"path": None, "error": f"{type(exc).__name__}: {exc}"}
            self._alert("scene_spec_error", f"{type(exc).__name__}: {exc}", None)

    def _llm_fill(self, spec: dict, norm: str) -> None:
        """(G77) 확정 스펙을 만든 직후, 후보 화면 전에 한 번. 스펙은 바꾸지 않는다(결과는 선택 단계의 처음 값으로만 쓴다).
        실패해도 면담 종료·장면 파일을 막지 않는다(기록만)."""
        try:
            rec = llm_fill_mod.run(self, spec, norm)
        except Exception as exc:  # noqa: BLE001
            rec = {"version": llm_fill_mod.LLM_FILL_VERSION, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300],
                   "adopted": [], "items": []}
        self.llm_fill = rec
        self.log.add_event("scene:llm_fill", {
            "status": rec.get("status"), "skipReason": rec.get("skipReason"), "cached": rec.get("cached"),
            "offeredSlots": rec.get("offeredSlots"), "rawCount": len(rec.get("rawItems") or []),
            "adopted": [a["slot"] for a in rec.get("adopted") or []],
            "rejected": [{"slot": r.get("slot"), "reasons": r.get("reasons")} for r in rec.get("items") or [] if not r.get("ok")],
            "seconds": rec.get("seconds")})

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
        self.scene_hashes = None
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
