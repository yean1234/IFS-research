"""면담 뒤 데스크톱 단계(selection.py·server.py·preview.py) — 선택·none·건너뜀(G34), 조절 범위·거부, 색 변경 기록(G31),
출처 여섯 가지(G15·G32), 거리 하한 기록(G33), selection.json 스키마(ifs-selection/0.2), 초안 표시, LLM·검증기 호출 0,
기존 엔드포인트 불변, 미리보기 어댑터(가짜 렌더러·가짜 플레이어), 합성 시나리오 1–6단계. 모든 대사는 합성이다."""
import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ifs_chatbot.candidates import candidates_bytes, load_table
from ifs_chatbot.config import MappingConfig, SelectionConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.preview import PreviewService, UnityQueueRenderer
from ifs_chatbot.selection import SelectionError, SelectionInvalid, SelectionProtocol
from ifs_chatbot.server import create_app
from ifs_chatbot.simulate import drive

SCHEMA = json.loads(shared("schemas", "selection.v0.2.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
SCHEMA01 = json.loads(shared("schemas", "selection.v0.1.json").read_text(encoding="utf-8"))   # 이전 기록·러너 쪽 합성 입력
VALIDATOR01 = Draft202012Validator(SCHEMA01)
SIX_SOURCES = {"said", "chosen", "edited", "default", "said_unrendered_chosen", "said_unrendered_default"}
TABLE = load_table()
FAKE_PLAYER = Path(__file__).parent / "fixtures" / "fake_preview_player.py"

T_FORM = "가슴 앞에 연기 같은 게 있어요. 작아요."
T_FEEL = "가슴 안쪽이 답답하고 무거운 느낌이에요."
T_ALL = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 안 움직여요. 불투명해요. 어두워요."
T_MOTION = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 불투명해요. 어두워요."   # 빈 자리 = 움직임 하나
T_LONG = "가슴 안쪽에 길쭉한 게 있어요."                 # 모형이 없는 모양어
T_SQUARE = "목에 네모난 게 걸려 있어요."                  # 모형이 있는 모양어
T_FLOOR = "얼굴 앞에 붙어 있어요."                        # 거리 하한(G33)


def v4_cfg(tmp_path, **over):
    base = {"llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(tmp_path / "logs")}
    base.update(over)
    return load_config("v4").with_overrides(**{**base, "preview.mode": over.get("preview.mode", "none")})


@pytest.fixture
def rt4(tmp_path):
    return Runtime(v4_cfg(tmp_path))


def done_session(rt, sid, text, condition="static"):
    s = rt.new_session(condition, sid)
    drive(s, {"id": sid, "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": text}})
    assert s.state == "done" and s.log.data["endedBy"] == "completed"
    return s


def valid(data, validator=None):
    errs = [e.message for e in (validator or VALIDATOR).iter_errors(json.loads(json.dumps(data, ensure_ascii=False)))]
    assert not errs, errs[:3]


ALL_ITEMS = {i: None for i in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "G13_appearance", "G13_representation"]}


# ── 단계 순서 ────────────────────────────────────────────────────────────────
def test_v4_profile_uses_mapper_v2_and_default_unchanged():
    assert load_config("v4").mapping.mode == "v2" and load_config("v4").selection.enabled
    assert load_config("default").mapping.mode == "v1" and MappingConfig().mode == "v1"
    assert load_config("default").selection.enabled is False and SelectionConfig().enabled is False
    assert load_config("pilot").selection.enabled is False


def test_spec_built_with_v2_in_new_flow(rt4):
    s = done_session(rt4, "SYN-V2", T_FEEL)
    assert s.scene_spec["meta"]["pipeline"]["builder"].startswith("scene-spec-builder-v2")


def test_selection_requires_completed_interview(rt4):
    s = rt4.new_session("static", "SYN-EARLY")
    with pytest.raises(SelectionError):
        s.selection()


def test_selection_disabled_in_default_config(rt):
    s = done_session(rt, "SYN-OFF", T_FEEL)
    with pytest.raises(SelectionError):
        s.selection()
    assert "selection" not in s.view()


def test_start_writes_candidates_and_valid_selection_json(rt4):
    s = done_session(rt4, "SYN-START", T_FEEL)
    f = s.selection()
    v = f.start()
    assert v["stage"] == "selecting" and len(v["candidates"]) == 4
    assert (f.dir / "candidates.json").read_bytes() == candidates_bytes(f.cands)
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["formatVersion"] == "ifs-selection/0.2"
    assert data["candidates"]["displayOrder"] == [c["id"] for c in v["candidates"]]
    valid(data)


def test_start_is_idempotent(rt4):
    s = done_session(rt4, "SYN-IDEM", T_FEEL)
    a = s.selection().start()
    b = s.selection().start()
    assert a["candidates"] == b["candidates"]
    assert sum(1 for e in s.log.data["events"] if e["type"] == "selection:candidates") == 1


def test_g28_determinism_has_two_meanings_through_the_flow(tmp_path):
    """G28 (a) 같은 확정 텍스트 → 같은 spec(정규화 해시)·같은 후보 id·같은 덮어쓰기. 세션 ID가 달라도 성립.
    (b) 표시 순서는 같은 spec과 같은 세션 ID에서만 같다(G20 순환). 세션 ID가 다르면 달라질 수 있다."""
    from ifs_chatbot.candidates import spec_sha256

    def cands(rt, sid):
        s = done_session(rt, sid, T_FEEL)
        c = s.selection().start()
        return s, s.selection_flow.cands, [x["id"] for x in c["candidates"]]

    rt1, rt2 = Runtime(v4_cfg(tmp_path / "a")), Runtime(v4_cfg(tmp_path / "b"))
    s_a, c_a, shown_a = cands(rt1, "SYN-G28-A")
    s_b, c_b, shown_b = cands(rt1, "SYN-G28-B")
    s_a2, c_a2, shown_a2 = cands(rt2, "SYN-G28-A")          # 다른 실행, 같은 세션 ID
    # (a) 세션이 달라도 같은 spec·후보·덮어쓰기
    assert spec_sha256(s_a.scene_spec) == spec_sha256(s_b.scene_spec) == spec_sha256(s_a2.scene_spec)
    key = lambda c: [(x["id"], x["index"], x["overrides"], x["axisValues"]) for x in c["candidates"]]   # noqa: E731
    assert key(c_a) == key(c_b) == key(c_a2)
    assert sorted(shown_a) == sorted(shown_b)
    # (b) 같은 spec + 같은 세션 ID → 같은 표시 순서(기록도 같음)
    assert shown_a == shown_a2 == c_a["displayOrder"] == c_a2["displayOrder"]
    assert s_a.selection_flow.data["candidatesShown"] == s_a2.selection_flow.data["candidatesShown"]
    # (b) 세션 ID가 다르면 순서는 다를 수 있다(이 두 ID는 실제로 다름 — 순환 칸이 다르다)
    assert c_a["orderRule"] != c_b["orderRule"] and shown_a != shown_b


# ── 선택 · 맞는 것이 없다(G23) ─────────────────────────────────────────────────
def test_select_records_display_position(rt4):
    s = done_session(rt4, "SYN-SEL", T_FEEL)
    f = s.selection()
    v = f.start()
    pick = v["candidates"][2]
    v = f.select(pick["id"])
    sel = f.data["selection"]
    assert v["stage"] == "adjusting" and sel["selectedCandidateId"] == pick["id"] and sel["displayPosition"] == 2
    assert sel["none"] is False and sel["operationalId"] == pick["id"]
    assert f.current == pick["overrides"]
    valid(f.data)


def test_select_unknown_or_twice_rejected(rt4):
    s = done_session(rt4, "SYN-SEL2", T_FEEL)
    f = s.selection()
    v = f.start()
    with pytest.raises(SelectionInvalid):
        f.select("c-000000000000")
    f.select(v["candidates"][0]["id"])
    with pytest.raises(SelectionError):
        f.select(v["candidates"][1]["id"])


def test_none_proceeds_with_baseline_candidate(rt4):
    s = done_session(rt4, "SYN-NONE", T_FEEL)
    f = s.selection()
    f.start()
    f.select("none")
    sel = f.data["selection"]
    assert sel["selectedCandidateId"] is None and sel["selectedIndex"] is None and sel["none"] is True
    assert sel["operationalIndex"] == 0 and sel["operationalId"] == f.cands["candidates"][0]["id"]
    assert f.current == {}
    f.finish()
    assert all(v["source"] != "chosen" for v in f.data["sourceDetails"].values())
    f.submit_premeasure(dict(ALL_ITEMS, A1=4))
    pm = json.loads((f.dir / "premeasure.json").read_text(encoding="utf-8"))
    assert pm["selectionNone"] is True
    valid(f.data)


@pytest.mark.parametrize("text", [T_ALL, T_MOTION])
def test_single_distinct_candidate_skips_selection(rt4, text):
    """G34: 구별되는 후보가 하나뿐이면(빈 자리 없음 / 움직임만 비어 정지 미리보기에서 구별 안 됨) 선택 단계 없이 조절로 간다.
    selection = {selectedCandidateId: null, none: false, skipped: true}, 보여 준 후보 없음, 고른 것이 없으니 chosen 0."""
    s = done_session(rt4, f"SYN-SKIP-{len(text)}", text)
    f = s.selection()
    v = f.start()
    assert v["stage"] == "adjusting" and v["skipped"] is True and len(v["candidates"]) == 1
    sel = f.data["selection"]
    assert sel["selectedCandidateId"] is None and sel["none"] is False and sel["skipped"] is True
    assert sel["skipReason"] == "single_distinct_candidate" and sel["operationalIndex"] == 0
    assert f.data["candidatesShown"] == [] and f.data["candidatesShownAt"] is None
    assert f.cands["selectionStep"] == "skip"
    with pytest.raises(SelectionError):
        f.select(v["candidates"][0]["id"])                  # 선택 단계가 없다
    with pytest.raises(SelectionError):
        f.select("none")
    valid(f.data)
    f.finish()
    assert f.data["finalOverrides"] == {} and f.data["sourceCounts"]["chosen"] == 0
    types = [e["type"] for e in s.log.data["events"]]
    assert types == ["selection:candidates", "selection:skipped", "selection:adjusted"]
    saved = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    valid(saved)
    assert runner_contract_errors(saved) == []


def test_motion_only_skip_records_removed_candidates(rt4):
    s = done_session(rt4, "SYN-SKIP-MOT", T_MOTION)
    f = s.selection()
    f.start()
    assert f.cands["distinct"]["gridCount"] == 4 and len(f.cands["distinct"]["removed"]) == 3
    assert all(r["rules"] == ["still_preview_motion"] for r in f.cands["distinct"]["removed"])
    ev = next(e for e in s.log.data["events"] if e["type"] == "selection:candidates")
    assert ev["payload"]["selectionStep"] == "skip" and ev["payload"]["distinctRemoved"] == 3
    f.finish()
    assert f.data["sources"]["motion.type"] == "default"


# ── 조절(G10·G22) ─────────────────────────────────────────────────────────────
def started(rt, sid, text=T_FEEL, pick=0):
    s = done_session(rt, sid, text)
    f = s.selection()
    v = f.start()
    if v["stage"] == "selecting":                     # 구별되는 후보가 하나면 이미 조절 단계(G34)
        f.select(next(c["id"] for c in v["candidates"] if c["index"] == pick))
    return s, f


@pytest.mark.parametrize("item,value", [("form", "shell"), ("color", "h03"), ("color", "n10"), ("brightness", 0.875),
                                        ("opacity", 0.4), ("size", 0.2), ("texture", 0.9), ("motion", "pounding")])
def test_adjust_accepts_table_values(rt4, item, value):
    _, f = started(rt4, f"SYN-ADJ-{item}-{str(value).replace('.', '')}")
    v = f.adjust(item, value)
    cur = v["current"]["items"][item]
    if item == "color":
        assert cur["swatch"] == value
    else:
        assert cur == value
    assert v["adjustCounts"][item] == 1


T_SCATTER = "가슴 앞에 연기가 흩어져요."   # motion.type = scattering(조절 표의 움직임 값 목록에 없음)


def test_said_value_outside_table_is_added_to_adjust_list(rt4):
    """말한 움직임 값이 표의 목록에 없으면 그 값을 이 세션의 목록 끝에 더해 현재 값으로 보인다(더한 사실은 기록).
    다른 값을 골랐다가 말한 값으로 돌아올 수 있고, 말하지 않은 표 밖 값은 여전히 거부한다."""
    s, f = started(rt4, "SYN-EXTRA", T_SCATTER)
    table_vals = TABLE["adjustItems"]["items"]["motion"]["values"]
    assert s.scene_spec["motion"]["type"] == "scattering" and "scattering" not in table_vals
    v = f.view()
    assert v["adjustExtras"] == {"motion": "scattering"}
    assert v["current"]["items"]["motion"] == "scattering"
    assert f.item_values("motion") == table_vals + ["scattering"]
    assert f.data["adjustValueExtras"] == {"motion": {"slot": "motion.type", "value": "scattering",
                                                      "reason": "said_value_not_in_table"}}
    ev = next(e for e in s.log.data["events"] if e["type"] == "selection:candidates")
    assert ev["payload"]["adjustValueExtras"] == ["motion"]
    f.adjust("motion", "floating")
    assert f.view()["current"]["items"]["motion"] == "floating"
    f.adjust("motion", "scattering")                        # 말한 값으로 돌아옴
    with pytest.raises(SelectionInvalid):
        f.adjust("motion", "spreading")                     # 말하지 않은 표 밖 값
    f.finish()
    assert f.data["sourceDetails"]["motion.type"]["source"] == "said" and "motion.type" not in f.data["finalOverrides"]
    valid(f.data)


def test_same_rule_for_other_category_items(tmp_path):
    """형태도 같은 규칙: 표에서 mist를 뺀 표로 '연기'(form.type = mist)를 말한 세션을 만들면 mist가 형태 목록에 더해진다."""
    import copy
    rt = Runtime(v4_cfg(tmp_path))
    table = copy.deepcopy(rt.candidate_table)
    table["adjustItems"]["items"]["form"]["values"] = ["blob", "shell", "fragments"]
    rt.candidate_table = table
    s, f = started(rt, "SYN-EXTRA-FORM", T_FORM)
    assert s.scene_spec["form"]["type"] == "mist"
    assert f.view()["adjustExtras"] == {"form": "mist"} and f.item_values("form")[-1] == "mist"
    assert f.view()["current"]["items"]["form"] == "mist"
    f.adjust("form", "shell")
    f.adjust("form", "mist")
    valid(f.data)


@pytest.mark.parametrize("n,text", [(1, T_FEEL), (2, T_ALL), (3, T_FORM)])
def test_no_extra_values_when_said_values_are_on_table(rt4, n, text):
    _, f = started(rt4, f"SYN-NOEX-{n}", text)
    assert f.view()["adjustExtras"] == {} and f.data["adjustValueExtras"] == {}


def test_web_panel_appends_extra_value():
    web = (REPO_ROOT / "chatbot" / "ifs_chatbot" / "web" / "stage.js").read_text(encoding="utf-8")
    assert "adjustExtras" in web


@pytest.mark.parametrize("item", ["layout.distance", "distance", "position", "layout.verticalOffset", "verticalOffset",
                                  "shapeModel", "speed", "erosion", "posture", "hue"])
def test_adjust_rejects_items_outside_g10(rt4, item):
    _, f = started(rt4, f"SYN-REJ-{item.replace('.', '')}")
    with pytest.raises(SelectionInvalid):
        f.adjust(item, 0.5)
    assert f.data["adjustments"]["events"] == []


@pytest.mark.parametrize("item,value", [("size", 0.95), ("size", 0.55), ("size", -0.1), ("opacity", 0.1), ("opacity", 0.0),
                                        ("brightness", 0.3), ("texture", 1.2), ("size", "0.5"), ("size", True),
                                        ("form", "cube"), ("form", 1), ("motion", "rotating"), ("motion", "approaching"),
                                        ("color", "red"), ("color", 0.5), ("color", "#ff0000")])
def test_adjust_rejects_values_outside_table(rt4, item, value):
    _, f = started(rt4, f"SYN-BAD-{item}-{abs(hash(str(value))) % 10000}")
    with pytest.raises(SelectionInvalid):
        f.adjust(item, value)


def test_adjust_out_of_order(rt4):
    s = done_session(rt4, "SYN-ORD", T_FEEL)
    f = s.selection()
    f.start()
    with pytest.raises(SelectionError):
        f.adjust("size", 0.3)
    f.select("none")
    f.finish()
    with pytest.raises(SelectionError):
        f.adjust("size", 0.3)
    with pytest.raises(SelectionError):
        f.finish()


# ── 색 변경 기록(G31) ─────────────────────────────────────────────────────────
def test_adjust_items_put_color_first():
    """G31: 조절 화면에서 색이 맨 앞. 값 표·서버 상수·화면 설정이 같은 순서."""
    from ifs_chatbot.selection import ITEMS
    assert TABLE["adjustItems"]["order"][0] == "color" and list(ITEMS) == TABLE["adjustItems"]["order"]


@pytest.mark.parametrize("steps,expect", [([], False), ([("color", "h03")], True), ([("color", "h03"), ("color", "n70")], False),
                                          ([("color", "h03"), ("color", "h05")], True), ([("size", 0.3)], False)])
def test_color_changed_compares_first_and_last(rt4, steps, expect):
    """colorChanged = 조절 기록에서 색의 처음 값과 마지막 값이 다름. 기본 회색(n70)으로 되돌리면 false(횟수는 남음)."""
    _, f = started(rt4, f"SYN-CC-{len(steps)}-{abs(hash(str(steps))) % 10000}", T_FEEL)
    for item, value in steps:
        f.adjust(item, value)
    assert f.view()["colorChanged"] is expect
    f.finish()
    assert f.data["colorChanged"] is expect
    saved = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert saved["colorChanged"] is expect
    if any(i == "color" for i, _ in steps):
        assert saved["adjustments"]["items"]["color"]["count"] == sum(1 for i, _ in steps if i == "color")
    valid(saved)


# ── 모형이 없는 모양어(G32) ───────────────────────────────────────────────────
def test_unrendered_shape_chosen_gets_new_source(rt4):
    """'길쭉'(모형 없음) → 형태 후보가 벌어지고, 후보를 고르면 형태 출처는 chosen이 아니라 said_unrendered_chosen. 말한 낱말은 기록에 남는다."""
    s, f = started(rt4, "SYN-UNR-C", T_LONG, pick=2)
    assert f.cands["axes"][0]["slot"] == "form.type" and f.cands["axes"][0]["reason"] == "said_unrendered"
    f.finish()
    rec = f.data["sourceDetails"]["form.type"]
    assert rec["source"] == "said_unrendered_chosen" and rec["value"] == "mist" and rec["chosenValue"] == "mist"
    assert [w["lemma"] for w in rec["saidWords"]] == ["길쭉"] and rec["saidWords"][0]["shape"] == "elongated"
    assert f.data["sources"]["layout.size"] == "chosen"            # 다른 축은 그대로 chosen
    assert f.data["sourceCounts"]["said_unrendered_chosen"] == 1 and sum(f.data["sourceCounts"].values()) == 16
    valid(f.data)
    assert runner_contract_errors(json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))) == []


