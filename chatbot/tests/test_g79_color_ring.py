"""G79: 웹 조절 화면의 색을 색상 고리(72칸) + 채도 단계 + 무채색 견본으로 고르기(값 표 4.0.0, selection 프로토콜 0.11.0,
experiment.toml만). 모든 대사는 합성이다(AGENTS.md 6). LLM·Ollama를 부르지 않는다(G77 쪽은 가짜 백엔드)."""
import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ifs_chatbot.candidates import effective_params, load_table
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.eval.color_bins import ACHROMATIC, COLOR_BIN_RULE, color_bin
from ifs_chatbot.paths import shared
from ifs_chatbot.selection import COLOR_RING_VERSION, SelectionInvalid, ring_hue, ui_config
from ifs_chatbot.simulate import drive

sys.path.insert(0, str(Path(__file__).parent))

WEB = Path(__file__).resolve().parents[1] / "ifs_chatbot" / "web"
V05 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.5.json").read_text(encoding="utf-8")))
T_NONE = "가슴 앞에 둥근 공이 있어요."          # 색을 말하지 않음
T_BLUE = "파란 공이에요."                         # 215°(칸 43), s 0.7(단계 사이)
T_YELLOW = "노란 공이에요."                       # 52°(칸 사이)
T_BLACK = "검은 공이에요."                        # 무채색, 견본에 없는 l
COLOR_WORDS = ("빨강", "빨간", "주황", "노랑", "노란", "초록", "파랑", "파란", "남색", "보라", "분홍", "갈색", "회색", "검정",
               "검은", "흰", "하얀", "하양", "까만", "red", "blue", "green", "yellow")
EVAL_WORDS = ("예쁜", "좋은", "나쁜", "밝은", "어두운", "진한", "연한", "선명", "탁한", "따뜻", "차가운", "예를 들어")


def exp_cfg(tmp_path, **over):
    c = load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "guard.required": False,
        "session.log_dir": str(tmp_path / "logs"), "preview.mode": "none"})
    return c.with_overrides(**over) if over else c


def done(rt, sid, text):
    s = rt.new_session("chatbot", sid)
    drive(s, {"id": sid, "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": text}})
    assert s.state == "done"
    return s


def adjusting(rt, sid, text):
    s = done(rt, sid, text)
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":
        v = f.select(v["candidates"][0]["id"])
    assert v["stage"] == "adjusting"
    return s, f, v


def sel(f):
    d = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    errs = [f"{list(e.path)}: {e.message}" for e in V05.iter_errors(d)]
    assert not errs, errs[:3]
    return d


def color(v):
    return v["current"]["items"]["color"]


@pytest.fixture(scope="module")
def rt(tmp_path_factory):
    return Runtime(exp_cfg(tmp_path_factory.mktemp("g79")))


# ── 값 표·설정·문구 ───────────────────────────────────────────────────────────
def test_table_v4_only_changes_color_item():
    t3, t4 = load_table(shared("lexicon", "candidate_values.v3.json")), load_table(shared("lexicon", "candidate_values.v4.json"))
    assert t4["tableVersion"] == "4.0.0" and t4["changes"][0]["version"] == "4.0.0" and "G79" in t4["changes"][0]["reason"]
    for k in ("defaults", "overrideKeys", "shapeModels", "candidateAxes", "distinctness", "interpretationSplits"):
        assert t4[k] == t3[k], k
    a3, a4 = t3["adjustItems"], t4["adjustItems"]
    assert a4["order"] == a3["order"] and a4["availability"] == a3["availability"]
    assert {k: v for k, v in a4["items"].items() if k != "color"} == {k: v for k, v in a3["items"].items() if k != "color"}
    c = a4["items"]["color"]
    assert c["kind"] == "hue_ring" and c["hueSteps"] == 72 and c["swatches"] == a3["items"]["color"]["swatches"]
    assert c["keys"] == a3["items"]["color"]["keys"] and c["slots"] == a3["items"]["color"]["slots"]
    assert c["screenSwatches"] == ["n10", "n30", "n50", "n70", "n90"]
    assert c["saturationSteps"] == [0.25, 0.4, 0.6, 0.85] and c["saturationSteps"][c["saturationDefaultIndex"]] == 0.6
    assert c["ringLightness"] == 0.5 and c["achromaticBelow"] == 0.10 and "scene_params.v1.json" in c["saturationEvidence"]


