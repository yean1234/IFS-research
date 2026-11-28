"""G73: [맞는 게 없어요] 뒤 형태 생성(none_gen.py·selection.py·server.py). 생성기는 대역(tests/fixtures/fake_gen3d.py —
같은 인자, 정해진 시간 뒤 가짜 GLB + form-asset.v0 사이드카)으로 바꿔 별도 프로세스 경로를 그대로 시험한다.
모든 대사는 합성이다. 생성 모델·torch를 부르지 않는다."""
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ifs_chatbot import none_gen as ng
from ifs_chatbot.config import Gen3DConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import shared
from ifs_chatbot.server import create_app
from ifs_chatbot.simulate import drive

FAKE = Path(__file__).parent / "fixtures" / "fake_gen3d.py"
V03 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.3.json").read_text(encoding="utf-8")))

T_SHAPE = "엉킨 실타래 같아요. 가슴 앞에 있어요."              # 형태 낱말 '엉킨'·'실타래' → 생성
T_NOSHAPE = "가슴 안쪽이 답답하고 무거운 느낌이에요."          # 형태를 말하지 않음 → no_shape_stated
T_PERSON = "작은 사람이 서 있어요."                           # 사람 → excluded_category


def cfg(tmp_path, preview="image", timeout=60.0, on_none=True, base="v4", regen=1):
    over = {"llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(tmp_path / "logs"),
            "preview.mode": preview, "preview.image_player": "fake" if preview == "image" else "",
            "selection.protocol": "selection_protocol.v0.8.json",
            "gen3d.on_none": on_none, "gen3d.assets_dir": str(tmp_path / "gen3d-out"),
            "gen3d.on_none_python": sys.executable, "gen3d.on_none_script": str(FAKE),
            "gen3d.on_none_timeout_s": timeout, "gen3d.on_none_max_regenerations": regen}
    return load_config(base).with_overrides(**over)


def done_session(rt, sid, text):
    s = rt.new_session("static", sid)
    drive(s, {"id": sid, "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": text}})
    assert s.state == "done"
    return s


def wait_stage(f, not_stage="generating", timeout=60):
    t = time.monotonic()
    while f.stage == not_stage and time.monotonic() - t < timeout:
        time.sleep(0.1)
    assert f.stage != not_stage, f"{timeout}초 안에 {not_stage}가 끝나지 않음"


def valid(data):
    errs = [f"{list(e.path)}: {e.message}" for e in V03.iter_errors(json.loads(json.dumps(data, ensure_ascii=False)))]
    assert not errs, errs[:3]


def sel_json(f):
    return json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))


@pytest.fixture
def fake_env(monkeypatch):
    def set_(mode="ok", delay=0.3):
        monkeypatch.setenv("FAKE_GEN3D_MODE", mode)
        monkeypatch.setenv("FAKE_GEN3D_DELAY", str(delay))
    set_()
    return set_


def start_none(tmp_path, sid, text, **kw):
    rt = Runtime(cfg(tmp_path, **kw))
    s = done_session(rt, sid, text)
    f = s.selection()
    v = f.start()
    assert v["stage"] == "selecting"
    assert sel_json(f)["formatVersion"] == "ifs-selection/0.2"          # none 전에는 0.2 그대로
    return rt, s, f


# ── 설정 ─────────────────────────────────────────────────────────────────────
def test_on_none_only_in_experiment_and_g62_stays_off():
    assert Gen3DConfig().on_none is False and Gen3DConfig().on_none_timeout_s == 180.0
    assert Gen3DConfig().on_none_max_regenerations == 1 and Gen3DConfig().on_none_pipeline == "sdxl-triposg"
    exp = load_config("experiment")
    assert exp.gen3d.on_none is True and exp.gen3d.enabled is False and exp.gen3d.default_form_source == "procedural"
    assert exp.selection.protocol == "selection_protocol.v0.9.json"   # G75: 0.8.0 + 참고 그림 고르기 문구(0.8.0 문구는 그대로 들어 있음)
    for name in ("default", "pilot", "v4", "v4-gen3d", "bridge", "mac8gb"):
        assert load_config(name).gen3d.on_none is False, name


