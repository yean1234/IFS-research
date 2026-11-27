"""G70 — 면담 앞부분(프로토콜 1.6, config/experiment.toml) + 연구 책임자 시험 세션 결함 1–5.

- G70: location 삭제(bodyRelation = not_asked), flesh_out where 삭제, focus_hold·다리·intro 문구, find LLM 조건(G70-e),
  안전 사전 0.3.0(G70-f), 다리 X는 일반명사만(G70-c)
- 결함 1·2: like_what 세션 1회(다리 포함)·직전 틀 반복 금지·형상 X에 like_what 금지(허용 목록 + V2)
- 결함 3: 프로브 '이미 말함' = 매퍼가 채운 슬롯 + 형상 신호, 크기 전용·모양 전용 프로브
- 결함 4: 남은 고정 문구에 '그것' 없음(형상 명사 X 인용 또는 '그 느낌')
- 결함 5: 프롬프트 v1.2.0 맥락(이미 말한 차원·이미 쓴 틀)
- 1.5·bridge 설정은 그대로

대사는 합성이거나 연구 책임자가 시험 삼아 적은 문장이다(참여자 자료 아님, AGENTS.md 6).
"""
import json

import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.llm import GenerationResult, ScriptedBackend
from ifs_chatbot.paths import SCENARIO_DIR, shared
from ifs_chatbot.prompts import PromptContext, PromptSet
from ifs_chatbot.protocol import Protocol
from ifs_chatbot.safety import Guard, SafetyLexicon
from ifs_chatbot.simulate import check_expect, drive, question_templates, session_metrics
from ifs_chatbot.validator import TurnContext

P16 = Protocol("elicitation_protocol.v1.6.json")
P15 = Protocol("elicitation_protocol.v1.5.json")


def scenario(name):
    return json.loads((SCENARIO_DIR / f"{name}.json").read_text(encoding="utf-8"))


FOG = scenario("g70_researcher_fog")["replies"]
FINISH = scenario("g70_researcher_finish")["replies"]


@pytest.fixture(scope="module")
def exp_cfg(tmp_path_factory):
    return load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "preview.mode": "none",
        "session.log_dir": str(tmp_path_factory.mktemp("g70logs"))})


@pytest.fixture(scope="module")
def ert(exp_cfg):
    return Runtime(exp_cfg, persist_logs=False)


class _Rule:
    """질문 틀 하나만 계속 내는 모의 LLM(규칙 1·2가 막는지 보려고 일부러 어기게 꾸민 대역)."""
    name = "rule"

    def __init__(self, template, pick="first"):
        self.template, self.pick, self.calls = template, pick, []

    def check(self):
        return True, "ok"

    def info(self):
        return {"name": f"only-{self.template}", "quant": None, "digest": None, "runtime": "test", "sampling": None}

    def warmup(self):
        return None

    def generate(self, req):
        self.calls.append(req)
        ctx = req.context
        cands = list(ctx.anchor_candidates)
        if self.pick == "non_image":
            from ifs_chatbot.extract import image_signal
            cands = [a for a in cands if not image_signal(a.text, self.lexicon, self.analyzer, P16.image_signal_spec)["present"]] or cands
        a = cands[0].text if cands else "느낌"
        out = {"stage": ctx.stage, "risk_signal": "none", "move": "ask", "template": self.template,
               "anchor_quote": a, "utterance": P16.realize(self.template, a)}
        return GenerationResult(json.dumps(out, ensure_ascii=False), latency_ms=0, meta={})


def make_rt(exp_cfg, backend):
    rt = Runtime(exp_cfg, backend=backend, persist_logs=False)
    backend.lexicon, backend.analyzer = rt.lexicon, rt.analyzer
    return rt


