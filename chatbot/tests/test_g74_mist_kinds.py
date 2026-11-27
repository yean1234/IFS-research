"""G74 안개 입자 모양(form.mistKind — fog·smoke·dust·cloud, 스펙 2.4.0의 선택 슬롯): 매퍼 v2 규칙(scene_params.v2 mistKinds 표),
형상 자리·비교 원천·움직임 비유 매개어(G71)·부정·동음이의('김')·다른 뜻('연기됐어요'), 스키마, 끈 설정의 출력 불변.
모든 대사는 합성이다(AGENTS.md 6)."""
import json

import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v2 import BUILDER_ID_MIST, BUILDER_ID_PROP, SceneSpecBuilderV2
from ifs_chatbot.scene_spec import check_principles, schema_errors
from ifs_chatbot.simulate import drive

P = shared("lexicon", "scene_params.v2.json")


@pytest.fixture(scope="module")
def an():
    return Analyzer()


@pytest.fixture(scope="module")
def on(an):
    return SceneSpecBuilderV2(an, proportions_path=P, mist_kinds_path=P)


@pytest.fixture(scope="module")
def prop_only(an):
    return SceneSpecBuilderV2(an, proportions_path=P)


def build(b, text):
    spec = b.build(text)
    assert check_principles(spec, normalize_confirmed(text)) == []
    return spec


def kind(spec):
    return spec["form"]["mistKind"]


def alts(spec):
    return [(a["value"], a["reason"]) for a in spec["_alternatives"] if a["path"] == "form.mistKind"]


# ── 매퍼: 낱말 → 종류 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,want", [
    ("안개가 껴 있어요", "fog"), ("수증기가 있어요", "fog"), ("아지랑이가 피어요", "fog"), ("물안개가 껴요", "fog"),
    ("연기가 피어올라요", "smoke"), ("담배 연기가 피어올라요", "smoke"), ("김이 모락모락 나요", "smoke"),
    ("먼지가 흩날려요", "dust"), ("가루가 날려요", "dust"), ("모래가 흩어져 있어요", "dust"), ("미세먼지가 가득해요", "dust"),
    ("구름이 떠 있어요", "cloud"), ("먹구름이에요", "cloud"),
])
def test_said_word_sets_kind(on, text, want):
    s = build(on, text)
    assert s["meta"]["specVersion"] == "2.4.0" and s["meta"]["pipeline"]["builder"] == BUILDER_ID_MIST
    assert kind(s) == want
    pv = s["_provenance"]["form.mistKind"][0]
    assert pv["source"] == "explicit_lexicon" and pv["rule"].endswith(f">form.mistKind:{want}")
    assert s["meta"]["pipeline"]["lexicons"]["mistKindTable"].endswith(".mistKinds@0.2.0")


@pytest.mark.parametrize("text,want", [("연기 같은 게 있어요", "smoke"), ("먹구름 같아요", "cloud"), ("먼지구름 같아요", "dust")])
def test_simile_source_sets_kind_at_layer_two(on, text, want):
    s = build(on, text)
    assert s["form"]["type"] == "mist" and kind(s) == want          # form.type은 기존 직유 원형 그대로
    pv = s["_provenance"]["form.mistKind"][0]
    assert pv["source"] == "simile_marker" and "+simile(" in pv["rule"]


@pytest.mark.parametrize("text,lemma", [("연기가 피어올라요", "연기"), ("먼지가 흩날려요", "먼지"), ("황사예요", "황사"),
                                        ("흙먼지가 날려요", "흙먼지"), ("매연이 있어요", "매연")])
def test_gas_and_dust_words_fill_form_type(on, prop_only, text, lemma):
    """메인 판정 (가): 형상 자리(층 1)의 기체·먼지 낱말은 form.type도 mist로 채운다(출처 기록)."""
    a, b = build(on, text), build(prop_only, text)
    assert b["form"]["type"] is None and a["form"]["type"] == "mist"
    assert a["_provenance"]["form.type"][0]["rule"] == f"mistKinds.{lemma}>form.type:mist"
    assert not any(u["category"] == "object" and u["lemma"] == lemma for u in a["_unmapped"])


@pytest.mark.parametrize("text,want", [("모래가 흩어져 있어요", None), ("가루가 날려요", "fragments"), ("구름이 떠 있어요", None),
                                       ("먹구름이에요", None), ("김이 모락모락 나요", None)])
def test_solid_grains_clouds_and_steam_keep_form_type(on, prop_only, text, want):
    """'모래·가루'(알갱이 고체)·'구름'(G71-e)·'김'은 form.type을 채우지 않는다 — 종류만 기록."""
    a, b = build(on, text), build(prop_only, text)
    assert a["form"]["type"] == b["form"]["type"] == want and kind(a) is not None


