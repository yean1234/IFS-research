"""2단계 독립 검토(T2)의 합성 대화 회귀 — AC-2 라벨 세트(drift_cases.json)와 따로 센다.

규칙을 고친 뒤 이 대화로 확인했으므로 독립 평가가 아니다(docs/drift-design.md 9.3절).
knownLimitation이 붙은 항목은 보류·분류표 밖이라 지금도 기대와 다르게 나온다. xfail로 두지 않고
문서 목록과 같은지만 확인한다. 대사는 모두 합성(AGENTS.md 6).
"""
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "drift" / "review_t2_regression.json"
DOC = Path(__file__).resolve().parents[2] / "docs" / "drift-design.md"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _decide(rt, item) -> dict:
    if "turns" in item:
        turns = [{"i": k, "stage": st, "text": tx} for k, (st, tx) in enumerate(item["turns"])]
        return rt.drift.assess(turns)
    s = rt.new_session("static", "REV" + item["id"])
    s.start()
    it = iter(item["static"])
    while s.awaiting in ("reply", "soft_check"):
        if s.awaiting == "soft_check":
            s.act("continue")
            continue
        t = next(it, None)
        s.reply(t) if t else s.act("skip")
    s.act("confirm")
    return s.log.data["drift"]["assessment"]


@pytest.fixture(scope="module")
def results(rt):
    return {it["id"]: _decide(rt, it) for it in DATA["items"]}


@pytest.mark.parametrize("item", [it for it in DATA["items"] if it["expected"] and not it["knownLimitation"]],
                         ids=lambda it: it["id"])
def test_review_case_matches_expectation(results, item):
    assert results[item["id"]]["decision"] == item["expected"], item["what"]


def test_known_limitations_are_listed_in_doc_and_reported(results):
    doc = DOC.read_text(encoding="utf-8")
    sec = doc.split("### 9.3", 1)[1].split("\n### ", 1)[0]
    lim = [it for it in DATA["items"] if it["knownLimitation"]]
    for it in lim:
        assert f"| {it['id']} |" in sec, it["id"]
    labeled = [it for it in DATA["items"] if it["expected"]]
    ok = sum(results[it["id"]]["decision"] == it["expected"] for it in labeled)
    print(f"\nreview-t2: 기대 일치 {ok}/{len(labeled)}, 알려진 한계 {len(lim)}, 기대 없음 "
          f"{len(DATA['items']) - len(labeled)}")
    for it in lim:
        print(f"  {it['id']} expected={it['expected']} got={results[it['id']]['decision']}")
    assert ok == len(labeled) - sum(results[it["id"]]["decision"] != it["expected"] for it in lim)
