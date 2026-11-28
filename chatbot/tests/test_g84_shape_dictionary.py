"""G84: 규칙 형태 사전(shared/lexicon/shape_prompt_en.v0.json) 0.3.0 — 형태 명사 117낱말을 더함.
2026-11-28 연구 책임자 결정: 원칙 2 유지 + 사전 넓히기. LLM 없이 같은 한국어 낱말 → 언제나 같은 영어 형태 이름.
모든 문장은 합성이다. LLM은 가짜 백엔드(부른 횟수를 셈). Ollama·GPU를 부르지 않는다.
낱말별 근거·점검 수치: docs/validation/run-g84-shape-dictionary/README.md"""
import json
import re
import sys
import tempfile
from pathlib import Path

import pytest

from ifs_chatbot import llm_fill as lf
from ifs_chatbot import llm_shape as ls
from ifs_chatbot import none_gen as ng
from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.paths import shared
from ifs_chatbot.scene_builder import normalize_confirmed

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import done_session  # noqa: E402
from test_g77_llm_fill import FakeLLM  # noqa: E402
from test_g82_llm_shape import gcfg, sess  # noqa: E402

LEX = json.loads(shared("lexicon", "shape_prompt_en.v0.json").read_text(encoding="utf-8"))

# 더한 낱말 → 영어(사전 0.3.0). Kiwi가 둘로 나누는 꼴(돌+덩어리 등)은 사전에 따로 항목이 있고 영어는 같다.
WORDS = {
    "돌덩이": "rock", "돌덩어리": "rock", "바윗덩이": "boulder", "바윗덩어리": "boulder", "쇳덩이": "lump", "흙덩이": "clod",
    "얼음덩어리": "lump", "얼음덩이": "lump", "눈덩이": "snowball", "눈뭉치": "snowball", "조약돌": "pebble", "자갈": "gravel",
    "벽돌": "brick", "맷돌": "millstone", "블록": "block", "타일": "tile", "통나무": "log", "고드름": "icicle",
    "판때기": "board", "널빤지": "plank", "판자": "plank", "방석": "cushion", "베개": "pillow", "이불": "quilt",
    "담요": "blanket", "수건": "towel", "매트": "mat", "원반": "disc", "동전": "coin", "거울": "mirror", "도마": "board",
    "바구니": "basket", "양동이": "bucket", "냄비": "pot", "뚝배기": "pot", "주전자": "kettle", "찻잔": "teacup",
    "머그잔": "mug", "밥그릇": "bowl", "쟁반": "tray", "대야": "basin", "장독": "crock", "드럼통": "barrel", "궤짝": "crate",
    "나무상자": "box", "가방": "bag", "봉지": "bag", "보따리": "bundle", "봉투": "envelope", "모래주머니": "sandbag",
    "쌀자루": "sack", "화분": "flowerpot", "깔때기": "funnel", "프라이팬": "skillet", "쇠사슬": "chain", "사슬": "chain",
    "철사": "wire", "노끈": "twine", "호스": "hose", "파이프": "pipe", "튜브": "tube", "털실타래": "skein", "그물": "net",
    "용수철": "coil", "유리구슬": "bead", "야구공": "ball", "골프공": "ball", "주사위": "dice", "톱니바퀴": "gear",
    "타이어": "tire", "반지": "ring", "목걸이": "necklace", "왕관": "crown", "골무": "thimble", "모자": "hat", "신발": "shoe",
    "열쇠": "key", "자물쇠": "padlock", "나사": "screw", "자석": "magnet", "닻": "anchor", "깃발": "flag", "우산": "umbrella",
    "의자": "chair", "사다리": "ladder", "숟가락": "spoon", "국자": "ladle", "연필": "pencil", "빗자루": "broom",
    "붓": "brush", "지우개": "eraser", "비누": "soap", "망원경": "telescope", "돋보기": "magnifier", "나침반": "compass",
    "주판": "abacus", "모래시계": "hourglass", "옷걸이": "hanger", "지팡이": "cane", "울타리": "fence", "텐트": "tent",
    "우체통": "mailbox", "절구": "mortar", "삽": "shovel", "갈퀴": "rake", "도토리": "acorn", "호두": "walnut",
    "솔방울": "pinecone", "감자": "potato", "당근": "carrot", "양파": "onion", "수박": "watermelon", "레몬": "lemon",
    "귤": "tangerine", "땅콩": "peanut", "배추": "cabbage", "만두": "dumpling",
}
G84_ENTRIES = [e for e in LEX["entries"] if "".join(e["ko"]) in WORDS and e["pos"] == "noun"]
G84_KEYS = {"+".join(e["ko"]) for e in G84_ENTRIES}


