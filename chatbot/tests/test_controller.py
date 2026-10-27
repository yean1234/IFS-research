"""컨트롤러 — 단계 진행, 고정 문구 vs LLM, 횟수 제한, 안전 분기."""
import pytest

from conftest import turn
from ifs_chatbot.controller import SessionError


def run_replies(s, replies):
    it = iter(replies)
    while s.awaiting == "reply":
        s.reply(next(it, "없어요"))


def sources(s):
    return [t.get("source") for t in s.log.turns]


def test_p07_storyboard_flow_offline(rt):
    s = rt.new_session("chatbot")
    s.start()
    run_replies(s, ["가슴이 좀 답답해요", "가슴 안쪽이요", "답답한 게 꽉 차 있어요", "젖은 종이처럼 축 처진 덩어리 같아요",
                    "회색이고 무거워요", "바닥에 눌어붙은 것 같아요", "그게 다예요", "손바닥만 하고 납작해요", "움직임은 없어요"])
    asked = [m["text"] for m in s.messages if m.get("source") == "llm"]
    assert asked[:2] == ["'답답'에 대해 더 있나요?", "그 '덩어리'는 어떤 '덩어리'인가요?"]   # 스토리보드와 같은 첫 두 질문
    # 색은 '회색'으로 이미 나와 건너뛰고, 크기·움직임만 고정 프로브로 묻는다(스토리보드: "고정 프로브: 크기? 움직임?")
    assert s.log.data["capture"]["probes"] == {"asked": ["size_shape", "movement"], "skippedAsCovered": ["color_brightness"]}
    assert s.awaiting == "confirm"
    s.act("confirm")
    d = s.log.data
    assert d["endedBy"] == "completed"
    assert d["capture"]["bodyRelation"]["part"] == "chest" and d["capture"]["bodyRelation"]["layer"] == "inner"
    slots = d["extraction"]["sceneSpecDraft"]["slots"]
    assert slots["material.color"]["value"]["name"] == "gray"
    assert slots["material.color"]["_provenance"]["trigger"] == "회색"
    assert slots["motion"]["values"][0]["value"] == {"motion": "still"}       # '움직임은 없어요'
    assert any(u["lemma"] == "눌어붙" for u in d["extraction"]["unmatched"])    # 사전 밖 단어 기록


def test_static_condition_never_calls_llm(rt):
    s = rt.new_session("static")
    s.start()
    run_replies(s, ["가슴이 좀 답답해요", "가슴 안쪽이요", "젖은 종이처럼 축 처진 덩어리 같아요", "회색이고 무거워요", "작아요", "가라앉아요"])
    assert "llm" not in sources(s) and "fixed:fleshout_open" in sources(s)
    assert s.log.data["model"] is None


def test_crisis_stops_llm_immediately(scripted):
    rt, backend = scripted([turn(stage="find", template="anything_else", anchor="무거워요", utterance="'무거워요'에 대해 더 있나요?")])
    s = rt.new_session("chatbot")
    s.start()
    s.reply("가슴이 무거워요")
    s.reply("가슴 안쪽이요")                  # → Find LLM 1회
    calls = len(backend.calls)
    s.reply("사실 요즘은 죽고 싶다는 생각도 들어요")
    assert s.state == "crisis" and s.awaiting == "none" and s.log.data["endedBy"] == "crisis"
    assert len(backend.calls) == calls        # 위기 이후 LLM 호출 없음
    crisis_text = s.messages[-1]["text"]
    assert "109" in crisis_text and "1577-0199" in crisis_text
    assert any(a["kind"] == "crisis" and a["severity"] == "critical" for a in s.log.data["alerts"])
    with pytest.raises(SessionError):
        s.reply("계속할래요")


def test_soft_check_once_per_expression(rt):
    s = rt.new_session("chatbot")
    s.start()
    s.reply("가슴이 답답하고 숨이 막히는 느낌이에요")
    assert s.awaiting == "soft_check"
    s.act("continue")
    assert s.awaiting == "reply"
    s.reply("가슴 안쪽이요")
    s.reply("숨이 막히는 것처럼 꽉 막혀 있어요")   # 같은 은유 — 다시 묻지 않음
    assert s.awaiting != "soft_check"
    assert sources(s).count("fixed:soft_check") == 1


def test_soft_check_stop_ends_session(rt):
    s = rt.new_session("chatbot")
    s.start()
    s.reply("숨이 막히는 느낌이 올라와요")
    s.act("stop")
    assert s.log.data["endedBy"] == "participant_stop" and s.awaiting == "none"


