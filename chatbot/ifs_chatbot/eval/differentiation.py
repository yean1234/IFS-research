"""구별 프로파일 계산기 — 자기보고·행동·언어 세 방법을 성분별로 따로 내고, 방법 사이의 수렴을 순위 상관과 사례 목록으로 본다.

정의: docs/rq-v4-differentiation-measure.md 3장(3.1 자기보고, 3.2 행동 결합 지표, 3.3 언어 지표, 3.4 수렴).
LLM 없음, 표준 라이브러리 + Kiwi(언어 표지), 결정적. **한 점수로 합치지 않는다. 유의성 판정을 내지 않는다.**

  python -m ifs_chatbot.eval.differentiation --records <기록 루트> [--records <다른 루트> …] \
      [--utterances utter.jsonl] --out <폴더> [--facing-deg 15] [--facing-threshold 0.5] [--start-distance 1.5] \
      [--distance-split fixed|median] [--facing-split fixed|median] [--window-s 30]
  python -m ifs_chatbot.eval.differentiation --sessions placement_sessions.csv [...]   # 세션 표만 있을 때
  → differentiation_profile.csv(세션 1행), differentiation_convergence.csv(변수 쌍 1행), differentiation_summary.json,
    (발화가 있으면) language_markers.csv(발화 1행)

입력
- 기록 폴더(--records): placement 분석기(ifs_chatbot.eval.placement.analyze)로 세션 표를 만들고, 각 세션의
  headpose.csv에서 G_early·G_late를, manifest.json에서 시작 거리(space.startDistanceM)와 flags.synthetic을 읽는다.
- 세션 표(--sessions): placement_sessions.csv. 머리 표본이 없으므로 G_late 대신 조건 단계 전체의 head_facing_ratio를 쓰고
  flags에 facing_from_whole_condition을 단다. 시작 거리는 --start-distance(기본 1.5 m, 문서 3.2의 잠정값).
- 발화(--utterances, jsonl): {"participant"(선택), "session_id", "when": "pre"|"post", "prompt": "L-A"|"L-B", "text"}.
  participant가 없으면 session_id가 세션 표에서 하나뿐일 때만 맞춘다.

자기보고(문서 3.1, 문항 키는 profile_items.PROFILE_ITEMS)
- 문항마다 {item}_pre, {item}_post, {item}_change = post − pre(원 척도). 문항이 없으면 빈칸.
  S5·S6은 옛 문구 파일 키(want_to_know·withdraw_attention)도 받는다(sr_aliases 열에 기록).
- 정규화: norm(x) = (x − 척도 최소) / (척도 최대 − 척도 최소) → 0–1. M1p·M2·M3은 0–10, P1·P2·S5·S6은 1–7.
- 성분 묶음: 알아차림 awareness = norm(M1p) / 탈동일시 disid = (norm(M2) + norm(P1)) / 2 — **둘 다 있을 때만**(하나만 있으면
  빈칸, flags에 disid_partial) / 반응성 reactivity = norm(M3) / 태도는 P2·S5·S6을 합치지 않고 따로 둔다.
  ambivalent_{pre,post} = S5 ≥ 5 그리고 S6 ≥ 5(1–7 척도의 "높음" = 중간 4보다 큼; 둘 중 하나라도 없으면 빈칸).
  성분 변화 = post − pre(정규화 척도).

행동(문서 3.2)
- delta_d_m = final_distance_m − 시작 거리. G(g_early, g_late) = 처음/마지막 window_s초 머리 표본 중 angle_deg ≤ facing_deg 비율
  (조건 단계, 시각은 그 단계 첫·마지막 표본 기준). g_shift = g_late − g_early. 눈 시선이 아니라 머리 방향이다.
- 2×2(직접 배치 place, 요약 포함 세션만): 거리 축 fixed = delta_d의 부호(0이면 미정), median = 표본 final_distance_m 중앙값보다 크면 먼
  쪽(같으면 가까운 쪽). 방향 축 fixed = g_late > facing_threshold(기본 0.5), median = 표본 g_late 중앙값보다 크면 봄.
  칸: NL near_facing, FL far_facing, FA far_not_facing, NA near_not_facing. 보기만 조건은 2×2를 만들지 않는다.
- 멈춤 거리 sd_asym_m = 접근 평균 − 후퇴 평균. regrab_count = grab_count − 1(직접 배치만, 첫 잡기 제외).

언어(문서 3.3, ifs_chatbot.eval.language_markers): L-A 발화의 K1–K7 개수 pre/post/change(post − pre), 절 수.
L-B 발화의 기존 사전 감정어(부정된 것은 ~ 표시)와 분류 없는 용언 원형 목록.

수렴(문서 3.4): 세션 수준 변수들 사이의 Spearman 순위 상관(쌍별 완전 사례, n < 3이거나 분산 0이면 null)과,
사전에 정한 규칙에 맞는 사례 목록(불일치·읽기 사례). 사례의 "읽는 법"은 문서 3.4 표의 후보 읽기이고 확정 해석이 아니다.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

from . import language_markers as lm
from . import placement
from .ownership import _num, _read_csv, _read_json, _r, _truthy, _write_csv, spearman
from .profile_items import ITEM_ALIASES, ITEM_SCALES, PROFILE_ITEMS

VERSION = "differentiation-profile/0.1"
WHENS = ("pre", "post")
DEFAULT_START_DISTANCE_M = 1.5     # 문서 3.2 `ΔD = D_place − 1.5`(잠정)
DEFAULT_FACING_THRESHOLD = 0.5     # 문서 3.2 G_late 기준 예시
DEFAULT_WINDOW_S = 30.0            # 문서 3.2 처음·마지막 30초
HIGH_ON_7 = 5.0                    # 1–7 척도 "높음"(중간 4 초과)
HIGH_NORM = (HIGH_ON_7 - 1.0) / 6.0   # 정규화 척도의 "높음" = 2/3(0–10 척도에서는 약 6.67 이상)
SYNTHETIC_NOTE = "합성 자료: 파이프라인 검증용이며 효과의 근거가 아님"

QUADRANTS = {"NL": "near_facing", "FL": "far_facing", "FA": "far_not_facing", "NA": "near_not_facing"}

# 문서 3.2 표 그대로(주장할 수 있는 것 / 없는 것)
CLAIMS = {
    "NL": {"can": "물체 가까이에서 주의를 둠",
           "cannot": "'구별되지 않음(얽힘)'인지 '다가가 살핌'인지 행동만으로는 모름"},
    "FL": {"can": "거리를 두고도 머리가 물체를 향함",
           "cannot": "'거리 둔 관찰'이라고 단정할 수 없음. far_facing은 차분한 관찰이라고 해석할 수 없음 — VR 거미 공포 연구에서 "
                     "공포증 집단은 최소 거리를 더 멀리 두면서도 더 자주 보고 몸을 더 향했음(Binder 외 2022). 경계 감시와 같은 행동 모양"},
    "FA": {"can": "거리도 두고 주의도 거둠",
           "cannot": "회피와 가장 잘 맞지만, 과제를 끝냈다고 여겨 둘러보는 행동일 수도 있음"},
    "NA": {"can": "가까이 두고 주의는 다른 데 둠",
           "cannot": "해석이 가장 모호함(무관심, 가까운 것을 보기 부담스러움, 둘러보기)"},
    "sd_mean_m": {"can": "사후에 '이것'이 있기에 알맞다고 고른 거리. 두 조건이 같은 방식으로 측정됨",
                  "cannot": "사전값이 없으므로 변화량이 아님. 물체·심상 자극에서 검증된 적이 없음"},
    "sd_asym_m": {"can": "방향에 따라 멈춘 거리가 다른지",
                  "cannot": "방어 경계의 비대칭이라고 해석할 근거가 약함(Lebert 외 2024; 한계법의 반응 편향일 수 있음)"},
    "regrab_count": {"can": "자리 조정에 들인 행동량", "cannot": "탐색인지 안절부절못함인지 구별 못 함"},
    "g_shift": {"can": "시간에 따라 머리 방향이 물체로 모이는지 흩어지는지",
                "cannot": "머리 방향만으로 주의를 확정할 수 없음. 시야각이 넓어 머리를 돌리지 않고 볼 수 있음"},
    "view_condition": {"can": "g·g_shift·머리–물체 거리만 두 조건에서 비교",
                       "cannot": "보기만 조건은 거리를 참여자가 정하지 않으므로 2×2를 만들지 않음. 조건 간 놓은 거리 비교는 조작의 결과라 결과 변수가 아님"},
}

# 수렴 변수: 이름 → (방법, 성분, 설명). 성분 이름은 문서 1·3.4절. "(해석)"은 문서가 표지와 성분을 연결한 해석.
CONVERGENCE_VARS = {
    "awareness_change": ("self_report", "awareness", "norm(M1p) post − pre"),
    "disid_change": ("self_report", "disidentification", "(norm(M2)+norm(P1))/2 post − pre"),
    "reactivity_change": ("self_report", "reactivity", "norm(M3) post − pre"),
    "P2_change": ("self_report", "attitude", "P2 post − pre (1–7)"),
    "S5_change": ("self_report", "attitude_approach", "S5 post − pre"),
    "S6_change": ("self_report", "attitude_withdraw", "S6 post − pre"),
    "delta_d_m": ("behavior", "distance(성분 미정)", "놓은 거리 − 시작 거리(직접 배치만)"),
    "g_late": ("behavior", "attention_orientation(해석)", "마지막 window 머리 향함 비율"),
    "g_shift": ("behavior", "attention_orientation(해석)", "g_late − g_early"),
    "sd_asym_m": ("behavior", "distance(성분 미정)", "멈춤 거리 접근 − 후퇴(사후만)"),
    "regrab_count": ("behavior", "adjustment(성분 미정)", "다시 잡은 횟수(직접 배치만)"),
    "la_K1_change": ("language", "disidentification(해석: 자기 거리두기)", "L-A K1 post − pre"),
    "la_K2_change": ("language", "disidentification", "L-A K2 동일시 틀 post − pre"),
    "la_K3_change": ("language", "disidentification", "L-A K3 존재 틀 post − pre"),
    "la_K4_change": ("language", "object_reference(해석)", "L-A K4 post − pre"),
    "la_K6_change": ("language", "temporal_distance(해석)", "L-A K6 post − pre"),
    "la_K7_change": ("language", "unspecified", "L-A K7 post − pre"),
}

# 사전에 정한 사례 규칙(문서 3.4 표 + 과제 지시의 예). kind: discordance(방법끼리 어긋남) / reading(읽기 후보)
CASE_RULES = [
    {"id": "disid_up_but_FA", "kind": "discordance",
     "rule": "disid_change > 0 그리고 quadrant = FA",
     "reading": "자기보고 탈동일시는 올랐는데 행동은 거리도 두고 주의도 거둔 모양(회피와 가장 잘 맞는 칸). 사례 메모로 남김"},
    {"id": "P1_high_with_K2", "kind": "discordance",
     "rule": "P1_post ≥ 5 그리고 L-A 사후 K2 ≥ 1",
     "reading": "자기보고가 사회적 바람직성(IFS식 정답)에 끌렸을 가능성, 또는 말버릇. 사례 메모로 남김"},
    {"id": "disid_up_but_K2_up", "kind": "discordance",
     "rule": "disid_change > 0 그리고 la_K2_change > 0",
     "reading": "자기보고 탈동일시와 언어 동일시 틀이 반대로 움직임. 사례 메모로 남김"},
    {"id": "FL_with_S6_high", "kind": "reading",
     "rule": "quadrant = FL 그리고 S6_post ≥ 5 (L-B 감정어는 참고로 함께 적음)",
     "reading": "경계 감시 쪽 후보. 구별이 아니라 섞임 쪽(문서 3.4)"},
    {"id": "FL_with_S5_P2_high", "kind": "reading",
     "rule": "quadrant = FL 그리고 S5_post ≥ 5 그리고 P2_post ≥ 5",
     "reading": "거리 둔 관찰 쪽 후보(문서 3.4: 프로파일이 가장 잘 맞는 경우). 단정하지 않음"},
    {"id": "NL_differentiated", "kind": "reading",
     "rule": "quadrant = NL 그리고 P1_post ≥ 5 그리고 P2_post ≥ 5",
     "reading": "가까이 두고도 구별됨 — 거리 = 구별이 아니라는 우려 (1)을 보여 주는 사례 후보"},
]
NOT_COMPUTABLE_RULES = [
    {"id": "sr_flat_behavior_changed",
     "rule": "자기보고는 변화가 없고 행동만 변함(문서 3.4)",
     "why": "행동 지표는 조건 단계 한 번만 기록되어 사전–사후 변화가 없음(멈춤 거리도 사후만)"},
]

PROFILE_ID = ["participant", "session_id", "source", "record_folder", "condition", "control_mode", "included",
              "synthetic", "auto_mode"]
SR_COLS = [f"{i}_{w}" for i in PROFILE_ITEMS for w in ("pre", "post", "change")] + ["sr_aliases"] + \
          [f"{c}_{w}" for c in ("awareness", "disid", "reactivity") for w in ("pre", "post", "change")] + \
          ["ambivalent_pre", "ambivalent_post"]
BEH_COLS = ["start_distance_m", "final_distance_m", "delta_d_m", "g_whole", "g_early", "g_late", "g_shift",
            "facing_source", "head_obj_distance_mean_m", "quadrant", "quadrant_name",
            "sd_approach_m", "sd_recede_m", "sd_asym_m", "sd_mean_m", "grab_count", "regrab_count", "first_grab_ms"]
LANG_COLS = [f"la_{k}_{w}" for k in lm.MARKERS for w in ("pre", "post", "change")] + \
            ["la_nclauses_pre", "la_nclauses_post"] + \
            ["lb_emotion_pre", "lb_emotion_post", "lb_emotion_n_pre", "lb_emotion_n_post", "lb_emotion_n_change",
             "lb_predicates_pre", "lb_predicates_post"]
PROFILE_COLUMNS = PROFILE_ID + SR_COLS + BEH_COLS + LANG_COLS + ["flags"]
CONV_COLUMNS = ["var_a", "method_a", "component_a", "var_b", "method_b", "component_b", "same_component",
                "same_method", "n", "rho"]


# ---------------------------------------------------------------- 도우미

def norm_item(item: str, x: float | None) -> float | None:
    if x is None:
        return None
    lo, hi = ITEM_SCALES[item]
    return (x - lo) / (hi - lo)


def _sub(a, b):
    return None if a is None or b is None else a - b


def _pkey(v) -> str | None:
    """참여자 표기를 P### 로. 숫자·"P7"·"7" 모두 받음."""
    if v is None or v == "":
        return None
    s = str(v).strip()
    if s[:1] in ("P", "p"):
        s = s[1:]
    try:
        return f"P{int(float(s)):03d}"
    except ValueError:
        return str(v)


