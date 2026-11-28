"""배치 실험(RQ V4) 기록 요약(ifs_chatbot.eval.placement) 테스트.
기록은 모두 합성(AGENTS.md 6): 계약 `ifs-placement/0.1` 형식대로 임시 폴더에 손으로 만든 값만 쓴다."""
import csv
import json
import math
from pathlib import Path

import pytest

from ifs_chatbot.eval import placement
from ifs_chatbot.eval.placement import analyze, cohen_d, nearest_ring, norm_azimuth, pearson, yaw_deg

HEAD_COLS = ["time_ms", "phase", "head_x", "head_y", "head_z", "head_qx", "head_qy", "head_qz", "head_qw",
             "obj_x", "obj_y", "obj_z", "distance_m", "angle_deg"]
OBJ_COLS = ["time_ms", "phase", "obj_x", "obj_y", "obj_z", "distance_m", "azimuth_deg", "height_m", "state"]
STOP_COLS = ["trial", "practice", "direction", "start_distance_m", "speed_mps", "stop_distance_m", "rt_ms", "timed_out"]
START = (0.0, 0.8, 1.5)          # 정면 1.5 m, 높이 0.8 m


def _csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def yaw_quat(deg):
    """y축 회전 쿼터니언 (qx, qy, qz, qw)."""
    h = math.radians(deg) / 2
    return (0.0, math.sin(h), 0.0, math.cos(h))


def polar(distance, az_deg, height):
    a = math.radians(az_deg)
    return (distance * math.sin(a), height, distance * math.cos(a))


def stop_rows(approach, recede, practice=(0.3, 0.3)):
    """연습 2회(값 0.3 — 섞이면 평균이 크게 틀어짐) + 방향 교차 본 시행. None은 timeout."""
    rows = [[1, 1, "approach", 3.0, 0.25, practice[0], 900, 0], [2, 1, "recede", 0.5, 0.25, practice[1], 900, 0]]
    t = 3
    for a, r in zip(approach, recede):
        for d, v, s in (("approach", a, 3.0), ("recede", r, 0.5)):
            rows.append([t, 0, d, s, 0.25, "" if v is None else v, 1000, 1 if v is None else 0])
            t += 1
    return rows


DEFAULT_HEAD = [  # (yaw, distance_m, angle_deg) — 조건 단계
    (-30, 1.0, 5), (0, 1.2, 10), (30, 1.4, 20), (60, 1.6, 40)]


def make_placement_session(root, pnum=1, sid="sess-a", condition="place", control=None, utc="20261122-010000",
                           final=(2.05, 30.0, 0.8), path=None, path_length=None, grab_count=None,
                           approach=(1.2, 1.4, 1.0, 1.3), recede=(1.6, 1.8, 1.7, None),
                           head=None, ratings=None, show_rings=True, rings=(1.0, 2.0, 3.0), completed=True,
                           omit=(), version="ifs-placement/0.1", draft_keys=(), auto_mode=False, events=None,
                           placement_override=None, manifest_extra=None, aborted_at="stop_distance"):
    """placement/P###/<sid>/<utc>/ 아래에 합성 기록 한 벌을 쓴다.
    path = 조건 단계 물체 위치 목록(기본: place·system_move·replay는 시작 → 최종 직선, static은 시작 고정)."""
    control = control or ("none" if condition == "place" else "static")
    folder = root / "placement" / f"P{pnum:03d}" / sid / utc
    folder.mkdir(parents=True)
    if control == "static" and condition == "view":
        final = (1.5, 0.0, 0.8)
    end = polar(*final)
    if path is None:
        path = [START] if control == "static" else [START, end]
    computed = sum(math.dist(path[i], path[i + 1]) for i in range(len(path) - 1))
    manifest = {
        "recordVersion": version, "participantNumber": pnum, "sessionId": sid, "specFile": "synthetic.json",
        "specSha256": "0" * 64, "startedAtUtc": utc, "unityVersion": "test",
        "headSource": "desktop", "inputSource": "auto" if auto_mode else "desktop",
        "condition": condition, "controlMode": control,
        "space": {"floorRadiusM": 4.0, "ringRadiiM": list(rings), "showRings": show_rings,
                  "startDistanceM": 1.5, "startHeightM": 0.8},
        "stopDistance": {"speedMps": 0.25, "approachStartM": 3.0, "recedeStartM": 0.5, "trialsPerDirection": 4,
                         "practiceTrials": 2, "minM": 0.2, "maxM": 3.5},
        "replaySource": None, "systemMoveTarget": None,
        "taskText": {"file": "placement_task.v0.json", "version": "0.1", "draftCount": len(draft_keys),
                     "draftKeys": list(draft_keys)},
        "config": {"headSampleHz": 20}, "flags": {"autoMode": auto_mode},
    }
    manifest.update(manifest_extra or {})
    files = {}
    files["manifest.json"] = json.dumps(manifest)
    head = DEFAULT_HEAD if head is None else head
    hrows = [[0, "baseline", 0, 1.6, 0, *yaw_quat(170), *START, 9.9, 90]]   # 조건 단계가 아님 — 무시돼야 함
    for i, (yw, d, a) in enumerate(head):
        hrows.append([1000 + 50 * i, "condition", 0, 1.6, 0, *yaw_quat(yw), *end, d, a])
    hrows.append([99000, "stop_distance", 0, 1.6, 0, *yaw_quat(-170), *START, 0.1, 0])
    orows = [[0, "baseline", *START, 1.5, 0, 0.8, "idle"]]
    for i, p in enumerate(path):
        d = math.hypot(p[0], p[2])
        orows.append([1000 + 50 * i, "condition", *p, round(d, 6), round(math.degrees(math.atan2(p[0], p[2])), 6),
                      p[1], "held" if condition == "place" else "system"])
    orows.append([99000, "stop_distance", 0, 0.8, 3.0, 3.0, 0, 0.8, "stop"])   # 멈춤 거리 이동 — 무시돼야 함
    pl = {"condition": condition, "controlMode": control, "phaseDurationMs": 90000,
          "finalX": end[0], "finalY": end[1], "finalZ": end[2], "finalDistanceM": final[0],
          "finalAzimuthDeg": final[1], "finalHeightM": final[2],
          "grabCount": (2 if condition == "place" else 0) if grab_count is None else grab_count,
          "firstGrabMs": 1500 if condition == "place" else None, "heldMs": 12000 if condition == "place" else 0,
          "pathLengthM": computed if path_length is None else path_length, "confirmed": True, "confirmMs": 80000}
    pl.update(placement_override or {})
    if ratings is None:
        ratings = [["self_decided", "check", 6, 800], ["know_more", "pre", 4, 900], ["know_more", "post", 5, 700]]
    if events is None:
        events = [[0, "phase", "setup"], [1000, "phase", "condition"], [99500, "phase", "done"]]
    traj = {"version": "ifs-trajectory/0.1", "sourceSessionId": sid, "sampleHz": 20, "startDistanceM": 1.5,
            "startHeightM": 0.8, "samples": [{"t_ms": 50 * i, "x": p[0], "y": p[1], "z": p[2]}
                                             for i, p in enumerate(path)]}
    summ = {"completed": completed, "abortedAt": None if completed else aborted_at, "endedAtUtc": utc}
    writers = {
        "headpose.csv": lambda p: _csv(p, HEAD_COLS, hrows),
        "objpose.csv": lambda p: _csv(p, OBJ_COLS, orows),
        "events.csv": lambda p: _csv(p, ["time_ms", "event", "detail"], events),
        "placement.json": lambda p: p.write_text(json.dumps(pl), encoding="utf-8"),
        "stopdistance.csv": lambda p: _csv(p, STOP_COLS, stop_rows(approach, recede)),
        "ratings.csv": lambda p: _csv(p, ["item", "when", "rating", "rt_ms"], ratings),
        "trajectory.json": lambda p: p.write_text(json.dumps(traj), encoding="utf-8"),
        "summary.json": lambda p: p.write_text(json.dumps(summ), encoding="utf-8"),
    }
    (folder / "manifest.json").write_text(files["manifest.json"], encoding="utf-8")
    for name, write in writers.items():
        if name not in omit:
            write(folder / name)
    return folder