def run(s, replies, fill=True):
    """fill=False면 준 답만 쓰고 멈춘다(그 직후 질문을 보려고)."""
    if s.awaiting == "start":
        s.start()
    it = iter(replies)
    while s.awaiting in ("reply", "soft_check"):
        if s.awaiting == "soft_check":
            s.act("continue")
            continue
        nxt = next(it, "없어요" if fill else None)
        if nxt is None:
            return
        s.reply(nxt)


def bot(s):
    return [t for t in s.log.turns if t.get("speaker") in ("system", "interviewer") and t.get("text")]


def llm_like_what_sent(s):
    return [t["text"] for t in bot(s) if t.get("source") == "llm" and (t.get("output") or {}).get("template") == "like_what"]


# ── 프로토콜 1.6 파일 ────────────────────────────────────────────────────────
def test_v16_sequences_have_no_location_and_bodyrelation_not_asked():
    for cond in ("static", "chatbot"):
        assert all(st.phrase != "location" for st in P16.sequence(cond))
        assert any(st.phrase == "location" for st in P15.sequence(cond))      # 1.5는 그대로
    assert "location" not in P16.phrases and "bridge_like_what_plain" not in P16.phrases
    assert P16.capture_defaults == {"bodyRelation": {"status": "not_asked"}}
    assert P15.capture_defaults == {} and P15.template_rules == {} and P15.probe_coverage is None


def test_v16_where_removed_from_flesh_out_only():
    assert "where" not in P16.allowed_templates("flesh_out")
    assert "where" in P15.allowed_templates("flesh_out")


def test_v16_phrases_exactly_as_g70():
    ph = P16.phrases
    assert ph["focus_hold"]["text"] == ("그 일을 떠올릴 때 드는 느낌에 잠시 주의를 두고 머물러 보세요. 뚜렷하지 않아도 괜찮아요. "
                                        "그러다 떠오르는 말이나 모습이 있으면 적어 주세요. 한 낱말이어도 돼요.")
    assert ph["bridge_feeling"]["text"] == "그 느낌이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"
    assert ph["bridge_feeling"]["withX"] == "그 '{X}'{X|이/가} 눈에 보이는 무언가라면, 마치 무엇 같을까요?"
    assert "짧게 적어도 되고, 맞거나 틀린 답은 없어요." in ph["intro"]["text"]
    assert ph["opening"] == P15.phrases["opening"]                        # G70-g
    for k in ("focus_hold", "bridge_feeling", "fleshout_open", "probe_size_shape", "probe_size", "probe_shape",
              "probe_color_brightness", "probe_movement", "depth_present", "intro"):
        assert ph[k]["status"] == "draft", k


def test_v16_fixed_phrases_never_use_geugeot():
    for k, p in P16.phrases.items():
        for form in ("text", "withX"):
            assert "그것" not in p.get(form, ""), (k, form)


@pytest.mark.parametrize("key,x,want", [
    ("bridge_feeling", "걱정", "그 '걱정'이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"),
    ("bridge_feeling", "두려움", "그 '두려움'이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"),
    ("bridge_feeling", "불안", "그 '불안'이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"),
    ("bridge_feeling", "", "그 느낌이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"),
    ("probe_size", "먹구름", "그 '먹구름'에 크기가 있나요?"),
    ("probe_shape", "안개", "그 '안개'에 모양이 있나요?"),
    ("probe_size_shape", "", "그 느낌에 크기나 모양이 있나요?"),
    ("probe_color_brightness", "돌", "그 '돌'에 색이나 밝기가 있나요?"),
    ("probe_movement", "", "그 느낌에 움직임이 있나요?"),
    ("fleshout_open", "안개", "지금 그 '안개'가 어떻게 있는지 떠오르는 대로 적어 주세요."),
    ("fleshout_open", "먹구름", "지금 그 '먹구름'이 어떻게 있는지 떠오르는 대로 적어 주세요."),
    ("depth_present", "돌", "지금은 떠오른 그 '돌'이 지금 어떻게 있는지에만 머물러 볼게요. 그 '돌'에서 지금 알아차려지는 것이 있나요?"),
    ("depth_present", "", "지금은 떠오른 그 느낌이 지금 어떻게 있는지에만 머물러 볼게요. 그 느낌에서 지금 알아차려지는 것이 있나요?"),
])
def test_v16_referent_josa(key, x, want):
    assert P16.phrase_ref(key, x) == want


