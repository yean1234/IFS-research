"""D9 — 감정어·추상 서술 → 구체 심상 다리 질문(프로토콜 1.5, config/bridge.toml).

사양: docs/codex-reviews/prompts/D9_rebuttal_prompt.md 「메인의 판정」 표, 세부는 docs/codex-reviews/D9_claude.md.
대사는 모두 합성이다(AGENTS.md 6).
"""
import json

import pytest

from conftest import FakeGuardModel, turn
from ifs_chatbot import controller as controller_mod
from ifs_chatbot.anchors import anchors_in, bridge_anchor
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.extract import image_signal
from ifs_chatbot.korean import Token
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.llm import ScriptedBackend
from ifs_chatbot.paths import CONFIG_DIR, shared
from ifs_chatbot.protocol import Protocol
from ifs_chatbot.prompts import PromptSet
from ifs_chatbot.safety import SafetyLexicon
from ifs_chatbot.validator import TurnContext

PLAIN = "지금 그것은 마치 무엇 같나요?"


# ── 준비 ─────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def bridge_cfg(tmp_path_factory):
    logs = tmp_path_factory.mktemp("d9logs")
    return load_config("bridge").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(logs)})


@pytest.fixture(scope="module")
def brt(bridge_cfg):
    return Runtime(bridge_cfg, persist_logs=False)


def run(s, replies, fill=True):
    """fill=False면 준 답만 쓰고 멈춘다(다리 질문 직후 상태를 보려고)."""
    it = iter(replies)
    while s.awaiting == "reply":
        nxt = next(it, "없어요" if fill else None)
        if nxt is None:
            return
        s.reply(nxt)


def bot(s):
    return [(m.get("source"), m["text"]) for m in s.messages if m["speaker"] == "bot"]


def bridge_turns(s):
    return [t for t in s.log.turns if (t.get("source") or "").startswith("bridge:")
            or t.get("source") == "fixed:bridge_like_what_plain"]


def sig(rt, text):
    return image_signal(text, rt.lexicon, rt.analyzer, rt.protocol.image_signal_spec)


# ── 형상 신호 판정 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["얇은 조개껍데기 같아요", "돌 같아요", "회색이에요", "안개가 있어요",
                                  "파도마냥 출렁여요", "돌처럼 딱딱해요", "덩어리예요"])
def test_image_signal_present(brt, text):
    assert sig(brt, text)["present"], text


@pytest.mark.parametrize("text", ["불안해요", "기대돼요", "가슴이 답답해요", "숨이 막혀요", "설레요", "조여요",
                                  "그냥 그래요", "모르겠어요"])
def test_image_signal_absent(brt, text):
    assert not sig(brt, text)["present"], text


def test_image_signal_excludes_items_also_in_sensation_or_emotion(brt):
    # '숨'은 sensation(숨)과 posture(숨다)에 모두 있다 → posture 근거로 치지 않는다
    r = sig(brt, "가슴 뒤에 숨어 있어요")
    assert not r["present"]
    assert any(e["lemma"] == "숨" and e["why"] == "also_sensation_or_emotion" for e in r["excluded"])


@pytest.mark.parametrize("text", ["불안 같아요", "가슴 같아요", "느낌 같아요", "숨 같아요"])
def test_simile_with_emotion_sensation_body_or_stop_noun_is_not_image(brt, text):
    r = sig(brt, text)
    assert not r["present"], text
    assert any(e["kind"] == "simile" for e in r["excluded"])


def test_negated_image_word_is_not_evidence(brt):
    r = sig(brt, "하얗지 않아요")
    assert not r["present"] and r["excluded"][0]["why"] == "negated"


# known-misclassification: 반박 처리 표 4b(일부 수용). 지금 규칙의 판정을 그대로 기대값으로 고정한다.
# 문맥 규칙을 더 넣지 않는다(시험 안 된 규칙이 늘어남). 규칙을 바꾸면 이 기대값이 깨져 변화가 드러난다.
KNOWN_MISCLASSIFIED = [
    # (발화, 지금 판정, 근거 종류, 근거 표현(trigger), 왜 오분류인가)
    ("밝은 성격이에요", True, "lexicon", "밝은", "성격 묘사인데 사전 brightness '밝'으로 신호 있음"),
    ("시험 전날 같아요", True, "simile", "전날 같", "장면·상황 비유인데 일반명사+'같'으로 신호 있음"),
    ("엄마 같아요", True, "simile", "엄마 같", "사람 비유인데 일반명사+'같'으로 신호 있음"),
    ("벽에 막힌 느낌이에요", True, "lexicon", "벽", "막힌 느낌(은유)인데 사전 object '벽'으로 신호 있음"),
]


@pytest.mark.parametrize("text,present,kind,trigger,why", KNOWN_MISCLASSIFIED, ids=[r[0] for r in KNOWN_MISCLASSIFIED])
def test_known_misclassification_image_signal(brt, text, present, kind, trigger, why):
    r = sig(brt, text)
    assert r["present"] is present, why       # known-misclassification: 지금 동작을 고정
    ev = [e for e in r["evidence"] if e["kind"] == kind]
    assert ev and ev[0]["trigger"] == trigger and ev[0]["negated"] is False


