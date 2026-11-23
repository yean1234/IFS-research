"""후보 생성기(candidates.py, D3·결정 G14–G20, G31·G32·G34) — 결정성, 말한 슬롯 불변, 2×2 구성과 우선순위, 한 차원·빈 자리 없음,
갈림, 순서 순환, 모형 없는 모양어(G32), 밝기 제외·구별 규칙·선택 건너뜀(G34). 모든 문장은 합성 대사다."""
import copy
import hashlib
import itertools
import json

import pytest

from ifs_chatbot.candidates import (GENERATOR_VERSION, SLOTS, candidates_bytes, effective_params, generate,
                                    load_table, slot_is_open, spec_sha256, unrendered_shape_words)
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
T_SHAPE = "목에 네모난 게 걸려 있어요."            # 모형이 있는 모양어(square → Cube)
T_LONG = "가슴 안쪽에 길쭉한 게 있어요."            # 모형이 없는 모양어(elongated)
T_MIXED = "가슴에 길쭉하고 둥근 게 있어요."          # 모형 없음(길쭉) + 모형 있음(둥근 → Sphere)
T_MOTION = "까만 덩어리가 눈앞 가까이 있어요. 크고 무겁고 매끈해요. 불투명해요. 어두워요."   # 빈 자리 = 움직임 하나


@pytest.fixture(scope="module")
def v2():
    return SceneSpecBuilderV2(Analyzer())


@pytest.fixture(scope="module")
def specs(v2):
    return {t: v2.build(t, session_id="SYN-GOLD") for t in (T_FORM, T_FEEL, T_ALL, T_ONE, T_CLOUD, T_SHAPE, T_LONG, T_MIXED,
                                                              T_MOTION)}


def empty_spec():
    """모든 슬롯이 빈 최소 spec(합성)."""
    return {"meta": {"specVersion": "2.1.0", "sessionId": "X", "pipeline": {"builder": "test"}},
            "form": {"type": None, "posture": None},
            "material": {"color": None, "brightness": None, "saturation": None, "roughness": None, "opacity": None, "erosion": None},
            "layout": {"size": None, "distance": None, "verticalOffset": None},
            "motion": {"type": None, "speed": None}, "body": {"part": None, "layer": None},
            "_provenance": {}, "_unmapped": []}


# ── 결정성(완료 기준) ─────────────────────────────────────────────────────────
GOLDEN = {   # 생성기 0.3.0 · 표 2.0.0 · 매퍼 v2 builder 2.2.0 · 기본 형상 사전 0.2.0 (2026-11-23, D6)
    T_FORM: "e7f9d79f3d1745d479549c1fec7c8f6b712c5ab57f613038f5426bb8f83bcc4e",
    T_FEEL: "1460beb13b0577efdd1c1156cf1d9611caa1e649a53e0503cd63b59221aad22f",
    T_CLOUD: "da2171ea36efe9c43b1bc9c1cf2a7b3d5dbf71f4fc2433bad9c3820eb0787e1a",
    T_LONG: "58ff4c3ebacf3f045413aa83b32d6148bbcf87be2df6fd55c86a7f29fd3ad94f",
    T_MOTION: "5144da5f0a80fc2065b89c08b5b997d71b4819aa9adaacc5757a460cb8ddb2e3",
}


# 결정성은 두 가지로 나눠 고정한다(G28, CP9 지적 3).
#  (a) 같은 확정 텍스트 → 같은 spec(정규화 해시) · 같은 후보 id · 같은 덮어쓰기. 세션 ID가 달라도 성립한다.
#  (b) 표시 순서는 같은 spec과 같은 세션 ID에서 같다(G20). 세션 ID가 다르면 순서는 달라질 수 있다.
# 출력 전체 바이트(candidates_bytes)에는 sessionId와 표시 순서가 들어 있으므로 세션 ID를 고정했을 때만 같다.
@pytest.mark.parametrize("text", list(GOLDEN))
def test_output_sha256_is_pinned(v2, text):
    """같은 확정 텍스트 + 같은 세션 ID(SYN-GOLD) → 같은 후보 바이트(sha256 고정). 표·생성기·매퍼를 바꾸면 이 값이 바뀐다."""
    spec = v2.build(text, session_id="SYN-GOLD")
    assert hashlib.sha256(candidates_bytes(generate(spec, "SYN-GOLD"))).hexdigest() == GOLDEN[text]


@pytest.mark.parametrize("text", [T_FORM, T_FEEL, T_CLOUD, T_ALL])
def test_same_text_twice_same_spec_and_candidates(v2, text):
    a, b = v2.build(text, session_id="SYN-A"), v2.build(text, session_id="SYN-A")
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)
    assert candidates_bytes(generate(a, "SYN-A")) == candidates_bytes(generate(b, "SYN-A"))


