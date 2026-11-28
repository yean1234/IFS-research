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
CP15(프롬프트 0.1.1): ① 위기·확인 판정 검사는 캐시보다 먼저(판정이 서면 캐시 채택값도 돌려주지 않음) ② 참여자 자료는 구분 표시
(dataFence) 안에 넣고 그 안은 자료이며 지시가 아니라고 적음(원문은 바꾸지 않음 — 표시 쪽 번호를 골라 겹치지 않게) ③ 형태 낱말 영어
검사는 tools/gen3d/prompts.english_shape_reasons 하나(목록 shared/lexicon/shape_english_block.v0.json, 생성 직전 재검증과 같은 함수).

검증(하나라도 실패하면 그 항목만 버림, 사유 코드를 남김):
  malformed · slot_not_allowed · slot_filled · value_not_allowed · evidence_pair_not_allowed · quote_mismatch ·
  span_not_token_aligned · quote_too_long · span_covered(매퍼가 쓴 구간) · span_excluded(매퍼가 뺀 구간·교차 감각 등 장면 값이 아니라고 판정한 낱말) ·
  negated · context_sentence(지난 일·상황 문장) · simile(비유 원천의 속성) · simile_of_predicate · position_location · position_size ·
  emotion_or_sense_word · body_word · no_noun · english_format · english_banned · english_color_size · english_non_shape ·
  non_meshable · korean_banned · multi_slot_quote(같은 구간을 두 슬롯에) · slot_duplicate · over_limit
  (CP15 2차, VALIDATOR_RULES 0.2.0) past_or_former · reported_speech · hypothetical(인용이 든 문장 전체) ·
  no_attribute_word(속성 슬롯에 그 속성을 말한 낱말이 없음) · form 슬롯도 korean_banned·non_meshable(문장 안 명사)
  (0.3.0) cross_sentence(두 문장에 걸친 인용) · 어미 변형·사람 표기 보충 · 슬롯별 속성 낱말
