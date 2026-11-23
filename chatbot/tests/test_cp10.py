"""CP10(docs/codex-reviews/CP10.md) 반영 — G37 안전 제외 우회, G38 낱말 뜻에서 온 변형값 표시, G39 form.baseVariant 출처와
형태 조절 기록, G40 기본 형상 근거 명사의 기록, G41 저장된 이전 판 파일. 판정과 세부는 docs/decisions.md 'CP10 반영 세부'.
모든 문장은 합성 대사다(AGENTS.md 6). held-out 코퍼스는 열지 않는다."""
import hashlib
import json

import pytest

from ifs_chatbot.candidates import load_table
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1
from ifs_chatbot.scene_builder_v2 import BUILDER_ID, SceneSpecBuilderV2
from ifs_chatbot.scene_spec import check_principles, schema_errors
from ifs_chatbot.selection import variant_for, variant_key_basis

from test_selection_flow import (VALIDATOR01, done_session, rt4, runner_contract_errors, started,  # noqa: F401
                                 valid)

LEX = json.loads(shared("lexicon", "base_shapes.v1.json").read_text(encoding="utf-8"))
TABLE = load_table()
LEGACY = REPO_ROOT / "docs" / "validation" / "legacy-files"


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
    spec = v2.build(text, session_id="SYN-CP10")
    assert check_principles(spec, normalize_confirmed(text)) == [], text
    assert schema_errors(spec) == [], text
    return spec


def excluded(spec):
    return [u for u in spec["_unmapped"] if u["reason"] in ("excluded_shape", "no_asset")]


def test_builder_and_lexicon_versions():
    # G45–G51에서 올림(builder 2.3.0 → 2.4.0, 사전 0.6.0 → 0.7.0). G37 판정 테스트는 tests/test_g45_exclusion.py로 옮겨 새 결정에 맞게 고침
    assert BUILDER_ID == "scene-spec-builder-v2/2.4.0"
    assert LEX["lexiconVersion"] == "0.7.0" and LEX["status"] == "draft"


def _listed_words(kind="excluded"):
    if kind == "excluded":
        return {w for d in LEX["excluded"]["categories"].values() for w in [*d["words"], *d["added"]["words"], *d["compounds"]]}
    return {w for k, d in LEX["noAsset"].items() if not k.startswith("_") for w in [*d["words"], *d["added"]["words"]]}


# ── G37(CP10) 가운데 G45–G51 뒤에도 그대로인 것 ─────────────────────────────
@pytest.mark.parametrize("text,base", [
    ("아이스크림 그릇이 있어요.", "container"),
    ("칼슘 그릇이 있어요.", "container"),
    ("칼국수 그릇이 있어요.", "container"),
    ("피부 같은 막이 있어요.", "sheet"),
    ("커피 같은 물방울이 있어요.", "drop"),
    ("피아노 같은 상자예요.", "container"),
])
def test_g37_lookalike_words_are_not_excluded(v2, text, base):
    """오탐 고정: 제외 낱말과 글자가 겹치지만 Kiwi가 한 토큰으로 내는 낱말은 제외하지 않는다(글자 부분 일치를 쓰지 않음)."""
    spec = build(v2, text)
    assert spec["form"]["base"] == base and not excluded(spec)


@pytest.mark.parametrize("word", ["아이스크림", "칼슘", "칼국수", "피부", "커피", "피아노", "총각", "아이디어", "뱀장어", "화살표",
                                  "피곤", "피로"])
def test_g37_lookalikes_are_single_tokens_and_not_listed(an, word):
    toks = [t for t in an.tokens(f"{word} 같아요.") if t.base_tag in ("NNG", "NNP")]
    assert [t.form for t in toks] == [word]
    assert word not in _listed_words() and word not in _listed_words("no_asset")


def test_g37_compounds_are_single_kiwi_tokens(an):
    """compounds는 Kiwi가 한 명사 토큰으로 내는 것만(둘로 자르면 중심 명사 규칙이 형태소 단위로 봄)."""
    for cat, d in LEX["excluded"]["categories"].items():
        for w in d["compounds"]:
            toks = [t for t in an.tokens(f"{w} 같아요.") if t.base_tag in ("NNG", "NNP")]
            assert [t.form for t in toks] == [w], (cat, w, [t.form for t in toks])