def test_unrendered_shape_baseline_pick_is_also_said_unrendered_chosen(rt4):
    _, f = started(rt4, "SYN-UNR-C0", T_LONG, pick=0)
    f.finish()
    assert f.data["sources"]["form.type"] == "said_unrendered_chosen" and f.data["sourceDetails"]["form.type"]["value"] == "blob"


def test_unrendered_shape_none_gets_default_variant(rt4):
    """맞는 것이 없다 → 고른 것이 없으니 기본 형태로 그려지고 출처는 said_unrendered_default(말한 낱말은 남음)."""
    s = done_session(rt4, "SYN-UNR-N", T_LONG)
    f = s.selection()
    f.start()
    f.select("none")
    f.finish()
    rec = f.data["sourceDetails"]["form.type"]
    assert rec["source"] == "said_unrendered_default" and rec["value"] == "blob" and rec["saidWords"][0]["lemma"] == "길쭉"
    valid(f.data)


def test_unrendered_shape_edited_form_is_edited(rt4):
    """조절로 형태를 고치면 다른 슬롯처럼 edited(말한 낱말은 saidWords에 그대로)."""
    _, f = started(rt4, "SYN-UNR-E", T_LONG, pick=0)
    f.adjust("form", "shell")
    f.finish()
    rec = f.data["sourceDetails"]["form.type"]
    assert rec["source"] == "edited" and rec["value"] == "shell" and rec["saidWords"][0]["lemma"] == "길쭉"


