"""보기 전 보고 과제 (ifs-prereport/0.1, docs/rq-v2-proposal.md 3.2).

확정 텍스트 뒤, 만든 형상을 보기 전에 참여자가 속성마다 한 번 답한 확정 여부(①②③)와 색·크기 값을 기록한다.
- 면담 밖의 고정 문구 과제다. 면담자·검증기(V1–V9)를 거치지 않고 LLM을 부르지 않는다.
- 고른 값은 장면 JSON에 넣지 않는다. 별도 파일 <log_dir>/<sessionId>/prereport.json에만 쓴다(git 밖).
- ③(not_set)이면 값을 받지 않는다(스키마가 막는다). 값을 추론하거나 기본값으로 채우지 않는다.
- 기록에는 이 보고가 딸린 장면 파일의 sha256을 남긴다(분석기가 Unity manifest.specSha256과 맞춘다).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .paths import shared

SCHEMA_ID = "ifs-prereport/0.1"
SCHEMA_FILE = "prereport.v0.json"
TASK_FILE = "prereport_task.v0.json"
RECORD_NAME = "prereport.json"


@lru_cache(maxsize=1)
def task_text() -> dict:
    return json.loads(shared("protocol", TASK_FILE).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", SCHEMA_FILE).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate(record: dict) -> list[str]:
    """스키마 위반 목록(없으면 빈 목록)."""
    errs = sorted(_validator().iter_errors(record), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}" for e in errs]


def record_path(log_dir: Path, session_id: str) -> Path:
    return Path(log_dir) / session_id / RECORD_NAME


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_record(*, session_id: str, participant: str | None, spec_path: Path, attributes: dict,
                 alt_specs: list[Path] = (), now: datetime | None = None) -> dict:
    """클라이언트가 보낸 attributes에 서버가 아는 값(ID·장면 sha256·문구 판)을 붙인다. 검증은 validate()."""
    t = task_text()
    spec_path = Path(spec_path)
    alt = {p.name: sha256_file(p) for p in alt_specs if Path(p).is_file() and Path(p) != spec_path}
    rec = {
        "schema": SCHEMA_ID,
        "sessionId": session_id,
        "participant": participant,
        "specSha256": sha256_file(spec_path),
        "specFile": spec_path.name,
        "taskTextFile": TASK_FILE,
        "taskTextVersion": t["taskVersion"],
        "createdAtUtc": (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "attributes": attributes,
    }
    if alt:
        rec["altSpecSha256"] = alt
    return rec


def write_record(record: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def delete_record(log_dir: Path, session_id: str) -> bool:
    """참여자 철회 때 보기 전 보고도 지운다(빈 세션 폴더도 지운다)."""
    p = record_path(log_dir, session_id)
    existed = p.exists()
    if existed:
        p.unlink()
    try:
        p.parent.rmdir()
    except OSError:
        pass
    return existed
