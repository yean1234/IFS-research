"""G82: [맞는 게 없어요] 뒤 규칙 그림 프롬프트에 중심 형태 명사가 없을 때 LLM이 형태 낱말 인용 + 영어 이름을 낸다(llm_shape.py).
첫 단계(오프라인) 시험. 모든 대사는 합성이다. LLM은 가짜 백엔드(정한 JSON을 돌려줌, 부른 횟수를 셈). Ollama·GPU를 부르지 않는다."""
import json
import sys
from pathlib import Path

import pytest

from ifs_chatbot import llm_fill as lf
from ifs_chatbot import llm_shape as ls
from ifs_chatbot import none_gen as ng
from ifs_chatbot.config import Gen3DConfig, load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.llm import BackendError

sys.path.insert(0, str(Path(__file__).parent))
from test_g73_none_gen import cfg, done_session  # noqa: E402
from test_g77_llm_fill import FakeLLM  # noqa: E402

T_PEBBLE = "디딤돌이 하나 있어요."              # 사전 밖 형태 낱말 → 규칙 no_shape_stated
T_TWICE = "디딤돌 옆에 또 디딤돌이 있어요."     # 같은 낱말이 두 번(위치 고치기를 하지 않음)
T_CUSHION = "쿠션 같은 거예요. 납작하고 푹신해요."  # 규칙은 꾸밈말만('flat') → 중심 명사 자리만 LLM
T_RULE = "엉킨 실타래 같아요. 가슴 앞에 있어요."    # 규칙이 형태를 잡음 → 부르지 않음
T_NOSHAPE = "쑥색이고 차가워요."
T_CAT = "고양이 같아요."                         # 규칙 차단(excluded_category) → 부르지 않음
# G84(형태 사전 0.3.0): 조약돌·돌덩이·자갈·벽돌·방석·베개·주전자가 규칙 사전에 들어가, 사전 밖 낱말 예를
# 디딤돌·고구마·몽돌·차돌·쿠션·바가지(0.3.0에 없음)로 바꿨다. 영어 이름은 가짜 LLM의 답이라 그대로 둔다.


def gcfg(tmp_path, on=True, **over):
    c = cfg(tmp_path).with_overrides(**{"gen3d.on_none_image_pick": True, "gen3d.on_none_llm_shape": on,
                                        "gen3d.on_none_llm_shape_timeout_s": 5.0,
                                        "selection.protocol": "selection_protocol.v0.12.json"})   # G82 문구 두 개(시작 점검)
    return c.with_overrides(**over) if over else c


def it(text, quote, en, span=None):
    s = text.index(quote) if span is None else span[0]
    return {"item": {"quote": quote, "charSpan": list(span or [s, s + len(quote)]), "en": en}}


def sess(tmp_path, text, reply=None, sid="SYN-G82", **over):
    llm = FakeLLM(reply if reply is not None else {"item": None}, delay=over.pop("delay", 0.0))
    rt = Runtime(gcfg(tmp_path, **over), backend=llm)
    s = done_session(rt, sid, text)
    return rt, s, llm


def run(s):
    return ls.run(s, s.scene_spec, s.log.data["confirmedText"])


# ── 설정·고정 파일 ───────────────────────────────────────────────────────────
def test_flag_off_by_default_and_in_every_config():
    g = Gen3DConfig()
    assert g.on_none_llm_shape is False and g.on_none_llm_shape_timeout_s == 20.0 and g.on_none_llm_shape_seed == 0
    for name in ("default", "pilot", "v4", "v4-gen3d", "bridge", "mac8gb"):
        assert load_config(name).gen3d.on_none_llm_shape is False, name
    assert load_config("experiment").gen3d.on_none_llm_shape is True        # G83: 실험 설정에서 켬(연구 책임자 결정)
    for name in ("llm_shape.v0.1.0.json", "llm_shape.v0.1.1.json", "llm_shape.v0.2.0.json", "llm_shape.v0.3.0.json"):
        p = ls.ShapePrompt(name)
        assert p.data["status"] == "draft" and p.data["options"]["temperature"] == 0 and p.data["decision"] == "G82"
        assert p.fill.path.name == "llm_fill.v0.1.1.json"                 # 검증기 목록은 G77 파일을 그대로 읽음
    assert ls.ShapePrompt().version == "0.3.0" and ls.ShapePrompt().allowed_stages == ("focus", "flesh_out")
    assert Gen3DConfig().on_none_llm_shape_prompt == "llm_shape.v0.3.0.json"


