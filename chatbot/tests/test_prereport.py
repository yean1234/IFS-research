"""보기 전 보고 과제(ifs_chatbot/prereport.py, shared/schemas/prereport.v0.2.json(0.1은 prereport.v0.json),
shared/protocol/prereport_task.v0.2.json). 합성 대사만 쓴다(AGENTS.md 6). LLM은 offline 백엔드."""
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

SCHEMA = json.loads(shared("schemas", "prereport.v0.2.json").read_text(encoding="utf-8"))
SCHEMA01 = json.loads(shared("schemas", "prereport.v0.json").read_text(encoding="utf-8"))
TASK = json.loads(shared("protocol", "prereport_task.v0.2.json").read_text(encoding="utf-8"))
TASK01 = json.loads(shared("protocol", "prereport_task.v0.json").read_text(encoding="utf-8"))

ANSWERS = {
    "color": {"commitment": "from_start", "value": {"h": 0.62, "l": 0.4}, "firstValue": {"h": 0.3, "l": 0.5},
              "method": "hue_lightness_field", "nSelections": 2, "commitmentChangedAfterPick": False},
    "size": {"commitment": "not_set", "value": None, "firstValue": None, "widthM": None, "firstWidthM": None,
             "method": "size_slider", "nSelections": 1, "commitmentChangedAfterPick": True},
    "form": {"commitment": "when_asked"},
    "motion": {"commitment": "not_set"},
}


def record(**over):
    rec = {"schema": "ifs-prereport/0.2", "sessionId": "SYN-01", "participant": None, "specSha256": "c" * 64,
           "specFile": "SYN-01.json", "taskTextFile": "prereport_task.v0.2.json", "taskTextVersion": "0.2",
           "createdAtUtc": "2026-11-18T01:02:03.456Z", "attributes": copy.deepcopy(ANSWERS)}
    rec.update(over)
    return rec


def errors(rec):
    return list(Draft202012Validator(SCHEMA).iter_errors(rec))


# ---------------------------------------------------------------- 스키마

def test_schemas_are_valid_and_accept_records():
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator.check_schema(SCHEMA01)
    assert errors(record()) == [] and prereport.validate(record()) == []
    rec = record()
    rec["attributes"]["size"] = {"commitment": "when_asked", "value": 0.31, "firstValue": 0.4, "widthM": 0.16,
                                 "firstWidthM": 0.26, "method": "size_slider", "nSelections": 3,
                                 "commitmentChangedAfterPick": False}
    rec["attributes"]["color"]["value"] = {"h": None, "s": 0, "l": 0.2}       # 무채색 띠
    assert errors(rec) == []
    old = {"schema": "ifs-prereport/0.1", "sessionId": "SYN-01", "participant": None, "specSha256": "c" * 64,
           "taskTextFile": "prereport_task.v0.json", "taskTextVersion": "0.1", "createdAtUtc": "2026-11-18T01:02:03Z",
           "attributes": {"color": {"commitment": "not_set", "value": None, "method": "hue_lightness_field",
                                    "nSelections": 0},
                          "size": {"commitment": "from_start", "value": 0.4, "method": "size_slider", "nSelections": 1},
                          "form": {"commitment": "not_set"}, "motion": {"commitment": "not_set"}}}
    assert prereport.validate(old) == []                                        # 0.1도 읽는다


@pytest.mark.parametrize("mutate", [
    lambda r: r["attributes"]["size"].update(value=0.5),                     # ③인데 값
    lambda r: r["attributes"]["size"].update(widthM=0.2),                    # ③인데 폭
    lambda r: r["attributes"]["color"].update(commitment="not_set"),         # ③인데 색 값
    lambda r: r["attributes"]["color"].update(firstValue=None),              # ①인데 첫 선택 없음
    lambda r: r["attributes"]["color"].update(value=None),
    lambda r: r["attributes"]["color"].update(nSelections=0),
    lambda r: r["attributes"]["color"].update(value={"h": 1.2, "l": 0.5}),
    lambda r: r["attributes"]["color"].update(value={"h": 0.2, "s": 0, "l": 0.5}),   # 무채색은 h null
    lambda r: r["attributes"]["color"].pop("commitmentChangedAfterPick"),
    lambda r: r["attributes"]["form"].update(value="round"),
    lambda r: r["attributes"].pop("motion"),
    lambda r: r.update(specSha256="0"),
    lambda r: r.update(schema="ifs-prereport/0.3"),
])
def test_schema_rejects(mutate):
    rec = record()
    mutate(rec)
    assert prereport.validate(rec)


