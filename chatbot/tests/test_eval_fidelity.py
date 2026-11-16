"""일치도 채점 규칙(ifs_chatbot.eval.fidelity)과 코퍼스 재생(corpus_run) 테스트.
대사는 모두 합성(AGENTS.md 6). spec은 채점 규칙만 보려고 손으로 만든 작은 가짜다."""
import json
from pathlib import Path

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
    # 근거 기준: color는 경로가 정답에 있으나 근거('파란')가 정답 구간('노란') 밖 → 근거 없는 값
    assert {u["path"]: u["reason"] for u in sc["unsupported"]} == {
        "material.brightness": "no_gold_span", "layout.size": "no_gold_span", "material.color": "outside_gold_span"}
    summ = aggregate([sc])["overall"]
    assert summ["negationErrors"] == 1 and summ["contamination"] == 2 and summ["spuriousValues"] == 2
    assert summ["unsupportedValues"] == 3 and summ["unsupportedRate"] == 1.0


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


# ── CP1 반영: 색 null 구성요소, expect 형식 검사 ─────────────────────────────
DEV = Path(__file__).parent / "fixtures" / "imagery_corpus" / "dev.json"


def test_satisfies_skips_null_color_components():
    assert satisfies(YELLOW, {"hue_deg": [40, 70], "s": None, "l": None})
    assert satisfies(YELLOW, {"hue_deg": None, "s": [0.4, 1.0]})
    assert not satisfies(BLUE, {"hue_deg": [40, 70], "l": None})
    assert satisfies({"h": 0.0, "s": 0.05, "l": 0.5}, {"hue_deg": None, "s": [0.0, 0.2], "l": [0.3, 0.7]})


def test_check_expect_accepts_valid_forms():
    ok = [({"equals": None}, "material.color"), ({"equals": "chest"}, "body.part"), ({"in": ["still"]}, "motion.type"),
          ({"range": [0.0, 0.35]}, "layout.size"), (YELLOW_EXPECT, "material.color"),
          ({"hue_deg": [345, 15]}, "material.color"), ({"hue_deg": None, "s": [0.0, 0.2]}, "material.color"),
          (None, "layout.size")]
    for expect, slot in ok:
        assert fidelity.check_expect(expect, slot) == ([], []), (expect, slot)


def test_check_expect_rejects_bad_forms():
    bad = [({"equals": "chests"}, "body.part"), ({"in": []}, "motion.type"), ({"in": ["still", None]}, "motion.type"),
           ({"in": [0.3]}, "layout.size"), ({"range": [0.5, 0.2]}, "layout.size"), ({"range": [0, 1.5]}, "layout.size"),
           ({"range": [0.1, 0.2]}, "body.layer"), ({"hue_deg": [40, 400]}, "material.color"),
           ({"s": [0.9, 0.1]}, "material.color"), ({"s": 0.5}, "material.color"), ({"hue_deg": [40, 70]}, "layout.size"),
           ({"approx": 0.5}, "layout.size"), ({}, "layout.size"), ({"equals": {"h": 0.1}}, "material.color")]
    for expect, slot in bad:
        errs, _ = fidelity.check_expect(expect, slot)
        assert errs, (expect, slot)


def test_check_expect_warns_on_vacuous_color():
    errs, warns = fidelity.check_expect({"hue_deg": None, "s": None, "l": None}, "material.color")
    assert errs == [] and warns


def test_dev_corpus_expect_format_is_valid():
    """dev 코퍼스 전체 정답의 expect가 형식에 맞고, 모든 expect로 채점이 예외 없이 돈다(held-out은 여기서 열지 않음)."""
    corpus = json.loads(DEV.read_text(encoding="utf-8"))
    chk = fidelity.check_corpus(corpus)
    assert chk["errors"] == [] and chk["items"] == 30
    sample = {"color": {"h": 0.1, "s": 0.5, "l": 0.5}, "numeric": 0.5}
    for it in corpus["items"]:
        for gl in it["gold"]:
            if fidelity.kind_of(gl) != "slot":
                continue
            kind, enum = fidelity.slot_kind(gl["slot"])
            value = enum[0] if kind == "categorical" else sample[kind]
            assert isinstance(satisfies(value, gl["expect"]), bool)
            assert isinstance(satisfies(None, gl["expect"]), bool)


