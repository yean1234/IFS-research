"""G83: G82(LLM 형태 이름)를 실험 설정에서 켜기 전에 실제 흐름 점검(docs/validation/run-g82-end-to-end '찾은 문제')에서 찾은
화면·기록 문제를 고친 것의 회귀 시험. 모든 대사는 합성이다(AGENTS.md 6).

a. [그 말이 아니에요] 뒤 조절 화면에 none_gen_unavailable 안내(view afterNone.basisRejected + stage.js 조건)
b. 화면 근거 낱말 = 인용 구간 안의 명사 부분(원문 글자 그대로), 조사는 받침에 맞게. 기록에 LLM 인용과 보인 구간 둘 다
c. [그 말이 아니에요] 단추가 그림 단추와 같은 크기(style.css)
d. 막힌 메시의 관문 점수를 afterNone.gate에, 만든 물체가 화면에 나온 적 없으면 shapeLlm.candidateChosen = null
"""
import json
import re
import sys
from pathlib import Path

import pytest

from ifs_chatbot import llm_shape as ls
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import WEB_DIR, shared
from ifs_chatbot.scene_builder import normalize_confirmed

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import sel_json, wait_stage  # noqa: E402
from test_g75_image_pick import calls, fake  # noqa: E402,F401
from test_g82_selection import ITEM, T_PEBBLE, none_until_settled, start, valid5  # noqa: E402

P13 = json.loads(shared("protocol", "selection_protocol.v0.13.json").read_text(encoding="utf-8"))
P12 = json.loads(shared("protocol", "selection_protocol.v0.12.json").read_text(encoding="utf-8"))
T13 = P13["phrases"]["llm_shape_basis"]["text"]
T12 = P12["phrases"]["llm_shape_basis"]["text"]


# ── 문구 판 ──────────────────────────────────────────────────────────────────
def test_protocol_013_changes_only_basis_text_and_notes():
    assert P13["protocolVersion"] == "0.13.0" and P13["changes"][0]["version"] == "0.13.0" and P13["status"] == "draft"
    assert "G83" in P13["changes"][0]["source"] and P13["changes"][1:] == P12["changes"]
    assert set(P13["phrases"]) == set(P12["phrases"])
    changed_text = [k for k in P12["phrases"] if P13["phrases"][k]["text"] != P12["phrases"][k]["text"]]
    assert changed_text == ["llm_shape_basis"]
    assert T13 == "'{quote}'{rago} 하신 말을 바탕으로 모양을 만들어 볼게요." and P13["phrases"]["llm_shape_basis"]["status"] == "draft"
    for k in P12["phrases"]:                                   # 다른 문구는 주석만 바뀔 수 있다(글·상태 그대로)
        if k != "llm_shape_basis":
            assert {x: P13["phrases"][k][x] for x in ("text", "status")} == {x: P12["phrases"][k][x] for x in ("text", "status")}
    assert "none_gen_unavailable" in P13["phrases"]["llm_shape_basis_wrong_button"]["note"]
    assert P13["adjustItemLabels"] == P12["adjustItemLabels"] and P13["premeasure"] == P12["premeasure"]
    assert not any(w in T13 for w in ("치료", "진단", "내담자", "예를 들어"))


def test_experiment_runtime_starts_with_g82_on_and_g77_shape_slot_off(tmp_path):
    cfg = load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "guard.required": False,
        "session.log_dir": str(tmp_path / "logs"), "preview.mode": "none"})
    rt = Runtime(cfg)                                          # 시작 점검(G82 문구·설정 조합) 통과
    assert rt.selection_protocol.version == "0.14.0" and rt.llm_shape_prompt is not None   # G85: experiment는 0.14
    assert rt.llm_rewrite_prompt is not None                   # G85 시작 점검도 통과
    assert ls.g77_shape_slot_open(cfg) is False                # G77 형태 낱말 칸은 자동으로 꺼짐
    assert any("shape_noun" in w for w in rt.warnings)


