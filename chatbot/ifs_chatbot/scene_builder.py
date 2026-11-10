"""확정 텍스트 → SceneSpec v2 (화이트박스 3층. 학습·LLM 없음).

  0층  Kiwi 형태소 분석 + 품사. 활용형은 원형으로(무거워요 → 무겁)              korean.Analyzer
  1층  명시적 속성 사전(색채어·크기어·질감어·자세어·신체부위어 …)              layer1_lexicon + scene_params.layer1
  2층  직유 표지(~처럼 · ~같은 · ~듯한 · ~마냥) → 원천 명사 → 형태 프로토타입    scene_params.layer2
       직유 구 안의 1층 근거('젖은 종이처럼'의 '젖은')는 비유 대상의 속성이라 2층으로 낮춘다.
  3층  감정어 V/A/D 평균 → 1·2층 뒤에도 비어 있는 슬롯에 '제안'만               vad_ko + scene_params.layer3
       값 자리에는 넣지 않고 _inferred에 둔다(원칙: 말하지 않은 속성은 null).

우선순위 1층 > 2층 > 3층. 같은 층에서는 먼저 말한 것이 값, 나머지는 _alternatives.
부정('무겁진 않아요')은 값에 넣지 않고 _negated. 사전에 없는 내용어는 _unmatched,
사전에는 있지만 v2에 옮길 곳이 없는 말은 _unmapped.

같은 확정 텍스트(+ 같은 meta 인자)는 언제나 같은 dict, 같은 파일 바이트가 된다(시각·난수 없음).
형식: shared/schemas/scene-spec.v2.json, 설명: docs/scene-spec-mapping.md
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .extract import CONTENT_TAGS, FUNCTION_LEMMAS
from .korean import Analyzer, Token, normalize
from .lexicon import Hit, Lexicon
from .paths import shared
from .scene_spec import SLOT_PATHS, SPEC_VERSION, text_hash

BUILDER_VERSION = "0.1.0"
BUILDER_ID = f"scene-spec-builder/{BUILDER_VERSION}"
SIMILE_SKIP_TAGS = ("JKS", "JKB", "JX", "VCP", "ETM", "JKO")   # extract.py와 같은 규칙
_ORDER = {p: i for i, p in enumerate(SLOT_PATHS)}


def normalize_confirmed(text: str) -> str:
    """세션 로그 confirmedText와 같은 정규화: 줄마다 normalize, 줄바꿈은 유지."""
    text = text or ""
    return normalize(text) if "\n" not in text else "\n".join(normalize(t) for t in text.split("\n"))


@dataclass(frozen=True)
class _Cand:
    path: str
    value: object
    layer: int
    start: int
    prov: dict


class SceneSpecBuilder:
    def __init__(self, lexicon: Lexicon, analyzer: Analyzer,
                 params_path: str | Path | None = None, vad_path: str | Path | None = None):
        self.lexicon, self.analyzer = lexicon, analyzer
        self.params = json.loads(Path(params_path or shared("lexicon", "scene_params.v0.json")).read_text(encoding="utf-8"))
        vad = json.loads(Path(vad_path or shared("lexicon", "vad_ko.v0.json")).read_text(encoding="utf-8"))
        self.vad_info = f"{vad['lexiconId']}@{vad['lexiconVersion']}"
        self.vad = {e["lemma"]: e for e in vad["entries"]}
        self.layer1: dict[str, list[dict]] = self.params["layer1"]
        self.prototypes: dict[str, str] = self.params["layer2"]["prototypes"]
        self.with_modifier: bool = self.params["layer2"].get("vehicleIncludesModifier", True)
        self.still_lemmas = set(self.params["negation"]["stillWhenNegated"])
        self.l3_targets: list[dict] = self.params["layer3"]["targets"]

    def info(self) -> dict:
        return {"builder": BUILDER_ID, "specVersion": SPEC_VERSION, "lexicons": self._lexicons()}

    def _lexicons(self) -> dict:
        return {"layer1": f"{self.lexicon.lexicon_id}@{self.lexicon.version}",
                "sceneParams": f"{self.params['lexiconId']}@{self.params['lexiconVersion']}",
                "vad": self.vad_info}

    # ── 진입점 ────────────────────────────────────────────────────────────────
    def build(self, text: str, *, session_id: str | None = None, participant_id: str | None = None,
              condition: str | None = None) -> dict:
        text = normalize_confirmed(text)
        toks = self.analyzer.tokens(text)                    # 0층
        hits = self.lexicon.hits(text)                       # 1층 사전 매칭
        similes = self._similes(text, toks)                  # 2층 직유 구

        def line_of(pos: int) -> int:
            return text.count("\n", 0, pos)

        body_lines = {line_of(h.char_span[0]) for h in hits if h.entry.category == "body_part" and not h.negated}
        cands: list[_Cand] = []
        unmapped: list[dict] = []
        negated: list[dict] = []

        for h in hits:
            e = h.entry
            if e.category == "dimension":           # 차원어('색깔', '크기')는 속성 값이 아니다
                continue
            sim = self._vehicle_of(h, similes)
            layer = 2 if sim else 1
            if h.negated:
                if e.category == "movement" and e.lemma in self.still_lemmas:
                    cands.append(_Cand("motion.type", "still", layer, h.char_span[0],
                                       self._prov(h, sim, "motion.type", "still(negated)")))
                else:
                    negated.append({"lemma": e.lemma, "category": e.category, "_provenance": self._prov(h, sim)})
                continue
            if sim and e.category == "object" and h.token_index == sim["srcIndex"]:
                continue                                 # 직유 원천 명사 → 아래 2층에서
            targets = self.layer1.get(e.category)
            if not targets:
                unmapped.append(self._unmapped(h, "no_scene_param", self._prov(h, sim)))
                continue
            produced, reason = 0, "no_value_mapping"
            for t in targets:
                if t.get("requires") == "bodyPartSameLine" and line_of(h.char_span[0]) not in body_lines:
                    reason = "no_body_part_context"
                    continue
                mapped = self._map(t, e.value)
                if mapped is None:
                    continue
                value, key = mapped
                cands.append(_Cand(t["path"], value, layer, h.char_span[0], self._prov(h, sim, t["path"], key)))
                produced += 1
            if not produced:
                unmapped.append(self._unmapped(h, reason, self._prov(h, sim)))

        proto_tokens: set[int] = set()
        for s in similes:                                # 2층: 원천 명사 → 형태 프로토타입
            src_hits = [h for h in hits if h.token_index == s["srcIndex"]]
            if any(h.entry.category == "form" for h in src_hits):
                continue                                 # '덩어리 같아요': 1층 형태어가 2층으로 낮춰져 이미 들어감
            proto = self.prototypes.get(s["sourceNoun"]) or self.prototypes.get(s["srcForm"])
            prov = {"source": "simile_marker", "trigger": s["trigger"], "charSpan": list(s["span"])}
            if proto:
                cands.append(_Cand("form.type", proto, 2, s["span"][0],
                                   {**prov, "rule": f"simile.{s['marker']}>prototype.{s['srcForm']}>form.type:{proto}"}))
                proto_tokens.add(s["srcIndex"])
                continue
            for h in src_hits:
                if h.entry.category == "object":
                    unmapped.append(self._unmapped(h, "simile_prototype_pending",
                                                   {**prov, "rule": f"simile.{s['marker']}>{h.entry.rule}"}))

        values, provenance, alternatives = self._merge(cands)
        inferred = self._layer3(hits, values)
        unmatched = self._unmatched(text, toks, hits, proto_tokens)

        def slot(path: str):
            return values.get(path)

        groups: dict[str, dict] = {}
        for path in SLOT_PATHS:
            g, k = path.split(".")
            groups.setdefault(g, {})[k] = slot(path)
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
            },
            **groups,
            "_provenance": provenance,
            "_unmatched": unmatched,
            "_unmapped": sorted(unmapped, key=lambda u: (u["_provenance"]["charSpan"][0], u["lemma"])),
            "_negated": sorted(negated, key=lambda n: (n["_provenance"]["charSpan"][0], n["lemma"])),
            "_alternatives": alternatives,
            "_inferred": inferred,
        }

    # ── 1층 대응 ─────────────────────────────────────────────────────────────
    @staticmethod
    def _map(target: dict, value: dict):
        """사전 항목 값 → (0–1 값, 대응 키). 표에 없으면 None(값을 만들지 않는다)."""
        key = value.get(target["key"])
        if key is None:
            return None
        transform = target.get("transform")
        if transform == "hsl":
            h, s, l = key
            return {"h": round(h / 360, 3), "s": round(float(s), 3), "l": round(float(l), 3)}, "hsl"
        if transform == "logScale":
            return round(min(1.0, max(0.0, 0.5 + math.log2(key) / 4)), 3), f"logScale({key})"
        if transform == "enum":
            return key, key
        v = target.get("values", {}).get(key)
        return (v, key) if v is not None else None

    @staticmethod
    def _prov(h: Hit, sim: dict | None, path: str | None = None, key: str | None = None) -> dict:
        rule = h.entry.rule if path is None else f"{h.entry.rule}>{path}:{key}"
        if sim:
            return {"source": "simile_marker", "trigger": h.trigger, "charSpan": list(h.char_span),
                    "rule": f"simile.{sim['marker']}>{rule}"}
        return {"source": "explicit_lexicon", "trigger": h.trigger, "charSpan": list(h.char_span), "rule": rule}

    @staticmethod
    def _unmapped(h: Hit, reason: str, prov: dict) -> dict:
        return {"lemma": h.entry.lemma, "category": h.entry.category, "value": dict(h.entry.value),
                "reason": reason, "_provenance": prov}

    # ── 2층: 직유 구 ─────────────────────────────────────────────────────────
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
            if j < 0 or toks[j].base_tag not in ("NNG", "NNP"):
                continue      # '것 같아요'(NNB)는 짐작 표현이라 직유가 아니다
            k = j
            while k - 1 >= 0 and toks[k - 1].base_tag in ("NNG", "NNP") and toks[k - 1].end >= toks[k].start - 1:
                k -= 1        # 이어진 명사는 합성어로(물 덩어리)
            vstart = toks[k].start
            if self.with_modifier and k - 1 >= 0 and toks[k - 1].base_tag == "ETM":
                vstart = self._eojeol_start(text, toks[k - 1].start)      # 관형형 어절('젖은')
                while True:                                               # 그 앞의 부사 어절('축 처진')
                    if vstart < 2 or text[vstart - 1] != " ":
                        break
                    ps = self._eojeol_start(text, vstart - 1)
                    eoj = [x for x in toks if x.start >= ps and x.end <= vstart - 1]
                    if not eoj or any(x.base_tag != "MAG" for x in eoj):
                        break
                    vstart = ps
            out.append({"marker": marker, "srcIndex": j, "srcForm": toks[j].form,
                        "sourceNoun": text[toks[k].start:toks[j].end],
                        "span": (toks[k].start, t.end), "trigger": text[toks[k].start:t.end],
                        "vehicle": (vstart, t.end)})
        return out

    @staticmethod
    def _eojeol_start(text: str, pos: int) -> int:
        return max(text.rfind(" ", 0, pos), text.rfind("\n", 0, pos)) + 1

    @staticmethod
    def _vehicle_of(h: Hit, similes: list[dict]) -> dict | None:
        s0, s1 = h.char_span
        for s in similes:
            v0, v1 = s["vehicle"]
            if v0 <= s0 and s1 <= v1:
                return s
        return None

    # ── 병합: 1층 > 2층, 같은 층에서는 먼저 말한 것 ─────────────────────────
    @staticmethod
    def _merge(cands: list[_Cand]):
        by_path: dict[str, list[_Cand]] = defaultdict(list)
        for c in cands:
            by_path[c.path].append(c)
        values, provenance, alternatives = {}, {}, []
        for path in SLOT_PATHS:
            cs = sorted(by_path.get(path, []), key=lambda c: (c.layer, c.start))
            if not cs:
                continue
            win = cs[0]
            values[path], provenance[path] = win.value, [win.prov]
            for c in cs[1:]:
                if c.layer == win.layer and c.value == win.value:
                    provenance[path].append(c.prov)          # 같은 값을 다시 말함 → 근거만 추가
                else:
                    alternatives.append({"path": path, "value": c.value,
                                         "reason": "lower_layer" if c.layer > win.layer else "later_mention",
                                         "_provenance": [c.prov]})
        return values, provenance, alternatives

    # ── 3층: V/A/D 제안(값 자리 아님) ────────────────────────────────────────
    def _layer3(self, hits: list[Hit], values: dict) -> dict:
        emo = [h for h in hits if h.entry.category == "emotion" and not h.negated and h.entry.lemma in self.vad]
        out: dict[str, dict] = {}
        if not emo:
            return out
        for t in sorted(self.l3_targets, key=lambda t: _ORDER[t["path"]]):
            if t["path"] in values:
                continue
            nums = [self.vad[h.entry.lemma][t["dim"]] for h in emo]
            out[t["path"]] = {
                "value": round(sum(nums) / len(nums), 3),
                "_provenance": [{"source": "vad_lexicon", "trigger": h.trigger, "charSpan": list(h.char_span),
                                 "rule": f"vadLexicon.{h.entry.lemma}>{t['path']}:{t['name']}"} for h in emo],
            }
        return out

    # ── 사전에 없는 말 ───────────────────────────────────────────────────────
    @staticmethod
    def _unmatched(text: str, toks: list[Token], hits: list[Hit], extra_covered: set[int]) -> list[dict]:
        covered = {h.token_index for h in hits} | extra_covered
        out = []
        for i, t in enumerate(toks):
            if t.base_tag not in CONTENT_TAGS or t.lemma in FUNCTION_LEMMAS or i in covered:
                continue
            # 부정 접두사로 합친 항목(불+투명 → 불투명)의 뒷부분
            if any(h.char_span[0] <= t.start and t.end <= h.char_span[1] and t.form in h.entry.lemma for h in hits):
                continue
            out.append({"lemma": t.lemma, "tag": t.tag, "surface": text[t.start:t.end], "charSpan": [t.start, t.end]})
        return out


def dumps(spec: dict) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2) + "\n"


def write_spec(spec: dict, path: str | Path) -> Path:
    """원자적 저장(중간에 꺼져도 반쯤 쓴 파일이 남지 않게)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(dumps(spec), encoding="utf-8")
    os.replace(tmp, path)
    return path
