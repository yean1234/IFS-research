"""G77: 확정 직후 매퍼가 비운 슬롯을 면담 LLM이 원문 인용과 함께 채운다([mapping] llm_fill). 모든 대사는 합성이다.
LLM은 가짜 백엔드(FakeLLM.structured — 정한 JSON을 돌려줌, 부른 횟수를 셈). Ollama·GPU를 부르지 않는다."""
import json
import re
import sys
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ifs_chatbot import llm_fill as lf
from ifs_chatbot import none_gen as ng
from ifs_chatbot.candidates import generate
from ifs_chatbot.config import MappingConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.llm import BackendError, GenerationResult
from ifs_chatbot.paths import REPO_ROOT, shared

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import T_SHAPE, cfg, done_session, sel_json, wait_stage  # noqa: E402
from test_g75_image_pick import calls, fake  # noqa: E402,F401  (fake = 생성기 대역 환경 fixture)

V05 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.5.json").read_text(encoding="utf-8")))
T_COLOR = "쑥색이에요. 가슴 앞에 있어요."            # 사전 밖 색 낱말(쑥색 — 매퍼 _unmatched·unlisted_noun)
T_ROCK = "돌덩이 같은 게 있어요."                    # 사전 밖 형태 낱말 → 규칙 그림 프롬프트 no_shape_stated
T_CROSS = "무겁고 차가워요."                          # 교차 감각만(매퍼 _unmapped weight·temperature)
T_NEG = "빨갛지는 않아요. 돌덩이예요."               # 부정된 색 + 사전 밖 형태 낱말
T_RED = "빨간 공이에요."                             # 매퍼가 색·형태를 채움
T_SAD = "슬퍼요."
T_HARD = "단단해요."
T_SIMILE = "천처럼 흔들리는 연기예요."
T_PRED_SIMILE = "돌덩이처럼 무거워요."


class FakeLLM:
    """면담 백엔드 대역 + G77 JSON 호출. reply: dict | str | callable(system, user, schema) | Exception."""
    name = "fake-ollama"

    def __init__(self, reply=None, delay=0.0):
        self.reply, self.delay, self.calls = reply, delay, []

    def check(self):
        return True, "ok"

    def info(self):
        return {"name": "fake-model", "digest": "sha256:" + "ab" * 32, "runtime": "test", "quant": None, "sampling": None}

    def warmup(self):
        return None

    def generate(self, req):                       # 면담에는 쓰지 않음(시험 세션은 static 조건)
        raise BackendError("not used")

    def structured(self, system, user, schema, *, seed, timeout_s, temperature=0.0, num_predict=400):
        self.calls.append({"system": system, "user": user, "schema": schema, "seed": seed, "timeout": timeout_s,
                           "temperature": temperature})
        if self.delay:
            time.sleep(self.delay)
        r = self.reply(system, user, schema) if callable(self.reply) else self.reply
        if isinstance(r, Exception):
            raise r
        return GenerationResult(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False), latency_ms=1, meta={})


def item(text, slot, value, quote, evt="attribute_word", span=None):
    s = text.index(quote) if span is None else span[0]
    return {"slot": slot, "value": value, "quote": quote, "charSpan": list(span or [s, s + len(quote)]), "evidenceType": evt}


def lcfg(tmp_path, on=True, pick=False, **over):
    c = cfg(tmp_path).with_overrides(**{"mapping.llm_fill": on, "selection.protocol": "selection_protocol.v0.10.json",
                                         "mapping.llm_fill_timeout_s": 5.0})
    if pick:
        c = c.with_overrides(**{"gen3d.on_none_image_pick": True, "gen3d.on_none_image_rounds": 2,
                                "gen3d.on_none_image_timeout_s": 60.0, "gen3d.on_none_mesh_timeout_s": 60.0})
    return c.with_overrides(**over) if over else c


def session(tmp_path, text, items=None, reply=None, sid="SYN-G77", **kw):
    llm = FakeLLM(reply if reply is not None else {"items": items or []}, delay=kw.pop("delay", 0.0))
    rt = Runtime(lcfg(tmp_path, **kw), backend=llm)
    s = done_session(rt, sid, text)
    return rt, s, llm


