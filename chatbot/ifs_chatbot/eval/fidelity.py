"""심상-구현 일치도 채점 — 정답(gold) 대비 SceneSpec 슬롯 값을 판정한다. LLM 없음, 결정론적.

  python -m ifs_chatbot.eval.fidelity --corpus tests/fixtures/imagery_corpus/dev.json --mapper v0 --out <폴더>
  → <폴더>/runs.json(항목별 확정 텍스트·spec·컨트롤러 기록), report.json, report.md

  python -m ifs_chatbot.eval.fidelity --corpus <코퍼스> --mapper v0 --compare <모듈:factory> --out <폴더>
  → <폴더>/runs.json·report.*(--mapper), <폴더>/compare/runs.json·report.*(--compare), <폴더>/paired.json·paired.md

  python -m ifs_chatbot.eval.fidelity --check-corpus <코퍼스>
  → 정답 라벨 형식 검사만(재생·채점 없음). 오류가 있으면 종료 코드 1. 출력에 phrase 원문은 넣지 않는다
    (held-out 문장을 보지 않고도 검사할 수 있게 항목 id·정답 번호·attr·slot·expect만 적는다).

## 정답 속성의 종류(kind)

| kind | 조건 | 쓰는 판정 |
| --- | --- | --- |
| slot | slot ≠ null, negated = false, expect ≠ null | reflected / distorted / preserved / lost / dropped_by_controller |
| slot_unscored | slot ≠ null, negated = false, expect = null | captured / preserved / lost / dropped_by_controller (반영률 분모에서 뺌) |
| negated | negated = true | preserved / lost / dropped_by_controller + negationError 표시 |
| no_slot | slot = null, negated = false | preserved / lost / dropped_by_controller |

## expect 형식(check_expect가 검사)

- {"equals": v}: 값 == v. {"equals": null}은 값이 null이어야 만족. v는 슬롯 값 형식(범주형은 스키마 enum, 수치는 0–1).
- {"in": [v, …]}: 범주형 슬롯만. 비어 있지 않고 null이 없는 enum 값 목록.
- {"range": [lo, hi]}: 수치 슬롯만. 0 ≤ lo ≤ hi ≤ 1.
- {"hue_deg": [lo, hi] | null, "s": [lo, hi] | null, "l": [lo, hi] | null}: material.color만. 세 키 중 일부만 적어도 된다.
  **키가 없거나 값이 null인 구성요소는 검사하지 않는다.** hue_deg는 0–360(lo > hi면 0°를 넘는 원형 구간), s·l은 0–1, lo ≤ hi.
  검사할 구성요소가 하나도 없으면(모두 null) 어떤 색이든 만족하므로 경고한다.

## 판정(slot)

- 위치: phrase를 정규화해 확정 텍스트에서 찾은 모든 구간(occurrence). 확정 텍스트에 없고 replies에는 있으면
  **dropped_by_controller**(컨트롤러가 그 답을 쓰지 않음 — 묻지 않은 프로브 등). replies에도 없으면 phrase_missing(코퍼스 오류, 집계 제외).
- **reflected**: spec[slot]이 expect를 만족한다(위 expect 형식).
- **distorted**: 값이 있으나 expect를 만족하지 않음(wrong_value), 또는 값이 null인데 그 phrase가 다른 슬롯 값을 잘못
  만듦(cross_slot: phrase 구간과 겹치는 _provenance가 다른 경로 P에 있고, P를 가진 정답 phrase가 그 근거를 덮지 않으며,
  P의 값이 P의 정답을 만족하지도 않음).
- **preserved**: 값이 null이고, phrase 구간의 공백 아닌 글자가 모두 보존 필드(_provenance를 뺀 '_' 최상위 키:
  _unmatched, _unmapped, _negated, _alternatives, _inferred, 개선 매핑이 더하는 보존 필드)의 원문 근거(charSpan과
  그 구간의 원문과 같은 surface/trigger/text/phrase)로 덮임. 원문 그대로(구간 포함)만 인정한다.
- **lost**: 위 어디에도 해당하지 않음.

no_slot·negated·slot_unscored의 보존: no_slot은 보존 필드 ∪ _provenance(값의 근거로 남은 것도 원문 보존으로 봄),
negated는 보존 필드만(값으로 쓰인 것은 오류이므로 보존으로 치지 않음). slot_unscored는 phrase와 겹치는 근거로 그 슬롯에
값이 생겼으면 captured.

## 지표

- 반영률 = reflected / slot 수 · 왜곡률 = distorted / slot 수 · 손실률 = lost / slot 수 · 컨트롤러 탈락률 = dropped / slot 수
- 보존률 = (reflected + captured + preserved) / 전체 속성 수(모든 kind, dropped 포함)
- 미반영 원문 보존률 = 반영·포착되지 않은 속성(dropped 제외) 중 phrase가 보존 필드에 원문 그대로 있는 비율(상태와 무관한
  verbatim 판정). 원문을 "잃지 않고 남겼다"는 뜻일 뿐 의미가 보존되었다는 뜻은 아니다.
- 배경 오염 = distractor 구간과 겹치는 _provenance 근거가 들어간 (distractor, 경로) 쌍의 수(정답 phrase가 그 경로로
  덮으면 제외). 그 근거가 값을 정한 첫 근거이면 decisive(값 자체를 배경이 정함)
- 근거 없는 값 — 두 가지를 함께 보고한다(docs/research-design.md 4.4와 같은 정의, 원칙 2 감시).
  · 경로 기준(spurious, Spurious_c) = 값이 있는 슬롯 중 그 항목 정답(부정 아님)에 그 경로가 없는 것의 수 / 값이 있는 슬롯 수.
  · 근거 기준(unsupported, Unsupported_c) = 값이 있는 슬롯 중, 그 슬롯의 _provenance charSpan 어느 것도 **같은 항목의
    같은 경로를 가진 부정 아닌 정답 phrase가 확정 텍스트에서 차지한 구간**과 겹치지 않는 것의 수 / 값이 있는 슬롯 수.
    사유: no_evidence(_provenance 구간 없음) · no_gold_span(그 경로의 정답이 없거나, 있어도 phrase가 확정 텍스트에 없음 —
    예: 컨트롤러가 버린 프로브 답) · outside_gold_span(근거가 정답 구간 밖). 값이 틀렸는지는 보지 않는다(그것은 왜곡률).
    경로 기준으로 근거 없는 값은 근거 기준으로도 근거 없는 값이다(spurious ⊆ unsupported).
    valueMatchesGold: 근거는 정답 구간 밖이지만 값은 그 경로 정답의 expect를 만족한다. 정답 라벨이 같은 속성의 여러 언급 중
    하나만 표시했을 때(예: 같은 낱말을 두 번 말함) 생기므로 따로 센다(unsupportedValueMatchesGold). 라벨 누락인지 사람이 확인한다.
- 부정 오류 = negated phrase 구간과 겹치는 _provenance 근거로 생긴 슬롯 값이 있는 negated 속성 수

## 추론 단위(항목 군집)

한 항목(문장) 안의 정답 속성은 서로 독립이 아니다. 그래서 신뢰구간은 **항목 단위 군집 부트스트랩**으로 낸다. 항목을
복원 추출(B회, 고정 시드 BOOTSTRAP_SEED, random.Random)하고, 뽑힌 항목들의 분자 합 / 분모 합(합동 비율)을 다시 계산한
백분위 95% 구간이다. 분모가 0인 재표본은 버리고 그 수를 남긴다. 두 매핑 비교(paired_compare)는 같은 재표본 항목에서
두 매핑의 합동 비율 차이를 계산한다(항목 단위 쌍차이). 30개 코퍼스의 구간은 이 합성 코퍼스에서의 변동만 나타내며
일반 성능의 증거가 아니다.

## 정답 구간 폭(expectWidths)

넓은 허용 구간은 반영률을 쉽게 올린다. 그래서 kind = slot 속성의 expect 종류별 수, range 폭·hue 폭·s·l 폭의 분포,
expect 종류별 반영률, range 폭이 중앙값 이하/초과인 속성의 반영률을 함께 보고한다.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from ..korean import normalize
from ..scene_spec import SLOT_PATHS

SCORER_VERSION = "0.2.0"
STATUSES = ("reflected", "distorted", "preserved", "lost", "dropped_by_controller", "captured")
TEXT_KEYS = ("surface", "trigger", "text", "phrase")
VALUE_EVIDENCE_KEY = "_provenance"
COLOR_SLOT = "material.color"
COLOR_KEYS = ("hue_deg", "s", "l")
BOOTSTRAP_B = 10000
BOOTSTRAP_SEED = 20261116
CI_LEVEL = 0.95

# 지표 이름 → (분자 키, 분모 키). _counts()의 키. 전체 요약·부트스트랩·쌍 비교가 같은 정의를 쓴다.
METRICS: dict[str, tuple[str, str]] = {
    "reflectRate": ("reflected", "slot"),
    "distortRate": ("distorted", "slot"),
    "lostRate": ("lost", "slot"),
    "droppedRate": ("dropped", "slot"),
    "preserveRate": ("preservedAll", "attrs"),
    "unreflectedVerbatimRate": ("unreflectedVerbatim", "unreflected"),
    "spuriousRate": ("spurious", "values"),
    "unsupportedRate": ("unsupported", "values"),
}
UNSUPPORTED_REASONS = ("no_evidence", "no_gold_span", "outside_gold_span")

Span = tuple[int, int]


# ── 기본 도우미 ──────────────────────────────────────────────────────────────
def find_spans(text: str, phrase: str) -> list[Span]:
    """정규화한 phrase가 text에 나타나는 모든 구간(겹치지 않게)."""
    p = normalize(phrase)
    out, i = [], 0
    if not p:
        return out
    while True:
        j = text.find(p, i)
        if j < 0:
            return out
        out.append((j, j + len(p)))
        i = j + len(p)


def overlaps(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def get_value(spec: dict | None, path: str):
    group, key = path.split(".")
    return ((spec or {}).get(group) or {}).get(key)


def satisfies(value, expect: dict) -> bool:
    """value가 expect를 만족하는가. expect 키: equals | in | range | hue_deg/s/l(색).
    색 expect에서 키가 없거나 값이 null인 구성요소는 검사하지 않는다."""
    if "equals" in expect:
        return value == expect["equals"]
    if value is None:
        return False
    if "in" in expect:
        return value in expect["in"]
    if "range" in expect:
        lo, hi = expect["range"]
        return isinstance(value, (int, float)) and not isinstance(value, bool) and lo <= value <= hi
    if set(expect) & set(COLOR_KEYS):
        unknown = set(expect) - set(COLOR_KEYS)
        if unknown:
            raise ValueError(f"모르는 expect 키: {sorted(unknown)}")
        if not isinstance(value, dict) or not {"h", "s", "l"} <= set(value):
            return False
        if expect.get("hue_deg") is not None:
            hue = (float(value["h"]) * 360.0) % 360.0
            lo, hi = expect["hue_deg"]
            if not (lo <= hue <= hi if lo <= hi else (hue >= lo or hue <= hi)):
                return False
        for k in ("s", "l"):
            if expect.get(k) is not None and not (expect[k][0] <= float(value[k]) <= expect[k][1]):
                return False
        return True
    raise ValueError(f"모르는 expect 형식: {expect}")


def show_value(value):
    """리포트 표시용: 색은 hue를 도 단위로."""
    if isinstance(value, dict) and {"h", "s", "l"} <= set(value):
        return {"hue_deg": round(float(value["h"]) * 360, 1), "s": value["s"], "l": value["l"]}
    return value


def value_evidence(spec: dict | None) -> list[tuple[str, Span, str]]:
    """(경로, 구간, trigger) — 슬롯 값의 근거."""
    out = []
    for path, provs in ((spec or {}).get(VALUE_EVIDENCE_KEY) or {}).items():
        for p in provs or []:
            cs = p.get("charSpan")
            if isinstance(cs, (list, tuple)) and len(cs) == 2:
                out.append((path, (int(cs[0]), int(cs[1])), p.get("trigger", "")))
    return out


def _walk(node, found: list[tuple[Span, str]]):
    if isinstance(node, dict):
        cs = node.get("charSpan")
        txt = next((node[k] for k in TEXT_KEYS if isinstance(node.get(k), str)), None)
        if isinstance(cs, (list, tuple)) and len(cs) == 2 and txt is not None:
            found.append(((int(cs[0]), int(cs[1])), txt))
        for v in node.values():
            _walk(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk(v, found)


def preservation_spans(spec: dict | None, text: str) -> list[Span]:
    """보존 필드('_'로 시작하는 최상위 키 중 _provenance 제외)에 원문 그대로 남은 구간.
    근거 문자열이 확정 텍스트의 그 구간과 글자까지 같아야 인정한다."""
    found: list[tuple[Span, str]] = []
    for key, node in (spec or {}).items():
        if key.startswith("_") and key != VALUE_EVIDENCE_KEY:
            _walk(node, found)
    return sorted({sp for sp, txt in found if 0 <= sp[0] <= sp[1] <= len(text) and text[sp[0]:sp[1]] == txt})


def coverage(text: str, span: Span, spans: list[Span]) -> float:
    """span 안의 공백 아닌 글자 중 spans로 덮인 비율."""
    idx = [i for i in range(span[0], span[1]) if not text[i].isspace()]
    if not idx:
        return 1.0
    covered = sum(1 for i in idx if any(s <= i < e for s, e in spans))
    return covered / len(idx)


def kind_of(g: dict) -> str:
    if g.get("negated"):
        return "negated"
    if g.get("slot") is None:
        return "no_slot"
    return "slot" if g.get("expect") is not None else "slot_unscored"


# ── 정답 라벨 형식 검사 ───────────────────────────────────────────────────────
@lru_cache(maxsize=None)
def slot_kind(path: str) -> tuple[str, tuple]:
    """('color' | 'categorical' | 'numeric', 범주형이면 enum 값). 스키마(shared/schemas/scene-spec.v2.json)에서 읽는다."""
    if path == COLOR_SLOT:
        return "color", ()
    from ..scene_spec import schema
    group, key = path.split(".")
    node = schema()["properties"][group]["properties"][key]
    if "enum" in node:
        return "categorical", tuple(v for v in node["enum"] if v is not None)
    return "numeric", ()


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _pair(x, lo_bound: float, hi_bound: float, allow_wrap: bool = False) -> str | None:
    """[lo, hi] 형식이면 None, 아니면 문제 설명."""
    if not (isinstance(x, list) and len(x) == 2 and all(_is_num(v) for v in x)):
        return f"[lo, hi] 숫자 두 개여야 합니다: {x!r}"
    lo, hi = x
    if not (lo_bound <= lo <= hi_bound and lo_bound <= hi <= hi_bound):
        return f"{lo_bound}–{hi_bound} 밖입니다: {x!r}"
    if lo > hi and not allow_wrap:
        return f"lo > hi입니다: {x!r}"
    return None


def check_expect(expect, slot: str | None = None) -> tuple[list[str], list[str]]:
    """expect 하나의 형식 검사. (오류, 경고). slot을 주면 슬롯 종류(스키마)와 맞는지도 본다."""
    errs: list[str] = []
    warns: list[str] = []
    if expect is None:
        return errs, warns
    if not isinstance(expect, dict) or not expect:
        return [f"expect는 비어 있지 않은 객체이거나 null이어야 합니다: {expect!r}"], warns
    kind, enum = slot_kind(slot) if slot in SLOT_PATHS else (None, ())
    keys = set(expect)
    if keys == {"equals"}:
        v = expect["equals"]
        if v is not None and kind == "categorical" and v not in enum:
            errs.append(f"equals 값 {v!r}가 {slot}의 enum에 없습니다")
        elif v is not None and kind == "numeric" and not (_is_num(v) and 0 <= v <= 1):
            errs.append(f"equals 값 {v!r}가 0–1 수치가 아닙니다")
        elif v is not None and kind == "color":
            errs.append("색 슬롯의 equals는 null만 씁니다(값은 hue_deg/s/l 구간으로)")
    elif keys == {"in"}:
        lst = expect["in"]
        if not isinstance(lst, list) or not lst:
            errs.append(f"in은 비어 있지 않은 목록이어야 합니다: {lst!r}")
        elif any(v is None for v in lst):
            errs.append("in 목록에 null이 있습니다(null은 {\"equals\": null}로)")
        elif kind in ("numeric", "color"):
            errs.append(f"in은 범주형 슬롯에만 씁니다({slot})")
        elif kind == "categorical":
            bad = [v for v in lst if v not in enum]
            if bad:
                errs.append(f"in 값 {bad!r}가 {slot}의 enum에 없습니다")
    elif keys == {"range"}:
        if kind in ("categorical", "color"):
            errs.append(f"range는 수치 슬롯에만 씁니다({slot})")
        problem = _pair(expect["range"], 0.0, 1.0)
        if problem:
            errs.append(f"range: {problem}")
    elif keys <= set(COLOR_KEYS):
        if kind is not None and kind != "color":
            errs.append(f"hue_deg/s/l은 {COLOR_SLOT}에만 씁니다({slot})")
        for k in COLOR_KEYS:
            if expect.get(k) is None:
                continue
            problem = _pair(expect[k], 0.0, 360.0, allow_wrap=True) if k == "hue_deg" else _pair(expect[k], 0.0, 1.0)
            if problem:
                errs.append(f"{k}: {problem}")
        if all(expect.get(k) is None for k in COLOR_KEYS):
            warns.append("색 expect에 검사할 구성요소가 없어 어떤 색이든 만족합니다")
    else:
        errs.append(f"모르는 expect 형식(키 {sorted(keys)})")
    return errs, warns


def check_corpus(corpus: dict) -> dict:
    """코퍼스 정답 라벨 형식 검사. phrase 원문은 메시지에 넣지 않는다(id·정답 번호·attr·slot·expect만).
    오류: 채점이 틀리거나 예외를 낼 형식. 경고: 채점은 되지만 의도와 다를 수 있는 것."""
    errors: list[str] = []
    warnings: list[str] = []
    items = corpus.get("items") if isinstance(corpus, dict) else None
    if not isinstance(items, list):
        return {"errors": ["items 목록이 없습니다"], "warnings": [], "items": 0, "gold": 0}
    seen: set = set()
    n_gold = 0
    for n, it in enumerate(items):
        iid = it.get("id") if isinstance(it, dict) else None
        where = f"{iid}" if iid is not None else f"items[{n}]"
        if not isinstance(it, dict) or iid is None:
            errors.append(f"{where}: id가 없습니다")
            continue
        if iid in seen:
            errors.append(f"{where}: id가 중복됩니다")
        seen.add(iid)
        replies = it.get("replies")
        if not isinstance(replies, dict):
            errors.append(f"{where}: replies가 객체가 아닙니다")
            replies = {}
        replies_text = "\n".join(normalize(v) for v in replies.values() if isinstance(v, str) and v)
        gold = it.get("gold")
        if not isinstance(gold, list):
            errors.append(f"{where}: gold가 목록이 아닙니다")
            continue
        for k, g in enumerate(gold):
            n_gold += 1
            if not isinstance(g, dict):
                errors.append(f"{where} gold[{k}]: 객체가 아닙니다")
                continue
            at = f"{where} gold[{k}] attr={g.get('attr')!r} slot={g.get('slot')!r}"
            if not isinstance(g.get("attr"), str) or not g.get("attr"):
                errors.append(f"{at}: attr가 없습니다")
            phrase = g.get("phrase")
            if not isinstance(phrase, str) or not normalize(phrase):
                errors.append(f"{at}: phrase가 비어 있습니다")
            elif not find_spans(replies_text, phrase):
                warnings.append(f"{at}: phrase가 replies에 없습니다(phrase_missing, 집계 제외)")
            slot = g.get("slot")
            if slot is not None and slot not in SLOT_PATHS:
                errors.append(f"{at}: 모르는 slot입니다")
                slot = None
            if "negated" in g and not isinstance(g["negated"], bool):
                errors.append(f"{at}: negated가 true/false가 아닙니다")
            e, w = check_expect(g.get("expect"), slot)
            errors += [f"{at}: {m}" for m in e]
            warnings += [f"{at}: {m}" for m in w]
            if g.get("expect") is not None and g.get("negated"):
                warnings.append(f"{at}: 부정 속성의 expect는 채점에 쓰지 않습니다")
            elif g.get("expect") is not None and g.get("slot") is None:
                warnings.append(f"{at}: slot이 없는 속성의 expect는 채점에 쓰지 않습니다")
        for k, d in enumerate(it.get("distractors") or []):
            if not isinstance(d, dict) or not isinstance(d.get("phrase"), str) or not normalize(d["phrase"]):
                errors.append(f"{where} distractors[{k}]: phrase가 없습니다")
    return {"errors": errors, "warnings": warnings, "items": len(items), "gold": n_gold}


# ── 한 항목 채점 ─────────────────────────────────────────────────────────────
def score_item(item: dict, run: dict) -> dict:
    """item: 코퍼스 항목(gold, distractors, replies). run: {confirmedText, spec, ...}."""
    text = run.get("confirmedText") or ""
    spec = run.get("spec") or {}
    replies_text = "\n".join(normalize(v) for v in (item.get("replies") or {}).values() if v)
    evidence = value_evidence(spec)
    keep = preservation_spans(spec, text)
    keep_and_values = sorted(set(keep) | {sp for _, sp, _ in evidence})
    gold = item.get("gold") or []
    occ = [find_spans(text, g["phrase"]) for g in gold]

    def licensed(path: str, span: Span) -> bool:
        """그 경로의 (부정 아닌) 정답 phrase가 이 근거 구간과 겹치는가."""
        return any(g.get("slot") == path and not g.get("negated") and any(overlaps(span, o) for o in occ[k])
                   for k, g in enumerate(gold))

    def benign(path: str) -> bool:
        """그 경로의 현재 값이 그 경로의 (부정 아닌) 정답 하나를 만족하는가."""
        v = get_value(spec, path)
        return v is not None and any(g.get("slot") == path and kind_of(g) == "slot" and satisfies(v, g["expect"])
                                     for g in gold)

    attrs = []
    for k, g in enumerate(gold):
        kind, spans = kind_of(g), occ[k]
        rec = {"attr": g["attr"], "phrase": g["phrase"], "slot": g.get("slot"), "kind": kind,
               "expect": g.get("expect"), "spans": [list(s) for s in spans]}
        if not spans:
            rec["status"] = "dropped_by_controller" if find_spans(replies_text, g["phrase"]) else "phrase_missing"
            attrs.append(rec)
            continue
        touching = [(p, sp, trig) for p, sp, trig in evidence if any(overlaps(sp, o) for o in spans)]
        verbatim = any(coverage(text, o, keep) >= 1.0 for o in spans)
        rec["verbatimPreserved"] = verbatim
        rec["coverageAny"] = round(max(coverage(text, o, keep_and_values) for o in spans), 3)
        rec["phraseEvidence"] = [{"path": p, "trigger": t} for p, _, t in touching]
        if kind in ("slot", "slot_unscored"):
            value = get_value(spec, g["slot"])
            rec["actual"] = show_value(value)
            rec["valueTriggers"] = [t for p, _, t in evidence if p == g["slot"]]
            cross = [{"path": p, "trigger": t, "value": show_value(get_value(spec, p))}
                     for p, sp, t in touching if p != g["slot"] and not licensed(p, sp) and not benign(p)]
            rec["crossSlot"] = cross
            if kind == "slot":
                ok = satisfies(value, g["expect"])
                rec["inAlternatives"] = any(a.get("path") == g["slot"] and satisfies(a.get("value"), g["expect"])
                                            for a in spec.get("_alternatives") or [])
                if ok:
                    rec["status"] = "reflected"
                elif value is not None:
                    rec["status"], rec["reason"] = "distorted", "wrong_value"
                elif cross:
                    rec["status"], rec["reason"] = "distorted", "cross_slot"
                else:
                    rec["status"] = "preserved" if verbatim else "lost"
            else:
                from_phrase = value is not None and any(p == g["slot"] for p, _, _ in touching)
                rec["status"] = "captured" if from_phrase else ("preserved" if verbatim else "lost")
        elif kind == "negated":
            errs = [{"path": p, "trigger": t, "value": show_value(get_value(spec, p))}
                    for p, sp, t in touching if not licensed(p, sp)]
            rec["negationError"] = errs
            rec["status"] = "preserved" if verbatim else "lost"
        else:  # no_slot
            full = any(coverage(text, o, keep_and_values) >= 1.0 for o in spans)
            rec["mappedTo"] = sorted({p for p, _, _ in touching})
            rec["status"] = "preserved" if full else "lost"
        attrs.append(rec)

    contamination, seen = [], set()
    for d in item.get("distractors") or []:
        for o in find_spans(text, d["phrase"]):
            for p, sp, t in evidence:
                if overlaps(sp, o) and not licensed(p, sp) and (d["phrase"], p) not in seen:
                    seen.add((d["phrase"], p))
                    first = ((spec.get(VALUE_EVIDENCE_KEY) or {}).get(p) or [{}])[0].get("charSpan")
                    contamination.append({"phrase": d["phrase"], "path": p, "trigger": t,
                                          "value": show_value(get_value(spec, p)),
                                          "decisive": list(sp) == list(first or [])})

    # 근거 없는 값 ① 경로 기준(spurious): 정답(부정 아님)에 그 경로가 없음
    gold_slots = {g["slot"] for g in gold if g.get("slot") and not g.get("negated")}
    filled = [p for p in SLOT_PATHS if get_value(spec, p) is not None]
    spurious = [{"path": path, "value": show_value(get_value(spec, path)),
                 "triggers": [t for p, _, t in evidence if p == path]}
                for path in filled if path not in gold_slots]
    # 근거 없는 값 ② 근거 기준(unsupported): 값의 _provenance 구간이 같은 경로 정답 phrase의 확정 텍스트 구간과 안 겹침
    unsupported = []
    for path in filled:
        ev = [sp for p, sp, _ in evidence if p == path]
        gold_spans = [o for k, g in enumerate(gold) if g.get("slot") == path and not g.get("negated") for o in occ[k]]
        if any(overlaps(sp, o) for sp in ev for o in gold_spans):
            continue
        reason = "no_evidence" if not ev else ("no_gold_span" if not gold_spans else "outside_gold_span")
        unsupported.append({"path": path, "value": show_value(get_value(spec, path)), "reason": reason,
                            "triggers": [t for p, _, t in evidence if p == path], "spurious": path not in gold_slots,
                            "valueMatchesGold": benign(path)})
    return {"id": item["id"], "style": item.get("style"), "attributes": attrs,
            "contamination": contamination, "spurious": spurious, "unsupported": unsupported,
            "valuesFilled": len(filled), "negationErrors": sum(1 for a in attrs if a.get("negationError"))}


# ── 집계 ────────────────────────────────────────────────────────────────────
def _rate(n: int, d: int):
    return round(n / d, 4) if d else None


def _counts(attrs: list[dict], items: list[dict]) -> dict:
    """지표의 분자·분모 원자료(METRICS가 가리키는 키). phrase_missing은 뺀다."""
    attrs = [a for a in attrs if a["status"] != "phrase_missing"]
    slot = [a for a in attrs if a["kind"] == "slot"]
    sc = Counter(a["status"] for a in slot)
    allc = Counter(a["status"] for a in attrs)
    unref = [a for a in attrs if a["status"] not in ("reflected", "captured", "dropped_by_controller")]
    return {
        "attrs": len(attrs), "slot": len(slot),
        "reflected": sc["reflected"], "distorted": sc["distorted"], "lost": sc["lost"],
        "dropped": sc["dropped_by_controller"],
        "preservedAll": allc["reflected"] + allc["captured"] + allc["preserved"],
        "unreflected": len(unref), "unreflectedVerbatim": sum(1 for a in unref if a.get("verbatimPreserved")),
        "values": sum(i["valuesFilled"] for i in items),
        "spurious": sum(len(i["spurious"]) for i in items),
        "unsupported": sum(len(i.get("unsupported") or []) for i in items),
    }


def _summary(attrs: list[dict], items: list[dict]) -> dict:
    c = _counts(attrs, items)
    attrs = [a for a in attrs if a["status"] != "phrase_missing"]
    slot = [a for a in attrs if a["kind"] == "slot"]
    sc = Counter(a["status"] for a in slot)
    allc = Counter(a["status"] for a in attrs)
    negs = [a for a in attrs if a["kind"] == "negated"]
    reasons = Counter(u["reason"] for i in items for u in i.get("unsupported") or [])
    return {
        "attributes": c["attrs"],
        "slotAttributes": c["slot"],
        "slotStatus": {s: sc.get(s, 0) for s in ("reflected", "distorted", "preserved", "lost", "dropped_by_controller")},
        "allStatus": {s: allc.get(s, 0) for s in STATUSES},
        **{m: _rate(c[a], c[b]) for m, (a, b) in METRICS.items()},
        "unreflected": c["unreflected"],
        "negated": len(negs),
        "negationErrors": sum(1 for a in negs if a.get("negationError")),
        "contamination": sum(len(i["contamination"]) for i in items),
        "contaminationDecisive": sum(1 for i in items for c_ in i["contamination"] if c_.get("decisive")),
        "spuriousValues": c["spurious"],
        "unsupportedValues": c["unsupported"],
        "unsupportedReasons": {r: reasons.get(r, 0) for r in UNSUPPORTED_REASONS},
        "unsupportedValueMatchesGold": sum(1 for i in items for u in i.get("unsupported") or [] if u.get("valueMatchesGold")),
        "valuesFilled": c["values"],
        "crossSlotSideEffects": sum(len(a.get("crossSlot") or []) for a in attrs),
    }


def item_counts(scored_item: dict) -> dict:
    return _counts(scored_item["attributes"], [scored_item])


def _quantile(sorted_vals: list[float], q: float) -> float:
    """선형 보간 분위수(numpy 기본과 같은 방식)."""
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _bootstrap(per_item: list[tuple[dict, ...]], stat, B: int, seed: int, level: float) -> dict:
    """항목 단위 군집 부트스트랩. per_item[i]는 항목 i의 counts 묶음(매핑 1개 또는 2개).
    stat(합친 counts 묶음) → {지표: 값 또는 None}."""
    rng = random.Random(seed)
    n = len(per_item)
    names = list(METRICS)
    reps: dict[str, list[float]] = {m: [] for m in names}
    if n:
        width = len(per_item[0])
        keys = list(per_item[0][0])
        for _ in range(B):
            idx = [rng.randrange(n) for _ in range(n)]
            sums = tuple({k: sum(per_item[i][j][k] for i in idx) for k in keys} for j in range(width))
            for m, v in stat(sums).items():
                if v is not None:
                    reps[m].append(v)
    alpha = (1 - level) / 2
    out = {}
    for m in names:
        r = sorted(reps[m])
        out[m] = {"lo": round(_quantile(r, alpha), 4) if r else None,
                  "hi": round(_quantile(r, 1 - alpha), 4) if r else None,
                  "replicates": len(r)}
    return out


def _pooled(c: dict) -> dict:
    return {m: (c[a] / c[b] if c[b] else None) for m, (a, b) in METRICS.items()}


def bootstrap_ci(scored: list[dict], B: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED, level: float = CI_LEVEL) -> dict:
    """전체 지표의 항목 단위 군집 부트스트랩 백분위 구간."""
    per_item = [(item_counts(i),) for i in scored]
    total = _counts([a for i in scored for a in i["attributes"]], scored)
    ci = _bootstrap(per_item, lambda sums: _pooled(sums[0]), B, seed, level)
    return {"unit": "item", "method": "cluster bootstrap, percentile", "B": B, "seed": seed, "level": level,
            "nItems": len(scored),
            "metrics": {m: {"estimate": _rate(total[a], total[b]), **ci[m]} for m, (a, b) in METRICS.items()}}


def _five(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    s = sorted(vals)
    return {"n": len(s), "min": round(s[0], 4), "median": round(_quantile(s, 0.5), 4),
            "mean": round(sum(s) / len(s), 4), "max": round(s[-1], 4)}


def expect_type(expect: dict) -> str:
    if "equals" in expect:
        return "equals_null" if expect["equals"] is None else "equals"
    if "in" in expect:
        return "in"
    if "range" in expect:
        return "range"
    return "color_hue" if expect.get("hue_deg") is not None else "color_sl"


def hue_width(pair) -> float:
    lo, hi = pair
    return float(hi - lo) if lo <= hi else float(360 - lo + hi)


def expect_widths(scored: list[dict]) -> dict:
    """kind = slot 정답의 expect 종류·구간 폭 통계와 종류·폭별 반영률(phrase_missing 제외)."""
    slot = [a for i in scored for a in i["attributes"] if a["kind"] == "slot" and a["status"] != "phrase_missing"]
    by_type: dict[str, list[dict]] = defaultdict(list)
    for a in slot:
        by_type[expect_type(a["expect"])].append(a)
    ranges = [a for a in slot if "range" in a["expect"]]
    rw = [float(a["expect"]["range"][1] - a["expect"]["range"][0]) for a in ranges]
    colors = [a["expect"] for a in slot if expect_type(a["expect"]).startswith("color")]
    med = _quantile(sorted(rw), 0.5) if rw else None

    def refl(group: list[dict]) -> dict:
        return {"n": len(group), "reflected": sum(1 for a in group if a["status"] == "reflected"),
                "reflectRate": _rate(sum(1 for a in group if a["status"] == "reflected"), len(group))}

    range_by_slot = defaultdict(list)
    for a, w in zip(ranges, rw):
        range_by_slot[a["slot"]].append(w)
    return {
        "byType": {t: refl(by_type[t]) for t in sorted(by_type)},
        "inListLength": _five([float(len(a["expect"]["in"])) for a in by_type.get("in", [])]),
        "rangeWidth": _five(rw),
        "rangeWidthBySlot": {s: _five(v) for s, v in sorted(range_by_slot.items())},
        "rangeReflectByWidth": {
            "median": round(med, 4) if med is not None else None,
            "atOrBelowMedian": refl([a for a, w in zip(ranges, rw) if med is not None and w <= med]),
            "aboveMedian": refl([a for a, w in zip(ranges, rw) if med is not None and w > med]),
        },
        "hueWidthDeg": _five([hue_width(e["hue_deg"]) for e in colors if e.get("hue_deg") is not None]),
        "sWidth": _five([float(e["s"][1] - e["s"][0]) for e in colors if e.get("s") is not None]),
        "lWidth": _five([float(e["l"][1] - e["l"][0]) for e in colors if e.get("l") is not None]),
    }


def aggregate(scored: list[dict], B: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED) -> dict:
    attrs = [dict(a, id=i["id"], style=i.get("style")) for i in scored for a in i["attributes"]]
    by_attr: dict[str, dict] = {}
    groups = defaultdict(list)
    for a in attrs:
        if a["status"] != "phrase_missing":
            groups[a["attr"]].append(a)
    for name in sorted(groups):
        c = Counter(a["status"] for a in groups[name])
        slot_n = sum(1 for a in groups[name] if a["kind"] == "slot")
        by_attr[name] = {"n": len(groups[name]), "slotN": slot_n, **{s: c.get(s, 0) for s in STATUSES},
                         "reflectRate": _rate(sum(1 for a in groups[name] if a["kind"] == "slot" and a["status"] == "reflected"), slot_n)}
    by_style = {st: _summary([a for a in attrs if a["style"] == st], [i for i in scored if i.get("style") == st])
                for st in sorted({i["style"] for i in scored if i.get("style")})}
    by_item = {i["id"]: _summary(i["attributes"], [i]) for i in scored}
    return {"overall": _summary(attrs, scored), "bootstrap": bootstrap_ci(scored, B, seed),
            "expectWidths": expect_widths(scored), "byAttr": by_attr, "byStyle": by_style, "byItem": by_item,
            "phraseMissing": [{"id": a["id"], "phrase": a["phrase"]} for a in attrs if a["status"] == "phrase_missing"]}


def failures(scored: list[dict], runs: dict[str, dict]) -> list[dict]:
    """문서용 실패 사례 목록(결정론적 순서). 근거 기준으로만 근거 없는 값(경로 기준으로는 아님)은 'unsupported'."""
    out = []
    for i in scored:
        trace = (runs.get(i["id"]) or {}).get("controllerTrace") or {}
        for a in i["attributes"]:
            if a["kind"] == "slot" and a["status"] in ("distorted", "lost", "preserved", "dropped_by_controller"):
                out.append({"id": i["id"], "type": a["status"], "reason": a.get("reason"), "attr": a["attr"],
                            "phrase": a["phrase"], "slot": a["slot"], "expect": a["expect"], "actual": a.get("actual"),
                            "valueTriggers": a.get("valueTriggers"), "phraseEvidence": a.get("phraseEvidence"),
                            "crossSlot": a.get("crossSlot"), "inAlternatives": a.get("inAlternatives"),
                            "coverageAny": a.get("coverageAny"),
                            "unusedReplies": trace.get("unusedReplies") if a["status"] == "dropped_by_controller" else None})
            elif a["kind"] in ("no_slot", "slot_unscored") and a["status"] in ("lost", "dropped_by_controller"):
                out.append({"id": i["id"], "type": a["status"], "attr": a["attr"], "phrase": a["phrase"],
                            "slot": a["slot"], "kind": a["kind"], "coverageAny": a.get("coverageAny")})
            if a.get("negationError"):
                out.append({"id": i["id"], "type": "negation_error", "attr": a["attr"], "phrase": a["phrase"],
                            "slot": a["slot"], "negationError": a["negationError"]})
        for c in i["contamination"]:
            out.append({"id": i["id"], "type": "contamination", **c})
        for s in i["spurious"]:
            out.append({"id": i["id"], "type": "spurious", **s})
        for u in i.get("unsupported") or []:
            if not u["spurious"]:
                out.append({"id": i["id"], "type": "unsupported", **{k: v for k, v in u.items() if k != "spurious"}})
    return out


def score_runs(corpus: dict, runs: dict, B: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED) -> dict:
    by_id = {r["id"]: r for r in runs["items"]}
    scored = [score_item(item, by_id.get(item["id"], {})) for item in corpus["items"]]
    return {"scorer": f"fidelity/{SCORER_VERSION}", "corpusId": corpus.get("corpusId"),
            "corpusVersion": corpus.get("version"), "mapper": runs.get("mapper"), "builder": runs.get("builder"),
            "analyzer": runs.get("analyzer"), "summary": aggregate(scored, B, seed), "items": scored,
            "failures": failures(scored, by_id)}


# ── 두 매핑 비교(항목 단위 쌍차이) ───────────────────────────────────────────────
def _slot_values(run: dict) -> dict:
    spec = run.get("spec") or {}
    return {p: get_value(spec, p) for p in SLOT_PATHS}


def paired_compare(report_a: dict, report_b: dict, runs_a: dict | None = None, runs_b: dict | None = None,
                   B: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED, level: float = CI_LEVEL) -> dict:
    """같은 코퍼스에 대한 두 채점 결과의 항목 단위 쌍 비교. 차이 = b − a(합동 비율).
    신뢰구간은 같은 재표본 항목에서 두 매핑의 합동 비율 차이를 계산한 군집 부트스트랩 백분위 구간."""
    items_a, items_b = report_a["items"], report_b["items"]
    ids_a, ids_b = [i["id"] for i in items_a], [i["id"] for i in items_b]
    if ids_a != ids_b:
        raise ValueError("두 결과의 항목 id 목록이 다릅니다(같은 코퍼스를 같은 순서로 채점해야 합니다)")
    per_item = []
    rows = []
    attr_pairs = Counter()
    sign = {m: Counter() for m in ("reflected", "distorted", "unsupported")}
    for ia, ib in zip(items_a, items_b):
        ca, cb = item_counts(ia), item_counts(ib)
        per_item.append((ca, cb))
        if len(ia["attributes"]) != len(ib["attributes"]):
            raise ValueError(f"{ia['id']}: 정답 속성 수가 다릅니다")
        disc = Counter()
        for aa, ab in zip(ia["attributes"], ib["attributes"]):
            if aa["phrase"] != ab["phrase"] or aa["attr"] != ab["attr"]:
                raise ValueError(f"{ia['id']}: 정답 속성 순서가 다릅니다")
            if aa["kind"] != "slot" or aa["status"] == "phrase_missing":
                continue
            key = ("a" if aa["status"] == "reflected" else "-") + ("b" if ab["status"] == "reflected" else "-")
            disc[key] += 1
            attr_pairs[key] += 1
        for m in sign:
            d = cb[m] - ca[m]
            sign[m]["b_more" if d > 0 else ("b_fewer" if d < 0 else "equal")] += 1
        row = {"id": ia["id"], "style": ia.get("style"), "slotN": ca["slot"],
               "reflectedA": ca["reflected"], "reflectedB": cb["reflected"],
               "distortedA": ca["distorted"], "distortedB": cb["distorted"],
               "unsupportedA": ca["unsupported"], "unsupportedB": cb["unsupported"],
               "verbatimA": ca["unreflectedVerbatim"], "verbatimB": cb["unreflectedVerbatim"],
               "unreflectedA": ca["unreflected"], "unreflectedB": cb["unreflected"],
               "reflectOnlyA": disc["a-"], "reflectOnlyB": disc["-b"]}
        if runs_a is not None and runs_b is not None:
            ra = {r["id"]: r for r in runs_a["items"]}.get(ia["id"]) or {}
            rb = {r["id"]: r for r in runs_b["items"]}.get(ia["id"]) or {}
            row["sameSlotValues"] = _slot_values(ra) == _slot_values(rb)
            row["diffSlots"] = sum(1 for p in SLOT_PATHS if _slot_values(ra)[p] != _slot_values(rb)[p])
        rows.append(row)
    tot_a = _counts([a for i in items_a for a in i["attributes"]], items_a)
    tot_b = _counts([a for i in items_b for a in i["attributes"]], items_b)
    pa, pb = _pooled(tot_a), _pooled(tot_b)

    def diff(sums):
        x, y = _pooled(sums[0]), _pooled(sums[1])
        return {m: (y[m] - x[m] if x[m] is not None and y[m] is not None else None) for m in METRICS}

    ci = _bootstrap(per_item, diff, B, seed, level)
    metrics = {m: {"a": _rate(tot_a[n], tot_a[d]), "b": _rate(tot_b[n], tot_b[d]),
                   "diff": round(pb[m] - pa[m], 4) if pa[m] is not None and pb[m] is not None else None, **ci[m]}
               for m, (n, d) in METRICS.items()}
    out = {"scorer": f"fidelity/{SCORER_VERSION}", "corpusId": report_a.get("corpusId"),
           "corpusVersion": report_a.get("corpusVersion"), "mapperA": report_a.get("mapper"),
           "mapperB": report_b.get("mapper"),
           "bootstrap": {"unit": "item", "method": "paired cluster bootstrap, percentile", "B": B, "seed": seed,
                         "level": level, "nItems": len(rows)},
           "metrics": metrics,
           "itemSigns": {m: {k: c.get(k, 0) for k in ("b_more", "equal", "b_fewer")} for m, c in sign.items()},
           "attributePairs": {"both": attr_pairs["ab"], "onlyA": attr_pairs["a-"], "onlyB": attr_pairs["-b"],
                              "neither": attr_pairs["--"]},
           "items": rows}
    if runs_a is not None and runs_b is not None:
        out["sameSlotValuesItems"] = sum(1 for r in rows if r["sameSlotValues"])
    return out


# ── 출력 ────────────────────────────────────────────────────────────────────
def _fmt(v) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.3f}"
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)


def _ci(m: dict) -> str:
    return f"[{_fmt(m.get('lo'))}, {_fmt(m.get('hi'))}]"


def to_markdown(report: dict) -> str:
    s = report["summary"]["overall"]
    L = [f"# 일치도 채점 — {report.get('corpusId')} · 매핑 {report.get('mapper')}", "",
         f"채점기 {report['scorer']}, 코퍼스 {report.get('corpusId')}@{report.get('corpusVersion')}, "
         f"빌더 {(report.get('builder') or {}).get('builder')}", "",
         "## 전체", "", "| 지표 | 값 |", "| --- | --- |"]
    for k in ("attributes", "slotAttributes", "reflectRate", "distortRate", "lostRate", "droppedRate", "preserveRate",
              "unreflectedVerbatimRate", "negated", "negationErrors", "contamination", "contaminationDecisive",
              "spuriousValues", "unsupportedValues", "valuesFilled", "spuriousRate", "unsupportedRate"):
        L.append(f"| {k} | {_fmt(s[k])} |")
    L += ["", "슬롯 속성 상태: " + ", ".join(f"{k} {v}" for k, v in s["slotStatus"].items()),
          "근거 없는 값(근거 기준) 사유: " + ", ".join(f"{k} {v}" for k, v in s["unsupportedReasons"].items())
          + f" · 그중 값은 정답 expect를 만족 {s['unsupportedValueMatchesGold']}"]
    bs = report["summary"].get("bootstrap")
    if bs:
        L += ["", f"## 신뢰구간(항목 단위 군집 부트스트랩, B = {bs['B']}, 시드 {bs['seed']}, 항목 {bs['nItems']}개)", "",
              "이 합성 코퍼스 안에서의 변동만 나타냅니다. 일반 성능의 증거가 아닙니다.", "",
              "| 지표 | 추정 | 95% 구간 |", "| --- | --- | --- |"]
        for m, v in bs["metrics"].items():
            L.append(f"| {m} | {_fmt(v['estimate'])} | {_ci(v)} |")
    ew = report["summary"].get("expectWidths")
    if ew:
        L += ["", "## 정답 구간 폭(kind = slot)", "", "| expect 종류 | n | reflected | 반영률 |", "| --- | --- | --- | --- |"]
        for t, r in ew["byType"].items():
            L.append(f"| {t} | {r['n']} | {r['reflected']} | {_fmt(r['reflectRate'])} |")
        rw = ew["rangeReflectByWidth"]
        L += ["", "| 폭 | n | 최소 | 중앙값 | 평균 | 최대 |", "| --- | --- | --- | --- | --- | --- |"]
        for name, key in (("range 폭", "rangeWidth"), ("hue 폭(도)", "hueWidthDeg"), ("s 폭", "sWidth"),
                          ("l 폭", "lWidth"), ("in 목록 길이", "inListLength")):
            f = ew[key]
            L.append(f"| {name} | {f['n']} | {_fmt(f['min'])} | {_fmt(f['median'])} | {_fmt(f['mean'])} | {_fmt(f['max'])} |")
        L += ["", f"range 폭 중앙값 {_fmt(rw['median'])} 이하: 반영률 {_fmt(rw['atOrBelowMedian']['reflectRate'])}"
              f" (n {rw['atOrBelowMedian']['n']}) · 초과: 반영률 {_fmt(rw['aboveMedian']['reflectRate'])}"
              f" (n {rw['aboveMedian']['n']})"]
    L += ["", "## 속성 유형별", "", "| 속성 | n | slot n | reflected | distorted | preserved | lost | dropped | captured | 반영률 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, r in report["summary"]["byAttr"].items():
        L.append(f"| {name} | {r['n']} | {r['slotN']} | {r['reflected']} | {r['distorted']} | {r['preserved']} | "
                 f"{r['lost']} | {r['dropped_by_controller']} | {r['captured']} | {_fmt(r['reflectRate'])} |")
    L += ["", "## 항목별", "",
          "| 항목 | slot n | 반영률 | 왜곡률 | 보존률 | 오염 | 부정 오류 | 근거 없는 값(경로) | 근거 없는 값(근거) |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for iid, r in report["summary"]["byItem"].items():
        L.append(f"| {iid} | {r['slotAttributes']} | {_fmt(r['reflectRate'])} | {_fmt(r['distortRate'])} | "
                 f"{_fmt(r['preserveRate'])} | {r['contamination']} | {r['negationErrors']} | {r['spuriousValues']} | "
                 f"{r['unsupportedValues']} |")
    L += ["", "## 실패 사례", "", "| 항목 | 유형 | 속성 | phrase | 기대 | 실제 | 근거 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for f in report["failures"]:
        ev = f.get("valueTriggers") or f.get("triggers") or f.get("trigger") or f.get("negationError") or f.get("crossSlot")
        L.append(f"| {f['id']} | {f['type']}{'/' + f['reason'] if f.get('reason') else ''} | {f.get('attr') or f.get('path')} | "
                 f"{f.get('phrase', '')} | {_fmt(f.get('expect'))} | {_fmt(f.get('actual', f.get('value')))} | {_fmt(ev)} |")
    return "\n".join(L) + "\n"


def paired_markdown(cmp: dict) -> str:
    bs = cmp["bootstrap"]
    L = [f"# 두 매핑 쌍 비교 — {cmp.get('corpusId')} · A = {cmp['mapperA']}, B = {cmp['mapperB']}", "",
         f"채점기 {cmp['scorer']}. 차이 = B − A(합동 비율). 구간은 항목 단위 쌍 군집 부트스트랩(B = {bs['B']}, "
         f"시드 {bs['seed']}, 항목 {bs['nItems']}개)의 백분위 95% 구간입니다. 이 합성 코퍼스 안의 변동만 나타냅니다.", "",
         "| 지표 | A | B | 차이 | 95% 구간 |", "| --- | --- | --- | --- | --- |"]
    for m, v in cmp["metrics"].items():
        L.append(f"| {m} | {_fmt(v['a'])} | {_fmt(v['b'])} | {_fmt(v['diff'])} | {_ci(v)} |")
    ap = cmp["attributePairs"]
    L += ["", f"슬롯 속성 반영 쌍: 둘 다 {ap['both']} · A만 {ap['onlyA']} · B만 {ap['onlyB']} · 둘 다 아님 {ap['neither']}"]
    for m, c in cmp["itemSigns"].items():
        L.append(f"항목 수({m}): B가 많음 {c['b_more']} · 같음 {c['equal']} · B가 적음 {c['b_fewer']}")
    if "sameSlotValuesItems" in cmp:
        L.append(f"슬롯 값이 모두 같은 항목: {cmp['sameSlotValuesItems']} / {len(cmp['items'])}")
    L += ["", "## 항목별", "",
          "| 항목 | slot n | 반영 A | 반영 B | A만 반영 | B만 반영 | 왜곡 A | 왜곡 B | 근거 없음 A | 근거 없음 B | 다른 슬롯 수 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in cmp["items"]:
        L.append(f"| {r['id']} | {r['slotN']} | {r['reflectedA']} | {r['reflectedB']} | {r['reflectOnlyA']} | "
                 f"{r['reflectOnlyB']} | {r['distortedA']} | {r['distortedB']} | {r['unsupportedA']} | "
                 f"{r['unsupportedB']} | {_fmt(r.get('diffSlots'))} |")
    return "\n".join(L) + "\n"


def _dump(o) -> str:
    return json.dumps(o, ensure_ascii=False, indent=2) + "\n"


def _write(out: Path, runs: dict, report: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "runs.json").write_text(_dump(runs), encoding="utf-8")
    (out / "report.json").write_text(_dump(report), encoding="utf-8")
    (out / "report.md").write_text(to_markdown(report), encoding="utf-8")


def _load_checked(corpus_path: str | Path | dict) -> dict:
    """코퍼스(경로 또는 dict)를 읽고 정답 라벨 형식 오류가 있으면 채점하지 않는다."""
    from .corpus_run import load_corpus
    corpus = corpus_path if isinstance(corpus_path, dict) else load_corpus(corpus_path)
    chk = check_corpus(corpus)
    if chk["errors"]:
        raise ValueError("코퍼스 정답 라벨 형식 오류:\n" + "\n".join(chk["errors"]))
    return corpus


def evaluate(corpus_path: str | Path, mapper="v0", out_dir: str | Path | None = None,
             B: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED) -> dict:
    from .corpus_run import run_corpus
    corpus = _load_checked(corpus_path)
    runs = run_corpus(corpus, mapper)
    report = score_runs(corpus, runs, B, seed)
    report["corpusCheck"] = {"errors": 0, "warnings": len(check_corpus(corpus)["warnings"])}
    if out_dir is not None:
        _write(Path(out_dir), runs, report)
    return report


def compare(corpus_path: str | Path, mapper_a="v0", mapper_b="v0", out_dir: str | Path | None = None,
            B: int = BOOTSTRAP_B, seed: int = BOOTSTRAP_SEED) -> dict:
    """같은 코퍼스를 두 매핑으로 재생·채점하고 항목 단위 쌍 비교를 낸다.
    out_dir: A 결과는 out_dir/, B 결과는 out_dir/compare/, 비교는 out_dir/paired.json·paired.md."""
    from .corpus_run import run_corpus
    corpus = _load_checked(corpus_path)
    runs_a, runs_b = run_corpus(corpus, mapper_a), run_corpus(corpus, mapper_b)
    rep_a, rep_b = score_runs(corpus, runs_a, B, seed), score_runs(corpus, runs_b, B, seed)
    cmp = paired_compare(rep_a, rep_b, runs_a, runs_b, B, seed)
    if out_dir is not None:
        out = Path(out_dir)
        _write(out, runs_a, rep_a)
        _write(out / "compare", runs_b, rep_b)
        (out / "paired.json").write_text(_dump(cmp), encoding="utf-8")
        (out / "paired.md").write_text(paired_markdown(cmp), encoding="utf-8")
    return {"a": rep_a, "b": rep_b, "paired": cmp}


def _print_summary(report: dict) -> None:
    s = report["summary"]["overall"]
    ci = report["summary"]["bootstrap"]["metrics"]
    print(f"매핑 {report['mapper']} · 속성 {s['attributes']}개(슬롯 {s['slotAttributes']}개)")
    print(f"  반영률 {s['reflectRate']} {_ci(ci['reflectRate'])}  왜곡률 {s['distortRate']} {_ci(ci['distortRate'])}  "
          f"손실률 {s['lostRate']}  컨트롤러 탈락률 {s['droppedRate']}")
    print(f"  보존률 {s['preserveRate']}  미반영 원문 보존률 {s['unreflectedVerbatimRate']}")
    print(f"  배경 오염 {s['contamination']}(값 결정 {s['contaminationDecisive']})  부정 오류 {s['negationErrors']}/{s['negated']}  "
          f"근거 없는 값 경로 {s['spuriousValues']}/{s['valuesFilled']} · 근거 {s['unsupportedValues']}/{s['valuesFilled']}")


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.fidelity", description="심상-구현 일치도 채점")
    ap.add_argument("--corpus")
    ap.add_argument("--mapper", default="v0", help="v0(기본) 또는 '모듈:factory'")
    ap.add_argument("--compare", help="두 번째 매핑(v0 또는 '모듈:factory'). 주면 항목 단위 쌍 비교를 낸다")
    ap.add_argument("--out", help="결과 폴더")
    ap.add_argument("--bootstrap", type=int, default=BOOTSTRAP_B, help=f"부트스트랩 반복 수(기본 {BOOTSTRAP_B})")
    ap.add_argument("--seed", type=int, default=BOOTSTRAP_SEED, help=f"부트스트랩 시드(기본 {BOOTSTRAP_SEED})")
    ap.add_argument("--check-corpus", metavar="PATH", help="정답 라벨 형식 검사만 한다(phrase 원문은 출력하지 않음)")
    args = ap.parse_args(argv)
    if args.check_corpus:
        from .corpus_run import load_corpus
        chk = check_corpus(load_corpus(args.check_corpus))
        print(f"항목 {chk['items']}개 · 정답 {chk['gold']}개 · 오류 {len(chk['errors'])} · 경고 {len(chk['warnings'])}")
        for m in chk["errors"]:
            print(f"  오류: {m}")
        for m in chk["warnings"]:
            print(f"  경고: {m}")
        sys.exit(1 if chk["errors"] else 0)
    if not args.corpus or not args.out:
        ap.error("--corpus와 --out이 필요합니다(또는 --check-corpus)")
    if args.compare:
        res = compare(args.corpus, args.mapper, args.compare, args.out, args.bootstrap, args.seed)
        _print_summary(res["a"])
        _print_summary(res["b"])
        c = res["paired"]["metrics"]
        print(f"차이(B − A) 반영률 {c['reflectRate']['diff']} {_ci(c['reflectRate'])}  "
              f"왜곡률 {c['distortRate']['diff']} {_ci(c['distortRate'])}")
        print(f"결과: {Path(args.out) / 'paired.md'}")
        return
    report = evaluate(args.corpus, args.mapper, args.out, args.bootstrap, args.seed)
    _print_summary(report)
    print(f"결과: {Path(args.out) / 'report.md'}")


if __name__ == "__main__":
    main()
