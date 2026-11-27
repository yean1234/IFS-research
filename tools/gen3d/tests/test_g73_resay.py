"""G73 CP13a: 다시 적은 글 → 갈래·형태 프롬프트·덮어쓰기 값. 생성기는 가짜(호출 횟수만 셈). 모델·GPU 없이 돈다.

  <venv>/python -m pytest tools/gen3d/tests/test_g73_resay.py -q

합성 대사만 쓴다(AGENTS.md 6). 대역 사전은 합성 시험 표(fixtures/bilingual_synthetic.v0.json), WordNet은 합성 표 백엔드.
실제 nltk WordNet 시험은 nltk와 데이터가 있을 때만 돈다(없으면 건너뜀, 내려받지 않음).
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

GEN3D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN3D))
pytest.importorskip("kiwipiepy")

import resay as rs  # noqa: E402
from bilingual import BilingualDict  # noqa: E402
from common import CHATBOT  # noqa: E402
from wordnet_filter import TableWordNet, WordNetFilter  # noqa: E402

sys.path.insert(0, str(CHATBOT))
from ifs_chatbot.config import Gen3DConfig, load_config  # noqa: E402
from ifs_chatbot.korean import Analyzer  # noqa: E402
from ifs_chatbot.resay import ResayMapper  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "bilingual_synthetic.v0.json"
FILT = rs.load_filter()
P = ["physical_entity.n.01", "entity.n.01"]
ART = ["artifact.n.01", "whole.n.02", "object.n.01", *P]
WN_TABLE = {
    "pebble": [["pebble.n.01", ["stone.n.02", "natural_object.n.01", "whole.n.02", "object.n.01", *P]]],
    "pinecone": [["pinecone.n.01", ["cone.n.03", "plant_organ.n.01", "natural_object.n.01", *P]]],
    "kettle": [["kettle.n.01", ["pot.n.01", *ART]]],
    "bell": [["bell.n.01", ["acoustic_device.n.01", *ART]]],
    "gong": [["gong.n.01", ["percussion_instrument.n.01", *ART]]],
    "car": [["car.n.01", ["motor_vehicle.n.01", *ART]]],
    "cart": [["cart.n.01", ["wheeled_vehicle.n.01", *ART]]],
    "tea": [["tea.n.01", ["beverage.n.01", "food.n.01", "substance.n.01", "matter.n.03", *P]]],
    "drum": [["drum.n.01", ["percussion_instrument.n.01", *ART]]],
    "north": [["north.n.01", ["direction.n.02", "abstraction.n.06", "entity.n.01"]]],
    "perfume": [["perfume.n.01", ["toiletry.n.01", *ART]]],
    "nostalgia": [["nostalgia.n.01", ["longing.n.01", "feeling.n.01", "state.n.02", "attribute.n.02",
                                      "abstraction.n.06", "entity.n.01"]]],
    "finch": [["finch.n.01", ["passerine.n.01", "bird.n.01", "vertebrate.n.01", "animal.n.01", "organism.n.01", *P]]],
    "anxiety": [["anxiety.n.01", ["emotion.n.01", "feeling.n.01", "abstraction.n.06", "entity.n.01"]]],
    "fog": [["fog.n.01", ["cloud.n.01", "physical_phenomenon.n.01", *P]]],
    "doll": [["doll.n.01", ["plaything.n.01", *ART]]],
}
FOG = {
    "검은 안개가 있는 느낌": {"form.type": "mist"},
    "구름 같은데 구름 보다는 덜 뺵뺵하고 보이지 않는 안개같은?": {"form.type": "mist", "mist.density": 0.4,
                                                       "material.opacity": 0.15},
    "먹구름": {"form.type": "mist"},
    "넓게 펼쳐진 안개가 떠오른다": {"form.type": "mist",
                            "layout.proportions": {"x": 1.0, "y": 0.3, "z": 1.0, "axisSaid": True}},
}


class FakeGenerator:
    def __init__(self):
        self.calls = []

    def __call__(self, text, negative, seed):
        self.calls.append((text, negative, seed))
        return {"fake": True, "seed": seed}


@pytest.fixture(scope="module")
def mapper():
    return ResayMapper(Analyzer())


def wn_table():
    return WordNetFilter(FILT, TableWordNet(WN_TABLE))


def pipe(mapper, *, enabled=True, bilingual="fixture", wordnet="table", **cfg):
    c = replace(Gen3DConfig(), resay=enabled, **cfg)
    bd = BilingualDict.load(FIX) if bilingual == "fixture" else bilingual
    wn = wn_table() if wordnet == "table" else wordnet
    return rs.ResayPipeline(c, mapper=mapper, bilingual=bd, wordnet=wn, filt=FILT)


def content(p):
    return [t for t in p["tokens"] if t["slot"] != "template"]


# ── 설정: 기본 끔, 꺼지면 아무것도 하지 않음 ─────────────────────────────────────────
def test_resay_off_by_default_in_code_and_every_config_file():
    """기본 끔. CP13b(G73-g)부터 v4-gen3d.toml 하나만 켠다(본 실험 experiment.toml은 끔)."""
    assert Gen3DConfig().resay is False
    for f in sorted((CHATBOT / "config").glob("*.toml")):
        assert load_config(f).gen3d.resay is (f.name == "v4-gen3d.toml"), f.name


def test_disabled_does_nothing_not_even_mapping():
    class Boom:
        def map(self, text):
            raise AssertionError("꺼진 설정에서 매핑을 부름")

        def crisis_hits(self, text):
            raise AssertionError("꺼진 설정에서 안전 사전을 부름")

    g = FakeGenerator()
    p = rs.ResayPipeline(Gen3DConfig(), mapper=Boom(), safety=Boom(), filt=FILT)
    assert p.run("둥근 덩어리예요", generator=g) == {"status": "disabled", "generatorCalls": 0}
    assert g.calls == []


def test_round_limit_from_config(mapper):
    g = FakeGenerator()
    r = pipe(mapper, resay_max_rounds=2).run("둥근 덩어리예요", round_no=3, generator=g)
    assert r["status"] == "round_limit" and g.calls == []


# ── 안개 사례 4문장: mist 갈래 + 값, 생성기 0회 ───────────────────────────────────────
@pytest.mark.parametrize("text", list(FOG))
def test_fog_cases_go_to_mist_values_without_generator(mapper, text):
    g = FakeGenerator()
    r = pipe(mapper).run(text, generator=g)
    assert r["status"] == "ok" and r["branch"] == "mist"
    assert r["generatorCalls"] == 0 and g.calls == [] and r["prompt"] is None
    got = {k: v["value"] for k, v in r["mapping"]["values"].items() if v is not None}
    assert got == FOG[text]


# ── 위기: 매핑·생성기 모두 건너뜀 ───────────────────────────────────────────────────
def test_crisis_keyword_skips_mapping_and_generator():
    class NoMap:
        def map(self, text):
            raise AssertionError("위기 뒤에 매핑을 부름")

    g = FakeGenerator()
    p = rs.ResayPipeline(replace(Gen3DConfig(), resay=True), mapper=NoMap(), wordnet=wn_table(), filt=FILT)
    r = p.run("죽고 싶은 마음이 둥근 공처럼 있어요", generator=g)
    assert r["status"] == "crisis" and r["generatorCalls"] == 0 and g.calls == [] and "mapping" not in r


# ── 갈래 solid: 손 사전 → 대역 사전 → WordNet ─────────────────────────────────────────
def test_hand_lexicon_prompt_one_call_with_charspans(mapper):
    g = FakeGenerator()
    r = pipe(mapper).run("둥근 덩어리가 있어요", generator=g)
    assert r["branch"] == "solid" and r["prompt"]["status"] == "ok"
    (p,) = r["prompt"]["prompts"]
    assert p["text"].split(",")[0] == "a single round lump"
    assert all(t["source"] == "lexicon" for t in content(p))
    assert len(g.calls) == 1 and g.calls[0][2] == 10          # seed = 기준 0 + 회차 1 × 10 + 0


def test_bilingual_noun_enters_prompt_with_audit_fields(mapper):
    text = "둥근 조약돌이 있어요"
    r = pipe(mapper).run(text, generator=FakeGenerator())
    (p,) = r["prompt"]["prompts"]
    assert p["text"].split(",")[0] == "a single round pebble"
    bi = [t for t in content(p) if t["source"] == "bilingual_dict"]
    assert len(bi) == 1 and bi[0]["dictEntryId"] == "syn-0001" and bi[0]["wordnet"] == "pebble.n.01"
    for t in content(p):                                       # 모든 내용 낱말이 원문 글자 위치로 거슬러 감
        s, e = t["charSpan"]
        assert text[s:e] == t["ko"]
    info = r["prompt"]["bilingualDict"]
    assert info["sha256"] and info["status"] == "synthetic-test-only" and info["dictVersion"] == "0.1.0"


def test_translation_not_in_wordnet_is_dropped_but_other_sense_kept(mapper):
    r = pipe(mapper).run("솔방울이 있어요", generator=FakeGenerator())
    (p,) = r["prompt"]["prompts"]                              # 'pine cone'은 합성 WordNet에 없음 → 판정 불가 → 버림
    assert p["text"].split(",")[0] == "a single pinecone" and p["sense"] is None


@pytest.mark.parametrize("bilingual,wordnet,reason", [
    (None, "table", "no_bilingual_dict"),
    ("fixture", "unavailable", "wordnet_unavailable"),
])
def test_unjudged_head_noun_fails_closed(mapper, bilingual, wordnet, reason):
    wn = WordNetFilter(FILT, None, "wordnet_unavailable") if wordnet == "unavailable" else wordnet
    g = FakeGenerator()
    r = pipe(mapper, bilingual=bilingual, wordnet=wn).run("주전자가 있어요", generator=g)
    assert r["branch"] == "solid" and r["prompt"]["status"] == "blocked"
    assert r["prompt"]["blockReason"] == "unjudged_head_noun" and reason in r["prompt"]["blockDetail"]
    assert g.calls == []


def test_two_senses_make_one_prompt_per_sense(mapper):
    g = FakeGenerator()
    r = pipe(mapper).run("종이 있어요", generator=g)
    ps = r["prompt"]["prompts"]
    assert [p["text"].split(",")[0] for p in ps] == ["a single bell", "a single gong"]
    assert [p["sense"]["index"] for p in ps] == [0, 1] and all(p["sense"]["of"] == 2 for p in ps)
    assert [c[2] for c in g.calls] == [10, 11]


def test_two_senses_respect_candidate_limit(mapper):
    g = FakeGenerator()
    pipe(mapper, resay_candidates=1).run("종이 있어요", generator=g)
    assert len(g.calls) == 1


def test_three_senses_are_discarded_and_head_fails_closed(mapper):
    g = FakeGenerator()
    r = pipe(mapper).run("차가 있어요", generator=g)
    assert r["prompt"]["blockReason"] == "unjudged_head_noun" and "ambiguous_sense" in r["prompt"]["blockDetail"]
    assert g.calls == []


def test_non_physical_and_psychological_senses_are_dropped(mapper):
    r = pipe(mapper).run("북이 있어요", generator=FakeGenerator())
    assert r["prompt"]["prompts"][0]["text"].split(",")[0] == "a single drum"      # north(방향) 버림
    r = pipe(mapper).run("향수 같은 공이 있어요", generator=FakeGenerator())
    first = r["prompt"]["prompts"][0]["text"].split(",")[0]
    assert first == "a single perfume-like ball" and "nostalgia" not in first        # 감정 뜻 버림


def test_unusable_translation_format_is_dropped(mapper):
    r = pipe(mapper).run("고깔 같은 공이 있어요", generator=FakeGenerator())
    p = r["prompt"]["prompts"][0]
    assert p["text"].split(",")[0] == "a single ball" and "(" not in p["text"]


# ── 사람·동물·인형·마스코트 차단 ───────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["작은 인형 같아요", "곰인형이 있어요", "마스코트 같은 거예요", "로봇 모양이에요",
                                  "캐릭터 같은 덩어리", "고양이가 있어요", "얼굴이 있어요", "허수아비 같은 게 있어요"])
def test_people_animals_dolls_mascots_blocked_by_mapping(mapper, text):
    g = FakeGenerator()
    r = pipe(mapper).run(text, generator=g)
    assert r["branch"] == "blocked" and r["generatorCalls"] == 0 and g.calls == [], r["mapping"]["formWords"]


@pytest.mark.parametrize("text,reason", [("목각상이 있어요", "humanlike_object"),
                                         ("방울새 같은 게 있어요", "wordnet_category")])
def test_bilingual_humanlike_or_animal_translation_blocks_generation(mapper, text, reason):
    g = FakeGenerator()
    r = pipe(mapper).run(text, generator=g)
    assert r["branch"] == "solid" and r["prompt"]["blockReason"] == reason and g.calls == []


def test_nonmeshable_simile_still_blocked_like_g62(mapper):
    g = FakeGenerator()
    r = pipe(mapper).run("연기 같은 공이 있어요", generator=g)
    assert r["branch"] == "solid"
    assert r["prompt"]["blockReason"] == "excluded_category"
    assert g.calls == []


# ── 감정·감각·위기어는 프롬프트에 들어가지 않음 ─────────────────────────────────────────
@pytest.mark.parametrize("text", ["불안 같은 공이 있어요", "슬픈 덩어리가 있어요", "답답한 느낌의 돌이 있어요",
                                  "무서운 상자가 있어요", "외로움 같은 구슬이에요"])
def test_emotion_words_never_in_prompt(mapper, text):
    r = pipe(mapper).run(text, generator=FakeGenerator())
    assert r["prompt"]["status"] == "ok"
    for p in r["prompt"]["prompts"]:
        for bad in ("anxiety", "sad", "fear", "scary", "lonely", "frustrat", "feeling", "emotion"):
            assert bad not in p["text"].lower()
        assert all(t["ko"] not in mapper.emotion_words for t in content(p))


def test_prompt_length_limits(mapper):
    r = pipe(mapper).run("둥글고 납작하고 길쭉하고 뾰족한 덩어리가 있어요", generator=FakeGenerator())
    p = r["prompt"]["prompts"][0]
    mods = [t for t in content(p) if t["slot"] == "shape_modifier"]
    assert len(mods) == 2 and any(d["reason"] == "prompt_limit" for d in p["dropped"])


# ── 결정성 ───────────────────────────────────────────────────────────────────
def _dump(r):
    return json.dumps(r, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


@pytest.mark.parametrize("text", [*FOG, "둥근 조약돌이 있어요", "종이 있어요", "빛줄기가 비쳐요", "작은 인형 같아요"])
def test_same_text_same_bytes(mapper, text):
    a = pipe(mapper).run(text, generator=FakeGenerator())
    b = pipe(ResayMapper(Analyzer())).run(text, generator=FakeGenerator())
    assert _dump(a) == _dump(b)


def test_same_bytes_across_processes(mapper):
    code = (
        "import sys, json; sys.path.insert(0, %r); sys.path.insert(0, %r);"
        "from ifs_chatbot.korean import Analyzer; from ifs_chatbot.resay import ResayMapper, mapping_bytes;"
        "m = ResayMapper(Analyzer()); sys.stdout.buffer.write(b''.join(mapping_bytes(m.map(t)) for t in %r))"
    ) % (str(GEN3D), str(CHATBOT), list(FOG))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, check=True).stdout
    from ifs_chatbot.resay import mapping_bytes
    assert out == b"".join(mapping_bytes(mapper.map(t)) for t in FOG)


def test_dict_sha_changes_with_dict_bytes(tmp_path, mapper):
    d = json.loads(FIX.read_text(encoding="utf-8"))
    d["dictVersion"] = "0.1.1"
    p2 = tmp_path / "d.json"
    p2.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    a = pipe(mapper).run("둥근 조약돌이 있어요", generator=FakeGenerator())
    b = pipe(mapper, bilingual=BilingualDict.load(p2)).run("둥근 조약돌이 있어요", generator=FakeGenerator())
    assert a["prompt"]["prompts"][0]["text"] == b["prompt"]["prompts"][0]["text"]
    assert a["prompt"]["bilingualDict"]["sha256"] != b["prompt"]["bilingualDict"]["sha256"]


def test_bilingual_dict_rejects_bad_format(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"dictId": "x", "entries": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        BilingualDict.load(bad)


# ── WordNet 거르개 ─────────────────────────────────────────────────────────────
def test_wordnet_table_judgements():
    wn = wn_table()
    assert wn.judge("pebble")["verdict"] == "pass"
    assert wn.judge("finch")["verdict"] == "block" and wn.judge("finch")["reason"].startswith("animal")
    assert wn.judge("doll")["reason"].startswith("humanlike")
    assert wn.judge("fog")["reason"].startswith("nonMeshable")
    assert wn.judge("anxiety")["verdict"] == "drop" and wn.judge("north")["reason"] == "non_physical"
    assert wn.judge("zzz")["verdict"] == "unjudgeable"


def test_wordnet_unavailable_judges_nothing():
    wn = WordNetFilter(FILT, None, "nltk_not_installed")
    assert not wn.available and wn.judge("pebble")["verdict"] == "unjudgeable"
    assert wn.info() == {"available": False, "reason": "nltk_not_installed", "senseScope": "dominant"}


def test_real_nltk_wordnet_if_present():
    """nltk와 WordNet 데이터가 있을 때만(이 venv에는 nltk가 없어 건너뜀). 내려받지 않는다."""
    wn = WordNetFilter.auto(FILT)
    if not wn.available:
        pytest.skip(f"WordNet 없음: {wn.unavailable_reason}")
    assert wn.info()["wordnetVersion"] == "3.0"
    assert wn.judge("pebble")["verdict"] == "pass" and wn.judge("ball")["verdict"] == "pass"
    for en, cat in (("doll", "humanlike"), ("mascot", "organism"), ("fog", "nonMeshable"), ("figurine", "humanlike")):
        assert wn.judge(en)["reason"].startswith(cat), en
    assert wn.judge("anxiety")["verdict"] == "drop"
