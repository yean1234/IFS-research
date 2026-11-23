"""매핑 v2 (scene_builder_v2.py) — D1 사전에 없는 명사 기록, D2 형상이 보이지 않게 되는 오류 수정.

문장은 모두 합성이다(AGENTS.md 6). 목업 코퍼스(docs/validation/mock-forms)에서 찾은 실패 유형을 새 문장으로 다시 썼다.
held-out 코퍼스는 열지 않는다. v0·v1 출력이 바뀌지 않았는지도 여기서 확인한다(v0 해시 고정 테스트는
test_scene_builder_v1.py에 있다).
"""
import json
from pathlib import Path

import pytest

from ifs_chatbot.controller import Runtime
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import REPO_ROOT
from ifs_chatbot.scene_builder import dumps, normalize_confirmed
from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1
from ifs_chatbot.scene_builder_v2 import BUILDER_ID, SceneSpecBuilderV2, floor_record
from ifs_chatbot.scene_spec import check_principles, is_mapping_fallback

TESTS = Path(__file__).parent
DEV = TESTS / "fixtures" / "imagery_corpus" / "dev.json"
MOCK = REPO_ROOT / "docs" / "validation" / "mock-forms"


@pytest.fixture(scope="module")
def analyzer():
    a = Analyzer()
    if not a.available:
        pytest.skip("kiwipiepy가 없으면 0층이 정규식 대체라 규칙이 다르게 걸린다")
    return a


@pytest.fixture(scope="module")
def v1(analyzer):
    return SceneSpecBuilderV1(analyzer)


@pytest.fixture(scope="module")
def v2(analyzer):
    return SceneSpecBuilderV2(analyzer)


def build(b, text, **meta):
    spec = b.build(text, **meta)
    assert check_principles(spec, normalize_confirmed(text)) == [], "원칙·스키마(v2.1) 위반"
    return spec


def val(spec, path):
    g, k = path.split(".")
    return spec[g][k]


def unlisted(spec):
    return {u["lemma"]: u for u in spec["_unmapped"] if u["category"] == "unlisted_noun"}


def rule(spec, path):
    return spec["_provenance"][path][0]["rule"]


SLOTS = ("form.type", "form.posture", "material.color", "material.brightness", "material.saturation",
         "material.roughness", "material.opacity", "material.erosion", "layout.size", "layout.distance",
         "layout.verticalOffset", "motion.type", "motion.speed", "body.part", "body.layer")


def same_slots(a, b):
    return all(val(a, p) == val(b, p) for p in SLOTS)


# ── D1 사전에 없는 명사 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("text,noun", [
    ("가슴 앞에 작은 화분이 있어요. 초록색이에요.", "화분"),
    ("배 안에 물병이 있어요.", "물병"),
    ("어깨에 작은 인형이 앉아 있어요.", "인형"),
])
def test_unlisted_noun_is_recorded(v1, v2, text, noun):
    """완료 기준: 사전에 없는 사물 명사가 _unmapped에 원문 근거와 함께 남는다(v1에서는 어디에도 없었다)."""
    assert noun not in {u["lemma"] for u in v1.build(text)["_unmapped"]}
    spec = build(v2, text)
    u = unlisted(spec)[noun]
    s, e = u["_provenance"]["charSpan"]
    t = normalize_confirmed(text)
    assert t[s:e] == noun == u["_provenance"]["trigger"]
    assert u["reason"] == "no_scene_param" and u["_provenance"]["source"] == "phrase_rule"
    assert u["value"] == {"noun": noun, "role": "subject", "scope": "main"}
    # 값은 만들지 않는다(원칙 2): 형태는 비어 있다
    assert val(spec, "form.type") is None


def test_recorded_noun_leaves_token_level_unmatched(v2):
    """기록한 명사는 '읽지 못한 말'(_unmatched 토큰 항목)에서 빠지고, 어절 원문 항목은 그대로 남는다."""
    spec = build(v2, "배 안에 물병이 있어요.")
    assert not any(u["lemma"] == "물병" and u["tag"] != "EOJEOL" for u in spec["_unmatched"])
    assert any(u["surface"] == "물병이" and u["tag"] == "EOJEOL" for u in spec["_unmatched"])


