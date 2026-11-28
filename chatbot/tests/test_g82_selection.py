"""G82 실험 경로 연결: [맞는 게 없어요] 뒤 규칙에 중심 형태 명사가 없을 때만 LLM 형태 이름 → 근거 인용 줄과 함께 그림 고르기(G75).
생성기는 대역(tests/fixtures/fake_gen3d.py), LLM은 가짜 백엔드(test_g77 FakeLLM). 모든 대사는 합성이다."""
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import WEB_DIR, shared
from ifs_chatbot.server import create_app

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import T_NOSHAPE, T_SHAPE, done_session, sel_json, wait_stage  # noqa: E402
from test_g75_image_pick import calls, fake, pcfg  # noqa: E402,F401
from test_g77_llm_fill import FakeLLM  # noqa: E402

V05 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.5.json").read_text(encoding="utf-8")))
T_PEBBLE = "조약돌이 하나 있어요."
ITEM = {"item": {"quote": "조약돌이", "charSpan": [0, 4], "en": "pebble"}}


def gcfg(tmp_path, on=True, **over):
    c = pcfg(tmp_path)
    if on:
        c = c.with_overrides(**{"gen3d.on_none_llm_shape": True, "selection.protocol": "selection_protocol.v0.12.json",
                                "gen3d.on_none_llm_shape_timeout_s": 5.0})
    return c.with_overrides(**over) if over else c


def start(tmp_path, text, reply=ITEM, on=True, sid="SYN-G82-SEL", **over):
    llm = FakeLLM(reply)
    rt = Runtime(gcfg(tmp_path, on=on, **over), backend=llm)
    s = done_session(rt, sid, text)
    f = s.selection()
    assert f.start()["stage"] == "selecting"
    return rt, s, f, llm


def valid5(f):
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.5"
    errs = [f"{list(e.path)}: {e.message}" for e in V05.iter_errors(d)]
    assert not errs, errs[:3]
    return d


def none_until_settled(f):
    v = f.select("none")
    if v["stage"] == "generating":
        wait_stage(f)
    return f.view()


# ── 설정·문구 ────────────────────────────────────────────────────────────────
def test_protocol_012_adds_two_draft_phrases_only():
    a = json.loads(shared("protocol", "selection_protocol.v0.11.json").read_text(encoding="utf-8"))
    b = json.loads(shared("protocol", "selection_protocol.v0.12.json").read_text(encoding="utf-8"))
    assert b["protocolVersion"] == "0.12.0" and b["changes"][0]["version"] == "0.12.0"
    assert set(b["phrases"]) - set(a["phrases"]) == {"llm_shape_basis", "llm_shape_basis_wrong_button"}
    assert all(b["phrases"][k] == a["phrases"][k] for k in a["phrases"])
    for k in ("llm_shape_basis", "llm_shape_basis_wrong_button"):
        t = b["phrases"][k]
        assert t["status"] == "draft" and "G82" in t["source"]
        assert not any(w in t["text"] for w in ("치료", "진단", "내담자", "증상", "예를 들어", "예를 들면"))
    assert "{quote}" in b["phrases"]["llm_shape_basis"]["text"] and b["phrases"]["llm_shape_basis_wrong_button"]["text"] == "그 말이 아니에요"


def test_configs_experiment_off_and_test_config_on():
    assert load_config("experiment").gen3d.on_none_llm_shape is False
    t = load_config("experiment-g82")
    assert t.gen3d.on_none_llm_shape is True and t.selection.protocol == "selection_protocol.v0.12.json"
    assert t.gen3d.on_none and t.gen3d.on_none_image_pick and t.mapping.mode == "v2"


def test_runtime_refuses_protocol_without_basis_phrases(tmp_path):
    with pytest.raises(RuntimeError, match="llm_shape_basis"):
        Runtime(gcfg(tmp_path).with_overrides(**{"selection.protocol": "selection_protocol.v0.11.json"}), backend=FakeLLM())


# ── 끔 = 그대로 ──────────────────────────────────────────────────────────────
def test_flag_off_no_call_and_records_unchanged(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, on=False)
    assert f.shape_llm_on is False and rt.llm_shape_prompt is None
    v = none_until_settled(f)
    assert llm.calls == [] and v["stage"] == "adjusting" and "llmShapeBasis" not in v
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.4"
    an = d["generation"]["afterNone"]
    assert "shapeLlm" not in d["generation"] and not any(k.startswith("shapeLlm") for k in an)
    assert an["blockReason"] == "no_shape_stated"


# ── 켬 ───────────────────────────────────────────────────────────────────────
def test_rule_caught_shape_no_call(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_SHAPE, sid="SYN-G82-RULE")
    v = none_until_settled(f)
    assert v["stage"] == "picking" and llm.calls == [] and "llmShapeBasis" not in v
    d = valid5(f)
    sl = d["generation"]["shapeLlm"]
    assert sl["route"] == "rule" and sl["routeReason"] == "rule_has_shape" and sl["called"] is False
    assert d["generation"]["afterNone"]["shapeLlmUsed"] is False


