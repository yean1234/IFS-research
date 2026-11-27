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
SHAPE_BUILDER_VERSION = "gen3d-shape-prompt/0.2.0"     # 0.2.0: 부속물 부정 틀, pluralStated
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


def shape_prompt(text: str) -> dict:
    """확정 텍스트 → 형태 프롬프트와 차단 판정. 같은 텍스트 → 언제나 같은 결과(사전·규칙만)."""
    rt = _shape_runtime()
    norm = rt.normalize(text)
    toks = rt.analyzer.tokens(norm)
    doc = rt.Doc(norm, toks)
    context = rt.excluder._context_sentences(doc)
    spec = rt.excluder.build(norm)
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
    tokens = [{"en": tmpl["prefix"], "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None}]
    for c in content:
        tokens.append({"en": c["en"], "ko": c["ko"], "charSpan": c["span"], "slot": c["e"]["slot"],
                       "lexiconKey": "+".join(c["e"]["ko"])})
    if head is None:
        tokens.append({"en": tmpl["defaultNoun"], "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None})
    phrase = " ".join(t["en"] for t in tokens)
    tokens += [{"en": s, "ko": None, "charSpan": None, "slot": "template", "lexiconKey": None} for s in tmpl["suffix"]]
    prompt_text = ", ".join([phrase, *tmpl["suffix"]]) if content else ""

    # 4) 감사: 모든 내용 토큰이 원문 글자로 거슬러 가야 한다(fail closed)
    untraceable = [t["en"] for t in tokens if t["slot"] != "template" and not (
        t["ko"] and t["charSpan"] and 0 <= t["charSpan"][0] < t["charSpan"][1] <= len(norm)
        and norm[t["charSpan"][0]:t["charSpan"][1]] == t["ko"])]
    if block is None and untraceable:
        block, detail = "untraceable_token", [f"untraceable:{u}" for u in untraceable]
    if block is None and not content:
        block = "no_shape_stated"
    # 부정 틀: 안전 제약(언제나 같음) + 부속물(말한 낱말과 한 낱말이라도 겹치면 뺌)
    said_words = {w for c in content for w in c["en"].replace("-", " ").split()}
    acc = [a for a in tmpl.get("negativeAccessories", []) if not (set(a.split()) & said_words)]
    negative = ", ".join([tmpl["negative"], *acc])
    toks_ = doc.toks
    plural = any(c["e"].get("plural") or (c["j"] + 1 < len(toks_) and toks_[c["j"] + 1].form == "들"
                                            and toks_[c["j"] + 1].base_tag == "XSN")
                 for c in content if c["e"]["pos"] == "noun")
    return {
        "status": "blocked" if block else "ok",
        "blockReason": block,
        "blockDetail": ";".join(sorted(set(detail))) or None,
        "text": "" if block else prompt_text,
        "negativeText": negative,
        "pluralStated": bool(plural),
        "lexiconVersion": rt.lex["lexiconVersion"],
        "builderVersion": SHAPE_BUILDER_VERSION,
        "templateVersion": tmpl["version"],
        "tokens": tokens if content else [],
        "dropped": dropped,
        "thinRisk": any(c["e"].get("thin") for c in content),
        "familiarObjectStated": any(c["e"].get("familiar") for c in content if c["e"]["pos"] == "noun"),
        "sourceTextSha256": sha256_text(norm),
    }