def test_protocol_08_adds_four_draft_phrases_only():
    a = json.loads(shared("protocol", "selection_protocol.v0.7.json").read_text(encoding="utf-8"))
    b = json.loads(shared("protocol", "selection_protocol.v0.8.json").read_text(encoding="utf-8"))
    assert b["protocolVersion"] == "0.8.0"
    new = set(b["phrases"]) - set(a["phrases"])
    assert new == {"none_gen_waiting", "none_gen_skip_button", "none_gen_ready", "none_gen_unavailable"}
    assert all(b["phrases"][k]["status"] == "draft" and "G73" in b["phrases"][k]["source"] for k in new)
    assert all(b["phrases"][k] == a["phrases"][k] for k in a["phrases"])
    assert b["phrases"]["none_gen_waiting"]["text"] == "말씀하신 내용으로 모양을 하나 더 만들고 있어요. 잠시만 기다려 주세요."


# ── 성공: none → 대기 → 생성 후보 → 고름 → 기록·GLB 복사 ────────────────────────
def test_none_generates_candidate_then_choose_records_and_copies_glb(tmp_path, fake_env):
    fake_env("ok", 0.5)
    rt, s, f = start_none(tmp_path, "SYN-G73-OK", T_SHAPE)
    before = list(f.cands["displayOrder"])
    v = f.select("none")
    assert v["stage"] == "generating" and v["afterNone"]["status"] == "running"
    assert sel_json(f)["formatVersion"] == "ifs-selection/0.3" and sel_json(f)["stage"] == "generating"
    with pytest.raises(Exception):
        f.select(before[0])                                           # 대기 중에는 고를 수 없음(409)
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "selecting"
    gen = [c for c in v["candidates"] if c.get("afterNone")]
    assert len(gen) == 1 and v["candidates"][0]["id"] == gen[0]["id"]            # 맨 앞
    assert [c["id"] for c in v["candidates"][1:]] == before                       # 나머지 순서 그대로
    an = f.data["generation"]["afterNone"]
    assert an["status"] == "ok" and an["attempt"] == 0 and an["seed"] == 0
    # 낱말별 원문 근거(정규화한 확정 텍스트 기준 charSpan)
    words = [(t["ko"], t["charSpan"]) for t in an["prompt"]["tokens"] if t["slot"] != "template"]
    assert words == [("엉킨", [0, 2]), ("실타래", [3, 6])]
    assert an["prompt"]["text"].startswith("a single tangled") and an["asset"]["models"][0]["repo"] == "none/fake-gen3d"
    assert an["startedAt"] and an["endedAt"] and an["seconds"] > 0 and an["exitCode"] == 0
    assert an["llmUnload"]["skipped"] == "no_ollama_models"                       # 오프라인 백엔드
    # 입력·산출물은 assets_dir(저장소 밖 관례) 아래 run 폴더
    run_dir = tmp_path / "gen3d-out" / an["run"]
    assert (run_dir / "inputs" / "sentences.json").is_file() and (run_dir / "generator.log").is_file()
    # 고름
    v = f.select(gen[0]["id"])
    assert v["stage"] == "adjusting"
    d = sel_json(f)
    assert d["form"]["asset"]["origin"] == ng.ORIGIN and d["generation"]["outcome"] == "generated_chosen"
    assert d["generation"]["afterNone"]["chosen"] is True and d["selection"]["afterNoneGeneration"] == "ok"
    glb = f.dir / d["form"]["asset"]["glb"]
    assert glb.is_file() and hashlib.sha256(glb.read_bytes()).hexdigest() == d["form"]["asset"]["glbSha256"]
    assert (f.dir / d["form"]["asset"]["sidecar"]).is_file()
    f.finish()
    d = sel_json(f)
    assert d["sources"]["form.type"] == "generated_chosen"                        # 러너 계약 값 그대로
    assert d["sourceDetails"]["form.type"]["origin"] == ng.ORIGIN
    assert d["finalOverrides"] == {}                                              # 크기·색 등은 사전 값 그대로
    valid(d)
    cand_bytes = (f.dir / "candidates.json").read_bytes()
    assert b"generated_after_none" not in cand_bytes                              # 후보 생성기 출력 파일은 바이트 고정
    ev = [e["type"] for e in s.log.data["events"]]
    assert ev.count("selection:none_gen") == 2