@pytest.mark.parametrize("text", [r[0] for r in KNOWN_MISCLASSIFIED])
def test_known_misclassification_skips_bridge_and_is_logged(brt, text):
    """known-misclassification: 첫 답에 신호가 있다고 보아 다리를 건너뛴다. 근거 표현·부정 여부·판정 시점이 기록에 남는다."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, [text, "가슴 안쪽이요", "없어요", "없어요"])
    assert bridge_turns(s) == []
    cap = s.log.data["capture"]
    assert cap["bridge"]["skipped"] == "image_signal_present"
    first = cap["imageSignal"]["timeline"][0]
    assert first["judgedAt"] == "reply" and first["kind"] == "opening" and first["present"] is True
    assert first["negated"] is False and first["evidence"][0]["trigger"]
    at = cap["imageSignal"]["atBridge"]
    assert at["judgedAt"] == "bridge" and at["present"] is True and at["evidence"][0]["text"] == text
    assert cap["firstElicitedBy"]["kind"] == "opening"


def test_image_signal_records_negation_and_judgement_point(brt):
    """반박 4b: imageSignal에 근거 표현·부정 여부·판정 시점이 남는다."""
    r = sig(brt, "덩어리는 없어요")
    assert not r["present"] and r["excluded"][0]["why"] == "negated" and r["excluded"][0]["negated"] is True
    assert r["excluded"][0]["trigger"] == "덩어리"
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["덩어리는 없어요", "가슴 안쪽이요", "없어요", "없어요", "돌 같아요"])
    s.act("confirm")
    isg = s.log.data["capture"]["imageSignal"]
    t0 = isg["timeline"][0]
    assert t0["negated"] is True and t0["present"] is False and t0["excluded"][0]["lemma"] == "덩어리"
    assert isg["atFind"]["judgedAt"] == "find_llm" and isg["atFind"]["excluded"][0]["why"] == "negated"
    assert isg["atBridge"]["judgedAt"] == "bridge" and isg["atBridge"]["present"] is False
    assert isg["confirmed"]["judgedAt"] == "confirmed" and isinstance(isg["confirmed"]["turn"], int)
    assert all(isinstance(t["i"], int) and t["stage"] for t in isg["timeline"])


def test_hit_inside_emotion_term_surface_is_not_image(brt):
    """사전 표면 일치 규칙: 적중 형태소가 감정·감각 표제어의 원문 표면 안에 있으면 신호에서 빼고 사유를 남긴다."""
    r = sig(brt, "가슴이 조이고 불안해요")
    assert r["present"] is False
    assert [(e["lemma"], e["why"], e["term"]) for e in r["excluded"]] == [("불", "inside_lexicon_term", "불안")]


@pytest.mark.parametrize("text", ["불꽃 같아요", "돌 같아요", "불이 있어요", "회색 덩어리예요", "불안한 돌 같아요"])
def test_inside_lexicon_term_does_not_over_exclude(brt, text):
    r = sig(brt, text)
    assert r["present"] is True, text
    assert not any(e["why"] == "inside_lexicon_term" for e in r["excluded"])


def test_x_surface_fallback_when_analyzer_splits_term(brt):
    x, info = x_of(brt, "가슴이 조이고 불안해요", None)
    assert x == "불안" and info["kind"] == "lexicon_surface"
    assert info["basis"]["rule"] == "lexicon_surface_match"
    assert "가슴이 조이고 불안해요"[slice(*info["basis"]["charSpan"])] == "불안"
    x2, _ = x_of(brt, "불안해요", None)                    # 분석기 경로는 그대로(규칙 이름이 다름)
    assert x2 == "불안" and _["basis"]["rule"] == "lexicon_category_and_participant_substring"
    for text in ("화분이 있어요", "설레요", "내일 시험이 있어요"):   # 한 글자·형태소 안쪽 일부·활용형은 대체 경로로 쓰지 않음
        assert x_of(brt, text, None)[0] == "", text


def test_simile_negation_is_recorded_but_not_used(brt):
    """known gap: '돌 같지 않아요'의 부정은 비유 표지 기록(negated)에만 남고 판정은 신호 있음(문맥 규칙을 늘리지 않음)."""
    r = sig(brt, "돌 같지 않아요")
    assert r["present"] is True
    assert [e["negated"] for e in r["evidence"] if e["kind"] == "simile"] == [True]


def test_image_signal_is_flow_only_not_scene_value(brt):
    """원칙 2: 형상 신호는 장면·추출 값에 들어가지 않는다(같은 확정 텍스트 → 같은 추출)."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답함이 있어요", "돌 같아요"])
    s.act("confirm")
    ext = s.log.data["extraction"]
    assert ext == brt.extractor.run(s.log.data["confirmedText"], s.log.data["capture"].get("bodyRelation"))
    assert "imageSignal" not in json.dumps(ext, ensure_ascii=False)


# ── X 고르기 ─────────────────────────────────────────────────────────────────
def x_of(rt, opening, focus):
    return bridge_anchor({"opening": opening, "focus_hold": focus}, rt.lexicon, rt.analyzer, rt.safety, doe_root=True)


def test_x_prefers_focus_sensation_over_opening_emotion(brt):
    x, info = x_of(brt, "불안해요", "답답함이 있어요")
    assert x == "답답" and info["from"] == "focus_hold" and info["category"] == "sensation"


def test_x_falls_back_to_opening_emotion(brt):
    x, info = x_of(brt, "불안해요", "그냥 그래요")
    assert x == "불안" and info["from"] == "opening" and info["category"] == "emotion"
    x, info = x_of(brt, "기대돼요", None)            # 오버레이의 감정어 '기대' + 분석기의 기대/NNG + 되/XSV
    assert x == "기대" and info["from"] == "opening"


def test_x_empty_when_only_conjugated_predicates(brt):
    x, info = x_of(brt, "설레요", "조여요")
    assert x == "" and info["from"] is None
    assert [t["why"] for t in info["tried"]] == ["predicate_only", "predicate_only"]


def test_x_skips_depth_strong_answer(brt):
    x, info = x_of(brt, "어릴 때 혼났던 게 생각나서 불안해요", "그냥 그래요")
    assert x == "" and info["tried"][1]["why"] == "depth_strong"


def test_x_is_always_participant_substring(brt):
    for opening, focus in [("불안해요", "답답함이 있어요"), ("기대돼요", "설레요"), ("걱정돼요", "가슴이 조여요")]:
        x, _ = x_of(brt, opening, focus)
        assert not x or x in opening or x in focus


def _lexicon_categories_of(rt, text, x):
    """text 안에서 x 자리(원문 부분 문자열)에 걸린 1층 사전 범주들."""
    s = text.find(x)
    return {h.entry.category for h in rt.lexicon.hits(text) if h.char_span[0] < s + len(x) and s < h.char_span[1]}


@pytest.mark.parametrize("opening,focus", [
    ("시험이 걱정돼요", None), ("시험이 걱정돼요", "그냥 그래요"), ("불안해요", "답답함이 있어요"),
    ("기대돼요", "설레요"), ("회사 일이 불안해요", "몸 안쪽이요"), ("발표가 두려워요", "숨이 차요"),
    ("내일 시험이 있어요", "그냥 그래요"),
])
def test_x_is_lexicon_emotion_or_sensation_and_participant_substring(brt, opening, focus):
    """반박 처리 표 3: X는 감정·감각 사전에 든 표현이면서 참여자 원문의 부분 문자열일 때만 쓴다."""
    x, info = x_of(brt, opening, focus)
    if not x:
        assert info["from"] is None and info["noXReason"]
        return
    src = {"opening": opening, "focus_hold": focus}[info["from"]]
    assert x in src
    assert info["category"] in ("emotion", "sensation")
    assert info["category"] in _lexicon_categories_of(brt, src, x)
    b = info["basis"]
    assert b["rule"] == "lexicon_category_and_participant_substring"
    assert src[b["charSpan"][0]:b["charSpan"][1]] == x


