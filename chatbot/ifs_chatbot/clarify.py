"""확인 질문 루프(선택 기능, 기본 꺼짐: config [mapping] clarify_loop) — LLM 없음, 고정 틀만.

확정 직후 개선 매핑(v1)이 값으로 옮기지 못한 속성성 표현(사전에 없는 의태어·형용사, 장면 파라미터가 없는 질감·모양어)과
퍼지 매칭으로 만든 값을 찾아, 질문 틀 what_kind("그 '{X}'은(는) 어떤 '{X}'인가요?")에 참여자 말 X를 그대로 넣어 묻는다.
- 시스템 어휘·차원어·예시·선택지를 넣지 않는다(AGENTS.md 원칙 3). 틀 실현은 protocol.realize(고정 문장).
- 질문은 검증기 V3·V4·V5·V7·V9로 다시 검사하고, 걸리면 묻지 않는다.
- 회상 문장(_clauses status = context) 속 말은 묻지 않는다(과거 장면으로 들어가지 않게).
확증 비교(research-design 3.2)에서는 끈다. 켜면 답이 확정 텍스트에 덧붙어 두 매핑에 같이 들어간다.
"""
from __future__ import annotations

import json

from .extract import FUNCTION_LEMMAS

TEMPLATE = "what_kind"
ATTR_TAGS = {"XR", "MAG", "VA"}
ATTR_CATEGORIES = {"texture", "shape"}
ENDINGS = ("하네요", "했어요", "해져요", "해요", "하고", "하게", "한데", "해서", "하다", "한", "해", "이에요", "예요", "이고",
           "이요", "요", "고", "게")


def _stem(word: str) -> str:
    for end in ENDINGS:
        if word.endswith(end) and len(word) - len(end) >= 2:
            return word[:-len(end)]
    return word


def _in_context(spec: dict, span: list[int]) -> bool:
    return any(c["status"] == "context" and c["charSpan"][0] <= span[0] and span[1] <= c["charSpan"][1]
               for c in spec.get("_clauses") or [])


def clarify_targets(spec: dict, text: str, max_n: int = 2, asked: set[str] | None = None) -> list[dict]:
    """v1 spec → 물을 참여자 표현 X 목록(원문 순서, 최대 max_n). X는 확정 텍스트에 글자 그대로 있다."""
    asked = asked or set()
    found: list[dict] = []
    for n in spec.get("_needsConfirmation") or []:
        found.append({"x": _stem(n["trigger"]), "charSpan": n["charSpan"], "why": "fuzzy_lexicon", "path": n["path"]})
    for u in spec.get("_unmatched") or []:
        if u["tag"].split("-")[0] in ATTR_TAGS and u["lemma"] not in FUNCTION_LEMMAS:
            found.append({"x": u["surface"], "charSpan": u["charSpan"], "why": "unread_attribute", "path": None})
    for u in spec.get("_unmapped") or []:
        if u["category"] in ATTR_CATEGORIES:
            p = u["_provenance"]
            found.append({"x": _stem(p["trigger"]), "charSpan": p["charSpan"], "why": f"unmapped_{u['category']}",
                          "path": None})
    out, seen = [], set(asked)
    for f in sorted(found, key=lambda f: (f["charSpan"][0], f["x"])):
        x = f["x"].strip(" .,!?~")
        if len(x) < 2 or x in seen or x not in text or _in_context(spec, f["charSpan"]):
            continue
        seen.add(x)
        out.append({**f, "x": x})
        if len(out) >= max_n:
            break
    return out


def question_json(protocol, x: str, stage: str = "flesh_out") -> tuple[str, str]:
    """(질문 문장, 검증기에 넣을 턴 JSON). 고정 틀 실현이라 같은 X면 언제나 같은 문장이다."""
    utt = protocol.realize(TEMPLATE, x)
    raw = json.dumps({"stage": stage, "risk_signal": "none", "move": "ask", "template": TEMPLATE,
                      "anchor_quote": x, "utterance": utt}, ensure_ascii=False)
    return utt, raw
