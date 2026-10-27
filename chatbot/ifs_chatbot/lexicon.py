"""1층 사전(shared/lexicon/layer1_lexicon.v0.json)을 형태소 토큰에 대응시킨다.

두 군데서 쓴다.
- 검증기 V5(어휘 누출): 면담자 질문에 참여자가 쓰지 않은 사전 어휘가 있는지
- 추출 미리보기: 확정 텍스트의 단어 → 속성 후보 + _provenance

Kiwi 품사 태그는 '-하다' 형용사를 문맥마다 다르게 낸다(촉촉하/VA, 캄캄/MAG+하/XSA,
선명/NNG+하/XSA). 그래서 표제어 형태가 같으면 품사군 안에서 너그럽게 맞춘다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .korean import Analyzer, Token, eojeol_at, normalize

# 사전 품사 → 받아들이는 Kiwi 기본 품사
COMPAT = {
    "NNG": {"NNG", "NNP", "NNB", "XR"},
    "NNP": {"NNG", "NNP", "XR"},
    "XR": {"XR", "NNG", "NNP", "MAG"},
    "MAG": {"MAG", "XR"},
    "VA": {"VA", "VV"},
    "VV": {"VV", "VA"},
    "NP": {"NP", "IC"},
}
NEG_PREFIXES = {"불", "무", "비", "미"}          # 불투명, 무가치 …
NEGATORS = {("않", "VX"), ("없", "VA"), ("아니", "VCN"), ("못하", "VX"), ("말", "VX")}
PRE_NEGATORS = {("안", "MAG"), ("못", "MAG")}
PREDICATE_TAGS = {"VA", "VV", "XR"}
CONTENT_BASE_TAGS = {"NNG", "NNP", "NNB", "XR", "MAG", "VA", "VV"}


@dataclass(frozen=True)
class LexEntry:
    lemma: str
    pos: str
    category: str
    value: dict = field(compare=False, hash=False)
    ex: str = field(default="", compare=False)
    src: str = field(default="draft", compare=False)
    alt: tuple[str, ...] = field(default=(), compare=False)
    rule_name: str = field(default="lexicon", compare=False)
    slot: str | None = field(default=None, compare=False)
    next_forms: tuple[str, ...] = field(default=(), compare=False)   # 다음 형태소가 이 중 하나일 때만 (예: 손바닥 + 만)

    @property
    def key(self) -> str:
        return f"{self.category}:{self.lemma}"

    @property
    def rule(self) -> str:
        return f"{self.rule_name}.{self.lemma}"


@dataclass
class Hit:
    entry: LexEntry
    trigger: str            # 원문에서 그 값을 만든 말(어절 또는 형태)
    char_span: tuple[int, int]
    token_index: int
    negated: bool = False
    change: str | None = None   # '-어지다' → "becoming"

    def provenance(self) -> dict:
        return {
            "source": "explicit_lexicon",
            "trigger": self.trigger,
            "charSpan": list(self.char_span),
            "rule": self.entry.rule,
        }


class Lexicon:
    def __init__(self, path: str | Path, analyzer: Analyzer):
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.version: str = data.get("lexiconVersion", "0.0.0")
        self.lexicon_id: str = data.get("lexiconId", "layer1")
        self.categories: dict = data["categories"]
        self.analyzer = analyzer
        self.entries: list[LexEntry] = []
        self._by_form: dict[str, list[LexEntry]] = {}
        self._by_alt: dict[str, list[LexEntry]] = {}
        for raw in data["entries"]:
            cat = self.categories.get(raw["category"], {})
            e = LexEntry(
                lemma=raw["lemma"], pos=raw["pos"], category=raw["category"], value=raw.get("value", {}),
                ex=raw.get("ex", ""), src=raw.get("src", "draft"), alt=tuple(raw.get("alt", [])),
                rule_name=cat.get("rule", f"{raw['category']}Lexicon"), slot=cat.get("slot"),
                next_forms=tuple(raw.get("next", [])),
            )
            self.entries.append(e)
            self._by_form.setdefault(e.lemma, []).append(e)
            for form in e.alt:  # 합성어·파생어 형태(보라색, 윙윙거리)는 품사를 따지지 않는다
                self._by_alt.setdefault(form, []).append(e)

    # ── 매칭 ────────────────────────────────────────────────────────────────
    def _candidates(self, form: str, base_tag: str, next_tok: Token | None) -> list[LexEntry]:
        out = [e for e in self._by_form.get(form, []) if base_tag in COMPAT.get(e.pos, {e.pos})]
        if base_tag in CONTENT_BASE_TAGS:
            out += self._by_alt.get(form, [])
        # Kiwi가 '촉촉하/VA'처럼 어근+하를 한 형태로 낸 경우 → 어근 항목
        if base_tag in ("VA", "VV") and form.endswith("하") and len(form) > 1:
            out += [e for e in self._by_form.get(form[:-1], []) if e.pos in ("XR", "NNG", "MAG")]
        # '탁/XR + 하/XSA' 처럼 갈라 낸 경우 → '탁하/VA' 항목
        if base_tag in ("XR", "NNG", "MAG") and next_tok is not None \
                and next_tok.form == "하" and next_tok.base_tag in ("XSA", "XSV"):
            out += [e for e in self._by_form.get(form + "하", []) if e.pos in ("VA", "VV")]
        seen, uniq = set(), []
        for e in out:
            if e.key not in seen:
                seen.add(e.key)
                uniq.append(e)
        return uniq

    def hits(self, text: str) -> list[Hit]:
        text = normalize(text)
        toks = self.analyzer.tokens(text)
        hits: list[Hit] = []
        skip_next = False
        for i, tok in enumerate(toks):
            if skip_next:
                skip_next = False
                continue
            form, base, start, end = tok.form, tok.base_tag, tok.start, tok.end
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            # 부정 접두사 + 명사 합치기: 불/XPN + 투명/NNG → 불투명
            if base == "XPN" and form in NEG_PREFIXES and nxt is not None and nxt.base_tag in ("NNG", "XR"):
                merged = form + nxt.form
                if merged in self._by_form or merged in self._by_alt:
                    form, base, end = merged, "NNG", nxt.end
                    skip_next = True
                    nxt = toks[i + 2] if i + 2 < len(toks) else None
            for e in self._candidates(form, base, nxt):
                if e.next_forms and (nxt is None or nxt.form not in e.next_forms):
                    continue
                if e.category == "self_reference":
                    prev = toks[i - 1] if i > 0 else None
                    if prev is None or prev.base_tag not in ("ETM", "MM"):
                        continue  # '저는 답답해요'의 '저'는 화자일 뿐, part 묘사가 아님
                if e.pos in PREDICATE_TAGS or base in ("VA", "VV"):
                    trigger = eojeol_at(text, start, end)
                    s = text.find(trigger, max(0, start - len(trigger)))
                    span = (s, s + len(trigger)) if s >= 0 else (start, end)
                else:
                    trigger, span = text[start:end], (start, end)
                hits.append(Hit(
                    entry=e, trigger=trigger, char_span=span, token_index=i,
                    negated=self._negated(toks, i), change=self._change(toks, i),
                ))
        return hits

    @staticmethod
    def _negated(toks: list[Token], i: int) -> bool:
        prev = toks[i - 1] if i > 0 else None
        if prev is not None and (prev.form, prev.base_tag) in PRE_NEGATORS:
            return True
        for t in toks[i + 1: i + 7]:
            if t.base_tag in ("SF", "SP"):
                break
            if (t.form, t.base_tag) in NEGATORS:
                return True
            # 다른 체언·용언이 나오면 그 뒤의 부정은 그 말의 것이다.
            # ('회색이고 무겁지 않아요'에서 '않'은 '무겁'의 부정). 부사는 통과('전혀 없어요').
            if t.base_tag in ("NNG", "NNP", "VA", "VV", "XR"):
                break
        return False

    @staticmethod
    def _change(toks: list[Token], i: int) -> str | None:
        """작/VA + 어/EC + 지/VX → 작아지다(becoming)."""
        if toks[i].base_tag != "VA" or i + 2 >= len(toks):
            return None
        a, b = toks[i + 1], toks[i + 2]
        if a.base_tag == "EC" and a.form in ("어", "아", "여") and b.form == "지" and b.base_tag == "VX":
            return "becoming"
        return None

    # ── 편의 함수 ────────────────────────────────────────────────────────────
    def keys(self, text: str) -> set[str]:
        return {h.entry.key for h in self.hits(text)}

    def categories_in(self, text: str) -> set[str]:
        return {h.entry.category for h in self.hits(text)}

    def info(self) -> dict:
        return {"lexiconId": self.lexicon_id, "lexiconVersion": self.version, "entries": len(self.entries)}
