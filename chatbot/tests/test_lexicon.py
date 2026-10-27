import pytest

from ifs_chatbot.korean import Analyzer
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.paths import shared


@pytest.fixture(scope="module")
def lx():
    return Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), Analyzer())


def test_every_entry_matches_its_example(lx):
    """사전 품질 검사: 모든 항목의 예시(ex)를 Kiwi로 분석하면 그 항목이 걸려야 한다."""
    missing = [(e.key, e.ex) for e in lx.entries if e.key not in lx.keys(e.ex)]
    assert missing == []


def test_irregular_and_hada_forms(lx):
    assert "weight:무겁" in lx.keys("회색이고 좀 무거워요")
    assert "sensation:답답" in lx.keys("가슴이 좀 답답해요")
    assert "texture:촉촉" in lx.keys("촉촉한 느낌")            # Kiwi가 '촉촉하/VA'로 내는 경우
    assert "color:보라" in lx.keys("보랏빛 안개")              # alt 형태
    assert "opacity:불투명" in lx.keys("불투명한 막")           # 부정 접두사 합치기


def test_negation_and_change(lx):
    hits = {h.entry.key: h for h in lx.hits("회색이고 무겁지 않아요")}
    assert not hits["color:회색"].negated and hits["weight:무겁"].negated
    assert lx.hits("움직임은 전혀 없어요")[0].negated
    assert lx.hits("너무 작아지는 느낌")[0].change == "becoming"


def test_self_reference_only_when_modified(lx):
    assert "self_reference:나" in lx.keys("웅크린 작은 나")
    assert "self_reference:저" not in lx.keys("저는 가슴이 답답해요")


def test_out_of_lexicon_word_is_not_matched(lx):
    # 「앞으로 개발 방향」이 든 사전 밖 단어의 예
    assert lx.hits("바닥에 눌어붙은 것 같아요") == []
