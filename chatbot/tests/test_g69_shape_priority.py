"""매퍼 v2 builder 2.6.0 — 형태 슬롯 우선순위(직접 형태 진술 > 비유 매개어), 모양 명사, 보통 크기, 광택 표면형.

계기: 연구 책임자가 --config experiment로 해 본 세션(연구자 시험 입력)에서 '구형·구체·동그란'이라고 말했는데 물체가
직사각형 천(form.base sheet)으로 나왔다. '천'은 '바람이 불면 천이 펄럭이듯이 물체가 … 움직이는'의 움직임 비유 매개어였다.
규칙·수치: shared/lexicon/scene_params.v2.json 2.1.0 shapePriority·neutralSize·surfaceTerms·speedWish.
아래 문장은 모두 합성이다. RESEARCHER_TRIAL은 연구자가 시험으로 입력한 대사를 옮긴 것이며 참여자 응답이 아니다(AGENTS.md 6).
"""
import json

import jsonschema
import pytest

from ifs_chatbot import candidates as cand
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1
from ifs_chatbot.scene_builder_v2 import BUILDER_ID, SceneSpecBuilderV2
from ifs_chatbot.scene_spec import check_principles

# 연구자 시험 입력(합성 표기, 2026-11-27). 면담 답을 차례로 한 줄씩 — 확정 텍스트와 같은 꼴
RESEARCHER_TRIAL = "\n".join([
    "빨리 끝내고 싶다",
    "마음 속에",
    "빨리 끝내고 싶다는 간절한 마음",
    "역동적인 형체?",
    "바람이 불면 천이 펄럭이듯이 물체가 계속 꾸물꾸물 움직이는 느낌",
    "기본 모형은 구형인 것 같아",
    "동그란 원?",
    "크기는 보통 크기고 모양은 구체",
    "색은 밝은 회색, 밝기는 무광",
])
MODEL_SHAPES = ("round", "square", "flat", "pointed")      # docs/shape-mapping.md 표(Unity 모양 모형)


@pytest.fixture(scope="module")
def v2():
    return SceneSpecBuilderV2(Analyzer())


@pytest.fixture(scope="module")
def schema():
    return json.loads(shared("schemas", "scene-spec.v2.2.json").read_text(encoding="utf-8"))


def build(b, text):
    spec = b.build(text, session_id="SYN-G69")
    assert check_principles(spec, normalize_confirmed(text)) == []
    return spec


def shapes(spec):
    return [u for u in spec["_unmapped"] if u["category"] == "shape" and u["reason"] == "no_scene_param"]


def first_model_shape(spec):
    """Unity 규칙 1: _unmapped shape를 charSpan 순서로 보고 표에 있는 첫 모양."""
    ss = sorted(shapes(spec), key=lambda u: u["_provenance"]["charSpan"][0])
    return next((u["value"]["shape"] for u in ss if u["value"]["shape"] in MODEL_SHAPES), None)


def alts(spec, path):
    return [a for a in spec["_alternatives"] if a["path"] == path]


def rules(spec, path):
    return [p["rule"] for p in spec["_provenance"].get(path, [])]


# ── 연구자 시험 입력(회귀) ────────────────────────────────────────────────────
def test_researcher_trial_draws_a_sphere_not_a_cloth(v2, schema):
    spec = build(v2, RESEARCHER_TRIAL)
    assert spec["meta"]["pipeline"]["builder"] == BUILDER_ID == "scene-spec-builder-v2/2.6.0"
    assert list(jsonschema.validators.validator_for(schema)(schema).iter_errors(spec)) == []
    # 형태: 천(sheet)이 기본이 아니고, 렌더러가 구(Sphere)를 그린다(form.type null|blob + 모양어 round, 기본 형상 없음)
    assert spec["form"]["base"] is None and spec["form"]["baseVariant"] is None
    assert spec["form"]["type"] in (None, "blob")
    assert first_model_shape(spec) == "round"
    said = {u["lemma"] for u in shapes(spec)}
    assert {"구형", "동그랗", "구체"} <= said
    # 천은 형태 대안으로만, 그리고 움직임 근거로
    (alt,) = alts(spec, "form.base")
    assert alt["value"] == "sheet" and alt["reason"] == "lower_priority"
    assert alt["_provenance"][0]["trigger"] == "천" and "+actionSimile(펄럭이듯이)" in alt["_provenance"][0]["rule"]
    # 움직임: 펄럭임/꿈틀 계열, 천이 근거에 들어감
    assert spec["motion"]["type"] in ("swaying", "wriggling")
    assert any(p["trigger"] == "천" and p["rule"].startswith("actionSimile.천>motion.type")
               for p in spec["_provenance"]["motion.type"])
    # '빨리 끝내고 싶다'는 움직임 빠르기가 아님
    assert spec["motion"]["speed"] is None
    assert all("+wish(끝내고 싶" in a["_provenance"][0]["rule"] for a in alts(spec, "motion.speed"))
    # 색: 밝은 회색 / 크기: 보통 = 0.5(말함) / 무광 = 거칠기
    c = spec["material"]["color"]
    assert c["s"] <= 0.1 and c["l"] > 0.55
    assert spec["layout"]["size"] == 0.5 and rules(spec, "layout.size") == ["neutralSize.보통>layout.size:0.5"]
    assert spec["material"]["roughness"] == 0.7 and rules(spec, "material.roughness") == [
        "surfaceTerm.무광>material.roughness:matte"]
    assert spec["material"]["brightness"] is None          # '밝기는 무광' — 밝기 값은 만들지 않음


