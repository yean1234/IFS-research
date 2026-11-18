"""보기 전 보고 과제(ifs_chatbot/prereport.py, shared/schemas/prereport.v0.json, shared/protocol/prereport_task.v0.json).
합성 대사만 쓴다(AGENTS.md 6). LLM은 offline 백엔드."""
import copy
import hashlib
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ifs_chatbot import prereport
from ifs_chatbot.paths import shared
from ifs_chatbot.server import create_app

SCHEMA = json.loads(shared("schemas", "prereport.v0.json").read_text(encoding="utf-8"))
TASK = json.loads(shared("protocol", "prereport_task.v0.json").read_text(encoding="utf-8"))

ANSWERS = {
    "color": {"commitment": "from_start", "value": {"h": 0.62, "l": 0.4}, "method": "hue_lightness_field",
              "nSelections": 2},
    "size": {"commitment": "not_set", "value": None, "method": "size_slider", "nSelections": 0},
    "form": {"commitment": "when_asked"},
    "motion": {"commitment": "not_set"},
}


def record(**over):
    rec = {"schema": "ifs-prereport/0.1", "sessionId": "SYN-01", "participant": None, "specSha256": "c" * 64,
           "taskTextFile": "prereport_task.v0.json", "taskTextVersion": "0.1", "createdAtUtc": "2026-11-18T01:02:03Z",
           "attributes": copy.deepcopy(ANSWERS)}
    rec.update(over)
    return rec


def errors(rec):
    return list(Draft202012Validator(SCHEMA).iter_errors(rec))


# ---------------------------------------------------------------- 스키마

def test_schema_is_valid_and_accepts_record():
    Draft202012Validator.check_schema(SCHEMA)
    assert errors(record()) == []
    rec = record()
    rec["attributes"]["size"] = {"commitment": "when_asked", "value": 0.31, "method": "size_slider", "nSelections": 3}
    assert errors(rec) == []


@pytest.mark.parametrize("mutate", [
    lambda r: r["attributes"]["size"].update(value=0.5),                     # ③인데 값
    lambda r: r["attributes"]["color"].update(commitment="not_set"),         # ③인데 색 값
    lambda r: r["attributes"]["color"].update(value=None),                   # ①인데 값 없음
    lambda r: r["attributes"]["color"].update(nSelections=0),                # ①인데 고른 적 없음
    lambda r: r["attributes"]["color"].update(value={"h": 1.2, "l": 0.5}),   # 0–1 밖
    lambda r: r["attributes"]["color"].update(value={"h": 0.2, "l": 0.5, "s": 0.6}),
    lambda r: r["attributes"]["size"].update(commitment="maybe"),
    lambda r: r["attributes"]["form"].update(value="round"),                 # 모양·움직임은 값을 받지 않는다
    lambda r: r["attributes"].pop("motion"),
    lambda r: r.update(specSha256="abc"),
    lambda r: r.update(schema="ifs-prereport/0.2"),
])
def test_schema_rejects(mutate):
    rec = record()
    mutate(rec)
    assert errors(rec)


# ---------------------------------------------------------------- 고정 문구

def _texts(task):
    for a in task["attributes"].values():
        yield a["question"]
    yield from task["commitmentOptions"]
    yield from task["fixedPhrases"].values()


def test_task_texts_are_draft_with_source_and_follow_scope():
    assert TASK["taskVersion"] == "0.1" and TASK["changes"][-1]["version"] == "0.1"
    assert TASK["attributeOrder"] == ["color", "size", "form", "motion"]
    assert [o["id"] for o in TASK["commitmentOptions"]] == ["from_start", "when_asked", "not_set"]
    for t in _texts(TASK):
        assert t["status"] == "draft"
        assert t["source"].startswith("docs/rq-v2-proposal.md 3.2 (초안, IRB 검토 전)") and "Bigelow" in t["source"]
    words = json.dumps(TASK, ensure_ascii=False)
    assert not re.search("치료|내담자|진단", words)
    assert {a: TASK["attributes"][a]["question"]["text"] for a in TASK["attributeOrder"]} == {
        "color": "떠올린 모습에 색이 있었나요?", "size": "떠올린 모습에 크기가 있었나요?",
        "form": "떠올린 모습에 모양이 있었나요?", "motion": "떠올린 모습에 움직임이 있었나요?"}