def test_none_again_regenerates_with_next_seed_then_none_path(tmp_path, fake_env):
    fake_env("ok", 0.2)
    rt, s, f = start_none(tmp_path, "SYN-G73-REGEN", T_SHAPE)
    f.select("none")
    wait_stage(f)
    first = f.data["generation"]["afterNone"]["candidateId"]
    v = f.select("none")                                              # 만든 후보도 아님 → 다시 만들기(seed + 1)
    assert v["stage"] == "generating"
    wait_stage(f)
    an = f.data["generation"]["afterNone"]
    assert an["attempt"] == 1 and an["seed"] == 1 and an["status"] == "ok" and an["candidateId"] != first
    assert f.data["generation"]["afterNoneEarlier"][0]["candidateId"] == first
    order = f.cands["displayOrder"]
    assert order[0] == an["candidateId"] and order[1] == first
    v = f.select("none")                                              # 상한(1회) → 기존 none 경로
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    d = sel_json(f)
    assert d["generation"]["afterNone"]["chosen"] is False and d["generation"]["afterNoneEarlier"][0]["chosen"] is False
    assert d["generation"]["outcome"] == "none" and d["form"]["asset"] is None
    valid(d)


def test_regeneration_off_means_second_none_is_existing_path(tmp_path, fake_env):
    rt, s, f = start_none(tmp_path, "SYN-G73-NOREGEN", T_SHAPE, regen=0)
    f.select("none")
    wait_stage(f)
    v = f.select("none")
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True and v["selection"]["afterNoneGeneration"] == "ok"


# ── 차단(모델 호출 없음) ──────────────────────────────────────────────────────
@pytest.mark.parametrize("text,reason", [(T_NOSHAPE, "no_shape_stated"), (T_PERSON, "excluded_category")])
def test_blocked_goes_straight_to_none_path_without_process(tmp_path, fake_env, text, reason):
    rt, s, f = start_none(tmp_path, "SYN-G73-BLK", text)
    v = f.select("none")
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    an = f.data["generation"]["afterNone"]
    assert an["status"] == "blocked" and an["blockReason"] in (reason, "form_blocked_G50")
    assert an["run"] is None and not (tmp_path / "gen3d-out").exists()             # 생성기를 띄우지 않음
    assert v["afterNone"]["status"] == "blocked"
    d = sel_json(f)
    assert d["selection"]["afterNoneGeneration"] == "blocked"
    f.finish()
    valid(sel_json(f))


def test_text_summary_preview_blocks(tmp_path, fake_env):
    rt, s, f = start_none(tmp_path, "SYN-G73-NOPREV", T_SHAPE, preview="none")
    v = f.select("none")
    assert v["stage"] == "adjusting" and f.data["generation"]["afterNone"]["blockReason"] == "no_shape_preview"


def test_other_session_in_interview_blocks(tmp_path, fake_env):
    rt, s, f = start_none(tmp_path, "SYN-G73-BUSYLLM", T_SHAPE)
    other = rt.new_session("static", "SYN-G73-OTHER")
    other.start()
    assert other.state in ng.INTERVIEW_STATES
    v = f.select("none")
    an = f.data["generation"]["afterNone"]
    assert v["stage"] == "adjusting" and an["blockReason"] == "interview_active" and "SYN-G73-OTHER" in an["blockDetail"]


