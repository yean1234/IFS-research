"""심상 유지(표류) 판정 — AC-2 (docs/acceptance.md, docs/drift-design.md).

- 시나리오 평가: tests/fixtures/drift/drift_cases.json(독립 작성자 라벨)을 실제 컨트롤러 정적 조건 재생으로 돌린다.
- 단위: 바꿔 말하기, 색 원형 거리, 생략·덧붙임, 위치 다듬기, 움직임으로 옮김, 퍼지 일치 제외, acknowledged.
- 컨트롤러: 세션 로그 drift 기록, 회상 확인·자기보고 고정 문구(v1.1), 철회, 스키마.
대사는 모두 합성(AGENTS.md 6).
"""
import json
from pathlib import Path

import pytest

from ifs_chatbot import drift as D
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import shared

CASES = Path(__file__).parent / "fixtures" / "drift" / "drift_cases.json"


# ── 시나리오 평가 (AC-2 기준 3–6) ───────────────────────────────────────────────
@pytest.fixture(scope="module")
def case_eval():
    return D.evaluate_cases(CASES)


def test_cases_meet_label_counts():
    data = json.loads(CASES.read_text(encoding="utf-8"))
    labels = [it["label"] for it in data["items"]]
    assert len(labels) >= 12 and labels.count("drift") >= 5 and labels.count("no_drift") >= 5
    types = {it["type"] for it in data["items"] if it["label"] == "no_drift"}
    assert {"a", "b"} <= types                     # 덧붙임(a)·바꿔 말하기(b)가 no-drift에 있다


def test_case_accuracy_and_addition_only_false_positives(case_eval):
    m = case_eval["metrics"]
    print("\n" + "\n".join(f"{r['id']} label={r['label']} pred={r['predicted']} DI={r['DI']} "
                           f"identity={r['identityContradiction']} contra={r['contradicted']}" for r in case_eval["items"]))
    print(json.dumps(m, ensure_ascii=False))
    assert m["n"] >= 12
    assert m["accuracy"] >= 0.90
    assert m["additionOnlyFalsePositives"] == 0
    assert m["undecidable"] == 0


def test_acknowledged_markers_match_labels(case_eval):
    assert case_eval["metrics"]["acknowledgedAgreement"] == 1.0


def test_evaluation_is_deterministic(case_eval):
    again = D.evaluate_cases(CASES)
    a = json.dumps(case_eval, ensure_ascii=False, sort_keys=True)
    b = json.dumps(again, ensure_ascii=False, sort_keys=True)
    assert a.encode("utf-8") == b.encode("utf-8")


def test_drift_module_does_not_use_llm():
    src = Path(D.__file__).read_text(encoding="utf-8")
    assert "from .llm" not in src and "import llm" not in src and "ollama" not in src.lower()


# ── 단위 ───────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def assessor(rt):
    assert rt.drift is not None and rt.drift.builder_label == "v1"
    return rt.drift


def run(assessor, *pairs):
    turns = [{"i": k, "stage": st, "text": tx} for k, (st, tx) in enumerate(pairs)]
    return assessor.assess(turns)


@pytest.mark.parametrize("h1,h2,deg", [(0.0, 0.5, 180.0), (350 / 360, 10 / 360, 20.0), (0.1, 0.1, 0.0),
                                        (0.9, 0.1, 72.0)])
def test_hue_distance_is_circular(h1, h2, deg):
    assert D.hue_distance_deg(h1, h2) == pytest.approx(deg, abs=0.01)


