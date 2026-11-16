"""코퍼스 재생 — 합성 답을 실제 컨트롤러(정적 조건, 조건 1)에 순서대로 넣어 확정 텍스트와 SceneSpec v2를 얻는다.

simulate.drive()와 같은 방식으로 Session을 움직인다. 안전 검사, 프로브 건너뛰기(이미 말한 차원은 묻지 않음),
확정 텍스트 조립, 장면 파일 쓰기를 모두 실제 코드 그대로 거친다. 그래서 컨트롤러가 버린 답(묻지 않은 프로브의 답)은
확정 텍스트에 들어가지 않는다. 실제 면담과 같다.

  python -m ifs_chatbot.eval.corpus_run --corpus tests/fixtures/imagery_corpus/dev.json --out runs.json

코퍼스 항목 형식: {"id", "replies": {opening, location, focus, fleshout, probe_size_shape, probe_color_brightness,
probe_movement}, "gold": [...], "distractors": [...]}. replies 값이 null인 프로브를 컨트롤러가 묻는 경우에는
[넘어가기](control:skip)를 누른 것으로 처리한다. 참여자가 같은 말을 되풀이했다고 지어내지 않기 위해서다.

매핑 함수는 바꿔 끼울 수 있다(mapper). 기본 "v0"은 현 scene_builder다. "v1"은 개선 매핑(scene_builder_v1.factory).
config의 [mapping] mode와 상관없이 mapper 인자가 매핑을 정한다. 다른 매핑은 "모듈:이름"으로 주며,
그 이름은 factory(rt) → build(text, *, session_id, participant_id, condition) -> dict 를 가진 객체를 돌려줘야 한다.
컨트롤러의 rt.scene_builder 자리에 넣으므로 개선 매핑도 같은 경로(Session._write_scene)를 지난다.
세션 로그와 장면 파일은 임시 폴더에 쓴다(chatbot/logs를 건드리지 않는다).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Callable

from ..config import Config, load_config
from ..controller import Runtime, Session
from ..korean import normalize

RUNNER_VERSION = "0.1.0"
CONDITION = "static"
# 고정 문구 id → 코퍼스 replies 키
FIXED_REPLY_KEYS = {"opening": "opening", "location": "location", "focus_hold": "focus", "fleshout_open": "fleshout"}
TRACE_TURN_KEYS = ("i", "speaker", "source", "stage", "probe", "text")


# ── 매핑 선택 ────────────────────────────────────────────────────────────────
def resolve_mapper(mapper: str | Callable | None) -> tuple[str, Callable | None]:
    """(라벨, factory). factory가 None이면 Runtime이 만든 v0 scene_builder를 그대로 쓴다."""
    if mapper is None or mapper == "v0":
        return "v0", None
    if mapper == "v1":                                   # 개선 매핑(= ifs_chatbot.scene_builder_v1:factory)
        from ..scene_builder_v1 import factory
        return "v1", factory
    if callable(mapper):
        return getattr(mapper, "__name__", "custom"), mapper
    if isinstance(mapper, str) and ":" in mapper:
        mod_name, attr = mapper.split(":", 1)
        return mapper, getattr(importlib.import_module(mod_name), attr)
    raise ValueError(f"모르는 매핑: {mapper!r} (v0 또는 '모듈:이름')")


def offline_config(work_dir: Path, base: Config | None = None) -> Config:
    """LLM·가드 모델 없이, 로그와 장면을 work_dir에 쓰는 정적 조건 설정."""
    cfg = base or load_config()
    # 매핑은 mapper 인자로만 고른다: 기본 자리는 v0, 다른 매핑은 make_runtime이 끼운다. 비교 파일·확인 질문은 끈다.
    return cfg.with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "interview.condition": CONDITION,
        "session.log_dir": str(work_dir / "logs"), "session.scenes_dir": str(work_dir / "scenes"),
        "mapping.mode": "v0", "mapping.save_both": False, "mapping.clarify_loop": False,
    })


def make_runtime(work_dir: Path, mapper: str | Callable | None = "v0", base: Config | None = None) -> tuple[Runtime, str]:
    label, factory = resolve_mapper(mapper)
    rt = Runtime(offline_config(work_dir, base), persist_logs=True)
    if factory is not None:
        rt.scene_builder = factory(rt)
    return rt, label


# ── 한 항목 재생 ──────────────────────────────────────────────────────────────
def _reply_key(session: Session) -> str | None:
    step = session.step
    if step is None:
        return None
    if step.type == "fixed":
        return FIXED_REPLY_KEYS.get(step.phrase, step.phrase)
    if step.type == "probes":
        cur = session.step_state[session.idx].get("current")
        return f"probe_{cur}" if cur else None
    return None


def drive_item(session: Session, item: dict, max_steps: int = 80) -> dict:
    """항목의 replies를 컨트롤러가 묻는 순서대로 넣는다. 재생 기록(trace 일부)을 돌려준다."""
    replies: dict = item.get("replies") or {}
    used: list[str] = []
    asked_without_reply: list[str] = []
    soft_checks = 0
    for _ in range(max_steps):
        a = session.awaiting
        if a == "none":
            break
        if a == "start":
            session.start()
        elif a == "reply":
            key = _reply_key(session)
            text = replies.get(key) if key else None
            if text is None or not normalize(text):
                asked_without_reply.append(key or "?")
                session.act("skip")
            else:
                used.append(key)
                session.reply(text)
        elif a == "soft_check":
            soft_checks += 1
            session.act("continue")
        elif a == "confirm":
            session.act("confirm")
    else:
        raise RuntimeError(f"{item.get('id')}: {max_steps}단계 안에 끝나지 않았습니다")
    unused = [k for k, v in replies.items() if v is not None and normalize(v) and k not in used]
    return {"usedReplies": used, "unusedReplies": unused, "askedWithoutReply": asked_without_reply,
            "softChecks": soft_checks}


def _trace(session: Session, drive: dict) -> dict:
    data = session.log.data
    turns = [{k: t[k] for k in TRACE_TURN_KEYS if k in t} for t in data["turns"]]
    scene = dict(data.get("sceneSpec") or {})
    scene.pop("path", None)                              # 임시 경로는 결과를 비결정적으로 만든다
    return {
        **drive,
        "endedBy": data.get("endedBy"),
        "probes": (data.get("capture") or {}).get("probes"),
        "alerts": [{"kind": a["kind"], "detail": a["detail"]} for a in data.get("alerts", [])],
        "sceneSpec": scene,
        "turns": turns,
    }


def run_items(rt: Runtime, items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        sid = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in str(item["id"]))[:40]
        rt.sessions.pop(sid, None)
        s = rt.new_session(CONDITION, sid)
        drive = drive_item(s, item)
        out.append({"id": item["id"], "style": item.get("style"),
                    "confirmedText": s.log.data.get("confirmedText"),
                    "spec": s.scene_spec,
                    "controllerTrace": _trace(s, drive)})
    return out


def load_corpus(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_corpus(corpus: dict | str | Path, mapper: str | Callable | None = "v0",
               work_dir: str | Path | None = None, base: Config | None = None) -> dict:
    """코퍼스 전체 재생. work_dir가 없으면 임시 폴더를 만들고 끝나면 지운다."""
    if not isinstance(corpus, dict):
        corpus = load_corpus(corpus)
    tmp = None
    if work_dir is None:
        tmp = tempfile.TemporaryDirectory(prefix="ifs-corpus-run-")
        work_dir = tmp.name
    try:
        rt, label = make_runtime(Path(work_dir), mapper, base)
        builder_info = rt.scene_builder.info() if hasattr(rt.scene_builder, "info") else {}
        items = run_items(rt, corpus["items"])
        return {"runner": f"corpus-run/{RUNNER_VERSION}", "corpusId": corpus.get("corpusId"),
                "corpusVersion": corpus.get("version"), "condition": CONDITION, "mapper": label,
                "builder": builder_info, "analyzer": rt.analyzer.info(), "items": items}
    finally:
        if tmp is not None:
            tmp.cleanup()


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.corpus_run", description="코퍼스 → 컨트롤러 → SceneSpec")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--mapper", default="v0", help="v0(기본) 또는 '모듈:factory'")
    ap.add_argument("--out", required=True, help="결과 JSON 파일")
    args = ap.parse_args(argv)
    res = run_corpus(args.corpus, args.mapper)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(res['items'])}개 항목 → {out}")


if __name__ == "__main__":
    main()