# ── 실패·시간 초과·관문 차단·기다리지 않음 ──────────────────────────────────────
@pytest.mark.parametrize("mode,status,field,expect", [
    ("failed", "failed", "error", "fake failure"),
    ("crash", "failed", "error", "exit 3"),
    ("mismatch", "failed", "error", "prompt_mismatch"),
    ("gate", "blocked", "blockReason", "person_like"),
])
def test_generator_failure_goes_to_none_path(tmp_path, fake_env, mode, status, field, expect):
    fake_env(mode, 0.1)
    rt, s, f = start_none(tmp_path, f"SYN-G73-{mode.upper()}", T_SHAPE)
    f.select("none")
    wait_stage(f)
    v = f.view()
    an = f.data["generation"]["afterNone"]
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    assert an["status"] == status and expect in (an[field] or "")
    assert an["candidateId"] is None and an["chosen"] is None
    assert not any(c.get("afterNone") for c in v["candidates"])
    valid(sel_json(f))


def test_timeout_kills_generator(tmp_path, fake_env):
    fake_env("hang")
    rt, s, f = start_none(tmp_path, "SYN-G73-TIMEOUT", T_SHAPE, timeout=4.0)
    f.select("none")
    job = f._none_job
    wait_stage(f, timeout=40)
    an = f.data["generation"]["afterNone"]
    assert f.stage == "adjusting" and an["status"] == "timeout" and an["seconds"] >= 4.0
    assert job.proc is not None and job.proc.poll() is not None                  # 프로세스가 꺼짐
    valid(sel_json(f))


def test_participant_skips_wait(tmp_path, fake_env):
    fake_env("hang")
    rt, s, f = start_none(tmp_path, "SYN-G73-SKIP", T_SHAPE)
    f.select("none")
    job = f._none_job
    v = f.skip_generation()
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    an = f.data["generation"]["afterNone"]
    assert an["status"] == "cancelled" and an["participantSkippedWait"] is True
    assert job.wait(30)
    assert job.proc is None or job.proc.poll() is not None
    time.sleep(0.2)
    assert f.stage == "adjusting" and f.data["generation"]["afterNone"]["status"] == "cancelled"   # 늦게 온 결과가 단계를 바꾸지 않음
    with pytest.raises(Exception):
        f.skip_generation()
    valid(sel_json(f))


def test_late_success_after_skip_does_not_add_candidate(tmp_path, fake_env):
    fake_env("ok", 1.5)
    rt, s, f = start_none(tmp_path, "SYN-G73-LATE", T_SHAPE)
    f.select("none")
    job = f._none_job
    f.skip_generation()
    assert job.wait(30)
    assert f.stage == "adjusting" and not any(c.get("origin") == ng.ORIGIN for c in f.cands["candidates"])
    assert f.data["form"]["asset"] is None


# ── 다른 설정·끔: 기존 동작 그대로 ──────────────────────────────────────────────
def test_off_means_none_goes_straight_to_adjusting_with_02(tmp_path, fake_env):
    rt = Runtime(cfg(tmp_path, on_none=False))
    assert rt.none_gen is None and "gen3dOnNone" not in rt.info()
    s = done_session(rt, "SYN-G73-OFF", T_SHAPE)
    f = s.selection()
    f.start()
    v = f.select("none")
    assert v["stage"] == "adjusting" and "afterNone" not in v
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.2" and "generation" not in d and "afterNoneGeneration" not in d["selection"]