def valid5(f):
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.5"
    errs = [f"{list(e.path)}: {e.message}" for e in V05.iter_errors(d)]
    assert not errs, errs[:3]
    return d


def reasons(s):
    return {(r.get("slot"), r.get("quote")): r["reasons"] for r in s.llm_fill["items"]}


# ── 설정·고정 파일 ───────────────────────────────────────────────────────────
def test_flag_only_in_experiment_and_prompt_file_is_draft():
    m = MappingConfig()
    assert m.llm_fill is False and m.llm_fill_timeout_s == 20.0 and m.llm_fill_max_items == 4
    exp = load_config("experiment")
    assert exp.mapping.llm_fill is True and exp.selection.protocol == "selection_protocol.v0.10.json"
    for name in ("default", "pilot", "v4", "v4-gen3d", "bridge", "mac8gb"):
        assert load_config(name).mapping.llm_fill is False, name
    p = lf.FillPrompt()
    assert p.data["status"] == "draft" and p.version == "0.1.0" and p.data["options"]["temperature"] == 0
    assert "layout.distance" not in json.dumps(p.slots) and "verticalOffset" not in json.dumps(p.slots)
    for name, s in p.slots.items():                  # 값 대응이 값 표 단계·견본·값 안에만 있음
        if s["values"] is None:
            continue
        for v in s["values"]:
            assert lf.item_overrides(p, load_table(), name, v)


def load_table():
    from ifs_chatbot.candidates import load_table as lt
    return lt(shared("lexicon", "candidate_values.v3.json"))


def test_protocol_010_adds_one_draft_phrase_only():
    a = json.loads(shared("protocol", "selection_protocol.v0.9.json").read_text(encoding="utf-8"))
    b = json.loads(shared("protocol", "selection_protocol.v0.10.json").read_text(encoding="utf-8"))
    assert b["protocolVersion"] == "0.10.0" and b["changes"][0]["version"] == "0.10.0"
    assert set(b["phrases"]) - set(a["phrases"]) == {"llm_fill_note"}
    assert all(b["phrases"][k] == a["phrases"][k] for k in a["phrases"])
    t = b["phrases"]["llm_fill_note"]
    assert t["status"] == "draft" and "G77" in t["source"] and "{quote}" in t["text"]
    assert not any(w in t["text"] for w in ("치료", "진단", "내담자", "증상", "예를 들어"))


def test_runtime_refuses_protocol_without_note(tmp_path):
    with pytest.raises(RuntimeError, match="llm_fill_note"):
        Runtime(lcfg(tmp_path).with_overrides(**{"selection.protocol": "selection_protocol.v0.9.json"}), backend=FakeLLM())


# ── 끔 = 그대로 ──────────────────────────────────────────────────────────────
def test_flag_off_no_call_and_records_unchanged(tmp_path):
    llm = FakeLLM({"items": [item(T_COLOR, "color", "green", "쑥색")]})
    rt = Runtime(lcfg(tmp_path, on=False), backend=llm)
    assert rt.llm_fill_prompt is None
    s = done_session(rt, "SYN-G77-OFF", T_COLOR)
    assert llm.calls == [] and s.llm_fill is None
    assert not [e for e in s.log.data["events"] if e.get("type") == "scene:llm_fill"]
    f = s.selection()
    f.start()
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.2" and "llmFill" not in d and "llmFillExposed" not in d
    assert "prefill" not in d["candidates"]
    assert generate(s.scene_spec, s.id, f.table) == f.cands            # prefill 인자 없이 같은 출력(바이트 비교는 기존 고정 시험)
    assert "llmFill" not in f.view()
    norm = s.log.data["confirmedText"]
    assert ng.shape_prompt(norm, s.scene_spec) == ng.shape_prompt(norm, s.scene_spec, None)