# ── G70: location·bodyRelation ───────────────────────────────────────────────
def test_session_has_not_asked_bodyrelation_and_extraction_skips_it(ert):
    s = ert.new_session("chatbot")
    run(s, ["걱정이 많아요", "그냥 그래요", "가슴이 답답해요", "차가운 물 같아요"])
    s.act("confirm")
    assert s.log.data["capture"]["bodyRelation"] == {"status": "not_asked"}
    assert "bodyRelation" not in s.log.data["extraction"]["sceneSpecDraft"]["slots"]
    assert not any(t.get("source") == "fixed:location" for t in s.log.turns)


# ── G70-e: find LLM 조건 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("opening,asked", [
    ("마감이 다가와요", False), ("빨리 끝내고 싶다", False), ("잘할 수 있을까 싶어요", False),
    ("걱정이 많아요", True), ("가슴이 답답해요", True), ("검은 안개가 있는 느낌", True)])
def test_find_llm_only_with_emotion_sensation_or_image(exp_cfg, opening, asked):
    be = ScriptedBackend([])           # 부르면 오류(스크립트 없음) → 기록에 llm_error
    rt = Runtime(exp_cfg, backend=be, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    s.reply(opening)
    fl = s.log.data["capture"]["findLlm"]
    assert fl["asked"] is asked and fl["from"] == "opening"
    assert (len(be.calls) > 0) is asked
    if not asked:
        assert fl["skipped"] == "no_emotion_sensation_or_image" and s.messages[-1]["source"] == "fixed:focus_hold"


# ── G70-c: 다리 X는 일반명사만, V5 허용어 ───────────────────────────────────
def test_bridge_x_is_noun_only_in_v16(ert):
    s = ert.new_session("chatbot")
    run(s, ["걱정이 많아요", "그냥 그래요", "가슴이 답답해요"], fill=False)
    br = s.log.data["capture"]["bridge"]
    assert br["x"] == "걱정" and br["xSelection"]["tried"][0]["why"] == "root_only"   # '답답'은 '-하' 어근
    assert s.messages[-1]["text"] == "그 '걱정'이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"
    assert br["v5Allow"] == sorted(["눈", "보이", "무언가", "느낌"])


def test_bridge_plain_when_only_roots_or_predicates(ert):
    s = ert.new_session("chatbot")
    run(s, ["마음이 무거워요", "어깨가 뻐근해요"], fill=False)
    br = s.log.data["capture"]["bridge"]
    assert br["x"] is None and br["phrase"] == "bridge_feeling" and br["plainChecks"]["passed"]
    assert "focus_hold:root_only" in br["xSelection"]["noXReason"]           # '뻐근'은 '-하' 어근(G70-c)
    t = next(t for t in s.log.turns if t.get("source") == "fixed:bridge_feeling")
    assert t["text"] == "그 느낌이 눈에 보이는 무언가라면, 마치 무엇 같을까요?"


def test_v5_allow_is_what_lets_bridge_sentence_pass(ert):
    """검증기를 약하게 한 곳의 범위: v5Allow 없이 같은 문장을 검사하면 V5에 걸린다(docs/chatbot-design.md 5-4)."""
    ctx = TurnContext("flesh_out", ["like_what"], ["걱정이 많아요"], "걱정이 많아요")
    out = {"stage": "flesh_out", "risk_signal": "none", "move": "ask", "template": "like_what", "anchor_quote": "걱정",
           "utterance": P16.phrase_ref("bridge_feeling", "걱정")}
    raw = json.dumps(out, ensure_ascii=False)
    strict = ert.clarify_validator.check(raw, ctx)
    assert not strict.passed and any(r.startswith("V5") for r in strict.reasons)
    allow = frozenset(P16.bridge["validation"]["v5Allow"])
    assert ert.clarify_validator.check(raw, ctx, extra_allow=allow).passed
    # LLM 질문 경로(Runtime.validator)는 extra_allow를 받지 않는다 → 같은 문장을 LLM이 내면 막힌다
    assert not ert.validator.check(raw, ctx).passed


# ── G70-f: 안전 사전 0.3.0 ───────────────────────────────────────────────────
def test_safety_v03_finish_wish_does_not_stop_but_crisis_side_kept():
    v2 = SafetyLexicon(shared("lexicon", "safety_ko.v0.2.json"))
    v3 = SafetyLexicon(shared("lexicon", "safety_ko.v0.3.json"))
    assert v3.version == "0.3.0"
    assert v2.is_stop("끝내고 싶어요") and not v3.is_stop("끝내고 싶어요")
    for lex in (v2, v3):
        assert lex.is_stop("끝낼래요") and lex.is_stop("그만") and lex.is_stop("끝내 주세요")
        g = Guard(lex, None, use_keywords=True)
        v = g.check_input("다 끝내고 싶어요")              # 위기 쪽 확인 문구 「다 끝내고 싶」은 그대로
        assert v.level == "soft" and "kw:ambiguous:give_up_all" in v.reasons
        assert g.check_input("빨리 끝내고 싶어요").level == "safe" and not lex.is_stop("빨리 끝내고 싶어요")


def test_experiment_session_continues_after_finish_wish(ert):
    s = ert.new_session("chatbot")
    s.start()
    s.reply("끝내고 싶어요")
    assert s.state == "interview" and s.messages[-1]["source"] == "fixed:focus_hold"


# ── 결함 1·2: 틀 규칙 ───────────────────────────────────────────────────────
@pytest.mark.parametrize("replies", [FOG, FINISH], ids=["fog", "finish"])
def test_like_what_only_llm_never_gets_like_what_out(exp_cfg, replies):
    be = _Rule("like_what")
    rt = make_rt(exp_cfg, be)
    s = rt.new_session("chatbot")
    run(s, replies)
    assert llm_like_what_sent(s) == []
    tpls = question_templates(s)
    assert tpls.count("like_what") <= 1                                     # 다리 질문 포함 1회
    assert all(not (a and a == b) for a, b in zip(tpls, tpls[1:]))          # 대체 문구 연속도 없음
    reasons = [r for t in s.log.turns for a in t.get("attempts", []) for r in a["reasons"]]
    assert any(r.startswith("V2:template_not_allowed:like_what") or r.startswith("V2:image_x:like_what") for r in reasons)
    assert all("그것" not in t["text"] for t in bot(s))


def test_image_x_blocked_by_v2_for_fog(exp_cfg):
    be = _Rule("like_what")
    rt = make_rt(exp_cfg, be)
    s = rt.new_session("chatbot")
    run(s, FOG)
    reasons = [r for t in s.log.turns for a in t.get("attempts", []) for r in a["reasons"]]
    assert any(r.startswith("V2:image_x:like_what:") for r in reasons)
    rules = s.log.data["capture"]["templateRules"]
    assert rules[0]["stage"] == "find" and rules[0]["blocked"].get("like_what") == "all_anchor_candidates_are_image"


def test_like_what_once_per_session_even_with_non_image_x(exp_cfg):
    be = _Rule("like_what", pick="non_image")
    rt = make_rt(exp_cfg, be)
    s = rt.new_session("chatbot")
    # 첫 답에 형상 신호('돌 같은')가 있어 다리를 건너뛰고, 형상이 아닌 X('불안')로 LLM like_what이 한 번 나갈 수 있다
    run(s, ["돌 같은 불안이 있어요", "그냥 그래요", "무거워요", "가라앉아요", "없어요"])
    assert s.log.data["capture"]["bridge"]["asked"] is False
    assert question_templates(s).count("like_what") <= 1
    blocked = [r["blocked"].get("like_what") for r in s.log.data["capture"]["templateRules"]]
    if llm_like_what_sent(s):
        assert "max_per_session:1" in blocked


def test_bridge_counts_as_the_one_like_what(exp_cfg):
    be = _Rule("like_what", pick="non_image")
    rt = make_rt(exp_cfg, be)
    s = rt.new_session("chatbot")
    run(s, ["불안해요", "그냥 그래요", "가슴이 답답해요", "물결 같아요", "없어요"])
    assert s.log.data["capture"]["bridge"]["asked"] is True
    assert llm_like_what_sent(s) == []
    fl = [r for r in s.log.data["capture"]["templateRules"] if r["stage"] == "flesh_out"]
    # 다리를 낸 세션은 CP11(1.5부터) 규칙이 먼저 like_what을 빼고, 1.6 규칙도 같은 판정(1회 다 씀)이다
    assert fl and "like_what" not in fl[0]["allowed"] and fl[0]["history"].count("like_what") == 1


def test_no_immediate_repeat_with_what_kind_only_llm(exp_cfg):
    be = _Rule("what_kind")
    rt = make_rt(exp_cfg, be)
    s = rt.new_session("chatbot")
    run(s, ["돌 같아요", "단단한 돌", "회색 돌이에요", "차가운 돌", "없어요"])
    tpls = question_templates(s)
    assert all(not (a and a == b) for a, b in zip(tpls, tpls[1:])), tpls
    assert any(r["blocked"].get("what_kind") == "immediate_repeat" for r in s.log.data["capture"]["templateRules"])


# ── 결함 3: 이미 말한 차원 ───────────────────────────────────────────────────
def test_fog_asks_size_only_quoting_image_noun(ert):
    s = ert.new_session("chatbot")
    run(s, FOG)
    probes = s.log.data["capture"]["probes"]
    assert "size" in probes["asked"] and "size_shape" not in probes["asked"] and "shape" not in probes["asked"]
    t = next(t for t in s.log.turns if t.get("probe") == "size")
    assert t["text"] == "그 '먹구름'에 크기가 있나요?"
    assert t["referent"]["x"] == "먹구름" and any(sk.get("why") == "followed_by:모양" for sk in t["referent"]["skipped"])
    cov = t["coverage"]
    assert cov["rule"] == "mapper_slots_and_image_signal" and cov["fallback"] is False
    assert cov["dims"]["shape"]["covered"] and cov["dims"]["size"]["covered"] is False
    assert cov["decision"] == {"entry": "size_shape", "asked": "size", "phrase": "probe_size"}
    assert any(e["kind"] == "noun_before_shape" and e["trigger"] == "구름 모양" for e in cov["imageShape"])


def test_coverage_falls_back_to_lexicon_rule_when_mapper_raises(exp_cfg, monkeypatch):
    rt = Runtime(exp_cfg, persist_logs=False)

    def boom(*a, **k):
        raise RuntimeError("synthetic mapper failure")
    monkeypatch.setattr(rt.scene_builder, "build", boom)
    s = rt.new_session("chatbot")
    run(s, ["걱정이 많아요", "그냥 그래요", "가슴이 답답해요", "차가운 물 같아요"])
    probes = s.log.data["capture"]["probes"]
    assert probes["coverage"] and all(c["fallback"] and "mapperError" in c for c in probes["coverage"])
    assert probes["coverage"][0]["dims"]["shape"]["covered"] is True          # 비유 '물 같' = 형상 신호


# ── 결함 4: '그것' 없음 · 조건 1 ─────────────────────────────────────────────
def test_static_condition_fleshout_open_uses_referent(tmp_path):
    cfg = load_config("experiment").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "preview.mode": "none",
        "interview.lock_condition": False, "session.log_dir": str(tmp_path)})
    rt = Runtime(cfg, persist_logs=False)
    s = rt.new_session("static")
    run(s, ["검은 안개가 있는 느낌", "먹구름"])
    t = next(t for t in s.log.turns if t.get("source") == "fixed:fleshout_open")
    assert t["text"] == "지금 그 '먹구름'이 어떻게 있는지 떠오르는 대로 적어 주세요."
    assert all("그것" not in t["text"] for t in bot(s))


