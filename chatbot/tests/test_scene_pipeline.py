"""2단계 연결: 챗봇 확정 단계 직후 SceneSpec v2를 scenes/{sessionId}.json으로 저장한다.
합성 대사 시나리오(scenarios/scene_ex0*.json)를 오프라인 대역으로 끝까지 돌려 정답과 비교한다."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import CHATBOT_DIR
from ifs_chatbot.server import create_app
from ifs_chatbot.simulate import drive, load_scenarios

FIXTURES = Path(__file__).parent / "fixtures" / "scene_spec"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture
def runtime(offline_cfg, tmp_path):
    cfg = offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs")})
    rt = Runtime(cfg)
    if not rt.analyzer.available:
        pytest.skip("kiwipiepy가 없으면 정답과 다르다")
    return rt


@pytest.fixture
def runtime_v0(offline_cfg, tmp_path):
    """주 매핑을 v0(규칙 기반 기준선)로 둔 런타임. 정답 EX01·EX02는 v0 출력이다."""
    cfg = offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs"), "mapping.mode": "v0"})
    rt = Runtime(cfg)
    if not rt.analyzer.available:
        pytest.skip("kiwipiepy가 없으면 정답과 다르다")
    return rt


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_confirm_writes_scene_file_equal_to_golden(runtime_v0, case):
    runtime = runtime_v0
    scenario = load_scenarios([str(CHATBOT_DIR / case["scenario"])])[0]
    s = runtime.new_session(case["condition"], case["sessionId"], case["participantId"])
    drive(s, scenario)
    assert s.state == "done"
    assert s.log.data["confirmedText"] == case["confirmedText"]
    path = runtime.cfg.scenes_dir / f"{case['sessionId']}.json"
    assert path == s.scene_path and path.exists()
    assert path.parent == runtime.cfg.log_dir / "scenes"           # 기본 출력 폴더: <log_dir>/scenes (git 밖)
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads((FIXTURES / case["file"]).read_text(encoding="utf-8"))
    ref = s.log.data["sceneSpec"]
    assert ref["path"] == str(path) and ref["problems"] == [] and ref["sourceTextHash"].startswith("sha256:")
    assert ref["mapping"] == {"requested": "v0", "used": "v0", "fallbackReason": None}


def golden_bytes(name: str) -> bytes:
    """정답 파일을 장면 파일 작성기와 같은 형식(키 순서 그대로, indent 2, 끝 줄바꿈)으로 다시 쓴 바이트.
    정답 파일 자체는 charSpan을 한 줄로 적은 손 정리본이라 v0 작성기 출력과 원래부터 바이트가 달랐다(baseline a753289에서도).
    정답 파일은 바꾸지 않고(AC-3.8 (1)), 키 순서·수 표기·들여쓰기까지 같아야 통과하는 바이트 비교를 한다."""
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def file_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")      # Windows 텍스트 모드 줄바꿈만 맞춘다


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_v0_scene_file_byte_identical_to_golden(runtime_v0, case):
    """AC-3.8: v0가 쓴 장면 파일이 정답과 바이트까지 같다(값 비교가 아니라 파일 바이트 비교. 키 순서도 본다)."""
    s = runtime_v0.new_session(case["condition"], case["sessionId"], case["participantId"])
    drive(s, load_scenarios([str(CHATBOT_DIR / case["scenario"])])[0])
    assert file_bytes(s.scene_path) == golden_bytes(case["file"])
    assert file_bytes(s.variant_path("v0")) == golden_bytes(case["file"])   # save_both 비교 파일도 같다


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_default_v1_writes_main_and_both_variants_v0_byte_identical(runtime, case):
    """기본 설정(mode = v1, save_both): 주 파일 = v1, 비교 파일 {sid}.v0.json은 정답과 바이트 동일, {sid}.v1.json = 주 파일."""
    assert runtime.cfg.mapping.mode == "v1" and runtime.cfg.mapping.save_both
    s = runtime.new_session(case["condition"], case["sessionId"], case["participantId"])
    drive(s, load_scenarios([str(CHATBOT_DIR / case["scenario"])])[0])
    main = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert main["meta"]["specVersion"] == "2.1.0" and main["meta"]["mapping"]["used"] == "v1"
    assert file_bytes(s.variant_path("v0")) == golden_bytes(case["file"])
    assert s.variant_path("v1").read_bytes() == s.scene_path.read_bytes()
    ref = s.log.data["sceneSpec"]
    assert ref["problems"] == [] and ref["variants"]["v0"] == str(s.variant_path("v0"))
    s.act("withdraw")                                               # 철회하면 비교 파일도 지운다
    assert not s.scene_path.exists() and not s.variant_path("v0").exists() and not s.variant_path("v1").exists()


def test_scene_uses_only_confirmed_text(runtime):
    """면담 중 말한 '회색 덩어리'가 있어도, 확정 때 고쳐 쓴 문장만 장면이 된다(턴 JSON·이전 답은 쓰지 않음)."""
    sc = {"id": "t", "condition": "chatbot", "replies": ["가슴 안쪽에 회색 덩어리가 있어요", "가슴 안쪽이요"],
          "defaultReply": "없어요", "confirm": {"edit": "작은 안개 같아요"}}
    s = runtime.new_session("chatbot", "ONLYCONFIRMED")
    drive(s, sc)
    spec = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert spec["form"]["type"] == "mist" and spec["material"]["color"] is None and spec["body"]["part"] is None
    assert spec["meta"]["participantId"] is None                    # 주지 않은 참여자 ID는 null


def test_static_condition_also_writes_scene(runtime):
    sc = load_scenarios([str(CHATBOT_DIR / "scenarios" / "p07_static.json")])[0]
    s = runtime.new_session("static", "STATIC01")
    drive(s, sc)
    spec = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert spec["meta"]["condition"] == "static"
    assert spec["form"]["type"] == "blob" and spec["layout"]["size"] is not None


def test_withdraw_deletes_scene_file(runtime):
    case = CASES[1]
    s = runtime.new_session("chatbot", "WD01")
    drive(s, load_scenarios([str(CHATBOT_DIR / case["scenario"])])[0])
    assert s.scene_path.exists()
    s.act("withdraw")
    assert not s.scene_path.exists() and s.scene_spec is None and s.log.data["sceneSpec"] is None


def test_stopped_session_writes_no_scene(runtime):
    s = runtime.new_session("chatbot", "STOP01")
    s.start()
    s.reply("가슴 안쪽에 회색 덩어리가 있어요")
    s.act("stop")
    assert not s.scene_path.exists() and "sceneSpec" not in s.log.data


def test_api_scene_endpoint_and_participant_id(offline_cfg, tmp_path):
    cfg = offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs")})
    client = TestClient(create_app(cfg, warmup=False))
    r = client.post("/api/sessions", json={"condition": "chatbot", "sessionId": "API01", "participantId": "SYN01"})
    assert r.status_code == 201
    assert client.get("/api/sessions/API01/scene").status_code == 409      # 확정 전에는 없다
    client.post("/api/sessions/API01/start")
    view = client.post("/api/sessions/API01/reply", json={"text": "웅크려진 작은 나"}).json()
    for _ in range(20):
        if view["awaiting"] == "confirm":
            break
        view = client.post("/api/sessions/API01/reply", json={"text": "없어요"}).json()
    client.post("/api/sessions/API01/action", json={"action": "confirm"})
    body = client.get("/api/sessions/API01/scene").json()
    assert body["spec"]["meta"]["participantId"] == "SYN01"
    assert body["spec"]["form"]["posture"] == "curled"
    assert Path(body["path"]).name == "API01.json"
    bad = client.post("/api/sessions", json={"condition": "chatbot", "participantId": "홍길동"})
    assert bad.status_code == 409                                         # 가명 형식만
