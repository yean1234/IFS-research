"""면담 서버 (FastAPI). 웹 데모와 Unity가 같은 API를 쓴다. 명세: shared/api/README.md

실행:  python -m ifs_chatbot.server                    (config/default.toml, http://127.0.0.1:8000)
       python -m ifs_chatbot.server --backend offline  (LLM 없이)
       python -m ifs_chatbot.server --config pilot      (연구 파일럿 설정)

기본은 127.0.0.1에만 연다. 내적 경험 데이터가 연구실 컴퓨터 밖으로 나가지 않게 하려는 것이다.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Config, load_config
from .controller import Runtime, Session, SessionError
from .paths import WEB_DIR

log = logging.getLogger("ifs_chatbot.server")


class CreateSession(BaseModel):
    condition: str | None = Field(None, description="static(조건 1) | chatbot(조건 2). 비우면 설정 기본값")
    sessionId: str | None = Field(None, description="가명 ID (예: P07). 비우면 자동 생성")


class Reply(BaseModel):
    text: str = Field(..., max_length=2000)


class Action(BaseModel):
    action: str = Field(..., description="start | skip | continue | stop | confirm | edit | withdraw")
    text: str | None = Field(None, max_length=4000, description="edit일 때 고친 확정 텍스트")


class Event(BaseModel):
    type: str = Field(..., max_length=64, description="예: calibration, distance_summary, feel_toward, containment")
    payload: dict = Field(default_factory=dict)


class GuardCheck(BaseModel):
    text: str = Field(..., max_length=2000)


def create_app(cfg: Config | None = None, runtime: Runtime | None = None, warmup: bool = True) -> FastAPI:
    rt = runtime or Runtime(cfg or load_config())
    app = FastAPI(title="IFS 심상화 면담 서버", version="0.1.0",
                  description="IFS 6F(Find·Focus·Flesh out) 유도 면담 — 고정 문구 + 로컬 LLM clean 질문 + 검증기 + 안전 계층")
    app.state.runtime = rt

    if warmup and rt.backend_ok:
        threading.Thread(target=rt.backend.warmup, daemon=True).start()

    def get_session(sid: str) -> Session:
        s = rt.sessions.get(sid)
        if s is None:
            raise HTTPException(404, f"세션이 없습니다: {sid}")
        return s

    def run(fn, *args):
        try:
            return fn(*args)
        except SessionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/health")
    def health():
        return rt.info()

    @app.get("/api/protocol")
    def protocol():
        """고정 문구·질문 틀·단계 정보(공용 프로토콜). Unity가 같은 문구를 쓰도록."""
        return rt.protocol.data

    @app.get("/api/sessions")
    def list_sessions():
        return [{"sessionId": s.id, "condition": s.condition, "state": s.state,
                 "createdAt": s.log.data["createdAt"]} for s in rt.sessions.values()]

    @app.post("/api/sessions", status_code=201)
    def create_session(body: CreateSession):
        try:
            s = rt.new_session(body.condition, body.sessionId)
        except (SessionError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc
        return s.view()

    @app.get("/api/sessions/{sid}")
    def get_view(sid: str):
        return get_session(sid).view()

    @app.post("/api/sessions/{sid}/start")
    def start(sid: str):
        return run(get_session(sid).start)

    @app.post("/api/sessions/{sid}/reply")
    def reply(sid: str, body: Reply):
        return run(get_session(sid).reply, body.text)

    @app.post("/api/sessions/{sid}/action")
    def action(sid: str, body: Action):
        return run(get_session(sid).act, body.action, body.text)

    @app.get("/api/sessions/{sid}/log")
    def session_log(sid: str):
        """연구자용: 세션 로그 전체(elicit-log/0.1) + 런타임 경고."""
        return get_session(sid).researcher_view()

    @app.post("/api/sessions/{sid}/events", status_code=201)
    def add_event(sid: str, body: Event):
        """Unity 등에서 보내는 이벤트(보정량, 거리 요약, Feel toward 응답 등)를 같은 세션 로그에 묶는다."""
        return run(get_session(sid).add_event, body.type, body.payload)

    @app.post("/api/guard/check")
    def guard_check(body: GuardCheck):
        """VR 단계(Feel toward 등)의 참여자 발화도 같은 L1 안전 검사를 받는다. LLM은 부르지 않는다."""
        v = rt.guard.check_input(body.text)
        return {**v.to_log(), "softCheckPhrase": rt.protocol.phrase("soft_check") if v.level == "soft" else None,
                "crisisPhrase": rt.protocol.phrase("crisis", researcher_contact=rt.cfg.session.researcher_contact)
                if v.level == "crisis" else None}

    @app.exception_handler(RuntimeError)
    def runtime_error(_request, exc: RuntimeError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

        @app.get("/")
        def index():
            return FileResponse(WEB_DIR / "index.html")

    return app


def build_config(args: argparse.Namespace) -> Config:
    cfg = load_config(args.config)
    return cfg.with_overrides(**{
        "llm.backend": args.backend, "llm.model": args.model, "interview.condition": args.condition,
        "guard.model_backend": "none" if args.no_guard_model else None,
        "session.researcher_contact": args.researcher_contact,
    })


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.server", description="IFS 심상화 면담 서버")
    ap.add_argument("--config", default=os.environ.get("IFS_CHATBOT_CONFIG"), help="config 이름(default|pilot) 또는 .toml 경로")
    ap.add_argument("--backend", choices=["ollama", "offline"], help="LLM 백엔드 덮어쓰기")
    ap.add_argument("--model", help="Ollama 모델 덮어쓰기 (예: gemma4:31b)")
    ap.add_argument("--condition", choices=["chatbot", "static"], help="기본 조건")
    ap.add_argument("--no-guard-model", action="store_true", help="가드 모델 없이 키워드 사전만")
    ap.add_argument("--researcher-contact", help="위기 안내에 넣을 연구자 연락처")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    import uvicorn

    cfg = build_config(args)
    rt = Runtime(cfg)
    for w in rt.warnings:
        log.warning(w)
    log.info("모델: %s (%s) / 가드: %s", rt.backend.info().get("name"), "ok" if rt.backend_ok else "사용 불가",
             rt.guard.info().get("name"))
    if args.host not in ("127.0.0.1", "localhost"):
        log.warning("127.0.0.1이 아닌 주소(%s)로 엽니다. 같은 네트워크의 다른 기기가 접속할 수 있습니다.", args.host)
    log.info("웹 데모: http://%s:%d", args.host, args.port)
    uvicorn.run(create_app(runtime=rt), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
