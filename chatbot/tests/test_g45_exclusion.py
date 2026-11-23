"""연구 책임자 결정 G45–G51(제외 낱말) — 중심 명사 규칙, 범주(person·threat·weapon·death_self_harm_trauma·동물), 낱말 추가,
기록(자리마다 글자 위치·문장 번호), 판정 못 하는 문형의 보수적 기본, 넷째 범주의 엄격 처리와 실험자 표시.
세부: docs/decisions.md 'G45–G51 구현 세부', 문형 표: docs/validation/mapper-v2/head-noun-patterns.md.
모든 문장은 합성 대사다(AGENTS.md 6). held-out 코퍼스는 열지 않는다."""
import json
import re
from pathlib import Path

import pytest

from ifs_chatbot.candidates import (form_blocks, form_said_unrendered, generate, listed_heads, load_table, safety_flags,
                                    shape_words, unrendered_said_words)
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2
from ifs_chatbot.scene_spec import check_principles, schema_errors

from test_selection_flow import done_session, rt4, runner_contract_errors, started, valid  # noqa: F401

LEX = json.loads(shared("lexicon", "base_shapes.v1.json").read_text(encoding="utf-8"))
TABLE = load_table()
CATS = LEX["excluded"]["categories"]


@pytest.fixture(scope="module")
def an():
    a = Analyzer()
    if not a.available:
        pytest.skip("kiwipiepy가 없으면 형태소 판정을 확인할 수 없다")
    return a


@pytest.fixture(scope="module")
def v2(an):
    return SceneSpecBuilderV2(an)


def build(v2, text):
    spec = v2.build(text, session_id="SYN-G45")
    assert check_principles(spec, normalize_confirmed(text)) == [], text
    assert schema_errors(spec) == [], text
    return spec


def recs(spec, lemma=None):
    """그리지 않은 기록(제외 범주 excluded_shape · 동물 no_asset)."""
    return [u for u in spec["_unmapped"] if u["reason"] in ("excluded_shape", "no_asset")
            and (lemma is None or u["lemma"] == lemma)]


def form_axis(spec):
    out = generate(spec, "SYN-G45", TABLE)
    return next((ax for ax in out["axes"] if ax["slot"] == "form.type"), None), out


# ── G46·G47·G50·G51 사전 범주 ─────────────────────────────────────────────
def test_categories_are_the_decided_four_plus_animal():
    assert set(CATS) == {"person", "threat", "weapon", "death_self_harm_trauma"}
    assert [k for k, d in CATS.items() if d["strict"]] == ["death_self_harm_trauma"]        # G50: 넷째 범주만 엄격
    assert set(k for k in LEX["noAsset"] if not k.startswith("_")) == {"animal"}
    animal = LEX["noAsset"]["animal"]
    assert {"뱀", "구렁이"} <= set(animal["words"])                                          # G51
    assert "뱀" not in {w for d in CATS.values() for w in [*d["words"], *d["added"]["words"]]}
    # G50: 0.6.0의 죽음·외상과 피·올가미를 넷째 범주로 옮김(지우지 않음)
    assert {"죽음", "시체", "송장", "무덤", "지옥", "해골", "피", "올가미"} <= set(CATS["death_self_harm_trauma"]["words"])
    assert {"핏자국", "핏물", "핏덩이", "핏줄", "피눈물", "핏방울", "핏빛", "무덤가"} <= set(CATS["death_self_harm_trauma"]["compounds"])