def test_g37_homonym_left_out_stays_out(v2):
    """동음이의로 뺀 '창'(무기 | 창문)은 계속 목록 밖 — 기록 사유가 틀리지 않게."""
    assert "창" not in _listed_words()
    spec = build(v2, "창이 있어요.")
    assert not excluded(spec)


def test_g37_recall_sentence_is_still_not_marked(v2):
    """제외 세 범주(넷째 범주 빼고)는 회상 문장에서 기록하지 않는다(G48 이후에도 그대로)."""
    spec = build(v2, "어제 사람이 많았던 장면이 생각나요.")
    assert not excluded(spec)


@pytest.mark.parametrize("text", ["칼날 같은 게 있어요.", "뱀 같은 끈이 있어요.", "해골 그릇이 있어요.", "그릇이 있어요."])
def test_g37_v1_output_unchanged_by_v2_lexicon(an, text):
    """v1 매퍼는 기본 형상 사전을 읽지 않는다 — 같은 문장의 v1 출력에 excluded_shape·no_asset·form.base가 없다."""
    spec = SceneSpecBuilderV1(an).build(text)
    assert not any(u["reason"] in ("excluded_shape", "no_asset") for u in spec["_unmapped"])
    assert "base" not in spec["form"]


# ── G38 낱말 뜻에서 온 변형값 ──────────────────────────────────────────────
def _vsrc(spec):
    return {pv["rule"].split(">form.baseVariant:")[1].split("=")[0]: pv["source"]
            for pv in spec["_provenance"].get("form.baseVariant", [])}


@pytest.mark.parametrize("text,expect", [
    ("그릇이 있어요.", {"opening": "lexicon_implied"}),
    ("실이 있어요.", {"form": "lexicon_implied", "gauge": "lexicon_implied"}),
    ("가는 실이 엉켜 있어요.", {"form": "explicit_lexicon", "gauge": "explicit_lexicon"}),
    ("실이 엉켜 있어요.", {"form": "explicit_lexicon", "gauge": "lexicon_implied"}),
    ("네모난 상자가 있어요.", {"opening": "lexicon_implied", "profile": "explicit_lexicon"}),
    ("불꽃이 있어요.", {}),
])
def test_g38_lexicon_implied_variant_is_marked(v2, text, expect):
    spec = build(v2, text)
    assert _vsrc(spec) == expect
    if spec["form"]["base"] is not None:
        assert spec["_provenance"]["form.base"][0]["source"] in ("explicit_lexicon", "simile_marker")
    basis = variant_key_basis(spec)
    assert basis == ({k: ("lexicon_implied" if v == "lexicon_implied" else "said") for k, v in expect.items()} or None)


def test_g38_lexicon_implied_only_in_base_variant(v2):
    texts = ["그릇이 있어요.", "가슴 앞에 작은 화분이 있어요. 초록색이에요.", "실 같은 게 감겨 있어요.", "까만 덩어리가 무거워요."]
    for t in texts:
        spec = build(v2, t)
        for path, provs in spec["_provenance"].items():
            if path != "form.baseVariant":
                assert all(p["source"] != "lexicon_implied" for p in provs), (t, path)


def test_g38_builder_220_spec_reads_the_same_by_rule():
    """builder 2.2.0 spec(source가 explicit_lexicon)도 rule 앞부분('baseShapes.')으로 낱말 뜻임을 안다."""
    spec = json.loads((LEGACY / "spec_2.2.0_builder-2.2.0.json").read_text(encoding="utf-8"))
    assert spec["meta"]["pipeline"]["builder"] == "scene-spec-builder-v2/2.2.0"
    assert spec["_provenance"]["form.baseVariant"][0]["source"] == "explicit_lexicon"
    assert variant_key_basis(spec) == {"opening": "lexicon_implied"}