def test_researcher_trial_candidates_keep_said_form(v2):
    spec = build(v2, RESEARCHER_TRIAL)
    c = cand.generate(spec, "SYN-G69")
    slots = [a.get("slot") for a in c["axes"]]
    assert "form.type" not in slots and "layout.size" not in slots   # 모양·크기는 말한 자리
    assert c["candidates"][0]["overrides"] == {}
    assert c["candidates"][0]["sources"]["form.type"] == "said"


def test_researcher_trial_deterministic_and_v1_untouched(v2):
    a, b = v2.build(RESEARCHER_TRIAL, session_id="S"), v2.build(RESEARCHER_TRIAL, session_id="S")
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)
    v1 = SceneSpecBuilderV1(Analyzer()).build(RESEARCHER_TRIAL)
    assert v1["meta"]["pipeline"]["builder"].startswith("scene-spec-builder-v1/")
    assert v1["layout"]["size"] is None                    # v1 경로는 바뀌지 않음(2.6.0 규칙은 v2에만)


# ── 움직임 비유 매개어 vs 형상 비유 ─────────────────────────────────────────────
@pytest.mark.parametrize("text,tag", [
    ("천처럼 펄럭여요", "+actionSimile(천처럼 펄럭여요)"),
    ("천이 펄럭이는 것처럼 물체가 움직여요", "+actionSimile(펄럭이는 것처럼)"),
    ("종이가 날리듯이 빨간 공이 움직여요", "+actionSimile(날리듯이)"),
])
def test_motion_simile_vehicle_does_not_fill_form_base(v2, text, tag):
    spec = build(v2, text)
    assert spec["form"]["base"] is None
    (alt,) = alts(spec, "form.base")
    assert alt["reason"] == "lower_priority" and tag in alt["_provenance"][0]["rule"]


@pytest.mark.parametrize("text,base", [
    ("천 같은 게 펄럭여요", "sheet"),             # '같은 게' — 형상 비유(그것이 천 같음)
    ("천이 펄럭이듯이 움직여요", "sheet"),        # 비유 절 뒤에 주어가 없으면 천이 물체일 수 있어 그대로(보수적)
    ("동그란 천이 있어요", "sheet"),              # 모양어가 형상 낱말을 꾸밈 — 직접 진술이 아님
    ("그릇이 있어요. 모양은 동그래요", "container"),   # 맞는 조합(compatibleBase)
    ("모양은 그릇 같아요", "container"),          # 형태 틀 안의 형상 낱말
    ("종이처럼 납작해요", "sheet"),
    ("불꽃 같은데 끝이 뾰족해요", "flame"),
])
def test_base_kept(v2, text, base):
    spec = build(v2, text)
    assert spec["form"]["base"] == base and alts(spec, "form.base") == []


@pytest.mark.parametrize("text,word", [
    ("종이 같은 느낌인데 모양은 구체예요", "구체"),
    ("천이 있어요. 모양은 동그래요", "동그랗"),
    ("모양은 동그랗고 종이처럼 얇아요", "동그랗"),
    ("네모난 모양인데 천처럼 부드러워요", "네모나"),
])
def test_direct_shape_statement_beats_base_noun(v2, text, word):
    spec = build(v2, text)
    assert spec["form"]["base"] is None
    (alt,) = alts(spec, "form.base")
    assert f"+directShape({word})" in alt["_provenance"][0]["rule"]
    assert first_model_shape(spec) is not None