# ── b. 화면 근거 낱말 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,quote,shown,particle", [
    ("조약돌이 하나 있어요.", "조약돌이", "조약돌", "이라고"),
    ("판때기예요. 겨자색이고 반지르르해요.", "판때기예요", "판때기", "라고"),
    ("머릿속에 톱니바퀴가 있어요.", "톱니바퀴가", "톱니바퀴", "라고"),
    ("꼭 주전자 같아요. 회색이에요.", "주전자", "주전자", "라고"),
    ("돌덩이들이 있어요.", "돌덩이들이", "돌덩이들", "이라고"),
    ("판때기 같은 게 있어요.", "판때기 같은 게", "판때기", "라고"),
    ("둥근 조약돌이에요.", "둥근 조약돌이에요", "조약돌", "이라고"),
    # CP20: 인용 안 명사가 둘이면 마지막 덩어리(명사구의 머리). 수사 '하나'는 덩어리를 시작하지 않음
    ("머릿속에 톱니바퀴가 있어요.", "머릿속에 톱니바퀴가", "톱니바퀴", "라고"),
    ("유리 구슬이 있어요.", "유리 구슬이", "구슬", "이라고"),
    ("돌멩이랑 조약돌이 있어요.", "돌멩이랑 조약돌이", "조약돌", "이라고"),
    ("조약돌 하나가 있어요.", "조약돌 하나가", "조약돌", "이라고"),
    ("큐브 3개예요.", "큐브 3개예요", "큐브", "라고"),
    # CP20: 숫자·영문·기호로 끝나는 낱말의 조사(숫자는 읽는 소리의 받침, 영문은 판단할 수 없어 '라고')
    ("큐브3이에요.", "큐브3이에요", "큐브3", "이라고"),
    ("A4용지예요.", "A4용지예요", "A4용지", "라고"),
    ("USB예요.", "USB예요", "USB", "라고"),
    ("별★이에요.", "별★이에요", "별", "이라고"),
])
def test_basis_display_noun_part_original_chars(text, quote, shown, particle):
    norm = normalize_confirmed(text)
    s = norm.index(quote)
    r = ls.basis_display(norm, quote, [s, s + len(quote)], T13)
    assert r["shownText"] == shown and r["particle"] == particle and r["fallback"] is None
    a, b = r["shownSpan"]
    assert norm[a:b] == shown and s <= a < b <= s + len(quote)       # 원문 글자 그대로의 부분 구간
    assert r["llmQuote"] == quote and r["llmCharSpan"] == [s, s + len(quote)]
    assert r["trimmed"] is (shown != quote)
    assert r["text"] == f"'{shown}'{particle} 하신 말을 바탕으로 모양을 만들어 볼게요."
    assert ls.basis_display(norm, quote, [s, s + len(quote)], T13) == r          # 같은 입력 → 같은 결과


def test_basis_display_falls_back_to_full_quote():
    norm = normalize_confirmed("조약돌이 하나 있어요.")
    old = ls.basis_display(norm, "조약돌이", [0, 4], T12)                    # 0.12 문구: 줄이지 않음(예전 그대로)
    assert old["shownText"] == "조약돌이" and old["fallback"] == "template_without_particle" and old["displayable"]
    assert old["text"] == "'조약돌이'라고 하신 말을 바탕으로 모양을 만들어 볼게요."
    none = ls.basis_display(normalize_confirmed("하나 있어요."), "있어요", [3, 6], T13)
    assert none["shownText"] == "있어요" and none["fallback"] == "no_noun" and none["displayable"]
    assert none["shownSpan"] == [3, 6]


