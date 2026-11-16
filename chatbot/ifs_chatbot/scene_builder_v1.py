"""확정 텍스트 → SceneSpec v2.1 — 개선 매핑 v1 (화이트박스. 학습·LLM·임베딩 없음).

v0(scene_builder.py)는 그대로 두고 비교 설계(docs/research-design.md 3절)를 위해 따로 만든 매핑이다.
같은 확정 텍스트(+ 같은 meta 인자)는 언제나 같은 dict, 같은 파일 바이트가 된다(시각·난수 없음).

층과 규칙(자세한 표는 docs/scene-spec-mapping.md 7절, 실패 유형 대응은 docs/mapping-v1.md):
  0층  Kiwi 형태소 + 어절·문장·절 나누기                                         Doc
  1층  사전(v0 + layer1_lexicon.v1.json 오버레이) + 어절 표면형 규칙               scene_params.v1.json
       색 이름·색 수식(연한/짙은 …)·띠는 색(누르스름)·수치 단위·비교 크기·공간 높이어·투명/가림 표현
  2층  직유 표지 → 원천 명사(합성어는 뒷부분) → 형태 프로토타입
  3층  감정어 V/A/D, 신체 부위 높이 → _inferred(값 자리 아님)
  범위 규칙  회상 문장·배경 사물·부분(테두리·안쪽)·차원 주제('색은')·때(처음엔/지금은)
             ·부정·자기 정정·모름 → 값에서 빼고 보존 필드에 원문 그대로 남긴다
  병합  차원 주제 > 부분(전체·겉 > 안쪽) > 지금 > 1층 > 2층 > 측정 > 비교 > 사전 > 구체어 > 먼저 말함
  퍼지  자모 편집거리 일치는 값이 아니다(원칙 2). _alternatives(needs_confirmation)·_needsConfirmation에만 남는다
  보존  값이 되지 않은 말은 _unmatched·_unmapped·_negated·_alternatives·_context·_parts·_uncertain에,
        확정 텍스트 전체는 절 단위 색인 _clauses(charSpan + 원문)에 남는다. 읽지 못한 말이 결과에서 사라지지 않는다.

형식: shared/schemas/scene-spec.v2.1.json (v2.0 상위 호환)
"""
from __future__ import annotations

import copy
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .extract import CONTENT_TAGS, FUNCTION_LEMMAS
from .jamo import decompose, levenshtein
from .korean import Analyzer, Token
from .lexicon import Hit, Lexicon
from .paths import shared
from .scene_builder import dumps, normalize_confirmed, write_spec  # noqa: F401 (같은 저장 방식)
from .scene_spec import SLOT_PATHS, text_hash

BUILDER_VERSION = "1.1.0"      # 1.1.0: 2단계 독립 검토(T3) 반영 — 퍼지 일치를 값에 쓰지 않음, 품사·구문 범위 규칙(docs/mapping-v1.md 5절)
BUILDER_ID = f"scene-spec-builder-v1/{BUILDER_VERSION}"
SPEC_VERSION = "2.1.0"
MAPPER_ID = "v1"

# 어절 경계가 되는 기호. 이모지(W_EMOJI)도 띄어쓰기처럼 어절을 끊는다('🔴빨간🔴공' → 빨간 · 공)
PUNCT_TAGS = {"SF", "SP", "SS", "SE", "SO", "SW", "W_EMOJI"}
NOUN_TAGS = {"NNG", "NNP"}
NOUNISH_TAGS = {"NNG", "NNP", "NNB", "NR", "SN", "NP"}
SIMILE_SKIP_TAGS = ("JKS", "JKB", "JX", "VCP", "ETM", "JKO")
# 절을 끊는 연결 어미. 대조·전환 어미(-더니 · -던데)도 절 경계다('모르겠더니 지금은 빨개요'의 모름은 앞 절에만)
CLAUSE_EC = {"고", "는데", "ᆫ데", "은데", "지만", "면서", "으면서", "으며", "며", "어서", "아서", "여서", "서", "다가",
             "니까", "으니까", "는데요", "더니", "던데"}
# 색 낱말로 받는 품사: 색 어간이 시작하는 형태소가 형용사·어근이거나, 명사 안에 색 어간이 다 들어 있어야 한다
COLOR_PRED_TAGS = {"VA", "XR"}
NEGATOR_FORMS = ("않", "안", "못")
TOPIC_PARTICLES = {"은", "는", "ᆫ", "도", "이", "가", "만"}
LOC_PARTICLES = {"에", "에서", "서", "로", "으로", "까지"}
SENT_END_FORMS = {"요", "이요"}
_ORDER = {p: i for i, p in enumerate(SLOT_PATHS)}

# 쓰는 범주(색은 표면형 규칙이 맡는다)
SKIP_LEXICON_CATEGORIES = {"color", "dimension"}


def _r(x: float) -> float:
    return round(min(1.0, max(0.0, float(x))), 3)


def load_lexicon_v1(analyzer: Analyzer, base: str | Path | None = None, overlay: str | Path | None = None) -> Lexicon:
    """v0 사전 + v1 오버레이를 합친 1층 사전. v0 파일은 읽기만 한다."""
    base_p = Path(base or shared("lexicon", "layer1_lexicon.v0.json"))
    over_p = Path(overlay or shared("lexicon", "layer1_lexicon.v1.json"))
    data = json.loads(base_p.read_text(encoding="utf-8"))
    ov = json.loads(over_p.read_text(encoding="utf-8"))
    removed = {(r["category"], r["lemma"]) for r in ov.get("remove", [])}
    keys = {(e["category"], e["lemma"], e["pos"]) for e in ov["entries"]}
    entries = [e for e in data["entries"]
               if (e["category"], e["lemma"]) not in removed and (e["category"], e["lemma"], e["pos"]) not in keys]
    merged = {**data, "lexiconId": ov.get("lexiconId", data.get("lexiconId")),
              "lexiconVersion": ov["lexiconVersion"],
              "categories": {**data["categories"], **ov.get("categories", {})},
              "entries": entries + ov["entries"]}
    lex = Lexicon(over_p, analyzer, data=merged)
    lex.base_info = f"{data.get('lexiconId')}@{data.get('lexiconVersion')}"   # type: ignore[attr-defined]
    return lex


# ── 0층: 어절·문장·절 ──────────────────────────────────────────────────────────
class Doc:
    """확정 텍스트의 토큰을 어절(띄어쓰기·문장부호 단위)·문장·절로 묶는다."""

    def __init__(self, text: str, toks: list[Token]):
        self.text, self.toks = text, toks
        n = len(toks)
        self.eoj = [0] * n
        self.eojeols: list[list[int]] = []
        for i, t in enumerate(toks):
            new = i == 0
            if i:
                p = toks[i - 1]
                gap = text[p.end:t.start] if t.start > p.end else ""
                new = any(ch.isspace() for ch in gap) or t.base_tag in PUNCT_TAGS or p.base_tag in PUNCT_TAGS
            if new:
                self.eojeols.append([i, i])
            else:
                self.eojeols[-1][1] = i
            self.eoj[i] = len(self.eojeols) - 1
        self.line = [text.count("\n", 0, t.start) for t in toks]
        self.sent = [0] * n
        self.clause = [0] * n
        s = c = 0
        for i, t in enumerate(toks):
            if i:
                p = toks[i - 1]
                last_of_eoj = self.eoj[i] != self.eoj[i - 1]
                sent_break = (self.line[i] != self.line[i - 1] or p.base_tag == "SF" or (p.base_tag == "SE")
                              or (last_of_eoj and p.base_tag == "EF")
                              or (last_of_eoj and p.form in SENT_END_FORMS and p.base_tag in ("EC", "JX", "EF")))
                if sent_break:
                    s += 1
                    c += 1
                elif p.base_tag == "SP" or (last_of_eoj and p.base_tag == "EC" and p.form in CLAUSE_EC):
                    c += 1
            self.sent[i], self.clause[i] = s, c

    # 어절
    def is_punct_eoj(self, e: int) -> bool:
        a, b = self.eojeols[e]
        return all(self.toks[k].base_tag in PUNCT_TAGS for k in range(a, b + 1))

    def espan(self, e: int) -> tuple[int, int]:
        a, b = self.eojeols[e]
        return self.toks[a].start, max(self.toks[k].end for k in range(a, b + 1))

    def etext(self, e: int) -> str:
        s, t = self.espan(e)
        return self.text[s:t]

    def etoks(self, e: int) -> range:
        a, b = self.eojeols[e]
        return range(a, b + 1)

    def eoj_clause(self, e: int) -> int:
        return self.clause[self.eojeols[e][0]]

    def eoj_sent(self, e: int) -> int:
        return self.sent[self.eojeols[e][0]]

    def toks_in(self, s: int, e: int) -> list[int]:
        return [i for i, t in enumerate(self.toks) if t.start < e and s < max(t.end, t.start + 1)]

    def clause_toks(self, c: int) -> list[int]:
        return [i for i in range(len(self.toks)) if self.clause[i] == c]

    def clause_span(self, c: int) -> tuple[int, int]:
        ids = self.clause_toks(c)
        return self.toks[ids[0]].start, max(self.toks[k].end for k in ids)


@dataclass
class Cand:
    path: str
    value: object
    tok: int
    start: int
    provs: list
    layer: int = 1
    klass: int = 2          # 0 수치 단위 · 1 비교·구 규칙 · 2 사전 · 3 퍼지
    sub: int = 0            # 슬롯별 순위(움직임: 상태 1 / 신체: 일반어 1–2 / 위치: 방향어 1)
    status: str = "ok"      # ok | context | corrected | uncertain
    reason: str | None = None
    part: str | None = None
    part_class: str | None = None
    dim_topic: bool = False
    tense: int = 0          # +1 지금 · −1 처음엔/~했다가
    attributive: bool = False
    kind: str = "lexicon"
    meta: dict = field(default_factory=dict)


