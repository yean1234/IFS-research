"""한국어 처리 유틸리티.

- 정규화: 유니코드 NFC, 따옴표 통일, 공백 정리
- 조사 선택: 은/는, 이/가, 을/를, 와/과, 으로/로 (받침 기준)
- 인용 추출: 작은따옴표 안 표현
- 형태소 분석: Kiwi(kiwipiepy)가 있으면 사용, 없으면 단순 규칙으로 대체

Kiwi는 문장을 형태소로 자르고 품사만 붙인다. "어떤 단어가 장면 속성인가"는
Kiwi가 아니라 1층 사전(shared/lexicon)이 정한다. (노션 「앞으로 개발 방향」 > 추출 답변)
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

# ── 정규화 ──────────────────────────────────────────────────────────────────
_CHAR_MAP = {
    "‘": "'", "’": "'", "＇": "'", "`": "'", "´": "'",
    "“": '"', "”": '"', "＂": '"',
    "？": "?", "！": "!", "～": "~",
}
_WS = re.compile(r"\s+")


def normalize(text: str | None) -> str:
    """NFC 정규화 + 따옴표·물음표 통일 + 연속 공백을 하나로."""
    text = unicodedata.normalize("NFC", text or "")
    for a, b in _CHAR_MAP.items():
        text = text.replace(a, b)
    return _WS.sub(" ", text).strip()


def squash(text: str | None) -> str:
    """모든 공백 제거. V3(인용이 참여자 말과 글자까지 같은가) 대조용 "공백 정규화"."""
    return _WS.sub("", normalize(text))


_QUOTE = re.compile(r"'([^']+)'")


def quoted_spans(text: str) -> list[str]:
    """작은따옴표 안 표현 목록. 예: "그 '덩어리'는 어떤 '덩어리'인가요?" → ['덩어리', '덩어리']"""
    return [m.strip() for m in _QUOTE.findall(normalize(text)) if m.strip()]


def strip_quoted(text: str) -> str:
    """작은따옴표 구간을 지운 나머지(면담자가 직접 고른 말)."""
    return normalize(_QUOTE.sub(" ", normalize(text)))


QUOTE_MASK = "QQ"


def mask_quoted(text: str) -> str:
    """작은따옴표 구간을 라틴 자리표시자(QQ)로 바꾼다. 따옴표를 그냥 지우면 '그 은 마치…'처럼 조사가 떨어져
    Kiwi가 '은'을 명사(銀)로 읽는다. 자리표시자를 두면 조사가 조사로 분석된다."""
    return normalize(_QUOTE.sub(QUOTE_MASK, normalize(text)))


def count_questions(text: str) -> int:
    return normalize(text).count("?")


# ── 받침·조사 ────────────────────────────────────────────────────────────────
_HANGUL_FIRST, _HANGUL_LAST = 0xAC00, 0xD7A3
_RIEUL = 8  # 종성 인덱스: ㄹ
# 숫자를 한국어로 읽을 때의 받침 (영/일/이/삼/사/오/육/칠/팔/구)
_DIGIT_JONG = {"0": 21, "1": _RIEUL, "2": 0, "3": 16, "4": 0, "5": 0, "6": 21, "7": _RIEUL, "8": _RIEUL, "9": 0}


def _last_jong(word: str) -> int | None:
    """마지막 글자의 종성 인덱스(0=받침 없음). 판단 불가면 None."""
    for ch in reversed(normalize(word)):
        if ch in "'\" .,!?)]}…~":
            continue
        code = ord(ch)
        if _HANGUL_FIRST <= code <= _HANGUL_LAST:
            return (code - _HANGUL_FIRST) % 28
        if ch in _DIGIT_JONG:
            return _DIGIT_JONG[ch]
        return None
    return None


_JOSA = {
    "은/는": ("은", "는"),
    "이/가": ("이", "가"),
    "을/를": ("을", "를"),
    "과/와": ("과", "와"),
    "와/과": ("과", "와"),
    "이라/라": ("이라", "라"),
    "아/야": ("아", "야"),
}


def josa(word: str, kind: str) -> str:
    """word 뒤에 붙일 조사. 판단할 수 없으면 '은(는)'처럼 병기한다."""
    jong = _last_jong(word)
    if kind == "으로/로":
        if jong is None:
            return "(으)로"
        return "로" if jong in (0, _RIEUL) else "으로"
    with_b, without_b = _JOSA[kind]
    if jong is None:
        return f"{with_b}({without_b})"
    return with_b if jong else without_b


# ── 형태소 분석 ──────────────────────────────────────────────────────────────
# 내용어로 보는 품사: 일반/고유명사, 형용사, 동사, 어근, 일반부사
CONTENT_TAGS = {"NNG", "NNP", "VA", "VV", "XR", "MAG"}
NOUN_TAGS = {"NNG", "NNP"}
PREDICATE_TAGS = {"VA", "VV", "XR"}


@dataclass(frozen=True)
class Token:
    form: str   # Kiwi가 돌려준 형태(용언은 어간: 무거워요 → 무겁)
    tag: str    # 세종 품사 태그 (불규칙 표시 포함: VA-I)
    start: int  # 원문(정규화된 문장) 기준 시작 위치
    end: int

    @property
    def base_tag(self) -> str:
        return self.tag.split("-")[0]

    @property
    def lemma(self) -> str:
        return self.form

    @property
    def is_content(self) -> bool:
        return self.base_tag in CONTENT_TAGS


class Analyzer:
    """Kiwi 래퍼. kiwipiepy가 없으면 정규식 기반 대체 분석을 쓴다(정확도 낮음)."""

    def __init__(self, use_kiwi: bool = True, user_words: list[tuple[str, str]] | None = None):
        self._kiwi = None
        self.backend = "fallback-regex"
        self.version = None
        if use_kiwi:
            try:
                import kiwipiepy  # noqa: WPS433
                from kiwipiepy import Kiwi

                self._kiwi = Kiwi()
                for word, tag in user_words or []:
                    self._kiwi.add_user_word(word, tag)
                self.backend = "kiwi"
                self.version = getattr(kiwipiepy, "__version__", None)
            except Exception:  # pragma: no cover - 설치 환경에 따라 다름
                self._kiwi = None

    @property
    def available(self) -> bool:
        return self._kiwi is not None

    def tokens(self, text: str) -> list[Token]:
        text = normalize(text)
        if not text:
            return []
        return list(_tokens_cached(self, text))

    def content_lemmas(self, text: str) -> set[str]:
        return {t.lemma for t in self.tokens(text) if t.is_content}

    def info(self) -> dict:
        return {"backend": self.backend, "version": self.version}


@lru_cache(maxsize=4096)
def _tokens_cached(analyzer: Analyzer, text: str) -> tuple[Token, ...]:
    if analyzer._kiwi is not None:
        return tuple(
            Token(t.form, t.tag, t.start, t.start + t.len) for t in analyzer._kiwi.tokenize(text)
        )
    return tuple(_fallback_tokens(text))


# 대체 분석: 어절에서 흔한 어미·조사를 떼어 내용어 후보만 남긴다.
_ENDINGS = sorted(
    [
        "이에요", "예요", "어요", "아요", "해요", "했어요", "였어요", "이었어요", "이요", "요",
        "습니다", "입니다", "이고", "하고", "고", "은", "는", "이", "가", "을", "를", "에", "에서",
        "의", "도", "만", "처럼", "같아요", "같은", "같이", "으로", "로", "와", "과", "한", "인",
    ],
    key=len,
    reverse=True,
)
_HANGUL_WORD = re.compile(r"[가-힣]+|[A-Za-z]+|\d+|[?!.]")


def _fallback_tokens(text: str):
    for m in _HANGUL_WORD.finditer(text):
        word, start = m.group(0), m.start()
        if word in "?!.":
            yield Token(word, "SF", start, m.end())
            continue
        stem = word
        for end in _ENDINGS:
            if stem.endswith(end) and len(stem) > len(end):
                stem = stem[: -len(end)]
                break
        yield Token(stem, "NNG", start, start + len(stem))


def eojeol_at(text: str, start: int, end: int) -> str:
    """start~end 구간을 포함하는 어절(띄어쓰기 단위) 전체."""
    text = normalize(text)
    left = text.rfind(" ", 0, start) + 1
    right = text.find(" ", end)
    return text[left: right if right != -1 else len(text)].strip(" .,!?")