def test_x_is_not_situation_noun_siheom(brt):
    """'시험이 걱정돼요'에서 상황 명사 '시험'(사전 밖)이 아니라 감정어 '걱정'을 고른다. '시험'은 버린 후보로 기록된다."""
    x, info = x_of(brt, "시험이 걱정돼요", None)
    assert x == "걱정" and x != "시험" and info["category"] == "emotion"
    x2, info2 = x_of(brt, "내일 시험이 있어요", None)       # 감정어가 없으면 '시험'을 쓰지 않고 X 없음
    assert x2 == ""
    opening_try = [t for t in info2["tried"] if t["from"] == "opening"][0]
    assert opening_try["why"] == "none_in_category"
    assert any(r["text"] == "시험" and r["category"] is None for r in opening_try["rejected"])
    assert "opening:none_in_category" in info2["noXReason"]


def test_bridge_records_x_basis_and_no_x_reason_in_session_log(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["시험이 걱정돼요", "가슴 안쪽이요", "없어요", "그냥 그래요"], fill=False)
    b = s.log.data["capture"]["bridge"]
    assert b["x"] == "걱정" and b["xSelection"]["basis"]["from"] == "opening"
    assert bot(s)[-1] == ("bridge:like_what", "그 '걱정'은 마치 무엇 같나요?")
    s2 = brt.new_session("chatbot")
    s2.start()
    run(s2, ["설레요", "몸 주변이요", "없어요", "조여요"], fill=False)
    b2 = s2.log.data["capture"]["bridge"]
    assert b2["x"] is None and b2["fallbackReason"] == "no_x"
    assert b2["xSelection"]["noXReason"] == ["focus_hold:predicate_only", "opening:predicate_only"]


