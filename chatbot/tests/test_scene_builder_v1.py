"""개선 매핑 v1 (scene_builder_v1.py) — 규칙별 단위 테스트, 결정론, LLM·네트워크 차단, 대체 경로, 확인 질문 루프.

문장은 모두 합성이다(AGENTS.md 6). dev 코퍼스 문장을 그대로 베끼지 않고 규칙마다 새로 썼다.
held-out 코퍼스는 열지 않는다(AC-3).
"""
import hashlib
import json
import socket
import urllib.request
from pathlib import Path

import httpx
import pytest

from ifs_chatbot.controller import Runtime
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder import SceneSpecBuilder, dumps, normalize_confirmed
from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1, fallback_spec, load_lexicon_v1
from ifs_chatbot.scene_spec import SLOT_PATHS, check_principles
from ifs_chatbot.validator import TurnContext

TESTS = Path(__file__).parent
DEV = TESTS / "fixtures" / "imagery_corpus" / "dev.json"
FIXTURES = TESTS / "fixtures" / "scene_spec"


@pytest.fixture(scope="module")
def analyzer():
    a = Analyzer()
    if not a.available:
        pytest.skip("kiwipiepy가 없으면 0층이 정규식 대체라 규칙이 다르게 걸린다")
    return a


@pytest.fixture(scope="module")
def v1(analyzer):
    return SceneSpecBuilderV1(analyzer)


def build(b, text, **meta):
    spec = b.build(text, **meta)
    assert check_principles(spec, normalize_confirmed(text)) == [], "원칙·스키마(v2.1) 위반"
    return spec


def val(spec, path):
    g, k = path.split(".")
    return spec[g][k]


def hue(spec):
    c = spec["material"]["color"]
    return round(c["h"] * 360) % 360, c["s"], c["l"]


def texts_of(spec, field):
    return [x.get("text") or x.get("trigger") for x in spec[field]]


# ── 사전 오버레이 ──────────────────────────────────────────────────────────────
def test_overlay_examples_hit_their_lemma(analyzer):
    """v1 오버레이의 ex가 Kiwi로 실제 그 항목에 걸린다(사전 항목이 죽은 항목이 아님)."""
    lex = load_lexicon_v1(analyzer)
    ov = json.loads(shared("lexicon", "layer1_lexicon.v1.json").read_text(encoding="utf-8"))
    miss = [e["lemma"] for e in ov["entries"]
            if not any(h.entry.lemma == e["lemma"] and h.entry.category == e["category"] for h in lex.hits(e["ex"]))]
    assert miss == []


def test_v0_files_are_untouched_by_overlay():
    """v1은 v0 사전 파일을 읽기만 한다: 버전이 그대로다."""
    for name in ("layer1_lexicon.v0.json", "scene_params.v0.json", "vad_ko.v0.json"):
        data = json.loads(shared("lexicon", name).read_text(encoding="utf-8"))
        assert data["lexiconVersion"] == "0.1.0"


# ── 색 ───────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,h_range,l_range", [
    ("노란색이에요", (40, 65), (0.5, 0.7)),            # Kiwi가 '노란색'을 한 명사로 냄
    ("하얀색 덩어리예요", None, (0.9, 1.0)),
    ("청록색이고 둥글어요", (160, 190), (0.3, 0.5)),
    ("잿빛 안개예요", None, (0.45, 0.65)),
    ("연두빛이 도는 공이에요", (80, 100), (0.45, 0.65)),
    ("크림색이에요", (35, 60), (0.8, 0.95)),
    ("검은색 공 같아요", None, (0.0, 0.15)),
])
def test_color_terms_by_surface(v1, text, h_range, l_range):
    h, s, l = hue(build(v1, text))
    if h_range:
        assert h_range[0] <= h <= h_range[1]
    else:
        assert s <= 0.1
    assert l_range[0] <= l <= l_range[1]


@pytest.mark.parametrize("text,check", [
    ("연한 갈색이에요", lambda h, s, l: 0.4 <= l <= 0.75 and s < 0.45),
    ("짙은 회색이에요", lambda h, s, l: l <= 0.35),
    ("어두운 초록색이에요", lambda h, s, l: 100 <= h <= 140 and l <= 0.3),
    ("연보라색 풍선 같아요", lambda h, s, l: 260 <= h <= 290 and l >= 0.6),
    ("진한 분홍색이에요", lambda h, s, l: l < 0.78),
    ("새하얗고 눈부셔요", lambda h, s, l: s == 0.0 and l >= 0.9),           # 무채색은 채도를 바꾸지 않는다
])
def test_color_modifiers_adjust_lightness_and_saturation(v1, text, check):
    spec = build(v1, text)
    assert check(*hue(spec))
    assert spec["material"]["brightness"] is None or "눈부셔" in text   # 명도 수식어는 밝기 값을 따로 만들지 않는다


def test_color_tint_and_near_blend(v1):
    h, s, l = hue(build(v1, "하얀색인데 약간 누르스름해요"))
    assert 35 <= h <= 65 and s <= 0.5 and 0.75 <= l <= 0.97
    spec = build(v1, "흰빛에 가까운 노란색이에요")
    h, s, l = hue(spec)
    assert 40 <= h <= 65 and l >= 0.65
    assert spec["layout"]["distance"] is None                 # '가까운'이 거리가 되지 않는다(다의어)