def test_rendered_shape_keeps_form_as_said(rt4):
    """모형이 있는 모양어('네모난' → Cube)는 형태 자리를 벌리지 않고 말한 자리로 둔다(출처 said, 모양어는 saidWords)."""
    _, f = started(rt4, "SYN-SQ", T_SQUARE)
    assert "form.type" not in [a["slot"] for a in f.cands["axes"]]
    f.finish()
    rec = f.data["sourceDetails"]["form.type"]
    assert rec["source"] == "said" and rec["saidWords"][0]["shape"] == "square"
    valid(f.data)


# ── 거리 하한(G33) ─────────────────────────────────────────────────────────────
def test_distance_floor_records_said_and_drawn(rt4):
    """매퍼 v2가 거리를 하한으로 올리면 selection.json에 말한 값과 그려진 값을 둘 다 적는다(spec은 그대로)."""
    s, f = started(rt4, "SYN-FLOOR", T_FLOOR)
    assert s.scene_spec["layout"]["distance"] == 0.1
    fl = f.data["distanceFloor"]
    assert fl["said"] == 0.0 and fl["drawn"] == 0.1 and fl["floor"] == 0.1 and fl["rule"].endswith("+floor(0.1;said=0.0)")
    f.finish()
    rec = f.data["sourceDetails"]["layout.distance"]
    assert rec["source"] == "said" and rec["value"] == 0.1 and rec["saidValue"] == 0.0
    assert "layout.distance" not in f.data["finalOverrides"]
    ev = next(e for e in s.log.data["events"] if e["type"] == "selection:candidates")
    assert ev["payload"]["distanceFloor"]["said"] == 0.0
    valid(f.data)