def test_every_sixth_step_equals_old_swatch():
    c = load_table(shared("lexicon", "candidate_values.v4.json"))["adjustItems"]["items"]["color"]
    sw = {s["id"]: s for s in c["swatches"]}
    for k in range(12):
        assert ring_hue(6 * k, 72) == sw[f"h{k:02d}"]["h"]
        assert sw[f"h{k:02d}"]["s"] == c["saturationSteps"][c["saturationDefaultIndex"]] and sw[f"h{k:02d}"]["l"] == c["ringLightness"]
    assert len({ring_hue(k, 72) for k in range(72)}) == 72 and ring_hue(71, 72) < 1.0


def test_only_experiment_uses_v4_and_protocol_011():
    exp = load_config("experiment")
    assert exp.selection.table == "candidate_values.v4.json" and exp.selection.protocol == "selection_protocol.v0.11.json"
    for name in ("default", "pilot", "v4", "v4-gen3d", "bridge", "mac8gb"):
        c = load_config(name).selection
        assert c.table != "candidate_values.v4.json" and c.protocol != "selection_protocol.v0.11.json", name


def test_protocol_011_adds_three_draft_phrases_only():
    a = json.loads(shared("protocol", "selection_protocol.v0.10.json").read_text(encoding="utf-8"))
    b = json.loads(shared("protocol", "selection_protocol.v0.11.json").read_text(encoding="utf-8"))
    assert b["protocolVersion"] == "0.11.0" and b["changes"][0]["version"] == "0.11.0" and b["status"] == "draft"
    new = set(b["phrases"]) - set(a["phrases"])
    assert new == {"adjust_color_ring_hint", "adjust_color_ring_value", "adjust_color_saturation_label"}
    assert all(b["phrases"][k] == a["phrases"][k] for k in a["phrases"]) and b["adjustItemLabels"] == a["adjustItemLabels"]
    assert b["premeasure"] == a["premeasure"]
    for k in new:
        p = b["phrases"][k]
        assert p["status"] == "draft" and "연구 책임자 요청 2026-11-28, G79" in p["source"]
        assert not any(w in p["text"] for w in COLOR_WORDS + EVAL_WORDS + ("치료", "진단", "내담자")), k
    assert b["phrases"]["adjust_color_ring_hint"]["text"].endswith("요.")
    assert "{k}" in b["phrases"]["adjust_color_ring_value"]["text"] and "{n}" in b["phrases"]["adjust_color_saturation_label"]["text"]


def test_runtime_loads_protocol_011_and_ui_config(rt):
    assert rt.selection_protocol.version == "0.11.0" and rt.candidate_table["tableVersion"] == "4.0.0"
    ui = ui_config(rt.selection_protocol, rt.candidate_table, {}, True)
    c = next(x for x in ui["adjustItems"] if x["id"] == "color")
    assert c["kind"] == "hue_ring" and [x["id"] for x in c["values"]] == ["n10", "n30", "n50", "n70", "n90"]
    assert c["ring"] == {"hueSteps": 72, "saturationSteps": [0.25, 0.4, 0.6, 0.85]}
    assert ui["phrases"]["adjust_color_ring_hint"] and ui["table"]["tableVersion"] == "4.0.0"


def test_ring_table_needs_ring_phrases_but_old_table_takes_new_protocol(tmp_path):
    # CP18-1: hue_ring 표 + 고리 문구 없는 프로토콜(0.10) → 시작을 멈춤(화면 문구가 빠지므로)
    with pytest.raises(RuntimeError, match="adjust_color_ring_hint"):
        Runtime(exp_cfg(tmp_path, **{"selection.protocol": "selection_protocol.v0.10.json"}))
    # 반대 조합(swatch 표 v3 + 0.11)은 막지 않는다: 쓰지 않는 문구가 있을 뿐이고 프로토콜 판은 기록에 남는다
    rt3 = Runtime(exp_cfg(tmp_path, **{"selection.table": "candidate_values.v3.json"}))
    assert rt3.selection_protocol.version == "0.11.0" and rt3.candidate_table["tableVersion"] == "3.0.0"


