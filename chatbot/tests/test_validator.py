"""검증기 V1–V9. 노션 스토리보드의 '보이지 않은 턴' 예시를 그대로 회귀 테스트로 둔다."""
import json

import pytest

from conftest import turn
from ifs_chatbot.korean import Analyzer
from ifs_chatbot.lexicon import Lexicon
from ifs_chatbot.paths import shared
from ifs_chatbot.protocol import Protocol
from ifs_chatbot.safety import Guard, SafetyLexicon
from ifs_chatbot.validator import TurnContext, Validator, describe

P07 = ["가슴이 좀 답답해요", "가슴 안쪽이요", "젖은 종이처럼 축 처진 덩어리 같아요"]


@pytest.fixture(scope="module")
def v():
    a = Analyzer()
    schema = json.loads(shared("schemas", "interviewer_turn.schema.json").read_text(encoding="utf-8"))
    return Validator(Protocol(), Lexicon(shared("lexicon", "layer1_lexicon.v0.json"), a), SafetyLexicon(), a, schema)


@pytest.fixture
def ctx():
    p = Protocol()
    return TurnContext("flesh_out", p.allowed_templates("flesh_out"), list(P07), P07[-1])


def codes(result):
    return {":".join(r.split(":")[:2]) for r in result.reasons}


def test_storyboard_hidden_turn_is_blocked_by_v5(v, ctx):
    r = v.check(turn(utterance="그 '덩어리'는 차가운가요?"), ctx)
    assert not r.passed and "V5:leak:차갑" in r.reasons


@pytest.mark.parametrize("template,anchor,utt", [
    ("what_kind", "덩어리", "그 '덩어리'는 어떤 '덩어리'인가요?"),
    ("anything_else", "답답", "'답답'에 대해 더 있나요?"),
    ("like_what", "축 처진 덩어리", "그 '축 처진 덩어리'는 마치 무엇 같나요?"),
    ("relationship", "덩어리", "'덩어리'와 '가슴' 사이에는 어떤 관계가 있나요?"),
    ("then_what", "", "그리고 그다음에는 어떻게 되나요?"),
])
def test_clean_template_questions_pass(v, ctx, template, anchor, utt):
    r = v.check(turn(template=template, anchor=anchor, utterance=utt), ctx)
    assert r.passed, r.reasons


def test_batchim_particle_is_not_misread(v, ctx):
    """'그 '회색'은 …'에서 따옴표를 지우면 '은'이 명사로 분석돼 V5가 오탐했다(회귀)."""
    ctx.participant_texts.append("회색이고 무거워요")
    r = v.check(turn(template="like_what", anchor="회색", utterance="그 '회색'은 마치 무엇 같나요?"), ctx)
    assert r.passed, r.reasons


@pytest.mark.parametrize("utt,template,expected", [
    ("혹시 그 '덩어리'는 회색인가요?", "what_kind", "V5:leak"),          # 설계 노트 §6 금지 예
    ("그 '덩어리'는 어떤 크기인가요?", "what_kind", "V5:leak"),           # 새 차원 열기
    ("'덩어리'에 대해 더 있나요? 어디에 있나요?", "anything_else", "V4:question_count"),
    ("예를 들면 그 '덩어리'는 마치 무엇 같나요?", "like_what", "V6:banned"),
    ("힘드셨겠네요. '덩어리'에 대해 더 있나요?", "anything_else", "V6:banned"),
    ("왜 그 '덩어리'가 생겼나요?", "anything_else", "V6:banned"),
    ("그 부분, '덩어리'에 대해 더 있나요?", "anything_else", "V6:banned"),   # IFS 용어로 이름 붙이기
    ("그 '덩어리'는 어떤 '덩어리'인가요?", "where", "V7:template_marker"),
    ("그 '덩어리'은(는) 어떤 '덩어리'인가요?", "what_kind", "V7:template_literal"),
    ("그 '늘어진 덩어리'는 어떤 '덩어리'인가요?", "what_kind", "V3:quote_not_verbatim"),
])
def test_leading_or_malformed_questions_are_blocked(v, ctx, utt, template, expected):
    r = v.check(turn(template=template, anchor="덩어리", utterance=utt), ctx)
    assert not r.passed and expected in codes(r), r.reasons