# ── 흐름: 다리 1회, 건너뜀, 위치 ───────────────────────────────────────────────
def test_bridge_asked_once_when_no_image_chatbot(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답함이 있어요", "돌 같아요"])
    srcs = [src for src, _ in bot(s)]
    assert srcs.count("bridge:like_what") == 1 and "fixed:bridge_like_what_plain" not in srcs
    assert ("bridge:like_what", "그 '답답'은 마치 무엇 같나요?") in bot(s)
    i_focus, i_bridge = srcs.index("fixed:focus_hold"), srcs.index("bridge:like_what")
    assert i_bridge == i_focus + 1                       # focus_hold 바로 뒤(focus LLM 0회)
    assert srcs[i_bridge + 1] == "llm"                   # 그다음 flesh_out LLM
    t = bridge_turns(s)[0]
    assert t["speaker"] == "system" and t["stage"] == "flesh_out" and "attempts" not in t   # LLM을 부르지 않음


def test_bridge_skipped_when_image_already_present(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["얇은 조개껍데기 같아요", "가슴 안쪽", "회색이에요", "없어요"])
    assert bridge_turns(s) == []
    assert s.log.data["capture"]["bridge"] == {"asked": False, "skipped": "image_signal_present", "stage": "flesh_out"}


def test_bridge_not_repeated_after_soft_check(brt):
    """다리 답에서 확인 문구(은유 '숨막혀요', 안전 사전 0.2)가 나와도 [계속] 뒤 다리를 다시 묻지 않는다."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답함이 있어요"], fill=False)
    assert bridge_turns(s) and s.awaiting == "reply"
    s.reply("숨막혀요")
    assert s.awaiting == "soft_check"
    s.act("continue")
    run(s, [])
    assert len(bridge_turns(s)) == 1


def test_bridge_plain_phrase_when_x_missing(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["설레요", "몸 주변이요", "모르겠어요", "조여요", "모르겠어요"])
    assert ("fixed:bridge_like_what_plain", PLAIN) in bot(s)
    b = s.log.data["capture"]["bridge"]
    assert b["x"] is None and b["phrase"] == "bridge_like_what_plain" and b["fallback"] is False
    assert bridge_turns(s)[0]["phraseStatus"] == "draft"


def test_static_condition_bridge_between_focus_hold_and_fleshout_open(brt):
    s = brt.new_session("static")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "답답해요", "돌 같아요", "커요", "회색", "없어요"])
    srcs = [src for src, _ in bot(s)]
    assert "llm" not in srcs and s.log.data["model"] is None
    i = srcs.index("fixed:focus_hold")
    assert srcs[i + 1] == "bridge:like_what" and srcs[i + 2] == "fixed:fleshout_open"
    # 두 조건에 같은 규칙·같은 문장
    c = brt.new_session("chatbot")
    c.start()
    run(c, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답해요"], fill=False)
    assert bot(c)[-1] == bot(s)[i + 1]


def test_static_bridge_skipped_when_image_present(brt):
    s = brt.new_session("static")
    s.start()
    run(s, ["회색 덩어리예요", "가슴 안쪽이요", "그대로 있어요", "작아요", "없어요"])
    srcs = [src for src, _ in bot(s)]
    i = srcs.index("fixed:focus_hold")
    assert srcs[i + 1] == "fixed:fleshout_open" and bridge_turns(s) == []


def test_no_more_at_bridge_skips_flesh_out_llm(brt):
    """다리 답이 '없어요'류일 때만 flesh_out LLM을 건너뛴다(focus_hold의 noMore는 물려받지 않음)."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "모르겠어요", "모르겠어요"])
    srcs = [src for src, _ in bot(s)]
    i = srcs.index("bridge:like_what")
    assert srcs[i + 1].startswith("fixed:probe_")       # 다리 답 '모르겠어요' → flesh_out LLM 건너뜀
    s2 = brt.new_session("chatbot")
    s2.start()
    run(s2, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답해요", "안 보여요"])
    srcs2 = [src for src, _ in bot(s2)]
    assert srcs2[srcs2.index("bridge:like_what") + 1].startswith("fixed:probe_")


def test_bridge_reply_with_content_resumes_flesh_out_llm_after_focus_no_more(brt):
    """focus_hold '없어요' → 다리 → '돌 같아요'(실질 답) → flesh_out LLM을 정상으로 묻는다."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "없어요", "돌 같아요"], fill=False)
    srcs = [src for src, _ in bot(s)]
    i = srcs.index("bridge:like_what")
    assert srcs[i + 1] == "llm"
    llm_turn = [t for t in s.log.turns if t.get("source") == "llm"][-1]
    assert llm_turn["stage"] == "flesh_out" and "돌 같아요" in s.participant_texts


def test_no_bridge_keeps_v14_focus_no_more_behaviour(brt):
    """다리를 내지 않은 경우(형상 신호 있음): focus_hold '없어요'가 지금처럼 flesh_out LLM을 건너뛰게 한다."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["회색 덩어리예요", "가슴 안쪽이요", "없어요", "없어요"], fill=False)
    srcs = [src for src, _ in bot(s)]
    assert bridge_turns(s) == []
    assert srcs[srcs.index("fixed:focus_hold") + 1].startswith("fixed:probe_")


def test_crisis_on_bridge_reply_uses_fixed_phrase_only(bridge_cfg):
    backend = ScriptedBackend([turn(stage="find", template="anything_else", anchor="불안", utterance="'불안'에 대해 더 있나요?")])
    rt = Runtime(bridge_cfg, backend=backend, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답해요"], fill=False)
    assert bot(s)[-1][0] == "bridge:like_what"
    calls = len(backend.calls)
    s.reply("사실 요즘은 죽고 싶다는 생각도 들어요")
    assert s.state == "crisis" and len(backend.calls) == calls and "109" in s.messages[-1]["text"]


# ── 다리 문장 검증: V1–V7·V9 적용, 걸리면 X 없는 문장, V8 미적용 ─────────────────
def test_bridge_falls_back_to_plain_when_x_sentence_fails_validator(brt, monkeypatch):
    monkeypatch.setattr(controller_mod, "bridge_anchor", lambda *a, **k: ("설레요", {"from": "opening"}))
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["설레요", "몸 주변이요", "모르겠어요", "모르겠어요"])
    assert ("fixed:bridge_like_what_plain", PLAIN) in bot(s)
    assert not any("'설레요'" in text for src, text in bot(s) if src.startswith("bridge:"))
    b = s.log.data["capture"]["bridge"]
    assert b["fallback"] is True and b["checks"]["passed"] is False
    assert any(r.startswith("V7:predicate_as_noun") for r in b["checks"]["reasons"])


def test_bridge_falls_back_on_v9_depth_anchor(brt, monkeypatch):
    monkeypatch.setattr(controller_mod, "bridge_anchor", lambda *a, **k: ("어릴 때", {"from": "opening"}))
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["어릴 때 생각이 나요", "몸 안이요", "모르겠어요", "모르겠어요"])
    b = s.log.data["capture"]["bridge"]
    assert b["phrase"] == "bridge_like_what_plain" and any(r.startswith("V9") for r in b["checks"]["reasons"])


def test_bridge_sentence_is_not_sent_to_guard_model_v8(bridge_cfg):
    utt = "그 '답답'은 마치 무엇 같나요?"
    guard = FakeGuardModel({("답답해요", utt): ("UNSAFE", "S2")})
    backend = ScriptedBackend([turn(stage="find", template="anything_else", anchor="불안", utterance="'불안'에 대해 더 있나요?")])
    rt = Runtime(bridge_cfg.with_overrides(**{"guard.check_output": True}), backend=backend, guard_model=guard,
                 persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답해요"], fill=False)
    assert bot(s)[-1] == ("bridge:like_what", utt)
    assert all(ai != utt for _, ai in guard.calls)


# ── X 없는 고정 문장의 검증 경로(반박 처리 표 7) ─────────────────────────────────
def _plain_out(rt):
    return json.dumps({"stage": "flesh_out", "risk_signal": "none", "move": "ask", "template": "like_what",
                       "anchor_quote": "", "utterance": PLAIN}, ensure_ascii=False)


def test_plain_phrase_goes_through_fixed_phrase_validation_path(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["설레요", "몸 주변이요", "모르겠어요", "조여요"], fill=False)
    b = s.log.data["capture"]["bridge"]
    pc = b["plainChecks"]
    assert pc["path"] == "fixed_phrase" and pc["passed"] is True and pc["reasons"] == []
    assert pc["notApplied"] == ["V1:anchor_required", "V3", "V8"]
    t = bridge_turns(s)[0]
    assert t["source"] == "fixed:bridge_like_what_plain" and t["checks"]["path"] == "fixed_phrase"
    assert t["checks"]["fallbackReason"] == "no_x" and t["checks"]["v8"] == "not_applied"
    assert t["output"]["anchor_quote"] == "" and t["output"]["utterance"] == PLAIN


def test_fixed_phrase_path_only_drops_quote_requirement(brt):
    """require_quote=False는 V1 anchor_required·V3만 뺀다. 기본(True)은 예전 그대로(인용 없는 like_what은 막힘)."""
    v, texts = brt.clarify_validator, ["설레요"]
    ctx = TurnContext("flesh_out", ["like_what"], texts, texts[-1])
    assert "V1:anchor_required" in v.check(_plain_out(brt), ctx).reasons            # 기본 경로: 인용 요구
    assert v.check(_plain_out(brt), ctx, require_quote=False).passed               # 고정 문구 경로: 통과
    bad = json.dumps({"stage": "flesh_out", "risk_signal": "none", "move": "ask", "template": "like_what",
                      "anchor_quote": "", "utterance": "지금 그것은 마치 돌멩이 같나요? 왜 그런가요?"}, ensure_ascii=False)
    reasons = v.check(bad, ctx, require_quote=False).reasons
    assert any(r.startswith("V4:question_count") for r in reasons)                # V4는 그대로
    assert any(r.startswith("V5") for r in reasons)                               # V5(새 내용어) 그대로
    assert any(r.startswith("V6") for r in reasons)                               # V6(왜) 그대로
    assert not any(r.startswith("V3") or r == "V1:anchor_required" for r in reasons)
    wrong_tmpl = json.dumps({"stage": "flesh_out", "risk_signal": "none", "move": "ask", "template": "like_what",
                             "anchor_quote": "", "utterance": "지금 그것은 어디쯤 있나요?"}, ensure_ascii=False)
    assert any(r.startswith("V7:template_marker") for r in v.check(wrong_tmpl, ctx, require_quote=False).reasons)


def test_plain_phrase_failing_validation_is_not_sent(brt, monkeypatch):
    """고정 문장마저 검증기에 걸리면 내지 않고(검증 안 된 문장을 내보내지 않음) 사유를 남긴다."""
    real = brt.clarify_validator.check

    def fake(raw, ctx, require_quote=True):
        r = real(raw, ctx, require_quote=require_quote)
        if not require_quote:
            r.passed, r.reasons = False, ["V5:novel:테스트"]
        return r
    monkeypatch.setattr(brt.clarify_validator, "check", fake)
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["설레요", "몸 주변이요", "모르겠어요", "조여요"])
    assert bridge_turns(s) == []
    b = s.log.data["capture"]["bridge"]
    assert b["asked"] is False and b["skipped"] == "plain_phrase_failed_validation"
    assert b["plainChecks"]["reasons"] == ["V5:novel:테스트"]
    assert any(a["kind"] == "bridge_plain_blocked" for a in s.log.data["alerts"])


# ── 반박 처리 표 8: Codex 합성 첫 발화 15개(D9_rebuttal.md) ──────────────────────
# 기대값은 지금 구현된 규칙의 결과다. 열: (첫 발화, 형상 신호, X, 다리 결과)
#   다리 결과: "skip" = 형상 신호가 있어 다리를 건너뜀, 아니면 낼 문장.
#   X 열은 다리를 냈다면 쓸 X(focus 답에 X가 없다고 둔 Codex 표의 가정과 같게 opening만 줌). None = X 없는 고정 문구.
# Codex가 X 선택 실패 예(²)로 든 줄('마음'·'숨'·'머리'·'벽'·'기분')과 '형태'는 모두 X None(고정 문구)이다.
# 이 가운데 '머리가 하얘져요'·'마음이 텅 빈 것 같아요'·'벽에 막힌 느낌이에요'는 형상 신호가 있어 다리 자체를 건너뛴다.
CODEX_15 = [
    ("불안해요", False, "불안", "그 '불안'은 마치 무엇 같나요?"),
    ("기대돼요", False, "기대", "그 '기대'는 마치 무엇 같나요?"),
    # Codex는 '답답'을 기대했으나, opening에서는 감정어만 X로 쓴다('답답'은 사전 sensation) → 고정 문구
    ("답답해요", False, None, PLAIN),
    ("마음이 무거워요", False, None, PLAIN),                 # '마음'은 인용 금지어, '무거워요'는 활용형
    ("숨이 막혀요", False, None, PLAIN),                     # '숨'은 sensation(opening은 emotion만). 은유 확인 문구가 먼저 나감
    ("머리가 하얘져요", True, None, "skip"),                 # 신호: color '하얗'(남은 위험에 적은 그대로)
    ("마음이 텅 빈 것 같아요", True, None, "skip"),          # 신호: shape '비'('빈'). '것 같'은 의존명사라 비유로 치지 않음
    ("벽에 막힌 느낌이에요", True, None, "skip"),            # known-misclassification(위 KNOWN_MISCLASSIFIED)
    ("구름 위에 있는 것 같아요", True, None, "skip"),        # 신호: object '구름'
    ("시험 전날 같아요", True, None, "skip"),                # known-misclassification(장면 비유)
    ("엄마 같아요", True, None, "skip"),                     # known-misclassification(사람 비유). '엄마'는 깊이 표지라 X도 아님
    # 분석기가 '불안'을 '불/NNG + 안/MAG'으로 나누지만, '불'은 감정 표제어 '불안'의 원문 표면 일치 안이라 신호에서 뺀다
    # (inside_lexicon_term). X는 표면 일치 대체 경로로 '불안'
    ("가슴이 조이고 불안해요", False, "불안", "그 '불안'은 마치 무엇 같나요?"),
    ("차갑고 푸른 덩어리 같아요", True, None, "skip"),
    ("형태가 없어요", False, None, PLAIN),                   # '형태'는 1층 사전에 없어 신호 없음(부정 처리와 무관). 감정어가 아니라 X도 아님
    ("기분은 괜찮은데 속이 꽉 막힌 느낌", False, None, PLAIN),  # '기분'은 인용 금지어
]


@pytest.mark.parametrize("text,present,x,outcome", CODEX_15, ids=[r[0] for r in CODEX_15])
def test_codex_15_signal_and_x(brt, text, present, x, outcome):
    assert sig(brt, text)["present"] is present
    got, info = x_of(brt, text, None)
    assert (got or None) == x
    if x is None:
        assert info["noXReason"]
    if outcome != "skip":
        assert (brt.protocol.realize("like_what", x) if x else PLAIN) == outcome


V5_SPLIT_FALLBACK = {"가슴이 조이고 불안해요"}


@pytest.mark.parametrize("cond", ["chatbot", "static"])
@pytest.mark.parametrize("text,present,x,outcome", CODEX_15, ids=[r[0] for r in CODEX_15])
def test_codex_15_bridge_in_session(brt, cond, text, present, x, outcome):
    """첫 발화만 바꾸고 나머지 답은 '가슴 안쪽이요'·'없어요'로 둔 흐름. 두 조건에 같은 결과."""
    s = brt.new_session(cond)
    s.start()
    replies = [text, "가슴 안쪽이요"] + (["없어요"] if cond == "chatbot" else []) + ["없어요"]
    for r in replies:
        if s.awaiting == "soft_check":
            s.act("continue")
        s.reply(r)
    if s.awaiting == "soft_check":
        s.act("continue")
    turns = bridge_turns(s)
    b = s.log.data["capture"]["bridge"]
    if outcome == "skip":
        assert turns == [] and b["skipped"] == "image_signal_present"
    elif text in V5_SPLIT_FALLBACK:
        # 남은 문제: X '불안'은 골랐지만 참여자 원문 쪽 분석이 '불/안'으로 나뉘어 사전 키 emotion:불안이 참여자 쪽에 없다.
        # 그래서 X 문장이 V5:leak:불안에 걸려 X 없는 고정 문장으로 바뀐다(검증기를 약하게 하지 않음)
        assert [t["text"] for t in turns] == [PLAIN]
        assert b["x"] == x and b["fallbackReason"] == "x_sentence_failed_validation"
        assert b["checks"]["reasons"] == [f"V5:leak:{x}"]
    else:
        assert [t["text"] for t in turns] == [outcome]
        assert b["x"] == x


# ── find 단계 LLM 틀 제한 ─────────────────────────────────────────────────────
def test_find_llm_only_anything_else_without_image(bridge_cfg):
    like = turn(stage="find", template="like_what", anchor="불안", utterance="그 '불안'은 마치 무엇 같나요?")
    ok = turn(stage="find", template="anything_else", anchor="불안", utterance="'불안'에 대해 더 있나요?")
    backend = ScriptedBackend([like, ok])
    rt = Runtime(bridge_cfg, backend=backend, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    s.reply("불안해요")
    s.reply("가슴 안쪽이요")
    assert backend.calls[0].context.allowed_templates == ["anything_else"]
    assert "anything_else" in backend.calls[0].user and "like_what" not in backend.calls[0].user.split("질문 틀]")[1].split("\n")[0]
    llm_turn = [t for t in s.log.turns if t.get("source") == "llm"][-1]
    assert "V2:template_not_allowed:like_what" in llm_turn["attempts"][0]["reasons"]
    assert llm_turn["text"] == "'불안'에 대해 더 있나요?"
    assert s.log.data["capture"]["imageSignal"]["atFind"]["allowedTemplates"] == ["anything_else"]


def test_find_llm_keeps_like_what_when_image_present(bridge_cfg):
    backend = ScriptedBackend([turn(stage="find", template="like_what", anchor="덩어리",
                                    utterance="그 '덩어리'는 마치 무엇 같나요?")])
    rt = Runtime(bridge_cfg, backend=backend, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    s.reply("덩어리가 있어요")
    s.reply("가슴 안쪽이요")
    assert backend.calls[0].context.allowed_templates == ["anything_else", "like_what"]
    assert s.messages[-1]["text"] == "그 '덩어리'는 마치 무엇 같나요?"


# ── 기록 3항목 ───────────────────────────────────────────────────────────────
def test_records_image_signal_first_elicited_by_and_imageless(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답함이 있어요", "돌 같아요"])
    cap = s.log.data["capture"]
    tl = cap["imageSignal"]["timeline"]
    assert [t["kind"] for t in tl[:5]] == ["opening", "location", "llm:find", "focus_hold", "bridge"]
    assert [t["present"] for t in tl[:5]] == [False, False, False, False, True]
    assert tl[4]["askedBy"] == "bridge:like_what" and tl[4]["cumulative"] is True
    assert cap["imageSignal"]["atBridge"]["present"] is False and cap["imageSignal"]["use"] == "flow_only"
    assert cap["firstElicitedBy"]["kind"] == "bridge" and cap["firstElicitedBy"]["evidence"] == ["돌"]
    assert cap["firstElicitedBy"]["detail"] == "bridge"
    assert [t["elicitedBy"] for t in tl[:5]] == ["opening", "opening", "llm", "focus_hold", "bridge"]
    assert cap["imageless"] is False
    s.act("confirm")
    assert cap["imageSignal"]["confirmed"]["present"] is True

    s2 = brt.new_session("chatbot")
    s2.start()
    run(s2, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "모르겠어요", "모르겠어요"])
    cap2 = s2.log.data["capture"]
    assert cap2["firstElicitedBy"] is None and cap2["imageless"] is True

    s3 = brt.new_session("chatbot")
    s3.start()
    run(s3, ["얇은 조개껍데기 같아요", "가슴 안쪽"])
    assert s3.log.data["capture"]["firstElicitedBy"]["kind"] == "opening"


ELICITED_BY = ["opening", "focus_hold", "bridge", "llm", "probe"]


@pytest.mark.parametrize("cond,replies,kind,detail", [
    ("chatbot", ["불안해요", "회색 덩어리가 가슴 안쪽에 있어요"], "opening", "location"),       # find 단계 고정 문구
    ("chatbot", ["불안해요", "가슴 안쪽이요", "돌 같아요"], "llm", "llm:find"),
    ("chatbot", ["불안해요", "가슴 안쪽이요", "없어요", "돌 같아요"], "focus_hold", "focus_hold"),
    ("chatbot", ["불안해요", "가슴 안쪽이요", "없어요", "없어요", "없어요", "회색이에요"], "probe", None),
    ("static", ["불안해요", "가슴 안쪽이요", "없어요", "없어요", "돌 같아요"], "probe", "fleshout_open"),  # flesh_out 단계 고정 문구
])
def test_first_elicited_by_kind_is_one_of_five(brt, cond, replies, kind, detail):
    """반박 처리 표 6: firstElicitedBy.kind = opening / focus_hold / bridge / llm / probe. 자세한 턴 종류는 detail."""
    s = brt.new_session(cond)
    s.start()
    run(s, replies)
    f = s.log.data["capture"]["firstElicitedBy"]
    assert f["kind"] == kind and f["kind"] in ELICITED_BY
    if detail:
        assert f["detail"] == detail
    else:
        assert f["detail"].startswith("probe:")
    assert all(t["elicitedBy"] in ELICITED_BY for t in s.log.data["capture"]["imageSignal"]["timeline"])


def test_schema_enumerates_first_elicited_by_kind(brt):
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", "session_log.schema.json").read_text(encoding="utf-8"))
    prop = schema["properties"]["capture"]["properties"]["firstElicitedBy"]
    assert prop["properties"]["kind"]["enum"] == ELICITED_BY
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["돌 같아요", "가슴 안쪽이요"], fill=False)
    data = json.loads(json.dumps(s.log.data, ensure_ascii=False))
    assert not list(Draft202012Validator(schema).iter_errors(data))
    data["capture"]["firstElicitedBy"]["kind"] = "llm:find"          # 예전 값은 이제 스키마 위반
    assert list(Draft202012Validator(schema).iter_errors(data))


def test_session_log_with_bridge_matches_schema(brt):
    from jsonschema import Draft202012Validator
    schema = json.loads(shared("schemas", "session_log.schema.json").read_text(encoding="utf-8"))
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답해요", "돌 같아요"])
    s.act("confirm")
    errs = list(Draft202012Validator(schema).iter_errors(json.loads(json.dumps(s.log.data, ensure_ascii=False))))
    assert not errs, errs[:2]


# ── 부수 수정 ────────────────────────────────────────────────────────────────
class StubAnalyzer:
    """'기대되/VV'처럼 '-되' 용언을 한 덩어리로 내는 분석기(다른 Kiwi 판·대체 분석기)를 흉내 낸다."""
    available = True

    def __init__(self, table):
        self.table = table

    def tokens(self, text):
        return [Token(*t) for t in self.table[text]]

    def content_lemmas(self, text):
        return {t.form for t in self.tokens(text) if t.base_tag in ("NNG", "NNP", "XR", "MAG", "VA", "VV")}


def test_doe_root_rule(brt):
    an = StubAnalyzer({"기대돼요": [("기대되", "VV", 0, 3), ("어요", "EF", 3, 4)],
                       "안돼요": [("안되", "VV", 0, 2), ("어요", "EF", 2, 3)]})
    lex = Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), an)
    on = anchors_in("기대돼요", lex, an, brt.safety, doe_root=True)
    assert [(a.text, a.kind) for a in on] == [("기대", "root")]
    assert anchors_in("기대돼요", lex, an, brt.safety, doe_root=False) == []     # 기본: 예전 그대로
    assert anchors_in("안돼요", lex, an, brt.safety, doe_root=True) == []        # 한 글자 어근('안')은 빼기


