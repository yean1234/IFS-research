"""G72 너비·높이·깊이 비율(layout.proportions, 스펙 2.4.0): 매퍼 v2 규칙(scene_params.v2 proportions 표), 스키마,
결과 상태 꼴 / 진행 꼴 구분, 끈 설정의 출력 불변, 조절 화면(값 표 3.0.0)의 축 조절·기록·크기와 함께 쓰기.
모든 대사는 합성이다(AGENTS.md 6)."""
import json

import pytest
from jsonschema import Draft202012Validator

from ifs_chatbot.candidates import effective_params, load_table, proportions_effective
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v2 import BUILDER_ID, BUILDER_ID_PROP, SceneSpecBuilderV2
from ifs_chatbot.scene_spec import check_principles, schema_errors
from ifs_chatbot.selection import SelectionInvalid
from ifs_chatbot.simulate import drive

SEL_SCHEMA = Draft202012Validator(json.loads(shared("schemas", "selection.v0.2.json").read_text(encoding="utf-8")))
SPREAD = {"x": 1.0, "y": 0.3, "z": 1.0, "axisSaid": True}
ELONG = {"x": 0.4, "y": 1.0, "z": 0.4, "axisSaid": False}


@pytest.fixture(scope="module")
def an():
    return Analyzer()


@pytest.fixture(scope="module")
def on(an):
    return SceneSpecBuilderV2(an, proportions_path=shared("lexicon", "scene_params.v2.json"))


@pytest.fixture(scope="module")
def off(an):
    return SceneSpecBuilderV2(an)


def build(b, text):
    spec = b.build(text)
    assert check_principles(spec, normalize_confirmed(text)) == []
    return spec


def prop(spec):
    return spec["layout"]["proportions"]


# ── 매퍼 ────────────────────────────────────────────────────────────────────
def test_test03_wide_mist_is_mist_with_wide_flat_proportions(on):
    s = build(on, "넓게 펼쳐진 안개가 떠오른다")
    assert s["meta"]["specVersion"] == "2.4.0" and s["meta"]["pipeline"]["builder"] == BUILDER_ID_PROP
    assert s["form"]["type"] == "mist"
    p = prop(s)
    assert p == SPREAD and p["x"] > p["y"] and p["z"] > p["y"]
    assert s["motion"]["type"] is None                       # 결과 상태 → 움직임이 아님
    pv = s["_provenance"]["layout.proportions"][0]
    assert pv["trigger"] == "넓게 펼쳐진" and pv["source"] == "phrase_rule"
    assert s["meta"]["pipeline"]["lexicons"]["proportionsTable"].endswith(".proportions@0.1.0")


@pytest.mark.parametrize("text", ["안개가 펼쳐져요", "안개가 넓게 펼쳐져요", "펼쳐지고 있어요"])
def test_progressive_spreading_stays_motion(on, text):
    s = build(on, text)
    assert prop(s) is None and s["motion"]["type"] == "spreading"


@pytest.mark.parametrize("text,want", [
    ("안개가 넓게 펼쳐져 있어요", SPREAD), ("옆으로 퍼진 안개", SPREAD), ("넓적한 돌", SPREAD),
    ("길쭉한 돌이에요", ELONG), ("기다란 돌", ELONG), ("길게 늘어진 천", ELONG),
    ("납작한 안개예요", {"x": 1.0, "y": 0.3, "z": 1.0, "axisSaid": False}),
    ("높이 솟은 기둥", {"x": 0.5, "y": 1.0, "z": 0.5, "axisSaid": True}),
    ("키가 큰 기둥이에요", {"x": 0.5, "y": 1.0, "z": 0.5, "axisSaid": True}),
    ("가로로 긴 막대", {"x": 1.0, "y": 0.4, "z": 0.4, "axisSaid": True}),
    ("세로로 길쭉해요", {"x": 0.4, "y": 1.0, "z": 0.4, "axisSaid": True}),
])
def test_said_axes_fill_proportions(on, text, want):
    assert prop(build(on, text)) == want


def test_elongated_without_direction_leaves_direction_to_renderer(on):
    p = prop(build(on, "길쭉한 돌이에요"))
    assert p["axisSaid"] is False and max(p["x"], p["y"], p["z"]) == 1.0


@pytest.mark.parametrize("text", ["회색 돌이에요", "시간이 길어요", "가슴이 답답해요", "안개가 있어요"])
def test_unsaid_is_null(on, text):
    s = build(on, text)
    assert prop(s) is None and "layout.proportions" not in s["_provenance"]


def test_negated_is_recorded_not_filled(on):
    s = build(on, "납작하지 않아요")
    assert prop(s) is None
    assert [n["lemma"] for n in s["_negated"] if n["category"] == "proportions"] == ["납작"]


