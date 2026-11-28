"""G85: 규칙 → G82 → LLM 다시 쓰기 재료(대상 명사구 + 모양 꾸밈) → 규칙 조립, 형태를 말하지 않으면 고정 중립 형태(system_default),
메시 관문에 막히면 남은 그림으로 세션에 한 번만 돌아감. 생성기는 대역(tests/fixtures/fake_gen3d.py), LLM은 가짜 백엔드. 모든 대사는 합성이다."""
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ifs_chatbot import llm_rewrite as lr
from ifs_chatbot import none_gen as ng
from ifs_chatbot import wordnet_check as wnc
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import WEB_DIR, shared
from ifs_chatbot.scene_builder import normalize_confirmed

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import T_NOSHAPE, T_PERSON, T_SHAPE, done_session, sel_json, wait_stage  # noqa: E402
from test_g75_image_pick import calls, fake, pcfg  # noqa: E402,F401
from test_g77_llm_fill import FakeLLM  # noqa: E402

V05 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.5.json").read_text(encoding="utf-8")))
T_STEP = "디딤돌이 하나 있어요."                    # 사전 0.3.0 밖 형태 명사(규칙 → no_shape_stated)
T_BUMPY_STEP = "울퉁불퉁한 디딤돌이 하나 있어요."   # 규칙이 꾸밈말만 잡음(modifier_only)
SUBJ = {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [0, 4]}
G82_NULL = {"item": None}
G82_ITEM = {"item": {"quote": "디딤돌이", "charSpan": [0, 4], "en": "pebble"}}


def added(*ws):
    return [{"en": w, "basis": "none", "quote": "", "charSpan": []} for w in ws]


def rw_item(subject=SUBJ, details=()):
    return {"item": {"subject": dict(subject), "details": list(details)}}


class Dual(FakeLLM):
    """G82 호출(스키마에 subject 없음)과 G85 호출(subject 있음)에 따로 답한다."""

    def __init__(self, g82=G82_NULL, g85=None):
        super().__init__(lambda system, user, schema: g85 if "subject" in json.dumps(schema) else g82)

    def kinds(self):
        return ["g85" if "subject" in json.dumps(c["schema"]) else "g82" for c in self.calls]


def rcfg(tmp_path, on=True, retry=False, **over):
    c = pcfg(tmp_path).with_overrides(**{"gen3d.on_none_llm_shape": True, "gen3d.on_none_llm_shape_timeout_s": 5.0,
                                          "selection.protocol": "selection_protocol.v0.14.json"})
    if on:
        c = c.with_overrides(**{"gen3d.on_none_llm_rewrite": True, "gen3d.on_none_llm_rewrite_timeout_s": 5.0})
    if retry:
        c = c.with_overrides(**{"gen3d.on_none_mesh_retry": True})
    return c.with_overrides(**over) if over else c


def start(tmp_path, text, llm, on=True, retry=False, sid="SYN-G85", **over):
    rt = Runtime(rcfg(tmp_path, on=on, retry=retry, **over), backend=llm)
    s = done_session(rt, sid, text)
    f = s.selection()
    assert f.start()["stage"] == "selecting"
    return rt, s, f


def settle(f):
    v = f.select("none")
    if v["stage"] == "generating":
        wait_stage(f)
    return f.view()


def valid5(f):
    d = sel_json(f)
    errs = [f"{list(e.path)}: {e.message}" for e in V05.iter_errors(d)]
    assert not errs, errs[:3]
    return d


# ── 검증기 단위(가짜 LLM, 세션 없이 propose) ────────────────────────────────────
@pytest.fixture(scope="module")
def offline_rt(tmp_path_factory):
    logs = tmp_path_factory.mktemp("g85-logs")
    cfg = load_config("experiment-g85").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none",
                                                          "session.log_dir": str(logs), "preview.mode": "none"})
    return Runtime(cfg)


def propose(rt, text, reply, flag=None, g82=None, cache=None):
    norm = normalize_confirmed(text)
    spec = rt.scene_builder.build(norm, session_id="SYN-G85-U", participant_id="SYN")
    spec = spec if isinstance(spec, dict) else spec.to_dict()
    llm = FakeLLM(reply)
    rec = lr.propose(rt.llm_rewrite_prompt, llm, norm, spec, seed=0, timeout_s=5.0,
                     cache={} if cache is None else cache, flag=flag, g82=g82)
    return rec, llm


def route(rec):
    return lr.decide_route(rec, (rec.get("ruleRoute") or {}).get("reason"))[0]


def test_adopted_subject_and_grounded_and_added(offline_rt):
    rec, llm = propose(offline_rt, T_STEP, rw_item(details=added("round", "pointed")))
    assert rec["status"] == "ok" and rec["called"] and route(rec) == "llm_rewrite" and len(llm.calls) == 1
    assert rec["shapePromptText"].startswith("a single round pointed stepping stone, one solid object")
    assert rec["addedCount"] == 2 and rec["adopted"]["subject"]["quote"] == "디딤돌이"
    assert rec["options"]["temperature"] == 0 and rec["inputTextSha256"] == rec["validatorTextSha256"]
    assert rec["model"]["digest"] and rec["prompt"]["promptVersion"] == "0.1.0" and rec["rawText"]
    assert rec["wordnet"]["status"] in ("available", "unavailable")
    # 사용자 메시지에 면담자 질문·매퍼 슬롯 값이 없다(확정 텍스트·어절·구간만)
    assert "확정 텍스트:\n디딤돌이 하나 있어요." in llm.calls[0]["user"]


