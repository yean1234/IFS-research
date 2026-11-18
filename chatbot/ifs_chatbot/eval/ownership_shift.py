"""소유감 기록 0.3의 같은 말·다른 값 쌍(shiftPairs)과 보기 전 보고(prereport.json) 분석. ownership.py가 부른다.
LLM 없음, 표준 라이브러리만, 결정론적. 근거: docs/rq-v2-proposal.md 3.1–3.2.

입력(세션 폴더 하나)
- manifest.shiftPairs: {attribute, axis(size|hue|lightness), basis(stated|default|mixed), w, lo, hi, step,
  deltaE_lo, deltaE_hi, valid, skipReason}. 축 값은 모두 0–1(hue = 색상각/360, 원형).
- 변형 id는 {attribute}_lo · {attribute}_hi (kind "shift"). 평정은 ownership.load_session이 읽은 값을 받는다.
- prereport.json(세션 폴더에 있을 때만, 형식 shared/schemas/prereport.v0.json). 없으면 no_report.

쌍마다 하는 일
1) 보고값 p를 쌍의 축에 투영: hue → color.value.h, lightness → color.value.l, size → size.value.
   거리 d는 size·lightness에서 |a − b|, hue에서 부호 있는 최단 각 차이의 절댓값(0.98과 0.02의 거리 = 0.04).
2) 가까운(near) = lo·hi 중 p에 더 가까운 쪽, 먼(far) = 다른 쪽. 다음을 모두 만족할 때만 near/far를 붙인다.
   commitment가 from_start 또는 when_asked · basis == stated · d(w, p) ≥ step/2 · d(near, p) < d(w, p) < d(far, p).
3) 붙이지 못하면 제외 사유를 하나 남긴다(검사 순서대로 첫 번째):
   pair_invalid:<skipReason> → no_report → report_invalid · report_spec_mismatch → not_set →
   basis_default · basis_mixed → too_close → order_violation(d(near,p) ≥ d(w,p), lo·hi가 p에서 같은 거리 포함)
   · beyond_far(d(w,p) ≥ d(far,p): 원형 색상에서 p가 먼 쪽을 넘어 반대편에 있음) → missing_rating(near·far 평정 없음).
4) near_minus_far = rating(near) − rating(far) (붙인 쌍만).
   shift_drop = rating(orig) − 평균(rating(lo), rating(hi)) (유효한 쌍이고 세 평정이 모두 있을 때). 보고 확정 여부로 나눠 요약.

요약
- 주 추정: from_start 쌍만 참여자마다 평균 → 참여자 평균의 평균과 95% 신뢰구간(t 분포, 참여자 수 n, n < 5면 lowN).
  같은 것을 속성(color·size)마다, when_asked 쌍으로 따로(탐색) 낸다.
- 붙인 쌍이 하나도 없는 참여자 비율, 제외 사유 수, 확정 여부별 shift_drop(쌍 단위 평균·n·lowN).
- 보고값 p와 ①②③은 분석에만 쓰고 장면 JSON에는 쓰지 않는다(AGENTS.md 1·2).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

PREREPORT_FILE = "prereport.json"
PREREPORT_SCHEMA = "ifs-prereport/0.1"
COMMITMENTS = ("from_start", "when_asked", "not_set")
GROUPS = (*COMMITMENTS, "no_report")
SHIFT_ATTRIBUTES = ("color", "size")
AXIS_ATTRIBUTE = {"size": "size", "hue": "color", "lightness": "color"}
LABELLED = ("from_start", "when_asked")

PAIR_COLUMNS = [
    "participant", "session", "attribute", "axis", "basis", "w", "lo", "hi", "step", "delta_e_lo", "delta_e_hi",
    "valid", "skip_reason", "commitment", "p", "d_w", "near", "far", "labelled", "exclusion",
    "rating_orig", "rating_lo", "rating_hi", "rating_near", "rating_far", "near_minus_far", "shift_drop", "included",
]


def _num(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


# ---------------------------------------------------------------- 거리

def signed_hue_diff(a: float, b: float) -> float:
    """a에서 b로 가는 부호 있는 최단 색상 차이(주기 1), −0.5 이상 0.5 미만."""
    return ((b - a + 0.5) % 1.0) - 0.5


def axis_distance(axis: str, a: float, b: float) -> float:
    return abs(signed_hue_diff(a, b)) if axis == "hue" else abs(a - b)


# ---------------------------------------------------------------- 보기 전 보고 읽기

def _check_report(rep) -> str | None:
    """가벼운 형식 검사(표준 라이브러리만). 문제가 있으면 설명, 없으면 None. 전체 검사는 shared/schemas/prereport.v0.json."""
    if not isinstance(rep, dict) or rep.get("schema") != PREREPORT_SCHEMA:
        return f"schema가 {PREREPORT_SCHEMA}가 아님"
    attrs = rep.get("attributes")
    if not isinstance(attrs, dict):
        return "attributes 없음"
    for a in ("color", "size", "form", "motion"):
        x = attrs.get(a)
        if not isinstance(x, dict) or x.get("commitment") not in COMMITMENTS:
            return f"attributes.{a}.commitment가 없거나 모르는 값"
    for a in SHIFT_ATTRIBUTES:
        x = attrs[a]
        v = x.get("value")
        if x["commitment"] == "not_set":
            if v is not None:
                return f"attributes.{a}: not_set인데 값이 있음"
            continue
        if a == "color":
            ok = isinstance(v, dict) and all(_num(v.get(k)) is not None and 0 <= _num(v.get(k)) <= 1 for k in ("h", "l"))
        else:
            ok = _num(v) is not None and 0 <= _num(v) <= 1
        if not ok:
            return f"attributes.{a}: {x['commitment']}인데 값이 없거나 0–1 밖"
    return None


def load_prereport(folder: Path, manifest: dict) -> tuple[dict | None, str | None, list[str]]:
    """→ (보고, 보고를 못 쓰는 사유 또는 None, 경고 문장들). 파일이 없으면 (None, None, [])."""
    path = Path(folder) / PREREPORT_FILE
    if not path.is_file():
        return None, None, []
    try:
        rep = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, "report_invalid", ["prereport.json 읽기 실패 — 보고 없음으로 보지 않고 report_invalid로 제외"]
    problem = _check_report(rep)
    if problem:
        return None, "report_invalid", [f"prereport.json 형식 오류({problem}) — report_invalid로 제외"]
    warns = []
    sha = manifest.get("specSha256")
    shas = {rep.get("specSha256"), *((rep.get("altSpecSha256") or {}).values())}
    if isinstance(sha, str) and sha and sha not in shas:
        return None, "report_spec_mismatch", [
            "prereport.json의 specSha256이 manifest.specSha256과 다름(다른 장면의 보고) — report_spec_mismatch로 제외"]
    if rep.get("sessionId") and manifest.get("sessionId") and rep["sessionId"] != manifest["sessionId"]:
        warns.append(f"prereport.json sessionId '{rep['sessionId']}'가 manifest '{manifest['sessionId']}'와 다름"
                     " — specSha256이 맞아 그대로 씀")
    return rep, None, warns


def report_value(rep: dict, axis: str) -> float | None:
    attrs = rep["attributes"]
    if axis == "size":
        return _num(attrs["size"].get("value"))
    v = attrs["color"].get("value")
    if not isinstance(v, dict):
        return None
    return _num(v.get("h" if axis == "hue" else "l"))


# ---------------------------------------------------------------- 쌍

def pair_rows(participant: str, session: str, manifest: dict, ratings: dict[str, float | None],
              report: dict | None, report_problem: str | None) -> tuple[list[dict], list[str]]:
    """manifest.shiftPairs 한 세션분 → (쌍 행 목록, 경고 문장). ratings = 변형 id → 평정(없으면 None)."""
    out, warns = [], []
    pairs = manifest.get("shiftPairs")
    if pairs is None:
        return out, warns
    if not isinstance(pairs, list):
        return out, ["manifest.shiftPairs가 배열이 아님 — 쌍 분석에서 뺌"]
    for raw in pairs:
        if not isinstance(raw, dict):
            warns.append("shiftPairs 항목이 객체가 아님 — 건너뜀")
            continue
        attr, axis = raw.get("attribute"), raw.get("axis")
        w, lo, hi, step = (_num(raw.get(k)) for k in ("w", "lo", "hi", "step"))
        valid = raw.get("valid") is True
        row = {
            "participant": participant, "session": session, "attribute": attr, "axis": axis,
            "basis": raw.get("basis"), "w": w, "lo": lo, "hi": hi, "step": step,
            "delta_e_lo": _num(raw.get("deltaE_lo")), "delta_e_hi": _num(raw.get("deltaE_hi")),
            "valid": valid, "skip_reason": raw.get("skipReason"),
            "commitment": None, "p": None, "d_w": None, "near": None, "far": None, "labelled": False,
            "exclusion": None, "rating_orig": ratings.get("orig"), "rating_lo": None, "rating_hi": None,
            "rating_near": None, "rating_far": None, "near_minus_far": None, "shift_drop": None, "included": True,
        }
        out.append(row)
        if axis not in AXIS_ATTRIBUTE or AXIS_ATTRIBUTE[axis] != attr:
            row["exclusion"] = "pair_invalid:axis_attribute"
            warns.append(f"shiftPairs의 attribute '{attr}'·axis '{axis}' 조합을 모름 — 제외")
            continue
        if report is not None:
            row["commitment"] = report["attributes"][attr]["commitment"]
        if not valid:
            row["exclusion"] = f"pair_invalid:{raw.get('skipReason') or 'unknown'}"
            continue
        vid_lo, vid_hi = f"{attr}_lo", f"{attr}_hi"
        row["rating_lo"], row["rating_hi"] = ratings.get(vid_lo), ratings.get(vid_hi)
        if None in (w, lo, hi, step):
            row["exclusion"] = "pair_invalid:missing_values"
            warns.append(f"유효한 {attr} 쌍에 w·lo·hi·step 중 빈 값 — 제외")
            continue
        if None not in (row["rating_orig"], row["rating_lo"], row["rating_hi"]):
            row["shift_drop"] = _r(row["rating_orig"] - (row["rating_lo"] + row["rating_hi"]) / 2)
        if report is None:
            row["exclusion"] = report_problem or "no_report"
            continue
        if row["commitment"] == "not_set":
            row["exclusion"] = "not_set"
            continue
        if row["basis"] != "stated":
            row["exclusion"] = "basis_mixed" if row["basis"] == "mixed" else "basis_default"
            continue
        p = report_value(report, axis)
        row["p"] = p
        if p is None:                      # 형식 검사를 통과했으면 생기지 않는다
            row["exclusion"] = "report_invalid"
            continue
        d_w = axis_distance(axis, w, p)
        d_lo, d_hi = axis_distance(axis, lo, p), axis_distance(axis, hi, p)
        row["d_w"] = _r(d_w, 6)
        if d_w < step / 2:
            row["exclusion"] = "too_close"
            continue
        near, far, d_near, d_far = ("lo", "hi", d_lo, d_hi) if d_lo < d_hi else ("hi", "lo", d_hi, d_lo)
        if d_lo == d_hi or not d_near < d_w:
            row["exclusion"] = "order_violation"
            continue
        if not d_w < d_far:
            row["exclusion"] = "beyond_far"
            continue
        row["near"], row["far"] = f"{attr}_{near}", f"{attr}_{far}"
        row["rating_near"], row["rating_far"] = ratings.get(row["near"]), ratings.get(row["far"])
        if row["rating_near"] is None or row["rating_far"] is None:
            row["exclusion"] = "missing_rating"
            continue
        row["labelled"] = True
        row["near_minus_far"] = _r(row["rating_near"] - row["rating_far"])
    return out, warns


# ---------------------------------------------------------------- 요약 통계

def _betacf(a: float, b: float, x: float) -> float:
    """정규화 불완전 베타의 연분수(Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    tail = 0.5 * _betainc(df / 2, 0.5, x)
    return 1 - tail if t >= 0 else tail


def t_quantile(q: float, df: float) -> float:
    """t 분포 분위수(q > 0.5). 이분법이라 결정론적."""
    lo, hi = 0.0, 1e4
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def mean_ci(values, low_n: int) -> dict:
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    out = {"mean": None, "sd": None, "ci95": None, "n": n, "lowN": n < low_n}
    if not n:
        return out
    m = sum(vals) / n
    out["mean"] = _r(m)
    if n >= 2:
        sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))
        half = t_quantile(0.975, n - 1) * sd / math.sqrt(n)
        out["sd"] = _r(sd)
        out["ci95"] = [_r(m - half), _r(m + half)]
    return out


