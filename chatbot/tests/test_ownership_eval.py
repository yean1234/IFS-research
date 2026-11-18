"""소유감 실험 기록 요약(ifs_chatbot.eval.ownership) 테스트.
기록은 모두 합성(AGENTS.md 6): 설계 확정본 2.4절 형식대로 임시 폴더에 손으로 만든다."""
import csv
import json
import math

import pytest

from ifs_chatbot.eval import ownership
from ifs_chatbot.eval.ownership import analyze, circular_range_deg, spearman

ORDER = ["size", "orig", "motion", "form", "color"]
SOURCES = {"form": "default", "color": "stated", "size": "stated", "motion": "mixed"}
HEAD_COLS = ["time_ms", "phase", "position", "variant", "head_x", "head_y", "head_z", "head_qx", "head_qy",
             "head_qz", "head_qw", "obj_x", "obj_y", "obj_z", "distance_m", "angle_deg"]


def _csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def default_head(position, variant, start):
    """형상마다 정면 1m에서 원뿔 안을 보는 표본 2개."""
    return [[start, "viewing", position, variant, 0, 1.6, 1, 0, 0, 0, 1, 0, 1.6, 2, 1.0, 5],
            [start + 50, "viewing", position, variant, 0, 1.6, 1, 0, 0, 0, 1, 0, 1.6, 2, 1.0, 5]]


def make_session(root, pnum=1, sid="sess-a", utc="20261117-010000", ratings=None, final="orig",
                 completed=True, order=ORDER, head=None, rating_rows=None, difference=None, config=None, events=None,
                 version="0.2", cb=None, draft_keys=()):
    """ownership/P###/<sid>/<utc>/ 아래에 합성 기록 한 벌을 쓴다.
    events가 None이면 러너처럼 형상마다 첫 viewing 표본 시각에 viewing_start를 쓴다.
    version "0.1"이면 0.2에서 늘어난 값(taskText.draftCount, magnitude.deltaE00Composited)을 넣지 않는다."""
    folder = root / "ownership" / f"P{pnum:03d}" / sid / utc
    folder.mkdir(parents=True)
    variants = [{"id": "orig", "attribute": None, "overrides": {}, "shapeModel": None}]
    for a in ("form", "color", "size", "motion"):
        variants.append({"id": a, "attribute": a, "overrides": {}, "shapeModel": None, "changedKeys": [f"{a}.k"],
                         "from": {}, "to": {}, "rule": "r", "source": SOURCES[a], "sourceByKey": {},
                         "flags": {"saidNotRendered": a == "form", "forced": False, "belowTarget": False,
                                   "motionAltersScale": False},
                         "magnitude": {"sizeStep": 0.25} if a == "size" else (
                             ({"deltaE00": 31.2} if version == "0.1" else {"deltaE00": 31.2, "deltaE00Composited": 18.4})
                             if a == "color" else None)})
    cfg = {"sizeStep": 0.25, "colorDeltaE": 30, "viewSeconds": 30, "headSampleHz": 20, "gazeConeDeg": 15}
    cfg.update(config or {})
    task_text = {"file": "ownership_task.v0.json", "version": "0.1"}
    if version != "0.1":
        task_text.update({"draftCount": len(draft_keys), "draftKeys": list(draft_keys)})
    manifest = {"recordVersion": f"ifs-ownership/{version}", "generatorVersion": f"ownership-variants/{version}",
                "participantNumber": pnum, "cb": ownership.cb_for(pnum) if cb is None else cb,
                "orderRow": (pnum - 1) % 10, "sessionId": sid, "taskText": task_text,
                "specFile": "synthetic.json", "specSha256": "0" * 64, "startedAtUtc": utc, "headSource": "desktop",
                "unityVersion": "test", "config": cfg, "flags": {"lowVisibility": False},
                "original": {"params": {}, "shapeModel": "none", "statedKeys": [], "defaultKeys": [],
                             "unmappedCount": 0, "unmatchedCount": 0},
                "variants": variants, "order": order}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    ratings = ratings or {v: 5 for v in order}
    if rating_rows is None:
        rating_rows = [[i, v, ratings[v], 1200, 30000, 0] for i, v in enumerate(order, 1) if v in ratings]
    _csv(folder / "ratings.csv", ["position", "variant", "rating", "rt_ms", "view_ms", "cancelled"], rating_rows)
    if head is None:
        head = []
        for i, v in enumerate(order, 1):
            head += default_head(i, v, i * 40000)
    _csv(folder / "headpose.csv", HEAD_COLS, head)
    _csv(folder / "difference.csv", ["variant", "rating", "rt_ms"],
         difference if difference is not None else [[v, 4, 900] for v in order if v != "orig"])
    if events is None:
        firsts: dict = {}
        for r in head:
            if r[1] == "viewing":
                firsts[r[2]] = min(firsts.get(r[2], r[0]), r[0])
        events = [[0, "phase", "setup"]] + [[firsts[p], "viewing_start", f"position={p};variant={order[p - 1]}"]
                                            for p in sorted(firsts)]
    _csv(folder / "events.csv", ["time_ms", "event", "detail"], events)
    summ = {"completed": completed, "abortedAt": None if completed else "rating",
            "finalChoice": {"position": order.index(final) + 1, "variant": final, "rt_ms": 800} if final else None,
            "ratings": ratings, "endedAtUtc": utc}
    (folder / "summary.json").write_text(json.dumps(summ), encoding="utf-8")
    return folder