@pytest.mark.parametrize("text,stop", [
    ("가슴 쪽에 답답한 느낌이 있어요.", "느낌"),
    ("어제 저녁 일이요.", "저녁"),
    ("눈 뒤쪽이요.", "눈"),
    ("크기는 잘 모르겠어요.", "크기"),
    ("반쯤 투명해요.", "반쯤"),
    ("공중에 떠 있어요.", "공중"),
])
def test_stop_nouns_are_not_recorded(v2, text, stop):
    """신체 부위·시간·장소 일반어·기능·차원 명사는 형상 후보가 아니라 기록하지 않는다(noun_stoplist.v2.json)."""
    assert stop not in unlisted(build(v2, text))


def test_lexicon_and_valued_nouns_are_not_unlisted(v2):
    """1층 사전에 있는 명사(덩어리·가슴)와 값이 된 색 명사는 '사전에 없는 명사'가 아니다."""
    assert unlisted(build(v2, "가슴에 회색 덩어리가 있어요.")) == {}


def test_verbal_noun_is_not_recorded(v2):
    """-하다가 붙은 서술성 명사('퇴근하고')는 사물 이름이 아니다."""
    assert "퇴근" not in unlisted(build(v2, "퇴근하고 나서요."))


def test_context_clause_noun_is_marked_context(v2):
    """'소파에 누웠을 때'의 소파는 참여자가 떠올린 상황의 명사다: scope context, 성분 location."""
    spec = build(v2, "퇴근하고 소파에 누웠을 때요. 다리 쪽에 작은 인형이 있어요.")
    u = unlisted(spec)
    assert u["소파"]["value"]["scope"] == "context" and u["소파"]["value"]["role"] == "location"
    assert u["인형"]["value"]["scope"] == "main"


def test_situation_answer_noun_is_marked_context(v2):
    """상황·시간 명사가 있고 값이 하나도 나오지 않은 문장('주말 아침 산책이요')의 명사는 context."""
    spec = build(v2, "주말 아침 산책이요. 배 안에 물병이 있어요.")
    u = unlisted(spec)
    assert u["산책"]["value"]["scope"] == "context" and u["물병"]["value"]["scope"] == "main"


def test_small_pot_keeps_size(v1, v2):
    """'작은 화분': v1은 화분이 배경 사물 목록(backgroundNouns)에 있어 '작은'을 _context(background_object)로 보냈다.
    v2는 '있다'의 주어인 배경 사물 낱말을 형상으로 보고 크기를 값으로 쓴다."""
    text = "가슴 앞에 작은 화분이 있어요. 초록색이에요."
    a = v1.build(text)
    assert val(a, "layout.size") is None
    assert [c["reason"] for c in a["_context"] if c["path"] == "layout.size"] == ["background_object"]
    b = build(v2, text)
    assert val(b, "layout.size") == 0.316 and rule(b, "layout.size").startswith("sizeLexicon.작>")
    assert not any(c["path"] == "layout.size" for c in b["_context"])


@pytest.mark.parametrize("text", [
    "창가에 화분이 있어요. 화분은 작아요.",      # 다른 배경 처소어가 있는 주변 묘사
    "방은 어두운데 그것은 밝아요.",              # 배경 주제(존재 서술 아님)
    "하늘은 파란데 그건 회색이에요.",
])
def test_background_nouns_stay_background(v1, v2, text):
    """배경 사물 규칙은 형상 판정이 없으면 v1 그대로다."""
    assert same_slots(v1.build(text), build(v2, text))