def make_ownership_session(root):
    folder = root / "ownership" / "P001" / "own-a" / "20261122-000000"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({"recordVersion": "ifs-ownership/0.2", "participantNumber": 1,
                                                      "sessionId": "own-a"}), encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps({"completed": True}), encoding="utf-8")


def four_conditions(root):
    make_placement_session(root, 1, "s-place", "place")
    make_placement_session(root, 2, "s-static", "view", "static")
    make_placement_session(root, 3, "s-replay", "view", "replay", final=(2.05, 30.0, 0.8))
    make_placement_session(root, 4, "s-sysmove", "view", "system_move", final=(2.5, -45.0, 1.0))


def row(res, sid):
    return next(s for s in res["sessions"] if s["session_id"] == sid)


# ---------------------------------------------------------------- 계산 도우미

def test_yaw_from_quaternion():
    for deg in (-170, -30, 0, 45, 90, 179):
        assert yaw_deg(*yaw_quat(deg)) == pytest.approx(deg)
    # 고개를 90° 숙여 정면이 수직이면 yaw를 정할 수 없다
    h = math.radians(90) / 2
    assert yaw_deg(math.sin(h), 0.0, 0.0, math.cos(h)) is None


def test_norm_azimuth_and_nearest_ring():
    assert norm_azimuth(190) == pytest.approx(-170)
    assert norm_azimuth(-180) == 180
    assert norm_azimuth(540) == 180
    assert nearest_ring(2.05, [1.0, 2.0, 3.0]) == (2.0, pytest.approx(0.05))
    assert nearest_ring(1.5, [1.0, 2.0]) == (1.0, 0.5)      # 같은 차이면 작은 반지름
    assert nearest_ring(None, [1.0]) == (None, None)
    assert nearest_ring(1.0, []) == (None, None)


def test_cohen_d_hand_computed():
    # A: 평균 1.2 sd 0.2, B: 평균 1.6 sd 0.2 → d = −2.0, se = √(6/9 + 4/12) = 1.0
    e = cohen_d([1.0, 1.2, 1.4], [1.4, 1.6, 1.8])
    assert e["d"] == pytest.approx(-2.0)
    assert e["sdPooled"] == pytest.approx(0.2)
    assert e["ci95_normal_approx"]["low"] == pytest.approx(-2.0 - 1.96, abs=1e-3)
    assert e["ci95_normal_approx"]["high"] == pytest.approx(-2.0 + 1.96, abs=1e-3)
    assert e["ci_method"] == "normal_approx"
    # Hedges g: df = 4, J = 1 − 3/(4·4 − 1) = 0.8 → g = −1.6
    assert e["hedges_g"] == pytest.approx(-1.6)
    assert e["meanDiff"] == pytest.approx(-0.4)


def test_cohen_d_small_n_and_zero_variance():
    e = cohen_d([1.0], [1.4, 1.6])
    assert e["d"] is None and e["hedges_g"] is None and e["ci95_normal_approx"] is None
    assert e["nA"] == 1 and e["meanA"] == 1.0
    assert cohen_d([], [])["d"] is None
    z = cohen_d([1.0, 1.0], [1.0, 1.0])
    assert z["d"] is None and z["sdPooled"] == 0 and z["hedges_g"] is None


def test_pearson_hand_computed_and_small_n():
    assert pearson([1, 2, 3], [1.0, 1.4, 1.2]) == pytest.approx(0.5)
    assert pearson([1, 2], [1, 2]) is None
    assert pearson([1, 2, 3], [5, 5, 5]) is None


# ---------------------------------------------------------------- 세션 발견

def test_discover_ignores_ownership_and_picks_completed(tmp_path):
    make_ownership_session(tmp_path)
    make_placement_session(tmp_path, 1, "sess-a", utc="20261122-010000")
    make_placement_session(tmp_path, 1, "sess-a", utc="20261122-020000", completed=False)
    (tmp_path / "junk").mkdir()
    (tmp_path / "junk" / "manifest.json").write_text("{not json", encoding="utf-8")
    res = analyze(tmp_path)
    assert [s["session_id"] for s in res["sessions"]] == ["sess-a"]
    s = res["sessions"][0]
    assert s["completed"] is True and s["record_folder"].endswith("20261122-010000")
    assert res["summary"]["records"]["skipped"] == 1
    assert res["summary"]["skipped"][0]["reason"] == "duplicate"


# ---------------------------------------------------------------- 세션 행

def test_place_session_final_pose_and_rings(tmp_path):
    make_placement_session(tmp_path, final=(2.05, 30.0, 0.8))
    s = analyze(tmp_path)["sessions"][0]
    assert s["condition"] == "place" and s["control_mode"] == "none"
    assert s["final_distance_m"] == pytest.approx(2.05)
    assert s["final_azimuth_deg"] == pytest.approx(30.0)
    assert s["final_height_m"] == pytest.approx(0.8)
    assert s["grab_count"] == 2 and s["first_grab_ms"] == 1500 and s["held_ms"] == 12000
    assert s["confirmed"] is True
    assert s["nearest_ring_m"] == 2.0 and s["ring_offset_m"] == pytest.approx(0.05)
    expected_path = math.dist(START, polar(2.05, 30.0, 0.8))
    assert s["obj_path_from_objpose_m"] == pytest.approx(expected_path, abs=1e-4)
    assert s["flags"] == ""


def test_rings_hidden_leave_ring_columns_blank(tmp_path):
    make_placement_session(tmp_path, show_rings=False)
    s = analyze(tmp_path)["sessions"][0]
    assert s["show_rings"] is False and s["nearest_ring_m"] is None and s["ring_offset_m"] is None


def test_final_falls_back_to_objpose_when_placement_missing(tmp_path):
    make_placement_session(tmp_path, final=(2.5, -45.0, 1.0), omit=("placement.json",))
    s = analyze(tmp_path)["sessions"][0]
    assert s["final_distance_m"] == pytest.approx(2.5)
    assert s["final_azimuth_deg"] == pytest.approx(-45.0)
    assert s["grab_count"] is None and s["path_length_m"] is None
    assert "missing_file:placement.json" in s["flags"] and "final_from_objpose" in s["flags"]


def test_stop_distance_excludes_practice_and_timeout(tmp_path):
    make_placement_session(tmp_path, approach=(1.2, 1.4, 1.0, 1.3), recede=(1.6, 1.8, 1.7, None))
    res = analyze(tmp_path)
    s = res["sessions"][0]
    assert s["stop_approach_mean_m"] == pytest.approx(1.225)
    assert s["stop_recede_mean_m"] == pytest.approx(1.7)
    assert s["stop_mean_m"] == pytest.approx((1.225 + 1.7) / 2, abs=1e-4)
    assert s["stop_n_valid"] == 7 and s["stop_n_timeout"] == 1
    vals = [1.2, 1.4, 1.0, 1.3, 1.6, 1.8, 1.7]
    m = sum(vals) / 7
    assert s["stop_sd_m"] == pytest.approx(math.sqrt(sum((v - m) ** 2 for v in vals) / 6), abs=1e-4)
    trials = res["stop_trials"]
    assert len(trials) == 10
    assert sum(t["included"] for t in trials) == 7
    assert all(not t["included"] for t in trials if t["practice"] or t["timed_out"])
    assert all(t["session_id"] == "sess-a" and t["condition"] == "place" for t in trials)