# ── 성공: 사전 밖 색 낱말 → 처음 값 → 조절 화면 안내 → 그대로 둠 ─────────────────────────
def test_unlisted_color_word_becomes_initial_value_and_kept(tmp_path):
    rt, s, llm = session(tmp_path, T_COLOR, [item(T_COLOR, "color", "green", "쑥색")])
    assert len(llm.calls) == 1
    c = llm.calls[0]
    assert c["temperature"] == 0 and c["seed"] == 0 and c["timeout"] == 5.0
    assert "쑥색이에요" in c["user"] and "color(색)" in c["user"]
    alts = c["schema"]["properties"]["items"]["items"]["anyOf"]
    assert {a["properties"]["slot"]["enum"][0] for a in alts} >= {"color", "brightness", "size", "shape_noun"}
    assert not any("distance" in json.dumps(a) for a in alts)
    rec = s.llm_fill
    assert rec["status"] == "ok" and [a["slot"] for a in rec["adopted"]] == ["color"]
    assert rec["model"]["digest"].startswith("sha256:") and rec["prompt"]["promptVersion"] == "0.1.0"
    assert s.scene_spec["material"]["color"] is None                      # 확정 스펙은 그대로
    f = s.selection()
    v = f.start()
    d = valid5(f)
    sw = next(x for x in f.table["adjustItems"]["items"]["color"]["swatches"] if x["id"] == "h04")
    for cnd in d["candidates"]["candidates"]:
        assert cnd["overrides"]["material.color.h"] == sw["h"] and cnd["sources"]["material.color"] == "llm_quoted"
    assert d["llmFillExposed"] is True and d["llmFill"]["applied"]["color"]["quote"] == "쑥색"
    assert not any(a["slot"] == "material.color" for a in d["candidates"]["axes"])       # 채운 슬롯은 축으로 벌리지 않음
    v = f.select(v["candidates"][0]["id"]) if v["stage"] == "selecting" else v
    assert v["stage"] == "adjusting"
    assert v["llmFill"]["items"]["color"]["text"] == "'쑥색'라고 하셔서 이렇게 해 봤어요. 다르면 고쳐 주세요."
    f.finish()
    d = valid5(f)
    assert d["sources"]["material.color"] == "llm_quoted" and d["sourceDetails"]["material.color"]["llmQuote"]["quote"] == "쑥색"
    assert d["finalOverrides"]["material.color.h"] == sw["h"]                # 러너는 finalOverrides로 그린다
    assert d["llmFill"]["participant"]["color"]["kept"] is True and d["sourceCounts"]["llm_quoted"] == 2
    ev = [e for e in s.log.data["events"] if e.get("type") == "scene:llm_fill"]
    assert ev and ev[0]["payload"]["adopted"] == ["color"]


def test_participant_edit_recorded_and_note_hidden(tmp_path):
    rt, s, llm = session(tmp_path, T_COLOR, [item(T_COLOR, "color", "green", "쑥색")], sid="SYN-G77-EDIT")
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":
        f.select(v["candidates"][0]["id"])
    v = f.adjust("color", "h08")
    assert "color" not in v["llmFill"]["items"]                          # 바꾸면 안내가 사라짐
    v = f.adjust("color", "h04")
    assert "color" in v["llmFill"]["items"]                              # 처음 값으로 돌아오면 다시
    f.adjust("color", "h08")
    f.finish()
    d = valid5(f)
    assert d["sources"]["material.color"] == "edited"
    p = d["llmFill"]["participant"]["color"]
    assert p["edited"] is True and p["kept"] is False and p["final"]["swatch"] == "h08" and p["adjustCount"] == 3


# ── 형태 낱말: 그림 프롬프트 빈자리 메우기 ───────────────────────────────────────────
def test_rock_shape_word_fills_image_prompt(tmp_path, fake):
    rt, s, llm = session(tmp_path, T_ROCK, [item(T_ROCK, "shape_noun", "boulder", "돌덩이", "shape_noun")],
                         sid="SYN-G77-ROCK", pick=True)
    assert s.llm_fill["adopted"][0]["english"] == "boulder"
    f = s.selection()
    f.start()
    v = f.select("none")
    assert v["stage"] == "generating", f.data["generation"]["afterNone"]
    an = f.data["generation"]["afterNone"]
    assert an["llmPromptUsed"] is True and an["prompt"]["shapeSource"] == "llm_quoted"
    assert an["prompt"]["text"].startswith("a single boulder, ") and an["prompt"]["builderVersion"].endswith("+llmquote-0.1.0")
    tok = [t for t in an["prompt"]["tokens"] if t["slot"] != "template"]
    assert tok == [{"en": "boulder", "ko": "돌덩이", "charSpan": [0, 3], "slot": "shape_noun", "lexiconKey": None,
                    "provenance": "llm_quoted"}]
    wait_stage(f)
    assert f.stage == "picking", f.data["generation"]["afterNone"]      # 생성기 대역도 같은 프롬프트를 만듦(llmShapeItems)
    c = calls(tmp_path)[-1]
    assert c["imagePick"]
    d = valid5(f)
    assert d["generation"]["llmPromptUsed"] is True and d["llmFillExposed"] is True
    rows = json.loads(next((tmp_path / "gen3d-out").glob("none-*-img/inputs/sentences.json")).read_text(encoding="utf-8"))
    assert rows[0]["llmShapeItems"] == [{"quote": "돌덩이", "charSpan": [0, 3], "english": "boulder"}]