def test_color_rules():
    blue, red = {"h": 215 / 360, "s": 0.7, "l": 0.5}, {"h": 0.0, "s": 0.75, "l": 0.45}
    near_red = {"h": 350 / 360, "s": 0.7, "l": 0.45}          # 0°를 넘어 10° 차이: 같은 색
    assert D.compare_color(blue, red)["verdict"] == "contradict"
    assert D.compare_color(red, near_red)["verdict"] == "agree"
    gray, bluish_gray = {"h": 0.0, "s": 0.05, "l": 0.45}, {"h": 0.569, "s": 0.2, "l": 0.495}
    assert D.compare_color(gray, bluish_gray)["verdict"] == "agree"      # 무채색 ↔ 옅은 유채색: 색상각을 보지 않음
    sky, navy = {"h": 0.556, "s": 0.49, "l": 0.85}, {"h": 0.639, "s": 0.63, "l": 0.15}
    r = D.compare_color(sky, navy)
    assert r["verdict"] == "contradict" and r["reason"] == "lightness"
    assert D.compare_color(gray, red)["verdict"] == "contradict"          # 무채색 ↔ 짙은 유채색: 채도


def test_numeric_two_tier():
    assert D.compare_numeric(0.316, 0.25)["verdict"] == "agree"        # 작은 ↔ 조그만
    assert D.compare_numeric(0.316, 0.0)["verdict"] == "agree"         # 작은 ↔ 엄지손톱만(같은 쪽, ×4 미만)
    assert D.compare_numeric(0.316, 0.621)["verdict"] == "contradict"  # 작은 ↔ 큰(중립점을 넘음)
    assert D.compare_numeric(0.0, 0.6)["verdict"] == "contradict"      # ×4 초과
    assert D.compare_numeric(0.68, 0.5)["verdict"] == "agree"          # 조금 밝은 ↔ 은은하게 밝은


def test_body_part_refinement_is_not_contradiction():
    assert D.compare_body_part("belly", "lower_belly")["verdict"] == "agree"
    assert D.compare_body_part("body", "head")["verdict"] == "agree"
    assert D.compare_body_part("chest", "solar_plexus")["verdict"] == "contradict"
    assert D.compare_layer("around", "around_behind")["verdict"] == "agree"
    assert D.compare_layer("inner", "around")["verdict"] == "contradict"


def test_identity_synonyms_and_heads(assessor):
    v = assessor.vocab
    assert D.same_identity("돌멩이", "돌", v) and D.same_identity("뭉치", "덩어리", v)
    assert D.same_identity("물방울", "방울", v) and D.same_identity("참새", "새", v)
    assert not D.same_identity("공", "막대", v) and not D.same_identity("안개", "돌", v)


def test_paraphrase_is_not_drift(assessor):
    a = run(assessor, ("find", "작은 회색 돌멩이 같은 게 있어요."), ("focus", "조그만 잿빛 돌이 있어요."),
            ("flesh_out", "잿빛이고 조그매요."))
    assert a["decision"] == "no_drift" and a["DI"] == 0.0
    assert a["primary"]["identity"]["verdict"] == "agree"


def test_omission_and_addition_are_not_compared(assessor):
    a = run(assessor, ("find", "파란 공 같은 게 있어요."), ("focus", "공이 그대로 있어요."),
            ("flesh_out", "표면이 반들반들하고 농구공만 해요."))
    assert a["decision"] == "no_drift"
    compared = {r["path"] for r in a["primary"]["slots"]}
    assert "material.color" not in compared and "layout.size" not in compared   # 생략·덧붙임


def test_identity_change_is_drift_regardless_of_di(assessor):
    a = run(assessor, ("find", "가슴에 작은 덩어리 같은 게 있어요."), ("focus", "덩어리가 가슴에 있어요."),
            ("flesh_out", "지금은 작은 새예요."))
    assert a["decision"] == "drift" and a["primary"]["identityContradiction"] is True
    assert a["acknowledged"]["flag"] is False                       # '지금은'만으로는 바뀌었다는 말이 아님


def test_negated_noun_is_not_identity(assessor):
    nouns = D.identity_nouns("이제는 공이 아니라 길쭉한 막대 모양으로 바뀌었어요.", assessor.analyzer, assessor.vocab)
    assert [n["head"] for n in nouns["nouns"]] == ["막대"]
    assert any(d["head"] == "공" and d["why"] == "negated" for d in nouns["dropped"])


