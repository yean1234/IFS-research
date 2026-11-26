"""소유감 실험(후보1) 기록 요약 — Unity 실험 러너가 남긴 ownership 기록을 읽어 형상·세션 표와 RQ1–RQ3 요약을 낸다.
LLM 없음, 표준 라이브러리만, 결정론적(같은 기록 → 같은 출력).

  python -m ifs_chatbot.eval.ownership --records <기록 루트 또는 세션 폴더> --out <폴더> [--orig-threshold 4]
  → <폴더>/stimuli.csv(세션×형상 n행), sessions.csv(세션 1행), shift_pairs.csv(0.3 쌍 1행),
    summary.json(RQ1–RQ3, 쌍 분석 shift, 건너뛴 기록, 경고)

기록 형식은 설계 확정본 2.4절(recordVersion "ifs-ownership/0.x"), 행동 지표는 3절을 따른다.
0.1·0.2·0.3을 모두 읽는다.
0.3(docs/rq-v2-proposal.md 3.1–3.2, unity/README.md 기록 표): manifest ratingItem·shiftPairs·variants[].kind
(orig | mismatch | shift), ratings.csv 끝 열 item, order 길이 n(5·7·9). 같은 말·다른 값 쌍(color_lo/hi · size_lo/hi)과
세션 폴더의 prereport.json(보기 전 보고, 없을 수 있음) 분석은 ownership_shift.py가 하고 shift_pairs.csv와
summary의 shift 절로 나온다. kind가 없는 0.1·0.2 기록은 orig 밖을 모두 mismatch로 본다. RQ1·RQ2·RQ3 diffVsOrig는
mismatch 변형만 쓴다(shift 변형을 섞지 않는다). RQ3 평정 상관은 세션 안 모든 형상(n개)을 쓴다.
평정 문항(ratingItem): recordVersion으로 정한다. 0.1·0.2 기록은 항상 'mine'(내 것 같다). 0.1·0.2 manifest에 0.3 전용
필드(ratingItem·shiftPairs·variants[].kind)가 있으면 경고하고 그 세션을 격리한다(excluded = quarantined, summary
quarantined 목록; Q1과 문항별 요약에서 빠짐). 0.3은 manifest.ratingItem(없으면 'unknown').
철회: --withdrawn <파일>(세션 ID 한 줄에 하나)의 세션은 기록 폴더를 읽기 전에 빼고 records.withdrawn에 개수만 남긴다.
출력 폴더가 git 저장소 안이고 출력 파일이 무시 규칙에 걸리지 않으면 경고한다.
0.3 ratings.csv는 item이 비어 있지 않고 manifest.ratingItem과 같은 행만 평정으로 쓴다(다른·빈 문항 행은 세어서 경고).
기존 요약(RQ1–RQ3)은 문항별로 따로 낸다(summaries.<문항>). 문항이 다른 세션을 평균하지 않는다.
같은 참여자·세션을 두 문항으로 따로 실행한 기록은 문항별로 각각 남는다(기록 고르기 키 = 참여자·세션·문항).
Q1(가까운−먼, shift)은 ratingItem == 'resemblance' 세션만 쓴다.
선택률(choiceRate)과 행동 상관(RQ3)은 원본 + mismatch 변형 제시 집합으로만 낸다. 최종 선택이 shift 변형인 세션은
선택률 분모에서 빼고 rq1.choseShift로 따로 센다.
순서 균형은 조건 집합(manifest 조건 집합 키, 없으면 order의 정렬된 id 목록)별로, 행 수 = manifest.orderRows
(없으면 조건 수 n이 짝수면 n, 홀수면 2n)로 낸다.
쌍 요약의 95% 신뢰구간(t 분포)은 과제 요구로 넣었다. p값은 여전히 내지 않는다. 0.2에서 늘어난 값(색 변형 magnitude.deltaE00Composited, taskText.draftCount)은 0.1 기록에서 빈칸이다.
magnitude_delta_e00은 0.1에서는 HSL 해석값 기준, 0.2에서는 셰이더 알베도(밝기 배율 포함) 기준이다(record_version 열로 구분).
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
- 순서 균형(orderBalance): 요약에 포함된 세션의 manifest orderRow(0–9)별·cb(0/1)별·orderRow×cb 20칸별 세션 수.
  행별 최대 − 최소 > 1, cb 두 값의 차이 > 1, 또는 20칸의 최대 − 최소 > 1이면 warnings에 적는다(참여자 번호를 건너뛰거나
  다시 쓰면 Williams 균형이 깨진다). Unity의 cb는 10명 단위마다 뒤집히므로(WilliamsDesign.CbFor) 1번부터 차례로
  배정하면 20칸이 고르게 찬다. 예전 규칙(cb = (번호 − 1) mod 2)으로 모은 기록은 행과 cb가 묶여 칸 불균형으로 경고된다.
- 초안 문구: manifest taskText.draftCount > 0인 세션(문구 status draft로 수집)이 있으면 warnings에 적는다.
  sessions.csv의 draft_phrases = draftCount(0.1 기록은 빈칸).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from . import ownership_shift as shift

RECORD_PREFIX = "ifs-ownership/"
SUMMARY_VERSION = "ownership-summary/0.5"   # 0.2: gap_ms·n_gaps·start_source 열, orderBalance
#                                               0.3: magnitude_delta_e00_composited·draft_phrases 열, orderBalance.byOrderRowCb
#                                               0.4: 기록 0.3 읽기 — kind·rating_item 등 열, shift_pairs.csv, summaries.*.shift
#                                               0.5: summaries.<문항>.{all,origAtOrAboveThreshold}, 최상위 shift(문항
#                                                    resemblance만), orderBalance.byConditionSet, rq1.choseShift
ATTRIBUTES = ("form", "color", "size", "motion")
SOURCES = ("stated", "default", "mixed")
METRICS = ("gaze_ms", "gaze_ratio", "dist_mean_m", "dist_min_m", "azimuth_range_deg", "path_m", "first_look_ms")
LOW_N = 5
MIN_CORR_PAIRS = 3
DEFAULT_ORIG_THRESHOLD = 4.0
DEFAULT_HZ = 20.0
DEFAULT_CONE_DEG = 15.0
GAP_FACTOR = 3.0          # 한 구간이 명목 표본 간격의 이 배수를 넘으면 명목 간격 뒤는 결측
WILLIAMS_ROWS = 10        # unity WilliamsDesign.Rows (5조건)
LEGACY_ITEM = "mine"      # 0.1·0.2 기록의 평정 문항
Q1_ITEM = "resemblance"   # 가까운−먼(Q1)에 쓰는 문항
VIEWING_START_EVENT = "viewing_start"

STIMULI_COLUMNS = [
    "participant", "session", "rating_item", "position", "variant", "kind", "attribute", "source", "rule",
    "said_not_rendered", "forced", "below_target", "motion_alters_scale",
    "magnitude_size_step", "magnitude_delta_e00", "magnitude_delta_e00_composited", "changed_keys",
    "rating", "rating_drop", "chosen", "difference_rating", "view_ms", "rt_ms", "n_cancelled",
    "n_samples", "gap_ms", "n_gaps", "start_source", *METRICS, *(f"{m}_diff" for m in METRICS),
    "included", "orig_below_threshold",
]
SESSION_COLUMNS = [
    "participant", "session", "record_folder", "record_version", "started_at_utc", "cb", "order_row", "order",
    "head_source", "low_visibility", "completed", "aborted_at",
    "orig_rating", "orig_chosen", "chosen_variant", "chosen_position",
    "size_step", "color_delta_e", "view_seconds", "head_sample_hz", "gaze_cone_deg",
    "task_text_version", "draft_phrases", "rating_item", "n_positions", "condition_set", "n_order_rows",
    "chose_shift", "first_presentation_utc", "prereport", "n_shift_pairs", "q1_eligible",
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

def record_version(man: dict) -> tuple[int, ...] | None:
    try:
        return tuple(int(x) for x in str(man.get("recordVersion", ""))[len(RECORD_PREFIX):].split("."))
    except ValueError:
        return None


def is_v03(man: dict) -> bool:
    """필드 유무가 아니라 recordVersion으로 정한다. 0.1·0.2만 예전 형식(읽을 수 없는 판 번호는 0.3 이후로 본다)."""
    v = record_version(man)
    return v is None or v >= (0, 3)


def legacy_v03_fields(man: dict) -> list[str]:
    """0.1·0.2 manifest에 들어 있으면 안 되는 0.3 전용 필드."""
    found = [k for k in ("ratingItem", "shiftPairs") if k in man]
    if any(isinstance(v, dict) and "kind" in v for v in man.get("variants") or []):
        found.append("variants[].kind")
    return found


def rating_item_of(man: dict) -> str:
    """평정 문항. 0.1·0.2 = 항상 mine(0.3 전용 필드가 있어도). 0.3 = manifest.ratingItem(없으면 unknown)."""
    if not is_v03(man):
        return LEGACY_ITEM
    ri = man.get("ratingItem")
    return ri if isinstance(ri, str) and ri else "unknown"


def discover(records: Path, withdrawn: set[str] | None = None) -> tuple[list[dict], list[dict], list[dict], int]:
    """(participant, session, 평정 문항)마다 기록 폴더 하나를 고른다. → (고른 것, 건너뛴 것, 경고, 철회로 뺀 폴더 수)
    withdrawn의 세션 ID는 평정·보고를 읽기 전에 뺀다(개수만 남긴다)."""
    withdrawn = withdrawn or set()
    n_withdrawn = 0
    groups: dict[tuple[int, str, str], list[dict]] = {}
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
        if isinstance(sid, str) and sid in withdrawn:
            n_withdrawn += 1
            continue
        if pnum is None or not isinstance(sid, str) or not sid:
            skipped.append({"record": rel, "reason": "manifest_missing_ids"})
            continue
        summ = _read_json(folder / "summary.json")
        if not isinstance(summ, dict):
            warnings.append({"record": rel, "message": "summary.json 없음 또는 읽기 실패 — 미완료로 본다"})
            summ = {}
        item = rating_item_of(man)
        groups.setdefault((pnum, sid, item), []).append({
            "folder": folder, "rel": rel, "manifest": man, "summary": summ, "item": item,
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
    return chosen, skipped, warnings, n_withdrawn


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


def cb_for(participant: int) -> int:
    """Unity WilliamsDesign.CbFor와 같은 규칙: (번호 − 1) mod 2를 10명 단위마다 뒤집는다(1–10번은 예전과 같음)."""
    return ((participant - 1) % 2) ^ (((participant - 1) // WILLIAMS_ROWS) % 2)


def order_rows_for(man: dict, n: int) -> int:
    """Williams 순서 행 수: manifest.orderRows가 있으면 그 값, 없으면 조건 수 n이 짝수면 n, 홀수면 2n."""
    r = _int(man.get("orderRows"))
    if r is not None and r > 0:
        return r
    return n if n % 2 == 0 else 2 * n


def condition_set_of(man: dict, order: list[str]) -> str:
    for k in ("conditionSet", "conditionSetKey", "conditions"):
        v = man.get(k)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, list) and v:
            return "|".join(sorted(str(x) for x in v))
    return "|".join(sorted(order))


def order_balance(sessions: list[dict]) -> dict:
    """조건 집합별로 order_balance_one을 낸다. balanced = 모든 집합이 균형."""
    sets: dict[str, list[dict]] = {}
    for s in sessions:
        sets.setdefault(s.get("condition_set") or "", []).append(s)
    by = {k: order_balance_one(v, max((s.get("n_order_rows") or WILLIAMS_ROWS) for s in v)) for k, v in sorted(sets.items())}
    return {"sessions": len(sessions), "byConditionSet": by, "balanced": all(b["balanced"] for b in by.values())}


def order_balance_one(sessions: list[dict], n_rows: int = WILLIAMS_ROWS) -> dict:
    """한 조건 집합 세션의 순서 행·cb·행×cb 칸별 세션 수와 균형 여부
    (행별 최대 − 최소 ≤ 1, cb 차이 ≤ 1, 칸 최대 − 최소 ≤ 1)."""
    rows = {str(r): 0 for r in range(n_rows)}
    cbs = {"0": 0, "1": 0}
    cells = {f"{r}:{c}": 0 for r in range(n_rows) for c in (0, 1)}
    unknown_row = unknown_cb = 0
    for s in sessions:
        r, c = s.get("order_row"), s.get("cb")
        row_ok = r is not None and 0 <= r < n_rows
        if row_ok:
            rows[str(r)] += 1
        else:
            unknown_row += 1
        if c in (0, 1):
            cbs[str(c)] += 1
        else:
            unknown_cb += 1
        if row_ok and c in (0, 1):
            cells[f"{r}:{c}"] += 1
    row_spread = max(rows.values()) - min(rows.values())
    cb_spread = abs(cbs["0"] - cbs["1"])
    cell_spread = max(cells.values()) - min(cells.values())
    return {"sessions": len(sessions), "nOrderRows": n_rows, "byOrderRow": rows, "byCb": cbs, "byOrderRowCb": cells,
            "unknownOrderRow": unknown_row, "unknownCb": unknown_cb,
            "rowSpread": row_spread, "cbSpread": cb_spread, "cellSpread": cell_spread,
            "balanced": row_spread <= 1 and cb_spread <= 1 and cell_spread <= 1
                        and unknown_row == 0 and unknown_cb == 0}


def _vec(row: dict, prefix: str) -> tuple[float, float, float] | None:
    v = [_num(row.get(f"{prefix}_{c}")) for c in ("x", "y", "z")]
    return None if any(x is None for x in v) else (v[0], v[1], v[2])


# ---------------------------------------------------------------- 세션 하나

def _variant_at(order: list[str], position) -> str | None:
    p = _int(position)
    return order[p - 1] if p is not None and 1 <= p <= len(order) else None


def load_session(cand: dict, orig_threshold: float) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """→ (세션 행, 형상 행 목록, 경고 목록, 쌍 행 목록). 행 값은 파이썬 값(None = 빈칸)."""
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
    v03 = is_v03(man)
    if not v03 and len(order) != 5:
        warn(f"order 길이 {len(order)} (5가 아님)")
    if v03 and len(order) not in (5, 7, 9):
        warn(f"order 길이 {len(order)} (0.3은 5·7·9)")
    if len(set(order)) != len(order):
        warn("order에 같은 형상이 두 번 이상 있음")
    variants = {str(v.get("id")): v for v in man.get("variants") or [] if isinstance(v, dict)}
    for v in order:
        if v not in variants:
            warn(f"order의 '{v}'가 variants에 없음")
    rating_item = cand.get("item") or rating_item_of(man)
    if v03 and not man.get("ratingItem"):
        warn("0.3 manifest에 ratingItem 없음 — 문항 'unknown'으로 따로 요약하고 Q1에서 뺀다")

    # 평정: 위에서부터 읽고 취소 행은 그 형상의 직전 유효 평정을 지운다
    ratings: dict[str, dict] = {}
    n_cancel: dict[str, int] = {}
    view_ms: dict[str, float] = {}
    other_items: dict[str, int] = {}
    for row in _read_csv(folder / "ratings.csv"):
        var = row.get("variant") or _variant_at(order, row.get("position"))
        if not var:
            continue
        item = row.get("item") or ""
        if v03 and item != rating_item:        # 0.3: 비어 있거나 다른 문항 행은 이 기록의 평정이 아니다
            other_items[item or "(빈칸)"] = other_items.get(item or "(빈칸)", 0) + 1
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
    if other_items:
        warn(f"ratings.csv에 manifest.ratingItem('{rating_item}')과 다른 문항 행 "
             + ", ".join(f"{k} {n}개" for k, n in sorted(other_items.items())) + " — 평정으로 쓰지 않음")
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
    events = _read_csv(folder / "events.csv")
    starts = viewing_starts(events)
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
    extra = [] if v03 else legacy_v03_fields(man)
    if extra:
        excluded = "quarantined"
        warn(f"{man.get('recordVersion')} 기록에 0.3 전용 필드({', '.join(extra)})가 있음 — 문항을 정할 수 없어 "
             "Q1과 문항별 요약에서 격리(quarantined)")
    flags = man.get("flags") if isinstance(man.get("flags"), dict) else {}
    task_text = man.get("taskText") if isinstance(man.get("taskText"), dict) else {}

    kinds = {vid: ("orig" if vid == "orig" else (vv.get("kind") if v03 and vv.get("kind") in ("mismatch", "shift")
                                                 else "mismatch"))
             for vid, vv in variants.items()}
    first_view = shift.first_presentation_utc(events)
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
        "task_text_version": task_text.get("version"), "draft_phrases": _int(task_text.get("draftCount")),
        "rating_item": rating_item, "n_positions": len(order), "condition_set": condition_set_of(man, order),
        "n_order_rows": order_rows_for(man, len(order)), "chose_shift": None if chosen_var is None else
        kinds.get(chosen_var) == "shift", "first_presentation_utc": None if first_view is None else
        first_view.isoformat().replace("+00:00", "Z"), "prereport": None, "n_shift_pairs": None, "q1_eligible": False,
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
        kind = "orig" if is_orig else kinds.get(var, "mismatch")
        rows.append({
            "_rec": rel, "participant": participant, "session": sid, "rating_item": rating_item,
            "position": pos, "variant": var, "kind": kind,
            "attribute": None if is_orig else (v.get("attribute") or var),
            "source": None if is_orig else v.get("source"),
            "rule": None if is_orig else v.get("rule"),
            "said_not_rendered": None if is_orig else bool(vflags.get("saidNotRendered")),
            "forced": None if is_orig else bool(vflags.get("forced")),
            "below_target": None if is_orig else bool(vflags.get("belowTarget")),
            "motion_alters_scale": None if is_orig else bool(vflags.get("motionAltersScale")),
            "magnitude_size_step": _num(mag.get("sizeStep")),
            "magnitude_delta_e00": _num(mag.get("deltaE00")),
            "magnitude_delta_e00_composited": _num(mag.get("deltaE00Composited")),
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

    # 같은 말·다른 값 쌍과 보기 전 보고(0.3). 0.1·0.2에는 shiftPairs가 없어 쌍 행이 없다
    pairs: list[dict] = []
    if v03 and "shiftPairs" in man:
        report, status, pw = shift.load_prereport(folder, man, first_view)
        for msg in pw:
            warn(msg)
        srow["prereport"] = status
        presented = {v for v in order if kinds.get(v) == "shift"}
        pairs, sw = shift.pair_rows(participant, sid, man, {k: r["rating"] for k, r in ratings.items()},
                                    presented, report, status)
        for msg in sw:
            warn(msg)
        srow["n_shift_pairs"] = len(pairs)
        srow["q1_eligible"] = rating_item == Q1_ITEM and any(p["skip_reason"] != "disabled" for p in pairs)
        for pr in pairs:
            pr.update({"included": not excluded, "record_folder": rel, "rating_item": rating_item})
    elif (folder / shift.PREREPORT_FILE).is_file():
        srow["prereport"] = "present"
        warn("prereport.json이 있지만 manifest에 shiftPairs가 없음(0.1·0.2 기록) — 쌍 분석 없음")
    return srow, rows, warns, pairs


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
    """한 문항의 세션들만 넣는다(문항이 다른 세션을 섞지 않는다). 제시 집합 = 원본 + mismatch 변형."""
    keys = {s["record_folder"] for s in sessions}
    chose_shift = {s["record_folder"] for s in sessions if s.get("chose_shift")}
    st = [r for r in stimuli if r["_rec"] in keys and r["kind"] in ("orig", "mismatch")]
    var_rows = [r for r in st if r["kind"] == "mismatch"]
    orig_rows = [r for r in st if r["kind"] == "orig"]

    def b(r):
        if r["chosen"] is None or r["_rec"] in chose_shift:     # shift를 고른 세션은 선택률 분모에서 뺀다
            return None
        return 1.0 if r["chosen"] else 0.0

    rq1 = {"presentationSet": "orig+mismatch",
           "choseShift": {"n": len(chose_shift), "of": len(keys)},
           "orig": {"rating": _est(r["rating"] for r in orig_rows),
                    "choiceRate": _est(b(r) for r in orig_rows)}}
    for a in ATTRIBUTES:
        rows = [r for r in var_rows if r["attribute"] == a]
        rq1[a] = {"ratingDrop": _est(r["rating_drop"] for r in rows),
                  "choiceRate": _est(b(r) for r in rows)}

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

    by_session: dict[str, list[dict]] = {}
    for r in st:
        by_session.setdefault(r["_rec"], []).append(r)
    rq3: dict = {"presentationSet": "orig+mismatch", "diffVsOrig": {}, "ratingCorrelation": {}}
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


def summarize_shift(sessions: list[dict], pairs: list[dict]) -> dict:
    """Q1: 문항 resemblance이고 disabled가 아닌 쌍이 하나라도 있는 세션의 쌍만."""
    q1 = [s for s in sessions if s.get("q1_eligible")]
    keys = {s["record_folder"] for s in q1}
    out = shift.summarize_pairs([p for p in pairs if p["record_folder"] in keys], [s["participant"] for s in q1], LOW_N)
    out["nSessions"] = len(q1)
    out["ratingItem"] = Q1_ITEM
    return out


# ---------------------------------------------------------------- 전체 실행

def read_withdrawn(path: str | Path | None) -> set[str]:
    """철회 목록 파일: 세션 ID를 한 줄에 하나(빈 줄·#로 시작하는 줄은 무시)."""
    if path is None:
        return set()
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")}


def unignored_outputs(out: Path, names: list[str]) -> list[str] | None:
    """출력 폴더가 git 저장소 안이면 무시 규칙에 걸리지 않는 출력 파일 이름 목록. 저장소 밖·git 없음이면 None."""
    import subprocess
    out = out.resolve()
    root = next((p for p in (out, *out.parents) if (p / ".git").exists()), None)
    if root is None:
        return None
    bad = []
    for n in names:
        try:
            r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", str(out / n)],
                               capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode == 1:
            bad.append(n)
    return bad


OUTPUT_FILES = ["stimuli.csv", "sessions.csv", "shift_pairs.csv", "summary.json"]


def analyze(records: str | Path, out_dir: str | Path | None = None,
            orig_threshold: float = DEFAULT_ORIG_THRESHOLD, withdrawn: set[str] | None = None) -> dict:
    root = Path(records)
    if not root.exists():
        raise FileNotFoundError(f"기록 경로가 없습니다: {records}")
    chosen, skipped, warnings, n_withdrawn = discover(root, withdrawn)
    sessions, stimuli, pairs = [], [], []
    for cand in chosen:
        srow, rows, w, pr = load_session(cand, orig_threshold)
        sessions.append(srow)
        stimuli.extend(rows)
        pairs.extend(pr)
        warnings.extend(w)
    included = [s for s in sessions if not s["excluded"]]
    quarantined = [{"record": s["record_folder"], "recordVersion": s["record_version"]}
                   for s in sessions if s["excluded"] == "quarantined"]
    clock = sum(1 for w in warnings if str(w.get("message", "")).startswith(shift.CLOCK_WARNING))
    if out_dir is not None:
        bad = unignored_outputs(Path(out_dir), OUTPUT_FILES)
        if bad:
            msg = (f"출력 폴더가 git 저장소 안이고 {', '.join(bad)}이(가) 무시 규칙에 걸리지 않음 — 참여자 값이 "
                   "커밋될 수 있으니 저장소 밖 폴더를 쓰기")
            warnings.append({"record": None, "message": msg})
            print("경고: " + msg, file=sys.stderr)
    passing = [s for s in included if s["orig_below_threshold"] is False]
    balance = order_balance(included)
    for key, bal in balance["byConditionSet"].items():
        if not bal["balanced"]:
            warnings.append({"record": None, "message": (
                f"순서 불균형(조건 집합 {key}, {bal['nOrderRows']}행): 포함된 세션 {bal['sessions']}개의 orderRow별 수 "
                f"최대−최소 {bal['rowSpread']}, cb 차이 {bal['cbSpread']}, orderRow×cb {2 * bal['nOrderRows']}칸 "
                f"최대−최소 {bal['cellSpread']}, orderRow·cb 모름 {bal['unknownOrderRow']}·{bal['unknownCb']} "
                "— 참여자 번호를 1부터 빠짐없이 차례로 배정했는지 확인")})
    drafted = [s for s in sessions if (s["draft_phrases"] or 0) > 0]
    if drafted:
        warnings.append({"record": None, "message": (
            f"초안 문구: 세션 {len(drafted)}개가 status draft 문구로 수집됨("
            + ", ".join(f"{s['participant']}/{s['session']} {s['draft_phrases']}개" for s in drafted)
            + ") — IRB 확인 전 문구라 본 실험 자료로 쓰기 전에 확인")})
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
            "quarantined": len(quarantined),
            "withdrawn": n_withdrawn,
        },
        "quarantined": quarantined,
        "reportClockWarnings": clock,
        "orderBalance": balance,
        "draftPhraseSessions": len(drafted),
        "ratingItems": sorted({s["rating_item"] for s in included}),
        "summaries": {item: {"all": summarize([s for s in included if s["rating_item"] == item], stimuli),
                             "origAtOrAboveThreshold": summarize([s for s in passing if s["rating_item"] == item],
                                                                 stimuli)}
                      for item in sorted({s["rating_item"] for s in included})},
        "shift": {"all": summarize_shift(included, pairs),
                  "origAtOrAboveThreshold": summarize_shift(passing, pairs)},
        "skipped": skipped,
        "warnings": warnings,
    }
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_csv(out / "stimuli.csv", STIMULI_COLUMNS, stimuli)
        _write_csv(out / "sessions.csv", SESSION_COLUMNS, sessions)
        _write_csv(out / "shift_pairs.csv", shift.PAIR_COLUMNS, pairs)
        (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"sessions": sessions, "stimuli": stimuli, "pairs": pairs, "summary": summary}


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
    for item, summ in summary["summaries"].items():
        rq1 = summ["all"]["rq1"]
        print(f" [문항 {item}] 원본 선택률 {rq1['orig']['choiceRate']['mean']} (n={rq1['orig']['choiceRate']['n']}, "
              f"shift 선택 {rq1['choseShift']['n']})")
        for a in ATTRIBUTES:
            d, c = rq1[a]["ratingDrop"], rq1[a]["choiceRate"]
            low = " lowN" if d["lowN"] else ""
            print(f"  {a:<6} 평정 하락 {d['mean']} (n={d['n']}{low})  선택률 {c['mean']}")
    pm = summary["shift"]["all"]["nearMinusFar"]["primary"]["participantMean"]
    print(f" [Q1 resemblance] 가까운−먼(from_start, 첫 선택) {pm['mean']} 95% CI {pm['ci95']} (참여자 n={pm['n']})")


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.ownership", description="소유감 실험 기록 요약(기술 통계)")
    ap.add_argument("--records", required=True, help="기록 루트(ownership/P###/... 위) 또는 그 아래 아무 폴더")
    ap.add_argument("--out", required=True, help="결과 폴더(stimuli.csv, sessions.csv, summary.json)")
    ap.add_argument("--withdrawn", help="철회한 세션 ID 목록 파일(한 줄에 하나). 그 세션의 기록 폴더는 읽기 전에 뺀다")
    ap.add_argument("--orig-threshold", type=float, default=DEFAULT_ORIG_THRESHOLD,
                    help=f"원본 평정이 이 값 미만이면 origBelowThreshold(기본 {DEFAULT_ORIG_THRESHOLD:g})")
    args = ap.parse_args(argv)
    if not Path(args.records).exists():
        ap.error(f"--records 경로가 없습니다: {args.records}")
    res = analyze(args.records, args.out, args.orig_threshold, read_withdrawn(args.withdrawn))
    _print_summary(res["summary"])
    print(f"결과: {Path(args.out) / 'summary.json'}")


if __name__ == "__main__":
    main()
