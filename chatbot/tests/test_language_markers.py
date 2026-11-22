"""언어 표지 K1–K7·태도 낱말(ifs_chatbot.eval.language_markers) 테스트.
문장은 모두 합성(AGENTS.md 6). 문서 docs/rq-v4-differentiation-measure.md 3.3의 예문과 새 합성 문장.
Kiwi가 기대와 다르게 태깅하거나 규칙이 놓치는 사례는 숨기지 않고 xfail(strict)로 남긴다 — 고쳐지면 테스트가 알려 준다."""
import json

import pytest

from ifs_chatbot.eval import language_markers as lm
from ifs_chatbot.eval.language_markers import MARKERS, analyze_text

pytestmark = pytest.mark.skipif(not lm._analyzer().available, reason="kiwipiepy 필요")


def counts(text):
    return {m: v for m, v in analyze_text(text)["counts"].items() if v}


# ---------------------------------------------------------------- 문서 3.3 합성 예문(기대 표지는 문서 표 그대로)

DOC_EXAMPLES = [
    ("나는 불안 덩어리다.", {"K1": 1, "K2": 1}),
    ("내가 그 돌이에요.", {"K1": 1, "K2": 1}),
    ("저 돌이 저예요.", {"K1": 1, "K2": 1, "K4": 1}),
    ("내 안에 불안한 게 있어요.", {"K1": 1, "K3": 1}),
    ("나한테 그런 마음이 있네.", {"K1": 1, "K3": 1}),
    ("가슴에 돌 같은 게 있다.", {"K3b": 1}),
    ("제 일부가 겁을 내고 있어요.", {"K1": 1}),
    ("그게 저기 보여요.", {"K4": 1, "K5": 1}),
    ("그 공이 아까보다 작아 보였다.", {"K4": 1, "K6": 1}),
    ("무거워요.", {"K7": 1}),
]


@pytest.mark.parametrize("text,expected", DOC_EXAMPLES)
def test_doc_examples(text, expected):
    assert counts(text) == expected


def test_doc_misanalysis_example_is_reproduced():
    # 문서가 오분석 예로 든 문장: Kiwi가 1인칭 '저'를 저/MM으로 태그 — 지금 동작을 고정(K1 놓침, K4 오탐)
    r = analyze_text("그냥 저 자체가 무거운 거예요.")
    assert ["저", "MM"] == r["tokens"][1][:2]
    assert r["counts"]["K1"] == 0 and r["counts"]["K4"] == 1


# ---------------------------------------------------------------- 표지별 양성·음성

@pytest.mark.parametrize("text", ["나는 그 돌이에요.", "내가 그 돌이에요.", "저는 그 돌이에요.", "제가 그 불안이에요.",
                                  "나도 그거예요."])
def test_first_person_variants_identification(text):
    c = counts(text)
    assert c["K1"] == 1 and c["K2"] == 1


def test_k1_counts_possessive_forms():
    # 내 = 나/NP + 의/JKG, 제 = 저/NP + 의/JKG
    assert counts("내 안에 화가 있고 제 속에도 있어요.")["K1"] == 2


def test_k2_b_x_is_me():
    r = analyze_text("이게 바로 저예요.")
    assert r["counts"]["K2"] == 1
    assert r["evidence"]["K2"][0]["rule"] == "b_fp_before_vcp"


def test_k2_negative_cases():
    assert counts("그건 제가 아니에요.").get("K2", 0) == 0      # VCN, 보격 JKC
    assert counts("나는 그 돌이 무섭다.").get("K2", 0) == 0      # VCP 없음
    assert counts("우리는 그 돌이에요.") == {}                  # 문서 K1·K2는 나·저만


def test_existence_frame_vs_k3b():
    assert counts("저한테 무거운 돌이 있었어요.") == {"K1": 1, "K3": 1, "K6": 1}
    assert counts("이것은 저기 있어요.") == {"K3b": 1, "K4": 1}
    r = analyze_text("내 속에 화가 있다.")
    assert r["evidence"]["K3"][0]["rule"] == "fp_jkg_inside"
    assert analyze_text("나한테 그런 마음이 있네.")["evidence"]["K3"][0]["rule"] == "fp_jkb"


