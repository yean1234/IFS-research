"""chatbot/scenarios/*.json의 기대(expect)를 오프라인 대역으로 확인한다.
안전 분기(위기·확인 문구·L5·중단)는 LLM과 무관하게 결정론적이어야 한다."""
import pytest

from ifs_chatbot.simulate import check_expect, drive, load_scenarios, session_metrics

SCENARIOS = load_scenarios([])


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(rt, sc):
    s = rt.new_session(sc.get("condition", "chatbot"))
    drive(s, sc)
    fails = check_expect(sc, session_metrics(s), s)
    assert fails == []