def _median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def head_windows(headpose: Path, facing_deg: float, window_s: float) -> dict:
    """조건 단계 머리 표본 → g_early, g_late, 겹침 여부. 표본이 없으면 값 None."""
    samples = []
    for row in _read_csv(headpose):
        if row.get("phase") != "condition":
            continue
        t, a = _num(row.get("time_ms")), _num(row.get("angle_deg"))
        if t is not None and a is not None:
            samples.append((t, a))
    if not samples:
        return {"g_early": None, "g_late": None, "overlap": False, "n": 0}
    samples.sort()
    t0, t1, w = samples[0][0], samples[-1][0], window_s * 1000.0
    early = [a for t, a in samples if t <= t0 + w]
    late = [a for t, a in samples if t >= t1 - w]

    def g(xs):
        return sum(1 for a in xs if a <= facing_deg) / len(xs) if xs else None

    return {"g_early": g(early), "g_late": g(late), "overlap": (t1 - t0) < 2 * w, "n": len(samples)}


# ---------------------------------------------------------------- 세션 불러오기

def sessions_from_records(roots: list[str | Path], facing_deg: float, window_s: float) -> tuple[list[dict], list[str]]:
    out, warnings = [], []
    for ri, root in enumerate(roots):
        root = Path(root)
        res = placement.analyze(root, None, facing_deg)
        label = f"{ri}:{root.parent.name}/{root.name}"
        for s in res["sessions"]:
            folder = root / s["record_folder"]
            man = _read_json(folder / "manifest.json") or {}
            hw = head_windows(folder / "headpose.csv", facing_deg, window_s)
            space = man.get("space") if isinstance(man.get("space"), dict) else {}
            flags = man.get("flags") if isinstance(man.get("flags"), dict) else {}
            out.append({**s, "_source": label, "_g": hw,
                        "_start": _num(space.get("startDistanceM")),
                        "_synthetic": flags.get("synthetic") is True})
        warnings += [f"[{label}] {w}" for w in res["summary"]["warnings"]]
    return out, warnings


