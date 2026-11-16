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
    assert D.same_identity("물방울", "방울", v) and D.same_identity("공기방울", "방울", v)
    assert not D.same_identity("공", "막대", v) and not D.same_identity("안개", "돌", v)
    # T2-F07: 한 음절 겹침은 오른쪽 머리로 보지 않는다(불꽃 ⊅ 꽃). 그 대가로 참새 ⊃ 새도 같은 정체가 아니다(9절 한계)
    assert not D.same_identity("불꽃", "꽃", v) and not D.same_identity("참새", "새", v)


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
    # 매핑 v1.1부터 퍼지 후보는 슬롯 값이 아니라 _alternatives(reason needs_confirmation)에만 있다
    assert snap["unconfirmed"].get("body.part", {}).get("value") == "chest"
    assert snap["unconfirmed"]["body.part"]["trigger"] == "가끔"


# ── 검토 T2 지적 회귀 (합성 문장. 규칙을 고친 뒤 통과시킨 것이라 AC-2 독립 평가가 아니다) ─────────
def test_t2_f01_change_inside_find_is_first_said_value(assessor):
    # 검토 T03/W1: Find 안에서 파랑 → 빨강. S_first는 슬롯마다 처음 말한 값(파랑)
    a = run(assessor, ("find", "파란 공 같은 게 떠올라요."), ("find", "몸 안이요. 배에 빨간 공이 있어요."),
            ("focus", "빨간 공이 배에 있어요."), ("flesh_out", "빨갛고 동그래요."))
    assert a["decision"] == "drift"
    row = {r["path"]: r for r in a["primary"]["slots"]}["material.color"]
    assert row["verdict"] == "contradict" and row["fromTurn"] == 0
    assert a["firstSnapshot"]["source"]["material.color"]["i"] == 0


def test_t2_f02_simile_modifier_and_material_are_not_identity(assessor):
    n = D.identity_nouns("가슴에 구름 같은 덩어리가 있어요.", assessor.analyzer, assessor.vocab)
    assert [x["head"] for x in n["nouns"]] == ["덩어리"]
    assert any(d["head"] == "구름" and d["why"] == "simile_modifier" for d in n["dropped"])
    n = D.identity_nouns("고무로 돼 있어요. 말랑해요.", assessor.analyzer, assessor.vocab)
    assert n["nouns"] == [] and n["dropped"][0]["why"] == "material"
    n = D.identity_nouns("유리로 만들어졌어요.", assessor.analyzer, assessor.vocab)
    assert n["nouns"] == [] and n["dropped"][0]["why"] == "material"
    # 'X로 바뀌었어요'는 그대로 변화 자리
    n = D.identity_nouns("이제는 막대로 바뀌었어요.", assessor.analyzer, assessor.vocab)
    assert [(x["head"], x["position"]) for x in n["nouns"]] == [("막대", "change")]
    # 'X 같은 게'·'X 같은 느낌'(일반어)은 이름 자리 그대로
    n = D.identity_nouns("하얀 솜 같은 게 있어요.", assessor.analyzer, assessor.vocab)
    assert [(x["head"], x["position"]) for x in n["nouns"]] == [("솜", "simile_name")]
    for turns in ((("find", "가슴에 구름 같은 덩어리가 있어요."), ("focus", "덩어리가 가슴에 있어요."),
                   ("flesh_out", "덩어리가 말랑해요.")),
                  (("find", "가슴에 공 같은 게 있어요."), ("focus", "공이 가슴에 있어요."),
                   ("flesh_out", "고무로 돼 있어요. 말랑해요."))):
        a = run(assessor, *turns)
        assert a["decision"] == "no_drift" and a["primary"]["identity"]["verdict"] == "agree", turns


def test_t2_f02_mass_head_compound_keeps_its_substance(assessor):
    v = assessor.vocab
    a = run(assessor, ("find", "배 쪽에 하얀 솜 같은 게 있어요."), ("focus", "솜이 그대로 있어요."),
            ("flesh_out", "하얀 솜뭉치예요. 폭신해요."))
    assert a["decision"] == "no_drift" and a["primary"]["identity"]["verdict"] == "agree"
    n = D.identity_nouns("커다란 털실 뭉치 같은 게 있어요.", assessor.analyzer, v)["nouns"]
    assert n[0]["head"] == "뭉치" and n[0]["massOf"] == "털실"
    rec = lambda h, m=None: {"head": h, **({"massOf": m} if m else {})}   # noqa: E731
    assert D.identity_match(rec("덩어리"), rec("돌덩어리"), v)                   # 덩이 → 돌덩이: 덧붙임
    assert not D.identity_match(rec("덩어리", "구름"), rec("덩어리", "돌"), v)    # 구름 덩어리 ≠ 돌 덩어리
    assert D.identity_match(rec("뭉치", "털실"), rec("덩어리", "털실"), v)