def test_same_text_is_byte_identical(v2, analyzer):
    """같은 확정 텍스트 → 같은 바이트(두 번, 새 인스턴스에서도)."""
    fresh = SceneSpecBuilderV2(Analyzer())
    for t in ["가슴 앞에 작은 화분이 있어요. 초록색이에요.", "퇴근하고 소파에 누웠을 때요. 거의 투명해요.",
              "몸 표면이요, 등에 붙어 있어요. 머리 위 한 뼘쯤 높이에 떠 있어요."]:
        first = dumps(v2.build(t, session_id="S1"))
        assert dumps(v2.build(t, session_id="S1")) == first
        assert dumps(fresh.build(t, session_id="S1")) == first


# ── D2(a) 투명도 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["거의 투명해요.", "투명에 가까워요.", "투명에 가까운 유리 파편이에요."])
def test_nearly_transparent_is_small_positive(v1, v2, text):
    """'거의 투명' · '투명에 가까운' → 0이 아니라 nearlyTransparent(0.15)."""
    assert val(build(v2, text), "material.opacity") == 0.15
    assert "+nearly(" in rule(v2.build(text), "material.opacity")


def test_near_transparent_is_not_distance(v1, v2):
    """v1은 '투명에 가까운'의 '가깝'을 거리(near 0.25)로 읽었다. v2는 거리 말이 아니다."""
    text = "투명에 가까운 유리 파편이에요."
    assert val(v1.build(text), "layout.distance") == 0.25
    assert val(build(v2, text), "layout.distance") is None


def test_v1_nearly_transparent_was_zero(v1):
    """v1의 원래 결함(목업 M04·M12): '거의'가 강한 정도 부사로 읽혀 0이 됨."""
    assert val(v1.build("거의 투명해요."), "material.opacity") == 0.0


def test_fully_transparent_stays_zero(v2):
    """'완전히 투명' — 참여자가 말한 그대로 0(원칙 2). '거의'와 구분된다."""
    spec = build(v2, "완전히 투명해요.")
    assert val(spec, "material.opacity") == 0.0 and rule(spec, "material.opacity").endswith("+total(완전히)")


def test_strong_degree_transparent_has_floor(v1, v2):
    """'아주 투명' — v1은 0, v2는 하한 0.05."""
    assert val(v1.build("아주 투명해요."), "material.opacity") == 0.0
    assert val(build(v2, "아주 투명해요."), "material.opacity") == 0.05


@pytest.mark.parametrize("text", ["투명해요.", "조금 투명해요.", "반투명해요.", "뒤가 다 비쳐 보여요.", "불투명해요."])
def test_other_opacity_words_unchanged(v1, v2, text):
    """음성: '거의'·'완전히'·'반쯤'·부분 한정이 없으면 v1과 같은 값."""
    assert val(build(v2, text), "material.opacity") == val(v1.build(text), "material.opacity")


def test_half_transparent_is_translucent(v1, v2):
    """'반쯤 투명'(mapping-audit A14): v1 0.1 → v2 0.5."""
    assert val(v1.build("반쯤 투명해요."), "material.opacity") == 0.1
    assert val(build(v2, "반쯤 투명해요."), "material.opacity") == 0.5


@pytest.mark.parametrize("text,part", [("끝은 거의 투명해요.", "끝"), ("가장자리는 투명해요.", "가장자리")])
def test_part_scoped_transparency_goes_to_parts(v1, v2, text, part):
    """부분 한정 투명도(A06)는 전체 opacity에 번지지 않고 _parts에 남는다."""
    assert val(v1.build(text), "material.opacity") is not None
    spec = build(v2, text)
    assert val(spec, "material.opacity") is None
    assert [(p["part"], p["path"]) for p in spec["_parts"]] == [(part, "material.opacity")]


def test_inside_shows_through_is_whole_opacity(v1, v2):
    """음성: '속이 조금 비쳐요'는 형상 전체가 비친다는 말이라 부분 한정이 아니다(v1과 같음)."""
    text = "보라색 구슬이에요. 겉은 매끈하고 속이 조금 비쳐요."
    assert val(build(v2, text), "material.opacity") == val(v1.build(text), "material.opacity") == 0.7


