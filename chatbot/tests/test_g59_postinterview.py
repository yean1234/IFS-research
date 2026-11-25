"""G59: 사후 면담 프로토콜·기록 화면 API, 초안 경고 줄 숨김 설정, 분석기의 사전 측정·사후 면담 열.
모든 대사·응답은 합성이다(AGENTS.md 6)."""
import csv
import json
import re
import shutil

import pytest
from fastapi.testclient import TestClient

from ifs_chatbot.config import SelectionConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.eval import placement
from ifs_chatbot.eval.placement import analyze
from ifs_chatbot.postinterview import FORMAT_VERSION, PostInterviewProtocol
from ifs_chatbot.server import create_app
from test_placement_eval import four_conditions, make_placement_session, row
from test_selection_flow import ALL_ITEMS, REPO_ROOT, T_FEEL, done_session, started, v4_cfg

WEB = REPO_ROOT / "chatbot" / "ifs_chatbot" / "web"
FREE_PLACE = ["PI1_place_recall", "PI2_how_known", "PI3_more", "PI4_timing", "PI5_one_line"]


# ── 프로토콜 ────────────────────────────────────────────────────────────────
def test_protocol_all_draft_with_g59_source():
    p = PostInterviewProtocol()
    assert p.version == "0.1.0" and p.data["status"] == "draft"
    entries = list(p._entries())
    assert entries and len(p.draft_keys()) == len(entries)
    for _, v in entries:
        assert v["status"] == "draft" and "G59" in v["source"] and "IRB 검토 전" in v["source"]
    ch = p.data["changes"][0]
    assert ch["version"] == p.version and "G59" in ch["source"]


def test_protocol_items_by_condition_and_order():
    p = PostInterviewProtocol()
    ids = lambda c, part=None: [i["id"] for i in p.items_for(c, part)]   # noqa: E731
    assert ids("place") == FREE_PLACE + ["PI6_basis", "PI7_referent", "PI8_purpose"]
    assert ids("point_select") == ids("place")
    assert ids("view") == ["PI1_place_recall", "PI2_view_noticed", "PI3_more", "PI4_timing", "PI5_one_line",
                           "PI7_referent", "PI8_purpose"]
    assert ids("place", "free") == FREE_PLACE
    pi6 = next(i for i in p.data["items"] if i["id"] == "PI6_basis")
    assert pi6["part"] == "after_free" and [s["id"] for s in pi6["items"]] == [
        "B1_visibility", "B2_reach", "B3_floor_marks", "B4_apart", "B5_near", "B6_no_thought"]
    assert pi6["scale"]["anchors"] == {"1": "전혀 영향을 주지 않았다", "7": "매우 많이 영향을 주었다"}
    texts = {i["id"]: i["text"] for i in p.data["items"]}
    assert texts["PI2_how_known"] == "그 자리에 놓던 순간으로 돌아가 볼게요. 그때 '여기다' 하는 것을 어떻게 알았나요?"
    assert texts["PI3_more"] == "말씀하신 '{X}'에 대해 더 있나요?"


def test_free_part_uses_no_words_the_rules_forbid_and_no_why_or_therapy_terms():
    """R4: 참여자가 먼저 쓰지 않은 낱말(거리·멀리·가까이·치우다·피하다·편하다·안전)은 자유 응답 문항에 없다.
    평정 묶음(PI6, 자유 응답 뒤에만 보임)에는 '가까이'·'편한'이 있다 — 그래서 뒤에 둔다."""
    p = PostInterviewProtocol()
    words = next(r for r in p.data["experimenterRules"] if r["id"] == "R4_no_new_words")["words"]
    for it in p.data["items"]:
        if it["part"] == "free":
            for w in words:
                assert w not in it["text"], (it["id"], w)
            assert "왜" not in it["text"]
    alltext = json.dumps(p.data, ensure_ascii=False)
    for banned in ("치료", "내담자", "진단", "추방자", "짐을 내려", "환자"):
        assert banned not in alltext


# ── API·기록 ────────────────────────────────────────────────────────────────
def _client(tmp_path, **over):
    rt = Runtime(v4_cfg(tmp_path, **over))
    return rt, TestClient(create_app(runtime=rt, warmup=False))


