"""추출 미리보기 — 확정 텍스트 → 속성 후보 (화이트박스, LLM 없음).

노션 설계(설계 노트 §6, 「인터렉션 디벨롭 리서치」)의 층 구조 중 이 데모가 하는 일:
  0층 Kiwi 형태소 분석                         ✔
  1층 사전 매칭(색·질감·크기·자세 …)            ✔  → _provenance {source, trigger, charSpan, rule}
  2층 직유 표지(~처럼 · ~같은 · ~듯한) → 원천 명사 ✔  (형태 프로토타입 선택은 원천 명사가 사전의 형태어일 때만.
                                                      FastText 유사도 선택은 아직 없음 → pending)
  3층 감성사전 V/A/D 보충                       ✘  (말하지 않은 슬롯은 비워 두고 unspecified로 표시)
  우선순위 병합: 말한 것이 추론한 것을 덮어쓴다 → 이 데모는 '말한 것'만 채운다.

출력의 sceneSpecDraft는 기존 TS IFSSceneSpec(form/material/layout/motion)과 이름을 맞춘 초안이다.
정식 스키마 정렬과 버전 올림은 렌더러 쪽 작업(docs/chatbot-design.md 참고).
"""
from __future__ import annotations

from dataclasses import dataclass

from .korean import Analyzer, normalize
from .lexicon import Hit, Lexicon

EXTRACTOR_VERSION = "0.1.0"
SIMILE_MARKERS = {"처럼": "처럼", "같": "같은", "듯": "듯한", "마냥": "마냥"}
FUNCTION_LEMMAS = {
    "있", "없", "같", "하", "되", "이", "것", "거", "좀", "그냥", "너무", "조금", "약간", "뭔가", "무언가",
    "정도", "쪽", "때", "수", "지금", "그", "이렇", "그렇", "어떻", "들", "보이", "느끼", "느껴지", "생각",
    "같이", "많이", "정말", "진짜", "아주", "되게", "엄청", "막",
}
CONTENT_TAGS = {"NNG", "NNP", "VA", "VV", "XR", "MAG"}
SINGLE_SLOTS = {"material.color", "material.brightness", "material.saturation", "material.opacity",
                "material.temperature", "physical.weight", "layout.size", "form.type", "layout.distanceCue"}
DRAFT_SLOTS = ["form.type", "form.shape", "material.color", "material.brightness", "material.saturation",
               "material.opacity", "material.texture", "material.temperature", "physical.weight",
               "layout.size", "motion", "posture", "sound", "bodyRelation", "selfReference"]