def test_stop_mean_blank_when_one_direction_missing(tmp_path):
    make_placement_session(tmp_path, approach=(1.2, 1.4), recede=(None, None))
    s = analyze(tmp_path)["sessions"][0]
    assert s["stop_approach_mean_m"] == pytest.approx(1.3)
    assert s["stop_recede_mean_m"] is None and s["stop_mean_m"] is None
    assert "stop_trials_short:approach" in s["flags"] and "stop_trials_short:recede" in s["flags"]


def test_head_behavior_condition_phase_only(tmp_path):
    make_placement_session(tmp_path)
    s = analyze(tmp_path)["sessions"][0]
    assert s["head_obj_distance_mean_m"] == pytest.approx(1.3)     # 1.0·1.2·1.4·1.6, baseline 9.9 제외
    assert s["head_facing_ratio"] == pytest.approx(0.5)           # 5·10 ≤ 15° < 20·40
    assert "gaze_ratio" not in s                                   # 눈 추적이 아니라 머리 방향 — 옛 이름은 쓰지 않는다
    assert s["head_yaw_range_deg"] == pytest.approx(90.0)         # −30…60, ±170 제외
    s30 = analyze(tmp_path, facing_deg=30)["sessions"][0]
    assert s30["head_facing_ratio"] == pytest.approx(0.75)
    assert analyze(tmp_path, gaze_deg=30)["sessions"][0]["head_facing_ratio"] == pytest.approx(0.75)   # 옛 인자 이름(별칭)


def test_yaw_range_wraps_around_back(tmp_path):
    make_placement_session(tmp_path, head=[(170, 1.0, 5), (-170, 1.0, 5)])
    assert analyze(tmp_path)["sessions"][0]["head_yaw_range_deg"] == pytest.approx(20.0)


def test_rating_columns_union(tmp_path):
    make_placement_session(tmp_path, 1, "a", ratings=[["self_decided", "check", 6, 800],
                                                       ["know_more", "pre", 3, 900], ["know_more", "pre", 4, 950]])
    make_placement_session(tmp_path, 2, "b", "view", ratings=[["withdraw", "post", 2, 700]])
    res = analyze(tmp_path)
    rating_cols = [c for c in res["columns"] if c.startswith("rating_")]
    assert rating_cols == ["rating_know_more_pre", "rating_self_decided_check", "rating_withdraw_post"]
    a, b = row(res, "a"), row(res, "b")
    assert a["rating_know_more_pre"] == 4          # 같은 (item, when)은 마지막 행
    assert a["rating_withdraw_post"] is None
    assert b["rating_withdraw_post"] == 2 and b["rating_self_decided_check"] is None
    assert res["columns"][-2:] == ["obj_path_from_objpose_m", "flags"]


def test_old_want_move_records_still_read_with_new_records(tmp_path):
    """G60: 문구 파일 0.6에서 want_move를 뺐다. 0.5 기록(want_move 행 있음)과 0.6 기록을 함께 읽으면
    열은 합집합으로 남고, 0.6 기록의 want_move 칸은 빈 값이다(0으로 채우거나 짐작하지 않음, 원칙 2)."""
    old = [["placed_by_me", "check", 4, 800], ["place_fit", "check", 2, 700], ["want_move", "check", 6, 600]]
    new = [["placed_by_me", "check", 5, 800], ["place_fit", "check", 3, 700]]
    make_placement_session(tmp_path, 1, "old", ratings=old,
                           manifest_extra={"taskText": {"file": "placement_task.v0.json", "version": "0.5", "draftCount": 0, "draftKeys": []}})
    make_placement_session(tmp_path, 2, "new", "view", ratings=new,
                           manifest_extra={"taskText": {"file": "placement_task.v0.json", "version": "0.6", "draftCount": 0, "draftKeys": []}})
    res = analyze(tmp_path)
    assert "rating_want_move_check" in res["columns"]
    o, n = row(res, "old"), row(res, "new")
    assert o["rating_want_move_check"] == 6 and o["rating_place_fit_check"] == 2
    assert n["rating_want_move_check"] is None and n["rating_place_fit_check"] == 3
    assert "rating_out_of_range" not in n["flags"]
    # 0.6 기록만 있으면 want_move 열 자체가 없다
    only_new = tmp_path / "only_new"
    make_placement_session(only_new, 3, "new2", ratings=new)
    assert "rating_want_move_check" not in analyze(only_new)["columns"]


def test_objpose_path_mismatch_flag(tmp_path):
    make_placement_session(tmp_path, 1, "ok")
    make_placement_session(tmp_path, 2, "bad", path_length=5.0)
    res = analyze(tmp_path)
    assert "objpose_path_mismatch" not in row(res, "ok")["flags"]
    assert "objpose_path_mismatch" in row(res, "bad")["flags"]


def test_view_static_has_zero_path_and_start_position(tmp_path):
    make_placement_session(tmp_path, condition="view", control="static")
    s = analyze(tmp_path)["sessions"][0]
    assert s["grab_count"] == 0 and s["path_length_m"] == 0
    assert s["obj_path_from_objpose_m"] == 0
    assert s["final_distance_m"] == pytest.approx(1.5)
    assert s["first_grab_ms"] is None


# ---------------------------------------------------------------- 빠진 파일·중단 세션·형식

def test_missing_and_empty_files_do_not_crash(tmp_path):
    folder = make_placement_session(tmp_path, omit=("headpose.csv", "stopdistance.csv", "trajectory.json"))
    (folder / "ratings.csv").write_text("", encoding="utf-8")
    (folder / "events.csv").write_text("{broken", encoding="utf-8")
    (folder / "placement.json").write_text("{broken", encoding="utf-8")
    s = analyze(tmp_path)["sessions"][0]
    for name in ("headpose.csv", "stopdistance.csv", "trajectory.json"):
        assert f"missing_file:{name}" in s["flags"]
    assert "empty_file:ratings.csv" in s["flags"]
    assert "unreadable_file:placement.json" in s["flags"]
    assert s["head_facing_ratio"] is None and s["stop_mean_m"] is None and s["stop_n_valid"] == 0
    assert s["final_distance_m"] == pytest.approx(2.05)           # objpose 마지막 행으로 대신


def test_aborted_session_flagged_and_excluded(tmp_path):
    make_placement_session(tmp_path, 1, "done")
    make_placement_session(tmp_path, 2, "aborted", completed=False)
    make_placement_session(tmp_path, 3, "nosummary", omit=("summary.json",))
    res = analyze(tmp_path)
    assert row(res, "aborted")["completed"] is False and row(res, "aborted")["aborted_at"] == "stop_distance"
    assert "missing_file:summary.json" in row(res, "nosummary")["flags"]
    rec = res["summary"]["records"]
    assert rec == {"sessions": 3, "included": 1, "excludedIncomplete": 2, "excludedPartialCondition": 0, "skipped": 0}
    assert row(res, "aborted")["condition_complete"] is True      # 옛 기록: 조건 단계 뒤(stop_distance)에서 중단
    assert "partial_condition" not in row(res, "aborted")["flags"]
    assert res["summary"]["summaries"]["byCondition"]["place"]["n"] == 1
    assert any("미완료 세션 2개" in w for w in res["summary"]["warnings"])


