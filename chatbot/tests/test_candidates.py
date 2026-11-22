"""후보 생성기(candidates.py, D3·결정 G14–G20) — 결정성, 말한 슬롯 불변, 2×2 구성과 우선순위, 한 차원·빈 자리 없음, 갈림, 순서 순환.
모든 문장은 합성 대사다."""
import copy
import hashlib
import itertools
import json

import pytest

from ifs_chatbot.candidates import (GENERATOR_VERSION, SLOTS, candidates_bytes, effective_params, generate,
                                    load_table, slot_is_open, spec_sha256)
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2

TABLE = load_table()
DEFAULTS = TABLE["defaults"]
DIM_SLOTS = {d: v["slot"] for d, v in TABLE["candidateAxes"]["dimensions"].items()}

T_FORM = "가슴 앞에 연기 같은 게 있어요. 작아요."
T_FEEL = "가슴 안쪽이 답답하고 무거운 느낌이에요."
T_ALL = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 안 움직여요. 불투명해요. 어두워요."
T_ONE = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 안 움직여요. 불투명해요."
T_CLOUD = "배 안쪽에 구름이 있어요. 하얀색이에요."
T_SHAPE = "목에 네모난 게 걸려 있어요."


@pytest.fixture(scope="module")
def v2():
    return SceneSpecBuilderV2(Analyzer())


@pytest.fixture(scope="module")
def specs(v2):
    return {t: v2.build(t, session_id="SYN-GOLD") for t in (T_FORM, T_FEEL, T_ALL, T_ONE, T_CLOUD, T_SHAPE)}


def empty_spec():
    """모든 슬롯이 빈 최소 spec(합성)."""
    return {"meta": {"specVersion": "2.1.0", "sessionId": "X", "pipeline": {"builder": "test"}},
            "form": {"type": None, "posture": None},
            "material": {"color": None, "brightness": None, "saturation": None, "roughness": None, "opacity": None, "erosion": None},
            "layout": {"size": None, "distance": None, "verticalOffset": None},
            "motion": {"type": None, "speed": None}, "body": {"part": None, "layer": None},
            "_provenance": {}, "_unmapped": []}


# ── 결정성(완료 기준) ─────────────────────────────────────────────────────────
GOLDEN = {
    T_FORM: "1f1919128a636cdb3a494f0e5306947743e08ebc086eddeab9b43ebcea33b3f7",
    T_FEEL: "25a2b34390c9757214428f68ae179c21ca2929e2b27c70fc29a090ff13c6da54",
    T_CLOUD: "05bfce1470346df37435633dbb85d649d296298cfdaeb1b720716d9d6be09f7e",
}


@pytest.mark.parametrize("text", list(GOLDEN))
def test_output_sha256_is_pinned(v2, text):
    """같은 확정 텍스트 → 같은 spec → 같은 후보 바이트(sha256 고정). 표·생성기·매퍼를 바꾸면 이 값이 바뀐다."""
    spec = v2.build(text, session_id="SYN-GOLD")
    assert hashlib.sha256(candidates_bytes(generate(spec, "SYN-GOLD"))).hexdigest() == GOLDEN[text]


@pytest.mark.parametrize("text", [T_FORM, T_FEEL, T_CLOUD, T_ALL])
def test_same_text_twice_same_spec_and_candidates(v2, text):
    a, b = v2.build(text, session_id="SYN-A"), v2.build(text, session_id="SYN-A")
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)
    assert candidates_bytes(generate(a, "SYN-A")) == candidates_bytes(generate(b, "SYN-A"))


def test_candidate_content_independent_of_session_id(v2):
    """sessionId가 달라도 후보 내용(id·덮어쓰기)은 같고 화면 순서만 바뀔 수 있다."""
    a = generate(v2.build(T_FEEL, session_id="SYN-A"), "SYN-A")
    b = generate(v2.build(T_FEEL, session_id="SYN-B"), "SYN-B")
    assert a["specSha256"] == b["specSha256"]
    assert a["candidates"] == b["candidates"]
    assert sorted(a["displayOrder"]) == sorted(b["displayOrder"])