# ── 정도 부사 ─────────────────────────────────────────────────────────────────
def test_degree_adverbs_scale_within_slot(v1):
    assert 0.55 <= val(build(v1, "표면이 살짝 거칠어요"), "material.roughness") <= 0.8
    assert val(build(v1, "표면이 아주 거칠어요"), "material.roughness") >= 0.95
    assert 0.2 <= val(build(v1, "조금 어두워요"), "material.brightness") <= 0.45
    assert val(build(v1, "아주 천천히 돌아요"), "motion.speed") <= 0.2
    assert val(build(v1, "속이 살짝 비쳐요"), "material.opacity") >= 0.6
    assert val(build(v1, "속이 훤히 비쳐요"), "material.opacity") <= 0.3
    assert val(build(v1, "조금 떨어져 있어요"), "layout.distance") <= 0.5


# ── 수치·단위 ─────────────────────────────────────────────────────────────────
def test_number_units_to_size_and_distance(v1):
    s = build(v1, "지름이 20센티 정도예요")
    assert val(s, "layout.size") == 0.5 and s["_measurements"][0]["meters"] == 0.2
    assert abs(val(build(v1, "한 2미터쯤 떨어져 있어요"), "layout.distance") - 0.63) < 0.01
    assert val(build(v1, "얼굴 앞 50센티에 있어요"), "layout.distance") < 0.1
    assert val(build(v1, "두 걸음 정도 앞에 있어요"), "layout.distance") == pytest.approx(0.333, abs=0.01)
    unk = build(v1, "30센티쯤이요")                           # 크기인지 거리인지 말하지 않음 → 값 없이 보존
    assert val(unk, "layout.size") is None and val(unk, "layout.distance") is None
    assert unk["_measurements"][0]["dimension"] == "unknown"


def test_width_is_not_overall_size(v1):
    s = build(v1, "폭은 손가락 세 개 정도고 길어요")
    assert val(s, "layout.size") is None and s["_measurements"][0]["dimension"] == "width"


# ── 비교 크기 ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,lo,hi", [
    ("크기는 계란만 해요", 0.1, 0.35),
    ("귤만한데 말랑해요", 0.1, 0.4),
    ("배구공보다 훨씬 커요", 0.6, 0.8),
    ("테니스공보다 조금 커요", 0.2, 0.35),
    ("제 키만 한 기둥 같아요", 0.95, 1.0),
    ("몸 전체를 감쌀 만큼 커요", 0.95, 1.0),
    ("동전 세 개 크기 정도요", 0.1, 0.35),
    ("크기는 큰 수박 정도예요", 0.55, 0.75),
])
def test_comparative_size_reference_table(v1, text, lo, hi):
    spec = build(v1, text)
    assert lo <= val(spec, "layout.size") <= hi
    assert spec["_provenance"]["layout.size"][0]["source"] == "phrase_rule"


def test_reference_body_noun_is_not_body_part(v1):
    spec = build(v1, "크기는 제 머리만 해요")
    assert val(spec, "body.part") is None and val(spec, "layout.size") is not None
    assert val(build(v1, "팔 길이만큼 떨어져 있어요"), "layout.distance") < 0.3


# ── 공간 높이어·방향 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,lo,hi", [
    ("눈높이에 떠 있어요", 0.85, 1.0),
    ("무릎 높이에 있어요", 0.2, 0.35),
    ("발밑에 깔려 있어요", 0.0, 0.08),
    ("머리 위에 떠 있어요", 0.9, 1.0),
    ("바닥 가까이에 있어요", 0.0, 0.2),
])
def test_height_words(v1, text, lo, hi):
    spec = build(v1, text)
    assert lo <= val(spec, "layout.verticalOffset") <= hi
    assert spec["layout"]["distance"] is None


def test_body_part_alone_gives_height_only_as_suggestion(v1):
    spec = build(v1, "가슴에 뭔가 있어요")
    assert val(spec, "body.part") == "chest" and val(spec, "layout.verticalOffset") is None
    assert spec["_inferred"]["layout.verticalOffset"]["_provenance"][0]["source"] == "body_part_height"


def test_direction_is_preserved_not_mapped(v1):
    spec = build(v1, "오른쪽앞에 둥근 게 있어요")
    assert spec["_direction"][0]["horizontal"] == "right" and spec["_direction"][0]["depth"] == "front"
    assert val(spec, "body.layer") is None


# ── 수식 범위·배경 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,want_h", [
    ("노란 벽 앞에 파란 공이 있어요", 215),
    ("하얀 탁자 위에 빨간 컵 같은 게 있어요", 0),
    ("작은 상자 위에 초록색 리본이 있어요", 120),
])
def test_modifier_scope_background_and_landmark(v1, text, want_h):
    spec = build(v1, text)
    assert hue(spec)[0] == want_h
    assert spec["_context"], "배경·자리 표지 사물의 수식어는 _context에 원문으로 남는다"
    if "작은" in text:
        assert val(spec, "layout.size") is None