FREE_OK = [
    {"id": "PI1_place_recall", "text": "창문 옆 밝은 자리였어요."},
    {"id": "PI2_how_known", "text": "밝은 데를 보니까 거기다 싶었어요."},
    {"id": "PI3_more", "word": "밝은 자리", "text": "햇빛이 드는 느낌이요."},
    {"id": "PI4_timing", "choice": "then"},
    {"id": "PI5_one_line", "skipped": True},
]
AFTER_OK = [{"id": "B1_visibility", "value": 5}, {"id": "B2_reach", "value": None}, {"id": "B3_floor_marks", "value": 2},
            {"id": "B4_apart", "value": 1}, {"id": "B5_near", "value": 6}, {"id": "B6_no_thought", "value": None},
            {"id": "PI7_referent", "choice": "both"}, {"id": "PI8_purpose", "text": "물체를 어디 두는지 보려는 것 같아요."}]


def test_postinterview_two_parts_gate_and_record(tmp_path):
    rt, c = _client(tmp_path)
    s, f = started(rt, "SYN-PI", T_FEEL)
    f.finish()
    f.submit_premeasure(dict(ALL_ITEMS, W1_intensity=4))
    cfg = c.get("/api/postinterview/config").json()
    assert cfg["enabled"] and cfg["protocol"]["draftCount"] > 0 and cfg["formatVersion"] == FORMAT_VERSION
    assert c.get("/api/sessions/SYN-PI/postinterview").json()["record"] is None
    url = "/api/sessions/SYN-PI/postinterview"
    # 평정 묶음은 자유 응답을 저장하기 전에는 받지 않음(G59)
    assert c.post(url, json={"condition": "place", "part": "after_free", "responses": AFTER_OK}).status_code == 409
    # 조건에 없는 문항·빠진 문항·모르는 조건
    bad = FREE_OK + [{"id": "PI2_view_noticed", "text": "합성"}]
    assert c.post(url, json={"condition": "place", "part": "free", "responses": bad}).status_code == 422
    assert c.post(url, json={"condition": "place", "part": "free", "responses": FREE_OK[:-1]}).status_code == 422
    assert c.post(url, json={"condition": "lean", "part": "free", "responses": FREE_OK}).status_code == 422
    # 자유 응답에 평정 묶음 항목을 섞으면 거부
    assert c.post(url, json={"condition": "place", "part": "free",
                             "responses": FREE_OK + [{"id": "B1_visibility", "value": 3}]}).status_code == 422
    r = c.post(url, json={"condition": "place", "part": "free", "responses": FREE_OK})
    assert r.status_code == 200 and r.json()["nextPart"] == "after_free"
    path = f.dir / "postinterview.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["formatVersion"] == FORMAT_VERSION and rec["condition"] == "place" and rec["completedAt"] is None
    assert "free" in rec["parts"] and "after_free" not in rec["parts"]
    # 자유 응답은 다시 저장하지 않음(덮어쓰기 없음), 뒤 부분은 같은 조건으로만
    assert c.post(url, json={"condition": "place", "part": "free", "responses": FREE_OK}).status_code == 409
    assert c.post(url, json={"condition": "view", "part": "after_free",
                             "responses": AFTER_OK[6:]}).status_code == 409
    assert c.post(url, json={"condition": "place", "part": "after_free",
                             "responses": AFTER_OK[:5] + AFTER_OK[6:]}).status_code == 422     # B6 빠짐
    assert c.post(url, json={"condition": "place", "part": "after_free",
                             "responses": [dict(AFTER_OK[0], value=8)] + AFTER_OK[1:]}).status_code == 422
    r = c.post(url, json={"condition": "place", "part": "after_free", "responses": AFTER_OK})
    assert r.status_code == 200 and r.json()["nextPart"] is None
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["completedAt"] and set(rec["parts"]) == {"free", "after_free"}
    by = {(i["id"], i.get("round")): i for i in rec["items"]}
    assert by[("PI3_more", 1)]["prompt"] == "말씀하신 '밝은 자리'에 대해 더 있나요?" and by[("PI3_more", 1)]["word"] == "밝은 자리"
    assert by[("PI5_one_line", None)]["skipped"] is True and by[("PI5_one_line", None)]["text"] is None
    assert by[("PI4_timing", None)]["choice"] == "then" and by[("B5_near", None)]["group"] == "PI6_basis"
    assert by[("B2_reach", None)]["skipped"] is True
    assert [i["id"] for i in rec["items"]][:5] == ["PI1_place_recall", "PI2_how_known", "PI3_more", "PI4_timing", "PI5_one_line"]
    assert c.post(url, json={"condition": "place", "part": "after_free", "responses": AFTER_OK}).status_code == 409
    # 다른 기록(selection.json·premeasure.json)은 그대로 있고, 사후 면담은 세션 로그 사건을 더하지 않음
    assert (f.dir / "premeasure.json").is_file()
    assert not any(e["type"].startswith("post") for e in s.log.data["events"])


