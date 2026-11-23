"""기본 형상 경로(D6, 결정 G21·G22·G30, docs/asset-plan.md) — 스키마 2.2.0, 매퍼 v2 낱말 → form.base, 안전 제외 낱말,
v0·v1 출력 불변, 후보(기본 형상은 후보 값이 아님)·조절(형태 항목의 기본 형상)·출처, C#·스키마·사전 목록 대조.
모든 문장은 합성 대사다(AGENTS.md 6)."""
import hashlib
import json
import re

import pytest
from jsonschema import Draft202012Validator

from ifs_chatbot.candidates import base_drawn, generate, load_table, slot_is_open
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.paths import REPO_ROOT, shared
from ifs_chatbot.scene_builder import SceneSpecBuilder, dumps, normalize_confirmed
from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1
from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2
from ifs_chatbot.scene_spec import BASE_SHAPES, check_principles, schema, schema_errors

SCHEMA22 = schema("2.2.0")
LEX = json.loads(shared("lexicon", "base_shapes.v1.json").read_text(encoding="utf-8"))
TABLE = load_table()
CS = REPO_ROOT / "unity" / "Assets" / "IFS" / "Runtime"


@pytest.fixture(scope="module")
def an():
    return Analyzer()


@pytest.fixture(scope="module")
def v2(an):
    return SceneSpecBuilderV2(an)


def build(v2, text):
    spec = v2.build(text, session_id="SYN-BASE")
    assert check_principles(spec, normalize_confirmed(text)) == [], text
    return spec


# ── 목록 대조 ───────────────────────────────────────────────────────────────
def test_base_lists_match_schema_lexicon_and_csharp():
    enum = [v for v in SCHEMA22["properties"]["form"]["properties"]["base"]["enum"] if v is not None]
    assert enum == list(BASE_SHAPES) == list(LEX["bases"])
    src = (CS / "SceneSpec" / "BaseShapes.cs").read_text(encoding="utf-8")
    consts = dict(re.findall(r'public const string (\w+) = "([^"]+)";', src))
    order = re.search(r"All = \{([^}]*)\}", src).group(1)
    assert [consts[n.strip()] for n in order.split(",")] == enum
    # 스키마 변형값 ⊆ C# 변형값 표(C#은 정하지 않은 값의 기본값 'normal'을 더 가짐)
    var = SCHEMA22["$defs"]["baseVariant"]["properties"]
    for key, spec in var.items():
        assert f'"{key}"' in src
        for v in spec["enum"]:
            assert f'"{v}"' in src, (key, v)
    for b, info in LEX["bases"].items():
        assert set(info["variants"]) <= set(var)


def test_every_entry_points_at_an_approved_base_and_has_a_source():
    for e in LEX["entries"]:
        assert e["base"] in BASE_SHAPES, e
        assert re.match(r"^(lit|tr):.+|^added$", e["source"]), e
        for k, v in (e.get("variant") or {}).items():
            assert k in LEX["bases"][e["base"]]["variants"] and v in LEX["bases"][e["base"]]["variants"][k], e
    lemmas = [e["lemma"] for e in LEX["entries"]]
    assert len(lemmas) == len(set(lemmas))
    excluded = {w for k, ws in LEX["excluded"].items() if not k.startswith("_") and k != "notListed" for w in ws}
    assert not excluded & set(lemmas)
    assert "병" not in lemmas      # 동음이의(질병·화병) — 합성어만


def test_lexicon_only_lists_built_shapes():
    """메시가 없는 기본 형상으로 가는 낱말은 사전에 넣지 않는다(뺀 형상의 낱말은 _unmapped에 남음 — G30 자르는 규칙)."""
    src = (CS / "Rendering" / "BaseShapeMesh.cs").read_text(encoding="utf-8")
    built = set(re.findall(r'\{ BaseShapes\.(\w+), "(\w+)/\d+" \}', src))
    built = {v for _, v in built}
    assert {e["base"] for e in LEX["entries"]} <= built