def test_candidate_ids_from_spec_hash_version_and_index(specs):
    out = generate(specs[T_FEEL], "S")
    for c in out["candidates"]:
        expect = "c-" + hashlib.sha256(f"{GENERATOR_VERSION}|{out['specSha256']}|{c['index']}".encode()).hexdigest()[:12]
        assert c["id"] == expect
    assert len({c["id"] for c in out["candidates"]}) == len(out["candidates"])


def test_no_randomness_or_time_in_module():
    src = (shared("..", "chatbot", "ifs_chatbot", "candidates.py")).read_text(encoding="utf-8")
    for banned in ("import random", "import time", "datetime", "uuid", "llm", "secrets"):
        assert banned not in src


def test_input_spec_not_mutated(specs):
    spec = specs[T_FORM]
    before = copy.deepcopy(spec)
    generate(spec, "S")
    assert spec == before


# ── 말한 슬롯 불변(G9) ────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [T_FORM, T_FEEL, T_ALL, T_ONE, T_CLOUD, T_SHAPE])
def test_said_slots_never_change(specs, text):
    spec = specs[text]
    base = effective_params(spec, DEFAULTS)
    said = [s for s in SLOTS if spec[s.split(".")[0]][s.split(".")[1]] is not None]
    for c in generate(spec, "S")["candidates"]:
        eff = effective_params(spec, DEFAULTS, c["overrides"])
        for slot in said:
            for key in [k for k in eff if k == slot or k.startswith(slot + ".")] or []:
                assert eff[key] == base[key], (text, slot, c)
            assert c["sources"][slot] == "said"
        assert not (set(c["axisValues"]) & set(said))


def test_property_said_slots_unchanged_over_slot_combinations():
    """빈 spec에 여섯 차원 슬롯을 하나씩 채운 모든 조합(64가지)에서 말한 슬롯은 덮어쓰기에 없다."""
    fills = {"form.type": "shell", "layout.size": 0.6, "material.opacity": 0.8, "material.brightness": 0.3,
             "material.roughness": 0.7, "motion.type": "sinking"}
    keys = list(fills)
    for mask in itertools.product([0, 1], repeat=len(keys)):
        spec = empty_spec()
        said = [k for k, m in zip(keys, mask) if m]
        for k in said:
            g, n = k.split(".")
            spec[g][n] = fills[k]
        out = generate(spec, "S")
        for c in out["candidates"]:
            assert not (set(c["overrides"]) & set(said)), (said, c["overrides"])
        n_open = len(keys) - len(said)
        assert len(out["candidates"]) == (4 if n_open >= 2 else (len(TABLE["candidateAxes"]["dimensions"][
            next(d for d, v in TABLE["candidateAxes"]["dimensions"].items() if v["slot"] not in said)]["levels"]) if n_open == 1 else 1))


def test_shape_word_counts_as_said_form(specs):
    """모양어('네모난')를 말했으면 form.type이 비어 있어도 형태는 벌리지 않는다(말한 모양이 그려지지 않게 되므로)."""
    spec = specs[T_SHAPE]
    assert spec["form"]["type"] is None and any(u["category"] == "shape" for u in spec["_unmapped"])
    assert not slot_is_open(spec, "form.type")
    out = generate(spec, "S")
    assert "form.type" not in [a["slot"] for a in out["axes"]]
    assert all("form.type" not in c["overrides"] for c in out["candidates"])


# ── 2×2 구성과 우선순위(G16) ──────────────────────────────────────────────────
def test_all_empty_is_form_by_size_2x2(specs):
    """느낌만 말해 형상 슬롯이 전부 비면 형태 × 크기 2×2(G19)."""
    out = generate(specs[T_FEEL], "S")
    assert [a["slot"] for a in out["axes"]] == ["form.type", "layout.size"]
    assert [a["reason"] for a in out["axes"]] == ["empty", "empty"]
    assert [c["axisValues"] for c in out["candidates"]] == [
        {"form.type": "blob", "layout.size": 0.5}, {"form.type": "blob", "layout.size": 0.7},
        {"form.type": "mist", "layout.size": 0.5}, {"form.type": "mist", "layout.size": 0.7}]


def test_grid_index_zero_is_baseline_without_overrides():
    for spec in (empty_spec(),):
        out = generate(spec, "S")
        c0 = out["candidates"][0]
        assert c0["index"] == 0 and c0["overrides"] == {}