# ── D2(b) 거리 ───────────────────────────────────────────────────────────────
def test_attached_to_body_is_not_distance(v1, v2):
    """'등에 붙어' — v1 distance 0(얼굴 앞). v2는 거리를 채우지 않고 _unmapped(distance, attached)에 남긴다."""
    text = "몸 표면이요, 등에 붙어 있어요."
    assert val(v1.build(text), "layout.distance") == 0.0
    spec = build(v2, text)
    assert val(spec, "layout.distance") is None
    u = [x for x in spec["_unmapped"] if x["category"] == "distance"]
    assert u and u[0]["value"] == {"distance": "attached"} and u[0]["reason"] == "no_scene_param"
    assert val(spec, "body.part") == "back"


def test_attached_later_mention_follows_body_location(v2):
    """처소어 없는 '붙어 있어요'도 텍스트에 신체 부위가 있으면 몸에 붙은 것이다."""
    spec = build(v2, "옆구리 쪽에 뭔가 있어요. 가만히 붙어 있어요.")
    assert val(spec, "layout.distance") is None


def test_attached_in_front_of_face_gets_floor(v2):
    """'얼굴 앞에 붙어' — 다른 처소어가 있으면 그 자리에 가깝게 붙은 것: 거리 값 + 하한 0.1."""
    spec = build(v2, "얼굴 앞에 붙어 있어요.")
    assert val(spec, "layout.distance") == 0.1 and rule(spec, "layout.distance").endswith("+floor(0.1;said=0.0)")


def test_small_measured_distance_gets_floor(v1, v2):
    """'한 뼘 앞' 0.2 m → v1 0(최소 0.3 m 아래), v2 하한 0.1. 말한 값은 rule과 _measurements에 남는다."""
    text = "한 뼘 앞에 있어요."
    assert val(v1.build(text), "layout.distance") == 0.0
    spec = build(v2, text)
    assert val(spec, "layout.distance") == 0.1
    assert rule(spec, "layout.distance") == "measure.뼘>layout.distance:0.2m+floor(0.1;said=0.0)"
    assert spec["_measurements"][0]["meters"] == 0.2


# ── G33: 거리 하한은 유지하고 말한 값과 그려진 값을 둘 다 기록 ─────────────────────
@pytest.mark.parametrize("text,said", [("얼굴 앞에 붙어 있어요.", 0.0), ("한 뼘 앞에 있어요.", 0.0)])
def test_floor_records_said_and_drawn_values(v2, text, said):
    """하한을 적용하면 슬롯 값(그려진 값) = 하한, rule 꼬리표 said=… = 말한 값(하한 전). 스키마 2.1 안에서(rule은 자유 문자열)."""
    spec = build(v2, text)
    rec = floor_record(spec)
    assert rec == {"slot": "layout.distance", "said": said, "drawn": 0.1, "floor": 0.1,
                   "rule": rule(spec, "layout.distance"), "trigger": spec["_provenance"]["layout.distance"][0]["trigger"],
                   "charSpan": spec["_provenance"]["layout.distance"][0]["charSpan"]}
    assert rec["said"] < rec["drawn"] == val(spec, "layout.distance")


@pytest.mark.parametrize("text", ["멀리 떨어져 있어요.", "코앞에 있어요.", "가슴 안쪽이 답답해요."])
def test_no_floor_record_when_floor_not_applied(v2, text):
    assert floor_record(build(v2, text)) is None


def test_floor_record_reads_builder_200_tag_without_said():
    """builder 2.0.0이 만든 spec('+floor(0.1)', 말한 값 없음)도 읽되 said는 None(지어내지 않음)."""
    spec = {"layout": {"distance": 0.1}, "_provenance": {"layout.distance": [
        {"source": "explicit_lexicon", "trigger": "붙어", "charSpan": [0, 2], "rule": "distanceLexicon.붙>layout.distance:attached+floor(0.1)"}]}}
    assert floor_record(spec)["said"] is None and floor_record(spec)["drawn"] == 0.1