def test_background_subject_and_recollection_sentence(v1):
    spec = build(v1, "공원 벤치에 앉아 있던 장면이요. 보라색 덩어리가 있어요. 주변 나무들은 초록색이에요.")
    assert 260 <= hue(spec)[0] <= 290
    assert val(spec, "form.posture") is None                      # 회상 문장의 '앉아'
    reasons = {c["reason"] for c in spec["_context"]}
    assert {"recollection_sentence", "background_subject"} <= reasons


def test_past_progressive_figure_sentence_is_not_recollection(v1):
    spec = build(v1, "점점 커지던 게 지금은 멈췄어요")
    assert val(spec, "motion.type") == "still"


# ── 부분·전체, 차원 주제 ───────────────────────────────────────────────────────
def test_part_whole(v1):
    spec = build(v1, "은색 테두리가 있고 안쪽은 짙은 파란색이에요")
    h, s, l = hue(spec)
    assert 200 <= h <= 230 and l < 0.4
    assert spec["_parts"] and spec["_parts"][0]["partClass"] == "detail"
    spec = build(v1, "겉은 거칠거칠한데 속은 매끈해요")
    assert spec["material"]["roughness"] is None or spec["material"]["roughness"] >= 0.5
    spec = build(v1, "겉은 까칠까칠한데 속은 매끈해요")
    assert val(spec, "material.roughness") >= 0.7 and spec["_parts"][0]["partClass"] == "inner"


def test_dimension_topic_wins(v1):
    spec = build(v1, "가운데는 하얗고 색은 주황색이에요")
    assert 20 <= hue(spec)[0] <= 40


# ── 자기 정정·모름·부정 ───────────────────────────────────────────────────────
def test_self_correction(v1):
    spec = build(v1, "빨간색… 아 아니다, 빨간색보다는 주황색에 가까워요")
    assert 20 <= hue(spec)[0] <= 40
    assert {a["reason"] for a in spec["_alternatives"] if a["path"] == "material.color"} == {"self_corrected"}
    assert val(spec, "layout.distance") is None
    assert 40 <= hue(build(v1, "노란색… 아니 금색이에요"))[0] <= 48
    assert 225 <= hue(build(v1, "파란색이 아니고 남색이에요"))[0] <= 235


def test_uncertainty_leaves_slot_null(v1):
    spec = build(v1, "색은 잘 모르겠어요. 크기는 주먹만 해요.")
    assert spec["material"]["color"] is None and val(spec, "layout.size") is not None
    assert spec["_uncertain"][0]["paths"] == ["material.color"]
    spec = build(v1, "몸 안인지 겉인지 모르겠어요. 배 쪽이요.")
    assert val(spec, "body.layer") is None and val(spec, "body.part") == "belly"
    spec = build(v1, "잘 모르겠지만 파란 것 같아요")             # 짐작한 값은 말한 값이다
    assert hue(spec)[0] == 215


def test_negation(v1):
    spec = build(v1, "빛이 전혀 안 나고 좀 어둑해요")
    assert 0.3 <= val(spec, "material.brightness") <= 0.45
    assert any(n["lemma"] == "빛" for n in spec["_negated"])
    assert build(v1, "안 빨개요")["material"]["color"] is None
    assert val(build(v1, "거의 안 움직여요"), "motion.type") == "still"
    assert val(build(v1, "그렇게 크지 않아요"), "layout.size") is None


# ── 움직임 ───────────────────────────────────────────────────────────────────
def test_motion_verb_beats_state_and_later_state_after_dadaga(v1):
    assert val(build(v1, "떠 있는데 가끔 부르르 떨려요"), "motion.type") == "trembling"
    assert val(build(v1, "둥둥 떠 있다가 빙글빙글 돌아요"), "motion.type") == "rotating"
    assert val(build(v1, "흔들거리다가 멈춰요"), "motion.type") == "still"
    assert val(build(v1, "넓게 퍼져 있고 천천히 소용돌이쳐요"), "motion.type") == "churning"


def test_mimetic_derivation_and_idiom(v1):
    assert val(build(v1, "표면이 까끌거려요"), "material.roughness") >= 0.7
    assert val(build(v1, "출렁출렁해요"), "motion.type") == "sloshing"
    spec = build(v1, "매끈하고 윤기가 흘러요")
    assert val(spec, "motion.type") is None and val(spec, "material.roughness") <= 0.15


def test_specific_body_part_beats_general(v1):
    spec = build(v1, "몸 주변이요. 왼쪽 무릎 근처에 있어요.")
    assert val(spec, "body.part") == "leg" and val(spec, "body.layer") == "around"


# ── 퍼지 매칭 ────────────────────────────────────────────────────────────────
def test_fuzzy_lexicon_marks_needs_confirmation(v1):
    """퍼지 일치는 값이 아니라 확인 필요 대안으로만 남는다(T3-F1, 원칙 2)."""
    spec = build(v1, "표면이 오돌도돌해요")
    assert val(spec, "material.roughness") is None and "material.roughness" not in spec["_provenance"]
    assert spec["_needsConfirmation"][0]["matched"] == "오돌토돌"
    alt = [a for a in spec["_alternatives"] if a["reason"] == "needs_confirmation"]
    assert [a["path"] for a in alt] == ["material.roughness"] and alt[0]["value"] == 0.75
    p = alt[0]["_provenance"][0]
    assert p["source"] == "fuzzy_lexicon" and p["needsConfirmation"] is True and p["trigger"] == "오돌도돌해요"