def test_releasing_on_current_handle_still_sends_once():
    # CP18-2: 지금 손잡이 자리를 눌렀다 놓아도 adjust를 한 번 보낸다(끄는 동안에는 보내지 않음)
    js = (WEB / "stage.js").read_text(encoding="utf-8")
    body = js[js.index("function colorRing("):js.index("function drawAdjusting(")]
    assert "dragIdx !== idx" not in body and "if (commit && dragIdx >= 0)" in body
    move = body[body.index('addEventListener("pointermove"'):body.index('const end = ')]
    assert "send(" not in move


# ── 서버 검증 ────────────────────────────────────────────────────────────────
def test_hue_steps_0_to_71_accepted(rt):
    s, f, v = adjusting(rt, "SYN-G79-ALL", T_NONE)
    for k in range(72):
        c = color(f.adjust("color", {"hueStep": k}))
        assert c["hueStep"] == k and c["h"] == ring_hue(k, 72) and c["s"] == 0.6 and c["l"] == 0.5 and c["saturationStep"] == 2
    ev = f.data["adjustments"]["events"]
    assert len(ev) == 72 and ev[5]["input"] == {"hueStep": 5}


BAD = [{"hueStep": 72}, {"hueStep": -1}, {"hueStep": 3.0}, {"hueStep": 2.5}, {"hueStep": "3"}, {"hueStep": True},
       {"hueStep": None}, {"hueStep": 3, "l": 0.2}, {}, [], 3, 3.0, None, True, "x99", "said", {"hueStep": "said"},
       {"saturationStep": 4}, {"hueStep": 1, "saturationStep": 1.0}, {"hueStep": 1, "saturationStep": -1},
       {"hueStep": 1, "saturationStep": "said"}, {"hueStep": 1, "saturationStep": 4}]


def test_hue_and_saturation_input_rejected(rt):
    s, f, v = adjusting(rt, "SYN-G79-BAD", T_NONE)                    # 색을 말하지 않은 세션('said' 자리도 없음)
    for bad in BAD:
        with pytest.raises(SelectionInvalid):
            f.adjust("color", bad)
    assert f.data["adjustments"]["events"] == [] and f.data["colorChanged"] is False


def test_saturation_only_needs_a_hue_and_steps_apply(rt):
    s, f, v = adjusting(rt, "SYN-G79-SAT", T_NONE)
    assert color(v)["hueStep"] is None and v["colorRing"]["unspecified"] is True
    with pytest.raises(SelectionInvalid):
        f.adjust("color", {"saturationStep": 0})                        # 고리에 색이 없으면 채도만 바꿀 수 없음
    f.adjust("color", {"hueStep": 30})
    for j, x in enumerate([0.25, 0.4, 0.6, 0.85]):
        c = color(f.adjust("color", {"saturationStep": j}))
        assert c["s"] == x and c["saturationStep"] == j and c["hueStep"] == 30 and c["l"] == 0.5
    c = color(f.adjust("color", {"hueStep": 31}))                       # 채도 단계는 그대로 이어짐
    assert c["saturationStep"] == 3 and c["s"] == 0.85
    c = color(f.adjust("color", "n30"))                                 # 무채색 견본 → 고리 밖
    assert c["hueStep"] is None and c["saturationStep"] is None and c["swatch"] == "n30"
    with pytest.raises(SelectionInvalid):
        f.adjust("color", {"saturationStep": 1})


def test_sixth_step_and_old_swatch_give_same_value(rt):
    s, f, v = adjusting(rt, "SYN-G79-6K", T_NONE)
    for k in range(12):
        a = color(f.adjust("color", {"hueStep": 6 * k, "saturationStep": 2}))
        b = color(f.adjust("color", f"h{k:02d}"))                        # 옛 견본 id도 계속 받음(G77·옛 화면)
        assert a == b and a["swatch"] == f"h{k:02d}" and a["hueStep"] == 6 * k
    assert f.data["adjustments"]["events"][-1]["input"] == "h11"


