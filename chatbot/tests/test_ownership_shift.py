"""소유감 기록 0.3 — 같은 말·다른 값 쌍(shiftPairs)과 보기 전 보고(prereport.json) 분석 테스트.
기록은 모두 합성(AGENTS.md 6). fixtures/ownership_v03/의 manifest 2개는 Unity가 합성 spec으로 낸 실제 출력이다."""
import csv
import json
from pathlib import Path

import pytest

from ifs_chatbot.eval import ownership, ownership_shift
from ifs_chatbot.eval.ownership import analyze

FIX = Path(__file__).parent / "fixtures" / "ownership_v03"
SHA = "a" * 64
MISMATCH = ("form", "color", "size", "motion")


def size_pair(w=0.3, lo=0.2, hi=0.4, basis="stated", valid=True, skip=None):
    return {"attribute": "size", "axis": "size", "basis": basis, "w": w, "lo": lo, "hi": hi, "step": 0.1,
            "deltaE_lo": None, "deltaE_hi": None, "valid": valid, "skipReason": skip}


def color_pair(w, lo, hi, axis="hue", basis="stated", valid=True, skip=None):
    return {"attribute": "color", "axis": axis, "basis": basis, "w": w, "lo": lo, "hi": hi,
            "step": 1 / 360 if axis == "hue" else 0.005, "deltaE_lo": 12.1, "deltaE_hi": 12.4,
            "valid": valid, "skipReason": skip}


DISABLED_COLOR = {"attribute": "color", "axis": "hue", "basis": "stated", "w": 0.5, "lo": None, "hi": None,
                  "step": None, "deltaE_lo": None, "deltaE_hi": None, "valid": False, "skipReason": "disabled"}


def report(color=("not_set", None), size=("not_set", None), sha=SHA, sid=None):
    """color = (commitment, {"h", "l"} | None), size = (commitment, 값 | None)."""
    def val(c, v):
        return None if c == "not_set" else v
    return {"schema": "ifs-prereport/0.1", "sessionId": sid, "participant": None, "specSha256": sha,
            "taskTextFile": "prereport_task.v0.json", "taskTextVersion": "0.1", "createdAtUtc": "2026-11-18T00:00:00Z",
            "attributes": {
                "color": {"commitment": color[0], "value": val(*color), "method": "hue_lightness_field", "nSelections": 1},
                "size": {"commitment": size[0], "value": val(*size), "method": "size_slider", "nSelections": 1},
                "form": {"commitment": "from_start"}, "motion": {"commitment": "not_set"}}}


def _csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def make_v03(root, pnum=1, sid="s03", pairs=(), ratings=None, order=None, prereport=None, manifest=None,
             extra_rating_rows=(), rating_item="resemblance"):
    """0.3 기록 한 벌. 유효한 쌍의 lo·hi만 order에 들어간다(n = 5 + 2 × 유효 쌍 수)."""
    folder = root / "ownership" / f"P{pnum:03d}" / sid / "20261118-010000"
    folder.mkdir(parents=True)
    if manifest is None:
        variants = [{"id": "orig", "kind": "orig", "attribute": None}]
        variants += [{"id": a, "kind": "mismatch", "attribute": a, "source": "stated", "flags": {}, "magnitude": None}
                     for a in MISMATCH]
        shift_ids = []
        for p in pairs:
            if p["valid"]:
                for side in ("lo", "hi"):
                    vid = f"{p['attribute']}_{side}"
                    shift_ids.append(vid)
                    variants.append({"id": vid, "kind": "shift", "attribute": p["attribute"], "source": p["basis"],
                                     "flags": {}, "magnitude": None})
        manifest = {"recordVersion": "ifs-ownership/0.3", "participantNumber": pnum, "cb": ownership.cb_for(pnum),
                    "orderRow": (pnum - 1) % 10, "sessionId": sid, "specFile": "syn.json", "specSha256": SHA,
                    "startedAtUtc": "20261118-010000", "headSource": "desktop", "ratingItem": rating_item,
                    "taskText": {"file": "ownership_task.v0.2.json", "version": "0.2", "draftCount": 0},
                    "config": {"headSampleHz": 20, "gazeConeDeg": 15}, "flags": {"lowVisibility": False},
                    "variants": variants, "shiftPairs": list(pairs),
                    "order": order or ["orig", *MISMATCH, *shift_ids]}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    order = manifest["order"]
    ratings = {**{v: 5 for v in order}, **(ratings or {})}
    rows = [[i, v, ratings[v], 1000, 30000, 0, manifest.get("ratingItem", "")] for i, v in enumerate(order, 1)]
    rows += list(extra_rating_rows)
    _csv(folder / "ratings.csv", ["position", "variant", "rating", "rt_ms", "view_ms", "cancelled", "item"], rows)
    (folder / "summary.json").write_text(json.dumps({"completed": True, "finalChoice": None}), encoding="utf-8")
    if prereport is not None:
        (folder / "prereport.json").write_text(json.dumps(prereport), encoding="utf-8")
    return folder