def test_ungrounded_subject_goes_neutral(offline_rt):
    bad = {"en": "stepping stone", "quote": "징검다리", "charSpan": [0, 4]}            # 원문에 없는 인용
    rec, _ = propose(offline_rt, T_STEP, rw_item(subject=bad, details=added("round")))
    assert rec["outcome"] == "no_subject" and rec["adopted"] is None and route(rec) == "system_default"
    rec, _ = propose(offline_rt, "쑥색이고 차가워요.", {"item": None})
    assert rec["outcome"] == "null" and route(rec) == "system_default"


def test_added_limits(offline_rt):
    rec, _ = propose(offline_rt, T_STEP, rw_item(details=added("round", "flat", "pointed")))
    els = rec["validation"]["details"]
    assert [d["accepted"] for d in els] == [True, True, False] and els[2]["rejectReasons"] == ["added_over_limit"]
    assert rec["addedCount"] == 2 and rec["status"] == "ok"
    rec, _ = propose(offline_rt, T_STEP, rw_item(details=added("jagged", "hollow", "long")))   # 목록 밖
    assert all("added_not_in_list" in d["rejectReasons"] for d in rec["validation"]["details"])
    assert rec["addedCount"] == 0 and rec["shapePromptText"].startswith("a single stepping stone,")
    # 대상 명사가 없거나 기각되면 덧붙임도 모두 버림
    rec, _ = propose(offline_rt, "답답해요.", rw_item(subject={"en": "rope", "quote": "답답해요", "charSpan": [0, 4]},
                                                  details=added("round", "flat")))
    assert rec["outcome"] == "no_subject" and rec["adopted"] is None and route(rec) == "system_default"


@pytest.mark.parametrize("subject_en,reason", [("sad stone", "english_emotion"), ("heavy stone", "english_non_shape"),
                                               ("green stone", "english_color_size"), ("tangled stone", "subject_modifier"),
                                               ("stone on floor", "english_place")])
def test_subject_emotion_state_color_rejected(offline_rt, subject_en, reason):
    rec, _ = propose(offline_rt, T_STEP, rw_item(subject={**SUBJ, "en": subject_en}))
    assert rec["outcome"] == "no_subject" and reason in rec["rejectReasons"]


@pytest.mark.parametrize("text,detail,reason", [
    ("쑥색 디딤돌이 하나 있어요.", {"en": "round", "quote": "쑥색", "charSpan": [0, 2]}, "color_word"),
    ("엉킨 디딤돌이 하나 있어요.", {"en": "compressed", "quote": "엉킨", "charSpan": [0, 2]}, "english_state"),
    (T_STEP, {"en": "tangled", "quote": "", "charSpan": []}, "added_not_in_list"),
    (T_STEP, {"en": "heavy", "quote": "", "charSpan": []}, "english_non_shape"),
])
def test_detail_color_emotion_state_rejected(offline_rt, text, detail, reason):
    subj = {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [text.index("디딤돌이"), text.index("디딤돌이") + 4]}
    d = {**detail, "basis": "none" if not detail["quote"] else "quote"}
    rec, _ = propose(offline_rt, text, rw_item(subject=subj, details=[d]))
    det = rec["validation"]["details"][0]
    assert det["accepted"] is False and reason in det["rejectReasons"], det
    assert rec["status"] == "ok" and rec["addedCount"] == 0                     # 대상은 그대로 채택, 그 꾸밈만 버림


@pytest.mark.parametrize("text,subject,why", [
    ("도롱뇽이 하나 있어요.", {"en": "salamander", "quote": "도롱뇽이", "charSpan": [0, 4]}, "english_banned"),
    ("뭔가 있어요.", {"en": "doll", "quote": "뭔가", "charSpan": [0, 2]}, "english_banned"),
])
def test_forbidden_category_no_neutral(offline_rt, text, subject, why):
    rec, _ = propose(offline_rt, text, rw_item(subject=subject))
    assert rec["outcome"] == "forbidden" and route(rec) == "none" and any(why in x for x in rec["forbidden"])


def test_wordnet_hypernym_catches_unlisted_animal(offline_rt):
    if wnc.info()["status"] != "available":
        pytest.skip("WordNet 없음(기록 unavailable)")
    assert wnc.reasons("newt")[0] == ["wordnet_forbidden"] and wnc.reasons("rock")[0] == []
    assert wnc.reasons("teddy bear")[0] == ["wordnet_forbidden"]
    rec, _ = propose(offline_rt, "뭔가 있어요.", rw_item(subject={"en": "newt", "quote": "뭔가", "charSpan": [0, 2]}))
    assert "subject:wordnet_forbidden" in rec["forbidden"] and route(rec) == "none"


def test_forbidden_detail_eyes(offline_rt):
    rec, _ = propose(offline_rt, T_STEP, rw_item(details=[{"en": "eyed", "basis": "none", "quote": "", "charSpan": []}]))
    assert rec["outcome"] == "forbidden" and route(rec) == "none"