def test_pi3_word_must_be_participant_words(tmp_path):
    rt, c = _client(tmp_path)
    started(rt, "SYN-PI3", T_FEEL)
    url = "/api/sessions/SYN-PI3/postinterview"
    base = [r for r in FREE_OK if r["id"] != "PI3_more"]
    for word in ("가까이", "멀리 있는 자리", "밝은 데를 보니까 거기다 싶었어요"):   # 참여자가 안 쓴 낱말 · 4어절 이상
        resp = base + [{"id": "PI3_more", "word": word, "text": "합성"}]
        assert c.post(url, json={"condition": "place", "part": "free", "responses": resp}).status_code == 422, word
    three = base + [{"id": "PI3_more", "word": w, "text": "합성"} for w in ("밝은", "자리", "창문")]
    assert c.post(url, json={"condition": "place", "part": "free", "responses": three}).status_code == 422  # 최대 2회
    # 둘째 회차는 첫 회차에서 받아 적은 말도 쓸 수 있음. 회차 없음 = 건너뜀 한 줄
    two = base + [{"id": "PI3_more", "word": "밝은", "text": "햇빛이 드는 느낌"}, {"id": "PI3_more", "word": "햇빛", "text": "따뜻해요"}]
    assert c.post(url, json={"condition": "place", "part": "free", "responses": two}).status_code == 200


def test_pi3_without_rounds_is_one_skipped_entry(tmp_path):
    rt, c = _client(tmp_path, **{"session.log_dir": str(tmp_path / "l2")})
    started(rt, "SYN-PI3N", T_FEEL)
    url = "/api/sessions/SYN-PI3N/postinterview"
    resp = [{"id": "PI1_place_recall", "skipped": True}, {"id": "PI2_view_noticed", "text": "흐릿했어요"},
            {"id": "PI4_timing", "skipped": True}, {"id": "PI5_one_line", "text": "흐릿함"}]
    rec = c.post(url, json={"condition": "view", "part": "free", "responses": resp}).json()["record"]
    pi3 = [i for i in rec["items"] if i["id"] == "PI3_more"]
    assert len(pi3) == 1 and pi3[0]["skipped"] is True and pi3[0]["round"] is None
    # view 조건에는 PI6이 없음
    after = [{"id": "PI7_referent", "choice": "object"}, {"id": "PI8_purpose", "skipped": True}]
    assert c.post(url, json={"condition": "view", "part": "after_free",
                             "responses": after + [{"id": "B1_visibility", "value": 3}]}).status_code == 422
    assert c.post(url, json={"condition": "view", "part": "after_free", "responses": after}).status_code == 200


def test_postinterview_session_checks_and_default_config(tmp_path, rt):
    _, c = _client(tmp_path)
    assert c.get("/api/sessions/NOPE/postinterview").status_code == 404
    assert c.get("/api/sessions/bad..id/postinterview").status_code in (404, 422)
    # 서버를 다시 띄운 뒤에도 같은 세션 폴더에 selection.json이 있으면 연다
    rt2, c2 = _client(tmp_path)
    assert c2.get("/api/sessions/NOPE/postinterview").status_code == 404
    (rt2.cfg.log_dir / "selection" / "SYN-OLD").mkdir(parents=True)
    (rt2.cfg.log_dir / "selection" / "SYN-OLD" / "selection.json").write_text("{}", encoding="utf-8")
    assert c2.get("/api/sessions/SYN-OLD/postinterview").json()["record"] is None
    # 기본 설정: 화면이 없고 API는 409, 기존 흐름 그대로
    cd = TestClient(create_app(runtime=rt, warmup=False))
    done_session(rt, "SYN-PI-DEF", T_FEEL)
    assert cd.get("/api/sessions/SYN-PI-DEF/postinterview").status_code == 409
    assert cd.post("/api/sessions/SYN-PI-DEF/postinterview",
                   json={"condition": "place", "part": "free", "responses": FREE_OK}).status_code == 409
    assert not (rt.cfg.log_dir / "selection").exists()


def test_postinterview_never_calls_llm(tmp_path, monkeypatch):
    rt, c = _client(tmp_path)
    started(rt, "SYN-PI-NOLLM", T_FEEL)

    def boom(*a, **k):
        raise AssertionError("사후 면담에서 LLM·검증기를 불렀음")

    monkeypatch.setattr(rt.backend, "generate", boom)
    monkeypatch.setattr(rt.validator, "check", boom)
    r = c.post("/api/sessions/SYN-PI-NOLLM/postinterview", json={"condition": "place", "part": "free", "responses": FREE_OK})
    assert r.status_code == 200