# ── 말한 색으로 돌아가기(G79-c) ──────────────────────────────────────────────
def test_said_hue_between_steps_can_return(rt):
    s, f, v = adjusting(rt, "SYN-G79-YEL", T_YELLOW)
    said = s.scene_spec["material"]["color"]
    base = effective_params(s.scene_spec, f.defaults)
    c0 = color(v)
    assert said is not None and c0["hueStep"] == "said" and v["colorRing"]["saidHueStep"] == "said"
    assert v["colorRing"]["saidHue"] == c0["h"] and v["colorRing"]["lightness"] == round(base["material.color.l"], 4)
    assert v["colorRing"]["home"] == "said" and v["colorRing"]["unspecified"] is False
    c = color(f.adjust("color", {"hueStep": 10}))
    assert c["hueStep"] == 10 and c["l"] == c0["l"]                     # 명도는 말한 값 유지
    c = color(f.adjust("color", {"hueStep": "said"}))
    assert c["h"] == c0["h"] and c["hueStep"] == "said"
    f.adjust("color", "n90")
    assert color(f.adjust("color", "said")) == c0                       # 말한 색 그대로(Home)
    f.finish()
    d = sel(f)
    assert d["sources"]["material.color"] == "said" and d["colorChanged"] is False
    assert not any(k.startswith("material.color") for k in d["finalOverrides"])     # 되돌아오면 덮어쓰기 없음
    cr = d["colorRing"]
    assert cr["final"]["origin"] == "said" and cr["initial"]["origin"] == "said" and cr["saidPosition"]["hueStep"] == "said"
    assert cr["final"]["saidInputs"] == 1 and cr["final"]["ringInputs"] == 2 and cr["final"]["swatchInputs"] == 1


def test_said_saturation_between_steps_is_an_extra_step(rt):
    s, f, v = adjusting(rt, "SYN-G79-BLUE", T_BLUE)
    c0 = color(v)
    R = v["colorRing"]
    assert c0["hueStep"] == round(c0["h"] * 72) and isinstance(c0["hueStep"], int)    # 215° = 칸 43
    assert c0["saturationStep"] == "said" and [x["step"] for x in R["saturations"]] == [0, 1, 2, "said", 3]
    assert R["saidSaturationStep"] == "said" and R["ringSaturation"] == c0["s"]
    c = color(f.adjust("color", {"saturationStep": 0}))
    assert c["s"] == 0.25 and c["hueStep"] == c0["hueStep"]
    c = color(f.adjust("color", {"saturationStep": "said"}))
    assert c == c0
    c = color(f.adjust("color", {"hueStep": 5}))                        # 채도는 말한 채도 그대로
    assert c["saturationStep"] == "said" and c["s"] == c0["s"] and c["l"] == c0["l"]
    f.finish()
    d = sel(f)
    assert d["sources"]["material.color"] == "edited" and d["sources"]["material.saturation"] == "edited"
    assert d["colorChanged"] is True and d["colorRing"]["final"]["origin"] == "picked"
    assert d["finalOverrides"]["material.color.h"] == ring_hue(5, 72) and "material.color.l" not in d["finalOverrides"]
    ev = [e for e in d["adjustments"]["events"] if e["item"] == "color"]
    assert ev[-1]["input"] == {"hueStep": 5} and ev[-1]["value"]["hueStep"] == 5 and ev[-1]["previous"]["hueStep"] == c0["hueStep"]


def test_said_achromatic_gets_its_own_swatch(rt):
    s, f, v = adjusting(rt, "SYN-G79-BLK", T_BLACK)
    c0, R = color(v), v["colorRing"]
    assert c0["hueStep"] is None and c0["swatch"] is None and R["saidSwatch"]["id"] == "said" and R["atSaid"] is True
    assert R["saidHue"] is None and R["lightness"] == 0.5               # 무채색을 말했으면 고리 명도는 0.5
    c = color(f.adjust("color", {"hueStep": 0}))
    assert c["l"] == 0.5 and c["s"] == 0.6
    assert color(f.adjust("color", "said")) == c0
    with pytest.raises(SelectionInvalid):
        f.adjust("color", {"hueStep": "said"})                           # 고리 위 말한 자리는 없음