def pair(res, attribute, session):
    return next(p for p in res["pairs"] if p["attribute"] == attribute and p["session"] == session)


def shift_summary(res):
    return res["summary"]["summaries"]["all"]["shift"]


# ---------------------------------------------------------------- 거리·통계 도우미

def test_signed_hue_difference_wraps_at_0_and_1():
    assert ownership_shift.signed_hue_diff(0.98, 0.02) == pytest.approx(0.04)
    assert ownership_shift.signed_hue_diff(0.02, 0.98) == pytest.approx(-0.04)
    assert ownership_shift.axis_distance("hue", 0.6, 0.5556) == pytest.approx(0.0444)
    assert ownership_shift.axis_distance("lightness", 0.9, 0.1) == pytest.approx(0.8)  # 밝기는 감기지 않는다


def test_t_quantile_matches_table():
    assert ownership_shift.t_quantile(0.975, 1) == pytest.approx(12.7062, abs=1e-3)
    assert ownership_shift.t_quantile(0.975, 10) == pytest.approx(2.2281, abs=1e-3)
    assert ownership_shift.t_quantile(0.975, 1000) == pytest.approx(1.9623, abs=1e-3)


# ---------------------------------------------------------------- 붙인 쌍(답을 아는 경우)

def test_labelled_size_pair_known_answer(tmp_path):
    # w 0.3, lo 0.2, hi 0.4, 보고 0.5 → d(w)=0.2 ≥ 0.05, d(hi)=0.1 < 0.2 < d(lo)=0.3 → near = size_hi
    make_v03(tmp_path, pairs=[size_pair()], ratings={"orig": 6, "size_hi": 6, "size_lo": 3},
             prereport=report(size=("from_start", 0.5)))
    res = analyze(tmp_path, tmp_path / "out")
    p = pair(res, "size", "s03")
    assert (p["labelled"], p["near"], p["far"], p["exclusion"]) == (True, "size_hi", "size_lo", None)
    assert p["near_minus_far"] == 3 and p["shift_drop"] == 1.5 and p["commitment"] == "from_start"
    sh = shift_summary(res)
    assert sh["nearMinusFar"]["primary"]["participantMean"]["mean"] == 3
    assert sh["nearMinusFar"]["primary"]["participantMean"]["n"] == 1
    assert sh["nearMinusFar"]["primary"]["participantMean"]["lowN"] is True
    assert sh["nearMinusFar"]["primary"]["byAttribute"]["size"]["mean"] == 3
    assert sh["shiftDrop"]["byCommitment"]["from_start"] == {"mean": 1.5, "n": 1, "lowN": True}
    assert res["summary"]["summaryVersion"] == "ownership-summary/0.4"
    with (tmp_path / "out" / "shift_pairs.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["near"] == "size_hi" and list(rows[0]) == ownership_shift.PAIR_COLUMNS


@pytest.mark.parametrize("w, lo, hi, h, near", [
    (0.98, 0.94, 0.02, 0.06, "color_hi"),     # hi가 0을 넘어 감김, 보고도 감긴 쪽
    (0.02, 0.98, 0.06, 0.90, "color_lo"),     # lo가 숫자로는 w보다 큼
    (0.6, 0.5556, 0.6556, 0.70, "color_hi"),  # 실제 Unity 출력: −16°, +20° (비대칭 각)
    (0.6, 0.5556, 0.6556, 0.50, "color_lo"),
])
def test_hue_pairs_use_signed_shortest_difference(tmp_path, w, lo, hi, h, near):
    make_v03(tmp_path, pairs=[color_pair(w, lo, hi)], ratings={"color_lo": 2, "color_hi": 6},
             prereport=report(color=("from_start", {"h": h, "l": 0.5})))
    p = pair(analyze(tmp_path), "color", "s03")
    assert p["labelled"] and p["near"] == near
    assert p["near_minus_far"] == (4 if near == "color_hi" else -4)


def test_color_threshold_uses_actual_shift_not_search_step(tmp_path):
    # step(1/360)/2로는 통과하지만 실제 이동폭 min(0.0444, 0.0556)/2 = 0.0222보다 가까우면 too_close
    make_v03(tmp_path, pairs=[color_pair(0.6, 0.5556, 0.6556)],
             prereport=report(color=("from_start", {"h": 0.615, "l": 0.5})))
    p = pair(analyze(tmp_path), "color", "s03")
    assert p["exclusion"] == "too_close" and p["threshold"] == pytest.approx(0.0222, abs=1e-4)


# ---------------------------------------------------------------- 제외 사유

@pytest.mark.parametrize("pairs, rep, reason", [
    ([size_pair()], None, "no_report"),
    ([size_pair()], report(size=("not_set", None)), "not_set"),
    ([size_pair(basis="default")], report(size=("from_start", 0.5)), "basis_default"),
    ([size_pair(basis="mixed")], report(size=("from_start", 0.5)), "basis_mixed"),
    ([size_pair()], report(size=("from_start", 0.33)), "too_close"),
    # w 0.5, lo 0.45, hi 0.9(비대칭), 보고 0.6: near = lo인데 d(lo)=0.15 ≥ d(w)=0.1
    ([size_pair(w=0.5, lo=0.45, hi=0.9)], report(size=("from_start", 0.6)), "order_violation"),
    # 원형: w 0, lo 0.95(−0.05), hi 0.2(+0.2), 보고 0.55 → d(w)=0.45, d(hi)=0.35 < d(w)이지만 d(lo)=0.4 ≤ d(w):
    # 보고가 먼 쪽(lo)을 넘어 반대편에 있다
    ([color_pair(0.0, 0.95, 0.2)], report(color=("from_start", {"h": 0.55, "l": 0.5})), "beyond_far"),
    ([DISABLED_COLOR], report(color=("from_start", {"h": 0.1, "l": 0.5})), "pair_invalid:disabled"),
    ([size_pair(lo=None, valid=False, skip="out_of_range")], report(size=("from_start", 0.5)),
     "pair_invalid:out_of_range"),
    ([size_pair()], report(size=("from_start", 0.5), sha="b" * 64), "report_spec_mismatch"),
])
def test_each_exclusion_reason(tmp_path, pairs, rep, reason):
    make_v03(tmp_path, pairs=pairs, prereport=rep)
    res = analyze(tmp_path)
    p = res["pairs"][0]
    assert p["exclusion"] == reason and p["labelled"] is False and p["near_minus_far"] is None
    sh = shift_summary(res)
    assert sh["exclusionReasons"] == {reason: 1}
    assert sh["participantsWithoutUsablePairs"] == {"n": 1, "of": 1, "share": 1.0}


def test_invalid_report_value_with_not_set_is_report_invalid(tmp_path):
    bad = report(size=("not_set", None))
    bad["attributes"]["size"]["value"] = 0.4            # ③인데 값이 있음 → 스키마 위반
    make_v03(tmp_path, pairs=[size_pair()], prereport=bad)
    res = analyze(tmp_path)
    assert res["pairs"][0]["exclusion"] == "report_invalid"
    assert res["sessions"][0]["prereport"] == "report_invalid"
    assert any("prereport.json 형식 오류" in w["message"] for w in res["summary"]["warnings"])


def test_missing_rating_is_recorded(tmp_path):
    folder = make_v03(tmp_path, pairs=[size_pair()], prereport=report(size=("from_start", 0.5)))
    rows = (folder / "ratings.csv").read_text(encoding="utf-8").splitlines()
    (folder / "ratings.csv").write_text("\n".join(r for r in rows if ",size_hi," not in r) + "\n", encoding="utf-8")
    assert analyze(tmp_path)["pairs"][0]["exclusion"] == "missing_rating"


# ---------------------------------------------------------------- 요약

def test_primary_estimate_is_mean_of_participant_means_with_t_ci(tmp_path):
    # P001: 쌍 2개(크기 +3, 색 +1) → 참여자 평균 2. P002: 크기 −2 → −2. 평균 0, sd √8, n 2 → CI ±12.706·2
    make_v03(tmp_path, pnum=1, sid="a", pairs=[size_pair(), color_pair(0.6, 0.5556, 0.6556)],
             ratings={"size_hi": 6, "size_lo": 3, "color_hi": 5, "color_lo": 4},
             prereport=report(size=("from_start", 0.5), color=("from_start", {"h": 0.7, "l": 0.5})))
    make_v03(tmp_path, pnum=2, sid="b", pairs=[size_pair()], ratings={"size_hi": 3, "size_lo": 5},
             prereport=report(size=("from_start", 0.5)))
    # P003: when_asked만(탐색) / P004: 보고 없음
    make_v03(tmp_path, pnum=3, sid="c", pairs=[size_pair()], ratings={"size_hi": 7, "size_lo": 6},
             prereport=report(size=("when_asked", 0.5)))
    make_v03(tmp_path, pnum=4, sid="d", pairs=[size_pair()], ratings={"orig": 7, "size_hi": 3, "size_lo": 5})
    sh = shift_summary(analyze(tmp_path))
    pm = sh["nearMinusFar"]["primary"]["participantMean"]
    assert pm["mean"] == 0 and pm["n"] == 2 and pm["lowN"] is True
    assert pm["ci95"] == pytest.approx([-25.4124, 25.4124], abs=1e-3)
    assert sh["nearMinusFar"]["primary"]["nPairs"] == 3
    assert sh["nearMinusFar"]["primary"]["byAttribute"]["color"] == {
        "mean": 1.0, "sd": None, "ci95": None, "n": 1, "lowN": True, "nPairs": 1}
    assert sh["nearMinusFar"]["whenAsked"]["participantMean"]["mean"] == 1
    assert sh["participantsWithoutUsablePairs"] == {"n": 1, "of": 4, "share": 0.25}
    assert sh["participantsWithoutFromStartPairs"] == {"n": 2, "of": 4, "share": 0.5}
    assert sh["exclusionReasons"] == {"no_report": 1}
    assert sh["shiftDrop"]["byCommitment"]["no_report"]["mean"] == 3
    assert sh["shiftDrop"]["byCommitment"]["when_asked"]["mean"] == pytest.approx(-1.5)
    assert sh["nSessions"] == 4


@pytest.mark.parametrize("n_pairs", [1, 2])
def test_order_length_7_and_9(tmp_path, n_pairs):
    pairs = [size_pair(), color_pair(0.6, 0.5556, 0.6556)][:n_pairs]
    make_v03(tmp_path, pairs=pairs, ratings={"orig": 6, "form": 2, "color": 3, "size": 4, "motion": 5},
             prereport=report(size=("from_start", 0.5), color=("from_start", {"h": 0.7, "l": 0.5})))
    res = analyze(tmp_path, tmp_path / "out")
    assert len(res["stimuli"]) == 5 + 2 * n_pairs
    assert res["sessions"][0]["n_positions"] == 5 + 2 * n_pairs
    assert not [w for w in res["summary"]["warnings"] if "order" in w["message"]]
    rq1 = res["summary"]["summaries"]["all"]["rq1"]
    # 어긋난 변형 평정 하락은 mismatch 형상만(쌍 변형이 섞이지 않음)
    assert {a: rq1[a]["ratingDrop"]["mean"] for a in MISMATCH} == {"form": 4, "color": 3, "size": 2, "motion": 1}
    assert all(rq1[a]["ratingDrop"]["n"] == 1 for a in MISMATCH)
    kinds = [r["kind"] for r in res["stimuli"]]
    assert kinds.count("shift") == 2 * n_pairs and kinds.count("mismatch") == 4
    assert len(res["pairs"]) == n_pairs and all(p["labelled"] for p in res["pairs"])


def test_v02_record_still_analysed_next_to_v03(tmp_path):
    folder = make_v03(tmp_path, pnum=2, sid="old", pairs=[])
    man = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    man["recordVersion"] = "ifs-ownership/0.2"
    for k in ("shiftPairs", "ratingItem"):
        man.pop(k)
    for v in man["variants"]:
        v.pop("kind")
    (folder / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
    make_v03(tmp_path, pnum=1, sid="new", pairs=[size_pair()], prereport=report(size=("from_start", 0.5)))
    res = analyze(tmp_path, tmp_path / "out")
    by = {s["session"]: s for s in res["sessions"]}
    assert by["old"]["n_shift_pairs"] is None and by["old"]["prereport"] is None
    assert by["new"]["n_shift_pairs"] == 1 and by["new"]["prereport"] == "present"
    assert res["summary"]["recordVersions"] == ["ifs-ownership/0.2", "ifs-ownership/0.3"]
    assert res["summary"]["summaries"]["all"]["rq1"]["form"]["ratingDrop"]["n"] == 2
    assert shift_summary(res)["nSessions"] == 1
    assert all(r["kind"] in ("orig", "mismatch") for r in res["stimuli"] if r["session"] == "old")


def test_other_rating_item_rows_are_ignored(tmp_path):
    make_v03(tmp_path, pairs=[], extra_rating_rows=[[1, "orig", 1, 900, 30000, 0, "mine"]])
    res = analyze(tmp_path)
    assert next(r for r in res["stimuli"] if r["variant"] == "orig")["rating"] == 5
    assert res["sessions"][0]["rating_item"] == "resemblance"
    assert any("다른 문항 행" in w["message"] for w in res["summary"]["warnings"])


# ---------------------------------------------------------------- Unity 실제 출력(합성 spec)

def _real(tmp_path, name, rep, ratings=None):
    man = json.loads((FIX / name).read_text(encoding="utf-8"))
    return make_v03(tmp_path, pnum=man["participantNumber"], sid=man["sessionId"], manifest=man, prereport=rep,
                    ratings=ratings), man


def test_real_unity_manifest_stated(tmp_path):
    _, man = _real(tmp_path, "manifest_stated.json",
                   report(color=("from_start", {"h": 0.7, "l": 0.5}), size=("when_asked", 0.1)),
                   ratings={"color_hi": 6, "color_lo": 2, "size_lo": 5, "size_hi": 4})
    assert man["recordVersion"] == "ifs-ownership/0.3" and len(man["order"]) == 9
    res = analyze(tmp_path)
    c, s = pair(res, "color", man["sessionId"]), pair(res, "size", man["sessionId"])
    assert (c["axis"], c["near"], c["near_minus_far"], c["commitment"]) == ("hue", "color_hi", 4, "from_start")
    assert (s["near"], s["near_minus_far"], s["commitment"]) == ("size_lo", 1, "when_asked")
    assert len(res["stimuli"]) == 9
    assert {r["kind"] for r in res["stimuli"]} == {"orig", "mismatch", "shift"}
    # 합성 기록의 specSha256 "0"은 sha256 형식이 아니라 짝 확인을 못 했다고 경고만 한다
    assert any("sha256 형식이 아님" in w["message"] for w in res["summary"]["warnings"])
    assert not [w for w in res["summary"]["warnings"] if "order" in w["message"]]


def test_real_unity_manifest_default(tmp_path):
    _, man = _real(tmp_path, "manifest_default.json",
                   report(color=("from_start", {"h": 0.2, "l": 0.95}), size=("from_start", 0.9)))
    res = analyze(tmp_path)
    assert [p["exclusion"] for p in res["pairs"]] == ["basis_default", "basis_default"]
    assert pair(res, "color", man["sessionId"])["axis"] == "lightness"
    assert shift_summary(res)["exclusionReasons"] == {"basis_default": 2}
