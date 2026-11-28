"""G75: [맞는 게 없어요] 뒤 생성에서 3D 모델이 참고할 그림을 참여자가 먼저 고른다([gen3d] on_none_image_pick).

흐름: 형태 낱말 규칙 프롬프트(+ 무채색 화풍 고정 문구) → 그림 3장(seed 기준 + 3r + 0·1·2) → 그림 관문 → 고르기 화면(picking)
→ 고른 그림으로만 형태 → 후보 맨 앞(G73과 같음). [이 중에는 없어요]·만든 후보에 [맞는 게 없어요] → 다음 회차(on_none_image_rounds까지).
생성기는 대역(tests/fixtures/fake_gen3d.py — 실제 생성기와 같은 인자·같은 자리의 산출물), Ollama는 모의 HTTP. 모든 대사는 합성이다."""
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
from ifs_chatbot.controller import Runtime, SessionError
from ifs_chatbot.paths import shared
from ifs_chatbot.server import create_app

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_cp13 import FakeOllama  # noqa: E402
from test_g73_none_gen import T_NOSHAPE, T_SHAPE, cfg, done_session, sel_json, wait_stage  # noqa: E402

V03 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.3.json").read_text(encoding="utf-8")))
V04 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.4.json").read_text(encoding="utf-8")))
T_CRISIS = "죽고 싶어요"
# G73 기록(afterNone)의 키 — 플래그를 끄면 이 키만 있어야 한다(imagePick 등 G75 키 없음)
G73_KEYS = {"version", "origin", "setting", "noneAt", "shownOrderBefore", "status", "blockReason", "blockDetail", "prompt", "run",
            "startedAt", "endedAt", "seconds", "exitCode", "error", "llmUnload", "timing", "asset", "candidateId",
            "displayPosition", "participantSkippedWait", "chosen", "attempt", "seed", "cacheProbe"}


def pcfg(tmp_path, rounds=2, image_timeout=60.0, mesh_timeout=60.0, **kw):
    return cfg(tmp_path, **kw).with_overrides(**{
        "gen3d.on_none_image_pick": True, "gen3d.on_none_image_rounds": rounds,
        "gen3d.on_none_image_timeout_s": image_timeout, "gen3d.on_none_mesh_timeout_s": mesh_timeout,
        "selection.protocol": "selection_protocol.v0.9.json"})


@pytest.fixture
def fake(monkeypatch):
    def set_(mesh="ok", image="ok", delay=0.2, gate="", tamper=""):
        monkeypatch.setenv("FAKE_GEN3D_MODE", mesh)
        monkeypatch.setenv("FAKE_GEN3D_IMAGE_MODE", image)
        monkeypatch.setenv("FAKE_GEN3D_DELAY", str(delay))
        monkeypatch.setenv("FAKE_GEN3D_IMAGE_GATE", gate)
        monkeypatch.setenv("FAKE_GEN3D_IMAGE_TAMPER", tamper)
    set_()
    return set_


def start(tmp_path, sid, text=T_SHAPE, **kw):
    rt = Runtime(pcfg(tmp_path, **kw))
    s = done_session(rt, sid, text)
    f = s.selection()
    assert f.start()["stage"] == "selecting"
    return rt, s, f


def valid4(f):
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.4"
    errs = [f"{list(e.path)}: {e.message}" for e in V04.iter_errors(d)]
    assert not errs, errs[:3]
    return d


def calls(tmp_path):
    p = tmp_path / "gen3d-out" / "fake-calls.log"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def to_picking(f):
    v = f.select("none")
    assert v["stage"] == "generating" and v["afterNone"]["phase"] == "image"
    wait_stage(f)
    assert f.stage == "picking", f.data["generation"]["afterNone"]
    return f.view()