def stim(res, variant, session="sess-a"):
    return next(r for r in res["stimuli"] if r["variant"] == variant and r["session"] == session)


# ---------------------------------------------------------------- (a) 행동 지표

def test_behavior_metrics_hand_computed(tmp_path):
    # 위치 1(size): 형상 중심 (0, 1.6, 2). 머리 (-1,·,3) → (0,·,3) → (1,·,3) → (1,·,3)
    # 방위각 315°, 0°, 45°, 45° → 0°/360° 경계를 넘는 원형 범위 90°. 이동 거리 1 + 1 + 0 = 2.
    # 각도 20, 10, 5, 30 (원뿔 15°) → 원뿔 안 2개 × 50ms = 100ms, 처음 원뿔 안은 두 번째 표본 → 50ms.
    head = [
        [1000, "viewing", 1, "size", -1, 1.6, 3, 0, 0, 0, 1, 0, 1.6, 2, 1.5, 20],
        [1050, "viewing", 1, "size", 0, 1.6, 3, 0, 0, 0, 1, 0, 1.6, 2, 1.0, 10],
        [1100, "viewing", 1, "size", 1, 1.6, 3, 0, 0, 0, 1, 0, 1.6, 2, 1.5, 5],
        [1150, "viewing", 1, "size", 1, 1.6, 3, 0, 0, 0, 1, 0, 1.6, 2, 2.0, 30],
        # rating 단계 표본은 지표에서 빠진다
        [1200, "rating", 1, "", 9, 1.6, 9, 0, 0, 0, 1, 0, 1.6, 2, 9.0, 0],
    ]
    for i, v in enumerate(ORDER[1:], 2):
        head += default_head(i, v, i * 40000)
    make_session(tmp_path, head=head)
    res = analyze(tmp_path)
    r = stim(res, "size")
    assert r["n_samples"] == 4
    assert r["gaze_ms"] == pytest.approx(100)
    assert r["gaze_ratio"] == pytest.approx(100 / 30000, abs=1e-4)
    assert r["first_look_ms"] == pytest.approx(50)
    assert r["dist_mean_m"] == pytest.approx(1.5)
    assert r["dist_min_m"] == pytest.approx(1.0)
    assert r["azimuth_range_deg"] == pytest.approx(90)
    assert r["path_m"] == pytest.approx(2)
    # 원본(위치 2): 표본 2개 모두 원뿔 안 → 100ms, 처음 0ms, 같은 자리 → 이동 0, 범위 0
    o = stim(res, "orig")
    assert (o["gaze_ms"], o["first_look_ms"], o["path_m"], o["azimuth_range_deg"]) == (100, 0, 0, 0)
    # 원본 대비 차이 = 변형 − 원본
    assert r["first_look_ms_diff"] == pytest.approx(50)
    assert r["dist_mean_m_diff"] == pytest.approx(0.5)
    assert r["azimuth_range_deg_diff"] == pytest.approx(90)
    assert o["gaze_ms_diff"] == 0