@pytest.mark.parametrize("norm,quote,span", [
    ("조약돌", "없는 물체", [0, 3]),                        # CP20 재현: 인용 글자가 원문에 없음
    ("조약돌이 하나 있어요.", "조약돌이", [1, 5]),           # 구간이 인용과 어긋남
    ("조약돌이 하나 있어요.", "조약돌이", None),
    ("조약돌이 하나 있어요.", "조약돌이", [0, 99]),
    ("조약돌이 하나 있어요.", "조약돌이", [True, 4]),
])
@pytest.mark.parametrize("template", [T13, T12])
def test_basis_display_span_mismatch_shows_nothing(norm, quote, span, template):
    # CP20: 어느 문구 분기에서도 원문에 없는 글자를 화면에 내지 않는다 — 보이지 않음(displayable false)
    r = ls.basis_display(norm, quote, span, template)
    assert r["fallback"] == "span_mismatch" and r["displayable"] is False
    assert r["shownText"] is None and r["shownSpan"] is None and r["text"] is None and r["llmQuote"] == quote


def test_span_mismatch_item_not_adopted_goes_existing_path(tmp_path, fake, monkeypatch):
    # CP20: 검증기를 지났다고 기록된 항목이라도 근거 줄을 원문 그대로 보일 수 없으면 채택하지 않음 → LLM 없는 지금 경로
    from ifs_chatbot import llm_shape as lsm
    real = lsm.run

    def bad_run(session, spec, norm):
        rec = real(session, spec, norm)
        rec["adopted"] = {"quote": "없는 물체", "charSpan": [0, 3], "en": "pebble", "origin": lsm.ORIGIN}
        return rec
    monkeypatch.setattr(lsm, "run", bad_run)
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-SPAN")
    v = none_until_settled(f)
    assert v["stage"] == "adjusting" and "llmShapeBasis" not in v and calls(tmp_path) == []
    d = valid5(f)
    sl, an = d["generation"]["shapeLlm"], d["generation"]["afterNone"]
    assert sl["route"] == "none" and sl["routeReason"] == "basis_span_mismatch" and sl["exposed"] is False
    assert sl["basisShown"]["displayable"] is False and sl["basisShown"]["shownText"] is None
    assert an["shapeLlmUsed"] is False and an["blockReason"] == "no_shape_stated" and f._shape_items() == []