def test_g82_forbidden_reject_skips_and_no_generation(offline_rt):
    rec, llm = propose(offline_rt, T_STEP, rw_item(), g82={"status": "rejected", "rejectReasons": ["english_banned"]})
    assert llm.calls == [] and rec["skipReason"] == "g82_forbidden" and route(rec) == "none"
    rec, llm = propose(offline_rt, T_STEP, rw_item(), g82={"status": "ok", "adopted": {"en": "pebble"}})
    assert llm.calls == [] and rec["skipReason"] == "g82_adopted"


def test_rule_blocked_category_not_called(offline_rt):
    rec, llm = propose(offline_rt, T_PERSON, rw_item())
    assert llm.calls == [] and rec["skipReason"].startswith("rule_blocked") and route(rec) == "none"


@pytest.mark.parametrize("text", ["디딤돌은 아니에요.", "예전에는 디딤돌이었어요.", "친구가 디딤돌 같대요.",
                                  "디딤돌이면 좋겠어요.", "디딤돌처럼 무거워요."])
def test_context_frames_rejected_goes_neutral(offline_rt, text):
    i = text.index("디딤돌")
    q = text[i:text.index(" ", i)] if " " in text[i:] else text[i:]
    q = q.rstrip(".")
    rec, _ = propose(offline_rt, text, rw_item(subject={"en": "stepping stone", "quote": q, "charSpan": [i, i + len(q)]},
                                               details=added("round")))
    assert rec["status"] != "ok" and rec["adopted"] is None, (text, rec["rejectReasons"])
    assert route(rec) in ("system_default", "none")


def test_flagged_no_call_no_cache_lookup(offline_rt):
    cache = {"x": 1}
    rec, llm = propose(offline_rt, T_STEP, rw_item(), flag="alert:soft_check", cache=cache)
    assert llm.calls == [] and rec["skipReason"] == "session_flagged" and rec["cacheKey"] is None and cache == {"x": 1}
    assert route(rec) == "none"


def test_cache_same_text_no_recall(offline_rt):
    cache = {}
    a, l1 = propose(offline_rt, T_STEP, rw_item(), cache=cache)
    b, l2 = propose(offline_rt, T_STEP, rw_item(), cache=cache)
    assert len(l1.calls) == 1 and l2.calls == [] and b["cached"] is True and b["shapePromptText"] == a["shapePromptText"]


def test_generator_recheck_fail_closed(offline_rt):
    pm = ng._load_prompts()
    norm = normalize_confirmed(T_STEP)
    ok = {"subject": dict(SUBJ), "details": [{"en": "round", "origin": "added"}]}
    assert pm._rewrite_head(norm, ok) is not None
    assert pm._rewrite_head(norm, {**ok, "subject": {**SUBJ, "quote": "디딤돌"}}) is None          # 구간 불일치
    assert pm._rewrite_head(norm, {**ok, "details": [{"en": w, "origin": "added"} for w in ("round", "flat", "oval")]}) is None
    assert pm._rewrite_head(norm, {**ok, "details": [{"en": "tangled", "origin": "added"}]}) is None
    assert pm._rewrite_head(norm, {**ok, "subject": {**SUBJ, "en": "doll"}}) is None
    # 다시 쓰기·중립 인자를 주지 않으면 규칙 출력은 예전 그대로(경로 층 유지)
    for t in (T_STEP, T_SHAPE, T_NOSHAPE, T_PERSON, T_BUMPY_STEP):
        n = normalize_confirmed(t)
        assert pm.shape_prompt(n) == pm.shape_prompt(n, llm_rewrite_item=None, neutral_form=None)
    # 중립 형태는 규칙이 아무 형태 낱말도 못 잡았을 때만(꾸밈말만 잡았거나 형태를 잡았으면 쓰이지 않음)
    ref = pm.neutral_form_ref()
    assert pm.shape_prompt(normalize_confirmed(T_NOSHAPE), neutral_form=ref)["shapeSource"] == "system_default"
    assert "shapeSource" not in pm.shape_prompt(normalize_confirmed(T_SHAPE), neutral_form=ref)
    assert pm.shape_prompt(normalize_confirmed(T_PERSON), neutral_form=ref)["status"] == "blocked"
    assert "shapeSource" not in pm.shape_prompt(normalize_confirmed(T_NOSHAPE), neutral_form={"version": "x", "sha256": "y"})


def test_closed_list_geometric_only():
    a = json.loads(shared("lexicon", "shape_added_adjectives.v0.json").read_text(encoding="utf-8"))
    assert a["maxAdded"] == 2 and a["status"] == "draft"
    for w in ("compressed", "tangled", "broken", "heavy", "tight", "crushed", "trapped", "hollow", "twisted"):
        assert w not in a["words"] and w in a["excluded"]
    assert all(isinstance(v, str) and v for v in a["words"].values())                  # 낱말마다 넣은 이유
    n = json.loads(shared("lexicon", "neutral_form_prompt.v0.json").read_text(encoding="utf-8"))
    assert n["phrase"] == "smooth abstract lump"


# ── 설정·문구 ────────────────────────────────────────────────────────────────
G85_KEYS = {"llm_rewrite_basis", "llm_rewrite_added", "llm_rewrite_neutral", "llm_rewrite_waiting", "mesh_retry_note"}


