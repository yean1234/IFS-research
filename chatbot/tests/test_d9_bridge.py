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
from ifs_chatbot.paths import shared
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


def test_no_more_at_focus_or_bridge_skips_flesh_out_llm(brt):
    s = brt.new_session("chatbot")
    s.start()
    run(s, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "모르겠어요", "돌 같아요"])
    srcs = [src for src, _ in bot(s)]
    i = srcs.index("bridge:like_what")
    assert srcs[i + 1].startswith("fixed:probe_")       # focus_hold '모르겠어요' → flesh_out LLM 건너뜀
    s2 = brt.new_session("chatbot")
    s2.start()
    run(s2, ["불안해요", "가슴 안쪽이요", "그냥 불안해요", "답답해요", "안 보여요"])
    srcs2 = [src for src, _ in bot(s2)]
    assert srcs2[srcs2.index("bridge:like_what") + 1].startswith("fixed:probe_")


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


@pytest.mark.parametrize("name", ["default", "pilot", "v4", "mac8gb"])
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