def test_circular_range_and_never_looked():
    assert circular_range_deg([350, 10]) == pytest.approx(20)
    assert circular_range_deg([0, 120, 240]) == pytest.approx(240)
    assert circular_range_deg([42]) == 0
    assert circular_range_deg([]) is None
    s = [{"t": 0, "angle": 40, "dist": 1, "head": (0, 0, 0), "obj": (0, 0, 1)}]
    m = ownership.behavior_metrics(s, 30000, 20, 15)
    assert m["gaze_ms"] == 0 and m["first_look_ms"] is None


# ---------------------------------------------------------------- (b) 취소된 평정

def test_cancelled_rating_ignored(tmp_path):
    rows = [[1, "size", 2, 900, 30000, 0],
            [1, "size", 2, 950, 30000, 1],   # 직전 평정 취소
            [1, "size", 6, 1500, 30000, 0],  # 다시 평정
            [2, "orig", 7, 800, 30000, 1],   # 취소 행만 먼저 남는 방식
            [2, "orig", 5, 800, 30000, 0],
            [3, "motion", 4, 800, 30000, 0], [4, "form", 4, 800, 30000, 0],
            [5, "color", 3, 800, 30000, 0],
            [5, "color", 3, 810, 30000, 1]]  # 마지막에 취소하고 다시 평정하지 않음
    make_session(tmp_path, rating_rows=rows)
    res = analyze(tmp_path)
    assert stim(res, "size")["rating"] == 6 and stim(res, "size")["n_cancelled"] == 1
    assert stim(res, "size")["rt_ms"] == 1500
    assert stim(res, "orig")["rating"] == 5
    assert stim(res, "color")["rating"] is None and stim(res, "color")["rating_drop"] is None
    assert stim(res, "size")["rating_drop"] == -1


# ---------------------------------------------------------------- (c) 중단 세션