# ── 기록: 말하지도 고르지도 않음(G79-d) ───────────────────────────────────────
def test_unspecified_untouched_is_recorded_apart_from_default_gray(rt):
    s, f, v = adjusting(rt, "SYN-G79-UNS", T_NONE)
    R = v["colorRing"]
    assert R["unspecified"] is True and R["home"] is None and color(v)["hueStep"] is None and color(v)["swatch"] == "n70"
    f.finish()
    d = sel(f)
    assert d["sources"]["material.color"] == "default"
    cr = d["colorRing"]
    assert cr["version"] == COLOR_RING_VERSION and cr["exposed"] is True and cr["exposedAt"]
    assert cr["initial"]["origin"] == "unspecified" and cr["final"]["origin"] == "unspecified" and cr["said"] is None
    assert cr["final"]["adjustCount"] == 0


def test_clicking_default_gray_is_picked_not_unspecified(rt):
    s, f, v = adjusting(rt, "SYN-G79-GRAY", T_NONE)
    v = f.adjust("color", "n70")                                         # 기본색과 같은 회색을 직접 고름
    assert v["colorRing"]["unspecified"] is False
    f.finish()
    d = sel(f)
    assert d["sources"]["material.color"] == "default" and d["colorChanged"] is False      # 러너 계약은 G15 규칙 그대로
    assert d["colorRing"]["final"]["origin"] == "picked" and d["colorRing"]["final"]["swatchInputs"] == 1


def test_versions_are_in_the_selection_record(rt):
    s, f, v = adjusting(rt, "SYN-G79-VER", T_BLUE)
    d = sel(f)
    assert d["formatVersion"] == "ifs-selection/0.5"
    assert d["generator"]["tableVersion"] == "4.0.0" and len(d["generator"]["tableSha256"]) == 64
    assert d["protocol"]["protocolVersion"] == "0.11.0" and "phrases.adjust_color_ring_hint" in d["protocol"]["draftKeys"]
    assert d["colorRing"]["tableVersion"] == "4.0.0" and d["colorRing"]["final"] is None
    ev = [e for e in s.log.data["events"] if e.get("type") == "selection:candidates"]
    assert ev and ev[0]["payload"]["tableVersion"] == "4.0.0"


# ── 끈 설정 = 그대로 ─────────────────────────────────────────────────────────
def test_v3_table_session_has_no_ring_keys(tmp_path):
    rt3 = Runtime(exp_cfg(tmp_path, **{"selection.table": "candidate_values.v3.json",
                                       "selection.protocol": "selection_protocol.v0.10.json"}))
    s, f, v = adjusting(rt3, "SYN-G79-V3", T_BLUE)
    assert f.ring is None and "colorRing" not in v and set(color(v)) == {"swatch", "h", "s", "l"}
    with pytest.raises(SelectionInvalid):
        f.adjust("color", {"hueStep": 6})
    f.adjust("color", "h01")
    f.finish()
    d = sel(f)
    assert "colorRing" not in d and all("input" not in e for e in d["adjustments"]["events"])
    assert set(d["adjustments"]["items"]["color"]["last"]) == {"swatch", "h", "s", "l"}
    ui = ui_config(rt3.selection_protocol, rt3.candidate_table, {}, True)
    assert next(x for x in ui["adjustItems"] if x["id"] == "color")["kind"] == "swatch"


# ── G77과의 맞물림 ───────────────────────────────────────────────────────────
def _g77():
    from test_g77_llm_fill import T_COLOR, item, session      # noqa: E402
    return T_COLOR, item, session


V4 = {"selection.table": "candidate_values.v4.json", "selection.protocol": "selection_protocol.v0.11.json"}


def test_llm_quoted_swatch_shows_on_ring_with_note(tmp_path):
    T_COLOR, item, session = _g77()
    rt4, s, llm = session(tmp_path, T_COLOR, [item(T_COLOR, "color", "green", "쑥색")], sid="SYN-G79-LLM", **V4)
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":
        v = f.select(v["candidates"][0]["id"])
    c = color(v)
    assert c["swatch"] == "h04" and c["hueStep"] == 24 and c["saturationStep"] == 2   # 견본 id 제안 → 고리의 칸 24
    assert "color" in v["llmFill"]["items"] and v["colorRing"]["home"] == "h04" and v["colorRing"]["unspecified"] is False
    v = f.adjust("color", {"hueStep": 30})
    assert "color" not in v["llmFill"]["items"]                          # 고치면 안내가 사라짐
    v = f.adjust("color", {"hueStep": 24})
    assert "color" in v["llmFill"]["items"]                              # 처음 칸으로 돌아오면 다시
    f.finish()
    d = sel(f)
    assert d["sources"]["material.color"] == "llm_quoted" and d["llmFill"]["participant"]["color"]["kept"] is True
    assert d["colorRing"]["initial"]["origin"] == "llm_quoted" and d["colorRing"]["final"]["origin"] == "llm_quoted"