# ---------------------------------------------------------------- 고정 문구

def _texts(task):
    for a in task["attributes"].values():
        yield a["question"]
    yield from task["commitmentOptions"]
    yield from task["fixedPhrases"].values()


def test_task_texts_are_draft_with_source_and_follow_scope():
    assert TASK["taskVersion"] == "0.2" and TASK["changes"][-1]["version"] == "0.2"
    assert TASK01["taskVersion"] == "0.1"                         # 0.1 기록이 가리키는 파일은 그대로 둔다
    assert TASK["attributeOrder"] == ["color", "size", "form", "motion"]
    assert [o["id"] for o in TASK["commitmentOptions"]] == ["from_start", "when_asked", "not_set"]
    for t in [*_texts(TASK), TASK["ariaLabels"]]:
        assert t["status"] == "draft"
        assert "docs/rq-v2-proposal.md 3.2 (초안, IRB 검토 전)" in t["source"] and "Bigelow" in t["source"]
    for key in ("open_link", "already_submitted", "submit_refused", "change_answer", "page_title", "not_ready"):
        assert TASK["fixedPhrases"][key]["text"]
    assert not re.search("치료|내담자|진단", json.dumps(TASK, ensure_ascii=False))
    assert TASK["attributes"]["color"]["question"]["text"] == "떠올린 모습에 색이 있었나요?"


def test_web_files_carry_no_participant_text():
    """참여자에게 보이는 한국어 문구는 과제 파일에만 있다(주석 제외)."""
    web = Path(prereport.__file__).parent / "web"
    js = re.sub(r"//[^\n]*|/\*.*?\*/", "", (web / "prereport.js").read_text(encoding="utf-8"), flags=re.S)
    html = re.sub(r"<!--.*?-->", "", (web / "prereport.html").read_text(encoding="utf-8"), flags=re.S)
    assert not re.search("[가-힣]", js) and not re.search("[가-힣]", html)
    assert "보기 전 보고로" not in (web / "app.js").read_text(encoding="utf-8")


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
    assert client.post(f"/api/sessions/{sid}/prereport", json={"attributes": ANSWERS}).status_code == 409
    assert not prereport.record_path(rt.cfg.log_dir, sid).exists()

    assert client.post(f"/api/sessions/{sid}/action", json={"action": "confirm"}).json()["state"] == "done"
    scene = rt.sessions[sid].scene_path
    frozen = hashlib.sha256(scene.read_bytes()).hexdigest()
    variants = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (rt.sessions[sid].variant_path("v0"), rt.sessions[sid].variant_path("v1")) if p.is_file()}
    # 확정 뒤 제출 전에 장면 파일이 바뀌어도 확정 때 고정한 sha256을 쓴다
    scene.write_text(scene.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert client.get(f"/api/sessions/{sid}/prereport").json()["available"] is True
    r = client.post(f"/api/sessions/{sid}/prereport", json={"attributes": ANSWERS})
    assert r.status_code == 201, r.text
    path = prereport.record_path(rt.cfg.log_dir, sid)
    assert path == Path(rt.cfg.log_dir) / sid / "prereport.json"
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert errors(rec) == []
    assert rec["specSha256"] == frozen == r.json()["specSha256"] != hashlib.sha256(scene.read_bytes()).hexdigest()
    assert rec.get("altSpecSha256", {}) == variants and rec["specFrozenAtUtc"]
    assert rec["specFile"] == f"{sid}.json" and rec["sessionId"] == sid
    assert rec["taskTextFile"] == "prereport_task.v0.2.json" and rec["taskTextVersion"] == "0.2"
    log = client.get(f"/api/sessions/{sid}/log").json()["log"]
    assert log["sceneSpec"]["sha256"]["specSha256"] == frozen
    ev = [e for e in log["events"] if e["type"] == "prereport"]
    assert len(ev) == 1 and "attributes" not in ev[0]["payload"]       # 고른 값은 세션 로그에 들어가지 않는다
    assert client.post(f"/api/sessions/{sid}/prereport", json={"attributes": ANSWERS}).status_code == 409
    st = client.get(f"/api/sessions/{sid}/prereport").json()
    assert st == {"sessionId": sid, "available": False, "submitted": True, "reason": None}
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
    assert client.get("/api/prereport/task").json()["taskVersion"] == "0.2"
    for text in (r.text, js.text):
        assert not re.search(r"(src|href)=\"https?://", text) and "cdn" not in text.lower()