def test_no_distance_floor_record_without_floor(rt4):
    _, f = started(rt4, "SYN-NOFLOOR", T_FEEL)
    assert f.data["distanceFloor"] is None


# ── 출처(G15 네 가지 + G32 두 가지) ─────────────────────────────────────────────
def test_said_then_edited_keeps_said_value(rt4):
    """말한 크기를 조절로 바꾸면 edited이고, 원래 말한 값도 기록에 남는다."""
    s, f = started(rt4, "SYN-EDIT", T_FORM)
    said_size = s.scene_spec["layout"]["size"]
    assert said_size is not None
    f.adjust("size", 0.6)
    f.finish()
    rec = f.data["sourceDetails"]["layout.size"]
    assert rec["source"] == "edited" and rec["saidValue"] == said_size and rec["value"] == 0.6
    assert f.data["finalOverrides"]["layout.size"] == 0.6
    assert f.data["adjustments"]["items"]["size"]["first"] == round(said_size, 4)
    assert f.data["sourceDetails"]["form.type"]["source"] == "said"
    valid(f.data)


def test_touched_then_reverted_keeps_original_source(rt4):
    s, f = started(rt4, "SYN-REV", T_FORM)
    said_size = round(s.scene_spec["layout"]["size"], 4)
    f.adjust("size", 0.3)
    f.adjust("size", 0.7)
    f.finish()
    assert f.data["sourceDetails"]["layout.size"]["source"] == "edited"   # 처음 값과 다름
    s2, f2 = started(rt4, "SYN-REV2", T_FEEL)
    f2.adjust("motion", "trembling")
    f2.adjust("motion", "still")
    f2.finish()
    assert f2.data["sourceDetails"]["motion.type"]["source"] == "default"
    assert f2.data["adjustments"]["items"]["motion"]["count"] == 2
    assert "motion.type" not in f2.data["finalOverrides"]
    assert said_size != 0.7


def test_chosen_and_default_sources(rt4):
    s, f = started(rt4, "SYN-CHO", T_FEEL, pick=3)
    f.finish()
    src = f.data["sourceDetails"]
    assert src["form.type"]["source"] == "chosen" and src["form.type"]["value"] == "mist"
    assert src["layout.size"]["source"] == "chosen" and src["layout.size"]["chosenValue"] == 0.7
    assert src["material.color"]["source"] == "default" and src["material.color"]["value"] == {"h": 0.0, "s": 0.0, "l": 0.7}
    assert src["body.part"]["source"] == "said"
    assert sum(f.data["sourceCounts"].values()) == 16
    assert f.data["finalOverrides"] == {"form.type": "mist", "layout.size": 0.7}


def test_color_edit_sets_three_keys_and_saturation_edited(rt4):
    _, f = started(rt4, "SYN-COL", T_FEEL)
    f.adjust("color", "h07")
    f.finish()
    fo = f.data["finalOverrides"]
    assert fo["material.color.h"] == 0.5833 and fo["material.color.s"] == 0.6 and fo["material.color.l"] == 0.5
    assert f.data["sourceDetails"]["material.color"]["source"] == "edited"
    assert f.data["sourceDetails"]["material.saturation"]["source"] == "edited"


def test_final_overrides_are_flat_unity_object(rt4):
    _, f = started(rt4, "SYN-FLAT", T_FEEL, pick=3)
    for item, val in (("brightness", 0.25), ("opacity", 0.6), ("texture", 0.1), ("motion", "floating")):
        f.adjust(item, val)
    f.finish()
    fo = f.data["finalOverrides"]
    assert isinstance(fo, dict) and fo
    for k, v in fo.items():
        assert k in TABLE["overrideKeys"]["numeric"] + TABLE["overrideKeys"]["categorical"]
        assert (isinstance(v, str)) or (0 <= v <= 1)
    assert not ({"layout.distance", "layout.verticalOffset", "shapeModel"} & set(fo))


def test_schema_blocks_distance_override(rt4):
    _, f = started(rt4, "SYN-SCH", T_FEEL)
    f.finish()
    bad = json.loads(json.dumps(f.data))
    bad["finalOverrides"]["layout.distance"] = 0.2
    assert list(VALIDATOR.iter_errors(bad))


def test_final_returns_original_spec_unchanged(rt4):
    s, f = started(rt4, "SYN-FIN", T_FORM)
    before = json.dumps(s.scene_spec, ensure_ascii=False, sort_keys=True)
    with pytest.raises(SelectionError):
        f.final()
    f.adjust("size", 0.8)
    f.finish()
    out = f.final()
    assert json.dumps(out["spec"], ensure_ascii=False, sort_keys=True) == before
    assert out["selection"]["finalOverrides"]["layout.size"] == 0.8
    spec_file = Path(s.log.data["sceneSpec"]["path"])
    assert "_provenance" in json.loads(spec_file.read_text(encoding="utf-8"))
    import hashlib
    assert out["selection"]["specSha256"] == hashlib.sha256(spec_file.read_bytes()).hexdigest()
    assert out["selection"]["spec"]["sha256Basis"] == "file" and out["selection"]["spec"]["normalizedSha256"]


# ── 러너에 넘기는 spec 해시(G26, CP9 지적 1) ─────────────────────────────────────
def test_spec_file_bytes_are_the_serialized_bytes_on_every_os(rt4, tmp_path):
    """spec 파일은 dumps(spec)의 UTF-8 바이트 그대로(LF, BOM 없음) 쓴다. Windows write_text의 CRLF 변환 때문에 같은 spec이
    OS에 따라 다른 sha256이 되던 경로를 막았다. 쓰는 쪽(챗봇)과 읽는 쪽(러너: 파일 바이트 sha256)이 같은 바이트를 본다."""
    import hashlib
    from ifs_chatbot.scene_builder import spec_bytes, write_spec
    s, f = started(rt4, "SYN-LF", T_FORM)
    raw = Path(s.log.data["sceneSpec"]["path"]).read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    assert raw == spec_bytes(s.scene_spec)
    assert f.data["specSha256"] == hashlib.sha256(raw).hexdigest()
    # 같은 spec을 다른 곳에 다시 써도, /final 응답의 spec을 다시 직렬화해도 같은 바이트(같은 해시)
    again = write_spec(json.loads(raw.decode("utf-8")), tmp_path / "copy" / "spec.json").read_bytes()
    assert again == raw
    f.finish()
    assert spec_bytes(f.final()["spec"]) == raw
    # 선택 기록도 LF로 쓴다
    assert b"\r" not in (f.dir / "selection.json").read_bytes()