@pytest.mark.parametrize("over,needle", [
    ({"gen3d.on_none_image_pick": False}, "on_none_image_pick"),
    ({"gen3d.on_none": False}, "on_none이"),
    ({"mapping.mode": "v1"}, "mapping"),
])
def test_startup_refuses_missing_settings(tmp_path, over, needle):
    with pytest.raises(RuntimeError, match=needle):
        Runtime(gcfg(tmp_path, **over), backend=FakeLLM())


def test_g82_on_turns_off_only_g77_shape_slot(tmp_path):
    """G82가 켜지면 G77은 형태 낱말 칸만 내밀지 않는다(색 등 다른 빈 슬롯은 그대로)."""
    text = "쑥색 고구마 같은 게 있어요."
    offered = {}
    for on in (False, True):
        llm = FakeLLM({"items": []})
        c = gcfg(tmp_path / str(on), on=on, **{"mapping.llm_fill": True})
        rt = Runtime(c, backend=llm)
        s = done_session(rt, f"SYN-G82-G77-{on}", text)
        offered[on] = s.llm_fill["offeredSlots"]
        assert ls.g77_shape_slot_open(c) is (not on)
    assert lf.SHAPE_SLOT in offered[False] and lf.SHAPE_SLOT not in offered[True]
    assert [x for x in offered[False] if x != lf.SHAPE_SLOT] == offered[True] and offered[True]


def test_flag_off_outputs_and_records_unchanged(tmp_path):
    llm = FakeLLM(it(T_PEBBLE, "디딤돌이", "pebble"))
    rt = Runtime(gcfg(tmp_path, on=False), backend=llm)
    assert rt.llm_shape_prompt is None
    s = done_session(rt, "SYN-G82-OFF", T_PEBBLE)
    assert llm.calls == [] and s.llm_shape_cache == {}
    assert not [e for e in s.log.data["events"] if "llm_shape" in str(e.get("type"))]
    norm = s.log.data["confirmedText"]
    pm = ng._load_prompts()
    with ng._prompts_lock:
        a = pm.shape_prompt(norm, mapper_spec=s.scene_spec)
        b = pm.shape_prompt(norm, mapper_spec=s.scene_spec, llm_shape_items=None)
    assert a == b and a["blockReason"] == "no_shape_stated" and "shapeSource" not in a
    assert ng.shape_prompt(norm, s.scene_spec) == a                    # 서버 쪽 감싼 함수도 그대로


# ── 채택 ─────────────────────────────────────────────────────────────────────
def test_adopted_shape_word_fills_head_and_records(tmp_path):
    rt, s, llm = sess(tmp_path, T_PEBBLE, it(T_PEBBLE, "디딤돌이", "pebble"))
    rec = run(s)
    norm = s.log.data["confirmedText"]
    assert rec["status"] == "ok" and rec["called"] and rec["candidate"] and rec["rejectReasons"] == []
    assert rec["adopted"] == {"quote": "디딤돌이", "charSpan": [0, 4], "en": "pebble", "origin": "llm_translated"}
    assert rec["shapePromptText"].startswith("a single pebble, one solid object")
    # 입력 해시: LLM에 넣은 확정 텍스트 = 검증기 텍스트 = 세션 확정 텍스트, 사용자 메시지 안 구분 표시 사이에 그대로
    assert rec["inputTextSha256"] == rec["validatorTextSha256"] == ls.sha256_text(norm)
    user = llm.calls[0]["user"]
    assert ls.sha256_text(user) == rec["userSha256"] and f"확정 텍스트:\n{norm}\n" in user
    assert "면담자" not in user and llm.calls[0]["temperature"] == 0 and llm.calls[0]["seed"] == 0
    # 기록 자리: 모델 digest·프롬프트 판·해시·검증기 판·원시 출력, 다음 단계 칸은 None
    assert rec["model"]["digest"] == "sha256:" + "ab" * 32 and rec["prompt"]["promptVersion"] == "0.3.0"
    assert len(rec["prompt"]["promptSha256"]) == 64 and rec["validatorRules"] == ls.VALIDATOR_RULES
    assert rec["g77ValidatorRules"] == lf.VALIDATOR_RULES and json.loads(rec["rawText"])["item"]["en"] == "pebble"
    assert rec["exposure"] == {"exposed": None, "imageChosen": None, "basisRejected": None, "at": None}
    # 규칙이 붙인 문장·출처 표시
    with ng._prompts_lock:
        pm = ng._load_prompts()
        p = pm.shape_prompt(norm, mapper_spec=s.scene_spec, llm_shape_items=ls.shape_items_from(rec))
        q = pm.image_pick_prompt(p)
    assert p["shapeSource"] == "llm_translated" and p["builderVersion"].endswith("+llmshape-0.1.0")
    assert [t for t in p["tokens"] if t.get("provenance") == "llm_translated"][0]["ko"] == "디딤돌이"
    assert q["builderVersion"].endswith("+llmshape-0.1.0")