def test_direct_shape_statement_beats_simile_mist(v2):
    spec = build(v2, "연기 같은 게 있는데 모양은 동그래요")
    assert spec["form"]["type"] is None and first_model_shape(spec) == "round"
    (alt,) = alts(spec, "form.type")
    assert alt["value"] == "mist" and "+directShape(동그랗)" in alt["_provenance"][0]["rule"]


def test_adverbial_shape_word_is_not_a_statement(v2):
    # '둥글게 감싸고' — 감싸는 모양새. 비유에서 온 형태(공기 같은 → mist)를 내리지 않는다
    spec = build(v2, "따뜻한 공기 같은 게 있어요. 저를 둥글게 감싸고 있어요.")
    assert spec["form"]["type"] == "mist"


@pytest.mark.parametrize("text,ft", [
    ("구름처럼 떠다녀요", None),                    # 움직임 비유 → 형태는 말하지 않은 자리(후보가 벌림)
    ("안개처럼 퍼진 빛이에요", "mist"),             # 퍼진 상태(완료 관형형)는 형상 비유
    ("구름 같은 게 떠다녀요", "mist"),              # '같은 게' — 형상 비유
])
def test_motion_simile_and_form_type(v2, text, ft):
    spec = build(v2, text)
    assert spec["form"]["type"] == ft
    if ft is None:
        (alt,) = alts(spec, "form.type")
        assert alt["value"] == "mist" and "+actionSimile(" in alt["_provenance"][0]["rule"]


def test_clause_simile_color_loses_to_direct_color(v2):
    spec = build(v2, "빨간 천이 펄럭이듯이 파란 물체가 움직여요")
    assert spec["material"]["color"]["h"] > 0.5            # 파랑(물체를 직접 말함)
    (alt,) = alts(spec, "material.color")
    assert alt["reason"] == "lower_layer" and "+actionSimile(펄럭이듯이)" in alt["_provenance"][0]["rule"]


# ── 모양 명사·동음이의 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expect", [
    ("구형이에요", "구형"),
    ("기본 모형은 구형인 것 같아", "구형"),
    ("구형 모양이에요", "구형"),
    ("모양은 구체\n색은 회색", "구체"),             # 줄 끝 명사(Kiwi가 '구+체'로 자름)도
    ("구형 핸드폰 같아요", None),                   # 舊型
    ("구체적으로 말하면 둥근 공이에요", None),       # 具體
])
def test_shape_nouns(v2, text, expect):
    spec = build(v2, text)
    got = [u["lemma"] for u in shapes(spec) if u["lemma"] in ("구형", "구체")]
    assert got == ([expect] if expect else [])
    if expect:
        u = next(u for u in shapes(spec) if u["lemma"] == expect)
        assert u["value"] == {"shape": "round"} and u["_provenance"]["rule"] == f"shapeNoun.{expect}>shape:round"


def test_gucheiro_not_form(v2):
    spec = build(v2, "구체적으로 말하면 둥근 공이에요")
    assert all(p["trigger"] != "구체" for p in spec["_provenance"].get("form.type", []))


def test_negated_shape_noun(v2):
    spec = build(v2, "구형은 아니에요")
    assert shapes(spec) == [] and any(n["lemma"] == "구형" and n["category"] == "shape" for n in spec["_negated"])


def test_line_end_noun_is_named_not_modifier(v2):
    spec = build(v2, "종이\n빨간색이에요")
    assert spec["form"]["base"] == "sheet"                  # '종이⏎빨간색' — 종이가 빨간색을 꾸미지 않음


# ── 보통 크기 · 광택 · 바람 ───────────────────────────────────────────────────
@pytest.mark.parametrize("text,size", [
    ("보통 크기예요", 0.5),
    ("크기는 보통이에요", 0.5),
    ("중간 크기예요", 0.5),
    ("크기는 보통 주먹만 해요", None),               # '보통'(대개) — 크기는 주먹 비교가 정함
    ("보통 이렇게 생겼어요", None),
])
def test_neutral_size(v2, text, size):
    spec = build(v2, text)
    if size is None:
        assert "neutralSize" not in json.dumps(spec["_provenance"], ensure_ascii=False)
    else:
        assert spec["layout"]["size"] == size


@pytest.mark.parametrize("text,r", [("무광이에요", 0.7), ("유광이에요", 0.1), ("무광은 아니에요", None)])
def test_gloss_terms(v2, text, r):
    assert build(v2, text)["material"]["roughness"] == r


@pytest.mark.parametrize("text,speed", [("빨리 끝내고 싶어요", None), ("빨리 돌아요", 0.8), ("천천히 내려오고 있어요", 0.25)])
def test_speed_adverb_on_wish(v2, text, speed):
    assert build(v2, text)["motion"]["speed"] == speed