@pytest.mark.parametrize("text", [T_FORM, T_FEEL, T_ALL, T_ONE, T_CLOUD, T_SHAPE, T_LONG, T_MOTION])
def test_g28a_same_text_gives_same_spec_ids_and_overrides_across_sessions(v2, text):
    """(a) 세션 ID가 달라도 spec(세션을 가리키는 meta를 뺀 것)·후보 id·덮어쓰기·축 값이 같다."""
    sids = ["SYN-A", "SYN-B", "SYN-C", "P07"]
    specs = [v2.build(text, session_id=sid) for sid in sids]
    assert len({spec_sha256(sp) for sp in specs}) == 1
    outs = [generate(sp, sid) for sp, sid in zip(specs, sids)]
    content = [[(c["id"], c["index"], c["overrides"], c["axisValues"], c["sources"]) for c in o["candidates"]] for o in outs]
    assert all(x == content[0] for x in content)
    assert all(o["axes"] == outs[0]["axes"] for o in outs)
    assert all(o["distinct"] == outs[0]["distinct"] and o["selectionStep"] == outs[0]["selectionStep"] for o in outs)
    assert all(sorted(o["displayOrder"]) == sorted(outs[0]["displayOrder"]) for o in outs)


def test_g28b_display_order_is_fixed_only_by_spec_and_session_id(v2):
    """(b) 같은 spec + 같은 세션 ID → 같은 표시 순서(몇 번을 불러도). 세션 ID가 다르면 순서가 달라질 수 있다."""
    spec = v2.build(T_FEEL, session_id="SYN-A")
    first = generate(spec, "SYN-A")
    for _ in range(3):
        again = generate(copy.deepcopy(spec), "SYN-A")
        assert again["displayOrder"] == first["displayOrder"]
        assert candidates_bytes(again) == candidates_bytes(first)
    orders = {tuple(generate(spec, f"SYN-{i:03d}")["displayOrder"]) for i in range(20)}
    assert len(orders) > 1, "세션 ID가 다르면 순서가 달라질 수 있어야 함(G20 순환)"
    assert {tuple(sorted(o)) for o in orders} == {tuple(sorted(first["displayOrder"]))}, "순서만 다르고 후보는 같다"


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
@pytest.mark.parametrize("text", [T_FORM, T_FEEL, T_ALL, T_ONE, T_CLOUD, T_SHAPE, T_LONG, T_MIXED, T_MOTION])
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
    """빈 spec에 다섯 차원 슬롯과 밝기를 하나씩 채운 모든 조합(64가지)에서 말한 슬롯은 덮어쓰기에 없고, 밝기는 어디서도 벌리지 않으며,
    후보 수는 구별 규칙(G34)을 적용한 값이다: 움직임 축은 정지 미리보기에서 구별되지 않아 접힌다."""
    fills = {"form.type": "shell", "layout.size": 0.6, "material.opacity": 0.8, "material.brightness": 0.3,
             "material.roughness": 0.7, "motion.type": "sinking"}
    keys = list(fills)
    dims = TABLE["candidateAxes"]["dimensions"]
    prio = TABLE["candidateAxes"]["priority"]
    for mask in itertools.product([0, 1], repeat=len(keys)):
        spec = empty_spec()
        said = [k for k, m in zip(keys, mask) if m]
        for k in said:
            g, n = k.split(".")
            spec[g][n] = fills[k]
        out = generate(spec, "S")
        for c in out["candidates"]:
            assert not (set(c["overrides"]) & set(said)), (said, c["overrides"])
            assert "material.brightness" not in c["overrides"]
        open_dims = [d for d in prio if dims[d]["slot"] not in said]
        top = open_dims[:2]
        if len(top) == 2:
            expect = 2 if "motion" in top else 4
        elif len(top) == 1:
            expect = 1 if top[0] == "motion" else len(dims[top[0]]["levels"])
        else:
            expect = 1
        assert len(out["candidates"]) == expect, (said, out["note"])
        assert out["selectionStep"] == ("skip" if expect == 1 else "choose")
        assert out["distinct"]["gridCount"] - len(out["distinct"]["removed"]) == expect


@pytest.mark.parametrize("text", [T_SHAPE, T_MIXED])
def test_rendered_shape_word_counts_as_said_form(specs, text):
    """모형이 있는 모양어('네모난' → Cube, '둥근' → Sphere)를 말했으면 form.type이 비어 있어도 형태는 벌리지 않는다(G32: 지금처럼 말한
    자리로 고정). 모형이 없는 모양어가 함께 있어도 같다(Unity가 모형을 그리므로)."""
    spec = specs[text]
    assert spec["form"]["type"] is None and any(u["category"] == "shape" for u in spec["_unmapped"])
    assert not slot_is_open(spec, "form.type")
    out = generate(spec, "S")
    assert "form.type" not in [a["slot"] for a in out["axes"]]
    assert all("form.type" not in c["overrides"] for c in out["candidates"])
    assert all(c["sources"]["form.type"] == "said" for c in out["candidates"])