def test_added_words_are_draft_and_marked_added():
    """G47·G50: 같은 범주의 비슷한 말(어린이·귀신 등)은 0.7.0에서 보탬 — 초안, 출처 [보]."""
    for d in [*CATS.values(), LEX["noAsset"]["animal"]]:
        add = d["added"]
        assert add["status"] == "draft" and add["source"] == "added" and add["version"] == "0.7.0"
    assert {"어린이", "꼬맹이"} <= set(CATS["person"]["added"]["words"])
    assert "귀신" in CATS["threat"]["added"]["words"]
    assert {"구렁이"} <= set(LEX["noAsset"]["animal"]["words"]) and "독사" in LEX["noAsset"]["animal"]["added"]["words"]
    # 합성어 23개(0.6.0) + 핏덩어리(0.7.0). 용도 설명이 사전에 있음
    # 0.6.0 합성어는 실제로 21개(decisions.md 'CP10 반영 세부'·G47의 '23개'는 잘못 센 수) + 핏덩어리(0.7.0)
    assert sum(len(d["compounds"]) for d in CATS.values()) == 22
    assert "뒷부분" in LEX["excludedCompounds"]["_comment"] and "에셋" in LEX["excludedCompounds"]["_comment"]


def test_listed_words_are_single_noun_tokens(an):
    """목록 낱말은 Kiwi 명사 한 토큰이어야 형태소 단위로 맞는다(G50 (3))."""
    words = {w for d in CATS.values() for w in [*d["words"], *d["added"]["words"], *d["compounds"]]}
    words |= {w for w in [*LEX["noAsset"]["animal"]["words"], *LEX["noAsset"]["animal"]["added"]["words"]]}
    listed = words
    for w in sorted(words):
        toks = [t for t in an.tokens(f"{w} 같아요.") if t.base_tag in ("NNG", "NNP")]
        # '어린아이'(0.6.0 낱말)는 Kiwi가 어리 + ㄴ + 아이로 자른다 — 마지막 명사 '아이'가 목록 낱말이라 같은 범주로 잡힘
        assert [t.form for t in toks] == [w] or (toks and toks[-1].form in listed), \
            (w, [(t.form, t.base_tag) for t in an.tokens(f"{w} 같아요.")])


def test_no_listed_word_is_a_base_shape_entry():
    lemmas = {e["lemma"] for e in LEX["entries"]}
    words = {w for d in CATS.values() for w in [*d["words"], *d["added"]["words"], *d["compounds"]]}
    assert not words & lemmas


# ── G45 중심 명사 규칙: 경계 사례(이전 CP10 사례를 새 결정에 맞게) ─────────
# (문장, 그려지는 기본 형상, 기록 [(낱말, 사유, 범주, 자리)])
DRAWN = [
    ("뱀 같은 끈이 있어요.", "line", [("뱀", "no_asset", "animal", "simile_source")]),                   # G45·G51
    ("뱀처럼 생긴 끈이에요.", "line", [("뱀", "no_asset", "animal", "simile_source")]),
    ("끈이 있는데 뱀 같아요.", "line", [("뱀", "no_asset", "animal", "simile_source")]),                 # 서술형 비교, 주어 = 끈
    ("구렁이 같은 끈이 있어요.", "line", [("구렁이", "no_asset", "animal", "simile_source")]),
    ("아이 장난감 상자예요.", "container", [("아이", "excluded_shape", "person", "modifier")]),
    ("아기 그릇이 있어요.", "container", [("아기", "excluded_shape", "person", "modifier")]),
    ("어린이 그릇이 있어요.", "container", [("어린이", "excluded_shape", "person", "modifier")]),       # G47 추가 낱말
    ("아이의 상자예요.", "container", [("아이", "excluded_shape", "person", "modifier")]),               # 소유(JKG)
    ("괴물 같은 불꽃이 있어요.", "flame", [("괴물", "excluded_shape", "threat", "simile_source")]),
    ("귀신 같은 막이 있어요.", "sheet", [("귀신", "excluded_shape", "threat", "simile_source")]),
    ("칼날 같은 불꽃이 있어요.", "flame", [("칼날", "excluded_shape", "weapon", "simile_source")]),
    ("아이 같은 불꽃이 있어요.", "flame", [("아이", "excluded_shape", "person", "simile_source")]),
    ("사람 그림자 같은 실이 있어요.", "line", [("사람", "excluded_shape", "person", "simile_source")]),  # lightHeads '그림자'
    ("칼 모양의 그릇이에요.", "container", [("칼", "excluded_shape", "weapon", "modifier")]),
    ("뱀이 있고 끈도 있어요.", "line", [("뱀", "no_asset", "animal", "head")]),                       # 다른 주어는 막지 않음
    ("칼은 아니고 끈이에요.", "line", [("칼", "excluded_shape", "weapon", "head")]),                   # 부정된 제외 낱말
    ("칼 같은 건 아니고 끈이에요.", "line", [("칼", "excluded_shape", "weapon", "head")]),              # 부정된 비교도 막지 않음
    ("귀신이 아니라 그릇이에요.", "container", [("귀신", "excluded_shape", "threat", "head")]),
    ("꼬마전구 같은 불씨가 있어요.", "flame", [("꼬마", "excluded_shape", "person", "modifier")]),       # 전에 과잉 제외
    ("아이가 가진 상자예요.", "container", [("아이", "excluded_shape", "person", "head")]),             # 관형절 주어(별개 개체)
    ("그릇처럼 생긴 거예요.", "container", []),                                                        # 알려진 문제 고침
]