def test_fill_keeps_said_form_and_base(on):
    s = build(on, "회색 덩어리에서 연기가 나요")
    assert s["form"]["type"] == "blob" and kind(s) == "smoke"
    assert any(a["path"] == "form.type" and a["value"] == "mist" and a["_provenance"][0]["rule"].endswith("+keptFormType")
               for a in s["_alternatives"])
    s = build(on, "연기가 피어오르는 그릇")
    assert s["form"]["base"] == "container" and s["form"]["type"] is None
    assert any(a["path"] == "form.type" and "+base(container)" in a["_provenance"][0]["rule"] for a in s["_alternatives"])


def test_simile_and_vehicle_do_not_fill_form_type(on, prop_only):
    for text in ("연기처럼 피어올라요", "구름이 흘러가듯이 물체가 움직여요"):
        assert build(on, text)["form"]["type"] == build(prop_only, text)["form"]["type"]


@pytest.mark.parametrize("text", ["안개 속에 돌이 있어요", "연기 사이로 돌이 보여요", "안개에 싸인 돌"])
def test_location_use_does_not_fill_form_type(on, prop_only, text):
    """메인 판정 (나): 장소 용법의 안개류 낱말은 form.type을 채우지 않는다(내린 근거는 대안 +location)."""
    a = build(on, text)
    assert a["form"]["type"] is None and kind(a) is None
    b = build(prop_only, text)
    if b["form"]["type"] is not None:
        assert any(al["path"] == "form.type" and "+location(" in al["_provenance"][0]["rule"] for al in a["_alternatives"])


@pytest.mark.parametrize("text", ["뿌연 게 있어요", "그냥 뿌옇게 보여요", "회색 돌이에요", "흐릿한 덩어리예요"])
def test_no_kind_word_is_null(on, text):
    s = build(on, text)
    assert "mistKind" in s["form"] and kind(s) is None and "form.mistKind" not in s["_provenance"]


# ── 범위 ────────────────────────────────────────────────────────────────────
def test_action_simile_vehicle_does_not_fill(on):
    """G71: 움직임 비유의 매개어는 형태를 채우지 않는다 — 종류도 대안(lower_priority)으로만."""
    s = build(on, "연기처럼 피어올라요")
    assert kind(s) is None and alts(s) == [("smoke", "lower_priority")]
    assert "+actionSimile(" in [a for a in s["_alternatives"] if a["path"] == "form.mistKind"][0]["_provenance"][0]["rule"]
    s = build(on, "구름이 흘러가듯이 물체가 움직여요")
    assert kind(s) is None and alts(s) == [("cloud", "lower_priority")]


def test_clause_simile_without_later_subject_keeps_word(on):
    """G71-a: 비유 절 뒤에 따로 주어가 없으면 매개어가 물체 자체일 수 있다 → 그대로."""
    assert kind(build(on, "연기가 춤추듯이 피어올라요")) == "smoke"


@pytest.mark.parametrize("text", ["안개는 아니에요", "연기가 아니에요", "먼지 같은 건 아니에요"])
def test_negated(on, text):
    s = build(on, text)
    assert kind(s) is None
    assert any(n["category"] == "mist_kind" for n in s["_negated"])


def test_retracted_word_loses_to_the_correction(on):
    s = build(on, "연기, 아니 구름이에요")
    assert kind(s) == "cloud"
    assert [n["lemma"] for n in s["_negated"] if n["category"] == "mist_kind"] == ["연기"]


@pytest.mark.parametrize("text", ["안개 속에 돌이 있어요", "연기를 내뿜는 돌", "구름의 그림자", "먹구름처럼 시커먼 덩어리",
                                  "회의가 연기됐어요", "연기를 잘해요", "김이 있어요", "빵가루가 날려요",
                                  "안개 낀 날 산책하던 기억이 떠올라요"])
def test_not_form_position_or_other_sense(on, text):
    """장소·목적어·꾸밈·색 비교, 다른 뜻('연기됐어요'), '김'(김이 나는 말이 없음), 표에 없는 합성어, 회상 문장."""
    assert kind(build(on, text)) is None


def test_direct_word_beats_simile_source(on):
    s = build(on, "연기 같은 안개가 있어요")
    assert kind(s) == "fog" and alts(s) == [("smoke", "lower_layer")]


def test_first_mention_wins_and_later_is_alternative(on):
    s = build(on, "안개가 있어요. 연기도 피어올라요.")
    assert kind(s) == "fog" and alts(s) == [("smoke", "later_mention")]
    s = build(on, "연기가 있어요. 담배 연기 같아요.")
    assert kind(s) == "smoke" and alts(s) == [] and len(s["_provenance"]["form.mistKind"]) == 2


