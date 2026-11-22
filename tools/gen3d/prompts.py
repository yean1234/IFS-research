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
