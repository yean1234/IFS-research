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


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_confirm_writes_scene_file_equal_to_golden(runtime, case):
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
