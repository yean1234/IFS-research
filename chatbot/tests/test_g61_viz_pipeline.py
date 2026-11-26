"""G61 — 스펙 2.3(윤곽·발광), 형태 변이 규칙층, 연구자 승인형 사전 확장 도구.

문장은 모두 합성이다(AGENTS.md 6). held-out 코퍼스는 열지 않는다. 기본 설정(두 기능 꺼짐)에서 매퍼 v2 출력이
G61 전과 바이트 단위로 같은지(sha256 고정), 켰을 때 원칙 1·2(사전·규칙만, 말하지 않은 것을 추론하지 않음)를
지키는지 본다.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ifs_chatbot.config import MappingConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.scene_builder import dumps, normalize_confirmed
from ifs_chatbot.scene_builder_v2 import (BUILDER_ID, BUILDER_ID_EXT, SceneSpecBuilderV2, load_lexicon_chain)
from ifs_chatbot.scene_spec import (ASPECT_LEVELS, EMISSION_LEVELS, ROUNDNESS_LEVELS, SPEC_VERSION_V22, SPEC_VERSION_V23,
                                    check_principles, schema_errors)
from ifs_chatbot.variants import VariantRules, parse_tag

EXT = shared("lexicon", "layer1_lexicon.v2.json")
VAR = shared("lexicon", "variant_rules.v0.json")
TOOL = REPO_ROOT / "tools" / "lexicon_proposals.py"
PROPOSALS_DIR = REPO_ROOT / "docs" / "validation" / "lexicon-proposals"


@pytest.fixture(scope="module")
def analyzer():
    a = Analyzer()
    if not a.available:
        pytest.skip("kiwipiepy가 없으면 0층이 정규식 대체라 규칙이 다르게 걸린다")
    return a


@pytest.fixture(scope="module")
def plain(analyzer):
    return SceneSpecBuilderV2(analyzer)


@pytest.fixture(scope="module")
def var(analyzer):
    return SceneSpecBuilderV2(analyzer, variant_rules_path=VAR)


@pytest.fixture(scope="module")
def ext(analyzer):
    return SceneSpecBuilderV2(analyzer, ext_lexicon_path=EXT)


@pytest.fixture(scope="module")
def both(analyzer):
    return SceneSpecBuilderV2(analyzer, ext_lexicon_path=EXT, variant_rules_path=VAR)


def _ok(b, text):
    spec = b.build(text)
    assert check_principles(spec, normalize_confirmed(text)) == []
    return spec


def _rules(spec, path):
    return [p["rule"] for p in spec["_provenance"].get(path, [])]


# ── 기본값 불변 ───────────────────────────────────────────────────────────────
# G61 전 HEAD(d21f984)의 scene_builder_v2.py로 잰 출력 sha256. 윤곽·발광어와 의태어 변이형이 든 합성 문장이라
# 두 기능이 기본에서 새지 않았는지 본다(dev.json·mock_corpus.json 66개 + 합성 30개도 같은 비교로 모두 같았다 — 작업 기록)
PINNED = {
    "가슴 앞에 각진 회색 덩어리가 있어요.": "60114227b4441f9f5e1968a0e546fd5ccda50a00bb1d0e67a48e208cce3bb653",
    "머리 위에 빤짝빤짝 빛나는 공 같은 게 떠 있어요.": "245ca1709ca7e79d781b78a723283d2fbd69876b3d919be18f7aaff4b04abe6e",
    "꺼칠꺼칠한 네모난 상자가 눈앞에 있어요.": "2d3d02fae07067038d967bf263f45541692299a6c13952c2d3c34b1587763f95",
    "모가 난 돌덩이가 배 속에 있어요. 빛은 안 나요.": "113193351bae1dbd61b1af1cb97ce12ff4dbd9cc15f3e27085e14c85fa095665",
    "살짝 둥그스름하고 환하게 빛나요.": "7121a40c99e604bb557ad566d2ae6c3d92e6ae48a806fa917fc23dc891854566",
    "번질번질한 검은 덩어리가 꼼틀거려요.": "d8b72cfd5c2d97bb415f18ce9abc8f35e10520f1a3d733e11027a474beaa82ce",
}


@pytest.mark.parametrize("text,sha", list(PINNED.items()))
def test_default_v2_output_unchanged_by_g61(plain, text, sha):
    assert hashlib.sha256(dumps(plain.build(text)).encode("utf-8")).hexdigest() == sha


def test_default_builder_id_and_version(plain):
    assert plain.builder_id == BUILDER_ID == "scene-spec-builder-v2/2.4.0"
    assert plain.info()["specVersion"] == SPEC_VERSION_V22
    spec = plain.build("둥근 덩어리가 빛나요.")
    assert "roundness" not in spec["form"] and "emission" not in spec["material"]
    assert "variantRules" not in spec["meta"]["pipeline"]["lexicons"]


def test_config_defaults_off_and_v4_loads():
    m = MappingConfig()
    assert m.ext_lexicon == "" and m.variant_rules == ""
    v4 = load_config("v4").mapping
    assert v4.mode == "v2" and v4.ext_lexicon == "" and v4.variant_rules == ""


def test_runtime_builds_ext_builder_from_config(offline_cfg, tmp_path):
    rt = Runtime(offline_cfg.with_overrides(**{
        "session.log_dir": str(tmp_path / "logs"), "mapping.mode": "v2",
        "mapping.ext_lexicon": "layer1_lexicon.v2.json", "mapping.variant_rules": "variant_rules.v0.json"}))
    b = rt.scene_builder
    assert isinstance(b, SceneSpecBuilderV2) and b.spec_version == SPEC_VERSION_V23 and b.builder_id == BUILDER_ID_EXT
    lex = b.info()["lexicons"]
    assert lex["variantRules"].startswith("variant-rules@") and lex["sceneParamsV3"].startswith("scene-params-v3@")


def test_runtime_warns_when_ext_set_without_v2(offline_cfg, tmp_path):
    rt = Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path / "logs"),
                                               "mapping.variant_rules": "variant_rules.v0.json"}))
    assert any("mode = \"v2\"" in w for w in rt.warnings)


# ── 스키마 2.3 ─────────────────────────────────────────────────────────────────
def test_schema_v23_fields_and_ordinals():
    s = json.loads(shared("schemas", "scene-spec.v2.3.json").read_text(encoding="utf-8"))
    p = s["properties"]
    assert p["form"]["properties"]["roundness"]["enum"] == [*ROUNDNESS_LEVELS, None]
    assert p["form"]["properties"]["aspect"]["enum"] == [*ASPECT_LEVELS, None]
    assert p["material"]["properties"]["emission"]["enum"] == [*EMISSION_LEVELS, None]
    p3 = json.loads(shared("lexicon", "scene_params.v3.json").read_text(encoding="utf-8"))
    assert p3["ordinal"]["form.roundness"]["levels"] == list(ROUNDNESS_LEVELS)
    assert p3["ordinal"]["form.aspect"]["levels"] == list(ASPECT_LEVELS)
    assert p3["ordinal"]["material.emission"]["levels"] == list(EMISSION_LEVELS)
    r = p3["render"]
    assert set(r["contour"]["superquadric"]) == set(ROUNDNESS_LEVELS)
    assert set(r["contour"]["aspectRatios"]) == set(ASPECT_LEVELS)
    assert all(max(v) == 1.0 for v in r["contour"]["aspectRatios"].values())    # 긴 축 = 1(layout.size 뜻 유지)
    assert set(r["emission"]["intensity"]) == set(EMISSION_LEVELS) and r["emission"]["intensity"]["none"] == 0


def test_v23_document_requires_new_keys_and_v22_rejects_them(ext, plain):
    spec = ext.build("둥근 덩어리예요.")
    assert schema_errors(spec) == []
    bad = json.loads(json.dumps(spec))
    del bad["material"]["emission"]
    assert schema_errors(bad)
    old = plain.build("둥근 덩어리예요.")
    old["form"]["roundness"] = None
    assert schema_errors(old) and any("2.3.0 전용" in x for x in check_principles(old, normalize_confirmed("둥근 덩어리예요.")))


# ── 1층 사전 v2 ────────────────────────────────────────────────────────────────
def test_v2_overlay_examples_hit_their_lemma(analyzer):
    lex = load_lexicon_chain(analyzer, [shared("lexicon", "layer1_lexicon.v0.json"),
                                        shared("lexicon", "layer1_lexicon.v1.json"), EXT])
    ov = json.loads(EXT.read_text(encoding="utf-8"))
    miss = [e["lemma"] for e in ov["entries"]
            if not any(h.entry.lemma == e["lemma"] and h.entry.category == e["category"] for h in lex.hits(e["ex"]))]
    assert miss == []
    assert {e["category"] for e in ov["entries"]} == {"contour", "emission"}


def test_v2_overlay_has_no_emotion_or_inferred_words():
    """감정어·온도어로 윤곽·발광을 정하는 항목이 없다(원칙 2)."""
    ov = json.loads(EXT.read_text(encoding="utf-8"))
    v0 = json.loads(shared("lexicon", "layer1_lexicon.v0.json").read_text(encoding="utf-8"))
    emo = {e["lemma"] for e in v0["entries"] if e["category"] in ("emotion", "sensation", "temperature")}
    assert not emo & {e["lemma"] for e in ov["entries"]}


# ── 윤곽·발광 값 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,path,value", [
    ("각진 돌이에요.", "form.roundness", "angular"),
    ("가슴 앞에 각진 회색 덩어리가 있어요.", "form.roundness", "angular"),     # Kiwi: 각/NNG + 지/VV (구 규칙)
    ("모가 나 있어요.", "form.roundness", "angular"),
    ("각이 져 있어요.", "form.roundness", "angular"),
    ("모난 덩어리예요.", "form.roundness", "angular"),
    ("네모난 덩어리예요.", "form.roundness", "angular"),
    ("동그란 덩어리예요.", "form.roundness", "rounded"),
    ("둥그스름해요.", "form.roundness", "slightly_rounded"),
    ("살짝 둥근 덩어리예요.", "form.roundness", "slightly_rounded"),      # 약한 정도 부사: 한 단계 중립 쪽
    ("살짝 각진 덩어리예요.", "form.roundness", "slightly_angular"),
    ("길쭉한 덩어리예요.", "form.aspect", "elongated"),
    ("기다란 막대 같아요.", "form.aspect", "elongated"),
    ("납작해요.", "form.aspect", "flattened"),
    ("넓적해요.", "form.aspect", "flattened"),
    ("빛나는 덩어리예요.", "material.emission", "glowing"),
    ("환한 덩어리예요.", "material.emission", "glowing"),
    ("반짝여요.", "material.emission", "faint"),
    ("살짝 빛나요.", "material.emission", "faint"),
    ("빛이 좀 나요.", "material.emission", "faint"),                     # 구 + 용언 앞 정도 부사
    ("빛나지 않아요.", "material.emission", "none"),                      # 발광어 부정 = 말한 값 none
    ("빛이 안 나요.", "material.emission", "none"),
])
def test_ext_values(ext, text, path, value):
    spec = _ok(ext, text)
    g, k = path.split(".")
    assert spec[g][k] == value, (text, spec[g], spec["_provenance"].get(path))
    assert spec["meta"]["specVersion"] == SPEC_VERSION_V23


def test_ext_does_not_infer_from_emotion_or_unsaid(ext):
    spec = _ok(ext, "불안하고 답답해요. 회색 덩어리예요.")
    assert spec["form"]["roundness"] is None and spec["form"]["aspect"] is None and spec["material"]["emission"] is None
    spec = _ok(ext, "밝은 노란색이에요.")                                   # 밝다 = 명도, 발광 아님
    assert spec["material"]["emission"] is None


def test_contour_negation_does_not_produce_opposite(ext):
    spec = _ok(ext, "둥글지 않아요.")
    assert spec["form"]["roundness"] is None
    assert any(n["category"] == "contour" and n["lemma"] == "둥글" for n in spec["_negated"])


def test_scope_rules_background_part_correction_uncertain(ext):
    spec = _ok(ext, "둥근 탁자 위에 납작한 게 있어요.")
    assert spec["form"]["roundness"] is None and spec["form"]["aspect"] == "flattened"
    assert any(c["path"] == "form.roundness" and c["reason"] == "background_object" for c in spec["_context"])
    spec = _ok(ext, "가장자리가 빛나요.")                                   # 부분만 → 전체 값 아님
    assert spec["material"]["emission"] is None
    assert any(p["path"] == "material.emission" and p["part"] == "가장자리" for p in spec["_parts"])
    spec = _ok(ext, "아 아니 둥글어요, 아니다 각졌어요.")
    assert spec["form"]["roundness"] == "angular"
    assert any(a["path"] == "form.roundness" and a["reason"] == "self_corrected" for a in spec["_alternatives"])
    spec = _ok(ext, "처음엔 둥글었다가 지금은 각졌어요.")
    assert spec["form"]["roundness"] == "angular"


def test_shape_word_keeps_unmapped_record_for_unity_model(ext, plain):
    """'둥근'은 v0 shape(Unity 구 모형, _unmapped)와 윤곽(form.roundness)에 함께 걸린다 — 모형 경로 기록은 그대로."""
    t = "둥근 덩어리예요."
    a, b = _ok(ext, t), plain.build(t)
    assert a["_unmapped"] == b["_unmapped"] and a["form"]["roundness"] == "rounded"
    for k in ("type", "posture", "base", "baseVariant"):
        assert a["form"][k] == b["form"][k]


def test_ext_is_deterministic(both):
    t = "꺼칠꺼칠하고 살짝 둥근 게 빤짝빤짝 빛나요."
    assert dumps(both.build(t)) == dumps(both.build(t))


def test_unlisted_noun_record_removed_when_phrase_uses_it(ext):
    spec = _ok(ext, "모가 나 있어요.")
    assert not any(u["category"] == "unlisted_noun" and u["lemma"] == "모" for u in spec["_unmapped"])


# ── 형태 변이 규칙층 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,path,root,rule,grade", [
    ("꺼칠꺼칠해요.", "material.roughness", "까칠", "ideophone_vowel", "larger"),
    ("꺼칠해요.", "material.roughness", "까칠", "ideophone_vowel", "larger"),
    ("번질번질해요.", "material.roughness", "반질반질", "ideophone_vowel", "larger"),
    ("꼼틀거려요.", "motion.type", "꿈틀거리", "ideophone_vowel", "smaller"),
    ("빤짝빤짝해요.", "material.brightness", "반짝반짝", "ideophone_consonant", "stronger"),
    ("빤짝여요.", "material.brightness", "반짝이", "ideophone_consonant", "stronger"),   # Kiwi가 조각낸 어절
])
def test_variant_positive(var, text, path, root, rule, grade):
    spec = _ok(var, text)
    rules = _rules(spec, path)
    assert rules and rules[0].startswith("variant("), (text, spec["_provenance"])
    tag = parse_tag(rules[0])
    assert tag["root"] == root and rule in tag["rules"] and grade in tag["grade"]
    assert spec["meta"]["specVersion"] == SPEC_VERSION_V22                      # 변이만 켜면 스펙은 2.2 그대로
    assert "variant" not in spec["_provenance"][path][0]                       # 2.2에는 구조 필드가 없다(rule 꼬리표만)


def test_variant_grade_does_not_change_value(var, plain):
    """큰말·센소리여도 값은 뿌리와 같다(강도 차이는 기록만)."""
    a = _ok(var, "꺼칠꺼칠해요.")["material"]["roughness"]
    b = _ok(plain, "까칠까칠해요.")["material"]["roughness"]
    assert a == b


@pytest.mark.parametrize("text", [
    "부들부들 떨려요.",       # 불용: 떨림(부들부들) ↔ 보들보들
    "철렁해요.",              # 불용: 가슴이 내려앉음 ↔ 찰랑
    "통통 튀는 공 같아요.",   # 모음+자음 동시 교체는 꺼 둠(통통 → 둥둥 오대응)
    "말려 있는 종이 같아요.",  # 용언 원형에는 교체를 걸지 않음(말리 → 멀리 오대응)
    "물컹물컹해요.",          # 뿌리가 사전에 없으면 대응하지 않음
    "사과가 있어요.",          # 보통 명사
])
def test_variant_negative(var, plain, text):
    a, b = _ok(var, text), plain.build(text)
    assert not any("variant(" in p["rule"] for ps in a["_provenance"].values() for p in ps)
    assert not any("variant(" in u["_provenance"]["rule"] for u in a["_unmapped"] + a["_negated"])
    for g in ("form", "material", "layout", "motion", "body"):
        assert a[g] == b[g]


def test_variant_precedes_fuzzy(var, plain):
    """변이 규칙이 값을 내면 그 토큰은 자모 퍼지(확인 필요 대안)로 가지 않는다."""
    t = "꺼칠해요."
    assert any(x["reason"] == "needs_confirmation" for x in plain.build(t)["_alternatives"])
    spec = _ok(var, t)
    assert not any(x["reason"] == "needs_confirmation" for x in spec["_alternatives"]) and not spec["_needsConfirmation"]


def test_variant_existing_mimetic_derivation_first(var, plain):
    """기존 의태어 파생(v1 mimeticDerivation)이 걸리는 말은 변이 규칙이 건드리지 않는다."""
    for t in ("번쩍번쩍해요.", "까끌거려요.", "출렁여요."):
        assert var.build(t)["_provenance"] == plain.build(t)["_provenance"]


def test_variant_negated_goes_to_negated(var):
    spec = _ok(var, "꺼칠하지 않아요.")
    assert spec["material"]["roughness"] is None
    assert any(n["lemma"] == "까칠" and n["_provenance"]["rule"].startswith("variant(") for n in spec["_negated"])


def test_variant_root_without_scene_value_is_recorded_unmapped(var):
    spec = _ok(var, "탄탄해요.")                         # 탄탄 → 단단(사전: texture firm, 장면 값 없음)
    assert any(u["lemma"] == "단단" and u["_provenance"]["rule"].startswith("variant(") for u in spec["_unmapped"])
    assert not any(u["surface"].startswith("탄탄") for u in spec["_unmatched"])


def test_variant_structured_record_in_v23(both):
    spec = _ok(both, "빤짝빤짝해요.")
    p = spec["_provenance"]["material.emission"][0]
    assert spec["material"]["emission"] == "faint"
    assert p["variant"] == {"rules": ["suffix:하", "ideophone_consonant"], "surface": "빤짝빤짝", "root": "반짝반짝",
                            "grade": ["stronger"]}
    assert p["rule"].startswith("variant(suffix:하>ideophone_consonant;surface=빤짝빤짝;root=반짝반짝;grade=stronger)>")


def test_variant_rules_table_unit():
    v = VariantRules(VAR)
    from ifs_chatbot.lexicon import LexEntry
    table = {"말랑": [LexEntry("말랑", "XR", "texture", {"texture": "soft"})],
             "단단": [LexEntry("단단", "XR", "texture", {"texture": "firm"})]}
    look = lambda f: table.get(f, [])  # noqa: E731
    m = v.resolve("물렁물렁", "MAG", None, look, lambda e: True)
    assert m is not None and m.root == "말랑" and "reduplication" in m.rules and m.grades == ("larger",)
    m = v.resolve("딴딴", "XR", None, look, lambda e: True)
    assert m is not None and m.root == "단단" and m.grades == ("stronger",)
    assert v.resolve("말랑", "XR", None, look, lambda e: True) is None          # 규칙 없는 같은 꼴 = 직접 일치 몫
    assert v.resolve("부들부들", "MAG", None, look, lambda e: True) is None     # 불용


# ── 연구자 승인형 사전 확장 도구 ──────────────────────────────────────────────────
def _tool(*args, cwd=REPO_ROOT):
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})


def test_tool_collect_from_spec_files_and_merge_only_approved(tmp_path, both):
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    for k, t in enumerate(["꺼끌꺼끌하고 뭉툭한 덩어리예요.", "뭉툭한 게 아른거려요."]):
        (scenes / f"SYN{k}.json").write_text(dumps(both.build(t)), encoding="utf-8")
    out = tmp_path / "p.proposals.json"
    r = _tool("collect", str(scenes), "--source", "synthetic test", "--out", str(out))
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text(encoding="utf-8"))
    terms = {it["term"]: it for it in doc["items"]}
    assert "뭉툭" in terms and terms["뭉툭"]["count"] == 2 and terms["뭉툭"]["decision"]["status"] == "proposed"
    assert all(it["decision"]["approvedBy"] == "" and it["decision"]["approvedOn"] == "" for it in doc["items"])
    # 승인 하나 + 반려 하나 + 미결정 나머지 → 승인한 것만 합쳐진다
    it = terms["뭉툭"]
    it["decision"].update({"status": "approved", "lemma": "뭉툭", "pos": "XR", "category": "contour",
                           "value": {"roundness": "slightly_rounded"}, "ex": "뭉툭한 덩어리예요",
                           "approvedBy": "연구자A", "approvedOn": "2026-11-26"})
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    lex_out = tmp_path / "layer1_lexicon.v2.1.json"
    r = _tool("merge", str(out), "--out", str(lex_out))
    assert r.returncode == 0, r.stderr
    new = json.loads(lex_out.read_text(encoding="utf-8"))
    base = json.loads(EXT.read_text(encoding="utf-8"))
    assert new["lexiconVersion"] == "2.1.0" and len(new["entries"]) == len(base["entries"]) + 1
    added = new["entries"][-1]
    assert added["lemma"] == "뭉툭" and added["review"]["approvedBy"] == "연구자A" and added["src"].startswith("review:")
    assert new["reviewMerge"]["proposals"][0]["sha256"].startswith("sha256:")
    # 새 사전으로 매퍼를 만들면 그 낱말이 걸린다(실행 경로는 설정으로 고를 때만 바뀜)
    b2 = SceneSpecBuilderV2(both.analyzer, ext_lexicon_path=lex_out)
    assert b2.build("뭉툭한 덩어리예요.")["form"]["roundness"] == "slightly_rounded"
    assert both.build("뭉툭한 덩어리예요.")["form"]["roundness"] is None


def test_tool_merge_refuses_unsigned_or_invalid(tmp_path):
    doc = json.loads((PROPOSALS_DIR / "priority-imagery.proposals.json").read_text(encoding="utf-8"))
    doc["items"][0]["decision"].update({"status": "approved", "lemma": "빽빽", "pos": "XR", "category": "texture",
                                        "value": {"texture": "dense"}})             # 승인자·날짜 없음
    p = tmp_path / "x.proposals.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = _tool("merge", str(p), "--out", str(tmp_path / "o.json"))
    assert r.returncode == 2 and "approvedBy" in r.stderr and not (tmp_path / "o.json").exists()
    doc["items"][0]["decision"].update({"approvedBy": "A", "approvedOn": "2026-11-26", "category": "color"})
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    r = _tool("merge", str(p), "--out", str(tmp_path / "o.json"))
    assert r.returncode == 2 and not (tmp_path / "o.json").exists()


def test_committed_proposals_examples_are_synthetic_and_unapproved():
    for f in ("priority-imagery.proposals.json", "synthetic-collect.proposals.json"):
        doc = json.loads((PROPOSALS_DIR / f).read_text(encoding="utf-8"))
        assert doc["format"] == "ifs-lexicon-proposals/0.1" and "synthetic" in doc["source"]
        assert all(it["decision"]["status"] == "proposed" and not it["decision"]["approvedBy"] for it in doc["items"])
    words = json.loads((PROPOSALS_DIR / "priority-imagery-words.json").read_text(encoding="utf-8"))
    ov = json.loads(EXT.read_text(encoding="utf-8"))
    # 합성 후보 목록은 사전에 합치지 않았다(직접 넣은 각지만 겹침)
    assert {w["term"] for w in words["words"]} & {e["lemma"] + "다" for e in ov["entries"]} <= {"각지다"}


def test_tool_default_output_is_git_ignored():
    r = subprocess.run(["git", "-C", str(REPO_ROOT), "check-ignore", "-q",
                        str(REPO_ROOT / "chatbot" / "logs" / "lexicon-proposals" / "x.proposals.json")])
    assert r.returncode == 0