# ── 모형이 없는 모양어(G32, G29 대체) ──────────────────────────────────────────
def test_unrendered_shape_word_opens_form_candidates(specs):
    """모형이 없는 모양어('길쭉')만 말했으면 형태 자리를 벌린다: 첫 축이 form.type(reason said_unrendered), 말한 낱말이 축에 남는다."""
    spec = specs[T_LONG]
    assert [u["lemma"] for u in unrendered_shape_words(spec)] == ["길쭉"]
    assert slot_is_open(spec, "form.type")
    out = generate(spec, "S")
    ax = out["axes"][0]
    assert ax["slot"] == "form.type" and ax["reason"] == "said_unrendered" and ax["values"] == ["blob", "mist"]
    assert [w["lemma"] for w in ax["saidWords"]] == ["길쭉"] and ax["saidWords"][0]["shape"] == "elongated"
    assert out["selectionStep"] == "choose" and len(out["candidates"]) == 4
    assert {c["axisValues"]["form.type"] for c in out["candidates"]} == {"blob", "mist"}
    assert "G32" in out["note"]


def test_shape_models_match_unity_shape_mapping():
    """표 shapeModels(모형이 있는 모양 값)가 Unity ShapeMapping.ModelByShape 원문과 같다(읽기만 하는 교차 테스트)."""
    import re
    src = shared("..", "unity", "Assets", "IFS", "Runtime", "SceneSpec", "ShapeMapping.cs").read_text(encoding="utf-8")
    block = re.search(r"ModelByShape\s*=\s*new Dictionary<string, string>\([^)]*\)\s*\{(.*?)\};", src, re.S).group(1)
    pairs = dict(re.findall(r'\{\s*"([a-z]+)",\s*Model(\w+)\s*\}', block))
    assert pairs == TABLE["shapeModels"]["models"]
    assert set(TABLE["shapeModels"]["mapped"]) == set(pairs)


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


def test_priority_order_follows_g34():
    """G34: 우선순위는 형태 > 크기 > 투명도 > 질감 > 움직임(밝기 없음)."""
    assert TABLE["candidateAxes"]["priority"] == ["form", "size", "opacity", "texture", "motion"]
    spec = empty_spec()
    spec["form"]["type"] = "blob"
    spec["layout"]["size"] = 0.4
    out = generate(spec, "S")
    assert [a["slot"] for a in out["axes"]] == ["material.opacity", "material.roughness"]


def test_form_said_uses_next_two_dimensions(specs):
    out = generate(specs[T_FORM], "S")
    assert [a["slot"] for a in out["axes"]] == ["material.opacity", "material.roughness"]
    assert len(out["candidates"]) == 4


def test_hue_and_brightness_never_spread_g17_g34():
    """색상(G17·G31)과 밝기(G34)는 후보에서 벌리지 않는다. 밝기만 빈 자리여도 후보 차원이 되지 않는다."""
    for spec in (empty_spec(),):
        for c in generate(spec, "S")["candidates"]:
            assert not any(k.startswith("material.color") or k == "material.brightness" for k in c["overrides"])
    assert "color" not in TABLE["candidateAxes"]["priority"] and "brightness" not in TABLE["candidateAxes"]["priority"]
    assert "brightness" not in TABLE["candidateAxes"]["dimensions"]
    only_brightness = empty_spec()
    for slot, v in (("form.type", "blob"), ("layout.size", 0.5), ("material.opacity", 1.0), ("material.roughness", 0.5),
                    ("motion.type", "still")):
        g, n = slot.split(".")
        only_brightness[g][n] = v
    out = generate(only_brightness, "S")
    assert out["axes"] == [] and len(out["candidates"]) == 1 and out["selectionStep"] == "skip"


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
@pytest.mark.parametrize("text", [T_ALL, T_ONE])
def test_no_empty_slot_gives_single_candidate_and_skips_selection(specs, text):
    """빈 자리가 없으면 후보 1개 → 선택 단계를 건너뛴다(G34가 G19의 '1개만 보여 주고 묻기'를 대체). T_ONE은 밝기만 비었던 문장."""
    out = generate(specs[text], "S")
    assert len(out["candidates"]) == 1 and out["axes"] == [] and out["candidates"][0]["overrides"] == {}
    assert out["displayOrder"] == [out["candidates"][0]["id"]] and out["selectionStep"] == "skip"


