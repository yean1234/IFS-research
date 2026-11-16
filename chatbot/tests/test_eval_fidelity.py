"""일치도 채점 규칙(ifs_chatbot.eval.fidelity)과 코퍼스 재생(corpus_run) 테스트.
대사는 모두 합성(AGENTS.md 6). spec은 채점 규칙만 보려고 손으로 만든 작은 가짜다."""
import json

import pytest

from ifs_chatbot.eval import corpus_run, fidelity
from ifs_chatbot.eval.fidelity import aggregate, coverage, find_spans, preservation_spans, satisfies, score_item

TEXT = "노란 공이 있어요.\n파란 벽 앞이에요.\n표면은 오돌토돌해요."


def blank_spec(**slots) -> dict:
    spec = {"form": {"type": None, "posture": None},
            "material": {"color": None, "brightness": None, "saturation": None, "roughness": None, "opacity": None,
                         "erosion": None},
            "layout": {"size": None, "distance": None, "verticalOffset": None},
            "motion": {"type": None, "speed": None},
            "body": {"part": None, "layer": None},
            "_provenance": {}, "_unmatched": [], "_unmapped": [], "_negated": [], "_alternatives": [], "_inferred": {}}
    for path, (value, triggers) in slots.items():
        g, k = path.split(".")
        spec[g][k] = value
        spec["_provenance"][path] = [{"source": "explicit_lexicon", "trigger": TEXT[s:e], "charSpan": [s, e],
                                      "rule": "test"} for s, e in triggers]
    return spec


def span_of(word: str, text: str = TEXT, nth: int = 0) -> tuple[int, int]:
    return find_spans(text, word)[nth]


def item(gold, distractors=(), replies=None, iid="T01"):
    return {"id": iid, "style": "multi_turn", "replies": replies or {"opening": TEXT},
            "gold": list(gold), "distractors": list(distractors)}


def g(attr, phrase, slot, expect, negated=False):
    return {"attr": attr, "phrase": phrase, "slot": slot, "expect": expect, "negated": negated}


YELLOW = {"h": 55 / 360, "s": 0.9, "l": 0.55}
BLUE = {"h": 215 / 360, "s": 0.7, "l": 0.5}
YELLOW_EXPECT = {"hue_deg": [40, 70], "s": [0.4, 1.0], "l": [0.35, 0.75]}


def status_of(scored, attr):
    return next(a for a in scored["attributes"] if a["attr"] == attr)


# ── expect 판정 ──────────────────────────────────────────────────────────────
def test_satisfies_kinds():
    assert satisfies("blob", {"equals": "blob"}) and not satisfies("mist", {"equals": "blob"})
    assert satisfies(None, {"equals": None}) and not satisfies("inner", {"equals": None})
    assert satisfies("around", {"in": ["around", "around_behind"]}) and not satisfies(None, {"in": ["around"]})
    assert satisfies(0.3, {"range": [0.0, 0.35]}) and satisfies(0.35, {"range": [0.0, 0.35]})
    assert not satisfies(0.36, {"range": [0.0, 0.35]}) and not satisfies("0.3", {"range": [0, 1]})
    assert not satisfies(True, {"range": [0, 1]})
    assert satisfies(YELLOW, YELLOW_EXPECT) and not satisfies(BLUE, YELLOW_EXPECT)


def test_satisfies_hue_wraps_through_zero():
    red_lo, red_hi = {"h": 350 / 360, "s": 0.8, "l": 0.5}, {"h": 10 / 360, "s": 0.8, "l": 0.5}
    exp = {"hue_deg": [345, 15]}
    assert satisfies(red_lo, exp) and satisfies(red_hi, exp)
    assert not satisfies({"h": 30 / 360, "s": 0.8, "l": 0.5}, exp)


def test_satisfies_achromatic_without_hue():
    grey = {"h": 0.0, "s": 0.05, "l": 0.5}
    assert satisfies(grey, {"s": [0.0, 0.2], "l": [0.3, 0.7]})
    assert not satisfies(grey, {"s": [0.0, 0.2], "l": [0.1, 0.4]})


def test_satisfies_rejects_unknown_expect():
    with pytest.raises(ValueError):
        satisfies(0.5, {"approx": 0.5})


def test_find_spans_normalizes_and_finds_all():
    assert find_spans("공 공", "공") == [(0, 1), (2, 3)]
    assert find_spans(TEXT, "노란  공") == [(0, 4)]   # 연속 공백은 정규화
    assert find_spans(TEXT, "없는 말") == []


# ── 상태 판정 ────────────────────────────────────────────────────────────────
def test_reflected_and_wrong_value_distorted():
    gold = [g("color", "노란", "material.color", YELLOW_EXPECT)]
    ok = score_item(item(gold), {"confirmedText": TEXT, "spec": blank_spec(**{"material.color": (YELLOW, [span_of("노란")])})})
    assert status_of(ok, "color")["status"] == "reflected"
    bad = score_item(item(gold), {"confirmedText": TEXT, "spec": blank_spec(**{"material.color": (BLUE, [span_of("파란")])})})
    a = status_of(bad, "color")
    assert a["status"] == "distorted" and a["reason"] == "wrong_value"