def test_protocol_014_adds_draft_phrases_only():
    a = json.loads(shared("protocol", "selection_protocol.v0.13.json").read_text(encoding="utf-8"))
    b = json.loads(shared("protocol", "selection_protocol.v0.14.json").read_text(encoding="utf-8"))
    assert b["protocolVersion"] == "0.14.0" and b["changes"][0]["version"] == "0.14.0"
    assert set(b["phrases"]) - set(a["phrases"]) == G85_KEYS
    assert all(b["phrases"][k] == a["phrases"][k] for k in a["phrases"])
    import re
    for k in G85_KEYS:
        t = b["phrases"][k]
        assert t["status"] == "draft" and "G85" in t["source"]
        assert not any(w in t["text"] for w in ("치료", "진단", "내담자", "증상", "예를 들어", "예를 들면", "같은 것", "이나 "))
        assert not re.search(r"[A-Za-z]", t["text"].replace("{quote}", "").replace("{rago}", ""))   # 영어 없음


def test_configs_g85_only_in_test_config():
    e, t = load_config("experiment"), load_config("experiment-g85")
    # 실험 설정은 메인 세션이 켤 때 함께 0.14 문구로 바꾼다(켰으면 문구도 0.14 — 꺼져 있으면 0.13 그대로)
    if e.gen3d.on_none_llm_rewrite:
        assert e.selection.protocol == "selection_protocol.v0.14.json" and e.gen3d.on_none_llm_shape
    assert t.gen3d.on_none_llm_rewrite is True and t.gen3d.on_none_mesh_retry is True
    assert t.selection.protocol == "selection_protocol.v0.14.json"
    assert t.gen3d == replace(e.gen3d, on_none_llm_rewrite=True, on_none_mesh_retry=True, on_none_llm_rewrite_timeout_s=25.0)
    assert t.selection == replace(e.selection, protocol="selection_protocol.v0.14.json")
    assert t.mapping == e.mapping and t.interview == e.interview and t.llm == e.llm


def test_runtime_refuses_bad_combos(tmp_path):
    with pytest.raises(RuntimeError, match="on_none_llm_shape"):
        Runtime(rcfg(tmp_path).with_overrides(**{"gen3d.on_none_llm_shape": False}), backend=Dual())
    with pytest.raises(RuntimeError, match="llm_rewrite_basis"):
        Runtime(rcfg(tmp_path).with_overrides(**{"selection.protocol": "selection_protocol.v0.13.json"}), backend=Dual())


# ── 실험 경로(가짜 생성기) ─────────────────────────────────────────────────────
def test_flag_off_records_unchanged(tmp_path, fake):
    llm = Dual(g85=rw_item())
    rt, s, f = start(tmp_path, T_STEP, llm, on=False, sid="SYN-G85-OFF")
    v = settle(f)
    assert v["stage"] == "adjusting" and llm.kinds() == ["g82"]
    d = valid5(f)
    assert "rewrite" not in d["generation"] and "promptRoute" not in d["generation"] and "meshRetry" not in d["generation"]
    assert not any(k in d["generation"]["afterNone"] for k in ("rewriteUsed", "neutralUsed", "promptRoute", "meshAttempts"))
    assert "rewriteOn" not in v.get("afterNone", {})


def test_rewrite_path_basis_and_added_line(tmp_path, fake):
    llm = Dual(g85=rw_item(details=added("round")))
    rt, s, f = start(tmp_path, T_STEP, llm, sid="SYN-G85-OK")
    v = settle(f)
    assert v["stage"] == "picking" and llm.kinds() == ["g82", "g85"]
    assert v["llmRewriteBasis"]["quote"] == "디딤돌" and v["llmRewriteBasis"]["text"] == "'디딤돌'이라고 하신 말을 바탕으로 그려 봤어요."
    assert v["llmRewriteAdded"]["text"] == "말씀하지 않은 모양이 더해졌을 수 있어요." and "llmRewriteNeutral" not in v
    assert "stepping" not in json.dumps({k: v[k] for k in ("llmRewriteBasis", "llmRewriteAdded")}, ensure_ascii=False)
    d = valid5(f)
    g = d["generation"]
    assert g["promptRoute"] == "llm_rewrite" and g["afterNone"]["promptRoute"] == "llm_rewrite"
    an = g["afterNone"]
    assert an["rewriteUsed"] is True and an["prompt"]["shapeSource"] == "llm_rewrite"
    assert an["imagePick"]["promptText"].startswith("a single round stepping stone")
    rw = g["rewrite"]
    assert rw["exposed"] and rw["addedLineShown"] and rw["addedCount"] == 1 and rw["assembledPrompt"] == an["prompt"]["text"]
    assert [e["origin"] for e in rw["elements"]] == ["grounded", "added"] and rw["basisShown"]["shownText"] == "디딤돌"
    v = f.pick_image("0")
    wait_stage(f)
    assert f.view()["stage"] == "selecting" and f.rewrite["imageChosen"] and f.rewrite["candidateExposed"]


def test_g82_adopted_g85_not_called(tmp_path, fake):
    llm = Dual(g82=G82_ITEM, g85=rw_item())
    rt, s, f = start(tmp_path, T_STEP, llm, sid="SYN-G85-G82")
    v = settle(f)
    assert v["stage"] == "picking" and llm.kinds() == ["g82"] and "llmShapeBasis" in v and "llmRewriteBasis" not in v
    assert valid5(f)["generation"]["promptRoute"] == "llm_word"