def test_fuzzy_does_not_fire_on_short_or_ambiguous_words(v1):
    spec = build(v1, "그냥 있어요")
    assert spec["_needsConfirmation"] == [] and all(val(spec, p) is None for p in SLOT_PATHS)


# ── 2단계 독립 검토(T3) 재현 입력 회귀 — 검토자가 쓴 합성 문장 ─────────────────────
@pytest.mark.parametrize("text,path,matched", [
    ("뭐라고 설명하기가 어려워요.", "material.saturation", "선명"),
    ("심정이 좀 복잡해요.", "body.part", "심장"),
    ("시장 한가운데 있는 것 같아요.", "body.part", "심장"),
    ("정리가 잘 안 돼요.", "motion.type", "정지"),
    ("멀미가 나는 느낌이에요.", "layout.distance", "멀리"),
    ("착한 아이 같아요.", "material.saturation", "탁하"),
    ("친한 친구 같은 느낌이에요.", "material.saturation", "진하"),
    ("빨래처럼 걸려 있어요.", "motion.speed", "빨리"),
    ("진통이 오는 느낌이에요.", "motion.type", "진동"),
])
def test_t3_f1_fuzzy_never_fills_slot_or_inferred(v1, text, path, matched):
    """T3-F1: 자모 퍼지 일치(다른 낱말)는 슬롯 값·_inferred를 만들지 않고 확인 필요 대안에만 원문과 함께 남는다."""
    spec = build(v1, text)
    assert all(val(spec, p) is None for p in SLOT_PATHS)
    assert spec["_inferred"] == {}
    assert any(n["path"] == path and n["matched"] == matched for n in spec["_needsConfirmation"])
    assert any(a["path"] == path and a["reason"] == "needs_confirmation" for a in spec["_alternatives"])


def test_t3_f1_fuzzy_does_not_override_spoken_gray(v1):
    spec = build(v1, "뭐라고 설명하기가 어려워요. 회색 덩어리예요.")
    assert val(spec, "material.saturation") is None
    h, s, l = hue(spec)
    assert s <= 0.1 and 0.35 <= l <= 0.55


@pytest.mark.parametrize("text", ["자세히 보라고 하는 것 같아요.", "그건 제 노래요.", "오렌지만 해요."])
def test_t3_f2_color_homonym_and_comparison_reference_are_not_color(v1, text):
    """T3-F2: 동사 '보-라고', 명사 '노래'+요, 'N만 하다'의 기준 사물은 색이 아니다(품사·구조 조건)."""
    spec = build(v1, text)
    assert spec["material"]["color"] is None
    assert spec["_unmatched"], "읽지 않은 말은 원문으로 남는다"


@pytest.mark.parametrize("text,want_h", [("색은 노래요.", 52), ("보라예요.", 275), ("오렌지색 공이에요.", 30),
                                         ("붉어졌어요.", 0), ("점점 파래져요.", 215)])         # 붉어지/VV: 색 + '-어지다'
def test_t3_f2_color_forms_still_read(v1, text, want_h):
    assert hue(build(v1, text))[0] == want_h


@pytest.mark.parametrize("text,path", [("크지도 작지도 않아요.", "layout.size"), ("밝지도 어둡지도 않아요.", "material.brightness")])
def test_t3_f3_coordinated_negation_negates_every_item(v1, text, path):
    """T3-F3: 'X지도 Y지도 않다'는 둘 다 부정 → 값 없음, 두 말 모두 _negated."""
    spec = build(v1, text)
    assert val(spec, path) is None
    assert len(spec["_negated"]) == 2


def test_t3_f4_former_relative_clause_and_lemma_color(v1):
    """T3-F4: '-던' 관형절 안의 말은 지난 상태(후보 단위 때), 색 활용형은 형태소 원형으로 찾는다."""
    assert hue(build(v1, "빨갛던 게 노래졌어요."))[0] == 52
    spec = build(v1, "아까 반짝이던 게 지금은 어두워졌어요.")
    assert val(spec, "material.brightness") <= 0.3
    assert any(a["reason"] == "superseded" for a in spec["_alternatives"])
    assert val(build(v1, "떨리던 게 이제 멈췄어요."), "motion.type") == "still"
    spec = build(v1, "파랬다가 지금은 노래졌어요.")
    assert hue(spec)[0] == 52
    assert any(a["path"] == "material.color" and a["_provenance"][0]["trigger"] == "파랬다가" for a in spec["_alternatives"])


@pytest.mark.parametrize("text", ["크고 검은 돌 옆의 작은 불빛이에요.", "작은 불빛이 크고 검은 돌 옆에 있어요."])
def test_t3_f5_coordinated_attributive_follows_same_head(v1, text):
    """T3-F5: '-고' 관형 나열('크고 검은 돌')은 같은 머리 명사를 꾸민다 → 자리 표지 사물의 크기는 형상 값이 아니다."""
    spec = build(v1, text)
    assert val(spec, "layout.size") == val(build(v1, "작은 불빛이에요."), "layout.size") < 0.5
    assert {"크고", "검은"} <= {c["text"] for c in spec["_context"] if c["reason"] == "landmark_object"}


