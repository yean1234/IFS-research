import pytest

from ifs_chatbot.extract import Extractor, find_modality, parse_body_relation
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.paths import shared


@pytest.fixture(scope="module")
def ex():
    a = Analyzer()
    return Extractor(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), a), a)


def test_notion_example_sentence(ex):
    """「심상 텍스트 3D 시각화 프로젝트」의 대표 입력 예시."""
    r = ex.run("가슴 안쪽에 젖은 종이처럼 눅눅하고 가장자리가 삭아가는 회색 덩어리가 있어요")
    lemmas = {a["lemma"] for a in r["attributes"]}
    assert {"회색", "눅눅", "삭", "덩어리", "젖"} <= lemmas
    assert [s["sourceNoun"] for s in r["similes"]] == ["종이"]
    gray = next(a for a in r["attributes"] if a["lemma"] == "회색")
    assert gray["_provenance"] == {"source": "explicit_lexicon", "trigger": "회색", "charSpan": [31, 33], "rule": "colorLexicon.회색"}
    assert gray["value"]["hsl"] == [0, 0.05, 0.45]                 # 노션 예시 출력과 같은 값


def test_only_stated_slots_are_filled(ex):
    d = ex.run("회색이고 무거워요")["sceneSpecDraft"]
    assert set(d["slots"]) == {"material.color", "physical.weight"}
    assert "layout.size" in d["unspecified"] and "material.brightness" in d["unspecified"]


def test_negation_is_not_turned_into_a_value(ex):
    d = ex.run("무겁진 않아요")["sceneSpecDraft"]
    assert "physical.weight" not in d["slots"] and d["negated"][0]["lemma"] == "무겁"


def test_simile_prototype_and_pending(ex):
    sims = {s["sourceNoun"]: s for s in ex.run("안개 같은 것이 종이처럼 얇아요")["similes"]}
    assert sims["안개"]["formPrototype"] == "mist"
    assert sims["종이"]["formPrototype"] is None and sims["종이"]["method"].startswith("pending")


def test_posture_and_self_reference_are_unresolved(ex):
    d = ex.run("검은 벽 뒤에 웅크린 작은 나")["sceneSpecDraft"]
    kinds = {u["slot"] for u in d["unresolved"]}
    assert {"posture", "selfReference"} <= kinds
    assert d["slots"]["layout.size"]["value"]["size"] == "small"


def test_same_text_same_result(ex):
    t = "젖은 종이처럼 축 처진 덩어리 같아요\n회색이고 무거워요"
    assert ex.run(t) == ex.run(t)    # 화이트박스: 같은 확정 텍스트 → 같은 결과


def test_body_relation_and_modality():
    a = Analyzer()
    lx = Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), a)
    br = parse_body_relation("가슴 안쪽이요", lx, False)
    assert (br["part"], br["layer"], br["ifsLocation"]) == ("chest", "inner", "in")
    assert parse_body_relation("주변이요", lx, False)["ifsLocation"] == "around"
    assert parse_body_relation("잘 모르겠어요", lx, True)["status"] == "unspecified"
    assert "body_sensation" in find_modality("가슴이 좀 답답해요", lx)["labels"]
    assert "sound_or_voice" in find_modality("낮게 웅웅거리는 목소리처럼 느껴져요", lx)["labels"]
    assert "emotion" in find_modality("감정으로 느껴진다", lx)["labels"]