def test_version_and_condition_mismatch_flags(tmp_path):
    make_placement_session(tmp_path, 1, "v", version="ifs-placement/0.9")
    make_placement_session(tmp_path, 2, "c", placement_override={"condition": "view"})
    make_placement_session(tmp_path, 3, "w", events=[[0, "phase", "setup"], [10, "warning", "x"], [20, "warning", "y"]])
    res = analyze(tmp_path)
    assert "version_mismatch" in row(res, "v")["flags"]
    assert "condition_mismatch" in row(res, "c")["flags"]
    assert "runner_warning:2" in row(res, "w")["flags"]


# ---------------------------------------------------------------- 요약

def test_four_conditions_counts_and_descriptives(tmp_path):
    four_conditions(tmp_path)
    make_ownership_session(tmp_path)
    res = analyze(tmp_path)
    summ = res["summary"]
    assert summ["version"] == "placement-summary/0.1"
    assert summ["nByConditionControl"]["included"] == {"place/none": 1, "view/replay": 1, "view/static": 1,
                                                       "view/system_move": 1}
    view = summ["summaries"]["byCondition"]["view"]
    assert view["n"] == 3
    assert view["final_distance_m"]["n"] == 3
    assert view["final_distance_m"]["mean"] == pytest.approx((1.5 + 2.05 + 2.5) / 3, abs=1e-4)
    assert view["final_distance_m"]["min"] == pytest.approx(1.5)
    assert "view/system_move" in summ["summaries"]["byConditionControl"]


def test_condition_effect_size_and_correlation(tmp_path):
    for i, (v, fd) in enumerate([(1.0, 1.0), (1.4, 2.0), (1.2, 3.0)], 1):
        make_placement_session(tmp_path, i, f"p{i}", "place", final=(fd, 0.0, 0.8),
                               approach=(v,) * 4, recede=(v,) * 4)
    for i, v in enumerate([1.4, 1.6, 1.8], 4):
        make_placement_session(tmp_path, i, f"v{i}", "view", "static", approach=(v,) * 4, recede=(v,) * 4)
    s = analyze(tmp_path)["summary"]["summaries"]
    e = s["stopConditionEffect"]["stop_mean_m"]["place_vs_view"]
    assert e["nA"] == 3 and e["nB"] == 3
    assert e["d"] == pytest.approx(-2.0, abs=1e-3)
    assert e["ci95_normal_approx"]["low"] == pytest.approx(-3.96, abs=1e-2)
    assert e["ci95_normal_approx"]["high"] == pytest.approx(-0.04, abs=1e-2)
    assert e["hedges_g"] == pytest.approx(-1.6, abs=1e-3)
    assert s["stopConditionEffect"]["stop_mean_m"]["place_vs_view_static"]["d"] == pytest.approx(-2.0, abs=1e-3)
    c = s["placeDistanceStopCorrelation"]["final_distance_m~stop_mean_m"]
    assert c["n"] == 3 and c["r"] == pytest.approx(0.5)
    d = s["stopDirectionEffect"]["all"]
    assert d["n"] == 6 and d["mean"] == 0


def test_direction_effect_and_ring_summary(tmp_path):
    make_placement_session(tmp_path, 1, "a", final=(2.05, 0, 0.8), approach=(1.0,) * 4, recede=(1.4,) * 4)
    make_placement_session(tmp_path, 2, "b", final=(2.5, 0, 0.8), approach=(1.2,) * 4, recede=(1.4,) * 4)
    make_placement_session(tmp_path, 3, "c", final=(0.95, 0, 0.8), show_rings=False)
    s = analyze(tmp_path)["summary"]["summaries"]
    d = s["stopDirectionEffect"]["all"]
    assert d["n"] == 3
    assert d["mean"] == pytest.approx((-0.4 - 0.2 + (1.225 - 1.7)) / 3, abs=1e-4)
    ring = s["ringClustering"]
    assert ring["nWithRings"] == 2 and ring["nWithin"] == 1 and ring["proportionWithin"] == 0.5
    assert ring["nRingsHidden"] == 1
    assert ring["uniformReference"] == pytest.approx(0.6 / 4.0)   # 고리 3개 × 0.2 m / 바닥 반지름 4 m


def test_small_n_gives_nulls_not_errors(tmp_path):
    make_placement_session(tmp_path, approach=(1.2,), recede=(1.6,))
    res = analyze(tmp_path)
    s = res["summary"]["summaries"]
    assert s["stopConditionEffect"]["stop_mean_m"]["place_vs_view"]["d"] is None
    assert s["placeDistanceStopCorrelation"]["final_distance_m~stop_mean_m"]["r"] is None
    assert s["byCondition"]["place"]["stop_mean_m"]["sd"] is None
    assert s["byCondition"]["view"]["n"] == 0 and s["byCondition"]["view"]["stop_mean_m"]["mean"] is None
    assert res["sessions"][0]["stop_sd_m"] == pytest.approx(math.sqrt(0.08), abs=1e-4)
    # 기록이 하나도 없어도 죽지 않는다
    empty = tmp_path / "empty"
    empty.mkdir()
    r0 = analyze(empty, tmp_path / "out0")
    assert r0["summary"]["records"]["sessions"] == 0
    assert (tmp_path / "out0" / "placement_sessions.csv").read_text(encoding="utf-8").startswith("participant,")


def test_draft_and_auto_mode_reported(tmp_path):
    make_placement_session(tmp_path, 1, "a", draft_keys=("instruction", "item_check"), auto_mode=True)
    make_placement_session(tmp_path, 2, "b")
    res = analyze(tmp_path)
    assert row(res, "a")["draft_phrases"] == 2 and row(res, "a")["auto_mode"] is True
    assert row(res, "a")["input_source"] == "auto"
    assert res["summary"]["draftPhraseSessions"] == 1 and res["summary"]["autoModeSessions"] == 1
    assert any("초안 문구" in w for w in res["summary"]["warnings"])


def test_cli_round_trip(tmp_path, capsys):
    rec = tmp_path / "records"
    four_conditions(rec)
    make_ownership_session(rec)
    out = tmp_path / "out"
    placement.main(["--records", str(rec), "--out", str(out), "--facing-deg", "15"])
    assert "세션 4개" in capsys.readouterr().out
    with (out / "placement_sessions.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert {r["condition"] + "/" + r["control_mode"] for r in rows} == {
        "place/none", "view/static", "view/replay", "view/system_move"}
    p = next(r for r in rows if r["condition"] == "place")
    assert p["completed"] == "1" and p["ring_offset_m"] == "0.05" and p["rating_know_more_pre"] == "4"
    assert p["condition_complete"] == "1" and "head_facing_ratio" in p and "gaze_ratio" not in p
    with (out / "stop_trials.csv").open(encoding="utf-8", newline="") as f:
        trials = list(csv.DictReader(f))
    assert len(trials) == 40 and set(trials[0]) == set(placement.STOP_COLUMNS)
    summ = json.loads((out / "placement_summary.json").read_text(encoding="utf-8"))
    assert summ["version"] == "placement-summary/0.1" and summ["records"]["sessions"] == 4
    text = json.dumps(summ, ensure_ascii=False)
    assert str(tmp_path) not in text and str(tmp_path).replace("\\", "/") not in text   # 로컬 절대 경로 없음
    assert "유의" not in text and "p_value" not in text and "pValue" not in text