def test_rule_shape_present_ignores_llm_shape(tmp_path):
    rt, s, llm = session(tmp_path, T_SHAPE, [item(T_SHAPE, "shape_noun", "rope", "실타래", "shape_noun")], sid="SYN-G77-RULE")
    assert "shape_noun" not in s.llm_fill["offeredSlots"]
    assert reasons(s)[("shape_noun", "실타래")][0] == "slot_filled"
    norm = s.log.data["confirmedText"]
    p0 = ng.shape_prompt(norm, s.scene_spec)
    assert ng.shape_prompt(norm, s.scene_spec, [{"quote": "실타래", "charSpan": [3, 6], "english": "rope"}]) == p0


def test_shape_prompt_llm_item_rechecked_fail_closed():
    pm = ng._load_prompts()
    p0 = ng.shape_prompt(T_ROCK)
    assert p0["blockReason"] == "no_shape_stated"
    bad = [{"quote": "돌덩이", "charSpan": [1, 4], "english": "boulder"}]           # 위치가 글자와 다름
    assert ng.shape_prompt(T_ROCK, None, bad) == p0
    bad2 = [{"quote": "돌덩이", "charSpan": [0, 3], "english": "big-boulder!"}]
    assert ng.shape_prompt(T_ROCK, None, bad2) == p0
    ok = ng.shape_prompt(T_ROCK, None, [{"quote": "돌덩이", "charSpan": [0, 3], "english": "Boulder"}])
    assert ok["status"] == "ok" and ok["text"].startswith("a single boulder") and pm.LLM_QUOTED == "llm_quoted"


# ── 검증기 기각 사유 ─────────────────────────────────────────────────────────
CASES = [
    ("quote_mismatch", T_COLOR, item(T_COLOR, "color", "green", "쑥색", span=[1, 3])),
    ("span_excluded", T_CROSS, item(T_CROSS, "color", "dark_gray", "무겁고")),            # 매퍼 _unmapped weight
    ("emotion_or_sense_word", T_CROSS, item(T_CROSS, "texture", "smooth", "차가워요")),   # 교차 감각(온도 → 질감)
    ("emotion_or_sense_word", T_SAD, item(T_SAD, "brightness", "dark", "슬퍼요")),        # 감정어
    ("negated", T_NEG, item(T_NEG, "color", "red", "빨갛지는")),
    ("simile", T_SIMILE, item(T_SIMILE, "texture", "smooth", "천처럼")),                  # 비유 원천의 속성
    ("span_excluded", T_SIMILE, item(T_SIMILE, "texture", "smooth", "천처럼")),           # 매퍼가 형태에서 뺀 비유 매개어
    ("no_noun", T_HARD, item(T_HARD, "shape_noun", "block", "단단해요", "shape_noun")),   # 형용사만
    ("simile_of_predicate", T_PRED_SIMILE, item(T_PRED_SIMILE, "shape_noun", "boulder", "돌덩이", "shape_noun")),
    ("english_banned", T_ROCK, item(T_ROCK, "shape_noun", "stone person", "돌덩이", "shape_noun")),
    ("english_color_size", T_ROCK, item(T_ROCK, "shape_noun", "big boulder", "돌덩이", "shape_noun")),
    ("english_non_shape", T_ROCK, item(T_ROCK, "shape_noun", "heavy boulder", "돌덩이", "shape_noun")),
    ("non_meshable", T_ROCK, item(T_ROCK, "shape_noun", "fog cloud", "돌덩이", "shape_noun")),
    ("english_format", T_ROCK, item(T_ROCK, "shape_noun", "a big round grey boulder", "돌덩이", "shape_noun")),
    ("value_not_allowed", T_COLOR, item(T_COLOR, "color", "olive", "쑥색")),
    ("evidence_pair_not_allowed", T_COLOR, item(T_COLOR, "color", "green", "쑥색", "measure_phrase")),
    ("slot_not_allowed", T_COLOR, item(T_COLOR, "distance", "near", "가슴 앞에")),           # 위치·거리는 대상이 아님
    ("slot_filled", T_RED, item(T_RED, "color", "blue", "빨간")),                             # 매퍼 값은 덮어쓰지 못함
    ("span_covered", T_RED, item(T_RED, "brightness", "bright", "빨간")),
    ("span_not_token_aligned", T_COLOR, item(T_COLOR, "color", "green", "쑥", span=[0, 1]) | {"quote": "쑥"}),
    ("quote_too_long", T_COLOR, item(T_COLOR, "color", "green", "쑥색이에요. 가슴 앞에 있어요")),
    ("malformed", T_COLOR, {"slot": "color", "value": "green", "quote": "쑥색"}),
]