def test_lexicon_overlay_adds_gidae_only_in_bridge_config(brt, rt):
    assert "emotion" in brt.lexicon.categories_in("기대돼요")
    assert "emotion" not in rt.lexicon.categories_in("기대돼요")                    # 기본 설정은 v0 그대로
    assert rt.lexicon.version == "0.1.0" and "layer1-interview-overlay@0.1.0" in brt.lexicon.version
    an = StubAnalyzer({"기대돼요": [("기대되", "VV", 0, 3), ("어요", "EF", 3, 4)]})
    assert "emotion" in Lexicon(brt.lexicon.path, an, data=None).categories_in("기대돼요")  # alt '기대되'
    v0 = json.loads(shared("lexicon", "layer1_lexicon.v0.json").read_text(encoding="utf-8"))
    assert not any(e["lemma"] == "기대" for e in v0["entries"])


def test_find_modality_sees_gidae_as_emotion_in_bridge_config(brt):
    s = brt.new_session("chatbot")
    s.start()
    s.reply("기대돼요")
    assert "emotion" in s.log.data["capture"]["findModality"]["labels"]


@pytest.mark.parametrize("text", ["숨막혀요", "숨이 막힌 느낌이에요", "숨이 막혀요", "숨이 막혔어요", "숨이 막히는 느낌"])
def test_metaphor_regex_v02_catches_conjugations(text):
    new, old = SafetyLexicon(shared("lexicon", "safety_ko.v0.2.json")), SafetyLexicon()
    assert any(h.id == "cannot_breathe" for h in new.crisis_hits(text)), text
    assert not any(h.tier == "crisis" for h in new.crisis_hits(text))
    if text in ("숨막혀요", "숨이 막힌 느낌이에요", "숨이 막혀요", "숨이 막혔어요"):
        assert not any(h.id == "cannot_breathe" for h in old.crisis_hits(text))   # v0(0.1.0)은 그대로


