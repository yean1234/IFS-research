"""G62-i: 형태 후보의 기본값 규칙([gen3d] default_form_source = "auto").
말한 형태 낱말이 모두 단순 도형(shared/lexicon/primitive_forms.v0.json)이고 절차 메시가 그 문장에서 그대로 그리면 절차 메시가 기본,
그 밖의 사물 낱말이 하나라도 있으면 생성 메시가 기본. 형태를 말하지 않았으면 생성 후보가 없어 지금처럼 절차 메시만.
판정은 사전·규칙만(같은 입력 → 같은 판정). 모든 대사는 합성이다. 생성 모델을 부르지 않는다."""
import json

import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.candidates import generate
from ifs_chatbot.form_assets import (PRIMITIVE_FORMS_FILE, SHAPE_MODEL_VALUES, judge_default_form, load_primitive_forms,
                                     procedural_draws)
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2

from test_g62_gen3d import ASSET_ID, T_FEEL, V03, cfg, done_session, key_of, run_flow, strip_times, valid, write_asset

PRIM = load_primitive_forms()

# 사전 형태 낱말(lexiconKey)·slot. 합성 문장의 글자 위치는 확정 텍스트에서 찾는다(사이드카 tokens와 같은 꼴)
WORDS = {"공": ("공", "shape_noun", "ball"), "동그란": ("동그랗", "shape_modifier", "round"),
         "둥근": ("둥글", "shape_modifier", "round"), "네모난": ("네모나", "shape_modifier", "square"),
         "상자": ("상자", "shape_noun", "box"), "조개껍데기": ("조개껍데기", "shape_noun", "seashell"),
         "바위": ("바위", "shape_noun", "boulder"), "천": ("천", "shape_noun", "cloth"),
         "나뭇잎": ("나뭇잎", "shape_noun", "leaf"), "원뿔": ("원뿔", "shape_noun", "cone")}