def batchim(w):
    c = ord(w[-1]) - 0xAC00
    return 0 <= c < 11172 and c % 28 != 0


@pytest.fixture(scope="module")
def mapper():
    """실험 설정(experiment.toml)의 매퍼 v2 — [맞는 게 없어요] 뒤 세션이 쓰는 spec과 같은 builder."""
    logs = tempfile.mkdtemp(prefix="ifs-g84-test-logs-")
    cfg = load_config("experiment").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none",
                                                       "session.log_dir": logs, "preview.mode": "none"})
    rt = Runtime(cfg)

    def run(text, stage_rule=None):
        norm = normalize_confirmed(text)
        spec = rt.scene_builder.build(norm, session_id="SYN-G84", participant_id="SYN")
        spec = spec if isinstance(spec, dict) else spec.to_dict()
        with ng._prompts_lock:
            pm = ng._load_prompts()
            p = pm.shape_prompt(norm, mapper_spec=spec, stage_rule=stage_rule)
            route = ls.rule_route(pm, p)
        return p, route
    return run


def heads(p):
    return [t for t in p.get("tokens") or [] if t.get("slot") == "shape_noun"]


# ── 사전 파일 ────────────────────────────────────────────────────────────────
def test_lexicon_version_and_source():
    assert LEX["lexiconVersion"] == "0.3.1"                                  # G85 3차: 0.3.1 = 0.3.0 + 다리미 한 항목
    assert LEX["changes"][0]["version"] == "0.3.1" and "다리미" in LEX["changes"][0]["what"]
    ch = next(c for c in LEX["changes"] if c["version"] == "0.3.0")
    assert ch["version"] == "0.3.0" and "2026-11-28 G84, 연구 책임자 결정: 원칙 2 유지 + 사전 넓히기" in ch["what"]
    assert 60 <= len(WORDS) <= 120
    # 낱말마다 사전 항목이 있고(붙여 쓴 꼴), 같은 낱말의 모든 항목이 같은 영어를 낸다
    by_word = {}
    for e in G84_ENTRIES:
        by_word.setdefault("".join(e["ko"]), set()).add(e["en"])
    assert set(by_word) == set(WORDS)
    assert all(v == {WORDS[k]} for k, v in by_word.items())
    # 항목 꼴은 기존과 같다(구조를 바꾸지 않음)
    assert all(set(e) <= {"ko", "pos", "en", "slot", "thin", "familiar", "plural"} and e["slot"] == "shape_noun"
               for e in G84_ENTRIES)


def test_primitive_forms_rechecked_for_new_lexicon():
    prim = json.loads(shared("lexicon", "primitive_forms.v0.json").read_text(encoding="utf-8"))
    assert prim["keyedTo"]["lexiconVersion"] == LEX["lexiconVersion"]
    assert not ({e["lexiconKey"] for e in prim["entries"]} & G84_KEYS)       # 더한 낱말은 모두 사물 → 단순 도형 아님


@pytest.mark.parametrize("en", sorted(set(WORDS.values())))
def test_english_single_word_and_not_blocked(en):
    pm = ng._load_prompts()
    assert re.fullmatch(r"[a-z]+", en)
    assert pm.english_shape_reasons(en) == [] and pm.llm_shape_english_reasons(en) == []


# ── 규칙 프롬프트의 중심 명사 ────────────────────────────────────────────────
@pytest.mark.parametrize("word", sorted(WORDS))
def test_new_word_is_rule_head_noun(mapper, word):
    ga = "이" if batchim(word) else "가"
    for text in (f"{word} 같은 게 있어요.", f"가슴 앞에 {word}{ga} 있어요."):
        p, (call, why) = mapper(text)
        h = heads(p)
        assert p["status"] == "ok" and h and h[-1]["en"] == WORDS[word], (text, p["blockReason"], p["dropped"])
        assert h[-1]["ko"] == word and h[-1]["lexiconKey"] in G84_KEYS and "provenance" not in h[-1]
        assert p["text"].startswith(f"a single {WORDS[word]}, one solid object")
        assert (call, why) == (False, "rule_has_shape")                     # G82 LLM을 부르지 않음
        assert p["blockReason"] != "no_shape_stated"                         # G77 형태 칸도 열리지 않음