def test_t2_f03_motion_only_in_first_turn_or_wrong_direction_does_not_excuse(assessor):
    a = run(assessor, ("find", "발밑에 원판 같은 게 천천히 움직여요."), ("focus", "원판이 머리 위에 있어요."),
            ("flesh_out", "머리 위에 가만히 있어요."))                      # 검토 S16/W2: 움직임은 첫 턴에만
    assert a["decision"] == "drift"
    rows = {r["path"]: r for r in a["primary"]["slots"]}
    assert rows["layout.verticalOffset"]["verdict"] == "contradict"
    a = run(assessor, ("find", "발밑에 납작한 원판 같은 게 있어요."),
            ("focus", "원판이 머리 위에 있어요. 천천히 가라앉아요."), ("flesh_out", "머리 위에 있어요."))   # 검토 S15
    assert a["decision"] == "drift"                                        # 가라앉음(아래) ≠ 위로 옮김
    assert {r["path"]: r for r in a["primary"]["slots"]}["layout.verticalOffset"]["verdict"] == "contradict"


def test_t2_f04_size_word_vs_measure_uses_hard_threshold_only(assessor):
    for turns in ((("find", "배에 큰 덩어리 같은 게 있어요."), ("focus", "덩어리가 배에 있어요."),
                   ("flesh_out", "주먹만 해요.")),
                  (("find", "가슴에 커다란 공 같은 게 있어요."), ("focus", "공이 가슴에 있어요."),
                   ("flesh_out", "주먹만 해요. 커다래요."))):
        a = run(assessor, *turns)
        row = {r["path"]: r for r in a["primary"]["slots"]}["layout.size"]
        assert a["decision"] == "no_drift" and row["verdict"] == "agree", turns
        assert row["scales"] == ["word", "measure"]
    # 같은 척도끼리는 그대로 중립점 규칙
    assert D.compare_slot("layout.size", 0.316, 0.621, scales=("word", "word"))["verdict"] == "contradict"
    assert D.compare_slot("layout.size", 0.316, 0.621, scales=("word", "measure"))["verdict"] == "agree"


def test_t2_f05_multiple_objects_are_flagged(assessor):
    a = run(assessor, ("find", "가슴에 작은 공 같은 게 있고, 배에는 막대 같은 게 있어요."),
            ("focus", "공이 가슴에 있어요."), ("flesh_out", "막대는 배에 있어요. 공은 그대로예요."))
    assert a["multipleObjects"]["flag"] is True and a["multipleObjects"]["turns"][0]["heads"] == ["공", "막대"]
    assert D.summarize(a)["multipleObjects"] is True
    # 판정은 바꾸지 않았다(절 단위 대상 연결은 보류): 서로 다른 대상의 부위가 비교되어 drift로 남는다
    assert a["decision"] == "drift"


def test_t2_f06_clarify_answers_do_not_set_identity(assessor):
    a = run(assessor, ("find", "가슴에 덩어리 같은 게 있어요."), ("focus", "덩어리가 그대로 있어요."),
            ("flesh_out", "주먹만 해요."), ("clarify", "젤리 같은 거요."))
    assert a["decision"] == "no_drift" and a["primary"]["identity"]["to"] == ["덩어리"]
    clar = [t for t in a["turns"] if t["stage"] == "clarify"][0]
    assert clar["identity"] == [] and clar["identityDropped"][0]["why"] == "clarify_answer"


def test_t2_f07_single_syllable_overlap_is_not_same_identity(assessor):
    a = run(assessor, ("find", "가슴에 작은 꽃 같은 게 있어요."), ("focus", "꽃이 가슴에 있어요."),
            ("flesh_out", "불꽃이에요. 활활 타요."))
    assert a["decision"] == "drift" and a["primary"]["identityContradiction"] is True


