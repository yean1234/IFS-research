"""CP13(Codex 구현 검토) 지적 4건: [맞는 게 없어요] 생성(on_none)과 면담 모델의 상호 배제.

1. 모델 내림 실패·잔류 → 생성하지 않음(blocked llm_unload_failed)
2. 생성(내림 ~ 재적재)이 진행 중이면 면담 세션 만들기·시작·답을 받지 않음(409). 키워드 위기 문장은 통과(모델 없이 고정 문구, CP12).
   재적재 실패 → 모델 준비 안 됨 → guard.required면 세션 만들기를 막고, 백그라운드 재시도로 돌아오면 다시 받음.
3. 앞 작업의 재적재 중에 예약한 다시 만들기는 재적재가 끝난 뒤에 시작.
4. [기다리지 않고 넘어갈게요]는 프로세스 끄기를 기다리지 않고 곧 응답.
생성기는 대역(tests/fixtures/fake_gen3d.py), Ollama는 모의 HTTP. 대사는 합성."""
import sys
import threading
import time
from pathlib import Path

import pytest

from ifs_chatbot import none_gen as ng
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime, SessionError

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import T_SHAPE, cfg, done_session  # noqa: E402

FAKE = Path(__file__).parent / "fixtures" / "fake_gen3d.py"
T_CRISIS = "죽고 싶어요"


class R:
    def __init__(self, code=200, data=None):
        self.status_code, self._d = code, data or {}

    def json(self):
        return self._d


def ollama_cfg(tmp_path, required=True):
    over = {"llm.backend": "ollama", "guard.model_backend": "ollama", "guard.required": required,
            "session.log_dir": str(tmp_path / "logs"), "gen3d.on_none": True, "gen3d.assets_dir": str(tmp_path / "gen3d-out"),
            "gen3d.on_none_python": sys.executable, "gen3d.on_none_script": str(FAKE)}
    return load_config("v4").with_overrides(**over)


class FakeOllama:
    """keep_alive 0이면 내림, 아니면 올림. fail_unload·stuck·fail_reload로 실패를 흉내."""

    def __init__(self, c, fail_unload=False, stuck=False, fail_reload=0):
        self.loaded = {c.llm.model, c.guard.model}
        self.fail_unload, self.stuck, self.fail_reload = fail_unload, stuck, fail_reload
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(dict(json))
        if json.get("keep_alive") == 0:
            if self.fail_unload:
                return R(500)
            if not self.stuck:
                self.loaded.discard(json["model"])
            return R()
        if self.fail_reload > 0:
            self.fail_reload -= 1
            return R(500)
        self.loaded.add(json["model"])
        return R()

    def get(self, url, timeout=None):
        return R(data={"models": [{"name": m} for m in sorted(self.loaded)]})


def svc_with(tmp_path, monkeypatch, fake=None, **kw):
    c = ollama_cfg(tmp_path, **kw)
    fo = fake or FakeOllama(c)
    monkeypatch.setattr(ng.httpx, "post", fo.post)
    monkeypatch.setattr(ng.httpx, "get", fo.get)
    monkeypatch.setenv("FAKE_GEN3D_MODE", "ok")
    monkeypatch.setenv("FAKE_GEN3D_DELAY", "0")
    monkeypatch.setenv("FAKE_GEN3D_PROBE", "miss")
    return ng.NoneGenService(c, tmp_path / "gen3d-out"), fo, c


def job_for(text=T_SHAPE):
    p = ng.shape_prompt(text)
    return ng.NoneGenJob("SYN-CP13", text, p["sourceTextSha256"], p["text"])