@pytest.mark.parametrize("text,base,expect", DRAWN)
def test_g45_modifier_or_simile_listed_word_draws_the_head_noun(v2, text, base, expect):
    spec = build(v2, text)
    assert spec["form"]["base"] == base, recs(spec)
    got = [(u["lemma"], u["reason"], u["value"].get("excluded") or u["value"].get("noAsset"), u["value"]["position"])
           for u in recs(spec) if "position" in u["value"]]
    assert got == expect
    for u in recs(spec):
        assert u["value"]["usedForShape"] is False
        assert u["value"]["formSaid"] is (u["value"].get("position") == "head" and not u["value"].get("negated", False))
    assert not form_said_unrendered(spec, TABLE)       # 그려진 형상이 있으면 형태 자리는 말한 자리


# (문장, 형상 자체인 낱말, 사유, 범주)
NOT_DRAWN = [
    ("끈 같은 뱀이 있어요.", "뱀", "no_asset", "animal"),
    ("뱀처럼 생긴 거예요.", "뱀", "no_asset", "animal"),
    ("뱀처럼 생긴 것이 있어요.", "뱀", "no_asset", "animal"),
    ("끈 같은 구렁이가 있어요.", "구렁이", "no_asset", "animal"),
    ("끈 같은 귀신이 있어요.", "귀신", "excluded_shape", "threat"),
    ("칼처럼 생긴 거예요.", "칼", "excluded_shape", "weapon"),
    ("칼날 같은 게 있어요.", "칼날", "excluded_shape", "weapon"),                  # 한 토큰 합성어
    ("칼집이 있어요.", "칼집", "excluded_shape", "weapon"),                         # 뜻의 중심은 '집'이지만 합성어 목록이 막음
    ("칼끝 같은 게 있어요.", "칼", "excluded_shape", "weapon"),                     # Kiwi 칼 + 끝, '끝'은 lightHeads
    ("사람 형상이에요.", "사람", "excluded_shape", "person"),
    ("사람 모습이 있어요.", "사람", "excluded_shape", "person"),
    ("작은 아이가 있어요.", "아이", "excluded_shape", "person"),
    ("여자아이가 있어요.", "아이", "excluded_shape", "person"),                     # Kiwi 여자 + 아이: 마지막 명사가 중심
    ("꼬맹이가 있어요.", "꼬맹이", "excluded_shape", "person"),
    ("귀신 같아요.", "귀신", "excluded_shape", "threat"),                           # 대상 없는 서술형 비교
    ("무언가 귀신 같아요.", "귀신", "excluded_shape", "threat"),
    ("칼 모양이에요.", "칼", "excluded_shape", "weapon"),
    ("칼은 아니고 칼처럼 생긴 거예요.", "칼", "excluded_shape", "weapon"),
    ("사람들 같은 게 있어요.", "사람", "excluded_shape", "person"),                 # '들'(XSN) 건너뜀
]


