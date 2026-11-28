"""본 실험 단일 설정 config/experiment.toml(v4 흐름 + D9 다리 질문 + 설계 뼈대 3절 권고값) 점검.

- 설정이 기존 설정 조합(bridge·v4·pilot)에서 정해 둔 곳만 다른지
- 합성 시나리오 2개(다리 질문 X 있음·X 없음)를 면담 → 확정 → 매퍼 v2 spec → 후보 → 선택 → 조절 → 사전 측정 → 사후 면담 기록까지
  모의 LLM(오프라인 대역)으로 돌려, 헤드셋 러너가 읽는 파일(spec·selection.json)과 분석기가 읽는 파일(premeasure·postinterview)이 나오는지
- (선택) IFS_LIVE=1이면 실제 로컬 LLM(Ollama)으로 한 시나리오

대사는 모두 합성이다(AGENTS.md 6). 실행: python -m pytest tests/test_experiment_config.py
"""
import hashlib
import json
import os
from dataclasses import asdict, replace

import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import SCENARIO_DIR
from ifs_chatbot.postinterview import PostInterviewProtocol, PostInterviewStore
from ifs_chatbot.simulate import check_expect, drive, session_metrics

SCENARIOS = ("g70_emotion_bridge_x", "g70_emotion_bridge_plain")   # 프로토콜 1.6(G70) 판. 1.5 판은 bridge 설정 시나리오


def scenario(name: str) -> dict:
    return json.loads((SCENARIO_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ── 설정 조합 ────────────────────────────────────────────────────────────────
def test_experiment_config_is_bridge_plus_v4_plus_backbone_values():
    exp, bridge, v4 = load_config("experiment"), load_config("bridge"), load_config("v4")
    # 면담·검증기 = bridge(D9) + 면담 조건 고정 + G70(프로토콜 1.6·프롬프트 v1.2.0). bridge는 1.5·v1.1.0 그대로
    assert exp.interview == replace(bridge.interview, lock_condition=True, protocol="elicitation_protocol.v1.6.json",
                                    prompt_version="1.2.0")
    assert bridge.interview.lock_condition is False
    assert bridge.interview.protocol == "elicitation_protocol.v1.5.json" and bridge.interview.prompt_version == "1.1.0"
    assert exp.validator == bridge.validator
    # 가드 = bridge, 가드 모델 필수만 pilot과 같게, 안전 사전은 G70-f 0.3.0(bridge는 0.2.0 그대로)
    assert exp.guard == replace(bridge.guard, required=True, safety_lexicon="safety_ko.v0.3.json")
    assert bridge.guard.safety_lexicon == "safety_ko.v0.2.json"
    assert load_config("pilot").guard.required is True
    # LLM·표류·미리보기 = v4
    assert exp.llm == v4.llm and exp.drift == v4.drift and exp.preview == v4.preview
    # 매핑 = v4(매퍼 v2), strict만 pilot과 같게
    assert exp.mapping == replace(v4.mapping, strict=True, proportions="scene_params.v2.json",   # G72: 비율
                                  mist_kinds="scene_params.v2.json",                            # G74: 안개 입자 모양
                                  llm_fill=True)                                                # G77: LLM 빈칸 채우기
    assert v4.mapping.llm_fill is False
    assert v4.mapping.proportions == "" and v4.mapping.mist_kinds == ""
    # 선택 단계 = v4, 초안 경고 줄만 참여자 보기에서 숨김(뼈대 3절·G59-8)
    # G72: 조절 항목 너비·높이·깊이(값 표 3.0.0 · 문구 0.7.0)
    # G73: 문구 0.8.0(0.7.0 + [맞는 게 없어요] 뒤 생성 화면 문구 4개). G75: 0.9.0(+ 참고 그림 고르기 화면 문구 4개)
    # G77: 0.10.0(+ LLM이 채운 처음 값의 근거 인용 안내 1개). G79: 값 표 4.0.0(색상 고리) · 문구 0.11.0(+ 고리 문구 3개)
    # G83: 0.13.0(0.12.0 = 0.11.0 + G82 근거 인용 줄·[그 말이 아니에요], 0.13.0 = 명사 부분·받침에 맞춘 조사)
    assert exp.selection == replace(v4.selection, participant_draft_banner=False, protocol="selection_protocol.v0.13.json",
                                    table="candidate_values.v4.json")
    assert v4.selection.table == "candidate_values.v2.json" and v4.selection.protocol == "selection_protocol.v0.json"
    # 생성 메시를 기본 후보로 두는 G62 경로는 끔(G67-b). G73: [맞는 게 없어요] 뒤 생성만 켬
    # G75: 그 생성에서 참고 그림을 먼저 고름(on_none_image_pick, 회차 2, 단계별 한도 180초)
    # G83: [맞는 게 없어요] 뒤 규칙에 중심 형태 명사가 없으면 LLM 형태 이름(G82, on_none_llm_shape, 한도 20초·seed 0)
    assert exp.gen3d.enabled is False and exp.gen3d == replace(v4.gen3d, on_none=True, on_none_image_pick=True,
                                                               on_none_llm_shape=True)
    assert exp.gen3d.on_none_llm_shape_timeout_s == 20.0 and exp.gen3d.on_none_llm_shape_seed == 0
    assert v4.gen3d.on_none_llm_shape is False
    assert exp.session == v4.session


def test_existing_configs_unchanged_by_experiment_profile():
    # 새 파일 하나만 더했다. 기존 설정이 코드 기본값 위에서 읽히는 값이 예전과 같은지(대표 키)
    assert load_config("v4").interview.protocol == "elicitation_protocol.v1.4.json"
    assert load_config("bridge").mapping.mode == "v1"
    assert load_config("v4").selection.participant_draft_banner is True
    assert load_config("v4-gen3d").gen3d.enabled is True
    assert load_config().selection.enabled is False
    # 면담 조건 고정은 experiment.toml만 켠다
    for name in ("default", "pilot", "v4", "v4-gen3d", "bridge", "mac8gb"):
        assert load_config(name).interview.lock_condition is False, name


# ── 모의 LLM으로 끝까지 ─────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def exp_rt(tmp_path_factory):
    cfg = load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "preview.mode": "none",
        "session.log_dir": str(tmp_path_factory.mktemp("exp_logs"))})
    return Runtime(cfg)


