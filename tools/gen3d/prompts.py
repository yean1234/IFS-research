"""한국어 서술 → 영어 프롬프트. 두 방식.

1. rules (기본, 화이트박스): 기존 규칙 추출기(SceneSpecBuilderV1)가 만든 SceneSpec의 **말한 값만**
   고정 표로 영어 낱말에 옮겨 조립한다. 같은 spec → 언제나 같은 프롬프트. LLM 없음(원칙 1과 맞음).
   말하지 않은 슬롯은 프롬프트에 넣지 않는다(원칙 2). 다만 생성 모델이 그 빈칸을 스스로 채운다는 점은
   여기서 막을 수 없다 — docs/gen3d-feasibility.md 「원칙과의 관계」.
2. llm (비교용): 로컬 Ollama(gemma4:e4b)로 번역. temperature 0 + seed 고정. **원칙 1(LLM은 유도 단계만)과
   충돌**하므로 실험 비교용으로만 쓴다. 모델은 태그가 아니라 digest로 기록한다(원칙 5).

두 방식 모두 생성 모델용 "촬영 조건" 꼬리말(단일 물체·가운데·흰 배경)을 붙인다. 이것은 심상 속성이 아니라
image→3D 단계가 물체를 배경과 분리하려고 필요한 시스템 문구이며, 메타데이터에 따로 남긴다.
"""
from __future__ import annotations

import json
import sys
import types
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHATBOT, sha256_text  # noqa: E402

RULES_VERSION = "gen3d-prompt-rules/0.1.0"

# form.type → 명사구
FORM_NOUN = {
    "blob": "rounded lump",
    "mist": "cloud of mist",
    "shell": "cracked open shell",
    "fragments": "cluster of small fragments",
}
# _unmapped의 모양어(category shape) → 형용사/명사. docs/shape-mapping.md의 모양 값 목록과 같은 키.
SHAPE_WORD = {
    "round": ("round", None), "square": ("square", "cube"), "flat": ("flat", None), "pointed": ("pointed", None),
    "dot": ("dot-like", None), "thin": ("thin", None), "thread": (None, "thread"), "hollow": ("hollow", None),
    "long": ("long", None), "sharp": ("sharp", None), "sheet": ("sheet-like", None), "angular": ("angular", None),
    "bumpy": ("bumpy", None), "circle": ("circular", None), "elongated": ("elongated", None), "hole": ("holed", None),
    "knot": ("knotted", None), "line": ("line-like", None), "string": (None, "string"), "thick": ("thick", None),
    "triangle": ("triangular", None), "edge": (None, None), "boundary": (None, None),
}
# form.posture(스키마 enum) → 영어. 표에 없는 값은 밑줄만 공백으로.
POSTURE = {"curled": "curled up", "turned_away": "turned away", "lying": "lying down", "prone": "lying face down"}

# 색 이름: HSL → 가장 가까운 기준 이름(고정 표, 결정적). 무채색은 명도로만.
HUE_NAMES = [(0, "red"), (20, "orange"), (40, "amber"), (55, "yellow"), (75, "yellow-green"), (120, "green"),
             (165, "teal"), (195, "sky blue"), (220, "blue"), (250, "indigo"), (280, "purple"), (320, "pink"),
             (345, "red")]


def color_name(c: dict) -> str:
    h, s, l = float(c["h"]) * 360.0, float(c["s"]), float(c["l"])
    if s < 0.12:
        if l < 0.2:
            return "black"
        if l < 0.4:
            return "dark gray"
        if l < 0.7:
            return "gray"
        if l < 0.9:
            return "light gray"
        return "white"
    # 원형 거리로 가장 가까운 기준 색상
    name = min(HUE_NAMES, key=lambda t: min(abs(h - t[0]), 360 - abs(h - t[0])))[1]
    if 15 <= h < 45 and l < 0.42:
        name = "brown"
    tone = ""
    if l < 0.3:
        tone = "dark "
    elif l > 0.72:
        tone = "pale "
    elif s < 0.3:
        tone = "muted "
    return tone + name


def _band(v, lo_word, hi_word, lo=0.35, hi=0.65):
    if v is None:
        return None
    if v <= lo:
        return lo_word
    if v >= hi:
        return hi_word
    return None


def rules_prompt(spec: dict) -> dict:
    """SceneSpec(v2.1) → 영어 프롬프트. 쓴 슬롯과 근거 낱말을 함께 돌려준다."""
    used: dict[str, str] = {}
    adjs: list[str] = []
    noun = "object"
    form = (spec.get("form") or {})
    mat = (spec.get("material") or {})
    if form.get("type"):
        noun = FORM_NOUN.get(form["type"], noun)
        used["form.type"] = form["type"]
    # 모양어: form.type이 없거나 blob일 때만 명사를 바꾼다(Unity ShapeMapping 규칙 4와 같은 우선순위).
    shapes = sorted((u for u in spec.get("_unmapped") or [] if u.get("category") == "shape"),
                    key=lambda u: ((u.get("_provenance") or {}).get("charSpan") or [0])[0])
    for u in shapes:
        val = (u.get("value") or {}).get("shape")
        adj, n = SHAPE_WORD.get(val, (None, None))
        if adj and adj not in adjs:
            adjs.append(adj)
        if n and form.get("type") in (None, "blob"):
            noun = n
        if adj or n:
            used.setdefault("shape", "")
            used["shape"] = (used["shape"] + " " + str(val)).strip()
    if form.get("posture"):
        adjs.append(POSTURE.get(form["posture"], form["posture"].replace("_", " ")))
        used["form.posture"] = form["posture"]
    if mat.get("color"):
        adjs.insert(0, color_name(mat["color"]))
        used["material.color"] = json.dumps(mat["color"])
    for key, words in (("brightness", ("dark", "glowing")), ("roughness", ("smooth glossy", "rough")),
                       ("erosion", (None, "eroded crumbling"))):
        w = _band(mat.get(key), *words)
        if w:
            adjs.append(w)
            used["material." + key] = str(mat.get(key))
    op = mat.get("opacity")
    if op is not None and op < 0.7:
        adjs.append("translucent" if op >= 0.3 else "nearly transparent")
        used["material.opacity"] = str(op)
    subject = ("a single " + " ".join(adjs) + " " + noun).replace("  ", " ")
    return {"subject": subject, "usedSlots": used, "rulesVersion": RULES_VERSION,
            "nothingStated": not used}