def test_unlisted_noun_record_is_replaced_by_value(on, prop_only):
    """'먼지'·'김'은 1층 사전에 없어 사전에 없는 명사로 남던 말 — 값의 근거가 되면 그 기록은 지운다(G72와 같음).
    사물 기록('구름' object)은 그대로 둔다(G71-e)."""
    a, b = build(on, "먼지가 흩날려요"), build(prop_only, "먼지가 흩날려요")
    assert any(u["lemma"] == "먼지" for u in b["_unmapped"]) and not any(u["lemma"] == "먼지" for u in a["_unmapped"])
    a = build(on, "구름이 떠 있어요")
    assert any(u["lemma"] == "구름" and u["category"] == "object" for u in a["_unmapped"])


def test_test03_wide_mist_is_fog_with_proportions(on):
    s = build(on, "넓게 펼쳐진 안개가 떠오른다")
    assert s["form"]["type"] == "mist" and kind(s) == "fog"
    assert s["layout"]["proportions"] == {"x": 1.0, "y": 0.3, "z": 1.0, "axisSaid": True}


# ── 끈 설정 · 스키마 ─────────────────────────────────────────────────────────
SAMPLES = ["안개가 껴 있어요", "연기가 피어올라요", "먼지가 흩날려요", "구름이 떠 있어요", "연기처럼 피어올라요", "안개는 아니에요",
           "넓게 펼쳐진 안개가 떠오른다", "회색 돌이에요", "연기 같은 안개가 있어요", "김이 모락모락 나요"]


def _strip(spec: dict) -> dict:
    """켠 쪽에서 G74가 더한 것(슬롯·근거·대안·부정·표 표기·builder)을 뺀 나머지."""
    s = json.loads(json.dumps(spec))
    s["form"].pop("mistKind", None)
    s["_provenance"].pop("form.mistKind", None)
    s["_alternatives"] = [a for a in s["_alternatives"] if a["path"] != "form.mistKind"]
    s["_negated"] = [n for n in s["_negated"] if n["category"] != "mist_kind"]
    s["meta"]["pipeline"]["lexicons"].pop("mistKindTable", None)
    s["meta"]["pipeline"]["builder"] = None
    s["_unmapped"] = [u for u in s["_unmapped"] if u["category"] not in ("unlisted_noun", "object")]
    s["form"]["type"] = None                                     # (가)·(나)는 form.type을 바꾼다 — 따로 시험
    s["_provenance"].pop("form.type", None)
    s["_alternatives"] = [a for a in s["_alternatives"] if a["path"] != "form.type"]
    s["_unmatched"] = []
    for cl in s.get("_clauses") or []:
        cl["usedFor"] = [u for u in cl["usedFor"] if u not in ("form.mistKind", "form.type")]
        cl["status"] = None
    s["meta"].pop("createdAt", None)
    return s


@pytest.mark.parametrize("text", SAMPLES)
def test_other_slots_unchanged_when_on(on, prop_only, text):
    a, b = build(on, text), build(prop_only, text)
    assert b["meta"]["pipeline"]["builder"] == BUILDER_ID_PROP and "mistKind" not in b["form"]
    assert _strip(a) == _strip(b)


def test_off_config_unchanged(an):
    off = SceneSpecBuilderV2(an)
    s = off.build("연기가 피어올라요")
    assert s["meta"]["specVersion"] == "2.2.0" and "mistKind" not in s["form"]
    with pytest.raises(ValueError):
        SceneSpecBuilderV2(an, mist_kinds_path=P)                   # 2.4.0(비율 표)와 함께만


def test_schema_rules(on, prop_only):
    s = on.build("연기가 피어올라요")
    assert schema_errors(s) == []
    bad = json.loads(json.dumps(s))
    bad["form"]["mistKind"] = "steam"
    assert schema_errors(bad)                                     # 닫힌 목록
    bad = json.loads(json.dumps(s))
    del bad["_provenance"]["form.mistKind"]
    assert schema_errors(bad)                                     # 값이 있으면 근거가 있어야 한다
    b = prop_only.build("연기가 피어올라요")
    assert schema_errors(b) == []                                 # 2.4.0에서 선택(키 없음)
    old = SceneSpecBuilderV2(Analyzer()).build("연기가 피어올라요")
    old["form"]["mistKind"] = None
    assert schema_errors(old)                                     # 2.2.0에는 없어야 한다


# ── 실험 설정 ────────────────────────────────────────────────────────────────
def test_experiment_runtime_writes_kind(tmp_path):
    cfg = load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "guard.required": False,
        "session.log_dir": str(tmp_path / "logs"), "preview.mode": "none"})
    rt = Runtime(cfg)
    s = rt.new_session("chatbot", "SYN-G74A")
    drive(s, {"id": "SYN-G74A", "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": "회색 연기가 피어올라요"}})
    assert s.state == "done"
    assert s.scene_spec["meta"]["pipeline"]["builder"] == BUILDER_ID_MIST
    assert s.scene_spec["form"]["mistKind"] == "smoke"