def test_regeneration_then_fallback(scripted):
    leak = turn(stage="find", template="anything_else", anchor="답답", utterance="'답답'한 느낌에 대해 더 있나요?")
    rt, backend = scripted([leak, leak, leak])
    s = rt.new_session("chatbot")
    s.start()
    s.reply("가슴이 좀 답답해요")
    s.reply("가슴 안쪽이요")
    t = s.log.turns[-1]
    assert len(backend.calls) == 3 and t["source"] == "fixed:fallback" and t["checks"]["fallback"]
    assert all(not a["passed"] and "V5:leak:느낌" in a["reasons"] for a in t["attempts"])
    assert "다시 쓰기" in backend.calls[1].user          # 두 번째 시도에는 걸린 이유를 알려 준다
    assert s.messages[-1]["text"] == "방금 말씀하신 것에 대해 더 있나요?"


def test_second_attempt_passes(scripted):
    bad = turn(stage="find", template="anything_else", anchor="답답", utterance="'답답'한 느낌에 대해 더 있나요?")
    good = turn(stage="find", template="anything_else", anchor="답답", utterance="'답답'한 것에 대해 더 있나요?")
    rt, _ = scripted([bad, good])
    s = rt.new_session("chatbot")
    s.start()
    s.reply("가슴이 좀 답답해요")
    s.reply("가슴 안쪽이요")
    t = s.log.turns[-1]
    assert t["source"] == "llm" and t["checks"]["regenerations"] == 1 and [a["passed"] for a in t["attempts"]] == [False, True]


def test_llm_risk_signal_goes_to_soft_check(scripted):
    rt, _ = scripted([turn(stage="find", template="none", anchor="", utterance="", move="hold", risk="distress")])
    s = rt.new_session("chatbot")
    s.start()
    s.reply("가슴이 좀 답답해요")
    s.reply("가슴 안쪽이요")
    assert s.awaiting == "soft_check"
    assert any(a["kind"] == "risk_signal" for a in s.log.data["alerts"])


def test_depth_drift_uses_present_focus_then_soft_check(rt):
    s = rt.new_session("chatbot")
    s.start()
    for r in ["가슴이 조여요", "가슴 안쪽이요", "꽉 조이는 느낌이에요", "어릴 때 교실에서 혼자 서 있던 장면이 떠올라요"]:
        s.reply(r)
    assert s.log.turns[-1]["source"] == "fixed:depth_present"
    s.reply("그때 친구들이 웃던 기억이 나요")
    assert s.awaiting == "soft_check"
    assert any(a["kind"] == "depth" for a in s.log.data["alerts"])
    s.act("continue")
    # 기억 서사 속 말('친구')은 인용 후보에서 빠진다
    assert not any("친구" in (t.get("text") or "") for t in s.log.turns if t.get("source") == "llm")


def test_dont_know_is_not_pressed(rt):
    s = rt.new_session("chatbot")
    s.start()
    s.reply("잘 모르겠어요")
    s.reply("위치는 잘 모르겠어요")
    # Find LLM 후속 질문을 건너뛰고 바로 Focus 고정 문구로
    assert s.log.turns[-1]["source"] == "fixed:focus_hold"
    assert s.log.data["capture"]["bodyRelation"]["status"] == "unspecified"


def test_skip_button_and_stop_command(rt):
    s = rt.new_session("chatbot")
    s.start()
    s.reply("가슴이 답답해요")
    s.act("skip")                          # 위치 질문 넘어가기
    assert s.log.data["capture"]["bodyRelation"]["status"] == "unspecified"
    s2 = rt.new_session("chatbot")
    s2.start()
    s2.reply("그만할래요")
    assert s2.log.data["endedBy"] == "participant_stop"


def test_edit_confirm_and_withdraw_deletes_log(rt):
    s = rt.new_session("static")
    s.start()
    run_replies(s, ["가슴이 답답해요", "가슴 안쪽이요", "회색 덩어리 같아요", "무거워요", "작아요", "없어요"])
    s.act("edit", "가슴 안쪽에 작은 회색 덩어리가 있어요")
    assert s.log.data["confirmedText"] == "가슴 안쪽에 작은 회색 덩어리가 있어요" and s.log.data["confirmation"]["edited"]
    assert s.log.path.exists()
    s.act("withdraw")
    assert not s.log.path.exists() and s.state == "withdrawn" and s.log.data["turns"] == []


def test_withdraw_not_allowed_after_crisis(rt):
    s = rt.new_session("chatbot")
    s.start()
    s.reply("죽고 싶어요")
    with pytest.raises(SessionError):
        s.act("withdraw")


def test_session_id_must_be_pseudonymous_and_path_safe(rt):
    with pytest.raises(SessionError):
        rt.new_session("chatbot", "../../etc/passwd")
    s = rt.new_session("chatbot", "P07-test")
    with pytest.raises(SessionError):
        rt.new_session("chatbot", "P07-test")          # 중복
    assert s.log.path.name == "P07-test.json"


def test_log_header_records_versions(rt):
    s = rt.new_session("chatbot")
    d = s.log.data
    assert d["logVersion"] == "elicit-log/0.1"
    assert set(d["protocol"]) >= {"promptVersion", "promptSha256", "lexiconVersion", "controllerVersion", "protocolVersion"}
    assert d["model"]["name"] == "offline-template"