def test_safety_v02_only_changes_cannot_breathe_and_no_more():
    v0 = json.loads(shared("lexicon", "safety_ko.v0.json").read_text(encoding="utf-8"))
    v2 = json.loads(shared("lexicon", "safety_ko.v0.2.json").read_text(encoding="utf-8"))
    assert v0["lexiconVersion"] == "0.1.0" and v2["lexiconVersion"] == "0.2.0"
    t0, t2 = v0["crisis"]["tiers"], v2["crisis"]["tiers"]
    assert t0["crisis"] == t2["crisis"]
    assert [p for p in t0["metaphor"]["patterns"] if p["id"] != "cannot_breathe"] \
        == [p for p in t2["metaphor"]["patterns"] if p["id"] != "cannot_breathe"]
    assert v0["depth"] == v2["depth"] and v0["control"]["stop"] == v2["control"]["stop"]
    assert set(v0["control"]["noMore"]["patterns"]) < set(v2["control"]["noMore"]["patterns"])
    new = SafetyLexicon(shared("lexicon", "safety_ko.v0.2.json"))
    assert new.is_no_more("안 보여요") and new.is_no_more("안 떠올라요") and not SafetyLexicon().is_no_more("안 보여요")


@pytest.mark.parametrize("text", ["안 보여요", "안 보여요.", "잘 안 떠올라요", "안 보이네요", "안 떠올라", "잘 안 보입니다"])
def test_safety_v02_no_more_whole_message_only(text):
    assert SafetyLexicon(shared("lexicon", "safety_ko.v0.2.json")).is_no_more(text), text