def test_deterministic_output(tmp_path):
    four_conditions(tmp_path / "r")
    analyze(tmp_path / "r", tmp_path / "o1")
    analyze(tmp_path / "r", tmp_path / "o2")
    for name in ("placement_sessions.csv", "stop_trials.csv", "placement_summary.json"):
        assert (tmp_path / "o1" / name).read_bytes() == (tmp_path / "o2" / name).read_bytes()


# ---------------------------------------------------------------- CP7 반영: 중단된 조건 단계·물체 반지름·설정 일치

def test_partial_condition_blanks_condition_metrics_and_is_excluded(tmp_path):
    make_placement_session(tmp_path, 1, "done")
    make_placement_session(tmp_path, 2, "cut", completed=False, aborted_at="condition",
                           placement_override={"conditionCompleted": False, "phaseDurationMs": 2000})
    # summary는 완료인데 조건 단계가 끝까지 가지 않았다고 적힌 기록(계약상 생기면 안 되지만 분석기는 막아야 함)
    make_placement_session(tmp_path, 3, "odd", placement_override={"conditionCompleted": False})
    res = analyze(tmp_path)
    for sid in ("cut", "odd"):
        s = row(res, sid)
        assert s["condition_complete"] is False and "partial_condition" in s["flags"]
        for k in placement.CONDITION_METRICS:
            assert s[k] is None, (sid, k)
        assert s["stop_approach_mean_m"] == pytest.approx(1.225)   # 조건 단계 밖 지표는 그대로
    assert row(res, "done")["condition_complete"] is True and row(res, "done")["final_distance_m"] is not None
    rec = res["summary"]["records"]
    assert rec["included"] == 1 and rec["excludedIncomplete"] == 1 and rec["excludedPartialCondition"] == 1
    place = res["summary"]["summaries"]["byCondition"]["place"]
    assert place["n"] == 1 and place["final_distance_m"]["n"] == 1 and place["stop_mean_m"]["n"] == 1
    assert any("partial_condition" in w and "P003/odd" in w for w in res["summary"]["warnings"])


def test_condition_complete_inferred_for_old_records(tmp_path):
    make_placement_session(tmp_path, 1, "ok")
    make_placement_session(tmp_path, 2, "in-cond", completed=False, aborted_at="condition")
    make_placement_session(tmp_path, 3, "after", completed=False, aborted_at="post_items")
    make_placement_session(tmp_path, 4, "before", completed=False, aborted_at="baseline", omit=("placement.json",))
    res = analyze(tmp_path)
    assert row(res, "ok")["condition_complete"] is True
    assert row(res, "in-cond")["condition_complete"] is False and row(res, "in-cond")["final_distance_m"] is None
    assert row(res, "after")["condition_complete"] is True and row(res, "after")["final_distance_m"] is not None
    assert row(res, "before")["condition_complete"] is False


def test_object_radius_column(tmp_path):
    make_placement_session(tmp_path, 1, "r", manifest_extra={"object": {"boundingRadiusM": 0.2512}})
    make_placement_session(tmp_path, 2, "none", manifest_extra={"object": {"boundingRadiusM": None}})
    make_placement_session(tmp_path, 3, "old")
    res = analyze(tmp_path)
    assert row(res, "r")["object_radius_m"] == pytest.approx(0.2512)
    assert row(res, "none")["object_radius_m"] is None and row(res, "old")["object_radius_m"] is None
    assert "object_radius_m" in res["columns"]


def test_object_shape_columns_only_when_present(tmp_path):
    """G72: manifest object.boundsM·object.proportions → 크기·모양 공변량 열. 그런 기록이 없으면 열 자체가 없다(출력 불변)."""
    make_placement_session(tmp_path, 1, "old")
    res = analyze(tmp_path)
    assert "object_width_m" not in res["columns"] and "proportions_x" not in row(res, "old")
    make_placement_session(tmp_path, 2, "wide", manifest_extra={"object": {
        "boundingRadiusM": 0.3, "boundsM": {"x": 0.6, "y": 0.18, "z": 0.6},
        "proportions": {"x": 1.0, "y": 0.3, "z": 1.0, "raw": {"x": 1.0, "y": 0.3, "z": 1.0}, "source": "said", "axisSaid": True}}})
    make_placement_session(tmp_path, 3, "plain", manifest_extra={"object": {"boundingRadiusM": 0.2, "boundsM": {"x": 0.4, "y": 0.4, "z": 0.4}}})
    res = analyze(tmp_path)
    w, pl, old = row(res, "wide"), row(res, "plain"), row(res, "old")
    assert (w["object_width_m"], w["object_height_m"], w["object_depth_m"]) == (0.6, 0.18, 0.6)
    assert (w["proportions_x"], w["proportions_y"], w["proportions_z"]) == (1.0, 0.3, 1.0)
    assert w["proportions_source"] == "said" and w["proportions_axis_said"] is True
    assert pl["object_height_m"] == 0.4 and pl["proportions_x"] is None and pl["proportions_source"] is None
    assert old["object_width_m"] is None
    assert res["columns"][-len(res["columns"]):].count("proportions_source") == 1


def test_config_mismatch_between_included_sessions(tmp_path):
    cfg = {"baselineSeconds": 30, "conditionSeconds": 90, "conditionEndsOnConfirm": False, "headSampleHz": 20}
    make_placement_session(tmp_path, 1, "a", manifest_extra={"config": cfg})
    make_placement_session(tmp_path, 2, "b", "view", manifest_extra={"config": cfg})
    same = analyze(tmp_path)["summary"]
    assert same["configMismatch"] == {} and not any(w.startswith("config_mismatch") for w in same["warnings"])

    other = tmp_path / "other"
    make_placement_session(other, 1, "a", manifest_extra={"config": cfg})
    make_placement_session(other, 2, "b", "view", manifest_extra={
        "config": {**cfg, "conditionSeconds": 60, "conditionEndsOnConfirm": True},
        "space": {"floorRadiusM": 4.0, "ringRadiiM": [1.0, 2.0, 3.0], "showRings": False,
                  "startDistanceM": 1.5, "startHeightM": 0.8}})
    # 요약에서 빠지는 세션(미완료)의 설정은 점검하지 않는다
    make_placement_session(other, 3, "c", completed=False, manifest_extra={"config": {**cfg, "baselineSeconds": 10}})
    summ = analyze(other)["summary"]
    assert set(summ["configMismatch"]) == {"conditionSeconds", "conditionEndsOnConfirm", "space"}
    assert summ["configMismatch"]["conditionSeconds"] == [60, 90]
    for key in ("conditionSeconds", "conditionEndsOnConfirm", "space"):
        assert f"config_mismatch:{key}" in summ["warnings"]
    assert "config_mismatch:baselineSeconds" not in summ["warnings"]
    assert "config_mismatch:stopDistance" not in summ["warnings"]


# ---------------------------------------------------------------- 계약 테스트: 실제 Unity 기록

REAL_RECORDS = Path(__file__).resolve().parents[2] / "docs" / "validation" / "placement" / "records"