def test_modifier_only_rule_keeps_modifier_and_fills_head(tmp_path):
    rt, s, llm = sess(tmp_path, T_CUSHION, it(T_CUSHION, "쿠션", "cushion"))
    rec = run(s)
    assert rec["ruleRoute"]["reason"] == "modifier_only" and rec["status"] == "ok"
    assert rec["shapePromptText"].startswith("a single flat cushion,")


def test_span_repaired_only_when_quote_unique(tmp_path):
    rt, s, llm = sess(tmp_path, T_PEBBLE, it(T_PEBBLE, "디딤돌이", "pebble", span=[0, 3]))
    rec = run(s)
    assert rec["status"] == "ok" and rec["item"]["spanRepaired"] == {"llmCharSpan": [0, 3], "to": [0, 4]}
    rt, s, llm = sess(tmp_path / "b", T_TWICE, it(T_TWICE, "디딤돌", "pebble", span=[1, 4]), sid="SYN-G82-TW")
    rec = run(s)
    assert rec["status"] == "rejected" and "quote_mismatch" in rec["rejectReasons"]


def test_quote_not_in_text_rejected(tmp_path):
    rt, s, llm = sess(tmp_path, T_PEBBLE, {"item": {"quote": "몽돌이", "charSpan": [0, 3], "en": "gravel"}})
    rec = run(s)
    assert rec["status"] == "rejected" and rec["rejectReasons"][0] == "quote_mismatch" and rec["adopted"] is None


@pytest.mark.parametrize("text,quote,why", [
    ("디딤돌은 아니에요.", "디딤돌은", "negated"),
    ("예전에는 고구마였어요.", "고구마", "past_or_former"),
    ("친구가 디딤돌 같대요.", "디딤돌", "reported_speech"),
    ("차돌이면 좋겠어요.", "차돌", "hypothetical"),
    ("아마 몽돌일 거예요.", "몽돌", "hypothetical"),
    ("친구가 디딤돌 같대요.", "디딤돌", "korean_banned"),        # 문장 안 사람 명사(한국어 금지)
    ("고구마처럼 무거워요.", "고구마", "simile_of_predicate"),     # 속성 비유(그대로 막음)
    ("쑥색이고 차가워요.", "쑥색", "color_word"),
    ("그냥 답답하고 무거운 느낌이에요.", "느낌", "non_shape_noun"),
])
def test_validator_rejects_frames_and_korean_words(tmp_path, text, quote, why):
    rt, s, llm = sess(tmp_path, text, it(text, quote, "pebble"))
    rec = run(s)
    assert rec["status"] == "rejected" and why in rec["rejectReasons"], rec["rejectReasons"]


def test_shape_verb_simile_passes(tmp_path):
    t = "쿠션처럼 생겼어요."
    rt, s, llm = sess(tmp_path, t, it(t, "쿠션", "pillow"))
    rec = run(s)
    assert rec["status"] == "ok" and rec["item"]["exempted"] == ["simile_of_predicate:shape_verb"]