# v0·v1은 하한을 모른다: 하한이 걸리는 문장의 v0·v1 출력 바이트를 sha256으로 고정(G33 변경 전 값, 2026-11-23).
V0_V1_PINNED = {
    "얼굴 앞에 붙어 있어요.": ("b46966ce149c8226bbbb6a9cd6ea38738f5aa19590c96529b788ebcbd0efc3c1",
                           "de65c6963991054d81c1fddede8d3ae1ca288fa7b6794977f90d8a3957fa8be3"),
    "한 뼘 앞에 있어요.": ("d700d2dcb95616fa045bfe7b839bb2dd96a3dbd45a2c12c277bdc82779c3cf51",
                       "069b3861f97c4d252f48ec2fb6641e458920ca87c35ca944f93aaed5bd081112"),
    "얼굴 앞에 길쭉한 게 붙어 있어요.": ("a9cfb3d4fdfd1d0f245ef20b3b2c8ba57dbff82ecebba9b18c55aaa4d7f53255",
                                 "aa13bce9a69c94a31b161cfb423b7f4036e52d323dd1d2069c9f4e4c6ffd9dbc"),
}


@pytest.mark.parametrize("text", list(V0_V1_PINNED))
def test_v0_v1_outputs_unchanged_by_g33(analyzer, v1, text):
    import hashlib
    from ifs_chatbot.lexicon import Lexicon
    from ifs_chatbot.paths import shared
    from ifs_chatbot.scene_builder import SceneSpecBuilder
    v0 = SceneSpecBuilder(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), analyzer), analyzer)
    h0, h1 = V0_V1_PINNED[text]
    assert hashlib.sha256(dumps(v0.build(text, session_id="SYN-PIN")).encode()).hexdigest() == h0
    assert hashlib.sha256(dumps(v1.build(text, session_id="SYN-PIN")).encode()).hexdigest() == h1
    assert "floor(" not in dumps(v1.build(text, session_id="SYN-PIN"))


def test_height_measure_is_not_distance(v1, v2):
    """'머리 위 한 뼘쯤 높이에' — 높이 말이 옆에 있는 수치는 수평 거리가 아니다(목업 M27)."""
    text = "머리 위 한 뼘쯤 높이에 노란빛이 떠 있어요."
    assert val(v1.build(text), "layout.distance") == 0.0
    spec = build(v2, text)
    assert val(spec, "layout.distance") is None and val(spec, "layout.verticalOffset") == 1.0
    m = spec["_measurements"][0]
    assert m["dimension"] == "unknown" and m["usedFor"] is None


@pytest.mark.parametrize("text", ["멀리 떨어져 있어요.", "두 걸음 앞에 있어요.", "가까이 있어요.", "코앞에 있어요."])
def test_distances_above_floor_unchanged(v1, v2, text):
    """음성: 하한 이상 거리는 v1 그대로."""
    assert val(build(v2, text), "layout.distance") == val(v1.build(text), "layout.distance")


# ── D2(d) '가슴 앞을 덮고' ───────────────────────────────────────────────────
def test_body_front_cover_is_location_not_size(v1, v2):
    """'가슴 앞을 덮고'의 '앞'은 시야 전체(1.7 m)가 아니라 위치다(목업 M08)."""
    text = "몸 표면이요. 가슴 앞을 덮고 있어요.\n가슴을 다 덮을 만큼이요."
    assert val(v1.build(text), "layout.size") == 1.0
    spec = build(v2, text)
    assert val(spec, "layout.size") == 0.667 and rule(spec, "layout.size") == "compare.cover.가슴>layout.size:0.4m"


def test_cover_whole_front_unchanged(v1, v2):
    """음성: 신체 부위 없이 '앞을 다 가릴 만큼'은 v1처럼 시야 전체."""
    text = "앞을 다 가릴 만큼 커요."
    assert val(build(v2, text), "layout.size") == val(v1.build(text), "layout.size") == 1.0