def test_neutral_form_path(tmp_path, fake):
    llm = Dual(g85={"item": None})
    rt, s, f = start(tmp_path, T_NOSHAPE, llm, sid="SYN-G85-NEU")
    v = settle(f)
    assert v["stage"] == "picking" and llm.kinds() == ["g82", "g85"]
    assert v["llmRewriteNeutral"]["text"].startswith("말씀하신 것에서 모양을 찾지 못해서") and "llmRewriteBasis" not in v
    assert "llmShapeBasis" not in v and "llmRewriteAdded" not in v
    d = valid5(f)
    an = d["generation"]["afterNone"]
    assert d["generation"]["promptRoute"] == "system_default" and an["neutralUsed"] is True
    assert an["imagePick"]["promptText"].startswith("a single smooth abstract lump, one solid object")
    assert d["generation"]["rewrite"]["neutralLineShown"] is True and d["generation"]["rewrite"]["neutralForm"]["version"]
    with pytest.raises(Exception):
        f.reject_shape_basis()                                     # 중립 형태에는 [그 말이 아니에요]가 없다


def test_forbidden_said_no_neutral(tmp_path, fake):
    llm = Dual(g85=rw_item(subject={"en": "doll", "quote": "디딤돌이", "charSpan": [0, 4]}))
    rt, s, f = start(tmp_path, T_STEP, llm, sid="SYN-G85-FB")
    v = settle(f)
    assert v["stage"] == "adjusting" and calls(tmp_path) == []
    assert valid5(f)["generation"]["promptRoute"] == "none"
    rt2, s2, f2 = start(tmp_path, T_PERSON, Dual(g85=rw_item()), sid="SYN-G85-PERSON")
    v = settle(f2)
    assert v["stage"] == "adjusting" and f2.rewrite["route"] == "none" and f2.rewrite["routeReason"].startswith("rule_blocked")


def test_flagged_session_no_llm_no_neutral(tmp_path, fake):
    llm = Dual(g85={"item": None})
    rt, s, f = start(tmp_path, T_NOSHAPE, llm, sid="SYN-G85-FLAG")
    s.log.data["alerts"].append({"kind": "soft_check", "detail": "합성", "turn": 1, "severity": "warning"})
    v = settle(f)
    assert llm.calls == [] and v["stage"] == "adjusting" and calls(tmp_path) == []
    rw = valid5(f)["generation"]["rewrite"]
    assert rw["route"] == "none" and rw["routeReason"] == "session_flagged" and rw["called"] is False


def test_basis_reject_no_recall(tmp_path, fake):
    llm = Dual(g85=rw_item())
    rt, s, f = start(tmp_path, T_STEP, llm, sid="SYN-G85-REJ")
    settle(f)
    v = f.reject_shape_basis()
    assert v["stage"] == "adjusting" and llm.kinds() == ["g82", "g85"]
    d = valid5(f)
    assert d["generation"]["rewrite"]["rejected"] is True and f._rewrite_item() is None


def test_web_wiring():
    js = (WEB_DIR / "stage.js").read_text(encoding="utf-8")
    for needle in ("v.llmRewriteBasis", "v.llmRewriteAdded", "v.llmRewriteNeutral", "v.meshRetry", "llm_rewrite_waiting"):
        assert needle in js, needle


# ── 메시 관문 → 남은 그림으로 한 번 ───────────────────────────────────────────────
def to_picking(f):
    v = settle(f)
    assert v["stage"] == "picking", f.data["generation"]["afterNone"]
    return v