@pytest.mark.parametrize("text", ["안 보이는데 차가운 느낌이에요", "안 보이고 검은 덩어리가 있어요", "잘 안 떠오르는데 따뜻해요",
                                  "얼굴은 안 보여요"])
def test_safety_v02_description_after_an_boyeo_is_not_no_more(brt, text):
    """뒤에 묘사가 이어지는 발화는 noMore가 아니다 — 참여자가 말한 묘사가 participant_texts에서 빠지지 않는다(원칙 2)."""
    assert not SafetyLexicon(shared("lexicon", "safety_ko.v0.2.json")).is_no_more(text), text
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", text], fill=False)
    assert text in s.participant_texts


def _v7(rt, template, anchor, utt, texts):
    out = json.dumps({"stage": "flesh_out", "risk_signal": "none", "move": "ask", "template": template,
                      "anchor_quote": anchor, "utterance": utt}, ensure_ascii=False)
    return rt.clarify_validator.check(out, TurnContext("flesh_out", [template], texts, texts[-1]))


def test_v7_predicate_as_noun(brt, rt):
    for tmpl, utt in [("what_kind", "그 '설레요'는 어떤 '설레요'인가요?"), ("where", "그 '설레요'는 어디쯤 있나요?"),
                      ("like_what", "그 '설레요'는 마치 무엇 같나요?")]:
        r = _v7(brt, tmpl, "설레요", utt, ["설레요"])
        assert "V7:predicate_as_noun:설레요" in r.reasons, tmpl
        assert not any(x.startswith("V7:predicate_as_noun") for x in _v7(rt, tmpl, "설레요", utt, ["설레요"]).reasons)
    assert _v7(brt, "anything_else", "설레요", "'설레요'에 대해 더 있나요?", ["설레요"]).passed   # 이 틀은 그대로 허용
    assert _v7(brt, "like_what", "불안", "그 '불안'은 마치 무엇 같나요?", ["불안해요"]).passed


def test_prompt_v110_only_changes_find_and_flesh_out_blocks():
    p10, p11 = PromptSet("1.0.0"), PromptSet("1.1.0")
    assert p10.common == p11.common and p10.context_template == p11.context_template
    assert p10.stage_blocks["focus"] == p11.stage_blocks["focus"]
    assert p10.stage_blocks["find"] != p11.stage_blocks["find"] and "anything_else" in p11.stage_blocks["find"]
    assert "like_what" in p11.stage_blocks["flesh_out"] and p10.sha256 != p11.sha256


def test_bridge_config_uses_all_d9_switches(bridge_cfg, brt):
    c = bridge_cfg
    assert c.interview.protocol == "elicitation_protocol.v1.5.json" and c.interview.prompt_version == "1.1.0"
    assert c.interview.lexicon_overlay and c.interview.anchor_doe_root and c.validator.predicate_as_noun
    assert c.guard.safety_lexicon == "safety_ko.v0.2.json"
    h = brt.header("chatbot")
    assert h["protocol"]["protocolVersion"] == "1.5.0" and h["protocol"]["promptVersion"] == "1.1.0"
    assert h["protocol"]["safetyLexiconVersion"] == "0.2.0" and h["validator"]["predicateAsNoun"] is True