@dataclass
class Extractor:
    lexicon: Lexicon
    analyzer: Analyzer

    def run(self, text: str, body_relation: dict | None = None) -> dict:
        text = normalize(text) if "\n" not in text else "\n".join(normalize(t) for t in text.split("\n"))
        hits = self.lexicon.hits(text)
        toks = self.analyzer.tokens(text)

        attributes = []
        for h in hits:
            if h.entry.category == "dimension":
                continue
            attributes.append({
                "category": h.entry.category, "slot": h.entry.slot, "lemma": h.entry.lemma,
                "value": h.entry.value, "negated": h.negated, "change": h.change,
                "valueSource": h.entry.src, "_provenance": h.provenance(),
            })

        similes = self._similes(text, toks)
        covered = {h.token_index for h in hits}
        content_total, unmatched = 0, []
        for i, t in enumerate(toks):
            if t.base_tag not in CONTENT_TAGS or t.lemma in FUNCTION_LEMMAS:
                continue
            content_total += 1
            if i not in covered:
                unmatched.append({"lemma": t.lemma, "tag": t.tag, "surface": text[t.start:t.end], "charSpan": [t.start, t.end]})

        draft = self._scene_draft(hits, similes, body_relation)
        return {
            "extractorVersion": EXTRACTOR_VERSION,
            "lexicon": self.lexicon.info(),
            "analyzer": self.analyzer.info(),
            "inputText": text,
            "layers": {"layer0": "kiwi" if self.analyzer.available else "fallback-regex",
                       "layer1": "lexicon", "layer2": "simile-marker (prototype: lexicon only)", "layer3": "not-implemented"},
            "attributes": attributes,
            "similes": similes,
            "unmatched": unmatched,
            "lostInformation": {
                "contentTokens": content_total,
                "unmatchedTokens": len(unmatched),
                "rate": round(len(unmatched) / content_total, 3) if content_total else None,
                "note": "소실 정보율 근사치: 사전에 걸리지 않은 내용어 비율. 사람 주석(F1·kappa)과 함께 봐야 한다.",
            },
            "sceneSpecDraft": draft,
        }

    # ── 2층: 직유 표지 ──────────────────────────────────────────────────────────
    def _similes(self, text: str, toks) -> list[dict]:
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
            # 원천 명사: 표지 바로 앞의 명사(조사·서술격 조사 건너뜀). '것 같아요'(NNB)는 짐작 표현이라 제외.
            j = i - 1
            while j >= 0 and toks[j].base_tag in ("JKS", "JKB", "JX", "VCP", "ETM", "JKO"):
                j -= 1
            if j < 0 or toks[j].base_tag not in ("NNG", "NNP"):
                continue
            src = toks[j]
            # 앞 명사가 이어지면 합성어로 본다(젖은 종이 → '종이', 물 덩어리 → '물 덩어리')
            k = j
            while k - 1 >= 0 and toks[k - 1].base_tag in ("NNG", "NNP") and toks[k - 1].end >= toks[k].start - 1:
                k -= 1
            source = text[toks[k].start:src.end]
            proto = None
            for e in self.lexicon._by_form.get(src.form, []):
                if e.category == "form":
                    proto = e.value.get("prototype")
            out.append({
                "marker": marker, "sourceNoun": source, "charSpan": [toks[k].start, t.end],
                "formPrototype": proto,
                "method": "lexicon" if proto else "pending (FastText 유사도로 blob·mist·shell·fragments 중 선택 예정)",
                "_provenance": {"source": "simile_marker", "trigger": text[toks[k].start:t.end],
                                "charSpan": [toks[k].start, t.end], "rule": f"simile.{marker}"},
            })
        return out

    # ── IFSSceneSpec 초안 ───────────────────────────────────────────────────────
    def _scene_draft(self, hits: list[Hit], similes: list[dict], body_relation: dict | None) -> dict:
        slots: dict[str, dict] = {}
        alternatives: dict[str, list] = {}
        negated: list[dict] = []
        unresolved: list[dict] = []

        def put(slot: str, value, prov: dict, extra: dict | None = None):
            item = {"value": value, "_provenance": prov, **(extra or {})}
            if slot in SINGLE_SLOTS:
                if slot in slots:
                    alternatives.setdefault(slot, []).append(item)
                else:
                    slots[slot] = item
            else:
                slots.setdefault(slot, {"values": []})["values"].append(item)

        for h in hits:
            e, prov = h.entry, h.provenance()
            if e.category in ("dimension", "emotion", "sensation", "object", "body_part", "body_layer", "relation"):
                continue
            if h.negated:
                if e.category == "movement" and e.lemma in ("움직임", "움직이"):
                    put("motion", {"motion": "still"}, {**prov, "rule": prov["rule"] + "+negation"})
                else:
                    negated.append({"slot": e.slot, "lemma": e.lemma, "_provenance": prov})
                continue
            if e.category == "color":
                v = e.value
                put("material.color", {"name": v["name"], "hue": v["hsl"][0], "saturation": v["hsl"][1],
                                        "lightness": v["hsl"][2]}, prov, {"valueSource": e.src})
            elif e.category == "size":
                put("layout.size", {k: v for k, v in e.value.items()} | ({"change": h.change} if h.change else {}), prov,
                    {"valueSource": e.src})
            elif e.category == "posture":
                put("posture", e.value, prov, {"status": "unresolved", "note": "IFSSceneSpec에 자세 슬롯 없음"})
                unresolved.append({"slot": "posture", "lemma": e.lemma, "reason": "no_slot"})
            elif e.category == "self_reference":
                put("selfReference", {"refersToSelf": True, "word": h.trigger}, prov,
                    {"status": "unresolved", "note": "IFS blending 단서. 인칭 슬롯 없음"})
                unresolved.append({"slot": "selfReference", "lemma": e.lemma, "reason": "no_slot"})
            elif e.slot:
                put(e.slot, e.value, prov, {"valueSource": e.src})

        for s in similes:
            if s["formPrototype"] and "form.type" not in slots:
                put("form.type", s["formPrototype"], s["_provenance"])
            elif not s["formPrototype"]:
                unresolved.append({"slot": "form.type", "sourceNoun": s["sourceNoun"], "reason": "prototype_pending"})

        if body_relation and body_relation.get("status") != "unspecified":
            slots["bodyRelation"] = body_relation

        return {
            "schema": "IFSSceneSpec-draft/0.1 (기존 TS IFSSceneSpec 필드명과 정렬 필요)",
            "slots": slots,
            "alternatives": alternatives,
            "negated": negated,
            "unresolved": unresolved,
            "unspecified": [s for s in DRAFT_SLOTS if s not in slots],
            "note": "참여자가 말한 것만 채웠다. 빈 슬롯은 3층(V/A/D)·설문 슬라이더(안전망)·VR 보정이 채울 몫이다.",
        }


