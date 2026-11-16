"""심상 유지(표류, drift) 판정 — 단계별 스냅샷 비교 (화이트박스, LLM·임베딩 없음).

정의와 임계값의 근거는 docs/drift-design.md, 연구 설계의 요구는 docs/research-design.md 4.5절,
수용 기준은 docs/acceptance.md AC-2.

1) 스냅샷: 참여자 턴 하나마다 그 턴의 텍스트만으로 SceneSpec 슬롯 값(개선 매핑 v1, 없거나 실패하면 v0)과
   형상 명사(정체)를 뽑는다. 단계(Find·Focus·Flesh out·확인 질문) 스냅샷은 그 단계 턴들의 값을
   '나중 턴이 앞 턴을 덮는' 방식으로 합친다. 누적 텍스트를 쓰지 않는다(4.5절: 먼저 말한 값이 이기는 규칙 때문).
2) 1차 쌍: S_first = 값이 하나라도 있는 가장 이른 단계, S_final = 그 뒤 모든 턴에서 슬롯마다 마지막으로 말한 값.
   보조: 인접 단계 쌍의 DI 최댓값.
3) 비교: 둘 다 값이 있는 슬롯만 비교한다(덧붙임·생략은 모순이 아님). 슬롯 판정을 속성 묶음
   (정체·색·크기·위치·자세·표면·움직임)으로 모아 묶음 단위로 센다.
4) DI = 모순 묶음 가중 합 / 비교 가능 묶음 가중 합. 판정 = 정체 모순 또는 DI ≥ θ → drift.
5) 참여자가 바뀌었다고 직접 말한 표지는 acknowledged로 따로 표시한다(판정은 바꾸지 않는다).

같은 턴 텍스트 → 같은 결과(시각·난수 없음). 판정에 LLM을 부르지 않는다(AGENTS.md 1·4).

  python -m ifs_chatbot.drift --cases tests/fixtures/drift/drift_cases.json [--out drift_eval.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .korean import Analyzer, Token
from .paths import shared
from .scene_spec import SLOT_PATHS

DRIFT_VERSION = "drift/1.0.0"
PARAMS_VERSION = "drift-params/1.0.0"
STAGE_ORDER: tuple[str, ...] = ("find", "focus", "flesh_out", "clarify")

# ── 판정 수치 (근거: docs/drift-design.md 3절) ─────────────────────────────────
PARAMS: dict = {
    "version": PARAMS_VERSION,
    # 0–1 단위 슬롯: |Δ| > hard 이거나, 중립점 0.5의 서로 반대쪽이면서 |Δ| > soft 이면 모순
    "tauNumSoft": 0.25,
    "tauNumHard": 0.5,
    "neutral": 0.5,
    # 색: 둘 다 유채색이면 원형 색상 거리 > tauHueDeg 또는 |Δl| > tauL. 한쪽이라도 무채색이면 |Δl| > tauL 또는 |Δs| > tauS
    "tauHueDeg": 60.0,
    "tauL": 0.45,
    "tauS": 0.4,
    "chromaticMinS": 0.15,
    "chromaticL": [0.08, 0.92],
    # 속성 묶음 가중치. 움직임은 상태이지 정체가 아니므로 0(기록만)
    "groupWeights": {"identity": 1.0, "color": 1.0, "size": 1.0, "position": 1.0,
                     "shape": 0.5, "surface": 0.5, "motion": 0.0},
    # 판정 경계: 핵심 묶음 하나(가중 1)의 모순이 비교 가능 가중 최대치(5.0)에서도 drift가 되도록 θ = 1/5
    "theta": 0.2,
    # 자리를 옮기는 움직임(이 값이 첫 스냅샷 이후 턴에 있으면 위치 묶음의 차이는 '움직여서 옮김'으로 본다)
    "translationalMotion": ["moving", "drifting", "rising", "sinking", "settling", "approaching"],
    "selfReportDriftMax": 3,
}

GROUPS: dict[str, tuple[str, ...]] = {
    "identity": ("form.type",),
    "shape": ("form.posture",),
    "color": ("material.color", "material.brightness", "material.saturation"),
    "surface": ("material.roughness", "material.opacity", "material.erosion"),
    "size": ("layout.size",),
    "position": ("body.part", "body.layer", "layout.verticalOffset", "layout.distance"),
    "motion": ("motion.type", "motion.speed"),
}
SLOT_GROUP = {p: g for g, ps in GROUPS.items() for p in ps}
NUMERIC_SLOTS = {"material.brightness", "material.saturation", "material.roughness", "material.opacity",
                 "material.erosion", "layout.size", "layout.distance", "layout.verticalOffset", "motion.speed"}

# motion.type 22종 → Unity 절차 움직임 묶음(unity/.../SpecMotion.cs와 같은 표). 같은 묶음이면 같은 값으로 본다
MOTION_GROUP = {
    "still": "still",
    "swaying": "sway", "sloshing": "sway", "rippling": "sway", "churning": "sway",
    "trembling": "tremble", "vibrating": "tremble", "wriggling": "tremble",
    "pounding": "pulse",
    "moving": "drift", "drifting": "drift", "floating": "drift", "rising": "drift",
    "sinking": "sink", "settling": "sink", "collapsing": "sink",
    "rotating": "spin", "circling": "spin",
    "spreading": "expand", "scattering": "expand",
    "approaching": "approach", "pushing": "approach",
}

# 신체 부위 포함 관계(자식 → 부모). 같은 부위를 더 좁게 말한 것은 다듬기이지 모순이 아니다
BODY_PARENT = {
    "lower_belly": "belly", "heart": "chest", "forehead": "face", "face": "head",
    "throat": "throat_neck", "nape": "throat_neck", "lower_back": "back", "hand": "arm", "foot": "leg",
}
BODY_GENERIC = {"body", "whole_body", "skin"}           # 몸 전체를 가리키는 말은 어느 부위와도 모순이 아니다
LAYER_PARENT = {"surface_above": "surface", "around_front": "around", "around_behind": "around",
                "around_side": "around", "around_below": "around"}

# ── 형상 명사(정체) 사전 (근거: docs/drift-design.md 2.2절) ────────────────────
# 같은 사물을 가리키는 동의어·지소어 묶음. 대표어로 바꿔 비교한다
IDENTITY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "덩어리": ("덩어리", "덩이", "뭉치", "뭉텅이", "뭉터기"),
    "돌": ("돌", "돌멩이", "돌맹이", "자갈", "조약돌"),
    "공": ("공", "볼"),
    "구슬": ("구슬", "알"),
    "방울": ("방울", "물방울", "물망울"),
    "원판": ("원판", "원반"),
    "막대": ("막대", "막대기", "작대기"),
    "천": ("천", "헝겊", "천조각", "보자기"),
    "띠": ("띠", "끈"),
    "빛": ("빛", "불빛", "빛줄기"),
    "안개": ("안개", "연무"),
    "구름": ("구름",),
    "점": ("점",),
}
# 사물의 부분·겉 특징을 가리키는 말(정체가 아니라 부분). scene_params.v1 partNouns에 더한다
MERONYMS = ("날개", "부리", "꼬리", "털", "깃털", "뿔", "가시", "보풀", "결", "주름", "구멍", "틈", "금", "흠집",
            "면", "귀퉁이", "손잡이", "윗면", "아랫면", "옆면", "앞면", "뒷면", "가장자리", "표면", "겉")
# 사물이 내는 성질을 가리킬 수 있는 말: '~ 같은 게'·'~이에요'처럼 이름을 붙일 때만 정체로 본다
PROPERTY_NOUNS = ("빛", "소리", "냄새", "열", "열기", "온기", "기운", "느낌", "감각", "무게", "힘", "그림자")
# 속성 차원·단위·정도를 가리키는 말(정체 아님)
DIMENSION_NOUNS = ("색", "색깔", "빛깔", "색상", "크기", "모양", "모습", "형태", "꼴", "길이", "폭", "너비", "높이",
                   "두께", "정도", "만큼", "쯤", "밝기", "채도", "질감", "촉감", "투명도", "속도", "움직임", "거리",
                   "위치", "온도", "무게감", "개", "번", "바퀴", "뼘", "지름", "반지름", "넓이", "면적", "부피")
TEMPORAL_NOUNS = ("지금", "이제", "현재", "처음", "원래", "아까", "예전", "전", "다음", "나중", "잠시", "가끔", "계속",
                  "오늘", "어제", "아침", "저녁", "밤", "낮", "주말", "순간", "때")
GENERIC_NOUNS = ("것", "거", "게", "뭔가", "무언가", "무엇", "그것", "이것", "하나", "몸", "느낌", "기분", "생각",
                 "자리", "제자리", "근처", "부분", "쪽", "왼쪽", "오른쪽", "위아래", "가로", "세로", "반", "전체",
                 "곳", "데", "군데", "지점")
# 이름을 붙이는 자리('X 같은 게'·'X예요'·'X로 바뀌었어요'·'X.'). 주어 자리('X가 …')보다 앞선다
NAMING_POSITIONS = ("simile_name", "copula", "change", "bare")
DIM_SKIP_BEFORE_CHANGE = {"모양", "모습", "형태", "꼴"}       # 'X 모양으로 바뀌었어요'
CHANGE_VERBS = {"바뀌", "변하", "되", "변해"}
CLAUSE_EC = {"고", "는데", "ᆫ데", "은데", "지만", "면서", "으면서", "으며", "며", "어서", "아서", "여서", "서",
             "다가", "니까", "으니까", "라", "이라"}
FORMER_MARKERS = {"처음", "원래", "아까", "예전"}
CORRECTION_AFTER = {"말고", "보다는", "보단"}
MEASURE_NEXT = {"만", "정도", "만큼", "쯤", "크기", "길이", "높이", "폭", "두께"}
# 참여자가 스스로 바뀌었다고 말한 표지(판정은 바꾸지 않고 acknowledged로만 표시)
ACK_RE = re.compile(r"바뀌었|바뀌어|바뀐|달라졌|달라져|달라진|이제는|이젠|다시\s*보니")


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 3)


# ── 형상 명사 추출 ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class IdentityVocab:
    exclude: frozenset            # 정체가 될 수 없는 명사(신체·관계·부분·배경·차원·때·일반어)
    colors: tuple[str, ...]       # 색 이름 어간(긴 것부터)
    property_nouns: frozenset
    synonyms: dict

    @classmethod
    def load(cls, lexicons=(), params_path: str | Path | None = None) -> "IdentityVocab":
        ex: set[str] = set(MERONYMS) | set(DIMENSION_NOUNS) | set(TEMPORAL_NOUNS) | set(GENERIC_NOUNS)
        colors: set[str] = set()
        p = Path(params_path) if params_path else shared("lexicon", "scene_params.v1.json")
        if p.exists():                                     # 개선 매핑의 공용 사전(읽기만)
            v = json.loads(p.read_text(encoding="utf-8")).get("v1", {})
            for cls_words in (v.get("partNouns") or {}).values():
                ex.update(cls_words)
            ex.update(v.get("relationalNouns") or [])
            ex.update(v.get("backgroundNouns") or [])
            ex.update((v.get("dimensionTopics") or {}).keys())
            colors.update((v.get("colorTerms") or {}).keys())
            colors.update((v.get("colorTints") or {}).keys())
        for lexicon in lexicons:                           # 1층 사전(v0, v1 오버레이)의 신체 부위어
            for e in getattr(lexicon, "entries", None) or []:
                if e.category == "body_part":
                    ex.add(e.lemma)
                    ex.update(e.alt)
        colors.update(("빨강", "주황", "노랑", "초록", "파랑", "보라", "분홍", "하양", "검정", "회색", "갈색", "베이지",
                       "남색", "하늘", "연두", "청록", "은", "금"))
        syn = {w: rep for rep, ws in IDENTITY_SYNONYMS.items() for w in ws}
        return cls(frozenset(ex), tuple(sorted(colors, key=lambda s: (-len(s), s))), frozenset(PROPERTY_NOUNS), syn)

    def is_color_noun(self, form: str, nxt: Token | None) -> bool:
        """색 이름 명사: '베이지 색'처럼 뒤에 색·빛이 붙거나, '하늘색·잿빛'처럼 색·빛으로 끝나거나, 색 이름 어간."""
        if nxt is not None and nxt.base_tag in ("NNG", "NNB") and nxt.form in ("색", "빛", "빛깔", "색깔"):
            return True
        if len(form) > 1 and form[-1] in ("색", "빛") and form not in ("불빛",):
            return True
        return form in self.colors or any(form.endswith(c) for c in self.colors if len(c) >= 2)

    def canon(self, head: str) -> str:
        return self.synonyms.get(head, head)


def same_identity(a: str, b: str, vocab: IdentityVocab) -> bool:
    """대표어가 같거나, 한쪽이 다른 쪽의 오른쪽 머리(합성어·하위어: 물방울 ⊃ 방울, 참새 ⊃ 새)이면 같은 정체."""
    ca, cb = vocab.canon(a), vocab.canon(b)
    if ca == cb:
        return True
    return a.endswith(b) or b.endswith(a) or ca.endswith(cb) or cb.endswith(ca)


def _sentences(toks: list[Token]) -> list[list[int]]:
    out, cur = [], []
    for i, t in enumerate(toks):
        cur.append(i)
        if t.tag == "SF":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _clauses(toks: list[Token], sent: list[int]) -> list[list[int]]:
    out, cur = [], []
    for i in sent:
        cur.append(i)
        t = toks[i]
        if (t.tag == "EC" and t.form in CLAUSE_EC) or t.tag == "SP":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def identity_nouns(text: str, analyzer: Analyzer, vocab: IdentityVocab) -> dict:
    """한 턴의 텍스트에서 형상 명사(정체)를 뽑는다.

    정체 자리: (a) 'X 같은 게'  (b) 'X예요·X이요'  (c) 'X(모양)으로 바뀌었어요·X가 됐어요'  (d) 'X가·X는·X도'(주어·화제).
    빼는 것: 회상 문장('~던 장면')·예전 표지 절('처음엔')·부정('X가 아니라')·비유('X처럼')·크기 비교('X만 해요')·
    장소('X에')·목적어('X를')·신체·관계·부분·배경·차원·때·색 이름. 성질 명사(빛·소리…)는 (a)–(c)에서만 정체.
    """
    toks = analyzer.tokens(text)
    found: list[dict] = []
    dropped: list[dict] = []
    for sent in _sentences(toks):
        forms = {(toks[i].form, toks[i].base_tag) for i in sent}
        if ("던", "ETM") in forms or ("장면", "NNG") in forms:
            continue                                         # 회상 문장: 떠올린 상황이지 형상이 아니다
        for clause in _clauses(toks, sent):
            former = any(toks[i].form in FORMER_MARKERS for i in clause)
            idx = [i for i in clause]
            k = 0
            while k < len(idx):
                i = idx[k]
                t = toks[i]
                if t.base_tag not in ("NNG", "NNP"):
                    k += 1
                    continue
                # 이어진 명사 묶음(합성어) [i..j]
                j = i
                while j + 1 < len(toks) and toks[j + 1].base_tag in ("NNG", "NNP") and j + 1 in clause:
                    j += 1
                run = list(range(i, j + 1))
                k += len(run)
                while j > i and toks[j].form in DIM_SKIP_BEFORE_CHANGE:
                    j -= 1                               # 'X 모양으로' → 머리는 X
                run = list(range(i, j + 1))
                # 묶음 안에서 정체가 될 수 없는 말을 떼어 낸다(색 이름·차원어 등은 수식어로 본다)
                keep = []
                for q in run:
                    f = toks[q].form
                    nq = toks[q + 1] if q + 1 < len(toks) else None
                    if f in vocab.exclude or vocab.is_color_noun(f, nq):
                        keep = []                        # 뒤에 오는 명사만 머리 후보로 남긴다
                        continue
                    keep.append(q)
                if not keep or keep[-1] != j:
                    continue                             # 머리(마지막 명사)가 정체가 아님
                head = toks[j].form
                surface = text[toks[keep[0]].start:toks[j].end]
                pos = _identity_position(toks, j)
                rec = {"surface": surface, "head": head, "class": vocab.canon(head), "position": pos,
                       "charSpan": [toks[keep[0]].start, toks[j].end]}
                if former:
                    dropped.append({**rec, "why": "former_clause"})
                elif pos in ("negated", "simile_property", "measure", "locative", "object", None):
                    if pos in ("negated", "simile_property", "measure"):
                        dropped.append({**rec, "why": pos})
                elif pos == "subject" and head in vocab.property_nouns:
                    dropped.append({**rec, "why": "property_noun_subject"})
                else:
                    found.append(rec)
    return {"nouns": found, "dropped": dropped}


def _identity_position(toks: list[Token], j: int) -> str | None:
    n = len(toks)
    nxt = toks[j + 1] if j + 1 < n else None
    if nxt is None or nxt.tag in ("SF", "SP"):
        return "bare"                                    # '돌멩이.' 같은 이름 대답
    f, tg = nxt.form, nxt.base_tag
    if tg == "VA" and f == "같" and j + 2 < n and toks[j + 2].base_tag == "ETM":
        return "simile_name"                             # X 같은 게
    if f in ("처럼", "같이") or (tg == "VA" and f == "같"):
        return "simile_property"                         # X처럼 부드러워요
    if tg == "VCP" or (tg == "JX" and f in ("이요", "요")):
        return "copula"
    if f in MEASURE_NEXT or tg == "XSN" or tg in ("XSA", "XSV"):
        return "measure" if (f in MEASURE_NEXT or tg == "XSN") else None
    if f in CORRECTION_AFTER:
        return "negated"
    if tg in ("JKS", "JKC"):
        after = toks[j + 2] if j + 2 < n else None
        if after is not None and after.base_tag == "VCN":
            return "negated"                             # X가 아니라
        if tg == "JKC" and after is not None and after.form in CHANGE_VERBS:
            return "change"                              # X가 됐어요
        return "subject"
    if tg == "JX" and f in ("은", "는", "ᆫ", "도"):
        return "subject"
    if tg == "JKB":
        if f in ("로", "으로") and any(toks[m].form in CHANGE_VERBS and toks[m].base_tag == "VV"
                                      for m in range(j + 2, min(n, j + 5))):
            return "change"                              # X로 바뀌었어요
        return "locative"
    if tg == "JKO":
        return "object"
    if tg in ("NNG", "NNB") and f in DIM_SKIP_BEFORE_CHANGE:
        return _identity_position(toks, j + 1) if _identity_position(toks, j + 1) == "change" else None
    return None


# ── 비교 ──────────────────────────────────────────────────────────────────────
def hue_distance_deg(h1: float, h2: float) -> float:
    """원형 색상 거리(도). h는 0–1(= 색상각/360)."""
    d = abs(float(h1) - float(h2)) % 1.0
    return round(min(d, 1.0 - d) * 360.0, 3)


def is_chromatic(c: dict, params: dict = PARAMS) -> bool:
    lo, hi = params["chromaticL"]
    return c["s"] >= params["chromaticMinS"] and lo < c["l"] < hi


def compare_color(a: dict, b: dict, params: dict = PARAMS) -> dict:
    dl = round(abs(a["l"] - b["l"]), 3)
    ds = round(abs(a["s"] - b["s"]), 3)
    out = {"dl": dl, "ds": ds, "dHueDeg": None}
    if is_chromatic(a, params) and is_chromatic(b, params):
        dh = hue_distance_deg(a["h"], b["h"])
        out["dHueDeg"] = dh
        if dh > params["tauHueDeg"]:
            return {**out, "verdict": "contradict", "reason": "hue"}
        if dl > params["tauL"]:
            return {**out, "verdict": "contradict", "reason": "lightness"}
        return {**out, "verdict": "agree", "reason": None}
    if dl > params["tauL"]:
        return {**out, "verdict": "contradict", "reason": "lightness"}
    if ds > params["tauS"]:
        return {**out, "verdict": "contradict", "reason": "saturation(achromatic)"}
    return {**out, "verdict": "agree", "reason": None}


def compare_numeric(a: float, b: float, params: dict = PARAMS) -> dict:
    d = round(abs(float(a) - float(b)), 3)
    m = params["neutral"]
    crosses = (a - m) * (b - m) < 0
    if d > params["tauNumHard"]:
        return {"delta": d, "verdict": "contradict", "reason": "beyond_hard"}
    if crosses and d > params["tauNumSoft"]:
        return {"delta": d, "verdict": "contradict", "reason": "crosses_neutral"}
    return {"delta": d, "verdict": "agree", "reason": None}


def _ancestors(v: str, parent: dict) -> list[str]:
    out = [v]
    while v in parent:
        v = parent[v]
        out.append(v)
    return out


def compare_body_part(a: str, b: str) -> dict:
    if a == b or a in BODY_GENERIC or b in BODY_GENERIC:
        return {"verdict": "agree", "reason": None if a == b else "generic"}
    if a in _ancestors(b, BODY_PARENT) or b in _ancestors(a, BODY_PARENT):
        return {"verdict": "agree", "reason": "refinement"}
    return {"verdict": "contradict", "reason": "different_part"}


def compare_layer(a: str, b: str) -> dict:
    ta, tb = _ancestors(a, LAYER_PARENT)[-1], _ancestors(b, LAYER_PARENT)[-1]
    if ta == tb:
        return {"verdict": "agree", "reason": None if a == b else "refinement"}
    return {"verdict": "contradict", "reason": "different_layer"}


def compare_slot(path: str, a, b, params: dict = PARAMS) -> dict:
    if path == "material.color":
        return compare_color(a, b, params)
    if path in NUMERIC_SLOTS:
        return compare_numeric(a, b, params)
    if path == "body.part":
        return compare_body_part(a, b)
    if path == "body.layer":
        return compare_layer(a, b)
    if path == "motion.type":
        ga, gb = MOTION_GROUP.get(a, a), MOTION_GROUP.get(b, b)
        return {"verdict": "agree" if ga == gb else "contradict", "reason": None if ga == gb else "motion_group",
                "groups": [ga, gb]}
    return {"verdict": "agree" if a == b else "contradict", "reason": None if a == b else "category"}


def compare_identity(a: list[dict], b: list[dict], vocab: IdentityVocab) -> dict:
    """둘 다 형상 명사가 있을 때만 비교. 겹치는 정체가 하나라도 있으면 같은 정체."""
    if not a or not b:
        return {"comparable": False}
    ha = sorted({x["head"] for x in a})
    hb = sorted({x["head"] for x in b})
    same = any(same_identity(x, y, vocab) for x in ha for y in hb)
    return {"comparable": True, "from": ha, "to": hb, "verdict": "agree" if same else "contradict",
            "reason": None if same else "identity_changed"}


# ── 판정기 ─────────────────────────────────────────────────────────────────────
class DriftAssessor:
    """턴 목록 → 스냅샷 → 쌍 비교 → DI·판정. builder는 build(text) -> SceneSpec dict."""

    def __init__(self, analyzer: Analyzer, builder, fallback_builder=None, vocab: IdentityVocab | None = None,
                 params: dict | None = None, builder_label: str = "v1"):
        self.analyzer = analyzer
        self.builder = builder
        self.fallback = fallback_builder
        self.builder_label = builder_label
        self.vocab = vocab or IdentityVocab.load()
        self.params = params or PARAMS

    @classmethod
    def from_runtime(cls, rt) -> "DriftAssessor":
        v1 = rt.scene_builders.get("v1")
        v0 = rt.scene_builders["v0"]
        vocab = IdentityVocab.load([rt.lexicon, getattr(v1, "lexicon", None)])
        if v1 is not None:
            return cls(rt.analyzer, v1, v0, vocab, builder_label="v1")
        return cls(rt.analyzer, v0, None, vocab, builder_label="v0")

    def info(self) -> dict:
        b = self.builder.info() if hasattr(self.builder, "info") else {}
        return {"driftVersion": DRIFT_VERSION, "params": self.params["version"], "snapshotBuilder": self.builder_label,
                "builder": b.get("builder")}

    # 턴 하나의 스냅샷
    def turn_snapshot(self, turn: dict) -> dict:
        text = turn["text"]
        used, err = self.builder_label, None
        try:
            spec = self.builder.build(text)
        except Exception as exc:  # noqa: BLE001 — v1이 실패하면 v0로 스냅샷을 만든다
            if self.fallback is None:
                raise
            err = f"{type(exc).__name__}: {exc}"[:200]
            spec, used = self.fallback.build(text), "v0"
        slots, evidence, unconfirmed = {}, {}, {}
        for path in SLOT_PATHS:
            g, k = path.split(".")
            v = (spec.get(g) or {}).get(k)
            if v is None:
                continue
            v = {kk: _r(vv) for kk, vv in v.items()} if isinstance(v, dict) else (
                _r(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
            provs = (spec.get("_provenance") or {}).get(path) or []
            trigger = provs[0].get("trigger") if provs else None
            if provs and all(pv.get("needsConfirmation") for pv in provs):
                unconfirmed[path] = {"value": v, "trigger": trigger}   # 매핑이 '확인 필요'로 표시한 퍼지 일치: 비교에 쓰지 않음
                continue
            slots[path] = v
            evidence[path] = trigger
        ident = identity_nouns(text, self.analyzer, self.vocab)
        return {"i": turn.get("i"), "stage": turn["stage"], "slots": slots, "evidence": evidence,
                "identity": ident["nouns"], "identityDropped": ident["dropped"], "unconfirmed": unconfirmed,
                "builder": used,
                **({"builderError": err} if err else {})}

    @staticmethod
    def merge(snaps: list[dict]) -> dict:
        """나중 턴이 앞 턴을 덮는다(슬롯별). 정체는 이름 자리(X 같은 게·X예요·X로 바뀌었어요) 명사가 있는
        마지막 턴의 것, 그런 턴이 없으면 주어 자리 명사가 있는 마지막 턴의 것('가장자리가 …'류 부분 주어가
        이미 이름 붙인 정체를 덮지 않게)."""
        slots, src = {}, {}
        named, named_turn, subj, subj_turn = [], None, [], None
        for s in snaps:
            for p, v in s["slots"].items():
                slots[p] = v
                src[p] = {"i": s["i"], "stage": s["stage"], "trigger": s["evidence"].get(p)}
            n = [x for x in s["identity"] if x["position"] in NAMING_POSITIONS]
            if n:
                named, named_turn = n, s["i"]
            elif s["identity"]:
                subj, subj_turn = s["identity"], s["i"]
        ident, ident_turn = (named, named_turn) if named else (subj, subj_turn)
        return {"slots": slots, "source": src, "identity": ident, "identityTurn": ident_turn,
                "turns": [s["i"] for s in snaps]}

    def compare(self, a: dict, b: dict, moved: bool) -> dict:
        P = self.params
        slot_rows = []
        groups: dict[str, dict] = {}
        for path in SLOT_PATHS:
            if path not in a["slots"] or path not in b["slots"]:
                continue                                          # 덧붙임·생략: 비교하지 않는다
            res = compare_slot(path, a["slots"][path], b["slots"][path], P)
            g = SLOT_GROUP[path]
            if g == "position" and moved and res["verdict"] == "contradict":
                res = {**res, "verdict": "explained_by_motion"}
            slot_rows.append({"path": path, "group": g, "from": a["slots"][path], "to": b["slots"][path], **res})
            gr = groups.setdefault(g, {"group": g, "weight": P["groupWeights"][g], "slots": [], "verdict": "agree"})
            gr["slots"].append(path)
            if res["verdict"] == "contradict":
                gr["verdict"] = "contradict"
        ident = compare_identity(a["identity"], b["identity"], self.vocab)
        if ident["comparable"]:                                   # 정체 명사가 있으면 form.type보다 앞선다
            gr = groups.setdefault("identity", {"group": "identity", "weight": P["groupWeights"]["identity"],
                                                "slots": [], "verdict": "agree"})
            gr["slots"].append("identityNoun")
            gr["verdict"] = ident["verdict"]
        identity_contradiction = ident.get("verdict") == "contradict"
        ordered = [groups[g] for g in GROUPS if g in groups]
        comparable = round(sum(g["weight"] for g in ordered), 3)
        contradicted = round(sum(g["weight"] for g in ordered if g["verdict"] == "contradict"), 3)
        di = round(contradicted / comparable, 3) if comparable > 0 else None
        if identity_contradiction or (di is not None and di >= P["theta"]):
            decision = "drift"
        elif di is None and not ident["comparable"]:
            decision = "undecidable"
        else:
            decision = "no_drift"
        return {"slots": slot_rows, "identity": ident, "groups": ordered, "comparableWeight": comparable,
                "contradictedWeight": contradicted, "DI": di, "identityContradiction": identity_contradiction,
                "movedByStatedMotion": moved, "decision": decision}

    def assess(self, turns: list[dict], confirmation_edited: bool = False) -> dict:
        """turns: [{"i", "stage", "text"}] — 참여자가 쓴 답(넘어가기·'없어요' 제외)만, 시간 순."""
        P = self.params
        turns = [t for t in turns if t.get("stage") in STAGE_ORDER and (t.get("text") or "").strip()]
        snaps = [self.turn_snapshot(t) for t in turns]
        by_stage: dict[str, list[dict]] = {}
        for s in snaps:
            by_stage.setdefault(s["stage"], []).append(s)
        stages = [st for st in STAGE_ORDER if st in by_stage]
        stage_snaps = {st: self.merge(by_stage[st]) for st in stages}
        nonempty = [st for st in stages if stage_snaps[st]["slots"] or stage_snaps[st]["identity"]]
        out: dict = {"version": DRIFT_VERSION, "params": dict(P), "snapshotBuilder": self.builder_label,
                     "turns": snaps,
                     "stages": [{"stage": st, **stage_snaps[st]} for st in stages],
                     "confirmationEdited": bool(confirmation_edited)}
        if not nonempty:
            out.update(primary=None, adjacent=[], maxAdjacentDI=None, decision="undecidable",
                       acknowledged={"flag": False, "markers": []}, reason="no_snapshot")
            return out
        first = nonempty[0]
        first_turns = set(stage_snaps[first]["turns"])
        later = [s for s in snaps if STAGE_ORDER.index(s["stage"]) > STAGE_ORDER.index(first)]
        trans = set(P["translationalMotion"])
        moved = any(s["slots"].get("motion.type") in trans for s in snaps
                    if STAGE_ORDER.index(s["stage"]) >= STAGE_ORDER.index(first))
        final = self.merge(later)
        primary = None
        if later and (final["slots"] or final["identity"]):
            primary = {"from": first, "to": "final", **self.compare(stage_snaps[first], final, moved)}
        adjacent = []
        for x, y in zip(nonempty, nonempty[1:]):
            mv = any(s["slots"].get("motion.type") in trans for s in by_stage[x] + by_stage[y])
            c = self.compare(stage_snaps[x], stage_snaps[y], mv)
            adjacent.append({"from": x, "to": y, "DI": c["DI"], "identityContradiction": c["identityContradiction"],
                             "decision": c["decision"]})
        dis = [a["DI"] for a in adjacent if a["DI"] is not None]
        markers = [{"i": s["i"], "stage": s["stage"], "match": m.group(0)}
                   for s, t in zip(snaps, turns) if s["i"] not in first_turns for m in ACK_RE.finditer(t["text"])]
        out.update(first=first, final=final, primary=primary, adjacent=adjacent,
                   maxAdjacentDI=max(dis) if dis else None,
                   decision=primary["decision"] if primary else "undecidable",
                   DI=primary["DI"] if primary else None,
                   acknowledged={"flag": bool(markers), "markers": markers})
        if primary is None:
            out["reason"] = "no_later_snapshot"
        return out

    def recall_anchor(self, turns: list[dict], max_eojeol: int = 3) -> dict | None:
        """회상 확인 문구의 X: 첫 스냅샷 단계에서 참여자가 쓴 형상 명사(원문 그대로). 없으면 None."""
        turns = [t for t in turns if t.get("stage") in STAGE_ORDER and (t.get("text") or "").strip()]
        for st in STAGE_ORDER:
            cand = None
            for t in turns:
                if t["stage"] != st:
                    continue
                nouns = identity_nouns(t["text"], self.analyzer, self.vocab)["nouns"]
                nouns = [x for x in nouns if x["position"] in NAMING_POSITIONS] or nouns
                if nouns and (cand is None or nouns[0]["position"] in NAMING_POSITIONS
                              or cand.get("position") not in NAMING_POSITIONS):
                    cand = {"x": nouns[0]["surface"], "i": t.get("i"), "stage": st, "charSpan": nouns[0]["charSpan"],
                            "position": nouns[0]["position"]}
            if cand and len(cand["x"].split()) <= max_eojeol:
                return cand
            if any(t["stage"] == st for t in turns):
                return None                                  # 첫 단계에 형상 명사가 없으면 묻지 않는다
        return None


def summarize(assessment: dict | None) -> dict | None:
    """연구자 화면용 요약(세션 로그 drift.summary)."""
    if not assessment:
        return None
    p = assessment.get("primary") or {}
    return {"decision": assessment.get("decision"), "DI": assessment.get("DI"),
            "identityContradiction": p.get("identityContradiction"),
            "contradicted": [g["group"] for g in p.get("groups", []) if g["verdict"] == "contradict"],
            "comparable": [g["group"] for g in p.get("groups", [])],
            "acknowledged": (assessment.get("acknowledged") or {}).get("flag"),
            "maxAdjacentDI": assessment.get("maxAdjacentDI"), "first": assessment.get("first")}


def participant_turns(log_turns: list[dict], clarify: dict | None = None) -> list[dict]:
    """세션 로그 턴 → 판정 입력. 버튼(control:*)과 '없어요'류(noMore)는 뺀다(확정 텍스트에 들어가지 않는 답).
    확인 질문 루프의 답(확정 텍스트에 덧붙은 것)은 'clarify' 단계로 넣는다."""
    used_clarify = {t.get("turn") for t in ((clarify or {}).get("turns") or []) if t.get("used")}
    out = []
    for t in log_turns:
        if t.get("speaker") != "participant" or str(t.get("source", "")).startswith("control"):
            continue
        if (t.get("flags") or {}).get("noMore"):
            continue
        stage = "clarify" if t.get("i") in used_clarify else t.get("stage")
        if stage not in STAGE_ORDER:
            continue
        out.append({"i": t["i"], "stage": stage, "text": t.get("text") or ""})
    return out


# ── 시나리오 평가 (AC-2) ───────────────────────────────────────────────────────
def evaluate_cases(path: str | Path, mapper: str = "v0") -> dict:
    """정답 라벨 시나리오를 실제 컨트롤러 정적 조건 재생(eval/corpus_run)으로 돌려 판정을 모은다.
    라벨이 없는 코퍼스(예: imagery_corpus/dev.json)도 돌릴 수 있다(판정 분포만 보고)."""
    from .config import load_config
    from .eval.corpus_run import CONDITION, drive_item, make_runtime

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    base = load_config().with_overrides(**{"drift.enabled": True, "drift.recall_check": False,
                                           "drift.self_report": False})
    rows = []
    with tempfile.TemporaryDirectory(prefix="ifs-drift-eval-") as tmp:
        rt, _ = make_runtime(Path(tmp), mapper, base)
        for item in data["items"]:
            sid = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in str(item["id"]))[:40]
            rt.sessions.pop(sid, None)
            s = rt.new_session(CONDITION, sid)
            drive_item(s, item)
            a = (s.log.data.get("drift") or {}).get("assessment") or {}
            pred = "drift" if a.get("decision") == "drift" else "no_drift"
            p = a.get("primary") or {}
            rows.append({"id": item["id"], "label": item.get("label"), "type": item.get("type"),
                         "predicted": pred, "decision": a.get("decision"), "DI": a.get("DI"),
                         "identityContradiction": p.get("identityContradiction"),
                         "contradicted": [g["group"] for g in p.get("groups", []) if g["verdict"] == "contradict"],
                         "acknowledgedLabel": item.get("acknowledged"),
                         "acknowledgedPred": (a.get("acknowledged") or {}).get("flag"),
                         "maxAdjacentDI": a.get("maxAdjacentDI"), "snapshotBuilder": a.get("snapshotBuilder")})
    labeled = [r for r in rows if r["label"] in ("drift", "no_drift")]
    cm = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for r in labeled:
        key = ("t" if r["predicted"] == r["label"] else "f") + ("p" if r["predicted"] == "drift" else "n")
        cm[key] += 1
    n = len(labeled)
    ack = [r for r in labeled if r["acknowledgedLabel"] is not None]
    return {
        "evaluator": DRIFT_VERSION, "params": PARAMS_VERSION, "corpusId": data.get("corpusId"),
        "corpusVersion": data.get("version"), "items": rows,
        "metrics": {
            "n": n, "nDrift": sum(r["label"] == "drift" for r in labeled),
            "nNoDrift": sum(r["label"] == "no_drift" for r in labeled),
            "accuracy": round((cm["tp"] + cm["tn"]) / n, 3) if n else None,
            "confusion": cm,
            "additionOnlyFalsePositives": sum(r["type"] == "a" and r["predicted"] == "drift" for r in labeled),
            "undecidable": sum(r["decision"] == "undecidable" for r in rows),
            "acknowledgedAgreement": (round(sum(r["acknowledgedLabel"] == r["acknowledgedPred"] for r in ack) / len(ack), 3)
                                      if ack else None),
            "predictedDrift": sum(r["predicted"] == "drift" for r in rows),
        },
    }


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.drift", description="심상 유지(표류) 판정 시나리오 평가")
    ap.add_argument("--cases", required=True, help="drift_cases.json 또는 라벨 없는 코퍼스")
    ap.add_argument("--out", help="결과 JSON 파일")
    args = ap.parse_args(argv)
    res = evaluate_cases(args.cases)
    for r in res["items"]:
        print(f"{r['id']:6} label={str(r['label']):9} pred={r['predicted']:9} DI={r['DI']!s:6} "
              f"identity={r['identityContradiction']!s:5} contra={','.join(r['contradicted']) or '-'} "
              f"ack={r['acknowledgedPred']}")
    print(json.dumps(res["metrics"], ensure_ascii=False))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
