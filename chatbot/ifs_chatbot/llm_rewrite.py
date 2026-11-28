"""G85: [맞는 게 없어요] 뒤 규칙 사전과 G82(형태 낱말 하나)가 모두 중심 형태를 얻지 못했을 때, 면담 LLM이 확정 텍스트에서 그림
프롬프트의 재료(대상 명사구 하나 + 모양 꾸밈 요소, 요소마다 원문 근거 또는 basis none)를 구조화해 낸다([gen3d] on_none_llm_rewrite,
기본 끔). AGENTS.md 원칙 1의 네 번째 예외·원칙 2 변경(2026-11-28 연구 책임자 결정).

순서: 규칙 사전 → G82 → G85. 앞 단계가 형태를 얻으면 뒤를 부르지 않는다.
흐름: 확정 텍스트(정규화한 그대로 — 면담자 질문·매퍼 슬롯 값은 넣지 않음) → 규칙 그림 프롬프트(rule_route: 중심 명사 없음·막을 사유 없음)
  → 면담 모델 한 번(온도 0·seed 고정·JSON 스키마·시간 한도) → {"item": null | {subject, details}}
  → 검증기: 대상 = G82 검증기 그대로(llm_shape.validate — G77 형태 낱말 검증·단계 줄·색 낱말·추상 명사) + G85 영어 규칙
    (prompts.rewrite_english_reasons) + WordNet 상위어 검사(wordnet_check) + 규칙이 문맥으로 뺀 구간과 겹치면 기각(rule_context_dropped).
    근거 있는 꾸밈 = 인용·토큰 경계·부정·회상·지난 일·남의 말·가정·두 문장·감정·감각·색·몸 낱말·한국어 금지 범주·단계 줄·규칙 문맥
    + 모양 낱말 허용 집합. 근거 없는 꾸밈(added) = 닫힌 목록(shape_added_adjectives) 안에서 최대 maxAdded개(초과분은 기각).
  → 결과(outcome): adopted(대상 근거 검증 통과 → 규칙이 조립, 출처 llm_rewrite) | no_subject(대상 근거 없음·기각·LLM null → 덧붙임 포함
    모두 버림 → 규칙이 형태 낱말을 하나도 못 잡았으면 고정 중립 형태 system_default) | forbidden(금지 범주 — 사람·동물·몸·안개·불꽃을
    말해서 막힘 → 중립 형태도 만들지 않음) | failed·timeout·invalid_output(지금 경로 그대로, 재시도 없음).
부르지 않는 경우: 위기·확인 판정(llm_fill.session_flag — 캐시 조회보다 먼저), G82가 채택함, G82가 금지 범주로 기각함, 규칙이 형태를
잡음·막음, 백엔드가 JSON 호출을 못 함. 같은 캐시 키는 세션 안에서 다시 부르지 않는다.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

from . import llm_fill as lf
from . import llm_shape as ls
from . import wordnet_check as wnc
from .paths import PROMPTS_DIR, shared
from .session_log import now_iso

LLM_REWRITE_VERSION = "ifs-llm-rewrite/0.1.0"
VALIDATOR_RULES = "ifs-llm-rewrite-validator/0.3.0"
# 0.3.0(3차 판정 2): 근거 꾸밈 구간에 모양 용언·어근이 있고 그것이 대상 명사를 꾸미거나 대상의 서술어일 때만(detail_no_predicate·
#   detail_other_subject·detail_not_on_subject). 대상이 기각되면 꾸밈도 볼 것 없이 버려진다
# 0.2.0(G85 판정 뒤, 2026-11-29): 근거 있는 꾸밈의 인용 구간이 비유 구문(처럼·같이·같은·마냥)이면 기각(simile_detail —
#   '팽이처럼' → conical처럼 사물에서 짐작한 모양). 몸 낱말 돌려 말하기는 규칙 그림 프롬프트 0.6.0(body_part_attachment)이 먼저 막는다
ORIGIN = "llm_rewrite"                     # 대상·근거 있는 꾸밈 토큰 출처(prompts.LLM_REWRITE와 같은 값)
ORIGIN_DEFAULT = "system_default"          # 고정 중립 형태(prompts.SYSTEM_DEFAULT와 같은 값)
PROMPT_DIR = PROMPTS_DIR / "llm_rewrite"
DEFAULT_PROMPT = "llm_rewrite.v0.1.0.json"
RECORD_VERSION = "ifs-llm-rewrite-record/0.1.0"
# 금지 범주(사람·얼굴·몸·동물·안개·불꽃류)로 막혔다는 뜻의 사유. 이 사유가 하나라도 있으면 중립 형태로도 가지 않는다(지금처럼 생성하지 않음)
FORBIDDEN_REASONS = frozenset({"korean_banned", "non_meshable", "body_word", "english_banned", "wordnet_forbidden",
                               "body_part_attachment"})
# 규칙 그림 프롬프트가 문맥으로 뺀 낱말(dropped reason). G85도 그 구간을 대상·꾸밈의 근거로 받지 않는다(같은 문맥 규칙)
RULE_CONTEXT_DROPS = frozenset({"negated", "context_sentence", "past_or_former", "reported_speech", "hypothetical",
                                "simile_of_predicate", "non_shape_stage_line", "mapper_negated", "mapper_context",
                                "mapper_action_simile", "mapper_location", "location", "size"})
ROUTES = ("rule", "llm_word", "llm_rewrite", "system_default", "none")
DETAIL_OPEN_EXCLUDED = frozenset({"mapper_unmapped:shape"})   # 꾸밈 근거로 열어 두는 매퍼 제외 사유(생성기 재검증도 같은 값)
PRIME_INPUT = "."                                      # 예열 요청의 고정 입력(llm.OllamaBackend.warmup_body와 같음)
SIMILE_FORMS = frozenset({"처럼", "같이", "마냥"})        # + 형용사 '같'(같은·같아요)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


_canon = ls._canon


def config_problems(cfg) -> list[str]:
    """[gen3d] on_none_llm_rewrite를 켰을 때 함께 있어야 하는 설정(시작 점검). 비면 문제 없음."""
    g = cfg.gen3d
    out = []
    if not g.on_none_llm_shape:
        out.append("[gen3d] on_none_llm_shape가 꺼져 있음(G85는 규칙 → G82 → G85 순서의 마지막 단계)")
    out += [p for p in ls.config_problems(cfg) if "on_none_llm_shape_timeout_s" not in p]
    if float(g.on_none_llm_rewrite_timeout_s) <= 0:
        out.append("[gen3d] on_none_llm_rewrite_timeout_s가 0 이하")
    return out


class RewritePrompt:
    """고정 프롬프트 파일(판·status draft)과 검증기가 쓰는 목록·사전의 해시."""

    def __init__(self, name: str = DEFAULT_PROMPT):
        p = Path(name)
        self.path = p if p.is_absolute() else PROMPT_DIR / name
        raw = self.path.read_text(encoding="utf-8")
        self.sha256 = sha256_text(raw)
        self.data = json.loads(raw)
        self.version = self.data["promptVersion"]
        self.fence = self.data["dataFence"]
        self.fill = lf.FillPrompt(self.data["validatorConfig"])
        mb = shared("lexicon", self.data["englishModifierLexicon"]).read_text(encoding="utf-8")
        self.modifier_block = {"file": self.data["englishModifierLexicon"], "sha256": sha256_text(mb),
                               "version": json.loads(mb)["version"]}
        self.korean_lexicons = {f: sha256_text(shared("lexicon", f).read_text(encoding="utf-8")) for f in ls.KOREAN_LEXICONS}
        rule = self.data.get("lineStageRule") or {}
        self.allowed_stages = tuple(rule.get("allowedStages") or ())
        added = json.loads(shared("lexicon", "shape_added_adjectives.v0.json").read_text(encoding="utf-8"))
        self.added_words = sorted(added["words"])
        self.max_added = int(added["maxAdded"])
        self.system = self.data["system"].replace("{addedWords}", ", ".join(self.added_words))

    def info(self, pm=None) -> dict:
        out = {"promptId": self.data["promptId"], "promptVersion": self.version, "file": self.path.name,
               "promptSha256": self.sha256, "systemSha256": sha256_text(self.system), "status": self.data["status"],
               "validatorConfig": {"file": self.fill.path.name, "sha256": self.fill.sha256, "version": self.fill.version},
               "englishBlock": dict(self.fill.english_block), "englishModifierBlock": dict(self.modifier_block),
               "koreanLexicons": dict(self.korean_lexicons), "allowedStages": list(self.allowed_stages),
               "maxAdded": self.max_added}
        if pm is not None:
            L = pm.rewrite_lists()
            out.update(addedList=dict(L.added), rewriteBlock=dict(L.block), neutralForm=dict(L.neutral))
        return out


def output_schema(prompt: RewritePrompt) -> dict:
    o = prompt.data["output"]
    span = {"type": "array", "items": {"type": "integer"}, "minItems": 0, "maxItems": 2}
    subject = {"type": "object",
               "properties": {"en": {"type": "string", "maxLength": int(o["maxEnglishLength"])},
                              "quote": {"type": "string", "maxLength": int(o["maxQuoteLength"])},
                              "charSpan": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}},
               "required": ["en", "quote", "charSpan"]}
    detail = {"type": "object",
              "properties": {"en": {"type": "string", "maxLength": 20}, "basis": {"enum": ["quote", "none"]},
                             "quote": {"type": "string", "maxLength": int(o["maxQuoteLength"])}, "charSpan": span},
              "required": ["en", "basis", "quote", "charSpan"]}
    item = {"type": "object", "properties": {"subject": subject,
                                             "details": {"type": "array", "items": detail, "maxItems": int(o["maxDetails"])}},
            "required": ["subject", "details"]}
    return {"type": "object", "properties": {"item": {"anyOf": [{"type": "null"}, item]}}, "required": ["item"]}


# ── LLM 입력 ─────────────────────────────────────────────────────────────────
def build_user(prompt: RewritePrompt, norm: str, doc, spans: dict, rule_mods: list[dict]) -> str | None:
    eoj = []
    for a, b in doc.eojeols:
        s, e = doc.toks[a].start, doc.toks[b].end
        eoj.append(f"{s}: {norm[s:e]}")
    filled = [f"- '{norm[s[0]:s[1]]}' [{s[0]}, {s[1]}]" for s, _, _ in sorted(spans["used"])]
    excl = [f"- '{norm[s[0]:s[1]]}' [{s[0]}, {s[1]}] ({r})" for s, r, _ in sorted(spans["excluded"], key=lambda x: x[0])]
    mods = [f"- '{m['ko']}' [{m['charSpan'][0]}, {m['charSpan'][1]}]" for m in rule_mods]
    data = {"text": norm, "eojeols": "\n".join(eoj) or "(없음)", "filled": "\n".join(filled) or "(없음)",
            "excluded": "\n".join(excl) or "(없음)", "ruleMods": "\n".join(mods) or "(없음)"}
    fence = lf.data_fence(prompt, [*data.values(), prompt.data["userTemplate"], prompt.system])
    if fence is None:
        return None
    _, fo, fc = fence
    return prompt.data["userTemplate"].format(fenceOpen=fo, fenceClose=fc, **data)


# ── 검증 ─────────────────────────────────────────────────────────────────────
def _overlaps(a, b) -> bool:
    return bool(a and b) and a[0] < b[1] and b[0] < a[1]


def _rule_context_hit(span, rule_dropped: list[dict]) -> list[str]:
    return sorted({d["reason"] for d in rule_dropped if d.get("reason") in RULE_CONTEXT_DROPS
                   and _overlaps(span, d.get("charSpan"))})


def _check_detail(ctx, d: dict, stages, allowed, rule_dropped, subject_span=None) -> tuple[dict, list[str]]:
    """근거 있는 꾸밈 하나(basis quote) → (정리한 항목, 기각 사유)."""
    P = ctx.prompt
    span, repaired = ls.repair_span(ctx.norm, d.get("quote"), d.get("charSpan"))
    item = {"en": d.get("en"), "basis": "quote", "quote": d.get("quote"), "charSpan": span, "origin": "grounded"}
    if repaired:
        item["spanRepaired"] = {"llmCharSpan": copy.deepcopy(d.get("charSpan")), "to": list(span)}
    why: list[str] = []
    q = d.get("quote")
    ok_span = isinstance(span, list) and len(span) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in span)
    if not isinstance(q, str) or not q.strip() or not ok_span or not (0 <= span[0] < span[1] <= len(ctx.norm)) \
            or ctx.norm[span[0]:span[1]] != q:
        return item, ["quote_mismatch"]
    s, e = span
    if s not in ctx.starts or e not in ctx.ends:
        why.append("span_not_token_aligned")
    if len(q.split()) > 2:
        why.append("quote_too_long")
    # 매퍼가 모양어를 슬롯 값으로 옮기지 않은 것(_unmapped 범주 shape)은 꾸밈의 근거로 받는다(모양 낱말이라는 뜻). 그 밖의 뺀 구간은 막음
    hit = [r for x, r, _ in ctx.spans["excluded"] if lf._overlap((s, e), x) and r not in DETAIL_OPEN_EXCLUDED]
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
    why.extend(lf.frame_reasons(ctx, idx))
    if len(lf._quote_sentences(ctx, idx)) > 1:
        why.append("cross_sentence")
    content = [toks[k] for k in idx if toks[k].base_tag in lf._CONTENT_TAGS]
    if any(t.lemma in P.blocked_lemmas for t in content):
        why.append("emotion_or_sense_word")
    if lf.has_attribute_word(ctx, "color", idx, j):
        why.append("color_word")
    after = toks[j + 1] if j + 1 < len(toks) and doc.sent[j + 1] == doc.sent[j] else None
    if any(toks[k].form in SIMILE_FORMS or (toks[k].form == "같" and toks[k].base_tag == "VA") for k in idx) or (
            after is not None and (after.form in SIMILE_FORMS or (after.form == "같" and after.base_tag == "VA"))):
        why.append("simile_detail")                                # 사물에 빗댄 구간에서 짐작한 모양(팽이처럼 → conical)
    # (3차 판정 2) 구간 안 모양 용언이 대상 명사를 직접 꾸미거나 대상 명사의 서술어일 때만(생성기 재검증과 같은 함수)
    att = ctx.pm.rewrite_detail_attach_reason(doc, (s, e), subject_span) if subject_span else "detail_no_subject_span"
    if att:
        why.append(att)
    if any(toks[k].lemma in P.body_lemmas for k in idx if toks[k].base_tag in lf._NOUN_TAGS):
        why.append("body_word")
    why.extend(lf._korean_block_reasons(ctx, idx))
    if stages and stages.get("status") == "applied" and allowed:
        item["lineStage"], outside = ls.line_stage_reason(ctx.norm, s, stages["stages"], allowed)
        if outside:
            why.append("non_shape_stage_line")
    rc = _rule_context_hit((s, e), rule_dropped)
    if rc:
        why.append("rule_context_dropped")
        item["ruleContext"] = rc
    why += [r for r in ctx.pm.rewrite_english_reasons(d.get("en") if isinstance(d.get("en"), str) else "", "detail")
            if r not in why]
    return item, sorted(set(why), key=why.index)


def validate(ctx, raw, prompt: RewritePrompt, stages: dict | None, rule_dropped: list[dict]) -> dict:
    """raw = LLM의 item → {outcome, subject, details, adopted, rejectReasons, forbidden, wordnet}.
    outcome: null | malformed | no_subject | forbidden | adopted."""
    allowed = prompt.allowed_stages
    out = {"outcome": None, "subject": None, "details": [], "adopted": None, "rejectReasons": [], "forbidden": [],
           "wordnet": None, "addedCount": 0, "groundedDetailCount": 0}
    if raw is None:
        out["outcome"] = "null"
        return out
    if not isinstance(raw, dict) or not isinstance(raw.get("subject"), dict) or not isinstance(raw.get("details", []), list):
        out.update(outcome="malformed", rejectReasons=["malformed"])
        return out
    sub = raw["subject"]
    en_sub = sub.get("en") if isinstance(sub.get("en"), str) else None

    def en_rule(v):
        return ctx.pm.rewrite_english_reasons(v, "subject")
    if en_sub is None:
        s_item, s_why = {"raw": copy.deepcopy(sub)}, ["malformed"]
    else:
        s_item, s_why = ls.validate(ctx, {"quote": sub.get("quote"), "charSpan": sub.get("charSpan"), "en": en_sub},
                                    stages, allowed, english=en_rule)
        s_why = list(s_why)
        if "quote_mismatch" not in s_why and "malformed" not in s_why:
            rc = _rule_context_hit(s_item.get("charSpan"), rule_dropped)
            if rc:
                s_why.append("rule_context_dropped")
                s_item["ruleContext"] = rc
        wn_why, wn_rec = wnc.reasons(en_sub)
        out["wordnet"] = wn_rec
        s_why += [r for r in wn_why if r not in s_why]
    out["subject"] = {**s_item, "rejectReasons": s_why, "accepted": not s_why}
    forbidden = [f"subject:{r}" for r in s_why if r in FORBIDDEN_REASONS]
    dets = []
    n_added = 0
    for k, d in enumerate(raw.get("details") or []):
        if k >= int(prompt.data["output"]["maxDetails"]):
            dets.append({"raw": copy.deepcopy(d), "rejectReasons": ["too_many_details"], "accepted": False})
            continue
        if not isinstance(d, dict) or not isinstance(d.get("en"), str) or d.get("basis") not in ("quote", "none"):
            dets.append({"raw": copy.deepcopy(d), "rejectReasons": ["malformed"], "accepted": False})
            continue
        if d["basis"] == "none":
            item = {"en": d["en"], "basis": "none", "quote": None, "charSpan": None, "origin": "added"}
            why = list(ctx.pm.rewrite_english_reasons(d["en"], "added"))
            if not why:
                n_added += 1
                if n_added > prompt.max_added:
                    why.append("added_over_limit")
        else:
            item, why = _check_detail(ctx, d, stages, allowed, rule_dropped,
                                      subject_span=(s_item or {}).get("charSpan") if not s_why else None)
        forbidden += [f"detail:{r}" for r in why if r in FORBIDDEN_REASONS]
        dets.append({**item, "rejectReasons": why, "accepted": not why})
    out["details"] = dets
    out["forbidden"] = sorted(set(forbidden))
    out["rejectReasons"] = sorted({r for r in s_why} | {r for x in dets for r in x["rejectReasons"]})
    if out["forbidden"]:
        out["outcome"] = "forbidden"
        return out
    if s_why:
        out["outcome"] = "no_subject"                  # 대상 근거가 없거나 기각 → 덧붙임 포함 LLM 출력을 모두 버림
        return out
    acc = [x for x in dets if x["accepted"]]
    adopted = {"subject": {"en": en_sub, "quote": s_item["quote"], "charSpan": list(s_item["charSpan"])},
               "details": [({"en": x["en"], "origin": "grounded", "quote": x["quote"], "charSpan": list(x["charSpan"])}
                            if x["origin"] == "grounded" else {"en": x["en"], "origin": "added"}) for x in acc]}
    seen, uniq = set(), []
    for x in adopted["details"]:                       # 같은 영어 꾸밈을 두 번 넣지 않음(차례 유지)
        if x["en"] not in seen:
            seen.add(x["en"])
            uniq.append(x)
    adopted["details"] = uniq
    # (CP21 재검토) 서버의 WordNet 판정 상태를 재료에 함께 넘긴다 — 생성기는 같은 판정을 다시 하고, 읽을 수 없으면 이 값으로만 건너뜀
    adopted["wordnet"] = {"status": (out.get("wordnet") or {}).get("status") or "unavailable",
                          "version": (out.get("wordnet") or {}).get("version")}
    out.update(outcome="adopted", adopted=adopted, addedCount=sum(x["origin"] == "added" for x in uniq),
               groundedDetailCount=sum(x["origin"] == "grounded" for x in uniq))
    return out


# ── 기록 ─────────────────────────────────────────────────────────────────────
def _base_record(prompt: RewritePrompt, binfo: dict, seed: int, timeout_s: float, norm: str) -> dict:
    return {
        "version": LLM_REWRITE_VERSION, "validatorRules": VALIDATOR_RULES, "g82ValidatorRules": ls.VALIDATOR_RULES,
        "g77ValidatorRules": lf.VALIDATOR_RULES, "prompt": prompt.info(), "wordnet": wnc.info(),
        "model": {"name": binfo.get("name"), "digest": binfo.get("digest"), "runtime": binfo.get("runtime")},
        "options": {"temperature": prompt.data["options"]["temperature"], "seed": int(seed),
                    "numPredict": prompt.data["options"]["numPredict"], "think": False},
        "timeoutS": float(timeout_s), "cacheKey": None, "cached": False, "at": now_iso(),
        "inputTextSha256": sha256_text(norm), "validatorTextSha256": None, "userSha256": None,
        "validationInputSha256": None, "rule": None, "ruleRoute": None, "lineStages": None, "ruleContextDropped": [],
        "called": False, "candidate": False, "outcome": None, "rejectReasons": [], "forbidden": [], "adopted": None,
        "status": None, "skipReason": None, "error": None, "seconds": None, "llmSeconds": None,
        "rawText": None, "rawItem": None, "validation": None, "shapePromptText": None, "negativeText": None,
        "addedCount": 0, "groundedDetailCount": 0, "rawTextSha256": None,
        # (CP21-4) 본 호출 앞의 예열 요청(관계없는 고정 입력 '.', 참여자 글 없음)은 본 호출과 다른 요청으로 따로 적는다
        "contextPrime": None,
    }


def cache_key(prompt: RewritePrompt, digest, seed: int, norm: str, vinput, rule, pm) -> str:
    L = pm.rewrite_lists()
    return "|".join([sha256_text(norm), str(digest), prompt.version, prompt.sha256, sha256_text(prompt.system),
                     prompt.fill.sha256, prompt.fill.english_block["sha256"], prompt.modifier_block["sha256"],
                     L.added["sha256"], L.block["sha256"], L.neutral["sha256"], VALIDATOR_RULES, ls.VALIDATOR_RULES,
                     lf.VALIDATOR_RULES, str(prompt.data["options"]["temperature"]), str(int(seed)),
                     sha256_text(_canon(prompt.korean_lexicons)), sha256_text(_canon(wnc.info())),
                     sha256_text(_canon(vinput)), sha256_text(_canon(rule))])


def g82_forbidden(g82: dict | None) -> list[str]:
    """G82 기록에서 금지 범주 기각 사유(있으면 G85를 부르지 않고 생성하지 않는다)."""
    return sorted(r for r in (g82 or {}).get("rejectReasons") or [] if r in FORBIDDEN_REASONS)


def propose(prompt: RewritePrompt, backend, norm: str, spec: dict, *, seed: int, timeout_s: float, cache: dict,
            flag: str | None, stages: dict | None = None, g82: dict | None = None, fresh_context: bool = False) -> dict:
    """한 번 부르기(세션 없이도 쓸 수 있는 핵심). flag = 위기·확인 판정 사유(있으면 캐시를 보지도 않고 부르지 않음).
    g82 = 같은 세션의 G82 호출 기록(채택했거나 금지 범주로 기각했으면 부르지 않음)."""
    binfo = backend.info() if hasattr(backend, "info") else {}
    rec = _base_record(prompt, binfo, seed, timeout_s, norm)
    stages = stages or {"status": "unavailable", "reason": "not_given", "lines": norm.count("\n") + 1, "stages": None}
    rec["lineStages"] = stages
    if flag:                                             # 판정이 먼저: 캐시를 조회하지 않는다
        rec.update(status="skipped", skipReason="session_flagged", error=flag)
        return rec
    if g82 is not None and g82.get("status") == "ok" and g82.get("adopted"):
        rec.update(status="skipped", skipReason="g82_adopted")
        return rec
    fb = g82_forbidden(g82)
    if fb:
        rec.update(status="skipped", skipReason="g82_forbidden", outcome="forbidden", forbidden=[f"g82:{r}" for r in fb])
        return rec
    if not hasattr(backend, "structured"):
        rec.update(status="skipped", skipReason="backend_unsupported", error=getattr(backend, "name", None))
        return rec
    from . import none_gen as ng
    t0 = time.monotonic()
    with ng._prompts_lock:
        pm = ng._load_prompts()
        rec["prompt"] = prompt.info(pm)
        srule = ls.stage_rule(stages, prompt.allowed_stages)
        shape = pm.shape_prompt(norm, mapper_spec=spec, stage_rule=srule)
        call, why = ls.rule_route(pm, shape)
        route = {"call": call, "reason": why, "status": shape.get("status"), "blockReason": shape.get("blockReason")}
        rule = {"builderVersion": shape.get("builderVersion"), "lexiconVersion": shape.get("lexiconVersion"),
                "templateVersion": shape.get("templateVersion"), "promptRule": shape.get("promptRule"),
                "mapperBuilder": shape.get("mapperBuilder"), "shapeLexiconSha256": pm._shape_runtime().lexicon_sha256}
        rec["ruleRoute"], rec["rule"] = route, rule
        rule_dropped = [d for d in shape.get("dropped") or [] if d.get("reason") in RULE_CONTEXT_DROPS]
        rec["ruleContextDropped"] = copy.deepcopy(rule_dropped)
        rule_mods = [{"ko": t["ko"], "charSpan": t["charSpan"], "en": t["en"]} for t in shape.get("tokens") or []
                     if t.get("slot") == "shape_modifier" and t.get("charSpan")]
        ctx = ls.make_ctx(pm, norm, spec, prompt, open_form_spans=call) if call else None
    vinput = ls.validation_input(ctx, route, stages) if ctx is not None else {"ruleRoute": route, "lineStages": stages}
    if ctx is not None:
        vinput["ruleContextDropped"] = sorted([list(d["charSpan"]), d["reason"]] for d in rule_dropped)
    rec["validationInputSha256"] = sha256_text(_canon(vinput))
    key = cache_key(prompt, binfo.get("digest"), seed, norm, vinput, rule, pm)
    rec["cacheKey"] = sha256_text(key)[:16]
    if key in cache:
        r = copy.deepcopy(cache[key])
        r["cached"] = True
        return r

    def done(status, **kw):
        rec.update(status=status, **kw)
        cache[key] = copy.deepcopy(rec)
        return rec

    if not call:
        return done("skipped", skipReason=why, seconds=round(time.monotonic() - t0, 2))
    rec["validatorTextSha256"] = sha256_text(ctx.norm)
    with ng._prompts_lock:
        user = build_user(prompt, ctx.norm, ctx.doc, ctx.spans, rule_mods)
    if user is None:
        return done("skipped", skipReason="fence_unavailable", seconds=round(time.monotonic() - t0, 2))
    if rec["validatorTextSha256"] != rec["inputTextSha256"]:
        return done("mismatch", error="LLM 입력 텍스트와 검증기 텍스트가 다름", seconds=round(time.monotonic() - t0, 2))
    rec["userSha256"] = sha256_text(user)
    rec["called"] = True
    if fresh_context and hasattr(backend, "prime_context"):
        # 앞 요청의 KV 캐시 재사용을 끊으려는 예열 요청(고정 입력 '.', num_predict 1). 재현성 원인 확인 결과 효과는 없었다
        # (docs/validation/run-g85-rewrite/repro_probe.json) — 메인 판정(CP21-4)으로 유지하고 따로 기록
        p = backend.prime_context()
        rec["contextPrime"] = {"separateRequest": True, "input": PRIME_INPUT, "numPredict": 1, "ok": bool(p.get("ok")),
                               "ms": p.get("ms"), "at": now_iso()}
    t1 = time.monotonic()
    try:
        res = backend.structured(prompt.system, user, output_schema(prompt), seed=int(seed), timeout_s=float(timeout_s),
                                 temperature=float(prompt.data["options"]["temperature"]),
                                 num_predict=int(prompt.data["options"]["numPredict"]))
    except Exception as exc:  # noqa: BLE001 — 실패·시간 초과는 지금 경로 그대로(재시도 없음)
        el = time.monotonic() - t1
        timeout = el >= float(timeout_s) - 0.05 or "timeout" in str(exc).lower()
        return done("timeout" if timeout else "failed", error=f"{type(exc).__name__}: {exc}"[:300],
                    seconds=round(time.monotonic() - t0, 2))
    llm_s = time.monotonic() - t1
    rec["llmSeconds"] = round(llm_s, 2)
    rec["rawText"] = res.raw or ""                        # (CP21-3) 원시 출력 전문(자르지 않음)과 그 sha256
    rec["rawTextSha256"] = sha256_text(rec["rawText"])
    if llm_s > float(timeout_s):
        return done("timeout", error=f"{llm_s:.1f}초 > {timeout_s}초", seconds=round(time.monotonic() - t0, 2))
    try:
        parsed = json.loads(res.raw)
        if not isinstance(parsed, dict) or "item" not in parsed:
            raise ValueError("item 키가 없음")
        raw_item = parsed["item"]
    except Exception as exc:  # noqa: BLE001
        return done("invalid_output", error=f"{type(exc).__name__}: {exc}"[:300], seconds=round(time.monotonic() - t0, 2))
    rec["rawItem"] = copy.deepcopy(raw_item)
    rec["candidate"] = raw_item is not None
    with ng._prompts_lock:
        v = validate(ctx, raw_item, prompt, stages, rule_dropped)
        rec.update(validation=v, outcome=v["outcome"], rejectReasons=v["rejectReasons"], forbidden=v["forbidden"])
        if v["outcome"] != "adopted":
            return done("null" if v["outcome"] == "null" else "rejected", seconds=round(time.monotonic() - t0, 2))
        composed = pm.shape_prompt(norm, mapper_spec=spec, llm_rewrite_item=v["adopted"],
                                   stage_rule=ls.stage_rule(stages, prompt.allowed_stages))   # 생성 직전 재검증과 같은 조립
    if composed.get("shapeSource") != ORIGIN:            # 재검증에서 떨어지면 채택하지 않음(fail closed)
        rec.update(outcome="recheck_failed", rejectReasons=["recheck_failed"])
        return done("rejected", seconds=round(time.monotonic() - t0, 2))
    return done("ok", adopted=v["adopted"], shapePromptText=composed.get("text"), negativeText=composed.get("negativeText"),
                addedCount=v["addedCount"], groundedDetailCount=v["groundedDetailCount"],
                seconds=round(time.monotonic() - t0, 2))


def run(session, spec: dict, norm: str, g82: dict | None) -> dict:
    """세션에서 한 번([맞는 게 없어요] 뒤 G82가 끝난 뒤, selection.py 스레드). 어떤 예외도 세션을 멈추지 않게 부르는 쪽이 감싼다."""
    rt = session.rt
    g = rt.cfg.gen3d
    prompt: RewritePrompt = rt.llm_rewrite_prompt
    flag = lf.session_flag(session)                      # 캐시보다 먼저
    stages = ls.line_stages(session, norm)
    if not getattr(rt, "backend_ok", True) and not flag:
        rec = _base_record(prompt, rt.backend.info() if hasattr(rt.backend, "info") else {}, g.on_none_llm_rewrite_seed,
                           g.on_none_llm_rewrite_timeout_s, norm)
        rec.update(status="skipped", skipReason="backend_unavailable", lineStages=stages)
        return rec
    return propose(prompt, rt.backend, norm, spec, seed=int(g.on_none_llm_rewrite_seed),
                   timeout_s=float(g.on_none_llm_rewrite_timeout_s), cache=session.llm_rewrite_cache, flag=flag,
                   stages=stages, g82=g82, fresh_context=True)


def decide_route(rec: dict | None, rule_reason: str | None) -> tuple[str, str]:
    """G85 호출 기록 + 규칙 경로 사유(no_shape_stated | modifier_only) → (promptRoute, 사유).
    - 채택 → llm_rewrite
    - 금지 범주(G85 검증 또는 G82 기각) → none(중립 형태도 만들지 않음)
    - 대상 근거 없음·LLM null → 규칙이 아무 형태 낱말도 못 잡았으면(no_shape_stated) system_default, 꾸밈말은 잡았으면(modifier_only) rule
    - 실패·시간 초과·형식 위반·불일치·재검증 실패·건너뜀(판정 등) → modifier_only면 rule, 아니면 none(지금 경로)"""
    r = rec or {}
    st, oc = r.get("status"), r.get("outcome")
    if st == "ok" and r.get("adopted"):
        return "llm_rewrite", "adopted"
    if oc == "forbidden":
        return "none", "forbidden_category"
    if oc in ("null", "no_subject"):
        if rule_reason == "no_shape_stated":
            return "system_default", f"no_grounded_subject:{oc}"
        return "rule", f"no_grounded_subject:{oc}"
    why = r.get("skipReason") or st or "not_called"
    return ("rule" if rule_reason == "modifier_only" else "none"), str(why)


def element_record(rec: dict | None) -> list[dict]:
    """기록용 요소 목록(역할·영어·근거·출처 grounded/added·통과 여부·사유). 원시 출력은 rec.rawText에 따로."""
    v = (rec or {}).get("validation") or {}
    out = []
    if v.get("subject"):
        s = v["subject"]
        out.append({"role": "subject", "en": s.get("en"), "quote": s.get("quote"), "charSpan": s.get("charSpan"),
                    "origin": "grounded", "accepted": s.get("accepted"), "rejectReasons": s.get("rejectReasons")})
    for d in v.get("details") or []:
        out.append({"role": "detail", "en": d.get("en"), "quote": d.get("quote"), "charSpan": d.get("charSpan"),
                    "origin": d.get("origin"), "accepted": d.get("accepted"), "rejectReasons": d.get("rejectReasons")})
    return out


def subject_basis(rec: dict | None) -> dict | None:
    a = (rec or {}).get("adopted") or {}
    s = a.get("subject")
    return {"quote": s["quote"], "charSpan": list(s["charSpan"])} if s else None