@pytest.mark.parametrize("dim", list(DIM_SLOTS))
def test_table_level0_and_pair0_are_defaults(dim):
    d = TABLE["candidateAxes"]["dimensions"][dim]
    assert d["levels"][0] == DEFAULTS[d["key"]] and d["pair"][0] == DEFAULTS[d["key"]]
    assert d["pair"][1] in d["levels"] and len(d["levels"]) <= 4 and len(set(map(str, d["levels"]))) == len(d["levels"])


def test_candidate_values_lie_on_adjust_grid():
    """고른 후보에서 조절을 한 칸씩 이어 갈 수 있게, 후보 값은 모두 조절 항목의 값 목록 위에 있다."""
    items = TABLE["adjustItems"]["items"]
    by_key = {it["key"]: it["values"] for it in items.values() if "key" in it}
    for d in TABLE["candidateAxes"]["dimensions"].values():
        for v in d["levels"] + d["pair"]:
            assert any(v == x for x in by_key[d["key"]]), (d["key"], v)
    for e in TABLE["interpretationSplits"]["entries"]:
        assert all(r in by_key[e["slot"]] for r in e["readings"])


def test_priority_order_follows_g16():
    assert TABLE["candidateAxes"]["priority"] == ["form", "size", "opacity", "brightness", "texture", "motion"]
    spec = empty_spec()
    spec["form"]["type"] = "blob"
    spec["layout"]["size"] = 0.4
    out = generate(spec, "S")
    assert [a["slot"] for a in out["axes"]] == ["material.opacity", "material.brightness"]


def test_form_said_uses_next_two_dimensions(specs):
    out = generate(specs[T_FORM], "S")
    assert [a["slot"] for a in out["axes"]] == ["material.opacity", "material.brightness"]
    assert len(out["candidates"]) == 4


def test_hue_never_spread_g17():
    out = generate(empty_spec(), "S")
    for c in out["candidates"]:
        assert not any(k.startswith("material.color") for k in c["overrides"])
    assert "color" not in TABLE["candidateAxes"]["priority"]


def test_overrides_use_unity_keys_and_ranges():
    """덮어쓰기는 Unity SceneOverrideJson이 받는 평평한 객체: 수치 0–1, form.type 4값, motion.type은 MotionGroups 표."""
    unity_forms = {"blob", "mist", "shell", "fragments"}
    unity_motions = {"still", "swaying", "sloshing", "rippling", "churning", "trembling", "vibrating", "wriggling", "pounding",
                     "moving", "drifting", "floating", "rising", "sinking", "settling", "collapsing", "rotating", "circling",
                     "spreading", "scattering", "approaching", "pushing"}
    allowed = set(TABLE["overrideKeys"]["numeric"]) | set(TABLE["overrideKeys"]["categorical"])
    for dim in DIM_SLOTS:
        spec = empty_spec()
        for other, slot in DIM_SLOTS.items():   # 이 차원만 비우고 나머지는 말한 것으로
            if other != dim:
                g, n = slot.split(".")
                spec[g][n] = DEFAULTS[TABLE["candidateAxes"]["dimensions"][other]["key"]]
        for c in generate(spec, "S")["candidates"]:
            for k, v in c["overrides"].items():
                assert k in allowed
                if k == "form.type":
                    assert v in unity_forms
                elif k == "motion.type":
                    assert v in unity_motions
                else:
                    assert isinstance(v, float) and 0 <= v <= 1
    assert not (allowed & {"layout.distance", "layout.verticalOffset"})


# ── 한 차원·빈 자리 없음(G19) ──────────────────────────────────────────────────
def test_no_empty_slot_gives_single_candidate(specs):
    out = generate(specs[T_ALL], "S")
    assert len(out["candidates"]) == 1 and out["axes"] == [] and out["candidates"][0]["overrides"] == {}
    assert out["displayOrder"] == [out["candidates"][0]["id"]]


def test_single_open_dimension_uses_table_levels(specs):
    out = generate(specs[T_ONE], "S")
    assert [a["slot"] for a in out["axes"]] == ["material.brightness"]
    assert [c["axisValues"]["material.brightness"] for c in out["candidates"]] == \
        TABLE["candidateAxes"]["dimensions"]["brightness"]["levels"]