@pytest.mark.skipif(not REAL_RECORDS.is_dir(), reason="Unity 자동 시행 기록(docs/validation/placement/records)이 없음")
def test_real_unity_records_follow_the_contract():
    """Unity 러너가 실제로 쓴 합성 자동 시행 기록 5개(place, view/static·replay·system_move·point_select)를 분석기가 읽는다."""
    res = analyze(REAL_RECORDS)
    sessions = res["sessions"]
    assert len(sessions) == 5
    assert {f"{s['condition']}/{s['control_mode']}" for s in sessions} == {
        "place/none", "view/static", "view/replay", "view/system_move", "view/point_select"}
    for s in sessions:
        flags = s["flags"].split(";") if s["flags"] else []
        assert not [f for f in flags if f.startswith("missing_file:")], (s["session_id"], flags)
        assert "version_mismatch" not in flags and "objpose_path_mismatch" not in flags, (s["session_id"], flags)
        assert s["completed"] is True and s["condition_complete"] is True and s["auto_mode"] is True
        assert s["final_distance_m"] is not None and s["stop_n_valid"] > 0
    assert res["summary"]["records"]["included"] == 5


def test_selection_skip_color_and_form_source_columns(tmp_path):
    """manifest selection의 skipped·colorChanged(G31·G34, ifs-selection/0.2에서 옴)와 sources.form.type(G32 said_unrendered_*)을 열로 읽는다.
    키가 없는 이전 기록(0.1 선택 파일)은 빈칸."""
    new = {"file": "selection.json", "sha256": "ab", "formatVersion": "ifs-selection/0.2", "none": False,
           "selectedCandidateId": None, "finalOverrides": {}, "sources": {"form.type": "said_unrendered_default"},
           "skipped": True, "colorChanged": True}
    old = {"file": "selection.json", "sha256": "cd", "formatVersion": "ifs-selection/0.1", "none": False,
           "selectedCandidateId": "c-000000000001", "finalOverrides": {"layout.size": 0.6}, "sources": {"form.type": "chosen"}}
    make_placement_session(tmp_path, 1, "new", version="ifs-placement/0.2", manifest_extra={"selection": new})
    make_placement_session(tmp_path, 2, "old", version="ifs-placement/0.2", manifest_extra={"selection": old})
    make_placement_session(tmp_path, 3, "nosel")
    res = analyze(tmp_path)
    cols = res["columns"]
    assert cols.index("selection_skipped") == cols.index("n_final_overrides") + 1
    assert {"selection_skipped", "color_changed", "form_source"} <= set(cols)
    n, o, x = row(res, "new"), row(res, "old"), row(res, "nosel")
    assert (n["selection_skipped"], n["color_changed"], n["form_source"]) == (True, True, "said_unrendered_default")
    assert (o["selection_skipped"], o["color_changed"], o["form_source"]) == (None, None, "chosen")
    assert (x["selection_skipped"], x["color_changed"], x["form_source"]) == (None, None, None)


def test_form_base_and_variant_source_columns(tmp_path):
    """CP10 G39: sources.form.base·form.baseVariant를 열 form_base_source·form_variant_source로 읽는다(키가 없는 기록 = 빈칸)."""
    new = {"file": "selection.json", "sha256": "ab", "formatVersion": "ifs-selection/0.2", "none": False,
           "selectedCandidateId": None, "finalOverrides": {"form.base": "line"}, "skipped": True, "colorChanged": False,
           "sources": {"form.type": "default", "form.base": "edited", "form.baseVariant": "edited"}}
    old = {"file": "selection.json", "sha256": "cd", "formatVersion": "ifs-selection/0.2", "none": False,
           "selectedCandidateId": None, "finalOverrides": {}, "skipped": True, "colorChanged": False,
           "sources": {"form.type": "default", "form.base": "said"}}
    make_placement_session(tmp_path, 1, "new", version="ifs-placement/0.2", manifest_extra={"selection": new})
    make_placement_session(tmp_path, 2, "old", version="ifs-placement/0.2", manifest_extra={"selection": old})
    make_placement_session(tmp_path, 3, "nosel")
    res = analyze(tmp_path)
    cols = res["columns"]
    assert cols.index("form_base_source") == cols.index("form_source") + 1
    assert cols.index("form_variant_source") == cols.index("form_base_source") + 1
    n, o, x = row(res, "new"), row(res, "old"), row(res, "nosel")
    assert (n["form_base_source"], n["form_variant_source"]) == ("edited", "edited")
    assert (o["form_base_source"], o["form_variant_source"]) == ("said", None)
    assert (x["form_base_source"], x["form_variant_source"]) == (None, None)


# ---------------------------------------------------------------- G52–G53 배치 공간 후보(B·E·F)

def _env_block(name, assist, practice=True):
    return {"name": name, "placementAssist": assist, "sky": {"kind": "gradient"}, "lighting": "neutral",
            "practice": ({"targetDistanceM": 2.0, "targetAzimuthDeg": -45, "targetHeightM": 0.8, "cubeSizeM": 0.25,
                          "targetSource": "experiment_config"} if assist and practice else None)}


