"""G82: [맞는 게 없어요] 뒤 규칙 그림 프롬프트에 중심 형태 명사가 없을 때, 면담 LLM이 확정 텍스트에서 형태 낱말 하나를 인용하고
영어 이름(소문자 한 낱말)을 낸다([gen3d] on_none_llm_shape, 기본 끔). AGENTS.md 원칙 1의 세 번째 예외(2026-11-28 연구 책임자 결정).

흐름: 확정 텍스트(정규화한 그대로 — 면담자 질문은 넣지 않음) + 매퍼 v2 spec → 규칙 그림 프롬프트(tools/gen3d/prompts.shape_prompt)
  → 중심 형태 명사가 있거나(rule_has_shape) 다른 사유로 막혔으면(rule_blocked:*) 부르지 않음
  → 면담 모델을 한 번 부름(온도 0·seed 고정·JSON 스키마, 시간 한도) → {"item": null | {quote, charSpan, en}}
  → 검증기: G77 형태 낱말 검증(llm_fill._check_item, 복사하지 않고 그대로 부름: 인용 글자·토큰 경계·어절 수·매퍼가 쓴/뺀 구간·
    부정·회상·지난 일·남의 말·가정·두 문장·감정·감각 낱말·몸 낱말·장소·크기 자리·속성 비유·한국어 사람·동물·안개·불꽃 명사·
    영어 금지 목록) + G82 규칙(아래 VALIDATOR_RULES) + 영어 규칙(tools/gen3d/prompts.llm_shape_english_reasons)
  → 통과한 것만 adopted. 프롬프트 문장·꾸밈말·부정 틀은 규칙이 붙인다(shape_prompt(..., llm_shape_items=...)).
부르지 않는 경우: 위기·확인 판정(llm_fill.session_flag — 캐시 조회보다 먼저, 캐시를 보지도 않음), 백엔드가 JSON 호출을 못 함,
규칙이 형태를 잡음·막음. 실패·시간 초과·형식 위반이면 결과를 버리고 지금 경로(재시도 없음). 같은 캐시 키는 세션 안에서 다시 부르지 않는다.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

from . import llm_fill as lf
from .paths import PROMPTS_DIR, shared
from .scene_builder import normalize_confirmed
from .session_log import now_iso

LLM_SHAPE_VERSION = "ifs-llm-shape/0.1.0"
# G82 검증기 판. 안에서 쓰는 G77 검증기 판(lf.VALIDATOR_RULES)도 따로 기록·캐시 키에 넣는다. 판마다의 평가 수치는
# docs/validation/run-g82-llm-shape-offline/README.md(1차)·run-g82-llm-shape-eval2/README.md(2차).
#   0.1.0: G77 형태 낱말 검증 + G82 영어 규칙. 0.2.0: 인용이 꼭 한 번 나오면 charSpan을 그 자리로 고침(repair_span),
#   '처럼 생겼어요'(모양 동사)의 simile_of_predicate를 풀어 줌. 0.3.0: 중심 명사가 색 낱말 color_word, 추상 명사 non_shape_noun.
#   0.4.0(G82 다음 단계·CP19): ① 매퍼가 form.*에 쓴 구간은 인용 허용(호출 조건이 '규칙에 중심 형태 명사 없음'이라 그때만) ②
#   단계 표지를 얻으면(확정 텍스트를 고치지 않았고 줄과 면담 답이 1:1) 형태·모습을 묻는 단계 줄에서만 인용 허용(non_shape_stage_line)
#   ③ 영어 이름은 한 낱말(two_words, 규칙은 prompts.llm_shape_english_reasons) ④ 캐시 키에 검증 입력(쓴·뺀 구간·부정 구간·규칙
#   중심 명사 유무·단계 표지)·한국어 검증 사전 해시·규칙 프롬프트·매퍼 판을 넣음
#   0.5.0(G82 3단계): G77 검증기 0.4.0(속성 비유 판정이 어근 XR을 건너뛰던 버그 수정)을 따름. '처럼 생겼어요' 예외 판정도 XR을
#   건너뛰지 않음('X처럼 단단하게 생겼어요'는 예외가 아님)
VALIDATOR_RULES = "ifs-llm-shape-validator/0.5.0"
VALIDATOR_RULES_HISTORY = ("ifs-llm-shape-validator/0.1.0", "ifs-llm-shape-validator/0.2.0",
                           "ifs-llm-shape-validator/0.3.0", "ifs-llm-shape-validator/0.4.0", VALIDATOR_RULES)
ORIGIN = "llm_translated"                              # 토큰·기록 출처(규칙 사전·G77 llm_quoted와 구분)
PROMPT_DIR = PROMPTS_DIR / "llm_shape"
DEFAULT_PROMPT = "llm_shape.v0.3.0.json"
EVIDENCE = "shape_noun"
FORM_PATH_PREFIX = "form."
# 검증기가 읽는 한국어 사전(감정·감각·몸 낱말 = G77 FillPrompt, 사람·동물·제외 범주 = base_shapes·형태 사전 blocked)
KOREAN_LEXICONS = ("layer1_lexicon.v0.json", "layer1_interview.v0.json", "vad_ko.v0.json", "base_shapes.v1.json",
                   "shape_prompt_en.v0.json")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _canon(x) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def config_problems(cfg) -> list[str]:
    """[gen3d] on_none_llm_shape를 켰을 때 함께 있어야 하는 설정(시작 점검). 비면 문제 없음."""
    g = cfg.gen3d
    out = []
    if not g.on_none:
        out.append("[gen3d] on_none이 꺼져 있음([맞는 게 없어요] 뒤 생성이 없으면 쓸 곳이 없음)")
    if not g.on_none_image_pick:
        out.append("[gen3d] on_none_image_pick이 꺼져 있음(LLM 형태 이름은 참여자가 그림을 먼저 고르는 경로에서만 씀)")
    if not cfg.selection.enabled:
        out.append("[selection] enabled가 꺼져 있음")
    if cfg.mapping.mode != "v2":
        out.append(f"[mapping] mode = \"{cfg.mapping.mode}\"(검증기가 매퍼 v2 spec의 쓴·뺀 구간을 씀)")
    if float(g.on_none_llm_shape_timeout_s) <= 0:
        out.append("[gen3d] on_none_llm_shape_timeout_s가 0 이하")
    return out


def g77_shape_slot_open(cfg) -> bool:
    """G77(llm_fill)이 형태 낱말 칸(shape_noun)을 내밀어도 되는가. G82가 켜지면 거짓(다른 빈 슬롯 제안은 그대로)."""
    return not bool(cfg.gen3d.on_none_llm_shape)


class ShapePrompt:
    """고정 프롬프트 파일(판·status draft). 파일 바이트 해시와 검증기가 쓰는 목록·사전의 해시를 기록·캐시 키에 쓴다."""

    def __init__(self, name: str = DEFAULT_PROMPT):
        p = Path(name)
        self.path = p if p.is_absolute() else PROMPT_DIR / name
        raw = self.path.read_text(encoding="utf-8")
        self.sha256 = sha256_text(raw)
        self.data = json.loads(raw)
        self.version = self.data["promptVersion"]
        self.fence = self.data["dataFence"]
        # 검증기의 한국어 목록·영어 금지 목록은 G77 프롬프트 파일을 그대로 읽는다(복사하지 않음 — 판정이 갈라지지 않게)
        self.fill = lf.FillPrompt(self.data["validatorConfig"])
        mb = shared("lexicon", self.data["englishModifierLexicon"]).read_text(encoding="utf-8")
        self.modifier_block = {"file": self.data["englishModifierLexicon"], "sha256": sha256_text(mb),
                               "version": json.loads(mb)["version"]}
        self.korean_lexicons = {f: sha256_text(shared("lexicon", f).read_text(encoding="utf-8")) for f in KOREAN_LEXICONS}
        rule = self.data.get("lineStageRule") or {}
        self.allowed_stages = tuple(rule.get("allowedStages") or ())

    def info(self) -> dict:
        return {"promptId": self.data["promptId"], "promptVersion": self.version, "file": self.path.name,
                "promptSha256": self.sha256, "status": self.data["status"],
                "validatorConfig": {"file": self.fill.path.name, "sha256": self.fill.sha256, "version": self.fill.version},
                "englishBlock": dict(self.fill.english_block), "englishModifierBlock": dict(self.modifier_block),
                "koreanLexicons": dict(self.korean_lexicons), "allowedStages": list(self.allowed_stages)}


def output_schema(prompt: ShapePrompt) -> dict:
    o = prompt.data["output"]
    item = {"type": "object",
            "properties": {"quote": {"type": "string", "maxLength": int(o["maxQuoteLength"])},
                           "charSpan": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                           "en": {"type": "string", "maxLength": int(o["maxEnglishLength"])}},
            "required": ["quote", "charSpan", "en"]}
    return {"type": "object", "properties": {"item": {"anyOf": [{"type": "null"}, item]}}, "required": ["item"]}


# ── 규칙 경로 판정 ────────────────────────────────────────────────────────────
def rule_route(pm, shape: dict) -> tuple[bool, str]:
    """규칙 그림 프롬프트 → (부를지, 사유). 중심 형태 명사가 없고(꾸밈말만 잡은 경우 포함) 막을 사유가 없을 때만 부른다."""
    if shape.get("blockReason") == "no_shape_stated":
        return True, "no_shape_stated"
    if shape.get("blockReason"):
        return False, f"rule_blocked:{shape['blockReason']}"
    default = pm._shape_runtime().lex["template"]["defaultNoun"]
    toks = shape.get("tokens") or []
    if any(t.get("slot") == "template" and t.get("en") == default for t in toks):
        return True, "modifier_only"
    return False, "rule_has_shape"


# ── 단계 표지(어느 줄이 어느 면담 단계의 답인가) ──────────────────────────────────
def line_stages(session, norm: str) -> dict:
    """확정 텍스트 줄 → 면담 단계. 확정 텍스트를 고치지 않았고, 줄이 확정 전 참여자 답(넘어가기·'없어요' 제외)과 1:1로 같을 때만
    applied. 아니면 unavailable(사유)이고 단계 규칙을 걸지 않는다(그 사실을 기록). 규칙만 — 줄 내용으로 단계를 짐작하지 않는다."""
    data = getattr(getattr(session, "log", None), "data", None) or {}
    conf = data.get("confirmation") or {}
    lines = norm.split("\n")
    if conf.get("edited") is not False:
        return {"status": "unavailable", "reason": "edited" if conf.get("edited") else "no_confirmation_record",
                "lines": len(lines), "stages": None}
    answers = []
    for t in data.get("turns") or []:
        if t.get("speaker") != "participant":
            continue
        src = str(t.get("source") or "")
        if src.startswith("control:"):
            if src == "control:confirm":
                break
            continue
        if (t.get("flags") or {}).get("noMore"):
            continue
        answers.append((t.get("stage"), t.get("text") or ""))
    if len(answers) != len(lines) or any(normalize_confirmed(a) != b for (_, a), b in zip(answers, lines)):
        return {"status": "unavailable", "reason": "line_turn_mismatch", "lines": len(lines), "stages": None}
    return {"status": "applied", "reason": None, "lines": len(lines), "stages": [s for s, _ in answers]}


def _line_of(norm: str, pos: int) -> int:
    return norm.count("\n", 0, max(0, pos))


# ── LLM 입력 ─────────────────────────────────────────────────────────────────
def build_user(prompt: ShapePrompt, norm: str, doc, spans: dict) -> str | None:
    eoj = []
    for a, b in doc.eojeols:
        s, e = doc.toks[a].start, doc.toks[b].end
        eoj.append(f"{s}: {norm[s:e]}")
    filled = [f"- '{norm[s[0]:s[1]]}' [{s[0]}, {s[1]}]" for s, _, _ in sorted(spans["used"])]
    excl = [f"- '{norm[s[0]:s[1]]}' [{s[0]}, {s[1]}] ({r})" for s, r, _ in sorted(spans["excluded"], key=lambda x: x[0])]
    data = {"text": norm, "eojeols": "\n".join(eoj) or "(없음)", "filled": "\n".join(filled) or "(없음)",
            "excluded": "\n".join(excl) or "(없음)"}
    fence = lf.data_fence(prompt, [*data.values(), prompt.data["userTemplate"], prompt.data["system"]])
    if fence is None:
        return None
    _, fo, fc = fence
    return prompt.data["userTemplate"].format(fenceOpen=fo, fenceClose=fc, **data)


# ── 검증 ─────────────────────────────────────────────────────────────────────
def make_ctx(pm, norm: str, spec: dict, prompt: ShapePrompt, open_form_spans: bool):
    """G77 검증 문맥(형태 낱말 칸 하나만 연 것). 영어 목록이 생성 규칙과 다르면 멈춘다.
    open_form_spans(0.4.0): 규칙 프롬프트에 중심 형태 명사가 없을 때(= 부르는 조건) 매퍼가 form.*에 쓴 구간을 '쓴 구간'에서 뺀다
    (형태 종류의 근거로 쓴 낱말은 형태 낱말이라는 근거). 다른 슬롯이 쓴 구간·매퍼가 뺀 구간은 그대로 막는다."""
    mb = pm.english_modifier_block()
    if mb.file != prompt.modifier_block["file"] or mb.sha256 != prompt.modifier_block["sha256"]:
        raise ValueError(f"영어 꾸밈말 금지 목록이 다름: 프롬프트 {prompt.modifier_block['file']} ≠ 생성 규칙 {mb.file}")
    ctx = lf._Ctx(pm, norm, spec, {}, prompt.fill, [lf.SHAPE_SLOT])
    ctx.form_spans_opened = []
    if open_form_spans:
        keep = []
        for u in ctx.spans["used"]:
            if str(u[1]).startswith(FORM_PATH_PREFIX):
                ctx.form_spans_opened.append({"charSpan": list(u[0]), "path": u[1], "text": norm[u[0][0]:u[0][1]]})
            else:
                keep.append(u)
        ctx.spans = {"used": keep, "excluded": ctx.spans["excluded"]}
    return ctx


def validation_input(ctx, route: dict, stages: dict) -> dict:
    """캐시 키·기록용: 검증 결과를 바꾸는 spec·규칙 쪽 입력(같은 텍스트라도 이것이 다르면 다른 키)."""
    return {"used": sorted([list(s), p] for s, p, _ in ctx.spans["used"]),
            "excluded": sorted([list(s), r] for s, r, _ in ctx.spans["excluded"]),
            "formSpansOpened": ctx.form_spans_opened, "negSpans": sorted(list(x) for x in ctx.neg_spans),
            "contextSentences": sorted(ctx.context), "ruleRoute": route, "lineStages": stages}


def repair_span(norm: str, quote, span):
    """(0.2.0) 인용 글자가 확정 텍스트에 **꼭 한 번** 나오는데 LLM이 센 charSpan이 그 자리와 다르면, 그 한 자리로 고친다
    (규칙만 — 인용 글자는 바꾸지 않음). 두 번 이상 나오거나 없으면 고치지 않는다(그대로 quote_mismatch). → (span, 고쳤는가)."""
    ok_span = isinstance(span, list) and len(span) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in span)
    if not isinstance(quote, str) or not quote.strip():
        return span, False
    if ok_span and 0 <= span[0] < span[1] <= len(norm) and norm[span[0]:span[1]] == quote:
        return span, False
    occ = [i for i in range(len(norm) - len(quote) + 1) if norm.startswith(quote, i)]
    if len(occ) != 1:
        return span, False
    return [occ[0], occ[0] + len(quote)], True


_SHAPE_VERBS = frozenset({"생기", "닮"})     # '베개처럼 생겼어요'·'X를 닮았어요' = 지금 모양을 말함(G77 frame의 _PAST_EXEMPT_VERBS와 같은 낱말)


def _simile_of_shape_verb(ctx, item: dict) -> bool:
    """(0.2.0) G77 simile_of_predicate가 '처럼 생겼어요'(모양 동사)에 걸린 경우인가. 비유 표지 뒤 첫 내용 낱말이 생기·닮이면 참."""
    s, e = item["charSpan"]
    toks, doc = ctx.toks, ctx.doc
    idx = [k for k, t in enumerate(toks) if t.start < e and s < t.end]
    if not idx:
        return False
    j = idx[-1]
    for k in range(j + 1, len(toks)):
        if doc.sent[k] != doc.sent[j]:
            return False
        t = toks[k]
        if t.form in ("처럼", "같이", "같") or t.base_tag.startswith(("E", "J", "S")) or t.base_tag in lf._AFFIX_TAGS \
                or t.base_tag == "VCP":
            continue
        return t.base_tag in ("VV", "VA") and t.lemma in _SHAPE_VERBS
    return False


def _head_noun(ctx, item: dict):
    """인용 안 중심 명사(마지막 일반 명사, 형식 명사는 건너뜀) — G77 _check_item과 같은 고르기."""
    s, e = item["charSpan"]
    idx = [k for k, t in enumerate(ctx.toks) if t.start < e and s < t.end and t.base_tag in lf._NOUN_TAGS]
    return next((k for k in reversed(idx) if ctx.toks[k].form not in ctx.rt.generic), None)


def validate(ctx, raw, stages: dict | None = None, allowed_stages: tuple = ()) -> tuple[dict | None, list[str]]:
    """raw = LLM의 item(null 또는 dict) → (정리한 항목, 기각 사유). null이면 (None, [])."""
    if raw is None:
        return None, []
    if not isinstance(raw, dict) or not isinstance(raw.get("en"), str):
        return {"raw": copy.deepcopy(raw)}, ["malformed"]
    span, repaired = repair_span(ctx.norm, raw.get("quote"), raw.get("charSpan"))
    g77 = {"slot": lf.SHAPE_SLOT, "value": raw.get("en"), "quote": raw.get("quote"), "charSpan": span,
           "evidenceType": EVIDENCE}
    item, why = lf._check_item(ctx, g77)                      # G77 검증기 그대로(형태 낱말 갈래)
    if why == ["malformed"]:
        return {"raw": copy.deepcopy(raw)}, why
    out = {"quote": item["quote"], "charSpan": list(item["charSpan"]), "en": item["value"]}
    if repaired:
        out["spanRepaired"] = {"llmCharSpan": copy.deepcopy(raw.get("charSpan")), "to": list(span)}
    if "excludedBy" in item:
        out["excludedBy"] = item["excludedBy"]
    why = list(why)
    aligned = "quote_mismatch" not in why
    head = _head_noun(ctx, out) if aligned else None
    if head is not None:
        if lf.has_attribute_word(ctx, "color", [head], head):
            why.append("color_word")                              # 색 이름('쑥색')에서 형태를 짓지 않음
        if ctx.toks[head].form in ctx.pm.english_modifier_block().korean_non_shape_heads:
            why.append("non_shape_noun")                          # 느낌·마음 같은 추상 명사
    if aligned and stages and stages.get("status") == "applied" and allowed_stages:
        st = stages["stages"]
        ln = _line_of(ctx.norm, out["charSpan"][0])
        out["lineStage"] = st[ln] if ln < len(st) else None
        if out["lineStage"] not in allowed_stages:
            why.append("non_shape_stage_line")                    # 걱정한 일(찾기 단계) 줄의 사물
    if "simile_of_predicate" in why and _simile_of_shape_verb(ctx, out):
        why.remove("simile_of_predicate")
        out["exempted"] = ["simile_of_predicate:shape_verb"]
    why += [r for r in ctx.pm.llm_shape_english_reasons(raw["en"]) if r not in why]
    return out, why


# ── 기록 ─────────────────────────────────────────────────────────────────────
def _base_record(prompt: ShapePrompt, binfo: dict, seed: int, timeout_s: float, norm: str) -> dict:
    return {
        "version": LLM_SHAPE_VERSION, "validatorRules": VALIDATOR_RULES, "g77ValidatorRules": lf.VALIDATOR_RULES,
        "prompt": prompt.info(),
        "model": {"name": binfo.get("name"), "digest": binfo.get("digest"), "runtime": binfo.get("runtime")},
        "options": {"temperature": prompt.data["options"]["temperature"], "seed": int(seed),
                    "numPredict": prompt.data["options"]["numPredict"], "think": False},
        "timeoutS": float(timeout_s), "cacheKey": None, "cached": False, "at": now_iso(),
        # 입력 해시: LLM에 넣은 확정 텍스트와 검증기가 본 텍스트가 같아야 한다(다르면 status mismatch로 버림)
        "inputTextSha256": sha256_text(norm), "validatorTextSha256": None, "userSha256": None,
        "validationInputSha256": None, "rule": None, "lineStages": None, "formSpansOpened": [],
        # 따로 두는 칸: 부름 여부 · 후보(LLM이 null이 아닌 항목을 냈는가) · 기각 사유 · 채택
        "called": False, "ruleRoute": None, "candidate": False, "rejectReasons": [], "adopted": None,
        "status": None, "skipReason": None, "error": None, "seconds": None, "llmSeconds": None,
        "rawText": None, "rawItem": None, "item": None, "shapePromptText": None,
        # 선택 단계(selection.py)가 채우는 자리: 노출·그림 고름·[그 말이 아니에요]
        "exposure": {"exposed": None, "imageChosen": None, "basisRejected": None, "at": None},
    }


def cache_key(prompt: ShapePrompt, digest, seed: int, norm: str, vinput: dict | None = None, rule: dict | None = None) -> str:
    """같은 텍스트라도 검증 입력(vinput: 쓴·뺀 구간·부정 구간·규칙 중심 명사 유무·단계 표지)·규칙 프롬프트·매퍼 판(rule)이 다르면 다른 키."""
    return "|".join([sha256_text(norm), str(digest), prompt.version, prompt.sha256, prompt.fill.sha256,
                     prompt.fill.english_block["sha256"], prompt.modifier_block["sha256"], VALIDATOR_RULES,
                     lf.VALIDATOR_RULES, str(prompt.data["options"]["temperature"]), str(int(seed)),
                     sha256_text(_canon(prompt.korean_lexicons)), sha256_text(_canon(vinput)), sha256_text(_canon(rule))])


def propose(prompt: ShapePrompt, backend, norm: str, spec: dict, *, seed: int, timeout_s: float,
            cache: dict, flag: str | None, stages: dict | None = None) -> dict:
    """한 번 부르기(세션 없이도 쓸 수 있는 핵심). flag = 위기·확인 판정 사유(있으면 캐시를 보지도 않고 부르지 않음).
    stages = line_stages() 결과(없으면 단계 규칙을 걸지 않고 unavailable로 적음)."""
    binfo = backend.info() if hasattr(backend, "info") else {}
    rec = _base_record(prompt, binfo, seed, timeout_s, norm)
    stages = stages or {"status": "unavailable", "reason": "not_given", "lines": norm.count("\n") + 1, "stages": None}
    rec["lineStages"] = stages
    if flag:                                             # 판정이 먼저: 캐시를 조회하지 않는다(G77 순서, CP15-2)
        rec.update(status="skipped", skipReason="session_flagged", error=flag)
        return rec
    if not hasattr(backend, "structured"):
        rec.update(status="skipped", skipReason="backend_unsupported", error=getattr(backend, "name", None))
        return rec
    from . import none_gen as ng                         # tools/gen3d/prompts.py(Kiwi·매퍼 판단 함수)를 같은 잠금으로
    t0 = time.monotonic()
    with ng._prompts_lock:
        pm = ng._load_prompts()
        shape = pm.shape_prompt(norm, mapper_spec=spec)
        call, why = rule_route(pm, shape)
        route = {"call": call, "reason": why, "status": shape.get("status"), "blockReason": shape.get("blockReason")}
        rule = {"builderVersion": shape.get("builderVersion"), "lexiconVersion": shape.get("lexiconVersion"),
                "templateVersion": shape.get("templateVersion"), "promptRule": shape.get("promptRule"),
                "mapperBuilder": shape.get("mapperBuilder"),
                "shapeLexiconSha256": pm._shape_runtime().lexicon_sha256}
        rec["ruleRoute"], rec["rule"] = route, rule
        ctx = make_ctx(pm, norm, spec, prompt, open_form_spans=call) if call else None
    vinput = validation_input(ctx, route, stages) if ctx is not None else {"ruleRoute": route, "lineStages": stages}
    rec["validationInputSha256"] = sha256_text(_canon(vinput))
    key = cache_key(prompt, binfo.get("digest"), seed, norm, vinput, rule)
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
    rec["formSpansOpened"] = ctx.form_spans_opened
    rec["validatorTextSha256"] = sha256_text(ctx.norm)
    with ng._prompts_lock:
        user = build_user(prompt, ctx.norm, ctx.doc, ctx.spans)
    if user is None:
        return done("skipped", skipReason="fence_unavailable", seconds=round(time.monotonic() - t0, 2))
    if rec["validatorTextSha256"] != rec["inputTextSha256"]:
        return done("mismatch", error="LLM 입력 텍스트와 검증기 텍스트가 다름", seconds=round(time.monotonic() - t0, 2))
    rec["userSha256"] = sha256_text(user)
    rec["called"] = True
    t1 = time.monotonic()
    try:
        res = backend.structured(prompt.data["system"], user, output_schema(prompt), seed=int(seed), timeout_s=float(timeout_s),
                                 temperature=float(prompt.data["options"]["temperature"]),
                                 num_predict=int(prompt.data["options"]["numPredict"]))
    except Exception as exc:  # noqa: BLE001 — 실패·시간 초과는 지금 경로 그대로
        el = time.monotonic() - t1
        timeout = el >= float(timeout_s) - 0.05 or "timeout" in str(exc).lower()
        return done("timeout" if timeout else "failed", error=f"{type(exc).__name__}: {exc}"[:300],
                    seconds=round(time.monotonic() - t0, 2))
    llm_s = time.monotonic() - t1
    rec["llmSeconds"] = round(llm_s, 2)
    rec["rawText"] = (res.raw or "")[:4000]
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
    if raw_item is None:
        return done("null", seconds=round(time.monotonic() - t0, 2))
    rec["candidate"] = True
    with ng._prompts_lock:
        item, why = validate(ctx, raw_item, stages, prompt.allowed_stages)
        rec["item"], rec["rejectReasons"] = item, why
        if why:
            return done("rejected", seconds=round(time.monotonic() - t0, 2))
        adopted = {"quote": item["quote"], "charSpan": list(item["charSpan"]), "en": item["en"], "origin": ORIGIN}
        composed = pm.shape_prompt(norm, mapper_spec=spec, llm_shape_items=[adopted])   # 생성 직전 재검증과 같은 조립
    if composed.get("shapeSource") != ORIGIN:            # 재검증에서 떨어지면 채택하지 않음(fail closed)
        rec["rejectReasons"] = ["recheck_failed"]
        return done("rejected", seconds=round(time.monotonic() - t0, 2))
    return done("ok", adopted=adopted, shapePromptText=composed.get("text"), seconds=round(time.monotonic() - t0, 2))


def run(session, spec: dict, norm: str) -> dict:
    """세션에서 한 번([맞는 게 없어요] 뒤 그림 회차 작업, selection.py). 어떤 예외도 세션을 멈추지 않게 부르는 쪽이 감싼다."""
    rt = session.rt
    g = rt.cfg.gen3d
    prompt: ShapePrompt = rt.llm_shape_prompt
    flag = lf.session_flag(session)                      # 캐시보다 먼저
    stages = line_stages(session, norm)
    if not getattr(rt, "backend_ok", True) and not flag:
        rec = _base_record(prompt, rt.backend.info() if hasattr(rt.backend, "info") else {}, g.on_none_llm_shape_seed,
                           g.on_none_llm_shape_timeout_s, norm)
        rec.update(status="skipped", skipReason="backend_unavailable", lineStages=stages)
        return rec
    return propose(prompt, rt.backend, norm, spec, seed=int(g.on_none_llm_shape_seed),
                   timeout_s=float(g.on_none_llm_shape_timeout_s), cache=session.llm_shape_cache, flag=flag, stages=stages)


def shape_items_from(rec: dict | None) -> list[dict]:
    """기록 → 규칙 프롬프트에 넘길 항목(채택된 것만, 0–1개). shape_prompt(..., llm_shape_items=...)"""
    a = (rec or {}).get("adopted")
    return [{"quote": a["quote"], "charSpan": list(a["charSpan"]), "en": a["en"]}] if a else []


# ── (G83-b) 그림 고르기 화면에 보이는 근거 낱말 ─────────────────────────────────────
# LLM 인용 구간(검증기를 통과한 것)에는 조사·서술격 조사가 붙어 있을 수 있다('판때기예요', '톱니바퀴가'). 화면에는 그 구간 안의
# 첫 명사 덩어리(원문 글자 그대로의 부분 구간)만 보인다. 기록에는 LLM 인용과 화면에 보인 구간을 둘 다 남긴다(basisShown).
# 원문에 없는 글자를 만들지 않는다: 보이는 글은 늘 확정 텍스트[shownSpan]이고, Kiwi 형태와 원문 글자가 다르면(축약 등) 줄이지 않는다.
BASIS_DISPLAY_VERSION = "ifs-llm-shape-basis-display/0.1.0"
_BASIS_HEAD_TAGS = {"NNG", "NNP", "NR", "SL", "SH"}            # 덩어리를 시작하는 품사(의존 명사 '것'은 시작하지 않음)
_BASIS_RUN_TAGS = _BASIS_HEAD_TAGS | {"XSN", "SN"}              # 이어 붙는 품사(접미사 '들' 등)


def basis_display(norm: str, quote: str, char_span, template: str) -> dict:
    """확정 텍스트(norm)·LLM 인용·charSpan·문구 틀('{quote}'·'{rago}') → 화면 글과 기록.
    {quote} = 인용 구간 안 첫 명사 덩어리(없거나 판단할 수 없으면 인용 전체), {rago} = 그 낱말 받침에 맞춘 '이라고'/'라고'.
    같은 입력 → 같은 결과(Kiwi 형태소 분석만, LLM 없음)."""
    from . import none_gen as ng
    from .korean import josa, normalize

    s, e = (list(char_span) + [None, None])[:2] if isinstance(char_span, (list, tuple)) else (None, None)
    out = {"version": BASIS_DISPLAY_VERSION, "llmQuote": quote, "llmCharSpan": [s, e] if s is not None else None,
           "shownText": quote, "shownSpan": [s, e] if s is not None else None, "trimmed": False, "fallback": None,
           "particle": None, "text": None}
    if "{rago}" not in template:
        out["fallback"] = "template_without_particle"   # 0.12 문구('{quote}'라고)는 인용 전체를 그대로(줄이면 조사가 맞지 않음)
    elif not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(norm) and norm[s:e] == quote):
        out["fallback"] = "span_mismatch"
    elif normalize(norm) != norm:
        out["fallback"] = "offset_basis_differs"
    else:
        toks = None
        with ng._prompts_lock:                              # 그림 프롬프트 규칙과 같은 Kiwi(같은 잠금)
            try:
                an = ng._load_prompts()._shape_runtime().analyzer
                toks = an.tokens(norm) if an.available else None
            except (Exception, SystemExit):                 # noqa: BLE001 — 분석을 못 하면 줄이지 않는다(인용 전체)
                toks = None
        if toks is None:
            out["fallback"] = "no_kiwi"
        else:
            inside = [t for t in toks if t.start >= s and t.end <= e and t.end > t.start]
            run = []
            for t in inside:
                tag = t.base_tag
                if not run:
                    if tag in _BASIS_HEAD_TAGS:
                        run = [t]
                elif tag in _BASIS_RUN_TAGS and t.start == run[-1].end:
                    run.append(t)
                else:
                    break
            if not run:
                out["fallback"] = "no_noun"
            else:
                a, b = run[0].start, run[-1].end
                if norm[a:b] != "".join(t.form for t in run):
                    out["fallback"] = "form_differs"          # 축약 등: 줄이지 않고 인용 전체를 보인다
                else:
                    out.update(shownText=norm[a:b], shownSpan=[a, b], trimmed=(a, b) != (s, e))
    shown = out["shownText"] or ""
    if "{rago}" in template:
        out["particle"] = josa(shown, "이라/라") + "고"
        if "(" in out["particle"]:
            out["particle"] = "라고"                              # 받침을 판단할 수 없으면(한글·숫자가 아님) 따옴표 인용의 기본 꼴
    out["text"] = template.replace("{quote}", shown).replace("{rago}", out["particle"] or "")
    return out