@pytest.mark.parametrize("text,word,reason,cat", NOT_DRAWN)
def test_g45_listed_head_is_not_drawn_and_goes_to_form_candidates(v2, text, word, reason, cat):
    """중심 명사가 목록 낱말이면 기본 형상·모양 모형을 내지 않고 형태 후보와 '맞는 것이 없다'로 넘어간다(G32와 같은 경로).
    기록에서 '모형이 없어서'(no_model)와 '제외 범주라서'(excluded_shape)·'동물 에셋 없음'(no_asset)이 갈린다."""
    spec = build(v2, text)
    assert spec["form"]["base"] is None and "form.base" not in spec["_provenance"]
    heads = listed_heads(spec)
    assert [(u["lemma"], u["reason"]) for u in heads] == [(word, reason)]
    v = heads[0]["value"]
    assert v["position"] == "head" and v["formSaid"] is True and (v.get("excluded") or v.get("noAsset")) == cat
    assert not shape_words(spec)                        # 막힌 모양어는 Unity가 모형으로 그리지 않음
    ax, out = form_axis(spec)
    assert ax is not None and ax["reason"] == "said_unrendered"
    assert [(w["lemma"], w["unrenderedBy"], w["category"]) for w in ax["saidWords"]] == [(word, reason, cat)]
    assert ax["saidWords"][0]["shape"] is None


def test_g45_simile_source_of_a_listed_head_is_blocked_not_drawn_as_its_own_shape(v2):
    """'끈 같은 뱀'에서 빗댄 낱말 '끈'으로 line을 그리지 않는다(중심 명사가 동물). 막힌 기록에 blockedBy."""
    spec = build(v2, "끈 같은 뱀이 있어요.")
    b = recs(spec, "끈")
    assert len(b) == 1 and b[0]["reason"] == "no_asset" and b[0]["category"] == "shape"
    assert b[0]["value"]["blockedBy"] == {"lemma": "뱀", "charSpan": [5, 6], "category": "animal", "rule": "simile_target"}
    assert b[0]["value"]["priorReason"] == "no_scene_param"
    spec = build(v2, "끈 같은 귀신이 있어요.")
    assert recs(spec, "끈")[0]["reason"] == "excluded_shape"


def test_g45_shape_word_describing_a_listed_head_is_not_a_model(v2):
    """'네모난 귀신' — 모양어가 목록 낱말을 꾸미면 모양 모형도 그리지 않는다(형상을 그 모양으로 본뜨지 않음)."""
    spec = build(v2, "네모난 귀신이 있어요.")
    sq = [u for u in spec["_unmapped"] if u["category"] == "shape"]
    assert sq and all(u["reason"] == "excluded_shape" and u["value"]["blockedBy"]["rule"] == "modifier_of_listed_head" for u in sq)
    assert not shape_words(spec)
    spec = build(v2, "귀신 옆에 네모난 그릇이 있어요.")          # 다른 명사를 꾸미면 그대로(변형값 단서)
    assert spec["form"]["base"] == "container" and spec["form"]["baseVariant"].get("profile") == "square"


def test_g45_unrendered_reasons_are_distinguished_from_no_model(v2):
    """G32 모형 없는 모양어와 G45 제외 범주가 함께 나오면 saidWords에 둘 다, 이유가 갈려서 남는다."""
    spec = build(v2, "가슴 안쪽에 길쭉한 게 있어요. 귀신 같아요.")
    words = unrendered_said_words(spec, TABLE)
    assert {(w["lemma"], w["unrenderedBy"]) for w in words} >= {("귀신", "excluded_shape")}
    assert any(w["unrenderedBy"] == "no_model" for w in words)


def test_g45_negated_listed_head_does_not_open_the_form_slot(v2):
    spec = build(v2, "사람이 아니에요.")
    assert recs(spec, "사람")[0]["value"].get("negated") is True
    assert not listed_heads(spec) and not form_said_unrendered(spec, TABLE)


def test_g45_retracted_base_word_is_not_drawn(v2):
    """'끈, 아니 귀신이에요' — '아니'로 거둬들인 앞 말은 그리지 않는다(_negated에 남김)."""
    for text in ("끈, 아니 귀신이에요.", "끈이에요. 아니, 귀신이에요."):
        spec = build(v2, text)
        assert spec["form"]["base"] is None, text
        assert any(n["lemma"] == "끈" and "retracted" in n["_provenance"]["rule"] for n in spec["_negated"]), text
        assert listed_heads(spec)[0]["lemma"] == "귀신"