def sessions_from_table(path: str | Path) -> list[dict]:
    rows = _read_csv(Path(path))
    if not rows:
        raise FileNotFoundError(f"세션 표가 비었거나 없습니다: {path}")
    out = []
    for r in rows:
        s = dict(r)
        for k in ("completed", "condition_complete", "auto_mode"):
            s[k] = _truthy(r.get(k))
        s["_source"] = Path(path).name
        s["_g"] = None
        s["_start"] = None
        s["_synthetic"] = None
        out.append(s)
    return out


# ---------------------------------------------------------------- 발화

def load_utterances(path: str | Path | None, sessions: list[dict]) -> tuple[dict, list[dict], list[str]]:
    """→ ({(participant, session_id): {(when, prompt): [분석 결과…]}}, 발화별 평평한 행, 경고)."""
    if not path:
        return {}, [], []
    items = lm.read_jsonl(path)
    keys = {(s["participant"], s["session_id"]) for s in sessions}
    by_sid: dict[str, list] = {}
    for p, sid in keys:
        by_sid.setdefault(sid, []).append((p, sid))
    out: dict = {}
    flat, warnings = [], []
    unmatched = 0
    for it in items:
        sid, pk = it.get("session_id"), _pkey(it.get("participant"))
        when, prompt = it.get("when"), it.get("prompt")
        res = lm.analyze_text(it.get("text"))
        flat.append(lm.flat_row({**it, "participant": pk}, res))
        if pk is not None:
            key = (pk, sid) if (pk, sid) in keys else None
        else:
            cands = by_sid.get(sid, [])
            key = cands[0] if len(cands) == 1 else None
        if key is None or when not in WHENS or prompt not in ("L-A", "L-B"):
            unmatched += 1
            continue
        out.setdefault(key, {}).setdefault((when, prompt), []).append(res)
    if unmatched:
        warnings.append(f"세션에 맞추지 못했거나 when·prompt가 계약 밖인 발화 {unmatched}개(language_markers.csv에는 있음)")
    return out, flat, warnings


