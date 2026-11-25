"""배치 기록 요약(placement.py)에 붙이는 데스크톱 자기보고 열 — 사전 측정(premeasure.json)과 사후 면담(postinterview.json)(G59).
LLM 없음, 표준 라이브러리만, 결정론적. 파일이 없으면 아무 열도 더하지 않는다(placement 출력이 바이트까지 그대로).

파일 찾는 곳(세션마다, 먼저 찾은 것):
  1) 배치 기록 폴더 안(연구자가 옮겨 둔 경우) <기록 폴더>/premeasure.json · postinterview.json
  2) --selection-dir(챗봇 세션 폴더의 뿌리, 보통 chatbot/logs/selection) 아래 <sessionId>/premeasure.json · postinterview.json
     — manifest의 sessionId와 챗봇 세션 ID가 같다고 본다(장면 파일 이름 = 세션 ID).

열
- pre_protocol_version, pre_{문항 id}(1–7 또는 빈칸 = 답하지 않음). 범위 밖 값은 빈칸 + flag premeasure_out_of_range.
- pi_condition, pi_protocol_version, pi_completed(뒤 부분까지 저장했는지)
- 사후 면담 항목: 평정(value) → pi_{id}, 선택(choice) → pi_{id}(선택지 id), 글(text) → pi_{id}_chars(글자 수, 건너뜀이면 빈칸)
  ·pi_{id}_skipped. 되묻기(PI3) 회차는 id 뒤에 _r{회차}. **자유 글 자체는 표에 넣지 않는다.**
- flags: unreadable_file:premeasure.json / unreadable_file:postinterview.json, premeasure_version_mismatch,
  postinterview_version_mismatch, premeasure_session_mismatch / postinterview_session_mismatch(파일의 sessionId가 다름),
  pi_condition_mismatch(사후 면담 조건이 배치 기록의 조건과 다름. 기대 조건 = controlMode가 point_select면 point_select,
  아니면 condition).
"""
from __future__ import annotations

from pathlib import Path

from .ownership import _read_json

PRE_FILE, PI_FILE = "premeasure.json", "postinterview.json"
PRE_PREFIX, PI_PREFIX = "ifs-premeasure/", "ifs-postinterview/"
PRE_RANGE = (1, 7)


def find_files(folder: Path, session_id: str, selection_root: Path | None) -> dict[str, Path | None]:
    out: dict[str, Path | None] = {}
    for name in (PRE_FILE, PI_FILE):
        p = folder / name
        if not p.is_file() and selection_root is not None and session_id:
            q = Path(selection_root) / session_id / name
            p = q if q.is_file() else p
        out[name] = p if p.is_file() else None
    return out


def _int_or_none(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def premeasure_columns(path: Path, session_id: str) -> tuple[dict, list[str], set[str]]:
    """→ (열, flags, 숫자 열 이름들)."""
    data = _read_json(path)
    if not isinstance(data, dict):
        return {}, [f"unreadable_file:{PRE_FILE}"], set()
    flags = []
    if not str(data.get("formatVersion", "")).startswith(PRE_PREFIX):
        flags.append("premeasure_version_mismatch")
    if data.get("sessionId") not in (None, session_id):
        flags.append("premeasure_session_mismatch")
    cols: dict = {"pre_protocol_version": data.get("protocolVersion")}
    numeric: set[str] = set()
    bad = False
    for it in data.get("items") or []:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str):
            continue
        v = _int_or_none(it.get("value"))
        if v is not None and not PRE_RANGE[0] <= v <= PRE_RANGE[1]:
            v, bad = None, True
        key = f"pre_{it['id']}"
        cols[key] = v
        numeric.add(key)
    if bad:
        flags.append("premeasure_out_of_range")
    return cols, flags, numeric


def expected_condition(condition, control_mode) -> str | None:
    return "point_select" if control_mode == "point_select" else condition


def postinterview_columns(path: Path, session_id: str, condition, control_mode) -> tuple[dict, list[str], set[str]]:
    data = _read_json(path)
    if not isinstance(data, dict):
        return {}, [f"unreadable_file:{PI_FILE}"], set()
    flags = []
    if not str(data.get("formatVersion", "")).startswith(PI_PREFIX):
        flags.append("postinterview_version_mismatch")
    if data.get("sessionId") not in (None, session_id):
        flags.append("postinterview_session_mismatch")
    cond = data.get("condition")
    exp = expected_condition(condition, control_mode)
    if exp is not None and cond is not None and cond != exp:
        flags.append("pi_condition_mismatch")
    cols: dict = {"pi_condition": cond, "pi_protocol_version": data.get("protocolVersion"),
                  "pi_completed": bool(data.get("completedAt"))}
    numeric: set[str] = set()
    for it in data.get("items") or []:
        if not isinstance(it, dict) or not isinstance(it.get("id"), str):
            continue
        key = it["id"] + (f"_r{it['round']}" if isinstance(it.get("round"), int) else "")
        skipped = it.get("skipped") is True
        if "value" in it:
            cols[f"pi_{key}"] = _int_or_none(it.get("value"))
            numeric.add(f"pi_{key}")
        elif "choice" in it:
            cols[f"pi_{key}"] = it.get("choice") if isinstance(it.get("choice"), str) else None
        elif "text" in it:
            t = it.get("text")
            cols[f"pi_{key}_chars"] = len(t) if isinstance(t, str) and t and not skipped else None
            cols[f"pi_{key}_skipped"] = skipped
    return cols, flags, numeric


def session_columns(folder: Path, session_id: str, condition, control_mode,
                    selection_root: Path | None) -> tuple[dict, list[str], set[str], dict[str, bool]]:
    """세션 하나 → (열, flags, 숫자 열, 찾은 파일 {이름: 있음})."""
    files = find_files(folder, session_id, selection_root)
    cols: dict = {}
    flags: list[str] = []
    numeric: set[str] = set()
    if files[PRE_FILE] is not None:
        c, f, n = premeasure_columns(files[PRE_FILE], session_id)
        cols.update(c)
        flags.extend(f)
        numeric.update(n)
    if files[PI_FILE] is not None:
        c, f, n = postinterview_columns(files[PI_FILE], session_id, condition, control_mode)
        cols.update(c)
        flags.extend(f)
        numeric.update(n)
    return cols, flags, numeric, {k: v is not None for k, v in files.items()}