def test_llm_shape_fills_prompt_basis_line_then_mesh(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G82-OK")
    v = f.select("none")
    assert v["stage"] == "generating"
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "picking" and len(llm.calls) == 1
    b = v["llmShapeBasis"]
    assert b["quote"] == "조약돌이" and b["text"] == "'조약돌이'라고 하신 말을 바탕으로 모양을 만들어 볼게요."
    assert "pebble" not in json.dumps(b, ensure_ascii=False)                     # 영어 이름은 화면에 보이지 않음
    c0 = calls(tmp_path)[0]
    assert c0["imagePick"]
    d = valid5(f)
    an = d["generation"]["afterNone"]
    assert an["shapeLlmUsed"] is True and an["prompt"]["shapeSource"] == "llm_translated"
    assert an["imagePick"]["promptText"].startswith("a single pebble") and an["blockReason"] is None
    sl = d["generation"]["shapeLlm"]
    assert sl["route"] == "llm" and sl["called"] and sl["candidate"] and sl["exposed"] is True and sl["rejected"] is False
    assert sl["adopted"]["en"] == "pebble" and sl["inputTextSha256"] == sl["validatorTextSha256"]
    assert sl["model"]["digest"] and sl["promptVersion"] == "0.3.0" and sl["validatorRules"] and sl["seed"] == 0
    assert json.loads(sl["rawText"])["item"]["en"] == "pebble"
    v = f.pick_image("0")
    assert v["stage"] == "generating"
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "selecting" and v["candidates"][0].get("afterNone") is True
    f.select(v["candidates"][0]["id"])
    d = valid5(f)
    assert d["generation"]["shapeLlm"]["imageChosen"] is True and d["generation"]["shapeLlm"]["candidateChosen"] is True
    assert len(llm.calls) == 1


def test_basis_rejected_goes_none_path_without_recall(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G82-REJ")
    none_until_settled(f)
    assert f.stage == "picking"
    v = f.reject_shape_basis()
    assert v["stage"] == "adjusting" and len(llm.calls) == 1
    d = valid5(f)
    an = d["generation"]["afterNone"]
    assert an["basisRejected"] is True and an["imagePick"]["outcome"] == "basis_rejected" and an["status"] == "declined"
    assert d["generation"]["shapeLlm"]["rejected"] is True and d["generation"]["shapeLlm"]["rejectedAt"]
    assert d["selection"]["none"] is True
    assert f._shape_items() == []                                            # 거절 뒤에는 쓰지 않음


def test_second_round_reuses_without_recall(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G82-R2")
    none_until_settled(f)
    v = f.pick_image("none")                                                   # [이 중에는 없어요] → 다음 회차
    assert v["stage"] == "generating"
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "picking" and v["afterNone"]["round"] == 1 and v["llmShapeBasis"]["quote"] == "조약돌이"
    assert len(llm.calls) == 1 and len(calls(tmp_path)) == 2


def test_flagged_session_no_call(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G82-FLAG")
    s.log.data["alerts"].append({"kind": "soft_check", "detail": "합성", "turn": 1, "severity": "warning"})
    v = none_until_settled(f)
    assert llm.calls == [] and v["stage"] == "adjusting"
    sl = valid5(f)["generation"]["shapeLlm"]
    assert sl["route"] == "none" and sl["routeReason"] == "session_flagged" and sl["called"] is False


@pytest.mark.parametrize("reply,reason", [({"item": None}, "null"), ({"item": {"quote": "하나", "charSpan": [5, 7], "en": "one"}}, "rejected")])
def test_llm_null_or_rejected_goes_none_path(tmp_path, fake, reply, reason):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, reply=reply, sid="SYN-G82-NULL")
    v = none_until_settled(f)
    assert v["stage"] == "adjusting" and len(llm.calls) == 1 and calls(tmp_path) == []
    d = valid5(f)
    assert d["generation"]["shapeLlm"]["route"] == "none" and d["generation"]["shapeLlm"]["status"] == reason
    assert d["generation"]["afterNone"]["blockReason"] == "no_shape_stated"


def test_no_shape_no_generation(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_NOSHAPE, reply={"item": None}, sid="SYN-G82-NOSHAPE")
    v = none_until_settled(f)
    assert v["stage"] == "adjusting" and calls(tmp_path) == []


def test_skip_during_llm_wait(tmp_path, fake):
    def slow(system, user, schema):
        time.sleep(0.8)
        return ITEM
    rt, s, f, llm = start(tmp_path, T_PEBBLE, reply=slow, sid="SYN-G82-SKIP")
    v = f.select("none")
    assert v["stage"] == "generating"
    v = f.skip_generation()
    assert v["stage"] == "adjusting"
    t = time.monotonic()
    while (f.shape_llm is None or "participantLeftBeforeResult" not in f.shape_llm) and time.monotonic() - t < 10:
        time.sleep(0.05)
    assert f.shape_llm["participantLeftBeforeResult"] is True and f.stage == "adjusting" and calls(tmp_path) == []


def test_api_reject_endpoint_and_web_wiring(tmp_path, fake):
    llm = FakeLLM(ITEM)
    rt = Runtime(gcfg(tmp_path), backend=llm)
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G82-API", T_PEBBLE)
    c.post(f"/api/sessions/{s.id}/candidates")
    assert c.post(f"/api/sessions/{s.id}/selection/shape-basis/reject").status_code == 409     # 고르기 화면 전
    c.post(f"/api/sessions/{s.id}/selection", json={"candidateId": "none"})
    wait_stage(s.selection_flow)
    v = c.get(f"/api/sessions/{s.id}/selection").json()
    assert v["stage"] == "picking" and v["llmShapeBasis"]["quote"] == "조약돌이"
    assert c.get("/api/selection/config").json()["phrases"]["llm_shape_basis_wrong_button"] == "그 말이 아니에요"
    r = c.post(f"/api/sessions/{s.id}/selection/shape-basis/reject")
    assert r.status_code == 200 and r.json()["stage"] == "adjusting"
    js = (WEB_DIR / "stage.js").read_text(encoding="utf-8")
    for needle in ("v.llmShapeBasis", "/selection/shape-basis/reject", "llm_shape_basis_wrong_button"):
        assert needle in js, needle