# ── 결함 5: 프롬프트 v1.2.0 맥락 ────────────────────────────────────────────
def test_prompt_v120_context_lists_covered_dims_and_used_templates():
    ps = PromptSet("1.2.0")
    ctx = PromptContext(stage="flesh_out", turn_no=2, max_turns=5, allowed_templates=["anything_else", "what_kind"],
                        transcript=[], participant_texts=["검은 안개가 있는 느낌"],
                        covered_dims=[{"dim": "shape", "words": ["안개"]}, {"dim": "color_brightness", "words": ["검은"]}],
                        used_templates=[{"template": "like_what", "count": 1, "blocked": "max_per_session:1"}])
    u = ps.user(ctx)
    assert "- shape ('안개')" in u and "- color_brightness ('검은')" in u
    assert "- like_what 1회 — 지금 쓸 수 없음(max_per_session:1)" in u
    assert "where" not in ps.common
    # 예전 판은 새 맥락을 무시한다(같은 출력)
    old = PromptSet("1.1.0")
    base = PromptContext(stage="flesh_out", turn_no=2, max_turns=5, allowed_templates=["anything_else"], transcript=[],
                         participant_texts=["검은 안개가 있는 느낌"])
    assert old.user(ctx) == old.user(PromptContext(**{**base.__dict__, "allowed_templates": ctx.allowed_templates}))