def test_k3_excludes_auxiliary_and_absence():
    assert counts("제가 그것을 가지고 있어요.") == {"K1": 1, "K4": 1}   # 있/VX
    assert counts("나에게는 그런 게 없어요.") == {"K1": 1}             # '없다'는 대상 아님


def test_k5_excludes_seem_construction():
    assert counts("그게 슬퍼 보여요.") == {"K4": 1}
    assert counts("그 돌이 멀리 보여요.") == {"K4": 1, "K5": 1}
    assert counts("지금은 그게 작아 보여요.") == {"K4": 1}


def test_k4_mm_requires_subject_position():
    assert counts("이 돌은 무겁다.") == {"K4": 1}
    assert counts("내가 그 돌이에요.").get("K4", 0) == 0   # 그 돌 + 이/VCP: 주어 아님
    assert counts("저 멀리 그게 있어요.") == {"K3b": 1, "K4": 1}   # '저 멀리'의 저/MM 뒤 체언 없음


def test_past_tense_k6_and_rate():
    r = analyze_text("저기 있었어요.")
    assert r["counts"]["K6"] == 1 and r["rates"]["K6"] == 1.0
    assert counts("잘 모르겠어요.") == {"K7": 1}   # 겠/EP는 과거가 아님
    r = analyze_text("나는 무섭고 무거웠어요.")
    assert r["n_clauses"] == 2 and r["counts"]["K6"] == 1 and r["rates"]["K6"] == 0.5


def test_subject_omission_is_unspecified_not_first_person():
    r = analyze_text("무거워요.")
    assert r["counts"]["K7"] == 1 and r["counts"]["K1"] == 0
    assert r["clauses"][0]["markers"] == ["K7"]
    # 이어진 둘째 절은 주어를 물려받지 않는다(원칙 2)
    r = analyze_text("나는 무섭고 싫어요.")
    assert r["n_clauses"] == 2 and r["counts"]["K7"] == 1 and r["counts"]["K1"] == 1


def test_clause_split_keeps_auxiliary_and_relative_clauses():
    assert analyze_text("더 알고 싶어요.")["n_clauses"] == 1
    assert analyze_text("보고 싶지 않아요.")["n_clauses"] == 1
    assert analyze_text("저에게 이런 게 있는 것 같아요.")["n_clauses"] == 1
    assert analyze_text("그거 보면 좀 무섭고 싫어요.")["n_clauses"] == 3


def test_empty_and_single_word():
    for t in ("", "   ", None):
        r = analyze_text(t)
        assert r["n_clauses"] == 0 and all(r["counts"][m] == 0 for m in MARKERS)
        assert all(v is None for v in r["rates"].values()) and "empty_text" in r["flags"]
    r = analyze_text("돌")
    assert r["n_clauses"] == 0 and r["n_fragments"] == 1 and r["rates"]["K7"] is None
    assert counts("무거워요") == {"K7": 1}


def test_evidence_spans_point_at_text():
    r = analyze_text("저 돌이 저예요.")
    for m in MARKERS:
        for e in r["evidence"][m]:
            s, t = e["chars"]
            assert r["text"][s:t] == e["text"]
    assert [e["text"] for e in r["evidence"]["K1"]] == ["저"]
    assert r["evidence"]["K4"][0]["text"] == "저 돌이"


def test_deterministic_and_versioned():
    a = json.dumps(analyze_text("내 안에 불안한 게 있어요."), ensure_ascii=False, sort_keys=True)
    b = json.dumps(analyze_text("내 안에 불안한 게 있어요."), ensure_ascii=False, sort_keys=True)
    assert a == b
    info = analyze_text("x")["analyzer"]
    import kiwipiepy
    assert info["backend"] == "kiwi" and info["kiwipiepy"] == kiwipiepy.__version__
    assert analyze_text("x")["version"] == lm.VERSION


def test_no_composite_score():
    r = analyze_text("나는 불안 덩어리다.")
    assert not any("index" in k or "score" in k for k in r)


# ---------------------------------------------------------------- 태도 낱말(L-B)