def test_single_open_texture_has_three_levels():
    spec = empty_spec()
    for slot, v in (("form.type", "blob"), ("layout.size", 0.5), ("material.opacity", 1.0), ("material.brightness", 0.5),
                    ("motion.type", "still")):
        g, n = slot.split(".")
        spec[g][n] = v
    out = generate(spec, "S")
    assert len(out["candidates"]) == 3 and out["axes"][0]["slot"] == "material.roughness"


def test_candidates_never_exceed_four(specs):
    for spec in list(specs.values()) + [empty_spec()]:
        assert 1 <= len(generate(spec, "S")["candidates"]) <= 4


# ── 낱말 해석 갈림(G18) ────────────────────────────────────────────────────────
def test_cloud_split_takes_first_axis(specs):
    spec = specs[T_CLOUD]
    assert any(u.get("category") == "object" and (u.get("value") or {}).get("object") == "cloud" for u in spec["_unmapped"])
    out = generate(spec, "S")
    assert out["axes"][0]["reason"] == "ambiguous" and out["axes"][0]["slot"] == "form.type"
    assert out["axes"][0]["split"]["id"] == "cloud" and out["axes"][0]["split"]["lemma"] == "구름"
    assert out["axes"][1] == {"slot": "layout.size", "reason": "empty", "values": [0.5, 0.7], "key": "layout.size"}


def test_split_skipped_when_target_slot_said():
    spec = empty_spec()
    spec["form"]["type"] = "shell"
    spec["_unmapped"] = [{"lemma": "구름", "category": "object", "value": {"object": "cloud"},
                          "_provenance": {"charSpan": [0, 2]}}]
    out = generate(spec, "S")
    assert all(a["reason"] == "empty" for a in out["axes"])
    assert out["splitSkipped"] and out["splitSkipped"][0]["id"] == "cloud"
    assert all("form.type" not in c["overrides"] for c in out["candidates"])


def test_split_table_is_closed_and_readings_start_at_default():
    for e in TABLE["interpretationSplits"]["entries"]:
        assert e["readings"][0] == DEFAULTS[e["slot"]] and e["status"] == "draft" and e["evidence"]


# ── 순서 순환(G20) ─────────────────────────────────────────────────────────────
def test_display_order_rotates_by_session_hash():
    spec = empty_spec()
    ids = [c["id"] for c in generate(spec, "S")["candidates"]]
    seen = set()
    for i in range(40):
        sid = f"SYN-{i:03d}"
        out = generate(spec, sid)
        off = int(hashlib.sha256(sid.encode()).hexdigest()[:8], 16) % 4
        assert out["displayOrder"] == ids[off:] + ids[:off]
        assert str(off) in out["orderRule"]
        seen.add(off)
    assert seen == {0, 1, 2, 3}


def test_spec_hash_ignores_identity_meta(specs):
    a = copy.deepcopy(specs[T_FEEL])
    b = copy.deepcopy(a)
    b["meta"]["sessionId"], b["meta"]["participantId"] = "OTHER", "P99"
    assert spec_sha256(a) == spec_sha256(b)
    b["material"]["opacity"] = 0.3
    assert spec_sha256(a) != spec_sha256(b)


def test_defaults_match_unity_scene_params_source():
    """표의 기본값을 Unity SceneParams.cs SceneDefaults 원문에서 다시 읽어 대조(읽기만). 교차 테스트의 파이썬 쪽."""
    import re
    src = shared("..", "unity", "Assets", "IFS", "Runtime", "SceneSpec", "SceneParams.cs").read_text(encoding="utf-8")
    pairs = {"colorH": "material.color.h", "colorS": "material.color.s", "colorL": "material.color.l",
             "brightness": "material.brightness", "roughness": "material.roughness", "opacity": "material.opacity",
             "erosion": "material.erosion", "size": "layout.size", "distance": "layout.distance",
             "verticalOffset": "layout.verticalOffset", "motionSpeed": "motion.speed"}
    for cs, key in pairs.items():
        m = re.search(rf"public float {cs} = ([0-9.]+)f;", src)
        assert m and float(m.group(1)) == DEFAULTS[key], key
    assert re.search(r'public string formType = "blob";', src) and DEFAULTS["form.type"] == "blob"
    assert re.search(r'public string motionType = "still";', src) and DEFAULTS["motion.type"] == "still"
