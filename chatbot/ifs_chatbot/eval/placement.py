"""배치 실험(RQ V4) 기록 요약 — Unity 배치 러너가 남긴 placement 기록을 읽어 세션 표·멈춤 거리 시행 표·기술 통계를 낸다.
LLM 없음, 표준 라이브러리만, 결정론적(같은 기록 → 같은 출력).

  python -m ifs_chatbot.eval.placement --records <기록 루트 또는 그 아래 폴더> --out <폴더> [--facing-deg 15]
  (--gaze-deg는 --facing-deg의 옛 이름으로 남겨 둔 별칭)
  → <폴더>/placement_sessions.csv(세션 1행), stop_trials.csv(멈춤 거리 시행 1행), placement_summary.json
  선택(G59): --selection-dir <챗봇 logs/selection> — 사전 측정·사후 면담 파일이 있으면 pre_*·pi_* 열과 요약 selfReport를 더한다
  (eval/self_report.py). 파일이 하나도 없으면 출력은 바이트까지 그대로.

기록 형식은 계약 `ifs-placement/0.1`(Unity 러너와 따로 구현하므로 둘 사이의 약속)을 따른다.
  manifest.json, headpose.csv, objpose.csv, events.csv, placement.json, stopdistance.csv, ratings.csv,
  trajectory.json, summary.json
거리 지표는 "고른 거리"로 보고하고 심리적 거리의 측정이라고 부르지 않는다(docs/decisions.md X48).
통계는 기술·추정만 한다(n, 평균, 표준편차, 효과크기와 근사 신뢰구간). 유의성 판정은 내지 않는다
(docs/rq-v4-proposal.md 4.6: 예비 연구 규모에서는 유의성으로 결론 내지 않음).

기록 찾기
- --records 아래의 manifest.json을 모두 찾고, recordVersion이 "ifs-placement/"로 시작하는 것만 쓴다
  (소유감 기록 "ifs-ownership/…"이 섞여 있어도 무시).
- 같은 (participantNumber, sessionId)에 폴더가 여럿이면 summary.completed가 true인 것 중 가장 최근 것
  (폴더 이름, 같으면 startedAtUtc 순), 완료된 것이 없으면 가장 최근 미완료 폴더를 쓴다. 나머지는 skipped.
- 출력에는 --records 기준 상대 경로만 적는다.

계약에서 모호해 이 스크립트가 정한 해석(Unity 러너와 맞출 점)
- 놓은 자리(final_*)는 placement.json 값을 쓴다. placement.json이 없거나 값이 비면 조건 단계 objpose.csv의
  마지막 행(distance_m·azimuth_deg·height_m)을 쓰고 flags에 final_from_objpose를 남긴다. 방위각은 (−180, 180]로 맞춘다.
  placement.json 거리와 objpose 마지막 행 거리가 FINAL_TOL_M을 넘게 다르면 final_pose_mismatch.
- 고리 몰림: 가장 가까운 고리 반지름 nearest_ring_m, ring_offset_m = 놓은 거리 − 그 반지름(부호 있음).
  space.showRings가 false거나 고리가 없으면 빈칸. 요약의 몰림 비율은 place 조건만 센다(보기만 조건의 최종 위치는
  참여자가 고른 자리가 아니다).
- 멈춤 거리: practice=1 행과 timed_out=1 행을 뺀다. 방향별 평균을 먼저 내고 stop_mean_m = 두 방향 평균의 평균
  (한 방향이라도 값이 없으면 빈칸). stop_sd_m = 남은 시행 전체(방향 구분 없이)의 표본 표준편차(n−1).
  stop_n_timeout은 본 시행(연습 제외)의 timeout 수.
- 머리 행동: headpose.csv의 phase가 "condition"인 표본만. head_facing_ratio = angle_deg ≤ --facing-deg인 표본 수 / angle_deg가
  있는 표본 수(표본 비율, 시간 적분 아님). angle_deg는 머리 정면(+z) 방향과 머리→물체 방향 사이 각이다. 눈 추적이 아니므로
  시선(gaze)이 아니라 "머리가 물체 쪽을 향한 비율"이라는 대리 지표다(예전 이름 gaze_ratio). head_yaw_range_deg = 머리 쿼터니언의 정면(+z)을 수평면에 투영한 yaw들이
  덮은 원형 범위(360 − 가장 큰 빈 구간). yaw는 +z 기준, 오른쪽(+x)이 +.
- obj_path_from_objpose_m: 조건 단계 objpose.csv 연속 행 사이 3차원 위치 거리의 합. placement.json pathLengthM과
  차이가 max(PATH_TOL_ABS_M, PATH_TOL_REL × 큰 값)을 넘으면 objpose_path_mismatch. pathLengthM이 누가 움직였든
  조건 단계 동안 물체가 지나간 길이라고 보고 모든 통제 방식에서 비교한다(system_move·replay에서 러너가 0을 쓰면 이 flag가 뜬다).
- VR 안 평정: ratings.csv의 (item, when)마다 마지막 행. 열 이름 rating_{item}_{when}. 열은 모든 세션에서 발견된 키의 합집합.
  범위 점검은 1–7, 단 구별 프로파일의 0–10 문항(profile_items.ITEM_SCALES의 M1p·M2·M3)은 0–10(2026-11-23 추가).
- 빠진 파일 missing_file:<이름>, 0바이트 파일 empty_file:<이름>, JSON이 깨진 파일 unreadable_file:<이름>.
  recordVersion이 KNOWN_VERSIONS("ifs-placement/0.1"·"0.2")가 아니면 version_mismatch. placement.json의 condition·controlMode가 manifest와
  다르면 condition_mismatch. events.csv의 warning 행이 있으면 runner_warning:<개수>.
- summary.json이 없으면 미완료로 본다. completed=false 세션은 표에는 남기고 요약 통계에서 빼며 개수만 보고한다.
- 조건 단계 완료(condition_complete): placement.json의 conditionCompleted(bool)를 쓴다. 필드가 없는 옛 기록은
  summary.completed가 true면 true, 아니면 abortedAt이 조건 단계 뒤 단계면 true, 그 밖(조건 단계·그 앞에서 중단,
  summary 없음)은 false로 추정한다. false면 flags에 partial_condition을 달고 조건 단계 지표(놓은 자리·고리·잡기·경로·확인·
  머리 행동) 칸을 비운다(원자료 파일은 그대로라 필요하면 다시 계산할 수 있다). 이런 세션은 요약 통계에서 뺀다.
- object_radius_m: manifest object.boundingRadiusM(물체 렌더 경계 반지름, 없으면 빈칸). 거리 지표는 모두 물체 중심
  기준이고, 보이는 가장자리까지의 거리는 대략 이만큼 짧다.
- 물체 크기·모양 공변량(G72, 2026-11-27 — manifest object.boundsM·object.proportions가 있는 세션이 하나라도 있을 때만 OBJECT_COLUMNS):
  object_width_m·object_height_m·object_depth_m = object.boundsM x·y·z(불러온 직후 물체 자기 축의 경계 상자, m. 안개는 레이마칭
  구라 위쪽 한계), proportions_x·y·z = object.proportions의 그리는 비율(가장 큰 값 = 1, 비율이 없던 세션은 빈칸),
  proportions_source = said | edited | default(선택 파일 sources, 없으면 spec 값 유무), proportions_axis_said = 방향을 말했는지.
- 설정 일치 점검: 요약에 넣은 세션들 사이에서 manifest config의 baselineSeconds·conditionSeconds·conditionEndsOnConfirm,
  manifest space·stopDistance가 다르면 요약 warnings에 config_mismatch:<키>를 넣는다(빠진 값도 하나의 값으로 본다).

멈춤 거리 반복 멈춤(G60-2, 2026-11-26 — manifest stopDistance.mode == "loop"인 세션)
- 원자료는 stoprounds.csv(라운드 1행)와 stopadjust.csv(조정 사건). stopdistance.csv는 헤더만이라 single 열(stop_approach_mean_m 등)은 빈칸이고
  stop_trials_short 점검도 하지 않는다. loop 세션이 하나라도 있을 때만 세션 표에 LOOP_COLUMNS를, 결과 폴더에 stop_loop_rounds.csv를,
  요약에 stopLoop를 더한다(loop 세션이 없으면 출력은 G60 전과 바이트까지 같다).
- 주 값 stop_final_mean_m = 본 라운드(practice=0) 가운데 확정된(end_reason confirmed) 라운드의 final_distance_m 평균. 확정 라운드가
  LOOP_MIN_CONFIRMED(2)개 미만이면 빈칸. 확정하지 않은 라운드는 결측으로 세고(stop_n_unconfirmed) 마지막 멈춤 거리로 채우지 않는다(원칙 2).
- 방향별 평균 stop_final_approach_mean_m·stop_final_recede_mean_m은 final_motion_dir(마지막 멈춤 직전 진행 방향)로 나눈다.
  요약 stopLoop.directionDiff에서 세션별 차(approach − recede)의 평균 절댓값이 LOOP_DIR_WARN_M(0.15 m)을 넘으면 경고한다(히스테리시스 점검).
- stop_first_minus_final_mean_m = 확정 라운드마다 first_stop_distance_m − final_distance_m의 평균(예전 단일 누름 지표와 잇는 값).
- 닻 지표 stop_minus_condition_final_m = stop_final_mean_m − final_distance_m(조건 단계 끝 자리, placement.json). 두 조건 모두 계산한다
  (보기만 조건의 닻: static은 시작 자리, system_move는 목표 자리). 조건 단계가 끝까지 가지 않으면 빈칸.
- eye_object_distance_m = 확정 순간 머리–물체 3차원 거리의 본 라운드 평균.
- 설정 일치 점검에서 stopDistance.loop.plan(참여자 번호로 정한 출발 계획)은 사람마다 달라 비교에서 뺀다.

눈높이(G60-3, 2026-11-26 — manifest eyeHeight가 있는 세션)
- eyeHeight가 있는 세션이 하나라도 있을 때만 EYE_COLUMNS를 더한다. eye_height_m = eyeHeight.measuredM(E), eye_height_source =
  calibrated | desktop_fixed. final_height_rel_eye_m = final_height_m − E, final_height_ratio_eye = final_height_m / E,
  head_y_drift_m = 조건 단계 headpose head_y 중앙값 − E(웅크리기·까치발 점검). 키가 없는 옛 기록은 빈칸.

효과크기
- Cohen d = (평균A − 평균B) / 합동 표준편차(n−1 가중). Hedges g = J·d, J = 1 − 3/(4·df − 1), df = nA + nB − 2
  (소표본 보정). d의 95% 구간 ci95_normal_approx = d ± 1.96·√((nA+nB)/(nA·nB) + d²/(2(nA+nB)))
  (정규 근사, ci_method "normal_approx" — 소표본에서는 정확하지 않다). 집단당 n < 2이거나 합동 표준편차가 0이면
  d·g·구간은 null.
- 상관은 Pearson r(place 조건, 짝 n < 3이거나 한쪽 분산이 0이면 null).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from .ownership import _int, _num, _read_csv, _read_json, _rel, _r, _truthy, _write_csv, circular_range_deg
from .profile_items import rating_range
from .self_report import PI_FILE, PRE_FILE, session_columns

RECORD_PREFIX = "ifs-placement/"
# 0.2(2026-11-23): 러너가 selection.json(챗봇 후보·조절 단계, ifs-selection/0.1)을 읽어 manifest에 selection{…}·appliedOverrides를 더함.
# 그 밖의 파일·필드는 0.1과 같다. 실제 예시: docs/validation/runner-selection/records/
# 같은 0.2 안에서 더한 키(2026-11-23, G31·G32·G34 — ifs-selection/0.2): selection.skipped(선택 단계를 건너뜀), selection.colorChanged
# (색을 바꿨는지, 0.1 선택 파일이면 null). 출처 sources.form.type에 said_unrendered_chosen·said_unrendered_default가 올 수 있다.
# (CP10 G39) sources에 form.base·form.baseVariant(기본 형상과 그 변형값) — 열 form_base_source·form_variant_source.
# 변형값 키마다 낱말 뜻(lexicon_implied)·참여자 말(said)의 구분은 manifest에 없고 selection.json sourceDetails.form.baseVariant.keyBasis에
# 있다(manifest selection.sha256으로 짝지음).
# (G50 (4)) selection.safetyFlags(넷째 제외 범주 표시, 선택 파일에 있을 때만) — 열 safety_flag_categories(범주, ';'로 이음,
# 표시가 없으면 빈 문자열)·safety_form_blocked(형태를 막은 표시가 있는지). 키가 없는 기록 = 빈칸.
# (G52–G53, 2026-11-24) 배치 공간 후보 B·E·F: 공간 설정이 기본값이 아닐 때만 manifest environment{name, placementAssist, sky, practice}
# — 열 environment(키가 없으면 "neutral": G52 전 러너는 중립 공간만 있었다)·placement_assist(없으면 false). 연습이 있으면
# practice.json(본 결과와 따로) — 열 practice_error_m(연습 상자와 목표 자리 거리)·practice_ended_by(participant_confirm |
# experimenter | abort, 연습이 없으면 빈칸). 연습은 placement.json·objpose.csv에 들어가지 않고, headpose.csv phase practice는 머리 행동에서
# 빠진다(condition만 셈). 세션 사이 environment가 다르면 config_mismatch:environment.
# 없는 키는 빈칸으로 읽는다(이전 기록 그대로 읽힘).
# (G60-2·G60-3, 2026-11-26, 형식 0.2 유지 — 추가만) stopDistance.mode·loop{…, plan}과 stoprounds.csv·stopadjust.csv(loop일 때만),
# manifest eyeHeight{…}(relative일 때만). 위 「멈춤 거리 반복 멈춤」「눈높이」 절 참고.
KNOWN_VERSIONS = ("ifs-placement/0.1", "ifs-placement/0.2")
TRAJECTORY_PREFIX = "ifs-trajectory/"
SUMMARY_VERSION = "placement-summary/0.1"
DEFAULT_FACING_DEG = 15.0
DEFAULT_GAZE_DEG = DEFAULT_FACING_DEG   # 옛 이름(별칭)
RING_TOL_M = 0.1             # 고리 반지름에서 이 거리 안이면 "고리에 몰림"으로 센다
FINAL_TOL_M = 0.05           # placement.json 최종 거리와 objpose 마지막 행 거리의 허용 차
PATH_TOL_ABS_M = 0.05        # 궤적 길이 교차 점검 허용 차(절대)
PATH_TOL_REL = 0.05          # 〃(상대, 큰 값 기준)
Z95 = 1.959963984540054
CONDITIONS = ("place", "view")
DIRECTIONS = ("approach", "recede")
WHEN_ORDER = {"pre": 0, "post": 1, "check": 2}
# abortedAt이 이 단계들이면 조건 단계는 끝까지 갔다(옛 기록에서 condition_complete를 추정할 때)
PHASES_AFTER_CONDITION = ("post_items", "post_wait", "stop_distance", "check_items", "done")
# 세션 간 설정 일치 점검: (요약 키, manifest에서 값을 꺼내는 경로)
CONFIG_CHECK_KEYS = (("baselineSeconds", ("config", "baselineSeconds")),
                     ("conditionSeconds", ("config", "conditionSeconds")),
                     ("conditionEndsOnConfirm", ("config", "conditionEndsOnConfirm")),
                     ("space", ("space",)),
                     ("stopDistance", ("stopDistance",)),
                     ("environment", ("environment",)),
                     ("eyeHeightMode", ("config", "eyeHeightMode")))
EXPECTED_FILES = ("headpose.csv", "objpose.csv", "events.csv", "placement.json", "stopdistance.csv",
                  "ratings.csv", "trajectory.json", "summary.json")

SESSION_HEAD = [
    "participant", "session_id", "record_folder", "condition", "control_mode", "completed", "aborted_at",
    "condition_complete", "input_source", "head_source", "auto_mode", "draft_phrases", "object_radius_m",
    "selection_none", "selected_candidate_id", "n_final_overrides",
    "selection_skipped", "color_changed", "form_source", "form_base_source", "form_variant_source",
    "safety_flag_categories", "safety_form_blocked",
    "environment", "placement_assist", "practice_error_m", "practice_ended_by",
    "final_distance_m", "final_azimuth_deg", "final_height_m", "grab_count", "first_grab_ms", "held_ms",
    "path_length_m", "confirmed",
    "show_rings", "nearest_ring_m", "ring_offset_m",
    "stop_approach_mean_m", "stop_recede_mean_m", "stop_mean_m", "stop_n_valid", "stop_n_timeout", "stop_sd_m",
    "head_obj_distance_mean_m", "head_facing_ratio", "head_yaw_range_deg",
]
# condition_complete가 false면 비우는 조건 단계 지표
CONDITION_METRICS = ("final_distance_m", "final_azimuth_deg", "final_height_m", "grab_count", "first_grab_ms", "held_ms",
                     "path_length_m", "confirmed", "nearest_ring_m", "ring_offset_m",
                     "head_obj_distance_mean_m", "head_facing_ratio", "head_yaw_range_deg", "obj_path_from_objpose_m")
SESSION_TAIL = ["obj_path_from_objpose_m", "flags"]
STOP_COLUMNS = ["participant", "session_id", "condition", "control_mode", "completed", "trial", "practice",
                "direction", "start_distance_m", "speed_mps", "stop_distance_m", "rt_ms", "timed_out", "included"]
DESC_METRICS = ("final_distance_m", "final_height_m", "grab_count", "first_grab_ms", "held_ms", "path_length_m",
                "stop_approach_mean_m", "stop_recede_mean_m", "stop_mean_m", "stop_sd_m",
                "head_obj_distance_mean_m", "head_facing_ratio", "head_yaw_range_deg", "obj_path_from_objpose_m")
STOP_METRICS = ("stop_mean_m", "stop_approach_mean_m", "stop_recede_mean_m")

# G60-2 반복 멈춤(loop 세션이 하나라도 있을 때만 세션 표에 붙는 열)
LOOP_FILES = ("stoprounds.csv", "stopadjust.csv")
LOOP_MIN_CONFIRMED = 2           # 확정된 본 라운드가 이보다 적으면 stop_final_mean_m 빈칸
LOOP_DIR_WARN_M = 0.15           # 방향별 평균 차가 이보다 크면 요약 경고(히스테리시스)
LOOP_COLUMNS = ["stop_mode", "stop_final_mean_m", "stop_final_sd_m", "stop_final_n", "stop_n_unconfirmed",
                "stop_final_approach_mean_m", "stop_final_recede_mean_m", "stop_first_minus_final_mean_m",
                "stop_passes_mean", "stop_n_at_bound", "stop_minus_condition_final_m", "eye_object_distance_m"]
LOOP_ROUND_COLUMNS = ["participant", "session_id", "condition", "control_mode", "completed", "round", "practice", "start_dir",
                      "start_distance_m", "final_distance_m", "first_stop_distance_m", "last_stop_distance_m", "n_stops",
                      "n_resumes", "final_motion_dir", "passes_before_confirm", "stop_spread_m", "at_bound", "end_reason",
                      "duration_ms", "eye_object_distance_m", "included"]
LOOP_METRICS = ("stop_final_mean_m", "stop_final_approach_mean_m", "stop_final_recede_mean_m",
                "stop_first_minus_final_mean_m", "stop_minus_condition_final_m", "eye_object_distance_m")
# G60-3 눈높이(manifest eyeHeight가 있는 세션이 하나라도 있을 때만)
OBJECT_COLUMNS = ["object_width_m", "object_height_m", "object_depth_m", "proportions_x", "proportions_y", "proportions_z",
                  "proportions_source", "proportions_axis_said"]
EYE_COLUMNS = ["eye_height_m", "eye_height_source", "final_height_rel_eye_m", "final_height_ratio_eye", "head_y_drift_m"]
EYE_METRICS = ("eye_height_m", "final_height_rel_eye_m", "final_height_ratio_eye", "head_y_drift_m")


# ---------------------------------------------------------------- 계산 도우미

def norm_azimuth(a: float | None) -> float | None:
    """방위각을 (−180, 180]로."""
    if a is None:
        return None
    x = math.fmod(a + 180.0, 360.0)
    if x < 0:
        x += 360.0
    x -= 180.0
    return 180.0 if x == -180.0 else x


def yaw_deg(qx: float, qy: float, qz: float, qw: float) -> float | None:
    """쿼터니언이 정면(+z)을 돌린 방향의 수평 yaw(+z 기준, +x 쪽이 +). 정면이 거의 수직이면 None."""
    fx = 2.0 * (qx * qz + qw * qy)
    fz = 1.0 - 2.0 * (qx * qx + qy * qy)
    if math.hypot(fx, fz) < 1e-6:
        return None
    return math.degrees(math.atan2(fx, fz))


def nearest_ring(distance: float | None, radii: list[float]) -> tuple[float | None, float | None]:
    """→ (가장 가까운 고리 반지름, 거리 − 반지름). 같은 차이면 작은 반지름."""
    if distance is None or not radii:
        return None, None
    ring = min(radii, key=lambda r: (abs(distance - r), r))
    return ring, distance - ring


def describe(values) -> dict:
    """n·mean·sd(n−1)·min·max. 값이 없으면 n=0과 null, sd는 n ≥ 2일 때만."""
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if not n:
        return {"n": 0, "mean": None, "sd": None, "min": None, "max": None}
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1)) if n >= 2 else None
    return {"n": n, "mean": _r(mean), "sd": _r(sd), "min": _r(min(vals)), "max": _r(max(vals))}


def _sd(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def hedges_j(df: int) -> float | None:
    """Hedges 소표본 보정 J = 1 − 3/(4·df − 1). df < 1이면 None."""
    if df < 1:
        return None
    return 1.0 - 3.0 / (4.0 * df - 1.0)


def cohen_d(a, b) -> dict:
    """A − B의 Cohen d(합동 표준편차), Hedges g, d의 정규 근사 95% 구간(ci95_normal_approx).
    집단당 n < 2거나 합동 sd가 0이면 d·g·구간 null."""
    xa = [float(v) for v in a if v is not None]
    xb = [float(v) for v in b if v is not None]
    na, nb = len(xa), len(xb)
    ma = sum(xa) / na if na else None
    mb = sum(xb) / nb if nb else None
    out = {"nA": na, "nB": nb, "meanA": _r(ma), "meanB": _r(mb),
           "meanDiff": _r(ma - mb) if ma is not None and mb is not None else None,
           "sdPooled": None, "d": None, "hedges_g": None,
           "ci95_normal_approx": None, "ci_method": "normal_approx"}
    if na < 2 or nb < 2:
        return out
    sa, sb = _sd(xa), _sd(xb)
    sp = math.sqrt(((na - 1) * sa * sa + (nb - 1) * sb * sb) / (na + nb - 2))
    out["sdPooled"] = _r(sp)
    if sp == 0:
        return out
    d = (ma - mb) / sp
    se = math.sqrt((na + nb) / (na * nb) + d * d / (2 * (na + nb)))
    j = hedges_j(na + nb - 2)
    out.update({"d": _r(d), "hedges_g": _r(j * d) if j is not None else None,
                "ci95_normal_approx": {"low": _r(d - Z95 * se), "high": _r(d + Z95 * se)}})
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r. 짝이 3개 미만이거나 한쪽 분산이 0이면 None."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def _mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def _median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _xyz(row: dict, prefix: str) -> tuple[float, float, float] | None:
    v = [_num(row.get(f"{prefix}_{c}")) for c in ("x", "y", "z")]
    return None if any(x is None for x in v) else (v[0], v[1], v[2])


# ---------------------------------------------------------------- 기록 찾기

def discover(records: Path) -> tuple[list[dict], list[dict]]:
    """(participant, session)마다 기록 폴더 하나를 고른다. → (고른 것, 건너뛴 것)"""
    groups: dict[tuple[int, str], list[dict]] = {}
    skipped: list[dict] = []
    for mf in sorted(records.rglob("manifest.json")):
        folder = mf.parent
        rel = _rel(folder, records)
        man = _read_json(mf)
        if man is None:
            continue   # 읽을 수 없는 manifest는 어느 실험 것인지 모르므로 건드리지 않는다
        if not isinstance(man, dict) or not str(man.get("recordVersion", "")).startswith(RECORD_PREFIX):
            continue
        pnum, sid = _int(man.get("participantNumber")), man.get("sessionId")
        if pnum is None or not isinstance(sid, str) or not sid:
            skipped.append({"record": rel, "reason": "manifest_missing_ids"})
            continue
        summ = _read_json(folder / "summary.json")
        summ = summ if isinstance(summ, dict) else None
        groups.setdefault((pnum, sid), []).append({
            "folder": folder, "rel": rel, "manifest": man, "summary": summ,
            "completed": bool(summ) and summ.get("completed") is True,
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
    return chosen, skipped


# ---------------------------------------------------------------- 세션 하나

def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _condition_complete(pl: dict, summ: dict) -> bool:
    """조건 단계를 정해진 끝까지 마쳤나. placement.json conditionCompleted가 있으면 그것, 없으면 summary로 추정."""
    v = pl.get("conditionCompleted")
    if isinstance(v, bool):
        return v
    if summ.get("completed") is True:
        return True
    return summ.get("abortedAt") in PHASES_AFTER_CONDITION


def _path(d: dict, keys: tuple):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def load_session(cand: dict, facing_deg: float = DEFAULT_FACING_DEG) -> tuple[dict, dict, list[dict]]:
    """→ (세션 행, 평정 {열 이름: 값}, 멈춤 거리 시행 행 목록). 값은 파이썬 값(None = 빈칸)."""
    folder, rel, man = cand["folder"], cand["rel"], cand["manifest"]
    flags: list[str] = []

    for name in EXPECTED_FILES:
        p = folder / name
        if not p.is_file():
            flags.append(f"missing_file:{name}")
        elif p.stat().st_size == 0:
            flags.append(f"empty_file:{name}")

    def read_json(name: str) -> dict:
        p = folder / name
        if not p.is_file() or p.stat().st_size == 0:
            return {}
        data = _read_json(p)
        if not isinstance(data, dict):
            flags.append(f"unreadable_file:{name}")
            return {}
        return data

    if man.get("recordVersion") not in KNOWN_VERSIONS:
        flags.append("version_mismatch")
    summ = read_json("summary.json")
    pl = read_json("placement.json")
    practice_rec = read_json("practice.json")   # 배치 연습(G53) — 있을 때만. 본 결과 지표에는 쓰지 않는다
    traj = read_json("trajectory.json")
    if traj and not str(traj.get("version", "")).startswith(TRAJECTORY_PREFIX):
        flags.append("trajectory_version_mismatch")

    pnum, sid = _int(man.get("participantNumber")), man["sessionId"]
    condition, control = man.get("condition"), man.get("controlMode")
    if pl and ((pl.get("condition") is not None and pl.get("condition") != condition)
               or (pl.get("controlMode") is not None and pl.get("controlMode") != control)):
        flags.append("condition_mismatch")

    # 물체 자세(조건 단계)
    obj_rows = []
    for row in _read_csv(folder / "objpose.csv"):
        t = _num(row.get("time_ms"))
        if row.get("phase") == "condition" and t is not None:
            obj_rows.append((t, row))
    obj_rows.sort(key=lambda tr: tr[0])
    pos = [p for p in (_xyz(r, "obj") for _, r in obj_rows) if p is not None]
    obj_path = sum(math.dist(pos[i], pos[i + 1]) for i in range(len(pos) - 1)) if pos else None
    last_obj = obj_rows[-1][1] if obj_rows else None

    # 놓은 자리
    final_d, final_az, final_h = _num(pl.get("finalDistanceM")), _num(pl.get("finalAzimuthDeg")), _num(pl.get("finalHeightM"))
    if final_d is None and last_obj is not None:
        final_d = _num(last_obj.get("distance_m"))
        final_az = _num(last_obj.get("azimuth_deg"))
        final_h = _num(last_obj.get("height_m"))
        if final_d is not None:
            flags.append("final_from_objpose")
    elif final_d is not None and last_obj is not None:
        od = _num(last_obj.get("distance_m"))
        if od is not None and abs(od - final_d) > FINAL_TOL_M:
            flags.append("final_pose_mismatch")
    final_az = norm_azimuth(final_az)
    path_len = _num(pl.get("pathLengthM"))
    if obj_path is not None and path_len is not None:
        if abs(obj_path - path_len) > max(PATH_TOL_ABS_M, PATH_TOL_REL * max(obj_path, path_len)):
            flags.append("objpose_path_mismatch")

    # 고리
    space = _dict(man.get("space"))
    radii = [x for x in (_num(v) for v in space.get("ringRadiiM") or []) if x is not None]
    show = space.get("showRings") if isinstance(space.get("showRings"), bool) else None
    if show is None:
        flags.append("show_rings_unknown")
    ring, offset = nearest_ring(final_d, radii) if show else (None, None)

    # 멈춤 거리
    stop_rows: list[dict] = []
    by_dir: dict[str, list[float]] = {d: [] for d in DIRECTIONS}
    n_main: dict[str, int] = {d: 0 for d in DIRECTIONS}
    n_timeout = 0
    odd_dir = missing_val = False
    for row in _read_csv(folder / "stopdistance.csv"):
        practice, timed_out = _truthy(row.get("practice")), _truthy(row.get("timed_out"))
        direction, value = row.get("direction"), _num(row.get("stop_distance_m"))
        included = False
        if direction not in DIRECTIONS:
            odd_dir = True
        elif not practice:
            n_main[direction] += 1
            if timed_out:
                n_timeout += 1
            elif value is None:
                missing_val = True
            else:
                by_dir[direction].append(value)
                included = True
        stop_rows.append({"trial": _int(row.get("trial")), "practice": practice, "direction": direction,
                          "start_distance_m": _num(row.get("start_distance_m")), "speed_mps": _num(row.get("speed_mps")),
                          "stop_distance_m": value, "rt_ms": _num(row.get("rt_ms")), "timed_out": timed_out,
                          "included": included})
    if odd_dir:
        flags.append("stop_direction_unknown")
    if missing_val:
        flags.append("stop_value_missing")
    stop_cfg = _dict(man.get("stopDistance"))
    is_loop = stop_cfg.get("mode") == "loop"
    per_dir = _int(stop_cfg.get("trialsPerDirection"))
    if per_dir is not None and not is_loop:      # loop(G60-2)는 stopdistance.csv에 시행이 없다
        for d in DIRECTIONS:
            if n_main[d] < per_dir:
                flags.append(f"stop_trials_short:{d}")
    m_app, m_rec = _mean(by_dir["approach"]), _mean(by_dir["recede"])
    valid = by_dir["approach"] + by_dir["recede"]

    # 반복 멈춤(G60-2): stoprounds.csv
    loop_rows: list[dict] = []
    loop_vals: dict = {}
    if is_loop:
        for name in LOOP_FILES:
            p = folder / name
            if not p.is_file():
                flags.append(f"missing_file:{name}")
            elif p.stat().st_size == 0:
                flags.append(f"empty_file:{name}")
        finals, firsts_minus, passes, eye_d = [], [], [], []
        by_final_dir: dict[str, list[float]] = {d: [] for d in DIRECTIONS}
        n_unconfirmed = n_bound = 0
        for row in _read_csv(folder / "stoprounds.csv"):
            practice = _truthy(row.get("practice"))
            final = _num(row.get("final_distance_m"))
            confirmed = row.get("end_reason") == "confirmed" and final is not None
            included = confirmed and not practice
            if not practice:
                if not confirmed:
                    n_unconfirmed += 1
                else:
                    finals.append(final)
                    fdir = row.get("final_motion_dir")
                    if fdir in by_final_dir:
                        by_final_dir[fdir].append(final)
                    first = _num(row.get("first_stop_distance_m"))
                    if first is not None:
                        firsts_minus.append(first - final)
                    pz = _num(row.get("passes_before_confirm"))
                    if pz is not None:
                        passes.append(pz)
                    if _truthy(row.get("at_bound")):
                        n_bound += 1
                    ed = _num(row.get("eye_object_distance_m"))
                    if ed is not None:
                        eye_d.append(ed)
            loop_rows.append({
                "round": _int(row.get("round")), "practice": practice, "start_dir": row.get("start_dir") or None,
                "start_distance_m": _num(row.get("start_distance_m")), "final_distance_m": final,
                "first_stop_distance_m": _num(row.get("first_stop_distance_m")),
                "last_stop_distance_m": _num(row.get("last_stop_distance_m")),
                "n_stops": _int(row.get("n_stops")), "n_resumes": _int(row.get("n_resumes")),
                "final_motion_dir": row.get("final_motion_dir") or None,
                "passes_before_confirm": _int(row.get("passes_before_confirm")),
                "stop_spread_m": _num(row.get("stop_spread_m")),
                "at_bound": _truthy(row.get("at_bound")) if row.get("at_bound") else None,
                "end_reason": row.get("end_reason") or None, "duration_ms": _num(row.get("duration_ms")),
                "eye_object_distance_m": _num(row.get("eye_object_distance_m")), "included": included})
        rounds_cfg = _int(_dict(stop_cfg.get("loop")).get("rounds"))
        n_main_rounds = sum(1 for r in loop_rows if not r["practice"])
        if rounds_cfg is not None and n_main_rounds < rounds_cfg:
            flags.append("stop_rounds_short")
        if n_unconfirmed:
            flags.append(f"stop_unconfirmed:{n_unconfirmed}")
        mean_final = _mean(finals) if len(finals) >= LOOP_MIN_CONFIRMED else None
        loop_vals = {
            "stop_final_mean_m": mean_final, "stop_final_sd_m": _sd(finals), "stop_final_n": len(finals),
            "stop_n_unconfirmed": n_unconfirmed,
            "stop_final_approach_mean_m": _mean(by_final_dir["approach"]),
            "stop_final_recede_mean_m": _mean(by_final_dir["recede"]),
            "stop_first_minus_final_mean_m": _mean(firsts_minus), "stop_passes_mean": _mean(passes),
            "stop_n_at_bound": n_bound, "eye_object_distance_m": _mean(eye_d),
        }

    # 눈높이(G60-3): manifest eyeHeight
    eye_block = _dict(man.get("eyeHeight"))
    eye_h = _num(eye_block.get("measuredM"))

    # 머리 행동(조건 단계)
    angles, dists, yaws, head_ys = [], [], [], []
    for row in _read_csv(folder / "headpose.csv"):
        if row.get("phase") != "condition":
            continue
        hy = _num(row.get("head_y"))
        if hy is not None:
            head_ys.append(hy)
        a, dist = _num(row.get("angle_deg")), _num(row.get("distance_m"))
        if a is not None:
            angles.append(a)
        if dist is not None:
            dists.append(dist)
        q = [_num(row.get(f"head_q{c}")) for c in ("x", "y", "z", "w")]
        if all(v is not None for v in q):
            y = yaw_deg(*q)
            if y is not None:
                yaws.append(y)

    # 평정
    ratings: dict[str, float | None] = {}
    out_of_range = False
    for row in _read_csv(folder / "ratings.csv"):
        item, when = row.get("item"), row.get("when")
        if not item or not when:
            continue
        r = _num(row.get("rating"))
        lo, hi = rating_range(item)   # 러너 기본 1–7, 구별 프로파일 0–10 문항(M1p·M2·M3)만 0–10
        if r is not None and not lo <= r <= hi:
            out_of_range = True
        ratings[f"rating_{item}_{when}"] = r
    if out_of_range:
        flags.append("rating_out_of_range")

    n_warn = sum(1 for row in _read_csv(folder / "events.csv") if row.get("event") == "warning")
    if n_warn:
        flags.append(f"runner_warning:{n_warn}")

    participant = f"P{pnum:03d}"
    completed = summ.get("completed") is True
    cond_complete = _condition_complete(pl, summ)
    if not cond_complete:
        flags.append("partial_condition")
    radius = _num(_dict(man.get("object")).get("boundingRadiusM"))
    bounds = _dict(_dict(man.get("object")).get("boundsM"))
    props = _dict(_dict(man.get("object")).get("proportions"))
    sel = _dict(man.get("selection"))
    srow = {
        "participant": participant, "session_id": sid, "record_folder": rel,
        "condition": condition, "control_mode": control,
        "completed": completed, "aborted_at": summ.get("abortedAt"),
        "condition_complete": cond_complete,
        "input_source": man.get("inputSource"), "head_source": man.get("headSource"),
        "auto_mode": _dict(man.get("flags")).get("autoMode") is True,
        "draft_phrases": _int(_dict(man.get("taskText")).get("draftCount")),
        "object_radius_m": _r(radius),
        # ifs-placement/0.2 manifest selection{…}(챗봇 selection.json에서 온 것). 0.1이나 선택 파일 없이 돈 세션은 빈칸
        "selection_none": sel.get("none") if isinstance(sel.get("none"), bool) else None,
        "selected_candidate_id": sel.get("selectedCandidateId") if sel else None,
        "n_final_overrides": len(sel["finalOverrides"]) if isinstance(sel.get("finalOverrides"), dict) else None,
        # G34: 선택 단계 건너뜀(skipped 키가 없는 기록 = 빈칸), G31: 색을 바꿨는지, G32: 형태 자리 출처(said_unrendered_* 구분)
        "selection_skipped": sel.get("skipped") if isinstance(sel.get("skipped"), bool) else None,
        "color_changed": sel.get("colorChanged") if isinstance(sel.get("colorChanged"), bool) else None,
        "form_source": (sel.get("sources") or {}).get("form.type") if isinstance(sel.get("sources"), dict) else None,
        # CP10 G39: 기본 형상·변형값 출처(키가 없는 기록 = 빈칸)
        "form_base_source": (sel.get("sources") or {}).get("form.base") if isinstance(sel.get("sources"), dict) else None,
        "form_variant_source": ((sel.get("sources") or {}).get("form.baseVariant")
                                if isinstance(sel.get("sources"), dict) else None),
        # G50 (4): 넷째 제외 범주 표시(키가 없는 기록 = 빈칸)
        "safety_flag_categories": (";".join(sorted({str(f.get("category")) for f in sel["safetyFlags"] if isinstance(f, dict)}))
                                   if isinstance(sel.get("safetyFlags"), list) else None),
        "safety_form_blocked": (any(isinstance(f, dict) and f.get("formBlock") is True for f in sel["safetyFlags"])
                                if isinstance(sel.get("safetyFlags"), list) else None),
        # G52–G53: 공간·놓기 도움(키가 없는 기록 = 중립·도움 없음 — 그 러너에는 다른 공간이 없었다), 배치 연습(있을 때만)
        "environment": str(_dict(man.get("environment")).get("name") or "neutral"),
        "placement_assist": _dict(man.get("environment")).get("placementAssist") is True,
        "practice_error_m": _r(_num(practice_rec.get("errorM"))),
        "practice_ended_by": practice_rec.get("endedBy") if isinstance(practice_rec.get("endedBy"), str) else None,
        "final_distance_m": _r(final_d), "final_azimuth_deg": _r(final_az), "final_height_m": _r(final_h),
        "grab_count": _int(pl.get("grabCount")), "first_grab_ms": _num(pl.get("firstGrabMs")),
        "held_ms": _num(pl.get("heldMs")), "path_length_m": _r(path_len),
        "confirmed": pl.get("confirmed") if isinstance(pl.get("confirmed"), bool) else None,
        "show_rings": show, "nearest_ring_m": ring, "ring_offset_m": _r(offset),
        "stop_approach_mean_m": _r(m_app), "stop_recede_mean_m": _r(m_rec),
        "stop_mean_m": _r((m_app + m_rec) / 2) if m_app is not None and m_rec is not None else None,
        "stop_n_valid": len(valid), "stop_n_timeout": n_timeout, "stop_sd_m": _r(_sd(valid)),
        "head_obj_distance_mean_m": _r(_mean(dists)),
        "head_facing_ratio": _r(sum(1 for a in angles if a <= facing_deg) / len(angles)) if angles else None,
        "head_yaw_range_deg": _r(circular_range_deg(yaws), 3),
        "obj_path_from_objpose_m": _r(obj_path),
        "flags": ";".join(flags),
        "_space": space,
        "_manifest": man,
        "_loop_rounds": loop_rows,
        "_has_loop": is_loop,
        "_has_eye": bool(eye_block),
        "_has_object": bool(bounds or props),
        # G72: 물체 크기·모양 공변량(RQ2)
        "object_width_m": _r(_num(bounds.get("x"))), "object_height_m": _r(_num(bounds.get("y"))),
        "object_depth_m": _r(_num(bounds.get("z"))),
        "proportions_x": _r(_num(props.get("x"))), "proportions_y": _r(_num(props.get("y"))),
        "proportions_z": _r(_num(props.get("z"))),
        "proportions_source": props.get("source") if isinstance(props.get("source"), str) else None,
        "proportions_axis_said": props.get("axisSaid") if isinstance(props.get("axisSaid"), bool) else None,
    }
    # G60-2 반복 멈춤 열(loop 세션이 하나라도 있을 때만 표에 나간다 — analyze가 정함)
    srow["stop_mode"] = "loop" if is_loop else "single"
    for k in LOOP_COLUMNS[1:]:
        v = loop_vals.get(k)
        srow[k] = _r(v) if isinstance(v, float) else v
    # G60-3 눈높이 열(eyeHeight가 있는 세션이 하나라도 있을 때만)
    srow["eye_height_m"] = _r(eye_h)
    srow["eye_height_source"] = eye_block.get("source") if isinstance(eye_block.get("source"), str) else None
    srow["final_height_rel_eye_m"] = _r(final_h - eye_h) if final_h is not None and eye_h else None
    srow["final_height_ratio_eye"] = _r(final_h / eye_h) if final_h is not None and eye_h else None
    hm = _median(head_ys)
    srow["head_y_drift_m"] = _r(hm - eye_h) if hm is not None and eye_h else None
    if not cond_complete:
        for k in CONDITION_METRICS + ("final_height_rel_eye_m", "final_height_ratio_eye", "head_y_drift_m"):
            srow[k] = None     # 중단된 조건 단계: 완료 자료처럼 보이지 않게 비운다(원자료 파일은 그대로)
    # 닻 지표: 확정 멈춤 거리 평균 − 조건 단계 끝 자리(두 조건 모두)
    sfm, fdm = srow.get("stop_final_mean_m"), srow.get("final_distance_m")
    srow["stop_minus_condition_final_m"] = _r(sfm - fdm) if is_loop and sfm is not None and fdm is not None else None
    ident = {"participant": participant, "session_id": sid, "condition": condition, "control_mode": control,
             "completed": completed}
    return srow, ratings, [{**ident, **r} for r in stop_rows]


# ---------------------------------------------------------------- 요약

def _rating_sort_key(col: str) -> tuple:
    item, _, when = col[len("rating_"):].rpartition("_")
    return (item, WHEN_ORDER.get(when, 9), when)


def _group_key(s: dict) -> str:
    return f"{s['condition']}/{s['control_mode']}"


def _count(sessions: list[dict], key) -> dict:
    out: dict[str, int] = {}
    for s in sessions:
        k = str(key(s))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def _uniform_ring_share(space: dict, tol: float) -> float | None:
    """놓은 거리가 0–floorRadiusM에 고르게 퍼졌다면 고리 ±tol 안에 들어갈 비율(참고값)."""
    rmax = _num(space.get("floorRadiusM"))
    radii = sorted({x for x in (_num(v) for v in space.get("ringRadiiM") or []) if x is not None})
    if not rmax or rmax <= 0 or not radii:
        return None
    covered, lo_prev = 0.0, 0.0
    for r in radii:                      # 구간 [r − tol, r + tol]의 합집합 ∩ [0, rmax]
        lo, hi = max(0.0, r - tol, lo_prev), min(rmax, r + tol)
        if hi > lo:
            covered += hi - lo
            lo_prev = hi
    return covered / rmax


def summarize(included: list[dict], rating_cols: list[str]) -> dict:
    metrics = list(DESC_METRICS) + rating_cols
    by_cond = {c: [s for s in included if s["condition"] == c] for c in CONDITIONS}
    for s in included:
        if s["condition"] not in by_cond:
            by_cond[str(s["condition"])] = [x for x in included if x["condition"] == s["condition"]]
    by_group: dict[str, list[dict]] = {}
    for s in included:
        by_group.setdefault(_group_key(s), []).append(s)

    def desc(rows):
        return {m: describe(s.get(m) for s in rows) for m in metrics}

    def diff(s):
        a, r = s["stop_approach_mean_m"], s["stop_recede_mean_m"]
        return None if a is None or r is None else a - r

    direction = {"definition": "세션별 stop_approach_mean_m − stop_recede_mean_m",
                 "all": describe(diff(s) for s in included),
                 "byCondition": {c: describe(diff(s) for s in rows) for c, rows in by_cond.items()}}

    place, view = by_cond.get("place", []), by_cond.get("view", [])
    view_modes = sorted({str(s["control_mode"]) for s in view})
    effect: dict = {"definition": "A − B, A = place. d = 평균 차 / 합동 sd(n−1), hedges_g = J·d (J = 1 − 3/(4·df − 1)), "
                                  "ci95_normal_approx = d의 정규 근사 95% 구간(소표본에서 부정확)"}
    for m in STOP_METRICS:
        e = {"place_vs_view": cohen_d([s[m] for s in place], [s[m] for s in view])}
        for mode in view_modes:
            e[f"place_vs_view_{mode}"] = cohen_d([s[m] for s in place],
                                                 [s[m] for s in view if str(s["control_mode"]) == mode])
        effect[m] = e

    corr = {}
    for m in STOP_METRICS:
        pairs = [(s["final_distance_m"], s[m]) for s in place
                 if s["final_distance_m"] is not None and s[m] is not None]
        r = pearson([p[0] for p in pairs], [p[1] for p in pairs])
        corr[f"final_distance_m~{m}"] = {"n": len(pairs), "r": _r(r)}

    ringed = [s for s in place if s["ring_offset_m"] is not None]
    within = sum(1 for s in ringed if abs(s["ring_offset_m"]) <= RING_TOL_M + 1e-9)
    shares = [x for x in (_uniform_ring_share(s["_space"], RING_TOL_M) for s in ringed) if x is not None]
    ring = {"toleranceM": RING_TOL_M, "condition": "place",
            "nWithRings": len(ringed), "nWithin": within,
            "proportionWithin": _r(within / len(ringed)) if ringed else None,
            "nRingsHidden": sum(1 for s in place if s["show_rings"] is False),
            "uniformReference": _r(_mean(shares)),
            "uniformReferenceNote": "놓은 거리가 0–floorRadiusM에 고르게 퍼졌을 때 기대 비율(참고값, 검정 아님)"}

    return {
        "byCondition": {c: {"n": len(rows), **desc(rows)} for c, rows in by_cond.items()},
        "byConditionControl": {g: {"n": len(rows), **desc(rows)} for g, rows in sorted(by_group.items())},
        "stopDirectionEffect": direction,
        "stopConditionEffect": effect,
        "placeDistanceStopCorrelation": corr,
        "ringClustering": ring,
    }


# ---------------------------------------------------------------- 전체 실행

def config_mismatches(sessions: list[dict]) -> dict[str, list]:
    """세션들 사이에서 값이 다른 설정 키 → 서로 다른 값 목록(정렬, JSON 문자열 기준). 같으면 빠진다."""
    out: dict[str, list] = {}
    for key, path in CONFIG_CHECK_KEYS:
        seen: dict[str, object] = {}
        for s in sessions:
            v = _path(s.get("_manifest") or {}, path)
            if key == "stopDistance" and isinstance(v, dict) and isinstance(v.get("loop"), dict) and "plan" in v["loop"]:
                # G60-2: 출발 계획은 참여자 번호로 정해 사람마다 다르다 — 설정 비교에서 뺀다
                v = {**v, "loop": {k: x for k, x in v["loop"].items() if k != "plan"}}
            seen.setdefault(json.dumps(v, sort_keys=True, ensure_ascii=False), v)
        if len(seen) > 1:
            out[key] = [seen[k] for k in sorted(seen)]
    return out


def analyze(records: str | Path, out_dir: str | Path | None = None, facing_deg: float = DEFAULT_FACING_DEG,
            gaze_deg: float | None = None, selection_dir: str | Path | None = None) -> dict:
    """gaze_deg는 facing_deg의 옛 이름(별칭). 둘 다 주면 gaze_deg를 쓴다.
    selection_dir(선택, G59): 챗봇 세션 폴더 뿌리(chatbot/logs/selection). 기록 폴더나 그 아래 <sessionId>/에
    premeasure.json·postinterview.json이 있으면 pre_*·pi_* 열을 더한다(eval/self_report.py). 하나도 없으면 출력은 그대로."""
    if gaze_deg is not None:
        facing_deg = gaze_deg
    root = Path(records)
    if not root.exists():
        raise FileNotFoundError(f"기록 경로가 없습니다: {records}")
    sel_root = Path(selection_dir) if selection_dir is not None else None
    chosen, skipped = discover(root)
    sessions, stops, rating_map, self_map = [], [], [], []
    self_numeric: set[str] = set()
    self_files = {PRE_FILE: 0, PI_FILE: 0}
    for cand in chosen:
        srow, ratings, rows = load_session(cand, facing_deg)
        cols, sflags, numeric, found = session_columns(cand["folder"], srow["session_id"], srow["condition"],
                                                       srow["control_mode"], sel_root)
        if sflags:
            srow["flags"] = ";".join(x for x in (srow["flags"], *sflags) if x)
        self_numeric |= numeric
        for k, v in found.items():
            self_files[k] += int(v)
        sessions.append(srow)
        rating_map.append(ratings)
        self_map.append(cols)
        stops.extend(rows)
    rating_cols = sorted({k for r in rating_map for k in r}, key=_rating_sort_key)
    self_cols: list[str] = []                     # 처음 나온 순서(세션 순서 → 파일 안 문항 순서), 결정론적
    for cols in self_map:
        self_cols.extend(k for k in cols if k not in self_cols)
    for s, r, sc in zip(sessions, rating_map, self_map):
        for c in rating_cols:
            s[c] = r.get(c)
        for c in self_cols:
            s[c] = sc.get(c)
    included = [s for s in sessions if s["completed"] and s["condition_complete"]]
    incomplete = [s for s in sessions if not s["completed"]]
    partial = [s for s in sessions if s["completed"] and not s["condition_complete"]]

    warnings: list[str] = []
    if incomplete:
        warnings.append(f"미완료 세션 {len(incomplete)}개는 요약 통계에서 뺌("
                        + ", ".join(f"{s['participant']}/{s['session_id']}" for s in incomplete) + ")")
    if partial:
        warnings.append(f"조건 단계가 끝까지 가지 않은 세션 {len(partial)}개(partial_condition)는 요약 통계에서 뺌("
                        + ", ".join(f"{s['participant']}/{s['session_id']}" for s in partial) + ")")
    mismatch = config_mismatches(included)
    for key in mismatch:
        warnings.append(f"config_mismatch:{key}")
    drafted = [s for s in sessions if (s["draft_phrases"] or 0) > 0]
    if drafted:
        warnings.append(f"초안 문구: 세션 {len(drafted)}개가 status draft 문구로 수집됨 — IRB 확인 전 문구라 본 실험 자료로 쓰기 전에 확인")
    auto = [s for s in sessions if s["auto_mode"]]
    if auto:
        warnings.append(f"자동 시행(autoMode) 세션 {len(auto)}개 — 참여자 자료가 아님")
    flagged = [s for s in sessions if s["flags"]]
    if flagged:
        warnings.append(f"flags가 있는 세션 {len(flagged)}개 — placement_sessions.csv의 flags 열 확인")
    unknown = sorted({str(s["condition"]) for s in sessions if s["condition"] not in CONDITIONS})
    if unknown:
        warnings.append("계약에 없는 condition 값: " + ", ".join(unknown))
    for c in CONDITIONS:
        n = sum(1 for s in included if s["condition"] == c)
        if n < 2:
            warnings.append(f"{c} 조건 완료 세션이 {n}개 — 이 조건이 들어가는 효과크기는 null")

    summary = {
        "version": SUMMARY_VERSION,
        "tool": "ifs_chatbot.eval.placement",
        "descriptiveOnly": True,
        "note": "기술 통계와 효과크기 추정만 낸다. 거리 지표는 '고른 거리'이며 심리적 거리의 측정이라고 해석하지 않는다. "
                "거리는 모두 물체 중심 기준이다(보이는 가장자리까지는 object_radius_m만큼 짧다). "
                "head_facing_ratio는 눈 추적이 아니라 머리 정면 방향 기준 대리 지표다(시선 지표가 아님). "
                "효과크기 구간은 정규 근사(ci_method normal_approx)라 소표본에서 부정확하다.",
        "facingDeg": facing_deg,
        "recordVersions": sorted({str(c["manifest"].get("recordVersion")) for c in chosen}),
        "records": {"sessions": len(sessions), "included": len(included),
                    "excludedIncomplete": len(incomplete), "excludedPartialCondition": len(partial),
                    "skipped": len(skipped)},
        "configMismatch": mismatch,
        "nByConditionControl": {"all": _count(sessions, _group_key), "included": _count(included, _group_key)},
        "draftPhraseSessions": len(drafted),
        "autoModeSessions": len(auto),
        "summaries": summarize(included, rating_cols + [c for c in self_cols if c in self_numeric]),
        "skipped": skipped,
        "warnings": warnings,
    }
    if self_cols:
        # 파일이 있을 때만 붙는 키(없으면 요약 JSON이 그대로)
        summary["selfReport"] = {
            "files": {"premeasure": self_files[PRE_FILE], "postinterview": self_files[PI_FILE]},
            "columns": self_cols,
            "note": "사전 측정(pre_*)·사후 면담(pi_*) 열. 사후 면담 자유 글은 표에 넣지 않고 글자 수(_chars)·건너뜀(_skipped)만 "
                    "적는다. 모든 문구는 초안(draft, IRB 검토 전)이다(G59).",
        }
    # G60-2·G60-3: 해당 세션이 하나라도 있을 때만 붙는 열(없으면 출력이 G60 전과 같다)
    has_loop = any(s["_has_loop"] for s in sessions)
    has_eye = any(s["_has_eye"] for s in sessions)
    has_object = any(s["_has_object"] for s in sessions)      # G72: 경계 상자·비율이 있는 기록이 하나라도 있을 때만
    extra_cols = (LOOP_COLUMNS if has_loop else []) + (EYE_COLUMNS if has_eye else []) + (OBJECT_COLUMNS if has_object else [])
    loop_rounds: list[dict] = []
    for s in sessions:
        ident = {"participant": s["participant"], "session_id": s["session_id"], "condition": s["condition"],
                 "control_mode": s["control_mode"], "completed": s["completed"]}
        loop_rounds.extend({**ident, **r} for r in s["_loop_rounds"])
        if not has_loop:
            for k in LOOP_COLUMNS:
                s.pop(k, None)
        if not has_eye:
            for k in EYE_COLUMNS:
                s.pop(k, None)
        if not has_object:
            for k in OBJECT_COLUMNS:
                s.pop(k, None)
    if has_loop:
        summary["stopLoop"] = loop_summary(included, loop_rounds)
        summary["warnings"].extend(summary["stopLoop"]["warnings"])
    if has_eye:
        summary["eyeHeight"] = eye_summary(included)
    columns = SESSION_HEAD + extra_cols + rating_cols + self_cols + SESSION_TAIL
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_csv(out / "placement_sessions.csv", columns, sessions)
        _write_csv(out / "stop_trials.csv", STOP_COLUMNS, stops)
        if has_loop:
            _write_csv(out / "stop_loop_rounds.csv", LOOP_ROUND_COLUMNS, loop_rounds)
        (out / "placement_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    for s in sessions:
        for k in ("_space", "_manifest", "_loop_rounds", "_has_loop", "_has_eye", "_has_object"):
            s.pop(k, None)
    res = {"sessions": sessions, "stop_trials": stops, "summary": summary, "columns": columns}
    if has_loop:
        res["stop_loop_rounds"] = loop_rounds
    return res


def loop_summary(included: list[dict], rounds: list[dict]) -> dict:
    """G60-2 반복 멈춤 요약(loop 세션만). 기술 통계·효과크기·상관만 — 유의성 판정은 내지 않는다."""
    loop = [s for s in included if s.get("stop_mode") == "loop"]
    by_cond = {c: [s for s in loop if s["condition"] == c] for c in CONDITIONS}

    def dir_diff(s):
        a, r = s.get("stop_final_approach_mean_m"), s.get("stop_final_recede_mean_m")
        return None if a is None or r is None else a - r

    diffs = [d for d in (dir_diff(s) for s in loop) if d is not None]
    warnings: list[str] = []
    mean_abs = _mean([abs(d) for d in diffs])
    if mean_abs is not None and mean_abs > LOOP_DIR_WARN_M:
        warnings.append(f"stop_loop_direction_gap: 마지막 진행 방향별 확정 거리 차의 평균 절댓값 {mean_abs:.3f} m > {LOOP_DIR_WARN_M} m"
                        " — 지나친 자리를 받아들이는 편향(히스테리시스) 확인")
    place, view = by_cond.get("place", []), by_cond.get("view", [])
    corr_pairs = [(s["final_distance_m"], s["stop_final_mean_m"]) for s in place
                  if s.get("final_distance_m") is not None and s.get("stop_final_mean_m") is not None]
    main_rounds = [r for r in rounds if not r["practice"]]
    reasons: dict[str, int] = {}
    for r in main_rounds:
        reasons[str(r["end_reason"])] = reasons.get(str(r["end_reason"]), 0) + 1
    return {
        "definition": "stop_final_mean_m = 본 라운드 가운데 확정(confirmed) 라운드의 final_distance_m 평균(확정 라운드 "
                      f"{LOOP_MIN_CONFIRMED}개 미만이면 빈칸). 확정하지 않은 라운드는 결측(마지막 멈춤 거리로 채우지 않음). "
                      "stop_minus_condition_final_m = stop_final_mean_m − 조건 단계 끝 자리(두 조건 모두, 닻 지표).",
        "nSessions": len(loop),
        "byCondition": {c: {"n": len(rows), **{m: describe(s.get(m) for s in rows) for m in LOOP_METRICS}}
                        for c, rows in by_cond.items()},
        "directionDiff": {"definition": "세션별 stop_final_approach_mean_m − stop_final_recede_mean_m(마지막 진행 방향별)",
                          "all": describe(diffs), "meanAbs": _r(mean_abs), "warnAboveM": LOOP_DIR_WARN_M},
        "conditionEffect": {m: cohen_d([s.get(m) for s in place], [s.get(m) for s in view])
                            for m in ("stop_final_mean_m", "stop_minus_condition_final_m")},
        "placeDistanceStopCorrelation": {"final_distance_m~stop_final_mean_m": {"n": len(corr_pairs), "r": _r(
            pearson([p[0] for p in corr_pairs], [p[1] for p in corr_pairs]))}},
        "rounds": {"main": len(main_rounds), "endReasons": dict(sorted(reasons.items())),
                   "unconfirmed": sum(1 for r in main_rounds if r["end_reason"] != "confirmed")},
        "note": "직접 배치에서 놓은 거리와 멈춤 거리의 상관은 '같은 선호의 반복'과 '방금 놓은 거리 기억 맞추기'를 가를 수 없다"
                "(docs/codex-reviews/D7_claude.md A4). 보기만 조건의 닻(시작·목표 자리)과 함께 stop_minus_condition_final_m으로 본다.",
        "warnings": warnings,
    }


def eye_summary(included: list[dict]) -> dict:
    """G60-3 눈높이 요약(eyeHeight가 있는 세션만)."""
    eye = [s for s in included if s.get("eye_height_m") is not None]
    sources: dict[str, int] = {}
    for s in eye:
        sources[str(s.get("eye_height_source"))] = sources.get(str(s.get("eye_height_source")), 0) + 1
    return {
        "definition": "eye_height_m = manifest eyeHeight.measuredM(E). final_height_rel_eye_m = 놓은 높이 − E, "
                      "final_height_ratio_eye = 놓은 높이 / E, head_y_drift_m = 조건 단계 head_y 중앙값 − E.",
        "nSessions": len(eye),
        "sources": dict(sorted(sources.items())),
        "byCondition": {c: {"n": sum(1 for s in eye if s["condition"] == c),
                            **{m: describe(s.get(m) for s in eye if s["condition"] == c) for m in EYE_METRICS}}
                        for c in CONDITIONS},
    }


def _print_summary(summary: dict) -> None:
    rec = summary["records"]
    print(f"세션 {rec['sessions']}개(요약 포함 {rec['included']}, 미완료 제외 {rec['excludedIncomplete']}, "
          f"건너뛴 폴더 {rec['skipped']}) · 경고 {len(summary['warnings'])}")
    for g, n in summary["nByConditionControl"]["included"].items():
        print(f"  {g}: {n}")
    for c, d in summary["summaries"]["byCondition"].items():
        fd, sm = d["final_distance_m"], d["stop_mean_m"]
        print(f"  {c:<5} 놓은 거리 평균 {fd['mean']} (n={fd['n']})  멈춤 거리 평균 {sm['mean']} (n={sm['n']})")


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.placement", description="배치 실험(RQ V4) 기록 요약(기술 통계)")
    ap.add_argument("--records", required=True, help="기록 루트(placement/P###/... 위) 또는 그 아래 아무 폴더")
    ap.add_argument("--out", required=True, help="결과 폴더(placement_sessions.csv, stop_trials.csv, placement_summary.json)")
    ap.add_argument("--facing-deg", "--gaze-deg", dest="facing_deg", type=float, default=DEFAULT_FACING_DEG,
                    help=f"head_facing_ratio로 셀 머리 정면–물체 방향 최대 각(기본 {DEFAULT_FACING_DEG:g}°). "
                         "눈 추적이 아니라 머리 방향 기준. --gaze-deg는 옛 이름(별칭)")
    ap.add_argument("--selection-dir", default=None,
                    help="(선택, G59) 챗봇 세션 폴더 뿌리(보통 chatbot/logs/selection). <sessionId>/premeasure.json·"
                         "postinterview.json이 있으면 pre_*·pi_* 열을 더한다(자유 글은 글자 수·건너뜀만). 기록 폴더 안의 같은 "
                         "이름 파일은 이 인자 없이도 읽는다")
    args = ap.parse_args(argv)
    if not Path(args.records).exists():
        ap.error(f"--records 경로가 없습니다: {args.records}")
    res = analyze(args.records, args.out, args.facing_deg, selection_dir=args.selection_dir)
    _print_summary(res["summary"])
    print(f"결과: {Path(args.out) / 'placement_summary.json'}")


if __name__ == "__main__":
    main()
