"""G73-c 재진술 전용 매핑: [맞는 게 없어요] 뒤 참여자가 다시 적은 글 → 형태 갈래와 허용 슬롯의 처음 값.

- 입력은 다시 적은 글 하나. 확정 텍스트·확정 스펙은 바꾸지 않는다(장면 = 확정 스펙 + 덮어쓰기, G73-c).
- 출력은 갈래(solid · mist · light · flame · blocked · none, G73-b)와 허용 슬롯(shared/lexicon/resay_values.v0.json
  allowedSlots)의 값뿐이다. 값마다 글자 위치(charSpans)·규칙 id(rules)·표 판(table)을 단다. 말하지 않은 슬롯은 None.
- 색·크기·위치·거리·움직임 등 허용 슬롯 밖의 값은 읽은 경로와 글자 위치만 notRead에 남기고 값은 버린다.
- 형태소 분석·부정·회상 문장·움직임 비유(G71)는 매퍼 v2(SceneSpecBuilderV2 + 1층 사전 v2 + 비율 표)를 그대로 쓴다.
- 갈래는 사전이 정한다(LLM·번역 모델 없음, 원칙 1). 같은 글 → 같은 dict, 같은 바이트(mapping_bytes).
- 부정은 서술어의 것이다(0.3.0): '안개가 안 보여요'·'안개가 짙지 않아요'에서 부정된 것은 서술어(보이·짙)이고 주어 '안개'는
  부정되지 않는다 → 갈래 mist를 세우고, 서술어 부정은 표의 규칙(투명도·밀도)으로만 값에 든다. 존재 부정('안개가 없어요'·
  '있지 않아요')과 지정 부정('안개가 아니에요')은 지금처럼 명사 부정이다. 이 예외는 재진술 매핑에만 있다 — 공유
  form_words.negated_near와 G62 shape_prompt는 그대로(바꾸면 G62 출력이 바뀐다).

이 모듈은 생성기를 부르지 않는다. 형태 프롬프트(갈래 solid)는 tools/gen3d/resay.py가 이 결과로 만든다.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .form_words import NOUNISH, form_position, negated_near, next_noun, noun_run_bounds
from .korean import Analyzer
from .paths import shared
from .scene_builder import normalize_confirmed
from .scene_builder_v1 import Doc
from .scene_builder_v2 import SceneSpecBuilderV2

RESAY_MAPPING_VERSION = "resay-mapping/0.3.0"
BRANCHES = ("solid", "mist", "light", "flame", "blocked", "none")
_PRED_TAGS = {"VA", "VV", "MAG", "XR"}
_FORM_POSITIONS = ("head", "simile", "noun_modifier")
_SKIP_POSITIONS = ("location", "size", "object", "genitive")
_PRED_HEAD_TAGS = {"VV", "VA", "XR"}
# 존재 서술어: 이것이 부정되면('없어요'·'있지 않아요') 주어가 없다는 뜻이라 주어 명사 부정으로 본다
_EXIST_PREDS = frozenset({"있", "없"})
# 주어 표지(같은 어절, 명사 바로 뒤): 주격 조사(이·가·께서) · 보조사(은·는·도·만). 표지가 없는 맨 명사도 주어로 본다
_SUBJECT_TAGS = frozenset({"JKS", "JX"})
# 1층 사전에서 형태 명사로 볼 수 있는 범주(그 밖 범주 낱말은 사물 이름이 아니다: 감정·색·몸 부위 …)
_OBJECT_CATEGORIES = frozenset({"object", "form", "shape"})


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load(path: Path) -> tuple[dict, str]:
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw), _sha(raw)


class ResayMapper:
    def __init__(self, analyzer: Analyzer, values_path: str | Path | None = None,
                 shape_lexicon_path: str | Path | None = None, filter_path: str | Path | None = None):
        if not getattr(analyzer, "available", False):
            raise RuntimeError("kiwipiepy가 없습니다. 재진술 매핑은 Kiwi 분석이 있어야 결정적으로 같습니다.")
        self.analyzer = analyzer
        # 매퍼 v2: 1층 사전 v2(발광) + 비율 표(G72). 허용 슬롯 값의 원천이고, 부정·회상·움직임 비유 판정을 빌려 쓴다
        self.builder = SceneSpecBuilderV2(analyzer, ext_lexicon_path=shared("lexicon", "layer1_lexicon.v2.json"),
                                          proportions_path=shared("lexicon", "scene_params.v2.json"))
        self.values, self.values_sha = _load(values_path or shared("lexicon", "resay_values.v0.json"))
        self.shape_lex, self.shape_lex_sha = _load(shape_lexicon_path or shared("lexicon", "shape_prompt_en.v0.json"))
        self.filt, self.filt_sha = _load(filter_path or shared("lexicon", "resay_prompt_filter.v0.json"))
        self.table_id = f"{self.values['lexiconId']}@{self.values['tableVersion']}"
        self.allowed: list[str] = list(self.values["allowedSlots"])
        pr = self.shape_lex["positionRules"]
        self.loc_nouns = frozenset(pr["locationNouns"])
        self.size_nouns = frozenset(pr["sizeNouns"])
        self.generic = frozenset(pr["genericFormNouns"])
        self.light_heads = frozenset(self.builder.bs["rules"]["lightHeads"]) | self.generic
        # 사전 항목: (종류, 값, 형태소 목록, 품사). 종류 branch(갈래 명사) | lexicon(손 형태 사전). 가장 긴 항목 먼저
        self.by_first: dict[str, list[dict]] = {}
        for name in self.values["branches"]["order"]:
            for ko in self.values["branches"][name]["nouns"]:
                self.by_first.setdefault(ko[0], []).append({"kind": "branch", "branch": name, "ko": ko, "pos": "noun"})
        for e in self.shape_lex["entries"]:
            self.by_first.setdefault(e["ko"][0], []).append({"kind": "lexicon", "ko": e["ko"], "pos": e["pos"],
                                                             "slot": e["slot"]})
        for v in self.by_first.values():
            v.sort(key=lambda e: (-len(e["ko"]), e["kind"] != "branch"))
        # 차단 낱말(형태 자리): 손 형태 사전 blocked person·animal + 사람 닮은 사물(G73-a). 안개·빛 같은 nonMeshable은 갈래 명사다
        b = self.shape_lex["blocked"]
        self.listed: dict[str, str] = {w: "person" for w in b["person"]}
        self.listed.update({w: "animal" for w in b["animal"]})
        self.listed.update({w: "humanlike" for w in self.filt["humanlike"]["ko"]})
        cats = set(self.filt["emotionCategories"])
        self.emotion_words = frozenset(f for e in self.builder.lexicon.entries if e.category in cats
                                       for f in (e.lemma, *e.alt))
        vad = json.loads(Path(shared("lexicon", "vad_ko.v0.json")).read_text(encoding="utf-8"))
        self.emotion_words |= frozenset(e["lemma"] for e in vad["entries"])
        self.non_object_words = frozenset(f for e in self.builder.lexicon.entries
                                          if e.category not in _OBJECT_CATEGORIES for f in (e.lemma, *e.alt))
        d = self.values["density"]
        self.density_terms = {(t["form"], t["tag"]): t["level"] for t in d["terms"]}
        self.density_mods = {w: kind for kind in ("less", "more", "soft") for w in d["modifiers"][kind]}

    # ── 외부 정보 ───────────────────────────────────────────────────────────────
    def info(self) -> dict:
        return {"mappingVersion": RESAY_MAPPING_VERSION, "resayValues": self.table_id,
                "resayValuesSha256": self.values_sha, "builder": self.builder.builder_id,
                "shapeLexicon": f"{self.shape_lex['lexiconId']}@{self.shape_lex['lexiconVersion']}",
                "promptFilter": f"{self.filt['lexiconId']}@{self.filt['tableVersion']}"}

    # ── 진입점 ─────────────────────────────────────────────────────────────────
    def map(self, text: str) -> dict:
        norm = normalize_confirmed(text)
        toks = self.analyzer.tokens(norm)
        doc = Doc(norm, toks)
        spec = self.builder.build(norm)
        context = self.builder._context_sentences(doc)
        neg_spans = [tuple(n["_provenance"]["charSpan"]) for n in spec.get("_negated") or []
                     if (n.get("_provenance") or {}).get("charSpan")]
        mediators: set[int] = set()
        for a in self.builder._action_similes(doc):          # G71: 움직임 비유의 매개어는 형태를 정하지 않는다
            mediators |= set(a["vehicles"])
        dropped: list[dict] = []
        words = self._form_words(doc, context, neg_spans, mediators, dropped)
        blocked = self._blocked(doc, spec, words)
        branch, basis = self._branch(words, blocked)
        values = {p: None for p in self.allowed}
        not_read: list[dict] = []
        self._builder_values(spec, values, not_read)
        if branch == "mist":
            w = basis[0]
            values["form.type"] = self._record("mist", [w["charSpan"]], [w["ko"]],
                                               [f"resay.branch.mist({w['ko']})>form.type:mist"], "resay_branch")
        self._density(doc, context, mediators, branch, values, dropped, not_read)
        self._visibility(doc, context, values, dropped, not_read)
        if branch == "light" and values.get("material.emission") is None:
            w = basis[0]
            implied = self.values["branches"]["light"]["impliedEmission"]
            values["material.emission"] = self._record(
                implied, [w["charSpan"]], [w["ko"]], [f"resay.branch.light({w['ko']})>material.emission:{implied}"],
                "lexicon_implied")
        values = {p: values[p] for p in self.allowed}       # 키 순서 고정, 허용 슬롯만
        return {
            "mappingVersion": RESAY_MAPPING_VERSION,
            "tables": self.info(),
            "sourceTextSha256": _sha(norm),
            "chars": len(norm),
            "branch": branch,
            "branchBasis": basis,
            "blockDetail": sorted({f"{b['kind']}:{b['ko']}" for b in blocked}) or None,
            "values": values,
            "notRead": not_read,
            "formWords": words,
            "dropped": sorted(dropped, key=lambda d: (d["charSpan"][0], d["charSpan"][1], d["reason"])),
        }

    # ── 형태 자리 낱말 ──────────────────────────────────────────────────────────
    def _match(self, toks, i: int) -> tuple[int, int, dict] | None:
        t = toks[i]
        for e in self.by_first.get(t.form, []):
            n = len(e["ko"])
            seg = toks[i:i + n]
            if len(seg) < n or [x.form for x in seg] != e["ko"]:
                continue
            if any(seg[m].start != seg[m - 1].end for m in range(1, n)):
                continue
            if e["pos"] == "noun":
                if not all(x.base_tag in NOUNISH for x in seg) or not noun_run_bounds(toks, i, i + n - 1):
                    continue
            elif not (n == 1 and t.base_tag in _PRED_TAGS):
                continue
            return i, i + n - 1, e
        return None

    def _form_words(self, doc: Doc, context: set, neg_spans, mediators: set, dropped: list) -> list[dict]:
        """형태 자리 낱말을 글 차례로. kind: branch(갈래 명사) | lexicon(손 형태 사전) | listed(차단 낱말) | unlisted(사전 밖 명사)."""
        toks, norm = doc.toks, doc.text
        raw = []
        i = 0
        while i < len(toks):
            hit = self._match(toks, i)
            if hit:
                a, b, e = hit
                raw.append((a, b, e))
                i = b + 1
                continue
            t = toks[i]
            if t.base_tag in ("NNG", "NNP"):
                j = i                                  # 붙어 쓴 명사 연속('솔방울')을 한 낱말로
                while j + 1 < len(toks) and toks[j + 1].base_tag in ("NNG", "NNP") and toks[j + 1].start == toks[j].end:
                    j += 1
                run = norm[toks[i].start:toks[j].end]
                if any(toks[k].form in self.listed for k in range(i, j + 1)):
                    for k in range(i, j + 1):          # '곰인형' → '곰'(동물)·'인형'(사람 닮은 사물) 각각
                        if toks[k].form in self.listed:
                            raw.append((k, k, {"kind": "listed", "listed": self.listed[toks[k].form], "pos": "noun"}))
                elif j + 1 < len(toks) and toks[j + 1].base_tag in ("XSV", "XSA") and toks[j + 1].start == toks[j].end:
                    pass                               # 서술성 명사 + -하다('불안하다')는 사물 이름이 아니다
                elif not (run in self.builder.stop_nouns or run in self.generic or run in self.emotion_words
                          or run in self.non_object_words or toks[i].form in self.builder.stop_nouns):
                    raw.append((i, j, {"kind": "unlisted", "pos": "noun"}))
                i = j + 1
                continue
            i += 1
        lexical_starts = {a for a, _, _ in raw}
        out = []
        for a, b, e in raw:
            s, en_ = toks[a].start, toks[b].end
            ko = norm[s:en_]
            base = {"ko": ko, "charSpan": [s, en_], "kind": e["kind"]}
            if e["kind"] == "branch":
                base["branch"] = e["branch"]
            elif e["kind"] == "lexicon":
                base["slot"] = e["slot"]
            elif e["kind"] == "listed":
                base["listed"] = e["listed"]
            reason = None
            pred_neg = None
            if doc.sent[a] in context:
                reason = "context_sentence"
            elif negated_near(doc, a, b, lexical_starts, neg_spans):
                pred_neg = self._predicate_negation(doc, b) if e["pos"] == "noun" else None
                if pred_neg is None:
                    reason = "negated"
            elif any(k in mediators for k in range(a, b + 1)):
                reason = "action_simile"
            pos = form_position(doc, b, self.loc_nouns, self.size_nouns) if e["pos"] == "noun" else "pred"
            if reason is None and pos in _SKIP_POSITIONS:
                reason = pos
            if reason:
                if e["kind"] != "unlisted":
                    dropped.append({"ko": ko, "charSpan": [s, en_], "reason": reason, "kind": e["kind"]})
                continue
            nxt = next_noun(doc, b)
            if pred_neg is not None:                   # 부정은 서술어의 것: 근거(서술어·부정 표지 글자 위치)를 남긴다
                base["predicateNegation"] = {"charSpan": pred_neg, "rule": "resay.negation.predicate_scope"}
            out.append({**base, "position": pos, "tokens": [a, b],
                        "nextNoun": toks[nxt].form if nxt is not None else None})
        return out

    def _predicate_negation(self, doc: Doc, b: int) -> list[int] | None:
        """명사(끝 토큰 b)가 바로 뒤 서술어의 주어이고, 그 서술어가 부정됐으며(안·못 + 용언, 용언-지 않·못, -ㄴ 게 아니다),
        그 서술어가 존재(있·없)가 아니면 [서술어(앞 '안'부터)–마지막 부정 표지] 글자 위치. 아니면 None(공유 판정 그대로).
        - 주어: 명사 바로 뒤가 같은 어절의 주격 조사·보조사 하나로 어절이 끝나거나, 표지 없이 어절이 끝난다.
        - 주어와 서술어 사이에는 부사 한 낱말짜리 어절(MAG, '안'·'못' 말고)만 올 수 있다('안개가 잘 안 보여요').
        - 지정 부정('안개가 아니에요')·쉼표 정정('안개, 아니 연기')·비유('안개 같은 게 안 보여요')는 여기 걸리지 않는다."""
        toks = doc.toks
        n = len(toks)
        m = b + 1
        if m < n and doc.eoj[m] == doc.eoj[b]:
            if toks[m].base_tag not in _SUBJECT_TAGS:
                return None
            m += 1
            if m < n and doc.eoj[m] == doc.eoj[b]:
                return None
        while m < n and doc.sent[m] == doc.sent[b] and toks[m].base_tag == "MAG" and toks[m].form not in ("안", "못") \
                and (m + 1 >= n or doc.eoj[m + 1] != doc.eoj[m]):
            m += 1
        if m >= n or doc.sent[m] != doc.sent[b]:
            return None
        if toks[m].form in ("안", "못") and toks[m].base_tag == "MAG":
            k = m + 1
            if k >= n or doc.sent[k] != doc.sent[b] or toks[k].base_tag not in _PRED_HEAD_TAGS:
                return None
        elif toks[m].base_tag in _PRED_HEAD_TAGS:
            k = m
        else:
            return None
        if toks[k].form in _EXIST_PREDS:
            return None
        negs = self._negators(doc, k)
        if not negs:
            return None
        return [toks[min(k, negs[0])].start, toks[max(k, negs[-1])].end]

    def _blocked(self, doc: Doc, spec: dict, words: list[dict]) -> list[dict]:
        """사람·동물·사람 닮은 사물이 형태 자리에 오면 갈래 blocked. 규칙은 G45·G62 형태 프롬프트와 같다:
        중심 명사면 막음, 명사 꾸밈이면 뒤 명사가 가벼운 머리('모양'·'형상')일 때만, 비유 원천이면 뒤가 형태 명사가 아닐 때."""
        out = []
        for u in spec.get("_unmapped") or []:              # 매퍼 v2의 제외 판정(G45–G51, 죽음·자해·외상 formBlock 포함)
            v = u.get("value") if isinstance(u.get("value"), dict) else {}
            if u.get("reason") in ("excluded_shape", "no_asset") and (v.get("formSaid") is True or v.get("formBlock") is True):
                out.append({"kind": str(v.get("excluded") or v.get("noAsset")), "ko": u.get("lemma"),
                            "charSpan": (u.get("_provenance") or {}).get("charSpan")})
        lex_nouns = {e["ko"][0] for e in self.shape_lex["entries"] if e["pos"] == "noun" and len(e["ko"]) == 1}
        for w in words:
            if w["kind"] != "listed":
                continue
            pos, nxt = w["position"], w["nextNoun"]
            if pos == "head":
                hit = True
            elif pos == "noun_modifier":
                hit = nxt in self.light_heads
            else:
                hit = not (nxt and nxt in lex_nouns and nxt not in self.generic)
            if hit:
                out.append({"kind": w["listed"], "ko": w["ko"], "charSpan": w["charSpan"]})
        return out

    def _branch(self, words: list[dict], blocked: list[dict]) -> tuple[str, list[dict]]:
        if blocked:
            return "blocked", [{"ko": b["ko"], "charSpan": b["charSpan"], "rule": f"resay.blocked.{b['kind']}"}
                               for b in blocked]
        nouns = [w for w in words if w["kind"] in ("branch", "lexicon", "unlisted") and w["position"] in _FORM_POSITIONS
                 and not (w["kind"] == "lexicon" and w.get("slot") != "shape_noun")]
        pick = next((w for w in nouns if w["position"] == "head"), None) or (nouns[0] if nouns else None)
        if pick is None and any(w["kind"] == "lexicon" and w.get("slot") == "shape_modifier" for w in words):
            mod = next(w for w in words if w["kind"] == "lexicon" and w.get("slot") == "shape_modifier")
            return "solid", [{"ko": mod["ko"], "charSpan": mod["charSpan"], "rule": "resay.solid.shape_modifier"}]
        if pick is None:
            return "none", []
        if pick["kind"] == "branch":
            br = pick["branch"]
            rule = f"resay.branch.{br}({pick['position']})"
        else:
            br = "solid"
            rule = f"resay.solid.{pick['kind']}({pick['position']})"
        return br, [{"ko": pick["ko"], "charSpan": pick["charSpan"], "rule": rule}]

    # ── 허용 슬롯 값 ────────────────────────────────────────────────────────────
    def _record(self, value, spans, kos, rules, source, table=None) -> dict:
        return {"value": value, "charSpans": spans, "ko": kos, "rules": rules, "source": source,
                "table": table or self.table_id}

    def _builder_values(self, spec: dict, values: dict, not_read: list) -> None:
        """매퍼 v2가 말한 값으로 채운 슬롯 가운데 허용 슬롯(form.type 제외)만 값으로, 나머지는 경로·글자 위치만."""
        take = {"layout.proportions": ("layout", "proportions"), "material.opacity": ("material", "opacity"),
                "material.emission": ("material", "emission")}
        for path, provs in (spec.get("_provenance") or {}).items():
            provs = provs if isinstance(provs, list) else [provs]
            spans = [list(p["charSpan"]) for p in provs if p.get("charSpan")]
            if path in take and path in self.allowed:
                grp, key = take[path]
                v = (spec.get(grp) or {}).get(key)
                if v is None:
                    continue
                values[path] = self._record(v, spans, [p.get("trigger") for p in provs], [p.get("rule") for p in provs],
                                            "mapper_v2", self.builder.builder_id)
            elif path == "form.type":
                continue                                   # 형태는 갈래가 정한다(mist만 값으로)
            else:
                not_read.append({"path": path, "charSpans": spans, "reason": "not_allowed_slot"})

    def _negators(self, doc: Doc, k: int) -> list[int]:
        """용언·어근 k를 부정하는 표지의 토큰 위치(글 차례). 범위는 k에 걸리는 것만 센다(CP13 지적 1).
        - 앞 부정: k 바로 앞 '안'·'못'(MAG, 같은 문장). 다른 용언 앞의 '안'은 그 용언의 것이다.
        - 뒤 부정: k와 같은 어절의 '-지'(EC) (+ 보조사 JX) 뒤 '않'·'못'(VX). 그 '않'에 다시 '-지 않'이 붙으면
          ('보이지 않지는 않아요') 바깥 부정으로 또 센다.
        - 바깥 부정: 부정 사슬 끝 어절이 관형형(ETM) + '것'(NNB) (+ 격조사·보조사) + '아니'(VCN)('보이는 게 아니에요').
        다른 절('짙지 않고 안 보여요')의 부정은 그 절 용언에만 걸린다. 극성은 _polarity: 표지 0개 = 부정 없음,
        1개 = 부정, 2개 이상 = 이중 부정(홀짝으로 뜻을 정하지 않는다)."""
        toks = doc.toks
        out: list[int] = []
        if k > 0 and toks[k - 1].form in ("안", "못") and toks[k - 1].base_tag == "MAG" and doc.sent[k - 1] == doc.sent[k]:
            out.append(k - 1)
        p = k
        while True:                                     # 뒤 부정 사슬: 용언 → -지 → 않 → -지 → 않 …
            nxt = None
            m = p + 1
            while m < len(toks) and doc.eoj[m] == doc.eoj[p]:
                if toks[m].form == "지" and toks[m].base_tag == "EC":
                    n = m + 1
                    while n < len(toks) and toks[n].base_tag == "JX":
                        n += 1
                    if n < len(toks) and toks[n].form in ("않", "못") and toks[n].base_tag in ("VX", "MAG"):
                        nxt = n
                    break
                if toks[m].base_tag in ("EC", "ETM", "EF", "ETN"):
                    break                               # 어미에서 어절의 용언이 끝난다(다음 용언의 '-지'는 그 용언 것)
                m += 1
            if nxt is None:
                break
            out.append(nxt)
            p = nxt
        m = p + 1                                       # 바깥 부정: -ㄴ 것이 아니다
        while m < len(toks) and doc.eoj[m] == doc.eoj[p] and toks[m].base_tag != "ETM":
            if toks[m].base_tag in ("EC", "EF", "ETN"):
                return out
            m += 1
        if m < len(toks) and toks[m].base_tag == "ETM" and doc.eoj[m] == doc.eoj[p]:
            n = m + 1
            if n < len(toks) and toks[n].form in ("것", "거") and toks[n].base_tag == "NNB":
                n += 1
                while n < len(toks) and toks[n].base_tag in ("JKS", "JKC", "JX"):
                    n += 1
                if n < len(toks) and toks[n].form == "아니" and toks[n].base_tag == "VCN" and doc.sent[n] == doc.sent[k]:
                    out.append(n)
        return out

    def _polarity(self, doc: Doc, k: int) -> str:
        """plain(부정 없음) | negated(표지 1개) | double_negation(2개 이상: 규칙이 뜻을 확정하지 못함 → 값을 채우지 않는다)."""
        n = len(self._negators(doc, k))
        return "plain" if n == 0 else ("negated" if n == 1 else "double_negation")

    def _density(self, doc: Doc, context: set, mediators: set, branch: str, values: dict, dropped: list,
                 not_read: list) -> None:
        d = self.values["density"]
        toks, norm = doc.toks, doc.text
        found = False
        for k, t in enumerate(toks):
            level = self.density_terms.get((t.form, t.base_tag))
            if level is None:
                continue
            e_span = doc.espan(doc.eoj[k])
            if doc.sent[k] in context:
                dropped.append({"ko": norm[e_span[0]:e_span[1]], "charSpan": list(e_span), "reason": "context_sentence",
                                "kind": "density"})
                continue
            mod, mod_k = None, None
            for m in range(k - 1, -1, -1):
                if doc.sent[m] != doc.sent[k] or doc.eoj[k] - doc.eoj[m] > d["modifiers"]["window"]:
                    break
                if toks[m].base_tag == "MAG" and toks[m].form in self.density_mods:
                    mod, mod_k = self.density_mods[toks[m].form], m
                    break
            pol = self._polarity(doc, k)
            key = level + ("+negated" if pol == "negated" else (f"+{mod}" if mod else ""))
            s0 = toks[mod_k].start if mod_k is not None else e_span[0]
            span = [s0, e_span[1]]
            ko = norm[span[0]:span[1]]
            if branch != "mist":
                dropped.append({"ko": ko, "charSpan": span, "reason": "branch_not_mist", "kind": "density"})
                continue
            if pol == "double_negation":                # 원칙 2: 말한 뜻을 규칙이 확정할 수 없으면 비운다
                negs = self._negators(doc, k)           # 글자 위치: 앞 '안'부터 마지막 부정 표지까지
                not_read.append({"path": d["path"], "reason": "double_negation",
                                 "charSpans": [[min(span[0], toks[negs[0]].start), max(span[1], toks[negs[-1]].end)]]})
                continue
            if found:
                dropped.append({"ko": ko, "charSpan": span, "reason": "later_mention", "kind": "density"})
                continue
            found = True
            v = d["values"][key]
            values[d["path"]] = self._record(v, [span], [ko], [f"resay.density.{key}({ko})>{d['path']}:{v}"], "resay_rule")

    def _visibility(self, doc: Doc, context: set, values: dict, dropped: list, not_read: list) -> None:
        rule = self.values["visibility"]["rules"][0]
        path = self.values["visibility"]["path"]
        toks, norm = doc.toks, doc.text
        for k, t in enumerate(toks):
            if not (t.form == "보이" and t.base_tag == "VV") or doc.sent[k] in context:
                continue
            negs = self._negators(doc, k)
            if not negs:
                continue
            if len(negs) > 1:                           # 이중 부정('안 보이지는 않아요'): 값을 채우지 않는다(원칙 2)
                s = toks[min(k, negs[0])].start         # 글자 위치: 앞 '안'부터 마지막 부정 표지까지
                e = toks[max(k, negs[-1])].end
                not_read.append({"path": path, "charSpans": [[s, e]], "reason": "double_negation"})
                continue
            a = k - 1 if negs[0] < k else k
            s = toks[a].start
            e = toks[k].end
            m = k + 1                                   # '-지 않'까지 원문 위치에 넣는다
            while m < len(toks) and doc.eoj[m] <= doc.eoj[k] + 1 and toks[m].base_tag in ("EC", "JX", "VX", "ETM", "EF"):
                e = toks[m].end
                if toks[m].base_tag == "VX":
                    break
                m += 1
            ko = norm[s:e]
            if values.get(path) is not None:
                dropped.append({"ko": ko, "charSpan": [s, e], "reason": "lower_priority", "kind": "visibility"})
                return
            values[path] = self._record(rule["value"], [[s, e]], [ko],
                                        [f"resay.visibility.{rule['id']}({ko})>{path}:{rule['value']}"], "resay_rule")
            return


def mapping_bytes(m: dict) -> bytes:
    """매핑 결과의 고정 바이트(결정성 비교·기록용)."""
    return json.dumps(m, ensure_ascii=False, indent=2).encode("utf-8")
