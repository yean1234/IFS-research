"""G77: 확정 직후 매퍼(v2)가 비운 슬롯을 면담 LLM이 참여자 원문 인용과 함께 채운다([mapping] llm_fill, experiment.toml만).

흐름: 확정 텍스트 → 매퍼 v2 spec(그대로, 바꾸지 않음) → 이 모듈이 면담 모델(Ollama, 그때 올라와 있음)을 한 번 부름(온도 0·seed 고정·
JSON 스키마 출력, 시간 한도) → 항목마다 검증기 → 통과한 값만
- 조절 항목 슬롯(색·밝기·투명도·질감·크기·움직임·형태 종류): 후보·조절 단계의 '처음 값'(덮어쓰기, selection.py → candidates.generate
  prefill). 장면 = 확정 스펙 + 덮어쓰기라 스펙 파일·해시·스키마는 그대로다. 참여자가 조절 화면에서 그대로 두거나 고친다.
- 형태 낱말(shape_noun): [맞는 게 없어요] 뒤 그림 프롬프트에서 규칙이 형태를 하나도 만들지 못했을 때(no_shape_stated)만 빈 형태 자리를
  메운다(tools/gen3d/prompts.shape_prompt llm_items). 규칙 형태가 있으면 쓰지 않는다.
부르지 않는 경우: 플래그 끔, 백엔드가 JSON 호출을 못 함(offline 등), 세션에 위기·확인 판정이 있었음(원칙 4), 채울 빈 슬롯이 없음.
실패·시간 초과·JSON 깨짐이면 결과를 버리고 지금 경로 그대로(재시도 없음). 같은 (확정 텍스트 해시, 모델 digest, 프롬프트 판·해시)는
세션 안에서 다시 부르지 않는다(cache). 위치·거리 슬롯은 대상이 아니다(G10).

검증(하나라도 실패하면 그 항목만 버림, 사유 코드를 남김):
  malformed · slot_not_allowed · slot_filled · value_not_allowed · evidence_pair_not_allowed · quote_mismatch ·
  span_not_token_aligned · quote_too_long · span_covered(매퍼가 쓴 구간) · span_excluded(매퍼가 뺀 구간·교차 감각 등 장면 값이 아니라고 판정한 낱말) ·
  negated · context_sentence(지난 일·상황 문장) · simile(비유 원천의 속성) · simile_of_predicate · position_location · position_size ·
  emotion_or_sense_word · body_word · no_noun · english_format · english_banned · english_color_size · english_non_shape ·
  non_meshable · korean_banned · multi_slot_quote(같은 구간을 두 슬롯에) · slot_duplicate · over_limit
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from pathlib import Path

from .candidates import slot_is_open, slot_value
from .paths import PROMPTS_DIR, shared
from .session_log import now_iso

LLM_FILL_VERSION = "ifs-llm-fill/0.1.0"
ORIGIN = "llm_quoted"                  # 값 출처(사전 rule·참여자 조절과 구분). selection 0.5 sources·후보 sources 값
PROMPT_DIR = PROMPTS_DIR / "llm_fill"
SHAPE_SLOT = "shape_noun"
# 세션에 이런 판정이 하나라도 있었으면 부르지 않는다(원칙 4: 위기·확인 판정 뒤에는 LLM을 더 부르지 않는 쪽으로)
FLAG_ALERTS = ("crisis", "soft_check", "clarify_soft", "risk_signal", "depth", "scene_safety_flag")
FLAG_MESSAGE_KINDS = ("crisis", "check")
_SIMILE_FORMS = ("처럼", "같이")
_NOUN_TAGS = ("NNG", "NNP")
_CONTENT_TAGS = ("NNG", "NNP", "VA", "VV", "XR", "MAG")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class FillPrompt:
    """고정 프롬프트 파일(판·status draft). 파일 바이트 해시를 기록·캐시 키에 쓴다."""

    def __init__(self, name: str = "llm_fill.v0.1.0.json"):
        p = Path(name)
        self.path = p if p.is_absolute() else PROMPT_DIR / name
        raw = self.path.read_text(encoding="utf-8")
        self.sha256 = sha256_text(raw)
        self.data = json.loads(raw)
        self.version = self.data["promptVersion"]
        self.slots: dict = self.data["slots"]
        self.shape = self.data["shapeNoun"]
        self.english_re = re.compile(self.shape["englishPattern"])
        blocked, body = set(), set()
        lex = json.loads(shared("lexicon", "layer1_lexicon.v0.json").read_text(encoding="utf-8"))
        cats = set(self.data["blockedLemmaCategories"])
        for e in lex["entries"]:
            if e.get("category") in cats:
                blocked.add(e["lemma"])
            if e.get("category") in self.data["bodyCategories"]:
                body.add(e["lemma"])
        for f in ("layer1_interview.v0.json", "vad_ko.v0.json"):
            for e in json.loads(shared("lexicon", f).read_text(encoding="utf-8")).get("entries", []):
                if f.startswith("vad") or e.get("category") == "emotion":
                    blocked.add(e["lemma"])
        blocked |= set(self.data["evaluationLemmas"])
        self.blocked_lemmas = frozenset(blocked)
        self.body_lemmas = frozenset(body)

    def info(self) -> dict:
        return {"promptId": self.data["promptId"], "promptVersion": self.version, "file": self.path.name,
                "promptSha256": self.sha256, "status": self.data["status"]}


# ── 세션 판정 ────────────────────────────────────────────────────────────────
def session_flag(session) -> str | None:
    """세션에 위기·확인 판정이 있었으면 그 사유(부르지 않음), 없으면 None."""
    for a in session.log.data.get("alerts") or []:
        if a.get("kind") in FLAG_ALERTS:
            return f"alert:{a.get('kind')}"
    for m in getattr(session, "messages", []) or []:
        if m.get("kind") in FLAG_MESSAGE_KINDS:
            return f"message:{m.get('kind')}"
    for t in session.log.data.get("turns") or []:
        if t.get("crisisKeyword"):
            return "turn:crisisKeyword"
    return None


# ── 빈 슬롯 ──────────────────────────────────────────────────────────────────
def open_slots(spec: dict, table: dict, prompt: FillPrompt, shape_open: bool) -> list[str]:
    """매퍼가 비운 슬롯 가운데 이 판이 다루는 것(조절 표에 그 항목이 있을 때만). shape_open = 규칙 그림 프롬프트가 no_shape_stated."""
    items = table["adjustItems"]["items"]
    out = []
    for name, s in prompt.slots.items():
        if name == SHAPE_SLOT:
            if shape_open:
                out.append(name)
            continue
        if s["item"] not in items:
            continue
        if name == "form":
            if not slot_is_open(spec, "form.type", table) or slot_value(spec, "form.base") is not None:
                continue
        elif any(slot_value(spec, x) is not None for x in s["specSlots"]):
            continue
        out.append(name)
    return out


def output_schema(prompt: FillPrompt, slots: list[str], max_items: int) -> dict:
    """Ollama format: 슬롯마다 값 enum을 묶은 anyOf(값이 그 슬롯의 허용 값에서만 나오게). shape_noun 값은 짧은 문자열."""
    alts = []
    for name in slots:
        s = prompt.slots[name]
        value = {"type": "string", "maxLength": 40} if s["values"] is None else {"type": "string", "enum": list(s["values"])}
        alts.append({"type": "object",
                     "properties": {"slot": {"type": "string", "enum": [name]}, "value": value,
                                    "quote": {"type": "string", "maxLength": 40},
                                    "charSpan": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                                    "evidenceType": {"type": "string", "enum": list(s["evidence"])}},
                     "required": ["slot", "value", "quote", "charSpan", "evidenceType"]})
    return {"type": "object", "properties": {"items": {"type": "array", "maxItems": max_items,
                                                        "items": {"anyOf": alts}}},
            "required": ["items"]}


# ── 매퍼 근거 ────────────────────────────────────────────────────────────────
def _span(p):
    cs = (p or {}).get("charSpan")
    return tuple(cs) if isinstance(cs, (list, tuple)) and len(cs) == 2 else None


def mapper_spans(spec: dict, prompts_mod, prompt: FillPrompt) -> dict:
    """used = 매퍼가 슬롯에 쓴 구간(_provenance·_inferred), excluded = 매퍼가 뺀 구간과 사유(G73-f와 같은 판단 + 부정·맥락·불확실 +
    장면 값이 아니라고 판정한 _unmapped: 교차 감각(무겁·차갑)·제외 범주 등. 사전 밖 명사(unlisted_noun)·사물(object)만 열어 둠)."""
    used, excluded = [], []
    for path, plist in (spec.get("_provenance") or {}).items():
        for p in plist if isinstance(plist, list) else [plist]:
            s = _span(p)
            if s:
                used.append((s, path, p.get("trigger")))
    for path, inf in (spec.get("_inferred") or {}).items():
        for p in (inf or {}).get("_provenance") or []:
            s = _span(p)
            if s:
                used.append((s, path, p.get("trigger")))
    ev = prompts_mod._mapper_evidence(spec)
    for s, reason in ev["discard"]:
        excluded.append((s, reason, None))
    for key, reason in (("_uncertain", "mapper_uncertain"), ("_needsConfirmation", "mapper_needs_confirmation")):
        for u in spec.get(key) or []:
            s = _span(u.get("_provenance") if isinstance(u, dict) else None) or _span(u if isinstance(u, dict) else None)
            if s:
                excluded.append((s, reason, (u or {}).get("lemma") if isinstance(u, dict) else None))
    opened = set(prompt.data["openUnmappedCategories"])
    for u in spec.get("_unmapped") or []:
        s = _span(u.get("_provenance"))
        if s and u.get("category") not in opened:
            excluded.append((s, f"mapper_unmapped:{u.get('category')}", u.get("lemma")))
    return {"used": used, "excluded": excluded}


def _overlap(a, b) -> bool:
    return bool(a and b) and a[0] < b[1] and b[0] < a[1]


# ── LLM 입력 ─────────────────────────────────────────────────────────────────
def build_user(prompt: FillPrompt, norm: str, doc, spec: dict, slots: list[str], spans: dict) -> str:
    eoj = []
    for a, b in doc.eojeols:
        s, e = doc.toks[a].start, doc.toks[b].end
        eoj.append(f"{s}: {norm[s:e]}")
    open_lines = []
    for name in slots:
        s = prompt.slots[name]
        if s["values"] is None:
            open_lines.append(f"- {name}({s['describe']}): 영어 명사구 1–3낱말")
        else:
            open_lines.append(f"- {name}({s['describe']}): " + ", ".join(f"{k}={v['ko']}" for k, v in s["values"].items()))
    filled = [f"- {path}: '{norm[s[0]:s[1]]}' [{s[0]}, {s[1]}]" for s, path, _ in sorted(spans["used"])]
    excl = [f"- '{norm[s[0]:s[1]]}' [{s[0]}, {s[1]}] ({r})" for s, r, _ in sorted(spans["excluded"], key=lambda x: x[0])]
    unm = [f"- '{u.get('surface')}' [{u['charSpan'][0]}, {u['charSpan'][1]}]" for u in spec.get("_unmatched") or []
           if isinstance(u.get("charSpan"), list)]
    unm += [f"- '{u.get('lemma')}' (사전 밖 명사)" for u in spec.get("_unmapped") or []
            if u.get("category") in prompt.data["openUnmappedCategories"]]
    return prompt.data["userTemplate"].format(
        text=norm, eojeols="\n".join(eoj) or "(없음)", openSlots="\n".join(open_lines) or "(없음)",
        filled="\n".join(filled) or "(없음)", excluded="\n".join(excl) or "(없음)", unmatched="\n".join(unm) or "(없음)")


# ── 검증 ─────────────────────────────────────────────────────────────────────
class _Ctx:
    def __init__(self, prompts_mod, norm: str, spec: dict, table: dict, prompt: FillPrompt, slots: list[str]):
        self.pm, self.norm, self.spec, self.table, self.prompt, self.slots = prompts_mod, norm, spec, table, prompt, slots
        self.rt = prompts_mod._shape_runtime()
        toks = self.rt.analyzer.tokens(norm)
        self.doc = self.rt.Doc(norm, toks)
        self.toks = toks
        self.context = self.rt.excluder._context_sentences(self.doc)
        self.neg_spans = [tuple(n["_provenance"]["charSpan"]) for n in spec.get("_negated") or []
                          if (n.get("_provenance") or {}).get("charSpan")]
        self.spans = mapper_spans(spec, prompts_mod, prompt)
        self.starts = {t.start for t in toks}
        self.ends = {t.end for t in toks}
        for a, b in self.doc.eojeols:
            self.ends.add(toks[b].end)


def _check_item(ctx: _Ctx, raw) -> tuple[dict, list[str]]:
    """항목 하나 → (정리한 항목, 기각 사유 목록). 사유가 비면 통과."""
    P = ctx.prompt
    if not isinstance(raw, dict) or not isinstance(raw.get("slot"), str) or not isinstance(raw.get("quote"), str) \
            or not isinstance(raw.get("charSpan"), list) or len(raw["charSpan"]) != 2 \
            or not all(isinstance(x, int) and not isinstance(x, bool) for x in raw["charSpan"]) \
            or not isinstance(raw.get("value"), str) or not isinstance(raw.get("evidenceType"), str):
        return {"raw": copy.deepcopy(raw)}, ["malformed"]
    slot, value, quote, (s, e), evt = raw["slot"], raw["value"], raw["quote"], raw["charSpan"], raw["evidenceType"]
    item = {"slot": slot, "value": value, "quote": quote, "charSpan": [s, e], "evidenceType": evt}
    why: list[str] = []
    if slot not in P.slots:
        return item, ["slot_not_allowed"]
    if slot not in ctx.slots:
        why.append("slot_filled")
    sd = P.slots[slot]
    if sd["values"] is not None and value not in sd["values"]:
        why.append("value_not_allowed")
    if evt not in sd["evidence"]:
        why.append("evidence_pair_not_allowed")
    norm = ctx.norm
    if not (0 <= s < e <= len(norm)) or norm[s:e] != quote or not quote.strip():
        why.append("quote_mismatch")
        return item, why                                          # 위치를 믿을 수 없어 아래 문맥 검사를 하지 않음
    if s not in ctx.starts or e not in ctx.ends:
        why.append("span_not_token_aligned")
    if len(quote.split()) > int(P.data["maxQuoteEojeol"]):
        why.append("quote_too_long")
    if any(_overlap((s, e), u) for u, _, _ in ctx.spans["used"]):
        why.append("span_covered")
    hit = [r for x, r, _ in ctx.spans["excluded"] if _overlap((s, e), x)]
    if hit:
        why.append("span_excluded")
        item["excludedBy"] = sorted(set(hit))
    idx = [k for k, t in enumerate(ctx.toks) if t.start < e and s < t.end]
    if not idx:
        why.append("span_not_token_aligned")
        return item, sorted(set(why), key=why.index)
    i, j = idx[0], idx[-1]
    doc, toks = ctx.doc, ctx.toks
    if ctx.pm._negated(doc, i, j, set(), ctx.neg_spans):
        why.append("negated")
    if doc.sent[i] in ctx.context:
        why.append("context_sentence")
    content = [toks[k] for k in idx if toks[k].base_tag in _CONTENT_TAGS]
    if any(t.lemma in P.blocked_lemmas for t in content):
        why.append("emotion_or_sense_word")
    nouns = [k for k in idx if toks[k].base_tag in _NOUN_TAGS]
    after = toks[j + 1] if j + 1 < len(toks) and doc.sent[j + 1] == doc.sent[j] else None
    simile_inside = any(toks[k].form in _SIMILE_FORMS or (toks[k].form == "같" and toks[k].base_tag == "VA") for k in idx)
    simile_after = after is not None and (after.form in _SIMILE_FORMS or (after.form == "같" and after.base_tag == "VA"))
    if slot != SHAPE_SLOT:
        if simile_inside or simile_after:
            why.append("simile")                                  # 비유 원천의 속성 옮기기 금지('돌처럼' → 회색)
        return item, sorted(set(why), key=why.index)
    # 형태 낱말: 중심 명사(인용 안 마지막 명사, 형식 명사는 건너뜀)
    generic = ctx.rt.generic
    head = next((k for k in reversed(nouns) if toks[k].form not in generic), None)
    if head is None:
        why.append("no_noun")
        return item, sorted(set(why), key=why.index)
    if toks[head].lemma in P.body_lemmas:
        why.append("body_word")
    pos = ctx.pm._position(ctx.rt, doc, head)
    if pos == "location":
        why.append("position_location")
    elif pos == "size":
        why.append("position_size")
    elif pos == "simile":
        # 비유 뒤에 명사가 오거나 문장이 끝나면 형상('돌덩이 같은 게', '돌덩이 같아요'), 용언이 오면 속성 비유('돌덩이처럼 무거워요')
        for k in range(head + 1, len(toks)):
            if doc.sent[k] != doc.sent[head]:
                break
            t = toks[k]
            if t.form in _SIMILE_FORMS or t.form == "같" or t.base_tag.startswith(("E", "J", "X", "S")) or t.base_tag == "VCP":
                continue
            if t.base_tag in ("NNG", "NNP", "NNB", "NP"):
                break
            if t.base_tag in ("VA", "VV", "MAG", "XR"):
                why.append("simile_of_predicate")
            break
    for k in nouns:
        kind = ctx.rt.block_kind.get(toks[k].form)
        if kind == "nonMeshable":
            why.append("non_meshable")
        elif kind in ("person", "animal"):
            why.append("korean_banned")
    sh = P.shape
    words = value.lower().split()
    if not ctx.prompt.english_re.match(value):
        why.append("english_format")
    if any(w in sh["bannedEnglish"] for w in words):
        why.append("english_banned")
    if any(w in sh["colorSizeEnglish"] for w in words):
        why.append("english_color_size")
    if any(w in sh["nonShapeEnglish"] for w in words):
        why.append("english_non_shape")
    if any(w in sh["nonMeshableEnglish"] for w in words):
        why.append("non_meshable")
    return item, sorted(set(why), key=why.index)


def item_overrides(prompt: FillPrompt, table: dict, slot: str, value: str) -> dict:
    """채택 값 → SceneParams 덮어쓰기 키:값(값 표의 단계·견본·valueOverrides 그대로)."""
    sd = prompt.slots[slot]
    v = sd["values"][value]
    it = table["adjustItems"]["items"][sd["item"]]
    if "swatch" in v:
        sw = next(x for x in it["swatches"] if x["id"] == v["swatch"])
        return {"material.color.h": sw["h"], "material.color.s": sw["s"], "material.color.l": sw["l"]}
    if "step" in v:
        if not any(abs(float(v["step"]) - x) < 1e-9 for x in it["values"]):
            raise ValueError(f"{slot}={value}: 값 표 단계 밖 {v['step']}")
        return {it["key"]: float(v["step"])}
    cat = v["category"]
    if cat not in it["values"]:
        raise ValueError(f"{slot}={value}: 값 표 밖 {cat}")
    vo = it.get("valueOverrides")
    return dict(vo[cat]) if vo is not None else {it["key"]: cat}


def validate(ctx: _Ctx, raw_items: list, max_items: int) -> tuple[list[dict], list[dict]]:
    """→ (항목별 검증 기록, 채택 항목). 실패 항목만 버리고 재시도하지 않는다."""
    recs = []
    for n, raw in enumerate(raw_items):
        item, why = _check_item(ctx, raw)
        recs.append({"i": n, **item, "ok": not why, "reasons": why})
    ok = [r for r in recs if r["ok"]]
    # 한 인용은 한 슬롯: 겹치는 구간을 다른 슬롯에 쓴 항목은 모두 버린다
    for a in ok:
        for b in ok:
            if a is not b and a["slot"] != b["slot"] and _overlap(a["charSpan"], b["charSpan"]):
                a["reasons"].append("multi_slot_quote")
    seen, adopted = set(), []
    for r in recs:
        if r.get("reasons"):
            r["reasons"] = sorted(set(r["reasons"]), key=r["reasons"].index)
        if r["ok"] and r["reasons"]:
            r["ok"] = False
        if not r["ok"]:
            continue
        if r["slot"] in seen:
            r.update(ok=False, reasons=["slot_duplicate"])
            continue
        if len(adopted) >= max_items:
            r.update(ok=False, reasons=["over_limit"])
            continue
        seen.add(r["slot"])
        a = {"slot": r["slot"], "value": r["value"], "quote": r["quote"], "charSpan": list(r["charSpan"]),
             "evidenceType": r["evidenceType"], "origin": ORIGIN}
        if r["slot"] == SHAPE_SLOT:
            a["english"] = r["value"]
        else:
            a["item"] = ctx.prompt.slots[r["slot"]]["item"]
            a["overrides"] = item_overrides(ctx.prompt, ctx.table, r["slot"], r["value"])
        adopted.append(a)
    return recs, adopted


# ── 한 번 부르기 ──────────────────────────────────────────────────────────────
def run(session, spec: dict, norm: str) -> dict:
    """확정 직후 한 번(Session._write_scene). 어떤 예외도 세션을 멈추지 않는다(기록만). 결과는 세션의 llm_fill에 둔다."""
    rt = session.rt
    cfg = rt.cfg.mapping
    prompt: FillPrompt = rt.llm_fill_prompt
    backend = rt.backend
    binfo = backend.info() if hasattr(backend, "info") else {}
    digest = binfo.get("digest")
    key = f"{sha256_text(norm)}|{digest}|{prompt.version}|{prompt.sha256}"
    cache = session.llm_fill_cache
    if key in cache:
        rec = copy.deepcopy(cache[key])
        rec["cached"] = True
        return rec
    rec = {"version": LLM_FILL_VERSION, "status": None, "skipReason": None, "error": None,
           "prompt": prompt.info(), "model": {"name": binfo.get("name"), "digest": digest, "runtime": binfo.get("runtime")},
           "options": {"temperature": prompt.data["options"]["temperature"], "seed": int(cfg.llm_fill_seed),
                       "numPredict": prompt.data["options"]["numPredict"], "think": False},
           "timeoutS": float(cfg.llm_fill_timeout_s), "maxItems": int(cfg.llm_fill_max_items),
           "cacheKey": sha256_text(key)[:16], "cached": False, "sourceTextSha256": sha256_text(norm),
           "at": now_iso(), "seconds": None, "offeredSlots": [], "rawText": None, "rawItems": None,
           "items": [], "adopted": []}

    def done(status, **kw):
        rec.update(status=status, **kw)
        cache[key] = copy.deepcopy(rec)
        return rec

    flag = session_flag(session)
    if flag:
        return done("skipped", skipReason="session_flagged", error=flag)
    if not hasattr(backend, "structured") or not getattr(rt, "backend_ok", True):
        return done("skipped", skipReason="backend_unsupported", error=getattr(backend, "name", None))
    from . import none_gen as ng                         # tools/gen3d/prompts.py(Kiwi·매퍼 판단 함수)를 같은 잠금으로
    t0 = time.monotonic()
    with ng._prompts_lock:
        pm = ng._load_prompts()
        shape = pm.shape_prompt(norm, mapper_spec=spec)
        slots = open_slots(spec, rt.candidate_table, prompt, shape.get("blockReason") == "no_shape_stated")
        rec["offeredSlots"] = slots
        if not slots:
            return done("skipped", skipReason="no_open_slot", seconds=round(time.monotonic() - t0, 2))
        ctx = _Ctx(pm, norm, spec, rt.candidate_table, prompt, slots)
        user = build_user(prompt, norm, ctx.doc, spec, slots, ctx.spans)
    rec["userSha256"] = sha256_text(user)
    schema = output_schema(prompt, slots, max(1, len(slots)))
    t1 = time.monotonic()
    try:
        res = backend.structured(prompt.data["system"], user, schema, seed=int(cfg.llm_fill_seed),
                                 timeout_s=float(cfg.llm_fill_timeout_s),
                                 temperature=float(prompt.data["options"]["temperature"]),
                                 num_predict=int(prompt.data["options"]["numPredict"]))
    except Exception as exc:  # noqa: BLE001 — 실패·시간 초과는 지금 경로 그대로
        el = time.monotonic() - t1
        timeout = el >= float(cfg.llm_fill_timeout_s) - 0.05 or "timeout" in str(exc).lower()
        return done("timeout" if timeout else "failed", error=f"{type(exc).__name__}: {exc}"[:300],
                    seconds=round(time.monotonic() - t0, 2))
    llm_s = time.monotonic() - t1
    rec["llmSeconds"] = round(llm_s, 2)
    rec["rawText"] = (res.raw or "")[:4000]
    if llm_s > float(cfg.llm_fill_timeout_s):
        return done("timeout", error=f"{llm_s:.1f}초 > {cfg.llm_fill_timeout_s}초", seconds=round(time.monotonic() - t0, 2))
    try:
        parsed = json.loads(res.raw)
        items = parsed["items"]
        if not isinstance(items, list):
            raise ValueError("items가 배열이 아님")
    except Exception as exc:  # noqa: BLE001
        return done("invalid_output", error=f"{type(exc).__name__}: {exc}"[:300], seconds=round(time.monotonic() - t0, 2))
    rec["rawItems"] = copy.deepcopy(items)
    with ng._prompts_lock:
        recs, adopted = validate(ctx, items, int(cfg.llm_fill_max_items))
    return done("ok", items=recs, adopted=adopted, seconds=round(time.monotonic() - t0, 2))


def prefill_from(rec: dict | None) -> dict:
    """세션 기록 → 조절 항목별 처음 값 {item: {overrides, quote, charSpan, slot, value}}(형태 낱말 항목 제외)."""
    out = {}
    for a in (rec or {}).get("adopted") or []:
        if a["slot"] != SHAPE_SLOT:
            out[a["item"]] = {"slot": a["slot"], "value": a["value"], "quote": a["quote"], "charSpan": list(a["charSpan"]),
                              "overrides": dict(a["overrides"])}
    return out


def shape_items_from(rec: dict | None) -> list[dict]:
    """세션 기록 → 그림 프롬프트용 형태 낱말 항목(채택된 것만, 0–1개)."""
    return [{"quote": a["quote"], "charSpan": list(a["charSpan"]), "english": a["english"]}
            for a in (rec or {}).get("adopted") or [] if a["slot"] == SHAPE_SLOT]