@pytest.mark.parametrize("why,text,it", CASES, ids=[f"{c[0]}-{i}" for i, c in enumerate(CASES)])
def test_validator_rejects(tmp_path, why, text, it):
    rt, s, llm = session(tmp_path, text, [it], sid="SYN-G77-REJ")
    rec = s.llm_fill
    assert rec["status"] == "ok", rec
    assert rec["adopted"] == [] and why in rec["items"][0]["reasons"], rec["items"]


def test_mapper_value_not_overwritten_in_candidates(tmp_path):
    rt, s, llm = session(tmp_path, T_RED, [item(T_RED, "color", "blue", "빨간")], sid="SYN-G77-RED")
    f = s.selection()
    f.start()
    d = valid5(f)
    assert d["llmFill"]["applied"] == {} and d["llmFillExposed"] is False
    assert all("material.color.h" not in c["overrides"] for c in d["candidates"]["candidates"])


def test_one_quote_two_slots_both_dropped_and_duplicates_and_limit(tmp_path):
    two = [item(T_COLOR, "color", "green", "쑥색"), item(T_COLOR, "brightness", "dark", "쑥색이에요")]
    rt, s, llm = session(tmp_path, T_COLOR, two, sid="SYN-G77-TWO")
    assert s.llm_fill["adopted"] == [] and all("multi_slot_quote" in r["reasons"] for r in s.llm_fill["items"])
    t = "쑥색 돌덩이 같아요. 투명하고 작아요."
    dup = [item(t, "color", "green", "쑥색"), item(t, "color", "green", "쑥색"),
           item(t, "shape_noun", "boulder", "돌덩이", "shape_noun"),
           item(t, "opacity", "see_through", "투명하고"), item(t, "size", "small", "작아요")]
    rt, s, llm = session(tmp_path, t, dup, sid="SYN-G77-DUP", **{"mapping.llm_fill_max_items": 1})
    rs = [r["reasons"] for r in s.llm_fill["items"]]
    assert rs[0] == [] and rs[1] == ["slot_duplicate"] and rs[2] == ["over_limit"]
    assert "slot_filled" in rs[3] and "span_covered" in rs[4]          # 매퍼가 채운 투명도·크기
    assert [a["slot"] for a in s.llm_fill["adopted"]] == ["color"]


# ── 부르지 않음·실패 ─────────────────────────────────────────────────────────
def test_no_call_after_crisis_or_check_judgement(tmp_path):
    rt, s, llm = session(tmp_path, T_COLOR, [item(T_COLOR, "color", "green", "쑥색")], sid="SYN-G77-FLAG")
    assert len(llm.calls) == 1
    norm, spec = s.log.data["confirmedText"], s.scene_spec
    for mut in ("alert", "turn", "message"):
        s.llm_fill_cache.clear()
        if mut == "alert":
            s.log.data["alerts"].append({"kind": "soft_check", "detail": "합성", "turn": 1, "severity": "warning"})
        elif mut == "turn":
            s.log.data["alerts"].clear()
            s.log.data["turns"][0]["crisisKeyword"] = True
        else:
            s.log.data["turns"][0]["crisisKeyword"] = False
            s.messages.append({"speaker": "bot", "text": "합성", "kind": "crisis", "source": "fixed:crisis", "i": 0})
        rec = lf.run(s, spec, norm)
        assert rec["status"] == "skipped" and rec["skipReason"] == "session_flagged", mut
    assert len(llm.calls) == 1                                          # 위기·확인 판정 뒤 호출 0


