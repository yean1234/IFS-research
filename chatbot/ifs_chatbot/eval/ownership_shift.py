"""소유감 기록 0.3의 같은 말·다른 값 쌍(shiftPairs)과 보기 전 보고(prereport.json) 분석. ownership.py가 부른다.
LLM 없음, 결정론적. 근거: docs/rq-v2-proposal.md 3.1–3.2. 보고 형식 검사는 서버와 같은 스키마
(ifs_chatbot.prereport.validate, jsonschema)로 한다.

입력(기록 폴더 하나)
- manifest.shiftPairs: {attribute, axis(size|hue|lightness), basis(stated|default|mixed), w, lo, hi, step, deltaE_lo,
  deltaE_hi, valid, skipReason[, wM, loM, hiM, deltaEComposited_lo/hi, axisChoiceBasis, provenanceWithoutValue,
  categoryCheck]}. 축 값은 0–1(hue = 색상각/360, 0/1에서 감김). wM·loM·hiM = 화면에 그린 가장 넓은 가로 폭(m).
  없는 필드는 없는 대로 읽는다.
- 변형 id {attribute}_lo · {attribute}_hi (kind "shift"). 평정은 ownership.load_session이 문항 검사 뒤 넘긴다.
- prereport.json(기록 폴더에 있을 때만, ifs-prereport/0.1 · 0.2)과 manifest.prereport{file, sha256, specSha256, ...}.

보고 연결(하나라도 어기면 보고를 쓰지 않음, 쌍마다 사유)
- 파일 없음 → no_report. 읽기·스키마 위반 → report_invalid(분석은 멈추지 않는다).
- report_spec_mismatch: manifest.prereport가 null인데 파일이 있음 · manifest.prereport.sha256과 파일 바이트 sha256이 다름
  · manifest.specSha256이 64자리 hex가 아님(예: "0") · 보고의 specSha256(과 확정 때 고정한 altSpecSha256)에
  manifest.specSha256이 없음 · 보고와 manifest의 sessionId가 다름.
- report_time_unknown: 형상 첫 제시 시각을 못 구함(경고). report_after_viewing: 보고 createdAtUtc ≥ 첫 제시 시각.
  첫 제시 시각은 first_presentation_utc(): manifest의 명시 필드가 있으면 그것, 없으면 startedAtUtc + events.csv의
  가장 이른 viewing_start(없으면 phase viewing) time_ms. time_ms는 startedAtUtc부터 잰 밀리초로 본다(가정).

쌍마다(첫 의도적 선택 = 주 분석, 최종 선택 = 보조. 0.1 보고는 firstValue가 없어 둘 다 value)
1) 보고값 p를 쌍의 축에 투영: hue → color.h(무채색 보고 h=null이면 report_axis_mismatch), lightness → color.l,
   size → widthM과 manifest wM·loM·hiM이 모두 있으면 log2(미터), 아니면 0–1 눈금(size_scale_fallback 표시, 제외 아님).
2) 값을 기록 정밀도(소수 4자리)의 정수 단위로 바꿔 거리를 잰다(hue는 주기 10000의 원형 최단 거리).
3) 가까운(near)/먼(far)을 붙이는 조건: commitment ① 또는 ② · basis == stated · 2·d(w,p) ≥ 문턱 ·
   d(near,p) < d(w,p) < d(far,p). 문턱 = 크기 0–1 눈금이면 step, 그 밖(색·미터 크기)은 min(d(lo,w), d(hi,w)).
   d(lo,p) = d(hi,p) · d(near,p) ≥ d(w,p) · d(w,p) = d(far,p) → order_violation, d(w,p) > d(far,p) → beyond_far.
4) 제외 사유(검사 순서대로 첫 번째): pair_invalid:<skipReason> → not_presented → 보고 연결 사유 → not_set →
   basis_default · basis_mixed → report_axis_mismatch → too_close → order_violation · beyond_far → missing_rating.
5) near_minus_far = rating(near) − rating(far). shift_drop = rating(orig) − 평균(rating(lo), rating(hi))
   (제시된 유효 쌍, 세 평정이 모두 있을 때), 보고 상태(①②③ 또는 연결 사유)별로 나눠 요약.

요약(Q1은 ratingItem == resemblance 세션만 — 호출하는 쪽이 거른다)
- 주 추정: 첫 선택 기준 from_start 쌍만 참여자마다 평균 → 참여자 평균의 평균과 95% CI(t). 속성별, when_asked(탐색),
  최종 선택 기준(보조)도 같은 꼴로.
- 0쌍 비율: 분모 = disabled가 아닌 쌍이 하나라도 있는 세션의 참여자.
- 보고값 p와 ①②③은 분석에만 쓰고 장면 JSON에는 쓰지 않는다(AGENTS.md 1·2).
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..prereport import validate as validate_report

PREREPORT_FILE = "prereport.json"
COMMITMENTS = ("from_start", "when_asked", "not_set")
REPORT_PROBLEMS = ("no_report", "report_invalid", "report_spec_mismatch", "report_after_viewing", "report_time_unknown")
GROUPS = (*COMMITMENTS, *REPORT_PROBLEMS)
SHIFT_ATTRIBUTES = ("color", "size")
AXIS_ATTRIBUTE = {"size": "size", "hue": "color", "lightness": "color"}
SCALE = 10000                 # 기록 정밀도(소수 4자리)
FIRST_PRESENTATION_FIELDS = ("firstPresentationUtc", "firstViewingStartUtc", "firstViewingUtc")

PAIR_COLUMNS = [
    "participant", "session", "record_folder", "rating_item", "attribute", "axis", "basis", "w", "lo", "hi", "step",
    "w_m", "lo_m", "hi_m", "delta_e_lo", "delta_e_hi", "valid", "skip_reason", "presented",
    "report_status", "commitment", "commitment_changed_after_pick", "first_from_final",
    "p", "p_m", "d_w", "threshold", "size_scale_fallback", "near", "far", "labelled", "exclusion", "near_minus_far",
    "p_final", "near_final", "labelled_final", "exclusion_final", "near_minus_far_final",
    "rating_orig", "rating_lo", "rating_hi", "shift_drop", "included",
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


def is_sha256(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)


# ---------------------------------------------------------------- 시각

def parse_utc(v) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def first_presentation_utc(manifest: dict, viewing_start_ms: list[float]) -> datetime | None:
    """형상 첫 제시 시각(UTC). manifest의 명시 필드(FIRST_PRESENTATION_FIELDS)가 먼저,
    없으면 startedAtUtc + 가장 이른 viewing_start time_ms. 못 구하면 None."""
    for k in FIRST_PRESENTATION_FIELDS:
        t = parse_utc(manifest.get(k))
        if t is not None:
            return t
    start = parse_utc(manifest.get("startedAtUtc"))
    times = [t for t in viewing_start_ms if t is not None]
    if start is None or not times:
        return None
    return start + timedelta(milliseconds=min(times))


# ---------------------------------------------------------------- 거리(정수 단위)

def _q(x: float) -> int:
    return int(round(x * SCALE))


def int_distance(axis: str, a: int, b: int) -> int:
    if axis == "hue":
        d = (b - a) % SCALE
        return min(d, SCALE - d)
    return abs(a - b)


def signed_hue_diff(a: float, b: float) -> float:
    """a에서 b로 가는 부호 있는 최단 색상 차이(주기 1), −0.5 이상 0.5 미만(정수 단위로 계산)."""
    d = (_q(b) - _q(a)) % SCALE
    return (d - SCALE if d >= SCALE // 2 else d) / SCALE


def axis_distance(axis: str, a: float, b: float) -> float:
    return int_distance(axis, _q(a), _q(b)) / SCALE


def classify(axis: str, w: int, lo: int, hi: int, p: int, threshold: int) -> tuple[str | None, str | None, int]:
    """→ (제외 사유 또는 None, near 쪽 'lo'|'hi' 또는 None, d(w,p)). 모든 값은 같은 정수 단위."""
    dist = "hue" if axis == "hue" else "line"
    d_w, d_lo, d_hi = int_distance(dist, w, p), int_distance(dist, lo, p), int_distance(dist, hi, p)
    if 2 * d_w < threshold:
        return "too_close", None, d_w
    if d_lo == d_hi:
        return "order_violation", None, d_w
    near, d_near, d_far = ("lo", d_lo, d_hi) if d_lo < d_hi else ("hi", d_hi, d_lo)
    if d_near >= d_w or d_w == d_far:
        return "order_violation", None, d_w
    if d_w > d_far:
        return "beyond_far", None, d_w
    return None, near, d_w


# ---------------------------------------------------------------- 보기 전 보고 읽기

def load_prereport(folder: Path, manifest: dict, first_view: datetime | None) -> tuple[dict | None, str, list[str]]:
    """→ (보고 또는 None, 상태, 경고). 상태 = "ok" 또는 REPORT_PROBLEMS 중 하나. 어떤 파일도 예외를 내지 않는다."""
    path = Path(folder) / PREREPORT_FILE
    mp = manifest.get("prereport", "absent")
    if not path.is_file():
        if isinstance(mp, dict):
            return None, "no_report", ["manifest.prereport가 있는데 기록 폴더에 prereport.json이 없음 — no_report"]
        return None, "no_report", []
    try:
        raw = path.read_bytes()
        rep = json.loads(raw.decode("utf-8-sig"))
        problems = validate_report(rep)
    except Exception as exc:  # noqa: BLE001 — 깨진 파일 하나가 분석을 멈추지 않게
        return None, "report_invalid", [f"prereport.json 읽기 실패({type(exc).__name__}) — report_invalid로 제외"]
    if problems:
        return None, "report_invalid", [f"prereport.json 형식 오류({problems[0]}) — report_invalid로 제외"]

    def mismatch(why: str):
        return None, "report_spec_mismatch", [f"prereport.json 연결 실패: {why} — report_spec_mismatch로 제외"]

    if mp is None:
        return mismatch("manifest.prereport가 null인데 기록 폴더에 파일이 있음")
    if isinstance(mp, dict) and mp.get("sha256") is not None and hashlib.sha256(raw).hexdigest() != mp.get("sha256"):
        return mismatch("파일 sha256이 manifest.prereport.sha256과 다름")
    sha = manifest.get("specSha256")
    if not is_sha256(sha):
        return mismatch(f"manifest.specSha256이 sha256 형식이 아님({sha!r})")
    if sha not in {rep["specSha256"], *(rep.get("altSpecSha256") or {}).values()}:
        return mismatch("보고의 specSha256이 manifest.specSha256과 다름(다른 장면의 보고)")
    if manifest.get("sessionId") is not None and rep["sessionId"] != manifest.get("sessionId"):
        return mismatch(f"보고 sessionId '{rep['sessionId']}' ≠ manifest '{manifest.get('sessionId')}'")
    created = parse_utc(rep["createdAtUtc"])
    if first_view is None or created is None:
        return None, "report_time_unknown", [
            "형상 첫 제시 시각을 구하지 못함(manifest 시작 시각·events.csv viewing_start) — report_time_unknown로 제외"]
    if created >= first_view:
        return None, "report_after_viewing", [
            f"보고 시각 {rep['createdAtUtc']}이 첫 제시 {first_view.isoformat()}보다 늦음 — report_after_viewing로 제외"]
    return rep, "ok", []


def _pick(rep: dict, attr: str, which: str):
    """→ (값, 폭 m, firstFromFinal). which = first | final."""
    a = rep["attributes"][attr]
    has_first = "firstValue" in a
    if which == "first" and has_first:
        return a.get("firstValue"), a.get("firstWidthM"), False
    return a.get("value"), a.get("widthM"), which == "first"


# ---------------------------------------------------------------- 쌍

def _label(row: dict, raw: dict, rep: dict, which: str) -> dict:
    """한 선택(첫·최종)으로 near/far를 정한다. → {exclusion, near, far, p, p_m, d_w, threshold, fallback, firstFromFinal}"""
    axis, attr = row["axis"], row["attribute"]
    out = {"exclusion": None, "near": None, "far": None, "p": None, "p_m": None, "d_w": None, "threshold": None,
           "fallback": None, "firstFromFinal": False}
    val, width, out["firstFromFinal"] = _pick(rep, attr, which)
    w, lo, hi, step = row["w"], row["lo"], row["hi"], row["step"]
    if axis == "size":
        out["p"] = _num(val)
        out["p_m"] = _num(width)
        wm, lom, him = (_num(raw.get(k)) for k in ("wM", "loM", "hiM"))
        if all(x is not None and x > 0 for x in (wm, lom, him, out["p_m"])):
            out["fallback"] = False
            qw, qlo, qhi, qp = (_q(math.log2(x)) for x in (wm, lom, him, out["p_m"]))
            thr = min(abs(qlo - qw), abs(qhi - qw))
        else:
            out["fallback"] = True
            if out["p"] is None:
                out["exclusion"] = "report_invalid"
                return out
            qw, qlo, qhi, qp = _q(w), _q(lo), _q(hi), _q(out["p"])
            thr = _q(step)
    else:
        if not isinstance(val, dict):
            out["exclusion"] = "report_invalid"
            return out
        if axis == "hue" and val.get("h") is None:
            out["exclusion"] = "report_axis_mismatch"       # 무채색 보고는 색상 축에 투영할 수 없다
            return out
        out["p"] = _num(val.get("h" if axis == "hue" else "l"))
        qw, qlo, qhi, qp = _q(w), _q(lo), _q(hi), _q(out["p"])
        dist = "hue" if axis == "hue" else "line"
        thr = min(int_distance(dist, qlo, qw), int_distance(dist, qhi, qw))
    excl, near, d_w = classify(axis, qw, qlo, qhi, qp, thr)
    out["d_w"], out["threshold"] = d_w / SCALE, thr / SCALE / 2
    if excl:
        out["exclusion"] = excl
        return out
    out["near"], out["far"] = f"{attr}_{near}", f"{attr}_{'hi' if near == 'lo' else 'lo'}"
    return out


def pair_rows(participant: str, session: str, manifest: dict, ratings: dict[str, float | None],
              presented: set[str], report: dict | None, report_status: str) -> tuple[list[dict], list[str]]:
    """manifest.shiftPairs 한 세션분 → (쌍 행 목록, 경고). ratings = 문항 검사를 통과한 평정(변형 id → 값).
    presented = order에도 있고 variants에서 kind shift인 변형 id."""
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
        row = {c: None for c in PAIR_COLUMNS}
        row.update({
            "participant": participant, "session": session, "attribute": attr, "axis": axis, "basis": raw.get("basis"),
            "w": _num(raw.get("w")), "lo": _num(raw.get("lo")), "hi": _num(raw.get("hi")), "step": _num(raw.get("step")),
            "w_m": _num(raw.get("wM")), "lo_m": _num(raw.get("loM")), "hi_m": _num(raw.get("hiM")),
            "delta_e_lo": _num(raw.get("deltaE_lo")), "delta_e_hi": _num(raw.get("deltaE_hi")),
            "valid": raw.get("valid") is True, "skip_reason": raw.get("skipReason"),
            "report_status": report_status, "labelled": False, "labelled_final": False,
            "rating_orig": ratings.get("orig"), "included": True,
        })
        out.append(row)

        def exclude(reason: str, final_too: bool = True):
            row["exclusion"] = reason
            if final_too:
                row["exclusion_final"] = reason

        if axis not in AXIS_ATTRIBUTE or AXIS_ATTRIBUTE[axis] != attr:
            exclude("pair_invalid:axis_attribute")
            warns.append(f"shiftPairs의 attribute '{attr}'·axis '{axis}' 조합을 모름 — 제외")
            continue
        if report is not None:
            a = report["attributes"][attr]
            row["commitment"] = a["commitment"]
            row["commitment_changed_after_pick"] = a.get("commitmentChangedAfterPick")
        if not row["valid"]:
            exclude(f"pair_invalid:{raw.get('skipReason') or 'unknown'}")
            continue
        ids = (f"{attr}_lo", f"{attr}_hi")
        row["presented"] = all(i in presented for i in ids)
        if not row["presented"]:
            exclude("not_presented")
            warns.append(f"유효한 {attr} 쌍의 변형이 order·variants(kind shift)에 모두 있지 않음 — not_presented")
            continue
        if None in (row["w"], row["lo"], row["hi"], row["step"]):
            exclude("pair_invalid:missing_values")
            warns.append(f"유효한 {attr} 쌍에 w·lo·hi·step 중 빈 값 — 제외")
            continue
        row["rating_lo"], row["rating_hi"] = ratings.get(ids[0]), ratings.get(ids[1])
        if None not in (row["rating_orig"], row["rating_lo"], row["rating_hi"]):
            row["shift_drop"] = _r(row["rating_orig"] - (row["rating_lo"] + row["rating_hi"]) / 2)
        if report is None:
            exclude(report_status)
            continue
        if row["commitment"] == "not_set":
            exclude("not_set")
            continue
        if row["basis"] != "stated":
            exclude("basis_mixed" if row["basis"] == "mixed" else "basis_default")
            continue
        for which in ("first", "final"):
            lab = _label(row, raw, report, which)
            suffix = "" if which == "first" else "_final"
            row[f"p{suffix}"] = lab["p"]
            row[f"near{suffix}"] = lab["near"]
            if which == "first":
                row.update({"p_m": lab["p_m"], "d_w": lab["d_w"], "threshold": lab["threshold"],
                            "size_scale_fallback": lab["fallback"], "far": lab["far"],
                            "first_from_final": lab["firstFromFinal"]})
            excl = lab["exclusion"]
            if excl is None:
                rn, rf = ratings.get(lab["near"]), ratings.get(lab["far"])
                if rn is None or rf is None:
                    excl = "missing_rating"
                else:
                    row[f"labelled{suffix}"] = True
                    row[f"near_minus_far{suffix}"] = _r(rn - rf)
            row[f"exclusion{suffix}"] = excl
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


def _participant_means(rows: list[dict], key: str) -> list[float]:
    by: dict[str, list[float]] = {}
    for r in rows:
        by.setdefault(r["participant"], []).append(r[key])
    return [sum(v) / len(v) for _, v in sorted(by.items())]


def _near_far(rows: list[dict], commitment: str, low_n: int, suffix: str = "") -> dict:
    lab, key = f"labelled{suffix}", f"near_minus_far{suffix}"
    sel = [r for r in rows if r[lab] and r["commitment"] == commitment]
    return {"participantMean": mean_ci(_participant_means(sel, key), low_n), "nPairs": len(sel),
            "byAttribute": {a: {**mean_ci(_participant_means([r for r in sel if r["attribute"] == a], key), low_n),
                                "nPairs": sum(1 for r in sel if r["attribute"] == a)}
                            for a in SHIFT_ATTRIBUTES}}


def summarize_pairs(rows: list[dict], q1_participants: list[str], low_n: int) -> dict:
    """rows = Q1 세션(문항 resemblance)의 쌍 행. q1_participants = disabled가 아닌 쌍이 하나라도 있는 그 세션들의 참여자."""
    def est(vals):
        vals = [float(v) for v in vals if v is not None]
        n = len(vals)
        return {"mean": _r(sum(vals) / n) if n else None, "n": n, "lowN": n < low_n}

    def share(have: set[str]) -> dict:
        parts = set(q1_participants)
        n_p = len(parts)
        miss = n_p - len(have & parts)
        return {"n": miss, "of": n_p, "share": _r(miss / n_p) if n_p else None}

    def reasons(col: str) -> dict:
        out: dict[str, int] = {}
        for r in rows:
            if r[col]:
                out[r[col]] = out.get(r[col], 0) + 1
        return dict(sorted(out.items()))

    def group(r):
        return r["commitment"] if r["report_status"] == "ok" and r["commitment"] in COMMITMENTS else r["report_status"]

    dropped = [r for r in rows if r["valid"] and r["presented"]]
    return {
        "nPairs": len(rows), "nValidPairs": sum(1 for r in rows if r["valid"]),
        "nLabelledPairs": sum(1 for r in rows if r["labelled"]),
        "nearMinusFar": {
            "primary": {**_near_far(rows, "from_start", low_n),
                        "note": "확증: 첫 의도적 선택 기준, from_start 쌍만, 참여자 평균의 평균, 95% CI(t)"},
            "whenAsked": {**_near_far(rows, "when_asked", low_n), "note": "탐색: 첫 선택 기준 when_asked 쌍"},
            "finalPick": {"fromStart": _near_far(rows, "from_start", low_n, "_final"),
                          "whenAsked": _near_far(rows, "when_asked", low_n, "_final"),
                          "note": "보조: [확인] 때 최종 선택 기준"},
        },
        "participantsWithoutUsablePairs": share({r["participant"] for r in rows if r["labelled"]}),
        "participantsWithoutFromStartPairs": share({r["participant"] for r in rows
                                                    if r["labelled"] and r["commitment"] == "from_start"}),
        "exclusionReasons": reasons("exclusion"),
        "exclusionReasonsFinal": reasons("exclusion_final"),
        "sizeScaleFallbackPairs": sum(1 for r in rows if r["size_scale_fallback"]),
        "commitmentChangedAfterPick": sum(1 for r in rows if r["commitment_changed_after_pick"]),
        "shiftDrop": {
            "byCommitment": {g: est(r["shift_drop"] for r in dropped if group(r) == g) for g in GROUPS},
            "byAttributeCommitment": {a: {g: est(r["shift_drop"] for r in dropped if r["attribute"] == a and group(r) == g)
                                          for g in GROUPS} for a in SHIFT_ATTRIBUTES},
            "note": "shift_drop = rating(orig) − 평균(rating(lo), rating(hi)), 제시된 유효 쌍 단위. "
                    "보고가 없거나 쓸 수 없으면 그 사유(no_report·report_invalid·report_spec_mismatch·"
                    "report_after_viewing·report_time_unknown)로 따로 센다",
        },
    }
