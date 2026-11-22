"""배치 실험(RQ V4) 기록 요약(ifs_chatbot.eval.placement) 테스트.
기록은 모두 합성(AGENTS.md 6): 계약 `ifs-placement/0.1` 형식대로 임시 폴더에 손으로 만든 값만 쓴다."""
import csv
import json
import math

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
                           placement_override=None):
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
    summ = {"completed": completed, "abortedAt": None if completed else "stop_distance", "endedAtUtc": utc}
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
    assert e["ciLow"] == pytest.approx(-2.0 - 1.96, abs=1e-3)
    assert e["ciHigh"] == pytest.approx(-2.0 + 1.96, abs=1e-3)
    assert e["meanDiff"] == pytest.approx(-0.4)


def test_cohen_d_small_n_and_zero_variance():
    e = cohen_d([1.0], [1.4, 1.6])
    assert e["d"] is None and e["ciLow"] is None and e["nA"] == 1 and e["meanA"] == 1.0
    assert cohen_d([], [])["d"] is None
    z = cohen_d([1.0, 1.0], [1.0, 1.0])
    assert z["d"] is None and z["sdPooled"] == 0


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
    assert s["gaze_ratio"] == pytest.approx(0.5)                  # 5·10 ≤ 15° < 20·40
    assert s["head_yaw_range_deg"] == pytest.approx(90.0)         # −30…60, ±170 제외
    s30 = analyze(tmp_path, gaze_deg=30)["sessions"][0]
    assert s30["gaze_ratio"] == pytest.approx(0.75)


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
    assert s["gaze_ratio"] is None and s["stop_mean_m"] is None and s["stop_n_valid"] == 0
    assert s["final_distance_m"] == pytest.approx(2.05)           # objpose 마지막 행으로 대신


def test_aborted_session_flagged_and_excluded(tmp_path):
    make_placement_session(tmp_path, 1, "done")
    make_placement_session(tmp_path, 2, "aborted", completed=False)
    make_placement_session(tmp_path, 3, "nosummary", omit=("summary.json",))
    res = analyze(tmp_path)
    assert row(res, "aborted")["completed"] is False and row(res, "aborted")["aborted_at"] == "stop_distance"
    assert "missing_file:summary.json" in row(res, "nosummary")["flags"]
    rec = res["summary"]["records"]
    assert rec == {"sessions": 3, "included": 1, "excludedIncomplete": 2, "skipped": 0}
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
    assert e["ciLow"] == pytest.approx(-3.96, abs=1e-2) and e["ciHigh"] == pytest.approx(-0.04, abs=1e-2)
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
    placement.main(["--records", str(rec), "--out", str(out), "--gaze-deg", "15"])
    assert "세션 4개" in capsys.readouterr().out
    with (out / "placement_sessions.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    assert {r["condition"] + "/" + r["control_mode"] for r in rows} == {
        "place/none", "view/static", "view/replay", "view/system_move"}
    p = next(r for r in rows if r["condition"] == "place")
    assert p["completed"] == "1" and p["ring_offset_m"] == "0.05" and p["rating_know_more_pre"] == "4"
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