def test_same_text_same_result(mapper):
    a, _ = mapper("돌덩이예요.")
    b, _ = mapper("돌덩이예요.")
    assert a == b and a["text"].startswith("a single rock,") and a["lexiconVersion"] == "0.3.1"


@pytest.mark.parametrize("word", sorted(WORDS))
def test_negated_new_word_does_not_start(mapper, word):
    eun = "은" if batchim(word) else "는"
    p, _ = mapper(f"{word}{eun} 아니에요.")
    # '그물은'·'눈뭉치는'은 Kiwi가 다른 꼴로 나눠 사전에 맞지 않고(그+물 등) 그대로 막힌다. 맞으면 부정으로 뺀다
    assert p["status"] == "blocked" and all(d["reason"] == "negated" for d in p["dropped"] if d["ko"].startswith(word))


# 동음이의어·형태가 아닌 쓰임: 새 항목이 잡히면 안 된다(점검에서 잡힌 '동전 세 개 크기'·'주사위는 던져졌어요'는 README에 보고)
HOMONYM = ["다리가 붓고 아파요.", "얼굴이 부어 있어요.", "모자 사이가 좋아요.", "동생이 나사에서 일해요.",
           "유튜브를 오래 봐서 눈이 아파요.", "먹이사슬 맨 위에 있는 느낌이에요.", "블록체인 공부가 걱정이에요.", "일이 모자라요.",
           "동전만 해요.", "수박만 한 크기예요.", "의자에 앉아 있는 느낌이에요.", "이불 속에 들어가 있는 것 같아요.",
           "텐트 안에 있는 것 같아요.", "울타리 밖에 있는 느낌이에요.", "눈이 와요.", "양동작전 같아요.", "판단이 안 서요."]


@pytest.mark.parametrize("text", HOMONYM)
def test_homonym_or_non_shape_use_not_caught(mapper, text):
    p, _ = mapper(text)
    assert not [t for t in p.get("tokens") or [] if t.get("lexiconKey") in G84_KEYS], (p["tokens"], p["dropped"])


# ── G82·G77과의 관계(세션) ───────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["돌덩이예요.", "조약돌이 하나 있어요.", "판때기예요. 겨자색이고 반지르르해요."])
def test_rule_word_means_g82_not_called(tmp_path, text):
    rt, s, llm = sess(tmp_path, text, {"item": {"quote": text[:3], "charSpan": [0, 3], "en": "rock"}})
    rec = ls.run(s, s.scene_spec, s.log.data["confirmedText"])
    assert rec["status"] == "skipped" and rec["skipReason"] == "rule_has_shape" and llm.calls == [] and rec["called"] is False


def test_rule_word_closes_g77_shape_slot_when_g82_off(tmp_path):
    """G82를 끈 설정에서도 규칙이 형태 명사를 잡으면 G77은 형태 낱말 칸(shape_noun)을 내밀지 않는다(다른 빈 칸은 그대로)."""
    c = gcfg(tmp_path, on=False, **{"mapping.llm_fill": True})
    rt = Runtime(c, backend=FakeLLM({"items": []}))
    s = done_session(rt, "SYN-G84-G77", "쑥색 돌덩이 같은 게 있어요.")
    assert lf.SHAPE_SLOT not in s.llm_fill["offeredSlots"] and s.llm_fill["offeredSlots"]


# ── 생성 경로 문맥 규칙(G84 후속, 규칙 판 gen3d-shape-prompt/0.5.0) ───────────────────────────
# 규칙 그림 프롬프트가 G77·G82 검증기와 같은 함수(llm_fill.frame_reasons·simile_of_predicate, llm_shape._simile_of_shape_verb·
# line_stage_reason)로 과거·전언·가정·속성 비유·형태를 묻지 않은 단계 줄의 낱말을 쓰지 않는다. 매퍼 spec은 그대로다.
FRAME_CASES = [("예전에는 돌덩이였어요.", "past_or_former"), ("처음엔 벽돌 같았어요.", "past_or_former"),
               ("친구가 조약돌 같대요.", "reported_speech"), ("벽돌이면 좋겠어요.", "hypothetical"),
               ("아마 자갈일 거예요.", "hypothetical"), ("돌덩이처럼 단단해요.", "simile_of_predicate"),
               ("예전에는 공이었어요.", "past_or_former")]                       # 0.2.1부터 있던 낱말(공)도 같이