def test_single_open_dimension_uses_table_levels():
    spec = empty_spec()
    for slot, v in (("form.type", "blob"), ("material.opacity", 1.0), ("material.roughness", 0.5), ("motion.type", "still")):
        g, n = slot.split(".")
        spec[g][n] = v
    out = generate(spec, "S")
    assert [a["slot"] for a in out["axes"]] == ["layout.size"]
    assert [c["axisValues"]["layout.size"] for c in out["candidates"]] == TABLE["candidateAxes"]["dimensions"]["size"]["levels"]


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


# ── 구별되지 않는 후보(G34) ─────────────────────────────────────────────────────
def test_motion_only_open_collapses_to_one_and_skips(specs):
    """빈 자리가 움직임뿐이면 표 값 4개를 만들지만, 후보 미리보기는 움직임을 멈춘 정지 그림이라 넷이 같은 그림 → 0번만 남고 건너뜀."""
    out = generate(specs[T_MOTION], "S")
    assert [a["slot"] for a in out["axes"]] == ["motion.type"]
    assert out["distinct"]["gridCount"] == 4 and len(out["candidates"]) == 1 and out["candidates"][0]["index"] == 0
    assert [(r["index"], r["sameAs"], r["rules"]) for r in out["distinct"]["removed"]] == \
        [(1, 0, ["still_preview_motion"]), (2, 0, ["still_preview_motion"]), (3, 0, ["still_preview_motion"])]
    assert out["distinct"]["collapsedAxes"] == ["motion.type"] and out["selectionStep"] == "skip"
    assert out["distinct"]["ruleVersion"] == TABLE["distinctness"]["ruleVersion"]


def test_texture_by_motion_keeps_only_texture_pair():
    """질감 × 움직임 2×2 → 움직임만 다른 후보가 접혀 2개(0번·2번)가 남고 선택 단계는 그대로."""
    spec = empty_spec()
    for slot, v in (("form.type", "blob"), ("layout.size", 0.5), ("material.opacity", 1.0)):
        g, n = slot.split(".")
        spec[g][n] = v
    out = generate(spec, "S")
    assert [a["slot"] for a in out["axes"]] == ["material.roughness", "motion.type"]
    assert [c["index"] for c in out["candidates"]] == [0, 2] and out["selectionStep"] == "choose"
    assert {c["axisValues"]["material.roughness"] for c in out["candidates"]} == {0.5, 0.1}
    assert out["distinct"]["collapsedAxes"] == ["motion.type"]
    assert sorted(out["displayOrder"]) == sorted(c["id"] for c in out["candidates"])


def test_equal_final_values_are_removed_by_rule():
    """덮어쓰기를 얹은 최종 값이 같은 후보는 하나만 남는다(same_final_values). 표 값이 겹치도록 고친 표로 확인(합성)."""
    import copy as _copy
    t = _copy.deepcopy(TABLE)
    t["candidateAxes"]["dimensions"]["size"]["pair"] = [0.5, 0.5]
    out = generate(empty_spec(), "S", t)
    assert [c["index"] for c in out["candidates"]] == [0, 2]
    assert {r["index"]: r["rules"] for r in out["distinct"]["removed"]} == {1: ["same_final_values"], 3: ["same_final_values"]}


def test_distinct_rules_are_code_confirmed_and_versioned():
    """표에는 코드로 확인한 규칙만(status confirmed_code), 확인 못 한 조합은 unverified에만. 움직임 규칙의 근거 코드가 그대로 있는지
    다시 본다(미리보기 플레이어가 그리기 전에 움직임을 멈추지 않게 바뀌면 이 규칙도 바뀌어야 한다)."""
    d = TABLE["distinctness"]
    assert d["ruleVersion"].startswith("ifs-distinct/") and d["status"] == "draft"
    assert {r["id"] for r in d["rules"]} == {"same_final_values", "still_preview_motion"}
    assert all(r["status"] == "confirmed_code" and r["evidence"] for r in d["rules"])
    assert d["unverified"] and all(u["combo"] and u["why"] for u in d["unverified"])
    queue = shared("..", "unity", "Assets", "IFS", "Runtime", "Preview", "PreviewQueue.cs").read_text(encoding="utf-8")
    stage = shared("..", "unity", "Assets", "IFS", "Runtime", "Preview", "PreviewStage.cs").read_text(encoding="utf-8")
    assert queue.index("stage.Load(") < queue.index("stage.FreezeMotion();") < queue.index("stage.RenderPng(")
    assert "m.enabled = false;" in stage and "m.transform.localRotation = Quaternion.identity;" in stage
    plan = shared("..", "unity", "Assets", "IFS", "Runtime", "Rendering", "FormRenderPlan.cs").read_text(encoding="utf-8")
    assert "motion" not in plan.split("public static FormRenderPlan Build", 1)[1].split("public static string RendererFor", 1)[0]


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