# ── 1. 내림 실패 → 만들지 않음 ────────────────────────────────────────────────
@pytest.mark.parametrize("mode,problem", [("fail_unload", "unload_request_failed"), ("stuck", "still_loaded")])
def test_unload_failure_blocks_generation(tmp_path, monkeypatch, mode, problem):
    c = ollama_cfg(tmp_path)
    svc, fo, _ = svc_with(tmp_path, monkeypatch, FakeOllama(c, **{mode: True}))
    res = svc._run(job_for())
    assert res["status"] == ng.BLOCKED and res["blockReason"] == ng.B_UNLOAD == "llm_unload_failed"
    assert res["blockDetail"].startswith(problem) and res["llmUnload"]["ok"] is False
    assert not (tmp_path / "gen3d-out" / res["run"] / "generator.log").exists()      # 생성 프로세스를 띄우지 않음


def test_unload_ok_is_recorded(tmp_path, monkeypatch):
    svc, fo, _ = svc_with(tmp_path, monkeypatch)
    res = svc._run(job_for())
    assert res["status"] == ng.OK and res["llmUnload"]["ok"] is True and res["llmUnload"]["loadedAfter"] == []


# ── 2. 생성 중 면담 거부, 위기 문장은 통과, 예약은 원자적 ─────────────────────────
def test_interview_refused_while_generating(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_GEN3D_MODE", "hang")
    monkeypatch.setenv("FAKE_GEN3D_DELAY", "0")
    rt = Runtime(cfg(tmp_path))
    waiting = rt.new_session("static", "SYN-CP13-WAIT")                 # 생성 전에 만들어 두었지만 시작 안 함
    s = done_session(rt, "SYN-CP13-GEN", T_SHAPE)
    f = s.selection()
    f.start()
    assert f.select("none")["stage"] == "generating"
    job = f._none_job
    with pytest.raises(SessionError, match="생성 중"):
        rt.new_session("static", "SYN-CP13-NEW")
    with pytest.raises(SessionError, match="생성 중"):
        waiting.start()
    assert rt.none_gen.info()["generatingFor"] == "SYN-CP13-GEN"
    with rt.interview_slot(T_CRISIS):                                  # 키워드 위기는 모델 없이 고정 문구 → 막지 않음
        pass
    with pytest.raises(SessionError):
        with rt.interview_slot("둥근 돌 같아요"):
            pass
    f.skip_generation()
    assert job.wait(30) and job.released.wait(30)
    rt.new_session("static", "SYN-CP13-AFTER")                         # 끝나면 다시 받음
    waiting.start()


def test_reservation_checks_interviews_and_inflight_atomically(tmp_path, monkeypatch):
    svc, fo, _ = svc_with(tmp_path, monkeypatch)
    p = ng.shape_prompt(T_SHAPE)
    args = ("SYN-CP13", T_SHAPE, p["sourceTextSha256"], p["text"], lambda r: None)
    assert svc.start(*args, other_interviews=lambda: ["SYN-OTHER"]) == ng.B_INTERVIEW
    with svc.interview_slot():
        assert svc.start(*args, other_interviews=lambda: []) == ng.B_INTERVIEW     # 면담 요청이 들어가 있음
    job = svc.start(*args, other_interviews=lambda: [])
    assert isinstance(job, ng.NoneGenJob)
    with pytest.raises(ng.InterviewBlocked):
        with svc.interview_slot():
            pass
    assert svc.start(*args) == ng.B_BUSY
    assert job.released.wait(60)


# ── 2. 재적재 실패 → 준비 안 됨 → 세션 만들기 거부 → 회복 ────────────────────────
def test_reload_failure_blocks_new_sessions_until_recovered(tmp_path, monkeypatch):
    c = ollama_cfg(tmp_path, required=True)
    fo = FakeOllama(c, fail_reload=4)                                   # 첫 재적재(모델 2개)와 바로 한 재시도가 실패
    svc, _, _ = svc_with(tmp_path, monkeypatch, fo)
    svc.retry_interval_s = 2.0
    p = ng.shape_prompt(T_SHAPE)
    job = svc.start("SYN-CP13", T_SHAPE, p["sourceTextSha256"], p["text"], lambda r: None, other_interviews=[])
    assert job.released.wait(60)
    assert job.result["status"] == ng.OK and job.result["llmReload"]["ok"] is False
    assert svc.models_ready is False
    rt = Runtime(cfg(tmp_path))
    rt.none_gen = svc
    with pytest.raises(SessionError, match="가드 모델이 준비되지"):
        rt.new_session("static", "SYN-CP13-R1")
    assert svc.info()["modelsReady"] is False
    t = time.monotonic()
    while not svc.models_ready and time.monotonic() - t < 20:
        time.sleep(0.1)
    assert svc.models_ready and svc.info()["modelsProblem"] is None
    rt.new_session("static", "SYN-CP13-R2")


def test_reload_failure_does_not_block_when_guard_not_required(tmp_path, monkeypatch):
    svc, fo, _ = svc_with(tmp_path, monkeypatch, required=False)
    with svc.lock:
        svc.models_ready, svc.models_problem = False, "not_loaded:x"
    assert svc.interview_refusal(creating=True) is None


# ── 3. 재적재 중 예약한 다시 만들기는 재적재 뒤에 시작 ──────────────────────────
def test_regeneration_waits_for_previous_reload(tmp_path, monkeypatch):
    svc, fo, _ = svc_with(tmp_path, monkeypatch)
    times = {}
    real_reload, real_run = svc.reload_models, svc._run

    def slow_reload():
        times.setdefault("reload_start", time.monotonic())
        time.sleep(1.0)
        out = real_reload()
        times.setdefault("reload_end", time.monotonic())
        return out

    def run(job):
        times.setdefault(f"run_{job.attempt}", time.monotonic())
        return real_run(job)

    monkeypatch.setattr(svc, "reload_models", slow_reload)
    monkeypatch.setattr(svc, "_run", run)
    p = ng.shape_prompt(T_SHAPE)
    second = {}
    done = threading.Event()

    def on_done_first(res):
        # 첫 결과가 화면에 나오자마자 참여자가 다시 [맞는 게 없어요] — 이때 앞 작업은 재적재 전(reloading)
        second["job"] = svc.start("SYN-CP13", T_SHAPE, p["sourceTextSha256"], p["text"], lambda r: done.set(),
                                  attempt=1, other_interviews=[])

    first = svc.start("SYN-CP13", T_SHAPE, p["sourceTextSha256"], p["text"], on_done_first, other_interviews=[])
    assert isinstance(first, ng.NoneGenJob)
    assert first.released.wait(60) and done.wait(60)
    assert isinstance(second["job"], ng.NoneGenJob)                     # 막히지 않고 예약됨
    assert times["run_1"] >= times["reload_end"]                        # 재적재가 끝난 뒤에 시작
    assert second["job"].released.wait(60)
    assert svc.active is None


# ── 4. 넘어가기는 곧 응답 ────────────────────────────────────────────────────
def test_skip_responds_before_process_is_killed(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_GEN3D_MODE", "hang")
    monkeypatch.setenv("FAKE_GEN3D_DELAY", "0")
    rt = Runtime(cfg(tmp_path))
    s = done_session(rt, "SYN-CP13-SKIP", T_SHAPE)
    f = s.selection()
    f.start()
    f.select("none")
    job = f._none_job
    t = time.monotonic()
    while job.proc is None and time.monotonic() - t < 30:
        time.sleep(0.05)
    real_kill = ng._kill

    def slow_kill(proc):
        time.sleep(3)
        real_kill(proc)

    monkeypatch.setattr(ng, "_kill", slow_kill)
    t = time.monotonic()
    v = f.skip_generation()
    assert time.monotonic() - t < 1.0                                 # taskkill(최대 15초)를 기다리지 않음
    assert v["stage"] == "adjusting" and f.data["generation"]["afterNone"]["status"] == "cancelled"
    assert job.wait(30)
