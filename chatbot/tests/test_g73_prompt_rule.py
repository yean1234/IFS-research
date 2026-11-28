"""G73 후속(2026-11-28): [맞는 게 없어요] 생성 프롬프트가 세션 매퍼(v2) 판단을 따르는지, 캐시 적중이 확실하면 모델을 내리지 않는지.

- 프롬프트 규칙: tools/gen3d/prompts.shape_prompt(text, mapper_spec=세션 spec). 매퍼가 형태에서 버린 낱말(움직임 비유의 매개어 G71,
  부정, 장소 용법 G74-c)은 빠지고 prompt.dropped에 사유가 남는다. 형태를 직접 말한 낱말은 그대로. 텍스트만 넘기면 예전 규칙(0.2.0).
- 캐시 미리 보기: 생성기 --cache-probe(대역 tests/fixtures/fake_gen3d.py, FAKE_GEN3D_PROBE).
모든 대사는 합성이거나 연구 책임자 시험 대사(scenarios/g70_researcher_finish.json, 참여자 자료 아님)다."""
import json
import sys
from pathlib import Path

import pytest

from ifs_chatbot import none_gen as ng
from ifs_chatbot.config import load_config
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.paths import CHATBOT_DIR, shared
from ifs_chatbot.scene_builder import normalize_confirmed
from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2

FAKE = Path(__file__).parent / "fixtures" / "fake_gen3d.py"
SCEN = json.loads((CHATBOT_DIR / "scenarios" / "g70_researcher_finish.json").read_text(encoding="utf-8"))
T_RESEARCHER = "\n".join(SCEN["replies"])          # '바람이 불면 천이 펄럭이듯이 … 모양은 구체'


@pytest.fixture(scope="module")
def mapper():
    """experiment.toml과 같은 매퍼 v2(비율·안개 종류 표 켬)."""
    m = load_config("experiment").mapping
    return SceneSpecBuilderV2(Analyzer(), proportions_path=shared("lexicon", m.proportions),
                              mist_kinds_path=shared("lexicon", m.mist_kinds))


def both(mapper, text):
    norm = normalize_confirmed(text)
    spec = mapper.build(norm)
    return spec, ng.shape_prompt(norm), ng.shape_prompt(norm, spec)


def content(p):
    return [(t["ko"], t["en"]) for t in p["tokens"] if t["slot"] != "template"]


# ── 매개어 빠짐 ──────────────────────────────────────────────────────────────
def test_action_simile_medium_is_dropped_researcher_session(mapper):
    spec, old, new = both(mapper, T_RESEARCHER)
    # 매퍼는 '천'(펄럭이듯이의 매개어)을 형태로 받지 않고 대안으로만 남긴다(G71)
    alts = [a for a in spec["_alternatives"] if a["path"].startswith("form.")
            and any(p["trigger"] == "천" and "actionSimile" in p["rule"] for p in a["_provenance"])]
    assert alts
    # 예전 규칙(텍스트만, 0.2.0)은 '천'을 넣었다 — G73 시험 결함. 0.5.0(G84 후속)부터는 텍스트 규칙도 '바람이 불면'의 가정 표지로 뺀다
    assert "cloth" not in old["text"] and any(d["ko"] == "천" and d["reason"] == "hypothetical" for d in old["dropped"])
    assert new["status"] == "ok" and "cloth" not in new["text"]
    assert {"ko": "천", "charSpan": alts[0]["_provenance"][0]["charSpan"], "reason": "mapper_action_simile"} in new["dropped"]
    assert ("동그란", "round") in content(new)                            # 직접 말한 모양어는 그대로
    assert new["promptRule"] == "mapper" and new["builderVersion"].endswith("+mapper-v2")
    assert old["promptRule"] == "text" and old["builderVersion"] == "gen3d-shape-prompt/0.5.0"


def test_simile_medium_with_its_own_subject_keeps_the_subject(mapper):
    spec, old, new = both(mapper, "돌이 구름처럼 떠다녀요")
    assert spec["form"]["type"] != "mist"                                 # G71: 비유에서 온 mist를 내림
    assert old["status"] == "blocked"                                    # 예전: '구름' 때문에 막힘
    assert new["status"] == "ok" and content(new) == [("돌", "stone")]


# ── 부정 빠짐 ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,gone,kept", [
    ("공은 아니고 상자 같아요", "공", ("상자", "box")),
    ("동그랗지는 않고 네모난 상자예요", "동그랗", ("상자", "box")),
])
def test_negated_word_is_dropped(mapper, text, gone, kept):
    spec, old, new = both(mapper, text)
    assert new["status"] == "ok" and kept in content(new)
    assert all(not t["ko"].startswith(gone) for t in new["tokens"] if t["ko"])
    assert any(d["ko"].startswith(gone) and d["reason"] in ("negated", "mapper_negated") for d in new["dropped"])


# ── 직접 진술 유지(예전과 같음) ───────────────────────────────────────────────
@pytest.mark.parametrize("text", ["가슴이 답답해요\n엉킨 실타래 같아요\n회색이고 손바닥만 해요", "동그란 돌이에요",
                                  "작은 상자 같은 게 있어요", "천이 펄럭이듯이 움직여요"])