def test_background_and_action_simile_do_not_fill(on):
    assert prop(build(on, "넓게 펼쳐진 들판 위에 작은 돌이 있어요")) is None
    # G71: 움직임 비유 절('천이 펄럭이듯이') 안의 말은 형태 비율을 채우지 않는다
    s = build(on, "넓게 펼쳐진 천이 펄럭이듯이 물체가 움직여요")
    assert prop(s) is None


def test_shape_model_word_not_doubled(on):
    """'납작한 덩어리' — 모양 모형(납작 원기둥)이 그려지므로 비율로 한 번 더 납작하게 하지 않고 대안으로 남긴다."""
    s = build(on, "납작한 덩어리")
    assert prop(s) is None
    alt = [a for a in s["_alternatives"] if a["path"] == "layout.proportions"]
    assert alt and alt[0]["reason"] == "lower_priority" and alt[0]["_provenance"][0]["rule"].endswith("+shapeModel(flat)")


def test_first_mention_wins_later_different_is_alternative(on):
    s = build(on, "넓게 펼쳐진 안개가 있어요. 그런데 길쭉해요")
    assert prop(s) == SPREAD
    assert [a["reason"] for a in s["_alternatives"] if a["path"] == "layout.proportions"] == ["later_mention"]


def test_deterministic(on):
    t = "넓게 펼쳐진 안개가 떠오른다"
    assert json.dumps(on.build(t), ensure_ascii=False) == json.dumps(on.build(t), ensure_ascii=False)


def test_off_output_unchanged(off):
    s = build(off, "넓게 펼쳐진 안개가 떠오른다")
    assert s["meta"]["specVersion"] == "2.2.0" and s["meta"]["pipeline"]["builder"] == BUILDER_ID
    assert "proportions" not in s["layout"] and "proportionsTable" not in s["meta"]["pipeline"]["lexicons"]
    assert s["motion"]["type"] == "spreading"                # 끈 설정은 예전처럼 움직임


def test_on_equals_off_apart_from_new_slot_when_no_axis_said(on, off):
    """축을 말하지 않은 글: 켠 출력에서 2.4 표기·새 슬롯만 빼면 끈 출력과 같다."""
    for t in ["회색 돌이에요", "가슴 앞에 연기 같은 게 있어요. 작아요.", "까만 덩어리가 천천히 흔들려요"]:
        a, b = on.build(t), off.build(t)
        assert a["layout"].pop("proportions") is None
        a["meta"]["specVersion"] = b["meta"]["specVersion"]
        a["meta"]["pipeline"]["builder"] = b["meta"]["pipeline"]["builder"]
        a["meta"]["pipeline"]["lexicons"].pop("proportionsTable")
        assert a == b


def test_ext_and_proportions_together(an):
    b = SceneSpecBuilderV2(an, ext_lexicon_path=shared("lexicon", "layer1_lexicon.v2.json"),
                           proportions_path=shared("lexicon", "scene_params.v2.json"))
    s = build(b, "길쭉한 돌이에요")
    assert s["meta"]["specVersion"] == "2.4.0"
    assert s["form"]["aspect"] == "elongated" and prop(s) == ELONG    # aspect는 기록, 렌더는 proportions 우선(Unity)


# ── 스키마 ───────────────────────────────────────────────────────────────────
def test_schema_rules(on, off):
    s = on.build("넓게 펼쳐진 안개가 떠오른다")
    assert schema_errors(s) == []
    bad = json.loads(json.dumps(s))
    del bad["layout"]["proportions"]
    assert schema_errors(bad)                                     # 2.4.0은 키가 있어야 한다(null 포함)
    old = off.build("회색 돌이에요")
    old["layout"]["proportions"] = None
    assert schema_errors(old)                                     # 2.2.0에는 없어야 한다
    big = json.loads(json.dumps(s))
    big["layout"]["proportions"] = {"x": 0.5, "y": 0.3, "z": 0.5, "axisSaid": True}
    assert any("가장 큰 값이 1" in x for x in check_principles(big, normalize_confirmed("넓게 펼쳐진 안개가 떠오른다")))


# ── 조절 화면(값 표 3.0.0) ───────────────────────────────────────────────────
def test_effective_rule():
    assert proportions_effective({"layout.proportions.x": 2.0, "layout.proportions.y": 0.5, "layout.proportions.z": 1.0}) == \
        {"x": 1.0, "y": 0.25, "z": 0.5}
    assert proportions_effective({"layout.proportions.x": 2.0, "layout.proportions.y": 0.25, "layout.proportions.z": 2.0}) == \
        {"x": 1.0, "y": 0.2, "z": 1.0}                            # 0.2 아래는 0.2
    assert proportions_effective({"layout.size": 0.5}) is None


