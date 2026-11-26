"""소유감 기록 0.3 — 같은 말·다른 값 쌍(shiftPairs)과 보기 전 보고(prereport.json) 분석 테스트.
기록은 모두 합성(AGENTS.md 6). fixtures/ownership_v03/의 manifest 2개는 Unity가 합성 spec으로 낸 실제 출력이다
(바이트 그대로 둔다. specSha256이 자리표시 "0"이라 연결 검사에서 빠지는 것까지 확인한다)."""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from ifs_chatbot import prereport as prereport_mod
from ifs_chatbot.eval import ownership, ownership_shift
from ifs_chatbot.eval.ownership import analyze

FIX = Path(__file__).parent / "fixtures" / "ownership_v03"
SHA = "a" * 64
MISMATCH = ("form", "color", "size", "motion")
VIEW_UTC = "2026-11-18T02:00:00.000Z"          # 형상 첫 제시(events.csv first_viewing_utc)
BEFORE = "2026-11-18T01:30:00.000Z"
AFTER = "2026-11-18T02:00:05.000Z"


def size_pair(w=0.3, lo=0.2, hi=0.4, basis="stated", valid=True, skip=None, m=None):
    p = {"attribute": "size", "axis": "size", "basis": basis, "w": w, "lo": lo, "hi": hi, "step": 0.1,
         "deltaE_lo": None, "deltaE_hi": None, "valid": valid, "skipReason": skip}
    if m:
        p.update(wM=m[0], loM=m[1], hiM=m[2])
    return p


def color_pair(w, lo, hi, axis="hue", basis="stated", valid=True, skip=None):
    return {"attribute": "color", "axis": axis, "basis": basis, "w": w, "lo": lo, "hi": hi,
            "step": 1 / 360 if axis == "hue" else 0.005, "deltaE_lo": 12.1, "deltaE_hi": 12.4,
            "valid": valid, "skipReason": skip}


DISABLED_COLOR = {"attribute": "color", "axis": "hue", "basis": "stated", "w": 0.5, "lo": None, "hi": None,
                  "step": None, "deltaE_lo": None, "deltaE_hi": None, "valid": False, "skipReason": "disabled"}


def width(s):
    return round(0.35 * 2 ** ((s - 0.5) * 4), 4)


def report(color=("not_set", None), size=("not_set", None), sha=SHA, sid="s03", created=BEFORE,
           color_first=None, size_first=None, changed=False):
    """ifs-prereport/0.2. color = (commitment, 값), size = (commitment, s 값). *_first = 첫 선택(없으면 최종과 같음)."""
    def keep(c, v):
        return None if c == "not_set" else v
    cf = color_first if color_first is not None else color[1]
    sf = size_first if size_first is not None else size[1]
    rep = {"schema": "ifs-prereport/0.2", "sessionId": sid, "participant": None, "specSha256": sha,
           "specFile": f"{sid}.json", "taskTextFile": "prereport_task.v0.2.json", "taskTextVersion": "0.2",
           "createdAtUtc": created,
           "attributes": {
               "color": {"commitment": color[0], "value": keep(color[0], color[1]), "firstValue": keep(color[0], cf),
                         "method": "hue_lightness_field", "nSelections": 2, "commitmentChangedAfterPick": changed},
               "size": {"commitment": size[0], "value": keep(size[0], size[1]), "firstValue": keep(size[0], sf),
                        "widthM": keep(size[0], size[1] is not None and width(size[1])),
                        "firstWidthM": keep(size[0], sf is not None and width(sf)),
                        "method": "size_slider", "nSelections": 2, "commitmentChangedAfterPick": False},
               "form": {"commitment": "from_start"}, "motion": {"commitment": "not_set"}}}
    assert prereport_mod.validate(rep) == [], prereport_mod.validate(rep)
    return rep