# ---------------------------------------------------------------- 프로파일 한 행

def self_report(s: dict, row: dict, flags: list[str]) -> None:
    aliases = []
    vals: dict[tuple[str, str], float | None] = {}
    for item in PROFILE_ITEMS:
        for w in WHENS:
            v = None
            for key in ITEM_ALIASES[item]:
                v = _num(s.get(f"rating_{key}_{w}"))
                if v is not None:
                    if key != item and f"{item}={key}" not in aliases:
                        aliases.append(f"{item}={key}")
                    break
            vals[(item, w)] = v
            row[f"{item}_{w}"] = v
        row[f"{item}_change"] = _sub(vals[(item, "post")], vals[(item, "pre")])
    row["sr_aliases"] = ";".join(aliases)
    for w in WHENS:
        row[f"awareness_{w}"] = _r(norm_item("M1p", vals[("M1p", w)]))
        row[f"reactivity_{w}"] = _r(norm_item("M3", vals[("M3", w)]))
        m2, p1 = norm_item("M2", vals[("M2", w)]), norm_item("P1", vals[("P1", w)])
        row[f"disid_{w}"] = _r((m2 + p1) / 2) if m2 is not None and p1 is not None else None
        if (m2 is None) != (p1 is None) and "disid_partial" not in flags:
            flags.append("disid_partial")
        s5, s6 = vals[("S5", w)], vals[("S6", w)]
        row[f"ambivalent_{w}"] = None if s5 is None or s6 is None else (s5 >= HIGH_ON_7 and s6 >= HIGH_ON_7)
    for c in ("awareness", "disid", "reactivity"):
        row[f"{c}_change"] = _r(_sub(row[f"{c}_post"], row[f"{c}_pre"]))