# ── G39 form.baseVariant 출처와 형태 조절 ───────────────────────────────────
T_BOWL = "가슴 앞에 그릇이 있어요."


def _fin(f):
    f.finish()
    valid(f.data)
    assert runner_contract_errors(json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))) == []
    assert sum(f.data["sourceCounts"].values()) == 17
    return f.data["sourceDetails"]


def test_g39_said_base_untouched_variant_is_said_with_key_basis(rt4):
    _, f = started(rt4, "SYN-G39-KEEP", T_BOWL)
    d = _fin(f)
    assert d["form.base"]["source"] == "said" and d["form.baseVariant"]["source"] == "said"
    assert d["form.baseVariant"]["value"] == {"opening": "wide"} and d["form.baseVariant"]["keyBasis"] == {"opening": "lexicon_implied"}
    assert "formItem" not in d["form.base"] and "form.baseVariant" not in f.data["finalOverrides"]
    cand = f.cands["candidates"][0]["sources"]
    assert cand["form.baseVariant"] == "said" and cand["form.base"] == "said"


def test_g39_said_base_changed_to_another_base_clears_variant(rt4):
    _, f = started(rt4, "SYN-G39-LINE", T_BOWL)
    f.adjust("form", "line")
    ev = f.data["adjustments"]["events"][-1]
    assert ev["value"] == "line" and ev["previous"] == "container"
    assert ev["formSlots"] == {"form.type": "blob", "form.base": "line", "form.baseVariant": None}
    d = _fin(f)
    assert (d["form.base"]["source"], d["form.base"]["value"]) == ("edited", "line")
    assert (d["form.baseVariant"]["source"], d["form.baseVariant"]["value"]) == ("edited", None)
    assert d["form.baseVariant"]["saidValue"] == {"opening": "wide"}
    assert d["form.type"]["source"] == "default"
    for s in ("form.type", "form.base", "form.baseVariant"):
        assert d[s]["formItem"] == {"item": "form", "first": "container", "last": "line", "count": 1}


def test_g39_change_then_revert_restores_said_sources(rt4):
    _, f = started(rt4, "SYN-G39-BACK", T_BOWL)
    f.adjust("form", "line")
    f.adjust("form", "container")
    assert f.data["adjustments"]["events"][-1]["formSlots"]["form.baseVariant"] == {"opening": "wide"}
    d = _fin(f)
    assert d["form.base"]["source"] == "said" and d["form.baseVariant"]["source"] == "said"
    assert d["form.baseVariant"]["value"] == {"opening": "wide"}
    assert all("formItem" not in d[s] for s in ("form.type", "form.base", "form.baseVariant"))
    assert f.data["adjustments"]["items"]["form"]["count"] == 2


@pytest.mark.parametrize("pick,type_src", [("blob", "default"), ("mist", "edited")])
def test_g39_said_base_replaced_by_form_type(rt4, pick, type_src):
    _, f = started(rt4, f"SYN-G39-{pick}", T_BOWL)
    f.adjust("form", pick)
    d = _fin(f)
    assert (d["form.base"]["source"], d["form.base"]["value"]) == ("edited", "none")
    assert (d["form.baseVariant"]["source"], d["form.baseVariant"]["value"]) == ("edited", None)
    assert d["form.type"]["source"] == type_src and d["form.type"]["formItem"]["last"] == pick


def test_g39_base_picked_without_saying_one(rt4):
    _, f = started(rt4, "SYN-G39-PICK", "가슴 안쪽이 답답하고 무거운 느낌이에요.")
    f.adjust("form", "container")
    d = _fin(f)
    assert (d["form.base"]["source"], d["form.base"]["value"]) == ("edited", "container")
    assert (d["form.baseVariant"]["source"], d["form.baseVariant"]["value"]) == ("default", None)
    assert "keyBasis" not in d["form.baseVariant"]
    assert d["form.baseVariant"]["formItem"]["last"] == "container"