def test_environment_and_practice_columns_and_old_records(tmp_path):
    """공간·놓기 도움 열(G52), 연습 파일(G53). 옛 기록(environment 키 없음) = neutral·도움 없음, 연습 빈칸."""
    make_placement_session(tmp_path, 1, "old")
    f = make_placement_session(tmp_path, 2, "e", manifest_extra={"environment": _env_block("space", True)})
    (f / "practice.json").write_text(json.dumps({"errorM": 0.0312, "endedBy": "participant_confirm", "confirmed": True,
                                                 "finalDistanceM": 2.0}), encoding="utf-8")
    make_placement_session(tmp_path, 3, "b-view", "view", manifest_extra={"environment": _env_block("neutral", True, practice=False)})
    res = analyze(tmp_path, tmp_path / "out")
    for c in ("environment", "placement_assist", "practice_error_m", "practice_ended_by"):
        assert c in placement.SESSION_HEAD
    o, e, b = row(res, "old"), row(res, "e"), row(res, "b-view")
    assert (o["environment"], o["placement_assist"], o["practice_error_m"], o["practice_ended_by"]) == ("neutral", False, None, None)
    assert (e["environment"], e["placement_assist"]) == ("space", True)
    assert e["practice_error_m"] == pytest.approx(0.0312)
    assert e["practice_ended_by"] == "participant_confirm"
    assert (b["environment"], b["placement_assist"], b["practice_error_m"]) == ("neutral", True, None)
    # 연습은 본 결과 지표에 들어가지 않는다(놓은 자리는 placement.json 값 그대로)
    assert e["final_distance_m"] == o["final_distance_m"]
    assert "missing_file:practice.json" not in o["flags"], "연습 파일은 필수가 아니다"
    # 공간이 다른 세션을 한 요약에 넣으면 경고
    assert "config_mismatch:environment" in res["summary"]["warnings"]
    header = (tmp_path / "out" / "placement_sessions.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header.index("environment") == header.index("safety_form_blocked") + 1


def test_same_environment_sessions_have_no_environment_mismatch(tmp_path):
    make_placement_session(tmp_path, 1, "a")
    make_placement_session(tmp_path, 2, "b", "view")
    assert "config_mismatch:environment" not in analyze(tmp_path)["summary"]["warnings"], "옛 기록끼리는 키가 없어 같다"
    other = tmp_path / "f"
    for i, sid in enumerate(("a", "b"), 1):
        make_placement_session(other, i, sid, manifest_extra={"environment": _env_block("nature", True)})
    assert "config_mismatch:environment" not in analyze(other)["summary"]["warnings"]


# ---------------------------------------------------------------- G60-2 반복 멈춤 · G60-3 눈높이(2026-11-26)

LOOP_ROUNDS_COLS = ["round", "practice", "start_dir", "start_distance_m", "speed_mps", "final_distance_m", "first_stop_distance_m",
                    "last_stop_distance_m", "n_stops", "n_resumes", "final_motion_dir", "passes_before_confirm", "stop_spread_m",
                    "at_bound", "end_reason", "duration_ms", "eye_object_distance_m"]


def _loop_block(plan_seed=1, main_rounds=4):
    return {"speedMps": 0.25, "approachStartM": 3.0, "recedeStartM": 0.5, "trialsPerDirection": 4, "practiceTrials": 2,
            "minM": 0.2, "maxM": 3.5, "mode": "loop",
            "loop": {"minM": 0.4, "maxM": 3.6, "rounds": main_rounds, "practiceRounds": 1, "roundSeconds": 75,
                     "plan": [{"round": 1, "practice": True, "startDir": "approach", "startDistanceM": 1.0 + plan_seed / 10}]}}


def _round(r, practice, final, first, direction, reason="confirmed", passes=0, at_bound=0, eye=1.5):
    conf = reason == "confirmed"
    return [r, practice, "approach", 2.0, 0.25, final if conf else "", first if first is not None else "",
            (final if conf else first) if first is not None else "", 1 if first is not None else 0, 0,
            direction if first is not None else "", passes if conf else "", 0.0 if first is not None else "",
            at_bound if conf else "", reason, 9000, eye if conf else ""]


def make_loop_session(root, pnum, sid, rounds, condition="place", control=None, final=(2.05, 30.0, 0.8), eye=None,
                      plan_seed=1, omit_loop_files=(), main_rounds=4):
    extra = {"stopDistance": _loop_block(plan_seed, main_rounds)}
    if eye is not None:
        extra["eyeHeight"] = {"mode": "relative", "referenceM": 1.6, "measuredM": eye, "offsetM": round(eye - 1.6, 4),
                              "sdM": 0.005, "pitchDeg": 1.0, "samples": 20, "trackingOrigin": "Floor", "source": "calibrated"}
    folder = make_placement_session(root, pnum, sid, condition, control, final=final, manifest_extra=extra,
                                    version="ifs-placement/0.2")
    _csv(folder / "stopdistance.csv", STOP_COLS, [])           # loop: 헤더만
    if "stoprounds.csv" not in omit_loop_files:
        _csv(folder / "stoprounds.csv", LOOP_ROUNDS_COLS, rounds)
    if "stopadjust.csv" not in omit_loop_files:
        _csv(folder / "stopadjust.csv", ["round", "practice", "time_ms", "t_ms", "event", "distance_m", "motion_dir", "rt_ms"],
             [[1, 1, 0, 0, "start", 2.0, "approach", 0]])
    return folder


def test_old_records_get_no_loop_or_eye_columns(tmp_path):
    four_conditions(tmp_path)
    res = analyze(tmp_path, tmp_path / "out")
    assert not set(placement.LOOP_COLUMNS + placement.EYE_COLUMNS) & set(res["columns"]), "새 열은 해당 세션이 있을 때만"
    assert not (tmp_path / "out" / "stop_loop_rounds.csv").exists()
    assert "stopLoop" not in res["summary"] and "eyeHeight" not in res["summary"]
    assert all("stop_mode" not in s and "eye_height_m" not in s for s in res["sessions"])


def test_loop_session_main_value_directions_and_anchor(tmp_path):
    rounds = [_round(1, 1, 0.3, 0.3, "approach"),                     # 연습 — 섞이면 평균이 크게 틀어짐
              _round(2, 0, 1.6, 1.7, "approach", passes=1),
              _round(3, 0, 1.8, 1.75, "recede"),
              _round(4, 0, None, 1.9, "recede", reason="timeout_stopped"),   # 미확정 — 마지막 멈춤으로 채우지 않음
              _round(5, 0, 1.7, 1.8, "approach", at_bound=1)]
    make_loop_session(tmp_path, 1, "loop-place", rounds)
    make_placement_session(tmp_path, 2, "old-single", version="ifs-placement/0.2")
    res = analyze(tmp_path, tmp_path / "out")
    cols = res["columns"]
    i = cols.index("head_yaw_range_deg") + 1
    assert cols[i:i + len(placement.LOOP_COLUMNS)] == placement.LOOP_COLUMNS
    s, old = row(res, "loop-place"), row(res, "old-single")
    assert s["stop_mode"] == "loop" and old["stop_mode"] == "single"
    assert s["stop_final_mean_m"] == pytest.approx((1.6 + 1.8 + 1.7) / 3, abs=1e-4)
    assert (s["stop_final_n"], s["stop_n_unconfirmed"], s["stop_n_at_bound"]) == (3, 1, 1)
    assert s["stop_final_approach_mean_m"] == pytest.approx(1.65)
    assert s["stop_final_recede_mean_m"] == pytest.approx(1.8)
    assert s["stop_first_minus_final_mean_m"] == pytest.approx(((1.7 - 1.6) + (1.75 - 1.8) + (1.8 - 1.7)) / 3, abs=1e-4)
    assert s["stop_passes_mean"] == pytest.approx(1 / 3, abs=1e-4)
    assert s["stop_minus_condition_final_m"] == pytest.approx(s["stop_final_mean_m"] - 2.05, abs=1e-4)
    assert s["eye_object_distance_m"] == pytest.approx(1.5)
    assert s["stop_mean_m"] is None and s["stop_n_valid"] == 0, "single 열은 빈칸"
    assert "stop_trials_short" not in s["flags"] and "stop_unconfirmed:1" in s["flags"]
    assert old["stop_final_mean_m"] is None and old["stop_minus_condition_final_m"] is None and old["stop_mean_m"] is not None
    rounds_out = list(csv.DictReader((tmp_path / "out" / "stop_loop_rounds.csv").open(encoding="utf-8")))
    assert len(rounds_out) == 5 and rounds_out[3]["final_distance_m"] == ""
    assert [r["included"] for r in rounds_out] == ["0", "1", "1", "0", "1"], "bool은 stop_trials.csv처럼 0/1"
    sl = res["summary"]["stopLoop"]
    assert sl["nSessions"] == 1 and sl["rounds"]["unconfirmed"] == 1
    assert sl["rounds"]["endReasons"] == {"confirmed": 3, "timeout_stopped": 1}


def test_loop_needs_two_confirmed_rounds_and_flags_missing_files(tmp_path):
    rounds = [_round(1, 1, 1.0, 1.0, "approach"), _round(2, 0, 1.6, 1.7, "approach"),
              _round(3, 0, None, None, "approach", reason="timeout_moving")]
    make_loop_session(tmp_path, 1, "few", rounds, omit_loop_files=("stopadjust.csv",))
    s = row(analyze(tmp_path), "few")
    assert s["stop_final_mean_m"] is None and s["stop_final_n"] == 1, "확정 라운드 2개 미만이면 빈칸"
    assert "missing_file:stopadjust.csv" in s["flags"] and "stop_rounds_short" in s["flags"]


def test_one_main_round_sessions_use_the_single_confirmed_value_and_old_four_round_records_still_read(tmp_path):
    # G83(2026-11-28): 연습 1 + 본 1. 본 1라운드를 확정하면 그 값이 주 값, 확정하지 않으면 빈칸(마지막 멈춤으로 채우지 않음)
    assert [placement.loop_min_confirmed(n) for n in (None, 0, 1, 2, 4)] == [2, 2, 1, 2, 2]
    make_loop_session(tmp_path, 1, "one", [_round(1, 1, 1.0, 1.0, "approach"), _round(2, 0, 1.6, 1.7, "recede")], main_rounds=1)
    make_loop_session(tmp_path, 2, "one-timeout", [_round(1, 1, 1.0, 1.0, "recede"),
                                                   _round(2, 0, None, 1.9, "approach", reason="timeout_stopped")], main_rounds=1)
    make_loop_session(tmp_path, 3, "old-four", [_round(1, 1, 0.3, 0.3, "approach"), _round(2, 0, 1.6, 1.7, "approach"),
                                                _round(3, 0, 1.8, 1.75, "recede"), _round(4, 0, 1.2, 1.3, "approach"),
                                                _round(5, 0, 1.6, 1.5, "recede")])
    res = analyze(tmp_path, tmp_path / "out")
    one, to, old = row(res, "one"), row(res, "one-timeout"), row(res, "old-four")
    assert one["stop_final_mean_m"] == pytest.approx(1.6) and one["stop_final_n"] == 1
    assert one["stop_final_sd_m"] is None, "한 값이라 SD 없음"
    assert (one["stop_final_recede_mean_m"], one["stop_final_approach_mean_m"]) == (pytest.approx(1.6), None), "방향별 평균은 한쪽만"
    assert one["stop_minus_condition_final_m"] == pytest.approx(1.6 - 2.05, abs=1e-4)
    assert "stop_rounds_short" not in one["flags"] and not any(f.startswith("stop_unconfirmed") for f in one["flags"])
    assert to["stop_final_mean_m"] is None and to["stop_n_unconfirmed"] == 1 and "stop_unconfirmed:1" in to["flags"]
    assert old["stop_final_mean_m"] == pytest.approx((1.6 + 1.8 + 1.2 + 1.6) / 4, abs=1e-4) and old["stop_final_n"] == 4
    assert old["stop_final_sd_m"] is not None and "stop_rounds_short" not in old["flags"]
    sl = res["summary"]["stopLoop"]
    assert sl["directionDiff"]["all"]["n"] == 1, "세션 안 방향 차는 예전 4라운드 세션에서만"
    assert "config_mismatch:stopDistance" in res["summary"]["warnings"], "본 라운드 수가 다른 세션을 섞으면 알린다"
    assert sl["rounds"]["main"] == 6


def test_loop_anchor_in_both_conditions_and_direction_gap_warning(tmp_path):
    big_gap = [_round(1, 1, 1.0, 1.0, "approach"), _round(2, 0, 1.2, 1.3, "approach"), _round(3, 0, 1.6, 1.5, "recede"),
               _round(4, 0, 1.2, 1.3, "approach"), _round(5, 0, 1.6, 1.5, "recede")]
    make_loop_session(tmp_path, 1, "lp", big_gap, plan_seed=1)
    make_loop_session(tmp_path, 2, "lv", big_gap, condition="view", control="static", plan_seed=2)
    res = analyze(tmp_path)
    v = row(res, "lv")
    assert v["final_distance_m"] == pytest.approx(1.5), "보기만(static) 조건의 끝 자리 = 시작 자리"
    assert v["stop_minus_condition_final_m"] == pytest.approx(1.4 - 1.5, abs=1e-4), "보기만 조건도 닻 지표를 낸다"
    sl = res["summary"]["stopLoop"]
    assert sl["directionDiff"]["meanAbs"] == pytest.approx(0.4, abs=1e-4)
    assert any(w.startswith("stop_loop_direction_gap") for w in res["summary"]["warnings"])
    assert "config_mismatch:stopDistance" not in res["summary"]["warnings"], "출발 계획(plan)은 사람마다 달라 비교에서 뺀다"
    assert set(sl["conditionEffect"]) == {"stop_final_mean_m", "stop_minus_condition_final_m"}


def test_eye_height_columns_and_old_records_blank(tmp_path):
    rounds = [_round(1, 1, 1.0, 1.0, "approach"), _round(2, 0, 1.6, 1.7, "approach"), _round(3, 0, 1.8, 1.75, "recede")]
    make_loop_session(tmp_path, 1, "eye", rounds, eye=1.75, final=(2.05, 30.0, 0.8))
    make_placement_session(tmp_path, 2, "old")
    res = analyze(tmp_path, tmp_path / "out")
    cols = res["columns"]
    assert cols.index("eye_height_m") == cols.index("eye_object_distance_m") + 1, "눈높이 열은 반복 멈춤 열 뒤"
    e, o = row(res, "eye"), row(res, "old")
    assert (e["eye_height_m"], e["eye_height_source"]) == (1.75, "calibrated")
    assert e["final_height_rel_eye_m"] == pytest.approx(0.8 - 1.75)
    assert e["final_height_ratio_eye"] == pytest.approx(0.8 / 1.75, abs=1e-4)
    assert e["head_y_drift_m"] == pytest.approx(1.6 - 1.75), "조건 단계 head_y 중앙값 − E"
    assert (o["eye_height_m"], o["final_height_rel_eye_m"], o["head_y_drift_m"], o["eye_height_source"]) == (None, None, None, None)
    assert res["summary"]["eyeHeight"]["sources"] == {"calibrated": 1}
    header = (tmp_path / "out" / "placement_sessions.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert "final_height_ratio_eye" in header


def test_sim_loop_plan_matches_the_unity_runner_and_default_sim_is_unchanged(tmp_path):
    """sim_placement의 xorshift64* 계획 = 러너 StopLoopSchedule(PlacementStopLoopTests에 고정한 값). 기본 생성은 새 난수를 뽑지 않는다."""
    from ifs_chatbot.eval import sim_placement as sim
    r = sim.XorShift64Star(1)
    assert [r.next_ulong() for _ in range(3)] == [5424204624148110235, 15555979849632202484, 6851360858507811590]
    assert [p["startDistanceM"] for p in sim.stop_loop_plan(1, "approach")] == [1.588, 2.687, 1.743, 1.462, 2.718]
    assert [p["startDistanceM"] for p in sim.stop_loop_plan(2, "recede")] == [2.082, 1.169, 2.798, 1.197, 1.743]
    assert [p["startDistanceM"] for p in sim.stop_loop_plan(7, "approach")] == [1.163, 1.517, 1.708, 2.107, 2.304]
    assert [p["startDir"] for p in sim.stop_loop_plan(2, "recede")][:3] == ["recede", "approach", "recede"]
    # 해석적 라운드: 2.0에서 가까워지며 1.0 멈춤 → 0.4 반사 → 1.5 멈춤·확정(러너 테스트와 같은 시나리오)
    res = sim.simulate_loop_round(2.0, -1, [1.0, 1.5], True)
    assert res["reason"] == "confirmed" and res["final"] == pytest.approx(1.5)
    assert sim._passes(res["points"], res["final"]) == 1
    assert [e[1] for e in res["events"]] == ["start", "stop", "resume", "turn", "stop", "confirm"]
    assert sim.simulate_loop_round(2.0, -1, [], False)["reason"] == "timeout_moving"
    assert sim.simulate_loop_round(2.0, -1, [1.0], False)["reason"] == "timeout_stopped"
    a, b = tmp_path / "a", tmp_path / "b"
    sim.generate(a, per_type=1)
    sim.generate(b, per_type=1, stop_mode="loop", eye_mode="relative")
    assert not list(a.rglob("stoprounds.csv")) and list(b.rglob("stoprounds.csv"))
    res_b = analyze(b / "records")
    assert all(s["stop_mode"] == "loop" and s["eye_height_source"] == "calibrated" for s in res_b["sessions"])
    assert "stopMode" not in json.loads((a / "sim_truth.json").read_text(encoding="utf-8"))