def test_direct_statements_are_kept_as_before(mapper, text):
    spec, old, new = both(mapper, text)
    assert (new["status"], new["text"]) == (old["status"], old["text"])
    assert not [d for d in new["dropped"] if d["reason"].startswith("mapper")]


# ── 장소 용법·안개류: 매퍼 판단을 따른다 ─────────────────────────────────────
def test_place_use_follows_mapper(mapper):
    spec, old, new = both(mapper, "안개 속에 돌이 있어요")
    if spec["form"]["type"] == "mist":                                  # 매퍼가 안개를 형태로 받았으면 그대로 막음
        assert new["status"] == "blocked"
    else:                                                               # G74-c: 장소 용법이면 형태가 아님 → 돌을 만든다
        assert new["status"] == "ok" and content(new) == [("돌", "stone")]


@pytest.mark.parametrize("text", ["넓게 펼쳐진 안개가 떠오른다", "연기가 피어올라요"])
def test_mist_said_as_the_object_stays_blocked(mapper, text):
    spec, old, new = both(mapper, text)
    assert spec["form"]["type"] == "mist"
    assert new["status"] == "blocked" and new["blockReason"] == "excluded_category"


def test_spec_of_other_text_fails_closed(mapper):
    norm = normalize_confirmed("엉킨 실타래 같아요")
    other = mapper.build(normalize_confirmed("동그란 돌이에요"))
    p = ng.shape_prompt(norm, other)
    assert p["status"] == "blocked" and p["blockReason"] == "mapper_spec_mismatch" and p["text"] == ""


def test_same_text_and_spec_give_same_prompt(mapper):
    norm = normalize_confirmed(T_RESEARCHER)
    spec = mapper.build(norm)
    a, b = ng.shape_prompt(norm, spec), ng.shape_prompt(norm, json.loads(json.dumps(spec)))
    assert a == b


def test_generator_row_rule(mapper):
    gp = ng._load_prompts()
    norm = normalize_confirmed(T_RESEARCHER)
    spec = mapper.build(norm)
    assert gp.shape_prompt_for_row({"id": "x", "text": norm}) == gp.shape_prompt(norm)
    assert gp.shape_prompt_for_row({"id": "x", "text": norm, "promptRule": "mapper", "mapperSpec": spec}) == \
        gp.shape_prompt(norm, mapper_spec=spec)
    with pytest.raises(SystemExit):
        gp.shape_prompt_for_row({"id": "x", "text": norm, "promptRule": "mapper"})


# ── 캐시 미리 보기: 적중이 확실하면 모델을 내리지 않음 ──────────────────────────
def _svc(tmp_path, monkeypatch, probe):
    over = {"llm.backend": "ollama", "guard.model_backend": "ollama", "session.log_dir": str(tmp_path / "logs"),
            "gen3d.on_none": True, "gen3d.assets_dir": str(tmp_path / "gen3d-out"),
            "gen3d.on_none_python": sys.executable, "gen3d.on_none_script": str(FAKE)}
    c = load_config("v4").with_overrides(**over)
    calls = []

    class R:
        status_code = 200

        def json(self):
            return {"models": []}

    monkeypatch.setattr(ng.httpx, "post", lambda url, json=None, timeout=None: calls.append(dict(json)) or R())
    monkeypatch.setattr(ng.httpx, "get", lambda url, timeout=None: R())
    monkeypatch.setenv("FAKE_GEN3D_MODE", "ok")
    monkeypatch.setenv("FAKE_GEN3D_DELAY", "0")
    monkeypatch.setenv("FAKE_GEN3D_PROBE", probe)
    return ng.NoneGenService(c, tmp_path / "gen3d-out"), calls


@pytest.mark.parametrize("probe,skipped", [("hit", True), ("miss", False), ("fail", False)])
def test_cache_probe_decides_unload(tmp_path, monkeypatch, mapper, probe, skipped):
    svc, calls = _svc(tmp_path, monkeypatch, probe)
    norm = normalize_confirmed("엉킨 실타래 같아요")
    spec = mapper.build(norm)
    p = ng.shape_prompt(norm, spec)
    job = ng.NoneGenJob("SYN-G73P", norm, p["sourceTextSha256"], p["text"], 0, 0, spec)
    res = svc._run(job)
    assert res["status"] == ng.OK
    unloads = [c for c in calls if c.get("keep_alive") == 0]
    if skipped:
        assert res["llmUnload"]["skipped"] == "cache_hit_expected" and res["llmUnload"]["models"] == []
        assert unloads == [] and res["cacheProbe"]["modelCallsExpected"] is False
    else:
        assert len(unloads) == 2 and res["llmUnload"].get("skipped") is None
        if probe == "fail":
            assert res["cacheProbe"]["modelCallsExpected"] is None and res["cacheProbe"]["error"]
    # 생성기 입력에 매퍼 규칙과 세션 spec
    row = json.loads((tmp_path / "gen3d-out" / res["run"] / "inputs" / "sentences.json").read_text(encoding="utf-8"))[0]
    assert row["promptRule"] == "mapper" and row["mapperSpec"]["meta"]["sourceTextHash"].endswith(p["sourceTextSha256"])
