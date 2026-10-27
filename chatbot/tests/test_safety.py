import pytest

from ifs_chatbot.safety import Guard, SafetyLexicon


@pytest.fixture(scope="module")
def g():
    return Guard(SafetyLexicon(), model=None)


@pytest.mark.parametrize("text,level,alert", [
    ("회색이고 좀 무거워요", "safe", False),
    ("가슴이 조이는 느낌이에요", "safe", False),          # 흔한 신체감각 묘사는 확인 문구를 내지 않는다
    ("숨이 막히는 느낌이 올라와요", "soft", False),       # 스토리보드 13′
    ("답답해 죽겠어요", "soft", False),
    ("어딘가로 사라지고 싶은 느낌이에요", "soft", True),   # 모호 — 연구자 알림
    ("죽고 싶어요", "crisis", True),
    ("자해를 한 적이 있어요", "crisis", True),
    ("그 사람을 죽이고 싶어요", "crisis", True),
])
def test_keyword_tiers(g, text, level, alert):
    v = g.check_input(text)
    assert (v.level, v.alert) == (level, alert), v.reasons


def test_model_s6_raises_soft_check_and_alert(fake_guard):
    g = Guard(SafetyLexicon(), fake_guard({("다 놓아 버리고 싶어요", ""): ("UNSAFE", "S6")}))
    v = g.check_input("다 놓아 버리고 싶어요")
    assert v.level == "soft" and v.alert and "model:S6" in v.reasons


def test_other_model_categories_are_logged_only(fake_guard):
    g = Guard(SafetyLexicon(), fake_guard({("나는 혐오스럽다", ""): ("UNSAFE", "S1")}))
    v = g.check_input("나는 혐오스럽다")
    assert v.level == "safe" and "model:S1:note" in v.reasons


@pytest.mark.parametrize("text,stop", [
    ("그만", True), ("그만할래요.", True), ("중단해 주세요", True),
    ("그만큼 커요", False), ("그만두고 싶은 마음이 덩어리 같아요", False),
])
def test_stop_is_whole_message_only(text, stop):
    assert SafetyLexicon().is_stop(text) is stop


@pytest.mark.parametrize("text,no_more", [
    ("없어요", True), ("아니요", True), ("잘 모르겠어요", True), ("더는 없어요", True), ("넘어갈게요", True),
    ("음 그냥 좀 답답해요", False), ("모르겠는데 가슴 안쪽이 꽉 막힌 느낌이 계속 있어요", False),
])
def test_no_more(text, no_more):
    assert SafetyLexicon().is_no_more(text) is no_more


def test_depth_markers():
    s = SafetyLexicon()
    d = s.depth("어릴 때 교실에서 망신당한 장면이 떠올라요")
    assert {x["id"] for x in d["strong"]} >= {"childhood", "abuse"}
    assert s.depth("회색 덩어리") == {"strong": [], "weak": []}
    assert s.has_depth_marker("엄마 목소리")