def test_experiment_llm_turn_gets_covered_dims_in_prompt(exp_cfg):
    be = ScriptedBackend([{"stage": "find", "risk_signal": "none", "move": "ask", "template": "anything_else",
                           "anchor_quote": "안개", "utterance": "'안개'에 대해 더 있나요?"}])
    rt = Runtime(exp_cfg, backend=be, persist_logs=False)
    s = rt.new_session("chatbot")
    s.start()
    s.reply("검은 안개가 있는 느낌")
    u = be.calls[0].user
    assert "[참여자가 이미 말한 차원" in u and "- shape ('안개')" in u
    assert "like_what" not in u.split("[이 단계에서 쓸 수 있는 질문 틀]")[1].split("\n")[0]


# ── 시나리오(연구 책임자 시험 입력) — 오프라인 대역 ─────────────────────────
@pytest.mark.parametrize("name", ["g70_researcher_fog", "g70_researcher_finish"])
def test_researcher_scenarios_offline(ert, name):
    sc = scenario(name)
    assert sc["researcherTestInput"] is True and sc["config"] == "experiment"
    s = ert.new_session("chatbot")
    drive(s, sc)
    assert check_expect(sc, session_metrics(s), s) == []


# ── 1.5·bridge 설정은 그대로 ─────────────────────────────────────────────────
def test_bridge_config_flow_and_log_keys_unchanged(tmp_path):
    cfg = load_config("bridge").with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(tmp_path)})
    rt = Runtime(cfg, persist_logs=False)
    s = rt.new_session("chatbot")
    run(s, ["설레요", "몸 주변이요", "없어요", "가슴이 조여요", "모르겠어요"])
    srcs = [t.get("source") for t in s.log.turns]
    assert "fixed:location" in srcs and "fixed:bridge_like_what_plain" in srcs
    cap = s.log.data["capture"]
    assert cap["bodyRelation"]["status"] != "not_asked"
    for k in ("templateRules", "findLlm"):
        assert k not in cap
    assert "coverage" not in (cap.get("probes") or {})
    assert not any("referent" in t or "coverage" in t for t in s.log.turns)
    assert rt.safety.version == "0.2.0" and rt.safety.is_stop("끝내고 싶어요")