# ── 프로토콜 1.5 · 기존 설정은 그대로 ───────────────────────────────────────────
def test_protocol_v15_only_adds_bridge_parts():
    p14 = json.loads(shared("protocol", "elicitation_protocol.v1.4.json").read_text(encoding="utf-8"))
    p15 = json.loads(shared("protocol", "elicitation_protocol.v1.5.json").read_text(encoding="utf-8"))
    assert p15["protocolVersion"] == "1.5.0" and p15["changes"][0]["version"] == "1.5.0"
    assert p15["changes"][0]["status"] == "draft" and p15["changes"][1:] == p14["changes"]
    same = ("protocolId", "description", "sources", "phraseStatusLegend", "templates", "dimensionProbes",
            "driftChecks", "vrStages", "outOfScope")
    assert all(p15[k] == p14[k] for k in same)                       # 질문 틀·프로브 순서 그대로
    assert {k: v for k, v in p15["fixedPhrases"].items() if k != "bridge_like_what_plain"} == p14["fixedPhrases"]
    plain = p15["fixedPhrases"]["bridge_like_what_plain"]
    assert plain["text"] == PLAIN and plain["status"] == "draft" and "D9" in plain["source"]
    for cond in ("static", "chatbot"):
        seq = [s for s in p15["conditions"][cond]["sequence"] if s["type"] != "bridge"]
        assert seq == p14["conditions"][cond]["sequence"]
        assert sum(s["type"] == "bridge" for s in p15["conditions"][cond]["sequence"]) == 1
    f14, f15 = p14["stages"]["find"], p15["stages"]["find"]
    assert f15["allowedTemplatesWhenNoImage"] == ["anything_else"] and f15["allowedTemplates"] == f14["allowedTemplates"]
    assert {k: v for k, v in p15["stages"].items() if k != "find"} == {k: v for k, v in p14["stages"].items() if k != "find"}
    banned = ("왜", "기억", "과거", "이유", "예전", "내담자", "진단", "치료", "상담", "모양", "보이")
    assert not any(w in plain["text"] for w in banned)


def test_v14_protocol_has_no_bridge():
    p = Protocol()
    assert p.version == "1.4.0" and p.bridge is None and not p.uses_image_signal()
    assert p.allowed_templates("find", image_present=False) == ["anything_else", "like_what"]


@pytest.mark.parametrize("name", ["default", "pilot", "v4", "mac8gb", pytest.param("v4-gen3d", marks=pytest.mark.skipif(
    not (CONFIG_DIR / "v4-gen3d.toml").is_file(), reason="v4-gen3d.toml은 다른 작업(G62)의 설정 파일"))])
def test_existing_configs_keep_d9_off(name):
    c = load_config(name)
    assert c.interview.protocol == "elicitation_protocol.v1.4.json" and c.interview.prompt_version == "1.0.0"
    assert c.interview.lexicon_overlay == "" and c.interview.anchor_doe_root is False
    assert c.validator.predicate_as_noun is False and c.guard.safety_lexicon == "safety_ko.v0.json"


@pytest.mark.parametrize("cond,replies", [
    ("chatbot", ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답함이 있어요", "돌 같아요"]),
    ("static", ["불안해요", "가슴 안쪽이요", "답답해요", "돌 같아요", "커요"]),
])
def test_default_runtime_never_bridges_or_records_d9(rt, cond, replies):
    s = rt.new_session(cond)
    s.start()
    run(s, replies)
    assert bridge_turns(s) == []
    cap = s.log.data["capture"]
    assert not {"imageSignal", "firstElicitedBy", "imageless", "bridge"} & set(cap)
    assert "predicateAsNoun" not in s.log.data["validator"] and "anchorDoeRoot" not in s.log.data["protocol"]
    assert s.log.data["protocol"]["protocolVersion"] == "1.4.0"
    assert s.log.data["protocol"]["safetyLexiconVersion"] == "0.1.0"


# ── CP11: 다리를 낸 세션은 그 뒤 LLM이 like_what을 다시 고르지 못함 · 부정 집계 ─────────
def test_like_what_blocked_for_llm_after_bridge(bridge_cfg):
    find = turn(stage="find", template="anything_else", anchor="불안", utterance="'불안'에 대해 더 있나요?")
    like = turn(stage="flesh_out", template="like_what", anchor="바람", utterance="그 '바람'은 마치 무엇 같나요?")
    kind = turn(stage="flesh_out", template="what_kind", anchor="바람", utterance="그 '바람'은 어떤 '바람'인가요?")
    backend = ScriptedBackend([find, like, kind])
    rt = Runtime(bridge_cfg, backend=backend, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답함이 있어요", "바람 같아요"], fill=False)
    assert bridge_turns(s) and s.log.data["capture"]["bridge"]["asked"] is True
    fl = [c for c in backend.calls if c.context.stage == "flesh_out"]
    assert fl and "like_what" not in fl[0].context.allowed_templates
    llm_turn = [t for t in s.log.turns if t.get("source") == "llm" and t.get("stage") == "flesh_out"][-1]
    assert "V2:template_not_allowed:like_what" in llm_turn["attempts"][0]["reasons"]
    assert llm_turn["text"] == "그 '바람'은 어떤 '바람'인가요?"
    assert s.log.data["capture"]["bridge"]["blockedTemplateAfter"] == "like_what"


def test_like_what_still_allowed_for_llm_when_bridge_skipped(bridge_cfg):
    find = turn(stage="find", template="anything_else", anchor="덩어리", utterance="'덩어리'에 대해 더 있나요?")
    like = turn(stage="flesh_out", template="like_what", anchor="덩어리", utterance="그 '덩어리'는 마치 무엇 같나요?")
    backend = ScriptedBackend([find, like])
    rt = Runtime(bridge_cfg, backend=backend, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    run(s, ["회색 덩어리예요", "가슴 안쪽이요", "그냥 있어요", "무거워요"], fill=False)
    assert bridge_turns(s) == [] and s.log.data["capture"]["bridge"]["asked"] is False
    fl = [c for c in backend.calls if c.context.stage == "flesh_out"]
    assert fl and "like_what" in fl[0].context.allowed_templates
    assert s.messages[-1]["text"] == "그 '덩어리'는 마치 무엇 같나요?"
    assert "blockedTemplateAfter" not in s.log.data["capture"]["bridge"]


def test_timeline_negation_aggregates_both_sides(brt):
    """CP11: 부정으로 뺀 사전 적중(negatedExcluded)과 부정이 기록만 된 비유 적중(negatedInEvidence)을 나눠 집계한다."""
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["공 같지 않아요", "가슴 안쪽이요"], fill=False)
    t0 = s.log.data["capture"]["imageSignal"]["timeline"][0]
    assert t0["present"] is True                       # 판정은 그대로(비유 적중은 신호)
    assert t0["negatedInEvidence"] is True and t0["negated"] is True
    s2 = brt.new_session("chatbot")
    s2.start()
    run(s2, ["덩어리는 없어요", "가슴 안쪽이요"], fill=False)
    t1 = s2.log.data["capture"]["imageSignal"]["timeline"][0]
    assert t1["negatedExcluded"] is True and t1["negatedInEvidence"] is False and t1["negated"] is True
    s3 = brt.new_session("chatbot")
    s3.start()
    run(s3, ["돌 같아요", "가슴 안쪽이요"], fill=False)
    t2 = s3.log.data["capture"]["imageSignal"]["timeline"][0]
    assert t2["negatedExcluded"] is False and t2["negatedInEvidence"] is False and t2["negated"] is False
