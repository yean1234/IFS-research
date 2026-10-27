"""HTTP API (shared/api/README.md) — 웹 데모와 Unity가 쓰는 계약."""
import pytest
from fastapi.testclient import TestClient

from ifs_chatbot.server import create_app


@pytest.fixture(scope="module")
def client(rt):
    return TestClient(create_app(runtime=rt, warmup=False))


def test_health_and_protocol(client):
    h = client.get("/api/health").json()
    assert h["backend"]["ok"] and set(h["conditions"]) == {"static", "chatbot"}
    p = client.get("/api/protocol").json()
    assert p["fixedPhrases"]["opening"]["status"] == "spec"


def test_full_session_over_http(client):
    v = client.post("/api/sessions", json={"condition": "chatbot", "sessionId": "API-P07"}).json()
    assert v["awaiting"] == "start" and v["buttons"][0]["action"] == "start"
    v = client.post("/api/sessions/API-P07/start").json()
    assert v["stageInfo"]["ifs"] == "Find"
    for text in ["가슴이 좀 답답해요", "가슴 안쪽이요", "없어요", "회색 덩어리 같아요", "없어요", "작아요", "가라앉아요"]:
        if v["awaiting"] != "reply":
            break
        r = client.post("/api/sessions/API-P07/reply", json={"text": text})
        assert r.status_code == 200, r.text
        v = r.json()
    assert v["awaiting"] == "confirm" and v["confirmDraft"]
    v = client.post("/api/sessions/API-P07/action", json={"action": "confirm"}).json()
    assert v["state"] == "done"
    log = client.get("/api/sessions/API-P07/log").json()["log"]
    assert log["endedBy"] == "completed" and log["extraction"]["attributes"]


def test_wrong_order_is_409(client):
    client.post("/api/sessions", json={"condition": "static", "sessionId": "API-ORDER"})
    r = client.post("/api/sessions/API-ORDER/reply", json={"text": "안녕"})
    assert r.status_code == 409
    assert client.get("/api/sessions/NOPE").status_code == 404


def test_guard_check_for_vr_stages(client):
    r = client.post("/api/guard/check", json={"text": "숨이 막히는 느낌이 올라와요"}).json()
    assert r["level"] == "soft" and r["softCheckPhrase"] == "지금 계속 이야기해도 괜찮으신가요?"
    r = client.post("/api/guard/check", json={"text": "죽고 싶어요"}).json()
    assert r["level"] == "crisis" and "109" in r["crisisPhrase"]


def test_unity_events_are_bundled_into_log(client):
    client.post("/api/sessions", json={"condition": "static", "sessionId": "API-EV"})
    r = client.post("/api/sessions/API-EV/events", json={"type": "calibration", "payload": {"scaleDelta": -0.25}})
    assert r.status_code == 201
    log = client.get("/api/sessions/API-EV/log").json()["log"]
    assert log["events"][0]["payload"] == {"scaleDelta": -0.25}


def test_web_demo_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "IFS 면담 데모" in r.text
    assert client.get("/static/app.js").status_code == 200
