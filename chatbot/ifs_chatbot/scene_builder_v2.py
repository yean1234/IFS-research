"""확정 텍스트 → SceneSpec v2.2 — 매핑 v2 (화이트박스. 학습·LLM·임베딩 없음).

v1(scene_builder_v1.py)을 상속해 아래 차이만 더한다. v0·v1 코드·설정 파일은 바꾸지 않으므로 v0·v1 출력은 그대로다.
같은 확정 텍스트(+ 같은 meta 인자)는 언제나 같은 dict, 같은 파일 바이트가 된다(시각·난수·빌드 사이 상태 없음).
설정: shared/lexicon/scene_params.v2.json(규칙·수치), shared/lexicon/noun_stoplist.v2.json(불용 명사).
근거 문서: docs/prompts/prototype-v4-build.md 단계 D의 D1·D2, docs/validation/mock-forms/README.md 7절,
docs/mapping-audit.md A06·A14. 비교 결과: docs/validation/mapper-v2/README.md.

D1  사전에 없는 명사 기록
    확정 텍스트의 명사(NNG·NNP) 중 1층 사전에 없고, 값·보존 기록이 덮지 않았고, 불용 명사가 아닌 것을 _unmapped에
    category unlisted_noun으로 남긴다. value.role(조사로 본 문장 성분)과 value.scope(main | context: 회상·상황절)를 붙인다.
    배경 사물 목록(backgroundNouns)에 있는 낱말이 '있다'의 주어면 형상 자체로 보고 배경 판정에서 뺀다
    ('가슴 앞에 작은 화분이 있어요'의 '작은'이 v1에서는 배경 사물 속성으로 빠졌다).
D2  형상이 보이지 않게 되는 오류
    (a) '거의 투명' · '투명에 가까운' → opacity 0이 아니라 nearlyTransparent(0.15). '완전히 투명'은 말한 대로 0.
        '반쯤 투명' → 0.5. 그 밖의 강한 정도 부사로 0이 되면 하한 0.05. 부분 한정('끝은 거의 투명')은 _parts로.
    (b) layout.distance 하한 0.1('코앞'과 같은 값). 신체 부위에 '붙어'는 거리가 아니라 몸 위치 → _unmapped.
        G33(builder 2.1.0): 하한을 적용하면 provenance rule 끝에 '+floor(0.1;said=<말한 값>)'를 붙여 말한 값과 그려진 값
        (슬롯 값)을 둘 다 남긴다. floor_record()가 이 기록을 읽는다(selection.json distanceFloor).
        '머리 위 한 뼘쯤 높이'처럼 높이 말 옆의 수치는 거리로 쓰지 않음(_measurements dimension unknown).
    (c) 자세어가 참여자 자신의 상태를 말한 절(상황절 '누웠을 때'·'서 있으면', 1인칭 주어 '제가 서 있는',
        신체 부위 주어 '몸이 처져요')이면 form.posture에 넣지 않고 _context에 남긴다.
    (d) '가슴 앞을 덮고'의 '앞'은 덮음 크기 기준(시야 전체 1.7 m)이 아니라 위치다.

D6  기본 형상 경로(builder 2.2.0, 결정 G21·G30, docs/asset-plan.md 3절)
    형상을 이름 붙이는 명사(shared/lexicon/base_shapes.v1.json)가 주어·이름·직유 원천이고 본 장면 문장이며 부정되지 않았으면
    form.base(container·line·sheet·flame·drop)에 넣고, 낱말 뜻과 같은 문장의 참여자 말이 정한 변형값을 form.baseVariant에 넣는다.
    그 명사의 다른 기록(_unmapped의 object·shape·unlisted_noun)은 지운다(이제 값의 근거). 안전 제외 낱말은 그리지 않고
    _unmapped reason excluded_shape로 남긴다. 출력은 언제나 specVersion 2.2.0(form.base·baseVariant가 null이어도 적음).

스키마 한계(스키마 2.2에서도 그대로): meta.mapping.used는 v0 | v1만 허용한다. v2는 requested = "v2",
used = "v1"(가장 가까운 값: v2는 v1 위의 수정), pipeline.builder = scene-spec-builder-v2/…로 남긴다.
대체 판정은 is_mapping_fallback()을 쓴다(v0·v1에서는 기존 판정 'used ≠ requested'와 같다).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .korean import Analyzer
from .lexicon import Hit, Lexicon
from .paths import shared
from .scene_builder import normalize_confirmed
from .scene_builder_v1 import (EOJEOL_TAG, NOUN_TAGS, PUNCT_TAGS, TOPIC_PARTICLES, Cand, Doc, SceneSpecBuilderV1,
                               fallback_spec)  # noqa: F401 (fallback_spec: 컨트롤러가 같은 대체 경로를 씀)
from .scene_spec import (MAPPING_USED_FOR, SPEC_VERSION_V22,  # noqa: F401 (v2 meta.mapping 규칙을 함께 내보냄)
                         is_mapping_fallback)

# 2.1.0(2026-11-23, G33): 거리 하한 꼬리표에 말한 값(said=…)을 더함
# 2.2.0(2026-11-23, D6·G30): 기본 형상 경로 form.base·form.baseVariant(스키마 2.2.0), 안전 제외 낱말 excluded_shape
BUILDER_VERSION = "2.2.0"
BUILDER_ID = f"scene-spec-builder-v2/{BUILDER_VERSION}"
MAPPER_ID = "v2"

# 보존 기록 중 '이미 다룬 말'로 보는 필드(D1). _clauses(전체 원문 색인)·_uncertain(절 전체)·_unmatched는 넣지 않는다
_COVER_KEYS = ("_provenance", "_unmapped", "_negated", "_alternatives", "_context", "_parts", "_measurements",
               "_direction", "_needsConfirmation")
_LOCATION_JKB = {"에", "에서", "로", "으로", "에게", "한테", "께", "까지", "에다"}


def _span_chars(node, out: set[int]) -> None:
    """node 안의 모든 charSpan이 덮는 글자 위치."""
    if isinstance(node, dict):
        cs = node.get("charSpan")
        if isinstance(cs, (list, tuple)) and len(cs) == 2:
            out.update(range(int(cs[0]), int(cs[1])))
        for v in node.values():
            _span_chars(v, out)
    elif isinstance(node, list):
        for v in node:
            _span_chars(v, out)


class SceneSpecBuilderV2(SceneSpecBuilderV1):
    mapper_id = MAPPER_ID

    def __init__(self, analyzer: Analyzer, lexicon: Lexicon | None = None, params_path: str | Path | None = None,
                 vad_path: str | Path | None = None, v2_params_path: str | Path | None = None,
                 stoplist_path: str | Path | None = None, base_shapes_path: str | Path | None = None):
        super().__init__(analyzer, lexicon, params_path, vad_path)
        self.p2 = json.loads(Path(v2_params_path or shared("lexicon", "scene_params.v2.json")).read_text(encoding="utf-8"))
        stop = json.loads(Path(stoplist_path or shared("lexicon", "noun_stoplist.v2.json")).read_text(encoding="utf-8"))
        self.stop_info = f"{stop['lexiconId']}@{stop['lexiconVersion']}"
        op, ds, po, un = self.p2["opacity"], self.p2["distance"], self.p2["posture"], self.p2["unlistedNouns"]
        self.op = op
        if op.get("partScoped"):
            self.part_scoped = set(self.part_scoped) | {"material.opacity"}
        self.opacity_nouns = set(op["opacityNouns"])
        self.dist_floor: float = ds["floor"]
        self.attach_lemmas = set(ds["bodyAttachLemmas"])
        self.attach_particles = set(ds["attachParticles"])
        self.self_words = set(ds["selfWords"]) | set(po["selfPronouns"])
        self.vertical_cues = set(ds["verticalCues"])
        self.sit_nouns = set(po["situationNouns"])
        self.cond_endings = set(po["conditionalEndings"])
        self.subj_particles = set(po["subjectParticles"])
        self.exist_preds = set(self.p2["figureNoun"]["existencePredicates"])
        self.noun_tags = set(un["tags"])
        # 불용 명사 = 표 + scene_params.v1의 부분·위치·차원·때 낱말(alsoExclude)
        words = {w for g in stop["groups"].values() for w in g["words"]}
        for ref in un["alsoExclude"]:
            node = self.params
            for part in ref.split("."):
                node = node[part]
            if isinstance(node, dict) and node and all(isinstance(x, list) for x in node.values()):
                words |= {w for ws in node.values() for w in ws}      # partNouns: 부류 → 낱말 목록
            else:
                words |= set(node)                                   # 목록, 또는 낱말이 키인 사전
        self.stop_nouns = frozenset(words)
        self.scene_time_nouns = frozenset(un["sceneTimeNouns"]) | set(self.v["contextSentence"]["situationNouns"])
        self.recall_verbs = frozenset(un["unambiguousRecallVerbs"])
        # 1층 사전의 모든 표제어·이형(범주 무관): 여기 있는 낱말은 '사전에 있는 말'
        self.lex_forms = frozenset(f for e in self.lexicon.entries for f in (e.lemma, *e.alt))
        # D6 기본 형상 사전
        bs = json.loads(Path(base_shapes_path or shared("lexicon", "base_shapes.v1.json")).read_text(encoding="utf-8"))
        self.bs = bs
        self.bs_info = f"{bs['lexiconId']}@{bs['lexiconVersion']}"
        self.bs_entries: dict[str, dict] = {e["lemma"]: e for e in bs["entries"]}
        self.bs_excluded: dict[str, str] = {w: code for code, ws in bs["excluded"].items()
                                            if not code.startswith("_") and code != "notListed" for w in ws}
        self.bs_roles = frozenset(bs["rules"]["roles"])
        self.bs_similes = bool(bs["rules"]["similes"])
        self.bs_cues: dict[str, dict] = {k: v for k, v in bs["variantCues"].items() if not k.startswith("_")}

    # ── 외부 정보 ───────────────────────────────────────────────────────────────
    @classmethod
    def from_runtime(cls, rt) -> "SceneSpecBuilderV2":
        return cls(rt.analyzer)

    def info(self) -> dict:
        return {"builder": BUILDER_ID, "specVersion": SPEC_VERSION_V22, "lexicons": self._lexicons(), "mapper": MAPPER_ID}

    def _lexicons(self) -> dict:
        return {**super()._lexicons(),
                "sceneParamsV2": f"{self.p2['lexiconId']}@{self.p2['lexiconVersion']}",
                "nounStoplist": self.stop_info, "baseShapes": self.bs_info}

    # ── 진입점 ─────────────────────────────────────────────────────────────────
    def build(self, text: str, *, session_id: str | None = None, participant_id: str | None = None,
              condition: str | None = None) -> dict:
        spec = super().build(text, session_id=session_id, participant_id=participant_id, condition=condition)
        spec["meta"]["pipeline"]["builder"] = BUILDER_ID
        spec["meta"]["mapping"] = {"requested": MAPPER_ID, "used": MAPPING_USED_FOR[MAPPER_ID], "fallbackReason": None}
        # D1: v1 build가 끝난 spec 위에서 다시 분석한다(같은 분석기·같은 텍스트라 결정적. 빌드 사이 상태를 두지 않음)
        norm = normalize_confirmed(text)
        doc = Doc(norm, self.analyzer.tokens(norm))
        hits = list(self.lexicon.hits(norm))
        added = self._unlisted_nouns(doc, hits, spec)
        if added:
            spec["_unmapped"] = sorted(spec["_unmapped"] + added,
                                       key=lambda u: (u["_provenance"]["charSpan"][0], u["lemma"], u["category"]))
            # 기록한 명사는 '읽지 못한 말'이 아니다(사전 낱말이 _unmatched에 안 남는 것과 같게). 어절 항목은 다시 계산한다
            spans = sorted({tuple(u["_provenance"]["charSpan"]) for u in added})
            tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG
                         and not any(s <= u["charSpan"][0] and u["charSpan"][1] <= e for s, e in spans)]
            spec["_unmatched"] = tok_level
            spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                        key=lambda u: (u["charSpan"][0], u["charSpan"][1]))
        # D6: 기본 형상(스키마 2.2.0). form 묶음의 키 순서는 type · posture · base · baseVariant
        base, variant, changed = self._base_shapes(doc, spec)
        spec["meta"]["specVersion"] = SPEC_VERSION_V22
        spec["form"] = {"type": spec["form"]["type"], "posture": spec["form"]["posture"], "base": base,
                        "baseVariant": variant}
        if changed:
            tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG]
            spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                        key=lambda u: (u["charSpan"][0], u["charSpan"][1]))
        return spec

    # ── D6: 기본 형상 ─────────────────────────────────────────────────────────
    def _base_role(self, doc: Doc, j: int) -> str:
        """base 판정용 문장 성분. '종이 한 장이'·'물방울 하나가'처럼 바로 뒤 어절이 수량 표현(관형사·수사·숫자 + 단위)이면
        그 수량 표현의 성분을 쓴다."""
        role = self._noun_role(doc, j)
        if role != "other":
            return role
        toks = doc.toks
        n = len(toks)
        k = j + 1
        while k < n and toks[k].base_tag == "XSN":
            k += 1
        if k >= n or doc.eoj[k] == doc.eoj[j] or toks[k].base_tag not in ("MM", "NR", "SN"):
            return role
        if toks[k].base_tag == "NR":
            return self._noun_role(doc, k)                       # '하나가'
        m = k + 1                                                # '한 장이' · '2 개가'
        if m < n and toks[m].base_tag in ("NNB", "NNG") and doc.eoj[m] in (doc.eoj[k], doc.eoj[k] + 1):
            return self._noun_role(doc, m)
        return role

    def _base_shapes(self, doc: Doc, spec: dict) -> tuple[str | None, dict | None, bool]:
        """형상 낱말 → form.base. (base, baseVariant, spec 기록을 바꿨는지). spec의 기록 필드를 제자리에서 고친다."""
        toks, text = doc.toks, doc.text
        n = len(toks)
        valued: set[int] = set()
        _span_chars(spec.get("_provenance"), valued)
        context_sents = self._context_sentences(doc) | self._situation_sentences(doc, valued)
        regions = self._situation_regions(doc)
        sim_src = {sm["srcIndex"]: sm for sm in self._similes(text, toks)} if self.bs_similes else {}
        hits: list[dict] = []
        i = 0
        while i < n:
            if toks[i].base_tag not in NOUN_TAGS:
                i += 1
                continue
            j = i
            while j + 1 < n and toks[j + 1].base_tag in NOUN_TAGS and toks[j + 1].start == toks[j].end \
                    and doc.eoj[j + 1] == doc.eoj[i]:
                j += 1
            a, b = i, j
            i = j + 1
            s, e = toks[a].start, toks[b].end
            lemma = text[s:e]
            entry, code = self.bs_entries.get(lemma), self.bs_excluded.get(lemma)
            if entry is None and code is None:
                continue
            if doc.sent[b] in context_sents or any(s0 <= a and b < k0 for s0, k0 in regions):
                continue                                         # 회상·상황 문장의 명사
            negated = Lexicon._negated(toks, b) or self._noun_negated(doc, b)
            sim = sim_src.get(b)
            if sim is None and self._base_role(doc, b) not in self.bs_roles:
                continue                                         # 장소·목적어·꾸밈말
            hits.append({"a": a, "b": b, "s": s, "e": e, "lemma": lemma, "entry": entry, "code": code,
                         "negated": negated, "simile": sim})
        changed = False
        unmapped = spec["_unmapped"]

        # 안전 제외 낱말: 그리지 않고 기록만(대신할 형상도 그리지 않음)
        for h in hits:
            if h["code"] is None or h["negated"]:
                continue
            changed = True
            same_span = [u for u in unmapped if u["_provenance"]["charSpan"] == [h["s"], h["e"]]]
            if same_span:
                for u in same_span:
                    u["reason"] = "excluded_shape"
                    u["value"] = {**u["value"], "excluded": h["code"]}
            else:
                unmapped.append({"lemma": h["lemma"], "category": "excluded_noun",
                                 "value": {"noun": h["lemma"], "excluded": h["code"]}, "reason": "excluded_shape",
                                 "_provenance": self._prov("explicit_lexicon", text, h["s"], h["e"],
                                                           f"baseShapes.excluded.{h['lemma']}")})
        # 부정된 형상 낱말: _negated에 남긴다(이미 있으면 그대로)
        for h in hits:
            if h["entry"] is None or not h["negated"]:
                continue
            if not any(x["_provenance"]["charSpan"] == [h["s"], h["e"]] for x in spec["_negated"]):
                changed = True
                spec["_negated"].append({"lemma": h["lemma"], "category": "base_shape",
                                         "_provenance": self._prov("explicit_lexicon", text, h["s"], h["e"],
                                                                   f"baseShapes.{h['lemma']}")})
        if changed:
            spec["_negated"].sort(key=lambda x: (x["_provenance"]["charSpan"][0], x["lemma"], x["category"]))
            unmapped.sort(key=lambda u: (u["_provenance"]["charSpan"][0], u["lemma"], u["category"]))

        base_hits = sorted((h for h in hits if h["entry"] is not None and not h["negated"]), key=lambda h: h["s"])
        if not base_hits:
            return None, None, changed
        changed = True

        def prov(h: dict, rule: str) -> dict:
            src = "simile_marker" if h["simile"] is not None else "explicit_lexicon"
            tail = f"+simile({h['simile']['marker']})" if h["simile"] is not None else ""
            return self._prov(src, text, h["s"], h["e"], rule + tail)

        win = base_hits[0]
        key = win["entry"]["base"]
        same = [h for h in base_hits if h["entry"]["base"] == key]
        spec["_provenance"]["form.base"] = [prov(h, f"baseShapes.{h['lemma']}>form.base:{key}") for h in same]
        for h in base_hits:
            # 이 명사의 다른 기록(사물·모양어·사전에 없는 명사, 직유 원형 대기 포함)은 이제 값의 근거이므로 지운다.
            # 같은 낱말이고 구간이 겹치는 것만(직유 기록의 구간은 '상자 같'처럼 표지까지 덮는다)
            unmapped[:] = [u for u in unmapped if not (u["lemma"] == h["lemma"]
                                                       and u["category"] in ("object", "shape", "unlisted_noun")
                                                       and u["_provenance"]["charSpan"][0] < h["e"]
                                                       and h["s"] < u["_provenance"]["charSpan"][1])]
            if h["entry"]["base"] != key:
                spec["_alternatives"].append({"path": "form.base", "value": h["entry"]["base"], "reason": "later_mention",
                                              "_provenance": [prov(h, f"baseShapes.{h['lemma']}>form.base:{h['entry']['base']}")]})
        # 변형값: 낱말 뜻(이긴 명사의 사전 항목) → 같은 문장의 참여자 말이 덮어씀
        variant: dict[str, str] = {}
        vprov: dict[str, dict] = {}
        for k, v in (win["entry"].get("variant") or {}).items():
            variant[k] = v
            vprov[k] = prov(win, f"baseShapes.{win['lemma']}>form.baseVariant:{k}={v}")
        sents = {doc.sent[h["b"]] for h in same}
        for k, vals in (self.bs_cues.get(key) or {}).items():
            best = None                                          # (charSpan 시작, 값, provenance)
            for v, cue in vals.items():
                for x, t in enumerate(toks):
                    if doc.sent[x] not in sents or t.form not in cue.get("lemmas", ()) \
                            or t.base_tag not in ("VV", "VA", "XR") or Lexicon._negated(toks, x):
                        continue
                    if best is None or t.start < best[0]:
                        best = (t.start, v, self._tok_prov(doc, x, f"baseVariantCue.{t.form}>form.baseVariant:{k}={v}"))
                for u in unmapped:
                    cs = u["_provenance"]["charSpan"]
                    if u["category"] == "shape" and (u["value"] or {}).get("shape") in cue.get("shapeValues", ()) \
                            and any(doc.sent[x] in sents for x in doc.toks_in(cs[0], cs[1])):
                        if best is None or cs[0] < best[0]:
                            best = (cs[0], v, dict(u["_provenance"],
                                                   rule=f"baseVariantCue.{u['lemma']}>form.baseVariant:{k}={v}"))
            if best is not None:
                variant[k] = best[1]
                vprov[k] = best[2]
        if variant:
            variant = {k: variant[k] for k in sorted(variant)}
            spec["_provenance"]["form.baseVariant"] = [vprov[k] for k in sorted(vprov)]
        spec["_provenance"] = _ordered_provenance(spec["_provenance"])
        spec["_alternatives"].sort(key=lambda al: (_PATH_ORDER.get(al["path"], 99), al["_provenance"][0]["charSpan"][0],
                                                   al["reason"]))
        return key, (variant or None), changed

    # ── D1: 배경 사물이 형상인 경우 ───────────────────────────────────────────
    def _figure_background_tokens(self, doc: Doc, context_sents: set[int]) -> set[int]:
        """배경 사물 낱말(backgroundNouns)이 '있다'·'생기다'·'놓이다'의 주어이고 같은 절에 다른 배경 처소어가 없으면
        그 낱말은 형상이다. 같은 텍스트에서 같은 낱말의 모든 토큰 번호를 돌려준다."""
        toks = doc.toks
        n = len(toks)
        forms: set[str] = set()
        for k, t in enumerate(toks):
            if t.base_tag not in NOUN_TAGS or not self._is_background(t.form) or doc.sent[k] in context_sents:
                continue
            m = k + 1
            while m < n and toks[m].base_tag == "XSN":
                m += 1
            if m >= n or doc.eoj[m] != doc.eoj[k]:
                continue
            nt = toks[m]
            if not ((nt.base_tag == "JKS" and nt.form in ("이", "가")) or
                    (nt.base_tag == "JX" and nt.form in ("은", "는", "ᆫ", "도"))):
                continue
            ids = doc.clause_toks(doc.clause[k])
            if not any(x > m and toks[x].form in self.exist_preds and toks[x].base_tag in ("VV", "VA", "VX") for x in ids):
                continue
            if any(x != k and toks[x].base_tag in NOUN_TAGS and self._is_background(toks[x].form) and x + 1 < n
                   and toks[x + 1].base_tag == "JKB" for x in ids):
                continue      # '창가에 화분이 있어요' — 주변 장면 묘사
            forms.add(t.form)
        return {k for k, t in enumerate(toks) if t.base_tag in NOUN_TAGS and t.form in forms}

    # ── D1: 사전에 없는 명사 ───────────────────────────────────────────────────
    def _situation_regions(self, doc: Doc) -> list[tuple[int, int]]:
        """'소파에 누웠을 때'처럼 관형형 + 때·적·순간·동안이 맺는 상황절의 토큰 범위 [시작, 표지). 시작은 같은 절에서
        표지 앞의 가장 가까운 연결·종결 어미·문장부호·'-는데'의 '데' 다음이다(Kiwi가 '-는데'를 관형형 + 데로 내면
        절이 나뉘지 않으므로). 조건 어미 -면('빛을 받으면 반짝여요')은 형상의 행동을 말하는 일이 많아 명사 표시에는 쓰지 않는다."""
        toks = doc.toks
        n = len(toks)
        out = []
        for k, t in enumerate(toks):
            if not (t.base_tag == "ETM" and k + 1 < n and toks[k + 1].form in self.sit_nouns
                    and toks[k + 1].base_tag in NOUN_TAGS | {"NNB"} and doc.clause[k + 1] == doc.clause[k]):
                continue
            s = k
            while s - 1 >= 0 and doc.clause[s - 1] == doc.clause[k] and not (
                    toks[s - 1].base_tag in ("EC", "EF", "SF", "SP", "SE")
                    or (toks[s - 1].form == "데" and toks[s - 1].base_tag == "NNB")):
                s -= 1
            out.append((s, k))
        return out

    def _situation_sentences(self, doc: Doc, valued: set[int]) -> set[int]:
        """떠올린 상황을 말한 문장(scene_params.v2.json unlistedNouns.scopeNote ②–④). v1 회상 문장 규칙은 '-던'·'장면'만
        본다. 여기서는 명사 기록의 scope 표시에만 쓰고 슬롯 값은 바꾸지 않는다. valued = 슬롯 값 근거가 덮은 글자."""
        toks = doc.toks
        sit = set(self.v["contextSentence"]["situationNouns"])
        out: set[int] = set()
        for k, t in enumerate(toks):
            s = doc.sent[k]
            # ② 관형형 + 상황 명사로 끝남('연락이 끊긴 일이요')
            if t.base_tag == "ETM" and k + 1 < len(toks) and toks[k + 1].form in sit and doc.sent[k + 1] == s and all(
                    toks[j].base_tag in ("JX", "VCP", "EF", "EC", "JKS") or toks[j].base_tag in PUNCT_TAGS
                    for j in range(k + 2, len(toks)) if doc.sent[j] == s):
                out.add(s)
            # ③ 생각나다 · 기억나다 · 떠올리다
            if t.base_tag == "VV" and t.form in self.recall_verbs:
                out.add(s)
        # ④ 상황·시간 명사가 있고 슬롯 값이 하나도 나오지 않은 문장('주말 아침 산책이요' · '어제 회의요')
        for s in sorted(set(doc.sent)):
            ids = [i for i in range(len(toks)) if doc.sent[i] == s]
            if any(toks[i].base_tag in NOUN_TAGS | {"MAG"} and toks[i].form in self.scene_time_nouns for i in ids) and \
                    not any(c in valued for i in ids for c in range(toks[i].start, toks[i].end)):
                out.add(s)
        return out

    def _noun_role(self, doc: Doc, j: int) -> str:
        """명사(연속의 마지막 토큰 j) 뒤 조사로 본 문장 성분."""
        toks = doc.toks
        n = len(toks)
        k = j + 1
        while k < n and toks[k].base_tag == "XSN":
            k += 1
        if k >= n:
            return "named"
        nt = toks[k]
        if doc.eoj[k] != doc.eoj[j]:
            if nt.base_tag in PUNCT_TAGS:
                return "named"           # '얇은 막.' — 이름만 말함
            if nt.base_tag in NOUN_TAGS:
                return "location" if nt.form in self.v["relationalNouns"] else "modifier"
            return "other"
        if nt.base_tag == "VCP" or (nt.base_tag == "JX" and nt.form in ("요", "이요")):
            return "named"
        if nt.base_tag == "JKS" or (nt.base_tag == "JX" and nt.form in TOPIC_PARTICLES):
            return "subject"
        if nt.base_tag == "JKB":
            return "location" if nt.form in _LOCATION_JKB else "other"
        if nt.base_tag == "JKO":
            return "object"
        if nt.base_tag == "JKG":
            return "modifier"
        return "other"

    def _unlisted_nouns(self, doc: Doc, hits: list[Hit], spec: dict) -> list[dict]:
        toks, text = doc.toks, doc.text
        n = len(toks)
        covered: set[int] = set()
        for key in _COVER_KEYS:
            _span_chars(spec.get(key), covered)
        hit_toks = {h.token_index for h in hits}
        valued: set[int] = set()
        _span_chars(spec.get("_provenance"), valued)
        context_sents = self._context_sentences(doc) | self._situation_sentences(doc, valued)
        regions = self._situation_regions(doc)
        un = self.p2["unlistedNouns"]

        def free(i: int) -> bool:
            t = toks[i]
            if t.base_tag not in self.noun_tags or i in hit_toks or t.form in self.lex_forms or t.form in self.stop_nouns:
                return False
            return not all(c in covered for c in range(t.start, t.end))

        out: list[dict] = []
        i = 0
        while i < n:
            if toks[i].base_tag not in NOUN_TAGS:
                i += 1
                continue
            j = i      # 띄어쓰기 없이 붙은 명사 연속('빵가루' · '털실')
            while j + 1 < n and toks[j + 1].base_tag in NOUN_TAGS and toks[j + 1].start == toks[j].end \
                    and doc.eoj[j + 1] == doc.eoj[i]:
                j += 1
            run = list(range(i, j + 1))
            i = j + 1
            nx = toks[j + 1] if j + 1 < n else None
            if nx is not None and nx.base_tag in ("XSV", "XSA") and nx.start == toks[j].end:
                continue      # 서술성 명사 + -하다('퇴근하고' · '통화했던')는 사물 이름이 아니다
            frees = [x for x in run if free(x)]
            if not frees:
                continue
            groups = [run] if len(frees) == len(run) else [[x] for x in frees]
            for g in groups:
                a, b = g[0], g[-1]
                s, e = toks[a].start, toks[b].end
                lemma = text[s:e]
                in_region = any(s0 <= a and b < k0 for s0, k0 in regions)
                scope = "context" if (doc.sent[b] in context_sents or in_region) else "main"
                out.append({"lemma": lemma, "category": un["category"],
                            "value": {"noun": lemma, "role": self._noun_role(doc, b), "scope": scope},
                            "reason": un["reason"],
                            "_provenance": self._prov(un["provenanceSource"], text, s, e, f"unlistedNoun.{lemma}")})
        return out

    # ── 범위 규칙(D1 배경 사물 형상 · D2(c) 자세) ────────────────────────────
    def _scope(self, doc: Doc, cands: list[Cand], context_sents: set[int], similes) -> None:
        # 형상으로 판정한 배경 사물 낱말은 v1 _scope가 직유 원천 명사를 다루는 것과 같은 경로(sim_src)로 배경·자리 표지
        # 판정에서 뺀다. similes 목록 자체는 바꾸지 않고 _scope에 넘기는 사본에만 srcIndex를 더한다
        promoted = self._figure_background_tokens(doc, context_sents)
        super()._scope(doc, cands, context_sents, list(similes) + [{"srcIndex": k} for k in sorted(promoted)])
        for c in cands:
            if c.path == "form.posture" and c.status == "ok":
                why = self._self_posture(doc, c.tok)
                if why is not None:
                    c.status, c.reason = "context", why

    def _subject_in(self, doc: Doc, ids: list[int]) -> int | None:
        """토큰 목록에서 마지막 주어(체언 + 이/가/은/는/도)의 토큰 번호."""
        toks = doc.toks
        n = len(toks)
        out = None
        for x in ids:
            if toks[x].base_tag not in NOUN_TAGS | {"NP", "NNB"}:
                continue
            m = x + 1
            while m < n and toks[m].base_tag == "XSN":
                m += 1
            if m < n and doc.eoj[m] == doc.eoj[x] and toks[m].form in self.subj_particles \
                    and toks[m].base_tag in ("JKS", "JX"):
                out = x
        return out

    def _self_posture(self, doc: Doc, i: int) -> str | None:
        """자세어 토큰 i가 참여자 자신의 상태를 말하면 _context reason, 아니면 None(형상의 자세)."""
        toks = doc.toks
        n = len(toks)
        # ① 상황절: 자세어 어절(+ 바로 뒤 보조 용언 어절)이 관형형 + 때 … 또는 -면으로 끝남
        e0 = doc.eoj[i]
        eojs = [e0]
        if e0 + 1 < len(doc.eojeols) and toks[doc.eojeols[e0 + 1][0]].base_tag == "VX":
            eojs.append(e0 + 1)
        tail = [k for e in eojs for k in doc.etoks(e) if k > i]
        if any(toks[k].base_tag == "EC" and toks[k].form in self.cond_endings for k in tail):
            return "recollection_sentence"
        last = doc.eojeols[eojs[-1]][1]
        if toks[last].base_tag == "ETM" and last + 1 < n and toks[last + 1].form in self.sit_nouns \
                and doc.sent[last + 1] == doc.sent[i]:
            return "recollection_sentence"
        # ② · ③ 주어: 같은 절에서 먼저, 없으면 같은 문장의 앞 절(가까운 것부터)
        c = doc.clause[i]
        subj = self._subject_in(doc, [k for k in doc.clause_toks(c) if k < i])
        cc = c - 1
        while subj is None and cc >= 0:
            ids = doc.clause_toks(cc)
            if not ids or doc.sent[ids[0]] != doc.sent[i]:
                break
            subj = self._subject_in(doc, ids)
            cc -= 1
        if subj is None:
            return None
        st = toks[subj]
        if st.form in self.self_words and st.base_tag == "NP":
            return "background_subject"
        if st.form in self.body_forms:
            pe = doc.eoj[subj] - 1
            if pe < 0 or doc.eoj_clause(pe) != doc.clause[subj] or doc.is_punct_eoj(pe):
                return "background_subject"           # '몸이 축 처져요' — 소유자 없는 신체 부위 = 참여자 몸
            owner = [k for k in doc.etoks(pe) if toks[k].base_tag in NOUN_TAGS | {"NP"}]
            if not owner or (toks[owner[0]].form in self.self_words and toks[owner[0]].base_tag == "NP"):
                return "background_subject"           # '제 몸이' 또는 앞 어절이 소유자가 아님
            return None                               # '그 사람 어깨가' — 형상의 몸
        return None

    # ── D2(a)(b): 사전 후보 다듬기 ────────────────────────────────────────────
    def _lexicon_cands(self, doc: Doc, hits: list[Hit], consumed: set[int], similes, body_any: bool,
                       unmapped: list, negated: list, records) -> list[Cand]:
        toks = doc.toks
        # '투명에 가까운' — 가깝 앞 어절이 투명도 낱말 + 에면 거리 말이 아니다(v1은 색에만 이 규칙을 씀)
        near_opacity: set[int] = set()
        for h in hits:
            if h.entry.category != "distance" or h.entry.lemma not in self.op["nearPredicates"] or h.token_index in consumed:
                continue
            pe = doc.eoj[h.token_index] - 1
            if pe < 0 or doc.eoj_clause(pe) != doc.clause[h.token_index]:
                continue
            ts = list(doc.etoks(pe))
            if toks[ts[0]].form in self.opacity_nouns and toks[ts[-1]].base_tag == "JKB" and toks[ts[-1]].form == "에":
                consumed.add(h.token_index)
                near_opacity.add(ts[0])
        by_tok: dict[int, list[Hit]] = {}
        for h in hits:
            by_tok.setdefault(h.token_index, []).append(h)
        out = super()._lexicon_cands(doc, hits, consumed, similes, body_any, unmapped, negated, records)
        keep = []
        for c in out:
            rule = c.provs[0]["rule"]
            if c.path == "material.opacity" and rule.endswith(":transparent"):
                self._transparent(doc, c, c.tok in near_opacity)
            elif c.path == "layout.distance" and rule.endswith(":attached"):
                lem = next((h.entry.lemma for h in by_tok.get(c.tok, []) if h.entry.category == "distance"), None)
                if lem in self.attach_lemmas and self._attached_to_body(doc, c.tok, body_any):
                    unmapped.append({"lemma": lem, "category": "distance", "value": {"distance": "attached"},
                                     "reason": "no_scene_param", "_provenance": dict(c.provs[0], rule=rule.split(">")[0])})
                    continue
            keep.append(c)
        return keep

    def _transparent(self, doc: Doc, c: Cand, near: bool) -> None:
        """'투명' 후보의 값을 정도 표현에 맞춘다(D2(a)). 바꾸면 rule 끝에 +표시를 단다."""
        op = self.op
        rule = c.provs[0]["rule"]
        _, f = self._degree(doc, c.tok)
        word = doc.etext(f) if f is not None else None
        pe = doc.eoj[c.tok] - 1
        prev = doc.etext(pe) if pe >= 0 and doc.eoj_clause(pe) == doc.clause[c.tok] and not doc.is_punct_eoj(pe) else None
        if near or word in op["nearlyWords"]:
            c.value, tag = op["nearlyTransparent"], f"nearly({'가깝' if near else word})"
        elif word in op["totalWords"]:
            c.value, tag = op["total"], f"total({word})"
        elif prev in op["halfWords"]:
            c.value, tag = op["halfValue"], f"half({prev})"
        elif isinstance(c.value, (int, float)) and c.value < op["floor"]:
            c.value, tag = op["floor"], f"floor({op['floor']})"
        else:
            return
        c.provs = [dict(c.provs[0], rule=f"{rule}+{tag}"), *c.provs[1:]]

    def _attached_to_body(self, doc: Doc, i: int, body_any: bool) -> bool:
        """'붙다'(토큰 i)가 몸에 붙었다는 말인가.
        ① 같은 절 i 앞에 '신체 부위(+ 쪽) + 에'·'저한테' → 예 ② 같은 절 i 앞에 다른 처소어('눈앞에'·'얼굴 앞에') → 아니오
        (그 자리에 가깝게 붙음: 거리 값 + 하한) ③ 처소어가 없으면 텍스트에 신체 부위 위치를 말했을 때(body_any) 예
        ('옆구리 쪽에 뭔가 붙어 있어요 … 가만히 붙어 있어요')."""
        toks = doc.toks
        other_loc = False
        for x in doc.clause_toks(doc.clause[i]):
            if x >= i or toks[x].base_tag not in NOUN_TAGS | {"NP"}:
                continue
            k = x + 1
            while k < len(toks) and toks[k].form == "쪽" and toks[k].base_tag in ("NNB", "NNG", "XSN"):
                k += 1
            if k >= len(toks) or toks[k].base_tag != "JKB" or toks[k].form not in self.attach_particles:
                continue
            t = toks[x]
            if t.form in self.body_forms or (t.form in self.self_words and t.base_tag == "NP"):
                return True
            other_loc = True
        return not other_loc and body_any

    # ── D2(b): 높이 말 옆 수치 ────────────────────────────────────────────────
    def _measure_dimension(self, doc: Doc, ids: list[int], s: int, e: int) -> tuple[str, str | None]:
        dim, cue = super()._measure_dimension(doc, ids, s, e)
        if dim != "distance":
            return dim, cue
        c = doc.clause[ids[0]]
        near = [k for k in doc.clause_toks(c) if ids[0] - 3 <= k < ids[0] or max(ids) < k <= max(ids) + 3]
        if any(doc.toks[k].form in self.vertical_cues for k in near):
            return "unknown", "vertical"
        return dim, cue

    # ── D2(d): '가슴 앞을 덮고' ───────────────────────────────────────────────
    def _ref_noun(self, doc: Doc, i: int, table: dict[str, float]):
        r = super()._ref_noun(doc, i, table)
        if r is not None and table is self.cover and r[0] in self.v["relationalNouns"]:
            a = r[1]
            if a > 0 and doc.toks[a - 1].form in self.body_forms and doc.clause[a - 1] == doc.clause[a]:
                return None
        return r

    # ── 병합 전: 거리 하한 · 부분 투명도 ─────────────────────────────────────
    def _merge(self, cands: list[Cand], uncertain_paths: set[str], records):
        keep = []
        floor = self.dist_floor
        for c in cands:
            if c.path == "layout.distance" and isinstance(c.value, (int, float)) and c.value < floor:
                # G33: 하한은 유지하고 말한 값과 그려진 값을 둘 다 남긴다. 그려진 값 = 슬롯 값(하한), 말한 값 = rule 꼬리표의
                # said=…(스키마 2.1에는 이 둘을 구조로 담을 자리가 없어 provenance rule 문자열에 적는다. floor_record()가 읽는다)
                said = c.value
                c.value = floor
                c.provs = [dict(c.provs[0], rule=f"{c.provs[0]['rule']}+floor({floor};said={_num_text(said)})"),
                           *c.provs[1:]]
            # 부분만 말한 투명도는 전체 값으로 올리지 않는다. 단 '속이 비쳐요'(안쪽 + 비치다)는 속이 들여다보인다는 말,
            # 곧 형상 전체가 비친다는 뜻이므로 v1처럼 전체 값으로 둔다(dev D02·D16)
            if c.path == "material.opacity" and c.status == "ok" and c.kind != "fuzzy" and (
                    c.part_class == "detail" or (c.part_class == "inner"
                                                 and not c.provs[0]["rule"].split("+")[0].endswith(":see_through"))):
                p = c.provs[0]
                records["_parts"].append({"text": p["trigger"], "charSpan": p["charSpan"], "part": c.part,
                                          "partClass": c.part_class, "path": c.path, "value": c.value,
                                          "rule": p["rule"]})
                continue
            keep.append(c)
        return super()._merge(keep, uncertain_paths, records)


# _provenance·_alternatives의 경로 순서(SceneSpec 슬롯 순서에 2.2 슬롯을 form.posture 뒤에 끼움)
_PATH_ORDER = {p: k for k, p in enumerate((
    "form.type", "form.posture", "form.base", "form.baseVariant",
    "material.color", "material.brightness", "material.saturation", "material.roughness", "material.opacity",
    "material.erosion", "layout.size", "layout.distance", "layout.verticalOffset", "motion.type", "motion.speed",
    "body.part", "body.layer"))}


def _ordered_provenance(prov: dict) -> dict:
    return {k: prov[k] for k in sorted(prov, key=lambda k: (_PATH_ORDER.get(k, 99), k))}


def _num_text(v) -> str:
    """말한 값의 표기(소수 넷째 자리까지, 같은 값이면 언제나 같은 글)."""
    return repr(round(float(v), 4))


_FLOOR_TAG = re.compile(r"\+floor\(([0-9.]+)(?:;said=(-?[0-9.]+(?:[eE][-+]?[0-9]+)?))?\)$")


def floor_record(spec: dict) -> dict | None:
    """G33: 매퍼 v2가 거리 하한을 적용한 spec이면 {slot, said, drawn, floor, rule, trigger, charSpan}, 아니면 None.
    said = 참여자가 말한 값(하한 전, 매퍼 단위 0–1), drawn = 슬롯 값(하한, 미리보기에 그려지는 값).
    builder 2.0.0이 만든 spec(꼬리표 '+floor(0.1)', 말한 값 없음)은 said = None.
    배치 러너는 spec의 거리를 쓰지 않는다(시작 자리는 실험 설정, decisions.md G33)."""
    provs = (spec.get("_provenance") or {}).get("layout.distance") or []
    if not provs:
        return None
    m = _FLOOR_TAG.search(provs[0].get("rule") or "")
    if not m:
        return None
    drawn = (spec.get("layout") or {}).get("distance")
    return {"slot": "layout.distance", "said": float(m.group(2)) if m.group(2) is not None else None,
            "drawn": drawn, "floor": float(m.group(1)), "rule": provs[0]["rule"],
            "trigger": provs[0].get("trigger"), "charSpan": list(provs[0].get("charSpan") or [])}


def factory(rt) -> SceneSpecBuilderV2:
    """corpus_run·fidelity의 --mapper v2(= ifs_chatbot.scene_builder_v2:factory) 용."""
    return SceneSpecBuilderV2.from_runtime(rt)