def _participant_means(rows: list[dict]) -> dict[str, float]:
    by: dict[str, list[float]] = {}
    for r in rows:
        by.setdefault(r["participant"], []).append(r["near_minus_far"])
    return {p: sum(v) / len(v) for p, v in sorted(by.items())}


def _near_far(rows: list[dict], commitment: str, low_n: int) -> dict:
    sel = [r for r in rows if r["labelled"] and r["commitment"] == commitment]
    pm = _participant_means(sel)
    return {"participantMean": mean_ci(pm.values(), low_n), "nPairs": len(sel),
            "byAttribute": {a: {**mean_ci(_participant_means([r for r in sel if r["attribute"] == a]).values(), low_n),
                                "nPairs": sum(1 for r in sel if r["attribute"] == a)}
                            for a in SHIFT_ATTRIBUTES}}


def summarize_pairs(rows: list[dict], participants: list[str], low_n: int) -> dict:
    """rows = 요약에 넣을 세션의 쌍 행. participants = 그 세션들의 참여자(쌍이 없는 참여자 포함)."""
    def est(vals):
        vals = [float(v) for v in vals if v is not None]
        n = len(vals)
        return {"mean": _r(sum(vals) / n) if n else None, "n": n, "lowN": n < low_n}

    parts = sorted(set(participants))
    usable = {r["participant"] for r in rows if r["labelled"]}
    from_start = {r["participant"] for r in rows if r["labelled"] and r["commitment"] == "from_start"}
    reasons: dict[str, int] = {}
    for r in rows:
        if r["exclusion"]:
            reasons[r["exclusion"]] = reasons.get(r["exclusion"], 0) + 1

    def group(r):
        return r["commitment"] if r["commitment"] in COMMITMENTS else "no_report"

    valid = [r for r in rows if r["valid"]]
    n_p = len(parts)
    return {
        "nPairs": len(rows), "nValidPairs": len(valid), "nLabelledPairs": sum(1 for r in rows if r["labelled"]),
        "nearMinusFar": {
            "primary": {**_near_far(rows, "from_start", low_n),
                        "note": "확증: from_start 쌍만, 참여자마다 평균 → 참여자 평균의 평균, 95% CI(t)"},
            "whenAsked": {**_near_far(rows, "when_asked", low_n), "note": "탐색: when_asked 쌍만"},
        },
        "participantsWithoutUsablePairs": {
            "n": n_p - len(usable & set(parts)), "of": n_p,
            "share": _r((n_p - len(usable & set(parts))) / n_p) if n_p else None},
        "participantsWithoutFromStartPairs": {
            "n": n_p - len(from_start & set(parts)), "of": n_p,
            "share": _r((n_p - len(from_start & set(parts))) / n_p) if n_p else None},
        "exclusionReasons": dict(sorted(reasons.items())),
        "shiftDrop": {
            "byCommitment": {g: est(r["shift_drop"] for r in valid if group(r) == g) for g in GROUPS},
            "byAttributeCommitment": {a: {g: est(r["shift_drop"] for r in valid if r["attribute"] == a and group(r) == g)
                                          for g in GROUPS} for a in SHIFT_ATTRIBUTES},
            "note": "shift_drop = rating(orig) − 평균(rating(lo), rating(hi)), 유효한 쌍 단위",
        },
    }