def test_mesh_retry_once_then_none(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_GEN3D_MESH_GATE_SEEDS", "0,1,2")
    llm = Dual()
    rt, s, f = start(tmp_path, T_SHAPE, llm, retry=True, sid="SYN-G85-MR")
    v = to_picking(f)
    n0 = len(v["imagePick"]["images"])
    f.pick_image("0")
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "picking" and v["meshRetry"]["text"].startswith("고르신 그림으로는")
    assert len(v["imagePick"]["images"]) == n0 - 1 and 0 not in [x["position"] for x in v["imagePick"]["images"]]
    with pytest.raises(Exception):
        f.pick_image("0")                                          # 막힌 그림은 다시 고를 수 없음
    f.pick_image(str(v["imagePick"]["images"][0]["position"]))
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "adjusting"                               # 두 번째도 막힘 → 지금처럼 끝
    mr = valid5(f)["generation"]["meshRetry"]
    assert mr["used"] is True and mr["attemptsTotal"] == 2 and [r["blockReason"] for r in mr["results"]] == ["person_like"] * 2
    assert all(r["gate"] for r in mr["results"])


def test_mesh_retry_second_ok(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_GEN3D_MESH_GATE_SEEDS", "0")
    rt, s, f = start(tmp_path, T_SHAPE, Dual(), retry=True, sid="SYN-G85-MR2")
    to_picking(f)
    f.pick_image("0")
    wait_stage(f)
    v = f.view()
    f.pick_image(str(v["imagePick"]["images"][0]["position"]))
    wait_stage(f)
    assert f.view()["stage"] == "selecting"
    assert valid5(f)["generation"]["meshRetry"]["attemptsTotal"] == 2


def test_mesh_retry_off_unchanged(tmp_path, fake, monkeypatch):
    monkeypatch.setenv("FAKE_GEN3D_MESH_GATE_SEEDS", "0")
    rt, s, f = start(tmp_path, T_SHAPE, Dual(), on=False, sid="SYN-G85-MR0")
    to_picking(f)
    f.pick_image("0")
    wait_stage(f)
    assert f.view()["stage"] == "adjusting" and "meshRetry" not in sel_json(f)["generation"]


# ── (G85 판정 뒤) 몸 낱말로 돌려 말하기 · 비유 꾸밈 · 중립 문구 ─────────────────────────────
@pytest.mark.parametrize("text", ["눈 두 개가 달린 디딤돌이에요.", "입이 있는 디딤돌이에요.", "다리가 네 개인 디딤돌 같은 게 있어요.",
                                  "털이 숭숭 난 디딤돌 같아요.", "꼬리가 달린 디딤돌이에요.", "눈이 두 개예요.",
                                  "눈 하나가 박힌 디딤돌이에요."])
def test_body_part_attachment_blocks_all_routes(offline_rt, text):
    pm = ng._load_prompts()
    n = normalize_confirmed(text)
    p = pm.shape_prompt(n)
    assert p["status"] == "blocked" and p["blockReason"] == "body_part_attachment" and "body_part_attachment:" in p["blockDetail"]
    rec, llm = propose(offline_rt, text, rw_item())
    assert llm.calls == [] and rec["skipReason"] == "rule_blocked:body_part_attachment" and route(rec) == "none"  # 중립도 아님
    # G82·G85 재료를 주어도 생성 직전 재검증에서 막힘(같은 함수)
    assert pm.shape_prompt(n, llm_rewrite_item={"subject": {**SUBJ, "quote": "디딤돌이"}, "details": []})["status"] == "blocked"
    assert pm.shape_prompt(n, neutral_form=pm.neutral_form_ref())["status"] == "blocked"


@pytest.mark.parametrize("text", ["손잡이가 달린 컵이에요.", "다리 위에 돌이 있어요.", "주둥이가 긴 병이에요.",
                                  "어깨가 축 처져요.", "눈앞에 공이 있어요.", "눈이 달린 건 아니고 그냥 돌이에요."])
def test_body_word_not_attachment_not_blocked(text):
    pm = ng._load_prompts()
    assert pm.shape_prompt(normalize_confirmed(text))["blockReason"] != "body_part_attachment"


def test_body_attachment_flow_no_generation(tmp_path, fake):
    llm = Dual(g85=rw_item())
    rt, s, f = start(tmp_path, "입이 있는 디딤돌이에요.", llm, sid="SYN-G85-BPA")
    v = settle(f)
    assert v["stage"] == "adjusting" and llm.calls == [] and calls(tmp_path) == []
    d = valid5(f)
    assert d["generation"]["promptRoute"] == "none" and d["generation"]["afterNone"]["blockReason"] == "body_part_attachment"


@pytest.mark.parametrize("text,quote", [("팽이처럼 생긴 디딤돌이 있어요.", "팽이처럼"), ("팽이 같은 디딤돌이 있어요.", "팽이"),
                                        ("팽이마냥 생긴 디딤돌이 있어요.", "팽이마냥")])
def test_simile_detail_rejected(offline_rt, text, quote):
    i = text.index("디딤돌이")
    subj = {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [i, i + 4]}
    det = {"en": "conical", "basis": "quote", "quote": quote, "charSpan": [0, len(quote)]}
    rec, _ = propose(offline_rt, text, rw_item(subject=subj, details=[det]))
    d = rec["validation"]["details"][0]
    assert d["accepted"] is False and "simile_detail" in d["rejectReasons"]
    assert rec["status"] == "ok" and "conical" not in rec["shapePromptText"]


def test_direct_shape_detail_accepted_and_generator_simile_recheck(offline_rt):
    text = "뾰족한 디딤돌이 있어요."
    subj = {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [4, 8]}
    rec, _ = propose(offline_rt, text, rw_item(subject=subj, details=[{"en": "pointed", "basis": "quote", "quote": "뾰족한",
                                                                         "charSpan": [0, 3]}]))
    assert rec["status"] == "ok"
    pm = ng._load_prompts()
    n = normalize_confirmed("팽이처럼 생긴 디딤돌이 있어요.")
    bad = {"subject": {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [8, 12]},
           "details": [{"en": "conical", "origin": "grounded", "quote": "팽이처럼", "charSpan": [0, 4]}]}
    assert pm._rewrite_head(n, bad) is None                                     # 생성기 쪽도 비유 구간이면 쓰지 않음


def test_neutral_phrase_text():
    b = json.loads(shared("protocol", "selection_protocol.v0.14.json").read_text(encoding="utf-8"))
    t = b["phrases"]["llm_rewrite_neutral"]
    assert b["protocolVersion"] == "0.14.0" and t["status"] == "draft" and "G85" in t["source"]
    assert t["text"] == ("말씀하신 것에서 모양을 찾지 못해서, 정해 둔 기본 모양으로 그림을 그려 봤어요. 쓰고 싶은 그림이 있으면 골라 주세요. "
                         "색은 보지 말고 모양만 봐 주세요.")


# ── Codex CP21 반영 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("en,reason", [("marble", "english_material"), ("sponge", "english_material"), ("iron", "english_material"),
                                       ("clay", "english_material"), ("cave", "english_scene"), ("hill", "english_scene")])
def test_cp21_1_head_material_and_place(en, reason):
    pm = ng._load_prompts()
    assert reason in pm.rewrite_english_reasons(en, "subject")
    assert pm.rewrite_english_reasons("rock", "subject") == [] and pm.rewrite_english_reasons("stepping stone", "subject") == []


