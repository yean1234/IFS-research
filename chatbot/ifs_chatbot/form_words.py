"""형태 낱말의 자리·부정 판정(사전·규칙만). G62 형태 프롬프트(tools/gen3d/prompts.py)와 G73 재진술 매핑(resay.py)이 같이 쓴다.

G62에서 tools/gen3d/prompts.py 안에 있던 함수를 그대로 옮겼다(동작 불변 — tools/gen3d 시험과 형태 프롬프트 바이트 비교로 확인).
같은 Doc → 언제나 같은 판정(모델·난수·상태 없음, 원칙 1).
"""
from __future__ import annotations

NOUNISH = frozenset({"NNG", "NNP", "XSN"})


def noun_run_bounds(toks, i: int, j: int) -> bool:
    """toks[i..j]가 붙어 쓴 명사 연속 전체와 같은가(뒷부분·앞부분만 맞추지 않음: '비눗방울'≠'방울')."""
    if i > 0 and toks[i - 1].base_tag in NOUNISH and toks[i - 1].end == toks[i].start:
        return False
    if j + 1 < len(toks) and toks[j + 1].base_tag in NOUNISH and toks[j + 1].start == toks[j].end \
            and not (toks[j + 1].form == "들" and toks[j + 1].base_tag == "XSN"):     # 복수 '조각들'은 같은 낱말
        return False
    return True


def form_position(doc, j: int, loc_nouns, size_nouns) -> str:
    """명사 토큰(끝 j)의 자리: head | simile | noun_modifier | object | genitive | location | size."""
    toks = doc.toks
    k = j + 1
    if k < len(toks) and toks[k].form == "들" and toks[k].base_tag == "XSN":
        k += 1
    if k >= len(toks) or doc.sent[k] != doc.sent[j]:
        return "head"
    nt = toks[k]
    if nt.form == "만큼":
        return "size"
    if nt.form == "만" and nt.base_tag == "JX" and k + 1 < len(toks) and toks[k + 1].form == "하":
        return "size"                                # 'N만 하다'(크기 비교). '꽃만'(뿐)은 크기가 아님
    if nt.base_tag in ("NNG", "NNP", "NNB") and nt.form in size_nouns:
        return "size"
    if nt.form in ("처럼", "같이") or (nt.form == "같" and nt.base_tag == "VA"):
        return "simile"
    if nt.base_tag in ("NNG", "NNP") and nt.form in loc_nouns:
        return "location"
    if nt.base_tag == "JKB":
        return "location"
    if nt.base_tag == "JKO":
        return "object"
    if nt.base_tag == "JKG":
        return "genitive"
    if nt.base_tag in ("NNG", "NNP"):
        return "noun_modifier"
    return "head"


def next_noun(doc, j: int, skip: int = 4):
    """j 뒤 같은 문장에서 처음 나오는 명사(NNG·NNP·NNB) 토큰 번호."""
    toks = doc.toks
    for k in range(j + 1, min(len(toks), j + 1 + skip)):
        if doc.sent[k] != doc.sent[j]:
            return None
        if toks[k].base_tag in ("NNG", "NNP", "NNB"):
            return k
    return None


def negated_near(doc, i: int, j: int, lexical_starts: set, neg_spans) -> bool:
    """부정·정정: 기존 추출기의 _negated 구간과 겹치거나, 바로 앞 '안', 또는 같은 문장에서 다른 사전 낱말이 나오기 전
    3어절 안에 아니·않·없·못이 온다('공은 아니고', '동그랗지는 않고', '끈, 아니 귀신이에요')."""
    toks = doc.toks
    s0, s1 = toks[i].start, toks[j].end
    if any(a < s1 and s0 < b for a, b in neg_spans):
        return True
    if i > 0 and toks[i - 1].form == "안" and toks[i - 1].base_tag == "MAG" and doc.sent[i - 1] == doc.sent[i]:
        return True
    eoj_limit = doc.eoj[j] + 3
    for k in range(j + 1, len(toks)):
        t = toks[k]
        if doc.sent[k] != doc.sent[j] or doc.eoj[k] > eoj_limit or k in lexical_starts:
            return False
        if (t.form == "아니" and t.base_tag in ("VCN", "MAG", "IC")) or (t.form == "않" and t.base_tag == "VX") \
                or (t.form == "없" and t.base_tag == "VA") or (t.form == "못" and t.base_tag in ("MAG", "VX")):
            return True
        if t.form == "안" and t.base_tag == "MAG":
            return True
    return False