def behavior(s: dict, row: dict, flags: list[str], start_default: float) -> None:
    place = s.get("condition") == "place"
    start = s.get("_start")
    if start is None:
        start = start_default
        flags.append("start_distance_default")
    fd = _num(s.get("final_distance_m"))
    row["start_distance_m"] = start
    row["final_distance_m"] = fd
    row["delta_d_m"] = _r(fd - start) if place and fd is not None else None
    row["g_whole"] = _num(s.get("head_facing_ratio"))
    g = s.get("_g")
    if g is not None and g["n"]:
        row["g_early"], row["g_late"] = _r(g["g_early"]), _r(g["g_late"])
        row["facing_source"] = "late_window"
        if g["overlap"]:
            flags.append("g_windows_overlap")
    else:
        row["g_early"] = None
        row["g_late"] = row["g_whole"]
        row["facing_source"] = "whole_condition" if row["g_whole"] is not None else None
        if row["g_whole"] is not None:
            flags.append("facing_from_whole_condition")
    row["g_shift"] = _r(_sub(row["g_late"], row["g_early"]))
    row["head_obj_distance_mean_m"] = _num(s.get("head_obj_distance_mean_m"))
    a, r = _num(s.get("stop_approach_mean_m")), _num(s.get("stop_recede_mean_m"))
    row["sd_approach_m"], row["sd_recede_m"] = a, r
    row["sd_asym_m"] = _r(_sub(a, r))
    row["sd_mean_m"] = _num(s.get("stop_mean_m"))
    gc = _num(s.get("grab_count"))
    row["grab_count"] = int(gc) if gc is not None else None
    row["regrab_count"] = (max(int(gc) - 1, 0) if gc is not None else None) if place else None
    row["first_grab_ms"] = _num(s.get("first_grab_ms")) if place else None


def language(utts: dict, row: dict, flags: list[str]) -> None:
    for w in WHENS:
        la = utts.get((w, "L-A"), [])
        lb = utts.get((w, "L-B"), [])
        if len(la) > 1 or len(lb) > 1:
            flags.append(f"multiple_utterances:{w}")
        for k in lm.MARKERS:
            row[f"la_{k}_{w}"] = sum(r["counts"][k] for r in la) if la else None
        row[f"la_nclauses_{w}"] = sum(r["n_clauses"] for r in la) if la else None
        if lb:
            hits = [h for r in lb for h in r["attitude"]["emotion_hits"]]
            row[f"lb_emotion_{w}"] = ";".join(("~" if h["negated"] else "") + h["lemma"] for h in hits)
            row[f"lb_emotion_n_{w}"] = sum(1 for h in hits if not h["negated"])
            row[f"lb_predicates_{w}"] = ";".join(("~" if p["negated"] else "") + p["lemma"]
                                                 for r in lb for p in r["attitude"]["predicate_lemmas"])
        else:
            row[f"lb_emotion_{w}"] = row[f"lb_emotion_n_{w}"] = row[f"lb_predicates_{w}"] = None
    for k in lm.MARKERS:
        row[f"la_{k}_change"] = _sub(row[f"la_{k}_post"], row[f"la_{k}_pre"])
    row["lb_emotion_n_change"] = _sub(row["lb_emotion_n_post"], row["lb_emotion_n_pre"])