# ── 서버 API ─────────────────────────────────────────────────────────────────
def test_api_none_wait_poll_choose_and_glb(tmp_path, fake_env):
    fake_env("ok", 0.5)
    rt = Runtime(cfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G73-API", T_SHAPE)
    assert c.post(f"/api/sessions/{s.id}/candidates").json()["stage"] == "selecting"
    r = c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": "none"})
    assert r.status_code == 200 and r.json()["stage"] == "generating"
    assert c.get("/api/selection/config").json()["phrases"]["none_gen_waiting"].startswith("말씀하신 내용으로")
    t = time.monotonic()
    while c.get(f"/api/sessions/{s.id}/selection").json()["stage"] == "generating" and time.monotonic() - t < 60:
        time.sleep(0.2)
    v = c.get(f"/api/sessions/{s.id}/selection").json()
    first = v["candidates"][0]
    assert v["stage"] == "selecting" and first["afterNone"] is True and first["generated"] is True
    g = c.get(first["asset"]["glbUrl"])
    assert g.status_code == 200 and hashlib.sha256(g.content).hexdigest() == first["asset"]["glbSha256"]
    assert c.post(f"/api/sessions/{s.id}/selection/none-gen/skip").status_code == 409    # 대기 중이 아님
    png = c.get(f"/api/sessions/{s.id}/preview/{first['id']}.png")
    assert png.status_code == 200                                                          # 가짜 렌더러가 GLB로 그림
    r = c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": first["id"]})
    assert r.json()["formAsset"]["origin"] == ng.ORIGIN
    assert "gen3dOnNone" in c.get("/api/health").json()


def test_api_skip_endpoint(tmp_path, fake_env):
    fake_env("hang")
    rt = Runtime(cfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G73-APISKIP", T_SHAPE)
    c.post(f"/api/sessions/{s.id}/candidates")
    assert c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": "none"}).json()["stage"] == "generating"
    r = c.post(f"/api/sessions/{s.id}/selection/none-gen/skip")
    assert r.status_code == 200 and r.json()["stage"] == "adjusting"
    assert r.json()["afterNone"]["participantSkippedWait"] is True
    s.selection_flow._none_job.wait(30)


def test_withdraw_cancels_generation(tmp_path, fake_env):
    fake_env("hang")
    rt, s, f = start_none(tmp_path, "SYN-G73-WD", T_SHAPE)
    f.select("none")
    job = f._none_job
    s.withdraw()
    assert job.wait(30) and job.cancel_reason == "withdrawn"


# ── Ollama 내리기·올리기(모의 HTTP) ───────────────────────────────────────────
def test_unload_and_reload_models_with_ollama_backend(tmp_path, monkeypatch):
    c = cfg(tmp_path).with_overrides(**{"llm.backend": "ollama", "guard.model_backend": "ollama"})
    svc = ng.NoneGenService(c, tmp_path / "out")
    calls, loaded = [], {c.llm.model, c.guard.model}

    class R:
        def __init__(self, code=200, data=None):
            self.status_code, self._d = code, data or {}

        def json(self):
            return self._d

    def post(url, json=None, timeout=None):
        calls.append((url, dict(json)))
        if json.get("keep_alive") == 0:
            loaded.discard(json["model"])
        else:
            loaded.add(json["model"])
        return R()

    def get(url, timeout=None):
        return R(data={"models": [{"name": m} for m in sorted(loaded)]})

    monkeypatch.setattr(ng.httpx, "post", post)
    monkeypatch.setattr(ng.httpx, "get", get)
    rec = svc.unload_models()
    assert [x["role"] for x in rec["models"]] == ["interview", "guard"] and all(x["ok"] for x in rec["models"])
    assert rec["loadedAfter"] == [] and all(u.endswith("/api/generate") and b["keep_alive"] == 0 for u, b in calls)
    svc.reload_models()
    assert loaded == {c.llm.model, c.guard.model}
    assert svc.setting()["unloadModels"] == [c.llm.model, c.guard.model]


# ── 웹 화면 연결(문자열 점검) ─────────────────────────────────────────────────
def test_web_wires_waiting_screen_skip_and_notice():
    from ifs_chatbot.paths import WEB_DIR
    js = (WEB_DIR / "stage.js").read_text(encoding="utf-8")
    for needle in ('v.stage === "generating"', "none_gen_waiting", "none_gen_skip_button", "/selection/none-gen/skip",
                   "none_gen_ready", "none_gen_unavailable", "is-after-none"):
        assert needle in js, needle