@pytest.mark.parametrize("en,why", [
    ("cat", "english_banned"), ("sparrow", "english_banned"), ("squirrel", "english_banned"), ("scarecrow", "english_banned"),
    ("skull", "english_banned"), ("hand", "english_banned"), ("fog", "non_meshable"), ("torch", "non_meshable"),
    ("candle", "non_meshable"), ("smoke", "non_meshable"),
    ("round pebble", "english_modifier"), ("glass bead", "english_non_shape"), ("wooden box", "english_modifier"),
    ("stone slab", "two_words"), ("fluffy cushion", "english_modifier"), ("two pebbles", "english_modifier"),
    ("small pebble", "english_color_size"), ("gray stone", "english_color_size"), ("heavy stone", "english_non_shape"),
    ("sad stone", "english_non_shape"), ("ball of yarn", "two_words"), ("Pebble", "english_format"),
    ("perfect pebble", "two_words"), ("yarn ball", "two_words"), ("pine cone", "two_words"),   # CP19-1: 한 낱말만
    ("smooth", "english_modifier"), ("round", "english_modifier"),
    ("pebble!", "english_format"), ("디딤돌", "english_format"),
])
def test_english_name_rules(tmp_path, en, why):
    assert why in ng._load_prompts().llm_shape_english_reasons(en)
    rt, s, llm = sess(tmp_path, T_PEBBLE, it(T_PEBBLE, "디딤돌이", en))
    rec = run(s)
    assert rec["status"] == "rejected" and why in rec["rejectReasons"]


@pytest.mark.parametrize("en", ["pebble", "stone", "pinecone", "skein", "plank", "bucket", "snowball", "brick"])
def test_english_plain_nouns_pass(en):
    assert ng._load_prompts().llm_shape_english_reasons(en) == []


def test_generator_recheck_fail_closed():
    pm = ng._load_prompts()
    norm = T_PEBBLE
    with ng._prompts_lock:
        good = pm.shape_prompt(norm, llm_shape_items=[{"quote": "디딤돌이", "charSpan": [0, 4], "en": "pebble"}])
        bad_q = pm.shape_prompt(norm, llm_shape_items=[{"quote": "디딤돌이", "charSpan": [0, 3], "en": "pebble"}])
        bad_en = pm.shape_prompt(norm, llm_shape_items=[{"quote": "디딤돌이", "charSpan": [0, 4], "en": "round pebble"}])
        two = pm.shape_prompt(norm, llm_shape_items=[{"quote": "디딤돌이", "charSpan": [0, 4], "en": "perfect pebble"}])
        with pytest.raises(ValueError, match="함께"):
            pm.shape_prompt(norm, llm_items=[{"quote": "디딤돌이", "charSpan": [0, 4], "english": "pebble"}],
                            llm_shape_items=[{"quote": "디딤돌이", "charSpan": [0, 4], "en": "pebble"}])
    assert good["status"] == "ok" and good["shapeSource"] == "llm_translated"
    assert bad_q["blockReason"] == bad_en["blockReason"] == two["blockReason"] == "no_shape_stated" and "shapeSource" not in bad_en


# ── 부르지 않는 경우 ─────────────────────────────────────────────────────────
def test_no_shape_stated_null_means_no_generation(tmp_path):
    rt, s, llm = sess(tmp_path, T_NOSHAPE, {"item": None})
    rec = run(s)
    assert rec["status"] == "null" and rec["called"] and not rec["candidate"] and rec["adopted"] is None
    assert ls.shape_items_from(rec) == []


@pytest.mark.parametrize("text,reason", [(T_RULE, "rule_has_shape"), (T_CAT, "rule_blocked:excluded_category")])
def test_rule_shape_or_block_means_no_call(tmp_path, text, reason):
    rt, s, llm = sess(tmp_path, text, it(text, text.split()[0], "pebble"))
    rec = run(s)
    assert rec["status"] == "skipped" and rec["skipReason"] == reason and llm.calls == [] and rec["called"] is False