# ── G48 기록: 자리마다 글자 위치·문장 번호 ───────────────────────────────
def test_g48_every_occurrence_is_recorded_with_span_and_sentence(v2):
    text = "칼이 있어요. 칼 옆에 그릇이 있어요. 아기 그릇도 있어요."
    spec = build(v2, text)
    got = [(u["lemma"], u["_provenance"]["charSpan"], u["value"]["sentence"], u["value"]["position"], u["value"]["role"])
           for u in recs(spec)]
    assert got == [("칼", [0, 1], 0, "head", "subject"), ("칼", [8, 9], 1, "modifier", "modifier"),
                   ("아기", [22, 24], 2, "modifier", "modifier")]
    for u in recs(spec):
        assert text[slice(*u["_provenance"]["charSpan"])] == u["lemma"]
        assert u["value"]["scope"] == "main" and u["value"]["usedForShape"] is False
    assert spec["form"]["base"] == "container"


def test_g48_modifier_record_points_at_its_head(v2):
    spec = build(v2, "아기 그릇이 있어요.")
    assert recs(spec, "아기")[0]["value"]["head"] == {"lemma": "그릇", "charSpan": [3, 5]}
    spec = build(v2, "뱀 같은 끈이 있어요.")
    assert recs(spec, "뱀")[0]["value"]["head"] == {"lemma": "끈", "charSpan": [5, 6]}


def test_g48_unanalyzed_kiwi_error_is_still_recorded(v2, an):
    """Kiwi 분석 오류('아이 모습이' → 아/IC 이/MM): 어절 글자 전체가 목록 낱말이면 position unanalyzed로 남긴다."""
    assert [t.base_tag for t in an.tokens("아이 모습이 보여요.")][:2] == ["IC", "MM"]
    spec = build(v2, "아이 모습이 보여요.")
    r = recs(spec, "아이")
    assert len(r) == 1 and r[0]["value"]["position"] == "unanalyzed" and r[0]["_provenance"]["charSpan"] == [0, 2]


# ── G49 판정 못 하는 문형의 보수적 기본 ──────────────────────────────────
@pytest.mark.parametrize("text,blocked,rule", [
    ("귀신이 있어요. 끈 같아요.", "끈", "unresolved_reference"),        # 다음 문장의 주어 없는 비교
    ("귀신이 있어요. 그건 끈 같아요.", "끈", "unresolved_reference"),    # 대명사 주어
    ("귀신 같은 게 끈처럼 늘어져 있어요.", "끈", "unresolved_reference"),
    ("귀신이 끈 같아요.", "끈", "simile_target"),                       # 서술형 비교의 주어가 목록 낱말
    ("그건 귀신인데 끈처럼 가늘어요.", "끈", "simile_target"),           # 대명사 주어 → 그 절의 서술 명사
    ("끈이 귀신이에요.", "끈", "copula"),                               # 주어 = 서술 명사
    ("긴 끈 같은 귀신이 있어요.", "끈", "simile_target"),
])
def test_g49_undecidable_patterns_take_the_conservative_default(v2, text, blocked, rule):
    spec = build(v2, text)
    assert spec["form"]["base"] is None
    b = [u for u in recs(spec, blocked) if "blockedBy" in u["value"]]
    assert b and b[0]["value"]["blockedBy"]["rule"] == rule
    ax, _ = form_axis(spec)
    assert ax is not None and ax["reason"] == "said_unrendered"


def test_g49_shape_word_in_a_following_sentence_without_subject_is_blocked(v2):
    spec = build(v2, "귀신이 있어요. 동그래요.")
    sw = [u for u in spec["_unmapped"] if u["category"] == "shape"]
    assert sw and sw[0]["reason"] == "excluded_shape" and sw[0]["value"]["blockedBy"]["rule"] == "unresolved_reference"


