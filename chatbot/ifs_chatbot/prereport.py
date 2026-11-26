"""보기 전 보고 과제 (ifs-prereport/0.2, docs/rq-v2-proposal.md 3.2).

확정 텍스트 뒤, 만든 형상을 보기 전에 참여자가 속성마다 한 번 답한 확정 여부(①②③)와 색·크기 값을 기록한다.
- 면담 밖의 고정 문구 과제다. 면담자·검증기(V1–V9)를 거치지 않고 LLM을 부르지 않는다.
- 고른 값은 장면 JSON에 넣지 않는다. 별도 파일 <log_dir>/<sessionId>/prereport.json에만 쓴다(git 밖).
- ③(not_set)이면 값을 받지 않는다(스키마가 막는다). 값을 추론하거나 기본값으로 채우지 않는다.
- 장면 파일의 sha256은 확정 시점에 고정한 값(controller가 넘김)을 쓴다. 제출 직전에 파일이 바뀌어도 바뀌지 않는다.
- 분석기(eval/ownership_shift.py)도 같은 validate()로 검사한다. 0.1 기록(prereport.v0.json)도 읽는다.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .paths import shared

SCHEMA_ID = "ifs-prereport/0.2"
SCHEMA_FILES = {"ifs-prereport/0.1": "prereport.v0.json", "ifs-prereport/0.2": "prereport.v0.2.json"}
TASK_FILE = "prereport_task.v0.3.json"
RECORD_NAME = "prereport.json"


@lru_cache(maxsize=1)
def task_text() -> dict:
    return json.loads(shared("protocol", TASK_FILE).read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _validator(schema_id: str):
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", SCHEMA_FILES[schema_id]).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate(record) -> list[str]:
    """record의 schema 값(0.1 · 0.2)에 맞는 스키마 위반 목록(없으면 빈 목록)."""
    sid = record.get("schema") if isinstance(record, dict) else None
    if sid not in SCHEMA_FILES:
        return [f"schema: 모르는 값 {sid!r} (가능: {sorted(SCHEMA_FILES)})"]
    errs = sorted(_validator(sid).iter_errors(record), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in errs]


def record_path(log_dir: Path, session_id: str) -> Path:
    return Path(log_dir) / session_id / RECORD_NAME


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now_iso(now: datetime | None = None) -> str:
    t = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def freeze_hashes(primary: Path, others: list[Path]) -> dict:
    """확정 시점의 장면 파일별 sha256. → {"specFile", "specSha256", "alt": {이름: sha}, "frozenAtUtc"}"""
    primary = Path(primary)
    alt = {Path(p).name: sha256_file(p) for p in others if p and Path(p).is_file() and Path(p) != primary}
    return {"specFile": primary.name, "specSha256": sha256_file(primary), "alt": alt, "frozenAtUtc": utc_now_iso()}


def build_record(*, session_id: str, participant: str | None, frozen: dict, attributes: dict,
                 now: datetime | None = None) -> dict:
    """클라이언트가 보낸 attributes에 서버가 아는 값(ID·확정 때 고정한 장면 sha256·문구 판)을 붙인다. 검증은 validate()."""
    t = task_text()
    rec = {
        "schema": SCHEMA_ID,
        "sessionId": session_id,
        "participant": participant,
        "specSha256": frozen["specSha256"],
        "specFile": frozen["specFile"],
        "specFrozenAtUtc": frozen["frozenAtUtc"],
        "taskTextFile": TASK_FILE,
        "taskTextVersion": t["taskVersion"],
        "createdAtUtc": utc_now_iso(now),
        "attributes": attributes,
    }
    if frozen.get("alt"):
        rec["altSpecSha256"] = dict(frozen["alt"])
    return rec


def write_record(record: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def delete_record(log_dir: Path, session_id: str) -> bool:
    """참여자 철회 때 보기 전 보고도 지운다(빈 세션 폴더도 지운다).
    Unity 기록 폴더로 복사된 사본은 여기서 지우지 못한다 — chatbot/README.md의 철회 절차를 따른다."""
    p = record_path(log_dir, session_id)
    existed = p.exists()
    if existed:
        p.unlink()
    try:
        p.parent.rmdir()
    except OSError:
        pass
    return existed