# ── 스키마 2.2.0 ────────────────────────────────────────────────────────────
def test_schema_22_accepts_v2_output_and_rejects_bad_base(v2):
    spec = build(v2, "가슴 앞에 작은 화분이 있어요.")
    assert spec["meta"]["specVersion"] == "2.2.0" and schema_errors(spec) == []
    bad = json.loads(json.dumps(spec))
    bad["form"]["base"] = "tree"
    assert schema_errors(bad)
    nop = json.loads(json.dumps(spec))
    del nop["_provenance"]["form.base"]
    assert any("form.base" in e for e in schema_errors(nop))
    wrongvar = json.loads(json.dumps(spec))
    wrongvar["form"]["baseVariant"] = {"drape": "cloth"}
    assert schema_errors(wrongvar)
    missing = json.loads(json.dumps(spec))
    del missing["form"]["base"]
    assert schema_errors(missing)


def test_schema_22_keeps_20_and_21_documents_valid(an):
    v1 = SceneSpecBuilderV1(an)
    s = v1.build("가슴 앞에 작은 화분이 있어요.")
    assert s["meta"]["specVersion"] == "2.1.0" and schema_errors(s) == []
    assert "base" not in s["form"]
    assert not list(Draft202012Validator(SCHEMA22).iter_errors(s))     # 2.2 스키마도 2.1 문서를 받는다(상위 호환)


# ── v0·v1 출력 불변(D6) ─────────────────────────────────────────────────────
# 값은 D6 변경 전 HEAD(08473d9 + 스텁 수리 34ba7e2)의 깨끗한 작업 폴더에서 같은 코드로 잰 것(2026-11-23)
V0_V1_PINNED_D6 = {
    "가슴 앞에 작은 화분이 있어요. 초록색이에요.": ("74d26b285115fbdf58cb42ec4461857975cef2cffddb3f8ab13ddaa8d366be7e",
                                     "ca09913df9ef7c0641c264a015350357484b5f33b8818829acf01f76430c5f6c"),
    "가느다란 검은 실이 손가락에 칭칭 감겨 있어요. 엉켜 있어요.": ("73c99ac443b8a90ee9fd22b481067cd2e2bf0f50fe887e5c6eb4907aaa58bc05",
                                            "defe38b13436ad938273b1e70f4685136f2621794d027ff9ada710513762d963"),
    "종이 한 장이 눈앞에 떠 있어요. 얇은 천 같아요.": ("4a363b2872e445541a6219b935c75f1e896f226b10ca3141d1f27e3324fbf4d6",
                                       "af06b3ab4544bb4e3a220c7637b9db46d149deecb1a8393ca27c2f87f2b931db"),
    "촛불 불꽃처럼 생겼어요. 물방울 하나가 맺혀 있어요.": ("9a95ed45673295940b44165bc442bacbe8afd42235637181e5d270becdd77603",
                                         "139d504e141d1dbde7a6a56b1855bdf4364027263a4edcecfd47656dd0721fe0"),
    "작은 사람이 웅크리고 있어요. 칼 같은 게 있어요.": ("380788f0ffee5a6eed5774a467aa29024d0a6d583b24b2eed754ef59d94c1d9a",
                                      "ccc03ca3ac73c3c8b25a68afcf02f652fcc577dbedb6723aa72846bcb1d0a292"),
}


@pytest.mark.parametrize("text", list(V0_V1_PINNED_D6))
def test_v0_v1_outputs_unchanged_by_d6(an, text):
    v0 = SceneSpecBuilder(Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), an), an)
    v1 = SceneSpecBuilderV1(an)
    h0, h1 = V0_V1_PINNED_D6[text]
    a, b = dumps(v0.build(text, session_id="SYN-PIN")), dumps(v1.build(text, session_id="SYN-PIN"))
    assert hashlib.sha256(a.encode()).hexdigest() == h0
    assert hashlib.sha256(b.encode()).hexdigest() == h1
    assert '"base"' not in a and '"base"' not in b