def _csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def make_v03(root, pnum=1, sid="s03", pairs=(), ratings=None, order=None, prereport=None, manifest=None,
             extra_rating_rows=(), rating_item="resemblance", utc="20261118-010000", first_view=VIEW_UTC,
             final=None, item_of=None, man_prereport="auto", raw_prereport=None):
    """0.3 기록 한 벌. 유효한 쌍의 lo·hi만 order에 들어간다(n = 5 + 2 × 유효 쌍 수)."""
    folder = root / "ownership" / f"P{pnum:03d}" / sid / utc
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
                    "orderRow": (pnum - 1) % 10, "sessionId": sid, "specFile": f"{sid}.json", "specSha256": SHA,
                    "startedAtUtc": "2026-11-18T01:55:00.000Z", "headSource": "desktop", "ratingItem": rating_item,
                    "taskText": {"file": "ownership_task.v0.2.json", "version": "0.2", "draftCount": 0},
                    "config": {"headSampleHz": 20, "gazeConeDeg": 15}, "flags": {"lowVisibility": False},
                    "variants": variants, "shiftPairs": list(pairs),
                    "order": order or ["orig", *MISMATCH, *shift_ids]}
    order = manifest["order"]
    raw = raw_prereport if raw_prereport is not None else (
        None if prereport is None else json.dumps(prereport).encode("utf-8"))
    if raw is not None:
        (folder / "prereport.json").write_bytes(raw)
    if man_prereport == "auto":
        manifest = {**manifest, "prereport": None if raw is None else {
            "file": "prereport.json", "sha256": hashlib.sha256(raw).hexdigest()}}
    elif man_prereport != "absent":
        manifest = {**manifest, "prereport": man_prereport}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ratings = {**{v: 5 for v in order}, **(ratings or {})}
    item_of = item_of or {}
    rows = [[i, v, ratings[v], 1000, 30000, 0, item_of.get(v, manifest.get("ratingItem", ""))]
            for i, v in enumerate(order, 1) if ratings[v] is not None]
    rows += list(extra_rating_rows)
    _csv(folder / "ratings.csv", ["position", "variant", "rating", "rt_ms", "view_ms", "cancelled", "item"], rows)
    events = [[0, "phase", "setup"], [1000, "viewing_start", f"position=1;variant={order[0]}"]]
    if first_view:
        events.append([1000, "first_viewing_utc", first_view])
    _csv(folder / "events.csv", ["time_ms", "event", "detail"], events)
    summ = {"completed": True, "finalChoice": {"position": order.index(final) + 1, "variant": final} if final else None}
    (folder / "summary.json").write_text(json.dumps(summ), encoding="utf-8")
    return folder


def pair(res, attribute, session="s03"):
    return next(p for p in res["pairs"] if p["attribute"] == attribute and p["session"] == session)


def q1(res):
    return res["summary"]["shift"]["all"]


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


def test_first_presentation_from_events():
    rows = [{"event": "viewing_start", "detail": "position=1;variant=orig", "time_ms": "5"},
            {"event": "first_viewing_utc", "detail": "2026-11-18T02:00:00.250Z", "time_ms": "5"}]
    t = ownership_shift.first_presentation_utc(rows)
    assert t.isoformat() == "2026-11-18T02:00:00.250000+00:00"
    assert ownership_shift.first_presentation_utc(rows[:1]) is None


# ---------------------------------------------------------------- 붙인 쌍(답을 아는 경우)