# ── D2(c) 자세 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,reason", [
    ("퇴근하고 소파에 누웠을 때요. 다리 쪽에 뭔가 기대 있어요.", "recollection_sentence"),
    ("서 있으면 가슴이 무거워요.", "recollection_sentence"),
    ("제가 서 있는 자리보다 조금 넓어요.", "background_subject"),
    ("몸이 무겁고 처져요.", "background_subject"),
    ("제 몸이 축 처져 있어요.", "background_subject"),
])
def test_participant_posture_is_context(v1, v2, text, reason):
    """참여자 자신의 자세·상태를 말한 절의 자세어는 형상 자세가 아니다(목업 M31·M23·M35)."""
    assert val(v1.build(text), "form.posture") is not None
    spec = build(v2, text)
    assert val(spec, "form.posture") is None
    assert {c["reason"] for c in spec["_context"] if c["path"] == "form.posture"} == {reason}


@pytest.mark.parametrize("text,posture", [
    ("작은 사람 모양이 쪼그려 앉아 있어요.", "crouched"),
    ("오른쪽 어깨 위에 앉아 있어요.", "sitting"),
    ("웅크리고 있어요.", "curled"),
    ("그 사람 어깨가 축 처져 있어요.", "limp"),
    ("고양이가 소파에 누워 있어요.", "lying"),
])
def test_figure_posture_is_kept(v1, v2, text, posture):
    """음성: 형상이 주어이거나 주어가 생략된 자세어는 v1처럼 형상 자세."""
    assert val(build(v2, text), "form.posture") == val(v1.build(text), "form.posture") == posture


# ── 형식·meta·대체 판정 ──────────────────────────────────────────────────────
def test_meta_records_v2_within_schema_21(v2):
    spec = build(v2, "웅크려진 작은 나")
    assert spec["meta"]["specVersion"] == "2.1.0"
    assert spec["meta"]["pipeline"]["builder"] == BUILDER_ID
    assert spec["meta"]["mapping"] == {"requested": "v2", "used": "v1", "fallbackReason": None}
    lex = spec["meta"]["pipeline"]["lexicons"]
    assert lex["sceneParamsV2"].startswith("scene-params-v2@") and lex["nounStoplist"].startswith("noun-stoplist-v2@")
    assert not is_mapping_fallback(spec["meta"]["mapping"])


def test_is_mapping_fallback_keeps_v0_v1_rule():
    assert not is_mapping_fallback({"requested": "v1", "used": "v1", "fallbackReason": None})
    assert not is_mapping_fallback({"requested": "v0", "used": "v0", "fallbackReason": None})
    assert is_mapping_fallback({"requested": "v1", "used": "v0", "fallbackReason": "x"})
    assert is_mapping_fallback({"requested": "v2", "used": "v0", "fallbackReason": "x"})
    assert is_mapping_fallback({"requested": "v2", "used": "v1", "fallbackReason": "x"})
    assert not is_mapping_fallback(None)


def _corpus_texts(path: Path) -> list[str]:
    from ifs_chatbot.eval.corpus_run import run_corpus
    return [it["confirmedText"] for it in run_corpus(path, "v0")["items"] if it.get("confirmedText")]


def test_all_dev_and_mock_outputs_pass_schema_21(v2):
    """dev·목업 코퍼스의 확정 텍스트 전부: v2 출력이 스키마 2.1과 원칙 검사를 통과한다."""
    texts = _corpus_texts(DEV) + _corpus_texts(MOCK / "mock_corpus.json")
    assert len(texts) >= 60
    for t in texts:
        assert check_principles(v2.build(t), normalize_confirmed(t)) == [], t[:30]


# ── v0·v1 불변 ───────────────────────────────────────────────────────────────
def test_v1_mock_specs_unchanged(v1):
    """목업 확인 때 컨트롤러가 쓴 v1 spec 36개(docs/validation/mock-forms/specs/v1)를 지금 v1이 바이트까지 그대로 낸다."""
    runs = json.loads((MOCK / "score" / "compare" / "runs.json").read_text(encoding="utf-8"))
    n = 0
    for it in runs["items"]:
        f = MOCK / "specs" / "v1" / f"{it['id']}.v1.json"
        if not f.exists() or it.get("confirmedText") is None:
            continue
        meta = json.loads(f.read_text(encoding="utf-8"))["meta"]
        got = dumps(v1.build(it["confirmedText"], session_id=meta["sessionId"], participant_id=meta["participantId"],
                             condition=meta["condition"]))
        assert f.read_bytes().replace(b"\r\n", b"\n") == got.encode("utf-8"), it["id"]
        n += 1
    assert n >= 30