def test_selection_records_llm_quote_and_shown_span(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-B")
    v = none_until_settled(f)
    assert v["stage"] == "picking"
    assert v["llmShapeBasis"] == {"quote": "디딤돌", "text": "'디딤돌'이라고 하신 말을 바탕으로 모양을 만들어 볼게요."}
    d = valid5(f)
    bs = d["generation"]["shapeLlm"]["basisShown"]
    assert bs["llmQuote"] == "디딤돌이" and bs["llmCharSpan"] == [0, 4]
    assert bs["shownText"] == "디딤돌" and bs["shownSpan"] == [0, 3] and bs["particle"] == "이라고" and bs["trimmed"] is True
    assert bs["version"] == ls.BASIS_DISPLAY_VERSION
    assert d["generation"]["afterNone"]["shapeLlmBasisShown"] == bs
    assert d["generation"]["shapeLlm"]["adopted"]["quote"] == "디딤돌이"       # LLM 인용은 그대로 남음
    assert "pebble" not in json.dumps(v["llmShapeBasis"], ensure_ascii=False)


# ── a. [그 말이 아니에요] 뒤 안내 ──────────────────────────────────────────────
def test_basis_rejected_view_carries_flag_for_unavailable_note(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-A")
    none_until_settled(f)
    v = f.reject_shape_basis()
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True
    assert v["afterNone"]["basisRejected"] is True and v["afterNone"]["status"] == "declined"
    js = (WEB_DIR / "stage.js").read_text(encoding="utf-8")
    m = re.search(r"const genNote = (.+?)\n", js)
    assert m and "an.basisRejected === true" in m.group(1) and '"blocked", "failed", "timeout"' in m.group(1)
    assert 'phrase("none_gen_unavailable")' in js[m.start():m.start() + 600]


def test_skip_and_image_none_do_not_show_unavailable_note(tmp_path, fake):
    # 참여자가 [넘어갈게요]를 누른 경우(cancelled)는 예전처럼 안내 없음 — basisRejected가 없음
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-A2")
    none_until_settled(f)
    v = f.skip_generation()
    assert v["stage"] == "adjusting" and v["afterNone"]["status"] == "cancelled" and not v["afterNone"].get("basisRejected")


# ── c. 단추 무게 ─────────────────────────────────────────────────────────────
def test_basis_button_same_size_as_image_buttons():
    js = (WEB_DIR / "stage.js").read_text(encoding="utf-8")
    css = (WEB_DIR / "style.css").read_text(encoding="utf-8")
    assert 'el("div", { class: "llm-shape-basis" }' in js and "none-fit-row llm-shape-basis" not in js
    rule = re.search(r"\.llm-shape-basis \.shape-basis-wrong \{([^}]*)\}", css)
    assert rule and "flex: 0 0 auto" in rule.group(1)
    assert "calc((100% - 2 * var(--space-4)) / 3" in rule.group(1)       # 3열 그림 칸 하나의 단추 폭
    assert re.search(r"\.llm-shape-basis \{[^}]*display: flex", css)
    # 관문으로 그림이 2장·1장만 보일 때도 그 칸의 단추 폭(실제 흐름 R2: 2장일 때 381px = 381px)
    assert ".stage:has(.pick-grid.n2) .llm-shape-basis .shape-basis-wrong" in css
    assert ".stage:has(.pick-grid.n1) .llm-shape-basis .shape-basis-wrong" in css


# ── d. 기록 ──────────────────────────────────────────────────────────────────
def test_mesh_gate_blocked_scores_in_after_none_and_candidate_chosen_null(tmp_path, fake):
    fake(mesh="gate")
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-D")
    none_until_settled(f)
    v = f.pick_image("0")
    assert v["stage"] == "generating"
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "adjusting" and v["afterNone"]["status"] == "blocked" and v["afterNone"]["blockReason"] == "person_like"
    f.finish()
    d = valid5(f)
    an = d["generation"]["afterNone"]
    assert an["gate"]["personLikeScore"] == 0.9 and an["gate"]["passed"] is False and an["gate"]["threshold"] == 0.5
    assert an["gate"]["labelScores"]["a head with eyes and a mouth"] == 0.7
    sl = d["generation"]["shapeLlm"]
    assert sl["exposed"] is True and sl["imageChosen"] is True
    assert sl["candidateExposed"] is False and sl["candidateChosen"] is None     # 만든 물체가 나온 적 없음 → null


def test_made_object_shown_but_not_chosen_is_false(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-D2")
    none_until_settled(f)
    f.pick_image("0")
    wait_stage(f)
    v = f.view()
    assert v["stage"] == "selecting" and v["candidates"][0].get("afterNone") is True
    other = next(c for c in v["candidates"] if not c.get("afterNone"))
    f.select(other["id"])                                       # 만든 물체 말고 다른 후보
    d = valid5(f)
    sl = d["generation"]["shapeLlm"]
    assert sl["candidateExposed"] is True and sl["candidateChosen"] is False
    assert "gate" not in d["generation"]["afterNone"]           # 막힌 메시가 없으면 키 없음


def test_basis_rejected_candidate_chosen_null(tmp_path, fake):
    rt, s, f, llm = start(tmp_path, T_PEBBLE, sid="SYN-G83-D3")
    none_until_settled(f)
    f.reject_shape_basis()
    f.finish()
    sl = valid5(f)["generation"]["shapeLlm"]
    assert sl["rejected"] is True and sl["candidateExposed"] is False and sl["candidateChosen"] is None
    assert calls(tmp_path) and all(c.get("imagePick") for c in calls(tmp_path))   # 메시 단계는 부르지 않음