# ---------------------------------------------------------------- 서버

@pytest.fixture(scope="module")
def client(rt):
    return TestClient(create_app(runtime=rt, warmup=False))


def _confirmed_session(client, sid):
    v = client.post("/api/sessions", json={"condition": "chatbot", "sessionId": sid}).json()
    v = client.post(f"/api/sessions/{sid}/start").json()
    for text in ["가슴이 좀 답답해요", "가슴 안쪽이요", "없어요", "회색 덩어리 같아요", "없어요", "작아요", "가라앉아요"]:
        if v["awaiting"] != "reply":
            break
        v = client.post(f"/api/sessions/{sid}/reply", json={"text": text}).json()
    assert v["awaiting"] == "confirm"
    return v


def test_refuses_before_confirmation_then_writes_valid_record(client, rt):
    sid = "PR-SYN-01"
    _confirmed_session(client, sid)
    st = client.get(f"/api/sessions/{sid}/prereport").json()
    assert st["available"] is False and st["submitted"] is False and st["reason"]
    r = client.post(f"/api/sessions/{sid}/prereport", json={"attributes": ANSWERS})
    assert r.status_code == 409
    assert not prereport.record_path(rt.cfg.log_dir, sid).exists()

    assert client.post(f"/api/sessions/{sid}/action", json={"action": "confirm"}).json()["state"] == "done"
    assert client.get(f"/api/sessions/{sid}/prereport").json()["available"] is True
    r = client.post(f"/api/sessions/{sid}/prereport", json={"attributes": ANSWERS})
    assert r.status_code == 201, r.text
    path = prereport.record_path(rt.cfg.log_dir, sid)
    assert path == Path(rt.cfg.log_dir) / sid / "prereport.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert errors(rec) == []
    scene = rt.sessions[sid].scene_path
    assert rec["specSha256"] == hashlib.sha256(scene.read_bytes()).hexdigest() == r.json()["specSha256"]
    assert rec["specFile"] == f"{sid}.json" and rec["sessionId"] == sid
    assert rec["taskTextFile"] == "prereport_task.v0.json" and rec["taskTextVersion"] == "0.1"
    assert rec["attributes"]["size"]["value"] is None
    # 고른 값은 세션 로그에 들어가지 않는다(장면 JSON은 확정 때 이미 쓰였고 이 과제가 건드리지 않는다)
    log = client.get(f"/api/sessions/{sid}/log").json()["log"]
    ev = [e for e in log["events"] if e["type"] == "prereport"]
    assert len(ev) == 1 and "attributes" not in ev[0]["payload"] and ev[0]["payload"]["specSha256"] == rec["specSha256"]
    # 한 번만 받는다
    assert client.post(f"/api/sessions/{sid}/prereport", json={"attributes": ANSWERS}).status_code == 409
    st = client.get(f"/api/sessions/{sid}/prereport").json()
    assert st == {"sessionId": sid, "available": False, "submitted": True, "reason": None}
    # 철회하면 보고도 지운다
    client.post(f"/api/sessions/{sid}/action", json={"action": "withdraw"})
    assert not path.exists()


def test_invalid_answers_are_422_and_not_written(client, rt):
    sid = "PR-SYN-02"
    _confirmed_session(client, sid)
    client.post(f"/api/sessions/{sid}/action", json={"action": "confirm"})
    bad = copy.deepcopy(ANSWERS)
    bad["size"]["value"] = 0.4                       # ③인데 값
    r = client.post(f"/api/sessions/{sid}/prereport", json={"attributes": bad})
    assert r.status_code == 422 and r.json()["detail"]["problems"]
    assert not prereport.record_path(rt.cfg.log_dir, sid).exists()


def test_task_page_and_text_are_served_locally(client):
    r = client.get("/prereport")
    assert r.status_code == 200 and "/static/prereport.js" in r.text
    js = client.get("/static/prereport.js")
    assert js.status_code == 200
    assert client.get("/api/prereport/task").json()["taskVersion"] == "0.1"
    for text in (r.text, js.text):
        assert not re.search(r"(src|href)=\"https?://", text) and "cdn" not in text.lower()