def test_runner_ready_only_with_spec_file_and_after_finish(rt4):
    from ifs_chatbot.selection import BLOCK_NOT_FINISHED
    s, f = started(rt4, "SYN-READY", T_FEEL)
    assert f.data["runnerReady"] is False and f.data["runnerBlockers"] == [BLOCK_NOT_FINISHED]
    valid(f.data)
    f.finish()
    assert f.data["runnerReady"] is True and f.data["runnerBlockers"] == []
    out = f.final()
    assert out["runnerReady"] is True and out["runnerBlockers"] == []
    assert out["specPath"] == s.log.data["sceneSpec"]["path"] and out["selectionPath"].endswith("selection.json")
    saved = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert saved["runnerReady"] is True and saved["spec"]["sha256Basis"] == "file"
    assert runner_contract_errors(saved) == []
    valid(saved)


def test_run_without_spec_file_is_marked_not_for_runner(tmp_path):
    """persist_logs = False(파일을 쓰지 않는 실행): specSha256은 null, sha256Basis none, /final과 기록에 runnerReady false와 이유."""
    from ifs_chatbot.selection import BLOCK_NO_SPEC_FILE
    rt = Runtime(v4_cfg(tmp_path), persist_logs=False)
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-NOFILE", T_FEEL)
    assert s.log.data["sceneSpec"]["path"] is None
    c.post("/api/sessions/SYN-NOFILE/candidates")
    c.post("/api/sessions/SYN-NOFILE/selection", json={"candidateId": "none"})
    assert c.post("/api/sessions/SYN-NOFILE/adjust/finish").json()["runnerReady"] is False
    fin = c.get("/api/sessions/SYN-NOFILE/final").json()
    assert fin["runnerReady"] is False and fin["runnerBlockers"] == [BLOCK_NO_SPEC_FILE]
    assert fin["specPath"] is None and fin["selectionPath"] is None
    sel = fin["selection"]
    assert sel["specSha256"] is None and sel["spec"]["sha256Basis"] == "none" and sel["runnerReady"] is False
    assert sel["runnerBlockers"] == [BLOCK_NO_SPEC_FILE]
    valid(sel)
    assert {"specSha256", "runnerReady"} <= set(runner_contract_errors(sel))
    assert not (tmp_path / "logs" / "selection").exists()


def test_changed_spec_file_blocks_runner(rt4):
    from ifs_chatbot.selection import BLOCK_SPEC_FILE_CHANGED
    s = done_session(rt4, "SYN-CHG", T_FEEL)
    p = Path(s.log.data["sceneSpec"]["path"])
    d = json.loads(p.read_text(encoding="utf-8"))
    d["form"]["type"] = "shell"                       # 확정 뒤 파일이 바뀐 경우(합성)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    f = s.selection()
    f.start()
    f.select("none")
    f.finish()
    assert f.data["specSha256"] is None and f.data["spec"]["sha256Basis"] == "none"
    assert f.data["runnerReady"] is False and f.data["runnerBlockers"] == [BLOCK_SPEC_FILE_CHANGED]
    valid(f.data)


def test_schema_ties_runner_ready_to_file_hash(rt4):
    _, f = started(rt4, "SYN-SCH2", T_FEEL)
    f.finish()
    ok = json.loads(json.dumps(f.data))
    valid(ok)
    for mutate in (lambda d: d.update(specSha256=None),                              # 준비됐다면서 해시 없음
                   lambda d: d["spec"].update(sha256Basis="serialized"),             # 준비됐다면서 파일 기준 아님
                   lambda d: d.update(runnerBlockers=["x"]),                         # 준비됐다면서 막는 이유
                   lambda d: d.update(runnerReady=False, runnerBlockers=[]),         # 안 됐다면서 이유 없음
                   lambda d: d["sources"].update({"form.shape": "said"}),            # 모르는 슬롯
                   lambda d: d["sources"].update({"layout.size": "chosne"})):        # 모르는 출처 값
        d = json.loads(json.dumps(ok))
        mutate(d)
        assert list(VALIDATOR.iter_errors(d)), d


# ── 사전 측정 ────────────────────────────────────────────────────────────────
def test_premeasure_validation_and_record(rt4):
    _, f = started(rt4, "SYN-PM", T_FEEL)
    with pytest.raises(SelectionError):
        f.premeasure_view()
    f.finish()
    pv = f.premeasure_view()
    assert [i["id"] for i in pv["items"]] == list(ALL_ITEMS) and pv["scale"]["min"] == 1 and pv["scale"]["max"] == 7
    for bad in ({"A1": 4}, dict(ALL_ITEMS, A1=8), dict(ALL_ITEMS, A1=0), dict(ALL_ITEMS, A1=True), dict(ALL_ITEMS, A1="4"),
                dict(ALL_ITEMS, A1=3.5), dict(ALL_ITEMS, X9=3)):
        with pytest.raises(SelectionInvalid):
            f.submit_premeasure(bad)
    good = {k: (i % 7) + 1 for i, k in enumerate(ALL_ITEMS)}
    good["A5"] = None
    v = f.submit_premeasure(good)
    assert v["stage"] == "done" and f.data["premeasure"]["answered"] == 8 and f.data["premeasure"]["skipped"] == 1
    pm = json.loads((f.dir / "premeasure.json").read_text(encoding="utf-8"))
    assert pm["formatVersion"] == "ifs-premeasure/0.1" and len(pm["items"]) == 9 and pm["draftCount"] > 0
    assert {i["id"]: i["value"] for i in pm["items"]} == good
    with pytest.raises(SelectionError):
        f.submit_premeasure(good)
    valid(f.data)


# ── 고정 문구(원칙 7) · 초안 표시(X35) ─────────────────────────────────────────
def test_protocol_all_draft_with_source():
    p = SelectionProtocol()
    entries = list(p._entries())
    assert entries and all(v.get("status") == "draft" and v.get("source") for _, v in entries)
    assert len(p.draft_keys()) == len(entries)


def test_protocol_texts_match_sources_verbatim():
    p = SelectionProtocol()
    items = {i["id"]: i["text"] for i in p.items()}
    assert items["G13_appearance"] == "이 형상의 모습은 내가 떠올린 것과 비슷하다"
    assert items["G13_representation"] == "이 형상은 내가 떠올린 그것을 나타낸다"
    doc = (REPO_ROOT / "docs" / "rq-v4-questionnaire-draft.md").read_text(encoding="utf-8")
    for i in range(1, 8):
        row = next(line for line in doc.splitlines() if line.startswith(f"| A{i}"))
        assert items[f"A{i}"] in row, f"A{i}"
    assert p.text("figure_intro") == "당신이 말한 것을 바탕으로 만든, 그것을 대신하는 형상입니다."
    assert p.text("none_fit") == "맞는 것이 없다"
    labels = [p.data["adjustItemLabels"][k]["text"] for k in TABLE["adjustItems"]["order"]]
    assert labels == ["색", "형태", "밝기", "투명도", "크기", "질감", "움직임"]          # G31: 색이 맨 앞
    assert p.version == "0.2.0" and "single_candidate_intro" not in p.data["phrases"]  # G34: 후보 1개 화면 없음
    assert "proceed_single_button" not in p.data["phrases"]


def test_protocol_has_no_therapy_terms():
    p = SelectionProtocol()
    text = " ".join(v.get("text", "") for _, v in p._entries())
    for banned in ("치료", "내담자", "진단", "상처", "추방자", "짐을 내려", "환자"):
        assert banned not in text


