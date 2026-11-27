"""G62 형태 후보 생성기: 모델 없이 도는 단위 테스트(프롬프트 빌더·차단 규칙·후처리 결정성·사이드카 스키마).

  <venv>/python -m pytest tools/gen3d/tests -q

합성 문장만 쓴다(AGENTS.md 6). kiwipiepy가 없으면 프롬프트 테스트는 건너뛴다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

GEN3D = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN3D))

kiwi = pytest.importorskip("kiwipiepy")
import form_asset as fa  # noqa: E402
import prompts  # noqa: E402


def sp(text):
    return prompts.shape_prompt(text)


def content(p):
    return [t for t in p["tokens"] if t["slot"] != "template"]


# ── 프롬프트 빌더 ──────────────────────────────────────────────────────────────
def test_shape_words_only_with_charspans():
    text = "가슴 앞에 노란 공이 있어요. 동그랗고 매끈해요. 주먹만 해요."
    p = sp(text)
    assert p["status"] == "ok" and p["blockReason"] is None
    words = p["text"].split(",")[0]
    assert words == "a single round ball"
    for bad in ("yellow", "smooth", "fist", "small"):          # 색·질감·크기 비교는 넣지 않음
        assert bad not in p["text"]
    for t in content(p):
        s, e = t["charSpan"]
        assert text[s:e] == t["ko"]
    assert {t["slot"] for t in content(p)} == {"shape_noun", "shape_modifier"}
    assert p["familiarObjectStated"] is True and p["thinRisk"] is False


def test_template_tokens_marked():
    p = sp("네모난 상자가 있어요.")
    tmpl = [t for t in p["tokens"] if t["slot"] == "template"]
    assert tmpl and all(t["charSpan"] is None and t["ko"] is None for t in tmpl)
    assert "plain white background" in [t["en"] for t in tmpl]


def test_modifier_only_uses_template_noun():
    p = sp("뭔가 동그란 게 있어요.")
    assert p["status"] == "ok"
    assert p["text"].startswith("a single round object")
    obj = [t for t in p["tokens"] if t["en"] == "object"]
    assert obj and obj[0]["slot"] == "template"


def test_negated_word_dropped():
    p = sp("동그란 공은 아니고 네모난 상자예요.")
    assert "ball" not in p["text"] and "box" in p["text"]
    assert any(d["ko"] == "공" and d["reason"] == "negated" for d in p["dropped"])


def test_size_comparison_and_context_sentence_dropped():
    p = sp("택배 상자 뜯던 오후가 떠올라요.\n작은 알갱이들이 있어요.\n구슬만큼 작아요.")
    assert p["text"].startswith("a single granules")
    reasons = {(d["ko"], d["reason"]) for d in p["dropped"]}
    assert ("상자", "context_sentence") in reasons and ("구슬", "size") in reasons


def test_thin_risk():
    p = sp("얇은 천이 축 늘어져 있어요.")
    assert p["status"] == "ok" and p["thinRisk"] is True


def test_deterministic_same_text():
    t = "울퉁불퉁한 조개껍데기처럼 생긴 껍데기가 붙어 있어요."
    assert json.dumps(sp(t), sort_keys=True, ensure_ascii=False) == json.dumps(sp(t), sort_keys=True, ensure_ascii=False)


# ── 차단 규칙 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["가슴 안쪽이 답답하고 무거운 느낌이에요.", "회색이고 무거워요", "따뜻한 느낌만 있어요."])
def test_no_shape_stated(text):
    p = sp(text)
    assert p["status"] == "blocked" and p["blockReason"] == "no_shape_stated" and p["text"] == ""


@pytest.mark.parametrize("text", [
    "회색 안개가 천천히 퍼져요.",            # mist
    "가슴 앞에 연기 같은 게 있어요.",
    "주황색 빛 덩어리가 있어요.",
    "촛불 같은 불꽃이 있어요.",
    "작은 사람이 웅크리고 있어요.",           # 기존 G45–G51 제외 판정
    "끈 같은 귀신이 있어요.",
    "칼처럼 생긴 게 있어요.",
    "뱀처럼 생긴 것이 있어요.",
    "끈인데 올가미 같아요.",
    "고양이가 소파에 누워 있어요.",           # 보충 목록
    "얼굴이 보여요.",
])
def test_excluded_category(text):
    p = sp(text)
    assert p["status"] == "blocked" and p["blockReason"] == "excluded_category" and p["blockDetail"]
    assert p["text"] == ""


@pytest.mark.parametrize("text,word", [
    ("뱀 같은 끈이 있어요.", "string"),        # G45: 비유 원천이면 중심 명사를 그림
    ("아이 장난감 상자예요.", "box"),
    ("얼굴 앞에 길쭉한 막대가 있어요.", "rod"),  # 몸 위치의 '얼굴'은 막지 않음
    ("유리병이 서 있어요. 뒤로 햇빛이 들어와요.", "bottle"),   # 배경 빛은 막지 않음
])
def test_not_excluded(text, word):
    p = sp(text)
    assert p["status"] == "ok", p["blockDetail"]
    assert word in p["text"]


# ── 후처리·캐시 키·내보내기 결정성 ──────────────────────────────────────────────────
def _mesh():
    import trimesh

    m = trimesh.creation.icosphere(subdivisions=5)          # 20480면
    m.vertices *= np.array([0.7, 1.3, 0.4])
    m.vertices += np.array([0.3, -0.2, 0.9])
    return np.asarray(m.vertices), np.asarray(m.faces)


def test_postprocess_normalizes_and_is_deterministic(tmp_path):
    v, f = _mesh()
    a, na = fa.postprocess(v, f, face_limit=5000)
    b, nb = fa.postprocess(v.copy(), f.copy(), face_limit=5000)
    assert np.array_equal(a.vertices, b.vertices) and np.array_equal(a.faces, b.faces) and na == nb
    lo, hi = a.bounds
    assert abs((hi - lo).max() - 1.0) < 1e-5                    # 가장 긴 변 1.0
    assert abs(lo[1]) < 1e-6                                    # 바닥 y = 0
    assert abs(lo[0] + hi[0]) < 1e-5 and abs(lo[2] + hi[2]) < 1e-5   # bottom-center 피벗
    assert len(a.faces) <= 5000 and na["facesBefore"] == 20480 and na["facesAfter"] == len(a.faces)
    assert na["axisAligned"] is False and na["pivot"] == "bottom-center"
    assert fa.export_glb(a, tmp_path / "a.glb") == fa.export_glb(b, tmp_path / "b.glb")


def test_postprocess_under_limit_keeps_faces():
    v, f = _mesh()
    m, n = fa.postprocess(v, f, face_limit=100000)
    assert n["facesAfter"] == n["facesBefore"] == 20480


def test_cache_key_inputs():
    models = [{"name": "shape", "repo": "r", "revision": "abc", "weightsSha256": None}]
    k = fa.cache_key("a single ball", "sdxl-triposg", models, 0)
    assert k == fa.cache_key("a single ball", "sdxl-triposg", models, 0)
    assert k != fa.cache_key("a single ball", "sdxl-triposg", models, 1)
    assert k != fa.cache_key("a single box", "sdxl-triposg", models, 0)
    assert k != fa.cache_key("a single ball", "sdxl-triposg", [dict(models[0], revision="abd")], 0)


def test_render_views_deterministic():
    v, f = _mesh()
    m, _ = fa.postprocess(v, f, face_limit=4000)
    a = fa.render_views(m, size=64, n_points=20000)
    b = fa.render_views(m, size=64, n_points=20000)
    assert len(a) == fa.GATE_VIEWS == 6
    assert all(np.array_equal(np.asarray(x), np.asarray(y)) for x, y in zip(a, b))
    assert np.asarray(a[0]).min() < 200                         # 물체가 그려짐


# ── 사이드카 스키마 ──────────────────────────────────────────────────────────────
def _validator():
    js = pytest.importorskip("jsonschema")
    return js.Draft202012Validator(json.loads(fa.SCHEMA_PATH.read_text(encoding="utf-8")))


def test_sidecar_blocked_and_ok_validate():
    val = _validator()
    models = [{"name": "shape", "repo": "VAST-AI/TripoSG", "revision": "x", "weightsSha256": {"a.safetensors": "0" * 64}}]
    p = sp("회색이고 무거워요")
    key = fa.cache_key(p["text"] + "\n" + p["sourceTextSha256"], "sdxl-triposg", models, 0)
    blocked = fa._sidecar(p, asset_id=key[:16], key=key, status="blocked", block=p["blockReason"],
                          block_detail=None, glb_name=None, glb_sha=None, pipeline="sdxl-triposg", models=models,
                          seed=0, norm=None, ratios=None, gate=None, timing=None, cache_hit=False)
    assert not list(val.iter_errors(blocked))
    q = sp("네모난 상자가 있어요.")
    v, f = _mesh()
    m, norm = fa.postprocess(v, f, face_limit=3000)
    k2 = fa.cache_key(q["text"], "sdxl-triposg", models, 0)
    ok = fa._sidecar(q, asset_id=k2[:16], key=k2, status="ok", block=None, block_detail=None,
                     glb_name=f"{k2[:16]}.glb", glb_sha="1" * 64, pipeline="sdxl-triposg", models=models, seed=0,
                     norm=norm, ratios=fa.axis_ratios(m),
                     gate={"personLikeScore": 0.01, "passed": True, "threshold": 0.5, "matchScore": 0.2},
                     timing={"image": 6.0}, cache_hit=False)
    assert not list(val.iter_errors(ok))
    bad = dict(ok, status="ok", glb=None)
    assert list(val.iter_errors(bad))                           # ok인데 GLB가 없으면 거부
    bad2 = dict(blocked, blockReason="made_up")
    assert list(val.iter_errors(bad2))
    # 여러 물체로 막힌 사이드카(gate_failed + multi_object)도 스키마를 지킨다
    multi = fa.decide_multi_object(fa.component_stats(_two_spheres()), False)
    mo = fa._sidecar(q, asset_id=k2[:16], key=k2, status="blocked", block="gate_failed", block_detail="multi_object",
                     glb_name=None, glb_sha=None, pipeline="sdxl-triposg", models=models, seed=0, norm=norm,
                     ratios=fa.axis_ratios(m), gate={"personLikeScore": 0.01, "passed": False, "multiObject": multi},
                     timing=None, cache_hit=False)
    assert not list(val.iter_errors(mo))


# ── 0.2.0: 부속물 부정 틀·복수 표시·여러 물체 검사 ───────────────────────────────────
def test_versions_bumped():
    p = sp("동그란 공이 있어요.")
    assert p["lexiconVersion"] == "0.2.0" and p["templateVersion"] == "g62-template/0.2.0"


def test_negative_accessories_skip_said_words():
    ball = sp("동그란 공이 있어요.")
    assert "pedestal" in ball["negativeText"] and "string" in ball["negativeText"]
    assert ball["negativeText"].startswith("person, human, face")            # 안전 부정 틀은 그대로
    string = sp("가느다란 끈이 있어요.")
    assert "string" in string["text"]
    assert "string" not in [x.strip() for x in string["negativeText"].split(",")]   # 말한 끈은 부정하지 않음
    bowl = sp("둥근 그릇이 있어요.")
    assert "bowl" not in [x.strip() for x in bowl["negativeText"].split(",")]


def test_cache_key_depends_on_negative():
    models = [{"name": "shape", "repo": "r", "revision": "abc", "weightsSha256": None}]
    assert fa.cache_key("a single ball", "sdxl-triposg", models, 0, "x") != \
        fa.cache_key("a single ball", "sdxl-triposg", models, 0, "y")


@pytest.mark.parametrize("text,plural", [("작은 조각들이 모여 있어요.", True), ("작은 알갱이가 있어요.", True),
                                         ("구슬들이 있어요.", True), ("동그란 공이 있어요.", False)])
def test_plural_stated(text, plural):
    assert sp(text)["pluralStated"] is plural


def _two_spheres(gap=3.0, r2=1.0):
    import trimesh

    a = trimesh.creation.icosphere(subdivisions=3)
    b = trimesh.creation.icosphere(subdivisions=3, radius=r2)
    b.apply_translation([gap, 0, 0])
    return trimesh.util.concatenate([a, b])


def test_component_stats_multi_and_floater():
    two = fa.component_stats(_two_spheres())
    assert two["components"] == 2 and two["significant"] == 2
    assert fa.decide_multi_object(two, plural_stated=False)["blocked"] is True
    exempt = fa.decide_multi_object(two, plural_stated=True)
    assert exempt["blocked"] is False and exempt["applied"] is False
    floater = fa.component_stats(_two_spheres(r2=0.1))         # 면적 비율 약 1% → 무시
    assert floater["components"] == 2 and floater["significant"] == 1
    assert fa.decide_multi_object(floater, False)["blocked"] is False
    assert fa.component_stats(_two_spheres()) == two            # 결정적


def test_postprocess_keeps_components_separate():
    m, _ = fa.postprocess(*(lambda t: (t.vertices, t.faces))(_two_spheres()), face_limit=100000)
    assert fa.component_stats(m)["significant"] == 2