def test_t3_f6_uncertainty_clause_and_recollection_noun(v1):
    """T3-F6: '-더니'는 절 경계(모름은 앞 절에만), '장면' 명사만으로는 회상 문장이 아니다."""
    spec = build(v1, "처음엔 모르겠더니 지금은 분명히 빨개요.")
    assert hue(spec)[0] == 0 and spec["_uncertain"][0]["text"] == "처음엔 모르겠더니"
    spec = build(v1, "장면 속에 빨간 공이 둥둥 떠 있어요.")
    assert hue(spec)[0] == 0 and val(spec, "form.type") == "blob" and val(spec, "motion.type") == "floating"
    assert "recollection_sentence" not in {c["reason"] for c in spec["_context"]}
    spec = build(v1, "빨간 우산을 들고 걷던 장면이요. 노란 공이 있어요.")          # '-던 장면'은 여전히 회상
    assert hue(spec)[0] == 52
    assert "recollection_sentence" in {c["reason"] for c in spec["_context"]}


def test_t3_f7_half_multiplier(v1):
    """T3-F7: 'N의 반' · 'N 반만' → 기준 사물 × 0.5, '두 뼘 반' → 2.5뼘(수 + 반)."""
    half_fist = v1.size_from_meters(0.05)
    for text in ("주먹 크기의 반 정도예요.", "주먹 반만 해요."):
        spec = build(v1, text)
        assert val(spec, "layout.size") == half_fist
        assert spec["_measurements"][0]["meters"] == 0.05 and "반" not in [u["surface"] for u in spec["_unmatched"]]
    spec = build(v1, "두 뼘 반쯤 돼요.")
    assert spec["_measurements"][0]["meters"] == 0.5 and spec["_measurements"][0]["text"] == "두 뼘 반쯤"
    assert val(build(v1, "반투명해요"), "material.opacity") == 0.5                 # '반투명'의 반은 배율이 아니다


def test_t3_f8_emoji_is_eojeol_boundary_and_unread_color_kept(v1):
    """T3-F8: 이모지는 어절 경계. 색 규칙이 읽지 못한 색 낱말은 _unmatched에 원문으로 남는다."""
    assert hue(build(v1, "🔴빨간🔴공🔴이에요"))[0] == 0
    assert "빨깐" in [u["surface"] for u in build(v1, "빨깐 공이에요.")["_unmatched"]]


def test_t3_f9_clarify_target_drops_particles(v1, analyzer):
    """T3-F9: 확인 질문의 X에서 조사·명사형 어미를 뗀다(Kiwi 품사, 없으면 닫힌 조사 목록)."""
    from ifs_chatbot.clarify import clarify_targets
    for text, want in (("뭐라고 설명하기가 어려워요.", "설명"), ("심정이 좀 복잡해요.", "심정"), ("빨래처럼 걸려 있어요.", "빨래")):
        spec = build(v1, text)
        t = normalize_confirmed(text)
        assert clarify_targets(spec, t, max_n=1, analyzer=analyzer)[0]["x"] == want
        assert clarify_targets(spec, t, max_n=1)[0]["x"] == want


# ── 무손실 보존 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "어제 산책하던 게 떠올라요. 가슴에 뭔가 동그랗고 말랑한 게 있어요.\n몸 안이요.\n잘 모르겠는데 따뜻하고 포근해요.",
    "파란색… 아 아니다 남색이고, 고소한 냄새가 나요. 소리는 없어요.",
])
def test_every_non_space_char_is_preserved_verbatim(v1, text):
    spec = build(v1, text)
    t = normalize_confirmed(text)
    covered = set()
    for c in spec["_clauses"]:
        s, e = c["charSpan"]
        assert t[s:e] == c["text"]
        covered.update(range(s, e))
    assert all(i in covered for i, ch in enumerate(t) if not ch.isspace())


# ── 어절 원문 보존(1.2.0) — 절 색인(_clauses)이 아니라 속성 단위 보존 필드에 남는가 ──────────────
def _verbatim_cover(spec, text, *, keys=None, skip=("_provenance", "_clauses")):
    """보존 필드(또는 keys)의 원문 근거(charSpan + 그 구간 원문과 같은 surface/trigger/text)가 덮는 글자 위치."""
    out = set()

    def walk(node):
        if isinstance(node, dict):
            cs = node.get("charSpan")
            txt = next((node[k] for k in ("surface", "trigger", "text", "phrase") if isinstance(node.get(k), str)), None)
            if isinstance(cs, list) and len(cs) == 2 and txt is not None and text[cs[0]:cs[1]] == txt:
                out.update(range(cs[0], cs[1]))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    for k, node in spec.items():
        if (keys is None and k.startswith("_") and k not in skip) or (keys is not None and k in keys):
            walk(node)
    return out


def _eojeol_entries(spec):
    return [u for u in spec["_unmatched"] if u["tag"] == "EOJEOL"]