def test_draft_shown_in_logs_and_screen(rt4):
    assert any("초안" in w for w in rt4.warnings)
    s, f = started(rt4, "SYN-DRAFT", T_FEEL)
    n = len(SelectionProtocol().draft_keys())
    assert f.data["protocol"]["draftCount"] == n == len(f.data["protocol"]["draftKeys"]) > 0
    ev = next(e for e in s.log.data["events"] if e["type"] == "selection:candidates")
    assert ev["payload"]["draftCount"] == n and ev["payload"]["draftKeys"]
    assert f.view()["draftCount"] == n
    web = (REPO_ROOT / "chatbot" / "ifs_chatbot" / "web" / "stage.js").read_text(encoding="utf-8")
    assert "초안 문구 사용 중" in web and "draftCount" in web


def test_require_spec_phrases_refuses_start(tmp_path):
    rt = Runtime(v4_cfg(tmp_path, **{"selection.require_spec_phrases": True}))
    s = done_session(rt, "SYN-REQ", T_FEEL)
    with pytest.raises(SelectionError):
        s.selection().start()


# ── LLM·검증기 호출 0(후보 단계는 면담 밖) ──────────────────────────────────────
def test_no_llm_or_validator_calls_in_stages(rt4, monkeypatch):
    s = done_session(rt4, "SYN-NOLLM", T_FORM, condition="chatbot")
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise AssertionError("후보·조절·측정 단계에서 LLM·검증기를 불렀음")

    monkeypatch.setattr(rt4.backend, "generate", boom)
    monkeypatch.setattr(rt4.validator, "check", boom)
    monkeypatch.setattr(rt4.clarify_validator, "check", boom)
    turns_before = len(s.log.turns)
    f = s.selection()
    v = f.start()
    f.select(v["candidates"][1]["id"])
    f.adjust("size", 0.3)
    f.adjust("color", "n30")
    f.finish()
    f.final()
    f.submit_premeasure(dict(ALL_ITEMS, A1=3))
    assert calls == [] and len(s.log.turns) == turns_before


def test_session_log_still_valid_after_stages(rt4):
    schema = json.loads(shared("schemas", "session_log.schema.json").read_text(encoding="utf-8"))
    s, f = started(rt4, "SYN-LOGV", T_FEEL)
    f.finish()
    f.submit_premeasure(dict(ALL_ITEMS))
    errs = [e.message for e in Draft202012Validator(schema).iter_errors(json.loads(json.dumps(s.log.data, ensure_ascii=False)))]
    assert not errs
    types = [e["type"] for e in s.log.data["events"]]
    assert types == ["selection:candidates", "selection:selected", "selection:adjusted", "selection:premeasure"]


def test_withdraw_deletes_selection_folder(rt4):
    s, f = started(rt4, "SYN-WD", T_FEEL)
    assert f.dir.exists()
    s.withdraw()
    assert not f.dir.exists() and s.selection_flow is None


# ── HTTP API ─────────────────────────────────────────────────────────────────
def test_http_flow(tmp_path):
    rt = Runtime(v4_cfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    done_session(rt, "SYN-HTTP", T_FORM)
    assert c.get("/api/sessions/SYN-HTTP").json()["selection"] == {"available": True, "stage": None}
    assert c.get("/api/sessions/SYN-HTTP/selection").json()["stage"] is None
    assert c.post("/api/sessions/SYN-HTTP/selection", json={"candidateId": "none"}).status_code == 409
    cfg = c.get("/api/selection/config").json()
    assert cfg["enabled"] and [i["id"] for i in cfg["adjustItems"]] == list(TABLE["adjustItems"]["order"])
    assert cfg["protocol"]["draftCount"] > 0
    v = c.post("/api/sessions/SYN-HTTP/candidates").json()
    assert v["stage"] == "selecting" and len(v["candidates"]) == 4
    assert c.post("/api/sessions/SYN-HTTP/selection", json={"candidateId": "c-zzz"}).status_code == 422
    v = c.post("/api/sessions/SYN-HTTP/selection", json={"candidateId": v["candidates"][0]["id"]}).json()
    assert v["stage"] == "adjusting"
    assert c.post("/api/sessions/SYN-HTTP/adjust", json={"item": "layout.distance", "value": 0.1}).status_code == 422
    assert c.post("/api/sessions/SYN-HTTP/adjust", json={"item": "size", "value": 0.99}).status_code == 422
    assert c.post("/api/sessions/SYN-HTTP/adjust", json={"item": "size", "value": 0.8}).status_code == 200
    assert c.get("/api/sessions/SYN-HTTP/final").status_code == 409
    assert c.get("/api/sessions/SYN-HTTP/premeasure").status_code == 409
    assert c.post("/api/sessions/SYN-HTTP/adjust/finish").json()["stage"] == "premeasure"
    fin = c.get("/api/sessions/SYN-HTTP/final").json()
    assert fin["spec"]["meta"]["sessionId"] == "SYN-HTTP" and fin["selection"]["finalOverrides"]["layout.size"] == 0.8
    pv = c.get("/api/sessions/SYN-HTTP/premeasure").json()
    assert len(pv["items"]) == 9
    assert c.post("/api/sessions/SYN-HTTP/premeasure", json={"responses": {"A1": 9}}).status_code == 422
    r = c.post("/api/sessions/SYN-HTTP/premeasure", json={"responses": dict(ALL_ITEMS, A2=2)})
    assert r.status_code == 200 and r.json()["stage"] == "done"
    assert c.get("/api/sessions/SYN-HTTP/preview/current.png").status_code == 409   # none 모드


def test_existing_endpoints_unchanged_in_default_config(rt):
    c = TestClient(create_app(runtime=rt, warmup=False))
    h = c.get("/api/health").json()
    for k in ("config", "conditions", "backend", "guard", "analyzer", "lexicon", "protocol", "prompts", "mapping", "drift", "warnings"):
        assert k in h
    assert h["mapping"]["mode"] == "v1" and h["selection"]["enabled"] is False
    done_session(rt, "SYN-DEF", T_FEEL)
    v = c.get("/api/sessions/SYN-DEF").json()
    assert set(v) == {"sessionId", "condition", "state", "awaiting", "stage", "stageInfo", "messages", "buttons",
                      "confirmDraft", "progress"}
    assert c.post("/api/sessions/SYN-DEF/candidates").status_code == 409
    assert c.get("/api/sessions/SYN-DEF/scene").status_code == 200
    assert c.get("/static/stage.js").status_code == 200


def test_web_assets_have_no_external_urls():
    web = REPO_ROOT / "chatbot" / "ifs_chatbot" / "web"
    for name in ("index.html", "app.js", "stage.js", "style.css"):
        text = (web / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), name


# ── 미리보기 어댑터 ──────────────────────────────────────────────────────────
def test_preview_fake_image_mode_over_http(tmp_path):
    rt = Runtime(v4_cfg(tmp_path, **{"preview.mode": "image", "preview.image_player": "fake"}))
    c = TestClient(create_app(runtime=rt, warmup=False))
    done_session(rt, "SYN-IMG", T_FEEL)
    v = c.post("/api/sessions/SYN-IMG/candidates").json()
    assert v["preview"]["mode"] == "image"
    pngs = []
    for cand in v["candidates"]:
        r = c.get(f"/api/sessions/SYN-IMG/preview/{cand['id']}.png")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content.startswith(b"\x89PNG")
        pngs.append(r.content)
    assert len(set(pngs)) == 4                       # 후보마다 그림이 다르다
    assert c.get("/api/sessions/SYN-IMG/preview/c-unknown.png").status_code == 422


def test_preview_missing_player_or_webgl_falls_back_to_none(tmp_path):
    from ifs_chatbot.config import PreviewConfig
    defaults = TABLE["defaults"]
    a = PreviewService(PreviewConfig(mode="image", image_player=str(tmp_path / "nope.exe")), tmp_path, tmp_path, defaults)
    assert a.mode == "none" and "없음" in a.reason and a.info()["requested"] == "image"
    b = PreviewService(PreviewConfig(mode="webgl", webgl_dir=str(tmp_path / "nobuild")), tmp_path, tmp_path, defaults)
    assert b.mode == "none" and b.info()["webglUrl"] is None
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "index.html").write_text("<!doctype html>", encoding="utf-8")
    w = PreviewService(PreviewConfig(mode="webgl", webgl_dir=str(tmp_path / "build")), tmp_path, tmp_path, defaults)
    assert w.mode == "webgl" and w.info()["webglUrl"] == "/preview/webgl/index.html"
    with pytest.raises(ValueError):
        PreviewService(PreviewConfig(mode="vr"), tmp_path, tmp_path, defaults)


