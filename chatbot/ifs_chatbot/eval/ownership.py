"""소유감 실험(후보1) 기록 요약 — Unity 실험 러너가 남긴 ownership 기록을 읽어 형상·세션 표와 RQ1–RQ3 요약을 낸다.
LLM 없음, 표준 라이브러리만, 결정론적(같은 기록 → 같은 출력).

  python -m ifs_chatbot.eval.ownership --records <기록 루트 또는 세션 폴더> --out <폴더> [--orig-threshold 4]
  → <폴더>/stimuli.csv(세션×형상 5행), sessions.csv(세션 1행), summary.json(RQ1–RQ3, 건너뛴 기록, 경고)

기록 형식은 설계 확정본 2.4절(recordVersion "ifs-ownership/0.x"), 행동 지표는 3절을 따른다.
추론 통계(p값)는 내지 않는다: 참여자 수가 작고 검정 계획이 아직 정해지지 않아 기술 통계(평균·n·lowN)만 낸다.

기록 찾기
- --records 아래의 manifest.json을 모두 찾는다(루트·ownership/·P###/·세션·UTC 폴더 어디를 줘도 된다).
  recordVersion이 "ifs-ownership/"로 시작하지 않는 manifest.json은 소유감 기록이 아니므로 무시한다.
- 같은 (participantNumber, sessionId)에 폴더가 여럿이면 summary.completed가 true인 것 중 가장 최근 것
  (UTC 폴더 이름, 같으면 startedAtUtc 순)을 쓰고, 완료된 것이 없으면 가장 최근 미완료 폴더를 쓴다. 나머지는 skipped.
- 출력에는 --records 기준 상대 경로만 적는다(로컬 절대 경로를 남기지 않는다).

2.4절에서 모호해 이 스크립트가 정한 해석(Unity 러너와 맞출 점)
- ratings.csv: 행을 위에서부터 읽는다. cancelled=1 행은 평정으로 쓰지 않고, 같은 형상에 그때까지 유효했던 평정을
  지운다. 그래서 "원래 행을 그대로 두고 취소 행을 덧붙임"과 "원래 행을 cancelled=1로 남김" 두 방식 모두 마지막
  유효 평정이 남는다. variant 칸이 비면 position과 manifest.order로 찾는다.
- view_ms: 그 형상의 ratings.csv 행 중 마지막 view_ms(취소 행 포함)를 쓴다.
- 제시 시작 시각(t0): events.csv의 viewing_start 행(detail "position=N;variant=ID")의 time_ms. 없으면 같은 순간에
  러너가 쓰는 phase 행(detail "viewing;position=N;variant=ID", viewing_start를 넣기 전 기록)을 쓰고, 둘 다 없으면
  그 형상의 첫 viewing 표본 time_ms를 쓰고 warnings에 적는다. t0가 첫 표본보다 늦으면 첫 표본을 쓰고 경고한다.
  어느 것을 썼는지는 stimuli.csv의 start_source(viewing_start / phase / first_sample).
- 표본 지속 시간: 러너는 프레임마다 최대 한 표본을 실제 시각으로 쓴다(밀린 표본을 채우지 않음). 그래서 gaze_ms는
  표본 수 × 고정 간격이 아니라 실제 time_ms 차이로 적분한다. 표본 i의 구간 = time_ms(i) → 같은 형상의 다음 viewing
  표본(첫 표본은 t0부터), 마지막 표본은 명목 간격 1000 / config.headSampleHz(없으면 20). 한 구간이 명목 간격의
  3배를 넘으면 명목 간격까지만 그 표본의 자세로 세고 나머지는 결측으로 본다(gap_ms에 더하고 n_gaps를 1 올림).
  gaze_ratio의 분모는 그대로 view_ms(결측 시간을 빼지 않음).
- first_look_ms: t0부터 원뿔 안 첫 표본의 time_ms까지. 끝까지 원뿔 안을 보지 않으면 빈칸.
- 방위각: 수평면은 x–z(Unity y-up). 방위각 = atan2(head_x − obj_x, head_z − obj_z), 0–360°.
- path_m: 연속한 viewing 표본 사이 3차원 머리 위치 거리의 합(형상마다 따로).
- 형상의 variant는 manifest.order[position − 1]을 기준으로 하고, headpose.csv의 variant 칸이 다르면 경고만 낸다.
- 선택: summary.json finalChoice.variant(없으면 position과 order). finalChoice가 없으면 chosen은 빈칸.
- difference.csv: 형상마다 마지막 행. 원본은 빈칸.
- 원본 평정이 없으면 origBelowThreshold는 빈칸이고, 기준 통과 요약에서 빠진다.

요약 규칙
- completed=false 세션은 sessions.csv에 excluded="incomplete"로 남기고 요약에서 뺀다.
- 원본 평정 < --orig-threshold(기본 4)이면 origBelowThreshold. 요약은 전체(all)와 기준 통과(origAtOrAboveThreshold) 두 벌.
- 추정치마다 n을 함께 적고, n < 5이면 "lowN": true.
- RQ3 상관: 세션 안에서 5개 형상의 rating과 행동 지표의 Spearman ρ(동순위 평균 순위). 짝이 3개 미만이거나
  한쪽 값이 모두 같으면 그 세션은 빠진다. 세션별 ρ의 평균과 세션 수를 낸다.
- 순서 균형(orderBalance): 요약에 포함된 세션의 manifest orderRow(0–9)별·cb(0/1)별 세션 수. 행별 최대 − 최소 > 1
  이거나 cb 두 값의 차이 > 1이면 warnings에 적는다(참여자 번호를 건너뛰거나 다시 쓰면 Williams 균형이 깨진다).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

RECORD_PREFIX = "ifs-ownership/"
SUMMARY_VERSION = "ownership-summary/0.2"   # 0.2: gap_ms·n_gaps·start_source 열, orderBalance
ATTRIBUTES = ("form", "color", "size", "motion")
SOURCES = ("stated", "default", "mixed")
METRICS = ("gaze_ms", "gaze_ratio", "dist_mean_m", "dist_min_m", "azimuth_range_deg", "path_m", "first_look_ms")
LOW_N = 5
MIN_CORR_PAIRS = 3
DEFAULT_ORIG_THRESHOLD = 4.0
DEFAULT_HZ = 20.0
DEFAULT_CONE_DEG = 15.0
GAP_FACTOR = 3.0          # 한 구간이 명목 표본 간격의 이 배수를 넘으면 명목 간격 뒤는 결측
WILLIAMS_ROWS = 10        # unity WilliamsDesign.Rows
VIEWING_START_EVENT = "viewing_start"

STIMULI_COLUMNS = [
    "participant", "session", "position", "variant", "attribute", "source", "rule",
    "said_not_rendered", "forced", "below_target", "motion_alters_scale",
    "magnitude_size_step", "magnitude_delta_e00", "changed_keys",
    "rating", "rating_drop", "chosen", "difference_rating", "view_ms", "rt_ms", "n_cancelled",
    "n_samples", "gap_ms", "n_gaps", "start_source", *METRICS, *(f"{m}_diff" for m in METRICS),
    "included", "orig_below_threshold",
]
SESSION_COLUMNS = [
    "participant", "session", "record_folder", "record_version", "started_at_utc", "cb", "order_row", "order",
    "head_source", "low_visibility", "completed", "aborted_at",
    "orig_rating", "orig_chosen", "chosen_variant", "chosen_position",
    "size_step", "color_delta_e", "view_seconds", "head_sample_hz", "gaze_cone_deg",
    "orig_below_threshold", "excluded",
]


# ---------------------------------------------------------------- 읽기 도우미

def _num(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
    else:
        s = str(v).strip()
        if not s:
            return None
        try:
            x = float(s)
        except ValueError:
            return None
    return x if math.isfinite(x) else None


def _int(v) -> int | None:
    x = _num(v)
    return int(x) if x is not None and x.is_integer() else None


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k is not None} for row in csv.DictReader(f)]


def _rel(folder: Path, root: Path) -> str:
    try:
        r = folder.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        r = folder.name
    return r or "."


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


# ---------------------------------------------------------------- 기록 찾기

def discover(records: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """(participant, session)마다 기록 폴더 하나를 고른다. → (고른 것, 건너뛴 것, 경고)"""
    groups: dict[tuple[int, str], list[dict]] = {}
    skipped: list[dict] = []
    warnings: list[dict] = []
    for mf in sorted(records.rglob("manifest.json")):
        folder = mf.parent
        rel = _rel(folder, records)
        man = _read_json(mf)
        if man is None:
            skipped.append({"record": rel, "reason": "manifest_unreadable"})
            continue
        if not isinstance(man, dict) or not str(man.get("recordVersion", "")).startswith(RECORD_PREFIX):
            continue
        pnum, sid = _int(man.get("participantNumber")), man.get("sessionId")
        if pnum is None or not isinstance(sid, str) or not sid:
            skipped.append({"record": rel, "reason": "manifest_missing_ids"})
            continue
        summ = _read_json(folder / "summary.json")
        if not isinstance(summ, dict):
            warnings.append({"record": rel, "message": "summary.json 없음 또는 읽기 실패 — 미완료로 본다"})
            summ = {}
        groups.setdefault((pnum, sid), []).append({
            "folder": folder, "rel": rel, "manifest": man, "summary": summ,
            "completed": summ.get("completed") is True,
            "sortKey": (folder.name, str(man.get("startedAtUtc") or "")),
        })
    chosen: list[dict] = []
    for key in sorted(groups):
        cands = sorted(groups[key], key=lambda c: c["sortKey"])
        done = [c for c in cands if c["completed"]]
        pick = (done or cands)[-1]
        chosen.append(pick)
        for c in cands:
            if c is not pick:
                skipped.append({"record": c["rel"], "reason": "duplicate", "completed": c["completed"],
                                "usedInstead": pick["rel"]})
    skipped.sort(key=lambda s: s["record"])
    return chosen, skipped, warnings


# ---------------------------------------------------------------- 행동 지표 (3절)

def azimuth_deg(head: tuple[float, float, float], obj: tuple[float, float, float]) -> float:
    """형상 중심을 원점으로 본 머리 위치의 수평(x–z) 방위각, 0 이상 360 미만."""
    return math.degrees(math.atan2(head[0] - obj[0], head[2] - obj[2])) % 360.0


def circular_range_deg(angles: list[float]) -> float | None:
    """방위각들이 덮은 원형 범위 = 360 − 가장 큰 빈 구간. 표본 1개면 0, 없으면 None."""
    if not angles:
        return None
    a = sorted(x % 360.0 for x in angles)
    gaps = [a[i + 1] - a[i] for i in range(len(a) - 1)] + [a[0] + 360.0 - a[-1]]
    return 360.0 - max(gaps)


def behavior_metrics(samples: list[dict], view_ms: float | None, hz: float, cone_deg: float,
                     start_ms: float | None = None) -> dict:
    """viewing 표본(time_ms 순)으로 한 형상의 행동 지표를 계산한다.
    start_ms = 제시 시작 시각(없거나 첫 표본보다 늦으면 첫 표본 시각). 표본 구간 규칙은 모듈 설명 참고."""
    out = {"n_samples": len(samples), "gap_ms": None, "n_gaps": None, **{m: None for m in METRICS}}
    if not samples:
        return out
    nominal = 1000.0 / hz
    cap = GAP_FACTOR * nominal
    t_first = samples[0]["t"]
    t0 = t_first if start_ms is None or start_ms > t_first else start_ms
    in_cone = [s["angle"] is not None and s["angle"] <= cone_deg for s in samples]
    gaze = gap = 0.0
    n_gaps = 0
    for i, s in enumerate(samples):
        begin = t0 if i == 0 else s["t"]
        end = samples[i + 1]["t"] if i + 1 < len(samples) else s["t"] + nominal
        span = max(0.0, end - begin)
        if span > cap:
            gap += span - nominal
            n_gaps += 1
            span = nominal
        if in_cone[i]:
            gaze += span
    out["gap_ms"] = _r(gap, 3)
    out["n_gaps"] = n_gaps
    out["gaze_ms"] = _r(gaze, 3)
    out["gaze_ratio"] = _r(gaze / view_ms, 4) if view_ms else None
    dists = [s["dist"] for s in samples if s["dist"] is not None]
    if dists:
        out["dist_mean_m"] = _r(sum(dists) / len(dists), 4)
        out["dist_min_m"] = _r(min(dists), 4)
    first = next((s["t"] - t0 for s, ok in zip(samples, in_cone) if ok), None)
    out["first_look_ms"] = _r(first, 3)
    pos = [s for s in samples if s["head"] is not None]
    az = [azimuth_deg(s["head"], s["obj"]) for s in pos if s["obj"] is not None]
    out["azimuth_range_deg"] = _r(circular_range_deg(az), 3)
    if pos:
        out["path_m"] = _r(sum(math.dist(pos[i]["head"], pos[i + 1]["head"]) for i in range(len(pos) - 1)), 4)
    return out


def _kv(detail: str) -> dict[str, str]:
    """'position=2;variant=form' → {'position': '2', 'variant': 'form'}. '='가 없는 조각은 버린다."""
    out: dict[str, str] = {}
    for part in (detail or "").split(";"):
        k, sep, v = part.partition("=")
        if sep:
            out[k.strip()] = v.strip()
    return out


def viewing_starts(events: list[dict]) -> dict[int, dict]:
    """events.csv 행 → position별 제시 시작 {t, variant, source}. viewing_start를 먼저 쓰고, 없는 position은
    phase "viewing;…" 행. 같은 position이 여럿이면 처음 것."""
    found: dict[str, dict[int, dict]] = {"viewing_start": {}, "phase": {}}
    for row in events:
        ev, t, detail = row.get("event"), _num(row.get("time_ms")), row.get("detail") or ""
        if t is None:
            continue
        if ev == VIEWING_START_EVENT:
            kind, kv = "viewing_start", _kv(detail)
        elif ev == "phase" and detail.startswith("viewing;"):
            kind, kv = "phase", _kv(detail[len("viewing;"):])
        else:
            continue
        p = _int(kv.get("position"))
        if p is not None and p not in found[kind]:
            found[kind][p] = {"t": t, "variant": kv.get("variant") or None, "source": kind}
    return {**found["phase"], **found["viewing_start"]}


def order_balance(sessions: list[dict]) -> dict:
    """요약에 포함된 세션의 순서 행·cb별 세션 수와 균형 여부(행별 최대 − 최소 ≤ 1, cb 차이 ≤ 1)."""
    rows = {str(r): 0 for r in range(WILLIAMS_ROWS)}
    cbs = {"0": 0, "1": 0}
    unknown_row = unknown_cb = 0
    for s in sessions:
        r, c = s.get("order_row"), s.get("cb")
        if r is not None and 0 <= r < WILLIAMS_ROWS:
            rows[str(r)] += 1
        else:
            unknown_row += 1
        if c in (0, 1):
            cbs[str(c)] += 1
        else:
            unknown_cb += 1
    row_spread = max(rows.values()) - min(rows.values())
    cb_spread = abs(cbs["0"] - cbs["1"])
    return {"sessions": len(sessions), "byOrderRow": rows, "byCb": cbs,
            "unknownOrderRow": unknown_row, "unknownCb": unknown_cb,
            "rowSpread": row_spread, "cbSpread": cb_spread,
            "balanced": row_spread <= 1 and cb_spread <= 1 and unknown_row == 0 and unknown_cb == 0}


def _vec(row: dict, prefix: str) -> tuple[float, float, float] | None:
    v = [_num(row.get(f"{prefix}_{c}")) for c in ("x", "y", "z")]
    return None if any(x is None for x in v) else (v[0], v[1], v[2])


# ---------------------------------------------------------------- 세션 하나

def _variant_at(order: list[str], position) -> str | None:
    p = _int(position)
    return order[p - 1] if p is not None and 1 <= p <= len(order) else None


def load_session(cand: dict, orig_threshold: float) -> tuple[dict, list[dict], list[dict]]:
    """→ (세션 행, 형상 행 목록, 경고 목록). 행 값은 파이썬 값(None = 빈칸)."""
    folder, rel, man, summ = cand["folder"], cand["rel"], cand["manifest"], cand["summary"]
    warns: list[dict] = []

    def warn(msg: str) -> None:
        warns.append({"record": rel, "message": msg})

    pnum, sid = _int(man.get("participantNumber")), man["sessionId"]
    participant = f"P{pnum:03d}"
    config = man.get("config") if isinstance(man.get("config"), dict) else {}
    hz = _num(config.get("headSampleHz"))
    if not hz or hz <= 0:
        hz = DEFAULT_HZ
        warn(f"config.headSampleHz 없음 — {DEFAULT_HZ:g}Hz로 계산")
    cone = _num(config.get("gazeConeDeg"))
    if cone is None:
        cone = DEFAULT_CONE_DEG
        warn(f"config.gazeConeDeg 없음 — {DEFAULT_CONE_DEG:g}°로 계산")
    order = [str(v) for v in man.get("order") or []]
    if len(order) != 5:
        warn(f"order 길이 {len(order)} (5가 아님)")
    variants = {str(v.get("id")): v for v in man.get("variants") or [] if isinstance(v, dict)}
    for v in order:
        if v not in variants:
            warn(f"order의 '{v}'가 variants에 없음")

    # 평정: 위에서부터 읽고 취소 행은 그 형상의 직전 유효 평정을 지운다
    ratings: dict[str, dict] = {}
    n_cancel: dict[str, int] = {}
    view_ms: dict[str, float] = {}
    for row in _read_csv(folder / "ratings.csv"):
        var = row.get("variant") or _variant_at(order, row.get("position"))
        if not var:
            continue
        vm = _num(row.get("view_ms"))
        if vm is not None:
            view_ms[var] = vm
        if _truthy(row.get("cancelled", "0")):
            n_cancel[var] = n_cancel.get(var, 0) + 1
            ratings.pop(var, None)
            continue
        r = _num(row.get("rating"))
        if r is not None:
            ratings[var] = {"rating": r, "rt_ms": _num(row.get("rt_ms"))}
    if isinstance(summ.get("ratings"), dict):
        for var, r in ratings.items():
            sr = _num(summ["ratings"].get(var))
            if sr is not None and sr != r["rating"]:
                warn(f"'{var}' 평정이 ratings.csv({r['rating']:g})와 summary.json({sr:g})에서 다름 — ratings.csv를 씀")

    diff: dict[str, float] = {}
    for row in _read_csv(folder / "difference.csv"):
        r = _num(row.get("rating"))
        if row.get("variant") and r is not None:
            diff[row["variant"]] = r

    fc = summ.get("finalChoice") if isinstance(summ.get("finalChoice"), dict) else None
    chosen_var = None
    if fc:
        chosen_var = fc.get("variant") or _variant_at(order, fc.get("position"))
    chosen_pos = order.index(chosen_var) + 1 if chosen_var in order else None

    # 머리 자세: viewing 표본만, position별
    samples: dict[int, list[dict]] = {}
    mismatch = set()
    for row in _read_csv(folder / "headpose.csv"):
        if row.get("phase") != "viewing":
            continue
        p, t = _int(row.get("position")), _num(row.get("time_ms"))
        if p is None or t is None:
            continue
        expect = _variant_at(order, p)
        if row.get("variant") and expect and row["variant"] != expect:
            mismatch.add(p)
        samples.setdefault(p, []).append({"t": t, "angle": _num(row.get("angle_deg")),
                                          "dist": _num(row.get("distance_m")),
                                          "head": _vec(row, "head"), "obj": _vec(row, "obj")})
    for p in sorted(mismatch):
        warn(f"headpose.csv position {p}의 variant가 manifest.order와 다름 — order를 따름")

    # 제시 시작 시각(events.csv)
    starts = viewing_starts(_read_csv(folder / "events.csv"))
    no_start, late_start = [], []
    start_used: dict[int, tuple] = {}
    for p in sorted(samples):
        first_t = min(s["t"] for s in samples[p])
        st = starts.get(p)
        if st is None:
            no_start.append(p)
            start_used[p] = (None, "first_sample")
            continue
        expect = _variant_at(order, p)
        if st["variant"] and expect and st["variant"] != expect:
            warn(f"events.csv {st['source']} position {p}의 variant '{st['variant']}'가 manifest.order('{expect}')와 다름")
        if st["t"] > first_t:
            late_start.append(p)
            start_used[p] = (None, "first_sample")
        else:
            start_used[p] = (st["t"], st["source"])
    if no_start:
        warn("events.csv에 viewing_start 없음(position " + ", ".join(map(str, no_start))
             + ") — 첫 viewing 표본을 제시 시작으로 씀(first_look_ms가 짧게 나올 수 있음)")
    if late_start:
        warn("viewing_start가 첫 viewing 표본보다 늦음(position " + ", ".join(map(str, late_start))
             + ") — 첫 표본을 제시 시작으로 씀")

    completed = summ.get("completed") is True
    orig_rating = ratings.get("orig", {}).get("rating")
    below = None if orig_rating is None else orig_rating < orig_threshold
    excluded = "" if completed else "incomplete"
    flags = man.get("flags") if isinstance(man.get("flags"), dict) else {}

    srow = {
        "participant": participant, "session": sid, "record_folder": rel,
        "record_version": man.get("recordVersion"), "started_at_utc": man.get("startedAtUtc"),
        "cb": _int(man.get("cb")), "order_row": _int(man.get("orderRow")), "order": "|".join(order),
        "head_source": man.get("headSource"), "low_visibility": bool(flags.get("lowVisibility")),
        "completed": completed, "aborted_at": summ.get("abortedAt"),
        "orig_rating": orig_rating, "orig_chosen": None if chosen_var is None else chosen_var == "orig",
        "chosen_variant": chosen_var, "chosen_position": chosen_pos,
        "size_step": _num(config.get("sizeStep")), "color_delta_e": _num(config.get("colorDeltaE")),
        "view_seconds": _num(config.get("viewSeconds")), "head_sample_hz": hz, "gaze_cone_deg": cone,
        "orig_below_threshold": below, "excluded": excluded,
    }

    rows: list[dict] = []
    for pos, var in enumerate(order, 1):
        v = variants.get(var, {})
        vflags = v.get("flags") if isinstance(v.get("flags"), dict) else {}
        mag = v.get("magnitude") if isinstance(v.get("magnitude"), dict) else {}
        rating = ratings.get(var, {}).get("rating")
        start_ms, start_src = start_used.get(pos, (None, None))
        beh = behavior_metrics(sorted(samples.get(pos, []), key=lambda s: s["t"]), view_ms.get(var), hz, cone, start_ms)
        beh["start_source"] = start_src
        is_orig = var == "orig"
        rows.append({
            "participant": participant, "session": sid, "position": pos, "variant": var,
            "attribute": None if is_orig else (v.get("attribute") or var),
            "source": None if is_orig else v.get("source"),
            "rule": None if is_orig else v.get("rule"),
            "said_not_rendered": None if is_orig else bool(vflags.get("saidNotRendered")),
            "forced": None if is_orig else bool(vflags.get("forced")),
            "below_target": None if is_orig else bool(vflags.get("belowTarget")),
            "motion_alters_scale": None if is_orig else bool(vflags.get("motionAltersScale")),
            "magnitude_size_step": _num(mag.get("sizeStep")),
            "magnitude_delta_e00": _num(mag.get("deltaE00")),
            "changed_keys": "|".join(str(k) for k in v.get("changedKeys") or []),
            "rating": rating,
            "rating_drop": None if rating is None or orig_rating is None else orig_rating - rating,
            "chosen": None if chosen_var is None else var == chosen_var,
            "difference_rating": None if is_orig else diff.get(var),
            "view_ms": view_ms.get(var), "rt_ms": ratings.get(var, {}).get("rt_ms"),
            "n_cancelled": n_cancel.get(var, 0),
            **beh,
            "included": not excluded, "orig_below_threshold": below,
        })
    orig_row = next((r for r in rows if r["variant"] == "orig"), None)
    for r in rows:
        for m in METRICS:
            o = orig_row.get(m) if orig_row else None
            r[f"{m}_diff"] = None if r[m] is None or o is None else _r(r[m] - o, 4)
    return srow, rows, warns


# ---------------------------------------------------------------- 요약

def _est(values) -> dict:
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    return {"mean": _r(sum(vals) / n) if n else None, "n": n, "lowN": n < LOW_N}


def _ranks(xs: list[float]) -> list[float]:
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """동순위 평균 순위의 Pearson 상관. 짝이 MIN_CORR_PAIRS 미만이거나 한쪽 분산이 0이면 None."""
    if len(xs) != len(ys) or len(xs) < MIN_CORR_PAIRS:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def summarize(sessions: list[dict], stimuli: list[dict]) -> dict:
    keys = {(s["participant"], s["session"]) for s in sessions}
    st = [r for r in stimuli if (r["participant"], r["session"]) in keys]
    var_rows = [r for r in st if r["variant"] != "orig"]
    orig_rows = [r for r in st if r["variant"] == "orig"]

    def b(v):
        return None if v is None else (1.0 if v else 0.0)

    rq1 = {"orig": {"rating": _est(r["rating"] for r in orig_rows),
                    "choiceRate": _est(b(r["chosen"]) for r in orig_rows)}}
    for a in ATTRIBUTES:
        rows = [r for r in var_rows if r["attribute"] == a]
        rq1[a] = {"ratingDrop": _est(r["rating_drop"] for r in rows),
                  "choiceRate": _est(b(r["chosen"]) for r in rows)}

    src_names = list(SOURCES)
    if any(r["source"] not in SOURCES for r in var_rows):
        src_names.append("unlabeled")

    def src_of(r):
        return r["source"] if r["source"] in SOURCES else "unlabeled"

    rq2 = {
        "bySource": {s: {"ratingDrop": _est(r["rating_drop"] for r in var_rows if src_of(r) == s)} for s in src_names},
        "byAttributeSource": {a: {s: {"ratingDrop": _est(r["rating_drop"] for r in var_rows
                                                          if r["attribute"] == a and src_of(r) == s)}
                                  for s in src_names} for a in ATTRIBUTES},
        "note": "mixed(바꾼 키 중 말한 것과 기본값이 섞임)는 stated·default와 따로 센다",
    }

    by_session: dict[tuple, list[dict]] = {}
    for r in st:
        by_session.setdefault((r["participant"], r["session"]), []).append(r)
    rq3: dict = {"diffVsOrig": {}, "ratingCorrelation": {}}
    for m in METRICS:
        col = f"{m}_diff"
        rq3["diffVsOrig"][m] = {"all": _est(r[col] for r in var_rows),
                                "byAttribute": {a: _est(r[col] for r in var_rows if r["attribute"] == a)
                                                for a in ATTRIBUTES}}
        rhos = []
        for k in sorted(by_session):
            pairs = [(r["rating"], r[m]) for r in by_session[k] if r["rating"] is not None and r[m] is not None]
            rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
            if rho is not None:
                rhos.append(rho)
        e = _est(rhos)
        rq3["ratingCorrelation"][m] = {"meanRho": e["mean"], "nSessions": e["n"], "lowN": e["lowN"]}
    return {"nSessions": len(keys), "rq1": rq1, "rq2": rq2, "rq3": rq3}


# ---------------------------------------------------------------- 전체 실행

def analyze(records: str | Path, out_dir: str | Path | None = None,
            orig_threshold: float = DEFAULT_ORIG_THRESHOLD) -> dict:
    root = Path(records)
    if not root.exists():
        raise FileNotFoundError(f"기록 경로가 없습니다: {records}")
    chosen, skipped, warnings = discover(root)
    sessions, stimuli = [], []
    for cand in chosen:
        srow, rows, w = load_session(cand, orig_threshold)
        sessions.append(srow)
        stimuli.extend(rows)
        warnings.extend(w)
    included = [s for s in sessions if not s["excluded"]]
    passing = [s for s in included if s["orig_below_threshold"] is False]
    balance = order_balance(included)
    if not balance["balanced"]:
        warnings.append({"record": None, "message": (
            f"순서 불균형: 포함된 세션 {balance['sessions']}개의 orderRow별 수 최대−최소 {balance['rowSpread']}, "
            f"cb 차이 {balance['cbSpread']}, orderRow·cb 모름 {balance['unknownOrderRow']}·{balance['unknownCb']} "
            "— 참여자 번호를 1부터 빠짐없이 차례로 배정했는지 확인")})
    summary = {
        "tool": "ifs_chatbot.eval.ownership",
        "summaryVersion": SUMMARY_VERSION,
        "descriptiveOnly": True,
        "lowNThreshold": LOW_N,
        "origThreshold": orig_threshold,
        "recordVersions": sorted({str(s["record_version"]) for s in sessions}),
        "records": {
            "sessions": len(sessions),
            "included": len(included),
            "excludedIncomplete": sum(1 for s in sessions if s["excluded"] == "incomplete"),
            "origBelowThreshold": sum(1 for s in included if s["orig_below_threshold"] is True),
            "origRatingMissing": sum(1 for s in included if s["orig_below_threshold"] is None),
            "skipped": len(skipped),
        },
        "orderBalance": balance,
        "summaries": {"all": summarize(included, stimuli),
                      "origAtOrAboveThreshold": summarize(passing, stimuli)},
        "skipped": skipped,
        "warnings": warnings,
    }
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_csv(out / "stimuli.csv", STIMULI_COLUMNS, stimuli)
        _write_csv(out / "sessions.csv", SESSION_COLUMNS, sessions)
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"sessions": sessions, "stimuli": stimuli, "summary": summary}


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(round(v, 4))
    return str(v)


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow([_cell(r.get(c)) for c in columns])


def _print_summary(summary: dict) -> None:
    rec = summary["records"]
    print(f"세션 {rec['sessions']}개(요약 포함 {rec['included']}, 미완료 제외 {rec['excludedIncomplete']}, "
          f"원본 평정 기준 미달 {rec['origBelowThreshold']}, 건너뛴 폴더 {rec['skipped']}) · 경고 {len(summary['warnings'])}")
    rq1 = summary["summaries"]["all"]["rq1"]
    print(f"  원본 선택률 {rq1['orig']['choiceRate']['mean']} (n={rq1['orig']['choiceRate']['n']})")
    for a in ATTRIBUTES:
        d, c = rq1[a]["ratingDrop"], rq1[a]["choiceRate"]
        low = " lowN" if d["lowN"] else ""
        print(f"  {a:<6} 평정 하락 {d['mean']} (n={d['n']}{low})  선택률 {c['mean']}")


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.ownership", description="소유감 실험 기록 요약(기술 통계)")
    ap.add_argument("--records", required=True, help="기록 루트(ownership/P###/... 위) 또는 그 아래 아무 폴더")
    ap.add_argument("--out", required=True, help="결과 폴더(stimuli.csv, sessions.csv, summary.json)")
    ap.add_argument("--orig-threshold", type=float, default=DEFAULT_ORIG_THRESHOLD,
                    help=f"원본 평정이 이 값 미만이면 origBelowThreshold(기본 {DEFAULT_ORIG_THRESHOLD:g})")
    args = ap.parse_args(argv)
    if not Path(args.records).exists():
        ap.error(f"--records 경로가 없습니다: {args.records}")
    res = analyze(args.records, args.out, args.orig_threshold)
    _print_summary(res["summary"])
    print(f"결과: {Path(args.out) / 'summary.json'}")


if __name__ == "__main__":
    main()