def test_whole_sentence_quote_is_blocked(v, ctx):
    long_q = "젖은 종이처럼 축 처진 덩어리"
    r = v.check(turn(template="like_what", anchor=long_q, utterance=f"그 '{long_q}'는 마치 무엇 같나요?"), ctx)
    assert "V3:anchor_too_long" in codes(r)


def test_multiword_sentence_quote_blocked_but_single_predicate_ok(v):
    p = Protocol()
    texts = ["가슴이 조여요", "가슴 안쪽이요"]
    c = TurnContext("find", p.allowed_templates("find"), texts, texts[-1])
    bad = v.check(turn(stage="find", template="anything_else", anchor="가슴이 조여요",
                       utterance="'가슴이 조여요'에 대해 더 있나요?"), c)
    ok = v.check(turn(stage="find", template="anything_else", anchor="조여요", utterance="'조여요'에 대해 더 있나요?"), c)
    assert "V3:anchor_is_sentence" in codes(bad) and ok.passed, (bad.reasons, ok.reasons)


def test_stage_and_template_scope(v, ctx):
    r = v.check(turn(stage="find", template="anything_else", anchor="덩어리", utterance="'덩어리'에 대해 더 있나요?"), ctx)
    assert "V2:stage_mismatch" in codes(r)
    p = Protocol()
    find_ctx = TurnContext("find", p.allowed_templates("find"), list(P07), P07[-1])
    r = v.check(turn(stage="find", template="where", anchor="덩어리", utterance="그 '덩어리'는 어디쯤 있나요?"), find_ctx)
    assert "V2:template_not_allowed" in codes(r)


def test_schema_and_semantics(v, ctx):
    assert v.check("그 덩어리는요?", ctx).reasons == ["V1:json_parse"]
    assert "V1:schema" in codes(v.check(json.dumps({"stage": "flesh_out"}), ctx))
    held = v.check(turn(move="hold", risk="none", template="none", anchor="", utterance=""), ctx)
    assert held.reasons == ["V1:hold_without_risk_signal"]
    risk = v.check(turn(move="hold", risk="distress", template="none", anchor="", utterance=""), ctx)
    assert risk.passed and risk.l2_signal
    ready = v.check(turn(move="ready_to_advance", template="none", anchor="", utterance=""), ctx)
    assert ready.passed and not ready.l2_signal


def test_v9_blocks_quotes_from_memory_narratives(v):
    p = Protocol()
    texts = ["가슴이 조여요", "그때 친구들이 웃던 기억이 나요"]
    c = TurnContext("flesh_out", p.allowed_templates("flesh_out"), texts, texts[-1])
    r = v.check(turn(template="what_kind", anchor="친구", utterance="그 '친구'는 어떤 '친구'인가요?"), c)
    assert {"V9:depth_anchor", "V9:depth_context"} & codes(r), r.reasons


def test_v8_only_blames_what_the_interviewer_adds(fake_guard):
    """Kanana는 참여자 말만으로 S2를 내는 문장이 있다. 그 판정을 면담자 탓으로 돌리지 않는다."""
    human = "젖은 종이처럼 축 처진 덩어리 같아요"
    safe_q, harmful_q = "그 '덩어리'는 어떤 '덩어리'인가요?", "그 덩어리를 부숴 버리세요."
    g = Guard(SafetyLexicon(), fake_guard({
        (human, safe_q): ("UNSAFE", "S2"), (human, ""): ("UNSAFE", "S2"),
        (human, harmful_q): ("UNSAFE", "S2"), ("", harmful_q): ("UNSAFE", "S2"),
    }))
    assert g.check_output(human, safe_q).level == "safe"
    assert g.check_output(human, harmful_q).level != "safe"


def test_v8_catches_harm_added_in_context(fake_guard):
    human, reply = "가슴이 답답해요", "그런 생각을 하다니 한심하네요."
    g = Guard(SafetyLexicon(), fake_guard({(human, reply): ("UNSAFE", "S2")}))   # 질문만으로는 SAFE
    assert g.check_output(human, reply).level != "safe"


def test_describe_is_human_readable():
    assert describe("V5:leak:차갑") == "V5 참여자가 쓰지 않은 묘사어·차원어를 씀: '차갑'"
    assert "'왜'" in describe("V6:banned:why:왜")