def assign_quadrants(rows: list[dict], facing_threshold: float, distance_split: str, facing_split: str) -> dict:
    """요약 포함 place 세션에 2×2 칸을 단다. → 사용한 기준값."""
    eligible = [r for r in rows if r["condition"] == "place" and r["included"]]
    d_med = _median(r["final_distance_m"] for r in eligible)
    g_med = _median(r["g_late"] for r in eligible)
    for r in rows:
        r["quadrant"] = r["quadrant_name"] = None
    for r in eligible:
        if distance_split == "median":
            far = None if r["final_distance_m"] is None or d_med is None else r["final_distance_m"] > d_med
        else:
            dd = r["delta_d_m"]
            far = None if dd is None or dd == 0 else dd > 0
        if facing_split == "median":
            facing = None if r["g_late"] is None or g_med is None else r["g_late"] > g_med
        else:
            facing = None if r["g_late"] is None else r["g_late"] > facing_threshold
        if far is None or facing is None:
            r["flags"].append("quadrant_undetermined")
            continue
        q = ("F" if far else "N") + ("L" if facing else "A")
        r["quadrant"], r["quadrant_name"] = q, QUADRANTS[q]
    return {"distanceSplit": distance_split, "facingSplit": facing_split,
            "distanceMedianM": _r(d_med) if distance_split == "median" else None,
            "facingThreshold": _r(g_med) if facing_split == "median" else facing_threshold,
            "nEligible": len(eligible)}


# ---------------------------------------------------------------- 수렴

def convergence(rows: list[dict]) -> list[dict]:
    names = list(CONVERGENCE_VARS)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pairs = [(r[a], r[b]) for r in rows if r.get(a) is not None and r.get(b) is not None]
            rho = spearman([p[0] for p in pairs], [p[1] for p in pairs])
            ma, ca, _ = CONVERGENCE_VARS[a]
            mb, cb, _ = CONVERGENCE_VARS[b]
            out.append({"var_a": a, "method_a": ma, "component_a": ca, "var_b": b, "method_b": mb, "component_b": cb,
                        "same_component": ca == cb, "same_method": ma == mb, "n": len(pairs), "rho": _r(rho, 3)})
    return out


def _ge(v, t):
    return v is not None and v >= t


def find_cases(rows: list[dict]) -> list[dict]:
    cases = []
    for r in rows:
        if not r["included"]:
            continue
        hits = {
            "disid_up_but_FA": (r["disid_change"] or 0) > 0 and r["quadrant"] == "FA",
            "P1_high_with_K2": _ge(r["P1_post"], HIGH_ON_7) and _ge(r["la_K2_post"], 1),
            "disid_up_but_K2_up": (r["disid_change"] or 0) > 0 and (r["la_K2_change"] or 0) > 0,
            "FL_with_S6_high": r["quadrant"] == "FL" and _ge(r["S6_post"], HIGH_ON_7),
            "FL_with_S5_P2_high": r["quadrant"] == "FL" and _ge(r["S5_post"], HIGH_ON_7) and _ge(r["P2_post"], HIGH_ON_7),
            "NL_differentiated": r["quadrant"] == "NL" and _ge(r["P1_post"], HIGH_ON_7) and _ge(r["P2_post"], HIGH_ON_7),
        }
        for rule in CASE_RULES:
            if hits[rule["id"]]:
                cases.append({"participant": r["participant"], "session_id": r["session_id"], "rule": rule["id"],
                              "kind": rule["kind"], "quadrant": r["quadrant"],
                              "values": {k: r.get(k) for k in ("disid_change", "P1_post", "P2_post", "S5_post",
                                                               "S6_post", "la_K2_pre", "la_K2_post", "lb_emotion_post")}})
    return cases


# ---------------------------------------------------------------- 요약

def _desc_by(rows: list[dict], cols: list[str], key) -> dict:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(str(key(r)), []).append(r)
    return {g: {"n": len(rs), **{c: placement.describe(r.get(c) for r in rs) for c in cols}}
            for g, rs in sorted(groups.items())}


