"""구별 프로파일(ifs_chatbot.eval.differentiation)·합성 세션 생성기(sim_placement) 테스트.
기록·평정·발화는 모두 합성(AGENTS.md 6). 기록 한 벌은 test_placement_eval.make_placement_session으로 만든다."""
import csv
import json
from pathlib import Path

import pytest

from ifs_chatbot.eval import differentiation as dv
from ifs_chatbot.eval import language_markers as lm
from ifs_chatbot.eval import placement, sim_placement
from ifs_chatbot.eval.profile_items import ITEM_SCALES, PROFILE_ITEMS
from test_placement_eval import make_placement_session

needs_kiwi = pytest.mark.skipif(not lm._analyzer().available, reason="kiwipiepy 필요")
REPO = Path(__file__).resolve().parents[2]
UNITY_RECORDS = REPO / "docs" / "validation" / "placement" / "records"


def head_series(early_angle, late_angle, seconds=90):
    """조건 단계 머리 표본(50 ms 간격): 처음 절반은 early_angle, 나머지는 late_angle. (yaw, 거리, 각)."""
    n = int(seconds * 20)
    return [(0, 1.0, early_angle if i < n // 2 else late_angle) for i in range(n)]


def ratings(pre: dict, post: dict):
    rows = [[k, "pre", v, 500] for k, v in pre.items()] + [[k, "post", v, 500] for k, v in post.items()]
    return rows


FULL_PRE = {"M1p": 4, "M2": 4, "P1": 3, "M3": 4, "P2": 4, "S5": 4, "S6": 3}
FULL_POST = {"M1p": 6, "M2": 7, "P1": 6, "M3": 6, "P2": 6, "S5": 6, "S6": 2}


def session(root, pnum, sid, condition="place", final=(1.0, 0.0, 0.8), late=5, early=5, rt=None, **kw):
    return make_placement_session(root, pnum, sid, condition, final=final, head=head_series(early, late),
                                  ratings=ratings(FULL_PRE, FULL_POST) if rt is None else rt, **kw)


def row(res, sid):
    return next(r for r in res["rows"] if r["session_id"] == sid)


def write_jsonl(path, items):
    path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    return path


# ---------------------------------------------------------------- 자기보고

def test_item_keys_and_scales():
    assert PROFILE_ITEMS == ("M1p", "M2", "P1", "M3", "P2", "S5", "S6")
    assert dv.norm_item("M2", 10) == 1.0 and dv.norm_item("P1", 1) == 0.0 and dv.norm_item("P2", 4) == 0.5
    assert dv.norm_item("M1p", None) is None
    assert set(ITEM_SCALES) == set(PROFILE_ITEMS)


def test_self_report_pre_post_change_and_components(tmp_path):
    session(tmp_path, 1, "a")
    r = row(dv.analyze([tmp_path]), "a")
    assert (r["M2_pre"], r["M2_post"], r["M2_change"]) == (4, 7, 3)
    assert r["awareness_change"] == pytest.approx(0.2)                        # (6 − 4)/10
    assert r["disid_pre"] == pytest.approx((0.4 + 2 / 6) / 2, abs=1e-4)       # (norm(M2)+norm(P1))/2
    assert r["disid_post"] == pytest.approx((0.7 + 5 / 6) / 2, abs=1e-4)
    assert r["reactivity_change"] == pytest.approx(0.2)
    assert (r["P2_change"], r["S5_change"], r["S6_change"]) == (2, 2, -1)     # 태도는 따로, 원 척도


def test_disid_requires_both_items(tmp_path):
    session(tmp_path, 1, "a", rt=ratings({"M2": 4}, {"M2": 8}))
    r = row(dv.analyze([tmp_path]), "a")
    assert r["disid_pre"] is None and r["disid_change"] is None and "disid_partial" in r["flags"]
    assert r["P1_pre"] is None and r["P1_change"] is None and r["awareness_pre"] is None


def test_ambivalent_flag(tmp_path):
    session(tmp_path, 1, "a", rt=ratings({"S5": 5, "S6": 6}, {"S5": 6, "S6": 4}))
    session(tmp_path, 2, "b", rt=ratings({"S5": 5}, {"S5": 6}))
    res = dv.analyze([tmp_path])
    a, b = row(res, "a"), row(res, "b")
    assert a["ambivalent_pre"] is True and a["ambivalent_post"] is False
    assert b["ambivalent_pre"] is None
    assert res["summary"]["selfReport"]["ambivalentPre"] == 1


def test_old_phrase_file_aliases(tmp_path):
    session(tmp_path, 1, "a", rt=[["want_to_know", "post", 5, 300], ["withdraw_attention", "post", 2, 300]])
    r = row(dv.analyze([tmp_path]), "a")
    assert (r["S5_post"], r["S6_post"], r["S5_pre"]) == (5, 2, None)
    assert r["sr_aliases"] == "S5=want_to_know;S6=withdraw_attention"


def test_placement_rating_range_uses_item_scale(tmp_path):
    session(tmp_path, 1, "a", rt=[["M2", "pre", 0, 1], ["M2", "post", 10, 1]])
    session(tmp_path, 2, "b", rt=[["M2", "pre", 11, 1]])
    session(tmp_path, 3, "c", rt=[["own", "pre", 0, 1]])        # 러너 기본 문항은 그대로 1–7
    res = placement.analyze(tmp_path)
    flags = {s["session_id"]: s["flags"] for s in res["sessions"]}
    assert "rating_out_of_range" not in flags["a"]
    assert "rating_out_of_range" in flags["b"] and "rating_out_of_range" in flags["c"]


# ---------------------------------------------------------------- 행동

def test_quadrants_fixed_rule(tmp_path):
    session(tmp_path, 1, "nl", final=(1.0, 0.0, 0.8), late=5)
    session(tmp_path, 2, "fl", final=(3.0, 0.0, 0.8), late=5)
    session(tmp_path, 3, "fa", final=(3.0, 0.0, 0.8), late=60)
    session(tmp_path, 4, "na", final=(1.0, 0.0, 0.8), late=60)
    res = dv.analyze([tmp_path])
    assert {r["session_id"]: r["quadrant"] for r in res["rows"]} == {"nl": "NL", "fl": "FL", "fa": "FA", "na": "NA"}
    assert row(res, "fl")["quadrant_name"] == "far_facing"
    assert row(res, "fl")["delta_d_m"] == pytest.approx(1.5)    # 3.0 − 시작 1.5(manifest)
    assert res["summary"]["behavior"]["quadrantCounts"] == {"NL": 1, "FL": 1, "FA": 1, "NA": 1, "undetermined": 0}


def test_g_early_late_windows(tmp_path):
    session(tmp_path, 1, "a", early=60, late=5)
    r = row(dv.analyze([tmp_path]), "a")
    assert r["g_early"] == 0.0 and r["g_late"] == 1.0 and r["g_shift"] == 1.0
    assert r["g_whole"] == pytest.approx(0.5) and r["facing_source"] == "late_window"


def test_facing_threshold_and_deg_parameters(tmp_path):
    session(tmp_path, 1, "a", final=(3.0, 0.0, 0.8), late=18)
    assert row(dv.analyze([tmp_path]), "a")["quadrant"] == "FA"                    # 18° > 15°
    assert row(dv.analyze([tmp_path], facing_deg=20), "a")["quadrant"] == "FL"
    assert row(dv.analyze([tmp_path], facing_deg=20, facing_threshold=1.0), "a")["quadrant"] == "FA"


def test_view_condition_has_no_quadrant(tmp_path):
    session(tmp_path, 1, "v", condition="view")
    r = row(dv.analyze([tmp_path]), "v")
    assert r["quadrant"] is None and r["delta_d_m"] is None and r["regrab_count"] is None
    assert r["g_late"] is not None
    assert "2×2를 만들지 않음" in dv.CLAIMS["view_condition"]["cannot"]


def test_zero_delta_is_undetermined_and_median_split(tmp_path):
    session(tmp_path, 1, "a", final=(1.5, 0.0, 0.8), late=5)
    session(tmp_path, 2, "b", final=(2.0, 0.0, 0.8), late=5)
    session(tmp_path, 3, "c", final=(3.0, 0.0, 0.8), late=60)
    res = dv.analyze([tmp_path])
    assert row(res, "a")["quadrant"] is None and "quadrant_undetermined" in row(res, "a")["flags"]
    med = dv.analyze([tmp_path], distance_split="median", facing_split="median")
    # 거리 중앙값 2.0 → 2.0 이하는 가까운 쪽, 향함 중앙값 1.0 → 1.0 이하는 안 봄
    assert {r["session_id"]: r["quadrant"] for r in med["rows"]} == {"a": "NA", "b": "NA", "c": "FA"}
    assert med["summary"]["behavior"]["quadrantRule"]["distanceMedianM"] == 2.0


def test_stop_asymmetry_and_regrab(tmp_path):
    session(tmp_path, 1, "a", grab_count=3, approach=(1.0, 1.0, 1.0, 1.0), recede=(1.5, 1.5, 1.5, 1.5))
    r = row(dv.analyze([tmp_path]), "a")
    assert r["sd_asym_m"] == pytest.approx(-0.5) and r["sd_mean_m"] == pytest.approx(1.25)
    assert r["grab_count"] == 3 and r["regrab_count"] == 2 and r["first_grab_ms"] == 1500


def test_claims_note_far_facing():
    assert "Binder" in dv.CLAIMS["FL"]["cannot"] and "차분한 관찰" in dv.CLAIMS["FL"]["cannot"]
    assert set(dv.QUADRANTS) <= set(dv.CLAIMS)


def test_sessions_table_input(tmp_path):
    rec = tmp_path / "rec"
    session(rec, 1, "a", final=(3.0, 0.0, 0.8), early=60, late=5)
    placement.analyze(rec, tmp_path / "pl")
    res = dv.analyze(sessions_csv=tmp_path / "pl" / "placement_sessions.csv")
    r = row(res, "a")
    assert r["facing_source"] == "whole_condition" and "facing_from_whole_condition" in r["flags"]
    assert r["g_late"] == pytest.approx(0.5) and r["quadrant"] == "FA"     # 전체 0.5는 기준 0.5 초과가 아님
    assert r["M2_change"] == 3 and "start_distance_default" in r["flags"]


# ---------------------------------------------------------------- 언어

@needs_kiwi
def test_language_columns_and_matching(tmp_path):
    session(tmp_path, 1, "a")
    u = write_jsonl(tmp_path / "u.jsonl", [
        {"participant": 1, "session_id": "a", "when": "pre", "prompt": "L-A", "text": "나는 불안 덩어리다."},
        {"participant": "P001", "session_id": "a", "when": "post", "prompt": "L-A", "text": "내 안에 불안한 게 있어요."},
        {"session_id": "a", "when": "post", "prompt": "L-B", "text": "안 무서워요. 궁금해요."},
        {"session_id": "zzz", "when": "post", "prompt": "L-A", "text": "무거워요."}])
    res = dv.analyze([tmp_path], utterances=u)
    r = row(res, "a")
    assert (r["la_K2_pre"], r["la_K2_post"], r["la_K2_change"]) == (1, 0, -1)
    assert (r["la_K3_pre"], r["la_K3_post"], r["la_K3_change"]) == (0, 1, 1)
    assert r["lb_emotion_post"] == "~무섭;궁금" and r["lb_emotion_n_post"] == 1 and r["lb_emotion_pre"] is None
    assert any("맞추지 못했" in w for w in res["summary"]["warnings"])
    assert len(res["utterances"]) == 4


@needs_kiwi
def test_ambiguous_session_id_without_participant(tmp_path):
    session(tmp_path, 1, "same")
    session(tmp_path, 2, "same")
    u = write_jsonl(tmp_path / "u.jsonl", [{"session_id": "same", "when": "pre", "prompt": "L-A", "text": "무거워요."}])
    res = dv.analyze([tmp_path], utterances=u)
    assert all(r["la_K7_pre"] is None for r in res["rows"])


# ---------------------------------------------------------------- 수렴·사례

def test_convergence_small_n_is_null(tmp_path):
    session(tmp_path, 1, "a")
    session(tmp_path, 2, "b", final=(3.0, 0.0, 0.8))
    conv = dv.analyze([tmp_path])["convergence"]
    assert conv and all(c["rho"] is None for c in conv)
    assert {c["n"] for c in conv if c["var_a"] == "disid_change" and c["var_b"] == "delta_d_m"} == {2}


def test_convergence_spearman_values(tmp_path):
    for i, (m2post, d) in enumerate([(5, 1.0), (6, 2.0), (7, 2.5), (8, 3.0)], 1):
        post = dict(FULL_POST, M2=m2post)
        session(tmp_path, i, f"s{i}", final=(d, 0.0, 0.8), rt=ratings(FULL_PRE, post))
    res = dv.analyze([tmp_path])
    c = next(c for c in res["convergence"] if c["var_a"] == "disid_change" and c["var_b"] == "delta_d_m")
    assert c["n"] == 4 and c["rho"] == 1.0 and c["method_a"] == "self_report" and c["method_b"] == "behavior"
    same = next(c for c in res["convergence"] if c["var_a"] == "disid_change" and c["var_b"] == "la_K2_change")
    assert same["same_component"] is True and same["n"] == 0 and same["rho"] is None


@needs_kiwi
def test_case_rules(tmp_path):
    session(tmp_path, 1, "fa", final=(3.0, 0.0, 0.8), late=60)                       # disid ↑ + FA
    session(tmp_path, 2, "nl", final=(1.0, 0.0, 0.8), late=5)                        # P1·P2 높음 + NL
    session(tmp_path, 3, "fl", final=(3.0, 0.0, 0.8), late=5,
            rt=ratings(FULL_PRE, dict(FULL_POST, S6=6)))                              # FL + S6 높음
    u = write_jsonl(tmp_path / "u.jsonl", [
        {"session_id": "nl", "when": "post", "prompt": "L-A", "text": "제가 그 불안이에요."},
        {"session_id": "nl", "when": "pre", "prompt": "L-A", "text": "무거워요."}])
    res = dv.analyze([tmp_path], utterances=u)
    got = {(c["session_id"], c["rule"]) for c in res["cases"]}
    assert ("fa", "disid_up_but_FA") in got
    assert ("nl", "NL_differentiated") in got and ("nl", "P1_high_with_K2") in got
    assert ("nl", "disid_up_but_K2_up") in got
    assert ("fl", "FL_with_S6_high") in got and ("fl", "FL_with_S5_P2_high") in got
    assert res["summary"]["cases"]["notComputable"][0]["id"] == "sr_flat_behavior_changed"


# ---------------------------------------------------------------- 요약·출력

def test_summary_no_composite_no_significance(tmp_path):
    session(tmp_path, 1, "a")
    res = dv.analyze([tmp_path], out_dir=tmp_path / "out")
    text = (tmp_path / "out" / "differentiation_summary.json").read_text(encoding="utf-8")
    s = json.loads(text)
    assert s["version"] == "differentiation-profile/0.1" and s["descriptiveOnly"] is True
    assert "p_value" not in text and "pValue" not in text and "significan" not in text.lower()
    head = (tmp_path / "out" / "differentiation_profile.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert head == dv.PROFILE_COLUMNS
    assert not any("index" in h or "total_score" in h for h in head)
    assert s["syntheticData"] is False and res["rows"][0]["synthetic"] is False


def test_outputs_deterministic(tmp_path):
    session(tmp_path / "r", 1, "a")
    session(tmp_path / "r", 2, "b", final=(3.0, 0.0, 0.8), late=60)
    dv.analyze([tmp_path / "r"], out_dir=tmp_path / "o1")
    dv.analyze([tmp_path / "r"], out_dir=tmp_path / "o2")
    for name in ("differentiation_profile.csv", "differentiation_convergence.csv", "differentiation_summary.json"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()


def test_cli_main(tmp_path, capsys):
    session(tmp_path / "r", 1, "a")
    dv.main(["--records", str(tmp_path / "r"), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    assert "2×2(place)" in out and (tmp_path / "o" / "differentiation_profile.csv").is_file()


# ---------------------------------------------------------------- 합성 세션 생성기

def test_sim_generator_deterministic_and_marked_synthetic(tmp_path):
    t1 = sim_placement.generate(tmp_path / "a", seed=7, per_type=1, hz=2)
    sim_placement.generate(tmp_path / "b", seed=7, per_type=1, hz=2)
    files_a = sorted(p.relative_to(tmp_path / "a") for p in (tmp_path / "a").rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(tmp_path / "b") for p in (tmp_path / "b").rglob("*") if p.is_file())
    assert files_a == files_b
    assert all((tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes() for f in files_a)
    assert t1["synthetic"] is True and len(t1["sessions"]) == len(sim_placement.ARCHETYPES)
    for mf in (tmp_path / "a" / "records").rglob("manifest.json"):
        flags = json.loads(mf.read_text(encoding="utf-8"))["flags"]
        assert flags["synthetic"] is True and "효과의 근거가 아님" in flags["syntheticNote"]


def test_sim_generator_refuses_to_delete_unmarked_folder(tmp_path):
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(FileExistsError):
        sim_placement.generate(tmp_path, seed=1, per_type=1, hz=2)
    assert (tmp_path / "records" / "keep.txt").is_file()


def test_sim_records_read_cleanly_by_placement(tmp_path):
    sim_placement.generate(tmp_path, seed=3, per_type=1, hz=4)
    res = placement.analyze(tmp_path / "records")
    assert res["summary"]["records"]["included"] == 4
    assert all(s["flags"] == "" for s in res["sessions"]), [s["flags"] for s in res["sessions"]]


def test_sim_head_pose_geometry():
    q, dist, ang = sim_placement.head_pose((0.0, 1.6, 0.0), (1.0, 1.2, 1.0), 10.0)
    assert 0 < ang < 10.0 + 1e-9 and dist == pytest.approx((2 + 0.16) ** 0.5)
    assert placement.yaw_deg(*q) == pytest.approx(45.0 + 10.0, abs=1e-6)


@needs_kiwi
def test_sim_pipeline_recovers_assumed_types(tmp_path):
    check = sim_placement.run_pipeline(tmp_path, seed=20261123, per_type=2, hz=4, extra_records=None)
    by = check["byArchetype"]
    for arch in ("near_look", "far_look", "far_away"):
        assert by[arch]["match_fixed"] == 2, by[arch]
    assert by["view_only"]["assigned_fixed"] == {"None": 2}
    assert "효과의 근거가 아님" in check["note"]
    s = json.loads((tmp_path / "analysis" / "differentiation" / "differentiation_summary.json").read_text(encoding="utf-8"))
    assert s["syntheticData"] is True and s["syntheticNote"] == dv.SYNTHETIC_NOTE


@pytest.mark.skipif(not UNITY_RECORDS.is_dir(), reason="Unity 합성 기록(docs/validation/placement/records) 없음")
def test_unity_records_format_compatible():
    res = dv.analyze([UNITY_RECORDS])
    assert len(res["rows"]) == 5 and all(r["included"] for r in res["rows"])
    place = [r for r in res["rows"] if r["condition"] == "place"]
    assert len(place) == 1 and place[0]["quadrant"] in dv.QUADRANTS and place[0]["g_late"] is not None
    assert place[0]["S5_post"] is not None and "S5=want_to_know" in place[0]["sr_aliases"]