def test_t2_f08_recall_anchor_only_from_naming_positions(assessor):
    tt = lambda *xs: [{"i": k, "stage": st, "text": tx} for k, (st, tx) in enumerate(xs)]   # noqa: E731
    assert assessor.recall_anchor(tt(("find", "가슴에 구름 같은 덩어리가 있어요."), ("focus", "덩어리가 있어요."))) is None
    assert assessor.recall_anchor(tt(("find", "가슴에 뭔가 있어요. 유리로 돼 있어요."), ("focus", "그대로예요."))) is None
    assert assessor.recall_anchor(tt(("find", "덩어리가 있어요."), ("focus", "덩어리예요."))) is None   # 주어 자리만
    assert assessor.recall_anchor(tt(("find", "배 쪽에 둥근 공 같은 게 있어요."),))["x"] == "공"
    assert assessor.recall_anchor(tt(("find", "작은 돌멩이예요."),))["x"] == "돌멩이"


def test_t2_f10_negated_change_marker_is_not_acknowledged(assessor):
    a = run(assessor, ("find", "가슴에 파란 공 같은 게 있어요."), ("focus", "공이 그대로예요. 바뀐 건 없어요."),
            ("flesh_out", "달라진 게 없어요. 파래요."))
    assert a["acknowledged"]["flag"] is False
    assert [m["match"] for m in a["acknowledged"]["negatedMarkers"]] == ["바뀐", "달라진"]
    a = run(assessor, ("find", "가슴에 파란 공 같은 게 있어요."), ("focus", "공이 있어요."),
            ("flesh_out", "색이 바뀌었는데 지금은 안 움직여요."))              # 부정이 다음 절에 있음: 표지 유지
    assert a["acknowledged"]["flag"] is True


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


def test_summary_comparable_is_primary_groups(rt):
    """CP2 #4: 1차 쌍에서 비교 가능했던 묶음은 summary.comparable(이름 목록)과 assessment.primary.groups에 있다.
    묶음이 하나뿐이면 그 하나의 모순으로 DI = 1이 된다(drift-design 9절 한계)."""
    s = rt.new_session("static", "DRIFT14")
    _drive(s, STATIC)
    s.act("confirm")
    d = s.log.data["drift"]
    groups = d["assessment"]["primary"]["groups"]
    assert d["summary"]["comparable"] == [g["group"] for g in groups]
    if len(groups) == 1 and groups[0]["verdict"] == "contradict":
        assert d["summary"]["DI"] == 1.0


def test_drift_checks_off_when_protocol_lacks_phrases(offline_cfg, tmp_path):
    rt = Runtime(offline_cfg.with_overrides(**{"session.log_dir": str(tmp_path), "drift.self_report": True,
                                                "drift.recall_check": True}))
    assert not rt.drift_self_report and not rt.drift_recall
    assert any("self_report" in w for w in rt.warnings)


@pytest.fixture
def rt_v11(offline_cfg, tmp_path):
    # v1.1 문구는 status = draft라 allow_draft_phrases = true를 따로 줘야 켜진다(Codex CP2 #12)
    return Runtime(offline_cfg.with_overrides(**{
        "session.log_dir": str(tmp_path), "interview.protocol": "elicitation_protocol.v1.1.json",
        "drift.self_report": True, "drift.recall_check": True, "drift.allow_draft_phrases": True}))


def test_draft_phrases_off_by_default_with_warning(offline_cfg, tmp_path):
    """CP2 #12: 문구가 draft이고 allow_draft_phrases = false면 recall_check·self_report를 켜도 끄고 경고한다."""
    assert offline_cfg.drift.allow_draft_phrases is False                    # default.toml 기본값
    rt = Runtime(offline_cfg.with_overrides(**{
        "session.log_dir": str(tmp_path), "interview.protocol": "elicitation_protocol.v1.1.json",
        "drift.self_report": True, "drift.recall_check": True}))
    assert rt.protocol.phrase_meta("recall_check")["status"] == "draft"
    assert not rt.drift_recall and not rt.drift_self_report
    for flag in ("recall_check", "self_report"):
        assert any(f"[drift] {flag}" in w and "draft" in w and "allow_draft_phrases" in w for w in rt.warnings), flag
    assert rt.info()["drift"]["recallCheck"] is False and rt.info()["drift"]["allowDraftPhrases"] is False
    s = rt.new_session("static", "DRAFT01")                                  # 회상 확인·자기보고 없이 끝난다
    _drive(s, STATIC)
    assert s.awaiting == "confirm"
    assert not any(m.get("source") in ("fixed:recall_check", "fixed:self_report_drift") for m in s.messages)
    s.act("confirm")
    assert s.state == "done" and s.log.data["drift"]["selfReport"] is None