def test_recall_scene_and_simile_property_nouns_are_dropped(assessor):
    nouns = D.identity_nouns("카페에서 책 읽던 장면이요. 솜처럼 폭신한 구름 같은 게 있어요.", assessor.analyzer,
                             assessor.vocab)
    assert [n["head"] for n in nouns["nouns"]] == ["구름"]


def test_stated_motion_explains_position_change(assessor):
    a = run(assessor, ("find", "배 쪽에 공기방울 같은 게 있어요."), ("focus", "공기방울이 천천히 위로 올라가요."),
            ("flesh_out", "지금은 가슴 쪽에 있어요."))
    assert a["decision"] == "no_drift"
    rows = {r["path"]: r for r in a["primary"]["slots"]}
    assert rows["body.part"]["verdict"] == "explained_by_motion"


def test_fuzzy_needs_confirmation_values_are_not_compared(assessor):
    snap = assessor.turn_snapshot({"i": 0, "stage": "flesh_out", "text": "가끔 살짝 흔들려요."})
    assert "body.part" not in snap["slots"]          # '가끔' → 가슴(퍼지 일치, 확인 필요)
    assert snap["unconfirmed"].get("body.part", {}).get("value") == "chest"


def test_acknowledged_marker_is_flagged_but_does_not_decide(assessor):
    a = run(assessor, ("find", "노란 띠 같은 게 목에 있어요."), ("focus", "노란 띠가 목에 있어요."),
            ("flesh_out", "다시 보니 이제는 노란색 그대로예요."))
    assert a["acknowledged"]["flag"] is True and a["decision"] == "no_drift"


def test_undecidable_when_nothing_restated(assessor):
    a = run(assessor, ("find", "초록색인 게 있어요."), ("flesh_out", "자두만 해요."))
    assert a["decision"] == "undecidable" and a["DI"] is None


def test_v1_failure_falls_back_to_v0_snapshot(assessor, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("일부러 낸 오류")
    monkeypatch.setattr(assessor.builder, "build", broken)
    snap = assessor.turn_snapshot({"i": 0, "stage": "find", "text": "가슴에 회색 덩어리가 있어요."})
    assert snap["builder"] == "v0" and "일부러 낸 오류" in snap["builderError"]


# ── 컨트롤러 ───────────────────────────────────────────────────────────────────
STATIC = ["주말 아침에 화분에 물 주던 장면이요. 배 쪽에 둥근 공 같은 게 있어요.", "몸 안이요. 배 가운데요.",
          "둥근 공이 있어요. 연두색이에요.", "다시 보니 이제는 공이 아니라 길쭉한 막대 모양으로 바뀌었어요."]


def _drive(s, texts):
    s.start()
    it = iter(texts)
    while s.awaiting in ("reply", "soft_check"):
        if s.awaiting == "soft_check":
            s.act("continue")
            continue
        t = next(it, None)
        s.reply(t) if t else s.act("skip")


def test_session_log_records_drift(rt):
    s = rt.new_session("static", "DRIFT01")
    _drive(s, STATIC)
    s.act("confirm")
    assert s.state == "done"
    d = s.log.data["drift"]
    assert d["enabled"] and d["assessment"]["decision"] == "drift"
    assert d["summary"]["identityContradiction"] is True and d["summary"]["acknowledged"] is True
    assert d["recallCheck"] is None and d["selfReport"] is None       # 기본 설정: 참여자에게 묻지 않음
    s.act("withdraw")
    assert s.log.data["drift"] is None


def test_session_log_with_drift_matches_schema(rt):
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", "session_log.schema.json").read_text(encoding="utf-8"))
    s = rt.new_session("static", "DRIFT02")
    _drive(s, STATIC)
    s.act("confirm")
    errors = list(Draft202012Validator(schema).iter_errors(json.loads(json.dumps(s.log.data, ensure_ascii=False))))
    assert not errors, [e.message for e in errors[:3]]


def test_drift_checks_off_when_protocol_lacks_phrases(offline_cfg, tmp_path):
    rt = Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path), "drift.self_report": True,
                                                "drift.recall_check": True}))
    assert not rt.drift_self_report and not rt.drift_recall
    assert any("self_report" in w for w in rt.warnings)


