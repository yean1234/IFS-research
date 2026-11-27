"""G73 CP13b: [맞는 게 없어요] 뒤 '다시 적기' 흐름 — 화면 단계·생성 요청·기록(selection 0.4)·덮어쓰기 처음 값.

켜는 조건: [gen3d] enabled = true, [gen3d] resay = true, 후보 문구 판(selection_protocol)에 다시 적기 문구가 있음.
하나라도 아니면 Runtime.resay = None이고 후보·조절·기록·화면 출력은 이 모듈이 없을 때와 바이트 단위로 같다.

흐름(결정 G73·G73-b·G73-c·G73-d):
  후보 화면 [맞는 게 없어요] → (다시 적기 횟수·대기 상한이 남았으면) 단계 resay(phase input) — 아니면 지금처럼 기준 후보 0번 → 조절
  제출 → 위기 판정(면담과 같은 가드: 키워드 → 걸리면 가드 모델도 부르지 않음). 위기면 고정 위기 문구만 내고 멈춘다
         (단계 resay_crisis, 생성기·매핑·LLM 0회, 원칙 4)
       → 백그라운드에서 tools/gen3d/resay.py ResayPipeline.run(공개 함수): 위기 키워드 → 재진술 매핑 → 갈래
           solid  → 형태 프롬프트 → 생성기(회당 후보 ≤ resay_candidates, seed = 0 + 회차×10 + k 고정 순서)
                    → 사이드카 검사(form_assets.check_sidecar, G62와 같은 관문) → 새 후보 + 앞서 본 후보 화면
           mist·light·flame(·none이고 값이 있음) → 생성하지 않고 허용 슬롯 값을 기준 후보 0번 위에 얹어 조절 화면 처음 값으로
           blocked · 프롬프트 차단 · 읽은 값 없음 → '만들지 못했어요'(이유는 연구자 기록에만) → 다시 적기(남았으면) 또는 건너뛰기
  회당 시간 제한·전체 대기 상한을 넘거나 생성기가 실패하거나 [건너뛸게요] → 지금처럼 기준 후보 0번 → 조절(다시 적은 값은 쓰지 않음)

원문: 참여자가 다시 적은 글은 git 밖 <log_dir>/selection/<sessionId>/resay.json에만 쓴다(persist_logs일 때만). selection.json·세션
로그에는 sha256·글자 수·글자 위치·규칙 id만 남기고, 글 조각(ko)과 한글 조각은 지운다(_scrub). 세션 폐기(withdraw)는 이 폴더째 지운다.

생성기 인터페이스: generator(prompt_text, negative_text, seed, *, out_dir, timeout_s, cancel) → {"status": ok|failed|timeout,
"sidecar": 경로 | None, "detail": 글 | None}. 챗봇은 모델을 부르지 않는다(G62-b). 실제 경로는 QueueGenerator(파일 큐 — 저장소 밖
상주 생성 프로세스가 <queue>/<jobId>.job.json을 읽고 out_dir에 GLB + form-asset 사이드카를 쓴 뒤 <jobId>.done.json을 남김).
시험은 가짜 생성기를 주입한다.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

from .candidates import PROPORTION_KEYS, effective_params, proportions_effective, slot_value
from .form_assets import check_sidecar, public_asset
from .paths import REPO_ROOT, shared
from .session_log import now_iso

RESAY_FLOW_VERSION = "ifs-resay-flow/0.1.0"
FORMAT_VERSION_RESAY = "ifs-selection/0.4"
RESAY_TEXT_FORMAT = "ifs-resay-text/0.1"
TEXT_FILE = "resay.json"
GENERATED_RESAID_CHOSEN = "generated_resaid_chosen"   # 출처: 다시 적은 글로 만든 생성 후보를 고름(form.type)
RESAID = "resaid"                                     # 출처: 다시 적은 글에서 읽은 값을 처음 값으로 쓰고 고치지 않음
RESAID_ORIGIN = "generated_resaid"                    # 후보 origin·sources.form.type
STAGE = "resay"
STAGE_CRISIS = "resay_crisis"
PHASES = ("input", "waiting", "notice")
MAX_TEXT_CHARS = 1000
SEED_RULE = "seed = 0 + 회차 × 10 + k(k = 프롬프트 순서, 0부터)"
ADJUST_TABLE = "resay_adjust.v0.json"
REQUIRED_PHRASES = ("resay_intro", "resay_submit_button", "resay_skip_button", "resay_wait", "resay_notice_generated",
                    "resay_blocked", "resay_blocked_retry", "resay_retry_button", "resay_continue_button")
REQUIRED_LABELS = ("density", "emission")
ACTIONS = ("submit", "skip", "retry", "continue")
# 끝난 결과(data.resay.outcome)
OUT_RESAID_CHOSEN = GENERATED_RESAID_CHOSEN
OUT_VALUES = "values_applied"
OUT_EARLIER = "earlier_candidate_chosen"
OUT_SKIPPED = "skipped"
OUT_EXHAUSTED = "exhausted"
OUT_TIMEOUT = "timeout"
OUT_FAILED = "generator_failed"
OUT_CRISIS = "crisis"
_HANGUL = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힣]+")
_PAREN = re.compile(r"\([^()]*\)")
_TEXT_KEYS = frozenset({"ko", "trigger", "surface", "norm", "match", "text_ko"})


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scrub(obj):
    """기록용 사본: 글 조각 키(ko 등)를 빼고, 규칙 id의 괄호 속 글과 남은 한글 조각을 '…'로 바꾼다(원문은 resay.json에만)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in _TEXT_KEYS:
                continue
            if k in ("rule", "rules") and v is not None:
                v = [_PAREN.sub("", r) if isinstance(r, str) else r for r in v] if isinstance(v, list) else \
                    (_PAREN.sub("", v) if isinstance(v, str) else v)
            out[k] = _scrub(v)
        return out
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str):
        return _HANGUL.sub("…", obj)
    return obj