def test_draft_phrases_on_when_allowed(rt_v11):
    """CP2 #12: allow_draft_phrases = true면 지금처럼 켜지고 draft 경고가 없다."""
    assert rt_v11.drift_recall and rt_v11.drift_self_report
    assert not any("status = draft" in w for w in rt_v11.warnings)
    assert rt_v11.info()["drift"]["allowDraftPhrases"] is True


def test_draft_gate_keys_in_both_configs():
    from ifs_chatbot.config import load_config
    for name in ("default", "pilot"):
        cfg = load_config(name)
        assert cfg.drift.allow_draft_phrases is False, name


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


def _schema_errors(s):
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", "session_log.schema.json").read_text(encoding="utf-8"))
    return [e.message for e in Draft202012Validator(schema).iter_errors(
        json.loads(json.dumps(s.log.data, ensure_ascii=False)))][:3]


@pytest.mark.parametrize("texts", [["가슴에 구름 같은 덩어리가 있어요.", "몸 안이요.", "덩어리가 있어요.", "말랑해요."],
                                   ["가슴에 뭔가 있어요. 유리로 돼 있어요.", "몸 안이요.", "그대로예요.", "말랑해요."]])
def test_t2_f08_recall_check_does_not_quote_simile_or_material(rt_v11, texts):
    s = rt_v11.new_session("static", "DRIFT08")
    _drive(s, texts)
    assert s.awaiting == "confirm"                                   # 묻지 않고 확정 요약으로
    rc = s.log.data["drift"]["recallCheck"]
    assert rc["asked"] is False and "x" not in rc
    assert not any(m.get("source") == "fixed:recall_check" for m in s.messages)


def test_t2_f09_confirmation_edited_is_in_summary(rt):
    s = rt.new_session("static", "DRIFT09")
    _drive(s, ["배 쪽에 파란 공 같은 게 있어요.", "몸 안이요. 배 가운데요.", "파란 공이 있어요.", "파랗고 동그래요."])
    s.act("edit", "머리 위에 빨간 막대가 있어요.")
    summ = s.log.data["drift"]["summary"]
    assert summ["confirmationEdited"] is True and summ["decision"] == "no_drift"   # 판정은 턴으로만 한다


def test_t2_f12_stop_while_recall_or_self_report_keeps_keys(rt_v11):
    s = rt_v11.new_session("static", "DRIFT12A")
    _drive(s, STATIC)
    assert s.awaiting == "recall"
    s.act("stop")
    rc = s.log.data["drift"]["recallCheck"]
    assert rc["asked"] is True and rc["x"] == "공" and rc["answer"] is None and rc["skipped"] == "stop"
    assert not _schema_errors(s)
    s = rt_v11.new_session("static", "DRIFT12B")
    _drive(s, STATIC)
    s.act("recall:same")
    s.act("confirm")
    assert s.awaiting == "self_report"
    s.act("stop")
    sr = s.log.data["drift"]["selfReport"]
    assert sr["asked"] is True and sr["questionTurn"] is not None and sr["protocolVersion"] == "1.1.0"
    assert sr["value"] is None and sr["skipped"] == "stop"
    assert s.log.data["endedBy"] == "participant_stop" and not _schema_errors(s)


def test_withdrawn_log_matches_schema(rt):
    s = rt.new_session("static", "DRIFT13")
    _drive(s, STATIC)
    s.act("confirm")
    s.act("withdraw")
    assert s.log.data["endedBy"] == "withdrawn"                   # 컨트롤러가 실제로 쓰는 값
    assert not _schema_errors(s)


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
    # 규칙 정의(움직임 방향, 크기 출처)도 세 곳이 같아야 한다
    design3 = design.split("\n## 3. ", 1)[1].split("\n## ", 1)[0]          # 설계 문서 3절(규칙 표)에서만 찾는다
    direction = D.motion_direction_text(P)
    assert direction in design3 and direction in sec
    assert P["sizeCrossScale"] == "hard_only"
    for text in (design3, sec):
        assert "크기 출처" in text and "τ_hard만" in text
    assert w["identity"] == w["color"] == w["size"] == w["position"] and w["shape"] == w["surface"]