class SceneSpecBuilderV1:
    mapper_id = MAPPER_ID

    def __init__(self, analyzer: Analyzer, lexicon: Lexicon | None = None, params_path: str | Path | None = None,
                 vad_path: str | Path | None = None):
        self.analyzer = analyzer
        self.lexicon = lexicon or load_lexicon_v1(analyzer)
        self.params = json.loads(Path(params_path or shared("lexicon", "scene_params.v1.json")).read_text(encoding="utf-8"))
        vad = json.loads(Path(vad_path or shared("lexicon", "vad_ko.v0.json")).read_text(encoding="utf-8"))
        self.vad_info = f"{vad['lexiconId']}@{vad['lexiconVersion']}"
        self.vad = {e["lemma"]: e for e in vad["entries"]}
        p = self.params
        self.layer1: dict[str, list[dict]] = p["layer1"]
        self.prototypes: dict[str, str] = p["layer2"]["prototypes"]
        self.with_modifier: bool = p["layer2"].get("vehicleIncludesModifier", True)
        self.still_lemmas = set(p["negation"]["stillWhenNegated"])
        self.l3_targets: list[dict] = p["layer3"]["targets"]
        self.body_height: dict[str, float] = p["bodyPartHeight"]["values"]
        v = p["v1"]
        self.v = v
        self.colors = {k: tuple(x) for k, x in v["colorTerms"].items()}
        self.color_stems = sorted(self.colors, key=lambda s: (-len(s), s))
        self.tints = {k: tuple(x) for k, x in v["colorTints"].items()}
        self.tint_stems = sorted(self.tints, key=lambda s: (-len(s), s))
        self.color_suffixes = sorted(v["colorSuffixes"], key=lambda s: (-len(s), s))
        self.color_mods = {w: kind for kind, ws in v["colorModifiers"].items() for w in ws}
        self.strong = set(v["degreeAdverbs"]["strong"])
        self.weak = set(v["degreeAdverbs"]["weak"])
        self.k = v["degreeAdverbs"]["k"]
        self.background = set(v["backgroundNouns"])
        self.part_class = {w: cls for cls, ws in v["partNouns"].items() for w in ws}
        self.part_scoped = set(v["partScopedSlots"])
        self.dim_topics: dict[str, str] = v["dimensionTopics"]
        self.refs: dict[str, float] = v["referenceObjects"]
        self.length_refs: dict[str, float] = v["lengthReferences"]
        self.cover: dict[str, float] = v["coverObjects"]
        self.body_general: dict[str, int] = v["bodyGeneral"]
        self.layer_explicit = set(v["layerExplicit"])
        self.body_forms = {f for e in self.lexicon.entries if e.category == "body_part" for f in (e.lemma, *e.alt)}
        self._fuzzy_index = self._build_fuzzy_index()
        unit_alt = "|".join(sorted(map(re.escape, v["units"]), key=lambda s: (-len(s), s)))
        num_alt = "|".join(sorted(map(re.escape, v["nativeNumbers"]), key=lambda s: (-len(s), s)))
        approx = "|".join(sorted(map(re.escape, v["approxWords"]), key=lambda s: (-len(s), s)))
        # '두 뼘 반' · '1미터 반' = 수 + 0.5 단위(덧셈). '반' 뒤에는 쯤·정도·가량이나 한글 아닌 글자만 온다('반투명' 제외)
        self._measure_re = re.compile(
            rf"(?:(?:{approx})\s*)?(\d+(?:\.\d+)?|{num_alt})\s*({unit_alt})(?![A-Za-z])"
            rf"(?:\s*(반)(?=쯤|정도|가량|[^가-힣]|$))?(?:\s*(쯤|정도|가량|남짓))?")

    # ── 외부 정보 ───────────────────────────────────────────────────────────────
    @classmethod
    def from_runtime(cls, rt) -> "SceneSpecBuilderV1":
        return cls(rt.analyzer)

    def info(self) -> dict:
        return {"builder": BUILDER_ID, "specVersion": SPEC_VERSION, "lexicons": self._lexicons(), "mapper": MAPPER_ID}

    def _lexicons(self) -> dict:
        return {"layer1": f"{self.lexicon.lexicon_id}@{self.lexicon.version}",
                "layer1Base": getattr(self.lexicon, "base_info", ""),
                "sceneParams": f"{self.params['lexiconId']}@{self.params['lexiconVersion']}",
                "vad": self.vad_info}

    # ── 진입점 ─────────────────────────────────────────────────────────────────
    def build(self, text: str, *, session_id: str | None = None, participant_id: str | None = None,
              condition: str | None = None) -> dict:
        text = normalize_confirmed(text)
        toks = self.analyzer.tokens(text)
        doc = Doc(text, toks)
        doc.coord_neg = self._coord_negated(doc)       # type: ignore[attr-defined]
        consumed: set[int] = set()
        records: dict[str, list] = defaultdict(list)     # 보존 필드
        cands: list[Cand] = []

        context_sents = self._context_sentences(doc)
        similes = self._similes(text, toks)

        # 1층 표면형 규칙(먼저 돌아 토큰을 차지한다)
        cands += self._directions(doc, consumed, records)
        cands += self._measurements(doc, consumed, records)
        cands += self._comparatives(doc, consumed, records)
        cands += self._heights(doc, consumed)
        cands += self._occlusion(doc, consumed)
        cands += self._colors(doc, consumed, records)
        # 1층 사전
        hits = [h for h in self.lexicon.hits(text)]
        hit_toks = {h.token_index for h in hits}
        body_any = any(h.entry.category == "body_part" and h.token_index not in consumed
                       and doc.sent[h.token_index] not in context_sents for h in hits)
        unmapped: list[dict] = []
        negated: list[dict] = []
        cands += self._lexicon_cands(doc, hits, consumed, similes, body_any, unmapped, negated, records)
        # 2층 직유
        proto_toks: set[int] = set()
        cands += self._simile_cands(doc, hits, similes, consumed, unmapped, proto_toks)
        # 퍼지
        fuzzy_toks: set[int] = set()
        cands += self._fuzzy(doc, hit_toks | consumed | proto_toks, fuzzy_toks)
        cands += self._fuzzy_eojeol(doc, cands, consumed | proto_toks | fuzzy_toks, fuzzy_toks)

        # 범위 규칙
        self._scope(doc, cands, context_sents, similes)
        uncertain_paths = self._uncertainty(doc, cands, records)
        self._corrections(doc, cands)
        self._dimension_negations(doc, negated)

        values, provenance, alternatives = self._merge(cands, uncertain_paths, records)
        for c in records.pop("_negatedCands", []):
            negated.append({"lemma": c.meta.get("match", {}).get("stem", c.provs[0]["trigger"]), "category": "color",
                            "_provenance": c.provs[0]})
        for c in cands:
            if c.status == "context":
                records["_context"].append({"text": c.provs[0]["trigger"], "charSpan": c.provs[0]["charSpan"],
                                            "reason": c.reason, "path": c.path, "value": c.value,
                                            "rule": c.provs[0]["rule"]})
        for m in records["_measurements"]:
            m["usedFor"] = None
            for path, provs in provenance.items():
                if any(pv["charSpan"] == m["charSpan"] for pv in provs):
                    m["usedFor"] = path
        inferred = self._layer3(hits, values, provenance, consumed, context_sents, doc)
        unmatched = self._unmatched(doc, hits, consumed | proto_toks | fuzzy_toks)
        clauses = self._clauses(doc, provenance, context_sents)
        needs = [{"path": c.path, "trigger": c.provs[0]["trigger"], "charSpan": c.provs[0]["charSpan"],
                  "reason": "fuzzy_lexicon", "matched": c.meta["matched"]}
                 for c in records.pop("_needsConfirmation", [])]

        groups: dict[str, dict] = {}
        for path in SLOT_PATHS:
            g, k = path.split(".")
            groups.setdefault(g, {})[k] = values.get(path)

        def sort_span(items, *keys):
            return sorted(items, key=lambda x: (x["charSpan"][0], x["charSpan"][1], *[str(x.get(k)) for k in keys]))

        return {
            "meta": {
                "specVersion": SPEC_VERSION,
                "participantId": participant_id,
                "sessionId": session_id,
                "condition": condition,
                "sourceTextHash": text_hash(text),
                "pipeline": {"builder": BUILDER_ID,
                             "analyzer": "kiwi" if self.analyzer.available else "fallback-regex",
                             "lexicons": self._lexicons()},
                "mapping": {"requested": MAPPER_ID, "used": MAPPER_ID, "fallbackReason": None},
            },
            **groups,
            "_provenance": provenance,
            "_unmatched": unmatched,
            "_unmapped": sorted(unmapped, key=lambda u: (u["_provenance"]["charSpan"][0], u["lemma"], u["category"])),
            "_negated": sorted(negated, key=lambda n: (n["_provenance"]["charSpan"][0], n["lemma"], n["category"])),
            "_alternatives": alternatives,
            "_inferred": inferred,
            "_context": sort_span(records["_context"], "path", "reason"),
            "_parts": sort_span(records["_parts"], "path"),
            "_uncertain": sort_span(records["_uncertain"]),
            "_measurements": sort_span(records["_measurements"], "dimension"),
            "_direction": sort_span(records["_direction"]),
            "_needsConfirmation": sort_span(needs, "path"),
            "_clauses": clauses,
        }

    # ── 도우미 ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _prov(source: str, text: str, s: int, e: int, rule: str, **extra) -> dict:
        p = {"source": source, "trigger": text[s:e], "charSpan": [s, e], "rule": rule}
        p.update(extra)
        return p

    def _eoj_prov(self, doc: Doc, i: int, rule: str, source: str = "explicit_lexicon") -> dict:
        s, e = doc.espan(doc.eoj[i])
        return self._prov(source, doc.text, s, e, rule)

    def _tok_prov(self, doc: Doc, i: int, rule: str, source: str = "explicit_lexicon") -> dict:
        t = doc.toks[i]
        return self._prov(source, doc.text, t.start, t.end, rule)

    def _degree(self, doc: Doc, i: int) -> tuple[float, int | None]:
        """앞 어절(같은 절, 부사 어절만 건너서 최대 2개)의 정도 부사 → 배율 k와 그 어절."""
        e = doc.eoj[i]
        for back in (1, 2):
            f = e - back
            if f < 0 or doc.eoj_clause(f) != doc.clause[i] or doc.is_punct_eoj(f):
                return 1.0, None
            w = doc.etext(f)
            if w in self.strong:
                return self.k["strong"], f
            if w in self.weak:
                return self.k["weak"], f
            if not all(doc.toks[k].base_tag in ("MAG",) for k in doc.etoks(f)) and not w.endswith("게"):
                return 1.0, None
        return 1.0, None

    def _apply_degree(self, path: str, value: float, k: float, key: str | None = None) -> float:
        c = (self.v.get("scalarCentersByKey", {}).get(path) or {}).get(key, self.v["scalarCenters"].get(path))
        if c is None or k == 1.0:
            return value
        return _r(c + (value - c) * k)

    def _map(self, target: dict, value: dict):
        key = value.get(target["key"])
        if key is None:
            return None
        tr = target.get("transform")
        if tr == "logScale":
            return round(min(1.0, max(0.0, 0.5 + math.log2(key) / 4)), 3), f"logScale({key})"
        if tr == "enum":
            return key, key
        v = target.get("values", {}).get(key)
        return (v, key) if v is not None else None

    def size_from_meters(self, m: float) -> float:
        s = self.v["size"]
        return _r(0.5 + math.log2(max(m, 1e-6) / s["referenceMeters"]) / s["octavesPerUnit"])

    def distance_from_meters(self, m: float) -> float:
        d = self.v["distance"]
        return _r((m - d["minMeters"]) / (d["maxMeters"] - d["minMeters"]))

    def _next_eoj_same_clause(self, doc: Doc, e: int) -> int | None:
        f = e + 1
        if f >= len(doc.eojeols) or doc.is_punct_eoj(f) or doc.eoj_clause(f) != doc.eoj_clause(e):
            return None
        return f

    def _head_noun(self, doc: Doc, e: int) -> tuple[str, int] | None:
        """관형 어절 e가 꾸미는 명사(명사구의 마지막 명사)."""
        f = self._next_eoj_same_clause(doc, e)
        if f is None:
            return None
        first = doc.eojeols[f][0]
        if doc.toks[first].base_tag not in NOUN_TAGS:
            return None
        head = None
        while f is not None:
            nouns = [k for k in doc.etoks(f) if doc.toks[k].base_tag in NOUN_TAGS]
            if not nouns:
                break
            head = nouns[-1]
            bare = all(doc.toks[k].base_tag in NOUN_TAGS | {"XSN"} for k in doc.etoks(f))
            nxt = self._next_eoj_same_clause(doc, f)
            if not bare or nxt is None or doc.toks[doc.eojeols[nxt][0]].base_tag not in NOUN_TAGS \
                    or doc.toks[doc.eojeols[nxt][0]].form in self.v["relationalNouns"]:
                break      # '벽 앞에'의 '앞'은 명사구의 머리가 아니라 위치 명사
            f = nxt
        return (doc.toks[head].form, head) if head is not None else None

    def _is_landmark(self, doc: Doc, k: int) -> bool:
        """명사 k 바로 뒤가 위치 명사('상자 위에' · '벽 앞에')면 그 명사는 형상이 아니라 자리 표지다."""
        e = doc.eoj[k]
        nxt = self._next_eoj_same_clause(doc, e)
        if nxt is None:
            return False
        first = doc.toks[doc.eojeols[nxt][0]]
        return first.base_tag in NOUN_TAGS and first.form in self.v["relationalNouns"]

    def _is_attributive(self, doc: Doc, e: int) -> bool:
        ts = [doc.toks[k] for k in doc.etoks(e)]
        if ts and ts[-1].base_tag == "ETM":
            return True
        return bool(ts) and all(t.base_tag in NOUN_TAGS | {"XSN", "MM"} for t in ts)

    def _coordinated_attributive(self, doc: Doc, e: int) -> int | None:
        """'크고 검은 돌' · '작고 둥글고 하얀 공' — 형용사 + '-고'로 이어진 관형 나열은 같은 머리 명사를 꾸민다.
        나열 끝의 관형 어절(…ETM) 번호를 돌려준다. '돌고 있는'(-고 있다)처럼 보조 용언이 오면 나열이 아니다."""
        toks = doc.toks
        f = e
        while True:
            ts = [toks[k] for k in doc.etoks(f)]
            if len(ts) < 2 or ts[-1].form != "고" or ts[-1].base_tag != "EC" or \
                    not any(t.base_tag in ("VA", "XSA") for t in ts[:-1]):
                return None
            g = f + 1
            if g >= len(doc.eojeols) or doc.is_punct_eoj(g) or doc.eoj_sent(g) != doc.eoj_sent(f):
                return None
            first = toks[doc.eojeols[g][0]]
            if first.base_tag in ("VX", "VCN") or first.form in NEGATOR_FORMS:
                return None
            if self._is_attributive(doc, g) and toks[doc.eojeols[g][1]].base_tag == "ETM":
                return g
            f = g

    def _is_background(self, noun: str) -> bool:
        return noun in self.background or any(len(b) >= 2 and noun.endswith(b) for b in self.background)

    def _topic(self, doc: Doc, i: int) -> tuple[str, int] | None:
        """같은 절에서 i 앞의 주제·주어 명사(명사 + 은/는/도/이/가) 또는 부분 명사 + 처소 조사."""
        out = None
        weak = False      # 이/가·처소 조사 주어는 관계절('가장자리가 삭아가는 회색')의 관형형에서 끊긴다
        for j in doc.clause_toks(doc.clause[i]):
            if j >= i:
                break
            t = doc.toks[j]
            if t.base_tag == "ETM" and weak:
                out, weak = None, False
                continue
            if t.base_tag not in NOUN_TAGS | {"NNB"}:
                continue
            k = j + 1
            while k < len(doc.toks) and doc.toks[k].base_tag == "XSN":
                k += 1
            if k >= len(doc.toks) or k >= i:
                continue
            nt = doc.toks[k]
            if j > 0 and doc.toks[j - 1].form in self.body_forms and t.form in self.part_class:
                continue      # '가슴 안쪽에'의 안쪽은 몸 위치이지 형상의 부분이 아니다
            if (nt.base_tag in ("JX", "JKS") and nt.form in TOPIC_PARTICLES) or \
                    (t.form in self.part_class and nt.base_tag == "JKB" and nt.form in LOC_PARTICLES):
                out = (t.form, j)
                weak = nt.base_tag != "JX"
        return out

    def _context_sentences(self, doc: Doc) -> set[int]:
        """회상 문장: '~던 장면이요' · '~던 게 떠올라요' · '~던 오후요'. 형상이 아니라 떠올린 상황을 말한 문장."""
        cs = self.v["contextSentence"]
        out = set()
        toks = doc.toks
        for s in sorted(set(doc.sent)):
            ids = [i for i in range(len(toks)) if doc.sent[i] == s]
            forms = [(toks[i].form, toks[i].base_tag) for i in ids]
            recall = any(f in cs["recallVerbs"] and tg == "VV" for f, tg in forms)
            # '장면'은 떠올린 상황을 가리킬 때만 회상 표지다: '-던 장면' 관형절의 머리이거나, 같은 문장에 '떠오르다' 류가 있을 때.
            # 명사 하나만으로 문장 전체를 회상으로 돌리지 않는다('장면 속에 빨간 공이 있어요'는 형상 문장)
            if any(toks[i].form in cs["nouns"] and toks[i].base_tag in NOUN_TAGS
                   and (recall or (i > 0 and doc.sent[i - 1] == s and toks[i - 1].base_tag == "ETM"
                                   and toks[i - 1].form in cs["etm"])) for i in ids):
                out.add(s)
                continue
            etm = [i for i in ids if toks[i].form in cs["etm"] and toks[i].base_tag == "ETM"]
            if not etm:
                continue
            if recall:
                out.add(s)
                continue
            for i in etm:                       # '~던 오후요' · '~던거요': 던 + 상황 명사로 문장이 끝남
                k = i + 1
                if k < len(toks) and doc.sent[k] == s and toks[k].form in cs["situationNouns"] and \
                        all(toks[j].base_tag in ("JX", "VCP", "EF", "EC", "SF", "JKS") or toks[j].base_tag in PUNCT_TAGS
                            for j in ids if j > k):
                    out.add(s)
        return out

    # ── 1층 규칙: 방향어 ───────────────────────────────────────────────────────
    def _directions(self, doc: Doc, consumed: set[int], records) -> list[Cand]:
        words = self.v["directionWords"]
        for i, t in enumerate(doc.toks):
            if t.form not in words or t.base_tag not in NOUN_TAGS or i in consumed:
                continue
            e = doc.eoj[i]
            ids = [k for k in doc.etoks(e) if doc.toks[k].base_tag in NOUN_TAGS]
            depth = vertical = None
            for k in ids:
                f = doc.toks[k].form
                if f in ("앞", "앞쪽"):
                    depth = "front"
                elif f in ("뒤", "뒤쪽"):
                    depth = "behind"
                elif f in ("위", "위쪽"):
                    vertical = "up"
                elif f in ("아래", "아래쪽", "밑"):
                    vertical = "down"
            s, en = doc.espan(e)
            consumed.update(ids)
            records["_direction"].append({"text": doc.text[s:en], "charSpan": [s, en], "horizontal": words[t.form],
                                          "vertical": vertical, "depth": depth})
        return []

    # ── 1층 규칙: 수치 + 단위 ─────────────────────────────────────────────────
    def _measurements(self, doc: Doc, consumed: set[int], records) -> list[Cand]:
        out = []
        v = self.v
        text = doc.text
        for m in self._measure_re.finditer(text):
            num_s, unit = m.group(1), m.group(2)
            if m.start(1) > 0 and re.match(r"[가-힣A-Za-z0-9]", text[m.start(1) - 1]) and not num_s.isdigit():
                continue
            num = float(num_s) if re.match(r"\d", num_s) else float(v["nativeNumbers"][num_s])
            if m.group(3):                       # '두 뼘 반' — 단위 뒤의 반은 반 단위를 더한다
                num += 0.5
            meters = num * v["units"][unit]
            s, e = m.start(), m.end()
            ids = doc.toks_in(s, e)
            if not ids:
                continue
            dim, cue = self._measure_dimension(doc, ids, s, e)
            rec = {"text": text[s:e], "charSpan": [s, e], "kind": "number_unit", "meters": round(meters, 4),
                   "dimension": dim, "reference": None}
            records["_measurements"].append(rec)
            consumed.update(ids)
            anchor = ids[0]
            if dim == "size":
                val = self.size_from_meters(meters)
                rule = f"measure.{unit}>layout.size:{round(meters, 3)}m"
                out.append(Cand("layout.size", val, anchor, s, [self._prov("phrase_rule", text, s, e, rule)],
                                klass=0, kind="measure"))
            elif dim == "distance":
                val = self.distance_from_meters(meters)
                rule = f"measure.{unit}>layout.distance:{round(meters, 3)}m"
                out.append(Cand("layout.distance", val, anchor, s, [self._prov("phrase_rule", text, s, e, rule)],
                                klass=0, kind="measure"))
        return out

    def _measure_dimension(self, doc: Doc, ids: list[int], s: int, e: int) -> tuple[str, str | None]:
        v = self.v
        c = doc.clause[ids[0]]
        before = [k for k in doc.clause_toks(c) if k < ids[0]]
        for k in reversed(before):
            f = doc.toks[k].form
            if f in v["widthWords"]:
                return "width", f
            if f in v["sizeCueWords"]:
                return "size", f
            if f == "거리":
                return "distance", f
        # 바로 뒤: 처소 조사·방향어·떨어지다 → 거리 / 크기·만하다 → 크기
        last = max(ids)
        nxt = [k for k in range(last + 1, min(len(doc.toks), last + 4))]
        for k in nxt:
            t = doc.toks[k]
            if t.base_tag in ("SF", "SP"):
                break
            if t.form in ("크기", "짜리", "만"):
                return "size", t.form
            if t.form in ("앞", "뒤", "옆", "앞쪽", "뒤쪽", "옆쪽", "거리") or t.form.startswith("떨어") or t.form.startswith("멀"):
                return "distance", t.form
            if t.base_tag == "JKB" and t.form in ("에", "에서"):
                return "distance", t.form
        if before:
            pf = [doc.toks[k].form for k in before[-3:]]
            if any(f in ("앞", "뒤", "옆", "앞쪽", "뒤쪽") for f in pf):
                return "distance", "앞"
        # 같은 줄에 크기 말이 있으면 크기('구슬만큼 작아요. 한 2센티쯤?')
        ln = doc.line[ids[0]]
        line_toks = [k for k in range(len(doc.toks)) if doc.line[k] == ln and k not in ids]
        forms = {doc.toks[k].form for k in line_toks}
        if forms & {"크기", "작", "크", "만큼", "만", "커다랗", "조그맣", "지름"}:
            return "size", "line"
        if any(f.startswith("떨어") or f == "거리" for f in forms):
            return "distance", "line"
        return "unknown", None

    # ── 1층 규칙: 비교 크기·거리 ─────────────────────────────────────────────
    def _ref_noun(self, doc: Doc, i: int, table: dict[str, float]) -> tuple[str, int, float] | None:
        """i 토큰(명사)이 끝나는 명사구로 표를 찾는다. 앞 명사를 붙여 더 긴 표제어를 먼저('사람 머리' → '머리')."""
        t = doc.toks[i]
        if t.base_tag not in NOUN_TAGS:
            return None
        start = i
        j = i - 1
        while j >= 0 and doc.toks[j].base_tag in NOUN_TAGS and doc.clause[j] == doc.clause[i] and (i - j) <= 2:
            start = j
            j -= 1
        for a in range(start, i + 1):
            key = "".join(doc.toks[k].form for k in range(a, i + 1))
            key_sp = doc.text[doc.toks[a].start:t.end]
            for kk in (key_sp, key):
                if kk in table:
                    return kk, a, table[kk]
        for n in range(len(t.form) - 1, 1, -1):       # 한 토큰 합성어: '엄지손톱' → '손톱'
            if t.form[-n:] in table:
                return t.form[-n:], i, table[t.form[-n:]]
        return None

    @staticmethod
    def _half_at(doc: Doc, j: int, clause: int) -> int | None:
        """j에서 '(의) 반'이 시작하면 '반' 토큰 번호. '반투명'처럼 반이 다른 명사의 앞부분이면 아니다."""
        toks = doc.toks
        n = len(toks)
        if j < n and toks[j].form == "의" and toks[j].base_tag == "JKG":
            j += 1
        if j >= n or toks[j].form != "반" or toks[j].base_tag not in ("NNG", "NR") or doc.clause[j] != clause:
            return None
        nx = toks[j + 1] if j + 1 < n else None
        if nx is not None and nx.start == toks[j].end and nx.base_tag in NOUN_TAGS and nx.form != "정도":
            return None
        return j

    def _comparatives(self, doc: Doc, consumed: set[int], records) -> list[Cand]:
        out = []
        v = self.v
        cf = v["comparativeFactors"]
        toks, text = doc.toks, doc.text
        n = len(toks)
        for i, t in enumerate(toks):
            if i in consumed or t.base_tag not in NOUN_TAGS:
                continue
            j = i + 1
            while j < n and toks[j].base_tag == "XSN":
                j += 1
            if j >= n:
                continue
            pattern = factor = None
            mult = 1.0
            end_tok = None
            dist_hint = False
            ref = None
            # 개수 배수: 동전 두 개
            if toks[j].base_tag in ("MM", "NR", "SN") and j + 1 < n and toks[j + 1].form == "개":
                num = toks[j].form
                mult = float(num) if num.isdigit() else float(v["nativeNumbers"].get(num, 1))
                j += 2
            # 절반: 'N 반만 해요' · 'N의 반만큼' · 'N 반쯤' — 기준 사물의 0.5배
            hj = self._half_at(doc, j, doc.clause[i])
            half_only = False
            if hj is not None:
                mult *= 0.5
                j = hj + 1
                while j < n and toks[j].base_tag == "XSN":          # 반쯤
                    j += 1
                if j >= n or toks[j].form not in ("만", "만큼", "만치", "보다", "크기", "정도"):
                    half_only = True                                  # 'N 반쯤 돼요' — 반 자체가 비교 구조
            nj = toks[j] if j < n else None
            if nj is None and not half_only:
                continue
            # (1) 길이 기준: 팔 길이만큼
            if nj is not None and t.form == "길이" and nj.form in ("만큼", "만치", "정도"):
                r = self._ref_noun(doc, i - 1, self.length_refs) if i else None
                if r:
                    ref = (r[0] + " 길이", r[1], r[2])
                    pattern, end_tok, dist_hint = "length", j, True
            if pattern is None and nj is not None:
                if nj.form == "만" and nj.base_tag == "JX":
                    k = j + 1
                    after = text[nj.end:doc.espan(doc.eoj[j])[1]]
                    nxt_txt = doc.etext(doc.eoj[k]) if k < n else ""
                    if after[:1] in ("하", "한", "해", "했") or (k < n and doc.eoj[k] != doc.eoj[j]
                                                              and nxt_txt[:1] in ("하", "한", "해", "했")):
                        pattern, end_tok = "equal", k
                elif nj.form in ("만큼", "만치"):
                    pattern, end_tok = "equal", j
                elif nj.form == "보다":
                    k = j + 1
                    slight = much = False
                    while k < n and k <= j + 4:
                        tk = toks[k]
                        if tk.base_tag == "JX":
                            k += 1
                            continue
                        if tk.form in cf["slightWords"]:
                            slight = True
                        elif tk.form in cf["muchWords"]:
                            much = True
                        elif tk.form == "더":
                            pass
                        elif tk.base_tag in ("VA", "VV"):
                            if tk.form[:1] in cf["biggerStems"] or tk.form in cf["biggerStems"]:
                                factor = cf["muchBigger"] if much else cf["slightlyBigger"] if slight else cf["bigger"]
                            elif tk.form[:1] in cf["smallerStems"] or tk.form in cf["smallerStems"]:
                                factor = cf["muchSmaller"] if much else cf["slightlySmaller"] if slight else cf["smaller"]
                            break
                        else:
                            break
                        k += 1
                    if factor is not None:
                        pattern, end_tok = "than", k
                elif nj.form in ("크기", "정도") and nj.base_tag in NOUN_TAGS and doc.eoj[j] != doc.eoj[i]:
                    k = j
                    if nj.form == "크기" and k + 1 < n and toks[k + 1].form == "정도":
                        k += 1
                    pattern, end_tok = "equal", k
                elif nj.base_tag == "JKO":
                    k = j + 1
                    while k < n and toks[k].base_tag == "MAG":
                        k += 1
                    if k < n and toks[k].form in v["coverVerbs"] and toks[k].base_tag == "VV":
                        r = self._ref_noun(doc, i, self.cover)
                        if r:
                            ref = r
                            pattern, end_tok = "cover", k
                            k2 = k + 1
                            while k2 < n and toks[k2].base_tag in ("ETM", "EC") and k2 <= k + 1:
                                k2 += 1
                            if k2 < n and toks[k2].form in ("만큼", "정도"):
                                end_tok = k2
            if pattern is None and half_only:
                pattern, end_tok = "half", j - 1
            if pattern is None:
                continue
            # 비교 구 뒤의 절반: '주먹 크기의 반 (정도)'
            if hj is None and end_tok is not None:
                hk = self._half_at(doc, end_tok + 1, doc.clause[i])
                if hk is not None:
                    mult *= 0.5
                    end_tok = hk
                    while end_tok + 1 < n and (toks[end_tok + 1].base_tag == "XSN" or toks[end_tok + 1].form in ("정도", "가량")) \
                            and doc.clause[end_tok + 1] == doc.clause[i]:
                        end_tok += 1
            if ref is None:
                ref = self._ref_noun(doc, i, self.refs)
                if ref is None:
                    continue
            key, a, meters = ref
            # 앞 관형어(큰 수박)
            adj = 1.0
            fa = doc.eoj[a] - 1
            if fa >= 0 and doc.eoj_clause(fa) == doc.clause[a] and doc.etext(fa) in v["referenceAdjectives"]:
                adj = v["referenceAdjectives"][doc.etext(fa)]
                a = doc.eojeols[fa][0]
            m = meters * mult * adj * (factor or 1.0)
            # 폭·너비 주제면 전체 크기가 아니다
            topic = self._topic(doc, a)
            c = doc.clause[i]
            width = topic is not None and topic[0] in v["widthWords"]
            clause_forms = {toks[k].form for k in doc.clause_toks(c)}
            is_dist = dist_hint or any(f.startswith("떨어") or f == "거리" for f in clause_forms if f)
            s = toks[a].start
            e = toks[end_tok].end
            # 끝 어절 마무리: '만 해요' → 어절 끝까지
            e = max(e, doc.espan(doc.eoj[end_tok])[1]) if pattern in ("equal", "than") else e
            ids = [k for k in range(a, end_tok + 1)]
            consumed.update(ids)
            dim = "width" if width else ("distance" if is_dist else "size")
            rec = {"text": text[s:e], "charSpan": [s, e], "kind": "cover" if pattern == "cover" else "reference",
                   "meters": round(m, 4), "dimension": dim, "reference": key}
            records["_measurements"].append(rec)
            if dim == "width":
                continue
            if dim == "distance":
                val = self.distance_from_meters(m)
                path = "layout.distance"
            else:
                val = self.size_from_meters(m)
                path = "layout.size"
            rule = f"compare.{pattern}.{key}>{path}:{round(m, 3)}m"
            out.append(Cand(path, val, a, s, [self._prov("phrase_rule", text, s, e, rule)], klass=1, kind="compare"))
        return out

    # ── 1층 규칙: 공간 높이어 ─────────────────────────────────────────────────
    def _heights(self, doc: Doc, consumed: set[int]) -> list[Cand]:
        out = []
        hp = self.v["heightPhrases"]
        toks, text = doc.toks, doc.text
        n = len(toks)

        def add(a: int, b: int, val: float, rule: str, eat: list[int]):
            s, e = toks[a].start, toks[b].end
            consumed.update(eat)
            out.append(Cand("layout.verticalOffset", _r(val), a, s,
                            [self._prov("phrase_rule", text, s, e, f"height.{rule}>layout.verticalOffset:{_r(val)}")],
                            klass=1, kind="height"))

        for i, t in enumerate(toks):
            if i in consumed or t.base_tag not in NOUN_TAGS:
                continue
            nxt = toks[i + 1] if i + 1 < n else None
            # X 높이(에) — 눈높이 · 가슴 높이 · 무릎 높이
            if nxt is not None and nxt.form == "높이" and t.form in hp["bodyLevel"] and doc.clause[i + 1] == doc.clause[i]:
                after = toks[i + 2] if i + 2 < n else None
                if after is None or not (after.base_tag in ("JX", "JKS") and after.form in TOPIC_PARTICLES):
                    val = hp["eyeLevel"] if t.form == "눈" else hp["bodyLevel"][t.form]
                    add(i, i + 1, val, f"{t.form}높이", [i, i + 1])
                    continue
            # 머리 (바로) 위
            if t.form == "머리":
                k = i + 1
                while k < n and toks[k].base_tag == "MAG" and toks[k].form in ("바로", "한참", "조금", "살짝"):
                    k += 1
                if k < n and toks[k].form in ("위", "위쪽") and doc.clause[k] == doc.clause[i]:
                    add(i, k, hp["aboveHead"], "머리위", [k])
                    continue
            # 발밑 · 발 (바로) 밑/아래 · 발치
            if t.form in ("발밑", "발치"):
                add(i, i, hp["underFoot"], t.form, [])
                continue
            if t.form == "발":
                k = i + 1
                while k < n and toks[k].base_tag == "MAG" and toks[k].form in ("바로",):
                    k += 1
                if k < n and toks[k].form in ("밑", "아래") and doc.clause[k] == doc.clause[i]:
                    add(i, k, hp["underFoot"], "발밑", [k])
                    continue
            # 바닥·천장(에·에서·가까이·근처·쪽·위)
            if t.form in ("바닥", "천장") and nxt is not None and (
                    (nxt.base_tag == "JKB" and nxt.form in ("에", "에서")) or nxt.form in ("가까이", "근처", "쪽", "위", "아래")):
                eat = [i] + ([i + 1] if nxt.form in ("가까이", "근처", "쪽", "위", "아래") else [])
                add(i, eat[-1], hp["floor"] if t.form == "바닥" else hp["ceiling"], t.form, eat)
        return out

    # ── 1층 규칙: 투명·가림 ───────────────────────────────────────────────────
    def _occlusion(self, doc: Doc, consumed: set[int]) -> list[Cand]:
        out = []
        oc = self.v["occlusion"]
        subj = "|".join(sorted(map(re.escape, oc["subjects"]), key=lambda s: (-len(s), s)))
        rx_opaque = re.compile(rf"({subj})(이|가|은|는)?\s*(거의|잘|하나도|전혀)?\s*안\s*보[이일여]")
        rx_clear = re.compile(rf"({subj})(이|가|은|는)?\s*(다|훤히|그대로)\s*보[이여]")
        text = doc.text
        for rx, val, name in ((rx_opaque, oc["opaque"], "occluded"), (rx_clear, oc["clear"], "see_all")):
            for m in rx.finditer(text):
                s, e = m.start(), m.end()
                ids = doc.toks_in(s, e)
                if not ids or any(k in consumed for k in ids):
                    continue
                # 'X 만큼/정도로 짙어요' — 뒤 서술어까지 이 규칙이 차지한다
                last = max(ids)
                e2 = doc.espan(doc.eoj[last])[1]
                k = last + 1
                eat = set(ids) | set(doc.etoks(doc.eoj[last]))
                while k < len(doc.toks) and doc.clause[k] == doc.clause[last] and k <= last + 4:
                    tk = doc.toks[k]
                    if tk.form in ("만큼", "정도"):
                        eat.update(doc.etoks(doc.eoj[k]))
                        e2 = doc.espan(doc.eoj[k])[1]
                    elif tk.base_tag in ("VA", "VV", "XR") and tk.form in ("짙", "진하", "탁하", "뿌옇", "탁", "흐리"):
                        eat.update(doc.etoks(doc.eoj[k]))
                        e2 = doc.espan(doc.eoj[k])[1]
                        break
                    k += 1
                consumed.update(eat)
                out.append(Cand("material.opacity", val, ids[0], s,
                                [self._prov("phrase_rule", text, s, e2, f"opacity.{name}>material.opacity:{val}")],
                                klass=1, kind="opacity"))
        # 반투명(Kiwi: 반/NNG + 투명/NNG, 띄어 쓴 '반 투명'은 반/XPN)
        for i, t in enumerate(doc.toks[:-1]):
            nx = doc.toks[i + 1]
            if t.form == "반" and nx.form == "투명" and text[t.end:nx.start].strip() == "" and i not in consumed:
                consumed.update({i, i + 1})
                out.append(Cand("material.opacity", 0.5, i, t.start,
                                [self._prov("explicit_lexicon", text, t.start, nx.end,
                                            "opacityLexicon.반투명>material.opacity:translucent")], kind="opacity"))
        return out

    # ── 1층 규칙: 색 ─────────────────────────────────────────────────────────
    def _match_color(self, w: str):
        prefixes = self.v["colorPrefixes"]
        for plen in (0, 1):
            if plen and (not w or w[0] not in prefixes):
                continue
            rest = w[plen:]
            for stem in self.tint_stems:
                if rest.startswith(stem):
                    return {"kind": "tint", "stem": stem, "prefix": w[:plen], "len": plen + len(stem)}
            for stem in self.color_stems:
                if not rest.startswith(stem):
                    continue
                tail = rest[len(stem):]
                suf = next((x for x in self.color_suffixes if tail.startswith(x)), "")
                need = len(self.colors[stem]) > 4 and self.colors[stem][4] == "suffix"
                if need and not suf:
                    continue
                return {"kind": "term", "stem": stem, "prefix": w[:plen], "len": plen + len(stem) + len(suf),
                        "suffix": suf}
        return None

    def _full_color_lemma(self, form: str, tag: str | None = None):
        """형태소 원형이 색 어간(또는 접두 + 어간) 그대로인가: 파랗 · 노래지 · 새빨갛.
        동사(VV)는 Kiwi가 '-어지다' 변화 동사를 한 형태로 낸 경우도 받는다: 붉어지 · 빨개지 = 색 활용형 + 지."""
        m = self._match_color(form)
        if m is not None and m["len"] == len(form):
            return m
        if tag == "VV" and form.endswith("지") and len(form) >= 2:
            m = self._match_color(form[:-1])
            if m is not None and m["len"] == len(form) - 1:
                return m
        return None

    def _color_pos_ok(self, doc: Doc, e: int, a: int, b: int) -> bool:
        """어절 e의 [a, b) 글자(색 어간)가 색 낱말로 쓰였는가 — 품사 조건.
        어간이 시작하는 형태소가 형용사·어근(VA·XR)이면 받는다('노래요' = 노랗/VA). 동사(VV)는 원형이 색 어간 그대로일 때만
        ('노래지다'). 명사·부사면 색 어간이 그 형태소 안에 다 들어 있거나 이어지는 형태소가 모두 명사여야 한다
        ('보라색' · '하늘/NNG 색/NNG'). 그래서 '보라고'(보/VV + 라고/EC), '제 노래요'(노래/NNG + 요/JX)는 색이 아니다."""
        ids = list(doc.etoks(e))
        toks = doc.toks
        tk = next((k for k in ids if toks[k].start <= a < toks[k].end), None)
        if tk is None:
            return False
        t = toks[tk]
        if t.base_tag in COLOR_PRED_TAGS:
            return True
        if t.base_tag == "VV":
            return self._full_color_lemma(t.form, "VV") is not None
        if t.base_tag in NOUN_TAGS | {"MAG", "NNB"}:
            over = [k for k in ids if toks[k].start < b and a < max(toks[k].end, toks[k].start + 1)]
            return all(k == tk or toks[k].base_tag in NOUN_TAGS | {"XSN"} for k in over)
        return False

    def _is_comparison_reference(self, doc: Doc, e: int) -> bool:
        """'오렌지만 해요' · '귤만큼 커요' — 'N만 하다 / N만큼·보다 + 크기 서술어'의 N은 비교 기준 사물이다(색이 아님)."""
        toks = doc.toks
        n = len(toks)
        cf = self.v["comparativeFactors"]
        ids = list(doc.etoks(e))
        nouns = [k for k in ids if toks[k].base_tag in NOUN_TAGS]
        if not nouns:
            return False
        j = nouns[-1] + 1
        if j >= n or doc.clause[j] != doc.clause[nouns[-1]]:
            return False
        if toks[j].form == "만" and toks[j].base_tag == "JX":
            k = j + 1
            return k < n and doc.clause[k] == doc.clause[j] and toks[k].form == "하" and toks[k].base_tag in ("VV", "XSV", "VA", "XSA")
        if toks[j].form in ("만큼", "만치", "보다"):
            for k in range(j + 1, min(n, j + 5)):
                if doc.clause[k] != doc.clause[j]:
                    break
                tk = toks[k]
                if tk.base_tag in ("VA", "VV"):
                    return tk.form[:1] in cf["biggerStems"] + cf["smallerStems"] or tk.form in cf["biggerStems"] + cf["smallerStems"]
        return False

    def _color_in_eojeol(self, doc: Doc, e: int):
        """어절 e의 색 낱말: 표면형(어절 첫머리)을 품사 조건으로 거르고, 안 되면 첫 형태소 원형('파랬다가' → 파랗)으로 찾는다."""
        s0 = doc.espan(e)[0]
        m = self._match_color(doc.etext(e))
        if m is not None:
            a = s0 + len(m["prefix"])
            if not self._color_pos_ok(doc, e, a, a + len(m["stem"])):
                m = None
        if m is None:
            first = doc.toks[doc.eojeols[e][0]]
            if first.base_tag in ("VA", "VV", "XR"):
                m = self._full_color_lemma(first.form, first.base_tag)
                if m is not None:
                    m = dict(m, suffix="", lemma=first.form)
        if m is not None and self._is_comparison_reference(doc, e):
            return None
        return m

    def _coord_negated(self, doc: Doc) -> set[int]:
        """'크지도 작지도 않아요' — '-지도'(EC 지 + JX 도)가 이어지고 뒤에 않·안·못이 오면 그 열의 모든 항이 부정이다."""
        toks = doc.toks
        out: set[int] = set()
        run: list[int] = []
        for e in range(len(doc.eojeols)):
            ids = list(doc.etoks(e))
            forms = [(toks[k].form, toks[k].base_tag) for k in ids]
            if len(forms) >= 2 and forms[-2] == ("지", "EC") and forms[-1] == ("도", "JX"):
                if run and doc.eoj_clause(run[-1]) != doc.eoj_clause(e):
                    run = []
                run.append(e)
                continue
            if run and doc.eoj_clause(e) == doc.eoj_clause(run[-1]) and ids \
                    and toks[ids[0]].form in NEGATOR_FORMS + ("아니",):
                for f in run:
                    out.update(doc.etoks(f))
            run = []
        return out

    def _colors(self, doc: Doc, consumed: set[int], records) -> list[Cand]:
        text = doc.text
        found = []   # (e, match)
        for e in range(len(doc.eojeols)):
            if doc.is_punct_eoj(e):
                continue
            ids = list(doc.etoks(e))
            if any(k in consumed for k in ids):
                continue
            m = self._color_in_eojeol(doc, e)
            if m:
                found.append((e, m))
        out: list[Cand] = []
        by_e = {e: m for e, m in found}
        skip: set[int] = set()
        for e in by_e:                       # 'X에 가까운 Y' · 'X빛이 도는 Y'의 X는 Y의 수식어
            f = e - 1
            if f >= 1 and doc.etext(f) in ("가까운", "도는", "띤", "띄는") and (f - 1) in by_e \
                    and doc.eoj_clause(f - 1) == doc.eoj_clause(e):
                skip.add(f - 1)
        blend = self.v["colorBlend"]
        effects = self.v["colorModifierEffects"]
        for e, m in found:
            if e in skip:
                continue
            s0, s1 = doc.espan(e)
            ids = list(doc.etoks(e))
            i0 = ids[0]
            if m["kind"] == "tint":
                name, h, s, l = self.tints[m["stem"]]
                hsl = [h, s * blend["tintAloneS"], l]
                rule = f"colorTint.{m['stem']}"
            else:
                name, h, s, l = self.colors[m["stem"]][:4]
                hsl = [h, s, l]
                rule = f"colorTerm.{m['stem']}{m.get('suffix', '')}"
            provs = [self._prov("phrase_rule", text, s0, s1, rule + ">material.color:hsl")]
            mods: list[tuple[str, float, int]] = []          # (종류, k, 어절)
            if m["prefix"]:
                mods.append((self.v["colorPrefixes"][m["prefix"]], 1.0, e))
            # 앞 어절의 색 수식어(연한·짙은 …)와 그 앞 정도 부사
            f = e - 1
            if f >= 0 and doc.eoj_clause(f) == doc.eoj_clause(e) and doc.etext(f) in self.color_mods:
                k, _ = self._degree(doc, doc.eojeols[f][0])
                kind = self.color_mods[doc.etext(f)]
                mods.append((kind, k, f))
                if kind in ("pastel", "light", "deep", "dark"):      # 명도 수식어는 색에만 쓴다(밝기·채도 값을 따로 만들지 않음)
                    g = f - 1
                    if g >= 0 and doc.eoj_clause(g) == doc.eoj_clause(e) and doc.etext(g) in (self.strong | self.weak):
                        consumed.update(doc.etoks(g))
                    consumed.update(doc.etoks(f))
                fs, fe = doc.espan(f)
                provs.append(self._prov("phrase_rule", text, fs, fe,
                                        f"colorModifier.{doc.etext(f)}>material.color:{self.color_mods[doc.etext(f)]}"))
            # 'X에 가까운 Y' · 'X빛이 도는 Y' — 앞 색 X를 Y에 섞는다
            if f >= 1 and doc.etext(f) in ("가까운", "도는", "띤", "띄는") and (f - 1) in by_e and \
                    doc.eoj_clause(f - 1) == doc.eoj_clause(e):
                xm = by_e[f - 1]
                xs = self.colors[xm["stem"]][1:4] if xm["kind"] == "term" else self.tints[xm["stem"]][1:4]
                hsl = self._blend(hsl, list(xs), blend["near"])
                skip.add(f - 1)
                consumed.update(doc.etoks(f - 1))
                consumed.update(doc.etoks(f))
                xs0, xs1 = doc.espan(f - 1)
                fs, fe = doc.espan(f)
                provs.append(self._prov("phrase_rule", text, xs0, fe, f"colorNear.{xm['stem']}>material.color:blend"))
            for kind, k, _ in mods:
                hsl = self._modify(hsl, effects[kind], k)
            consumed.update(ids)
            c = Cand("material.color", {"h": _r(hsl[0] / 360), "s": _r(hsl[1]), "l": _r(hsl[2])}, i0, s0, provs,
                     kind="color", attributive=self._is_attributive(doc, e))
            c.meta = {"eoj": e, "match": m, "hsl": hsl, "name": name}
            # '빨갛지 않아요' · '빨간색은 아니고' — 부정
            nf = self._next_eoj_same_clause(doc, e)
            in_eoj = [doc.toks[k].form for k in ids]
            pre = doc.toks[i0 - 1] if i0 else None
            if any(k in doc.coord_neg for k in ids) or \
                    ("지" in in_eoj and nf is not None and doc.etext(nf)[:1] in ("않", "안")) or \
                    (nf is not None and doc.etext(nf).startswith("아니") and not doc.etext(e).endswith("에")) or \
                    (pre is not None and pre.form in ("안", "못") and pre.base_tag == "MAG" and doc.clause[i0 - 1] == doc.clause[i0]):
                c.status = "negated"
            out.append(c)
        # '하얀색인데 약간 누르스름해요' — 띠는 색은 같은 문장의 색에 섞는다
        tints = [c for c in out if c.meta["match"]["kind"] == "tint" and c.status == "ok"]
        for tc in tints:
            base = [c for c in out if c is not tc and c.meta["match"]["kind"] == "term" and c.status == "ok"
                    and doc.sent[c.tok] == doc.sent[tc.tok]]
            if not base:
                continue
            b = min(base, key=lambda c: abs(c.start - tc.start))
            th, ts, tl = self.tints[tc.meta["match"]["stem"]][1:4]
            bh = b.meta["hsl"]
            hsl = [th, max(bh[1], ts * blend["tintS"]), bh[2] + (tl - bh[2]) * blend["tintL"]]
            b.value = {"h": _r(hsl[0] / 360), "s": _r(hsl[1]), "l": _r(hsl[2])}
            b.provs.append(dict(tc.provs[0], rule=f"colorTint.{tc.meta['match']['stem']}>material.color:tint"))
            tc.status = "merged"
        return [c for c in out if c.status != "merged"]

    @staticmethod
    def _blend(hsl: list, other: list, w: float) -> list:
        h, s, l = hsl
        oh, os_, ol = other
        if os_ >= 0.1 and s >= 0.1:
            d = ((oh - h + 180) % 360) - 180
            h = (h + d * w) % 360
        elif s < 0.1 <= os_:
            h = oh
        return [h, s + (os_ - s) * w, l + (ol - l) * w]

    @staticmethod
    def _modify(hsl: list, eff: dict, k: float) -> list:
        h, s, l = hsl
        if s < 0.1:          # 무채색(흰·검·회)은 채도를 바꾸지 않는다('새하얀'이 분홍이 되지 않게)
            eff = {k2: v for k2, v in eff.items() if k2 not in ("sMul", "sUp")}
        if "lUp" in eff:
            l = l + (1 - l) * eff["lUp"] * k
        if "lMul" in eff:
            l = l * (1 - (1 - eff["lMul"]) * k)
        if "sMul" in eff:
            s = s * (1 - (1 - eff["sMul"]) * k) if eff["sMul"] < 1 else min(1.0, s * (1 + (eff["sMul"] - 1) * k))
        if "sUp" in eff:
            s = s + (1 - s) * eff["sUp"] * k
        return [h, min(1.0, max(0.0, s)), min(1.0, max(0.0, l))]

    # ── 1층 사전 ─────────────────────────────────────────────────────────────
    def _lexicon_cands(self, doc: Doc, hits: list[Hit], consumed: set[int], similes, body_any: bool,
                       unmapped: list, negated: list, records) -> list[Cand]:
        out = []
        toks, text = doc.toks, doc.text
        for h in hits:
            e = h.entry
            i = h.token_index
            if e.category in SKIP_LEXICON_CATEGORIES or i in consumed:
                continue
            sim = self._vehicle_of(toks[i], similes)
            layer = 2 if sim else 1
            predicate = e.pos in ("VA", "VV", "XR") or toks[i].base_tag in ("VA", "VV")
            mk = (lambda rule: self._eoj_prov(doc, i, rule)) if predicate else (lambda rule: self._tok_prov(doc, i, rule))
            if sim:
                base_mk = mk
                mk = lambda rule, _b=base_mk, _s=sim: dict(_b(f"simile.{_s['marker']}>{rule}"), source="simile_marker")  # noqa: E731
            neg = h.negated or self._noun_negated(doc, i) or i in doc.coord_neg
            # 'X에 가까운/가까워요'의 X가 색이면 거리 말이 아니다(색 규칙이 맡음)
            if e.category == "distance" and e.lemma == "가깝" and i > 0:
                pe = doc.eoj[i] - 1
                if pe >= 0 and self._match_color(doc.etext(pe)) and doc.etext(pe).endswith("에"):
                    consumed.add(i)
                    continue
            if neg:
                if e.category == "movement" and e.lemma in self.still_lemmas:
                    out.append(Cand("motion.type", "still", i, toks[i].start,
                                    [mk(f"{e.rule}>motion.type:still(negated)")], layer=layer, sub=1))
                else:
                    negated.append({"lemma": e.lemma, "category": e.category, "_provenance": mk(e.rule)})
                continue
            if sim and e.category == "object" and i == sim["srcIndex"]:
                continue
            # 몸 안 · 배꼽 아래 — 위치어
            if e.category == "body_layer":
                c = self._body_layer(doc, h, layer, mk, body_any, unmapped, records)
                if c is not None:
                    out.append(c)
                continue
            idiom = self.v["idioms"]["glossFlow"]
            if e.category == "movement" and e.lemma in idiom["verbs"]:
                tp = self._topic(doc, i)
                if tp and tp[0] in idiom["subjects"]:          # '윤기가 흘러요'
                    unmapped.append({"lemma": e.lemma, "category": e.category, "value": dict(e.value),
                                     "reason": "idiom", "_provenance": mk(e.rule)})
                    continue
            targets = self.layer1.get(e.category)
            if not targets:
                unmapped.append({"lemma": e.lemma, "category": e.category, "value": dict(e.value),
                                 "reason": "no_scene_param", "_provenance": mk(e.rule)})
                continue
            produced = 0
            for tg in targets:
                mapped = self._map(tg, e.value)
                if mapped is None:
                    continue
                value, key = mapped
                path = tg["path"]
                sub = 0
                if path == "material.opacity" and key == "see_through":
                    k, f = self._degree(doc, i)
                    pe = doc.eoj[i] - 1
                    if f is None and pe >= 0 and doc.etext(pe) in ("다", "훤히", "완전히") and doc.eoj_clause(pe) == doc.clause[i]:
                        k = self.k["strong"]
                    value = _r(1 - self.v["seeThrough"]["base"] * k)
                elif isinstance(value, float) and path in self.v["scalarCenters"]:
                    k, _ = self._degree(doc, i)
                    value = self._apply_degree(path, value, k, key)
                if path == "motion.type" and self._is_state(doc, i, e.lemma):
                    sub = 1
                if path == "body.part":
                    sub = self.body_general.get(e.lemma, 0)
                out.append(Cand(path, value, i, toks[i].start, [mk(f"{e.rule}>{path}:{key}")], layer=layer, sub=sub))
                produced += 1
            if not produced:
                unmapped.append({"lemma": e.lemma, "category": e.category, "value": dict(e.value),
                                 "reason": "no_value_mapping", "_provenance": mk(e.rule)})
        # '몸 안이요' — Kiwi가 '안'을 부사(MAG)로 낸 경우
        for i, t in enumerate(toks):
            if t.form != "안" or t.base_tag != "MAG" or i == 0 or i in consumed:
                continue
            prev = toks[i - 1]
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            body_prev = any(h.token_index == i - 1 and h.entry.category == "body_part" for h in hits)
            if body_prev and (nxt is None or nxt.base_tag in ("JX", "VCP", "JKB", "EF", "SF") or doc.eoj[i + 1] != doc.eoj[i]) \
                    and (nxt is None or nxt.base_tag not in ("VV", "VA")):
                out.append(Cand("body.layer", "inner", i, t.start,
                                [self._tok_prov(doc, i, "bodyLayerLexicon.안>body.layer:inner")], sub=0))
        return out

    def _noun_negated(self, doc: Doc, i: int) -> bool:
        """'빛이 안 나고' — 체언 + 조사 + (부사) + 안/못 + 용언."""
        toks = doc.toks
        if toks[i].base_tag not in NOUN_TAGS:
            return False
        k = i + 1
        while k < len(toks) and toks[k].base_tag in ("XSN", "JKS", "JX"):
            k += 1
        while k < len(toks) and toks[k].base_tag == "MAG" and toks[k].form in ("거의", "전혀", "별로", "잘", "좀", "그다지", "하나도"):
            k += 1
        return (k + 1 < len(toks) and toks[k].form in ("안", "못") and toks[k].base_tag == "MAG"
                and toks[k + 1].base_tag in ("VV", "VA") and doc.clause[k] == doc.clause[i])

    def _is_state(self, doc: Doc, i: int, lemma: str) -> bool:
        """'떠 있다'·'퍼져 있다'(-어 있다 결과 상태)와 '가만히'·'멈추다'는 상태어. 움직임 동사보다 뒤로 민다."""
        toks = doc.toks
        if lemma in ("가만히", "멈추", "정지"):
            return True
        if toks[i].base_tag == "MAG":          # '둥둥 떠 있어요' — 의태 부사는 꾸미는 동사의 상태를 따른다
            for k in range(i + 1, min(len(toks), i + 3)):
                if toks[k].base_tag == "VV" and doc.clause[k] == doc.clause[i]:
                    return self._is_state(doc, k, toks[k].form)
            return False
        if i + 2 < len(toks) and toks[i + 1].base_tag == "EC" and toks[i + 1].form in ("어", "아", "여") \
                and toks[i + 2].base_tag == "VX" and toks[i + 2].form in ("있", "잇"):
            return True
        return False

    def _body_layer(self, doc: Doc, h: Hit, layer: int, mk, body_any: bool, unmapped: list, records) -> Cand | None:
        toks = doc.toks
        i = h.token_index
        e = h.entry
        val = e.value.get("layer")
        sub = 0 if e.lemma in self.layer_explicit else 1
        j = i - 1
        while j >= 0 and toks[j].base_tag == "MAG" and toks[j].form in ("바로", "조금", "살짝", "좀"):
            j -= 1
        prev = toks[j] if j >= 0 and doc.clause[j] == doc.clause[i] else None
        prev_body = prev is not None and prev.form in self.body_forms
        rule = f"{e.rule}>body.layer:{val}"
        if prev_body:
            return Cand("body.layer", val, i, toks[i].start, [mk(rule)], layer=layer, sub=sub)
        if prev is not None and prev.base_tag in NOUNISH_TAGS and doc.eoj[j] >= doc.eoj[i] - 1:
            p = mk(rule)
            records["_context"].append({"text": p["trigger"], "charSpan": p["charSpan"], "reason": "object_relative_position",
                                        "path": "body.layer", "value": val, "rule": p["rule"]})
            return None
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        k = i + 1
        while k < len(toks) and toks[k].form == "쪽" and toks[k].base_tag in ("NNB", "NNG", "XSN"):
            k += 1
        nt = toks[k] if k < len(toks) else None
        if nxt is not None and nxt.base_tag in NOUN_TAGS and doc.eoj[i + 1] != doc.eoj[i]:
            p = mk(rule)
            records["_context"].append({"text": p["trigger"], "charSpan": p["charSpan"], "reason": "object_relative_position",
                                        "path": "body.layer", "value": val, "rule": p["rule"]})
            return None
        locative = nt is None or nt.base_tag in ("VCP", "EF", "SF", "SP") or \
            (nt.base_tag == "JKB" and nt.form in LOC_PARTICLES) or (nt.base_tag == "JX" and nt.form in ("요", "이요", "에요"))
        line_short = sum(1 for f in range(len(doc.eojeols)) if not doc.is_punct_eoj(f)
                         and doc.line[doc.eojeols[f][0]] == doc.line[i]) <= 3
        if locative and (body_any or line_short):
            return Cand("body.layer", val, i, toks[i].start, [mk(rule)], layer=layer, sub=sub)
        unmapped.append({"lemma": e.lemma, "category": e.category, "value": dict(e.value),
                         "reason": "no_body_part_context", "_provenance": mk(e.rule)})
        return None

    # ── 2층: 직유 ─────────────────────────────────────────────────────────────
    def _similes(self, text: str, toks: list[Token]) -> list[dict]:
        out = []
        for i, t in enumerate(toks):
            marker = None
            if t.form == "처럼" and t.base_tag == "JKB":
                marker = "처럼"
            elif t.form == "마냥" and t.base_tag in ("JKB", "MAG"):
                marker = "마냥"
            elif t.form == "같" and t.base_tag == "VA":
                marker = "같은"
            elif t.form == "듯" and t.base_tag in ("NNB", "XR"):
                marker = "듯한"
            if marker is None:
                continue
            j = i - 1
            while j >= 0 and toks[j].base_tag in SIMILE_SKIP_TAGS:
                j -= 1
            if j < 0 or toks[j].base_tag not in NOUN_TAGS:
                continue
            k = j
            while k - 1 >= 0 and toks[k - 1].base_tag in NOUN_TAGS and toks[k - 1].end >= toks[k].start - 1:
                k -= 1
            vstart = toks[k].start
            if self.with_modifier and k - 1 >= 0 and toks[k - 1].base_tag == "ETM":
                vstart = max(text.rfind(" ", 0, toks[k - 1].start), text.rfind("\n", 0, toks[k - 1].start)) + 1
            out.append({"marker": marker, "srcIndex": j, "srcStart": k, "srcForm": toks[j].form,
                        "sourceNoun": text[toks[k].start:toks[j].end], "span": (toks[k].start, t.end),
                        "trigger": text[toks[k].start:t.end], "vehicle": (vstart, t.end)})
        return out

    @staticmethod
    def _vehicle_of(t: Token, similes: list[dict]) -> dict | None:
        for s in similes:
            v0, v1 = s["vehicle"]
            if v0 <= t.start and t.end <= v1:
                return s
        return None

    def _prototype(self, source: str, src_form: str) -> tuple[str, str] | None:
        key = source.replace(" ", "")
        for cand in (key, src_form):
            if cand in self.prototypes:
                return cand, self.prototypes[cand]
        for n in range(len(key) - 1, 0, -1):          # 합성어: 가장 긴 뒷부분
            tail = key[-n:]
            if tail in self.prototypes and len(tail) >= 1 and n < len(key):
                return tail, self.prototypes[tail]
        return None

    def _simile_cands(self, doc: Doc, hits: list[Hit], similes, consumed: set[int], unmapped: list,
                      proto_toks: set[int]) -> list[Cand]:
        out = []
        for s in similes:
            if s["srcIndex"] in consumed:
                continue
            src_hits = [h for h in hits if h.token_index == s["srcIndex"]]
            if any(h.entry.category == "form" for h in src_hits):
                continue
            proto = self._prototype(s["sourceNoun"], s["srcForm"])
            prov = {"source": "simile_marker", "trigger": s["trigger"], "charSpan": list(s["span"])}
            if proto:
                key, value = proto
                out.append(Cand("form.type", value, s["srcIndex"], s["span"][0],
                                [{**prov, "rule": f"simile.{s['marker']}>prototype.{key}>form.type:{value}"}],
                                layer=2, kind="simile"))
                proto_toks.update(range(s["srcStart"], s["srcIndex"] + 1))
                continue
            for h in src_hits:
                if h.entry.category == "object":
                    unmapped.append({"lemma": h.entry.lemma, "category": h.entry.category, "value": dict(h.entry.value),
                                     "reason": "simile_prototype_pending",
                                     "_provenance": {**prov, "rule": f"simile.{s['marker']}>{h.entry.rule}"}})
        return out

    # ── 퍼지(자모 편집거리) ───────────────────────────────────────────────────
    def _build_fuzzy_index(self) -> list[tuple[str, list[str], str, object]]:
        idx = []
        for e in self.lexicon.entries:
            if e.category in SKIP_LEXICON_CATEGORIES or e.category not in self.layer1:
                continue
            if not any(self._map(tg, e.value) for tg in self.layer1[e.category]):
                continue
            fam = "pred" if e.pos in ("VA", "VV") else "nom"
            for form in (e.lemma, *e.alt):
                j = decompose(form)
                if len(j) >= self.v["fuzzy"]["minJamo"]:
                    idx.append((form, j, fam, e))
        return idx

    def _derive_mimetic(self, form: str, next_form: str | None = None):
        """까끌거리 → 까끌(까끌까끌) · 출렁이 → 출렁 · 펄럭펄럭 → 펄럭. 사전 항목을 돌려준다.
        Kiwi가 '까끌/NNG + 거리/VV'처럼 나눈 경우는 next_form으로 받는다."""
        roots = [form] if next_form in self.v["mimeticDerivation"]["suffixes"] and len(form) >= 2 else []
        for suf in self.v["mimeticDerivation"]["suffixes"]:
            if form.endswith(suf) and len(form) - len(suf) >= 2:
                roots.append(form[:-len(suf)])
        if len(form) >= 4 and len(form) % 2 == 0 and form[:len(form) // 2] == form[len(form) // 2:]:
            roots.append(form[:len(form) // 2])
        for root in roots:
            for cand in (root, root + root, root + "거리", root + "이"):
                for e in self.lexicon._by_form.get(cand, []):
                    if e.category in self.layer1 and e.category not in SKIP_LEXICON_CATEGORIES:
                        return root, e
        return None

    def _strip_endings(self, form: str) -> list[str]:
        out = [form]
        for end in sorted(self.v["fuzzyEndings"], key=lambda s: (-len(s), s)):
            if form.endswith(end) and len(form) - len(end) >= 2:
                out.append(form[:-len(end)])
                break
        return out

    def _fuzzy(self, doc: Doc, covered: set[int], fuzzy_toks: set[int]) -> list[Cand]:
        """사전에 없는 내용어: (1) 의태어 파생 규칙(정확 일치, 값) (2) 자모 편집거리 ≤ 1(kind = fuzzy: 값이 아니라
        확인 필요 대안으로만 남는다 — _merge)."""
        out = []
        maxd = self.v["fuzzy"]["maxDistance"]
        for i, t in enumerate(doc.toks):
            if i in covered or t.base_tag not in CONTENT_TAGS or t.lemma in FUNCTION_LEMMAS:
                continue
            nx = (doc.toks[i + 1] if i + 1 < len(doc.toks) and doc.eoj[i + 1] == doc.eoj[i]
                  and doc.toks[i + 1].base_tag in ("VV", "XSV", "XSA") else None)
            der = self._derive_mimetic(t.form, nx.form if nx is not None else None)
            if der:
                root, e = der
                for tg in self.layer1[e.category]:
                    mapped = self._map(tg, e.value)
                    if mapped is None or tg["path"] == "body.layer":
                        continue
                    value, key = mapped
                    path = tg["path"]
                    if isinstance(value, float) and path in self.v["scalarCenters"]:
                        value = self._apply_degree(path, value, self._degree(doc, i)[0], key)
                    sub = 1 if path == "motion.type" and self._is_state(doc, i, t.form) else 0
                    out.append(Cand(path, value, i, t.start,
                                    [self._eoj_prov(doc, i, f"mimeticDerivation.{root}>{e.rule}>{path}:{key}")], sub=sub))
                    fuzzy_toks.add(i)
                continue
            fam = "pred" if t.base_tag in ("VA", "VV") else "nom"
            best, best_d = [], maxd + 1
            for variant in self._strip_endings(t.form):
                tj = decompose(variant)
                if len(tj) < self.v["fuzzy"]["minJamo"]:
                    continue
                for form, j, f, e in self._fuzzy_index:
                    if f != fam or abs(len(j) - len(tj)) > maxd:
                        continue
                    d = levenshtein(tj, j)
                    if d < best_d:
                        best, best_d = [(form, e)], d
                    elif d == best_d and (form, e) not in best:
                        best.append((form, e))
            if not best or best_d == 0 or best_d > maxd:
                continue
            kinds = {(e.category, json.dumps(e.value, sort_keys=True, ensure_ascii=False)) for _, e in best}
            if len(kinds) != 1:
                continue                                  # 동률 후보가 서로 다르면 쓰지 않는다
            form, e = best[0]
            for tg in self.layer1[e.category]:
                mapped = self._map(tg, e.value)
                if mapped is None:
                    continue
                value, key = mapped
                path = tg["path"]
                if path in ("body.layer",):
                    continue
                prov = self._eoj_prov(doc, i, f"fuzzy(d={best_d}).{form}>{e.rule}>{path}:{key}", source="fuzzy_lexicon")
                prov["needsConfirmation"] = True
                out.append(Cand(path, value, i, t.start, [prov], klass=3, kind="fuzzy", meta={"matched": form}))
                fuzzy_toks.add(i)
        return out

    def _fuzzy_best(self, variants: list[str], fams: tuple[str, ...]):
        maxd = self.v["fuzzy"]["maxDistance"]
        best, best_d = [], maxd + 1
        for variant in variants:
            tj = decompose(variant)
            if len(tj) < self.v["fuzzy"]["minJamo"]:
                continue
            for form, j, f, e in self._fuzzy_index:
                if f not in fams or abs(len(j) - len(tj)) > maxd:
                    continue
                d = levenshtein(tj, j)
                if d < best_d:
                    best, best_d = [(form, e)], d
                elif d == best_d and (form, e) not in best:
                    best.append((form, e))
        if not best or best_d == 0 or best_d > maxd:
            return None
        if len({(e.category, json.dumps(e.value, sort_keys=True, ensure_ascii=False)) for _, e in best}) != 1:
            return None
        return best[0][0], best[0][1], best_d

    def _fuzzy_eojeol(self, doc: Doc, cands: list[Cand], covered: set[int], fuzzy_toks: set[int]) -> list[Cand]:
        """Kiwi가 모르는 말을 조각낸 경우('오돌도돌해요' → 오/NR 돌/NNG 도/JX 돌/NNG): 어절 표면형(어미를 뗀 3음절 이상)으로
        퍼지 매칭한다. 그 어절의 어느 토큰도 값 후보를 만들지 않았을 때만."""
        out = []
        cand_toks = {c.tok for c in cands}
        for e in range(len(doc.eojeols)):
            if doc.is_punct_eoj(e):
                continue
            ids = list(doc.etoks(e))
            if any(k in covered or k in cand_toks for k in ids) or len(ids) < 3:
                continue
            w = doc.etext(e).strip(" .,!?~")
            variants = [v for v in self._strip_endings(w) if len(v) >= 3]
            if not variants or any(self.lexicon._by_form.get(v) for v in variants):
                continue
            found = self._fuzzy_best(variants, ("nom", "pred"))
            if not found:
                continue
            form, ent, d = found
            for tg in self.layer1[ent.category]:
                mapped = self._map(tg, ent.value)
                if mapped is None or tg["path"] == "body.layer":
                    continue
                value, key = mapped
                path = tg["path"]
                prov = self._eoj_prov(doc, ids[0], f"fuzzy(d={d}).{form}>{ent.rule}>{path}:{key}", source="fuzzy_lexicon")
                prov["needsConfirmation"] = True
                out.append(Cand(path, value, ids[0], doc.toks[ids[0]].start, [prov], klass=3, kind="fuzzy",
                                meta={"matched": form}))
                fuzzy_toks.update(ids)
        return out

    # ── 범위 규칙 ─────────────────────────────────────────────────────────────
    def _scope(self, doc: Doc, cands: list[Cand], context_sents: set[int], similes) -> None:
        sim_src = {s["srcIndex"] for s in similes}
        former = set(self.v["formerMarkers"])
        current = set(self.v["currentMarkers"])
        former_etm = set(self.v["contextSentence"]["etm"])          # '던'
        clause_tense: dict[int, int] = {}
        for c_id in set(doc.clause):
            ids = doc.clause_toks(c_id)
            forms = [doc.toks[k].form for k in ids]
            tense = 0
            if any(f in current for f in forms):
                tense = 1
            elif any(f in former for f in forms) or any(
                    doc.toks[k].form == "다가" and doc.toks[k].base_tag == "EC" for k in ids):   # '~했다가 / ~있다가' 뒤 상태가 지금
                tense = -1
            clause_tense[c_id] = tense
        attr_paths = ("material.", "form.", "motion.", "layout.size")
        for c in cands:
            i = c.tok
            if doc.sent[i] in context_sents:
                c.status, c.reason = "context", "recollection_sentence"
                continue
            c.tense = clause_tense.get(doc.clause[i], 0)
            # 후보 단위 때: '-던' 관형절 안의 말은 지난 상태다('빨갛던 게 노래졌어요' · '아까 반짝이던 게 지금은 …')
            last = doc.toks[doc.eojeols[doc.eoj[i]][1]]
            if last.base_tag == "ETM" and last.form in former_etm:
                c.tense = -1
            # 관형어 → 꾸미는 명사
            if c.kind in ("color", "lexicon") and c.path.startswith(("material.", "form.posture", "layout.size")):
                e = doc.eoj[i]
                attr_e = e if (c.attributive or self._is_attributive(doc, e)) else self._coordinated_attributive(doc, e)
                if attr_e is not None:
                    hn = self._head_noun(doc, attr_e)
                    if hn:
                        noun, k = hn
                        if self._is_background(noun) and k not in sim_src:
                            c.status, c.reason = "context", "background_object"
                            continue
                        if self._is_landmark(doc, k) and k not in sim_src:
                            c.status, c.reason = "context", "landmark_object"
                            continue
                        if noun in self.part_class and c.path in self.part_scoped:
                            c.part, c.part_class = noun, self.part_class[noun]
            # 주제·주어
            tp = self._topic(doc, i)
            if tp:
                noun, k = tp
                if self._is_background(noun) and c.path.startswith(attr_paths) and k not in sim_src:
                    c.status, c.reason = "context", "background_subject"
                    continue
                if noun in self.part_class and c.path in self.part_scoped and c.part is None:
                    c.part, c.part_class = noun, self.part_class[noun]
                if self.dim_topics.get(noun) == c.path:
                    c.dim_topic = True
            if c.status == "negated":
                continue

    def _uncertainty(self, doc: Doc, cands: list[Cand], records) -> set[str]:
        """'잘 모르겠어요' 절. 그 절이 가리키는 차원은 값을 비운다(말한 것: 모른다)."""
        markers = self.v["uncertaintyMarkers"]
        paths_all: set[str] = set()
        for c_id in sorted(set(doc.clause)):
            ids = doc.clause_toks(c_id)
            marks = [k for k in ids if any(doc.toks[k].form.startswith(m) for m in markers)]
            if not marks:
                continue
            paths: set[str] = set()
            for k in ids:
                f = doc.toks[k].form
                if f in self.dim_topics:
                    paths.add(self.dim_topics[f])
            # 'X인지 Y인지' · '움직이는지'
            q_toks = set()
            for k in ids:
                nx = doc.toks[k + 1] if k + 1 < len(doc.toks) else None
                nx2 = doc.toks[k + 2] if k + 2 < len(doc.toks) else None
                if nx is not None and nx.base_tag == "EC" and nx.form.endswith("지"):
                    q_toks.add(k)
                elif nx is not None and nx.base_tag == "VCP" and nx2 is not None and nx2.base_tag == "EC" and nx2.form.endswith("지"):
                    q_toks.add(k)
            for c in cands:
                if doc.clause[c.tok] == c_id and c.status == "ok":
                    if c.tok in q_toks and c.kind != "fuzzy":
                        paths.add(c.path)
                    c.status, c.reason = "uncertain", "participant_uncertain"
            for k in q_toks:
                f = doc.toks[k].form
                if f.startswith("움직"):
                    paths.add("motion.type")
            s, e = doc.clause_span(c_id)
            records["_uncertain"].append({"text": doc.text[s:e], "charSpan": [s, e], "paths": sorted(paths),
                                          "marker": doc.toks[marks[0]].form})
            paths_all |= paths
        return paths_all

    def _corrections(self, doc: Doc, cands: list[Cand]) -> None:
        cm = self.v["correctionMarkers"]
        toks = doc.toks
        points: list[tuple[int, int]] = []          # (토큰, 문장)
        for i, t in enumerate(toks):
            if t.form == "아니" and t.base_tag in ("VCN", "IC", "MAG"):
                prev = toks[i - 1] if i else None
                standalone = prev is None or prev.base_tag in ("IC", "SE", "SP", "SF") or doc.eoj[i - 1] != doc.eoj[i] \
                    and prev.base_tag not in ("JKS", "JKC", "JX")
                if standalone:
                    points.append((i, doc.sent[i]))
                else:   # 'X이 아니고' → 바로 앞 후보
                    for c in cands:
                        if c.status == "ok" and c.tok < i and doc.eoj[c.tok] >= doc.eoj[i] - 1 and doc.clause[c.tok] == doc.clause[i]:
                            c.status, c.reason = "corrected", "self_corrected"
        for c in cands:
            if c.status != "ok":
                continue
            e = doc.eoj[c.tok]
            forms = [toks[k].form for k in doc.etoks(e)]
            if "보다" in forms and forms.index("보다") + 1 < len(forms) and forms[forms.index("보다") + 1] in ("는", "ᆫ"):
                later = [d for d in cands if d is not c and d.path == c.path and d.start > c.start
                         and doc.sent[d.tok] == doc.sent[c.tok] and d.kind != "fuzzy"]
                if later:
                    c.status, c.reason = "corrected", "self_corrected"
            nf = self._next_eoj_same_clause(doc, e)
            if nf is not None and doc.etext(nf) == "말고":
                c.status, c.reason = "corrected", "self_corrected"
        for i, s in points:
            after_paths = {d.path for d in cands if d.start > toks[i].start and doc.sent[d.tok] == s and d.kind != "fuzzy"}
            for c in cands:
                if c.status != "ok" or c.start >= toks[i].start:
                    continue
                if doc.sent[c.tok] == s or (doc.sent[c.tok] == s - 1 and c.path in after_paths):
                    c.status, c.reason = "corrected", "self_corrected"

    def _dimension_negations(self, doc: Doc, negated: list) -> None:
        """'색은 없어요' · '소리는 없어요' — 차원 자체를 없다고 말함."""
        toks = doc.toks
        dims = {e.lemma for e in self.lexicon.entries if e.category == "dimension"}
        for i, t in enumerate(toks):
            if t.base_tag not in NOUN_TAGS or t.form not in dims:
                continue
            k = i + 1
            while k < len(toks) and toks[k].base_tag in ("JX", "JKS"):
                k += 1
            while k < len(toks) and toks[k].base_tag == "MAG":
                k += 1
            if k < len(toks) and toks[k].form == "없" and doc.clause[k] == doc.clause[i]:
                s, e = t.start, doc.espan(doc.eoj[k])[1]
                negated.append({"lemma": t.form, "category": "dimension",
                                "_provenance": self._prov("explicit_lexicon", doc.text, s, e, f"dimensionLexicon.{t.form}+없")})

    # ── 병합 ─────────────────────────────────────────────────────────────────
    def _merge(self, cands: list[Cand], uncertain_paths: set[str], records):
        by_path: dict[str, list[Cand]] = defaultdict(list)
        alternatives: list[dict] = []
        for c in cands:
            if c.kind == "fuzzy" and c.status in ("ok", "uncertain", "corrected"):
                # 자모 퍼지 일치는 참여자가 그 낱말을 말했다는 근거가 아니다(원칙 2): 슬롯 값에 쓰지 않고 확인 필요 대안으로만 둔다
                alternatives.append({"path": c.path, "value": c.value, "reason": "needs_confirmation",
                                     "_provenance": list(c.provs)})
                records["_needsConfirmation"].append(c)
                continue
            if c.status == "ok":
                by_path[c.path].append(c)
            elif c.status in ("corrected", "uncertain"):
                alternatives.append({"path": c.path, "value": c.value, "reason": c.reason, "_provenance": list(c.provs)})
            elif c.status == "negated":
                records["_negatedCands"].append(c)
        values, provenance = {}, {}
        for path in SLOT_PATHS:
            cs = by_path.get(path, [])
            if not cs:
                continue
            if path in uncertain_paths:
                alternatives += [{"path": c.path, "value": c.value, "reason": "participant_uncertain",
                                  "_provenance": list(c.provs)} for c in sorted(cs, key=lambda c: c.start)]
                continue
            if path in self.part_scoped:
                whole = [c for c in cs if c.part_class in (None, "outer")]
                inner = [c for c in cs if c.part_class == "inner"]
                pool = whole or inner
                for c in cs:
                    if c not in pool:
                        p = c.provs[0]
                        records["_parts"].append({"text": p["trigger"], "charSpan": p["charSpan"], "part": c.part,
                                                  "partClass": c.part_class, "path": c.path, "value": c.value,
                                                  "rule": p["rule"]})
                cs = pool
                if not cs:
                    continue
            cs = sorted(cs, key=lambda c: (-int(c.dim_topic), -c.tense, c.layer, c.klass, c.sub, c.start))
            win = cs[0]
            values[path], provenance[path] = win.value, list(win.provs)
            for c in cs[1:]:
                if c.layer == win.layer and c.value == win.value:
                    provenance[path] += c.provs
                    continue
                if c.layer > win.layer:
                    reason = "lower_layer"
                elif c.tense < win.tense:
                    reason = "superseded"
                elif (c.klass, c.sub, -int(c.dim_topic)) != (win.klass, win.sub, -int(win.dim_topic)):
                    reason = "lower_priority"
                else:
                    reason = "later_mention"
                alternatives.append({"path": path, "value": c.value, "reason": reason, "_provenance": list(c.provs)})
        alternatives.sort(key=lambda a: (_ORDER[a["path"]], a["_provenance"][0]["charSpan"][0], a["reason"]))
        return values, provenance, alternatives

    # ── 3층·제안 ─────────────────────────────────────────────────────────────
    def _layer3(self, hits: list[Hit], values: dict, provenance: dict, consumed: set[int], context_sents: set[int],
                doc: Doc) -> dict:
        out: dict[str, dict] = {}
        emo = [h for h in hits if h.entry.category == "emotion" and not h.negated and h.entry.lemma in self.vad
               and doc.sent[h.token_index] not in context_sents]
        for t in sorted(self.l3_targets, key=lambda t: _ORDER[t["path"]]):
            if not emo or t["path"] in values:
                continue
            nums = [self.vad[h.entry.lemma][t["dim"]] for h in emo]
            out[t["path"]] = {
                "value": round(sum(nums) / len(nums), 3),
                "_provenance": [{"source": "vad_lexicon", "trigger": h.trigger, "charSpan": list(h.char_span),
                                 "rule": f"vadLexicon.{h.entry.lemma}>{t['path']}:{t['name']}"} for h in emo],
            }
        part = values.get("body.part")
        if part is not None and "layout.verticalOffset" not in values and part in self.body_height:
            p = provenance["body.part"][0]
            out["layout.verticalOffset"] = {
                "value": self.body_height[part],
                "_provenance": [{"source": "body_part_height", "trigger": p["trigger"], "charSpan": p["charSpan"],
                                 "rule": f"bodyPartHeight.{part}>layout.verticalOffset:{self.body_height[part]}"}]}
        return dict(sorted(out.items(), key=lambda kv: _ORDER[kv[0]]))

    @staticmethod
    def _unmatched(doc: Doc, hits: list[Hit], covered: set[int]) -> list[dict]:
        # v1은 색을 사전이 아니라 색 규칙으로 읽는다. 색 규칙이 차지하지 않은 색 사전 낱말은 '읽지 못한 말'로 남긴다
        hits = [h for h in hits if h.entry.category != "color"]
        cov = {h.token_index for h in hits} | covered
        out = []
        for i, t in enumerate(doc.toks):
            if t.base_tag not in CONTENT_TAGS or t.lemma in FUNCTION_LEMMAS or i in cov:
                continue
            if any(h.char_span[0] <= t.start and t.end <= h.char_span[1] and t.form in h.entry.lemma for h in hits):
                continue
            out.append({"lemma": t.lemma, "tag": t.tag, "surface": doc.text[t.start:t.end], "charSpan": [t.start, t.end]})
        return out

    def _clauses(self, doc: Doc, provenance: dict, context_sents: set[int]) -> list[dict]:
        """확정 텍스트 전체의 절 단위 원문 색인. 각 절이 어느 슬롯 값에 쓰였는지 적는다."""
        text = doc.text
        if not doc.toks:
            s = text.strip()
            return [{"charSpan": [text.find(s), text.find(s) + len(s)], "text": s, "usedFor": [], "status": "unused"}] if s else []
        starts = []
        for i in range(len(doc.toks)):
            if i == 0 or doc.clause[i] != doc.clause[i - 1]:
                starts.append(doc.toks[i].start if i else 0)
        bounds = starts[1:] + [len(text)]
        used_spans = [(p, pv["charSpan"]) for p, provs in provenance.items() for pv in provs]
        out = []
        for a, b in zip(starts, bounds):
            seg = text[a:b]
            lead = len(seg) - len(seg.lstrip())
            s, e = a + lead, a + len(seg.rstrip())
            if s >= e:
                continue
            ids = [i for i, t in enumerate(doc.toks) if s <= t.start < e]
            content = [i for i in ids if doc.toks[i].base_tag in CONTENT_TAGS and doc.toks[i].lemma not in FUNCTION_LEMMAS]
            used_for = sorted({p for p, (x, y) in used_spans if x < e and s < y}, key=lambda p: _ORDER[p])
            covered = [i for i in content if any(x <= doc.toks[i].start and doc.toks[i].end <= y for _, (x, y) in used_spans)]
            if any(doc.sent[i] in context_sents for i in ids):
                status = "context"
            elif content and len(covered) == len(content):
                status = "used"
            elif covered or used_for:
                status = "partly_used"
            else:
                status = "unused"
            out.append({"charSpan": [s, e], "text": text[s:e], "usedFor": used_for, "status": status})
        return out


# ── 대체 경로·팩토리 ──────────────────────────────────────────────────────────
def fallback_spec(v0_spec: dict, requested: str, reason: str) -> dict:
    """v1이 실패했을 때: v0 결과에 대체 사실을 meta에 남긴다(specVersion 2.1.0 — v2.1 스키마가 meta.mapping을 허용)."""
    spec = copy.deepcopy(v0_spec)
    spec["meta"]["specVersion"] = SPEC_VERSION
    spec["meta"]["mapping"] = {"requested": requested, "used": "v0", "fallbackReason": reason[:300]}
    return spec


def factory(rt) -> SceneSpecBuilderV1:
    """corpus_run·fidelity의 --mapper ifs_chatbot.scene_builder_v1:factory 용."""
    return SceneSpecBuilderV1.from_runtime(rt)