class SpyCache(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.touched = 0

    def __contains__(self, k):
        self.touched += 1
        return super().__contains__(k)

    def __getitem__(self, k):
        self.touched += 1
        return super().__getitem__(k)

    def __setitem__(self, k, v):
        self.touched += 1
        super().__setitem__(k, v)


@pytest.mark.parametrize("mut", ["alert", "turn", "message"])
def test_flagged_session_no_call_and_no_cache_lookup(tmp_path, mut):
    rt, s, llm = sess(tmp_path, T_PEBBLE, it(T_PEBBLE, "디딤돌이", "pebble"))
    first = run(s)
    assert first["status"] == "ok" and len(llm.calls) == 1
    s.llm_shape_cache = SpyCache(s.llm_shape_cache)           # 앞 성공 결과가 캐시에 있음
    s.llm_shape_cache.touched = 0
    if mut == "alert":
        s.log.data["alerts"].append({"kind": "soft_check", "detail": "합성", "turn": 1, "severity": "warning"})
    elif mut == "turn":
        s.log.data["turns"][0]["crisisKeyword"] = True
    else:
        s.messages.append({"speaker": "bot", "text": "합성", "kind": "crisis", "source": "fixed:crisis", "i": 0})
    rec = run(s)
    assert rec["status"] == "skipped" and rec["skipReason"] == "session_flagged" and rec["adopted"] is None
    assert len(llm.calls) == 1 and s.llm_shape_cache.touched == 0     # 호출 0, 캐시 조회 0


def test_cache_hit_no_second_call_and_key_parts(tmp_path):
    rt, s, llm = sess(tmp_path, T_PEBBLE, it(T_PEBBLE, "디딤돌이", "pebble"))
    a = run(s)
    b = run(s)
    assert b["cached"] is True and b["adopted"] == a["adopted"] and len(llm.calls) == 1
    p = rt.llm_shape_prompt
    k = ls.cache_key(p, "sha256:x", 0, T_PEBBLE)
    assert k != ls.cache_key(p, "sha256:x", 1, T_PEBBLE) and k != ls.cache_key(p, "sha256:y", 0, T_PEBBLE)
    assert k != ls.cache_key(ls.ShapePrompt("llm_shape.v0.1.0.json"), "sha256:x", 0, T_PEBBLE)
    for part in (ls.VALIDATOR_RULES, lf.VALIDATOR_RULES, p.sha256, p.modifier_block["sha256"], p.fill.english_block["sha256"]):
        assert part in k


@pytest.mark.parametrize("reply,delay,status", [
    (BackendError("boom"), 0.0, "failed"),
    ("{not json", 0.0, "invalid_output"),
    ({"items": []}, 0.0, "invalid_output"),
    ({"item": None}, 0.6, "timeout"),
])
def test_failure_timeout_invalid_keep_rule_path(tmp_path, reply, delay, status):
    rt, s, llm = sess(tmp_path, T_PEBBLE, reply, delay=delay, **{"gen3d.on_none_llm_shape_timeout_s": 0.3})
    rec = run(s)
    assert rec["status"] == status and rec["adopted"] is None and ls.shape_items_from(rec) == []


def test_offline_backend_skips(tmp_path):
    rt = Runtime(gcfg(tmp_path))                                     # offline 대역: JSON 호출 없음
    s = done_session(rt, "SYN-G82-OFFL", T_PEBBLE)
    rec = run(s)
    assert rec["status"] == "skipped" and rec["skipReason"] == "backend_unsupported"


# ── 검증기 0.4.0(G82 다음 단계·CP19) ─────────────────────────────────────────
def test_same_text_different_spec_misses_cache(tmp_path):
    """CP19-2: 같은 확정 텍스트라도 검증에 쓰는 spec 부분(뺀 구간 등)이 다르면 캐시를 쓰지 않고 다시 부른다."""
    rt, s, llm = sess(tmp_path, T_PEBBLE, it(T_PEBBLE, "디딤돌이", "pebble"))
    norm = s.log.data["confirmedText"]
    a = run(s)
    spec2 = json.loads(json.dumps(s.scene_spec))
    spec2.setdefault("_negated", []).append({"lemma": "디딤돌", "_provenance": {"charSpan": [0, 3]}})
    b = ls.propose(rt.llm_shape_prompt, llm, norm, spec2, seed=0, timeout_s=5.0, cache=s.llm_shape_cache, flag=None)
    assert a["status"] == "ok" and b["cached"] is False and len(llm.calls) == 2
    assert a["validationInputSha256"] != b["validationInputSha256"] and a["cacheKey"] != b["cacheKey"]
    assert b["status"] == "rejected" and "negated" in b["rejectReasons"]
    c = ls.propose(rt.llm_shape_prompt, llm, norm, spec2, seed=0, timeout_s=5.0, cache=s.llm_shape_cache, flag=None)
    assert c["cached"] is True and len(llm.calls) == 2
    assert set(a["prompt"]["koreanLexicons"]) == set(ls.KOREAN_LEXICONS) and a["rule"]["mapperBuilder"]


def test_form_span_used_by_mapper_is_open_when_rule_has_no_head(tmp_path):
    t = "차돌 같은 게 박혀 있어요."
    rt, s, llm = sess(tmp_path, t, it(t, "차돌", "brick"))
    assert any(str(p).startswith("form.") for p in (s.scene_spec.get("_provenance") or {}))   # 매퍼가 form.*에 씀
    rec = run(s)
    assert rec["status"] == "ok" and rec["formSpansOpened"] and rec["formSpansOpened"][0]["text"].startswith("차돌")
    assert "span_covered" not in rec["rejectReasons"]


def test_other_slot_span_still_covered(tmp_path):
    t = "회색 덩이 같은 게 있어요. 회색이 짙어요."
    rt, s, llm = sess(tmp_path, t, it(t, "회색", "slate"))
    rec = run(s)
    assert rec["status"] in ("rejected", "skipped")
    if rec["status"] == "rejected":
        assert "span_covered" in rec["rejectReasons"] or "color_word" in rec["rejectReasons"]


def interview_session(tmp_path, replies, reply, sid="SYN-G82-ST", edit=None):
    from ifs_chatbot.simulate import drive
    llm = FakeLLM(reply)
    rt = Runtime(gcfg(tmp_path), backend=llm)
    s = rt.new_session("static", sid)
    drive(s, {"id": sid, "replies": list(replies), "defaultReply": "없어요",
              "confirm": {"edit": edit} if edit is not None else "confirm"})
    assert s.state == "done"
    return rt, s, llm


WORRY = ["노트북 앞에서 보고서를 쓰는 게 걱정이에요", "가슴이 답답해요", "어둡고 무거워요"]


def test_stage_rule_rejects_quote_from_worry_line(tmp_path):
    norm = "\n".join(WORRY)
    rt, s, llm = interview_session(tmp_path, WORRY, it(norm, "노트북", "laptop"))
    rec = run(s)
    assert rec["lineStages"]["status"] == "applied" and rec["lineStages"]["stages"][0] == "find"
    assert rec["status"] == "rejected" and "non_shape_stage_line" in rec["rejectReasons"]
    assert rec["item"]["lineStage"] == "find"


def test_stage_rule_keeps_shape_line(tmp_path):
    lines = ["회사 일이 걱정이에요", "가슴이 답답해요", "디딤돌 같은 게 있어요"]
    norm = "\n".join(lines)
    rt, s, llm = interview_session(tmp_path, lines, it(norm, "디딤돌", "pebble"), sid="SYN-G82-ST2")
    rec = run(s)
    assert rec["lineStages"]["status"] == "applied" and rec["status"] == "ok"
    assert rec["item"]["lineStage"] in ("focus", "flesh_out")


def test_stage_rule_unavailable_when_text_edited(tmp_path):
    norm = "\n".join(WORRY)
    rt, s, llm = interview_session(tmp_path, WORRY, it(norm, "노트북", "laptop"), sid="SYN-G82-ST3", edit=norm)
    rec = run(s)
    assert rec["lineStages"] == {"status": "unavailable", "reason": "edited", "lines": 3, "stages": None}
    assert "non_shape_stage_line" not in rec["rejectReasons"]              # 표지가 없으면 단계 규칙을 걸지 않음(기록만)


@pytest.mark.parametrize("text", ["참새 같은 게 앉아 있어요.", "다람쥐 같은 게 웅크리고 있어요.", "뱀 같은 게 있어요."])
def test_korean_animal_words_blocked_by_rule(tmp_path, text):
    """A3: 형태 사전 0.2.1 blocked.animal 보강 → 규칙이 막아 LLM을 부르지 않는다."""
    rt, s, llm = sess(tmp_path, text, it(text, text.split()[0], "bird"))
    rec = run(s)
    assert rec["status"] == "skipped" and rec["skipReason"] == "rule_blocked:excluded_category" and llm.calls == []


@pytest.mark.parametrize("text", ["바가지처럼 단단해요.", "바가지처럼 묵직해요.", "바가지처럼 딱딱해요.", "바가지같이 싸늘해요.",
                                  "바가지처럼 답답해요.", "바가지처럼 무거워요.", "바가지처럼 차가워요.", "바가지처럼 단단하게 생겼어요."])
def test_simile_of_root_predicate_rejected(tmp_path, text):
    """검증기 0.5.0(G77 0.4.0): 2차 평가 오통과 17건의 꼴. XR 서술어와 VA 서술어 모두 속성 비유로 막는다."""
    rt, s, llm = sess(tmp_path, text, it(text, "바가지", "kettle"))
    rec = run(s)
    assert rec["status"] == "rejected" and "simile_of_predicate" in rec["rejectReasons"], rec["rejectReasons"]