# ── 낱말 → form.base ────────────────────────────────────────────────────────
WORDS = [
    # (문장, 기본 형상, 변형값)
    ("가슴 앞에 작은 화분이 있어요.", "container", {"opening": "wide"}),
    ("그릇이요.", "container", {"opening": "wide"}),
    ("배 안에 유리병이 있어요.", "container", {"opening": "narrow"}),
    ("까만 네모난 상자예요.", "container", {"opening": "wide", "profile": "square"}),
    ("네모난 그릇 같아요.", "container", {"opening": "wide", "profile": "square"}),    # 모양어 '네모'가 단면을 정함
    ("실이 한 가닥 있어요.", "line", {"form": "curve", "gauge": "thin"}),
    ("엉킨 실타래가 있어요.", "line", {"form": "tangle", "gauge": "thin"}),
    ("매듭이요. 단단하게 묶여 있어요.", "line", {"form": "knot"}),
    ("굵은 밧줄이 있어요.", "line", {"form": "curve", "gauge": "thick"}),
    ("가느다란 검은 실이 엉켜 있어요.", "line", {"form": "tangle", "gauge": "thin"}),         # 같은 문장의 '엉키'가 tangle
    ("굵은 실이 있어요.", "line", {"form": "curve", "gauge": "thick"}),                      # 말한 '굵'이 낱말 뜻(thin)을 덮음
    ("선이요. 한 줄로 쭉.", "line", {"form": "curve"}),
    ("종이 한 장이 있어요.", "sheet", {"drape": "paper"}),                                   # 수량 표현 뒤의 주어
    ("얇은 천이 있어요. 보라색이에요.", "sheet", {"drape": "cloth"}),
    ("막이요. 얇은 막.", "sheet", {"drape": "cloth"}),
    ("보자기 같은 게 있어요.", "sheet", {"drape": "cloth"}),
]


@pytest.mark.parametrize("text,base,variant", WORDS)
def test_word_goes_to_form_base(v2, text, base, variant):
    spec = build(v2, text)
    assert spec["form"]["base"] == base
    assert spec["form"]["baseVariant"] == variant
    assert spec["_provenance"]["form.base"][0]["rule"].startswith("baseShapes.")
    assert schema_errors(spec) == []


def test_simile_is_recorded_as_simile(v2):
    spec = build(v2, "그릇 같은 게 있어요.")
    p = spec["_provenance"]["form.base"][0]
    assert spec["form"]["base"] == "container" and p["source"] == "simile_marker" and p["rule"].endswith("+simile(같은)")


@pytest.mark.parametrize("text", [
    "그릇은 아니에요.",                         # 부정
    "그릇이 없어요.",
    "화분 옆에 뭔가 있어요.",                     # 장소
    "컵을 들고 있는 느낌이에요.",                  # 목적어
    "어제 컵을 깨뜨렸던 게 생각나요.",              # 회상 문장
    "병이 있어요.",                             # 동음이의 맨 낱말
    "종이컵이 있어요.",                          # 뒷부분만 맞추지 않음
])
def test_no_base_without_a_said_shape_noun(v2, text):
    spec = build(v2, text)
    assert spec["form"]["base"] is None and spec["form"]["baseVariant"] is None
    assert "form.base" not in spec["_provenance"]


def test_negated_base_noun_is_recorded_in_negated(v2):
    spec = build(v2, "그릇은 아니에요.")
    assert any(n["lemma"] == "그릇" for n in spec["_negated"])


def test_two_different_bases_first_wins_and_rest_is_alternative(v2):
    text = "그릇이 있어요. 유리병도 있어요."
    spec = build(v2, text)
    assert spec["form"]["base"] == "container"
    assert [p["trigger"] for p in spec["_provenance"]["form.base"]] == ["그릇", "유리병"]   # 같은 형상이면 근거에 더함
    assert spec["form"]["baseVariant"] == {"opening": "wide"}                           # 변형값은 처음 낱말


@pytest.mark.parametrize("text,word,code", [
    ("작은 사람이 웅크리고 있어요.", "사람", "human_figure"),
    ("괴물 같은 게 있어요.", "괴물", "attacking_being"),
    ("칼이 꽂혀 있어요.", "칼", "weapon"),
    ("무덤이 보여요.", "무덤", "death_trauma"),
    ("피가 고여 있어요.", "피", "blood_noose"),
    ("올가미가 걸려 있어요.", "올가미", "blood_noose"),
])
def test_excluded_words_are_recorded_not_drawn(v2, text, word, code):
    spec = build(v2, text)
    assert spec["form"]["base"] is None
    u = [x for x in spec["_unmapped"] if x["lemma"] == word]
    assert len(u) == 1 and u[0]["reason"] == "excluded_shape" and u[0]["value"]["excluded"] == code
    assert schema_errors(spec) == []


def test_excluded_word_in_context_sentence_is_not_marked(v2):
    spec = build(v2, "어제 사람을 만났던 일이 생각나요. 가슴이 답답해요.")
    assert not any(x["reason"] == "excluded_shape" for x in spec["_unmapped"])