def test_check_corpus_reports_without_phrase_text():
    secret = "비밀스러운 합성 문장"
    corpus = {"items": [{"id": "X1", "replies": {"opening": secret},
                         "gold": [g("color", secret, "material.color", {"hue_deg": [40, 400]}),
                                  g("size", "없는 구절", "layout.size", {"range": [0.1, 0.2]})]}]}
    chk = fidelity.check_corpus(corpus)
    assert len(chk["errors"]) == 1 and len(chk["warnings"]) == 1        # hue 범위 오류, phrase_missing 경고
    assert all(secret not in m and "없는 구절" not in m for m in chk["errors"] + chk["warnings"])


def test_check_corpus_cli_exit_code(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(SYN, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        fidelity.main(["--check-corpus", str(good)])
    assert e.value.code == 0
    bad = json.loads(json.dumps(SYN))
    bad["items"][0]["gold"][0]["expect"] = {"range": [0.9, 0.1]}
    (tmp_path / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        fidelity.main(["--check-corpus", str(tmp_path / "bad.json")])
    assert e.value.code == 1 and "오류" in capsys.readouterr().out


def test_evaluate_refuses_malformed_corpus():
    bad = json.loads(json.dumps(SYN))
    bad["items"][0]["gold"][0]["expect"] = {"range": [0.9, 0.1]}
    with pytest.raises(ValueError):
        fidelity.evaluate(bad, "v0")


# ── CP1 반영: 근거 기준 근거 없는 값(unsupported) ─────────────────────────────
def test_unsupported_reasons():
    gold = [g("color", "노란", "material.color", YELLOW_EXPECT),
            g("size", "주먹만 해요", "layout.size", {"range": [0.05, 0.5]})]
    it = item(gold, replies={"opening": TEXT, "probe_size_shape": "주먹만 해요."})
    supported = blank_spec(**{"material.color": (YELLOW, [span_of("노란")])})
    assert score_item(it, {"confirmedText": TEXT, "spec": supported})["unsupported"] == []
    # 정답 경로는 있으나 phrase가 확정 텍스트에 없음(컨트롤러 탈락) → 경로 기준으로는 통과, 근거 기준으로는 근거 없음
    dropped = blank_spec(**{"layout.size": (0.3, [span_of("공이")])})
    sc = score_item(it, {"confirmedText": TEXT, "spec": dropped})
    assert sc["spurious"] == []
    assert [(u["path"], u["reason"], u["spurious"]) for u in sc["unsupported"]] == [("layout.size", "no_gold_span", False)]
    # 근거 구간이 없는 값
    no_ev = blank_spec(**{"material.color": (YELLOW, [])})
    u = score_item(it, {"confirmedText": TEXT, "spec": no_ev})["unsupported"]
    assert [(x["reason"], x["valueMatchesGold"]) for x in u] == [("no_evidence", True)]


def test_unsupported_counts_correct_value_from_unlabelled_mention():
    text = "노란 공이에요. 노란 빛이 나요."
    gold = [g("color", "노란 공", "material.color", YELLOW_EXPECT)]
    s = find_spans(text, "노란")[1]
    spec = blank_spec()
    spec["material"]["color"] = YELLOW
    spec["_provenance"]["material.color"] = [{"trigger": "노란", "charSpan": list(s)}]
    sc = score_item(item(gold, replies={"opening": text}), {"confirmedText": text, "spec": spec})
    assert status_of(sc, "color")["status"] == "reflected"
    assert sc["unsupported"][0]["reason"] == "outside_gold_span" and sc["unsupported"][0]["valueMatchesGold"]
    assert aggregate([sc], B=10)["overall"]["unsupportedValueMatchesGold"] == 1


# ── CP1 반영: 항목 단위 군집 부트스트랩, 쌍 비교, 구간 폭 ─────────────────────
def _scored_items(n_ok: int, n_bad: int) -> list[dict]:
    gold = [g("color", "노란", "material.color", YELLOW_EXPECT)]
    ok = blank_spec(**{"material.color": (YELLOW, [span_of("노란")])})
    bad = blank_spec(**{"material.color": (BLUE, [span_of("파란")])})
    out = [score_item(item(gold, iid=f"T{k:02d}"), {"confirmedText": TEXT, "spec": ok}) for k in range(n_ok)]
    out += [score_item(item(gold, iid=f"T{n_ok + k:02d}"), {"confirmedText": TEXT, "spec": bad}) for k in range(n_bad)]
    return out


def test_summary_rates_equal_pooled_item_counts():
    scored = _scored_items(3, 2)
    summ = aggregate(scored, B=50)["overall"]
    tot = {k: sum(fidelity.item_counts(i)[k] for i in scored) for k in fidelity.item_counts(scored[0])}
    for m, (num, den) in fidelity.METRICS.items():
        assert summ[m] == (round(tot[num] / tot[den], 4) if tot[den] else None), m


def test_cluster_bootstrap_is_deterministic_and_brackets_estimate():
    scored = _scored_items(6, 4)
    a = fidelity.bootstrap_ci(scored, B=400, seed=7)
    assert a == fidelity.bootstrap_ci(scored, B=400, seed=7)
    assert a["unit"] == "item" and a["nItems"] == 10
    r = a["metrics"]["reflectRate"]
    assert r["estimate"] == 0.6 and r["lo"] <= 0.6 <= r["hi"] and r["lo"] < r["hi"] and r["replicates"] == 400
    same = fidelity.bootstrap_ci(_scored_items(5, 0), B=100)["metrics"]["reflectRate"]
    assert same["lo"] == same["hi"] == same["estimate"] == 1.0           # 모든 항목이 같으면 구간 폭 0


def test_paired_compare_item_level():
    a = {"corpusId": "unit", "mapper": "A", "items": _scored_items(2, 3)}
    b = {"corpusId": "unit", "mapper": "B", "items": _scored_items(4, 1)}
    cmp = fidelity.paired_compare(a, b, B=300, seed=1)
    m = cmp["metrics"]["reflectRate"]
    assert (m["a"], m["b"], m["diff"]) == (0.4, 0.8, 0.4) and m["lo"] <= 0.4 <= m["hi"]
    assert cmp["attributePairs"] == {"both": 2, "onlyA": 0, "onlyB": 2, "neither": 1}
    assert cmp["itemSigns"]["reflected"] == {"b_more": 2, "equal": 3, "b_fewer": 0}
    assert cmp == fidelity.paired_compare(a, b, B=300, seed=1)
    assert "| T02 |" in fidelity.paired_markdown(cmp)
    with pytest.raises(ValueError):
        fidelity.paired_compare(a, {"items": _scored_items(4, 0)}, B=10)


def test_expect_widths():
    gold = [g("color", "노란", "material.color", {"hue_deg": [345, 15], "s": [0.4, 1.0]}),
            g("size", "공이", "layout.size", {"range": [0.1, 0.4]}),
            g("texture_roughness", "오돌토돌해요", "material.roughness", {"range": [0.6, 1.0]}),
            g("motion_type", "벽 앞", "motion.type", {"in": ["still", "floating"]})]
    spec = blank_spec(**{"layout.size": (0.2, [span_of("공이")])})
    ew = aggregate([score_item(item(gold), {"confirmedText": TEXT, "spec": spec})], B=10)["expectWidths"]
    assert ew["hueWidthDeg"]["max"] == 30.0 and ew["sWidth"]["max"] == 0.6
    assert ew["rangeWidth"]["n"] == 2 and ew["rangeWidth"]["median"] == 0.35
    assert ew["byType"]["range"] == {"n": 2, "reflected": 1, "reflectRate": 0.5}
    assert ew["rangeReflectByWidth"]["atOrBelowMedian"]["reflected"] == 1
    assert ew["inListLength"]["max"] == 2.0


# ── 2단계 독립 검토(T3) 반영: 절 색인 분리, 퍼지 경로 값, 매핑 대체, 크기 구간 옥타브 ──────────
def test_t3_g1_clause_index_alone_is_not_attribute_preservation():
    """T3-G1: _clauses(절 색인)로만 덮인 속성은 보존이 아니라 lost(clauseIndexOnly)로 따로 센다."""
    gold = [g("texture_roughness", "오돌토돌해요", "material.roughness", {"range": [0.6, 1.0]}),
            g("color", "노란", "material.color", YELLOW_EXPECT)]
    spec = blank_spec()
    spec["_clauses"] = [{"charSpan": [0, len(TEXT)], "text": TEXT, "usedFor": [], "status": "unused"}]
    sc = score_item(item(gold), {"confirmedText": TEXT, "spec": spec})
    a = status_of(sc, "texture_roughness")
    assert a["status"] == "lost" and a["clauseIndexOnly"] and not a["verbatimPreserved"] and a["verbatimWithClauseIndex"]
    summ = aggregate([sc], B=10)["overall"]
    assert summ["lostRate"] == 1.0 and summ["lostClauseIndexOnly"] == 2
    assert summ["unreflectedVerbatimRate"] == 0.0 and summ["unreflectedVerbatimRateWithClauseIndex"] == 1.0
    s, e = span_of("노란")                                  # 속성 단위 보존 필드에 있으면 보존
    spec["_unmatched"] = [{"lemma": "노랗", "tag": "VA", "surface": TEXT[s:e], "charSpan": [s, e]}]
    b = status_of(score_item(item(gold), {"confirmedText": TEXT, "spec": spec}), "color")
    assert b["status"] == "preserved" and not b["clauseIndexOnly"]


def test_t3_g2_fuzzy_path_values_are_counted():
    """T3-G2: 퍼지 일치 근거로 슬롯에 들어간 값은 정답이 없어도 fuzzyValues로 센다."""
    gold = [g("color", "노란", "material.color", YELLOW_EXPECT)]
    spec = blank_spec(**{"material.color": (YELLOW, [span_of("노란")]),
                         "material.saturation": (0.9, [span_of("표면은")])})
    spec["_provenance"]["material.saturation"][0].update(source="fuzzy_lexicon", needsConfirmation=True)
    sc = score_item(item(gold), {"confirmedText": TEXT, "spec": spec})
    assert [f["path"] for f in sc["fuzzyValues"]] == ["material.saturation"]
    summ = aggregate([sc], B=10)["overall"]
    assert summ["fuzzyValues"] == 1 and summ["fuzzyValueRate"] == 0.5 and summ["reflectRate"] == 1.0
    assert any(f["type"] == "fuzzy_value" for f in fidelity.failures([sc], {}))


def test_t3_g3_fallback_is_counted_and_warned(tmp_path):
    """T3-G3: 요청한 매핑이 예외로 v0에 대체되면 corpus_run·채점 요약에 건수·id가 남고 리포트 머리에 경고가 나온다."""
    from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1

    class Broken(SceneSpecBuilderV1):
        def build(self, text, **meta):
            raise RuntimeError("일부러 낸 오류")

    runs = corpus_run.run_corpus(SYN, lambda rt: Broken(rt.analyzer), work_dir=tmp_path)
    assert runs["mappingFallback"] == {"count": 1, "ids": ["U01"]}
    rep = fidelity.score_runs(SYN, runs, B=10)
    assert rep["summary"]["mappingFallback"]["ids"] == ["U01"]
    md = fidelity.to_markdown(rep)
    assert "경고" in md.split("## 전체")[0] and "U01" in md.split("## 전체")[0]
    ok = fidelity.score_runs(SYN, corpus_run.run_corpus(SYN, "v1", work_dir=tmp_path / "ok"), B=10)
    assert ok["summary"]["mappingFallback"]["count"] == 0 and "경고" not in fidelity.to_markdown(ok).split("## 전체")[0]


def test_t3_f7_size_range_width_in_octaves():
    gold = [g("size", "공이", "layout.size", {"range": [0.05, 0.5]})]
    ew = aggregate([score_item(item(gold), {"confirmedText": TEXT, "spec": blank_spec()})], B=10)["expectWidths"]
    so = ew["sizeRangeOctavesV1"]
    assert so["octavesPerUnit"] == 6.0 and so["octaves"]["median"] == 2.7 and so["ratio"]["median"] == round(2 ** 2.7, 2)


def test_compare_writes_paired_outputs(tmp_path):
    def factory(rt):
        return rt.scene_builder
    res = fidelity.compare(SYN, "v0", factory, tmp_path, B=50)
    assert res["paired"]["metrics"]["reflectRate"]["diff"] == 0.0 and res["paired"]["sameSlotValuesItems"] == 1
    for f in ("report.json", "paired.json", "paired.md", "compare/report.json", "compare/runs.json"):
        assert (tmp_path / f).exists(), f