def summarize(rows: list[dict], quad_params: dict, conv: list[dict], cases: list[dict], params: dict,
              warnings: list[str], n_utterances: int) -> dict:
    inc = [r for r in rows if r["included"]]
    place = [r for r in inc if r["condition"] == "place"]
    synthetic = any(r["synthetic"] for r in rows)
    qcount = {q: sum(1 for r in place if r["quadrant"] == q) for q in QUADRANTS}
    qcount["undetermined"] = sum(1 for r in place if r["quadrant"] is None)
    sr_cols = [f"{i}_{w}" for i in PROFILE_ITEMS for w in ("pre", "post", "change")] + \
              [f"{c}_{w}" for c in ("awareness", "disid", "reactivity") for w in ("pre", "post", "change")]
    beh_cols = ["delta_d_m", "g_whole", "g_early", "g_late", "g_shift", "head_obj_distance_mean_m",
                "sd_asym_m", "sd_mean_m", "regrab_count"]
    la_cols = [f"la_{k}_{w}" for k in lm.MARKERS for w in ("pre", "post", "change")] + \
              ["la_nclauses_pre", "la_nclauses_post", "lb_emotion_n_pre", "lb_emotion_n_post"]
    same_comp = [c for c in conv if c["same_component"] and not c["same_method"]]
    return {
        "version": VERSION,
        "tool": "ifs_chatbot.eval.differentiation",
        "descriptiveOnly": True,
        "syntheticData": synthetic,
        "syntheticNote": SYNTHETIC_NOTE if synthetic else None,
        "note": "세 방법(자기보고·행동·언어)을 성분별로 따로 낸다. 한 점수로 합치지 않는다. 유의성 판정을 내지 않는다. "
                "2×2 칸 이름은 관찰 서술이며 심리 상태의 판정이 아니다. 사례 규칙의 '읽는 법'은 후보 읽기다. "
                "언어 표지는 규칙 개수이고 짧은 발화에서 불안정하다(docs/rq-v4-differentiation-measure.md 3.3 한계).",
        "parameters": params,
        "itemScales": {k: list(v) for k, v in ITEM_SCALES.items()},
        "normalization": "norm(x) = (x − 척도 최소) / (척도 최대 − 척도 최소). disid = (norm(M2) + norm(P1)) / 2, 둘 다 있을 때만",
        "highThreshold": {"onScale1to7": HIGH_ON_7, "normalized": _r(HIGH_NORM)},
        "records": {"sessions": len(rows), "included": len(inc), "place": len(place),
                    "view": sum(1 for r in inc if r["condition"] == "view"),
                    "synthetic": sum(1 for r in rows if r["synthetic"]),
                    "utterances": n_utterances},
        "selfReport": {"byCondition": _desc_by(inc, sr_cols, lambda r: r["condition"]),
                       "ambivalentPost": sum(1 for r in inc if r["ambivalent_post"]),
                       "ambivalentPre": sum(1 for r in inc if r["ambivalent_pre"])},
        "behavior": {"quadrantRule": quad_params, "quadrantCounts": qcount,
                     "byCondition": _desc_by(inc, beh_cols, lambda r: r["condition"]),
                     "byQuadrant": _desc_by(place, ["disid_change", "P2_post", "S5_post", "S6_post", "la_K2_change",
                                                    "la_K3_change", "g_late", "delta_d_m"],
                                            lambda r: r["quadrant"] or "undetermined"),
                     "claims": CLAIMS},
        "language": {"byConditionWhen": _desc_by(inc, la_cols, lambda r: r["condition"]),
                     "analyzer": lm.analyzer_info(), "knownLimitations": lm.KNOWN_LIMITATIONS},
        "convergence": {"method": "Spearman 순위 상관(동순위 평균 순위), 쌍별 완전 사례, n < 3 또는 분산 0이면 null. 요약 포함 세션만",
                        "note": "유의성 판정 없음. 같은 성분·다른 방법 쌍의 상관이 다른 성분 쌍보다 높아야 성분 구분이 쓸모 있다고 "
                                "볼 수 있다(다특성–다방법 발상, 문서 3.4). 표본이 작으면 상관 추정이 매우 불안정하다(n=20에서도 r≈.6 미만은 구별 어려움).",
                        "variables": {k: {"method": m, "component": c, "definition": d}
                                      for k, (m, c, d) in CONVERGENCE_VARS.items()},
                        "sameComponentCrossMethod": same_comp,
                        "nPairs": len(conv)},
        "cases": {"rules": CASE_RULES, "notComputable": NOT_COMPUTABLE_RULES,
                  "counts": {rule["id"]: sum(1 for c in cases if c["rule"] == rule["id"]) for rule in CASE_RULES},
                  "list": cases},
        "warnings": warnings,
    }


# ---------------------------------------------------------------- 전체 실행