def test_cp21_1_wordnet_place(offline_rt):
    if wnc.info()["status"] != "available":
        pytest.skip("WordNet 없음")
    assert "wordnet_place" in wnc.reasons("pond")[0] and "wordnet_forbidden" not in wnc.reasons("pond")[0]
    rec, _ = propose(offline_rt, T_STEP, rw_item(subject={**SUBJ, "en": "pond"}))
    assert rec["outcome"] == "no_subject" and "wordnet_place" in rec["rejectReasons"] and route(rec) == "system_default"


@pytest.mark.parametrize("text,quote", [("예전에는 디딤돌이었어요.", "디딤돌이었어요"), ("친구가 디딤돌 같대요.", "디딤돌"),
                                        ("디딤돌은 아니에요.", "디딤돌은"), ("디딤돌이면 좋겠어요.", "디딤돌이면")])
def test_cp21_2_generator_recheck_context(offline_rt, text, quote):
    pm = ng._load_prompts()
    n = normalize_confirmed(text)
    spec = offline_rt.scene_builder.build(n, session_id="SYN-G85-U", participant_id="SYN")
    spec = spec if isinstance(spec, dict) else spec.to_dict()
    i = n.index(quote)
    item = {"subject": {"en": "stepping stone", "quote": quote, "charSpan": [i, i + len(quote)]}, "details": []}
    assert pm._rewrite_head(n, item) is not None                     # 글자·영어 검사는 지나도
    p = pm.shape_prompt(n, mapper_spec=spec, llm_rewrite_item=item)   # 문맥 재검증에서 버림(fail closed)
    assert p.get("shapeSource") != "llm_rewrite" and p["rewriteRecheckReasons"]
    p2 = pm.shape_prompt(n, llm_rewrite_item=item)                    # 매퍼 spec 없이도 문맥 규칙은 건다
    assert p2.get("shapeSource") != "llm_rewrite"


def test_cp21_3_raw_text_full_and_sha(offline_rt):
    raw = json.dumps(rw_item(), ensure_ascii=False) + " " * 5000
    rec, _ = propose(offline_rt, T_STEP, raw)
    assert rec["status"] == "ok" and rec["rawText"] == raw and len(rec["rawText"]) > 4000
    assert rec["rawTextSha256"] == lr.sha256_text(raw)


def test_cp21_4_prime_is_separate_fixed_request(offline_rt, monkeypatch):
    from ifs_chatbot.config import LLMConfig
    from ifs_chatbot import llm as llm_mod
    b = llm_mod.OllamaBackend.__new__(llm_mod.OllamaBackend)
    b.cfg, b.host = LLMConfig(), "http://127.0.0.1:1"
    sent = []

    class R:
        status_code = 200
    monkeypatch.setattr(llm_mod.httpx, "post", lambda url, json=None, timeout=None: sent.append(json) or R())
    out = b.prime_context()
    assert out["ok"] is True and sent == [b.warmup_body()]
    assert [m["content"] for m in sent[0]["messages"]] == [lr.PRIME_INPUT]       # 참여자 글이 들어가지 않는 고정 입력

    class P(FakeLLM):
        def __init__(self, reply):
            super().__init__(reply)
            self.primes = 0

        def prime_context(self):                                     # 인자가 없다 — 참여자 글을 넘길 길이 없음
            self.primes += 1
            return {"ok": True, "ms": 1}
    norm = normalize_confirmed(T_STEP)
    spec = offline_rt.scene_builder.build(norm, session_id="SYN-G85-U", participant_id="SYN")
    spec = spec if isinstance(spec, dict) else spec.to_dict()
    be = P(rw_item())
    rec = lr.propose(offline_rt.llm_rewrite_prompt, be, norm, spec, seed=0, timeout_s=5.0, cache={}, flag=None, fresh_context=True)
    assert be.primes == 1 and len(be.calls) == 1 and rec["status"] == "ok"
    cp = rec["contextPrime"]
    assert cp["separateRequest"] is True and cp["input"] == "." and cp["ok"] is True and cp["ms"] == 1
    rec2, _ = propose(offline_rt, T_STEP, rw_item())                    # 기본(세션 밖 호출)은 예열 없음
    assert rec2["contextPrime"] is None


def test_cp21_5_span_repair_ambiguous_and_valid(offline_rt):
    text = "디딤돌이 있고 디딤돌이 또 있어요."
    bad = {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [2, 6]}          # 틀린 위치 + 같은 인용이 두 번
    rec, _ = propose(offline_rt, text, rw_item(subject=bad))
    assert rec["status"] != "ok" and "quote_mismatch" in rec["rejectReasons"]
    good = {"en": "stepping stone", "quote": "디딤돌이", "charSpan": [8, 12]}         # 둘째 것을 정확히 가리킴
    rec, _ = propose(offline_rt, text, rw_item(subject=good))
    assert rec["status"] == "ok" and rec["adopted"]["subject"]["charSpan"] == [8, 12]


def test_cp21_5_participant_view_no_english_ids_paths(tmp_path, fake):
    llm = Dual(g85=rw_item(details=added("round")))
    rt, s, f = start(tmp_path, T_STEP, llm, sid="SYN-G85-PRIV")
    v = settle(f)
    assert v["stage"] == "picking" and v["llmRewriteBasis"]
    blob = json.dumps(v, ensure_ascii=False)
    for needle in ("stepping", "a single", "round stepping", "gray clay", str(tmp_path), str(tmp_path).replace("\\", "/")):
        assert needle not in blob, needle                                    # ('round'는 imagePick.round 키 이름이라 낱말째 보지 않음)
    shown = " ".join(x["text"] for x in (v.get("llmRewriteBasis"), v.get("llmRewriteAdded")) if x)
    assert s.id not in shown and "SYN-" not in shown and not any(c.isascii() and c.isalpha() for c in shown)


