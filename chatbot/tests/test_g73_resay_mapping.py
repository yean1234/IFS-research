"""G73-c 재진술 전용 매핑(ifs_chatbot/resay.py): 갈래 + 허용 슬롯 값만, 값마다 글자 위치·규칙·판. 합성 대사만(AGENTS.md 6)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("kiwipiepy")

from ifs_chatbot.korean import Analyzer  # noqa: E402
from ifs_chatbot.paths import shared  # noqa: E402
from ifs_chatbot.resay import RESAY_MAPPING_VERSION, ResayMapper, mapping_bytes  # noqa: E402
from ifs_chatbot.scene_builder import normalize_confirmed  # noqa: E402

ALLOWED = ["form.type", "mist.density", "layout.proportions", "material.opacity", "material.emission"]
CORPUS = Path(__file__).resolve().parent / "fixtures" / "imagery_corpus"


@pytest.fixture(scope="module")
def m():
    return ResayMapper(Analyzer())


def vals(r):
    return {k: v["value"] for k, v in r["values"].items() if v is not None}


def test_table_is_draft_with_own_version():
    t = json.loads(Path(shared("lexicon", "resay_values.v0.json")).read_text(encoding="utf-8"))
    assert t["status"] == "draft" and t["tableVersion"] == "0.1.0" and t["allowedSlots"] == ALLOWED
    f = json.loads(Path(shared("lexicon", "resay_prompt_filter.v0.json")).read_text(encoding="utf-8"))
    assert f["status"] == "draft" and f["tableVersion"] == "0.1.0"


def test_fog_case_values(m):
    r = m.map("구름 같은데 구름 보다는 덜 뺵뺵하고 보이지 않는 안개같은?")
    assert r["branch"] == "mist" and r["mappingVersion"] == RESAY_MAPPING_VERSION
    assert vals(r) == {"form.type": "mist", "mist.density": 0.4, "material.opacity": 0.15}
    d = r["values"]["mist.density"]
    assert d["ko"] == ["덜 뺵뺵하고"] and d["rules"][0].startswith("resay.density.high+less")
    assert d["table"] == "resay-values-v0@0.1.0" and d["source"] == "resay_rule"
    assert r["values"]["layout.proportions"] is None             # 말하지 않은 슬롯은 None(기본값과 섞지 않음)


def test_color_size_position_motion_are_not_read(m):
    r = m.map("빨갛고 커다란 공이 머리 위에서 빠르게 빙글빙글 돌아요")
    assert r["branch"] == "solid" and vals(r) == {}
    paths = {x["path"] for x in r["notRead"]}
    assert {"material.color", "layout.size", "motion.type"} <= paths
    assert all(set(x) == {"path", "charSpans", "reason"} for x in r["notRead"])    # 값은 남기지 않는다
    r = m.map("검은 안개가 있는 느낌")
    assert vals(r) == {"form.type": "mist"} and [x["path"] for x in r["notRead"]] == ["material.color"]


def _corpus_texts():
    out = []
    for n in ("dev.json", "heldout.json"):
        d = json.loads((CORPUS / n).read_text(encoding="utf-8"))
        for it in d["items"]:
            out += [v for v in it["replies"].values() if v]
    return out


def test_only_allowed_slots_and_every_value_traceable_on_corpus(m):
    texts = _corpus_texts() + ["넓게 펼쳐진 옅은 안개가 반쯤 투명해요", "희미하게 반짝이는 빛", "짙은 연기가 빛나요"]
    assert len(texts) > 100
    for t in texts:
        r = m.map(t)
        norm = normalize_confirmed(t)
        assert list(r["values"]) == ALLOWED and r["branch"] in ("solid", "mist", "light", "flame", "blocked", "none")
        for path, v in r["values"].items():
            if v is None:
                continue
            assert v["charSpans"] and v["rules"] and v["table"], (t, path)
            for s, e in v["charSpans"]:
                assert 0 <= s < e <= len(norm), (t, path)
            if v["source"] in ("resay_rule", "resay_branch", "lexicon_implied"):
                assert [norm[s:e] for s, e in v["charSpans"]] == v["ko"], (t, path)
            if path == "form.type":
                assert v["value"] == "mist" and r["branch"] == "mist"
            if path == "mist.density":
                assert r["branch"] == "mist"


@pytest.mark.parametrize("text,density", [("옅은 안개", 0.25), ("짙은 안개", 0.8), ("아주 빽빽한 안개", 0.9),
                                          ("빽빽하지 않은 연기", 0.35), ("조금 옅은 연기", 0.35), ("자욱한 안개", 0.8)])
def test_density_words(m, text, density):
    r = m.map(text)
    assert r["branch"] == "mist" and r["values"]["mist.density"]["value"] == density


def test_density_outside_mist_is_dropped(m):
    r = m.map("빽빽한 덩어리가 있어요")
    assert r["branch"] == "solid" and r["values"]["mist.density"] is None
    assert any(d["reason"] == "branch_not_mist" for d in r["dropped"])


@pytest.mark.parametrize("text,branch", [
    ("빛줄기가 비쳐요", "light"), ("불꽃이 타올라요", "flame"), ("둥근 덩어리", "solid"), ("둥근 조약돌이에요", "solid"),
    ("동그랗고 납작해요", "solid"), ("불안한 느낌", "none"), ("작은 인형 같아요", "blocked"), ("곰인형", "blocked"),
    ("마스코트 같은 거", "blocked"), ("고양이가 있어요", "blocked"), ("안개는 아니고 공이 있어요", "solid"),
    ("구름처럼 떠다녀요", "none"), ("어제 안개 낀 길을 걷던 게 떠올라요. 공이 있어요.", "solid"),
])
def test_branches(m, text, branch):
    assert m.map(text)["branch"] == branch


def test_light_branch_emission_implied_unless_said(m):
    r = m.map("빛이 있어요")
    e = r["values"]["material.emission"]
    assert e["value"] == "glowing" and e["source"] == "lexicon_implied" and e["ko"] == ["빛"]
    r = m.map("희미하게 반짝이는 빛")
    assert r["branch"] == "light" and r["values"]["material.emission"]["source"] == "mapper_v2"


def test_action_simile_mediator_does_not_set_branch(m):
    r = m.map("구름처럼 떠다녀요")
    assert r["branch"] == "none" and vals(r) == {}
    assert [d["reason"] for d in r["dropped"]] == ["action_simile"]


def test_deterministic_bytes(m):
    texts = ["검은 안개가 있는 느낌", "먹구름", "넓게 펼쳐진 안개가 떠오른다", "빛줄기가 비쳐요"]
    m2 = ResayMapper(Analyzer())
    for t in texts:
        assert mapping_bytes(m.map(t)) == mapping_bytes(m.map(t)) == mapping_bytes(m2.map(t))


def test_module_uses_no_model():
    src = (Path(__file__).resolve().parents[1] / "ifs_chatbot" / "resay.py").read_text(encoding="utf-8")
    for bad in ("llm", "ollama", "httpx", "urllib", "requests", "torch"):
        assert f"import {bad}" not in src and f"from .{bad}" not in src