def test_unconsumed_content_eojeols_kept_whole_with_exact_span(v1):
    """어떤 규칙도 값·보존 기록으로 쓰지 않은 내용어(정도 부사·부정 보조 용언·'같은'·의존 명사 '게'·수사·서술어)는
    어절 전체가 원문 그대로 _unmatched(tag EOJEOL)에 남고, charSpan은 text[s:e]와 같다."""
    text = "음 손바닥 위에 조약돌 같은 게 하나 있어요. 별로 차갑진 않네요. 은은하게 데워진 느낌이에요."
    spec = build(v1, text)
    t = normalize_confirmed(text)
    eoj = _eojeol_entries(spec)
    for u in eoj:
        s, e = u["charSpan"]
        assert t[s:e] == u["surface"] and u["surface"] == u["surface"].strip() and u["lemma"]
    surfaces = [u["surface"] for u in eoj]
    for w in ("게", "하나", "있어요", "않네요", "느낌이에요"):
        assert w in surfaces, w
    assert "별로" in [u["surface"] for u in spec["_unmatched"]]         # 어절 전체가 이미 낱말 항목이면 어절 항목을 겹쳐 넣지 않는다
    assert "별로" not in surfaces
    assert "차갑진" in [n["_provenance"]["trigger"] for n in spec["_negated"]]
    # 부정 범위 '별로 차갑진 않네요' 전체가 속성 단위 보존 필드(_negated + _unmatched)로 덮인다
    s = t.index("별로 차갑진 않네요")
    kept = _verbatim_cover(spec, t)
    assert all(i in kept for i in range(s, s + len("별로 차갑진 않네요")) if not t[i].isspace())


def test_eojeol_preservation_with_emoji_and_newlines(v1):
    """이모지·줄바꿈이 섞여도 어절 항목의 charSpan은 정규화한 확정 텍스트 구간과 맞고, 공백·이모지를 담지 않는다."""
    text = "🙂 어…\n왼쪽 발등에 🌀회오리 같은 게\n있는데 그리 크진 않아요 🙂\n✨반짝✨"
    spec = build(v1, text)
    t = normalize_confirmed(text)
    eoj = _eojeol_entries(spec)
    assert eoj
    for u in eoj:
        s, e = u["charSpan"]
        assert t[s:e] == u["surface"]
        assert not any(ch.isspace() for ch in u["surface"])
        assert not any(ch in u["surface"] for ch in "🙂🌀✨")
    surfaces = [u["surface"] for u in spec["_unmatched"]]
    for w in ("같은", "게", "있는데", "그리", "않아요"):
        assert w in surfaces, w
    # 내용어가 있는 어절은 모두 ① 보존 필드가 어절 전체를 덮거나 ② 내용어가 값 근거로만 쓰였다(아무것도 사라지지 않음)
    kept = _verbatim_cover(spec, t)
    valued = _verbatim_cover(spec, t, keys=("_provenance",))
    import re
    for m in re.finditer(r"[^\s🙂🌀✨…]+", t):
        idx = range(m.start(), m.end())
        assert all(i in kept for i in idx) or any(i in valued for i in idx), m.group(0)


def test_value_only_eojeol_not_added_and_rule_is_additive(v1, monkeypatch):
    """값으로만 쓰인 어절('빨간')은 어절 항목이 되지 않는다. 어절 항목을 빼면 나머지 출력(슬롯 값·다른 보존 필드·
    낱말 단위 _unmatched)은 이 규칙이 없을 때와 같다 — 이 규칙은 보존 항목만 더한다."""
    texts = ["빨간 공이 둥둥 떠 있어요", "가슴 한가운데 회색 돌멩이처럼 딱딱한 게 있어요.\n몸 안이요.\n천천히 가라앉아요.",
             "🙂 노르스름한\n솜뭉치 같은데 별로 안 무거워요"]
    with_rule = [build(v1, t) for t in texts]
    assert "빨간" not in [u["surface"] for u in _eojeol_entries(with_rule[0])]
    monkeypatch.setattr(SceneSpecBuilderV1, "_unmatched_eojeols", lambda self, doc, spec: [])
    for t, a in zip(texts, with_rule):
        b = v1.build(t)
        a = {**a, "_unmatched": [u for u in a["_unmatched"] if u["tag"] != "EOJEOL"]}
        assert dumps(a) == dumps(b)


def test_eojeol_entries_are_not_clarify_targets(v1, analyzer):
    """어절 항목(tag EOJEOL)은 확인 질문 대상이 아니다(질문 X는 낱말 단위 항목에서만 — 기존 동작 유지)."""
    from ifs_chatbot.clarify import clarify_targets
    text = "엄청 몽실몽실한 게 떠 있는데 그다지 크진 않아요"
    spec = build(v1, text)
    t = normalize_confirmed(text)
    eoj_spans = {tuple(u["charSpan"]) for u in _eojeol_entries(spec)}
    assert eoj_spans
    targets = clarify_targets(spec, t, max_n=10, analyzer=analyzer)
    assert all(tuple(x["charSpan"]) not in eoj_spans or x["why"] != "unread_attribute" for x in targets)
    tok_only = {**spec, "_unmatched": [u for u in spec["_unmatched"] if u["tag"] != "EOJEOL"]}
    assert targets == clarify_targets(tok_only, t, max_n=10, analyzer=analyzer)