def test_g39_variant_for_matches_unity_rule():
    spec = {"form": {"type": None, "posture": None, "base": "container", "baseVariant": {"opening": "narrow"}}}
    assert variant_for(spec, "container") == {"opening": "narrow"}
    assert variant_for(spec, "line") is None and variant_for(spec, "none") is None
    assert variant_for({"form": {"base": None, "baseVariant": None}}, "container") is None


def test_g39_runner_refuses_variant_without_base():
    d = json.loads((LEGACY / "sel_0.2_d6_spec-2.2.0.json").read_text(encoding="utf-8"))
    d["sources"]["form.baseVariant"] = "said"
    assert runner_contract_errors(d) == []
    d["sources"].pop("form.base")
    assert "sources.baseVariant_without_base" in runner_contract_errors(d)


# ── G40 기본 형상 근거 명사 ────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "그릇이 있어요.", "실 같은 게 있어요.", "그릇이 있고 상자도 있어요.", "그릇이 있어요. 그릇이 커요.",
    "선 같은 실이 있어요.", "그릇이 있어요. 실도 있어요.", "판판한 판이 있어요.", "막 같은 종이가 있어요.",
])
def test_g40_removed_records_keep_word_and_span_in_provenance(an, v2, text):
    """기본 형상 근거가 된 명사의 v1 기록(_unmapped object·shape·unlisted_noun)이 v2에서 빠지면, 그 낱말과 글자 위치가
    _provenance['form.base'](같은 형상) 또는 _alternatives(path form.base, 다른 형상)에 남는다."""
    old = SceneSpecBuilderV1(an).build(text)
    spec = build(v2, text)
    keep = {(u["lemma"], tuple(u["_provenance"]["charSpan"])) for u in spec["_unmapped"]}
    gone = [u for u in old["_unmapped"] if (u["lemma"], tuple(u["_provenance"]["charSpan"])) not in keep]
    assert gone, "빠진 기록이 있는 문장을 골랐다"
    traces = [p for p in spec["_provenance"].get("form.base", [])]
    traces += [p for al in spec["_alternatives"] if al["path"] == "form.base" for p in al["_provenance"]]
    for u in gone:
        s, e = u["_provenance"]["charSpan"]
        assert any(p["trigger"] == u["lemma"] and s <= p["charSpan"][0] and p["charSpan"][1] <= e for p in traces), u


# ── G41 저장된 이전 판 파일 ────────────────────────────────────────────────
@pytest.mark.parametrize("name,version", [("spec_2.0.0.json", "2.0.0"), ("spec_2.1.0.json", "2.1.0"),
                                          ("spec_2.2.0_builder-2.2.0.json", "2.2.0")])
def test_g41_legacy_spec_files_still_validate(name, version):
    spec = json.loads((LEGACY / name).read_text(encoding="utf-8"))
    assert spec["meta"]["specVersion"] == version
    assert schema_errors(spec) == []
    assert b"\r\n" not in (LEGACY / name).read_bytes()


@pytest.mark.parametrize("sel,spec,version", [
    ("sel_0.1_spec-2.0.0.json", "spec_2.0.0.json", "ifs-selection/0.1"),
    ("sel_0.1_spec-2.1.0.json", "spec_2.1.0.json", "ifs-selection/0.1"),
    ("sel_0.2_d6_spec-2.2.0.json", "spec_2.2.0_builder-2.2.0.json", "ifs-selection/0.2"),
])
def test_g41_legacy_selection_files_match_their_specs_and_runner_contract(sel, spec, version):
    data = json.loads((LEGACY / sel).read_text(encoding="utf-8"))
    assert data["formatVersion"] == version
    assert data["specSha256"] == hashlib.sha256((LEGACY / spec).read_bytes()).hexdigest()
    assert runner_contract_errors(data) == []
    if version == "ifs-selection/0.1":
        valid(data, VALIDATOR01)                           # 0.1 스키마(러너 쪽 합성 입력과 같은 기준)
    assert "form.baseVariant" not in data["sources"]


def test_g41_legacy_files_have_no_local_paths():
    for p in LEGACY.iterdir():
        raw = p.read_text(encoding="utf-8")
        assert ":\\" not in raw and "Users" not in raw and "/home/" not in raw, p.name