def _gen3d_resay():
    """tools/gen3d/resay.py(CP13a 공개 함수: ResayPipeline·load_filter). torch 등 모델 의존 없음."""
    gen3d = str(REPO_ROOT / "tools" / "gen3d")
    if gen3d not in sys.path:
        sys.path.insert(0, gen3d)
    return importlib.import_module("resay")


# ── 생성기 ──────────────────────────────────────────────────────────────────
class QueueGenerator:
    """저장소 밖 상주 생성 프로세스(tools/gen3d, localhost 전용)와 파일 큐로 주고받는다. 외부 전송 없음.
    작업 파일 <queue>/<jobId>.job.json {schema, jobId, promptText, negativeText, seed, outDir} → 생성 프로세스가 outDir에
    GLB + form-asset 사이드카를 쓰고 <jobId>.done.json {status: ok|failed, sidecar: 파일 이름, detail}을 남긴다.
    시간 안에 done이 없으면 <jobId>.cancel을 남기고 timeout."""

    POLL_S = 0.5

    def __init__(self, queue_dir: Path):
        self.queue_dir = Path(queue_dir)

    @property
    def info(self) -> dict:
        return {"kind": "queue", "protocol": "ifs-gen3d-job/0"}

    def __call__(self, prompt_text: str, negative_text: str, seed: int, *, out_dir: Path, timeout_s: float,
                 cancel: threading.Event) -> dict:
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        job_id = sha256_text(f"{out_dir}|{seed}|{prompt_text}|{negative_text}")[:16]
        job = {"schema": "ifs-gen3d-job/0", "jobId": job_id, "promptText": prompt_text, "negativeText": negative_text,
               "seed": seed, "outDir": str(out_dir), "createdAt": now_iso()}
        tmp = self.queue_dir / f"{job_id}.job.json.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.queue_dir / f"{job_id}.job.json")
        done = self.queue_dir / f"{job_id}.done.json"
        end = time.monotonic() + max(0.0, timeout_s)
        while time.monotonic() < end and not cancel.is_set():
            if done.is_file():
                try:
                    d = json.loads(done.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    time.sleep(self.POLL_S)
                    continue
                side = d.get("sidecar")
                return {"status": d.get("status") if d.get("status") in ("ok", "failed") else "failed",
                        "sidecar": (out_dir / Path(side).name) if isinstance(side, str) and side else None,
                        "detail": str(d.get("detail") or "")[:300] or None}
            time.sleep(self.POLL_S)
        (self.queue_dir / f"{job_id}.cancel").write_text("", encoding="utf-8")
        return {"status": "timeout", "sidecar": None, "detail": "cancelled" if cancel.is_set() else None}


def make_generator(cfg, log_dir: Path):
    kind = cfg.gen3d.resay_generator
    if kind == "":
        return None
    if kind == "queue":
        q = Path(cfg.gen3d.resay_queue_dir) if cfg.gen3d.resay_queue_dir else Path(log_dir) / "gen3d-queue"
        return QueueGenerator(q)
    raise ValueError(f"[gen3d] resay_generator는 \"\" | \"queue\": {kind!r}")


# ── 런타임 하나에 하나 ───────────────────────────────────────────────────────
class ResayService:
    """설정·표·파이프라인(늦게 만듦)·생성기. SelectionFlow마다 ResayState를 만든다."""

    def __init__(self, rt, generator=None, pipeline=None):
        self.rt = rt
        g = rt.cfg.gen3d
        self.max_rounds = max(0, int(g.resay_max_rounds))
        self.max_candidates = max(0, int(g.resay_candidates))
        self.round_timeout_s = float(g.resay_round_timeout_s)
        self.total_wait_s = float(g.resay_total_wait_s)
        self.generator = generator if generator is not None else make_generator(rt.cfg, rt.cfg.log_dir)
        self._pipeline = pipeline
        self._lock = threading.Lock()
        raw = shared("lexicon", ADJUST_TABLE).read_text(encoding="utf-8")
        self.adjust = json.loads(raw)
        self.adjust_info = {"file": ADJUST_TABLE, "id": f"{self.adjust['lexiconId']}@{self.adjust['tableVersion']}",
                            "sha256": sha256_text(raw)}

    @property
    def pipeline(self):
        """처음 부를 때 만든다(Kiwi·매퍼 초기화). 백그라운드 작업 안에서 부르므로 회당 제한 시간에 들어간다(CP13b 지적 1)."""
        with self._lock:
            if self._pipeline is None:
                self._pipeline = self._build_pipeline()
            return self._pipeline

    def _build_pipeline(self):
        rs = _gen3d_resay()
        from .resay import ResayMapper
        return rs.ResayPipeline(self.rt.cfg.gen3d, mapper=ResayMapper(self.rt.analyzer), safety=self.rt.safety)

    def setting(self) -> dict:
        gen = self.generator
        return {"maxRounds": self.max_rounds, "candidates": self.max_candidates, "roundTimeoutS": self.round_timeout_s,
                "totalWaitS": self.total_wait_s, "seedRule": SEED_RULE,
                "generator": (getattr(gen, "info", None) or {"kind": type(gen).__name__}) if gen is not None else {"kind": "none"}}

    def crisis_phrase(self) -> str:
        return self.rt.protocol.phrase("crisis", researcher_contact=self.rt.cfg.session.researcher_contact)


def missing_phrases(protocol) -> list[str]:
    ph = protocol.data.get("phrases", {})
    lb = protocol.data.get("adjustItemLabels", {})
    return [f"phrases.{k}" for k in REQUIRED_PHRASES if k not in ph] + \
           [f"adjustItemLabels.{k}" for k in REQUIRED_LABELS if k not in lb]


# ── 세션 하나 ───────────────────────────────────────────────────────────────
class ResayState:
    """SelectionFlow 하나의 다시 적기 상태. 모든 공개 메서드는 flow.lock 안에서 부른다(백그라운드 결과도 lock을 잡고 들어온다)."""

    def __init__(self, flow, svc: ResayService):
        self.f, self.svc = flow, svc
        self.phase: str | None = None
        self.round = 0                      # 지금(마지막) 회차. 0 = 다시 적기 화면을 아직 보이지 않음
        self.token = 0                      # 진행 중 회차 표시(건너뛰기·시간 초과 뒤 늦게 온 결과를 버림)
        self.thread: threading.Thread | None = None
        self.cancel = threading.Event()
        self.started: float | None = None
        self.deadline: float | None = None
        self.wait_used = 0.0                # 모든 회차의 기다림 합(초)
        self.pending: dict | None = None    # 갈래 solid 회차의 값(새 후보를 고르면 처음 값으로 씀)
        self.new_ids: list[str] = []        # 이번 회차 새 후보
        self.notice_retry = False
        self.extra_items: dict[str, dict] = {}     # 이 세션에 더한 조절 항목(density·emission)
        self.applied: list[dict] = []        # 조절 화면 처음 값으로 쓴 값

    # ── 기록 ────────────────────────────────────────────────────────────────
    @property
    def rec(self) -> dict:
        return self.f.data["resay"]

    def init_record(self) -> dict:
        return {"version": RESAY_FLOW_VERSION, "setting": self.svc.setting(),
                "tables": {"adjust": dict(self.svc.adjust_info), "mapping": None, "prompt": None},
                "protocolVersion": self.f.protocol.version, "exposed": False, "textFile": None,
                "nonePresses": [], "events": [], "rounds": [], "outcome": None, "overrides": [], "dropped": [],
                "renderVars": None, "totalWaitMs": 0}

    def _event(self, event: str, **kw) -> dict:
        ev = {"i": len(self.rec["events"]), "event": event, "round": self.round or None, "at": now_iso(), **kw}
        self.rec["events"].append(ev)
        return ev

    def _round_rec(self) -> dict:
        return self.rec["rounds"][self.round - 1]

    def _log(self, kind: str, payload: dict) -> None:
        self.f._log_event(f"selection:resay_{kind}", payload)

    def _text_path(self) -> Path:
        return self.f.dir / TEXT_FILE

    def _write_text(self, round_no: int, **fields) -> None:
        """원문 파일(git 밖, persist일 때만). 회차별 원문과 글 조각이 든 매핑·프롬프트 원본."""
        if not self.f.persist:
            return
        self.f.dir.mkdir(parents=True, exist_ok=True)
        p = self._text_path()
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else \
            {"formatVersion": RESAY_TEXT_FORMAT, "sessionId": self.f.s.id, "rounds": []}
        r = next((x for x in data["rounds"] if x["round"] == round_no), None)
        if r is None:
            r = {"round": round_no}
            data["rounds"].append(r)
        r.update(fields)
        tmp = self.f.dir / (TEXT_FILE + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        os.replace(tmp, p)
        self.rec["textFile"] = TEXT_FILE

    # ── 남은 횟수·시간 ──────────────────────────────────────────────────────
    def time_left(self) -> float:
        return self.svc.total_wait_s - self.wait_used

    def can_start_round(self) -> bool:
        return self.round < self.svc.max_rounds and self.time_left() > 0

    # ── 후보 화면 [맞는 게 없어요] ───────────────────────────────────────────
    def on_none(self) -> bool:
        """[맞는 게 없어요]. 여기서 처리했으면 True(다시 적기 화면으로 가거나, 회차를 다 써서 기준 후보 0번 → 조절로 끝냄),
        다시 적기를 한 번도 보이지 않았고 보일 수도 없으면 False(SelectionFlow.select의 지금 경로)."""
        self.rec["nonePresses"].append({"afterRound": self.round, "at": now_iso()})
        if self.can_start_round():
            self._show_input()
            self.f.data["stage"] = STAGE
            self.f._save()
            return True
        if self.round > 0:
            self._end(OUT_EXHAUSTED if self.round >= self.svc.max_rounds else OUT_TIMEOUT,
                      reason="rounds_used" if self.round >= self.svc.max_rounds else "total_wait")
            return True
        return False

    def _show_input(self) -> None:
        self.round += 1
        self.phase = "input"
        self.pending, self.new_ids, self.notice_retry = None, [], False
        self.rec["exposed"] = True
        self.rec["rounds"].append({"round": self.round, "shownAt": now_iso(), "submittedAt": None, "textSha256": None,
                                   "normalizedSha256": None, "chars": None, "safety": None, "status": None,
                                   "branch": None, "branchBasis": [], "blockDetail": None, "values": None,
                                   "notRead": [], "dropped": [], "prompt": None, "generation": [], "candidateIds": [],
                                   "waitMs": None, "outcome": None})
        self._event("screen_shown")
        self._log("shown", {"round": self.round})

    # ── 다시 적기 화면 동작 ─────────────────────────────────────────────────
    def action(self, action: str, text: str | None) -> None:
        from .selection import SelectionError, SelectionInvalid
        if action not in ACTIONS:
            raise SelectionInvalid(f"모르는 다시 적기 동작: {action!r} (가능: {', '.join(ACTIONS)})")
        self.check_timeout()
        if self.f.stage != STAGE:
            if action == "skip" and self.f.stage == "adjusting" and self.rec["outcome"] in (OUT_TIMEOUT, OUT_FAILED, OUT_SKIPPED):
                return                                   # 시간 초과와 [건너뛸게요]가 겹침: 이미 지금 경로로 갔다
            raise SelectionError(f"지금은 다시 적기 단계가 아닙니다(지금: {self.f.stage}).")
        if action == "skip":
            self._skip()
        elif action == "submit":
            if self.phase != "input":
                raise SelectionError("글을 적는 화면이 아닙니다.")
            if not isinstance(text, str) or not text.strip():
                raise SelectionInvalid("적은 글이 없습니다.")
            if len(text) > MAX_TEXT_CHARS:
                raise SelectionInvalid(f"글이 너무 깁니다({MAX_TEXT_CHARS}자 이하).")
            self._submit(text)
        elif action == "retry":
            if self.phase != "notice" or not self.notice_retry:
                raise SelectionError("다시 적을 수 없습니다.")
            self._show_input()
            self.f._save()
        else:   # continue
            if self.phase != "notice" or self.notice_retry:
                raise SelectionError("지금은 [다음으로]를 받을 수 없습니다.")
            self._end(OUT_EXHAUSTED, reason="blocked_last_round")

    def _skip(self) -> None:
        r = self._round_rec()
        if self.phase == "waiting":
            self._stop_wait()
            r["outcome"] = "skipped_while_waiting"
        elif r["outcome"] is None:
            r["outcome"] = "skipped"
        self._end(OUT_SKIPPED, reason=f"phase_{self.phase}")

    def _submit(self, text: str) -> None:
        # 회당 제한 시간은 제출 시각에 시작한다. 위기 판정·파이프라인 초기화(Kiwi·매퍼)·매핑·생성이 모두 그 안에 든다(CP13b 지적 1)
        submitted = time.monotonic()
        r = self._round_rec()
        r.update(submittedAt=now_iso(), textSha256=sha256_text(text), chars=len(text))
        self._event("submitted", textSha256=r["textSha256"], chars=len(text))
        self._write_text(self.round, text=text, textSha256=r["textSha256"], submittedAt=r["submittedAt"])
        # 위기 판정: 면담과 같은 가드(키워드가 위기면 가드 모델도 부르지 않음). 위기면 매핑·생성기·LLM을 부르지 않는다(원칙 4)
        v = self.f.rt.guard.check_input(text)
        r["safety"] = {"level": v.level, "alert": v.alert, "reasons": _scrub(list(v.reasons)),
                       "keywordIds": sorted({str(h.get("id")) for h in v.keyword_hits}),
                       "model": None if v.model is None else {k: v.model.get(k) for k in ("label", "category")}}
        if v.level == "crisis":
            self._crisis(r, "guard")
            return
        self.phase = "waiting"
        self.token += 1
        self.cancel = threading.Event()
        self.started = submitted
        self.deadline = submitted + max(0.0, min(self.svc.round_timeout_s, self.time_left()))
        self.f._save()
        self._log("submitted", {"round": self.round, "textSha256": r["textSha256"], "chars": len(text),
                                "safety": r["safety"]["level"]})
        token, round_no, cancel, deadline = self.token, self.round, self.cancel, self.deadline
        out_dir = self._asset_dir(round_no)
        self.thread = threading.Thread(target=self._work, args=(text, token, round_no, cancel, deadline, out_dir),
                                       name=f"resay-{self.f.s.id}-{round_no}", daemon=True)
        self.thread.start()

    def _asset_dir(self, round_no: int) -> Path:
        if self.f.persist:
            return self.f.dir / "resay-assets" / f"r{round_no}"
        return Path(tempfile.mkdtemp(prefix=f"ifs-resay-{self.f.s.id}-r{round_no}-"))

    def _crisis(self, r: dict, by: str) -> None:
        r["outcome"] = "crisis"
        self.phase = None
        self.rec["outcome"] = OUT_CRISIS
        self._event("crisis", by=by)
        self.f.data["stage"] = STAGE_CRISIS
        self.f._save()
        self.f.s._alert("resay_crisis", f"다시 적기 {self.round}회차 글에서 위기 판정({by}). 고정 문구만 냄, 생성기·매핑 0회",
                        None, "critical")
        self._log("crisis", {"round": self.round, "by": by})

    # ── 백그라운드 ──────────────────────────────────────────────────────────
    def _work(self, text, token, round_no, cancel, deadline, out_dir) -> None:
        calls: list[dict] = []

        def generator(prompt_text, negative_text, seed):
            if cancel.is_set() or time.monotonic() >= deadline:
                calls.append({"seed": seed, "status": "timeout", "called": False, "waitMs": 0})
                return calls[-1]
            t0 = time.monotonic()
            try:
                res = self.svc.generator(prompt_text, negative_text, seed, out_dir=out_dir / f"s{seed}",
                                         timeout_s=max(0.0, deadline - t0), cancel=cancel)
            except Exception as exc:          # 생성기 오류는 실패로 기록하고 흐름은 지금 경로로
                res = {"status": "failed", "sidecar": None, "detail": f"{type(exc).__name__}: {exc}"[:300]}
            res = {**res, "seed": seed, "called": True, "waitMs": int((time.monotonic() - t0) * 1000)}
            calls.append(res)
            return res

        try:
            pipeline = self.svc.pipeline                 # 첫 회차면 여기서 초기화(제한 시간 안)
            out = pipeline.run(text, round_no=round_no,
                               generator=generator if self.svc.generator is not None else None)
            err = None
        except Exception as exc:
            out, err = None, f"{type(exc).__name__}: {exc}"[:300]
        with self.f.lock:
            if token != self.token or self.f.data is None:
                return                                   # 건너뛰기·시간 초과·철회 뒤에 온 결과는 버린다
            self.check_timeout()                         # 제한 시간을 넘겨 끝났으면 결과를 쓰지 않고 지금 경로로
            if token != self.token:
                return
            self._finish(out, err, calls, text)

    def join(self, timeout: float | None = None) -> None:
        """시험용: 진행 중인 회차를 기다린다."""
        t = self.thread
        if t is not None:
            t.join(timeout)

    def cancel_work(self) -> None:
        """철회·세션 종료·서버 종료(CP13b 지적 3): 진행 중 회차의 토큰을 무효화하고 생성기에 취소를 알린다.
        늦게 온 결과는 _work가 버린다. 기록은 고치지 않는다(철회면 폴더째 지우고, 종료면 끝나지 않은 회차로 남는다)."""
        self.token += 1
        self.cancel.set()

    def _stop_wait(self) -> None:
        self.token += 1
        self.cancel.set()
        if self.started is not None:
            used = time.monotonic() - self.started
            self.wait_used += used
            self.rec["totalWaitMs"] = int(self.wait_used * 1000)
            self._round_rec()["waitMs"] = int(used * 1000)
        self.started = self.deadline = None

    def check_timeout(self) -> None:
        """기다리는 중에 시간이 지났으면(생성기가 시간 제한을 지키지 않아도) 지금 경로로 끝낸다."""
        if self.f.data is None or self.f.stage != STAGE or self.phase != "waiting" or self.deadline is None:
            return
        if time.monotonic() < self.deadline:
            return
        self._stop_wait()
        self._round_rec()["outcome"] = "timeout"
        self._end(OUT_TIMEOUT, reason="round_timeout")

    def _finish(self, out, err, calls, text) -> None:
        r = self._round_rec()
        used = time.monotonic() - self.started if self.started is not None else 0.0
        self.wait_used += used
        self.rec["totalWaitMs"] = int(self.wait_used * 1000)
        r["waitMs"] = int(used * 1000)
        self.started = self.deadline = None
        if out is None:
            r["outcome"] = "error"
            r["status"] = "error"
            r["error"] = _scrub(err)
            self._end(OUT_FAILED, reason="pipeline_error")
            return
        r["status"] = out["status"]
        if out["status"] == "crisis":
            r["safety"] = {**(r["safety"] or {}), "pipelineKeywordIds": out.get("crisisIds")}
            self._crisis(r, "pipeline_keyword")
            return
        m = out.get("mapping")
        if m is None:                                    # disabled·round_limit은 여기 오지 않는다(설정·회차를 앞에서 막음)
            r["outcome"] = "error"
            self._end(OUT_FAILED, reason=f"pipeline_{out['status']}")
            return
        self.rec["tables"]["mapping"] = _scrub(m["tables"]) | {"mappingVersion": m["mappingVersion"]}
        r.update(normalizedSha256=m["sourceTextSha256"], branch=m["branch"],
                 branchBasis=_scrub(m["branchBasis"]), blockDetail=_scrub(m["blockDetail"]),
                 values=_scrub(m["values"]), notRead=_scrub(m["notRead"]), dropped=_scrub(m["dropped"]))
        pr = out.get("prompt")
        if pr is not None:
            self.rec["tables"]["prompt"] = {k: _scrub(pr.get(k)) for k in ("promptVersion", "filter", "bilingualDict", "wordnet")}
            r["prompt"] = {"status": pr["status"], "blockReason": pr.get("blockReason"),
                           "blockDetail": _scrub(pr.get("blockDetail")),
                           "prompts": [_scrub({k: p.get(k) for k in ("text", "negativeText", "sense", "tokens")})
                                       for p in pr.get("prompts") or []]}
        self._write_text(self.round, mapping=m, prompt=pr, status=out["status"])
        branch = m["branch"]
        if branch == "solid":
            self._finish_solid(r, out, calls, m)
            return
        if branch == "blocked":
            self._notice(r, "blocked")
            return
        entries = self._entries(m)
        if not entries:
            self._notice(r, "nothing_read")
            return
        r["outcome"] = "values"
        self._event("values_shown", slots=[e["slot"] for e in entries])
        self._enter_adjusting(OUT_VALUES, entries)

    def _finish_solid(self, r: dict, out: dict, calls: list[dict], m: dict) -> None:
        pr = out.get("prompt") or {}
        if pr.get("status") != "ok":
            self._notice(r, "prompt_blocked")
            return
        if out["status"] == "no_generator" or self.svc.generator is None:
            self._notice(r, "no_generator")
            return
        gen_rows, assets = [], []
        for c in out.get("candidates") or []:
            res = c.get("result") or {}
            row = {"k": c["k"], "seed": c["seed"], "sense": _scrub(c.get("sense")), "status": res.get("status"),
                   "called": bool(res.get("called")), "waitMs": res.get("waitMs"), "assetId": None, "candidateId": None,
                   "reason": None, "detail": _scrub(res.get("detail"))}
            self._event("generation_attempt", k=c["k"], seed=c["seed"], status=res.get("status"), called=row["called"])
            if res.get("status") == "ok" and res.get("sidecar"):
                side = Path(res["sidecar"])
                try:
                    data = json.loads(side.read_text(encoding="utf-8"))
                    a, rej = check_sidecar(side, data)
                except (OSError, ValueError) as exc:
                    a, rej = None, {"reason": "sidecar_invalid", "detail": f"{type(exc).__name__}"}
                if a is not None:
                    a["_k"], a["_sense"] = c["k"], row["sense"]
                    assets.append(a)
                    row["assetId"] = a["assetId"]
                else:
                    row["reason"], row["detail"] = rej.get("reason"), _scrub(rej.get("detail"))
            elif res.get("status") == "ok":
                row["reason"] = "no_sidecar"
            gen_rows.append(row)
        r["generation"] = gen_rows
        if not assets:
            timed_out = any(g["status"] == "timeout" for g in gen_rows)
            r["outcome"] = "timeout" if timed_out else "generator_failed"
            self._end(OUT_TIMEOUT if timed_out else OUT_FAILED, reason=r["outcome"])
            return
        ids = self._add_candidates(assets)
        for row in gen_rows:
            row["candidateId"] = next((cid for cid, a in zip(ids, assets) if a["assetId"] == row["assetId"]), None)
        r["candidateIds"] = ids
        r["outcome"] = "candidates"
        self.new_ids = ids
        self.pending = {"round": self.round, "entries": self._entries(m)}
        self.phase = None
        self.f.data["stage"] = "selecting"
        self._event("candidates_shown", candidateIds=ids, displayOrder=list(self.f.cands["displayOrder"]))
        self.f._save()
        self._log("candidates", {"round": self.round, "candidateIds": ids,
                                 "assetIds": [a["assetId"] for a in assets]})

    def _add_candidates(self, assets: list[dict]) -> list[str]:
        cands = self.f.cands
        base = cands["candidates"][0]
        start = max(c["index"] for c in cands["candidates"]) + 1
        ids = []
        for k, a in enumerate(assets):
            sources = dict(base["sources"])
            sources["form.type"] = RESAID_ORIGIN
            cid = f"r{self.round}-" + sha256_text(f"{RESAY_FLOW_VERSION}|{cands['specSha256']}|{self.round}|"
                                                  f"{a['assetId']}|{a['glbSha256']}")[:12]
            cands["candidates"].append({"id": cid, "index": start + k, "overrides": dict(base["overrides"]),
                                        "axisValues": {}, "sources": sources, "origin": RESAID_ORIGIN,
                                        "asset": public_asset(a), "resayRound": self.round, "sense": a["_sense"]})
            self.f._asset_paths[cid] = a["_glbPath"]
            self.f._sidecar_paths[cid] = a["_sidecarPath"]
            ids.append(cid)
        cands["displayOrder"] = ids + [c for c in cands["displayOrder"] if c not in ids]
        return ids

    def _notice(self, r: dict, why: str) -> None:
        r["outcome"] = why
        self.phase = "notice"
        self.notice_retry = self.can_start_round()
        self._event("blocked_shown", reason=why, canRetry=self.notice_retry)
        self.f._save()
        self._log("blocked", {"round": self.round, "reason": why, "canRetry": self.notice_retry})

    # ── 덮어쓰기 처음 값 ────────────────────────────────────────────────────
    def _entries(self, m: dict) -> list[dict]:
        """매핑 값 → 조절 화면 처음 값(덮어쓰기 키). 조절 항목이 없어 참여자가 고칠 수 없는 값은 쓰지 않고 dropped에 남긴다."""
        table = self.f.table
        items = table["adjustItems"]["items"]
        tbl_id = self.svc.adjust_info["id"]
        out, dropped = [], []

        def add(slot, item_ids, keys, val, src_rec, source, rules, table_id):
            out.append({"slot": slot, "items": item_ids, "keys": keys, "value": copy.deepcopy(val),
                        "charSpans": copy.deepcopy(src_rec.get("charSpans") or []), "rules": _scrub({"rules": rules})["rules"],
                        "source": source, "table": table_id, "mappingVersion": m["mappingVersion"], "round": self.round})

        branch = m["branch"]
        form_val = self.svc.adjust["branchForm"].get(branch)
        if form_val is not None and "form" in items and form_val in items["form"].get("valueOverrides", {}):
            if branch == "mist" and m["values"].get("form.type"):
                v = m["values"]["form.type"]
                add("form.type", ["form"], dict(items["form"]["valueOverrides"][form_val]), form_val, v, v["source"],
                    v["rules"], v["table"])
            elif branch != "mist" and m["branchBasis"]:
                b = m["branchBasis"][0]
                add("form.base", ["form"], dict(items["form"]["valueOverrides"][form_val]), form_val,
                    {"charSpans": [b["charSpan"]]}, "resay_branch", [f"resay.branchForm.{branch}>form:{form_val}"], tbl_id)
        for slot, v in m["values"].items():
            if v is None or slot == "form.type":
                continue
            if slot == "mist.density":
                if branch != "mist":
                    dropped.append({"slot": slot, "reason": "branch_not_mist"})
                    continue
                self.extra_items["density"] = self.svc.adjust["items"]["density"]
                add(slot, ["density"], {"mist.density": float(v["value"])}, v["value"], v, v["source"], v["rules"], v["table"])
            elif slot == "material.emission":
                self.extra_items["emission"] = self.svc.adjust["items"]["emission"]
                add(slot, ["emission"], {"material.emission": v["value"]}, v["value"], v, v["source"], v["rules"], v["table"])
            elif slot == "material.opacity":
                if "opacity" not in items:
                    dropped.append({"slot": slot, "reason": "no_adjust_item"})
                    continue
                add(slot, ["opacity"], {"material.opacity": float(v["value"])}, v["value"], v, v["source"], v["rules"],
                    v["table"])
            elif slot == "layout.proportions":
                if not all(i in items for i in ("width", "height", "depth")):
                    dropped.append({"slot": slot, "reason": "no_adjust_item"})
                    continue
                pv = v["value"]
                add(slot, ["width", "height", "depth"],
                    {k: float(pv[ax]) for k, ax in zip(PROPORTION_KEYS, "xyz")}, pv, v, v["source"], v["rules"], v["table"])
            else:
                dropped.append({"slot": slot, "reason": "not_mapped"})
        if dropped:
            self.rec["dropped"].extend({**d, "round": self.round} for d in dropped)
        return out

    def _apply(self, entries: list[dict]) -> None:
        """기준 덮어쓰기(self.f.current) 위에 얹는다. slotsChanged는 기록용(처음 값과 달라진 슬롯)이고, resaid 출처는
        값이 바뀌었는지와 따로 적용된 재진술 슬롯(_resaid_slots)에 단다(CP13b 지적 2)."""
        before = effective_params(self.f.spec, self.f.defaults, self.f.current)
        for e in entries:
            changed = sorted({_slot_of(k) for k, val in e["keys"].items() if before.get(k) != val})
            self.f.current.update(e["keys"])
            self.applied.append({**e, "slotsChanged": changed, "first": copy.deepcopy(e["keys"]),
                                 "final": None, "edited": None})
        self.rec["overrides"] = self.applied
        for item in list(self.extra_items):
            if not any(item in e["items"] for e in self.applied):
                self.extra_items.pop(item)

    # ── 끝내기 ──────────────────────────────────────────────────────────────
    def _end(self, outcome: str, reason: str) -> None:
        """지금 경로: 기준 후보 0번 → 조절. 다시 적은 값은 쓰지 않는다."""
        self._event("ended", outcome=outcome, reason=reason)
        self._enter_adjusting(outcome, [])

    def _enter_adjusting(self, outcome: str, entries: list[dict]) -> None:
        f = self.f
        op = f.cands["candidates"][0]
        sel = {"selectedCandidateId": None, "selectedIndex": None, "none": True, "skipped": False,
               "displayPosition": None, "operationalId": op["id"], "operationalIndex": op["index"], "at": now_iso(),
               "resayRound": self.round or None}
        f.data["selection"] = sel
        f.data["stage"] = "adjusting"
        f.current = dict(op["overrides"])
        self.phase = None
        self.new_ids = []
        if not entries:
            self.extra_items = {}
        if f.gen3d:
            f._record_generation_choice(None)
            f.data["generation"]["outcome"] = "none"
        if entries:
            self._apply(entries)
        self.rec["outcome"] = outcome
        f._save()
        f._log_event("selection:selected", {k: sel[k] for k in ("selectedCandidateId", "none", "displayPosition",
                                                                 "operationalId", "operationalIndex")})
        self._log("ended", {"outcome": outcome, "round": self.round, "applied": [e["slot"] for e in entries]})

    def after_select(self, op: dict, choice: str) -> None:
        """후보 화면에서 후보를 고른 뒤(SelectionFlow.select 안). 다시 적은 글로 만든 후보면 자산 기록·처음 값을 얹는다."""
        sel = self.f.data["selection"]
        sel["resayRound"] = self.round or None
        self.new_ids = []
        if self.round == 0:
            return
        if choice != "none" and op.get("origin") == RESAID_ORIGIN:
            f = self.f
            gen = f.data["generation"]
            gen["outcome"] = GENERATED_RESAID_CHOSEN
            f.data["form"]["asset"] = {**f._asset_record(op), "resayRound": op["resayRound"]}
            self._event("chosen", candidateId=op["id"], resaid=True)
            entries = self.pending["entries"] if self.pending and self.pending["round"] == op["resayRound"] else []
            if self.pending and self.pending["round"] != op["resayRound"]:
                self.rec["dropped"].append({"slot": "*", "reason": "chosen_candidate_from_earlier_round", "round": self.round})
            if entries:
                self._apply(entries)
            self.rec["outcome"] = OUT_RESAID_CHOSEN
        elif choice != "none":
            self._event("chosen", candidateId=op["id"], resaid=False)
            self.extra_items = {}
            self.rec["outcome"] = OUT_EARLIER
        self._log("chosen", {"candidateId": None if choice == "none" else op["id"], "outcome": self.rec["outcome"]})

    # ── 조절 마친 뒤 ────────────────────────────────────────────────────────
    def on_finish(self, final_params: dict) -> None:
        summ = self.f.data["adjustments"]["items"]
        for e in self.applied:
            e["final"] = {k: _round(final_params.get(k)) for k in e["keys"]}
            e["edited"] = any(_round(final_params.get(k)) != _round(v) for k, v in e["keys"].items())
            e["adjustCount"] = sum(summ.get(i, {}).get("count", 0) for i in e["items"])
        p = final_params
        spec_em = slot_value(self.f.spec, "material.emission")
        self.rec["renderVars"] = {
            "formType": p.get("form.type"), "formBase": p.get("form.base"),
            "opacity": _round(p.get("material.opacity")),
            "mistDensity": _round(p["mist.density"]) if "mist.density" in p else None,
            "mistDensityRule": "덮어쓰기 mist.density가 있으면 그 값이 Unity mist 프리셋 밀도(기본 0.5)를 대신한다(form.type mist일 때만 그림)",
            "emission": p.get("material.emission", spec_em),
            "size": _round(p.get("layout.size")),
            "proportions": proportions_effective(p) if PROPORTION_KEYS[0] in p else None,
            "measuredDims": None,
            "measuredDimsNote": "실측 치수는 Unity가 그린 경계 상자에서 잰다(러너·미리보기 기록). 챗봇 쪽에서는 재지 않는다",
        }

    def slot_sources(self, out: dict, counts: dict, edited: dict, final_params: dict) -> None:
        """_slot_sources 결과에 다시 적기 출처를 얹는다: 고른 생성 후보가 다시 적은 글의 것이면 generated_resaid_chosen,
        처음 값으로 쓰고 고치지 않은 슬롯은 resaid."""
        ft = out.get("form.type")
        asset = (self.f.data.get("form") or {}).get("asset")
        if ft is not None and ft["source"] == "generated_chosen" and asset is not None and asset.get("resayRound"):
            counts[ft["source"]] -= 1
            ft["source"] = GENERATED_RESAID_CHOSEN
            ft["resayRound"] = asset["resayRound"]
            counts[GENERATED_RESAID_CHOSEN] += 1
        summ = self.f.data["adjustments"]["items"]
        for e in self.applied:
            # 이 값의 조절 항목을 처음 값과 다른 값으로 끝냈으면 참여자가 고친 것(edited). 처음 값이 spec과 달라서, 바꿨다가
            # spec 값으로 돌아온 경우도 SelectionFlow 규칙(spec 기준)으로는 '고침'이 아니게 보이므로 여기서 바로잡는다
            item_edited = any(i in summ and not _same(summ[i]["last"], summ[i]["first"]) for i in e["items"])
            for slot in _resaid_slots(e):
                if slot not in out or slot in edited:
                    continue
                rec = out[slot]
                if rec["source"] in ("generated_chosen", GENERATED_RESAID_CHOSEN):
                    continue
                counts[rec["source"]] -= 1
                if item_edited:
                    rec.update(source="edited", value=_slot_final(slot, final_params, e))
                    counts["edited"] += 1
                    continue
                if slot == "layout.proportions":
                    val = {**proportions_effective(final_params), "axisSaid": bool((e["value"] or {}).get("axisSaid", True))}
                elif slot == "form.type":
                    val = final_params["form.type"]
                elif slot == "form.base":
                    val = final_params.get("form.base")
                else:
                    val = _round(final_params.get(slot))
                rec.update(source=RESAID, value=val,
                           resay={"round": e["round"], "charSpans": e["charSpans"], "rules": e["rules"],
                                  "mappingVersion": e["mappingVersion"], "table": e["table"]})
                counts[RESAID] += 1

    # ── 화면 ────────────────────────────────────────────────────────────────
    def visible_extra_items(self, params: dict) -> list[str]:
        out = []
        for item, it in self.extra_items.items():
            want = (it.get("showWhen") or {}).get("formType")
            if want is None or params.get("form.type") == want:
                out.append(item)
        return out

    def view(self) -> dict:
        f = self.f
        r = self.rec["rounds"][-1] if self.rec["rounds"] else None
        out = {"active": True, "stage": f.stage, "phase": self.phase if f.stage == STAGE else None,
               "round": self.round, "maxRounds": self.svc.max_rounds,
               "canRetry": bool(self.phase == "notice" and self.notice_retry),
               "newCandidateIds": list(self.new_ids) if f.stage == "selecting" else [],
               "elapsedMs": int((time.monotonic() - self.started) * 1000) if self.phase == "waiting" and self.started else None,
               "crisisPhrase": self.svc.crisis_phrase() if f.stage == STAGE_CRISIS else None,
               # 연구자 화면용(참여자 화면에는 그리지 않음): 갈래·결과·만들지 못한 이유
               "researcher": {"outcome": self.rec["outcome"], "exposed": self.rec["exposed"],
                              "branch": r["branch"] if r else None, "roundOutcome": r["outcome"] if r else None,
                              "blockReason": ((r.get("prompt") or {}).get("blockReason") if r else None),
                              "blockDetail": r["blockDetail"] if r else None,
                              "totalWaitMs": self.rec["totalWaitMs"],
                              "applied": [e["slot"] for e in self.applied]}}
        return out


def _same(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 1e-9
    return a == b


def _resaid_slots(e: dict) -> list[str]:
    """출처 resaid를 다는 슬롯: 다시 적은 글이 정한 슬롯(e.slot)은 값이 기존과 같아도 늘 넣는다(확정 스펙 form.type mist +
    다시 적은 글 mist → resaid). 같은 조절 값이 함께 정하는 다른 슬롯(형태 항목의 form.type·form.base)은 값이 바뀐 것만."""
    return sorted({e["slot"], *e["slotsChanged"]})


def _slot_final(slot: str, p: dict, e: dict):
    if slot == "layout.proportions":
        return {**proportions_effective(p), "axisSaid": True}
    if slot in ("form.type", "form.base"):
        return p.get(slot)
    return _round(p.get(slot))


def _slot_of(key: str) -> str:
    if key.startswith("layout.proportions."):
        return "layout.proportions"
    if key.startswith("material.color."):
        return "material.color"
    return key


def _round(v):
    return round(v, 4) if isinstance(v, float) else v