CASES_V1 =json.loads((FIXTURES / "cases_v1.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES_V1, ids=[c["file"] for c in CASES_V1])
def test_unity_v1_examples_are_current_v1_output(v1, case):
    """Unity EditMode 테스트가 읽는 v2.1 예시(StreamingAssets)가 지금 v1 출력과 같다(키 순서·수 표기까지)."""
    from ifs_chatbot.paths import REPO_ROOT
    path = REPO_ROOT / "unity" / "Assets" / "StreamingAssets" / "IFS" / "examples" / "v1" / case["file"]
    got = dumps(build(v1, case["confirmedText"], session_id=case["sessionId"], participant_id=case["participantId"],
                      condition=case["condition"]))
    assert path.read_bytes().replace(b"\r\n", b"\n") == got.encode("utf-8")


def test_all_outputs_valid_against_v21_schema(v1):
    for text in ["", "웅크려진 작은 나", "가슴 안쪽에 젖은 종이처럼 눅눅하고 가장자리가 삭아가는 회색 덩어리가 있어요",
                 "오른쪽 어깨 위에 얹혀 있어요", "크기는 잘 모르겠어요"]:
        spec = build(v1, text)
        assert spec["meta"]["specVersion"] == "2.1.0" and spec["meta"]["mapping"]["used"] == "v1"


# ── 결정론 ──────────────────────────────────────────────────────────────────
def _dev_confirmed_texts():
    from ifs_chatbot.eval.corpus_run import run_corpus
    return [it["confirmedText"] for it in run_corpus(DEV, "v0")["items"]]


def test_v1_same_input_byte_identical(v1, analyzer):
    texts = _dev_confirmed_texts()[:10] + ["표면이 오돌도돌해요", "빨간색… 아 아니다, 주황색이에요"]
    fresh = SceneSpecBuilderV1(Analyzer())
    for t in texts:
        first, second = dumps(v1.build(t, session_id="S1")), dumps(v1.build(t, session_id="S1"))
        assert first == second
        assert dumps(fresh.build(t, session_id="S1")) == first          # 새 인스턴스여도 바이트까지 같다


def test_v0_output_byte_identical_to_baseline_hashes(analyzer):
    """AC-3.8 보강: v0 출력 바이트가 개선 매핑을 넣기 전 커밋(d4e3e3a)의 v0 출력과 한 바이트도 다르지 않다."""
    pinned = json.loads((FIXTURES / "v0_output_sha256.json").read_text(encoding="utf-8"))["hashes"]
    b = SceneSpecBuilder(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), analyzer), analyzer)
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]
    got = {c["file"]: hashlib.sha256(dumps(b.build(c["confirmedText"], session_id=c["sessionId"],
                                                   participant_id=c["participantId"], condition=c["condition"])).encode()).hexdigest()
           for c in cases}
    from ifs_chatbot.eval.corpus_run import run_corpus
    for it in run_corpus(DEV, "v0")["items"]:
        got[it["id"]] = hashlib.sha256(dumps(b.build(it["confirmedText"], session_id=it["id"], condition="static")).encode()).hexdigest()
    assert got == pinned


# ── LLM·네트워크 차단 ────────────────────────────────────────────────────────
@pytest.fixture
def no_network(monkeypatch):
    calls = []

    def boom(name):
        def _f(*a, **k):
            calls.append(name)
            raise AssertionError(f"매핑 경로에서 {name} 호출")
        return _f

    monkeypatch.setattr(socket.socket, "connect", boom("socket.connect"))
    monkeypatch.setattr(httpx, "get", boom("httpx.get"))
    monkeypatch.setattr(httpx, "post", boom("httpx.post"))
    monkeypatch.setattr(httpx.Client, "send", boom("httpx.Client.send"))
    monkeypatch.setattr(urllib.request, "urlopen", boom("urlopen"))
    import ifs_chatbot.llm as llm
    for cls in (llm.OllamaBackend, llm.OfflineTemplateBackend):
        monkeypatch.setattr(cls, "generate", boom(f"{cls.__name__}.generate"))
    monkeypatch.setattr(llm.OllamaBackend, "_post", boom("OllamaBackend._post"))
    try:
        import ollama  # noqa: F401
        monkeypatch.setattr("ollama.chat", boom("ollama.chat"), raising=False)
        monkeypatch.setattr("ollama.generate", boom("ollama.generate"), raising=False)
    except ImportError:
        pass
    try:
        import requests
        monkeypatch.setattr(requests.Session, "request", boom("requests"))
    except ImportError:
        pass
    return calls


def test_dev_corpus_maps_with_no_llm_no_network(no_network, analyzer):
    """AC-3.9: LLM·HTTP·소켓을 호출 즉시 예외로 바꾼 상태에서 dev 코퍼스 전체를 v1·v0로 매핑한다(정적 조건 재생 포함)."""
    from ifs_chatbot.eval.corpus_run import run_corpus
    for mapper in ("v1", "v0"):
        res = run_corpus(DEV, mapper)
        for it in res["items"]:
            spec = it["spec"]
            assert spec is not None, it["id"]
            assert check_principles(spec, normalize_confirmed(it["confirmedText"])) == []
            if mapper == "v1":
                assert spec["meta"]["mapping"] == {"requested": "v1", "used": "v1", "fallbackReason": None}
    assert no_network == []


# ── 대체 경로(AC-3.7) ─────────────────────────────────────────────────────────
def _drive_static(s, replies, confirm=True):
    s.start()
    i = 0
    while s.awaiting == "reply" and i < len(replies):
        s.reply(replies[i])
        i += 1
    while s.awaiting in ("reply", "soft_check"):
        s.act("skip" if s.awaiting == "reply" else "continue")
    if confirm:
        s.act("confirm")


