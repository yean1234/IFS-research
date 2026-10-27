"""결정론적 검증기 — 매 턴, 질문이 참여자에게 나가기 전에 실행 (「IFS 이론이란?」 4절).

| 검사 | 규칙 | 실패 시 |
| V1 스키마  | JSON 파싱, enum·길이, move와 필드의 짝 | 재생성 |
| V2 단계    | stage == 컨트롤러 단계, 이 단계에서 허용된 질문 틀 | 재생성 |
| V3 인용    | anchor_quote·작은따옴표 인용이 참여자 발화에 글자 그대로 있음(공백 무시) | 재생성 |
| V4 단일 질문 | '?' 정확히 1개, 물음표로 끝남, 80자 이하 | 재생성 |
| V5 어휘 누출 | 1층 사전 어휘(색·크기·질감·감정명·차원어 등)가 질문에 있는데 참여자 발화에는 없음 | 재생성 |
|   (확장)   | 엄격 모드: 질문 틀에 없는 새 내용어(돌, 차갑 …)가 따옴표 밖에 있음 | 재생성 |
| V6 금지 패턴 | 예를 들·이를테면·아니면·혹은·왜·언제부터·무슨 일·것 같네요 + 규칙 5–7에서 뽑은 추가 표현 | 재생성 |
| V7 질문 틀 일치 | where면 '어디', like_what이면 '무엇 같' 같은 표지어 | 재생성 |
| V8 출력 가드 | 가드 모델·키워드 판정이 안전 | 재생성 없이 고정 문구 |
| V9 깊이 제한(확장, L5) | 기억·관계 장면 표지(어릴 때, 엄마, 교실 …)를 인용해 파고들지 않음 | 재생성 |

재생성은 최대 2회. 그래도 실패하면 고정 대체 문구를 낸다(controller).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import jsonschema

from .korean import Analyzer, count_questions, mask_quoted, normalize, quoted_spans, squash
from .lexicon import Lexicon
from .protocol import Protocol
from .safety import Guard, SafetyLexicon

# V6 — (id, 정규식, 출처)
BANNED_PATTERNS: list[tuple[str, str, str]] = [
    ("for_example", r"예를\s*들", "spec"),
    ("such_as", r"이를테면", "spec"),
    ("or_else", r"아니면", "spec"),
    ("or", r"혹은", "spec"),
    ("why", r"왜", "spec"),
    ("since_when", r"언제부터", "spec"),
    ("what_happened", r"무슨\s*일", "spec"),
    ("seems_interpret", r"것\s*같네요", "spec"),
    # 규칙 2: 선택지
    ("or_2", r"또는|거나|든지", "rule2"),
    ("perhaps", r"혹시", "rule2: 설계 노트 §6의 금지 예 '혹시 회색인가요?'"),
    # 규칙 5: 왜·원인·과거·기억
    ("when", r"언제", "rule5"),
    ("past", r"기억|예전|옛날|어릴|어렸|과거|그때|그\s*때", "rule5"),
    ("cause", r"원인|이유|때문", "rule5"),
    # 규칙 6: 공감·칭찬·위로·감정 해석
    ("empathy", r"힘드(셨|시|시겠)|괜찮(아요|으실|을)|마음이\s*아프|안타깝|공감|이해(해요|가\s*돼|합니다)|응원|수고", "rule6"),
    ("praise", r"잘\s*(하고|하셨|해\s*주)|좋(아요|네요|습니다)|훌륭|대단|고마|감사", "rule6"),
    ("reflective", r"군요|네요", "rule6"),
    # 규칙 7: 자기 노출
    ("self_disclosure", r"저도|저는|제가|제\s*생각|제\s*경험|나도", "rule7"),
    # 해석·진단·IFS 용어로 이름 붙이기 (규칙 1·6, 노션: 면담자는 part를 이름 붙이거나 해석하지 않는다)
    ("diagnosis", r"증상|진단|트라우마|상처|치료|상담|우울증|장애", "rule6"),
    ("ifs_label", r"부분|파트|part|보호자|추방자|관리자|소방관|참자기|셀프|내면\s*아이|내면의\s*아이", "rule1"),
    ("advice", r"해\s*보세요|보세요|하세요|방법|시도", "rule: 조언 금지"),
]
_BANNED = [(i, re.compile(p, re.I), s) for i, p, s in BANNED_PATTERNS]

# V5 엄격 모드: 질문 틀 6개와 조사 처리에 쓰이는 말
TEMPLATE_ALLOW = {
    "관계", "사이", "다음", "그다음", "말씀", "방금", "지금", "더", "마치", "좀", "조금", "또",
    "있", "없", "같", "되", "대하", "어떻", "하", "말하", "떠오르", "알아차리", "그리고", "쯤", "어디쯤",
}

REASON_TEXT = {
    "V1": "출력이 JSON 스키마에 맞지 않음",
    "V1:hold_without_risk_signal": "move가 hold인데 risk_signal이 none — 위험 신호가 없으면 ask 또는 ready_to_advance",
    "V1:anchor_required": "ask인데 anchor_quote가 비어 있음",
    "V2": "단계나 질문 틀이 컨트롤러와 맞지 않음",
    "V2:stage_mismatch": "단계(stage)가 컨트롤러의 현재 단계와 다름",
    "V2:template_not_allowed": "이 단계에서 쓸 수 없는 질문 틀",
    "V3": "인용이 참여자 말과 글자까지 같지 않음",
    "V3:anchor_not_in_utterance": "anchor_quote가 질문 문장 안에 없음",
    "V3:relationship_needs_two_quotes": "relationship 틀은 참여자 표현 두 개를 작은따옴표로 인용해야 함",
    "V3:anchor_too_long": "인용이 너무 김 — 참여자 말에서 한 낱말이나 짧은 구(3어절 이하)만 인용",
    "V3:anchor_is_sentence": "여러 어절 문장을 통째로 인용함 — 인용 후보의 낱말·짧은 구 하나만 인용",
    "V4": "질문 형식 위반",
    "V4:question_count": "물음표가 정확히 하나가 아님(질문은 하나만)",
    "V4:not_question_end": "물음표로 끝나지 않음",
    "V4:too_long": "80자를 넘음",
    "V5": "참여자가 쓰지 않은 말을 꺼냄",
    "V5:leak": "참여자가 쓰지 않은 묘사어·차원어를 씀",
    "V5:novel": "질문 틀에 없는 새 말을 씀",
    "V6": "금지 표현이 있음",
    "V7": "고른 질문 틀과 문장이 맞지 않음",
    "V7:template_literal": "질문 틀의 '은(는)'·'{X}'를 그대로 씀 — 받침에 맞는 조사 하나만",
    "V8": "출력 가드가 안전하지 않다고 판단",
    "V9": "기억·관계 장면을 인용해 깊이 들어감(L5)",
    "V9:depth_context": "기억·과거 장면을 말한 문장 속 말을 인용함(L5) — 지금 떠오른 것의 묘사어를 인용",
    "LLM": "LLM 호출 오류",
}


def describe(reason: str) -> str:
    """사람이 읽는 사유. 'V5:leak:차갑' → "V5 참여자가 쓰지 않은 묘사어·차원어를 씀: '차갑'"."""
    parts = reason.split(":")
    code = parts[0]
    sub = f"{code}:{parts[1]}" if len(parts) > 1 else code
    base = REASON_TEXT.get(sub) or REASON_TEXT.get(code, reason)
    detail = ":".join(parts[2:]) if sub in REASON_TEXT else (parts[-1] if len(parts) > 1 else "")
    return f"{code} {base}" + (f": '{detail}'" if detail and detail != "none" else "")


@dataclass
class TurnContext:
    stage: str
    allowed_templates: list[str]
    participant_texts: list[str]
    last_participant_text: str
    last_participant_guard_model: dict | None = None   # 입력 검사 때의 가드 모델 판정(V8 비교용)


@dataclass
class CheckResult:
    passed: bool
    reasons: list[str]
    parsed: dict | None = None
    hard_fail: bool = False            # V8 — 재생성하지 않고 고정 문구
    l2_signal: bool = False            # risk_signal/hold — controller가 확인 문구로
    guard: dict | None = None
    notes: list[str] = field(default_factory=list)

    def to_log(self) -> dict:
        return {"passed": self.passed, "reasons": self.reasons, "hardFail": self.hard_fail,
                "l2Signal": self.l2_signal, "guard": self.guard, "notes": self.notes}


class Validator:
    def __init__(self, protocol: Protocol, lexicon: Lexicon, safety: SafetyLexicon, analyzer: Analyzer,
                 schema: dict, guard: Guard | None = None, strict_novel_content: bool = True,
                 depth_anchor_block: bool = True, check_output: bool = True, max_anchor_eojeol: int = 3):
        self.protocol, self.lexicon, self.safety, self.analyzer = protocol, lexicon, safety, analyzer
        self.schema = schema
        self._schema_validator = jsonschema.Draft202012Validator(schema)
        self.guard = guard
        self.strict = strict_novel_content
        self.depth_block = depth_anchor_block
        self.check_output = check_output
        self.max_anchor_eojeol = max_anchor_eojeol

    def check(self, raw: str, ctx: TurnContext) -> CheckResult:
        # ── V1 ──
        try:
            out = json.loads(raw)
        except Exception:
            return CheckResult(False, ["V1:json_parse"])
        errors = sorted(self._schema_validator.iter_errors(out), key=lambda e: list(e.path))
        if errors:
            return CheckResult(False, [f"V1:schema:{'/'.join(map(str, e.path)) or 'root'}:{e.validator}" for e in errors[:3]], parsed=None)
        out = {k: (normalize(v) if isinstance(v, str) else v) for k, v in out.items()}

        # L2: 위험 신호는 보조 신호. 질문을 검사하지 않고 controller가 확인 문구로 넘긴다.
        if out["risk_signal"] != "none":
            return CheckResult(True, [], parsed=out, l2_signal=True)
        if out["move"] == "hold":
            # 규칙 11은 risk_signal과 hold를 함께 쓴다. 신호 없는 hold는 잘못된 출력으로 보고 다시 만든다
            # (참여자 발화는 이미 L1 가드를 통과했다). gemma4:e4b 실험에서 실제로 나왔다.
            return CheckResult(False, ["V1:hold_without_risk_signal"], parsed=out)

        reasons: list[str] = []
        move, template = out["move"], out["template"]
        notes: list[str] = []
        if move == "ask":
            if template == "none" or not out["utterance"]:
                reasons.append("V1:ask_without_template_or_utterance")
            if template not in ("then_what", "none") and not out["anchor_quote"]:
                reasons.append("V1:anchor_required")
        elif out["utterance"]:
            notes.append(f"move={move}인데 utterance가 있음(무시함)")

        # ── V2 ──
        if out["stage"] != ctx.stage:
            reasons.append(f"V2:stage_mismatch:{out['stage']}")
        if move == "ask" and template not in ctx.allowed_templates:
            reasons.append(f"V2:template_not_allowed:{template}")

        if move != "ask" or reasons:
            return CheckResult(not reasons, reasons, parsed=out, notes=notes)

        utt, anchor = out["utterance"], out["anchor_quote"]
        participant_all = "\n".join(ctx.participant_texts)
        p_squashed = [squash(t) for t in ctx.participant_texts]

        def verbatim(s: str) -> bool:  # 한 발화 안에 글자 그대로(공백 무시) 있는가
            s = squash(s)
            return bool(s) and any(s in p for p in p_squashed)

        # ── V3 ──
        if anchor and not verbatim(anchor):
            reasons.append(f"V3:anchor_not_verbatim:{anchor}")
        quotes = quoted_spans(utt)
        for q in quotes:
            if not verbatim(q):
                reasons.append(f"V3:quote_not_verbatim:{q}")
        if anchor and squash(anchor) not in squash(utt):
            reasons.append("V3:anchor_not_in_utterance")
        if template == "relationship" and len({squash(q) for q in quotes}) < 2:
            reasons.append("V3:relationship_needs_two_quotes")
        # (확장) 인용은 참여자의 '단어'여야 한다. 문장 통째 되풀이는 clean 질문이 아니고,
        # 가드 모델도 조롱처럼 읽는다(gemma4:e4b 실험에서 S2로 판정됨).
        for q in dict.fromkeys([anchor, *quotes]):
            if not q:
                continue
            n = len(q.split())
            if self.max_anchor_eojeol and n > self.max_anchor_eojeol:
                reasons.append(f"V3:anchor_too_long:{q}")
                break
            toks = [t for t in self.analyzer.tokens(q) if t.base_tag not in ("SF", "SP", "SS", "SE", "SW")]
            if n >= 2 and toks and toks[-1].base_tag == "EF":   # '가슴이 조여요'처럼 여러 어절 문장. '조여요' 한 어절은 허용
                reasons.append(f"V3:anchor_is_sentence:{q}")
                break

        # ── V4 ──
        n_q = count_questions(utt)
        if n_q != 1:
            reasons.append(f"V4:question_count:{n_q}")
        if not utt.rstrip().endswith("?"):
            reasons.append("V4:not_question_end")
        if len(utt) > 80:
            reasons.append(f"V4:too_long:{len(utt)}")

        # ── V5 ──
        p_keys = self.lexicon.keys(participant_all)
        for h in self.lexicon.hits(utt):
            if h.entry.key not in p_keys:
                reasons.append(f"V5:leak:{h.entry.lemma}")
        if self.strict:
            p_lemmas = self.analyzer.content_lemmas(participant_all)
            outside = mask_quoted(utt)
            for lemma in sorted(self.analyzer.content_lemmas(outside)):
                if lemma in TEMPLATE_ALLOW or lemma in p_lemmas:
                    continue
                if any(r.endswith(f":{lemma}") for r in reasons):
                    continue
                reasons.append(f"V5:novel:{lemma}")

        # ── V6 ── (따옴표 안의 참여자 원문은 검사하지 않는다)
        outside = mask_quoted(utt)
        for pid, rx, _src in _BANNED:
            m = rx.search(outside)
            if m:
                reasons.append(f"V6:banned:{pid}:{m.group(0)}")

        # ── V7 ──
        marker = self.protocol.marker(template)
        if marker is not None and not marker.search(outside):
            reasons.append(f"V7:template_marker:{template}")
        if re.search(r"(은|는|이|가|와|과|을|를|으로|로)\((은|는|이|가|와|과|을|를|으로|로)\)|\{[XY]\}", utt):
            reasons.append("V7:template_literal")

        # ── V9 (L5) ──
        if self.depth_block:
            deep = [bool(self.safety.depth(t)["strong"]) for t in ctx.participant_texts]
            for q in [anchor, *quotes]:
                if not q:
                    continue
                if self.safety.has_depth_marker(q):
                    reasons.append(f"V9:depth_anchor:{q}")
                    break
                found_in = [d for t, d in zip(ctx.participant_texts, deep) if squash(q) in squash(t)]
                if found_in and all(found_in):
                    reasons.append(f"V9:depth_context:{q}")  # 기억 서사 속 말만 인용함
                    break

        if reasons:
            return CheckResult(False, reasons, parsed=out, notes=notes)

        # ── V8 ── (앞 검사를 모두 통과한 질문만 가드에 보낸다)
        if self.guard is not None and self.check_output:
            gv = self.guard.check_output(ctx.last_participant_text, utt, ctx.last_participant_guard_model)
            if gv.level != "safe":
                return CheckResult(False, [f"V8:guard:{gv.label}"], parsed=out, hard_fail=True, guard=gv.to_log(), notes=notes)
            return CheckResult(True, [], parsed=out, guard=gv.to_log(), notes=notes)
        return CheckResult(True, [], parsed=out, notes=notes)