@pytest.fixture
def rt_v11(offline_cfg, tmp_path):
    return Runtime(offline_cfg.with_overrides(**{
        "session.log_dir": str(tmp_path), "interview.protocol": "elicitation_protocol.v1.1.json",
        "drift.self_report": True, "drift.recall_check": True}))


def test_recall_check_and_self_report_flow(rt_v11):
    assert rt_v11.protocol.version == "1.1.0" and rt_v11.drift_recall and rt_v11.drift_self_report
    s = rt_v11.new_session("static", "DRIFT03")
    _drive(s, STATIC)
    assert s.awaiting == "recall"
    q = s.messages[-1]["text"]
    assert q == "'공' — 지금 떠오르는 것도 그 '공'인가요?"           # 참여자가 쓴 말만 인용, 현재 시제
    assert [b["action"] for b in s.buttons()][:3] == ["recall:same", "recall:little", "recall:much"]
    s.act("recall:much")
    assert s.awaiting == "confirm"
    assert "많이 달라졌어요" not in (s.confirm_draft or "")          # 버튼 답은 확정 텍스트에 들어가지 않는다
    s.act("confirm")
    assert s.awaiting == "self_report" and len(s.buttons()) == 8
    s.act("self_report:2")
    assert s.state == "done" and s.log.data["endedBy"] == "completed"
    d = s.log.data["drift"]
    assert d["recallCheck"]["answer"] == "much" and d["recallCheck"]["x"] == "공"
    assert d["selfReport"]["value"] == 2 and d["selfReport"]["selfReportDrift"] is True
    assert d["selfReport"]["protocolVersion"] == "1.1.0"


def test_self_report_rejects_other_actions(rt_v11):
    s = rt_v11.new_session("static", "DRIFT04")
    _drive(s, STATIC)
    s.act("recall:skip")
    s.act("confirm")
    from ifs_chatbot.controller import SessionError
    with pytest.raises(SessionError):
        s.act("self_report:9")
    s.act("self_report:skip")
    assert s.log.data["drift"]["selfReport"]["value"] is None and s.state == "done"


def test_protocol_v11_phrases_are_draft_and_keep_v1(rt_v11):
    p11 = json.loads(shared("protocol", "elicitation_protocol.v1.1.json").read_text(encoding="utf-8"))
    p10 = json.loads(shared("protocol", "elicitation_protocol.v1.json").read_text(encoding="utf-8"))
    assert p10["protocolVersion"] == "1.0.0" and p11["protocolVersion"] == "1.1.0"
    assert p11["changes"][-1]["version"] == p11["protocolVersion"] and p11["changes"][-1]["status"] == "draft"
    for k in ("recall_check", "self_report_drift"):
        assert p11["fixedPhrases"][k]["status"] == "draft" and "drift-design.md" in p11["fixedPhrases"][k]["source"]
    assert {k: v for k, v in p11["fixedPhrases"].items() if k in p10["fixedPhrases"]} == p10["fixedPhrases"]
    # v1.1은 문구 2개와 driftChecks 절만 더한다: 그 밖의 절은 v1.0과 같다
    assert {k: v for k, v in p11.items() if k not in ("protocolVersion", "changes", "driftChecks", "fixedPhrases")} \
        == {k: v for k, v in p10.items() if k not in ("protocolVersion", "fixedPhrases")}
    banned = ("왜", "기억", "과거", "이유", "예전", "옛날", "어릴", "치료", "내담자", "진단", "상담", "증상")
    for k in ("recall_check", "self_report_drift"):
        ph = p11["fixedPhrases"][k]
        texts = [ph["text"]] + [o["label"] for o in ph.get("options") or []] + list((ph.get("scale") or {}).get("anchors", {}).values())
        assert not any(w in t for w in banned for t in texts), k
    assert not any(w in p11["fixedPhrases"]["recall_check"]["text"] for w in ("처음", "아까", "원래"))  # 지금 떠오르는 것만 묻는다


