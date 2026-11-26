"""합성 배치 세션 생성기 — 기록 형식 `ifs-placement/0.1`을 따르는 가짜 세션 폴더와 발화 파일을 만든다.

**합성 자료: 파이프라인 검증용이며 효과의 근거가 아님.** 참여자 자료가 아니다(AGENTS.md 원칙 6).
목적은 placement → differentiation 분석 파이프라인이 형식대로 돌고, 연구자가 미리 정한 가상 유형을 표로 구분해 내는지
확인하는 것뿐이다. 유형마다의 거리·머리 방향·평정·발화는 연구자가 정한 합성 값(아래 ARCHETYPES)이므로, 분석 결과가
유형을 잘 가른다는 것은 **코드가 정의대로 계산한다**는 뜻이지 측정이 타당하다는 뜻이 아니다.

  python -m ifs_chatbot.eval.sim_placement --out <폴더> [--seed 20261123] [--per-type 6] [--hz 5] \
      [--analyze] [--extra-records <실제 Unity 기록 루트>]
  → <폴더>/records/placement/P###/SIM##/<utc>/ (manifest flags.synthetic = true)
    <폴더>/utterances.jsonl(L-A·L-B 사전·사후 발화), <폴더>/sim_truth.json(세션별 가정 유형 — 분석기는 읽지 않음)
    --analyze: <폴더>/analysis/placement/, analysis/differentiation/(고정 기준), analysis/differentiation_median/(중앙값 분할),
               (--extra-records가 있으면) analysis/with_unity_records/, 그리고 analysis/sim_check.json(유형별 대조)

결정적: 같은 seed·인자 → 같은 바이트(난수는 random.Random(seed) 하나, 시각은 고정 값에서 계산).
머리·물체 표본 주기는 --hz(기본 4 Hz, 러너 기본 20 Hz보다 낮춰 용량을 줄임. manifest config.headSampleHz에 적음).

G60-2·G60-3(2026-11-26) 선택: --stop-mode loop(멈춤 거리 반복 멈춤 — stoprounds.csv·stopadjust.csv, 출발 계획은 러너와 같은
xorshift64* 규칙 stop_loop_plan), --eye-mode relative(세션마다 눈높이 E를 정해 시작·멈춤 높이를 E − 1.60만큼 옮기고 manifest eyeHeight를 씀).
둘 다 기본(single·none)이면 예전과 바이트까지 같다(새 난수는 새 방식에서만 뽑음). 새 방식 기록은 기존 검증 폴더가 아닌 새 폴더에 만든다.
--analyze면 기본 방식과 같은 파이프라인(placement → differentiation 고정·중앙값 → sim_check)을 돈다. loop 기록의 멈춤 성분은
differentiation이 placement의 주 값 stop_final_mean_m으로 읽는다(G60-2, 2026-11-26).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import random
import shutil
import sys
from pathlib import Path

from ..korean import normalize
from .profile_items import ITEM_SCALES, PROFILE_ITEMS

SIM_VERSION = "sim-placement/0.1"
SYNTHETIC_NOTE = "합성 자료: 파이프라인 검증용이며 효과의 근거가 아님"
MARKER_FILE = "SYNTHETIC_README.md"
HEAD_COLS = ["time_ms", "phase", "head_x", "head_y", "head_z", "head_qx", "head_qy", "head_qz", "head_qw",
             "obj_x", "obj_y", "obj_z", "distance_m", "angle_deg"]
OBJ_COLS = ["time_ms", "phase", "obj_x", "obj_y", "obj_z", "distance_m", "azimuth_deg", "height_m", "state"]
STOP_COLS = ["trial", "practice", "direction", "start_distance_m", "speed_mps", "stop_distance_m", "rt_ms", "timed_out"]
HEAD_POS = (0.0, 1.6, 0.0)
START = (0.0, 1.2, 1.5)               # 러너 기본 시작 자리(정면 1.5 m, 높이 1.2 m)
FLOOR_R = 4.0
STOP_SPEED = 0.25
CONDITION_S = 90.0
BASELINE_S = 30.0

# G60-2 반복 멈춤(러너 PlacementConfig 기본값과 같게)
LOOP = {"minM": 0.4, "maxM": 3.6, "startMinM": 1.0, "startMaxM": 3.0, "rounds": 4, "practiceRounds": 1,
        "roundSeconds": 75.0, "toggleDebounceMs": 250.0, "hideRings": True}
LOOP_ROUNDS_COLS = ["round", "practice", "start_dir", "start_distance_m", "speed_mps", "final_distance_m", "first_stop_distance_m",
                    "last_stop_distance_m", "n_stops", "n_resumes", "final_motion_dir", "passes_before_confirm", "stop_spread_m",
                    "at_bound", "end_reason", "duration_ms", "eye_object_distance_m"]
LOOP_ADJUST_COLS = ["round", "practice", "time_ms", "t_ms", "event", "distance_m", "motion_dir", "rt_ms"]
LOOP_START_RULE = "xorshift64star(splitmix64(participantNumber)), uniform [startMinM, startMaxM], round 0.001 m"
EYE_REF = 1.6
_M64 = (1 << 64) - 1


class XorShift64Star:
    """러너 StopLoopSchedule.cs의 XorShift64Star와 같은 수열(splitmix64로 시드를 펴고 xorshift64*로 뽑음)."""

    def __init__(self, seed: int):
        z = (seed + 0x9E3779B97F4A7C15) & _M64
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M64
        z ^= z >> 31
        self.s = z or 0x9E3779B97F4A7C15

    def next_ulong(self) -> int:
        x = self.s
        x ^= x >> 12
        x ^= (x << 25) & _M64
        x ^= x >> 27
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & _M64

    def next_double(self) -> float:
        return (self.next_ulong() >> 11) * (1.0 / 9007199254740992.0)


def _round_half_away(x: float, nd: int) -> float:
    q = 10 ** nd
    return math.floor(abs(x) * q + 0.5) / q * (1 if x >= 0 else -1)


def stop_loop_plan(pnum: int, first: str, loop: dict = LOOP) -> list[dict]:
    """러너 StopLoopSchedule.Build와 같은 라운드 계획: 연습 뒤 본 라운드, 출발 방향 번갈아, 출발 거리는 번호 시드 의사난수(1 mm)."""
    second = "recede" if first == "approach" else "approach"
    rng = XorShift64Star(pnum)
    out = []
    for i in range(loop["practiceRounds"] + loop["rounds"]):
        u = rng.next_double()
        out.append({"round": i + 1, "practice": i < loop["practiceRounds"], "startDir": first if i % 2 == 0 else second,
                    "startDistanceM": _round_half_away(loop["startMinM"] + (loop["startMaxM"] - loop["startMinM"]) * u, 3)})
    return out


def simulate_loop_round(start: float, direction: int, stops: list[float], confirm: bool, speed: float = STOP_SPEED,
                        lo: float = LOOP["minM"], hi: float = LOOP["maxM"], dwell_s: float = 0.8,
                        limit_s: float = LOOP["roundSeconds"]) -> dict:
    """반복 멈춤 한 라운드를 해석적으로 푼다(러너와 같은 규칙: 왕복·끝에서 반사, 멈춤/재개는 같은 방향, 확정은 멈춘 상태에서).
    stops = 차례로 멈출 거리(물체가 그 거리를 처음 지나는 순간), 각 멈춤 뒤 dwell_s 머문 뒤 다시 움직이거나(남았으면) 확정(confirm).
    → {"events": [(t_s, event, distance, dir, rt_s)], "end": t_s, "reason", "final", "stops", "points", "path": [(t_s, d)]}"""
    t, d, dr = 0.0, start, direction
    last_change = 0.0
    events = [(0.0, "start", d, dr, 0.0)]
    path = [(0.0, d)]
    points = [d]
    stop_ds: list[float] = []
    last_stop_dir = None

    def travel_to(target: float | None, until: float):
        """target(없으면 until까지)을 처음 지날 때까지 움직인다. → 닿았나"""
        nonlocal t, d, dr
        while True:
            bound = hi if dr > 0 else lo
            hit_target = target is not None and ((dr > 0 and d < target <= bound) or (dr < 0 and bound <= target < d))
            nxt = target if hit_target else bound
            dt = abs(nxt - d) / speed
            if t + dt >= until:
                d += dr * speed * (until - t)
                t = until
                path.append((t, d))
                return False
            t += dt
            d = nxt
            path.append((t, d))
            if hit_target:
                return True
            dr = -dr
            points.append(d)
            events.append((t, "turn", d, dr, t - last_change))

    for i, target in enumerate(stops):
        if not travel_to(target, limit_s):
            events.append((t, "timeout", d, dr, t - last_change))
            return {"events": events, "end": t, "reason": "timeout_moving", "final": None, "stops": stop_ds,
                    "points": points, "path": path, "last_dir": last_stop_dir}
        stop_ds.append(d)
        points.append(d)
        last_stop_dir = dr
        events.append((t, "stop", d, dr, t - last_change))
        last_change = t
        if t + dwell_s >= limit_s:
            t = limit_s
            path.append((t, d))
            events.append((t, "timeout", d, dr, t - last_change))
            return {"events": events, "end": t, "reason": "timeout_stopped", "final": None, "stops": stop_ds,
                    "points": points, "path": path, "last_dir": last_stop_dir}
        t += dwell_s
        path.append((t, d))
        if i + 1 < len(stops):
            events.append((t, "resume", d, dr, t - last_change))
            last_change = t
        elif confirm:
            events.append((t, "confirm", d, dr, t - last_change))
            return {"events": events, "end": t, "reason": "confirmed", "final": d, "stops": stop_ds,
                    "points": points, "path": path, "last_dir": last_stop_dir}
    if not stops:
        travel_to(None, limit_s)
        events.append((t, "timeout", d, dr, t - last_change))
        return {"events": events, "end": t, "reason": "timeout_moving", "final": None, "stops": [], "points": points,
                "path": path, "last_dir": None}
    t = limit_s                      # 멈춘 채 확정하지 않음
    path.append((t, d))
    events.append((t, "timeout", d, dr, t - last_change))
    return {"events": events, "end": t, "reason": "timeout_stopped", "final": None, "stops": stop_ds, "points": points,
            "path": path, "last_dir": last_stop_dir}


def _passes(points: list[float], final: float) -> int:
    return sum(1 for a, b in zip(points, points[1:]) if min(a, b) + 1e-6 < final < max(a, b) - 1e-6)


def _path_at(path: list[tuple[float, float]], tm: float) -> float:
    for (t0, d0), (t1, d1) in zip(path, path[1:]):
        if t0 <= tm <= t1:
            return d0 if t1 == t0 else d0 + (d1 - d0) * (tm - t0) / (t1 - t0)
    return path[-1][1]

# ---------------------------------------------------------------- 가정한 가상 유형(연구자가 정한 합성 값)
# ratings: 문항 → (사전 중심, 사후 중심). 세션마다 −1·0·0·+1 중 하나를 더하고 척도 끝에서 자른다.
# p_face: (처음 30초, 마지막 30초)에 머리가 물체를 향할(각 ≤ 12°) 확률의 중심(세션마다 ±0.1 균등).
ARCHETYPES = {
    "near_look": {
        "label": "가까이 두고 바라봄", "condition": "place", "control": "none", "expected_quadrant": "NL",
        "distance": (0.7, 1.2), "azimuth": (-30.0, 30.0), "height": (0.9, 1.3), "grabs": (1, 2),
        "p_face": (0.6, 0.85), "stop": {"approach": (0.6, 0.8), "recede": (0.8, 1.0)},
        "ratings": {"M1p": (5, 7), "M2": (4, 6), "P1": (3, 5), "M3": (4, 6), "P2": (4, 5), "S5": (5, 6), "S6": (3, 2)},
        "utter": {("pre", "L-A"): ["나는 불안 덩어리예요.", "저는 그 돌이에요.", "그 돌이 저예요."],
                  ("post", "L-A"): ["내 안에 불안한 게 있어요.", "저한테 그런 마음이 있네요.", "제 안에 작은 돌이 있어요."],
                  ("pre", "L-B"): ["좀 무서워요.", "아직 무서워요."],
                  ("post", "L-B"): ["궁금해요.", "좀 안쓰러워요."]},
    },
    "far_look": {
        "label": "멀리 두고 바라봄", "condition": "place", "control": "none", "expected_quadrant": "FL",
        "distance": (2.6, 3.4), "azimuth": (-40.0, 40.0), "height": (0.9, 1.3), "grabs": (2, 3),
        "p_face": (0.7, 0.8), "stop": {"approach": (1.4, 1.7), "recede": (1.6, 1.9)},
        "ratings": {"M1p": (5, 6), "M2": (4, 5), "P1": (3, 4), "M3": (4, 4), "P2": (3, 3), "S5": (5, 5), "S6": (4, 6)},
        "utter": {("pre", "L-A"): ["나는 그 돌이에요.", "저는 그냥 불안한 사람이에요."],
                  ("post", "L-A"): ["그게 저기 멀리 보여요.", "그 돌이 멀리 보여요."],
                  ("pre", "L-B"): ["좀 두려워요."],
                  ("post", "L-B"): ["아직 무서워요.", "좀 두려워요."]},
    },
    "far_away": {
        "label": "멀리 두고 고개 돌림", "condition": "place", "control": "none", "expected_quadrant": "FA",
        "distance": (2.8, 3.6), "azimuth": (-60.0, 60.0), "height": (0.6, 1.2), "grabs": (1, 1),
        "p_face": (0.5, 0.15), "stop": {"approach": (1.6, 2.0), "recede": (1.8, 2.2)},
        "ratings": {"M1p": (5, 5), "M2": (4, 6), "P1": (3, 5), "M3": (4, 4), "P2": (4, 3), "S5": (4, 2), "S6": (4, 6)},
        "utter": {("pre", "L-A"): ["저는 그냥 불안한 사람이에요.", "나는 불안 덩어리예요."],
                  ("post", "L-A"): ["그건 저기 있어요.", "그 돌은 아직 저기 있네요."],
                  ("pre", "L-B"): ["좀 짜증 나요."],
                  ("post", "L-B"): ["싫어요.", "보고 싶지 않아요."]},
    },
    "view_only": {
        "label": "보기만 조건", "condition": "view", "control": "static", "expected_quadrant": None,
        "distance": (1.5, 1.5), "azimuth": (0.0, 0.0), "height": (1.2, 1.2), "grabs": (0, 0),
        "p_face": (0.6, 0.6), "stop": {"approach": (1.0, 1.2), "recede": (1.2, 1.4)},
        "ratings": {"M1p": (5, 6), "M2": (4, 5), "P1": (3, 4), "M3": (4, 5), "P2": (4, 4), "S5": (4, 4), "S6": (3, 3)},
        "utter": {("pre", "L-A"): ["무거워요.", "잘 모르겠어요."],
                  ("post", "L-A"): ["무거웠어요.", "그 돌이 작아 보였어요."],
                  ("pre", "L-B"): ["잘 모르겠어요."],
                  ("post", "L-B"): ["괜찮아요."]},
    },
}


# ---------------------------------------------------------------- 기하

def polar(distance: float, az_deg: float, height: float) -> tuple[float, float, float]:
    a = math.radians(az_deg)
    return (distance * math.sin(a), height, distance * math.cos(a))


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def head_pose(head, obj, yaw_offset_deg: float):
    """머리→물체 방향에서 yaw만 yaw_offset만큼 돌린 정면. → (쿼터니언, 머리–물체 거리, 정면–물체 각)."""
    d = [obj[i] - head[i] for i in range(3)]
    dist = math.sqrt(sum(c * c for c in d))
    u = [c / dist for c in d]
    yaw = math.atan2(u[0], u[2]) + math.radians(yaw_offset_deg)
    pitch = -math.asin(max(-1.0, min(1.0, u[1])))        # +면 아래를 봄(+x축 회전)
    fwd = (math.sin(yaw) * math.cos(pitch), -math.sin(pitch), math.cos(yaw) * math.cos(pitch))
    cosang = max(-1.0, min(1.0, sum(f * v for f, v in zip(fwd, u))))
    q = qmul((0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)), (math.sin(pitch / 2), 0.0, 0.0, math.cos(pitch / 2)))
    return q, dist, math.degrees(math.acos(cosang))


def _f(x: float, nd: int = 4) -> str:
    s = f"{x:.{nd}f}"
    return "0." + "0" * nd if s.startswith("-0.") and float(s) == 0 else s


def _csv_text(header, rows) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------- 세션 하나

def _rating(rng: random.Random, item: str, center: float) -> int:
    lo, hi = ITEM_SCALES[item]
    return int(max(lo, min(hi, center + rng.choice((-1, 0, 0, 1)))))


def make_session(root: Path, rng: random.Random, pnum: int, sid: str, arch_key: str, hz: float, seed: int,
                 index: int, stop_mode: str = "single", eye_mode: str = "none") -> dict:
    """세션 폴더 하나를 쓰고 발화 4개와 가정 정보를 돌려준다.
    stop_mode loop·eye_mode relative(G60-2·G60-3)는 새 방식 기록 — 기본(single·none)이면 난수를 더 뽑지 않아 예전과 같은 바이트."""
    A = ARCHETYPES[arch_key]
    place = A["condition"] == "place"
    loop = stop_mode == "loop"
    eye_rel = eye_mode == "relative"
    eye_h = round(min(1.90, max(1.35, rng.gauss(1.62, 0.07))), 3) if eye_rel else EYE_REF
    off = eye_h - EYE_REF if eye_rel else 0.0
    head_pos = (HEAD_POS[0], eye_h, HEAD_POS[2]) if eye_rel else HEAD_POS
    start_pos = (START[0], START[1] + off, START[2]) if eye_rel else START
    stop_h = 1.2 + off
    dt = 1000.0 / hz
    utc = f"20261123-{index // 60:02d}{index % 60:02d}00"
    started = f"2026-11-23T{index // 60:02d}:{index % 60:02d}:00.000Z"
    folder = root / "placement" / f"P{pnum:03d}" / sid / utc
    folder.mkdir(parents=True, exist_ok=True)

    final = polar(rng.uniform(*A["distance"]), rng.uniform(*A["azimuth"]), rng.uniform(*A["height"]))
    if not place:
        final = start_pos
    p_early = min(1.0, max(0.0, A["p_face"][0] + rng.uniform(-0.1, 0.1)))
    p_late = min(1.0, max(0.0, A["p_face"][1] + rng.uniform(-0.1, 0.1)))

    # 단계 시각(ms)
    t_base, t_pre = 0.0, BASELINE_S * 1000
    t_prewait, t_cond = t_pre + 10000, t_pre + 15000
    t_post = t_cond + CONDITION_S * 1000
    t_postwait, t_stop = t_post + 10000, t_post + 15000

    # 직접 배치 궤적: 잡기 n번, 마지막 놓기에서 최종 자리
    segments = []      # (t0, t1, p0, p1)
    grabs = rng.randint(*A["grabs"]) if place else 0
    cur, t = start_pos, t_cond + rng.uniform(1500, 4000)
    first_grab = t - t_cond if grabs else None
    held = 0.0
    for g in range(grabs):
        if g == grabs - 1:
            target = final
        else:
            frac = rng.uniform(0.3, 0.8)
            target = tuple(start_pos[i] + (final[i] - start_pos[i]) * frac for i in range(3))
            target = (target[0] + rng.uniform(-0.4, 0.4), target[1], target[2])
        dur = rng.uniform(2000, 4000)
        segments.append((t, t + dur, cur, target))
        held += dur
        cur = target
        t += dur + rng.uniform(2000, 6000)
    confirm_ms = (segments[-1][1] - t_cond + 2000) if segments else None

    def obj_at(tm: float):
        if tm < t_cond or not segments:
            return start_pos if tm < t_cond else (final if place else start_pos), "idle"
        if tm >= t_post:
            return final, "idle"
        pos, state = start_pos, "idle"
        for t0, t1, p0, p1 in segments:
            if tm < t0:
                return pos, state
            if tm <= t1:
                f = (tm - t0) / (t1 - t0)
                return tuple(p0[i] + (p1[i] - p0[i]) * f for i in range(3)), "held"
            pos, state = p1, "idle"
        return pos, state

    hrows, orows, cond_path = [], [], []

    def sample(tm: float, phase: str, obj, state: str | None, p_face: float | None):
        if obj is None:
            hrows.append([int(tm), phase, _f(head_pos[0]), _f(head_pos[1]), _f(head_pos[2]),
                          "0.000000", "0.000000", "0.000000", "1.000000", "", "", "", "", ""])
            return
        facing = rng.random() < (p_face if p_face is not None else 0.9)
        off = rng.uniform(0.0, 12.0) if facing else rng.uniform(25.0, 120.0)
        off *= rng.choice((-1.0, 1.0))
        q, dist, ang = head_pose(head_pos, obj, off)
        hrows.append([int(tm), phase, _f(head_pos[0]), _f(head_pos[1]), _f(head_pos[2]),
                      *(f"{c:.6f}" for c in q), _f(obj[0]), _f(obj[1]), _f(obj[2]), _f(dist), f"{ang:.2f}"])
        hd = math.hypot(obj[0], obj[2])
        orows.append([int(tm), phase, _f(obj[0]), _f(obj[1]), _f(obj[2]), _f(hd),
                      f"{math.degrees(math.atan2(obj[0], obj[2])):.2f}", _f(obj[1]), state])

    tm = t_base
    while tm < t_pre:
        sample(tm, "baseline", start_pos, "idle", None)
        tm += dt
    while tm < t_prewait:
        sample(tm, "pre_items", start_pos, "idle", None)
        tm += dt
    while tm < t_cond:
        sample(tm, "pre_wait", None, None, None)
        tm += dt
    while tm < t_post:
        rel = (tm - t_cond) / 1000.0
        p = p_early if rel < 30 else p_late if rel >= 60 else p_early + (p_late - p_early) * (rel - 30) / 30
        obj, state = obj_at(tm)
        sample(tm, "condition", obj, state if place else "idle", p)
        cond_path.append(obj)
        tm += dt
    while tm < t_postwait:
        sample(tm, "post_items", final, "idle", None)
        tm += dt
    while tm < t_stop:
        sample(tm, "post_wait", None, None, None)
        tm += dt

    # 멈춤 거리: 연습 2(approach·recede) + 방향 교차 4·4. 첫 방향은 번호 홀짝(러너 기본 by_participant)
    first = "approach" if pnum % 2 else "recede"
    other = "recede" if first == "approach" else "approach"
    order = [(1, first), (1, other)] + [(0, d) for _ in range(4) for d in (first, other)]
    srows, events = [], []
    trial_t = t_stop
    loop_rounds, loop_adjust, loop_plan = [], [], []
    if loop:
        order = []                          # G60-2: single 시행 대신 반복 멈춤 라운드
        loop_plan = stop_loop_plan(pnum, first)
        a_lo, a_hi = A["stop"]["approach"]
        r_lo, r_hi = A["stop"]["recede"]
        c_lo, c_hi = (a_lo + r_lo) / 2, (a_hi + r_hi) / 2
        for pr in loop_plan:
            target = round(min(3.5, max(0.5, rng.uniform(c_lo, c_hi) + rng.gauss(0, 0.05))), 3)
            n_stops = rng.choice((1, 1, 2, 3))
            stops = [round(min(3.5, max(0.5, target + rng.choice((-1, 1)) * rng.uniform(0.15, 0.35))), 3)
                     for _ in range(n_stops - 1)] + [target]
            confirm = pr["practice"] or rng.random() > 0.08
            res = simulate_loop_round(pr["startDistanceM"], -1 if pr["startDir"] == "approach" else 1, stops, confirm)
            practice = 1 if pr["practice"] else 0
            t0 = trial_t
            events.append([int(t0), "stop_round_start", f"round={pr['round']};practice={practice};start_dir={pr['startDir']}"])
            for (te, ev_name, de, dre, rte) in res["events"]:
                loop_adjust.append([pr["round"], practice, int(round(t0 + te * 1000)), int(round(te * 1000)), ev_name,
                                    _f(de), "approach" if dre < 0 else "recede", int(round(rte * 1000))])
            flat = {(a[0], b[0]) for a, b in zip(res["path"], res["path"][1:]) if a[1] == b[1] and b[0] > a[0]}
            tt = t0
            while tt < t0 + res["end"] * 1000:
                ts = (tt - t0) / 1000
                paused = any(a <= ts < b for a, b in flat)
                sample(tt, "stop_distance", (0.0, stop_h, _path_at(res["path"], ts)), "stop_paused" if paused else "stop", None)
                tt += dt
            fin, sd = res["final"], res["stops"]
            eye_d = math.hypot(fin, head_pos[1] - stop_h) if fin is not None else None
            loop_rounds.append([pr["round"], practice, pr["startDir"], _f(pr["startDistanceM"]), _f(STOP_SPEED),
                                _f(fin) if fin is not None else "", _f(sd[0]) if sd else "", _f(sd[-1]) if sd else "",
                                len(sd), max(0, len(sd) - 1),
                                ("approach" if res["last_dir"] < 0 else "recede") if res["last_dir"] is not None else "",
                                _passes(res["points"], fin) if fin is not None else "",
                                _f(max(sd) - min(sd)) if sd else "",
                                (1 if fin - LOOP["minM"] <= 0.05 or LOOP["maxM"] - fin <= 0.05 else 0) if fin is not None else "",
                                res["reason"], int(round(res["end"] * 1000)), _f(eye_d) if eye_d is not None else ""])
            events.append([int(t0 + res["end"] * 1000), "stop_round_end",
                           f"round={pr['round']};end_reason={res['reason']};final_m={_f(fin) if fin is not None else ''}"])
            trial_t = t0 + res["end"] * 1000 + 2000
    for k, (practice, direction) in enumerate(order, 1):
        start_d = 3.0 if direction == "approach" else 0.5
        lo, hi = A["stop"][direction]
        stop_d = round(min(3.9, max(0.25, rng.uniform(lo, hi) + rng.gauss(0, 0.05))), 3)
        rt = abs(start_d - stop_d) / STOP_SPEED * 1000.0
        stop_d = round(start_d - STOP_SPEED * rt / 1000.0 if direction == "approach" else start_d + STOP_SPEED * rt / 1000.0, 4)
        events.append([int(trial_t), "stop_trial_start", f"trial={k};direction={direction}"])
        tt = trial_t
        while tt < trial_t + rt:
            dnow = start_d - STOP_SPEED * (tt - trial_t) / 1000 if direction == "approach" \
                else start_d + STOP_SPEED * (tt - trial_t) / 1000
            sample(tt, "stop_distance", (0.0, stop_h, dnow), "stop", None)
            tt += dt
        events.append([int(trial_t + rt), "stop_press", f"trial={k};distance={stop_d}"])
        srows.append([k, practice, direction, start_d, STOP_SPEED, stop_d, int(round(rt)), 0])
        trial_t += rt + 2000
    t_done = trial_t

    # 평정
    ratings, rt_ms = [], 900
    vals = {}
    for when, ti in (("pre", 0), ("post", 1)):
        for item in PROFILE_ITEMS:
            v = _rating(rng, item, A["ratings"][item][ti])
            vals[(item, when)] = v
            ratings.append([item, when, v, rt_ms + rng.randint(0, 900)])

    # 사건
    ev = [[0, "session_start", f"participant={pnum};session={sid}"], [0, "auto_mode", "synthetic_simulator"],
          [0, "phase", "baseline"], [int(t_pre), "phase", "pre_items"], [int(t_prewait), "phase", "pre_wait"],
          [int(t_cond), "phase", "condition"]]
    for t0, t1, _, _ in segments:
        ev += [[int(t0), "grab", ""], [int(t1), "release", ""]]
    if confirm_ms is not None:
        ev.append([int(t_cond + confirm_ms), "confirm", ""])
    ev += [[int(t_post), "phase", "post_items"], [int(t_postwait), "phase", "post_wait"],
           [int(t_stop), "phase", "stop_distance"]] + events + [[int(t_done), "phase", "done"]]
    ev.sort(key=lambda e: e[0])

    path_len = sum(math.dist(cond_path[i], cond_path[i + 1]) for i in range(len(cond_path) - 1))
    fd = math.hypot(final[0], final[2])
    pl = {"condition": A["condition"], "controlMode": A["control"], "phaseDurationMs": int(CONDITION_S * 1000),
          "finalX": round(final[0], 4), "finalY": round(final[1], 4), "finalZ": round(final[2], 4),
          "finalDistanceM": round(fd, 4), "finalAzimuthDeg": round(math.degrees(math.atan2(final[0], final[2])), 2),
          "finalHeightM": round(final[1], 4), "grabCount": grabs, "firstGrabMs": int(first_grab) if first_grab else None,
          "heldMs": int(held), "pathLengthM": round(path_len, 4), "confirmed": confirm_ms is not None,
          "confirmMs": int(confirm_ms) if confirm_ms is not None else None, "conditionCompleted": True}
    traj = {"version": "ifs-trajectory/0.1", "sourceSessionId": sid, "sampleHz": hz, "startDistanceM": start_pos[2],
            "startHeightM": start_pos[1],
            "samples": [{"t_ms": int(i * dt), "x": round(p[0], 4), "y": round(p[1], 4), "z": round(p[2], 4)}
                        for i, p in enumerate(cond_path)]}
    manifest = {
        "recordVersion": "ifs-placement/0.1", "participantNumber": pnum, "sessionId": sid,
        "specFile": "synthetic", "specSha256": "0" * 64, "startedAtUtc": started, "unityVersion": "none (synthetic)",
        "headSource": "desktop", "inputSource": "auto", "condition": A["condition"], "controlMode": A["control"],
        "space": {"floorRadiusM": FLOOR_R, "ringRadiiM": [1.0, 2.0, 3.0], "showRings": True,
                  "startDistanceM": START[2], "startHeightM": START[1], "startPlacementSource": "experiment_config"},
        "object": {"boundingRadiusM": 0.2},
        "stopDistance": {"speedMps": STOP_SPEED, "approachStartM": 3.0, "recedeStartM": 0.5, "trialsPerDirection": 4,
                         "practiceTrials": 2, "minM": 0.2, "maxM": 4.0},
        "replaySource": None, "systemMoveTarget": None,
        "taskText": {"file": "synthetic (문구 없음 — 문항 키만)", "version": None, "draftCount": len(PROFILE_ITEMS),
                     "draftKeys": list(PROFILE_ITEMS)},
        "config": {"baselineSeconds": BASELINE_S, "conditionSeconds": CONDITION_S, "conditionEndsOnConfirm": False,
                   "headSampleHz": hz},
        "flags": {"autoMode": True, "synthetic": True, "syntheticNote": SYNTHETIC_NOTE, "simulator": SIM_VERSION,
                  "seed": seed, "stopFirstDirection": first, "layoutIgnored": False},
    }
    if loop:   # G60-2: 러너처럼 stopDistance에 mode·loop, config 끝에 stopMode·stopLoop* 키
        manifest["stopDistance"]["mode"] = "loop"
        manifest["stopDistance"]["loop"] = {
            "minM": LOOP["minM"], "maxM": LOOP["maxM"], "speedMps": STOP_SPEED, "heightM": 1.2,
            "startMinM": LOOP["startMinM"], "startMaxM": LOOP["startMaxM"], "startRule": LOOP_START_RULE,
            "rounds": LOOP["rounds"], "practiceRounds": LOOP["practiceRounds"], "roundSeconds": LOOP["roundSeconds"],
            "toggleDebounceMs": LOOP["toggleDebounceMs"], "hideRings": LOOP["hideRings"],
            "plan": [{"round": p["round"], "practice": p["practice"], "startDir": p["startDir"],
                      "startDistanceM": p["startDistanceM"]} for p in loop_plan]}
        manifest["config"]["stopMode"] = "loop"
    if eye_rel:   # G60-3: 러너처럼 config 끝에 eyeHeightMode, manifest 맨 끝에 eyeHeight
        manifest["config"]["eyeHeightMode"] = "relative"
        manifest["eyeHeight"] = {"mode": "relative", "referenceM": EYE_REF, "measuredM": eye_h, "offsetM": round(off, 4),
                                 "sdM": 0.006, "pitchDeg": 2.0, "samples": 20, "trackingOrigin": "Floor",
                                 "source": "calibrated"}
    files = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        "headpose.csv": _csv_text(HEAD_COLS, hrows),
        "objpose.csv": _csv_text(OBJ_COLS, orows),
        "events.csv": _csv_text(["time_ms", "event", "detail"], ev),
        "placement.json": json.dumps(pl, ensure_ascii=False, indent=2) + "\n",
        "stopdistance.csv": _csv_text(STOP_COLS, srows),
        "ratings.csv": _csv_text(["item", "when", "rating", "rt_ms"], ratings),
        "trajectory.json": json.dumps(traj, ensure_ascii=False) + "\n",
        "summary.json": json.dumps({"completed": True, "abortedAt": None,
                                    "endedAtUtc": started}, ensure_ascii=False, indent=2) + "\n",
    }
    if loop:
        files["stoprounds.csv"] = _csv_text(LOOP_ROUNDS_COLS, loop_rounds)
        files["stopadjust.csv"] = _csv_text(LOOP_ADJUST_COLS, loop_adjust)
    for name, body in files.items():
        (folder / name).write_text(body, encoding="utf-8", newline="\n")

    utter = []
    for (when, prompt), options in sorted(A["utter"].items()):
        utter.append({"participant": f"P{pnum:03d}", "session_id": sid, "when": when, "prompt": prompt,
                      "text": normalize(rng.choice(options)), "synthetic": True})
    truth = {"participant": f"P{pnum:03d}", "session_id": sid, "archetype": arch_key, "label": A["label"],
             "condition": A["condition"], "expected_quadrant": A["expected_quadrant"],
             "p_face_early": round(p_early, 3), "p_face_late": round(p_late, 3),
             "final_distance_m": round(fd, 4), "grabs": grabs}
    if loop:      # 새 방식에서만(기본 sim_truth.json 바이트 그대로)
        truth["stop_mode"] = "loop"
        truth["loop_end_reasons"] = [r[14] for r in loop_rounds]
    if eye_rel:
        truth["eye_height_m"] = eye_h
    return {"utterances": utter, "truth": truth}


# ---------------------------------------------------------------- 전체 생성

def archetype_table() -> list[dict]:
    rows = []
    for k, A in ARCHETYPES.items():
        rows.append({"archetype": k, "label": A["label"], "condition": f"{A['condition']}/{A['control']}",
                     "expected_quadrant": A["expected_quadrant"], "distance_m": list(A["distance"]),
                     "p_face_early_late": list(A["p_face"]), "grabs": list(A["grabs"]),
                     "stop_m": {d: list(v) for d, v in A["stop"].items()},
                     "ratings_pre_post": {i: list(v) for i, v in A["ratings"].items()},
                     "utterances": {f"{w}/{p}": v for (w, p), v in sorted(A["utter"].items())}})
    return rows


def generate(out: str | Path, seed: int = 20261123, per_type: int = 6, hz: float = 4.0, stop_mode: str = "single",
             eye_mode: str = "none") -> dict:
    """stop_mode loop·eye_mode relative(G60-2·G60-3)는 새 방식 합성 기록. 기본이면 예전과 같은 바이트."""
    if stop_mode not in ("single", "loop") or eye_mode not in ("none", "relative"):
        raise ValueError(f"stop_mode {stop_mode} / eye_mode {eye_mode}: single|loop, none|relative")
    out = Path(out)
    root = out / "records"
    if root.exists():
        if not (root / MARKER_FILE).is_file():
            raise FileExistsError(f"{root}가 이미 있고 합성 표시 파일({MARKER_FILE})이 없어 지우지 않습니다")
        shutil.rmtree(root)
    root.mkdir(parents=True)
    rng = random.Random(seed)
    order = [k for k in ARCHETYPES for _ in range(per_type)]
    rng.shuffle(order)
    utter, truth = [], []
    for i, key in enumerate(order):
        res = make_session(root, rng, 101 + i, f"SIM{i + 1:02d}", key, hz, seed, i, stop_mode, eye_mode)
        utter += res["utterances"]
        truth.append(res["truth"])
    (root / MARKER_FILE).write_text(
        f"# 합성 배치 세션\n\n{SYNTHETIC_NOTE}.\n\n"
        f"`ifs_chatbot.eval.sim_placement`(seed {seed}, 유형당 {per_type}개, 표본 {hz:g} Hz)이 만든 가짜 기록입니다. "
        "참여자 자료가 아니며, 각 유형의 거리·머리 방향·평정·발화는 연구자가 정한 가정입니다(`../sim_truth.json`). "
        "모든 manifest의 `flags.synthetic`이 true입니다.\n"
        + (f"\n멈춤 거리 방식 {stop_mode}, 눈높이 {eye_mode}(G60-2·G60-3 새 방식 — 2026-11-26).\n"
           if stop_mode != "single" or eye_mode != "none" else ""), encoding="utf-8", newline="\n")
    (out / "utterances.jsonl").write_text("".join(json.dumps(u, ensure_ascii=False) + "\n" for u in utter),
                                          encoding="utf-8", newline="\n")
    truth_doc = {"version": SIM_VERSION, "synthetic": True, "note": SYNTHETIC_NOTE, "seed": seed, "perType": per_type,
                 "headSampleHz": hz, "archetypes": archetype_table(), "sessions": truth}
    if stop_mode != "single" or eye_mode != "none":
        truth_doc["stopMode"] = stop_mode
        truth_doc["eyeHeightMode"] = eye_mode
    (out / "sim_truth.json").write_text(json.dumps(truth_doc, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8", newline="\n")
    return truth_doc


# ---------------------------------------------------------------- 분석까지 한 번에

def _mean(vals):
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def sim_check(truth: dict, diff_res: dict, diff_median: dict | None = None) -> dict:
    """가정 유형 대 분석 결과(2×2 칸, 언어 표지 평균, 사례 수). 대조 표일 뿐 검정이 아니다."""
    from . import language_markers as lm
    by_key = {(r["participant"], r["session_id"]): r for r in diff_res["rows"]}
    med_key = {(r["participant"], r["session_id"]): r for r in diff_median["rows"]} if diff_median else {}
    out = {}
    for arch in ARCHETYPES:
        ts = [t for t in truth["sessions"] if t["archetype"] == arch]
        rows = [by_key[(t["participant"], t["session_id"])] for t in ts]
        exp = ARCHETYPES[arch]["expected_quadrant"]
        assigned: dict[str, int] = {}
        for r in rows:
            assigned[str(r["quadrant"])] = assigned.get(str(r["quadrant"]), 0) + 1
        med_assigned: dict[str, int] = {}
        for t in ts:
            q = str(med_key[(t["participant"], t["session_id"])]["quadrant"]) if med_key else None
            if q is not None:
                med_assigned[q] = med_assigned.get(q, 0) + 1
        cases: dict[str, int] = {}
        for c in diff_res["cases"]:
            if any(c["participant"] == t["participant"] and c["session_id"] == t["session_id"] for t in ts):
                cases[c["rule"]] = cases.get(c["rule"], 0) + 1
        out[arch] = {
            "label": ARCHETYPES[arch]["label"], "n": len(ts), "expected_quadrant": exp,
            "assigned_fixed": dict(sorted(assigned.items())),
            "match_fixed": sum(1 for r in rows if r["quadrant"] == exp) if exp else None,
            "assigned_median": dict(sorted(med_assigned.items())) if med_key else None,
            "match_median": (sum(1 for t in ts if med_key[(t["participant"], t["session_id"])]["quadrant"] == exp)
                             if exp and med_key else None),
            "g_late_mean": _mean(r["g_late"] for r in rows), "delta_d_mean": _mean(r["delta_d_m"] for r in rows),
            "language_means": {f"{k}_{w}": _mean(r[f"la_{k}_{w}"] for r in rows) for k in lm.MARKERS
                               for w in ("pre", "post")},
            "disid_change_mean": _mean(r["disid_change"] for r in rows),
            "ambivalent_post": sum(1 for r in rows if r["ambivalent_post"]),
            "cases": dict(sorted(cases.items())),
        }
        if any(r.get("stop_mode") == "loop" for r in rows):
            # G60-2: loop 기록일 때만(기본 sim_check.json 바이트 그대로). 멈춤 성분 = placement 주 값 stop_final_mean_m
            # 생성기의 loop 확정 거리 가정: 접근·후퇴 범위의 가운데 구간에서 고름(+ 작은 잡음, make_session)
            st = ARCHETYPES[arch]["stop"]
            out[arch]["stop_assumed_range_m"] = [round((st["approach"][0] + st["recede"][0]) / 2, 3),
                                                 round((st["approach"][1] + st["recede"][1]) / 2, 3)]
            out[arch]["sd_mean_mean"] = _mean(r["sd_mean_m"] for r in rows)
            out[arch]["sd_loop_insufficient"] = sum(1 for r in rows if "sd_loop_insufficient" in (r["flags"] or ""))
    conv = [c for c in diff_res["convergence"] if c["same_component"] and not c["same_method"]]
    return {"version": SIM_VERSION, "synthetic": True, "note": SYNTHETIC_NOTE + ". 유형별 값은 생성기가 정한 가정의 "
            "복원이다 — 분석 코드가 정의대로 계산하는지의 확인이지 측정의 타당성 근거가 아니다.",
            "byArchetype": out, "sameComponentCrossMethod": conv}


def run_pipeline(out: str | Path, seed: int, per_type: int, hz: float, extra_records: str | None,
                 stop_mode: str = "single", eye_mode: str = "none") -> dict:
    """생성 → placement → differentiation(고정·중앙값) → sim_check. stop_mode·eye_mode가 기본이면 예전과 같은 호출(같은 바이트)."""
    from . import differentiation, placement
    out = Path(out)
    truth = (generate(out, seed, per_type, hz) if stop_mode == "single" and eye_mode == "none"
             else generate(out, seed, per_type, hz, stop_mode, eye_mode))
    records, utter = out / "records", out / "utterances.jsonl"
    an = out / "analysis"
    placement.analyze(records, an / "placement")
    d_fixed = differentiation.analyze([records], utterances=utter, out_dir=an / "differentiation")
    d_median = differentiation.analyze([records], utterances=utter, out_dir=an / "differentiation_median",
                                       distance_split="median", facing_split="median")
    if extra_records:
        differentiation.analyze([records, extra_records], utterances=utter, out_dir=an / "with_unity_records")
    check = sim_check(truth, d_fixed, d_median)
    (an / "sim_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                       newline="\n")
    return check


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.sim_placement",
                                 description=f"합성 배치 세션 생성({SYNTHETIC_NOTE})")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261123)
    ap.add_argument("--per-type", type=int, default=6)
    ap.add_argument("--hz", type=float, default=4.0)
    ap.add_argument("--analyze", action="store_true", help="생성 뒤 placement·differentiation 분석까지")
    ap.add_argument("--extra-records", help="함께 분석할 다른 기록 루트(형식 호환 확인용, --analyze와 함께)")
    ap.add_argument("--stop-mode", choices=("single", "loop"), default="single",
                    help="(G60-2) 멈춤 거리 방식. loop면 반복 멈춤 기록(stoprounds.csv·stopadjust.csv)")
    ap.add_argument("--eye-mode", choices=("none", "relative"), default="none",
                    help="(G60-3) 눈높이. relative면 세션마다 눈높이를 정해 높이를 옮기고 manifest eyeHeight를 씀")
    args = ap.parse_args(argv)
    print(f"[{SYNTHETIC_NOTE}]")
    if args.analyze:
        check = run_pipeline(args.out, args.seed, args.per_type, args.hz, args.extra_records, args.stop_mode, args.eye_mode)
        for arch, v in check["byArchetype"].items():
            print(f"  {arch:<10} n={v['n']} 기대 {v['expected_quadrant']} → 고정 {v['assigned_fixed']} "
                  f"· 중앙값 {v['assigned_median']}")
        print(f"결과: {Path(args.out) / 'analysis'}")
    elif args.stop_mode != "single" or args.eye_mode != "none":
        t = generate(args.out, args.seed, args.per_type, args.hz, args.stop_mode, args.eye_mode)
        print(f"세션 {len(t['sessions'])}개: {Path(args.out) / 'records'}")
    else:
        t = generate(args.out, args.seed, args.per_type, args.hz)
        print(f"세션 {len(t['sessions'])}개: {Path(args.out) / 'records'}")


if __name__ == "__main__":
    main()
