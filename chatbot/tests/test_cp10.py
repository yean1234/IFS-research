"""CP10(docs/codex-reviews/CP10.md) 반영 — G37 안전 제외 우회, G38 낱말 뜻에서 온 변형값 표시, G39 form.baseVariant 출처와
형태 조절 기록, G40 기본 형상 근거 명사의 기록, G41 저장된 이전 판 파일. 판정과 세부는 docs/decisions.md 'CP10 반영 세부'.
모든 문장은 합성 대사다(AGENTS.md 6). held-out 코퍼스는 열지 않는다."""
import hashlib
import json

import pytest

from ifs_chatbot.candidates import generate, load_table, shape_words, unrendered_shape_words
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
    return [u for u in spec["_unmapped"] if u["reason"] == "excluded_shape"]


def test_builder_and_lexicon_versions():
    assert BUILDER_ID == "scene-spec-builder-v2/2.3.0"
    assert LEX["lexiconVersion"] == "0.6.0" and LEX["status"] == "draft"


# ── G37 안전 제외: 합성어·수식·부정·직유 ───────────────────────────────────
# (문장, 제외 기록에 있어야 할 낱말, 사유 코드). 고치기 전(builder 2.2.0)에는 '해골 그릇'·'아이 장난감 상자'가 container로 그려졌고
# '칼날'·'칼집'·'사람 형상'·'피 웅덩이'·'피그릇'·부정·'-처럼 생긴 거예요'는 제외 기록이 없었다(docs/decisions.md 'CP10 반영 세부')
@pytest.mark.parametrize("text,lemma,code", [
    ("칼날 같은 게 있어요.", "칼날", "weapon"),                 # Kiwi 한 토큰 → 합성어 목록
    ("칼집이 있어요.", "칼집", "weapon"),
    ("작은 아이가 있어요.", "아이", "human_figure"),
    ("사람 형상이에요.", "사람", "human_figure"),              # 띄어 쓴 명사 + 명사
    ("아이 장난감 상자예요.", "상자", "human_figure"),         # 넓힌 명사 연속 전체를 그리지 않음
    ("해골 그릇이 있어요.", "그릇", "death_trauma"),
    ("피 웅덩이가 있어요.", "피 웅덩이", "blood_noose"),       # 기록이 없던 말 → 넓힌 연속으로 새 기록
    ("피그릇이 있어요.", "피그릇", "blood_noose"),             # Kiwi가 피 + 그릇으로 자름
    ("사람이 아니에요.", "사람", "human_figure"),              # 부정도 기록
    ("핏방울 같은 게 있어요.", "핏방울", "blood_noose"),
])
def test_g37_excluded_morpheme_anywhere_in_noun_run_is_recorded_not_drawn(v2, text, lemma, code):
    spec = build(v2, text)
    assert spec["form"]["base"] is None and "form.base" not in spec["_provenance"]
    hits = [u for u in excluded(spec) if u["lemma"] == lemma]
    assert hits and all(u["value"]["excluded"] == code for u in hits), excluded(spec)
    assert all(f["excluded"] for u in hits for f in u["value"]["excludedForms"])


def test_g37_negated_and_simile_excluded_words_are_both_recorded(v2):
    spec = build(v2, "칼은 아니고 칼처럼 생긴 거예요.")
    recs = sorted(excluded(spec), key=lambda u: u["_provenance"]["charSpan"][0])
    assert [u["lemma"] for u in recs] == ["칼", "칼"]
    assert recs[0]["value"].get("negated") is True and recs[1]["value"].get("simile") == "처럼"
    assert all(u["value"]["excluded"] == "weapon" for u in recs)


def test_g37_converted_records_keep_their_prior_reason(v2):
    """G40과 같은 방향: 기록을 excluded_shape로 바꿀 때 원래 사유를 value.priorReason에 남긴다."""
    spec = build(v2, "해골 그릇이 있어요.")
    by = {u["lemma"]: u for u in excluded(spec)}
    assert by["그릇"]["category"] == "object" and by["그릇"]["value"]["priorReason"] == "no_scene_param"
    assert by["그릇"]["value"]["excludedPhrase"] == "해골 그릇"


