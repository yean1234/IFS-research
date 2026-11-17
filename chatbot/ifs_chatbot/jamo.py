"""한글 자모 분해와 자모 편집거리 — 개선 매핑(v1)의 결정론적 퍼지 매칭용.

임베딩이 아니다. 음절을 초성·중성·종성 자모로 풀어 Levenshtein 거리를 잰다.
같은 두 문자열은 언제나 같은 거리다(난수·모델 없음).
"""
from __future__ import annotations

_BASE, _LAST = 0xAC00, 0xD7A3
_L = [chr(c) for c in range(0x1100, 0x1113)]          # 초성 19
_V = [chr(c) for c in range(0x1161, 0x1176)]          # 중성 21
_T = [""] + [chr(c) for c in range(0x11A8, 0x11C3)]   # 종성 27 + 없음


def decompose(text: str) -> list[str]:
    """'매끈' → ['ᄆ','ᅢ','ᄁ','ᅳ','ᆫ']. 한글 음절이 아닌 글자는 그대로 둔다."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if _BASE <= code <= _LAST:
            i = code - _BASE
            out.append(_L[i // 588])
            out.append(_V[(i % 588) // 28])
            t = _T[i % 28]
            if t:
                out.append(t)
        else:
            out.append(ch)
    return out


def levenshtein(a: list[str] | str, b: list[str] | str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def jamo_distance(a: str, b: str) -> int:
    return levenshtein(decompose(a), decompose(b))