def run_full(rt: Runtime, name: str, sid: str, condition: str = "place"):
    sc = scenario(name)
    s = rt.new_session("chatbot", sid, None)
    drive(s, sc)
    f = s.selection()
    view = f.start()
    if view["stage"] == "selecting":
        f.select(view["candidates"][0]["id"])
    f.adjust("color", "h07")
    f.finish()
    f.submit_premeasure({i["id"]: 4 for i in rt.selection_protocol.items()})
    store = PostInterviewStore(PostInterviewProtocol(rt.cfg.selection.post_interview), rt.cfg.log_dir)
    # 사후 면담 앞 부분(PI1–PI5)을 모두 [건너뜀]으로 저장(합성 세션이라 글은 넣지 않음)
    free = [{"id": it["id"], "skipped": True} for it in store.protocol.items_for(condition, "free")]
    store.save(sid, condition, "free", free)
    return sc, s, f, store


@pytest.mark.parametrize("name,sid", [(SCENARIOS[0], "SYN-EXP-X"), (SCENARIOS[1], "SYN-EXP-PLAIN")])
def test_experiment_flow_offline_interview_to_postinterview(exp_rt, name, sid):
    sc, s, f, store = run_full(exp_rt, name, sid)
    # 면담: 시나리오 기대(다리 질문 경로 포함) 그대로
    assert check_expect(sc, session_metrics(s), s) == []
    assert s.log.data["capture"]["bridge"]["asked"] is True
    assert s.log.data["protocol"]["protocolVersion"] == "1.6.0"
    assert s.log.data["protocol"]["promptVersion"] == "1.2.0"
    assert s.log.data["capture"]["bodyRelation"] == {"status": "not_asked"}      # G70: location 없음
    # 확정 → 세션 안에서 바로 매퍼 v2 spec(bridge.toml처럼 v1이 아님, 이음매 없이 후보 단계가 v2를 씀)
    spec_path = s.log.data["sceneSpec"]["path"]
    spec_bytes = open(spec_path, "rb").read()
    spec = json.loads(spec_bytes)
    assert spec["meta"]["pipeline"]["builder"].startswith("scene-spec-builder-v2/")
    # 후보 → 선택 → 조절 → 사전 측정: 러너가 읽는 선택 파일
    sel = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert sel["formatVersion"] == "ifs-selection/0.5"          # G77: llm_fill 켬 → 처음부터 0.5(gen3d 끔이라도)
    assert sel["llmFill"]["status"] == "skipped" and sel["llmFill"]["skipReason"] == "backend_unsupported"   # 오프라인 대역
    assert sel["runnerReady"] is True and sel["spec"]["sha256Basis"] == "file"
    assert sel["specSha256"] == hashlib.sha256(spec_bytes).hexdigest()   # 러너의 시작 거부 조건(G26)
    assert sel["colorChanged"] is True
    assert not any(k.startswith("layout.distance") or k.startswith("layout.verticalOffset") for k in sel["finalOverrides"])
    pre = json.loads((f.dir / "premeasure.json").read_text(encoding="utf-8"))
    assert pre["sessionId"] == sid and all(i["value"] == 4 for i in pre["items"])
    # 사후 면담 기록(분석기 --selection-dir가 읽는 곳)
    pi = json.loads(store.path(sid).read_text(encoding="utf-8"))
    assert pi["sessionId"] == sid and pi["condition"] == "place" and "free" in pi["parts"]
    assert sorted(p.name for p in f.dir.iterdir()) == ["candidates.json", "postinterview.json", "premeasure.json", "selection.json"]