# ── (G85 3차 판정) 얼굴 낱말 주어 · 꾸밈 근거 구간 · 다리미 ──────────────────────────────────────
@pytest.mark.parametrize("text", ["입이 커다란 디딤돌 같아요.", "눈이 반짝이는 디딤돌이에요.", "혀가 나온 디딤돌이에요.",
                                  "눈 큰 디딤돌이에요.", "눈이 쌓인 지붕 같아요."])
def test_face_word_subject_blocks(text):
    p = ng._load_prompts().shape_prompt(normalize_confirmed(text))
    assert p["blockReason"] == "body_part_attachment" and "얼굴주어" in p["blockDetail"]       # 눈(雪)도 막힘(예외 없음)


@pytest.mark.parametrize("text", ["다리가 짧은 디딤돌이에요.", "꼬리 모양 디딤돌이에요."])
def test_limb_words_keep_attachment_rule_only(text):
    assert ng._load_prompts().shape_prompt(normalize_confirmed(text))["blockReason"] != "body_part_attachment"


@pytest.mark.parametrize("text,quote,ok,reason", [
    ("뾰족한 디딤돌이 있어요.", "뾰족한", True, None),
    ("디딤돌이 뾰족해요.", "뾰족해요", True, None),
    ("주둥이가 긴 디딤돌이에요.", "긴", False, "detail_other_subject"),
    ("주둥이가 긴 디딤돌이에요.", "주둥이가", False, "detail_no_predicate"),
    ("디딤돌이 있는데 끝이 뾰족해요.", "뾰족해요", False, "detail_other_subject"),
])
def test_detail_must_attach_to_subject(offline_rt, text, quote, ok, reason):
    i = text.index("디딤돌이") if "디딤돌이" in text else text.index("디딤돌")
    q = "디딤돌이" if "디딤돌이" in text else "디딤돌"
    subj = {"en": "stepping stone", "quote": q, "charSpan": [i, i + len(q)]}
    j = text.index(quote)
    det = {"en": "pointed" if "뾰족" in quote else "rounded", "basis": "quote", "quote": quote, "charSpan": [j, j + len(quote)]}
    rec, _ = propose(offline_rt, text, rw_item(subject=subj, details=[det]))
    d = rec["validation"]["details"][0]
    assert d["accepted"] is ok, d
    if reason:
        assert reason in d["rejectReasons"]
    pm = ng._load_prompts()                                                # 생성기 재검증도 같은 판정
    n = normalize_confirmed(text)
    item = {"subject": subj, "details": [{"en": det["en"], "origin": "grounded", "quote": quote, "charSpan": [j, j + len(quote)]}]}
    assert (pm.shape_prompt(n, llm_rewrite_item=item).get("shapeSource") == "llm_rewrite") is ok


def test_dari_mi_in_lexicon():
    p = ng._load_prompts().shape_prompt(normalize_confirmed("울퉁불퉁한 다리미가 있어요."))
    assert p["status"] == "ok" and p["text"].startswith("a single bumpy clothes iron") and p["lexiconVersion"] == "0.3.1"


# ── CP21 재검토: 생성기 재검증도 WordNet 판정 ─────────────────────────────────────────
def test_generator_recheck_wordnet_place_and_forbidden(monkeypatch):
    pm = ng._load_prompts()
    n = normalize_confirmed(T_STEP)
    if wnc.info()["status"] != "available":
        pytest.skip("WordNet 없음")
    pond = {"subject": {**SUBJ, "en": "pond"}, "details": []}                 # 서버 검증 없이 생성기에 바로
    assert pm.rewrite_english_reasons("pond", "subject") == []                 # 목록은 지나가지만
    assert pm._rewrite_head(n, pond) is None                                   # WordNet 장소로 거부
    assert pm._rewrite_head(n, {"subject": {**SUBJ, "en": "newt"}, "details": []}) is None     # 금지 범주
    assert pm._rewrite_head(n, {"subject": dict(SUBJ), "details": []}) is not None
    p = pm.shape_prompt(n, llm_rewrite_item=pond)
    assert p.get("shapeSource") != "llm_rewrite"
    # WordNet을 읽을 수 없으면: 서버도 unavailable이라 적었을 때만 서버처럼 건너뛰고, 아니면 닫힘
    fake_state = {**wnc.state(), "status": "unavailable", "wn": None}
    monkeypatch.setattr(wnc, "state", lambda: fake_state)
    ok = {"subject": dict(SUBJ), "details": []}
    assert pm._rewrite_head(n, ok) is None
    assert pm._rewrite_head(n, {**ok, "wordnet": {"status": "available"}}) is None
    assert pm._rewrite_head(n, {**ok, "wordnet": {"status": "unavailable"}}) is not None


def test_server_adopted_carries_wordnet_status(offline_rt):
    rec, _ = propose(offline_rt, T_STEP, rw_item())
    assert rec["adopted"]["wordnet"]["status"] == wnc.info()["status"]