@pytest.fixture
def rt_v1(offline_cfg, tmp_path, analyzer):
    return Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs")}))


def test_v1_exception_falls_back_to_v0(rt_v1, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("일부러 낸 오류")
    monkeypatch.setattr(rt_v1.scene_builders["v1"], "build", broken)
    s = rt_v1.new_session("static", "FB01")
    _drive_static(s, ["가슴에 회색 덩어리가 있어요", "몸 안이요", "그대로예요", "무거워요"])
    assert s.state == "done"
    main = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert main["meta"]["mapping"]["used"] == "v0" and "일부러 낸 오류" in main["meta"]["mapping"]["fallbackReason"]
    assert main["meta"]["specVersion"] == "2.1.0" and main["meta"]["pipeline"]["builder"].startswith("scene-spec-builder/0.")
    assert main["form"]["type"] == "blob"
    ref = s.log.data["sceneSpec"]
    assert ref["fallback"] is True and ref["problems"] == [] and ref["variants"]["v1"] is None
    assert "일부러 낸 오류" in ref["variants"]["v1Error"]
    assert any(a["kind"] == "scene_mapping_fallback" for a in s.log.data["alerts"])
    v0 = json.loads(s.variant_path("v0").read_text(encoding="utf-8"))
    assert v0["meta"]["specVersion"] == "2.0.0"                      # 비교 파일은 순수 v0


def test_fallback_spec_is_valid_v21(analyzer):
    b = SceneSpecBuilder(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), analyzer), analyzer)
    text = "웅크려진 작은 나"
    spec = fallback_spec(b.build(text), "v1", "테스트")
    assert check_principles(spec, text) == []


def test_corpus_run_mapper_selection_ignores_config_mode(offline_cfg):
    from ifs_chatbot.eval.corpus_run import make_runtime
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        rt, label = make_runtime(Path(d), "v0", offline_cfg)
        assert label == "v0" and rt.scene_builder is rt.scene_builders["v0"]
        rt, label = make_runtime(Path(d), "v1", offline_cfg)
        assert label == "v1" and isinstance(rt.scene_builder, SceneSpecBuilderV1)


# ── 확인 질문 루프 ───────────────────────────────────────────────────────────
@pytest.fixture
def rt_clarify(offline_cfg, tmp_path, analyzer):
    return Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs"), "mapping.clarify_loop": True}))


REPLIES = ["배에 뭔가 몽글몽글한 게 있어요", "몸 안이요", "표면이 오돌도돌해요", "포근해요"]


def test_clarify_loop_asks_only_what_kind_with_participant_words(rt_clarify):
    s = rt_clarify.new_session("static", "CL01")
    _drive_static(s, REPLIES)
    assert s.state == "clarify" and s.awaiting == "reply"
    q = [t for t in s.log.turns if t.get("source") == "clarify:what_kind"]
    assert len(q) == 1
    x = q[0]["anchor"]
    assert q[0]["text"] == rt_clarify.protocol.realize("what_kind", x)
    # 질문 틀 준수: 검증기 V3·V5·V7 재사용 — 참여자가 쓰지 않은 내용어 없음
    raw = json.dumps({"stage": "flesh_out", "risk_signal": "none", "move": "ask", "template": "what_kind",
                      "anchor_quote": x, "utterance": q[0]["text"]}, ensure_ascii=False)
    r = rt_clarify.clarify_validator.check(raw, TurnContext("flesh_out", ["what_kind"], REPLIES, REPLIES[-1]))
    assert r.passed, r.reasons
    s.reply("작은 알갱이가 뭉친 것 같은")
    q2 = [t for t in s.log.turns if t.get("source") == "clarify:what_kind"]
    assert len(q2) == 2 and q2[1]["anchor"] != x
    s.act("skip")                                                  # 넘어가기 → 답을 덧붙이지 않는다
    assert s.state == "done"
    info = s.log.data["clarify"]
    assert info["appended"] == ["작은 알갱이가 뭉친 것 같은"] and len([t for t in info["turns"] if t["passed"]]) <= 2
    assert s.log.data["confirmedText"].endswith("\n작은 알갱이가 뭉친 것 같은")
    spec = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert spec["form"]["type"] == "fragments"                      # 덧붙인 답이 다시 매핑됨


def test_clarify_loop_off_by_default(rt_v1):
    assert rt_v1.cfg.mapping.clarify_loop is False
    s = rt_v1.new_session("static", "CL00")
    _drive_static(s, REPLIES)
    assert s.state == "done" and not any(t.get("source") == "clarify:what_kind" for t in s.log.turns)


def test_clarify_stop_keeps_confirmed_scene_and_crisis_uses_fixed_phrase(rt_clarify):
    s = rt_clarify.new_session("static", "CL02")
    _drive_static(s, REPLIES)
    assert s.state == "clarify"
    s.act("stop")
    assert s.state == "stopped" and s.scene_path.exists()
    assert s.log.data["confirmedText"] == "\n".join(REPLIES)
    s2 = rt_clarify.new_session("static", "CL03")
    _drive_static(s2, REPLIES)
    s2.reply("죽고 싶어요")
    assert s2.state == "crisis" and s2.messages[-1]["source"] == "fixed:crisis"
