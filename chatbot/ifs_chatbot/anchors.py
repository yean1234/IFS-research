"""인용 후보 — 참여자 발화에서 글자 그대로 잘라 낸 낱말·짧은 명사구.

Clean Language 질문은 참여자의 '핵심 낱말'을 되돌려 묻는다. 작은 모델(gemma4:e4b)은 문장을 통째로
인용하는 경향이 있어서(실험: "'젖은 종이처럼 축 처진 덩어리 같아요'는 마치 무엇 같나요?"), 컨트롤러가
인용 후보를 미리 잘라 프롬프트에 넣는다. 후보는 모두 참여자 원문의 부분 문자열이므로 새 말을 주지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .korean import Analyzer, normalize
from .lexicon import Lexicon
from .safety import SafetyLexicon

ANCHOR_STOP = {
    "것", "거", "수", "때", "쪽", "정도", "뭔가", "무언가", "무엇", "마음", "생각", "지금", "그것", "이것", "저것",
    "느낌", "기분", "감정", "상황", "부분", "약간", "조금", "좀", "그냥", "너무", "정말", "진짜", "제일", "가장",
}
# 묘사어가 먼저, 신체 부위·사물(비유의 원천)은 뒤로
CATEGORY_RANK = ("form", "shape", "color", "texture", "brightness", "temperature", "weight", "size",
                 "movement", "posture", "sound", "sensation", "emotion", "object")
SKIP_CATEGORIES = {"dimension", "body_layer", "self_reference"}


@dataclass(frozen=True)
class Anchor:
    text: str        # 참여자 원문 그대로의 부분 문자열
    kind: str        # noun | phrase | root | predicate
    rank: int        # 작을수록 앞
    age: int         # 0 = 가장 최근 발화


def _rank(cat: str | None) -> int:
    if cat in CATEGORY_RANK:
        return CATEGORY_RANK.index(cat)
    if cat == "body_part":
        return len(CATEGORY_RANK) + 5
    return len(CATEGORY_RANK)


def anchors_in(text: str, lexicon: Lexicon, analyzer: Analyzer, safety: SafetyLexicon, age: int = 0) -> list[Anchor]:
    text = normalize(text)
    toks = analyzer.tokens(text)
    cats = {h.token_index: h.entry.category for h in lexicon.hits(text)}
    eojeols = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]

    def eojeol_of(pos: int) -> int:
        return next((n for n, (a, b) in enumerate(eojeols) if a <= pos < b), -1)

    def tokens_in(n: int) -> list:
        a, b = eojeols[n]
        return [t for t in toks if a <= t.start < b and t.base_tag not in ("SF", "SP", "SS", "SE", "SW")]

    out: list[Anchor] = []
    for i, tok in enumerate(toks):
        # '-하다' 형용사 어근: Kiwi가 '답답하/VA'(한 덩어리)나 '캄캄/MAG + 하/XSA'로 낼 때도 어근을 인용 후보로
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        root = None
        if tok.base_tag in ("VA", "VV") and tok.form.endswith("하") and len(tok.form) > 1:
            root = tok.form[:-1]
        elif tok.base_tag == "MAG" and nxt is not None and nxt.form == "하" and nxt.base_tag in ("XSA", "XSV"):
            root = tok.form
        if root is not None:
            if text[tok.start:tok.start + len(root)] == root and root not in ANCHOR_STOP and not safety.has_depth_marker(root):
                out.append(Anchor(root, "root", 3, age))
            continue
        cat = cats.get(i)
        # 문장 끝 용언 한 어절('조여요', '무거워요', '흔들려요') — 참여자 원문 그대로, 사전의 묘사어일 때만
        if tok.base_tag in ("VA", "VV") and cat and cat not in SKIP_CATEGORIES:
            e = eojeol_of(tok.start)
            if e >= 0 and eojeols[e][0] == tok.start:
                in_eojeol = tokens_in(e)
                if in_eojeol and in_eojeol[-1].base_tag == "EF":
                    word = text[eojeols[e][0]:eojeols[e][1]].rstrip(".,!?~…")
                    if word and not safety.has_depth_marker(word):
                        out.append(Anchor(word, "predicate", _rank(cat) + 1, age))
            continue
        surface = text[tok.start:tok.end]
        if surface != tok.form or tok.form in ANCHOR_STOP or safety.has_depth_marker(tok.form):
            continue
        self_ref = cat == "self_reference"   # '작은 나'처럼 꾸밈을 받은 나/저 — part 묘사. 맨 '나'는 화자라 빼고 명사구만
        if cat in SKIP_CATEGORIES and not self_ref:
            continue
        if tok.base_tag == "XR":
            out.append(Anchor(tok.form, "root", 3, age))
            continue
        if tok.base_tag not in ("NNG", "NNP") and not self_ref:
            continue
        rank = _rank("posture") if self_ref else _rank(cat)
        if not self_ref:
            out.append(Anchor(tok.form, "noun", rank, age))
        # 앞 어절이 관형형(…은/ㄴ/는)으로 끝나면 붙여 짧은 명사구를 만든다: '젖은 종이', '축 처진 덩어리'
        e = eojeol_of(tok.start)
        if e <= 0 or eojeols[e][0] != tok.start:
            continue
        start, extra = None, 0
        prev = tokens_in(e - 1)
        if prev and prev[-1].base_tag == "ETM":
            start, extra = eojeols[e - 1][0], 1
            if e - 2 >= 0:
                prev2 = tokens_in(e - 2)
                if prev2 and (all(t.base_tag == "MAG" for t in prev2) or prev2[-1].base_tag == "ETM"):
                    start, extra = eojeols[e - 2][0], 2
        if start is not None:
            phrase = text[start:tok.end]
            if not safety.has_depth_marker(phrase):
                out.append(Anchor(phrase, "phrase", max(0, rank - 1), age))
    return out


def anchor_candidates(texts: list[str], lexicon: Lexicon, analyzer: Analyzer, safety: SafetyLexicon,
                      used: set[str] | None = None, limit: int = 8) -> list[Anchor]:
    """여러 발화에서 후보를 모아 (순위, 최근성) 순으로. 이미 쓴 인용은 뺀다."""
    used = {normalize(u) for u in (used or set()) if u}
    best: dict[str, Anchor] = {}
    for age, text in enumerate(reversed(texts)):
        if safety.depth(text)["strong"]:
            continue  # L5: 기억·외상 서사 발화의 말은 인용하지 않는다(그 장면으로 더 들어가지 않게)
        for a in anchors_in(text, lexicon, analyzer, safety, age):
            if a.text in used:
                continue
            if a.text not in best or (a.rank, a.age) < (best[a.text].rank, best[a.text].age):
                best[a.text] = a
    return sorted(best.values(), key=lambda a: (a.rank, a.age))[:limit]