def test_unity_queue_renderer_with_fake_player(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_PLAYER_MODE", "ok")
    r = UnityQueueRenderer([sys.executable, str(FAKE_PLAYER)], tmp_path / "q", start_timeout_s=20, request_timeout_s=10)
    try:
        spec = json.dumps({"meta": {}}, ensure_ascii=False)
        a = r.render(spec, {})
        b = r.render(spec, {"form.type": "mist"})
        assert a.startswith(b"\x89PNG") and a != b and r.renders == 2 and r.info()["running"]
        assert not list((tmp_path / "q").glob("*.done.json")) and not list((tmp_path / "q").glob("*.png"))
    finally:
        r.close()
    assert not r._alive()


@pytest.mark.parametrize("mode", ["die_on_request", "never_ready", "error"])
def test_player_failure_falls_back_to_none_and_alerts(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("FAKE_PLAYER_MODE", mode)
    rt = Runtime(v4_cfg(tmp_path, **{"preview.mode": "image", "preview.image_player": str(FAKE_PLAYER),
                                     "preview.start_timeout_s": 2.0, "preview.request_timeout_s": 3.0}))
    c = TestClient(create_app(runtime=rt, warmup=False))
    try:
        s = done_session(rt, f"SYN-DIE-{mode.replace('_', '')}", T_FEEL)
        v = c.post(f"/api/sessions/{s.id}/candidates").json()
        assert v["preview"]["mode"] == "image"
        r = c.get(f"/api/sessions/{s.id}/preview/{v['candidates'][0]['id']}.png")
        assert r.status_code == 503
        st = c.get(f"/api/sessions/{s.id}/selection").json()
        assert st["preview"]["mode"] == "none" and st["preview"]["requested"] == "image" and st["preview"]["reason"]
        assert any(a["kind"] == "preview_fallback" for a in s.log.data["alerts"])
        assert s.selection_flow.data["preview"]["mode"] == "none"
        assert c.get(f"/api/sessions/{s.id}/preview/current.png").status_code == 409
    finally:
        rt.preview.close()


# ── 러너 계약(unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs) ─────────────
RUNNER_INPUTS = REPO_ROOT / "docs" / "validation" / "runner-selection" / "inputs"


def runner_contract_errors(data: dict) -> list[str]:
    """PlacementSelection.Parse가 거부하는 조건을 파이썬으로 옮긴 것(읽기만 해서 대조)."""
    errs = []
    if not str(data.get("formatVersion", "")).startswith("ifs-selection/"):
        errs.append("formatVersion")
    ss = data.get("specSha256")
    if not (isinstance(ss, str) and re.fullmatch(r"[0-9a-fA-F]{64}", ss)):
        errs.append("specSha256")
    fo = data.get("finalOverrides")
    if not isinstance(fo, dict) or {"layout.distance", "layout.verticalOffset"} & set(fo):
        errs.append("finalOverrides")
    v02 = data.get("formatVersion") == "ifs-selection/0.2"
    sel = data.get("selection")
    if not isinstance(sel, dict) or not isinstance(sel.get("none"), bool) or "selectedCandidateId" not in sel:
        errs.append("selection")
    elif sel["none"] and sel["selectedCandidateId"] is not None:
        errs.append("selection.none+id")
    elif v02 and not isinstance(sel.get("skipped"), bool):
        errs.append("selection.skipped")                    # 0.2: 필수(G34)
    elif sel.get("skipped") and (sel["none"] or sel["selectedCandidateId"] is not None):
        errs.append("selection.skipped+none/id")
    if v02 and not isinstance(data.get("colorChanged"), bool):
        errs.append("colorChanged")                         # 0.2: 필수(G31)
    src = data.get("sources")
    allowed = RUNNER_SOURCES if v02 else RUNNER_SOURCES_01
    if not isinstance(src, dict):
        errs.append("sources")
    elif any(k not in RUNNER_SLOTS or v not in allowed for k, v in src.items()):
        errs.append("sources.values")                       # G27(0.1은 네 값, 0.2는 여섯 값)
    spec = data.get("spec")
    if isinstance(spec, dict) and "sha256Basis" in spec and spec["sha256Basis"] != "file":
        errs.append("sha256Basis")                          # G26
    if data.get("runnerReady") is False:
        errs.append("runnerReady")
    return errs


RUNNER_SLOTS = set(SCHEMA["$defs"]["slotName"]["enum"])
RUNNER_SOURCES = set(SCHEMA["$defs"]["source"]["enum"])
RUNNER_SOURCES_01 = set(SCHEMA01["$defs"]["source"]["enum"])


def test_runner_slot_and_source_lists_match_csharp():
    """러너(PlacementSelection.cs)의 슬롯 이름·출처 값 목록이 스키마와 같다(G27). 0.2는 여섯 값(G32), 0.1은 네 값."""
    src = (REPO_ROOT / "unity" / "Assets" / "IFS" / "Runtime" / "Placement" / "PlacementSelection.cs").read_text(encoding="utf-8")
    slots = re.search(r"SlotNames\s*=\s*\{([^}]*)\}", src).group(1)
    sources = re.search(r"SourceValues\s*=\s*\{([^}]*)\}", src).group(1)
    sources01 = re.search(r"SourceValues01\s*=\s*\{([^}]*)\}", src).group(1)
    # 0.2 슬롯 = 0.1 슬롯 + form.base(D6, SceneSpec 2.2.0 기본 형상 — 0.2에 하위 호환으로 더함)
    assert set(re.findall(r'"([^"]+)"', slots)) == RUNNER_SLOTS == set(SCHEMA01["$defs"]["slotName"]["enum"]) | {"form.base"}
    assert set(re.findall(r'"([^"]+)"', sources)) == RUNNER_SOURCES == SIX_SOURCES
    assert set(re.findall(r'"([^"]+)"', sources01)) == RUNNER_SOURCES_01 == {"said", "chosen", "edited", "default"}
    from ifs_chatbot.selection import SOURCES
    assert set(SOURCES) == SIX_SOURCES
    known = re.search(r"KnownFormatVersions\s*=\s*\{([^}]*)\}", src).group(1)
    assert set(re.findall(r'"([^"]+)"', known)) == {"ifs-selection/0.1", "ifs-selection/0.2"}


@pytest.mark.parametrize("name", ["sel_chosen_adjusted.json", "sel_none_of_these.json", "sel_no_overrides.json"])
def test_runner_synthetic_selection_files_pass_schema(name):
    """러너 쪽 손으로 만든 합성 입력은 0.1 형식이다(러너가 0.1도 계속 읽음). 0.1 스키마로 확인한다."""
    data = json.loads((RUNNER_INPUTS / name).read_text(encoding="utf-8"))
    assert data["formatVersion"] == "ifs-selection/0.1"
    valid(data, VALIDATOR01)
    assert runner_contract_errors(data) == []


def test_schema_rejects_runner_contract_violations():
    base = json.loads((RUNNER_INPUTS / "sel_chosen_adjusted.json").read_text(encoding="utf-8"))
    for mutate in (lambda d: d.pop("specSha256"), lambda d: d.update(specSha256="abc"),
                   lambda d: d["finalOverrides"].update({"layout.distance": 0.1}),
                   lambda d: d["finalOverrides"].update({"layout.verticalOffset": 0.5}),
                   lambda d: d["selection"].update(none=True), lambda d: d.pop("sources"),
                   lambda d: d["sources"].update({"form.type": "inferred"}), lambda d: d.pop("finalOverrides"),
                   lambda d: d["sources"].update({"form.type": "said_unrendered_chosen"})):    # 0.1에는 없는 값
        d = json.loads(json.dumps(base))
        mutate(d)
        assert list(VALIDATOR01.iter_errors(d)), d


def test_schema_02_rejects_inconsistent_skip_and_missing_new_fields(rt4):
    _, f = started(rt4, "SYN-SCH02", T_FEEL)
    f.finish()
    ok = json.loads(json.dumps(f.data))
    valid(ok)
    for mutate in (lambda d: d.pop("colorChanged"),                                          # 0.2 필수
                   lambda d: d["selection"].pop("skipped"),                                  # 0.2 필수
                   lambda d: d["selection"].update(skipped=True),                            # 건너뛰었다면서 id 있음
                   lambda d: d["selection"].update(none=True, selectedCandidateId=None, skipped=True),
                   lambda d: d["sources"].update({"form.type": "offered"}),
                   lambda d: d["sourceCounts"].pop("said_unrendered_default"),
                   lambda d: d.update(formatVersion="ifs-selection/0.1")):
        d = json.loads(json.dumps(ok))
        mutate(d)
        assert list(VALIDATOR.iter_errors(d)), d


def test_chatbot_selection_files_satisfy_runner_contract(tmp_path):
    """챗봇이 만든 selection.json(시나리오 4개 이상)이 러너 계약 필드를 모두 갖고, specSha256이 저장된 spec 파일 바이트와 같다."""
    import hashlib
    from ifs_chatbot.selection_sim import load, make_runtime, run_one
    rt = make_runtime(tmp_path / "logs")
    scs = load()
    assert len(scs) >= 4
    for sc in scs:
        r = run_one(rt, sc)
        s, f = r["session"], r["flow"]
        data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
        assert runner_contract_errors(data) == [], sc["id"]
        valid(data)
        spec_bytes = Path(s.log.data["sceneSpec"]["path"]).read_bytes()
        assert data["specSha256"] == hashlib.sha256(spec_bytes).hexdigest()
        assert set(data["sources"].values()) <= SIX_SOURCES
        assert data["selection"]["none"] == (sc["selection"] == "none")
        assert data["selection"]["skipped"] == (sc["selection"] == "skip")


def test_placement_analyzer_reads_v02_records_with_selection():
    """러너가 0.2로 올린 기록(manifest selection{…}·appliedOverrides)에 version_mismatch가 붙지 않고, 선택 열이 채워진다."""
    from ifs_chatbot.eval.placement import KNOWN_VERSIONS, analyze
    assert "ifs-placement/0.2" in KNOWN_VERSIONS and "ifs-placement/0.1" in KNOWN_VERSIONS
    root = REPO_ROOT / "docs" / "validation" / "runner-selection" / "records"
    res = analyze(root)
    assert {"selection_none", "selected_candidate_id", "n_final_overrides"} <= set(res["columns"])
    assert res["columns"][-2:] == ["obj_path_from_objpose_m", "flags"]
    sessions = res["sessions"]
    assert sessions
    for s in sessions:
        assert "version_mismatch" not in (s["flags"] or ""), s["flags"]
        man = json.loads(next((root / s["record_folder"]).glob("manifest.json")).read_text(encoding="utf-8")) \
            if (root / s["record_folder"]).is_dir() else None
        if man and man.get("selection"):
            assert s["selection_none"] == man["selection"]["none"]
            assert s["selected_candidate_id"] == man["selection"]["selectedCandidateId"]
            assert s["n_final_overrides"] == len(man["selection"]["finalOverrides"])
    assert any(s["selection_none"] is True for s in sessions) and any(s["selection_none"] is False for s in sessions)


# ── 합성 시나리오 1–6단계(완료 기준) ────────────────────────────────────────────
def test_selection_scenarios_run_end_to_end(tmp_path):
    from ifs_chatbot.selection_sim import load, run
    scs = load()
    assert len(scs) >= 4
    s = run(scs, tmp_path / "out", quiet=True)
    assert s["expectFailures"] == 0, [r["expectFailures"] for r in s["results"]]
    by = {r["scenario"]: r for r in s["results"]}
    assert by["S3_all_said"]["candidateCount"] == 1 and by["S4_none_fit"]["selection"]["none"] is True
    assert by["S3_all_said"]["selection"]["skipped"] is True and by["S5_one_open"]["selection"]["skipped"] is True
    assert by["S5_one_open"]["candidateCountBeforeDistinct"] == 4
    assert by["S6_unrendered_shape_chosen"]["sources"]["form.type"] == "said_unrendered_chosen"
    assert by["S7_unrendered_none_floor"]["sources"]["form.type"] == "said_unrendered_default"
    assert by["S7_unrendered_none_floor"]["distanceFloor"]["said"] == 0.0
    # D6: 기본 형상을 말함 → 조절에서 다른 기본 형상으로 고침 / '막' 갈림에서 껍질을 고름
    assert by["S8_base_said_edited"]["sources"]["form.base"] == "edited"
    assert by["S8_base_said_edited"]["sources"]["form.type"] == "default"
    assert by["S9_membrane_split"]["sources"]["form.type"] == "chosen" and by["S9_membrane_split"]["sources"]["form.base"] == "said"
    assert all(r["interviewLlmTurns"] == 0 for r in s["results"])
    for r in s["results"]:
        d = tmp_path / "out" / r["scenario"]
        for name in ("confirmed_text.txt", "spec.json", "candidates.json", "selection.json", "premeasure.json"):
            assert (d / name).exists()
        valid(json.loads((d / "selection.json").read_text(encoding="utf-8")))
        assert "<log_dir>" in (d / "selection.json").read_text(encoding="utf-8")