def test_labelled_size_pair_known_answer(tmp_path):
    # 0–1 눈금(Unity 폭 없음): w 0.3, lo 0.2, hi 0.4, 보고 0.5 → near = size_hi, size_scale_fallback 표시
    make_v03(tmp_path, pairs=[size_pair()], ratings={"orig": 6, "size_hi": 6, "size_lo": 3},
             prereport=report(size=("from_start", 0.5)))
    res = analyze(tmp_path, tmp_path / "out")
    p = pair(res, "size")
    assert (p["labelled"], p["near"], p["far"], p["exclusion"]) == (True, "size_hi", "size_lo", None)
    assert p["near_minus_far"] == 3 and p["shift_drop"] == 1.5 and p["size_scale_fallback"] is True
    sh = q1(res)
    assert sh["nearMinusFar"]["primary"]["participantMean"]["mean"] == 3
    assert sh["nearMinusFar"]["primary"]["participantMean"]["lowN"] is True
    assert sh["sizeScaleFallbackPairs"] == 1 and sh["exclusionReasons"] == {}
    assert sh["shiftDrop"]["byCommitment"]["from_start"] == {"mean": 1.5, "n": 1, "lowN": True}
    assert res["summary"]["summaryVersion"] == "ownership-summary/0.5"
    with (tmp_path / "out" / "shift_pairs.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1 and rows[0]["near"] == "size_hi" and list(rows[0]) == ownership_shift.PAIR_COLUMNS


def test_meters_decide_direction_where_two_scales_disagree(tmp_path):
    # Codex 반례: 원본 8.7 cm(w = 0.30, 쌍 0.20/0.40), 보고 12 cm. 웹 눈금 s = 0.5 + log2(0.12/0.35)/4 ≈ 0.114
    s = round(0.5 + __import__("math").log2(0.12 / 0.35) / 4, 4)
    m = (0.087, round(0.087 * 2 ** -0.4, 4), round(0.087 * 2 ** 0.4, 4))
    rep = report(size=("from_start", s))
    rep["attributes"]["size"]["widthM"] = rep["attributes"]["size"]["firstWidthM"] = 0.12
    make_v03(tmp_path / "m", pairs=[size_pair(m=m)], ratings={"size_lo": 2, "size_hi": 7}, prereport=rep)
    p = pair(analyze(tmp_path / "m"), "size")
    assert (p["near"], p["near_minus_far"], p["size_scale_fallback"]) == ("size_hi", 5, False)
    # 같은 보고를 0–1 눈금으로만 비교하면 방향이 뒤집힌다(그래서 폭이 있으면 미터를 쓴다)
    make_v03(tmp_path / "s", pairs=[size_pair()], ratings={"size_lo": 2, "size_hi": 7}, prereport=rep)
    p = pair(analyze(tmp_path / "s"), "size")
    assert (p["near"], p["near_minus_far"], p["size_scale_fallback"]) == ("size_lo", -5, True)


@pytest.mark.parametrize("w, lo, hi, h, near", [
    (0.98, 0.94, 0.02, 0.06, "color_hi"),     # hi가 0을 넘어 감김
    (0.02, 0.98, 0.06, 0.90, "color_lo"),     # lo가 숫자로는 w보다 큼
    (0.6, 0.5611, 0.6444, 0.70, "color_hi"),  # 실제 Unity 출력(비대칭 각)
    (0.6, 0.5611, 0.6444, 0.50, "color_lo"),
])
def test_hue_pairs_use_signed_shortest_difference(tmp_path, w, lo, hi, h, near):
    make_v03(tmp_path, pairs=[color_pair(w, lo, hi)], ratings={"color_lo": 2, "color_hi": 6},
             prereport=report(color=("from_start", {"h": h, "l": 0.5})))
    p = pair(analyze(tmp_path), "color")
    assert p["labelled"] and p["near"] == near
    assert p["near_minus_far"] == (4 if near == "color_hi" else -4)


def test_color_threshold_uses_actual_shift_not_search_step(tmp_path):
    # step(1/360)/2로는 통과하지만 실제 이동폭 min(0.0444, 0.0556)/2 = 0.0222보다 가까우면 too_close
    make_v03(tmp_path, pairs=[color_pair(0.6, 0.5556, 0.6556)],
             prereport=report(color=("from_start", {"h": 0.615, "l": 0.5})))
    p = pair(analyze(tmp_path), "color")
    assert p["exclusion"] == "too_close" and p["threshold"] == pytest.approx(0.0222)


@pytest.mark.parametrize("pairs, rep, reason", [
    # Codex 반례: 등호는 모두 order_violation, 정확한 반대편은 beyond_far
    ([size_pair(w=0.5, lo=0.4, hi=0.6)], report(size=("from_start", 0.55)), "order_violation"),
    ([color_pair(0.6, 0.5556, 0.6556)], report(color=("from_start", {"h": 0.6278, "l": 0.5})), "order_violation"),
    ([color_pair(0.6, 0.5556, 0.6556)], report(color=("from_start", {"h": 0.1278, "l": 0.5})), "order_violation"),
    ([color_pair(0.6, 0.5556, 0.6556)], report(color=("from_start", {"h": 0.1, "l": 0.5})), "beyond_far"),
])
def test_distance_ties_are_order_violation(tmp_path, pairs, rep, reason):
    make_v03(tmp_path, pairs=pairs, prereport=rep)
    p = analyze(tmp_path)["pairs"][0]
    assert p["exclusion"] == reason and p["labelled"] is False


# ---------------------------------------------------------------- 제외 사유

@pytest.mark.parametrize("pairs, rep, reason", [
    ([size_pair()], None, "no_report"),
    ([size_pair()], report(size=("not_set", None)), "not_set"),
    ([size_pair(basis="default")], report(size=("from_start", 0.5)), "basis_default"),
    ([size_pair(basis="mixed")], report(size=("from_start", 0.5)), "basis_mixed"),
    ([size_pair()], report(size=("from_start", 0.33)), "too_close"),
    ([size_pair(w=0.5, lo=0.45, hi=0.9)], report(size=("from_start", 0.6)), "order_violation"),
    ([color_pair(0.0, 0.95, 0.2)], report(color=("from_start", {"h": 0.55, "l": 0.5})), "beyond_far"),
    ([color_pair(0.6, 0.5611, 0.6444)], report(color=("from_start", {"h": None, "s": 0, "l": 0.5})),
     "report_axis_mismatch"),
    ([DISABLED_COLOR], report(color=("from_start", {"h": 0.1, "l": 0.5})), "pair_invalid:disabled"),
    # 대칭 쌍을 못 찾으면 lo·hi가 남아 있어도 valid=false만 본다
    ([color_pair(0.6, 0.5556, 0.6556, valid=False, skip="asymmetric")], report(color=("from_start", {"h": 0.7, "l": .5})),
     "pair_invalid:asymmetric"),
    ([size_pair()], report(size=("from_start", 0.5), sha="b" * 64), "report_spec_mismatch"),
    ([size_pair()], report(size=("from_start", 0.5), sid="other"), "report_spec_mismatch"),
])
def test_each_exclusion_reason(tmp_path, pairs, rep, reason):
    make_v03(tmp_path, pairs=pairs, prereport=rep)
    res = analyze(tmp_path)
    p = res["pairs"][0]
    assert p["exclusion"] == reason and p["labelled"] is False and p["near_minus_far"] is None
    sh = q1(res)
    if reason == "pair_invalid:disabled":       # 쌍이 모두 꺼진 세션은 Q1(분모 포함)에 들어가지 않는다
        assert sh["nSessions"] == 0 and sh["exclusionReasons"] == {} and sh["participantsWithoutUsablePairs"]["of"] == 0
        return
    assert sh["exclusionReasons"] == {reason: 1}
    assert sh["participantsWithoutUsablePairs"] == {"n": 1, "of": 1, "share": 1.0}


@pytest.mark.parametrize("created, first_view, warned", [
    (AFTER, VIEW_UTC, True),            # 보고 시각이 첫 제시보다 늦어도 러너 복사 해시가 맞으면 쓰고 경고만
    (VIEW_UTC, VIEW_UTC, True),
    (BEFORE, VIEW_UTC, False),
    (AFTER, None, False),               # first_viewing_utc 없음(0.2 등) → 비교 안 함, 제외도 아님
    (AFTER, "2026-11-18T02:00:00.000", False),   # 시간대 표시 없는 문자열은 비교하지 않는다
])
def test_clock_comparison_is_only_a_warning(tmp_path, created, first_view, warned):
    make_v03(tmp_path, pairs=[size_pair()], ratings={"size_hi": 6, "size_lo": 3},
             prereport=report(size=("from_start", 0.5), created=created), first_view=first_view)
    res = analyze(tmp_path)
    assert res["pairs"][0]["labelled"] is True and res["pairs"][0]["exclusion"] is None
    assert res["summary"]["reportClockWarnings"] == (1 if warned else 0)
    assert any(w["message"].startswith("report_clock_warning") for w in res["summary"]["warnings"]) is warned


@pytest.mark.parametrize("man_prereport, raw, reason", [
    ({"file": "prereport.json", "sha256": "c" * 64}, None, "report_spec_mismatch"),   # 복사본 해시가 다름
    (None, None, "report_spec_mismatch"),                                              # manifest는 보고 없음이라는데 파일이 있음
    ({"file": "prereport.json"}, None, "report_spec_mismatch"),                         # 러너 해시 없음 → 건너뛰지 않고 제외
    ("absent", None, "report_spec_mismatch"),                                          # manifest에 prereport 키 자체가 없음
    ("auto", b"{not json", "report_invalid"),
    ("auto", json.dumps({**report(size=("from_start", 0.5)), "altSpecSha256": ["x"]}).encode(), "report_invalid"),
    ("auto", json.dumps({**report(size=("not_set", None)), "schema": "ifs-prereport/9"}).encode(), "report_invalid"),
])
def test_link_and_format_failures(tmp_path, man_prereport, raw, reason):
    make_v03(tmp_path, pairs=[size_pair()], prereport=report(size=("from_start", 0.5)), raw_prereport=raw,
             man_prereport=man_prereport)
    res = analyze(tmp_path)                                  # 깨진 파일이 분석을 멈추지 않는다
    assert res["pairs"][0]["exclusion"] == reason
    assert q1(res)["shiftDrop"]["byCommitment"][reason]["n"] == 1


def test_invalid_report_value_with_not_set_is_report_invalid(tmp_path):
    bad = report(size=("not_set", None))
    bad["attributes"]["size"]["value"] = 0.4            # ③인데 값이 있음 → 스키마 위반
    make_v03(tmp_path, pairs=[size_pair()], raw_prereport=json.dumps(bad).encode())
    res = analyze(tmp_path)
    assert res["pairs"][0]["exclusion"] == "report_invalid" and res["sessions"][0]["prereport"] == "report_invalid"


def test_v01_report_is_legacy_in_primary(tmp_path):
    rep = {"schema": "ifs-prereport/0.1", "sessionId": "s03", "participant": None, "specSha256": SHA,
           "taskTextFile": "prereport_task.v0.json", "taskTextVersion": "0.1", "createdAtUtc": "2026-11-18T01:00:00Z",
           "attributes": {"color": {"commitment": "not_set", "value": None, "method": "hue_lightness_field",
                                    "nSelections": 0},
                          "size": {"commitment": "from_start", "value": 0.5, "method": "size_slider", "nSelections": 1},
                          "form": {"commitment": "not_set"}, "motion": {"commitment": "not_set"}}}
    make_v03(tmp_path, pairs=[size_pair()], ratings={"size_hi": 6, "size_lo": 3}, prereport=rep)
    res = analyze(tmp_path)
    p = pair(res, "size")
    # 0.1 보고는 첫 선택·물리 폭이 관측되지 않아 주 분석에서 빼고 보조(최종 선택) 집계에만 남긴다
    assert p["exclusion"] == "report_legacy" and not p["labelled"]
    assert p["labelled_final"] and p["near_minus_far_final"] == 3
    assert q1(res)["nearMinusFar"]["finalPick"]["fromStart"]["participantMean"]["mean"] == 3
    assert q1(res)["nearMinusFar"]["primary"]["participantMean"]["n"] == 0


# ---------------------------------------------------------------- 첫 선택(주) · 최종 선택(보조)

def test_primary_uses_first_pick_final_is_supplementary(tmp_path):
    # 첫 선택 0.5 → near hi(+3). 최종 0.1 → near lo(−3)
    make_v03(tmp_path, pairs=[size_pair()], ratings={"size_hi": 6, "size_lo": 3},
             prereport=report(size=("from_start", 0.1), size_first=0.5))
    res = analyze(tmp_path)
    p = pair(res, "size")
    assert (p["near"], p["near_minus_far"], p["near_final"], p["near_minus_far_final"]) == ("size_hi", 3, "size_lo", -3)
    nf = q1(res)["nearMinusFar"]
    assert nf["primary"]["participantMean"]["mean"] == 3
    assert nf["finalPick"]["fromStart"]["participantMean"]["mean"] == -3


def test_commitment_changed_after_pick_is_counted(tmp_path):
    make_v03(tmp_path, pairs=[color_pair(0.6, 0.5611, 0.6444)],
             prereport=report(color=("not_set", None), changed=True))
    res = analyze(tmp_path)
    assert pair(res, "color")["exclusion"] == "not_set" and q1(res)["commitmentChangedAfterPick"] == 1


# ---------------------------------------------------------------- 제시·평정 검증

def test_shift_variant_not_presented(tmp_path):
    folder = make_v03(tmp_path, pairs=[size_pair()], prereport=report(size=("from_start", 0.5)),
                      order=["orig", *MISMATCH, "size_lo"],
                      extra_rating_rows=[[7, "size_hi", 7, 900, 30000, 0, "resemblance"]])
    assert folder.exists()
    assert analyze(tmp_path)["pairs"][0]["exclusion"] == "not_presented"


@pytest.mark.parametrize("item", ["", "mine"])
def test_rating_with_empty_or_other_item_is_missing(tmp_path, item):
    make_v03(tmp_path, pairs=[size_pair()], prereport=report(size=("from_start", 0.5)),
             ratings={"size_hi": 7, "size_lo": 2}, item_of={"size_hi": item})
    res = analyze(tmp_path)
    assert res["pairs"][0]["exclusion"] == "missing_rating"
    assert any("다른 문항 행" in w["message"] for w in res["summary"]["warnings"])


# ---------------------------------------------------------------- 문항 분리

def test_q1_uses_resemblance_only_and_items_are_not_mixed(tmp_path):
    # 같은 참여자·세션을 두 문항으로 실행: 둘 다 남고, 'mine'의 +5는 Q1에 들어가지 않는다
    make_v03(tmp_path, pnum=1, sid="s03", pairs=[size_pair()], rating_item="mine", utc="20261118-010000",
             ratings={"size_lo": 2, "size_hi": 7, "orig": 7, "form": 1},
             prereport=report(size=("from_start", 0.5)))
    make_v03(tmp_path, pnum=1, sid="s03", pairs=[size_pair()], rating_item="resemblance", utc="20261118-020000",
             ratings={"size_lo": 6, "size_hi": 7, "orig": 6, "form": 5},
             prereport=report(size=("from_start", 0.5)))
    # 0.2 기록(문항 mine으로 봄)
    old = make_v03(tmp_path, pnum=2, sid="old", pairs=[], ratings={"orig": 6, "form": 3})
    man = json.loads((old / "manifest.json").read_text(encoding="utf-8"))
    man["recordVersion"] = "ifs-ownership/0.2"
    for k in ("shiftPairs", "ratingItem", "prereport"):
        man.pop(k, None)
    for v in man["variants"]:
        v.pop("kind")
    (old / "manifest.json").write_text(json.dumps(man), encoding="utf-8")

    res = analyze(tmp_path, tmp_path / "out")
    assert len(res["sessions"]) == 3 and res["summary"]["records"]["skipped"] == 0
    assert {(s["session"], s["rating_item"]) for s in res["sessions"]} == {
        ("s03", "mine"), ("s03", "resemblance"), ("old", "mine")}
    sm = res["summary"]["summaries"]
    assert set(sm) == {"mine", "resemblance"}
    assert sm["mine"]["all"]["rq1"]["form"]["ratingDrop"] == {"mean": 4.5, "n": 2, "lowN": True}
    assert sm["resemblance"]["all"]["rq1"]["form"]["ratingDrop"] == {"mean": 1, "n": 1, "lowN": True}
    pm = q1(res)["nearMinusFar"]["primary"]["participantMean"]
    assert pm["mean"] == 1 and pm["n"] == 1 and q1(res)["nSessions"] == 1


def test_primary_estimate_is_mean_of_participant_means_with_t_ci(tmp_path):
    make_v03(tmp_path, pnum=1, sid="a", pairs=[size_pair(), color_pair(0.6, 0.5556, 0.6556)],
             ratings={"size_hi": 6, "size_lo": 3, "color_hi": 5, "color_lo": 4},
             prereport=report(size=("from_start", 0.5), color=("from_start", {"h": 0.7, "l": 0.5}), sid="a"))
    make_v03(tmp_path, pnum=2, sid="b", pairs=[size_pair()], ratings={"size_hi": 3, "size_lo": 5},
             prereport=report(size=("from_start", 0.5), sid="b"))
    make_v03(tmp_path, pnum=3, sid="c", pairs=[size_pair()], ratings={"size_hi": 7, "size_lo": 6},
             prereport=report(size=("when_asked", 0.5), sid="c"))
    make_v03(tmp_path, pnum=4, sid="d", pairs=[size_pair()], ratings={"orig": 7, "size_hi": 3, "size_lo": 5})
    # 쌍이 모두 disabled인 세션은 0쌍 비율 분모에 들어가지 않는다
    make_v03(tmp_path, pnum=5, sid="e", pairs=[DISABLED_COLOR])
    sh = q1(analyze(tmp_path))
    pm = sh["nearMinusFar"]["primary"]["participantMean"]
    assert pm["mean"] == 0 and pm["n"] == 2 and pm["ci95"] == pytest.approx([-25.4124, 25.4124], abs=1e-3)
    assert sh["nearMinusFar"]["whenAsked"]["participantMean"]["mean"] == 1
    assert sh["participantsWithoutUsablePairs"] == {"n": 1, "of": 4, "share": 0.25}
    assert sh["participantsWithoutFromStartPairs"] == {"n": 2, "of": 4, "share": 0.5}
    assert sh["shiftDrop"]["byCommitment"]["no_report"]["mean"] == 3
    assert sh["shiftDrop"]["byCommitment"]["when_asked"]["mean"] == pytest.approx(-1.5)
    assert sh["nSessions"] == 4


# ---------------------------------------------------------------- 제시 집합 · 순서 길이 · 균형

@pytest.mark.parametrize("n_pairs", [1, 2])
def test_order_length_7_and_9(tmp_path, n_pairs):
    pairs = [size_pair(), color_pair(0.6, 0.5611, 0.6444)][:n_pairs]
    make_v03(tmp_path, pairs=pairs, ratings={"orig": 6, "form": 2, "color": 3, "size": 4, "motion": 5},
             prereport=report(size=("from_start", 0.5), color=("from_start", {"h": 0.7, "l": 0.5})))
    res = analyze(tmp_path, tmp_path / "out")
    n = 5 + 2 * n_pairs
    assert len(res["stimuli"]) == n and res["sessions"][0]["n_order_rows"] == (2 * n)
    assert not [w for w in res["summary"]["warnings"] if "order" in w["message"]]
    rq1 = res["summary"]["summaries"]["resemblance"]["all"]["rq1"]
    assert {a: rq1[a]["ratingDrop"]["mean"] for a in MISMATCH} == {"form": 4, "color": 3, "size": 2, "motion": 1}
    assert all(p["labelled"] for p in res["pairs"])
    bal = res["summary"]["orderBalance"]["byConditionSet"]
    assert len(bal) == 1 and next(iter(bal.values()))["nOrderRows"] == 2 * n


def test_choice_and_correlation_use_orig_and_mismatch_only(tmp_path):
    make_v03(tmp_path, pnum=1, sid="a", pairs=[size_pair()], final="size_hi",
             ratings={"orig": 7, "form": 1, "color": 2, "size": 3, "motion": 4, "size_lo": 5, "size_hi": 6})
    make_v03(tmp_path, pnum=2, sid="b", pairs=[size_pair()], final="orig")
    res = analyze(tmp_path)
    rq1 = res["summary"]["summaries"]["resemblance"]["all"]["rq1"]
    assert rq1["choseShift"] == {"n": 1, "of": 2} and rq1["presentationSet"] == "orig+mismatch"
    assert rq1["orig"]["choiceRate"] == {"mean": 1, "n": 1, "lowN": True}       # shift를 고른 세션은 분모에서 빠짐
    assert rq1["form"]["choiceRate"]["n"] == 1


def test_order_balance_by_condition_set_and_order_rows(tmp_path):
    for n in (1, 2):
        make_v03(tmp_path, pnum=n, sid=f"nine{n}", pairs=[size_pair(), color_pair(0.6, 0.5611, 0.6444)])
    make_v03(tmp_path, pnum=3, sid="seven", pairs=[size_pair()])
    bal = analyze(tmp_path)["summary"]["orderBalance"]
    assert {k: v["nOrderRows"] for k, v in bal["byConditionSet"].items()} == {
        "color|color_hi|color_lo|form|motion|orig|size|size_hi|size_lo": 18,
        "color|form|motion|orig|size|size_hi|size_lo": 14}
    assert bal["byConditionSet"]["color|form|motion|orig|size|size_hi|size_lo"]["byOrderRow"]["2"] == 1


# ---------------------------------------------------------------- Unity 실제 출력(합성 spec)

def _real(tmp_path, name, rep, ratings=None, sha=None):
    man = json.loads((FIX / name).read_text(encoding="utf-8"))
    if sha is not None:
        man["specSha256"] = sha
    return make_v03(tmp_path, pnum=man["participantNumber"], sid=man["sessionId"], manifest=man, prereport=rep,
                    ratings=ratings), man


def test_real_unity_manifest_placeholder_hash_is_excluded(tmp_path):
    man = json.loads((FIX / "manifest_stated.json").read_text(encoding="utf-8"))
    assert man["specSha256"] == "0" and man["prereport"] is None
    _real(tmp_path, "manifest_stated.json",
          report(color=("from_start", {"h": 0.7, "l": 0.5}), sid=man["sessionId"]))
    res = analyze(tmp_path)
    assert {p["exclusion"] for p in res["pairs"]} == {"report_spec_mismatch"}


def test_real_unity_manifest_stated(tmp_path):
    rep = report(color=("from_start", {"h": 0.7, "l": 0.5}), size=("when_asked", 0.1), sid="SYN-shift-stated")
    _, man = _real(tmp_path, "manifest_stated.json", rep, sha=SHA,
                   ratings={"color_hi": 6, "color_lo": 2, "size_lo": 5, "size_hi": 4})
    assert man["recordVersion"] == "ifs-ownership/0.3" and len(man["order"]) == 9 and man["orderRows"] == 18
    res = analyze(tmp_path)
    c, s = pair(res, "color", man["sessionId"]), pair(res, "size", man["sessionId"])
    assert (c["axis"], c["near"], c["near_minus_far"], c["commitment"]) == ("hue", "color_hi", 4, "from_start")
    # 크기는 manifest의 wM·loM·hiM(0.201/0.1523/0.2653 m)과 보고 폭(0.35·2^((0.1−0.5)·4) ≈ 0.115 m)을 미터로 비교
    assert (s["near"], s["near_minus_far"], s["size_scale_fallback"]) == ("size_lo", 1, False)
    assert res["sessions"][0]["condition_set"] == man["conditionSet"]
    assert {r["kind"] for r in res["stimuli"]} == {"orig", "mismatch", "shift"}


def test_real_unity_manifest_default(tmp_path):
    rep = report(color=("from_start", {"h": 0.2, "l": 0.95}), size=("from_start", 0.9), sid="SYN-shift-default")
    _, man = _real(tmp_path, "manifest_default.json", rep, sha=SHA)
    res = analyze(tmp_path)
    assert [p["exclusion"] for p in res["pairs"]] == ["basis_default", "basis_default"]
    assert pair(res, "color", man["sessionId"])["axis"] == "lightness"


def test_commitment_at_pick_differs_is_excluded_from_primary_only(tmp_path):
    rep = report(size=("when_asked", 0.5))
    rep["attributes"]["size"]["commitmentAtPick"] = "from_start"      # 고를 때 ①, 최종 ②
    make_v03(tmp_path, pairs=[size_pair()], ratings={"size_hi": 6, "size_lo": 3}, prereport=rep)
    p = pair(analyze(tmp_path), "size")
    assert p["exclusion"] == "commitment_changed" and p["labelled_final"] and p["near_minus_far_final"] == 3
    rep["attributes"]["size"]["commitmentAtPick"] = "when_asked"      # 같으면 주 분석에 들어간다
    make_v03(tmp_path / "same", pairs=[size_pair()], ratings={"size_hi": 6, "size_lo": 3}, prereport=rep)
    assert pair(analyze(tmp_path / "same"), "size")["labelled"] is True


@pytest.mark.parametrize("width, reason, near", [
    # 원본·lo의 log 거리가 같은 보고(기하평균 √(0.5·0.4), 6자리) → 기록 정밀도에서 구분 안 됨 → order_violation
    (round((0.5 * 0.4) ** 0.5, 6), "order_violation", None),
    (0.45, "order_violation", None),         # w/lo/hi = .5/.4/.6 m에 0.45 m: lo가 원본보다 가깝지 않음
    (0.3, None, "size_lo"),
    (0.8, None, "size_hi"),
])
def test_meter_distances_with_record_precision(tmp_path, width, reason, near):
    rep = report(size=("from_start", 0.5))
    rep["attributes"]["size"]["widthM"] = rep["attributes"]["size"]["firstWidthM"] = width
    make_v03(tmp_path, pairs=[size_pair(w=0.5, lo=0.4, hi=0.6, m=(0.5, 0.4, 0.6))], prereport=rep,
             ratings={"size_lo": 3, "size_hi": 6})
    p = pair(analyze(tmp_path), "size")
    assert (p["exclusion"], p["near"], p["size_scale_fallback"]) == (reason, near, False)


def _legacy(folder, keep=()):
    man = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    man["recordVersion"] = "ifs-ownership/0.2"
    for k in ("shiftPairs", "ratingItem", "prereport"):
        if k not in keep:
            man.pop(k, None)
    if "kind" not in keep:
        for v in man["variants"]:
            v.pop("kind")
    (folder / "manifest.json").write_text(json.dumps(man), encoding="utf-8")


def test_legacy_record_with_v03_fields_is_quarantined(tmp_path):
    ok = make_v03(tmp_path, pnum=1, sid="ok", pairs=[], ratings={"orig": 6, "form": 3})
    _legacy(ok)
    bad = make_v03(tmp_path, pnum=2, sid="bad", pairs=[size_pair()], ratings={"orig": 6, "form": 1},
                   prereport=report(size=("from_start", 0.5), sid="bad"))
    _legacy(bad, keep=("ratingItem", "shiftPairs", "kind"))
    res = analyze(tmp_path)
    by = {s["session"]: s for s in res["sessions"]}
    assert by["bad"]["rating_item"] == "mine" and by["bad"]["excluded"] == "quarantined"
    assert by["ok"]["rating_item"] == "mine" and by["ok"]["excluded"] == ""
    summ = res["summary"]
    assert summ["quarantined"] == [{"record": "ownership/P002/bad/20261118-010000", "recordVersion": "ifs-ownership/0.2"}]
    assert summ["records"]["quarantined"] == 1 and res["pairs"] == []
    assert summ["summaries"]["mine"]["all"]["rq1"]["form"]["ratingDrop"] == {"mean": 3, "n": 1, "lowN": True}
    assert summ["shift"]["all"]["nSessions"] == 0
    assert any("격리" in w["message"] for w in summ["warnings"])


def test_withdrawn_sessions_are_dropped_before_reading(tmp_path):
    make_v03(tmp_path / "rec", pnum=1, sid="keep", pairs=[size_pair()])
    make_v03(tmp_path / "rec", pnum=2, sid="gone", pairs=[size_pair()])
    lst = tmp_path / "withdrawn.txt"
    lst.write_text("# 철회 목록\ngone\n\n", encoding="utf-8")
    ownership.main(["--records", str(tmp_path / "rec"), "--out", str(tmp_path / "out"), "--withdrawn", str(lst)])
    data = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert data["records"]["withdrawn"] == 1 and data["records"]["sessions"] == 1
    assert "gone" not in (tmp_path / "out" / "sessions.csv").read_text(encoding="utf-8")
    assert "gone" not in (tmp_path / "out" / "shift_pairs.csv").read_text(encoding="utf-8")


def test_output_inside_git_repo_is_warned_unless_ignored(tmp_path):
    import subprocess
    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        pytest.skip("git 없음")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    make_v03(tmp_path / "rec", pairs=[size_pair()])
    res = analyze(tmp_path / "rec", repo / "out")
    msgs = [w["message"] for w in res["summary"]["warnings"] if "git 저장소" in w["message"]]
    assert len(msgs) == 1 and "shift_pairs.csv" in msgs[0]
    (repo / ".gitignore").write_text("out/\n", encoding="utf-8")
    res = analyze(tmp_path / "rec", repo / "out2")
    assert any("git 저장소" in w["message"] for w in res["summary"]["warnings"])
    res = analyze(tmp_path / "rec", repo / "out")
    assert not any("git 저장소" in w["message"] for w in res["summary"]["warnings"])
    res = analyze(tmp_path / "rec", tmp_path / "outside")
    assert not any("git 저장소" in w["message"] for w in res["summary"]["warnings"])