def test_same_text_gives_same_bytes(v2):
    t = "까만 네모난 상자예요. 칼 같은 것도 있어요."
    assert dumps(v2.build(t, session_id="A")) == dumps(v2.build(t, session_id="A"))


# ── 후보·조절 ───────────────────────────────────────────────────────────────
def test_base_is_never_a_candidate_value_and_closes_form_slot(v2):
    spec = build(v2, "가슴 앞에 화분이 있어요.")
    assert base_drawn(spec)
    assert not slot_is_open(spec, "form.type", TABLE) and not slot_is_open(spec, "form.base", TABLE)
    out = generate(spec, "SYN-C", TABLE)
    assert all(ax["slot"] not in ("form.type", "form.base") for ax in out["axes"])
    for c in out["candidates"]:
        assert "form.base" not in c["overrides"] and "form.type" not in c["overrides"]
        assert c["sources"]["form.base"] == "said" and c["sources"]["form.type"] == "default"
    # 형상을 말하지 않은 사람에게는 형태 축 값이 form.type 표에서만 온다(기본 형상을 내밀지 않음)
    feel = build(v2, "가슴 안쪽이 답답하고 무거운 느낌이에요.")
    vals = {v for ax in generate(feel, "SYN-C", TABLE)["axes"] if ax["slot"] == "form.type" for v in ax["values"]}
    assert vals and not vals & set(BASE_SHAPES)


def test_base_with_mist_is_kept_in_spec_but_not_drawn(v2):
    """form.type이 mist이면 기본 형상은 spec에 남지만 그려지지 않는다(Unity not_applied_form, docs/asset-plan.md 2-5절).
    형태는 말한 자리(mist)라 후보에서 벌리지 않는다."""
    spec = build(v2, "안개가 있어요. 그릇처럼 생겼어요.")
    assert spec["form"]["type"] == "mist" and spec["form"]["base"] == "container"
    assert not base_drawn(spec) and not slot_is_open(spec, "form.type", TABLE)
    out = generate(spec, "SYN-C", TABLE)
    assert all(c["sources"]["form.type"] == "said" and c["sources"]["form.base"] == "said" for c in out["candidates"])


def test_adjust_form_item_lists_approved_bases():
    it = TABLE["adjustItems"]["items"]["form"]
    assert it["values"] == ["blob", "mist", "shell", "fragments", *BASE_SHAPES]
    assert it["slots"] == ["form.type", "form.base"]
    for b in BASE_SHAPES:
        assert it["valueOverrides"][b] == {"form.type": "blob", "form.base": b}
    for ft in ("blob", "mist", "shell", "fragments"):
        assert it["valueOverrides"][ft] == {"form.type": ft, "form.base": "none"}
    assert "form.base" in TABLE["overrideKeys"]["categorical"]
    assert TABLE["defaults"]["form.base"] == "none"


# ── 조절 흐름(선택 파일) ────────────────────────────────────────────────────
from test_selection_flow import done_session, rt4, runner_contract_errors, started, valid  # noqa: E402,F401


def test_adjust_flow_base_said_then_edited(rt4):
    """말한 기본 형상(container)이 조절 화면의 현재 값이고, 다른 형태(mist)를 고르면 form.type·form.base가 함께 '고침'.
    finalOverrides에 form.base none이 들어가고 선택 파일은 스키마·러너 계약을 지킨다."""
    s, f = started(rt4, "SYN-BASE-ADJ", "가슴 앞에 화분이 있어요.")
    v = f.view()
    assert v["current"]["items"]["form"] == "container"
    v = f.adjust("form", "mist")
    assert v["current"]["items"]["form"] == "mist"
    f.finish()
    assert f.data["finalOverrides"]["form.type"] == "mist" and f.data["finalOverrides"]["form.base"] == "none"
    assert f.data["sources"]["form.base"] == "edited" and f.data["sources"]["form.type"] == "edited"
    assert f.data["sourceDetails"]["form.base"]["saidValue"] == "container"
    valid(f.data)
    assert runner_contract_errors(json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))) == []


def test_adjust_flow_pick_a_base_without_saying_one(rt4):
    """형상을 말하지 않았어도 조절의 형태 항목에서 기본 형상을 고를 수 있다(G22). 출처는 고침, form.type은 그대로 기본값."""
    s, f = started(rt4, "SYN-BASE-PICK", "가슴 안쪽이 답답하고 무거운 느낌이에요.")
    f.adjust("form", "container")
    f.finish()
    assert f.data["finalOverrides"].get("form.base") == "container"
    assert f.data["sources"]["form.base"] == "edited"
    valid(f.data)


