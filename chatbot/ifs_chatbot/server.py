"""면담 서버 (FastAPI). 웹 데모와 Unity가 같은 API를 쓴다. 명세: shared/api/README.md

실행:  python -m ifs_chatbot.server                    (config/default.toml, http://127.0.0.1:8000)
       python -m ifs_chatbot.server --backend offline  (LLM 없이)
       python -m ifs_chatbot.server --config pilot      (연구 파일럿 설정)
       python -m ifs_chatbot.server --config v4         (실험 프로토타입 흐름: 면담 뒤 후보 선택·조절·사전 측정)

기본은 127.0.0.1에만 연다. 내적 경험 데이터가 연구실 컴퓨터 밖으로 나가지 않게 하려는 것이다.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Config, load_config
from .controller import Runtime, Session, SessionError
from .paths import WEB_DIR
from .selection import SelectionError, SelectionInvalid, ui_config

log = logging.getLogger("ifs_chatbot.server")


class CreateSession(BaseModel):
    condition: str | None = Field(None, description="static(조건 1) | chatbot(조건 2). 비우면 설정 기본값")
    sessionId: str | None = Field(None, description="가명 ID (예: P07). 비우면 자동 생성")
    participantId: str | None = Field(None, description="가명 참여자 ID. 장면 파일 meta에만 쓴다. 비우면 null")


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


class SelectionChoice(BaseModel):
    candidateId: str = Field(..., max_length=64, description="보여 준 후보 id 또는 \"none\"(맞는 것이 없다, G23)")


class AdjustStep(BaseModel):
    item: str = Field(..., max_length=32, description="form | color | brightness | opacity | size | texture | motion (G10)")
    value: Any = Field(..., description="표의 값(색은 견본 id, 형태·움직임은 이름, 나머지는 정해진 단계의 숫자)")


class PremeasureAnswers(BaseModel):
    responses: dict[str, Any] = Field(..., description="문항 id → 1–7 정수 또는 null(답하지 않음)")


def create_app(cfg: Config | None = None, runtime: Runtime | None = None, warmup: bool = True) -> FastAPI:
    rt = runtime or Runtime(cfg or load_config())

    @asynccontextmanager
    async def lifespan(_app):
        yield
        rt.preview.close()          # 상주 미리보기 플레이어 끄기

    app = FastAPI(title="IFS 심상화 면담 서버", version="0.1.0", lifespan=lifespan,
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
            s = rt.new_session(body.condition, body.sessionId, body.participantId)
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

    @app.get("/api/sessions/{sid}/scene")
    def scene(sid: str):
        """확정 뒤 만든 SceneSpec v2와 저장 경로. Unity의 HTTP 경로 전달(ISceneSpecPathSource)이 쓸 자리."""
        s = get_session(sid)
        if s.scene_spec is None:
            raise HTTPException(409, "아직 장면 기술이 없습니다([이대로 맞아요] 뒤에 생깁니다).")
        return {"sessionId": s.id, "path": (s.log.data.get("sceneSpec") or {}).get("path"), "spec": s.scene_spec}

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

    # ── 면담 뒤 데스크톱 단계: 4 후보 선택 · 5 조절 · 6 사전 측정 (selection.py, LLM·검증기 호출 없음) ──────
    def sel_run(fn, *args):
        try:
            return fn(*args)
        except SelectionInvalid as exc:
            raise HTTPException(422, str(exc)) from exc
        except (SelectionError, SessionError) as exc:
            raise HTTPException(409, str(exc)) from exc

    def flow(sid: str, create: bool = False):
        s = get_session(sid)
        if not rt.cfg.selection.enabled:
            raise HTTPException(409, "후보 단계가 꺼져 있습니다([selection] enabled = false). 새 흐름은 --config v4.")
        f = sel_run(s.selection, create)
        if f is None:
            raise HTTPException(409, "아직 후보가 없습니다(POST …/candidates 먼저).")
        return f

    @app.get("/api/selection/config")
    def selection_config():
        """후보·조절·사전 측정 화면의 고정 문구(초안 표시 포함), 조절 항목과 값 목록, 미리보기 모드."""
        return ui_config(rt.selection_protocol, rt.candidate_table, rt.preview.info(), rt.cfg.selection.enabled)

    @app.get("/api/sessions/{sid}/selection")
    def selection_state(sid: str):
        """지금 단계와 후보·조절 상태(화면 다시 그리기용)."""
        s = get_session(sid)
        if not rt.cfg.selection.enabled:
            raise HTTPException(409, "후보 단계가 꺼져 있습니다([selection] enabled = false).")
        f = s.selection(create=False)
        if f is None:
            v = s.view().get("selection") or {}
            return {"sessionId": sid, "stage": None, "available": v.get("available", False), "preview": rt.preview.info(),
                    **{k: rt.selection_protocol.info()[k] for k in ("draftCount", "draftKeys")}}
        return f.view()

    @app.post("/api/sessions/{sid}/candidates")
    def candidates(sid: str):
        """확정 뒤 후보를 만들고 기록한다(같은 세션에서 다시 부르면 같은 후보)."""
        return sel_run(flow(sid, create=True).start)

    @app.post("/api/sessions/{sid}/selection")
    def select(sid: str, body: SelectionChoice):
        return sel_run(flow(sid).select, body.candidateId)

    @app.post("/api/sessions/{sid}/adjust")
    def adjust(sid: str, body: AdjustStep):
        return sel_run(flow(sid).adjust, body.item, body.value)

    @app.post("/api/sessions/{sid}/adjust/finish")
    def adjust_finish(sid: str):
        return sel_run(flow(sid).finish)

    @app.get("/api/sessions/{sid}/final")
    def final(sid: str):
        """헤드셋 러너가 읽을 원본 spec(바꾸지 않음) + selection.json(러너 계약: formatVersion·specSha256·finalOverrides·selection·sources).
        runnerReady가 false면(spec 파일이 저장되지 않은 실행 등) 러너에 넘길 수 없고 runnerBlockers에 이유가 있다(G26)."""
        return sel_run(flow(sid).final)

    @app.get("/api/sessions/{sid}/premeasure")
    def premeasure_get(sid: str):
        return sel_run(flow(sid).premeasure_view)

    @app.post("/api/sessions/{sid}/premeasure")
    def premeasure_post(sid: str, body: PremeasureAnswers):
        return sel_run(flow(sid).submit_premeasure, body.responses)

    @app.get("/api/sessions/{sid}/preview/{target}.png")
    def preview_png(sid: str, target: str):
        """image 모드: 후보 id 또는 current(조절 중 지금 상태)의 미리보기 PNG. 플레이어가 실패하면 none으로 바뀌고 503."""
        f = flow(sid)
        overrides = sel_run(f.overrides_for, target)
        if rt.preview.mode != "image":
            raise HTTPException(409, f"미리보기 모드가 image가 아닙니다(지금 {rt.preview.mode}: {rt.preview.reason}).")
        data = rt.preview.render(f.spec, overrides)
        if data is None:
            f.note_preview_fallback()
            raise HTTPException(503, f"미리보기를 그리지 못해 글 요약으로 바꿉니다: {rt.preview.reason}")
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.exception_handler(RuntimeError)
    def runtime_error(_request, exc: RuntimeError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    if rt.preview.mode == "webgl" and rt.preview.webgl_dir is not None:
        # WebGL 미리보기 빌드를 같은 출처로 내보낸다(외부 CDN 없음). 압축을 끈 빌드라 별도 헤더가 필요 없다.
        app.mount("/preview/webgl", StaticFiles(directory=rt.preview.webgl_dir, html=True), name="preview-webgl")

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
    ap.add_argument("--config", default=os.environ.get("IFS_CHATBOT_CONFIG"),
                    help="config 이름(default|pilot|v4) 또는 .toml 경로. v4 = 실험 프로토타입 흐름(매퍼 v2, 면담 뒤 "
                         "후보 선택·조절·사전 측정 단계, 미리보기 image). 예: --config v4 --backend offline --condition static")
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