def test_equals_null_means_value_must_stay_null():
    gold = [g("color", "노란", "material.color", {"equals": None})]
    assert status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": blank_spec()}), "color")["status"] == "reflected"
    spec = blank_spec(**{"material.color": (YELLOW, [span_of("노란")])})
    assert status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": spec}), "color")["status"] == "distorted"


def test_cross_slot_distortion_when_phrase_makes_other_slot_value():
    gold = [g("texture_roughness", "표면은 오돌토돌해요", "material.roughness", {"range": [0.6, 1.0]})]
    spec = blank_spec(**{"body.layer": ("surface", [span_of("표면")])})
    a = status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": spec}), "texture_roughness")
    assert a["status"] == "distorted" and a["reason"] == "cross_slot"
    assert a["crossSlot"][0]["path"] == "body.layer"


def test_cross_slot_not_counted_when_other_value_matches_its_gold():
    gold = [g("texture_roughness", "표면은 오돌토돌해요", "material.roughness", {"range": [0.6, 1.0]}),
            g("body_layer", "벽 앞", "body.layer", {"equals": "surface"})]
    spec = blank_spec(**{"body.layer": ("surface", [span_of("표면")])})
    a = status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": spec}), "texture_roughness")
    assert a["status"] == "lost" and a["crossSlot"] == []


def test_preserved_requires_verbatim_cover_of_whole_phrase():
    gold = [g("texture_roughness", "오돌토돌해요", "material.roughness", {"range": [0.6, 1.0]})]
    s, e = span_of("오돌토돌해요")
    spec = blank_spec()
    spec["_unmatched"] = [{"lemma": "오돌토돌", "tag": "XR", "surface": TEXT[s:s + 4], "charSpan": [s, s + 4]}]
    part = status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": spec}), "texture_roughness")
    assert part["status"] == "lost" and 0 < part["coverageAny"] < 1
    spec["_verbatim"] = [{"text": TEXT[s:e], "charSpan": [s, e]}]          # 개선 매핑의 보존 필드(이름 무관)
    full = status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": spec}), "texture_roughness")
    assert full["status"] == "preserved" and full["verbatimPreserved"]


def test_preservation_span_must_match_text():
    s, e = span_of("오돌토돌해요")
    spec = {"_x": [{"text": "다른 글자", "charSpan": [s, e]}], "_provenance": {"a.b": [{"trigger": TEXT[s:e], "charSpan": [s, e]}]}}
    assert preservation_spans(spec, TEXT) == []                           # 글자가 다르면, _provenance는 보존 필드 아님
    assert coverage(TEXT, (s, e), [(s, e)]) == 1.0


def test_dropped_by_controller_vs_phrase_missing():
    gold = [g("size", "주먹만 해요", "layout.size", {"range": [0.05, 0.5]}),
            g("color", "보라색", "material.color", YELLOW_EXPECT)]
    it = item(gold, replies={"opening": TEXT, "probe_size_shape": "주먹만 해요."})
    sc = score_item(it, {"confirmedText": TEXT, "spec": blank_spec()})
    assert status_of(sc, "size")["status"] == "dropped_by_controller"
    assert status_of(sc, "color")["status"] == "phrase_missing"
    summ = aggregate([sc])["overall"]
    assert summ["slotAttributes"] == 1 and summ["droppedRate"] == 1.0     # phrase_missing은 집계 제외


def test_negation_error_and_contamination_and_spurious():
    gold = [g("brightness", "공이", "material.brightness", None, negated=True),
            g("color", "노란", "material.color", YELLOW_EXPECT)]
    spec = blank_spec(**{"material.color": (BLUE, [span_of("파란")]),
                         "material.brightness": (0.7, [span_of("공이")]),
                         "layout.size": (0.3, [span_of("벽")])})
    sc = score_item(item(gold, distractors=[{"phrase": "파란 벽", "why": "배경"}]), {"confirmedText": TEXT, "spec": spec})
    assert status_of(sc, "brightness")["negationError"][0]["path"] == "material.brightness"
    assert {(c["path"], c["decisive"]) for c in sc["contamination"]} == {("material.color", True), ("layout.size", True)}
    assert {s["path"] for s in sc["spurious"]} == {"material.brightness", "layout.size"}  # 부정 정답은 경로를 허가하지 않음
    summ = aggregate([sc])["overall"]
    assert summ["negationErrors"] == 1 and summ["contamination"] == 2 and summ["spuriousValues"] == 2