"""
from __future__ import annotations

import copy
import hashlib
import json
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

# ── 검증기 규칙 판(CP15 2차, 2026-11-28). 프롬프트 판과 따로 움직인다. 기록 validatorRules와 캐시 키에 들어간다 ─────
VALIDATOR_RULES = "ifs-llm-fill-validator/0.3.0"   # 0.3.0: CP15 재검토 2(어미 변형·사람 표기·슬롯별 속성 낱말·두 문장 인용)
# 문장 틀(인용 구간이 든 문장 전체를 본다 — 표지가 인용 밖 앞뒤에 있어도). 매퍼의 _context_sentences는 '~던 장면' 같은
# 회상 문장만 잡아 지난 일·남의 말·가정을 거르지 못한다(G77 실측). 매퍼는 그대로 두고 이 검증기에만 더 엄격하게 얹는다.
_PAST_EP = ("었", "았", "였", "더")               # 선어말 어미에 이 글자가 있으면 지난 일('이었어요'·'했었어요'·'~더라')
_PAST_EXEMPT_VERBS = frozenset({"생기", "닮"})    # '~처럼 생겼어요'·'닮았어요'는 지금 모양을 말하는 관용
_FORMER_WORDS = frozenset({"예전", "원래", "처음", "아까", "옛날", "과거", "어릴", "그때", "당시", "이전", "지난번"})
_CURRENT_WORDS = frozenset({"지금", "이제", "현재", "요즘", "오늘"})   # 인용 절에 있으면 지난 일 표지를 보지 않음('~였는데 지금은 회색')
_REPORT_EC = frozenset({"라고", "다고", "자고", "냐고", "이라고"})
_REPORT_EF = frozenset({"대", "래", "대요", "래요"})
# 0.3.0: 어미 변형(Kiwi가 한 덩이로 내는 것) — '라면서요'(EF)·'라던데'(EC)·'다던데요'(EF)·'라더라' 등은 앞부분으로 본다
_REPORT_ENDING_PREFIX = ("라고", "다고", "자고", "냐고", "라면서", "다면서", "라던", "다던", "라더", "다더", "래", "대")
_HYPO_ENDING_PREFIX = ("ᆯ까", "을까", "ㄹ까", "ᆯ지", "을지", "ㄹ지")   # '쑥색일까 봐요'·'쑥색일지도 몰라요'
_REPORT_ETM = frozenset({"라는", "다는"})
_REPORT_VERBS = frozenset({"말하", "듣", "그러"})
_OTHER_PERSON = frozenset({"친구", "엄마", "아빠", "어머니", "아버지", "사람", "남", "남들", "누구", "누군가", "선생님", "동생",
                           "언니", "오빠", "형", "누나", "가족", "부모", "부모님", "할머니", "할아버지", "의사", "상담사", "선배",
                           "후배", "동료", "애인", "남편", "아내", "그", "그녀", "걔", "쟤", "얘"})
_HYPO_EC = frozenset({"면", "으면", "라면", "다면", "이라면", "거든", "려면", "으려면"})
_HYPO_MAG = frozenset({"아마", "아마도", "혹시", "만약", "만일"})
_HYPO_VERBS = frozenset({"싶", "바라", "원하"})
_HYPO_ETM = frozenset({"ᆯ", "을", "ㄹ"})
_HYPO_NNB = frozenset({"것", "거", "수", "지", "듯"})
# 속성 슬롯은 인용 안에 그 슬롯의 속성을 직접 말한 낱말이 있어야 한다(사물 명사·상관없는 낱말·다른 속성 낱말에서 짐작한 값은
# 원칙 2 위반). 0.3.0: 슬롯마다 그 슬롯의 사전 어근(layer1_lexicon 해당 범주)과 그 슬롯에 고유한 어근만 받는다(형용사면 통과 X).
_ATTR_SLOTS = ("color", "brightness", "opacity", "texture", "size", "motion")
_COLOR_TAILS = ("색", "빛")
_COLOR_GENERIC = frozenset({"색", "빛", "색깔", "빛깔", "색상", "색채", "색감", "빛살"})   # 색 이름 없이 '색깔'만이면 기각
_COLOR_ADJ_TAIL = ("렇", "랗", "얗", "멓")
_COLOR_ADJ_IN = ("스름", "스레", "불그", "푸르", "누르", "붉", "희끄", "거무", "검붉", "푸릇", "누릇", "노릇")
_NOT_COLOR_ADJ = frozenset({"그렇", "이렇", "저렇", "어떻", "아무렇"})
_SLOT_ROOTS = {      # 낱말(형태·기본형)이 이것으로 시작하면 그 슬롯의 속성 낱말(내용 품사만)
    "brightness": ("밝", "어둡", "어두", "환하", "환해", "캄캄", "깜깜", "컴컴", "침침", "어둑", "어슴푸레", "희미", "흐릿",
                   "눈부시", "빛나", "반짝", "번쩍", "칙칙"),
    "opacity": ("투명", "불투명", "비치", "비쳐", "비춰", "맑", "탁하", "뿌옇", "뿌연", "흐리", "말갛", "말간"),
    "texture": ("거칠", "매끈", "매끄럽", "미끈", "미끄럽", "반들", "반질", "반지르르", "맨들", "보송", "보들", "부드럽",
                "꺼끌", "까끌", "까칠", "꺼칠", "까슬", "거슬", "울퉁", "우툴", "오돌", "오톨", "도톨", "올록", "끈적", "폭신",
                "푹신", "말랑", "몰랑", "푸석", "버석", "까실"),
    "size": ("커다랗", "조그맣", "자그맣", "조그마", "자그마", "쪼그맣", "쪼끄맣", "큼직", "커다란", "조그만", "거대", "산만",
             "작달막", "자그만"),
    "motion": ("흔들", "떨", "떠다니", "떠돌", "가라앉", "움직이", "굴러", "구르", "출렁", "꿈틀", "일렁", "두근", "뛰",
               "맴돌", "흘러", "흐르", "꿀렁", "울렁", "들썩", "요동", "휘청", "부들", "파르르", "둥둥", "빙빙", "뱅글", "빙글",
               "데굴", "대굴", "떼굴", "꼼지락", "꿈지럭", "들썩", "펄럭", "팔랑", "너울", "넘실", "쿵쾅", "콩닥", "벌렁",
               "가물", "하늘하늘", "살랑"),
}
_SLOT_EXACT = {"size": frozenset({"크", "작", "커다랗", "조그맣"}), "motion": frozenset({"돌", "뜨"})}   # 짧은 어근은 기본형이 같을 때만
_ROOT_TAGS = ("VA", "VV", "XR", "MAG", "NNG")
_MEASURE = frozenset({"만", "만큼", "정도"})
_ATTR_CATS = {"color": ("color", "saturation"), "brightness": ("brightness",), "opacity": ("opacity",),
              "texture": ("texture",), "size": ("size",), "motion": ("movement",)}
# 0.3.0: 형태 쪽 사람 낱말 보충(높임말·준말·호칭·대명사, 기존 제외 목록에 없는 표기). 형태소 분석이 명사로 내지 않는 것('아이' →
# 감탄사+관형사, '분' → 동사)도 어절 표면이 이 낱말(+조사)이면 막는다
_PERSON_EXTRA = frozenset({"애기", "애", "그분", "이분", "저분", "분", "아이", "아가씨", "총각", "청년", "인물", "얼굴", "사람들",
                           "남자애", "여자애", "아이들", "애들", "언니", "오빠", "누나", "형", "동생", "친구", "선생님", "사람얼굴"})
_EOJ_TAILS = ("", "이", "가", "은", "는", "을", "를", "의", "도", "만", "처럼", "같이", "같은", "모양", "모습", "형상", "이에요",
              "예요", "이고", "고", "랑", "이랑", "하고", "들")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class FillPrompt:
    """고정 프롬프트 파일(판·status draft). 파일 바이트 해시를 기록·캐시 키에 쓴다."""

    def __init__(self, name: str = "llm_fill.v0.1.1.json"):
        p = Path(name)
        self.path = p if p.is_absolute() else PROMPT_DIR / name
        raw = self.path.read_text(encoding="utf-8")
        self.sha256 = sha256_text(raw)
        self.data = json.loads(raw)
        self.version = self.data["promptVersion"]
        self.slots: dict = self.data["slots"]
        self.shape = self.data["shapeNoun"]
        if "englishBlockLexicon" not in self.shape or "dataFence" not in self.data:
            raise ValueError(f"{self.path.name}: 0.1.1 이상이 아님(englishBlockLexicon·dataFence 없음) — 0.1.0은 기록으로만 남긴 판(CP15)")
        eb = shared("lexicon", self.shape["englishBlockLexicon"]).read_text(encoding="utf-8")
        self.english_block = {"file": self.shape["englishBlockLexicon"], "sha256": sha256_text(eb),
                              "version": json.loads(eb)["version"]}
        self.fence = self.data["dataFence"]
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
        # 속성 사전의 어근(슬롯별): 인용 안에 이 어근이 있으면 그 속성을 말한 낱말로 본다
        self.attr_lemmas = {slot: frozenset(e["lemma"] for e in lex["entries"] if e.get("category") in cats_)
                            for slot, cats_ in _ATTR_CATS.items()}

    def info(self) -> dict:
        return {"promptId": self.data["promptId"], "promptVersion": self.version, "file": self.path.name,
                "promptSha256": self.sha256, "status": self.data["status"], "englishBlock": dict(self.english_block)}


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
FENCE_MAX_TRIES = 100000


def data_fence(prompt: FillPrompt, parts: list[str], max_tries: int | None = None) -> tuple[int, str, str] | None:
    """참여자 자료를 감쌀 시작·끝 표시. 표시와 같은 글자가 프롬프트에 들어가는 어떤 글(parts — 구분 안팎의 자료·슬롯 안내·
    템플릿·system)에 있으면 번호를 올린다(원문은 바꾸지 않음 → charSpan 그대로). 같은 자료 → 같은 번호.
    한 번호를 막으려면 그 표시가 글에 한 번은 나와야 하므로, '<<<' 수 + 1번 안에 반드시 찾는다. 못 찾으면 None(부르지 않고 기록)."""
    blob = "\n".join(parts)
    limit = blob.count("<<<") + 2 if max_tries is None else max_tries
    for n in range(min(limit, FENCE_MAX_TRIES)):
        o, c = prompt.fence["open"].format(n=n), prompt.fence["close"].format(n=n)
        if o not in blob and c not in blob:
            return n, o, c
    return None


def build_user(prompt: FillPrompt, norm: str, doc, spec: dict, slots: list[str], spans: dict) -> str | None:
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
    data = {"text": norm, "eojeols": "\n".join(eoj) or "(없음)", "filled": "\n".join(filled) or "(없음)",
            "excluded": "\n".join(excl) or "(없음)", "unmatched": "\n".join(unm) or "(없음)"}
    slots_txt = "\n".join(open_lines) or "(없음)"
    fence = data_fence(prompt, [*data.values(), slots_txt, prompt.data["userTemplate"], prompt.data["system"]])
    if fence is None:
        return None
    _, fo, fc = fence
    return prompt.data["userTemplate"].format(openSlots=slots_txt, fenceOpen=fo, fenceClose=fc, **data)


# ── 검증 ─────────────────────────────────────────────────────────────────────
class _Ctx:
    def __init__(self, prompts_mod, norm: str, spec: dict, table: dict, prompt: FillPrompt, slots: list[str]):
        self.pm, self.norm, self.spec, self.table, self.prompt, self.slots = prompts_mod, norm, spec, table, prompt, slots
        self.rt = prompts_mod._shape_runtime()
        eb = prompts_mod.english_block()
        if eb.file != prompt.english_block["file"] or eb.sha256 != prompt.english_block["sha256"]:
            raise ValueError(f"영어 금지 목록이 다름: 프롬프트 {prompt.english_block['file']} ≠ 생성 규칙 {eb.file}")
        toks = self.rt.analyzer.tokens(norm)
        self.doc = self.rt.Doc(norm, toks)
        self.toks = toks
        self.context = self.rt.excluder._context_sentences(self.doc)
        self.neg_spans = [tuple(n["_provenance"]["charSpan"]) for n in spec.get("_negated") or []
                          if (n.get("_provenance") or {}).get("charSpan")]
        self.spans = mapper_spans(spec, prompts_mod, prompt)
        self.korean_block = _korean_block(self.rt)
        self.starts = {t.start for t in toks}
        self.ends = {t.end for t in toks}
        for a, b in self.doc.eojeols:
            self.ends.add(toks[b].end)


def _korean_block(rt) -> dict:
    """형태 자리에 오면 막는 한국어 명사 → 사유. 기존 제외 판정(base_shapes.v1 excluded·noAsset, G45–G51)과 형태 프롬프트
    보충 목록(shape_prompt_en blocked: 사람·동물·안개·불꽃·빛, G62·G75)을 그대로 다시 쓴다."""
    out = {}
    bs = rt.excluder.bs
    for cat in (bs.get("excluded") or {}).get("categories", {}).values():
        for w in list(cat.get("words") or []) + list((cat.get("added") or {}).get("words") or []) + list(cat.get("compounds") or []):
            out[w] = "korean_banned"
    for cat in (bs.get("noAsset") or {}).values():
        if isinstance(cat, dict):
            for w in list(cat.get("words") or []) + list((cat.get("added") or {}).get("words") or []):
                out[w] = "korean_banned"
    for w, kind in rt.block_kind.items():
        out[w] = "non_meshable" if kind == "nonMeshable" else "korean_banned"
    for w in _PERSON_EXTRA:
        out.setdefault(w, "korean_banned")
    return out


def _korean_block_reasons(ctx, idx: list[int]) -> list[str]:
    """(0.3.0) 인용과 그 문장의 명사·대명사, 그리고 어절 표면(형태소 분석이 명사로 내지 않는 '아이'·'분')을 본다."""
    toks, doc = ctx.toks, ctx.doc
    sent = _sentence_ids(ctx, idx)
    why = []
    for k in sent:
        if toks[k].base_tag in ("NNG", "NNP", "NP") and toks[k].form in ctx.korean_block:
            why.append(ctx.korean_block[toks[k].form])
    for e in sorted({doc.eoj[k] for k in sent}):
        a, b = doc.eojeols[e]
        surf = ctx.norm[toks[a].start:toks[b].end].rstrip(".,!?~…")
        for w in _PERSON_EXTRA:
            if surf.startswith(w) and surf[len(w):] in _EOJ_TAILS:
                why.append("korean_banned")
    return why


def _quote_sentences(ctx, idx: list[int]) -> set[int]:
    """인용 토큰의 문장 번호(문장 부호 토큰은 뺌 — Kiwi는 문장 끝 마침표를 다음 문장 번호로 매긴다)."""
    ss = {ctx.doc.sent[k] for k in idx if not ctx.toks[k].base_tag.startswith("S")}
    return ss or {ctx.doc.sent[k] for k in idx}


def _sentence_ids(ctx, idx: list[int]) -> list[int]:
    ss = _quote_sentences(ctx, idx)
    return [k for k in range(len(ctx.toks)) if ctx.doc.sent[k] in ss and not (
        ctx.toks[k].base_tag.startswith("S") and ctx.toks[k].base_tag not in ("SSO", "SSC"))]


def _prev_pred(toks, k: int):
    for m in range(k - 1, -1, -1):
        if toks[m].base_tag in ("VV", "VA", "VX", "VCP", "XSV", "XSA"):
            return toks[m]
        if toks[m].base_tag.startswith(("N", "S")):
            return None
    return None


def frame_reasons(ctx, idx: list[int]) -> list[str]:
    """(CP15 2차) 인용이 든 문장이 지난 일·남의 말·가정이면 사유. 표지가 인용 밖(같은 문장 앞뒤)에 있어도 본다.
    past_or_former · reported_speech · hypothetical. 막는 쪽으로 넉넉하다('보면 쑥색이에요'의 '면'도 가정으로 본다)."""
    toks, doc = ctx.toks, ctx.doc
    sent = _sentence_ids(ctx, idx)
    clauses = {doc.clause[k] for k in idx}
    now = any(toks[k].form in _CURRENT_WORDS for k in sent if doc.clause[k] in clauses)
    past = report = hypo = False
    for n, k in enumerate(sent):
        t = toks[k]
        f, tag = t.form, t.base_tag
        nxt = toks[sent[n + 1]] if n + 1 < len(sent) else None
        if tag == "EP" and any(c in f for c in _PAST_EP):
            pv = _prev_pred(toks, k)
            if pv is None or pv.lemma not in _PAST_EXEMPT_VERBS:
                past = True
        elif tag == "ETM" and f == "던":
            past = True
        elif tag in ("NNG", "NNP", "MAG") and f in _FORMER_WORDS:
            past = True
        elif tag == "NNG" and f == "전" and nxt is not None and nxt.base_tag == "JKB":
            past = True                                       # '전에는'
        if (tag == "EC" and f in _REPORT_EC) or (tag == "EF" and f in _REPORT_EF) or (tag == "ETM" and f in _REPORT_ETM) \
                or tag == "JKQ" or (tag in ("EC", "EF") and f.startswith(_REPORT_ENDING_PREFIX)):
            report = True                                     # JKQ: 따옴표 뒤 '라고'("쑥색이에요"라고 했어요)
        elif tag in ("VV", "VX") and t.lemma in _REPORT_VERBS:
            report = True
        elif tag in ("NNG", "NNP", "NP") and f in _OTHER_PERSON:
            report = True
        if (tag == "EC" and f in _HYPO_EC) or (tag == "EP" and "겠" in f) or (tag == "MAG" and f in _HYPO_MAG) \
                or (tag in ("EC", "EF") and f.startswith(_HYPO_ENDING_PREFIX)):
            hypo = True
        elif tag in ("VV", "VX") and t.lemma in _HYPO_VERBS:
            hypo = True
        elif tag == "ETM" and f in _HYPO_ETM and nxt is not None and nxt.base_tag == "NNB" and nxt.form in _HYPO_NNB:
            hypo = True                                       # '쑥색일 것 같아요'·'~ㄹ 수도'·'~ㄹ지도'
    why = []
    if past and not now:
        why.append("past_or_former")
    if report:
        why.append("reported_speech")
    if hypo:
        why.append("hypothetical")
    return why


def has_attribute_word(ctx, slot: str, idx: list[int], j: int) -> bool:
    """속성 슬롯: 인용 안에 그 슬롯의 속성을 직접 말한 낱말이 있는가(0.3.0: 슬롯별로 좁힘, 규칙·사전만).
    ① 그 슬롯 범주의 사전 어근(layer1_lexicon) ② 그 슬롯에 고유한 어근(_SLOT_ROOTS, 내용 품사만) ③ 색은 '색 이름 + 색·빛'
    꼴 명사('쑥색'·'잿빛', 매퍼 사전 밖 색 이름도 — G77이 열어 둔 대상)나 색 형용사. '색깔'·'빛깔'만이면 기각
    ④ 크기는 견줌 표현('집채만'·'주먹만큼'). 다른 슬롯의 형용사('길어요' → 밝기)는 받지 않는다."""
    toks = ctx.toks
    lem = ctx.prompt.attr_lemmas.get(slot, frozenset())
    q = [toks[k] for k in idx]
    if any(t.lemma in lem and t.base_tag in _ROOT_TAGS and not (t.base_tag == "NNG" and len(t.lemma) < 2) for t in q):
        return True                                       # 한 글자 명사('돌'=움직임 사전의 '돌다'와 같은 글자)는 사전 일치로 보지 않음
    roots, exact = _SLOT_ROOTS.get(slot, ()), _SLOT_EXACT.get(slot, frozenset())
    if any(t.base_tag in _ROOT_TAGS and ((t.lemma in exact and t.base_tag != "NNG") or (roots and (t.lemma.startswith(roots) or t.form.startswith(roots))))
           for t in q):
        return True
    if slot == "color":
        for n, k in enumerate(idx):
            t = toks[k]
            if t.base_tag in _NOUN_TAGS:
                prev = toks[idx[n - 1]] if n > 0 else None
                glued = prev is not None and prev.base_tag in _NOUN_TAGS and prev.end == t.start \
                    and prev.form not in _COLOR_GENERIC
                if t.form not in _COLOR_GENERIC and t.form.endswith(_COLOR_TAILS + ("색깔", "빛깔")) and len(t.form) >= 2:
                    return True                                   # '쑥색'·'겨자색'·'잿빛'·'살구빛깔'
                if t.form in _COLOR_TAILS + ("색깔", "빛깔") and glued:
                    return True                                   # Kiwi가 '쑥/색'으로 나눈 경우
            if t.base_tag in ("VA", "XR") and t.lemma not in _NOT_COLOR_ADJ and (
                    (len(t.lemma) >= 2 and t.lemma.endswith(_COLOR_ADJ_TAIL)) or any(x in t.lemma for x in _COLOR_ADJ_IN)):
                return True
        return False
    if slot == "size":
        after = toks[j + 1] if j + 1 < len(toks) and ctx.doc.sent[j + 1] == ctx.doc.sent[j] else None
        return any(t.form in _MEASURE and t.base_tag in ("JX", "JKB", "NNB") for t in q) \
            or (after is not None and after.form in _MEASURE and after.base_tag in ("JX", "JKB", "NNB"))
    return False


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
    why.extend(frame_reasons(ctx, idx))                          # 지난 일·남의 말·가정(문장 전체, CP15 2차)
    if len(_quote_sentences(ctx, idx)) > 1:
        why.append("cross_sentence")                              # 두 문장에 걸친 인용(0.3.0)
    content = [toks[k] for k in idx if toks[k].base_tag in _CONTENT_TAGS]
    if any(t.lemma in P.blocked_lemmas for t in content):
        why.append("emotion_or_sense_word")
    nouns = [k for k in idx if toks[k].base_tag in _NOUN_TAGS]
    after = toks[j + 1] if j + 1 < len(toks) and doc.sent[j + 1] == doc.sent[j] else None
    simile_inside = any(toks[k].form in _SIMILE_FORMS or (toks[k].form == "같" and toks[k].base_tag == "VA") for k in idx)
    simile_after = after is not None and (after.form in _SIMILE_FORMS or (after.form == "같" and after.base_tag == "VA"))
    if slot in ("form", SHAPE_SLOT):
        # 형태 쪽(형태 종류·형태 낱말): 인용과 그 문장의 명사·대명사·어절이 사람·동물·제외 범주·안개·불꽃이면 버림
        why.extend(_korean_block_reasons(ctx, idx))
    if slot in _ATTR_SLOTS and not has_attribute_word(ctx, slot, idx, j):
        why.append("no_attribute_word")                           # 사물 명사·상관없는 낱말에서 속성을 짐작하지 않음
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
    # 영어: 생성 직전 재검증(prompts._llm_head)과 같은 함수·같은 목록(소문자화·하이픈 정리·복수형 어간·어근 포함, CP15-1)
    why.extend(ctx.pm.english_shape_reasons(value))
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
    key = f"{sha256_text(norm)}|{digest}|{prompt.version}|{prompt.sha256}|{prompt.english_block['sha256']}|{VALIDATOR_RULES}"
    cache = session.llm_fill_cache
    # 위기·확인 판정은 캐시보다 먼저 본다(CP15-2): 앞서 성공한 결과가 캐시에 있어도 판정이 서면 채택값을 돌려주지 않고 부르지도 않는다
    flag = session_flag(session)
    if key in cache and not flag:
        rec = copy.deepcopy(cache[key])
        rec["cached"] = True
        return rec
    rec = {"version": LLM_FILL_VERSION, "validatorRules": VALIDATOR_RULES, "status": None, "skipReason": None, "error": None,
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

    if flag:
        # 캐시의 앞 결과(원시 응답·채택값)는 분석용으로 그대로 두고, 건너뜀은 따로 남긴다(CP15 재검토)
        rec.update(status="skipped", skipReason="session_flagged", error=flag,
                   cachedEarlier=key in cache)
        skips = getattr(session, "llm_fill_skips", None)
        if isinstance(skips, list):
            skips.append(copy.deepcopy(rec))
        return rec
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
        if user is None:                                 # 자료와 겹치지 않는 구분 표시를 못 고름 → 부르지 않음(확정은 막지 않음)
            return done("skipped", skipReason="fence_unavailable", seconds=round(time.monotonic() - t0, 2))
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