def test_g49_listed_word_after_the_base_does_not_block(v2):
    """앞 문장의 비교는 뒤에 나온 목록 낱말을 가리키지 않는다(앞 문장만 봄)."""
    assert build(v2, "끈 같아요. 귀신도 있어요.")["form"]["base"] == "line"


def test_g49_pattern_table_document_exists():
    doc = REPO_ROOT / "docs" / "validation" / "mapper-v2" / "head-noun-patterns.md"
    raw = doc.read_text(encoding="utf-8")
    assert "판정" in raw and "보수적" in raw
    assert ":\\" not in raw and "Users" not in raw


# ── G50 넷째 범주(죽음·자해·외상) ─────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "올가미 같은 끈이 있어요.",          # G45의 '뱀 같은 끈 → 끈'과 다름
    "해골 그릇이 있어요.",
    "피 같은 물방울이 있어요.",
    "피 웅덩이가 있어요. 그릇도 있어요.",
    "끈인데 올가미 같아요.",
    "피그릇이 있어요.",
    "핏방울 같은 게 있어요.",
    "피 같은 붉은 끈이 있어요.",         # 색 낱말이 대상(끈)을 꾸밈 → 형상 비교로 봄(엄격한 쪽)
])
def test_g50_strict_category_blocks_form_assets_and_form_candidates(v2, text):
    spec = build(v2, text)
    assert spec["form"]["base"] is None and spec["form"]["baseVariant"] is None
    assert form_blocks(spec) and not shape_words(spec)
    assert all(u["value"]["blockedBy"]["rule"] == "strict_category" for u in recs(spec) if "blockedBy" in u["value"])
    ax, out = form_axis(spec)
    assert ax is None, out["axes"]                       # 형태 축을 벌리지 않는다(다른 빈 차원은 그대로)
    assert out["axes"] and all(a["slot"] != "form.type" for a in out["axes"])
    assert all(c["sources"]["form.type"] == "default" for c in out["candidates"])
    assert not form_said_unrendered(spec, TABLE)
    flags = safety_flags(spec)
    assert flags and all(f["category"] == "death_self_harm_trauma" for f in flags)


@pytest.mark.parametrize("text,color", [
    ("피처럼 붉은 덩어리예요.", True),     # G50 (2): 색은 '붉은'으로 정해짐, 형태는 막지 않음
    ("피같이 빨간 실이에요.", True),
    ("피처럼 붉은 끈이 있어요.", True),
    ("피 같은 색이에요.", False),         # 색 낱말이 따로 없으면 색을 지어내지 않음(원칙 2)
    ("핏빛 덩어리예요.", False),          # 뜻이 색인 낱말
])
def test_g50_color_comparison_is_not_blocked_and_color_is_not_invented(v2, text, color):
    spec = build(v2, text)
    assert not form_blocks(spec)
    assert (spec["material"]["color"] is not None) is color
    flags = safety_flags(spec)
    assert len(flags) == 1 and flags[0]["formBlock"] is False
    assert flags[0]["position"] in ("color_comparison", "color_expression")
    if "끈" in text or "실" in text:
        assert spec["form"]["base"] == "line"


@pytest.mark.parametrize("text", ["피곤해요. 그릇이 있어요.", "피부가 따가워요. 그릇이 있어요.", "피하고 싶어요. 그릇이 있어요.",
                                  "피로해요. 그릇이 있어요.", "커피 같은 물방울이 있어요.", "피아노 같은 상자예요."])
def test_g50_morpheme_matching_does_not_catch_lookalikes(v2, text):
    spec = build(v2, text)
    assert spec["form"]["base"] is not None and not safety_flags(spec) and not recs(spec)


def test_g50_strict_words_are_recorded_even_in_recall_sentences(v2):
    """넷째 범주는 회상 문장에서도 기록·표시하고 형태를 막는다(엄격 — 문장 범위를 가르지 않음, ⚠ 사람이 정할 것)."""
    spec = build(v2, "어제 피를 봤던 장면이 생각나요. 그릇이 있어요.")
    f = safety_flags(spec)
    assert len(f) == 1 and f[0]["scope"] == "context" and f[0]["formBlock"] is True
    assert spec["form"]["base"] is None