def analyze(records: list[str | Path] | None = None, sessions_csv: str | Path | None = None,
            utterances: str | Path | None = None, out_dir: str | Path | None = None,
            facing_deg: float = placement.DEFAULT_FACING_DEG, facing_threshold: float = DEFAULT_FACING_THRESHOLD,
            start_distance: float = DEFAULT_START_DISTANCE_M, distance_split: str = "fixed",
            facing_split: str = "fixed", window_s: float = DEFAULT_WINDOW_S) -> dict:
    if not records and not sessions_csv:
        raise ValueError("records 또는 sessions_csv 중 하나가 필요합니다")
    warnings: list[str] = []
    if records:
        sessions, w = sessions_from_records(list(records), facing_deg, window_s)
        warnings += w
    else:
        sessions = sessions_from_table(sessions_csv)
        warnings.append("세션 표만 입력: G_late 대신 조건 단계 전체 head_facing_ratio를 씀(facing_from_whole_condition)")
    keys: dict[tuple, int] = {}
    for s in sessions:
        keys[(s["participant"], s["session_id"])] = keys.get((s["participant"], s["session_id"]), 0) + 1
    dup = sorted(k for k, n in keys.items() if n > 1)
    if dup:
        warnings.append("같은 (participant, session_id)가 여러 입력에 있음: " + ", ".join(f"{p}/{s}" for p, s in dup))
    utt, flat, w = load_utterances(utterances, sessions)
    warnings += w

    rows = []
    for s in sessions:
        flags: list[str] = []
        key = (s["participant"], s["session_id"])
        row = {"participant": s["participant"], "session_id": s["session_id"], "source": s["_source"],
               "record_folder": s.get("record_folder"), "condition": s.get("condition"),
               "control_mode": s.get("control_mode"),
               "included": bool(s.get("completed")) and bool(s.get("condition_complete")),
               "synthetic": s.get("_synthetic"), "auto_mode": s.get("auto_mode")}
        self_report(s, row, flags)
        behavior(s, row, flags, start_distance)
        language({} if key in dup else utt.get(key, {}), row, flags)
        row["flags"] = flags
        rows.append(row)
    quad = assign_quadrants(rows, facing_threshold, distance_split, facing_split)
    inc = [r for r in rows if r["included"]]
    conv = convergence(inc)
    cases = find_cases(rows)
    params = {"facingDeg": facing_deg, "facingThreshold": facing_threshold, "startDistanceDefaultM": start_distance,
              "distanceSplit": distance_split, "facingSplit": facing_split, "windowS": window_s,
              "input": "records" if records else "sessions_csv"}
    if sum(1 for r in inc if r["condition"] == "place") < 3:
        warnings.append("요약 포함 place 세션이 3개 미만 — median 분할과 상관은 의미가 거의 없음")
    summary = summarize(rows, quad, conv, cases, params, warnings, len(flat))
    for r in rows:
        r["flags"] = ";".join(r["flags"])
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_csv(out / "differentiation_profile.csv", PROFILE_COLUMNS, rows)
        _write_csv(out / "differentiation_convergence.csv", CONV_COLUMNS, conv)
        if flat:
            _write_csv(out / "language_markers.csv", lm.CSV_COLUMNS, flat)
        (out / "differentiation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                                          encoding="utf-8")
    return {"rows": rows, "convergence": conv, "cases": cases, "summary": summary, "utterances": flat}


def _print_summary(summary: dict) -> None:
    rec = summary["records"]
    if summary["syntheticData"]:
        print(f"[{SYNTHETIC_NOTE}]")
    print(f"세션 {rec['sessions']}개(요약 포함 {rec['included']}: place {rec['place']}, view {rec['view']}), "
          f"발화 {rec['utterances']}개 · 경고 {len(summary['warnings'])}")
    print("  2×2(place): " + ", ".join(f"{k} {v}" for k, v in summary["behavior"]["quadrantCounts"].items()))
    hit = ", ".join(f"{k} {v}" for k, v in summary["cases"]["counts"].items() if v)
    print("  사례: " + (hit or "없음"))


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.differentiation",
                                 description="구별 프로파일(자기보고·행동·언어, 합산 없음)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--records", action="append", help="placement 기록 루트(여러 번 줄 수 있음)")
    src.add_argument("--sessions", help="placement_sessions.csv(머리 표본 없이 계산)")
    ap.add_argument("--utterances", help="발화 jsonl: participant(선택)·session_id·when·prompt·text")
    ap.add_argument("--out", required=True)
    ap.add_argument("--facing-deg", type=float, default=placement.DEFAULT_FACING_DEG)
    ap.add_argument("--facing-threshold", type=float, default=DEFAULT_FACING_THRESHOLD)
    ap.add_argument("--start-distance", type=float, default=DEFAULT_START_DISTANCE_M,
                    help="manifest에 시작 거리가 없을 때 쓰는 값(m)")
    ap.add_argument("--distance-split", choices=("fixed", "median"), default="fixed")
    ap.add_argument("--facing-split", choices=("fixed", "median"), default="fixed")
    ap.add_argument("--window-s", type=float, default=DEFAULT_WINDOW_S)
    args = ap.parse_args(argv)
    res = analyze(args.records, args.sessions, args.utterances, args.out, args.facing_deg, args.facing_threshold,
                  args.start_distance, args.distance_split, args.facing_split, args.window_s)
    _print_summary(res["summary"])
    print(f"결과: {Path(args.out) / 'differentiation_summary.json'}")


if __name__ == "__main__":
    main()