def test_flagged_session_puts_no_initial_value_on_ring(tmp_path):
    T_COLOR, item, session = _g77()
    rt4, s, llm = session(tmp_path, T_COLOR, [item(T_COLOR, "color", "green", "쑥색")], sid="SYN-G79-FLAG", **V4)
    s.log.data["alerts"].append({"kind": "crisis", "detail": "합성", "turn": 1, "severity": "critical"})
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":
        v = f.select(v["candidates"][0]["id"])
    d = sel(f)
    assert d["llmFill"]["notApplied"] == {"color": "session_flagged"} and not (v.get("llmFill") or {}).get("items")
    assert color(v)["hueStep"] is None and v["colorRing"]["unspecified"] is True
    assert d["colorRing"]["initial"]["origin"] == "unspecified"


# ── 웹 정적 계약 ─────────────────────────────────────────────────────────────
def test_web_has_no_external_urls_or_libraries():
    for name in ("stage.js", "style.css", "index.html", "app.js"):
        t = (WEB / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://|//cdn|@import|<script[^>]+src=\"http", t), name


def test_ring_markup_uses_protocol_text_and_no_color_names():
    js = (WEB / "stage.js").read_text(encoding="utf-8")
    body = js[js.index("function colorRing("):js.index("function drawAdjusting(")]
    assert 'role: "slider"' in body and "conic-gradient" in body and "pointerup" in body and "setPointerCapture" in body
    assert "shiftKey ? 6 : 1" in body and '"Home"' in body
    assert 'phrase("adjust_color_ring_value")' in body and 'phrase("adjust_color_saturation_label")' in body
    assert 'phrase("adjust_color_ring_hint")' in body
    # 낭독기 글(aria-label·aria-valuetext)은 프로토콜 문구나 항목 이름으로만 만든다
    for m in re.finditer(r'"aria-(?:label|valuetext)"\s*[:,]\s*([^,}\n]+)', body):
        assert "phrase(" in m.group(1) or "it.label" in m.group(1) or "p.text" in m.group(1), m.group(0)
    code = "\n".join(l.split("//")[0] for l in body.splitlines())                    # 주석 밖
    assert not any(w in code for w in COLOR_WORDS + EVAL_WORDS)
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.ring-handle \{[^}]*width: 44px; height: 44px", css)
    assert ".hue-ring:focus-visible" in css and ".chip.unset" in css


# ── 분석용 색 묶음(G79-f) ─────────────────────────────────────────────────────
def test_color_bin_rule():
    assert COLOR_BIN_RULE == "ifs-color-bin/0.1.0"
    assert color_bin(0.5, 0.0) == ACHROMATIC and color_bin(0.5, 0.0999) == ACHROMATIC and color_bin(0.5, 0.10) == "h06"
    c = load_table(shared("lexicon", "candidate_values.v4.json"))["adjustItems"]["items"]["color"]
    for k in range(72):                                                  # 고리 칸 → 가장 가까운 12칸(가운데는 위쪽)
        want = ((k + 3) // 6) % 12
        assert color_bin(ring_hue(k, 72), 0.6) == f"h{want:02d}", k
    for sw in c["swatches"]:
        assert color_bin(sw["h"], sw["s"]) == (ACHROMATIC if sw["s"] < 0.1 else sw["id"])
    assert color_bin(1.0, 0.5) == "h00" and color_bin(0.99, 0.5) == "h00" and color_bin(1 / 24, 0.5) == "h01"
    with pytest.raises(ValueError):
        color_bin(1.2, 0.5)
    with pytest.raises(TypeError):
        color_bin(True, 0.5)


def test_color_bin_not_used_by_screen_or_record():
    for p in (WEB / "stage.js", Path(__file__).resolve().parents[1] / "ifs_chatbot" / "selection.py"):
        assert "color_bin" not in p.read_text(encoding="utf-8") and "colorBin" not in p.read_text(encoding="utf-8")