# ── G32 동작 변경 고정(D6) ──────────────────────────────────────────────────
T_THREAD = "가슴 안쪽에 실 같은 게 감겨 있어요."


def test_thread_was_unrendered_shape_word_and_is_now_a_drawn_base(v2, an):
    """builder 2.1.0까지 '실'은 모형 없는 모양어(_unmapped shape thread)라 G32 규칙으로 형태 후보(blob·mist)를 벌리고 출처를
    said_unrendered_*로 적었다. D6부터 '실'은 form.base = line의 근거가 되어 _unmapped에서 빠지고, 형태 자리는 말한 자리다
    (후보에서 벌리지 않음, 출처 form.base = said, form.type = default)."""
    from ifs_chatbot.candidates import form_said_unrendered, unrendered_shape_words
    v1 = SceneSpecBuilderV1(an)
    old = v1.build(T_THREAD)
    assert [u["value"]["shape"] for u in old["_unmapped"] if u["category"] == "shape"] == ["thread"]
    spec = build(v2, T_THREAD)
    assert spec["form"]["base"] == "line" and spec["_provenance"]["form.base"][0]["source"] == "simile_marker"
    assert not unrendered_shape_words(spec, TABLE) and not form_said_unrendered(spec, TABLE)
    out = generate(spec, "SYN-C", TABLE)
    assert all(ax["slot"] != "form.type" and ax["reason"] != "said_unrendered" for ax in out["axes"])
    assert all(c["sources"]["form.base"] == "said" and c["sources"]["form.type"] == "default" for c in out["candidates"])
    # 같은 spec에서 form.base만 지우면(= builder 2.1.0의 판정) 다시 G32 경로
    old_like = json.loads(json.dumps(spec))
    old_like["form"]["base"], old_like["form"]["baseVariant"] = None, None
    old_like["_unmapped"].append({"lemma": "실", "category": "shape", "value": {"shape": "thread"}, "reason": "no_scene_param",
                                  "_provenance": spec["_provenance"]["form.base"][0]})
    assert form_said_unrendered(old_like, TABLE)
    assert generate(old_like, "SYN-C", TABLE)["axes"][0]["reason"] == "said_unrendered"


def test_line_word_beside_another_noun_is_not_a_base(v2):
    """'털실 뭉치처럼'의 직유 원천은 '뭉치'(blob)라 털실은 꾸밈말 — base가 아니다(사전에 있어도)."""
    spec = build(v2, "털실 뭉치처럼 생겼어요.")
    assert spec["form"]["base"] is None and spec["form"]["type"] == "blob"


def test_numeral_cheon_is_not_cloth(v2):
    spec = build(v2, "천천히 움직여요. 천 원짜리 같아요.")
    assert spec["form"]["base"] is None


def test_membrane_split_offers_shell_reading(v2):
    """'막'은 얇은 판(sheet)과 껍질(shell) 두 읽기 — 후보 표의 갈림(membrane): blob(= 기본 형상 sheet가 그려짐) | shell.
    갈림 축이 빈 자리 축보다 먼저이고, 말한 다른 슬롯은 모든 후보에서 같다(G9·G18)."""
    spec = build(v2, "막이요. 얇은 막.")
    out = generate(spec, "SYN-M", TABLE)
    ax = out["axes"][0]
    assert ax["slot"] == "form.type" and ax["reason"] == "ambiguous" and ax["values"] == ["blob", "shell"]
    assert ax["split"]["id"] == "membrane" and ax["split"]["lemma"] == "막"
    shell = [c for c in out["candidates"] if c["axisValues"].get("form.type") == "shell"]
    assert shell and all(c["overrides"]["form.type"] == "shell" and "form.base" not in c["overrides"] for c in shell)
    # 형태를 말했으면(form.type 있음) 갈림을 쓰지 않는다
    told = json.loads(json.dumps(spec))
    told["form"]["type"] = "mist"
    told["_provenance"]["form.type"] = [dict(spec["_provenance"]["form.base"][0], rule="synthetic>form.type:mist")]
    assert all(a["reason"] != "ambiguous" for a in generate(told, "SYN-M", TABLE)["axes"])