@pytest.mark.parametrize("reply,delay,status", [
    (BackendError("boom"), 0.0, "failed"),
    ("{not json", 0.0, "invalid_output"),
    ({"items": []}, 0.6, "timeout"),
])
def test_failure_or_timeout_keeps_rule_path(tmp_path, reply, delay, status):
    llm = FakeLLM(reply, delay=delay)
    rt = Runtime(lcfg(tmp_path, **{"mapping.llm_fill_timeout_s": 0.3}), backend=llm)
    s = done_session(rt, "SYN-G77-FAIL", T_COLOR)
    assert s.llm_fill["status"] == status and s.llm_fill["adopted"] == []
    f = s.selection()
    f.start()
    d = valid5(f)
    assert d["llmFillExposed"] is False and d["llmFill"]["applied"] == {}
    base = generate(s.scene_spec, s.id, f.table)
    assert [c["overrides"] for c in d["candidates"]["candidates"]] == [c["overrides"] for c in base["candidates"]]


def test_cache_no_second_call(tmp_path):
    rt, s, llm = session(tmp_path, T_COLOR, [item(T_COLOR, "color", "green", "쑥색")], sid="SYN-G77-CACHE")
    rec = lf.run(s, s.scene_spec, s.log.data["confirmedText"])
    assert rec["cached"] is True and rec["adopted"] == s.llm_fill["adopted"] and len(llm.calls) == 1


def test_offline_backend_skips(tmp_path):
    rt = Runtime(lcfg(tmp_path))                                        # offline 대역: JSON 호출 없음
    s = done_session(rt, "SYN-G77-OFFLINE", T_COLOR)
    assert s.llm_fill["status"] == "skipped" and s.llm_fill["skipReason"] == "backend_unsupported"


def test_unavailable_item_not_applied(tmp_path):
    t = "꿀렁꿀렁해요."                                                 # 사전 밖 흉내말(매퍼 _unmatched)
    rt, s, llm = session(tmp_path, t, [item(t, "motion", "swaying", "꿀렁꿀렁해요")], sid="SYN-G77-MOT")
    assert [a["slot"] for a in s.llm_fill["adopted"]] == ["motion"], s.llm_fill["items"]
    f = s.selection()
    f.start()                                                           # 미리보기 image = 정지 그림 → 움직임 항목 꺼짐(G22)
    d = valid5(f)
    assert d["llmFill"]["notApplied"] == {"motion": "unavailable:still_image_preview"} and d["llmFill"]["applied"] == {}


# ── 스키마·러너 대조 ─────────────────────────────────────────────────────────
def test_schema_05_and_runner_lists_agree():
    s5 = json.loads(shared("schemas", "selection.v0.5.json").read_text(encoding="utf-8"))
    assert s5["properties"]["formatVersion"] == {"const": "ifs-selection/0.5"}
    src = (REPO_ROOT / "unity" / "Assets" / "IFS" / "Runtime" / "Placement" / "PlacementSelection.cs").read_text(encoding="utf-8")
    known = re.search(r"KnownFormatVersions\s*=\s*\{([^}]*)\}", src).group(1)
    assert "ifs-selection/0.5" in known
    s05 = re.findall(r'"([a-z_]+)"', re.search(r"SourceValues05\s*=\s*\{([^}]*)\}", src).group(1))
    assert s05 == s5["$defs"]["source"]["enum"]
    fa = json.loads(shared("schemas", "form-asset.v0.json").read_text(encoding="utf-8"))
    assert fa["properties"]["prompt"]["properties"]["tokens"]["items"]["properties"]["provenance"] == {
        "enum": ["llm_quoted"], "description": fa["properties"]["prompt"]["properties"]["tokens"]["items"]["properties"]
        ["provenance"]["description"]}