# ── 설정·문구·프롬프트 ───────────────────────────────────────────────────────────
def test_flag_only_in_experiment_and_defaults():
    g = Gen3DConfig()
    assert g.on_none_image_pick is False and g.on_none_image_rounds == 2
    assert g.on_none_image_timeout_s == 180.0 and g.on_none_mesh_timeout_s == 180.0
    exp = load_config("experiment")
    assert exp.gen3d.on_none_image_pick is True and exp.gen3d.on_none is True and exp.gen3d.on_none_image_rounds == 2
    # G77: 0.10.0(0.9.1 문구 그대로 + llm_fill_note 하나). G79: 0.11.0(+ 색상 고리 문구 3개). G82·G83: 0.13.0(+ 근거 인용 줄)
    assert exp.selection.protocol == "selection_protocol.v0.13.json"
    for name in ("default", "pilot", "v4", "v4-gen3d", "bridge", "mac8gb"):
        c = load_config(name)
        assert c.gen3d.on_none_image_pick is False, name
        assert c.selection.protocol not in ("selection_protocol.v0.9.json", "selection_protocol.v0.10.json",
                                         "selection_protocol.v0.11.json", "selection_protocol.v0.12.json",
                                         "selection_protocol.v0.13.json"), name


def test_protocol_09_adds_four_draft_phrases_only():
    a = json.loads(shared("protocol", "selection_protocol.v0.8.json").read_text(encoding="utf-8"))
    b = json.loads(shared("protocol", "selection_protocol.v0.9.json").read_text(encoding="utf-8"))
    assert b["protocolVersion"] == "0.9.1" and [c["version"] for c in b["changes"][:2]] == ["0.9.1", "0.9.0"]   # CP14: 안내 문구 고침
    new = set(b["phrases"]) - set(a["phrases"])
    assert new == {"image_pick_waiting", "image_pick_intro", "image_pick_none", "image_pick_skip_button"}
    assert all(b["phrases"][k]["status"] == "draft" and "G75" in b["phrases"][k]["source"] for k in new)
    assert all(b["phrases"][k] == a["phrases"][k] for k in a["phrases"])            # 기존 문구는 그대로
    assert b["phrases"]["image_pick_intro"]["text"] == ("말씀하신 모양으로 그림을 그려 봤어요. 떠올리신 모양과 가장 가까운 그림을 "
                                                        "골라 주세요. 색은 보지 말고 모양만 봐 주세요.")
    assert b["phrases"]["image_pick_none"]["text"] == "이 중에는 없어요"
    for k in new:                                                                     # 치료·진단 표현 없음(원칙 8)
        assert not any(w in b["phrases"][k]["text"] for w in ("치료", "진단", "내담자", "증상"))


def test_image_pick_prompt_adds_fixed_gray_style_only():
    p = ng.shape_prompt(T_SHAPE)
    q = ng.image_pick_prompt(p)
    content = [(t["en"], t["ko"], t["charSpan"]) for t in p["tokens"] if t["slot"] != "template"]
    assert [(t["en"], t["ko"], t["charSpan"]) for t in q["tokens"] if t["slot"] != "template"] == content   # 말한 낱말 그대로
    assert q["text"].startswith(p["text"] + ", ") and "monochrome gray clay" in q["text"]
    assert q["negativeText"].startswith(p["negativeText"]) and "colorful" in q["negativeText"]
    assert q["builderVersion"] == "gen3d-shape-prompt/0.5.0+imagepick" and q["imageStyle"] == "g75-shape-only-gray"
    assert ng.image_pick_prompt(p) == q                                              # 결정적
    assert p == ng.shape_prompt(T_SHAPE) and "imageStyle" not in p                   # 원래 규칙(G62·G73)은 그대로
    b = ng.image_pick_prompt(ng.shape_prompt(T_NOSHAPE))
    assert b["status"] == "blocked" and b["text"] == ""                              # 막힌 것은 막힌 그대로


# ── 플래그 끔: G73 그대로 ──────────────────────────────────────────────────────
def test_flag_off_is_g73_unchanged(tmp_path, fake):
    rt = Runtime(cfg(tmp_path))
    assert rt.none_gen.image_pick is False and "imagePick" not in rt.none_gen.setting()
    s = done_session(rt, "SYN-G75-OFF", T_SHAPE)
    f = s.selection()
    f.start()
    v = f.select("none")
    assert v["stage"] == "generating" and "phase" not in v["afterNone"]
    wait_stage(f)
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.3" and d["stage"] == "selecting"
    an = d["generation"]["afterNone"]
    assert set(an) == G73_KEYS and "imagePickExposed" not in d["generation"]
    assert an["prompt"]["builderVersion"] == "gen3d-shape-prompt/0.5.0+mapper-v2" and "imageStyle" not in an["prompt"]
    assert not any(c["imagePick"] or c["fromImage"] for c in calls(tmp_path))     # 생성기도 예전 인자만
    assert "imagePick" not in f.view()
    assert not [e for e in V03.iter_errors(d)]