# ── G50 (4) 세션 기록·실험자 표시·러너 계약 ───────────────────────────────
def test_g50_selection_records_safety_flags_and_form_blocked(rt4):
    s, f = started(rt4, "SYN-G50-SEL", "올가미 같은 끈이 있어요. 작아요.")
    assert [x["lemma"] for x in f.data["safetyFlags"]] == ["올가미"]
    assert all(a["slot"] != "form.type" for a in f.cands["axes"])
    f.adjust("form", "line")                              # 조절에서 형태를 바꾸는 것은 막지 않음(결정에 없음)
    f.finish()
    valid(f.data)
    d = f.data["sourceDetails"]["form.type"]
    assert d["formBlocked"] == {"rule": "G50", "by": ["올가미"], "adjustFormAllowed": True}
    assert f.data["sourceDetails"]["form.base"]["source"] == "edited"
    assert runner_contract_errors(json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))) == []
    # 세션 기록: sceneSpec.safetyFlags · 이벤트 · 연구자 알림. 참여자 화면(view)에는 없음
    assert s.log.data["sceneSpec"]["safetyFlags"][0]["lemma"] == "올가미"
    assert any(e["type"] == "scene:safety_flag" for e in s.log.data["events"])
    assert any(a["kind"] == "scene_safety_flag" for a in s.log.data["alerts"])
    assert s.researcher_view()["safetyFlags"][0]["category"] == "death_self_harm_trauma"
    assert "safetyFlags" not in json.dumps(s.view(), ensure_ascii=False)
    assert "safetyFlags" not in json.dumps(f.view(), ensure_ascii=False)


def test_g50_session_without_strict_words_has_empty_flags(rt4):
    s, f = started(rt4, "SYN-G50-NONE", "끈 같은 뱀이 있어요.")
    assert f.data["safetyFlags"] == []
    assert "safetyFlags" not in s.log.data["sceneSpec"] and s.researcher_view()["safetyFlags"] == []
    assert not any(a["kind"] == "scene_safety_flag" for a in s.log.data["alerts"])
    f.finish()
    valid(f.data)
    d = f.data["sourceDetails"]["form.type"]
    assert d["source"] in ("said_unrendered_chosen", "said_unrendered_default")
    assert [(w["lemma"], w["unrenderedBy"], w["category"]) for w in d["saidWords"]] == [("뱀", "no_asset", "animal")]


def test_runner_reads_safety_flags_and_unity_filters_both_unrendered_reasons():
    """러너(PlacementSelection)가 safetyFlags를 공개 속성으로 들고 manifest에 옮기며, Unity ShapeMapping과 챗봇이 같은
    사유(excluded_shape·no_asset)를 모양어에서 뺀다(C# 원문 대조)."""
    sel = (REPO_ROOT / "unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs").read_text(encoding="utf-8")
    assert "public JArray SafetyFlags" in sel and "public bool HasSafetyFlags" in sel and 'o["safetyFlags"]' in sel
    sm = (REPO_ROOT / "unity/Assets/IFS/Runtime/SceneSpec/ShapeMapping.cs").read_text(encoding="utf-8")
    m = re.search(r'UnrenderedReasons = \{ ([^}]*) \}', sm)
    from ifs_chatbot.candidates import UNRENDERED_REASONS
    assert m and [x.strip().strip('"') for x in m.group(1).split(",")] == list(UNRENDERED_REASONS)


def test_analyzer_reads_safety_flag_columns():
    from ifs_chatbot.eval.placement import SESSION_HEAD
    assert "safety_flag_categories" in SESSION_HEAD and "safety_form_blocked" in SESSION_HEAD


def test_lexicon_has_no_local_paths():
    raw = Path(shared("lexicon", "base_shapes.v1.json")).read_text(encoding="utf-8")
    assert ":\\" not in raw and "Users" not in raw