def test_drift_log_with_recall_and_self_report_matches_schema(rt_v11):
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", "session_log.schema.json").read_text(encoding="utf-8"))
    s = rt_v11.new_session("static", "DRIFT05")
    _drive(s, STATIC)
    s.act("recall:little")
    s.act("confirm")
    s.act("self_report:5")
    d = s.log.data["drift"]
    assert d["recallCheck"]["asked"] and d["selfReport"]["value"] == 5 and d["assessment"]["decision"] == "drift"
    errors = list(Draft202012Validator(schema).iter_errors(json.loads(json.dumps(s.log.data, ensure_ascii=False))))
    assert not errors, [e.message for e in errors[:3]]


# ── 문서 세 곳의 수치가 PARAMS와 같은지 (drift.py · drift-design.md · research-design.md 4.5) ──────
def _g(x) -> str:
    return f"{x:g}"


def test_docs_match_params():
    P = D.PARAMS
    root = Path(__file__).resolve().parents[2] / "docs"
    design = (root / "drift-design.md").read_text(encoding="utf-8")
    rd = (root / "research-design.md").read_text(encoding="utf-8")
    sec = rd.split("### 4.5", 1)[1].split("\n### ", 1)[0]
    lo, hi = P["chromaticL"]
    w = P["groupWeights"]
    for s in (f"τ_soft = {_g(P['tauNumSoft'])}", f"τ_hard = {_g(P['tauNumHard'])}", f"τ_hue = {_g(P['tauHueDeg'])}°",
              f"τ_l = {_g(P['tauL'])}", f"τ_s = {_g(P['tauS'])}", f"s ≥ {_g(P['chromaticMinS'])}",
              f"{_g(lo)} < l < {_g(hi)}", f"θ = {_g(P['theta'])}", f"value ≤ {P['selfReportDriftMax']}",
              D.DRIFT_VERSION, D.PARAMS_VERSION, "·".join(P["translationalMotion"])):
        assert s in design, s
    for g, label in (("identity", "정체 identity"), ("color", "색 color"), ("size", "크기 size"),
                     ("position", "위치 position"), ("shape", "자세 shape"), ("surface", "표면 surface")):
        assert any(line.startswith(f"| {label} |") and f"| {_g(w[g])} |" in line for line in design.splitlines()), g
    assert any(line.startswith("| 움직임 motion |") and f"| **{_g(w['motion'])}** |" in line for line in design.splitlines())
    for s in (f"`|Δ| > {_g(P['tauNumHard'])}`", f"`|Δ| > {_g(P['tauNumSoft'])}`", f"`> {_g(P['tauHueDeg'])}°`",
              f"`|Δl| > {_g(P['tauL'])}`", f"`|Δs| > {_g(P['tauS'])}`", f"`s ≥ {_g(P['chromaticMinS'])}`",
              f"`{_g(lo)} < l < {_g(hi)}`", f"`DI ≥ {_g(P['theta'])}`", f"자기보고 ≤ {P['selfReportDriftMax']}",
              f"정체·색·크기·위치 {_g(w['identity'])}, 자세·표면 {_g(w['shape'])}, 움직임 {_g(w['motion'])}",
              D.DRIFT_VERSION, D.PARAMS_VERSION):
        assert s in sec, s
    assert w["identity"] == w["color"] == w["size"] == w["position"] and w["shape"] == w["surface"]