def test_attitude_uses_existing_lexicon_with_negation():
    att = analyze_text("안 무서워요.")["attitude"]
    assert att["lexicon"]["lexiconId"] and [(h["lemma"], h["negated"]) for h in att["emotion_hits"]] == [("무섭", True)]
    att = analyze_text("궁금해요.")["attitude"]
    assert [(h["lemma"], h["emotion"], h["negated"]) for h in att["emotion_hits"]] == [("궁금", "curious", False)]
    assert analyze_text("무섭지 않아요.")["attitude"]["emotion_hits"][0]["negated"] is True


def test_attitude_unlisted_words_are_listed_not_classified():
    att = analyze_text("싫어요.")["attitude"]
    assert att["emotion_hits"] == []
    assert [p["lemma"] for p in att["predicate_lemmas"]] == ["싫"]
    assert "분류하지 않음" in att["note"]


# ---------------------------------------------------------------- 알려진 한계(xfail strict: 고쳐지면 실패로 알림)

@pytest.mark.xfail(strict=True, reason="Kiwi가 1인칭 '저'를 저/MM으로 태그(문서 3.3 오분석 예)")
def test_limitation_jeo_tagged_as_determiner():
    assert counts("그냥 저 자체가 무거운 거예요.") == {"K1": 1}


@pytest.mark.xfail(strict=True, reason="'마음속'이 한 낱말이라 자기 위치어 규칙(1인칭+의+안·속)에 안 맞음")
def test_limitation_maeumsok():
    assert counts("제 마음속에 작은 돌이 있어요.") == {"K1": 1, "K3": 1}


@pytest.mark.xfail(strict=True, reason="조사 없는 1인칭 주어도 K7로 셈")
def test_limitation_dropped_particle():
    assert counts("나 무서워.") == {"K1": 1}


@pytest.mark.xfail(strict=True, reason="'아까는'(시간 명사 + JX)을 주어로 봄")
def test_limitation_topic_adverbial():
    assert counts("아까는 무거웠어요.") == {"K6": 1, "K7": 1}


@pytest.mark.xfail(strict=True, reason="안긴 절의 1인칭 주어 + 바깥 VCP를 K2로 잡음")
def test_limitation_embedded_vcp():
    assert counts("내가 본 게 그 돌이에요.") == {"K1": 1}


@pytest.mark.xfail(strict=True, reason="Kiwi가 '공이'를 공/NR 이/NR(숫자)로 태그하는 문맥이 있음")
def test_limitation_gong_as_number():
    assert counts("저 공이 저기 보였어요.") == {"K4": 1, "K5": 1, "K6": 1}


def test_known_limitations_listed():
    ids = {k["id"] for k in lm.KNOWN_LIMITATIONS}
    assert {"jeo_mm", "maeumsok", "dropped_particle", "topic_adverbial", "embedded_vcp", "gong_nr"} <= ids


# ---------------------------------------------------------------- CLI

def test_cli_text_json(capsys):
    lm.main(["--text", "그게 저기 보여요."])
    out = json.loads(capsys.readouterr().out)
    assert out["results"][0]["counts"]["K5"] == 1 and out["known_limitations"]


def test_cli_file_csv(tmp_path):
    src = tmp_path / "u.jsonl"
    src.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [
        {"id": "a", "when": "pre", "text": "나는 불안 덩어리다."},
        {"id": "b", "when": "post", "text": "내 안에 불안한 게 있어요."}]) + "\n", encoding="utf-8")
    out = tmp_path / "o.csv"
    lm.main(["--file", str(src), "--format", "csv", "--out", str(out)])
    lines = out.read_text(encoding="utf-8").splitlines()
    head = lines[0].split(",")
    assert len(lines) == 3 and head[:2] == ["id", "participant"]
    row = dict(zip(head, lines[2].split(",")))
    assert row["K3"] == "1" and row["when"] == "post"


def test_cli_cases_reports_mismatches(tmp_path):
    src = tmp_path / "c.json"
    src.write_text(json.dumps({"cases": [
        {"id": "ok", "sentence": "무거워요.", "expected": {"K7": 1, "n_clauses": 1}},
        {"id": "bad", "sentence": "그냥 저 자체가 무거운 거예요.", "expected": {"K1": 1, "n_clauses": 1}}]},
        ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "r.json"
    lm.main(["--cases", str(src), "--out", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["accuracy"]["cases_all_match"] == 1 and doc["accuracy"]["per_marker"]["K1"] == "1/2"
    assert [m["id"] for m in doc["mismatches"]] == ["bad"]