def test_incomplete_session_excluded(tmp_path):
    make_session(tmp_path, pnum=1, sid="done", ratings={"orig": 6, "form": 2, "color": 6, "size": 6, "motion": 6})
    make_session(tmp_path, pnum=2, sid="aborted", completed=False, final=None,
                 ratings={"orig": 6, "form": 6, "color": 6, "size": 6, "motion": 6})
    res = analyze(tmp_path, tmp_path / "out")
    by = {s["session"]: s for s in res["sessions"]}
    assert by["aborted"]["excluded"] == "incomplete" and by["done"]["excluded"] == ""
    summ = res["summary"]
    assert summ["records"] == {"sessions": 2, "included": 1, "excludedIncomplete": 1, "origBelowThreshold": 0,
                               "origRatingMissing": 0, "skipped": 0}
    rq1 = summ["summaries"]["mine"]["all"]["rq1"]
    assert rq1["form"]["ratingDrop"] == {"mean": 4, "n": 1, "lowN": True}
    with (tmp_path / "out" / "sessions.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["completed"] for r in rows] == ["1", "0"]
    assert rows[1]["excluded"] == "incomplete" and rows[1]["chosen_variant"] == ""


# ---------------------------------------------------------------- (d) 중복 폴더

def test_duplicate_folders(tmp_path):
    make_session(tmp_path, utc="20261117-090000", ratings={v: 3 for v in ORDER})
    make_session(tmp_path, utc="20261117-100000", ratings={v: 6 for v in ORDER})
    make_session(tmp_path, utc="20261117-110000", completed=False, final=None)
    make_session(tmp_path, sid="sess-b", utc="20261117-120000")  # 같은 참여자, 다른 세션 → 따로 쓴다
    res = analyze(tmp_path)
    assert len(res["sessions"]) == 2
    used = {s["session"]: s["record_folder"] for s in res["sessions"]}
    assert used["sess-a"] == "ownership/P001/sess-a/20261117-100000"
    assert stim(res, "orig")["rating"] == 6
    sk = res["summary"]["skipped"]
    assert [(s["record"].rsplit("/", 1)[1], s["reason"], s["completed"]) for s in sk] == [
        ("20261117-090000", "duplicate", True), ("20261117-110000", "duplicate", False)]
    assert all(s["usedInstead"] == used["sess-a"] for s in sk)
    # 완료된 것이 하나도 없으면 가장 최근 미완료를 쓰고 요약에서는 뺀다
    other = tmp_path / "only_incomplete"
    make_session(other, utc="20261117-090000", completed=False, final=None)
    make_session(other, utc="20261117-100000", completed=False, final=None)
    res2 = analyze(other)
    assert res2["sessions"][0]["record_folder"].endswith("20261117-100000")
    assert res2["summary"]["records"]["included"] == 0


def test_records_can_point_at_session_folder(tmp_path):
    folder = make_session(tmp_path)
    res = analyze(folder.parent)  # 세션 폴더
    assert len(res["sessions"]) == 1 and res["sessions"][0]["record_folder"] == folder.name
    res = analyze(folder)  # UTC 폴더 자체
    assert res["sessions"][0]["record_folder"] == "."


# ---------------------------------------------------------------- (e) 집계

def test_rating_drop_choice_rate_and_threshold(tmp_path):
    make_session(tmp_path, pnum=1, sid="s1", final="orig",
                 ratings={"orig": 6, "form": 3, "color": 5, "size": 6, "motion": 4})
    make_session(tmp_path, pnum=2, sid="s2", final="size",
                 ratings={"orig": 5, "form": 4, "color": 5, "size": 3, "motion": 5})
    make_session(tmp_path, pnum=3, sid="s3", final="color",  # 원본 평정 3 < 4
                 ratings={"orig": 3, "form": 1, "color": 6, "size": 3, "motion": 3})
    res = analyze(tmp_path, tmp_path / "out")
    by = {s["session"]: s for s in res["sessions"]}
    assert by["s3"]["orig_below_threshold"] is True and by["s1"]["orig_below_threshold"] is False
    assert by["s1"]["orig_chosen"] is True and by["s2"]["chosen_variant"] == "size"
    assert stim(res, "orig", "s1")["rating_drop"] == 0
    assert stim(res, "form", "s1")["rating_drop"] == 3

    alls = res["summary"]["summaries"]["mine"]["all"]
    passing = res["summary"]["summaries"]["mine"]["origAtOrAboveThreshold"]
    assert alls["nSessions"] == 3 and passing["nSessions"] == 2
    # 전체: form 하락 (3 + 1 + 2) / 3 = 2, 기준 통과: (3 + 1) / 2 = 2
    assert alls["rq1"]["form"]["ratingDrop"]["mean"] == 2
    assert alls["rq1"]["color"]["ratingDrop"]["mean"] == pytest.approx((1 + 0 - 3) / 3, abs=1e-4)
    assert passing["rq1"]["color"]["ratingDrop"] == {"mean": 0.5, "n": 2, "lowN": True}
    assert alls["rq1"]["orig"]["choiceRate"]["mean"] == pytest.approx(1 / 3, abs=1e-4)
    assert passing["rq1"]["orig"]["choiceRate"]["mean"] == 0.5
    assert passing["rq1"]["size"]["choiceRate"]["mean"] == 0.5
    assert passing["rq1"]["form"]["choiceRate"]["mean"] == 0
    # RQ2: color·size는 stated, form은 default, motion은 mixed(따로)
    rq2 = passing["rq2"]
    assert rq2["bySource"]["default"]["ratingDrop"]["mean"] == 2
    assert rq2["bySource"]["stated"]["ratingDrop"]["mean"] == pytest.approx((1 + 0 + 0 + 2) / 4)
    assert rq2["bySource"]["mixed"]["ratingDrop"] == {"mean": 1, "n": 2, "lowN": True}
    assert rq2["byAttributeSource"]["form"]["stated"] == {"ratingDrop": {"mean": None, "n": 0, "lowN": True}}
    assert "unlabeled" not in rq2["bySource"]
    # 출력 파일
    out = tmp_path / "out"
    with (out / "stimuli.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 15 and list(rows[0]) == ownership.STIMULI_COLUMNS
    s1_form = next(r for r in rows if r["session"] == "s1" and r["variant"] == "form")
    assert (s1_form["source"], s1_form["said_not_rendered"], s1_form["rating_drop"], s1_form["chosen"]) == \
        ("default", "1", "3", "0")
    s1_orig = next(r for r in rows if r["session"] == "s1" and r["variant"] == "orig")
    assert (s1_orig["source"], s1_orig["chosen"], s1_orig["difference_rating"]) == ("", "1", "")
    data = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert data["descriptiveOnly"] is True and data["origThreshold"] == 4
    assert data["records"]["origBelowThreshold"] == 1


def test_rq3_correlation_and_spearman(tmp_path):
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)
    assert spearman([1, 2, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9487, abs=1e-4)
    assert spearman([1, 2], [1, 2]) is None and spearman([1, 1, 1], [1, 2, 3]) is None
    # 평정이 높을수록 오래 본 세션: gaze_ms는 형상마다 원뿔 안 표본 수 × 50ms
    ratings = {"orig": 7, "form": 3, "color": 4, "size": 5, "motion": 6}
    head = []
    for i, v in enumerate(ORDER, 1):
        k = ratings[v]
        head += [[i * 40000 + j * 50, "viewing", i, v, 0, 1.6, 1, 0, 0, 0, 1, 0, 1.6, 2, 1.0, 5 if j < k else 40]
                 for j in range(8)]
    make_session(tmp_path, ratings=ratings, head=head)
    res = analyze(tmp_path)
    corr = res["summary"]["summaries"]["mine"]["all"]["rq3"]["ratingCorrelation"]
    assert corr["gaze_ms"] == {"meanRho": 1.0, "nSessions": 1, "lowN": True}
    assert corr["path_m"]["nSessions"] == 0  # 모두 0 → 분산 없음
    diff = res["summary"]["summaries"]["mine"]["all"]["rq3"]["diffVsOrig"]["gaze_ms"]
    assert diff["byAttribute"]["form"]["mean"] == pytest.approx((3 - 7) * 50)
    assert diff["all"]["n"] == 4


# ---------------------------------------------------------------- (f) 빈 입력

def test_empty_input_gives_empty_summary(tmp_path):
    (tmp_path / "records").mkdir()
    # 소유감 기록이 아닌 manifest.json은 무시
    (tmp_path / "records" / "manifest.json").write_text('{"dependencies": {}}', encoding="utf-8")
    ownership.main(["--records", str(tmp_path / "records"), "--out", str(tmp_path / "out")])
    data = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert data["records"]["sessions"] == 0 and data["skipped"] == []
    assert data["summaries"] == {} and data["ratingItems"] == []     # 문항이 없으면 문항별 요약도 없다
    assert data["shift"]["all"]["nSessions"] == 0
    lines = (tmp_path / "out" / "stimuli.csv").read_text(encoding="utf-8").splitlines()
    assert lines == [",".join(ownership.STIMULI_COLUMNS)]
    assert (tmp_path / "out" / "sessions.csv").read_text(encoding="utf-8").splitlines() == \
        [",".join(ownership.SESSION_COLUMNS)]


def test_no_absolute_paths_in_outputs(tmp_path):
    make_session(tmp_path / "rec")
    (tmp_path / "rec" / "ownership" / "P009" / "x" / "20261117-000000").mkdir(parents=True)
    bad = tmp_path / "rec" / "ownership" / "P009" / "x" / "20261117-000000" / "manifest.json"
    bad.write_text("{not json", encoding="utf-8")
    analyze(tmp_path / "rec", tmp_path / "out")
    for name in ("stimuli.csv", "sessions.csv", "summary.json"):
        text = (tmp_path / "out" / name).read_text(encoding="utf-8")
        assert str(tmp_path) not in text and tmp_path.as_posix() not in text
    data = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert data["skipped"] == [{"record": "ownership/P009/x/20261117-000000", "reason": "manifest_unreadable"}]
    assert not math.isnan(data["summaries"]["mine"]["all"]["rq1"]["orig"]["rating"]["mean"])


# ---------------------------------------------------------------- (g) 표본 간격·제시 시작(CP4)

def _row(t, pos, var, angle, x=0.0):
    return [t, "viewing", pos, var, x, 1.6, 1, 0, 0, 0, 1, 0, 1.6, 2, 1.0, angle]


def _with_size_head(size_rows):
    """위치 1(size)만 손으로 주고 나머지 위치는 기본 표본."""
    head = list(size_rows)
    for i, v in enumerate(ORDER[1:], 2):
        head += default_head(i, v, i * 40000)
    return head


def _ev(*rows):
    """setup + 주어진 행 + 위치 2–5의 viewing_start(기본 표본 시각)."""
    return [[0, "phase", "setup"], *rows] + [[i * 40000, "viewing_start", f"position={i};variant={v}"]
                                             for i, v in enumerate(ORDER[1:], 2)]


def test_irregular_intervals_integrate_real_time(tmp_path):
    # 제시 시작 1000. 표본 1000(안) 1050(안) 1130(밖) 1160(안), 마지막은 명목 50ms.
    # 구간: 50 · 80 · 30 · 50 → 원뿔 안 50 + 80 + 50 = 180ms (예전 방식이면 3 × 50 = 150)
    head = _with_size_head([_row(1000, 1, "size", 5), _row(1050, 1, "size", 5),
                            _row(1130, 1, "size", 40), _row(1160, 1, "size", 5)])
    make_session(tmp_path, head=head)
    res = analyze(tmp_path)
    r = stim(res, "size")
    assert r["gaze_ms"] == pytest.approx(180)
    assert (r["gap_ms"], r["n_gaps"], r["first_look_ms"], r["start_source"]) == (0, 0, 0, "viewing_start")
    assert r["gaze_ratio"] == pytest.approx(180 / 30000, abs=1e-4)
    assert res["summary"]["warnings"] == []


def test_long_gap_is_capped_and_counted_as_missing(tmp_path):
    # 1050 → 1600(550ms > 명목 50 × 3): 명목 50만 세고 500ms는 결측. 같은 자세를 과거 시각으로 채우지 않은 기록.
    head = _with_size_head([_row(1000, 1, "size", 5), _row(1050, 1, "size", 5),
                            _row(1600, 1, "size", 5), _row(1650, 1, "size", 40)])
    make_session(tmp_path, head=head)
    res = analyze(tmp_path, tmp_path / "out")
    r = stim(res, "size")
    assert r["gaze_ms"] == pytest.approx(150)
    assert r["gap_ms"] == pytest.approx(500) and r["n_gaps"] == 1
    assert r["gaze_ratio"] == pytest.approx(150 / 30000, abs=1e-4), "분모는 view_ms 그대로"
    # 딱 3배(150ms)는 결측이 아님
    m = ownership.behavior_metrics([{"t": 0, "angle": 5, "dist": 1, "head": None, "obj": None},
                                    {"t": 150, "angle": 5, "dist": 1, "head": None, "obj": None}], 30000, 20, 15)
    assert (m["gaze_ms"], m["gap_ms"], m["n_gaps"]) == (200, 0, 0)
    with (tmp_path / "out" / "stimuli.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    size = next(x for x in rows if x["variant"] == "size")
    assert (size["gap_ms"], size["n_gaps"]) == ("500", "1")
    assert next(x for x in rows if x["variant"] == "orig")["gap_ms"] == "0"


def test_first_look_counts_from_viewing_start_before_first_sample(tmp_path):
    # 제시 시작 1000, 첫 표본은 40ms 늦은 1040(밖), 1090에 처음 원뿔 안 → first_look 90(첫 표본 기준이면 50)
    # 표본 0의 구간은 제시 시작부터: 1000 → 1090 = 90(밖), 표본 1은 명목 50(안)
    head = _with_size_head([_row(1040, 1, "size", 30), _row(1090, 1, "size", 5)])
    make_session(tmp_path, head=head, events=_ev([1000, "viewing_start", "position=1;variant=size"]))
    res = analyze(tmp_path)
    r = stim(res, "size")
    assert r["first_look_ms"] == pytest.approx(90)
    assert r["gaze_ms"] == pytest.approx(50) and r["gap_ms"] == 0
    assert r["start_source"] == "viewing_start"
    assert res["summary"]["warnings"] == []
    # viewing_start를 넣기 전 기록: 같은 순간의 phase 행을 쓴다(경고 없음)
    other = tmp_path / "old"
    make_session(other, head=head, events=_ev([1000, "phase", "viewing;position=1;variant=size"]))
    res2 = analyze(other)
    assert stim(res2, "size")["first_look_ms"] == pytest.approx(90)
    assert stim(res2, "size")["start_source"] == "phase"
    assert res2["summary"]["warnings"] == []


def test_missing_or_late_viewing_start_falls_back_with_warning(tmp_path):
    head = _with_size_head([_row(1040, 1, "size", 30), _row(1090, 1, "size", 5)])
    make_session(tmp_path, head=head, events=_ev())  # 위치 1의 시작 행이 없음
    res = analyze(tmp_path)
    r = stim(res, "size")
    assert r["first_look_ms"] == pytest.approx(50) and r["start_source"] == "first_sample"
    msgs = [w["message"] for w in res["summary"]["warnings"]]
    assert len(msgs) == 1 and "viewing_start 없음(position 1)" in msgs[0]
    # 시작 행이 첫 표본보다 늦으면 첫 표본을 쓰고 경고
    late = tmp_path / "late"
    make_session(late, head=head, events=_ev([1060, "viewing_start", "position=1;variant=size"]))
    res2 = analyze(late)
    assert stim(res2, "size")["first_look_ms"] == pytest.approx(50)
    assert stim(res2, "size")["start_source"] == "first_sample"
    assert any("늦음(position 1)" in w["message"] for w in res2["summary"]["warnings"])


# ---------------------------------------------------------------- (h) 순서 균형

def _bal(res):
    """0.1·0.2 기록은 조건 집합이 하나(5조건, 10행)."""
    bal = res["summary"]["orderBalance"]
    assert len(bal["byConditionSet"]) == 1
    one = next(iter(bal["byConditionSet"].values()))
    assert one["nOrderRows"] == 10 and one["balanced"] == bal["balanced"]
    return one


def _order_warnings(res):
    return [w for w in res["summary"]["warnings"] if w["message"].startswith("순서 불균형")]


def test_order_balance_counts_and_warns(tmp_path):
    for n in (1, 2, 3, 4):  # 번호를 차례로: 행 0–3 한 번씩, cb 2:2
        make_session(tmp_path / "seq", pnum=n, sid=f"s{n}")
    res = analyze(tmp_path / "seq")
    bal = _bal(res)
    assert bal["sessions"] == 4 and bal["byCb"] == {"0": 2, "1": 2}
    assert bal["byOrderRow"] == {"0": 1, "1": 1, "2": 1, "3": 1, **{str(r): 0 for r in range(4, 10)}}
    assert (bal["rowSpread"], bal["cbSpread"], bal["balanced"]) == (1, 0, True)
    assert _order_warnings(res) == []

    for n in (1, 3, 5):  # 홀수 번호만 → cb 3:0
        make_session(tmp_path / "odd", pnum=n, sid=f"s{n}")
    res = analyze(tmp_path / "odd")
    assert _bal(res)["byCb"] == {"0": 3, "1": 0}
    assert len(_order_warnings(res)) == 1 and "cb 차이 3" in _order_warnings(res)[0]["message"]

    for n in (1, 11, 2):  # 1과 11은 같은 행 0 → 행 0 두 번, 행 3–9 0번
        make_session(tmp_path / "reuse", pnum=n, sid=f"s{n}")
    res = analyze(tmp_path / "reuse")
    assert _bal(res)["rowSpread"] == 2
    assert len(_order_warnings(res)) == 1

    # 미완료 세션은 세지 않는다
    make_session(tmp_path / "inc", pnum=1, sid="a")
    make_session(tmp_path / "inc", pnum=3, sid="b", completed=False, final=None)
    make_session(tmp_path / "inc", pnum=5, sid="c", completed=False, final=None)
    res = analyze(tmp_path / "inc")
    assert res["summary"]["orderBalance"]["sessions"] == 1 and _order_warnings(res) == []


def test_cb_rule_matches_unity_and_crosses_with_order_row():
    assert [ownership.cb_for(n) for n in range(1, 11)] == [(n - 1) % 2 for n in range(1, 11)]  # 1–10번은 예전과 같다
    assert [ownership.cb_for(n) for n in (11, 12, 20, 21)] == [1, 0, 0, 0]
    assert len({((n - 1) % 10, ownership.cb_for(n)) for n in range(1, 21)}) == 20


def test_order_balance_checks_row_by_cb_cells(tmp_path):
    for n in range(1, 21):  # 새 규칙으로 1–20번: 20칸이 한 번씩
        make_session(tmp_path / "new", pnum=n, sid=f"s{n}")
    bal = _bal(analyze(tmp_path / "new"))
    assert bal["cellSpread"] == 0 and bal["balanced"] and set(bal["byOrderRowCb"].values()) == {1}

    for n in range(1, 21):  # 예전 규칙(cb = (번호 − 1) mod 2): 행과 cb가 묶여 10칸 2개·10칸 0개
        make_session(tmp_path / "old", pnum=n, sid=f"s{n}", cb=(n - 1) % 2)
    res = analyze(tmp_path / "old")
    bal = _bal(res)
    assert (bal["rowSpread"], bal["cbSpread"], bal["cellSpread"], bal["balanced"]) == (0, 0, 2, False)
    assert len(_order_warnings(res)) == 1 and "20칸 최대−최소 2" in _order_warnings(res)[0]["message"]


# ---------------------------------------------------------------- (i) 기록 버전 0.1·0.2, 초안 문구

def test_reads_both_record_versions_and_flags_draft_phrases(tmp_path):
    make_session(tmp_path, pnum=1, sid="v01", version="0.1")
    make_session(tmp_path, pnum=2, sid="v02", draft_keys=("done", "rating"))
    make_session(tmp_path, pnum=3, sid="v02-spec")
    res = analyze(tmp_path, tmp_path / "out")
    by = {s["session"]: s for s in res["sessions"]}
    assert by["v01"]["record_version"] == "ifs-ownership/0.1" and by["v01"]["draft_phrases"] is None
    assert by["v02"]["draft_phrases"] == 2 and by["v02-spec"]["draft_phrases"] == 0
    assert stim(res, "color", "v01")["magnitude_delta_e00_composited"] is None
    assert stim(res, "color", "v02")["magnitude_delta_e00_composited"] == 18.4
    assert stim(res, "color", "v02")["magnitude_delta_e00"] == 31.2
    assert res["summary"]["recordVersions"] == ["ifs-ownership/0.1", "ifs-ownership/0.2"]
    assert res["summary"]["draftPhraseSessions"] == 1
    drafts = [w for w in res["summary"]["warnings"] if w["message"].startswith("초안 문구")]
    assert len(drafts) == 1 and "P002/v02 2개" in drafts[0]["message"]
    with (tmp_path / "out" / "sessions.csv").open(encoding="utf-8") as f:
        rows = {r["session"]: r for r in csv.DictReader(f)}
    assert (rows["v01"]["draft_phrases"], rows["v02"]["draft_phrases"]) == ("", "2")
    with (tmp_path / "out" / "stimuli.csv").open(encoding="utf-8") as f:
        col = {(r["session"], r["variant"]): r["magnitude_delta_e00_composited"] for r in csv.DictReader(f)}
    assert (col[("v01", "color")], col[("v02", "color")]) == ("", "18.4")