def test_table_v2_params_unchanged():
    t2, t3 = load_table(), load_table(shared("lexicon", "candidate_values.v3.json"))
    spec = {"form": {}, "material": {}, "layout": {}, "motion": {}}
    assert "layout.proportions.x" not in effective_params(spec, t2["defaults"])
    assert effective_params(spec, t3["defaults"])["layout.proportions.x"] == 1.0
    assert t3["adjustItems"]["order"] == ["color", "form", "brightness", "opacity", "size", "width", "height", "depth",
                                          "texture", "motion"]
    assert t2["adjustItems"]["order"] == ["color", "form", "brightness", "opacity", "size", "texture", "motion"]


def exp_cfg(tmp_path):
    return load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "guard.required": False,
        "session.log_dir": str(tmp_path / "logs"), "preview.mode": "none"})


def done(rt, sid, text):
    s = rt.new_session("chatbot", sid)
    drive(s, {"id": sid, "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": text}})
    assert s.state == "done"
    return s


def test_adjust_axes_records_and_size_together(tmp_path):
    rt = Runtime(exp_cfg(tmp_path))
    s = done(rt, "SYN-G72A", "넓게 펼쳐진 안개가 떠오른다")
    assert s.scene_spec["meta"]["specVersion"] == "2.4.0"
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":
        v = f.select(v["candidates"][0]["id"])
    assert v["current"]["items"]["width"] == 1.0 and v["current"]["items"]["height"] == 0.3
    with pytest.raises(SelectionInvalid):
        f.adjust("height", 0.3)                                   # 단계 밖(말한 값은 단계 사이 — 시작 값으로만)
    f.adjust("height", 0.5)
    f.adjust("width", 1.4)                                        # 한 축을 올리면 그 축이 가장 길다
    f.adjust("size", 0.7)
    f.finish()
    d = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    errs = [e.message for e in SEL_SCHEMA.iter_errors(d)]
    assert not errs, errs[:3]
    fo = d["finalOverrides"]
    assert fo["layout.proportions.x"] == 1.4 and fo["layout.proportions.y"] == 0.5 and fo["layout.size"] == 0.7
    assert "layout.proportions.z" not in fo                       # 말한 값 그대로(덮어쓰기 없음)
    pr = d["proportions"]
    assert pr["said"] == SPREAD
    assert pr["axes"]["x"] == {"item": "width", "first": 1.0, "final": 1.4, "edited": True, "count": 1}
    assert pr["axes"]["z"]["edited"] is False and pr["axes"]["z"]["final"] == 1.0
    assert pr["first"] == {"x": 1.0, "y": 0.3, "z": 1.0}
    assert pr["final"] == {"x": 1.0, "y": round(0.5 / 1.4, 4), "z": round(1.0 / 1.4, 4)}
    assert max(pr["final"].values()) == 1.0                       # 가장 긴 변 = 크기(layout.size)가 정함
    det = d["sourceDetails"]["layout.proportions"]
    assert det["source"] == "edited" and det["saidValue"] == SPREAD and det["value"]["axisSaid"] is True
    assert d["sources"]["layout.proportions"] == "edited" and d["sources"]["layout.size"] == "edited"


def test_unsaid_proportions_default_source(tmp_path):
    rt = Runtime(exp_cfg(tmp_path))
    s = done(rt, "SYN-G72B", "가슴 앞에 회색 돌이 있어요.")
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":
        f.select("none")
    f.finish()
    d = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert d["sources"]["layout.proportions"] == "default" and d["sourceDetails"]["layout.proportions"]["value"] is None
    assert d["proportions"]["edited"] is False and d["proportions"]["said"] is None


def test_v4_config_has_no_axis_items(tmp_path):
    rt = Runtime(load_config("v4").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none",
                                                     "session.log_dir": str(tmp_path / "logs"), "preview.mode": "none"}))
    s = done(rt, "SYN-G72C", "넓게 펼쳐진 안개가 떠오른다")
    assert s.scene_spec["meta"]["specVersion"] == "2.2.0"
    f = s.selection()
    f.start()
    assert "proportions" not in f.data
    with pytest.raises(SelectionInvalid):
        f.adjust("width", 1.0) if f.stage == "adjusting" else f._validate("width", 1.0)


def test_posture_sets_direction_of_unsaid_elongation(on):
    """방향을 말하지 않은 길쭉함 + 말한 자세 → 그 방향(기본 세로로 두면 Unity lying 배율과 지워짐)."""
    s = build(on, "길쭉한 게 누워 있어요")
    assert prop(s) == {"x": 1.0, "y": 0.4, "z": 0.4, "axisSaid": True}
    assert s["_provenance"]["layout.proportions"][0]["rule"].endswith("+posture(lying)")
    assert prop(build(on, "길쭉한 돌이 서 있어요"))["y"] == 1.0


def test_bare_soar_is_not_height(on):
    """'뾰족하게 솟아 있고'(끝이 솟음)는 물체 전체의 높이가 아니다 — '솟'은 높이·우뚝·높게와 함께일 때만."""
    assert prop(build(on, "끝이 여러 개로 뾰족하게 솟아 있고, 각진 면마다 빛이 반사돼요.")) is None
