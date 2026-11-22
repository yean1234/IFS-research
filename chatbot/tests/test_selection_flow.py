"""면담 뒤 데스크톱 단계(selection.py·server.py·preview.py) — 선택·none, 조절 범위·거부, 출처 네 가지, selection.json 스키마,
초안 표시, LLM·검증기 호출 0, 기존 엔드포인트 불변, 미리보기 어댑터(가짜 렌더러·가짜 플레이어), 합성 시나리오 1–6단계.
모든 대사는 합성이다."""
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

SCHEMA = json.loads(shared("schemas", "selection.v0.1.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)
TABLE = load_table()
FAKE_PLAYER = Path(__file__).parent / "fixtures" / "fake_preview_player.py"

T_FORM = "가슴 앞에 연기 같은 게 있어요. 작아요."
T_FEEL = "가슴 안쪽이 답답하고 무거운 느낌이에요."
T_ALL = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 안 움직여요. 불투명해요. 어두워요."


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


def valid(data):
    errs = [e.message for e in VALIDATOR.iter_errors(json.loads(json.dumps(data, ensure_ascii=False)))]
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
    assert data["formatVersion"] == "ifs-selection/0.1"
    assert data["candidates"]["displayOrder"] == [c["id"] for c in v["candidates"]]
    valid(data)


def test_start_is_idempotent(rt4):
    s = done_session(rt4, "SYN-IDEM", T_FEEL)
    a = s.selection().start()
    b = s.selection().start()
    assert a["candidates"] == b["candidates"]
    assert sum(1 for e in s.log.data["events"] if e["type"] == "selection:candidates") == 1


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


def test_single_candidate_flow(rt4):
    s = done_session(rt4, "SYN-ONE", T_ALL)
    f = s.selection()
    v = f.start()
    assert v["single"] is True and len(v["candidates"]) == 1
    f.select(v["candidates"][0]["id"])
    f.finish()
    assert f.data["finalOverrides"] == {}
    assert f.data["sourceCounts"]["chosen"] == 0


# ── 조절(G10·G22) ─────────────────────────────────────────────────────────────
def started(rt, sid, text=T_FEEL, pick=0):
    s = done_session(rt, sid, text)
    f = s.selection()
    v = f.start()
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


# ── 출처 네 가지(G15) ─────────────────────────────────────────────────────────
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
    assert sum(f.data["sourceCounts"].values()) == 15
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
    assert labels == ["형태", "색", "밝기", "투명도", "크기", "질감", "움직임"]


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
    sel = data.get("selection")
    if not isinstance(sel, dict) or not isinstance(sel.get("none"), bool) or "selectedCandidateId" not in sel:
        errs.append("selection")
    elif sel["none"] and sel["selectedCandidateId"] is not None:
        errs.append("selection.none+id")
    if not isinstance(data.get("sources"), dict):
        errs.append("sources")
    return errs


@pytest.mark.parametrize("name", ["sel_chosen_adjusted.json", "sel_none_of_these.json", "sel_no_overrides.json"])
def test_runner_synthetic_selection_files_pass_schema(name):
    data = json.loads((RUNNER_INPUTS / name).read_text(encoding="utf-8"))
    valid(data)
    assert runner_contract_errors(data) == []


def test_schema_rejects_runner_contract_violations():
    base = json.loads((RUNNER_INPUTS / "sel_chosen_adjusted.json").read_text(encoding="utf-8"))
    for mutate in (lambda d: d.pop("specSha256"), lambda d: d.update(specSha256="abc"),
                   lambda d: d["finalOverrides"].update({"layout.distance": 0.1}),
                   lambda d: d["finalOverrides"].update({"layout.verticalOffset": 0.5}),
                   lambda d: d["selection"].update(none=True), lambda d: d.pop("sources"),
                   lambda d: d["sources"].update({"form.type": "inferred"}), lambda d: d.pop("finalOverrides")):
        d = json.loads(json.dumps(base))
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
        assert set(data["sources"].values()) <= {"said", "chosen", "edited", "default"}
        assert data["selection"]["none"] == (sc["selection"] == "none")


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
    assert all(r["interviewLlmTurns"] == 0 for r in s["results"])
    for r in s["results"]:
        d = tmp_path / "out" / r["scenario"]
        for name in ("confirmed_text.txt", "spec.json", "candidates.json", "selection.json", "premeasure.json"):
            assert (d / name).exists()
        valid(json.loads((d / "selection.json").read_text(encoding="utf-8")))
        assert "<log_dir>" in (d / "selection.json").read_text(encoding="utf-8")
