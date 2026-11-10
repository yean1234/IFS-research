"""2단계: 확정 텍스트 → SceneSpec v2 변환 함수 (화이트박스 3층)."""
import json
from pathlib import Path

import pytest

from ifs_chatbot.korean import Analyzer
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder import SceneSpecBuilder, dumps
from ifs_chatbot.scene_spec import SLOT_PATHS, check_principles, schema

FIXTURES = Path(__file__).parent / "fixtures" / "scene_spec"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def builder():
    a = Analyzer()
    if not a.available:
        pytest.skip("kiwipiepy가 없으면 0층이 정규식 대체라 정답과 다르다")
    return SceneSpecBuilder(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), a), a)


def build(builder, text, **meta):
    spec = builder.build(text, **meta)
    assert check_principles(spec, text) == [], "원칙 3·4 위반"
    return spec


def values(spec):
    return {p: spec[p.split(".")[0]][p.split(".")[1]] for p in SLOT_PATHS}


# ── 정답 일치 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_matches_golden_including_provenance(builder, case):
    expected = json.loads((FIXTURES / case["file"]).read_text(encoding="utf-8"))
    got = build(builder, case["confirmedText"], session_id=case["sessionId"],
                participant_id=case["participantId"], condition=case["condition"])
    assert got == expected


# ── 결정론 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [c["confirmedText"] for c in CASES] + [
    "젖은 종이처럼 축 처진 덩어리 같아요\n회색이고 무거워요. 바닥에 눌어붙은 것 같아요",
    "슬프고 무거운데 구름처럼 떠다녀요",
])
def test_same_input_same_output(builder, text):
    first, second = builder.build(text, session_id="S1"), builder.build(text, session_id="S1")
    assert first == second
    assert dumps(first) == dumps(second)                          # 파일 바이트까지 같다
    a = Analyzer()
    fresh = SceneSpecBuilder(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), a), a)
    assert dumps(fresh.build(text, session_id="S1")) == dumps(first)   # 새 인스턴스여도 같다


# ── 부정 표현 ───────────────────────────────────────────────────────────────
def test_negation_is_not_put_into_the_slot(builder):
    spec = build(builder, "무겁진 않아요")
    assert [n["lemma"] for n in spec["_negated"]] == ["무겁"]
    assert spec["_unmapped"] == [] and spec["_provenance"] == {}

    spec = build(builder, "회색인데 밝지 않아요")
    assert spec["material"]["brightness"] is None                 # '밝'을 bright로 넣지 않는다
    assert spec["material"]["color"] == {"h": 0.0, "s": 0.05, "l": 0.45}
    assert [n["lemma"] for n in spec["_negated"]] == ["밝"]
    assert "material.brightness" not in spec["_inferred"]          # 3층도 부정을 뒤집어 채우지 않는다


def test_negated_movement_means_still(builder):
    spec = build(builder, "움직임은 없어요")
    assert spec["motion"]["type"] == "still"
    assert spec["_provenance"]["motion.type"][0]["rule"].endswith("motion.type:still(negated)")


# ── 사전에 없는 단어 ────────────────────────────────────────────────────────
def test_unknown_words_go_to_unmatched(builder):
    spec = build(builder, "회색 해파리가 너울거려요")
    assert [(u["lemma"], u["surface"]) for u in spec["_unmatched"]] == [("해파리", "해파리"), ("너울거리", "너울거려")]
    assert values(spec)["material.color"] is not None
    assert values(spec)["form.type"] is None                        # 모르는 말에서 형태를 짐작하지 않는다


def test_known_but_unmappable_words_go_to_unmapped_not_unmatched(builder):
    spec = build(builder, "가장자리가 차가워요")
    assert spec["_unmatched"] == []
    assert {(u["lemma"], u["reason"]) for u in spec["_unmapped"]} == {("가장자리", "no_scene_param"), ("차갑", "no_scene_param")}


# ── 층 우선순위 ─────────────────────────────────────────────────────────────
def test_layer1_beats_layer2(builder):
    spec = build(builder, "구름처럼 생긴 덩어리가 있어요")
    assert spec["form"]["type"] == "blob"
    assert spec["_provenance"]["form.type"][0]["source"] == "explicit_lexicon"
    alt = spec["_alternatives"][0]
    assert (alt["path"], alt["value"], alt["reason"], alt["_provenance"][0]["source"]) == \
        ("form.type", "mist", "lower_layer", "simile_marker")