@pytest.mark.parametrize("text,blocked", [
    ("뱀 같은 끈이 있어요.", "끈"),
    ("뱀처럼 생긴 끈이에요.", "끈"),
    ("끈이 있는데 뱀 같아요.", "끈"),                         # 직유가 뒤에 와도 같은 문장
    ("괴물 같은 불꽃이 있어요.", "불꽃"),
    ("칼날 같은 불꽃이 있어요.", "불꽃"),
    ("아이 같은 불꽃이 있어요.", "불꽃"),
    ("올가미 같은 밧줄이 있어요.", "밧줄"),
    ("피 같은 물방울이 있어요.", "물방울"),
    ("사람 그림자 같은 실이 있어요.", "실"),
    ("칼 같은 건 아니고 끈이에요.", "끈"),                    # 부정된 직유도 막음(⚠ 사람이 정할 것)
])
def test_g37_excluded_simile_source_blocks_bases_in_the_same_sentence(v2, text, blocked):
    """제외 낱말이 직유 원천이면 같은 문장의 형상 낱말을 그리지 않는다(공격하는 존재 등의 모양을 본뜬 것으로 그리지 않음).
    막힌 낱말의 기록에 excludedBy, 그 기록은 모양어로 세지 않아 형태 후보를 벌리지 않는다(G32 경로 안 탐)."""
    spec = build(v2, text)
    assert spec["form"]["base"] is None and spec["form"]["baseVariant"] is None
    b = [u for u in excluded(spec) if u["lemma"] == blocked]
    assert len(b) == 1 and b[0]["value"]["excludedBy"]["rule"] == "simile_source"
    assert not unrendered_shape_words(spec, TABLE) and not shape_words(spec)
    out = generate(spec, "SYN-C", TABLE)
    assert all(ax["reason"] != "said_unrendered" for ax in out["axes"])


def test_g37_excluded_subject_in_another_clause_does_not_block(v2):
    """직유가 아닌 다른 주어('뱀이 있고')는 같은 문장의 다른 형상 낱말을 막지 않는다(참여자가 말한 다른 형상)."""
    spec = build(v2, "뱀이 있고 끈도 있어요.")
    assert spec["form"]["base"] == "line"
    assert [u["lemma"] for u in excluded(spec)] == ["뱀"]


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


@pytest.mark.parametrize("word", ["아이스크림", "칼슘", "칼국수", "피부", "커피", "피아노", "총각", "아이디어", "뱀장어", "화살표"])
def test_g37_lookalikes_are_single_tokens_and_not_listed(an, word):
    toks = [t for t in an.tokens(f"{word} 같아요.") if t.base_tag in ("NNG", "NNP")]
    assert [t.form for t in toks] == [word]
    listed = {w for k, ws in LEX["excluded"].items() if not k.startswith("_") and k != "notListed" for w in ws}
    listed |= {w for k, ws in LEX["excludedCompounds"].items() if not k.startswith("_") for w in ws}
    assert word not in listed


def test_g37_compounds_are_single_kiwi_tokens(an):
    """excludedCompounds는 Kiwi가 한 명사 토큰으로 내는 것만(둘로 자르면 형태소 판정이 이미 잡으므로 목록에 둘 필요가 없음)."""
    for code, ws in LEX["excludedCompounds"].items():
        if code.startswith("_"):
            continue
        assert code in LEX["excluded"]
        for w in ws:
            toks = [t for t in an.tokens(f"{w} 같아요.") if t.base_tag in ("NNG", "NNP")]
            assert [t.form for t in toks] == [w], (w, [t.form for t in toks])


def test_g37_homonym_left_out_stays_out(v2):
    """동음이의로 뺀 '창'(무기 | 창문)은 계속 목록 밖 — 기록 사유가 틀리지 않게."""
    assert "창" not in {w for k, ws in LEX["excluded"].items() if k != "notListed" and not k.startswith("_") for w in ws}
    assert "창" not in {w for k, ws in LEX["excludedCompounds"].items() if not k.startswith("_") for w in ws}
    spec = build(v2, "창이 있어요.")
    assert not excluded(spec)


@pytest.mark.parametrize("text", ["아이 장난감 상자예요.", "꼬마전구가 있어요."])
def test_g37_known_conservative_over_exclusion(v2, text):
    """안전 쪽으로 넓게 잡아 사람을 그리지 않는 말도 그리지 않는다(⚠ 사람이 정할 것). 동작을 고정해 둔다."""
    spec = build(v2, text)
    assert spec["form"]["base"] is None
    assert any(u["value"]["excluded"] == "human_figure" for u in excluded(spec))


def test_g37_recall_sentence_is_still_not_marked(v2):
    spec = build(v2, "어제 사람이 많았던 장면이 생각나요.")
    assert not excluded(spec)


@pytest.mark.parametrize("text", ["칼날 같은 게 있어요.", "뱀 같은 끈이 있어요.", "해골 그릇이 있어요.", "그릇이 있어요."])
def test_g37_v1_output_unchanged_by_v2_lexicon(an, text):
    """v1 매퍼는 기본 형상 사전을 읽지 않는다 — 같은 문장의 v1 출력에 excluded_shape·form.base가 없다."""
    spec = SceneSpecBuilderV1(an).build(text)
    assert not any(u["reason"] == "excluded_shape" for u in spec["_unmapped"])
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