def toks(text: str, *surfaces, like: str | None = None) -> list:
    """확정 텍스트(정규화)에서 낱말 위치를 찾아 사이드카 prompt.tokens 꼴로(틀 낱말 포함). like = 비유 원천 낱말('…-like')."""
    norm = normalize_confirmed(text)
    out = [{"en": "a single", "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None}]
    pos = 0
    for s in surfaces:
        i = norm.index(s, pos)
        key, slot, en = WORDS[s] if s != like else ("조개+껍데기", "shape_noun", "seashell-like")
        out.append({"en": en, "ko": s, "charSpan": [i, i + len(s)], "slot": slot, "lexiconKey": key})
        pos = i + len(s)
    out.append({"en": "plain background", "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None})
    return out


def auto_flow(tmp_path, sid, text, surfaces=(), like=None, seed_kind="ok", choose=None, bad_span=False):
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="auto"))
    seen = {}

    def seed(s):
        if seed_kind == "none":
            return
        if seed_kind == "blocked":                       # 형태를 말하지 않음 → 생성 도구가 막은 사이드카만 있음
            write_asset(assets, key_of(s), "P-blocked", status="blocked", block_reason="no_shape_stated", tokens=[])
            return
        t = toks(text, *surfaces, like=like)
        if bad_span:
            t[1]["charSpan"] = [t[1]["charSpan"][0] + 1, t[1]["charSpan"][1] + 1]
        write_asset(assets, key_of(s), "P-ok-0", seed=0, tokens=t)
        write_asset(assets, key_of(s), "P-ok-1", seed=1, tokens=t)

    def pick(v):
        seen["v"] = v
        return choose(v) if choose else v["candidates"][0]["id"]

    s, f = run_flow(rt, sid, text, before_start=seed, choose=pick)
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    valid(data, V03)
    return rt, s, f, data, seen.get("v")


# ── 목록 파일 ───────────────────────────────────────────────────────────────
def test_primitive_list_is_versioned_and_keyed_to_shape_lexicon():
    raw = json.loads(shared("lexicon", PRIMITIVE_FORMS_FILE).read_text(encoding="utf-8"))
    shape_lex = json.loads(shared("lexicon", raw["keyedTo"]["lexicon"]).read_text(encoding="utf-8"))
    assert PRIM["version"] == raw["lexiconVersion"] and len(PRIM["sha256"]) == 64
    assert raw["keyedTo"]["lexiconVersion"] == shape_lex["lexiconVersion"]
    keys = {"+".join(e["ko"]) for e in shape_lex["entries"]}
    assert set(PRIM["entries"]) <= keys                  # 형태 사전에 있는 낱말만(사이드카 lexiconKey와 같은 키)
    assert all(e["procedural"]["value"] in SHAPE_MODEL_VALUES for e in PRIM["entries"].values()
               if e["procedural"]["check"] == "shape")
    # 사물(조개껍데기·바위·천·나뭇잎)은 단순 도형이 아니다
    assert not {"조개껍데기", "조개+껍데기", "바위", "천", "나뭇잎"} & set(PRIM["entries"])


# 합성 문장 하나로 각 항목의 절차 사전 결과가 목록에 적힌 것과 같은지(목록이 절차 사전과 어긋나지 않게)
PROBES = {"공": ("공이 있어요.", "공"), "볼링+공": ("볼링공이 있어요.", "볼링공"), "상자": ("상자가 있어요.", "상자"),
          "네모": ("네모가 있어요.", "네모"), "동그랗": ("동그란 게 있어요.", "동그란"), "둥글": ("둥근 게 있어요.", "둥근"),
          "네모나": ("네모난 게 있어요.", "네모난"), "납작": ("납작한 게 있어요.", "납작"), "뾰족": ("뾰족한 게 있어요.", "뾰족")}


@pytest.fixture(scope="module")
def v2():
    an = Analyzer()
    if not an.available:
        pytest.skip("kiwipiepy 없음")
    return SceneSpecBuilderV2(an)


def test_every_listed_word_is_drawn_by_procedural_dictionary(v2):
    assert set(PROBES) == set(PRIM["entries"])
    for key, (text, surface) in PROBES.items():
        spec = v2.build(text)
        i = text.index(surface)
        assert procedural_draws(spec, PRIM["entries"][key]["procedural"], [i, i + len(surface)]), key


@pytest.mark.parametrize("text,surface", [("원뿔이 있어요.", "원뿔"), ("큐브가 있어요.", "큐브"), ("구슬이 있어요.", "구슬")])
def test_geometric_words_the_procedural_dictionary_does_not_draw_are_not_listed(v2, text, surface):
    """원뿔·큐브·구슬은 기하 도형이지만 절차 사전이 형상으로 옮기지 않는다(기본 덩어리를 그림) → 목록에 없음 → 생성 기본."""
    spec = v2.build(text)
    assert spec["form"]["type"] is None and spec["form"]["base"] is None and not any(
        u.get("category") == "shape" for u in spec.get("_unmapped") or [])
    assert surface not in PRIM["entries"]


# ── 판정 함수(사전·규칙만, 결정적) ──────────────────────────────────────────
def _judge(v2, text, *surfaces, like=None, offered=True):
    spec = v2.build(text)
    norm = normalize_confirmed(text)
    a = {"assetId": "a0", "_formWords": [t for t in toks(text, *surfaces, like=like) if t["slot"] != "template"]}
    return judge_default_form([a] if offered else [], spec, norm, PRIM)


def test_judge_rules_and_determinism(v2):
    b = _judge(v2, "동그란 공이 있어요.", "동그란", "공")
    assert (b["rule"], b["source"]) == ("primitive_stated", "procedural")
    assert [(w["ko"], w["charSpan"], w["primitive"], w["reason"]) for w in b["words"]] == \
        [("동그란", [0, 3], True, "listed_and_drawn"), ("공", [4, 5], True, "listed_and_drawn")]
    assert b == _judge(v2, "동그란 공이 있어요.", "동그란", "공")      # 같은 입력 → 같은 판정
    assert _judge(v2, "네모난 상자가 있어요.", "네모난", "상자")["rule"] == "primitive_stated"
    for text, words in (("조개껍데기가 있어요.", ("조개껍데기",)), ("바위가 있어요.", ("바위",)),
                        ("천이 있어요.", ("천",)), ("나뭇잎이 있어요.", ("나뭇잎",)), ("원뿔이 있어요.", ("원뿔",))):
        b = _judge(v2, text, *words)
        assert (b["rule"], b["source"]) == ("non_primitive_stated", "generated"), text
        assert b["words"][0]["reason"] == "not_listed"
    assert _judge(v2, "동그란 공이 있어요.", "동그란", "공", offered=False)["rule"] == "no_generated_candidate"


def test_judge_mixed_primitive_and_object_words_default_to_generated(v2):
    """섞인 경우: 단순 도형 낱말이 있어도 사물 낱말이 하나라도 있으면 생성 메시가 기본(절차 메시는 사물 낱말을 그리지 못함)."""
    b = _judge(v2, "동그란 조개껍데기가 있어요.", "동그란", "조개껍데기")
    assert (b["rule"], b["source"]) == ("non_primitive_stated", "generated")
    assert [(w["ko"], w["primitive"]) for w in b["words"]] == [("동그란", True), ("조개껍데기", False)]
    b = _judge(v2, "조개껍데기 같은 공이 있어요.", "조개껍데기", "공", like="조개껍데기")      # 비유 원천도 말한 형태 낱말
    assert b["rule"] == "non_primitive_stated" and [w["primitive"] for w in b["words"]] == [False, True]
    # 목록에 있어도 절차 메시가 그 문장에서 그리지 않으면 단순 도형으로 세지 않는다('동그란 상자'는 네모 단면 상자로 그려짐)
    b = _judge(v2, "동그란 상자가 있어요.", "동그란", "상자")
    assert b["rule"] == "non_primitive_stated"
    assert [(w["ko"], w["reason"]) for w in b["words"]] == [("동그란", "procedural_not_drawn"), ("상자", "listed_and_drawn")]


def test_judge_fails_closed_when_words_do_not_trace_to_text(v2):
    spec = v2.build("공이 있어요.")
    a = {"assetId": "a0", "_formWords": [{"en": "ball", "ko": "공", "charSpan": [1, 2], "slot": "shape_noun", "lexiconKey": "공"}]}
    b = judge_default_form([a], spec, normalize_confirmed("공이 있어요."), PRIM)
    assert (b["rule"], b["source"]) == ("form_words_untraceable", "procedural") and b["words"][0]["charSpan"] is None
    ok = {"assetId": "a0", "_formWords": [{"en": "ball", "ko": "공", "charSpan": [0, 1], "slot": "shape_noun", "lexiconKey": "공"}]}
    assert judge_default_form([ok], spec, None, PRIM)["rule"] == "form_words_untraceable"            # 확정 텍스트 없음
    assert judge_default_form([ok], spec, "다른 글", PRIM)["rule"] == "form_words_untraceable"        # 해시가 다름
    assert judge_default_form([{"assetId": "a0", "_formWords": []}], spec, normalize_confirmed("공이 있어요."),
                              PRIM)["rule"] == "no_form_words"


# ── 세션 흐름(Runtime + 합성 사이드카) ───────────────────────────────────────
def test_auto_primitive_sentence_makes_procedural_default(tmp_path):
    text = "동그란 공이 눈앞에 있어요."
    rt, s, f, data, v = auto_flow(tmp_path, "SYN-G62I-PRIM", text, ("동그란", "공"))
    gen = data["generation"]
    assert gen["defaultFormSourceSetting"] == "auto" and gen["defaultFormRule"] == "primitive_stated"
    assert data["defaultFormSource"] == "procedural" and gen["defaultCandidateId"] is None
    assert v["defaultCandidateId"] is None and not any(c["default"] for c in v["candidates"])
    # 생성 메시는 대안으로 남는다(고를 수 있음), 절차 후보 순서 규칙은 procedural 설정과 같다(순환·미리 선택 없음)
    assert sum(1 for c in v["candidates"] if c["generated"]) == 2
    from ifs_chatbot.candidates import _display_offset
    n = len(f.cands["candidates"])
    assert f.cands["displayOrder"] == [f.cands["candidates"][(k + _display_offset(s.id, n)) % n]["id"] for k in range(n)]
    basis = gen["defaultFormBasis"]
    norm = normalize_confirmed(text)
    assert [(w["ko"], w["charSpan"], w["lexiconKey"]) for w in basis["words"]] == \
        [("동그란", [0, 3], "동그랗"), ("공", [4, 5], "공")]
    assert all(norm[w["charSpan"][0]:w["charSpan"][1]] == w["ko"] for w in basis["words"])
    assert basis["listVersion"] == PRIM["version"] and basis["listSha256"] == PRIM["sha256"]
    assert basis["assetIds"] == [ASSET_ID("P-ok-0"), ASSET_ID("P-ok-1")]
    assert data["selection"]["acceptedDefault"] is None
    assert f.cands["generation"]["defaultFormRule"] == "primitive_stated"          # candidates.json에도 같은 근거
    assert rt.info()["gen3d"]["primitiveForms"]["version"] == PRIM["version"]


@pytest.mark.parametrize("text,surfaces", [("조개껍데기가 손바닥 위에 있어요.", ("조개껍데기",)),
                                           ("바위가 앞에 있어요.", ("바위",)), ("나뭇잎이 떠 있어요.", ("나뭇잎",))])
def test_auto_object_sentence_makes_generated_default(tmp_path, text, surfaces):
    rt, s, f, data, v = auto_flow(tmp_path, "SYN-G62I-OBJ", text, surfaces, choose=lambda v: v["defaultCandidateId"])
    gen = data["generation"]
    assert gen["defaultFormRule"] == "non_primitive_stated" and data["defaultFormSource"] == "generated"
    first = v["candidates"][0]
    assert first["generated"] and first["default"] and first["asset"]["assetId"] == ASSET_ID("P-ok-0")
    assert sum(1 for c in v["candidates"] if not c["generated"]) >= 1        # 절차 메시는 대안으로 남음
    assert data["selection"]["acceptedDefault"] is True and data["sources"]["form.type"] == "generated_chosen"
    assert gen["defaultFormBasis"]["words"][0]["reason"] == "not_listed"


def test_auto_mixed_sentence_makes_generated_default(tmp_path):
    rt, s, f, data, v = auto_flow(tmp_path, "SYN-G62I-MIX", "동그란 조개껍데기가 있어요.", ("동그란", "조개껍데기"))
    gen = data["generation"]
    assert gen["defaultFormRule"] == "non_primitive_stated" and data["defaultFormSource"] == "generated"
    assert [(w["ko"], w["primitive"]) for w in gen["defaultFormBasis"]["words"]] == [("동그란", True), ("조개껍데기", False)]
    assert v["candidates"][0]["generated"] and v["candidates"][0]["default"]


@pytest.mark.parametrize("seed_kind", ["none", "blocked"])
def test_auto_form_not_stated_has_no_generation(tmp_path, seed_kind):
    """형태를 말하지 않음 → 생성 도구가 만들지 않음(사이드카 없음 또는 no_shape_stated로 막힘) → 절차 후보만, 지금과 같다."""
    rt, s, f, data, v = auto_flow(tmp_path, "SYN-G62I-NONE-" + seed_kind, T_FEEL, seed_kind=seed_kind)
    proc = generate(s.scene_spec, s.id, rt.candidate_table)
    assert [c["id"] for c in f.cands["candidates"]] == [c["id"] for c in proc["candidates"]]
    assert f.cands["displayOrder"] == proc["displayOrder"]
    gen = data["generation"]
    assert gen["offered"] == [] and gen["defaultFormRule"] == "no_generated_candidate"
    assert data["defaultFormSource"] == "procedural" and gen["defaultFallbackReason"] is None
    assert gen["defaultFormBasis"]["words"] == []
    assert [r["reason"] for r in gen["rejected"]] == ([] if seed_kind == "none" else ["blocked"])


def test_auto_untraceable_words_fall_back_to_procedural(tmp_path):
    rt, s, f, data, v = auto_flow(tmp_path, "SYN-G62I-UNTR", "조개껍데기가 있어요.", ("조개껍데기",), bad_span=True)
    gen = data["generation"]
    assert gen["defaultFormRule"] == "form_words_untraceable" and data["defaultFormSource"] == "procedural"
    assert len(gen["offered"]) == 2 and gen["defaultCandidateId"] is None     # 생성 후보는 남지만 기본이 아님


def test_auto_default_dropped_by_preview_keeps_rule_and_records_fallback(tmp_path):
    """생성 기본 후보를 미리보기가 그리지 못해 모두 빠지면 절차가 기본이 되고 사유가 남는다(판정 규칙 기록은 그대로)."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default="auto"))
    text = "조개껍데기가 있어요."
    s = done_session(rt, "SYN-G62I-DROP", text)
    write_asset(assets, key_of(s), "P-ok-0", tokens=toks(text, "조개껍데기"))
    f = s.selection()
    v = f.start()
    gid = v["defaultCandidateId"]
    assert gid and f.cands["generation"]["defaultFormRule"] == "non_primitive_stated"
    f.client_preview("asset_failed", "webgl", "selecting", "synthetic", {"candidateId": gid})
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    assert data["defaultFormSource"] == "procedural" and data["generation"]["defaultFallbackReason"] == "preview_failed"
    assert data["generation"]["defaultFormRule"] == "non_primitive_stated"


# ── 고정 설정·꺼짐 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("setting,rule", [("generated", "setting_generated"), ("procedural", "setting_procedural")])
def test_fixed_settings_still_work_and_record_rule(tmp_path, setting, rule):
    """기존 값은 그대로 동작한다: 단순 도형 문장이어도 generated면 생성 기본, procedural이면 미리 선택 없음."""
    assets = tmp_path / "assets"
    rt = Runtime(cfg(tmp_path, True, assets, default=setting))
    assert rt.form_assets.primitive_forms is None and "primitiveForms" not in rt.info()["gen3d"]
    text = "동그란 공이 있어요."
    s, f = run_flow(rt, "SYN-G62I-FIX-" + setting, text,
                    before_start=lambda s: write_asset(assets, key_of(s), "P-ok-0", tokens=toks(text, "동그란", "공")))
    data = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    gen = data["generation"]
    assert gen["defaultFormRule"] == rule and gen["defaultFormBasis"] is None
    assert data["defaultFormSource"] == setting
    assert (gen["defaultCandidateId"] is not None) == (setting == "generated")
    valid(data, V03)


def test_flag_off_identical_with_auto_setting(tmp_path):
    """v4.toml(꺼짐): default_form_source가 auto여도 출력이 같고 0.2 그대로다(단순 도형 목록도 읽지 않음)."""
    assets = tmp_path / "assets"
    outs = []
    text = "동그란 공이 있어요."
    for name, d in (("p", None), ("a", "auto")):
        c = cfg(tmp_path / name, None if d is None else False, assets, default=d)
        rt = Runtime(c)
        assert rt.form_assets is None
        s, f = run_flow(rt, "SYN-G62I-OFF", text,
                        before_start=lambda s: write_asset(assets, key_of(s), "P-ok-0", tokens=toks(text, "동그란", "공")))
        outs.append(((f.dir / "candidates.json").read_bytes(),
                     strip_times(json.loads((f.dir / "selection.json").read_text(encoding="utf-8")))))
    assert outs[0] == outs[1] and outs[0][1]["formatVersion"] == "ifs-selection/0.2"
    assert "defaultFormSource" not in outs[0][1] and b"defaultFormRule" not in outs[0][0]
    assert load_config("v4").gen3d.enabled is False and load_config("v4-gen3d").gen3d.default_form_source == "auto"


def test_unity_runner_does_not_need_new_fields():
    """러너는 selection의 맨 위 defaultFormSource(문자열)와 selection.acceptedDefault만 읽는다. 새 필드(generation.defaultFormRule·
    defaultFormBasis, 설정값 auto)는 generation 안에만 있고 맨 위 defaultFormSource 값은 procedural | generated 그대로다."""
    src = (REPO_ROOT / "unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs").read_text(encoding="utf-8")
    assert '"generation"' not in src and "defaultFormRule" not in src and "defaultFormSourceSetting" not in src
    schema = json.loads(shared("schemas", "selection.v0.3.json").read_text(encoding="utf-8"))
    assert schema["properties"]["defaultFormSource"]["enum"][:2] == ["procedural", "generated"]