def test_postinterview_web_screen_is_data_driven():
    js = (WEB / "postinterview.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'id="postinterview"' in html and "/static/postinterview.js" in html
    assert '"postinterview"' in app and "ifsPostInterview" in app
    assert "/api/postinterview/config" in js and "/postinterview`" in js
    # 문항 글은 프로토콜에서만 온다(화면 코드에 문항 문장을 박아 두지 않음)
    for it in PostInterviewProtocol().data["items"]:
        assert it["text"] not in js
    assert not re.search(r"https?://", js)


# ── 초안 경고 줄 숨김 설정(작업 C) ─────────────────────────────────────────────
def test_participant_draft_banner_setting_default_on(tmp_path):
    assert SelectionConfig().participant_draft_banner is True
    assert load_config("v4").selection.participant_draft_banner is True
    assert load_config("default").selection.participant_draft_banner is True
    _, c = _client(tmp_path)
    assert c.get("/api/selection/config").json()["participantDraftBanner"] is True
    _, c2 = _client(tmp_path / "off", **{"selection.participant_draft_banner": False})
    cfg = c2.get("/api/selection/config").json()
    assert cfg["participantDraftBanner"] is False and cfg["protocol"]["draftCount"] > 0     # 기록·연구자 정보는 그대로
    stage = (WEB / "stage.js").read_text(encoding="utf-8")
    banner = stage[stage.index("function banners()"):stage.index("// 단계가 바뀌면")]
    assert "participantDraftBanner === false" in banner and "researcher-only" in banner


def test_hidden_banner_keeps_records(tmp_path):
    rt, _ = _client(tmp_path, **{"selection.participant_draft_banner": False})
    s, f = started(rt, "SYN-BANNER", T_FEEL)
    assert f.data["protocol"]["draftCount"] > 0 and f.view()["draftCount"] > 0
    ev = next(e for e in s.log.data["events"] if e["type"] == "selection:candidates")
    assert ev["payload"]["draftCount"] > 0


# ── 분석기(작업 D) ──────────────────────────────────────────────────────────
def _pre(sid, w1=5):
    items = [{"id": "W1_intensity", "value": w1}] + [{"id": f"A{i}", "value": i % 7 + 1} for i in range(1, 8)]
    items[3]["value"] = None
    return {"formatVersion": "ifs-premeasure/0.1", "sessionId": sid, "protocolVersion": "0.5.0", "items": items}


def _pi(sid, condition):
    return {"formatVersion": FORMAT_VERSION, "sessionId": sid, "condition": condition, "protocolVersion": "0.1.0",
            "completedAt": "2026-11-25T00:00:00+09:00",
            "items": [{"id": "PI1_place_recall", "kind": "oral", "text": "합성 자리 설명", "skipped": False},
                      {"id": "PI3_more", "kind": "oral_repeat", "round": 1, "word": "자리", "text": "합성", "skipped": False},
                      {"id": "PI4_timing", "kind": "choice", "choice": "now", "choiceText": "지금", "skipped": False},
                      {"id": "PI5_one_line", "kind": "typed", "text": None, "skipped": True},
                      {"id": "B1_visibility", "kind": "rating_group", "group": "PI6_basis", "value": 6, "skipped": False}]}


def test_analyzer_without_files_is_byte_identical(tmp_path):
    rec = tmp_path / "r"
    four_conditions(rec)
    analyze(rec, tmp_path / "o1")
    empty = tmp_path / "sel"
    (empty / "other-session").mkdir(parents=True)
    (empty / "other-session" / "premeasure.json").write_text(json.dumps(_pre("other-session")), encoding="utf-8")
    res = analyze(rec, tmp_path / "o2", selection_dir=empty)
    for name in ("placement_sessions.csv", "stop_trials.csv", "placement_summary.json"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()
    assert "selfReport" not in res["summary"] and not any(c.startswith(("pre_", "pi_")) for c in res["columns"])


def test_analyzer_matches_head_version_on_real_records(tmp_path):
    """기록 폴더에 사전 측정·사후 면담 파일이 없으면 G59 전 분석기(커밋 a7eb7ee의 placement.py)와 출력이 바이트까지 같다."""
    import importlib.util
    import subprocess
    try:
        src = subprocess.run(["git", "show", "a7eb7ee:chatbot/ifs_chatbot/eval/placement.py"], cwd=REPO_ROOT,
                             capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git 기록(a7eb7ee)을 읽을 수 없음")
    src = src.replace("from .ownership", "from ifs_chatbot.eval.ownership").replace("from .profile_items",
                                                                                   "from ifs_chatbot.eval.profile_items")
    mod_path = tmp_path / "placement_head.py"
    mod_path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("placement_head", mod_path)
    head = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(head)
    real = REPO_ROOT / "docs" / "validation" / "placement" / "records"
    if not real.exists():
        pytest.skip("검증 기록 없음")
    head.analyze(real, tmp_path / "old")
    analyze(real, tmp_path / "new")
    for name in ("placement_sessions.csv", "stop_trials.csv", "placement_summary.json"):
        assert (tmp_path / "old" / name).read_bytes() == (tmp_path / "new" / name).read_bytes(), name


def test_analyzer_adds_pre_and_pi_columns(tmp_path):
    rec = tmp_path / "r"
    make_placement_session(rec, 1, "s-place", "place")
    make_placement_session(rec, 2, "s-point", "view", "point_select", final=(2.4, 25.0, 1.2))
    make_placement_session(rec, 3, "s-static", "view", "static")
    sel = tmp_path / "sel"
    for sid, cond in (("s-place", "place"), ("s-point", "view")):        # s-point은 조건을 잘못 고른 경우(point_select여야 함)
        (sel / sid).mkdir(parents=True)
        (sel / sid / "premeasure.json").write_text(json.dumps(_pre(sid)), encoding="utf-8")
        (sel / sid / "postinterview.json").write_text(json.dumps(_pi(sid, cond)), encoding="utf-8")
    # 기록 폴더 안에 둔 파일도 읽음(s-static: 사전 측정만, 범위 밖 값)
    static_folder = next((rec / "placement" / "P003").rglob("manifest.json")).parent
    (static_folder / "premeasure.json").write_text(json.dumps(_pre("s-static", w1=9)), encoding="utf-8")
    out = tmp_path / "o"
    res = analyze(rec, out, selection_dir=sel)
    p = row(res, "s-place")
    assert p["pre_W1_intensity"] == 5 and p["pre_A3"] is None and p["pre_protocol_version"] == "0.5.0"
    assert p["pi_condition"] == "place" and p["pi_completed"] is True and p["pi_PI4_timing"] == "now"
    assert p["pi_PI1_place_recall_chars"] == len("합성 자리 설명") and p["pi_PI1_place_recall_skipped"] is False
    assert p["pi_PI3_more_r1_chars"] == 2 and p["pi_PI5_one_line_chars"] is None and p["pi_PI5_one_line_skipped"] is True
    assert p["pi_B1_visibility"] == 6 and "pi_condition_mismatch" not in p["flags"]
    assert "pi_condition_mismatch" in row(res, "s-point")["flags"]
    st = row(res, "s-static")
    assert st["pre_W1_intensity"] is None and "premeasure_out_of_range" in st["flags"] and st["pi_condition"] is None
    # 자유 글 자체는 표에 없다
    text = (out / "placement_sessions.csv").read_text(encoding="utf-8")
    assert "합성 자리 설명" not in text and "pi_PI1_place_recall_chars" in text
    with (out / "placement_sessions.csv").open(encoding="utf-8", newline="") as fh:
        head = next(csv.reader(fh))
    assert head[-2:] == placement.SESSION_TAIL and head.index("pre_protocol_version") > head.index("rating_know_more_post")
    summ = json.loads((out / "placement_summary.json").read_text(encoding="utf-8"))
    assert summ["selfReport"]["files"] == {"premeasure": 3, "postinterview": 2}
    assert "pre_W1_intensity" in summ["summaries"]["byCondition"]["place"]
    assert str(tmp_path) not in json.dumps(summ, ensure_ascii=False)
    # 결정론
    analyze(rec, tmp_path / "o2", selection_dir=sel)
    for name in ("placement_sessions.csv", "placement_summary.json"):
        assert (out / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()
    shutil.rmtree(tmp_path / "o2")


def test_analyzer_cli_selection_dir(tmp_path, capsys):
    rec = tmp_path / "r"
    make_placement_session(rec, 1, "s-place", "place")
    sel = tmp_path / "sel" / "s-place"
    sel.mkdir(parents=True)
    (sel / "postinterview.json").write_text(json.dumps(_pi("s-place", "place")), encoding="utf-8")
    placement.main(["--records", str(rec), "--out", str(tmp_path / "o"), "--selection-dir", str(tmp_path / "sel")])
    with (tmp_path / "o" / "placement_sessions.csv").open(encoding="utf-8", newline="") as fh:
        r = next(csv.DictReader(fh))
    assert r["pi_condition"] == "place" and r["pi_B1_visibility"] == "6"