def test_v2_does_not_change_v1_instance(analyzer):
    """v2 인스턴스를 만들어도 v1의 표(부분 한정 슬롯 등)와 출력이 바뀌지 않는다(공유 상태 없음)."""
    before = SceneSpecBuilderV1(analyzer)
    t = "가장자리는 거의 투명해요. 등에 붙어 있어요."
    first = dumps(before.build(t))
    SceneSpecBuilderV2(analyzer)
    assert "material.opacity" not in before.part_scoped
    assert dumps(before.build(t)) == first == dumps(SceneSpecBuilderV1(analyzer).build(t))


# ── 매핑 선택(기본값은 그대로) ───────────────────────────────────────────────
def test_corpus_run_v2_label(offline_cfg):
    import tempfile
    from ifs_chatbot.eval.corpus_run import make_runtime
    with tempfile.TemporaryDirectory() as d:
        rt, label = make_runtime(Path(d), "v2", offline_cfg)
        assert label == "v2" and isinstance(rt.scene_builder, SceneSpecBuilderV2)


def test_default_mode_is_unchanged_and_v2_not_built(offline_cfg, tmp_path):
    from ifs_chatbot.config import MappingConfig, load_config
    assert MappingConfig().mode == "v1" and load_config("default").mapping.mode == "v1"
    rt = Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs")}))
    assert "v2" not in rt.scene_builders and isinstance(rt.scene_builder, SceneSpecBuilderV1)


def _drive_static(s, replies):
    s.start()
    i = 0
    while s.awaiting == "reply" and i < len(replies):
        s.reply(replies[i])
        i += 1
    while s.awaiting in ("reply", "soft_check"):
        s.act("skip" if s.awaiting == "reply" else "continue")
    s.act("confirm")


def test_controller_mode_v2_writes_v2_scene(offline_cfg, tmp_path):
    """mapping.mode = "v2"로 고르면 주 장면이 v2이고, 비교 파일 v0·v1·v2가 함께 남는다."""
    rt = Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs"),
                                               "session.scenes_dir": str(tmp_path / "scenes"), "mapping.mode": "v2"}))
    assert isinstance(rt.scene_builder, SceneSpecBuilderV2)
    s = rt.new_session("static", "V2C01")
    _drive_static(s, ["가슴 앞에 작은 화분이 있어요", "몸 안이요", "그대로예요", "거의 투명해요"])
    assert s.state == "done"
    main = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert main["meta"]["mapping"]["requested"] == "v2" and main["meta"]["pipeline"]["builder"] == BUILDER_ID
    assert "화분" in unlisted(main)
    ref = s.log.data["sceneSpec"]
    assert ref["problems"] == [] and "fallback" not in ref
    assert set(k for k in ref["variants"] if not k.endswith("Error")) >= {"v0", "v1", "v2"}


def test_controller_v2_build_error_falls_back_to_v0(offline_cfg, tmp_path, monkeypatch):
    rt = Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs"),
                                               "session.scenes_dir": str(tmp_path / "scenes"), "mapping.mode": "v2"}))

    def broken(*a, **k):
        raise RuntimeError("일부러 낸 오류")
    monkeypatch.setattr(rt.scene_builders["v2"], "build", broken)
    s = rt.new_session("static", "V2C02")
    _drive_static(s, ["가슴에 회색 덩어리가 있어요", "몸 안이요", "그대로예요", "무거워요"])
    main = json.loads(s.scene_path.read_text(encoding="utf-8"))
    assert main["meta"]["mapping"]["requested"] == "v2" and main["meta"]["mapping"]["used"] == "v0"
    assert is_mapping_fallback(main["meta"]["mapping"]) and s.log.data["sceneSpec"]["fallback"] is True