def test_no_slot_and_unscored_attributes():
    gold = [g("shape", "공이", None, None), g("motion_type", "벽 앞", "motion.type", None)]
    spec = blank_spec(**{"motion.type": ("still", [span_of("벽")])})
    s, e = span_of("공이")
    spec["_unmatched"] = [{"lemma": "공", "tag": "NNG", "surface": TEXT[s:e], "charSpan": [s, e]}]
    sc = score_item(item(gold), {"confirmedText": TEXT, "spec": spec})
    assert status_of(sc, "shape")["status"] == "preserved"
    assert status_of(sc, "motion_type")["status"] == "captured"
    summ = aggregate([sc])["overall"]
    assert summ["slotAttributes"] == 0 and summ["preserveRate"] == 1.0


def test_rates():
    gold = [g("color", "노란", "material.color", YELLOW_EXPECT),
            g("size", "공이", "layout.size", {"range": [0.0, 0.2]}),
            g("texture_roughness", "오돌토돌해요", "material.roughness", {"range": [0.6, 1.0]}),
            g("shape", "벽 앞", None, None)]
    spec = blank_spec(**{"material.color": (YELLOW, [span_of("노란")]), "layout.size": (0.5, [span_of("공이")])})
    summ = aggregate([score_item(item(gold), {"confirmedText": TEXT, "spec": spec})])["overall"]
    assert summ["slotAttributes"] == 3
    assert summ["reflectRate"] == round(1 / 3, 4) and summ["distortRate"] == round(1 / 3, 4)
    assert summ["lostRate"] == round(1 / 3, 4)
    assert summ["preserveRate"] == 0.25                                     # reflected 1 / 전체 4


def test_missing_spec_counts_as_empty():
    gold = [g("color", "노란", "material.color", YELLOW_EXPECT)]
    sc = score_item(item(gold), {"confirmedText": TEXT, "spec": None})
    assert status_of(sc, "color")["status"] == "lost"


# ── 실제 컨트롤러로 재생 ──────────────────────────────────────────────────────
SYN = {"corpusId": "unit", "version": "0", "items": [{
    "id": "U01", "style": "multi_turn",
    "replies": {"opening": "가슴 쪽에 동그란 게 있어요.", "location": "몸 안이에요.", "focus": "가만히 있어요.",
                "fleshout": "색은 노랗고 작아요.", "probe_size_shape": "주먹만 해요.",
                "probe_color_brightness": None, "probe_movement": None},
    "gold": [g("size", "주먹만 해요", "layout.size", {"range": [0.05, 0.5]}),
             g("color", "노랗고", "material.color", YELLOW_EXPECT)],
    "distractors": []}]}


def test_corpus_run_uses_real_controller_flow(tmp_path):
    res = corpus_run.run_corpus(SYN, "v0", work_dir=tmp_path)
    run = res["items"][0]
    tr = run["controllerTrace"]
    assert tr["endedBy"] == "completed"
    assert "probe_size_shape" in tr["unusedReplies"]          # '작아요'로 크기 프로브를 건너뜀 → 그 답은 안 쓰임
    assert "주먹" not in run["confirmedText"]
    assert run["spec"]["meta"]["condition"] == "static"
    assert (tmp_path / "scenes" / "U01.json").exists()          # 장면 파일은 work_dir에만
    sc = score_item(SYN["items"][0], run)
    assert status_of(sc, "size")["status"] == "dropped_by_controller"
    assert status_of(sc, "color")["status"] == "reflected"


def test_corpus_run_skips_probe_without_reply(tmp_path):
    it = json.loads(json.dumps(SYN["items"][0]))
    it["replies"]["fleshout"] = "그냥 있어요."                  # 크기·색 프로브가 나온다
    it["replies"]["probe_size_shape"] = None
    run = corpus_run.run_corpus({"items": [it]}, "v0", work_dir=tmp_path)["items"][0]
    tr = run["controllerTrace"]
    assert "probe_size_shape" in tr["askedWithoutReply"]
    assert any(t.get("source") == "control:skip" for t in tr["turns"])
    assert "넘어갈게요" not in run["confirmedText"]


def test_corpus_run_mapper_is_swappable(tmp_path):
    calls = []

    def factory(rt):
        base = rt.scene_builder

        class Wrapped:
            def build(self, text, **meta):
                calls.append(text)
                return base.build(text, **meta)
        return Wrapped()

    res = corpus_run.run_corpus(SYN, factory, work_dir=tmp_path)
    assert calls == [res["items"][0]["confirmedText"]] and res["mapper"] == "factory"


def test_scoring_is_deterministic(tmp_path):
    a = fidelity.score_runs(SYN, corpus_run.run_corpus(SYN, "v0", work_dir=tmp_path / "a"))
    b = fidelity.score_runs(SYN, corpus_run.run_corpus(SYN, "v0", work_dir=tmp_path / "b"))
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)
    assert fidelity.to_markdown(a) == fidelity.to_markdown(b)