# ── LLM 번역(비교용, 원칙 1과 충돌) ─────────────────────────────────────────────
OLLAMA = "http://127.0.0.1:11434"
LLM_MODEL = "gemma4:e4b"
LLM_INSTRUCTION = (
    "You convert a Korean description of a mental image into a short English noun phrase describing ONE "
    "physical object for a 3D generator. Keep only the object's appearance that the text states: shape, color, "
    "material, surface, transparency, brightness. Do not add any colors, materials, or details that are not in "
    "the text. Omit body locations, feelings, memories, scenes, motion, and size. If the text states nothing "
    "about appearance, answer exactly: an object. Answer with the phrase only, no quotes.\n\nKorean text:\n"
)


def ollama_digest(model: str = LLM_MODEL) -> str | None:
    with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as r:
        tags = json.load(r)
    for m in tags.get("models", []):
        if m.get("name") == model or m.get("model") == model:
            return m.get("digest")
    return None


def llm_prompt(text: str, seed: int = 0) -> dict:
    body = {"model": LLM_MODEL, "prompt": LLM_INSTRUCTION + text, "stream": False, "think": False,
            "keep_alive": 0,                         # 끝나면 VRAM을 비운다(3D 모델과 겹치지 않게)
            "options": {"temperature": 0, "seed": seed, "num_predict": 80}}
    req = urllib.request.Request(OLLAMA + "/api/generate", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    phrase = out.get("response", "").strip().strip('"').strip().rstrip(".")
    return {"subject": phrase, "llm": {"model": LLM_MODEL, "digest": ollama_digest(),
                                       "instructionSha256": sha256_text(LLM_INSTRUCTION),
                                       "options": body["options"]}}


# ── SceneSpec 만들기(기존 규칙 경로, 코드 무수정으로 호출) ──────────────────────────
_builder = None


def build_spec(text: str, sid: str) -> dict:
    global _builder
    if _builder is None:
        sys.path.insert(0, str(CHATBOT))
        from ifs_chatbot.korean import Analyzer
        from ifs_chatbot.scene_builder_v1 import SceneSpecBuilderV1

        an = Analyzer()
        if not getattr(an, "available", False):
            raise SystemExit("kiwipiepy가 없어 규칙 추출이 대체 분석기로 돕니다. venv에 kiwipiepy를 설치하세요.")
        _builder = SceneSpecBuilderV1(an)
    return _builder.build(text, session_id=sid)


# ── G62: 형태 후보 생성기용 규칙 프롬프트(shape_prompt) ───────────────────────────────
# 확정 텍스트에서 '말한 형태 낱말'만 고정 사전(shared/lexicon/shape_prompt_en.v0.json)으로 옮긴다.
# LLM·번역기 없음(원칙 1). 색·재질·크기·감정 낱말은 사전에 없어 프롬프트에 들어가지 않는다.
# 모든 내용 토큰은 원문 charSpan을 단다. 거슬러 갈 수 없는 토큰이 하나라도 있으면 막는다(fail closed).
# 막는 경우 모델을 부르지 않는다: no_shape_stated, excluded_category, untraceable_token.
# charSpan은 normalize_confirmed(text) 기준이고 sourceTextSha256도 그 문자열의 해시다(세션 confirmedText와 같은 정규화).
SHAPE_BUILDER_VERSION = "gen3d-shape-prompt/0.5.0"     # 0.2.0: 부속물 부정 틀, pluralStated
# 0.5.0(G84 후속, 2026-11-28): 문맥 규칙 — 사전 낱말이 든 문장이 과거·이전·전언·가정이거나(llm_fill.frame_reasons),
# 비유 원천이 속성 비유('X처럼 단단해요', llm_fill.simile_of_predicate — '처럼 생겼어요'는 형태 진술로 둠, llm_shape._simile_of_shape_verb)이거나,
# 단계 규칙(stage_rule)을 받았을 때 형태를 묻는 단계 밖 줄이면(llm_shape.line_stage_reason) 그 낱말을 쓰지 않는다. G82·G77 검증기와 같은 함수.
# 매퍼(IFSSceneSpec)는 건드리지 않는다. 설정 플래그 없이 항상(세 판 모두 0.5.0으로 올림).
# (G73 후속) 매퍼 판단을 따르는 규칙: shape_prompt(text, mapper_spec=세션 spec)일 때만. 텍스트만 넘기면 0.2.0 그대로
# (G62 기본 후보 경로·eval_g62 재현성). 판 이름에 규칙을 붙여 사이드카 builderVersion만 보고도 가를 수 있게 한다.
SHAPE_BUILDER_VERSION_MAPPER = "gen3d-shape-prompt/0.5.0+mapper-v2"
PROMPT_RULE_TEXT, PROMPT_RULE_MAPPER = "text", "mapper"
SHAPE_LEXICON = CHATBOT.parent / "shared" / "lexicon" / "shape_prompt_en.v0.json"
_NOUNISH = {"NNG", "NNP", "XSN"}
_PRED_TAGS = {"VA", "VV", "MAG", "XR"}
_shape_rt = None


class _ShapeRuntime:
    def __init__(self, lexicon_path: Path = SHAPE_LEXICON):
        sys.path.insert(0, str(CHATBOT))
        from ifs_chatbot.korean import Analyzer
        from ifs_chatbot.scene_builder import normalize_confirmed
        from ifs_chatbot.scene_builder_v1 import Doc
        from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2

        raw = Path(lexicon_path).read_text(encoding="utf-8")
        self.lex = json.loads(raw)
        self.lexicon_sha256 = sha256_text(raw)
        self.analyzer = Analyzer()
        if not self.analyzer.available:
            raise SystemExit("kiwipiepy가 없습니다. 형태 프롬프트는 Kiwi 분석이 있어야 결정적으로 같습니다.")
        self.normalize = normalize_confirmed
        self.Doc = Doc
        # 기존 제외 판정(G45–G51, base_shapes.v1 excluded·noAsset)을 그대로 쓴다(코드 무수정 호출)
        self.excluder = SceneSpecBuilderV2(self.analyzer)
        pr = self.lex["positionRules"]
        self.loc_nouns = frozenset(pr["locationNouns"])
        self.size_nouns = frozenset(pr["sizeNouns"])
        self.generic = frozenset(pr["genericFormNouns"])
        self.light_heads = frozenset(self.excluder.bs["rules"]["lightHeads"]) | self.generic
        self.by_first: dict[str, list[dict]] = {}
        for e in self.lex["entries"]:
            self.by_first.setdefault(e["ko"][0], []).append(e)
        for v in self.by_first.values():
            v.sort(key=lambda e: -len(e["ko"]))
        b = self.lex["blocked"]
        self.block_kind = {w: "nonMeshable" for w in b["nonMeshable"]}
        self.block_kind.update({w: "person" for w in b["person"]})
        self.block_kind.update({w: "animal" for w in b["animal"]})


def _shape_runtime() -> _ShapeRuntime:
    global _shape_rt
    if _shape_rt is None:
        _shape_rt = _ShapeRuntime()
    return _shape_rt


def _noun_run_bounds(toks, i: int, j: int) -> bool:
    """toks[i..j]가 붙어 쓴 명사 연속 전체와 같은가(뒷부분·앞부분만 맞추지 않음: '비눗방울'≠'방울')."""
    if i > 0 and toks[i - 1].base_tag in _NOUNISH and toks[i - 1].end == toks[i].start:
        return False
    if j + 1 < len(toks) and toks[j + 1].base_tag in _NOUNISH and toks[j + 1].start == toks[j].end \
            and not (toks[j + 1].form == "들" and toks[j + 1].base_tag == "XSN"):     # 복수 '조각들'은 같은 낱말
        return False
    return True


def _position(rt: _ShapeRuntime, doc, j: int) -> str:
    """명사 토큰(끝 j)의 자리: head | simile | noun_modifier | object | genitive | location | size."""
    toks = doc.toks
    k = j + 1
    if k < len(toks) and toks[k].form == "들" and toks[k].base_tag == "XSN":
        k += 1
    if k >= len(toks) or doc.sent[k] != doc.sent[j]:
        return "head"
    nt = toks[k]
    if nt.form == "만큼":
        return "size"
    if nt.form == "만" and nt.base_tag == "JX" and k + 1 < len(toks) and toks[k + 1].form == "하":
        return "size"                                # 'N만 하다'(크기 비교). '꽃만'(뿐)은 크기가 아님
    if nt.base_tag in ("NNG", "NNP", "NNB") and nt.form in rt.size_nouns:
        return "size"
    if nt.form in ("처럼", "같이") or (nt.form == "같" and nt.base_tag == "VA"):
        return "simile"
    if nt.base_tag in ("NNG", "NNP") and nt.form in rt.loc_nouns:
        return "location"
    if nt.base_tag == "JKB":
        return "location"
    if nt.base_tag == "JKO":
        return "object"
    if nt.base_tag == "JKG":
        return "genitive"
    if nt.base_tag in ("NNG", "NNP"):
        return "noun_modifier"
    return "head"


def _next_noun(doc, j: int, skip: int = 4):
    """j 뒤 같은 문장에서 처음 나오는 명사(NNG·NNP·NNB) 토큰 번호."""
    toks = doc.toks
    for k in range(j + 1, min(len(toks), j + 1 + skip)):
        if doc.sent[k] != doc.sent[j]:
            return None
        if toks[k].base_tag in ("NNG", "NNP", "NNB"):
            return k
    return None


def _negated(doc, i: int, j: int, lexical_starts: set, neg_spans) -> bool:
    """부정·정정: 기존 추출기의 _negated 구간과 겹치거나, 바로 앞 '안', 또는 같은 문장에서 다른 사전 낱말이 나오기 전
    3어절 안에 아니·않·없·못이 온다('공은 아니고', '동그랗지는 않고', '끈, 아니 귀신이에요')."""
    toks = doc.toks
    s0, s1 = toks[i].start, toks[j].end
    if any(a < s1 and s0 < b for a, b in neg_spans):
        return True
    if i > 0 and toks[i - 1].form == "안" and toks[i - 1].base_tag == "MAG" and doc.sent[i - 1] == doc.sent[i]:
        return True
    eoj_limit = doc.eoj[j] + 3
    for k in range(j + 1, len(toks)):
        t = toks[k]
        if doc.sent[k] != doc.sent[j] or doc.eoj[k] > eoj_limit or k in lexical_starts:
            return False
        if (t.form == "아니" and t.base_tag in ("VCN", "MAG", "IC")) or (t.form == "않" and t.base_tag == "VX") \
                or (t.form == "없" and t.base_tag == "VA") or (t.form == "못" and t.base_tag in ("MAG", "VX")):
            return True
        if t.form == "안" and t.base_tag == "MAG":
            return True
    return False


def shape_prompt_for_row(row: dict) -> dict:
    """생성기 입력 sentences.json의 한 줄 → shape_prompt. promptRule = "mapper"이고 mapperSpec이 있으면 매퍼 규칙
    (G73 [맞는 게 없어요] 생성 — none_gen.py가 세션 spec을 함께 적음), 아니면 텍스트만(G62 기본 후보·평가 입력).
    (G75) imageStyle이 IMAGE_PICK_STYLE_ID면 이미지 고르기 화풍 문구를 더한다(image_pick_prompt). 없으면 예전 그대로."""
    if row.get("promptRule") == PROMPT_RULE_MAPPER:
        spec = row.get("mapperSpec")
        if not isinstance(spec, dict):
            raise SystemExit(f"{row.get('id')}: promptRule mapper인데 mapperSpec이 없음")
        # (G77) 서버가 검증해 채택한 LLM 형태 낱말(있을 때만 키가 있다). 규칙이 형태를 못 만들었을 때만 쓰인다
        # (G82) 서버가 검증해 채택한 LLM 형태 이름(llmTranslatedShapeItems, 있을 때만). 규칙에 중심 형태 명사가 없을 때만 쓰인다
        p = shape_prompt(row["text"], mapper_spec=spec, llm_items=row.get("llmShapeItems"),
                         llm_shape_items=row.get("llmTranslatedShapeItems"), stage_rule=row.get("lineStageRule"))
    else:
        p = shape_prompt(row["text"])
    style = row.get("imageStyle")
    if style is None:
        return p
    if style != IMAGE_PICK_STYLE_ID:
        raise SystemExit(f"{row.get('id')}: 모르는 imageStyle {style!r}(아는 값: {IMAGE_PICK_STYLE_ID})")
    return image_pick_prompt(p)


# ── G75: 참여자가 먼저 고르는 참고 이미지의 화풍(형태만 보이는 무채색) ─────────────────────────────
# 최종 물체는 형태만 쓰고 색·재질은 참여자가 말한 값(매핑)으로 칠한다. 참여자가 이미지의 색을 보고 고르면 어긋나므로
# 이미지를 흰 배경의 무채색 점토 조형 하나로 고정한다. 아래 문구는 심상 속성이 아니라 시스템 문구다(slot template).
# 내용 토큰(말한 형태 낱말)은 바꾸지 않는다. 같은 입력 → 같은 출력. 이 함수를 거치지 않는 경로(G62 기본 후보·G73)는 그대로다.
IMAGE_PICK_STYLE_ID = "g75-shape-only-gray"
IMAGE_PICK_STYLE_VERSION = "g75-image-style/0.1.0"
IMAGE_PICK_SUFFIX = ("untextured monochrome gray clay sculpture", "single uniform color", "soft even studio lighting",
                     "centered", "entire object in view")
IMAGE_PICK_NEGATIVE = ("colorful", "multicolored", "painted", "patterned", "glossy", "metallic", "reflections",
                       "background objects")
SHAPE_BUILDER_VERSION_IMAGE_PICK = "gen3d-shape-prompt/0.5.0+imagepick"


def image_pick_prompt(p: dict) -> dict:
    """shape_prompt 결과 → 이미지 고르기(G75)용 프롬프트. 막힌 결과는 판 이름만 바꿔 그대로(모델을 부르지 않음).
    부정 틀 항목이 말한 낱말과 한 낱말이라도 겹치면 뺀다(negativeAccessories와 같은 규칙)."""
    q = dict(p)
    rule = p.get("promptRule")
    q["builderVersion"] = SHAPE_BUILDER_VERSION_IMAGE_PICK + ("+mapper-v2" if rule == PROMPT_RULE_MAPPER else "") \
        + (SHAPE_BUILDER_LLM_SUFFIX if p.get("shapeSource") == LLM_QUOTED else "") \
        + (SHAPE_BUILDER_LLM_SHAPE_SUFFIX if p.get("shapeSource") == LLM_TRANSLATED else "")
    q["imageStyle"] = IMAGE_PICK_STYLE_ID
    q["imageStyleVersion"] = IMAGE_PICK_STYLE_VERSION
    if p.get("status") != "ok" or not p.get("text"):
        return q
    said = {w for t in p.get("tokens") or [] if t.get("slot") != "template" for w in t["en"].replace("-", " ").split()}
    neg = [n for n in IMAGE_PICK_NEGATIVE if not (set(n.split()) & said)]
    q["text"] = ", ".join([p["text"], *IMAGE_PICK_SUFFIX])
    q["negativeText"] = ", ".join([p["negativeText"], *neg]) if p.get("negativeText") else ", ".join(neg)
    q["tokens"] = list(p.get("tokens") or []) + [{"en": s, "ko": None, "charSpan": None, "slot": "template",
                                                  "lexiconKey": None} for s in IMAGE_PICK_SUFFIX]
    return q


def _overlaps(a, b) -> bool:
    return bool(a and b) and a[0] < b[1] and b[0] < a[1]


def _mapper_evidence(spec: dict) -> dict:
    """(G73 후속) 세션 매퍼(v2) spec에서 형태 낱말 판단을 모은다. 값은 [시작, 끝) 목록.
    - form: form.* 슬롯의 근거(_provenance) — 매퍼가 형태로 받아들인 낱말
    - discard: 매퍼가 형태에서 버린 낱말과 사유 — 움직임 비유의 매개어(G71 actionSimile), 장소 용법(G74-c location),
      직접 형태 진술에 밀린 형상 낱말(G71-b lower_priority), 부정·정정(_negated), 형태 슬롯의 맥락 낱말(_context)
    - recorded: 매퍼가 어떤 식으로든 적은 낱말(_unmapped의 사물·모양어·사전 밖 명사, form.* 대안 등)"""
    ev = {"form": [], "discard": [], "recorded": []}

    def span(p):
        cs = (p or {}).get("charSpan")
        return tuple(cs) if isinstance(cs, (list, tuple)) and len(cs) == 2 else None

    for path, plist in (spec.get("_provenance") or {}).items():
        for p in plist if isinstance(plist, list) else [plist]:
            s = span(p)
            if s:
                (ev["form"] if path.startswith("form.") else ev["recorded"]).append(s)
    for a in spec.get("_alternatives") or []:
        path, why = a.get("path") or "", a.get("reason") or ""
        for p in a.get("_provenance") or []:
            s = span(p)
            if not s:
                continue
            rule = p.get("rule") or ""
            reason = None
            if path.startswith("form."):
                if "actionSimile" in rule:
                    reason = "mapper_action_simile"
                elif "+location(" in rule or why == "location":
                    reason = "mapper_location"
                elif why == "lower_priority":
                    reason = "mapper_lower_priority"
            if reason:
                ev["discard"].append((s, reason))
            else:
                ev["recorded"].append(s)
    for n in spec.get("_negated") or []:
        s = span(n.get("_provenance"))
        if s:
            ev["discard"].append((s, "mapper_negated"))
    for c in spec.get("_context") or []:
        s = span(c)
        if s and (c.get("path") or "").startswith("form."):
            ev["discard"].append((s, "mapper_context"))
        elif s:
            ev["recorded"].append(s)
    for u in spec.get("_unmapped") or []:
        s = span(u.get("_provenance"))
        if s:
            ev["recorded"].append(s)
    return ev


def _mapper_verdict(ev: dict, span, is_noun: bool) -> str | None:
    """사전에 맞은 낱말 하나 → None(프롬프트 후보로 둠) 또는 뺀 사유.
    형태 슬롯 근거면 둔다. 매퍼가 버렸으면 그 사유. 형태 명사인데 매퍼가 전혀 적지 않았으면 mapper_unrecorded.
    형태 꾸밈말(동그란·엉킨·오돌토돌 등)은 매퍼가 다른 슬롯(질감·침식)에 적거나 적지 않아도, 버리지 않았으면 둔다."""
    if any(_overlaps(span, f) for f in ev["form"]):
        return None
    for s, reason in ev["discard"]:
        if _overlaps(span, s):
            return reason
    if is_noun and not any(_overlaps(span, r) for r in ev["recorded"]):
        return "mapper_unrecorded"
    return None


# (G77) 0.1.1(CP15-1): 생성 직전 재검증이 서버 검증기와 같은 영어 금지 규칙(english_shape_reasons)을 쓴다
SHAPE_BUILDER_LLM_SUFFIX = "+llmquote-0.1.1"           # (G77) LLM 인용 형태 낱말로 빈 형태 자리를 메웠을 때 builderVersion 끝에
LLM_QUOTED = "llm_quoted"
SHAPE_EN_BLOCK = CHATBOT.parent / "shared" / "lexicon" / "shape_english_block.v0.json"
EN_REASONS = ("english_banned", "english_color_size", "english_non_shape", "non_meshable")   # 기각 사유 순서(형식 다음)
_EN_SUFFIXES = ("shaped", "esque", "like", "ish", "oid", "ed")   # 붙여 쓴 꼴('catlike'·'horned')을 어간으로 되돌려 exact와 대조
_en_block = None


class _EnglishBlock:
    def __init__(self, path: Path = SHAPE_EN_BLOCK):
        import re
        raw = Path(path).read_text(encoding="utf-8")
        d = json.loads(raw)
        self.file, self.sha256, self.version = Path(path).name, sha256_text(raw), d["version"]
        self.pattern = re.compile(d["englishPattern"])
        self.irregular = dict(d["irregularPlurals"])
        self.exact = {k: frozenset(d["categories"][k]["exact"]) for k in EN_REASONS}
        self.contained = {k: tuple(d["categories"][k]["contained"]) for k in EN_REASONS}


def english_block() -> _EnglishBlock:
    global _en_block
    if _en_block is None:
        _en_block = _EnglishBlock()
    return _en_block


def _en_variants(w: str, irregular: dict) -> set[str]:
    """낱말 → 대조할 꼴(그대로 + 불규칙 복수형 + 단순 복수형 어간 + 붙여 쓴 접미 떼기). 규칙만, 같은 낱말 → 같은 집합."""
    out = {w}
    for x in list(out):
        if x in irregular:
            out.add(irregular[x])
        if len(x) > 4 and x.endswith("ies"):
            out.add(x[:-3] + "y")
        if len(x) > 4 and x.endswith("ves"):
            out.update((x[:-3] + "f", x[:-3] + "fe"))
        if len(x) > 3 and x.endswith("es"):
            out.add(x[:-2])
        if len(x) > 2 and x.endswith("s") and not x.endswith("ss"):
            out.add(x[:-1])
    for x in list(out):
        for suf in _EN_SUFFIXES:
            if x.endswith(suf) and len(x) - len(suf) >= 2:
                stem = x[:-len(suf)]
                out.add(stem)
                if stem in irregular:
                    out.add(irregular[stem])
                if len(stem) > 2 and stem.endswith("s") and not stem.endswith("ss"):
                    out.add(stem[:-1])
    return out


def english_shape_reasons(value: str) -> list[str]:
    """(G77) LLM 형태 낱말(영어) → 기각 사유 목록(비면 통과). 서버 검증기(llm_fill._check_item)와 생성 직전 재검증(_llm_head)이
    같은 함수를 쓴다. ASCII·형식(영문자 1–3낱말, 낱말 사이 공백 하나) 밖이면 곧바로 english_format 하나로 버림(글자를 지우고
    검사하지 않음) → 소문자 낱말로 나눔 → 낱말과 이어 붙인 낱말 묶음마다 복수형·접미 어간을 만든 뒤 exact 목록 일치, contained
    어근이 안에 들어 있는지. 막는 쪽으로 넉넉하다(handle → hand 등 과차단은 의도, 막히면 형태 자리를 메우지 않음)."""
    B = english_block()
    if not isinstance(value, str) or not value.isascii():    # ASCII 밖(소문자화로 ASCII가 되는 'K' U+212A 포함)은 곧바로
        return ["english_format"]
    low = value.lower()
    if not B.pattern.fullmatch(low):
        # 허용 문자(영소문자·낱말 사이 공백 하나) 밖의 글자가 하나라도 있으면 지우고 검사하지 않고 곧바로 형식 위반으로 버린다
        # (닮은꼴 문자 'skսll'·숫자 'f0g'·하이픈·소유격 "wolf's"·앞뒤 공백·줄바꿈 — 사유 일관, CP15 재검토)
        return ["english_format"]
    why = []
    words = low.split()
    grams = {"".join(words[i:j]) for i in range(len(words)) for j in range(i + 1, len(words) + 1)}
    forms = set()
    for g in grams:
        forms |= _en_variants(g, B.irregular)
    for k in EN_REASONS:
        if any(f in B.exact[k] for f in forms) or any(r in g for g in grams for r in B.contained[k]):
            why.append(k)
    return why


def _llm_head(norm: str, items) -> dict | None:
    """(G77) 서버가 채택한 LLM 형태 낱말 항목 가운데 첫 번째를 다시 확인한다(같은 입력 → 같은 결과, 생성기 프로세스도 같은 판정).
    인용이 확정 텍스트의 charSpan 글자와 같고 영어가 서버 검증기와 같은 규칙(english_shape_reasons)을 통과할 때만.
    아니면 None(규칙 결과 그대로 — fail closed)."""
    for it in items or []:
        try:
            q, (s, e), en = it["quote"], it["charSpan"], it["english"]
        except (KeyError, TypeError, ValueError):
            continue
        if isinstance(q, str) and isinstance(en, str) and isinstance(s, int) and isinstance(e, int) \
                and not isinstance(s, bool) and not isinstance(e, bool) \
                and 0 <= s < e <= len(norm) and norm[s:e] == q and not english_shape_reasons(en):
            return {"en": en.lower(), "ko": q, "charSpan": [s, e]}
        return None                                     # 첫 항목만 본다(빈자리 메우기 하나)
    return None


# ── G82: [맞는 게 없어요] 뒤 규칙이 형태 명사를 잡지 못했을 때 LLM이 인용·영어 이름을 낸 형태 낱말 ─────────────
# (첫 단계: 오프라인 평가만. 실험 경로 selection.py·none_gen.py에는 잇지 않았다. llm_shape_items를 주지 않으면 출력은 그대로)
SHAPE_BUILDER_LLM_SHAPE_SUFFIX = "+llmshape-0.1.0"     # (G82) LLM 형태 이름으로 중심 명사 자리를 메웠을 때 builderVersion 끝에
LLM_TRANSLATED = "llm_translated"                       # (G82) 토큰 출처(규칙 사전 토큰·G77 llm_quoted와 구분)
SHAPE_EN_MOD_BLOCK = CHATBOT.parent / "shared" / "lexicon" / "shape_english_modifier_block.v0.json"
EN_MOD_REASONS = ("two_words", "english_modifier", "english_banned", "non_meshable")
_en_mod_block = None


class _EnglishModifierBlock:
    """(G82) 꾸밈말 금지 목록(허용 목록 아님). 규칙 사전의 shape_modifier 영어 낱말도 막는다(규칙만 붙이는 꾸밈말)."""

    def __init__(self, path: Path = SHAPE_EN_MOD_BLOCK):
        raw = Path(path).read_text(encoding="utf-8")
        d = json.loads(raw)
        self.file, self.sha256, self.version = Path(path).name, sha256_text(raw), d["version"]
        self.max_words = int(d["maxWords"])
        c = d["categories"]
        lex_mods = {w for e in _shape_runtime().lex["entries"] if e["slot"] == "shape_modifier" for w in e["en"].split()}
        self.modifier = frozenset(c["shape_adjective"]) | frozenset(c["texture_material"]) \
            | frozenset(c["emotion_evaluation"]) | frozenset(c["quantity"]) | frozenset(lex_mods)
        self.banned = frozenset(c["english_banned_supplement"])
        self.non_meshable = frozenset(c["non_meshable_supplement"])
        self.first_only = frozenset(d["firstWordOnly"])
        self.adj_suffixes = tuple(d["firstWordAdjectiveSuffixes"])
        self.adj_min = int(d["firstWordAdjectiveSuffixMinLength"])
        self.korean_non_shape_heads = frozenset(d.get("koreanNonShapeHeads") or [])   # (0.1.1) 인용 쪽 검사(chatbot llm_shape)


def english_modifier_block() -> _EnglishModifierBlock:
    global _en_mod_block
    if _en_mod_block is None:
        _en_mod_block = _EnglishModifierBlock()
    return _en_mod_block


def llm_shape_english_reasons(value: str) -> list[str]:
    """(G82) LLM 형태 이름(영어) → 기각 사유(비면 통과). 서버 검증기(chatbot llm_shape)와 생성 직전 재검증(_llm_shape_head)이
    같은 함수를 쓴다. ① G77 금지 규칙 english_shape_reasons 그대로(형식·사람·동물·색·크기·재질·감정·안개·불꽃) ② 소문자가 아니면
    english_format ③ 낱말 수가 목록 maxWords(0.2.0부터 1) 초과면 two_words ④ 꾸밈말(모양·질감·재질·감정·개수 낱말, 규칙 사전 shape_modifier 영어) ⑤ 두 낱말의 앞 낱말이
    재질 명사(stone·paper 등)이거나 형용사 꼴 접미(-ous·-y 등) ⑥ G82 보충 금지(동물·사람·안개·불꽃 낱말). 막는 쪽으로 넉넉하다."""
    why = list(english_shape_reasons(value))
    if "english_format" in why:
        return why
    if value != value.lower():
        return ["english_format"]
    M = english_modifier_block()
    B = english_block()
    words = value.split()
    if len(words) > M.max_words:
        why.append("two_words")                      # (0.2.0 목록, CP19-1) 영어 이름은 한 낱말
    forms = set()
    for w in words:
        forms |= _en_variants(w, B.irregular)
    if forms & M.modifier:
        why.append("english_modifier")
    elif len(words) >= 2:
        first = words[0]
        if first in M.first_only or (len(first) >= M.adj_min and first.endswith(M.adj_suffixes)):
            why.append("english_modifier")
    joined = {"".join(words)}
    for g in joined:
        forms |= _en_variants(g, B.irregular)
    if forms & M.banned and "english_banned" not in why:
        why.append("english_banned")
    if forms & M.non_meshable and "non_meshable" not in why:
        why.append("non_meshable")
    return why


def _llm_shape_head(norm: str, items) -> dict | None:
    """(G82) 서버가 채택한 LLM 형태 이름 항목 {quote, charSpan, en} 첫 번째를 다시 확인한다(생성기 프로세스도 같은 판정).
    인용이 확정 텍스트 charSpan 글자와 같고 영어가 llm_shape_english_reasons를 통과할 때만. 아니면 None(fail closed)."""
    for it in items or []:
        try:
            q, (s, e), en = it["quote"], it["charSpan"], it["en"]
        except (KeyError, TypeError, ValueError):
            return None
        if isinstance(q, str) and isinstance(en, str) and isinstance(s, int) and isinstance(e, int) \
                and not isinstance(s, bool) and not isinstance(e, bool) \
                and 0 <= s < e <= len(norm) and norm[s:e] == q and not llm_shape_english_reasons(en):
            return {"en": en, "ko": q, "charSpan": [s, e]}
        return None
    return None


_frame_mods = None


def _frame_modules():
    """(G84 후속) 문맥 규칙 함수가 있는 챗봇 모듈(G77·G82 검증기와 같은 함수를 쓴다 — 복사하지 않음)."""
    global _frame_mods
    if _frame_mods is None:
        sys.path.insert(0, str(CHATBOT))
        from ifs_chatbot import llm_fill, llm_shape
        _frame_mods = (llm_fill, llm_shape)
    return _frame_mods


def _frame_drop(fctx, norm: str, i: int, j: int, e: dict, pos: str, stage_rule: dict | None) -> list[str]:
    """사전에 맞은 낱말 toks[i..j] → 쓰지 않을 문맥 사유(비면 씀). G77·G82 검증기와 같은 규칙:
    past_or_former · reported_speech · hypothetical(문장 전체) · simile_of_predicate(비유 원천 명사, '처럼 생겼어요'는 뺌)
    · non_shape_stage_line(단계 규칙이 있을 때). 부정·회상 문장·장소·크기는 앞에서 따로 본다."""
    lf, ls = _frame_modules()
    why = list(lf.frame_reasons(fctx, list(range(i, j + 1))))
    if (e["pos"] == "noun" and pos == "simile" and lf.simile_of_predicate(fctx.doc, fctx.toks, j)
            and not ls._simile_of_shape_verb(fctx, {"charSpan": [fctx.toks[i].start, fctx.toks[j].end]})):
        why.append("simile_of_predicate")
    if stage_rule:
        _st, outside = ls.line_stage_reason(norm, fctx.toks[i].start, stage_rule["stages"], stage_rule["allowedStages"])
        if outside:
            why.append("non_shape_stage_line")
    return why


def shape_prompt(text: str, mapper_spec: dict | None = None, llm_items: list | None = None,
                 llm_shape_items: list | None = None, stage_rule: dict | None = None) -> dict:
    """확정 텍스트 → 형태 프롬프트와 차단 판정. 같은 텍스트 → 언제나 같은 결과(사전·규칙만).

    mapper_spec(G73 후속, 실험 설정의 [맞는 게 없어요] 생성만): 같은 확정 텍스트로 세션이 만든 매퍼 v2 spec.
    주면 ① 차단 판정(제외 범주·안개·부정)을 기본 매퍼가 아니라 이 spec으로 하고, ② 사전에 맞은 낱말 가운데 매퍼가 형태에서
    버린 것(움직임 비유의 매개어·장소 용법·직접 진술에 밀린 형상 낱말·부정)과 매퍼가 적지 않은 형태 명사를 빼고 dropped에
    사유와 함께 남긴다. spec의 sourceTextHash가 이 텍스트와 다르면 막는다(mapper_spec_mismatch). 같은 (텍스트, spec) → 같은 결과.
    주지 않으면 0.2.0 그대로(G62 기본 후보 경로·오프라인 평가).
    (G82) llm_shape_items: 서버 검증기를 통과한 LLM 형태 이름 [{quote, charSpan, en}]. 규칙이 중심 형태 명사를 못 잡았고(꾸밈말만
    잡은 경우 포함) 막을 사유가 없을 때만 중심 명사 자리를 메운다(문장·꾸밈말·부정 틀은 규칙 그대로). llm_items(G77)와 함께 주면 오류.
    (G84 후속, 0.5.0) 사전 낱말마다 문맥 규칙(_frame_drop)을 건다. stage_rule = {stages, allowedStages}(llm_shape.stage_rule —
    단계 표지가 applied일 때만)이면 형태를 묻는 단계 밖 줄의 낱말도 뺀다. 뺀 낱말은 dropped에 reason(첫 사유)·frameReasons."""
    if llm_items and llm_shape_items:
        raise ValueError("G77 llm_items와 G82 llm_shape_items를 함께 줄 수 없음(형태 낱말 자리는 한 경로만)")
    rt = _shape_runtime()
    norm = rt.normalize(text)
    toks = rt.analyzer.tokens(norm)
    doc = rt.Doc(norm, toks)
    fctx = types.SimpleNamespace(toks=toks, doc=doc)         # (G84 후속) 검증기 문맥 함수가 보는 두 값
    context = rt.excluder._context_sentences(doc)
    use_mapper = mapper_spec is not None
    spec = mapper_spec if use_mapper else rt.excluder.build(norm)
    ev = _mapper_evidence(mapper_spec) if use_mapper else None
    mapper_mismatch = False
    if use_mapper:
        h = str((mapper_spec.get("meta") or {}).get("sourceTextHash") or "")
        mapper_mismatch = h.split(":", 1)[-1] != sha256_text(norm)
    neg_spans = [tuple(n["_provenance"]["charSpan"]) for n in spec.get("_negated") or []
                 if (n.get("_provenance") or {}).get("charSpan")]
    tmpl = rt.lex["template"]

    # 1) 사전 맞춤(가장 긴 항목 먼저). 명사는 붙어 쓴 명사 연속 전체와 같을 때만.
    matches = []
    i = 0
    while i < len(toks):
        t = toks[i]
        hit = None
        for e in rt.by_first.get(t.form, []):
            n = len(e["ko"])
            seg = toks[i:i + n]
            if len(seg) < n or [x.form for x in seg] != e["ko"]:
                continue
            if any(seg[m].start != seg[m - 1].end for m in range(1, n)):
                continue
            if e["pos"] == "noun":
                if not all(x.base_tag in _NOUNISH for x in seg) or not _noun_run_bounds(toks, i, i + n - 1):
                    continue
            elif not (n == 1 and t.base_tag in _PRED_TAGS):
                continue
            hit = (i, i + n - 1, e)
            break
        if hit:
            matches.append(hit)
            i = hit[1] + 1
        else:
            i += 1
    lexical_starts = {m[0] for m in matches}

    accepted, dropped = [], []
    for i, j, e in matches:
        s, en_ = toks[i].start, toks[j].end
        ko = norm[s:en_]
        if doc.sent[i] in context:
            dropped.append({"ko": ko, "charSpan": [s, en_], "reason": "context_sentence"})
            continue
        if _negated(doc, i, j, lexical_starts, neg_spans):
            dropped.append({"ko": ko, "charSpan": [s, en_], "reason": "negated"})
            continue
        pos = _position(rt, doc, j) if e["pos"] == "noun" else "pred"
        if pos in ("location", "size"):
            dropped.append({"ko": ko, "charSpan": [s, en_], "reason": pos})
            continue
        if ev is not None:
            why = _mapper_verdict(ev, (s, en_), e["pos"] == "noun" and e["slot"] == "shape_noun")
            if why:
                dropped.append({"ko": ko, "charSpan": [s, en_], "reason": why})
                continue
        # (G84 후속) 문맥 규칙은 매퍼 판단 뒤에(매퍼가 이미 뺀 낱말의 사유 기록은 예전 그대로)
        fwhy = _frame_drop(fctx, norm, i, j, e, pos, stage_rule)
        if fwhy:
            dropped.append({"ko": ko, "charSpan": [s, en_], "reason": fwhy[0], "frameReasons": fwhy})
            continue
        accepted.append({"i": i, "j": j, "e": e, "ko": ko, "span": [s, en_], "pos": pos})

    # 2) 차단 판정: 기존 제외 판정(G45–G51) → 메시로 안 되는 범주(form.type mist·form.base flame) → 보충 목록
    detail = []
    for u in spec.get("_unmapped") or []:
        v = u.get("value") if isinstance(u.get("value"), dict) else {}
        if u.get("reason") in ("excluded_shape", "no_asset") and (v.get("formSaid") is True or v.get("formBlock") is True):
            detail.append(f"{v.get('excluded') or v.get('noAsset')}:{u.get('lemma')}")
    form = spec.get("form") or {}
    if form.get("type") == "mist":
        detail.append("nonMeshable:form.type=mist")
    if form.get("base") == "flame":
        detail.append("nonMeshable:form.base=flame")
    shape_nouns_here = any(a["e"]["pos"] == "noun" and a["e"]["slot"] == "shape_noun" for a in accepted)
    for k, t in enumerate(toks):
        kind = rt.block_kind.get(t.form)
        if not kind or t.base_tag not in ("NNG", "NNP") or not _noun_run_bounds(toks, k, k):
            continue
        if doc.sent[k] in context or _negated(doc, k, k, lexical_starts, neg_spans):
            continue
        pos = _position(rt, doc, k)
        if pos in ("location", "size", "object", "genitive"):
            continue
        nxt = _next_noun(doc, k)
        nxt_form = toks[nxt].form if nxt is not None else None
        if kind == "nonMeshable" and ev is not None and \
                any(_overlaps((t.start, t.end), s) for s, _ in ev["discard"]):
            continue                                 # 매퍼가 형태에서 버린 안개·구름(장소 용법·움직임 비유). 사람·동물은 그대로 막음
        if kind == "nonMeshable":
            hit = pos in ("noun_modifier", "simile") or (pos == "head" and not shape_nouns_here)
            if pos == "simile" and nxt_form in rt.excluder.bs_color_nouns:
                hit = False                         # '불꽃 같은 색' = 색 비교
        elif pos == "head":
            hit = True
        elif pos == "noun_modifier":
            hit = nxt_form in rt.light_heads         # '얼굴 모양'·'고양이 형상'
        else:                                        # 비유 원천: 대상이 형태 명사면 그 명사를 그림(G45)
            hit = not (nxt_form and nxt_form in rt.by_first and nxt_form not in rt.generic)
        if hit:
            detail.append(f"{kind}:{t.form}")
    block = "excluded_category" if detail else None
    if mapper_mismatch:                              # 다른 텍스트의 spec — 매퍼 판단을 믿을 수 없음(fail closed)
        block, detail = "mapper_spec_mismatch", ["mapper_spec_mismatch:meta.sourceTextHash"]

    # 3) 프롬프트 조립: 꾸밈말(나온 차례) + 비유·명사 꾸밈('…-like') + 중심 명사(처음 나온 것)
    mods, likes, head, later = [], [], None, []
    for a in accepted:
        e = a["e"]
        if e["slot"] == "shape_modifier":
            if e["en"] not in [m["en"] for m in mods]:
                mods.append({**a, "en": e["en"]})
        elif a["pos"] in ("simile", "noun_modifier"):
            like = e["en"].replace(" ", "-") + "-like"
            if like not in [m["en"] for m in likes]:
                likes.append({**a, "en": like})
        elif head is None:
            head = {**a, "en": e["en"]}
        else:
            later.append(a)
    if head is None and likes:                      # '깃털 같은 게' — 비유 원천이 곧 형상(형식 명사 대상)
        first = likes.pop(0)
        head = {**first, "en": first["e"]["en"]}
    if head is not None:                            # '상자 같은 게 … 네모난 상자예요' — 같은 낱말의 비유는 중심 명사와 겹침
        for a in [x for x in likes if x["e"]["en"] == head["en"]]:
            likes.remove(a)
            dropped.append({"ko": a["ko"], "charSpan": a["span"], "reason": "same_as_head"})
    for a in later:
        dropped.append({"ko": a["ko"], "charSpan": a["span"], "reason": "later_mention"})

    content = mods + likes + ([head] if head else [])
    # (G77) 규칙이 형태 낱말을 하나도 못 만들었고 막을 사유도 없을 때만, 서버가 채택한 LLM 인용 형태 낱말 하나로 중심 명사 자리를 메운다
    llm_tok = _llm_head(norm, llm_items) if (not content and llm_items and block is None) else None
    # (G82) 중심 명사가 없고(꾸밈말만 있어도 됨) 막을 사유도 없을 때만 LLM 형태 이름 하나로 중심 명사 자리를 메운다
    shape_tok = _llm_shape_head(norm, llm_shape_items) if (head is None and llm_shape_items and block is None) else None
    tokens = [{"en": tmpl["prefix"], "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None}]
    for c in content:
        tokens.append({"en": c["en"], "ko": c["ko"], "charSpan": c["span"], "slot": c["e"]["slot"],
                       "lexiconKey": "+".join(c["e"]["ko"])})
    if llm_tok is not None:
        tokens.append({"en": llm_tok["en"], "ko": llm_tok["ko"], "charSpan": llm_tok["charSpan"], "slot": "shape_noun",
                       "lexiconKey": None, "provenance": LLM_QUOTED})
    elif shape_tok is not None:
        tokens.append({"en": shape_tok["en"], "ko": shape_tok["ko"], "charSpan": shape_tok["charSpan"], "slot": "shape_noun",
                       "lexiconKey": None, "provenance": LLM_TRANSLATED})
    elif head is None:
        tokens.append({"en": tmpl["defaultNoun"], "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None})
    phrase = " ".join(t["en"] for t in tokens)
    tokens += [{"en": s, "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None} for s in tmpl["suffix"]]
    prompt_text = ", ".join([phrase, *tmpl["suffix"]]) if (content or llm_tok or shape_tok) else ""

    # 4) 감사: 모든 내용 토큰이 원문 글자로 거슬러 가야 한다(fail closed)
    untraceable = [t["en"] for t in tokens if t["slot"] != "template" and not (
        t["ko"] and t["charSpan"] and 0 <= t["charSpan"][0] < t["charSpan"][1] <= len(norm)
        and norm[t["charSpan"][0]:t["charSpan"][1]] == t["ko"])]
    if block is None and untraceable:
        block, detail = "untraceable_token", [f"untraceable:{u}" for u in untraceable]
    if block is None and not content and llm_tok is None and shape_tok is None:
        block = "no_shape_stated"
    # 부정 틀: 안전 제약(언제나 같음) + 부속물(말한 낱말과 한 낱말이라도 겹치면 뺌)
    said_words = {w for c in content for w in c["en"].replace("-", " ").split()}
    if llm_tok is not None:
        said_words |= set(llm_tok["en"].split())
    if shape_tok is not None:
        said_words |= set(shape_tok["en"].split())
    acc = [a for a in tmpl.get("negativeAccessories", []) if not (set(a.split()) & said_words)]
    negative = ", ".join([tmpl["negative"], *acc])
    toks_ = doc.toks
    plural = any(c["e"].get("plural") or (c["j"] + 1 < len(toks_) and toks_[c["j"] + 1].form == "들"
                                            and toks_[c["j"] + 1].base_tag == "XSN")
                 for c in content if c["e"]["pos"] == "noun")
    out = {
        "status": "blocked" if block else "ok",
        "blockReason": block,
        "blockDetail": ";".join(sorted(set(detail))) or None,
        "text": "" if block else prompt_text,
        "negativeText": negative,
        "pluralStated": bool(plural),
        "lexiconVersion": rt.lex["lexiconVersion"],
        "builderVersion": SHAPE_BUILDER_VERSION_MAPPER if use_mapper else SHAPE_BUILDER_VERSION,
        "promptRule": PROMPT_RULE_MAPPER if use_mapper else PROMPT_RULE_TEXT,
        "mapperBuilder": (((mapper_spec.get("meta") or {}).get("pipeline") or {}).get("builder")) if use_mapper else None,
        "templateVersion": tmpl["version"],
        "tokens": tokens if (content or llm_tok or shape_tok) else [],
        "dropped": dropped,
        "thinRisk": any(c["e"].get("thin") for c in content),
        "familiarObjectStated": any(c["e"].get("familiar") for c in content if c["e"]["pos"] == "noun"),
        "sourceTextSha256": sha256_text(norm),
    }
    if llm_tok is not None:                          # (G77) 키는 LLM 낱말을 썼을 때만(쓰지 않으면 예전 출력 그대로)
        out["builderVersion"] += SHAPE_BUILDER_LLM_SUFFIX
        out["shapeSource"] = LLM_QUOTED
    if shape_tok is not None:                        # (G82) 키는 LLM 형태 이름을 썼을 때만(쓰지 않으면 예전 출력 그대로)
        out["builderVersion"] += SHAPE_BUILDER_LLM_SHAPE_SUFFIX
        out["shapeSource"] = LLM_TRANSLATED
    return out