# ── 성공: 그림 3장 → 고름 → 고른 그림으로만 형태 → 후보 맨 앞 → 고름 ──────────────────────
def test_three_images_pick_then_mesh_candidate_and_records(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-OK")
    before = list(f.cands["displayOrder"])
    v = to_picking(f)
    assert [im["position"] for im in v["imagePick"]["images"]] == [0, 1, 2]
    assert v["afterNone"]["phase"] == "pick" and v["afterNone"]["round"] == 0 and v["afterNone"]["rounds"] == 2
    d = valid4(f)
    ip = d["generation"]["afterNone"]["imagePick"]
    assert ip["seeds"] == [0, 1, 2] and ip["shownOrder"] == [0, 1, 2] and ip["shownAt"] and ip["status"] == "shown"
    assert all(im["shown"] and im["gate"]["passed"] and len(im["sha256"]) == 64 for im in ip["images"])
    assert ip["promptText"].endswith("entire object in view") and ip["builderVersion"].endswith("+imagepick+mapper-v2")
    assert d["generation"]["imagePickExposed"] is True and d["stage"] == "picking"
    assert d["generation"]["afterNone"]["seed"] is None                              # 고르기 전
    c1 = calls(tmp_path)
    assert len(c1) == 1 and c1[0]["imagePick"] and c1[0]["seeds"] == "0,1,2"
    with pytest.raises(Exception):
        f.select(before[0])                                                           # 고르기 화면에서는 후보를 고를 수 없음
    # 고름(자리 1 = seed 1)
    v = f.pick_image("1")
    assert v["stage"] == "generating" and v["afterNone"]["phase"] == "mesh"
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "selecting" and v["candidates"][0].get("afterNone") is True
    assert [c["id"] for c in v["candidates"][1:]] == before
    c2 = calls(tmp_path)[-1]
    assert c2["fromImage"] == "after-none-s1.png" and c2["seed"] == 1 and c2["imageSha256"] == ip["images"][1]["sha256"]
    d = valid4(f)
    an = d["generation"]["afterNone"]
    assert an["status"] == "ok" and an["seed"] == 1 and an["asset"]["seed"] == 1
    assert an["imagePick"]["outcome"] == "picked" and an["imagePick"]["pickedPosition"] == 1
    assert an["imagePick"]["pickedSeed"] == 1 and an["imagePick"]["pickedImageSha256"] == ip["images"][1]["sha256"]
    assert an["imagePick"]["decidedAt"] and an["run"].endswith("-r0-mesh") and an["imagePick"]["run"].endswith("-r0-img")
    v = f.select(v["candidates"][0]["id"])
    assert v["stage"] == "adjusting" and v["formAsset"]["origin"] == ng.ORIGIN
    f.finish()
    d = valid4(f)
    assert d["sources"]["form.type"] == "generated_chosen" and d["selection"]["afterNoneGeneration"] == "ok"
    assert d["generation"]["afterNone"]["chosen"] is True
    ev = [(e["type"], e.get("payload", e).get("status")) for e in s.log.data["events"]]
    assert ("selection:image_pick", "shown") in ev and ("selection:image_pick", "picked") in ev


def test_gated_image_hidden_and_order_kept(tmp_path, fake):
    fake(gate="1")
    rt, s, f = start(tmp_path, "SYN-G75-GATE")
    v = to_picking(f)
    assert len(v["imagePick"]["images"]) == 2
    ip = f.data["generation"]["afterNone"]["imagePick"]
    assert ip["shownOrder"] == [0, 2]
    hid = ip["images"][1]
    assert hid["seed"] == 1 and hid["shown"] is False and hid["problem"] == "gate_not_passed" and hid["position"] is None
    assert f.image_png(0, 2) is None                                                  # 보이지 않은 자리(CP14-1: 서버 404)
    v = f.pick_image("1")                                                             # 자리 1 = seed 2
    wait_stage(f)
    assert f.data["generation"]["afterNone"]["seed"] == 2 and calls(tmp_path)[-1]["fromImage"] == "after-none-s2.png"
    valid4(f)


def test_tampered_image_is_not_shown(tmp_path, fake):
    fake(tamper="0")
    rt, s, f = start(tmp_path, "SYN-G75-TAMPER")
    to_picking(f)
    ip = f.data["generation"]["afterNone"]["imagePick"]
    assert ip["shownOrder"] == [1, 2] and ip["images"][0]["problem"] == "sha256_mismatch"


def test_all_gated_goes_to_none_path(tmp_path, fake):
    fake(gate="all")
    rt, s, f = start(tmp_path, "SYN-G75-ALLGATE")
    f.select("none")
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    d = valid4(f)
    an = d["generation"]["afterNone"]
    assert an["status"] == "blocked" and an["blockReason"] == ng.B_ALL_IMAGES_GATED == "all_images_gated"
    assert an["imagePick"]["outcome"] == "blocked" and d["generation"]["imagePickExposed"] is False
    assert not any(c["fromImage"] for c in calls(tmp_path))                          # 형태 단계는 부르지 않음


def test_blocked_prompt_never_starts_generator(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-NOSHAPE", T_NOSHAPE)
    v = f.select("none")
    assert v["stage"] == "adjusting"
    d = valid4(f)
    an = d["generation"]["afterNone"]
    assert an["status"] == "blocked" and an["blockReason"] == "no_shape_stated" and an["imagePick"]["status"] == "blocked"
    assert calls(tmp_path) == [] and d["selection"]["afterNoneGeneration"] == "blocked"


@pytest.mark.parametrize("mode,status", [("failed", "failed"), ("crash", "failed"), ("mismatch", "failed")])
def test_image_generator_failure_goes_to_none_path(tmp_path, fake, mode, status):
    fake(image=mode)
    rt, s, f = start(tmp_path, f"SYN-G75-IMG{mode.upper()}")
    f.select("none")
    wait_stage(f)
    assert f.stage == "adjusting"
    an = valid4(f)["generation"]["afterNone"]
    assert an["status"] == status and an["imagePick"]["outcome"] == status
    if mode == "mismatch":
        assert "prompt_mismatch" in an["error"]


# ── [이 중에는 없어요] → 2회차 → none 경로 ──────────────────────────────────────────
def test_none_on_images_second_round_then_declined(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-DECL")
    to_picking(f)
    v = f.pick_image("none")
    assert v["stage"] == "generating" and v["afterNone"]["round"] == 1
    wait_stage(f)
    assert f.stage == "picking"
    ip = f.data["generation"]["afterNone"]["imagePick"]
    assert ip["round"] == 1 and ip["seeds"] == [3, 4, 5] and ip["shownOrder"] == [3, 4, 5]
    early = f.data["generation"]["afterNoneEarlier"][0]
    assert early["imagePick"]["outcome"] == "none" and early["chosen"] is None and early["attempt"] == 0
    v = f.pick_image("none")                                                          # 상한(2회차) → 기존 none 경로
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    d = valid4(f)
    assert d["generation"]["afterNone"]["status"] == "declined" and d["selection"]["afterNoneGeneration"] == "declined"
    assert d["generation"]["afterNone"]["imagePick"]["outcome"] == "none"
    f.finish()
    valid4(f)


def test_none_on_mesh_candidate_uses_next_image_round_not_regeneration(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-MESHNONE", regen=1)
    to_picking(f)
    f.pick_image("0")
    wait_stage(f)
    first = f.data["generation"]["afterNone"]["candidateId"]
    v = f.select("none")                                                              # 만든 후보도 아님 → 다음 그림 회차
    assert v["stage"] == "generating" and v["afterNone"]["phase"] == "image" and v["afterNone"]["round"] == 1
    wait_stage(f)
    assert f.stage == "picking" and f.data["generation"]["afterNoneEarlier"][0]["chosen"] is False
    f.pick_image("2")                                                                 # seed 5
    wait_stage(f)
    an = f.data["generation"]["afterNone"]
    assert an["status"] == "ok" and an["seed"] == 5 and an["candidateId"] != first
    assert f.cands["displayOrder"][:2] == [an["candidateId"], first]
    v = f.select("none")                                                              # 회차 끝 → 기존 none 경로(다시 만들기 없음)
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    assert sum(1 for c in calls(tmp_path) if c["imagePick"]) == 2 and sum(1 for c in calls(tmp_path) if c["fromImage"]) == 2
    valid4(f)


# ── 넘어가기·시간 초과 ──────────────────────────────────────────────────────────
def test_skip_on_picking_screen(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-SKIPPICK")
    to_picking(f)
    v = f.skip_generation()
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    d = valid4(f)
    an = d["generation"]["afterNone"]
    assert an["status"] == "cancelled" and an["participantSkippedPick"] is True and an["imagePick"]["outcome"] == "skipped"
    assert an["participantSkippedWait"] is False and d["generation"]["imagePickExposed"] is True


def test_skip_during_image_wait_kills_generator(tmp_path, fake):
    fake(image="hang")
    rt, s, f = start(tmp_path, "SYN-G75-SKIPWAIT")
    f.select("none")
    job = f._none_job
    v = f.skip_generation()
    assert v["stage"] == "adjusting"
    assert job.wait(30)
    an = f.data["generation"]["afterNone"]
    assert an["status"] == "cancelled" and an["participantSkippedWait"] is True
    assert an["imagePick"]["outcome"] == "cancelled" and an["imagePick"]["generatorStatus"] == "cancelled"
    assert job.proc is None or job.proc.poll() is not None
    valid4(f)


def test_image_timeout(tmp_path, fake):
    fake(image="hang")
    rt, s, f = start(tmp_path, "SYN-G75-IMGTO", image_timeout=3.0)
    f.select("none")
    wait_stage(f, timeout=40)
    an = f.data["generation"]["afterNone"]
    assert f.stage == "adjusting" and an["status"] == "timeout" and an["imagePick"]["seconds"] >= 3.0
    valid4(f)


def test_mesh_timeout_and_pick_time_not_counted(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-MESHTO", image_timeout=4.0, mesh_timeout=3.0)
    to_picking(f)
    time.sleep(4.5)                                                                    # 고르는 시간은 어느 한도에도 넣지 않는다
    fake(mesh="hang")
    f.pick_image("0")
    wait_stage(f, timeout=40)
    an = f.data["generation"]["afterNone"]
    assert f.stage == "adjusting" and an["status"] == "timeout" and an["imagePick"]["outcome"] == "picked"
    assert 3.0 <= an["seconds"] < 30
    valid4(f)


def test_pick_time_beyond_limits_still_makes_mesh(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-SLOWPICK", image_timeout=4.0, mesh_timeout=4.0)
    to_picking(f)
    time.sleep(4.5)
    f.pick_image("2")
    wait_stage(f)
    assert f.stage == "selecting" and f.data["generation"]["afterNone"]["status"] == "ok"


def test_changed_image_file_after_showing_blocks_mesh(tmp_path, fake):
    rt, s, f = start(tmp_path, "SYN-G75-CHANGED")
    to_picking(f)
    path, _ = f._pick_paths[0]
    Path(path).write_bytes(b"not the same")
    with pytest.raises(Exception):
        f.image_png(0, 0)
    f.pick_image("0")
    wait_stage(f)
    an = f.data["generation"]["afterNone"]
    assert f.stage == "adjusting" and an["status"] == "blocked" and an["blockReason"] == ng.B_IMAGE_MISSING
    assert not any(c["fromImage"] for c in calls(tmp_path))


# ── 상호 배제(CP13) 유지 ──────────────────────────────────────────────────────
def test_interview_blocked_during_phases_but_not_while_picking(tmp_path, fake):
    fake(delay=1.5)
    rt, s, f = start(tmp_path, "SYN-G75-MUTEX")
    f.select("none")
    with pytest.raises(SessionError, match="생성 중"):
        rt.new_session("static", "SYN-G75-NEW1")
    with rt.interview_slot(T_CRISIS):                                                 # 키워드 위기 문장은 막지 않음
        pass
    wait_stage(f)
    assert f.stage == "picking"
    f._none_job.released.wait(30)
    assert rt.none_gen.interview_refusal() is None                                     # 고르는 동안은 면담 모델이 올라가 있음
    other = rt.new_session("static", "SYN-G75-OTHER")                                  # 다른 세션이 면담을 시작하면
    other.start()
    f.pick_image("0")                                                                  # 형태 단계는 만들지 않음(interview_active)
    an = f.data["generation"]["afterNone"]
    assert f.stage == "adjusting" and an["status"] == "blocked" and an["blockReason"] == ng.B_INTERVIEW
    assert "SYN-G75-OTHER" in an["blockDetail"]
    valid4(f)


def test_models_unloaded_and_reloaded_around_each_phase(tmp_path, fake, monkeypatch):
    c = pcfg(tmp_path).with_overrides(**{"llm.backend": "ollama", "guard.model_backend": "ollama", "guard.required": False})
    fo = FakeOllama(c)
    monkeypatch.setattr(ng.httpx, "post", fo.post)
    monkeypatch.setattr(ng.httpx, "get", fo.get)
    rt = Runtime(c.with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none"}))
    rt.none_gen = ng.NoneGenService(c, tmp_path / "gen3d-out")
    s = done_session(rt, "SYN-G75-OLLAMA", T_SHAPE)
    f = s.selection()
    f.start()
    to_picking(f)
    assert f._none_job.released.wait(30)
    assert fo.loaded == {c.llm.model, c.guard.model}                                   # 고르는 동안 다시 올라가 있음
    f.pick_image("0")
    wait_stage(f)
    assert f._none_job.released.wait(30)
    alive = [x["keep_alive"] == 0 for x in fo.calls]
    assert alive == [True, True, False, False, True, True, False, False]               # 내림·올림 × 그림 단계·형태 단계
    an = f.data["generation"]["afterNone"]
    assert an["imagePick"]["llmUnload"]["ok"] is True and an["llmUnload"]["ok"] is True


# ── 서버 API·화면 ─────────────────────────────────────────────────────────────
def test_api_pick_flow(tmp_path, fake):
    rt = Runtime(pcfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G75-API", T_SHAPE)
    c.post(f"/api/sessions/{s.id}/candidates")
    assert c.post(f"/api/sessions/{s.id}/selection/image-pick", json={"choice": "0"}).status_code == 409   # 고르기 전
    r = c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": "none"})
    assert r.json()["stage"] == "generating" and r.json()["afterNone"]["phase"] == "image"
    t = time.monotonic()
    while c.get(f"/api/sessions/{s.id}/selection").json()["stage"] == "generating" and time.monotonic() - t < 60:
        time.sleep(0.1)
    v = c.get(f"/api/sessions/{s.id}/selection").json()
    assert v["stage"] == "picking" and len(v["imagePick"]["images"]) == 3
    png = c.get(v["imagePick"]["images"][0]["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png" and png.content[:4] == b"\x89PNG"
    ip = s.selection_flow.data["generation"]["afterNone"]["imagePick"]
    assert hashlib.sha256(png.content).hexdigest() == ip["images"][0]["sha256"]
    assert c.get(f"/api/sessions/{s.id}/selection/image-pick/0/7.png").status_code == 404
    assert c.post(f"/api/sessions/{s.id}/selection/image-pick", json={"choice": "9"}).status_code == 422
    cfgv = c.get("/api/selection/config").json()["phrases"]
    assert cfgv["image_pick_none"] == "이 중에는 없어요" and cfgv["image_pick_skip_button"] == "넘어갈게요"
    r = c.post(f"/api/sessions/{s.id}/selection/image-pick", json={"choice": "0"})
    assert r.status_code == 200 and r.json()["stage"] == "generating" and r.json()["afterNone"]["phase"] == "mesh"
    s.selection_flow._none_job.wait(30)
    wait_stage(s.selection_flow)
    assert c.get(f"/api/sessions/{s.id}/selection").json()["stage"] == "selecting"


def test_api_skip_on_picking(tmp_path, fake):
    rt = Runtime(pcfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G75-APISKIP", T_SHAPE)
    c.post(f"/api/sessions/{s.id}/candidates")
    c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": "none"})
    wait_stage(s.selection_flow)
    r = c.post(f"/api/sessions/{s.id}/selection/none-gen/skip")
    assert r.status_code == 200 and r.json()["stage"] == "adjusting"


def test_web_wires_picking_screen():
    from ifs_chatbot.paths import WEB_DIR
    js = (WEB_DIR / "stage.js").read_text(encoding="utf-8")
    for needle in ('v.stage === "picking"', "image_pick_intro", "image_pick_none", "image_pick_skip_button",
                   "image_pick_waiting", "/selection/image-pick", "choose_button", "/selection/none-gen/skip"):
        assert needle in js, needle
    assert '"picking"' in (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert ".pick-grid" in (WEB_DIR / "style.css").read_text(encoding="utf-8")


# ── CP14 ────────────────────────────────────────────────────────────────────
def test_cp14_1_image_url_only_while_picking_current_round_shown(tmp_path, fake):
    fake(gate="1")
    rt = Runtime(pcfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G75-CP14URL", T_SHAPE)
    url = f"/api/sessions/{s.id}/selection/image-pick"
    assert c.get(f"{url}/0/0.png").status_code == 404                                # 후보 단계 전
    c.post(f"/api/sessions/{s.id}/candidates")
    assert c.get(f"{url}/0/0.png").status_code == 404                                # 고르기 화면 전
    c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": "none"})
    f = s.selection_flow
    wait_stage(f)
    assert f.stage == "picking"
    assert c.get(f"{url}/0/0.png").status_code == 200 and c.get(f"{url}/0/1.png").status_code == 200
    assert c.get(f"{url}/0/2.png").status_code == 404                                # 숨긴 그림(관문)의 자리
    assert c.get(f"{url}/1/0.png").status_code == 404                                # 다른 회차
    assert c.get(f"/api/sessions/SYN-NO-SUCH/selection/image-pick/0/0.png").status_code == 404   # 없는 세션
    c.post(url, json={"choice": "none"})                                              # 2회차로
    wait_stage(f)
    assert f.stage == "picking"
    assert c.get(f"{url}/0/0.png").status_code == 404 and c.get(f"{url}/1/0.png").status_code == 200   # 앞 회차는 닫힘
    c.post(url, json={"choice": "0"})                                                 # 고른 뒤
    assert c.get(f"{url}/1/0.png").status_code == 404
    f._none_job.wait(30)
    wait_stage(f)
    assert c.get(f"{url}/1/0.png").status_code == 404


def test_cp14_2_invalid_image_paths_not_recorded(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_GEN3D_IMAGE_BADPATH", "0:abs,1:dotdot")
    rt, s, f = start(tmp_path, "SYN-G75-CP14PATH")
    to_picking(f)
    ip = f.data["generation"]["afterNone"]["imagePick"]
    assert ip["shownOrder"] == [2]
    for im in ip["images"][:2]:
        assert im["problem"] == "file_path_invalid" and im["file"] is None and im["shown"] is False
    run_dir = tmp_path / "gen3d-out" / ip["run"]
    abs_str = str((run_dir / "images" / "after-none-s0.png").resolve())
    f.pick_image("0")
    wait_stage(f)
    valid4(f)
    texts = [(f.dir / "selection.json").read_text(encoding="utf-8"), json.dumps(s.log.data, ensure_ascii=False)]
    for t in texts:
        for needle in (abs_str, abs_str.replace("\\", "\\\\"), "FAKE-SECRET-DIR", str(run_dir.resolve() / "images")):
            assert needle not in t, needle


def test_schema_04_reads_and_03_records_still_valid():
    s4 = json.loads(shared("schemas", "selection.v0.4.json").read_text(encoding="utf-8"))
    s3 = json.loads(shared("schemas", "selection.v0.3.json").read_text(encoding="utf-8"))
    assert s4["properties"]["formatVersion"] == {"const": "ifs-selection/0.4"}
    assert s3["properties"]["formatVersion"] == {"const": "ifs-selection/0.3"}                # 0.3 스키마는 그대로
    assert "picking" in s4["properties"]["stage"]["enum"] and "picking" not in s3["properties"]["stage"]["enum"]
    # 0.4는 0.3의 필드를 빼지 않았다(선택 필드만 더함)
    assert set(s3["properties"]) <= set(s4["properties"]) and set(s3["$defs"]) <= set(s4["$defs"])
    g3, g4 = s3["$defs"]["generation"], s4["$defs"]["generation"]
    assert g3["required"] == g4["required"] and set(g3["properties"]) < set(g4["properties"])