@pytest.mark.parametrize("text,why", FRAME_CASES)
def test_frame_word_not_used_for_generation(mapper, text, why):
    p, (call, route) = mapper(text)
    assert p["status"] == "blocked" and p["blockReason"] == "no_shape_stated" and (call, route) == (True, "no_shape_stated")
    d = [x for x in p["dropped"] if x["reason"] == why]
    assert d and why in d[0]["frameReasons"]
    assert p["builderVersion"] == "gen3d-shape-prompt/0.6.0+mapper-v2"


@pytest.mark.parametrize("text,en", [("돌덩이처럼 생겼어요.", "rock"), ("돌덩이 같아요.", "rock"), ("돌덩이 같은 게 있어요.", "rock"),
                                     ("예전에는 공이었는데 지금은 돌덩이예요.", "rock")])
def test_shape_statement_kept(mapper, text, en):
    p, _ = mapper(text)
    assert p["status"] == "ok" and heads(p)[-1]["en"] == en


def test_worry_line_noun_dropped_by_stage_rule(mapper):
    srule = ls.stage_rule({"status": "applied", "stages": ["find", "focus", "flesh_out"]}, ("focus", "flesh_out"))
    text = "\n".join(["가방 때문에 요즘 신경 쓰여요.", "가슴이 답답해요.", "공 같은 게 있어요."])
    p, _ = mapper(text, srule)
    assert heads(p)[-1]["en"] == "ball"
    assert {"ko": "가방", "charSpan": [0, 2], "reason": "non_shape_stage_line", "frameReasons": ["non_shape_stage_line"]} in p["dropped"]
    p0, _ = mapper(text)                                    # 단계 표지가 없으면(확정 텍스트를 고친 세션 등) 단계 규칙을 걸지 않음
    assert heads(p0)[-1]["en"] == "bag"


def test_mapper_spec_unchanged_by_frame_rule(mapper):
    """차단은 생성 경로에만 — 매퍼 spec(확정 스펙)은 그대로(같은 builder가 같은 결과)."""
    p, _ = mapper("예전에는 돌덩이였어요.")
    assert p["status"] == "blocked"
    with ng._prompts_lock:
        pm = ng._load_prompts()
        spec = pm._shape_runtime().excluder.build(normalize_confirmed("예전에는 돌덩이였어요."))
    assert any(u.get("lemma") == "돌덩이" for u in spec.get("_unmapped") or [])


@pytest.mark.parametrize("text,quote,why", [(t, w, r) for t, r in FRAME_CASES[:6]
                                            for w in [next(x for x in WORDS if x in t)]])
def test_g82_does_not_revive_rule_blocked_word(tmp_path, text, quote, why):
    """규칙이 문맥으로 뺀 낱말을 G82 LLM이 다시 내도 검증기가 같은 규칙으로 기각한다(채택 없음 → 생성 안 함)."""
    rt, s, llm = sess(tmp_path, text, {"item": {"quote": quote, "charSpan": [text.index(quote), text.index(quote) + len(quote)],
                                               "en": WORDS[quote]}})
    rec = ls.run(s, s.scene_spec, s.log.data["confirmedText"])
    assert rec["called"] and rec["status"] == "rejected" and why in rec["rejectReasons"] and rec["adopted"] is None


def test_g82_does_not_revive_worry_line_word(tmp_path):
    from test_g82_llm_shape import interview_session
    lines = ["가방 때문에 요즘 신경 쓰여요", "가슴이 답답해요", "어둡고 무거워요"]
    norm = "\n".join(lines)
    rt, s, llm = interview_session(tmp_path, lines, {"item": {"quote": "가방", "charSpan": [0, 2], "en": "bag"}}, sid="SYN-G84-W")
    rec = ls.run(s, s.scene_spec, s.log.data["confirmedText"])
    assert rec["ruleRoute"]["reason"] == "no_shape_stated" and rec["rule"]["builderVersion"].startswith("gen3d-shape-prompt/0.6.0")
    assert rec["status"] == "rejected" and "non_shape_stage_line" in rec["rejectReasons"] and rec["adopted"] is None
    assert norm == s.log.data["confirmedText"]