def parse_body_relation(text: str, lexicon: Lexicon, no_more: bool) -> dict:
    """Find 위치 질문의 답 → bodyRelation. 감정 이름에서 위치를 추론하지 않는다(B08)."""
    text = normalize(text)
    if no_more:
        return {"status": "unspecified", "text": text, "note": "참여자가 위치를 특정하지 않음 — 압박하지 않고 넘어감"}
    hits = lexicon.hits(text)
    parts = [h for h in hits if h.entry.category == "body_part"]
    layers = [h for h in hits if h.entry.category == "body_layer"]
    layer = None
    if layers:
        layer = layers[0].entry.value.get("layer")
    else:  # '표면이요', '주변이요' 처럼 사전 형태가 아닌 답
        for key, val in (("표면", "surface"), ("겉", "surface"), ("주변", "around"), ("밖", "around"), ("안", "inner"), ("속", "inner")):
            if key in text:
                layer = val
                break
    rel = {
        "status": "stated" if (parts or layer) else "unparsed",
        "text": text,
        "part": parts[0].entry.value.get("part") if parts else None,
        "layer": layer,
        "_provenance": [h.provenance() for h in (parts[:1] + layers[:1])] or [{"source": "participant_answer", "trigger": text}],
    }
    if rel["layer"] and rel["layer"].startswith("surface"):
        rel["ifsLocation"] = "on"
    elif rel["layer"] and rel["layer"].startswith("around"):
        rel["ifsLocation"] = "around"
    elif rel["layer"] == "inner":
        rel["ifsLocation"] = "in"
    else:
        rel["ifsLocation"] = None
    return rel


def find_modality(text: str, lexicon: Lexicon) -> dict:
    """Find 첫 반응의 경험 양식(IFS: part는 생각·감정·감각·이미지·소리로 경험됨). 연구자용 휴리스틱 표지.
    참여자에게 말하지 않는다."""
    hits = lexicon.hits(text)
    cats = {h.entry.category for h in hits}
    dims = {h.entry.lemma for h in hits if h.entry.category == "dimension"}
    labels = []
    if cats & {"sensation", "body_part", "temperature", "weight"} or dims & {"감각"}:
        labels.append("body_sensation")
    if "emotion" in cats or dims & {"감정", "기분"}:
        labels.append("emotion")
    if cats & {"color", "brightness", "form", "shape", "object", "size", "posture", "texture", "opacity"} \
            or dims & {"모습", "형태", "형상", "색", "색깔"} or "이미지" in text or "보여" in text:
        labels.append("image_or_scene")
    if "sound" in cats:
        labels.append("sound_or_voice")
    if "생각" in text or "라는 말" in text or "문장" in text:
        labels.append("thought_or_sentence")
    return {"labels": labels or ["unknown_or_other"], "categories": sorted(cats),
            "method": "heuristic: 1층 사전 범주", "note": "2D 설문의 find.initial_response 6범주와 같은 이름. 참여자에게 보이지 않는다."}