def test_layer2_simile_prototype_when_no_form_word(builder):
    spec = build(builder, "구름처럼 떠다녀요")
    assert spec["form"]["type"] == "mist"
    assert spec["_provenance"]["form.type"] == [{"source": "simile_marker", "trigger": "구름처럼", "charSpan": [0, 4],
                                                 "rule": "simile.처럼>prototype.구름>form.type:mist"}]


def test_modifier_inside_simile_is_layer2(builder):
    """'젖은 종이처럼'의 '젖은'은 비유 대상의 속성 → 1층 '눅눅하고'에 밀린다."""
    spec = build(builder, CASES[0]["confirmedText"])
    assert spec["material"]["roughness"] == 0.35
    assert spec["_alternatives"][0]["_provenance"][0]["trigger"] == "젖은"


def test_layer3_only_suggests_and_never_fills_values(builder):
    spec = build(builder, "슬프고 작아요")
    assert spec["layout"]["size"] == 0.316                          # 말한 값(1층)
    assert spec["material"]["brightness"] is None                   # 말하지 않은 값은 null 그대로
    assert set(spec["_inferred"]) == {"material.brightness", "motion.speed"}   # 크기는 말했으니 제안도 없다
    assert spec["_inferred"]["material.brightness"]["value"] == 0.15
    assert spec["_inferred"]["material.brightness"]["_provenance"][0]["source"] == "vad_lexicon"


def test_body_layer_needs_body_part_on_same_line(builder):
    spec = build(builder, "검은 벽 뒤에 웅크린 작은 나")
    assert spec["body"]["layer"] is None
    assert ("뒤", "no_body_part_context") in {(u["lemma"], u["reason"]) for u in spec["_unmapped"]}
    assert build(builder, "가슴 안쪽이요")["body"] == {"part": "chest", "layer": "inner"}


def test_first_mention_wins_within_a_layer(builder):
    spec = build(builder, "회색이었다가 까맣게 돼요")
    assert spec["material"]["color"]["l"] == 0.45
    assert [a["reason"] for a in spec["_alternatives"]] == ["later_mention"]


def test_common_color_compounds_missing_from_lexicon_are_reported(builder):
    """'검은색'·'파란색'은 1층 사전 v0.1.0에 없다 → 값을 짐작하지 않고 _unmatched에 남는다(사전 보강 대상)."""
    spec = build(builder, "검은색이에요")
    assert spec["material"]["color"] is None
    assert [u["surface"] for u in spec["_unmatched"]] == ["검은색"]


# ── 사전끼리의 정합 ─────────────────────────────────────────────────────────
def _schema_enum(path):
    g, k = path.split(".")
    return set(schema()["properties"][g]["properties"][k]["enum"]) - {None}


def test_lexicon_values_fit_schema_and_units():
    layer1 = json.loads(shared("lexicon", "layer1_lexicon.v0.json").read_text(encoding="utf-8"))
    params = json.loads(shared("lexicon", "scene_params.v0.json").read_text(encoding="utf-8"))
    vad = json.loads(shared("lexicon", "vad_ko.v0.json").read_text(encoding="utf-8"))
    for cat, targets in params["layer1"].items():
        assert cat in layer1["categories"], cat
        for t in targets:
            assert t["path"] in SLOT_PATHS
            for v in t.get("values", {}).values():
                assert 0.0 <= v <= 1.0, (cat, t["path"], v)
            if t.get("transform") == "enum":
                used = {e["value"][t["key"]] for e in layer1["entries"] if e["category"] == cat and t["key"] in e["value"]}
                assert used <= _schema_enum(t["path"]), (t["path"], used - _schema_enum(t["path"]))
    assert set(params["layer2"]["prototypes"].values()) <= _schema_enum("form.type")
    emotions = {e["lemma"] for e in layer1["entries"] if e["category"] == "emotion"}
    assert emotions == {e["lemma"] for e in vad["entries"]}         # 감정어마다 V/A/D가 있다
    assert all(0.0 <= e[d] <= 1.0 for e in vad["entries"] for d in "vad")