def test_experiment_participant_view_hides_draft_banner(exp_rt):
    from ifs_chatbot.selection import ui_config
    ui = ui_config(exp_rt.selection_protocol, exp_rt.candidate_table, exp_rt.preview.info(), True,
                   exp_rt.cfg.selection.participant_draft_banner)
    assert ui["participantDraftBanner"] is False


# ── 면담 조건 고정([interview] lock_condition) ──────────────────────────────
def test_experiment_locks_condition_screen_server_and_log(exp_rt):
    from fastapi.testclient import TestClient
    from ifs_chatbot.server import create_app
    c = TestClient(create_app(runtime=exp_rt, warmup=False))
    # 시작 화면: 조건 선택이 없고 설정 조건을 한 줄로만
    page = c.get("/").text
    assert 'name="condition"' not in page and 'value="static"' not in page and "조건 1" not in page
    assert 'id="condition-locked"' in page and 'data-condition="chatbot"' in page
    assert "면담: 조건 2 · AI 챗봇 면담 (설정으로 고정)" in page
    h = c.get("/api/health").json()
    assert h["conditionLocked"] is True and h["defaultCondition"] == "chatbot"
    # 서버: 다른 조건 요청은 거절(세션을 만들지 않음), 같은 조건·빈 조건은 챗봇으로
    r = c.post("/api/sessions", json={"condition": "static", "sessionId": "SYN-LOCK-STATIC"})
    assert r.status_code == 409 and "lock_condition" in r.json()["detail"]
    assert "SYN-LOCK-STATIC" not in exp_rt.sessions
    for sid, body in (("SYN-LOCK-EMPTY", {}), ("SYN-LOCK-CHATBOT", {"condition": "chatbot"})):
        r = c.post("/api/sessions", json={**body, "sessionId": sid})
        assert r.status_code == 201 and r.json()["condition"]["id"] == "chatbot"
        log = exp_rt.sessions[sid].log.data
        assert log["elicitationCondition"] == "chatbot" and log["conditionLocked"] is True


def test_unlocked_config_still_offers_both_conditions(tmp_path):
    from fastapi.testclient import TestClient
    from ifs_chatbot.server import create_app
    cfg = load_config("bridge").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "preview.mode": "none", "session.log_dir": str(tmp_path)})
    rt = Runtime(cfg)
    c = TestClient(create_app(runtime=rt, warmup=False))
    page = c.get("/").text
    assert 'value="static"' in page and 'value="chatbot"' in page and 'id="condition-locked"' not in page
    assert "conditionLocked" not in c.get("/api/health").json()
    r = c.post("/api/sessions", json={"condition": "static", "sessionId": "SYN-UNLOCK-STATIC"})
    assert r.status_code == 201 and r.json()["condition"]["id"] == "static"
    assert "conditionLocked" not in rt.sessions["SYN-UNLOCK-STATIC"].log.data


# ── 실제 로컬 LLM(선택) ──────────────────────────────────────────────────────
@pytest.mark.live
@pytest.mark.skipif(os.environ.get("IFS_LIVE") != "1", reason="IFS_LIVE=1일 때만(Ollama + gemma4:e4b)")
def test_experiment_flow_live_llm(tmp_path):
    cfg = load_config("experiment").with_overrides(**{
        "guard.model_backend": "none", "guard.required": False, "preview.mode": "none", "session.log_dir": str(tmp_path)})
    rt = Runtime(cfg)
    if not rt.backend_ok:
        pytest.skip(rt.backend_msg)
    sc, s, f, _ = run_full(rt, SCENARIOS[0], "SYN-EXP-LIVE")
    assert s.log.data["endedBy"] == "completed"
    assert s.log.data["capture"]["bridge"]["asked"] is True
    for t in s.log.turns:
        if t.get("source") == "llm" and t.get("text"):
            assert t["checks"]["passed"]
    sel = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert sel["runnerReady"] is True
    assert (f.dir / "premeasure.json").is_file()
